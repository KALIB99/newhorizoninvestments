import numpy as np
import pandas as pd
import pytest

from portfolio.sizing import (
    combine_weights,
    correlation_clusters,
    fractional_kelly,
    kelly_fraction,
    position_from_signal,
    realised_vol_ewma,
    vol_target_scale,
)
from risk.limits import LIMITS


def test_vol_target_scale_is_lagged_and_capped():
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0, 0.30 / np.sqrt(8760), 5000))  # 30% annual vol
    vol = realised_vol_ewma(r, 20, 8760)
    assert vol.iloc[-1] == pytest.approx(0.30, rel=0.35)
    scale = vol_target_scale(r, 0.15, 20, 8760)
    assert scale.iloc[-1] == pytest.approx(0.5, rel=0.4)
    assert scale.max() <= LIMITS.max_gross_exposure
    # lag: scale at t must not depend on r[t]
    r2 = r.copy()
    r2.iloc[-1] = 10.0
    assert vol_target_scale(r2, 0.15, 20, 8760).iloc[-1] == scale.iloc[-1]


def test_kelly_zero_for_no_edge_or_too_few_trades():
    assert kelly_fraction(np.array([-0.01, 0.01] * 50)) == 0.0
    assert kelly_fraction(np.array([0.01] * 10)) == 0.0


def test_fractional_kelly_is_quarter_and_capped_by_per_trade_risk():
    rng = np.random.default_rng(1)
    t = rng.normal(0.002, 0.01, 500)
    full = kelly_fraction(t)
    frac = fractional_kelly(t)
    assert frac <= 0.25 * full + 1e-12
    assert frac * abs(t.min()) <= LIMITS.max_risk_per_trade + 1e-12


def test_correlation_clusters_merge_above_cap():
    rng = np.random.default_rng(2)
    a = rng.normal(0, 1, 1000)
    df = pd.DataFrame({"a": a, "b": a + rng.normal(0, 0.3, 1000), "c": rng.normal(0, 1, 1000)})
    cl = correlation_clusters(df, 0.7)
    assert sorted(map(sorted, cl)) == [["a", "b"], ["c"]]


def test_combine_weights_sum_to_one_and_split_clusters():
    rng = np.random.default_rng(3)
    a = rng.normal(0, 1, 1000)
    df = pd.DataFrame({"a": a, "b": a + rng.normal(0, 0.2, 1000), "c": rng.normal(0, 1, 1000)})
    w = combine_weights(df, shrink=0.5, corr_cap=0.7)
    assert w.sum() == pytest.approx(1.0)
    assert w["a"] == pytest.approx(w["b"])
    assert w["c"] > w["a"]  # the correlated pair shares one budget


def test_combine_weights_shrinks_toward_equal():
    rng = np.random.default_rng(4)
    df = pd.DataFrame({"lo": rng.normal(0, 0.5, 1000), "hi": rng.normal(0, 2.0, 1000)})
    w0 = combine_weights(df, shrink=0.0)
    w1 = combine_weights(df, shrink=1.0)
    assert w1["lo"] == pytest.approx(0.5) and w1["hi"] == pytest.approx(0.5)
    assert w0["lo"] > 0.9


def test_position_from_signal_applies_regime_multiplier_and_clip():
    vt = LIMITS.vol_target_annual  # realised vol == target → unit weight before multipliers
    base = position_from_signal(1.0, vt, 1.0, "Trend")
    assert base == pytest.approx(1.0)
    assert position_from_signal(1.0, vt, 1.0, "Range") == pytest.approx(0.8)
    assert position_from_signal(1.0, vt, 1.0, "Chaos") == pytest.approx(0.3)
    assert position_from_signal(1.0, 0.01, 1.0, "Trend") == LIMITS.max_gross_exposure
    assert position_from_signal(1.0, 0.0, 1.0, "Trend") == 0.0
    with pytest.raises(KeyError):
        position_from_signal(1.0, 0.1, 1.0, "Sideways")
