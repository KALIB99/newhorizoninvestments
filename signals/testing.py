"""Contract tests every signal must pass. Import these in the signal's test module."""

from __future__ import annotations

import numpy as np
import polars as pl

from signals.base import Params, SignalFn


class SignalContractError(AssertionError):
    pass


def assert_signal_contract(fn: SignalFn, df: pl.DataFrame, params: Params) -> pl.Series:
    """Shape, dtype, range and NaN checks. Returns the computed signal."""
    out = fn(df, params)
    if not isinstance(out, pl.Series):
        raise SignalContractError(f"signal must return pl.Series, got {type(out)}")
    if len(out) != df.height:
        raise SignalContractError(f"signal length {len(out)} != input height {df.height}")
    if out.dtype not in (pl.Float64, pl.Float32):
        raise SignalContractError(f"signal dtype must be float, got {out.dtype}")
    vals = out.drop_nulls()
    if vals.is_nan().any():
        raise SignalContractError("signal contains NaN; use null for 'no signal'")
    if len(vals) and (vals.min() < -1.0 - 1e-12 or vals.max() > 1.0 + 1e-12):
        raise SignalContractError(f"signal outside [-1, 1]: min={vals.min()} max={vals.max()}")
    if len(vals) == 0:
        raise SignalContractError("signal is entirely null")
    return out


def assert_no_lookahead(
    fn: SignalFn,
    df: pl.DataFrame,
    params: Params,
    n_checks: int = 6,
    atol: float = 1e-9,
) -> None:
    """A signal has no lookahead iff its value at bar t is unchanged when all bars after t
    are removed. We compute the signal on the full frame and on several prefixes and
    require the overlapping values to agree.

    Rolling-window signals warm up identically on both, so this catches: centred windows,
    ``shift(-k)``, full-sample normalisation (z-scoring with the global mean/std), and
    anything that peeks at the future.
    """
    full = fn(df, params).to_numpy().astype(float)
    n = df.height
    if n < 20:
        raise ValueError("need at least 20 bars to test lookahead meaningfully")
    cut_points = np.linspace(n // 2, n - 1, num=n_checks, dtype=int)
    for k in cut_points:
        prefix = fn(df.head(int(k)), params).to_numpy().astype(float)
        a, b = full[:k], prefix
        both = ~(np.isnan(a) | np.isnan(b))
        if not np.allclose(a[both], b[both], atol=atol, equal_nan=True):
            idx = int(np.argmax(~np.isclose(a, b, atol=atol, equal_nan=True)))
            raise SignalContractError(
                f"lookahead detected: signal at bar {idx} changes when bars >= {k} are removed "
                f"({a[idx]!r} vs {b[idx]!r})"
            )
        # null pattern must match too: a value that exists only with future data is lookahead
        if not np.array_equal(np.isnan(a), np.isnan(b)):
            raise SignalContractError(f"lookahead detected: null pattern differs when bars >= {k} are removed")


def synthetic_ohlcv(n: int = 2000, seed: int = 0, start: str = "2024-01-01") -> pl.DataFrame:
    """Random-walk OHLCV frame with the firm's canonical columns, for unit tests."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.001, n)
    close = 100 * np.exp(np.cumsum(r))
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.0007, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.0007, n)))
    vol = rng.lognormal(10, 0.3, n)
    ts = pl.datetime_range(
        pl.lit(start).str.to_datetime(time_zone="UTC"),
        pl.lit(start).str.to_datetime(time_zone="UTC") + pl.duration(minutes=n - 1),
        interval="1m",
        eager=True,
    )
    return pl.DataFrame(
        {
            "ts_close": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
        }
    )
