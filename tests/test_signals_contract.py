"""Signal contract: Params hashing, registry, shape/range checks, lookahead detection."""

import polars as pl
import pytest

from signals.base import Params, clip_unit, get, register, registry
from signals.testing import (
    SignalContractError,
    assert_no_lookahead,
    assert_signal_contract,
    synthetic_ohlcv,
)


class P(Params):
    window: int = 20


def good_signal(df: pl.DataFrame, params: P) -> pl.Series:
    # rolling z-score of returns, backward looking
    r = df["close"].log().diff()
    z = (r - r.rolling_mean(params.window)) / r.rolling_std(params.window)
    return clip_unit(z / 3.0)


def lookahead_signal(df: pl.DataFrame, params: P) -> pl.Series:
    r = df["close"].log().diff()
    return clip_unit(r.shift(-1) * 100)  # peeks one bar ahead


def global_norm_signal(df: pl.DataFrame, params: P) -> pl.Series:
    r = df["close"].log().diff()
    return clip_unit((r - r.mean()) / r.std())  # full-sample normalisation = subtle lookahead


def test_params_hash_is_stable_and_sensitive():
    assert P().config_hash() == P().config_hash()
    assert P(window=21).config_hash() != P().config_hash()
    assert len(P().config_hash()) == 12


def test_params_frozen_and_strict():
    with pytest.raises(Exception):
        P(windw=3)  # typo must fail
    p = P()
    with pytest.raises(Exception):
        p.window = 5


def test_registry_roundtrip():
    registry.pop("_t_good", None)
    register("_t_good")(good_signal)
    assert get("_t_good") is good_signal
    with pytest.raises(ValueError):
        register("_t_good")(lookahead_signal)
    with pytest.raises(KeyError):
        get("_t_missing")
    registry.pop("_t_good")


def test_good_signal_passes_contract_and_lookahead():
    df = synthetic_ohlcv(600)
    s = assert_signal_contract(good_signal, df, P())
    assert len(s) == df.height
    assert_no_lookahead(good_signal, df, P())


def test_shift_minus_one_is_detected():
    df = synthetic_ohlcv(600)
    with pytest.raises(SignalContractError, match="lookahead"):
        assert_no_lookahead(lookahead_signal, df, P())


def test_full_sample_normalisation_is_detected():
    df = synthetic_ohlcv(600)
    with pytest.raises(SignalContractError, match="lookahead"):
        assert_no_lookahead(global_norm_signal, df, P())


def test_contract_rejects_out_of_range_and_wrong_length():
    df = synthetic_ohlcv(100)
    with pytest.raises(SignalContractError, match=r"outside \[-1, 1\]"):
        assert_signal_contract(lambda d, p: d["close"].log().diff() * 1e6 + 5.0, df, P())
    with pytest.raises(SignalContractError, match="length"):
        assert_signal_contract(lambda d, p: pl.Series([0.1, 0.2]), df, P())
