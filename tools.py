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
from scoring import rank_airports


logger = logging.getLogger(__name__)


def _status_delay_scores() -> dict[str, dict[str, Any]]:
    response = requests.get(FAA_STATUS_URL, timeout=20)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    scores: dict[str, dict[str, Any]] = {}

    for delay_type in root.findall(".//Delay_type"):
        name = delay_type.findtext("Name", default="FAA status").strip()
        for airport in delay_type.findall(".//Airport") + delay_type.findall(".//Ground_Delay"):
            iata = (airport.findtext("ARPT") or "").strip().upper()
            if not iata:
                continue
            severity = 100 if "Closure" in name else 80 if "Ground" in name else 60
            scores[iata] = {
                "delay_score": max(severity, scores.get(iata, {}).get("delay_score", 0)),
                "status": name,
                "reason": airport.findtext("Reason", default="FAA delay/advisory").strip(),
            }

    return scores


@tool
def get_airport_info(iata: str) -> dict[str, Any]:
    """Get basic airport information for an IATA code."""
    try:
        airport = airport_by_iata(iata)
        if not airport:
            return {"error": f"No cached airport found for IATA code {iata.upper()}."}
        return airport
    except Exception as exc:
        logger.exception("get_airport_info failed")
        return {"error": str(exc), "suggestion": "Check the IATA code or refresh the airport cache."}


@tool
def get_congestion(iata: str) -> dict[str, Any]:
    """Get live FAA delay status for an IATA code."""
    try:
        normalized = iata.strip().upper()
        live_scores = _status_delay_scores()
        if normalized in live_scores:
            return {"iata": normalized, **live_scores[normalized], "source": FAA_STATUS_URL}
        return {
            "iata": normalized,
            "delay_score": 10,
            "status": "No active FAA delay advisory in current feed",
            "source": FAA_STATUS_URL,
        }
    except Exception as exc:
        logger.exception("get_congestion failed")
        return {
            "iata": iata.strip().upper(),
            "delay_score": 0,
            "error": str(exc),
            "suggestion": "FAA status feed may be unavailable. Retry or inspect logs.",
        }


@tool
def get_passenger_metrics(iata: str) -> dict[str, Any]:
    """Get cached FAA passenger/enplanement metrics for an IATA code."""
    try:
        metrics = metrics_by_iata(iata)
        if not metrics:
            return {"error": f"No cached passenger metrics found for IATA code {iata.upper()}."}
        return metrics
    except Exception as exc:
        logger.exception("get_passenger_metrics failed")
        return {"error": str(exc), "suggestion": "Check cached enplanement data."}


@tool
def rank_airports_for_expansion(region: str = "New England", top_n: int = 5) -> str:
    """Rank airports for terminal/capacity expansion with deterministic scores."""
    try:
        live_scores = _status_delay_scores()
        candidates = []
        for airport in expansion_candidates(region):
            delay = live_scores.get(
                airport["iata"],
                {"delay_score": 10, "status": "No active FAA delay advisory in current feed"},
            )
            candidates.append({**airport, **delay})

        if not candidates:
            return f"No candidate airports found for region '{region}'."

        ranked = rank_airports(candidates, top_n=top_n)
        lines = [
            f"Top {len(ranked)} {region} airports for expansion potential",
            "",
            "| Rank | IATA | Airport | Composite | Congestion | Growth | Utilization | Secondary |",
            "|---:|---|---|---:|---:|---:|---:|---:|",
        ]

        for idx, airport in enumerate(ranked, start=1):
            lines.append(
                "| {rank} | {iata} | {name} | {composite:.1f} | {congestion:.1f} | "
                "{growth:.1f} | {utilization:.1f} | {secondary:.1f} |".format(
                    rank=idx,
                    iata=airport["iata"],
                    name=airport["name"],
                    composite=airport["composite"],
                    congestion=airport["congestion"],
                    growth=airport["growth"],
                    utilization=airport["utilization"],
                    secondary=airport["secondary"],
                )
            )

        lines.extend(
            [
                "",
                "Assumptions: FAA delay status is live where available; passenger metrics are "
                "cached from the FAA 2024 commercial-service workbook and lag official "
                "reporting; utilization and secondary are transparent proxies, not physical "
                "capacity measurements.",
            ]
        )
        return "\n".join(lines)
    except Exception as exc:
        logger.exception("rank_airports_for_expansion failed")
        return f"Ranking failed: {exc}. Suggestion: check cached data and FAA status feed."
