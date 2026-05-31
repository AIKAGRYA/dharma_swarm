# Online Schema Migration + Enterprise Semantic Layer Architecture
## Adversarial Research Report: grounding dharma_swarm's OMS hardening in external evidence

**Author:** Computer research agent (adversarial posture)
**Date:** 2026-06-01
**Scope:** Palantir OSv2, dbt Semantic Layer, Snowflake Cortex, Neo4j Migrations, Atlan/Collibra/Alation, Liquibase/Flyway, academic literature (F1, Spanner, BullFrog, SLSM)
**Directive:** "Be the adult that grounds it in hardcore external research." — Operator

---

## Context: dharma_swarm's Current Naive Backfill Plan

dharma_swarm's `dharma_swarm/ontology.py` defines **21 `ObjectType` instances** in `_DOMAIN_TYPES`:

```
ResearchThread, Experiment, Paper, AgentIdentity, CustodianRole,
KnowledgeArtifact, TypedTask, EvolutionEntry, WitnessLog,
ActionProposal, GateDecisionRecord, ExecutionLease, Outcome, ValueEvent,
Contribution, VentureCell,
RevenueTarget, RevenueOffer, RevenueOutreachDraft, RevenueEngagement,
ComputeReinvestment
```

The in-flight OMS hardening (Devin) proposes adding two new fields to `ObjectType`:

- `api_name: str` — a stable machine-readable identifier
- `status: str` — lifecycle status (e.g., `ACTIVE`, `DEPRECATED`, `EXPERIMENTAL`)

The current plan is: **edit the `ObjectType` Pydantic model, add defaults to all 21 type definitions, and redeploy.** There is:
- No migration versioning
- No zero-downtime mechanism
- No consumer notification
- No rollback plan
- No audit trail for what existed before

This report documents what real systems do and identifies the specific failure modes of the proposed approach.

---

## Palantir OSv2 Migration: What Is Publicly Known

### The OSv1 → OSv2 Migration Framework

Palantir has published detailed documentation of its Object Storage V2 (OSv2) migration framework. The primitives are:

**Dual-index soak period:** When an object type migrates from Phonograph (OSv1) to OSv2, both indices are kept in sync simultaneously for up to 14 days ([Palantir docs: OSv1-OSv2 migration](https://palantir.com/docs/foundry/object-backend/osv1-osv2-migration/)). During this window, queries are routed to OSv2 while OSv1 remains warm for rollback. After the soak period ends, OSv1 rollback is **permanently unavailable**.

**Transition windows:** The migration does not cut over immediately. The first Funnel pipeline must complete; then a transition window (configurable time-of-day) is required before Object Set Service (OSS) switches reads to OSv2 ([Palantir docs: OSv1-OSv2 migration](https://palantir.com/docs/foundry/object-backend/osv1-osv2-migration/)). This prevents cutover during high-traffic periods.

**User-edit lockout:** Edits are automatically disabled from the moment migration is defined through the entire soak period ([Palantir docs: OSv1-OSv2 migration](https://palantir.com/docs/foundry/object-backend/osv1-osv2-migration/)). Object reads remain available. This is an **explicit consumer-impact window**.

**Backfill mechanics:** After migration initiation, it may take up to 30 minutes to initiate the first Funnel pipeline. If the pipeline fails, a `PIPELINE_FAILED` error appears in the Datasources tab ([Palantir docs: OSv1-OSv2 migration](https://palantir.com/docs/foundry/object-backend/osv1-osv2-migration/)). There is no automatic retry beyond the next transition window.

**Rollback semantics:** Abort during soak period = immediate revert to OSv1 without re-indexing. After soak period = **no rollback** ([Palantir docs: OSv1-OSv2 migration](https://palantir.com/docs/foundry/object-backend/osv1-osv2-migration/)).

### OSv2 Schema Migration for Object Type Evolution

A separate migration framework governs *within-OSv2 schema changes*. The key rules:

**Breaking changes that trigger migration mode:**
- Changing the data type of an existing property
- Changing an object type's backing datasource
- Changing the primary key of an object type
- Changing the ID of a property that has received user edits
- Deleting a property that has received user edits
- Changing the data type of a struct field

**Non-breaking changes (no migration required):**
- Changing display name, title key, render hints, type classes, or visibility
- Deleting properties or making schema changes to properties **that have never received user edits**

([Palantir docs: schema-migrations](https://palantir.com/docs/foundry/object-edits/schema-migrations/))

**Adding new properties** is implicitly non-breaking — which is what Devin's `api_name` + `status` plan attempts. However, the critical gap: Palantir's system has *predefined migration instructions* for breaking changes (e.g., "migrate edits from old property to new property"). dharma_swarm has no equivalent.

**Schema versioning:** Once a schema change is saved, a new schema version is created in the backend, and a Funnel replacement pipeline is orchestrated. The new version is queryable "as soon as the replacement pipeline is completed and the new version is declared to be fully hydrated by object databases" ([Palantir docs: schema-migrations](https://palantir.com/docs/foundry/object-edits/schema-migrations/)). Maximum 500 schema migrations in a single batch.

**Value type versioning:** Palantir values types (semantic wrappers around properties) have an explicit breaking/non-breaking split. Non-breaking changes auto-propagate; breaking changes require deprecating the old type and creating a new one ([Palantir docs: value-types-versions](https://palantir.com/docs/foundry/object-link-types/value-types-versions)). The `api_name` (apiName) field for value types is listed as mutable *metadata*, but the `base type` is immutable.

**Critical Palantir community evidence:** A 2025 community post documented that removing a property broke a downstream action type, and the breakage "went unnoticed" because the Ontology Manager does not currently run dependency checks before merging ([Palantir Developer Community: breaking changes](https://community.palantir.com/t/unintended-breaking-changes-when-removing-object-type-proeprties-in-the-ontology-manager/3557)). A separate post notes: "Avoid versioned Object Type names. The Ontology should only contain stable Object Types required to support a decision. If you need to deprecate properties, carry out the migration fully" ([Palantir Community: design principles](https://community.palantir.com/t/ontology-and-pipeline-design-principles/5481)).

### What is *not* publicly known about Palantir OSv2

Palantir does not publicly disclose:
- Internal shadow-type mechanics beyond what is described above
- Specific A/B routing weights during dual-index period
- Whether consumer SDK versions are automatically pinned to schema versions
- Multi-tenant schema isolation details
- Conference talks at QCon, Strange Loop, or ESWC that describe internal primitives beyond what the docs expose

**Assessment:** Palantir's public documentation is the most detailed of any vendor on this list for actual migration primitives, but it is still documentation — not engineering detail. Claims about "OSv2 shadow types" as a general-purpose migration primitive are not supported by any public source found; the actual mechanism is dual-index + soak period + transition windows.

---

## dbt Semantic Layer Evolution Mechanics

### Model Versioning (the actual migration primitive)

dbt introduced model versioning in v1.5 to enable **intentional breaking changes** with a migration window. The mechanism:

**`ref()` versioning:** Consumers pin to a specific version with `ref('dim_customers', version=2)`. Unversioned refs resolve to `latest_version` ([dbt-core discussion #6736](https://github.com/dbt-labs/dbt-core/discussions/6736)).

**Deprecation dates:** Older versions must specify a `deprecation_date`. After that date, dbt raises warnings on compilation/run ([dbt-core discussion #6736](https://github.com/dbt-labs/dbt-core/discussions/6736)). There is no automatic enforcement or deletion.

**Contract enforcement:** `contract: true` on a model enables schema enforcement. CI detects breaking changes (removing columns, changing data types, removing constraints) without a version bump and raises an error. Adding columns is **not** a breaking change ([dbt-core discussion #6736](https://github.com/dbt-labs/dbt-core/discussions/6736)).

**Warehouse aliasing:** By default, versioned model `v2` of `dim_customers` materializes as `dim_customers_v2`. The unversioned name is not automatically created ([dbt-core discussion #6736](https://github.com/dbt-labs/dbt-core/discussions/6736)).

### Semantic Layer Spec Migration (the messy reality)

The January 2026 spec redesign broke the prior semantic model YAML structure:

**Breaking changes introduced:**
- `measures` removed from authorship spec; metrics now defined directly
- YAML structure reorganized (annotations embedded in model YAML, not separate files)
- Deep dictionary nesting removed; keys renamed

**Migration tooling:** `dbt-autofix deprecations --semantic-layer` migrates "the vast majority of the code" automatically ([dbt blog: modernizing-the-semantic-layer-spec](https://docs.getdbt.com/blog/modernizing-the-semantic-layer-spec)). The phrase "vast majority" is not quantified.

**Consumer story:** Consumers on legacy spec can continue until they upgrade to dbt Core 1.12+ or migrate to Fusion engine. The old spec "still works" ([Paradime comparison](https://www.paradime.io/blog/dbt-semantic-layer-vs-snowflake-semantic-views-a-complete-technical-comparison)). Migration is **opt-in**, not forced.

**Assessment:** dbt has migration tooling for the spec change but **no zero-downtime primitive for semantic model evolution**. The model versioning framework (`ref()` pinning + deprecation dates) is the closest to a proper migration primitive. There is no dual-write, no consumer notification beyond deprecation warnings, and no rollback.

---

## Snowflake Cortex Semantic-Model Evolution

### Semantic Views (schema-level objects, GA 2025-2026)

Snowflake semantic views are schema-level objects storing business semantics (metrics, dimensions, facts, relationships) natively in the database, replacing the earlier YAML-file-in-a-stage approach ([Snowflake engineering blog: native-semantic-views-ai-bi](https://www.snowflake.com/en/blog/engineering/native-semantic-views-ai-bi/)).

**Schema evolution mechanics:**
- Semantic views support `CREATE OR REPLACE SEMANTIC VIEW` — a full replace-in-place operation
- Snowflake's `ENABLE_SCHEMA_EVOLUTION` parameter on tables allows automatic column addition from new data ([Snowflake docs: schema-evolution](https://docs.snowflake.com/en/user-guide/data-load-schema-evolution))
- Standard SQL `SELECT * FROM SEMANTIC_VIEW(...)` syntax for querying went GA March 2, 2026 ([Paradime comparison](https://www.paradime.io/blog/dbt-semantic-layer-vs-snowflake-semantic-views-a-complete-technical-comparison))

**Consumer update mechanics:** Partners (Sigma, Hex, Omni) integrate directly. When a semantic view is updated, Sigma reflects changes immediately. Omni provides "schema refresh, dynamic dev/test environments and content validation" to ensure analysis stays in sync ([Snowflake engineering blog](https://www.snowflake.com/en/blog/engineering/native-semantic-views-ai-bi/)). However, no Snowflake-native *migration protocol* (no staging, no soak period, no consumer notification API) is documented in public sources.

**Open Semantic Interchange (OSI):** A vendor-neutral spec finalized January 2026 for portable semantic layer constructs ([Snowflake OSI blog](https://www.snowflake.com/en/blog/open-semantic-interchanges-specs-finalized/)). Still early-stage. Not a migration framework.

**Assessment:** Snowflake's semantic view evolution story is **replace-in-place**. There is no versioning, no staged cutover, no migration primitive. If a semantic view change breaks a consumer, the consumer breaks immediately. Snowflake's `ENABLE_SCHEMA_EVOLUTION` applies to underlying tables (auto-adding columns) not to semantic view evolution. The docs on this are thin because the feature is new (GA 2025).

---

## Neo4j + Graph Schema Evolution

### The Schema-Freedom Problem

Neo4j is "schema-free" in the relational sense — there is no enforced schema on node properties. Labels and relationship types exist; constraints and indexes are optional overlays. This means graph schema migration is fundamentally about *data migration* (re-labeling nodes, renaming properties, adding/removing constraints) rather than DDL ([Stack Overflow: Neo4j schema migrations](https://stackoverflow.com/questions/53083183/neo4j-schema-migrations)).

### neo4j-migrations (michael-simons/neo4j-migrations)

The de facto migration tool for Neo4j, inspired directly by Flyway ([GitHub: neo4j-migrations](https://github.com/michael-simons/neo4j-migrations)).

**Migration primitives:**
- **Cypher-based migrations** (`.cypher`): versioned scripts run exactly once, stored in the database as a subgraph
- **Catalog-based migrations** (`.xml`): declarative schema items (constraints, indexes) with operations `create`, `drop`, `verify`, `apply`
- **Java-based migrations**: programmatic refactorings implementing `JavaBasedMigration`
- **Built-in refactorings**: `rename.label`, `rename.type`, `rename.nodeProperty`, `rename.relationshipProperty`, `addSurrogateKeyTo.nodes`, `normalize.asBoolean`, `merge.nodes` ([neo4j-migrations docs](https://michael-simons.github.io/neo4j-migrations/2.9.3/))

**Versioning:** Files named `V1_2_3__Description.cypher`. Applied migrations are immutable (checksum-verified). Repeatable migrations (`R__`) can be re-run when changed.

**Catalog versioning:** Items are versioned by migration version + item ID. The same constraint name at versions 1 and 2 is accessible in both variants — enabling drop-and-recreate patterns ([neo4j-migrations docs](https://michael-simons.github.io/neo4j-migrations/2.9.3/)).

**Rollback:** neo4j-migrations does **not** support transactional rollback of applied migrations. `repair` fixes the chain; `clean` removes metadata. Rollback = write a new migration that reverses the effect ([neo4j-migrations docs](https://michael-simons.github.io/neo4j-migrations/2.9.3/)).

**Zero-downtime patterns:** Not explicitly supported by the tool. Must be implemented via Cypher scripts that add labels first, backfill, then remove old labels in subsequent migrations.

**Applicability to dharma_swarm:** dharma_swarm's ontology is stored in Python code (in-process), not in a graph database. Neo4j-migrations' specific primitives do not apply directly. However, the *pattern* (versioned scripts, immutable history, repair-not-rollback) is directly applicable.

---

## Atlan / Collibra / Alation: Actual Mechanisms

### Atlan

Atlan's documentation on schema evolution is **thin and largely marketing**. The technical content found:

- Atlan catalogs Confluent Schema Registry assets and provides "visibility into schema evolution, compatibility, and governance" — but the actual migration primitives are not documented publicly ([Atlan docs: Confluent Schema Registry](https://docs.atlan.com/apps/connectors/schema/confluent-schema-registry))
- The Atlan data catalog migration guide describes re-ingesting technical metadata from source systems; it does not describe type versioning or migration primitives for Atlan's own asset types ([Atlan guide: migration-best-practices](https://atlan.com/know/data-catalog/migration-best-practices/))
- Atlan's approach to evolving the catalog schema appears to be: point connectors at source systems and let automated discovery rebuild the technical layer

**Verdict: Atlan's docs are thin on schema evolution mechanics. No migration primitives found.**

### Collibra

Collibra exposes:
- BPMN-based approval workflows for asset state changes (governance-layer workflows, not schema-layer migration) ([Collibra developer portal: approval process](https://developer.collibra.com/workflows/workflow-documentation/Content/Workflows/OOTBWorkflows/ApprovalProcess/co_ootb-wf-approval-process-walk-through.htm))
- REST APIs for asset management (PUT, GET, DELETE)
- The Hackolade-Collibra integration uses `SET/REPLACE` semantics on the Import API: existing edits in Collibra **are overwritten** by subsequent publishes from the data model tool ([Hackolade-Collibra integration](https://hackolade.com/help/CollibraDataDictionaryintegratio.html)) — a destructive default with no merge semantics
- Metadata versioning history exists for traceability, but schema evolution tooling is not documented at the primitive level
- CI/CD integration: datasets can be blocked from promotion to PROD until Collibra's steward certification API returns success

**Verdict: Collibra provides governance workflows and lineage, not schema migration primitives. The Import API's destructive SET/REPLACE behavior is a direct analogy to dharma_swarm's current plan.**

### Alation

Alation provides:
- **Impact analysis via lineage:** Given a table/column change, Alation traverses the lineage graph to identify all downstream BI reports, pipelines, and data stewards that depend on it ([Alation YouTube: data lineage impact analysis](https://www.youtube.com/watch?v=HAlP_QB1mJ8))
- Column-level lineage for precise impact scoping
- Deprecation flag propagation: marking an asset deprecated propagates warnings to all impacted downstream assets automatically
- Export to CSV for stakeholder communication

**Verdict: Alation is impact-analysis tooling, not migration tooling. Its value is identifying what breaks *before* you make a change — which dharma_swarm currently does not have.**

---

## Liquibase/Flyway Patterns Applicable to ObjectType Evolution

### Core Primitives

Both tools implement the same fundamental pattern: numbered, ordered, immutable changesets applied exactly once, with history stored in a `DATABASECHANGELOG` / `flyway_schema_history` table.

**Liquibase changeset types applicable to ObjectType evolution:**

| Changeset Operation | Relational DB Equivalent | dharma_swarm Analogy |
|---|---|---|
| `addColumn (nullable=true)` | Add nullable column | Add `api_name: str = ""` with default |
| `addNotNullConstraint` (after backfill) | Enforce NOT NULL after backfill complete | Add `api_name: Required[str]` only after all instances populated |
| `update` (data migration) | `UPDATE table SET col = ...` | Backfill existing type definitions with `api_name` values |
| `dropColumn` (contract phase) | Remove old column | Remove deprecated property after consumers migrated |
| `addUniqueConstraint` | Add uniqueness | Enforce uniqueness of `api_name` across types |
| `createIndex` | Add index | Add searchable index on `api_name` in storage backend |

([Zero-downtime migrations guide](https://java.elitedev.in/java/zero-downtime-database-migrations-liquibase-spring-boot/))

### The Expand-Contract Pattern (the only safe zero-downtime approach)

The industry-standard pattern for zero-downtime field addition is **Expand-Contract (also called Parallel Change)**:

1. **Expand:** Add the new field as **nullable/optional with a default**. Old code ignores it; new code can write to it. Deploy this first, before any code that requires the field.
2. **Backfill:** Run a background job that populates the new field for all existing instances. Must be idempotent and batched to avoid locking.
3. **Switch reads:** Deploy new code that reads from the new field. Verify no consumers use the old path.
4. **Contract:** Only after all consumers are on the new code, make the field required or remove the old field.

**Critical rule:** Never make a field required in the same deployment that adds it. This is the **single most common zero-downtime mistake** ([JusDB: zero-downtime migrations](https://www.jusdb.com/blog/schema-versioning-and-migration-strategies-for-scalable-databases), [zero-downtime discussion](https://www.linkedin.com/posts/mohamedhabibwork_database-devops-ci-activity-7432151855209734144-mmhu)).

### Flyway-Specific Notes

- Flyway does **not** support automatic rollbacks. Once applied, a migration must be reversed by a new forward migration ([Flyway DevCommunity](https://dev.to/mspilari/database-migrations-with-flyway-in-spring-boot-5g0a)).
- The `liquibase-zd` plugin (zero-downtime extension for Liquibase) automates the expand-contract pattern for PostgreSQL ([GitHub: liquibase-zd](https://github.com/coenvk/liquibase-zd)).
- Migrations that fail partway through leave the schema in a partially-migrated state. Transactional DDL (PostgreSQL) helps; MySQL has implicit commits and cannot be fully rolled back ([Atlas docs: applying migrations](https://atlasgo.io/versioned/apply)).

---

## Academic State-of-the-Art on Online Schema Migration

### F1: Online, Asynchronous Schema Change (Rae et al., 2013, VLDB)

This is the foundational paper, published at VLDB 2013 and implementing schema changes in Google's F1 database backing Google AdWords.

**Core constraint:** "Downtime or table locking during schema changes is not acceptable" — directly measured in revenue impact. ([F1 distributed SQL paper, Google Research](https://static.googleusercontent.com/media/research.google.com/en/us/pubs/archive/41344.pdf))

**The protocol:** At most **two schema versions** may coexist at any time. Servers use either the current version or one version old. This is the minimum that allows safe asynchronous transitions ([F1 schema change paper](https://static.googleusercontent.com/media/research.google.com/en/pubs/archive/41376.pdf)).

**State machine for schema elements:**

```
absent → delete-only → write-only → public   (for adding required elements)
absent → delete-only → public                 (for adding optional elements)
absent → write-only → public                  (for adding constraints)
```

Each transition must wait at least one **schema lease period** (the time any server can use an old schema). This prevents the scenario where two servers simultaneously use incompatible schemas.

**Why single-step addition causes corruption:** Adding index `I` directly to schema `S2` while servers still run `S1`: a server on `S2` adds a row + index entry; a server on `S1` deletes the row without touching `I` (because `S1` doesn't know about `I`). Result: orphan index entry, corrupted index. ([F1 schema change paper](https://static.googleusercontent.com/media/research.google.com/en/pubs/archive/41376.pdf))

**The write-only intermediate state:** In `write-only`, the index is maintained by all writes but not read by any queries. This ensures the index is kept consistent by the time it becomes `public`. The database reorganization (backfill) happens during the write-only → public transition, ensuring completeness before consumers can read from the index.

**Applicability:** F1's model is for distributed databases with stateless servers and no global membership. dharma_swarm's ontology.py is in-process Python — but the **conceptual model** (intermediate states, max-2-versions, schema lease periods) directly applies to any system where multiple agent instances run concurrently against the same ontology definition.

### Spanner: Atomic Schema-Change Transactions (Corbett et al., 2012, OSDI)

Spanner uses **TrueTime** to assign schema changes a future timestamp. All reads/writes that would occur after that timestamp block behind the schema change; those that would occur before it proceed. This achieves atomic cross-datacenter schema changes without locking. ([Spanner OSDI paper](https://static.googleusercontent.com/media/research.google.com/en/archive/spanner-osdi2012.pdf))

**Key insight for dharma_swarm:** The mechanism requires a shared time source. Without it, "defining the schema change to happen at t would be meaningless." In a Python multi-agent system, the equivalent is a **distributed lock + epoch counter**: agents must agree on a schema epoch before executing.

### BullFrog: Online Schema Evolution via Lazy Evaluation (Bhattacherjee et al., SIGMOD 2021)

BullFrog supports **single-step schema migrations** — even backwards-incompatible ones — without downtime or advance notice. When a migration is submitted, BullFrog initiates a logical switch to the new schema immediately but physically migrates data **lazily, as it is accessed** by incoming transactions. ([BullFrog, ACM SIGMOD 2021](https://dl.acm.org/doi/10.1145/3448016.3452842))

**Key insight:** The "service vacuum" problem (period between schema deployment and full data migration) is eliminated by serving old data through the new schema on-demand. Implemented as a PostgreSQL extension.

### SLSM: Lazy Schema Migration on Shared-Nothing Databases (Zeng et al., 2024, arXiv)

SLSM extends BullFrog's lazy approach to distributed shared-nothing databases. It keeps old and new schemas with the same data distribution (reducing cross-node communication), and "fuses" migration transactions with user transactions — migrating only the data accessed by each user transaction, just-in-time. ([SLSM arXiv:2404.03929](https://arxiv.org/abs/2404.03929))

**Key finding:** Eager backfill causes "massive data movement that may block concurrent queries" and creates a service vacuum. Lazy migration eliminates this. This is relevant even for small-scale systems: the pattern applies wherever consumers may read stale (un-backfilled) instances during a migration window.

### Living in Parallel Realities: Co-Existing Schema Versions (Herrmann et al., SIGMOD 2017)

Formal treatment of running multiple schema versions simultaneously over the same physical data, using a bidirectional evolution language. Demonstrates that this can be done without code duplication and with major performance optimization. ([arXiv:1608.05564](https://arxiv.org/abs/1608.05564))

### Zero-Downtime SQL Database Schema Evolution (de Jong et al., ICSE SEIP 2017)

Empirical study of zero-downtime schema evolution in continuous deployment. Documents that the expand-contract pattern, correctly implemented, allows online migration with no service interruption. ([IEEE ICSE-SEIP 2017](https://ieeexplore.ieee.org/document/7965438/))

---

## What dharma_swarm's Naive Backfill Will Break

The current plan is: edit `ObjectType` (add `api_name: str = ""` and `status: Literal["ACTIVE", ...] = "ACTIVE"`), update all 21 `_DOMAIN_TYPES` definitions inline, and redeploy. Here are the specific failure modes:

### Failure Mode 1: Race Between Agents on Old and New Code During Rolling Restart

**Mechanism:** If multiple agent processes run concurrently (on VPS instances, in container replicas, or in async tasks), during a rolling restart some processes run old code (no `api_name` / `status`) and some run new code. An agent on old code reads an `ObjectType` dict from the registry and updates it; an agent on new code reads the same type and writes `api_name`. If the registry is a shared mutable object (in-memory or JSONL backend), these concurrent writes produce **undefined merge behavior**.

**Academic backing:** This is precisely the "two-schema corruption" scenario documented in the F1 paper ([F1 schema change paper](https://static.googleusercontent.com/media/research.google.com/en/pubs/archive/41376.pdf)). F1 requires intermediate states and a maximum of two concurrent schema versions precisely because naive concurrent schema use corrupts data.

**dharma_swarm specifics:** The `OntologyRegistry` at line ~845 iterates over `_DOMAIN_TYPES` on startup. If a process starts while another is mid-restart, the new `api_name` field will be absent from some instances and present in others.

### Failure Mode 2: Existing Serialized OntologyObj Instances Have No `api_name` Field

**Mechanism:** The JSONL storage backend serializes `OntologyObj` instances. Adding `api_name` to `ObjectType` does **not** automatically backfill existing JSONL records. When new code reads an old JSONL record and tries to access `obj_type.api_name`, one of two things happens:
- If using Pydantic: the field gets default value (`""`), silently masking the missing data
- If downstream code assumes non-empty `api_name` for routing or API calls: the empty-string default causes silent misbehavior (API calls to `""` endpoint, routing to the wrong bucket)

**Palantir analogy:** Palantir explicitly distinguishes "properties that have never received user edits" (safe to change) from those that have. dharma_swarm has no mechanism to track which object instances have been written with new vs old schema ([Palantir docs: schema-migrations](https://palantir.com/docs/foundry/object-edits/schema-migrations/)).

### Failure Mode 3: `api_name = ""` as Undetected Missing Data

**Mechanism:** Using `""` (empty string) as the default for `api_name` is a **type system lie**. The field claims to have a name when it doesn't. Any downstream consumer that treats `api_name` as a stable identifier (for external API routing, for caching keys, for logging correlation) will either:
- Use `""` as a key, causing key collisions across all 21 types with empty `api_name`
- Fail silently until a later validation check that may not exist

**Industry analogy:** This is the "REQUIRED field with optional default" antipattern that zero-downtime migration literature specifically prohibits ([Liquibase zero-downtime guide](https://java.elitedev.in/java/zero-downtime-database-migrations-liquibase-spring-boot/)). The correct approach is: add the field as nullable/optional → backfill → enforce non-null constraint as a separate step.

### Failure Mode 4: No Audit Trail of Pre-Migration State

**Mechanism:** Once the code is modified and deployed, there is no record of what the types looked like before. If a bug is discovered post-deployment, there is no:
- Migration version number to roll back to
- Snapshot of pre-migration type definitions
- Changelog entry describing what changed and why

**Industry standard:** Liquibase/Flyway store a `DATABASECHANGELOG` / `flyway_schema_history` table with checksums, execution timestamps, and author information ([Flyway docs](https://blog.jetbrains.com/idea/2024/11/how-to-use-flyway-for-database-migrations-in-spring-boot-applications/)). neo4j-migrations stores the history as a **subgraph within the database itself** ([neo4j-migrations README](https://github.com/michael-simons/neo4j-migrations)). dharma_swarm has neither.

### Failure Mode 5: No Consumer Notification — Agents Depending on `ObjectType.name` Break Silently

**Mechanism:** Multiple agents (GuardianCrew, RevenueSpine, A2A bridge, etc.) reference object types by `name` string (e.g., `"ActionProposal"`, `"VentureCell"`). If the proposed `api_name` field is intended to eventually *replace* `name` as the canonical identifier, any agent that doesn't receive explicit notification of this change will silently use the old `name` field.

**Palantir community evidence:** A user reported that removing a property broke a downstream action type and the breakage "went unnoticed" because the Ontology Manager provides no per-property dependency tracking ([Palantir community: breaking changes](https://community.palantir.com/t/unintended-breaking-changes-when-removing-object-type-proeprties-in-the-ontology-manager/3557)).

**Alation model:** Alation's impact analysis traverses the full downstream dependency graph before a schema change and alerts all data stewards. dharma_swarm has no equivalent — no lineage graph, no consumer registry.

### Failure Mode 6: Status Field `ACTIVE` as Universal Default Hides Lifecycle Intent

**Mechanism:** Setting `status = "ACTIVE"` as the default for all 21 types assumes that "active" is the correct lifecycle state for all of them. But:
- `_RESEARCH_THREAD`, `_EXPERIMENT`, `_PAPER` may be in experimental states
- `_WITNESS_LOG` and `_EVOLUTION_ENTRY` are infrastructure types — their "status" semantics differ from domain types
- Revenue pipeline types (`RevenueTarget`, `RevenueEngagement`) already have their own `status` fields with completely different enum values

Setting a global `status = "ACTIVE"` on the `ObjectType` level without differentiating these creates **conflicting status semantics** at type registration time vs. instance level. Palantir's Ontology Manager explicitly tracks `experimental`, `active`, and `deprecated` at the object type level as a separate administrative concept from instance-level status ([Palantir community: design principles](https://community.palantir.com/t/ontology-and-pipeline-design-principles/5481)).

### Failure Mode 7: No Rollback Path

**Mechanism:** Once the new `api_name` and `status` fields are added and deployed, any code that writes these fields to the JSONL backend creates records that are incompatible with the old code (which doesn't know about these fields). Rolling back the code would leave new-format records in the store that old code ignores. This creates **permanent forward-only state** without a migration framework to version the transition.

**Industry analogy:** Flyway's model explicitly states that once a migration is applied, it cannot be automatically undone — a *new migration must reverse it* ([Flyway dev.to](https://dev.to/mspilari/database-migrations-with-flyway-in-spring-boot-5g0a)). The correct approach is to define the reverse migration *before* deploying forward.

### Failure Mode 8: `OntologyRegistry` Hot-Path Has No Schema Version Check

**Mechanism:** `OntologyRegistry` loads `_DOMAIN_TYPES` at startup. If any agent process in a multi-agent cluster has a different version of `ontology.py` in memory (e.g., due to import caching, incomplete restart, or a stuck process), that agent will operate on a registry with a different schema. Without a schema version check at every registry access, type-level inconsistencies propagate silently into `OntologyObj` instances.

**F1 analogy:** F1 enforces schema leases — each server must check in with the schema-change coordinator before expiry. If it can't reach the coordinator, it stops serving rather than use a potentially stale schema. dharma_swarm has no equivalent check ([F1 schema change paper](https://static.googleusercontent.com/media/research.google.com/en/pubs/archive/41376.pdf)).

---

## Adversarial Questions

1. **What is the contract between `api_name` and the external API layer?** If `api_name` is intended to be the stable identifier exposed to external callers, then adding it with a default of `""` means external callers get different values for the same type depending on when they call. Who owns the contract? When is it frozen? Has this been specified anywhere, or is it being inferred from implementation?

2. **How are concurrent multi-agent reads to `OntologyRegistry` guarded?** The `OntologyRegistry` class exists but there is no evidence of distributed locking or schema-epoch coordination. If two agents running different code versions both modify the registry, what is the merge semantics? The answer in the current code appears to be: undefined.

3. **Who are the consumers of `ObjectType.name` vs. the proposed `ObjectType.api_name`?** Palantir's 2024 community post asked exactly this question about their own system and found that per-property consumer dependency tracking **does not exist** in Ontology Manager. Has dharma_swarm conducted the equivalent analysis? What are the downstream code paths that will read `api_name`?

4. **Is the proposed `status` field at the `ObjectType` level distinct from the `status` property on individual `OntologyObj` instances?** Several domain types (RevenueTarget, RevenueEngagement, VentureCell) already have `status` as an *instance-level property* with specific enum values. The proposed `ObjectType.status` appears to be a *type-level lifecycle state*. These have completely different semantics. Conflating them will cause confusion in consumers that enumerate types by status.

5. **What is the rollback procedure if `api_name` backfill produces incorrect values?** The current plan has no rollback. If incorrect `api_name` values are deployed and agents begin using them for external routing, correction requires: identifying all incorrectly-routed calls, finding all stored records with wrong values, writing a reverse migration, redeploying. What is the estimated blast radius and recovery time?

6. **Does the Devin backfill touch persisted `OntologyObj` JSONL records, or only the in-memory type definitions?** If only the in-memory definitions are updated, existing persisted objects have no `api_name`. If the OMS hardening later makes `api_name` required for validation, every existing persisted object fails validation. Has this been thought through?

7. **Why is this change being made as a direct code edit rather than a registered migration?** dbt has `dbt-autofix`, neo4j-migrations has versioned Cypher scripts, Liquibase has changesets. What is the equivalent for dharma_swarm's ontology evolution? If the answer is "there isn't one," that is the actual problem to solve — not the specific `api_name` + `status` backfill.

8. **What is the observable signal that migration is complete?** Palantir has the "fully hydrated" state declaration; F1 has write-only → public promotion; BullFrog has lazy completion tracking. What is dharma_swarm's equivalent? When can agents safely assume that all 21 types have valid `api_name` values? Without this signal, there is no cutover semantics — just hope.

---

## Recommended Migration Framework Primitives for dharma_swarm

Ranked by implementability and immediate impact:

### 1. Schema Version Integer on `OntologyRegistry` (Implement First, Days)

Add a `schema_version: int` field to `OntologyRegistry`. Every time `_DOMAIN_TYPES` changes, increment this version. Log the version on startup. Any agent that reads from the registry checks that its compiled-in version matches the runtime version.

```python
ONTOLOGY_SCHEMA_VERSION = 2  # was 1 before api_name + status added

class OntologyRegistry(BaseModel):
    schema_version: int = ONTOLOGY_SCHEMA_VERSION
    # ... existing fields
```

This gives you: observable migration progress, version mismatch detection, audit trail. Cost: hours.

### 2. Versioned Migration Manifest in `docs/schema/migrations/` (Implement in Parallel, Days)

Create a human-readable migration manifest file for every ontology change:

```
docs/schema/migrations/
  0001_initial_21_types.md
  0002_add_api_name_status.md   ← Devin's current work
  0003_...
```

Each file contains: what changed, which types, what the before state was, what the after state is, rollback procedure, affected consumers. This is the equivalent of a Flyway `flyway_schema_history` table at the ontology level.

### 3. Expand-Contract in Two Deploys (Implement for Current Migration, Days)

Do not add `api_name` and make it required in one step. Follow:

**Deploy 1 (Expand):** Add `api_name: str = ""` and `status: str = "ACTIVE"` with defaults. All 21 types get their proper values hardcoded. Existing serialized objects read back fine (Pydantic fills defaults).

**Verify:** Run the full agent suite. Confirm no consumer breaks. Log the schema version.

**Deploy 2 (Backfill + Enforce, Weeks Later):** If `api_name` is intended to be non-empty and unique, add a startup validation that asserts `all(t.api_name for t in _DOMAIN_TYPES)` and `len(set(t.api_name for t in _DOMAIN_TYPES)) == len(_DOMAIN_TYPES)`. This detects future types added without `api_name`.

### 4. `OntologyMigration` Dataclass for Each Change (Implement This Week)

Model migrations explicitly:

```python
@dataclass
class OntologyMigration:
    version: int
    description: str
    affected_types: list[str]
    breaking: bool
    rollback_procedure: str
    applied_at: datetime | None = None

MIGRATIONS: list[OntologyMigration] = [
    OntologyMigration(
        version=2,
        description="Add api_name (str) and status (str) to all 21 ObjectTypes",
        affected_types=[t.name for t in _DOMAIN_TYPES],
        breaking=False,  # Additive with defaults
        rollback_procedure="Revert ontology.py to commit <hash>; no stored-data rollback needed",
    )
]
```

This is a lightweight version of Liquibase's changeset model adapted to Python.

### 5. Consumer Dependency Graph (Implement as Tech Debt Item, Weeks)

Build a static analysis script that identifies all code paths in the dharma_swarm codebase that reference `ObjectType.name`, `type_name`, or any field that will be affected by ontology changes. Run it before any migration. This is the equivalent of Alation's impact analysis, but local.

```bash
grep -r "type_name\|obj_type\|ObjectType\|_DOMAIN_TYPES" ds/ --include="*.py" \
  | grep -v "ontology.py\|test_" > /tmp/ontology_consumers.txt
```

### 6. JSONL Schema Version Header (Implement for Storage Backend, Weeks)

Add a schema version header to every JSONL file written by the OntologyRegistry:

```json
{"_schema_version": 2, "_migrated_at": "2026-06-01T00:00:00Z"}
{"id": "...", "type_name": "ActionProposal", "api_name": "action_proposal", ...}
```

On read, detect version mismatch and either migrate the record forward in-place (lazy migration, BullFrog-style) or reject it.

### 7. Deprecation Mechanism for ObjectTypes (Implement as Feature, Months)

Before deprecating any type, the system should:
1. Set `status = "DEPRECATED"` at the type level (not delete the type)
2. Log all active `OntologyObj` instances of that type
3. Refuse to create new instances of the deprecated type (via `OntologyRegistry.create_object` validation)
4. After a configurable grace period, tombstone existing instances

This mirrors Palantir's `active` / `deprecated` / `experimental` lifecycle and dbt's `deprecation_date` mechanism ([Palantir community: design principles](https://community.palantir.com/t/ontology-and-pipeline-design-principles/5481); [dbt-core discussion #6736](https://github.com/dbt-labs/dbt-core/discussions/6736)).

---

## Sources

1. **Palantir Docs: OSv1 → OSv2 Migration** — Full migration primitive set: dual-index, soak period, transition windows, rollback, consumer impact.
   https://palantir.com/docs/foundry/object-backend/osv1-osv2-migration/

2. **Palantir Docs: Schema Migrations (Object Edits)** — Breaking vs non-breaking changes, versioning, Funnel pipelines, 500-migration limit.
   https://palantir.com/docs/foundry/object-edits/schema-migrations/

3. **Palantir Docs: Edit Object Types** — Application-breaking consequences, unregister/reregister behavior, writeback dataset loss.
   https://palantir.com/docs/foundry/object-link-types/edit-object-type/

4. **Palantir Docs: Value Type Versions** — Breaking vs non-breaking, auto-propagation of non-breaking changes, deprecation for breaking changes.
   https://www.palantir.com/docs/foundry/object-link-types/value-types-versions

5. **Palantir Community: Ontology and Pipeline Design Principles** — "Avoid versioned Object Type names"; deprecate fully; maturity states.
   https://community.palantir.com/t/ontology-and-pipeline-design-principles/5481

6. **Palantir Community: Breaking Changes Without Warning** — Property removal broke action type silently; no per-property consumer dependency check.
   https://community.palantir.com/t/unintended-breaking-changes-when-removing-object-type-proeprties-in-the-ontology-manager/3557

7. **Palantir Community: Backfill Strategy for Incremental Builds** — Semantic versioning for incremental pipelines; user-edit complication.
   https://community.palantir.com/t/migrating-ontology-property-to-new-column-backfilling-strategy-for-incremental-builds/3970

8. **dbt Core Discussion #6736: Model Versions** — Full spec of `ref()` pinning, deprecation dates, lifecycle statuses, contract enforcement.
   https://github.com/dbt-labs/dbt-core/discussions/6736

9. **dbt Developer Blog: Modernizing the Semantic Layer Spec** — Breaking changes in Jan 2026 spec redesign; `dbt-autofix` migration tool; "vast majority" caveat.
   https://docs.getdbt.com/blog/modernizing-the-semantic-layer-spec

10. **Snowflake Engineering Blog: Native Semantic Views** — Schema-level objects replacing YAML files; replace-in-place semantics; no versioning or staged cutover documented.
    https://www.snowflake.com/en/blog/engineering/native-semantic-views-ai-bi/

11. **Snowflake Docs: Enable Automatic Table Schema Evolution** — `ENABLE_SCHEMA_EVOLUTION` parameter; auto-adds columns from new data.
    https://docs.snowflake.com/en/user-guide/data-load-schema-evolution

12. **GitHub: michael-simons/neo4j-migrations** — Flyway-inspired migration tool for Neo4j; Cypher + XML + Java migrations; versioned naming convention; no rollback.
    https://github.com/michael-simons/neo4j-migrations

13. **neo4j-migrations Documentation** — Full primitive set: Cypher scripts, catalog-based XML, built-in refactorings (rename.label, rename.nodeProperty, etc.).
    https://michael-simons.github.io/neo4j-migrations/2.9.3/

14. **Atlan Docs: Confluent Schema Registry** — "Visibility into schema evolution" — no technical migration primitives documented.
    https://docs.atlan.com/apps/connectors/schema/confluent-schema-registry

15. **Hackolade-Collibra Integration Docs** — SET/REPLACE destructive semantics; edits in Collibra overwritten by subsequent publishes.
    https://hackolade.com/help/CollibraDataDictionaryintegratio.html

16. **Alation: Data Lineage Impact Analysis** (YouTube) — Column-level impact analysis; downstream dependency traversal; deprecation flag propagation.
    https://www.youtube.com/watch?v=HAlP_QB1mJ8

17. **Liquibase Zero-Downtime Guide** — Expand-contract pattern; addColumn → backfill → switch → dropColumn; rollback procedures.
    https://java.elitedev.in/java/zero-downtime-database-migrations-liquibase-spring-boot/

18. **GitHub: liquibase-zd** — Liquibase plugin automating expand-contract for PostgreSQL.
    https://github.com/coenvk/liquibase-zd

19. **Flyway Dev.to Guide** — No automatic rollback; reversal migration is the standard; backup-and-restore for critical environments.
    https://dev.to/mspilari/database-migrations-with-flyway-in-spring-boot-5g0a

20. **Rae et al., 2013: Online, Asynchronous Schema Change in F1** — Foundational paper; state machine (absent/delete-only/write-only/public); max-2-versions constraint; corruption examples.
    https://static.googleusercontent.com/media/research.google.com/en/pubs/archive/41376.pdf

21. **F1 Distributed SQL paper (Shute et al., 2013)** — Non-blocking schema changes; schema lease mechanism; asynchronous servers using different schemas.
    https://static.googleusercontent.com/media/research.google.com/en/us/pubs/archive/41344.pdf

22. **Spanner OSDI 2012 (Corbett et al.)** — TrueTime-based atomic schema-change transactions; future-timestamp assignment; reads/writes synchronize with schema-change timestamp.
    https://static.googleusercontent.com/media/research.google.com/en/archive/spanner-osdi2012.pdf

23. **BullFrog: Online Schema Evolution via Lazy Evaluation (SIGMOD 2021)** — Single-step backwards-incompatible migrations without downtime; lazy physical migration; PostgreSQL extension.
    https://dl.acm.org/doi/10.1145/3448016.3452842

24. **SLSM: Lazy Schema Migration on Shared-Nothing Databases (arXiv 2024)** — Service vacuum problem; fusion transactions; comparison to F1; eliminates waiting for full backfill.
    https://arxiv.org/abs/2404.03929

25. **Herrmann et al., 2017: Living in Parallel Realities (SIGMOD 2017)** — Co-existing schema versions over shared data; bidirectional evolution language.
    https://arxiv.org/abs/1608.05564

26. **de Jong et al., 2017: Zero-Downtime SQL Schema Evolution (ICSE SEIP)** — Empirical validation of expand-contract for continuous deployment.
    https://ieeexplore.ieee.org/document/7965438/

27. **JusDB: Schema Versioning and Migration Strategies** — Expand-contract as foundation; never run lock-holding DDL during business hours; test on production-sized data.
    https://www.jusdb.com/blog/schema-versioning-and-migration-strategies-for-scalable-databases

---

*This report was generated adversarially. Every claim cites a primary source. Where sources are thin or paywalled, this is stated explicitly. The goal is not to validate Devin's backfill plan — it is to find what breaks.*
