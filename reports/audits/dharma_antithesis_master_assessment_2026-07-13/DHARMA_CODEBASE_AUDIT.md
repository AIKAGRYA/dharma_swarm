# Dharma Swarm and DharmaGraph Codebase Audit

**Evidence freeze:** 2026-07-13  
**Authoritative remote baseline:** `origin/main` = `c14b950bc5009f2200d9425155010be508ead981` (`feat(onboarding): implement WP-O4 closeout semantics and CI binding (#912)`)  
**Deep source/test base:** `debff832ac4cbf7b385664d00f184f0ffdb909c4`, followed by a path-level diff and current-main rerun. The only intervening commit changed onboarding/docops surfaces, not the audited graph/runtime defect paths. The 188-test graph suite was rerun at `c14b950…`.  
**Document role:** dated report, subordinate to canonical governance, code, runtime owners, tests, and external receipts.

## 1. Custody and baseline

The directory named `/Users/dhyana/dharma_swarm` is **not** authoritative current main. At freeze time it was on `agent/magpie-seed`, HEAD `5207a2fb7bdd312ee1f53057e5daa27707f1b2ba`, 664 commits behind and 56 ahead of current main, with 20 dirty paths plus untracked state. It also hosted the observed live daemon. No user changes were modified.

The audit began in a clean detached worktree at `/private/tmp/ds_funding_adjudication_20260713`, moved from `debff832…` to exact current `c14b950…` after upstream advanced. That ephemeral worktree was later removed by concurrent cleanup, so final exact-current admission, focused tests, entry-point smokes, and all twelve counterexamples were rerun in a fresh clean detached clone at `/private/tmp/ds_final_validation_20260713`. The relevant defect paths are byte-identical between the two SHAs; the commit SHA, durable receipts, and report-local harness—not either temporary path—are the evidence identities.

### Worktree/branch findings

| Location or ref | State relative to `c14b950…` | Assessment |
|---|---|---|
| `/private/tmp/ds_funding_adjudication_20260713` | clean, detached current main; later removed | initial authoritative audit checkout |
| `/private/tmp/ds_final_validation_20260713` | clean, detached current main | final exact-current validation context; ephemeral |
| `/Users/dhyana/dharma_swarm` | 664 behind / 56 ahead; dirty | user/live development seat, not release truth |
| `ds_dharmagraph_autopsy_20260708` | 207 behind / 0 ahead; dirty/untracked spec | obsolete history; proposal is unratified |
| `ds_dharmagraph_parity_gauntlet_20260711` | 31 behind / 19 squash-diverged | relevant tree incorporated by squash; not canonical |
| neutral-core and old LangGraph verifier refs | fully ancestral or obsolete | no unique current runtime asset |

There were 32 open worktrees against a declared budget of roughly 14. That is operational state sprawl and creates custody ambiguity even when individual branches are useful.

### Runtime and dependency assumptions

- `pyproject.toml` requires Python `>=3.11`; the reusable repository virtual environment reports Python 3.13.12.
- LangGraph is an optional/test-oracle dependency pinned at 1.2.4; current local parity environment also reported `langgraph-checkpoint==4.1.1` and `langgraph-checkpoint-sqlite==3.1.0`.
- Primary CLIs are `dharma-swarm` and `dgc` (`pyproject.toml` entry points). The operator API is launched by `run_operator.sh`; the live daemon target resolves to `dgc orchestrate-live`.
- Exact current main's `Makefile` does not parse under the host's stock GNU Make 3.81. This prevents the repository-mandated `make onboard` from reaching Python at all.
- A clean older baseline that still parsed fell back to `/usr/bin/python3` 3.9.6 and failed evaluating a Pydantic annotation. A supported 3.13 interpreter rendered onboarding but reported blocked admission. The current parse regression supersedes that as the first local failure.

### CI at the freeze

