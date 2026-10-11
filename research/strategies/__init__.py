"""Candidate strategies. Empty by design at bootstrap — nothing lands here without a
tearsheet produced under the backtest-protocol skill. CI runs ``eval.gate`` on every file
touched in this directory.

Module contract:

    from signals.base import Params
    from eval.report import StrategySpec

    class CyclicalInversionParams(Params):
        level_lookback: tuple[int, ...] = (48, 96, 168)   # the pre-registered grid lives here
        ...

    STRATEGY = StrategySpec(
        name="cyclical_inversion",
        description=...,
        rationale=...,               # the written economic rationale (research-protocol)
        signals=["sr_inversion"],    # names in signals.registry
        timeframe="1h",
        max_holding_bars=72,
        params_class="research.strategies.cyclical_inversion.CyclicalInversionParams",
    )

Strategies traded through ``trader.engine`` should build on ``research.common`` (data →
MarketData, walk-forward selection, ¼-Kelly sizing, tearsheet) so the protocol is identical
for every candidate. ``cyclical_inversion`` is the reference implementation.
"""
