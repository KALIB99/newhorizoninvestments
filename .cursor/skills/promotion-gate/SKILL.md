---
name: promotion-gate
description: Procedure to promote a strategy from research → paper → live. Invoke before any promotion.
---
# Promotion gate

1. Confirm tearsheet exists with config hash matching code
   (`research/reports/<strategy>_<hash>.json`, hash == `Params.config_hash()`).
2. Judge verdict = ACCEPT on the tearsheet, recorded in tasks.md.
3. Run `python -m eval.gate <strategy>`: checks DSR p<0.05, PBO<0.3, OOS trades ≥ 200
   (intraday) or ≥ 100 (`horizon: multiday` in the tearsheet, or bars ≥ 1d — the Judge verifies
   the claim against median holding time, and may rule on an episode-count exception for
   carry-type books), cost-sensitivity 1.5×, per-regime PnL (positive in ≥ 2 of 3),
   walk-forward OOS/IS ≥ 0.5, Sharpe ≤ 3 sanity flag (≤ 6 when the tearsheet declares both
   `horizon: multiday` and `market_neutral: true` — CIO-approved 2026-10-11; the Judge verifies
   the neutrality claim against the trades artefact: paired legs, net delta ≈ 0). Exit code 0
   is required.
4. Research → Paper: add to `configs/paper.yaml`, no human signature needed. Record in
   CHANGELOG.md.
5. Paper → Live: requires ≥4 weeks paper, slippage within 30% of model
   (`execution/reports/fill_quality_<strategy>.json`), risk-manager APPROVE, and a
   human-signed `capital_allocation.yaml` entry. Initial allocation ≤10% of target.
   Agents never write to `capital_allocation.yaml` — they prepare the entry in the PR
   description and the human adds it.
6. Record the promotion in CHANGELOG.md with the evidence links (tearsheet, judge verdict,
   gate output, fill-quality report, risk-manager review).

Demotion follows the reverse path and needs only a risk-manager VETO or a postmortem drift
flag; it never needs a human signature.
