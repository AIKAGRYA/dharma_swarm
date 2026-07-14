# Dharma Scenario–Telemetry Epistemic Membrane V1

**Document role:** Reference dossier with proposed, testable contracts
**Status:** PROPOSED / NON-NORMATIVE — no runtime, deployment,
evidence-settlement, or promotion authority
**Version:** 0.1.0
**Date:** 2026-07-14
**Owner:** Unassigned; an operator-opened track is required before implementation
**Replaces:** Nothing
**Subordinate to:** `CLAUDE.md`, the canonical governance stack, the active-track
register, existing runtime and receipt owners, the NATS substrate contract, and
the Verified Experiment Loop
**Evidence basis:** the July 2026
[master assessment](../../reports/audits/dharma_antithesis_master_assessment_2026-07-13/EXECUTIVE_VERDICT.md),
its [source manifest](../../reports/audits/dharma_antithesis_master_assessment_2026-07-13/SOURCE_MANIFEST.csv),
the frozen Dharma audit baseline `c14b950bc5009f2200d9425155010be508ead981`,
and the pinned upstream sources in §13

> This dossier preserves a candidate design. It is not repo-level canon,
> runtime truth, an active build spec, or a new workstream. If it conflicts with
> a canonical owner or a current implementation, that owner wins. Before code
> work begins, rerun `make onboard`, admit or assign a track, and revalidate every
> named seam against the then-current `HEAD`.

## 1. Decision capsule

The proposal connects two complementary membranes to Dharma's existing proof
and execution surfaces:

1. `ScenarioCorpusV1` is a portable **simulated-input envelope** for
   MiroFish/OASIS-style generated worlds, personas, interventions, action
   streams, reports, and interviews.
2. `DharmaTelemetryProjectionV1` is a versioned **external export profile** that
   projects existing canonical records one way into OpenTelemetry-compatible
   observability systems for correlation and diagnosis.
3. Neither a generated society nor telemetry can create evidence authority.
   Automatic promotion remains proposition-, principal-, action-, and
   manifest-specific, and evaluator-owned.

The memorable invariant is:

> Scenario generation proposes worlds. Canonical execution creates records.
> Telemetry makes those records inspectable. Only an evaluator-owned,
> exact-scope capability may authorize promotion.

The immediate recommendation is deliberately small: freeze the schemas and a
golden projection fixture before selecting or deploying any backend. A scenario
spike remains separate and optional. The replay/conformance work identified by
the master assessment still outranks both.

## 2. Why these ideas belong together

MiroFish-like systems and observability systems sit on opposite sides of an
execution boundary:

```text
seed documents
  -> OASIS-style world, personas, recommendations, interventions
  -> ScenarioCorpusV1                                  [simulated input]
  -> ordinary admission and bounded fixture execution
  -> existing canonical owners, receipts, and settlements
       |-> replay bundle + applicable property evaluation
       |
       `-> DharmaTelemetryProjectionV1                 [external projection]
            -> OTLP / Collector
            -> exactly one selected analysis backend
            -> anomaly hypothesis or replay request
            -> existing Verified Experiment Loop intake
            -> independent execution and verifier
            -> exact OperationalInputGate
