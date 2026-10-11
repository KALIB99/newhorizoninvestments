"""Funding-rate carry (spec §5.2): long spot / short perp while funding is rich.

Economic rationale (pre-registered before any result was seen)
---------------------------------------------------------------
Perpetual funding is the price leveraged longs pay to hold exposure without expiry. Retail
demand for leveraged upside is persistent and pro-cyclical, so funding is positive most of
the time and spikes in rallies. A delta-neutral holder (long spot, short perp) collects it.
The other side is the leveraged long who values convenience over cost. It is not
arbitraged away because it ties up ~1× equity in spot cash plus perp margin, carries
single-exchange (both legs are Binance), liquidation/ADL and basis risk, and the yield
compresses as soon as more capital arrives — it is a risk premium with limited capacity,
not a free lunch.

Falsification test: walk-forward OOS after fees on both legs, spread, slippage, and the
basis P&L of the hedge; DSR p < 0.05, PBO < 0.3, ≥ 100 OOS trades (multiday horizon,
T-018), positive at 1.5× costs.

Risk: per leg notional = risk_per_trade / basis_stop of equity (0.5% / 1.5% = 0.33×), so
a basis blow-out to the stop costs ≤ 0.5% of equity. Three symbols → gross 2.0×, net ≈ 0.

History: removed from the codebase on 2026-10-10 by CIO instruction and restored the same
day on CIO approval as the market-neutral ballast (tasks.md T-002 / T-018). Same rules, same
6-trial grid as the original pre-registration.

Results log
-----------
- @c6aea8f61b87 (BTC/ETH/SOL) and @10a3a9221ede (13 coins), 2026-10-10: OOS +12.8% / +11.5%,
  max DD −0.38% / −0.44%, DSR p < 1e-4, PBO 0.16 / 0.11, 11 / 20 trades → Insufficient evidence.
  Judge ruling (T-002): INSUFFICIENT EVIDENCE, exception denied — the trades are ~4 funding
  episodes, two of which carry all the P&L. Defects fixed in the same day: (1) the walk-forward
  stitch dropped the bar on which a deselected pair's exit filled (Σ trades $12,365 vs series
  $12,780); (2) pairs decided on the last active bar were opened and closed a bar later;
  (3) APR mis-scaled for 4h-funding symbols; (4) IS Sharpe now pooled like OOS. Corrected
  tearsheets (same hashes): OOS +12.1% / +12.3%, Sharpe 4.70 / 3.72, max DD −0.45% / −0.43%,
  PBO 0.11 / 0.07, 1.5× costs +3.62 / +3.15. Still not modelled: spot cash + perp margin ≤
  equity, stablecoin opportunity cost, exchange risk. Re-submission conditions: tasks.md T-002.
- Re-submission 2026-10-11, pre-registered before any run: same 6-trial grid, ``--prior-trials 12``
  (trials 13–18 on this hypothesis). History from 2020-01-01 (earliest Binance archive month
  for every symbol; later-listed coins enter when they list). Per-leg notional capped so that
  spot cash + perp initial margin (33%, 3× leverage) ≤ equity → 0.25× per leg, 3 pairs.
  Independent episode = held intervals across all symbols merged when the flat gap ≤ 7 days.
  Exception test (Judge's thresholds, applied by the researcher only to set the verdict; the
  gate still counts trades): ≥ 30 OOS episodes, ≥ 60% positive, moving-block bootstrap
  (block 10 days, 2000 draws, seed 0) 95% CI on invested-day Sharpe excludes zero.
  Sensitivities reported, not in headline P&L: 5% stablecoin APR on deployed cash (spot
  notional + margin) while invested; max perp-leg rally during each hold vs the 33% margin.
  Result @ab992575744a (BTC/ETH/SOL) / @e44affb7ad96 (13 coins), OOS 2020-06-29 → 2026-09-26:
  total +64% / +73% (CAGR 8.3% / 9.1%), Sharpe 5.32 / 4.88, max DD −0.63% / −0.98%, DSR p < 1e-4,
  **PBO 0.36 / 0.64 (fails < 0.30)**, 43 / 65 trades, **8 / 7 episodes** (88% / 71% positive),
  invested-day Sharpe CI [9.9, 14.0] / [8.5, 12.3], net of 5% cash yield +53% / +59%, positive at
  1.5× costs and in all 3 regimes. 79% of P&L is 2020–21; the Oct-2020→May-2021 episode alone is
  62%; 2022 and 2025 had no trades. 17/43 holds saw the perp leg rally > 33% (max +458%, SOL 2021):
  the hedge only survives in a multi-asset-margin account where spot gains collateralise the short.
  Exception thresholds NOT met → Insufficient evidence by the pre-registered rule. A first run of
  this re-submission silently zeroed everything after 2020-12-21 (Binance spot outage → NaN exit
  fill → NaN equity); fixed with a deferred-exit rule, a hard finite-equity check, and a test.

Run:  python -m research.strategies.funding_carry
"""