The final GitHub check-run refresh for `c14b950…` showed successful Python 3.11/3.12, CodeQL, Semgrep, gitleaks, dashboard, gauntlet tier 1, kernel/Hypothesis, manifest, hermetic-lock, and governance checks; one duplicate `Quality ratchet` run remained in progress. `Onboarding admission parity` was **skipped** on the observed merge/main runs (the API returned duplicate main/PR-associated checks). CI success therefore does not falsify the locally reproduced Make 3.81 parse failure.

## 2. Ground-truth system map

### Supported entry points and execution traces

```text
Operator surfaces
  dgc / dharma-swarm / FastAPI dashboard / orchestrate-live
          |
          +--> TaskBoard (SQLite/WAL task FSM)
          +--> Orchestrator (routing, dispatch, settlement)
          |       |
          |       +--> spine invocation / runtime identity / receipts
          |       +--> graph.DurableInvoker (conditional effect ownership)
          |       +--> providers / runtime_provider / model hierarchy
          |
          +--> SwarmManager
          |       +--> graph reconciler at boot/tick
          |       +--> failure propagation, agents, signal/stigmergy loops
          |
          +--> optional Organism root (off by default in canonical API)
          +--> runtime state, dashboards, NATS/A2A and other projections

DharmaGraph neutral candidate
  GraphBuilder -> CompiledGraph -> scheduler/channels/routing/effects
       |                 |
       |                 +--> checkpoint/persistence JSON kernel
       |                 +--> deterministic test effects
       |
       +--> tests and parity gauntlet; no production hot-path owner

Other execution/state surfaces still live
  workflow.py / CompiledWorkflow / AgentRunner
  topology_genome.py
  loop checkpoint.py
  langgraph_parity clone and adapters
  graph_store / graph_nexus / claim_graph / ontology graphs (knowledge semantics)
```

The knowledge-graph modules are not automatically duplicate runtime schedulers; they solve different semantic/storage problems. The duplication problem is narrower and still serious: multiple workflow executors and at least four checkpoint/persistence mechanisms coexist without one production owner.

### Entry-point custody and smoke boundary

All traces below are at `c14b950…`. Help/import/factory smokes were rerun from a clean detached checkout with `PYTHONPATH` bound to that tree; they intentionally did not start providers or mutate the user's runtime state.

| Public surface | Static call path | Mutation/effect boundary | Safe execution result and unresolved boundary |
|---|---|---|---|
| `dharma-swarm` | `pyproject.toml` → `dharma_swarm.cli:app` → `_get_swarm()` → `SwarmManager.init()` | mutating commands reach agent spawn, TaskBoard, memory, evolution, and state directories | `python -m dharma_swarm.cli --help` exited 0 and enumerated commands; no mutating command or full loop was run |
| `dgc` | `pyproject.toml` → `dharma_swarm.dgc_cli:main` → `dharma_swarm.terminal_commands.*` | broad dispatcher can launch daemons, providers, task/evolution paths, remote/VPS tools, and local services | `python -m dharma_swarm.dgc_cli --help` exited 0; command breadth is verified, individual command safety/custody is not |
| `dgc orchestrate-live` | `dgc_cli.py` → `terminal_commands/lifecycle.py:cmd_orchestrate_live` → `orchestrate_live.py:orchestrate` → `SwarmManager.tick()` | TaskBoard promotion, dispatch, providers, receipts, evolution, and recurring state mutation | not launched from current main; the observed live process was from dirty/stale `5207a2…`, so it is not current-main execution proof |
| operator API | `run_operator.sh` → `api.main:app/lifespan` → `SwarmManager.init()` plus mounted HTTP/WS/A2A routers | lifespan creates runtime owners; routes can mutate tasks, chat/session state, evolution, and projections | importing `api.main:app` exited 0 and exposed 151 routes; full lifespan was not started; the isolated WebSocket auth counterexample was executed |
| web dashboard | `scripts/dashboard_ctl.sh` / launchd surfaces → API and `dashboard/package.json` Next.js app | presentation/client state plus API calls; service scripts supervise local processes | dashboard CI was green at freeze; no current-main browser, build, or service smoke was run |
| MCP | `dharma_swarm.mcp_server:create_mcp_server` → lazy `SwarmManager.init()` on first tool call | tools include spawn, task creation, memory writes, and graph/telos reads | factory construction returned `Server`, exit 0; no project-script launcher, transport handshake, or mutating tool call was verified |
| A2A HTTP/NATS | `api.main` gateway initialization → `a2a_server.py` / `node_gateway.py` / `nats_transport.py` → runtime spine and task owners | inbound/outbound task messages, NATS, receipt/claim state, and remote effects | `A2AServer()` construction exited 0; no exact-current-main HTTP or NATS roundtrip was run |

