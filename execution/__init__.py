"""Execution: Broker interface, PaperBroker (default), LiveBroker (gated), slippage model.

No order-placement capability is exposed via MCP. Orders go through this package, and live
orders go through ``execution.gate.assert_live_allowed`` first.
"""

from execution.broker import Broker, Fill, Order, OrderStatus, PaperBroker, Position
from execution.gate import LiveTradingBlocked, assert_live_allowed

__all__ = [
    "Broker",
    "Fill",
    "LiveTradingBlocked",
    "Order",
    "OrderStatus",
    "PaperBroker",
    "Position",
    "assert_live_allowed",
]