from __future__ import annotations

import argparse
import itertools
import json

import numpy as np
import pandas as pd
from loguru import logger

import data
from eval import metrics
from eval.costs import CostModel, spread_bps_for
from eval.cv import walk_forward
from eval.report import REPORTS_DIR, StrategySpec, Tearsheet
from regime import classify_rules, regime_features
from research.common import artifacts_dir, daily, git_sha, params_from_spec
from risk.kill_switch import KillSwitch
from risk.limits import LIMITS
from signals.base import Params

NAME = "funding_carry"


class FundingCarryParams(Params):
    symbols: tuple[str, ...] = ("BTC", "ETH", "SOL")
    timeframe: str = "1h"
    start: str = "2020-01-01"
    end: str = "2026-10-01"
    entry_apr: tuple[float, ...] = (0.15, 0.25, 0.40)
    exit_apr: tuple[float, ...] = (0.05, 0.10)
    apr_window_bars: int = 24
    basis_stop: float = 0.015
    perp_initial_margin: float = 0.33
    """Margin posted per unit of perp notional (3× leverage). Sizing enforces
    spot cash + perp margin ≤ equity; a rally beyond this within one hold would need a top-up."""
    cash_yield_apr: float = 0.05
    """Stablecoin yield forgone on deployed cash — a reported sensitivity, not charged to P&L."""
    episode_gap_days: int = 7
    spot_taker_fee_bps: float = 10.0
    perp_spread_bps: dict[str, float] = {"BTC": 1.0, "ETH": 1.0, "SOL": 2.0}
    spot_spread_bps: dict[str, float] = {"BTC": 1.0, "ETH": 1.0, "SOL": 2.0}
    wf_train_days: int = 180
    wf_test_days: int = 30
    wf_embargo_days: int = 2


STRATEGY = StrategySpec(
    name=NAME,
    description="Delta-neutral long spot / short perp on BTC/ETH/SOL while trailing 24h funding APR is rich.",
    rationale=__doc__ or "",
    signals=["funding_apr"],
    timeframe="1h",
    max_holding_bars=24 * 30,
    params_class="research.strategies.funding_carry.FundingCarryParams",
)


def load(p: FundingCarryParams) -> tuple[pd.DatetimeIndex, dict[str, pd.DataFrame]]:
    out = {}
    for b in p.symbols:
        perp = data.load(f"{b}/USDT:USDT", p.timeframe, p.start, p.end, features=["funding_paid", "funding_rate_last"])
        spot = data.load(f"{b}/USDT", p.timeframe, p.start, p.end, features=["quote_volume"])
        a = perp.to_pandas().set_index("ts_close")[["open", "high", "low", "close", "funding_paid", "funding_rate_last"]]
        s = spot.to_pandas().set_index("ts_close")[["open", "close", "quote_volume"]].add_prefix("spot_")
        d = a.join(s, how="inner")
        d.index = pd.DatetimeIndex(d.index).tz_convert("UTC")
        out[b] = d
    # Union index: later-listed coins are NaN until they list and are simply not tradable then.
    # (Intersection would truncate BTC/ETH history to the youngest symbol.)
    idx = out[p.symbols[0]].index
    for d in out.values():
        idx = idx.union(d.index)
    return idx, {b: d.reindex(idx) for b, d in out.items()}


