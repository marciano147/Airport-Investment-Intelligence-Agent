from tools import (
    _FAA_STATUS_CACHE,
    _status_delay_scores,
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
    assert "100.0" in result
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
    _FAA_STATUS_CACHE["data"] = None
    _FAA_STATUS_CACHE["expires_at"] = 0.0

    class Response:
        text = "<not-valid"

        def raise_for_status(self):
            return None

    monkeypatch.setattr("tools.requests.get", lambda *args, **kwargs: Response())

    result = get_congestion.invoke({"iata": "BOS"})

    assert result["iata"] == "BOS"
    assert result["delay_minutes"] == 0
    assert "error" in result
    assert "FAA status feed" in result["suggestion"]


def test_faa_status_scores_use_ttl_cache(monkeypatch):
    _FAA_STATUS_CACHE["data"] = None
    _FAA_STATUS_CACHE["expires_at"] = 0.0
    calls = {"count": 0}

    class Response:
        text = """
        <Airport_Status>
          <Delay_type>
            <Name>Ground Delay</Name>
            <Airport>
              <ARPT>BOS</ARPT>
              <Reason>weather</Reason>
            </Airport>
          </Delay_type>
        </Airport_Status>
        """

        def raise_for_status(self):
            return None

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        return Response()

    monkeypatch.setattr("tools.requests.get", fake_get)

    first = _status_delay_scores()
    second = _status_delay_scores()

    assert calls["count"] == 1
    assert first == second
    assert first["BOS"]["delay_minutes"] == 45


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
