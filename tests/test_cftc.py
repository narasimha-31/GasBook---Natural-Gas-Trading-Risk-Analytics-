"""CFTC client tests with a fake HTTP session (no network)."""

import pytest

from gasbook.ingest import cftc


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(dict(params))
        return FakeResponse(self.pages[len(self.calls) - 1])


def row(date, oi, long_, short):
    return {
        "report_date_as_yyyy_mm_dd": f"{date}T00:00:00.000",
        "open_interest_all": str(oi),
        "m_money_positions_long_all": str(long_),
        "m_money_positions_short_all": str(short),
        "m_money_positions_spread": "0",
        "prod_merc_positions_long": "0",
        "prod_merc_positions_short": "0",
    }


def test_filters_to_nymex_contract_and_computes_net():
    session = FakeSession([[row("2026-09-15", 1_000_000, 200_000, 300_000), row("2026-09-08", 900_000, 250_000, 150_000)]])

    df = cftc.fetch_positioning(session=session)

    assert "023651" in session.calls[0]["$where"]
    assert list(df["report_date"].dt.strftime("%Y-%m-%d")) == ["2026-09-08", "2026-09-15"]
    assert list(df["mm_net"]) == [100_000, -100_000]
    assert df["mm_net_pct_oi"].iloc[-1] == pytest.approx(-0.1)


def test_pages_until_short_page(monkeypatch):
    monkeypatch.setattr(cftc, "PAGE_SIZE", 2)
    session = FakeSession([
        [row("2026-09-01", 10, 5, 1), row("2026-09-08", 10, 5, 2)],
        [row("2026-09-15", 10, 5, 3)],
    ])

    df = cftc.fetch_positioning(session=session)

    assert [c["$offset"] for c in session.calls] == [0, 2]
    assert len(df) == 3


def test_empty_response():
    df = cftc.fetch_positioning(session=FakeSession([[]]))
    assert df.empty
    assert "mm_net" in df.columns
