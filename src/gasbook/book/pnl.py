"""Mark-to-market P&L for the physical book, and a daily P&L explain.

Sign convention: buy = +1, sell = -1. Trade value = sign x volume x (market price - contract price).

Marks (all real prices):
- Before the delivery month: NYMEX front-month futures close. After that contract expires (3 business days
  before the month starts), its final settlement price is used until delivery begins.
- During the delivery month: days that have flowed settle at the EIA Henry Hub daily spot price (weekends and
  holidays carry the last traded price); the rest of the month is marked at the latest spot price.
- After the month ends: fully settled, the value no longer changes.
- Index deals: contract price = spot + adder, so the value is just the locked-in adder margin: -sign x adder x volume.

Daily P&L explain (sums exactly to the change in total MTM):
- new_deals: value on the trade date of deals done that day (dealer margin captured).
- forward_price_move: existing fixed-price deals not yet in delivery x change in their forward mark.
- delivery_and_spot: everything else (spot moves on deals in delivery, switching from futures to spot marks).
"""

import pandas as pd


class Marks:
    """Price lookups built from the real price history."""

    def __init__(self, spot: pd.Series, futures: pd.Series):
        spot, futures = spot.sort_index(), futures.sort_index()
        days = pd.date_range(spot.index.min(), spot.index.max(), freq="D")
        self.spot_daily = spot.reindex(days).ffill()
        self.spot_cum = self.spot_daily.cumsum()
        self.futures = futures

    def spot(self, day: pd.Timestamp) -> float:
        return float(self.spot_daily.loc[:day].iloc[-1])

    def spot_sum(self, start: pd.Timestamp, end: pd.Timestamp) -> float:
        """Sum of daily spot prices from start to end inclusive."""
        before = self.spot_cum.loc[: start - pd.Timedelta(days=1)]
        return float(self.spot_cum.loc[:end].iloc[-1] - (before.iloc[-1] if len(before) else 0.0))

    def forward(self, month_start: pd.Timestamp, day: pd.Timestamp) -> float:
        """Futures mark for a delivery month on a given day (final settlement once the contract has expired)."""
        expiry = month_start - pd.offsets.BDay(3)
        return float(self.futures.loc[: min(day, expiry)].iloc[-1])


def trade_values(trades: pd.DataFrame, marks: Marks, day: pd.Timestamp) -> pd.DataFrame:
    """Value of every trade done on or before `day`, with the forward exposure used by the P&L explain."""
    book = trades[trades["trade_date"] <= day]
    rows = []
    for t in book.itertuples(index=False):
        sign = 1 if t.buy_sell == "buy" else -1
        start, end = t.delivery_start, t.delivery_end
        n_days = (end - start).days + 1
        vol = t.volume_mmbtu_per_day
        forward_qty = 0.0  # MMBtu still priced off futures (drives forward_price_move)

        if t.price_type == "index":
            value = -sign * t.index_adder * vol * n_days
        elif day < start:
            value = sign * vol * n_days * (marks.forward(start, day) - t.fixed_price)
            forward_qty = sign * vol * n_days
        elif day <= end:
            flowed = marks.spot_sum(start, day)
            remaining = (end - day).days * marks.spot(day)
            value = sign * vol * (flowed + remaining - n_days * t.fixed_price)
        else:
            value = sign * vol * (marks.spot_sum(start, end) - n_days * t.fixed_price)

        rows.append({"trade_id": t.trade_id, "counterparty_id": t.counterparty_id, "delivery_start": start,
                     "value": value, "forward_qty": forward_qty})
    return pd.DataFrame(rows, columns=["trade_id", "counterparty_id", "delivery_start", "value", "forward_qty"])


def daily_pnl(trades: pd.DataFrame, marks: Marks, days: pd.DatetimeIndex) -> pd.DataFrame:
    """Total MTM per day and the P&L explain. `days` must be consecutive business days."""
    out, prev = [], None
    for day in days:
        vals = trade_values(trades, marks, day)
        total = vals["value"].sum()
        row = {"date": day, "mtm_total": total}
        if prev is not None:
            new_ids = set(trades.loc[trades["trade_date"] == day, "trade_id"])
            new_deals = vals.loc[vals["trade_id"].isin(new_ids), "value"].sum()
            # Forward price move on deals that were forward yesterday and are still forward today
            p = prev.set_index("trade_id")
            fwd = p[p["forward_qty"] != 0]
            move = 0.0
            for month, grp in fwd.groupby("delivery_start"):
                if day < month:
                    move += grp["forward_qty"].sum() * (marks.forward(month, day) - marks.forward(month, prev_day))
            row["pnl"] = total - prev["value"].sum()
            row["new_deals"] = new_deals
            row["forward_price_move"] = move
            row["delivery_and_spot"] = row["pnl"] - new_deals - move
        out.append(row)
        prev, prev_day = vals, day
    return pd.DataFrame(out)


def load_from_database(engine) -> tuple[pd.DataFrame, Marks]:
    """Read trades and prices from the PostgreSQL trade database."""
    trades = pd.read_sql(
        "SELECT trade_id, trade_date, counterparty_id, buy_sell, delivery_start, delivery_end, "
        "volume_mmbtu_per_day, price_type, fixed_price, index_adder FROM trades ORDER BY trade_date, trade_id",
        engine, parse_dates=["trade_date", "delivery_start", "delivery_end"],
    )
    for col in ("fixed_price", "index_adder"):
        trades[col] = trades[col].astype(float)
    prices = pd.read_sql("SELECT price_date, series, price FROM prices", engine, parse_dates=["price_date"])
    prices["price"] = prices["price"].astype(float)
    wide = prices.pivot(index="price_date", columns="series", values="price")
    return trades, Marks(wide["henry_hub_spot"].dropna(), wide["ng_front_month"].dropna())
