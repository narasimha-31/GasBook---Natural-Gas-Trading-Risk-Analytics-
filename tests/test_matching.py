"""Confirmation matching tests: each planted error type is caught and harmless differences are not flagged."""

import pandas as pd
import pytest

from gasbook.book import confirmations, matching, simulate


def one_trade(**overrides):
    t = {"trade_id": "T00001", "trade_date": pd.Timestamp("2026-03-02"), "counterparty_id": "CP03",
         "buy_sell": "sell", "delivery_start": pd.Timestamp("2026-04-01"), "delivery_end": pd.Timestamp("2026-04-30"),
         "volume_mmbtu_per_day": 10_000, "price_type": "fixed", "fixed_price": 3.1234, "index_adder": None}
    t.update(overrides)
    return pd.DataFrame([t])


def their_confirm(**overrides):
    c = {"confirm_ref": "C-1", "counterparty_id": "CP03", "their_side": "buy", "trade_date": pd.Timestamp("2026-03-02"),
         "confirm_date": pd.Timestamp("2026-03-03"), "delivery_start": pd.Timestamp("2026-04-01"),
         "delivery_end": pd.Timestamp("2026-04-30"), "volume_mmbtu_per_day": 10_000, "price_type": "fixed",
         "fixed_price": 3.123, "index_adder": None}
    c.update(overrides)
    return pd.DataFrame([c])


def test_rounded_price_and_late_confirm_still_match():
    r = matching.match(one_trade(), their_confirm()).iloc[0]
    assert r["status"] == "matched"


@pytest.mark.parametrize("field, change", [
    ("volume", {"volume_mmbtu_per_day": 1_000}),
    ("price", {"fixed_price": 3.223}),
    ("counterparty", {"counterparty_id": "CP05"}),
    ("delivery", {"delivery_start": pd.Timestamp("2026-05-01"), "delivery_end": pd.Timestamp("2026-05-31")}),
    ("side", {"their_side": "sell"}),
])
def test_each_difference_is_reported(field, change):
    r = matching.match(one_trade(), their_confirm(**change)).iloc[0]
    assert r["status"] == "break"
    assert r["differences"] == field


def test_missing_and_unknown():
    unrelated = their_confirm(counterparty_id="CP06", volume_mmbtu_per_day=2_500, fixed_price=9.0,
                              delivery_start=pd.Timestamp("2026-06-01"))
    r = matching.match(one_trade(), unrelated).set_index("status")
    assert "missing_confirm" in r.index and "unknown_trade" in r.index


def test_matcher_finds_planted_errors_on_a_full_book():
    days = pd.bdate_range("2025-01-02", "2025-12-31")
    futures = pd.DataFrame({"date": days, "close": 3.0 + (days.dayofyear % 30) / 100})
    trades = simulate.generate_trades(futures, start="2025-01-02", end="2025-12-31")
    confirms, key = confirmations.generate(trades, list(simulate.COUNTERPARTIES["counterparty_id"]))
    score = matching.score_against_key(matching.match(trades, confirms), key, trades).set_index("error")

    planted = score.drop(index="false alarms (clean trades flagged)")
    raised = planted["found"] + planted["found_on_identical_twin"]
    assert (raised == planted["planted"]).all()  # every planted problem is raised as an exception
    assert score.loc["false alarms (clean trades flagged)", "found"] == 0


def test_answer_key_counts_match_error_share():
    days = pd.bdate_range("2025-01-02", "2025-06-30")
    trades = simulate.generate_trades(pd.DataFrame({"date": days, "close": 3.0}), start="2025-01-02",
                                      end="2025-06-30")
    _, key = confirmations.generate(trades, list(simulate.COUNTERPARTIES["counterparty_id"]))
    assert (key["error"] != "unknown").sum() == round(len(trades) * confirmations.ERROR_SHARE)
