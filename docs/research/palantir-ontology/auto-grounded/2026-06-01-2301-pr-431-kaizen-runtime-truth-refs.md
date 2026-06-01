# Artifact
- **Artifact:** PR #431 — “feat(kaizen): bind reviews to runtime truth refs” ([GitHub PR](https://github.com/AmitabhainArunachala/dharma_swarm/pull/431))
- **Trigger:** New open PR updated in last 2h; touches “truth refs / evidence refs / identity invariant digest” surfaces.

## What it claims (non-editorial)
PR #431 adds a “runtime truth refs” concept to KaizenReview by copying trace/receipt/identity references from source AgentOps `report.json` files into `kaizen_review.json` and `kaizen_review.md`, and then projecting a small runtime refs summary into the Daily Operating Brief and Operating Facts bundle. The PR also states a boundary: KaizenReview may *copy* references but does not create receipt authority, claim live NATS contact, dispatch work, mutate ontology, or decide Forge fitness.

Concretely, it:
- Extracts a `runtime_truth_refs` dictionary from AgentOps reports by pulling known scalar/list keys and selected nested dicts.
- Computes a `runtime_truth_summary` (jobs with refs / without refs + union of ref keys).
- Treats KaizenReview organ-state as more “bound” if there is both a next-work-packet recommendation and runtime refs.
- Adds evidence references to organ evidence by including the review source path plus extracted receipt/trace/digest values.