These smokes prove import/registration only. They do not promote a surface to operational maturity, and the failed repository admission remains the first supported local door.

### DharmaGraph composition

| Layer | Current implementation | Actual status |
|---|---|---|
| Neutral graph semantics | `graph/{types,state,channels,routing,compiler,scheduler,effects,errors}.py` | candidate/test-only; coherent scoped engine |
| Thread/checkpoint persistence | `graph/{checkpoint,persistence,persistence_adapter,persistence_runtime}.py` | prototype; sequential restart works, concurrent updates do not |
| Production dispatch durability | `graph/{durable_invoker,receipt_chain}.py` | partially operational and imported by Orchestrator |
| Reconciliation | `graph/{reconciler,reconcile_board}.py` | partially operational; boot/tick imported by SwarmManager |
| Telos bridge | `graph/telos_bridge.py` | unwired prototype |
| LangGraph parity | governance gauntlet plus `dharma_swarm/langgraph_parity` clone | useful differential/inventory tooling; not production integration |
| CLI/API/MCP for graph runs | none | absent |

`rg` found no non-test production importer of `GraphBuilder`, `CompiledGraph`, `GraphPersistenceKernel`, `GraphCheckpointStore`, or `GraphTelosBridge`. Production import of graph code is limited to the durability and reconciliation seams. That distinction is the central integration truth.

## 3. Subsystem maturity

| Subsystem | Classification | Evidence boundary |
|---|---|---|
| Repository admission/build | partial; broken on audited host | exact current `make onboard` cannot parse on stock macOS GNU Make 3.81; no repository minimum Make version was found |
| TaskBoard and task FSM | partial | SQLite/WAL and snapshot semantics; failed prerequisites can route before propagation |
| Orchestrator and dispatch | partial | real production seam and receipts; large ambient-effect surface and fail-open paths |
| Runtime truth spine | partial | identity, receipt, idempotency abstractions are real; not universally saturated |
| Model/provider routing | partial | centralized config and fallbacks; URL discard and backend-identity duplication reproduced |
| Swarm state/stigmergy/signal bus | prototype to partial | cross-instance lost write and mutable-event alias reproduced |
| Evolution/selection | prototype; terminology overstates learning | strong mutation gating; invalid shadow fitness contaminates selection inputs |
| DharmaGraph neutral core | prototype with a strong scoped kernel | 188 focused tests; deterministic BSP semantics; not hot path |
| Graph persistence | prototype | restart tests pass; concurrent lost update, aliasing, poison journal |
| DurableInvoker/reconciler | partial | production imports and meaningful CAS tests; authority and fail-open limitations |
| LangGraph parity gauntlet | operational inventory; weak readiness evaluator | reproducible 52/100; false-credit and judge-authority defects |
| API/dashboard security | partial; unsafe when exposed | bearer auth bypass for WebSockets reproduced |
| Organism composition | opt-in prototype | API launcher leaves `DHARMA_ORGANISM_ROOT` off by default |
| Cybernetic live closure | harness-proven; not production-closed | authoritative boundary: 11/13 harness, 0/13 live |
| Observability/operations | partial | health/receipts exist; observed daemon source drift and later HTTP instability |
| Test estate | extensive but uneven | hundreds of tests; strong local kernels, major false-green and cross-instance gaps |
| Memory/kernel/retrieval stack | prototype; assessment-limited | current-main implementation and governance gates exist across `memory.py`, `memory_kernel/`, `memory_retrieval.py`, and `knowledge_ops/`; no representative runtime, custody, or concurrency smoke in this audit |
| MCP surfaces | prototype | two library/factory surfaces exist; optional dependency factory constructed, but no launcher/transport/tool lifecycle was exercised |
| A2A HTTP/NATS | prototype | gateway/server/transport code exists and API construction succeeds; consequential roundtrip and failure semantics remain unverified here |
| Local service supervision | partial and duplicated | `run_operator.sh`, dashboard control, launchd, and tmux surfaces exist; the inspected live source was unattested and stale |
| Containers/deployment | unsupported in this audit | Dockerfiles and `docker-compose.yml` exist; no clean image build, deploy, rollback, or isolation smoke was executed |
| Whole-organism backup/restore | unsupported | Litestream configuration exists, but no canonical complete-state owner or demonstrated full restore/DR exercise was established |

