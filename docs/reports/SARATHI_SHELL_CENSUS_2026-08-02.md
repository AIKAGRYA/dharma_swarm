# Sarathi Agent-Shell Element Census — 2026-08-02

**Status:** P0 forensic census; no deployment or refactor authorization

**Evidence revision:** `origin/main` at `9d792ceacef32a1698838dc01586ed90ecb93666`

**Repository:** `AmitabhainArunachala/dharma_swarm`
**Verdict:** `CLOSED_NOT_PROD` — Sarathi is not an end-to-end persistent agent shell on this revision.

## Executive answer

Sarathi currently consists of a 1,124-line deterministic planning/delegation/status package and two bounded, manually callable runtime scripts. It can create plans, classify proposed delegations, enqueue file-mailbox tasks, render briefs, and judge a synthetic proof window. It does not own an ingress listener, reply transport, model call, per-turn context compiler, episodic or semantic memory, effect-capable worker, canonical persisted persona, standing supervisor, or self-modification path. The direct source says so: planning is model-free (`dharma_swarm/holon_system/sarathi/plan.py:1-8`), wake scheduling/liveness are out of scope (`dharma_swarm/holon_system/sarathi/wake.py:10-13`), the runtime binds `invoker=None` (`scripts/runtime/sarathi_wake_daemon.py:22-31,363-380`), and the so-called gateway is a read-only snapshot with both liveness booleans false (`dharma_swarm/holon_system/sarathi/gateway.py:1-25`). **[E]**

The repository does contain implementations of all twelve requested element types, often several. They belong to independent shells, runners, schedulers, stores, registries, and evolution systems. That makes every row below `SCATTERED`; it does not make those capabilities reachable by Sarathi. The direct Sarathi package is imported in only five production files outside itself—the `holon_system` facade, two thin facade modules, and two runtime scripts—and no Sarathi import occurs in the generic API gateway, A2A, MCP, memory, context-compiler, agent-runner, cron, container, or evolution families. The reproducing search is in §2.13. **[X]**

One folder is feasible only as a **composition root plus Sarathi-owned adapters**. It is not sound to move every discovered implementation under `dharma_swarm/sarathi/`. Shared infrastructure has other consumers, several files are pinned by active-track ownership or operator rulings, and naive moves break imports. The tested safe migration shape is add-first: add the complete Sarathi package, keep compatibility exports, update consumers, then remove old bodies only after import and governance changes land atomically. **[I]**

### Evidence notation

- **[E] explicit:** stated or directly implemented in source at the cited lines.
- **[X] executed:** established by the shown command or runtime reproduction.
- **[I] inferred:** conclusion from cited explicit/executed evidence.

No prose architecture inventory was used as implementation truth. In particular, `docs/architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md` was excluded from counts. Governance files were consulted only where the task explicitly requires authority/ownership rulings.

## 0. Method and scope

The checkout was dirty and its branch was behind `origin/main`, so measuring the working tree would have mixed local work with stale source. The audit therefore pinned and exported exact remote main:

```text
$ git ls-remote origin refs/heads/main
9d792ceacef32a1698838dc01586ed90ecb93666  refs/heads/main

$ git archive origin/main | tar -x -C /private/tmp/sarathi_shell_census_origin_main_9d792ceacef3
```

All source citations and LOC counts below refer to that immutable export. The export contained 5,277 tracked files and 2,444 Python files. Tests, prose docs, archived/retired code, generated reports, and vendored files were excluded from production-family counts; tests were used for verification. **[X]**

The search began with behavior, not names:

```bash
rg -l 'subprocess|Popen|asyncio\.create_subprocess'
rg -l 'while True|asyncio\.sleep|schedule|cron|daemon'
rg -l 'queue|inbox|mailbox|JetStream|consumer'
rg -l 'sqlite|aiosqlite|CREATE TABLE|connect\('
rg -l 'FastAPI|APIRouter|websocket|nats|NATS|listen|socket'
rg -l 'Path\.home\(\)|~/\.dharma|~/\.hermes|DHARMA_HOME'
rg -l 'write_text|open\(.+["'"']w|git apply|git commit|git push'
find . \( -name 'Dockerfile*' -o -name 'docker-compose*' \
  -o -name '*.plist' -o -name '*.service' \)
```

After excluding tests/docs/archive/report artifacts, the broad sweep found 226 production-ish files with process/model behavior, 407 with loop/schedule behavior, 264 with queue/mailbox behavior, 143 with database behavior, 43 with registry/identity behavior, 107 with listener behavior, 571 with state-root behavior, and 385 with runtime file-mutation behavior. These are search populations, not claims that every match is an agent shell. Each was reduced into the material independent families catalogued in §2. **[X]**

The existence gate was mechanical. Ninety-seven paths in the runtime sweep and forty-one in the surface sweep were each checked with `test -e`; none was missing. A final report-wide citation check is recorded in §7. **[X]**

## 1. Element table

`Portable Mac+VPS?` means the cited implementation can execute on both macOS and a conventional Linux VPS without changing source or relying on an undeclared host service. “Partial” is not deployment-ready. Verdicts use only the required vocabulary.

