# Palantir Ontology — Mission-Relative Grounding (Adversarial)

**Artifact:** PR #408 — “feat(governance): schema-alignment gate (KARMA) + typed-proposal envelope [Stage-1 additive, post-OMS]” ([GitHub PR](https://github.com/AmitabhainArunachala/dharma_swarm/pull/408))

## What it claims (evidence-only)

This PR introduces (a) a CI governance checker (`check_ontology_alignment.py`) intended to detect conflicts among concurrent ontology-modifying pull requests, and (b) a typed Pydantic “proposal envelope” contract (`typed_proposal_envelope.py`) for agents to publish structured ontology change proposals (with provenance) instead of free-text suggestions. The gate asserts it runs in CI on ontology-touching PRs, compares the current branch’s `ontology.py` snapshot against other open ontology PRs and/or `origin/main`, and fails the build on a set of explicit “ALIGN-00x” conflict rules.

It further claims post-OMS `api_name` discipline: `api_name = dharma.<domain>.<TypeName>` with PascalCase `TypeName` and no `.vN` suffix; versioning is expected to live in `ObjectType.version`. It asserts “fail closed” behavior when it cannot read `origin/main` or cannot query open PRs, and provides tests intended to verify the checker’s extraction/diffing and the envelope’s validation constraints.

## External grounding (primary sources)

### What Palantir actually does for ontology branching/proposals and merge checks

