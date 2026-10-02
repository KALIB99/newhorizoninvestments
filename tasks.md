# tasks.md — shared ground truth for the Planner → Worker → Judge loop

Conventions:
- IDs are `T-NNN`, monotonically increasing. Never reuse.
- Every task has an owner (a subagent name) and an explicit DONE condition.
- Workers move their task between sections; the Judge writes `JUDGE: <VERDICT> — ...` under it.
- Hypotheses from postmortem-analyst use the form:
  `H: <claim>. Test: <exact backtest>. Decision rule: <metric threshold>. Owner: quant-researcher.`

## Queue
- [ ] T-001 | owner: data-engineer | Build ccxt ingestion for BTC/ETH/SOL perps + spot on Binance and Bybit: 1m OHLCV, funding, OI, back to 2023-01-01. Partitioned parquet under data/store/, `data.load()` wired, quality report shipped.
      DONE: `data.load("BTC/USDT:USDT", "1m", "2023-01-01", <today>)` returns a frame with no unmarked gaps; `data/reports/` contains a quality report per symbol/exchange; tests pass.
- [ ] T-002 | owner: quant-researcher | H: funding-rate carry (short perp / long spot when annualised funding z > 1.5, exit z < 0.5) has positive expectancy after costs on BTC/ETH/SOL (spec §5.2).
      DONE: tearsheet in research/reports/ with DSR p<0.05, PBO<0.3, ≥200 OOS trades, positive at 1.5× costs; `python -m eval.gate funding_carry` exit 0; Judge verdict recorded. Depends on T-001.
- [ ] T-003 | owner: quant-researcher | Implement the HMM regime classifier (spec §5.1) with the rule-based fallback; label 2023→today on the 1h clock.
      DONE: `regime.classify(df)` returns Trend/Range/Chaos with ≥3 regimes present; stability report (label persistence, transition matrix) in research/reports/; tests pass. Depends on T-001.
- [ ] T-004 | owner: quant-researcher | TSMOM (spec §5.3) and OU mean reversion (spec §5.4) as separate signals; backtest each gated by regime and ungated.
      DONE: two tearsheets each, gated vs ungated; a written answer to "does gating help after costs?" with the numbers; Judge verdict recorded. Depends on T-003.
- [ ] T-005 | owner: news-analyst | Feed ingestion + `NewsItem` schema, event calendar with Tier-1 no-trade windows, `sentiment_impulse(symbol, ts)`.
      DONE: `news/store/event_calendar.parquet` exists with FOMC/CPI/NFP for the current year; impulse series saved for BTC/ETH/SOL; latency report (ingested_at − ts) included; handed to quant-researcher as T-006.
- [ ] T-006 | owner: quant-researcher | Test `sentiment_impulse` as a ridge-fitted feature in both directional sleeves (spec §5.6).
      DONE: Sharpe after costs with vs without the feature, on walk-forward OOS; decision: keep feature / keep only hard overrides. Depends on T-004, T-005.
- [ ] T-007 | owner: execution-engineer | PaperBroker fills against recorded L2 (queue-position for makers, book-walk for takers, 50–300 ms jitter); slippage model fitted from paper fills and written to execution/reports/slippage_fit.json.
      DONE: fill-quality report; `eval.costs.CostModel.from_fitted()` loads the coefficients; tests prove slippage grows with size/ADV. Depends on T-001.
- [ ] T-008 | owner: postmortem-analyst | Nightly job wired in ops/ (00:15 UTC postmortem, 00:45 UTC planner summary) writing to tasks.md and ops/reports/.
      DONE: `python -m ops.nightly postmortem` runs end-to-end on a day of paper fills and appends ≥1 well-formed hypothesis here.

## In progress

## Awaiting judge

## Done / Rejected (with reason)
- [x] T-000 | owner: planner | Bootstrap: repo skeleton, AGENTS.md, .mdc rules, subagents, skills, pyproject, CI, eval.gate, risk limits + tests, broker interface + LIVE gate.
      JUDGE: n/a (bootstrap, no strategy claim). Evidence: `make test` green, `python -m eval.gate --self-test` exit 0.
