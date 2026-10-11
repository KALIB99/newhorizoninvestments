# Changelog

Promotions and demotions are recorded here with evidence links (promotion-gate step 6).
Format: `YYYY-MM-DD | <strategy>@<confighash> | research→paper | paper→live | demoted | evidence...`

## Unreleased

- 2026-10-09 | data | `data.ingest` from data.binance.vision (perp 5m/1h + funding, spot 1h, 2023-01 → 2026-09); `data.load` now returns UTC timestamps.
- 2026-10-09 | trader | `trader.principles` (human-trader rules; can only tighten risk/limits.py) and `trader.engine` (bar-by-bar portfolio simulator using the real KillSwitch). Tests: tests/test_trader.py.
- 2026-10-09 | disciplined_daytrader@dbb0eb4bd85e | Reject | research/reports/disciplined_daytrader_dbb0eb4bd85e.md
- 2026-10-09 | funding_carry@c6aea8f61b87 | Insufficient evidence (11 OOS trades) | research/reports/funding_carry_c6aea8f61b87.md
- 2026-10-10 | data | 10 more coins ingested (perp + spot 1h): BNB XRP DOGE ADA AVAX LINK LTC DOT TRX BCH. `eval.costs.SPREAD_BPS_BY_BASE` placeholder spreads; carry now caps concurrent pairs at the 2.0× gross limit.
- 2026-10-10 | disciplined_daytrader@87ddd1db2d42, @328aeb491316 | Reject (trailing-DD halt OOS) | research/reports/
- 2026-10-10 | funding_carry@42f4825e4859, @10a3a9221ede | Insufficient evidence (19–20 OOS trades) | research/reports/
- 2026-10-10 | removed | `disciplined_daytrader`, `funding_carry`, `signals.momentum`, `signals.mean_reversion` and their tearsheets removed by CIO instruction (tasks.md T-002/T-009/T-010/T-011). Shared pipeline kept as `research.common`.
- 2026-10-10 | trader | engine: structural stop prices (`SleeveInputs.stop_px`, size shrinks on a gap away, entry skipped on a gap through), breakeven ratchet (`breakeven_r`), armed ATR trail (`trail_after_r`, `trail_atr`). Defaults unchanged; tests in tests/test_trader.py.
- 2026-10-10 | cyclical_inversion@f6ba4f3a085f | Reject (trailing-DD halt OOS; all 24 trials negative) | research/reports/cyclical_inversion_f6ba4f3a085f.md · tasks.md T-013
- 2026-10-10 | cyclical_inversion@ede72ec78a6e, @f1f78f878d25 | Reject (pre-registered wider-stop follow-up, prior trials carried) | tasks.md T-014
- 2026-10-10 | cyclical_inversion@72fb5e9b8e1e (10 new coins), @6ac762315bd4 (all 13) | Reject (out-of-universe; trailing-DD halt Apr 2024 on both; BTC/SOL reclaim diagnostic does not replicate) | tasks.md T-016
- 2026-10-10 | trader | engine: maker entry style (`SleeveConfig.entry_style="maker"`, `maker_ttl_bars`); research pipeline reports an un-halted evidence series when the DD halt fires. Tests in tests/test_trader.py.
- 2026-10-10 | cyclical_inversion@37a81ade45c2 | Reject (maker entries; gross expectancy ≈ −0.03R; family closed at 104 trials) | tasks.md T-017
- 2026-10-10 | constitution | research/reports/constitution_review.md: 15% vol target × −8% sticky halt is inconsistent (halts a Sharpe-1 book ~100% within 3y). AGENTS.md priors updated with the horizon lesson (T-019).
- 2026-10-10 | **constitution amended, CIO-approved (T-018)** | vol target 0.15 → 0.10; trailing halt −0.08 → −0.15; −0.08 is now a de-risk tier (risk × 0.5, alert, auto-recovers). `eval.gate` OOS-trade floor 200 intraday / 100 multiday (`Tearsheet.horizon`). Tests prove every tier triggers. Evidence: tests/test_risk_limits.py, tests/test_kill_switch.py, tests/test_trader.py, tests/test_gate.py.
- 2026-10-10 | funding_carry@c6aea8f61b87, @10a3a9221ede | restored on CIO approval; tearsheets reproduce bit-for-bit; Insufficient evidence (11 / 20 trades vs multiday floor 100) → Judge ruling requested on episode count and Sharpe plausibility | tasks.md T-002
- 2026-10-11 | data | 1h perp + spot extended to 2020-01 for all 13 symbols (data.ingest, archive). SOL/XRP/LTC/TRX perps fail the 0.10% gap-fraction check over 2020–22 (72-bar holes); recorded in data/reports.
- 2026-10-11 | funding_carry@ab992575744a, @e44affb7ad96 | **re-submission (T-002)**: cash+margin cap (0.25×/leg), 2020→2026 history, episodes + block-bootstrap CI, cash-yield and margin sensitivities; deferred exits on venue gaps + hard finite-equity check after a silent NaN failure on the 2020-12-21 spot outage. OOS +64% / +73%, Sharpe 5.3 / 4.9, PBO 0.36 / 0.64, 8 / 7 episodes. **Judge #2: INSUFFICIENT EVIDENCE — forward paper only**; new defects: is_gap dropped, no in-hold collateral check, no running gross check (SOL +458% → 2.8× gross), basis-stop re-entry. tasks.md T-002.
- 2026-10-11 | **gate amended, CIO-approved (T-002)** | Sharpe plausibility cap 3.0 → 6.0 only when a tearsheet declares both `horizon: multiday` and `market_neutral: true` (`eval/gate.py`, `eval/report.py`; Judge verifies the neutrality claim). Directional/intraday books unchanged. Test in tests/test_gate.py. funding_carry tearsheets regenerated with the flag; gate now fails on verdict + trade count only.
- 2026-10-10 | funding_carry | **Judge: INSUFFICIENT EVIDENCE, exception denied** (~4 independent episodes). Fixed the defects it found: walk-forward stitch dropped deselection-exit bars (series was 3% richer than the ledger), entries on the last active bar, APR hard-coded to 8h funding, IS Sharpe not pooled. New tests/test_funding_carry.py reconciles Σ trade PnL to the equity series (≤ 1%). Corrected OOS +12.1% / +12.3%, Sharpe 4.70 / 3.72. Re-submission conditions in tasks.md T-002.

- 2026-10-02 | bootstrap | repo skeleton, constitution, rules, subagents, skills, eval.gate, risk limits + kill switch, broker interface + LIVE gate, CI. No strategies.
