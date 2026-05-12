# Dharma Fleet Control Plane Repo Audit

Audit date: 2026-05-11
Repo inspected: `/Users/dhyana/dharma_swarm`
Branch: `cleanup/mixed-quality-recovery-2026-05-10`
Worktree state before this report: dirty; many modified files and untracked interop files existed before the audit. Notable untracked fleet-relevant files include `api/routers/interop.py`, `dharma_swarm/operator_core/interop.py`, `dharma_swarm/operator_core/interop_worker.py`, `dashboard/src/hooks/useInterop.ts`, `dashboard/src/app/dashboard/interop/`, and `tests/test_interop_router.py`.

## 0. Executive Summary

What already exists for local agent coordination:

- Local task state: `dharma_swarm/task_board.py` defines a SQLite `tasks` table and explicit status FSM (`pending`, `assigned`, `running`, `completed`, `failed`, `cancelled`) at lines 18-25 and 27-40.
- Local messaging: `dharma_swarm/message_bus.py` is an async SQLite-backed bus with `messages`, `heartbeats`, `subscriptions`, `artifacts`, and `events` tables at lines 30-83.
- Local bridge queue: `dharma_swarm/operator_bridge.py` provides durable queue/claim/recover/respond semantics in SQLite (`operator_bridge_tasks`) at lines 51-79, with enqueue/claim/respond methods at lines 347-440, 487-571, and 820-958.
- Runtime spine: `dharma_swarm/runtime_state.py` provides a richer single-host runtime DB with sessions, task claims, delegation runs, workspace leases, artifacts, memory facts, operator actions, and session events at lines 30-220.
- Local A2A: `dharma_swarm/a2a/*` implements agent cards, an in-memory local A2A server, local client delegation, and a Trishula bridge. It is explicitly not yet remote HTTP.
- API/dashboard: `api/main.py` wires a FastAPI app with health, agents, commands/tasks, telemetry, routing, ontology, lineage, stigmergy, verify, hypernodes, and chat routers at lines 248-285.

What already exists for remote / cross-VPS coordination:

- File-based Trishula bridge: `dharma_swarm/trishula_bridge.py` reads `~/trishula/inbox` and turns messages into `Task` objects; it does not insert them into the task board itself.
- A2A-to-Trishula compatibility: `dharma_swarm/a2a/a2a_bridge.py` converts Trishula JSON messages into A2A tasks and writes completed A2A results back to `~/trishula/outbox`.
- Roaming mailbox bootstrap: `dharma_swarm/roaming_mailbox.py`, `roaming_poller.py`, `roaming_operator_bridge.py`, and `roaming_dispatch_daemon.py` implement file/git mailbox task dispatch and response collection.
- VPS knowledge exists as data/docs: `dharma_swarm/ontology.py` names AGNI at `157.245.193.15` and RUSHABDEV at `167.172.95.184` at lines 2073-2087. `scripts/sync_jikoku.sh` rsyncs Jikoku logs from SSH aliases `agni` and `rushabdev` at lines 17-25.
- Planning docs are explicit that the current remote layer is bootstrap, not a full distributed control plane: `docs/plans/2026-03-26-roaming-control-plane-spec.md` lines 52-74 and 94-105.

What is missing for a real fleet control plane:

- Canonical central schema for nodes, workers, node capabilities, task events, task artifacts, approvals, repo locks, node heartbeats, credentials references, and policy decisions tied together by `task_id`, `node_id`, `worker_id`, and `correlation_id`.
- HTTP node gateway with per-node identity, heartbeats, task accept/status/events, artifact upload, and cancellation.
- A2A HTTP/SSE facade. Current A2A server is in-memory and local only.
- Auth model for remote node gateways. API has optional dashboard Bearer auth, but no node identity, no per-task scoped tokens, no mTLS/Tailscale/WireGuard enforcement, and no remote gateway policy boundary.
- Worker adapter interface for Codex CLI, Claude Code, OpenClaw, Hermes, shell, and MCP tools. There are provider adapters and interop worker prototypes, but no fleet task adapter contract.
- Prometheus/OpenTelemetry/Loki/Grafana integration. Current telemetry is SQLite/JSONL/Langfuse/Jikoku oriented.

Highest-leverage next 3 implementation steps:

1. Add a central durable fleet state schema beside the existing runtime DB: `fleet_tasks`, `fleet_task_events`, `fleet_task_artifacts`, `fleet_nodes`, `fleet_workers`, `fleet_node_heartbeats`, `fleet_approvals`, `fleet_repo_locks`.
2. Add a private, auth-gated FastAPI node gateway router for node registration/heartbeat/capabilities and task claim/status/event append. Keep it local/dev-safe first.
3. Add a minimal `AgentAdapter`/`WorkerAdapter` base and one dry-run/shell adapter, then map Codex/Claude/OpenClaw/Hermes to that contract later.

Architecture classification: the repo is closest to a local message bus plus local A2A protocol plus file-based remote sync plus API/dashboard app. It is not yet a true distributed control plane.

Safest near-term architecture: central Dharma API remains the private source of truth; Trishula/roaming mailbox remain fallback; add durable fleet tables and a private node-gateway router before adding any live multi-machine execution.

## 1. Repo Map

