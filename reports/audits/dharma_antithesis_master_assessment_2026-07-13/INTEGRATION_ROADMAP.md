# Integration Roadmap

**Baseline:** `c14b950bc5009f2200d9425155010be508ead981`  
**Strategy:** restore admission, harden proof, build one bounded replay laboratory, validate one real dispatch seam, and only then decide whether to buy whole-container exploration.  
**2026-07-14 iteration:** add a one-way telemetry membrane and a separately calibrated MiroFish/OASIS-style scenario lane without changing the frozen baseline or core sequencing.  
**Document role:** dated working plan; it does not alter `ACTIVE_TRACK.yaml` or authorize product changes.

## 1. Priority model

Scores are relative: impact/confidence/reversibility 1–5 high is good; effort/operational risk 1–5 high is costly.

| Priority | Work | Impact | Confidence | Effort | Operational risk | Reversibility | Evidence rationale | Decision |
|---:|---|---:|---:|---:|---:|---:|---|---|
| P0 | Restore `make onboard` on GNU Make 3.81/current and supported Python | 5 | 5 | 1 | 1 | 5 | exact-main parse failure is reproduced before any admission logic; fix is localized | do immediately |
| P0 | Rotate host-exposed credentials; stop secret-bearing argv | 5 | 5 | 1–2 | 2 | 4 | live values were directly visible; rotation is urgent but requires external credential owners | operator/security action immediately |
| P0 | Authenticate all WebSockets when API auth is configured | 5 | 5 | 2 | 2 | 5 | missing-token snapshot was reproduced with auth configured; middleware/router change is bounded | fix before non-loopback exposure |
| P0 | Reframe 52/100 as compatibility inventory, never readiness | 4 | 5 | 1 | 1 | 5 | scoring and authority counterexamples are reproduced; wording/gate changes are cheap | governance/test wording now |
| P1 | RFC-001 World/choice/replay bundle on graph core | 5 | 4 | 3 | 2 | 5 | directly attacks replay/provenance gaps using an existing kernel; implementation is not yet proven | build |
| P1 | RFC-002 crash/property gauntlet and broken controls | 5 | 5 | 3 | 2 | three persistence/crash defects and false-green scoring are reproduced | build/adapt |
| P1 | Fix graph concurrent persistence/fork/journal defects | 5 | 5 | 3 | 3 | 4 | lost update, alias, and poison journal are deterministic; storage migration raises moderate risk | prerequisite to cutover |
| P1 | Add strict effect mode and ambiguous effect state | 5 | 4 | 3 | 3 | 4 | fail-open code is inspected and effect ambiguity is real; production behavior was not fault-injected | adapt DurableInvoker |
| P1 | Bind parity/promotion verifier to real authority | 4 | 5 | 2 | 2 | 5 | forged identity/signature acceptance is reproduced; the proposed rule is deliberately narrow | implement one gate |
| P1 | Pin `DharmaTelemetryProjectionV1` and one end-to-end causal trace | 4 | 5 | 2 | 1 | 5 | canonical receipt and OTel adapter doctrine already exist; current adapter uses an older GenAI field and lacks proof-scope/completeness semantics | harden projection, no backend dependency |
| P2 | RFC-003 production dispatch conformance slice | 5 | 4 | 4 | 3 | 5 | the seam is production-wired but untested end-to-end under replay; adapter remains removable | build adapter, no new executor |
| P2 | Fix stigmergy multiwriter protocol and SignalBus aliasing | 4 | 5 | 3 | 3 | 4 | both data-loss/alias behaviors are reproduced; storage protocol work is broader than a copy fix | harden existing owners |
| P2 | Correct shadow evolution evaluation and provider identity | 4 | 5 | 3 | 3 | 4 | unchanged-code fitness, URL discard, and pseudodiversity are reproduced/inspected | quarantine until fixed |
| P2 | Attested clean daemon launcher and owner-surface health | 5 | 4 | 3 | 3 | 4 | live source drift is observed; a complete supervised restart/restore was not executed | required for live-closure claims |
| P2 | Scope-matched cohort delta and SLO canaries | 4 | 4 | 2–3 | 2 | 5 | BubbleUp/TraceQL/SRE patterns turn high-cardinality telemetry into testable hypotheses without changing truth ownership | build one query and canaries after projection |
| P3 | Low-consequence DharmaGraph production slice | 4 | 3 | 4 | 4 | 4 | benefit is plausible only after RFC-003; duplicate-effect risk keeps confidence lower | only after conformance |
| P3 | MiroFish/OASIS-style scenario-corpus and hindcast spike | 3 | 3 | 3 | 1 | 5 | workbench/intervention design is useful, but correlated generation and absent public calibration make prediction authority unsafe | isolated simulated-input lane only |
| P3 | Hermetic x86-64 multi-container target and Antithesis POC | 3 | 3 | 4 | 3 | 4 | external efficacy is credible, but packaging, pricing, security, and incremental yield are unknown | conditional partner test |
| Avoid | custom hypervisor/new scheduler/whole-swarm rewrite | negative | 5 | 5 | 5 | 1 | current failures are at adapters/oracles/owners; new core substrates add irreversible duplication | explicit non-goal |

