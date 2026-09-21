"""Project paths and settings loaded from the local .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_REFERENCE = ROOT / "data" / "reference"

load_dotenv(ROOT / ".env")


def eia_api_key() -> str:
    key = os.getenv("EIA_API_KEY", "")
    if not key or key == "your_key_here":
        raise RuntimeError(
            "EIA_API_KEY is not set. Copy .env.example to .env and paste your free key "
            "from https://www.eia.gov/opendata/register.php"
        )
    return key