| Path | Purpose | Key classes/functions | Relevance to fleet control plane | Notes |
|---|---|---|---|---|
| `dharma_swarm/a2a/agent_card.py` | Agent capability cards persisted to disk | `AgentCapability` L41-L63, `AgentCard` L66-L180, `CardRegistry` L250-L413 | Agent/node capability discovery seed | Cards persist under `~/.dharma/a2a/cards` by default; auth type exists but is descriptive only. |
| `dharma_swarm/a2a/a2a_server.py` | Local in-process A2A task server | `A2ATaskStatus` L33-L41, `A2ATask` L86-L118, `A2AServer` L130-L302 | Local task envelope and lifecycle | `_tasks` is in-memory L156-L158; remote HTTP is future milestone L8-L9. |
| `dharma_swarm/a2a/a2a_client.py` | Local delegation client | `DelegationResult` L40-L69, `A2AClient` L72-L232 | Capability-based delegation | Uses local `A2AServer`; remote AGNI/RUSHABDEV HTTP is future milestone L7-L8. |
| `dharma_swarm/a2a/a2a_bridge.py` | Trishula/A2A compatibility | `A2ABridge` L45-L288 | Migration path from file messages to A2A | Reads inbox, writes outbox, emits SignalBus events. |
| `dharma_swarm/message_bus.py` | SQLite async pub/sub and event rail | `MessageBus` L111-L675 | Good local durable bus | Has `heartbeats`, `artifacts`, `events`; not cross-host by itself. |
| `dharma_swarm/signal_bus.py` | In-process event bus | `SignalBus` L47-L180 | Local low-latency signals | Non-durable, process-local. |
| `dharma_swarm/handoff.py` | JSONL handoff protocol | `Artifact`, `Handoff`, `HandoffProtocol` L87-L363 | Typed handoffs and artifacts | Durable JSONL, not fleet task state. |
| `dharma_swarm/trishula_bridge.py` | File inbox to swarm tasks | `TrishulaBridge` L102-L347 | Legacy/fallback remote ingress | Creates `Task` objects at L203-L224; caller must persist/dispatch. |
| `dharma_swarm/roaming_mailbox.py` | Git/file mailbox | `MailboxTask` L39-L74, `RoamingMailbox` L91-L208 | Bootstrap remote transport | Plain JSON files under tasks/responses/receipts. |
| `dharma_swarm/roaming_poller.py` | Remote-side mailbox worker | `GitMailboxSync` L37-L68, `RoamingPoller` L70-L166 | Remote pull/claim/respond loop | Runs arbitrary responder command via subprocess L126-L132. |
| `dharma_swarm/roaming_operator_bridge.py` | OperatorBridge to mailbox adapter | `RoamingOperatorBridge` L28-L143 | Connects real bridge tasks to roaming files | Keeps mailbox as transport, not second task system. |
| `dharma_swarm/roaming_dispatch_daemon.py` | Local dispatcher/collector | `RoamingDispatchDaemon` L69-L143 | Local loop for roaming work | Uses git sync optionally; no live HTTP. |
| `dharma_swarm/roaming_onboarding.py` | Roaming agent registration | `RoamingAgentRegistration` L80-L97, `onboard_roaming_agent` L132-L277 | External identity/card bootstrap | Writes dock JSON, A2A card, telemetry identity; auth_type is `none` L190-L197. |
| `dharma_swarm/operator_bridge.py` | Canonical durable operator queue | `OperatorBridgeTask` L140-L182, `OperatorBridge` L226-L958 | Strongest task lifecycle implementation | Has claim timeout/recovery/ack/artifact hooks; not node-aware. |
| `dharma_swarm/runtime_state.py` | Canonical SQLite runtime state | DDL L30-L220, `RuntimeStateStore` L718+ | Best base for central DB | Single-host; lacks nodes/workers/remote auth. |
| `dharma_swarm/telemetry_plane.py` | SQLite telemetry/business state | DDL L24-L261 | Routing/policy/economic telemetry | Has `policy_decisions` L166-L181, no Prometheus exporter. |
| `api/main.py` | FastAPI app bootstrap/auth/CORS | `BearerAuthMiddleware` L168-L211, router registration L248-L285 | Existing control-plane API surface | `api/routers/interop.py` exists but is not registered. |
| `api/routers/commands.py` | Task create/list/dispatch API | `/api/commands/task` L27, `/api/commands/tasks` L56 | Dashboard task surface | Does not expose task detail/status/events/artifacts. |
| `api/routers/health.py` | Health/overview API | `/api/health` L28, `/api/health/anomalies` L66 | Local health | Not node health. |
| `api/routers/agents.py` | Agent list/spawn/stop/sync/chat | endpoints L296-L582 | Local agent management | WebSocket `/ws/agents`; no remote node model. |
| `api/routers/telemetry.py` | Telemetry API | prefix `/api/telemetry` L14, endpoints L94-L239 | Runtime telemetry dashboard | SQLite telemetry projection. |
| `api/routers/routing.py` | Routing manifest | `/api/routing/manifest` L155 | Provider/adapter catalog view | Reads terminal adapters; not worker dispatch. |
| `api/routers/interop.py` | Untracked interop API | endpoints L54-L142 | Prototype external-agent desk | File-backed; not registered in `api/main.py`. |
| `dashboard/src/lib/api.ts` | Next.js API helpers | task helpers L178-L200, health L204-L210 | Dashboard client surface | No individual task endpoint noted L188-L191. |
| `dashboard/src/hooks/useInterop.ts` | Untracked interop hook | EventSource to `/api/interop/stream` L27-L50 | Prototype live interop UI | Imports `fetchInteropStatus`/`enqueueInteropTask`, but those exports were not found in `dashboard/src/lib/api.ts`. |
| `scripts/sync_jikoku.sh` | Pulls remote Jikoku logs | rsync AGNI/RUSHABDEV L17-L25 | Cross-VPS observability fallback | Pull-only; no heartbeat/task dispatch. |
| `Dockerfile`, `docker-compose.yml` | Ginko/Swarmlens deployment | Docker healthcheck L29-L30; compose healthcheck L17-L21 | Deployment evidence | Targets `swarmlens_app:app` on port 8080, not fleet node gateway. |
| `docs/plans/2026-03-26-roaming-control-plane-spec.md` | Roaming architecture plan | current phase L52-L74, hybrid plan L158-L177 | Best planning doc for target | Says mailbox is correct bootstrap, not final nervous system. |
| `tests/test_a2a.py` | A2A tests | server tests L337-L447, client L454-L548, bridge L555-L842 | Coverage for current A2A behavior | Confirms local/direct semantics. |
| `tests/test_message_bus.py` | Message bus tests | send/reply/pubsub/heartbeat/event retry | Local bus coverage | No cross-host coverage. |
| `tests/test_roaming_*` | Roaming mailbox/poller/bridge/daemon tests | see files | Remote bootstrap coverage | File/git transport tests, not HTTP/node gateway. |
| `tests/test_interop_router.py` | Untracked interop tests | router lifecycle L87-L137 | Prototype external-agent API coverage | Router tested standalone, not via `api/main.py`. |

Missing requested file: `dharma_swarm/external_agent_registration.py` does not exist in this checkout. Closest implemented equivalent is `dharma_swarm/roaming_onboarding.py`.

## 2. Existing A2A Layer

Current AgentCard model:

- `AgentCapability` has `name`, `description`, `input_modes`, `output_modes` and substring matching in `matches()` at `dharma_swarm/a2a/agent_card.py` L41-L63.
- `AgentCard` fields are `name`, `description`, `capabilities`, `endpoint`, `auth_type`, `role`, `model`, `provider`, `status`, `version`, timestamps, and `metadata` at L66-L101.
- `endpoint` defaults to `local://`; docstring says remote agents use HTTP URL at L74-L77.
- `auth_type` defaults to `none` L78-L79; there is no enforcement in this layer.

Where cards are stored:

- Default cards directory is `~/.dharma/a2a/cards` via `_DEFAULT_CARDS_DIR` at `agent_card.py` L28-L29.
- `CardRegistry._card_path()` sanitizes card names and maps to JSON files at L269-L273.
- `CardRegistry._load_from_disk()` reads `*.json` into memory at L275-L285; `_persist_card()` writes JSON at L287-L296.

What CardRegistry does:

- `register()` persists and stores cards L300-L308.
- `unregister()` deletes from memory and disk L310-L319.
- `discover()` filters by capability L337-L352.
- `discover_by_role()` filters by role L354-L367.
- `discover_available()` filters status `idle` or `available` L369-L374.
- `register_from_agent_registry()` converts existing agent registry dicts to cards L378-L402.
- `sync_status()` updates card status L404-L413.

What A2AServer does:

- Defines statuses `submitted`, `working`, `input-required`, `completed`, `failed`, `cancelled` at `a2a_server.py` L33-L41.
- Defines `A2ATask` with id/from/to/status/messages/capability/dharma_task_id/result/error/metadata at L86-L118.
- `A2AServer` stores `_tasks` in an in-memory dict L156-L158.
- `register_handler()` maps capabilities to sync handlers L163-L178.
- `submit()` stores task then immediately dispatches it L186-L210.
- `_dispatch()` marks working, calls a handler/default handler, and marks completed unless handler changed status L212-L241.
- `cancel()` only cancels submitted/working/input-required tasks L252-L265.

Task lifecycle:

- A2A lifecycle is submitted -> working -> completed/failed/cancelled, with optional input-required enum but no async waiting implementation.
- Tests cover submit, handler failure, default handler, get status, cancel, list, and summary in `tests/test_a2a.py` L337-L447.

Where the task store is:

- `A2AServer._tasks` in memory only at `a2a_server.py` L156-L158.
- There is no A2A SQLite/Postgres task store.

Is the task store durable or in-memory:

- In-memory only. The module docstring explicitly says “In-memory A2A task store layered on task model” at `a2a_server.py` L11-L13.

What A2AClient does:

- Discovers agents via `CardRegistry` L96-L117.
- `delegate()` finds available agents by capability and picks the first L121-L162.
- `delegate_to()` submits to the local `A2AServer` L164-L214.
- `get_task_status()` and `cancel_task()` are local server calls L216-L232.

Does it support remote HTTP yet:

- No. `a2a_client.py` says remote AGNI/RUSHABDEV HTTP is a future milestone at L7-L8. `a2a_server.py` says the same at L8-L9. `a2a/__init__.py` says HTTP transport for inter-VPS communication is future milestone at L14.

What A2ABridge does:

- Converts Trishula JSON messages into `A2ATask` at `a2a_bridge.py` L75-L133.
- Scans a Trishula inbox, skips `type == ack`, submits tasks to `A2AServer`, and emits `A2A_TASK_SUBMITTED` at L135-L181.
- Converts A2A task results back into Trishula response messages at L185-L229.
- Writes results to Trishula outbox if the outbox exists at L231-L257.
- Emits SignalBus events via `_emit_signal()` at L261-L268.

How it connects to SignalBus or Trishula:

- Trishula inbox defaults to `~/trishula/inbox` L151.
- Trishula outbox defaults to `~/trishula/outbox` L69-L70.
- Signal constants are `A2A_TASK_SUBMITTED`, `A2A_TASK_COMPLETED`, and `A2A_TASK_FAILED` L39-L42.
- Tests use a fake signal bus and validate submitted/completed/failed events in `tests/test_a2a.py` L576-L584 and L641-L721.

Exact TODOs/comments about remote HTTP:

- `dharma_swarm/a2a/__init__.py` L13-L14: local-only for now; HTTP transport is future milestone.
- `dharma_swarm/a2a/a2a_server.py` L7-L9: direct calls for local agents, HTTP endpoint for AGNI/RUSHABDEV future milestone.
- `dharma_swarm/a2a/a2a_client.py` L7-L8: remote AGNI/RUSHABDEV HTTP delegation future milestone.
- `dharma_swarm/a2a/a2a_bridge.py` L191-L192: Trishula outbound for remote agents on AGNI/RUSHABDEV that do not speak A2A yet.

What would need to change for HTTP/SSE remote transport:

- Persist A2A tasks in the central task/event store instead of `A2AServer._tasks`.
- Add FastAPI router serving `/.well-known/agent-card.json`, `POST /a2a/tasks`, `GET /a2a/tasks/{id}`, `POST /a2a/tasks/{id}/cancel`, and `GET /a2a/tasks/{id}/events` as SSE.
- Add auth: per-node identity and per-task scoped token, not `auth_type="none"`.
- Convert handler execution from sync direct function calls to durable dispatch through worker adapters or node gateway.
- Add event append/replay so SSE can resume using `Last-Event-ID`.
- Include correlation fields: `task_id`, `node_id`, `worker_id`, `correlation_id`, `trace_id`.

## 3. Existing API / Dashboard Surface

FastAPI app:

- `api/main.py` creates the app at L216-L221.
- Bearer auth middleware is added at L225. If `DASHBOARD_API_KEY` is absent, all `/api/*` routes are open in dev mode at L60-L67 and L176-L181.
- Public routes are defined at L151-L160.
- CORS origins are read from `DASHBOARD_CORS_ORIGINS`, defaulting to localhost ports 3000/3001/8420 at L227-L243.
- Routers registered at L248-L285 do not include `api.routers.interop`.

Endpoint inventory:

| Method | Path | Router/file | Handler | Auth? | DB/state touched | WebSocket/SSE? | Notes |
|---|---|---|---|---|---|---|---|
| GET | `/` | `api/main.py:L290` | `root` | No | none | No | Metadata only. |
| GET | `/api/health` | `api/routers/health.py:L28` | `health` | Optional Bearer | monitor/swarm/trace store | No | Local app health, not node health. |
| GET | `/api/health/anomalies` | `health.py:L66` | `anomalies` | Optional Bearer | monitor | No | Local anomaly view. |
| GET | `/api/overview` | `health.py:L83` | `overview` | Optional Bearer | swarm/evolution/stigmergy | No | Dashboard summary. |
| GET | `/api/agents` | `agents.py:L296` | `list_agents` | Optional Bearer | swarm + ontology identity | No | Local agents. |
| POST | `/api/agents/spawn` | `agents.py:L330` | `spawn_agent` | Optional Bearer | swarm | No | Local spawn. |
| POST | `/api/agents/{id}/stop` | `agents.py:L361` | `stop_agent` | Optional Bearer | swarm | No | Local stop. |
| POST | `/api/agents/sync` | `agents.py:L373` | `sync_agents` | Optional Bearer | swarm | No | Syncs local registry. |
| POST | `/api/agents/{id}/chat` | `agents.py:L404` | `agent_chat` | Optional Bearer | chat/session state | SSE | Agent chat stream. |
| WS | `/api/ws/agents` | `agents.py:L582` | `agents_ws` | Optional token query | swarm | WebSocket | Periodic local agent updates. |
| POST | `/api/commands/task` | `commands.py:L27` | `create_task` | Optional Bearer | `swarm.create_task` | No | Creates local TaskBoard task. |
| GET | `/api/commands/tasks` | `commands.py:L56` | `list_tasks` | Optional Bearer | `swarm.list_tasks` | No | No per-task endpoint. |
| POST | `/api/commands/dispatch` | `commands.py:L101` | `dispatch_next` | Optional Bearer | orchestrator/swarm | No | Local dispatch. |
| GET | `/api/telemetry/*` | `telemetry.py:L94-L239` | telemetry handlers | Optional Bearer | `TelemetryPlaneStore`, `RuntimeStateStore` | No | SQLite telemetry views. |
| GET | `/api/routing/manifest` | `routing.py:L155` | `get_routing_manifest` | Optional Bearer | terminal adapters/model policy | No | Provider catalog/route manifest. |
| POST | `/api/chat` | `chat.py:L1219` | `chat_stream` | Optional Bearer | chat runtime | SSE | Agentic chat with tools. |
| WS | `/ws/chat/session/{session_id}` | `chat.py:L1353` | chat WS | Token query | in-memory chat events | WebSocket | Not under `/api`. |
| GET/POST | `/api/interop/*` | `interop.py:L54-L142` | interop handlers | Would be optional Bearer if registered | file-backed `AgentInteropStore` | SSE at L74 | Untracked and not registered in `api/main.py`. |
| GET | `/graphql/*` | `graphql_router.py:L230-L378` | GraphQL-like REST | Not `/api`; middleware only gates `/api` | ontology/stigmergy | No | Auth gap if exposed. |
| GET | `/api/verify/*` | `verify.py:L104-L180` | verify handlers | health public; others optional Bearer | verify subsystem | No | Webhook is public route. |

