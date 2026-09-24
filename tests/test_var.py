"""VaR model and backtest tests on synthetic data with known answers."""

import numpy as np
import pandas as pd
import pytest

from gasbook.risk import var


@pytest.fixture
def normal_returns():
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2000-01-03", periods=6000)
    return pd.Series(rng.normal(0, 0.02, len(idx)), index=idx)


def test_log_returns_rejects_non_positive_prices():
    with pytest.raises(ValueError):
        var.log_returns(pd.Series([3.0, 0.0, 2.5]))


def test_losses_flip_with_side():
    r = pd.Series([0.1, -0.2])
    assert list(var.losses(r, 1)) == [-0.1, 0.2]
    assert list(var.losses(r, -1)) == [0.1, -0.2]
    with pytest.raises(ValueError):
        var.losses(r, 0)


def test_no_look_ahead(normal_returns):
    """Changing today's return must not change today's VaR forecast."""
    shocked = normal_returns.copy()
    day = shocked.index[3000]
    shocked[day] = 5.0
    for model in (
        lambda r: var.var_normal(var.losses(r, 1), 250, 0.99),
        lambda r: var.var_historical(var.losses(r, 1), 250, 0.99),
        lambda r: var.var_ewma(r, 1, 0.99),
        lambda r: var.var_filtered_hs(r, 1, 250, 0.99),
    ):
        assert model(normal_returns)[day] == pytest.approx(model(shocked)[day])


def test_models_hit_about_one_percent_on_normal_data(normal_returns):
    loss = var.losses(normal_returns, 1)
    for forecast in (
        var.var_normal(loss, 250, 0.99),
        var.var_historical(loss, 250, 0.99),
        var.var_ewma(normal_returns, 1, 0.99),
        var.var_filtered_hs(normal_returns, 1, 250, 0.99),
    ):
        result = var.backtest(loss, forecast, 0.99)
        assert 0.005 < result["breach_rate"] < 0.02


def test_ewma_recursion_matches_hand_calculation():
    r = pd.Series([0.01, -0.02, 0.03, 0.0])
    sigma = var.ewma_vol(r, lam=0.9, seed_window=2)
    seed = (0.01**2 + 0.02**2) / 2
    assert np.isnan(sigma.iloc[1])
    assert sigma.iloc[2] == pytest.approx(np.sqrt(seed))
    assert sigma.iloc[3] == pytest.approx(np.sqrt(0.9 * seed + 0.1 * 0.03**2))


def test_kupiec_accepts_exact_rate_and_rejects_bad_rate():
    good = pd.Series([True] * 10 + [False] * 990)
    bad = pd.Series([True] * 50 + [False] * 950)
    assert var.kupiec_pof(good, 0.99)[1] == pytest.approx(1.0)
    assert var.kupiec_pof(bad, 0.99)[1] < 0.001


def test_independence_flags_clustered_breaches():
    spread = pd.Series(([True] + [False] * 99) * 10)
    clustered = pd.Series([False] * 495 + [True] * 10 + [False] * 495)
    assert var.christoffersen_independence(spread)[1] > 0.05
    assert var.christoffersen_independence(clustered)[1] < 0.001


def test_to_pct_loss_long_capped_short_uncapped():
    # Henry Hub 2026-01-22 -> 2026-01-23: $8.42 -> $30.72
    log_move = np.log(30.72 / 8.42)
    assert var.to_pct_loss(log_move, -1) == pytest.approx(30.72 / 8.42 - 1)  # short loses ~265%
    assert var.to_pct_loss(-np.log(0.36), 1) == pytest.approx(0.64)  # long loses 64% when price falls 64%
    assert var.to_pct_loss(50.0, 1) <= 1.0  # a long can never lose more than 100%
