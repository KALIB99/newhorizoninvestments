"""Signal library.

Every signal is a pure function ``signal(df: pl.DataFrame, params: Params) -> pl.Series``
returning values in [-1, 1]. No I/O inside signals. Register with ``@register("name")``.
"""

from signals.base import Params, SignalFn, clip_unit, get, register, registry

__all__ = ["Params", "SignalFn", "clip_unit", "get", "register", "registry"]
