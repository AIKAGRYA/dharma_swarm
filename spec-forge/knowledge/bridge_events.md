# Bridge Event Vocabulary — Ground Truth Inventory

**Scout 1 artifact for S1 features F-023..F-028.** Enumerated from CODE, not docs.

Sources (read in full, 2026-06-12):
- `/Users/dhyana/dharma_swarm/dharma_swarm/terminal_bridge.py` (2,268 lines — the stdio bridge)
- `/Users/dhyana/dharma_swarm/dharma_swarm/terminal_bridge_text.py` (pure renderers; shapes only)
- `/Users/dhyana/dharma_swarm/dharma_swarm/tui/engine/events.py` (canonical stream-event dataclasses, SCHEMA_VERSION=1)
- `/Users/dhyana/dharma_swarm/dharma_swarm/operator_core/{contracts,adapters,permission_payloads,routing_payloads,runtime_payloads,workspace_payloads,session_payloads,session_views}.py` (payload builders)
- `/Users/dhyana/dharma_helm_build/terminal/src/bridge.ts`, `types.ts`, `protocol.ts`, `app.tsx` (TS consumer)

Line numbers cited as `terminal_bridge.py:NNN` etc. refer to the files above as read on 2026-06-12.

---

## 0. Transport and envelope conventions

- **Transport**: NDJSON over the child process stdio. Python emits via `TerminalBridge._emit` (`terminal_bridge.py:893-895`): `json.dumps(payload, default=_json_default) + "\n"`. `_json_default` (`:76-81`) converts dataclasses via `asdict`, sets to sorted lists, and **anything else to `str(value)`** — so unexpected types silently become strings.
- **TS side** (`bridge.ts:50-65`): readline per line, `JSON.parse`, on parse failure synthesizes `{type:"bridge.error", code:"invalid_bridge_json", message:<raw line>}`. `BridgeEvent` is currently just `Record<string, unknown>` (`bridge.ts:7`) — **there is no typed event union on the TS side today; that is what F-023..F-028 must supply.**
- **Request stitching**: every request carries `id` (TS auto-increments a stringified counter, `bridge.ts:92-94`); responses echo it as `request_id` (string; `""` when absent).
- **Discriminator**: top-level `type` string on every event. Two naming families coexist:
  - dot-form bridge envelope types (`bridge.ready`, `command.result`, `permission.decision`, …) — minted by TerminalBridge itself;
  - snake_case stream types (`text_delta`, `session_end`, …) — `asdict()` of the `tui/engine/events.py` dataclasses, passed through verbatim with `request_id` injected (`terminal_bridge.py:817-822`).
- **Secondary discriminator inside `payload`**: the operator_core payload builders stamp `version: "v1"` + `domain` (snake_case: `workspace_snapshot`, `runtime_snapshot`, `routing_decision`, `agent_routes`, `permission_decision`, `permission_resolution`, `permission_outcome`, `permission_history`, `session_catalog`, `session_detail`). Note the dot/underscore split: event type `permission.decision` carries payload `domain: "permission_decision"`.
- `_emit_payload_result` (`terminal_bridge.py:897-915`): `{type, request_id, payload, content?, ...extra}` — extras used: `policy` (model.policy.result), `routes` (agent.routes.result), `session_id` (session.detail.result).

---

## 1. Events the bridge EMITS — bridge lifecycle & request/response family

Frequency classes: **boot** (once per process/handshake), **per-turn** (each prompt/command), **streaming** (many per turn), **refresh** (on demand/tab focus), **rare** (errors, approvals, cancels).

### 1.1 `bridge.ready` — boot
Emitted at `run_stdio()` start (`terminal_bridge.py:252-258`), before any request.

| field | type | notes |
|---|---|---|
| `type` | `"bridge.ready"` | |
| `schema_version` | `number` (1) | only event carrying this at top level besides stream events |
| `protocol` | `"dharma-terminal-bridge"` | |

TS handles: `protocol.ts:3841` (tab patch → runtime tab), `protocol.ts:2096` (activity feed).

### 1.2 `bridge.error` — rare
Emitted from many paths. Shape: `{type, code: string, message: string, request_id?: string}`.

Python-emitted `code` values (each cited):
- `invalid_json` (`:270`), `invalid_request` (`:279`), `unknown_request_type` (`:363`)
- `missing_prompt` (`:588` intent.resolve, `:678` session.bootstrap, `:720` session.start)
- `adapter_boot_failed` (`:697`), `unknown_provider` (`:710`)
- `missing_session_id` (`:844`), `session_detail_failed` (`:860`)

TS-synthesized codes (same `type`, minted in `bridge.ts`, never cross the wire): `invalid_bridge_json` (:59), `bridge_exit` (:66), `bridge_spawn_error` (:74), `bridge_stdin_unavailable` (:97), `bridge_send_failed` (:109).

TS handles: `protocol.ts:3987` (error line → runtime tab), `protocol.ts:2105` (activity). The union must include both wire codes and locally-minted codes.

### 1.3 `handshake.result` — boot
`terminal_bridge.py:393-405`.

| field | type |
|---|---|
| `request_id` | `string` |
| `providers` | `Array<{provider_id: string; default_model: string; models: Array<{id: string; display_name: string; capabilities: string[]}>}>` |
| `default_provider` | `string` (`"codex"` preferred, else first sorted, else `""`) |
| `legacy_terminal` | `{stack: "python-textual"; replacement_target: "bun-ink"}` |
| `adapter_boot_error` | `string \| null` |

`providers` is `[]` when adapters failed to boot (then `adapter_boot_error` is set). Provider ids today: `"claude" | "codex" | "openrouter"` (`:235-239`).
TS handles: `app.tsx:1674`, `protocol.ts:3844`, `protocol.ts:2096`.

