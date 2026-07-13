# First Principles and Target Architecture

**Baseline:** Dharma `c14b950bc5009f2200d9425155010be508ead981`; original public research accessed 2026-07-13; MiroFish/telemetry extension accessed 2026-07-14.  
**Scope:** incremental architecture for trustworthy testing and promotion, not a wholesale runtime rewrite.  
**Document role:** dated proposal/report, subordinate to the active track and ratified architecture. No interface below is canonical until promoted through the repository's normal spec/ADR process.

## 1. Thesis: Dharma gaps and concrete failure modes

Dharma does not need a general deterministic hypervisor. It needs a **bounded replay laboratory** that closes two existing seams:

1. `CompiledGraph.invoke(...)` for graph state, order, checkpoint, and crash semantics.
2. The real production slice `TaskBoard -> Orchestrator -> spine -> DurableInvoker -> fixture AgentInvoker -> settlement`.

The laboratory must make every controlled choice and fault explicit, execute non-vacuous properties, emit a causal trace, minimize failures, and package a fresh-process replay bundle. Everything outside that boundary must remain labeled nondeterministic or observational.

```text
Scenario corpus / Hypothesis state machine
                    |
                    v
          bounded site-aware explorer
             choices + fault plan
                    |
                    v
    WorldV1 + fixture-only effect adapters
   time | choice | fs | model | tool | network deny
                    |
       +------------+------------+
       |                         |
       v                         v
CompiledGraphAdapter    ProductionDispatchAdapter
       |                         |
       +------------+------------+
                    v
             causal EventSink
                    |
             executable properties
                    |
       +------------+------------+
       |                         |
 counterexample              regression pass
       |
 shrink -> ReplayBundleV1 -> fresh-process verifier
```

Two orthogonal lanes feed or observe this laboratory without acquiring its authority:

```text
seed documents -> OASIS-style personas/world/interventions -> ScenarioCorpusV1
                                                        (simulated input only)

canonical receipts/events -> DharmaTelemetryProjectionV1 -> OTLP/Collector
                                                       -> one analytics backend
                                                       -> hypothesis/replay task
```

## 2. Derived invariants and revised first principles

The starting hypotheses were directionally sound but too universal. The revisions matter:

- **Identical world/seed/config/code/model fixtures should replay** becomes: identical **manifest plus site-addressed choice tape** must produce the same scoped semantic trace and property result, or fail closed. Seed alone is not enough.
- **Every nondeterminism must be controlled** becomes: every control-relevant nondeterminism inside the claimed boundary must be captured or prohibited. Outside sources must be explicitly out of scope; whole-world control is not required for a bounded claim.
- **Every failure should be minimized** becomes: minimize only while preserving property identity and causal phase. A smaller exception with a different cause is not the same counterexample.
- **Test worlds should be realistic and hermetic** is a tradeoff, not a simultaneously maximizable objective. Use fixture simulation for reproducibility and a separate live canary for representativeness; never coerce one evidence class into the other.
- **Exploration coverage should be measurable** means site/fault/property activation coverage and discovery curves, not raw seed counts or wall time.
- **Promotion requires proof obligations** remains, but the verifier's authority must be a runtime capability, not a self-declared string in a receipt.
- **Many simulated agents imply diversity** becomes: shared ontology/persona/config/action/report generators create correlated pseudodiversity. A simulated population is one scoped scenario instrument unless calibration demonstrates otherwise.
- **More telemetry means more truth** becomes: telemetry is a lossy, forgeable projection for correlation and diagnosis. Missing/sampled projection data can force an investigation inconclusive, but no telemetry field can mint promotion authority.

## 3. Principles, precedents, adaptations, and tests

