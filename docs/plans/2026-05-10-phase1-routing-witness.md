# Phase 1 — Canonical Route Witness (Dashboard-Ready, Anti-Magic)

**Date:** 2026-05-10
**Owner:** Dhyana (sponsor) + active inhabitant agent
**Status:** approved spec, implementation in this session
**Subordinate to:** `CLAUDE.md`, `docs/governance/SOVEREIGN_MANIFEST.md`, `docs/foundations/CONTEMPLATIVE_SPINE.md`
**Predecessors:** Codex think-through transcript (in conversation), grill-me decisions Q1–Q5
**Telos:** close feedback fragmentation between routing decisions and task value (spine §3 recognition closure) without inventing a second routing reality.

---

## 0. The actual problem (per Codex think-through)

**Routing infrastructure is not the bottleneck.** dharma_swarm already has:
- `provider_policy.ProviderPolicyRouter` (policy brain)
- `providers.ModelRouter` (execution + retry/fallback/circuit/canary)
- `routing_memory.RoutingMemoryStore` (per-(provider,model,task_signature) EWMA matrix)
- `telemetry_plane.TelemetryPlaneStore` with typed `RoutingDecisionRecord`
- `decision_router.DecisionRouter` with typed `RouteDecision` + `RoutePath` enum
- `model_hierarchy.CANONICAL_SEED_ORDER` (catalog authority)
- `routing_decisions.jsonl` audit log (`DGC_ROUTER_AUDIT_LOG`)
- `runtime.db` typed store (`DGC_ROUTER_TELEMETRY_DB`)

The bottlenecks are:

1. **Feedback fragmentation** — route outcome lives in routing memory/telemetry; task value lives in TelicSeam. Not one causal object.
2. **Signal poverty** — quality scores too heuristic, sparse, decoupled from task type / tool need / credit state.
3. **Budget policy gap** — `agent_registry.is_budget_exceeded` exists but isn't wired into AgentRunner / ModelRouter completion.
4. **Bypass sprawl** — direct `complete_via_preferred_runtime_providers` / `create_runtime_provider` calls evade routing policy and witness.
5. **Silent fallback** — `provider_policy.py:223` defaults to `CLAUDE_CODE` on filter-empty. Should be typed `NO_ROUTE` with reason.

Phase 1 attacks #4 and partially #2. Phases 2 and 3 attack the rest.

---

## 1. Scope (Phase 1 only)

**In scope:**
- Enrich `RoutingDecisionRecord` schema with dashboard-ready typed fields (nullable, default-valued).
- Add `ProviderAttemptRecord` typed dataclass + SQLite table.
- Add `dharma_swarm/route_witness.py` — emission/normalization helper. Never routes.
- Wire emissions at four surfaces: `ModelRouter.complete_for_task()`, `complete_via_preferred_runtime_providers()`, `pulse_alt_lanes.py`, `inquiry_substrate_chew._call_provider()`.
- Existing `routing_decisions.jsonl` audit path stays canonical. No new JSONL file.
- Best-effort failure: witness write failure logs but never raises.

**Explicitly out of scope (Phase 2 / 3):**
- Wiring `is_budget_exceeded` into completion preflight (Phase 2).
- Replacing the silent `CLAUDE_CODE` fallback with typed `NO_ROUTE` (Phase 2).
- Ontology objects `RoutingDecision` / `ProviderAttempt` linked to `Outcome` / `ValueEvent` / `Contribution` via TelicSeam (Phase 3).
- Outcome quality back-link from TelicSeam to routing decision (Phase 3).
- Bare `Provider().complete()` callers in `deep_agent_backend`, `scout_framework`, etc. (Phase 1.5 — instrument once Phase 1 reveals which surfaces actually fire in practice).
- Grafana dashboard panels (built later against this schema).

---

## 2. Schema additions (additive, nullable)

### 2.1 `RoutingDecisionRecord` — extend existing dataclass

Existing fields preserved unchanged. New fields appended, all nullable/defaulted:

