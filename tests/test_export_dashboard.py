"""Dashboard export tests: values are JSON-safe and every exported file is valid."""

import json
import math

import numpy as np
import pandas as pd
import pytest

from gasbook import export_dashboard as ex


def test_clean_handles_nan_dates_and_numpy_types():
    assert ex.clean(float("nan")) is None
    assert ex.clean(np.float64(1.23456), 2) == 1.23
    assert ex.clean(np.int64(7)) == 7
    assert ex.clean(np.bool_(True)) is True
    assert ex.clean(pd.Timestamp("2026-01-23 00:00")) == "2026-01-23"
    assert ex.clean(float("inf")) is None


def test_columns_and_records_shapes():
    df = pd.DataFrame({"date": pd.to_datetime(["2026-01-22", "2026-01-23"]), "price": [8.42, np.nan]})
    assert ex.columns(df, 2) == {"date": ["2026-01-22", "2026-01-23"], "price": [8.42, None]}
    assert ex.records(df)[1] == {"date": "2026-01-23", "price": None}


@pytest.mark.skipif(not (ex.REPORTS / "var_backtest_summary.csv").exists(), reason="reports not generated")
def test_every_export_is_valid_json_with_meta(tmp_path):
    ex.write_all(tmp_path)
    for name in ex.EXPORTS:
        data = json.loads((tmp_path / f"{name}.json").read_text())
        assert {"title", "source", "period", "simulated"} <= set(data["meta"])
        text = json.dumps(data)
        assert "NaN" not in text and "Infinity" not in text
        for v in data.get("headline", {}).values():
            assert not (isinstance(v, float) and math.isnan(v))
