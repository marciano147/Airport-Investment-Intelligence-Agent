"""Compute layer: deterministic airport expansion scoring."""

from __future__ import annotations

from typing import Any


WEIGHTS = {
    "congestion": 0.35,
    "growth": 0.30,
    "utilization": 0.25,
    "secondary": 0.10,
}


def normalize(value: float, min_val: float = 0, max_val: float = 100) -> float:
    """Clamp and scale a value to 0-100."""
    if max_val == min_val:
        return 50.0

    try:
        number = float(value)
    except (TypeError, ValueError):
        number = min_val

    scaled = (number - min_val) / (max_val - min_val) * 100
    return max(0.0, min(100.0, scaled))


def calculate_scores(airport: dict[str, Any]) -> dict[str, float]:
    """Calculate deterministic component and composite scores.

    Expected values:
    - `delay_minutes` or `delay_score`
    - `yoy_growth` as percentage points, for example 8.5 for 8.5%
    - `utilization` on a 0-100 scale
    - `secondary` on a 0-100 scale
    """
    delay = airport.get("delay_score")
    if delay is None:
        delay = airport.get("delay_minutes", 15)
    congestion = normalize(delay, 0, 60)

    growth_pct = airport.get("yoy_growth", 3.0)
    growth = normalize(growth_pct, -5, 20)

    util = airport.get("utilization", 65)
    utilization = normalize(util, 40, 95)

    secondary_input = airport.get("secondary", 50)
    secondary = normalize(secondary_input, 0, 100)

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


def rank_airports(
    airports: list[dict[str, Any]], top_n: int = 5
) -> list[dict[str, Any]]:
    """Rank airports by composite score and return top_n with full breakdown."""
    scored = []
    for airport in airports:
        scores = calculate_scores(airport)
        scored.append({**airport, **scores})

    ranked = sorted(scored, key=lambda item: item["composite"], reverse=True)
    return ranked[:top_n]


def format_ranking(ranked: list[dict[str, Any]]) -> str:
    """Format a markdown table with the full score breakdown."""
    lines = [
        "| Rank | IATA | Airport | Composite | Congestion | Growth | Utilization | Secondary |",
        "|---:|---|---|---:|---:|---:|---:|---:|",
    ]

    for idx, airport in enumerate(ranked, start=1):
        lines.append(
            "| {rank} | {iata} | {name} | {composite:.1f} | {congestion:.1f} | "
            "{growth:.1f} | {utilization:.1f} | {secondary:.1f} |".format(
                rank=idx,
                iata=airport.get("iata", "N/A"),
                name=airport.get("name", airport.get("airport_name", "N/A")),
                composite=airport["composite"],
                congestion=airport["congestion"],
                growth=airport["growth"],
                utilization=airport["utilization"],
                secondary=airport["secondary"],
            )
        )

    return "\n".join(lines)
