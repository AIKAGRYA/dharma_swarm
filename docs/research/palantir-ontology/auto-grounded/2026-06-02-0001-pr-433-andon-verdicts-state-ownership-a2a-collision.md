# Grounding Report — PR #433: ANDON verdicts (Slices D + E)

**Artifact:** PR #433 — “andon(verdict): devin slices D + E — restacked onto main” (https://github.com/AmitabhainArunachala/dharma_swarm/pull/433)

## What it claims

PR #433 adds two internal “verdict” documents that evaluate ANDON Layer-2 Revision 3 claims: (D) workflow state ownership is fragmented and lacks a `workflowRun` boundary, and (E) the system uses `A2ATask` for both external protocol traffic and internal work-queue delegation, allegedly creating a dangerous conflation.

The verdict for Slice D states that there are many state surfaces (SQLite-backed runtime state plus multiple JSONL ledgers and in-memory managers), that durable workflow-run boundaries are not first-class (a workflow-state contract exists but lacks a runtime producer), and that the “multiple owners” issue is layered rather than competing writes.

The verdict for Slice E confirms that a single `A2ATask` model is used across internal and external boundaries, but argues this is a deliberate protocol-level choice because the gateway enforces authentication, tags provenance of origin, strips internal fields before returning results, and limits delegation depth.

## External grounding

### Palantir Foundry Ontology: identifiers and canonical names are first-class

