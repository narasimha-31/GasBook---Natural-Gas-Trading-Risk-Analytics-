"""P&L tests on a tiny hand-checkable book (no database needed)."""

import pandas as pd
import pytest

from gasbook.book import pnl

# March 2026 contract expires Wed 2026-02-25; March has 31 days.
MAR = pd.Timestamp("2026-03-01")
MAR_END = pd.Timestamp("2026-03-31")


def marks():
    days = pd.bdate_range("2026-02-02", "2026-04-10")
    futures = pd.Series(3.0, index=days)
    futures["2026-02-10":] = 3.5  # front month rises 50 cents on Feb 10
    futures["2026-02-26":] = 9.9  # after expiry NG=F is April; must NOT be used for March
    spot = pd.Series(4.0, index=days)
    return pnl.Marks(spot, futures)


def trade(tid, trade_date, side, ptype, price=None, adder=None, vol=10_000):
    return {
        "trade_id": tid, "trade_date": pd.Timestamp(trade_date), "counterparty_id": "CP01", "buy_sell": side,
        "delivery_start": MAR, "delivery_end": MAR_END, "volume_mmbtu_per_day": vol, "price_type": ptype,
        "fixed_price": price, "index_adder": adder,
    }


def test_forward_mark_uses_final_settlement_after_expiry():
    m = marks()
    assert m.forward(MAR, pd.Timestamp("2026-02-24")) == 3.5
    assert m.forward(MAR, pd.Timestamp("2026-02-27")) == 3.5  # final settle, not the April price 9.9


def test_fixed_buy_before_delivery_is_marked_to_futures():
    book = pd.DataFrame([trade("T1", "2026-02-05", "buy", "fixed", price=3.0)])
    v = pnl.trade_values(book, marks(), pd.Timestamp("2026-02-12"))
    assert v["value"].iloc[0] == pytest.approx(10_000 * 31 * (3.5 - 3.0))


def test_fixed_sell_settles_at_spot_once_delivered():
    book = pd.DataFrame([trade("T1", "2026-02-05", "sell", "fixed", price=3.0)])
    v = pnl.trade_values(book, marks(), pd.Timestamp("2026-04-06"))
    assert v["value"].iloc[0] == pytest.approx(-10_000 * 31 * (4.0 - 3.0))


def test_index_deal_only_carries_its_margin():
    book = pd.DataFrame([trade("T1", "2026-02-05", "sell", "index", adder=0.03)])
    for day in ("2026-02-05", "2026-03-15", "2026-04-06"):
        v = pnl.trade_values(book, marks(), pd.Timestamp(day))
        assert v["value"].iloc[0] == pytest.approx(0.03 * 10_000 * 31)


def test_trades_are_excluded_before_trade_date():
    book = pd.DataFrame([trade("T1", "2026-02-20", "buy", "fixed", price=3.0)])
    assert pnl.trade_values(book, marks(), pd.Timestamp("2026-02-19")).empty


def test_pnl_explain_adds_up_and_isolates_price_move():
    book = pd.DataFrame([
        trade("T1", "2026-02-05", "buy", "fixed", price=3.0),
        trade("T2", "2026-02-10", "sell", "index", adder=0.03),
    ])
    days = pd.bdate_range("2026-02-05", "2026-04-06")
    daily = pnl.daily_pnl(book, marks(), days).set_index("date")

    parts = daily[["new_deals", "forward_price_move", "delivery_and_spot"]].sum(axis=1)
    assert (parts - daily["pnl"]).abs().max() < 1e-6
    feb10 = daily.loc["2026-02-10"]
    assert feb10["forward_price_move"] == pytest.approx(10_000 * 31 * 0.5)  # T1 gains on the 50c move
    assert feb10["new_deals"] == pytest.approx(0.03 * 10_000 * 31)  # T2 margin booked on its trade date
    assert daily["mtm_total"].iloc[-1] == pytest.approx(10_000 * 31 * (4.0 - 3.0) + 0.03 * 10_000 * 31)
