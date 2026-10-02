from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

import polars as pl
from pydantic import BaseModel, ConfigDict


class Params(BaseModel):
    """Base class for all signal/strategy parameter sets.

    Frozen so a parameter set can be hashed; ``extra="forbid"`` so a typo in a config
    fails loudly instead of silently using a default. ``version`` is bumped whenever the
    *meaning* of the parameters changes, so old tearsheets stop matching the code.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = "1"

    def config_hash(self) -> str:
        """12-hex-char digest of the canonical JSON of this parameter set plus class name."""
        payload = {
            "cls": f"{type(self).__module__}.{type(self).__qualname__}",
            "params": self.model_dump(mode="json"),
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(blob).hexdigest()[:12]


SignalFn = Callable[[pl.DataFrame, Params], pl.Series]

registry: dict[str, SignalFn] = {}


def register(name: str) -> Callable[[SignalFn], SignalFn]:
    """Register a signal under ``name``. Names are unique; re-registering is an error."""

    def deco(fn: SignalFn) -> SignalFn:
        if name in registry and registry[name] is not fn:
            raise ValueError(f"signal '{name}' already registered")
        registry[name] = fn
        return fn

    return deco


def get(name: str) -> SignalFn:
    try:
        return registry[name]
    except KeyError as e:
        raise KeyError(f"unknown signal '{name}'. Registered: {sorted(registry)}") from e


def clip_unit(s: pl.Series) -> pl.Series:
    """Clip a signal into [-1, 1], preserving nulls."""
    return s.cast(pl.Float64).clip(-1.0, 1.0)
