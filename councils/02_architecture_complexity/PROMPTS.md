# Council 02: Architecture and Complexity Prompts

Council ID: `architecture_complexity`

Use these prompts to find module depth failures, fan-in pressure, dependency
cycles, fragile boot order, fake seams, source-of-truth duplication, and unsafe
refactor plans.

## Shared Prompt Contract

```text
You are applying one architecture and complexity lens. Audit only. Do not edit
files.

Every finding must include command evidence or file:line evidence. Mark each
claim OBSERVED, INFERRED, or NOT_PROVEN. Rank risks by blast radius and by
future change amplification. End with one executable test, gate, or measurement
that would catch the failure again.
```

## Prompt AC-01: Module Depth and Responsibility Density Audit

Expert lens: senior refactoring architect.

Mandatory commands:

```bash
python3 scripts/repo_xray.py --repo-root .
rg --files dharma_swarm api dashboard/src scripts tests | xargs wc -l | sort -nr | head -60
rg -n "^(class|def|async def) |FastAPI\\(|APIRouter\\(|Typer\\(" dharma_swarm api scripts dashboard/src
```

Force inspection:

- largest files by lines and definitions;
- classes/functions per file;
- files mixing CLI, runtime, persistence, and UI concerns;
- public entrypoint count vs implementation depth.

Failure classes:

- `MEGA_MODULE`
- `GOD_OBJECT`
- `SHALLOW_WIDE_INTERFACE`
- `MIXED_RESPONSIBILITY_SURFACE`

Required output: top 10 module-depth risks and the first extraction seam for
each high-risk file.

## Prompt AC-02: Fan-In/Fan-Out Hub Pressure Audit

Expert lens: dependency economist.

Mandatory commands:

```bash
rg -n "^(from|import) (dharma_swarm|api)" dharma_swarm api scripts tests
rg -n "runtime_state|swarm|agent_runner|operator_bridge|orchestrator|models|providers" dharma_swarm api scripts tests
```

Force inspection:

- modules imported everywhere;
- modules that import too many neighbors;
- high fan-in files with high churn;
- shared models that become architecture gravity.

Failure classes:

- `UNSTABLE_HUB`
- `IMPORT_GRAVITY`
- `CHANGE_AMPLIFICATION`
- `LEAKY_SHARED_MODEL`

Required output: hub table with fan-in evidence, fan-out evidence, tests touching
the hub, and a contract or facade proposal.

## Prompt AC-03: Dependency Cycle and Layer Violation Audit

Expert lens: import-graph pathologist.

Mandatory commands:

```bash
python3 scripts/repo_xray.py --repo-root .
rg -n "from api|import api|from dharma_swarm|import dharma_swarm" api dharma_swarm scripts tests
rg -n "from .* import .*main|get_swarm|get_trace_store|get_monitor" api dharma_swarm
```

Force inspection:

- API-to-core and core-to-API backedges;
- lazy imports hiding cycles;
- test-only imports that mask runtime cycles;
- service locator patterns.

Failure classes:

- `IMPORT_CYCLE`
- `LAYER_INVERSION`
- `SERVICE_LOCATOR_COUPLING`
- `BOOTSTRAP_FRAGILITY`

Required output: cycle or layer-risk graph and the narrowest dependency inversion
that would break the risk.

## Prompt AC-04: Temporal Coupling and Boot-Order Audit

Expert lens: distributed runtime reviewer.

Mandatory commands:

```bash
rg -n "init|startup|lifespan|on_event|__aenter__|start_|stop_|daemon|heartbeat|tick\\(" api dharma_swarm scripts tests
rg -n "RuntimeStateStore\\(|OperatorBridge\\(|SwarmManager\\(|TraceStore\\(|SystemMonitor\\(" api dharma_swarm scripts tests
```

Force inspection:

- hidden initialization order;
- singletons and global stores;
- teardown gaps;
- tests depending on time, daemon order, or live processes.

Failure classes:

- `BOOT_ORDER_DEPENDENCY`
- `STALE_SINGLETON`
- `RACE_PRONE_DAEMON_STATE`
- `TIME_DEPENDENT_TEST_PASS`

Required output: boot-order dependency map and one deterministic fixture or
lifecycle test.

## Prompt AC-05: Boundary Seams and Adapter Integrity Audit

Expert lens: hexagonal architecture reviewer.

Mandatory commands:

```bash
rg -n "adapter|bridge|gateway|router|client|provider|store|repository|projection" dharma_swarm api dashboard/src tests
rg -n "os\\.environ|Path\\(|open\\(|sqlite|requests|httpx|subprocess|tmux|launchd" dharma_swarm api scripts tests
```

Force inspection:

