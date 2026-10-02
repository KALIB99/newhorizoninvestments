"""Transaction cost model. Every backtest charges this; there is no "gross" mode.

Per-side cost in bps = fee + spread/2 + slippage(size/ADV, spread)
where slippage_bps = a + b * sqrt(size/ADV) + c * spread_bps  (fitted by execution-engineer).

Funding is charged separately per holding period from the funding-rate series.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

FITTED_PATH = Path("execution/reports/slippage_fit.json")


class CostModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    taker_fee_bps: float = Field(5.0, ge=0, description="Binance/Bybit perp taker, VIP0 ≈ 5 bps")
    maker_fee_bps: float = Field(2.0, ge=0, description="perp maker, VIP0 ≈ 2 bps")
    spread_bps: float = Field(1.0, ge=0, description="typical BTC/ETH perp spread; wider for alts")
    slip_a: float = Field(0.5, ge=0, description="slippage intercept, bps")
    slip_b: float = Field(25.0, ge=0, description="bps per sqrt(size/ADV)")
    slip_c: float = Field(0.5, ge=0, description="bps per bp of spread")
    multiplier: float = Field(1.0, gt=0, description="stress multiplier; gate requires 1.5 to pass")
    source: str = "default_conservative"

    # ---- primitives ---------------------------------------------------------------------
    def slippage_bps(self, size_adv: float | np.ndarray, spread_bps: float | None = None) -> np.ndarray:
        s = self.spread_bps if spread_bps is None else spread_bps
        size_adv = np.asarray(size_adv, dtype=float)
        return self.slip_a + self.slip_b * np.sqrt(np.clip(size_adv, 0, None)) + self.slip_c * s

    def per_side_bps(
        self, size_adv: float | np.ndarray = 0.0, taker: bool = True, spread_bps: float | None = None
    ) -> np.ndarray:
        s = self.spread_bps if spread_bps is None else spread_bps
        fee = self.taker_fee_bps if taker else self.maker_fee_bps
        raw = fee + s / 2.0 + self.slippage_bps(size_adv, s)
        return np.asarray(raw * self.multiplier, dtype=float)

    def round_trip_bps(self, size_adv: float = 0.0, taker: bool = True) -> float:
        return float(2.0 * self.per_side_bps(size_adv, taker))

    def cost_drag(
        self,
        turnover: np.ndarray,
        size_adv: float | np.ndarray = 0.0,
        taker: bool = True,
        spread_bps: float | np.ndarray | None = None,
    ) -> np.ndarray:
        """Cost per bar as a fraction of equity given |Δposition| per bar (turnover).

        ``turnover`` is in units of equity (1.0 = turning over the full book once).
        """
        turnover = np.asarray(turnover, dtype=float)
        if spread_bps is None:
            spread_bps = self.spread_bps
        spread_bps = np.broadcast_to(np.asarray(spread_bps, dtype=float), turnover.shape)
        size_adv = np.broadcast_to(np.asarray(size_adv, dtype=float), turnover.shape)
        fee = self.taker_fee_bps if taker else self.maker_fee_bps
        per_side = (fee + spread_bps / 2.0 + self.slippage_bps(size_adv, spread_bps)) * self.multiplier
        return np.abs(turnover) * per_side / 1e4

    @staticmethod
    def funding_drag(position: np.ndarray, funding_rate: np.ndarray) -> np.ndarray:
        """Funding paid per bar: long pays when funding > 0. Both arrays aligned per bar;
        funding_rate is the *per-bar* rate (exchange 8h rate pro-rated by the data engineer)."""
        return np.asarray(position, dtype=float) * np.asarray(funding_rate, dtype=float)

    # ---- variants -----------------------------------------------------------------------
    def scaled(self, multiplier: float) -> CostModel:
        return self.model_copy(update={"multiplier": self.multiplier * multiplier})

    @classmethod
    def from_fitted(cls, path: Path | str = FITTED_PATH, **overrides: float) -> CostModel:
        """Load the execution-engineer's fitted slippage coefficients if present, else the
        conservative defaults. Never silently optimistic: a missing file is logged as such."""
        p = Path(path)
        if not p.exists():
            return cls(source="default_conservative (no fitted file found)", **overrides)
        d = json.loads(p.read_text())
        return cls(
            slip_a=d["a"],
            slip_b=d["b"],
            slip_c=d["c"],
            source=f"fitted:{p} n={d.get('n_fills', '?')} fitted_at={d.get('fitted_at', '?')}",
            **overrides,
        )
