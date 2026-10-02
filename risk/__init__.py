"""Risk: the invariants in .cursor/rules/risk-invariants.mdc as code.

Every limit here has a test in tests/test_risk_limits.py and tests/test_kill_switch.py that
proves it triggers. Loosening a default is a constitution change.
"""

from risk.kill_switch import HaltReason, KillSwitch, KillSwitchState
from risk.limits import (
    LIMITS,
    ExposureCheck,
    RiskLimits,
    RiskViolation,
    check_exposure,
    in_event_window,
    max_position_from_risk,
)

__all__ = [
    "LIMITS",
    "ExposureCheck",
    "HaltReason",
    "KillSwitch",
    "KillSwitchState",
    "RiskLimits",
    "RiskViolation",
    "check_exposure",
    "in_event_window",
    "max_position_from_risk",
]
