"""Each test proves a risk-invariants.mdc limit triggers. Do not delete tests to make a
change pass; that is the thing these tests exist to prevent."""

from datetime import UTC, datetime, timedelta

import pytest

from risk.limits import (
    LIMITS,
    RiskLimits,
    RiskViolation,
    check_exposure,
    enforce_exposure,
    in_event_window,
    max_position_from_risk,
    scale_to_exposure_limits,
)

pytestmark = pytest.mark.risk


def test_constitution_defaults_are_unchanged():
    """If this fails, someone changed a constitution value. Update the .mdc, get human sign-off."""
    assert LIMITS.max_risk_per_trade == 0.005
    assert LIMITS.max_gross_exposure == 2.0
    assert LIMITS.max_net_exposure == 1.0
    assert LIMITS.daily_loss_limit == -0.025
    assert LIMITS.trailing_dd_limit == -0.08
    assert LIMITS.kelly_fraction == 0.25
    assert LIMITS.vol_target_annual == 0.15
    assert LIMITS.event_pre_minutes == 15
    assert LIMITS.event_post_minutes == 30
    assert LIMITS.data_staleness_seconds == 180
    assert LIMITS.reconciliation_tolerance == 0.01
    assert LIMITS.regime_multipliers == {"Trend": 1.0, "Range": 0.8, "Chaos": 0.3}


def test_limits_are_frozen():
    with pytest.raises(Exception):
        LIMITS.max_gross_exposure = 5.0  # type: ignore[misc]
    assert RiskLimits().max_gross_exposure == 2.0


def test_gross_limit_triggers():
    chk = check_exposure({"BTC": 1.2, "ETH": -0.9})  # gross 2.1, net 0.3
    assert not chk.ok and any("gross" in v for v in chk.violations)
    with pytest.raises(RiskViolation):
        enforce_exposure({"BTC": 1.2, "ETH": -0.9})


def test_net_limit_triggers():
    chk = check_exposure({"BTC": 0.6, "ETH": 0.6})  # gross 1.2 ok, net 1.2 > 1.0
    assert not chk.ok and any("net" in v for v in chk.violations)


def test_within_limits_passes():
    assert check_exposure({"BTC": 0.9, "ETH": -0.9}).ok  # market-neutral carry style


def test_scaling_never_increases_and_fits_both_limits():
    w = scale_to_exposure_limits({"BTC": 2.0, "ETH": 1.5})
    chk = check_exposure(w)
    assert chk.ok
    assert all(abs(w[k]) <= abs(v) for k, v in {"BTC": 2.0, "ETH": 1.5}.items())
    assert scale_to_exposure_limits({"BTC": 0.1}) == {"BTC": 0.1}


def test_per_trade_risk_cap():
    # 1% stop → at most 0.5%/1% = 50% of equity notional
    assert max_position_from_risk(100_000, 0.01) == pytest.approx(50_000)
    # 0.1% stop would allow 5× equity by risk alone; the gross limit must still cap it elsewhere
    assert max_position_from_risk(100_000, 0.001) == pytest.approx(500_000)
    with pytest.raises(ValueError):
        max_position_from_risk(100_000, 0.0)  # a trade without a stop is not sizeable
    assert max_position_from_risk(0, 0.01) == 0.0


def test_event_window_blocks_15_before_30_after():
    ev = datetime(2026, 3, 18, 18, 0, tzinfo=UTC)  # FOMC
    assert in_event_window(ev - timedelta(minutes=15), [ev])
    assert in_event_window(ev + timedelta(minutes=30), [ev])
    assert in_event_window(ev, [ev])
    assert not in_event_window(ev - timedelta(minutes=16), [ev])
    assert not in_event_window(ev + timedelta(minutes=31), [ev])
    assert not in_event_window(ev, [])
