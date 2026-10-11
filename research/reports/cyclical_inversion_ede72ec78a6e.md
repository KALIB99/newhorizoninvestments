# Tearsheet — cyclical_inversion @ ede72ec78a6e

Generated 2026-10-09T22:45:32.382147+00:00 · code a79caa8 · params `research.strategies.cyclical_inversion.CyclicalInversionParams`

**Verdict (researcher): Reject**

## Protocol
- Data: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT · 1h · 2023-01-01 → 2026-10-01
- Splits: walk-forward 180D train / 30D test / 2D embargo; per-family best-train-Sharpe selection; ¼-Kelly risk from train trades
- Trials evaluated (feeds DSR): **28**
- Cost model: `{"maker_fee_bps": 2.0, "multiplier": 1.0, "slip_a": 0.5, "slip_b": 25.0, "slip_c": 0.5, "source": "default_conservative (no fitted file found)", "spread_bps": 1.0, "taker_fee_bps": 5.0}`

## Headline (walk-forward OOS, after costs)
| metric | value |
|---|---|
| Sharpe OOS | -0.48 |
| Sharpe IS | 0.97 |
| OOS / IS | -0.50 |
| Deflated Sharpe (prob.) | 0.001 |
| DSR p-value | 0.9991 |
| PBO | 0.150 |
| Max drawdown | -7.93% |
| Calmar | -0.27 |
| Turnover / bar | 0.0030 |
| Cost drag / trade | 14.6 bps |
| Trades OOS | 275 |
| Hit rate | 31.3% |
| Payoff ratio | 1.86 |
| Sharpe OOS @ 1.5× costs | -0.56 |

Sharpe by walk-forward fold: -0.51, -0.41, 0.40, -3.13, -0.51, 4.80, -3.88, 4.35, 0.02, -3.96, -0.42, -3.11, -3.19, -0.27, -0.37, -3.52, -6.72, 3.29, -8.82

## Per-regime PnL
| regime | PnL |
|---|---|
| Chaos | -2.85% |
| Range | +0.97% |
| Trend | -4.91% |

## Monthly PnL
| month | PnL |
|---|---|
| 2023-06 | -0.20% |
| 2023-07 | -0.12% |
| 2023-08 | -0.31% |
| 2023-09 | +0.75% |
| 2023-10 | -2.78% |
| 2023-11 | +0.95% |
| 2023-12 | +2.03% |
| 2024-01 | -2.58% |
| 2024-02 | +1.65% |
| 2024-03 | +0.32% |
| 2024-04 | -3.58% |
| 2024-05 | +1.06% |
| 2024-06 | +0.00% |
| 2024-07 | +0.00% |
| 2024-08 | +0.00% |
| 2024-09 | +0.00% |
| 2024-10 | +0.00% |
| 2024-11 | +0.00% |
| 2024-12 | +0.00% |
| 2025-01 | +0.00% |
| 2025-02 | +0.00% |
| 2025-03 | -0.15% |
| 2025-04 | -0.13% |
| 2025-05 | +0.00% |
| 2025-06 | +0.00% |
| 2025-07 | +0.52% |
| 2025-08 | -0.89% |
| 2025-09 | -0.22% |
| 2025-10 | -1.00% |
| 2025-11 | -0.20% |
| 2025-12 | +0.00% |
| 2026-01 | +0.00% |
| 2026-02 | +0.00% |
| 2026-03 | +0.00% |
| 2026-04 | +3.28% |
| 2026-05 | -3.04% |
| 2026-06 | -2.01% |
| 2026-07 | +0.00% |
| 2026-08 | +0.00% |
| 2026-09 | +0.00% |

## Notes
OOS 2023-06-30 → 2026-09-12. Total return -6.72%, CAGR -2.15%, mean day -0.0057%, best day +1.41%, worst day -1.54%, 12% of days positive, 74% flat.

Kill-switch halts in the final run: ['2026-06-03T20:00:00+00:00 trailing_drawdown equity=93,287'].

Costs paid $5,954, funding paid $647 (on $100k start). Average -0.140R per trade, median hold 15 bars.

By side: short: 50 trades, $-2,426, avg +0.096R, hit 36%; long: 225 trades, $-4,296, avg -0.192R, hit 30%

By symbol: BTC/USDT:USDT: 94 trades, $-1,953, avg -0.197R; ETH/USDT:USDT: 89 trades, $928, avg -0.006R; SOL/USDT:USDT: 92 trades, $-5,697, avg -0.210R

Exit reasons: {'stop': 222, 'time': 27, 'signal': 23, 'kill_switch': 2, 'stop_gap': 1}; avg R by exit: kill_switch -0.80, signal +2.85, stop -0.54, stop_gap +2.11, time +0.54

Principles that fired (count of bars/setups): {'derisk_in_drawdown': 178, 'skip_cooldown': 149, 'shrunk_to_planned_risk': 74, 'shrunk_to_budget': 72, 'skip_risk_budget_full': 59, 'skip_consecutive_losses': 39, 'skip_cost_vs_edge': 2, 'halt_trailing_drawdown': 1}

Trial Sharpes (daily, full period, single sleeve, 0.5% risk): inv_n96_k4.0_t3.0_both -0.95, inv_n96_k4.0_t3.0_long -0.36, inv_n168_k4.0_t3.0_both -1.16, inv_n168_k4.0_t3.0_long -0.40

Sweep diagnostic (96-bar support, k=4, forward 24h in ATR): BTC: 855 sweeps, 716 reclaimed → -0.09 ATR (hit 56%) vs not reclaimed -0.35 ATR (hit 48%); ETH: 731 sweeps, 566 reclaimed → +0.05 ATR (hit 57%) vs not reclaimed +0.05 ATR (hit 52%); SOL: 861 sweeps, 692 reclaimed → +0.27 ATR (hit 56%) vs not reclaimed -0.32 ATR (hit 46%)

1.5× costs: OOS Sharpe -0.56, halts ['2025-10-30T13:00:00+00:00 trailing_drawdown equity=93,687'].

Tier-1 event windows are NOT applied (no event calendar yet, T-005). Regime = rules fallback. Costs are the conservative default model (no fitted slippage yet, T-007). Dry/paper system only.

## Params
```json
{
  "allowed_regimes": [
    "Trend",
    "Range",
    "Chaos"
  ],
  "atr_period": 14,
  "breakeven_r": 1.0,
  "drop_lookback": 24,
  "end": "2026-10-01",
  "level_lookback": [
    96,
    168
  ],
  "max_hold": 72,
  "min_drop_atr": [
    4.0
  ],
  "reclaim_window": 2,
  "sides": [
    "both",
    "long"
  ],
  "spread_bps": {
    "BTC/USDT:USDT": 1.0,
    "ETH/USDT:USDT": 1.0,
    "SOL/USDT:USDT": 2.0
  },
  "start": "2023-01-01",
  "stop_buffer_atr": 1.0,
  "sweep_atr": 0.1,
  "symbols": [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT"
  ],
  "timeframe": "1h",
  "trail_after_r": 1.5,
  "trail_atr": [
    3.0
  ],
  "version": "1",
  "wf_embargo_days": 2,
  "wf_test_days": 30,
  "wf_train_days": 180
}
```
