"""EIA-ICE parser tests on a small frame shaped like the real files (no network)."""

import numpy as np
import pandas as pd
import pytest

from gasbook.ingest import eia_ice


def raw_frame():
    # Column headers copied from the real files, including the line break in "Delivery \nend date"
    return pd.DataFrame({
        "Price hub": ["Henry", "Algonquin Citygates", "Algonquin Citygates", "Algonquin Citygates", None],
        "Trade date": ["2015-01-05", "2015-01-05", "2015-01-02", "2015-01-05", "2015-01-06"],
        "Delivery start date": ["2015-01-06", "2015-01-06", "2015-01-03", "2015-01-06", "2015-01-07"],
        "Delivery \nend date": ["2015-01-06", "2015-01-06", "2015-01-05", "2015-01-06", "2015-01-07"],
        "High price $/MMBtu": [3.1, 10.75, 8.0, 10.75, 1.0],
        "Low price $/MMBtu": [2.9, 9.0, 7.0, 9.0, 1.0],
        "Wtd avg price $/MMBtu": [3.0, 9.9179, 7.6341, 9.9179, 1.0],
        "Change": [0.1, 2.2838, 1.8034, 2.2838, 0.0],
        "Daily volume MMBtu": [500000, 72100, 56300, 72100, 1],
        "Number of trades": [300, 20, 18, 20, 1],
        "Number of counterparties": [60, 12, 8, 12, 1],
    })


def test_normalize_renames_types_and_hub_names():
    df = eia_ice.normalize(raw_frame())
    assert list(df.columns) == list(eia_ice.COLUMNS.values())
    assert set(df["hub"]) == {"Henry Hub", "Algonquin Citygates"}
    assert pd.api.types.is_datetime64_any_dtype(df["delivery_start"])
    assert df["wavg"].dtype == float


def test_normalize_drops_blank_hub_and_duplicates():
    df = eia_ice.normalize(raw_frame())
    assert len(df) == 3  # blank hub row and the duplicated Algonquin day removed
    assert not df.duplicated(subset=["hub", "delivery_start"]).any()


def test_normalize_rejects_changed_file_layout():
    with pytest.raises(ValueError, match="missing columns"):
        eia_ice.normalize(raw_frame().drop(columns=["Wtd avg price $/MMBtu"]))


def test_to_wide_keeps_missing_days_empty():
    wide = eia_ice.to_wide(eia_ice.normalize(raw_frame()))
    assert list(wide.columns) == ["Algonquin Citygates", "Henry Hub"]
    assert np.isnan(wide.loc["2015-01-03", "Henry Hub"])  # no Henry trade that day: not filled in
    assert wide.loc["2015-01-06", "Algonquin Citygates"] == pytest.approx(9.9179)