## 2. Immediate: day 0–7

### 2.1 Restore the repository door

**Owner surfaces:** `Makefile`, onboarding contract tests, CI.  
**Effort:** 0.5–1 engineer-day.  
**Dependency:** none.

Work:

1. Replace or guard GNU-Make-version-sensitive target-specific `override export` syntax.
2. Add parse-only tests for GNU Make 3.81 and current GNU Make.
3. Run one clean actual `make onboard` using a supported Python.
4. Make unsupported Python fail early with a precise `>=3.11` admission message rather than a Pydantic traceback.
5. Ensure merge-commit onboarding parity is not silently skipped when Makefile/onboarding surfaces changed.

Acceptance:

```text
GNU Make 3.81: make -n onboard -> exit 0
current GNU Make: make -n onboard -> exit 0
clean supported environment: make onboard -> reaches readiness evaluator
unsupported Python: exits early with version requirement, no import traceback
```

Kill/rollback: if a compatibility abstraction makes the Makefile more complex, use a small portable wrapper/target rather than version-dependent syntax. Do not weaken report-root isolation to gain compatibility.

### 2.2 Contain urgent security exposure

**Effort:** 0.5–2 operator/security days.  
**Dependency:** credential owners and deployment authority.

- Rotate every credential observed in process arguments without recording old values.
- Restart/scrub the responsible Cursor extension-host launch path.
- prohibit secrets in command arguments; prefer scoped secret stores/file descriptors where supported;
- add auth-enabled WebSocket tests and enforce token/origin/session policy before `accept()`;
- retain loopback default, but do not treat loopback as the auth mechanism.

Acceptance:

- scrubbed process census contains no secret values in argv;
- old credentials are invalid;
- missing/invalid WebSocket token fails before session snapshot or subscription;
- HTTP and WebSocket auth policy are contract-tested together.

Kill: do not add secret values to fixtures, logs, process tests, or this report corpus while testing the fix.

### 2.3 Freeze claim boundaries

- Label parity 52/100 as a **compatibility inventory**.
- Block all “production ready,” “exactly once,” “deterministic swarm,” and “live-closed” coercions not backed by their explicit proof obligations.
- Archive or add an unmistakable supersession banner to the historical invalid 100/100 report.
- Record that `HARNESS_PROVEN 11/13` and `CLOSED_LIVE 0/13` are distinct types of claim.

Acceptance: repository search finds no live surface that presents the historical score as current; a broken import-only engine earns zero readiness credit.

Kill criterion: preserve historical artifacts with explicit supersession if removal would damage custody; do not rewrite history or make the new wording imply a stronger capability than the receipts prove.

### 2.4 Ratify the replay boundary

Approve the non-goals and interface sketch in RFC-001. Do not begin with whole-swarm simulation. Select one existing failure—checkpoint fork aliasing is ideal because it is deterministic, small, and currently false-green—as the first replay fixture.

