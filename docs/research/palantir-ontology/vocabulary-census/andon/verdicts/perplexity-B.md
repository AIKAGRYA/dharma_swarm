# Slice B Verdict — Envelope Schemas

**Agent:** perplexity-computer  
**Slice:** B (Codex claim #2 — "7 envelope schemas, pairwise incompatible")  
**Branch:** perplexity-grounding/1780289724-vocabulary-census  
**Timestamp:** 2026-06-01  
**Verdict:** `partially_confirmed`

---

## Envelopes Found and Characterized

### 1. RuntimeEnvelope

**Path:** `dharma_swarm/runtime_contract.py:41–50`

**Fields:**
| Field | Type |
|---|---|
| `contract_version` | `str` |
| `event_id` | `str` |
| `event_type` | `str` |
| `emitted_at` | `str` (ISO-8601) |
| `source` | `str` |
| `agent_id` | `str` |
| `session_id` | `str` |
| `trace_id` | `str` |
| `payload` | `dict[str, Any]` |
| `checksum` | `str` (SHA-256) |

**Purpose:** Append-only, content-addressed event record for the runtime event log (`event_log.py:33`); checksum enforces integrity on write.

**Consumers:** `dharma_swarm/event_log.py`, `dharma_swarm/evaluation_registry.py`, `dharma_swarm/session_event_bridge.py`, `dharma_swarm/flywheel_exporter.py`, `dharma_swarm/memory_lattice.py`, `dharma_swarm/orchestrator.py`, `dharma_swarm/canonical_replay.py`.

---

### 2. MessageBus row (messages table)

**Path:** `dharma_swarm/message_bus.py:27–35` (DDL); `dharma_swarm/models.py:243–255` (Python model)

**Fields (SQLite DDL → `Message` model):**
| Field | Type |
|---|---|
| `id` | `TEXT` / `str` |
| `from_agent` | `TEXT` / `str` |
| `to_agent` | `TEXT` / `str` |
| `subject` | `TEXT` / `Optional[str]` |
| `body` | `TEXT` / `str` |
| `priority` | `TEXT` / `MessagePriority` |
| `status` | `TEXT` / `MessageStatus` |
| `created_at` | `TEXT` / `datetime` |
| `read_at` | `TEXT` / `Optional[datetime]` |
| `reply_to` | `TEXT` / `Optional[str]` |
| `metadata` | `TEXT` (JSON) / `dict[str, Any]` |

**Purpose:** Agent-to-agent async message store (SQLite-backed pub/sub); carries durable inter-agent tasks and notifications.

**Note:** `MessageBus` also has an `events` sub-table (`message_bus.py:57–67`) with a distinct 7-column schema (`event_id`, `event_type`, `task_id`, `agent_id`, `source_pid`, `occurred_at`, `payload`). This is a second flat schema living inside the same SQLite file. It does NOT overlap with `RuntimeEnvelope`.

---

### 3. A2ATask

**Path:** `dharma_swarm/a2a/a2a_server.py:184–233`

**Fields:**
| Field | Type |
|---|---|
| `id` | `str` (hex, 16 chars) |
| `context_id` | `str` |
| `from_agent` | `str` |
| `to_agent` | `str` |
| `status` | `A2ATaskStatus` (8 states) |
| `history` | `list[A2AMessage]` |
| `messages` | `list[A2AMessage]` (alias of history) |
| `artifacts` | `list[A2AArtifact]` |
| `capability` | `str` |
| `dharma_task_id` | `str` |
| `created_at` | `str` (ISO-8601) |
| `updated_at` | `str` (ISO-8601) |
| `result` | `str` |
| `error` | `str` |
| `trace_id` | `str` |
| `extensions` | `list[A2AExtension]` |
| `metadata` | `dict[str, Any]` |

**Purpose:** A2A 1.0 spec-conformant work unit — the primary inter-agent task container for request/response lifecycle and artifact delivery.

---

### 4. OnboardingReceipt (A2A receipt schema)

**Path:** `dharma_swarm/roaming_onboarding.py:101–113`

**Fields:**
| Field | Type |
|---|---|
| `receipt_id` | `str` |
| `agent_uid` | `str` |
| `callsign` | `str` |
| `team_id` | `str` |
| `department` | `str` |
| `squad_id` | `str` |
| `harness` | `str` |
| `endpoint` | `str` |
| `dock_path` | `str` |
| `card_path` | `str` |
| `telemetry_db_path` | `str` |
| `receipt_path` | `str` |
| `created_at` | `str` (ISO-8601) |

**Purpose:** Frozen onboarding paper trail written once per agent registration; consumed by `registry_hydrator.py` to populate `NodeRegistry`.

---

### 5. NATS contact envelope

**Actual location:** `/home/user/workspace/nats/` — **not** inside `dharma_swarm/`. There is no Python NATS client library in `dharma_swarm/` at all (`dharma_swarm/a2a/node_gateway.py:20` lists "gRPC / NATS transport bindings (Tier 2)" as **not yet implemented**).

NATS envelopes are bare-text or ad hoc JSON dicts assembled in `/home/user/workspace/nats/`.

**Two formats observed:**

**a) Text-header format** (`nats/a2a_client.py:44`):
```
[perplexity->claude] <ISO-timestamp>\n<body>
```
Fields: routing header (prefix string), freeform body. No typed schema.

