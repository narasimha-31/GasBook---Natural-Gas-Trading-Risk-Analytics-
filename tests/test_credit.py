"""Credit exposure tests on a tiny hand-checkable book."""

import pandas as pd
import pytest

from gasbook.book import credit, pnl

MAR, MAR_END = pd.Timestamp("2026-03-01"), pd.Timestamp("2026-03-31")


def marks(spot_level=4.0):
    days = pd.bdate_range("2026-02-02", "2026-05-29")
    return pnl.Marks(pd.Series(spot_level, index=days), pd.Series(3.0, index=days))


def cps(limit=1_000_000, status="active"):
    return pd.DataFrame([{"counterparty_id": "CP01", "name": "Test Buyer", "status": status,
                          "credit_limit_usd": limit}])


def trade(side, ptype, price=None, adder=None, vol=10_000):
    return {"trade_id": "T1", "trade_date": pd.Timestamp("2026-02-05"), "counterparty_id": "CP01",
            "buy_sell": side, "delivery_start": MAR, "delivery_end": MAR_END, "volume_mmbtu_per_day": vol,
            "price_type": ptype, "fixed_price": price, "index_adder": adder}


def test_payment_date_is_25th_of_next_month():
    assert credit.payment_date(MAR) == pd.Timestamp("2026-04-25")


def test_unpaid_sales_build_up_then_clear_on_payment():
    book = pd.DataFrame([trade("sell", "fixed", price=3.0)])
    mid = credit.exposures(book, cps(), marks(), pd.Timestamp("2026-03-10")).iloc[0]
    assert mid["unpaid_sales"] == pytest.approx(10 * 10_000 * 3.0)  # Mar 1-10 delivered, unpaid
    before = credit.exposures(book, cps(), marks(), pd.Timestamp("2026-04-24")).iloc[0]
    assert before["unpaid_sales"] == pytest.approx(31 * 10_000 * 3.0)  # full month still owed
    after = credit.exposures(book, cps(), marks(), pd.Timestamp("2026-04-27")).iloc[0]
    assert after["unpaid_sales"] == 0 and after["exposure"] == 0


def test_index_sale_bills_at_spot_so_a_spike_raises_what_they_owe():
    book = pd.DataFrame([trade("sell", "index", adder=0.03)])
    calm = credit.exposures(book, cps(), marks(4.0), pd.Timestamp("2026-04-01")).iloc[0]
    spike = credit.exposures(book, cps(), marks(30.0), pd.Timestamp("2026-04-01")).iloc[0]
    assert calm["unpaid_sales"] == pytest.approx(31 * 10_000 * 4.03)
    assert spike["unpaid_sales"] == pytest.approx(31 * 10_000 * 30.03)


def test_purchases_net_against_sales_and_exposure_floors_at_zero():
    buy = trade("buy", "fixed", price=3.0)
    book = pd.DataFrame([buy])
    e = credit.exposures(book, cps(), marks(), pd.Timestamp("2026-04-01")).iloc[0]
    assert e["unpaid_purchases"] == pytest.approx(31 * 10_000 * 3.0)
    assert e["exposure"] == 0  # we owe them, so they are not a credit risk to us


def test_future_value_counts_before_delivery():
    book = pd.DataFrame([trade("buy", "fixed", price=2.5)])  # futures at 3.0 -> deal is worth 0.5 to us
    e = credit.exposures(book, cps(), marks(), pd.Timestamp("2026-02-10")).iloc[0]
    assert e["future_value"] == pytest.approx(31 * 10_000 * 0.5)
    assert e["exposure"] == pytest.approx(31 * 10_000 * 0.5)


def test_alerts_and_commissioning_halves_limit():
    book = pd.DataFrame([trade("sell", "fixed", price=3.0)])
    day = pd.Timestamp("2026-04-01")  # owed 930,000
    assert credit.exposures(book, cps(limit=2_000_000), marks(), day).iloc[0]["alert"] == "green"
    assert credit.exposures(book, cps(limit=1_200_000), marks(), day).iloc[0]["alert"] == "amber"
    assert credit.exposures(book, cps(limit=900_000), marks(), day).iloc[0]["alert"] == "red"
    restricted = credit.exposures(book, cps(limit=2_000_000, status="commissioning"), marks(), day).iloc[0]
    assert restricted["effective_limit"] == 1_000_000
    assert restricted["alert"] == "amber"
