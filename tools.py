"""LangChain tools for airport investment analysis."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

import requests
from langchain_core.tools import tool

from data_loader import (
    FAA_STATUS_URL,
    airport_by_iata,
    expansion_candidates,
    metrics_by_iata,
)
from long_haul import long_haul_estimate
from scoring import calculate_scores, format_ranking, rank_airports


logger = logging.getLogger(__name__)


def _status_delay_scores() -> dict[str, dict[str, Any]]:
    response = requests.get(FAA_STATUS_URL, timeout=20)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    scores: dict[str, dict[str, Any]] = {}

    for delay_type in root.findall(".//Delay_type"):
        name = delay_type.findtext("Name", default="FAA status").strip()
        for airport in delay_type.findall(".//Airport") + delay_type.findall(
            ".//Ground_Delay"
        ):
            iata = (airport.findtext("ARPT") or "").strip().upper()
            if not iata:
                continue
            delay_minutes = _delay_minutes_for_status(name)
            scores[iata] = {
                "delay_minutes": max(
                    delay_minutes, scores.get(iata, {}).get("delay_minutes", 0)
                ),
                "status": name,
                "reason": airport.findtext(
                    "Reason", default="FAA delay/advisory"
                ).strip(),
            }

    return scores


def _delay_minutes_for_status(status_name: str) -> int:
    if "Closure" in status_name:
        return 60
    if "Ground" in status_name:
        return 45
    if "Delay" in status_name:
        return 30
    return 15


def _airport_score_input(
    iata: str, live_scores: dict[str, dict[str, Any]]
) -> dict[str, Any]:
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
            "status": "No active FAA delay advisory in current feed",
        },
    )
    return {**candidate, **delay}


def _apply_pair_proxies(left: dict[str, Any], right: dict[str, Any]) -> None:
    max_per_runway = max(
        float(left["enplanements_per_runway"]),
        float(right["enplanements_per_runway"]),
        1.0,
    )
    max_enplanements = max(float(left["enplanements"]), float(right["enplanements"]), 1.0)

    for airport in (left, right):
        airport["utilization"] = round(
            (float(airport["enplanements_per_runway"]) / max_per_runway) * 100, 1
        )
        airport["secondary"] = round(
            (1 - (float(airport["enplanements"]) / max_enplanements)) * 100, 1
        )


def _comparison_row(label: str, left: Any, right: Any) -> str:
    return f"| {label} | {left} | {right} |"


@tool
def get_airport_info(iata: str) -> dict[str, Any]:
    """Get airport facts, location, type, and runway metadata for an IATA code."""
    try:
        airport = airport_by_iata(iata)
        if not airport:
            return {"error": f"No cached airport found for IATA code {iata.upper()}."}
        return airport
    except Exception as exc:
        logger.exception("get_airport_info failed")
        return {
            "error": str(exc),
            "suggestion": "Check the IATA code or refresh the airport cache.",
        }


@tool
def get_congestion(iata: str) -> dict[str, Any]:
    """Get current FAA delay, ground stop, or closure status for an IATA code."""
    try:
        normalized = iata.strip().upper()
        live_scores = _status_delay_scores()
        if normalized in live_scores:
            return {"iata": normalized, **live_scores[normalized], "source": FAA_STATUS_URL}
        return {
            "iata": normalized,
            "delay_minutes": 0,
            "status": "No active FAA delay advisory in current feed",
            "source": FAA_STATUS_URL,
        }
    except Exception as exc:
        logger.exception("get_congestion failed")
        return {
            "iata": iata.strip().upper(),
            "delay_minutes": 0,
            "error": str(exc),
            "suggestion": "FAA status feed may be unavailable. Retry or inspect logs.",
        }


@tool
def get_passenger_metrics(iata: str) -> dict[str, Any]:
    """Get cached FAA enplanements and year-over-year growth for an IATA code."""
    try:
        metrics = metrics_by_iata(iata)
        if not metrics:
            return {"error": f"No cached passenger metrics found for IATA code {iata.upper()}."}
        return metrics
    except Exception as exc:
        logger.exception("get_passenger_metrics failed")
        return {"error": str(exc), "suggestion": "Check cached enplanement data."}


@tool
def compare_airports(iata1: str, iata2: str) -> str:
    """Compare two airports side by side on KPIs and deterministic scores."""
    try:
        left_iata = iata1.strip().upper()
        right_iata = iata2.strip().upper()
        live_scores = _status_delay_scores()
        left = _airport_score_input(left_iata, live_scores)
        right = _airport_score_input(right_iata, live_scores)

        if "error" in left:
            return f"Error for {left_iata}: {left['error']}"
        if "error" in right:
            return f"Error for {right_iata}: {right['error']}"

        _apply_pair_proxies(left, right)
        left_scores = calculate_scores(left)
        right_scores = calculate_scores(right)
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
                "Delay minutes",
                left.get("delay_minutes", "N/A"),
                right.get("delay_minutes", "N/A"),
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
                "Long-haul proxy", _long_haul_value(long_left), _long_haul_value(long_right)
            ),
            _comparison_row("Composite score", left_scores["composite"], right_scores["composite"]),
            _comparison_row("Congestion score", left_scores["congestion"], right_scores["congestion"]),
            _comparison_row("Growth score", left_scores["growth"], right_scores["growth"]),
            _comparison_row("Utilization score", left_scores["utilization"], right_scores["utilization"]),
            _comparison_row("Secondary score", left_scores["secondary"], right_scores["secondary"]),
            "",
            "Higher composite score indicates stronger relative pressure/opportunity under the defined KPI weights.",
            "",
            "Assumptions & Limitations: Long-haul share is a static proxy when shown. "
            "Utilization in direct comparisons is peer-relative between the selected "
            "airports; regional rankings use peer-relative enplanements per runway.",
        ]
        return "\n".join(lines)
    except Exception as exc:
        logger.exception("compare_airports failed")
        return f"Error comparing airports: {exc}"


def _long_haul_value(estimate: dict[str, Any]) -> str:
    value = estimate.get("long_haul_pct_estimate")
    if value is None:
        return "Unknown"
    return f"{value}% ({estimate.get('confidence', 'unknown')})"


@tool
def get_long_haul_estimate(iata: str) -> dict[str, Any]:
    """Approximate an airport's long-haul / international flight share."""
    try:
        return long_haul_estimate(iata)
    except Exception as exc:
        logger.exception("get_long_haul_estimate failed")
        return {"error": str(exc)}


