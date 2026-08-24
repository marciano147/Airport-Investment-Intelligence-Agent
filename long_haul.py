"""Transparent long-haul share proxy data."""

from __future__ import annotations

from typing import Any


LONG_HAUL_PROXY: dict[str, dict[str, Any]] = {
    "ANC": {"estimate": 35, "confidence": "medium"},
    "LAX": {"estimate": 28, "confidence": "medium"},
    "SFO": {"estimate": 32, "confidence": "medium"},
    "JFK": {"estimate": 45, "confidence": "medium"},
    "EWR": {"estimate": 38, "confidence": "medium"},
    "ORD": {"estimate": 22, "confidence": "low"},
    "ATL": {"estimate": 18, "confidence": "low"},
    "DFW": {"estimate": 20, "confidence": "low"},
    "MIA": {"estimate": 48, "confidence": "medium"},
    "SEA": {"estimate": 25, "confidence": "low"},
    "BOS": {"estimate": 22, "confidence": "low"},
    "IAD": {"estimate": 40, "confidence": "medium"},
    "IAH": {"estimate": 25, "confidence": "low"},
    "SNA": {"estimate": 5, "confidence": "low"},
    "SAN": {"estimate": 8, "confidence": "low"},
    "PDX": {"estimate": 12, "confidence": "low"},
    "HNL": {"estimate": 55, "confidence": "medium"},
    "MCO": {"estimate": 15, "confidence": "low"},
    "LAS": {"estimate": 10, "confidence": "low"},
    "PHX": {"estimate": 12, "confidence": "low"},
    "DEN": {"estimate": 15, "confidence": "low"},
    "CLT": {"estimate": 14, "confidence": "low"},
    "MSP": {"estimate": 16, "confidence": "low"},
    "DTW": {"estimate": 18, "confidence": "low"},
    "PHL": {"estimate": 20, "confidence": "low"},
    "LGA": {"estimate": 8, "confidence": "low"},
    "BWI": {"estimate": 10, "confidence": "low"},
}


def long_haul_estimate(iata: str) -> dict[str, Any]:
    """Return an approximate long-haul / international share proxy."""
    normalized = iata.strip().upper()
    proxy = LONG_HAUL_PROXY.get(normalized)

    if not proxy:
        return {
            "iata": normalized,
            "long_haul_pct_estimate": None,
            "definition": "Approximate share of international plus very long domestic flights",
            "confidence": "none",
            "note": (
                "No specific proxy is available for this airport. Long-haul share "
                "requires route-level schedule data; use a generic 8-15% assumption "
                "for many secondary airports only if the analysis needs a placeholder."
            ),
        }

    return {
        "iata": normalized,
        "long_haul_pct_estimate": proxy["estimate"],
        "definition": "Approximate share of international plus very long domestic flights",
        "confidence": proxy["confidence"],
        "note": (
            "This is a static proxy based on known airport traffic patterns, not live "
            "schedule data. A production-grade estimate should use route-level BTS T-100, "
            "OAG, Cirium, or similar schedule data."
        ),
    }