The deep execution audit was intentionally concentrated on graph, dispatch, evidence, and promotion boundaries. The assessment does not promote memory, MCP, A2A, container, or backup surfaces from existence alone; their rows prevent the overall verdict from silently implying they were fully adjudicated.

## 4. Verified assets

### 4.1 Neutral scheduling semantics

The graph core uses deterministic bulk-synchronous steps, explicit routing, channel reducers, and validate-all-before-commit behavior. Tests cover conditional edges, fan-out, cycles, resume, persistence, crash receipts, telos bridge behavior, and differential-oracle cases. This is a credible foundation for a **bounded replay laboratory**, not evidence of whole-swarm determinism.

### 4.2 Production-wired durability seams

`Orchestrator` imports the durable invoker and receipt persistence; `SwarmManager` performs graph reconciliation on boot/tick. With a healthy SQLite owner and identity, CAS, memoization, and concurrent-claim tests are meaningful. This should be adapted rather than replaced.

### 4.3 Honest sub-100 boundary

The current parity artifact says `52.00/100`, `34 gaps`, and `NOT_FINISHED`. A fresh builder run on `c14b950…` produced the same score and source-tree digest `ffd0e30e…108cde`; the committed builder receipt's semantic replay check passed with the frozen seed. This is much more credible than the historical `FINAL_100_PARITY_REPORT.md`, which the current rubric correctly treats as void/self-graded.

### 4.4 Claim-language infrastructure

The governance stack distinguishes owners, projections, receipts, AMBER/RED, and `CLOSED_NOT_PROD`. This is valuable. Its weakness is enforcement: a forgeable string or status-only dictionary can still be promoted by evaluators that do not possess authenticated authority.

### 4.5 Strong caution around live mutation

Actual code mutation/application is gated more strongly than the rhetoric suggests. Shadow/archive states are recorded. The defect is that unchanged-baseline test results can be scored as proposal fitness and affect predictor/meta inputs—not that the repository blindly applies every proposal.

### 4.6 Existing one-way telemetry seam

The frozen baseline already states the correct doctrine in `dharma_swarm/spine/receipt.py`: `EvidenceReceipt` is canonical and OpenTelemetry is an export adapter, not the truth surface. That is the seam to extend, not replace. The inspected adapter emits `gen_ai.system`, while the current developmental OpenTelemetry GenAI conventions use `gen_ai.provider.name`; `tests/test_dispatch_dropoff_sources.py` pins the older field. This is bounded interoperability/schema drift, not evidence that receipt settlement is wrong. A versioned projection with golden fixtures should absorb convention churn without changing canonical receipt structures.

## 5. Reproduced and static failures

Each finding states modality, counterevidence, and a concrete falsifier. Full machine-readable forms are in `EVIDENCE_LEDGER.jsonl`.

### F-01 — Current onboarding door does not parse

