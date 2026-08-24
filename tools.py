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
from scoring import format_ranking, rank_airports


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