def funding_apr(d: pd.DataFrame, window: int) -> pd.Series:
    """Realised funding over the trailing `window` bars, annualised. `funding_paid` is the rate
    settled *at* ts_close, so the value is known at the close; no lookahead. Summing what was
    actually paid makes the APR independent of the settlement interval (8h on majors, 4h on
    some alts) — the previous `mean(rate_last) × 3 × 365` mis-scaled 4h symbols (Judge, T-002)."""
    bars_per_year = 365.0 * 24.0 * 3600.0 / (d.index[1] - d.index[0]).total_seconds()
    return d["funding_paid"].rolling(window).sum() * (bars_per_year / window)


def leg_size(p: FundingCarryParams) -> tuple[float, int]:
    """Per-leg notional as a fraction of equity, and the number of concurrent pairs.

    Risk cap: a basis blow-out to the stop costs ≤ max_risk_per_trade → leg ≤ risk / basis_stop.
    Gross cap: 2 legs per pair → max_pairs = gross / (2 · leg).
    Cash cap (Judge, T-002): spot is bought with cash and the short perp posts initial margin,
    so max_pairs · leg · (1 + IM) ≤ 1.0 — the book must be fundable without borrowing."""
    leg = LIMITS.max_risk_per_trade / p.basis_stop
    max_pairs = int(LIMITS.max_gross_exposure / (2 * leg) + 1e-9)
    leg = min(leg, 1.0 / (max_pairs * (1.0 + p.perp_initial_margin)))
    return leg, max_pairs


def episodes(trades: pd.DataFrame, gap_days: int) -> pd.DataFrame:
    """Collapse overlapping/adjacent holds across symbols into independent episodes.

    A new episode starts only after the whole book has been flat for more than `gap_days`.
    Returns one row per episode: start, end, n_trades, pnl_usd."""
    if not len(trades):
        return pd.DataFrame(columns=["start", "end", "n_trades", "pnl_usd"])
    t = trades.sort_values("entry_ts").reset_index(drop=True)
    gap = pd.Timedelta(days=gap_days)
    rows: list[dict] = []
    cur: dict | None = None
    for _, x in t.iterrows():
        if cur is not None and x["entry_ts"] <= cur["end"] + gap:
            cur["end"] = max(cur["end"], x["exit_ts"])
            cur["n_trades"] += 1
            cur["pnl_usd"] += float(x["pnl_usd"])
        else:
            if cur is not None:
                rows.append(cur)
            cur = {"start": x["entry_ts"], "end": x["exit_ts"], "n_trades": 1, "pnl_usd": float(x["pnl_usd"])}
    if cur is not None:
        rows.append(cur)
    return pd.DataFrame(rows)


def block_bootstrap_sharpe_ci(r: np.ndarray, ppy: int, block: int = 10, n_boot: int = 2000, seed: int = 0,
                              level: float = 0.95) -> tuple[float, float]:
    """Moving-block bootstrap CI on the annualised Sharpe of a per-period return series.
    Blocks of consecutive observations preserve the autocorrelation that an IID bootstrap
    (and the DSR) would ignore — the Judge's objection to counting accrual days as bets."""
    r = np.asarray(r, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    if n < 2 * block:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(n_boot, n_blocks))
    offs = np.arange(block)
    samples = r[(starts[:, :, None] + offs[None, None, :]).reshape(n_boot, -1)[:, :n]]
    sd = samples.std(axis=1, ddof=1)
    sh = np.where(sd > 0, samples.mean(axis=1) / np.where(sd > 0, sd, 1.0) * np.sqrt(ppy), np.nan)
    a = (1.0 - level) / 2.0
    return float(np.nanquantile(sh, a)), float(np.nanquantile(sh, 1.0 - a))


