# Constitution review — "optimise for profit" (2026-10-10)

Requested by the CIO: *fix and optimise for profit; rethink the constitution and make it more
efficient for profit.* This note separates (1) where the profit is actually being lost,
(2) the rules that cost expected profit **without** protecting capital, which should change,
and (3) the rules that look restrictive but are not the problem, which should not.

Nothing in `risk/limits.py` or `.cursor/rules/risk-invariants.mdc` has been changed by this
review. Items marked **needs CIO approval** are proposals; the constitution requires the
human's explicit written approval before any of them lands.

## 1. Where the profit is lost

Six runs of `cyclical_inversion` plus the earlier `disciplined_daytrader` tell the same story.
Back out the cost paid per trade (in R, i.e. as a fraction of the stop distance) and the
signal's *gross* expectancy is zero:

| run | universe / execution | avg R (net) | cost/trade | ≈ cost in R | ≈ gross R |
|---|---|---|---|---|---|
| f6ba4f3a085f | BTC ETH SOL, taker | −0.175 | 14.6 bps | 0.15 | −0.03 |
| ede72ec78a6e | stop 1.0 ATR | −0.17 | 14.6 bps | 0.10 | −0.07 |
| f1f78f878d25 | stop 2.0 ATR | −0.148 | 14.3 bps | 0.07 | −0.08 |
| 72fb5e9b8e1e | 10 other coins | −0.317 | 18.4 bps | 0.18 | −0.14 |
| 6ac762315bd4 | all 13 coins | −0.174 | 17.0 bps | 0.17 | −0.00 |
| 37a81ade45c2 | BTC ETH SOL, **maker** | −0.154 | 11.8 bps | 0.12 | −0.03 |

