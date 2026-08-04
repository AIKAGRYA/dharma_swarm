# Persistent Agents, Holons, and Sarathi — Start Here

**Status:** durable subsystem navigation reference; not a live-state or
completion authority

**Updated:** 2026-08-04

**Implementation contract:**
[`SARATHI_COMPOSITION_ROOT_P0.md`](SARATHI_COMPOSITION_ROOT_P0.md)

**Build history:** [`BUILD_LINEAGE.md`](BUILD_LINEAGE.md)

This is the single discovery point for the repo's persistent-agent work. Code,
tests, enforced policy, receipts, and operator rulings win over this page. The
older design folders remain evidence and history; they are indexed here so an
agent does not mistake one of them for a second product root.

## The direct answer

- **One place to start:** this file.
- **One public Sarathi product root:**
  [`dharma_swarm/sarathi/`](../../dharma_swarm/sarathi/).
- **One physical folder containing every agent subsystem:** no. Shared Holon,
  memory, provider, transport, scheduler, governance, and tool engines remain
  with their existing owners and will be reached through adapters when wired.
- **One finished Hermes/OpenClaw-class agent today:** no. The P0 root closes one
  real message → cognition → reply → receipt path and fails closed on effects;
  transports, memory retrieval, tools, heartbeat, and self-modification remain
  follow-on work
  ([P0:34-59](SARATHI_COMPOSITION_ROOT_P0.md#L34-L59)).

The organizing decision is therefore **one composition root, not one giant
directory and not another substrate**. This is also the anti-fork rule recorded
by the June Holon work: do not create another agent system, registry, daemon, or
memory store
([sovereign Holon README:77-83](../sovereign_holons/README.md#L77-L83)).

## What the names mean

| Term | Use this meaning | Do not use it to mean |
|---|---|---|
| **Persistent agent shell** | The complete long-lived product: ingress, identity, context, memory, cognition, governed effects, reply, persistence, wake, evolution, and receipts. | A workflow, dispatcher, profile, cron job, or PID. |
| **Holon** | A reusable governed agent cell with its own identity/model/voice that can participate in the wider organism. | A synonym for Sarathi. |
| **Holon runtime** | Shared bridge, wake, persistence, health, kill, budget, and compass implementations. | A complete chief-of-staff shell. |
| **`holon_system`** | The landed facade/navigation family plus legacy Sarathi organs. Its own package says the substrate remains elsewhere ([source:1-12](../../dharma_swarm/holon_system/__init__.py#L1-L12)). | The new public product boundary. |
| **Sarathi** | The repo-owned, mutable persistent-agent product and chief-of-staff seat. | Every autonomous loop in the repository. |
| **Apex** | Sarathi's role in the organism. | A separate runtime, store, registry, or daemon. |
| **Hermes / OpenClaw** | External comparators and integration lineages that clarify the intended product class. | Sarathi's source body or runtime state. |

## The one-root architecture

```text
Python now; HTTP / MCP / A2A / CLI later
                    |
                    v
          dharma_swarm.sarathi
       one handle_turn(request) contract
                    |
        narrow, dependency-injected adapters
          /       |        |        \
         v        v        v         v
      Holon    providers  Runtime   governance
      organs              State     and effects
```

The package root owns the stable turn contract, version-controlled identity,
composition, and result/receipt semantics. Shared modules must not import back
into it. Every future transport should be a thin caller of the same
`handle_turn`; a transport must not grow another Sarathi prompt, model loop, or
memory store
([P0:98-107](SARATHI_COMPOSITION_ROOT_P0.md#L98-L107)).

The stable Python direction is:

```python
from dharma_swarm.sarathi import SarathiTurnRequest, handle_turn

result = await handle_turn(
    SarathiTurnRequest(message="What needs attention?", caller_id="agent-name")
)
```

`caller_id` is mandatory because it is part of the durable-memory ownership
key; two callers using the same `session_id` must not see each other's history.

Importing the package must not start a provider, subprocess, socket, loop, or
state directory. The exact public types and negative controls are part of the
active P0 contract
([P0:61-96](SARATHI_COMPOSITION_ROOT_P0.md#L61-L96)).

## Code map: product versus ingredients

| Role | Exact code home | Relationship to the one root |
|---|---|---|
| **Sarathi product root** | [`dharma_swarm/sarathi/`](../../dharma_swarm/sarathi/) | **CURRENT BRANCH:** the sole public composition boundary. Its inert exports are defined at [`__init__.py:1-38`](../../dharma_swarm/sarathi/__init__.py#L1-L38); the turn path is [`shell.py:102-233`](../../dharma_swarm/sarathi/shell.py#L102-L233). It is additive and does not replace shared engines. |
| **Legacy Sarathi organs** | [`dharma_swarm/holon_system/sarathi/`](../../dharma_swarm/holon_system/sarathi/) | Landed planning, delegation, wake, proof, brief, pulse, roster, and inspection projections. Preserve compatibility; adapt selectively. Its package explicitly withholds liveness claims ([source:1-5](../../dharma_swarm/holon_system/sarathi/__init__.py#L1-L5)). |
| **Bounded Sarathi wake command** | [`scripts/runtime/sarathi_wake_daemon.py`](../../scripts/runtime/sarathi_wake_daemon.py) | Landed fixed-cycle runtime wrapper, not the portable product root or a standing service. It calls the organ wake path and Holon wake cycle ([source:363-393](../../scripts/runtime/sarathi_wake_daemon.py#L363-L393)). |
| **Direct Holon substrate** | [`holon_bridge.py`](../../dharma_swarm/holon_bridge.py), [`holon_runtime.py`](../../dharma_swarm/holon_runtime.py), [`holon_persistence.py`](../../dharma_swarm/holon_persistence.py), [`holon_health.py`](../../dharma_swarm/holon_health.py), [`holon_killswitch.py`](../../dharma_swarm/holon_killswitch.py), [`holon_budget_guard.py`](../../dharma_swarm/holon_budget_guard.py), [`holon_compass.py`](../../dharma_swarm/holon_compass.py) | Shared named-agent dialogue and governed wake ingredients. The defined wake order begins at [`holon_runtime.py:53`](../../dharma_swarm/holon_runtime.py#L53). |
| **Classic persistent actor** | [`persistent_agent.py`](../../dharma_swarm/persistent_agent.py) + [`autonomous_agent.py`](../../dharma_swarm/autonomous_agent.py) | Landed independent shell lineage: wake loop, mini-cron, memory, ReAct, and host tools ([persistent actor:117-175](../../dharma_swarm/persistent_agent.py#L117-L175), [loop:580-625](../../dharma_swarm/persistent_agent.py#L580-L625), [brain:386-423](../../dharma_swarm/autonomous_agent.py#L386-L423)). It is not silently renamed Sarathi. |
| **Living Agent Kernel** | [`dharma_swarm/operator_core/living_agent_kernel*.py`](../../dharma_swarm/operator_core/) | Shared durable wake/lease/closeback/tool/proof family; `LivingAgentKernel` begins at [`living_agent_kernel.py:1199`](../../dharma_swarm/operator_core/living_agent_kernel.py#L1199). It is an ingredient, not a second Sarathi root. |
| **Structured state** | [`runtime_state.py`](../../dharma_swarm/runtime_state.py) | Shared SQLite state and receipt spine; `RuntimeStateStore` begins at [`:1209`](../../dharma_swarm/runtime_state.py#L1209). P0 must reuse it, not invent a Sarathi database. |
| **Memory and context** | [`memory_kernel/`](../../dharma_swarm/memory_kernel/) + [`context_compiler.py`](../../dharma_swarm/context_compiler.py) | Shared retrieval/context ingredients. They are deferred adapters in P0, not claims of current Sarathi memory ownership. |
| **Read-only MCP projection** | [`mcp_server.py:134-169`](../../dharma_swarm/mcp_server.py#L134-L169) | Landed `sarathi_status` and `sarathi_roster`; they do not accept a message or dispatch work. Future conversational MCP must call the product root. |
| **Swarm execution** | [`swarm.py`](../../dharma_swarm/swarm.py), [`orchestrator.py`](../../dharma_swarm/orchestrator.py), [`agent_runner.py`](../../dharma_swarm/agent_runner.py) | Shared multi-agent task execution. It remains independent until an admitted adapter is proven. |
| **Adjacent autonomous runtimes** | [`orchestrate_live.py`](../../dharma_swarm/orchestrate_live.py), the seven `cron_*.py` modules ([runner](../../dharma_swarm/cron_runner.py)), and root [`garden_daemon.py`](../../garden_daemon.py) | Independent supervisors/runners, not hidden Sarathi bodies. `garden_daemon.py` spawns a subprocess at [`:216`](../../garden_daemon.py#L216) and loops at [`:340`](../../garden_daemon.py#L340); the cron runner calls the provider stack at [`:464`](../../dharma_swarm/cron_runner.py#L464). Inventory them by behavior, but do not move or rename them as Sarathi. |

## Current truth, without aspiration leakage

Use these labels in agent handoffs:

| Label | Meaning |
|---|---|
| **LANDED** | The cited commit is an ancestor of `origin/main`. |
| **CURRENT BRANCH** | Present on the active P0 branch but not yet on `origin/main`; not product truth until merged. |
| **UNMERGED / PARALLEL** | Exists in another Git ref or PR but is not an ancestor of `origin/main`; inspect, do not silently depend on it. |
| **ASPIRATION** | Intended design or deferred adapter without an implemented, tested path. |

The detailed commit-by-commit classification is in
[`BUILD_LINEAGE.md`](BUILD_LINEAGE.md). In particular:

- `dharma_swarm/holon_system/sarathi/`, the bounded wake daemon, and read-only
  MCP inspection are **LANDED**.
- the P0 composition root is **CURRENT BRANCH** until its PR lands;
- memory recall work on `origin/claude/sarathi-autonomy-build-vyr998` and the
  August behavior census/navigation branch are **UNMERGED / PARALLEL**;
- portable transports, governed tool execution, heartbeat, and
  self-modification are **ASPIRATION** under the current P0.

No identity file, profile, pulse, process, tmux session, or model response proves
that Sarathi is alive. The legacy status projection deliberately returns
`wake_loop_active=false` and `alive_claim=false`
([gateway.py:15-25](../../dharma_swarm/holon_system/sarathi/gateway.py#L15-L25)).

## Product constraints

The product is being built to satisfy four operator constraints:

1. **Mutable** — behavior and identity live in version-controlled source and may
   evolve through governed changes.
2. **Lives in the repo** — repo source is the body; `~/.dharma` is runtime state,
   not the definition of Sarathi.
3. **Callable by any agent or model** — one ingress-neutral turn contract sits
   behind every transport; callability does not grant effect authority.
4. **Runs anywhere** — the core accepts configured state/provider dependencies;
   Mac launchd, Linux services, containers, or other supervisors remain host
   adapters rather than assumptions in the core.

P0 is scoped to prove only the repo body and Python composition seam. A full
portability claim requires the same message/restart/receipt checks under both
Mac and Linux supervisors; that proof is not implied by this page.

On the current branch, the tracked identity/persona is source
([`identity.py:41-57`](../../dharma_swarm/sarathi/identity.py#L41-L57)); cognition
uses the repository provider route while excluding agentic CLI and explicitly
paid providers until a budget adapter exists
([`runtime_provider.py:38-121`](../../dharma_swarm/sarathi/adapters/runtime_provider.py#L38-L121));
turn history and receipts reuse `RuntimeStateStore`
([`runtime_state.py:20-166`](../../dharma_swarm/sarathi/adapters/runtime_state.py#L20-L166));
and every requested/model-proposed effect is blocked because P0 has no effect
adapter ([`shell.py:58-72`](../../dharma_swarm/sarathi/shell.py#L58-L72)).
Durable history is scoped by required `caller_id` plus normalized `session_id`,
and an assistant reply is reloaded only when its correlated completion receipt
exists.

## Document map

| If you need… | Read this | Authority / caveat |
|---|---|---|
| The current implementation boundary | [`SARATHI_COMPOSITION_ROOT_P0.md`](SARATHI_COMPOSITION_ROOT_P0.md) | Active build contract; explicitly not a completeness claim. |
| How months of work fit together | [`BUILD_LINEAGE.md`](BUILD_LINEAGE.md) | Dated, evidence-backed history report. |
| The March one-organism / cross-harness doctrine | [`roaming-control-plane-spec.md`](../plans/2026-03-26-roaming-control-plane-spec.md), [`self-evolving-organism-master-build-spec.md`](../plans/2026-03-26-self-evolving-organism-master-build-spec.md), and [`living-agent-roaming-onboarding-architecture.md`](../plans/2026-03-26-living-agent-roaming-onboarding-architecture.md) | Landed intent: OpenClaw, Hermes, local/VPS agents, one shared identity/task/runtime/memory/governance plane, and no shadow runtime. It is design evidence, not proof that the full responder landed. |
| The Sarathi/Apex product vision | [`05_SARATHI_APEX_MAP.md`](../sarathi_apex_build/05_SARATHI_APEX_MAP.md), [`MASTER_2026-06-10_anatomy_altitude_integration.md`](../vision_maps/MASTER_2026-06-10_anatomy_altitude_integration.md), and [`MASTER_2026-06-10_leverage_synthesis.md`](../vision_maps/MASTER_2026-06-10_leverage_synthesis.md) | Historical intent and organism synthesis only. The Apex map itself says it is not operating state ([notice:1-17](../sarathi_apex_build/05_SARATHI_APEX_MAP.md#L1-L17)). |
| Binding autonomy ceiling | [`OPERATOR_RULING_2026-07-30_SARATHI_AUTONOMY_CEILING.md`](../ops/OPERATOR_RULING_2026-07-30_SARATHI_AUTONOMY_CEILING.md) | Operator ruling; executable policy wins on conflict ([ruling:11-18](../ops/OPERATOR_RULING_2026-07-30_SARATHI_AUTONOMY_CEILING.md#L11-L18)). |
| July Sarathi build sequence | [`sarathi_apex_build/README.md`](../sarathi_apex_build/README.md) | Historical build corpus, not current readiness authority ([status:1-5](../sarathi_apex_build/README.md#L1-L5)). |
| June sovereign-Holon intent | [`sovereign_holons/README.md`](../sovereign_holons/README.md) | Historical design/research corpus ([notice:1-14](../sovereign_holons/README.md#L1-L14)). |
| Hermes/OpenClaw and peer comparison | [`FRONTIER_PEERS.md`](../sovereign_holons/FRONTIER_PEERS.md) plus the broad index below | Research/reference; use it to choose organs, never as a source or liveness claim. |
| Broad persistent-agent inventory | [`hermes_persistent_agent_index_2026-08-01.md`](../reports/hermes_persistent_agent_index_2026-08-01.md) | Verified-partial report. Read its mandatory errata first ([errata:10-55](../reports/hermes_persistent_agent_index_2026-08-01.md#L10-L55)). |
| Prior physical-move analysis | [`HOLON_CONSOLIDATION_PLAN_2026-08-01.md`](../plans/HOLON_CONSOLIDATION_PLAN_2026-08-01.md) | Plan only; no moves occurred, and naive ordering was proven to break imports ([plan:16-40](../plans/HOLON_CONSOLIDATION_PLAN_2026-08-01.md#L16-L40)). |
| Proposed cross-runtime schema | [`PERSISTENT_AGENT_DESCRIPTOR.md`](../architecture/PERSISTENT_AGENT_DESCRIPTOR.md) | Draft/reference, not a runtime-consumed contract. |

## Rules for future agents

1. Start here, then inspect source and tests before repeating a prose claim.
2. Search by behavior—model calls, subprocesses, loops, queues, stores, ports,
   identity registration, state roots, and runtime mutation—not by `sarathi` or
   `holon` filenames alone.
3. Add capabilities behind `dharma_swarm.sarathi`; do not create another public
   agent root, memory store, provider router, receipt spine, or scheduler.
4. Preserve `dharma_swarm.holon_system.sarathi` compatibility until a separately
   tested deprecation is admitted.
5. Keep effects fail-closed. A mailbox claim fence is not an execution permit;
   callability, cognition, and authority are separate claims.
6. When a new invocation surface or competing shell lands, update this index and
   the lineage in the same change, with a test at the new boundary.
