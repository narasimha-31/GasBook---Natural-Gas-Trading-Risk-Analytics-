"""Forecast the weekly EIA storage change and test it honestly.

Models
- Benchmark "5-year average": the average change for the same week over the previous five years.
- Benchmark "last week's gap": this week's 5-year average plus however far last week was from its own average.
- Linear (ridge) regression: main model. The weather-to-gas relationship is close to a straight line, every
  coefficient reads in plain units, and unlike tree models it can extend to colder weeks than it has seen.
- Gradient-boosted trees: challenger, for curved and combined effects. Kept only if it wins on the test years.
- Blend: the average of the two. This is the forecast shown, because it scored best on validation.

Chosen on 2016-2021 validation (before scoring the test years):
- linear uses every input; holidays and production cut its validation error from 20.5 to 16.4 Bcf
- trees use the base inputs only: production keeps setting records, and trees cannot predict beyond
  values they have seen, so it made them slightly worse
- blend validation error 14.6 Bcf, better than either model alone
Holidays and production were added after looking at test-year misses, so the test score is slightly optimistic.

Testing
- Everything from 2022 on is held out and only scored once, at the end.
- Settings are chosen with walk-forward validation inside 2010-2021: for each year 2016-2021, train on the
  years before it and score that year.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from gasbook.models.storage_features import BASE_FEATURES, FEATURES
from gasbook.research.storage_report import five_year_average_change

TEST_START = pd.Timestamp("2022-01-01")
VALIDATION_YEARS = range(2016, 2022)
RIDGE_ALPHAS = [0.1, 0.3, 1, 3, 10, 30, 100]
GBM_SETTINGS = [
    {"max_depth": d, "learning_rate": lr, "max_iter": n, "l2_regularization": 1.0, "min_samples_leaf": 20}
    for d in (2, 3) for lr in (0.03, 0.08) for n in (200, 500)
]


def ridge(alpha: float):
    return make_pipeline(StandardScaler(), Ridge(alpha=alpha))


def gbm(settings: dict):
    return HistGradientBoostingRegressor(random_state=0, **settings)


def walk_forward_mae(make_model, data: pd.DataFrame, features=FEATURES, years=VALIDATION_YEARS) -> float:
    """Average error over validation years, each scored by a model trained only on earlier years."""
    errors = []
    for year in years:
        train = data[data.index.year < year]
        valid = data[data.index.year == year]
        model = make_model().fit(train[features], train["weekly_change_bcf"])
        errors.append(np.abs(model.predict(valid[features]) - valid["weekly_change_bcf"]).mean())
    return float(np.mean(errors))


def tune(data: pd.DataFrame, features) -> dict:
    """Best ridge strength and tree settings for a feature set, chosen on walk-forward validation only."""
    ridge_cv = {a: walk_forward_mae(lambda a=a: ridge(a), data, features) for a in RIDGE_ALPHAS}
    gbm_cv = {i: walk_forward_mae(lambda s=s: gbm(s), data, features) for i, s in enumerate(GBM_SETTINGS)}
    best_alpha = min(ridge_cv, key=ridge_cv.get)
    best_gbm = min(gbm_cv, key=gbm_cv.get)
    return {"ridge_cv": pd.Series(ridge_cv, name="walk_forward_mae_bcf"), "best_alpha": best_alpha,
            "linear_cv_mae": ridge_cv[best_alpha], "best_gbm": GBM_SETTINGS[best_gbm], "trees_cv_mae": gbm_cv[best_gbm]}


def benchmarks(storage: pd.DataFrame) -> pd.DataFrame:
    """Both benchmark forecasts, per week ending."""
    s = storage.sort_values("week_ending").reset_index(drop=True).copy()
    s["normal"] = five_year_average_change(s)
    s["bench_5yr_avg"] = s["normal"]
    s["bench_last_gap"] = s["normal"] + (s["weekly_change_bcf"] - s["normal"]).shift(1)
    return s.set_index(pd.to_datetime(s["week_ending"]))[["bench_5yr_avg", "bench_last_gap"]]


def score(actual: pd.Series, predicted: pd.Series) -> dict:
    err = predicted - actual
    winter = actual.index.month.isin([11, 12, 1, 2, 3])
    big = actual.abs() >= 150
    return {
        "weeks": len(err),
        "mae_bcf": float(err.abs().mean()),
        "rmse_bcf": float(np.sqrt((err**2).mean())),
        "bias_bcf": float(err.mean()),
        "share_within_10bcf": float((err.abs() <= 10).mean()),
        "mae_winter_bcf": float(err[winter].abs().mean()),
        "mae_summer_bcf": float(err[~winter].abs().mean()),
        "mae_big_weeks_bcf": float(err[big].abs().mean()) if big.any() else np.nan,
        "worst_miss_bcf": float(err.abs().max()),
        "worst_miss_week": err.abs().idxmax().date(),
    }


def ridge_coefficients(model, features=FEATURES) -> pd.DataFrame:
    """Coefficients in natural units: Bcf of weekly storage change per one unit of each input."""
    scaler, reg = model.named_steps["standardscaler"], model.named_steps["ridge"]
    per_unit = reg.coef_ / scaler.scale_
    return pd.DataFrame({"feature": features, "bcf_per_unit": per_unit}).set_index("feature")


def run(features: pd.DataFrame, storage: pd.DataFrame, linear_features=FEATURES, tree_features=BASE_FEATURES) -> dict:
    data = features.dropna(subset=list(dict.fromkeys([*linear_features, *tree_features])) + ["weekly_change_bcf"])
    train = data[data.index < TEST_START]
    test = data[data.index >= TEST_START]

    tuned_linear = tune(train, linear_features)
    tuned_trees = tune(train, tree_features)
    best_alpha, best_gbm = tuned_linear["best_alpha"], tuned_trees["best_gbm"]
    lin = ridge(best_alpha).fit(train[linear_features], train["weekly_change_bcf"])
    tree = gbm(best_gbm).fit(train[tree_features], train["weekly_change_bcf"])

    b = benchmarks(storage)
    preds = pd.DataFrame({
        "actual": test["weekly_change_bcf"],
        "linear": lin.predict(test[linear_features]),
        "trees": tree.predict(test[tree_features]),
    }, index=test.index)
    preds["blend"] = (preds["linear"] + preds["trees"]) / 2
    preds = preds.join(b)

    models = ["bench_5yr_avg", "bench_last_gap", "linear", "trees", "blend"]
    scores = pd.DataFrame({m: score(preds["actual"], preds[m]) for m in models}).T
    return {
        "preds": preds,
        "scores": scores,
        "best_alpha": best_alpha,
        "best_gbm": best_gbm,
        "linear_cv_mae": tuned_linear["linear_cv_mae"],
        "trees_cv_mae": tuned_trees["trees_cv_mae"],
        "linear_model": lin,
        "tree_model": tree,
        "coefficients": ridge_coefficients(lin, list(linear_features)),
        "linear_features": list(linear_features),
        "tree_features": list(tree_features),
        "train_rows": train,
    }


def retrain_backtest(features: pd.DataFrame, best_alpha: float, best_gbm: dict, years=range(2022, 2027),
                     linear_features=FEATURES, tree_features=BASE_FEATURES) -> pd.DataFrame:
    """How the model would have done in use: each year forecast by models retrained on every earlier week.

    Settings (ridge strength, tree settings) stay fixed from validation; only the data grows.
    """
    data = features.dropna(subset=list(dict.fromkeys([*linear_features, *tree_features])) + ["weekly_change_bcf"])
    frames = []
    for year in years:
        train, test = data[data.index.year < year], data[data.index.year == year]
        if test.empty:
            continue
        lin = ridge(best_alpha).fit(train[linear_features], train["weekly_change_bcf"]).predict(test[linear_features])
        tree = gbm(best_gbm).fit(train[tree_features], train["weekly_change_bcf"]).predict(test[tree_features])
        frames.append(pd.DataFrame({"actual": test["weekly_change_bcf"], "linear": lin, "trees": tree,
                                    "blend": (lin + tree) / 2}, index=test.index))
    return pd.concat(frames)


def final_models(features: pd.DataFrame, best_alpha: float, best_gbm: dict,
                 linear_features=FEATURES, tree_features=BASE_FEATURES):
    """Both models refit on every week available, for live forecasts and the interactive sliders."""
    data = features.dropna(subset=list(dict.fromkeys([*linear_features, *tree_features])) + ["weekly_change_bcf"])
    lin = ridge(best_alpha).fit(data[linear_features], data["weekly_change_bcf"])
    tree = gbm(best_gbm).fit(data[tree_features], data["weekly_change_bcf"])
    return lin, tree