Acceptance test: a ratified RFC names the exact graph boundary, manifest inputs, property, forbidden ambient effects, first failure fixture, owner, and rollback; no production executor imports the laboratory.

Kill criterion: stop or shrink the RFC if it requires a second scheduler, a new persistence owner, a live provider, user state, or a whole-swarm determinism claim.

**Week-one exit gate:** current main onboards locally; urgent credentials/auth are contained; one graph failure has a ratified manifest, property, and replay schema.

## 3. First 30 days

### 3.1 Complete RFC-001

- implement `WorldV1` adapter over current `EffectsProvider`;
- stable semantic choice sites with domain digests;
- fixture-only AgentInvoker and outbound-network tripwire;
- canonical `WorldManifestV1`, `TraceEventV1`, `ReplayBundleV1`;
- secret/path/symlink checks;
- fresh-process verifier;
- fixed counterexample corpus in a bounded CI lane.

Acceptance:

- 100/100 fresh-process replays of the selected failure match property ID and semantic trace;
- mutation of code/config/fixture/graph/domain refuses before execution;
- unknown fixture generates zero outbound calls;
- test leaves user home and real runtime DB untouched;
- insertion of an unrelated effect call does not shift a named choice.

### 3.2 Complete RFC-002

- add production-boundary fault hooks at journal/apply/checkpoint and claim/provider/complete;
- implement non-vacuous five-state property result;
- use Hypothesis state machines for bounded action generation and shrinking;
- add corrupt-checkpoint and disabled-CAS broken controls;
- run restart verification in new processes.

Initial required properties:

1. checkpoint state digest reconstructs identically;
2. pending writes recover once or quarantine terminally;
3. provider-idempotent duplicate attempts use one external effect key;
4. non-idempotent ambiguous outcome does not auto-retry;
5. no property passes without activation.

Acceptance: every fault site activates; both broken controls fail; minimized case preserves property and phase; no partial-credit aggregation.

### 3.3 Repair graph correctness blockers

- replace unlocked JSON read-modify-replace with an existing transactional owner, CAS/generation protocol, or interprocess lock;
- deep-copy/immutably snapshot forked checkpoint mappings;
- validate pending writes before journal persistence or quarantine invalid records;
- fsync parent directory where file-replace durability is claimed;
- add concurrent multiprocess and crash/restart tests.

Acceptance test: synchronized multiprocess writes preserve both updates; fork mutation cannot alter its parent; invalid journal data is rejected before persistence or quarantined terminally; crash/restart preserves the last committed generation.

Kill criterion: if fixing JSON persistence requires a new bespoke store, adapt the existing SQLite runtime owner instead. No fifth checkpoint substrate.

### 3.4 Implement the one authority gate

Implement only the proposition-specific `Claim<Satisfies<P>, M, Principal<K>, Q>` plus the `OperationalInputGate` described in the architecture report, where `M : EvidenceModality` and `Q : Scope`. Promotion requires `Q = ManifestScope<S>` and an evaluator-owned `Authorize<K, P, Promote<C>, ManifestScope<S>>` capability, not JSON text, OTel/ATIF metadata, or a generic global verifier. Require exact proposition and manifest scope for automatic capability promotion.

Acceptance: builder-reported 52, a reproduced but irrelevant proposition, and attacker-provided `authority="RuntimeVerifier"` all yield `EPI001`; promotion invocation count stays zero.

Kill criterion: disable automatic promotion and retain claims as data if any untyped edge, dynamic update, deserialization path, or self-declared authority bypasses the gate.

### 3.5 Pin the telemetry membrane

Build `DharmaTelemetryProjectionV1` over the existing canonical `ExecutionIdentity + EvidenceReceipt` seam. Use current OTel primitives and a pinned `dharma.*` schema; migrate `gen_ai.system` toward current `gen_ai.provider.name` behind versioned golden fixtures. Preserve requested and resolved provider/backend identity separately. Add span links for prerequisite, fork/join, `replay_of`, and `verification_of`; include exact manifest/world/property scope, five-state result, redaction policy, and projection completeness.

