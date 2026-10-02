import numpy as np
import pandas as pd
import pytest

from eval import metrics as m
from eval.costs import CostModel


def test_sharpe_basic_and_scaling():
    rng = np.random.default_rng(0)
    r = rng.normal(0.001, 0.01, 10_000)
    sr = m.sharpe(r, 252)
    assert sr == pytest.approx(0.1 * np.sqrt(252), rel=0.1)
    assert np.isnan(m.sharpe(np.zeros(10), 252))


def test_max_drawdown_and_calmar():
    r = np.array([0.1, -0.5, 0.2])  # 1.1 → 0.55 → 0.66 ; dd = -50%
    assert m.max_drawdown(r) == pytest.approx(-0.5)
    assert m.calmar(np.array([0.01] * 100), 252) > 0


def test_deflated_sharpe_penalises_trials():
    rng = np.random.default_rng(1)
    r = rng.normal(0.0005, 0.01, 2000)  # weak but real edge
    one = m.deflated_sharpe(r, n_trials=1)
    many = m.deflated_sharpe(r, n_trials=200)
    assert one.sr0 == 0.0
    assert many.sr0 > 0
    assert many.dsr < one.dsr
    assert many.p_value > one.p_value
    assert one.psr == pytest.approx(one.dsr)


def test_deflated_sharpe_uses_trial_variance_when_given():
    rng = np.random.default_rng(2)
    r = rng.normal(0.001, 0.01, 1000)
    tight = m.deflated_sharpe(r, 50, trial_sharpes=np.full(50, 0.1) + rng.normal(0, 0.001, 50))
    wide = m.deflated_sharpe(r, 50, trial_sharpes=rng.normal(0, 0.2, 50))
    assert wide.sr0 > tight.sr0


def test_deflated_sharpe_noise_rarely_passes():
    """Pure noise with 100 trials: pick the best-looking one, DSR must not call it real."""
    rng = np.random.default_rng(3)
    trials = rng.normal(0, 0.01, (1500, 100))
    srs = trials.mean(0) / trials.std(0, ddof=1)
    best = trials[:, int(np.argmax(srs))]
    res = m.deflated_sharpe(best, n_trials=100, trial_sharpes=srs)
    assert res.p_value > 0.05


def test_pbo_high_for_noise_low_for_real_edge():
    rng = np.random.default_rng(4)
    noise = rng.normal(0, 0.01, (1600, 20))
    assert m.pbo(noise, n_splits=8).pbo > 0.3
    edge = rng.normal(0, 0.01, (1600, 20))
    edge[:, 0] += 0.004  # one genuinely good trial that wins IS and OOS
    assert m.pbo(edge, n_splits=8).pbo < 0.3


def test_pbo_input_validation():
    with pytest.raises(ValueError):
        m.pbo(np.zeros((100, 1)))
    with pytest.raises(ValueError):
        m.pbo(np.zeros((100, 3)), n_splits=5)


def test_trade_stats():
    t = np.array([2.0, 2.0, -1.0, -1.0, -1.0])
    assert m.hit_rate(t) == pytest.approx(0.4)
    assert m.payoff_ratio(t) == pytest.approx(2.0)
    assert m.turnover(np.array([0, 1, 1, -1])) == pytest.approx((1 + 0 + 2) / 4)


def test_monthly_and_regime_pnl():
    idx = pd.date_range("2024-01-01", periods=60, freq="D", tz="UTC")
    r = pd.Series(0.01, index=idx)
    mp = m.monthly_pnl(r)
    assert set(mp) == {"2024-01", "2024-02"}
    assert mp["2024-01"] == pytest.approx(1.01**31 - 1)
    reg = pd.Series(["Trend"] * 30 + ["Range"] * 30, index=idx)
    pr = m.per_regime_pnl(r, reg)
    assert set(pr) == {"Trend", "Range"}


def test_periods_per_year():
    assert m.periods_per_year("1m") == 525_600
    assert m.periods_per_year("1h") == 8_760
    assert m.periods_per_year("1d") == 365


def test_cost_model_round_trip_is_in_realistic_band():
    c = CostModel()
    rt = c.round_trip_bps(size_adv=0.001)
    assert 10 <= rt <= 30, rt  # "5–15 bps round-trip" is the optimistic end; defaults are conservative
    assert c.scaled(1.5).round_trip_bps(0.001) == pytest.approx(1.5 * rt)
    assert c.slippage_bps(0.04) > c.slippage_bps(0.0)


def test_cost_drag_and_funding():
    c = CostModel(taker_fee_bps=5, spread_bps=2, slip_a=1, slip_b=0, slip_c=0)
    drag = c.cost_drag(np.array([0.0, 1.0, 0.5]))
    assert drag[0] == 0
    assert drag[1] == pytest.approx((5 + 1 + 1) / 1e4)
    assert drag[2] == pytest.approx(0.5 * (5 + 1 + 1) / 1e4)
    f = CostModel.funding_drag(np.array([1.0, -1.0]), np.array([0.0001, 0.0001]))
    assert f[0] > 0 > f[1]  # longs pay positive funding, shorts receive


def test_cost_model_from_missing_fit_is_conservative(tmp_path):
    c = CostModel.from_fitted(tmp_path / "nope.json")
    assert "default_conservative" in c.source
    assert c.slip_a == CostModel().slip_a
