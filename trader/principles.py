"""The trader's principles: what good discretionary traders do, minus what humans get wrong.

Every rule below is either a human strength we keep or a human failure mode we make
impossible. The risk-relevant values default to ``risk.limits.RiskLimits`` and are validated
so they can only be *tighter* than the constitution, never looser.

| human failure mode                      | rule that removes it                                   |
|-----------------------------------------|--------------------------------------------------------|
| no stop / moving the stop ("it'll come  | stop is set before entry; stops only ratchet in favour |
|   back")                                |   (engine structural)                                  |
| averaging down a loser                  | one position per symbol, no adds (engine structural)   |
| sizing up after wins (euphoria)         | size = fixed fraction of equity at risk, from equity   |
|                                         |   only; halves in drawdown, never grows past the cap   |
| revenge trading after a loss            | ``cooldown_bars_after_loss`` on that symbol            |
| tilt: a string of losses                | ``max_consecutive_losses_per_day`` → done for the day  |
| overtrading / boredom                   | ``max_trades_per_symbol_per_day``; entries only on     |
|                                         |   pre-defined setups                                   |
| trading small edges that costs eat      | ``min_stop_cost_multiple``: 1R must be ≥ k × round-trip |
| blowing up on one bad day               | daily loss limit → flatten + halt until next UTC day   |
| slow bleed / denial                     | trailing drawdown limit → halt until a human re-enables |
| trading through FOMC/CPI/NFP            | Tier-1 event windows block new risk                    |
|                                         |                                                        |
| human strength we keep                  | rule that encodes it                                   |
| reading the market's character          | regime gate: momentum in Trend, mean reversion in Range |
| stepping aside when it is chaotic       | no directional risk in Chaos                           |
| patience / waiting for the setup        | vol band filter; nothing happens without a trigger     |
| scepticism of "too good" results        | eval.gate plausibility check, DSR, PBO                 |
| stopping when the edge goes away        | walk-forward ¼-Kelly sizing → 0 risk when train edge ≤ 0 |
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from risk.limits import LIMITS


class TraderPrinciples(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    risk_per_trade: float = Field(LIMITS.max_risk_per_trade, gt=0)
    max_gross_exposure: float = Field(LIMITS.max_gross_exposure, gt=0)
    max_net_exposure: float = Field(LIMITS.max_net_exposure, gt=0)
    vol_target_annual: float = Field(LIMITS.vol_target_annual, gt=0)
    daily_loss_limit: float = Field(LIMITS.daily_loss_limit, lt=0)
    trailing_dd_limit: float = Field(LIMITS.trailing_dd_limit, lt=0)
    kelly_fraction: float = Field(LIMITS.kelly_fraction, gt=0)

    drawdown_derisk_at: float = Field(-0.04, lt=0, description="DD from HWM at which risk per trade halves")
    drawdown_derisk_factor: float = Field(0.5, gt=0, le=1)
    max_trades_per_symbol_per_day: int = Field(3, ge=1)
    max_consecutive_losses_per_day: int = Field(4, ge=1)
    cooldown_bars_after_loss: int = Field(4, ge=0)
    min_stop_cost_multiple: float = Field(5.0, ge=1, description="1R ≥ this × round-trip cost or no trade")
    min_fill_fraction: float = Field(0.25, gt=0, le=1, description="skip if risk budget allows < this of intended")
    stop_extra_slippage_spreads: float = Field(1.0, ge=0, description="stop fills pay this many extra spreads")

    @model_validator(mode="after")
    def _never_looser_than_constitution(self) -> TraderPrinciples:
        bad = []
        if self.risk_per_trade > LIMITS.max_risk_per_trade:
            bad.append("risk_per_trade")
        if self.max_gross_exposure > LIMITS.max_gross_exposure:
            bad.append("max_gross_exposure")
        if self.max_net_exposure > LIMITS.max_net_exposure:
            bad.append("max_net_exposure")
        if self.vol_target_annual > LIMITS.vol_target_annual:
            bad.append("vol_target_annual")
        if self.daily_loss_limit < LIMITS.daily_loss_limit:
            bad.append("daily_loss_limit")
        if self.trailing_dd_limit < LIMITS.trailing_dd_limit:
            bad.append("trailing_dd_limit")
        if self.kelly_fraction > LIMITS.kelly_fraction:
            bad.append("kelly_fraction")
        if bad:
            raise ValueError(f"principles may only tighten risk/limits.py; looser: {bad}")
        return self


PRINCIPLES = TraderPrinciples()
