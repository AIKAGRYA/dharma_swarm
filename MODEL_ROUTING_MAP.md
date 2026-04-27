# Model Routing Map — dharma_swarm

**Generated:** 2026-04-04 | **Purpose:** Complete map of how every LLM call flows through the system.
Three calling surfaces exist. This document maps each one, identifies
inconsistencies between them, and preserves historical context for the
now-resolved HuggingFace blocker.

**Drift status:** Updated 2026-04-27 as a historical routing-drift
register. The canonical routing reference is
`docs/architecture/MODEL_ROUTING_CANON.md`; the canonical doc read
order is `docs/governance/CANONICAL_DOC_STACK.md`; current
operational state is summarized in `reports/ops/REPO_STATE_NOW.md`.

**Important correction:** the old `huggingface_hub` import crash is
resolved and must not be treated as the current Loop 1 blocker. This
map still documents real routing fragmentation, but it does not claim
repo-wide routing coherence or implementation fixes without tests.

---

## The Three Calling Surfaces

### Surface 1: Swarm Agents (orchestrate_live → swarm → orchestrator → agent_runner → providers)
**How it works:** SwarmManager.init() creates a ModelRouter via create_default_router(). The ModelRouter holds 18 provider instances. When an agent needs to call an LLM, agent_runner._invoke_provider() calls ModelRouter.complete_for_task() which:
1. Calls router_v1.build_routing_signals() to classify the request (the old HuggingFace import crash is resolved)
2. Calls ProviderPolicyRouter.route() to pick a provider chain
3. Tries each provider in the chain with fallback
4. Records telemetry, EWMA scores, and audit logs

**Agent identity model:** Agents are defined in startup_crew.py with: name, role (AgentRole enum), thread, provider (ProviderType enum), model (string). On boot, _resolve_default_crew() checks for API keys in order: Ollama Cloud → OpenRouter → Claude Code CLI. Each agent gets the SAME provider and model — there's no per-agent model differentiation in the default crew.

**Persistent agents:** PersistentAgent (persistent_agent.py) has: name, role (AgentRole), provider_type (ProviderType), model (string). Conductors (conductors.py) are PersistentAgents hardcoded to: Claude conductor = ProviderType.ANTHROPIC + "claude-opus-4-6", Codex conductor = ProviderType.ANTHROPIC + "claude-sonnet-4-20250514".

**AutonomousAgent** (autonomous_agent.py) has AgentIdentity with: name, role, system_prompt, model (default "claude-sonnet-4-20250514"), provider (default "anthropic"), max_turns, allowed_tools, working_directory. This class does NOT use ModelRouter — it creates its own Anthropic/OpenRouter/Codex clients directly via _call_llm(). Provider is resolved by string matching: "anthropic" → AsyncAnthropic, "openrouter" → complete_via_preferred_runtime_providers(), "codex" → complete_via_preferred_runtime_providers() with Codex order.

**AgentRunner** (agent_runner.py) DOES use ModelRouter — it receives a provider (which is the ModelRouter) and calls provider.complete_for_task() or provider.complete().

### Surface 2: DGC CLI / TUI (dgc_cli.py, pulse.py)
**How it works:** The CLI does NOT use ModelRouter for most operations. Instead:
- pulse.py calls `claude -p` as a subprocess via run_claude_headless(). This is the Claude Code CLI binary, not an API call. It requires the `claude` binary installed and authenticated.
- dgc_cli.py cmd_agent uses AutonomousAgent directly — which creates its own API clients, bypassing ModelRouter entirely.
- Some CLI commands (cmd_context, cmd_evolve) access the swarm's ModelRouter indirectly via swarm._router.get_provider().

**Model selection:** pulse.py defaults to whatever model the Claude Code CLI uses (configured in ~/.claude/). DGC CLI agent command defaults to "anthropic/claude-opus-4-6" via --model flag.