| # | Source / precedent | Invariant | Dharma failure addressed | Adaptation and justification | Executable acceptance | Risk / counterargument | Decision |
|---:|---|---|---|---|---|---|---|
| 1 | FoundationDB simulator; TigerBeetle VOPR; Antithesis | A replay claim is closed over code, world, configuration, and choices | seeded effects shift after call-order changes; no production replay bundle | build `WorldManifestV1` and stable site-addressed `ChoiceRecordV1`; small Dharma-specific boundary | 100 fresh processes reproduce property ID and semantic trace; changed code/config/domain refuses before execution | canonicalization can hide semantic fields | **build** manifest/tape; **adapt** principles |
| 2 | Antithesis environment; Turmoil/MadSim | Controlled execution cannot silently escape to ambient effects | live provider/network/filesystem can contaminate tests | fixture-only invoker, temp-root filesystem, network tripwire, sanitized environment; unknown fixture is an error | unknown fixture produces zero outbound calls; host home/state remains unchanged | fixtures conceal live drift | **build/adapt** boundary; maintain separate live lane |
| 3 | Stateright/Loom/Shuttle; FoundationDB Buggify | Scheduling and faults are explicit search dimensions | ad hoc mocks and sequential tests miss crash windows/races | named fault sites at journal/apply/checkpoint and claim/provider/complete; bounded explorer | every declared fault site activated; broken CAS and corrupt checkpoint controls fail | state explosion; instrumentation drift | **borrow/adapt**, bounded only |
| 4 | QuickCheck/Hypothesis state machines and shrinking | Failure reduction preserves the violated property and phase | large traces are hard to debug; naive shrink can change cause | Hypothesis stateful scenario generation; shrink with property/phase guard | minimized bundle replays same property and failure phase in fresh process | shrinker version changes results | **borrow** Hypothesis, pin version and corpus |
| 5 | Antithesis properties; TigerBeetle assertions; model checking | A pass requires an activated, applicable oracle | parity points and tests pass on imports/literals or never-reached paths | `PropertyResultV1 = pass|fail|inconclusive|not_activated|invalid_test`; require activation count | deliberate broken controls fail; zero activation never passes | activation alone does not prove oracle quality | **build** result contract; **adapt** oracle discipline |
| 6 | event sourcing, vector/causal histories, Jepsen | Ordering claims derive from causal identity, not wall time | receipts/projections can conflate publish, delivery, completion | canonical trace events with causal parents, run/task/claim/effect keys, state digests | reconstruct joins without timestamp order; missing parent invalidates bundle | trace size and secret leakage | **build** narrow event schema; redact by construction |
| 7 | idempotency protocols and transaction recovery | External effect safety is typed by retry semantics | DurableInvoker fails open; post-provider crash is ambiguous | classify `pure`, `provider_idempotent`, `non_idempotent`; strict test mode; ambiguous quarantine | injected post-provider crash causes no duplicate non-idempotent call and yields `ambiguous` | some providers cannot supply status/idempotency | **adapt** DurableInvoker; do not claim universal exactly-once |
| 8 | formal refinement/differential testing | Compatibility and correctness are distinct evidence | LangGraph parity score is treated as readiness; app rows use clone | retain differential oracle as compatibility detector; property gauntlet owns safety claims | clone-only or import-only behavior yields zero production-readiness credit | two implementations may share a bug | **retain/demote**, do not delete |
| 9 | supply-chain/reproducible-build practice | The verifier must know the exact subject and toolchain | stale worktree daemon and forgeable judge identity | manifest binds clean SHA/tree digest, lock digest, interpreter, fixtures, graph/scenario | dirty tree or digest drift refuses promotion/replay | local uncommitted experiments need support | allow `experiment` modality, never auto-promote |
| 10 | Antithesis + real-cluster testing/Jepsen | Hermetic replay and production realism are complementary evidence | deterministic fixture success can be laundered into live behavior | two lanes: deterministic fixture exploration and non-deterministic live-provider canary | reports cannot merge modalities; live failures become sanitized local fixtures | duplicated test maintenance | **build local**, **partner/POC later** |
| 11 | MiroFish/OASIS | Generative populations expand scenario coverage but do not create independent evidence | model consensus and plausible reports can be laundered into prediction or truth | `ScenarioCorpusV1` binds seed, generator/model/prompt, persona/graph/recommender versions, intervention, and sample; its source-kind remains `simulated` rather than becoming an evidence modality | an uncalibrated scenario/report cannot typecheck at promotion; hindcast gate beats preregistered baselines before forecast use | persona realism and world calibration are difficult; AGPL code risk | **adapt** workbench/interface; **avoid** prediction authority |
| 12 | OpenTelemetry/OpenInference/ATIF | Interoperability is a one-way projection from canonical owners | traces, scores, and dashboards can become a shadow truth store | `DharmaTelemetryProjectionV1` carries canonical receipt digest, causal links, exact scope, five-state result, redaction and completeness; export through Collector | export loss cannot change settlement; tampered `authority` field cannot promote; golden adapter fixtures stay pinned | schema churn, cardinality, privacy, and exporter loss | **borrow** transport/schema; **build** thin pinned adapter |
| 13 | Temporal history; Honeycomb BubbleUp; Tempo TraceQL | History, visibility, anomaly hypothesis, and verifier result are distinct artifacts | mutable dashboards and status-shaped completion can masquerade as replay/proof | preserve append-only owner history; compare failed cohort to scope-matched baseline; emit replay tasks and `HypothesisCandidate` only | sampled/partial view never yields verified claim; one exemplar reaches its canonical receipt and replay command | full observability stacks can outgrow one-VPS operations | **adapt** distinctions and one query; **avoid** second authority store |