The first trace covers one fixture task from acceptance through route, provider attempt, effect settlement, property evaluation, and promotion rejection/acceptance. Export is asynchronous and one-way. A local in-memory/file collector is sufficient for the fixture; selecting or deploying a production backend is out of scope.

Acceptance:

- disabling, delaying, duplicating, or corrupting export changes no canonical state;
- every retained span resolves to a digest-matching canonical receipt/event;
- a tampered span or incoming baggage claiming authority cannot pass `OperationalInputGate`;
- no raw prompt, secret, or personal data appears in the golden export;
- retained-record completeness and projection-run/trace/query completeness are separate; sampling is visible from the pinned sampler decision/coverage and loss from unexpected owner-sequence gaps, cursor lag, or terminal export failure, not a field on the missing span;
- the complete trace answers one concrete causal question across the real identity spine.

Kill criterion: remove the adapter if it needs another receipt owner, writes back, changes settlement, treats span status as a five-state property result, or cannot pin schema behavior.

**30-day exit gate:** every modeled failure produces a secret-clean replay bundle; broken controls fail; graph persistence collision is closed; no deterministic run can reach a live provider; the one-way telemetry projection cannot mint authority or change settlement.

## 4. 90-day horizon

### 4.1 Complete RFC-003: one real production dispatch conformance slice

Target the actual path:

```text
TaskBoard
 -> Orchestrator.route_next / assignment
 -> _run_task_via_spine
 -> invoke_agent
 -> DurableInvoker
 -> FixtureAgentInvoker
 -> task and runtime settlement
```

Use temporary SQLite owners and a sanitized environment. Scenarios: success, provider failure, timeout, duplicate, restart, idempotent post-return crash, non-idempotent ambiguity, and state-store outage.

Acceptance:

- task/runtime/receipt states match declared scenario;
- provider call cardinality matches effect class;
- correlation joins without timestamp ordering;
- 50 fixture scenarios have identical externally visible settlement with and without trace/replay adapter;
- strict store outage results in zero provider calls;
- no code path touches real `~/.dharma`.

Kill/rollback:

- abort if shadow execution can issue a second real effect;
- abort if a parallel Orchestrator is required;
- roll back adapter on semantic task-state divergence;
- do not claim upstream routing or the whole system deterministic.

### 4.2 Close adjacent correctness debt

- Stigmergy: shared transactional/append protocol and cross-process decay tests.
- SignalBus: immutable/copy-on-enqueue payload; subscriber mutation isolation.
- Task dependency semantics: ratify failure propagation versus liveness and eliminate race.
- Shadow evolution: test proposed diff in isolated tree or exclude result from fitness/predictor/meta-evolution.
- Provider routing: propagate resolved base URLs to clients and deduplicate diversity by resolved backend identity.

Acceptance test: cross-process stigmergy decay retains a concurrent append; SignalBus drains an immutable/copy-isolated event; failed dependency semantics match the ratified FSM; shadow fitness executes the proposed diff; provider factories preserve endpoint and backend identity.

Kill criterion: quarantine the affected feature independently if its owner cannot meet the test without a new store, executor, or provider call; do not let one blocked repair delay the others.

### 4.3 Attest the live runtime

- launch only from a clean, recorded SHA/tree digest;
- expose runtime SHA/config/lock digest in health and receipts;
- supervise process with restart/backoff/resource limits;
- prove backup/restore for TaskBoard/runtime state and reconcile `ambiguous` effects;
- owner-surface live-closure proof requires a later cycle consuming the prior output.

Acceptance: repeated health checks cite exact clean SHA; restart restores state; one low-consequence end-to-end loop carries dispatch, owner receipt, subsequent consumption, and no ambiguous effect.

Kill criterion: on SHA/tree mismatch, missing restore proof, or ambiguous effect, stop/redeploy the service and refuse all live-closure promotion until a clean owner-surface receipt exists.

### 4.4 Low-consequence DharmaGraph integration