```

The scenario lane is upstream: it helps generate questions, worlds, and
interventions. The telemetry lane is downstream: it helps inspect what the
real owner surfaces recorded. There is no telemetry-to-authority write-back
edge, and generated output never bypasses ordinary admission or verification.

This dossier narrows the relationship among existing surfaces; it does not
declare a replacement architecture:

- `EvidenceReceipt` and its owner remain canonical within their current scope.
- `ExecutionIdentity` remains the execution identity seam.
- `TelemetryPlaneStore` remains the existing internal company-state owner; this
  dossier does not redefine or replace it.
- `RuntimeTelemetryProjector` remains the existing internal runtime-to-company-
  state projector; this dossier does not create another telemetry read model.
- OpenTelemetry is an export/trace envelope, not a delivery protocol. NATS
  delivery and acknowledgement semantics remain governed by
  `NATS_SUBSTRATE_MASTER_SPEC.md`.
- Operational findings enter the existing `self_research.Hypothesis` / Verified
  Experiment Loop intake. There is no new `HypothesisCandidate` store or class.
- This does not replace or revive the older `SWARMLENS_MASTER_SPEC`; it only
  defines a narrow export, analysis, and epistemic boundary.

## 3. Normative words inside a non-normative dossier

`MUST`, `MUST NOT`, `SHOULD`, and `MAY` express the proposed contract. They do
not acquire repository authority until an admitted track promotes the relevant
parts through the normal ADR/spec process.

The candidate invariants are:

1. Existing owner records, receipts, settlements, replay bundles, verifier
   results, and promotion decisions MUST remain authoritative within their
   declared scopes.
2. Export disabled, delayed, duplicated, corrupted, sampled, or unavailable
   MUST NOT change execution, settlement, evaluation, or promotion.
3. External observability MUST be a write-only `plugin-sink`: it may receive a
   projection and may fail without affecting canonical state.
4. A simulated population MUST be treated as one correlated scenario instrument
   unless independence is demonstrated against preregistered criteria.
5. `origin_kind="simulated"` MUST remain provenance, not a new evidence modality.
6. Trace context, baggage, span attributes, dashboards, scores, ATIF `extra`
   fields, model confidence, and vendor metadata MUST NOT mint authority.
7. Canonical evidence MUST NOT be sampled. An external projection MAY be sampled
   only when scope-level coverage and completeness are explicit.
8. Every retained derived record SHOULD link to a digest-matching owner record.
9. A generated report, vote, interview, forecast, anomaly, SLO, profile, or
   ambient network/process event MUST NOT directly trigger promotion or runtime
   remediation.
10. External schema churn MUST stay behind a versioned adapter/profile and MUST
    NOT force churn into the canonical receipt schema.
11. Incoming correlation context MUST be treated as untrusted input.
12. Raw prompts, secrets, credentials, personal data, and unrestricted tool
    payloads MUST NOT be exported by default.

## 4. Five responsibility roles, not a new five-plane canon

The repository already uses other plane language. The following are five
responsibility/data roles for this proposal, not a replacement repo-wide
architecture.

| Role | Contents | Purpose | Authority boundary |
|---|---|---|---|
| 1. Canonical execution history | current owner records, receipts, settlements, replay bundles | durable execution truth within a declared scope | source for projections; never reconstructed from telemetry |
| 2. External telemetry projection | OTLP plus pinned `dharma.*` fields | correlation, transport, visualization | lossy and forgeable; no write-back or authorization |
| 3. Evaluation records | datasets, trials, scorers, baselines, lineage | scientific comparison | scores are evidence inputs, not promotion capabilities |
| 4. Operational analysis | trace queries, cohort deltas, SLOs, alerts, profiles | diagnosis and hypothesis generation | routes only to existing hypothesis/replay intake |
| 5. Promotion authority | evaluator-owned exact capability | authorize one particular promotion | consumes only a correctly typed, scoped, independently reproduced claim |

`ScenarioCorpusV1` sits upstream of role 1. It supplies simulated test input; it
is not a sixth role, an owner store, an evidence modality, or a promotion path.

## 5. `ScenarioCorpusV1`: simulated-input interchange

### 5.1 What to adapt from MiroFish and OASIS

The useful MiroFish pattern is the legible flow from source material to an
inspectable generated world:

```text
seed documents
  -> generated ontology / graph
  -> personas and environment configuration
  -> social-platform actions and recommendations
  -> per-round action stream
  -> synthesized report
  -> post-run interviews