## 4. Target components

### 4.1 `WorldV1`

`WorldV1` is an injected control boundary, not a global service and not a new executor.

```python
class WorldV1(Protocol):
    def now(self, site_id: str) -> datetime: ...
    def choose(
        self,
        site_id: str,
        domain: Sequence[JSONValue],
    ) -> JSONValue: ...
    def fault(self, site_id: str, occurrence: int) -> FaultAction: ...
    def filesystem_root(self) -> Path: ...
    def emit(self, event: TraceEventV1) -> None: ...
```

Rules:

- `site_id` is stable across unrelated call insertion and names a semantic choice.
- Every choice records the domain digest and selection; replay refuses if the domain changed.
- The adapter may preserve today's `EffectsProvider` behind this protocol while call sites migrate.
- Host time, unseeded randomness, user home, environment lookup, and outbound network access are prohibited within the claimed boundary unless explicitly recorded in the manifest and adapter.
- No test-only scheduler replaces `CompiledGraph` or `Orchestrator`.

### 4.2 `SystemUnderTest`

```python
class SystemUnderTest(Protocol):
    async def execute(
        self,
        scenario: ScenarioV1,
        world: WorldV1,
        sink: EventSink,
    ) -> OutcomeV1: ...
```

Initial adapters:

- `CompiledGraphAdapter`: graph definition + input + checkpoint/fault plan.
- `ProductionDispatchAdapter`: real TaskBoard/Orchestrator/spine/DurableInvoker path with a fixture invoker and temporary SQLite owners.

Non-goals:

- whole-swarm determinism;
- real LLM determinism;
- NATS/kernel/multicore schedule control;
- performance/load testing;
- replacing existing runtime ownership.

### 4.3 Fixture agent/model/tool boundary

```python
class FixtureAgentInvoker(AgentInvoker):
    """Request digest -> declared success/failure/timeout/tool transcript.

    Unknown requests fail. There is no live-provider fallback.
    """
```

Fixture keys include normalized request, model/tool contract version, and relevant policy/config digest. Fixtures may be synthetic or sanitized captures with explicit authority; live credentials, raw unrelated prompts, and user home paths are forbidden.

### 4.4 Properties

