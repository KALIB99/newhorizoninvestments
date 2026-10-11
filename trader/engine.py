"""Bar-by-bar portfolio simulator that trades like a disciplined day trader.

Timing (no lookahead): every decision is taken at the close of bar t using data through t
and filled at the open of bar t+1. Stops are resting orders checked intrabar against the
bar's high/low; a gap through the stop fills at the open. Every fill pays
``CostModel.per_side_bps``; stop fills pay extra spread; funding is charged on positions
open at each settlement close.

The same engine runs the per-trial research backtests and the final walk-forward run, so
the numbers in the tearsheet come from exactly the rules the trader would follow live.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from loguru import logger

from eval.costs import CostModel
from risk.kill_switch import KillSwitch
from risk.limits import LIMITS
from trader.principles import PRINCIPLES, TraderPrinciples


@dataclass(frozen=True)
class SleeveConfig:
    name: str
    stop_atr: float
    max_hold: int
    allowed_regimes: tuple[str, ...]
    trail: bool = True
    vol_band: tuple[float, float] | None = None
    breakeven_r: float | None = None
    """Once the best close is ≥ this many R in favour, the stop moves to entry + round-trip
    cost (a scratch, not a loss). None → never."""
    trail_after_r: float = 0.0
    """The trailing stop only arms once the best close is ≥ this many R in favour. 0 → from entry."""
    trail_atr: float | None = None
    """Trail distance in units of the *current* ATR. None → the trade's initial stop distance."""
    entry_style: str = "taker"
    """``taker``: market order at the next open. ``maker``: post-only limit at the decision
    close; fills only if a later bar trades *through* the limit (low < limit for a buy), at the
    limit or the bar's open if that is better, paying the maker fee. Unfilled after
    ``maker_ttl_bars`` bars → cancelled. Adverse selection is structural: you are filled
    precisely when price comes to you."""
    maker_ttl_bars: int = 1


@dataclass
class SleeveInputs:
    """Pre-computed, backward-looking arrays per symbol, all aligned to ``MarketData.index``.

    ``entry[sym][t]`` ∈ {-1, 0, +1}: a setup triggered at the close of t.
    ``exit_long/exit_short[sym][t]``: the sleeve's own exit condition at the close of t.
    ``stop_px[sym][t]`` (optional): an absolute, structural stop price decided at the close
    of t (e.g. just beyond the level that invalidates the setup). NaN → fall back to
    ``stop_atr × ATR`` below/above the fill.
    """

    config: SleeveConfig
    entry: dict[str, np.ndarray]
    exit_long: dict[str, np.ndarray]
    exit_short: dict[str, np.ndarray]
    stop_px: dict[str, np.ndarray] | None = None


@dataclass
class MarketData:
    index: pd.DatetimeIndex  # ts_close, UTC
    day: np.ndarray  # UTC trading day of each bar (from ts_open)
    open: dict[str, np.ndarray]
    high: dict[str, np.ndarray]
    low: dict[str, np.ndarray]
    close: dict[str, np.ndarray]
    atr: dict[str, np.ndarray]
    sigma_annual: dict[str, np.ndarray]
    funding: dict[str, np.ndarray]
    regime: dict[str, np.ndarray]
    rv_pct: dict[str, np.ndarray]
    adv_usd: dict[str, np.ndarray]
    spread_bps: dict[str, float]
    event_block: np.ndarray | None = None  # True where a Tier-1 window blocks new risk

    @property
    def symbols(self) -> list[str]:
        return list(self.close)


@dataclass
class _Pos:
    sleeve: int
    side: int
    qty: float
    entry_px: float
    entry_i: int
    stop: float
    dist: float
    best: float
    risk_usd: float
    last_px: float
    pnl: float = 0.0
    cost: float = 0.0
    funding: float = 0.0


@dataclass
class SimResult:
    returns: pd.Series
    equity: pd.Series
    trades: pd.DataFrame
    rules: Counter = field(default_factory=Counter)
    halts: list[str] = field(default_factory=list)


