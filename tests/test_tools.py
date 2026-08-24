from tools import compare_airports, get_long_haul_estimate, rank_airports_for_expansion


def test_compare_airports_returns_side_by_side_scores(monkeypatch):
    monkeypatch.setattr("tools._status_delay_scores", lambda: {})

    result = compare_airports.invoke({"iata1": "LAX", "iata2": "SNA"})

    assert "Comparison: LAX vs SNA" in result
    assert "Composite score" in result
    assert "Long-haul proxy" in result
    assert "100.0" in result
    assert "Assumptions & Limitations" in result


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
