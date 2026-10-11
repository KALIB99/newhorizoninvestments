# Tearsheet — cyclical_inversion @ 6ac762315bd4

Generated 2026-10-09T22:53:46.274591+00:00 · code a79caa8 · params `research.strategies.cyclical_inversion.CyclicalInversionParams`

**Verdict (researcher): Reject**

## Protocol
- Data: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT, BNB/USDT:USDT, XRP/USDT:USDT, DOGE/USDT:USDT, ADA/USDT:USDT, AVAX/USDT:USDT, LINK/USDT:USDT, LTC/USDT:USDT, DOT/USDT:USDT, TRX/USDT:USDT, BCH/USDT:USDT · 1h · 2023-01-01 → 2026-10-01
- Splits: walk-forward 180D train / 30D test / 2D embargo; per-family best-train-Sharpe selection; ¼-Kelly risk from train trades
- Trials evaluated (feeds DSR): **80**
- Cost model: `{"maker_fee_bps": 2.0, "multiplier": 1.0, "slip_a": 0.5, "slip_b": 25.0, "slip_c": 0.5, "source": "default_conservative (no fitted file found)", "spread_bps": 1.0, "taker_fee_bps": 5.0}`

## Headline (walk-forward OOS, after costs)
| metric | value |
|---|---|
| Sharpe OOS | -0.41 |
| Sharpe IS | 1.18 |
| OOS / IS | -0.34 |
| Deflated Sharpe (prob.) | 0.000 |
| DSR p-value | 0.9995 |
| PBO | 0.034 |
| Max drawdown | -8.21% |
| Calmar | -0.19 |
| Turnover / bar | 0.0023 |
| Cost drag / trade | 17.0 bps |
| Trades OOS | 164 |
| Hit rate | 30.5% |
| Payoff ratio | 1.91 |
| Sharpe OOS @ 1.5× costs | -0.60 |

Sharpe by walk-forward fold: 2.17, -0.15, -1.70, 1.24, -0.79, -0.05, 0.29, -3.80, -5.95

## Per-regime PnL
| regime | PnL |
|---|---|
| Chaos | -1.77% |
| Range | -1.56% |
| Trend | -1.77% |

## Monthly PnL
| month | PnL |
|---|---|
| 2023-06 | -1.38% |
| 2023-07 | +3.62% |
| 2023-08 | -0.57% |
| 2023-09 | -1.40% |
| 2023-10 | +0.85% |
| 2023-11 | -0.77% |
| 2023-12 | +1.49% |
| 2024-01 | -1.80% |
| 2024-02 | +1.21% |
| 2024-03 | -2.94% |
| 2024-04 | -3.23% |
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
OOS 2023-06-30 → 2026-09-12. Total return -5.01%, CAGR -1.59%, mean day -0.0042%, best day +2.20%, worst day -1.38%, 6% of days positive, 86% flat.

Kill-switch halts in the final run: ['2024-04-13T20:00:00+00:00 trailing_drawdown equity=94,986'].

Costs paid $5,296, funding paid $216 (on $100k start). Average -0.174R per trade, median hold 14 bars.

By side: short: 42 trades, $361, avg -0.059R, hit 38%; long: 122 trades, $-5,375, avg -0.213R, hit 28%

By symbol: ADA/USDT:USDT: 12 trades, $5,064, avg +0.815R; AVAX/USDT:USDT: 10 trades, $-1,417, avg -0.531R; BCH/USDT:USDT: 10 trades, $658, avg +0.167R; BNB/USDT:USDT: 10 trades, $-1,533, avg -0.610R; BTC/USDT:USDT: 22 trades, $396, avg +0.055R; DOGE/USDT:USDT: 14 trades, $705, avg +0.138R; DOT/USDT:USDT: 6 trades, $-300, avg -0.216R; ETH/USDT:USDT: 16 trades, $-2,669, avg -0.513R; LINK/USDT:USDT: 14 trades, $-1,318, avg -0.392R; LTC/USDT:USDT: 16 trades, $447, avg -0.025R; SOL/USDT:USDT: 11 trades, $-623, avg -0.356R; TRX/USDT:USDT: 11 trades, $-3,253, avg -0.756R; XRP/USDT:USDT: 12 trades, $-1,171, avg -0.337R

Exit reasons: {'stop': 131, 'time': 18, 'signal': 15}; avg R by exit: signal +2.35, stop -0.50, time +0.10