```python
@dataclass(frozen=True)
class RoutingDecisionRecord:
    # --- existing fields (unchanged) ---
    decision_id: str
    action_name: str
    route_path: str
    selected_provider: str = ""
    selected_model_hint: str = ""
    confidence: float = 0.0
    requires_human: bool = False
    session_id: str = ""
    task_id: str = ""
    run_id: str = ""
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)

    # --- Phase 1 dashboard-ready additions (all default-valued) ---
    schema_version: str = "v1"
    task_signature: str = ""              # opaque hash/slug per task class
    task_type: str = "unknown"            # pulse | chew | code_edit | research | chat | inquiry | unknown
    caller: str = "unknown"               # pulse_alt_lanes | inquiry_chew | model_router | complete_via_preferred | ...
    decision_class: str = "pinned"        # pinned | widened | fallback | no_route | canary
    selected_tier: str = "unknown"        # free | cheap | paid
    widened_from: str = ""                # original pinned provider lane, if widened
    candidate_chain: list[str] = field(default_factory=list)  # provider lanes considered, in order
    n_attempts: int = 0
    outcome: str = "unknown"              # success | empty_content | all_failed | timeout | gate_block | no_route
    duration_ms: float = 0.0
    total_tokens: int = 0
    cost_estimate_usd: float = 0.0
```

SQL migration: `ALTER TABLE routing_decisions ADD COLUMN <name> <type> DEFAULT <default>` for each new field. Existing rows preserved; queries that don't reference new columns keep working.

### 2.2 `ProviderAttemptRecord` — new dataclass

```python
@dataclass(frozen=True)
class ProviderAttemptRecord:
    decision_id: str                      # FK to RoutingDecisionRecord.decision_id
    attempt_idx: int                      # 0-based
    provider: str                         # ProviderType.value
    model: str
    tier: str = "unknown"                 # free | cheap | paid
    success: bool = False
    outcome: str = "unknown"              # success | failed | timeout
    error_class: str = ""                 # enum below
    error_detail: str = ""                # ≤200 chars, redacted
    duration_ms: float = 0.0
    stop_reason: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    cost_estimate_usd: float = 0.0
    circuit_state: str = "closed"         # open | closed | half_open
    schema_version: str = "v1"
    created_at: datetime = field(default_factory=_utc_now)
```

New SQLite table `provider_attempts` with `decision_id` indexed for join queries.

### 2.3 `error_class` enumeration

Single source of truth, lives in `route_witness.py`:

```
credit_exhausted   — provider returns "Credit balance is too low" or equivalent
rate_limit         — 429 / quota error
timeout            — wall-clock exceeded
network            — connection refused, DNS, transient HTTP error
model_unavailable  — 404 model, deprecated, region-blocked
empty_content      — 200 OK with no visible content (gpt-5 reasoning starvation, etc.)
api_error          — 500 / 503 from provider
auth_error         — 401 / 403 not classified as rate-limit
unknown            — fallthrough
```

### 2.4 JSONL row shapes

Two row kinds in `~/.dharma/logs/router/routing_decisions.jsonl`. Each row carries `row_kind: "decision" | "attempt"` and `schema_version: "v1"`.

Decision row mirrors `RoutingDecisionRecord` field set. Attempt row mirrors `ProviderAttemptRecord` field set. Decision row is written FIRST, attempts AFTER, all in one helper call so they land contiguously even under concurrent writers.

---

## 3. `route_witness.py` — emission helper

Single file. Single responsibility: build, redact, classify, emit. Never routes. Never gates. Never falls back.

### 3.1 Public API