## External grounding (primary sources)
### Palantir Foundry ontology identity: API names vs RIDs (engineering reality, not marketing)
Foundry’s ontology APIs treat **API names and RIDs as distinct identifiers**, and explicitly model RIDs as **unique resource identifiers** that are used across other APIs ([Palantir Ontologies API “Get Ontology”](https://palantir.com/docs/foundry/api/ontologies-v2-resources/ontologies/get-ontology/)).

For object types, Foundry similarly distinguishes the human-facing **API name** from a **RID**, and explicitly calls an integer-like “unique ID” a *legacy identifier* “not recommended for use in new applications,” while the RID is described as “useful for interacting with other Foundry APIs” ([Palantir Object Types API “Get Object Type”](https://palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/)).

**Why this matters for PR #431:** PR #431 is building a mini “identity spine” for operational artifacts (Kaizen reviews) using heterogeneous keys (`trace_id`, `run_id`, `receipt_refs`, `identity_invariant_digest`, etc.). Palantir’s approach suggests you need an explicit separation between (a) human-oriented names, (b) stable globally unique identifiers, and (c) legacy/ephemeral IDs—*and tooling that treats them differently* ([Palantir Object Types API “Get Object Type”](https://palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/)).

### Palantir Foundry ontology lifecycle: edits + “latest state” materialization + retention realities
Foundry’s object edits/materializations emphasize (1) composing “latest state” from backing datasources plus user edits, and (2) sharp retention constraints where “only the latest snapshot is guaranteed to be available” unless a downstream transform persists history ([Palantir “Object edits and materializations”](https://palantir.com/docs/foundry/object-edits/materializations/)).

**Why this matters for PR #431:** the PR’s “runtime truth refs” are positioned as durable evidence references, but Palantir’s docs make a repeated point: without explicit downstream persistence design, history disappears and “latest state” can mask provenance unless you treat provenance as first-class and persist it deliberately ([Palantir “Object edits and materializations”](https://palantir.com/docs/foundry/object-edits/materializations/)).

### Provenance theory: identity, evolution, and responsibility are modeled—not guessed
W3C PROV frames provenance as a graph over **entities**, **activities**, and **agents**, with explicit mechanisms for versioning/evolution (each revision is a *new entity*) and responsibility (agents associated with activities, entities attributed to agents) ([W3C PROV Model Primer](https://www.w3.org/TR/prov-primer/)).

PROV also explicitly allows multiple co-existing “descriptions” of the same thing and links them via specialization/alternate relationships, which is a disciplined way to represent “same run described differently by different systems” without collapsing identity incorrectly ([W3C PROV Model Primer](https://www.w3.org/TR/prov-primer/)).

**Why this matters for PR #431:** the PR currently flattens multiple semantics (receipt, trace, correlation, identity digest) into a bag of strings and uses them directly as evidence refs. A PROV-grade approach would type these: Which are entities? Which are activities? Which are agent identifiers? Which are revision identifiers? And which system is asserting them? ([W3C PROV Model Primer](https://www.w3.org/TR/prov-primer/)).

### Distributed tracing reality: “trace_id” is not evidence—it's a correlation handle
OpenTelemetry’s context propagation explains that trace/span IDs exist to correlate signals across services and are propagated (e.g., via `traceparent`) to build end-to-end causality across distributed systems ([OpenTelemetry “Context propagation”](https://opentelemetry.io/docs/concepts/context-propagation/)).

**Why this matters for PR #431:** a trace ID helps you *find* evidence (logs/spans/metrics) but is not itself evidence of correctness, nor a durable receipt of an effect. Treating `trace_id` as evidence can become an integrity vulnerability (it proves a request was traced, not that the outputs are correct) ([OpenTelemetry “Context propagation”](https://opentelemetry.io/docs/concepts/context-propagation/)).

### Ontology concept vs data reality: objects are backed by data sources
Foundry’s ontology docs emphasize that object types are schemas for real-world entities/events and are powered by “backing datasources” connected into the ontology ([Palantir “Object types overview”](https://palantir.com/docs/foundry/object-link-types/object-types-overview/)).

**Why this matters for PR #431:** PR #431 defines a boundary (“no runtime/ontology ownership”), but it still creates a schema-like object (`runtime_truth_refs`) whose values are sourced from upstream “datasources” (AgentOps reports). If you want Palantir-grade correctness, you need explicit data contracts for those upstream reports (what keys, what types, what allowed values), and you need invariants that prevent invented references from entering the system ([Palantir “Object types overview”](https://palantir.com/docs/foundry/object-link-types/object-types-overview/)).

## Gaps surfaced (concrete, adversarial)
1. **No stable identifier hierarchy (name vs durable ID vs correlation handle).** Palantir makes an explicit split between API name, RID, and legacy IDs, and warns against legacy IDs in new apps ([Palantir Object Types API “Get Object Type”](https://palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/)). PR #431 mixes trace IDs, receipt refs, and “identity invariant digests” without defining which are durable “RIDs” vs ephemeral correlation tokens.

2. **Evidence references are not typed, scoped, or attributable.** PROV’s baseline is: who asserted what, about which entity/activity/agent, and how versions relate ([W3C PROV Model Primer](https://www.w3.org/TR/prov-primer/)). PR #431 stores raw key/value material without a typed provenance model (no agent attribution, no activity linkage, no revision semantics).

3. **No explicit retention / replay strategy for runtime evidence.** Foundry’s docs are blunt: without explicit design, history is deleted and only latest snapshots are guaranteed ([Palantir “Object edits and materializations”](https://palantir.com/docs/foundry/object-edits/materializations/)). PR #431 does not state where receipts/traces live, their retention, whether refs remain resolvable, or how the system fails when they expire.

4. **Trace correlation is being used as “truth binding.”** OpenTelemetry makes clear trace/span IDs exist for correlation across signals and services ([OpenTelemetry “Context propagation”](https://opentelemetry.io/docs/concepts/context-propagation/)). PR #431’s organ-state uses “runtime truth refs” as a binding criterion without distinguishing correlation handles from cryptographic/durable receipts.

5. **No schema contract for AgentOps reports; refs can be invented or garbage.** Foundry ontology object types are powered by backing datasources, implying contracts and mapping discipline ([Palantir “Object types overview”](https://palantir.com/docs/foundry/object-link-types/object-types-overview/)). PR #431 attempts “invented refs are invalid,” but does not define validation rules, allowed prefixes (`receipt://...`), or how to reject/alert on malformed refs.

## Adversarial questions (the PR does not answer)
1. What is the *durable* identifier for a “runtime truth reference set” analogous to a Foundry RID, and what is merely a label/correlation token ([Palantir Ontologies API “Get Ontology”](https://palantir.com/docs/foundry/api/ontologies-v2-resources/ontologies/get-ontology/))?

2. If `trace_id` is present but the trace backend has evicted data, is the review still “bound,” and what observable checks prevent false confidence ([OpenTelemetry “Context propagation”](https://opentelemetry.io/docs/concepts/context-propagation/))?

3. Who is the asserting agent for each reference (AgentOps? Kaizen bridge script? upstream runtime?), and how is responsibility represented (e.g., PROV attribution/association) ([W3C PROV Model Primer](https://www.w3.org/TR/prov-primer/))?

4. What prevents a malicious or buggy AgentOps report from inserting arbitrary `receipt_refs` that look valid but don’t correspond to real evidence?

5. Do “identity invariant digests” have a formal definition (hash of what payload, canonicalization, algorithm, collision expectations), or are they currently just strings?

## Recommended next move
Treat PR #431 as a useful “plumbing” step, but not as a legitimate Palantir-grade grounding of operational judgments in runtime truth. Before merging, require a follow-on design that (a) defines an explicit identifier taxonomy (durable vs ephemeral) aligned with the API-name/RID split Palantir uses, (b) introduces validation + resolvability checks for refs (otherwise the system can be trivially poisoned), and (c) upgrades “runtime truth refs” from a bag of strings to a typed provenance model (PROV-inspired) with attribution, versioning, and retention semantics.
