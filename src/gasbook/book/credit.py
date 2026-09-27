"""Counterparty credit exposure for the physical book.

Exposure to a counterparty on a given day (NAESB Base Contract with netting):

    unpaid_sales     = gas we delivered to them that they have not paid for yet
    unpaid_purchases = gas they delivered to us that we have not paid for yet
    future_value     = value to us of deliveries still to come (what we lose if they default and we replace them)
    exposure         = max(0, unpaid_sales - unpaid_purchases + future_value)

Payment: each delivery month is invoiced and paid on the 25th of the following month, so up to ~55 days of gas
can be owed at once. In a price spike, index-priced sales bill at the spot price, so what customers owe jumps.

Late payers: some counterparties pay a few days after the 25th (payment_delay_days), which keeps their unpaid
gas on our books longer. We always pay on time.

Default: if a counterparty defaults, all its deals are terminated on the default date (NAESB Section 10).
Loss = max(0, unpaid_sales - unpaid_purchases + future_value) on that date, assuming nothing is recovered.
From then on its exposure is frozen at that loss and its alert is "defaulted".

Limits: amber at 75% of the credit limit, red at 100%. Counterparties in "commissioning" or "disputed" status
get half their normal limit (lesson from the Venture Global vs BP commissioning-cargo dispute).
"""

import pandas as pd

from gasbook.book.pnl import Marks

AMBER, RED = 0.75, 1.00
RESTRICTED_STATUS = {"commissioning": 0.5, "disputed": 0.5}


def payment_date(delivery_start: pd.Timestamp, delay_days: int = 0) -> pd.Timestamp:
    """25th of the month after the delivery month, plus any days the counterparty usually pays late."""
    return delivery_start + pd.offsets.MonthBegin(1) + pd.Timedelta(days=24 + delay_days)


def trade_credit_parts(t, marks: Marks, day: pd.Timestamp, delay_days: int = 0) -> tuple[float, float, float]:
    """(unpaid_sales, unpaid_purchases, future_value) for one trade on `day`.

    `delay_days` = how late this counterparty pays us (applies to our sales only; we pay on time).
    """
    start, end = t.delivery_start, t.delivery_end
    vol = t.volume_mmbtu_per_day
    sign = 1 if t.buy_sell == "buy" else -1

    # Billed amount for days already delivered (only unpaid if the payment date is still ahead)
    billed = 0.0
    due = payment_date(start, delay_days if sign == -1 else 0)
    if day >= start and day < due:
        last = min(day, end)
        n = (last - start).days + 1
        if t.price_type == "fixed":
            billed = n * vol * t.fixed_price
        else:
            billed = vol * (marks.spot_sum(start, last) + n * t.index_adder)

    # Value of deliveries still to come
    future = 0.0
    if t.price_type == "fixed":
        if day < start:
            future = sign * vol * ((end - start).days + 1) * (marks.forward(start, day) - t.fixed_price)
        elif day < end:
            future = sign * vol * (end - day).days * (marks.spot(day) - t.fixed_price)
    else:
        remaining = (end - start).days + 1 if day < start else max((end - day).days, 0)
        future = -sign * t.index_adder * vol * remaining

    unpaid_sales = billed if sign == -1 else 0.0
    unpaid_purchases = billed if sign == 1 else 0.0
    return unpaid_sales, unpaid_purchases, future


def _delays(counterparties: pd.DataFrame) -> dict[str, int]:
    if "payment_delay_days" not in counterparties:
        return {}
    return counterparties.set_index("counterparty_id")["payment_delay_days"].fillna(0).astype(int).to_dict()


def _parts(trades: pd.DataFrame, marks: Marks, day: pd.Timestamp, delays: dict[str, int]) -> dict:
    parts = {}
    for t in trades[trades["trade_date"] <= day].itertuples(index=False):
        s, p, f = trade_credit_parts(t, marks, day, delays.get(t.counterparty_id, 0))
        acc = parts.setdefault(t.counterparty_id, [0.0, 0.0, 0.0])
        acc[0] += s
        acc[1] += p
        acc[2] += f
    return parts


def default_settlement(trades: pd.DataFrame, counterparties: pd.DataFrame, marks: Marks, counterparty_id: str,
                       default_date: pd.Timestamp) -> dict:
    """Termination on default: what they owed us, what we owed them, replacement cost, and the net loss."""
    book = trades[trades["counterparty_id"] == counterparty_id]
    s, p, f = _parts(book, marks, default_date, _delays(counterparties)).get(counterparty_id, [0.0, 0.0, 0.0])
    return {"counterparty_id": counterparty_id, "default_date": default_date, "unpaid_sales": s,
            "unpaid_purchases": p, "future_value": f, "net_settlement": s - p + f, "loss": max(0.0, s - p + f),
            "loss_without_setoff": max(0.0, s + f)}


def exposures(trades: pd.DataFrame, counterparties: pd.DataFrame, marks: Marks, day: pd.Timestamp) -> pd.DataFrame:
    """Exposure, effective limit, utilization and alert per counterparty on `day`."""
    parts = _parts(trades, marks, day, _delays(counterparties))
    cp = counterparties.set_index("counterparty_id")
    rows = []
    for cid, row in cp.iterrows():
        s, p, f = parts.get(cid, [0.0, 0.0, 0.0])
        limit = float(row["credit_limit_usd"]) * RESTRICTED_STATUS.get(row["status"], 1.0)
        default_date = row.get("default_date")
        defaulted = pd.notna(default_date) and day >= pd.Timestamp(default_date)
        if defaulted:
            d = default_settlement(trades, counterparties.reset_index(drop=True), marks, cid, pd.Timestamp(default_date))
            s, p, f, exposure = d["unpaid_sales"], d["unpaid_purchases"], d["future_value"], d["loss"]
        else:
            exposure = max(0.0, s - p + f)
        util = exposure / limit if limit else float("inf")
        alert = "defaulted" if defaulted else "red" if util >= RED else "amber" if util >= AMBER else "green"
        rows.append({
            "date": day, "counterparty_id": cid, "name": row["name"], "status": row["status"],
            "unpaid_sales": s, "unpaid_purchases": p, "future_value": f, "exposure": exposure,
            "credit_limit": float(row["credit_limit_usd"]), "effective_limit": limit, "utilization": util,
            "alert": alert,
        })
    return pd.DataFrame(rows)


def exposure_history(trades, counterparties, marks, days) -> pd.DataFrame:
    return pd.concat([exposures(trades, counterparties, marks, d) for d in days], ignore_index=True)
