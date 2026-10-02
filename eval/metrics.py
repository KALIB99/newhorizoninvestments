"""Performance metrics. Never report ``sharpe`` without ``deflated_sharpe`` and ``pbo``.

References
- Bailey & López de Prado (2014), "The Deflated Sharpe Ratio".
- Bailey, Borwein, López de Prado & Zhu (2017), "The Probability of Backtest Overfitting".
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

EULER_GAMMA = 0.5772156649015329
MINUTES_PER_YEAR = 365 * 24 * 60


def periods_per_year(tf: str) -> int:
    """Bars per year for a timeframe string like '1m', '5m', '1h', '1d'."""
    unit = tf[-1]
    n = int(tf[:-1])
    minutes = {"m": 1, "h": 60, "d": 1440}[unit] * n
    return MINUTES_PER_YEAR // minutes


# ---- basic ------------------------------------------------------------------------------
def sharpe(returns: np.ndarray | pd.Series, ppy: int, rf: float = 0.0) -> float:
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    if len(r) < 2:
        return float("nan")
    sd = r.std(ddof=1)
    if sd == 0:
        return float("nan")
    return float((r.mean() - rf / ppy) / sd * math.sqrt(ppy))


def equity_curve(returns: np.ndarray | pd.Series) -> np.ndarray:
    r = np.nan_to_num(np.asarray(returns, dtype=float))
    return np.cumprod(1.0 + r)


def max_drawdown(returns: np.ndarray | pd.Series) -> float:
    """Max peak-to-trough drawdown as a negative fraction (e.g. -0.12)."""
    eq = equity_curve(returns)
    hwm = np.maximum.accumulate(eq)
    dd = eq / hwm - 1.0
    return float(dd.min()) if len(dd) else float("nan")


def calmar(returns: np.ndarray | pd.Series, ppy: int) -> float:
    r = np.asarray(returns, dtype=float)
    mdd = max_drawdown(r)
    if math.isnan(mdd) or len(r) == 0:
        return float("nan")
    ann = (equity_curve(r)[-1]) ** (ppy / len(r)) - 1.0
    if mdd == 0:
        return float("inf") if ann > 0 else float("nan")
    return float(ann / abs(mdd))


def turnover(position: np.ndarray | pd.Series) -> float:
    """Mean absolute position change per bar, in units of equity."""
    p = np.nan_to_num(np.asarray(position, dtype=float))
    return float(np.abs(np.diff(p, prepend=0.0)).mean()) if len(p) else float("nan")


def hit_rate(trade_pnls: np.ndarray | pd.Series) -> float:
    t = np.asarray(trade_pnls, dtype=float)
    t = t[~np.isnan(t)]
    return float((t > 0).mean()) if len(t) else float("nan")


def payoff_ratio(trade_pnls: np.ndarray | pd.Series) -> float:
    """Mean winner / |mean loser|."""
    t = np.asarray(trade_pnls, dtype=float)
    w, losses = t[t > 0], t[t < 0]
    if len(w) == 0 or len(losses) == 0:
        return float("nan")
    return float(w.mean() / abs(losses.mean()))


def monthly_pnl(returns: pd.Series) -> dict[str, float]:
    """{'2024-01': 0.021, ...} from a UTC-indexed per-bar return series."""
    if not isinstance(returns.index, pd.DatetimeIndex):
        raise TypeError("monthly_pnl needs a DatetimeIndex")
    idx = returns.index.tz_convert("UTC").tz_localize(None) if returns.index.tz is not None else returns.index
    m = (1.0 + returns.fillna(0.0)).groupby(idx.to_period("M")).prod() - 1.0
    return {str(k): float(v) for k, v in m.items()}


def per_regime_pnl(returns: pd.Series, regime: pd.Series) -> dict[str, float]:
    """Total compounded return per regime label (aligned series)."""
    df = pd.DataFrame({"r": returns, "g": regime}).dropna()
    out = (1.0 + df["r"]).groupby(df["g"]).prod() - 1.0
    return {str(k): float(v) for k, v in out.items()}


# ---- deflated sharpe ---------------------------------------------------------------------
@dataclass(frozen=True)
class DeflatedSharpe:
    sr: float  # observed, per-period
    sr0: float  # expected max SR under the null given n_trials, per-period
    psr: float  # probabilistic SR vs 0
    dsr: float  # probabilistic SR vs sr0  (= the Deflated Sharpe Ratio)
    p_value: float  # 1 - dsr; gate requires < 0.05
    n_trials: int
    n_obs: int


def probabilistic_sharpe(sr: float, sr_benchmark: float, n_obs: int, skew: float, kurt: float) -> float:
    """PSR: probability that the true SR exceeds ``sr_benchmark``. All SRs per-period.
    ``kurt`` is the *non-excess* kurtosis (normal = 3)."""
    if n_obs < 3:
        return float("nan")
    denom = math.sqrt(max(1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr**2, 1e-12))
    z = (sr - sr_benchmark) * math.sqrt(n_obs - 1) / denom
    return float(stats.norm.cdf(z))


def expected_max_sharpe(n_trials: int, sr_var: float) -> float:
    """E[max SR] across ``n_trials`` independent trials with SR variance ``sr_var``, under
    the null that every true SR is zero."""
    if n_trials <= 1:
        return 0.0
    n = float(n_trials)
    z1 = stats.norm.ppf(1.0 - 1.0 / n)
    z2 = stats.norm.ppf(1.0 - 1.0 / (n * math.e))
    return float(math.sqrt(max(sr_var, 0.0)) * ((1 - EULER_GAMMA) * z1 + EULER_GAMMA * z2))


def deflated_sharpe(
    returns: np.ndarray | pd.Series,
    n_trials: int,
    trial_sharpes: np.ndarray | None = None,
) -> DeflatedSharpe:
    """Deflated Sharpe Ratio for a per-period return series selected out of ``n_trials``.

    If the per-period Sharpe of *every* trial is supplied, their variance is used for
    E[max SR]. Otherwise we fall back to the estimator variance of the observed SR,
    (1 - γ3·SR + (γ4−1)/4·SR²)/(T−1), which is the standard approximation when only the
    trial count was logged. Log the trials; the fallback is less conservative.
    """
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    n_obs = len(r)
    if n_obs < 3 or r.std(ddof=1) == 0:
        return DeflatedSharpe(float("nan"), float("nan"), float("nan"), float("nan"), 1.0, n_trials, n_obs)
    sr = float(r.mean() / r.std(ddof=1))
    skew = float(stats.skew(r, bias=False))
    kurt = float(stats.kurtosis(r, fisher=False, bias=False))
    if trial_sharpes is not None and len(trial_sharpes) > 1:
        sr_var = float(np.var(np.asarray(trial_sharpes, dtype=float), ddof=1))
    else:
        sr_var = max(1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr**2, 1e-12) / (n_obs - 1)
    sr0 = expected_max_sharpe(max(int(n_trials), 1), sr_var)
    psr = probabilistic_sharpe(sr, 0.0, n_obs, skew, kurt)
    dsr = probabilistic_sharpe(sr, sr0, n_obs, skew, kurt)
    return DeflatedSharpe(sr, sr0, psr, dsr, 1.0 - dsr, int(n_trials), n_obs)


# ---- probability of backtest overfitting (CSCV) -------------------------------------------
@dataclass(frozen=True)
class PBOResult:
    pbo: float
    n_combinations: int
    logits: np.ndarray
    oos_sharpe_of_is_best: np.ndarray


def pbo(
    trial_returns: np.ndarray | pd.DataFrame,
    n_splits: int = 16,
    max_combinations: int = 1000,
    seed: int = 0,
) -> PBOResult:
    """Probability of Backtest Overfitting via combinatorially-symmetric cross-validation.

    ``trial_returns``: T × N matrix, one column per parameter combination tried.
    Rows are split into ``n_splits`` contiguous blocks; for each choice of half the blocks
    as in-sample we select the IS-best column and record its OOS relative rank. PBO is the
    fraction of splits where that rank is below the median (logit < 0).
    """
    M = np.asarray(trial_returns, dtype=float)
    if M.ndim != 2:
        raise ValueError("trial_returns must be 2-D (T × N)")
    T, N = M.shape
    if N < 2:
        raise ValueError("PBO needs at least 2 trials; log every parameter combination tried")
    if n_splits % 2:
        raise ValueError("n_splits must be even")
    M = M[: T - (T % n_splits)]
    blocks = np.array_split(M, n_splits, axis=0)
    all_combos = list(itertools.combinations(range(n_splits), n_splits // 2))
    rng = np.random.default_rng(seed)
    if len(all_combos) > max_combinations:
        idx = rng.choice(len(all_combos), size=max_combinations, replace=False)
        all_combos = [all_combos[i] for i in idx]

    def _sr(x: np.ndarray) -> np.ndarray:
        sd = x.std(axis=0, ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            s = np.where(sd > 0, x.mean(axis=0) / sd, -np.inf)
        return s

    logits, oos_best = [], []
    for combo in all_combos:
        is_idx = set(combo)
        is_mat = np.vstack([blocks[i] for i in range(n_splits) if i in is_idx])
        oos_mat = np.vstack([blocks[i] for i in range(n_splits) if i not in is_idx])
        n_star = int(np.argmax(_sr(is_mat)))
        oos_sr = _sr(oos_mat)
        rank = stats.rankdata(oos_sr)[n_star]  # 1..N
        omega = rank / (N + 1.0)
        logits.append(math.log(omega / (1.0 - omega)))
        oos_best.append(float(oos_sr[n_star]))
    logits_arr = np.asarray(logits)
    return PBOResult(float((logits_arr < 0).mean()), len(all_combos), logits_arr, np.asarray(oos_best))