### Surface 3: Dashboard (api/routers/chat.py, Next.js frontend)
**How it works:** The dashboard has its own completely separate model resolution system:
- ChatProfileSpec defines named profiles: "claude_opus", "codex_operator", "qwen35_surgeon", "glm5_researcher", "kimi_k25_scout", "sonnet46_operator"
- Each profile has: provider_order (tuple of ProviderType), default_models (dict of ProviderType → model string), model_envs (dict of ProviderType → env var name for override)
- CertifiedLane (certified_lanes.py) adds: registration_id, codename, display_name, aliases
- On each chat request, the dashboard creates a fresh provider via create_runtime_provider() — it does NOT share the swarm's ModelRouter or its EWMA scores
- The dashboard resolves provider order from env vars (e.g., DASHBOARD_CHAT_PROVIDER_ORDER) with fallback to profile defaults

---

## Provider Hierarchy (Single Source of Truth: model_hierarchy.py)

### Tier Table

| Tier | Provider | Default Model | Env Key for API Key | Lane Role |
|------|----------|---------------|---------------------|-----------|
| FREE | Ollama Cloud | glm-5:cloud | OLLAMA_API_KEY | Research Delegate |
| FREE | NVIDIA NIM | meta/llama-3.3-70b-instruct | NVIDIA_NIM_API_KEY | Challenger |
| FREE | Groq | qwen/qwen3-32b | GROQ_API_KEY | Validator |
| FREE | Cerebras | qwen-3-235b-a22b-instruct-2507 | CEREBRAS_API_KEY | Bulk Builder |
| FREE | SiliconFlow | Qwen/Qwen3-Coder-480B-A35B-Instruct | SILICONFLOW_API_KEY | Bulk Builder |
| FREE | SambaNova | Meta-Llama-3.3-70B-Instruct | SAMBANOVA_API_KEY | General Support |
| FREE | Together | Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 | TOGETHER_API_KEY | Bulk Builder |
| FREE | Fireworks | qwen3-coder-480b-a35b-instruct | FIREWORKS_API_KEY | Bulk Builder |
| CHEAP | Mistral | mistral-small-latest | MISTRAL_API_KEY | General Support |
| CHEAP | Google AI | gemini-2.5-flash | GOOGLE_AI_API_KEY | General Support |
| CHEAP | Chutes | deepseek-ai/DeepSeek-R1 | CHUTES_API_KEY | General Support |
| CHEAP | OpenRouter Free | meta-llama/llama-3.3-70b-instruct:free | OPENROUTER_API_KEY | Research Delegate |
| PAID | Codex CLI | codex | (binary: codex) | Primary Driver |
| PAID | Claude Code CLI | claude-code | (binary: claude) | Primary Driver |
| PAID | Anthropic API | claude-opus-4-6 | ANTHROPIC_API_KEY | Primary Driver |
| PAID | OpenAI API | gpt-5 | OPENAI_API_KEY | General Support |
| PAID | OpenRouter Paid | xiaomi/mimo-v2-pro | OPENROUTER_API_KEY | Research Delegate |

### Canonical Seed Order (Cold Start)
FREE providers first (Ollama → NIM → Groq → Cerebras → SiliconFlow → SambaNova → Together → Fireworks) → CHEAP (Mistral → Google AI → Chutes → OpenRouter Free) → PAID (Codex → Claude Code → Anthropic → OpenAI → OpenRouter).

After ~100 routing events, EWMA scores from real performance data override this seed order.

---

## Inconsistencies Between Surfaces

### INCONSISTENCY-01: Three different LLM calling paths
- SwarmManager agents → ModelRouter.complete_for_task() (routing, EWMA, circuit breakers, telemetry)
- AutonomousAgent (CLI) → direct AsyncAnthropic/OpenRouter clients (no routing, no EWMA, no circuit breakers)
- Dashboard chat → create_runtime_provider() per request (no shared EWMA, no circuit breakers, separate telemetry)

**Impact:** The swarm's learned routing preferences (EWMA scores) are invisible to CLI agents and the dashboard. A provider that's been circuit-broken in the swarm will still be used by the dashboard and CLI.

