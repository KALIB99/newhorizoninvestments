"""Shared research pipeline for strategies traded through ``trader.engine``.

A strategy module supplies (a) ``MarketData`` and (b) a list of pre-registered ``SleeveInputs``
trials. This module does the protocol work that must be identical for every strategy:

* every trial is simulated once under full costs (per-trial research runs, no DD halt);
* walk-forward selection (180D train / 30D test / 2D embargo): in each test window the
  trial with the best training Sharpe per family is switched on and sized at ¼-Kelly of
  its training trades, capped by ``risk_per_trade``; a family with no training edge sits out;
* the final run is one continuous book through the real ``KillSwitch``;
* the tearsheet is built from the OOS portion only, with DSR over *all* trials, PBO (CSCV)
  over the trial matrix, per-regime and monthly PnL, and the 1.5× cost stress.
"""

from __future__ import annotations

import importlib
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
from loguru import logger

import data
from eval import metrics
from eval.costs import CostModel
from eval.cv import walk_forward
from eval.report import StrategySpec, Tearsheet
from portfolio.sizing import kelly_fraction, realised_vol_ewma
from regime import classify_rules, regime_features
from signals.base import Params
from trader.engine import MarketData, SimResult, SleeveInputs, simulate
from trader.principles import PRINCIPLES, TraderPrinciples

DEFAULT_FEATURES = ["funding_paid", "funding_rate_last", "quote_volume", "taker_buy_volume"]


