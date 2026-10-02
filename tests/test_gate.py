"""eval.gate: passes a good tearsheet, fails a bad one, catches hash drift, CLI exit codes."""

from datetime import UTC, datetime, timedelta

import pytest

from eval import gate
from eval.report import Tearsheet
from signals.base import Params


class DemoParams(Params):
    entry_z: float = 1.5
    exit_z: float = 0.5


def mk_tearsheet(**over) -> Tearsheet:
    p = DemoParams()
    now = datetime(2026, 1, 1, tzinfo=UTC)
    base = dict(
        strategy="demo_carry",
        config_hash=p.config_hash(),
        params=p.model_dump(),
        params_class=f"{__name__}.DemoParams",
        n_trials=30,
        data_start=now - timedelta(days=800),
        data_end=now,
        timeframe="1h",
        symbols=["BTC/USDT:USDT"],
        cost_model={},
        sharpe_oos=1.2,
        sharpe_is=1.6,
        deflated_sharpe=0.98,
        dsr_p_value=0.02,
        pbo=0.2,
        max_drawdown=-0.08,
        calmar=1.5,
        turnover=0.02,
        cost_drag_bps_per_trade=8.0,
        n_trades_oos=450,
        hit_rate=0.55,
        payoff_ratio=1.1,
        sharpe_oos_at_1_5x_costs=0.6,
        per_regime_pnl={"Trend": 0.05, "Range": 0.08, "Chaos": -0.01},
        monthly_pnl={"2025-12": 0.01},
        sharpe_by_fold=[1.0, 1.3, 1.1],
        verdict="Candidate for Judge",
    )
    base.update(over)
    return Tearsheet(**base)


def _passed(checks):
    return all(c.passed or c.severity == "WARN" for c in checks)


def test_self_test_passes():
    assert gate.self_test()


def test_good_tearsheet_passes_including_hash_check():
    assert _passed(gate.evaluate(mk_tearsheet()))


@pytest.mark.parametrize(
    "over,name",
    [
        ({"dsr_p_value": 0.06}, "DSR"),
        ({"pbo": 0.31}, "PBO"),
        ({"n_trades_oos": 199}, "OOS trades"),
        ({"sharpe_oos_at_1_5x_costs": 0.0}, "1.5x costs"),
        ({"per_regime_pnl": {"Trend": 0.1, "Range": 0.1}}, "regimes covered"),
        ({"per_regime_pnl": {"Trend": 0.1, "Range": -0.1, "Chaos": -0.1}}, "positive in"),
        ({"sharpe_oos": 0.7, "sharpe_is": 1.6}, "OOS/IS"),
        ({"sharpe_oos": 3.1, "sharpe_is": 3.5}, "plausibility"),
        ({"verdict": "Insufficient evidence"}, "verdict"),
    ],
)
def test_each_threshold_fails_independently(over, name):
    checks = gate.evaluate(mk_tearsheet(**over))
    failed = [c for c in checks if not c.passed and c.severity == "FAIL"]
    assert failed, name
    assert any(name.lower() in c.name.lower() for c in failed), [c.name for c in failed]


def test_short_data_span_is_warning_not_failure():
    ts = mk_tearsheet(data_start=datetime(2025, 6, 1, tzinfo=UTC))
    checks = gate.evaluate(ts)
    warn = [c for c in checks if c.severity == "WARN"]
    assert warn and not warn[0].passed
    assert _passed(checks)


def test_config_hash_drift_fails():
    ts = mk_tearsheet(config_hash="deadbeef0000")
    checks = gate.evaluate(ts)
    assert not [c for c in checks if "config hash" in c.name][0].passed


def test_unimportable_params_class_fails():
    ts = mk_tearsheet(params_class="research.strategies.nope.Nope")
    assert not [c for c in gate.evaluate(ts) if "config hash" in c.name][0].passed


def test_momentum_payoff_ratio_rule():
    ts = mk_tearsheet(strategy="tsmom_1h", payoff_ratio=1.4)
    assert not _passed(gate.evaluate(ts))
    ts = mk_tearsheet(strategy="tsmom_1h", payoff_ratio=1.6)
    assert _passed(gate.evaluate(ts))


def test_cli_roundtrip_with_saved_tearsheet(tmp_path):
    ts = mk_tearsheet()
    md, js = ts.save(tmp_path)
    assert md.exists() and js.exists()
    assert Tearsheet.load(js) == ts
    assert gate.main(["demo_carry", "--reports-dir", str(tmp_path)]) == 0
    assert gate.main(["missing", "--reports-dir", str(tmp_path)]) == 1
    mk_tearsheet(n_trades_oos=10, strategy="bad_one").save(tmp_path)
    assert gate.main(["--all", "--reports-dir", str(tmp_path)]) == 1


def test_markdown_contains_all_headline_metrics():
    md = mk_tearsheet().to_markdown()
    for key in ("Deflated Sharpe", "PBO", "Trades OOS", "1.5× costs", "Candidate for Judge", "Trials evaluated"):
        assert key in md
