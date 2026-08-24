from data_loader import expansion_candidates, load_enplanements, load_airports
from long_haul import load_long_haul_proxies
from scoring import (
    UNMET_DEMAND_WEIGHTS,
    WEIGHTS,
    load_congestion_baselines,
)


def test_weights_sum_to_one():
    assert round(sum(WEIGHTS.values()), 6) == 1.0
    assert round(sum(UNMET_DEMAND_WEIGHTS.values()), 6) == 1.0


def test_congestion_baselines_are_valid():
    baselines = load_congestion_baselines()
    iatas = list(baselines)

    assert len(iatas) == len(set(iatas))
    for iata, record in baselines.items():
        assert len(iata) == 3
        assert iata.isalpha()
        assert 0 <= record["baseline"] <= 100
        assert record["confidence"] in {"low", "medium", "high"}


def test_long_haul_proxies_are_valid():
    proxies = load_long_haul_proxies()
    iatas = list(proxies)

    assert len(iatas) == len(set(iatas))
    assert proxies["ANC"]["estimate"] == 35
    for iata, record in proxies.items():
        assert len(iata) == 3
        assert 0 <= record["estimate"] <= 100
        assert record["confidence"] in {"low", "medium", "high"}


def test_candidate_data_is_sane():
    for airport in expansion_candidates("US"):
        assert airport["enplanements"] >= 0
        assert int(airport["runway_count"]) >= 1
        assert 0 <= airport["utilization"] <= 100
        assert 0 <= airport["secondary"] <= 100


def test_cached_source_tables_are_sane():
    airports = load_airports()
    enplanements = load_enplanements()

    assert len(airports) > 50
    assert len(enplanements) > 50
    for row in airports:
        assert len(str(row.get("iata") or "")) == 3
        assert int(float(row.get("runway_count") or 0)) >= 0
    for row in enplanements:
        assert int(float(row.get("enplanements") or 0)) >= 0
