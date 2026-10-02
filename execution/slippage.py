"""Slippage model: slippage_bps ~ a + b·sqrt(size/ADV) + c·spread_bps.

Fitted from paper/live fills by the execution-engineer and saved to
execution/reports/slippage_fit.json, from where ``eval.costs.CostModel.from_fitted`` reads
it. This is the single most important honesty link in the firm.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from eval.costs import FITTED_PATH


class SlippageModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    a: float = Field(ge=0)
    b: float = Field(ge=0)
    c: float = Field(ge=0)
    n_fills: int = 0
    r2: float = float("nan")
    fitted_at: datetime | None = None

    def predict(self, size_adv: np.ndarray | float, spread_bps: np.ndarray | float) -> np.ndarray:
        size_adv = np.asarray(size_adv, dtype=float)
        return self.a + self.b * np.sqrt(np.clip(size_adv, 0, None)) + self.c * np.asarray(spread_bps, dtype=float)

    @classmethod
    def fit(cls, fills: pd.DataFrame, min_fills: int = 100) -> SlippageModel:
        """``fills`` needs columns: size_adv, spread_bps, realised_slippage_bps.
        Non-negative least squares via clipping so a pathological sample cannot produce a
        negative (i.e. optimistic) coefficient."""
        req = {"size_adv", "spread_bps", "realised_slippage_bps"}
        if not req <= set(fills.columns):
            raise ValueError(f"fills must have columns {sorted(req)}")
        f = fills.dropna(subset=list(req))
        if len(f) < min_fills:
            raise ValueError(f"need >= {min_fills} fills to fit slippage; have {len(f)}")
        X = np.column_stack([np.ones(len(f)), np.sqrt(f["size_adv"].clip(lower=0)), f["spread_bps"]])
        y = f["realised_slippage_bps"].to_numpy()
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        coef = np.clip(coef, 0, None)
        pred = X @ coef
        ss_res = float(((y - pred) ** 2).sum())
        ss_tot = float(((y - y.mean()) ** 2).sum()) or 1.0
        return cls(a=coef[0], b=coef[1], c=coef[2], n_fills=len(f), r2=1 - ss_res / ss_tot, fitted_at=datetime.now(UTC))

    def save(self, path: Path | str = FITTED_PATH) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.model_dump(mode="json"), indent=2))
        return p

    @classmethod
    def load(cls, path: Path | str = FITTED_PATH) -> SlippageModel:
        return cls.model_validate_json(Path(path).read_text())


def fill_quality(fills: pd.DataFrame, model: SlippageModel) -> dict[str, float]:
    """Realised vs modelled cost summary for the fill-quality report. The paper→live
    promotion rule is |realised/modelled − 1| ≤ 0.30."""
    pred = model.predict(fills["size_adv"].to_numpy(), fills["spread_bps"].to_numpy())
    real = fills["realised_slippage_bps"].to_numpy()
    ratio = float(real.mean() / pred.mean()) if pred.mean() else float("nan")
    return {
        "n_fills": int(len(fills)),
        "realised_mean_bps": float(real.mean()),
        "modelled_mean_bps": float(pred.mean()),
        "realised_over_modelled": ratio,
        "within_30pct": bool(abs(ratio - 1.0) <= 0.30),
    }
