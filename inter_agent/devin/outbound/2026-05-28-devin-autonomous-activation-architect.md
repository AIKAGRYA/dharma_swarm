# Devin Outbound — Autonomous Activation Architect Three-Deliverable Drop

**From:** Devin (Roaming) `AGT-DEVIN_ROAMING_2987D222`
**Authority:** `external_worker_evidence_only`
**Date:** 2026-05-28
**Branch:** `devin/2026-05-28-autonomous-activation-architect` (forked from `devin/2026-05-28-autonomous-expansion-audit`, parent PR #369)
**Active track:** `runtime-truth-spine-2026-06` — **not displaced.**

## What landed

Three docs-only reports under `docs/reports/`:

1. `autonomous_activation_onboarding_receipt_2026-05-28.md` — 17-field onboarding receipt per `docs/governance/ONBOARDING_RECEIPT.md`. Required by Master Prompt step 3 before any architecture proposal.
2. `autonomous_activation_map_v1.md` — 11-stage chain (intent → recursive improvement) mapped to existing owner surfaces. Per stage: existing owner, missing adapter, activation risk, telos risk, economic risk, ecological risk, operational leverage. Stages already wired (1, 5, 6) explicitly marked "don't touch."
3. `autonomous_activation_minimal_metabolic_loop_v1.md` — THE first loop. Selected: **Operator Brief Publication wedge.** Why this over Trading Lab / scout outreach / benchmark publication / API services / grants: explicitly justified. Full timeline T+0 to T+60d with kill conditions wired to `fractal_room.evaluate_kill_conditions`. Nine receipts per iteration enumerated. Reinforcement signals defined.
4. `autonomous_activation_pr_sequence_v1.md` — 6 PRs, ~640 LOC total. Each PR: exact owner surfaces, touched files, kill conditions, rollback strategy, benchmark/KPI, acceptance criteria, ecological cost, welfare assessment, replay command. **PR-A6 explicitly WAITs on truth-spine track closure.**

## Active-track defense

None of the proposed PRs touch `dharma_swarm/spine/**`, `orchestrator.py`, `agent_runner.py`, `runtime_state.py`, `tests/test_dispatch_dropoff_sources.py`, or `tools/spine_check.py`. All proposed modules are new files, ≤ 150 LOC each, feature-flagged default off. **Recommendation: do not land the PR sequence until `runtime-truth-spine-2026-06` blockers close**, or open `autonomous-activation-2026-07` as parallel track in `ACTIVE_TRACK.yaml`.

## Doctrinal compliance audit

| Doctrine | Compliance |
|---|---|
| "Growth allowed; unwitnessed growth not" | ✅ 9 receipts per loop iteration |
| "Autonomy allowed; unreceipted autonomy not" | ✅ `closure_v0.EvidenceReceipt` mandatory before `NextDecision` |
| "Revenue allowed; telos-corrupting revenue not" | ✅ STEELMAN gate + Jagat Kalyan constraint + free issues first |
| "Expansion allowed; ecologically blind not" | ✅ Per-PR compute cost noted; revenue-wedge burn cap $2k/mo |

## Forbidden actions audit

All 9 forbidden actions from Master Prompt cross-checked in PR sequence's "What this sequence does NOT do" table. **None proposed.** `evolution.py` `shadow_mode=True` invariant defended in PR sequence CI gate matrix.

## What I'm NOT asking Devin to do

This drop is for the operator. Devin keeps `external_worker_evidence_only` authority. Future activation PRs (A1–A6) require human approval per `VENTURE_CELL_REVENUE_WEDGE.md`.

## What I AM asking the operator to decide

1. Does the Operator Brief Publication wedge match the operator's intuition for "the first metabolic loop"? (Top alternatives: Trading Lab, benchmark publication — both rejected with reasoning.)
2. Is the 6-PR sequence the right granularity, or should it consolidate (e.g., A1+A2 in one PR)?
3. Should the WAIT gate on PR-A6 be replaced with an explicit parallel-track declaration in `ACTIVE_TRACK.yaml`?
4. Does any stage's risk grid undercount a risk class?

## Replay commands (when PRs eventually land)

```bash
# PR-A1
pytest tests/test_venture_cell_fsm.py -q

# PR-A2
pytest tests/test_work_packet_proposer.py -q

# PR-A3
pytest tests/test_kaizen_publisher.py -q

# PR-A4 (the wedge)
pytest tests/test_operator_brief_publisher.py -q

# PR-A5
pytest tests/test_world_model_witness.py -q

# PR-A6 (WAIT)
pytest tests/test_operator_brief_cron.py -q
```

## PR

To be opened against `main` (or rebased onto `main` after PR #369 merges).

— end notice —
