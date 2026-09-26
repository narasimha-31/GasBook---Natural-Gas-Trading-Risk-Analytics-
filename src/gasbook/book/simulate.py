"""Generate the simulated trading book from real prices.

What is simulated: the trades and the counterparties (real trades are confidential).
What is real: every price. Fixed-price deals use the NYMEX front-month futures close on the trade date
(plus a small dealer margin); index deals settle on the EIA Henry Hub daily spot price.

Scope, kept honest:
- One hub: Henry Hub, the only hub with free daily prices through 2026. No other hub prices are invented.
- Every deal is for next-month delivery (the contract the front-month futures price refers to).
- Counterparty names are generic and fictional. They are never real companies.
"""

import numpy as np
import pandas as pd

SEED = 2026
START, END = "2025-01-02", "2026-08-31"
HUB = "HH"
TRADERS = ["Trader 1", "Trader 2", "Trader 3"]
VOLUMES = [2_500, 5_000, 7_500, 10_000, 15_000, 20_000]  # MMBtu/day, typical physical deal sizes
TRADES_PER_DAY = (0, 4)  # inclusive range of new deals per business day
FIXED_SHARE = 0.6
DEALER_MARGIN = 0.03  # $/MMBtu: we buy slightly below and sell slightly above the screen price
# Risk policy: net fixed-price position per delivery month must stay within +/- this many MMBtu/day.
# A fixed-price deal that would break the limit is done in the opposite direction instead (a hedge).
POSITION_LIMIT = 25_000

HUBS = pd.DataFrame([{
    "hub_id": HUB,
    "hub_name": "Henry Hub",
    "region": "Louisiana (Gulf Coast)",
    "price_source": "EIA RNGWHHD daily spot; NYMEX NG front month via yfinance",
}])

# Fictional counterparties. Types mirror who a Houston gas marketer deals with.
COUNTERPARTIES = pd.DataFrame([
    ("CP01", "Permian Producer A", "producer", "BBB", 8_000_000, "active"),
    ("CP02", "Haynesville Producer B", "producer", "BB", 5_000_000, "active"),
    ("CP03", "Gulf Coast Utility C", "utility", "A", 15_000_000, "active"),
    ("CP04", "Texas Power Generator D", "power", "BBB-", 10_000_000, "active"),
    ("CP05", "Petrochemical Plant E", "industrial", "A-", 12_000_000, "active"),
    ("CP06", "LNG Feedgas Buyer F", "lng_feedgas", "BBB", 20_000_000, "active"),
    ("CP07", "LNG Feedgas Buyer G", "lng_feedgas", "BB+", 6_000_000, "commissioning"),
    ("CP08", "Regional Marketer H", "marketer", "BB-", 3_000_000, "active"),
], columns=["counterparty_id", "name", "type", "credit_rating", "credit_limit_usd", "status"])
COUNTERPARTIES["contract"] = "NAESB Base Contract (2006)"
COUNTERPARTIES["payment_terms"] = "25th of month following delivery"

# Who we usually buy from vs sell to
BUY_FROM = ["CP01", "CP02", "CP08"]
SELL_TO = ["CP03", "CP04", "CP05", "CP06", "CP07", "CP08"]


def front_delivery_month(trade_date: pd.Timestamp) -> pd.Timestamp:
    """First day of the delivery month the NYMEX front-month contract covers on this date.

    The front contract is the nearest month whose expiry (3 business days before the month starts)
    is on or after the trade date.
    """
    month = trade_date.normalize() - pd.offsets.MonthBegin(1)  # start checking from the current month
    for _ in range(4):
        if month - pd.offsets.BDay(3) >= trade_date.normalize():
            return month
        month += pd.offsets.MonthBegin(1)
    raise ValueError(f"no expiry found after {trade_date}")


def generate_trades(futures: pd.DataFrame, seed: int = SEED, start: str = START, end: str = END) -> pd.DataFrame:
    """Simulated trades on real trading days, priced off the real front-month futures close."""
    rng = np.random.default_rng(seed)
    f = futures.set_index("date")["close"].sort_index().loc[start:end]
    rows = []
    net_fixed: dict[pd.Timestamp, int] = {}  # net fixed-price MMBtu/day per delivery month
    for trade_date, screen in f.items():
        for _ in range(rng.integers(TRADES_PER_DAY[0], TRADES_PER_DAY[1] + 1)):
            buy = rng.random() < 0.5
            delivery_start = front_delivery_month(trade_date)
            fixed = rng.random() < FIXED_SHARE
            volume = int(rng.choice(VOLUMES))
            if fixed:
                current = net_fixed.get(delivery_start, 0)
                if abs(current + (volume if buy else -volume)) > POSITION_LIMIT:
                    buy = not buy  # hedge instead of adding to the open position
                net_fixed[delivery_start] = current + (volume if buy else -volume)
            cp = rng.choice(BUY_FROM if buy else SELL_TO)
            margin = -DEALER_MARGIN if buy else DEALER_MARGIN
            rows.append({
                "trade_date": trade_date,
                "counterparty_id": cp,
                "hub_id": HUB,
                "buy_sell": "buy" if buy else "sell",
                "delivery_start": delivery_start,
                "delivery_end": delivery_start + pd.offsets.MonthEnd(0),
                "volume_mmbtu_per_day": volume,
                "price_type": "fixed" if fixed else "index",
                "fixed_price": round(screen + margin, 4) if fixed else None,
                "index_name": None if fixed else "EIA Henry Hub daily spot",
                "index_adder": None if fixed else round(margin, 4),
                "trader": rng.choice(TRADERS),
            })
    trades = pd.DataFrame(rows)
    trades.insert(0, "trade_id", [f"T{i:05d}" for i in range(1, len(trades) + 1)])
    return trades
