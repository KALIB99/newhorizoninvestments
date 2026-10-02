from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import duckdb
import polars as pl

STORE_ROOT = Path("data/store")
CANONICAL = ["ts_open", "ts_close", "open", "high", "low", "close", "volume", "is_gap"]
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class DataNotAvailable(FileNotFoundError):
    pass


def _market(symbol: str) -> str:
    return "perp" if ":" in symbol else "spot"


def _slug(symbol: str) -> str:
    return symbol.replace("/", "-").replace(":", "_")


def store_path(symbol: str, tf: str, exchange: str = "binance", root: Path | str = STORE_ROOT) -> Path:
    return Path(root) / exchange / _market(symbol) / _slug(symbol) / tf


def load(
    symbol: str,
    tf: str,
    start: str | datetime,
    end: str | datetime,
    features: Sequence[str] | None = None,
    exchange: str = "binance",
    root: Path | str = STORE_ROOT,
) -> pl.DataFrame:
    """Load bars (and optional feature columns) for ``symbol`` in [start, end].

    Symbols use ccxt notation: ``BTC/USDT`` spot, ``BTC/USDT:USDT`` perp. Gaps are *marked*
    (``is_gap=True``) never silently forward-filled. Raises ``DataNotAvailable`` if the
    partition does not exist — run the ingestion (T-001) first.
    """
    path = store_path(symbol, tf, exchange, root)
    if not path.exists() or not any(path.rglob("*.parquet")):
        raise DataNotAvailable(f"no data at {path}. Run ingestion for {exchange} {symbol} {tf} (tasks.md T-001).")
    cols = CANONICAL + list(features or [])
    bad = [c for c in cols if not _IDENT.fullmatch(c)]
    if bad:
        raise ValueError(f"invalid column names {bad}; identifiers must match {_IDENT.pattern}")
    con = duckdb.connect()
    try:
        # The only interpolated pieces are a path we built ourselves and identifiers checked
        # against _IDENT above; time bounds are bound parameters.
        glob = str(path / "date=*" / "*.parquet")
        available = {
            r[0]
            for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?, hive_partitioning=true)", [glob]).fetchall()
        }
        missing = [c for c in cols if c not in available]
        if missing:
            raise DataNotAvailable(f"columns {missing} not in {path}; available: {sorted(available)}")
        q = f"""
            SELECT {", ".join(cols)}
            FROM read_parquet(?, hive_partitioning=true)
            WHERE ts_close >= ?::TIMESTAMPTZ AND ts_close <= ?::TIMESTAMPTZ
            ORDER BY ts_close
        """  # noqa: S608 - identifiers validated, values parameterised
        tbl = con.execute(q, [glob, _ts(start), _ts(end)]).pl()
    finally:
        con.close()
    return tbl


def _ts(x: str | datetime) -> str:
    if isinstance(x, datetime):
        if x.tzinfo is None:
            raise ValueError("datetimes must be tz-aware UTC")
        return x.isoformat()
    return x if ("T" in x or "+" in x or x.endswith("Z")) else f"{x}T00:00:00+00:00"
