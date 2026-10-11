from datetime import UTC, datetime, timedelta

import pytest

from risk.kill_switch import HaltReason, KillSwitch

pytestmark = pytest.mark.risk

T0 = datetime(2026, 1, 10, 9, 0, tzinfo=UTC)


def test_daily_loss_halts_and_clears_next_utc_day():
    ks = KillSwitch(initial_equity=100_000)
    ks.on_equity(100_000, T0)
    ks.on_equity(98_000, T0 + timedelta(hours=1))  # -2.0%: fine
    assert ks.can_trade(T0 + timedelta(hours=1))
    ks.on_equity(97_400, T0 + timedelta(hours=2))  # -2.6% ≤ -2.5%
    assert ks.halted and ks.state.reasons == [HaltReason.DAILY_LOSS]
    assert not ks.can_trade(T0 + timedelta(hours=14))  # still same UTC day (23:00)
    assert ks.can_trade(T0 + timedelta(hours=16))  # 01:00 next day → cleared
    assert ks.gross_multiplier() == 1.0


def test_daily_loss_boundary_is_inclusive():
    ks = KillSwitch(initial_equity=100_000)
    ks.on_equity(100_000, T0)
    ks.on_equity(97_500, T0 + timedelta(minutes=1))  # exactly -2.5%
    assert ks.halted


def test_trailing_drawdown_derisk_tier_at_minus_8pct_then_recovers():
    ks = KillSwitch(initial_equity=100_000)
    ks.on_equity(110_000, T0)  # new HWM
    ks.on_equity(101_300, T0 + timedelta(days=1))  # -7.9%: normal
    assert ks.risk_multiplier() == 1.0 and not ks.state.derisk
    ks.on_equity(101_200, T0 + timedelta(days=2))  # -8.0%: de-risk, not a halt
    assert not ks.halted and ks.state.derisk and ks.risk_multiplier() == 0.5
    assert ks.can_trade(T0 + timedelta(days=2))
    assert any("DE-RISK" in line for line in ks.state.log)
    ks.on_equity(104_000, T0 + timedelta(days=3))  # -5.5%: tier clears without a human
    assert ks.risk_multiplier() == 1.0 and not ks.state.derisk


def test_trailing_drawdown_is_sticky_until_human():
    ks = KillSwitch(initial_equity=100_000)
    ks.on_equity(110_000, T0)  # new HWM
    ks.on_equity(94_000, T0 + timedelta(days=3))  # -14.5%: de-risk only
    assert not ks.halted
    ks.on_equity(93_500, T0 + timedelta(days=4))  # -15.0% from HWM
    assert ks.halted and HaltReason.TRAILING_DD in ks.state.reasons
    assert ks.risk_multiplier() == 0.0
    assert not ks.can_trade(T0 + timedelta(days=30))  # time does not heal this one
    with pytest.raises(ValueError):
        ks.human_reenable("")
    ks.human_reenable("CIO", now=T0 + timedelta(days=30))
    assert ks.can_trade(T0 + timedelta(days=30))
    assert any("re-enabled by 'CIO'" in line for line in ks.state.log)


def test_trailing_dd_not_cleared_by_day_rollover_even_with_daily_loss():
    ks = KillSwitch(initial_equity=100_000)
    ks.on_equity(100_000, T0)
    ks.on_equity(84_000, T0 + timedelta(hours=1))  # -16% in one day: both trip
    assert set(ks.state.reasons) == {HaltReason.DAILY_LOSS, HaltReason.TRAILING_DD}
    assert not ks.can_trade(T0 + timedelta(days=1))


def test_reconciliation_mismatch_halts():
    ks = KillSwitch()
    assert ks.on_reconciliation({"BTC": 1.000}, {"BTC": 1.005})  # 0.5% ok
    assert not ks.on_reconciliation({"BTC": 1.00}, {"BTC": 1.02})  # 2% > 1%
    assert ks.halted and HaltReason.RECONCILIATION in ks.state.reasons


def test_reconciliation_catches_position_missing_on_one_side():
    ks = KillSwitch()
    assert not ks.on_reconciliation({"ETH": 5.0}, {})
    assert ks.halted


def test_data_staleness_halts_after_3_minutes():
    ks = KillSwitch()
    assert ks.on_data_heartbeat(T0, T0 + timedelta(seconds=180))
    assert not ks.on_data_heartbeat(T0, T0 + timedelta(seconds=181))
    assert ks.halted and HaltReason.DATA_STALE in ks.state.reasons


def test_exchange_risk_flag_halves_gross_and_full_score_halts():
    ks = KillSwitch()
    ks.on_exchange_risk(0.69)
    assert ks.gross_multiplier() == 1.0
    ks.on_exchange_risk(0.7)
    assert ks.gross_multiplier() == 0.5
    ks.on_exchange_risk(0.2)
    assert ks.gross_multiplier() == 1.0
    ks.on_exchange_risk(1.0)
    assert ks.halted and ks.gross_multiplier() == 0.0


def test_manual_trip_is_sticky():
    ks = KillSwitch()
    ks.trip("manual", "operator")
    assert not ks.can_trade(T0 + timedelta(days=5))


def test_naive_timestamps_rejected():
    ks = KillSwitch()
    with pytest.raises(ValueError):
        ks.on_equity(1.0, datetime(2026, 1, 1))
