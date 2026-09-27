-- GasBook trade database, laid out like a small ETRM (trading system).
-- Dimension tables: hubs, counterparties. Fact tables: trades, prices, confirmations.

DROP TABLE IF EXISTS confirmations;
DROP TABLE IF EXISTS trades;
DROP TABLE IF EXISTS prices;
DROP TABLE IF EXISTS counterparties;
DROP TABLE IF EXISTS hubs;

CREATE TABLE hubs (
    hub_id          TEXT PRIMARY KEY,
    hub_name        TEXT NOT NULL,
    region          TEXT NOT NULL,
    price_source    TEXT NOT NULL
);

CREATE TABLE counterparties (
    counterparty_id     TEXT PRIMARY KEY,
    name                TEXT NOT NULL,            -- fictional, never a real company
    type                TEXT NOT NULL,            -- producer, utility, lng_feedgas, power, industrial, marketer
    credit_rating       TEXT NOT NULL,
    credit_limit_usd    NUMERIC(14, 2) NOT NULL CHECK (credit_limit_usd >= 0),
    contract            TEXT NOT NULL,            -- e.g. NAESB Base Contract (2006)
    payment_terms       TEXT NOT NULL,
    payment_delay_days  INTEGER NOT NULL DEFAULT 0 CHECK (payment_delay_days >= 0),  -- days late after the 25th
    default_date        DATE,                     -- simulated default, NULL if none
    status              TEXT NOT NULL             -- active, commissioning, disputed
);

CREATE TABLE trades (
    trade_id                TEXT PRIMARY KEY,
    trade_date              DATE NOT NULL,
    counterparty_id         TEXT NOT NULL REFERENCES counterparties (counterparty_id),
    hub_id                  TEXT NOT NULL REFERENCES hubs (hub_id),
    buy_sell                TEXT NOT NULL CHECK (buy_sell IN ('buy', 'sell')),
    delivery_start          DATE NOT NULL,
    delivery_end            DATE NOT NULL,
    volume_mmbtu_per_day    INTEGER NOT NULL CHECK (volume_mmbtu_per_day > 0),
    price_type              TEXT NOT NULL CHECK (price_type IN ('fixed', 'index')),
    fixed_price             NUMERIC(10, 4),       -- $/MMBtu, fixed-price deals only
    index_name              TEXT,                 -- index deals only
    index_adder             NUMERIC(10, 4),       -- $/MMBtu added to the index, index deals only
    trader                  TEXT NOT NULL,
    CHECK (delivery_end >= delivery_start),
    CHECK ((price_type = 'fixed' AND fixed_price IS NOT NULL AND index_name IS NULL)
        OR (price_type = 'index' AND fixed_price IS NULL AND index_name IS NOT NULL))
);

CREATE TABLE prices (
    price_date      DATE NOT NULL,
    series          TEXT NOT NULL,                -- henry_hub_spot, ng_front_month
    price           NUMERIC(10, 4) NOT NULL,
    source          TEXT NOT NULL,
    PRIMARY KEY (price_date, series)
);

-- Counterparty confirmations as received (simulated). Their own reference, their side of the deal.
CREATE TABLE confirmations (
    confirm_ref             TEXT PRIMARY KEY,
    counterparty_id         TEXT NOT NULL REFERENCES counterparties (counterparty_id),
    their_side              TEXT NOT NULL CHECK (their_side IN ('buy', 'sell')),
    trade_date              DATE NOT NULL,
    confirm_date            DATE NOT NULL,
    delivery_start          DATE NOT NULL,
    delivery_end            DATE NOT NULL,
    volume_mmbtu_per_day    INTEGER NOT NULL CHECK (volume_mmbtu_per_day > 0),
    price_type              TEXT NOT NULL CHECK (price_type IN ('fixed', 'index')),
    fixed_price             NUMERIC(10, 4),
    index_adder             NUMERIC(10, 4)
);

CREATE INDEX trades_trade_date_idx ON trades (trade_date);
CREATE INDEX trades_counterparty_idx ON trades (counterparty_id);
CREATE INDEX trades_delivery_idx ON trades (delivery_start, delivery_end);
CREATE INDEX confirmations_trade_date_idx ON confirmations (trade_date);
