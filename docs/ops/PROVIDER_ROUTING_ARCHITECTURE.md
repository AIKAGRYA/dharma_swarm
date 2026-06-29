# Provider Routing Architecture — the one place

**Status:** canonical · **Track:** `provider-routing-consolidation-2026-06` · **Opened:** 2026-06-21

This is the single reference for how dharma_swarm decides **which provider and
which model** runs a task. If any other doc or code comment disagrees with the
precedence below, this document wins and the code is the bug.

It supersedes the scattered, drifted understanding mapped in the 2026-06-21
audit. The historical snapshot at `docs/_archive/2026-04/MODEL_ROUTING_MAP.md`
is stale; do not trust it.

---

## 1. The North Star (operator-locked 2026-06-21)

> One routing brain, in one place, that sends any task to any model on any
> provider. By default it reaches for the **most capable** model available
> (power-first), preferring **direct first-party** paths (NIM, Ollama Cloud,
> z.ai/Zhipu, …) over aggregators like OpenRouter. It is **malleable**: you or
> a task can pin a specific provider/model and that **wins**; you can nudge it
> cheaper/faster; and it adapts from outcomes — without becoming opaque.

Four decisions are LOCKED:

| # | Decision | Choice |
|---|----------|--------|
| 1 | Default selection | **Power-first** — most capable model by default; cost is an opt-in nudge |
| 2 | Explicit request | **Pin + safe fallback** — exact provider/model wins; fall back only if down / no live key |
| 3 | Architecture | **Unify, keep smarts** — keep affinity/EWMA/reward/canary; collapse under ONE precedence |
| 4 | New first-party path | **z.ai / Zhipu / GLM direct** (Moonshot/Kimi stays via OpenRouter for now) |

---

## 2. THE PRECEDENCE (the whole system in one line)

```
explicit > capability/power > malleable overlays > learned > availability prune > fallback walk
```

Expanded, in strict order:

1. **Explicit** — if the request (task metadata or caller) names a **model** or a
   **provider**, honor it as the *selection*. A named model resolves to its
   best route via `model_pool`; a named provider resolves to that provider's
   default model. This is **pin + safe fallback**: the named choice is chain
   position 0; the rest of the ranked chain follows so a dead key / down
   provider degrades gracefully instead of failing (unless the caller asks for
   hard-pin-no-substitute).
2. **Capability / power** — with nothing explicit, rank candidates by
   intelligence/power score (`model_hierarchy` intelligence seed, then learned
   EWMA), **most powerful first**. This is the power-first default.
3. **Malleable overlays** — named, ordered, optional adjustments: cost
   preference (`SmartRouter` tier), decision path (REFLEX/DELIBERATIVE/ESCALATE),
   language quality, tooling need. Each is a documented pass, not tangled logic.
   Cost is OPT-IN: a task sets `prefer_low_cost` to trade power for price.
4. **Learned** — session affinity, routing-memory EWMA, reward ranking, canary.
   These reorder the *post-decision* chain as tiebreak overlays; they never
   override an explicit selection.
5. **Availability prune** — drop providers that are not registered or whose key
   the liveness oracle reports dead (`key_oracle`, fail-open on unknown).
   **First-party providers are preferred; OpenRouter is last** (aggregator).
6. **Fallback walk** — execute the chain in order; first success wins; on
   failure try the next; record the outcome (feeds the learned overlays).

---

## 3. Module map — who owns what (unchanged data layer, fixed decision layer)

### Data / registry layer (already consolidated — preserved as-is)

| Module | Owns |
|--------|------|
| `model_hierarchy.py` | Provider tiers, ordering, **intelligence/power scores**, lane roles, path priorities |
| `model_pool.py` | Logical models, each with an ordered cross-provider **route** list; power floor; `_PROVIDER_RANK` (first-party preferred) |
| `model_defaults.py` | The single per-provider default-model leaf (`_PROVIDER_DEFAULTS`) |
| `evolution_roster.py` | Historical seed catalog feeding `model_pool` |
| `api_keys.py` | Every `*_API_KEY` env name + aliases; one key home `~/.dharma/agent_keys.env` |
| `runtime_provider.py` | `resolve_runtime_provider_config` + `create_default_provider_map` (registration) |

### Decision layer (the target of this track)

