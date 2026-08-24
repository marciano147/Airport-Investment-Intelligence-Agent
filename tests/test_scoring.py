from scoring import calculate_scores, normalize, rank_airports


def test_calculate_scores_uses_required_weights():
    scores = calculate_scores(
        {
            "delay_score": 100,
            "yoy_growth": 0.15,
            "utilization": 1,
            "secondary": 1,
        }
    )

    assert scores["composite"] == 100.0
    assert scores["congestion"] == 100.0
    assert scores["growth"] == 100.0
    assert scores["utilization"] == 100.0
    assert scores["secondary"] == 100.0


def test_missing_fields_default_to_zero():
    assert calculate_scores({}) == {
        "composite": 0.0,
        "congestion": 0.0,
        "growth": 0.0,
        "utilization": 0.0,
        "secondary": 0.0,
    }


def test_ranking_order_and_top_n():
    airports = [
        {"iata": "LOW", "delay_score": 10, "yoy_growth": 0.00, "utilization": 0.4, "secondary": 0.2},
        {"iata": "HIGH", "delay_score": 90, "yoy_growth": 0.12, "utilization": 0.9, "secondary": 0.8},
        {"iata": "MID", "delay_score": 50, "yoy_growth": 0.04, "utilization": 0.6, "secondary": 0.6},
    ]

    ranked = rank_airports(airports, top_n=2)

    assert [airport["iata"] for airport in ranked] == ["HIGH", "MID"]
    assert len(ranked) == 2


def test_normalize_bounds():
    assert normalize(-1) == 0.0
    assert normalize(2) == 2.0
    assert normalize(200) == 100.0
    assert normalize(0.5) == 50.0
    assert normalize(0.15, mode="growth") == 100.0
