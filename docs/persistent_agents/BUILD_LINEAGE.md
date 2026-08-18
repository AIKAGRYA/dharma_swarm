# Sarathi / Holon / Persistent-Agent Build Lineage

**Status:** dated history report and branch map; not runtime or liveness
authority

**Measured:** 2026-08-04

**Main comparison procedure:** resolve `origin/main` immediately before running
the classification commands below; this pre-landing report does not predict a
future integration SHA.

**Governance dependency:** PR #1215 landed on main as squash commit
`d5fec94eab54f1b924c1fd659b36240b32ca9b39`. The exact P0 integration base is
intentionally unbound here and must be remeasured immediately before landing.

This file answers the historical question: did the repo spend months trying to
build a custom Hermes/OpenClaw-class persistent agent, and how do the resulting
systems relate? **Yes, that intent is visible in code and Git history.** What the
history does *not* show is one earlier commit where every capability became one
coherent product. The work landed as several independent lineages; the August
P0 is the first explicit `dharma_swarm.sarathi` public composition-root
contract.

This report does not replace the dated source artifacts it cites. It indexes
them and classifies their Git state so a design document cannot masquerade as a
landed runtime.

## Status vocabulary

| Status | Test |
|---|---|
| **LANDED** | `git merge-base --is-ancestor <commit> origin/main` exits 0. |
| **CURRENT BRANCH** | Commit or working-tree source is present on the P0 branch but not an ancestor of `origin/main`. |
| **UNMERGED / PARALLEL** | Commit is reachable from another ref but `git merge-base --is-ancestor <commit> origin/main` exits nonzero. |
| **ASPIRATION** | A design or deferred adapter has no complete tested implementation on the current branch. |

## Chronology: March through August 2026

