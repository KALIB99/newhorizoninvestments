"""Data access. Everything goes through ``data.load``.

Layout (written by the data-engineer's ingestion, T-001):
    data/store/<exchange>/<market>/<symbol>/<tf>/date=YYYY-MM-DD/part.parquet
    data/store/features.duckdb           (feature store views over the parquet)
    data/reports/<exchange>_<symbol>_<tf>_quality.json

Columns (canonical): ts_open, ts_close (UTC), open, high, low, close, volume, is_gap,
plus optional funding_rate, open_interest, mark, index, and feature columns.
"""

from data.quality import QualityReport, quality_report
from data.store import DataNotAvailable, load, store_path

__all__ = ["DataNotAvailable", "QualityReport", "load", "quality_report", "store_path"]
