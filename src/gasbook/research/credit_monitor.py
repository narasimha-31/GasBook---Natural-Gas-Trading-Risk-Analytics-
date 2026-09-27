"""Daily counterparty credit exposure vs limits for the simulated book, read from the PostgreSQL trade database.

Run: python -m gasbook.research.credit_monitor   (needs: python -m gasbook.book.database)
Outputs: reports/credit_exposure_daily.csv, reports/credit_breaches.csv, reports/credit_latest.csv,
         reports/credit_monitor.png
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy import create_engine

from gasbook.book import credit, pnl
from gasbook.book.database import connection_url
from gasbook.config import ROOT

REPORTS = ROOT / "reports"
STORM = ("2026-01-20", "2026-01-30")


def breach_episodes(history: pd.DataFrame, level: str = "red") -> pd.DataFrame:
    """Continuous runs of days a counterparty was at or above an alert level."""
    flagged = history["alert"].eq(level) if level == "red" else history["alert"].isin(["amber", "red"])
    rows = []
    for cid, g in history.assign(flag=flagged).groupby("counterparty_id"):
        g = g.sort_values("date")
        run_id = (g["flag"] != g["flag"].shift()).cumsum()
        for _, run in g[g["flag"]].groupby(run_id[g["flag"]]):
            peak = run.loc[run["utilization"].idxmax()]
            rows.append({
                "counterparty_id": cid, "name": peak["name"], "level": level,
                "first_day": run["date"].min().date(), "last_day": run["date"].max().date(),
                "trading_days": len(run), "peak_day": peak["date"].date(),
                "peak_exposure": peak["exposure"], "effective_limit": peak["effective_limit"],
                "peak_utilization": peak["utilization"],
            })
    return pd.DataFrame(rows).sort_values("first_day") if rows else pd.DataFrame(rows)


def plot(history: pd.DataFrame, path) -> None:
    util = history.pivot(index="date", columns="name", values="utilization") * 100
    fig, ax = plt.subplots(figsize=(12, 6))
    for name in util:
        ax.plot(util.index, util[name], lw=1, label=name)
    ax.axhline(75, color="orange", ls="--", lw=1, label="Amber (75%)")
    ax.axhline(100, color="red", ls="--", lw=1, label="Red (100% of limit)")
    ax.axvspan(pd.Timestamp(STORM[0]), pd.Timestamp(STORM[1]), color="orange", alpha=0.2)
    ax.set_ylabel("Credit limit used (%)")
    ax.set_title("Counterparty credit exposure vs limit (simulated book, real prices; storm shaded)")
    ax.legend(fontsize=7, ncol=2, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    engine = create_engine(connection_url())
    trades, marks = pnl.load_from_database(engine)
    cps = pd.read_sql("SELECT counterparty_id, name, status, credit_limit_usd, payment_delay_days, default_date "
                      "FROM counterparties", engine, parse_dates=["default_date"])
    cps["credit_limit_usd"] = cps["credit_limit_usd"].astype(float)

    last = min(marks.futures.index.max(), marks.spot_daily.index.max())
    days = marks.futures.loc[trades["trade_date"].min():last].index
    history = credit.exposure_history(trades, cps, marks, days)
    red = breach_episodes(history, "red")
    amber = breach_episodes(history, "amber")
    latest = history[history["date"] == days[-1]].sort_values("utilization", ascending=False)

    REPORTS.mkdir(exist_ok=True)
    history.round(4).to_csv(REPORTS / "credit_exposure_daily.csv", index=False)
    pd.concat([red, amber]).round(4).to_csv(REPORTS / "credit_breaches.csv", index=False)
    latest.round(4).to_csv(REPORTS / "credit_latest.csv", index=False)
    plot(history, REPORTS / "credit_monitor.png")

    pd.set_option("display.width", 220)
    print(f"Credit monitor {days[0].date()} -> {days[-1].date()}\n")
    print("Red (over limit) episodes:")
    print(red.round(2).to_string(index=False) if len(red) else "  none")
    print("\nAmber-or-worse episodes:")
    print(amber.round(2).to_string(index=False) if len(amber) else "  none")
    storm = history[(history["date"] >= STORM[0]) & (history["date"] <= "2026-02-27")]
    peak = storm.loc[storm.groupby("name")["utilization"].idxmax()]
    print("\nPeak utilization during and after Winter Storm Fern (to end of Feb):")
    print(peak[["name", "date", "unpaid_sales", "future_value", "exposure", "effective_limit", "utilization",
                "alert"]].round(2).to_string(index=False))
    print(f"\nLatest ({days[-1].date()}):")
    print(latest[["name", "exposure", "effective_limit", "utilization", "alert"]].round(2).to_string(index=False))