Only after RFC-003 passes, put one bounded task class behind a feature flag using the current graph adapter. Preserve one-click fallback and compare settlement against the conformance corpus.

Acceptance test: the flagged task class matches unflagged settlement across the full conformance corpus, issues no duplicate effect, emits a replay bundle for every fixture failure, and rolls back in one operator action.

Kill criterion: any semantic divergence, duplicate effect, unreplayable failure, or operator-invisible scope boundary disables the flag.

### 4.5 Run an isolated scenario-corpus and hindcast spike

Keep this lane outside production execution and promotion. Prefer the Apache-2.0 OASIS environment, manual-action, recommender, and interview interfaces as mechanics for Dharma-designed interventions; treat MiroFish as product and workflow prior art unless an AGPL review explicitly authorizes code reuse. Persist each generated society as `ScenarioCorpusV1` with seed-document digests, graph/persona/config/model/prompt versions, randomness controls, intervention log, action timeline, and `origin_kind="simulated"`. That is a scenario-source tag, not a sixth evidence-ledger modality.

Run two distinct experiments:

1. **Stakeholder rehearsal:** generate counterpositions, interventions, interview questions, and failure stories for replay-lab properties. Score only unique property/fault activation and operator usefulness; never score agreement as truth.
2. **Forecast hindcast:** freeze at least 30 development cases and a separate 30-case holdout spanning at least three domains before revealing outcomes. Run at least 30 stochastic replications per held-out case, then commit exactly one preregistered aggregate probability forecast per case before scoring; replications estimate Monte Carlo variability and never count as independent events. Preregister Brier/log-loss, calibration, ranking, abstention, and cost analysis; compare against base-rate, persistence/simple statistical, and single-agent baselines; repeat across at least two genuinely distinct resolved model families; and report sensitivity to persona, graph, prompt, and recommender changes.

Acceptance:

- every artifact is traceable to its frozen inputs and carries `origin_kind="simulated"`; an `observed` claim may say the generator emitted an artifact, but not that its synthetic world-content occurred;
- an automated temporal-leakage scan finds zero post-cutoff material, and every event carries run, scenario, monotonic sequence, causal parent, actor, input/output digest, and settlement identity;
- fixed-fixture non-LLM corpus plumbing replays byte-identically in a fresh process;
- the rehearsal track activates at least three previously unactivated properties or fault sites that survive independent fixture reproduction;
- any forecasting claim reports at least 10% relative Brier-score improvement over the strongest preregistered simple baseline with a paired-bootstrap 95% confidence interval excluding zero and expected calibration error at most 0.10; the bootstrap resamples held-out cases stratified by domain, never seed-level runs;
- a preregistered outcome-permutation broken control has absolute Brier score at least 0.05 worse than the candidate, with the case-stratified paired-bootstrap 95% interval for that gap excluding zero;
- under each preregistered persona/graph/prompt/recommender perturbation, worst-case absolute Brier degradation is at most 0.05 and expected calibration error remains at most 0.10; otherwise the claim is demoted;
- no generated persona, interview, vote, consensus, or forecast reaches `OperationalInputGate` without independent evaluator-owned evidence for the exact proposition.

Kill criterion: stop forecasting claims if outcome leakage is found, any numeric lift/calibration/sensitivity gate above fails, narrative confidence rises while calibration worsens, model-family diversity collapses to one resolved backend, or an input/version change was not recorded. Stop the whole spike if AGPL code enters a distributable component without counsel, synthetic world-content is presented as observed target-world evidence, cost per incremental reproduced failure exceeds the simpler hand-authored/generative baseline, or the lane starts creating a second executor or authority store.

**90-day exit gate:** zero conformance divergence, zero unmodeled duplicate effects inside the selected boundary, exact replay for every fixture failure, attested launcher, and one-click rollback. The scenario lane is optional and cannot weaken or substitute for this gate; if run, its simulated-origin tags and independent-reproduction boundary must remain intact.

## 5. Longer horizon: 3–12 months

### 5.1 Continuous exploration service