- **Modality:** reproduced on exact `c14b950…`.
- **Evidence:** GNU Make 3.81 reports `Makefile:592: *** multiple target patterns. Stop.` on target-specific `override export` assignments.
- **Impact:** the mandatory first action cannot run on the local platform; all later readiness output is unreachable.
- **Counterevidence:** CI on newer GNU Make may accept the syntax; many other checks passed. The onboarding parity check was skipped on this merge commit, and the repository does not explicitly declare GNU Make 3.81 as supported or state another minimum.
- **Falsifier:** `make -n onboard` must parse on GNU Make 3.81 and current GNU Make, followed by one clean supported-Python `make onboard` run.

### F-02 — Graph JSON persistence loses concurrent writes

- **Modality:** deterministic reproduction against source introduced at `3d9bf6406` and unchanged on current main.
- **Evidence:** two synchronized writers both completed without error; only one task record remained: `attempted=2, persisted=1`.
- **Cause:** unlocked read-modify-tempfile-replace cycles in `graph/persistence.py`; atomic replacement prevents torn single writes but not lost updates. Parent-directory fsync is absent.
- **Falsifier:** repeated interprocess collision tests retain both writes using a transaction, CAS/generation, or interprocess lock.

### F-03 — Fork aliases parent checkpoint state

- **Modality:** reproduced.
- **Evidence:** child mutation changed parent channel/version; mapping identity was shared. A covering test contains a vacuous `or True` clause while the parity row earns full credit.
- **Falsifier:** child mutation leaves the serialized parent state and versions byte-identical.

### F-04 — Invalid pending write can poison every resume

- **Modality:** reproduced.
- **Evidence:** a conflicting write failed, remained in the journal, failed again on resume, and remained pending.
- **Counterevidence:** manually inserted valid writes replay successfully.
- **Falsifier:** invalid writes are rejected before journaling or quarantined in a terminal typed state so later resume makes progress.

### F-05 — “Exactly once” fails open

- **Modality:** static plus test-confirmed.
- **Evidence:** `durable_invoker.py` executes when state/identity is absent and also executes after idempotency-begin failure; tests explicitly cover fail-open behavior.
- **Correct claim:** conditional effectively-once under a healthy local owner and cooperative external side-effect semantics.
- **Falsifier:** strict mode must produce zero external calls when ownership cannot be established; non-idempotent post-dispatch ambiguity must quarantine rather than retry.

### F-06 — Receipt truth is derived from an unbound status dictionary

- **Modality:** static plus positive-test confirmation.
- **Evidence:** the reconciler accepts a dictionary such as `{"status":"ok","task_id":"task-1"}` and derives terminal truth without run/claim/side-effect binding or authenticated chain.
- **Counterevidence:** write access to the runtime DB is an implicit authority boundary.
- **Falsifier:** receipts lacking execution identity, task/claim bindings, effect key, and verified authority are rejected.

### F-07 — Parity judge authority is forgeable

- **Modality:** reproduced.
- **Evidence:** replacing judge ID, attestation, and “signature” with attacker-selected strings produced no findings after digest recomputation. The verifier checks public-field consistency, not a trusted key/OIDC identity.
- **Counterevidence:** the digest catches accidental corruption and tampering by an actor that cannot recompute it.
- **Falsifier:** `signature="not-a-signature"` and self-declared authority must fail against a configured trust root, with builder and verifier custody distinct.

### F-08 — Parity score grants false capability credit

- **Modality:** observed in gauntlet code; broken-control probes confirm behavior.
- **Evidence:** import/getattr-only facets can earn partial points; APP01-04 run the LangGraph-parity clone; async persistence checks can accept a synchronous file call wrapped in `async`; performance facets and a completeness observation include unconditional truth.
- **Counterevidence:** the report is explicitly NOT_FINISHED and governance already records some hardening cards.
- **Falsifier:** an importable engine whose methods always raise scores zero; application rows execute the neutral engine; all points derive from enumerated behavioral observations.

