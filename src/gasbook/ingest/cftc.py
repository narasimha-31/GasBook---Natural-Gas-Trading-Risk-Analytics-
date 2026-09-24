"""CFTC Commitments of Traders: managed-money (hedge fund) positioning in NYMEX Henry Hub natural gas futures.

Source: CFTC Public Reporting API (Socrata), Disaggregated Futures-Only report, no key needed.
https://publicreporting.cftc.gov/resource/72hh-3qpy
Positions are as of Tuesday and published the following Friday at 3:30 pm ET.
"""

import pandas as pd
import requests

from gasbook.config import DATA_RAW

URL = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
NYMEX_NATGAS_CODE = "023651"  # contract_market_name "NAT GAS NYME"
PAGE_SIZE = 5000

FIELDS = {
    "report_date_as_yyyy_mm_dd": "report_date",
    "open_interest_all": "open_interest",
    "m_money_positions_long_all": "mm_long",
    "m_money_positions_short_all": "mm_short",
    "m_money_positions_spread": "mm_spread",
    "prod_merc_positions_long": "producer_long",
    "prod_merc_positions_short": "producer_short",
}


def fetch_positioning(code: str = NYMEX_NATGAS_CODE, session: requests.Session | None = None) -> pd.DataFrame:
    """Weekly positioning with net managed money and its share of open interest."""
    session = session or requests.Session()
    rows, offset = [], 0
    while True:
        params = {
            "$select": ",".join(FIELDS),
            "$where": f"cftc_contract_market_code='{code}'",
            "$order": "report_date_as_yyyy_mm_dd ASC",
            "$limit": PAGE_SIZE,
            "$offset": offset,
        }
        resp = session.get(URL, params=params, timeout=60)
        resp.raise_for_status()
        page = resp.json()
        rows.extend(page)
        offset += len(page)
        if len(page) < PAGE_SIZE:
            break
    return _clean(rows)


def _clean(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=[*FIELDS.values(), "mm_net", "mm_net_pct_oi"])
    df = pd.DataFrame(rows).reindex(columns=list(FIELDS)).rename(columns=FIELDS)
    df["report_date"] = pd.to_datetime(df["report_date"])
    num = [c for c in FIELDS.values() if c != "report_date"]
    df[num] = df[num].apply(pd.to_numeric, errors="coerce")
    df = df.drop_duplicates(subset="report_date", keep="last").sort_values("report_date").reset_index(drop=True)
    df["mm_net"] = df["mm_long"] - df["mm_short"]
    df["mm_net_pct_oi"] = df["mm_net"] / df["open_interest"]
    return df


if __name__ == "__main__":
    cot = fetch_positioning()
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    out = DATA_RAW / "cftc_natgas_positioning.csv"
    cot.to_csv(out, index=False)
    print(f"{len(cot):,} weeks {cot['report_date'].min().date()} -> {cot['report_date'].max().date()} saved to {out}")
    print(cot[["report_date", "open_interest", "mm_long", "mm_short", "mm_net", "mm_net_pct_oi"]].tail()
          .round({"mm_net_pct_oi": 3}))
