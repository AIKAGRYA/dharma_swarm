# Artifact: PR #409 — feat(ontology): OMS hardening — TypeStatus lifecycle, api_name, uniqueness guard

- Artifact: PR #409
- Title: feat(ontology): OMS hardening — TypeStatus lifecycle, api_name, uniqueness guard
- Link: https://github.com/AmitabhainArunachala/dharma_swarm/pull/409

## What it claims

This PR introduces lifecycle tracking for ontology object types via a `TypeStatus` enum, adds an `api_name` field intended to be a frozen API identifier in the format `dharma.<domain>.<TypeName>`, and adds uniqueness protection so no two object types can share the same `api_name`.

It also backfills the current registry’s domain types to have `status=ACTIVE` and non-empty `api_name` values, and adds tests to enforce the intended naming grammar and global uniqueness.

## External grounding

Palantir’s Foundry Ontology API treats `apiName` as the programmatic identifier for an object type (camelCase), and simultaneously returns a separate `rid` field which is the unique resource identifier used to interact with other Foundry APIs ([Palantir Foundry API: Get Object Type](https://palantir.com/docs/foundry/api/ontologies-v2-resources/object-types/get-object-type/)).

Palantir’s Foundry Ontology supports lifecycle status values on object types including `ACTIVE`, `ENDORSED`, `EXPERIMENTAL`, and `DEPRECATED` ([Palantir Foundry API: Get Object Type](https://palantir.com/docs/foundry/api/ontologies-v2-resources/object-types/get-object-type/)).

Palantir documentation also states that “the object ID of an object type cannot be edited after the initial object type creation process,” and it references object type statuses like `deprecated`, `experimental`, and `active`, plus visibility concepts like `prominent` and `hidden` ([Palantir docs: Edit object types](https://palantir.com/docs/foundry/object-link-types/edit-object-type/)).

Palantir’s object-type creation docs emphasize that API names are programmatic names inferred from display names and can be changed after creation, and list reserved keywords that cannot be used for API names (including `rid`, `primaryKey`, `typeId`) ([Palantir docs: Create an object type](https://palantir.com/docs/foundry/object-link-types/create-object-type/)).

In Palantir Foundry Functions, object identity is represented via multiple identifiers: a `rid` field (`string | undefined`), and also `typeId` + `primaryKey` which are always present even when `rid` is undefined for newly created objects ([Palantir docs: Object identifiers](https://palantir.com/docs/foundry/functions/object-identifiers/)).

Palantir’s open-source RID specification defines a stable, globally disambiguating identifier format `ri.<service>.<instance>.<type>.<locator>` with regex constraints for each component, explicitly designed to wrap existing unique identifiers with namespacing context ([palantir/resource-identifier](https://github.com/palantir/resource-identifier)).

In RDF/OWL ecosystems (which Foundry is not, but which represent the reference bar for ontology engineering), identifiers are IRIs, and best practice is to treat them as globally-scoped identifiers rather than local serialization artifacts ([W3C RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/); [W3C OWL 2 Primer](https://www.w3.org/TR/owl2-primer/)).

Ontology lifecycle/versioning research emphasizes that evolution must be tracked alongside impact/consistency considerations, particularly in OWL-based systems where changes can impact logical consistency ([Pittet et al., arXiv:1208.1750](https://arxiv.org/abs/1208.1750)).

Separately, peer “semantic layer as code” ecosystems emphasize disciplined naming/structure to avoid collisions (e.g., dbt recommends a `sem_` prefix “for the sake of unique file names” under certain project structures) ([dbt Semantic Layer best practices](https://docs.getdbt.com/best-practices/how-we-build-our-metrics/semantic-layer-7-semantic-structure)).

## Gaps surfaced

1) **`api_name` is overloaded as both human-facing namespace and stable identifier, but Foundry separates programmatic `apiName` from an immutable `rid`**: Foundry’s API returns both `apiName` and `rid`, where `rid` is explicitly “useful for interacting with other Foundry APIs” ([Palantir Foundry API: Get Object Type](https://palantir.com/docs/foundry/api/ontologies-v2-resources/object-types/get-object-type/)). If dharma_swarm wants Palantir-grade stability, it needs a separate immutable `rid` (or `type_rid`) minted at creation time (likely in Palantir RID format) rather than freezing a string that embeds a human name.

2) **Lifecycle status set is not aligned with Foundry and misses key enterprise states**: Foundry uses at least `EXPERIMENTAL`, `ACTIVE`, `DEPRECATED`, and (in API v2) `ENDORSED` ([Palantir Foundry API: Get Object Type](https://palantir.com/docs/foundry/api/ontologies-v2-resources/object-types/get-object-type/)). The PR uses `EXPERIMENTAL`, `ACTIVE`, `PROMOTED`. A PhD-grade grounding would define semantics for “promoted” vs “endorsed,” and include `DEPRECATED` with explicit migration windows and compatibility behaviors.

3) **No explicit immutability rule enforcement for promoted identifiers**: The PR docstring claims immutability “once set on a PROMOTED type,” but the code does not enforce immutability on promotion, nor does it define a transition mechanism or operator control consistent with “object ID cannot be edited” constraints in Foundry ([Palantir docs: Edit object types](https://palantir.com/docs/foundry/object-link-types/edit-object-type/)).

4) **No constraints mirror Palantir’s API-name validation rules**: Palantir docs enumerate reserved keywords and imply additional “functional coding standards” rules for API names ([Palantir docs: Create an object type](https://palantir.com/docs/foundry/object-link-types/create-object-type/)). The PR enforces only `dharma.<domain>.<TypeName>` (and only weak PascalCase checks), but does not validate domain character sets, max length, or reserved words, and conflates an “API name” with a namespaced, dotted identifier.

5) **Ignores object-instance identity design (rid vs primaryKey vs typeId)**: Foundry explicitly highlights that `rid` may be undefined on newly created objects, and that equality should be based on `typeId` + `primaryKey` in those cases ([Palantir docs: Object identifiers](https://palantir.com/docs/foundry/functions/object-identifiers/)). The PR changes type-level metadata but does not connect it to instance identity: there is no `typeId` equivalent, no consistent instance RID strategy, and no handling for “undefined rid” situations.

## Adversarial questions

1) If `api_name` is “frozen” and “subject to SEMVER,” what is the actual compatibility contract when it changes: do you support aliases, redirects, or dual-read/dual-write during migration, and how is that represented in the registry?

2) What is the authoritative stable identifier for an object type that survives renames: `name`, `api_name`, or something like a minted RID? Foundry uses `rid` as the unique resource identifier for API interactions ([Palantir Foundry API: Get Object Type](https://palantir.com/docs/foundry/api/ontologies-v2-resources/object-types/get-object-type/)).

3) Why is `TypeStatus.PROMOTED` the right lifecycle concept instead of aligning with Foundry’s `ENDORSED` and `DEPRECATED` statuses, and what operational behavior changes when a type moves between these states ([Palantir Foundry API: Get Object Type](https://palantir.com/docs/foundry/api/ontologies-v2-resources/object-types/get-object-type/))?

4) If `api_name` embeds the `TypeName` verbatim, how do you handle the extremely common enterprise event of renaming a type for clarity without breaking API consumers? In RDF/OWL practice, stable IRIs typically do not encode volatile display labels ([W3C RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/)).

5) Where is the provenance / audit trail for ontology evolution events (who promoted a type, why, what diff), and how is consistency checked as the ontology evolves (a core theme in ontology evolution/versioning research) ([Pittet et al., arXiv:1208.1750](https://arxiv.org/abs/1208.1750))?

## Recommended next move

Rework before treating this as “Palantir-grounded.” Keep the intent (lifecycle + uniqueness), but split identifiers into (a) immutable type RID (Palantir RID format) and (b) editable programmatic apiName / display naming, then explicitly define lifecycle semantics aligned to Foundry (`EXPERIMENTAL` → `ACTIVE` → `ENDORSED` with `DEPRECATED` as a first-class migration state) and enforce immutability rules and migration pathways in code, not just in docstrings.
