"""Demand-city weather tests (no network)."""

import pandas as pd
import pytest

from gasbook.ingest import demand_weather as dw


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
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return FakeResponse(self.payload)


def test_degree_days_split_around_65f():
    dd = dw.degree_days(pd.Series([20.0, 65.0, 80.0]))
    assert dd["hdd"].tolist() == [45.0, 0.0, 0.0]
    assert dd["cdd"].tolist() == [0.0, 0.0, 15.0]


def test_observed_returns_every_city_with_its_region():
    payload = {"daily": {"time": ["2026-01-25", "2026-01-26"], "temperature_2m_mean": [10.0, 70.0]}}
    session = FakeSession(payload)
    df = dw.observed("2026-01-25", "2026-01-26", session=session)
    assert session.calls == len(dw.CITIES)
    assert set(df["region"]) == {"East", "Midwest", "South Central", "Mountain", "Pacific"}
    chicago = df[df["city"] == "Chicago"].set_index("date")
    assert chicago.loc["2026-01-25", "hdd"] == pytest.approx(55.0)
    assert chicago.loc["2026-01-26", "cdd"] == pytest.approx(5.0)
