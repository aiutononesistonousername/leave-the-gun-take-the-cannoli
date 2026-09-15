"""Test del modello di proiezione (nessun accesso alla rete)."""

import numpy as np
import pandas as pd
import pytest

from cannoli import config, projections
from cannoli.config import Scenario


def _gdp_frame() -> pd.DataFrame:
    """PIL Eurostat fittizio: 2.000 mld nel 2025."""
    return pd.DataFrame({"geo": ["IT", "IT"], "country": ["Italia", "Italia"], "year": [2024, 2025], "gdp_meur": [1_950_000.0, 2_000_000.0]})


def _imf_frame() -> pd.DataFrame:
    rows = []
    for year in range(2024, 2032):
        rows.append({"year": year, "indicator": "NGDP_RPCH", "label": "", "value": 1.0})
        rows.append({"year": year, "indicator": "PCPIPCH", "label": "", "value": 2.0})
        rows.append({"year": year, "indicator": "LP", "label": "", "value": 58.0})
    return pd.DataFrame(rows)


def _cofog_frame() -> pd.DataFrame:
    rows = []
    for code, val in [("GF07", 6.6), ("GF09", 4.0), ("GF02", 1.3), ("TOTAL", 50.0)]:
        rows.append({"geo": "IT", "country": "Italia", "year": 2024, "cofog": code, "function": code, "unit": "PC_GDP", "value": val})
        rows.append({"geo": "IT", "country": "Italia", "year": 2024, "cofog": code, "function": code, "unit": "MIO_EUR", "value": val * 20_000})
    return pd.DataFrame(rows)


def test_linear_path_endpoints_and_length():
    path = projections.linear_path(2026, 2.0, 2035, 5.0)
    assert len(path) == 10
    assert path[2026] == pytest.approx(2.0)
    assert path[2035] == pytest.approx(5.0)
    steps = np.diff([path[y] for y in sorted(path)])
    assert np.allclose(steps, steps[0])


def test_piecewise_path_hits_every_waypoint():
    path = projections.piecewise_path({2026: 2.8, 2028: 3.2, 2035: 5.0})
    assert path[2026] == pytest.approx(2.8)
    assert path[2027] == pytest.approx(3.0)
    assert path[2028] == pytest.approx(3.2)
    assert path[2035] == pytest.approx(5.0)
    assert sorted(path) == list(range(2026, 2036))


def test_project_gdp_compounds_real_growth_and_inflation():
    gdp = projections.project_gdp(_gdp_frame(), _imf_frame(), end_year=2035)
    by_year = gdp.set_index("year")["gdp_bn"]
    assert by_year.loc[2025] == pytest.approx(2000.0)
    nominal = 1.01 * 1.02
    assert by_year.loc[2026] == pytest.approx(2000.0 * nominal)
    assert by_year.loc[2035] == pytest.approx(2000.0 * nominal**10)
    sources = gdp.set_index("year")["source"]
    assert sources.loc[2031] == "FMI WEO"
    assert sources.loc[2032].startswith("estrapolazione")


def test_baseline_scenario_is_flat():
    base = next(s for s in config.SCENARIOS if s.key == "baseline")
    shares = projections.scenario_shares(base)
    assert shares["total_share"].nunique() == 1
    assert shares["total_share"].iloc[0] == pytest.approx(config.START_CORE_SHARE + config.START_RELATED_SHARE)


def test_gov_path_reaches_targets():
    gov = next(s for s in config.SCENARIOS if s.key == "gov_path")
    shares = projections.scenario_shares(gov).set_index("year")
    assert shares.loc[config.TARGET_YEAR, "total_share"] == pytest.approx(config.NATO_TOTAL_TARGET)
    assert shares.loc[config.TARGET_YEAR, "core_share"] == pytest.approx(config.NATO_CORE_TARGET)
    assert shares.loc[config.TARGET_YEAR, "related_share"] == pytest.approx(config.NATO_RELATED_TARGET)
    assert shares["total_share"].is_monotonic_increasing


def test_core_only_scenario():
    sc = Scenario(key="x", label="x", short="x", description="", core_target=3.5)
    shares = projections.scenario_shares(sc).set_index("year")
    assert shares.loc[config.TARGET_YEAR, "core_share"] == pytest.approx(3.5)
    assert shares["related_share"].nunique() == 1


def test_build_scenarios_extra_cost_consistency():
    gdp = projections.project_gdp(_gdp_frame(), _imf_frame())
    scen = projections.build_scenarios(gdp, _cofog_frame(), _imf_frame())
    base = scen[scen["scenario"] == "baseline"]
    assert np.allclose(base["extra_vs_baseline_bn"], 0.0)
    gov = scen[scen["scenario"] == "gov_path"].set_index("year")
    assert (gov["extra_vs_baseline_bn"].iloc[1:] > 0).all()
    assert gov["cumulative_extra_bn"].is_monotonic_increasing
    # Nel 2035: (5,0 - 2,8)% del PIL
    gdp_2035 = gdp.set_index("year").loc[2035, "gdp_bn"]
    assert gov.loc[2035, "extra_vs_baseline_bn"] == pytest.approx((5.0 - 2.8) / 100 * gdp_2035)
    # Confronto con la sanità al 6,6% del PIL
    assert gov.loc[2035, "extra_pct_sanita"] == pytest.approx(2.2 / 6.6 * 100)
    assert gov.loc[2035, "extra_per_capita_eur"] == pytest.approx(gov.loc[2035, "extra_vs_baseline_bn"] * 1e9 / 58e6)
    # "Anni di bilancio" = somma dei rapporti annui extra_t / bilancio_t
    expected_years = (gov["extra_vs_baseline_bn"] / gov["istruzione_bn"]).sum()
    assert gov.loc[2035, "extra_years_of_istruzione"] == pytest.approx(expected_years)


def test_price_index_and_constant_prices():
    gdp = projections.project_gdp(_gdp_frame(), _imf_frame())
    by_year = gdp.set_index("year")
    assert by_year.loc[2025, "price_index"] == pytest.approx(1.0)
    assert by_year.loc[2035, "price_index"] == pytest.approx(1.02**10)
    scen = projections.build_scenarios(gdp, _cofog_frame(), _imf_frame())
    gov = scen[scen["scenario"] == "gov_path"].set_index("year")
    assert gov.loc[2035, "total_bn_const"] == pytest.approx(gov.loc[2035, "total_bn"] / 1.02**10)
    # A prezzi costanti la quota di PIL non cambia
    assert gov.loc[2035, "total_bn_const"] / (by_year.loc[2035, "gdp_bn"] / 1.02**10) * 100 == pytest.approx(5.0)
    assert gov["cumulative_extra_bn_const"].iloc[-1] < gov["cumulative_extra_bn"].iloc[-1]
