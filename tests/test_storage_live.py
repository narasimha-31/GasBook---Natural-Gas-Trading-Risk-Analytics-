"""Live storage forecast tests: weather merge, range from past misses, chained projection, forecast log."""

import numpy as np
import pandas as pd
import pytest

from gasbook.models import storage_live as live
from gasbook.models.storage_features import BASE_FEATURES, FEATURES, REGIONS

CITIES = {"A": "East", "B": "Midwest", "C": "South Central", "D": "Mountain", "E": "Pacific"}


def daily(start, end, hdd=2.0, cdd=1.0):
    rows = [{"date": d, "city": c, "region": r, "hdd": hdd, "cdd": cdd}
            for d in pd.date_range(start, end) for c, r in CITIES.items()]
    return pd.DataFrame(rows)


class Echo:
    """Stand-in model: predicts last week's change plus a fixed step, to check chaining."""

    def __init__(self, features, step):
        self.features, self.step = features, step

    def predict(self, x):
        assert list(x.columns) == self.features
        return x["change_prev_bcf"].to_numpy() + self.step


def test_combine_weather_prefers_observed_days():
    obs = daily("2026-09-01", "2026-09-10")
    fc = daily("2026-09-08", "2026-09-20", hdd=99.0)
    w = live.combine_weather(obs, fc)
    assert not w.duplicated(["city", "date"]).any()
    assert w.loc[w["date"] <= "2026-09-10", "hdd"].eq(2.0).all()
    assert w.loc[w["date"] > "2026-09-10", "source"].eq("forecast").all()


def test_error_range_uses_past_misses():
    bt = pd.DataFrame({"actual": np.zeros(11), "blend": np.arange(-5, 6, dtype=float)})
    low, high = live.error_range(bt)
    assert low == pytest.approx(-4.0) and high == pytest.approx(4.0)


def test_forecast_weeks_chains_projection_and_reports_range():
    storage = pd.DataFrame({"week_ending": pd.to_datetime(["2026-09-11", "2026-09-18"]),
                            "storage_bcf": [3298.0, 3351.0], "weekly_change_bcf": [60.0, 53.0]})
    weather = pd.concat([daily("2026-09-12", "2026-09-22").assign(source="observed"),
                         daily("2026-09-23", "2026-10-02").assign(source="forecast")])
    monthly = pd.DataFrame({"month": pd.date_range("2026-01-01", periods=6, freq="MS")})
    lng = monthly.assign(lng_exports_bcfd=16.0)
    prod = monthly.assign(production_bcfd=108.0)
    out = live.forecast_weeks(storage, weather, lng, prod, Echo(FEATURES, 10.0), Echo(BASE_FEATURES, 20.0), (-5.0, 8.0))

    assert list(out["kind"]) == ["next report", "projection"]
    assert out["report_date"].iloc[0] == pd.Timestamp("2026-10-01").date()  # Thursday after week ending Sep 25
    first = (53 + 10 + 53 + 20) / 2
    assert out["forecast_bcf"].iloc[0] == pytest.approx(first)
    assert out["forecast_bcf"].iloc[1] == pytest.approx(first + 15)  # chained on the first week's forecast
    assert out["low_bcf"].iloc[0] == pytest.approx(first - 8) and out["high_bcf"].iloc[0] == pytest.approx(first + 5)
    assert out["forecast_weather_share"].iloc[0] == pytest.approx(3 / 7, abs=0.01)  # Sep 23-25 of Sep 19-25
    assert out["hdd_total"].iloc[0] == pytest.approx(2.0 * 7 * len(REGIONS))


def test_forecast_weeks_refuses_missing_weather():
    storage = pd.DataFrame({"week_ending": pd.to_datetime(["2026-09-18"]), "storage_bcf": [3351.0],
                            "weekly_change_bcf": [53.0]})
    monthly = pd.DataFrame({"month": pd.date_range("2026-01-01", periods=6, freq="MS")})
    with pytest.raises(ValueError, match="weather"):
        live.forecast_weeks(storage, daily("2026-09-12", "2026-09-22").assign(source="observed"),
                            monthly.assign(lng_exports_bcfd=16.0), monthly.assign(production_bcfd=108.0),
                            Echo(FEATURES, 0), Echo(BASE_FEATURES, 0), (-1.0, 1.0), n_weeks=1)


def test_update_log_is_idempotent_and_scores_actuals():
    new = pd.DataFrame({"week_ending": [pd.Timestamp("2026-09-25").date()], "report_date": ["2026-10-01"],
                        "kind": ["next report"], "forecast_bcf": [79.1], "low_bcf": [60.6], "high_bcf": [103.6],
                        "forecast_weather_share": [0.57]})
    storage = pd.DataFrame({"week_ending": pd.to_datetime(["2026-09-18"]), "weekly_change_bcf": [53.0]})
    day = pd.Timestamp("2026-09-27")
    log = live.update_log(pd.DataFrame(), new, storage, day)
    log = live.update_log(log, new, storage, day)  # same day again: no duplicate
    assert len(log) == 1 and log["actual_bcf"].isna().all()

    reported = pd.concat([storage, pd.DataFrame({"week_ending": [pd.Timestamp("2026-09-25")], "weekly_change_bcf": [85.0]})])
    log = live.update_log(log, new.iloc[0:0], reported, pd.Timestamp("2026-10-02"))
    assert log["actual_bcf"].iloc[0] == 85.0
    assert log["miss_bcf"].iloc[0] == pytest.approx(-5.9)


def test_shift_forecast_days_leaves_observed_days_alone():
    w = pd.concat([daily("2026-09-12", "2026-09-14").assign(source="observed", mean_temp_f=70.0),
                   daily("2026-09-15", "2026-09-16").assign(source="forecast", mean_temp_f=70.0)])
    out = live.shift_forecast_days(w, -10)
    assert out.loc[out["source"] == "observed", "mean_temp_f"].eq(70.0).all()
    ahead = out[out["source"] == "forecast"]
    assert ahead["mean_temp_f"].eq(60.0).all() and ahead["hdd"].eq(5.0).all() and ahead["cdd"].eq(0.0).all()
