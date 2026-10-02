from __future__ import annotations

import math

import numpy as np
import pandas as pd

from risk.limits import LIMITS, RiskLimits


def realised_vol_ewma(returns: pd.Series, span: int = 20, ppy: int = 365 * 24) -> pd.Series:
    """Annualised EWMA realised vol. ``span=20`` per the risk-manager spec. Lagged by one
    bar so the scale used at t only knows returns through t−1 (no lookahead)."""
    var = returns.pow(2).ewm(span=span, adjust=False, min_periods=span).mean()
    return (var * ppy).pow(0.5).shift(1)


def vol_target_scale(
    returns: pd.Series,
    target: float = LIMITS.vol_target_annual,
    span: int = 20,
    ppy: int = 365 * 24,
    max_leverage: float = LIMITS.max_gross_exposure,
) -> pd.Series:
    """σ_target / σ_realised, capped at ``max_leverage``. Multiply the raw signal by this."""
    vol = realised_vol_ewma(returns, span, ppy)
    scale = (target / vol).clip(upper=max_leverage)
    return scale.fillna(0.0)


def kelly_fraction(trade_pnls: np.ndarray | pd.Series) -> float:
    """Continuous-approximation Kelly: f* = μ / σ² of per-trade returns (fraction of equity).
    Returns 0 when the edge is non-positive."""
    t = np.asarray(trade_pnls, dtype=float)
    t = t[~np.isnan(t)]
    if len(t) < 30:
        return 0.0  # not enough OOS trades to estimate; constitution says < 200 is weak anyway
    var = t.var(ddof=1)
    if var <= 0:
        return 0.0
    return float(max(t.mean() / var, 0.0))


def fractional_kelly(trade_pnls: np.ndarray | pd.Series, limits: RiskLimits = LIMITS) -> float:
    """0.25 × Kelly, capped so that a single trade cannot risk more than max_risk_per_trade
    given the worst observed trade loss."""
    f = limits.kelly_fraction * kelly_fraction(trade_pnls)
    t = np.asarray(trade_pnls, dtype=float)
    worst = float(np.nanmin(t)) if len(t) else 0.0
    if worst < 0:
        f = min(f, limits.max_risk_per_trade / abs(worst))
    return f


def correlation_clusters(returns: pd.DataFrame, cap: float = 0.7) -> list[list[str]]:
    """Group strategies whose pairwise |correlation| exceeds ``cap`` (single-linkage).
    Each cluster is treated as one strategy for budgeting."""
    cols = list(returns.columns)
    corr = returns.corr().abs().fillna(0.0)
    parent = {c: c for c in cols}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            if corr.loc[a, b] > cap:
                parent[find(a)] = find(b)
    groups: dict[str, list[str]] = {}
    for c in cols:
        groups.setdefault(find(c), []).append(c)
    return list(groups.values())


def combine_weights(
    returns: pd.DataFrame,
    shrink: float = 0.5,
    corr_cap: float = 0.7,
) -> pd.Series:
    """Inverse-variance weights shrunk toward equal weight (λ=shrink), with correlated
    pairs (> corr_cap) merged into one budget that is then split equally inside the cluster.
    Weights sum to 1. Recompute weekly."""
    if returns.shape[1] == 0:
        return pd.Series(dtype=float)
    clusters = correlation_clusters(returns, corr_cap)
    cluster_ret = pd.DataFrame({"+".join(c): returns[c].mean(axis=1) for c in clusters})
    var = cluster_ret.var(ddof=1).replace(0, np.nan)
    inv = (1.0 / var).fillna(0.0)
    iv = inv / inv.sum() if inv.sum() > 0 else pd.Series(1.0 / len(inv), index=inv.index)
    eq = pd.Series(1.0 / len(iv), index=iv.index)
    cw = (1 - shrink) * iv + shrink * eq
    out: dict[str, float] = {}
    for c in clusters:
        w = cw["+".join(c)] / len(c)
        for s in c:
            out[s] = float(w)
    return pd.Series(out).reindex(returns.columns)


def regime_multiplier(regime: str, limits: RiskLimits = LIMITS) -> float:
    try:
        return limits.regime_multipliers[regime]
    except KeyError as e:
        raise KeyError(f"unknown regime {regime!r}; expected {sorted(limits.regime_multipliers)}") from e


def position_from_signal(
    signal: float,
    realised_vol_annual: float,
    kelly_mult: float,
    regime: str,
    limits: RiskLimits = LIMITS,
) -> float:
    """w = s × (σ_target / σ) × f_kelly × regime_multiplier, clipped to the gross limit."""
    if realised_vol_annual <= 0 or math.isnan(realised_vol_annual):
        return 0.0
    w = signal * (limits.vol_target_annual / realised_vol_annual) * kelly_mult * regime_multiplier(regime, limits)
    return float(np.clip(w, -limits.max_gross_exposure, limits.max_gross_exposure))