| Element | Implementations found (path:line) | Lines | Portable Mac+VPS? | Wired to Sarathi? | Verdict |
|---|---|---:|---|---|---|
| 1. Gateway / ingress | Read-only Sarathi snapshot (`dharma_swarm/holon_system/sarathi/gateway.py:1-25`); generic holon HTTP/model bridge (`api/routers/holon.py:43-89`, `dharma_swarm/holon_bridge.py:106-168,358-401`); A2A HTTP (`dharma_swarm/a2a/node_gateway.py:314-500`); two NATS/mailbox protocols (`dharma_swarm/a2a/mailbox_gateway.py:42-45,169-288`, `dharma_swarm/a2a/nats_transport.py:65-75,328-365,695-698`); Telegram (`dharma_swarm/gateway/base.py:28-50,94-102`, `dharma_swarm/gateway/telegram.py:73-178`); generic dashboard chats (`api/routers/agents.py:424-557`, `api/routers/chat.py:1219-1302`). | 5,791 audited | Partial | Only the snapshot is direct; generic `/holon/{name}/chat` can address the string `sarathi` if an out-of-repo identity exists, but it never imports Sarathi organs. | SCATTERED |
| 2. Memory | StrangeLoop SQLite (`dharma_swarm/memory.py:1-6,77-103`); AgentMemoryBank JSON (`dharma_swarm/agent_memory.py:1-13,69-95`); AgentMemoryManager SQLite (`dharma_swarm/agent_memory_manager.py:148-179`); memory-plane event/conversation stores (`dharma_swarm/engine/event_memory.py:263-283`, `dharma_swarm/engine/conversation_memory.py:176-230`); lattice/palace (`dharma_swarm/memory_lattice.py:31-50`, `dharma_swarm/memory_palace.py:205-278`); graph/vector/knowledge families; read-only MemoryKernel census (`dharma_swarm/memory_kernel/facade.py:1-5,60-75`). | 11,514 principal-family LOC | Partial | No. Sarathi package and wrappers import none of them. | SCATTERED |
| 3. Context | Canonical dispatch compiler (`dharma_swarm/context_compiler.py:37-126,245-431`); legacy role context (`dharma_swarm/context.py:1363-1415`); ContextAgent (`dharma_swarm/context_agent.py:318-366,643-686`); MemoryKernel default/shadow compilers; optional holon memory pack (`dharma_swarm/holon_runtime.py:53-80,127-150`); generic wake file rehydration (`scripts/runtime/codex_composer_wake_loop.py:208-226,449-508`); Sarathi `BootPack` (`dharma_swarm/holon_system/sarathi/plan.py:22-38`). | 6,346 plus BootPack | Partial | BootPack only; no per-turn compiler or memory retrieval is supplied by either Sarathi wrapper. | SCATTERED |
| 4. Persistence / database | Holon JSONL (`dharma_swarm/holon_persistence.py:25-60,63-97`); Sarathi mailbox/reports/briefs/spend files (`dharma_swarm/roaming_mailbox.py:115-170,192-356`, `scripts/runtime/sarathi_wake_daemon.py:224-250,296-341`); RuntimeState SQLite (`dharma_swarm/runtime_state.py`); TaskBoard/Stigmergy (`dharma_swarm/task_board.py`, `dharma_swarm/stigmergy.py`); memory-plane SQLite (`dharma_swarm/engine/event_memory.py`, `dharma_swarm/engine/conversation_memory.py`). | 7,522 core audited | Yes for files/SQLite; semantics partial | Sarathi writes only its isolated files and holon JSONL; no shared transaction or durable reply ledger. | SCATTERED |
| 5. Compute host | Bounded Sarathi command (`scripts/runtime/sarathi_wake_daemon.py:51-74,224-393`); tmux generic wake (`scripts/runtime/codex_composer_wake_loop.py:1178-1261`); live organism service (`dharma_swarm/orchestrate_live.py:2281-2483`, `Dockerfile.swarm:39-40`, `docker-compose.yml:78-133`); API image (`Dockerfile:5-46`, `docker-compose.yml:58-75`); launchd files; cron daemon; numerous operator daemons. | 2,126 direct host artifacts; >10k competing supervisors | No single portable definition | The bounded command is direct, but no container, launchd, systemd, cron job, or installed entry point runs it. | SCATTERED |
| 6. Cognition | AgentRunner/provider stack (`dharma_swarm/agent_runner.py:1838-2104`, `dharma_swarm/providers.py`, `dharma_swarm/runtime_provider.py`); holon streaming model call (`dharma_swarm/holon_bridge.py:379-401`); ContextAgent Ollama call (`dharma_swarm/context_agent.py:336-366`); injected spine pass-through (`dharma_swarm/spine/invoke.py:19-55`). | 9,331 audited | Partial; provider/secret/binary dependent | No. Sarathi planning is deterministic and the daemon supplies no invoker. | SCATTERED |
| 7. Tools / effectors | AgentRunner local tools (`dharma_swarm/agent_runner.py:261-399,1829-2065`); AutonomousAgent/PersistentAgent (`dharma_swarm/autonomous_agent.py:281-295,386-553,945-1041`, `dharma_swarm/persistent_agent.py:431-447`); API file/shell tools (`api/chat_tools.py:29-35,373-437,749-773`, `api/chat_tool_execution.py:195-381`); browser registry (`dharma_swarm/browser_agent.py:148-249,574-719`); Living Agent Kernel effect boundary (`dharma_swarm/operator_core/living_agent_kernel.py:2420-2785`); roaming command workers. | >22,000 competing runtime LOC | No; host and container assumptions differ | No. Sarathi produces mailbox files or calls an injected invoker; no effect-capable consumer is bound. | SCATTERED |
| 8. Identity / persona | `AgentConfig` (`dharma_swarm/models.py:181-210`); Ginko AgentRegistry identity (`dharma_swarm/agent_registry.py:165-242`); RunningHolon identity (`dharma_swarm/holon_bridge.py:1-11,106-149`); execution identity (`dharma_swarm/spine/identity.py:28-100`); CardRegistry/contact/node registries (`dharma_swarm/a2a/agent_card.py:471-528`, `dharma_swarm/a2a/contact_registry.py:68-155`, `dharma_swarm/a2a/node_registry.py:153-225`); generic `WakeProfile` (`scripts/runtime/codex_composer_wake_loop.py:53-68,129-136`); static Sarathi roster. | At least 6 registries / 7 concepts | File forms mostly yes | No canonical Sarathi identity/card/persona is tracked or loaded by the direct package. | SCATTERED |
| 9. Scheduler / heartbeat | Seven-module cron subsystem (`dharma_swarm/cron_*.py`); bounded Sarathi wrapper (`scripts/runtime/sarathi_wake_daemon.py:51-54,363-393`); generic tmux wake (`scripts/runtime/codex_composer_wake_loop.py:1178-1261`); PersistentAgent loop (`dharma_swarm/persistent_agent.py:580-625`); garden daemon (`garden_daemon.py:337-353`); organism supervisor; 17 scheduled GitHub workflows; A2A workers. | >16,000 audited | No; launchd/tmux/GitHub/Linux split | No standing scheduler targets canonical Sarathi. | SCATTERED |
| 10. Evolution / self-modification | Guarded Darwin stack (`dharma_swarm/evolution.py:2357-2424,3245-3508` plus safety/promotion modules); self-improve (`dharma_swarm/self_improve.py:233-432`); DGM (`dharma_swarm/dgm_loop.py:351-400,636-759`); AutoResearch (`dharma_swarm/autoresearch_loop.py:434-507`); BuildEngine (`dharma_swarm/build_engine.py:166-425`); custodians (`dharma_swarm/custodians.py:605-741`); Ginko prompt evolution (`dharma_swarm/ginko_evolution.py:238-459`); Forge candidate/config evolution. | 12,791 audited | No; git/provider/container assumptions | No. None imports or is callable from canonical Sarathi. | SCATTERED |
| 11. Governance | Autonomy dial (`dharma_swarm/operator_core/autonomy_dial.py`); reversibility gate (`dharma_swarm/operator_core/reversibility_gate.py:47-145`); canonical execution lease (`dharma_swarm/operator_core/execution_lease.py:116-173,187-252`); kill/budget guards (`dharma_swarm/holon_killswitch.py`, `dharma_swarm/holon_budget_guard.py`); permissions/evolution safety; separate generic wake activation lease (`scripts/runtime/codex_composer_wake_loop.py:1217-1229`). | >2,596 core audited | Core Python yes; policy paths pinned | Partially, but with a critical authority hole: `NEEDS_LEASE` work is enqueued without a validated execution lease. | SCATTERED |
| 12. Observability / receipts | Holon JSONL/compass (`dharma_swarm/holon_runtime.py:163-219`, `dharma_swarm/holon_persistence.py:32-84`); Sarathi briefs, daemon reports, task receipts, proof evaluator (`scripts/runtime/sarathi_wake_daemon.py:267-341`, `dharma_swarm/holon_system/sarathi/proof.py:22-73,98-151`); RuntimeState/agent-run receipts (`dharma_swarm/agent_runner.py:1314-1331`); generic wake status/receipts. | >2,000 direct plus shared stores | Files yes; truth semantics no | Partially. Persistence is fail-open and the 14-cycle proof can pass without dispatch, model, reply, memory, or even its cycle JSONL. | SCATTERED |

The table’s uncomfortable result is deliberate: nothing is `SINGLE`, and nothing is repository-wide `MISSING`; instead, every required behavior exists in multiple incompatible forms while the Sarathi-owned end-to-end connection is missing. **[I]**

## 2. Scatter map and independence proof

### 2.1 Gateway / ingress

1. **Canonical Sarathi “gateway”:** `gateway_snapshot()` only reads roster/pulse/brief/scoreboard and returns false liveness (`dharma_swarm/holon_system/sarathi/gateway.py:15-25`). It listens nowhere and sends no reply. **[E]**
2. **Sovereign-holon HTTP:** `POST /holon/{name}/chat` loads a `~/.dharma/agents/<name>/identity.json`, constructs its provider, streams a reply, and logs turns (`api/routers/holon.py:43-89`; `dharma_swarm/holon_bridge.py:106-168,358-401`). It does not import `holon_system.sarathi`, call the Sarathi planner/wake/delegator, compile canonical context, or expose tools. **[E][X]**
3. **Dashboard agent/global chat:** `/api/agents/{agent_id}/chat` ultimately calls the dashboard-wide stream after creating a persona-shaped string (`api/routers/agents.py:424-516`); `/api/chat` uses a global profile/live brief (`api/routers/chat.py:1219-1302`). Neither is the Sarathi shell. **[E]**
4. **A2A HTTP:** the task routes are real (`dharma_swarm/a2a/node_gateway.py:314-500`), but `api/main.py:159-185` creates `A2AServer()` with no handlers; default no-handler dispatch becomes failed (`dharma_swarm/a2a/a2a_server.py:341-377,574-584`). The adapter submits tasks; it supplies no cognition (`dharma_swarm/a2a/spine_adapter.py:81-168`). **[E]**
5. **NATS/mailbox HTTP:** `mailbox_gateway.py` uses stream `DHARMA_A2A` and `dharma.agent.<uid>.inbox` (`dharma_swarm/a2a/mailbox_gateway.py:42-45,169-288`), while the canonical task transport uses `DS_TASKS` and `dharma.a2a.task.<target>.<capability>` (`dharma_swarm/a2a/nats_transport.py:65-75,328-365,695-698`). They do not share a stream contract, and neither has a Sarathi consumer. **[E][X]**
6. **Telegram:** the adapter can poll and send (`dharma_swarm/gateway/telegram.py:73-178`), but the base drops inbound events when no handler is bound (`dharma_swarm/gateway/base.py:94-102`). Both production constructors omit a handler (`dharma_swarm/swarm.py:503`; `dharma_swarm/terminal_commands/infrastructure.py:284`). **[E]**

These implementations are independent, not alternate front ends over one Sarathi handler. A cross-surface search found no canonical Sarathi import in `api/`, `dharma_swarm/a2a/`, or `dharma_swarm/gateway/`. The only case-insensitive `sarathi` hit in those targets was unrelated metadata on another contact at `dharma_swarm/a2a/contact_registry.py:123`. **[X]**

### 2.2 Memory

The principal episodic owners are independent schemas/stores: `StrangeLoopMemory` mixes RAM and SQLite (`dharma_swarm/memory.py:77-103`); `AgentMemoryBank` owns per-agent JSON (`dharma_swarm/agent_memory.py:69-95`); `AgentMemoryManager` owns `~/.dharma/agent_memory/memories.db` (`dharma_swarm/agent_memory_manager.py:148-179`); event and conversation stores share `memory_plane.db` but own separate tables (`dharma_swarm/engine/event_memory.py:263-283`, `dharma_swarm/engine/conversation_memory.py:176-230`); `conversation_log.py`, `routing_memory.py`, `organism_memory.py`, and `experiment_memory.py` add more stores. `MemoryLattice` composes five facilities without merging ownership (`dharma_swarm/memory_lattice.py:31-50`), while `MemoryPalace` adds vectors/LanceDB and can become temporary when no state directory is supplied (`dharma_swarm/memory_palace.py:205-278`). **[E]**

