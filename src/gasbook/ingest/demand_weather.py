"""Daily average temperature in the big gas-heating and cooling cities, for forecasting weekly storage.

Storage swings with how much gas the whole country burns for heat and power, which depends mostly on the
Northeast and Midwest in winter and on the South in summer. So this uses demand centres in each of EIA's
five storage regions, not the Gulf Coast sites used by Storm Watch.

Heating degree days (HDD) = how far the day's average temperature is below 65F; cooling degree days (CDD) =
how far it is above. They are the standard way the gas industry turns weather into demand.

Source: Open-Meteo (free, no key). Observed: ERA5 archive. Forecast: next 16 days.
"""

import pandas as pd
import requests

from gasbook.config import DATA_RAW

BASE_TEMP_F = 65.0

# City: (latitude, longitude, EIA storage region)
CITIES = {
    "New York": (40.713, -74.006, "East"),
    "Boston": (42.360, -71.059, "East"),
    "Philadelphia": (39.953, -75.165, "East"),
    "Pittsburgh": (40.441, -79.996, "East"),
    "Atlanta": (33.749, -84.388, "East"),
    "Chicago": (41.878, -87.630, "Midwest"),
    "Detroit": (42.331, -83.046, "Midwest"),
    "Minneapolis": (44.978, -93.265, "Midwest"),
    "Dallas": (32.777, -96.797, "South Central"),
    "Houston": (29.760, -95.370, "South Central"),
    "Denver": (39.739, -104.990, "Mountain"),
    "Los Angeles": (34.052, -118.244, "Pacific"),
}
UNITS = {"temperature_unit": "fahrenheit", "timezone": "America/New_York"}


def degree_days(mean_temp_f: pd.Series) -> pd.DataFrame:
    """Heating and cooling degree days from daily average temperature."""
    return pd.DataFrame({
        "hdd": (BASE_TEMP_F - mean_temp_f).clip(lower=0),
        "cdd": (mean_temp_f - BASE_TEMP_F).clip(lower=0),
    }, index=mean_temp_f.index)


def _frame(payload: dict, city: str) -> pd.DataFrame:
    d = payload["daily"]
    region = CITIES[city][2]
    df = pd.DataFrame({"date": pd.to_datetime(d["time"]), "city": city, "region": region,
                       "mean_temp_f": d["temperature_2m_mean"]})
    return pd.concat([df, degree_days(df["mean_temp_f"])], axis=1)


def observed(start: str, end: str, session: requests.Session | None = None) -> pd.DataFrame:
    session = session or requests.Session()
    frames = []
    for city, (lat, lon, _) in CITIES.items():
        r = session.get("https://archive-api.open-meteo.com/v1/archive", timeout=120,
                        params={"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
                                "daily": "temperature_2m_mean", **UNITS})
        r.raise_for_status()
        frames.append(_frame(r.json(), city))
    return pd.concat(frames, ignore_index=True)


def forecast(days: int = 16, session: requests.Session | None = None) -> pd.DataFrame:
    session = session or requests.Session()
    frames = []
    for city, (lat, lon, _) in CITIES.items():
        r = session.get("https://api.open-meteo.com/v1/forecast", timeout=60,
                        params={"latitude": lat, "longitude": lon, "daily": "temperature_2m_mean",
                                "forecast_days": days, **UNITS})
        r.raise_for_status()
        frames.append(_frame(r.json(), city))
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    end = (pd.Timestamp.today() - pd.Timedelta(days=6)).strftime("%Y-%m-%d")  # archive lags by a few days
    obs = observed("2009-06-01", end)
    obs.to_csv(DATA_RAW / "weather_demand_observed.csv", index=False)
    fc = forecast()
    fc.to_csv(DATA_RAW / "weather_demand_forecast.csv", index=False)
    print(f"observed: {len(obs):,} rows ({obs['date'].min().date()} -> {obs['date'].max().date()}), "
          f"forecast: {len(fc)} rows")
