# Sarathi and Holon — Read This First

**Role:** Sarathi/Holon subsystem semantic and navigation canon. Its narrow
authority locks the terms, boundaries, and routes on this page; it does not own
live-state claims. Run `make onboard` and `make organism-status` for those.
Code, tests, receipts, enforced policy, and operator rulings remain the fact
owners named by
`docs/governance/CANONICAL_DOC_STACK.md:19-31,55-128`.

**Evidence baseline:** source at `origin/main` commit
`f3eb5b39759f4f6deae5f0562530d7ed38792458`, inspected 2026-08-03. The full
behavior-first census was measured at `9d792ceacef32a1698838dc01586ed90ecb93666`;
the only later agent-shell source change through this baseline was the inspection-only
Sarathi MCP addition (`dharma_swarm/mcp_server.py:134-169`). Reproduce with:

```bash
git diff --name-only \
  9d792ceacef32a1698838dc01586ed90ecb93666..f3eb5b39759f4f6deae5f0562530d7ed38792458 \
  | rg 'sarathi|holon|mcp|memory|context|agent_runner|persistent_agent|autonomous_agent|living_agent|cron|gateway|a2a|evolution|Docker|compose|pyproject|runtime_provider|tools'
# dharma_swarm/mcp_server.py
# docs/reports/hermes_persistent_agent_index_2026-08-01.md
# tests/test_mcp_server.py
```

## The 60-second answer

There is **not one integrated autonomous-agent shell today**. There are several
independent runtime families containing useful pieces. Sarathi is the intended
apex chief-of-staff seat, but its current repo body is a deterministic organ
package plus bounded runtime wrappers; it is not yet the persistent shell that
owns a turn from ingress through reply, memory, effects, and receipt
(`dharma_swarm/holon_system/sarathi/__init__.py:1-40`,
`dharma_swarm/holon_system/sarathi/plan.py:1-8`,
`scripts/runtime/sarathi_wake_daemon.py:22-31,51-57`).

The sovereign-holon runtime is the closest reusable substrate: it can load a
named identity and model, stream tool-disabled dialogue while writing
conversation/receipt/compass state, run bounded governed wake cycles, and
persist cycle records (`dharma_swarm/holon_bridge.py:1-16,106-168,358-401`,
`api/routers/holon.py:43-89`, `dharma_swarm/conversation_log.py:44-52,73-133`,
`dharma_swarm/holon_compass.py:41-54`,
`dharma_swarm/holon_runtime.py:1-18,53-80,222-283`). It does not call the Sarathi
planner, delegator, response sweep, or proof organs; the behavior-first census
proves those families are independent
(`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:78-89,230-259`).

The right consolidation is therefore **one Sarathi composition root over shared
owners**, not moving every agent-related implementation into one directory. The
tested add-first shape and the shared-file constraints are recorded at
`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:360-443,598-607`.

## Operator constraints captured for Sarathi

The operator's four constraints for this subsystem are recorded here together:

- **MUTABLE** — she can be changed, including by herself.
- **LIVES IN THE REPO** — her body is version-controlled source, not a sidecar.
- **CALLABLE BY ANY AGENT OR MODEL** — one stable, non-human-only invocation
  contract.
- **RUNS ANYWHERE** — the same core works on a local Mac and a conventional Linux
  VPS, with host adapters supplied by configuration rather than hard-coded paths.

No current surface satisfies all four simultaneously
(`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:261-304,445-486`).

## Locked vocabulary

Use these meanings in code, plans, prompts, and agent handoffs:

| Term | Meaning here | Boundary / evidence |
|---|---|---|
| **Persistent agent shell** | The whole long-lived product boundary: ingress, owned identity/context/memory, cognition, governed tools, reply, durable state, scheduler, evolution, and receipts. | The twelve measured element classes are enumerated at `docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:57-76`. |
| **Holon** | A reusable governed agent cell: sovereign enough to have its own identity/model/voice, but composable inside the wider organism. It is a substrate concept, not another name for Sarathi. | The current direct implementation loads `RunningHolon` from the shared agent home and model route (`dharma_swarm/holon_bridge.py:55-68,106-168`). |
| **Holon runtime** | The shared bridge/wake/persistence/kill/budget/compass code in the existing top-level modules. | `dharma_swarm/holon_runtime.py:1-18`; `dharma_swarm/holon_persistence.py:25-97`; `dharma_swarm/holon_killswitch.py:16-52`. |
| **`holon_system`** | A navigation/facade package over shared owners, plus the current Sarathi source package. It is not a second runtime body. | Its package contract says exactly that (`dharma_swarm/holon_system/__init__.py:1-12`); runtime leaves re-export the top-level owners (`dharma_swarm/holon_system/runtime/bridge.py:1-26`, `dharma_swarm/holon_system/runtime/wake_cycle.py:1-5`). |
| **Sarathi** | One specific repo-owned chief-of-staff holon/seat intended to compose the shared shell capabilities. | The current occupant is `dharma_swarm/holon_system/sarathi/` and exports planning, delegation, wake, proof, pulse, brief, roster, scoreboard, and snapshot APIs (`dharma_swarm/holon_system/sarathi/__init__.py:7-40`). |
| **Apex** | Sarathi's role/altitude in the organism. It is not a separate runtime, registry, memory store, or daemon. | The facade calls Sarathi an occupant (`dharma_swarm/holon_system/__init__.py:3-6`); the build folder is explicitly history, not an ecosystem-wide runtime owner (`docs/sarathi_apex_build/README.md:1-5`). |
| **Hermes Agent** | An external agent implementation optionally loaded from `external/hermes-agent`; it is an integration/comparison lane, not Sarathi's repo-owned body. | `dharma_swarm/build_engine.py:25,69-107`. |
| **OpenClaw** | A parallel external/fleet runtime whose config/VM is observed by Dharma tooling. It is not a source package for Sarathi. | `dharma_swarm/terminal_commands/_status_helpers.py:281-309`; `scripts/runtime/live_ops_census.py:630-645`. |

Do not use “Sarathi,” “Holon,” “Apex,” “Hermes,” and “OpenClaw” as synonyms.

## What exists today

The current Sarathi **source capability** is **GENESIS SOURCE / OPTIONAL
INSPECTION ADAPTER**, not a durable agent shell and not proof that an MCP process
is callable or live. The two MCP handlers currently return status and roster
before generic swarm bootstrap (`dharma_swarm/mcp_server.py:134-169`). Their test
is structural/source-level rather than a live protocol probe
(`tests/test_mcp_server.py:240-315`); `run_mcp_stdio.py:1-27` is the launcher, and
MCP remains an optional install extra (`pyproject.toml:33-36`). The canonical
organ snapshot continues to publish `wake_loop_active=false` and
`alive_claim=false`
(`dharma_swarm/holon_system/sarathi/gateway.py:15-25`).

