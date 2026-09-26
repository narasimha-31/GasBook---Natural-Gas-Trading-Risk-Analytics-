"""Counterparty credit exposure for the physical book.

Exposure to a counterparty on a given day (NAESB Base Contract with netting):

    unpaid_sales     = gas we delivered to them that they have not paid for yet
    unpaid_purchases = gas they delivered to us that we have not paid for yet
    future_value     = value to us of deliveries still to come (what we lose if they default and we replace them)
    exposure         = max(0, unpaid_sales - unpaid_purchases + future_value)

Payment: each delivery month is invoiced and paid on the 25th of the following month, so up to ~55 days of gas
can be owed at once. In a price spike, index-priced sales bill at the spot price, so what customers owe jumps.

Limits: amber at 75% of the credit limit, red at 100%. Counterparties in "commissioning" or "disputed" status
get half their normal limit (lesson from the Venture Global vs BP commissioning-cargo dispute).
"""

import pandas as pd

from gasbook.book.pnl import Marks

AMBER, RED = 0.75, 1.00
RESTRICTED_STATUS = {"commissioning": 0.5, "disputed": 0.5}


def payment_date(delivery_start: pd.Timestamp) -> pd.Timestamp:
    """25th of the month after the delivery month."""
    return delivery_start + pd.offsets.MonthBegin(1) + pd.Timedelta(days=24)


def trade_credit_parts(t, marks: Marks, day: pd.Timestamp) -> tuple[float, float, float]:
    """(unpaid_sales, unpaid_purchases, future_value) for one trade on `day`."""
    start, end = t.delivery_start, t.delivery_end
    vol = t.volume_mmbtu_per_day
    sign = 1 if t.buy_sell == "buy" else -1

    # Billed amount for days already delivered (only unpaid if the payment date is still ahead)
    billed = 0.0
    if day >= start and day < payment_date(start):
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


def exposures(trades: pd.DataFrame, counterparties: pd.DataFrame, marks: Marks, day: pd.Timestamp) -> pd.DataFrame:
    """Exposure, effective limit, utilization and alert per counterparty on `day`."""
    book = trades[trades["trade_date"] <= day]
    parts = {}
    for t in book.itertuples(index=False):
        s, p, f = trade_credit_parts(t, marks, day)
        acc = parts.setdefault(t.counterparty_id, [0.0, 0.0, 0.0])
        acc[0] += s
        acc[1] += p
        acc[2] += f

    cp = counterparties.set_index("counterparty_id")
    rows = []
    for cid, row in cp.iterrows():
        s, p, f = parts.get(cid, [0.0, 0.0, 0.0])
        limit = float(row["credit_limit_usd"]) * RESTRICTED_STATUS.get(row["status"], 1.0)
        exposure = max(0.0, s - p + f)
        util = exposure / limit if limit else float("inf")
        rows.append({
            "date": day, "counterparty_id": cid, "name": row["name"], "status": row["status"],
            "unpaid_sales": s, "unpaid_purchases": p, "future_value": f, "exposure": exposure,
            "credit_limit": float(row["credit_limit_usd"]), "effective_limit": limit, "utilization": util,
            "alert": "red" if util >= RED else "amber" if util >= AMBER else "green",
        })
    return pd.DataFrame(rows)


def exposure_history(trades, counterparties, marks, days) -> pd.DataFrame:
    return pd.concat([exposures(trades, counterparties, marks, d) for d in days], ignore_index=True)
