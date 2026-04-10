---
title: Dharma Terminal Autonomous Build
path: mode_pack/claude/terminal-autonomous-build/SKILL.md
slug: dharma-terminal-autonomous-build
doc_type: skill
status: active
summary: Use this mode for bounded autonomous terminal architecture cleanup where the canonical shell, bridge boundary, and stop conditions are explicit.
source:
  provenance: repo_local
  kind: skill
  origin_signals:
  - mode_pack/contracts/mode_pack.v1.json
  - docs/governance/TERMINAL_OPERATING_MODEL.md
  - docs/plans/2026-04-09-terminal-autonomous-build-control.md
  cited_urls: []
  generated_hint: human_or_agent_authored_repo_doc
disciplines:
- frontend_engineering
- software_architecture
- operations
- verification
inspiration:
- operator_runtime
- product_surface
- verification
connected_relevant_files:
- mode_pack/contracts/mode_pack.v1.json
- docs/governance/TERMINAL_OPERATING_MODEL.md
- docs/plans/2026-04-09-terminal-autonomous-build-control.md
- docs/plans/2026-04-09-terminal-autonomous-build-issues.md
- scripts/start_terminal_autonomous_build_tmux.sh
- scripts/status_terminal_autonomous_build_tmux.sh
- scripts/stop_terminal_autonomous_build_tmux.sh
improvement:
  room_for_improvement:
  - Keep the lane focused on one terminal seam at a time.
  - Refine promotion gates only when the canonical shell or bridge contract materially changes.
  - Add stronger terminal smoke checks if the lane starts shipping larger UI changes.
  next_review_at: '2026-04-10T12:00:00+08:00'
pkm:
  note_class: skill
  vault_path: mode_pack/claude/terminal-autonomous-build/SKILL.md
  retrieval_terms:
  - terminal
  - autonomous
  - build
  - bridge
  - bun
  - operator
  evergreen_potential: medium
stigmergy:
  meaning: This file provides a repo-local autonomous terminal lane so long-running UI and bridge cleanup can proceed without reopening scope each cycle.
  state: active
  semantic_weight: 0.79
  coordination_comment: Use this mode only when terminal ownership, stop conditions, and non-goals are already explicit.
  trace_role: coordination_trace
curation:
  last_frontmatter_refresh: '2026-04-09T19:00:00+08:00'
  curated_by_model: Codex (GPT-5)
  future_model_handoffs:
  - GPT-5 Codex
  - Claude
  - Gemini
  - Local evaluator
  schema_version: pkm-phd-stigmergy-v1
name: dharma-terminal-autonomous-build
description: Autonomous terminal cleanup and refactor mode for bounded work on the canonical Bun shell and bridge boundary.
version: 1.0.0
allowed-tools:
- Read
- Grep
- Glob
- Bash
- Edit
- Write
---
# Dharma Terminal Autonomous Build

Use this mode only when the canonical terminal surface is known, the bridge boundary is documented, and the current tranche can be validated without widening into adjacent product systems.

## Objectives

- keep iterating on bounded terminal cleanup without re-opening the entire repo
- preserve one canonical Bun shell while harvesting safe structure from experimental work
- reduce bridge ambiguity instead of hiding it under new UI churn
- leave a truthful control trail after each tranche

## Required output

1. current lane
2. tranche completed
3. files changed
4. validation performed
5. residual risks
6. next bounded seam

## Rules

- treat `terminal/` as canonical unless a human explicitly changes that rule
- use `terminal-v2/` as a reference surface, not as a peer product to keep in parity
- keep `dharma_swarm/terminal_bridge.py` focused on transport and typed payload delivery
- move shell-local rendering and presentation logic into the Bun shell when touched
- stop on hidden ownership conflicts between `terminal/`, `terminal-v2/`, `operator_core`, and `terminal_bridge.py`

## Non-goals

- building a new `v3` shell in parallel
- broad style cleanup
- dashboard, API, or unrelated orchestration refactors
- reviving dual-shell parity as an end in itself

## Handoff

Use [2026-04-09-terminal-autonomous-build-control.md](/Users/dhyana/dharma_swarm/docs/plans/2026-04-09-terminal-autonomous-build-control.md) as the lane owner.
Record lane/runtime issues in [2026-04-09-terminal-autonomous-build-issues.md](/Users/dhyana/dharma_swarm/docs/plans/2026-04-09-terminal-autonomous-build-issues.md).