The semantic side is likewise plural: four-graph SQLite (`dharma_swarm/graph_store.py`), in-memory/Qdrant knowledge (`dharma_swarm/engine/knowledge_store.py`), SQLite-vec/FTS (`dharma_swarm/vector_store.py`), the concept bridge (`dharma_swarm/semantic_memory_bridge.py`), knowledge-units SQLite (`dharma_swarm/knowledge_units.py`), field knowledge (`dharma_swarm/field_knowledge_base.py`), and governed retrieval (`dharma_swarm/memory_retrieval.py`). The read-only MemoryKernel coordinates discovery rather than owning consolidation (`dharma_swarm/memory_kernel/facade.py:1-5,60-75`). Its executable registry reported `83` unique registered surfaces and `66` currently existing surfaces. **[E][X]**

There is partial sharing outside Sarathi: `AgentRunner` writes AgentMemoryBank and AgentMemoryManager in one completion path and ConversationMemoryStore in another (`dharma_swarm/agent_runner.py:2982-3023,3136-3167,3382-3398`). There is **zero direct sharing with Sarathi**: no canonical Sarathi module or wrapper imports any of these owners. **[X]**

### 2.3 Context

1. `ContextCompiler` is declared canonical and is truly called for ordinary orchestrator dispatch (`dharma_swarm/context_compiler.py:1,37-126,245-431`; `dharma_swarm/orchestrator.py:1148-1215`).
2. The legacy assembler builds a role/filesystem prompt and is injected only for a provider-specific AgentRunner path (`dharma_swarm/context.py:1363-1415`; `dharma_swarm/agent_runner.py:947-1020`).
3. `ContextAgent` has separate Ollama distillation and static package assembly (`dharma_swarm/context_agent.py:318-366,643-686`).
4. `holon_wake_cycle()` can optionally read a six-item/1,800-character MemoryKernel pack (`dharma_swarm/holon_runtime.py:53-80,127-150`). Neither Sarathi wrapper supplies it.
5. The generic wake profile’s `rehydrate_context()` records existence, size, hashes, and selected summaries; it does not produce a model prompt (`scripts/runtime/codex_composer_wake_loop.py:208-226,449-508`).
6. Direct Sarathi receives only a caller-injected `BootPack` of roster, open items, dedup keys, audit, and lodestone text (`dharma_swarm/holon_system/sarathi/plan.py:22-38`).

Only items 1 and 2 share the ordinary orchestration/AgentRunner path; items 3–6 are independent. Searches across all context-family files found no canonical Sarathi import. **[E][X]**

### 2.4 Persistence / database

Sarathi-adjacent durability is split among:

- append-only holon cycle JSONL (`dharma_swarm/holon_persistence.py:25-60`), whose reader silently skips malformed lines (`:63-84`);
- a separate file mailbox with task, response, and receipt directories (`dharma_swarm/roaming_mailbox.py:115-170`), `O_EXCL` claim files (`:192-254`), and a non-transactional response-then-task update (`:327-356`);
- separate daemon spend, lock, report, brief, and closeback files (`scripts/runtime/sarathi_wake_daemon.py:187-221,224-250,267-341`);
- RuntimeState SQLite, TaskBoard, StigmergyStore, and the memory-plane databases, all with independent schemas and consumers.

They share a configurable state root in some deployments, not one transaction, schema, writer, or replay contract. `holon_wake_cycle()` explicitly treats persistence as best-effort and swallows every exception (`dharma_swarm/holon_runtime.py:45-50`). That makes the observable `status="ran"` independent of durable proof. **[E]**

### 2.5 Compute host

The direct Sarathi runtime is a fixed-cycle Python command and explicitly delegates repetition to an outside scheduler (`scripts/runtime/sarathi_wake_daemon.py:51-54,224-393`). The generic Composer profile is a different, tmux-supervised infinite loop (`scripts/runtime/codex_composer_wake_loop.py:1178-1261`) with no Sarathi-organ import. The main organism is yet another supervised service (`dharma_swarm/orchestrate_live.py:2281-2483`) packaged by `Dockerfile.swarm` and the `swarm` Compose service (`Dockerfile.swarm:39-40`; `docker-compose.yml:78-118`). PersistentAgent/AutonomousAgent, the Living Agent Kernel worker, cron, garden, A2A workers, Merge Master Mike, and multiple operator shell loops each define independent process boundaries. **[E]**

No Dockerfile, Compose service, plist, systemd unit, cron registry entry, or installed console script invokes `sarathi_wake_daemon.py`. The independence check is both negative imports and positive entrypoint enumeration in §5. **[X]**

### 2.6 Cognition

Actual model seams exist in the main runner (`dharma_swarm/agent_runner.py:1838-1859,2067-2104`), sovereign-holon bridge (`dharma_swarm/holon_bridge.py:379-401`), provider implementations, AutonomousAgent (`dharma_swarm/autonomous_agent.py:386-553`), ContextAgent (`dharma_swarm/context_agent.py:336-366`), and the semantic drain (`scripts/runtime/codex_composer_semantic_inbox_drain.py:211-220`). `spine.invoke_agent()` is only a typed pass-through to an injected invoker (`dharma_swarm/spine/invoke.py:19-55`). **[E]**

Direct Sarathi calls none of them. `build_plan()` is pure deterministic mapping (`dharma_swarm/holon_system/sarathi/plan.py:105-180`); live invoke requires a non-null injected invoker (`dharma_swarm/holon_system/sarathi/delegate.py:277-292`); the only canonical wrapper deliberately supplies none (`scripts/runtime/sarathi_wake_daemon.py:22-31,363-380`). The `WakeProfile` model label in the generic loop is status metadata; that script contains no provider completion using it. **[E][X]**

### 2.7 Tools / effectors

The main effect stacks are independent:

- **AgentRunner:** catalog, host path handling, hard-wired `LocalSandbox`, file/shell/HTTP executor, and ReAct loop (`dharma_swarm/agent_runner.py:261-399,1506-1587,1829-2065`). A Docker sandbox exists (`dharma_swarm/docker_sandbox.py:113-247`) but this path does not select it.
- **Autonomous/Persistent agents:** default write/bash/web tools and direct filesystem/shell/web execution (`dharma_swarm/autonomous_agent.py:281-295,945-1041,1163-1193`), composed by `PersistentAgent` (`dharma_swarm/persistent_agent.py:431-447`).
- **API tools:** direct file operations (`api/chat_tools.py:373-437`) and Docker-default/host-opt-in shell execution (`api/chat_tool_execution.py:195-381`).
- **Browser:** Playwright/httpx engine and registrations (`dharma_swarm/browser_agent.py:148-249,574-719`), but no non-test production importer binds it to a live registry.
- **Living Agent Kernel:** separate tool policy, patch registry, authority/path checks, and `DiffApplier` boundary (`dharma_swarm/operator_core/living_agent_kernel.py:55-70,2420-2785`).
- **Roaming workers:** git-sync and arbitrary responder commands (`dharma_swarm/roaming_poller.py:37-67,118-148`); they do not target the isolated Sarathi queue or validate Sarathi gate metadata.

No family imports canonical Sarathi. Conversely, Sarathi imports none of these effectors; it only emits a file task or invokes a caller-provided object. **[X]**

### 2.8 Identity / persona

At least six independent registries or identity homes coexist:

1. `AgentConfig`, described as canonical agent config (`dharma_swarm/models.py:181-210`).
2. `AgentRegistry.AgentIdentity` under `~/.dharma/ginko/agents` (`dharma_swarm/agent_registry.py:165-242`).
3. `RunningHolon` under the conflicting `~/.dharma/agents` home (`dharma_swarm/holon_bridge.py:1-11,106-149`).
4. A2A `CardRegistry` persisted under its own card root (`dharma_swarm/a2a/agent_card.py:471-528`), in-memory `ContactRegistry` (`dharma_swarm/a2a/contact_registry.py:68-155`), and persisted `NodeRegistry` (`dharma_swarm/a2a/node_registry.py:153-225`).
5. `ExecutionIdentity`, which identifies a work claim/run rather than a persona (`dharma_swarm/spine/identity.py:28-100`), plus lifecycle integration (`dharma_swarm/runtime_lifecycle_identity.py:12-80`).
6. Generic wake `WakeProfile` seat metadata (`scripts/runtime/codex_composer_wake_loop.py:53-68,129-136`).

