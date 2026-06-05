# Artifact
- **PR**: #406
- **Title**: feat(ontology): hard-wire telos gate into execute_action (W1 — runtime governance)
- **Link**: https://github.com/AmitabhainArunachala/dharma_swarm/pull/406

## What it claims
This PR claims to move governance from “merge-time” controls (branch protection / CI gates) to *runtime* enforcement by making `OntologyRegistry.execute_action` a hard chokepoint for declared `telos_gates`. It asserts that when an action declares telos gates, the call path will always invoke a shared default gatekeeper, so callers cannot bypass gating by omitting a gate callback or by providing an explicit gate callback that always returns PASS.

It also claims to scope “harmful/destructive intent” detection to ontology action parameters, including a local pre-classifier that promotes certain high-confidence destructive payloads (e.g., destructive SQL/admin/exfiltration phrases) into existing harm categories in the shared gatekeeper vocabulary, while reducing false positives by using token/phrase boundary matching rather than raw substring matching.

Finally, it claims to enforce a fail-closed posture when gates are declared but gate infrastructure is unavailable or returns malformed results, and to ensure `telos_required` object types are not “stranded” by requiring that telos-required actions actually produce gate verdicts.

## External grounding
### 1) Palantir Foundry Ontology: what “ontology” is in Foundry (schema + instances + backing data)
Palantir describes an **object type** as the schema definition of a real-world entity or event, and an **object** as a single instance of that type ([Palantir Foundry docs — Object types overview](https://palantir.com/docs/foundry/object-link-types/object-types-overview/)).

Foundry emphasizes that the Ontology is not only an abstract model: it “maps each ontological concept to an organization's actual data,” and objects are created by adding **backing datasources** to an object type in Ontology Manager ([Palantir Foundry docs — Object types overview](https://palantir.com/docs/foundry/object-link-types/object-types-overview/)).

**Grounding implication:** Palantir’s ontology is tightly coupled to governed data assets and operational apps; the “runtime” enforcement surface in Foundry is not just “block an action based on keywords” but enforcement against governed assets, roles, and purposes.

### 2) Palantir Foundry governance: runtime “checkpoints” and policy enforcement patterns
Foundry describes **Checkpoints** as a mechanism that enables governance teams to request a justification/acknowledgment **prior to being able to perform actions considered sensitive**, i.e., gating actions with required human input in the workflow ([Palantir Foundry docs — Data protection and governance](https://palantir.com/docs/foundry/security/data-protection-and-governance/)).

Foundry also describes **Sensitive Data Scanner** operating in the background to detect sensitive data and trigger configured responses such as creating issues or applying **Security Marking** to lock down datasets ([Palantir Foundry docs — Data protection and governance](https://palantir.com/docs/foundry/security/data-protection-and-governance/)).

**Grounding implication:** A Palantir-grade “runtime governance” system typically includes (a) explicit workflow checkpoints/approvals and (b) continuous monitoring with automated controls that affect data access states, not only a synchronous allow/block verdict.

### 3) Semantic-layer peers: governance is definitions + access controls + propagation, not only filters
dbt’s Semantic Layer positions governance as centralized definitions that propagate everywhere (metric changes refresh everywhere they’re used) and mentions robust access permissions as part of the layer ([dbt Semantic Layer docs](https://docs.getdbt.com/docs/use-dbt-semantic-layer/dbt-sl)).

Cube’s semantic layer documentation frames two consumption patterns—entity-first and metrics-first—emphasizing making consumption clear/BI-compatible by shaping views (denormalized exposures) and clarifying time dimension semantics ([Cube docs — Designing metrics](https://cube.dev/docs/product/data-modeling/recipes/designing-metrics)).

**Grounding implication:** Enterprise governance layers tend to embed policy and consistency into the *definitions and exposures* (models, metrics, views) and their propagation, rather than relying on per-call keyword interpretation.

### 4) Formal ontology semantics: RDF/OWL define meaning and interoperability constraints
RDF defines an RDF graph as a set of RDF triples, where a triple has subject (IRI/blank node), predicate (IRI), and object (IRI/literal/blank node), and IRIs have global scope with equality by simple string comparison ([W3C RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/)).

OWL 2 adds description-logic semantics for classes/properties/individuals with reasoning tasks (consistency, subsumption, instance retrieval) and defines profiles (EL/QL/RL) that trade expressivity for scalable reasoning, including OWL 2 QL for SQL-friendly query answering and OWL 2 RL for rule-based reasoning over triples ([W3C OWL 2 Overview](https://www.w3.org/TR/owl2-overview/)).

**Grounding implication:** If the project intends “Palantir semantic ontology” in a strong sense, you eventually need a stance on formal semantics (even if only lightweight): identity/IRI strategy, constraints, and whether any reasoning/validation beyond unit tests will exist.

## Gaps surfaced (concrete, evidence-based)
1) **No evidence of “checkpoint-style” governance or justifications that are first-class artifacts.** Foundry’s Checkpoints are explicitly about requiring justification/acknowledgment before sensitive actions are allowed ([Palantir Foundry docs — Data protection and governance](https://palantir.com/docs/foundry/security/data-protection-and-governance/)). This PR’s gate interface returns `{gate: PASS|BLOCK}` only, which cannot represent “needs justification,” “pending approval,” or “acknowledged with reason,” nor does it create/attach a durable justification object.

2) **Runtime governance is framed as content scanning rather than policy tied to identity, purpose, and governed assets.** Foundry guidance repeatedly ties access to “explicit approved purposes” and uses governance teams/SMEs as accountable authorities ([Palantir Foundry docs — Data protection and governance](https://palantir.com/docs/foundry/security/data-protection-and-governance/)). This PR’s gating signature passes only `(action_name, params)` and appears not to include actor identity, roles, purpose context, data classifications, or policy references—so it cannot implement Foundry-like purpose limitation or role-based sensitive-action gating.

3) **No continuous monitoring/automatic control loop analogous to Sensitive Data Scanner + Security Markings.** Foundry describes background monitoring that detects sensitive data and triggers configured responses like issues or security markings that lock down datasets ([Palantir Foundry docs — Data protection and governance](https://palantir.com/docs/foundry/security/data-protection-and-governance/)). This PR is synchronous call-time gating only; there is no evidence of an asynchronous control plane that can change access state after the fact.

4) **No formal semantics/identity strategy for ontology resources, which blocks interoperability and robust constraints.** RDF’s model depends on globally-scoped IRIs and clear identity choices, and OWL profiles exist specifically to make scalable constraints/reasoning feasible ([W3C RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/); [W3C OWL 2 Overview](https://www.w3.org/TR/owl2-overview/)). This PR is governance plumbing inside a Python registry, but it does not address foundational ontology needs like stable identifiers/IRIs, constraint languages, or any reasoning profile choice.

5) **Peer semantic layers emphasize governed *definitions* and propagation; this change is runtime-only.** dbt Semantic Layer emphasizes central definitions that propagate consistently across all consuming tools and robust permissions ([dbt Semantic Layer docs](https://docs.getdbt.com/docs/use-dbt-semantic-layer/dbt-sl)). Cube emphasizes shaping exposures for consumer clarity, including time semantics ([Cube docs — Designing metrics](https://cube.dev/docs/product/data-modeling/recipes/designing-metrics)). This PR does not address the governance of definitions (e.g., versioned action definitions, policy evaluation semantics, or how policies propagate across APIs).

## Adversarial questions
1) What is the *governance contract* beyond PASS/BLOCK—do we need states like REVIEW, REQUIRE_JUSTIFICATION, REQUIRE_APPROVAL (checkpoint), or quarantine? Foundry explicitly supports justification/ack before sensitive actions ([Palantir Foundry docs — Data protection and governance](https://palantir.com/docs/foundry/security/data-protection-and-governance/)).

2) Where is actor identity/purpose encoded and enforced? If governance is about “approved purposes,” how does `execute_action` receive the purpose, policy binding, and role context needed to enforce it ([Palantir Foundry docs — Data protection and governance](https://palantir.com/docs/foundry/security/data-protection-and-governance/))?

3) What is the canonical mapping from “declared gates” to “enforced gates,” and how is it governed/versioned? In Foundry terms, what is the equivalent of centrally managed controls (e.g., security markings/checkpoints) that are not editable by callers ([Palantir Foundry docs — Data protection and governance](https://palantir.com/docs/foundry/security/data-protection-and-governance/))?

4) What is the formal semantics of the ontology—are IDs/refs intended to become globally meaningful IRIs, and if so what is the IRI strategy and constraint story ([W3C RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/))? If not, how do you prevent the “ontology” from becoming an in-process metadata dictionary rather than an ontology?

5) How will this scale from unit-tested keyword blocks to enterprise-grade controls? Peer layers focus on centralized definitions, propagation, and permissions mechanisms ([dbt Semantic Layer docs](https://docs.getdbt.com/docs/use-dbt-semantic-layer/dbt-sl)). What is the plan to evolve from heuristics to policy-as-code tied to types, roles, classifications, and audit?

## Recommended next move
This artifact is directionally correct (enforcing runtime gating at a universal chokepoint), but it is not yet Palantir-grade governance: it lacks checkpoint/justification semantics, actor/purpose-aware policy evaluation, and any continuous control plane comparable to Foundry’s scanner/markings/checkpoints ([Palantir Foundry docs — Data protection and governance](https://palantir.com/docs/foundry/security/data-protection-and-governance/)). Treat it as a necessary hardening step, but require follow-up design work that (1) makes “justification/approval” a first-class typed artifact and (2) threads identity/purpose/policy context into action execution so governance is not reducible to parameter keyword inspection.