### 1.4 `status.result` — refresh
`terminal_bridge.py:340-348`: `{type, request_id, active_session_id: string|null, active_provider: string|null, providers: string[]}`.
**TS: sends the `status` request (`app.tsx:814`) but has NO handler for `status.result` — fire-and-forget today.**

### 1.5 `command.result` — per-turn
`terminal_bridge.py:475-484` (success) and `:468` (commands-unavailable variant).

| field | type | notes |
|---|---|---|
| `request_id` | `string` | |
| `command` | `string` | leading `/` stripped |
| `target_pane` | `string` | from `_command_target_pane` (`:2203-2225`): one of `chat,runtime,repo,models,agents,evolution,ontology,sessions,approvals,control` |
| `output` | `string` (in practice) | system command handler output; async/model commands materialized into snapshot text (`:471-474`) |
| `action` | `string \| null` | opaque handler action tag, e.g. `"model:…"`, `"async:…"` |
| `ok` | `false` (only on the `:468` failure variant; absent on success) | |

TS handles: `protocol.ts:3849` (+ alias treatment of `action.result` with `action_type=command.run`), `protocol.ts:2078` (activity), heavy routing logic in `app.tsx` (e.g. `:207`, `:1235`, `:1567`).

### 1.6 `action.result` — per-turn
`_handle_action_run` (`terminal_bridge.py:486-522`): result of `_run_action` plus `{type, request_id, action_type}`. Shape varies by `action_type` (see §3.2 for the request side):

Common: `ok: boolean`, `summary: string`, `target_pane: string`.
Variant extras:
- `surface.refresh` (`:1987-2036`): `surface: string`, plus ONE of `payload` (workspace/session-catalog/routing/runtime/agent-routes payload depending on surface) or `output: string`; `policy`/`routes` extras on models/agents surfaces.
- `model.set` (`:2037-2052`): `output: string`, `policy: ModelPolicySummary`, `payload: RoutingDecisionPayload`.
- `agent.route` (`:2053-2088`): `output: string`, `route: Record<string,unknown> | null`.
- `evolution.run` (`:2089-2104`): `output: string`.
- `command.run` (`:2105-2121`): `output`, `action` (same as command.result fields).
- `approval.resolve` (`:2122-2165`): `output: string`, `payload: PermissionResolutionPayload` (with `enforcement_state` mutated to the runtime value by `:489-497` before emit).
- unknown action (`:2166-2171`): `ok: false`, `output: string`.

TS handles: `app.tsx:1495`, `:2134`, `:2335` (surface.refresh sniff), `protocol.ts:3849/2078` (command.run alias only). Other action_type results are consumed via payload sniffing, not a typed union.

### 1.7 `intent.result` — per-turn
Emitted by `intent.resolve` (`terminal_bridge.py:597-603`) AND mid-`session.start` when the bootstrap intent auto-executes a command (`:736-741`).

`intent` object (from `_resolve_prompt_intent`, `:1781-1877`):

| field | type | notes |
|---|---|---|
| `kind` | `"chat" \| "command" \| "model_switch" \| "identity" \| "memory" \| "agent" \| "evolution"` | |
| `auto_execute` | `boolean` | |
| `confidence` | `"low" \| "medium" \| "high"` | |
| `reason` | `string` | |
| `command` | `string` (only kind=command) | |
| `provider`,`model`,`strategy` | `string` (only kind=model_switch; may be `""`) | |

**TS: NOT handled anywhere** (no `intent.result` match in terminal/src). The intent the UI uses arrives embedded in `session.bootstrap.result.intent` instead.

### 1.8 `command.graph.result` — refresh (boot-adjacent: requested at startup, `app.tsx:815`)
`terminal_bridge.py:607-614`: `{type, request_id, graph, content: string}`.
`graph` (`_build_command_graph_summary`, `:1372-1390`): `{count: number, async_count: number, commands: string[], async_commands: string[], categories: Record<"chat"|"repo"|"runtime"|"control"|"ontology"|"memory"|"swarm", string[]>}`.
TS handles: `app.tsx:1874`.

### 1.9 `command.registry.result` — refresh
`terminal_bridge.py:616-625`: `{type, request_id, registry, content: string}`.
`registry` (`:1392-1445`): `{count: number, commands: Array<{name: string; async: boolean; category: string; target_pane: string; description: string}>}`.
TS handles: `app.tsx:1882`.

### 1.10 `operator.snapshot.result` — refresh
`terminal_bridge.py:627-636`: `{type, request_id, snapshot, content: string}`.
`snapshot` (`_build_operator_snapshot`, `:1447-1489`):
- success: `{runtime_db: string, overview: {sessions, claims, active_claims, acknowledged_claims, runs, active_runs, artifacts, promoted_facts, context_bundles, operator_actions: number}, runs: Array<{run_id, task_id, assigned_to, status, current_artifact_id, failure_code, started_at: string}>, actions: unknown[]}`
- failure: `{runtime_db: string, error: string, overview: {}, runs: [], actions: []}`

**TS: NOT handled** (never requested by app.tsx either — `runtime.snapshot` is used instead). Candidate for dropping or wiring in S2.

### 1.11 `model.policy.result` — refresh / per-route-change
`_emit_payload_result` at `terminal_bridge.py:648-653`: `{type, request_id, payload: RoutingDecisionPayload, policy: ModelPolicySummary}`.

`RoutingDecisionPayload` (`routing_payloads.py:15-30`):
```
{version:"v1", domain:"routing_decision",
 decision: {route_id, provider_id, model_id, strategy, reason: string,
            fallback_chain: string[] ("provider:model"), degraded: boolean,
            metadata: {active_label, default_route, targets}},
 strategies: string[], targets: Target[], fallback_targets: Array<{alias,provider,model,label}>}
```
`ModelPolicySummary` (`terminal_bridge.py:1549-1563`): `{selected_provider, selected_model, selected_route, strategy, strategies: string[], default_route, active_label, fallback_chain: Array<{alias,provider,model,label}>, targets: Array<{alias, provider, model, label, lane_role, tier, available: boolean, availability_reason, config_source}>}`.
TS handles: `app.tsx:1960`; typed as `RoutingDecisionPayload` in `types.ts:167-174`.

