---
title: Terminal Autonomous Build Issues
path: docs/plans/2026-04-09-terminal-autonomous-build-issues.md
slug: terminal-autonomous-build-issues
doc_type: plan
status: active
summary: Live issue log for the terminal-specific autonomous build lane, capturing runtime problems, scope drift, and control-surface gaps.
source:
  provenance: repo_local
  kind: cleanup_plan
  origin_signals:
  - docs/plans/2026-04-09-terminal-autonomous-build-control.md
  - mode_pack/claude/terminal-autonomous-build/SKILL.md
  cited_urls: []
  generated_hint: human_or_agent_authored_repo_doc
disciplines:
- frontend_engineering
- operations
- verification
inspiration:
- operator_runtime
- canonical_truth
connected_relevant_files:
- docs/plans/2026-04-09-terminal-autonomous-build-control.md
- mode_pack/claude/terminal-autonomous-build/SKILL.md
- scripts/start_terminal_autonomous_build_tmux.sh
improvement:
  room_for_improvement:
  - Keep entries issue-shaped and operational.
  - Promote solved issues into stable lane docs when the mechanism is verified.
  next_review_at: '2026-04-10T12:00:00+08:00'
pkm:
  note_class: plan
  vault_path: docs/plans/2026-04-09-terminal-autonomous-build-issues.md
  retrieval_terms:
  - terminal
  - autonomous
  - issues
  - build
  - bridge
  evergreen_potential: medium
stigmergy:
  meaning: This note preserves the real friction around terminal autonomous execution so later runs improve the mechanism instead of rediscovering it.
  state: active
  semantic_weight: 0.78
  coordination_comment: Update this when the terminal lane fails because of runtime, scope, or ownership problems.
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
# Terminal Autonomous Build Issues

## Purpose

This is the live issue log for the terminal-specific autonomous build lane.

Record here when the lane fails because of:

- unclear shell authority
- bridge ownership ambiguity
- launcher/runtime failures
- drift into unrelated product systems

## Current Issues

### 1. No terminal-specific autonomous lane owner

Status: fixed

Problem:

- the repo had an autonomous cleanup lane, but it explicitly excluded `terminal/`, `dharma_swarm/terminal_bridge.py`, and TUI-adjacent hot paths
- that made the existing launcher unsafe for terminal recovery work

Fix:

- added [2026-04-09-terminal-autonomous-build-control.md](/Users/dhyana/dharma_swarm/docs/plans/2026-04-09-terminal-autonomous-build-control.md)
- added [mode_pack/claude/terminal-autonomous-build/SKILL.md](/Users/dhyana/dharma_swarm/mode_pack/claude/terminal-autonomous-build/SKILL.md)
- added terminal-specific tmux launch helpers

### 2. Risk of dual-shell drift during unattended runs

Status: guarded

Problem:

- unattended work can easily drift into maintaining parity between `terminal/` and `terminal-v2/` instead of preserving one canonical shell

Current posture:

- the lane contract treats `terminal/` as canonical
- `terminal-v2/` is reference-only unless a human explicitly changes that decision

### 3. External runtime ownership is still required

Status: open

Problem:

- adding a lane and launcher does not itself guarantee a healthy long-running external runtime
- the human or supervisor still has to launch and own the unattended process

Current posture:

- the lane mechanism exists in-repo
- runtime health still depends on the external Claude CLI account, token, and budget state