Foundry’s Ontology APIs explicitly treat both a stable API name and a stable Resource Identifier (RID) as canonical handles for referencing an ontology (“API name or RID of the Ontology”), which is a concrete example of “durable identifier discipline” rather than ad-hoc strings and correlation IDs ([Palantir Foundry API: Get Ontology (v2)](https://palantir.com/docs/foundry/api/ontologies-v2-resources/ontologies/get-ontology/)).

Palantir’s own developer conventions distinguish between an object representing the identifier (`resourceIdentifier`) and a string representation (`rid`), which highlights why mixing “from_agent” strings, “remote” markers, and transport-specific tags quickly becomes messy without typed identity surfaces ([palantir/resource-identifier issue #4](https://github.com/palantir/resource-identifier/issues/4)).

### Palantir Foundry Ontology: actions are transactional, not just “events happened”

In Foundry, an “action is a single transaction” that commits edits to objects/properties/links and is reflected across applications, with consistent validation and side effects defined by an action type ([Palantir Foundry docs: Action types overview](https://palantir.com/docs/foundry/action-types/overview/)).

This matters because it implies that “workflow runs” in an ontology-centric system are not merely logs; they are accountable, replayable, permission-checked state transitions (which Slice D’s verdict still treats as missing but doesn’t specify how to model).

### Provenance modeling: “workflow run boundary” is a solved standards problem

The W3C PROV model provides explicit primitives that match what Slice D describes as missing: `prov:Activity` (a run over time), `prov:startedAtTime`/`prov:endedAtTime`, `prov:used` and `prov:wasGeneratedBy` to chain inputs and outputs, and `prov:Agent` responsibility edges ([W3C PROV-O Recommendation](https://www.w3.org/TR/prov-o/)).

PROV-O also provides a way to qualify relationships (e.g., usage/generation as first-class nodes via `prov:Usage`/`prov:Generation`) that can carry additional attributes like “role”, “plan”, or “atTime,” which is exactly the sort of structured run record missing from “delegation-only” traces ([W3C PROV-O Recommendation](https://www.w3.org/TR/prov-o/)).

### Identity collision: global identifiers have rules; “strings” do not

RDF’s core concept is that IRIs are globally-scoped identifiers, and reusing the same IRI denotes the same resource; “IRI collision” is called out as an interoperability problem when you violate global identity discipline ([W3C RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/)).

This is relevant to Slice E: if you want “A2A task is protocol-level” to be safe, you need a globally unambiguous identity model for “agents”, “nodes”, “tasks”, and “runs”, not a set of strings and ad-hoc tags.

### Ontology structure: schema-level rigor is explicit, not implied

Foundry draws a clear line between a schema definition (“property”) and a value on an object instance (“property value”), and calls out keying and uniqueness as an explicit design surface (including warnings against time values as primary keys because of collisions and representation issues) ([Palantir Foundry docs: Properties overview](https://palantir.com/docs/foundry/object-link-types/properties-overview/)).

This is directly relevant to Slice D’s state-owner inventory: without explicit keys for “workflow run”, “delegation”, “session”, “mission”, etc., you will end up with unstable join semantics across the multiple ledgers.

### Palantir marketing claim (useful only as hypothesis, not evidence)

Palantir’s public post claims “actions capture the kinetics between objects” and that action writebacks enable learning loops, but it is not an engineering spec; treat it as a prompt to demand concrete system guarantees (IDs, audit semantics, replay, permissions, conflict handling), not as proof of capabilities ([Palantir Blog: The Ontology: Resilience in crisis](https://blog.palantir.com/the-ontology-resilience-in-crisis-7833bb5e15e7)).

## Gaps surfaced

1. **No explicit “workflow run” object with durable identifier + lifecycle semantics.** Slice D asserts the absence of a run boundary, but neither verdict defines the minimal schema for a run (stable ID, start/end, participants, inputs/outputs, status transitions) in the style of PROV `prov:Activity` ([W3C PROV-O Recommendation](https://www.w3.org/TR/prov-o/)) and Palantir’s RID/APIName discipline ([Palantir Foundry API: Get Ontology (v2)](https://palantir.com/docs/foundry/api/ontologies-v2-resources/ontologies/get-ontology/)).

2. **No ontology-grade identity model for agents/nodes/tasks.** Slice E argues that `from_agent` strings plus `metadata["source"]` tags are “distinguishable,” but RDF-style identity discipline says the hard part is global scope and collision avoidance, not local tagging ([W3C RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/)).

3. **No transactional semantics for “edits” to runtime truth.** Foundry’s action types are explicit transactions with consistent validation and writeback behavior; the verdicts do not map “state changes” and “delegation results” to any transaction/audit primitive that would support replay, governance, or compliance ([Palantir Foundry docs: Action types overview](https://palantir.com/docs/foundry/action-types/overview/)).

4. **Keying / uniqueness constraints across layered ledgers are undocumented.** Foundry documentation emphasizes primary keys and collision pitfalls as a schema-level concern; the verdict’s inventory lists many stores but does not specify how their keys join safely (session ID vs delegation ID vs mission ID vs context ID) ([Palantir Foundry docs: Properties overview](https://palantir.com/docs/foundry/object-link-types/properties-overview/)).

5. **“Protocol-level unit of work” claim lacks an external spec citation.** The Slice E verdict appeals to an “A2A 1.0 spec” but does not cite a public standard or doc; if the protocol is intended to be interoperable, it must have a concrete, citable model and conformance story (contrast: PROV-O and RDF are public, normative specs) ([W3C PROV-O Recommendation](https://www.w3.org/TR/prov-o/); [W3C RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/)).

## Adversarial questions

1. What is the canonical identifier scheme for `workflowRun`, `task`, `agent`, and `node` (string format, minting authority, collision domain), and how does it align with RID-style stable identifiers (rather than correlation IDs)? ([Palantir Foundry API: Get Ontology (v2)](https://palantir.com/docs/foundry/api/ontologies-v2-resources/ontologies/get-ontology/); [palantir/resource-identifier issue #4](https://github.com/palantir/resource-identifier/issues/4))

2. If a workflow-run is missing, what is the intended provenance model: do we want PROV `Activity/Entity/Agent` semantics (inputs/outputs, responsibility, start/end), and if not, what is the alternative and why is it better? ([W3C PROV-O Recommendation](https://www.w3.org/TR/prov-o/))

3. Where are the transactional boundaries and audit logs for state transitions that matter (permissions, validation, writeback), analogous to Foundry’s “action is a single transaction”? ([Palantir Foundry docs: Action types overview](https://palantir.com/docs/foundry/action-types/overview/))

4. If `A2ATask` is protocol-level, what are the required fields for safe interoperability at the network boundary (identity, authentication context, authorization scope, replay protection) beyond “X-A2A-Key” and “metadata source tag”? ([W3C RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/))

5. What are the primary keys for each “state surface” in Slice D’s inventory, and what are the guaranteed join paths between them (including time/version semantics), given Foundry’s explicit warnings about key choice and collisions? ([Palantir Foundry docs: Properties overview](https://palantir.com/docs/foundry/object-link-types/properties-overview/))

## Recommended next move

Rework is justified: these verdicts are useful as internal diagnostics, but they do not yet ground “workflow run boundary” and “internal/external A2A conflation” against the rigor of (a) Foundry-style identifier discipline and transactional action semantics, and (b) standards-grade provenance/identity modeling (PROV-O + RDF). The next move should be to specify a minimal ontology-aligned “WorkflowRun” object type (or PROV Activity specialization) plus a typed identity scheme for agents/nodes/tasks, and then re-audit Slice D/E against that explicit model rather than against informal “layered vs competing” arguments.