### 1.12 `agent.routes.result` — refresh
`terminal_bridge.py:655-662`: `{type, request_id, payload: AgentRoutesPayload, routes}`.
`AgentRoutesPayload` (`routing_payloads.py:33-42`): `{version:"v1", domain:"agent_routes", routes: Array<{intent, provider, model_alias, reasoning, role: string}>, openclaw: {present: boolean, readable: boolean, agents_count: number, providers: string[]}, subagent_capabilities: string[]}`. The `routes` extra is the same data pre-payload (`:1565-1606`).
TS handles: `app.tsx:2000`; typed `types.ts:176-182`.

### 1.13 `evolution.surface.result` — refresh
`terminal_bridge.py:664-673`: `{type, request_id, surface, content: string}`.
`surface` (`:1608-1627`): `{domains: Array<{name: string; fitness_threshold: number|null; max_iterations: number|null; max_duration_seconds: number|null}>, entry_commands: string[], principles: string[]}`.
TS handles: `app.tsx:2015`.

### 1.14 `session.bootstrap.result` — per-turn (the big one)
`terminal_bridge.py:675-694`: the entire `_build_session_bootstrap` dict (`:1261-1370`) spread at top level + `{type, request_id}`:

| field | type |
|---|---|
| `prompt` | `string` |
| `active_tab` | `string` |
| `intent` | Intent object (§1.7) |
| `selected_provider`, `selected_model`, `routing_strategy` | `string` |
| `command_graph` | CommandGraph (§1.8) |
| `model_policy` | ModelPolicySummary (§1.11) |
| `orientation_packet` | `Record<string, unknown>` (pydantic `model_dump(mode="json")` of OrientationPacket) |
| `workspace_preview` | `{“Repo root”, “Branch”, “Dirty”, “Repo risk”: string}` (`:1732-1738` — display-keyed!) |
| `runtime_preview` | `{“Runtime activity”, “Artifact state”, “Verification status”, “Loop decision”, “Next task”: string}` (`:1740-1747`) |
| `workspace_snapshot`, `ontology_snapshot`, `runtime_snapshot` | `string` (rendered markdown text) |
| `repo_guidance`, `session_context_hint`, `working_memory`, `system_prompt` | `string` |

TS handles: `app.tsx:1372`, `:2023` (drives the pending session.start in `pendingBootstraps`).
Note: previews use **display-label keys with spaces** — keep as `Record<string,string>` in TS (matches `TabPreview`).

### 1.15 `session.ack` — per-turn
`terminal_bridge.py:797-805`: `{type, request_id, session_id: string, provider: string, model: string}`. TS handles: `protocol.ts:3881`.

### 1.16 `assistant` — per-turn (identity/memory intents only)
`terminal_bridge.py:760-765` (identity), `:776-781` (memory): `{type:"assistant", request_id, message: string}`.
**TS: NOT handled.** `eventToTabPatch` has no `assistant` branch; identity/memory answers are silently dropped today. Must be in the union and wired (chat tab).

### 1.17 `session.catalog.result` — refresh
`terminal_bridge.py:835-839`: `{type, request_id, payload: SessionCatalogPayload}`.
`SessionCatalogPayload` (`session_payloads.py:50-87`): `{version:"v1", domain:"session_catalog", count: number, sessions: Array<{session: CanonicalSession, replay_ok: boolean, replay_issues: string[], total_turns: number, total_cost_usd: number}>}`.
`CanonicalSession` (`contracts.py:250-264`, asdict): `{session_id, provider_id, model_id, cwd, created_at, updated_at, status: string, parent_session_id, branch_label, worktree_path, summary: string|null, pinned_context: string[], compacted_from_session_ids: string[], metadata: {provider_session_id, total_cost_usd, total_turns, total_input_tokens, total_output_tokens, tags, forked_from}}`.
TS handles: `app.tsx:1826`, `protocol.ts:3875`; typed `types.ts:275-287` (matches, but TS `SessionCatalogPayload` omits `version`/`domain` — fine, they exist on the wire).

### 1.18 `session.detail.result` — refresh
`terminal_bridge.py:870-875`: `{type, request_id, payload: SessionDetailPayload, session_id: string}`.
`SessionDetailPayload` (`session_payloads.py:90-117`): `{version, domain:"session_detail", session: CanonicalSession, replay_ok, replay_issues, compaction_preview: {event_count: number, by_type: Record<string,number>, compactable_ratio: number, protected_event_types: string[], recent_event_types: string[]}, recent_events: CanonicalEventEnvelope[], approval_history: PermissionHistoryPayload}`.
`CanonicalEventEnvelope` (`contracts.py:352-365` via `adapters.py:90-111`): `{event_id: string ("evt-<uuid>"), event_type: string, source: "provider", audience: "all", transport: "local", session_id: string|null, created_at: string ISO, payload: Record<string,unknown> (the asdict'd stream event minus `type`), entity_refs: [], correlation_id: null, raw: object|null}` — enums serialize as strings via `_json_default`.
TS handles: `app.tsx:1858`, `protocol.ts:3878`; envelope `event_type` sniffed at `protocol.ts:3277-3289` (`text_delta`/`thinking_delta`/`tool_call_complete`/`tool_result`/`session_end`/`session_start`) and `app.tsx:698-705`.

### 1.19 `session.cancelled` — rare
`terminal_bridge.py:884-891`: `{type, request_id, cancelled: boolean, session_id: string|null}`. **TS: NOT handled** (no `session.cancel` request is ever sent by app.tsx either).

