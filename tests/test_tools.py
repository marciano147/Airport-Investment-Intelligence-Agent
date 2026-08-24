from tools import (
    compare_airports,
    get_airport_info,
    get_congestion,
    get_long_haul_estimate,
    get_passenger_metrics,
    rank_airports_for_expansion,
)


def test_compare_airports_returns_side_by_side_scores(monkeypatch):
    monkeypatch.setattr("tools._status_delay_scores", lambda: {})

    result = compare_airports.invoke({"iata1": "LAX", "iata2": "SNA"})

    assert "Comparison: LAX vs SNA" in result
    assert "Composite score" in result
    assert "Long-haul proxy" in result
    assert "Congestion score | 72.0 | 35.0" in result
    assert "Assumptions & Limitations" in result


def test_compare_airports_returns_invalid_airport_error(monkeypatch):
    monkeypatch.setattr("tools._status_delay_scores", lambda: {})

    result = compare_airports.invoke({"iata1": "ZZZ", "iata2": "LAX"})

    assert "Error for ZZZ" in result
    assert "No cached airport" in result


def test_airport_and_passenger_tools_return_errors_for_unknown_iata():
    airport = get_airport_info.invoke({"iata": "ZZZ"})
    metrics = get_passenger_metrics.invoke({"iata": "ZZZ"})

    assert "error" in airport
    assert "error" in metrics


def test_get_congestion_returns_fallback_when_faa_feed_is_invalid(monkeypatch):
    monkeypatch.setattr("tools.get_faa_status", lambda iata: (_ for _ in ()).throw(ValueError("bad xml")))

    result = get_congestion.invoke({"iata": "BOS"})

    assert result["iata"] == "BOS"
    assert result["delay_minutes"] == 0
    assert "error" in result
    assert "FAA NAS Status feed" in result["suggestion"]


def test_get_congestion_uses_live_nas_program(monkeypatch):
    monkeypatch.setattr(
        "tools.get_faa_status",
        lambda iata: {
            "iata": "SAN",
            "delay_minutes": 20.0,
            "status": "Active FAA NAS traffic management program",
            "program": "Ground Delay Programs",
            "reason": "airport volume",
            "source": "nas",
        },
    )

    result = get_congestion.invoke({"iata": "SAN"})

    assert result["iata"] == "SAN"
    assert result["delay_minutes"] == 20.0
    assert result["program"] == "Ground Delay Programs"
    assert result["congestion_score"] >= 40


def test_long_haul_estimate_known_and_unknown_airports():
    known = get_long_haul_estimate.invoke({"iata": "ANC"})
    unknown = get_long_haul_estimate.invoke({"iata": "ZZZ"})

    assert known["long_haul_pct_estimate"] == 35
    assert known["confidence"] == "medium"
    assert unknown["long_haul_pct_estimate"] is None
    assert unknown["confidence"] == "none"


def test_rank_tool_accepts_us_default_without_live_faa(monkeypatch):
    monkeypatch.setattr("tools._status_delay_scores", lambda: {})

    result = rank_airports_for_expansion.invoke({"region": "US", "top_n": 3})

    assert "Ranking for region: US" in result
    assert "Composite" in result
    assert "Assumptions & Limitations" in result


def test_rank_tool_returns_message_for_empty_candidate_set(monkeypatch):
    monkeypatch.setattr("tools._status_delay_scores", lambda: {})
    monkeypatch.setattr("tools.expansion_candidates", lambda region: [])

    result = rank_airports_for_expansion.invoke({"region": "ZZ", "top_n": 3})

    assert "No candidate airports found" in result
