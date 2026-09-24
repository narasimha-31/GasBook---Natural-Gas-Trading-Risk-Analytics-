"""Storage report tests: 5-year normal, report-day alignment, and contract roll flags."""

import numpy as np
import pandas as pd
import pytest

from gasbook.ingest.futures import expiry_dates, near_expiry
from gasbook.research import storage_report as sr


def storage_frame(years=range(2015, 2022), bump_2021=0.0):
    rows = []
    for y in years:
        for d in pd.date_range(f"{y}-01-01", f"{y}-12-31", freq="W-FRI"):
            change = 10.0 + (bump_2021 if y == 2021 else 0.0)
            rows.append({"week_ending": d, "weekly_change_bcf": change})
    return pd.DataFrame(rows)


def test_five_year_average_needs_five_prior_years():
    s = storage_frame()
    avg = sr.five_year_average_change(s)
    assert avg[s["week_ending"] < "2020-01-01"].isna().all()
    assert avg[s["week_ending"].dt.year == 2020].eq(10.0).all()


def test_five_year_average_picks_nearest_friday_to_same_date():
    # Give every report a unique value (its day number) so the average reveals exactly which reports were used.
    s = storage_frame()
    s["weekly_change_bcf"] = (s["week_ending"] - pd.Timestamp("2000-01-01")).dt.days * 1.0
    avg = sr.five_year_average_change(s)
    # Nearest Friday to Jan 1 of 2020, 2019, 2018, 2017, 2016 (some fall in late December of the prior year)
    expected_dates = pd.to_datetime(["2020-01-03", "2019-01-04", "2017-12-29", "2016-12-30", "2016-01-01"])
    expected = np.mean((expected_dates - pd.Timestamp("2000-01-01")).days)
    new_year = s.index[s["week_ending"] == "2021-01-01"][0]
    assert avg[new_year] == pytest.approx(expected)


def test_vs_normal_and_report_day_move():
    s = storage_frame(bump_2021=25.0)  # 2021 builds are 25 Bcf above normal every week
    days = pd.bdate_range("2014-12-01", "2022-03-01")
    fut = pd.DataFrame({"date": days, "close": np.exp(np.arange(len(days)) * 0.001)})
    ev = sr.build_weeks(s, fut)

    # 2021-12-31's "one year ago" report is 2021-01-01 (52 weeks back, itself bumped), so stop before it
    e2021 = ev[(ev["week_ending"] >= "2021-01-01") & (ev["week_ending"] <= "2021-12-24")]
    assert e2021["vs_normal_bcf"].round(6).eq(25.0).all()
    assert (ev["report_date"] - ev["week_ending"]).dt.days.ge(6).all()  # never before Thursday
    assert ev["report_date"].dt.dayofweek.le(4).all()
    assert ev["move_report_day"].round(6).eq(0.001).all()  # one trading day of the synthetic 0.1%/day trend


def test_expiry_is_three_business_days_before_month_start():
    exp = expiry_dates("2026-02-01", "2026-03-15")
    assert pd.Timestamp("2026-02-25") in exp  # March 2026 contract: Mar 1 is Sunday -> Feb 25 (Wed)


def test_near_expiry_flags_window():
    dates = pd.Series(pd.to_datetime(["2026-02-25", "2026-02-26", "2026-02-27"]))
    assert near_expiry(dates).tolist() == [True, True, False]
