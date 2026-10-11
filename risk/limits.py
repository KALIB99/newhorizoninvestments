from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field


class RiskLimits(BaseModel):
    """Canonical values from risk-invariants.mdc. Frozen. Do not loosen without the human's
    explicit approval in the PR description (and update the .mdc in the same PR).

    Amendment 2026-10-10, CIO-approved (tasks.md T-018, research/reports/constitution_review.md):
    vol target 15% → 10% and trailing hard halt −8% → −15%, with −8% becoming an automatic
    de-risk tier (risk per trade × 0.5, alert). Rationale: at 15% vol a Sharpe-1 book tripped
    the −8% sticky halt with ~100% probability within 3 years; at 10% / −15% it is ≈ 21%.
    """

    model_config = ConfigDict(frozen=True)

    max_risk_per_trade: float = Field(0.005, description="fraction of equity at risk per trade")
    max_gross_exposure: float = Field(2.0, description="Σ|w_i| ≤ 2.0× equity")
    max_net_exposure: float = Field(1.0, description="|Σ w_i| ≤ 1.0× equity")
    daily_loss_limit: float = Field(-0.025, description="flatten + halt until next UTC day")
    trailing_dd_derisk: float = Field(-0.08, description="from HWM; risk per trade × multiplier + alert, auto-recovers")
    trailing_dd_derisk_multiplier: float = Field(0.5, description="risk per trade multiplier while in the de-risk tier")
    trailing_dd_limit: float = Field(-0.15, description="from HWM; halt, human re-enable")
    kelly_fraction: float = Field(0.25, description="apply 0.25 × Kelly")
    vol_target_annual: float = Field(0.10, description="10% annualised, 20-period EWMA")
    event_pre_minutes: int = Field(15, description="no new risk before Tier-1 event")
    event_post_minutes: int = Field(30, description="no new risk after Tier-1 event")
    data_staleness_seconds: int = Field(180, description="kill switch if data older than this")
    reconciliation_tolerance: float = Field(0.01, description="|local − exchange| / exchange > 1% → halt")
    exchange_risk_flag_threshold: float = Field(0.7, description="news exchange_risk ≥ 0.7 → gross × 0.5")
    exchange_risk_gross_multiplier: float = 0.5
    chaos_gross_multiplier: float = 0.3
    regime_multipliers: dict[str, float] = Field(default_factory=lambda: {"Trend": 1.0, "Range": 0.8, "Chaos": 0.3})


LIMITS = RiskLimits()


class RiskViolation(Exception):
    def __init__(self, rule: str, detail: str) -> None:
        self.rule = rule
        self.detail = detail
        super().__init__(f"{rule}: {detail}")


@dataclass(frozen=True)
class ExposureCheck:
    gross: float
    net: float
    ok: bool
    violations: tuple[str, ...]


def check_exposure(weights: Mapping[str, float], limits: RiskLimits = LIMITS) -> ExposureCheck:
    """``weights`` are positions as fractions of equity (signed). Pure; raises nothing."""
    gross = float(sum(abs(w) for w in weights.values()))
    net = float(sum(weights.values()))
    v: list[str] = []
    if gross > limits.max_gross_exposure + 1e-12:
        v.append(f"gross {gross:.3f} > {limits.max_gross_exposure}")
    if abs(net) > limits.max_net_exposure + 1e-12:
        v.append(f"|net| {abs(net):.3f} > {limits.max_net_exposure}")
    return ExposureCheck(gross, net, not v, tuple(v))


def enforce_exposure(weights: Mapping[str, float], limits: RiskLimits = LIMITS) -> None:
    chk = check_exposure(weights, limits)
    if not chk.ok:
        raise RiskViolation("exposure", "; ".join(chk.violations))


def scale_to_exposure_limits(weights: Mapping[str, float], limits: RiskLimits = LIMITS) -> dict[str, float]:
    """Proportionally shrink a weight vector until gross and net both fit. Never scales up."""
    chk = check_exposure(weights, limits)
    k = 1.0
    if chk.gross > 0:
        k = min(k, limits.max_gross_exposure / chk.gross)
    if abs(chk.net) > 0:
        k = min(k, limits.max_net_exposure / abs(chk.net))
    return {s: w * k for s, w in weights.items()}


def max_position_from_risk(equity: float, stop_distance_frac: float, limits: RiskLimits = LIMITS) -> float:
    """Largest notional such that losing ``stop_distance_frac`` of it costs no more than
    ``max_risk_per_trade`` of equity. Example: 1% stop → 0.5% / 1% = 0.5× equity."""
    if equity <= 0:
        return 0.0
    if stop_distance_frac <= 0:
        raise ValueError("stop_distance_frac must be > 0; a trade without a stop has unbounded risk")
    return equity * limits.max_risk_per_trade / stop_distance_frac


def in_event_window(ts: datetime, event_times: Iterable[datetime], limits: RiskLimits = LIMITS) -> bool:
    """True if ``ts`` is within [event − pre, event + post] of any Tier-1 event."""
    pre = timedelta(minutes=limits.event_pre_minutes)
    post = timedelta(minutes=limits.event_post_minutes)
    return any(ev - pre <= ts <= ev + post for ev in event_times)
