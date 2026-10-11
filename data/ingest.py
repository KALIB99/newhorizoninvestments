"""Ingestion from Binance's public bulk archive (data.binance.vision).

The REST APIs are rate-limited and geo-blocked from many networks; the archive is neither,
and it is the same data. Monthly zips are cached under data/raw/ and written to the store as

    data/store/binance/perp/<symbol>/<tf>/date=YYYY-MM/part.parquet

Columns: canonical OHLCV + is_gap, plus quote_volume, n_trades, taker_buy_volume,
funding_paid (the settled 8h rate on the bar whose close is the settlement time, else 0)
and funding_rate_last (the most recent settled rate known at ts_close — safe for signals).

    python -m data.ingest --symbols BTC ETH SOL --tfs 5m 1h --start 2023-01 --end 2026-09
"""

from __future__ import annotations

import argparse
import io
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
from loguru import logger

from data.quality import _tf_seconds, quality_report
from data.store import STORE_ROOT, store_path

BASE = "https://data.binance.vision/data/futures/um/monthly"
SPOT_BASE = "https://data.binance.vision/data/spot/monthly"
RAW_ROOT = Path("data/raw/binance")
KLINE_COLS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "n_trades",
    "taker_buy_volume",
    "taker_buy_quote_volume",
    "ignore",
]


def ccxt_symbol(base: str, market: str = "perp") -> str:
    return f"{base}/USDT:USDT" if market == "perp" else f"{base}/USDT"


def months(start: str, end: str) -> list[str]:
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def _use_system_trust_store() -> None:
    """Verify TLS against the OS keychain (corporate proxies re-sign certificates)."""
    try:
        import truststore

        truststore.inject_into_ssl()
    except ImportError:
        pass


