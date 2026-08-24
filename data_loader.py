"""Public data loading and cache helpers."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

import requests


logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
AIRPORTS_CACHE = DATA_DIR / "airports.csv"
ENPLANEMENTS_CACHE = DATA_DIR / "enplanements.csv"

OURAIRPORTS_US_URL = "https://ourairports.com/countries/US/airports.csv"
FAA_STATUS_URL = "https://nasstatus.faa.gov/api/airport-status-information"
FAA_ENPLANEMENTS_URL = (
    "https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger"
)

NEW_ENGLAND_STATES = {"ME", "NH", "VT", "MA", "RI", "CT"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def refresh_airports_cache() -> list[dict[str, Any]]:
    """Refresh US airport metadata from OurAirports."""
    response = requests.get(OURAIRPORTS_US_URL, timeout=30)
    response.raise_for_status()
    rows = list(csv.DictReader(response.text.splitlines()))
    airports: list[dict[str, Any]] = []

    for row in rows:
        iata = (row.get("iata_code") or "").strip().upper()
        if not iata or len(iata) != 3:
            continue
        if row.get("scheduled_service") not in {"1", "yes", "true", "TRUE"}:
            continue

        state = (row.get("iso_region") or "").replace("US-", "")
        airports.append(
            {
                "iata": iata,
                "name": row.get("name", ""),
                "city": row.get("municipality", ""),
                "state": state,
                "type": row.get("type", ""),
                "latitude": row.get("latitude_deg", ""),
                "longitude": row.get("longitude_deg", ""),
                "scheduled_service": row.get("scheduled_service", ""),
                "source": "OurAirports US airports cache",
            }
        )

    _write_csv(
        AIRPORTS_CACHE,
        airports,
        [
            "iata",
            "name",
            "city",
            "state",
            "type",
            "latitude",
            "longitude",
            "scheduled_service",
            "source",
        ],
    )
    return airports


def load_airports(refresh: bool = False) -> list[dict[str, Any]]:
    if refresh or not AIRPORTS_CACHE.exists():
        try:
            return refresh_airports_cache()
        except Exception:
            logger.exception("Failed to refresh airports cache")
            if not AIRPORTS_CACHE.exists():
                raise
    return _read_csv(AIRPORTS_CACHE)


def load_enplanements() -> list[dict[str, Any]]:
    return _read_csv(ENPLANEMENTS_CACHE)


def airport_by_iata(iata: str) -> dict[str, Any] | None:
    normalized = iata.strip().upper()
    for airport in load_airports():
        if airport.get("iata") == normalized:
            return airport
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


def airports_for_region(region: str) -> list[dict[str, Any]]:
    normalized = region.strip().lower()
    airports = load_airports()

    if normalized in {"new england", "northeast new england"}:
        return [
            airport
            for airport in airports
            if airport.get("state") in NEW_ENGLAND_STATES
        ]

    if len(region.strip()) == 2:
        state = region.strip().upper()
        return [airport for airport in airports if airport.get("state") == state]

    return airports


def expansion_candidates(region: str) -> list[dict[str, Any]]:
    """Return airports enriched with passenger metrics and deterministic proxies."""
    candidates: list[dict[str, Any]] = []
    for airport in airports_for_region(region):
        metrics = metrics_by_iata(airport["iata"])
        if metrics:
            candidates.append({**airport, **metrics})

    if not candidates:
        return []

    max_enplanements = max(candidate["enplanements"] for candidate in candidates) or 1
    for candidate in candidates:
        utilization = candidate["enplanements"] / max_enplanements
        candidate["utilization"] = round(utilization, 4)
        candidate["secondary"] = round(1 - utilization, 4)
        candidate["proxy_notes"] = (
            "Utilization is 2024 enplanements relative to the largest airport in the selected "
            "region; secondary is the inverse size proxy for non-dominant market opportunity."
        )

    return candidates
