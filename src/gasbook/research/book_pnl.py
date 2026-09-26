"""Daily mark-to-market P&L and P&L explain for the simulated book, read from the PostgreSQL trade database.

Run: python -m gasbook.research.book_pnl   (needs the database loaded: python -m gasbook.book.database)
Outputs: reports/book_pnl_daily.csv, reports/book_pnl_by_counterparty.csv, reports/book_pnl.png
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy import create_engine

from gasbook.book import pnl
from gasbook.book.database import connection_url
from gasbook.config import ROOT

REPORTS = ROOT / "reports"
STORM = ("2026-01-20", "2026-01-30")  # Winter Storm Fern


def plot(daily: pd.DataFrame, path) -> None:
    d = daily.set_index("date")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    ax1.plot(d.index, d["mtm_total"] / 1e6, color="tab:blue")
    ax1.axvspan(pd.Timestamp(STORM[0]), pd.Timestamp(STORM[1]), color="orange", alpha=0.3, label="Winter Storm Fern")
    ax1.axhline(0, color="k", lw=0.5)
    ax1.set_ylabel("$ millions")
    ax1.set_title("Book mark-to-market value (simulated trades, real Henry Hub prices)")
    ax1.legend()

    s = d.loc["2026-01-12":"2026-02-13", ["new_deals", "forward_price_move", "delivery_and_spot"]] / 1e3
    s.columns = ["New deals", "Forward price move", "Delivery & spot"]
    s.index = s.index.strftime("%b %d")
    s.plot.bar(stacked=True, ax=ax2, color=["tab:green", "tab:blue", "tab:orange"], width=0.8)
    ax2.axhline(0, color="k", lw=0.5)
    ax2.set_ylabel("$ thousands")
    ax2.set_title("Daily P&L explained around Winter Storm Fern")
    ax2.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    engine = create_engine(connection_url())
    trades, marks = pnl.load_from_database(engine)

    last = min(marks.futures.index.max(), marks.spot_daily.index.max())
    days = marks.futures.loc[trades["trade_date"].min():last].index
    daily = pnl.daily_pnl(trades, marks, days)

    final = pnl.trade_values(trades, marks, days[-1])
    cps = pd.read_sql("SELECT counterparty_id, name, type FROM counterparties", engine)
    by_cp = (final.groupby("counterparty_id")["value"].sum().rename("mtm_usd").reset_index()
             .merge(cps, on="counterparty_id").sort_values("mtm_usd"))

    REPORTS.mkdir(exist_ok=True)
    daily.round({c: 2 for c in daily.columns if c != "date"}).to_csv(REPORTS / "book_pnl_daily.csv", index=False)
    by_cp.round(2).to_csv(REPORTS / "book_pnl_by_counterparty.csv", index=False)
    plot(daily, REPORTS / "book_pnl.png")

    d = daily.set_index("date")
    storm = d.loc[STORM[0]:STORM[1]]
    print(f"{len(trades)} trades, valued {days[0].date()} -> {days[-1].date()}")
    print(f"Book value on {days[-1].date()}: ${d['mtm_total'].iloc[-1]:,.0f}")
    print(f"Winter Storm Fern {STORM[0]} -> {STORM[1]}: P&L ${storm['pnl'].sum():,.0f} "
          f"(forward ${storm['forward_price_move'].sum():,.0f}, delivery/spot ${storm['delivery_and_spot'].sum():,.0f}, "
          f"new deals ${storm['new_deals'].sum():,.0f})")
    print("Worst 5 days:")
    print(d.nsmallest(5, "pnl")[["pnl", "new_deals", "forward_price_move", "delivery_and_spot"]].round(0).to_string())
    print("\nBy counterparty (value of all deals, + = they owe us value):")
    print(by_cp[["name", "type", "mtm_usd"]].round(0).to_string(index=False))
