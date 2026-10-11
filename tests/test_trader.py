"""The trader's principles must trigger, and must never be looser than risk/limits.py."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from eval.costs import CostModel
from risk.limits import LIMITS
from signals.sr_inversion import SRInversionParams, sr_inversion, sr_levels
from signals.testing import assert_no_lookahead, assert_signal_contract, synthetic_ohlcv
from trader import MarketData, SleeveConfig, SleeveInputs, TraderPrinciples, simulate

pytestmark = pytest.mark.risk
E0 = 100_000.0


def make_md(
    closes: dict[str, list[float]],
    *,
    lows: dict[str, dict[int, float]] | None = None,
    opens: dict[str, dict[int, float]] | None = None,
    regime: str = "Trend",
    atr: float = 1.0,
    sigma: float = 0.1,
    start: str = "2024-01-01 01:00",
) -> MarketData:
    n = len(next(iter(closes.values())))
    idx = pd.date_range(start, periods=n, freq="1h", tz="UTC")
    o, h, lo, c = {}, {}, {}, {}
    for s, cl in closes.items():
        cl = np.asarray(cl, dtype=float)
        op = np.concatenate([[cl[0]], cl[:-1]])
        for i, v in (opens or {}).get(s, {}).items():
            op[i] = v
        lw = np.minimum(op, cl)
        for i, v in (lows or {}).get(s, {}).items():
            lw[i] = v
        o[s], c[s], lo[s], h[s] = op, cl, lw, np.maximum(op, cl)
    syms = list(closes)
    return MarketData(
        index=idx,
        day=(idx - pd.Timedelta(hours=1)).normalize().to_numpy(),
        open=o,
        high=h,
        low=lo,
        close=c,
        atr={s: np.full(n, atr) for s in syms},
        sigma_annual={s: np.full(n, sigma) for s in syms},
        funding={s: np.zeros(n) for s in syms},
        regime={s: np.full(n, regime, dtype=object) for s in syms},
        rv_pct={s: np.full(n, 0.5) for s in syms},
        adv_usd={s: np.full(n, 1e12) for s in syms},
        spread_bps={s: 1.0 for s in syms},
    )


def sleeve(md: MarketData, entries: dict[str, dict[int, int]], *, stop_atr=2.0, max_hold=1000, trail=False,
           exit_long_at: dict[str, list[int]] | None = None, regimes=("Trend",),
           stop_px: dict[str, dict[int, float]] | None = None, **cfg) -> SleeveInputs:
    n = len(md.index)
    entry, xl, xs, sp = {}, {}, {}, {}
    for s in md.symbols:
        e = np.zeros(n, dtype=int)
        for i, d in entries.get(s, {}).items():
            e[i] = d
        entry[s] = e
        x = np.zeros(n, dtype=bool)
        for i in (exit_long_at or {}).get(s, []):
            x[i] = True
        xl[s] = x
        xs[s] = np.zeros(n, dtype=bool)
        a = np.full(n, np.nan)
        for i, v in (stop_px or {}).get(s, {}).items():
            a[i] = v
        sp[s] = a
    return SleeveInputs(SleeveConfig("test", stop_atr, max_hold, regimes, trail=trail, **cfg), entry, xl, xs,
                        stop_px=sp if stop_px else None)


COSTS = CostModel()


# ---- principles can only tighten ------------------------------------------------------------
@pytest.mark.parametrize(
    "field,looser",
    [
        ("risk_per_trade", LIMITS.max_risk_per_trade * 2),
        ("max_gross_exposure", LIMITS.max_gross_exposure + 1),
        ("max_net_exposure", LIMITS.max_net_exposure + 1),
        ("vol_target_annual", LIMITS.vol_target_annual * 2),
        ("daily_loss_limit", LIMITS.daily_loss_limit * 2),
        ("trailing_dd_limit", LIMITS.trailing_dd_limit * 2),
        ("kelly_fraction", 1.0),
    ],
)
def test_principles_reject_anything_looser_than_constitution(field, looser):
    with pytest.raises(ValueError, match="only tighten"):
        TraderPrinciples(**{field: looser})


def test_principles_accept_tighter_values():
    p = TraderPrinciples(risk_per_trade=0.0025, daily_loss_limit=-0.01, max_gross_exposure=1.0)
    assert p.risk_per_trade == 0.0025


# ---- timing ---------------------------------------------------------------------------------
def test_entry_decided_at_close_fills_next_open():
    md = make_md({"X": [100.0] * 10 + [101.0] * 10}, opens={"X": {6: 100.5}})
    r = simulate(md, [sleeve(md, {"X": {5: 1}}, exit_long_at={"X": [8]})], costs=COSTS)
    t = r.trades.iloc[0]
    assert t["entry_ts"] == md.index[6]
    assert t["entry_px"] == pytest.approx(100.5)
    assert t["exit_ts"] == md.index[9]


# ---- every trade has a stop; a stopped trade loses ~1R = 0.5% of equity ----------------------
def test_stop_caps_loss_at_risk_per_trade():
    closes = [100.0] * 5 + [99.0, 97.0, 97.0, 97.0, 97.0]
    md = make_md({"X": closes}, lows={"X": {6: 96.0}})
    r = simulate(md, [sleeve(md, {"X": {2: 1}})], costs=COSTS)
    t = r.trades.iloc[0]
    assert t["exit_reason"] == "stop"
    assert t["exit_px"] == pytest.approx(98.0)
    assert t["risk_usd"] == pytest.approx(LIMITS.max_risk_per_trade * E0, rel=1e-6)
    assert -1.1 < t["r_multiple"] < -1.0
    assert r.equity.iloc[-1] > E0 * (1 - LIMITS.max_risk_per_trade) - 50


def test_trailing_stop_only_ratchets_in_favour():
    closes = [100.0] * 3 + [102.0, 105.0, 110.0, 109.0, 106.0, 106.0]
    md = make_md({"X": closes})
    r = simulate(md, [sleeve(md, {"X": {1: 1}}, trail=True)], costs=COSTS)
    t = r.trades.iloc[0]
    assert t["exit_reason"] == "stop"
    assert t["exit_px"] == pytest.approx(108.0)


# ---- structural stops: the stop is a price, risk is still ≤ 0.5% ------------------------------
def test_structural_stop_price_sizes_to_risk_per_trade():
    closes = [100.0] * 5 + [99.0, 96.0, 96.0, 96.0]
    md = make_md({"X": closes}, lows={"X": {6: 95.0}})
    r = simulate(md, [sleeve(md, {"X": {2: 1}}, stop_px={"X": {2: 97.0}})], costs=COSTS)
    t = r.trades.iloc[0]
    assert t["exit_reason"] == "stop"
    assert t["exit_px"] == pytest.approx(97.0)
    assert t["risk_usd"] == pytest.approx(LIMITS.max_risk_per_trade * E0, rel=1e-6)
    assert t["qty"] == pytest.approx(LIMITS.max_risk_per_trade * E0 / 3.0)
    assert -1.1 < t["r_multiple"] < -1.0


def test_structural_stop_gap_away_shrinks_size_so_dollar_risk_is_unchanged():
    # decided at close 100 with stop 97 (3 wide); fills at 103 (6 wide) → qty halves
    md = make_md({"X": [100.0] * 5 + [103.0] * 5}, opens={"X": {3: 103.0}})
    r = simulate(md, [sleeve(md, {"X": {2: 1}}, stop_px={"X": {2: 97.0}}, exit_long_at={"X": [6]})], costs=COSTS)
    t = r.trades.iloc[0]
    assert t["entry_px"] == pytest.approx(103.0)
    assert t["risk_usd"] == pytest.approx(LIMITS.max_risk_per_trade * E0, rel=1e-6)
    assert t["qty"] == pytest.approx(LIMITS.max_risk_per_trade * E0 / 6.0)
    assert r.rules["shrunk_to_planned_risk"] == 1


def test_structural_stop_gap_through_skips_entry():
    md = make_md({"X": [100.0] * 5 + [96.0] * 5}, opens={"X": {3: 96.0}})
    r = simulate(md, [sleeve(md, {"X": {2: 1}}, stop_px={"X": {2: 97.0}})], costs=COSTS)
    assert r.trades.empty
    assert r.rules["skip_gap_through_stop"] == 1


def test_structural_stop_on_wrong_side_is_never_taken():
    md = make_md({"X": [100.0] * 10})
    r = simulate(md, [sleeve(md, {"X": {2: 1}}, stop_px={"X": {2: 101.0}})], costs=COSTS)
    assert r.trades.empty
    assert r.rules["skip_stop_wrong_side"] == 1


# ---- maker entries: fill only when traded through, at the limit, paying the maker fee --------
def test_maker_entry_fills_only_when_price_trades_through_the_limit():
    # decision at close 100 (bar 2). Bar 3 low = 100.0 exactly → not through → unfilled, cancelled.
    md = make_md({"X": [100.0] * 10})
    r = simulate(md, [sleeve(md, {"X": {2: 1}}, entry_style="maker")], costs=COSTS)
    assert r.trades.empty
    assert r.rules["maker_unfilled"] == 1
    # same tape but bar 3 dips to 99.5 → filled at the limit (100), not at the open
    md2 = make_md({"X": [100.0] * 10}, lows={"X": {3: 99.5}}, opens={"X": {3: 100.4}})
    r2 = simulate(md2, [sleeve(md2, {"X": {2: 1}}, entry_style="maker", exit_long_at={"X": [6]})], costs=COSTS)
    t = r2.trades.iloc[0]
    assert t["entry_ts"] == md2.index[3]
    assert t["entry_px"] == pytest.approx(100.0)
    assert r2.rules["maker_filled"] == 1


def test_maker_entry_is_cheaper_than_taker_and_improves_on_a_gap():
    md = make_md({"X": [100.0] * 10}, lows={"X": {3: 98.0}}, opens={"X": {3: 99.0}})
    taker = simulate(md, [sleeve(md, {"X": {2: 1}}, exit_long_at={"X": [6]})], costs=COSTS).trades.iloc[0]
    maker = simulate(md, [sleeve(md, {"X": {2: 1}}, entry_style="maker", exit_long_at={"X": [6]})], costs=COSTS).trades.iloc[0]
    assert maker["entry_px"] == pytest.approx(99.0)  # resting bid at 100 fills at the better open
    entry_cost_t = taker["cost_usd"] - COSTS.per_side_bps(0.0, True, 1.0) / 1e4 * taker["qty"] * taker["exit_px"]
    entry_cost_m = maker["cost_usd"] - COSTS.per_side_bps(0.0, True, 1.0) / 1e4 * maker["qty"] * maker["exit_px"]
    assert entry_cost_m < entry_cost_t * 0.75


def test_maker_ttl_keeps_the_order_resting_then_cancels():
    md = make_md({"X": [100.0] * 12}, lows={"X": {5: 99.0}})
    r = simulate(md, [sleeve(md, {"X": {2: 1}}, entry_style="maker", maker_ttl_bars=3, exit_long_at={"X": [8]})], costs=COSTS)
    assert len(r.trades) == 1
    assert r.trades.iloc[0]["entry_ts"] == md.index[5]
    r2 = simulate(md, [sleeve(md, {"X": {2: 1}}, entry_style="maker", maker_ttl_bars=2)], costs=COSTS)
    assert r2.trades.empty
    assert r2.rules["maker_unfilled"] == 1


# ---- adjusting stops: breakeven after +1R, trail arms only after +trail_after_r --------------
def test_breakeven_moves_stop_to_entry_plus_costs_after_one_r():
    # 1R = 2 ATR = 2.0; +1R reached at close 102, then a full retrace to 97 → scratch, not −1R
    closes = [100.0] * 3 + [101.0, 102.5, 101.0, 99.0, 97.0, 97.0]
    md = make_md({"X": closes})
    r = simulate(md, [sleeve(md, {"X": {1: 1}}, breakeven_r=1.0)], costs=COSTS)
    t = r.trades.iloc[0]
    assert t["exit_reason"] == "stop"
    assert t["exit_px"] > 100.0
    assert abs(t["r_multiple"]) < 0.05


def test_without_breakeven_the_same_path_loses_one_r():
    closes = [100.0] * 3 + [101.0, 102.5, 101.0, 99.0, 97.0, 97.0]
    md = make_md({"X": closes})
    r = simulate(md, [sleeve(md, {"X": {1: 1}})], costs=COSTS)
    assert r.trades.iloc[0]["exit_px"] == pytest.approx(98.0)


def test_trail_arms_only_after_threshold_then_tracks_atr():
    # 1R = 2.0. Rally to 101 (0.5R) then back to 99.5: an always-on trail would have stopped
    # at 99.0; with trail_after_r=1.5 the trail is not armed, the original stop at 98 holds.
    closes = [100.0] * 3 + [101.0, 99.5, 99.5, 104.0, 106.0, 104.5, 104.5]
    md = make_md({"X": closes})
    r = simulate(md, [sleeve(md, {"X": {1: 1}}, trail=True, trail_after_r=1.5, trail_atr=1.0)], costs=COSTS)
    t = r.trades.iloc[0]
    # armed at 104 (+2R): trail = best − 1 ATR → 105 after the 106 close → stopped at 105
    assert t["exit_reason"] == "stop"
    assert t["exit_px"] == pytest.approx(105.0)


# ---- daily loss limit: flatten, halt for the day, resume next UTC day -------------------------
def test_daily_loss_limit_flattens_and_blocks_until_next_day():
    n = 48
    closes = [100.0] * n
    for i in range(5, n):
        closes[i] = 95.0
    md = make_md({"X": closes}, opens={"X": {5: 95.0}}, atr=0.5)
    p = TraderPrinciples(min_stop_cost_multiple=1.0, cooldown_bars_after_loss=0)
    entries = {"X": {2: 1, 10: 1, 12: 1, 30: 1}}
    r = simulate(md, [sleeve(md, entries, stop_atr=1.0)], principles=p, costs=COSTS)
    assert r.rules["halt_daily_loss"] == 1
    assert r.trades.iloc[0]["exit_reason"] == "stop_gap"
    entered_same_day = r.trades[(r.trades["entry_ts"] > md.index[5]) & (r.trades["entry_ts"] < md.index[23])]
    assert entered_same_day.empty
    assert (r.trades["entry_ts"] >= md.index[23]).any()


def test_trailing_drawdown_halt_is_sticky():
    n = 60
    closes = [100.0] * n
    for i in range(5, n):
        closes[i] = 60.0
    md = make_md({"X": closes}, opens={"X": {5: 60.0}}, atr=0.5)
    p = TraderPrinciples(min_stop_cost_multiple=1.0, cooldown_bars_after_loss=0)
    r = simulate(md, [sleeve(md, {"X": {2: 1, 40: 1, 50: 1}}, stop_atr=1.0)], principles=p, costs=COSTS)
    assert any("trailing_drawdown" in h for h in r.halts)
    assert len(r.trades) == 1


# ---- anti-revenge, anti-overtrading, anti-tilt ---------------------------------------------
def test_cooldown_blocks_reentry_after_a_loss():
    closes = [100.0] * 5 + [97.0] * 15
    md = make_md({"X": closes}, lows={"X": {5: 96.0}})
    r = simulate(md, [sleeve(md, {"X": {2: 1, 6: 1, 7: 1, 15: 1}})], costs=COSTS)
    assert r.rules["skip_cooldown"] == 2
    assert len(r.trades) == 2


def test_max_trades_per_symbol_per_day():
    n = 23
    md = make_md({"X": [100.0] * n})
    entries = {"X": {i: 1 for i in range(1, 20, 2)}}
    exits = {"X": list(range(2, 21, 2))}
    r = simulate(md, [sleeve(md, entries, exit_long_at=exits)], costs=COSTS)
    assert len(r.trades) == TraderPrinciples().max_trades_per_symbol_per_day
    assert r.rules["skip_max_trades"] > 0


def test_consecutive_losses_end_the_day():
    syms = {f"S{i}": [100.0] * 5 + [97.0] * 15 for i in range(5)}
    md = make_md(syms, lows={s: {5: 96.0} for s in syms})
    entries = {s: {2: 1} for s in list(syms)[:4]}
    entries["S4"] = {8: 1}
    p = TraderPrinciples(max_gross_exposure=2.0, vol_target_annual=LIMITS.vol_target_annual)
    r = simulate(md, [sleeve(md, entries)], principles=p, costs=COSTS)
    assert (r.trades["pnl_usd"] < 0).sum() == 4
    assert "S4" not in set(r.trades["symbol"])
    assert r.rules["skip_consecutive_losses"] > 0


# ---- step aside: regime gate --------------------------------------------------------------
def test_regime_gate_blocks_wrong_regime():
    md = make_md({"X": [100.0] * 10}, regime="Chaos")
    r = simulate(md, [sleeve(md, {"X": {2: 1, 5: -1}})], costs=COSTS)
    assert r.trades.empty
    assert r.rules["skip_regime"] == 2


def test_cost_filter_skips_trades_whose_stop_is_too_tight_for_costs():
    md = make_md({"X": [100.0] * 10}, atr=0.01)
    r = simulate(md, [sleeve(md, {"X": {2: 1}})], costs=COSTS)
    assert r.trades.empty
    assert r.rules["skip_cost_vs_edge"] == 1


# ---- exposure: gross ≤ 2.0×, |net| ≤ 1.0×, vol target -------------------------------------
def test_exposure_caps_hold_when_every_symbol_fires():
    syms = {f"S{i}": [100.0] * 10 for i in range(6)}
    md = make_md(syms, atr=0.5, sigma=0.01)
    entries = {s: {2: 1 if i % 2 == 0 else -1} for i, s in enumerate(syms)}
    exits = {s: [6] for s in syms}
    sl = sleeve(md, entries, exit_long_at=exits)
    for s in syms:
        sl.exit_short[s][6] = True
    r = simulate(md, [sl], costs=COSTS)
    gross = r.trades["notional_usd"].sum()
    net = (r.trades["notional_usd"] * r.trades["side"]).sum()
    assert gross <= LIMITS.max_gross_exposure * E0 * 1.001
    assert abs(net) <= LIMITS.max_net_exposure * E0 * 1.001
    assert r.rules["shrunk_to_budget"] + r.rules["skip_risk_budget_full"] > 0


def test_vol_target_caps_position_size():
    md = make_md({"X": [100.0] * 10}, atr=0.5, sigma=0.60)
    r = simulate(md, [sleeve(md, {"X": {2: 1}}, exit_long_at={"X": [6]})], costs=COSTS)
    notional = r.trades.iloc[0]["notional_usd"]
    assert notional / E0 * 0.60 <= LIMITS.vol_target_annual * 1.001


def test_constitutional_derisk_tier_halves_risk_at_minus_8pct_even_if_principles_do_not():
    # principles' own tier disabled (factor 1.0); the −8% LIMITS tier must still halve risk.
    # X gaps from 100 to 50 (−12.5% of equity at 0.5% risk / 2.0 stop): daily-loss halt fires
    # and clears at the next UTC day (bar 24+); the −12.5% drawdown is below the −8% de-risk
    # tier but above the −15% halt, so Y (entered on day 2) must be sized at half risk.
    closes = [100.0] * 5 + [50.0] * 31
    md = make_md({"X": closes, "Y": [100.0] * 36}, opens={"X": {5: 50.0}}, atr=1.0)
    p = TraderPrinciples(min_stop_cost_multiple=1.0, cooldown_bars_after_loss=0,
                         drawdown_derisk_factor=1.0, drawdown_derisk_at=-0.001)
    r = simulate(md, [sleeve(md, {"X": {2: 1}, "Y": {26: 1}}, exit_long_at={"Y": [30]})], principles=p, costs=COSTS)
    assert not any("trailing_drawdown" in h for h in r.halts)  # −12.5% is above the −15% halt
    assert r.rules["halt_daily_loss"] == 1
    y = r.trades[r.trades["symbol"] == "Y"].iloc[0]
    assert y["risk_usd"] <= LIMITS.trailing_dd_derisk_multiplier * LIMITS.max_risk_per_trade * E0 * 1.0001
    assert y["risk_usd"] > 0.4 * LIMITS.max_risk_per_trade * E0  # halved, not zeroed
    assert r.rules["derisk_dd_tier"] >= 1


def test_drawdown_halves_risk():
    closes = [100.0] * 5 + [94.0] * 10 + [94.0] * 10
    md = make_md({"X": closes, "Y": [100.0] * 25}, opens={"X": {5: 94.0}}, atr=1.0)
    p = TraderPrinciples(min_stop_cost_multiple=1.0, cooldown_bars_after_loss=0, daily_loss_limit=-0.025,
                         drawdown_derisk_at=-0.001)
    r = simulate(md, [sleeve(md, {"X": {2: 1}, "Y": {8: 1}}, exit_long_at={"Y": [12]})], principles=p, costs=COSTS)
    y = r.trades[r.trades["symbol"] == "Y"].iloc[0]
    assert y["risk_usd"] < 0.5 * LIMITS.max_risk_per_trade * E0 * 1.0001
    assert r.rules["derisk_in_drawdown"] >= 1


# ---- signal contracts -----------------------------------------------------------------------
@pytest.mark.parametrize("params", [SRInversionParams(level_lookback=48), SRInversionParams(level_lookback=96, min_drop_atr=6.5)])
def test_sr_inversion_contract_and_no_lookahead(params):
    df = synthetic_ohlcv(2500, seed=3)
    assert_signal_contract(sr_inversion, df, params)
    assert_no_lookahead(sr_inversion, df, params)


def test_sr_inversion_fires_on_sweep_and_reclaim_only():
    """A hand-built tape: flat range 100–110 for 60 bars, a 6-ATR drop that pierces the
    range low and closes back above it (bar 60), then a drop that pierces and does NOT reclaim
    (bars 70–75). Exactly one long setup, on the reclaim bar, stop below the sweep low."""
    n = 90
    close = np.full(n, 105.0)
    high = np.full(n, 106.0)
    low = np.full(n, 104.0)
    low[30] = 100.0  # range low at 100 (inside the 48-bar window at bar 60)
    high[35] = 110.0  # range high at 110
    # bar 60: sweep + reclaim in one bar (ATR ≈ 2): low 97 < 100, close 101 > 100
    low[60], close[60], high[60] = 97.0, 101.0, 105.0
    for i in range(61, 70):
        close[i], high[i], low[i] = 102.0, 103.0, 101.0
    # bars 70+: breakdown without reclaim
    for i in range(70, n):
        close[i], high[i], low[i] = 96.0, 97.0, 95.0
    open_ = np.concatenate([[close[0]], close[:-1]])
    import polars as pl

    df = pl.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": np.ones(n)})
    p = SRInversionParams(level_lookback=48, min_drop_atr=1.0, atr_period=14)
    lv = sr_levels(df, p)
    longs = np.where(lv["long_setup"].to_numpy())[0]
    assert list(longs) == [60]
    assert lv["long_stop"][60] < 97.0
    assert lv["support"][60] == pytest.approx(100.0)
    sig = sr_inversion(df, p)
    assert sig[60] > 0
    assert (sig.fill_null(0.0).to_numpy()[70:] == 0).all()
