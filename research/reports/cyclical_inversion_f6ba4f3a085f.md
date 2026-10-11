# Tearsheet — cyclical_inversion @ f6ba4f3a085f

Generated 2026-10-09T22:42:51.968566+00:00 · code a79caa8 · params `research.strategies.cyclical_inversion.CyclicalInversionParams`

**Verdict (researcher): Reject**

## Protocol
- Data: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT · 1h · 2023-01-01 → 2026-10-01
- Splits: walk-forward 180D train / 30D test / 2D embargo; per-family best-train-Sharpe selection; ¼-Kelly risk from train trades
- Trials evaluated (feeds DSR): **24**
- Cost model: `{"maker_fee_bps": 2.0, "multiplier": 1.0, "slip_a": 0.5, "slip_b": 25.0, "slip_c": 0.5, "source": "default_conservative (no fitted file found)", "spread_bps": 1.0, "taker_fee_bps": 5.0}`

## Headline (walk-forward OOS, after costs)
| metric | value |
|---|---|
| Sharpe OOS | -0.47 |
| Sharpe IS | 1.11 |
| OOS / IS | -0.42 |
| Deflated Sharpe (prob.) | 0.004 |
| DSR p-value | 0.9960 |
| PBO | 0.348 |
| Max drawdown | -8.14% |
| Calmar | -0.20 |
| Turnover / bar | 0.0024 |
| Cost drag / trade | 14.6 bps |
| Trades OOS | 226 |
| Hit rate | 29.6% |
| Payoff ratio | 1.98 |
| Sharpe OOS @ 1.5× costs | -0.33 |

Sharpe by walk-forward fold: -0.47, 1.97, 1.91, -3.87, 2.46, 0.58, -1.68, 1.24, 0.58, -8.10, -3.66, 3.42, -0.19, -1.11, -3.49, -2.93, -8.83

## Per-regime PnL
| regime | PnL |
|---|---|
| Chaos | +0.15% |
| Range | -1.57% |
| Trend | -3.85% |

## Monthly PnL
| month | PnL |
|---|---|
| 2023-06 | -0.45% |
| 2023-07 | +0.25% |
| 2023-08 | +1.34% |
| 2023-09 | +0.84% |
| 2023-10 | -2.45% |
| 2023-11 | +0.02% |
| 2023-12 | +1.75% |
| 2024-01 | -1.16% |
| 2024-02 | +0.55% |
| 2024-03 | +0.31% |
| 2024-04 | -3.71% |
| 2024-05 | -0.21% |
| 2024-06 | +0.00% |
| 2024-07 | +0.00% |
| 2024-08 | +0.00% |
| 2024-09 | +0.00% |
| 2024-10 | +0.00% |
| 2024-11 | +0.00% |
| 2024-12 | +0.00% |
| 2025-01 | +0.00% |
| 2025-02 | -0.05% |
| 2025-03 | -0.05% |
| 2025-04 | -0.19% |
| 2025-05 | +0.00% |
| 2025-06 | -0.13% |
| 2025-07 | -0.65% |
| 2025-08 | -1.21% |
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
OOS 2023-06-30 → 2026-09-12. Total return -5.22%, CAGR -1.66%, mean day -0.0044%, best day +1.39%, worst day -1.42%, 8% of days positive, 81% flat.

Kill-switch halts in the final run: ['2025-08-13T10:00:00+00:00 trailing_drawdown equity=94,784'].

Costs paid $4,851, funding paid $391 (on $100k start). Average -0.175R per trade, median hold 7 bars.

By side: short: 69 trades, $-1,335, avg +0.065R, hit 33%; long: 157 trades, $-3,881, avg -0.280R, hit 28%

By symbol: BTC/USDT:USDT: 66 trades, $447, avg -0.169R; ETH/USDT:USDT: 84 trades, $1,444, avg +0.005R; SOL/USDT:USDT: 76 trades, $-7,107, avg -0.378R

Exit reasons: {'stop': 204, 'time': 13, 'signal': 9}; avg R by exit: signal +3.32, stop -0.40, time +0.94

Principles that fired (count of bars/setups): {'skip_cooldown': 146, 'derisk_in_drawdown': 124, 'shrunk_to_budget': 70, 'shrunk_to_planned_risk': 56, 'skip_risk_budget_full': 39, 'skip_cost_vs_edge': 25, 'skip_consecutive_losses': 17, 'halt_trailing_drawdown': 1}

Trial Sharpes (daily, full period, single sleeve, 0.5% risk): inv_n48_k4.0_t1.5_both -2.03, inv_n48_k4.0_t1.5_long -1.38, inv_n48_k4.0_t3.0_both -1.94, inv_n48_k4.0_t3.0_long -1.46, inv_n48_k6.5_t1.5_both -1.41, inv_n48_k6.5_t1.5_long -0.80, inv_n48_k6.5_t3.0_both -1.56, inv_n48_k6.5_t3.0_long -0.74, inv_n96_k4.0_t1.5_both -1.48, inv_n96_k4.0_t1.5_long -0.81, inv_n96_k4.0_t3.0_both -1.20, inv_n96_k4.0_t3.0_long -0.98, inv_n96_k6.5_t1.5_both -1.59, inv_n96_k6.5_t1.5_long -0.96, inv_n96_k6.5_t3.0_both -1.68, inv_n96_k6.5_t3.0_long -0.95, inv_n168_k4.0_t1.5_both -1.34, inv_n168_k4.0_t1.5_long -0.70, inv_n168_k4.0_t3.0_both -1.38, inv_n168_k4.0_t3.0_long -0.74, inv_n168_k6.5_t1.5_both -1.44, inv_n168_k6.5_t1.5_long -0.61, inv_n168_k6.5_t3.0_both -1.48, inv_n168_k6.5_t3.0_long -0.39

Sweep diagnostic (96-bar support, k=4, forward 24h in ATR): BTC: 855 sweeps, 716 reclaimed → -0.09 ATR (hit 56%) vs not reclaimed -0.35 ATR (hit 48%); ETH: 731 sweeps, 566 reclaimed → +0.05 ATR (hit 57%) vs not reclaimed +0.05 ATR (hit 52%); SOL: 861 sweeps, 692 reclaimed → +0.27 ATR (hit 56%) vs not reclaimed -0.32 ATR (hit 46%)

1.5× costs: OOS Sharpe -0.33, halts ['2025-03-04T17:00:00+00:00 trailing_drawdown equity=97,532'].

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
    48,
    96,
    168
  ],
  "max_hold": 72,
  "min_drop_atr": [
    4.0,
    6.5
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
  "stop_buffer_atr": 0.25,
  "sweep_atr": 0.1,
  "symbols": [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT"
  ],
  "timeframe": "1h",
  "trail_after_r": 1.5,
  "trail_atr": [
    1.5,
    3.0
  ],
  "version": "1",
  "wf_embargo_days": 2,
  "wf_test_days": 30,
  "wf_train_days": 180
}
```