### 1.20 `workspace.snapshot.result` — refresh
`terminal_bridge.py:423-427`: `{type, request_id, payload: WorkspaceSnapshotPayload}`.
`WorkspaceSnapshotPayload` (`workspace_payloads.py:109-137`):
```
{version:"v1", domain:"workspace_snapshot", repo_root: string,
 git: {branch, head: string, staged|unstaged|untracked: number|null,
       changed_hotspots: Array<{name: string; count: number}>, changed_paths: string[],
       sync: {summary: string, status: "tracking"|"no_upstream"|"detached"|"unavailable",
              upstream: string|null, ahead: number|null, behind: number|null}},
 topology: {warnings: string[], repos: Array<{domain:"dgc"|"sab", name, role: string, canonical: boolean,
            path: string, exists: boolean, is_git: boolean, branch: string|null, head: string|null,
            dirty: boolean|null, modified_count: number, untracked_count: number}>},
 inventory: {python_modules|python_tests|scripts|docs|workflows: number|null},
 language_mix: Array<{suffix: string; count: number}>,
 largest_python_files: Array<{path: string; lines: number; defs: number; classes: number; imports: number}>,
 most_imported_modules: Array<{module: string; count: number}>}
```
**Bug-grade note**: `_handle_workspace_snapshot` computes `content` (`:417-422`) but never emits it — the dead variable means the TS fallback `String(typed.content ?? "")` at `app.tsx:1358` can never fire for this event. Same pattern in `_handle_runtime_snapshot` (`:447`).
TS handles: `app.tsx:1354/1736`, `protocol.ts:3872`; typed `types.ts:244-259` (TS adds optional `topology.preview`/`pressure_preview` the Python never sends).

### 1.21 `ontology.snapshot.result` — refresh
`terminal_bridge.py:431-437`: `{type, request_id, content: string}` (text only, no payload). TS handles: `app.tsx:1912`.

### 1.22 `runtime.snapshot.result` — refresh
`terminal_bridge.py:448-452`: `{type, request_id, payload: RuntimeSnapshotPayload}`.
`RuntimeSnapshotPayload` (`runtime_payloads.py:14-33` → `adapters.py:173-241`): `{version:"v1", domain:"runtime_snapshot", snapshot: CanonicalRuntimeSnapshot-asdict}` with snapshot fields:
`{snapshot_id ("runtime-<uuid>"), created_at: ISO, repo_root: string, runtime_db: string|null, health: "ok"|"degraded"|"critical"|"unknown", bridge_status: string ("connected"), active_session_count, active_run_count, artifact_count, context_bundle_count, anomaly_count: number, verification_status: string, next_task: string|null, active_task: string|null, worktree_count: number|null, summary: string|null, warnings: string[], metrics: Record<string,string> (claims/active_claims/acknowledged_claims/operator_actions/promoted_facts as STRINGS), metadata: {overview, runs, actions, supervisor_preview}}`.
TS handles: `app.tsx:1927`; typed `types.ts:122-159` — **TS type declares ~17 extra optional fields** (`verification_summary`, `loop_state`, `task_progress`, `durable_state`, `runtime_freshness`, …) **that Python never emits**; those are populated TS-side from supervisor state files, not from this event. The union must mark them as TS-enrichment, not wire fields.

### 1.23 `permission.history.result` — refresh
`terminal_bridge.py:457-461`: `{type, request_id, payload: PermissionHistoryPayload}`.
`PermissionHistoryPayload` (`permission_payloads.py:396-416`): `{version:"v1", domain:"permission_history", count: number, entries: Array<{action_id: string, decision: PermissionDecisionPayload, resolution: PermissionResolutionPayload|null, outcome: PermissionOutcomePayload|null, first_seen_at, last_seen_at: string, seen_count: number, pending: boolean, status: string}>}` (`:363-393`; history-entry payload `domain` values here are the **transcript event types** `permission_decision|permission_resolution|permission_outcome`, `:341-345`).
TS handles: `app.tsx:1771`; typed `types.ts:355-372`.

### 1.24 `permission.decision` — rare (gated tools during streaming)
`_emit_permission_decision` (`terminal_bridge.py:917-922`), fired when an adapter yields `ToolCallComplete` and governance says deny/require-approval (auto-allow is suppressed at `:919-920`). `{type, request_id, payload: PermissionDecisionPayload}`:
`{version:"v1", domain:"permission_decision", action_id: "perm-<sha1-12>", tool_name: string, risk: "safe_read"|"workspace_mutation"|"cross_boundary_mutation"|"shell_or_network"|"destructive", decision: "allow"|"require_approval"|"deny", rationale: string, policy_source: string ("legacy-governance"), requires_confirmation: boolean, command_prefix: string|null (first 120 chars of args), metadata: {tool_call_id, provider_options, provider_id, session_id}}` (`adapters.py:244-290`, `permission_payloads.py:37-58`; None-valued metadata keys stripped).
TS handles: `protocol.ts:3908`, `:1999`, `app.tsx:~1790`; typed `types.ts:306-318`.

### 1.25 `permission.resolution` — rare
Emitted inside `action.run/approval.resolve` (`terminal_bridge.py:505-509`) BEFORE the `action.result` for the same request_id. `{type, request_id, payload: PermissionResolutionPayload}`:
`{version:"v1", domain:"permission_resolution", action_id, resolution: "approved"|"denied"|"dismissed"|"resolved", resolved_at: ISO, actor: string, summary: string, note: string|null, enforcement_state: "recorded_only"|"runtime_recorded", metadata: {...request metadata, runtime_action_id?, runtime_event_id?}}` (`permission_payloads.py:61-75,105-127`; enforcement_state upgraded at `terminal_bridge.py:489-497`).
TS handles: `protocol.ts:3925`, `:2020`; typed `types.ts:331-342`.

