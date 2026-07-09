---
title: Agent Holon Code Map
path: docs/architecture/AGENT_HOLON_CODE_MAP.md
doc_type: architecture
status: current
created: 2026-07-06
owner_surface: sovereign_holon_runtime
summary: Canonical code map and operating index for agent, persistent-agent, and sovereign-holon runtime surfaces.
---

# Agent Holon Code Map

This is the canonical code map for the current agent / persistent-agent /
sovereign-holon runtime in `dharma_swarm`.

It is a map, not a runtime rewrite. Do not collapse these modules into one
file, do not move runtime state, and do not create a new agent system to solve
navigation drift.

**Scope note**: this map covers the sovereign-holon talk/run/health call
chains only. For model routing, A2A transport/spine, API/gateway routers,
CLI/wrapper inventory, identity/state-home census, worktree drift across the
full dharma_swarm-family clone set, and the parallel `~/.hermes` ecosystem
(including its live self-mod loop and cross-system bridge), see the
companion document
[`HOLON_RUNTIME_FULL_ESTATE_MAP.md`](HOLON_RUNTIME_FULL_ESTATE_MAP.md).

## Snapshot Evidence

This map was produced from the current worktree and live-state projections after
running:

- `make onboard`
- `dgc agent list`
- `dgc agent status --json`

Important observations from those commands on 2026-07-06:

- The active checkout is `/Users/dhyana/dharma_swarm` on branch
  `agent/magpie-seed`.
- `dgc agent list` shows two distinct operator surfaces: preset autonomous
  agents and registered sovereign holons under `~/.dharma/agents`.
- `dgc agent list` and `dgc agent status --json` both emitted
  `[holon] provider 'sakana' -> 'sakana' is not a valid ProviderType; defaulting to claude_code`.
- `dgc agent status --json` showed most registered holons without service
  heartbeats. `codex_composer` had a fresh service heartbeat ledger, but
  `service_alive=false` and `status=error`. This is liveness evidence, not proof
  of useful work.
- `make onboard` reported stale live-ops evidence for several surfaces. Treat
  onboard/live-ops prose as orientation; verify claims against code, receipts,
  runtime DB rows, and target-owned artifacts.

## Authority Model

Keep these four layers separate:

| Layer | Canonical owner | What it proves | What it does not prove |
| --- | --- | --- | --- |
| Identity | `~/.dharma/agents/<name>/identity.json` plus `prompt_variants/active.txt`, loaded by `dharma_swarm/holon_bridge.py` | The named holon exists, has a prompt, provider, model, and LivingDock home | That it is alive or doing useful work |
| Liveness | `dharma_swarm/holon_service_liveness.py`, `dharma_swarm/holon_canonical_state.py`, `scripts/runtime/live_ops_census.py` | Recent heartbeat, ledger integrity, bridge/process/session evidence | Semantic cognition, completed work, or correct output |
| Work authority | `dharma_swarm/holon_runtime.py`, `dharma_swarm/holon_killswitch.py`, `dharma_swarm/holon_budget_guard.py` | A governed wake cycle checks kill and budget before work | That the produced answer satisfied an external task |
| Completion proof | `dharma_swarm/holon_persistence.py`, `dharma_swarm/holon_truth_projection.py`, target artifacts, verifier receipts | What ran, what status was recorded, what artifacts were bound into runtime truth | Broad agent competence or standing authority |

Tmux/process liveness is evidence only. A2A bridge liveness is transport
evidence only. Neither is sovereign holon health by itself.

## Canonical Path: Talk To A Holon

Use this path when the operator or UI needs to speak to a registered holon as
itself.

### CLI Path

```text
dgc agent talk <name> <message>
  -> dharma_swarm/dgc_cli.py
  -> dharma_swarm/terminal_commands/agents.py:_cmd_agent_talk
  -> scripts/holon_talk.py:talk
  -> dharma_swarm/holon_bridge.py:load_holon
  -> scripts/holon_talk.py:_resolve_provider
  -> provider.stream(LLMRequest)
  -> ~/.dharma/agents/<name>/talk_receipts.jsonl
```

