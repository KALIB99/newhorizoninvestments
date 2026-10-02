"""Sticky kill switch. Trips on: daily loss, trailing drawdown, reconciliation mismatch,
data staleness, exchange-risk flag, or an explicit ``trip``. Once halted, nothing trades.

Two halt classes:
- ``daily_loss`` auto-clears at the next UTC day boundary (rule: "halt until next UTC day").
- everything else is sticky until ``human_reenable(signature=...)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from loguru import logger

from risk.limits import LIMITS, RiskLimits


class HaltReason(StrEnum):
    DAILY_LOSS = "daily_loss"
    TRAILING_DD = "trailing_drawdown"
    RECONCILIATION = "reconciliation_mismatch"
    DATA_STALE = "data_staleness"
    EXCHANGE_RISK = "exchange_risk_flag"
    MANUAL = "manual"


@dataclass
class KillSwitchState:
    halted: bool = False
    reasons: list[HaltReason] = field(default_factory=list)
    halted_at: datetime | None = None
    day_start_equity: float | None = None
    day: datetime | None = None  # UTC date of day_start_equity
    high_water_mark: float = 0.0
    gross_multiplier: float = 1.0
    log: list[str] = field(default_factory=list)


class KillSwitch:
    def __init__(self, limits: RiskLimits = LIMITS, initial_equity: float | None = None) -> None:
        self.limits = limits
        self.state = KillSwitchState()
        if initial_equity is not None:
            self.state.high_water_mark = initial_equity

    # ---- status -------------------------------------------------------------------------
    @property
    def halted(self) -> bool:
        return self.state.halted

    def can_trade(self, now: datetime | None = None) -> bool:
        """Also performs the daily-loss auto-clear if the UTC day has rolled over."""
        now = now or datetime.now(UTC)
        self._maybe_clear_daily(now)
        return not self.state.halted

    def gross_multiplier(self) -> float:
        return 0.0 if self.state.halted else self.state.gross_multiplier

    # ---- triggers -----------------------------------------------------------------------
    def trip(self, reason: HaltReason | str, detail: str = "", now: datetime | None = None) -> None:
        reason = HaltReason(reason)
        now = now or datetime.now(UTC)
        if reason not in self.state.reasons:
            self.state.reasons.append(reason)
        self.state.halted = True
        self.state.halted_at = self.state.halted_at or now
        msg = f"KILL SWITCH {reason} @ {now.isoformat()} {detail}".strip()
        self.state.log.append(msg)
        logger.critical(msg)

    def on_equity(self, equity: float, now: datetime) -> None:
        """Feed marked-to-market equity. Checks daily loss and trailing drawdown."""
        if now.tzinfo is None:
            raise ValueError("now must be tz-aware UTC")
        self._maybe_clear_daily(now)
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if self.state.day is None or day > self.state.day:
            self.state.day = day
            self.state.day_start_equity = equity
        self.state.high_water_mark = max(self.state.high_water_mark, equity)

        # tolerance errs on the side of tripping: a limit that is "exactly" hit counts as hit
        eps = 1e-9
        if self.state.day_start_equity:
            daily = equity / self.state.day_start_equity - 1.0
            if daily <= self.limits.daily_loss_limit + eps:
                self.trip(HaltReason.DAILY_LOSS, f"daily={daily:.2%} <= {self.limits.daily_loss_limit:.2%}", now)
        if self.state.high_water_mark > 0:
            dd = equity / self.state.high_water_mark - 1.0
            if dd <= self.limits.trailing_dd_limit + eps:
                self.trip(HaltReason.TRAILING_DD, f"dd={dd:.2%} <= {self.limits.trailing_dd_limit:.2%}", now)

    def on_reconciliation(
        self, local: dict[str, float], exchange: dict[str, float], now: datetime | None = None
    ) -> bool:
        """Compare local vs exchange positions (notional or qty, same units). Returns ok."""
        tol = self.limits.reconciliation_tolerance
        for sym in set(local) | set(exchange):
            a, b = local.get(sym, 0.0), exchange.get(sym, 0.0)
            denom = max(abs(b), abs(a), 1e-12)
            if abs(a - b) / denom > tol:
                self.trip(HaltReason.RECONCILIATION, f"{sym}: local={a} exchange={b}", now)
                return False
        return True

    def on_data_heartbeat(self, last_bar_ts: datetime, now: datetime) -> bool:
        age = (now - last_bar_ts).total_seconds()
        if age > self.limits.data_staleness_seconds:
            self.trip(HaltReason.DATA_STALE, f"age={age:.0f}s > {self.limits.data_staleness_seconds}s", now)
            return False
        return True

    def on_exchange_risk(self, score: float, now: datetime | None = None) -> None:
        """news-analyst exchange_risk flag. ≥ threshold → gross × 0.5 (not a halt); 1.0 →
        halt (exchange is down / insolvent)."""
        if score >= 1.0:
            self.trip(HaltReason.EXCHANGE_RISK, f"score={score}", now)
        elif score >= self.limits.exchange_risk_flag_threshold:
            self.state.gross_multiplier = min(self.state.gross_multiplier, self.limits.exchange_risk_gross_multiplier)
            self.state.log.append(f"exchange_risk {score:.2f} → gross × {self.state.gross_multiplier}")
        else:
            self.state.gross_multiplier = 1.0

    # ---- re-enable ----------------------------------------------------------------------
    def _maybe_clear_daily(self, now: datetime) -> None:
        """Only the DAILY_LOSS halt clears automatically, and only on a new UTC day."""
        if not self.state.halted or self.state.reasons != [HaltReason.DAILY_LOSS]:
            return
        assert self.state.halted_at is not None
        if now.date() > self.state.halted_at.date():
            self.state.halted = False
            self.state.reasons.clear()
            self.state.halted_at = None
            self.state.log.append(f"daily-loss halt cleared at {now.isoformat()}")
            logger.warning("daily-loss halt cleared (new UTC day)")

    def human_reenable(self, signature: str, now: datetime | None = None) -> None:
        """Only path out of a sticky halt. ``signature`` is recorded verbatim in the log; it
        is the human's name/initials and is required to be non-empty."""
        if not signature or not signature.strip():
            raise ValueError("human_reenable requires a non-empty signature")
        now = now or datetime.now(UTC)
        self.state.log.append(f"re-enabled by {signature!r} at {now.isoformat()} after {self.state.reasons}")
        logger.warning("kill switch re-enabled by {}", signature)
        self.state.halted = False
        self.state.reasons.clear()
        self.state.halted_at = None
        self.state.gross_multiplier = 1.0
