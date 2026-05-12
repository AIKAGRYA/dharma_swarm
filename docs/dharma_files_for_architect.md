# Dharma Fleet Control Plane Architect Packet

This is the compact handoff extracted from `docs/dharma_fleet_control_plane_audit.md`. It does not propose source edits beyond a future PR 1.

## 1. Most Important Files For The External Architect

1. `docs/plans/2026-03-26-roaming-control-plane-spec.md`
   - Why it matters: existing design intent for roaming agents and the hybrid control-plane direction.
   - Key areas: federated bootstrap, git mailbox limits, proposed VPS control plane.
   - Inspect: lines 5-27, 52-105, 107-177, 179-230, 285-320.

2. `api/main.py`
   - Why it matters: FastAPI app root, auth middleware, CORS, router registration.
   - Key classes/functions: `BearerAuthMiddleware`, app router includes.
   - Inspect: lines 60-67, 151-211, 227-285.

3. `api/routers/commands.py`
   - Why it matters: current dashboard task command surface.
   - Key handlers: `/commands/task`, `/commands/tasks`, `/commands/dispatch`, `/commands/dharma`.
   - Inspect: lines 17-118.

4. `api/routers/agents.py`
   - Why it matters: current agent list/detail/spawn/chat/websocket surface.
   - Key handlers: `list_agents`, `spawn_agent`, `chat_with_agent`, `agents_ws`.
   - Inspect: lines 296-404, 499-582.

5. `api/routers/telemetry.py`
   - Why it matters: current telemetry API, not Prometheus/OpenTelemetry.
   - Key handlers: overview, routing, economics, agents, events, outcomes, project.
   - Inspect: lines 94-239.

6. `api/routers/interop.py`
   - Why it matters: untracked but highly relevant typed task/worker API prototype.
   - Key handlers: `interop_status`, `interop_tasks`, `claim_next`, `heartbeat`, `record_response`, stream.
   - Inspect: lines 54-132.
   - Important note: it is not registered in `api/main.py` in the inspected tree.

7. `dashboard/src/lib/api.ts`
   - Why it matters: dashboard client API; reveals missing individual task endpoint and missing interop exports.
   - Key functions: `apiRequest`, `fetchTasks`, `createTask`, `fetchHealth`.
   - Inspect: lines 46-135, 178-210.

8. `dharma_swarm/models.py`
   - Why it matters: core local task, agent, role, provider models.
   - Key classes: `TaskStatus`, `AgentRole`, `ProviderType`, `Task`, `AgentConfig`, `AgentState`.
   - Inspect: lines 19-26, 43-65, 114-133, 156-240.

9. `dharma_swarm/task_board.py`
   - Why it matters: durable local task board with status transitions.
   - Key classes/functions: `TaskBoard`, `_TRANSITIONS`, task/dependency schema, create/list/status methods.
   - Inspect: lines 18-40, 66-217, 287-309, 365-529.

10. `dharma_swarm/runtime_state.py`
    - Why it matters: broad SQLite runtime state store with sessions, claims, leases, artifacts, events.
    - Key objects: `DEFAULT_RUNTIME_DB`, DDL, runtime dataclasses, `RuntimeStateStore`.
    - Inspect: lines 28-220, 327-473, 718 onward.

11. `dharma_swarm/operator_bridge.py`
    - Why it matters: closest existing durable typed task queue with claim, heartbeat, artifact, recover, response.
    - Key classes/functions: `OperatorBridgeTask`, `OperatorBridge.enqueue_task`, `claim_task`, `heartbeat_task`, `record_partial_artifact`, `recover_stale_tasks`, `respond_task`.
    - Inspect: lines 51-79, 140-182, 226-1011.

12. `dharma_swarm/telemetry_plane.py`
    - Why it matters: central telemetry schema for routing, policy, provider attempts, reward ledger.
    - Key objects: telemetry DDL, policy decisions table, `TelemetryPlaneStore`.
    - Inspect: lines 24-55, 94-145, 166-261.

