"""Live storage forecast: the next EIA report, plus a projection one week further, and a log to score them.

- Weather for each storage week (Saturday to Friday) comes from the observed archive where it exists,
  otherwise from the forecast service (recent days and days ahead). The share of forecast days is reported.
- The second week is a projection: it uses the first week's forecast as its "last week" inputs.
- The likely range comes from the model's real misses in the retrained backtest (10th to 90th percentile),
  not from an assumed spread.
- Every forecast is written to a log before the report is published, then scored once the actual is known.
"""

import pandas as pd

from gasbook.ingest.demand_weather import degree_days
from gasbook.models import storage_features as sf
from gasbook.models.storage_features import BASE_FEATURES, FEATURES

LOG_COLUMNS = ["made_on", "week_ending", "report_date", "kind", "forecast_bcf", "low_bcf", "high_bcf",
               "forecast_weather_share", "actual_bcf", "miss_bcf"]


def combine_weather(observed: pd.DataFrame, forecast: pd.DataFrame) -> pd.DataFrame:
    """Observed days where available, forecast days only for dates the archive does not have yet."""
    obs = observed.assign(source="observed")
    fc = forecast.assign(source="forecast")
    have = set(zip(obs["city"], pd.to_datetime(obs["date"])))
    fc = fc[[(c, pd.Timestamp(d)) not in have for c, d in zip(fc["city"], fc["date"])]]
    return pd.concat([obs, fc], ignore_index=True)


def shift_forecast_days(weather: pd.DataFrame, degrees_f: float) -> pd.DataFrame:
    """What if the days still forecast turn out warmer (+) or colder (-)? Observed days stay as they were."""
    w = weather.copy()
    ahead = w["source"] == "forecast"
    w.loc[ahead, "mean_temp_f"] = w.loc[ahead, "mean_temp_f"] + degrees_f
    w.loc[ahead, ["hdd", "cdd"]] = degree_days(w.loc[ahead, "mean_temp_f"]).to_numpy()
    return w


def error_range(backtest: pd.DataFrame, column: str = "blend", low_q: float = 0.1, high_q: float = 0.9) -> tuple[float, float]:
    """Quantiles of forecast minus actual from the backtest: actual tends to land in [f - q_high, f - q_low]."""
    miss = backtest[column] - backtest["actual"]
    return float(miss.quantile(low_q)), float(miss.quantile(high_q))


def forecast_weeks(storage: pd.DataFrame, weather: pd.DataFrame, lng: pd.DataFrame, production: pd.DataFrame,
                   linear, trees, miss_quantiles: tuple[float, float], n_weeks: int = 2) -> pd.DataFrame:
    """Forecast the next `n_weeks` storage weeks after the latest report."""
    s = storage.sort_values("week_ending")
    last = pd.Timestamp(s["week_ending"].iloc[-1])
    prev_level = float(s["storage_bcf"].iloc[-1])
    prev_change = float(s["weekly_change_bcf"].iloc[-1])
    weeks = pd.Series([last + pd.Timedelta(days=7 * (k + 1)) for k in range(n_weeks)])

    dd = sf.weekly_degree_days(weather, weeks)
    w = weather.copy()
    w["date"] = pd.to_datetime(w["date"])
    w["week_ending"] = w["date"] + pd.to_timedelta((4 - w["date"].dt.dayofweek) % 7, unit="D")
    forecast_share = (w[w["week_ending"].isin(weeks)].groupby("week_ending")["source"]
                      .apply(lambda x: (x == "forecast").mean()))
    lng_v = sf.monthly_available(lng, "lng_exports_bcfd", weeks).to_numpy()
    prod_v = sf.monthly_available(production, "production_bcfd", weeks).to_numpy()
    seasons = sf.seasonal_terms(weeks)
    holidays = sf.holiday_weeks(weeks)
    q_low, q_high = miss_quantiles

    rows = []
    for k, week in enumerate(weeks):
        x = dd.loc[week].to_dict()
        years = (week - sf.TREND_START).days / 365.25
        x.update(seasons.iloc[k].to_dict())
        x.update(holidays.iloc[k].to_dict())
        x.update({
            "storage_prev_bcf": prev_level, "change_prev_bcf": prev_change,
            "lng_exports_bcfd": lng_v[k], "production_bcfd": prod_v[k], "years_since_2010": years,
            "cdd_south_x_years": x["cdd_South Central"] * years, "cdd_east_x_years": x["cdd_East"] * years,
        })
        row = pd.DataFrame([x])
        if row[FEATURES].isna().any(axis=None):
            raise ValueError(f"missing inputs for week ending {week.date()}: weather not available yet")
        lin = float(linear.predict(row[FEATURES])[0])
        tree = float(trees.predict(row[BASE_FEATURES])[0])
        blend = (lin + tree) / 2
        rows.append({
            "week_ending": week.date(), "report_date": (week + pd.Timedelta(days=6)).date(),
            "kind": "next report" if k == 0 else "projection",
            "forecast_bcf": round(blend, 1), "low_bcf": round(blend - q_high, 1), "high_bcf": round(blend - q_low, 1),
            "linear_bcf": round(lin, 1), "trees_bcf": round(tree, 1),
            "forecast_weather_share": round(float(forecast_share.get(week, 1.0)), 2),
            "hdd_total": round(sum(x[f"hdd_{r}"] for r in sf.REGIONS), 1),
            "cdd_total": round(sum(x[f"cdd_{r}"] for r in sf.REGIONS), 1),
        })
        prev_level, prev_change = prev_level + blend, blend  # chain into the projection
    return pd.DataFrame(rows)


def update_log(log: pd.DataFrame, new: pd.DataFrame, storage: pd.DataFrame, made_on: pd.Timestamp) -> pd.DataFrame:
    """Add today's forecasts (once per day and week) and fill in actuals for weeks EIA has now reported."""
    log = log.reindex(columns=LOG_COLUMNS) if len(log) else pd.DataFrame(columns=LOG_COLUMNS)
    add = new.assign(made_on=made_on.date())[[c for c in LOG_COLUMNS if c in new.columns or c == "made_on"]]
    key = set(zip(log["made_on"].astype(str), log["week_ending"].astype(str)))
    add = add[[(str(m), str(w)) not in key for m, w in zip(add["made_on"], add["week_ending"])]]
    frames = [f for f in (log, add) if len(f)]
    out = pd.concat(frames, ignore_index=True).reindex(columns=LOG_COLUMNS) if frames else log
    actual = storage.set_index(pd.to_datetime(storage["week_ending"]).dt.date)["weekly_change_bcf"]
    weeks = pd.to_datetime(out["week_ending"]).dt.date
    out["actual_bcf"] = weeks.map(actual)
    out["miss_bcf"] = (out["forecast_bcf"].astype(float) - out["actual_bcf"]).round(1)
    return out
