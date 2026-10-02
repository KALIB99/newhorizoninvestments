"""The live-trading gate. Two independent conditions, both required:

1. ``LIVE_TRADING`` environment variable is exactly ``"1"``.
2. ``capital_allocation.yaml`` exists, is signed by a human (non-empty ``signed_by``,
   ``signed_at``, ``signature``), is not expired, and has at least one allocation.

Agents never edit capital_allocation.yaml. The schema is enforced here so a malformed or
unsigned file fails closed.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

ALLOCATION_PATH = Path("capital_allocation.yaml")


class LiveTradingBlocked(RuntimeError):
    pass


class Allocation(BaseModel):
    strategy: str
    exchange: str
    capital_usd: float = Field(gt=0)
    max_fraction_of_target: float = Field(le=0.10, gt=0, description="initial live ≤ 10% of target")
    evidence: list[str] = Field(
        min_length=1, description="links: tearsheet, judge verdict, gate output, fill-quality, risk review"
    )


class CapitalAllocation(BaseModel):
    version: int = Field(ge=1)
    signed_by: str = Field(min_length=2)
    signed_at: datetime
    signature: str = Field(min_length=8, description="human-provided token; agents cannot generate it")
    expires_at: datetime
    allocations: list[Allocation] = Field(min_length=1)

    @field_validator("signed_at", "expires_at")
    @classmethod
    def _tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamps in capital_allocation.yaml must be timezone-aware (UTC)")
        return v

    def is_valid_at(self, now: datetime) -> bool:
        return self.signed_at <= now < self.expires_at


def load_allocation(path: Path | str = ALLOCATION_PATH) -> CapitalAllocation:
    p = Path(path)
    if not p.exists():
        raise LiveTradingBlocked(f"{p} does not exist; the human must create and sign it")
    raw = yaml.safe_load(p.read_text()) or {}
    try:
        return CapitalAllocation.model_validate(raw)
    except ValidationError as e:
        raise LiveTradingBlocked(f"{p} is not a valid signed allocation: {e}") from e


def live_env_enabled() -> bool:
    return os.environ.get("LIVE_TRADING", "") == "1"


def assert_live_allowed(
    strategy: str | None = None,
    path: Path | str = ALLOCATION_PATH,
    now: datetime | None = None,
) -> CapitalAllocation:
    """Raise ``LiveTradingBlocked`` unless both gate conditions hold. If ``strategy`` is
    given, it must also appear in the allocations."""
    if not live_env_enabled():
        raise LiveTradingBlocked("LIVE_TRADING != '1'")
    alloc = load_allocation(path)
    now = now or datetime.now(UTC)
    if not alloc.is_valid_at(now):
        raise LiveTradingBlocked(
            f"allocation signed_at={alloc.signed_at.isoformat()} expires_at={alloc.expires_at.isoformat()} not valid at {now.isoformat()}"
        )
    if strategy is not None and strategy not in {a.strategy for a in alloc.allocations}:
        raise LiveTradingBlocked(f"strategy {strategy!r} has no signed allocation")
    return alloc