Palantir’s Foundry Ontology supports a first-class “branch” concept: a branch is a separate version of an ontology derived from main so changes can be tested in isolation before merging. ([Palantir docs: ontology proposals](https://www.palantir.com/docs/foundry/ontologies/ontologies-proposals/))

Palantir defines an ontology “proposal” as analogous to a Git pull request: proposals are automatically created alongside a branch and include metadata such as reviews, a name, and descriptions of changes being merged. ([Palantir docs: ontology proposals](https://www.palantir.com/docs/foundry/ontologies/ontologies-proposals/))

In Palantir’s workflow, each modified ontology entity becomes a separate “task” in the proposal and tasks are individually reviewed/approved/rejected. ([Palantir docs: ontology proposals](https://www.palantir.com/docs/foundry/ontologies/ontologies-proposals/))

Foundry’s Global Branching integration explicitly includes “merge checks” that run when a proposal is created, verifying whether resources on a branch can merge into `main`, and failed checks can include conflicts requiring rebasing. ([Palantir docs: branching the ontology](https://www.palantir.com/docs/foundry/ontologies/branching-ontology))

Foundry’s conflict resolution is interactive and resource-scoped: during rebasing, users can choose “Use Main branch changes” vs “Keep current branch changes” or make “custom changes” on the resource to resolve conflicts. ([Palantir docs: branching the ontology](https://www.palantir.com/docs/foundry/ontologies/branching-ontology))

### What Palantir’s public API implies about identifiers and lifecycle

Foundry’s API retrieves object types by “API name” (the endpoint path includes `objectTypes/{apiName}`), and the schema includes a `rid` as a unique resource identifier. ([Palantir API docs: Get Object Type](https://www.palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/))

The same API schema enumerates object type release statuses including `ACTIVE`, `EXPERIMENTAL`, and `DEPRECATED`, indicating lifecycle as a first-class concern. ([Palantir API docs: Get Object Type](https://www.palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/))

### What standards-based semantic systems use for “gates” (constraints) vs ad-hoc diffing

SHACL is a W3C standard for validating RDF graphs against conditions expressed as “shapes” (a shapes graph) applied to a data graph, producing a validation report. ([W3C SHACL Recommendation](https://www.w3.org/TR/shacl/))

SHACL also explicitly supports severity levels (e.g., `sh:Info`, `sh:Warning`, `sh:Violation`) with `sh:Violation` as the default severity if unspecified, which provides a standards-based pattern for “warn vs fail” behavior. ([W3C SHACL Recommendation](https://www.w3.org/TR/shacl/))

OWL 2’s structural specification formalizes “structural equivalence” and requires eliminating structurally equivalent duplicate axioms (i.e., you cannot have two axioms that are structurally equivalent in the same ontology’s axiom set). ([W3C OWL 2 Structural Specification](https://www.w3.org/TR/owl2-syntax/))

OWL 2 DL’s typing constraints prohibit reusing the same identifier (IRI) as more than one property type (object vs data vs annotation property), an example of “hard constraints” that protect downstream reasoning/consumers. ([W3C OWL 2 Structural Specification](https://www.w3.org/TR/owl2-syntax/))

### Peer “semantic layer as code” governance references (what mature systems emphasize)

Cube describes a semantic layer architecture with four pillars: data modeling, access control, caching, and APIs, and stresses code-first modeling managed in version control with automated testing and documentation. ([Cube docs: Introduction](https://cube.dev/docs/product/introduction))

dbt’s semantic-layer governance framing explicitly stresses version control, audit trail (“who changed what, when, and why”), and rollback for governed definitions treated as software code. ([dbt Labs blog](https://www.getdbt.com/blog/semantic-layer-data-governance-security))

## Gaps surfaced (adult / adversarial)

1. **Palantir’s merge checks are resource- and UI-mediated with explicit conflict resolution paths; this PR’s gate is a best-effort text/AST diff without a resolution workflow.** In Foundry, rebasing and conflict resolution are an explicit product surface with per-resource choices and “custom changes” to resolve conflicts. ([Palantir docs: branching the ontology](https://www.palantir.com/docs/foundry/ontologies/branching-ontology)) The current PR can detect some conflicts but provides no deterministic resolution protocol and no notion of “choose main vs choose branch” or “custom reconciliation,” so it risks becoming a noisy pre-merge blocker rather than a governance system.

2. **Lifecycle mismatch: Palantir exposes `DEPRECATED` and `ENDORSED`-like notions; PR #408 hard-codes a narrower lifecycle and maps “promoted” as a concept without external grounding.** Palantir’s API surface shows `ACTIVE`, `EXPERIMENTAL`, `DEPRECATED` as first-class statuses. ([Palantir API docs: Get Object Type](https://www.palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/)) If dharma_swarm intends to be “Palantir-like,” a PhD-grade design would explicitly justify lifecycle state choices, how deprecation is represented (and enforced), and how “endorsement/prominence/visibility” maps to access patterns.

3. **The `api_name` discipline is asserted but not aligned to Palantir’s notion of API name (camelCase, stable identifier in API paths) or RID.** Palantir’s API treats `apiName` as the path identifier and also provides `rid` as a unique resource identifier for interactions with other APIs. ([Palantir API docs: Get Object Type](https://www.palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/)) PR #408’s `dharma.<domain>.<TypeName>` scheme is a repo convention but does not address the two-identifier pattern (human-stable API name vs system RID) or migration/aliasing when names change.

4. **Constraint language gap: the gate is bespoke logic, but mature semantic systems typically express invariants in a dedicated constraint language (e.g., SHACL) with standard reporting and severity semantics.** SHACL is explicitly designed for validation with a shapes graph producing a validation report and includes severity levels to distinguish warnings from violations. ([W3C SHACL Recommendation](https://www.w3.org/TR/shacl/)) A PhD-grade governance gate would either (a) adopt a constraint representation (even if not RDF) or (b) explicitly justify why bespoke diff rules are superior for this ontology’s semantics.

5. **Governance scope gap: enterprise semantic layers emphasize access control and runtime enforcement, not just naming and schema diffs.** Cube frames access control as a core pillar enforced deterministically at the semantic layer runtime. ([Cube docs: Introduction](https://cube.dev/docs/product/introduction)) dbt frames semantic layer as a governance checkpoint with audit trail and rollback. ([dbt Labs blog](https://www.getdbt.com/blog/semantic-layer-data-governance-security)) PR #408 has no equivalent for (a) runtime policy enforcement, (b) a stable audit log across proposals, or (c) rollback semantics when “approved” ontology changes break downstream agents.

## Adversarial questions (what this PR assumes but does not answer)

1. **What is the authoritative identity of an object type: `name`, `api_name`, or something like Palantir’s `rid`?** Palantir’s API strongly suggests a split between stable identifier(s) and a unique resource identifier (`rid`). ([Palantir API docs: Get Object Type](https://www.palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/)) PR #408 enforces `api_name` uniqueness but does not define a durable identity model for renames, merges, or splits.

2. **What is the intended conflict-resolution policy when ALIGN-001/004/005 fire?** Palantir has explicit “Use main vs keep branch vs custom change” pathways. ([Palantir docs: branching the ontology](https://www.palantir.com/docs/foundry/ontologies/branching-ontology)) Here, the gate blocks but does not define a governance procedure for systematically reconciling conflicts.

3. **How does this system avoid governance-by-regex (API_NAME_PATTERN) becoming a long-term compatibility trap?** Palantir’s `apiName` is camelCase and is used directly as an API identifier; if you change it, you break clients. ([Palantir API docs: Get Object Type](https://www.palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/)) The PR’s `dharma.<domain>.<TypeName>` is a *new* contract, but there is no migration story for previously created types, aliases, or client bindings.

4. **Where is the audit trail and rollback story at the ontology contract level (not just git history)?** dbt’s semantic layer governance framing makes version control, audit trail, and rollback explicit product requirements for governed definitions. ([dbt Labs blog](https://www.getdbt.com/blog/semantic-layer-data-governance-security)) This PR is a CI gate, but it doesn’t specify how agents/ops discover “what changed,” “why,” and “how to roll back” in operational terms.

5. **Why are OWL/SHACL-style structural constraints referenced but not actually implemented as constraints?** OWL 2’s “no duplicate structurally equivalent axioms” and typing constraints are examples of rigorous invariants. ([W3C OWL 2 Structural Specification](https://www.w3.org/TR/owl2-syntax/)) SHACL provides a validation/report pattern. ([W3C SHACL Recommendation](https://www.w3.org/TR/shacl/)) PR #408 borrows the rhetoric but implements bespoke checks; what is the formal semantics of these checks and how do we know they are complete?

## Recommended next move

Treat PR #408 as a useful **stage-0 guardrail** but not a “Palantir-like” ontology governance system yet: require it to be paired with a written authority/identity model (including rename/alias/ID strategy analogous to Palantir’s `apiName` + `rid` split), and a deterministic conflict-resolution and rollback procedure (borrowing from Foundry’s explicit rebase/conflict UX and from semantic-layer governance patterns). Until those are articulated, expect ALIGN-00x to either under-detect deep semantic conflicts (false negatives) or over-block (false positives) without an operational path to resolution.