**Fix:** All three surfaces should route through a shared ModelRouter instance (or at minimum, share the same RoutingMemoryStore SQLite DB so EWMA scores transfer).

### INCONSISTENCY-02: Agent identity/config is defined in multiple places with different schemas
- startup_crew.py: dict with name/role/thread/provider/model
- persistent_agent.py: PersistentAgent(name, role: AgentRole, provider_type: ProviderType, model)
- autonomous_agent.py: AgentIdentity(name, role: str, system_prompt, model: str, provider: str)
- profiles.py: AgentProfile(name, skill_name, model: str, provider: str, autonomy, permissions)

**Impact:** Agent identity/config is not fully unified across all
calling surfaces. The startup crew uses AgentRole enums + ProviderType
enums. AutonomousAgent uses bare strings. AgentProfile uses bare
strings. PersistentAgent uses enums. Converting between them is
error-prone (see INTERFACE_MISMATCH_MAP.md MISMATCH-02).

**Current code truth:** `AgentConfig` / `AgentState` and the shared
enums in `dharma_swarm/models.py` are the current cross-runtime code
truth. `AutonomousAgent.AgentIdentity` remains a separate surface.

**Aspirational migration:** unifying all surfaces into one Pydantic
`AgentIdentity` model may still be desirable, but it is not implemented
by this cleanup and must not be described as current behavior until
code and tests prove it.

### INCONSISTENCY-03: Conductors and persistent agents still bypass the routed policy path
Earlier versions of this map described conductors as simply hardcoded
to Anthropic. Current code is more nuanced, but the risk remains:
conductor / persistent-agent paths do not yet prove the same routed
policy, routing-memory, and circuit-breaker behavior as
`ModelRouter.complete_for_task()`.

**Fix direction:** conductors and persistent agents should either use
the same routed provider path as swarm agents or record equivalent
routing outcomes into the shared routing memory. Do not claim this is
implemented until provider-path tests cover it.

### INCONSISTENCY-04: pulse.py uses subprocess, not API
pulse.py calls `claude -p` as a subprocess. This means:
- It doesn't go through ModelRouter (no routing, no EWMA, no circuit breakers)
- It requires the `claude` binary installed and OAuth-authenticated
- It has different timeout behavior (subprocess timeout vs API timeout)
- It can't use free providers — it's always Claude
- If ANTHROPIC_API_KEY is set but `claude` binary is not installed, the heartbeat crashes

**Fix:** pulse.py should use complete_via_preferred_runtime_providers() with the cheap-first chain, falling back to subprocess only if no API keys are available.

### INCONSISTENCY-05: Dashboard profiles don't match swarm agent identities
Dashboard defines profiles like "qwen35_surgeon" with Groq as first provider. The swarm's startup crew has a "surgeon" agent that uses Ollama or OpenRouter Free. These are the same conceptual agent but with different providers, different models, and different identity schemas. Changes to one don't propagate to the other.

**Fix:** Derive dashboard profiles from the same agent identity source as startup_crew.py and persistent_agent.py.

---

## Historical HuggingFace Blocker: Resolved

### What happens
Every swarm agent call goes through:
agent_runner._invoke_provider() → ModelRouter.complete_for_task() → router_v1.build_routing_signals() → tiny_router_shadow.infer_tiny_router_shadow_from_messages() → ... → _load_tiny_router_artifacts() → `from huggingface_hub import snapshot_download` → ImportError

**Post-PR #28 status:** this is no longer the current blocker. The
interface mismatch map marks `MM-01` resolved. Keep the details below
as historical context only.

### Why it exists
tiny_router_shadow.py is an ML-based message transition classifier. It tries to load a HuggingFace checkpoint model for better accuracy. If the checkpoint isn't available, it falls back to a pure-Python heuristic (line 647-651). The fallback WORKS — but the ImportError crashes before the fallback can trigger.

### Historical fix options

