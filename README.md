# QuantFirm

A crypto day-trading "agent firm" that runs inside Cursor: a Planner → Worker → Judge loop
of subagents, hard risk invariants as rules, and a human-owned capital gate.

Read `AGENTS.md` first. The strategy design is in `docs/strategy-spec.md`. Work is tracked in
`tasks.md`.

Nothing here is a profit guarantee. Most retail algo day-traders lose money. The structure
maximises the chance of finding and keeping an edge; it does not conjure one.

## Layout

```
AGENTS.md                 firm constitution (always loaded by Cursor)
.cursor/rules/            risk-invariants (always), research-protocol, execution-safety
.cursor/agents/           data-engineer, quant-researcher, news-analyst, risk-manager,
                          execution-engineer, judge (read-only), postmortem-analyst
.cursor/skills/           backtest-protocol, promotion-gate
.cursor/mcp.json          read-only data servers; no order placement via MCP
tasks.md                  PWJ queue with DONE conditions
docs/strategy-spec.md     regime gate, carry core, TSMOM, OU-MR, flow, news, sizing, validation
data/        store.py (load), quality.py            research/   strategies/, reports/
signals/     base.py (Params, registry), testing.py  regime/     features, rules, hmm
portfolio/   sizing (vol target, Kelly, combiner)    risk/       limits, kill_switch
execution/   gate (LIVE), broker (Paper/Live), slippage
news/        schema (NewsItem, events, impulse)      eval/       costs, metrics, cv, report, gate
ops/         settings, nightly, schedule, alerts, tasks
```

## Setup

```bash
python3.11 -m venv .venv            # 3.11+; 3.13 works for the core stack
.venv/bin/pip install -e ".[dev]"   # add [research] for hmmlearn/vectorbt, [ops] for prefect
cp .env.example .env                # fill in read-only exchange keys when you need data
make test
.venv/bin/python -m eval.gate --self-test
```

## Day-one prompts (paste into Cursor Agent, in order)

1. **Data** — "Use the data-engineer subagent: build ccxt ingestion for BTC/ETH/SOL perps +
   spot on Binance and Bybit, 1m OHLCV, funding, OI, back to 2023-01-01. Store as parquet,
   expose data.load(), ship a quality report." (tasks.md T-001)
2. **First edge** — "Use the quant-researcher subagent: implement the funding-rate carry
   strategy from docs/strategy-spec.md §5.2 under research-protocol. Log trial count. Produce
   a tearsheet. Then invoke the judge subagent on it." (T-002)
3. **Regime + sleeves** — "quant-researcher: implement the HMM regime classifier (§5.1), then
   TSMOM (§5.3) and OU mean reversion (§5.4) as separate signals. Backtest each gated by
   regime and ungated; report whether gating helps after costs." (T-003, T-004)
4. **News** — "news-analyst: build the feed ingestion and JSON schema, the event calendar, and
   the sentiment impulse. Then hand the impulse series to quant-researcher to test as a
   feature with ridge." (T-005, T-006)
5. **Loop** — "Set up the nightly schedule in ops/ so postmortem-analyst writes hypotheses to
   tasks.md and I get a summary. Everything stays in PaperBroker until I sign
   capital_allocation.yaml." (T-007, T-008; `python -m ops.schedule crontab`)

## The capital key

`execution.LiveBroker` cannot be constructed unless `LIVE_TRADING=1` **and**
`capital_allocation.yaml` is a valid, unexpired, human-signed allocation naming the strategy.
The template shipped here is deliberately invalid. Agents never edit that file.

## MCP

`.cursor/mcp.json` wires: `trader-dev` (pre-existing), a read-only DuckDB server over the
feature store (needs `uvx`), and GitHub for PRs (needs `GITHUB_TOKEN`). Add a news MCP
(CryptoPanic/RSS) when the news-analyst needs it. Never add an exchange trading endpoint.

## What decides whether this makes money

1. The fitted slippage model being honest (`execution/slippage.py` → `eval/costs.py`).
2. The Judge rejecting most things (target > 80%).
3. Carry doing the heavy lifting; directional sleeves adding modest uncorrelated return.
4. You, not the agents, holding the capital key.
