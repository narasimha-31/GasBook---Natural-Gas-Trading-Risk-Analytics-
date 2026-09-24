"""Q1: Does the standard risk number (VaR) work for natural gas?

Backtests four 1-day 99% VaR models on real Henry Hub daily spot prices (EIA, 1997-today),
for both a long desk (loses when prices fall) and a short desk (loses in a spike, like a marketer
that sold fixed-price gas to customers). Also zooms in on five cold-weather price spikes (2021-2026).

Run: python -m gasbook.research.q1_var_backtest
Outputs (committed so results are visible on GitHub): reports/q1_*.csv, reports/q1_var_backtest.png
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from gasbook.config import DATA_RAW, ROOT
from gasbook.risk import var

LEVEL = 0.99
WINDOW = 250  # about one trading year
POSITION_USD = 1_000_000  # express % losses per $1M of gas position

REPORTS = ROOT / "reports"

# Cold-weather events. Windows cover the spike and the crash after it.
# Jan 2024 and Jan 2025 spikes were Friday trades priced for long Martin Luther King holiday weekends.
EVENTS = {
    "Winter Storm Uri (Feb 2021)": ("2021-02-08", "2021-02-26"),
    "Winter Storm Elliott (Dec 2022)": ("2022-12-19", "2023-01-06"),
    "Jan 2024 arctic blast": ("2024-01-08", "2024-01-26"),
    "Jan 2025 cold snap": ("2025-01-13", "2025-01-31"),
    "Winter Storm Fern (Jan 2026)": ("2026-01-19", "2026-02-06"),
}

SIDES = {"long": 1, "short": -1}


def forecasts(returns: pd.Series, side: int) -> dict[str, pd.Series]:
    loss = var.losses(returns, side)
    return {
        "Normal (textbook)": var.var_normal(loss, WINDOW, LEVEL),
        "Historical simulation": var.var_historical(loss, WINDOW, LEVEL),
        "EWMA (RiskMetrics)": var.var_ewma(returns, side, LEVEL),
        "Filtered historical": var.var_filtered_hs(returns, side, WINDOW, LEVEL),
    }


def run(prices: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    returns = var.log_returns(prices)
    summary, storms, series = [], [], {}

    for side_name, side in SIDES.items():
        loss = var.losses(returns, side)
        for model, fc in forecasts(returns, side).items():
            series[(side_name, model)] = (loss, fc)
            res = var.backtest(loss, fc, LEVEL)
            summary.append({"side": side_name, "model": model, **res})

            for event, (start, end) in EVENTS.items():
                w = pd.concat({"loss": loss, "var": fc}, axis=1).loc[start:end].dropna()
                breach = w["loss"] > w["var"]
                worst_day = w["loss"].idxmax()
                worst_pct = var.to_pct_loss(w.loc[worst_day, "loss"], side)
                var_pct = var.to_pct_loss(w.loc[worst_day, "var"], side)
                storms.append({
                    "side": side_name,
                    "model": model,
                    "event": event,
                    "trading_days": len(w),
                    "breaches": int(breach.sum()),
                    "worst_day": worst_day.date(),
                    "worst_loss_pct": worst_pct,
                    "var_that_day_pct": var_pct,
                    "worst_loss_per_1m_usd": worst_pct * POSITION_USD,
                    "var_that_day_per_1m_usd": var_pct * POSITION_USD,
                    "loss_to_var_ratio": worst_pct / var_pct,
                })

    return pd.DataFrame(summary), pd.DataFrame(storms), series


def plot(series: dict, path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    for ax, (side, sign) in zip(axes, SIDES.items()):
        loss, _ = series[(side, "Normal (textbook)")]
        recent = loss.loc["2020-06-01":]
        actual = var.to_pct_loss(recent, sign).clip(lower=0) * 100
        ax.plot(recent.index, actual, color="0.6", lw=0.7, label="Actual daily loss (gains hidden)")
        for model, color in (("Normal (textbook)", "tab:red"), ("Filtered historical", "tab:blue")):
            _, fc = series[(side, model)]
            ax.plot(recent.index, var.to_pct_loss(fc.loc[recent.index], sign) * 100, color=color, lw=1.2,
                    label=f"99% VaR: {model}")
        for start, end in EVENTS.values():
            ax.axvspan(pd.Timestamp(start), pd.Timestamp(end), color="orange", alpha=0.2)
        ax.set_title(f"{side.capitalize()} Henry Hub position: daily loss vs 99% VaR (cold-weather events shaded)")
        ax.set_ylabel("% of position")
        ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    hh = pd.read_csv(DATA_RAW / "henry_hub_daily.csv", parse_dates=["date"]).set_index("date")["henry_hub"]
    summary, storms, series = run(hh)

    REPORTS.mkdir(exist_ok=True)
    summary.round(4).to_csv(REPORTS / "q1_var_backtest_summary.csv", index=False)
    storms.round(4).to_csv(REPORTS / "q1_var_storm_windows.csv", index=False)
    plot(series, REPORTS / "q1_var_backtest.png")

    pd.set_option("display.width", 200)
    print(f"Henry Hub {hh.index.min().date()} -> {hh.index.max().date()}, 1-day {LEVEL:.0%} VaR, {WINDOW}-day window\n")
    print(summary[["side", "model", "days", "breaches", "expected", "breach_rate", "kupiec_p", "independence_p"]]
          .round(4).to_string(index=False))
    print()
    print(storms[["side", "model", "event", "breaches", "worst_day", "worst_loss_per_1m_usd",
                  "var_that_day_per_1m_usd"]].round(0).to_string(index=False))