```

That workflow is useful for stakeholder rehearsal, adversarial narratives,
intervention design, and new fixture/property coverage. It is not telemetry,
deterministic replay, calibrated forecasting, or independent consensus.

The lower-level OASIS interfaces are the preferred reuse candidate because the
pinned repository is Apache-2.0 and exposes environment, action/manual-action,
recommender, interview, and platform-extension mechanics. MiroFish is AGPL-3.0;
its product concepts and UX may inform the design, but its implementation MUST
stay outside a distributable Dharma component unless explicit license review
authorizes otherwise.

### 5.2 Minimum envelope

`ScenarioCorpusV1` is a versioned file/interchange schema, not a new database,
service, executor, or authority owner.

```json
{
  "schema": "dharma.scenario-corpus.v1",
  "scenario_id": "scenario_...",
  "source_cutoff": "2025-12-31T23:59:59Z",
  "seed_corpus_digest": "sha256:...",
  "source_manifest_digest": "sha256:...",
  "generator_code_digest": "sha256:...",
  "generator_models": [
    {
      "requested": "provider/model",
      "resolved": "provider/model@revision"
    }
  ],
  "prompt_bundle_digest": "sha256:...",
  "graph_digest": "sha256:...",
  "persona_bundle_digest": "sha256:...",
  "environment_config_digest": "sha256:...",
  "recommender_digest": "sha256:...",
  "randomness_control_digest": "sha256:...",
  "intervention_log_digest": "sha256:...",
  "action_timeline_digest": "sha256:...",
  "result_bundle_digest": "sha256:...",
  "report_bundle_digest": "sha256:...",
  "sample_id": "sample_...",
  "origin_kind": "simulated",
  "known_real_outcome_cutoff": null,
  "license_manifest_digest": "sha256:...",
  "provenance_manifest_digest": "sha256:..."
}
```

Required semantics:

- Every source artifact MUST be content-digested and covered by the source
  cutoff. Hindcasts MUST set `known_real_outcome_cutoff`, which MUST precede
  every source artifact available to the generator.
- Requested and resolved model/provider identity MUST be separate. Logical lane
  names are not model-family diversity.
- Every persona, report, interview, vote, and forecast inherits the scenario's
  simulated origin and manifest scope.
- Fixed, non-LLM corpus plumbing SHOULD support byte-identical fixture replay.
  Live LLM generation is not thereby deterministic.
- The schema MUST record licenses or use restrictions for inputs, models, and
  imported artifacts.

### 5.3 Action/event contract

Every action-timeline event MUST carry enough identity to detect omissions and
reconstruct declared causality without relying on wall-clock ordering:

```json
{
  "schema": "dharma.scenario-event.v1",
  "run_id": "run_...",
  "scenario_id": "scenario_...",
  "sequence": 42,
  "event_id": "event_...",
  "causal_parents": ["event_..."],
  "actor_id": "persona_...",
  "environment_id": "environment_...",
  "event_type": "manual_intervention",
  "input_digest": "sha256:...",
  "output_digest": "sha256:...",
  "intervention_or_fault_id": "intervention_...",
  "resolved_model_and_config_digest": "sha256:...",
  "settlement_id": "settlement_...",
  "result": "accepted"
}
```

A declared root has an empty `causal_parents` list plus an explicit root type.
Sequence is monotonic within one run; sequence alone makes no cross-run causal
claim. Missing parents, duplicate sequence identity, or an unbound result make
the corpus incomplete.

### 5.4 Epistemic interpretation

Dharma's evidence modalities remain closed:

```text
Observed | Reproduced | Reported | Inferred | Speculative
```

`origin_kind="simulated"` is orthogonal source provenance. For example:

- “The generator emitted artifact X” may be `Observed` if directly captured.
- X's statement about the target world is not thereby observed. Without
  independent evidence it remains `Speculative`.
- Replaying the generator may reproduce the generation event; it does not
  reproduce the target-world proposition contained in the output.
- Thousands of personas sharing seeds, graph construction, prompts, model
  families, and recommendation dynamics are correlated samples, not thousands
  of independent witnesses.

### 5.5 Two separate uses

Stakeholder rehearsal is the default permitted use. Success means the corpus
adds unique intervention, scenario, or property/fault activation at bounded
cost, preserves its simulated origin, and produces fixtures that an independent
test can reproduce.

Forecast use is disabled by default. It may be proposed only after the entire
hindcast gate in §10.3 passes. Narrative realism, agent count, interview quality,
votes, emergence, or apparent consensus are not substitutes for calibration.

## 6. `DharmaTelemetryProjectionV1`: external export profile

### 6.1 Identity and dependency direction

`DharmaTelemetryProjectionV1` names a versioned mapping/profile. It MUST NOT be
implemented as a new canonical class, table, ledger, store, telemetry plane, or
read model.

```text
existing owner transaction / append-only receipt
  -> existing owner cursor or same-owner outbox where available
  -> pure versioned projection profile
  -> OTLP
  -> Collector: redact | normalize | budget | export
  -> exactly one backend selected for an earned operational question
