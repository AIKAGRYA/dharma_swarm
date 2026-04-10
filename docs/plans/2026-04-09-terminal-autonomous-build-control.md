---
title: Terminal Autonomous Build Control
path: docs/plans/2026-04-09-terminal-autonomous-build-control.md
slug: terminal-autonomous-build-control
doc_type: plan
status: active
summary: Governing control file for bounded autonomous work on the Dharma terminal stack, canonical shell, and bridge boundary.
source:
  provenance: repo_local
  kind: cleanup_plan
  origin_signals:
  - docs/governance/TERMINAL_OPERATING_MODEL.md
  - mode_pack/claude/terminal-autonomous-build/SKILL.md
  - scripts/start_terminal_autonomous_build_tmux.sh
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
- canonical_truth
connected_relevant_files:
- docs/governance/TERMINAL_OPERATING_MODEL.md
- mode_pack/claude/terminal-autonomous-build/SKILL.md
- docs/plans/2026-04-09-terminal-autonomous-build-issues.md
- scripts/start_terminal_autonomous_build_tmux.sh
- scripts/status_terminal_autonomous_build_tmux.sh
- scripts/stop_terminal_autonomous_build_tmux.sh
- terminal/
- terminal-v2/
- dharma_swarm/terminal_bridge.py
improvement:
  room_for_improvement:
  - Keep the tranche queue concrete and seam-based.
  - Add narrower bridge extraction targets as they become validated.
  - Revisit the allowed surface list only when the terminal operating model changes.
  next_review_at: '2026-04-10T12:00:00+08:00'
pkm:
  note_class: plan
  vault_path: docs/plans/2026-04-09-terminal-autonomous-build-control.md
  retrieval_terms:
  - terminal
  - autonomous
  - build
  - control
  - bridge
  - bun
  evergreen_potential: medium
stigmergy:
  meaning: This file gives long-running terminal cleanup one governing owner so the work can stay bounded while still touching the live shell and bridge seam.
  state: active
  semantic_weight: 0.86
  coordination_comment: Start here for any unattended or semi-attended terminal cleanup run that must stay inside the canonical shell lane.
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
---
# Terminal Autonomous Build Control

## Purpose

This file governs bounded autonomous work on the Dharma terminal stack.

It exists so a long-running lane can improve the terminal without:

- treating multiple shells as equal truth
- widening into unrelated product systems
- confusing UI cleanup with bridge or runtime ownership

## Canonical Surface

- `terminal/` is the canonical Bun shell.
- `terminal-v2/` is a reference surface unless a human explicitly promotes it.
- `dharma_swarm/terminal_bridge.py` is a live bridge seam under reduction.

## Allowed Touch Surface

- `terminal/**`
- `terminal-v2/**` only for reference, extraction, or freeze notes
- `dharma_swarm/terminal_bridge.py`
- `dharma_swarm/operator_core/**` only when tightening shared terminal-facing contracts
- terminal-focused tests
- terminal governance and lane docs

## Hard Boundaries

Do not widen into:

- `dashboard/**`
- `api/**`
- unrelated orchestration or scheduler work
- broad repo-wide cleanup
- a new terminal product surface without an explicit promotion decision

## Tranche Contract

Each cycle should do exactly one bounded seam:

1. choose the highest-leverage terminal seam that does not collide with active ownership
2. inspect bridge, shell, and test blast radius before editing
3. implement only if the seam preserves one canonical shell
4. validate the touched shell or bridge path with focused tests or typecheck
5. record blockers when the next move would require promotion, migration, or human naming decisions

## Preferred Queue

1. extract stable shell helpers out of `terminal/src/app.tsx`
2. isolate shell-local rendering and request orchestration from `dharma_swarm/terminal_bridge.py`
3. consolidate duplicated terminal semantics only after the live shell owns the shared extraction target
4. stop before inventing a third shell or widening into unrelated runtime subsystems

## Required Output Per Cycle

- current lane
- tranche completed
- files changed
- validation performed
- residual risks
- next bounded seam

## Operator Note

This file governs the lane.

If a human wants to run the terminal lane in tmux, use:

- `bash scripts/start_terminal_autonomous_build_tmux.sh`

Status and stop helpers:

- `bash scripts/status_terminal_autonomous_build_tmux.sh`
- `bash scripts/stop_terminal_autonomous_build_tmux.sh`
