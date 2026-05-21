# Dashboard Data Fidelity Audit

**Date:** 2026-05-20
**Author:** Devin (architecture review)
**Revision:** 1 — post-dkeys normalization

## Context

Provider keys are now present and multiple runtime lanes complete
successfully (OpenRouter, OpenAI, NVIDIA NIM, Ollama, Cerebras confirmed).
Remaining issues are env alias normalization (fixed in this PR), stale
process restart, and provider-specific failures (Groq access-denied,
SiliconFlow/Moonshot auth failures, Anthropic low credits).

This audit maps every dashboard page to its backend endpoint(s) and
assesses data fidelity: does the endpoint return real, meaningful data
when providers are live?

## Fidelity Categories

| Category | Meaning |
|---|---|
| **LIVE** | Endpoint returns real data from running system state |
| **PROVIDER-GATED** | Endpoint exists and works, but data is sparse until agents dispatch (needs live LLM) |
| **STUB** | Frontend page exists but backend endpoint is missing or returns placeholder |
| **BROKEN** | Endpoint or page has a known bug preventing data flow |

## Page-by-Page Assessment

### Tier 1: LIVE (real data flowing now)

| Page | Route | API Endpoint(s) | Status |
|---|---|---|---|
| Control Surface | `/dashboard/control-surface` | `/api/control-surface/rows`, `/api/control-surface/summary` | LIVE — 95 reconciled rows |
| Command Post | `/dashboard/command-post` | `/api/chat/status`, `/api/chat` (SSE) | LIVE — 6 profiles, streaming works |
| Runtime | `/dashboard/runtime` | `/api/health` | LIVE — system health |
| Overview | `/dashboard` | `/api/overview` | LIVE — swarm summary |
| Modules | `/dashboard/modules` | `/api/modules` | LIVE — truth map |
| Conv. Log | `/dashboard/log` | `/api/commands/traces` | LIVE — trace history |
| Claude Chat | `/dashboard/claude` | `/api/chat` | LIVE — profile-specific |
| GLM-5 Chat | `/dashboard/glm5` | `/api/chat` | LIVE — profile-specific |
| Qwen3.5 Chat | `/dashboard/qwen35` | `/api/chat` | LIVE — profile-specific |

### Tier 2: PROVIDER-GATED (endpoint exists, data sparse until agents run)

| Page | Route | API Endpoint(s) | Status | What populates it |
|---|---|---|---|---|
| Agents | `/dashboard/agents` | `/api/agents`, `/api/agents/spawn` | PROVIDER-GATED | Spawning an agent requires LLM provider |
| Tasks | `/dashboard/tasks` | `/api/commands/tasks` | PROVIDER-GATED | Tasks created by running agents |
| Evolution | `/dashboard/evolution` | `/api/evolution/archive`, `/api/evolution/fitness-trend`, `/api/evolution/dag` | PROVIDER-GATED | DarwinEngine needs agent runs |
| Telemetry | `/dashboard/telemetry` | `/api/telemetry/overview`, `/api/telemetry/routing`, `/api/telemetry/economics`, +5 more | PROVIDER-GATED | Telemetry accumulates from LLM calls |
| Stigmergy | `/dashboard/stigmergy` | `/api/stigmergy/marks`, `/api/stigmergy/heatmap`, `/api/stigmergy/hot-paths`, `/api/stigmergy/high-salience` | PROVIDER-GATED | Marks written by active agents |
| Lineage | `/dashboard/lineage` | `/api/lineage/{id}/dag`, `/api/lineage/{id}/provenance`, `/api/lineage/{id}/impact` | PROVIDER-GATED | Requires artifact IDs from agent runs |
| Ontology | `/dashboard/ontology` | `/api/ontology/types` | PROVIDER-GATED | Types exist but richness depends on agent activity |
| Gates | `/dashboard/gates` | `/api/verify/*` | PROVIDER-GATED | Gate checks run during agent dispatch |
| Audit | `/dashboard/audit` | `/api/verify/*` | PROVIDER-GATED | Same as gates |
| Eval | `/dashboard/eval` | `/api/evolution/*` | PROVIDER-GATED | Eval data from agent fitness scoring |
| Models | `/dashboard/models` | `/api/agents` (model field) | PROVIDER-GATED | Model usage stats from agent runs |
| Qwen3.5 Telemetry | `/dashboard/qwen35/telemetry` | `/api/telemetry/*` | PROVIDER-GATED | Profile-specific telemetry |
| Timeline | `/dashboard/timeline` | `/api/viz/timeline` | PROVIDER-GATED | Time-series from agent events |

