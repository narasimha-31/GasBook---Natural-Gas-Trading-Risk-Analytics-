"""EIA API v2 client.

Docs: https://www.eia.gov/opendata/documentation.php
The API returns at most 5,000 rows per request, so fetch_series pages through results.
"""

import pandas as pd
import requests

from gasbook.config import DATA_RAW, eia_api_key

BASE_URL = "https://api.eia.gov/v2"
PAGE_SIZE = 5000

# Henry Hub natural gas spot price, $/MMBtu, daily (same series FRED mirrors as DHHNGSP)
HENRY_HUB_ROUTE = "natural-gas/pri/fut"
HENRY_HUB_SERIES = "RNGWHHD"


def fetch_series(
    route: str,
    series: str,
    frequency: str,
    start: str | None = None,
    end: str | None = None,
    session: requests.Session | None = None,
    api_key: str | None = None,
) -> pd.DataFrame:
    """Download one EIA series as a DataFrame with columns [period, value]."""
    session = session or requests.Session()
    api_key = api_key or eia_api_key()
    rows, offset = [], 0

    while True:
        params = {
            "api_key": api_key,
            "frequency": frequency,
            "data[0]": "value",
            "facets[series][]": series,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "offset": offset,
            "length": PAGE_SIZE,
        }
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        resp = session.get(f"{BASE_URL}/{route}/data/", params=params, timeout=60)
        resp.raise_for_status()
        body = resp.json().get("response", {})
        page = body.get("data", [])
        rows.extend(page)

        total = int(body.get("total", 0))
        offset += len(page)
        if not page or offset >= total:
            break

    return _clean(rows)


def _clean(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["period", "value"])
    df = pd.DataFrame(rows)[["period", "value"]]
    df["period"] = pd.to_datetime(df["period"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return (
        df.dropna(subset=["value"])
        .drop_duplicates(subset="period", keep="last")
        .sort_values("period")
        .reset_index(drop=True)
    )


def fetch_henry_hub_daily(start: str = "1997-01-07", **kwargs) -> pd.DataFrame:
    """Henry Hub daily spot price ($/MMBtu), columns [date, henry_hub]."""
    df = fetch_series(HENRY_HUB_ROUTE, HENRY_HUB_SERIES, "daily", start=start, **kwargs)
    return df.rename(columns={"period": "date", "value": "henry_hub"})


def save_raw(df: pd.DataFrame, name: str) -> str:
    """Cache an API pull to data/raw/<name>.csv so reruns don't hit the API."""
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    path = DATA_RAW / f"{name}.csv"
    df.to_csv(path, index=False)
    return str(path)


if __name__ == "__main__":
    hh = fetch_henry_hub_daily()
    path = save_raw(hh, "henry_hub_daily")
    print(f"{len(hh):,} rows {hh['date'].min().date()} -> {hh['date'].max().date()} saved to {path}")
    print(hh.tail())
