# Hybrid strategy specification

This is the firm's target architecture. Every sleeve below is a hypothesis until it passes
the Judge and `eval.gate`. Nothing here is implemented until the corresponding task in
`tasks.md` is Done.

## 5.1 Regime layer (the gate)

Classify each bar on a 1h clock into **Trend / Range / Chaos** using a 3-state Gaussian HMM
on features:

- log realised vol (Garman-Klass, 24h)
- vol-of-vol
- Hurst exponent (rolling 256 bars)
- ADX(14)
- |funding z-score|

Fallback rule set if the HMM is unstable (`regime.rules.classify_rules`):

- Hurst > 0.55 and ADX > 25 → Trend
- Hurst < 0.45 → Range
- realised vol > 90th percentile → Chaos (takes precedence)

Chaos → gross exposure × 0.3, directional signals off, carry only.

## 5.2 Core: market-neutral carry (ballast, ~40–50% of risk)

- **Funding harvest**: short perp / long spot when annualised funding z-score > 1.5 (and
  vice versa where shorting spot is possible). Exit at z < 0.5. Hedge ratio = 1, rebalance
  deltas when |Δ| > 2%.
- **Cross-exchange funding spread**: long perp on exchange A, short on B when funding spread
  > fees × 3.
- Edge is ~5–15% annualised at low vol; it pays for the directional sleeve's variance.

## 5.3 Directional sleeve A — time-series momentum (Trend regime)

- Signal: ensemble of normalised returns, `s_mom = mean_k(r_k / σ_k)` for
  k ∈ {1h, 4h, 12h, 24h}, clipped to [-1, 1].
- Entry filter: price beyond 20-bar Donchian high/low AND vol percentile in 30–85.
- Exit: trailing stop at 2.5 × ATR(14) or signal sign flip.
- Expected: hit rate 35–45%, payoff ratio > 2. **Judge rejects if payoff < 1.5.**

## 5.4 Directional sleeve B — mean reversion (Range regime)

- Model deviation from 1h VWAP as an OU process; estimate half-life θ via AR(1) on 5m bars.
  **Reject if half-life < 10 min or > 6h.**
- Signal: `s_mr = -z` where `z = (price − VWAP) / σ_resid`; active when |z| > 2, exit at
  |z| < 0.5, hard stop at |z| > 3.5.
- Confirmation: orderbook imbalance (bid−ask depth / total, top 10) must agree in sign;
  otherwise half size.

## 5.5 Flow overlay — liquidation / positioning (all regimes, small)

- Quadrant: ΔOI > 0 & Δp > 0 → new longs (crowding); ΔOI < 0 & Δp < 0 → long liquidations.
- Fade crowded extremes: when funding z > 2 and OI 24h change > 15%, scale momentum longs
  by 0.5 and allow mean-reversion shorts earlier (|z| > 1.5).

## 5.6 News layer

- `sentiment_impulse` added as a feature to both sleeves with coefficient fitted by ridge on
  OOS data (expect small, < 15% of signal weight).
- Hard overrides from news-analyst: no-trade windows, exchange-risk gross cut, asset flatten
  on hack/depeg.
- Evaluate separately: does the news layer improve Sharpe after costs? If not, keep only the
  hard overrides.

## 5.7 Combination & sizing

- Each sleeve → vol-targeted position `w_i = s_i × (σ_target / σ_i)`.
- Portfolio weights: inverse-variance shrunk to equal weight (λ = 0.5); correlation cap 0.7.
- Final sizing × 0.25 Kelly multiplier derived from the OOS trade distribution; × regime
  multiplier (Trend 1.0, Range 0.8, Chaos 0.3).
- Target 10% annualised portfolio vol (amended from 15% on 2026-10-10, T-018: the old target
  was inconsistent with the -8% halt). Realistic goal after costs: Sharpe 1.0–1.5,
  max DD 8–12%; the -8% tier halves risk, the -15% halt is the hard stop. **Anything
  backtesting > 3 Sharpe is almost certainly overfit or mis-costed** — the Judge treats it as
  a red flag, not a win.

## 5.8 Validation stack (what "profitable" must mean here)

1. Purged, embargoed k-fold → walk-forward (6-month train, 1-month test, roll).
2. Deflated Sharpe Ratio (Bailey & López de Prado) using the logged trial count.
3. Probability of Backtest Overfitting via CSCV; require PBO < 0.3.
4. Cost sensitivity: still positive at 1.5× modelled costs.
5. Paper trading ≥ 4 weeks with realised slippage within 30% of model.
6. Live at ≤ 10% of intended capital for ≥ 8 weeks; promote only if live Sharpe is within
   1σ of paper.

## 6. The iteration loop

```
nightly 00:15 UTC   postmortem-analyst → attribution + hypotheses → tasks.md
nightly 00:45 UTC   Planner (main Agent) → scopes hypotheses into tasks with DONE conditions
on task             quant-researcher / data-engineer / news-analyst → work in git worktree branches
on completion       judge → verdict in tasks.md; REVISE loops back; ACCEPT → PR
weekly              risk-manager → reweight portfolio, demote drifting strategies
human               reviews ACCEPTed PRs, signs capital_allocation.yaml for promotions
```

## 9. What will actually determine whether this makes money

- The fitted slippage model being honest (execution-engineer's most important deliverable).
- The Judge rejecting most things. Track its rejection rate; aim for > 80%.
- Carry doing the heavy lifting while directional sleeves add modest, uncorrelated return.
- The human, not the agents, holding the capital key.
