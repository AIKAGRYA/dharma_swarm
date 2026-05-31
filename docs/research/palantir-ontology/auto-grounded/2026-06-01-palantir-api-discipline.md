# Palantir Ontology API Discipline: Adversarial Research Report

**Date:** 2026-06-01  
**Author:** Computer (adversarial research subagent)  
**Scope:** dharma\_swarm PR #408 — ontology API naming + status lifecycle vs. PhD-grade enforcement  
**Posture:** Challenge. Reject marketing language. Say where docs are thin or paywalled.

---

## Context: What dharma\_swarm PR #408 Does (and What is Unproven)

PR #408 implements two files:

1. **`dharma_swarm/ontology.py`**: Defines `ObjectType`, `LinkDef`, `ActionDef`, `OntologyRegistry` as Pydantic `BaseModel` instances. The `ObjectType` class carries optional `api_name: str`, `status: str | None`, and `version: int = 1` fields. There is **no `api_name` validator on `ObjectType` itself** — validation is delegated entirely to the CI gate.

2. **`scripts/governance/check_ontology_alignment.py`**: A CI script that extracts AST snapshots from `ontology.py` across open PRs and checks 7 conflict rules (ALIGN-001 through ALIGN-007). ALIGN-007 enforces the api_name pattern `^dharma\.[a-z][a-z0-9_]*\.[A-Z][A-Za-z0-9]*\.v\d+$` but, critically, this check is a **warning by default** (only becomes an error with `--strict`). The gate does not run at object construction time — it runs only in CI.

**What is unproven or asserted without external grounding:**

- The claim that `dharma.<domain>.<TypeName>.v<N>` is "Palantir-style" naming. Palantir does NOT use this pattern internally (see below).  
- The claim that `status: experimental → active → promoted` maps cleanly to Palantir's real lifecycle. Palantir has five statuses, not three, and the transitions have platform-enforced constraints dharma_swarm does not model.  
- The `register_type` uniqueness guard exists in code but is not backed by a persistent store — in-memory only, reset on process restart.  
- ALIGN-007 is a "warning" by default — meaning api\_name discipline can be merged without enforcement.  
- There is no consumer-side propagation model. When an ObjectType's api\_name changes (or when a version bumps), downstream OSDK-equivalent consumers are not notified, re-generated, or gated.  
- There is no property-level api\_name discipline, only type-level.  
- There is no notion of a "breaking change" vs. "non-breaking change" for property mutations.

---

## Palantir OMS api\_name Reality

### What Palantir Actually Defines as `api_name`

