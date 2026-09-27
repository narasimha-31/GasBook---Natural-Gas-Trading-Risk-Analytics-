"""Weekly features for forecasting the EIA storage change.

Every feature for a storage week must be known by the Thursday the number is published:
- weather for the storage week (Saturday to Friday) has already happened
- last week's storage level and change came out in last Thursday's report
- LNG exports and production are published about two months after the month ends, so only months at
  least MONTHLY_LAG_MONTHS before the week are used
- holiday weeks (Thanksgiving, Christmas, New Year) are known in advance; factories and offices close,
  so less gas is burned
"""

import numpy as np
import pandas as pd

REGIONS = ["East", "Midwest", "South Central", "Mountain", "Pacific"]
MONTHLY_LAG_MONTHS = 3  # conservative: a week in September only sees monthly data up to June
TREND_START = pd.Timestamp("2010-01-01")


def weekly_degree_days(daily: pd.DataFrame, week_endings: pd.Series) -> pd.DataFrame:
    """Sum each city's daily HDD/CDD over the storage week (Saturday to Friday), then average cities per region.

    Returns one row per week ending with columns hdd_<region> and cdd_<region>.
    Weeks with any missing day for a city are left empty rather than partly summed.
    """
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"])
    # The storage week ending on Friday F covers Saturday F-6 to Friday F
    d["week_ending"] = d["date"] + pd.to_timedelta((4 - d["date"].dt.dayofweek) % 7, unit="D")
    per_city = d.groupby(["week_ending", "city", "region"]).agg(
        hdd=("hdd", "sum"), cdd=("cdd", "sum"), days=("hdd", "count")).reset_index()
    per_city.loc[per_city["days"] < 7, ["hdd", "cdd"]] = np.nan
    per_region = per_city.groupby(["week_ending", "region"])[["hdd", "cdd"]].mean().unstack("region")
    per_region.columns = [f"{kind}_{region}" for kind, region in per_region.columns]
    return per_region.reindex(pd.to_datetime(week_endings)).rename_axis("week_ending")


def monthly_available(monthly: pd.DataFrame, column: str, week_endings: pd.Series,
                      lag_months: int = MONTHLY_LAG_MONTHS) -> pd.Series:
    """A monthly series (e.g. LNG exports) from the latest month that would already be published by each week."""
    m = monthly.set_index(pd.to_datetime(monthly["month"]))[column].sort_index()
    weeks = pd.to_datetime(pd.Series(week_endings))
    usable_month = weeks.dt.to_period("M").dt.to_timestamp() - pd.DateOffset(months=lag_months)
    values = m.asof(pd.DatetimeIndex(usable_month))  # latest published month on or before the usable month
    return pd.Series(values.to_numpy(), index=weeks.to_numpy(), name=column)


def holiday_weeks(week_endings: pd.Series) -> pd.DataFrame:
    """Flags for storage weeks (Saturday to Friday) containing Thanksgiving, Christmas Day or New Year's Day."""
    w = pd.to_datetime(pd.Series(week_endings))
    start = w - pd.Timedelta(days=6)

    def contains(day_of_year) -> np.ndarray:
        return np.array([any(s <= d <= e for d in day_of_year(s, e)) for s, e in zip(start, w)])

    def thanksgiving(year: int) -> pd.Timestamp:  # fourth Thursday of November
        nov1 = pd.Timestamp(year=year, month=11, day=1)
        return nov1 + pd.Timedelta(days=(3 - nov1.dayofweek) % 7 + 21)

    return pd.DataFrame({
        "thanksgiving_week": contains(lambda s, e: [thanksgiving(y) for y in {s.year, e.year}]).astype(float),
        "christmas_week": contains(lambda s, e: [pd.Timestamp(year=y, month=12, day=25) for y in {s.year, e.year}]).astype(float),
        "new_year_week": contains(lambda s, e: [pd.Timestamp(year=y, month=1, day=1) for y in {s.year, e.year}]).astype(float),
    }, index=w.to_numpy())


def seasonal_terms(week_endings: pd.Series, harmonics: int = 2) -> pd.DataFrame:
    """Smooth yearly cycle as sine/cosine pairs (a gentle baseline for injection and withdrawal seasons)."""
    w = pd.to_datetime(pd.Series(week_endings))
    angle = 2 * np.pi * (w.dt.dayofyear.to_numpy() / 365.25)
    out = {}
    for k in range(1, harmonics + 1):
        out[f"season_sin{k}"] = np.sin(k * angle)
        out[f"season_cos{k}"] = np.cos(k * angle)
    return pd.DataFrame(out, index=w.to_numpy())


def build(storage: pd.DataFrame, daily_weather: pd.DataFrame, lng_monthly: pd.DataFrame,
          production_monthly: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per storage week: target (weekly_change_bcf) plus features known by report day."""
    s = storage.sort_values("week_ending").reset_index(drop=True).copy()
    s["week_ending"] = pd.to_datetime(s["week_ending"])
    weeks = s["week_ending"]

    df = pd.DataFrame(index=weeks.to_numpy())
    df.index.name = "week_ending"
    df["weekly_change_bcf"] = s["weekly_change_bcf"].to_numpy()
    df = df.join(weekly_degree_days(daily_weather, weeks))
    df["storage_prev_bcf"] = s["storage_bcf"].shift(1).to_numpy()
    df["change_prev_bcf"] = s["weekly_change_bcf"].shift(1).to_numpy()
    df["lng_exports_bcfd"] = monthly_available(lng_monthly, "lng_exports_bcfd", weeks).to_numpy()
    if production_monthly is not None:
        df["production_bcfd"] = monthly_available(production_monthly, "production_bcfd", weeks).to_numpy()
        # Gas left for the domestic market after exports; physically, +1 Bcf/d should add about 7 Bcf a week
        df["net_supply_bcfd"] = df["production_bcfd"] - df["lng_exports_bcfd"]
    df = df.join(holiday_weeks(weeks))
    df = df.join(seasonal_terms(weeks))
    years = ((weeks - TREND_START).dt.days / 365.25).to_numpy()
    df["years_since_2010"] = years
    # Coal retirements: each cooling degree day burns more gas for power over time
    df["cdd_south_x_years"] = df["cdd_South Central"] * years
    df["cdd_east_x_years"] = df["cdd_East"] * years
    return df


BASE_FEATURES = (
    [f"hdd_{r}" for r in REGIONS] + [f"cdd_{r}" for r in REGIONS]
    + ["storage_prev_bcf", "change_prev_bcf", "lng_exports_bcfd", "season_sin1", "season_cos1", "season_sin2",
       "season_cos2", "years_since_2010", "cdd_south_x_years", "cdd_east_x_years"]
)
HOLIDAY_FEATURES = ["thanksgiving_week", "christmas_week", "new_year_week"]
WEATHER_SEASON_FEATURES = (
    [f"hdd_{r}" for r in REGIONS] + [f"cdd_{r}" for r in REGIONS]
    + ["storage_prev_bcf", "change_prev_bcf", "season_sin1", "season_cos1", "season_sin2", "season_cos2"]
)
# Version 2: one physical supply input instead of production, LNG exports and a time trend that move together
NET_SUPPLY_FEATURES = WEATHER_SEASON_FEATURES + HOLIDAY_FEATURES + ["net_supply_bcfd"]
PRODUCTION_FEATURES = ["production_bcfd"]
FEATURES = BASE_FEATURES + HOLIDAY_FEATURES + PRODUCTION_FEATURES
