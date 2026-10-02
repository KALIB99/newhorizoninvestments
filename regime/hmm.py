"""3-state Gaussian HMM regime model. Requires the ``research`` extra (hmmlearn).

States are mapped to names by their mean log-realised-vol and Hurst: highest vol → Chaos,
of the remaining two the higher Hurst → Trend, the other → Range. Stability = the fit
converges and no state has < 5% occupancy; otherwise ``classify`` falls back to rules.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from regime.rules import REGIMES

FEATURES = ["log_rv", "vol_of_vol", "hurst", "adx", "abs_funding_z"]


def classify_hmm(feats: pd.DataFrame, n_iter: int = 200, seed: int = 0) -> tuple[pd.Series, bool]:
    from hmmlearn.hmm import GaussianHMM  # ImportError propagates to regime.classify

    X = feats[FEATURES].replace([np.inf, -np.inf], np.nan)
    ok = X.notna().all(axis=1)
    Xv = X[ok]
    if len(Xv) < 500:
        return pd.Series(None, index=feats.index, dtype="object"), False
    Z = (Xv - Xv.mean()) / Xv.std(ddof=1).replace(0, 1.0)
    model = GaussianHMM(n_components=3, covariance_type="full", n_iter=n_iter, random_state=seed)
    model.fit(Z.to_numpy())
    states = model.predict(Z.to_numpy())
    occupancy = np.bincount(states, minlength=3) / len(states)
    stable = bool(model.monitor_.converged and occupancy.min() >= 0.05)

    means = pd.DataFrame(model.means_, columns=FEATURES)
    chaos = int(means["log_rv"].idxmax())
    rest = [s for s in range(3) if s != chaos]
    trend = max(rest, key=lambda s: means.loc[s, "hurst"])
    rng = [s for s in rest if s != trend][0]
    name = {chaos: "Chaos", trend: "Trend", rng: "Range"}
    assert set(name.values()) == set(REGIMES)

    labels = pd.Series(None, index=feats.index, dtype="object")
    labels[ok] = [name[s] for s in states]
    return labels, stable