```python
async def emit_routing_decision(
    *,
    decision_id: str,
    action_name: str,
    route_path: str,
    selected_provider: ProviderType | str,
    selected_model: str,
    candidate_chain: list[ProviderType | str],
    decision_class: str,
    caller: str,
    outcome: str,
    duration_ms: float,
    attempts: list[ProviderAttemptRecord],
    task_type: str = "unknown",
    task_signature: str = "",
    confidence: float = 0.0,
    requires_human: bool = False,
    reasons: list[str] | None = None,
    widened_from: ProviderType | str | None = None,
    session_id: str = "",
    task_id: str = "",
    run_id: str = "",
    total_tokens: int = 0,
    cost_estimate_usd: float = 0.0,
    metadata: dict[str, Any] | None = None,
    telemetry: TelemetryPlaneStore | None = None,
    audit_log_path: Path | None = None,
) -> None:
    """Write one canonical RoutingDecisionRecord + N ProviderAttemptRecord rows.

    Best-effort. Logs and swallows on failure. Never raises into the caller.
    """

def build_provider_attempt(
    *,
    decision_id: str,
    attempt_idx: int,
    provider: ProviderType | str,
    model: str,
    success: bool,
    duration_ms: float,
    error: BaseException | None = None,
    error_class: str | None = None,
    error_detail: str = "",
    stop_reason: str | None = None,
    usage: dict[str, int] | None = None,
    cost_estimate_usd: float | None = None,
    circuit_state: str = "closed",
) -> ProviderAttemptRecord:
    """Construct a redacted, classified ProviderAttemptRecord.

    If `error` is provided, derives `error_class` automatically from exception
    type + message patterns. Truncates `error_detail` to 200 chars and runs
    redaction patterns. If `cost_estimate_usd` is None, looks up via
    model_hierarchy.
    """
```

### 3.2 Redaction rules

`error_detail` is truncated to 200 chars BEFORE storage. Then scrubbed of:
- API key patterns (`sk-`, `Bearer `, hex blobs ≥ 32 chars)
- Email addresses
- File paths under `~/.dharma/` (replaced with `<witness_path>`)
- Anything matching `re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*\S+")`

If after redaction the detail is empty, store `"[redacted]"`.

### 3.3 Tier and cost lookup

`route_witness.py` imports from `model_hierarchy`:
- `tier_for_provider(provider, model) -> "free" | "cheap" | "paid"` — derived from the provider's position in `CANONICAL_SEED_ORDER` and known free providers list.
- `estimate_cost_usd(provider, model, prompt_tokens, completion_tokens) -> float` — returns 0.0 for free providers, looks up per-model pricing for paid lanes.

These stay local to route_witness; no other module touches pricing. Phase 2 may centralize them.

### 3.4 Failure mode

All emissions wrapped in `try/except Exception: logger.warning(...)`. A witness write failure must never cascade into a real LLM call. Witness write failures DO emit a stigmergy mark on `channel="review"` with `salience=0.7` so chronic emission failures become visible in the review queue.

---

## 4. Call site instrumentation

### 4.1 `ModelRouter.complete_for_task()` (`providers.py`)

Already plumbed for telemetry (env-gated `DGC_ROUTER_TELEMETRY_ENABLE`). Refactor existing emission to go through `route_witness.emit_routing_decision()`. ModelRouter constructs `ProviderAttemptRecord` for each provider attempt during retry/fallback, then calls the helper once at the end of the route attempt sequence.

Preserve existing `ExternalOutcomeRecord` writes — tests/views may depend on them. Phase 3 may unify.

### 4.2 `runtime_provider.complete_via_preferred_runtime_providers()` (`runtime_provider.py`)

Currently iterates `configs` calling `provider.complete()` directly. Add:
- Generate `decision_id = uuid4().hex` at function start.
- Build `attempts: list[ProviderAttemptRecord]` accumulated as the chain iterates.
- After the final return / final exception, call `emit_routing_decision()` once with the full chain.
- `caller="runtime_provider.complete_via_preferred_runtime_providers"`.
- `decision_class="fallback"` (always — this function is by definition a chain).

### 4.3 `~/.dharma/scripts/pulse_alt_lanes.py`

Currently calls `OpenAIProvider().complete()` then `OllamaProvider().complete()` raw. Refactor to:
- Generate `decision_id` at start.
- Build `attempts: list[ProviderAttemptRecord]` for openai (success or fail) + ollama (if reached).
- Call `emit_routing_decision()` after the chosen result is decided.
- `caller="pulse_alt_lanes"`, `task_type="pulse"`, `action_name="heartbeat_alt_pulse"`, `decision_class="fallback"`.

### 4.4 `dharma_swarm/inquiry_substrate_chew.py::_call_provider()`

Currently single provider call (no chain). Refactor to:
- Caller (`run_chew`) generates `decision_id` and passes through.
- `_call_provider` wraps the actual `provider.complete()` in try/except, builds one `ProviderAttemptRecord`, returns both response AND attempt record.
- `run_chew` calls `emit_routing_decision()` with single-attempt list.
- `caller="inquiry_substrate_chew"`, `task_type="chew"`, `decision_class="pinned"` (when explicit `--provider`) or `"widened"` (when chain selection).

