# First-Brick Spec — The Record→Runtime Bridge

**Created:** 2026-06-08 · **Status:** DESIGN (not yet implementation-approved) · **Owner:** Dhyana + operator
**Track:** Off the declared "Runtime Truth Reconciliation" track — opening this lane is an explicit operator choice (see [README.md](README.md) governance note).

> **SUPERSEDING DECISION (2026-06-09, operator):** First holon = **`opus_composer`** (resolves this spec's recommendation over `05_RECONCILED_PLAN`'s merge_master_mike). Canonical repo = `/Users/dhyana/dharma_swarm`. v1 is **read-only** (talk-as-itself, no enforcement) because opus_composer has no structured `autonomy_policy` yet. See [BUILD_STEP_ZERO.md](BUILD_STEP_ZERO.md) and [READINESS_VERDICT.md](READINESS_VERDICT.md).
>
> **⚠️ ASSUMPTION-CORRECTION BANNER (2026-06-09 audit — the body below has 8 verified-wrong assumptions; this banner + the v1 build-ready appendix are AUTHORITATIVE over the original body):**
> 1. **Agent path:** ✅ DECIDED 2026-06-09 — `load_holon` reads `~/.dharma/agents/<name>/` (canonical home; opus_composer is there). The broader `ginko/agents` → `agents/` consolidation is a separate supervised migration that does NOT gate this read-only v1. See [AGENT_HOME_RECONCILIATION.md](AGENT_HOME_RECONCILIATION.md).
> 2. **Provider interface:** use `provider.stream(LLMRequest)` / `complete_via_preferred_runtime_providers` (`runtime_provider.py:604`). `provider.stream_completion()` **does not exist** anywhere.
> 3. **Model fallback:** do NOT hardcode `claude_haiku_4_5`; use identity model + live `resolve_runtime_provider_config` fallback.
> 4. **Witness:** reuse `~/.dharma/witness/` + `conversation_log`; do NOT build `~/.dharma/holon_witness/` (non-goal violation).
> 5. **First holon:** opus_composer (not merge_master_mike — `05` is superseded).
> 6. `holon_bridge.py` / `RunningHolon` / `POST /holon-chat` are **build deliverables**, not existing state.
> 7. Citation nits: `chat_with_agent` starts `api/routers/agents.py:404` (the "475" end-line is wrong); `AutonomyPolicy` is `external_agent_registration.py:136` (not :130).
> 8. The `AgentRegistry` default pointing at `ginko/agents` is the system-wide deviation behind all of this (see reconciliation doc).

This document is the executable spec for organ #1 of the sovereign holon: the **record→runtime bridge**. It is intentionally narrow. It does not build memory, evolution, verification, or governance — those are subsequent organs. It builds **only** the function that turns a registered agent record into a running `PersistentAgent` configured from that record's own model, prompt, banks, and identity, reachable through a human talk surface.

---

## Verified ground truth (before any code)

These are the wiring facts the spec is built on. Each one was read directly from the repo on 2026-06-08, not paraphrased.

### 1. `chat_with_agent` exists and is cosmetic

