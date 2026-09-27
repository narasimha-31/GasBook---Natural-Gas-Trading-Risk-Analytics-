"""Forecasting the weekly EIA storage number: results, checks and the model the dashboard uses.

Run: python -m gasbook.research.storage_model
     (needs: python -m gasbook.ingest.eia, python -m gasbook.ingest.demand_weather)
Outputs:
  reports/storage_model_scores.csv        test-year accuracy of every model, frozen and retrained each year
  reports/storage_model_predictions.csv   week-by-week forecasts vs actual, 2022 onward (retrained each year)
  reports/storage_model_walkforward.csv   same, from 2016 onward, for the storage report study (2016-2021 also
                                          chose the model settings, so those years are slightly flattering)
  reports/storage_model_coefficients.csv  what the linear model learned, in plain units (refit on all weeks)
  reports/storage_model.png               forecast vs actual chart

Findings kept in the code on purpose (see storage_forecast.py for the full notes):
- the chosen forecast is the blend, picked on 2016-2021 validation before the test years were scored
- production, LNG exports and the time trend move together (correlation 0.86-0.96), so their separate
  weights are not physically meaningful; a single "net supply" input was tried and did not beat version 1
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from gasbook.config import DATA_RAW, ROOT
from gasbook.models import storage_features as sf
from gasbook.models import storage_forecast as sm

REPORTS = ROOT / "reports"


def load_features() -> tuple[pd.DataFrame, pd.DataFrame]:
    storage = pd.read_csv(DATA_RAW / "storage_weekly.csv", parse_dates=["week_ending"])
    weather = pd.read_csv(DATA_RAW / "weather_demand_observed.csv", parse_dates=["date"])
    lng = pd.read_csv(DATA_RAW / "lng_exports_monthly.csv", parse_dates=["month"])
    production = pd.read_csv(DATA_RAW / "production_monthly.csv", parse_dates=["month"])
    return sf.build(storage, weather, lng, production), storage


def plot(preds: pd.DataFrame, path) -> None:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7.5), sharex=True, gridspec_kw={"height_ratios": [3, 1.3]})
    ax1.plot(preds.index, preds["actual"], color="0.15", lw=1.3, label="Actual (EIA report)")
    ax1.plot(preds.index, preds["blend"], color="tab:blue", lw=1.1, label="Model forecast")
    ax1.plot(preds.index, preds["bench_5yr_avg"], color="0.65", lw=0.9, ls="--", label="5-year average")
    ax1.axhline(0, color="k", lw=0.5)
    ax1.set_ylabel("Weekly storage change, Bcf")
    ax1.set_title("Weekly storage change: model forecast vs actual, 2022 onward (never seen in training)")
    ax1.legend(fontsize=8)
    ax2.bar(preds.index, preds["blend"] - preds["actual"], width=5, color="tab:blue", alpha=0.7)
    ax2.axhline(0, color="k", lw=0.5)
    ax2.set_ylabel("Forecast miss, Bcf")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    features, storage = load_features()
    frozen = sm.run(features, storage)
    retrained = sm.retrain_backtest(features, frozen["best_alpha"], frozen["best_gbm"])
    retrained = retrained.join(frozen["preds"][["bench_5yr_avg", "bench_last_gap"]])
    walkforward = sm.retrain_backtest(features, frozen["best_alpha"], frozen["best_gbm"], years=range(2016, 2027))

    models = ["bench_5yr_avg", "bench_last_gap", "linear", "trees", "blend"]
    scores = pd.concat([
        frozen["scores"].assign(evaluation="frozen on 2010-2021"),
        pd.DataFrame({k: sm.score(retrained["actual"], retrained[k]) for k in models}).T
        .assign(evaluation="retrained each year"),
    ]).rename_axis("model").reset_index()

    lin, _ = sm.final_models(features, frozen["best_alpha"], frozen["best_gbm"])
    coefficients = sm.ridge_coefficients(lin).reset_index()

    REPORTS.mkdir(exist_ok=True)
    scores.to_csv(REPORTS / "storage_model_scores.csv", index=False)
    retrained.round(2).to_csv(REPORTS / "storage_model_predictions.csv")
    walkforward.round(2).to_csv(REPORTS / "storage_model_walkforward.csv")
    coefficients.round(4).to_csv(REPORTS / "storage_model_coefficients.csv", index=False)
    plot(retrained, REPORTS / "storage_model.png")

    pd.set_option("display.width", 220)
    cols = ["model", "evaluation", "mae_bcf", "bias_bcf", "share_within_10bcf", "mae_winter_bcf", "mae_summer_bcf",
            "mae_big_weeks_bcf"]
    print(f"Settings from validation: ridge strength {frozen['best_alpha']}, trees {frozen['best_gbm']}")
    print(f"Validation error (2016-2021): linear {frozen['linear_cv_mae']:.2f}, trees {frozen['trees_cv_mae']:.2f} Bcf\n")
    print(scores[cols].round(2).to_string(index=False))
    print("\nLinear model, Bcf of weekly change per unit (refit on all weeks):")
    print(coefficients.set_index("feature")["bcf_per_unit"].round(3).to_string())