**Option A — code fix that landed before this cleanup:**
In dharma_swarm/tiny_router_shadow.py, line 494-495, change:
```python
# BEFORE:
def _load_tiny_router_artifacts(*, allow_download: bool):
    from huggingface_hub import snapshot_download

# AFTER:
def _load_tiny_router_artifacts(*, allow_download: bool):
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        return None
```

**Option B — environment variable (no code change):**
Set `TINY_ROUTER_BACKEND=heuristic` in your environment. The _requested_backend() function at line 470 reads this env var. When set to "heuristic", _load_tiny_router_checkpoint_runtime() at line 539 returns None immediately (line 540: `if backend == "heuristic": return None`), bypassing the HuggingFace import entirely.

**Option C — install the dependency:**
`pip install huggingface-hub` — this makes the import succeed, but the model download will likely fail on first run without internet access to HuggingFace. On subsequent runs with `local_files_only=True`, it would use cached artifacts.

**Current recommendation:** do not re-open this as an active blocker.
If a future routing failure appears, reproduce it with a current test
or runtime log and add a new drift entry instead of reviving the old
`MM-01` claim.

---

## Historical Minimum Viable Model Path

This section is retained as 2026-04-04 bootstrap context. Do not use
it as a current blocker list without re-verifying against
`reports/ops/REPO_STATE_NOW.md` and current tests.

1. Confirm the HuggingFace fix remains present; do not re-apply it as
   if it were still missing.
2. Get ONE free API key. Easiest options:
   - GROQ_API_KEY from console.groq.com (free, instant, Qwen3-32B at 3000 tok/s)
   - NVIDIA_NIM_API_KEY from build.nvidia.com (free, 50 req/day)
   - OLLAMA_API_KEY for Ollama Cloud (GLM-5 744B)
3. Export the key: `export GROQ_API_KEY=gsk_xxxxx`
4. The startup_crew.py will detect the key and configure agents accordingly
5. Run `dgc orchestrate-live` — the swarm loop will spawn agents, dispatch tasks, and complete them via the free provider

---

## File Reference

| File | Lines | Role in Model Routing |
|------|-------|-----------------------|
| model_hierarchy.py | ~400 | Single source of truth: tiers, seed order, default models, EWMA ranking, lane roles |
| runtime_provider.py | ~500 | Provider config resolution from env vars, provider factory, preferred-chain helper |
| providers.py | ~3000 | 18 LLMProvider subclasses + ModelRouter (routing, fallback, circuit breakers, EWMA, telemetry) |
| base_provider.py | ~60 | Abstract provider interface (ProviderCapabilities, BaseProvider) |
| router_v1.py | ~400 | Request classification: complexity, language, context tier, tiny router signals |
| tiny_router_shadow.py | ~710 | ML-based message transition classifier (optional, falls back to heuristic) |
| provider_policy.py | ~430 | ProviderPolicyRouter: task-type → provider selection policy |
| routing_memory.py | ~580 | EWMA score storage + candidate ranking (SQLite) |
| resilience.py | varies | CircuitBreakerRegistry: health tracking, open/closed/half-open states |
| startup_crew.py | ~200 | Default agent definitions: names, roles, providers, models |
| persistent_agent.py | ~320 | PersistentAgent: long-lived agent with wake loop |
| autonomous_agent.py | ~750 | AutonomousAgent: ReAct loop with direct provider calls (bypasses ModelRouter) |
| profiles.py | ~160 | AgentProfile: runtime config per agent instance |
| conductors.py | ~80 | Conductor / persistent-agent provider configs; still outside the fully routed policy path |
| certified_lanes.py | ~80 | Dashboard chat lane definitions |
| api/routers/chat.py | ~900 | Dashboard chat endpoint: profiles, provider resolution, tool execution |
| free_fleet.py | ~410 | Free model discovery and tier management |
| model_registry.py | ~170 | Model capability registry (context windows, costs) |
| ollama_config.py | varies | Ollama Cloud transport resolution |

---

*End of Model Routing Map*
