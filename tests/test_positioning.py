"""Hedge fund positioning tests: percentile uses past data only, signals, timing, and roll handling."""

import numpy as np
import pandas as pd
import pytest

from gasbook.research import hedge_fund_positioning as hfp


def test_rolling_percentile_uses_only_past_and_current():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 0.0])
    pct = hfp.rolling_percentile(s, window=3)
    assert pct.iloc[:2].isna().all()
    assert pct.iloc[3] == pytest.approx(1.0)  # 4 is the highest of [2, 3, 4]
    assert pct.iloc[4] == pytest.approx(1 / 3)  # 0 is the lowest of [3, 4, 0]


def test_future_values_do_not_change_past_percentiles():
    s = pd.Series(np.arange(20, dtype=float))
    changed = s.copy()
    changed.iloc[15:] = -100
    assert hfp.rolling_percentile(s, 5).iloc[:15].equals(hfp.rolling_percentile(changed, 5).iloc[:15])


def test_signal_is_contrarian():
    pct = pd.Series([0.05, 0.5, 0.95, np.nan])
    sig = hfp.signal_from_percentile(pct, crowded=0.10)
    assert sig.iloc[0] == 1  # funds crowded short -> buy
    assert sig.iloc[1] == 0
    assert sig.iloc[2] == -1  # funds crowded long -> sell
    assert np.isnan(sig.iloc[3])


def test_roll_days_are_zeroed():
    days = pd.bdate_range("2026-02-16", "2026-03-06")
    close = pd.Series(3.0, index=days)
    close["2026-02-26":] = 4.0  # jump on the day after the Feb 25 expiry
    r = hfp.daily_returns_ex_roll(pd.DataFrame({"date": days, "close": close.to_numpy()}))
    assert r.abs().sum() == pytest.approx(0.0)


def test_entry_is_the_monday_after_tuesday_report(monkeypatch):
    monkeypatch.setattr(hfp, "HOLD_DAYS", 2)
    monkeypatch.setattr(hfp, "LOOKBACK_WEEKS", 1)
    days = pd.bdate_range("2026-03-02", "2026-04-30")
    futures = pd.DataFrame({"date": days, "close": np.exp(np.arange(len(days)) * 0.01)})
    cot = pd.DataFrame({"report_date": pd.to_datetime(["2026-03-03", "2026-03-10"]), "mm_net_pct_oi": [0.1, 0.2]})
    weeks = hfp.build_weeks(cot, futures)
    assert list(weeks["entry_date"].dt.strftime("%Y-%m-%d")) == ["2026-03-09", "2026-03-16"]
    assert weeks["forward_return"].round(6).eq(0.02).all()  # 2 trading days of +1%


def test_reports_before_futures_data_are_dropped(monkeypatch):
    monkeypatch.setattr(hfp, "HOLD_DAYS", 2)
    monkeypatch.setattr(hfp, "LOOKBACK_WEEKS", 1)
    days = pd.bdate_range("2026-03-02", "2026-04-30")
    futures = pd.DataFrame({"date": days, "close": 3.0})
    cot = pd.DataFrame({"report_date": pd.to_datetime(["2025-06-03", "2026-03-10"]), "mm_net_pct_oi": [0.1, 0.2]})
    weeks = hfp.build_weeks(cot, futures)
    assert list(weeks["report_date"].dt.strftime("%Y-%m-%d")) == ["2026-03-10"]