Only CardRegistry has an explicit bridge from AgentRegistry (`dharma_swarm/a2a/agent_card.py:619-642`). Contact, node, holon, execution, and wake-profile concepts are otherwise independent. `default_contacts()` contains no Sarathi contact (`dharma_swarm/a2a/contact_registry.py:108-155`), and the tracked tree contains no Sarathi identity JSON, A2A card, or restart-surviving persona source loaded by canonical Sarathi. **[E][X]**

### 2.9 Scheduler / heartbeat

The seven `cron_*.py` modules total 2,312 LOC and implement a real scheduler/daemon/runner family: due calculation/locking/dispatch (`dharma_swarm/cron_scheduler.py:337-448`), a persistent wait loop (`dharma_swarm/cron_daemon.py:35-136`), and subprocess/handler execution (`dharma_swarm/cron_runner.py:123-186,856-940`). No registered job invokes Sarathi. **[E][X]**

Independent loops include the bounded Sarathi command, the generic tmux Composer loop, the six-hour Ginko Compose loop (`dharma_swarm/ginko_cron_loop.py:41-65`; `docker-compose.yml:120-133`), PersistentAgent, the root `garden_daemon.py`, the Living Agent Kernel worker, A2A inbox/Palantir/Devin workers, Merge Master Mike, organism supervision, and many operator loops. Seventeen scheduled GitHub workflows add a cloud-only scheduler/effect plane; their cron declarations include `.github/workflows/merge-master-mike-backlog.yml:4-5`, `loop-watcher.yml:14-16`, `hardening-lane.yml:29-30`, `nightly-tests.yml:9-10`, and `walking-brief.yml:18-19`. **[E]**

These share neither one job registry nor one service manager. None imports or calls canonical Sarathi. **[X]**

### 2.10 Evolution / self-modification

The source/config mutation families are substantively independent:

- **Guarded Darwin:** 5,925 LOC across `evolution.py`, `diff_applier.py`, `evolution_safety.py`, safety runtime, sealed apply, verification, and promotion gate. It can apply/test and commit a signed packet (`dharma_swarm/evolution.py:2357-2424,3245-3508`; `dharma_swarm/diff_applier.py:233-498`) and has a separate safety decision (`dharma_swarm/evolution_safety.py:222-360`).
- **SelfImprove:** enabled through the live organism but disabled by default; its live path reads `_runtime_state` without the constructor assigning it (`dharma_swarm/self_improve.py:233-254,373-432`; wiring at `dharma_swarm/orchestrate_live.py:750-784,2254,2334`).
- **DGM:** advertises live mode but explicitly forces/refuses shadow (`dharma_swarm/dgm_loop.py:351-400,636-759,860-876`).
- **AutoResearch:** defaults `dry_run=False` and writes source directly with backup/revert (`dharma_swarm/autoresearch_loop.py:100-109,434-507`); its only production construction does not run the loop.
- **BuildEngine:** mutates/tests/commits directly and has destructive git cleanup semantics (`dharma_swarm/build_engine.py:166-425`); no non-test service caller was found.
- **Custodians:** edit, branch, and commit before the merge gate (`dharma_swarm/custodians.py:360-428,605-741`); cron and operator CLI can execute it.
- **Ginko evolution:** mutates out-of-repo prompt/generation/identity state (`dharma_swarm/ginko_evolution.py:238-459`), not source.
- **Forge loops:** evolve candidates/config/history, not Sarathi code.

There is no shared base class, promotion contract, or canonical Sarathi import among these families. None gives Sarathi a self-modification method. Moving them into a Sarathi folder would falsely transfer both ownership and authority. **[X][I]**

### 2.11 Governance

Four governance vocabularies meet—but do not form one effect-boundary proof:

1. Sarathi reads the autonomy dial and reversibility gate (`dharma_swarm/holon_system/sarathi/delegate.py:41-52,212-266`).
2. Holon runtime separately checks kill, direct-process budget, and an optional `planned_action` (`dharma_swarm/holon_runtime.py:82-118`). The Sarathi daemon omits `planned_action`, so this outer gate is bypassed; inner delegation classification still runs.
3. The canonical `ExecutionLease` includes issuer, recipient, task/correlation IDs, allowed actions/paths, expiry, budget, content hash, and validation (`dharma_swarm/operator_core/execution_lease.py:116-173,187-252`).
4. Sarathi calls the file mailbox claim fence “the execution lease” (`dharma_swarm/holon_system/sarathi/delegate.py:9-18,298-300`), but a claim receipt contains only task, claimant, and time (`dharma_swarm/roaming_mailbox.py:192-254`).

The type mismatch is executable, not semantic nitpicking. `GATED_CLASSES` omits `ActionClass.NEEDS_LEASE` (`dharma_swarm/holon_system/sarathi/delegate.py:48-52`), and mailbox metadata records a gate class but no `execution_lease_id` (`:137-150`). At dispatch level, a reproduced `needs_lease` delegation was enqueued with `status=dispatched`; after claim it was `claimed`; its execution-lease ID was null. **[X]**

```text
lease_repro:
  action_class needs_lease
  execution_lease_id null
  metadata_keys ["sarathi"]
  outcome_status dispatched
  task_status_after_claim claimed
```

This is a small AI-native language-design obligation: `ClaimFence<TaskId>` must not inhabit `ExecutionPermit<ActionHash, Recipient, Expiry, Budget>`. A worker may cross an effect boundary only after a validator constructs the latter from a current gate decision, dial ceiling, canonical execution lease, and matching execution identity. Receipts after the fact cannot repair missing authority before the effect. **[I]**

### 2.12 Observability / receipts

Sarathi emits useful files—briefs, outcome ledgers, task files, daemon reports, spend ledger, holon events, compass signals, and proof reports—but they are independent projections. The generic wake loop emits a different status/receipt family, and AgentRunner/RuntimeState emit still others. They do not share a required run identity or a single truth predicate. **[E]**

Three runtime counterexamples defeat the stronger proof claims while the focused tests remain green:

1. `holon_wake_cycle()` returned `status=ran` after its persistence writer raised; `_persist()` swallows the exception (`dharma_swarm/holon_runtime.py:45-50,217-219`). **[X]**
2. Fourteen propose-only cycles passed `evaluate_unattended_proof()` even when every holon persistence write raised and no event log existed. The auditor only examines rows whose status is `dispatched` (`dharma_swarm/holon_system/sarathi/proof.py:22-26,37-73`); propose-only cycles create none (`scripts/runtime/sarathi_proof_window.py:168-195`). **[X]**
3. The proof runner accepted `verified_at="9999-99-99T99:99"` because validation checks only a regex-shaped timestamp (`scripts/runtime/sarathi_proof_window.py:34-36,77-100`). A full 14-cycle CLI run returned `passed: true`, `audit_findings_total: 0`, and fourteen `ran` statuses while creating zero mailbox task files. **[X]**

```text
persistence_repro: persist_calls 1, result_status ran
proof_without_persistence_repro:
  event_log_exists false
  passed true
  persist_calls 14
  statuses ["ran"]
proof_cli_invalid_kill_timestamp:
  cycles_run 14
  passed true
  audit_findings_total 0
  mailbox_task_files 0
```

The proof therefore establishes only that a deterministic propose-mode function returned `ran` fourteen times and found no fabricated `dispatched` rows. It does not prove unattended ingress, cognition, effects, replies, persistence, scheduling, or kill-path reachability. **[I]**

### 2.13 Reproducing the independence checks

```bash
# All production importers/references of the canonical package.
rg -l --glob '*.py' 'holon_system\.sarathi' | sort

# Output:
dharma_swarm/holon_system/__init__.py
dharma_swarm/holon_system/gateway/operator_brief.py
dharma_swarm/holon_system/observability/scoreboard.py
scripts/runtime/sarathi_proof_window.py
scripts/runtime/sarathi_wake_daemon.py
tests/test_holon_system_imports.py
tests/test_sarathi_delegate.py
tests/test_sarathi_plan.py
tests/test_sarathi_proof.py
tests/test_sarathi_proof_window.py
tests/test_sarathi_wake.py

# Cross-family check; output was only unrelated metadata at contact_registry.py:123.
rg -n -i --glob '*.py' sarathi \
  api dharma_swarm/a2a dharma_swarm/gateway \
  dharma_swarm/context_compiler.py dharma_swarm/context.py \
  dharma_swarm/context_agent.py dharma_swarm/memory.py \
  dharma_swarm/agent_memory.py dharma_swarm/agent_memory_manager.py \
  dharma_swarm/memory_kernel dharma_swarm/mcp_server.py \
  dharma_swarm/dharma_context_mcp.py dharma_swarm/chetana/mcp_server.py
```

The first list contains six tests in addition to five production paths. `tests/test_sarathi_wake_daemon.py` loads the script rather than importing the package textually, which is why it is absent from the `rg` output. **[X]**

## 3. Portability audit

The direct ten-module Sarathi organ package is ordinary Python and file data. Its bounded wrapper uses `fcntl.flock`, which is available on macOS and Linux (`scripts/runtime/sarathi_wake_daemon.py:71-74,191-221`), and derives the repository from `__file__` (`:76-90`). With explicit `--state-root` and `--agents-root`, the one-shot command ran successfully against temporary directories on the local Mac. This is source portability, not a portable persistent service. **[E][X]**

