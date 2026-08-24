"""Load labeled long-haul share proxies from CSV."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any


PROXIES_PATH = Path(__file__).resolve().parent / "data" / "long_haul_proxies.csv"


@lru_cache(maxsize=1)
def load_long_haul_proxies() -> dict[str, dict[str, Any]]:
    """Load prototype long-haul share proxies from CSV."""
    proxies: dict[str, dict[str, Any]] = {}
    if not PROXIES_PATH.exists():
        return proxies
    with PROXIES_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            iata = (row.get("iata") or "").strip().upper()
            if not iata:
                continue
            try:
                estimate = float(row.get("estimate") or 0)
            except (TypeError, ValueError):
                continue
            proxies[iata] = {
                "estimate": int(estimate) if estimate.is_integer() else estimate,
                "confidence": (row.get("confidence") or "low").strip().lower(),
                "note": (row.get("note") or "prototype route-mix proxy").strip(),
            }
    return proxies


def long_haul_estimate(iata: str) -> dict[str, Any]:
    """Return an approximate long-haul / international share proxy."""
    normalized = iata.strip().upper()
    proxy = load_long_haul_proxies().get(normalized)

    if not proxy:
        return {
            "iata": normalized,
            "long_haul_share_proxy_pct": None,
            "label": "Estimated long-haul share proxy",
            "definition": "Approximate share of international plus very long domestic flights",
            "confidence": "none",
            "is_proxy": True,
            "source": "data/long_haul_proxies.csv",
            "note": (
                "No specific proxy is available for this airport. This is not calculated "
                "from current route-level schedules. Use a generic 8-15% assumption for "
                "many secondary airports only if the analysis needs a placeholder."
            ),
        }

    return {
        "iata": normalized,
        "long_haul_share_proxy_pct": proxy["estimate"],
        "label": "Estimated long-haul share proxy",
        "definition": "Approximate share of international plus very long domestic flights",
        "confidence": proxy["confidence"],
        "is_proxy": True,
        "source": "data/long_haul_proxies.csv",
        "note": (
            "Estimated long-haul share proxy; not calculated from current route-level "
            "schedules. A production-grade estimate should use BTS T-100, OAG, Cirium, "
            "or similar schedule data."
        ),
    }