(T-009's breakout momentum: +0.02–0.06R gross; VWAP mean reversion negative gross.)

The implication is arithmetic, not opinion: a rule change that lets the book take more risk
per trade, more gross, or run longer into a drawdown multiplies a number that is ≤ 0. Loosening
limits cannot make these profitable; it makes them lose faster. The constitution is not what is
losing the money. Costs larger than the gross edge of hourly patterns are — exactly as the
first line of AGENTS.md's priors predicted.

## 2. Rules that cost expected profit without protecting capital — change these

### 2a. The 15% vol target and the −8% sticky trailing-DD halt are inconsistent  **needs CIO approval**

Monte Carlo, i.i.d. daily returns, 4,000 paths, 3 years. Probability that a *genuinely good*
book trips the −8% trailing halt (which is sticky: a human must re-enable):

| Sharpe \ vol target | 5% | 8% | 10% | 15% (current) |
|---|---|---|---|---|
| 0.5 | 37% | 83% | 95% | 100% |
| 1.0 | 17% | 65% | 87% | **100%** (84% in year 1) |
| 1.5 | 7% | 45% | 73% | 99% |
| 2.0 | 2% | 26% | 55% | 96% |

At the current pair the kill switch is not a tail-risk device; it is a certainty. Every real
edge the firm ever finds will be halted in its first year or two and sit idle until someone
re-enables it. That is the single largest structural drag on expected profit in the document.

Consistent pairs (P(trip in 3y) for Sharpe 1.0 / Sharpe 0.7):

| vol target | −10% | −12% | −15% | −20% |
|---|---|---|---|---|
| 8% | 39% / 54% | 22% / 33% | 8% / 16% | 1% / 3% |
| 10% | 65% / 77% | 44% / 57% | **21% / 33%** | 5% / 10% |
| 15% | 96% / 98% | 86% / 93% | 62% / 77% | 28% / 43% |

**Proposed amendment**
- `vol_target_annual` 0.15 → **0.10** (tightens).
- `trailing_dd_limit` −0.08 → **−0.15** as the sticky, human-re-enable halt (loosens the hard stop
  by 7% of capital).
- −8% becomes an automatic tier: risk per trade × 0.5 and an alert (`TraderPrinciples.drawdown_derisk_at`
  already does this at −4%; add a second tier). No human action needed to recover.
- `kelly_fraction` 0.25 unchanged. ¼-Kelly implies vol ≈ Sharpe/4 (25% at Sharpe 1), so 10% is
  still well inside it.
- Daily loss limit −2.5% unchanged: it is a 4.8σ day at 10% vol, a genuine tail stop.

What this trades: the maximum loss before a human must act rises from 8% to 15% of capital.
In exchange, a Sharpe-1 strategy survives 3 years with ~80% probability instead of ~0%.
Alternative if 15% is unacceptable: vol 8% / halt −12% (P ≈ 22% / 33%), at the cost of 20%
lower expected return per unit of edge.

### 2b. The gate's trade-count floor is horizon-blind  **needs CIO approval**

`min_oos_trades = 200` is right for hourly systems and structurally un-promotable for
multi-day ones: funding carry produced +12.8% OOS, max DD −0.38%, DSR p < 0.0001, positive in
all three regimes and at 1.5× costs — and could never pass, with 11–20 trades. Proposal: 200
for strategies on ≤ 4h bars, 100 for ≥ 1d bars / multi-day holds, with the Judge able to rule
on an episode-count exception for carry-type books where each "trade" is weeks of daily
accruals. This changes `eval.gate.GateThresholds`, which is a constitution change.

### 2c. The research budget is pointed at the wrong horizon — **changed (planning, not a limit)**

The constitution calls the firm a "day-trading" firm and then, correctly, says costs decide day
trading. Three families of 1h directional patterns (breakout momentum, VWAP mean reversion,
S/R sweep inversion) have now been tested under the protocol across 13 coins with gross edge
≈ 0. The efficient move is to stop spending trials there. AGENTS.md priors now record this
and T-019 redirects directional research to 4h bars / ≥ 1-day holds, where the cost per unit
of expected move falls 3–5×, and to cross-sectional, market-neutral constructions.

### 2d. Evaluation lost evidence after a halt — **fixed**

The final backtest book honours the sticky halt, so one drawdown event truncated the OOS
series (T-016: 98 trades after an April-2024 halt on a 3-year window). The pipeline now also
reports an *evidence series* without the halt in the diagnostics and notes. The verdict still
uses the halted book — that is what you would have lived through.

### 2e. Taker-only execution — **fixed in the simulator, open in production**

`trader.engine` can now simulate post-only maker entries (fill only if the next bar trades
through the limit). On this signal it cut cost/trade from 14.6 to 11.8 bps and did not change
the verdict, which is the useful negative: the cost lever is worth ~0.03–0.1R per trade and is
not enough on its own for an hourly pattern. It will matter for a signal with real gross edge.
Fitting the real fill probability and adverse selection from L2 (T-007) remains the honest
next step; the simulator's maker model filled 100% of orders, which is optimistic.

## 3. Rules that look restrictive but are not the problem — leave these

- **0.5% risk per trade, 2.0× gross, 1.0× net.** These bound a single bad trade and a
  correlated blow-up. They did bind in the backtests (`shrunk_to_budget` fired 70–75 times),
  but only because tight structural stops imply large notionals; a positive-edge system at a
  10% vol target almost never hits them. Loosening them raises variance, not expectancy.
- **¼-Kelly from training trades.** It sized the losing months *down* (`risk_per_trade` went to
  0 in windows with no training edge). Full Kelly on an estimated edge is how accounts die.
- **The Judge / DSR / PBO / 1.5× cost stress / ≥ 2 of 3 regimes.** Five Rejects in a day feels
  inefficient. It is the opposite: each run cost 30 seconds and zero dollars. The same five
  ideas run live at 15% vol would have cost 5–8% of capital each before the halt. A gate that
  rejects most ideas is working; a gate that passes most ideas is the expensive kind.
- **Behavioural rules in `TraderPrinciples`** (3 trades/symbol/day, 4-bar cooldown, 4 losses →
  done). `skip_cooldown` fired 130–150 times per run. They might cost a little expectancy on a
  good signal; they are not why a zero-edge signal lost. Revisit when there is an edge to
  measure them against.

## 4. What "optimise for profit" means operationally, in order

1. Approve or amend 2a so that an edge, once found, is allowed to compound.
2. Spend the next research trials at horizons where cost ≤ ⅓ of gross edge (T-019), not at 1h.
3. Restore the market-neutral carry sleeve from git history as the ballast the constitution
   already prescribes (AGENTS.md: "market-neutral carry is the ballast; directional signals are
   the overlay, not the core"). It was removed by instruction today; it remains the only
   strategy this firm has produced with positive, cost-robust, all-regime OOS evidence. Its
   blocker is 2b, not performance.
4. Fit real execution costs (T-007) before trusting any hourly result in either direction.
