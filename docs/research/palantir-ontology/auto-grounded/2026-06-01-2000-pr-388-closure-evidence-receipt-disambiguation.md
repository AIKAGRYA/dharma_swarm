# Grounding report — PR #388: “PR-H1: disambiguate ClosureEvidenceReceipt from spine EvidenceReceipt”

**Artifact:** PR #388 — “PR-H1: disambiguate ClosureEvidenceReceipt from spine EvidenceReceipt” ([GitHub PR](https://github.com/AmitabhainArunachala/dharma_swarm/pull/388))

## What it claims

This PR claims that two classes named `EvidenceReceipt` in the codebase actually represent different concepts: a runtime dispatch receipt (`dharma_swarm.spine.receipt.EvidenceReceipt`) and a closure-loop receipt used in operator closure logic (`dharma_swarm/operator_core/closure_v0.py`).

It proposes resolving the ambiguity by renaming the closure-loop class to `ClosureEvidenceReceipt`, while retaining a temporary backward-compatible alias `EvidenceReceipt = ClosureEvidenceReceipt` for one release cycle. It also updates manifest-check tooling and tests accordingly.

## External grounding

### 1) Palantir Foundry: identity is multi-layered (RID vs API name vs primary key) and name collisions are treated as governance risks

Palantir’s Foundry Ontology makes a hard distinction between *human-/developer-facing names* (API names) and *system resource identifiers* (RIDs): the ontology itself has a RID, each object type has an API name, and each object type also has a RID intended for cross-API interoperability ([Palantir Get Object Type API](https://palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/)).

Foundry also explicitly marks an additional object type identifier as “legacy” and “not recommended for use in new applications,” which is a direct warning that systems must plan identifier evolution and migration rather than entrenching a single ambiguous ID forever ([Palantir Get Object Type API](https://palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/)).

In Foundry, object identity for *instances* is anchored in a declared **primary key**, and Palantir warns that if the primary key is non-deterministic, “edits can be lost” and “links may disappear,” because ontology edits are associated with the primary key ([Palantir Create an object type](https://palantir.com/docs/foundry/object-link-types/create-object-type/)).

**Why this matters for PR #388:** the rename fixes a *symbol collision*, but it does not yet introduce a Palantir-style *identity discipline* where stable identifiers are separate from display names and where compatibility shims have explicit deprecation and migration mechanics.

### 2) W3C RDF: global identifiers must not collide; collisions are interoperability failures

RDF 1.1 explains that IRIs have “global scope,” so repeated use of the same IRI denotes the same resource; using the same identifier for different intended referents is an “IRI collision,” and causes loss of interoperability ([W3C RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/)).

RDF also notes that once an identifier is minted, its intended referent should not change, tying naming/identity decisions to long-lived compatibility promises rather than convenience refactors ([W3C RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/)).

**Why this matters for PR #388:** the core issue is a collision: the same class-name token (“EvidenceReceipt”) was being used for two different intended referents. RDF’s framing is that collisions are not “style issues” but interoperability failures, meaning the repo needs an explicit “identifier ownership” and “minting” policy for ontology-adjacent terms.

### 3) Peer enterprise governance tools formalize “unique identifier vs name” separation

Collibra’s Import API documentation emphasizes that resources must be uniquely identified, typically by UUID, and if identified by name, the identifier must include additional scope (e.g., domain/community) so the “name” alone does not serve as a global identifier ([Collibra Import API tutorial](https://developer.collibra.com/tutorials/getting-started-with-the-import-api)).

dbt’s semantic layer documentation similarly treats identifiers as a structured modeling surface (primary/unique/foreign/natural keys) and requires uniqueness constraints within defined boundaries (semantic models), highlighting that identity and naming are not one-dimensional ([dbt semantic models](https://docs.getdbt.com/docs/build/semantic-models)).

**Why this matters for PR #388:** simply renaming a class is the “obvious” fix, but enterprise semantic systems require more: scoped naming, explicit identity domains, and formalized uniqueness rules.

## Gaps surfaced (concrete)

1) **No explicit “identity domain” for receipts.** Palantir differentiates Ontology RID (system) vs object type API name (developer) vs object primary key (instance identity) ([Palantir Get Object Type API](https://palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/)), but the repo still treats receipts as mostly ad-hoc Python dataclasses with weakly defined identity semantics.

2) **No deprecation/migration enforcement.** Foundry warns against using legacy IDs and implies migration discipline ([Palantir Get Object Type API](https://palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/)); this PR adds an alias but does not add instrumentation (warnings, deadlines, or CI checks) that ensure external consumers migrate off the deprecated name.

3) **Alias risks perpetuating the collision.** Keeping `EvidenceReceipt` as an alias undermines the stated goal of disambiguation, because downstream code can continue to import the ambiguous name, and tooling/static analysis cannot reliably detect semantic intent.

4) **Receipt-ID stability is not anchored in a typed identity scheme.** Foundry’s warning about non-deterministic primary keys causing edits/links to disappear is effectively a warning about unstable identity surfaces ([Palantir Create an object type](https://palantir.com/docs/foundry/object-link-types/create-object-type/)); the closure receipt `receipt_id` is a hash-derived string, but the PR does not document the permanence requirements (what changes are allowed without invalidating history?), nor does it define collision resistance expectations.

5) **No scoped naming convention for ontology-adjacent terms.** RDF treats identifier collisions as interoperability failures ([W3C RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/)), and Collibra requires scoping when using names as identifiers ([Collibra Import API tutorial](https://developer.collibra.com/tutorials/getting-started-with-the-import-api)); the repo lacks a formal naming/namespace scheme for “spine” vs “operator_core” artifacts.

## Adversarial questions

1) If “EvidenceReceipt” is intended to be *canonical* in the spine, why allow any alias named `EvidenceReceipt` elsewhere at all, even temporarily, given the goal is to prevent future collisions?

2) What is the formal identity contract for `ClosureEvidenceReceipt.receipt_id` (persistence, collision resistance, and referent stability), and what downstream state is keyed by it?

3) Is `correlation_id` actually the stable join key across receipts, VSM projections, Kaizen reviews, and proposals, or is it just a string passed around? What prevents collision across runs?

4) Does the manifest-checker enforce *semantic* uniqueness (e.g., “receipt concept must be single-owned”) or only *syntactic* uniqueness (class-name appears in file X)? How does it prevent a near-duplicate with a different name?

5) How will external consumers be notified and forced to migrate off the alias, and what is the expiry mechanism (date, version, or CI failure)?

## Recommended next move

Treat this PR as a necessary refactor but not an ontology-grade fix. Require a follow-on governance artifact: (a) a short “identifier policy” (namespaces / ownership / collision rules) modeled after Foundry’s RID vs apiName separation, and (b) an enforcement mechanism for alias removal (warning + deadline + CI). Without that, the system is still operating at “5th grade naming hygiene,” not Palantir/enterprise semantic maturity.
