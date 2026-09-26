"""Historical storm replays on today's book.

A scenario takes a real storm's day-by-day percentage price moves (spot and front-month futures) and applies
them on top of today's prices, starting the next business day. Futures moves on contract-roll days are removed,
so a switch to the next contract is not mistaken for a storm move. After the storm window, prices stay at the
storm's final level until a chosen horizon (e.g. just past the next payment date, to capture the credit peak).

This is a what-if on the current book, not a forecast. No new trades are added during the scenario.
"""

import numpy as np
import pandas as pd

from gasbook.book import credit, pnl
from gasbook.ingest.futures import near_expiry

# Windows start the business day before the first big move so the replay begins from calm prices.
STORMS = {
    "Winter Storm Uri (Feb 2021)": ("2021-02-05", "2021-02-26"),
    "Winter Storm Elliott (Dec 2022)": ("2022-12-16", "2023-01-06"),
    "Jan 2024 arctic blast": ("2024-01-05", "2024-01-26"),
    "Jan 2025 cold snap": ("2025-01-10", "2025-01-31"),
    "Winter Storm Fern (Jan 2026)": ("2026-01-16", "2026-02-06"),
}


def storm_ratios(spot: pd.Series, futures: pd.Series, start: str, end: str) -> pd.DataFrame:
    """Cumulative price ratio vs the first day of the window, per trading day, for spot and futures.

    Futures roll days (expiry day and the day after) get a 0% move.
    """
    days = futures.loc[start:end].index
    s = spot.reindex(days).ffill()
    f_ret = np.log(futures).diff().loc[days]
    roll = near_expiry(pd.Series(days, index=days), before_bdays=0, after_bdays=1)
    f_ret = f_ret.where(~roll, 0.0).fillna(0.0)
    f_ret.iloc[0] = 0.0
    return pd.DataFrame({"spot_ratio": s / s.iloc[0], "futures_ratio": np.exp(f_ret.cumsum())}, index=days)


def shocked_marks(marks: pnl.Marks, today: pd.Timestamp, ratios: pd.DataFrame,
                  horizon: pd.Timestamp) -> tuple[pnl.Marks, pd.DatetimeIndex]:
    """Price history up to `today`, followed by the storm path applied to today's prices, held flat to `horizon`."""
    spot_today = marks.spot(today)
    fut_today = float(marks.futures.loc[:today].iloc[-1])
    scen_days = pd.bdate_range(today + pd.offsets.BDay(1), horizon)
    path = ratios.iloc[1:].reset_index(drop=True)  # day 0 of the window = today
    idx = np.minimum(np.arange(len(scen_days)), len(path) - 1)  # after the storm, hold the final level
    new_spot = pd.Series(spot_today * path["spot_ratio"].to_numpy()[idx], index=scen_days)
    new_fut = pd.Series(fut_today * path["futures_ratio"].to_numpy()[idx], index=scen_days)
    spot_hist = marks.spot_daily.loc[:today]
    spot_hist = spot_hist[spot_hist.index.dayofweek < 5]
    fut_hist = marks.futures.loc[:today]
    return pnl.Marks(pd.concat([spot_hist, new_spot]), pd.concat([fut_hist, new_fut])), scen_days


def run_scenario(trades, counterparties, marks, today, ratios, horizon) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Daily book value and credit exposures through the scenario for trades done on or before `today`."""
    book = trades[trades["trade_date"] <= today]
    m, days = shocked_marks(marks, today, ratios, horizon)
    base = pnl.trade_values(book, m, today)["value"].sum()
    rows, exp = [], []
    for d in days:
        rows.append({"date": d, "pnl_vs_today": pnl.trade_values(book, m, d)["value"].sum() - base,
                     "spot": m.spot(d), "futures": float(m.futures.loc[:d].iloc[-1])})
        exp.append(credit.exposures(book, counterparties, m, d))
    return pd.DataFrame(rows), pd.concat(exp, ignore_index=True)