```python
class Property(Protocol):
    property_id: str
    min_activations: int

    def observe(self, event: TraceEventV1) -> None: ...
    def finalize(self, outcome: OutcomeV1) -> PropertyResultV1: ...
```

`PropertyResultV1` has exactly five outcomes:

```text
pass | fail | inconclusive | not_activated | invalid_test
```

Bounded liveness can report bounded success or inconclusive, never unbounded liveness. A property with insufficient activations is `not_activated`, never pass. A broken-control corpus is mandatory for the harness itself.

### 4.5 Causal event sink

Events use explicit parent links and stable semantic identity. Sequence numbers order records within one trace; they do not establish cross-system causality by themselves.

```json
{
  "schema": "dharma.trace-event.v1",
  "seq": 31,
  "event_id": "run:7/graph:3/node:a/attempt:0/committed",
  "causal_parents": [
    "run:7/graph:3/node:a/attempt:0/provider-returned"
  ],
  "component": "graph.persistence",
  "event_type": "checkpoint_committed",
  "task_id": "task-7",
  "claim_id": "claim-2",
  "side_effect_key": null,
  "state_digest": "sha256:...",
  "redacted_attributes": {}
}
```

The sink validates parent existence, identity continuity, monotone local sequence, schema, and redaction. It writes append-only inside the bundle staging directory.

### 4.6 Replay bundle and regression corpus

```text
ReplayBundleV1/
  manifest.json
  scenario.json
  choices.jsonl
  faults.jsonl
  events.jsonl
  properties.json
  failure.json
  fixtures/
  checkpoints/
  SHA256SUMS
```

Bundle creation rejects:

- path traversal or absolute paths;
- escaping symlinks;
- secret-scanner findings;
- raw environment dumps;
- unapproved provider prompts or personal data;
- noncanonical JSON/unstable digests;
- missing causal parents or unchecked files.

The regression corpus stores minimized bundles keyed by property, component, and semantic digest. A schema migrator must preserve old bundle verification or explicitly mark it unsupported; silent reinterpretation is forbidden.

### 4.7 `DharmaTelemetryProjectionV1`

Dharma already has the right doctrine: `EvidenceReceipt` is canonical and OpenTelemetry is an export adapter. Preserve that dependency direction and make the adapter explicit:

```text
owner transaction / append-only receipt
  -> durable projection cursor or same-owner outbox
  -> DharmaTelemetryProjectionV1
  -> OTLP
  -> Collector: redact | normalize | budget | export
  -> exactly one chosen backend
```

Required projection fields:

- canonical receipt/event ID and payload digest;
- trace/span plus explicit links for prerequisite, fork/join, `replay_of`, and `verification_of`;
- code, world, manifest, config, fixture, choice-log, and effect digests when applicable;
- requested provider/model separately from resolved provider/model/endpoint and attempt;
- property ID/version, activation count/state, and the five-state result;
- proposition, modality, asserted principal, and scope as descriptive metadata only;
- retained-record completeness `complete | partial`; owner sequence/cursor; projection-run/trace/query completeness `complete | partial | sampled | lost`; redaction-policy digest; and exporter/schema version. Scope-level `sampled` comes from the pinned sampling policy/decision and covered owner-sequence range; `lost` comes from unexpected owner-sequence gaps, cursor lag, or terminal export failure—a missing record cannot label itself.

The adapter uses stable OTel primitives plus a pinned `dharma.*` namespace. It may map agent/model/tool fields into the current GenAI/OpenInference vocabulary, but that evolving vocabulary never leaks back into the canonical receipt schema. In particular, baseline `EvidenceReceipt.to_otel_span()` still emits the older `gen_ai.system`; the current GenAI repository uses `gen_ai.provider.name` and marks the convention Development. Migration therefore needs versioned golden fixtures, dual-read only if required by an existing backend, and no claim that the external schema is stable.

Operational queries worth shipping first:

