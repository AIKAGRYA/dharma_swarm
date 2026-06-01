# Artifact
- **Artifact:** PR #436 (merged) — `feat(spine): add runtime identity mapping receipts [impact-checked]`
- **Link:** https://github.com/AmitabhainArunachala/dharma_swarm/pull/436
- **Commit (merge):** a4d07e8

## What it claims
This change adds a durable “identity mapping receipts” mechanism in the runtime spine (SQLite-backed RuntimeStateStore) so that external identifiers (workflow_id, proposal_id, event_id, message_id, ontology_action_id, engine_artifact_id) can be mapped to a canonical `run_id` and later resolved deterministically.

It exposes helper APIs (async + sync) to record mappings idempotently, list them, resolve an external ID to `run_id`, and include mappings as a section in `get_run_ledger(run_id)`.

## External grounding
### What Palantir’s Ontology actually emphasizes (and what that implies for our “ontology action id” mappings)
Palantir positions the Foundry Ontology as both (a) semantic elements—objects, properties, links—and (b) kinetic elements—actions, functions, and dynamic security—so operational change is expressed as controlled actions/functions over governed objects. ([Palantir Ontology overview](https://www.palantir.com/docs/foundry/ontology/))

Palantir describes the Ontology backend as multiple services: a metadata service defining object types/link types/action types, and object databases responsible for querying and writeback orchestration. That is: “IDs” are not merely convenience keys; they are part of a system that supports indexing/query computation and orchestrated edits. ([Palantir Ontology architecture](https://www.palantir.com/docs/foundry/object-backend/overview))

Foundry’s action APIs explicitly treat “apply action” as a first-class operation, with batching limits and visibility/consistency semantics tied to object storage versioning (eventual consistency vs immediate visibility). This is an operational contract, not just a log line: it implies a need for traceability across “action invocation → object edits → visibility semantics.” ([Palantir API: Apply Action Batch](https://www.palantir.com/docs/foundry/api/ontology-resources/actions/apply-action-batch))

In AIP Logic, tool calls and ontology edits are executed under the invoking user’s permissions, and there is an explicit statement that ontology edits are only written when the Logic function is executed from an action (even if the function contains an “apply action” block). This is a concrete example of *governed write-paths*, and implies that “action IDs” carry provenance/security semantics beyond correlation. ([Palantir AIP Logic blocks](https://www.palantir.com/docs/foundry/logic/blocks))

### What semantic/ontology standards emphasize (and what that implies for our “mapping receipts”)
RDF models information as triples in a directed labeled graph and uses IRIs/blank nodes/literals to identify resources and values; the identifier design is a core part of the data model, not an implementation detail. ([W3C RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/))

OWL 2 defines a formal logic-based ontology language with explicit semantics (classes, properties, individuals, axioms) intended for machine reasoning over meaning, not just linking IDs. This creates a hard bar: any “ontology” work that stays at correlation IDs is pre-semantic. ([W3C OWL 2 Structural Specification](https://www.w3.org/TR/owl2-syntax/))

## Gaps surfaced (concrete, PhD-grade)
1) **“Ontology action id” is treated as a string key, but Palantir-style kinetics treat actions as governed edits with consistency semantics.** We have no explicit model for action invocation context (actor/principal, permission scope, submission criteria, branch-vs-main semantics, or object storage visibility semantics). Palantir’s action API and AIP Logic docs show those semantics exist and matter. ([Palantir API: Apply Action Batch](https://www.palantir.com/docs/foundry/api/ontology-resources/actions/apply-action-batch)) ([Palantir AIP Logic blocks](https://www.palantir.com/docs/foundry/logic/blocks))

2) **No provenance graph, only point lookups.** Mapping receipts create a reversible association external_id → run_id, but do not create a provenance DAG of “this run produced these artifacts, invoked these actions, wrote these objects,” which is closer to what an ontology-backed operational platform needs (and what Palantir’s backend description implies via writeback orchestration + indexing). ([Palantir Ontology architecture](https://www.palantir.com/docs/foundry/object-backend/overview))

3) **No semantic commitment: identifiers exist without a type system that can support reasoning.** RDF/OWL grounding suggests identifiers and relations are only meaningful when embedded in a typed graph with explicit predicates/axioms. The current design records mappings for a fixed set of kinds but does not model relations/constraints among them (e.g., `message_id` emitted-by `workflow_id`, `ontology_action_id` edits `object_type`, etc.). ([W3C RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/)) ([W3C OWL 2 Structural Specification](https://www.w3.org/TR/owl2-syntax/))

4) **Consistency and visibility are underspecified.** Palantir explicitly distinguishes eventual vs immediate visibility across object storage versions for action-applied edits, which implies the trace/log system needs to represent “when did this become observable where?” Our receipts do not encode visibility/consistency windows, retries, or reconciliation state. ([Palantir API: Apply Action Batch](https://www.palantir.com/docs/foundry/api/ontology-resources/actions/apply-action-batch))

5) **Security is not first-class in the mapping ledger.** Palantir repeatedly frames Ontology operations as permissioned and audited; AIP Logic tool execution is performed under user permissions. Our mapping receipts appear global and do not encode principal/authorization context; that’s a major mismatch if “ontology action id” is meant to be an operationally meaningful identifier. ([Palantir AIP Logic blocks](https://www.palantir.com/docs/foundry/logic/blocks))

## Adversarial questions
1) If `ontology_action_id` is supposed to approximate a Palantir “action type invocation,” where do we record the action’s *parameters*, *actor/principal*, and *permission context* (and how does it affect who can resolve mappings)? ([Palantir AIP Logic blocks](https://www.palantir.com/docs/foundry/logic/blocks))

2) What is the intended consistency contract of “mapping resolution”? If object edits are eventually consistent (Palantir’s Object Storage V1 note), should mapping resolution ever return “pending/unobservable,” and what’s the reconciliation strategy? ([Palantir API: Apply Action Batch](https://www.palantir.com/docs/foundry/api/ontology-resources/actions/apply-action-batch))

3) Why is the mapping kind set closed and hard-coded (workflow/proposal/event/message/ontology_action/engine_artifact)? What happens when new ID domains appear (e.g., agent tool call IDs, audit log IDs), and how do we avoid schema migrations for routine evolution?

4) Are we building “ontology” or “correlation”? Where is the step that turns these mappings into explicit typed relations (RDF-like graph edges) so they can be queried/validated/derived rather than manually looked up? ([W3C RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/))

5) How do we prevent “foreign ID collision” or poisoning? If external IDs are user-provided or come from untrusted adapters, what guarantees prevent an attacker/bug from mapping a high-value external_id to the wrong run_id?

## Recommended next move
Treat this artifact as a useful *plumbing primitive* (durable correlation) but not as “Palantir ontology grounding” yet: require follow-on work that (a) models action invocations with provenance + security context, (b) introduces an explicit typed relation layer (graph edges) rather than only key→run mapping, and (c) defines consistency/visibility semantics for when mappings are considered authoritative.
