"""Cyclical inversion at support / resistance, traded on 1h BTC/ETH/SOL perps.

Economic rationale (pre-registered before any PnL was computed)
----------------------------------------------------------------
How this strategy sees the market. Price on a leveraged perp venue is not a random walk
around value; between news it is a machine that hunts resting liquidity. Stops and
liquidation prices cluster just beyond the obvious levels — the recent swing low (support)
and swing high (resistance) — because that is where every textbook tells traders to put
them. Price is pulled to those pools, the orders fire, and the resulting flow is *forced*:
a liquidation engine and a stop-loss do not care about value, they sell at any price. Forced
flow is also *finite*: once the pool is drained there is nobody left to sell, and the
market inverts back inside the range, usually fast, because the same move trapped the
breakout traders who sold the breakdown and now have to buy back. Then the cycle restarts
towards the other side of the range. We call the turn at the extreme the inversion and the
back-and-forth between the extremes the cycle.

Who is on the other side. (1) The leveraged longs being liquidated into the sweep and the
discretionary traders whose stops sat under the level — they are the forced sellers we buy
from. (2) The breakout/breakdown trader who shorts the break and is squeezed when it fails.
Both groups are structurally present on every exchange, every day.

Why it is not arbitraged away. The trade requires buying during the most violent minutes
of the day, after a large drop, with a hit rate well under 50%; most humans cannot do it
and most systematic momentum capital is positioned the other way. It is also costly to run
at scale: the edge is per-event and capacity-limited.

The biases we deliberately trade against. (a) "Do not catch a falling knife" — we only
catch it *after* it has stuck in the floor (the reclaim), which is the point. (b) "Stand
aside in Chaos" — the firm's prior gates directional risk out of the high-vol regime, but
forced flow is a high-vol phenomenon; this strategy is pre-registered to trade *all three*
regimes and lets the per-regime PnL adjudicate. (c) "Breakouts continue" — the counterfactual
diagnostic below measures what the breakdown-follower would have earned on the same bars.

Maximise profit, minimise loss (how the trade is managed). Stop = just beyond the sweep
extreme, the one price that falsifies the thesis; it is structural, not an ATR multiple,
and the position is sized so that stop costs 1R ≤ 0.5% of equity. After +1R the stop moves
to breakeven-after-costs (a failed inversion becomes a scratch). After +1.5R an ATR trail
arms and follows the move. The target is the other side of the cycle: a close at the
opposite level ends the trade. 72-bar time stop. Max 3 entries per symbol per day, 4-bar
cooldown after a loss, risk halves at −4% from the high-water mark (``TraderPrinciples``).

Falsification test (fixed in advance). Walk-forward OOS after fees + spread + slippage +
funding; DSR p < 0.05 over all 24 trials; PBO < 0.3; ≥ 200 OOS trades; positive at 1.5×
costs; positive in ≥ 2 of 3 regimes; OOS/IS Sharpe ≥ 0.5. Anything less is Reject or
Insufficient evidence. No parameter is changed after seeing results.

Dry system: PaperBroker only. Nothing here touches ``capital_allocation.yaml``.

Results log (appended after the fact; the pre-registration above was not edited)
-----------------------------------------------------------------------------
* @f6ba4f3a085f (24 trials, defaults): **Reject**. OOS Sharpe −0.47, DSR p 0.996, 226 trades,
  hit 30%, payoff 1.98, −8% trailing-DD halt 2025-08-13. Direction after a reclaim is right
  ~56% of the time over 24h (vs ~48% for sweeps that keep falling) but the first sweep low is
  usually re-tested: 68% of the −1R losers reached +1R within 72h. tasks.md T-013.
* @ede72ec78a6e / @f1f78f878d25 (pre-registered follow-up, stop 1.0 / 2.0 ATR beyond the
  sweep, prior trials 24 / 28): **Reject** both; wider stops swap hit rate for payoff and
  expectancy stays ≈ −0.15R. tasks.md T-014.
* @72fb5e9b8e1e (10 unseen coins: BNB XRP DOGE ADA AVAX LINK LTC DOT TRX BCH, prior 32) and
  @6ac762315bd4 (all 13, prior 56), original grid, no retuning: **Reject** both; OOS Sharpe
  −0.96 / −0.41, DD halt April 2024 on both, 0/24 trials positive. The BTC/SOL "reclaim
  carries direction" diagnostic fails on 7 of the 10 new coins. tasks.md T-016. Family
  closed at 80 trials. Remaining: T-012 (maker entries) as a cost lever, T-015 low prior.

Run:  python -m research.strategies.cyclical_inversion
      python -m research.strategies.cyclical_inversion --prior-trials 24 --set stop_buffer_atr=1.0 ...
"""

