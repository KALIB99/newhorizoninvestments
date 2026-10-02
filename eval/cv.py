"""Purged, embargoed k-fold and walk-forward splitters (López de Prado, AFML ch. 7).

Both operate on positional indices into a time-ordered frame. ``PurgedKFold`` is for
parameter selection on the train/validation portion; ``walk_forward`` produces the
out-of-sample numbers that go in the tearsheet.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pandas as pd


class PurgedKFold:
    """K-fold where training samples whose label window overlaps the test fold are purged,
    and an embargo of ``embargo`` bars after each test fold is dropped from training.

    Parameters
    ----------
    n_splits : number of contiguous test folds.
    embargo : bars to drop after each test fold (research-protocol: 2× max holding period).
    """

    def __init__(self, n_splits: int = 5, embargo: int = 0) -> None:
        if n_splits < 2:
            raise ValueError("n_splits must be >= 2")
        if embargo < 0:
            raise ValueError("embargo must be >= 0")
        self.n_splits = n_splits
        self.embargo = embargo

    def split(self, n_samples: int, t1: np.ndarray | None = None) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        """Yield (train_idx, test_idx).

        ``t1[i]`` is the positional index at which sample ``i``'s label is resolved (the bar
        the trade exits). Defaults to ``i`` (labels resolve at the same bar), in which case
        purging reduces to the embargo.
        """
        idx = np.arange(n_samples)
        if t1 is None:
            t1 = idx.copy()
        t1 = np.asarray(t1)
        if len(t1) != n_samples:
            raise ValueError("t1 must have one entry per sample")
        folds = np.array_split(idx, self.n_splits)
        for test in folds:
            test_start, test_end = int(test[0]), int(test[-1])
            # purge: any train sample whose label window [i, t1[i]] touches the test window
            overlaps = (idx <= test_end) & (t1 >= test_start)
            # embargo: bars right after the test window
            embargoed = (idx > test_end) & (idx <= test_end + self.embargo)
            train = idx[~overlaps & ~embargoed]
            yield train, test


def train_val_test_split(
    n_samples: int, train: float = 0.6, val: float = 0.2
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Chronological 60/20/20 split by default (research-protocol)."""
    if not 0 < train < 1 or not 0 <= val < 1 or train + val >= 1:
        raise ValueError("fractions must satisfy 0 < train, 0 <= val, train + val < 1")
    idx = np.arange(n_samples)
    a = int(n_samples * train)
    b = int(n_samples * (train + val))
    return idx[:a], idx[a:b], idx[b:]


def walk_forward(
    index: pd.DatetimeIndex,
    train: str | pd.Timedelta = "180D",
    test: str | pd.Timedelta = "30D",
    embargo: str | pd.Timedelta = "0D",
    anchored: bool = False,
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Rolling (or anchored) walk-forward on a UTC DatetimeIndex.

    Default is the firm's 6-month train / 1-month test roll. Yields positional indices.
    """
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError("walk_forward needs a DatetimeIndex")
    if not index.is_monotonic_increasing:
        raise ValueError("index must be sorted")
    train_td, test_td, emb_td = pd.Timedelta(train), pd.Timedelta(test), pd.Timedelta(embargo)
    start, end = index[0], index[-1]
    pos = np.arange(len(index))
    test_start = start + train_td
    while test_start + test_td <= end + pd.Timedelta(seconds=1):
        train_lo = start if anchored else test_start - train_td
        train_hi = test_start - emb_td
        tr = pos[(index >= train_lo) & (index < train_hi)]
        te = pos[(index >= test_start) & (index < test_start + test_td)]
        if len(tr) and len(te):
            yield tr, te
        test_start = test_start + test_td
