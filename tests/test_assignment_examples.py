from data_loader import expansion_candidates
from tools import (
    compare_airports,
    get_long_haul_estimate,
    get_unmet_demand,
    rank_airports_for_expansion,
)


def test_new_england_expansion_ranking_is_deterministic(monkeypatch):
    monkeypatch.setattr("tools._status_delay_scores", lambda: {})

    result = rank_airports_for_expansion.invoke(
        {"region": "New England", "top_n": 5}
    )

    assert "Ranking for region: New England" in result
    assert "BOS" in result
    assert "Composite" in result
    assert "Utilization" in result


def test_lax_vs_sna_congestion_comparison_shows_provenance(monkeypatch):
    monkeypatch.setattr("tools._status_delay_scores", lambda: {})

    result = compare_airports.invoke({"iata1": "LAX", "iata2": "SNA"})

    assert "Comparison: LAX vs SNA" in result
    assert "Current FAA delay | None | None" in result
    assert "Structural congestion baseline | 72.0 | 35.0" in result
    assert "Final congestion score | 72.0 | 35.0" in result
    assert "Unmet-demand pressure (proxy) | 63.8 (Moderate) | 22.4 (Limited)" in result


def test_anc_long_haul_estimate_is_labeled_proxy():
    result = get_long_haul_estimate.invoke({"iata": "ANC"})

    assert result["long_haul_share_proxy_pct"] == 35
    assert result["confidence"] == "medium"
    assert result["is_proxy"] is True
    assert "not calculated from current route-level schedules" in result["note"].lower()


def test_sfo_unmet_demand_pressure_is_a_proxy_index(monkeypatch):
    monkeypatch.setattr("tools._status_delay_scores", lambda: {})

    result = get_unmet_demand.invoke({"iata": "SFO"})

    assert result["iata"] == "SFO"
    assert 0 <= result["pressure_score"] <= 100
    assert result["classification"] in {"High", "Moderate", "Limited"}
    assert "congestion" in result["drivers"]
    assert "utilization" in result["drivers"]
    assert "growth" in result["drivers"]
    assert result["is_proxy"] is True
    assert "unserved" in result["definition"].lower()


def test_sfo_utilization_does_not_depend_on_comparison_set():
    us = next(item for item in expansion_candidates("US") if item["iata"] == "SFO")
    california = next(
        item for item in expansion_candidates("California") if item["iata"] == "SFO"
    )

    assert us["utilization"] == california["utilization"]
    assert us["enplanements_per_runway"] == california["enplanements_per_runway"]
