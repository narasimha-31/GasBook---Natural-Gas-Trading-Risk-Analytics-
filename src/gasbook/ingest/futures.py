"""NYMEX Henry Hub front-month futures (continuous NG=F) via yfinance.

Caveats handled here:
- Today's bar is dropped (incomplete while the market is open).
- NG=F is a continuous series that jumps when it rolls to the next contract. `near_expiry` flags those days so
  analyses can exclude them. NYMEX NG expires 3 business days before the first calendar day of the delivery month.
"""

import pandas as pd
import yfinance as yf

from gasbook.config import DATA_RAW

TICKER = "NG=F"


def fetch_front_month(start: str = "2010-01-01") -> pd.DataFrame:
    raw = yf.download(TICKER, start=start, progress=False, auto_adjust=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    df = raw[["Close", "Volume"]].rename(columns={"Close": "close", "Volume": "volume"}).dropna(subset=["close"])
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df[df.index < pd.Timestamp.today().normalize()]  # drop today's incomplete bar
    return df.rename_axis("date").reset_index()


def expiry_dates(start: str, end: str) -> pd.DatetimeIndex:
    """Approximate NG expiries: 3 business days before the 1st of each delivery month (ignores exchange holidays)."""
    months = pd.date_range(pd.Timestamp(start) - pd.offsets.MonthBegin(1), pd.Timestamp(end) + pd.offsets.MonthBegin(2),
                           freq="MS")
    return pd.DatetimeIndex([m - pd.offsets.BDay(3) for m in months])


def near_expiry(dates: pd.Series, before_bdays: int = 0, after_bdays: int = 1) -> pd.Series:
    """True for dates from `before_bdays` before to `after_bdays` after a contract expiry.

    Default (expiry day and the day after) matches where NG=F roll jumps show up in the data:
    average absolute daily move is ~5.0% the day after expiry vs ~2.4% on normal days.
    """
    dates = pd.to_datetime(dates)
    exp = expiry_dates(dates.min(), dates.max())
    flags = pd.Series(False, index=dates.index)
    for e in exp:
        lo, hi = e - pd.offsets.BDay(before_bdays), e + pd.offsets.BDay(after_bdays)
        flags |= (dates >= lo) & (dates <= hi)
    return flags


if __name__ == "__main__":
    ng = fetch_front_month()
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    out = DATA_RAW / "ng_front_month.csv"
    ng.to_csv(out, index=False)
    print(f"{len(ng):,} days {ng['date'].min().date()} -> {ng['date'].max().date()} saved to {out}")