Principles that fired (count of bars/setups): {'skip_risk_budget_full': 202, 'shrunk_to_budget': 99, 'derisk_in_drawdown': 82, 'skip_cost_vs_edge': 69, 'skip_cooldown': 56, 'skip_consecutive_losses': 45, 'shrunk_to_planned_risk': 40, 'halt_trailing_drawdown': 1}

Trial Sharpes (daily, full period, single sleeve, 0.5% risk): inv_n48_k4.0_t1.5_both -1.91, inv_n48_k4.0_t1.5_long -1.99, inv_n48_k4.0_t3.0_both -1.95, inv_n48_k4.0_t3.0_long -1.89, inv_n48_k6.5_t1.5_both -2.03, inv_n48_k6.5_t1.5_long -0.89, inv_n48_k6.5_t3.0_both -2.16, inv_n48_k6.5_t3.0_long -0.76, inv_n96_k4.0_t1.5_both -1.78, inv_n96_k4.0_t1.5_long -2.22, inv_n96_k4.0_t3.0_both -1.49, inv_n96_k4.0_t3.0_long -2.03, inv_n96_k6.5_t1.5_both -1.75, inv_n96_k6.5_t1.5_long -1.25, inv_n96_k6.5_t3.0_both -1.57, inv_n96_k6.5_t3.0_long -0.76, inv_n168_k4.0_t1.5_both -2.49, inv_n168_k4.0_t1.5_long -1.37, inv_n168_k4.0_t3.0_both -1.71, inv_n168_k4.0_t3.0_long -1.46, inv_n168_k6.5_t1.5_both -2.10, inv_n168_k6.5_t1.5_long -0.85, inv_n168_k6.5_t3.0_both -2.07, inv_n168_k6.5_t3.0_long -0.46

Sweep diagnostic (96-bar support, k=4, forward 24h in ATR): BTC: 855 sweeps, 716 reclaimed → -0.09 ATR (hit 56%) vs not reclaimed -0.35 ATR (hit 48%); ETH: 731 sweeps, 566 reclaimed → +0.05 ATR (hit 57%) vs not reclaimed +0.05 ATR (hit 52%); SOL: 861 sweeps, 692 reclaimed → +0.27 ATR (hit 56%) vs not reclaimed -0.32 ATR (hit 46%); BNB: 771 sweeps, 623 reclaimed → -0.13 ATR (hit 60%) vs not reclaimed +0.40 ATR (hit 59%); XRP: 823 sweeps, 656 reclaimed → +0.28 ATR (hit 58%) vs not reclaimed +0.08 ATR (hit 55%); DOG: 801 sweeps, 629 reclaimed → +0.05 ATR (hit 56%) vs not reclaimed +0.26 ATR (hit 58%); ADA: 1018 sweeps, 787 reclaimed → +0.03 ATR (hit 53%) vs not reclaimed -0.08 ATR (hit 53%); AVA: 987 sweeps, 774 reclaimed → -0.09 ATR (hit 48%) vs not reclaimed +0.35 ATR (hit 54%); LIN: 896 sweeps, 686 reclaimed → +0.44 ATR (hit 59%) vs not reclaimed +0.06 ATR (hit 55%); LTC: 758 sweeps, 578 reclaimed → +0.32 ATR (hit 60%) vs not reclaimed +0.37 ATR (hit 58%); DOT: 983 sweeps, 762 reclaimed → -0.02 ATR (hit 51%) vs not reclaimed +0.21 ATR (hit 56%); TRX: 796 sweeps, 594 reclaimed → +0.06 ATR (hit 55%) vs not reclaimed -0.11 ATR (hit 58%); BCH: 844 sweeps, 661 reclaimed → +0.23 ATR (hit 60%) vs not reclaimed +0.39 ATR (hit 61%)

1.5× costs: OOS Sharpe -0.60, halts ['2024-03-20T04:00:00+00:00 trailing_drawdown equity=94,269'].

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
    "BTC/USDT:USDT": 1.0,
    "DOGE/USDT:USDT": 2.0,
    "DOT/USDT:USDT": 3.0,
    "ETH/USDT:USDT": 1.0,
    "LINK/USDT:USDT": 3.0,
    "LTC/USDT:USDT": 2.5,
    "SOL/USDT:USDT": 2.0,
    "TRX/USDT:USDT": 2.5,
    "XRP/USDT:USDT": 1.5
  },
  "start": "2023-01-01",
  "stop_buffer_atr": 0.25,
  "sweep_atr": 0.1,
  "symbols": [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
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
