from scoring import (
    calculate_scores,
    calculate_unmet_demand_pressure,
    congestion_breakdown,
    format_ranking,
    get_congestion_score,
    load_congestion_baselines,
    normalize,
    rank_airports,
    utilization_score,
)


def test_calculate_scores_uses_required_weights():
    scores = calculate_scores(
        {
            "delay_minutes": 60,
            "yoy_growth": 20,
            "utilization": 100,
            "secondary": 100,
        }
    )

    assert scores["composite"] == 100.0
    assert scores["congestion"] == 100.0
    assert scores["growth"] == 100.0
    assert scores["utilization"] == 100.0
    assert scores["secondary"] == 100.0


def test_defaults_are_explicit_scoring_fallbacks():
    scores = calculate_scores({})

    assert scores == {
        "composite": 43.9,
        "congestion": 35.0,
        "growth": 47.1,
        "utilization": 50.0,
        "secondary": 50.0,
    }


def test_ranking_order_and_top_n():
    airports = [
        {"iata": "LOW", "delay_minutes": 5, "yoy_growth": 0, "utilization": 50, "secondary": 20},
        {"iata": "HIGH", "delay_minutes": 55, "yoy_growth": 18, "utilization": 92, "secondary": 80},
        {"iata": "MID", "delay_minutes": 30, "yoy_growth": 8, "utilization": 75, "secondary": 60},
    ]

    ranked = rank_airports(airports, top_n=2)

    assert [airport["iata"] for airport in ranked] == ["HIGH", "MID"]
    assert len(ranked) == 2


def test_rank_airports_handles_empty_and_large_top_n():
    assert rank_airports([]) == []

    airports = [
        {"iata": "A", "delay_minutes": 10},
        {"iata": "B", "delay_minutes": 20},
    ]

    assert len(rank_airports(airports, top_n=10)) == 2


def test_delay_score_takes_precedence_and_bad_inputs_clamp():
    scores = calculate_scores(
        {
            "delay_score": 30,
            "delay_minutes": 60,
            "yoy_growth": "bad",
            "utilization": None,
            "secondary": "bad",
        }
    )

    assert scores == {
        "composite": 42.1,
        "congestion": 30.0,
        "growth": 47.1,
        "utilization": 50.0,
        "secondary": 50.0,
    }


def test_zero_live_delay_uses_airport_baseline_congestion():
    assert get_congestion_score(0, "ATL") == 75.0
    assert get_congestion_score(None, "ZZZ") == 35.0
    assert get_congestion_score(45, "ZZZ") == 100.0


def test_normalize_bounds():
    assert normalize(-1) == 0.0
    assert normalize(50) == 50.0
    assert normalize(200) == 100.0
    assert normalize(20, -5, 20) == 100.0
    assert normalize(3, -5, 20) == 32.0


def test_format_ranking_includes_full_breakdown():
    table = format_ranking(
        [
            {
                "iata": "BOS",
                "name": "Boston Logan International Airport",
                "composite": 50.0,
                "congestion": 10.0,
                "growth": 20.0,
                "utilization": 30.0,
                "secondary": 40.0,
            }
        ]
    )

    assert "Composite" in table
    assert "Secondary" in table
    assert "BOS" in table


def test_congestion_baselines_load_from_csv():
    baselines = load_congestion_baselines()

    assert baselines["EWR"]["baseline"] == 82
    assert baselines["EWR"]["confidence"] == "low"
    assert "proxy" in baselines["EWR"]["note"]


def test_congestion_breakdown_separates_live_and_structural():
    quiet = congestion_breakdown(0, "LAX")
    delayed = congestion_breakdown(38, "LAX")

    assert quiet["structural_baseline"] == 72.0
    assert quiet["congestion_score"] == 72.0
    assert quiet["live_faa_program"] == "none"
    assert quiet["source"] == "prototype structural baseline"
    assert delayed["live_delay_minutes"] == 38
    assert delayed["congestion_score"] > quiet["congestion_score"]
    assert delayed["live_faa_program"] == "38 min"


def test_utilization_score_is_absolute():
    assert utilization_score(1_000_000) == 0.0
    assert utilization_score(8_000_000) == 100.0
    assert utilization_score(4_500_000) == 50.0


def test_unmet_demand_pressure_is_a_labeled_proxy():
    result = calculate_unmet_demand_pressure(
        {
            "iata": "SFO",
            "delay_minutes": 0,
            "yoy_growth": 3.67,
            "enplanements_per_runway": 6_269_742,
            "secondary": 50,
        }
    )

    assert 0 <= result["pressure_score"] <= 100
    assert result["classification"] in {"High", "Moderate", "Limited"}
    assert result["is_proxy"] is True
    assert result["drivers"]["congestion"] == 70.0
    assert "utilization" in result["drivers"]
    assert "growth" in result["drivers"]


def test_format_ranking_with_empty_list_still_returns_headers():
    table = format_ranking([])

    assert "Rank" in table
    assert "Composite" in table
    assert "BOS" not in table