| Element | Current Sarathi-owned state | Shared/adjacent implementations to evaluate or adapt | Verdict |
|---|---|---|---|
| Gateway / ingress | Python snapshot plus MCP `sarathi_status`/`sarathi_roster` are observation surfaces; neither accepts a message or sends a conversational reply (`dharma_swarm/mcp_server.py:134-169`). | Generic holon HTTP, A2A, NATS/mailbox, Telegram, and dashboard gateways (`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:63,80-89`). | **UNWIRED** |
| Memory | No episodic or semantic store is imported by the package or wrappers. | MemoryKernel and several legacy/independent stores (`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:64,91-97`). | **UNWIRED** |
| Context | Caller-injected `BootPack`; no per-turn compiler or retrieval (`dharma_swarm/holon_system/sarathi/plan.py:22-38`). | `ContextCompiler`, MemoryKernel compilers, legacy context, and optional holon pack (`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:65,99-108`). | **UNWIRED** |
| Persistence / database | Mailbox, briefs, reports, spend file, and holon JSONL are separate file projections (`scripts/runtime/sarathi_wake_daemon.py:225-312,373-380`; `dharma_swarm/holon_runtime.py:45-50,217-219`; `dharma_swarm/holon_persistence.py:25-60`). | RuntimeState, TaskBoard/Stigmergy, memory-plane SQLite, and holon persistence (`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:66,110-119`). | **PARTIAL** |
| Compute host | Two bounded Python commands; the wake wrapper tells an outside scheduler to invoke it (`scripts/runtime/sarathi_wake_daemon.py:51-57`). | Organism containers, cron, tmux wake, launchd, and operator daemons (`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:67,121-125`). | **UNWIRED** |
| Cognition | The planner is explicitly model-free and the wrapper runs `invoker=None` (`dharma_swarm/holon_system/sarathi/plan.py:1-8`; `scripts/runtime/sarathi_wake_daemon.py:22-31`). | AgentRunner/provider stack, direct holon streaming, and other model callers (`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:68,127-131`). | **UNWIRED** |
| Tools / effectors | Delegation can enqueue a file task or use a caller-injected invoker; no consumer/effect runner is bound (`dharma_swarm/holon_system/sarathi/delegate.py:268-337`). | AgentRunner tools, AutonomousAgent, API tools, browser agent, Living Agent Kernel, roaming workers (`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:69,133-144`). | **UNWIRED** |
| Identity / persona | Static roster and status metadata; no version-controlled Sarathi persona/card is loaded per turn. | `RunningHolon`, AgentRegistry, execution identity, A2A registries, and wake profiles (`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:70,146-157`). | **UNWIRED** |
| Scheduler / heartbeat | No standing scheduler targets the Sarathi organs; the direct wrapper is fixed-cycle (`scripts/runtime/sarathi_wake_daemon.py:51-57,363-393`). | Cron, PersistentAgent, tmux Composer, garden, organism, A2A, and workflow loops (`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:71,159-165`). | **UNWIRED** |
| Evolution / self-modification | No Sarathi evolution entrypoint or promotion path. | Darwin, self-improve, DGM, AutoResearch, BuildEngine, custodians, Ginko, and Forge are independent candidates, not approved adapters (`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:72,167-180`). | **UNWIRED** |
| Governance | Reversibility classification and autonomy dial are called; execution-lease and transitive-budget guarantees are incomplete (`dharma_swarm/holon_system/sarathi/delegate.py:195-266,298-326`). | Shared authority, kill/budget, policy, and evolution-safety owners (`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:73,182-202`). | **PARTIAL** |
| Observability / receipts | Briefs, outcome ledgers, task/invoke refs, daemon reports, and proof evaluation exist, but they do not establish one end-to-end turn identity (`dharma_swarm/holon_system/sarathi/wake.py:89-164`; `scripts/runtime/sarathi_wake_daemon.py:273-312`). | Holon JSONL, RuntimeState/AgentRunner receipts, and generic wake receipts (`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:74,204-228`). | **PARTIAL** |

“Adjacent” does not mean safe to reuse. AutoResearch writes source directly,
BuildEngine can stash/clean/commit, and custodians can commit before their merge
gate (`dharma_swarm/autoresearch_loop.py:434-487,548-604`,
`dharma_swarm/build_engine.py:166-244,267-310,524-532`,
`dharma_swarm/custodians.py:358-428,605-655`). Any evolution adapter needs a
separate authority and promotion review.

## The runtime families — keep them conceptually separate

These are ingredients or parallel shells, not aliases for one implementation:

| Family | Real body / entrypoints | Relationship to Sarathi |
|---|---|---|
| **Sarathi organs** | `dharma_swarm/holon_system/sarathi/`; bounded wrappers in `scripts/runtime/sarathi_wake_daemon.py` and `scripts/runtime/sarathi_proof_window.py`; inspection-only MCP handlers in `dharma_swarm/mcp_server.py:134-169`, launched conditionally by `run_mcp_stdio.py:1-27`. | The seat-specific source. This is what must become the composition root. |
| **Sovereign-holon direct runtime** | `dharma_swarm/holon_bridge.py`, `dharma_swarm/holon_runtime.py`, `dharma_swarm/holon_persistence.py`, `dharma_swarm/holon_health.py`, `dharma_swarm/holon_killswitch.py`, `dharma_swarm/holon_budget_guard.py`, `dharma_swarm/holon_compass.py`; generic HTTP at `api/routers/holon.py:43-89`; generic CLI at `dharma_swarm/dgc_cli.py:629-669`. | Closest reusable Holon substrate. It is shared and does not traverse Sarathi organs. |
| **Swarm / AgentRunner** | `dharma_swarm/swarm.py`, `dharma_swarm/orchestrator.py`, `dharma_swarm/agent_runner.py`, providers, tools, and task board. `AgentRunner` begins at `dharma_swarm/agent_runner.py:1682`. | Mature shared cognition/tool path; currently independent of Sarathi. |
| **Packaged organism service** | `dharma_swarm/orchestrate_live.py:2281-2368,2416-2483` supervises many loops; it is the Docker CMD (`Dockerfile.swarm:39-40`), Compose swarm service (`docker-compose.yml:78-118`), and macOS launchd body (`com.dharma.swarm.plist:13-39`). | Real cross-host organism host, but not a Sarathi service. Its host adapters remain separate. |
| **Dashboard/API tool shell** | Model tool calls reach filesystem, shell, swarm, and evolution effectors through `api/routers/chat.py:1025-1062` and `api/chat_tools.py:1-5,54-437,749-773`; routes mount at `api/main.py:602-609`. | Independent operator-facing model/effect path; not AgentRunner and not wired to Sarathi. |
| **PersistentAgent + AutonomousAgent** | `PersistentAgent` at `dharma_swarm/persistent_agent.py:117` with its loop at `dharma_swarm/persistent_agent.py:580-625`; `AutonomousAgent` at `dharma_swarm/autonomous_agent.py:386`. | Another persistent/agentic body used by conductors; not the Sarathi turn path. |
| **Living Agent Kernel** | `LivingAgentKernel` at `dharma_swarm/operator_core/living_agent_kernel.py:1199`, its governed tool-plan/effect boundary at `dharma_swarm/operator_core/living_agent_kernel.py:2322-2785`, daemon service at `dharma_swarm/operator_core/living_agent_kernel_service.py:39-134`, and provider worker at `dharma_swarm/operator_core/living_agent_kernel_provider_worker.py:501-539`. | Shared governance/effect substrate with separate process bodies. It must constrain Sarathi, not be copied into the seat. |
| **Composer wake/responder** | Sarathi is one `WakeProfile` in `scripts/runtime/codex_composer_wake_loop.py:129-136`; the standing path is tmux-oriented at `scripts/runtime/codex_composer_wake_loop.py:1178-1261`. | A generic supervisor/status profile. Naming a profile `sarathi` does not wire the Sarathi organs. |
| **Cron and garden daemons** | Seven `dharma_swarm/cron_*.py` modules (`dharma_swarm/cron_scheduler.py:337-448`; `dharma_swarm/cron_daemon.py:35-136`; `dharma_swarm/cron_runner.py:123-186,856-940`) plus `garden_daemon.py:337-353`. | Independent schedulers/model subprocess loops; neither is Sarathi's service. |
| **Ginko scheduler** | `dharma_swarm/ginko_cron_loop.py:1-9,41-65`, mounted as its own Compose service at `docker-compose.yml:120-133`. | A separately wired evolution scheduler, not one of the seven cron modules and not Sarathi. |
| **Merge Master Mike daemon** | `scripts/runtime/merge_master_mike_daemon.py:685-706`; wake/status/cycle/tmux commands at `Makefile:602-618`. | Independent persistent merge-control loop with its own authority lane. |
| **GitHub scheduled effectors** | Scheduled workflows include `.github/workflows/loop-watcher.yml:14-16,158-195`, `.github/workflows/active-track.yml:27-29,494`, `.github/workflows/automerge.yml:45-46,152-330`, `.github/workflows/pr-dedupe.yml:48-49,140-142,222-223`, and `.github/workflows/stale-pr.yml:16-17,60-150`. | Cloud-only schedulers/mutators; production surfaces, but neither portable core nor Sarathi. |
| **Legacy/operator loops** | `agent_loop.sh:16-61`, `swarm.sh:73-103`, `run_overnight.sh:29-81`, `deep_reading_daemon.py:499-519`, and `garden_daemon.py:337-353`. | Host-oriented independent loops retained in the census; not consolidation targets by default. |
| **A2A and gateways** | `dharma_swarm/a2a/`, `dharma_swarm/gateway/`, roaming mailbox/pollers, and API routes (`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:80-89`). | Transport candidates. A transport without one Sarathi turn handler is not the shell. |
| **Memory and context** | `dharma_swarm/memory_kernel/`, `dharma_swarm/context_compiler.py`, memory-plane stores, and legacy stores (`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:91-108`). | Shared state services. Sarathi needs adapters and one ownership policy, not another store. |
| **Provider/model routing** | Operational contract in `docs/ops/MODEL_KEY_ROUTING.md:9-24`; architecture index in `docs/architecture/MODEL_ROUTING_CANON.md`; the separate Composer Sarathi profile resolves at `scripts/runtime/codex_composer_wake_loop.py:90-101`. | Shared provider owners plus a profile-specific resolver; canonical Sarathi organs do not call either today. |
| **Evolution families** | Guarded Darwin, SelfImprove, DGM, AutoResearch, BuildEngine, custodians, Ginko, and Forge (`dharma_swarm/evolution.py:2357-2424,3245-3508`; `dharma_swarm/self_improve.py:233-254,373-432`; `dharma_swarm/dgm_loop.py:351-400,636-759`; `docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:169-180`). | Independent mutation/proposal systems with different safety boundaries. Sarathi has no approved self-modification adapter today. |
| **Hermes / OpenClaw** | Optional external Hermes checkout and observed OpenClaw config/VM (`dharma_swarm/build_engine.py:25,72-107`; `scripts/runtime/live_ops_census.py:630-645`). | Comparators/integrations/parallel products. Never use their sidecar state as Sarathi's repo-owned body. |