- bounded nightly portfolios over committed scenarios;
- discovery curves and site/fault/property coverage;
- minimized corpus lifecycle and schema migrations;
- budget/capacity controls;
- operator UI for property outcome, causal path, replay command, and scope;
- never execute a discovered bundle against live providers automatically.

Scale only when unique actionable failure yield justifies compute and triage cost. Kill a strategy whose discovery curve remains flat across a predeclared budget and whose corpus adds no new property/fault coverage.

### 5.2 Formal specification where state is small

Use Stateright/TLA+/Apalache/P-style models selectively for small protocols: effect ownership, checkpoint lifecycle, task dependency propagation, and promotion authority. Do not formalize the entire swarm. Connect model counterexamples to executable fixture scenarios.

Acceptance: each model has a refinement mapping to a tested runtime seam and at least one mutant it rejects. Kill models that cannot be related to production events/state.

### 5.3 Antithesis POC

Prerequisites:

- representative hermetic x86-64 multi-container target;
- sanitized data and no live production secrets;
- local seeded-defect corpus and property contracts;
- export path from vendor counterexample to local regression;
- agreed test-hour/cost, security, data-deletion, and success envelope.

POC acceptance:

- reproduces every predeclared seeded crash/idempotency defect;
- finds at least one novel actionable defect not found by the local harness;
- provides a stable rerun/debug artifact;
- exercises the real topology, not a toy rewrite;
- results become durable local tests;
- total integration/compute/triage cost fits the agreed envelope.

POC kill:

- representative topology cannot run;
- sensitive credentials or unrestricted internet are required;
- failures cannot be exported to local regressions;
- findings are exclusively packaging/mock artifacts;
- no incremental defect yield at the predeclared budget.

### 5.4 Escalate observability only when a query earns it

Choose exactly one operational backend based on the existing estate and the causal question proven by `DharmaTelemetryProjectionV1`: Tempo/TraceQL for an established Grafana estate, ClickHouse/ClickStack for high-cardinality wide-event analysis, or Honeycomb for managed cohort exploration. Implement BubbleUp/Event-Deltas-style foreground-versus-baseline comparison, multi-window SLO burn alerts, and trace exemplars back to canonical receipts. The output type is `HypothesisCandidate`, never a verified claim.

Add Hubble only when Linux/Kubernetes A2A traffic needs an independent network witness; surface its lost-event counter as evidence incompleteness. Add Tetragon only for privileged replay-lab boundary observation/enforcement. Add span-correlated Pyroscope profiles only after causal correctness exists and there is a measured performance question.

Acceptance: one retained query isolates a pre-seeded causal discriminator that a flat dashboard misses; every result links to canonical receipts and states projection completeness; disabling the backend changes no execution, settlement, evaluation, or promotion outcome.

Kill criterion: remove or defer any component that creates a second truth store, requires canonical evidence sampling, places high-cardinality IDs in metric labels, cannot redact sensitive content, or causes an alert/anomaly/profile to trigger automatic promotion or remediation.

## 6. First three implementation-ready RFC/spike specifications

### Module ownership and migration touchpoints

| RFC | Existing production owners touched | Initial laboratory/module home | Dependency direction and migration rule |
|---|---|---|---|
| RFC-001 | `graph/effects.py`, `scheduler.py`, `compiler.py`, `checkpoint.py` | `tests/oracle_support/dharma_replay_lab.py`, `tests/fixtures/dharma_replay/`, then a ratified `graph/replay.py` schema module only if needed | laboratory imports the graph kernel; production imports nothing from the laboratory; adapter removal is rollback |
| RFC-002 | `graph/persistence.py`, `persistence_runtime.py`, `durable_invoker.py`, `receipt_chain.py` | extend `test_graph_persistence_kernel.py`, `test_graph_durable_invoker.py`, and `test_graph_chaos_receipt.py`; keep faults/properties in replay-lab support | tests/fault adapters call existing owners; no new checkpoint/effect store; strict mode reaches production only behind an explicit flag |
| RFC-003 | `task_board.py:get_ready_tasks`, `orchestrator.py:route_next/_run_task_via_spine`, `spine/invoke.py:invoke_agent`, `graph/durable_invoker.py`, `runtime_lifecycle.py`, `runtime_state.py` | `tests/oracle_support/dispatch_conformance.py` plus temporary SQLite fixtures; extend `test_orchestrator_spine_dispatch.py` and task-board/runtime tests | conformance adapter wraps the real seam and fixture invoker; temporary owners first; a production feature flag is allowed only after zero-divergence acceptance |

