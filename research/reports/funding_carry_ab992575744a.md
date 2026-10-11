# Tearsheet — funding_carry @ ab992575744a

Generated 2026-10-11T10:00:57.711090+00:00 · code a79caa8 · params `research.strategies.funding_carry.FundingCarryParams`

**Verdict (researcher): Insufficient evidence**

## Protocol
- Data: BTC/USDT:USDT+BTC/USDT, ETH/USDT:USDT+ETH/USDT, SOL/USDT:USDT+SOL/USDT · 1h (multiday) · 2020-01-01 → 2026-10-01
- Splits: walk-forward 180D/30D/2D embargo; best-train-Sharpe selection
- Trials evaluated (feeds DSR): **18**
- Cost model: `{"maker_fee_bps": 2.0, "multiplier": 1.0, "slip_a": 0.5, "slip_b": 25.0, "slip_c": 0.5, "source": "default_conservative (no fitted file found)", "spread_bps": 1.0, "taker_fee_bps": 5.0}`

## Headline (walk-forward OOS, after costs)
| metric | value |
|---|---|
| Sharpe OOS | 5.32 |
| Sharpe IS | 7.84 |
| OOS / IS | 0.68 |
| Deflated Sharpe (prob.) | 1.000 |
| DSR p-value | 0.0000 |
| PBO | 0.363 |
| Max drawdown | -0.63% |
| Calmar | 13.21 |
| Turnover / bar | 0.0004 |
| Cost drag / trade | 42.3 bps |
| Trades OOS | 43 |
| Hit rate | 88.4% |
| Payoff ratio | 22.28 |
| Sharpe OOS @ 1.5× costs | 4.78 |

Sharpe by walk-forward fold: n/a

## Per-regime PnL
| regime | PnL |
|---|---|
| Chaos | +6.29% |
| Range | +24.98% |
| Trend | +23.80% |

## Monthly PnL
| month | PnL |
|---|---|
| 2020-06 | +0.00% |
| 2020-07 | +0.82% |
| 2020-08 | +2.28% |
| 2020-09 | +0.36% |
| 2020-10 | +0.42% |
| 2020-11 | +1.58% |
| 2020-12 | +1.42% |
| 2021-01 | +6.45% |
| 2021-02 | +9.86% |
| 2021-03 | +4.34% |
| 2021-04 | +5.92% |
| 2021-05 | +1.10% |
| 2021-06 | +0.00% |
| 2021-07 | +0.00% |
| 2021-08 | +0.94% |
| 2021-09 | +2.39% |
| 2021-10 | +1.48% |
| 2021-11 | +1.20% |
| 2021-12 | +0.01% |
| 2022-01 | +0.00% |
| 2022-02 | +0.00% |
| 2022-03 | +0.00% |
| 2022-04 | +0.00% |
| 2022-05 | +0.00% |
| 2022-06 | +0.00% |
| 2022-07 | +0.00% |
| 2022-08 | +0.00% |
| 2022-09 | +0.00% |
| 2022-10 | +0.00% |
| 2022-11 | +0.00% |
| 2022-12 | +0.00% |
| 2023-01 | +0.00% |
| 2023-02 | +0.00% |
| 2023-03 | +0.00% |
| 2023-04 | -0.04% |
| 2023-05 | +0.00% |
| 2023-06 | +0.00% |
| 2023-07 | +0.00% |
| 2023-08 | +0.00% |
| 2023-09 | +0.00% |
| 2023-10 | +0.00% |
| 2023-11 | +0.00% |
| 2023-12 | +1.01% |
| 2024-01 | +1.05% |
| 2024-02 | +1.22% |
| 2024-03 | +4.26% |
| 2024-04 | +0.85% |
| 2024-05 | +0.02% |
| 2024-06 | +0.28% |
| 2024-07 | +0.00% |
| 2024-08 | +0.00% |
| 2024-09 | +0.00% |
| 2024-10 | +0.00% |
| 2024-11 | +0.78% |
| 2024-12 | +0.93% |
| 2025-01 | -0.02% |
| 2025-02 | +0.00% |
| 2025-03 | +0.00% |
| 2025-04 | +0.00% |
| 2025-05 | +0.00% |
| 2025-06 | +0.00% |
| 2025-07 | +0.00% |
| 2025-08 | +0.00% |
| 2025-09 | +0.00% |
| 2025-10 | +0.00% |
| 2025-11 | +0.00% |
| 2025-12 | +0.00% |
| 2026-01 | +0.00% |
| 2026-02 | +0.00% |
| 2026-03 | +0.00% |
| 2026-04 | +0.00% |
| 2026-05 | +0.00% |
| 2026-06 | +0.00% |
| 2026-07 | +0.00% |
| 2026-08 | +0.00% |
| 2026-09 | +0.00% |

## Notes
OOS 2020-06-29 → 2026-09-26: total +64.46%, CAGR +8.29%, mean day +0.0218%, worst day -0.59%, days invested 27%.

Sizing: 0.251× equity per leg, ≤ 3 pairs — capped by spot cash + 33% perp margin ≤ equity (binding) rather than by the 0.5% / 1.5% basis-stop risk rule.

Horizon: multiday — median hold 512 bars (21.3 days). Trade-count floor 100 (T-018); trades 43.

Independent episodes (book flat > 7d between): 8, positive 88%; invested-day Sharpe +11.64, moving-block bootstrap 95% CI [+9.94, +14.04] (block 10d, 2000 draws). Exception thresholds ≥ 30 / ≥ 60% / CI > 0 → NOT met. The gate still counts trades; the exception is the Judge's call.

Cash-yield sensitivity: 5% stablecoin APR on deployed cash (spot + margin) while invested = $7,155 over OOS → total net +53.11% (vs +64.46%), Sharpe net +4.73. This is the strategy's excess return over parking the same cash in USDC.

Margin check: max perp-leg rally within a hold +457.7% vs initial margin 33%; holds breaching margin (would need a top-up from spot) 17/43.

Funding received $58,274; costs paid $4,836; basis + price P&L is the remainder.

Exit reasons: {'signal': 27, 'deselected': 12, 'basis_stop': 4}. Halts: none.

Trial Sharpes (daily, full period): entry 15%/exit 5% +5.99, entry 15%/exit 10% +5.70, entry 25%/exit 5% +5.83, entry 25%/exit 10% +5.57, entry 40%/exit 5% +5.62, entry 40%/exit 10% +5.44

1.5× costs: OOS Sharpe +4.78, halts none.

Not modelled: single-exchange risk (both legs Binance), spot borrow for the negative-funding side (not traded), margin interest, ADL. Costs are the conservative default (spot taker 10 bps, perp taker 5 bps, both legs).

## Params
```json
{
  "apr_window_bars": 24,
  "basis_stop": 0.015,
  "cash_yield_apr": 0.05,
  "end": "2026-10-01",
  "entry_apr": [
    0.15,
    0.25,
    0.4
  ],
  "episode_gap_days": 7,
  "exit_apr": [
    0.05,
    0.1
  ],
  "perp_initial_margin": 0.33,
  "perp_spread_bps": {
    "BTC": 1.0,
    "ETH": 1.0,
    "SOL": 2.0
  },
  "spot_spread_bps": {
    "BTC": 1.0,
    "ETH": 1.0,
    "SOL": 2.0
  },
  "spot_taker_fee_bps": 10.0,
  "start": "2020-01-01",
  "symbols": [
    "BTC",
    "ETH",
    "SOL"
  ],
  "timeframe": "1h",
  "version": "1",
  "wf_embargo_days": 2,
  "wf_test_days": 30,
  "wf_train_days": 180
}
```