```

The first implementation, if admitted, SHOULD be a dependency-light pure
mapping plus a golden JSON fixture. This preserves the current local doctrine
that OpenInference-style normalization does not require an OpenInference,
OpenTelemetry, Langfuse, or LiteLLM runtime dependency. An SDK, Collector, or
backend deployment is a later operator decision.

### 6.2 Required projected fields

The profile SHOULD project only fields that exist in or can be derived
deterministically from current owners:

- owner type, canonical record ID, owner-local sequence, payload digest, and
  projection cursor;
- trace and span identity;
- parent/child for synchronous causality;
- explicit links for prerequisite, fork/join, `replay_of`, and
  `verification_of` relations;
- code/tree, world, manifest, configuration, fixture, choice-log, and effect
  digests when present;
- requested provider/model/backend separately from resolved
  provider/model/endpoint/backend and attempt;
- property ID/version, activation count/state, and exactly one result:
  `pass | fail | inconclusive | not_activated | invalid_test`;
- proposition, evidence modality, asserted principal, and scope as descriptive
  metadata only;
- retained-record completeness: `complete | partial`;
- projection-run, trace, and query completeness:
  `complete | partial | sampled | lost`;
- redaction-policy digest;
- projection profile, exporter, sampler, and external schema versions.

An illustrative interchange record is:

```json
{
  "profile": "dharma.telemetry-projection.v1",
  "owner": {
    "kind": "evidence_receipt",
    "record_id": "receipt_...",
    "sequence": 81,
    "payload_digest": "sha256:..."
  },
  "causality": {
    "trace_id": "...",
    "span_id": "...",
    "parent_span_id": "...",
    "links": [
      {"kind": "verification_of", "record_id": "receipt_..."}
    ]
  },
  "execution": {
    "manifest_digest": "sha256:...",
    "requested_provider": "...",
    "resolved_provider": "...",
    "requested_model": "...",
    "resolved_model": "...",
    "attempt": 1
  },
  "property": {
    "property_id": "dispatch_conformance.v1",
    "version": "1",
    "activation_count": 1,
    "result": "pass"
  },
  "epistemics": {
    "proposition": "ProductionDispatchConformance",
    "modality": "reproduced",
    "asserted_principal": "DispatchVerifierV1",
    "scope": "sha256:...",
    "authority": "descriptive_only"
  },
  "completeness": {
    "retained_record": "complete",
    "projection_scope": "complete"
  },
  "redaction_policy_digest": "sha256:..."
}
```

### 6.3 Causality

Use parent/child for ordinary synchronous calls. Use span links for relations
that are causal but not stack-like: prerequisite, enqueue/dequeue, fork/join,
replay, and verification. Wall-clock proximity MUST NOT be used as causal proof.
If NATS carries the event, its governed causal and acknowledgement fields remain
the delivery record; the OTel envelope does not replace them.

### 6.4 Completeness

Completeness belongs to a declared scope, not to an individual missing span:

- `complete`: every owner sequence in the declared range was projected and
  retained under the pinned policy;
- `partial`: declared fields or sources were intentionally unavailable;
- `sampled`: the pinned sampler intentionally omitted part of the declared
  owner-sequence range and records its decision/coverage;
- `lost`: unexpected owner-sequence gaps, cursor lag beyond its terminal bound,
  or terminal exporter failure were detected.

A missing span cannot label itself. `sampled` and `lost` MUST be inferred from
the projection run, owner sequence, cursor, sampler, and exporter state. “No
event observed” is not proof that no event occurred when completeness is not
`complete`.

### 6.5 Schema evolution

The frozen Dharma audit baseline's `EvidenceReceipt.to_otel_span()` emits the
older `gen_ai.system` attribute. The pinned OpenTelemetry GenAI semantic
conventions use `gen_ai.provider.name` and are marked Development. Therefore:

- the external mapping MUST be pinned and covered by golden fixtures;
- migration SHOULD occur inside the profile, not by making the canonical
  receipt depend on a moving external vocabulary;
- dual-read MAY exist only when an already selected backend requires it;
- OpenInference/GenAI vocabulary is interoperability metadata, not Dharma proof
  scope or authority.

### 6.6 Operational questions worth earning a backend for

The first slice should prove one real causal query before choosing a platform.
Candidate queries are:

1. accepted task with no canonical terminal settlement receipt;
2. duplicate effect commitment for one idempotency key;
3. incomplete A2A producer/consumer causal chain;
4. requested-versus-resolved provider/backend pseudodiversity;
5. property or promotion rejection by proposition, modality, principal, scope,
   activation, or manifest mismatch;
6. later-cycle live-closure lag;
7. projection lag/loss with a link to the canonical record and replay command.

A BubbleUp/Event-Deltas-style analysis compares a failing/rejected foreground
cohort against a scope-matched passing baseline, then ranks discriminating
dimensions such as tree digest, manifest, world, route, provider, model, tool,
queue age, retry, property, fault site, and causal predecessor.

Its output MUST route to the existing `Hypothesis` / Verified Experiment Loop
intake or a normal replay task. It is not a verified claim, root cause, automatic
fix, or new persistence owner.

## 7. Exactly one typed epistemic-authority contribution

`typed-contribution-id: EPI-OPERATIONAL-INPUT-GATE-001`

This dossier preserves one small language-level rule rather than a broad proof
calculus:

```text
Claim<Satisfies<P>, M, Principal<K>, Q>