| Implementation | Host assumption / hard-coded surface | Mac | Linux VPS | Can move unchanged? |
|---|---|---|---|---|
| Canonical Sarathi organs | Eager package import reaches `holon_health → holon_bridge → models/pydantic`; state collaborators are injected. The package itself owns no service/provider dependencies (`dharma_swarm/holon_system/sarathi/__init__.py:7-40`). | Yes with project env | Yes with project env | As a complete group, mostly; make `__init__` lazy and declare runtime dependencies. |
| Sarathi wake command | `Path.home()/.dharma` default, POSIX advisory lock, unsafe no-lock fallback on non-POSIX; depends on repo-relative script execution and an external scheduler (`scripts/runtime/sarathi_wake_daemon.py:51-92,191-221,396-405`). | Yes, bounded | Yes, bounded | Rewrite/package as a module and service entrypoint; retain configurable roots. |
| Sarathi proof command | Repo-relative import bootstrap and local file proof only; not a service (`scripts/runtime/sarathi_proof_window.py:43-59,112-230`). | Yes | Yes | Package, then make persistence/listener/kill witnesses authoritative. |
| Generic Composer wake | Requires git and tmux for standing mode and creates a named tmux session (`scripts/runtime/codex_composer_wake_loop.py:554-589,1178-1261`). Its activation start checks only that a lease string is nonempty (`:1217-1229`). | Yes if tmux installed | Yes if tmux installed | No; replace tmux control with a service-manager-neutral supervisor interface. |
| Cron family | Imports `fcntl` unconditionally (`dharma_swarm/cron_scheduler.py:18`); launchd template uses `/bin/bash`, `/opt/homebrew/bin`, and `/Users/dhyana/.npm-global/bin` (`scripts/com.dharma.cron-daemon.plist:8-40`). | Yes after template substitution | Python family yes; plist no | Scheduler core can stay shared; provide separate launchd/systemd adapters and eliminate fixed PATH. |
| Root organism plist | Hard-codes `/Users/dhyana/dharma_swarm`, `/Users/dhyana/.dharma`, `/bin/bash`, and `/opt/homebrew/bin` (`com.dharma.swarm.plist:13-45`). | One machine only | No | Rewrite as a generated template; do not move into Sarathi. |
| Garden daemon | Writes `~/.dharma` and `~/.claude`, prompts over several assumed home repositories (`garden_daemon.py:29-64`), launches Claude with `bypassPermissions` (`:208-223`); launcher hard-codes `/opt/homebrew/bin/python3` (`run_garden.sh:21-28`). | This Mac shape only | No unchanged | Independent operator daemon; rewrite roots, binary discovery, and authority before reuse. |
| Persistent/Autonomous agent | Forces working directory to `Path.home()/dharma_swarm` (`dharma_swarm/persistent_agent.py:149-159`), then uses host filesystem/shell/web effectors. | Only matching checkout | Only matching checkout | Keep shared; make workdir/sandbox/provider/authority injected. |
| CLI model providers | Searches user npm, Homebrew, and `/usr/local/bin`; defaults cwd to `~/dharma_swarm`; spawns provider CLIs with full tool access (`dharma_swarm/providers.py:659-683,719-767`). | Conditional | Conditional | Keep provider adapters; remove default checkout and expose explicit capability/authority contract. |
| AgentRunner local sandbox | Selects `LocalSandbox` at `dharma_swarm/agent_runner.py:1829-1836`; host subprocess shell is in `dharma_swarm/sandbox.py:151-184`; absolute work paths are accepted at `agent_runner.py:1506-1587`. | Host-dependent | Host-dependent | No; bind the existing Docker sandbox or another portable sandbox explicitly. |
| API file/shell tools | Allowed roots assume `~/dharma_swarm` (`api/chat_tools.py:29-35`). The web image lives at `/app`, contains neither Docker CLI nor a source volume (`Dockerfile:7-25`; `docker-compose.yml:58-70`). | Checkout API may work | Deployed web file/shell tools fail closed or lack source | Keep API route; rewrite roots/backends. Do not cite it as a working Sarathi effector. |
| Swarm container | Source mounted read-only at `/app/dharma_swarm`; mutable evolution uses separate volumes (`docker-compose.yml:78-110`). Runs the organism CMD, not Sarathi (`Dockerfile.swarm:39-40`). | Docker Desktop conditional | Docker yes | Shared compute must stay; add a dedicated Sarathi service or parameterized worker. Read-only source conflicts with in-place self-modification by design. |
| Web/holon HTTP | Image creates only `/root/.dharma/ginko/*`, and Compose mounts only that subtree (`Dockerfile:27-33`; `docker-compose.yml:58-70`). `/holon/sarathi/chat` needs `/root/.dharma/agents/sarathi/identity.json`. | Source-run conditional | Container returns 404 absent sidecar identity | Rewrite deployment state contract or version a portable persona source. |
| Roaming mailbox | Atomic claim is explicitly scoped to one filesystem; git synchronization cannot guarantee exclusivity (`dharma_swarm/roaming_mailbox.py:192-219`). | Yes, local FS | Yes, one local FS | File queue may stay for offline use, but not as a fleet-wide authority/queue without a broker adapter. |
| A2A/NATS | Broker URLs, streams, durable consumers, TLS, and credentials are external. One design expects `DHARMA_A2A`; another `DS_TASKS` (`dharma_swarm/a2a/mailbox_gateway.py:42-45`; `dharma_swarm/a2a/nats_transport.py:65-75`). | Conditional | Conditional | Choose one protocol; configure endpoints and credentials, never hard-code loopback. |
| Living Agent Kernel service | Uses POSIX `fcntl` and a standalone worker loop (`dharma_swarm/operator_core/living_agent_kernel_service.py:10,39-134`; `scripts/runtime/living_agent_kernel_worker_process.py:36-141`); no plist/Compose/systemd packaging. | Conditional | Conditional | Keep independent/shared; package host adapters before considering Sarathi reuse. |
| Evolution stacks | Guarded Darwin assumes git/tests/provider and a home checkout (`dharma_swarm/evolution.py:3420-3508`); `evolution_safety.py` hard-codes protected roots for `/root`, `/home/openclaw`, `/Users/dhyana`, and `/app` (`dharma_swarm/evolution_safety.py:46-55,96-104`). AutoResearch hard-codes repository roots and writes source (`dharma_swarm/autoresearch_loop.py:46-109,434-507`). | Conditional | Conditional | Do not move. Replace path allowlists with configuration and converge effect-boundary promotion first. |
| GitHub workflow schedulers | Seventeen cron workflows depend on GitHub-hosted Linux, repository permissions/secrets, GitHub API, and cloud event semantics. Several mutate branches/PRs, e.g. `.github/workflows/loop-watcher.yml:70-79,176-195` and `pr-dedupe.yml:140-142,222-224`. | Cloud only | Cloud only | Must stay under `.github/workflows`; never part of a runs-anywhere shell core. |

### Deployment-artifact census

```text
./Dockerfile
./Dockerfile.swarm
./com.dharma.swarm.plist
./docker-compose.yml
./scripts/com.dharma.cron-daemon.plist
./scripts/com.dharma.dashboard-api.plist
./scripts/com.dharma.dashboard-web.plist
./scripts/com.dharma.sovereign-hardening-night.plist
./scripts/com.dhyana.litestream.plist
```

There is no tracked `*.service` file and no Sarathi-named Dockerfile, Compose service, plist, or service unit. **[X]**

### Portability conclusion

The reusable **core** can be Mac/Linux portable if configuration owns state root, repo/workspace, provider, broker, and sandbox. The current **service** cannot be moved unchanged because no such service exists. The nearest standing loops are coupled to tmux, launchd, Docker/Linux, GitHub Actions, or a specific home checkout. **[I]**

## 4. Consolidation verdict

### 4.1 Can the elements be organized into `dharma_swarm/sarathi/`?

**Yes as one Sarathi-owned composition root; no as a physical collection of all implementations.** The folder should own the stable turn contract, Sarathi persona/config schema, orchestration of shared services, portable runtime entrypoint, adapters, and Sarathi-specific receipts. Shared provider, memory, context, transport, sandbox, scheduler, governance, and evolution engines must stay in their canonical homes and be consumed through explicit interfaces. **[I]**

A concrete target shape is:

```text
dharma_swarm/sarathi/
  __init__.py             # small/lazy public API
  shell.py                # handle_turn() composition root
  identity.py             # versioned persona schema + state overlay
  plan.py
  delegate.py
  wake.py
  brief.py
  proof.py
  runtime/
    service.py            # portable bounded unit + supervisor protocol
    cli.py                # installed entry point
  adapters/
    ingress.py            # HTTP/A2A/MCP envelope adapters
    context.py            # ContextCompiler adapter
    memory.py             # canonical episodic/semantic adapter
    invoker.py            # AgentRunner/provider adapter
    mailbox.py            # file queue/offline adapter
    scheduler.py          # service-neutral heartbeat contract
  governance.py           # consumes operator_core; does not redefine it
  receipts.py             # turn/action/reply witnesses sharing ExecutionIdentity
```

