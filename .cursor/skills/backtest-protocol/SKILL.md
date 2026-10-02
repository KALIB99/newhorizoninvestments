---
name: backtest-protocol
description: The only accepted way to backtest a signal or strategy in this firm. Invoke whenever producing performance numbers for anything under research/ or signals/.
---
# Backtest protocol

Follow every step. Skipping one makes the result inadmissible to the Judge.

## 1. Pre-register
- Write the economic rationale (why the edge exists, who is on the other side, why it has
  not been arbitraged away) at the top of `research/strategies/<name>.py` as a docstring.
- Define `Params` as a pydantic model. Decide the parameter grid *before* looking at results.
  Grid size ≤ 50 unless Bayesian optimisation with a logged prior.
- Set `n_trials = 0`. Every evaluation of a parameter combination increments it.

## 2. Data
- `data.load(symbol, tf, start, end, features=[...])`. ≥ 2 full years or all available.
- Confirm the quality report for the dataset has no unresolved gaps in the test period.
- Verify no lookahead: `signals.testing.assert_no_lookahead(signal_fn, df, params)`.

## 3. Costs — non-negotiable
- Build costs with `eval.costs.CostModel` (fees + spread + slippage + funding). Use the
  current fitted slippage coefficients if `execution/reports/slippage_fit.json` exists.
- Also run at 1.5× costs. Record both.

## 4. Splits
- Purged, embargoed k-fold (`eval.cv.PurgedKFold`, embargo = 2× max holding period) for
  parameter selection, on the 60% train / 20% validation portion only.
- Walk-forward (`eval.cv.walk_forward`, 6-month train, 1-month test, rolling) for the
  out-of-sample numbers that go in the tearsheet.
- Regime labels from `regime.classify` on the 1h clock; report PnL per regime.

## 5. Metrics (all of them, every time)
`eval.metrics`: sharpe, deflated_sharpe (with `n_trials`), pbo (CSCV), max_drawdown,
calmar, turnover, cost_drag, trade_count, per-regime PnL, monthly PnL table,
hit rate, payoff ratio.

## 6. Tearsheet
- Build an `eval.report.Tearsheet`, `tearsheet.save("research/reports/")`. This writes
  `<name>_<confighash>.md` and `<name>_<confighash>.json`.
- The config hash is `Params.config_hash()`; the Judge recomputes it from code.
- End with exactly one of: **Reject** / **Insufficient evidence** / **Candidate for Judge**.

## 7. Hand-off
- Move the task to "Awaiting judge" in tasks.md with a link to the tearsheet.
- Run `python -m eval.gate <name>` yourself first; include its output.