### F-09 — Stigmergy cross-instance decay loses an append

- **Modality:** deterministic reproduction.
- **Evidence:** instance A paused after reading; instance B appended; A atomically replaced the file; the fresh mark disappeared.
- **Cause:** locks are per object/process, while decay is read-rewrite.
- **Counterevidence:** module singleton use is safe within one process.
- **Falsifier:** a cross-instance/process regression preserves the concurrent mark through an OS lock, append log, transaction, or generation protocol.

### F-10 — Failed prerequisites can become ready

- **Modality:** behavior reproduced; semantic intent disputed.
- **Evidence:** the ready query treats failed/dead-letter/stale-running dependencies as satisfied although the API contract says all completed; a child became ready after prerequisite failure. Propagation is separate and cadence-gated.
- **Counterevidence:** an existing test documents terminal dependencies as satisfied, suggesting an intentional liveness policy.
- **Falsifier:** ratify an explicit dependency-failure semantic and prove routing cannot race propagation, or change the query so only the intended state admits dispatch.

### F-11 — Shadow fitness evaluates unchanged code

- **Modality:** control flow proven; downstream fitness consequence directly inferred from executed assignments.
- **Evidence:** shadow mode saves the diff then clears it; unchanged baseline tests can yield `pass_rate=1.0`; correctness/safety/efficiency feed fitness, archive/predictor, and free-grind best-result/meta inputs.
- **Counterevidence:** status remains `shadow`; live application is gated.
- **Falsifier:** execute the proposed diff in an isolated disposable tree, or prohibit shadow results from correctness, predictor training, best-fitness replacement, and meta-evolution.

### F-12 — Provider configuration does not reach clients reliably

- **Modality:** reproduced.
- **Evidence:** a resolved Groq proxy URL was `https://proxy.invalid/v1`; the instantiated client retained the hard-coded public endpoint. Similar omissions span several providers.
- **Falsifier:** factory-to-HTTP-client tests prove the resolved base URL and identity arrive at the actual client.

### F-13 — Logical provider diversity is not backend diversity

- **Modality:** reproduced.
- **Evidence:** `anthropic` and `claude_code` logical lanes both instantiated `ClaudeCodeProvider`; deduplication keys by enum label, not resolved backend identity.
- **Counterevidence:** this can be intentional cost routing.
- **Falsifier:** diversity calculations and council membership deduplicate by provider/backend/model/credential domain, or Anthropic remains a genuinely distinct API lane.

### F-14 — Bearer authentication does not protect WebSockets

- **Modality:** reproduced, high severity if the API is exposed beyond loopback.
- **Evidence:** HTTP middleware enforces the configured key; WebSocket code accepts unconditionally. With `DASHBOARD_API_KEY` set, an unauthenticated `/ws/chat/session/...` connection received a `chat_snapshot`.
- **Counterevidence:** launcher defaults to `127.0.0.1`; observed socket path is read-oriented.
- **Falsifier:** auth-enabled tests reject missing/invalid socket credentials before `accept()` on every WebSocket route.

### F-15 — Running daemon source is not attested current main

- **Modality:** source drift reproduced; later health failure cause unresolved.
- **Evidence:** listener cwd was `/Users/dhyana/dharma_swarm` at stale/dirty `5207a2f…`, not audited `c14b950…`. One early health probe succeeded; later TCP connected while HTTP did not return successfully.
- **Falsifier:** restart from a clean attested SHA and produce repeatable health plus owner-surface receipts carrying that SHA.

### F-16 — Full Organism is opt-in at the canonical API

- **Modality:** static and environment observed.
- **Evidence:** `api/main.py` gates composition behind `DHARMA_ORGANISM_ROOT=1`; `run_operator.sh` does not set it and the audit environment left it unset.
- **Falsifier:** canonical launcher enables the owner surface and live health proves Organism/StrangeLoop activity from the exact SHA.

### F-17 — Host process arguments exposed live credentials