**File:** [`api/routers/agents.py:404-475`](file:///Users/dhyana/dharma_swarm/api/routers/agents.py).

The endpoint takes `agent_id`, calls `_resolve_agent_payload(agent_id)` to get the registry record, extracts `display_name / role / model / provider / status / current_task` into a **string template**, builds a `system_prompt` like:

```text
You are {agent_name}, a {agent_role} agent in the DHARMA swarm.
Model: {agent_model} | Provider: {agent_provider} | Status: {agent_status}
…
```

…and streams through `_agentic_stream(api_messages, settings, …)` from `api/routers/chat.py` — i.e. **the operator's global chat backend with its own settings**, not the agent's own runtime. The `agent_model` and `agent_provider` fields are *informational substrings inside the system prompt*. They never select the model, never load `prompt_variants/active.txt`, never replay `task_log.jsonl`, never enter the agent's own wake loop.

> **Implication:** sitting in this chat is sitting with the operator's global model wearing a name tag. The agent's evolved self does not speak.

### 2. `_check_gate` is fail-OPEN

**File:** [`dharma_swarm/persistent_agent.py:425-443`](file:///Users/dhyana/dharma_swarm/dharma_swarm/persistent_agent.py).

```python
def _check_gate(self, task_text: str) -> dict[str, Any] | None:
    try:
        …
        if decision == GateDecision.BLOCK:
            return {"blocked": True, "reason": outcome.result.reason}
        return {"blocked": False}
    except Exception as e:
        logger.debug("[%s] gate check skipped: %s", self.name, e)
        return None
```

The caller in the wake loop cannot distinguish "no gates configured" from "gates crashed" from "gate passed" — `None` and `{"blocked": False}` both mean *proceed*. **Any claim that the bridge is "fail-closed" without first fixing this is false.** The first brick MUST either (a) wire its own pre-execution gate (recommended — keep _check_gate untouched in this PR), or (b) be explicitly documented as fail-open.

### 3. `AutonomyPolicy` is documented-as-decorative

**File:** [`dharma_swarm/external_agent_registration.py:130-160`](file:///Users/dhyana/dharma_swarm/dharma_swarm/external_agent_registration.py).

```python
class AutonomyPolicy(BaseModel):
    """Concrete refusal flags for an external worker.

    These are encoded as positive refusals so a registration record
    self-documents what the worker may *not* do, **without depending on
    runtime enforcement code reading the same fields back.**"""
    requires_approval: bool = True
    can_approve_prs: bool = False
    can_write_source: bool = False
    …
```

So `requires_approval=True` is a self-description, **not a constraint**. Building a runtime that reads these fields and enforces them is not "step 3 of 5" — it is **building the PDP/PEP governance system** that the hostile_safety_audit_2026_06_05 said is unsolved. **Out of scope for the first brick.** The bridge will treat the manifest as advisory metadata only and force a human-in-the-loop confirmation for any tool call until that system exists.

### 4. The registry is a filing cabinet, not a loader

**File:** [`dharma_swarm/agent_registry.py:329-350`](file:///Users/dhyana/dharma_swarm/dharma_swarm/agent_registry.py).

```python
def load_agent(self, name: str) -> dict[str, Any] | None:
    """Load agent identity from disk. … Returns: Identity dict, or None …"""
```

Returns a dict. There is **no** function in `dharma_swarm/` that takes that dict and returns a runnable `PersistentAgent`. The wake loop's only constructor is `orchestrate_live.py`, which uses hardcoded config. **This is precisely the missing function.**

### 5. The "easiest first holon" picture is wrong

The dossier's two candidates verified on disk:

- **`conductor_claude` / `conductor_codex`:** typed as `persistent_agent_candidate` in [`l4_readiness.jsonl`](file:///Users/dhyana/dharma_swarm/docs/research/persistent_agents_census_2026-05/l4_readiness.jsonl). **No directory exists in `~/.dharma/ginko/agents/`.** They are registration-intent, not selves.
- **`KARYA-Steady-Builder`:** directory `~/dharma_swarm/.claude/agent-memory/KARYA-Steady-Builder/` is **empty**. KARYA is persona files in `.claude/agents/`, no ginko self, no manifest.
- **`merge_master_mike`:** a daemon-script ([`scripts/runtime/merge_master_mike_daemon.py:26`](file:///Users/dhyana/dharma_swarm/scripts/runtime/merge_master_mike_daemon.py)) with `AGENT_UID = "merge_master_mike"` as a constant. Not a ginko-registered agent.

**Therefore the first holon must use one of the 46 actual ginko-registered selves**, not KARYA or conductor_*. The strongest candidates by readiness score (from the prior agent-naming-map session): `opus_composer`, `codex_composer`, `codex-primus`, `opus-primus` — all `registered_worker` at L1 with measured score 2. Recommended: **`opus_composer`** (clean name, no separator-drift issue, paired with `codex_composer` for downstream pairing experiments).

---

## What the bridge does (and only this)

```
                        ┌─────────────────────────────────────────┐
                        │  load_holon(name) → RunningHolon        │
                        └─────────────────────────────────────────┘
                                          │
                                          ▼
        ┌─────────────────────────────────────────────────────────────────┐
        │ 1. AgentRegistry.load_agent(name)             → identity dict   │
        │ 2. Read prompt_variants/active.txt            → system prompt   │
        │ 3. Read last K rows of task_log.jsonl         → conversation seed
        │ 4. Resolve identity["model"]                  → live provider   │
        │ 5. Look for examples/agents/<name>.registration.json (optional) │
        │ 6. Construct PersistentAgent(name, …)         → runnable body   │
        │ 7. Return RunningHolon{registry, persistent_agent, manifest}    │
        └─────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                        ┌─────────────────────────────────────────┐
                        │  POST /agents/{id}/holon-chat           │  ← NEW endpoint
                        │  (does NOT replace /agents/{id}/chat)   │
                        └─────────────────────────────────────────┘
```

**Non-goals (explicit):**

- No new daemon. The bridge is a request-scoped object; idle holons hold no resources.
- No new memory store. Reads/writes go to existing `task_log.jsonl` and `prompt_variants/`.
- No new registry. `AgentRegistry` is the only registry.
- No replacement of `chat_with_agent`. The new endpoint is `/agents/{id}/holon-chat` (additive). Old endpoint stays until the new one is proven.
- No write actions through the chat surface in v1. Read-only conversation + the holon's *own* read-only tools. Tool calls that mutate require an explicit operator confirmation token.

---

## API surface (smallest possible)

### `dharma_swarm/holon_bridge.py` (new file, target <250 LOC)

```python
@dataclass
class RunningHolon:
    name: str
    identity: dict                 # AgentRegistry.load_agent result
    manifest: dict | None          # examples/agents/<name>.registration.json if present
    agent: PersistentAgent         # the body, configured from identity
    system_prompt: str             # from prompt_variants/active.txt
    model: str                     # resolved live model id
    provider: str                  # resolved provider

def load_holon(name: str, registry: AgentRegistry | None = None) -> RunningHolon: ...
def holon_reply(holon: RunningHolon, user_message: str, *, history: list[dict]) -> AsyncIterator[str]: ...
```

`load_holon` is pure (no side effects beyond reading files). `holon_reply` is the streaming generator that the new endpoint calls.

### `api/routers/agents.py` (additive)

```python
@router.post("/agents/{agent_id}/holon-chat")
async def chat_with_holon(agent_id: str, req: _AgentChatRequest): ...
```

Lives next to `chat_with_agent`. Same request schema for drop-in client testing. Different code path.

### Model routing (the rule, from research)

Per the run-3 Fireworks finding (GLM-5.1 worker + Opus 4.7 advisor: 18/100 at $368 vs 14/100 Opus end-to-end at $954), the bridge uses a **two-tier policy that is explicit, not implicit**:

1. **Primary:** the agent's own `identity["model"]`, routed via `runtime_provider.preferred_runtime_provider_configs()`. If unset, fallback is `claude_haiku_4_5` (cheap and live), **not** the global default (which crashes if `claude_code` binary missing).
2. **Advisor:** an *optional* second-pass call to a frontier model when the primary's response triggers a "hard sub-task" classifier (initially: long-horizon planning, code generation >50 LOC, novel API design). Triggered explicitly, not by every turn.

**Critic correction applied:** the 7.8× harness-over-model variance number holds inside a near-frontier model band. Defaulting to a weak free model violates that band. The advisor pattern is how we reconcile: free-tier *floor*, frontier-tier *ceiling on demand*.

---

## The verification organ (built in from turn 1)

**Critic finding:** a same-model "did that work?" check is theater identical to the cosmetic chat endpoint. The verifier must assert a re-readable artifact.

**Rule:** every response from `holon_reply` that claims an outcome ("I updated X", "the test passes", "the file now contains Y") **must include a `verifier_artifact`** — a path to a file the operator (or a second process) can read independently. No artifact, no claim. The endpoint refuses to emit "done" markers without one.

For v1, the artifact contract is dumb-simple:

```json
{
  "claim": "I updated docs/sovereign_holons/02_FIRST_BRICK_SPEC.md",
  "verifier_artifact": "/Users/dhyana/.dharma/holon_witness/<session>/2026-06-08T07:00:00Z.txt",
  "verifier_command": "diff -u <before> <after>"
}
```

The artifact is written by the bridge after the holon's tool call returns. The operator can re-run `verifier_command` to confirm. Same-model self-grading is **explicitly forbidden** in v1; if a check is needed beyond artifact existence, it goes to a *different model* (e.g., Haiku checks Sonnet).

---

## Prompt-injection scope (critic finding #3)

The bridge accepts text the operator types **and** text the holon's tools return. Tool outputs are untrusted content. v1 mitigations:

1. **Trust-tagging:** every chunk fed back into the model is prefixed with `<source:operator>` or `<source:tool:<tool_name>>`. The system prompt instructs the holon to treat `<source:tool:*>` as data, never as instructions.
2. **Tool-call whitelist:** v1 ships with read-only tools only. Write tools require an operator confirmation token per call.
3. **No web fetch in v1.** Indirect prompt injection from arbitrary URLs is the highest-severity vector ([Sophos lethal-trifecta analysis 2026-05-11](https://www.sophos.com/en-us/blog/inside-the-lethal-trifecta-blast-radius-reduction-in-ai-agent-deployments)). Adding web fetch requires a follow-up spec.

**Moltbook addendum:** with `moltbook.com` now confirmed real (770k+ AI agents on an agent-only social network running OpenClaw, [Forbes 2026-01-30](https://www.forbes.com/sites/amirhusain/2026/01/30/an-agent-revolt-moltbook-is-not-a-good-idea/)), the bridge MUST NOT auto-fetch any URL from the agent's outputs in v1. This is the exact lethal-trifecta scenario (private data + untrusted content + external communication). Documenting now so future organs don't drift into it.

---

## Acceptance criteria for the first brick

The brick is "done" when **all six** are true:

1. `load_holon("opus_composer")` returns a `RunningHolon` whose `system_prompt` matches `~/.dharma/ginko/agents/opus_composer/prompt_variants/active.txt` byte-for-byte (or, if file absent, a default sourced from the identity record — explicitly logged).
2. `POST /agents/opus_composer/holon-chat` with `{"messages":[{"role":"user","content":"who are you?"}]}` streams a response whose first 10 tokens are routed through the model named in the identity record (verified by inspecting the provider's request log).
3. The same call **does not** invoke `_agentic_stream` from `api/routers/chat.py`.
4. Any response that contains the word `done`, `updated`, `committed`, `passed`, or `created` without a `verifier_artifact` field is replaced with a refusal message logged to `~/.dharma/holon_witness/<session>/violations.jsonl`.
5. Tool calls from inside the holon are denied unless the request carried `X-Holon-Confirmation: <token>` (operator approval).
6. `tests/test_holon_bridge.py` exists with: (a) golden test for `load_holon`, (b) integration test using a stub model that the routed message reaches the stub, (c) artifact-required refusal test.

---

## Build sequence (the smallest commits)

| # | Commit                                                                  | LOC budget | Reversible? |
| - | ----------------------------------------------------------------------- | ---------- | ----------- |
| 1 | `dharma_swarm/holon_bridge.py` (pure functions, no network)             | <150       | Yes — delete file |
| 2 | `tests/test_holon_bridge.py` (golden + stub-model)                      | <100       | Yes         |
| 3 | `api/routers/agents.py` adds `/agents/{id}/holon-chat` (additive route) | <80        | Yes — delete route |
| 4 | `docs/sovereign_holons/02_FIRST_BRICK_SPEC.md` updated with results     | n/a        | n/a         |
| 5 | First witness baseline: `docs/sovereign_holons/baselines/2026-MM-DD-opus_composer.txt` | n/a | Yes |

Each commit must run `make hygiene-check` and `python3 scripts/docops/check_docops_integrity.py` green. PR is opened against branch `feat/sovereign-holons/first-brick`. Operator owns the merge (doctrine).

---

## Out of scope for this brick (and the spec that owns each)

- **Memory reorganization / sleep-time compute** → future `03_SLEEP_TIME_COMPUTE.md`. The `AgentCronScheduler` exists; the content of what it should run does not.
- **`pass^k` reliability instrumentation** → future `04_RELIABILITY_METRIC.md`. Replaces empty `fitness_history.jsonl`.
- **Reading `AutonomyPolicy` at runtime (real PDP/PEP)** → future `05_GOVERNANCE_RUNTIME.md`. Material project; not glue.
- **DGM self-improvement loop wiring** → existing track; the dgm_loop_unwired audit owns this.
- **Bi-temporal memory (Graphiti pattern)** → future `06_BITEMPORAL_MEMORY.md`. Speculative until the bridge ships.

---

## Open design questions (must resolve before commit #1)

1. **Single-thread coherence vs. parallel holons?** Cognition's "don't build multi-agents" and Walden Yan's follow-up (writes single-threaded; additional agents = intelligence not actions) suggest v1 supports **one active holon per session**. The bridge can `load_holon` many; only one is "speaking" at any moment. Confirm with operator.
2. **Prompt-cache strategy?** Claude Sonnet 4.6 with 90% cache reads ([Anthropic pricing](https://www.cloudzero.com/blog/claude-api-pricing/)) brings effective cost to $0.30/M tokens. The system prompt + brief context is stable per session → 1-hour cache. NVIDIA Dynamo's `--strip-anthropic-preamble` finding shows variable preambles **destroy** KV reuse. Confirm bridge places stable content first.
3. **Witness path:** `~/.dharma/holon_witness/<session>/` is parallel to existing `~/.dharma/witness/`. Confirm naming or reuse the existing root.
4. **Confirmation token:** simple operator-typed string in v1, or generated per-session? Recommend per-session token shown once at chat open.

---

## v1 BUILD-READY APPENDIX (2026-06-09) — hardened verifiers + resolved contracts

Produced by the spec-hardening pass + adversarial integrator. **The draft verifiers were all false-greens** (they mocked `provider.stream_completion`, a method that does not exist; real interface is `provider.complete(LLMRequest)` / `provider.stream(LLMRequest)`, `models.py:309`) and hardcoded a `~/.dharma/ginko/agents/opus_composer/` path that **does not exist**. Rewritten below against the real repo.

### Resolutions to the open questions above
- **Q3 (witness path) — RESOLVED:** reuse existing owners (`conversation_log.log_exchange()` with `interface="holon"` + `spine.EvidenceReceipt` / `runtime_state.RuntimeReceipt`). **Do NOT build `~/.dharma/holon_witness/`** — a new top-level tree violates the active track's "no new event log" non-goal (see `BUILD_STEP_ZERO.md` §v1 persistence constraint). If session witness files are wanted, nest under the existing `~/.dharma/witness/` root.
- **Q4 (confirmation token) — DEFERRED:** read-only v1 has no tool calls to gate → the `X-Holon-Confirmation` mechanism (criterion 5) is **enforcement-phase, not v1**. v1 ships without it.
- **provider coercion — SETTLED (canon):** `identity['provider'] == "anthropic_max"` → `ProviderType.CLAUDE_CODE` (Max-plan, per `MODEL_KEY_ROUTING` "THE ONE WAY"). Naive `ProviderType("anthropic_max")` raises — coercion is required.
- **model fallback — SETTLED:** do not hardcode a Haiku id (none found in `model_hierarchy`/`DEFAULT_MODELS`). v1 model = identity's `claude-opus-4-8`; fallback is the existing live-fallback in `resolve_runtime_provider_config`.

### ⬜ BLOCKED ON AGENT-HOME RECONCILIATION (do not encode an agent path yet)
**There is a real two-home fork, not a simple pick.** Verified 2026-06-09: `~/.dharma/agents/` (41 dirs, where roaming_onboarding + opus_composer live) vs `~/.dharma/ginko/agents/` (46 dirs, what `AgentRegistry` **defaults to** at `agent_registry.py:201` and `ginko_evolution`/`ginko_agents`/`graphql_router` hardcode). opus_composer lives in the former; the registry reads the latter. **Any `load_holon` path is an assumption until the agent-home reconciliation audit resolves the canonical home + migration direction** (in progress). Do not bake a path into verifiers until then — the operator's directive is "all agents at one obvious place," which is a substrate-consolidation decision, not a per-build choice.

### 6 hardened verifiers (run all green before the build is "done")
| # | Criterion | Verifier (real interface; route-level where the criterion is HTTP) |
|---|-----------|---------------------------------------------------------------------|
| 1 | `load_holon("opus_composer")` system_prompt = agent's `active.txt` byte-for-byte (else logged default) | `python3 -c "...from dharma_swarm.holon_bridge import load_holon; h=load_holon('opus_composer'); exp=(Path.home()/'.dharma/agents/opus_composer/prompt_variants/active.txt').read_text(); assert h.system_prompt==exp; print('PASS')"` + a tmp-agent run with `active.txt` absent asserting the default-branch log line. |
| 2 | holon-chat routes first tokens through the identity model | Stub provider subclassing the real base, recording `LLMRequest.model`; patch `holon_bridge.create_runtime_provider`→stub; assert `recorded.model==holon.model=="claude-opus-4-8"` and `stub.stream` awaited ≥1. |
| 3 | same call does NOT invoke `_agentic_stream` | Patch **both** `api.routers.chat._agentic_stream` (`:969`) **and** `_subprocess_agentic_stream` (`:871`, which the former delegates to at `:988`) to raising sentinels; drive a full request via FastAPI `TestClient` (not `holon_reply` in isolation); assert neither sentinel fired. (Patching only `_agentic_stream` leaves a subprocess escape hatch.) |
| 4 | outcome-claim words without `verifier_artifact` → logged refusal | Stub model reply with `done`/`updated`, no artifact; assert stream contains refusal sentinel + a line appended to the witness; **`xfail` until the refusal codepath exists** (no vacuous PASS). |
| 5 | tool calls denied unless `X-Holon-Confirmation` header | **Enforcement-phase (deferred for read-only v1).** When built: two `TestClient` requests (no header → refused + 0 side-effects; valid token → permitted), header read at the route. |
| 6 | `tests/test_holon_bridge.py` exists with golden+stub+refusal tests, all passing | `python3 -m pytest tests/test_holon_bridge.py -v` exit 0 **and** assert the 3 named tests were *collected and passed* (not keyword-grep). |

### Resolved contracts (derived from code)
- **system_prompt source:** `~/.dharma/agents/<name>/prompt_variants/active.txt`, fallback `identity['system_prompt']` (logged).
- **`PersistentAgent` signature** (`persistent_agent.py:128`): `(name, role: AgentRole, provider_type: ProviderType, model, state_dir=None, wake_interval_seconds=3600.0, system_prompt='', max_turns=25, model_router=None)`. `provider_type` via the coercion above.
- **provider call shape:** `provider.stream(LLMRequest(model, messages, system, max_tokens, temperature, tools))`.
- **`AutonomyPolicy` is advisory in v1** (`external_agent_registration.py:135`; validator fires only at registration). v1 = metadata + human confirmation, no runtime PDP.
- **Greenfield (must be designed, not "derived"):** `AgentSeedResolver` / `resolve_agent_seed` and `dgc agent talk` — no such symbols exist yet.
