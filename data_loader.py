"""Public airport data loading and ranking candidate assembly."""

from __future__ import annotations

import csv
import logging
import re
import time
import xml.etree.ElementTree as ET
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
FAA_STATUS_TTL_SECONDS = 120
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

# Prototype region support. Known regions map to curated major airports; two
# letter state codes are resolved dynamically from the FAA enplanement cache.
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

_NAS_STATUS_CACHE: dict[str, Any] = {"expires_at": 0.0, "data": None}


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

    # OurAirports stores runway rows separately from airport rows. Collapse them
    # once into per-airport runway count and longest-runway metadata for fast
    # scoring later.
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
    """Load cached US scheduled-service airports, refreshing OurAirports if asked."""
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
    """Load the cleaned FAA enplanement cache used for passenger growth."""
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
    """Resolve a user-facing region or state code into candidate IATA codes."""
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


def get_runway_count(iata: str) -> int:
    """Return a cached runway count for an IATA code."""
    airport = airport_by_iata(iata)
    if not airport:
        return 1
    runway_count = int(airport.get("runway_count") or 0)
    return max(runway_count, 1)


def parse_delay_minutes(text: str | None) -> float | None:
    """Extract minutes from FAA strings like `20 minutes` or `1 hour 5 minutes`."""
    if not text:
        return None
    normalized = text.lower().strip()
    hours_match = re.search(r"(\d+(?:\.\d+)?)\s*hour", normalized)
    minutes_match = re.search(r"(\d+(?:\.\d+)?)\s*minute", normalized)
    hours = float(hours_match.group(1)) if hours_match else 0.0
    minutes = float(minutes_match.group(1)) if minutes_match else 0.0
    if hours_match or minutes_match:
        return (hours * 60) + minutes

    bare_number = re.search(r"(\d+(?:\.\d+)?)", normalized)
    if bare_number:
        return float(bare_number.group(1))
    return None


def fetch_nas_status_delays() -> dict[str, dict[str, Any]]:
    """Fetch FAA NAS active programs as airport-level live delay signals."""
    now = time.time()
    cached = _NAS_STATUS_CACHE["data"]
    if cached is not None and now < _NAS_STATUS_CACHE["expires_at"]:
        logger.info("compute_layer source=nas_status_cache status=hit")
        return {iata: dict(status) for iata, status in cached.items()}

    started = time.perf_counter()
    try:
        response = requests.get(FAA_STATUS_URL, timeout=20)
        response.raise_for_status()
        scores = parse_nas_status_xml(response.text)
        _NAS_STATUS_CACHE["data"] = scores
        _NAS_STATUS_CACHE["expires_at"] = now + FAA_STATUS_TTL_SECONDS
        logger.info(
            "compute_layer source=nas_status_live status=ok duration_ms=%.1f rows=%s",
            (time.perf_counter() - started) * 1000,
            len(scores),
        )
        return {iata: dict(status) for iata, status in scores.items()}
    except Exception:
        logger.exception("NAS Status fetch failed")
        if cached is not None:
            logger.info("compute_layer source=nas_status_cache status=stale")
            return {iata: dict(status) for iata, status in cached.items()}
        raise


def parse_nas_status_xml(xml_text: str) -> dict[str, dict[str, Any]]:
    """Parse FAA NAS XML into one strongest active program per airport."""
    root = ET.fromstring(xml_text)
    scores: dict[str, dict[str, Any]] = {}
    update_time = (root.findtext("Update_Time") or "").strip()

    for delay_type in root.findall(".//Delay_type"):
        program = (delay_type.findtext("Name") or "FAA NAS Status").strip()
        _parse_ground_delays(delay_type, program, update_time, scores)
        _parse_arrival_departure_delays(delay_type, program, update_time, scores)
        _parse_ground_stops(delay_type, program, update_time, scores)
        _parse_closures(delay_type, program, update_time, scores)

    return scores


def get_faa_status(iata: str) -> dict[str, Any]:
    """Return live NAS delay status or a clean zero-delay baseline path."""
    normalized = iata.strip().upper()
    active_programs = fetch_nas_status_delays()
    if normalized in active_programs:
        return {
            "iata": normalized,
            **active_programs[normalized],
            "status": "Active FAA NAS traffic management program",
            "note": "Live FAA NAS Status traffic management program.",
        }

    return {
        "iata": normalized,
        "delay_minutes": 0,
        "status": "No active FAA NAS traffic management program",
        "reason": "",
        "program": "",
        "source": FAA_STATUS_URL,
        "note": "No active FAA NAS program; scoring may use deterministic hub baseline.",
    }


