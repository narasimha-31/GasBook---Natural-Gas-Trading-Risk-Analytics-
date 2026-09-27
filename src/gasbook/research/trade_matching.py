"""Match every booked trade to the counterparty's confirmation and list what needs fixing.

Reads trades and confirmations from the PostgreSQL trade database. The answer key (which errors were planted)
is regenerated from the same seed only to score the matcher; the matcher itself never sees it.

Run: python -m gasbook.research.trade_matching   (needs: python -m gasbook.book.database)
Outputs: reports/matching_exceptions.csv, reports/matching_score.csv, reports/matching.png
"""

import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy import create_engine

from gasbook.book import confirmations, matching
from gasbook.book.database import connection_url
from gasbook.config import ROOT

REPORTS = ROOT / "reports"


def load(engine) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    dates = ["trade_date", "delivery_start", "delivery_end"]
    trades = pd.read_sql("SELECT * FROM trades ORDER BY trade_id", engine, parse_dates=dates)
    confs = pd.read_sql("SELECT * FROM confirmations", engine, parse_dates=dates + ["confirm_date"])
    for df in (trades, confs):
        for col in ("fixed_price", "index_adder"):
            df[col] = df[col].astype(float)
    cps = pd.read_sql("SELECT counterparty_id FROM counterparties ORDER BY counterparty_id", engine)
    return trades, confs, list(cps["counterparty_id"])


def exception_label(row) -> str:
    if row["status"] == "break":
        return "wrong " + row["differences"]
    return {"missing_confirm": "no confirmation received", "unknown_trade": "confirmation for a trade not in the book"}[
        row["status"]]


if __name__ == "__main__":
    engine = create_engine(connection_url())
    trades, confs, cp_ids = load(engine)

    started = time.perf_counter()
    results = matching.match(trades, confs)
    seconds = time.perf_counter() - started

    _, key = confirmations.generate(trades, cp_ids)
    score = matching.score_against_key(results, key, trades)

    exceptions = results[results["status"] != "matched"].copy()
    exceptions["issue"] = exceptions.apply(exception_label, axis=1)
    exceptions = exceptions.merge(trades[["trade_id", "trade_date", "counterparty_id", "buy_sell",
                                          "volume_mmbtu_per_day", "fixed_price", "index_adder"]],
                                  on="trade_id", how="left")

    REPORTS.mkdir(exist_ok=True)
    exceptions.to_csv(REPORTS / "matching_exceptions.csv", index=False)
    score.to_csv(REPORTS / "matching_score.csv", index=False)

    counts = exceptions["issue"].value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.barh(counts.index, counts.values, color="tab:purple")
    for y, v in enumerate(counts.values):
        ax.text(v + 0.3, y, str(v), va="center")
    ax.set_xlabel("Trades needing attention")
    ax.set_title(f"Confirmation exceptions: {len(exceptions)} of {len(trades)} trades (simulated errors)")
    fig.tight_layout()
    fig.savefig(REPORTS / "matching.png", dpi=130)
    plt.close(fig)

    print(f"{len(trades)} trades vs {len(confs)} confirmations, matched in {seconds:.1f} s")
    print(results["status"].value_counts().to_string())
    print("\nExceptions by issue:")
    print(counts.sort_values(ascending=False).to_string())
    print("\nMatcher vs planted errors:")
    print(score.to_string(index=False))
