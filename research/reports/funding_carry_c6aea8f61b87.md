# Tearsheet — funding_carry @ c6aea8f61b87

Generated 2026-10-11T09:46:32.870654+00:00 · code a79caa8 · params `research.strategies.funding_carry.FundingCarryParams`

**Verdict (researcher): Insufficient evidence**

## Protocol
- Data: BTC/USDT:USDT+BTC/USDT, ETH/USDT:USDT+ETH/USDT, SOL/USDT:USDT+SOL/USDT · 1h (multiday) · 2023-01-01 → 2026-10-01
- Splits: walk-forward 180D/30D/2D embargo; best-train-Sharpe selection
- Trials evaluated (feeds DSR): **6**
- Cost model: `{"maker_fee_bps": 2.0, "multiplier": 1.0, "slip_a": 0.5, "slip_b": 25.0, "slip_c": 0.5, "source": "default_conservative (no fitted file found)", "spread_bps": 1.0, "taker_fee_bps": 5.0}`

## Headline (walk-forward OOS, after costs)
| metric | value |
|---|---|
| Sharpe OOS | 4.70 |
| Sharpe IS | 7.70 |
| OOS / IS | 0.61 |
| Deflated Sharpe (prob.) | 1.000 |
| DSR p-value | 0.0000 |
| PBO | 0.106 |
| Max drawdown | -0.45% |
| Calmar | 8.10 |
| Turnover / bar | 0.0003 |
| Cost drag / trade | 40.2 bps |
| Trades OOS | 11 |
| Hit rate | 90.9% |
| Payoff ratio | 14.14 |
| Sharpe OOS @ 1.5× costs | 3.62 |

Sharpe by walk-forward fold: n/a

## Per-regime PnL
| regime | PnL |
|---|---|
| Chaos | +2.71% |
| Range | +5.73% |
| Trend | +3.21% |

## Monthly PnL
| month | PnL |
|---|---|
| 2023-06 | +0.00% |
| 2023-07 | +0.00% |
| 2023-08 | +0.00% |
| 2023-09 | +0.00% |
| 2023-10 | +0.00% |
| 2023-11 | +0.00% |
| 2023-12 | +1.19% |
| 2024-01 | +1.25% |
| 2024-02 | +1.35% |
| 2024-03 | +4.86% |
| 2024-04 | +0.93% |
| 2024-05 | -0.08% |
| 2024-06 | +0.00% |
| 2024-07 | +0.00% |
| 2024-08 | +0.00% |
| 2024-09 | +0.00% |
| 2024-10 | +0.00% |
| 2024-11 | +1.04% |
| 2024-12 | +1.02% |
| 2025-01 | +0.00% |
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
OOS 2023-06-30 → 2026-09-12: total +12.09%, CAGR +3.62%, mean day +0.0098%, worst day -0.37%, days invested 16%.

Horizon: multiday — median hold 969 bars (40.4 days); each trade is weeks of daily funding accruals. Trade-count floor 100 (T-018). Judge may rule on an episode-count exception.

Funding received $13,194; costs paid $1,525; basis + price P&L is the remainder.

Exit reasons: {'deselected': 6, 'signal': 5}. Halts: none.

Trial Sharpes (daily, full period): entry 15%/exit 5% +5.03, entry 15%/exit 10% +4.68, entry 25%/exit 5% +5.11, entry 25%/exit 10% +4.62, entry 40%/exit 5% +4.76, entry 40%/exit 10% +4.23

1.5× costs: OOS Sharpe +3.62, halts none.

Not modelled: exchange/custody risk on two venues, spot borrow for the negative-funding side (not traded), margin interest. Costs are the conservative default (spot taker 10 bps, perp taker 5 bps, both legs).

## Params
```json
{
  "apr_window_bars": 24,
  "basis_stop": 0.015,
  "end": "2026-10-01",
  "entry_apr": [
    0.15,
    0.25,
    0.4
  ],
  "exit_apr": [
    0.05,
    0.1
  ],
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
  "start": "2023-01-01",
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
