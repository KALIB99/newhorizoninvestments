"""Candidate strategies. Empty by design at bootstrap — nothing lands here without a
tearsheet produced under the backtest-protocol skill. CI runs ``eval.gate`` on every file
touched in this directory.

Module contract:

    from signals.base import Params
    from eval.report import StrategySpec

    class FundingCarryParams(Params):
        entry_z: float = 1.5
        exit_z: float = 0.5
        ...

    STRATEGY = StrategySpec(
        name="funding_carry",
        description=...,
        rationale=...,            # the written economic rationale (research-protocol)
        signals=["funding_z"],    # names in signals.registry
        timeframe="1h",
        max_holding_bars=24 * 7,
        params_class="research.strategies.funding_carry.FundingCarryParams",
    )
"""