**b) Structured JSON dict** (`nats/_andon_broadcast.py:16–32`):
| Field | Type |
|---|---|
| `kind` | `str` |
| `severity` | `str` |
| `from` | `str` |
| `to` | `str` |
| `at` | `str` |
| `subject_line` | `str` |
| `branch` | `str` |
| `...` | various |

**c) Presence beacon** (`nats/presence_heartbeat.py:50–63`):
| Field | Type |
|---|---|
| `agent` | `str` |
| `callsign` | `str` |
| `version` | `str` |
| `role` | `str` |
| `subscribes` | `list[str]` |
| `publishes` | `list[str]` |
| `pid` | `int` |
| `host` | `str` |
| `ts` | `str` |
| `uptime_s` | `int` |
| `beacon_seq` | `int` |

**Purpose:** Inter-process fleet coordination over the agni VPS NATS broker. No schema enforcement — Codex's claim that there is a single "NATS contact envelope" understates the fragmentation: there are at least three ad hoc shapes on the wire.

---

### 6. SignalBus dict

**Path:** `dharma_swarm/signal_bus.py:95–113`

**Schema:** Untyped `dict[str, Any]` with one mandatory key:
| Field | Type |
|---|---|
| `"type"` | `str` (e.g. `"ANOMALY_DETECTED"`, `"LIFECYCLE_TASK_STARTED"`) |
| `*` | arbitrary — caller-defined additional keys |

**Example shapes from call sites:**
- `agent_runner.py:2431`: `{"type": "LIFECYCLE_TASK_STARTED", "agent": str, "task_id": str, "task_title": str, "timestamp": str}`
- `a2a_bridge.py:269`: `{"type": str, "task_id": str, "from": str, "to": str, "capability": str, "status": str}`

**Purpose:** In-process synchronous loop-to-loop heartbeat bus (single asyncio event loop); explicitly NOT the inter-agent message bus (`signal_bus.py:1–12`).

---

### 7. "Spec envelope" — NOT FOUND as a code artifact

Codex lists a "spec envelope" as the 7th schema. No Python class, dataclass, or Pydantic model named `SpecEnvelope` or similar exists in the repo. Three candidate interpretations were checked:

- `ControlSurfaceEnvelope` (`dharma_swarm/operator_core/control_surface_models.py:98`): an API **response wrapper** (`schema_version`, `request_id`, `generated_at`, `source_errors`, `freshness_window`, `data`) used only by the control surface API router. This is plausible as Codex's intended "spec envelope."
- `CanonicalEvent` (`dharma_swarm/engine/events.py:58`): a provider-neutral LLM event envelope used internally by `dharma_swarm/engine/`. Fields: `event_type`, `timestamp`, `event_id`, `source_agent`, `target_agent`, `session_id`, `artifact_id`, `payload`, `metadata`.
- Spec documents (`docs/architecture/SWARM_BOARDSTORE_SPEC.md`, `docs/architecture/SHAKTI_GINKO_ORGAN.md`): describe envelope shapes in prose/table but contain no code artifacts.

