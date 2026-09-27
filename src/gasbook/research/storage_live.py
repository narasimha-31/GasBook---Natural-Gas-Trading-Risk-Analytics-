"""Forecast the next EIA storage report (and one week further), and log it before it is published.

Run any day before Thursday: python -m gasbook.research.storage_live
(needs: python -m gasbook.ingest.eia, python -m gasbook.research.storage_model)
Outputs: reports/storage_next_week.csv, reports/storage_forecast_log.csv (appended, scored when actuals arrive)
"""

import pandas as pd

from gasbook.config import DATA_RAW, ROOT
from gasbook.ingest import demand_weather
from gasbook.models import storage_forecast as sm
from gasbook.models import storage_live as live
from gasbook.research.storage_model import load_features

REPORTS = ROOT / "reports"
LOG = REPORTS / "storage_forecast_log.csv"


if __name__ == "__main__":
    features, storage = load_features()
    settings = sm.run(features, storage)  # same validation-chosen settings as the study
    linear, trees = sm.final_models(features, settings["best_alpha"], settings["best_gbm"])
    backtest = pd.read_csv(REPORTS / "storage_model_predictions.csv", parse_dates=["week_ending"])

    observed = pd.read_csv(DATA_RAW / "weather_demand_observed.csv", parse_dates=["date"])
    recent_and_ahead = demand_weather.forecast(days=16, past_days=10)
    recent_and_ahead.to_csv(DATA_RAW / "weather_demand_forecast.csv", index=False)
    weather = live.combine_weather(observed, recent_and_ahead)

    lng = pd.read_csv(DATA_RAW / "lng_exports_monthly.csv", parse_dates=["month"])
    production = pd.read_csv(DATA_RAW / "production_monthly.csv", parse_dates=["month"])
    result = live.forecast_weeks(storage, weather, lng, production, linear, trees, live.error_range(backtest))

    log = pd.read_csv(LOG) if LOG.exists() else pd.DataFrame()
    log = live.update_log(log, result, storage, pd.Timestamp.today().normalize())
    REPORTS.mkdir(exist_ok=True)
    result.to_csv(REPORTS / "storage_next_week.csv", index=False)
    log.to_csv(LOG, index=False)

    last = storage.sort_values("week_ending").iloc[-1]
    print(f"Latest EIA report: week ending {pd.Timestamp(last['week_ending']).date()}, "
          f"change {last['weekly_change_bcf']:+.0f} Bcf, storage {last['storage_bcf']:,.0f} Bcf\n")
    pd.set_option("display.width", 200)
    print(result.to_string(index=False))
    scored = log.dropna(subset=["actual_bcf"])
    print(f"\nForecast log: {len(log)} forecasts, {len(scored)} scored"
          + (f", average miss {scored['miss_bcf'].abs().mean():.1f} Bcf" if len(scored) else ""))
