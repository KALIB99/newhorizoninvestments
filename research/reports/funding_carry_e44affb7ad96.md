# Tearsheet — funding_carry @ e44affb7ad96

Generated 2026-10-11T10:01:04.627296+00:00 · code a79caa8 · params `research.strategies.funding_carry.FundingCarryParams`

**Verdict (researcher): Insufficient evidence**

## Protocol
- Data: BTC/USDT:USDT+BTC/USDT, ETH/USDT:USDT+ETH/USDT, SOL/USDT:USDT+SOL/USDT, BNB/USDT:USDT+BNB/USDT, XRP/USDT:USDT+XRP/USDT, DOGE/USDT:USDT+DOGE/USDT, ADA/USDT:USDT+ADA/USDT, AVAX/USDT:USDT+AVAX/USDT, LINK/USDT:USDT+LINK/USDT, LTC/USDT:USDT+LTC/USDT, DOT/USDT:USDT+DOT/USDT, TRX/USDT:USDT+TRX/USDT, BCH/USDT:USDT+BCH/USDT · 1h (multiday) · 2020-01-01 → 2026-10-01
- Splits: walk-forward 180D/30D/2D embargo; best-train-Sharpe selection
- Trials evaluated (feeds DSR): **18**
- Cost model: `{"maker_fee_bps": 2.0, "multiplier": 1.0, "slip_a": 0.5, "slip_b": 25.0, "slip_c": 0.5, "source": "default_conservative (no fitted file found)", "spread_bps": 1.0, "taker_fee_bps": 5.0}`

## Headline (walk-forward OOS, after costs)
| metric | value |
|---|---|
| Sharpe OOS | 4.88 |
| Sharpe IS | 7.42 |
| OOS / IS | 0.66 |
| Deflated Sharpe (prob.) | 1.000 |
| DSR p-value | 0.0000 |
| PBO | 0.640 |
| Max drawdown | -0.98% |
| Calmar | 9.32 |
| Turnover / bar | 0.0006 |
| Cost drag / trade | 45.2 bps |
| Trades OOS | 65 |
| Hit rate | 67.7% |
| Payoff ratio | 16.60 |
| Sharpe OOS @ 1.5× costs | 4.51 |

Sharpe by walk-forward fold: n/a

## Per-regime PnL
| regime | PnL |
|---|---|
| Chaos | +6.14% |
| Range | +31.05% |
| Trend | +24.09% |

## Monthly PnL
| month | PnL |
|---|---|
| 2020-06 | +0.00% |
| 2020-07 | +1.17% |
| 2020-08 | +3.92% |
| 2020-09 | +0.65% |
| 2020-10 | +0.73% |
| 2020-11 | +2.71% |
| 2020-12 | +3.33% |
| 2021-01 | +6.65% |
| 2021-02 | +7.74% |
| 2021-03 | +3.47% |
| 2021-04 | +9.24% |
| 2021-05 | +3.42% |
| 2021-06 | +0.00% |
| 2021-07 | +0.00% |
| 2021-08 | +1.70% |
| 2021-09 | +1.05% |
| 2021-10 | +1.42% |
| 2021-11 | +0.84% |
| 2021-12 | -0.08% |
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
| 2023-04 | -0.11% |
| 2023-05 | +0.00% |
| 2023-06 | +0.00% |
| 2023-07 | +0.00% |
| 2023-08 | +0.00% |
| 2023-09 | +0.00% |
| 2023-10 | +0.00% |
| 2023-11 | +0.00% |
| 2023-12 | +0.80% |
| 2024-01 | +0.71% |
| 2024-02 | +0.59% |
| 2024-03 | +3.36% |
| 2024-04 | +0.57% |
| 2024-05 | +0.00% |
| 2024-06 | +0.00% |
| 2024-07 | +0.00% |
| 2024-08 | +0.00% |
| 2024-09 | +0.00% |
| 2024-10 | -0.05% |
| 2024-11 | +0.81% |
| 2024-12 | +1.34% |
| 2025-01 | -0.02% |
| 2025-02 | +0.00% |
| 2025-03 | +0.00% |
| 2025-04 | +0.00% |
| 2025-05 | +0.00% |
| 2025-06 | +0.00% |
| 2025-07 | +0.00% |
| 2025-08 | +0.00% |
| 2025-09 | +0.00% |
| 2025-10 | -0.11% |
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
OOS 2020-06-29 → 2026-09-26: total +72.59%, CAGR +9.13%, mean day +0.0240%, worst day -0.92%, days invested 28%.

Sizing: 0.251× equity per leg, ≤ 3 pairs — capped by spot cash + 33% perp margin ≤ equity (binding) rather than by the 0.5% / 1.5% basis-stop risk rule.

Horizon: multiday — median hold 375 bars (15.6 days). Trade-count floor 100 (T-018); trades 65.

Independent episodes (book flat > 7d between): 7, positive 71%; invested-day Sharpe +10.03, moving-block bootstrap 95% CI [+8.45, +12.31] (block 10d, 2000 draws). Exception thresholds ≥ 30 / ≥ 60% / CI > 0 → NOT met. The gate still counts trades; the exception is the Judge's call.

Cash-yield sensitivity: 5% stablecoin APR on deployed cash (spot + margin) while invested = $8,378 over OOS → total net +58.72% (vs +72.59%), Sharpe net +4.26. This is the strategy's excess return over parking the same cash in USDC.

Margin check: max perp-leg rally within a hold +508.5% vs initial margin 33%; holds breaching margin (would need a top-up from spot) 22/65.

Funding received $67,724; costs paid $7,921; basis + price P&L is the remainder.

Exit reasons: {'signal': 44, 'deselected': 15, 'basis_stop': 3, 'kill_switch': 3}. Halts: ['2021-02-11T04:00:00+00:00 daily_loss'].

Trial Sharpes (daily, full period): entry 15%/exit 5% +5.82, entry 15%/exit 10% +5.70, entry 25%/exit 5% +5.91, entry 25%/exit 10% +5.74, entry 40%/exit 5% +5.62, entry 40%/exit 10% +5.46

1.5× costs: OOS Sharpe +4.51, halts ['2020-12-21T15:00:00+00:00 daily_loss'].

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
    "ADA": 2.5,
    "AVAX": 3.0,
    "BCH": 3.0,
    "BNB": 1.5,
    "BTC": 1.0,
    "DOGE": 2.0,
    "DOT": 3.0,
    "ETH": 1.0,
    "LINK": 3.0,
    "LTC": 2.5,
    "SOL": 2.0,
    "TRX": 2.5,
    "XRP": 1.5
  },
  "spot_spread_bps": {
    "ADA": 2.5,
    "AVAX": 3.0,
    "BCH": 3.0,
    "BNB": 1.5,
    "BTC": 1.0,
    "DOGE": 2.0,
    "DOT": 3.0,
    "ETH": 1.0,
    "LINK": 3.0,
    "LTC": 2.5,
    "SOL": 2.0,
    "TRX": 2.5,
    "XRP": 1.5
  },
  "spot_taker_fee_bps": 10.0,
  "start": "2020-01-01",
  "symbols": [
    "BTC",
    "ETH",
    "SOL",
    "BNB",
    "XRP",
    "DOGE",
    "ADA",
    "AVAX",
    "LINK",
    "LTC",
    "DOT",
    "TRX",
    "BCH"
  ],
  "timeframe": "1h",
  "version": "1",
  "wf_embargo_days": 2,
  "wf_test_days": 30,
  "wf_train_days": 180
}
```
