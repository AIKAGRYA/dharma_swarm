---
title: Terminal Bridge Reduction Map
path: docs/plans/2026-04-10-terminal-bridge-reduction-map.md
slug: terminal-bridge-reduction-map
doc_type: plan
status: active
summary: Ownership map for reducing terminal_bridge.py without destabilizing the canonical Bun shell or reviving dual-shell drift.
source:
  provenance: repo_local
  kind: cleanup_plan
  origin_signals:
  - docs/governance/TERMINAL_OPERATING_MODEL.md
  - docs/plans/2026-04-09-terminal-autonomous-build-control.md
  cited_urls: []
  generated_hint: human_or_agent_authored_repo_doc
disciplines:
- frontend_engineering
- software_architecture
- verification
inspiration:
- operator_runtime
- canonical_truth
connected_relevant_files:
- dharma_swarm/terminal_bridge.py
- dharma_swarm/terminal_bridge_context.py
- dharma_swarm/terminal_bridge_renderers.py
- dharma_swarm/operator_core/command_payloads.py
- dharma_swarm/operator_core/runtime_payloads.py
- dharma_swarm/operator_core/workspace_payloads.py
- dharma_swarm/operator_core/session_payloads.py
- dharma_swarm/operator_core/routing_payloads.py
- terminal/src/protocol.ts
- docs/governance/TERMINAL_OPERATING_MODEL.md
improvement:
  room_for_improvement:
  - Promote more payload summaries into operator_core only when multiple surfaces need them.
  - Delete compatibility renderers only after terminal/ consumes payloads everywhere they matter.
  next_review_at: '2026-04-11T12:00:00+08:00'
pkm:
  note_class: plan
  vault_path: docs/plans/2026-04-10-terminal-bridge-reduction-map.md
  retrieval_terms:
  - terminal
  - bridge
  - reduction
  - ownership
  - operator_core
  evergreen_potential: medium
stigmergy:
  meaning: This note preserves the intended cut lines for terminal bridge reduction so future work tightens the architecture instead of moving responsibilities around arbitrarily.
  state: active
  semantic_weight: 0.84
  coordination_comment: Use this map before extracting more bridge logic or promoting any v2-era terminal structure.
  trace_role: coordination_trace
curation:
  last_frontmatter_refresh: '2026-04-10T10:30:00+08:00'
  curated_by_model: Codex (GPT-5)
  future_model_handoffs:
  - GPT-5 Codex
  - Claude
  - Gemini
  - Local evaluator
  schema_version: pkm-phd-stigmergy-v1
---
# Terminal Bridge Reduction Map

## Current Diagnosis

`dharma_swarm/terminal_bridge.py` still mixes four different roles:

1. stdio transport and request dispatch
2. canonical payload orchestration
3. terminal bootstrap and working-memory assembly
4. compatibility text rendering for shells that still expect rendered text

The strongest existing seams already live outside the bridge:

- canonical workspace payloads in [workspace_payloads.py](/Users/dhyana/dharma_swarm/dharma_swarm/operator_core/workspace_payloads.py#L1)
- canonical runtime payloads in [runtime_payloads.py](/Users/dhyana/dharma_swarm/dharma_swarm/operator_core/runtime_payloads.py#L1)
- canonical session payloads in [session_payloads.py](/Users/dhyana/dharma_swarm/dharma_swarm/operator_core/session_payloads.py#L1)
- canonical routing payloads in [routing_payloads.py](/Users/dhyana/dharma_swarm/dharma_swarm/operator_core/routing_payloads.py#L1)
- terminal-side payload consumption in [protocol.ts](/Users/dhyana/dharma_swarm/terminal/src/protocol.ts#L1)

## Completed Local Tightening

- bootstrap context, repo guidance, working memory, and system prompt assembly are isolated in [terminal_bridge_context.py](/Users/dhyana/dharma_swarm/dharma_swarm/terminal_bridge_context.py#L1)
- compatibility text renderers are isolated in [terminal_bridge_renderers.py](/Users/dhyana/dharma_swarm/dharma_swarm/terminal_bridge_renderers.py#L1)
- command graph and command registry payloads are isolated in [command_payloads.py](/Users/dhyana/dharma_swarm/dharma_swarm/operator_core/command_payloads.py#L1)
- model-policy summary construction is isolated in [routing_payloads.py](/Users/dhyana/dharma_swarm/dharma_swarm/operator_core/routing_payloads.py#L1)
- `build_agent_routes_payload` accepts the legacy list shape and the canonical dict envelope while still emitting the same versioned payload

## Keep In Bridge

- transport lifecycle: `run_stdio`, `_reader`, `_processor`, `_handle_request`
- request routing and adapter interaction: `_handle_handshake`, `_handle_command`, `_handle_action_run`, `_handle_session_start`
- payload emission helpers: `_emit`, `_emit_payload_result`
- approval persistence glue that joins runtime actions to session/audit history: `_record_runtime_approval_resolution`, `_record_permission_payload`
- bridge-only adapter bootstrapping: `_ensure_adapters`, `_available_provider_ids`, `close`

These belong in the bridge because they are the bridge.

## Move Toward operator_core

- any reusable session bootstrap contract fields once they stabilize beyond the terminal shell

Reason:

- `operator_core` already owns the canonical payload family
- shared route/session/runtime truth should not stay embedded in a shell bridge forever

## Move Toward terminal/

- compatibility text renderers:
  - `_render_command_graph_text`
  - `_render_command_registry_text`
  - `_render_operator_snapshot_text`
  - `_render_model_policy_text`
  - `_render_agent_routes_text`
  - `_render_evolution_surface_text`
  - `_render_session_catalog_text`
  - `_render_session_detail_text`
- preview extraction helpers:
  - `_build_workspace_preview`
  - `_build_runtime_preview`
  - `_find_line_value`
  - `_find_prefixed_line`
  - `_extract_git_branch`
  - `_extract_git_dirty`
  - `_extract_repo_risk`

Reason:

- these are shell-facing presentation and compatibility helpers
- the canonical Bun shell already has its own typed protocol consumption layer in `terminal/src/protocol.ts`

## Isolate But Keep Adjacent For Now

- bootstrap context and working memory
- repo guidance summarization
- system prompt assembly

These remain bridge-adjacent because they still feed `session.bootstrap`, but they should not stay embedded in the main bridge file. First extraction landed in [terminal_bridge_context.py](/Users/dhyana/dharma_swarm/dharma_swarm/terminal_bridge_context.py#L1).

Compatibility text renderers are also isolated but intentionally not promoted into `operator_core`. They exist to preserve old text surfaces while the canonical Bun shell continues moving toward typed payloads.

## Defer

- replacing stdio bridge transport with direct HTTP or direct adapter calls
- deleting `terminal-v2/`
- promoting the API server as the terminal’s only chat path

These are architecture decisions, not cleanup steps.

## Recommended Extraction Order

1. isolate bridge context and bootstrap-prompt helpers
2. isolate compatibility text renderers
3. decide which model-policy and command-summary shapes are truly shared and move only those into `operator_core`
4. add explicit event-order tests before changing streaming/session event flow
5. revisit transport architecture only after the bridge file is smaller and the canonical shell is stable