13. `dharma_swarm/message_bus.py`
    - Why it matters: SQLite-backed local message, heartbeat, artifact, and event bus.
    - Key classes/functions: `MessageBus`, messages/heartbeats/artifacts/events schema, send/receive/pubsub/heartbeat/artifact/event APIs.
    - Inspect: lines 30-83, 111-675.

14. `dharma_swarm/signal_bus.py`
    - Why it matters: in-process async pub/sub used for local signals.
    - Key classes/functions: `SignalBus`, `Signal`, handler subscription and emit.
    - Inspect: lines 1-14, 47-180.

15. `dharma_swarm/handoff.py`
    - Why it matters: JSONL durable handoff protocol and artifact model.
    - Key classes/functions: `Artifact`, `Handoff`, `HandoffProtocol`.
    - Inspect: lines 87-363.

16. `dharma_swarm/trishula_bridge.py`
    - Why it matters: file-inbox bridge from Trishula messages into Dharma tasks.
    - Key classes/functions: `TrishulaBridge`, `process_inbox`, `create_task_from_message`.
    - Inspect: lines 20-22, 102-347, 203-224.

17. `dharma_swarm/a2a/agent_card.py`
    - Why it matters: current local A2A capability and card registry model.
    - Key classes/functions: `AgentCapability`, `AgentCard`, `CardRegistry`.
    - Inspect: lines 28-29, 41-180, 250-413.

18. `dharma_swarm/a2a/a2a_server.py`
    - Why it matters: current local A2A task lifecycle and in-memory task store.
    - Key classes/functions: `A2ATaskStatus`, `A2ATask`, `A2AServer.submit_task`, `process_task`, `cancel_task`.
    - Inspect: lines 7-13, 33-41, 86-118, 130-302.

19. `dharma_swarm/a2a/a2a_client.py`
    - Why it matters: local-only A2A delegation client.
    - Key classes/functions: `A2AClient.delegate`, `delegate_to`.
    - Inspect: lines 7-8, 72-232.

20. `dharma_swarm/a2a/a2a_bridge.py`
    - Why it matters: translation layer between Trishula mailbox messages and local A2A tasks.
    - Key classes/functions: `A2ABridge`, `trishula_message_to_a2a_task`, `ingest_trishula_inbox`, `send_result_to_trishula`.
    - Inspect: lines 45-71, 75-181, 185-268.

21. `dharma_swarm/roaming_mailbox.py`
    - Why it matters: git-friendly cross-harness task and response mailbox.
    - Key classes/functions: `MailboxTask`, `MailboxResponse`, `RoamingMailbox`.
    - Inspect: lines 1-10, 39-208.

22. `dharma_swarm/roaming_poller.py`
    - Why it matters: remote-side pull/claim/respond loop for roaming mailbox.
    - Key classes/functions: `GitMailboxSync`, `RoamingPoller.process_once`.
    - Inspect: lines 1-10, 37-68, 70-166.

23. `dharma_swarm/roaming_operator_bridge.py`
    - Why it matters: bridge between durable operator tasks and git mailbox transport.
    - Key classes/functions: `RoamingOperatorBridge`.
    - Inspect: lines 1-4, 28-143.

24. `dharma_swarm/roaming_onboarding.py`
    - Why it matters: onboarding records for OpenClaw, Claude Code, Codex, Hermes, VPS workers.
    - Key classes/functions: `RoamingAgentRegistration`, `onboard_roaming_agent`.
    - Inspect: lines 1-13, 80-97, 132-277.

25. `dharma_swarm/terminal_adapters/base.py`
    - Why it matters: closest existing generic CLI model adapter base, but it is completion-stream oriented rather than task-lifecycle oriented.
    - Key classes/functions: `Capability`, `ModelProfile`, `ProviderConfig`, `CompletionRequest`, `ProviderAdapter`.
    - Inspect: lines 13-96.

