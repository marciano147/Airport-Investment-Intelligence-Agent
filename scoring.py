"""Deterministic airport expansion scoring."""

from __future__ import annotations

from typing import Any


WEIGHTS = {
    "congestion": 0.35,
    "growth": 0.30,
    "utilization": 0.25,
    "secondary": 0.10,
}


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def normalize(value: Any, *, mode: str = "percent") -> float:
    """Normalize values to 0-100.

    Ratios between 0 and 1 are treated as percentages. Values already between
    1 and 100 are treated as scores. Negative values score 0.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0

    if mode == "growth":
        # -5% -> 0, 0% -> 25, 10% -> 75, 15%+ -> 100.
        return clamp(((number + 0.05) / 0.20) * 100)

    if 0 <= number <= 1:
        return clamp(number * 100)
    return clamp(number)


def calculate_scores(airport_data: dict[str, Any]) -> dict[str, float]:
    """Return weighted deterministic scores for one airport."""
    congestion = normalize(airport_data.get("delay_score", 0))
    growth = (
        0.0
        if "yoy_growth" not in airport_data
        else normalize(airport_data.get("yoy_growth"), mode="growth")
    )
    utilization = normalize(airport_data.get("utilization", 0))
    secondary = normalize(airport_data.get("secondary", 0))

    composite = (
        congestion * WEIGHTS["congestion"]
        + growth * WEIGHTS["growth"]
        + utilization * WEIGHTS["utilization"]
        + secondary * WEIGHTS["secondary"]
    )

    return {
        "composite": round(composite, 1),
        "congestion": round(congestion, 1),
        "growth": round(growth, 1),
        "utilization": round(utilization, 1),
        "secondary": round(secondary, 1),
    }


def rank_airports(airports: list[dict[str, Any]], top_n: int = 5) -> list[dict[str, Any]]:
    """Score and rank airports by expansion potential."""
    scored = []
    for airport in airports:
        scores = calculate_scores(airport)
        scored.append({**airport, **scores})

    return sorted(scored, key=lambda item: item["composite"], reverse=True)[:top_n]