This is a plan, not a claim that the listed new files exist.

### 4.2 Files that can move as a group with their bodies substantially unchanged

| Current file(s) | Move judgment | Evidence / required compatibility |
|---|---|---|
| `dharma_swarm/holon_system/sarathi/plan.py` | Move with the whole package | Pure deterministic module (`:1-8`); its only local dependency is package data/types. Moving it alone breaks `delegate.py`’s relative import. |
| `delegate.py`, `wake.py` | Bodies can move together after the authority defect is fixed | Relative imports remain valid as a group (`delegate.py:50`; `wake.py` local imports). External dependencies—operator core, mailbox, spine—should stay imports. Do not canonize “claim fence = lease.” |
| `brief.py`, `roster.py`, `scoreboard.py` | Move with compatibility shims | Pure formatting/roster logic. Current facade consumers are `holon_system/gateway/operator_brief.py` and `holon_system/observability/scoreboard.py`. |
| `pulse.py`, `gateway.py` | Source can move, semantics need repair before being public shell APIs | `gateway.py` is only a snapshot; `pulse.py` accepts `agents_root` but `wake.py:121-125` does not forward it. Rename snapshot or add a real ingress separately. |
| `proof.py` | Pure evaluator body can move | Keep it a pure evaluator, but replace its proof obligations before allowing a liveness promotion. |

All nine bodies plus their local imports should be staged at once. `__init__.py` should **not** move unchanged: it eagerly imports every surface (`dharma_swarm/holon_system/sarathi/__init__.py:7-40`), so importing a pure leaf drags health, bridge, model schemas, and third-party dependencies. The target initializer should be lazy or export only a minimal shell API. **[E][I]**

### 4.3 Files that require rewriting to become host-agnostic

| Current surface | Rewrite required |
|---|---|
| `scripts/runtime/sarathi_wake_daemon.py` | Put the executable body in the installed package; separate `run_one_cycle()` from supervisor control; use injected/configured state/workspace/provider/scheduler; keep the old script as a thin launcher. Its current bounded loop is useful, but “daemon” and “standing” overclaim the process contract. |
| `scripts/runtime/sarathi_proof_window.py` | Package it, replace regex kill evidence with a validated/fresh supervisor/kill receipt, require durable cycle/context/provider/reply/memory witnesses, and fail closed when persistence fails. Keep old script as launcher until callers migrate. |
| `scripts/runtime/codex_composer_wake_loop.py` | Do not copy its entire implementation. Extract a generic supervisor adapter if desired; remove the competing Sarathi profile after canonical service parity. Replace tmux and nonempty-string lease admission. |
| Sarathi `gateway.py` + `pulse.py` | Keep snapshot/status as observability, not ingress. Add a real `handle_turn` contract and transport adapters. Liveness must be derived from fresh receipts rather than hard-coded booleans. |
| `roaming_mailbox.py` adapter | Keep shared file queue, but add canonical execution identity and a consumer-side validated permit. For multi-host use, adapt the chosen A2A/NATS transport rather than treating git/file claims as fleet authority. |
| Persona/identity | No move source exists. Add a version-controlled Sarathi persona/schema with an explicitly mutable state overlay; stop requiring an out-of-repo identity merely to answer HTTP. |
| Context/memory adapters | Wrap existing canonical/shared services. Do not fork their stores under Sarathi. Ensure one turn ID spans compiled context, model attempt, reply, memory write, and receipt. |
| Service packaging | Add an installed console entry point and package-only test; then provide launchd and systemd/container adapters generated from configuration. `scripts*` is excluded from wheels (`pyproject.toml:62-64`). |

### 4.4 Files that must stay where they are

| Surface | Why it stays |
|---|---|
| `dharma_swarm/holon_bridge.py`, `holon_runtime.py` | They are shared canonical primitives. `holon_system` explicitly promises a thin front door over existing canonical organs (`dharma_swarm/holon_system/__init__.py:1-6`), while facades import the legacy homes (`holon_system/runtime/bridge.py:1-14`, `wake_cycle.py:1-3`). The sprawl guard pins `load_holon` and `holon_wake_cycle` to these exact files (`scripts/governance/sprawl_guard.py:51-62`). Sarathi should import/adapt them, not absorb them. |
| `holon_persistence.py`, `holon_health.py`, `holon_killswitch.py`, `holon_budget_guard.py` | Shared runtime leaves with non-Sarathi consumers. They may later move behind compatibility shims in a broader canonical-runtime migration, but not into a seat-specific package. |
| `operator_core/reversibility_gate.py`, `operator_core/autonomy_dial.py`, `risk_patterns.py` | Operator ruling requires a stdlib-only referee import chain (`reversibility_gate.py:24-26`; `autonomy_dial.py:25`; `risk_patterns.py:1-15`). Policy JSON names the exact modules (`scripts/governance/automerge_tier_policy.json:8-18`) and Tier2 paths (`:47-79`). Moving them casually breaks trusted-checkout evaluation. |
| `operator_core/execution_lease.py`, `operator_core/permissions.py` | Authority must remain shared, not owned by the actor it constrains. Sarathi should consume a validated lease. These two are currently omitted from Tier2 and need governance hardening, not relocation into Sarathi. |
| `context_compiler.py`, memory stores/MemoryKernel | Canonical/shared infrastructure with many non-Sarathi consumers and independent data migrations. Sarathi needs adapters and ownership selection, not copied stores. |
| `agent_runner.py`, `autonomous_agent.py`, `sandbox.py`, `diff_applier.py`, `api/main.py`, `Dockerfile` | Shared execution/deployment surfaces owned by the active Titanium track (`docs/governance/ACTIVE_TRACK.yaml:1735-1787`). |
| `docker-compose.yml`, `Dockerfile.swarm` | Shared organism deployment surfaces owned by the organism-rewire track (`docs/governance/ACTIVE_TRACK.yaml:788-819`). Add a service through that owner; do not move the files. |
| `swarm.py`, `orchestrator.py`, `pyproject.toml` | Shared composition/packaging surfaces owned by DharmaGraph (`docs/governance/ACTIVE_TRACK.yaml:917-936`). A Sarathi entrypoint change must coordinate with that track. |
| `evolution_safety.py` | Owned by the Sovereign Safety TCB (`docs/governance/ACTIVE_TRACK.yaml:1368-1399`). Evolution engines remain independent and governed. |
| `api/routers/*`, `dharma_swarm/a2a/*`, `dharma_swarm/gateway/*`, cron, providers, Living Agent Kernel | Shared protocol/runtime families. Add Sarathi handlers/adapters at their extension seams; do not rename their canonical modules into a seat namespace. |
| `.github/workflows/*`, Dockerfiles, Compose, launchd/systemd adapters | Host/platform integration must remain in conventional repository locations so packaging and operators can find it. The Sarathi package should expose commands/config consumed by these files. |

The active-track search found **no owned surface** matching canonical Sarathi, the legacy holon runtime/control leaves, its two runtime wrappers, or the relevant operator-core modules. This is not permission to move them; it is a P0 ownership gap for a safety-critical shell. **[X][I]**

```bash
sed -n '134,2019p' docs/governance/ACTIVE_TRACK.yaml | \
  rg -n 'sarathi|holon_system|holon_(bridge|runtime|persistence|health|killswitch|budget_guard)|operator_core/(execution_lease|permissions|reversibility_gate|autonomy_dial)|scripts/runtime/sarathi_(wake_daemon|proof_window)'
# exit 1: no active owned-surface match
```

`owned_surfaces` is explicitly the coordination plane (`docs/governance/ACTIVE_TRACK.yaml:118-132`). Before implementation, a Sarathi track should own `dharma_swarm/sarathi/**`, its compatibility shims, tests, and service adapters; changes to the shared rows above must coordinate with their current owners. **[E][I]**

### 4.5 Import graph and tested move order

The relevant current graph is:

```text
scripts/runtime/sarathi_{wake_daemon,proof_window}.py
  ├─ dharma_swarm.holon_system.sarathi.{plan,wake,...}
  ├─ dharma_swarm.holon_runtime
  └─ dharma_swarm.roaming_mailbox

dharma_swarm.holon_system.sarathi.__init__
  ├─ brief ─ pulse ─ dharma_swarm.holon_health
  │                    └─ dharma_swarm.holon_bridge ─ models/pydantic
  ├─ delegate ─ plan ─ operator_core
  ├─ gateway ─ brief/pulse/roster/scoreboard
  ├─ proof
  └─ wake ─ plan/delegate/pulse

dharma_swarm.holon_system.runtime.__init__
  ├─ .bridge ─ dharma_swarm.holon_bridge
  └─ .wake_cycle ─ dharma_swarm.holon_runtime
```