### 1.26 `permission.outcome` — rare
Emitted right after permission.resolution (`terminal_bridge.py:510-514`). `{type, request_id, payload: PermissionOutcomePayload}`:
`{version:"v1", domain:"permission_outcome", action_id, outcome: "runtime_recorded"|"runtime_record_failed"|"runtime_applied"|"runtime_rejected"|"runtime_expired", outcome_at: ISO, source: "runtime", summary: string, metadata: {...}}` (`permission_payloads.py:78-90,130-148`; outcome classification at `terminal_bridge.py:575-582`).
TS handles: `app.tsx:1809`, activity at `protocol.ts:2041`; **not in `eventToTabPatch`** (intentional — pane render comes from the approval queue state). Typed `types.ts:344-353`.

---

## 2. Events the bridge EMITS — streaming canonical family (per `session.start`)

During `adapter.stream(...)` every yielded dataclass is `asdict()`-flattened and emitted with `request_id` injected (`terminal_bridge.py:816-822`). **All carry the base envelope fields** (`events.py:17-26`): `type: string`, `schema_version: 1`, `timestamp: number (unix float)`, `provider_id: string`, `session_id: string`, `raw: object|null`.

The full registry (`events.py` EVENT_TYPES, lines 209-230) — 20 types. "Adapters emit" verified by grepping constructor calls in `tui/engine/adapters/{claude,codex,openrouter}.py`:

| type | extra fields (beyond base envelope) | adapters emit? | freq | TS handled? |
|---|---|---|---|---|
| `session_start` | `model: string`, `provider_session_id: string\|null`, `capabilities: string[]`, `tools_available: string[]`, `system_info: object` | yes (4 sites) | per-turn | only via session-detail envelopes (`protocol.ts:3289`, `app.tsx:705`); not in live eventToTabPatch |
| `session_end` | `success: boolean`, `error_code: string\|null`, `error_message: string\|null` | yes (13 sites) | per-turn | `protocol.ts:3978`, `app.tsx:2129` |
| `text_delta` | `content: string`, `content_index: number`, `role: "assistant"` | claude only (1 site) | streaming | `protocol.ts:3894`, `app.tsx:2271+` |
| `text_complete` | same as text_delta | yes (5 sites) | per-turn | `protocol.ts:3894`, `app.tsx:2275+` |
| `thinking_delta` | `content: string` | claude only | streaming | `protocol.ts:3897`, `:1943` |
| `thinking_complete` | `content: string`, `is_redacted: boolean` | yes (3 sites) | per-turn | `protocol.ts:3900`, `:1943` |
| `tool_call_start` | `tool_call_id`, `tool_name`, `arguments_partial: string` | **NO adapter constructs it** | — | not handled |
| `tool_args_delta` | `tool_call_id`, `delta: string` | 1 site | streaming | not handled |
| `tool_call_complete` | `tool_call_id`, `tool_name`, `arguments: string`, `provider_options: object` | yes (2 sites) | streaming | `protocol.ts:3942`, `:1958`; also triggers permission.decision server-side |
| `tool_result` | `tool_call_id`, `tool_name`, `content: string`, `is_error: boolean`, `structured_result: object\|null`, `duration_ms: number\|null` | yes (2 sites) | streaming | `protocol.ts:3955`, `:1976` |
| `tool_progress` | `tool_call_id`, `tool_name`, `elapsed_seconds: number` | 1 site | streaming | not handled |
| `task_started` | `task_id`, `description: string`, `parent_tool_call_id: string\|null` | 1 site | rare | `protocol.ts:3965`, `:2062` |
| `task_progress` | `task_id`, `summary: string` | 1 site | rare | `protocol.ts:3965`, `:2062` |
| `task_complete` | `task_id`, `success: boolean`, `summary: string` | **NO adapter constructs it** | — | `protocol.ts:3965` (handler exists, dead today) |
| `usage` | `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `thinking_tokens: number`, `total_cost_usd: number\|null`, `model_breakdown: object` | yes (3 sites) | per-turn | not handled live (only in compaction `protected_event_types`) |
| `error` | `code: string`, `message: string`, `retryable: boolean`, `retry_after_seconds: number\|null` | yes (12 sites) | rare | `protocol.ts:3987`, `:2105` |
| `rate_limit` | `status: string`, `utilization: number\|null`, `resets_at: number\|null` | 1 site | rare | not handled |
| `permission_decision` / `permission_resolution` / `permission_outcome` (snake_case dataclasses) | see `events.py:172-206` | not adapter-emitted; used as **session-store transcript records** (`terminal_bridge.py:924-981`) and reappear inside `session.detail.result.recent_events[].event_type` | — | via approval history only |

**Critical dual-shape warning for `session_end`**: besides the adapter dataclass (full envelope), the bridge synthesizes a minimal `{type:"session_end", request_id, success: true, session_id: null}` for auto-executed command/identity/memory intents (`terminal_bridge.py:750-756, 766-773, 783-790`) — no `schema_version`, no `timestamp`, `session_id: null` not `""`. The TS type must allow both.

---

## 3. Requests the bridge ACCEPTS

Dispatch is the if-chain in `_handle_request` (`terminal_bridge.py:290-370`). Exactly **20 request types**; anything else → `bridge.error/unknown_request_type`. All requests: `{id?: string|number, type: string, ...}` (`id` coerced to string).

| # | type | fields beyond `id` (observed types; defaults) | result event(s) | TS sends? (app.tsx) |
|---|---|---|---|---|
| 1 | `handshake` | — | `handshake.result` | yes (:1619, :2484, :2492) |
| 2 | `command.run` | `command: string` (leading `/` ok) | `command.result` | yes (:2055, :2622) |
| 3 | `action.run` | `action_type: string` + variant fields (§3.2) | `action.result` (+ `permission.resolution` + `permission.outcome` for approval.resolve) | yes (:2058, :2680, :2694) |
| 4 | `command.graph` | — | `command.graph.result` | yes (:815) |
| 5 | `command.registry` | — | `command.registry.result` | yes (:816) |
| 6 | `intent.resolve` | `prompt: string` (required) | `intent.result` \| `bridge.error/missing_prompt` | **no** |
| 7 | `model.policy` | `provider?: string ("codex")`, `model?: string`, `strategy?: string` | `model.policy.result` | yes (:124, :848, :2611, :2946) |
| 8 | `operator.snapshot` | — | `operator.snapshot.result` | **no** |
| 9 | `agent.routes` | — | `agent.routes.result` | yes (:125, :852, :2087) |
| 10 | `evolution.surface` | — | `evolution.surface.result` | yes (:126, :2102) |
| 11 | `session.bootstrap` | `prompt` (required), `active_tab?`, `provider?`, `model?`, `strategy?` — **`resume_session_id` is sent by TS (:2649) but IGNORED by `_build_session_bootstrap`** | `session.bootstrap.result` | yes (:2643) |
| 12 | `session.start` | `prompt` (required), `provider? ("codex")`, `model?`, `session_id?`, `bootstrap?: object`, `system_prompt?`, `enable_thinking?: boolean`, `resume_session_id?`, `provider_options?: object` — **`messages` is sent by TS (:2091-2123) but IGNORED by Python** (`:807-814` builds messages from `prompt` only) | `session.ack` → stream events → `session_end`; or intent shortcuts (`intent.result`+`command.result`+synth `session_end`, or `assistant`+synth `session_end`); or `bridge.error` | yes (:2090, :2105, :2116) |
| 13 | `session.catalog` | `cwd?: string`, `limit?: number (20)` | `session.catalog.result` | yes (:858) |
| 14 | `session.detail` | `session_id` (required), `transcript_limit?: number (80)` | `session.detail.result` \| `bridge.error` | yes (:869) |
| 15 | `session.cancel` | — | `session.cancelled` | **no** |
| 16 | `status` | — | `status.result` | yes (:814) — result unhandled |
| 17 | `workspace.snapshot` | — | `workspace.snapshot.result` | yes (:122, :832) |
| 18 | `ontology.snapshot` | — | `ontology.snapshot.result` | yes (:817) |
| 19 | `runtime.snapshot` | — | `runtime.snapshot.result` | yes (:123, :836) |
| 20 | `permission.history` | `limit?: number (50)` | `permission.history.result` | yes (:862) |

### 3.2 `action.run` sub-vocabulary (`action_type`, `_run_action` `:1986-2171`)

| action_type | request fields | notes |
|---|---|---|
| `surface.refresh` | `surface: string` — recognized: `repo/workspace`, `sessions/session`, `models/model`, `control/runtime`, `agents/agent`, `ontology`, `commands/command/registry`, `evolution/evolve`, `notes/memory` (unknown → runtime snapshot output) | payload attach varies by surface |
| `model.set` | `provider: string`, `model: string`, `strategy?: string` | mutates active route server-side |
| `agent.route` | `intent: string` | matched against the 4 static routes |
| `evolution.run` | `command: string` (`/evolve`, `/loops`, `/cascade …`) | |
| `command.run` | `command: string` | same as top-level command.run minus model materialization |
| `approval.resolve` | `action_id: string` (required), `resolution: "approved"\|"denied"\|"dismissed"\|"resolved"` (required), `actor?: string ("operator")`, `note?: string`, `metadata?: object` (should carry `session_id`/`task_id`/`run_id` for runtime recording) | triple-emit: permission.resolution, permission.outcome, action.result |

---

## 4. Mismatches & gaps surfaced by this inventory (feed into F-023..F-028 acceptance)

1. **TS `messages` ignored**: app.tsx sends conversation history in `session.start.messages`; Python builds `messages=[{role:"user",content:prompt}]` only (`terminal_bridge.py:807-814`). Continuity is currently prompt-string-only on the wire.
2. **`resume_session_id` ignored in `session.bootstrap`** (used only in `session.start` → CompletionRequest).
3. **Dead `content`**: workspace/runtime snapshot handlers compute rendered text and drop it (`:417-422`, `:447`); TS fallbacks reading `event.content` for those events are dead code.
4. **Unhandled on TS side** (must still be union members): `intent.result`, `assistant`, `session.cancelled`, `status.result`, `operator.snapshot.result`, stream `usage`, `rate_limit`, `tool_args_delta`, `tool_progress`, live `session_start`.
5. **Schema-only stream types**: `tool_call_start` and `task_complete` are defined but no adapter constructs them — type them, mark as reserved.
6. **`session_end` dual shape** (adapter envelope vs synthesized minimal, §2).
7. **TS `CanonicalRuntimeSnapshot` superset**: ~17 optional fields in `types.ts:122-159` are TS-side supervisor enrichment, never on the wire — split wire type from enriched view type.
8. **Naming split**: event types dot-form vs payload `domain` snake_case vs permission-history inner domains using transcript event-type names (`permission_decision` etc.).
9. **`_json_default` stringification** means any unexpected Python object arrives as a bare string — TS parsers should be tolerant (`z.unknown()` / `Record<string, unknown>` escape hatches at metadata/raw boundaries).

---

## 5. Proposed discriminated-union sketch (TypeScript), grouped into S2 families

Discriminate on `type`. Shared scaffolding:

```ts
// ── shared ────────────────────────────────────────────────────────────
interface RequestStamped { request_id: string }            // "" when absent
interface StreamEnvelope {                                  // events.py base
  schema_version: 1; timestamp: number;
  provider_id: string; session_id: string;
  raw?: Record<string, unknown> | null;
}
type PaneId = "chat"|"runtime"|"repo"|"models"|"agents"|"evolution"
            |"ontology"|"sessions"|"approvals"|"control"|"commands"
            |"thinking"|"tools"|"timeline";