## 2. Current Local A2A Flow In 10 Bullets

1. `AgentCard` describes a local agent with name, description, capabilities, endpoint, auth type, role, model, provider, status, version, timestamps, and metadata in `dharma_swarm/a2a/agent_card.py`.
2. `CardRegistry` stores cards as JSON files under the default `.dharma/a2a/cards` path unless another cards directory is passed.
3. `A2AServer` is initialized with a `CardRegistry`, optional dispatcher callback, optional `SignalBus`, and an in-memory `_tasks` dictionary.
4. `A2AServer.submit_task` creates an `A2ATask`, sets it to queued, records timestamps, and keeps it only in process memory.
5. `A2AServer.process_task` moves a task to working, calls the dispatcher if provided, and then marks the task completed or failed.
6. `A2AServer.cancel_task` can cancel a queued or working in-memory task, but there is no durable lease or remote cancellation protocol.
7. `A2AClient.delegate` and `delegate_to` resolve local agent cards and submit to the local server. The file comments explicitly mark HTTP remote support as future work.
8. `A2ABridge.trishula_message_to_a2a_task` translates file-inbox Trishula JSON messages into `A2ATaskRequest` objects.
9. `A2ABridge.ingest_trishula_inbox` submits translated tasks into the local A2A server and emits optional local signals.
10. `tests/test_a2a.py` covers cards, registry behavior, local server lifecycle, local client delegation, and Trishula bridge conversion. It does not prove HTTP, SSE, node gateway, or durable cross-host behavior.

## 3. Current Remote/Cross-VPS Flow In 10 Bullets

1. The roaming design currently uses a git-friendly mailbox, described in `roaming_mailbox.py` and `docs/plans/2026-03-26-roaming-control-plane-spec.md`.
2. `RoamingMailbox` writes task and response JSON files rather than using a live RPC, queue, or database-backed node gateway.
3. `RoamingOperatorBridge` mirrors selected operator bridge tasks into the roaming mailbox and imports mailbox responses back into the operator bridge.
4. `RoamingPoller` is intended to run on a remote harness: it syncs the mailbox, claims work, executes a local callback, writes a response, and syncs again.
5. `roaming_dispatch_daemon.py` provides a local dispatch/collect loop around mailbox sync, but the transport remains git/file based.
6. `roaming_onboarding.py` creates living agent records, cards, runtime metadata, and receipts for external harnesses such as OpenClaw, Claude Code, Codex, Hermes, and VPS workers.
7. `trishula_bridge.py` scans `~/trishula/inbox` and writes processed-message state under `~/.dharma/trishula_processed.json`.
8. `scripts/sync_jikoku.sh` pulls Jikoku logs from known VPS aliases/IPs for Agni and Rushabdev, but it is observability sync, not task dispatch.
9. `dharma_swarm/context.py` reads local Agni state files such as `WORKING.md`, `HEARTBEAT.md`, and `PRIORITIES.md`; this is passive file-state ingestion.
10. No inspected code proves a live authenticated remote node gateway, per-node heartbeat API, durable central task state, remote SSE event stream, or remote artifact upload path.

## 4. Exact Missing Pieces

### Central Task Store

- Missing: one canonical durable `fleet_tasks` store owned by the control plane.
- Existing partials: `task_board.py`, `operator_bridge.py`, `runtime_state.py`, `message_bus.py`, and A2A in-memory `_tasks`.
- Required fields: `task_id`, `parent_task_id`, `idempotency_key`, `title`, `kind`, `description`, `payload_json`, `required_capabilities_json`, `repo`, `branch`, `requested_by`, `status`, `priority`, `risk_level`, `approval_status`, `assigned_node_id`, `assigned_worker_id`, `lease_owner`, `lease_expires_at`, `created_at`, `updated_at`, `started_at`, `completed_at`, `failed_reason`.

### Node Registry

