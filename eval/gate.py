"""Promotion gate: ``python -m eval.gate <strategy>``.

Machine half of the promotion-gate skill. Reads the strategy's latest tearsheet JSON from
research/reports/ and checks it against the constitution's thresholds. Exit 0 = pass.

The gate is deliberately dumb: it trusts the numbers in the tearsheet. Catching lies in
the numbers is the Judge's job; the gate catches numbers that are honest but inadequate,
and tearsheets whose config hash no longer matches the code.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from eval.report import REPORTS_DIR, Tearsheet

STRATEGIES_DIR = Path("research/strategies")


class GateThresholds(BaseModel):
    """Constitution values. Changing these is a constitution change."""

    model_config = ConfigDict(frozen=True)

    dsr_p_value_max: float = 0.05
    pbo_max: float = 0.30
    min_oos_trades: int = 200
    min_oos_trades_multiday: int = 100
    """Amended 2026-10-10 with CIO approval (tasks.md T-018): strategies that hold ≥ 1 day
    cannot produce 200 independent OOS trades in a 2–3 year window; 100 applies to them. The
    Judge may additionally rule on an episode-count exception for carry-type books."""
    cost_stress_multiplier: float = 1.5
    min_regimes: int = 3
    min_positive_regimes: int = 2
    min_oos_is_ratio: float = 0.5
    max_plausible_sharpe: float = 3.0
    max_plausible_sharpe_neutral_multiday: float = 6.0
    """Amended 2026-10-11 with CIO approval (tasks.md T-002, Judge's item 5): a market-neutral
    multiday book (tearsheet declares both) is flat most days, so its return dispersion is tiny
    and Sharpe 4–5 is the normal shape of a ~4% CAGR yield, not a mis-costing signature. The cap
    stays a sanity bound; directional and intraday books keep 3.0."""
    min_data_span_days: int = 730
    min_payoff_ratio_momentum: float = 1.5


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    severity: str = "FAIL"  # FAIL blocks; WARN does not


@dataclass
class GateResult:
    strategy: str
    tearsheet: Path | None
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed or c.severity == "WARN" for c in self.checks)

    def render(self) -> str:
        lines = [f"eval.gate — {self.strategy}  ({self.tearsheet or 'no tearsheet'})"]
        for c in self.checks:
            mark = "PASS" if c.passed else c.severity
            lines.append(f"  [{mark:4}] {c.name:<28} {c.detail}")
        lines.append(f"  => {'PASS' if self.passed else 'FAIL'}")
        return "\n".join(lines)


def _recompute_hash(ts: Tearsheet) -> tuple[bool, str]:
    """Import the Params class named in the tearsheet, rebuild it from the stored params and
    compare hashes. Any import failure is a failure: the code the report describes must
    exist on this branch."""
    try:
        mod_name, cls_name = ts.params_class.rsplit(".", 1)
        cls = getattr(importlib.import_module(mod_name), cls_name)
        params = cls(**ts.params)
        h = params.config_hash()
    except Exception as e:  # noqa: BLE001 - we report every failure mode the same way
        return False, f"could not rebuild params from code: {type(e).__name__}: {e}"
    return h == ts.config_hash, f"code={h} report={ts.config_hash}"


THRESHOLDS = GateThresholds()


def _is_daily_or_slower(tf: str) -> bool:
    """'1d', '3d', '1w' → True; '1m', '5m', '1h', '4h' → False."""
    return tf.strip().lower().endswith(("d", "w"))


def evaluate(ts: Tearsheet, thr: GateThresholds | None = None, *, check_code: bool = True) -> list[Check]:
    thr = thr or THRESHOLDS
    c: list[Check] = []

    if check_code:
        ok, detail = _recompute_hash(ts)
        c.append(Check("config hash matches code", ok, detail))

    c.append(
        Check(
            "researcher verdict",
            ts.verdict == "Candidate for Judge",
            f"'{ts.verdict}' (must be 'Candidate for Judge')",
        )
    )
    c.append(
        Check(
            f"DSR p-value < {thr.dsr_p_value_max:.2f}",
            ts.dsr_p_value < thr.dsr_p_value_max,
            f"p={ts.dsr_p_value:.4f} (n_trials={ts.n_trials})",
        )
    )
    c.append(Check(f"PBO < {thr.pbo_max:.2f}", ts.pbo < thr.pbo_max, f"pbo={ts.pbo:.3f}"))
    multiday = ts.horizon == "multiday" or _is_daily_or_slower(ts.timeframe)
    need = thr.min_oos_trades_multiday if multiday else thr.min_oos_trades
    c.append(
        Check(
            f"OOS trades >= {need}",
            ts.n_trades_oos >= need,
            f"n={ts.n_trades_oos} ({'multiday' if multiday else 'intraday'} horizon)",
        )
    )
    c.append(
        Check(
            f"positive at {thr.cost_stress_multiplier}x costs",
            ts.sharpe_oos_at_1_5x_costs > 0,
            f"sharpe@1.5x={ts.sharpe_oos_at_1_5x_costs:.2f}",
        )
    )

    n_reg = len(ts.per_regime_pnl)
    n_pos = sum(1 for v in ts.per_regime_pnl.values() if v > 0)
    c.append(
        Check(f">= {thr.min_regimes} regimes covered", n_reg >= thr.min_regimes, f"regimes={sorted(ts.per_regime_pnl)}")
    )
    c.append(
        Check(
            f"positive in >= {thr.min_positive_regimes} regimes",
            n_pos >= thr.min_positive_regimes,
            f"positive={n_pos}/{n_reg}",
        )
    )

    if ts.sharpe_is > 0:
        ratio = ts.sharpe_oos / ts.sharpe_is
        c.append(Check(f"OOS/IS Sharpe >= {thr.min_oos_is_ratio}", ratio >= thr.min_oos_is_ratio, f"ratio={ratio:.2f}"))
    else:
        c.append(Check("OOS/IS Sharpe", False, f"in-sample Sharpe {ts.sharpe_is:.2f} <= 0"))

    neutral_carve_out = multiday and ts.market_neutral
    cap = thr.max_plausible_sharpe_neutral_multiday if neutral_carve_out else thr.max_plausible_sharpe
    c.append(
        Check(
            f"Sharpe <= {cap} (plausibility)",
            ts.sharpe_oos <= cap,
            f"sharpe_oos={ts.sharpe_oos:.2f}; above this is a mis-costing/lookahead red flag"
            + (" [market-neutral multiday cap]" if neutral_carve_out else ""),
        )
    )

    span = ts.data_end - ts.data_start
    c.append(
        Check(
            f"data span >= {thr.min_data_span_days}d",
            span >= timedelta(days=thr.min_data_span_days),
            f"span={span.days}d (constitution: 2 years or all available)",
            severity="WARN",
        )
    )

    if ts.payoff_ratio is not None and any("mom" in s or "breakout" in s for s in ts.strategy.split("_")):
        c.append(
            Check(
                f"payoff ratio >= {thr.min_payoff_ratio_momentum} (momentum)",
                ts.payoff_ratio >= thr.min_payoff_ratio_momentum,
                f"payoff={ts.payoff_ratio:.2f}",
            )
        )
    return c


def run(strategy: str, reports_dir: Path | str = REPORTS_DIR, *, check_code: bool = True) -> GateResult:
    paths = Tearsheet.find(strategy, reports_dir)
    res = GateResult(strategy, None)
    if not paths:
        res.checks.append(Check("tearsheet exists", False, f"no {strategy}_<hash>.json under {reports_dir}"))
        return res
    res.tearsheet = paths[0]
    try:
        ts = Tearsheet.load(paths[0])
    except Exception as e:  # noqa: BLE001
        res.checks.append(Check("tearsheet parses", False, f"{type(e).__name__}: {e}"))
        return res
    res.checks.append(Check("tearsheet exists", True, paths[0].name))
    res.checks.extend(evaluate(ts, check_code=check_code))
    return res


# ---- self test ----------------------------------------------------------------------------
def _synthetic(passing: bool) -> Tearsheet:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    good = {
        "sharpe_oos": 1.3,
        "sharpe_is": 1.8,
        "deflated_sharpe": 0.985,
        "dsr_p_value": 0.015,
        "pbo": 0.18,
        "n_trades_oos": 640,
        "sharpe_oos_at_1_5x_costs": 0.7,
        "per_regime_pnl": {"Trend": 0.11, "Range": 0.04, "Chaos": -0.02},
        "verdict": "Candidate for Judge",
    }
    bad = {
        "sharpe_oos": 4.2,
        "sharpe_is": 4.9,
        "deflated_sharpe": 0.6,
        "dsr_p_value": 0.4,
        "pbo": 0.55,
        "n_trades_oos": 48,
        "sharpe_oos_at_1_5x_costs": -0.3,
        "per_regime_pnl": {"Trend": 0.3, "Range": -0.1},
        "verdict": "Candidate for Judge",
    }
    return Tearsheet(
        strategy="selftest",
        config_hash="0123456789ab",
        params={},
        params_class="signals.base.Params",
        n_trials=40,
        data_start=now - timedelta(days=800),
        data_end=now,
        timeframe="5m",
        symbols=["BTC/USDT:USDT"],
        cost_model={},
        max_drawdown=-0.09,
        calmar=1.4,
        turnover=0.05,
        cost_drag_bps_per_trade=9.0,
        monthly_pnl={"2025-12": 0.01},
        **(good if passing else bad),
    )


def self_test() -> bool:
    ok = evaluate(_synthetic(True), check_code=False)
    bad = evaluate(_synthetic(False), check_code=False)
    good_pass = all(c.passed or c.severity == "WARN" for c in ok)
    bad_fail = not all(c.passed or c.severity == "WARN" for c in bad)
    print(GateResult("selftest/passing", None, ok).render())
    print(GateResult("selftest/failing", None, bad).render())
    return good_pass and bad_fail


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m eval.gate", description=__doc__)
    ap.add_argument("strategy", nargs="?", help="strategy name (research/strategies/<name>.py)")
    ap.add_argument("--all", action="store_true", help="gate every strategy with a tearsheet")
    ap.add_argument(
        "--self-test", action="store_true", help="verify the gate passes a good tearsheet and fails a bad one"
    )
    ap.add_argument("--reports-dir", default=str(REPORTS_DIR))
    ap.add_argument("--no-code-check", action="store_true", help="skip config-hash recomputation (Judge use only)")
    args = ap.parse_args(argv)

    if args.self_test:
        return 0 if self_test() else 1

    names: list[str]
    if args.all:
        names = sorted({p.name.rsplit("_", 1)[0] for p in Path(args.reports_dir).glob("*_*.json")})
        if not names:
            print("no tearsheets found")
            return 0
    elif args.strategy:
        names = [args.strategy]
    else:
        ap.error("give a strategy name, --all or --self-test")
        return 2

    rc = 0
    for n in names:
        res = run(n, args.reports_dir, check_code=not args.no_code_check)
        print(res.render())
        rc |= 0 if res.passed else 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