What API already exists:

- Agents: yes, local only (`api/routers/agents.py`).
- Telemetry: yes, SQLite telemetry (`api/routers/telemetry.py`).
- Health: yes, local app health (`api/routers/health.py`).
- Ontology/lineage/stigmergy: yes, read-oriented plus stigmergy promote.
- Tasks: create/list/dispatch only through commands router.
- Dashboard state: yes through overview, dashboard_new, telemetry, routing, chat.

What does not exist:

- No canonical node/agent health endpoint for remote machines.
- No task lifecycle API with per-task events/artifacts/leases.
- No artifact upload/download API tied to tasks.
- No approval action API for fleet task approval.
- No `/metrics` endpoint for Prometheus.
- No registered A2A HTTP router.

Cleanest place to add node gateway/A2A HTTP router:

- Add `api/routers/node_gateway.py` with prefix `/api/nodes` for central control-plane operations.
- Add `api/routers/a2a_http.py` for `/.well-known/agent-card.json` and `/api/a2a/*` or standards-compatible paths.
- Register both in `api/main.py:_register_routers()` at lines 248-285.
- Reuse `api/models.py` style `ApiResponse` and add focused Pydantic request/response models.

## 4. Local Messaging / Events

| System | Scope | Durable? | Cross-host? | Real-time? | Good for | Not good for |
|---|---:|---:|---:|---:|---|---|
| `MessageBus` | Local process(es) sharing SQLite | Yes | No, unless DB is shared unsafely | Poll/async | Local inbox/pubsub/heartbeats/events/artifacts | Fleet-wide queue without node model or network transport |
| `SignalBus` | In-process only | No | No | Yes inside process | Loop-to-loop hints | Any durable task/event log |
| `HandoffProtocol` | Local JSONL | Yes | File-sync possible but not live | No | Human-readable agent handoffs and artifacts | Canonical fleet task state |
| `TrishulaBridge` | Local files under `~/trishula` | File durable | Via external sync | No | Fallback remote ingress | Low-latency or authenticated fleet control |
| `RoamingMailbox` | File/git mailbox | File durable | Yes via git | No | Bootstrap remote task exchange | High-volume, leases, streaming logs |
| `OperatorBridge` | Local SQLite + ledgers + MessageBus | Yes | No | Poll/event bus local | Canonical local bridge lifecycle | Remote node identity/transport |
| `RuntimeStateStore` | SQLite runtime DB | Yes | No | No | Structured source of truth for sessions/runs/artifacts/events | Direct remote dispatch without API |
| `A2AServer` | In-memory local | No | No | Direct call | Local delegation semantics | Durable/fleet A2A |

Can these become the central task/event log:

- Best reuse: `RuntimeStateStore` and `OperatorBridge` patterns. They already have claims, runs, leases, artifacts, events, recovery, and acknowledgement.
- Do not make `SignalBus` central.
- Do not make `A2AServer._tasks` central.
- Keep `MessageBus.events` as a useful local event rail, but a fleet event log should be explicitly typed and tied to nodes/workers/tasks.
- Keep `RoamingMailbox`/Trishula as fallback slow lane.

## 5. Remote / Cross-VPS Capabilities

Known remote nodes:

- AGNI VPS: `dharma_swarm/ontology.py` L2073-L2079, canonical path `/remote/157.245.193.15`, description “OpenClaw, 56 skills, 8 agents”.
- RUSHABDEV VPS: `ontology.py` L2081-L2087, canonical path `/remote/167.172.95.184`.
- Trishula mesh: `ontology.py` L2088-L2095, “Three-agent comms: Mac + 2 VPSes”.
- `scripts/sync_jikoku.sh` uses SSH aliases `agni` and `rushabdev` at lines 17-25.

How Dharma currently reads remote state:

- `dharma_swarm/context.py:read_agni_state()` reads synced files `~/agni-workspace/WORKING.md`, `HEARTBEAT.md`, and `PRIORITIES.md` at lines 523-539.
- `read_trishula_inbox()` reads `~/trishula/inbox/*.md` at lines 542-560.
- `read_ops()` composes AGNI, Trishula, memory, manifest, and shipped artifacts at lines 785-798.
- `scripts/sync_jikoku.sh` pulls `~/.dharma/jikoku/JIKOKU_LOG.jsonl` from VPSes to local subdirs at lines 14-25.

How remote sync currently works:

- Trishula inbox/outbox files.
- Roaming mailbox JSON files under `roaming_mailbox/tasks`, `responses`, `receipts`.
- Optional git branch sync in `roaming_poller.py:GitMailboxSync` L37-L68 and `roaming_dispatch_daemon.py:MailboxRepoSync` L30-L67.
- rsync for Jikoku logs in `scripts/sync_jikoku.sh`.

Live remote communication:

- No evidence of a live Dharma node gateway.
- No registered HTTP remote task dispatch.
- A2A remote HTTP is explicitly future work.
- Roaming poller can run remote commands locally on the remote host, but transport is git/file sync.

Health/heartbeat:

- `MessageBus.heartbeat()` exists for local agent status.
- Roaming onboarding writes `last_seen_at` and telemetry identity, but there is no remote node heartbeat endpoint.
- Interop prototype has worker heartbeat files via `AgentInteropStore.heartbeat_worker()` L206-L242 and `/api/interop/heartbeat` L119-L128, but the router is not registered.
- Jikoku sync pulls logs, not health.

Fragile parts:

- File and git sync have conflicts, latency, stale state, no authenticated node identity, no revocation, no streaming logs, and weak heartbeat.
- Remote responder commands are subprocess-based (`roaming_poller.py` L126-L132; `operator_core/interop_worker.py` L79-L86), so command scoping and secret isolation need a stronger policy boundary before exposing remote gateways.

Keep as fallback:

- Trishula inbox/outbox for low-trust/manual and NAT-hostile environments.
- Roaming mailbox for mobile/phone/harnesses without stable server transport.
- Jikoku rsync as fallback telemetry ingestion.

## 6. Database / State Inventory

Observed repo-local DB files:

| DB/store | Location | Type | Tables/models | Writers | Readers | Purpose |
|---|---|---|---|---|---|---|
| Task board | `.dharma/db/tasks.db`; runtime path from `swarm.py` L607 | SQLite | `tasks`, `task_dependencies` | `TaskBoard` | Swarm/API | Local tasks. |
| Message bus | `.dharma/db/messages.db`; `swarm.py` L610 | SQLite | `messages`, `heartbeats`, `subscriptions`, `artifacts`, `events` | `MessageBus`, `OperatorBridge` | API/orchestrator/tests | Local messaging/event rail. |
| Runtime state | `.dharma/state/runtime.db` and `.dharma/db/runtime.db`; `swarm.py` L605/L618 | SQLite | sessions, task_claims, delegation_runs, workspace_leases, artifact_records, session_events, etc. | `RuntimeStateStore`, `OperatorBridge`, telemetry projector | telemetry/API/tests | Structured single-host runtime state. |
| Telemetry plane | same runtime DB by default | SQLite | agent_identity, routing_decisions, policy_decisions, external_outcomes, etc. | `TelemetryPlaneStore`, projector, routing | `/api/telemetry` | Operational/economic/routing telemetry. |
| Operator bridge tasks | usually message bus DB | SQLite | `operator_bridge_tasks` | `OperatorBridge` | bridge/roaming/tests | Durable local work queue. |
| A2A cards | `~/.dharma/a2a/cards/*.json` | JSON files | `AgentCard` | `CardRegistry`, onboarding, interop | A2A client/interop | Capabilities/discovery. |
| Handoffs | `~/.dharma/handoffs.jsonl` | JSONL | `Handoff`, `Artifact` | `HandoffProtocol` | local agents | Structured handoff history. |
| Roaming mailbox | `roaming_mailbox/*` or `~/.dharma/agent_interop/mailbox` | JSON files | `MailboxTask`, `MailboxResponse` | mailbox/poller/interop | poller/daemon/dashboard prototype | Slow remote task transport. |
| Interop store | `~/.dharma/agent_interop` | JSONL/files | workers, locks, events, prompts | `AgentInteropStore` | interop router/hook | Prototype external-agent desk. |
| Ontology | `.dharma/ontology.db` | SQLite | ontology registry | ontology runtime | API/ontology | Concept/object registry. |
| Memory plane | `.dharma/db/memory_plane.db` | SQLite | event memory/index | EventMemoryStore | context/retrieval | Semantic/event memory. |

Current equivalents vs missing fleet fields:

| Table/model | Fields | Used by | Missing fields for fleet control |
|---|---|---|---|
| `tasks` in `task_board.py` | id,title,description,status,priority,assigned_to,created_by,timestamps,result,metadata | Swarm commands/orchestrator | node_id, worker_id, lease_id, parent_task_id, approval_id, artifact summary, correlation_id, retry policy. |
| `operator_bridge_tasks` | id,sender,task,scope,output,constraints,payload,status,claim timeout,claimed_by,response,metadata | OperatorBridge/roaming | node_id, worker_id, adapter, repo, branch, lease token, streaming event cursor, artifact upload status. |
| `message_bus.heartbeats` | agent_id,last_seen,status,metadata | local agent status | node_id, worker_id, capabilities, version, private address, auth identity, resource stats. |
| `message_bus.events` | event_id,event_type,task_id,agent_id,source_pid,occurred_at,consumed_at,payload | local event rail | node_id, worker_id, severity, sequence, correlation_id, trace_id, durable replay cursor. |
| `runtime_state.task_claims` | claim_id,task_id,session_id,agent_id,status,claimed_at,acked_at,heartbeat_at,stale_after,retry_count | runtime/bridge | node_id, worker_id, lease token, adapter, failure class, cancel status. |
| `runtime_state.delegation_runs` | run_id,task_id,assigned_to,status,assigned_by,current_artifact_id | runtime/bridge | node_id, worker_id, transport, remote task id, queue backend. |
| `runtime_state.workspace_leases` | lease_id,zone_path,holder_run_id,mode,base_hash,times | runtime/artifacts | repo_id, branch, worktree, conflict policy, node_id. |
| `runtime_state.artifact_records` | artifact_id,session_id,task_id,run_id,kind,manifest_path,payload_path,checksum | runtime/artifacts | node_id, worker_id, content type, size, storage backend, upload status. |
| `telemetry_plane.policy_decisions` | decision_id,session_id,task_id,run_id,policy_name,decision,reason | telemetry/API | actor/node, approval linkage, enforcement result. |

Minimal schemas to add:

- `fleet_nodes(node_id PK, hostname, display_name, base_url, transport, status, last_heartbeat_at, version, trust_level, capabilities_json, metadata_json, created_at, updated_at)`
- `fleet_workers(worker_id PK, node_id FK, adapter, label, status, current_task_id, capabilities_json, last_heartbeat_at, metadata_json)`
- `fleet_tasks(task_id PK, title, body, status, priority, requested_capabilities_json, assigned_node_id, assigned_worker_id, lease_id, approval_state, repo, branch, metadata_json, created_at, updated_at)`
- `fleet_task_events(event_id PK, task_id FK, node_id, worker_id, seq, event_type, status, severity, message, payload_json, correlation_id, trace_id, created_at)`
- `fleet_task_artifacts(artifact_id PK, task_id FK, node_id, worker_id, kind, uri, content_type, size_bytes, checksum, metadata_json, created_at)`
- `fleet_approvals(approval_id PK, task_id FK, policy_name, requested_by, approved_by, decision, reason, expires_at, created_at, decided_at)`
- `fleet_repo_locks(lock_id PK, repo, branch, path_scope, holder_task_id, holder_node_id, mode, base_ref, expires_at, released_at, metadata_json)`
- `fleet_node_tokens(token_id PK, node_id FK, token_hash, scopes_json, expires_at, revoked_at, created_at)` or store only credential refs if a secret manager is used.

## 7. Security / Authority / Approvals

Existing protections:

- Dashboard API Bearer auth: `api/main.py` L60-L67 logs dev-open mode if `DASHBOARD_API_KEY` missing; middleware enforces Bearer for `/api/*` when set at L168-L211.
- CORS allowlist: `api/main.py` L227-L243.
- API key env registry: `dharma_swarm/api_keys.py` L13-L43 defines credential env var names; it does not store values.
- Shell tool gate: `api/chat_tools.py` calls `telos_gates.check_action()` before shell execution L450-L459 and applies regex blocklist L431-L465.
- Local sandbox: `dharma_swarm/sandbox.py` rejects destructive command patterns L20-L30 and executes with timeouts L90-L120.
- Governance filter: `dharma_swarm/operator_core/permissions.py` redacts raw/thinking events and marks gated tools requiring confirmation L23-L37 and L60-L80.
- Prompt injection scanner: `dharma_swarm/injection_scanner.py` detects prompt injection, secret exfiltration, hidden unicode, and HTML concealment L24-L61 and blocks content L98-L113.
- Decision router escalates privileged actions without consent at `dharma_swarm/decision_router.py` L107-L124.
- Roaming onboarding sets `autonomy_policy.requires_approval=True` in dock JSON at `roaming_onboarding.py` L174-L177.

Security gaps:

- No remote node authentication model.
- No per-node identity or token table.
- No mTLS/Tailscale/WireGuard enforcement in code.
- A2A cards use `auth_type` but no enforcement.
- Roaming onboarding writes `auth_type="none"` for cards at `roaming_onboarding.py` L190-L197.
- `dharma_swarm/codex_cli.py` appends `--dangerously-bypass-approvals-and-sandbox` at L17-L22 for DGC-owned Codex launches. That may be intentional for local trusted operation, but it is unsafe as a remote default.
- `api/routers/graphql_router.py` is mounted at `/graphql` and the middleware gates only `/api` paths (`api/main.py` L190-L193), so those endpoints are not covered by Bearer auth unless another layer protects them.
- `api/routers/interop.py` has no router-specific auth and is not registered. If registered, it would inherit `/api` Bearer middleware but still lacks per-worker identity/scopes.

Biggest security gap for remote node gateways:

Remote nodes would accept task execution and stream logs/artifacts without a node identity, scoped token, approval policy, command sandbox, or audit trail tied to immutable task events. Do not expose public agent ports until this is fixed.

Proposed v1 security model:

- Private network only: Tailscale/WireGuard/VPC; no public node gateway ports.
- Per-node identity: generated `node_id`, token hash in central DB, rotation/revocation.
- Per-task scoped token: dispatch token can only append events/artifacts/status for one task.
- Approval gates: tasks with shell/deploy/credential/repo-write risk require approval row before lease creation.
- No secrets in logs: redact env values; store credential references, never raw secrets.
- Audit trail: every state transition writes `fleet_task_events` with actor, node, worker, policy decision, and correlation id.

## 8. Observability / Grafana Readiness

Existing telemetry/logging:

- `dharma_swarm/observability.py` has local JSONL trace spans and optional Langfuse. `TraceSpan` includes `trace_id` and `span_id` at L86-L100; local store writes `~/.dharma/traces/traces_YYYY-MM-DD.jsonl` at L114-L147.
- `dharma_swarm/jikoku_samaya.py` has `JikokuTracer` and JSONL spans; `scripts/sync_jikoku.sh` pulls VPS logs.
- `dharma_swarm/telemetry_plane.py` stores agent identity, routing decisions, policy decisions, interventions, economic events, external outcomes, and provider attempts in SQLite at L24-L261.
- `dharma_swarm/runtime_telemetry_projector.py` mirrors runtime sessions, claims, runs, actions, and events into telemetry at L44-L99.
- `api/routers/telemetry.py` exposes telemetry views but no Prometheus format.

Missing:

- No `/metrics` endpoint found.
- No Prometheus client usage found.
- No OpenTelemetry SDK wiring found.
- No Loki/Tempo config found.
- Logs/events do not consistently include `task_id`, `node_id`, `worker_id`, `adapter`, `correlation_id`, and `trace_id`.

Grafana additions:

- Add Prometheus endpoint under `/metrics`.
- Export gauges/counters from central fleet tables.
- Add structured JSON logs for node gateway and worker adapters.
- Add trace context fields to central task events.

Proposed metrics:

- `dharma_node_up`
- `dharma_node_last_heartbeat_timestamp`
- `dharma_node_cpu_percent`
- `dharma_worker_up`
- `dharma_worker_busy`
- `dharma_task_total`
- `dharma_task_duration_seconds`
- `dharma_task_failed_total`
- `dharma_approval_pending_total`
- `dharma_repo_lock_active`
- `dharma_artifact_uploaded_total`
- `dharma_llm_tokens_total`
- `dharma_llm_cost_usd_total`

Proposed log labels:

- `task_id`
- `node_id`
- `worker_id`
- `adapter`
- `repo`
- `branch`
- `status`
- `severity`
- `correlation_id`
- `trace_id`

## 9. Worker Adapter Readiness

Existing adapters/wrappers:

- Terminal provider adapter interface: `dharma_swarm/terminal_adapters/base.py` defines `ProviderAdapter.stream()`, `cancel()`, `close()` and capabilities at L13-L25 and L74-L96.
- Claude Code adapter: `dharma_swarm/terminal_adapters/claude.py` wraps Claude CLI subprocess/NDJSON at L71-L240.
- Codex adapter: `dharma_swarm/terminal_adapters/codex.py` wraps Codex CLI at L45-L240.
- Routing manifest instantiates `ClaudeAdapter`, `CodexAdapter`, `OpenRouterAdapter`, and `OllamaAdapter` in `api/routers/routing.py` L66-L89.
- Interop prototype adapters: `dharma_swarm/operator_core/interop.py` defines `DEFAULT_ADAPTERS` for `codex-cli`, `claude-code`, `hermes`, `openclaw`, MCP, etc. at L20-L32.
- Interop worker: `operator_core/interop_worker.py` claims file-backed tasks and runs a command template via `subprocess.run()` at L79-L86.
- Runtime governance adapter: `dharma_swarm/runtime_bridge.py` defines `RuntimeAdapter.normalize_action()` and `RuntimeBridge` registry/governance at L22-L58 and L88-L98.
- Gateway platform adapter: `dharma_swarm/gateway/base.py` defines messaging platform adapters, not task workers.

Current process-management utilities:

- `roaming_poller.py` and `interop_worker.py` run subprocess responder commands.
- `scripts/start_interop_workers_tmux.sh` and siblings exist untracked.
- Chat tool execution uses `asyncio.create_subprocess_exec` in `api/chat_tools.py` L470-L488.

Agent representation:

- `dharma_swarm/models.py` defines `AgentConfig`, `AgentState`, `ProviderType`, roles including `conductor` and `worker`.
- `roaming_onboarding.py` creates `living_agent.json` docks and telemetry identities.
- There is no single fleet `AgentAdapter` contract with `health`, `start_task`, `get_status`, `stream_events`, `cancel`, `collect_artifacts`.

Minimal adapter interface:

```python
class AgentAdapter:
    name: str
    capabilities: list[str]
    async def health(self) -> dict: ...
    async def start_task(self, task: dict) -> dict: ...
    async def get_status(self, task_id: str) -> dict: ...
    async def stream_events(self, task_id: str): ...
    async def cancel(self, task_id: str) -> dict: ...
    async def collect_artifacts(self, task_id: str) -> list[dict]: ...
```

Where it could live:

- New `dharma_swarm/fleet/adapters.py` or `dharma_swarm/node_gateway/adapters.py`.
- Reuse normalization ideas from `terminal_adapters/base.py`.
- Implement first with `DryRunAdapter` or `ShellAdapter`.
- Later wrap `CodexAdapter`, `ClaudeAdapter`, `operator_core/interop_worker.py`, OpenClaw, Hermes, and MCP.

## 10. Proposed Target Architecture From This Repo

Target shape:

```text
Dharma Dashboard
  -> Dharma Control Plane API
    -> central task/event/artifact DB
    -> Dharma Conductor Agent
    -> Node Registry
    -> Policy/Approval System
    -> Observability Exporters
      -> Dharma Node Gateway on each VPS/Mac
        -> CodexAdapter
        -> ClaudeCodeAdapter
        -> OpenClawAdapter
        -> HermesAdapter
        -> ShellAdapter
        -> MCPToolAdapter
```