`scripts/holon_talk.py` supports two explicit routing modes:

- `declared-first`: use the holon's identity-declared provider/model first via
  `holon_bridge.get_holon_provider`.
- `free-first`: walk `preferred_runtime_provider_configs()` while excluding the
  `claude_code` fallback door.

The CLI talk script writes a compact receipt directly to
`~/.dharma/agents/<name>/talk_receipts.jsonl`.

### API Path

```text
POST /holon/{name}/chat
  -> api/main.py includes api/routers/holon.py
  -> api/routers/holon.py:holon_chat
  -> dharma_swarm/holon_bridge.py:load_holon
  -> dharma_swarm/holon_bridge.py:build_livingdock_dialogue_context
  -> dharma_swarm/holon_bridge.py:get_holon_dialogue_provider
  -> dharma_swarm/holon_bridge.py:holon_reply
  -> dharma_swarm/holon_persistence.py:append_talk_receipt
  -> ~/.dharma/agents/<name>/talk_receipts.jsonl
  -> ~/.dharma/agents/<name>/dialogue/conversation_receipts/*.json
```

This is the preferred UI/backend dialogue path because it:

- Validates the holon name before touching paths.
- Loads the holon's own prompt and model from `~/.dharma/agents`.
- Adds LivingDock context as read-only evidence.
- Uses `get_holon_dialogue_provider`, which refuses agentic providers such as
  `claude_code` and `codex` unless a safe non-agentic dialogue override exists.
- Streams through `holon_reply` and never delegates to `_agentic_stream`.
- Writes normalized dialogue receipts with hashes and context references via
  `append_talk_receipt`.

Do not use `POST /agents/{agent_id}/chat` as the sovereign holon talk path. That
route in `api/routers/agents.py` builds a persona prompt for a generic agent chat
and delegates to `_agentic_stream`; it is a dashboard convenience surface, not the
holon's own read-only dialogue seat.

## Canonical Path: Governed Wake Cycles

Use this path when a registered holon should run one or more governed work
cycles.

```text
dgc agent run <name> --cycles N
  -> dharma_swarm/dgc_cli.py
  -> dharma_swarm/terminal_commands/agents.py:_cmd_agent_run
  -> scripts/holon_run.py:run
  -> dharma_swarm/holon_bridge.py:load_holon
  -> scripts/holon_talk.py:_resolve_provider
  -> scripts/holon_run.py:_make_free_runner
  -> dharma_swarm/holon_runtime.py:run_holon_loop
  -> dharma_swarm/holon_runtime.py:holon_wake_cycle
  -> dharma_swarm/holon_killswitch.py:is_kill_requested
  -> dharma_swarm/holon_budget_guard.py:check_cost_cap
  -> injected runner
  -> dharma_swarm/holon_compass.py:log_signal
  -> dharma_swarm/holon_persistence.py:save_cycle_record
  -> ~/.dharma/agents/<name>/holon_events.jsonl
```

The load-bearing order inside `holon_wake_cycle` is:

1. Kill check.
2. Budget check.
3. One injected unit of work.
4. Non-binding compass signal.
5. Append-only persistence.

`holon_runtime.py` intentionally does not own live model wiring. The runner is
injected. Tests can stub the runner; `scripts/holon_run.py` supplies a live
runner built from `holon_bridge` and `scripts/holon_talk.py`.

Completion proof can then be projected outward:

```text
standalone holon receipt JSON
  -> dharma_swarm/holon_truth_projection.py:project_holon_receipt
  -> dharma_swarm/runtime_state.py:RuntimeStateStore
  -> ~/.dharma/state/runtime.db
  -> execution_identity + task_claim + delegation_run + artifact_records + runtime_receipts
```

Canonical component state is separate:

```text
dharma_swarm/holon_canonical_state.py:project_canonical_holon_state
  -> ~/.dharma/a2a_bus/state/<agent_uid>.json
```

That file projects service heartbeat, A2A bridge heartbeat, semantic responder
receipt, and L4 proof evidence. It does not supervise processes or prove useful
work by itself.