def _fetch(url: str, dest: Path) -> Path | None:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310 - fixed https host
            dest.write_bytes(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.warning("not published: {}", url)
            return None
        raise
    return dest


def _read_zip_csv(path: Path, columns: list[str]) -> pl.DataFrame:
    with zipfile.ZipFile(path) as z:
        raw = z.read(z.namelist()[0])
    first = raw.split(b"\n", 1)[0]
    has_header = not first[:1].isdigit()
    return pl.read_csv(
        io.BytesIO(raw),
        has_header=has_header,
        new_columns=columns,
        infer_schema_length=0,
    )


def _klines(pair: str, tf: str, month: str, market: str = "perp") -> pl.DataFrame | None:
    base = BASE if market == "perp" else SPOT_BASE
    url = f"{base}/klines/{pair}/{tf}/{pair}-{tf}-{month}.zip"
    p = _fetch(url, RAW_ROOT / market / "klines" / pair / tf / f"{month}.zip")
    if p is None:
        return None
    df = _read_zip_csv(p, KLINE_COLS)
    step_ms = _tf_seconds(tf) * 1000
    ot = pl.col("open_time").cast(pl.Int64)
    # some archive months are in microseconds; normalise to ms
    ot = pl.when(ot > 10**14).then(ot // 1000).otherwise(ot)
    return df.select(
        pl.from_epoch(ot, time_unit="ms").dt.replace_time_zone("UTC").alias("ts_open"),
        pl.from_epoch(ot + step_ms, time_unit="ms").dt.replace_time_zone("UTC").alias("ts_close"),
        *(pl.col(c).cast(pl.Float64) for c in ("open", "high", "low", "close", "volume", "quote_volume")),
        pl.col("n_trades").cast(pl.Int64),
        pl.col("taker_buy_volume").cast(pl.Float64),
    )


def _funding(pair: str, month: str) -> pl.DataFrame | None:
    url = f"{BASE}/fundingRate/{pair}/{pair}-fundingRate-{month}.zip"
    p = _fetch(url, RAW_ROOT / "funding" / pair / f"{month}.zip")
    if p is None:
        return None
    df = _read_zip_csv(p, ["calc_time", "funding_interval_hours", "last_funding_rate"])
    return df.select(
        pl.from_epoch(pl.col("calc_time").cast(pl.Int64), time_unit="ms")
        .dt.replace_time_zone("UTC")
        .dt.round("1m")
        .alias("funding_ts"),
        pl.col("last_funding_rate").cast(pl.Float64).alias("rate"),
    )


def build(
    base: str, tf: str, start: str, end: str, root: Path | str = STORE_ROOT, market: str = "perp"
) -> pl.DataFrame:
    """Download, align, mark gaps, join funding (perps), write partitions and a quality report."""
    pair = f"{base}USDT"
    ms = months(start, end)
    with ThreadPoolExecutor(max_workers=8) as ex:
        kl = [k for k in ex.map(lambda m: _klines(pair, tf, m, market), ms) if k is not None]
        fu = [] if market == "spot" else [f for f in ex.map(lambda m: _funding(pair, m), ms) if f is not None]
    if not kl:
        raise RuntimeError(f"no klines for {pair} {tf} {start}..{end}")
    bars = pl.concat(kl).unique("ts_close", keep="first").sort("ts_close")

    symbol = ccxt_symbol(base, market)
    rep = quality_report(bars, "binance", symbol, tf)
    rep.save()
    logger.info("{} {} quality passed={} issues={}", symbol, tf, rep.passed, rep.issues)

    step = f"{_tf_seconds(tf)}s"
    grid = pl.DataFrame(
        {"ts_close": pl.datetime_range(bars["ts_close"][0], bars["ts_close"][-1], interval=step, eager=True)}
    )
    df = grid.join(bars, on="ts_close", how="left").with_columns(
        pl.col("open").is_null().alias("is_gap"),
        (pl.col("ts_close") - pl.duration(seconds=_tf_seconds(tf))).alias("ts_open"),
    )

    funding = pl.concat(fu).unique("funding_ts").sort("funding_ts") if fu else None
    if funding is not None:
        df = df.join(funding.rename({"funding_ts": "ts_close", "rate": "funding_paid"}), on="ts_close", how="left")
        df = df.join_asof(
            funding.rename({"rate": "funding_rate_last"}),
            left_on="ts_close",
            right_on="funding_ts",
            strategy="backward",
        ).drop("funding_ts")
        df = df.with_columns(pl.col("funding_paid").fill_null(0.0))
    else:
        df = df.with_columns(pl.lit(0.0).alias("funding_paid"), pl.lit(None, pl.Float64).alias("funding_rate_last"))

    out = store_path(symbol, tf, "binance", root)
    df = df.with_columns(pl.col("ts_close").dt.strftime("%Y-%m").alias("_m"))
    for (m,), part in df.group_by(["_m"]):
        d = out / f"date={m}"
        d.mkdir(parents=True, exist_ok=True)
        part.drop("_m").write_parquet(d / "part.parquet")
    logger.info("{} {}: {} bars ({} gaps) → {}", symbol, tf, df.height, int(df["is_gap"].sum()), out)
    return df.drop("_m")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m data.ingest")
    ap.add_argument("--symbols", nargs="+", default=["BTC", "ETH", "SOL"])
    ap.add_argument("--tfs", nargs="+", default=["5m", "1h"])
    ap.add_argument("--start", default="2023-01")
    now = datetime.now(UTC)
    last = f"{now.year:04d}-{now.month - 1:02d}" if now.month > 1 else f"{now.year - 1:04d}-12"
    ap.add_argument("--end", default=last, help="last complete month (archive publishes monthly)")
    ap.add_argument("--markets", nargs="+", default=["perp"], choices=["perp", "spot"])
    args = ap.parse_args(argv)
    _use_system_trust_store()
    for mkt in args.markets:
        for s in args.symbols:
            for tf in args.tfs:
                build(s, tf, args.start, args.end, market=mkt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