| Target component | Existing file/module | Reuse level | Required changes | Risk |
|---|---|---|---|---|
| Dashboard | `dashboard/src/*` | mostly works | Add node/task event/artifact UI; fix untracked interop client exports | Medium |
| Control Plane API | `api/main.py`, routers | mostly works | Add node gateway and A2A HTTP routers; auth hardening | Medium |
| Central task DB | `task_board.py`, `operator_bridge.py`, `runtime_state.py` | partial | Add fleet tables and repository methods | Medium |
| Event log | `message_bus.events`, `runtime_state.session_events` | partial | Add ordered task event log with node/worker/trace labels | Medium |
| Artifact DB | `message_bus.artifacts`, `runtime_state.artifact_records` | partial | Add upload API and task artifact linkage | Medium |
| Node Registry | none; closest `roaming_onboarding.py` | partial | Add `fleet_nodes`, node tokens, capabilities, heartbeat | High |
| Policy/Approvals | `decision_router.py`, `provider_policy.py`, `telemetry_plane.policy_decisions`, `operator_core/permissions.py` | partial | Add enforceable approval rows and API actions | High |
| Worker adapters | `terminal_adapters/*`, `operator_core/interop_worker.py` | partial | Add `AgentAdapter` contract and task execution lifecycle | High |
| A2A local | `dharma_swarm/a2a/*` | mostly works | Persist tasks and expose HTTP/SSE | Medium |
| Remote fallback | `trishula_bridge.py`, `roaming_*` | already works as fallback | Keep, document, do not promote as live control plane | Low |
| Observability | `observability.py`, `jikoku_samaya.py`, `telemetry_plane.py` | partial | Add Prometheus metrics and structured node logs | Medium |
| Queue scaling | none; optional `temporalio` dependency in `pyproject.toml` L41-L46 | missing | Later NATS/Temporal integration behind repository interface | Medium |
| Deployment | `Dockerfile`, `docker-compose.yml` | replace/partial | Current Docker targets Ginko/Swarmlens, not node gateway | Medium |

## 11. Implementation Plan

PR 1 - central task/event/artifact schema

- Goal: Add durable canonical fleet state without remote execution.
- Files to add: `dharma_swarm/fleet/__init__.py`, `dharma_swarm/fleet/state.py`, `tests/test_fleet_state.py`.
- Files to modify: none or minimal `pyproject` packaging if needed.
- Schema changes: create `fleet_tasks`, `fleet_task_events`, `fleet_task_artifacts`.
- Tests: schema creation, task create/get/list, event append/list ordering, artifact record/list.
- Risks: duplicating `TaskBoard`; mitigate by naming this fleet schema v1 and not switching existing code yet.
- Acceptance: tests pass; no API behavior change.

PR 2 - node registry and heartbeat model

- Add `fleet_nodes`, `fleet_workers`, `fleet_node_heartbeats`.
- Add repository methods `register_node`, `heartbeat_node`, `upsert_worker`, `list_online_nodes`.
- Tests for stale/offline transitions.

PR 3 - node gateway router

- Add `api/routers/node_gateway.py`.
- Endpoints: `POST /api/nodes/register`, `POST /api/nodes/{node_id}/heartbeat`, `GET /api/nodes`, `GET /api/nodes/{node_id}`.
- Add required API key placeholder or reuse `DASHBOARD_API_KEY` only for dev.
- Register in `api/main.py`.

PR 4 - A2A HTTP facade

- Add `api/routers/a2a_http.py`.
- Serve `/.well-known/agent-card.json`, `POST /api/a2a/tasks`, `GET /api/a2a/tasks/{task_id}`, `GET /api/a2a/tasks/{task_id}/events`.
- Reuse `AgentCard` and `A2ATask` data shapes but persist to fleet store.

PR 5 - worker adapter interface

- Add `dharma_swarm/fleet/adapters.py`.
- Implement `DryRunAdapter` first, optionally `ShellAdapter` with strict allowlist.
- Tests for health/start/status/events/cancel/artifacts.

PR 6 - Grafana/Prometheus metrics

- Add `/metrics` endpoint.
- Add counters/gauges listed in section 8.
- Tests assert metric names appear.

PR 7 - remote node bootstrap

- Add docs/scripts for `dharma-node` on AGNI/RUSHABDEV/Mac.
- State private-network requirement.
- Keep Trishula/roaming fallback.

PR 8 - conductor routing

- Add simple router: match capability, online node, free worker, approval state, create lease, dispatch, monitor events/heartbeat.
- Tests cover no eligible node, approval required, stale lease recovery.

## 12. Files To Send To ChatGPT / Architect

1. `dharma_swarm/a2a/agent_card.py`
   Why it matters: capability discovery and card persistence.
   Key classes/functions: `AgentCapability`, `AgentCard`, `CardRegistry`.
   Important notes: cards persist to `~/.dharma/a2a/cards`; auth is descriptive.
   Line ranges: 41-180, 250-413.

2. `dharma_swarm/a2a/a2a_server.py`
   Why it matters: current A2A task lifecycle.
   Key classes/functions: `A2ATaskStatus`, `A2ATask`, `A2AServer`.
   Important notes: in-memory only; remote HTTP future milestone.
   Line ranges: 33-118, 130-302.

3. `dharma_swarm/a2a/a2a_client.py`
   Why it matters: current delegation behavior.
   Key classes/functions: `A2AClient.delegate`, `delegate_to`.
   Important notes: local server calls only.
   Line ranges: 72-232.

4. `dharma_swarm/a2a/a2a_bridge.py`
   Why it matters: bridge between Trishula files and A2A.
   Key classes/functions: `A2ABridge`.
   Important notes: outbox/inbox fallback for AGNI/RUSHABDEV.
   Line ranges: 45-288.

5. `dharma_swarm/message_bus.py`
   Why it matters: durable local message/event/artifact tables.
   Key classes/functions: `MessageBus`.
   Important notes: local SQLite, not cross-host.
   Line ranges: 30-83, 111-675.

6. `dharma_swarm/operator_bridge.py`
   Why it matters: strongest existing durable task lifecycle.
   Key classes/functions: `OperatorBridgeTask`, `OperatorBridge`.
   Important notes: queue/claim/recover/respond/ack/artifact semantics.
   Line ranges: 51-79, 226-958.

7. `dharma_swarm/runtime_state.py`
   Why it matters: existing canonical runtime DB.
   Key classes/functions: `RuntimeStateStore`, DDL blocks, dataclasses.
   Important notes: reuse schema style for fleet tables.
   Line ranges: 30-220, 327-473, 718 onward.

8. `dharma_swarm/telemetry_plane.py`
   Why it matters: policy/routing/economic telemetry.
   Key classes/functions: `TelemetryPlaneStore`, DDL.
   Important notes: includes `policy_decisions`; not Prometheus.
   Line ranges: 24-261.

