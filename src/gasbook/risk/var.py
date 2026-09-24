"""One-day Value at Risk models and backtests.

Conventions
- Returns are daily log returns of the price.
- side = +1 for a long position (loses when price falls), -1 for a short position (loses when price rises).
  A marketer that sold fixed-price gas to customers is effectively short and loses in a spike.
- Loss = -side * return, so a positive loss is money lost.
- Every VaR forecast for day t uses data up to day t-1 only (no look-ahead).
"""

import numpy as np
import pandas as pd
from scipy import stats

EWMA_LAMBDA = 0.94  # RiskMetrics daily decay


def log_returns(prices: pd.Series) -> pd.Series:
    if (prices <= 0).any():
        raise ValueError("log returns need strictly positive prices")
    return np.log(prices).diff().dropna()


def losses(returns: pd.Series, side: int) -> pd.Series:
    if side not in (1, -1):
        raise ValueError("side must be +1 (long) or -1 (short)")
    return -side * returns


def to_pct_loss(log_loss, side: int):
    """Convert a log-return loss into the fraction of position value lost.

    Long: price falls by 1 - exp(-L), capped at 100%. Short: price rises by exp(L) - 1, uncapped (spikes).
    Monotonic in L, so breach counts are unchanged; use this only for reporting money amounts.
    """
    if side not in (1, -1):
        raise ValueError("side must be +1 (long) or -1 (short)")
    return 1 - np.exp(-log_loss) if side == 1 else np.exp(log_loss) - 1


def var_normal(loss: pd.Series, window: int, level: float) -> pd.Series:
    """Parametric VaR: rolling mean + z * rolling std, assumes normally distributed returns."""
    z = stats.norm.ppf(level)
    roll = loss.rolling(window)
    return (roll.mean() + z * roll.std()).shift(1)


def var_historical(loss: pd.Series, window: int, level: float) -> pd.Series:
    """Historical simulation: the level-quantile of the last `window` losses."""
    return loss.rolling(window).quantile(level).shift(1)


def ewma_vol(returns: pd.Series, lam: float = EWMA_LAMBDA, seed_window: int = 30) -> pd.Series:
    """RiskMetrics volatility: sigma2[t] = lam*sigma2[t-1] + (1-lam)*r[t-1]^2. Value at t uses returns to t-1."""
    r = returns.to_numpy()
    sigma2 = np.full(len(r), np.nan)
    if len(r) <= seed_window:
        return pd.Series(sigma2, index=returns.index)
    sigma2[seed_window] = np.mean(r[:seed_window] ** 2)
    for t in range(seed_window + 1, len(r)):
        sigma2[t] = lam * sigma2[t - 1] + (1 - lam) * r[t - 1] ** 2
    return pd.Series(np.sqrt(sigma2), index=returns.index)


def var_ewma(returns: pd.Series, side: int, level: float, lam: float = EWMA_LAMBDA) -> pd.Series:
    """Normal VaR scaled by EWMA volatility: reacts fast to volatility spikes, still assumes normal tails."""
    losses(returns, side)  # validates side
    return stats.norm.ppf(level) * ewma_vol(returns, lam)


def var_filtered_hs(returns: pd.Series, side: int, window: int, level: float, lam: float = EWMA_LAMBDA) -> pd.Series:
    """Filtered historical simulation: EWMA volatility x empirical quantile of volatility-standardized losses.

    Combines fast reaction to volatility (EWMA) with real fat tails (historical quantiles).
    """
    sigma = ewma_vol(returns, lam)
    std_loss = losses(returns, side) / sigma
    q = std_loss.rolling(window).quantile(level).shift(1)
    return q * sigma


def kupiec_pof(breaches: pd.Series, level: float) -> tuple[float, float]:
    """Kupiec proportion-of-failures test. Returns (LR statistic, p-value). Low p-value = wrong breach rate."""
    b = breaches.dropna().astype(bool)
    n, x = len(b), int(b.sum())
    p = 1 - level
    if n == 0:
        return np.nan, np.nan
    phat = x / n
    ll_null = (n - x) * np.log(1 - p) + x * np.log(p)
    ll_alt = (n - x) * np.log(1 - phat) + x * np.log(phat) if 0 < x < n else 0.0
    lr = -2 * (ll_null - ll_alt)
    return lr, stats.chi2.sf(lr, 1)


def christoffersen_independence(breaches: pd.Series) -> tuple[float, float]:
    """Christoffersen test that breaches don't cluster. Returns (LR statistic, p-value). Low p-value = clustering."""
    b = breaches.dropna().astype(int).to_numpy()
    if len(b) < 2:
        return np.nan, np.nan
    prev, curr = b[:-1], b[1:]
    n00 = np.sum((prev == 0) & (curr == 0))
    n01 = np.sum((prev == 0) & (curr == 1))
    n10 = np.sum((prev == 1) & (curr == 0))
    n11 = np.sum((prev == 1) & (curr == 1))
    if n01 + n11 == 0 or n00 + n10 == 0:
        return 0.0, 1.0

    def ll(k0, k1):
        p = k1 / (k0 + k1) if (k0 + k1) else 0.0
        return (k0 * np.log(1 - p) if k0 and p < 1 else 0.0) + (k1 * np.log(p) if k1 and p > 0 else 0.0)

    ll_null = ll(n00 + n10, n01 + n11)
    ll_alt = ll(n00, n01) + ll(n10, n11)
    lr = -2 * (ll_null - ll_alt)
    return lr, stats.chi2.sf(lr, 1)


def backtest(loss: pd.Series, var: pd.Series, level: float) -> dict:
    """Compare realized losses to VaR forecasts on the days where a forecast exists."""
    df = pd.concat({"loss": loss, "var": var}, axis=1).dropna()
    breach = df["loss"] > df["var"]
    kup_lr, kup_p = kupiec_pof(breach, level)
    ind_lr, ind_p = christoffersen_independence(breach)
    excess = (df["loss"] - df["var"])[breach]
    return {
        "days": len(df),
        "breaches": int(breach.sum()),
        "expected": round(len(df) * (1 - level), 1),
        "breach_rate": breach.mean(),
        "kupiec_p": kup_p,
        "independence_p": ind_p,
        "avg_excess_when_breached": excess.mean() if len(excess) else 0.0,
        "worst_excess": excess.max() if len(excess) else 0.0,
    }
