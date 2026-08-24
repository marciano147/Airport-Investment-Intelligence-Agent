"""Public airport data loading and ranking candidate assembly."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

import requests


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


def load_airports(refresh: bool = False) -> list[dict[str, Any]]:
    if refresh:
        AIRPORTS_CACHE.unlink(missing_ok=True)
        RUNWAYS_CACHE.unlink(missing_ok=True)
    download_ourairports()
    return _read_csv(AIRPORTS_CACHE)


def load_enplanements() -> list[dict[str, Any]]:
    return _read_csv(ENPLANEMENTS_CACHE)


def airport_by_iata(iata: str) -> dict[str, Any] | None:
    normalized = iata.strip().upper()
    for airport in load_airports():
        if airport.get("iata") == normalized:
            return {
                **airport,
                "runway_count": int(float(airport.get("runway_count") or 0)),
                "longest_runway_ft": int(
                    float(airport.get("longest_runway_ft") or 0)
                ),
            }
    return None


def metrics_by_iata(iata: str) -> dict[str, Any] | None:
    normalized = iata.strip().upper()
    for row in load_enplanements():
        if row.get("iata") == normalized:
            return {
                **row,
                "year": int(float(row.get("year", 0) or 0)),
                "enplanements": int(float(row.get("enplanements", 0) or 0)),
                "prior_year_enplanements": int(
                    float(row.get("prior_year_enplanements", 0) or 0)
                ),
                "yoy_growth": float(row.get("yoy_growth", 0) or 0),
            }
    return None


def get_airports_for_region(region: str = "US") -> list[str]:
    """Return major IATA codes for a requested prototype region."""
    normalized = region.lower().strip()
    if normalized in REGION_MAP:
        return REGION_MAP[normalized]

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
        return [row["iata"] for row in ranked[:20]]

    return MAJOR_US_AIRPORTS


def expansion_candidates(region: str = "US") -> list[dict[str, Any]]:
    """Return ranked-scope airports enriched with public metrics and proxies."""
    candidates: list[dict[str, Any]] = []
    for iata in get_airports_for_region(region):
        airport = airport_by_iata(iata)
        metrics = metrics_by_iata(iata)
        if airport and metrics:
            candidates.append({**airport, **metrics})

    if not candidates:
        return []

    max_enplanements_per_runway = max(
        _enplanements_per_runway(candidate) for candidate in candidates
    ) or 1
    max_enplanements = max(candidate["enplanements"] for candidate in candidates) or 1

    for candidate in candidates:
        per_runway = _enplanements_per_runway(candidate)
        utilization = (per_runway / max_enplanements_per_runway) * 100
        secondary = (1 - (candidate["enplanements"] / max_enplanements)) * 100
        candidate["enplanements_per_runway"] = round(per_runway, 1)
        candidate["utilization"] = round(utilization, 1)
        candidate["secondary"] = round(secondary, 1)
        candidate["proxy_notes"] = (
            "Utilization uses 2024 enplanements per runway relative to the selected "
            "region. Secondary is an inverse size proxy for non-dominant market opportunity."
        )

    return candidates


def _enplanements_per_runway(candidate: dict[str, Any]) -> float:
    runway_count = int(candidate.get("runway_count") or 0)
    if runway_count <= 0:
        runway_count = 1
    return float(candidate["enplanements"]) / runway_count