### 4.5 Bare `Provider().complete()` callers

**Deferred to Phase 1.5.** After Phase 1 runs for ≥3 days, query `routing_decisions.jsonl` for known `caller` values; subtract from a grep of all `provider.complete(` call sites in the repo. The diff is the bare-callers backlog.

---

## 5. Migration safety

- All schema changes are additive: new columns nullable, new tables created idempotently with `CREATE TABLE IF NOT EXISTS`.
- `_row_to_routing_decision` extended to read new fields with `.get()`-style defaults; old rows still read.
- `routing_decisions.jsonl` continues to be the audit file. New rows have additional fields; old readers ignoring unknown keys still work.
- Phase 1 ships behind the existing `DGC_ROUTER_TELEMETRY_ENABLE` env (already on in `run_operator.sh` since Move 2 today). No new env var.
- A second env `DGC_ROUTE_WITNESS_DISABLE_HELPER=1` provides an emergency kill-switch — set this if the helper itself misbehaves; ModelRouter falls back to its prior emission path.

---

## 6. Verification before declaring Phase 1 done

1. Manual fire of `pulse_alt_lanes.py` produces:
   - A new row in `routing_decisions.jsonl` with `row_kind="decision"`, `caller="pulse_alt_lanes"`, populated dashboard-ready fields.
   - One `row_kind="attempt"` per provider tried (≥1, often 2: claude_code attempt then openai attempt).
   - Matching rows in `runtime.db` (`routing_decisions` + `provider_attempts` tables).
   - `error_detail` ≤ 200 chars, no secrets in any stored field.

2. Manual fire of `inquiry_substrate_chew.py` produces same shape with `caller="inquiry_substrate_chew"`.

3. `make test-smoke` passes (no test breakage).

4. Targeted pytest covers:
   - Schema additions (new fields readable from old rows).
   - `ProviderAttemptRecord` round-trip through SQLite.
   - Redaction (test that `sk-...` patterns get scrubbed in `error_detail`).
   - Best-effort failure (witness write fails → caller still gets normal response).

5. JSON schema for the JSONL written next to the audit file at `~/.dharma/logs/router/routing_decisions_v1.schema.json`.

6. Witness entry at `~/.dharma/witness/2026-05-10-inhabitant-claude-phase1-routing.md` with smoke results, predicted Grafana panels, and Phase 1.5 / Phase 2 hand-off.

---

## 7. Anti-magic invariants

- **`route_witness.py` is the only module that constructs `RoutingDecisionRecord` from non-test code.** Other modules pass kwargs to its public functions; they never instantiate the record themselves.
- **`route_witness.py` is the only module that writes to `routing_decisions.jsonl`.** Other emitters either go through it or are explicitly grandfathered (only `ModelRouter` if its existing direct write must remain for backwards compat — to be confirmed during implementation).
- **`route_witness.py` does not import from `provider_policy.py` or `decision_router.py`.** It is a downstream witness, not an upstream policy or classifier. Imports flow one way: callers → route_witness → telemetry_plane.
- **No decorator, no metaclass, no monkey-patch, no global mutable state in route_witness.** All state lives in records, all behavior in functions.

---

## 8. Hand-off to next phase

Phase 1 produces ≥3 days of populated `routing_decisions.jsonl` with full dashboard-ready dimensions. Phase 2 reads the actual data to:

- Decide whether `is_budget_exceeded` preflight matters (does cost_estimate_usd actually exceed budget?).
- Decide whether silent CLAUDE_CODE fallback fires (does any decision_class="fallback" with selected_provider="claude_code" appear?).
- Identify which bare-provider callers from §4.5 actually fire and instrument them.
- Promote any frequently-queried `metadata` keys to typed columns.

Phase 3 promotes `RoutingDecisionRecord` + `ProviderAttemptRecord` to first-class ontology objects linked via `TelicSeam` to `ActionProposal` → `Outcome` → `ValueEvent` → `Contribution`.

End of spec.
