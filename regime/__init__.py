"""Regime layer (spec §5.1): Trend / Range / Chaos on the 1h clock.

``classify`` uses the 3-state Gaussian HMM when ``hmmlearn`` is installed and the fit is
stable; otherwise the rule-based fallback. Both return the same labels.
"""

from regime.features import adx, garman_klass_vol, hurst_exponent, regime_features
from regime.rules import REGIMES, classify_rules

__all__ = ["REGIMES", "adx", "classify", "classify_rules", "garman_klass_vol", "hurst_exponent", "regime_features"]


def classify(df, method: str = "auto"):  # noqa: ANN001 - pandas DataFrame with ohlc + optional funding_z
    """Return a pd.Series of regime labels aligned to ``df``.

    method: "rules" | "hmm" | "auto" (hmm if available and stable, else rules).
    """
    feats = regime_features(df)
    if method == "rules":
        return classify_rules(feats)
    try:
        from regime.hmm import classify_hmm

        labels, stable = classify_hmm(feats)
        if method == "hmm" or stable:
            return labels
    except ImportError:
        if method == "hmm":
            raise
    return classify_rules(feats)