### RFC-001 — `WorldV1` and `ReplayBundleV1`

**Question:** can one existing graph failure replay semantically across fresh processes without a new executor?

**Inputs:** graph definition, scenario, fixture bundle, fault plan, bounds, exact code/config/lock/toolchain digests.  
**Outputs:** manifest, site-addressed choices, causal events, property results, checksums.  
**Initial fixture:** fork-alias property; corrected control and deliberately broken control.  
**Effort:** 10–15 engineer-days including CI, security, and docs.  
**Dependencies:** admission fix; current graph core.  
Acceptance test: Every condition in §3.1 passes in fresh processes with an identical semantic trace and property identity.

Kill criterion: Stop if the design introduces a new executor or any ambient fallback.

### RFC-002 — Crash consistency and non-vacuous property gauntlet

**Question:** do graph/durable-effect semantics survive each named crash window, and can the harness detect its own mutants?

**Inputs:** fault-site registry, property registry, Hypothesis action machine, strict persistence/effect mode.  
**Outputs:** property activation/results, minimized replay bundle, coverage by site/fault.  
**Mutants:** disable CAS; accept mismatched reconstructed checkpoint; optionally replay invalid journal forever.  
**Effort:** 15–25 engineer-days.  
**Dependencies:** RFC-001, persistence protocol decision.  
Acceptance test: Every condition in §3.2 passes and each deliberately broken control fails.

Kill criterion: Any broken-control pass invalidates the gauntlet.

### RFC-003 — Production dispatch conformance slice

**Question:** can replay/tracing adapters observe one real orchestration seam without changing settlement or duplicating effects?

**Inputs:** temporary TaskBoard/runtime DB, fixture invoker, scenario corpus, effect safety class, fault plan.  
**Outputs:** joined task/runtime/receipt trace, outcome, conformance diff, replay bundle.  
**Effort:** 20–30 engineer-days.  
**Dependencies:** RFC-001/002, strict DurableInvoker mode, security fixtures.  
Acceptance test: Every condition in §4.1 passes with the fixture invoker, temporary owners, and zero settlement divergence.

Kill criterion: Stop on any live-provider call, second Orchestrator, user-state touch, duplicate effect, or semantic divergence.

## 7. Acceptance tests, kill criterion controls, operating model, and ownership

- One active track should own all replay-lab surfaces; no parallel “simulation,” “world,” or “determinism” substrates.
- Every new fault site has a production-boundary owner and at least one activation test.
- Every property has an owner, applicability predicate, activation minimum, broken control, and falsifier.
- Every committed bundle is secret-scanned and reviewed as potentially sensitive.
- CI separates fixed regression, bounded exploration, and live canary lanes.
- Live canary findings are observational until converted into a fixture and reproduced by an independent runtime verifier.
- Canonical receipts, replay bundles, verifier results, promotion decisions, and settlement evidence are never sampled; operational projections may be sampled only when projection-run/trace/query completeness records the pinned sampler decision/coverage and derives loss from unexpected owner-sequence gaps, cursor lag, or terminal export failure.
- Telemetry, SLOs, anomaly cohorts, network witnesses, profiles, and simulated societies can create replay tasks or `HypothesisCandidate`s, never authority.
- Capacity budget is explicit: max steps, choices, virtual time, process count, disk, and retained bundle size.

## 8. Final sequencing rule

No new LangGraph parity feature, production graph migration, autonomous evolution promotion, or Antithesis purchase should outrank:

```text
admission works
  -> one failure replays exactly
  -> broken controls fail
  -> crash semantics are honest
  -> one production seam conforms
  -> only then broaden or partner
```