@tool
def rank_airports_for_expansion(region: str = "US", top_n: int = 5) -> str:
    """Rank airports for terminal/capacity expansion with deterministic scores."""
    try:
        live_scores = _status_delay_scores()
        airports_data = []
        for airport in expansion_candidates(region):
            delay = live_scores.get(
                airport["iata"],
                {
                    "delay_minutes": 0,
                    "status": "No active FAA delay advisory in current feed",
                },
            )
            airports_data.append({**airport, **delay})

        if not airports_data:
            return f"No candidate airports found for region '{region}'."

        ranked = rank_airports(airports_data, top_n=top_n)
        return (
            f"### Ranking for region: {region} (top {len(ranked)})\n\n"
            f"{format_ranking(ranked)}\n\n"
            "Scores use the mandatory weighted formula: Congestion 35%, Growth 30%, "
            "Utilization 25%, Secondary 10%.\n\n"
            "Assumptions & Limitations: FAA delay status is live where available. "
            "Passenger metrics are cached from the FAA 2024 commercial-service workbook "
            "and lag official reporting. Utilization and secondary are transparent proxies."
        )
    except Exception as exc:
        logger.exception("rank_airports_for_expansion failed")
        return f"Ranking failed: {exc}. Suggestion: check cached data and FAA status feed."