- Missing: canonical `nodes` table/model for VPSes, Mac Minis, and local machines.
- Existing partials: ontology entries for Agni/Rushabdev, roaming onboarding records, operator interop adapter registry.
- Required fields: `node_id`, `display_name`, `hostname`, `environment`, `transport`, `base_url`, `public_key_fingerprint`, `status`, `last_seen_at`, `metadata_json`, `created_at`, `updated_at`.

### Heartbeat

- Missing: durable per-node and per-worker heartbeat accepted by a central API.
- Existing partials: `message_bus.heartbeats`, `operator_bridge.heartbeat_task`, Trishula/Jikoku state files.
- Required fields: `heartbeat_id`, `node_id`, `worker_id`, `reported_at`, `status`, `cpu_percent`, `memory_percent`, `disk_percent`, `active_task_count`, `capabilities_json`, `metadata_json`.

### Node Gateway

- Missing: registered FastAPI router for node health, capability registration, task accept/status/events, artifact upload.
- Existing partials: unregistered `api/routers/interop.py`, local A2A server, roaming poller.
- Required endpoints: `POST /api/nodes/register`, `POST /api/nodes/{node_id}/heartbeat`, `POST /api/node-gateway/tasks/{task_id}/accept`, `GET /api/node-gateway/tasks/{task_id}`, `GET /api/node-gateway/tasks/{task_id}/events`, `POST /api/node-gateway/tasks/{task_id}/artifacts`.

### Worker Adapters

- Missing: task-oriented adapter interface with health, start, status, events, cancel, artifacts.
- Existing partials: `terminal_adapters.ProviderAdapter`, `operator_core/interop.py`, `operator_core/interop_worker.py`, `runtime_bridge.py`.
- Required interface: `AgentAdapter.health`, `start_task`, `get_status`, `stream_events`, `cancel`, `collect_artifacts`.

### A2A HTTP Transport

- Missing: HTTP facade for agent cards, task submission, task status, and SSE.
- Existing partials: local `CardRegistry`, local `A2AServer`, local `A2AClient`, local `A2ABridge`.
- Required endpoints: `GET /.well-known/agent-card.json`, `POST /api/a2a/tasks`, `GET /api/a2a/tasks/{task_id}`, `GET /api/a2a/tasks/{task_id}/events`.
- Required behavior: back A2A task lifecycle with the central durable task/event store rather than `A2AServer._tasks`.

### Grafana Metrics

- Missing: Prometheus `/metrics`, OpenTelemetry traces, Loki label discipline.
- Existing partials: `telemetry_plane.py`, `observability.py`, `jikoku_samaya.py`, `scripts/sync_jikoku.sh`.
- Required metrics: `dharma_node_up`, `dharma_node_last_heartbeat_timestamp`, `dharma_worker_up`, `dharma_worker_busy`, `dharma_task_total`, `dharma_task_duration_seconds`, `dharma_task_failed_total`, `dharma_approval_pending_total`, `dharma_repo_lock_active`, `dharma_artifact_uploaded_total`, `dharma_llm_tokens_total`, `dharma_llm_cost_usd_total`.

### Auth/Approval Gates

- Missing: enforced node identity and scoped task tokens for remote gateways.
- Existing partials: `api/main.py` bearer API-key middleware, `provider_policy.py`, `decision_router.py`, `operator_core/permissions.py`, `sandbox.py`, `injection_scanner.py`, `api/chat_tools.py`.
- Required v1 model: private network only, per-node identity, per-task scoped tokens, central approval records, no public agent ports, no secrets in logs, append-only audit trail.

## 5. Recommended PR 1: Central Task/Event/Artifact Schema

Goal:
- Add a durable canonical fleet task, task event, and task artifact store without changing remote dispatch behavior yet.
- Keep it local and SQLite-backed to match existing repo patterns.
- Do not depend on node gateways, A2A HTTP, NATS, Temporal, Prometheus, or frontend changes in PR 1.