Static AST importer counts on the clean snapshot:

| Current module/family | Production importers | Test importers | Important direct consumers |
|---|---:|---:|---|
| Canonical Sarathi organs | 4, plus textual `holon_system.__all__` | 6 static | two facade leaves; two runtime scripts |
| `holon_bridge` | 8 (7 excluding facade) | 3 | HTTP route, terminal/DGC paths, runtime facade |
| `holon_runtime` | 5 (4 excluding facade) | 4 | Sarathi scripts, verifier/script paths, runtime facade |
| `holon_persistence` / health / kill / budget | 3 / 3 / 3 / 1 | 2 / 1 / 4 / 1 | runtime and terminal paths |
| execution lease / permissions / reversibility / dial | 2 / 1 / 4 / 4 | 1 / 2 / 1 / 3 | operator core, policy, Sarathi, generic runtime |
| `scripts.runtime*` | 21 | 26 | five packaged `holon_system` facades currently import excluded scripts |

The current `holon_system.runtime` facade passes import identity tests but has migrated zero production consumers. `runtime/__init__.py:3-4` eagerly imports both facade leaves. This is not a true Python circular import today; it is an eager fan-in/re-entry hazard. Removing/moving a legacy body before its facade is inverted makes the whole parent package unimportable. **[E][X]**

#### Executed move simulations

1. **Naive single-file Sarathi move fails.** Moving only `holon_system/sarathi/plan.py` to `dharma_swarm/sarathi/plan.py` made import of the old package fail with `ModuleNotFoundError: dharma_swarm.holon_system.sarathi.plan`, because `delegate.py:50` imports `.plan`. The new leaf itself imported. **[X]**
2. **Add-first whole-package staging works.** Copying the complete package to `dharma_swarm/sarathi/` while leaving the old package produced `add_first_imports 17 17`; old and new APIs both imported. Seven focused Sarathi/import test files returned `68 passed in 0.93s`. **[X]**
3. **Naive legacy-runtime move fails.** Moving `dharma_swarm/holon_runtime.py` to `dharma_swarm/sarathi/runtime.py`, with editable-install fallback removed from `sys.meta_path`, made `import dharma_swarm.holon_system.runtime` fail exactly at `runtime/__init__.py:4 → wake_cycle.py:3 → ModuleNotFoundError: dharma_swarm.holon_runtime`. **[X]**
4. **Checkout imports hide a wheel defect.** A package-only copy can import the current runtime facade, but `holon_system.transport.a2a_send` and `holon_system.responders.wake_profiles` fail with `ModuleNotFoundError: No module named 'scripts'`. `pyproject.toml:62-64` excludes `scripts*`; five packaged facades import those excluded modules. **[X]**

#### Required import-safe sequence

1. Admit an owned `dharma_swarm/sarathi/**` surface and specify its public turn/authority contracts.
2. Add the **entire** target package first, with a lazy/minimal initializer. Do not remove old files.
3. Add a package-owned runtime command and package-only wheel test. Reverse dependencies so old scripts import package functions, never package modules importing `scripts.runtime`.
4. Convert each old `holon_system.sarathi` module to a compatibility shim or update its five production references one by one. After each slice, import both old-first and new-first in fresh processes and run the focused tests.
5. Bind shared context, memory, invoker, transport, scheduler, and authority adapters without moving their implementations.
6. Only after zero consumers remain, remove old bodies. Keep legacy `holon_bridge`/`holon_runtime` canonical unless a separate, atomic runtime-wide migration also updates their 13 production import edges, sprawl guard, verifiers, policy, ownership, and shims.

This sequence keeps the repository importable at every intermediate commit. The obvious move-first sequences do not. **[X][I]**

## 5. The callable-surface question

“Any agent or model can call Sarathi” should mean that a caller does not need a checkout-specific Python import, a human terminal, a home-directory identity sidecar, or knowledge of Sarathi’s internal organs. One versioned handler must accept a transport-neutral turn envelope and return/deliver a correlated result:

```text
handle_turn(TurnEnvelope) -> TurnReceipt

TurnEnvelope:
  schema_version, turn_id, caller ExecutionIdentity, target="sarathi",
  message/task, history refs, capability request, idempotency key,
  authority/lease refs, deadline, reply_to

TurnReceipt:
  same turn_id + execution identity,
  accepted/rejected/completed status,
  context_bundle_ref, provider_attempt_ref, reply or reply_ref,
  effect receipts, episodic-write ref, budget use, errors
```

The same handler should be mounted behind Python, HTTP, A2A/NATS, and MCP adapters. A caller-specific adapter may authenticate or stream, but it must not substitute a separate prompt/model/agent implementation. Effects must validate `ExecutionPermit` at the consumer boundary; callability is not blanket authority. **[I]**

### Existing invocation surfaces

| Surface | What exists now | Sarathi-specific? | Executable truth | Usability verdict |
|---|---|---|---|---|
| HTTP | `POST /holon/{name}/chat` is mounted (`api/routers/holon.py:43-89`; `api/main.py:577-581`) and streams the named holon’s provider. Dynamic app inspection produced `TOTAL_ROUTES 152`, `SARATHI_ROUTES 0`. | No; dynamic name only | Requires an identity under `~/.dharma/agents/<name>`; read-only, caller-supplied history, no tools/governance/Sarathi organs (`api/routers/holon.py:1-9,34-89`). | **Closest transport to usable dialogue today**, but it is not the Sarathi shell and the container lacks Sarathi identity state. |
| Dashboard chat | `/api/agents/{agent_id}/chat` and `/api/chat` exist. | No | They use dashboard/global model paths (`api/routers/agents.py:424-516`; `api/routers/chat.py:1219-1302`). | Cosmetic/global alternatives, not acceptable aliases. |
| A2A HTTP | Agent-card and task/status/cancel/stream routes are mounted (`dharma_swarm/a2a/node_gateway.py:314-500`). | No | App creates a handlerless `A2AServer` (`api/main.py:159-185`); no-handler tasks fail (`dharma_swarm/a2a/a2a_server.py:574-584`). No Sarathi card/contact/handler. | Protocol skeleton only. |
| A2A/NATS | Generic `DS_TASKS` transport and a separate `DHARMA_A2A` mailbox gateway exist. | No | No dedicated Sarathi subject consumer; `default_contacts()` has no Sarathi (`dharma_swarm/a2a/contact_registry.py:102-155`). | Not callable as Sarathi. Choose one contract first. |
| MCP | Three servers expose 24 tools: nine generic swarm tools (`dharma_swarm/mcp_server.py:40-134`), six context tools (`dharma_swarm/dharma_context_mcp.py:976-1179`), and nine Chetana tools (`dharma_swarm/chetana/mcp_server.py:341-349`). `run_mcp_stdio.py:12-23` starts only the generic server. | No | Search found no Sarathi MCP tool/import. | Missing Sarathi adapter. |
| Installed CLI | `dharma-swarm` and `dgc` are the only console scripts (`pyproject.toml:58-64`). Generic `dgc agent talk NAME` and `dgc agent run NAME` are declared (`dharma_swarm/dgc_cli.py:629-654,1615-1631`). | No; dynamic name | They call excluded checkout scripts (`dharma_swarm/terminal_commands/agents.py:101-129`). `holon_run.py` loads the generic identity/provider and self-task, passes `cap_usd=0.0`—explicitly unbounded—and no `planned_action` (`scripts/holon_run.py:32-75`; `dharma_swarm/holon_budget_guard.py:25-31`). It bypasses Sarathi plan/delegate/proof organs. | Human CLI, checkout-only implementation; not a stable agent API. |
| Direct scripts | `sarathi_wake_daemon.py`, `sarathi_proof_window.py`, and the generic wake script all execute `--help` successfully. | Two are canonical-adjacent | The Sarathi scripts are bounded and excluded from the installed wheel. | Useful diagnostics, not ingress/reply. |
| Holon-system CLI/API inventories | `command_names()` claims `sarathi brief/pulse`; `route_names()` claims chat/history (`dharma_swarm/holon_system/cli/commands.py:1-5`; `dharma_swarm/holon_system/api/routes.py:1-5`). | Names only | No CLI wiring implements brief/pulse; dynamic route inspection found no `/holon/{name}/chat/history`. | Phantom inventory, not invocation. |
| Python | `dharma_swarm.holon_system.sarathi` exports 17 symbols (`__init__.py:7-40`). | Yes | Imports and focused tests pass, but callers must inject BootPack, mailbox, sinks, invoker, state, and schedule; no `handle_turn` or reply contract exists. | **Closest surface to actual Sarathi organs**, but only a component API. |

### Closest usable path today

- For **a conversation reply**, generic `POST /holon/sarathi/chat` is closest because it is mounted HTTP and performs a real provider stream. It works only if an external identity is provisioned and remains an independent, read-only holon chat. **[E][I]**
- For **the code actually called Sarathi**, the Python package is closest because its plan/delegate/wake/proof organs are real and tested. It is not a shell boundary. **[E][I]**
- For **agent-to-agent interoperability**, A2A is the right existing protocol family, but it is not usable until Sarathi owns a card, handler, durable consumer, and reply path under one chosen NATS/A2A contract. **[I]**