9. `dharma_swarm/roaming_mailbox.py`
   Why it matters: current file/git remote task transport.
   Key classes/functions: `MailboxTask`, `MailboxResponse`, `RoamingMailbox`.
   Important notes: fallback, not final nervous system.
   Line ranges: 1-208.

10. `dharma_swarm/roaming_operator_bridge.py`
    Why it matters: bridges real OperatorBridge work into roaming files.
    Key classes/functions: `RoamingOperatorBridge`.
    Important notes: explicitly keeps mailbox as transport.
    Line ranges: 1-143.

11. `dharma_swarm/roaming_poller.py`
    Why it matters: remote-side polling pattern.
    Key classes/functions: `GitMailboxSync`, `RoamingPoller`.
    Important notes: subprocess responder and git sync.
    Line ranges: 37-166.

12. `dharma_swarm/roaming_onboarding.py`
    Why it matters: external/roaming agent registration.
    Key classes/functions: `RoamingAgentRegistration`, `onboard_roaming_agent`.
    Important notes: creates dock/card/telemetry identity; `auth_type="none"`.
    Line ranges: 80-97, 132-277.

13. `api/main.py`
    Why it matters: API auth, CORS, router registration.
    Key classes/functions: `BearerAuthMiddleware`, `_register_routers`.
    Important notes: interop router not registered; `/graphql` outside `/api` auth gate.
    Line ranges: 60-67, 151-211, 227-285.

14. `api/routers/commands.py`
    Why it matters: current task API.
    Key classes/functions: `create_task`, `list_tasks`, `dispatch_next`.
    Important notes: no task detail/events/artifacts.
    Line ranges: 17-116.

15. `api/routers/agents.py`
    Why it matters: current local agent API and WebSocket.
    Key classes/functions: list/spawn/stop/sync/chat/ws.
    Important notes: local agents, not remote nodes.
    Line ranges: 296-599.

16. `api/routers/telemetry.py`
    Why it matters: current telemetry API.
    Key classes/functions: `get_store`, telemetry endpoints.
    Important notes: projects runtime DB into telemetry on TTL.
    Line ranges: 14-85, 94-239.

17. `api/routers/interop.py`
    Why it matters: untracked prototype node/worker-ish API.
    Key classes/functions: interop status/tasks/events/workers/SSE/heartbeat.
    Important notes: file-backed and not registered.
    Line ranges: 16-142.

18. `dharma_swarm/operator_core/interop.py`
    Why it matters: untracked external-agent interop store.
    Key classes/functions: `AgentInteropStore`.
    Important notes: default adapters include Codex, Claude Code, Hermes, OpenClaw, MCP.
    Line ranges: 20-32, 65-353.

19. `dharma_swarm/operator_core/interop_worker.py`
    Why it matters: command-template worker loop.
    Key classes/functions: `_run_task`, `main`.
    Important notes: subprocess execution; use as prototype only.
    Line ranges: 14-153.

20. `dharma_swarm/terminal_adapters/base.py`
    Why it matters: existing provider adapter abstraction.
    Key classes/functions: `Capability`, `ProviderAdapter`.
    Important notes: stream/cancel/close shape can inform worker adapters.
    Line ranges: 13-25, 74-96.

21. `dharma_swarm/terminal_adapters/codex.py`
    Why it matters: Codex CLI subprocess adapter.
    Key classes/functions: `CodexAdapter`.
    Important notes: local provider stream, not fleet task adapter.
    Line ranges: 45-240.

22. `dharma_swarm/terminal_adapters/claude.py`
    Why it matters: Claude Code subprocess adapter.
    Key classes/functions: `ClaudeAdapter`.
    Important notes: local provider stream and auth-status handling.
    Line ranges: 71-240.

23. `dharma_swarm/decision_router.py`
    Why it matters: risk/escalation policy.
    Key classes/functions: `DecisionRouter`, `DecisionInput`.
    Important notes: privileged action escalation hook.
    Line ranges: 25-79, 97-179.

24. `docs/plans/2026-03-26-roaming-control-plane-spec.md`
    Why it matters: architecture intent.
    Key classes/functions: n/a.
    Important notes: says git mailbox is bootstrap, next phase is hybrid HTTP/A2A.
    Line ranges: 52-105, 158-231, 285-320.

25. `tests/test_a2a.py`, `tests/test_operator_bridge.py`, `tests/test_roaming_*`, `tests/test_interop_router.py`
    Why it matters: behavioral contract.
    Key classes/functions: current expected lifecycle tests.
    Important notes: use these to avoid breaking local behavior.
    Line ranges: see sections above.

## 13. Questions / Unknowns

- Where the Dharma hub should run in production is not determined from repo code.
- Whether Postgres is available is unknown; current code is SQLite-first.
- Whether AGNI/RUSHABDEV/Mac Minis are on Tailscale/WireGuard is unknown.
- Whether OpenClaw/Hermes are managed by systemd, tmux, Docker, or manual shells is unknown.
- Whether Codex/Claude CLIs have stable non-interactive modes across remote hosts is unknown.
- Whether the dashboard source here is the only production frontend is uncertain because interop frontend files are untracked and incomplete against `api.ts`.
- Whether production deploys are in scope for this control plane is unknown.
- Whether remote agents may access secrets is unknown.
- Whether remote nodes are trusted equally is unknown.
- Whether Grafana/Loki/Prometheus already exist outside the repo is unknown.
- Whether NATS JetStream or Temporal should be adopted soon is unknown; `temporalio` is only an optional dependency in `pyproject.toml`, and no NATS code was found.

## 14. Suggested Next Prompt For Implementation

```text
Implement PR 1 from docs/dharma_fleet_control_plane_audit.md safely.

Scope:
- Add a new durable fleet state module only.
- Do not change existing task dispatch behavior.
- Do not register new API routes yet.
- Do not touch secrets or environment values.

Add:
- dharma_swarm/fleet/__init__.py
- dharma_swarm/fleet/state.py
- tests/test_fleet_state.py

Implement:
- SQLite schema creation for fleet_tasks, fleet_task_events, fleet_task_artifacts.
- Dataclasses or Pydantic models for FleetTask, FleetTaskEvent, FleetTaskArtifact.
- FleetStateStore with init_db(), create_task(), get_task(), list_tasks(), update_task_status(), append_event(), list_events(), record_artifact(), list_artifacts().
- Use WAL, foreign_keys=ON, busy_timeout, JSON serialization helpers consistent with runtime_state.py.
- Include fields for task_id, status, priority, requested_capabilities_json, assigned_node_id, assigned_worker_id, correlation_id, trace_id, metadata_json, created_at, updated_at.
- Do not implement remote node dispatch in this PR.

Tests:
- Schema initializes idempotently.
- Task create/get/list works.
- Status update appends/does not require event only if you choose that behavior; be explicit.
- Event append/list preserves order and filters by task_id.
- Artifact record/list links to task_id.
- Metadata round-trips as dict.

Run:
- pytest -q tests/test_fleet_state.py
- python -m compileall dharma_swarm/fleet

Return:
- Files changed.
- Test results.
- Any deliberately deferred pieces for PR 2.
```
