"""The firm's clock (spec §6). Two backends: crontab (default, zero deps) and Prefect
(``pip install -e .[ops]``). ``python -m ops.schedule crontab`` prints the crontab block;
``python -m ops.schedule prefect`` serves the Prefect deployments.

All times UTC. Everything stays in PaperBroker until capital_allocation.yaml is signed.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "bin" / "python"

JOBS = [
    # minute hour dom mon dow   command                                   purpose
    ("15", "0", "*", "*", "*", "-m ops.nightly postmortem", "postmortem-analyst → attribution + hypotheses → tasks.md"),
    ("45", "0", "*", "*", "*", "-m ops.nightly summary", "Planner summary for the CIO (ops/reports/daily_*.md)"),
    ("0", "1", "*", "*", "1", "-m ops.nightly weekly", "risk-manager reweight + drift/demotion review"),
    ("*/5", "*", "*", "*", "*", "-m ops.nightly heartbeat", "data staleness + kill-switch state check"),
]


def crontab_block() -> str:
    lines = ["# --- quantfirm (UTC) ---", "CRON_TZ=UTC"]
    for m, h, dom, mon, dow, cmd, why in JOBS:
        lines.append(f"# {why}")
        lines.append(f"{m} {h} {dom} {mon} {dow} cd {ROOT} && {PY} {cmd} >> ops/logs/cron.log 2>&1")
    lines.append("# --- end quantfirm ---")
    return "\n".join(lines) + "\n"


def serve_prefect() -> None:  # pragma: no cover - requires the ops extra
    from prefect import flow, serve

    from ops import nightly

    @flow(name="quantfirm-postmortem")
    def postmortem_flow() -> None:
        nightly.postmortem()

    @flow(name="quantfirm-summary")
    def summary_flow() -> None:
        nightly.summary()

    @flow(name="quantfirm-weekly")
    def weekly_flow() -> None:
        nightly.weekly()

    serve(
        postmortem_flow.to_deployment(name="nightly-0015", cron="15 0 * * *", timezone="UTC"),
        summary_flow.to_deployment(name="nightly-0045", cron="45 0 * * *", timezone="UTC"),
        weekly_flow.to_deployment(name="weekly-mon-0100", cron="0 1 * * 1", timezone="UTC"),
    )


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "crontab"
    if mode == "crontab":
        print(crontab_block(), end="")
    elif mode == "prefect":
        serve_prefect()
    else:
        sys.exit(f"unknown mode {mode!r}; use crontab|prefect")
