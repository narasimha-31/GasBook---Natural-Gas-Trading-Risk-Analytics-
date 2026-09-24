"""Basis risk: how far a hub price moves away from Henry Hub, and how much a Henry Hub hedge leaves uncovered.

basis = hub price - Henry Hub price, same gas delivery day, only on days where both traded (never filled in).
"""

import numpy as np
import pandas as pd

HENRY = "Henry Hub"
# Hedge accounting rule of thumb (ASC 815): a hedge is "highly effective" if it explains >= 80% of the risk.
HIGHLY_EFFECTIVE = 0.80


def basis_table(wide: pd.DataFrame) -> pd.DataFrame:
    """Hub-minus-Henry basis per delivery day. NaN wherever the hub or Henry Hub did not trade."""
    if HENRY not in wide:
        raise ValueError("wide price table needs a 'Henry Hub' column")
    return wide.drop(columns=HENRY).sub(wide[HENRY], axis=0)


def basis_stats(basis: pd.DataFrame, blowout: float = 1.0) -> pd.DataFrame:
    """Size and tail of each hub's basis. `blowout` = $/MMBtu gap that counts as a blowout day."""
    rows = []
    for hub in basis:
        b = basis[hub].dropna()
        if b.empty:
            continue
        rows.append({
            "hub": hub,
            "days": len(b),
            "mean": b.mean(),
            "std": b.std(),
            "p01": b.quantile(0.01),
            "p99": b.quantile(0.99),
            "min": b.min(),
            "max": b.max(),
            "max_day": b.idxmax().date(),
            f"share_abs_gt_{blowout:g}": (b.abs() > blowout).mean(),
        })
    return pd.DataFrame(rows).set_index("hub")


def monthly_profile(basis: pd.DataFrame) -> pd.DataFrame:
    """Average basis by calendar month (1-12) per hub, to show winter vs summer behaviour."""
    return basis.groupby(basis.index.month).mean().rename_axis("month")


def paired_changes(hub: pd.Series, henry: pd.Series, max_gap_days: int = 4) -> pd.DataFrame:
    """Day-over-day price changes on days both traded, dropping changes that span a gap longer than a weekend."""
    df = pd.concat({"hub": hub, "henry": henry}, axis=1).dropna()
    gap = df.index.to_series().diff().dt.days
    chg = df.diff()
    return chg[gap <= max_gap_days].dropna()


def hedge_effectiveness(hub: pd.Series, henry: pd.Series, max_gap_days: int = 4) -> dict:
    """How much daily price risk at `hub` a Henry Hub hedge removes.

    naive: hedge 1 MMBtu of Henry Hub per 1 MMBtu of physical gas (what most small desks do).
    min_variance: best hedge ratio from regression (beta). R^2 is the share of risk it can remove.
    """
    chg = paired_changes(hub, henry, max_gap_days)
    if len(chg) < 30:
        raise ValueError("need at least 30 paired daily changes")
    dh, dH = chg["hub"], chg["henry"]
    var_unhedged = dh.var()
    beta = np.cov(dh, dH)[0, 1] / dH.var()
    r2 = np.corrcoef(dh, dH)[0, 1] ** 2
    naive_resid = dh - dH  # this is exactly the daily change in basis
    calm = naive_resid.abs() <= naive_resid.abs().quantile(0.99)
    r2_calm = np.corrcoef(dh[calm], dH[calm])[0, 1] ** 2
    return {
        "paired_days": len(chg),
        "hedge_ratio_min_var": beta,
        "r2": r2,
        "r2_without_worst_1pct": r2_calm,
        "effectiveness_naive": 1 - naive_resid.var() / var_unhedged,
        "effectiveness_min_var": r2,
        "highly_effective": bool(r2 >= HIGHLY_EFFECTIVE),
        "residual_p99_abs": naive_resid.abs().quantile(0.99),
        "residual_worst_abs": naive_resid.abs().max(),
        "residual_worst_day": naive_resid.abs().idxmax().date(),
    }


def monthly_hedge_effectiveness(hub: pd.Series, henry: pd.Series) -> dict:
    """Same test on monthly average prices (desks usually hedge a month of volume, not one day).

    Averages only use days where both hubs traded. Small sample: one observation per month.
    """
    both = pd.concat({"hub": hub, "henry": henry}, axis=1).dropna()
    chg = both.resample("MS").mean().dropna().diff().dropna()
    r2 = np.corrcoef(chg["hub"], chg["henry"])[0, 1] ** 2
    return {
        "months": len(chg),
        "r2_monthly": r2,
        "effectiveness_naive_monthly": 1 - (chg["hub"] - chg["henry"]).var() / chg["hub"].var(),
        "highly_effective_monthly": bool(r2 >= HIGHLY_EFFECTIVE),
    }