def simulate_carry(idx: pd.DatetimeIndex, frames: dict[str, pd.DataFrame], p: FundingCarryParams,
                   entry: float, exit_: float, perp_costs: CostModel, spot_costs: CostModel,
                   active: np.ndarray | None = None, honour_dd_halt: bool = True,
                   initial_equity: float = 100_000.0) -> tuple[pd.Series, pd.DataFrame, list[str]]:
    T = len(idx)
    limits = LIMITS if honour_dd_halt else LIMITS.model_copy(update={"trailing_dd_limit": -1.0})
    ks = KillSwitch(limits, initial_equity=initial_equity)
    leg, max_pairs = leg_size(p)
    arr = {b: {k: d[k].to_numpy(float) for k in d.columns} for b, d in frames.items()}
    apr = {b: funding_apr(d, p.apr_window_bars).to_numpy(float) for b, d in frames.items()}
    act = np.ones(T, dtype=bool) if active is None else active
    pos: dict[str, dict] = {}
    pend_in: set[str] = set()
    pend_out: dict[str, str] = {}
    equity = initial_equity
    rets = np.zeros(T)
    trades, halts = [], []
    sticky = False

    def leg_cost(b: str, notional: float) -> float:
        c_p = float(perp_costs.per_side_bps(0.0, True, p.perp_spread_bps[b]))
        c_s = float(spot_costs.per_side_bps(0.0, True, p.spot_spread_bps[b]))
        return notional * (c_p + c_s) / 1e4

    for t in range(T):
        prev = equity
        for b, why in list(pend_out.items()):
            if b in pos:
                S, P = arr[b]["spot_open"][t], arr[b]["open"][t]
                if not (np.isfinite(S) and np.isfinite(P)):
                    continue  # venue gap (e.g. Binance spot outage 2020-12-21): exit at the next tradable open
                x = pos.pop(b)
                mtm = x["qs"] * (S - x["ls"]) - x["qp"] * (P - x["lp"])
                c = leg_cost(b, x["qs"] * S)
                equity += mtm - c
                x["pnl"] += mtm - c
                trades.append({"symbol": b, "entry_ts": idx[x["i"]], "exit_ts": idx[t], "pnl_usd": x["pnl"],
                               "funding_usd": x["fund"], "cost_usd": x["cost"] + c, "notional_usd": x["n"],
                               "bars_held": t - x["i"], "exit_reason": why})
                del pend_out[b]
            else:
                del pend_out[b]
        for b in list(pend_in):
            if sticky or ks.halted or not act[t]:
                continue  # decided on the last active bar; do not open a pair we would close next bar
            S, P = arr[b]["spot_open"][t], arr[b]["open"][t]
            if not (np.isfinite(S) and np.isfinite(P)):
                continue
            n = leg * equity * ks.risk_multiplier()
            c = leg_cost(b, n)
            equity -= c
            pos[b] = {"qs": n / S, "qp": n / P, "ls": S, "lp": P, "basis0": P / S - 1.0, "i": t, "pnl": -c,
                      "fund": 0.0, "cost": c, "n": n}
        pend_in.clear()

        for b, x in pos.items():
            S, P = arr[b]["spot_close"][t], arr[b]["close"][t]
            if not (np.isfinite(S) and np.isfinite(P)):
                continue
            mtm = x["qs"] * (S - x["ls"]) - x["qp"] * (P - x["lp"])
            fund = x["qp"] * P * np.nan_to_num(arr[b]["funding_paid"][t])
            equity += mtm + fund
            x["pnl"] += mtm + fund
            x["fund"] += fund
            x["ls"], x["lp"] = S, P
        rets[t] = equity / prev - 1.0
        if not np.isfinite(equity):
            raise RuntimeError(f"{NAME}: equity became non-finite at {idx[t]} — a NaN leaked into the ledger")

        now = idx[t].to_pydatetime()
        was = ks.halted
        ks.on_equity(equity, now)
        if ks.halted:
            if not was:
                halts.append(f"{idx[t].isoformat()} {','.join(ks.state.reasons)}")
                sticky = sticky or any(r != "daily_loss" for r in ks.state.reasons)
            for b in pos:
                pend_out[b] = "kill_switch"
            continue
        if not ks.can_trade(now):
            continue

        for b, x in pos.items():
            S, P = arr[b]["spot_close"][t], arr[b]["close"][t]
            if (P / S - 1.0) - x["basis0"] >= p.basis_stop:
                pend_out[b] = "basis_stop"
            elif apr[b][t] < exit_ or not act[t]:
                pend_out[b] = "signal" if act[t] else "deselected"
        if not act[t]:
            continue
        slots = max_pairs - (len(pos) - len(pend_out))
        cands = [b for b in frames if b not in pos and b not in pend_out
                 and np.isfinite(apr[b][t]) and apr[b][t] >= entry]
        for b in sorted(cands, key=lambda b: -apr[b][t])[: max(slots, 0)]:
            pend_in.add(b)

    before = equity
    for b in list(pos):
        x = pos.pop(b)
        c = leg_cost(b, x["qs"] * x["ls"])  # last marked spot price (the final bar may be a gap)
        equity -= c
        trades.append({"symbol": b, "entry_ts": idx[x["i"]], "exit_ts": idx[-1], "pnl_usd": x["pnl"] - c,
                       "funding_usd": x["fund"], "cost_usd": x["cost"] + c, "notional_usd": x["n"],
                       "bars_held": T - 1 - x["i"], "exit_reason": "end"})
    rets[-1] = (1 + rets[-1]) * equity / before - 1.0
    return pd.Series(rets, index=idx), pd.DataFrame(trades), halts


