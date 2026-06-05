# Seam: Runtime Spine Adoption Saturation

Single-folder home for the next seam. All three deliverables landed in PR [#425](https://github.com/AmitabhainArunachala/dharma_swarm/pull/425) live here so the build pack can be assembled against one consolidated source of truth.

## Contents

| File | Purpose |
|---|---|
| `01_gap_matrix.md` | 16-surface coverage matrix with file:line evidence from `codex/runtime-truth-spine-v2`. Five PhD-grade holes, five adversarial questions, same-name collision risks, external anchors. |
| `02_master_spec.md` | Phase spec: goals G1–G5, non-goals NG1–NG6, done-when, four-slice plan (A/B/C/D), risk register R1–R8, single goal metric, three-source convergence, primary sources. |
| `03_codex_55_plan.md` | Full executable plan for Codex GPT-5.5 — preflight, four slice sections with diff-intent pseudocode, test file structures, commit messages, failure-mode playbook, process-discipline rules. |

## Phase in one line

Drive joined-or-adapter-ready ratio across the 16 mission surfaces from **56.25% (9/16) → ≥95%**, gated by a CI adoption-metric script.

## Four slices

- **A — Close legacy ledger bypass.** Quarantine `create_task_claim_sync` / `create_delegation_run_sync` at `runtime_state.py:1595` / `:1686`. CI invariant test.
- **B — Adapter saturation on five boundaries.** TaskBoard, MessageBus send, MessageBus consume, ToolRegistry, RuntimeArtifactStore.
- **C — Mapping receipts for five parallel lineages.** workflow_id, proposal_id, event_id, ontology_action_id (generate-side), engine_artifact_id.
- **D — Adoption metric script + CI gate.** Single number, single source of truth.

## Three-source convergence

Three independent reads named the same three slices with the same file:line targets:

- claude C2 synthesis (07:15:45Z)
- v0.0.3.3 clean-main audit §21
- v2 worktree `blast_radius_audit.md` §14

## Posture

Stage-1 evidence-only. Adversarial. Kill nothing — metabolize. Co-equal contributor: claude synthesizes, John merges, perplexity grounds.

## Build pack — what plugs in here

This folder is the docs surface. The build pack should add (without modifying these three files):

- `Buildpack.md` or `build-pack/` — concrete asset list (scripts, CI YAML, test stubs, deprecation shims) keyed to the four slices
- `metric/` — the adoption-metric script + fixtures (Slice D)
- `ci/` — invariant tests (Slice A guard, Slice B adapter contract tests, Slice C lineage mapping tests)
- `shims/` — deprecation paths for the legacy ledger helpers

Anything that reshapes the spec itself should be a follow-up PR amending `02_master_spec.md`, not silently overwriting it.
