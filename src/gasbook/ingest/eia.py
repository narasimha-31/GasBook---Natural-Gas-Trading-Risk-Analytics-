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

# Lower 48 working gas in underground storage, Bcf, weekly (week ending Friday, released Thursday)
STORAGE_ROUTE = "natural-gas/stor/wkly"
STORAGE_SERIES = "NW2_EPG0_SWO_R48_BCF"

# Monthly citygate prices, $/Mcf (thousand cubic feet, NOT $/MMBtu; 1 Mcf is roughly 1.037 MMBtu)
CITYGATE_ROUTE = "natural-gas/pri/sum"
CITYGATE_SERIES = {"US": "N3050US3", "TX": "N3050TX3", "LA": "N3050LA3"}


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


def fetch_storage_weekly(start: str = "2010-01-01", **kwargs) -> pd.DataFrame:
    """Lower 48 working gas storage (Bcf), columns [week_ending, storage_bcf, weekly_change_bcf]."""
    df = fetch_series(STORAGE_ROUTE, STORAGE_SERIES, "weekly", start=start, **kwargs)
    df = df.rename(columns={"period": "week_ending", "value": "storage_bcf"})
    df["weekly_change_bcf"] = df["storage_bcf"].diff()
    return df


def fetch_citygate_monthly(start: str = "1989-01", **kwargs) -> pd.DataFrame:
    """Monthly citygate prices ($/Mcf) for US, Texas and Louisiana in long format [month, region, price_per_mcf]."""
    frames = []
    for region, series in CITYGATE_SERIES.items():
        df = fetch_series(CITYGATE_ROUTE, series, "monthly", start=start, **kwargs)
        frames.append(df.rename(columns={"period": "month", "value": "price_per_mcf"}).assign(region=region))
    return pd.concat(frames, ignore_index=True)[["month", "region", "price_per_mcf"]]


def save_raw(df: pd.DataFrame, name: str) -> str:
    """Cache an API pull to data/raw/<name>.csv so reruns don't hit the API."""
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    path = DATA_RAW / f"{name}.csv"
    df.to_csv(path, index=False)
    return str(path)


if __name__ == "__main__":
    pulls = {
        "henry_hub_daily": (fetch_henry_hub_daily, "date"),
        "storage_weekly": (fetch_storage_weekly, "week_ending"),
        "citygate_monthly": (fetch_citygate_monthly, "month"),
    }
    for name, (fetch, date_col) in pulls.items():
        df = fetch()
        path = save_raw(df, name)
        print(f"{name}: {len(df):,} rows {df[date_col].min().date()} -> {df[date_col].max().date()} saved to {path}")
