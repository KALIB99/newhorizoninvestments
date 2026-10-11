"""Cyclical inversion at support / resistance: the liquidity-sweep reversal.

The market's "formula" at the hourly scale on crypto perps, as this signal sees it:

    price is pulled to where the resting orders are (stops below support, above
    resistance) → the orders fire (forced, price-insensitive flow: stop-outs and
    liquidations) → the forced flow is finite and exhausts → price inverts back inside the
    range → the cycle restarts towards the other side.

The crowd trades the first arrow (buy the breakout, sell the breakdown). This signal trades
the third: it waits for a *large drop* through support (the sweep), demands proof that the
forced flow is spent (a close back above the level, the reclaim), and only then goes long
with the stop just beyond the sweep extreme — the one price that falsifies the thesis.
Mirror for resistance. Everything is backward-looking; values are in [-1, 1].

``sr_levels`` returns the full frame (levels, setups, stops) for an engine; ``sr_inversion``
is the registered pure signal.
"""

from __future__ import annotations

import polars as pl

from signals.base import Params, clip_unit, register


class SRInversionParams(Params):
    level_lookback: int = 96
    """Bars that define the range whose extremes are support / resistance (prior bars only)."""
    drop_lookback: int = 24
    """Bars over which the move *into* the level is measured (the 'large drop')."""
    min_drop_atr: float = 4.0
    """The move into the level must be at least this many ATR to count as capitulation.
    (On BTC/ETH/SOL 1h, 2023–26, sweeps sit 4–8 ATR below the prior 24h high: p10 ≈ 4,
    median ≈ 5.8, p90 ≈ 8 — measured on setup *counts* only, before any PnL was computed.)"""
    sweep_atr: float = 0.1
    """Minimum penetration beyond the level, in ATR, to count as a sweep (not a touch)."""
    reclaim_window: int = 2
    """The first close back inside the level must come within this many bars of the sweep."""
    stop_buffer_atr: float = 0.25
    """Stop sits this many ATR beyond the sweep extreme."""
    atr_period: int = 14
    magnitude_atr: float = 8.0
    """Drop size (in ATR) at which the signal saturates at ±1."""


def atr_wilder(df: pl.DataFrame, n: int) -> pl.Series:
    """Wilder ATR (EWM of true range with alpha = 1/n); null until ``n`` bars are available."""
    h, lo, c1 = df["high"], df["low"], df["close"].shift(1)
    tr = pl.DataFrame({"a": h - lo, "b": (h - c1).abs(), "c": (lo - c1).abs()}).max_horizontal()
    return tr.ewm_mean(alpha=1.0 / n, adjust=False, min_samples=n)


def sr_levels(df: pl.DataFrame, p: SRInversionParams) -> pl.DataFrame:
    """Columns: support, resistance, atr, long_setup, short_setup, long_stop, short_stop,
    long_mag, short_mag. All decided with data through the current bar."""
    w = p.reclaim_window
    low, high, close, atr = pl.col("low"), pl.col("high"), pl.col("close"), pl.col("atr")
    f = df.select("high", "low", "close").with_columns(atr=atr_wilder(df, p.atr_period))
    f = f.with_columns(
        support=low.rolling_min(p.level_lookback).shift(1),
        resistance=high.rolling_max(p.level_lookback).shift(1),
        # size of the move into the level, measured at the sweep bar (includes that bar)
        drop_atr=(high.rolling_max(p.drop_lookback) - low) / atr,
        rise_atr=(high - low.rolling_min(p.drop_lookback)) / atr,
    )
    sup, res = pl.col("support"), pl.col("resistance")
    f = f.with_columns(
        sweep_dn=(low < sup - p.sweep_atr * atr) & (pl.col("drop_atr") >= p.min_drop_atr),
        sweep_up=(high > res + p.sweep_atr * atr) & (pl.col("rise_atr") >= p.min_drop_atr),
    )
    long_setup, short_setup = pl.lit(False), pl.lit(False)
    long_mag, short_mag = pl.lit(0.0), pl.lit(0.0)
    for j in range(w + 1):
        s_j, r_j = sup.shift(j), res.shift(j)
        # the sweep happened j bars ago and *this* close is the first one back inside the level
        lo_j = pl.col("sweep_dn").shift(j).fill_null(False) & (close > s_j)
        sh_j = pl.col("sweep_up").shift(j).fill_null(False) & (close < r_j)
        for i in range(1, j + 1):
            lo_j = lo_j & (close.shift(i) <= s_j)
            sh_j = sh_j & (close.shift(i) >= r_j)
        lo_j, sh_j = lo_j.fill_null(False), sh_j.fill_null(False)
        long_setup = long_setup | lo_j
        short_setup = short_setup | sh_j
        # magnitude = the largest qualifying move into the level among the sweeps resolving here
        long_mag = pl.max_horizontal(long_mag, pl.when(lo_j).then(pl.col("drop_atr").shift(j)).otherwise(0.0))
        short_mag = pl.max_horizontal(short_mag, pl.when(sh_j).then(pl.col("rise_atr").shift(j)).otherwise(0.0))

    warm = sup.is_null() | atr.is_null() | pl.col("drop_atr").is_null() | sup.shift(w).is_null()
    return f.select(
        "support",
        "resistance",
        "atr",
        long_setup=long_setup & ~warm,
        short_setup=short_setup & ~warm,
        long_stop=low.rolling_min(w + 1) - p.stop_buffer_atr * atr,
        short_stop=high.rolling_max(w + 1) + p.stop_buffer_atr * atr,
        long_mag=long_mag.fill_null(0.0),
        short_mag=short_mag.fill_null(0.0),
        warm=warm,
    )


@register("sr_inversion")
def sr_inversion(df: pl.DataFrame, params: SRInversionParams) -> pl.Series:
    """+m at a confirmed long inversion (sweep of support + reclaim), −m at a short one,
    0 otherwise, null during warm-up. m = min(1, drop_in_ATR / magnitude_atr)."""
    lv = sr_levels(df, params)
    out = (
        lv.select(
            pl.when(pl.col("warm"))
            .then(None)
            .when(pl.col("long_setup"))
            .then(pl.col("long_mag") / params.magnitude_atr)
            .when(pl.col("short_setup"))
            .then(-pl.col("short_mag") / params.magnitude_atr)
            .otherwise(0.0)
            .alias("sr_inversion")
        )
        .to_series()
    )
    return clip_unit(out).fill_nan(None)