### Tier 3: STUB / MISSING ENDPOINT

| Page | Route | Expected Endpoint | Status | Fix |
|---|---|---|---|---|
| Observatory | `/dashboard/observatory` | `/api/agents/observatory` | **STUB** — endpoint does not exist | Need to implement observatory endpoint in `api/routers/agents.py` |
| Ecosystem | `/dashboard/ecosystem` | `/api/viz/snapshot`, `/api/viz/events` | Partial — viz endpoints exist but ecosystem graph needs ReactFlow data | Wire viz snapshot to ecosystem ReactFlow component |
| Synthesizer | `/dashboard/synthesizer` | Unknown | **STUB** — multi-source aggregation page, no dedicated endpoint | Design synthesizer API |
| Workflows | `/dashboard/workflows` | None | **STUB** — "Coming soon" placeholder | Future work |
| Blocks | `/dashboard/blocks` | None | **STUB** — "Coming soon" placeholder | Future work |

## Env Alias Mismatches (Fixed in This PR)

| dkeys name | dharma_swarm name | Status |
|---|---|---|
| `GEMINI_API_KEY` | `GOOGLE_AI_API_KEY` | **Fixed** — normalize_env_aliases() + load_runtime_env.sh |
| `NVIDIA_API_KEY` | `NVIDIA_NIM_API_KEY` | **Fixed** — normalize_env_aliases() + load_runtime_env.sh |
| `NIM_API_KEY` | `NVIDIA_NIM_API_KEY` | Already aliased (load_runtime_env.sh) |
| `PERPLEXITY_API_KEY` | `PPLX_API_KEY` | **Fixed** — normalize_env_aliases() + load_runtime_env.sh |

## Provider Status (from user's local audit)

| Provider | Key Present | Status |
|---|---|---|
| OpenRouter | Yes | **Working** |
| OpenAI | Yes | **Working** |
| NVIDIA NIM | Yes | **Working** |
| Ollama | Yes | **Working** |
| Cerebras | Yes | **Working** |
| Anthropic | Yes | **Low credits** — blocked |
| Groq | Yes | **Access denied** |
| SiliconFlow | Yes | **Auth failure** |
| Moonshot | Yes | **Auth failure** |
| Google AI / Gemini | Yes (as GEMINI_API_KEY) | **Fixed** — alias normalization |

## Summary

- **9 pages fully LIVE** — producing real data now
- **13 pages PROVIDER-GATED** — endpoints exist, data sparse until agents dispatch (which is now possible with working providers)
- **5 pages STUB** — need backend work (Observatory, Ecosystem wiring, Synthesizer, Workflows, Blocks)
- **4 env alias mismatches** — 3 fixed in this PR, 1 already handled

## Recommended Next Actions

1. **Restart stale processes** — Any operator/API process started before dkeys updates needs restart to pick up normalized env vars
2. **Spawn a test agent** — With OpenRouter/OpenAI working, spawn one agent to validate the full pipeline (agent → task → trace → telemetry → dashboard)
3. **Implement `/api/agents/observatory`** — Most impactful missing endpoint
4. **Wire Ecosystem page** — Connect viz snapshot to ReactFlow component
