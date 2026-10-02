"""Broker interface, PaperBroker (default) and LiveBroker (gated).

The PaperBroker here is the bootstrap version: it fills at mark ± half-spread plus modelled
slippage, enforces ``max_slippage_bps``, idempotency and kill-after, and records realised
slippage per fill. T-007 replaces the fill engine with recorded-L2 queue/book-walk
simulation; the interface does not change.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from eval.costs import CostModel
from execution.gate import ALLOCATION_PATH, CapitalAllocation, assert_live_allowed


class OrderStatus(StrEnum):
    NEW = "new"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Order(BaseModel):
    """Every field without a default is required by execution-safety.mdc. Do not add defaults
    to client_order_id, max_slippage_bps, time_in_force or kill_after."""

    model_config = ConfigDict(frozen=True)

    client_order_id: str = Field(min_length=8, description="idempotency key; resubmitting is a no-op")
    symbol: str
    side: Literal["buy", "sell"]
    qty: float = Field(gt=0)
    order_type: Literal["market", "limit", "post_only"] = "market"
    limit_price: float | None = None
    max_slippage_bps: float = Field(ge=0, description="reject the fill if modelled/realised slippage exceeds this")
    time_in_force: Literal["GTC", "IOC", "FOK", "PO"]
    kill_after: timedelta = Field(description="cancel if not filled within this; required")
    strategy: str = "unattributed"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def signed_qty(self) -> float:
        return self.qty if self.side == "buy" else -self.qty


class Fill(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    qty: float
    price: float
    fee_usd: float
    ts: datetime
    mark_at_submit: float
    realised_slippage_bps: float
    latency_ms: float
    strategy: str
    paper: bool


class Position(BaseModel):
    symbol: str
    qty: float = 0.0
    avg_price: float = 0.0
    realised_pnl: float = 0.0


class Broker(ABC):
    paper: bool

    @abstractmethod
    def place(
        self, order: Order, *, mark: float, spread_bps: float | None = None, adv: float | None = None
    ) -> OrderStatus: ...

    @abstractmethod
    def cancel(self, client_order_id: str) -> bool: ...

    @abstractmethod
    def replace(self, client_order_id: str, new_order: Order, **kw: object) -> OrderStatus: ...

    @abstractmethod
    def positions(self) -> dict[str, Position]: ...

    @abstractmethod
    def balances(self) -> dict[str, float]: ...

    @abstractmethod
    def fills(self) -> Iterator[Fill]: ...

    def cancel_all(self) -> int:
        return 0


class PaperBroker(Broker):
    paper = True

    def __init__(
        self,
        cash_usd: float = 100_000.0,
        costs: CostModel | None = None,
        latency_ms: tuple[float, float] = (50.0, 300.0),
        seed: int | None = None,
    ) -> None:
        self.cash = cash_usd
        self.costs = costs or CostModel.from_fitted()
        self.latency_ms = latency_ms
        self._rng = random.Random(seed)  # noqa: S311 - simulation jitter, not security
        self._positions: dict[str, Position] = {}
        self._fills: list[Fill] = []
        self._orders: dict[str, OrderStatus] = {}
        self._open: dict[str, Order] = {}

    # ---- interface ----------------------------------------------------------------------
    def place(
        self,
        order: Order,
        *,
        mark: float,
        spread_bps: float | None = None,
        adv: float | None = None,
        now: datetime | None = None,
    ) -> OrderStatus:
        now = now or datetime.now(UTC)
        if order.client_order_id in self._orders:
            logger.debug("duplicate client_order_id {} ignored", order.client_order_id)
            return self._orders[order.client_order_id]
        if now - order.created_at > order.kill_after:
            return self._set(order, OrderStatus.EXPIRED)

        spread = self.costs.spread_bps if spread_bps is None else spread_bps
        size_adv = (order.qty * mark / adv) if adv else 0.0
        taker = order.order_type == "market" or order.time_in_force in ("IOC", "FOK")
        slip_bps = float(self.costs.slippage_bps(size_adv, spread)) * (1.0 if taker else 0.25)
        half_spread_bps = spread / 2.0 if taker else 0.0
        adverse_bps = half_spread_bps + slip_bps
        if adverse_bps > order.max_slippage_bps:
            logger.warning(
                "paper reject {}: modelled slippage {:.1f}bps > max {:.1f}",
                order.client_order_id,
                adverse_bps,
                order.max_slippage_bps,
            )
            return self._set(order, OrderStatus.REJECTED)

        sign = 1.0 if order.side == "buy" else -1.0
        px = mark * (1.0 + sign * adverse_bps / 1e4)
        if order.order_type != "market" and order.limit_price is not None:
            if (order.side == "buy" and px > order.limit_price) or (order.side == "sell" and px < order.limit_price):
                self._open[order.client_order_id] = order
                return self._set(order, OrderStatus.NEW)
        fee_bps = self.costs.taker_fee_bps if taker else self.costs.maker_fee_bps
        fee = order.qty * px * fee_bps / 1e4
        latency = self._rng.uniform(*self.latency_ms)
        fill = Fill(
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            qty=order.qty,
            price=px,
            fee_usd=fee,
            ts=now + timedelta(milliseconds=latency),
            mark_at_submit=mark,
            realised_slippage_bps=sign * (px / mark - 1.0) * 1e4,
            latency_ms=latency,
            strategy=order.strategy,
            paper=True,
        )
        self._apply(fill)
        return self._set(order, OrderStatus.FILLED)

    def cancel(self, client_order_id: str) -> bool:
        if client_order_id in self._open:
            del self._open[client_order_id]
            self._orders[client_order_id] = OrderStatus.CANCELLED
            return True
        return False

    def replace(self, client_order_id: str, new_order: Order, **kw: object) -> OrderStatus:
        self.cancel(client_order_id)
        return self.place(new_order, **kw)  # type: ignore[arg-type]

    def cancel_all(self) -> int:
        n = len(self._open)
        for cid in list(self._open):
            self.cancel(cid)
        return n

    def positions(self) -> dict[str, Position]:
        return {k: v.model_copy() for k, v in self._positions.items() if abs(v.qty) > 1e-12}

    def balances(self) -> dict[str, float]:
        return {"USD": self.cash}

    def fills(self) -> Iterator[Fill]:
        yield from self._fills

    def status(self, client_order_id: str) -> OrderStatus | None:
        return self._orders.get(client_order_id)

    # ---- internals ----------------------------------------------------------------------
    def _set(self, order: Order, st: OrderStatus) -> OrderStatus:
        self._orders[order.client_order_id] = st
        return st

    def _apply(self, fill: Fill) -> None:
        pos = self._positions.setdefault(fill.symbol, Position(symbol=fill.symbol))
        signed = fill.qty if fill.side == "buy" else -fill.qty
        if pos.qty == 0 or (pos.qty > 0) == (signed > 0):
            new_qty = pos.qty + signed
            pos.avg_price = (pos.avg_price * abs(pos.qty) + fill.price * abs(signed)) / abs(new_qty)
            pos.qty = new_qty
        else:
            closed = min(abs(pos.qty), abs(signed))
            pnl = closed * (fill.price - pos.avg_price) * (1 if pos.qty > 0 else -1)
            pos.realised_pnl += pnl
            self.cash += pnl
            pos.qty += signed
            if abs(pos.qty) < 1e-12:
                pos.qty, pos.avg_price = 0.0, 0.0
            elif (pos.qty > 0) == (signed > 0):
                pos.avg_price = fill.price
        self.cash -= fill.fee_usd
        self._fills.append(fill)


class LiveBroker(Broker):
    """ccxt-backed broker. Constructing one without the gate is impossible by design: the
    assertion is the first statement of ``__init__`` and there is no alternative constructor."""

    paper = False

    def __init__(
        self,
        exchange_id: str,
        strategy: str | None = None,
        allocation_path: str = str(ALLOCATION_PATH),
        **ccxt_kwargs: object,
    ) -> None:
        self.allocation: CapitalAllocation = assert_live_allowed(strategy, allocation_path)
        import ccxt  # local import: paper runs never need it

        cls = getattr(ccxt, exchange_id)
        self.exchange = cls({"enableRateLimit": True, **ccxt_kwargs})
        self.exchange_id = exchange_id
        logger.warning(
            "LiveBroker({}) constructed under allocation v{} signed by {}",
            exchange_id,
            self.allocation.version,
            self.allocation.signed_by,
        )

    def place(
        self, order: Order, *, mark: float, spread_bps: float | None = None, adv: float | None = None
    ) -> OrderStatus:
        params = {"clientOrderId": order.client_order_id, "timeInForce": order.time_in_force}
        if order.order_type == "post_only":
            params["postOnly"] = True
        typ = "market" if order.order_type == "market" else "limit"
        self.exchange.create_order(order.symbol, typ, order.side, order.qty, order.limit_price, params)
        return OrderStatus.NEW

    def cancel(self, client_order_id: str) -> bool:
        raise NotImplementedError("T-007: implement with reconciliation loop and backoff")

    def replace(self, client_order_id: str, new_order: Order, **kw: object) -> OrderStatus:
        raise NotImplementedError("T-007")

    def positions(self) -> dict[str, Position]:
        raise NotImplementedError("T-007")

    def balances(self) -> dict[str, float]:
        raise NotImplementedError("T-007")

    def fills(self) -> Iterator[Fill]:
        raise NotImplementedError("T-007")