from __future__ import annotations

import argparse
import itertools
import json

import numpy as np
import pandas as pd
import polars as pl
from loguru import logger
from pydantic import Field

from eval.costs import CostModel, spread_bps_for
from eval.report import REPORTS_DIR, StrategySpec
from research.common import (
    WFConfig,
    align_frames,
    artifacts_dir,
    base_diagnostics,
    build_market,
    load_frames,
    make_tearsheet,
    np_series,
    params_from_spec,
    run_pipeline,
    summarise_oos,
)
from signals.base import Params
from signals.sr_inversion import SRInversionParams, sr_levels
from trader.engine import MarketData, SleeveConfig, SleeveInputs

NAME = "cyclical_inversion"
REGIMES_ALL = ("Trend", "Range", "Chaos")


class CyclicalInversionParams(Params):
    symbols: tuple[str, ...] = ("BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT")
    timeframe: str = "1h"
    start: str = "2023-01-01"
    end: str = "2026-10-01"
    spread_bps: dict[str, float] = Field(
        default_factory=lambda: {"BTC/USDT:USDT": 1.0, "ETH/USDT:USDT": 1.0, "SOL/USDT:USDT": 2.0}
    )
    # ---- pre-registered grid: 3 × 2 × 2 × 2 = 24 trials ----
    level_lookback: tuple[int, ...] = (48, 96, 168)
    """Range that defines support/resistance: 2, 4, 7 days of hourly bars."""
    min_drop_atr: tuple[float, ...] = (4.0, 6.5)
    """Size of the move into the level. 4 ≈ every sweep; 6.5 ≈ the largest ~30% (capitulations)."""
    trail_atr: tuple[float, ...] = (1.5, 3.0)
    """Trail distance once armed: tight (bank the bounce) vs loose (let the cycle run)."""
    sides: tuple[str, ...] = ("both", "long")
    """Symmetric, or long-only — crypto drops are liquidation-driven and faster than rallies."""
    # ---- fixed ----
    drop_lookback: int = 24
    sweep_atr: float = 0.1
    reclaim_window: int = 2
    stop_buffer_atr: float = 0.25
    breakeven_r: float = 1.0
    trail_after_r: float = 1.5
    max_hold: int = 72
    atr_period: int = 14
    allowed_regimes: tuple[str, ...] = REGIMES_ALL
    entry_style: str = "taker"
    """``taker`` (market at next open) or ``maker`` (post-only limit at the decision close, T-012)."""
    maker_ttl_bars: int = 1
    wf_train_days: int = 180
    wf_test_days: int = 30
    wf_embargo_days: int = 2


STRATEGY = StrategySpec(
    name=NAME,
    description="Liquidity-sweep inversion at support/resistance on 1h BTC/ETH/SOL perps: enter on the first "
    "close back inside a swept level after a large move into it, structural stop beyond the sweep, "
    "breakeven at +1R, ATR trail after +1.5R, target at the opposite level.",
    rationale=__doc__ or "",
    signals=["sr_inversion"],
    timeframe="1h",
    max_holding_bars=72,
    params_class="research.strategies.cyclical_inversion.CyclicalInversionParams",
)


def trial_name(n: int, k: float, trail: float, side: str) -> str:
    return f"inv_n{n}_k{k}_t{trail}_{side}"


def build_trials(frames: dict[str, pl.DataFrame], md: MarketData, p: CyclicalInversionParams) -> list[SleeveInputs]:
    """Every combination in the pre-registered grid, in a fixed order."""
    aligned = align_frames(frames, md.index)
    levels: dict[tuple[int, float], dict[str, pl.DataFrame]] = {}
    for n, k in itertools.product(p.level_lookback, p.min_drop_atr):
        sp = SRInversionParams(level_lookback=n, drop_lookback=p.drop_lookback, min_drop_atr=k, sweep_atr=p.sweep_atr,
                               reclaim_window=p.reclaim_window, stop_buffer_atr=p.stop_buffer_atr,
                               atr_period=p.atr_period)
        levels[(n, k)] = {s: sr_levels(f, sp) for s, f in aligned.items()}
    trials: list[SleeveInputs] = []
    for n, k, trail, side in itertools.product(p.level_lookback, p.min_drop_atr, p.trail_atr, p.sides):
        cfg = SleeveConfig(trial_name(n, k, trail, side), stop_atr=2.0, max_hold=p.max_hold,
                           allowed_regimes=p.allowed_regimes, trail=True, breakeven_r=p.breakeven_r,
                           trail_after_r=p.trail_after_r, trail_atr=trail, entry_style=p.entry_style,
                           maker_ttl_bars=p.maker_ttl_bars)
        entry, xl, xs, stop = {}, {}, {}, {}
        for s, f in aligned.items():
            lv = levels[(n, k)][s]
            lng = lv["long_setup"].to_numpy()
            sht = lv["short_setup"].to_numpy() if side == "both" else np.zeros(len(lng), dtype=bool)
            e = np.where(lng, 1, np.where(sht, -1, 0)).astype(int)
            close = np_series(f["close"])
            res, sup = np_series(lv["resistance"]), np_series(lv["support"])
            with np.errstate(invalid="ignore"):
                xl[s] = close >= res  # the cycle reached the other side
                xs[s] = close <= sup
            entry[s] = e
            stop[s] = np.where(lng, np_series(lv["long_stop"]), np.where(sht, np_series(lv["short_stop"]), np.nan))
        trials.append(SleeveInputs(cfg, entry, xl, xs, stop_px=stop))
    return trials