where:
  P : Proposition
  M : EvidenceModality
  K : PrincipalId
  Q : Scope
```

For `S : ManifestDigest`, an automatic capability-promotion node `Promote<C>`
may execute only when:

```text
input = Claim<
  Satisfies<P>,
  Reproduced,
  Principal<K>,
  ManifestScope<S>
>
```

and all of the following are true:

1. `S` exactly equals the target manifest digest;
2. the proposition `P` is exactly the proposition required by this promotion;
3. the evaluator—not the payload—possesses
   `Authorize<K, P, Promote<C>, ManifestScope<S>>`.

The typechecker checks the proposition, modality, principal shape, and scope
shape. The evaluator checks exact digest equality and capability possession.
There is no generic global `RuntimeVerifier` super-authority. Deserializing an
`authority` string cannot mint a capability. Neither an OTel/ATIF attribute, a
MiroFish report, an LLM score, a builder receipt, a vendor badge, nor model
consensus can satisfy this gate.

Required counterexample fixture:

```text
builder claim:
  proposition = SurfaceParity
  modality = Reported
  principal = Builder
  scope = current source digest

telemetry attribute:
  authority = "RuntimeVerifier"

promotion requires:
  proposition = ProductionDispatchConformance
  modality = Reproduced
  principal = DispatchVerifierV1
  scope = exact current manifest digest
  evaluator-owned Authorize capability for this exact tuple

expected:
  rejection_code = EPI001
  promotion.invocation_count = 0
