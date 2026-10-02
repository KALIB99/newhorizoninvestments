"""Data quality gates: gaps, duplicate timestamps, outliers > 10σ, clock drift.
Every dataset ships with one of these."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import polars as pl
from pydantic import BaseModel, Field

REPORTS_DIR = Path("data/reports")


class QualityReport(BaseModel):
    exchange: str
    symbol: str
    timeframe: str
    n_rows: int
    start: datetime | None
    end: datetime | None
    expected_rows: int
    n_gaps: int = Field(description="missing bars (not rows flagged is_gap)")
    gap_fraction: float
    largest_gap_bars: int
    n_duplicate_ts: int
    n_outliers_10sigma: int
    n_nonpositive_prices: int
    n_ohlc_violations: int = Field(description="high < max(open,close) or low > min(open,close)")
    max_clock_drift_seconds: float = Field(description="|ts_close − expected grid| max")
    passed: bool
    issues: list[str]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def save(self, directory: Path | str = REPORTS_DIR) -> Path:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{self.exchange}_{self.symbol.replace('/', '-').replace(':', '_')}_{self.timeframe}_quality.json"
        p.write_text(self.model_dump_json(indent=2))
        return p


def _tf_seconds(tf: str) -> int:
    n, unit = int(tf[:-1]), tf[-1]
    return n * {"m": 60, "h": 3600, "d": 86400}[unit]


def quality_report(
    df: pl.DataFrame, exchange: str, symbol: str, tf: str, max_gap_fraction: float = 0.001
) -> QualityReport:
    issues: list[str] = []
    step = _tf_seconds(tf)
    if df.height == 0:
        return QualityReport(
            exchange=exchange,
            symbol=symbol,
            timeframe=tf,
            n_rows=0,
            start=None,
            end=None,
            expected_rows=0,
            n_gaps=0,
            gap_fraction=1.0,
            largest_gap_bars=0,
            n_duplicate_ts=0,
            n_outliers_10sigma=0,
            n_nonpositive_prices=0,
            n_ohlc_violations=0,
            max_clock_drift_seconds=0.0,
            passed=False,
            issues=["empty dataset"],
        )
    ts = df["ts_close"].sort()
    start, end = ts[0], ts[-1]
    expected = int((end - start).total_seconds() // step) + 1

    n_dup = df.height - df["ts_close"].n_unique()
    if n_dup:
        issues.append(f"{n_dup} duplicate timestamps")

    uniq = ts.unique().sort()
    diffs = uniq.diff().drop_nulls().dt.total_seconds().to_numpy()
    missing_per_gap = np.maximum(np.round(diffs / step).astype(int) - 1, 0)
    n_gaps = int(missing_per_gap.sum())
    largest = int(missing_per_gap.max()) if len(missing_per_gap) else 0
    gap_fraction = n_gaps / expected if expected else 0.0
    if gap_fraction > max_gap_fraction:
        issues.append(f"gap fraction {gap_fraction:.4%} > {max_gap_fraction:.2%} (largest gap {largest} bars)")

    # clock drift: distance of each ts_close from the step grid anchored at start
    offs = (uniq - start).dt.total_seconds().to_numpy() % step
    drift = float(np.minimum(offs, step - offs).max()) if len(offs) else 0.0
    if drift > 1.0:
        issues.append(f"clock drift {drift:.1f}s off the {tf} grid")

    px = df.select(["open", "high", "low", "close"])
    n_nonpos = int((px.to_numpy() <= 0).sum())
    if n_nonpos:
        issues.append(f"{n_nonpos} non-positive prices")
    viol = df.filter(
        (pl.col("high") < pl.max_horizontal("open", "close")) | (pl.col("low") > pl.min_horizontal("open", "close"))
    ).height
    if viol:
        issues.append(f"{viol} OHLC consistency violations")

    r = np.log(df["close"].to_numpy()[1:] / df["close"].to_numpy()[:-1]) if df.height > 1 else np.array([])
    r = r[np.isfinite(r)]
    if len(r) > 10:
        mad = np.median(np.abs(r - np.median(r))) * 1.4826 or r.std() or 1e-12
        n_out = int((np.abs(r - np.median(r)) > 10 * mad).sum())
    else:
        n_out = 0
    if "is_gap" in df.columns and not df["is_gap"].any() and n_gaps:
        issues.append("gaps present but no rows flagged is_gap — ingestion must mark gaps")

    passed = not issues  # everything above is a hard failure
    if n_out:  # outliers are a warning: real crashes exist, but they must be cross-checked
        issues.append(f"WARN: {n_out} returns beyond 10σ (robust) — verify against a second exchange before use")

    return QualityReport(
        exchange=exchange,
        symbol=symbol,
        timeframe=tf,
        n_rows=df.height,
        start=start,
        end=end,
        expected_rows=expected,
        n_gaps=n_gaps,
        gap_fraction=gap_fraction,
        largest_gap_bars=largest,
        n_duplicate_ts=n_dup,
        n_outliers_10sigma=n_out,
        n_nonpositive_prices=n_nonpos,
        n_ohlc_violations=viol,
        max_clock_drift_seconds=drift,
        passed=passed,
        issues=issues,
    )


def load_report(path: Path | str) -> QualityReport:
    return QualityReport.model_validate(json.loads(Path(path).read_text()))