# ---- "crack the formula": does the reclaim carry information? -------------------------------
def sweep_diagnostics(frames: dict[str, pl.DataFrame], md: MarketData, p: CyclicalInversionParams,
                      horizon: int = 24) -> dict:
    """Descriptive, not a trial. For every downside sweep of the 96-bar support (k = 4): the
    forward ``horizon``-bar return in ATR units, split by whether the market reclaimed the level
    within the window (our entry) or kept falling (the breakdown-follower's entry). Positive
    'reclaimed' and non-positive 'not reclaimed' is the thesis; the opposite kills it."""
    aligned = align_frames(frames, md.index)
    sp = SRInversionParams(level_lookback=96, drop_lookback=p.drop_lookback, min_drop_atr=4.0, sweep_atr=p.sweep_atr,
                           reclaim_window=p.reclaim_window, stop_buffer_atr=p.stop_buffer_atr, atr_period=p.atr_period)
    out = {}
    for s, f in aligned.items():
        lv = sr_levels(f, sp)
        close, low, atr = np_series(f["close"]), np_series(f["low"]), np_series(lv["atr"])
        sup = np_series(lv["support"])
        w = p.reclaim_window
        swept = (low < sup - p.sweep_atr * atr) & ~lv["warm"].to_numpy()
        reclaimed = lv["long_setup"].to_numpy()
        # a sweep bar is 'resolved as reclaim' if a long setup fires within w bars of it
        rec_any = np.zeros_like(swept)
        for j in range(w + 1):
            rec_any[: len(rec_any) - j] |= reclaimed[j:]
        T = len(close)
        fwd = np.full(T, np.nan)
        fwd[: T - horizon] = (close[horizon:] - close[: T - horizon]) / atr[: T - horizon]
        # measure from the bar where the decision is made: the last bar of the window
        dec = np.arange(T) + w
        ok = dec < T - horizon
        idx = np.where(swept & ok)[0]
        f_rec = fwd[dec[idx[rec_any[idx]]]]
        f_not = fwd[dec[idx[~rec_any[idx]]]]
        out[s] = {
            "sweeps": int(len(idx)),
            "reclaimed_within_window": int(rec_any[idx].sum()),
            f"fwd_{horizon}h_atr_mean_reclaimed": float(np.nanmean(f_rec)) if len(f_rec) else None,
            f"fwd_{horizon}h_atr_mean_not_reclaimed": float(np.nanmean(f_not)) if len(f_not) else None,
            f"fwd_{horizon}h_hit_rate_reclaimed": float(np.nanmean(f_rec > 0)) if len(f_rec) else None,
            f"fwd_{horizon}h_hit_rate_not_reclaimed": float(np.nanmean(f_not > 0)) if len(f_not) else None,
        }
    return out