```

This closes two common holes at once: a reproduced but irrelevant proposition
does not authorize the desired action, and a payload cannot self-assert standing.

## 8. Keep four meanings of “replay” separate

| Meaning | What it does | What it does not prove |
|---|---|---|
| `ReplayBundleV1` | controlled semantic re-execution against an exact manifest and choice/fault record | representativeness outside its declared boundary |
| Temporal-style history replay | re-executes durable orchestration decisions while avoiding recorded side effects | property correctness or safe retry of ambiguous effects |
| ATIF trajectory playback | ports an ordered agent interaction for inspection/evaluation | canonical causality, exact world replay, or authority |
| trace/query navigation | drills through projected telemetry and exemplars | re-execution, completeness, or a reproduced claim |

Only controlled replay plus an applicable independent verifier may produce the
`Reproduced` claim needed by the proposed promotion gate.

## 9. What to copy, adapt, or avoid

| System / pattern | Decision | Copy or adapt | Explicit limit |
|---|---|---|---|
| MiroFish | adapt concepts | seed-to-world UX, personas, intervention workbench, action timeline, reports/interviews | AGPL code stays out without review; no replay, prediction, or consensus authority |
| OASIS | borrow selectively | environment/action/manual-action, recommender, interview, platform extension interfaces | published scale and external validity were not reproduced here |
| OpenTelemetry + Collector | borrow | OTLP, spans, links, events, redaction/export membrane | not a canonical event store or delivery authority |
| OTel GenAI conventions | adapt behind a pin | provider/model/agent vocabulary | Development status; no Dharma authority semantics |
| OpenInference | adapt vocabulary | cross-framework model/agent/tool normalization | not proof scope or evaluator capability |
| Harbor ATIF | export only | portable ordered trajectory interchange | not causal completeness, replay, or authority |
| Temporal history | adapt concepts | history/visibility/activity distinction | do not add an orchestrator for its UI or call history replay property proof |
| Honeycomb BubbleUp / ClickStack Event Deltas | adapt method | foreground-versus-baseline discriminator ranking | a ranked discriminator is a hypothesis, not root cause |
| Tempo TraceQL | optional backend | structural trace queries and exemplars | not a replay engine or owner |
| Google SRE | borrow | multi-window SLO burn alerts | an alert does not prove an individual proposition |
| Hubble / Tetragon | later, if earned | ambient network/process witness on Linux/Kubernetes | drops make absence non-proof; not needed without a real boundary |
| Pyroscope | later, if earned | span-correlated CPU/resource diagnosis | performance evidence is not correctness evidence |

Choose exactly one backend, and only after the concrete query, current
operational estate, retention/cardinality budget, and operator owner justify it:

- Tempo/TraceQL if an existing Grafana estate and structural trace queries are
  the dominant need;
- ClickHouse/ClickStack if local high-cardinality wide-event analysis is the
  dominant need;
- Honeycomb if managed cohort exploration and operational simplicity justify
  the service boundary.

Do not deploy a full “LGTM plus ClickHouse plus Honeycomb” stack speculatively.

## 10. Acceptance gates

### 10.1 Thin telemetry slice

The proposed adapter/profile is acceptable only if all of these pass:

- Disabling, delaying, duplicating, or corrupting export changes no canonical
  state, settlement, verifier result, or promotion decision.
- Every retained projection resolves to a digest-matching canonical record.
- Tampered attributes, trace context, or baggage cannot pass
  `OperationalInputGate`.
- The golden fixture contains no raw prompts, credentials, secrets, or personal
  data.
- Sampling and loss are visible at the correct projection scope.
- One fixture trace connects acceptance, routing, resolved provider attempt,
  effect settlement, property result, and promotion decision.
- One cohort query reaches a canonical exemplar and an applicable replay command.
- Removing the adapter requires no canonical data migration.

### 10.2 Scenario rehearsal

The proposed scenario spike is acceptable only if:

- every artifact is frozen-input traceable and tagged `origin_kind="simulated"`;
- a temporal leakage scan finds zero post-cutoff source material;
- fixed non-LLM plumbing replays byte-identically;
- generated reports and personas remain non-promotable;
- at least three previously unactivated properties, fault sites, or stakeholder
  interventions are activated and survive independent fixture reproduction;
- cost per independently reproduced useful case is no worse than the
  preregistered simpler generator baseline.

### 10.3 Optional forecast hindcast

Forecast language remains disabled unless one frozen protocol passes all of the
following:

1. At least 30 development cases and a separate 30-case holdout are frozen
   across at least three domains before outcomes are revealed.
2. Each held-out case has at least 30 stochastic replications, collapsed into
   exactly one preregistered aggregate probability per case before scoring.
   Seeds estimate Monte Carlo variance; they are not independent events.
3. Brier score, log-loss, calibration, ranking, abstention, and cost analysis are
   preregistered.
4. Base-rate, persistence/simple statistical, and single-agent baselines are
   included.
5. At least two genuinely distinct **resolved** model families are used.
6. Relative Brier improvement is at least 10% over the strongest preregistered
   simple baseline, with a paired-bootstrap 95% confidence interval excluding
   zero. The bootstrap resamples held-out cases stratified by domain, never
   seed-level runs.
7. Expected calibration error is at most `0.10`.
8. A preregistered outcome-permutation broken control is at least `0.05`
   absolute Brier worse, with the case-stratified paired-bootstrap 95% interval
   for that gap excluding zero.
9. For every preregistered persona, graph, prompt, and recommender perturbation,
   worst-case absolute Brier degradation is at most `0.05` and ECE remains at
   most `0.10`.
10. Temporal leakage is zero and every input/version is recorded.

Failure of any gate demotes the system to exploratory scenario/hypothesis
generation. It does not permit selective reporting of a forecast success.

## 11. Kill and stop criteria

Kill the telemetry adapter/profile if it:

- writes back or becomes another owner, store, ledger, read model, or execution
  path;
- changes settlement or runtime behavior when its exporter fails;
- treats span status as the five-state property result;
- samples canonical evidence;
- stores raw prompts, secrets, or personal data by default;
- cannot pin schema behavior with golden fixtures;
- lets an analysis, alert, or profile trigger promotion/remediation directly.

Defer or remove a backend if it becomes a second truth store, cannot enforce the
redaction/cardinality budget, or has no owned query that leads back to canonical
evidence.

Stop forecast claims if leakage appears, a numeric lift/calibration/broken-
control/sensitivity gate fails, provider diversity resolves to one backend,
version drift is unrecorded, or narrative confidence rises while calibration
worsens.

Stop the scenario spike if MiroFish AGPL code enters a distributable component
without review, synthetic target-world content is represented as observed,
cost exceeds the simpler baseline, or the lane creates another executor or
authority store.

## 12. Proposed implementation sequence — only after track admission

| Stage | Deliverable | Exit condition |
|---|---|---|
| 0. Revalidation | current owner/seam map, operator, threat model, schema freeze | current `HEAD` and active-track constraints recorded |
| 1. Pure projection | dependency-light mapping, golden fixture, negative authority fixture | adapter removal/failure has no canonical effect |
| 2. One earned query | one backend or local test harness for one causal question | exemplar reaches owner record and replay |
| 3. Scenario rehearsal | OASIS-style isolated fixtures and intervention corpus | unique independently reproduced coverage at bounded cost |
| 4. Optional hindcast | sealed/preregistered datasets and scoring | every §10.3 gate passes |
| 5. Ambient/performance witnesses | Hubble/Tetragon or Pyroscope only for a measured need | loss semantics and authority boundary tested |

Likely first-slice file surfaces, subject to revalidation, are:

```text
dharma_swarm/spine/otel_projection.py                 pure plugin-sink mapping
tests/test_spine_otel_projection.py                   invariants and failures
tests/fixtures/spine/dharma_telemetry_projection_v1.json
```

The implementation MUST use `# spine: plugin-sink` and MUST NOT create a new
database, runtime dependency, or `TelemetryPlaneStore` peer. The exact scenario
lab owner and path are intentionally unresolved until a track establishes
whether it belongs in the replay laboratory, Forge fixtures, or a separate
research harness.

