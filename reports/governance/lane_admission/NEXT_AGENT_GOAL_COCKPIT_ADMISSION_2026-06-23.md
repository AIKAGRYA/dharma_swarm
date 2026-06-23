# Next Agent Goal — Cockpit Admission / Control-Tower Hardening — 2026-06-23

## Objective

Turn the Operator Coherence Cockpit from a dirty-checkout candidate into a safely reviewable control-tower lane for Dharma Swarm multi-agent operation.

## Context

The operator routinely runs 4–10 agents across multiple local/remote providers, branches, windows, and worktrees. Therefore, “clean” means visible, preserved, classified, owned, receipted, and promotable — not single-threaded.

A cockpit candidate exists only in dirty checkout `/Users/dhyana/dharma_swarm` on branch `telos-ai-seed-v0-from-sandbox` at observed HEAD `cd610be3ccef`. It is not canonical `origin/main` yet.

Read first:

- `reports/governance/lane_admission/OPERATOR_COHERENCE_COCKPIT_LANE_PACKET_2026-06-23.md`
- `reports/governance/prod_readiness/PROD_READINESS_CONTINUATION_2026-06-23.md`
- `reports/governance/prod_readiness/PROD_GRADE_REVIEW_RESULTS_2026-06-22.md`
- `reports/governance/portfolio_truth_2026-06-22/ORGANISM_PORTFOLIO_NEXT_ACTIONS.md`

## Constraints

Do not run destructive operations:

- no `git reset`
- no `git clean`
- no stash drop
- no branch deletion
- no worktree prune
- no PR close/merge
- no raw union of dirty active tracks into `ACTIVE_TRACK.yaml`

Do not treat `/Users/dhyana/dharma_swarm` as canonical truth. It is a dirty candidate checkout.

## Tasks

1. Locate and inspect the cockpit implementation in `/Users/dhyana/dharma_swarm`:
   - `api/routers/operator_coherence.py`
   - `dharma_swarm/operator_core/operator_coherence_cockpit.py`
   - `scripts/runtime/operator_coherence_cockpit.py`
   - `dashboard/src/components/operator-coherence/`
   - `dashboard/src/lib/operatorCoherence.ts`
   - `dashboard/src/hooks/useOperatorCoherence.ts`
   - `tests/test_operator_coherence_cockpit.py`
   - `reports/governance/operator_coherence_cockpit.{json,md}`

2. Re-run and record the full declared verification if safe:
   - Python compileall for cockpit files
   - `uv run pytest -q tests/test_operator_coherence_cockpit.py`
   - `npm run lint -- src/lib/operatorCoherence.ts src/components/operator-coherence/CoherenceSections.tsx`
   - `uv run python scripts/runtime/operator_coherence_cockpit.py --output reports/governance/operator_coherence_cockpit.json --markdown reports/governance/operator_coherence_cockpit.md`
   - `python3 -m json.tool reports/governance/operator_coherence_cockpit.json`
   - `npm run build`

3. Produce an admission decision:
   - `ADMIT_AS_SUCCESSOR_TRACK`
   - `ADMIT_AS_RUNTIME_TRUTH_EXTENSION`
   - `KEEP_CANDIDATE_NEEDS_EXTRACTION`
   - `DO_NOT_ADMIT`

4. If admission is recommended, propose the exact track identity and owned surfaces. Do not edit `ACTIVE_TRACK.yaml` unless explicitly approved.

5. Draft a lane/admission packet schema if missing, with fields for:
   - lane id, agent/provider, branch, worktree, base ref, intended surfaces, touched surfaces, verification, receipts, status, dependencies, conflicts, promotion recommendation.

6. State whether this cockpit should become the read model used by the future `orchestration-arena-v1` / Dharma Forge track.

## Expected output

Write:

- `reports/governance/lane_admission/OPERATOR_COHERENCE_COCKPIT_ADMISSION_REVIEW_2026-06-23.md`
- `reports/governance/lane_admission/OPERATOR_COHERENCE_COCKPIT_ADMISSION_REVIEW_2026-06-23.json`

Final answer should include:

- verdict,
- verification results,
- changed/written files,
- blockers,
- whether operator approval is needed for branch extraction / PR creation.
