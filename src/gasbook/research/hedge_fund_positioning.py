"""When hedge funds crowd into one side of natural gas futures, does the price tend to reverse?

Positioning: CFTC managed-money net position as a share of open interest (NYMEX Henry Hub futures).
Crowded long  = net position in the top 10% of its own last 3 years (156 weeks, past data only).
Crowded short = bottom 10%. Thresholds are fixed in advance, not tuned.

Timing: positions are as of Tuesday but published Friday 3:30 pm ET, after futures settle, so the earliest
realistic entry is the next Monday's close. We measure the futures return over the following 4 weeks.

Contract rolls: NG=F jumps when it switches contracts. Daily returns on expiry day and the day after are set to 0,
which approximates rolling at no gain or loss. Futures data starts in 2010.

The sample is split into 2010-2017 and 2018-2026 to check whether a pattern holds up in later years.

Run: python -m gasbook.research.hedge_fund_positioning
Outputs: reports/positioning_*.csv, reports/positioning.png
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

from gasbook.config import DATA_RAW, ROOT
from gasbook.ingest.futures import near_expiry

REPORTS = ROOT / "reports"
LOOKBACK_WEEKS = 156
CROWDED = 0.10
HOLD_DAYS = 20  # about 4 weeks
PERIODS = {"2010-2017": ("2010-01-01", "2017-12-31"), "2018-2026": ("2018-01-01", "2026-12-31")}


def rolling_percentile(values: pd.Series, window: int = LOOKBACK_WEEKS) -> pd.Series:
    """Where this week's value ranks among the last `window` weeks (including this one), from 0 to 1."""
    return values.rolling(window).apply(lambda w: (w <= w[-1]).mean(), raw=True)


def daily_returns_ex_roll(futures: pd.DataFrame) -> pd.Series:
    f = futures.sort_values("date").set_index("date")["close"]
    r = np.log(f).diff()
    roll = near_expiry(pd.Series(r.index, index=r.index), before_bdays=0, after_bdays=1)
    return r.where(~roll, 0.0).dropna()


def signal_from_percentile(pct: pd.Series, crowded: float = CROWDED) -> pd.Series:
    """Contrarian position: +1 (buy) when funds are crowded short, -1 (sell) when crowded long, else 0."""
    sig = pd.Series(0, index=pct.index)
    sig[pct <= crowded] = 1
    sig[pct >= 1 - crowded] = -1
    return sig.where(pct.notna())


def build_weeks(cot: pd.DataFrame, futures: pd.DataFrame) -> pd.DataFrame:
    w = cot[["report_date", "mm_net_pct_oi"]].sort_values("report_date").reset_index(drop=True)
    w["percentile"] = rolling_percentile(w["mm_net_pct_oi"], LOOKBACK_WEEKS)
    w["signal"] = signal_from_percentile(w["percentile"], CROWDED)

    r = daily_returns_ex_roll(futures)
    cum = r.cumsum()
    dates = cum.index
    entry_target = w["report_date"] + pd.Timedelta(days=6)  # Tuesday -> following Monday
    pos = dates.searchsorted(entry_target)
    in_range = pos + HOLD_DAYS < len(dates)
    safe_pos = np.minimum(pos, len(dates) - 1)
    # Entry must be within a few days of the target: reports from before the futures data starts are dropped,
    # not pushed onto the first available date
    on_time = (dates[safe_pos] - entry_target.to_numpy()) <= pd.Timedelta(days=4)
    ok = in_range & on_time
    w = w[ok].copy()
    pos = pos[ok]
    w["entry_date"] = dates[pos]
    w["forward_return"] = cum.to_numpy()[pos + HOLD_DAYS] - cum.to_numpy()[pos]
    w["strategy_return"] = w["signal"] * w["forward_return"]
    return w.dropna(subset=["percentile"]).reset_index(drop=True)


def mean_test(x: pd.Series, lags: int = 4) -> tuple[float, float]:
    """Mean with Newey-West t-stat (4-week holding periods overlap week to week)."""
    if len(x) < 10:
        return np.nan, np.nan
    fit = sm.OLS(x.to_numpy(), np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return fit.tvalues[0], fit.pvalues[0]


def summarize(weeks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for period, (start, end) in PERIODS.items():
        p = weeks[(weeks["entry_date"] >= start) & (weeks["entry_date"] <= end)]
        for label, mask in (
            ("funds crowded long -> sell", p["signal"] == -1),
            ("funds crowded short -> buy", p["signal"] == 1),
            ("not crowded", p["signal"] == 0),
        ):
            sub = p[mask]
            trade = sub["strategy_return"] if label != "not crowded" else sub["forward_return"]
            t, pval = mean_test(trade)
            rows.append({
                "period": period,
                "situation": label,
                "weeks": len(sub),
                "avg_4wk_price_move_pct": sub["forward_return"].mean() * 100,
                "avg_trade_return_pct": trade.mean() * 100 if label != "not crowded" else np.nan,
                "win_rate": (trade > 0).mean() if label != "not crowded" else np.nan,
                "t_stat": t if label != "not crowded" else np.nan,
                "p_value": pval if label != "not crowded" else np.nan,
            })
    return pd.DataFrame(rows)


def plot(weeks: pd.DataFrame, cot: pd.DataFrame, path) -> None:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    c = cot.set_index("report_date")["mm_net_pct_oi"] * 100
    ax1.plot(c.index, c, color="0.3", lw=0.8)
    w = weeks.set_index("report_date")
    ax1.scatter(w.index[w["signal"] == -1], c.reindex(w.index[w["signal"] == -1]), color="tab:red", s=10,
                label="Crowded long (top 10% of last 3 yrs)")
    ax1.scatter(w.index[w["signal"] == 1], c.reindex(w.index[w["signal"] == 1]), color="tab:green", s=10,
                label="Crowded short (bottom 10%)")
    ax1.axhline(0, color="k", lw=0.5)
    ax1.set_ylabel("Net managed money, % of open interest")
    ax1.set_title("Hedge fund positioning in NYMEX natural gas futures (CFTC)")
    ax1.legend(fontsize=8)

    for period, (start, end) in PERIODS.items():
        p = w[(w["entry_date"] >= start) & (w["entry_date"] <= end)]
        trades = p["strategy_return"].where(p["signal"] != 0, 0.0)
        # Non-overlapping view: take every 4th week so each trade is counted once
        ax2.plot(p.index[::4], trades.iloc[::4].cumsum() * 100, label=f"Contrarian rule, {period}")
    ax2.axhline(0, color="k", lw=0.5)
    ax2.set_ylabel("Cumulative return (%), every 4th week")
    ax2.set_title("Contrarian rule: sell when funds crowded long, buy when crowded short, hold 4 weeks")
    ax2.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    cot = pd.read_csv(DATA_RAW / "cftc_natgas_positioning.csv", parse_dates=["report_date"])
    futures = pd.read_csv(DATA_RAW / "ng_front_month.csv", parse_dates=["date"])
    weeks = build_weeks(cot, futures)
    summary = summarize(weeks)

    REPORTS.mkdir(exist_ok=True)
    weeks.to_csv(REPORTS / "positioning_weeks.csv", index=False)
    summary.round(4).to_csv(REPORTS / "positioning_summary.csv", index=False)
    plot(weeks, cot, REPORTS / "positioning.png")

    pd.set_option("display.width", 200)
    print(f"{len(weeks)} weeks with a signal, entries {weeks['entry_date'].min().date()} -> "
          f"{weeks['entry_date'].max().date()}\n")
    print(summary.round(3).to_string(index=False))