// ── family: lifecycle / transport ─────────────────────────────────────
type BridgeReadyEvent = { type:"bridge.ready"; schema_version:1; protocol:"dharma-terminal-bridge" };
type BridgeErrorEvent = { type:"bridge.error"; code:BridgeErrorCode; message:string } & Partial<RequestStamped>;
type BridgeErrorCode =
  | "invalid_json"|"invalid_request"|"unknown_request_type"|"missing_prompt"
  | "adapter_boot_failed"|"unknown_provider"|"missing_session_id"|"session_detail_failed"
  // minted locally in bridge.ts, never on the wire:
  | "invalid_bridge_json"|"bridge_exit"|"bridge_spawn_error"
  | "bridge_stdin_unavailable"|"bridge_send_failed";
type HandshakeResultEvent = RequestStamped & {
  type:"handshake.result";
  providers: ProviderInfo[]; default_provider: string;
  legacy_terminal: { stack:string; replacement_target:string };
  adapter_boot_error: string | null;
};
type StatusResultEvent = RequestStamped & {
  type:"status.result";
  active_session_id: string|null; active_provider: string|null; providers: string[];
};

// ── family: workspace (F-02x repo/ontology surfaces) ──────────────────
type WorkspaceSnapshotResultEvent = RequestStamped &
  { type:"workspace.snapshot.result"; payload: WorkspaceSnapshotPayload };   // types.ts:244 already correct
type OntologySnapshotResultEvent = RequestStamped &
  { type:"ontology.snapshot.result"; content: string };

// ── family: runtime (control plane) ───────────────────────────────────
type RuntimeSnapshotResultEvent = RequestStamped &
  { type:"runtime.snapshot.result"; payload: RuntimeSnapshotPayload };       // wire snapshot ONLY (no TS-enriched fields)
type OperatorSnapshotResultEvent = RequestStamped &
  { type:"operator.snapshot.result"; snapshot: OperatorSnapshot; content: string };

// ── family: sessions (catalog/detail/continuity) ──────────────────────
type SessionBootstrapResultEvent = RequestStamped & SessionBootstrap & { type:"session.bootstrap.result" };
type SessionAckEvent       = RequestStamped & { type:"session.ack"; session_id:string; provider:string; model:string };
type SessionCatalogResultEvent = RequestStamped & { type:"session.catalog.result"; payload: SessionCatalogPayload };
type SessionDetailResultEvent  = RequestStamped & { type:"session.detail.result"; payload: SessionDetailPayload; session_id: string };
type SessionCancelledEvent = RequestStamped & { type:"session.cancelled"; cancelled:boolean; session_id:string|null };
type AssistantMessageEvent = RequestStamped & { type:"assistant"; message:string };   // identity/memory intents
type IntentResultEvent     = RequestStamped & { type:"intent.result"; intent: PromptIntent };
type SessionEndEvent =
  | (RequestStamped & StreamEnvelope & { type:"session_end"; success:boolean; error_code:string|null; error_message:string|null })
  | (RequestStamped & { type:"session_end"; success:true; session_id:null });        // synthesized shortcut shape

// ── family: streaming (chat/thinking/tools/timeline panes) ────────────
type TextDeltaEvent     = RequestStamped & StreamEnvelope & { type:"text_delta"; content:string; content_index:number; role:"assistant" };
type TextCompleteEvent  = RequestStamped & StreamEnvelope & { type:"text_complete"; content:string; content_index:number; role:"assistant" };
type ThinkingDeltaEvent = RequestStamped & StreamEnvelope & { type:"thinking_delta"; content:string };
type ThinkingCompleteEvent = RequestStamped & StreamEnvelope & { type:"thinking_complete"; content:string; is_redacted:boolean };
type ToolCallCompleteEvent = RequestStamped & StreamEnvelope & { type:"tool_call_complete"; tool_call_id:string; tool_name:string; arguments:string; provider_options:Record<string,unknown> };
type ToolResultEvent    = RequestStamped & StreamEnvelope & { type:"tool_result"; tool_call_id:string; tool_name:string; content:string; is_error:boolean; structured_result:Record<string,unknown>|null; duration_ms:number|null };
type ToolArgsDeltaEvent = RequestStamped & StreamEnvelope & { type:"tool_args_delta"; tool_call_id:string; delta:string };
type ToolProgressEvent  = RequestStamped & StreamEnvelope & { type:"tool_progress"; tool_call_id:string; tool_name:string; elapsed_seconds:number };
type TaskStartedEvent   = RequestStamped & StreamEnvelope & { type:"task_started"; task_id:string; description:string; parent_tool_call_id:string|null };
type TaskProgressEvent  = RequestStamped & StreamEnvelope & { type:"task_progress"; task_id:string; summary:string };
type TaskCompleteEvent  = RequestStamped & StreamEnvelope & { type:"task_complete"; task_id:string; success:boolean; summary:string };  // reserved, never emitted today
type ToolCallStartEvent = RequestStamped & StreamEnvelope & { type:"tool_call_start"; tool_call_id:string; tool_name:string; arguments_partial:string };  // reserved
type SessionStartEvent  = RequestStamped & StreamEnvelope & { type:"session_start"; model:string; provider_session_id:string|null; capabilities:string[]; tools_available:string[]; system_info:Record<string,unknown> };
type UsageEvent         = RequestStamped & StreamEnvelope & { type:"usage"; input_tokens:number; output_tokens:number; cache_read_tokens:number; cache_write_tokens:number; thinking_tokens:number; total_cost_usd:number|null; model_breakdown:Record<string,unknown> };
type StreamErrorEvent   = RequestStamped & StreamEnvelope & { type:"error"; code:string; message:string; retryable:boolean; retry_after_seconds:number|null };
type RateLimitEvent     = RequestStamped & StreamEnvelope & { type:"rate_limit"; status:string; utilization:number|null; resets_at:number|null };

