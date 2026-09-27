"""Weather parsing tests with fake Open-Meteo responses (no network)."""

import pandas as pd

from gasbook.ingest import weather


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params)))
        return FakeResponse(self.payload)


def test_forecast_returns_one_row_per_site_and_day():
    payload = {"daily": {"time": ["2026-01-25", "2026-01-26"], "temperature_2m_min": [9.0, 3.5],
                         "wind_gusts_10m_max": [30.0, 25.0]}}
    session = FakeSession(payload)
    df = weather.forecast(session=session, days=2)
    assert len(df) == 2 * len(weather.SITES)
    assert set(df["site"]) == set(weather.SITES)
    assert session.calls[0][1]["temperature_unit"] == "fahrenheit"


def test_past_forecasts_take_the_daily_minimum_per_lead():
    payload = {"hourly": {"time": ["2026-01-26T00:00", "2026-01-26T06:00"],
                          "temperature_2m_previous_day1": [10.0, 4.0],
                          "temperature_2m_previous_day5": [12.0, 8.0]}}
    df = weather.past_forecasts("2026-01-26", "2026-01-26", leads=(1, 5), session=FakeSession(payload))
    one_site = df[df["site"] == next(iter(weather.SITES))]
    got = one_site.set_index("lead_days")["min_temp_f"].to_dict()
    assert got == {1: 4.0, 5: 8.0}
    assert (df["date"] == pd.Timestamp("2026-01-26")).all()
