from data_loader import (
    _NAS_STATUS_CACHE,
    airport_by_iata,
    cache_stats,
    clear_caches,
    expansion_candidates,
    fetch_nas_status_delays,
    get_airports_for_region,
    get_faa_status,
    get_runway_count,
    load_airports,
    metrics_by_iata,
    parse_delay_minutes,
    parse_nas_status_xml,
    secondary_proxy_score,
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


def test_get_runway_count_returns_safe_cached_count():
    assert get_runway_count("BOS") >= 1
    assert get_runway_count("ZZZ") == 1


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


def test_secondary_proxy_rewards_long_haul_route_mix():
    high_long_haul = {
        "iata": "JFK",
        "enplanements": 25_000_000,
        "enplanements_per_runway": 6_000_000,
    }
    low_long_haul = {
        "iata": "LGA",
        "enplanements": 25_000_000,
        "enplanements_per_runway": 6_000_000,
    }

    assert secondary_proxy_score(high_long_haul) > secondary_proxy_score(low_long_haul)


def test_expansion_candidates_falls_back_when_runway_count_is_zero(monkeypatch):
    clear_caches()
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
    assert candidate["utilization"] == 0.0
    clear_caches()


def test_data_loader_cache_stats_track_repeated_lookup():
    clear_caches()

    first = airport_by_iata("BOS")
    second = airport_by_iata("BOS")
    load_airports()
    load_airports()
    stats = cache_stats()

    assert first == second
    assert stats["airport_by_iata"]["hits"] >= 1
    assert stats["load_airports"]["hits"] >= 1
    assert stats["nas_status_cache"]["has_data"] is False


def test_parse_delay_minutes_handles_common_faa_text():
    assert parse_delay_minutes("20 minutes") == 20
    assert parse_delay_minutes("1 hour and 30 minutes") == 90
    assert parse_delay_minutes("31") == 31
    assert parse_delay_minutes("") is None


def test_parse_nas_status_xml_extracts_active_program_minutes():
    xml = """
    <AIRPORT_STATUS_INFORMATION>
      <Update_Time>Mon Aug 24 14:58:46 2026 GMT</Update_Time>
      <Delay_type>
        <Name>Ground Delay Programs</Name>
        <Ground_Delay_List>
          <Ground_Delay>
            <ARPT>SAN</ARPT>
            <Reason>airport volume</Reason>
            <Avg>20 minutes</Avg>
            <Max>48 minutes</Max>
          </Ground_Delay>
        </Ground_Delay_List>
      </Delay_type>
      <Delay_type>
        <Name>General Arrival/Departure Delay Info</Name>
        <Arrival_Departure_Delay_List>
          <Delay>
            <ARPT>PHX</ARPT>
            <Reason>TM Initiatives:ESP:VOL</Reason>
            <Arrival_Departure Type="Departure">
              <Min>31 minutes</Min>
              <Max>45 minutes</Max>
              <Trend>Increasing</Trend>
            </Arrival_Departure>
          </Delay>
        </Arrival_Departure_Delay_List>
      </Delay_type>
      <Delay_type>
        <Name>Ground Stops</Name>
        <Ground_Stop_List>
          <Ground_Stop>
            <ARPT>EWR</ARPT>
            <Reason>weather</Reason>
          </Ground_Stop>
        </Ground_Stop_List>
      </Delay_type>
    </AIRPORT_STATUS_INFORMATION>
    """

    parsed = parse_nas_status_xml(xml)

    assert parsed["SAN"]["delay_minutes"] == 20.0
    assert parsed["SAN"]["program"] == "Ground Delay Programs"
    assert parsed["SAN"]["source_detail"] == "avg_delay_minutes"
    assert parsed["PHX"]["delay_minutes"] == 38.0
    assert parsed["PHX"]["source_detail"] == "departure_delay_minutes"
    assert parsed["EWR"]["delay_minutes"] == 60.0
    assert parsed["EWR"]["source_detail"] == "ground_stop_proxy_minutes"


def test_fetch_nas_status_delays_uses_ttl_cache(monkeypatch):
    _NAS_STATUS_CACHE["data"] = None
    _NAS_STATUS_CACHE["expires_at"] = 0.0
    calls = {"count": 0}

    class Response:
        text = """
        <AIRPORT_STATUS_INFORMATION>
          <Delay_type>
            <Name>Ground Delay Programs</Name>
            <Ground_Delay_List>
              <Ground_Delay>
                <ARPT>BOS</ARPT>
                <Reason>weather</Reason>
                <Avg>25 minutes</Avg>
              </Ground_Delay>
            </Ground_Delay_List>
          </Delay_type>
        </AIRPORT_STATUS_INFORMATION>
        """

        def raise_for_status(self):
            return None

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        return Response()

    monkeypatch.setattr("data_loader.requests.get", fake_get)

    first = fetch_nas_status_delays()
    second = fetch_nas_status_delays()

    assert calls["count"] == 1
    assert first == second
    assert first["BOS"]["delay_minutes"] == 25.0


def test_get_faa_status_falls_back_when_no_active_nas_program(monkeypatch):
    monkeypatch.setattr("data_loader.fetch_nas_status_delays", lambda: {})

    result = get_faa_status("LAX")

    assert result["iata"] == "LAX"
    assert result["delay_minutes"] == 0
    assert result["status"] == "No active FAA NAS traffic management program"
