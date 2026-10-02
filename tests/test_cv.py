import numpy as np
import pandas as pd
import pytest

from eval.cv import PurgedKFold, train_val_test_split, walk_forward


def test_purged_kfold_embargo_removes_bars_after_test():
    pk = PurgedKFold(n_splits=4, embargo=5)
    splits = list(pk.split(100))
    assert len(splits) == 4
    train, test = splits[0]  # test = 0..24
    assert test[0] == 0 and test[-1] == 24
    assert not set(range(25, 30)) & set(train)  # embargoed
    assert 30 in train
    assert not set(test) & set(train)


def test_purged_kfold_purges_overlapping_labels():
    # every label resolves 10 bars later
    t1 = np.arange(100) + 10
    pk = PurgedKFold(n_splits=4, embargo=0)
    train, test = list(pk.split(100, t1=t1))[1]  # test = 25..49
    # samples 15..24 have t1 in the test window → purged
    assert not set(range(15, 25)) & set(train)
    assert 14 in train


def test_purged_kfold_validation():
    with pytest.raises(ValueError):
        PurgedKFold(n_splits=1)
    with pytest.raises(ValueError):
        list(PurgedKFold(3).split(10, t1=np.arange(5)))


def test_train_val_test_is_chronological_60_20_20():
    a, b, c = train_val_test_split(100)
    assert (len(a), len(b), len(c)) == (60, 20, 20)
    assert a[-1] < b[0] < b[-1] < c[0]


def test_walk_forward_rolls_6m_train_1m_test_no_overlap():
    idx = pd.date_range("2024-01-01", "2025-01-01", freq="h", tz="UTC")
    folds = list(walk_forward(idx, "180D", "30D"))
    assert len(folds) >= 5
    for tr, te in folds:
        assert tr[-1] < te[0]
        assert (idx[te[-1]] - idx[te[0]]) <= pd.Timedelta("30D")
        assert (idx[tr[-1]] - idx[tr[0]]) <= pd.Timedelta("180D")
    # consecutive test folds are contiguous
    for (_, a), (_, b) in zip(folds, folds[1:], strict=False):
        assert b[0] == a[-1] + 1


def test_walk_forward_embargo_and_anchored():
    idx = pd.date_range("2024-01-01", "2025-01-01", freq="h", tz="UTC")
    tr, te = next(walk_forward(idx, "180D", "30D", embargo="2D"))
    assert idx[te[0]] - idx[tr[-1]] >= pd.Timedelta("2D")
    anchored = list(walk_forward(idx, "180D", "30D", anchored=True))
    assert anchored[-1][0][0] == 0
