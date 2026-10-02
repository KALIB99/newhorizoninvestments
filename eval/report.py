"""Tearsheet schema. The markdown is for humans; the JSON twin is what ``eval.gate`` reads.
Both are written by ``Tearsheet.save`` so they cannot drift apart."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

REPORTS_DIR = Path("research/reports")

Verdict = Literal["Reject", "Insufficient evidence", "Candidate for Judge"]


class StrategySpec(BaseModel):
    """What a module in research/strategies/ must expose as ``STRATEGY``."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    description: str
    rationale: str = Field(description="Why the edge exists, who is on the other side, why not arbitraged")
    signals: list[str] = Field(description="names in signals.registry")
    regimes: list[str] = Field(default_factory=lambda: ["Trend", "Range", "Chaos"])
    timeframe: str = "1m"
    max_holding_bars: int = Field(gt=0)
    params_class: str = Field(description="dotted path to the Params subclass")


class Tearsheet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # identity
    strategy: str
    config_hash: str = Field(min_length=12, max_length=12)
    params: dict
    params_class: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    code_ref: str = Field("", description="git sha of the code that produced this")

    # protocol bookkeeping
    n_trials: int = Field(ge=1, description="every parameter combination evaluated")
    data_start: datetime
    data_end: datetime
    timeframe: str
    symbols: list[str]
    cost_model: dict = Field(description="CostModel.model_dump() used")
    cv: str = Field("purged-kfold → walk-forward 180D/30D", description="split description")

    # headline metrics (OOS, walk-forward, after costs, 1× costs)
    sharpe_oos: float
    sharpe_is: float
    deflated_sharpe: float = Field(description="DSR probability")
    dsr_p_value: float
    pbo: float
    max_drawdown: float = Field(le=0)
    calmar: float
    turnover: float
    cost_drag_bps_per_trade: float
    n_trades_oos: int = Field(ge=0)
    hit_rate: float | None = None
    payoff_ratio: float | None = None

    # robustness
    sharpe_oos_at_1_5x_costs: float
    per_regime_pnl: dict[str, float]
    monthly_pnl: dict[str, float]
    sharpe_by_fold: list[float] = Field(default_factory=list)

    # researcher's own call
    verdict: Verdict
    notes: str = ""

    # ---- io -----------------------------------------------------------------------------
    @property
    def stem(self) -> str:
        return f"{self.strategy}_{self.config_hash}"

    def save(self, directory: Path | str = REPORTS_DIR) -> tuple[Path, Path]:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        json_path = d / f"{self.stem}.json"
        md_path = d / f"{self.stem}.md"
        json_path.write_text(self.model_dump_json(indent=2))
        md_path.write_text(self.to_markdown())
        return md_path, json_path

    @classmethod
    def load(cls, path: Path | str) -> Tearsheet:
        return cls.model_validate_json(Path(path).read_text())

    @classmethod
    def find(cls, strategy: str, directory: Path | str = REPORTS_DIR, config_hash: str | None = None) -> list[Path]:
        d = Path(directory)
        pattern = f"{strategy}_{config_hash or '*'}.json"
        return sorted(d.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)

    def to_markdown(self) -> str:
        reg = "\n".join(f"| {k} | {v:+.2%} |" for k, v in sorted(self.per_regime_pnl.items()))
        months = "\n".join(f"| {k} | {v:+.2%} |" for k, v in sorted(self.monthly_pnl.items()))
        folds = ", ".join(f"{s:.2f}" for s in self.sharpe_by_fold) or "n/a"
        hr = f"{self.hit_rate:.1%}" if self.hit_rate is not None else "n/a"
        pr = f"{self.payoff_ratio:.2f}" if self.payoff_ratio is not None else "n/a"
        return f"""# Tearsheet — {self.strategy} @ {self.config_hash}

Generated {self.generated_at.isoformat()} · code {self.code_ref or "uncommitted"} · params `{self.params_class}`

**Verdict (researcher): {self.verdict}**

## Protocol
- Data: {", ".join(self.symbols)} · {self.timeframe} · {self.data_start.date()} → {self.data_end.date()}
- Splits: {self.cv}
- Trials evaluated (feeds DSR): **{self.n_trials}**
- Cost model: `{json.dumps(self.cost_model, sort_keys=True)}`

## Headline (walk-forward OOS, after costs)
| metric | value |
|---|---|
| Sharpe OOS | {self.sharpe_oos:.2f} |
| Sharpe IS | {self.sharpe_is:.2f} |
| OOS / IS | {self.sharpe_oos / self.sharpe_is if self.sharpe_is else float("nan"):.2f} |
| Deflated Sharpe (prob.) | {self.deflated_sharpe:.3f} |
| DSR p-value | {self.dsr_p_value:.4f} |
| PBO | {self.pbo:.3f} |
| Max drawdown | {self.max_drawdown:.2%} |
| Calmar | {self.calmar:.2f} |
| Turnover / bar | {self.turnover:.4f} |
| Cost drag / trade | {self.cost_drag_bps_per_trade:.1f} bps |
| Trades OOS | {self.n_trades_oos} |
| Hit rate | {hr} |
| Payoff ratio | {pr} |
| Sharpe OOS @ 1.5× costs | {self.sharpe_oos_at_1_5x_costs:.2f} |

Sharpe by walk-forward fold: {folds}

## Per-regime PnL
| regime | PnL |
|---|---|
{reg}

## Monthly PnL
| month | PnL |
|---|---|
{months}

## Notes
{self.notes or "_none_"}

## Params
```json
{json.dumps(self.params, indent=2, sort_keys=True)}
```
"""