Files to add:
- `dharma_swarm/fleet/__init__.py`
- `dharma_swarm/fleet/models.py`
- `dharma_swarm/fleet/store.py`
- `tests/test_fleet_store.py`

Files to edit:
- None required for the minimal PR.
- Optional only if local conventions require exports: `dharma_swarm/__init__.py`.

Proposed tables:
- `fleet_tasks`
- `fleet_task_events`
- `fleet_task_artifacts`

Minimum `fleet_tasks` columns:
- `task_id TEXT PRIMARY KEY`
- `parent_task_id TEXT`
- `idempotency_key TEXT UNIQUE`
- `title TEXT NOT NULL`
- `kind TEXT NOT NULL`
- `description TEXT NOT NULL DEFAULT ''`
- `payload_json TEXT NOT NULL DEFAULT '{}'`
- `required_capabilities_json TEXT NOT NULL DEFAULT '[]'`
- `repo TEXT`
- `branch TEXT`
- `requested_by TEXT`
- `status TEXT NOT NULL`
- `priority INTEGER NOT NULL DEFAULT 0`
- `risk_level TEXT NOT NULL DEFAULT 'normal'`
- `approval_status TEXT NOT NULL DEFAULT 'not_required'`
- `assigned_node_id TEXT`
- `assigned_worker_id TEXT`
- `lease_owner TEXT`
- `lease_expires_at TEXT`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `started_at TEXT`
- `completed_at TEXT`
- `failed_reason TEXT`

Minimum `fleet_task_events` columns:
- `event_id TEXT PRIMARY KEY`
- `task_id TEXT NOT NULL`
- `node_id TEXT`
- `worker_id TEXT`
- `event_type TEXT NOT NULL`
- `status TEXT`
- `message TEXT NOT NULL DEFAULT ''`
- `payload_json TEXT NOT NULL DEFAULT '{}'`
- `severity TEXT NOT NULL DEFAULT 'info'`
- `correlation_id TEXT`
- `trace_id TEXT`
- `created_at TEXT NOT NULL`

Minimum `fleet_task_artifacts` columns:
- `artifact_id TEXT PRIMARY KEY`
- `task_id TEXT NOT NULL`
- `node_id TEXT`
- `worker_id TEXT`
- `name TEXT NOT NULL`
- `kind TEXT NOT NULL`
- `uri TEXT NOT NULL`
- `sha256 TEXT`
- `size_bytes INTEGER`
- `metadata_json TEXT NOT NULL DEFAULT '{}'`
- `created_at TEXT NOT NULL`

Indexes:
- `idx_fleet_tasks_status`
- `idx_fleet_tasks_assigned_node`
- `idx_fleet_tasks_created_at`
- `idx_fleet_task_events_task_created`
- `idx_fleet_task_artifacts_task`

Tests to add:
- Creating the store initializes all three tables idempotently.
- Creating a task persists JSON payload and required capabilities.
- Idempotency key returns or rejects duplicate submissions deterministically.
- Status transition updates `updated_at` and appends a task event.
- Appending events preserves order by `created_at`.
- Recording artifacts links them to the task and preserves metadata JSON.
- Lease fields can be set and cleared without changing unrelated task fields.
- Invalid status and invalid approval status are rejected at the model/store boundary.

Suggested test commands:
- `pytest -q tests/test_fleet_store.py`
- `pytest -q tests/test_task_board.py tests/test_message_bus.py tests/test_operator_bridge.py tests/test_fleet_store.py`

Acceptance criteria:
- No existing task board, A2A, operator bridge, or API behavior changes.
- New store can be used by later PRs as the control-plane source of truth.
- The schema can represent local tasks now and remote node-dispatched tasks later.
- Tests pass with a temporary SQLite database and do not touch the user's real `.dharma` state.

Primary risks:
- Duplicating existing task concepts without a clear migration path.
- Choosing names that collide with `TaskBoard` or `OperatorBridge` semantics.
- Letting PR 1 grow into routing or node-gateway work. Keep PR 1 as persistence only.