1. accepted task with no canonical terminal settlement receipt;
2. duplicate effect commitment by idempotency key;
3. incomplete A2A causal chain or unpaired producer/consumer;
4. requested-versus-resolved provider/backend pseudodiversity;
5. property outcome and promotion rejection by authority, scope, modality, activation, or proposition mismatch;
6. later-cycle live-closure lag;
7. projection lag/loss, with exemplar links to the canonical receipt and replay command.

The first derived analysis is one BubbleUp-style cohort comparison: failed/rejected executions versus passing executions with the same manifest scope. Compare code/tree, world, provider/backend, model, agent, route, tool, queue age, retry, property, fault site, and causal predecessor. Its only output is a hypothesis/replay task. Sampling is forbidden for settlement, promotion, verification, replay, and non-pass property evidence.

Acceptance: disabling or corrupting the exporter changes no canonical settlement; every exported record resolves to a digest-matching canonical record; a tampered span claiming verifier authority cannot invoke promotion; scope-level sampling is surfaced from the declared sampler decision/coverage and loss from owner-sequence gaps, cursor lag, or terminal export failure; one outlier query leads through an exemplar to a reproducible bundle. Kill the adapter if it writes back, becomes a second owner, stores raw secrets/prompts by default, or requires a second execution path.

### 4.8 `ScenarioCorpusV1`

MiroFish contributes a workbench pattern, not a truth engine. A scenario generator may turn seed documents into ontology, personas, environment configuration, intervention branches, expected observations, and post-run interview questions. Its output enters `WorldV1` only as generated test input:

```json
{
  "schema": "dharma.scenario-corpus.v1",
  "seed_corpus_digest": "sha256:...",
  "generator_code_digest": "sha256:...",
  "generator_models": ["provider/model@revision"],
  "prompt_bundle_digest": "sha256:...",
  "graph_persona_recommender_digests": ["sha256:..."],
  "intervention_digest": "sha256:...",
  "sample_id": "...",
  "origin_kind": "simulated",
  "known_real_outcome_cutoff": null
}
```

Every persona, population result, report, and interview inherits that scope. `origin_kind="simulated"` is a scenario provenance tag, not a sixth evidence modality: the closed evidence ledger still uses `observed`, `reproduced`, `reported`, `inferred`, or `speculative`. “The generator emitted X” may be observed; X's synthetic claim about the target world is not thereby observed and remains speculative until independently evaluated. Multiple agents generated by a shared pipeline do not gain independent-witness authority. MiroFish AGPL code stays outside Dharma unless counsel approves; the Apache-2.0 OASIS environment interface is the preferred source of reusable abstractions.

For exploratory stakeholder rehearsal, acceptance is simpler: the corpus adds unique scenario/intervention/property activation at a bounded cost and preserves its simulated-origin tag. For forecasting, acceptance is deliberately hard: frozen historical cutoffs, preregistered proper scoring, simple and real-data baselines, repeated seeds, held-out events, model-family diversity, and sensitivity tests. Kill forecast claims if they fail the roadmap's preregistered lift, calibration, or numeric perturbation-sensitivity gates.

## 5. Schemas and lifecycle

### `WorldManifestV1`

```json
{
  "schema": "dharma.world.v1",
  "code_sha": "c14b950bc5009f2200d9425155010be508ead981",
  "dirty_tree_digest": null,
  "python_version": "3.13.12",
  "dependency_lock_digest": "sha256:...",
  "world_implementation_digest": "sha256:...",
  "graph_digest": "sha256:...",
  "scenario_digest": "sha256:...",
  "config_digest": "sha256:...",
  "fixture_bundle_digest": "sha256:...",
  "fault_plan_digest": "sha256:...",
  "seed": 20260713,
  "bounds": {
    "max_steps": 100,
    "max_choices": 500,
    "virtual_time_limit_ms": 60000
  }
}
```

### `ChoiceRecordV1`