- **Modality:** observed host operational security exposure.
- **Evidence handling:** values were neither repeated nor written into artifacts. Source tracing found no committed Dharma launcher responsible.
- **Implication:** process-list output must be treated as sensitive; rotate affected credentials and remove secrets from argv/environment-to-argv relays.
- **Boundary:** this is not attributed to Dharma source without evidence.

## 6. Determinism and distributed-systems semantics

### Current deterministic envelope

`SimulatedEffects` controls a seed-derived clock/RNG/dispatch order for the neutral graph. It does **not** control model/provider calls, tool execution, filesystem semantics, UUIDs, SQLite fault windows, NATS/network behavior, asyncio/process scheduling, or the broader Orchestrator. Inserting one additional PRNG-consuming effect can shift every later choice. Therefore:

```text
same seed != same semantic execution
```

unless code, configuration, fixture bundle, choice-site identities, domains, dependency versions, and all control-relevant effect boundaries are also pinned.

The neutral scheduler is sequential bulk-synchronous simulation. It can explore graph-order choices; it cannot claim coverage of asyncio races, multiprocess file contention, kernel scheduling, NATS delivery, real provider drift, or multicore memory ordering.

### Consistency and effect semantics

- TaskBoard uses SQLite/WAL and is stronger than JSONL/file-rewrite surfaces.
- Graph JSON persistence currently has atomic-single-write but not serializable-multiwriter semantics.
- DurableInvoker's local CAS cannot determine whether an uncooperative external effect occurred after a provider response and before local completion.
- Non-idempotent effects require an `ambiguous` terminal/quarantine state, not automatic retry.
- Receipt order should be causal, not inferred from wall-clock timestamps.

## 7. Agent and ML credibility

The system contains model selection, provider fallbacks, scoring, mutation proposals, archives, predictors, and meta-evolution. Those are legitimate orchestration and experimentation mechanisms. The audit did not find evidence justifying a claim of a scientifically validated self-improving learning system:

- no credible counterfactual shadow evaluation of the proposed code;
- no clean, externally grounded task-outcome dataset with stable lineage;
- no randomized or matched baseline establishing uplift from mutation/selection;
- no protection against provider/backend pseudodiversity in council evidence;
- zero production-live cybernetic loop closures;
- no evidence that multi-agent agreement is calibrated as truth.

The right current label is **heuristic, model-assisted orchestration with experimental evolutionary machinery**, not autonomous online learning. A useful future experiment must pre-register the dataset, baseline, metric, allowed mutations, external outcome, stopping rule, and regression guard; use a disposable clean worktree; and keep model consensus as a report modality, never proof authority.

## 8. Code quality, tests, and supply chain

- Exact current main tracks roughly 4,965 files, including more than 1,000 under `dharma_swarm` and roughly 900 test files. Breadth is not the problem; ownership and realism are.
- The focused graph suite passed `188` tests. Independent narrow Swarm unit tests passed `7`; separately, the exact-current report-local counterexample harness reproduced all `12/12` named probes, including graph and Swarm defects that those green suites missed.
- 207 Python modules exceed the repository's documented 500-line guidance. Largest audited examples include `thinkodynamic_director.py`, `telos_substrate.py`, `runtime_state.py`, `evolution.py`, and `providers.py` in the 3,400–5,200 line range.
- Historical parity reports remain discoverable beside current evidence, including an invalid 100/100 report. Current governance voids it, but navigation still permits accidental resurrection.
- Dependency locks and gitleaks/CodeQL/Semgrep checks are strengths. This assessment did not perform a full license/SBOM/CVE audit, dependency rebuild from zero, or all-platform CI replay.
- GitNexus indexes available locally were stale (`5207…` and another sibling, not `c14b950…`); direct source and `rg` were treated as authority.

## 9. Security, SRE, DevOps, and production maturity

### Positive

