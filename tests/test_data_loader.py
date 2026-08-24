from data_loader import expansion_candidates, metrics_by_iata


def test_metrics_are_loaded_from_faa_cache():
    metrics = metrics_by_iata("BOS")

    assert metrics["year"] == 2024
    assert metrics["enplanements"] == 21090721
    assert metrics["prior_year_enplanements"] == 19962678
    assert metrics["source"] == "FAA 2024 commercial service enplanements workbook"


def test_expansion_candidates_add_deterministic_proxies():
    candidates = expansion_candidates("New England")
    bos = next(candidate for candidate in candidates if candidate["iata"] == "BOS")
    pvd = next(candidate for candidate in candidates if candidate["iata"] == "PVD")

    assert bos["utilization"] == 1.0
    assert bos["secondary"] == 0.0
    assert 0 < pvd["utilization"] < 1
    assert 0 < pvd["secondary"] < 1
    assert "proxy" in pvd["proxy_notes"].lower()