**The 7th "spec envelope" is unidentified as a distinct code artifact.** If Codex meant `ControlSurfaceEnvelope`, that schema is an API response wrapper — a different concern from the 6 message-carrying envelopes.

---

## Field Overlap Table

Rows = fields; columns = envelopes. ✓ = present, — = absent.

| Field | RuntimeEnvelope | MessageBus `messages` | A2ATask | OnboardingReceipt | NATS (JSON) | SignalBus dict |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `id` / `event_id` / `receipt_id` | ✓ (`event_id`) | ✓ (`id`) | ✓ (`id`) | ✓ (`receipt_id`) | — | — |
| `from_agent` / `from` | — | ✓ (`from_agent`) | ✓ (`from_agent`) | — | ✓ (`from`) | — |
| `to_agent` / `to` | — | ✓ (`to_agent`) | ✓ (`to_agent`) | — | ✓ (`to`) | — |
| `created_at` / `emitted_at` / `at` / `ts` | ✓ (`emitted_at`) | ✓ (`created_at`) | ✓ (`created_at`) | ✓ (`created_at`) | ✓ (`at`/`ts`) | — |
| `agent_id` / `agent` | ✓ (`agent_id`) | — | — | ✓ (`agent_uid`) | ✓ (`agent`) | ✓ (`agent`) |
| `session_id` | ✓ | — | — | — | — | — |
| `trace_id` | ✓ | — | ✓ | — | — | — |
| `payload` / `body` / `metadata` | ✓ (`payload`) | ✓ (`body`+`metadata`) | ✓ (`metadata`) | — | ✓ (body) | ✓ (free keys) |
| `checksum` | ✓ | — | — | — | — | — |
| `status` | — | ✓ (`status`) | ✓ (`status`) | — | — | — |
| `type` / `event_type` | ✓ (`event_type`) | — | — | — | ✓ (`kind`) | ✓ (`type`) |
| `source` / `callsign` | ✓ (`source`) | — | — | ✓ (`callsign`) | ✓ (`from`) | — |
| `contract_version` | ✓ | — | — | — | — | — |
| `endpoint` | — | — | — | ✓ | — | — |
| `history` / `artifacts` | — | — | ✓ | — | — | — |
| `capability` | — | — | ✓ | — | — | — |
| `dharma_task_id` | — | — | ✓ | — | — | — |

**Observations:**
- No two envelopes share a common required field set. `trace_id` overlaps only `RuntimeEnvelope` ↔ `A2ATask`.
- `from_agent` / `to_agent` routing appears in `MessageBus.messages`, `A2ATask`, and NATS — three independent namings of the same semantic with no shared type.
- `RuntimeEnvelope` is the only schema with a `checksum` integrity field.
- `SignalBus` is the only schema with no identity field at all.

---

## Translator Inventory

The following code paths translate **between** envelope types:

| Path | From | To | File:line |
|---|---|---|---|
| `A2ABridge.trishula_message_to_a2a_task` | TRISHULA `dict` (file-based) | `A2ATask` | `dharma_swarm/a2a/a2a_bridge.py:74` |
| `A2ABridge.a2a_task_to_trishula_message` | `A2ATask` | TRISHULA `dict` | `dharma_swarm/a2a/a2a_bridge.py:187` |
| `A2ABridge._emit_signal` | `A2ATask` fields | `SignalBus` dict | `dharma_swarm/a2a/a2a_bridge.py:263–283` |
| `SessionEventBridge.session_start / session_interaction / session_end` | `SessionEvent` | `RuntimeEnvelope` | `dharma_swarm/session_event_bridge.py:51+` |
| `MessageBusGatewayAdapter` | `Message` (MessageBus row) | gateway message dict | `dharma_swarm/contracts/runtime_adapters.py:519` |
| `RuntimeInteropAdapter.export_snapshot` | `RuntimeEnvelope` + `Message` + A2A | flat dict snapshot | `dharma_swarm/contracts/runtime_adapters.py:783` |
| `hydrate_from_receipts` | `OnboardingReceipt` JSONL | `RemoteNode` in `NodeRegistry` | `dharma_swarm/a2a/registry_hydrator.py:79` |

