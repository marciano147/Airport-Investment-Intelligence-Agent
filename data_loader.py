"""Public airport data loading and ranking candidate assembly."""

from __future__ import annotations

import csv
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import requests

from long_haul import long_haul_estimate


logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
AIRPORTS_CACHE = DATA_DIR / "airports.csv"
RUNWAYS_CACHE = DATA_DIR / "runways.csv"
ENPLANEMENTS_CACHE = DATA_DIR / "enplanements.csv"

OURAIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
RUNWAYS_URL = "https://davidmegginson.github.io/ourairports-data/runways.csv"
FAA_STATUS_URL = "https://nasstatus.faa.gov/api/airport-status-information"
FAA_ENPLANEMENTS_URL = (
    "https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger"
)

MAJOR_US_AIRPORTS = [
    "ATL",
    "LAX",
    "ORD",
    "DFW",
    "DEN",
    "JFK",
    "SFO",
    "SEA",
    "LAS",
    "MCO",
    "CLT",
    "EWR",
    "PHX",
    "IAH",
    "BOS",
    "MSP",
    "DTW",
    "PHL",
    "LGA",
    "BWI",
]

REGION_MAP = {
    "new england": ["BOS", "MHT", "PVD", "BDL", "PWM", "BTV"],
    "northeast": ["BOS", "JFK", "LGA", "EWR", "PHL", "BDL", "PVD"],
    "california": ["LAX", "SFO", "SAN", "SJC", "OAK", "SNA", "SMF"],
    "texas": ["DFW", "IAH", "AUS", "SAT", "DAL", "HOU"],
    "florida": ["MCO", "MIA", "FLL", "TPA", "JAX"],
    "midwest": ["ORD", "MDW", "DTW", "MSP", "STL", "CVG", "IND"],
    "us": MAJOR_US_AIRPORTS,
    "usa": MAJOR_US_AIRPORTS,
    "all": MAJOR_US_AIRPORTS,
    "nationwide": MAJOR_US_AIRPORTS,
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def download_ourairports() -> None:
    """Download OurAirports airport and runway caches if they are missing."""
    if AIRPORTS_CACHE.exists() and RUNWAYS_CACHE.exists():
        return

    airport_response = requests.get(OURAIRPORTS_URL, timeout=30)
    airport_response.raise_for_status()
    runway_response = requests.get(RUNWAYS_URL, timeout=30)
    runway_response.raise_for_status()

    raw_airports = list(csv.DictReader(airport_response.text.splitlines()))
    raw_runways = list(csv.DictReader(runway_response.text.splitlines()))

    runway_stats: dict[str, dict[str, int]] = {}
    for runway in raw_runways:
        ident = runway.get("airport_ident", "")
        if not ident:
            continue
        length = int(float(runway.get("length_ft") or 0))
        stats = runway_stats.setdefault(
            ident, {"runway_count": 0, "longest_runway_ft": 0}
        )
        stats["runway_count"] += 1
        stats["longest_runway_ft"] = max(stats["longest_runway_ft"], length)

    airports: list[dict[str, Any]] = []
    runway_rows: list[dict[str, Any]] = []
    for row in raw_airports:
        iata = (row.get("iata_code") or "").strip().upper()
        if row.get("iso_country") != "US" or not iata or len(iata) != 3:
            continue
        if str(row.get("scheduled_service", "")).lower() not in {"1", "yes", "true"}:
            continue

        stats = runway_stats.get(
            row.get("ident", ""), {"runway_count": 0, "longest_runway_ft": 0}
        )
        airport = {
            "iata": iata,
            "ident": row.get("ident", ""),
            "name": row.get("name", ""),
            "city": row.get("municipality", ""),
            "state": (row.get("iso_region") or "").replace("US-", ""),
            "type": row.get("type", ""),
            "latitude": row.get("latitude_deg", ""),
            "longitude": row.get("longitude_deg", ""),
            "elevation_ft": row.get("elevation_ft", ""),
            "scheduled_service": row.get("scheduled_service", ""),
            "runway_count": stats["runway_count"],
            "longest_runway_ft": stats["longest_runway_ft"],
            "source": "OurAirports airports and runways cache",
        }
        airports.append(airport)
        runway_rows.append(
            {
                "iata": iata,
                "ident": row.get("ident", ""),
                "runway_count": stats["runway_count"],
                "longest_runway_ft": stats["longest_runway_ft"],
                "source": "OurAirports airports and runways cache",
            }
        )

    airport_fields = [
        "iata",
        "ident",
        "name",
        "city",
        "state",
        "type",
        "latitude",
        "longitude",
        "elevation_ft",
        "scheduled_service",
        "runway_count",
        "longest_runway_ft",
        "source",
    ]
    runway_fields = ["iata", "ident", "runway_count", "longest_runway_ft", "source"]
    _write_csv(AIRPORTS_CACHE, sorted(airports, key=lambda item: item["iata"]), airport_fields)
    _write_csv(RUNWAYS_CACHE, sorted(runway_rows, key=lambda item: item["iata"]), runway_fields)


@lru_cache(maxsize=1)
def _load_airports_cached() -> tuple[dict[str, str], ...]:
    download_ourairports()
    return tuple(_read_csv(AIRPORTS_CACHE))


def load_airports(refresh: bool = False) -> list[dict[str, Any]]:
    if refresh:
        AIRPORTS_CACHE.unlink(missing_ok=True)
        RUNWAYS_CACHE.unlink(missing_ok=True)
        _load_airports_cached.cache_clear()
        _airport_by_iata_cached.cache_clear()
        _airports_for_region_cached.cache_clear()
        _expansion_candidates_cached.cache_clear()
    return [dict(row) for row in _load_airports_cached()]


@lru_cache(maxsize=1)
def _load_enplanements_cached() -> tuple[dict[str, str], ...]:
    return tuple(_read_csv(ENPLANEMENTS_CACHE))


def load_enplanements() -> list[dict[str, Any]]:
    return [dict(row) for row in _load_enplanements_cached()]


@lru_cache(maxsize=1024)
def _airport_by_iata_cached(iata: str) -> tuple[tuple[str, Any], ...] | None:
    normalized = iata.strip().upper()
    for airport in load_airports():
        if airport.get("iata") == normalized:
            hydrated = {
                **airport,
                "runway_count": int(float(airport.get("runway_count") or 0)),
                "longest_runway_ft": int(
                    float(airport.get("longest_runway_ft") or 0)
                ),
            }
            return tuple(hydrated.items())
    return None


@lru_cache(maxsize=1024)
def _metrics_by_iata_cached(iata: str) -> tuple[tuple[str, Any], ...] | None:
    normalized = iata.strip().upper()
    for row in load_enplanements():
        if row.get("iata") == normalized:
            hydrated = {
                **row,
                "year": int(float(row.get("year", 0) or 0)),
                "enplanements": int(float(row.get("enplanements", 0) or 0)),
                "prior_year_enplanements": int(
                    float(row.get("prior_year_enplanements", 0) or 0)
                ),
                "yoy_growth": float(row.get("yoy_growth", 0) or 0),
            }
            return tuple(hydrated.items())
    return None


def airport_by_iata(iata: str) -> dict[str, Any] | None:
    cached = _airport_by_iata_cached(iata)
    return dict(cached) if cached else None


def metrics_by_iata(iata: str) -> dict[str, Any] | None:
    cached = _metrics_by_iata_cached(iata)
    return dict(cached) if cached else None


@lru_cache(maxsize=256)
def _airports_for_region_cached(region: str = "US") -> tuple[str, ...]:
    normalized = region.lower().strip()
    if normalized in REGION_MAP:
        return tuple(REGION_MAP[normalized])

    if len(normalized) == 2:
        state = normalized.upper()
        state_airports = [
            row
            for row in load_enplanements()
            if row.get("state", "").upper() == state
        ]
        ranked = sorted(
            state_airports,
            key=lambda row: int(float(row.get("enplanements") or 0)),
            reverse=True,
        )
        return tuple(row["iata"] for row in ranked[:20])

    return tuple(MAJOR_US_AIRPORTS)


def get_airports_for_region(region: str = "US") -> list[str]:
    """Return major IATA codes for a requested prototype region."""
    return list(_airports_for_region_cached(region))


@lru_cache(maxsize=256)
def _expansion_candidates_cached(region: str = "US") -> tuple[tuple[tuple[str, Any], ...], ...]:
    candidates: list[dict[str, Any]] = []
    for iata in get_airports_for_region(region):
        airport = airport_by_iata(iata)
        metrics = metrics_by_iata(iata)
        if airport and metrics:
            candidates.append({**airport, **metrics})

    if not candidates:
        return tuple()

    max_enplanements_per_runway = max(
        _enplanements_per_runway(candidate) for candidate in candidates
    ) or 1
    for candidate in candidates:
        per_runway = _enplanements_per_runway(candidate)
        candidate["enplanements_per_runway"] = round(per_runway, 1)
        candidate["utilization"] = utilization_proxy_score(
            per_runway, max_enplanements_per_runway
        )
        candidate["secondary"] = secondary_proxy_score(candidate)
        candidate["proxy_notes"] = (
            "Utilization uses 2024 enplanements per runway relative to the selected region "
            "with a cap below full saturation. Secondary combines airport scale, long-haul "
            "proxy, and runway pressure."
        )

    return tuple(tuple(candidate.items()) for candidate in candidates)


def expansion_candidates(region: str = "US") -> list[dict[str, Any]]:
    """Return ranked-scope airports enriched with public metrics and proxies."""
    return [dict(candidate) for candidate in _expansion_candidates_cached(region)]


def utilization_proxy_score(
    enplanements_per_runway: float,
    max_enplanements_per_runway: float,
) -> float:
    """Score runway pressure without letting the top peer saturate at 100."""
    if max_enplanements_per_runway <= 0:
        return 65.0
    ratio = max(0.0, min(1.0, enplanements_per_runway / max_enplanements_per_runway))
    return round(35 + (ratio * 57), 1)


def secondary_proxy_score(candidate: dict[str, Any]) -> float:
    """Score strategic context from scale, route mix, and runway pressure."""
    enplanements = float(candidate.get("enplanements") or 0)
    enplanements_per_runway = float(candidate.get("enplanements_per_runway") or 0)
    estimate = long_haul_estimate(str(candidate.get("iata", ""))).get(
        "long_haul_pct_estimate"
    )
    long_haul_pct = float(estimate) if estimate is not None else 12.0

    long_haul_score = _normalize_value(long_haul_pct, 5, 45)
    scale_score = _normalize_value(enplanements, 2_000_000, 45_000_000)
    runway_pressure_score = _normalize_value(
        enplanements_per_runway, 2_000_000, 10_000_000
    )
    score = (
        long_haul_score * 0.45
        + scale_score * 0.35
        + runway_pressure_score * 0.20
    )
    return round(max(35.0, min(95.0, score)), 1)


def cache_stats() -> dict[str, Any]:
    """Expose compute-layer cache stats for debugging and interviews."""
    return {
        "load_airports": _load_airports_cached.cache_info()._asdict(),
        "load_enplanements": _load_enplanements_cached.cache_info()._asdict(),
        "airport_by_iata": _airport_by_iata_cached.cache_info()._asdict(),
        "metrics_by_iata": _metrics_by_iata_cached.cache_info()._asdict(),
        "get_airports_for_region": _airports_for_region_cached.cache_info()._asdict(),
        "expansion_candidates": _expansion_candidates_cached.cache_info()._asdict(),
    }


def clear_caches() -> None:
    """Clear all compute-layer caches."""
    _load_airports_cached.cache_clear()
    _load_enplanements_cached.cache_clear()
    _airport_by_iata_cached.cache_clear()
    _metrics_by_iata_cached.cache_clear()
    _airports_for_region_cached.cache_clear()
    _expansion_candidates_cached.cache_clear()


def _enplanements_per_runway(candidate: dict[str, Any]) -> float:
    runway_count = int(candidate.get("runway_count") or 0)
    if runway_count <= 0:
        runway_count = 1
    return float(candidate["enplanements"]) / runway_count


def _normalize_value(value: float, min_val: float, max_val: float) -> float:
    if max_val == min_val:
        return 50.0
    scaled = (value - min_val) / (max_val - min_val) * 100
    return max(0.0, min(100.0, scaled))
