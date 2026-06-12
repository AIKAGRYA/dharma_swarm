# Forge Swarm Evolution Arena v0 Measurement 10H Launch

**Date:** 2026-06-05  
**Status:** launch packet for 10-hour Codex 5.5 `/goal` run  
**Mission id:** `20260605T-swarm-evolution-arena-v0-measurement-10h`  
**Mode:** `measurement_mode` allowed by green preflight gates  
**Authority:** candidate-for-human-review only, no public or archive-fitness claim

## Objective

Run the sealed AutoResearch micro-gauntlet from the green task pack, compare
controls against a live decorrelated Dharma Swarm roster, compute paired
rubric-level `swarm_lift` with uncertainty, and close with one of:

- `positive_lift_candidate`
- `measured_negative`
- `inconclusive_low_power`
- `contaminated_quarantine`
- `blocked_with_evidence`

Do not claim "swarm evolution" unless final receipts prove positive
score-quality lift over both best-single-full-budget and same-budget Self-MoA.

## Relevant Files

- Main spec: `docs/specs/forge_packets/FORGE_SWARM_EVOLUTION_ARENA_V0_MEASUREMENT_GOAL.md`
- This launch packet: `docs/specs/forge_packets/FORGE_SWARM_EVOLUTION_ARENA_V0_MEASUREMENT_10H_LAUNCH.md`
- Preflight guard: `scripts/runtime/forge_swarm_evolution_arena_v0_preflight.py`
- Taskpack builder: `scripts/runtime/forge_swarm_evolution_arena_v0_taskpack_builder.py`
- Taskpack test: `tests/test_forge_swarm_evolution_arena_v0_taskpack_builder.py`
- Green run dir: `reports/forge/swarm-evolution-arena-v0-measurement/20260605T141000Z-measurement-candidate-taskpack`
- Readiness packet: `reports/forge/swarm-evolution-arena-v0-measurement/20260605T141000Z-measurement-candidate-taskpack/readiness_packet.json`
- Gates: `task_pack_gate.json`, `roster_gate.json`, `roi_governor.jsonl`
- Task manifest: `task_manifest.json`
- Closed-book prompt: `closed_book_prompt_set.md`
- Discard policy: `discard_policy.md`

## Verified Starting State

The green packet currently reports:

- `closeout_state=preflight_ready`
- `measurement_mode_allowed=true`
- `task_pack_gate=green`
- `roster_gate=green`
- `roi_governor=green`
- task pack: 3 sealed AutoResearch microtasks, 30 rubric items
- roster: OpenAI, Gemini, ZAI coding, Ollama Cloud

Known caveat: `tests/test_forge_swarm_evolution_arena_v0_preflight.py` is not
present in this worktree. Do not cite it as verification.

## Opening Commands

Run from `/Users/dhyana/dharma_swarm`:

```bash
make onboard
pytest -q tests/test_forge_swarm_evolution_arena_v0_taskpack_builder.py
python3 -m py_compile scripts/runtime/forge_swarm_evolution_arena_v0_preflight.py scripts/runtime/forge_swarm_evolution_arena_v0_taskpack_builder.py
python3 scripts/runtime/forge_swarm_evolution_arena_v0_preflight.py --run-dir reports/forge/swarm-evolution-arena-v0-measurement/20260605T141000Z-measurement-candidate-taskpack --write-readiness-packet --json --strict-exit
python3 scripts/runtime/autonomy_spine.py init --mission-id 20260605T-swarm-evolution-arena-v0-measurement-10h --mode research --risk Q2 --goal "Swarm Evolution Arena v0 Measurement 10H: run green-gated sealed AutoResearch taskpack against best-single, same-budget Self-MoA, and live swarm controls; compute paired rubric-level swarm_lift; no trainer/archive/public claims."
```

If the mission already exists, bind to it and continue; do not create a
duplicate unless the existing mission is stale and explicitly recorded.

## Measurement Rules

Candidate arms may read only candidate-visible task files:

- `tasks/*/visible/*`
- task instructions and allowed train/dev/challenge inputs

Candidate arms must not read:

- `sealed/*`
- `tasks/*/scorer.py`
- `tasks/*/rubric.json`
- `sealed/*/hidden_labels.csv`
- `sealed/*/oracle_submission.json`

Run closed-book memorization probes before any candidate sees task files.

Run these controls on the same 3 tasks:

- `nop`
- `each_solo_role`
- `best_single_full_budget`
- `same_budget_self_moa`
- `labels_only_sham_swarm`
- `full_live_dharma_swarm`

Enforce budget parity:

- each live swarm role max 20 model calls or USD 5 equivalent;
- best-single and Self-MoA receive matched total budget;
- log calls, tokens if available, wall time, retries, provider, model, and tool
  permissions.

Prove role liveness:

- separate invocation/session;
- prompt;
- transcript/log;
- artifact;
- handoff receipt;
- whether the artifact changed the final action.

Score only after submissions are written. The scorer may read sealed labels;
candidate arms may not.

## Required Artifacts

Write or update in the green run dir:

- `closed_book_results.jsonl`
- `control_results.jsonl`
- `paired_rubric_scores.jsonl`
- `role_liveness_receipts.jsonl`
- `handoff_receipts.jsonl`
- `budget_ledger.jsonl`
- `anti_goodhart_receipts.jsonl`
- `swarm_lift_report.json`
- `swarm_lift_report.md`
- `decision_packet.md`

If a dedicated measurement runner does not exist, build the smallest one first,
with tests. Do not manually improvise unverifiable rows.

## Metrics

Primary:

```text
swarm_lift = full_live_dharma_swarm_score - max(best_single_full_budget_score, same_budget_self_moa_score)
```

Also report:

- conditional success;
- routeable advantage;
- cost-normalized lift;
- paired bootstrap confidence interval or low-power warning.

Latency-only wins are not swarm wins.

## ROI Governor

Run the ROI governor every cycle and every 60-90 minutes. Stop or pivot if:

- receipts increase but evidence quality does not;
- role liveness collapses;
- budget parity breaks;
- contamination appears;
- same blocker repeats 3 times;
- task, intervention, hypothesis, and next action all repeat.

## Authority Boundaries

Forbidden without explicit operator lease:

- public benchmark submission;
- `external_confirmed=true`;
- trainer build;
- production router mutation;
- archive fitness mutation;
- public claim;
- push/merge/release.

A positive result is only `candidate_for_human_review`.

## Closeout

Do not close because time expired. Close only with a machine-readable decision
packet proving one of the valid closeout states.

Plain-language rule:

The win condition is not "many agents ran." The win condition is a reproducible,
budget-matched, contamination-clean score lift over best-single and same-budget
Self-MoA.
