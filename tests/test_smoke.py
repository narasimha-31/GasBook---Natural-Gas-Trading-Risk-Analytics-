import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_package_imports():
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    import gasbook

    assert gasbook.__version__


def test_reference_data_has_sources():
    for name in ("lng_terminals.csv", "lng_events.csv", "gas_consumption_by_sector_2025.csv"):
        with open(ROOT / "data" / "reference" / name, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert rows, f"{name} is empty"
        assert all(r["source_url"].startswith("https://") for r in rows), f"{name} has a row without a source"
