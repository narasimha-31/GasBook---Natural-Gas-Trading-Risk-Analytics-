"""Match our trades to counterparty confirmations and explain every difference.

There is no shared ID, so pairs are found by comparing details. Only trades and confirmations with the same
trade date are compared. Each candidate pair gets one point per field that agrees:

    counterparty, side (theirs must be the opposite of ours), delivery month, volume, price type, price

Pairs are accepted best-score-first if at least MIN_SCORE of the 6 fields agree, and each trade and each
confirmation is used once. Result statuses:

    matched          - every field agrees (prices within PRICE_TOLERANCE)
    break            - paired, but some fields differ (listed in `differences`)
    missing_confirm  - our trade has no confirmation
    unknown_trade    - a confirmation for a trade we never booked
"""

import pandas as pd

PRICE_TOLERANCE = 0.001  # $/MMBtu: confirmations round to 3 decimals
MIN_SCORE = 4
FIELDS = ["counterparty", "side", "delivery", "volume", "price_type", "price"]


def _field_checks(t, c) -> dict[str, bool]:
    if t.price_type == c.price_type == "fixed":
        price_ok = abs(t.fixed_price - c.fixed_price) <= PRICE_TOLERANCE
    elif t.price_type == c.price_type == "index":
        price_ok = abs(t.index_adder - c.index_adder) <= PRICE_TOLERANCE
    else:
        price_ok = False
    return {
        "counterparty": t.counterparty_id == c.counterparty_id,
        "side": t.buy_sell != c.their_side,
        "delivery": t.delivery_start == c.delivery_start,
        "volume": t.volume_mmbtu_per_day == c.volume_mmbtu_per_day,
        "price_type": t.price_type == c.price_type,
        "price": price_ok,
    }


def match(trades: pd.DataFrame, confirms: pd.DataFrame) -> pd.DataFrame:
    candidates = []
    conf_by_day = {d: g for d, g in confirms.groupby("trade_date")}
    for t in trades.itertuples(index=False):
        day = conf_by_day.get(t.trade_date)
        if day is None:
            continue
        for c in day.itertuples(index=False):
            checks = _field_checks(t, c)
            score = sum(checks.values())
            if score >= MIN_SCORE:
                candidates.append((score, t.trade_id, c.confirm_ref, checks))

    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    used_t, used_c, rows = set(), set(), []
    for score, tid, cref, checks in candidates:
        if tid in used_t or cref in used_c:
            continue
        used_t.add(tid)
        used_c.add(cref)
        diffs = [f for f in FIELDS if not checks[f]]
        rows.append({"trade_id": tid, "confirm_ref": cref, "status": "break" if diffs else "matched",
                     "differences": ", ".join(diffs), "score": score})

    for tid in trades.loc[~trades["trade_id"].isin(used_t), "trade_id"]:
        rows.append({"trade_id": tid, "confirm_ref": None, "status": "missing_confirm", "differences": "",
                     "score": 0})
    for cref in confirms.loc[~confirms["confirm_ref"].isin(used_c), "confirm_ref"]:
        rows.append({"trade_id": None, "confirm_ref": cref, "status": "unknown_trade", "differences": "",
                     "score": 0})
    return pd.DataFrame(rows)


TWIN_FIELDS = ["trade_date", "counterparty_id", "buy_sell", "delivery_start", "price_type", "fixed_price",
               "index_adder"]


def _twin_key(row) -> tuple:
    return tuple(None if pd.isna(row[f]) else row[f] for f in TWIN_FIELDS)


def score_against_key(results: pd.DataFrame, key: pd.DataFrame, trades: pd.DataFrame | None = None) -> pd.DataFrame:
    """How many planted errors the matcher found, by error type, and how many clean trades it wrongly flagged.

    If `trades` is given, an error flagged on an identical twin trade (same day, counterparty, side, delivery,
    price) is counted separately: without a shared ID the two cannot be told apart, so the problem was still
    raised, just on the other trade.
    """
    expected_status = {"volume": "break", "price": "break", "counterparty": "break", "delivery": "break",
                       "missing": "missing_confirm"}
    field_for = {"volume": "volume", "price": "price", "counterparty": "counterparty", "delivery": "delivery"}
    by_trade = results.dropna(subset=["trade_id"]).set_index("trade_id")
    planted_ids = set(key["trade_id"].dropna())
    false_alarms = by_trade[(by_trade["status"] != "matched") & (~by_trade.index.isin(planted_ids))]
    twin_of = {}
    if trades is not None:
        t = trades.set_index("trade_id")
        alarm_keys = {_twin_key(t.loc[tid]): tid for tid in false_alarms.index}
        twin_of = {tid: alarm_keys.get(_twin_key(t.loc[tid])) for tid in planted_ids}
    used_twins = set()

    rows = []
    for error, grp in key[key["error"] != "unknown"].groupby("error"):
        found = on_twin = 0
        for tid in grp["trade_id"]:
            r = by_trade.loc[tid]
            ok = r["status"] == expected_status[error]
            if ok and error in field_for:
                ok = field_for[error] in r["differences"].split(", ")
            if ok:
                found += 1
            elif twin_of.get(tid) and twin_of[tid] not in used_twins:
                on_twin += 1
                used_twins.add(twin_of[tid])
        rows.append({"error": error, "planted": len(grp), "found": found, "found_on_identical_twin": on_twin})
    n_unknown = int((key["error"] == "unknown").sum())
    rows.append({"error": "unknown", "planted": n_unknown,
                 "found": min(n_unknown, int((results["status"] == "unknown_trade").sum())),
                 "found_on_identical_twin": 0})
    rows.append({"error": "false alarms (clean trades flagged)", "planted": 0,
                 "found": len(false_alarms) - len(used_twins), "found_on_identical_twin": 0})
    return pd.DataFrame(rows)
