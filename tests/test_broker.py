"""Broker adapters and the LIVE gate (execution-safety.mdc)."""

from datetime import UTC, datetime, timedelta

import pytest
import yaml

from eval.costs import CostModel
from execution.broker import LiveBroker, Order, OrderStatus, PaperBroker
from execution.gate import LiveTradingBlocked, assert_live_allowed

pytestmark = pytest.mark.execution

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def mk_order(cid="order-0001", side="buy", qty=1.0, max_slip=10.0, typ="market", tif="IOC", **kw):
    return Order(
        client_order_id=cid,
        symbol="BTC/USDT:USDT",
        side=side,
        qty=qty,
        order_type=typ,
        max_slippage_bps=max_slip,
        time_in_force=tif,
        kill_after=timedelta(seconds=30),
        created_at=NOW,
        **kw,
    )


# ---- order schema -----------------------------------------------------------------------
@pytest.mark.parametrize("missing", ["client_order_id", "max_slippage_bps", "time_in_force", "kill_after"])
def test_order_required_fields_have_no_defaults(missing):
    kwargs = dict(
        client_order_id="order-0001",
        symbol="BTC/USDT:USDT",
        side="buy",
        qty=1.0,
        max_slippage_bps=5.0,
        time_in_force="IOC",
        kill_after=timedelta(seconds=10),
    )
    kwargs.pop(missing)
    with pytest.raises(Exception):
        Order(**kwargs)


# ---- paper broker -----------------------------------------------------------------------
def test_paper_fill_records_realised_slippage_and_fee():
    b = PaperBroker(cash_usd=10_000, costs=CostModel(), seed=1)
    st = b.place(mk_order(), mark=100.0, spread_bps=2.0, now=NOW)
    assert st == OrderStatus.FILLED
    f = next(b.fills())
    assert f.price > 100.0  # buyer pays up
    assert f.realised_slippage_bps > 0
    assert 50 <= f.latency_ms <= 300
    assert b.positions()["BTC/USDT:USDT"].qty == 1.0
    assert b.balances()["USD"] < 10_000  # fee charged


def test_paper_rejects_when_modelled_slippage_exceeds_max():
    b = PaperBroker(costs=CostModel(), seed=1)
    st = b.place(mk_order(max_slip=0.5), mark=100.0, spread_bps=2.0, now=NOW)
    assert st == OrderStatus.REJECTED
    assert b.positions() == {}


def test_paper_slippage_grows_with_size_over_adv():
    b = PaperBroker(costs=CostModel(), seed=1)
    b.place(mk_order("a" * 8, qty=1.0, max_slip=1000), mark=100.0, adv=1e9, now=NOW)
    b.place(mk_order("b" * 8, qty=1.0, max_slip=1000), mark=100.0, adv=1e3, now=NOW)
    small, big = list(b.fills())
    assert big.realised_slippage_bps > small.realised_slippage_bps


def test_paper_idempotent_client_order_id():
    b = PaperBroker(seed=1)
    o = mk_order()
    b.place(o, mark=100.0, now=NOW)
    b.place(o, mark=100.0, now=NOW)
    assert len(list(b.fills())) == 1


def test_paper_kill_after_expires_stale_order():
    b = PaperBroker(seed=1)
    st = b.place(mk_order(), mark=100.0, now=NOW + timedelta(seconds=31))
    assert st == OrderStatus.EXPIRED
    assert b.positions() == {}


def test_paper_round_trip_pnl_and_flat():
    b = PaperBroker(
        cash_usd=10_000, costs=CostModel(taker_fee_bps=0, spread_bps=0, slip_a=0, slip_b=0, slip_c=0), seed=1
    )
    b.place(mk_order("buy00001", "buy", 2.0, max_slip=1), mark=100.0, now=NOW)
    b.place(mk_order("sell0001", "sell", 2.0, max_slip=1), mark=110.0, now=NOW)
    assert b.positions() == {}
    assert b.balances()["USD"] == pytest.approx(10_000 + 20.0)