| Date | Status | Build / commit | What it actually established | What it did **not** establish |
|---|---|---|---|---|
| 2026-03-17 | **LANDED** | `94191530f` — “New subsystems: autonomous agent…” | Introduced `AutonomousAgent` and `PersistentAgent`. The former is a ReAct/model/tool agent ([source:386-423](../../dharma_swarm/autonomous_agent.py#L386-L423)); the latter composes it with a task queue and witness state ([source:117-175](../../dharma_swarm/persistent_agent.py#L117-L175)). | No Sarathi identity, one-root API, portable service, or unified authority boundary. |
| 2026-03-20 | **LANDED** | `7c3d42817` — “Hard Memory Infrastructure” | Added vector storage, organism memory, and the sleep-time agent; `VectorStore` and `SleepTimeAgent` remain real code ([vector:214](../../dharma_swarm/vector_store.py#L214), [sleep agent:59](../../dharma_swarm/sleep_time_agent.py#L59)). | It did not make one agent own all memory or connect that memory to a Sarathi turn. |
| 2026-03-26 | **LANDED** | `0c7fec942` — roaming dispatch daemon and control-plane doctrine | Explicitly put OpenClaw on remote hosts, local Codex, VPS Claude Code, and future Hermes behind one `dharma_swarm` organism with shared identity, task, runtime-truth, memory, and governance planes ([spec:11-26](../plans/2026-03-26-roaming-control-plane-spec.md#L11-L26)). The dispatch daemon remains real source ([`roaming_dispatch_daemon.py`](../../dharma_swarm/roaming_dispatch_daemon.py)). | It routed mailbox tasks but did not land the later model-powered roaming responder or a Sarathi turn API. |
| 2026-03-27 | **LANDED** | `f57660c9f` — self-evolving organism runtime | Made “one runtime, no second orchestration center” an explicit invariant and defined a governed research→grade→attribute→mutate→promote/rollback loop ([spec:5-9](../plans/2026-03-26-self-evolving-organism-master-build-spec.md#L5-L9), [spec:29-41](../plans/2026-03-26-self-evolving-organism-master-build-spec.md#L29-L41), [invariants:81-96](../plans/2026-03-26-self-evolving-organism-master-build-spec.md#L81-L96)). | It evolved the organism substrate; it did not compose every persistent-agent element into Sarathi. |
| 2026-03-27 | **UNMERGED / PARALLEL** | `57b6bfe66` on `origin/roaming-fixall-20260326` | Added the concrete self-starting `roaming_llm_worker.py`, launcher, and tests. Inspect with `git show --stat 57b6bfe66`. | The worker is absent from current HEAD. The landed doctrine/dispatch daemon must not be mistaken for a landed model responder. |
| 2026-04-04 | **LANDED** | `2e6406a28` — per-agent mini-cron | Added the `PersistentAgent` mini-cron and recurring wake behavior. Current construction registers the cron at [`persistent_agent.py:173-205`](../../dharma_swarm/persistent_agent.py#L173-L205), and the daemon loop remains at [`:580-625`](../../dharma_swarm/persistent_agent.py#L580-L625). | A mini-cron is a scheduler inside the classic stack, not a portable Sarathi heartbeat. |
| 2026-05-20 | **UNMERGED / PARALLEL** | `39291ad3d` on `origin/research/persistent-agents-deepdive-2026-05` | A comparative landscape commit with 12,424 insertions explicitly studied Hermes Agent, OpenClaw, Letta, AutoGPT, and other persistent-agent products. Reproduce its file list with `git show --stat 39291ad3d`. | Research alone neither landed on main nor integrated a shell. |
| 2026-05-28 | **LANDED** | `64e20c8cc` — Hermes persistent-agent index task | Recorded the explicit P0 request for a repository-wide persistent-agent index in [`hermes_full_persistent_agent_index_2026-05-28.md`](../agent_tasks/hermes_full_persistent_agent_index_2026-05-28.md). | A task document is not the requested census and not runtime code. The later August index still says the P0 remained open ([report:58-70](../reports/hermes_persistent_agent_index_2026-08-01.md#L58-L70)). |
| 2026-06-11 (authored 06-06) | **LANDED** | `6b9b51e1b` — Living Agent Kernel OS slice | Added the durable wake/lease/recovery/promotion/tool/proof family; the principal class is [`LivingAgentKernel`](../../dharma_swarm/operator_core/living_agent_kernel.py#L1199). | The kernel was a separate execution/governance family, not a Sarathi product root. Its [wake lease](../../dharma_swarm/operator_core/living_agent_kernel.py#L1030-L1133) is also distinct from the [content-hashed execution lease](../../dharma_swarm/operator_core/execution_lease.py#L116-L252). |
| 2026-06-12 (docs created 06-08) | **LANDED** | `b659713c6` — sovereign-Holon historical design home | Locked the “sovereign agent + cell in the organism” intent and explicitly required composition rather than a new registry/daemon/store ([design:17-27](../sovereign_holons/README.md#L17-L27), [boundary:77-83](../sovereign_holons/README.md#L77-L83)). It also documented the missing record→runtime bridge ([gap:61-66](../sovereign_holons/README.md#L61-L66)). | The documents did not prove a living service. The folder now declares itself historical ([notice:1-14](../sovereign_holons/README.md#L1-L14)). |
| 2026-06-11/12 | **LANDED** | `76702ce4d`, merged by PR #585 at `9c76b2106` | Added the direct governed Holon bridge/runtime/persistence/health/kill/budget/compass substrate. The wake cycle begins with explicit kill and budget checks at [`holon_runtime.py:53-80`](../../dharma_swarm/holon_runtime.py#L53-L80). | It did not call the later Sarathi planner/delegator or present one transport-neutral Sarathi turn. |
| 2026-07-09 | **LANDED** | PR #821 merge `0beef7584` | Removed the duplicate repo-root `holon/` fork, added the thin `holon_system` facade, and added the first Sarathi brief/pulse/roster/gateway projections. The facade declares that shared runtime primitives remain in existing modules ([source:1-12](../../dharma_swarm/holon_system/__init__.py#L1-L12)). | The projection was intentionally not an alive agent: current gateway output still pins both liveness booleans false ([source:15-25](../../dharma_swarm/holon_system/sarathi/gateway.py#L15-L25)). |
| 2026-07-31 | **LANDED** | PR #1167 merge `c5653967e` | Added the Sarathi autonomy dial, planner, delegator, wake unit, proof harness, and operator ruling. One wake unit now builds a plan, delegates, sweeps responses, writes a brief, and closes back ([wake:89-164](../../dharma_swarm/holon_system/sarathi/wake.py#L89-L164)). | The planner explicitly uses no model call ([plan:1-8](../../dharma_swarm/holon_system/sarathi/plan.py#L1-L8)), and the lane did not establish a stable general ingress/reply API. |
| 2026-08-01 | **LANDED** | PR #1170 merge `04f9bd5e8` | Added the bounded `sarathi_wake_daemon.py` wrapper. It binds the organs to `holon_wake_cycle`, persists reports/spend, and runs a requested number of cycles ([source:343-393](../../scripts/runtime/sarathi_wake_daemon.py#L343-L393)). | Its own contract delegates standing scheduling to an external caller ([source:51-57](../../scripts/runtime/sarathi_wake_daemon.py#L51-L57)); it is not a universal message surface. |
| 2026-08-03 | **LANDED** | PR #1207 merge `b65030b7d` | Added MCP tools `sarathi_status` and `sarathi_roster` before generic swarm bootstrap ([source:134-169](../../dharma_swarm/mcp_server.py#L134-L169)). | Both are inspection-only; neither accepts a message, invokes Sarathi cognition, or dispatches an effect. |
| 2026-08-03 | **LANDED** | PR #1198 merge `f654c3908` — verified-partial index | Added the broad Hermes persistent-agent index and move-plan evidence. The report's core finding is many correct organs with almost no composition ([report:106-115](../reports/hermes_persistent_agent_index_2026-08-01.md#L106-L115)). | Its mandatory errata lists missed systems and false claims, and its proposed three-PR build plan is explicitly non-executable as written ([errata:10-55](../reports/hermes_persistent_agent_index_2026-08-01.md#L10-L55)). |
| 2026-08-03 | **UNMERGED / PARALLEL** | `df4ee41cc` on `origin/claude/sarathi-autonomy-build-vyr998` | Added a candidate `holon_system.sarathi.memory` recall adapter plus tests. Inspect with `git show --stat df4ee41cc`. | It is not on `origin/main` or the P0 branch; no current code may assume the module exists. |
| 2026-08-03 | **UNMERGED / PARALLEL** | `90fa0025a` on `origin/census/sarathi-shell-20260802` | Added a behavior-first census/navigation umbrella after finding the August index omissions. Inspect its permanent-map draft with `git show 90fa0025a:docs/persistent_agents/README.md`. | The commit is not on `origin/main`; paths that exist only there must not be linked as if landed. |
| 2026-08-04 | **LANDED** | PR #1215 squash merge `d5fec94e` | Admitted `dharma_swarm/sarathi/**`, exact P0 tests, the atomic shared-state seam, this documentation surface, and its docs-index pointer under `organism-rewire-2026-07` ([ownership:822-837](../governance/ACTIVE_TRACK.yaml#L822-L837), [item 11:927-930](../governance/ACTIVE_TRACK.yaml#L927-L930)). The active contract fixes one stable `handle_turn` composition root ([P0:14-30](SARATHI_COMPOSITION_ROOT_P0.md#L14-L30)). | Governance and a spec are not proof that the P0 implementation works or has landed. The source/tests must pass and the P0 branch must merge before the implementation becomes **LANDED**. |
| 2026-08-04 | **CURRENT BRANCH** | P0 implementation change / branch | Added the inert public package and types ([`__init__.py:1-38`](../../dharma_swarm/sarathi/__init__.py#L1-L38), [`contracts.py:15-212`](../../dharma_swarm/sarathi/contracts.py#L15-L212)), repo-owned identity ([`identity.py:41-57`](../../dharma_swarm/sarathi/identity.py#L41-L57)), one message→cognition→reply→receipt turn path ([`shell.py:102-233`](../../dharma_swarm/sarathi/shell.py#L102-L233)), repository provider adapter ([`runtime_provider.py:38-121`](../../dharma_swarm/sarathi/adapters/runtime_provider.py#L38-L121)), and shared `RuntimeStateStore` adapter ([`runtime_state.py:20-166`](../../dharma_swarm/sarathi/adapters/runtime_state.py#L20-L166)). | It deliberately executes no effects ([`shell.py:58-72`](../../dharma_swarm/sarathi/shell.py#L58-L72)); it has no HTTP/MCP/A2A/CLI mount, standing supervisor, or self-modification adapter, and remains non-landed until its PR merges. |
| after P0 | **ASPIRATION** | transport, memory retrieval, effects, heartbeat, evolution adapters | The intended product class is a full repo-owned, mutable, portable persistent shell callable by any agent/model. | These capabilities remain explicitly deferred in the P0 contract ([P0:98-107](SARATHI_COMPOSITION_ROOT_P0.md#L98-L107)); do not write “full Hermes/OpenClaw equivalent” yet. |

## What the history proves

The product intention did not appear suddenly in August:

1. **March–April built a real classic shell and one-organism doctrine:**
   persistent wake, model reasoning, memory, tools, mini-cron, plus explicit
   OpenClaw/Hermes integration through one shared plane.
2. **May deepened the comparison:** comparative research and the P0 census task
   made the missing product-level composition increasingly explicit.
3. **June built stronger shared organs:** the Living Agent Kernel and direct
   governed Holon runtime introduced durable wake, authority, and proof
   machinery while the sovereign-Holon corpus prohibited a parallel substrate.
4. **July created the named Sarathi seat:** facade collapse, deterministic
   planning/delegation/proof, an autonomy dial, and a bounded wake command.
5. **August exposed the integration failure and chose a root:** the inventories
   showed that the capabilities existed but were independent; the P0 chose
   `dharma_swarm/sarathi/` as the one public composition boundary.

That is a coherent lineage toward a custom Hermes/OpenClaw-class product. It is
not evidence that the complete product already exists.

## Convergence map

```text
March classic PersistentAgent / AutonomousAgent ───────────┐
March hard memory + later MemoryKernel / ContextCompiler ──┤
June Living Agent Kernel authority/effect/proof family ────┤
June direct governed Holon runtime ─────────────────────────┤ adapters
July holon_system.sarathi organs and wake wrapper ──────────┤
Existing provider / A2A / MCP / RuntimeState services ──────┘
                                                            |
                                                            v
                                              dharma_swarm.sarathi
                                               one public turn API
```

The arrows mean “candidate or selected shared dependency,” not “already wired.”
The P0 intentionally excludes live effects and defers memory/context/transports.

## What moves and what stays

| Decision | Files | Reason |
|---|---|---|
| **Create/add** | `dharma_swarm/sarathi/**` | Stable product contract, repo identity, composition, adapters, and receipt semantics belong together. |
| **Keep and adapt** | `dharma_swarm/holon_system/sarathi/**` | Existing public exports and runtime wrappers depend on these organs; P0 requires compatibility ([P0:51-54](SARATHI_COMPOSITION_ROOT_P0.md#L51-L54)). |
| **Keep shared** | top-level `holon_*.py`, `runtime_state.py`, `memory_kernel/**`, `context_compiler.py`, `operator_core/living_agent_kernel*.py`, providers, A2A, schedulers, tools | They serve the wider organism and have independent owners/importers. Copying them into Sarathi would create forks. |
| **Do not execute as a move script** | [`HOLON_CONSOLIDATION_PLAN_2026-08-01.md`](../plans/HOLON_CONSOLIDATION_PLAN_2026-08-01.md) | It records that no files were moved and reproduces eager-import failures in the naive order ([plan:16-40](../plans/HOLON_CONSOLIDATION_PLAN_2026-08-01.md#L16-L40)). |

The code can therefore have one **public home** without forcing all reusable
organs into one physical directory.

## Parallel work that must not be silently merged by assumption

| Ref | Useful content | Safe treatment |
|---|---|---|
| `origin/research/persistent-agents-deepdive-2026-05` @ `39291ad3d` | Hermes/OpenClaw landscape and cached source survey. | Historical research input only; review before selective salvage. |
| `origin/roaming-fixall-20260326` @ `57b6bfe66` | Self-starting model-powered roaming worker, launcher, and tests. | The doctrine landed but this responder did not; re-measure before adapting it through the P0 root. |
| `origin/claude/sarathi-autonomy-build-vyr998` @ `df4ee41cc` and descendants | Governed memory-recall candidate and fixes. | Re-measure and adapt through the P0 port; do not import the absent module. |
| `origin/feat/sarathi-apex-reconcile` @ `e7856fed9` | Richer `holon_system.sarathi.gateway` candidate with evaluate/execute and receipt paths. | Re-measure authority and host assumptions; salvage selectively through P0 rather than restoring it wholesale. |
| `origin/census/sarathi-shell-20260802` @ `90fa0025a` | Behavior-first census and prior umbrella navigation. | Evidence source until separately landed; its destination claims are not current code. |

## Reproduce the branch classification

```bash
git fetch origin
MAIN_REF=origin/main

for COMMIT in \
  94191530f 7c3d42817 0c7fec942 f57660c9f 57b6bfe66 \
  2e6406a28 64e20c8cc 6b9b51e1b b659713c6 76702ce4d \
  0beef7584 c5653967e e7856fed9 \
  04f9bd5e8 b65030b7d f654c3908 \
  39291ad3d df4ee41cc 90fa0025a \
  d5fec94e; do
  if git merge-base --is-ancestor "$COMMIT" "$MAIN_REF"; then
    printf 'LANDED %s\n' "$COMMIT"
  else
    printf 'NOT_ON_MAIN %s\n' "$COMMIT"
  fi
done

git show -s --format='%H %cs %s' \
  94191530f 0c7fec942 f57660c9f 57b6bfe66 2e6406a28 \
  6b9b51e1b b659713c6 76702ce4d e7856fed9 \
  0beef7584 c5653967e 04f9bd5e8 b65030b7d \
  f654c3908 d5fec94e

test -e dharma_swarm/persistent_agent.py
test -e dharma_swarm/autonomous_agent.py
test -e dharma_swarm/operator_core/living_agent_kernel.py
test -e dharma_swarm/holon_runtime.py
test -e dharma_swarm/holon_system/sarathi/__init__.py
test -e scripts/runtime/sarathi_wake_daemon.py
test -e docs/persistent_agents/SARATHI_COMPOSITION_ROOT_P0.md
```

When the P0 branch lands, update this report's comparison point and promote only
the rows whose ancestry and executable tests prove **LANDED**.
