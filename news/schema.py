from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

from risk.limits import LIMITS


class Category(StrEnum):
    REGULATORY = "regulatory"
    EXCHANGE_RISK = "exchange_risk"
    MACRO = "macro"
    HACK = "hack"
    ETF_FLOW = "etf_flow"
    PROTOCOL = "protocol"
    LIQUIDATION = "liquidation"
    OTHER = "other"


class Tier(StrEnum):
    T1 = "tier1"  # FOMC, CPI, NFP — hard no-trade window
    T2 = "tier2"  # ETF decisions, large unlocks — soft


class NewsItem(BaseModel):
    """One structured record per headline. Produced by news-analyst."""

    model_config = ConfigDict(frozen=True)

    ts: datetime = Field(description="event time (UTC)")
    ingested_at: datetime = Field(description="when we saw it; latency = ingested_at − ts")
    source: str
    headline: str
    entities: list[str] = Field(default_factory=list, description="tickers/protocols/exchanges")
    category: Category
    direction: float = Field(ge=-1, le=1)
    magnitude: float = Field(ge=0, le=1)
    horizon_minutes: int = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    is_scheduled: bool = False
    dedupe_key: str | None = None

    @field_validator("ts", "ingested_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamps must be tz-aware")
        return v.astimezone(UTC)

    @property
    def latency(self) -> timedelta:
        return self.ingested_at - self.ts

    @property
    def impulse(self) -> float:
        return self.direction * self.magnitude * self.confidence


class ScheduledEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    ts: datetime
    name: str
    tier: Tier
    pre_minutes: int = LIMITS.event_pre_minutes
    post_minutes: int = LIMITS.event_post_minutes

    @property
    def window(self) -> tuple[datetime, datetime]:
        return self.ts - timedelta(minutes=self.pre_minutes), self.ts + timedelta(minutes=self.post_minutes)

    def blocks(self, ts: datetime) -> bool:
        lo, hi = self.window
        return self.tier == Tier.T1 and lo <= ts <= hi


def sentiment_impulse(
    items: list[NewsItem],
    index: pd.DatetimeIndex,
    half_life_minutes: float = 90.0,
    entity: str | None = None,
) -> pd.Series:
    """EWMA of direction×magnitude×confidence with the given half-life, evaluated on
    ``index``. Each item contributes from its ``ingested_at`` (not ``ts``) — we can only
    act on what we have seen. Returns a series in roughly [-1, 1]."""
    out = pd.Series(0.0, index=index)
    if not items:
        return out
    decay = math.log(2) / (half_life_minutes * 60.0)
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    t = (index.tz_convert("UTC") - epoch).total_seconds().to_numpy(dtype=float)
    acc = np.zeros(len(index))
    for it in items:
        if entity is not None and entity not in it.entities:
            continue
        age = t - it.ingested_at.timestamp()
        acc += it.impulse * np.where(age >= 0, np.exp(-decay * np.clip(age, 0, None)), 0.0)
    out[:] = np.clip(acc, -1.0, 1.0)
    return out
