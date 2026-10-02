"""Nightly / weekly entrypoints (spec §6). ``python -m ops.nightly <postmortem|summary|weekly|heartbeat>``.

Bootstrap behaviour: runs end-to-end on an empty log directory, writes a report saying so,
and does *not* invent hypotheses from no data. T-008 wires the real attribution once the
PaperBroker is producing fills. The postmortem-analyst subagent reads the report this job
writes and adds the human-judgement hypotheses; this job adds only mechanical ones (drift).
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
from loguru import logger

from eval import metrics
from ops import tasks as tasksmd
from ops.alerts import alert, setup_logging
from ops.settings import get_settings

FILL_COLS = ["ts", "strategy", "symbol", "side", "qty", "price", "fee_usd", "realised_slippage_bps", "mark_at_submit"]


def _fills_for(day: datetime, logs_dir: Path) -> pd.DataFrame:
    p = logs_dir / f"fills_{day:%Y-%m-%d}.parquet"
    if not p.exists():
        return pd.DataFrame(columns=FILL_COLS)
    return pd.read_parquet(p)


def _pnl_for(day: datetime, logs_dir: Path) -> pd.DataFrame:
    """Per-bar strategy PnL rows: ts, strategy, symbol, regime, pnl, cost."""
    p = logs_dir / f"pnl_{day:%Y-%m-%d}.parquet"
    if not p.exists():
        return pd.DataFrame(columns=["ts", "strategy", "symbol", "regime", "pnl", "cost"])
    return pd.read_parquet(p)


def postmortem(day: datetime | None = None) -> Path:
    s = get_settings()
    day = day or (datetime.now(UTC) - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    fills, pnl = _fills_for(day, s.logs_dir), _pnl_for(day, s.logs_dir)
    s.reports_dir.mkdir(parents=True, exist_ok=True)
    out = s.reports_dir / f"daily_{day:%Y-%m-%d}.md"

    lines = [f"# Daily postmortem — {day:%Y-%m-%d} (UTC)", ""]
    if fills.empty and pnl.empty:
        lines += [
            "No fills and no PnL rows logged. Either the paper book is idle (fine during bootstrap) or logging is broken (not fine).",
            "",
        ]
        out.write_text("\n".join(lines))
        logger.info("postmortem: no data for {}", day.date())
        return out

    if not pnl.empty:
        lines += ["## Attribution", "", "| by | key | PnL | cost |", "|---|---|---|---|"]
        for dim in ("strategy", "regime", "symbol"):
            if dim in pnl:
                g = pnl.groupby(dim)[["pnl", "cost"]].sum()
                for k, row in g.iterrows():
                    lines.append(f"| {dim} | {k} | {row['pnl']:+.2f} | {row['cost']:.2f} |")
        if "ts" in pnl:
            pnl["hour"] = pd.to_datetime(pnl["ts"], utc=True).dt.hour
            g = pnl.groupby("hour")["pnl"].sum()
            lines += ["", "## PnL by hour (UTC)", "", "| hour | PnL |", "|---|---|"] + [
                f"| {h:02d} | {v:+.2f} |" for h, v in g.items()
            ]
        total_cost, total_pnl = pnl["cost"].sum(), pnl["pnl"].sum()
        lines += [
            "",
            f"**Alpha vs cost:** gross {total_pnl + total_cost:+.2f}, costs {total_cost:.2f}, net {total_pnl:+.2f}",
            "",
        ]

    if not fills.empty:
        lines += ["## Fill quality", ""]
        lines.append(
            f"- fills: {len(fills)}; realised slippage mean {fills['realised_slippage_bps'].mean():.2f} bps, p95 {fills['realised_slippage_bps'].quantile(0.95):.2f} bps"
        )
        lines.append(
            "- compare against execution/reports/slippage_fit.json (T-007) — paper→live needs |realised/modelled − 1| ≤ 0.30"
        )
        lines.append("")

    # mechanical drift check: rolling 30d sharpe vs OOS backtest (needs history + tearsheets)
    drift = _drift_flags(day, s.logs_dir)
    if drift:
        lines += ["## Drift flags", ""] + [f"- {d}" for d in drift] + [""]
        for d in drift:
            tid = tasksmd.next_task_id()
            tasksmd.append_to_section(
                tasksmd.hypothesis_entry(
                    tid,
                    claim=f"{d.split(':')[0]} has drifted from its OOS distribution",
                    test="re-run walk-forward on data through yesterday with the promoted config hash; compare rolling-30d Sharpe to the OOS fold distribution",
                    decision_rule="if rolling Sharpe < (OOS mean − 1.5σ) for 2 consecutive weeks → demote to paper",
                    owner="quant-researcher",
                )
            )
            logger.warning("drift task {} queued: {}", tid, d)

    lines += [
        "## Hypotheses",
        "",
        "_postmortem-analyst subagent: read this report and add 1–3 falsifiable hypotheses to tasks.md (Queue)._",
        "",
    ]
    out.write_text("\n".join(lines))
    logger.info("postmortem written to {}", out)
    return out


def _drift_flags(day: datetime, logs_dir: Path, window_days: int = 30) -> list[str]:
    frames = []
    for i in range(window_days):
        d = day - timedelta(days=i)
        p = logs_dir / f"pnl_{d:%Y-%m-%d}.parquet"
        if p.exists():
            frames.append(pd.read_parquet(p))
    if not frames:
        return []
    pnl = pd.concat(frames)
    flags = []
    from eval.report import Tearsheet

    for strat, g in pnl.groupby("strategy"):
        daily = g.groupby(pd.to_datetime(g["ts"], utc=True).dt.date)["pnl"].sum()
        if len(daily) < 20:
            continue
        sr = metrics.sharpe(daily.to_numpy(), 365)
        paths = Tearsheet.find(str(strat))
        if not paths:
            continue
        ts = Tearsheet.load(paths[0])
        if len(ts.sharpe_by_fold) >= 3:
            mu, sd = float(pd.Series(ts.sharpe_by_fold).mean()), float(pd.Series(ts.sharpe_by_fold).std(ddof=1))
            if sd > 0 and sr < mu - 1.5 * sd:
                flags.append(f"{strat}: rolling-{window_days}d Sharpe {sr:.2f} < OOS mean {mu:.2f} − 1.5σ ({sd:.2f})")
    return flags


def summary(day: datetime | None = None) -> Path:
    """Planner-facing roll-up for the CIO: yesterday's report + tasks.md section counts."""
    s = get_settings()
    day = day or (datetime.now(UTC) - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    daily = s.reports_dir / f"daily_{day:%Y-%m-%d}.md"
    text = tasksmd.TASKS_PATH.read_text() if tasksmd.TASKS_PATH.exists() else ""
    counts = {
        sec: text.split(sec, 1)[1].split("\n## ", 1)[0].count("\n- [") if sec in text else 0 for sec in tasksmd.SECTIONS
    }
    body = [f"# CIO summary — {day:%Y-%m-%d}", "", "## tasks.md", ""] + [f"- {k[3:]}: {v}" for k, v in counts.items()]
    body += ["", "## Postmortem", "", daily.read_text() if daily.exists() else "_no postmortem report for this day_"]
    out = s.reports_dir / f"summary_{day:%Y-%m-%d}.md"
    out.write_text("\n".join(body))
    alert(
        f"quantfirm daily summary {day:%Y-%m-%d}: " + ", ".join(f"{k[3:]}={v}" for k, v in counts.items()), level="INFO"
    )
    return out


def weekly() -> Path:
    s = get_settings()
    now = datetime.now(UTC)
    out = s.reports_dir / f"weekly_{now:%G-W%V}.md"
    out.write_text(
        f"# Weekly — {now:%G-W%V}\n\n"
        "- [ ] risk-manager: recompute `portfolio.combine_weights` on the last 90d of strategy returns; note any pair with |ρ| > 0.7.\n"
        "- [ ] risk-manager: demote any strategy with an open drift task in tasks.md.\n"
        "- [ ] postmortem-analyst: full tearsheet + parameter stability report.\n"
        "- [ ] judge: rejection rate this week (target > 80%) → research/reports/judge_log.md\n"
    )
    return out


def heartbeat() -> int:
    """Checks data freshness for the paper book. Exit 1 (and alert) if stale."""
    s = get_settings()
    marker = s.logs_dir / "last_bar.txt"
    if not marker.exists():
        logger.info("heartbeat: no last_bar marker (paper book not running)")
        return 0
    last = datetime.fromisoformat(marker.read_text().strip())
    age = (datetime.now(UTC) - last).total_seconds()
    from risk.limits import LIMITS

    if age > LIMITS.data_staleness_seconds:
        alert(
            f"DATA STALE: last bar {age:.0f}s ago (> {LIMITS.data_staleness_seconds}s). Kill switch should be tripped.",
            level="ERROR",
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m ops.nightly")
    ap.add_argument("job", choices=["postmortem", "summary", "weekly", "heartbeat"])
    ap.add_argument("--day", help="UTC date YYYY-MM-DD (default: yesterday)")
    a = ap.parse_args(argv)
    setup_logging()
    day = datetime.fromisoformat(a.day).replace(tzinfo=UTC) if a.day else None
    if a.job == "postmortem":
        print(postmortem(day))
    elif a.job == "summary":
        print(summary(day))
    elif a.job == "weekly":
        print(weekly())
    else:
        return heartbeat()
    return 0


if __name__ == "__main__":
    sys.exit(main())