- SQLite runtime owners, health routes, structured receipts, idempotency records, launcher scripts, CI matrices, and governance checks exist.
- The runtime has explicit concepts for delivery versus semantic reply versus completion.
- Live mutation authority is bounded more strongly than many agent systems.

### Blocking gaps

- canonical local admission is broken;
- live daemon source is dirty/stale and not attested;
- full organism composition is not the default owner path;
- bearer auth does not cover WebSockets;
- ambient secrets can be process-table-visible on the host;
- JSON/file stores use process-local locks across shared paths;
- effect ownership fails open;
- no exact replay bundle spans a production dispatch;
- no demonstrated backup/restore/DR exercise for the complete organism state;
- no evidence that unattended operation avoids accumulating stale branches, receipts, poisoned journals, or external side effects.

## 10. Recommended disposition by subsystem

| Subsystem | Decision | Immediate obligation |
|---|---|---|
| Neutral graph scheduler/channels | preserve and adapt | freeze surface; add stable choice sites and replay bundle |
| Graph JSON persistence | harden or replace internally with SQLite owner | concurrency, crash-window, directory-fsync tests |
| DurableInvoker | preserve, add strict mode | typed effect class; fail closed in test/promotion paths |
| Reconciler | preserve, strengthen authority | require bound, authenticated receipt chain |
| `workflow.py` / topology executor | retain during migration, no new features | conformance corpus before cutover |
| LangGraph clone/parity score | retain as compatibility oracle; demote | behavioral facets only; authenticated verifier; no readiness claim |
| Shadow evolution fitness | quarantine from selection | isolated-diff execution or exclude correctness/meta inputs |
| Provider routing | consolidate by resolved backend identity | end-to-end factory/client contract tests |
| Stigmergy JSONL | redesign storage protocol | cross-process atomicity and recovery tests |
| SignalBus | copy/immutability boundary | mutation isolation test |
| API/WebSockets | fix before non-loopback exposure | auth parity tests across protocols |
| Organism root | do not claim default-live | one attested clean launcher and owner-surface health |

## 11. Commands and exact local evidence

| Proof | Command or durable locator | Result |
|---|---|---|
| authoritative freeze | `git rev-parse origin/main` and remote `HEAD`/ref inspection | `c14b950bc5009f2200d9425155010be508ead981` |
| local admission | `make --version`; `make onboard` | GNU Make 3.81; parse failure at `Makefile:592`, exit 2 |
| focused graph suite | `.venv/bin/python -m pytest -q -p no:cacheprovider` over the 13 enumerated graph/parity files | 188 passed in 10.76s initially and 4.58s on final exact-current rerun, exit 0 |
| fresh parity builder | `scripts/governance/dharmagraph_parity_gauntlet.py --emit --role builder --seed 20260713 --performance-iterations 5` | 52.00/100, 34 gaps, broken control failed, exit 0 |
| committed receipt replay | `scripts/governance/dharmagraph_parity_gauntlet.py --check --seed 20260711 --performance-iterations 5` | receipt check passed on the frozen source tree |

The full command lines, environments, outputs, test-file list, counterexample harness descriptions, and limitations are recorded in [VERIFICATION_LOG.md](VERIFICATION_LOG.md). The machine-readable propositions and falsifiers are in [EVIDENCE_LEDGER.jsonl](EVIDENCE_LEDGER.jsonl).

## 12. Proof boundary

The following claim is supportable:

> At `c14b950…`, a scoped DharmaGraph test corpus passes and the parity inventory reproducibly reports 52/100, while production imports use only its durability/reconciliation seams.

These claims are not supportable:

- Dharma Swarm is deterministically replayable.
- DharmaGraph is the production graph runtime.
- 52/100 measures production readiness or 52% semantic correctness.
- the system provides unconditional exactly-once effects.
- evolution has demonstrated real-world performance improvement.
- 11 harness-proven loops are live-closed.

The target architecture and executable promotion boundary are specified in `FIRST_PRINCIPLES_AND_TARGET_ARCHITECTURE.md`.
