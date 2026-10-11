# Tearsheet — cyclical_inversion @ 37a81ade45c2

Generated 2026-10-09T23:03:43.302968+00:00 · code a79caa8 · params `research.strategies.cyclical_inversion.CyclicalInversionParams`

**Verdict (researcher): Reject**

## Protocol
- Data: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT · 1h · 2023-01-01 → 2026-10-01
- Splits: walk-forward 180D train / 30D test / 2D embargo; per-family best-train-Sharpe selection; ¼-Kelly risk from train trades
- Trials evaluated (feeds DSR): **104**
- Cost model: `{"maker_fee_bps": 2.0, "multiplier": 1.0, "slip_a": 0.5, "slip_b": 25.0, "slip_c": 0.5, "source": "default_conservative (no fitted file found)", "spread_bps": 1.0, "taker_fee_bps": 5.0}`

## Headline (walk-forward OOS, after costs)
| metric | value |
|---|---|
| Sharpe OOS | -0.59 |
| Sharpe IS | 1.21 |
| OOS / IS | -0.49 |
| Deflated Sharpe (prob.) | 0.001 |
| DSR p-value | 0.9991 |
| PBO | 0.350 |
| Max drawdown | -7.79% |
| Calmar | -0.28 |
| Turnover / bar | 0.0025 |
| Cost drag / trade | 11.8 bps |
| Trades OOS | 211 |
| Hit rate | 37.4% |
| Payoff ratio | 1.34 |
| Sharpe OOS @ 1.5× costs | -0.48 |

Sharpe by walk-forward fold: -0.63, -1.37, 1.12, -3.46, 1.90, 0.17, -1.52, 3.21, 0.71, -4.75, -1.32, 3.42, -1.42, -3.49, -3.49, -4.18, -5.48, -1.80, -3.84, -3.99

## Per-regime PnL
| regime | PnL |
|---|---|
| Chaos | -0.81% |
| Range | -3.43% |
| Trend | -2.69% |

## Monthly PnL
| month | PnL |
|---|---|
| 2023-06 | -0.45% |
| 2023-07 | +0.18% |
| 2023-08 | -0.93% |
| 2023-09 | +1.05% |
| 2023-10 | -2.69% |
| 2023-11 | -0.33% |
| 2023-12 | +1.48% |
| 2024-01 | -1.06% |
| 2024-02 | +1.34% |
| 2024-03 | +0.56% |
| 2024-04 | -3.45% |
| 2024-05 | +0.20% |
| 2024-06 | +0.00% |
| 2024-07 | +0.00% |
| 2024-08 | +0.00% |
| 2024-09 | +0.00% |
| 2024-10 | +0.00% |
| 2024-11 | +0.00% |
| 2024-12 | +0.00% |
| 2025-01 | +0.00% |
| 2025-02 | +0.00% |
| 2025-03 | -0.00% |
| 2025-04 | -0.06% |
| 2025-05 | +0.00% |
| 2025-06 | -0.15% |
| 2025-07 | -0.90% |
| 2025-08 | -0.92% |
| 2025-09 | +0.00% |
| 2025-10 | +0.00% |
| 2025-11 | +0.00% |
| 2025-12 | -0.13% |
| 2026-01 | +0.00% |
| 2026-02 | +0.00% |
| 2026-03 | -0.24% |
| 2026-04 | -0.07% |
| 2026-05 | -0.33% |
| 2026-06 | +0.00% |
| 2026-07 | +0.00% |
| 2026-08 | +0.00% |
| 2026-09 | +0.00% |

## Notes
OOS 2023-06-30 → 2026-09-12. Total return -6.79%, CAGR -2.17%, mean day -0.0058%, best day +1.39%, worst day -1.46%, 8% of days positive, 81% flat.

Kill-switch halts in the final run: ['2026-05-18T21:00:00+00:00 trailing_drawdown equity=93,217'].

Costs paid $3,985, funding paid $395 (on $100k start). Average -0.154R per trade, median hold 8 bars.

By side: short: 48 trades, $-4,016, avg -0.253R, hit 42%; long: 163 trades, $-2,773, avg -0.125R, hit 36%

By symbol: BTC/USDT:USDT: 64 trades, $874, avg -0.054R; ETH/USDT:USDT: 76 trades, $285, avg +0.008R; SOL/USDT:USDT: 71 trades, $-7,948, avg -0.419R

Exit reasons: {'stop': 188, 'signal': 12, 'time': 10, 'kill_switch': 1}; avg R by exit: kill_switch -0.18, signal +2.90, stop -0.40, time +0.85

Principles that fired (count of bars/setups): {'maker_filled': 211, 'skip_cooldown': 131, 'derisk_in_drawdown': 119, 'shrunk_to_budget': 75, 'skip_cost_vs_edge': 42, 'skip_risk_budget_full': 40, 'skip_consecutive_losses': 10, 'halt_trailing_drawdown': 1}

Evidence series without the DD halt (not used for the verdict): sharpe_oos -0.820, total_return -0.101, max_drawdown -0.113, n_trades_oos 283, avg_R -0.154

Trial Sharpes (daily, full period, single sleeve, 0.5% risk): inv_n48_k4.0_t1.5_both -1.81, inv_n48_k4.0_t1.5_long -1.20, inv_n48_k4.0_t3.0_both -1.81, inv_n48_k4.0_t3.0_long -1.17, inv_n48_k6.5_t1.5_both -1.08, inv_n48_k6.5_t1.5_long -0.69, inv_n48_k6.5_t3.0_both -1.18, inv_n48_k6.5_t3.0_long -0.56, inv_n96_k4.0_t1.5_both -1.28, inv_n96_k4.0_t1.5_long -0.72, inv_n96_k4.0_t3.0_both -1.19, inv_n96_k4.0_t3.0_long -0.97, inv_n96_k6.5_t1.5_both -1.29, inv_n96_k6.5_t1.5_long -0.86, inv_n96_k6.5_t3.0_both -1.36, inv_n96_k6.5_t3.0_long -0.69, inv_n168_k4.0_t1.5_both -1.09, inv_n168_k4.0_t1.5_long -0.49, inv_n168_k4.0_t3.0_both -1.34, inv_n168_k4.0_t3.0_long -0.58, inv_n168_k6.5_t1.5_both -1.11, inv_n168_k6.5_t1.5_long -0.46, inv_n168_k6.5_t3.0_both -1.12, inv_n168_k6.5_t3.0_long -0.24

Sweep diagnostic (96-bar support, k=4, forward 24h in ATR): BTC: 855 sweeps, 716 reclaimed → -0.09 ATR (hit 56%) vs not reclaimed -0.35 ATR (hit 48%); ETH: 731 sweeps, 566 reclaimed → +0.05 ATR (hit 57%) vs not reclaimed +0.05 ATR (hit 52%); SOL: 861 sweeps, 692 reclaimed → +0.27 ATR (hit 56%) vs not reclaimed -0.32 ATR (hit 46%)

1.5× costs: OOS Sharpe -0.48, halts ['2026-08-27T15:00:00+00:00 trailing_drawdown equity=95,818'].

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
  "entry_style": "maker",
  "level_lookback": [
    48,
    96,
    168
  ],
  "maker_ttl_bars": 1,
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