The behavior-first independence commands and importer evidence are preserved in
`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:230-259,391-443`.

## Target composition boundary

This is a semantic/design guardrail, not proof of an accepted implementation
spec. A future `dharma_swarm/sarathi/` directory should own the seat, contracts,
and adapters—not shared engines:

```text
Python / HTTP / MCP / A2A-NATS / CLI
                    |
          handle_turn(TurnEnvelope)              MISSING
                    |
       versioned Sarathi identity/persona        MISSING
                    |
       context + memory adapters                 MISSING
                    |
       provider/model cognition                  MISSING
                    |
  gate + validated lease + budget + kill         PARTIAL
                    |
       shared effectors / sub-holons             UNWIRED
                    |
 reply + episodic write + correlated receipt     MISSING
                    |
 portable supervisor + gated evolution           MISSING
```

`handle_turn` must be the one implementation mounted behind every transport;
adapters may authenticate, serialize, or stream, but must not create their own
prompt/model/agent. The proposed transport-neutral envelope and receipt fields
are recorded at `docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:445-464`.

Shared owners stay shared and outside the Sarathi seat. Their physical paths may
change only through a separately admitted, atomic runtime-wide migration. The
detailed move/keep matrix, active-track constraints, importer counts, and
executed move simulations are at
`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:352-443`. That August 2 census
supersedes the August 1 plan's proposed Sarathi destination moves; retain the
older plan only for its reproduced eager-import hazard and move probes
(`docs/plans/HOLON_CONSOLIDATION_PLAN_2026-08-01.md:18-40,69-89`).

This documentation canon grants no implementation admission. The census found
no active owned surface for the canonical Sarathi package/runtime leaves; open
or coordinate a current track before implementation
(`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:381-389`).

## What “any agent or model can call Sarathi” means

It means a caller with a versioned envelope can submit a message/task without a
human terminal, checkout-specific Python knowledge, or a home-directory persona;
the same turn ID follows acceptance, context, model attempt, effects, reply,
memory write, budget, and receipt. Callability grants no effect authority: the
consumer still validates a permit immediately before acting
(`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:445-464`).

| Surface now | What it really offers | Verdict |
|---|---|---|
| Python package | Direct imports of `build_plan`, `delegate_all`, `run_wake_unit`, `gateway_snapshot`, and related organs (`dharma_swarm/holon_system/sarathi/__init__.py:7-40`). | Best implementation API; not a transport-neutral agent call. |
| MCP | `sarathi_status` and `sarathi_roster` return projections before swarm bootstrap (`dharma_swarm/mcp_server.py:134-169`); `run_mcp_stdio.py:1-27` launches the generic server only when the optional MCP dependency is installed. Current tests inspect the source/AST rather than construct a live server (`tests/test_mcp_server.py:265-315`). | **Closest inspection adapter source, not reproduced callability.** No message, reply, or action; installation and deployment are not implied. |
| HTTP | Mounted `POST /holon/{name}/chat` loads a sidecar identity and streams the generic holon's model while writing conversation and compass state (`api/routers/holon.py:43-89`; `api/main.py:577-580`). | Closest generic dialogue transport; tool-disabled, not read-only, and not connected to Sarathi organs. |
| CLI | Generic `dgc agent talk/run/status/kill` plus direct Sarathi runtime scripts (`dharma_swarm/dgc_cli.py:629-669`; `scripts/runtime/sarathi_wake_daemon.py:51-57`). The talk/run handlers import top-level `scripts` (`dharma_swarm/terminal_commands/agents.py:101-127`) even though packaging excludes `scripts*` (`pyproject.toml:58-64`). | Human/checkout oriented and not a stable packaged cross-agent surface. |
| A2A / NATS | Several task/mailbox transports exist, but none consumes a Sarathi turn (`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:80-89`). | Transport substrate only. |

