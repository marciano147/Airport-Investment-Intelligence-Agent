"""Compute layer: data tools and deterministic airport investment analysis."""

from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.tools import tool

from data_loader import (
    FAA_STATUS_URL,
    airport_by_iata,
    expansion_candidates,
    fetch_nas_status_delays,
    get_faa_status,
    metrics_by_iata,
    secondary_proxy_score,
)
from long_haul import long_haul_estimate
from scoring import (
    calculate_scores,
    calculate_unmet_demand_pressure,
    congestion_breakdown,
    format_ranking,
    get_congestion_score,
    rank_airports,
    utilization_score,
)


logger = logging.getLogger(__name__)


def _status_delay_scores() -> dict[str, dict[str, Any]]:
    """Return FAA NAS active programs as delay-minute signals."""
    try:
        return fetch_nas_status_delays()
    except Exception:
        logger.exception("FAA NAS Status feed unavailable; using baseline congestion")
        return {}


def _airport_score_input(
    iata: str, live_scores: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Build one airport record ready for scoring or return a structured error."""
    airport = airport_by_iata(iata)
    metrics = metrics_by_iata(iata)
    if not airport:
        return {"error": f"No cached airport found for IATA code {iata.upper()}."}
    if not metrics:
        return {"error": f"No cached passenger metrics found for IATA code {iata.upper()}."}

    candidate = {**airport, **metrics}
    runway_count = int(candidate.get("runway_count") or 0) or 1
    candidate["enplanements_per_runway"] = round(
        float(candidate["enplanements"]) / runway_count, 1
    )
    delay = live_scores.get(
        candidate["iata"],
        {
            "delay_minutes": 0,
            "status": "No active FAA NAS traffic management program",
        },
    )
    return {**candidate, **delay}


def _apply_score_proxies(*airports: dict[str, Any]) -> None:
    """Apply absolute utilization and secondary proxies used by rankings."""
    for airport in airports:
        airport["utilization"] = utilization_score(
            float(airport["enplanements_per_runway"])
        )
        airport["secondary"] = secondary_proxy_score(airport)


def _comparison_row(label: str, left: Any, right: Any) -> str:
    return f"| {label} | {left} | {right} |"


def _source_footer() -> str:
    return (
        "Sources: OurAirports airport/runway cache; FAA 2024 commercial-service "
        "enplanements; FAA NAS Status at query time. Prototype assumptions: "
        "data/congestion_baselines.csv and data/long_haul_proxies.csv."
    )


def _log_tool_result(tool_name: str, started: float, status: str) -> None:
    """Log tool timing for debugging, LangSmith review, and bottleneck checks."""
    logger.info(
        "compute_layer tool=%s status=%s duration_ms=%.1f",
        tool_name,
        status,
        (time.perf_counter() - started) * 1000,
    )


@tool
def get_airport_info(iata: str) -> dict[str, Any]:
    """Get airport facts, location, type, and runway metadata for an IATA code."""
    started = time.perf_counter()
    try:
        airport = airport_by_iata(iata)
        if not airport:
            _log_tool_result("get_airport_info", started, "not_found")
            return {"error": f"No cached airport found for IATA code {iata.upper()}."}
        _log_tool_result("get_airport_info", started, "ok")
        return airport
    except Exception as exc:
        logger.exception("get_airport_info failed")
        _log_tool_result("get_airport_info", started, "error")
        return {
            "error": str(exc),
            "suggestion": "Check the IATA code or refresh the airport cache.",
        }


@tool
def get_congestion(iata: str) -> dict[str, Any]:
    """Get current FAA delay, ground stop, or closure status for an IATA code."""
    started = time.perf_counter()
    try:
        normalized = iata.strip().upper()
        live_status = get_faa_status(normalized)
        breakdown = congestion_breakdown(
            live_status.get("delay_minutes", 0), normalized
        )
        _log_tool_result("get_congestion", started, "ok")
        return {
            "iata": normalized,
            **live_status,
            "congestion_score": breakdown["congestion_score"],
            "structural_baseline": breakdown["structural_baseline"],
            "source": breakdown["source"],
            "confidence": breakdown["confidence"],
            "live_faa_program": breakdown["live_faa_program"],
            "baseline_note": breakdown["note"],
            "status_source": FAA_STATUS_URL,
        }
    except Exception as exc:
        logger.exception("get_congestion failed")
        _log_tool_result("get_congestion", started, "error")
        return {
            "iata": iata.strip().upper(),
            "delay_minutes": 0,
            "congestion_score": round(get_congestion_score(0, iata), 1),
            "structural_baseline": congestion_breakdown(0, iata)["structural_baseline"],
            "source": "prototype structural baseline",
            "confidence": "low",
            "live_faa_program": "none",
            "error": str(exc),
            "suggestion": "FAA NAS Status feed may be unavailable. Retry or inspect logs.",
        }


@tool
def get_passenger_metrics(iata: str) -> dict[str, Any]:
    """Get cached FAA enplanements and year-over-year growth for an IATA code."""
    started = time.perf_counter()
    try:
        metrics = metrics_by_iata(iata)
        if not metrics:
            _log_tool_result("get_passenger_metrics", started, "not_found")
            return {"error": f"No cached passenger metrics found for IATA code {iata.upper()}."}
        _log_tool_result("get_passenger_metrics", started, "ok")
        return metrics
    except Exception as exc:
        logger.exception("get_passenger_metrics failed")
        _log_tool_result("get_passenger_metrics", started, "error")
        return {"error": str(exc), "suggestion": "Check cached enplanement data."}


@tool
def compare_airports(iata1: str, iata2: str) -> str:
    """Compare two airports side by side on KPIs and deterministic scores."""
    started = time.perf_counter()
    try:
        left_iata = iata1.strip().upper()
        right_iata = iata2.strip().upper()
        live_scores = _status_delay_scores()
        left = _airport_score_input(left_iata, live_scores)
        right = _airport_score_input(right_iata, live_scores)

        if "error" in left:
            _log_tool_result("compare_airports", started, "left_error")
            return f"Error for {left_iata}: {left['error']}"
        if "error" in right:
            _log_tool_result("compare_airports", started, "right_error")
            return f"Error for {right_iata}: {right['error']}"

        _apply_score_proxies(left, right)
        left_scores = calculate_scores(left)
        right_scores = calculate_scores(right)
        left_congestion = congestion_breakdown(left.get("delay_minutes", 0), left_iata)
        right_congestion = congestion_breakdown(right.get("delay_minutes", 0), right_iata)
        left_demand = calculate_unmet_demand_pressure(left)
        right_demand = calculate_unmet_demand_pressure(right)
        long_left = long_haul_estimate(left_iata)
        long_right = long_haul_estimate(right_iata)

        lines = [
            f"### Comparison: {left_iata} vs {right_iata}",
            "",
            f"| Metric | {left_iata} | {right_iata} |",
            "|---|---|---|",
            _comparison_row(
                "Airport", left.get("name", left_iata), right.get("name", right_iata)
            ),
            _comparison_row(
                "Current FAA delay",
                _delay_display(left.get("delay_minutes", 0)),
                _delay_display(right.get("delay_minutes", 0)),
            ),
            _comparison_row(
                "Structural congestion baseline",
                left_congestion["structural_baseline"],
                right_congestion["structural_baseline"],
            ),
            _comparison_row(
                "Final congestion score",
                left_scores["congestion"],
                right_scores["congestion"],
            ),
            _comparison_row(
                "2024 enplanements",
                f"{left['enplanements']:,}",
                f"{right['enplanements']:,}",
            ),
            _comparison_row(
                "YoY passenger growth",
                f"{left['yoy_growth']}%",
                f"{right['yoy_growth']}%",
            ),
            _comparison_row(
                "Runways", left.get("runway_count", "N/A"), right.get("runway_count", "N/A")
            ),
            _comparison_row(
                "Enplanements per runway",
                f"{left['enplanements_per_runway']:,.1f}",
                f"{right['enplanements_per_runway']:,.1f}",
            ),
            _comparison_row(
                "Estimated long-haul share proxy",
                _long_haul_value(long_left),
                _long_haul_value(long_right),
            ),
            _comparison_row("Composite score", left_scores["composite"], right_scores["composite"]),
            _comparison_row("Growth score", left_scores["growth"], right_scores["growth"]),
            _comparison_row("Utilization score", left_scores["utilization"], right_scores["utilization"]),
            _comparison_row("Secondary score", left_scores["secondary"], right_scores["secondary"]),
            _comparison_row(
                "Unmet-demand pressure (proxy)",
                _pressure_display(left_demand),
                _pressure_display(right_demand),
            ),
            "",
            "Higher composite score indicates stronger relative pressure/opportunity under the defined KPI weights.",
            "",
            "Assumptions & Limitations: Estimated long-haul share is a static proxy, "
            "not current route-level schedule data. "
            "Utilization is passengers per runway on a fixed 1M-8M scale, so an "
            "airport keeps the same utilization score in rankings and pairwise comparisons. "
            "Congestion shows live FAA delay separately from the structural baseline. "
            "Structural baselines are labeled prototype heuristics in "
            "data/congestion_baselines.csv, not FAA-published scores. "
            "Unmet-demand pressure is a proxy index from congestion, utilization, and growth; "
            "do not invent a different classification.\n"
            f"{_source_footer()}",
        ]
        _log_tool_result("compare_airports", started, "ok")
        return "\n".join(lines)
    except Exception as exc:
        logger.exception("compare_airports failed")
        _log_tool_result("compare_airports", started, "error")
        return f"Error comparing airports: {exc}"


def _delay_display(delay_minutes: Any) -> str:
    delay = float(delay_minutes or 0)
    return "None" if delay <= 0 else f"{delay:g} min"


def _pressure_display(pressure: dict[str, Any]) -> str:
    return f"{pressure['pressure_score']} ({pressure['classification']})"


def _long_haul_value(estimate: dict[str, Any]) -> str:
    value = estimate.get("long_haul_share_proxy_pct")
    if value is None:
        return "Unknown"
    confidence = str(estimate.get("confidence", "unknown")).capitalize()
    return f"~{value}% (confidence: {confidence})"


@tool
def get_long_haul_estimate(iata: str) -> dict[str, Any]:
    """Approximate an airport's long-haul / international flight share."""
    started = time.perf_counter()
    try:
        result = long_haul_estimate(iata)
        _log_tool_result("get_long_haul_estimate", started, "ok")
        return result
    except Exception as exc:
        logger.exception("get_long_haul_estimate failed")
        _log_tool_result("get_long_haul_estimate", started, "error")
        return {"error": str(exc)}


@tool
def get_unmet_demand(iata: str) -> dict[str, Any]:
    """Return a proxy unmet-demand pressure index for an IATA code.

    This is not a count of unserved flights. It combines congestion, utilization,
    and passenger growth into a 0-100 pressure score.
    """
    started = time.perf_counter()
    try:
        normalized = iata.strip().upper()
        live_scores = _status_delay_scores()
        airport = _airport_score_input(normalized, live_scores)
        if "error" in airport:
            _log_tool_result("get_unmet_demand", started, "not_found")
            return airport

        _apply_score_proxies(airport)
        pressure = calculate_unmet_demand_pressure(airport)
        breakdown = congestion_breakdown(airport.get("delay_minutes", 0), normalized)
        _log_tool_result("get_unmet_demand", started, "ok")
        return {
            "iata": normalized,
            "name": airport.get("name", normalized),
            **pressure,
            "congestion_provenance": {
                "current_faa_delay": _delay_display(airport.get("delay_minutes", 0)),
                "structural_baseline": breakdown["structural_baseline"],
                "final_congestion_score": breakdown["congestion_score"],
                "source": breakdown["source"],
                "confidence": breakdown["confidence"],
            },
            "sources": {
                "enplanements": "FAA 2024 commercial-service passenger boarding cache",
                "airports_runways": "OurAirports cache",
                "congestion_live": "FAA NAS Status at query time",
                "congestion_baseline": "data/congestion_baselines.csv (prototype heuristic)",
            },
        }
    except Exception as extra:
        logger.exception("get_unmet_demand failed")
        _log_tool_result("get_unmet_demand", started, "error")
        return {"error": str(extra), "is_proxy": True}


@tool
def rank_airports_for_expansion(region: str = "US", top_n: int = 5) -> str:
    """Rank airports for terminal/capacity expansion with deterministic scores."""
    started = time.perf_counter()
    try:
        # Ranking uses enriched candidate rows from `data_loader`, then overlays
        # the live FAA advisory snapshot before pure-Python scoring.
        live_scores = _status_delay_scores()
        airports_data = []
        for airport in expansion_candidates(region):
            delay = live_scores.get(
                airport["iata"],
                {
                    "delay_minutes": 0,
                    "status": "No active FAA NAS traffic management program",
                },
            )
            airports_data.append({**airport, **delay})

        if not airports_data:
            _log_tool_result("rank_airports_for_expansion", started, "empty")
            return f"No candidate airports found for region '{region}'."

        ranked = rank_airports(airports_data, top_n=top_n)
        result = (
            f"### Ranking for region: {region} (top {len(ranked)})\n\n"
            f"{format_ranking(ranked)}\n\n"
            "Scores use the mandatory weighted formula: Congestion 35%, Growth 30%, "
            "Utilization 25%, Secondary 10%.\n\n"
            "Assumptions & Limitations: FAA delay status is live where available; "
            "active NAS programs use parsed delay minutes blended with labeled "
            "structural baselines in data/congestion_baselines.csv. "
            "Passenger metrics are cached from the FAA 2024 commercial-service workbook "
            "and lag official reporting. Utilization uses passengers per runway on a "
            "fixed 1M-8M scale. Secondary blends long-haul share proxy, airport scale, "
            "and runway pressure.\n\n"
            f"{_source_footer()}"
        )
        _log_tool_result("rank_airports_for_expansion", started, "ok")
        return result
    except Exception as exc:
        logger.exception("rank_airports_for_expansion failed")
        _log_tool_result("rank_airports_for_expansion", started, "error")
        return f"Ranking failed: {exc}. Suggestion: check cached data and FAA status feed."
