"""Storm Watch tests on small hand-built weather and price series."""

import pandas as pd

from gasbook.book import storm_watch as sw


def weather(midland, houston, gust=None):
    days = pd.date_range("2026-01-20", periods=len(midland))
    rows = [{"date": d, "site": sw.MIDLAND, "min_temp_f": m, "max_gust_mph": 20.0} for d, m in zip(days, midland)]
    rows += [{"date": d, "site": sw.HOUSTON, "min_temp_f": h, "max_gust_mph": g}
             for d, h, g in zip(days, houston, gust or [20.0] * len(days))]
    return pd.DataFrame(rows)


def test_alert_levels_follow_the_rules():
    a = sw.daily_alerts(weather([40, 18, 5, 40], [50, 45, 40, 24]))
    assert a["level"].tolist() == ["none", "watch", "warning", "warning"]
    assert "Houston" in a["reason"].iloc[3]


def test_hurricane_gusts_trigger_a_warning():
    a = sw.daily_alerts(weather([80, 80], [80, 80], gust=[30, 90]))
    assert a["level"].tolist() == ["none", "warning"]
    assert "gusts" in a["reason"].iloc[1]


def test_spike_events_group_nearby_days():
    idx = pd.bdate_range("2025-11-03", periods=60)
    spot = pd.Series(3.0, index=idx)
    spot.iloc[40] = 6.0   # +100% day
    spot.iloc[41] = 9.0   # still a spike, same event
    ev = sw.spike_events(spot)
    assert len(ev) == 1
    assert ev["peak_price"].iloc[0] == 9.0
    assert ev["price_before"].iloc[0] == 3.0


def test_warned_looks_forward_from_the_spike_day():
    a = sw.daily_alerts(weather([40, 40, 40, 5, 40], [50, 50, 50, 50, 50]))  # cold arrives Jan 23
    assert sw.warned(a, pd.Timestamp("2026-01-20"), lookahead=7)      # spike 3 days before the cold: warned
    assert not sw.warned(a, pd.Timestamp("2026-01-24"), lookahead=7)  # cold already passed


def test_forecast_notice_counts_days_before_the_spike():
    # Freeze on Jan 26. The 5-day-ahead forecast (issued Jan 21) saw it; the 7-day one (issued Jan 19) did not.
    rows = [{"date": pd.Timestamp("2026-01-26"), "site": sw.MIDLAND, "min_temp_f": temp, "lead_days": lead}
            for lead, temp in ((7, 30.0), (5, 6.0), (1, 3.0))]
    past = pd.DataFrame(rows)
    assert sw.forecast_notice(past, pd.Timestamp("2026-01-23")) == 2     # issued Jan 21, spike Jan 23
    assert sw.forecast_notice(past, pd.Timestamp("2026-01-20")) is None  # no warning issued by Jan 20
