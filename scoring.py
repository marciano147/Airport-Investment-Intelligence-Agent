"""Compute layer: deterministic airport expansion scoring."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any


WEIGHTS = {
    "congestion": 0.35,
    "growth": 0.30,
    "utilization": 0.25,
    "secondary": 0.10,
}

UNMET_DEMAND_WEIGHTS = {
    "congestion": 0.40,
    "utilization": 0.35,
    "growth": 0.25,
}

# Absolute passengers-per-runway range. SFO keeps the same utilization score
# whether it is ranked nationally, by state, or compared with one peer.
UTILIZATION_MIN_PER_RUNWAY = 1_000_000
UTILIZATION_MAX_PER_RUNWAY = 8_000_000

DEFAULT_STRUCTURAL_BASELINE = 35.0
DEFAULT_BASELINE_CONFIDENCE = "low"
DEFAULT_BASELINE_NOTE = "default prototype structural congestion proxy"
CONGESTION_BASELINES_PATH = Path(__file__).resolve().parent / "data" / "congestion_baselines.csv"


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


@lru_cache(maxsize=1)
def load_congestion_baselines() -> dict[str, dict[str, Any]]:
    """Load labeled prototype congestion baselines from CSV."""
    baselines: dict[str, dict[str, Any]] = {}
    if not CONGESTION_BASELINES_PATH.exists():
        return baselines
    with CONGESTION_BASELINES_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            iata = (row.get("iata") or "").strip().upper()
            if not iata:
                continue
            baselines[iata] = {
                "baseline": _number_or_default(row.get("baseline"), DEFAULT_STRUCTURAL_BASELINE),
                "confidence": (row.get("confidence") or DEFAULT_BASELINE_CONFIDENCE).strip(),
                "note": (row.get("note") or DEFAULT_BASELINE_NOTE).strip(),
            }
    return baselines


def structural_congestion_baseline(iata: str = "") -> dict[str, Any]:
    """Return the labeled structural congestion proxy for an IATA code."""
    record = load_congestion_baselines().get(str(iata or "").strip().upper())
    if not record:
        return {
            "baseline": DEFAULT_STRUCTURAL_BASELINE,
            "confidence": DEFAULT_BASELINE_CONFIDENCE,
            "note": DEFAULT_BASELINE_NOTE,
        }
    return dict(record)


def utilization_score(enplanements_per_runway: Any) -> float:
    """Score runway pressure on a fixed passengers-per-runway scale."""
    return round(
        normalize(
            _number_or_default(enplanements_per_runway, 0),
            UTILIZATION_MIN_PER_RUNWAY,
            UTILIZATION_MAX_PER_RUNWAY,
        ),
        1,
    )


def get_congestion_score(delay_minutes: Any, iata: str = "") -> float:
    """Score congestion from live FAA delay plus a deterministic hub baseline."""
    return congestion_breakdown(delay_minutes, iata)["congestion_score"]


def congestion_breakdown(delay_minutes: Any, iata: str = "") -> dict[str, Any]:
    """Separate live FAA delay from the structural congestion proxy."""
    normalized_iata = str(iata or "").strip().upper()
    record = structural_congestion_baseline(normalized_iata)
    baseline = float(record["baseline"])
    delay = _number_or_default(delay_minutes, 0)
    live_score = round(normalize(delay, 0, 45), 1) if delay > 0 else None

    if delay <= 0:
        final = baseline
        source = "prototype structural baseline"
        live_program = "none"
        confidence = record["confidence"]
    else:
        blended = (baseline * 0.55) + (live_score * 0.45)
        final = max(baseline, live_score, blended)
        source = "live FAA NAS program blended with structural baseline"
        live_program = f"{delay:g} min"
        confidence = "medium"

    return {
        "iata": normalized_iata,
        "structural_baseline": round(baseline, 1),
        "live_delay_minutes": delay,
        "live_congestion_score": live_score,
        "congestion_score": round(float(final), 1),
        "source": source,
        "confidence": confidence,
        "live_faa_program": live_program,
        "note": record["note"],
    }


def calculate_scores(airport: dict[str, Any]) -> dict[str, float]:
    """Calculate deterministic component and composite scores.

    Expected values:
    - `delay_minutes` or `delay_score`
    - `yoy_growth` as percentage points, for example 8.5 for 8.5%
    - `enplanements_per_runway` for absolute utilization, or `utilization` 0-100
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

    if airport.get("enplanements_per_runway") is not None:
        utilization = utilization_score(airport.get("enplanements_per_runway"))
    else:
        utilization = normalize(_number_or_default(airport.get("utilization"), 50), 0, 100)

    secondary_input = _number_or_default(airport.get("secondary"), 50)
    secondary = normalize(secondary_input, 0, 100)

    # Keep the composite as plain Python math for reviewer reproducibility and
    # to make the LLM/compute-layer separation explicit.
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


def classify_unmet_demand(pressure_score: float) -> str:
    """Label the unmet-demand pressure index without claiming unserved flights."""
    if pressure_score >= 70:
        return "High"
    if pressure_score >= 50:
        return "Moderate"
    return "Limited"


def calculate_unmet_demand_pressure(airport: dict[str, Any]) -> dict[str, Any]:
    """Return a proxy unmet-demand pressure index from congestion, utilization, and growth."""
    scores = calculate_scores(airport)
    pressure = (
        scores["congestion"] * UNMET_DEMAND_WEIGHTS["congestion"]
        + scores["utilization"] * UNMET_DEMAND_WEIGHTS["utilization"]
        + scores["growth"] * UNMET_DEMAND_WEIGHTS["growth"]
    )
    pressure_score = round(pressure, 1)
    return {
        "pressure_score": pressure_score,
        "classification": classify_unmet_demand(pressure_score),
        "drivers": {
            "congestion": scores["congestion"],
            "utilization": scores["utilization"],
            "growth": scores["growth"],
        },
        "is_proxy": True,
        "definition": (
            "Unmet demand pressure index. It is not a count of unserved flights "
            "or true origin-destination booking demand."
        ),
        "weights": dict(UNMET_DEMAND_WEIGHTS),
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
