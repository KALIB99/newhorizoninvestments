# Tearsheet — funding_carry @ 10a3a9221ede

Generated 2026-10-11T09:46:36.377190+00:00 · code a79caa8 · params `research.strategies.funding_carry.FundingCarryParams`

**Verdict (researcher): Insufficient evidence**

## Protocol
- Data: BTC/USDT:USDT+BTC/USDT, ETH/USDT:USDT+ETH/USDT, SOL/USDT:USDT+SOL/USDT, BNB/USDT:USDT+BNB/USDT, XRP/USDT:USDT+XRP/USDT, DOGE/USDT:USDT+DOGE/USDT, ADA/USDT:USDT+ADA/USDT, AVAX/USDT:USDT+AVAX/USDT, LINK/USDT:USDT+LINK/USDT, LTC/USDT:USDT+LTC/USDT, DOT/USDT:USDT+DOT/USDT, TRX/USDT:USDT+TRX/USDT, BCH/USDT:USDT+BCH/USDT · 1h (multiday) · 2023-01-01 → 2026-10-01
- Splits: walk-forward 180D/30D/2D embargo; best-train-Sharpe selection
- Trials evaluated (feeds DSR): **12**
- Cost model: `{"maker_fee_bps": 2.0, "multiplier": 1.0, "slip_a": 0.5, "slip_b": 25.0, "slip_c": 0.5, "source": "default_conservative (no fitted file found)", "spread_bps": 1.0, "taker_fee_bps": 5.0}`

## Headline (walk-forward OOS, after costs)
| metric | value |
|---|---|
| Sharpe OOS | 3.72 |
| Sharpe IS | 6.86 |
| OOS / IS | 0.54 |
| Deflated Sharpe (prob.) | 1.000 |
| DSR p-value | 0.0000 |
| PBO | 0.065 |
| Max drawdown | -0.43% |
| Calmar | 8.62 |
| Turnover / bar | 0.0005 |
| Cost drag / trade | 42.8 bps |
| Trades OOS | 20 |
| Hit rate | 85.0% |
| Payoff ratio | 9.89 |
| Sharpe OOS @ 1.5× costs | 3.17 |

Sharpe by walk-forward fold: n/a

## Per-regime PnL
| regime | PnL |
|---|---|
| Chaos | +2.51% |
| Range | +5.93% |
| Trend | +3.37% |

## Monthly PnL
| month | PnL |
|---|---|
| 2023-06 | +0.00% |
| 2023-07 | +0.00% |
| 2023-08 | +0.00% |
| 2023-09 | +0.00% |
| 2023-10 | +0.00% |
| 2023-11 | +0.00% |
| 2023-12 | +1.16% |
| 2024-01 | +0.96% |
| 2024-02 | +0.97% |
| 2024-03 | +6.07% |
| 2024-04 | +1.24% |
| 2024-05 | +0.00% |
| 2024-06 | +0.00% |
| 2024-07 | +0.00% |
| 2024-08 | +0.00% |
| 2024-09 | +0.00% |
| 2024-10 | -0.06% |
| 2024-11 | +0.49% |
| 2024-12 | +1.07% |
| 2025-01 | +0.00% |
| 2025-02 | +0.00% |
| 2025-03 | +0.00% |
| 2025-04 | +0.00% |
| 2025-05 | +0.00% |
| 2025-06 | +0.00% |
| 2025-07 | +0.00% |
| 2025-08 | +0.00% |
| 2025-09 | +0.00% |
| 2025-10 | -0.14% |
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
OOS 2023-06-30 → 2026-09-12: total +12.25%, CAGR +3.67%, mean day +0.0099%, worst day -0.40%, days invested 16%.

Horizon: multiday — median hold 449 bars (18.7 days); each trade is weeks of daily funding accruals. Trade-count floor 100 (T-018). Judge may rule on an episode-count exception.

Funding received $14,390; costs paid $2,859; basis + price P&L is the remainder.

Exit reasons: {'signal': 11, 'deselected': 9}. Halts: none.

Trial Sharpes (daily, full period): entry 15%/exit 5% +4.30, entry 15%/exit 10% +3.96, entry 25%/exit 5% +4.58, entry 25%/exit 10% +4.56, entry 40%/exit 5% +4.83, entry 40%/exit 10% +4.26

1.5× costs: OOS Sharpe +3.17, halts none.

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
  "start": "2023-01-01",
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
