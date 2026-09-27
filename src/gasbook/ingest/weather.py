"""Weather for the places that matter to a Gulf Coast gas desk, from Open-Meteo (free, no key).

Three sources:
- forecast:       next 16 days                         https://api.open-meteo.com/v1/forecast
- observed:       what actually happened (ERA5 archive) https://archive-api.open-meteo.com/v1/archive
- past forecasts: what the forecast said N days before  https://previous-runs-api.open-meteo.com/v1/forecast
                  (archived from January 2024 onward)

Temperatures in Fahrenheit, wind in mph, days in US Central time.
"""

import pandas as pd
import requests

from gasbook.config import DATA_RAW

SITES = {
    "Midland TX (Permian gas fields)": (31.997, -102.078),
    "Houston TX": (29.760, -95.370),
    "Erath LA (Henry Hub)": (29.958, -92.036),
    "Sabine Pass LA (LNG)": (29.728, -93.870),
    "Corpus Christi TX (LNG)": (27.800, -97.396),
}
UNITS = {"temperature_unit": "fahrenheit", "wind_speed_unit": "mph", "timezone": "America/Chicago"}
DAILY = "temperature_2m_min,wind_gusts_10m_max"


def _daily_frame(payload: dict, site: str) -> pd.DataFrame:
    d = payload["daily"]
    return pd.DataFrame({"date": pd.to_datetime(d["time"]), "site": site,
                         "min_temp_f": d["temperature_2m_min"], "max_gust_mph": d["wind_gusts_10m_max"]})


def forecast(session: requests.Session | None = None, days: int = 16) -> pd.DataFrame:
    session = session or requests.Session()
    frames = []
    for site, (lat, lon) in SITES.items():
        r = session.get("https://api.open-meteo.com/v1/forecast", timeout=60,
                        params={"latitude": lat, "longitude": lon, "daily": DAILY, "forecast_days": days, **UNITS})
        r.raise_for_status()
        frames.append(_daily_frame(r.json(), site))
    return pd.concat(frames, ignore_index=True)


def observed(start: str, end: str, session: requests.Session | None = None) -> pd.DataFrame:
    session = session or requests.Session()
    frames = []
    for site, (lat, lon) in SITES.items():
        r = session.get("https://archive-api.open-meteo.com/v1/archive", timeout=120,
                        params={"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
                                "daily": DAILY, **UNITS})
        r.raise_for_status()
        frames.append(_daily_frame(r.json(), site))
    return pd.concat(frames, ignore_index=True)


def past_forecasts(start: str, end: str, leads=(1, 2, 3, 5, 7), session: requests.Session | None = None) -> pd.DataFrame:
    """Daily minimum temperature as forecast `lead` days earlier, for each site and day (from hourly runs)."""
    session = session or requests.Session()
    cols = [f"temperature_2m_previous_day{k}" for k in leads]
    frames = []
    for site, (lat, lon) in SITES.items():
        r = session.get("https://previous-runs-api.open-meteo.com/v1/forecast", timeout=120,
                        params={"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
                                "hourly": ",".join(cols), **UNITS})
        r.raise_for_status()
        h = pd.DataFrame(r.json()["hourly"])
        h["date"] = pd.to_datetime(h["time"]).dt.normalize()
        daily = h.groupby("date")[cols].min()
        long = daily.melt(ignore_index=False, var_name="lead", value_name="min_temp_f").reset_index()
        long["lead_days"] = long["lead"].str.extract(r"(\d+)$").astype(int)
        frames.append(long.drop(columns="lead").assign(site=site))
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    obs = observed("2010-01-01", (pd.Timestamp.today() - pd.Timedelta(days=7)).strftime("%Y-%m-%d"))
    obs.to_csv(DATA_RAW / "weather_observed.csv", index=False)
    past = past_forecasts("2024-01-01", (pd.Timestamp.today() - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    past.to_csv(DATA_RAW / "weather_past_forecasts.csv", index=False)
    fc = forecast()
    fc.to_csv(DATA_RAW / "weather_forecast.csv", index=False)
    print(f"observed: {len(obs):,} rows, past forecasts: {len(past):,} rows, forecast: {len(fc)} rows")
