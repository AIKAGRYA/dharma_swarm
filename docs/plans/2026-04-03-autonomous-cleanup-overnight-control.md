---
title: Autonomous Cleanup Overnight Control
path: docs/plans/2026-04-03-autonomous-cleanup-overnight-control.md
slug: autonomous-cleanup-overnight-control
doc_type: plan
status: active
summary: Governing control file for running the non-TUI repo hygiene lane as an overnight autonomous loop without widening into TUI, dashboard, or unrelated runtime churn.
source:
  provenance: repo_local
  kind: cleanup_plan
  origin_signals:
  - docs/plans/2026-04-02-cleanup-control-center.md
  - docs/plans/2026-04-02-generated-artifact-control-center.md
  - docs/plans/2026-04-03-tui-baseline-protection-note.md
  - mode_pack/claude/autonomous-build/SKILL.md
  cited_urls: []
  generated_hint: human_or_agent_authored_repo_doc
disciplines:
- operations
- knowledge_management
- documentation
- software_architecture
- verification
inspiration:
- repo_topology
- operator_runtime
connected_relevant_files:
- docs/plans/2026-04-02-cleanup-control-center.md
- docs/plans/2026-04-02-generated-artifact-control-center.md
- docs/plans/2026-04-03-tui-baseline-protection-note.md
- docs/plans/2026-04-03-autonomous-build-skill-issues-and-fixes.md
- mode_pack/claude/autonomous-build/SKILL.md
- scripts/start_autonomous_cleanup_tmux.sh
- scripts/status_autonomous_cleanup_tmux.sh
- scripts/stop_autonomous_cleanup_tmux.sh
improvement:
  room_for_improvement:
  - Add a concrete external launcher only when a human-approved Claude/tmux owner is chosen.
  - Keep the lane queue updated as bounded seams are completed.
  - Archive completed seams instead of letting this become a backlog dump.
  next_review_at: '2026-05-17T12:00:00+08:00'
pkm:
  note_class: plan
  vault_path: docs/plans/2026-04-03-autonomous-cleanup-overnight-control.md
  retrieval_terms:
  - autonomous
  - overnight
  - cleanup
  - control
  - non-tui
  - repo hygiene
  evergreen_potential: medium
stigmergy:
  meaning: This file gives an overnight autonomous run one governing owner for the non-TUI cleanup lane so it can iterate without reopening the full repo ontology each cycle.
  state: active
  semantic_weight: 0.84
  coordination_comment: Start here for any overnight autonomous repo-hygiene run that must stay out of the TUI hot lane.
  trace_role: coordination_trace
curation:
  last_frontmatter_refresh: '2026-05-12T02:31:47+08:00'
  curated_by_model: Codex (GPT-5)
  future_model_handoffs:
  - GPT-5 Codex
  - Claude
  - Gemini
  - Local evaluator
  schema_version: pkm-phd-stigmergy-v1
---
# Autonomous Cleanup Overnight Control

## Purpose

This file is the lane owner for overnight autonomous cleanup on the non-TUI repo hygiene surface.

It exists so the run can keep moving without:

- reopening the whole repo from scratch each cycle
- drifting into TUI/dashboard hot work
- confusing doctrine work with runtime refactors

## Hard Boundaries

Do not touch:

- `terminal/`
- `dharma_swarm/operator_core/`
- `dharma_swarm/terminal_bridge.py`
- `dharma_swarm/tui/**`
- active dashboard hot-path implementation

Use [tui-baseline-protection-note.md](/Users/dhyana/dharma_swarm/docs/plans/2026-04-03-tui-baseline-protection-note.md) whenever the repo dirt threatens to blur the TUI truth.

## Governing Entry Points

Read in this order:

1. [cleanup-control-center.md](/Users/dhyana/dharma_swarm/docs/plans/2026-04-02-cleanup-control-center.md)
2. [generated-artifact-control-center.md](/Users/dhyana/dharma_swarm/docs/plans/2026-04-02-generated-artifact-control-center.md)
3. [autonomous-build-skill-issues-and-fixes.md](/Users/dhyana/dharma_swarm/docs/plans/2026-04-03-autonomous-build-skill-issues-and-fixes.md)

## Overnight Loop Contract

Each cycle should do exactly one bounded seam:

1. pick the strongest non-colliding seam
2. inspect the current state and path coupling
3. implement only if the seam is merge-safe
4. validate path truth, tracking truth, and authority truth
5. update control docs and issue log if the seam exposed a new constraint

## Allowed Seam Classes

- root residue and root-runbook doctrine
- docs authority and directory-local indexing
- specs precedence and companion-class clarification
- generated-artifact and verification-family doctrine
- substrate authority labeling

## Disallowed Overnight Behavior

- broad style normalization
- “clean everything” sweeps
- TUI or dashboard product polish
- runtime refactors disguised as cleanup
- deleting historical material first and asking questions later

## Current Best Queue

1. classify the remaining non-hot ambiguous `specs/` occupants that are still normative candidates
2. tighten cross-indexes after the `program*` root seam settles
3. continue report-family doctrine only where path coupling is already explicit
4. stop when the next seam would require hot-lane interference or unbounded research

## Recent Tranche Notes

- 2026-05-08, run `20260402T163603Z`: completed the `specs/` prompt-and-completion residue tranche by removing the stale tracked copies of `PARALLEL_BUILD_AGENT_PROMPTS_2026-03-19.md`, `SOVEREIGN_BUILD_PHASE_MASTER_PROMPT_2026-03-19.md`, and `VERIFICATION_COMPLETE.md` from `specs/`. The authoritative prompt and archive copies remain under `docs/prompts/` and `docs/archive/`.
- 2026-05-10, run `20260402T163603Z`: completed the `specs/` living-layers research duplicate tranche by removing the stale tracked `specs/research_living_layers/` copies. Active research companion truth remains under `specs/research/`; historical duplicate authority remains under `docs/archive/specs_research_living_layers/`.
- 2026-05-11, run `20260402T163603Z`: completed the `specs/` non-hot occupant classification tranche by updating `specs/README.md` with authority classes for every remaining tracked occupant. No files were moved, and the DGC terminal architecture spec bodies remained untouched as TUI-adjacent material.
- 2026-05-12, run `20260402T163603Z`: completed a root-control frontmatter discipline tranche by repairing malformed YAML in `docs/plans/2026-04-02-root-state-reconciliation.md`. No root files were moved, and no code, TUI, dashboard, or product hot-path files were touched.

## Required Output Per Cycle

- diagnosis
- tranche executed
- files changed
- validation performed
- residual risks
- next bounded seam

## Operator Note

This file governs the lane.
If a human wants a real overnight process owner, they can use:

- `bash scripts/start_autonomous_cleanup_tmux.sh`

Status and stop helpers:

- `bash scripts/status_autonomous_cleanup_tmux.sh`
- `bash scripts/stop_autonomous_cleanup_tmux.sh`

The launcher points the runtime at the repo-local skill and this control file:

- `dharma-autonomous-build`

Keep this control file as the lane contract.