def simulate(
    md: MarketData,
    sleeves: list[SleeveInputs],
    principles: TraderPrinciples = PRINCIPLES,
    costs: CostModel | None = None,
    *,
    active: list[np.ndarray] | None = None,
    risk_frac: list[np.ndarray] | None = None,
    honour_dd_halt: bool = True,
    initial_equity: float = 100_000.0,
) -> SimResult:
    """Run the portfolio. ``active[s][t]`` switches sleeve ``s`` on at bar t (walk-forward
    selection); ``risk_frac[s][t]`` is its risk per trade (¼-Kelly from training data),
    always capped by ``principles.risk_per_trade``.

    ``honour_dd_halt=False`` is for per-trial research runs only, so that one drawdown does
    not truncate the series the walk-forward selects from. The final run always honours it.
    """
    costs = costs or CostModel.from_fitted()
    p = principles
    T = len(md.index)
    syms = md.symbols
    limits = LIMITS.model_copy(
        update={
            "daily_loss_limit": p.daily_loss_limit,
            "trailing_dd_limit": p.trailing_dd_limit if honour_dd_halt else -1.0,
            # the de-risk tier stays on in research runs: it is sizing, not a halt
        }
    )
    ks = KillSwitch(limits, initial_equity=initial_equity)
    rules: Counter = Counter()
    halts: list[str] = []
    ones = np.ones(T, dtype=bool)
    act = active or [ones] * len(sleeves)
    rfs = risk_frac or [np.full(T, p.risk_per_trade)] * len(sleeves)

    equity = initial_equity
    hwm = initial_equity
    pos: dict[str, _Pos] = {}
    pend_entry: dict[str, tuple[int, int, float, float, float, float, int]] = {}  # (sleeve, side, qty, dist, stop_px, limit, ttl)
    pend_exit: dict[str, str] = {}
    trades: list[dict] = []
    trades_today: Counter = Counter()
    consec_losses = 0
    last_loss_i: dict[str, int] = {}
    cur_day = None
    rets = np.zeros(T)
    eq = np.zeros(T)
    sticky_halt = False

    def fill_cost(sym: str, notional: float, stop: bool, taker: bool = True) -> float:
        adv = md.adv_usd[sym][t_]
        size_adv = notional / adv if adv and np.isfinite(adv) and adv > 0 else 0.0
        bps = float(costs.per_side_bps(size_adv, taker, md.spread_bps[sym]))
        if stop:
            bps += p.stop_extra_slippage_spreads * md.spread_bps[sym] * costs.multiplier
        return abs(notional) * bps / 1e4

    def close_pos(sym: str, px: float, reason: str, stop: bool) -> None:
        nonlocal equity, consec_losses
        ps = pos.pop(sym)
        mtm = ps.side * ps.qty * (px - ps.last_px)
        c = fill_cost(sym, ps.qty * px, stop)
        equity += mtm - c
        ps.pnl += mtm - c
        ps.cost += c
        r_mult = ps.pnl / ps.risk_usd if ps.risk_usd > 0 else 0.0
        trades.append(
            {
                "symbol": sym,
                "sleeve": sleeves[ps.sleeve].config.name,
                "sleeve_idx": ps.sleeve,
                "side": ps.side,
                "entry_ts": md.index[ps.entry_i],
                "exit_ts": md.index[t_],
                "entry_px": ps.entry_px,
                "exit_px": px,
                "qty": ps.qty,
                "risk_usd": ps.risk_usd,
                "notional_usd": ps.qty * ps.entry_px,
                "pnl_usd": ps.pnl,
                "cost_usd": ps.cost,
                "funding_usd": ps.funding,
                "r_multiple": r_mult,
                "bars_held": t_ - ps.entry_i,
                "exit_reason": reason,
            }
        )
        if ps.pnl < 0:
            consec_losses += 1
            last_loss_i[sym] = t_
        else:
            consec_losses = 0

    for t_ in range(T):
        day = md.day[t_]
        if day != cur_day:
            cur_day = day
            trades_today.clear()
            consec_losses = 0
        prev_eq = equity

        # 1) orders decided at the previous close fill at this open
        for sym, reason in list(pend_exit.items()):
            if sym in pos:
                close_pos(sym, md.open[sym][t_], reason, stop=False)
        pend_exit.clear()
        still_pending: dict[str, tuple[int, int, float, float, float, float, int]] = {}
        for sym, (s, side, qty, dist, sp, limit, ttl) in list(pend_entry.items()):
            if sticky_halt or ks.halted:
                continue
            px = md.open[sym][t_]
            if not np.isfinite(px):
                continue
            taker = not np.isfinite(limit)
            if not taker:
                lo_, hi_ = md.low[sym][t_], md.high[sym][t_]
                traded_through = (lo_ < limit) if side > 0 else (hi_ > limit)
                if not traded_through:
                    if ttl > 1:
                        still_pending[sym] = (s, side, qty, dist, sp, limit, ttl - 1)
                    else:
                        rules["maker_unfilled"] += 1
                    continue
                px = min(px, limit) if side > 0 else max(px, limit)
                rules["maker_filled"] += 1
            if np.isfinite(sp):
                # structural stop: the price is fixed, so the risk per unit depends on the fill.
                d_fill = side * (px - sp)
                if d_fill <= 0:
                    rules["skip_gap_through_stop"] += 1
                    continue
                if d_fill > dist:  # gapped away from the stop: shrink so $ at risk is unchanged
                    qty *= dist / d_fill
                    rules["shrunk_to_planned_risk"] += 1
                dist, stop = d_fill, sp
            else:
                stop = px - side * dist
            c = fill_cost(sym, qty * px, stop=False, taker=taker)
            equity -= c
            pos[sym] = _Pos(s, side, qty, px, t_, stop, dist, px, qty * dist, px, pnl=-c, cost=c)
        pend_entry = still_pending

        # 2) resting stops, intrabar
        for sym in list(pos):
            ps = pos[sym]
            o, h, lo = md.open[sym][t_], md.high[sym][t_], md.low[sym][t_]
            if not np.isfinite(lo):
                continue
            if ps.side > 0:
                if ps.entry_i < t_ and o <= ps.stop:
                    close_pos(sym, o, "stop_gap", stop=True)
                elif lo <= ps.stop:
                    close_pos(sym, ps.stop, "stop", stop=True)
            else:
                if ps.entry_i < t_ and o >= ps.stop:
                    close_pos(sym, o, "stop_gap", stop=True)
                elif h >= ps.stop:
                    close_pos(sym, ps.stop, "stop", stop=True)

        # 3) mark to market and funding at the close
        for sym, ps in pos.items():
            c = md.close[sym][t_]
            if not np.isfinite(c):
                continue
            mtm = ps.side * ps.qty * (c - ps.last_px)
            fund = ps.side * ps.qty * c * md.funding[sym][t_]
            equity += mtm - fund
            ps.pnl += mtm - fund
            ps.funding += fund
            ps.last_px = c
        rets[t_] = equity / prev_eq - 1.0 if prev_eq > 0 else 0.0
        eq[t_] = equity
        hwm = max(hwm, equity)

        # 4) kill switch at the close
        now = md.index[t_].to_pydatetime()
        was_halted = ks.halted
        ks.on_equity(equity, now)
        if ks.halted:
            if not was_halted:
                reason = ",".join(ks.state.reasons)
                halts.append(f"{md.index[t_].isoformat()} {reason} equity={equity:,.0f}")
                rules[f"halt_{reason}"] += 1
                if any(r != "daily_loss" for r in ks.state.reasons):
                    sticky_halt = True
            for sym in pos:
                pend_exit[sym] = "kill_switch"
            continue
        if not ks.can_trade(now):
            continue

        # 5) ratchet stops (never loosen): breakeven once +breakeven_r, trail once +trail_after_r
        for sym, ps in pos.items():
            cfg = sleeves[ps.sleeve].config
            c = md.close[sym][t_]
            if not np.isfinite(c):
                continue
            ps.best = max(ps.best, c) if ps.side > 0 else min(ps.best, c)
            gain_r = ps.side * (ps.best - ps.entry_px) / ps.dist if ps.dist > 0 else 0.0
            tighten = max if ps.side > 0 else min
            if cfg.breakeven_r is not None and gain_r >= cfg.breakeven_r:
                rt = 2.0 * float(costs.per_side_bps(0.0, True, md.spread_bps[sym])) / 1e4 * ps.entry_px
                ps.stop = tighten(ps.stop, ps.entry_px + ps.side * rt)
            if cfg.trail and gain_r >= cfg.trail_after_r:
                td = ps.dist
                if cfg.trail_atr is not None:
                    a = md.atr[sym][t_]
                    td = cfg.trail_atr * a if np.isfinite(a) and a > 0 else ps.dist
                ps.stop = tighten(ps.stop, ps.best - ps.side * td)

        # 6) sleeve exits and time stops
        for sym, ps in pos.items():
            sl = sleeves[ps.sleeve]
            if t_ - ps.entry_i >= sl.config.max_hold:
                pend_exit[sym] = "time"
            elif ps.side > 0 and sl.exit_long[sym][t_]:
                pend_exit[sym] = "signal"
            elif ps.side < 0 and sl.exit_short[sym][t_]:
                pend_exit[sym] = "signal"

        # 7) new entries
        if consec_losses >= p.max_consecutive_losses_per_day:
            rules["skip_consecutive_losses"] += 1
            continue
        if md.event_block is not None and md.event_block[t_]:
            rules["skip_event_window"] += 1
            continue
        dd = equity / hwm - 1.0
        derisk = p.drawdown_derisk_factor if dd <= p.drawdown_derisk_at else 1.0
        if ks.risk_multiplier() < 1.0:  # constitutional de-risk tier (risk/limits.py trailing_dd_derisk)
            derisk = min(derisk, ks.risk_multiplier())
            rules["derisk_dd_tier"] += 1
        gross = sum(ps.qty * md.close[s_][t_] for s_, ps in pos.items() if s_ not in pend_exit)
        net = sum(ps.side * ps.qty * md.close[s_][t_] for s_, ps in pos.items() if s_ not in pend_exit)
        vol_used = sum(
            ps.qty * md.close[s_][t_] / equity * md.sigma_annual[s_][t_] for s_, ps in pos.items() if s_ not in pend_exit
        )
        for s, sl in enumerate(sleeves):
            if not act[s][t_]:
                continue
            for sym in syms:
                if sym in pend_entry or (sym in pos and sym not in pend_exit):
                    continue
                d = int(sl.entry[sym][t_])
                if d == 0:
                    continue
                if md.regime[sym][t_] not in sl.config.allowed_regimes:
                    rules["skip_regime"] += 1
                    continue
                vb = sl.config.vol_band
                rv = md.rv_pct[sym][t_]
                if vb is not None and not (np.isfinite(rv) and vb[0] <= rv <= vb[1]):
                    rules["skip_vol_band"] += 1
                    continue
                if trades_today[sym] >= p.max_trades_per_symbol_per_day:
                    rules["skip_max_trades"] += 1
                    continue
                if sym in last_loss_i and t_ - last_loss_i[sym] <= p.cooldown_bars_after_loss:
                    rules["skip_cooldown"] += 1
                    continue
                c = md.close[sym][t_]
                sp = float(sl.stop_px[sym][t_]) if sl.stop_px is not None else float("nan")
                dist = d * (c - sp) if np.isfinite(sp) else sl.config.stop_atr * md.atr[sym][t_]
                sig = md.sigma_annual[sym][t_]
                if not (np.isfinite(dist) and dist > 0 and np.isfinite(sig) and sig > 0 and np.isfinite(c)):
                    if np.isfinite(sp) and np.isfinite(c):
                        rules["skip_stop_wrong_side"] += 1
                    continue
                rt_cost = 2.0 * float(costs.per_side_bps(0.0, True, md.spread_bps[sym])) / 1e4 * c
                if dist < p.min_stop_cost_multiple * rt_cost:
                    rules["skip_cost_vs_edge"] += 1
                    continue
                rf = min(float(rfs[s][t_]), p.risk_per_trade) * derisk
                if rf <= 0:
                    rules["skip_no_edge_in_training"] += 1
                    continue
                if derisk < 1.0:
                    rules["derisk_in_drawdown"] += 1
                want = rf * equity / (dist / c)
                cap = min(
                    want,
                    max(0.0, (p.vol_target_annual - vol_used) / sig * equity),
                    max(0.0, p.max_gross_exposure * equity - gross),
                    max(0.0, p.max_net_exposure * equity - d * net) if d * net >= 0 else want,
                )
                if cap < p.min_fill_fraction * want:
                    rules["skip_risk_budget_full"] += 1
                    continue
                if cap < want:
                    rules["shrunk_to_budget"] += 1
                maker = sl.config.entry_style == "maker"
                pend_entry[sym] = (s, d, cap / c, dist, sp, c if maker else float("nan"), sl.config.maker_ttl_bars)
                trades_today[sym] += 1
                gross += cap
                net += d * cap
                vol_used += cap / equity * sig

    # flatten at the end so every trade is closed and counted
    t_ = T - 1
    before = equity
    for sym in list(pos):
        close_pos(sym, md.close[sym][t_], "end", stop=False)
    if before > 0:
        rets[-1] = (1.0 + rets[-1]) * equity / before - 1.0
    eq[-1] = equity
    if halts:
        logger.debug("halts: {}", halts)
    return SimResult(
        returns=pd.Series(rets, index=md.index, name="ret"),
        equity=pd.Series(eq, index=md.index, name="equity"),
        trades=pd.DataFrame(trades),
        rules=rules,
        halts=halts,
    )
