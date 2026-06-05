# Grounding report — PR #409: “feat(ontology): OMS hardening — TypeStatus lifecycle, api_name, uniqueness guard”

Artifact: PR #409 — feat(ontology): OMS hardening — TypeStatus lifecycle, api_name, uniqueness guard ([GitHub PR](https://github.com/AmitabhainArunachala/dharma_swarm/pull/409))

## What it claims

This PR introduces lifecycle metadata for ontology object types (`TypeStatus`: experimental/active/promoted), adds a frozen `api_name` field intended to act as a stable identifier, and adds a uniqueness guard in type registration to prevent duplicate names. It frames these as prerequisites for downstream work (align-gate, OSDK code generation, and audit finding consolidation) and asserts the changes are additive and backwards-compatible.

It also asserts a naming “grammar” of `dharma.<domain>.<TypeName>` (PascalCase TypeName), claims this should be “Palantir-grounded,” and ties `PROMOTED` to SEMVER deprecation rules.

## External grounding (primary sources)

### 1) Palantir Foundry: object types are identified by an API name (and also a stable RID)

Palantir’s Ontology API fetches an object type “with the given API name,” and describes `apiName` as “the name of the object type in the API in camelCase format,” while also returning a stable `rid` as “the unique resource identifier of an object type, useful for interacting with other Foundry APIs” ([Palantir Foundry API — Get Object Type](https://palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/)).

Palantir additionally labels `id` as “a legacy identifier” and explicitly says it is “not recommended for use in new applications” ([Palantir Foundry API — Get Object Type](https://palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/)).

**Implication for this PR:** a “frozen identifier” concept is directionally aligned with Foundry’s use of identifiers, but Foundry distinguishes at least two notions: a human-ish API name (camelCase) and a globally unique resource identifier (RID). This PR adds a single `api_name` string but does not introduce the equivalent of a RID/UUID-backed stable identifier.

### 2) Palantir Foundry: Ontology Manager supports branches and is the governance locus

Ontology Manager (OMA) is described as the app to “build and maintain your organization’s Ontology,” including creating object types and action types, connecting data, and investigating updates in user apps ([Palantir — Ontology Manager overview](https://palantir.com/docs/foundry/ontology-manager/overview/)).

Critically, OMA explicitly supports the ability to “navigate between or create new branches” ([Palantir — Ontology Manager overview](https://palantir.com/docs/foundry/ontology-manager/overview/)).

**Implication for this PR:** “promotion” and “frozen api_name” only become meaningful if paired with a notion of branching, change review, and controlled deployment of ontology revisions; this PR introduces lifecycle labels but not the branch-based workflow that makes them operational.

### 3) Palantir Foundry: link types vs link instances + how they are backed by data

Palantir defines a **link type** as the schema definition of a relationship, and a **link** as “a single instance of that relationship” ([Palantir — Link types overview](https://palantir.com/docs/foundry/object-link-types/link-types-overview/)).

Palantir further states links in user applications are created/displayed by “adding backing datasources” for the object types, and for many-to-many links “datasources back the link types themselves” ([Palantir — Link types overview](https://palantir.com/docs/foundry/object-link-types/link-types-overview/)).

**Implication for this PR:** if `api_name` is intended to be stable across codegen and integration surfaces, you eventually need a mapping from type identifiers to backing data products / data lineage and to branch-reconciled schema changes; this PR only touches registry metadata, not the data-binding layer.

### 4) Palantir Foundry: semantic versioning and stability expectations

Palantir’s API documentation states it uses semantic versioning with major versions only and is “committed to maintaining backwards compatibility within major versions,” while noting non-breaking updates can be deployed transparently ([Palantir — API versioning overview](https://palantir.com/docs/foundry/api/general/overview/versioning/)).

It also states stable endpoint removals/replacements (outside emergency scenarios) are announced at least twelve months in advance ([Palantir — API versioning overview](https://palantir.com/docs/foundry/api/general/overview/versioning/)).

**Implication for this PR:** invoking “SEMVER deprecation rules” suggests you need explicit policy and enforcement: what counts as a breaking schema change for an object type? how are deprecated types handled? what’s the migration surface? None is specified or enforced here.

### 5) W3C RDF: identifiers have global scope; collisions are an interoperability break

The RDF 1.1 Concepts spec emphasizes: “By design, IRIs have global scope… Violating this principle constitutes an IRI collision,” and notes the IRI owner establishes intended referents via specification documents and/or dereferenceable IRIs ([W3C — RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/)).

**Implication for this PR:** your `api_name` is functioning like a namespace-qualified identifier. If you are serious about “Palantir-grade” semantics, you likely want an actual IRI scheme (or at least a stable URI-like convention) and collision rules that operate across repos/environments/tenants—not just inside one Python process.

## Gaps surfaced (concrete, evidence-backed)

1) **Your `api_name` format is not aligned with Foundry’s described object-type API naming conventions.** Foundry describes the API name of an object type as camelCase ([Palantir Foundry API — Get Object Type](https://palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/)), while this PR mandates `dharma.<domain>.<TypeName>` with PascalCase TypeName. If downstream systems are meant to emulate Foundry integrations, this mismatch will bite at the codegen boundary (SDK naming, endpoint paths, client expectations).

2) **No RID-equivalent stable identifier exists.** Foundry returns an object type `rid` that is “useful for interacting with other Foundry APIs,” while warning that `id` is legacy ([Palantir Foundry API — Get Object Type](https://palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/)). This PR adds `api_name` but does not add a separate immutable, system-generated identifier (RID/UUID) that survives renames, refactors, or merges.

3) **Lifecycle labels are not coupled to a governance workflow.** Ontology Manager explicitly supports branches ([Palantir — Ontology Manager overview](https://palantir.com/docs/foundry/ontology-manager/overview/)), but this PR adds `TypeStatus` without implementing any workflow constraints (e.g., only operator can promote; promotion implies immutability; promotion must occur on mainline branch; review gates). Without enforcement, “status” is descriptive metadata, not governance.

4) **Promotion/SEMVER is asserted but not defined in terms of actual compatibility contracts.** Palantir’s own versioning rules spell out compatibility expectations and notice periods ([Palantir — API versioning overview](https://palantir.com/docs/foundry/api/general/overview/versioning/)), but this PR doesn’t define what it means for an ontology type to be “breaking” vs “non-breaking” (field add? field removal? cardinality change? action signature change?). There is no migration guidance or depreciation lifecycle.

5) **Uniqueness checks are local, not global.** RDF calls out that identifier collision breaks interoperability for globally-scoped identifiers ([W3C — RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/)). This PR’s uniqueness guard prevents duplicate type names in a single registry, but does not address collisions across modules, multiple registries, multi-tenant deployments, or future federation.

## Adversarial questions (sharp, unanswered)

1) If `api_name` is the stable integration identifier, what is the separate, immutable, system-generated identifier (RID/UUID equivalent) used for internal references and refactor safety, consistent with Foundry’s `rid` vs `apiName` split ([Palantir Foundry API — Get Object Type](https://palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/))?

2) How does a type move from EXPERIMENTAL → ACTIVE → PROMOTED, and what enforces this? Foundry’s Ontology Manager is explicitly branch-aware ([Palantir — Ontology Manager overview](https://palantir.com/docs/foundry/ontology-manager/overview/)); what is the analog here (branches, approvals, audit trail, reconcile/merge semantics)?

3) What is the precise compatibility contract for a PROMOTED object type? Palantir’s API versioning docs are explicit about backwards compatibility commitments and breaking changes ([Palantir — API versioning overview](https://palantir.com/docs/foundry/api/general/overview/versioning/)); what are your “breaking changes” at the ontology schema level (properties, links, action signatures, security policy)?

4) Why is `api_name` mandated as `dharma.<domain>.<TypeName>` PascalCase, when Palantir’s object type API name is described as camelCase ([Palantir Foundry API — Get Object Type](https://palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/))? Are you intentionally diverging (and if so, where is the spec)?

5) How will links and their backing data evolve, given Palantir’s requirement that links be backed by datasources and many-to-many links can be backed at the link type level ([Palantir — Link types overview](https://palantir.com/docs/foundry/object-link-types/link-types-overview/))? Does `api_name` participate in data-binding/lineage in any way, or is this purely codegen sugar?

## Recommended next move

This PR is directionally correct (introducing lifecycle metadata and explicit identifiers), but it is not yet “Palantir-grounded” in the ways that matter for a durable ontology system: it conflates API name with stable internal identifier, asserts governance (promotion/SEMVER) without implementing the branch + policy enforcement that makes it real, and chooses a naming format that appears to diverge from Foundry’s documented object type API naming conventions. Recommend rework before downstream codegen/align-gate depends on it: explicitly split *human/API name* vs *immutable system ID*, define compatibility rules for PROMOTED types, and tie promotion to a branch-based workflow and enforcement hooks.