The Palantir Foundry API (v1 and v2) defines `ObjectTypeApiName` as the **API name of the object type in camelCase format** — not namespaced, not semver-stamped, not dot-separated. The canonical example from the official API reference is simply `"employee"`, `"Flight"`, `"Employee"` ([Palantir Foundry API: Get Object Type](https://palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/)).

The v1 API response shape is:
```json
{
  "apiName": "employee",
  "description": "A full-time or part-time employee of our firm",
  "primaryKey": ["employeeId"],
  "properties": { "employeeId": { "baseType": "Integer" }, ... },
  "rid": "ri.ontology.main.object-type.0381eda6-..."
}
```

**Key finding:** `api_name` is `camelCase`, plain, human-readable. It is **not** namespaced with dots, not version-stamped with `.v<N>`. The `rid` (Resource Identifier, e.g. `ri.ontology.main.object-type.UUID`) is the actual stable machine identifier. The api_name is the developer-facing shorthand. Calling it "immutable" overstates the documentation; Palantir's docs say it can be changed from a default after creation ([Create Object Type](https://palantir.com/docs/foundry/object-link-types/create-object-type/)):

> "After creating a new object type, you can change the API name from the assigned default."

**What Palantir's API name rules actually are** ([Create Object Type](https://palantir.com/docs/foundry/object-link-types/create-object-type/)):

- Must follow "functional coding standards"  
- Must NOT be any of the reserved words: `ontology`, `object`, `property`, `link`, `relation`, `rid`, `primaryKey`, `typeId`, `ontologyObject`  
- Must be camelCase  
- Max 100 characters ([Stack Overflow: Foundry Actions API name limit](https://stackoverflow.com/questions/75602990/while-deploying-ontology-actions-through-foundry-templates-i-got-ontologymetadataobjecttype))
- Properties and link types have their own `PropertyApiName` / `LinkTypeApiName` variants

The official Palantir community design principles post (by a Foundry Solutions Architect, November 2025) explicitly states ([Ontology and Pipeline Design Principles](https://community.palantir.com/t/ontology-and-pipeline-design-principles/5481)):

> **"Avoid versioned Object Type names."**  
> Bad: `Message_v2`  
> Worse: `Message_v3_Embedded`

This is the exact opposite of what dharma_swarm PR #408 enforces (`dharma.<domain>.<TypeName>.v<N>`). Palantir's stated principle is that version suffixes in api_names are an **anti-pattern** because the api_name becomes hard to change once production code depends on it. Palantir's approach is that ObjectType schema evolution happens through property additions (additive) and schema migrations (OSv2 migration framework), not through version-bumped names.

### api\_name Immutability: What Palantir Actually Enforces

The docs do not state `api_name` is immutable post-creation. What IS protected when a type reaches `active` or `promoted` status is deletion and certain destructive operations. The `promoted` status applies "operational protections … such as restrictions on deletion" ([Metadata Statuses](https://palantir.com/docs/foundry/object-link-types/metadata-statuses/)). The OMS enforces status-based protections; it does not hard-lock the api_name field.

The real immutability mechanism in Palantir is the **Resource Identifier (RID)** — `ri.ontology.main.object-type.<UUID>`. This is the stable machine-readable identifier. api_name is a *human* shorthand that can be changed, but changing it breaks any OSDK consumers that generated code against it.

**Summary:** dharma_swarm's claim that `api_name` is "frozen and immutable" overstates Palantir's enforcement. Palantir does not freeze the string; it provides stable RIDs and warns against renaming via community best-practices guidance, not enforcement.

---

## Palantir OMS Status Lifecycle: Real Five-State Model

The actual Palantir status lifecycle has **five** values, not three ([Metadata Statuses](https://palantir.com/docs/foundry/object-link-types/metadata-statuses/)):

| Status | Description | Available To |
|---|---|---|
| `experimental` | Default for all new resources. Unfinished, expect changes. | All resource types |
| `active` | Stable, production-quality. Activates restrictions on deletion. | All resource types |
| `deprecated` | No production usage; should be deleted soon. | All resource types |
| `example` | Demo/tutorial content only. | All resource types |
| `promoted` | Highest trust; "core" resource, purple checkmark icon. Requires `Ontology Owner` role. | Object types only |

**The v1 API exposes four values** in the `releaseStatus` enum: `ACTIVE`, `ENDORSED`, `EXPERIMENTAL`, `DEPRECATED`. Note: `ENDORSED` appears in the v1 API response type but is not documented in the lifecycle UI guide — this may be a legacy value. The v2 API (`ontologies-v2-resources`) exposes `releaseStatus` as well.

**Cascade behavior** (platform-enforced, not just convention):  
- If an object type is moved to `experimental`, all its properties automatically become `experimental`.  
- If an object type is moved to `example`, all properties automatically become `example`.  
- If a property backing a link is marked `experimental`, the link type is automatically changed to `experimental`.  
- If a property is `deprecated`, its dependent link types become `deprecated`.  
- Ontology Manager will produce `OntologyMetadata:ConflictBetweenLinkTypeStatusAndPropertyTypeStatus` errors if inconsistencies arise.

**What dharma_swarm PR #408 misses:** Only three states modeled (`experimental`, `active`, `promoted`), no `deprecated` state, no `example` state, no cascade enforcement to properties or links, no check that deprecating an ObjectType triggers deprecation of dependent LinkDefs.

The Palantir API versioning documentation also shows that endpoints pass through `Public Preview` → `Stable` → `Deprecated` → removal with a **12-month notice window** for stable endpoint removal ([Foundry API Versioning](https://palantir.com/docs/foundry/api/general/overview/versioning/)):

> "If we have to replace or remove a stable endpoint, we will announce the change at least **twelve months** in advance, and provide continued support and SLA guarantees in the meantime."

dharma_swarm has no analogous notice window for ObjectType deprecation.

---

## Palantir OSDK Versioning + Consumer Contract

The OSDK is Palantir's primary consumer-side API generation mechanism. Key facts:

**How OSDK is generated:** The OSDK generates typed accessors from ontology metadata, keyed by `api_name`. It supports TypeScript (npm: `@osdk/client`), Python (pip), Java (Maven), and OpenAPI spec ([OSDK Overview](https://www.palantir.com/docs/foundry/ontology-sdk/overview/)).

**OSDK v1 → v2 breaking changes:** Palantir shipped OSDK 2.0 in October 2024 as GA. This was a major breaking change that:
- Changed the client invocation pattern: `legacyClient.objects.legacyObject.fetchPage()` → `client(myObject).fetchPage()`  
- Changed return types: `Page<myObject>` → `PageResult<Osdk.Instance<myObject>>`  
- Changed geo types: `GeoShape, GeoPoint` → `GeoJSON`  
- Removed the `OntologyObject` type (replaced by `OsdkBase`)  
- Changed `DateTime` handling from custom types to ISO 8601 strings  
([TypeScript OSDK Migration Guide](https://palantir.com/docs/foundry/ontology-sdk/typescript-osdk-migration/))

**Consumer deprecation window:** Palantir committed to maintaining v1.x support for "at least one year after the release of OSDK 2.0." New applications default to 2.0; existing apps must opt in to migrate.

**The core OSDK consumer contract for api_names:**  
- When you generate an OSDK, the generated package exports strongly-typed interfaces keyed by `api_name`. If `api_name` changes, the generated type name changes. All consumer code referencing the old name breaks at compile time.  
- The `$ontologyRid` is exported from the generated package and is used to bind the client. The ontology RID is stable across api_name changes; the generated type names are not.  
- **The OSDK has no automatic re-generation trigger.** If an ontology schema changes, consumers must manually regenerate their SDK and update their code.

**What dharma_swarm misses:** There is no OSDK equivalent — no code generation, no typed accessor generation from ontology metadata. The PR #408 gate catches api_name pattern violations but has no mechanism to notify downstream "SDK consumers" (whatever agents depend on the registry) when a type's api_name changes or when a property changes in a breaking way.

---

## Palantir OSv2 Migration Mechanics

OSv2 (Object Storage V2) replaces Phonograph (OSv1) as the backing store. The migration framework is documented at ([OSv1 to OSv2 Migration](https://palantir.com/docs/foundry/object-backend/osv1-osv2-migration/)) and the schema migration framework at ([Schema Migrations](https://palantir.com/docs/foundry/object-edits/schema-migrations/)).

**Key mechanics:**

1. **Mandatory migration:** Migration from OSv1 to OSv2 is mandatory for all object types. Large types (200M+ rows/200GB+) must migrate.

2. **Zero-downtime via soak period:** The migration framework dual-indexes in both OSv1 and OSv2 during a configurable soak period (up to 14 days). All queries route to OSv2 during soak; if issues arise, you can abort and revert to OSv1. After soak ends, rollback requires re-indexing (downtime risk).

3. **Transition windows:** Operators can configure preferred time windows (e.g., low-traffic hours on specific days) for the data cutover.

4. **Write freeze during migration:** User edits (mutations) are disabled during the migration period including the soak. Reads remain available.

5. **Breaking vs. non-breaking schema changes:** The schema migration framework distinguishes:
   - **Breaking changes** (require explicit migration instruction): changing property data type, changing backing datasource, changing primary key.  
   - **Non-breaking changes** (deployed transparently): adding new properties, updating descriptions.
   
6. **Predefined migration instructions (OSv2):** Drop all property edits, drop struct field edits, drop all edits, move edits, cast property to new type, revert migration. Max 500 migrations at once.

7. **Incompatible usage tracking:** OMS tracks incompatible usage (e.g., direct Phonograph API calls) and surfaces them in the Ontology Manager UI. Some incompatible usages will fail post-migration if not remediated.

**What is thin/paywalled in the docs:** The Ontology Manager UI screenshots are referenced frequently but not fully described in text. The exact API endpoints for triggering or checking migration state are not publicly documented (they are internal Foundry platform APIs). The "Upgrade Assistant" tool for model deprecation is documented for model deprecation but not for ObjectType schema migration. Community posts fill gaps that official docs leave thin.

**Relevance to dharma_swarm:** dharma_swarm has no equivalent of this dual-indexed soak period. When a type is modified in `ontology.py`, any downstream consumer that read the old schema immediately sees the new one (or sees nothing if the field is removed). There is no read/write separation during migrations, no soak period, no rollback mechanism.

---

## Peer Comparisons

| System | Naming Pattern | Versioning | Status Lifecycle | Deprecation Flow | Migration Tooling | Source URL |
|---|---|---|---|---|---|---|
| **Palantir Foundry OMS** | `camelCase` api_name (e.g. `employee`); stable `rid` for machine identity; explicitly anti-versioned-name | Major version in platform API URL (`/api/v1/`, `/api/v2/`); ObjectType schema versioned internally via schema version on OSv2 backend | 5 states: `experimental → active → promoted` (object types only) + `deprecated` + `example`; platform-cascade to properties/links | 12-month notice for stable API removal; `deprecated` HTTP response header; Upgrade Assistant UI | OSv2 dual-index soak period (up to 14 days); predefined schema migration instructions; transition windows | [palantir.com/docs/foundry/object-link-types/metadata-statuses/](https://palantir.com/docs/foundry/object-link-types/metadata-statuses/) |
| **Palantir OSDK (TypeScript)** | Generated from ontology `api_name`; consumer types keyed by api_name; changing api_name = compile-time break | Semantic versioning on SDK package (`@osdk/client`); OSDK 1.x → 2.0 was breaking with 1-year support window | Inherits ontology status; `experimental` ontology types not guaranteed in generated SDK | Manual SDK regeneration required; no auto-notification; 1-year LTS window for major versions | Developers must regenerate SDK via Developer Console when ontology changes | [palantir.com/docs/foundry/ontology-sdk/typescript-osdk-migration/](https://palantir.com/docs/foundry/ontology-sdk/typescript-osdk-migration/) |
| **dbt Semantic Layer** | snake_case entity names in YAML (`semantic_model`, `metric`); no namespace prefix; no version suffix in name | No first-class versioning of semantic models; models reference underlying dbt models which can be versioned independently | No published status lifecycle (experimental/active/deprecated); governance via project discipline | Deprecation by removing YAML definitions; no automated consumer notification | dbt model versioning (`model_version`) decoupled from semantic model naming | [docs.getdbt.com/docs/build/semantic-models](https://docs.getdbt.com/docs/build/semantic-models) |
| **Cube.dev Semantic Layer** | snake_case cube/view names (e.g. `orders`, `line_items`); no version suffix; no namespace | No built-in API versioning; REST/GraphQL API is single-version; breaking changes via manual coordination | No documented lifecycle states | No documented deprecation workflow | No built-in migration tooling for cube schema changes | [cube.dev/docs/product/data-modeling/concepts](https://cube.dev/docs/product/data-modeling/concepts) |
| **Apollo Federation (GraphQL)** | Field names in camelCase; subgraph service names; no version suffix in field names | No URL versioning; evolutionary API design; `@deprecated(reason: "...")` directive on fields/enum values | `@deprecated` flag is the only lifecycle state (binary: active or deprecated) | Usage metrics in GraphOS Studio; schema checks against operation traces; reach out to identified clients; then remove | Schema checks in CI; no dual-index period; rolling deploy of subgraphs; rollback via supergraph schema | [apollographql.com/docs/graphos/schema-design/guides/deprecations](https://www.apollographql.com/docs/graphos/schema-design/guides/deprecations) |
| **Protobuf + buf.build** | PascalCase message names; snake_case field names; version in package name (e.g. `pet.v1`); field numbers are stable identifiers | Package-level versioning (`v1`, `v2`); field numbers are immutable; field names can change (wire-safe) but break generated source | No semantic lifecycle states; breaking changes detected mechanically | `reserved` keyword for deleted field numbers; `deprecated = true` field option | `buf breaking` CLI: FILE/PACKAGE/WIRE_JSON/WIRE rule sets; CI + BSR server-side gates; PR review flow for breaking changes on BSR | [buf.build/docs/breaking/](https://buf.build/docs/breaking/) |

---

## What dharma\_swarm PR #408 Misses vs. PhD-Grade Enforcement

### Gap 1: Wrong api\_name Convention — Inverted Anti-Pattern

dharma_swarm enforces `dharma.<domain>.<TypeName>.v<N>`. Palantir explicitly prohibits versioned names like `Message_v2` and calls `Message_v3_Embedded` "worse." The official community design guide ([Ontology and Pipeline Design Principles](https://community.palantir.com/t/ontology-and-pipeline-design-principles/5481)) states: "Avoid versioned Object Type names." The dots-in-api_name pattern has no precedent in Palantir's own documentation. Palantir api_names are camelCase, flat, human-readable. The `v<N>` suffix is a Protobuf/gRPC pattern, not a Palantir OMS pattern. dharma_swarm has imported Protobuf-style naming into an ontology context where Palantir explicitly discourages it.

**What PhD-grade would do:** Separate the *stable machine identifier* (a UUID or RID) from the *human api_name*. Use a plain `camelCase` api_name for developer ergonomics. Use the RID for machine identity and backwards-compatible references. Version the schema separately via schema versions in the backing store, not in the name.

### Gap 2: ALIGN-007 is a Warning, Not an Error by Default

The api_name pattern check is only enforced as an error with `--strict`. This means agents can merge ObjectTypes with invalid api_names in normal CI runs. A gate that defaults to warning is not a gate — it is a suggestion box.

**What PhD-grade would do:** api_name discipline is either enforced hard in the Pydantic model at construction time (validator on `ObjectType.__init__`) or it is not enforced at all. The CI layer is a second line of defense, not the primary one.

### Gap 3: No Property-Level api\_name Discipline

Each `PropertyDef` in dharma_swarm has only a `name: str` field. There is no `api_name` for properties, no pattern enforcement, no stability guarantee. In Palantir, every property has its own `PropertyApiName` that appears in the OSDK-generated types and the API response map. Changing a property's api_name breaks every consumer referencing that property.

**What PhD-grade would do:** Apply the same naming discipline (and immutability semantics) to property names as to type names. Add `api_name: str` with a validator to `PropertyDef`. Track property api_name changes in the CI conflict detection.

### Gap 4: No Cascade Status Enforcement

dharma_swarm tracks `ObjectType.status` but has no mechanism to enforce that dependent `LinkDef` or `PropertyDef` statuses are consistent. Palantir enforces this at the platform level — an `active` link type cannot reference an `experimental` object type. The system raises `OntologyMetadata:ConflictBetweenLinkTypeStatusAndObjectTypeStatus` and blocks saves.

**What PhD-grade would do:** When a type's status changes (e.g., from `experimental` to `active`), validate that all its properties and all LinkDefs referencing it are also in a compatible status. ALIGN-003 only checks for conflicting status *across PRs*, not for internal consistency within a single PR.

### Gap 5: No `deprecated` or `example` States

The OntologyStatus enum in dharma_swarm has three values: `experimental`, `active`, `promoted`. Palantir has five. The absence of `deprecated` is critical: there is no machine-readable signal that a type is scheduled for removal, no way to automate "deprecated resources should be regularly deleted," and no deprecation notice mechanism to downstream agents.

**What PhD-grade would do:** Add `deprecated` as a mandatory lifecycle state. Add a `deprecated_at: datetime` field to `ObjectType`. Require that `promoted → deprecated` transitions include a deprecation reason and a `sunset_after: date` timestamp. The CI gate should fail if a `deprecated` type is still referenced by non-deprecated LinkDefs or ActionDefs.

### Gap 6: No Consumer Notification or SDK Re-Generation

When an ObjectType's api_name or property schema changes in dharma_swarm, there is no mechanism to notify downstream consumers. In Palantir, the OSDK propagates breaking changes at compile time — if an api_name changes, the generated TypeScript/Python types change and all downstream code fails to compile. In buf/gRPC, the `buf breaking` tool catches wire-format changes in CI. dharma_swarm has neither.

**What PhD-grade would do:** Build a consumer registry: every agent that reads an ObjectType via the OntologyRegistry should be registered as a "subscriber" to that type's schema. When the schema changes (property addition is non-breaking; property deletion/type change is breaking), subscribers should be notified (at minimum: logged with error severity; at best: CI fails with a diff report listing all affected consumers).

### Gap 7: `register_type` Uniqueness Guard is In-Memory Only

The `OntologyRegistry` is an in-memory singleton in Python. The uniqueness guard (checking for duplicate api_names) only works within a single process run. Across concurrent agent processes or restarts, the guard is invisible. Two agents running in parallel processes can both successfully `register_type` with the same api_name and neither will see the conflict until the CI gate runs.

**What PhD-grade would do:** The uniqueness guard must be backed by a persistent store (e.g., the ontology.py file itself as the source of truth, enforced via the AST-parse CI gate — which is what check_ontology_alignment.py does). Alternatively, use a lock file or a Redis/Postgres backend for the registry during live agent runs. The current design conflates two separate concerns: runtime registry and schema governance registry.

### Gap 8: No "Breaking vs. Non-Breaking" Change Classification

dharma_swarm's CI gate detects *conflicts* between PRs (ALIGN-001 through ALIGN-007) but does not classify changes as breaking vs. non-breaking. Palantir's OSv2 schema migration framework has a documented taxonomy of what is breaking:

- **Breaking (require migration instruction):** changing property data type, changing backing datasource, changing primary key  
- **Non-breaking (deployed transparently):** adding new properties, updating descriptions

buf.build's WIRE/WIRE_JSON/FILE/PACKAGE categories provide the same graduated taxonomy for Protobuf.

dharma_swarm has no such taxonomy. ALIGN-001 flags any diff in `api_name`, `telos_alignment`, `shakti_energy`, `version`, or `description` as an error — even a description change, which is non-breaking. This creates noise and desensitizes reviewers to real breaking changes.

### Gap 9: No Transition Window or Soak Period for Schema Changes

When a breaking schema change is merged to main in dharma_swarm, it takes effect immediately. Palantir's OSv2 migration allows:  
- A configurable soak period (up to 14 days) where both old and new indices are live.  
- A transition window (specific hours/days) for the cutover.  
- Abort-and-revert during soak with no downtime.

The dharma_swarm equivalent would be: a schema version stamp on ObjectType that existing instances can still be read against, while new writes use the new schema. This is especially relevant for `OntologyObj` instances already stored in JSONL backends.

### Gap 10: No Governance Authority Model

Palantir's OMS is operated by a single "forward-deployed engineer" acting as the ontology authority. The `promoted` status requires the `Ontology Owner` role. check_ontology_alignment.py documents this correctly ("dharma_swarm has 5 agents... editing concurrently") but then defers authority to "Operator (@AmitabhainArunachala) decides if ambiguous" — which is correct in principle but has no machine enforcement. There is no role-based gate that prevents an agent from promoting a type to `promoted` without operator sign-off. ALIGN-006 catches removal of `PROMOTED` types without a deprecation marker, but there is no check that promotion itself required authorization.

---

## Adversarial Questions

**1. Why does dharma_swarm's `api_name` pattern (`dharma.<domain>.<TypeName>.v<N>`) include a version suffix that Palantir's own design guide explicitly calls an anti-pattern?** The Palantir community guidance says "Avoid versioned Object Type names. Bad: `Message_v2`. Worse: `Message_v3_Embedded`." What concrete operational justification overrides this?

**2. The OntologyRegistry uniqueness guard is in-memory. Two agents running as separate processes (e.g., claude and devin) can both successfully register `dharma.core.Task.v1` and not discover the conflict until CI runs. How long is the window between concurrent agent writes and CI gate execution? What is the blast radius if they both commit to different branches and both get merged before CI runs?**

**3. ALIGN-007 is a warning by default. This means in normal CI (`python check_ontology_alignment.py` without `--strict`), a PR with api_name `dharma.FOO.Bar.v1` (violating PascalCase domain) will merge. Is the --strict flag enforced in the CI YAML? If not, the api_name discipline is advisory, not enforceable.**

**4. There is no `deprecated` state in dharma_swarm's ObjectType. When a PROMOTED type becomes obsolete, what is the machine-readable signal to downstream agents that they should stop using it? "Operator decides" is not a machine-readable signal — agents will continue to reference deprecated types because there is no programmatic path to discovery.**

**5. Property names in dharma_swarm (`PropertyDef.name`) are free-form strings with no api_name discipline. If an agent renames a property from `task_id` to `taskId`, this is a breaking change for any agent that reads `OntologyObj.properties["task_id"]`. The CI gate does not check property-level API name stability. How many lines of downstream agent code depend on specific property names? Has this been audited?**

**6. The schema change classification is binary in dharma_swarm: conflict or no conflict. Palantir's OSv2 migration framework distinguishes breaking from non-breaking changes. A description update triggers ALIGN-001 just like a primary key change. Is this noise-to-signal ratio acceptable for a system with 5 concurrent agent editors?**

**7. What happens to `OntologyObj` instances already stored in JSONL backends when an ObjectType schema changes (e.g., a property is removed)? dharma_swarm has no migration framework for live data. Palantir's OSv2 migration predefined instructions (drop edits, cast property type, move edits) address exactly this. The PR #408 doc says "never modifies ontology.py, never auto-resolves" — but it says nothing about the existing data.**

**8. The `promoted` status requires the `Ontology Owner` role in Palantir, enforced by the platform. In dharma_swarm, which code path enforces that only the human operator (not an agent) can promote a type? If mike (merge authority) can merge any PR with `status="promoted"`, the promotion control is entirely social, not technical.**

---

## Recommended Hardening Passes (Ranked by Impact)

### Hardening Pass 1 (Highest Impact): Move api\_name Validation into `ObjectType` at Construction Time

Currently, api_name discipline lives in CI only. The Pydantic `ObjectType` model should enforce the api_name pattern at instantiation with a `@validator`:

```python
from pydantic import validator
import re

API_NAME_PATTERN = re.compile(r"^dharma\.[a-z][a-z0-9_]*\.[A-Z][A-Za-z0-9]*\.v\d+$")

class ObjectType(BaseModel):
    api_name: str  # Make required, not Optional
    
    @validator("api_name")
    def validate_api_name(cls, v):
        if not API_NAME_PATTERN.match(v):
            raise ValueError(f"api_name '{v}' violates pattern dharma.<domain>.<TypeName>.v<N>")
        return v
```

This catches violations at the point of registration, not hours later in CI. However — see Gap 1 — first settle whether the naming convention itself is correct (Palantir explicitly deprecates version suffixes in api_names).

**OR**: Separate the machine-stable identifier from the human api_name. Add `rid: str` (auto-generated UUID) as the true stable identifier and allow `api_name` to be a human-readable camelCase name that can change. Track `rid` in the conflict detection instead of api_name.

### Hardening Pass 2: Add `deprecated` State + Sunset Enforcement to the Status Machine

Add `deprecated` to `OntologyStatus`:

```python
class OntologyStatus(str, Enum):
    EXPERIMENTAL = "experimental"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    PROMOTED = "promoted"
```

Add to `ObjectType`:
```python
deprecated_at: datetime | None = None
sunset_after: date | None = None
deprecation_reason: str = ""
```

Add ALIGN-008 to the CI gate: fail if a non-deprecated ObjectType references a deprecated LinkDef or if a deprecated type is still used as `target_type` in a non-deprecated LinkDef.

### Hardening Pass 3: Property-Level api\_name Discipline + Breaking Change Classification

Add `api_name: str` to `PropertyDef` with pattern enforcement (snake_case for properties, not camelCase — matching Palantir's actual property naming convention). Add ALIGN-009 to the CI gate: detect property api_name changes between PR and main and classify them as:

- **Non-breaking:** description change, adding a new property with `required=False`  
- **Breaking:** renaming existing property api_name, changing `property_type`, removing a property, changing `required=False` to `required=True`

For breaking changes, require a migration instruction (analogous to OSv2's migration instructions) before the PR can be approved.

### Hardening Pass 4: Consumer Registry + Propagation Notification

Build a consumer registry that records which agent code paths depend on which ObjectType api_names and PropertyDef api_names. At minimum, a static analysis pass that searches the codebase for string literals matching known api_names. When the CI gate detects a breaking change (per Pass 3), output a **CONSUMER IMPACT REPORT**: which files, which function calls, which agents are affected. This mirrors buf.build's CI PR comments and Apollo's GraphOS Studio client impact reports.

### Hardening Pass 5: Promote ALIGN-007 to Error-by-Default; Add Status Transition Monotonicity Check to Object Model

(a) Set ALIGN-007 to `severity="error"` unconditionally. Remove the `--strict` flag for production CI — strict should be the default. Non-strict can be a development convenience flag.

(b) Add monotonicity enforcement to `OntologyRegistry.update_type` (or wherever status transitions are applied):

```python
VALID_TRANSITIONS = {
    "experimental": {"active", "deprecated"},
    "active": {"promoted", "deprecated"},
    "promoted": {"deprecated"},  # Can only go to deprecated, never back
    "deprecated": set(),  # Terminal state
}

def transition_status(current: str, proposed: str) -> str:
    if proposed not in VALID_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid status transition: {current} → {proposed}")
    return proposed
```

This enforces monotonicity at the code level, not just in the CI conflict check.

---

## Sources

1. Palantir Foundry Ontology Overview — https://www.palantir.com/docs/foundry/ontology/overview  
2. Palantir API: Get Object Type (v1) — https://palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/  
3. Palantir Foundry: Metadata Statuses (experimental/active/promoted/deprecated/example lifecycle) — https://palantir.com/docs/foundry/object-link-types/metadata-statuses/  
4. Palantir Foundry: Create Object Type (api_name format, camelCase rules, reserved words, mutability) — https://palantir.com/docs/foundry/object-link-types/create-object-type/  
5. Palantir OSDK Overview — https://www.palantir.com/docs/foundry/ontology-sdk/overview/  
6. Palantir TypeScript OSDK 1.x → 2.0 Migration Guide (breaking changes, consumer contract, 1-year LTS window) — https://palantir.com/docs/foundry/ontology-sdk/typescript-osdk-migration/  
7. Palantir OSv1 → OSv2 Migration (zero-downtime soak period, transition windows, mandatory migration) — https://palantir.com/docs/foundry/object-backend/osv1-osv2-migration/  
8. Palantir OSv2 Schema Migrations (breaking vs. non-breaking, predefined migration instructions) — https://palantir.com/docs/foundry/object-edits/schema-migrations/  
9. Palantir Foundry API Versioning (12-month deprecation notice, breaking vs. non-breaking changes) — https://palantir.com/docs/foundry/api/general/overview/versioning/  
10. Palantir Community: Ontology and Pipeline Design Principles (avoid versioned api_names, maturity status discipline, design rules) — https://community.palantir.com/t/ontology-and-pipeline-design-principles/5481  
11. Palantir foundry-platform-python GitHub: ObjectType.md (api_name as identifier for GET endpoints, v1 Stable methods) — https://github.com/palantir/foundry-platform-python/blob/develop/docs/v1/Ontologies/ObjectType.md  
12. Palantir osdk-ts GitHub (TypeScript OSDK library; semver via changesets; contributor semver rules) — https://github.com/palantir/osdk-ts  
13. Palantir October 2024 Release Notes (OSDK 2.0 GA announcement) — https://palantir.com/docs/foundry/announcements/2024-10/  
14. dbt Semantic Models Documentation — https://docs.getdbt.com/docs/build/semantic-models  
15. Cube.dev Data Modeling Concepts — https://cube.dev/docs/product/data-modeling/concepts  
16. Apollo GraphQL Schema Deprecations Guide (@deprecated directive, field usage metrics, schema checks) — https://www.apollographql.com/docs/graphos/schema-design/guides/deprecations  
17. buf.build Breaking Change Detection (FILE/PACKAGE/WIRE_JSON/WIRE categories; CI integration; BSR server-side checks) — https://buf.build/docs/breaking/  
18. buf.build Breaking Change Rules Reference — https://buf.build/docs/breaking/rules/  
19. Stack Overflow: Foundry Actions API name max 100 chars — https://stackoverflow.com/questions/75602990/while-deploying-ontology-actions-through-foundry-templates-i-got-ontologymetadataobjecttype  
20. Palantir Community: Drilling down on OSv2 incompatible usage — https://community.palantir.com/t/drilling-down-on-incompatible-usage-for-a-osv2-migration/3299

---

*Note on documentation gaps: Palantir's docs do not expose the internal OMS API endpoints (no public REST spec for creating/mutating ObjectTypes through OMS directly — only for reading via the public Foundry API). The mechanism by which Palantir enforces api_name immutability server-side (if any) is not documented publicly; the docs describe protections tied to `active`/`promoted` status but do not document an api_name rename endpoint or a mutation rejection. Community posts and the platform SDK source code fill this gap partially. Treat claims about "OMS authority model" enforcement details as inferred from behavior, not explicitly documented.*
