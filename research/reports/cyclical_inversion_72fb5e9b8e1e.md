# Tearsheet — cyclical_inversion @ 72fb5e9b8e1e

Generated 2026-10-09T22:53:33.089541+00:00 · code a79caa8 · params `research.strategies.cyclical_inversion.CyclicalInversionParams`

**Verdict (researcher): Reject**

## Protocol
- Data: BNB/USDT:USDT, XRP/USDT:USDT, DOGE/USDT:USDT, ADA/USDT:USDT, AVAX/USDT:USDT, LINK/USDT:USDT, LTC/USDT:USDT, DOT/USDT:USDT, TRX/USDT:USDT, BCH/USDT:USDT · 1h · 2023-01-01 → 2026-10-01
- Splits: walk-forward 180D train / 30D test / 2D embargo; per-family best-train-Sharpe selection; ¼-Kelly risk from train trades
- Trials evaluated (feeds DSR): **56**
- Cost model: `{"maker_fee_bps": 2.0, "multiplier": 1.0, "slip_a": 0.5, "slip_b": 25.0, "slip_c": 0.5, "source": "default_conservative (no fitted file found)", "spread_bps": 1.0, "taker_fee_bps": 5.0}`

## Headline (walk-forward OOS, after costs)
| metric | value |
|---|---|
| Sharpe OOS | -0.96 |
| Sharpe IS | 1.30 |
| OOS / IS | -0.74 |
| Deflated Sharpe (prob.) | 0.000 |
| DSR p-value | 1.0000 |
| PBO | 0.100 |
| Max drawdown | -7.66% |
| Calmar | -0.29 |
| Turnover / bar | 0.0011 |
| Cost drag / trade | 18.4 bps |
| Trades OOS | 98 |
| Hit rate | 25.5% |
| Payoff ratio | 1.68 |
| Sharpe OOS @ 1.5× costs | -1.02 |

Sharpe by walk-forward fold: -0.70, -4.45, -3.49, -3.17, -2.11, -5.40

## Per-regime PnL
| regime | PnL |
|---|---|
| Chaos | -3.20% |
| Range | -2.17% |
| Trend | -1.84% |

## Monthly PnL
| month | PnL |
|---|---|
| 2023-06 | -0.93% |
| 2023-07 | +0.88% |
| 2023-08 | -2.52% |
| 2023-09 | +0.00% |
| 2023-10 | +0.00% |
| 2023-11 | +0.00% |
| 2023-12 | +0.00% |
| 2024-01 | +0.00% |
| 2024-02 | +0.31% |
| 2024-03 | -2.69% |
| 2024-04 | -2.24% |
| 2024-05 | +0.00% |
| 2024-06 | +0.00% |
| 2024-07 | +0.00% |
| 2024-08 | +0.00% |
| 2024-09 | +0.00% |
| 2024-10 | +0.00% |
| 2024-11 | +0.00% |
| 2024-12 | +0.00% |
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
OOS 2023-06-30 → 2026-09-12. Total return -7.04%, CAGR -2.25%, mean day -0.0062%, best day +1.04%, worst day -1.41%, 3% of days positive, 93% flat.

Kill-switch halts in the final run: ['2024-04-27T11:00:00+00:00 trailing_drawdown equity=92,965'].

Costs paid $2,606, funding paid $96 (on $100k start). Average -0.317R per trade, median hold 7 bars.

By side: short: 25 trades, $-742, avg -0.166R, hit 32%; long: 73 trades, $-6,301, avg -0.369R, hit 23%

By symbol: ADA/USDT:USDT: 12 trades, $-1,343, avg -0.519R; AVAX/USDT:USDT: 8 trades, $-789, avg -0.537R; BCH/USDT:USDT: 5 trades, $-1,296, avg -0.911R; BNB/USDT:USDT: 8 trades, $-923, avg -0.187R; DOGE/USDT:USDT: 16 trades, $-1,341, avg -0.495R; DOT/USDT:USDT: 10 trades, $1,151, avg +0.234R; LINK/USDT:USDT: 13 trades, $615, avg +0.170R; LTC/USDT:USDT: 10 trades, $-556, avg -0.265R; TRX/USDT:USDT: 8 trades, $-1,950, avg -0.565R; XRP/USDT:USDT: 8 trades, $-609, avg -0.494R

Exit reasons: {'stop': 84, 'time': 8, 'signal': 4, 'kill_switch': 2}; avg R by exit: kill_switch -0.33, signal +2.14, stop -0.51, time +0.49