## Runtime Code Owners

### Holon Runtime

| File | Owner role | Edit when |
| --- | --- | --- |
| `dharma_swarm/holon_bridge.py` | Loads a registered holon as itself; builds read-only dialogue requests; resolves provider routes | Changing identity loading, read-only dialogue context, provider safety, or outcome-claim guard utility |
| `dharma_swarm/holon_runtime.py` | Governed wake-cycle body | Changing kill/budget/work/compass/persist order or cycle result semantics |
| `dharma_swarm/holon_persistence.py` | Append-only holon cycle and talk receipt storage | Changing `holon_events.jsonl`, `talk_receipts.jsonl`, or conversation receipt format |
| `dharma_swarm/holon_health.py` | Read-only holon status projection | Changing `dgc agent status` fields or health row semantics |
| `dharma_swarm/holon_service_liveness.py` | Per-holon service heartbeat ledger and liveness projection | Changing heartbeat schema, ledger hash chain, freshness, or `service_alive` rules |
| `dharma_swarm/holon_canonical_state.py` | Canonical A2A-bus state projection | Changing `~/.dharma/a2a_bus/state/<agent>.json` fields or component aggregation |
| `dharma_swarm/holon_truth_projection.py` | Standalone holon receipt to runtime truth adapter | Changing projection into `runtime.db`, artifact binding, lifecycle mapping, or Codex Composer canonical state helpers |
| `dharma_swarm/holon_killswitch.py` | Durable kill signal | Changing kill marker path or operator stop semantics |
| `dharma_swarm/holon_budget_guard.py` | Cost-cap enforcement primitive | Changing budget halt semantics |
| `dharma_swarm/holon_compass.py` | Non-binding telos compass signal | Changing scoring/logging of compass signals; not enforcement |

### Operator And API Surfaces

| File | Owner role | Edit when |
| --- | --- | --- |
| `dharma_swarm/terminal_commands/agents.py` | Thin command handlers for `dgc agent ...` | Changing CLI behavior for talk/run/status/kill/list |
| `dharma_swarm/dgc_cli.py` | Large argparse command tree and dispatch | Adding/removing top-level CLI verbs or parser args only; prefer `terminal_commands/agents.py` for behavior |
| `api/routers/holon.py` | Canonical read-only API chat route | Changing `/holon/{name}/chat` or `/holon/{name}/chat/history` |
| `api/routers/agents.py` | Generic agent dashboard/detail/chat route | Changing dashboard detail projection or legacy generic chat, not the holon own-model route |
| `api/main.py` | FastAPI app and router inclusion | Changing router registration, auth, or app startup |
| `scripts/holon_talk.py` | CLI live talk implementation | Changing explicit CLI routing modes or compact talk receipt behavior |
| `scripts/holon_run.py` | CLI live governed-cycle runner | Changing live runner construction for governed cycles |
| `scripts/runtime/live_ops_census.py` | Read-only live-ops census | Changing operator cockpit evidence aggregation, especially `codex_composer` L4 proof gaps |

### Lower-Level Or Legacy Agent Runtime

| File | Current role | Relationship to holons |
| --- | --- | --- |
| `dharma_swarm/swarm.py` | Top-level swarm coordinator for task board, agent pool, message bus, orchestrator, memory, telemetry, optional subsystems | Full swarm boot path, not the canonical direct holon talk/run path |
| `dharma_swarm/agent_runner.py` | Lower-level task executor and `AgentPool` for swarm/orchestrator work | Worker execution substrate; edit for generic task execution, provider routing, local tool loop, and completion contracts |
| `dharma_swarm/autonomous_agent.py` | ReAct-style autonomous agent with tools and memory | Legacy/direct autonomous wake path; can build an `AgentIdentity` from a registered holon but sets `allowed_tools=[]` for that adapter |
| `dharma_swarm/persistent_agent.py` | Periodic self-waking agent loop around `AutonomousAgent` | Older persistent-agent loop; not the current governed holon wake-cycle body |
| `dharma_swarm/agent_registry.py` | Ginko registry, prompt evolution, fitness, and budget bookkeeping | Defaults to `~/.dharma/ginko/agents`; do not use as the holon identity authority |