- where IO enters core logic;
- adapter thinness and contract tests;
- direct filesystem/environment/process coupling;
- provider and runtime boundaries.

Failure classes:

- `SIDE_EFFECTFUL_CORE`
- `FAKE_ADAPTER`
- `DIRECT_FILESYSTEM_COUPLING`
- `UNMOCKABLE_SEAM`

Required output: seam map with concrete files and the smallest protocol or
adapter contract to add.

## Prompt AC-06: Source-of-Truth Duplication Audit

Expert lens: data contract and governance auditor.

Mandatory commands:

```bash
rg -n "canonical|source of truth|single source|manifest|registry|RuntimeStateStore|ACTIVE_SURFACE_MANIFEST" dharma_swarm api dashboard docs tests
rg -n "Agent|Task|Session|Runtime|Receipt|Event|Surface" dharma_swarm/models.py dharma_swarm/runtime_state.py api/models.py dashboard/src/lib/types.ts
```

Force inspection:

- duplicated schemas;
- docs-vs-code authority conflicts;
- backend/frontend type drift;
- readiness, receipt, track, or runtime numbers computed in multiple places.

Failure classes:

- `PARALLEL_TRUTH_STORE`
- `SCHEMA_FORK`
- `FRONTEND_INVENTED_STATE`
- `DOC_AUTHORITY_CONFLICT`

Required output: source-of-truth conflict table and one conformance test that
forces all surfaces through one owner.

## Prompt AC-07: Refactor Blast Radius Audit

Expert lens: change-safety lead.

Mandatory commands:

```bash
rg -n "SwarmManager|AgentRunner|RuntimeStateStore|OperatorBridge|DarwinEngine|OntologyRegistry|ModelRouter" dharma_swarm api scripts tests dashboard/src
rg --files tests dashboard/src/lib | sort
```

Force inspection:

- direct consumers of hotspot symbols;
- characterization coverage;
- script and dashboard consumers;
- hidden public APIs.

Failure classes:

- `HIGH_RADIUS_EDIT`
- `NO_CHARACTERIZATION_TEST`
- `IMPLICIT_PUBLIC_API`
- `HIDDEN_SCRIPT_CONSUMER`

Required output: blast-radius matrix and the safest characterization test before
any refactor.

## Prompt AC-08: Entrypoint-to-Surface Wiring Audit

Expert lens: API and product surface integrator.

Mandatory commands:

```bash
rg -n "include_router|APIRouter\\(|FastAPI\\(|websocket|fetch\\(|api/" api dashboard/src tests
rg -n "use[A-Z].*\\(|build.*Surface|controlPlane|runtimeControl|operatorCoherence" dashboard/src
```

Force inspection:

- route registration;
- dashboard consumers;
- generated API drift;
- dead endpoints and untested route contracts.

Failure classes:

- `ORPHAN_ROUTE`
- `UNTESTED_ROUTE`
- `FRONTEND_BACKEND_CONTRACT_MISMATCH`
- `PROJECTION_PRETENDING_RUNTIME`

Required output: route-to-consumer table and one contract test.

## Prompt AC-09: State, Persistence, and Event Coupling Audit

Expert lens: state-machine reviewer.

Mandatory commands:

```bash
rg -n "RuntimeStateStore|session_events|task_claim|delegation_run|receipt|artifact|sqlite|db_path|idempot" dharma_swarm api scripts tests
rg -n "legacy_no_identity_allowed|include_memory_plane|require_identity|idempotency" dharma_swarm tests scripts
```

Force inspection:

- state ownership;
- idempotency and event identity;
- legacy identity bypasses;
- event/receipt consistency.

Failure classes:

- `WRITE_PATH_FORK`
- `NON_IDEMPOTENT_EVENT`
- `IDENTITY_BYPASS`
- `STATE_REPLAY_GAP`

Required output: state transition risks and one invariant test.

## Prompt AC-10: Evidence-Based Complexity Reduction Plan

Expert lens: principal engineer preparing a safe extraction sequence.

Mandatory commands:

```bash
rg -n "TODO|FIXME|HACK|legacy|deprecated|quarantine|shadow|bypass" dharma_swarm api scripts tests dashboard/src
```

Also use outputs from AC-01 through AC-09.

Force inspection:

- rank refactors by risk removed per line changed;
- define seam, tests, rollback, and no-change criteria;
- reject cosmetic file splitting.

Failure classes:

- `COSMETIC_SPLIT`
- `ABSTRACTION_WITHOUT_PRESSURE`
- `BEHAVIOR_CHANGING_CLEANUP`
- `UNBOUNDED_REFACTOR`

Required output: top 5 complexity-reduction PRs, each with scope, verifier,
risk removed, and rollback path.