```json
{
  "schema": "dharma.choice.v1",
  "seq": 17,
  "site_id": "graph.dispatch:g1:superstep:3",
  "occurrence": 1,
  "domain_digest": "sha256:...",
  "selected_index": 2,
  "selected_value_digest": "sha256:..."
}
```

### Run lifecycle

```text
declared
  -> admitted      (manifest complete, supported environment, no ambient escape)
  -> exploring     (bounded choices/faults)
  -> evaluating    (properties activated/finalized)
  -> passed
     or failed -> minimizing -> bundled -> replay_verified
     or inconclusive
     or invalid_test
```

No `failed` execution becomes a trusted regression until a fresh process verifies the bundle. No `passed` run can auto-promote if a required property is `not_activated` or `inconclusive`.

## 6. Effect safety and crash model

External effects are classified:

| Class | Re-execution rule | Crash after provider return / before local completion |
|---|---|---|
| `pure` | safe to recompute | retry allowed |
| `provider_idempotent` | retry only with identical provider-enforced key | query/retry with same key; verify result |
| `non_idempotent` | no automatic retry | mark `ambiguous`, quarantine for operator/reconciliation |

Mandatory crash sites:

1. after local ownership claim, before provider call;
2. after provider return, before local completion;
3. after graph journal, before state application;
4. after state application, before checkpoint;
5. after checkpoint, before receipt append.

Acceptance for strict deterministic runs: unavailable idempotency ownership yields zero provider calls. Acceptance for non-idempotent post-provider crash: no second call, durable `ambiguous` state, causal receipt showing why completion is unknown.

## 7. Exploration strategy

Start with three layers, in this order:

1. **Fixed regression replay:** every known minimized bundle on every relevant change.
2. **Property-based action generation:** Hypothesis state machines vary graph inputs, task states, recovery actions, and bounded faults; shrinking preserves property and phase.
3. **Bounded schedule/fault portfolios:** random, depth-first where small, and PCT-style priority perturbation for in-process choices.

Metrics:

- choice sites discovered/activated;
- domain alternatives exercised;
- fault sites activated;
- property activation counts and outcomes;
- unique semantic failures and time-to-first-discovery;
- replay success rate across fresh processes;
- shrink ratio and failure-phase preservation;
- production-seam conformance divergence.

Do not count raw seeds, tokens, agent votes, or wall-clock hours as coverage.

## 8. Exactly one typed epistemic-authority semantic contribution

typed-contribution-id: EPI-OPERATIONAL-INPUT-GATE-001

Introduce one construct:

```text
Claim<Satisfies<P>, M, Principal<K>, Q>

where P : Proposition, M : EvidenceModality, K : PrincipalId, Q : Scope
```

Add one evaluator/typechecking rule, the **OperationalInputGate**:

> For `S : ManifestDigest`, an automatic capability-promotion node `Promote<C>` may execute only when its input is `Claim<Satisfies<P>, Reproduced, Principal<K>, ManifestScope<S>>`, `S` exactly equals the target manifest digest, and the evaluator—not the payload—possesses `Authorize<K, P, Promote<C>, ManifestScope<S>>`.

This refinement closes a hole in the generic `T` form: reproducing an irrelevant result at the right scope is not evidence for the proposition the promotion actually needs. `P` names the discharged proposition, `K` names the verifier principal, and the evaluator-owned capability binds that principal to exactly one proposition, promotion action, and scope. There is no global `RuntimeVerifier` super-authority. The compiler checks the declared input port and proposition; the evaluator checks capability possession and exact scope. Deserializing `{"authority":"RuntimeVerifier"}`, an ATIF `extra` field, an OTel span attribute, an LLM score, or a MiroFish report cannot mint the capability.

There is no implicit coercion from `Reported`, `Observed`, builder-produced, vendor-produced, telemetry-produced, consensus-produced, differently scoped, differently propositioned, or simulated-origin world-content claims. A telemetry projection may describe the claim and rejection reason; it can never satisfy this input type.

