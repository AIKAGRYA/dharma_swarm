---
title: Terminal Model Catalog Audit
path: docs/plans/2026-04-10-terminal-model-catalog-audit.md
slug: terminal-model-catalog-audit
doc_type: audit
status: active
summary: Reconciles terminal adapter catalogs, route policy targets, legacy model targets, and model-picker visibility.
source:
  provenance: repo_local
  kind: audit
  origin_signals:
  - dharma_swarm/terminal_bridge.py
  - dharma_swarm/terminal_adapters
  - dharma_swarm/tui/model_routing.py
  - dharma_swarm/provider_matrix.py
  - terminal/src/routePolicy.ts
  cited_urls: []
  generated_hint: human_or_agent_authored_repo_doc
disciplines:
- software_architecture
- terminal_ui
- provider_routing
stigmergy:
  meaning: Use this note before changing terminal model routing or claiming all advertised models are selectable.
  state: active
  semantic_weight: 0.86
  coordination_comment: The main risk is confusing adapter catalog coverage with route-policy picker coverage.
  trace_role: coordination_trace
curation:
  last_frontmatter_refresh: '2026-04-10T00:00:00+08:00'
  curated_by_model: Codex (GPT-5)
  schema_version: pkm-phd-stigmergy-v1
---
# Terminal Model Catalog Audit

## Finding Summary

The terminal currently has three model truths, and they are not identical:

- adapter handshake catalog: 29 models after this audit fix
- Bun model picker / route policy: 13 selectable route targets
- legacy Textual `MODEL_TARGETS`: 6 hard model targets plus 6 soft aliases

This is mostly coherent but under-explained. The route policy intentionally selects the operating lanes. The adapter catalog describes what the bridge adapter says it can call. Legacy `MODEL_TARGETS` still backs old Textual commands and natural-language aliases.

## Evidence

Primary sources:

- `dharma_swarm/terminal_bridge.py` emits handshake models from `adapter.list_models()`.
- `dharma_swarm/terminal_bridge.py` builds `model.policy.result` from `build_default_matrix_targets(profile="live25")`.
- `terminal/src/routePolicy.ts` treats policy targets as picker targets when `available` is true.
- `dharma_swarm/tui/model_routing.py` still owns legacy hard targets, soft targets, alias resolution, and legacy `/model list` formatting.
- `dharma_swarm/provider_matrix.py` owns the live25 lane target list.

Direct bridge probe before the fix showed 28 adapter models and 13 route-policy models. A joined local audit showed one concrete mismatch: `openrouter:qwen/qwen3-coder` was route-policy selectable but absent from both OpenRouter adapter catalogs. This audit fixes that catalog gap.

## Current Selectable Route Targets

These are the routes the Bun picker should expose from `model.policy.result` when configured:

| Provider | Model | Role | Tier |
| --- | --- | --- | --- |
| codex | gpt-5.4 | primary_driver | subscription |
| claude | claude-opus-4-6 | primary_driver | subscription |
| ollama | glm-5:cloud | research_delegate | free |
| ollama | deepseek-v3.2:cloud | bulk_builder | free |
| ollama | kimi-k2.5:cloud | research_delegate | free |
| ollama | qwen3-coder:480b-cloud | bulk_builder | free |
| ollama | minimax-m2.7:cloud | challenger | free |
| openrouter | moonshotai/kimi-k2.5 | research_delegate | paid_api |
| openrouter | z-ai/glm-5 | research_delegate | paid_api |
| openrouter | qwen/qwen3-coder | bulk_builder | paid_api |
| openrouter | openai/gpt-5-codex | bulk_builder | paid_api |
| openrouter | deepseek/deepseek-r1 | challenger | paid_api |
| openrouter | meta-llama/llama-3.3-70b-instruct:free | general_support | cheap |

## Adapter Catalog Only

These models are advertised by adapters but are not route-policy picker targets. That is not automatically a bug; it means they are catalog-callable but not first-class operating lanes.

| Provider | Model | Note |
| --- | --- | --- |
| claude | claude-sonnet-4-5 | soft alias only |
| claude | claude-sonnet-4-6 | adapter catalog only |
| claude | claude-opus-4 | adapter catalog only |
| claude | claude-haiku-4-5 | soft alias only |
| openrouter | xiaomi/mimo-v2-pro | legacy target only, not live25 route |
| openrouter | google/gemini-2.5-pro | soft alias only |
| openrouter | deepseek/deepseek-chat-v3-0324 | adapter catalog only |
| openrouter | nvidia/nemotron-3-super-120b-a12b:free | adapter catalog only |
| openrouter | nvidia/llama-3.1-nemotron-70b-instruct:free | adapter catalog only |
| openrouter | nvidia/nemotron-nano-9b-v2:free | adapter catalog only |
| openrouter | z-ai/glm-4.5-air:free | adapter catalog only |
| openrouter | zhipuai/glm-5-plus | adapter catalog only |
| openrouter | qwen/qwen3-coder:free | adapter catalog only |
| openrouter | qwen/qwen3-235b-a22b | adapter catalog only |
| openrouter | google/gemma-3-27b-it:free | adapter catalog only |
| openrouter | nousresearch/hermes-3-llama-3.1-405b:free | adapter catalog only |

## Confirmed Drift

- `dharma_swarm/tui/model_routing.py` still derives one legacy target from `ProviderType.CLAUDE_CODE` as `claude-code`, but the terminal adapter catalog does not expose `claude-code`; live runtime config resolves Claude Code to `claude-opus-4-6`.
- `dharma_swarm/tui/model_routing.py` has only 6 hard targets, while `terminal/src/routePolicy.ts` consumes 13 policy targets. The Bun terminal is on the 13-target policy path; old Textual model list output is not equivalent.
- Before this audit, `openrouter:qwen/qwen3-coder` was route-policy selectable but absent from OpenRouter adapter `list_models()`. That is now fixed in both terminal OpenRouter adapter paths.

## Cleanup Recommendation

Do not collapse all 29 adapter models into the primary picker. The picker should stay focused on route-policy lanes. Instead:

- standardize the language: call the 13 entries `Selectable routes`, and call the broader adapter list `Adapter catalog`.
- add a model-details pane or secondary section that shows adapter-catalog-only models with a reason they are not policy routes.
- migrate legacy `/model list` text away from `MODEL_TARGETS` or label it as legacy-only until Textual is retired.
- keep `provider_matrix.py` as the operating lane source and adapter `list_models()` as capability/catalog metadata.
- defer live generation testing across all remote models unless a human explicitly approves cost-bearing API calls.

## Verification Notes

This audit used local imports and direct bridge probes. It did not send inference prompts to paid or remote providers.

Context+ was attempted first for this turn, but all calls failed with `Transport closed`; this document therefore records a deterministic local audit rather than a Context+-backed semantic traversal.
