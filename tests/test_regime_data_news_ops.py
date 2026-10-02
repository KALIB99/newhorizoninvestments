"""Regime rules + features, data quality, news schema, slippage fit, ops helpers."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import polars as pl
import pytest

from data.quality import quality_report
from data.store import DataNotAvailable, load, store_path
from execution.slippage import SlippageModel, fill_quality
from news.schema import Category, NewsItem, ScheduledEvent, Tier, sentiment_impulse
from ops import tasks as tasksmd
from regime import classify
from regime.features import adx, garman_klass_vol, hurst_exponent, regime_features
from regime.rules import REGIMES, classify_rules
from signals.testing import synthetic_ohlcv

# ---- regime -------------------------------------------------------------------------------


def _ohlc(n=3000, phi=0.0, seed=0):
    """phi > 0 → AR(1)-persistent returns (trending); phi < 0 → mean-reverting."""
    df = synthetic_ohlcv(n, seed).to_pandas().set_index("ts_close")
    if phi:
        rng = np.random.default_rng(seed)
        eps = rng.normal(0, 0.001, n)
        r = np.zeros(n)
        for i in range(1, n):
            r[i] = phi * r[i - 1] + eps[i]
        df["close"] = 100 * np.exp(np.cumsum(r))
        df["open"] = df["close"].shift(1).bfill()
        df["high"] = df[["open", "close"]].max(axis=1) * 1.0005
        df["low"] = df[["open", "close"]].min(axis=1) * 0.9995
    return df


def test_rules_mapping():
    f = pd.DataFrame(
        {
            "hurst": [0.6, 0.6, 0.4, 0.5, np.nan],
            "adx": [30, 20, 10, 10, 10],
            "rv_pct": [0.5, 0.5, 0.5, 0.95, 0.5],
        }
    )
    out = classify_rules(f)
    assert list(out[:4]) == ["Trend", "Range", "Range", "Chaos"]
    assert out.iloc[4] is None


def test_features_are_backward_looking_and_hurst_in_range():
    df = _ohlc()
    f = regime_features(df)
    assert set(f.columns) >= {"log_rv", "vol_of_vol", "hurst", "adx", "rv_pct"}
    h = f["hurst"].dropna()
    assert len(h) > 0 and h.between(0.0, 1.2).all()
    # chopping off the tail must not change earlier values
    f2 = regime_features(df.iloc[:-500])
    common = f.index[:-500]
    pd.testing.assert_series_equal(f.loc[common, "adx"], f2["adx"], check_names=False)
    pd.testing.assert_series_equal(f.loc[common, "hurst"], f2["hurst"], check_names=False)


def test_hurst_orders_mean_reverting_random_trending():
    mr = hurst_exponent(_ohlc(4000, -0.5)["close"]).dropna().mean()
    rnd = hurst_exponent(_ohlc(4000, 0.0)["close"]).dropna().mean()
    trend = hurst_exponent(_ohlc(4000, 0.5)["close"]).dropna().mean()
    assert mr < rnd < trend


def test_classify_rules_end_to_end_yields_known_labels():
    labels = classify(_ohlc(5000), method="rules").dropna()
    assert set(labels.unique()) <= set(REGIMES)
    assert len(labels) > 1000


def test_adx_and_gk_positive():
    df = _ohlc()
    assert (adx(df).dropna() >= 0).all()
    assert (garman_klass_vol(df).dropna() > 0).all()


# ---- data -----------------------------------------------------------------------------------


def test_quality_report_detects_gaps_dupes_outliers():
    df = synthetic_ohlcv(1000)
    clean = quality_report(df, "binance", "BTC/USDT:USDT", "1m")
    assert clean.passed and clean.n_gaps == 0 and clean.n_duplicate_ts == 0

    gappy = pl.concat([df.head(400), df.tail(500)])  # 100 bars missing
    rep = quality_report(gappy, "binance", "BTC/USDT:USDT", "1m")
    assert rep.n_gaps == 100 and rep.largest_gap_bars == 100 and not rep.passed

    duped = pl.concat([df, df.head(3)])
    assert quality_report(duped, "binance", "BTC/USDT:USDT", "1m").n_duplicate_ts == 3

    spiked = df.with_columns(
        pl.when(pl.arange(0, df.height) == 500).then(pl.col("close") * 1.5).otherwise(pl.col("close")).alias("close")
    )
    spiked = spiked.with_columns(pl.max_horizontal("high", "close").alias("high"))
    rep = quality_report(spiked, "binance", "BTC/USDT:USDT", "1m")
    assert rep.n_outliers_10sigma >= 1 and rep.passed  # outliers warn, not fail


def test_quality_report_marks_unflagged_gaps_as_failure():
    df = synthetic_ohlcv(500).with_columns(pl.lit(False).alias("is_gap"))
    gappy = pl.concat([df.head(200), df.tail(200)])
    rep = quality_report(gappy, "bybit", "ETH/USDT", "1m")
    assert any("is_gap" in i for i in rep.issues)


def test_store_path_and_load_roundtrip(tmp_path):
    df = synthetic_ohlcv(120).with_columns(
        (pl.col("ts_close") - pl.duration(minutes=1)).alias("ts_open"), pl.lit(False).alias("is_gap")
    )
    p = store_path("BTC/USDT:USDT", "1m", "binance", tmp_path)
    assert p == tmp_path / "binance" / "perp" / "BTC-USDT_USDT" / "1m"
    assert store_path("BTC/USDT", "1m", "binance", tmp_path).parts[-3] == "spot"
    part = p / "date=2024-01-01"
    part.mkdir(parents=True)
    df.write_parquet(part / "part.parquet")
    out = load("BTC/USDT:USDT", "1m", "2024-01-01", "2024-01-01T00:59:00+00:00", root=tmp_path)
    assert out.height == 60 and out["ts_close"].is_sorted()
    with pytest.raises(DataNotAvailable):
        load("SOL/USDT:USDT", "1m", "2024-01-01", "2024-01-02", root=tmp_path)
    with pytest.raises(DataNotAvailable, match="columns"):
        load("BTC/USDT:USDT", "1m", "2024-01-01", "2024-01-02", features=["funding_z"], root=tmp_path)


# ---- news -------------------------------------------------------------------------------------


def test_news_item_validation_and_impulse():
    t = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    item = NewsItem(
        ts=t,
        ingested_at=t + timedelta(minutes=2),
        source="x",
        headline="h",
        entities=["BTC"],
        category=Category.HACK,
        direction=-1,
        magnitude=0.8,
        horizon_minutes=120,
        confidence=0.5,
    )
    assert item.latency == timedelta(minutes=2)
    assert item.impulse == pytest.approx(-0.4)
    with pytest.raises(Exception):
        NewsItem(
            ts=datetime(2026, 1, 1),
            ingested_at=t,
            source="x",
            headline="h",
            category="hack",
            direction=0,
            magnitude=0,
            horizon_minutes=1,
            confidence=0,
        )


def test_sentiment_impulse_decays_with_90min_half_life_from_ingestion():
    t = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    item = NewsItem(
        ts=t,
        ingested_at=t + timedelta(minutes=10),
        source="x",
        headline="h",
        entities=["BTC"],
        category=Category.MACRO,
        direction=1,
        magnitude=1,
        horizon_minutes=60,
        confidence=1,
    )
    idx = pd.date_range(t, periods=200, freq="min", tz="UTC")
    s = sentiment_impulse([item], idx, 90.0)
    assert s.iloc[9] == 0.0  # not yet ingested
    assert s.iloc[10] == pytest.approx(1.0)
    assert s.iloc[100] == pytest.approx(0.5, rel=1e-3)
    assert sentiment_impulse([item], idx, 90.0, entity="ETH").abs().sum() == 0


def test_scheduled_event_window_matches_risk_invariants():
    ev = ScheduledEvent(ts=datetime(2026, 3, 18, 18, 0, tzinfo=UTC), name="FOMC", tier=Tier.T1)
    assert ev.blocks(ev.ts - timedelta(minutes=15)) and ev.blocks(ev.ts + timedelta(minutes=30))
    assert not ev.blocks(ev.ts - timedelta(minutes=16))
    assert not ScheduledEvent(ts=ev.ts, name="unlock", tier=Tier.T2).blocks(ev.ts)


# ---- slippage -----------------------------------------------------------------------------------


def test_slippage_fit_recovers_coefficients_and_never_negative(tmp_path):
    rng = np.random.default_rng(0)
    n = 2000
    size_adv = rng.uniform(0, 0.05, n)
    spread = rng.uniform(0.5, 3, n)
    y = 0.8 + 20 * np.sqrt(size_adv) + 0.4 * spread + rng.normal(0, 0.2, n)
    fills = pd.DataFrame({"size_adv": size_adv, "spread_bps": spread, "realised_slippage_bps": y})
    m = SlippageModel.fit(fills)
    assert (
        m.a == pytest.approx(0.8, abs=0.1)
        and m.b == pytest.approx(20, rel=0.05)
        and m.c == pytest.approx(0.4, abs=0.05)
    )
    assert m.r2 > 0.9
    p = m.save(tmp_path / "slippage_fit.json")
    assert SlippageModel.load(p).b == pytest.approx(m.b)
    from eval.costs import CostModel

    c = CostModel.from_fitted(p)
    assert c.slip_b == pytest.approx(m.b) and c.source.startswith("fitted")
    fq = fill_quality(fills, m)
    assert fq["within_30pct"]
    with pytest.raises(ValueError):
        SlippageModel.fit(fills.head(10))


# ---- ops --------------------------------------------------------------------------------------------


def test_tasks_md_helpers(tmp_path):
    p = tmp_path / "tasks.md"
    p.write_text(
        "# t\n\n## Queue\n- [ ] T-007 | x\n\n## In progress\n\n## Awaiting judge\n\n## Done / Rejected (with reason)\n"
    )
    assert tasksmd.next_task_id(p) == "T-008"
    tasksmd.append_to_section(tasksmd.hypothesis_entry("T-008", "a", "b", "c"), "## Queue", p)
    text = p.read_text()
    assert text.index("T-008") < text.index("## In progress")
    assert "H: a. Test: b. Decision rule: c. Owner: quant-researcher." in text
    assert tasksmd.next_task_id(p) == "T-009"


def test_nightly_runs_on_empty_logs(tmp_cwd, monkeypatch):
    (tmp_cwd / "tasks.md").write_text(
        "## Queue\n\n## In progress\n\n## Awaiting judge\n\n## Done / Rejected (with reason)\n"
    )
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    from ops import nightly

    day = datetime(2026, 1, 1, tzinfo=UTC)
    rep = nightly.postmortem(day)
    assert rep.exists() and "No fills" in rep.read_text()
    summ = nightly.summary(day)
    assert "CIO summary" in summ.read_text()
    assert nightly.heartbeat() == 0
    assert nightly.main(["weekly"]) == 0
