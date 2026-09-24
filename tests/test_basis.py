"""Basis risk tests on small hand-built price tables."""

import numpy as np
import pandas as pd
import pytest

from gasbook.risk import basis


def wide():
    idx = pd.to_datetime(["2015-01-05", "2015-01-06", "2015-01-07", "2015-02-24"])
    return pd.DataFrame(
        {"Henry Hub": [3.0, 3.1, 3.0, 2.9], "Algonquin Citygates": [9.0, np.nan, 5.0, 30.0]}, index=idx
    )


def test_basis_is_hub_minus_henry_and_keeps_gaps():
    b = basis.basis_table(wide())
    assert list(b.columns) == ["Algonquin Citygates"]
    assert b.loc["2015-01-05", "Algonquin Citygates"] == pytest.approx(6.0)
    assert np.isnan(b.loc["2015-01-06", "Algonquin Citygates"])  # hub didn't trade: stays empty


def test_basis_table_requires_henry():
    with pytest.raises(ValueError):
        basis.basis_table(pd.DataFrame({"Malin": [1.0]}))


def test_stats_find_blowout_day():
    s = basis.basis_stats(basis.basis_table(wide()), blowout=5.0)
    row = s.loc["Algonquin Citygates"]
    assert row["days"] == 3
    assert row["max"] == pytest.approx(27.1)
    assert str(row["max_day"]) == "2015-02-24"
    assert row["share_abs_gt_5"] == pytest.approx(2 / 3)


def test_paired_changes_skip_long_gaps():
    w = wide()
    chg = basis.paired_changes(w["Algonquin Citygates"], w["Henry Hub"], max_gap_days=4)
    # Jan 5 -> Jan 7 is a 2-day gap (kept); Jan 7 -> Feb 24 is 48 days (dropped)
    assert list(chg.index.strftime("%Y-%m-%d")) == ["2015-01-07"]
    assert chg.loc["2015-01-07", "hub"] == pytest.approx(-4.0)


def test_perfect_tracking_hub_is_fully_hedged():
    idx = pd.bdate_range("2015-01-01", periods=200)
    henry = pd.Series(3 + np.cumsum(np.random.default_rng(1).normal(0, 0.05, 200)), index=idx)
    res = basis.hedge_effectiveness(henry + 0.25, henry)  # constant basis
    assert res["effectiveness_naive"] == pytest.approx(1.0)
    assert res["hedge_ratio_min_var"] == pytest.approx(1.0)
    assert res["highly_effective"]


def test_independent_hub_is_not_hedged():
    idx = pd.bdate_range("2015-01-01", periods=500)
    rng = np.random.default_rng(2)
    henry = pd.Series(3 + np.cumsum(rng.normal(0, 0.05, 500)), index=idx)
    hub = pd.Series(3 + np.cumsum(rng.normal(0, 0.05, 500)), index=idx)
    res = basis.hedge_effectiveness(hub, henry)
    assert res["r2"] < 0.05
    assert res["effectiveness_naive"] < 0  # hedging an unrelated price adds risk
    assert not res["highly_effective"]


def test_monthly_effectiveness_averages_before_comparing():
    idx = pd.bdate_range("2015-01-01", "2016-12-31")
    rng = np.random.default_rng(3)
    month_level = pd.Series(rng.normal(0, 0.5, 24), index=pd.date_range("2015-01-01", periods=24, freq="MS"))
    henry = 3 + month_level.reindex(idx, method="ffill")
    hub = henry + rng.normal(0, 1.0, len(idx))  # big daily noise that averages out within a month
    daily = basis.hedge_effectiveness(hub, henry)
    monthly = basis.monthly_hedge_effectiveness(hub, henry)
    assert monthly["months"] == 23
    assert monthly["r2_monthly"] > daily["r2"]
    assert monthly["highly_effective_monthly"]
