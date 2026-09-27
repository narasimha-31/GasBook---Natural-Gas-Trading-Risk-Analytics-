"""Storage forecast tests: week alignment, no look-ahead, holiday flags, and that the models learn a known rule."""

import numpy as np
import pandas as pd
import pytest

from gasbook.models import storage_features as sf
from gasbook.models import storage_forecast as sm


def daily_weather(start, end, temp_by_date=None):
    days = pd.date_range(start, end)
    rows = []
    for city, (_, _, region) in {"Chicago": (0, 0, "Midwest"), "Boston": (0, 0, "East")}.items():
        for d in days:
            t = (temp_by_date or {}).get(d.strftime("%Y-%m-%d"), 65.0)
            rows.append({"date": d, "city": city, "region": region, "hdd": max(0.0, 65 - t), "cdd": max(0.0, t - 65)})
    return pd.DataFrame(rows)


def test_degree_days_sum_saturday_to_friday():
    # One cold day (Saturday) belongs to the week ending the following Friday, not the week before
    w = daily_weather("2026-01-03", "2026-01-16", {"2026-01-10": 15.0})  # Jan 10 2026 is a Saturday
    out = sf.weekly_degree_days(w, pd.Series(pd.to_datetime(["2026-01-09", "2026-01-16"])))
    assert out.loc["2026-01-09", "hdd_Midwest"] == 0
    assert out.loc["2026-01-16", "hdd_Midwest"] == pytest.approx(50.0)


def test_partial_weeks_are_left_empty():
    w = daily_weather("2026-01-12", "2026-01-16")  # only Monday-Friday of the week
    out = sf.weekly_degree_days(w, pd.Series(pd.to_datetime(["2026-01-16"])))
    assert np.isnan(out.loc["2026-01-16", "hdd_East"])


def test_monthly_data_uses_only_published_months():
    monthly = pd.DataFrame({"month": pd.date_range("2026-01-01", "2026-09-01", freq="MS"),
                            "lng_exports_bcfd": np.arange(1.0, 10.0)})
    v = sf.monthly_available(monthly, "lng_exports_bcfd", pd.Series(pd.to_datetime(["2026-09-11"])))
    assert v.iloc[0] == 6.0  # a week in September sees June (value 6), never July-September


def test_holiday_flags_2023():
    weeks = pd.Series(pd.to_datetime(["2023-11-24", "2023-12-01", "2023-12-29", "2024-01-05"]))
    h = sf.holiday_weeks(weeks)
    assert h["thanksgiving_week"].tolist() == [1, 0, 0, 0]  # Thanksgiving 2023: Thursday Nov 23
    assert h["christmas_week"].tolist() == [0, 0, 1, 0]
    assert h["new_year_week"].tolist() == [0, 0, 0, 1]


def test_walk_forward_trains_only_on_earlier_years():
    idx = pd.date_range("2014-01-03", "2021-12-31", freq="W-FRI")
    rng = np.random.default_rng(0)
    data = pd.DataFrame(rng.normal(size=(len(idx), len(sf.FEATURES))), columns=sf.FEATURES, index=idx)
    data["weekly_change_bcf"] = -2.0 * data["hdd_East"] + rng.normal(0, 0.1, len(idx))
    seen = []

    class Spy:
        def fit(self, X, y):
            seen.append(X.index.max().year)
            self.m = sm.ridge(1.0).fit(X, y)
            return self

        def predict(self, X):
            return self.m.predict(X)

    sm.walk_forward_mae(Spy, data, years=range(2016, 2019))
    assert seen == [2015, 2016, 2017]


def test_linear_model_recovers_a_known_weather_rule():
    idx = pd.date_range("2010-01-01", periods=600, freq="W-FRI")
    rng = np.random.default_rng(1)
    X = pd.DataFrame(rng.uniform(0, 300, size=(600, len(sf.FEATURES))), columns=sf.FEATURES, index=idx)
    y = -0.4 * X["hdd_East"] + rng.normal(0, 1, 600)
    model = sm.ridge(0.1).fit(X, y)
    coef = sm.ridge_coefficients(model)["bcf_per_unit"]
    assert coef["hdd_East"] == pytest.approx(-0.4, abs=0.02)
    assert coef.drop("hdd_East").abs().max() < 0.05
