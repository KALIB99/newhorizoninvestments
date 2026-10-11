# Tearsheet — cyclical_inversion @ f1f78f878d25

Generated 2026-10-09T22:45:56.130960+00:00 · code a79caa8 · params `research.strategies.cyclical_inversion.CyclicalInversionParams`

**Verdict (researcher): Reject**

## Protocol
- Data: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT · 1h · 2023-01-01 → 2026-10-01
- Splits: walk-forward 180D train / 30D test / 2D embargo; per-family best-train-Sharpe selection; ¼-Kelly risk from train trades
- Trials evaluated (feeds DSR): **32**
- Cost model: `{"maker_fee_bps": 2.0, "multiplier": 1.0, "slip_a": 0.5, "slip_b": 25.0, "slip_c": 0.5, "source": "default_conservative (no fitted file found)", "spread_bps": 1.0, "taker_fee_bps": 5.0}`

## Headline (walk-forward OOS, after costs)
| metric | value |
|---|---|
| Sharpe OOS | -0.67 |
| Sharpe IS | 1.37 |
| OOS / IS | -0.49 |
| Deflated Sharpe (prob.) | 0.003 |
| DSR p-value | 0.9974 |
| PBO | 0.493 |
| Max drawdown | -7.87% |
| Calmar | -0.25 |
| Turnover / bar | 0.0011 |
| Cost drag / trade | 14.3 bps |
| Trades OOS | 158 |
| Hit rate | 38.6% |
| Payoff ratio | 1.16 |
| Sharpe OOS @ 1.5× costs | -0.78 |

Sharpe by walk-forward fold: 3.46, -2.20, 1.48, -3.97, -0.35, 4.10, -1.70, 3.90, -1.16, -4.21, -0.19, -2.96, -5.18, -3.86

## Per-regime PnL
| regime | PnL |
|---|---|
| Chaos | -1.86% |
| Range | -2.33% |
| Trend | -2.12% |

## Monthly PnL
| month | PnL |
|---|---|
| 2023-06 | +0.13% |
| 2023-07 | +0.38% |
| 2023-08 | -1.36% |
| 2023-09 | +1.11% |
| 2023-10 | -3.43% |
| 2023-11 | +0.58% |
| 2023-12 | +0.12% |
| 2024-01 | -0.69% |
| 2024-02 | +0.55% |
| 2024-03 | -0.44% |
| 2024-04 | -2.29% |
| 2024-05 | +0.34% |
| 2024-06 | +0.00% |
| 2024-07 | +0.00% |
| 2024-08 | +0.00% |
| 2024-09 | +0.00% |
| 2024-10 | +0.00% |
| 2024-11 | +0.00% |
| 2024-12 | +0.00% |
| 2025-01 | -0.32% |
| 2025-02 | -0.97% |
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
OOS 2023-06-30 → 2026-09-12. Total return -6.19%, CAGR -1.97%, mean day -0.0053%, best day +1.04%, worst day -1.57%, 9% of days positive, 82% flat.

Kill-switch halts in the final run: ['2025-02-26T18:00:00+00:00 trailing_drawdown equity=93,818'].

Costs paid $2,167, funding paid $318 (on $100k start). Average -0.148R per trade, median hold 34 bars.

By side: short: 37 trades, $-3,111, avg -0.237R, hit 35%; long: 121 trades, $-3,076, avg -0.121R, hit 40%

By symbol: BTC/USDT:USDT: 54 trades, $-1,381, avg -0.046R; ETH/USDT:USDT: 49 trades, $-2,247, avg -0.204R; SOL/USDT:USDT: 55 trades, $-2,558, avg -0.199R

Exit reasons: {'stop': 100, 'time': 39, 'signal': 16, 'kill_switch': 2, 'stop_gap': 1}; avg R by exit: kill_switch -0.40, signal +1.74, stop -0.61, stop_gap +1.25, time +0.23

Principles that fired (count of bars/setups): {'derisk_in_drawdown': 116, 'skip_cooldown': 70, 'shrunk_to_planned_risk': 43, 'shrunk_to_budget': 11, 'skip_risk_budget_full': 9, 'skip_consecutive_losses': 5, 'halt_trailing_drawdown': 1}

Trial Sharpes (daily, full period, single sleeve, 0.5% risk): inv_n96_k4.0_t3.0_both -0.61, inv_n96_k4.0_t3.0_long -0.18, inv_n168_k4.0_t3.0_both -0.54, inv_n168_k4.0_t3.0_long +0.16

Sweep diagnostic (96-bar support, k=4, forward 24h in ATR): BTC: 855 sweeps, 716 reclaimed → -0.09 ATR (hit 56%) vs not reclaimed -0.35 ATR (hit 48%); ETH: 731 sweeps, 566 reclaimed → +0.05 ATR (hit 57%) vs not reclaimed +0.05 ATR (hit 52%); SOL: 861 sweeps, 692 reclaimed → +0.27 ATR (hit 56%) vs not reclaimed -0.32 ATR (hit 46%)

1.5× costs: OOS Sharpe -0.78, halts ['2024-05-01T08:00:00+00:00 trailing_drawdown equity=93,628'].

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
  "stop_buffer_atr": 2.0,
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