### Counterexample fixture

```text
parity_builder.output = Claim(
  value = {score: 52},
  proposition = SurfaceParity,
  modality = Reported,
  principal = Builder,
  scope = SourceScope<current_source_digest>
)

telemetry_span.attributes["authority"] = "RuntimeVerifier"

auto_promote_production_dispatch.input requires
  Claim<
    Satisfies<ProductionDispatchConformance>,
    Reproduced,
    Principal<DispatchVerifierV1>,
    ManifestScope<current_manifest_digest>
  >
evaluator also requires
  Authorize<
    DispatchVerifierV1,
    ProductionDispatchConformance,
    Promote<ProductionDispatch>,
    ManifestScope<current_manifest_digest>
  >

expected:
  rejection EPI001
  reason includes proposition/modality/capability mismatch
  auto_promote_production_dispatch invocation_count == 0
```

The rule fails if any untyped edge, dynamic state update, deserialization path, telemetry write-back, or generic verifier capability reaches the promotion node. Do **not** add a confidence lattice, consensus-to-truth rule, generic proof calculus, or self-declared authority in this tranche. This is still one contribution: a proposition-specific non-coercion gate, tightened so evidence relevance and authority are evaluator semantics rather than receipt prose.

## 9. Build, borrow, adapt, partner, avoid

| Capability | Disposition | Reason | Estimated initial effort |
|---|---|---|---:|
| World manifest, choice tape, event schema, replay bundle | **build** | Dharma identity/receipt integration is specific and small | 5–8 engineer-days |
| Current `SimulatedEffects`, persistence kernel, DurableInvoker | **adapt** | existing seams are real; rewriting adds another substrate | 8–12 engineer-days |
| Hypothesis stateful generation/shrinking | **borrow** | Python-native, mature, already familiar in repo | 4–7 engineer-days |
| FoundationDB/TigerBeetle design principles | **adapt concepts** | strongest open precedents; product-specific implementations do not transplant | 2–3 design-days |
| LangGraph differential oracle | **retain and demote** | valuable compatibility detector, weak readiness proof | 1–2 engineer-days |
| Stateright | **borrow concepts / optional model spec** | strong explicit-state checker; Rust embedding cost is unnecessary initially | spike only |
| OTel API/OTLP/Collector + OpenInference fields | **borrow** | stable transport/core causality plus broad agent instrumentation; no need to invent a tracing protocol | 3–5 engineer-days for pinned adapter and fixtures |
| `DharmaTelemetryProjectionV1` + one cohort-delta query | **build thinly** | Dharma scope/property/authority/completeness semantics are specific; existing receipt adapter is the seam | 5–8 engineer-days |
| Tempo, ClickStack, or Honeycomb | **select at most one later** | query/visualization backend should follow existing operations and measured need | 3–10 operator-days depending on estate |
| Harbor ATIF | **export only** | useful portable trajectory/eval/training format; insufficient as canonical proof | 2–4 engineer-days after canonical history is closed |
| Temporal history principles | **adapt concepts** | history/visibility and deterministic-orchestration/activity separation are valuable | 2–3 design-days; do not replace Orchestrator |
| MiroFish workbench concepts / OASIS interface | **adapt / optional borrow** | strong scenario/intervention/persona UX; OASIS is permissive, MiroFish is AGPL | 5–10 engineer-day isolated spike |
| Hubble/Tetragon/Pyroscope | **borrow later** | ambient boundary witness and trace-linked performance diagnosis after Linux target exists | separate operational spike |
| Shuttle/Turmoil/MadSim | **avoid as dependencies** | Rust runtime/scheduler coupling does not match Python production path | none |
| Antithesis | **partner/POC later** | valuable whole-container exploration after target is hermetic | 3–6 weeks integration/POC |
| Custom hypervisor | **avoid** | multi-year moat project unrelated to current bottleneck | prohibited |
| New graph/orchestrator/checkpoint substrate | **avoid** | current failure is closure and proof, not missing surface | prohibited |