There is therefore no usable full-call surface today. MCP is the closest
inspection adapter contract in source; generic Holon HTTP is the closest
dialogue transport; neither is Sarathi the persistent shell.

## Target truth ladder — never promote prose into liveness

Use these claim types in reviews, status APIs, and future tests:

| Claim type | Minimum proof | Current Sarathi |
|---|---|---|
| `SourcePresent` | Versioned code imports and its focused tests pass. | **YES** |
| `AdapterSourcePresent` | A non-human adapter is versioned and structurally tested. | **YES — optional MCP status/roster source** |
| `CallableReadOnly` | A running non-human protocol adapter returns an honest projection without effects in a reproduced supported environment. | **NOT PROVEN** |
| `EffectBound` | One turn handler reaches cognition and an effector through validated authority, then returns correlated effect/reply/memory receipts. | **NO** |
| `DurableServiceProven` | Restart survival plus real message→reply→memory/effect proof under both Mac and Linux/VPS supervisors, with kill and budget witnesses. | **NO** |

The **target rule** is that only `DurableServiceProven` may imply `alive=true`.
A PID, tmux session, heartbeat, profile, MCP response, source import, or
synthetic cycle proves a narrower claim only. The canonical Sarathi organs and
direct wrapper keep both liveness booleans false
(`dharma_swarm/holon_system/sarathi/gateway.py:15-25`;
`scripts/runtime/sarathi_wake_daemon.py:296-305`), but enforcement is not there:
the current generic proof helper allows `alive_claim_allowed` from only sprawl +
wake booleans (`dharma_swarm/holon_system/observability/proof_gates.py:6-11`).
The separate Composer profile can derive `wake_loop_active=true` from a successful
tmux `send-keys`; that is supervisor/process evidence only
(`scripts/runtime/codex_composer_wake_loop.py:1217-1261`).

## One document map

Start here, then follow only the lane needed:

| Need | Read / inspect | Authority role |
|---|---|---|
| Names, boundaries, current high-level composition | **This file** | Narrow Sarathi/Holon subsystem semantic and navigation canon. |
| Executable truth | `dharma_swarm/holon_system/sarathi/`, shared modules named above, and `tests/test_sarathi_*.py`, `tests/test_holon_*.py`, `tests/test_mcp_server.py` | Code/tests win over prose. |
| What is live now | `make onboard`, `make organism-status`, `docs/state/LIVE_OPS_DASHBOARD.md` | Live-state owners; this page makes no liveness claim. |
| Exhaustive twelve-element evidence | [`reports/SARATHI_SHELL_CENSUS_2026-08-02.md`](reports/SARATHI_SHELL_CENSUS_2026-08-02.md) | Dated behavior-first report; read its post-census MCP update. |
| Consolidation decision | [`reports/SARATHI_SHELL_CENSUS_2026-08-02.md`](reports/SARATHI_SHELL_CENSUS_2026-08-02.md) §4, with [`plans/HOLON_CONSOLIDATION_PLAN_2026-08-01.md`](plans/HOLON_CONSOLIDATION_PLAN_2026-08-01.md) retained for move probes | The later census supersedes the older plan's destination moves; no moves occurred. |
| Autonomy authority | [`ops/OPERATOR_RULING_2026-07-30_SARATHI_AUTONOMY_CEILING.md`](ops/OPERATOR_RULING_2026-07-30_SARATHI_AUTONOMY_CEILING.md) and enforced policy/code | Ruling plus executable gate/dial; implementation wins on conflict (`docs/ops/OPERATOR_RULING_2026-07-30_SARATHI_AUTONOMY_CEILING.md:11-18,71-92`). |
| Deep July body narrative | [`architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md`](architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md) | Dated reference, superseded as the orientation/current-count owner. |
| Quick direct-holon call chains | [`architecture/AGENT_HOLON_CODE_MAP.md`](architecture/AGENT_HOLON_CODE_MAP.md) | Subordinate code index, not a liveness verdict. |
| Proposed cross-runtime descriptor | [`architecture/PERSISTENT_AGENT_DESCRIPTOR.md`](architecture/PERSISTENT_AGENT_DESCRIPTOR.md) | Draft proposal with mandatory errata; nothing reads it at runtime (`docs/architecture/PERSISTENT_AGENT_DESCRIPTOR.md:9-33`). |
| Model/provider/key routing | [`ops/MODEL_KEY_ROUTING.md`](ops/MODEL_KEY_ROUTING.md) and [`architecture/MODEL_ROUTING_CANON.md`](architecture/MODEL_ROUTING_CANON.md) | Operational contract plus architecture index; the separate Composer profile resolver is `scripts/runtime/codex_composer_wake_loop.py:90-101`. |
| Sarathi intent and build sequence | [`sarathi_apex_build/README.md`](sarathi_apex_build/README.md), especially [`05_SARATHI_APEX_MAP.md`](sarathi_apex_build/05_SARATHI_APEX_MAP.md) | Build history and seat vision, not current runtime truth. |
| June sovereign-holon research/design | [`sovereign_holons/README.md`](sovereign_holons/README.md) | Historical corpus. |
| Wider persistent-agent inventory | [`reports/hermes_persistent_agent_index_2026-08-01.md`](reports/hermes_persistent_agent_index_2026-08-01.md) | Partial report with a mandatory errata block at `docs/reports/hermes_persistent_agent_index_2026-08-01.md:7-51`. |
| Autonomy build request | [`prompts/SARATHI_AUTONOMY_BUILD_2026-07-30.md`](prompts/SARATHI_AUTONOMY_BUILD_2026-07-30.md) | Historical build prompt, not proof of delivery. |
| Wider organism vision | [`vision_maps/MASTER_2026-06-10_anatomy_altitude_integration.md`](vision_maps/MASTER_2026-06-10_anatomy_altitude_integration.md) and [`MASTER_2026-06-10_leverage_synthesis.md`](vision_maps/MASTER_2026-06-10_leverage_synthesis.md) | Vision/research context, not source or live state. |