def render_notes(x: dict, sw: dict, s_stress: float, stress_halts: list[str]) -> str:
    lines = [
        f"OOS {x['oos_start']} → {x['oos_end']}. Total return {x['total_return']:+.2%}, CAGR {x['cagr']:+.2%}, "
        f"mean day {x['mean_daily_return']:+.4%}, best day {x['best_day']:+.2%}, worst day {x['worst_day']:+.2%}, "
        f"{x['pct_days_positive']:.0%} of days positive, {x['pct_days_flat']:.0%} flat.",
        f"Kill-switch halts in the final run: {x['halts'] or 'none'}.",
        f"Costs paid ${x.get('cost_usd', 0):,.0f}, funding paid ${x.get('funding_usd', 0):,.0f} (on $100k start). "
        f"Average {x.get('avg_R', float('nan')):+.3f}R per trade, median hold {x.get('median_bars_held', float('nan')):.0f} bars.",
        "By side: " + "; ".join(f"{k}: {v['trades']} trades, ${v['pnl_usd']:,.0f}, avg {v['avg_R']:+.3f}R, hit {v['hit_rate']:.0%}"
                                for k, v in x.get("by_side", {}).items()),
        "By symbol: " + "; ".join(f"{k}: {v['trades']} trades, ${v['pnl_usd']:,.0f}, avg {v['avg_R']:+.3f}R"
                                  for k, v in x.get("by_symbol", {}).items()),
        f"Exit reasons: {x.get('exit_reasons', {})}; avg R by exit: "
        + ", ".join(f"{k} {v:+.2f}" for k, v in x.get("avg_R_by_exit", {}).items()),
        f"Principles that fired (count of bars/setups): {x['rules_triggered']}",
        ("Evidence series without the DD halt (not used for the verdict): "
         + ", ".join(f"{k} {v:+.3f}" if isinstance(v, float) else f"{k} {v}"
                     for k, v in x["evidence_series_without_dd_halt"].items() if k != "note"))
        if "evidence_series_without_dd_halt" in x else "No DD halt in the final run.",
        "Trial Sharpes (daily, full period, single sleeve, 0.5% risk): "
        + ", ".join(f"{k} {v:+.2f}" for k, v in x["trial_daily_sharpes_full_period"].items()),
        "Sweep diagnostic (96-bar support, k=4, forward 24h in ATR): "
        + "; ".join(
            f"{k[:3]}: {v['sweeps']} sweeps, {v['reclaimed_within_window']} reclaimed → "
            f"{v['fwd_24h_atr_mean_reclaimed']:+.2f} ATR (hit {v['fwd_24h_hit_rate_reclaimed']:.0%}) vs not reclaimed "
            f"{v['fwd_24h_atr_mean_not_reclaimed']:+.2f} ATR (hit {v['fwd_24h_hit_rate_not_reclaimed']:.0%})"
            for k, v in sw.items()
        ),
        f"1.5× costs: OOS Sharpe {s_stress:+.2f}, halts {stress_halts or 'none'}.",
        "Tier-1 event windows are NOT applied (no event calendar yet, T-005). Regime = rules fallback. "
        "Costs are the conservative default model (no fitted slippage yet, T-007). Dry/paper system only.",
    ]
    return "\n\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog=f"python -m research.strategies.{NAME}")
    ap.add_argument("--reports-dir", default=str(REPORTS_DIR))
    ap.add_argument("--symbols", nargs="+", help="base assets, e.g. BTC ETH XRP (default: the Params default)")
    ap.add_argument("--prior-trials", type=int, default=0, help="trials already spent on this hypothesis (feeds DSR)")
    ap.add_argument("--set", action="append", default=[], metavar="FIELD=JSON",
                    help="override a Params field for a pre-registered follow-up, e.g. --set stop_buffer_atr=1.0 "
                         "--set 'level_lookback=[96,168]'. Every override changes the config hash.")
    args = ap.parse_args(argv)
    logger.disable("risk")
    over: dict = {}
    if args.symbols:
        over = {"symbols": tuple(f"{b}/USDT:USDT" for b in args.symbols),
                "spread_bps": {f"{b}/USDT:USDT": spread_bps_for(b) for b in args.symbols}}
    for kv in args.set:
        k, v = kv.split("=", 1)
        over[k] = json.loads(v)
    p: CyclicalInversionParams = params_from_spec(STRATEGY, **over)  # type: ignore[assignment]
    wf = WFConfig(p.wf_train_days, p.wf_test_days, p.wf_embargo_days)
    frames = load_frames(p.symbols, p.timeframe, p.start, p.end)
    logger.info("loaded {} symbols; building features/regimes", len(frames))
    md = build_market(frames, p.spread_bps, p.atr_period)
    trials = build_trials(frames, md, p)
    logger.info("{} pre-registered trials", len(trials))
    costs = CostModel.from_fitted()
    res = run_pipeline(md, trials, wf, costs)
    stress = run_pipeline(md, trials, wf, costs.scaled(1.5))
    s = summarise_oos(res, stress, md, p.symbols[0], prior_trials=args.prior_trials)
    extra = base_diagnostics(res, s)
    extra["sweep_diagnostic"] = sweep_diagnostics(frames, md, p)
    ts = make_tearsheet(STRATEGY, p, md, res, s, wf, render_notes(extra, extra["sweep_diagnostic"], s.sharpe_stress,
                                                                   stress.final.halts))
    md_path, _ = ts.save(args.reports_dir)
    d = artifacts_dir(args.reports_dir, ts.stem)
    (d / "diagnostics.json").write_text(json.dumps(extra, indent=2, default=str))
    res.final.trades.to_csv(d / "trades.csv", index=False)
    pd.Series(res.final.returns).to_frame("ret").to_csv(d / "returns.csv")
    print(md_path.read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
