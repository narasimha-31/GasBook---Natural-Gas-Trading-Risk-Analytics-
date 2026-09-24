"""EIA client tests using a fake HTTP session (no network, no API key needed)."""

import pandas as pd

from gasbook.ingest import eia


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeSession:
    """Serves pre-built pages and records the params of each request."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(dict(params))
        return FakeResponse(self.pages[len(self.calls) - 1])


def page(rows, total):
    return {"response": {"total": str(total), "data": rows}}


def test_pages_until_total_reached(monkeypatch):
    monkeypatch.setattr(eia, "PAGE_SIZE", 2)
    session = FakeSession([
        page([{"period": "2021-02-16", "value": "23.86"}, {"period": "2021-02-17", "value": "22.02"}], 3),
        page([{"period": "2021-02-18", "value": "14.25"}], 3),
    ])

    df = eia.fetch_henry_hub_daily(session=session, api_key="test")

    assert len(session.calls) == 2
    assert [c["offset"] for c in session.calls] == [0, 2]
    assert session.calls[0]["facets[series][]"] == "RNGWHHD"
    assert list(df.columns) == ["date", "henry_hub"]
    assert len(df) == 3


def test_cleans_types_blanks_and_duplicates():
    session = FakeSession([
        page([
            {"period": "2026-01-27", "value": "7.46"},
            {"period": "2026-01-26", "value": "30.72"},
            {"period": "2026-01-26", "value": "30.72"},
            {"period": "2026-01-28", "value": None},
        ], 4),
    ])

    df = eia.fetch_henry_hub_daily(session=session, api_key="test")

    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert df["henry_hub"].dtype == float
    assert df["date"].is_monotonic_increasing
    assert df["date"].is_unique
    assert len(df) == 2


def test_empty_response_returns_empty_frame():
    df = eia.fetch_series("x", "y", "daily", session=FakeSession([page([], 0)]), api_key="test")
    assert df.empty
    assert list(df.columns) == ["period", "value"]


def test_storage_adds_weekly_change():
    session = FakeSession([
        page([
            {"period": "2026-09-04", "value": "3208"},
            {"period": "2026-09-11", "value": "3298"},
        ], 2),
    ])

    df = eia.fetch_storage_weekly(session=session, api_key="test")

    assert session.calls[0]["facets[series][]"] == "NW2_EPG0_SWO_R48_BCF"
    assert list(df.columns) == ["week_ending", "storage_bcf", "weekly_change_bcf"]
    assert df["weekly_change_bcf"].iloc[-1] == 90


def test_citygate_returns_one_block_per_region():
    pages = [page([{"period": "2021-02", "value": "8.5"}], 1) for _ in eia.CITYGATE_SERIES]
    session = FakeSession(pages)

    df = eia.fetch_citygate_monthly(session=session, api_key="test")

    requested = [c["facets[series][]"] for c in session.calls]
    assert requested == list(eia.CITYGATE_SERIES.values())
    assert sorted(df["region"]) == sorted(eia.CITYGATE_SERIES)
    assert list(df.columns) == ["month", "region", "price_per_mcf"]