## 10. Migration and rollout

### Phase A — laboratory only

- no production code-path behavior change;
- adapter calls current graph core;
- temporary directories and fixture invoker only;
- fixed regression corpus in CI;
- replay bundle schema versioned and secret-scanned.
- pinned one-way telemetry projection golden fixtures; no backend required in CI;
- optional generated scenarios enter only as `ScenarioCorpusV1` fixtures with `origin_kind="simulated"`; claims about them still use the closed evidence-modality enum.

Rollback: remove CI job/adapter without touching the executor. Kill if a second scheduler becomes necessary.

### Phase B — one production-seam conformance slice

- exercise real TaskBoard/Orchestrator/spine/DurableInvoker with temporary owners;
- run success/failure/timeout/duplicate/restart/ambiguous scenarios;
- compare externally visible task/receipt state with and without trace/replay adapters;
- no real provider or tool call.

Rollback: feature flag and adapter removal. Kill if shadow execution can issue a duplicate effect or requires a parallel Orchestrator.

### Phase C — low-consequence feature-flagged integration

- choose one bounded task class;
- require exact conformance corpus and one-click fallback to existing executor;
- surface scope/nondeterministic boundaries to operator;
- live provider canary remains observational and separate.
- export canonical receipts asynchronously and expose projection loss/lag; no telemetry query writes back.

Rollback: disable flag, retain replay evidence, reconcile ambiguous effects before retry.

### Phase D — external POC

Package the same representative x86-64 multi-container fixture target for Antithesis. Compare local harness and vendor against predeclared seeded defects, novel actionable findings, replay quality, integration labor, data boundary, and cost. Do not use the vendor as the sole verifier of its own benefit.

## 11. Success and kill criteria

### Success

- 100/100 fresh-process replay for every committed counterexample;
- zero silent replay after code/config/fixture/domain drift;
- every safety property activated and every broken control detected;
- zero outbound calls in fixture lane;
- all modeled crash sites exercised;
- no duplicate non-idempotent effect; ambiguous outcomes quarantined;
- zero semantic divergence in the selected production conformance slice;
- every promotion input bound to exact manifest and verifier capability.
- every automatic promotion bound to the exact discharged proposition and evaluator-owned authorization tuple;
- export loss changes no settlement, and every retained projection resolves to a digest-matching canonical receipt;
- simulated-origin scenario reports remain non-promotable and forecasting claims remain disabled until the hindcast gate passes.

### Kill or redirect

- implementation requires a new executor or persistence substrate;
- a broken control passes;
- deterministic lane touches user `~/.dharma`, live network, or real credentials;
- shrink changes the violated property or phase;
- replay digest excludes a field later shown to affect control flow;
- conformance adapter changes task settlement semantics;
- exploration metrics collapse into seed counts/agent votes;
- a trace backend, ATIF file, dashboard score, anomaly result, or simulated population is accepted as canonical truth or promotion authority;
- telemetry requires a second receipt/owner store, writes back into runtime state, or exports raw secrets/prompts by default;
- the MiroFish/OASIS lane fails to add unique property/intervention coverage or is unstable under declared sensitivity tests;
- Antithesis POC cannot run the representative target or cannot export failures into durable local regressions.

## 12. Residual uncertainty

Fixture determinism can hide live-model drift; fault models can encode designer blind spots; graph-order exploration does not test asyncio/kernel/multicore races; semantic canonicalization can launder differences; replay bundles and telemetry can leak sensitive prompts; exporters and schemas can silently drop or reinterpret fields; simulated societies can amplify a generator's bias; and any adapter can drift from production. These are not reasons to avoid the laboratory. They are reasons to keep its claim boundary narrow, run live canaries separately, surface projection completeness, calibrate generated worlds, and require counterevidence in every promotion decision.