Principles that fired (count of bars/setups): {'derisk_in_drawdown': 99, 'skip_risk_budget_full': 91, 'shrunk_to_budget': 50, 'skip_cooldown': 45, 'skip_cost_vs_edge': 35, 'skip_consecutive_losses': 31, 'shrunk_to_planned_risk': 24, 'halt_trailing_drawdown': 1}

Trial Sharpes (daily, full period, single sleeve, 0.5% risk): inv_n48_k4.0_t1.5_both -2.37, inv_n48_k4.0_t1.5_long -1.42, inv_n48_k4.0_t3.0_both -2.32, inv_n48_k4.0_t3.0_long -1.53, inv_n48_k6.5_t1.5_both -1.59, inv_n48_k6.5_t1.5_long -0.73, inv_n48_k6.5_t3.0_both -1.60, inv_n48_k6.5_t3.0_long -0.85, inv_n96_k4.0_t1.5_both -2.00, inv_n96_k4.0_t1.5_long -1.92, inv_n96_k4.0_t3.0_both -1.20, inv_n96_k4.0_t3.0_long -1.57, inv_n96_k6.5_t1.5_both -1.45, inv_n96_k6.5_t1.5_long -1.12, inv_n96_k6.5_t3.0_both -1.20, inv_n96_k6.5_t3.0_long -0.96, inv_n168_k4.0_t1.5_both -2.37, inv_n168_k4.0_t1.5_long -1.31, inv_n168_k4.0_t3.0_both -1.91, inv_n168_k4.0_t3.0_long -1.46, inv_n168_k6.5_t1.5_both -1.76, inv_n168_k6.5_t1.5_long -0.67, inv_n168_k6.5_t3.0_both -1.72, inv_n168_k6.5_t3.0_long -0.62

Sweep diagnostic (96-bar support, k=4, forward 24h in ATR): BNB: 771 sweeps, 623 reclaimed → -0.13 ATR (hit 60%) vs not reclaimed +0.40 ATR (hit 59%); XRP: 823 sweeps, 656 reclaimed → +0.28 ATR (hit 58%) vs not reclaimed +0.08 ATR (hit 55%); DOG: 801 sweeps, 629 reclaimed → +0.05 ATR (hit 56%) vs not reclaimed +0.26 ATR (hit 58%); ADA: 1018 sweeps, 787 reclaimed → +0.03 ATR (hit 53%) vs not reclaimed -0.08 ATR (hit 53%); AVA: 987 sweeps, 774 reclaimed → -0.09 ATR (hit 48%) vs not reclaimed +0.35 ATR (hit 54%); LIN: 896 sweeps, 686 reclaimed → +0.44 ATR (hit 59%) vs not reclaimed +0.06 ATR (hit 55%); LTC: 758 sweeps, 578 reclaimed → +0.32 ATR (hit 60%) vs not reclaimed +0.37 ATR (hit 58%); DOT: 983 sweeps, 762 reclaimed → -0.02 ATR (hit 51%) vs not reclaimed +0.21 ATR (hit 56%); TRX: 796 sweeps, 594 reclaimed → +0.06 ATR (hit 55%) vs not reclaimed -0.11 ATR (hit 58%); BCH: 844 sweeps, 661 reclaimed → +0.23 ATR (hit 60%) vs not reclaimed +0.39 ATR (hit 61%)

1.5× costs: OOS Sharpe -1.02, halts ['2024-03-20T02:00:00+00:00 trailing_drawdown equity=93,465'].

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
    "ADA/USDT:USDT": 2.5,
    "AVAX/USDT:USDT": 3.0,
    "BCH/USDT:USDT": 3.0,
    "BNB/USDT:USDT": 1.5,
    "DOGE/USDT:USDT": 2.0,
    "DOT/USDT:USDT": 3.0,
    "LINK/USDT:USDT": 3.0,
    "LTC/USDT:USDT": 2.5,
    "TRX/USDT:USDT": 2.5,
    "XRP/USDT:USDT": 1.5
  },
  "start": "2023-01-01",
  "stop_buffer_atr": 0.25,
  "sweep_atr": 0.1,
  "symbols": [
    "BNB/USDT:USDT",
    "XRP/USDT:USDT",
    "DOGE/USDT:USDT",
    "ADA/USDT:USDT",
    "AVAX/USDT:USDT",
    "LINK/USDT:USDT",
    "LTC/USDT:USDT",
    "DOT/USDT:USDT",
    "TRX/USDT:USDT",
    "BCH/USDT:USDT"
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
