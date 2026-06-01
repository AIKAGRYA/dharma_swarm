# Grounding report — PR #406: `feat(ontology): hard-wire telos gate into execute_action (W1 — runtime governance)`

**Artifact:** PR #406 — “feat(ontology): hard-wire telos gate into execute_action (W1 — runtime governance)” ([GitHub PR](https://github.com/AmitabhainArunachala/dharma_swarm/pull/406))

## What it claims

PR #406 claims to “hard-wire” governance at runtime by ensuring `OntologyRegistry.execute_action` always runs a default telos gatekeeper for actions that declare `telos_gates`, so gating cannot be bypassed by omitting a gate or by supplying an override that always returns PASS ([GitHub PR](https://github.com/AmitabhainArunachala/dharma_swarm/pull/406)).

It further claims that explicit non-default gate callbacks may still run, but only after the default gate passes and without the ability to override a default BLOCK, and that `telos_required` types remain fail-closed without an explicit post-default gate ([GitHub PR](https://github.com/AmitabhainArunachala/dharma_swarm/pull/406)).

## External grounding (primary sources)

### 1) Palantir Foundry Ontology “actions” are transactional, governed writes

Palantir’s Foundry execution model for ontology edits emphasizes transactional semantics: in a “staged-write” function, all edits across nested calls are staged together and committed at the end of the action execution, with rollback if the function throws an error ([Palantir Functions docs — TypeScript v2 staged writes](https://www.palantir.com/docs/foundry/functions/typescript-v2-staged-writes)).

**Why this matters to PR #406:** if `execute_action` is your “action service,” the runtime governance you embed there is in the same conceptual position Palantir puts its action execution guarantees: it is not “optional middleware,” it is the commit boundary for side effects and auditability ([Palantir Functions docs — TypeScript v2 staged writes](https://www.palantir.com/docs/foundry/functions/typescript-v2-staged-writes)).

### 2) Industry-standard policy architectures separate “decision” from “enforcement”

NIST’s ABAC reference architecture explicitly distinguishes a Policy Decision Point (PDP) that computes access decisions from a Policy Enforcement Point (PEP) that enforces them ([NIST SP 800-162](https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-162.pdf)).

OPA (Open Policy Agent) makes the same separation explicit: “OPA decouples policy decision-making from policy enforcement,” and systems query OPA with structured input for a decision ([OPA documentation](https://openpolicyagent.org/docs)).

**Why this matters to PR #406:** “hard-wire into chokepoint” is a PEP move; but the PR’s default gate is also bundling PDP behavior (decision logic) into the same runtime module. That coupling matters for maintainability, evolvability, and proving properties under adversarial pressure ([NIST SP 800-162](https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-162.pdf); [OPA documentation](https://openpolicyagent.org/docs)).

### 3) Constraint validation in ontology systems typically uses formal “shapes” with explicit conformance reports

W3C SHACL defines a standard approach for validating graphs against declarative constraints (“shapes graphs”), producing a validation report with explicit results, severities, and constraint identifiers ([W3C SHACL Recommendation](https://www.w3.org/TR/shacl/)).

SHACL also requires processors to **signal failure** when asked to operate under an unsupported entailment regime, which is an explicit spec-level “don’t silently continue” behavior ([W3C SHACL Recommendation](https://www.w3.org/TR/shacl/)).

**Why this matters to PR #406:** if “telos gates” are effectively runtime constraints on action execution, the strongest external precedent is not keyword scanning—it is declarative constraint evaluation with structured reports and well-defined failure modes ([W3C SHACL Recommendation](https://www.w3.org/TR/shacl/)).

## Gaps surfaced (PhD-grade expectations vs current PR)

1) **No explicit policy model / PDP surface; enforcement and decision are fused.**  
   The PR hardwires enforcement at the chokepoint, but the “default gate” is not a separable PDP with a stable query API (unlike ABAC PDP/PEP or OPA’s query model). This makes it hard to: (a) evaluate decisions offline, (b) replay decisions for audit, (c) evolve policy independently of runtime call sites ([NIST SP 800-162](https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-162.pdf); [OPA documentation](https://openpolicyagent.org/docs)).

2) **The default gate appears to be a keyword/phrase heuristic, not a formal, typed constraint system.**  
   The PR moves toward runtime governance but does not approach SHACL-like declarative constraint semantics (constraint identifiers, structured results, conformance model) that ontology systems use when “constraints” matter ([W3C SHACL Recommendation](https://www.w3.org/TR/shacl/)).

3) **No explicit transactional/audit linkage between gate decisions and the action commit boundary.**  
   Palantir emphasizes that action execution has a commit/rollback boundary, and edits are applied at action completion with full rollback on errors; the PR logs gate results in an internal action log, but does not yet define a durable audit schema, retention, or replay aligned to the transaction boundary ([Palantir Functions docs — TypeScript v2 staged writes](https://www.palantir.com/docs/foundry/functions/typescript-v2-staged-writes)).

4) **No “policy information point” (PIP) notion; decisions are made without external context.**  
   ABAC explicitly expects the PDP to request attributes from PIPs as needed (identity, object attributes, environment conditions). The PR’s default gate mostly inspects action parameters, which is a narrow slice of the context ABAC architectures assume is needed for high-assurance decisions ([NIST SP 800-162](https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-162.pdf)).

5) **The PR’s fail-closed behavior is underspecified relative to formal systems.**  
   SHACL requires signaling failure for unsupported entailment regimes; OPA treats undefined default decision as error; ABAC architectures emphasize orchestration correctness. The PR has some fail-closed paths (exceptions/malformed verdicts), but does not specify a canonical set of error states and what exactly is recorded for audit and operator debugging ([W3C SHACL Recommendation](https://www.w3.org/TR/shacl/); [OPA documentation](https://openpolicyagent.org/docs); [NIST SP 800-162](https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-162.pdf)).

## Adversarial questions (what this PR assumes but does not answer)

1) **What is the formal policy language for telos gates?** If “telos_gates” are policy, where is the canonical policy definition and evaluation semantics that can be reviewed independent of code deployments (PAP/PDP separation)? ([NIST SP 800-162](https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-162.pdf); [OPA documentation](https://openpolicyagent.org/docs))

2) **How are gate decisions audited and replayed?** Palantir-style operational layers require re-playable, attributable action logs around the commit boundary; what is the durable schema, retention, and replay mechanism for gate decisions? ([Palantir Functions docs — TypeScript v2 staged writes](https://www.palantir.com/docs/foundry/functions/typescript-v2-staged-writes))

3) **Where is the “policy information point” data coming from?** If the gate only inspects params, how does it incorporate subject identity, object sensitivity, environment conditions (time, location, deployment branch), or data classification? ([NIST SP 800-162](https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-162.pdf))

4) **What is the behavior under partial failures and retries?** Palantir staged writes highlight retries and rollback semantics; if an action is retried, does the gate produce stable decisions and stable audit IDs, or can it vary based on nondeterministic external state? ([Palantir Functions docs — TypeScript v2 staged writes](https://www.palantir.com/docs/foundry/functions/typescript-v2-staged-writes))

5) **How do you prevent “policy drift” when default gate changes?** With decision logic embedded in code, how do you ensure historical actions can be re-evaluated against the policy version that was in force at the time, a common compliance requirement? ([OPA documentation](https://openpolicyagent.org/docs))

## Recommended next move

Treat PR #406 as a *necessary but insufficient* enforcement refactor: it moves gating to the right architectural location (the chokepoint), but the current mechanism is not yet enterprise/Palantir-grade because it lacks a separable policy decision surface, formal constraint semantics, and a durable audit/replay story. Next move should be to define a minimal PDP/PEP/PIP split for telos gating (even if PDP is still in-process) and specify an auditable decision schema and versioning strategy before further expanding the gate vocabulary.
