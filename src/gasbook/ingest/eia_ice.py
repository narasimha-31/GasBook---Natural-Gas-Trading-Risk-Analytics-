"""EIA-ICE daily natural gas hub prices (republished by EIA from ICE).

Source: https://www.eia.gov/electricity/wholesale/
Free coverage ends in December 2017: EIA stopped publishing the natural gas files after that year,
so this dataset is 2014-03 to 2017-12 for 8 hubs. No newer or other hubs are filled in or estimated.
"""

import io

import pandas as pd
import requests

from gasbook.config import DATA_RAW

BASE = "https://www.eia.gov/electricity/wholesale/xls/archive"
FILES = {
    2014: "ice_natgas-2014final.xls",
    2015: "ice_natgas-2015final.xls",
    2016: "ice_natgas-2016final.xls",
    2017: "ice_natgas-2017final.xlsx",
}

COLUMNS = {
    "Price hub": "hub",
    "Trade date": "trade_date",
    "Delivery start date": "delivery_start",
    "Delivery end date": "delivery_end",
    "High price $/MMBtu": "high",
    "Low price $/MMBtu": "low",
    "Wtd avg price $/MMBtu": "wavg",
    "Change": "change",
    "Daily volume MMBtu": "volume_mmbtu",
    "Number of trades": "n_trades",
    "Number of counterparties": "n_counterparties",
}

HUB_NAMES = {
    "Henry": "Henry Hub",
    "Algonquin Citygates": "Algonquin Citygates",
    "TETCO-M3": "TETCO-M3",
    "Chicago Citygates": "Chicago Citygates",
    "Malin": "Malin",
    "PG&E - Citygate": "PG&E Citygate",
    "Socal-Citygate": "SoCal Citygate",
    "Socal-Ehrenberg": "SoCal Ehrenberg",
}


def download_year(year: int, session: requests.Session | None = None) -> bytes:
    """Fetch one yearly file, caching the raw bytes in data/raw/eia_ice/."""
    cache = DATA_RAW / "eia_ice" / FILES[year]
    if cache.exists():
        return cache.read_bytes()
    session = session or requests.Session()
    resp = session.get(f"{BASE}/{FILES[year]}", headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
    resp.raise_for_status()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(resp.content)
    return resp.content


def normalize(raw: pd.DataFrame) -> pd.DataFrame:
    """Rename columns, standardize hub names, fix types, drop bad and duplicate rows."""
    df = raw.rename(columns=lambda c: " ".join(str(c).split())).rename(columns=COLUMNS)
    missing = set(COLUMNS.values()) - set(df.columns)
    if missing:
        raise ValueError(f"EIA-ICE file is missing columns: {sorted(missing)}")

    df = df[list(COLUMNS.values())].dropna(subset=["hub", "trade_date", "wavg"])
    df["hub"] = df["hub"].str.strip().map(HUB_NAMES).fillna(df["hub"].str.strip())
    for col in ("trade_date", "delivery_start", "delivery_end"):
        df[col] = pd.to_datetime(df[col])
    for col in ("high", "low", "wavg", "change", "volume_mmbtu", "n_trades", "n_counterparties"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return (
        df.drop_duplicates(subset=["hub", "delivery_start"], keep="last")
        .sort_values(["hub", "delivery_start"])
        .reset_index(drop=True)
    )


def load_all(session: requests.Session | None = None) -> pd.DataFrame:
    frames = [pd.read_excel(io.BytesIO(download_year(y, session))) for y in FILES]
    return normalize(pd.concat(frames, ignore_index=True))


def to_wide(df: pd.DataFrame, value: str = "wavg") -> pd.DataFrame:
    """One row per gas delivery date, one column per hub. Missing days stay NaN (never filled)."""
    return df.pivot_table(index="delivery_start", columns="hub", values=value, aggfunc="last").sort_index()


if __name__ == "__main__":
    hubs = load_all()
    out = DATA_RAW / "eia_ice_hub_prices_2014_2017.csv"
    hubs.to_csv(out, index=False)
    print(f"{len(hubs):,} rows, {hubs['hub'].nunique()} hubs, "
          f"{hubs['delivery_start'].min().date()} -> {hubs['delivery_start'].max().date()} saved to {out}")
    print(hubs.groupby("hub")["wavg"].agg(["count", "min", "max"]).round(2))