## State Homes

| Path | Type | Current meaning | Edit policy |
| --- | --- | --- | --- |
| `~/.dharma/agents` | Live runtime state | Canonical LivingDock-style holon home used by `holon_bridge`, `holon_health`, `holon_runtime`, `holon_persistence` | Do not mutate identity files for this task; runtime code may append receipts through owner APIs |
| `~/.dharma/ginko/agents` | Live runtime state | Legacy/lower-level `AgentRegistry` home for prompt variants, fitness, and task logs | Do not treat as sovereign holon identity authority |
| `~/.dharma/a2a/cards` | Live runtime state | A2A/external discovery cards; contains admitted and historical card names | Do not rename/delete cards from a code-map task |
| `~/.dharma/external_agents` | Live runtime state | External responders and nests, including semantic responder state | Read as evidence only unless working on that owner surface |
| `~/.dharma/a2a_bus` | Live runtime state | A2A bus messages, receipts, bridge heartbeats, canonical state projections | Do not edit by hand; write only through owner code/verifiers |
| `~/.dharma/state/runtime.db` | Live runtime database | Runtime truth store for execution identities, task claims, delegation runs, artifacts, and receipts | Do not edit directly; use `RuntimeStateStore` owners |
| `docs/architecture/*` | Repo docs | Operating maps/specs | This file is the canonical code map for the requested scope |
| `docs/sovereign_holons/*` | Repo docs | Sovereign holon design/state-of-truth docs | Verify before citing; docs may lag code/live state |

## What Future Agents Should Edit First

For holon dialogue changes:

1. `api/routers/holon.py` for API behavior.
2. `dharma_swarm/holon_bridge.py` for identity loading, dialogue context, or safe provider resolution.
3. `dharma_swarm/holon_persistence.py` for normalized talk receipt shape.
4. `scripts/holon_talk.py` only for CLI-specific routing/output.
5. `tests/test_holon_bridge.py` for regression coverage.

For governed wake-cycle changes:

1. `dharma_swarm/holon_runtime.py`.
2. `dharma_swarm/holon_killswitch.py` or `dharma_swarm/holon_budget_guard.py` only if the gate primitive itself changes.
3. `dharma_swarm/holon_compass.py` only if the non-binding signal changes.
4. `dharma_swarm/holon_persistence.py` if cycle record shape changes.
5. `scripts/holon_run.py` only for the live CLI runner.
6. `tests/test_holon_runtime.py`.

For health, liveness, and operator cockpit changes:

1. `dharma_swarm/holon_service_liveness.py` for service heartbeat rules.
2. `dharma_swarm/holon_health.py` for `dgc agent status`.
3. `dharma_swarm/holon_canonical_state.py` for A2A-bus state projection.
4. `scripts/runtime/live_ops_census.py` for cockpit evidence aggregation.
5. `tests/test_holon_health.py` and `tests/test_holon_canonical_state.py`.

For runtime-truth projection changes:

1. `dharma_swarm/holon_truth_projection.py`.
2. `dharma_swarm/runtime_state.py` only if the underlying store contract changes.
3. Add focused tests around receipt projection and artifact binding; the required
   narrow command for this map does not include a projection test.

## What Future Agents Should Not Touch Unless Asked

- Do not edit `~/.dharma/agents/*/identity.json` or
  `~/.dharma/agents/*/prompt_variants/active.txt` to make tests pass.
- Do not delete, rename, or normalize directories in `~/.dharma/agents`,
  `~/.dharma/ginko/agents`, `~/.dharma/a2a/cards`, `~/.dharma/external_agents`,
  or `~/.dharma/a2a_bus` from a mapping task.
- Do not edit `~/.dharma/state/runtime.db` directly.
- Do not change `dharma_swarm/swarm.py` or `dharma_swarm/agent_runner.py` for a
  holon-specific talk/run fix unless the bug is proven to live in the generic
  swarm/task executor substrate.
