"""Stress replay tests on small hand-checkable data."""

import numpy as np
import pandas as pd
import pytest

from gasbook.book import pnl, stress


def test_ratios_start_at_one_and_ignore_roll_jumps():
    days = pd.bdate_range("2026-02-16", "2026-03-06")
    spot = pd.Series(4.0, index=days)
    spot["2026-02-18":] = 8.0
    fut = pd.Series(3.0, index=days)
    fut["2026-02-26":] = 3.6  # jump the day after the Feb 25 expiry = a roll, not a storm move
    r = stress.storm_ratios(spot, fut, "2026-02-16", "2026-03-06")
    assert r.iloc[0].tolist() == [1.0, 1.0]
    assert r["spot_ratio"].iloc[-1] == pytest.approx(2.0)
    assert r["futures_ratio"].iloc[-1] == pytest.approx(1.0)


def test_shocked_marks_apply_path_then_hold():
    hist = pd.bdate_range("2026-09-01", "2026-09-22")
    marks = pnl.Marks(pd.Series(3.0, index=hist), pd.Series(2.5, index=hist))
    ratios = pd.DataFrame({"spot_ratio": [1.0, 2.0, 4.0], "futures_ratio": [1.0, 1.5, 1.2]})
    m, days = stress.shocked_marks(marks, pd.Timestamp("2026-09-22"), ratios, pd.Timestamp("2026-09-30"))
    assert days[0] == pd.Timestamp("2026-09-23")
    assert m.spot(pd.Timestamp("2026-09-23")) == pytest.approx(6.0)
    assert m.spot(pd.Timestamp("2026-09-24")) == pytest.approx(12.0)
    assert m.spot(pd.Timestamp("2026-09-30")) == pytest.approx(12.0)  # held at the final storm level
    assert m.spot(pd.Timestamp("2026-09-22")) == pytest.approx(3.0)  # history untouched
    assert float(m.futures.loc["2026-09-30"]) == pytest.approx(3.0)


def test_scenario_pnl_for_a_short_fixed_sale():
    hist = pd.bdate_range("2026-09-01", "2026-09-22")
    marks = pnl.Marks(pd.Series(3.0, index=hist), pd.Series(3.0, index=hist))
    trades = pd.DataFrame([{
        "trade_id": "T1", "trade_date": pd.Timestamp("2026-09-10"), "counterparty_id": "CP01", "buy_sell": "sell",
        "delivery_start": pd.Timestamp("2026-10-01"), "delivery_end": pd.Timestamp("2026-10-31"),
        "volume_mmbtu_per_day": 10_000, "price_type": "fixed", "fixed_price": 3.0, "index_adder": np.nan,
    }])
    cps = pd.DataFrame([{"counterparty_id": "CP01", "name": "Buyer", "status": "active", "credit_limit_usd": 1e7}])
    ratios = pd.DataFrame({"spot_ratio": [1.0, 2.0], "futures_ratio": [1.0, 2.0]})
    path, exp = stress.run_scenario(trades, cps, marks, pd.Timestamp("2026-09-22"), ratios,
                                    pd.Timestamp("2026-09-24"))
    # October futures double from 3 to 6: a 10,000/day x 31-day sale at $3 loses 31 x 10,000 x 3
    assert path["pnl_vs_today"].iloc[-1] == pytest.approx(-31 * 10_000 * 3.0)
    assert (exp["exposure"] == 0).all()  # a losing sale is not a credit exposure to the buyer
