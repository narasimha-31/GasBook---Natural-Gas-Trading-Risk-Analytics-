"""Simulated counterparty confirmations, with planted errors.

Each counterparty sends its own record of every trade: its own reference number (no shared ID with ours),
its own side of the deal, volume, price and delivery month. We then break a share of them on purpose so the
matcher has something real to catch. The list of planted errors (the answer key) is returned separately and
never stored with the confirmations, so the matcher cannot see it.

Planted error types (one per affected trade):
    volume        - they have a different daily volume
    price         - they have a different fixed price or index adder
    counterparty  - the confirmation comes from a different counterparty than the one we booked
    delivery      - they have a different delivery month
    missing       - no confirmation ever arrives
    unknown       - they confirm a trade we never booked

Harmless differences that must NOT be flagged: prices rounded to 3 decimals, confirmations dated a day later.
"""

import numpy as np
import pandas as pd

SEED = 11
ERROR_SHARE = 0.12
UNKNOWN_SHARE = 0.01
ERROR_TYPES = ["volume", "price", "counterparty", "delivery", "missing"]
WRONG_VOLUMES = {2_500: 25_000, 5_000: 50_000, 7_500: 5_000, 10_000: 1_000, 15_000: 10_000, 20_000: 2_000}


def _their_side(buy_sell: str) -> str:
    return "sell" if buy_sell == "buy" else "buy"


def generate(trades: pd.DataFrame, counterparty_ids: list[str], seed: int = SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (confirmations, answer_key)."""
    rng = np.random.default_rng(seed)
    confirms, key = [], []
    n = len(trades)
    broken = set(rng.choice(n, size=round(n * ERROR_SHARE), replace=False))

    for i, t in enumerate(trades.itertuples(index=False)):
        c = {
            "counterparty_id": t.counterparty_id,
            "their_side": _their_side(t.buy_sell),
            "trade_date": t.trade_date,
            "confirm_date": t.trade_date + pd.offsets.BDay(int(rng.integers(0, 2))),
            "delivery_start": t.delivery_start,
            "delivery_end": t.delivery_end,
            "volume_mmbtu_per_day": t.volume_mmbtu_per_day,
            "price_type": t.price_type,
            "fixed_price": round(t.fixed_price, 3) if t.price_type == "fixed" else None,
            "index_adder": round(t.index_adder, 3) if t.price_type == "index" else None,
        }
        if i in broken:
            error = str(rng.choice(ERROR_TYPES))
            key.append({"trade_id": t.trade_id, "error": error})
            if error == "missing":
                continue
            if error == "volume":
                c["volume_mmbtu_per_day"] = WRONG_VOLUMES[t.volume_mmbtu_per_day]
            elif error == "price":
                bump = float(rng.choice([-0.25, -0.10, -0.05, 0.05, 0.10, 0.25]))
                if t.price_type == "fixed":
                    c["fixed_price"] = round(t.fixed_price + bump, 3)
                else:
                    c["index_adder"] = round(t.index_adder + bump, 3)
            elif error == "counterparty":
                c["counterparty_id"] = str(rng.choice([x for x in counterparty_ids if x != t.counterparty_id]))
            elif error == "delivery":
                shift = pd.offsets.MonthBegin(1) if rng.random() < 0.5 else -pd.offsets.MonthBegin(1)
                c["delivery_start"] = t.delivery_start + shift
                c["delivery_end"] = c["delivery_start"] + pd.offsets.MonthEnd(0)
        confirms.append(c)

    # Trades the counterparty has but we never booked
    for _ in range(round(n * UNKNOWN_SHARE)):
        t = trades.iloc[int(rng.integers(0, n))]
        c = {
            "counterparty_id": str(rng.choice(counterparty_ids)),
            "their_side": str(rng.choice(["buy", "sell"])),
            "trade_date": t.trade_date,
            "confirm_date": t.trade_date,
            "delivery_start": t.delivery_start,
            "delivery_end": t.delivery_end,
            "volume_mmbtu_per_day": int(rng.choice([2_500, 5_000, 10_000])),
            "price_type": "fixed",
            "fixed_price": round(float(t.fixed_price) if pd.notna(t.fixed_price) else 3.0, 3) + 0.4,
            "index_adder": None,
        }
        confirms.append(c)
        key.append({"trade_id": None, "error": "unknown"})

    out = pd.DataFrame(confirms).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    out.insert(0, "confirm_ref", [f"C-{rng.integers(100000, 999999)}-{i:04d}" for i in range(len(out))])
    return out, pd.DataFrame(key)
