from scoring import calculate_scores, format_ranking, normalize, rank_airports


def test_calculate_scores_uses_required_weights():
    scores = calculate_scores(
        {
            "delay_minutes": 60,
            "yoy_growth": 20,
            "utilization": 95,
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
        "composite": 34.7,
        "congestion": 25.0,
        "growth": 32.0,
        "utilization": 45.5,
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
