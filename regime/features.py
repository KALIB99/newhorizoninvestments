"""Regime features on the 1h clock. All rolling, all backward-looking."""

from __future__ import annotations

import numpy as np
import pandas as pd


def garman_klass_vol(df: pd.DataFrame, window: int = 24, ppy: int = 365 * 24) -> pd.Series:
    """Annualised Garman-Klass realised vol over ``window`` bars."""
    log_hl = np.log(df["high"] / df["low"]) ** 2
    log_co = np.log(df["close"] / df["open"]) ** 2
    gk = 0.5 * log_hl - (2 * np.log(2) - 1) * log_co
    return (gk.rolling(window).mean() * ppy).pow(0.5)


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder's ADX."""
    h, lo, c = df["high"], df["low"], df["close"]
    up = h.diff()
    dn = -lo.diff()
    plus_dm = up.where((up > dn) & (up > 0), 0.0)
    minus_dm = dn.where((dn > up) & (dn > 0), 0.0)
    tr = pd.concat([h - lo, (h - c.shift()).abs(), (lo - c.shift()).abs()], axis=1).max(axis=1)
    alpha = 1.0 / period
    atr = tr.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=alpha, adjust=False, min_periods=period).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=alpha, adjust=False, min_periods=period).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=alpha, adjust=False, min_periods=period).mean()


def _hurst_rs(x: np.ndarray) -> float:
    """Rescaled-range Hurst exponent of a return window, via log-log regression of R/S on
    sub-window size. ~0.5 random walk, > 0.5 trending, < 0.5 mean-reverting."""
    n = len(x)
    if n < 32 or np.all(x == x[0]):
        return np.nan
    sizes = [s for s in (8, 16, 32, 64, 128, 256) if s <= n // 2]
    rs = []
    for s in sizes:
        chunks = x[: (n // s) * s].reshape(-1, s)
        dev = np.cumsum(chunks - chunks.mean(axis=1, keepdims=True), axis=1)
        r = dev.max(axis=1) - dev.min(axis=1)
        sd = chunks.std(axis=1, ddof=1)
        ok = sd > 0
        if ok.any():
            rs.append((r[ok] / sd[ok]).mean())
        else:
            rs.append(np.nan)
    rs_arr = np.asarray(rs)
    good = ~np.isnan(rs_arr) & (rs_arr > 0)
    if good.sum() < 2:
        return np.nan
    slope, _ = np.polyfit(np.log(np.asarray(sizes)[good]), np.log(rs_arr[good]), 1)
    return float(slope)


def hurst_exponent(close: pd.Series, window: int = 256) -> pd.Series:
    r = np.log(close).diff()
    return r.rolling(window).apply(_hurst_rs, raw=True)


def regime_features(df: pd.DataFrame) -> pd.DataFrame:
    """Feature frame for the regime model. Requires open/high/low/close; ``funding_z`` is
    optional (0 if absent)."""
    out = pd.DataFrame(index=df.index)
    rv = garman_klass_vol(df)
    out["log_rv"] = np.log(rv.replace(0, np.nan))
    out["vol_of_vol"] = out["log_rv"].diff().rolling(24).std()
    out["hurst"] = hurst_exponent(df["close"])
    out["adx"] = adx(df)
    out["abs_funding_z"] = df["funding_z"].abs() if "funding_z" in df else 0.0
    out["rv"] = rv
    out["rv_pct"] = rv.rolling(24 * 90, min_periods=24 * 7).rank(pct=True)
    return out
