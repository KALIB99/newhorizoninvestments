"""Rule-based fallback (spec §5.1):
realised vol > 90th pct            → Chaos   (takes precedence)
Hurst > 0.55 and ADX > 25          → Trend
Hurst < 0.45                       → Range
otherwise                          → Range   (no edge claimed; directional sleeves idle)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

REGIMES = ("Trend", "Range", "Chaos")


def classify_rules(
    feats: pd.DataFrame,
    hurst_trend: float = 0.55,
    hurst_range: float = 0.45,
    adx_trend: float = 25.0,
    chaos_pct: float = 0.90,
) -> pd.Series:
    trend = (feats["hurst"] > hurst_trend) & (feats["adx"] > adx_trend)
    chaos = feats["rv_pct"] > chaos_pct
    labels = np.where(chaos, "Chaos", np.where(trend, "Trend", "Range"))
    out = pd.Series(labels, index=feats.index, dtype="object")
    warm = feats[["hurst", "adx", "rv_pct"]].isna().any(axis=1)
    out[warm] = None
    return out