# ---- data -----------------------------------------------------------------------------------
def atr_pd(df: pd.DataFrame, n: int) -> pd.Series:
    h, lo, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h - lo, (h - c.shift()).abs(), (lo - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def load_frames(symbols: tuple[str, ...], tf: str, start: str, end: str,
                features: list[str] | None = None) -> dict[str, pl.DataFrame]:
    feats = DEFAULT_FEATURES if features is None else features
    return {s: data.load(s, tf, start, end, features=feats) for s in symbols}


def align_frames(frames: dict[str, pl.DataFrame], idx: pd.DatetimeIndex) -> dict[str, pl.DataFrame]:
    """Restrict every frame to the common ``MarketData.index`` so per-symbol arrays line up."""
    out = {}
    for s, f in frames.items():
        ts = pd.DatetimeIndex(f["ts_close"].to_pandas()).tz_convert("UTC")
        out[s] = f.filter(pl.Series(ts.isin(idx)))
    return out


def build_market(frames: dict[str, pl.DataFrame], spread_bps: dict[str, float], atr_period: int = 14) -> MarketData:
    pdf: dict[str, pd.DataFrame] = {}
    for s, f in frames.items():
        d = f.to_pandas().set_index("ts_close")
        d.index = pd.DatetimeIndex(d.index).tz_convert("UTC")
        pdf[s] = d
    syms = list(frames)
    idx = pdf[syms[0]].index
    for d in pdf.values():
        idx = idx.intersection(d.index)
    out: dict[str, dict[str, np.ndarray]] = {
        k: {} for k in ("open", "high", "low", "close", "atr", "sigma", "funding", "regime", "rv_pct", "adv")
    }
    for s, d in pdf.items():
        d = d.loc[idx]
        rf = regime_features(d[["open", "high", "low", "close"]])
        out["open"][s] = d["open"].to_numpy(float)
        out["high"][s] = d["high"].to_numpy(float)
        out["low"][s] = d["low"].to_numpy(float)
        out["close"][s] = d["close"].to_numpy(float)
        out["atr"][s] = atr_pd(d, atr_period).to_numpy(float)
        out["sigma"][s] = realised_vol_ewma(np.log(d["close"]).diff(), span=20 * 24).to_numpy(float)
        out["funding"][s] = d["funding_paid"].fillna(0.0).to_numpy(float) if "funding_paid" in d else np.zeros(len(d))
        out["regime"][s] = classify_rules(rf).to_numpy(object)
        out["rv_pct"][s] = rf["rv_pct"].to_numpy(float)
        qv = d["quote_volume"] if "quote_volume" in d else d["volume"] * d["close"]
        out["adv"][s] = qv.rolling(24).sum().shift(1).to_numpy(float)
    day = (idx - pd.Timedelta(hours=1)).normalize().to_numpy()
    return MarketData(
        index=idx, day=day, open=out["open"], high=out["high"], low=out["low"], close=out["close"],
        atr=out["atr"], sigma_annual=out["sigma"], funding=out["funding"], regime=out["regime"],
        rv_pct=out["rv_pct"], adv_usd=out["adv"], spread_bps={s: spread_bps[s] for s in syms},
    )


def np_series(s: pl.Series) -> np.ndarray:
    return s.cast(pl.Float64).fill_null(np.nan).to_numpy()


# ---- walk-forward ---------------------------------------------------------------------------
def daily(r: pd.Series) -> pd.Series:
    return (1.0 + r).resample("1D").prod() - 1.0


@dataclass
class WalkForward:
    active: list[np.ndarray]
    risk: list[np.ndarray]
    oos_mask: np.ndarray
    windows: list[dict]
    is_sharpes: list[float]


@dataclass(frozen=True)
class WFConfig:
    train_days: int = 180
    test_days: int = 30
    embargo_days: int = 2


def family_of(name: str) -> str:
    return name.split("_", 1)[0]


def select(md: MarketData, trials: list[SleeveInputs], runs: list[SimResult], wf: WFConfig,
           principles: TraderPrinciples, family: Callable[[str], str] = family_of) -> WalkForward:
    """Per test window and per family: pick the trial with the best Sharpe on the training
    window and size it at ¼-Kelly of its training trades (capped at risk_per_trade). A family
    whose best training Sharpe ≤ 0 or Kelly ≤ 0 sits the window out."""
    T = len(md.index)
    D = pd.DataFrame({i: daily(r.returns) for i, r in enumerate(runs)})
    fams: dict[str, list[int]] = {}
    for i, t in enumerate(trials):
        fams.setdefault(family(t.config.name), []).append(i)
    active = [np.zeros(T, dtype=bool) for _ in trials]
    risk = [np.zeros(T) for _ in trials]
    oos = np.zeros(T, dtype=bool)
    windows, is_sh = [], []
    bar_day = pd.DatetimeIndex(md.day)
    bar_day = bar_day.tz_localize(None) if bar_day.tz is not None else bar_day
    didx = D.index.tz_localize(None) if D.index.tz is not None else D.index
    for tr, te in walk_forward(D.index, f"{wf.train_days}D", f"{wf.test_days}D", f"{wf.embargo_days}D"):
        lo, hi = didx[te[0]], didx[te[-1]]
        mask = (bar_day >= lo) & (bar_day <= hi)
        oos |= mask
        tr_lo, tr_hi = D.index[tr[0]], D.index[tr[-1]] + pd.Timedelta(days=1)
        rec = {"test_start": str(lo.date()), "test_end": str(hi.date())}
        for fam, ids in fams.items():
            sh = {i: metrics.sharpe(D[i].iloc[tr].to_numpy(), 365) for i in ids}
            best = max(ids, key=lambda i: -np.inf if np.isnan(sh[i]) else sh[i])
            tdf = runs[best].trades
            if len(tdf):
                inside = (tdf["entry_ts"] >= tr_lo) & (tdf["exit_ts"] < tr_hi)
                rmult = tdf.loc[inside, "r_multiple"].to_numpy()
            else:
                rmult = np.array([])
            f = principles.kelly_fraction * kelly_fraction(rmult)
            rf = min(principles.risk_per_trade, f) if sh[best] > 0 else 0.0
            rec[fam] = {"trial": trials[best].config.name, "train_sharpe": round(float(sh[best]), 3),
                        "train_trades": int(len(rmult)), "risk_per_trade": round(rf, 5)}
            if rf > 0:
                active[best] |= mask
                risk[best][mask] = rf
                is_sh.append(float(sh[best]))
        windows.append(rec)
    return WalkForward(active, risk, oos, windows, is_sh)


@dataclass
class PipelineResult:
    trials: list[SleeveInputs]
    runs: list[SimResult]
    wf: WalkForward
    final: SimResult
    costs: CostModel
    final_unhalted: SimResult | None = None
    """The same book without the sticky trailing-DD halt. Never used for the verdict (the halt
    is what you would live through); reported so one drawdown event does not erase the
    statistical evidence about the signal."""


def run_pipeline(md: MarketData, trials: list[SleeveInputs], wf: WFConfig, costs: CostModel,
                 principles: TraderPrinciples = PRINCIPLES) -> PipelineResult:
    runs = []
    for t in trials:
        runs.append(simulate(md, [t], principles, costs, honour_dd_halt=False))
        logger.info("trial {:<28} trades={:>5} sharpe(daily)={:+.2f}", t.config.name, len(runs[-1].trades),
                    metrics.sharpe(daily(runs[-1].returns).to_numpy(), 365))
    sel = select(md, trials, runs, wf, principles)
    final = simulate(md, trials, principles, costs, active=sel.active, risk_frac=sel.risk, honour_dd_halt=True)
    unhalted = None
    if final.halts:
        unhalted = simulate(md, trials, principles, costs, active=sel.active, risk_frac=sel.risk, honour_dd_halt=False)
    return PipelineResult(trials, runs, sel, final, costs, unhalted)


# ---- tearsheet ------------------------------------------------------------------------------
@dataclass
class OOSSummary:
    trades: pd.DataFrame
    r_oos: pd.Series
    d_oos: pd.Series
    sharpe_oos: float
    sharpe_is: float
    sharpe_stress: float
    dsr: metrics.DeflatedSharpe
    pbo: float
    per_regime: dict[str, float]
    folds: list[float]
    eq_oos: np.ndarray
    cost_bps: float
    turnover: float
    n_trials: int
    verdict: str


def summarise_oos(res: PipelineResult, stress: PipelineResult, md: MarketData, regime_symbol: str,
                  prior_trials: int = 0) -> OOSSummary:
    oos = res.wf.oos_mask
    r_oos = res.final.returns[oos]
    d_oos = daily(r_oos)
    trades = res.final.trades
    if len(trades):
        trades = trades[trades["entry_ts"] >= r_oos.index[0]]
    trial_daily = pd.DataFrame({i: daily(r.returns) for i, r in enumerate(res.runs)}).loc[d_oos.index[0]:]
    trial_sh = np.array([metrics.sharpe(trial_daily[c].to_numpy(), 365) / np.sqrt(365) for c in trial_daily])
    n_trials = len(res.trials) + prior_trials
    dsr = metrics.deflated_sharpe(d_oos.to_numpy(), n_trials, trial_sharpes=trial_sh[np.isfinite(trial_sh)])
    pbo = float(metrics.pbo(trial_daily.to_numpy(), n_splits=16).pbo)
    regime = pd.Series(md.regime[regime_symbol], index=md.index)[oos]
    per_regime = metrics.per_regime_pnl(r_oos, regime)
    folds = []
    for w in res.wf.windows:
        seg = d_oos.loc[w["test_start"]:w["test_end"]]
        if len(seg) > 2 and seg.std() > 0:
            folds.append(round(float(metrics.sharpe(seg.to_numpy(), 365)), 2))
    sharpe_oos = float(metrics.sharpe(d_oos.to_numpy(), 365))
    sharpe_is = float(np.mean(res.wf.is_sharpes)) if res.wf.is_sharpes else float("nan")
    sharpe_stress = float(metrics.sharpe(daily(stress.final.returns[stress.wf.oos_mask]).to_numpy(), 365))
    eq_oos = metrics.equity_curve(d_oos.to_numpy())
    notional = float(trades["notional_usd"].sum()) if len(trades) else 0.0
    cost_bps = float(trades["cost_usd"].sum() / notional * 1e4) if notional else 0.0
    turnover = float(2 * notional / res.final.equity[oos].mean() / oos.sum()) if oos.sum() else 0.0
    n_tr = int(len(trades))
    passes = (
        dsr.p_value < 0.05 and pbo < 0.30 and n_tr >= 200 and sharpe_stress > 0
        and sum(v > 0 for v in per_regime.values()) >= 2 and len(per_regime) >= 3
        and sharpe_is > 0 and sharpe_oos / sharpe_is >= 0.5 and sharpe_oos <= 3.0
        and not res.final.halts
    )
    if any("trailing_drawdown" in h for h in res.final.halts):
        verdict = "Reject"
    elif n_tr < 200:
        verdict = "Insufficient evidence"
    elif passes:
        verdict = "Candidate for Judge"
    else:
        verdict = "Reject"
    return OOSSummary(trades, r_oos, d_oos, sharpe_oos, sharpe_is, sharpe_stress, dsr, pbo, per_regime, folds,
                      eq_oos, cost_bps, turnover, n_trials, verdict)


def make_tearsheet(spec: StrategySpec, p: Params, md: MarketData, res: PipelineResult, s: OOSSummary,
                   wf: WFConfig, notes: str) -> Tearsheet:
    pnl = s.trades["pnl_usd"].to_numpy() if len(s.trades) else np.array([])
    n_tr = int(len(s.trades))
    return Tearsheet(
        strategy=spec.name,
        config_hash=p.config_hash(),
        params=p.model_dump(mode="json"),
        params_class=spec.params_class,
        code_ref=git_sha(),
        n_trials=s.n_trials,
        data_start=md.index[0].to_pydatetime(),
        data_end=md.index[-1].to_pydatetime(),
        timeframe=spec.timeframe,
        symbols=list(md.symbols),
        cost_model=res.costs.model_dump(),
        cv=f"walk-forward {wf.train_days}D train / {wf.test_days}D test / {wf.embargo_days}D embargo; "
           "per-family best-train-Sharpe selection; ¼-Kelly risk from train trades",
        sharpe_oos=s.sharpe_oos,
        sharpe_is=s.sharpe_is,
        deflated_sharpe=float(s.dsr.dsr),
        dsr_p_value=float(s.dsr.p_value),
        pbo=s.pbo,
        max_drawdown=float(min(metrics.max_drawdown(s.d_oos.to_numpy()), 0.0)),
        calmar=float(metrics.calmar(s.d_oos.to_numpy(), 365)),
        turnover=s.turnover,
        cost_drag_bps_per_trade=s.cost_bps,
        n_trades_oos=n_tr,
        hit_rate=float(metrics.hit_rate(pnl)) if n_tr else None,
        payoff_ratio=float(metrics.payoff_ratio(pnl)) if n_tr else None,
        sharpe_oos_at_1_5x_costs=s.sharpe_stress,
        per_regime_pnl=s.per_regime,
        monthly_pnl=metrics.monthly_pnl(s.r_oos),
        sharpe_by_fold=s.folds,
        verdict=s.verdict,  # type: ignore[arg-type]
        notes=notes,
    )


def base_diagnostics(res: PipelineResult, s: OOSSummary) -> dict:
    d_oos, trades = s.d_oos, s.trades
    out: dict = {
        "oos_start": str(d_oos.index[0].date()),
        "oos_end": str(d_oos.index[-1].date()),
        "total_return": float(s.eq_oos[-1] - 1.0),
        "cagr": float(s.eq_oos[-1] ** (365 / len(d_oos)) - 1.0),
        "mean_daily_return": float(d_oos.mean()),
        "best_day": float(d_oos.max()),
        "worst_day": float(d_oos.min()),
        "pct_days_positive": float((d_oos > 0).mean()),
        "pct_days_flat": float((d_oos == 0).mean()),
        "halts": res.final.halts,
        "rules_triggered": dict(res.final.rules.most_common()),
    }
    if res.final_unhalted is not None:
        oos = res.wf.oos_mask
        ru = res.final_unhalted.returns[oos]
        du = daily(ru)
        tu = res.final_unhalted.trades
        tu = tu[tu["entry_ts"] >= ru.index[0]] if len(tu) else tu
        out["evidence_series_without_dd_halt"] = {
            "sharpe_oos": float(metrics.sharpe(du.to_numpy(), 365)),
            "total_return": float(metrics.equity_curve(du.to_numpy())[-1] - 1.0),
            "max_drawdown": float(metrics.max_drawdown(du.to_numpy())),
            "n_trades_oos": int(len(tu)),
            "avg_R": float(tu["r_multiple"].mean()) if len(tu) else None,
            "note": "verdict uses the halted book; this is what the signal did if you could have kept trading",
        }
    if len(trades):
        out["by_symbol"] = {
            k: {"trades": int(len(t)), "pnl_usd": float(t["pnl_usd"].sum()), "avg_R": float(t["r_multiple"].mean())}
            for k, t in trades.groupby("symbol")
        }
        out["by_side"] = {
            ("long" if k > 0 else "short"): {"trades": int(len(t)), "pnl_usd": float(t["pnl_usd"].sum()),
                                             "avg_R": float(t["r_multiple"].mean()),
                                             "hit_rate": float((t["pnl_usd"] > 0).mean())}
            for k, t in trades.groupby("side")
        }
        out["by_sleeve"] = {
            k: {"trades": int(len(t)), "pnl_usd": float(t["pnl_usd"].sum()), "avg_R": float(t["r_multiple"].mean())}
            for k, t in trades.groupby("sleeve")
        }
        out["exit_reasons"] = {k: int(v) for k, v in trades["exit_reason"].value_counts().items()}
        out["avg_R_by_exit"] = {k: float(t["r_multiple"].mean()) for k, t in trades.groupby("exit_reason")}
        out["avg_R"] = float(trades["r_multiple"].mean())
        out["median_bars_held"] = float(trades["bars_held"].median())
        out["funding_usd"] = float(trades["funding_usd"].sum())
        out["cost_usd"] = float(trades["cost_usd"].sum())
    out["trial_daily_sharpes_full_period"] = {
        t.config.name: round(float(metrics.sharpe(daily(r.returns).to_numpy(), 365)), 3)
        for t, r in zip(res.trials, res.runs, strict=True)
    }
    out["trial_trades_full_period"] = {t.config.name: int(len(r.trades)) for t, r in zip(res.trials, res.runs, strict=True)}
    out["walk_forward_windows"] = res.wf.windows
    return out


# ---- misc -----------------------------------------------------------------------------------
def params_from_spec(spec: StrategySpec, **overrides: object) -> Params:
    """Instantiate the Params class by its dotted path, so the config hash names the real module
    even under ``python -m`` (where the strategy file runs as ``__main__``)."""
    mod, cls = spec.params_class.rsplit(".", 1)
    return getattr(importlib.import_module(mod), cls)(**overrides)


def artifacts_dir(reports_dir: str | Path, stem: str) -> Path:
    """Side artefacts live in a subfolder: eval.gate globs ``<strategy>_*.json`` at the top level."""
    d = Path(reports_dir) / "artifacts" / stem
    d.mkdir(parents=True, exist_ok=True)
    return d


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603,S607
    except Exception:  # noqa: BLE001
        return ""
