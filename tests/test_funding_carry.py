"""Accounting invariants for the funding-carry simulator (Judge, T-002, 2026-10-10).

The walk-forward stitch once dropped the bar on which a deselected pair's exit filled, so the
return series was ~3% richer than the trade log. These tests pin the ledger to the series.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from eval.costs import CostModel
from research.strategies.funding_carry import (
    FundingCarryParams,
    block_bootstrap_sharpe_ci,
    episodes,
    funding_apr,
    leg_size,
    pipeline,
    simulate_carry,
)
from risk.limits import LIMITS

SYMS = ("BTC", "ETH", "SOL")


def _frames(n_bars: int = 24 * 150, seed: int = 7) -> tuple[pd.DatetimeIndex, dict[str, pd.DataFrame]]:
    """Hourly spot+perp tape; funding settles every 8 bars and is rich in alternating 20-day blocks."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01 01:00", periods=n_bars, freq="1h", tz="UTC")
    out = {}
    for k, b in enumerate(SYMS):
        close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.005, n_bars)))
        open_ = np.r_[close[0], close[:-1]]
        basis = 0.0005 + 0.0003 * np.sin(np.arange(n_bars) / 200 + k)
        rich = ((np.arange(n_bars) // (24 * 20)) % 2 == 0)
        paid = np.where((np.arange(n_bars) % 8 == 0), np.where(rich, 0.0004, 0.00002), 0.0)
        out[b] = pd.DataFrame(
            {
                "open": open_ * (1 + basis), "high": np.maximum(open_, close) * (1 + basis) * 1.002,
                "low": np.minimum(open_, close) * (1 + basis) * 0.998, "close": close * (1 + basis),
                "funding_paid": paid, "funding_rate_last": pd.Series(paid).replace(0.0, np.nan).ffill().fillna(0.0).to_numpy(),
                "spot_open": open_, "spot_close": close, "spot_quote_volume": 1e8,
            },
            index=idx,
        )
    return idx, out


def _costs() -> tuple[CostModel, CostModel]:
    return CostModel(), CostModel(taker_fee_bps=10.0, maker_fee_bps=10.0)


def _ledger_matches_series(rets: pd.Series, trades: pd.DataFrame, tol: float = 0.01) -> None:
    equity_change = 100_000.0 * (float(np.prod(1.0 + rets.to_numpy())) - 1.0)
    ledger = float(trades["pnl_usd"].sum())
    assert ledger != 0.0
    assert abs(ledger - equity_change) <= tol * abs(equity_change), (ledger, equity_change)


def test_funding_apr_is_interval_agnostic_and_causal():
    idx, fr = _frames(24 * 10)
    d = fr["BTC"]
    apr = funding_apr(d, 24)
    # 3 settlements of 4 bps per 24h → 0.0012 × 365 ≈ 43.8% APR once the window is full and rich
    assert apr.iloc[47] == pytest.approx(0.0012 * 365, rel=1e-9)
    # doubling the settlement frequency at the same per-settlement rate doubles the APR
    d2 = d.copy()
    d2["funding_paid"] = np.where(np.arange(len(d2)) % 4 == 0, 0.0004, 0.0)
    assert funding_apr(d2, 24).iloc[47] == pytest.approx(2 * 0.0012 * 365, rel=1e-9)
    # causal: perturbing the future never changes the present
    d3 = d.copy()
    d3.iloc[60:, d3.columns.get_loc("funding_paid")] = 0.05
    assert funding_apr(d3, 24).iloc[:60].equals(apr.iloc[:60])


def test_simulate_carry_ledger_reconciles_with_deselection_exits():
    idx, fr = _frames()
    p = FundingCarryParams()
    perp, spot = _costs()
    active = np.ones(len(idx), dtype=bool)
    active[24 * 30 : 24 * 45] = False  # force 'deselected' exits mid-episode
    active[24 * 90 : 24 * 100] = False
    rets, trades, halts = simulate_carry(idx, fr, p, 0.15, 0.05, perp, spot, active=active)
    assert halts == []
    assert "deselected" in set(trades["exit_reason"])
    # no pair is opened on an inactive bar
    inactive = set(idx[~active])
    assert not any(ts in inactive for ts in trades["entry_ts"])
    _ledger_matches_series(rets, trades)
    # and the series is flat whenever the book is flat and inactive
    assert (rets[~active & ~np.roll(active, 1) & ~np.roll(active, 2)] == 0).all()


def test_leg_size_is_fundable_without_borrowing():
    p = FundingCarryParams()
    leg, pairs = leg_size(p)
    # cash cap binds: spot cash + perp margin for every pair fits inside equity
    assert pairs * leg * (1.0 + p.perp_initial_margin) <= 1.0 + 1e-12
    # and never exceeds the constitution's per-trade risk or gross limits
    assert leg <= LIMITS.max_risk_per_trade / p.basis_stop + 1e-12
    assert 2 * pairs * leg <= LIMITS.max_gross_exposure + 1e-12
    # with no margin requirement the risk rule is the binding one
    leg0, _ = leg_size(FundingCarryParams(perp_initial_margin=0.0))
    assert leg0 == pytest.approx(LIMITS.max_risk_per_trade / p.basis_stop)


def test_episodes_merge_across_symbols_and_split_on_flat_gap():
    ts = pd.Timestamp("2024-01-01", tz="UTC")
    d = pd.Timedelta(days=1)
    t = pd.DataFrame({
        "symbol": ["BTC", "ETH", "SOL", "BTC", "ETH"],
        "entry_ts": [ts, ts + 2 * d, ts + 20 * d, ts + 40 * d, ts + 44 * d],
        "exit_ts": [ts + 10 * d, ts + 15 * d, ts + 25 * d, ts + 42 * d, ts + 50 * d],
        "pnl_usd": [100.0, 50.0, -30.0, 10.0, -40.0],
    })
    ep = episodes(t, gap_days=7)
    # BTC+ETH overlap → one; SOL starts 5d after the book went flat → same episode; 15d gap → new
    assert len(ep) == 2
    assert ep["n_trades"].tolist() == [3, 2]
    assert ep["pnl_usd"].tolist() == pytest.approx([120.0, -30.0])
    assert ep["end"].iloc[0] == ts + 25 * d
    assert len(episodes(t, gap_days=3)) == 3
    assert episodes(t.iloc[:0], 7).empty


def test_block_bootstrap_ci_is_reproducible_and_brackets_the_point_estimate():
    rng = np.random.default_rng(1)
    r = rng.normal(0.001, 0.01, 400)
    lo, hi = block_bootstrap_sharpe_ci(r, 365, block=10, n_boot=500, seed=0)
    assert (lo, hi) == block_bootstrap_sharpe_ci(r, 365, block=10, n_boot=500, seed=0)
    point = r.mean() / r.std(ddof=1) * np.sqrt(365)
    assert lo < point < hi
    # autocorrelated series: a block bootstrap must widen the CI relative to iid resampling
    ar = np.zeros(400)
    for i in range(1, 400):
        ar[i] = 0.8 * ar[i - 1] + rng.normal(0, 0.01)
    ar += 0.001
    lo_b, hi_b = block_bootstrap_sharpe_ci(ar, 365, block=20, n_boot=500, seed=0)
    lo_i, hi_i = block_bootstrap_sharpe_ci(ar, 365, block=1, n_boot=500, seed=0)
    assert hi_b - lo_b > hi_i - lo_i
    assert np.isnan(block_bootstrap_sharpe_ci(r[:5], 365, block=10)[0])


def test_venue_outage_defers_exit_and_keeps_ledger_finite():
    """Binance spot was down 2020-12-21 16:00–18:00 while perps traded. An exit scheduled into
    that hole must wait for the next tradable open, not poison equity with NaN."""
    idx, fr = _frames()
    p = FundingCarryParams()
    perp, spot = _costs()
    # deactivate at bar t0 (inside a rich-funding block, so pairs are held): the exit is decided
    # at t0 and would fill at t0+1, which falls inside a 3-bar spot outage
    t0 = 24 * 15
    active = np.ones(len(idx), dtype=bool)
    active[t0:] = False
    hole = slice(t0 + 1, t0 + 4)
    for b in fr:
        fr[b].iloc[hole, fr[b].columns.get_indexer(["spot_open", "spot_close"])] = np.nan
    rets, trades, halts = simulate_carry(idx, fr, p, 0.15, 0.05, perp, spot, active=active)
    assert np.isfinite(rets.to_numpy()).all()
    assert trades["pnl_usd"].notna().all()
    # exits that were due in the hole filled at the first bar after it
    late = trades[trades["exit_reason"] == "deselected"]
    assert len(late) > 0 and (late["exit_ts"] == idx[t0 + 4]).all()
    _ledger_matches_series(rets, trades)


def test_pipeline_stitch_includes_every_exit_bar():
    idx, fr = _frames()
    p = FundingCarryParams(wf_train_days=30, wf_test_days=15, wf_embargo_days=1)
    perp, spot = _costs()
    res = pipeline(idx, fr, p, perp, spot)
    assert res["windows"], "walk-forward produced no windows"
    assert len(res["trades"]) > 0
    _ledger_matches_series(res["final_r"], res["trades"])
    assert len(res["is_daily"]) > 0