## Navigation and change guardrails

1. Read this page before any Sarathi/Holon/persistent-shell change.
2. Search by behavior, not names. The reproducing sweep is at
   `docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:39-55`.
3. Do not create another registry, memory store, provider router, scheduler, or
   receipt type merely to make Sarathi look complete. Adapt the selected shared
   owner through one composition root.
4. Do not call a profile, process, heartbeat, source package, or read-only MCP
   tool a living agent. Use the truth ladder above.
5. Any PR changing the meaning of Sarathi/Holon, adding an invocation surface,
   or promoting a truth-ladder claim must update this file and add executable
   proof at the promoted boundary.
6. Any physical consolidation must follow add-first compatibility staging and
   keep the repository importable at every intermediate commit
   (`docs/reports/SARATHI_SHELL_CENSUS_2026-08-02.md:427-443`).

## Fast verification

```bash
# The canonical subject doorway and all primary targets exist.
test -e docs/SARATHI.md
test -e dharma_swarm/holon_system/sarathi/__init__.py
test -e dharma_swarm/holon_bridge.py
test -e dharma_swarm/holon_runtime.py

# Current Sarathi exports and honest liveness projection. Project requires 3.11+.
SARATHI_PYTHON="${SARATHI_PYTHON:-python3.11}"
"$SARATHI_PYTHON" -c 'import sys; assert sys.version_info >= (3, 11)'
"$SARATHI_PYTHON" - <<'PY'
from dharma_swarm.holon_system import sarathi
snapshot = sarathi.gateway_snapshot()
assert snapshot["wake_loop_active"] is False
assert snapshot["alive_claim"] is False
print(sorted(sarathi.__all__))
PY

# Prove the direct package/wrappers do not already wire the missing shared systems.
! rg -n 'memory_kernel|context_compiler|AgentMemory|runtime_provider|AgentRunner|AutonomousAgent|evolution|self_improve|dgm_loop|a2a|nats|FastAPI|APIRouter' \
  dharma_swarm/holon_system/sarathi \
  scripts/runtime/sarathi_wake_daemon.py \
  scripts/runtime/sarathi_proof_window.py

# Focused current contracts, including the post-census MCP surface.
"$SARATHI_PYTHON" -m pytest -q \
  tests/test_sarathi_plan.py \
  tests/test_sarathi_delegate.py \
  tests/test_sarathi_wake.py \
  tests/test_sarathi_proof.py \
  tests/test_sarathi_wake_daemon.py \
  tests/test_sarathi_proof_window.py \
  tests/test_holon_system_imports.py \
  tests/test_mcp_server.py
```
