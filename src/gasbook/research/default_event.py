"""What the simulated producer default during Winter Storm Fern costs the desk.

On the default date every deal with the counterparty is terminated (NAESB Section 10). We add up what they
owed us, subtract what we owed them (set-off), and add what it costs to replace the gas they will no longer
deliver at that day's prices. A positive net amount is our loss, assuming nothing is recovered in bankruptcy.

Run: python -m gasbook.research.default_event   (needs: python -m gasbook.book.database)
Output: reports/default_event.csv
"""

import pandas as pd
from sqlalchemy import create_engine

from gasbook.book import credit, pnl
from gasbook.book.database import connection_url
from gasbook.config import ROOT

REPORTS = ROOT / "reports"


if __name__ == "__main__":
    engine = create_engine(connection_url())
    trades, marks = pnl.load_from_database(engine)
    cps = pd.read_sql("SELECT counterparty_id, name, status, credit_limit_usd, payment_delay_days, default_date "
                      "FROM counterparties", engine, parse_dates=["default_date"])
    cps["credit_limit_usd"] = cps["credit_limit_usd"].astype(float)

    rows = []
    for cp in cps.dropna(subset=["default_date"]).itertuples(index=False):
        when = pd.Timestamp(cp.default_date)
        open_deals = trades[(trades["counterparty_id"] == cp.counterparty_id) & (trades["delivery_end"] >= when)]
        d = credit.default_settlement(trades, cps, marks, cp.counterparty_id, when)
        day_before = credit.exposures(trades, cps.assign(default_date=pd.NaT), marks, when - pd.offsets.BDay(1))
        before = day_before.set_index("counterparty_id").loc[cp.counterparty_id]
        rows.append({
            **d, "name": cp.name, "credit_limit": cp.credit_limit_usd, "open_deals": len(open_deals),
            "open_volume_mmbtu": int((open_deals["volume_mmbtu_per_day"]
                                      * ((open_deals["delivery_end"] - open_deals["delivery_start"]).dt.days + 1)).sum()),
            "spot_on_default_date": marks.spot(when),
            "exposure_day_before": before["exposure"], "utilization_day_before": before["utilization"],
            "loss_vs_limit": d["loss"] / cp.credit_limit_usd,
        })

    out = pd.DataFrame(rows)
    REPORTS.mkdir(exist_ok=True)
    out.round({c: 2 for c in out.select_dtypes("number").columns}).to_csv(REPORTS / "default_event.csv", index=False)
    for r in rows:
        print(f"{r['name']} defaults on {r['default_date'].date()} (Henry Hub spot ${r['spot_on_default_date']:.2f})")
        print(f"  open deals: {r['open_deals']} ({r['open_volume_mmbtu']:,} MMBtu)")
        print(f"  what they owed us:            ${r['unpaid_sales']:,.0f}")
        print(f"  what we owed them (set-off):  ${r['unpaid_purchases']:,.0f}")
        print(f"  cost to replace their gas:    ${r['future_value']:,.0f}")
        print(f"  net loss:                     ${r['loss']:,.0f}  = {r['loss_vs_limit']:.0%} of their ${r['credit_limit']:,.0f} limit")
        print(f"  loss if the contract had no set-off: ${r['loss_without_setoff']:,.0f}")
        print(f"  saved by set-off (netting):   ${r['loss_without_setoff'] - r['loss']:,.0f}")
        print(f"  exposure the day before:      ${r['exposure_day_before']:,.0f} ({r['utilization_day_before']:.0%} of limit)")
