"""Compute layer: deterministic airport expansion scoring."""

from __future__ import annotations

from typing import Any


WEIGHTS = {
    "congestion": 0.35,
    "growth": 0.30,
    "utilization": 0.25,
    "secondary": 0.10,
}

BASELINE_CONGESTION = {
    "ATL": 75,
    "ORD": 78,
    "LAX": 72,
    "DFW": 70,
    "JFK": 80,
    "EWR": 82,
    "LGA": 85,
    "SFO": 70,
    "BOS": 68,
    "MIA": 65,
    "CLT": 60,
    "DEN": 55,
    "PHX": 50,
    "IAH": 58,
    "SEA": 55,
    "MSP": 52,
    "DTW": 55,
    "PHL": 62,
    "BWI": 45,
    "MDW": 50,
    "IAD": 58,
    "FLL": 48,
    "MCO": 45,
    "LAS": 50,
    "SAN": 40,
    "SNA": 35,
    "PDX": 38,
    "AUS": 42,
    "BNA": 40,
    "DAL": 45,
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


def _number_or_default(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_congestion_score(delay_minutes: Any, iata: str = "") -> float:
    """Score congestion from live FAA delay plus a deterministic hub baseline."""
    baseline = BASELINE_CONGESTION.get(iata.strip().upper(), 35)
    delay = _number_or_default(delay_minutes, 0)
    if delay <= 0:
        return float(baseline)

    live_score = normalize(delay, 0, 45)
    blended = (baseline * 0.55) + (live_score * 0.45)
    return max(float(baseline), live_score, blended)


def calculate_scores(airport: dict[str, Any]) -> dict[str, float]:
    """Calculate deterministic component and composite scores.

    Expected values:
    - `delay_minutes` or `delay_score`
    - `yoy_growth` as percentage points, for example 8.5 for 8.5%
    - `utilization` on a 0-100 scale
    - `secondary` on a 0-100 scale
    """
    iata = str(airport.get("iata", "") or "")
    delay_score = airport.get("delay_score")
    if delay_score is not None:
        congestion = normalize(delay_score, 0, 100)
    else:
        congestion = get_congestion_score(airport.get("delay_minutes", 0), iata)

    growth_pct = _number_or_default(airport.get("yoy_growth"), 3.0)
    growth = normalize(growth_pct, -5, 12)

    util = _number_or_default(airport.get("utilization"), 65)
    utilization = normalize(util, 40, 95)

    secondary_input = _number_or_default(airport.get("secondary"), 50)
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
