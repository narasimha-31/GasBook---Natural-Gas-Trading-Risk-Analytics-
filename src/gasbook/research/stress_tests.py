"""Replay five real storms on today's simulated book: P&L hit and credit limit breaches.

Each storm's real day-by-day % price moves (spot and futures, roll jumps removed) start the day after the
valuation date. Prices then hold at the storm's final level until just after the next payment date, so the
credit peak (unpaid storm-priced gas) is captured.

Run: python -m gasbook.research.stress_tests   (needs: python -m gasbook.book.database)
Outputs: reports/stress_summary.csv, reports/stress_credit.csv, reports/stress_tests.png
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy import create_engine

from gasbook.book import credit, pnl, stress
from gasbook.book.database import connection_url
from gasbook.config import DATA_RAW, ROOT

REPORTS = ROOT / "reports"


def full_history() -> tuple[pd.Series, pd.Series]:
    """Storm windows go back to 2021, before the book starts, so read the full price history from the raw files."""
    spot = pd.read_csv(DATA_RAW / "henry_hub_daily.csv", parse_dates=["date"]).set_index("date")["henry_hub"]
    fut = pd.read_csv(DATA_RAW / "ng_front_month.csv", parse_dates=["date"]).set_index("date")["close"]
    return spot, fut


if __name__ == "__main__":
    engine = create_engine(connection_url())
    trades, marks = pnl.load_from_database(engine)
    cps = pd.read_sql("SELECT counterparty_id, name, status, credit_limit_usd FROM counterparties", engine)
    cps["credit_limit_usd"] = cps["credit_limit_usd"].astype(float)

    today = min(marks.futures.index.max(), marks.spot_daily.index.max())
    # Run until the day after next month's deliveries are paid, so storm-priced deliveries are fully billed and owed
    next_month = today + pd.offsets.MonthBegin(1)
    horizon = credit.payment_date(next_month) + pd.Timedelta(days=1)
    base_exp = credit.exposures(trades, cps, marks, today).set_index("name")

    spot_hist, fut_hist = full_history()
    summary, credit_rows, paths = [], [], {}
    for name, (start, end) in stress.STORMS.items():
        ratios = stress.storm_ratios(spot_hist, fut_hist, start, end)
        path, exp = stress.run_scenario(trades, cps, marks, today, ratios, horizon)
        paths[name] = path
        peak = exp.loc[exp.groupby("name")["utilization"].idxmax()].set_index("name")
        breached = peak[peak["alert"] == "red"]
        newly = [n for n in breached.index if base_exp.loc[n, "alert"] != "red"]
        summary.append({
            "storm": name,
            "peak_spot_multiple": ratios["spot_ratio"].max(),
            "worst_pnl": path["pnl_vs_today"].min(),
            "worst_pnl_day": path.loc[path["pnl_vs_today"].idxmin(), "date"].date(),
            "pnl_at_horizon": path["pnl_vs_today"].iloc[-1],
            "counterparties_over_limit": len(breached),
            "newly_over_limit": ", ".join(newly) if newly else "none",
            "total_peak_exposure": peak["exposure"].sum(),
        })
        for n, r in peak.iterrows():
            credit_rows.append({"storm": name, "name": n, "base_utilization": base_exp.loc[n, "utilization"],
                                "peak_utilization": r["utilization"], "peak_day": r["date"].date(),
                                "peak_exposure": r["exposure"], "effective_limit": r["effective_limit"],
                                "alert": r["alert"]})

    summary = pd.DataFrame(summary)
    credit_df = pd.DataFrame(credit_rows)
    REPORTS.mkdir(exist_ok=True)
    summary.round(2).to_csv(REPORTS / "stress_summary.csv", index=False)
    credit_df.round(4).to_csv(REPORTS / "stress_credit.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 5))
    for name, path in paths.items():
        ax.plot(path["date"], path["pnl_vs_today"] / 1e6, label=name)
    ax.axhline(0, color="k", lw=0.5)
    ax.set_ylabel("P&L vs today ($ millions)")
    ax.set_title(f"Today's book ({today.date()}) under five real storm price paths")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(REPORTS / "stress_tests.png", dpi=130)
    plt.close(fig)

    pd.set_option("display.width", 220)
    print(f"Valuation date {today.date()}, scenario horizon {horizon.date()}\n")
    print(summary.round(0).to_string(index=False))
    print("\nCredit utilization, today vs storm peak:")
    wide = credit_df.pivot(index="name", columns="storm", values="peak_utilization")
    wide.insert(0, "today", base_exp["utilization"])
    print((wide * 100).round(0).to_string())