def pipeline(idx, frames, p: FundingCarryParams, perp_costs: CostModel, spot_costs: CostModel) -> dict:
    grid = [(e, x) for e, x in itertools.product(p.entry_apr, p.exit_apr) if x < e]
    runs = [simulate_carry(idx, frames, p, e, x, perp_costs, spot_costs, honour_dd_halt=False) for e, x in grid]
    D = pd.DataFrame({i: daily(r[0]) for i, r in enumerate(runs)})
    T = len(idx)
    bar_day = (idx - pd.Timedelta(hours=1)).normalize()
    oos = np.zeros(T, dtype=bool)
    # The final run is one continuous book: in each window it trades the selected (entry, exit)
    # pair, so we stitch per-window segments from the matching trial run.
    chosen = np.full(T, -1)
    windows, is_sh, is_parts = [], [], []
    for tr, te in walk_forward(D.index, f"{p.wf_train_days}D", f"{p.wf_test_days}D", f"{p.wf_embargo_days}D"):
        lo, hi = D.index[te[0]], D.index[te[-1]]
        mask = (bar_day >= lo) & (bar_day <= hi)
        oos |= mask
        sh = np.nan_to_num([metrics.sharpe(D[i].iloc[tr].to_numpy(), 365) for i in range(len(grid))], nan=-np.inf)
        best = int(np.argmax(sh))
        windows.append({"test_start": str(lo.date()), "trial": grid[best], "train_sharpe": round(float(sh[best]), 3)})
        if sh[best] > 0:
            chosen[mask] = best
            is_sh.append(float(sh[best]))
            is_parts.append(D[best].iloc[tr])
    # final: run each selected config only where selected (positions close on deselection)
    final_r = pd.Series(0.0, index=idx)
    final_trades, halts = [], []
    for i, (e, x) in enumerate(grid):
        act = chosen == i
        if not act.any():
            continue
        r, tdf, h = simulate_carry(idx, frames, p, e, x, perp_costs, spot_costs, active=act, honour_dd_halt=True)
        # A run driven by `active` holds nothing outside its windows (no entries while inactive,
        # exits on deselection), so its return series is already zero there. Do not mask it —
        # the old `act | roll(act, 1)` mask dropped the bar on which a deselected pair's exit
        # filled (open[t+2]), silently excluding exit costs (Judge, T-002, 2026-10-10).
        final_r += r
        final_trades.append(tdf)
        halts += h
    trades = pd.concat(final_trades) if final_trades else pd.DataFrame()
    is_daily = pd.concat(is_parts) if is_parts else pd.Series(dtype=float)
    return {"grid": grid, "runs": runs, "D": D, "oos": oos, "final_r": final_r, "trades": trades, "halts": halts,
            "windows": windows, "is_sh": is_sh, "is_daily": is_daily}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog=f"python -m research.strategies.{NAME}")
    ap.add_argument("--reports-dir", default=str(REPORTS_DIR))
    ap.add_argument("--symbols", nargs="+", help="base assets, e.g. BTC ETH XRP (default: the Params default)")
    ap.add_argument("--prior-trials", type=int, default=0, help="trials already spent on this hypothesis (feeds DSR)")
    args = ap.parse_args(argv)
    logger.disable("risk")
    over: dict = {}
    if args.symbols:
        sp = {b: spread_bps_for(b) for b in args.symbols}
        over = {"symbols": tuple(args.symbols), "perp_spread_bps": sp, "spot_spread_bps": sp}
    p = params_from_spec(STRATEGY, **over)
    idx, frames = load(p)
    perp = CostModel.from_fitted()
    spot = CostModel.from_fitted(taker_fee_bps=p.spot_taker_fee_bps, maker_fee_bps=p.spot_taker_fee_bps)
    res = pipeline(idx, frames, p, perp, spot)
    st = pipeline(idx, frames, p, perp.scaled(1.5), spot.scaled(1.5))

    oos = res["oos"]
    r_oos = res["final_r"][oos]
    d_oos = daily(r_oos)
    trades = res["trades"]
    if len(trades):
        trades = trades[trades["entry_ts"] >= r_oos.index[0]]
    pnl = trades["pnl_usd"].to_numpy() if len(trades) else np.array([])
    D = res["D"].loc[d_oos.index[0]:]
    trial_sh = np.array([metrics.sharpe(D[c].to_numpy(), 365) / np.sqrt(365) for c in D])
    n_trials = len(res["grid"]) + args.prior_trials
    dsr = metrics.deflated_sharpe(d_oos.to_numpy(), n_trials, trial_sharpes=trial_sh[np.isfinite(trial_sh)])
    pbo = metrics.pbo(D.to_numpy(), n_splits=16).pbo
    btc = frames[p.symbols[0]][["open", "high", "low", "close"]]
    regime = classify_rules(regime_features(btc))[oos]
    per_regime = metrics.per_regime_pnl(r_oos, regime)
    s_oos = metrics.sharpe(d_oos.to_numpy(), 365)
    # Pooled training-day returns of the selected trials, like-for-like with the pooled OOS series.
    s_is = metrics.sharpe(res["is_daily"].to_numpy(), 365) if len(res["is_daily"]) else float("nan")
    s_st = metrics.sharpe(daily(st["final_r"][st["oos"]]).to_numpy(), 365)
    eq = metrics.equity_curve(d_oos.to_numpy())
    n_tr = len(trades)
    min_trades = 100  # multiday horizon (eval.gate.GateThresholds.min_oos_trades_multiday)
    leg, max_pairs = leg_size(p)

    # ---- Judge's T-002 conditions: episodes, block-bootstrap CI, cash yield, margin ------------
    ep = episodes(trades, p.episode_gap_days)
    n_ep = len(ep)
    ep_pos = float((ep["pnl_usd"] > 0).mean()) if n_ep else float("nan")
    invested = d_oos[d_oos != 0].to_numpy()
    ci_lo, ci_hi = block_bootstrap_sharpe_ci(invested, 365, block=10, n_boot=2000, seed=0)
    sh_inv = metrics.sharpe(invested, 365) if len(invested) > 1 else float("nan")
    exception_ok = n_ep >= 30 and ep_pos >= 0.60 and np.isfinite(ci_lo) and ci_lo > 0
    bars_per_year = 365.0 * 24.0 * 3600.0 / (idx[1] - idx[0]).total_seconds()
    deployed = np.zeros(len(idx))
    max_rally, n_margin_breach = 0.0, 0
    for _, x in trades.iterrows():
        i0, i1 = idx.get_loc(x["entry_ts"]), idx.get_loc(x["exit_ts"])
        deployed[i0:i1 + 1] += x["notional_usd"] * (1.0 + p.perp_initial_margin) / 100_000.0
        f = frames[x["symbol"]]
        rally = float(f["high"].iloc[i0:i1 + 1].max() / f["open"].iloc[i0] - 1.0)
        max_rally = max(max_rally, rally)
        n_margin_breach += int(rally >= p.perp_initial_margin)
    opp_bar = pd.Series(deployed * p.cash_yield_apr / bars_per_year, index=idx)
    r_net = (res["final_r"] - opp_bar)[oos]
    d_net = daily(r_net)
    eq_net = metrics.equity_curve(d_net.to_numpy())
    s_net = metrics.sharpe(d_net.to_numpy(), 365)
    opp_usd = float(opp_bar[oos].sum() * 100_000.0)

    neutral_cap = 6.0  # eval.gate: market-neutral multiday plausibility cap (CIO-approved 2026-10-11)
    passes = (dsr.p_value < 0.05 and pbo < 0.3 and s_st > 0 and len(per_regime) >= 3
              and sum(v > 0 for v in per_regime.values()) >= 2 and s_is > 0 and s_oos / s_is >= 0.5
              and s_oos <= neutral_cap and not res["halts"])
    enough = n_tr >= min_trades or exception_ok
    if any("trailing_drawdown" in h for h in res["halts"]):
        verdict = "Reject"
    else:
        verdict = "Insufficient evidence" if not enough else ("Candidate for Judge" if passes else "Reject")
    notional = trades["notional_usd"].sum() if n_tr else 0.0
    med_hold_h = float(trades["bars_held"].median()) if n_tr else float("nan")
    notes = "\n\n".join([
        f"OOS {d_oos.index[0].date()} → {d_oos.index[-1].date()}: total {eq[-1] - 1:+.2%}, "
        f"CAGR {eq[-1] ** (365 / len(d_oos)) - 1:+.2%}, mean day {d_oos.mean():+.4%}, worst day {d_oos.min():+.2%}, "
        f"days invested {(d_oos != 0).mean():.0%}.",
        f"Sizing: {leg:.3f}× equity per leg, ≤ {max_pairs} pairs — capped by spot cash + {p.perp_initial_margin:.0%} "
        f"perp margin ≤ equity (binding) rather than by the 0.5% / {p.basis_stop:.1%} basis-stop risk rule.",
        f"Horizon: multiday — median hold {med_hold_h:,.0f} bars ({med_hold_h / 24:,.1f} days). Trade-count floor "
        f"{min_trades} (T-018); trades {n_tr}.",
        f"Independent episodes (book flat > {p.episode_gap_days}d between): {n_ep}, positive {ep_pos:.0%}; "
        f"invested-day Sharpe {sh_inv:+.2f}, moving-block bootstrap 95% CI [{ci_lo:+.2f}, {ci_hi:+.2f}] "
        f"(block 10d, 2000 draws). Exception thresholds ≥ 30 / ≥ 60% / CI > 0 → "
        f"{'MET' if exception_ok else 'NOT met'}. The gate still counts trades; the exception is the Judge's call.",
        f"Cash-yield sensitivity: {p.cash_yield_apr:.0%} stablecoin APR on deployed cash (spot + margin) while "
        f"invested = ${opp_usd:,.0f} over OOS → total net {eq_net[-1] - 1:+.2%} (vs {eq[-1] - 1:+.2%}), "
        f"Sharpe net {s_net:+.2f}. This is the strategy's excess return over parking the same cash in USDC.",
        f"Margin check: max perp-leg rally within a hold {max_rally:+.1%} vs initial margin {p.perp_initial_margin:.0%}; "
        f"holds breaching margin (would need a top-up from spot) {n_margin_breach}/{n_tr}.",
        f"Funding received ${trades['funding_usd'].sum() if n_tr else 0:,.0f}; costs paid "
        f"${trades['cost_usd'].sum() if n_tr else 0:,.0f}; basis + price P&L is the remainder.",
        f"Exit reasons: {trades['exit_reason'].value_counts().to_dict() if n_tr else {}}. Halts: {res['halts'] or 'none'}.",
        "Trial Sharpes (daily, full period): " + ", ".join(
            f"entry {e:.0%}/exit {x:.0%} {metrics.sharpe(res['D'][i].to_numpy(), 365):+.2f}" for i, (e, x) in enumerate(res["grid"])),
        f"1.5× costs: OOS Sharpe {s_st:+.2f}, halts {st['halts'] or 'none'}.",
        "Not modelled: single-exchange risk (both legs Binance), spot borrow for the negative-funding side (not "
        "traded), margin interest, ADL. Costs are the conservative default (spot taker 10 bps, perp taker 5 bps, both legs).",
    ])
    ts = Tearsheet(
        strategy=NAME, config_hash=p.config_hash(), params=p.model_dump(mode="json"),
        params_class=STRATEGY.params_class, code_ref=git_sha(), n_trials=n_trials,
        data_start=idx[0].to_pydatetime(), data_end=idx[-1].to_pydatetime(), timeframe=p.timeframe,
        horizon="multiday", market_neutral=True,
        symbols=[f"{b}/USDT:USDT+{b}/USDT" for b in p.symbols], cost_model=perp.model_dump(),
        cv=f"walk-forward {p.wf_train_days}D/{p.wf_test_days}D/{p.wf_embargo_days}D embargo; best-train-Sharpe selection",
        sharpe_oos=float(s_oos), sharpe_is=s_is, deflated_sharpe=float(dsr.dsr), dsr_p_value=float(dsr.p_value),
        pbo=float(pbo), max_drawdown=float(min(metrics.max_drawdown(d_oos.to_numpy()), 0.0)),
        calmar=float(metrics.calmar(d_oos.to_numpy(), 365)),
        turnover=float(2 * notional / 100_000 / max(oos.sum(), 1)),
        cost_drag_bps_per_trade=float(trades["cost_usd"].sum() / notional * 1e4) if notional else 0.0,
        n_trades_oos=n_tr, hit_rate=float(metrics.hit_rate(pnl)) if n_tr else None,
        payoff_ratio=float(metrics.payoff_ratio(pnl)) if n_tr else None, sharpe_oos_at_1_5x_costs=float(s_st),
        per_regime_pnl=per_regime, monthly_pnl=metrics.monthly_pnl(r_oos), verdict=verdict, notes=notes,
        sharpe_by_fold=[],
    )
    md_path, _ = ts.save(args.reports_dir)
    d = artifacts_dir(args.reports_dir, ts.stem)
    (d / "windows.json").write_text(json.dumps(res["windows"], indent=2, default=str))
    trades.to_csv(d / "trades.csv", index=False)
    ep.to_csv(d / "episodes.csv", index=False)
    (d / "diagnostics.json").write_text(json.dumps({
        "leg_fraction": leg, "max_pairs": max_pairs, "n_trades_oos": n_tr, "n_episodes_oos": n_ep,
        "episodes_positive_frac": ep_pos, "invested_day_sharpe": sh_inv, "block_bootstrap_ci95": [ci_lo, ci_hi],
        "exception_thresholds_met": bool(exception_ok), "cash_yield_apr": p.cash_yield_apr,
        "opportunity_cost_usd": opp_usd, "total_oos": float(eq[-1] - 1), "total_oos_net_cash_yield": float(eq_net[-1] - 1),
        "sharpe_oos_net_cash_yield": float(s_net), "max_perp_rally_in_hold": max_rally,
        "holds_breaching_margin": n_margin_breach, "perp_initial_margin": p.perp_initial_margin,
    }, indent=2, default=str))
    print(md_path.read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
