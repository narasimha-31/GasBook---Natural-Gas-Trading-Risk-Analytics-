"""Simulated book tests (no database needed)."""

import numpy as np
import pandas as pd
import pytest

from gasbook.book import simulate


@pytest.fixture
def futures():
    days = pd.bdate_range("2025-01-02", "2025-06-30")
    return pd.DataFrame({"date": days, "close": 3.0 + np.linspace(0, 1, len(days))})


def test_front_delivery_month_rolls_after_expiry():
    # March 2026 contract expires Wed 2026-02-25
    assert simulate.front_delivery_month(pd.Timestamp("2026-02-25")) == pd.Timestamp("2026-03-01")
    assert simulate.front_delivery_month(pd.Timestamp("2026-02-26")) == pd.Timestamp("2026-04-01")
    assert simulate.front_delivery_month(pd.Timestamp("2026-02-10")) == pd.Timestamp("2026-03-01")
    assert simulate.front_delivery_month(pd.Timestamp("2026-01-20")) == pd.Timestamp("2026-02-01")  # Feb expires Jan 28


def test_generation_is_repeatable(futures):
    a = simulate.generate_trades(futures, start="2025-01-02", end="2025-06-30")
    b = simulate.generate_trades(futures, start="2025-01-02", end="2025-06-30")
    pd.testing.assert_frame_equal(a, b)


def test_fixed_prices_come_from_the_real_screen_price(futures):
    t = simulate.generate_trades(futures, start="2025-01-02", end="2025-06-30")
    fixed = t[t["price_type"] == "fixed"].merge(futures, left_on="trade_date", right_on="date")
    expected = fixed["close"] + np.where(fixed["buy_sell"] == "buy", -simulate.DEALER_MARGIN, simulate.DEALER_MARGIN)
    assert np.allclose(fixed["fixed_price"], expected.round(4))


def test_trades_are_valid(futures):
    t = simulate.generate_trades(futures, start="2025-01-02", end="2025-06-30")
    assert t["trade_id"].is_unique
    assert (t["delivery_start"] > t["trade_date"]).all()
    assert (t["delivery_start"].dt.day == 1).all()
    assert (t["delivery_end"] == t["delivery_start"] + pd.offsets.MonthEnd(0)).all()
    assert t["volume_mmbtu_per_day"].isin(simulate.VOLUMES).all()
    assert set(t["counterparty_id"]) <= set(simulate.COUNTERPARTIES["counterparty_id"])
    fixed = t["price_type"] == "fixed"
    assert t.loc[fixed, "fixed_price"].notna().all() and t.loc[fixed, "index_name"].isna().all()
    assert t.loc[~fixed, "fixed_price"].isna().all() and t.loc[~fixed, "index_name"].notna().all()
    # buys only from suppliers, sells only to buyers
    assert set(t.loc[t["buy_sell"] == "buy", "counterparty_id"]) <= set(simulate.BUY_FROM)
    assert set(t.loc[t["buy_sell"] == "sell", "counterparty_id"]) <= set(simulate.SELL_TO)


def test_counterparties_are_fictional():
    real_names = ["cheniere", "venture global", "freeport", "kinder", "energy transfer", "exxon", "chevron",
                  "shell", "bp ", "sempra", "williams", "eqt", "entergy", "nrg", "vistra", "centerpoint", "dow"]
    names = " ".join(simulate.COUNTERPARTIES["name"]).lower()
    assert not any(n in names for n in real_names)


def test_schema_has_all_tables():
    from gasbook.book.database import SCHEMA

    sql = SCHEMA.read_text().lower()
    for table in ("hubs", "counterparties", "trades", "prices"):
        assert f"create table {table}" in sql


def test_front_delivery_month_matches_futures_expiry_everywhere():
    """For every business day, delivery month's expiry is on/after the trade date and the previous month's is before."""
    from gasbook.ingest.futures import expiry_dates

    for d in pd.bdate_range("2025-01-01", "2026-12-31"):
        m = simulate.front_delivery_month(d)
        exp_this = expiry_dates(m, m)[expiry_dates(m, m) < m].max()  # expiry of month m
        assert m.day == 1
        assert m - pd.offsets.BDay(3) >= d
        assert (m - pd.offsets.MonthBegin(1)) - pd.offsets.BDay(3) < d
        assert exp_this == m - pd.offsets.BDay(3)


def test_fixed_position_stays_within_limit():
    days = pd.bdate_range("2025-01-02", "2026-06-30")
    futures = pd.DataFrame({"date": days, "close": 3.0})
    t = simulate.generate_trades(futures, start="2025-01-02", end="2026-06-30")
    fixed = t[t["price_type"] == "fixed"].copy()
    fixed["qty"] = fixed["volume_mmbtu_per_day"].where(fixed["buy_sell"] == "buy", -fixed["volume_mmbtu_per_day"])
    running = fixed.groupby("delivery_start")["qty"].cumsum()  # position after each trade, in trade order
    assert running.abs().max() <= simulate.POSITION_LIMIT
