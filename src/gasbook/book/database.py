"""Build the PostgreSQL trade database: create it if needed, apply the schema, load hubs, counterparties,
real prices, and the simulated trades.

Connection settings come from .env (PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD).
Run: python -m gasbook.book.database
"""

import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine

from gasbook import config  # noqa: F401  (loads .env)
from gasbook.book import confirmations, simulate
from gasbook.config import DATA_RAW

SCHEMA = Path(__file__).with_name("schema.sql")


def connection_url(database: str | None = None) -> URL:
    password = os.getenv("PGPASSWORD", "")
    if not password or password == "your_password_here":
        raise RuntimeError("PGPASSWORD is not set in .env")
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("PGUSER", "postgres"),
        password=password,
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        database=database or os.getenv("PGDATABASE", "gasbook"),
    )


def ensure_database() -> None:
    """Create the gasbook database if it does not exist (connects to the default 'postgres' database)."""
    name = os.getenv("PGDATABASE", "gasbook")
    admin = create_engine(connection_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()


def load_prices() -> pd.DataFrame:
    hh = pd.read_csv(DATA_RAW / "henry_hub_daily.csv", parse_dates=["date"])
    ng = pd.read_csv(DATA_RAW / "ng_front_month.csv", parse_dates=["date"])
    return pd.concat([
        pd.DataFrame({"price_date": hh["date"], "series": "henry_hub_spot", "price": hh["henry_hub"],
                      "source": "EIA API RNGWHHD"}),
        pd.DataFrame({"price_date": ng["date"], "series": "ng_front_month", "price": ng["close"],
                      "source": "NYMEX NG=F via yfinance"}),
    ], ignore_index=True)


def build(engine: Engine, trades: pd.DataFrame, prices: pd.DataFrame, confirms: pd.DataFrame) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(SCHEMA.read_text())
        simulate.HUBS.to_sql("hubs", conn, if_exists="append", index=False)
        simulate.COUNTERPARTIES.to_sql("counterparties", conn, if_exists="append", index=False)
        prices.to_sql("prices", conn, if_exists="append", index=False, chunksize=5_000)
        trades.to_sql("trades", conn, if_exists="append", index=False, chunksize=5_000)
        confirms.to_sql("confirmations", conn, if_exists="append", index=False, chunksize=5_000)


if __name__ == "__main__":
    futures = pd.read_csv(DATA_RAW / "ng_front_month.csv", parse_dates=["date"])
    trades = simulate.generate_trades(futures)
    ensure_database()
    engine = create_engine(connection_url())
    confirms, _answer_key = confirmations.generate(trades, list(simulate.COUNTERPARTIES["counterparty_id"]))
    build(engine, trades, load_prices(), confirms)
    with engine.connect() as conn:
        counts = {t: conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                  for t in ("hubs", "counterparties", "prices", "trades", "confirmations")}
    print("Loaded:", counts)
    print(trades.groupby(["buy_sell", "price_type"]).size().rename("trades").to_string())