def test_paper_passive_limit_rests_and_can_be_cancelled():
    b = PaperBroker(seed=1)
    st = b.place(mk_order(typ="limit", tif="GTC", max_slip=50, limit_price=99.0), mark=100.0, now=NOW)
    assert st == OrderStatus.NEW
    assert b.cancel_all() == 1
    assert b.status("order-0001") == OrderStatus.CANCELLED


# ---- live gate ----------------------------------------------------------------------------
def _signed(tmp_path, **over):
    d = {
        "version": 1,
        "signed_by": "CIO",
        "signed_at": "2025-12-01T00:00:00+00:00",
        "signature": "abcdefgh12345678",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "allocations": [
            {
                "strategy": "funding_carry",
                "exchange": "binance",
                "capital_usd": 5000,
                "max_fraction_of_target": 0.10,
                "evidence": ["research/reports/x.md"],
            }
        ],
    }
    d.update(over)
    p = tmp_path / "capital_allocation.yaml"
    p.write_text(yaml.safe_dump(d))
    return p


def test_gate_blocks_without_env(tmp_path):
    p = _signed(tmp_path)
    with pytest.raises(LiveTradingBlocked, match="LIVE_TRADING"):
        assert_live_allowed(path=p, now=NOW)


def test_gate_blocks_shipped_template_even_with_env(monkeypatch, repo_root):
    monkeypatch.setenv("LIVE_TRADING", "1")
    with pytest.raises(LiveTradingBlocked):
        assert_live_allowed(path=repo_root / "capital_allocation.yaml", now=NOW)


def test_gate_blocks_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVE_TRADING", "1")
    with pytest.raises(LiveTradingBlocked, match="does not exist"):
        assert_live_allowed(path=tmp_path / "nope.yaml", now=NOW)


@pytest.mark.parametrize(
    "bad",
    [
        {"signature": ""},
        {"signed_by": ""},
        {"allocations": []},
        {"expires_at": "2025-12-31T00:00:00+00:00"},  # expired
        {"signed_at": "2026-02-01T00:00:00+00:00"},  # signed in the future
        {"signed_at": "2025-12-01T00:00:00"},  # naive timestamp
    ],
)
def test_gate_blocks_invalid_or_unsigned(monkeypatch, tmp_path, bad):
    monkeypatch.setenv("LIVE_TRADING", "1")
    p = _signed(tmp_path, **bad)
    with pytest.raises(LiveTradingBlocked):
        assert_live_allowed(path=p, now=NOW)


def test_gate_blocks_allocation_over_10pct(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVE_TRADING", "1")
    p = _signed(
        tmp_path,
        allocations=[
            {
                "strategy": "x",
                "exchange": "binance",
                "capital_usd": 1,
                "max_fraction_of_target": 0.11,
                "evidence": ["e"],
            }
        ],
    )
    with pytest.raises(LiveTradingBlocked):
        assert_live_allowed(path=p, now=NOW)


def test_gate_blocks_unlisted_strategy_but_passes_listed(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVE_TRADING", "1")
    p = _signed(tmp_path)
    with pytest.raises(LiveTradingBlocked, match="no signed allocation"):
        assert_live_allowed("tsmom", path=p, now=NOW)
    alloc = assert_live_allowed("funding_carry", path=p, now=NOW)
    assert alloc.signed_by == "CIO"


def test_env_must_be_exactly_1(monkeypatch, tmp_path):
    p = _signed(tmp_path)
    for v in ("true", "yes", "1 ", "01"):
        monkeypatch.setenv("LIVE_TRADING", v)
        with pytest.raises(LiveTradingBlocked):
            assert_live_allowed(path=p, now=NOW)


def test_live_broker_cannot_be_constructed_without_gate(tmp_path):
    with pytest.raises(LiveTradingBlocked):
        LiveBroker("binance", allocation_path=str(tmp_path / "missing.yaml"))


def test_live_broker_constructs_with_gate_but_does_not_touch_network(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVE_TRADING", "1")
    p = _signed(tmp_path)
    b = LiveBroker("binance", strategy="funding_carry", allocation_path=str(p))
    assert b.paper is False and b.allocation.version == 1