**Gaps — no translator found:**
- `RuntimeEnvelope` → `A2ATask`: no code path. A `RuntimeInteropAdapter` snapshot includes both but does not map fields one-to-one.
- `RuntimeEnvelope` → `SignalBus` dict: no code path.
- `MessageBus.messages` row → `A2ATask`: no code path. `A2ABridge` converts TRISHULA file-inbox messages, not `MessageBus` rows.
- `OnboardingReceipt` → any of the 5 other envelopes: no code path beyond registry hydration.
- NATS wire formats → any internal envelope: no code path in `dharma_swarm/`; NATS lives entirely in `/home/user/workspace/nats/`.

---

## Headline Verdict for Slice B

**`partially_confirmed`** — and leaning toward **`incompatible-and-unbridged`**.

**Confirmed:** 6 of the 7 envelopes exist and are genuinely incompatible (no shared type signature, no common required field set). `A2ABridge` translates TRISHULA↔A2ATask and emits A2ATask events to `SignalBus`; `SessionEventBridge` translates session events into `RuntimeEnvelope`. These two bridges cover ~3 of the 15 possible pairwise paths.

**Overstated in one dimension:** The "7th envelope" (Codex's "spec envelope") does not exist as a distinct code artifact. The closest candidates are `ControlSurfaceEnvelope` (an API response wrapper, not a message-carrying envelope) and `CanonicalEvent` (an LLM engine event, not a coordination envelope). Codex appears to have combined two unrelated things into a single count.

**Understated in another dimension:** NATS is not one envelope — it is at least three ad hoc wire formats (text-header, `kind`-keyed JSON, presence beacon) with no schema enforcement. Codex's count of "7" likely undercounts the NATS fragmentation.

The count is off (6 confirmed code envelopes, not 7), but the structural diagnosis — independent schemas with almost no shared field surface and sparse bridging — is accurate.

---

## What I Observed That Codex Did NOT Flag

1. **NATS is outside `dharma_swarm/` entirely.** `dharma_swarm/a2a/node_gateway.py:20` explicitly declares NATS/gRPC as "Tier 2 — not yet implemented." The live NATS coordination visible in `/home/user/workspace/nats/` is operated by a separate process (`agni_daemon.py`, `a2a_client.py`, `presence_heartbeat.py`) with no schema contract enforced anywhere. Codex counted "NATS contact envelope" as if it were a defined schema; it is an ad hoc string format with at least three in-practice shapes. This is worse than Codex implied.

2. **`MessageBus` contains two disjoint sub-schemas.** The `messages` table and the `events` table (`message_bus.py:57–67`) are both inside `MessageBus` but carry entirely different fields. Codex's "MessageBus rows" conflates them into one. The `events` table (`event_id`, `event_type`, `task_id`, `agent_id`, `source_pid`, `occurred_at`, `payload`) is closer semantically to `RuntimeEnvelope` than the `messages` table is, yet there is no code that bridges between them.

3. **`CanonicalEvent` is an 8th envelope Codex missed entirely.** `dharma_swarm/engine/events.py:58` defines `CanonicalEvent` — a provider-neutral event envelope for LLM orchestration events with 9 fields including `event_id`, `source_agent`, `target_agent`, `session_id`, `artifact_id`, `payload`. It overlaps semantically with `RuntimeEnvelope` but has no adapter connecting them. It is consumed only within `dharma_swarm/engine/` and never referenced by `event_log.py` or `evaluation_registry.py`.

4. **`SessionEventBridge` is the only translator that converts INTO `RuntimeEnvelope`** (`dharma_swarm/session_event_bridge.py:51`). All other envelope types remain isolated. The `RuntimeInteropAdapter` (`contracts/runtime_adapters.py:740`) bundles multiple envelope types into a flat snapshot dict but does not provide bidirectional field mapping — it is a projection, not a translator.

5. **`trace_id` overlaps `RuntimeEnvelope` and `A2ATask` but is wired differently.** `RuntimeEnvelope.trace_id` is auto-generated at creation (`runtime_contract.py:68`); `A2ATask.trace_id` is an optional carry-through (`a2a_server.py:213`) with no mechanism forcing them to be the same value across a single agent interaction. This means a single causal chain (operator → A2ATask → RuntimeEnvelope events) has two independent `trace_id` lineages with no join key — an observability gap Codex did not name.