| Module | Role after consolidation |
|--------|--------------------------|
| `decision_router.py` | Classifies path: REFLEX / DELIBERATIVE / ESCALATE |
| `provider_policy.py` | **The one selection owner.** Applies the precedence in §2. Now consults `context["preferred_provider"]` + requested model (Stage 1). |
| `router_v1.py` | Signal enrichment (language, complexity, reasoning) — advisory inputs only |
| `smart_router.py` | Cost-tier overlay (pass 3), invoked only when `prefer_low_cost` |
| `providers.py` | `ModelRouter`: builds + prunes the chain, runs the learned overlays (pass 4) and the availability prune (pass 5), walks the chain |

> **Drift this fixes:** today `provider_policy` selects purely from seed order
> and never reads the explicit `preferred_provider` that `agent_runner` already
> puts in the context — so "use this provider" is silently ignored. And two
> rank systems disagree (`CANONICAL_SEED_ORDER` free-first vs
> `_PROVIDER_RANK` first-party-first). Stage 1 fixes the first; Stage 2 unifies
> the second into the single power-first, first-party-preferred order.

---

## 4. Malleability surface — how to steer it

- **Per-task (code):** set `provider`/`model` on the request, or
  `task.metadata["preferred_provider"]` / `["preferred_model"]` to pin;
  `["prefer_low_cost"] = True` to nudge cheaper;
  `["allow_provider_routing"] = True` to widen a pinned agent back to full
  routing.
- **Env knobs (runtime):** `DGC_ROUTER_*` (learning, memory, sticky, canary,
  telemetry, audit) and `DGC_SMART_ROUTER_ENABLED`. `DHARMA_FORCE_ANTHROPIC_API`
  forces the metered API instead of the Claude Max CLI lane.
- **Keys (operator):** add via `dkeys`; they land in `~/.dharma/agent_keys.env`
  and are read only through `api_keys.py`. A provider with no live key is pruned
  automatically.

---

## 5. Migration — staged, each test-guarded

1. **Stage 1 — keystone (explicit-wins).** `provider_policy` consults
   `context["preferred_provider"]` and the requested model as a *selection*
   (pin + safe fallback). Fixes the observed `--provider claude_code` failure.
2. **Stage 2 — unify ranking.** One power-first, first-party-preferred order;
   retire the seed-vs-pool contradiction.
3. **Stage 3 — first-party z.ai/Zhipu.** `ZHIPU` enum + resolution + factory +
   `ZhipuProvider`, so GLM does not need OpenRouter.
4. **Stage 4 — collapse & document overlays.** The six passes named and ordered
   per §2; one audit log line per decision.
5. **Stage 5 — drift cleanup.** `AgentConfig` default model, hardcoded literals,
   delete dead `providers_extended.py`, reconcile `.env.example`/`.env.template`
   with the 18-member enum.

---

## 6. Invariants that must hold

- One selection owner (`provider_policy.route`); no second router decides.
- Explicit selection is never silently overridden by a learned overlay.
- Every provider with a live key is reachable AND selectable.
- First-party direct paths rank above OpenRouter.
- No new model/key/route registry is created; everything converges on the data
  layer in §3.

---

## 7. Consolidation status (2026-06-21)

Stages 1–4 shipped; Stage 5 done with scoped exceptions recorded below.

- **Stage 1 — explicit-wins:** DONE. `provider_policy` honors
  `context["preferred_provider"]`/`["preferred_model"]` as selection.
- **Stage 2 — power-first default:** DONE. `power_first` base ordering;
  `preferred_low_cost` defaults False (request + production derivation).
- **Stage 3 — z.ai/Zhipu first-party:** DONE. `ProviderType.ZHIPU`, default
  `glm-5.2`, endpoint `https://api.z.ai/api/coding/paas/v4`. The coding endpoint
  is intentional for coding-plan keys; live calls require the environment's
  network egress allowlist to include `api.z.ai`.
- **Stage 4 — one precedence, documented + tested:** DONE. See §2 and
  `tests/test_provider_routing_explicit.py`.
- **Stage 5 — drift cleanup:** env templates updated for Zhipu. The following
  were **deliberately NOT changed** (out of scope / unsafe in this track):
  - `AgentConfig.model = "claude-sonnet-4-20250514"` — agent-identity surface,
    a codebase-wide convention across 10+ files; belongs to the identity owners,
    not routing. The router resolves model hints from the data layer regardless.
  - `providers_extended.py` — NOT dead code: `test_providers_quality_track.py`
    imports its `MoonshotProvider`. Left intact.
  - Model-specific literals in `cost_tracker.py` (pricing table), TUI
    `ModelProfile`s, and CLI `--model` defaults — legitimately per-model config,
    not routing drift.