@lru_cache(maxsize=256)
def _expansion_candidates_cached(region: str = "US") -> tuple[tuple[tuple[str, Any], ...], ...]:
    """Assemble airport facts, passenger metrics, and deterministic proxy inputs."""
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
    """Score strategic context from route mix, airport scale, and runway pressure."""
    enplanements = float(candidate.get("enplanements") or 0)
    enplanements_per_runway = float(candidate.get("enplanements_per_runway") or 0)
    estimate = long_haul_estimate(str(candidate.get("iata", ""))).get(
        "long_haul_pct_estimate"
    )
    long_haul_pct = float(estimate) if estimate is not None else 12.0

    # Secondary is a strategic terminal-value proxy. Long-haul share dominates,
    # with airport scale and runway pressure keeping large constrained hubs from
    # being treated like small route-mix outliers.
    long_haul_score = min(40 + (long_haul_pct * 0.95), 88)
    scale_score = 45 + (_normalize_value(enplanements, 2_000_000, 45_000_000) * 0.35)
    runway_pressure_score = 40 + (
        _normalize_value(enplanements_per_runway, 2_000_000, 10_000_000) * 0.35
    )
    score = (
        long_haul_score * 0.60
        + scale_score * 0.25
        + runway_pressure_score * 0.15
    )
    return round(max(35.0, min(90.0, score)), 1)


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


def _parse_ground_delays(
    delay_type: ET.Element,
    program: str,
    update_time: str,
    scores: dict[str, dict[str, Any]],
) -> None:
    for ground_delay in delay_type.findall("./Ground_Delay_List/Ground_Delay"):
        iata = (ground_delay.findtext("ARPT") or "").strip().upper()
        if not iata:
            continue
        delay = (
            parse_delay_minutes(ground_delay.findtext("Avg"))
            or parse_delay_minutes(ground_delay.findtext("Max"))
            or 30.0
        )
        _record_nas_delay(
            scores,
            iata,
            delay,
            program,
            ground_delay.findtext("Reason"),
            update_time,
            "avg_delay_minutes",
        )


def _parse_arrival_departure_delays(
    delay_type: ET.Element,
    program: str,
    update_time: str,
    scores: dict[str, dict[str, Any]],
) -> None:
    for delay in delay_type.findall("./Arrival_Departure_Delay_List/Delay"):
        iata = (delay.findtext("ARPT") or "").strip().upper()
        if not iata:
            continue
        reason = delay.findtext("Reason")
        for arrival_departure in delay.findall("./Arrival_Departure"):
            min_delay = parse_delay_minutes(arrival_departure.findtext("Min"))
            max_delay = parse_delay_minutes(arrival_departure.findtext("Max"))
            minutes = _midpoint_or_known_delay(min_delay, max_delay) or 30.0
            delay_kind = arrival_departure.attrib.get("Type", "Arrival/Departure")
            _record_nas_delay(
                scores,
                iata,
                minutes,
                program,
                reason,
                update_time,
                f"{delay_kind.lower()}_delay_minutes",
            )


def _parse_ground_stops(
    delay_type: ET.Element,
    program: str,
    update_time: str,
    scores: dict[str, dict[str, Any]],
) -> None:
    for ground_stop in delay_type.findall("./Ground_Stop_List/Ground_Stop"):
        iata = (ground_stop.findtext("ARPT") or "").strip().upper()
        if iata:
            _record_nas_delay(
                scores,
                iata,
                60.0,
                program,
                ground_stop.findtext("Reason"),
                update_time,
                "ground_stop_proxy_minutes",
            )


def _parse_closures(
    delay_type: ET.Element,
    program: str,
    update_time: str,
    scores: dict[str, dict[str, Any]],
) -> None:
    for closure in delay_type.findall("./Airport_Closure_List/Airport"):
        iata = (closure.findtext("ARPT") or "").strip().upper()
        if iata:
            _record_nas_delay(
                scores,
                iata,
                60.0,
                program,
                closure.findtext("Reason"),
                update_time,
                "closure_proxy_minutes",
            )


def _record_nas_delay(
    scores: dict[str, dict[str, Any]],
    iata: str,
    delay_minutes: float,
    program: str,
    reason: str | None,
    update_time: str,
    metric: str,
) -> None:
    existing_delay = float(scores.get(iata, {}).get("delay_minutes", -1))
    if delay_minutes < existing_delay:
        return
    scores[iata] = {
        "delay_minutes": round(delay_minutes, 1),
        "program": program,
        "reason": (reason or "").strip(),
        "source": FAA_STATUS_URL,
        "source_detail": metric,
        "updated_at": update_time,
    }


def _midpoint_or_known_delay(
    min_delay: float | None,
    max_delay: float | None,
) -> float | None:
    if min_delay is not None and max_delay is not None:
        return (min_delay + max_delay) / 2
    return max_delay if max_delay is not None else min_delay