// ── family: approvals ──────────────────────────────────────────────────
type PermissionDecisionEvent   = RequestStamped & { type:"permission.decision";   payload: CanonicalPermissionDecision };
type PermissionResolutionEvent = RequestStamped & { type:"permission.resolution"; payload: CanonicalPermissionResolution };
type PermissionOutcomeEvent    = RequestStamped & { type:"permission.outcome";    payload: CanonicalPermissionOutcome };
type PermissionHistoryResultEvent = RequestStamped & { type:"permission.history.result"; payload: PermissionHistoryPayload };

// ── family: models / routing ───────────────────────────────────────────
type ModelPolicyResultEvent = RequestStamped & { type:"model.policy.result"; payload: RoutingDecisionPayload; policy: ModelPolicySummary };
type AgentRoutesResultEvent = RequestStamped & { type:"agent.routes.result"; payload: AgentRoutesPayload; routes: AgentRoutesSummary };

// ── family: tabs / commands / actions ──────────────────────────────────
type CommandResultEvent = RequestStamped & {
  type:"command.result"; command:string; target_pane:PaneId; output:string;
  action:string|null; ok?:false;
};
type CommandGraphResultEvent    = RequestStamped & { type:"command.graph.result"; graph:CommandGraph; content:string };
type CommandRegistryResultEvent = RequestStamped & { type:"command.registry.result"; registry:CommandRegistry; content:string };
type EvolutionSurfaceResultEvent = RequestStamped & { type:"evolution.surface.result"; surface:EvolutionSurface; content:string };
type ActionResultEvent = RequestStamped & { type:"action.result"; action_type:ActionType;
  ok:boolean; summary:string; target_pane:PaneId;
  output?:string; payload?:Record<string,unknown>; policy?:ModelPolicySummary;
  routes?:AgentRoutesSummary; route?:Record<string,unknown>|null; surface?:string; action?:string|null };
type ActionType = "surface.refresh"|"model.set"|"agent.route"|"evolution.run"|"command.run"|"approval.resolve";

// ── the union ──────────────────────────────────────────────────────────
export type DharmaBridgeEvent =
  | BridgeReadyEvent | BridgeErrorEvent | HandshakeResultEvent | StatusResultEvent          // lifecycle
  | WorkspaceSnapshotResultEvent | OntologySnapshotResultEvent                               // workspace
  | RuntimeSnapshotResultEvent | OperatorSnapshotResultEvent                                 // runtime
  | SessionBootstrapResultEvent | SessionAckEvent | SessionCatalogResultEvent
  | SessionDetailResultEvent | SessionCancelledEvent | SessionEndEvent
  | AssistantMessageEvent | IntentResultEvent                                               // sessions
  | TextDeltaEvent | TextCompleteEvent | ThinkingDeltaEvent | ThinkingCompleteEvent
  | ToolCallStartEvent | ToolArgsDeltaEvent | ToolCallCompleteEvent | ToolResultEvent
  | ToolProgressEvent | TaskStartedEvent | TaskProgressEvent | TaskCompleteEvent
  | SessionStartEvent | UsageEvent | StreamErrorEvent | RateLimitEvent                       // streaming
  | PermissionDecisionEvent | PermissionResolutionEvent | PermissionOutcomeEvent
  | PermissionHistoryResultEvent                                                            // approvals
  | ModelPolicyResultEvent | AgentRoutesResultEvent                                         // models
  | CommandResultEvent | CommandGraphResultEvent | CommandRegistryResultEvent
  | EvolutionSurfaceResultEvent | ActionResultEvent;                                        // tabs

// ── requests (mirror) ──────────────────────────────────────────────────
export type DharmaBridgeRequest =
  | { type:"handshake" } | { type:"status" }
  | { type:"command.run"; command:string }
  | { type:"action.run" } & ActionRunVariant
  | { type:"command.graph" } | { type:"command.registry" }
  | { type:"intent.resolve"; prompt:string }
  | { type:"model.policy"; provider?:string; model?:string; strategy?:string }
  | { type:"operator.snapshot" } | { type:"agent.routes" } | { type:"evolution.surface" }
  | { type:"session.bootstrap"; prompt:string; active_tab?:string; provider?:string; model?:string; strategy?:string }
  | { type:"session.start"; prompt:string; provider?:string; model?:string; session_id?:string;
      bootstrap?:Record<string,unknown>; system_prompt?:string; enable_thinking?:boolean;
      resume_session_id?:string; provider_options?:Record<string,unknown> }     // NOTE: `messages` not consumed by Python
  | { type:"session.catalog"; cwd?:string; limit?:number }
  | { type:"session.detail"; session_id:string; transcript_limit?:number }
  | { type:"session.cancel" }
  | { type:"workspace.snapshot" } | { type:"ontology.snapshot" } | { type:"runtime.snapshot" }
  | { type:"permission.history"; limit?:number };

type ActionRunVariant =
  | { action_type:"surface.refresh"; surface:string }
  | { action_type:"model.set"; provider:string; model:string; strategy?:string }
  | { action_type:"agent.route"; intent:string }
  | { action_type:"evolution.run"; command:string }
  | { action_type:"command.run"; command:string }
  | { action_type:"approval.resolve"; action_id:string;
      resolution:"approved"|"denied"|"dismissed"|"resolved";
      actor?:string; note?:string; metadata?:Record<string,unknown> };
```

Supporting payload types (`WorkspaceSnapshotPayload`, `RuntimeSnapshotPayload`, `RoutingDecisionPayload`, `AgentRoutesPayload`, `SessionCatalogPayload`, `SessionDetailPayload`, `CanonicalPermission*`, `PermissionHistoryPayload`) already exist in `terminal/src/types.ts:94-392` and match the wire (modulo the §4.7 runtime-snapshot superset). The union above is the missing layer between `BridgeEvent = Record<string, unknown>` and those payload types.