The July 2026 assessment estimated 5–8 engineer-days for a thin projection and
5–10 engineer-days for an isolated scenario spike. These are planning estimates,
not commitments. The telemetry slice may accompany replay RFC-001 but must not
outrank it.

## 13. Pinned prior-art register

This table preserves the inspected versions. It does not claim that every
upstream system was executed or that current upstream still matches these pins.

| Source | Inspected pin | License / status | Evidence used |
|---|---|---|---|
| [MiroFish](https://github.com/666ghj/MiroFish) | `96096ea0ff42b1a30cbc41a1560b8c91090f9968` | AGPL-3.0 | source/docs inspection of workflow, logs, reports, state, tests; no live LLM/Zep run |
| [OASIS](https://github.com/camel-ai/oasis) | `7234ac32589499ffb493e053f36d4de82aec8f43` | Apache-2.0 | source/docs interface inspection; paper results not reproduced |
| [OASIS paper](https://arxiv.org/abs/2411.11581) | arXiv v1 inspected | author-reported research | reported scale/phenomena only; no independent reproduction |
| [OpenTelemetry semantic-conventions GenAI](https://github.com/open-telemetry/semantic-conventions-genai) | `63f8200eee093730ce845d26ce2aafb621b0807e` | Apache-2.0; GenAI Development | attribute/schema inspection |
| [OpenInference](https://github.com/Arize-ai/openinference) | `3f8994b70dd2b0595f3bad5c6698896384cdd613` | Apache-2.0 | agent/model/tool vocabulary inspection |
| [Harbor / ATIF](https://github.com/harbor-framework/harbor) | `16a510cecbda385d9d98b50d5096d7c36378f95a` | Apache-2.0 | trajectory interchange inspection |
| [Temporal](https://github.com/temporalio/temporal) | `710be0d0e30cf578df910235c048e474768a5565` | MIT | history/visibility/activity concepts |
| [Grafana Tempo](https://github.com/grafana/tempo) | see assessment manifest | AGPL-3.0 | TraceQL and exemplar concepts |
| [Cilium Hubble](https://github.com/cilium/cilium) | see assessment manifest | Apache-2.0 | ambient network visibility and loss semantics |
| [Tetragon](https://github.com/cilium/tetragon) | see assessment manifest | Apache-2.0 | ambient process/security witness concepts |
| [Grafana Pyroscope](https://github.com/grafana/pyroscope) | see assessment manifest | AGPL-3.0 | span-correlated profiling concepts |

The July 14 extension was source-and-documentation inspection only. It did not
start or reproduce a live MiroFish/Zep run, OASIS million-agent run, Collector,
trace backend, Kubernetes/eBPF environment, or profiler deployment.

### Dharma baselines

- Frozen audit baseline: `origin/main@c14b950bc5009f2200d9425155010be508ead981`.
- A 2026-07-14 source recheck observed
  `origin/main@c631a4925645274c4d53fba112a5107200a12faf` and confirmed the
  named `EvidenceReceipt`, `ExecutionIdentity`, `TelemetryPlaneStore`,
  `RuntimeTelemetryProjector`, and dependency-light `llm_burn` seams.
- The authoring checkout was dirty and changed concurrently. Therefore no
  current-code implementation claim is made here; revalidation at admitted
  implementation `HEAD` is mandatory.

## 14. Security, privacy, and operational budgets

Before any live exporter is enabled, the admitted track MUST define:

- allowlisted fields and redaction-policy digest;
- retention by record class;
- high-cardinality budget and which fields may never become metric labels;
- data residency and vendor-boundary constraints;
- cursor/outbox failure and recovery behavior;
- sampling policy for noncanonical projection data;
- exporter authentication and certificate/key handling;
- operator ownership for alerts, costs, and deletion requests;
- a secret/PII fixture that proves forbidden data is absent;
- a rollback test that removes export without canonical migration.

Incoming `traceparent`, `tracestate`, baggage, model metadata, and vendor fields
are untrusted correlation hints. They require length/cardinality limits and MUST
never be copied into an authority-bearing field.

## 15. Non-goals

- Replacing canonical receipts, owners, runtime state, or the existing internal
  telemetry plane.
- Creating a second simulator, executor, orchestrator, evaluator, event ledger,
  candidate store, authority store, or telemetry read model.
- Treating MiroFish as telemetry, deterministic simulation, forecast oracle, or
  independent consensus.
- Adding `simulated` as an evidence modality.
- Deploying a full observability stack before one query earns it.
- Adopting Temporal merely for history UI.
- Ingesting ATIF or OTel as proof.
- Automatic remediation or promotion from alerts.
- Raw prompt, secret, or personal-data retention.
- Kubernetes/eBPF infrastructure before a real target exists.
- Using profiles as correctness evidence.
- Importing AGPL implementation code without explicit review.
- Adding a confidence lattice, consensus-to-truth coercion, generic proof
  calculus, or self-declared verifier authority.

## 16. Open decisions before implementation

1. Which current owner/outbox seam can project without a new persistence
   surface at implementation `HEAD`?
2. Which active track and operator own the work?
3. What exact query justifies the first backend, if any?
4. What retention, cardinality, privacy, and cost budgets apply?
5. Does MiroFish remain prior art only? Default: yes.
6. Is stakeholder rehearsal sufficient, or is a fully funded preregistered
   hindcast justified? Default: rehearsal only.
7. Which replay-lab/Forge surface owns scenario fixtures without adding an
   executor?
8. What rollback receipt proves the export membrane is removable?

## 17. Promotion checklist for this dossier

This reference may become an active spec only when:

- an operator admits or assigns an active track;
- current code and canonical docs have been re-audited;
- the owner and exact code surfaces are named;
- the schema, threat model, negative authority fixture, and rollback test are
  accepted;
- a concrete causal query justifies any backend;
- licensing review preserves the MiroFish/OASIS boundary;
- the spec creates no second owner/read model/candidate store;
- acceptance and kill criteria remain executable;
- the active spec states exactly which parts of this dossier it adopts,
  changes, or rejects.

Until then, this file is durable research context—not build authority.