- Do not use `api/routers/agents.py:/agents/{agent_id}/chat` as a substitute
  for `api/routers/holon.py:/holon/{name}/chat`.
- Do not weaken `holon_runtime.py` gate order. Kill and budget happen before
  work.
- Do not relabel `holon_compass.py` as enforcement. It is explicitly
  non-binding.
- Do not make tmux/process status a completion proof. It is liveness evidence.

## Duplicated, Stale, Or Name-Drifted Surfaces

Current drift visible from code and state inspection:

- `~/.dharma/agents` and `~/.dharma/ginko/agents` both contain agent-like
  identities. Holon code uses `~/.dharma/agents`; `AgentRegistry` defaults to
  `~/.dharma/ginko/agents`.
- A2A cards include hyphen/underscore duplicates such as `artha_cream.json` and
  `artha-cream.json`, `merge_master_mike.json` and `merge-master-mike.json`,
  `palantir_pilot.json` and `palantir-pilot.json`,
  `livelihood_loom_ceo.json` and `livelihood-loom-ceo.json`,
  `cybernetics_codex.json` and `cybernetics-codex.json`, plus other historical
  card aliases.
- `~/.dharma/agents` includes both `hermes_m5` and `hermes-m5`. The status
  command lists registered holons by identity-bearing directories, so name
  spelling matters.
- `scripts/holon_talk.py` writes compact receipts directly, while the API route
  uses `holon_persistence.append_talk_receipt` and writes normalized dialogue
  receipts. This is a receipt-shape split, not necessarily a bug.
- `api/routers/agents.py` has a generic agent chat route that looks similar to
  holon chat but is not the canonical own-model holon path.
- `scripts/runtime/live_ops_census.py` has a specialized
  `holon.codex_composer_l4` surface. It is valuable operator evidence for
  `codex_composer`, not a generic proof that every registered holon is healthy.
- Live status currently includes invalid provider-name fallback evidence for
  `sakana`. Fixing that belongs in identity/provider configuration or admission
  normalization, not in this code-map task.

## Verification Map

Required narrow verification command:

```bash
pytest tests/test_holon_bridge.py tests/test_holon_runtime.py tests/test_holon_health.py tests/test_holon_canonical_state.py -q
```

What those tests cover:

| Test file | Coverage |
| --- | --- |
| `tests/test_holon_bridge.py` | `load_holon` identity/prompt loading, provider coercion, real `opus_composer` load, provider creation, CLI talk routing fallback, `holon_reply` streaming, and outcome-claim guard utility |
| `tests/test_holon_runtime.py` | Kill before work, budget before work, normal cycle, compass non-blocking behavior, loop stop semantics, persistence side effects through the runtime path, and optional memory-context injection |
| `tests/test_holon_health.py` | Read-only `holon_status`, service liveness projection, kill reflection, compass counts, malformed identity degradation, deterministic health rows, and no side effects for missing holons |
| `tests/test_holon_canonical_state.py` | Canonical state projection from bridge heartbeat, semantic responder receipt, L4 service heartbeat/proof, safe state target checks, and preservation of unrelated existing fields |

Gaps not proven by that narrow command:

- It does not run a live model end-to-end through `dgc agent run`.
- It does not prove `~/.dharma/state/runtime.db` projection through
  `holon_truth_projection.py`.
- It does not prove generic `swarm.py`/`agent_runner.py` task execution.
- It does not prove every registered holon's service is alive.

## Minimal Decision Rules

- To talk to a holon, start at `api/routers/holon.py` or
  `scripts/holon_talk.py`, then follow `holon_bridge.py`.
- To run governed cycles, start at `scripts/holon_run.py`, then
  `holon_runtime.py`.
- To inspect health, start at `holon_health.py`, then
  `holon_service_liveness.py`.
- To inspect canonical fleet state, start at `holon_canonical_state.py`.
- To bind standalone holon proof into runtime truth, start at
  `holon_truth_projection.py`.
- To change generic agent task execution, use `agent_runner.py` and
  `swarm.py`; do not route holon-specific fixes there first.