No current surface satisfies all four operator constraints simultaneously: mutable/versioned body, stable non-human call, Mac+VPS service portability, and a persistent shell with cognition/effects/memory. **[I]**

## 6. Top 10 blockers

Ordered by how much downstream integration each blocks:

1. **There is no call-to-reply composition root.** `make_wake_work_fn()` composes backlog planning and delegation (`dharma_swarm/holon_system/sarathi/wake.py:89-182`), while the only HTTP reply path independently calls `holon_bridge` (`api/routers/holon.py:43-89`). No function owns `ingress → identity → context → model → tools → reply → memory → receipt`. Until that exists, every adapter would call a different “Sarathi.”

2. **Sarathi has no canonical version-controlled persona or registered address.** The generic chat loader requires an out-of-repo `~/.dharma/agents/<name>/identity.json` (`dharma_swarm/holon_bridge.py:32,106-149`); `default_contacts()` has no Sarathi (`dharma_swarm/a2a/contact_registry.py:102-155`); there is no tracked Sarathi A2A card/consumer. Restart identity and fleet callability are therefore undefined.

3. **Canonical Sarathi has no cognition.** Its planner explicitly calls no model (`dharma_swarm/holon_system/sarathi/plan.py:1-8,105-180`), and its only runtime wrapper supplies `invoker=None` (`scripts/runtime/sarathi_wake_daemon.py:22-31,363-380`). A deterministic backlog mapper is not an agent shell.

4. **Canonical Sarathi has neither compiled context nor owned memory.** `BootPack` is only injected roster/backlog/dedup/audit/lodestone data (`dharma_swarm/holon_system/sarathi/plan.py:22-38`). The canonical compiler is wired elsewhere (`dharma_swarm/orchestrator.py:1148-1215`), and the optional holon memory pack is not supplied (`dharma_swarm/holon_runtime.py:127-150`). Persistence across turns is therefore not semantic continuity.

5. **There is no bound effector or reply consumer.** Direct invoke requires an injected invoker; otherwise work becomes an isolated file task (`dharma_swarm/holon_system/sarathi/delegate.py:277-326`). Existing roaming workers neither target that queue nor enforce Sarathi metadata (`dharma_swarm/roaming_poller.py:118-148`). No canonical path turns a Sarathi decision into a governed tool result and sends it to the caller.

6. **Authority is unsound at the mailbox boundary.** `NEEDS_LEASE` is omitted from hard-gated classes (`dharma_swarm/holon_system/sarathi/delegate.py:48-52`), then the claim fence is labeled an execution lease (`:298-326`) without calling the actual validator (`dharma_swarm/operator_core/execution_lease.py:187-252`). The executed counterexample dispatched and claimed `needs_lease` work with a null lease ID.

7. **The “unattended proof” is vacuous and persistence is fail-open.** Persistence exceptions are swallowed (`dharma_swarm/holon_runtime.py:45-50`); proof audits only `dispatched` rows (`dharma_swarm/holon_system/sarathi/proof.py:22-73`); the proof window is propose-only (`scripts/runtime/sarathi_proof_window.py:168-195`). Fourteen cycles passed with no event log, no tasks, and an impossible regex-shaped kill timestamp.

8. **No portable standing host runs canonical Sarathi.** The wrapper says an external scheduler must re-invoke it (`scripts/runtime/sarathi_wake_daemon.py:51-54`); the generic standing path requires tmux (`scripts/runtime/codex_composer_wake_loop.py:1231-1261`); the two Sarathi scripts are excluded from wheels (`pyproject.toml:58-64`); no Sarathi service artifact exists.

9. **Budget and kill guarantees do not cover downstream autonomous work.** The daemon admits that its cap covers only ~$0 direct spend and not enqueued workers (`scripts/runtime/sarathi_wake_daemon.py:22-31,313-329`). The generic `dgc agent run` passes an explicitly unbounded zero cap and no planned action (`scripts/holon_run.py:66-75`; `dharma_swarm/holon_budget_guard.py:25-31`). A portable shell needs one transitive action/budget/kill authority across the turn and every child effect.

10. **Self-modification and consolidation have no owned, import-safe lane.** Eight independent evolution families exist, none callable by Sarathi; several bypass the guarded Darwin promotion path (`dharma_swarm/autoresearch_loop.py:434-507`, `dharma_swarm/build_engine.py:166-425`). No active `owned_surfaces` glob covers Sarathi, its wrappers, or shared authority leaves, while naive moves break facade imports and shared canonical paths are policy-pinned (`scripts/governance/sprawl_guard.py:51-62`).

The first closure slice should address blockers 1, 2, 3, 5, and 6 together: an installed `handle_turn`, one versioned persona/card, one actual invoker, one reply adapter, and consumer-side validated execution permits. Adding another scheduler or another store before that would increase scatter without creating a shell. **[I]**

## 7. Verification ledger

### Focused source tests

Run against the exact `origin/main` export:

```bash
.venv/bin/python -m pytest -q \
  tests/test_holon_system_imports.py \
  tests/test_holon_persistence.py \
  tests/test_holon_budget_guard.py \
  tests/test_holon_killswitch.py \
  tests/test_holon_health.py \
  tests/test_holon_runtime.py \
  tests/test_holon_runtime_integration.py \
  tests/test_autonomy_dial.py \
  tests/test_reversibility_gate.py \
  tests/test_operator_core_permissions.py \
  tests/test_sarathi_plan.py \
  tests/test_sarathi_delegate.py \
  tests/test_sarathi_wake.py \
  tests/test_sarathi_proof.py \
  tests/test_sarathi_proof_window.py \
  tests/test_sarathi_wake_daemon.py \
  tests/test_codex_composer_wake_loop.py

# 158 passed in 2.47s
```

Passing tests establish current intended unit behavior; they do not refute the executed authority/persistence counterexamples because those cross-module obligations are absent from the fixtures. **[X][I]**

### Safe one-cycle command

```bash
DGC_SARATHI_AUTONOMY=shadow \
  .venv/bin/python scripts/runtime/sarathi_wake_daemon.py \
  --cycles 1 \
  --state-root /private/tmp/sarathi-census-smoke/state \
  --agents-root /private/tmp/sarathi-census-smoke/agents \
  --json

# exit 0; status=ran; cycles_run=1; autonomy_level=shadow;
# wake_loop_active=false; spent_usd=0; no dispatch
```

This proves the bounded wrapper executes portably with explicit roots. It does not prove a standing shell. **[X]**

### Dynamic route and tool inventory

```text
api.main.app: TOTAL_ROUTES 152, SARATHI_ROUTES 0
MCP servers: 3
MCP tools: 9 + 6 + 9 = 24
Sarathi-specific MCP tools: 0
Installed console scripts: dharma-swarm, dgc
Sarathi-installed console scripts: 0
```

### Move probes

```text
whole-package add-first: old exports=17, new exports=17
focused add-first tests: 68 passed in 0.93s
single plan.py move: old package import FAILED (missing old .plan)
legacy holon_runtime move: holon_system.runtime import FAILED at wake_cycle.py:3
package-only transport facade: FAILED (No module named 'scripts')
```

### Runtime counterexample command

The temporary fixture monkey-patched only the persistence writer and kill-receipt reader; production classification, delegation, mailbox claiming, wake, and proof evaluation remained unchanged:

```bash
PYTHONPATH=/private/tmp/sarathi_shell_census_origin_main_9d792ceacef3 \
  .venv/bin/python /private/tmp/sarathi_census_repros.py

# exit 0
# needs_lease task: dispatched, claimed, execution_lease_id=null
# persist writer raised once: wake status=ran
# persist writer raised 14 times: proof passed=true, event_log_exists=false
```

The causes are independently reproducible from cited source: `GATED_CLASSES` at `delegate.py:52`, mailbox enqueue at `:298-326`, fail-open `_persist` at `holon_runtime.py:45-50`, receipt-bearing statuses at `proof.py:22-26`, and propose-only window at `sarathi_proof_window.py:168-195`.

## Final consolidation decision

Create `dharma_swarm/sarathi/` as the single **seat composition root**, not as a dump of shared implementations. Stage the existing Sarathi organ package add-first, package the runtime, add a real turn handler/persona/A2A card, and wire existing context, memory, provider, tools, scheduler, and governance through adapters. Keep shared engines and policy-pinned modules in place. Require a single execution identity across ingress, context, model, effect, reply, memory, and proof, and require an actual validated execution permit immediately before every effect.

Until that path passes a real message-to-reply-and-memory integration test under both a Mac supervisor and a Linux/VPS supervisor, the truthful status remains:

```text
SARATHI = GENESIS SOURCE + DETERMINISTIC ORGANS + BOUNDED WRAPPERS
SARATHI != PERSISTENT AGENT SHELL
```
