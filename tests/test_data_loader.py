from data_loader import (
    airport_by_iata,
    expansion_candidates,
    get_airports_for_region,
    metrics_by_iata,
)


def test_metrics_are_loaded_from_faa_cache_as_percentage_points():
    metrics = metrics_by_iata("BOS")

    assert metrics["year"] == 2024
    assert metrics["enplanements"] == 21090721
    assert metrics["prior_year_enplanements"] == 19962678
    assert metrics["yoy_growth"] == 5.65
    assert metrics["source"] == "FAA 2024 commercial service enplanements workbook"


def test_airport_info_includes_runway_metadata():
    airport = airport_by_iata("BOS")

    assert airport["iata"] == "BOS"
    assert airport["runway_count"] >= 1
    assert airport["longest_runway_ft"] > 0


def test_airport_info_accepts_lowercase_and_unknown_iata():
    airport = airport_by_iata(" bos ")

    assert airport["iata"] == "BOS"
    assert airport_by_iata("ZZZ") is None


def test_region_mapping_defaults_to_major_us_airports():
    assert get_airports_for_region("US")[:3] == ["ATL", "LAX", "ORD"]
    assert get_airports_for_region("unknown-region")[:3] == ["ATL", "LAX", "ORD"]
    assert "LAX" in get_airports_for_region("California")
    assert "BOS" in get_airports_for_region("New England")


def test_state_code_region_uses_faa_cache():
    california = get_airports_for_region("CA")

    assert california[0] == "LAX"
    assert "SFO" in california


def test_empty_state_region_has_no_candidates():
    assert get_airports_for_region("ZZ") == []
    assert expansion_candidates("ZZ") == []


def test_expansion_candidates_add_deterministic_proxies():
    candidates = expansion_candidates("New England")
    bos = next(candidate for candidate in candidates if candidate["iata"] == "BOS")
    pvd = next(candidate for candidate in candidates if candidate["iata"] == "PVD")

    assert bos["enplanements_per_runway"] > pvd["enplanements_per_runway"]
    assert 0 <= bos["utilization"] <= 100
    assert 0 <= pvd["secondary"] <= 100
    assert "runway" in pvd["proxy_notes"].lower()


def test_expansion_candidates_falls_back_when_runway_count_is_zero(monkeypatch):
    monkeypatch.setattr("data_loader.get_airports_for_region", lambda region: ["AAA"])
    monkeypatch.setattr(
        "data_loader.airport_by_iata",
        lambda iata: {
            "iata": iata,
            "name": "Zero Runway Test Airport",
            "runway_count": 0,
        },
    )
    monkeypatch.setattr(
        "data_loader.metrics_by_iata",
        lambda iata: {
            "iata": iata,
            "year": 2024,
            "enplanements": 1000,
            "prior_year_enplanements": 900,
            "yoy_growth": 11.11,
        },
    )

    candidate = expansion_candidates("test")[0]

    assert candidate["enplanements_per_runway"] == 1000.0
    assert candidate["utilization"] == 100.0
