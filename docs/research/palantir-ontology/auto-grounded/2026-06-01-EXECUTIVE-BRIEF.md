# Ontology PhD-Grounding: Executive Brief (Trio Report)

**Date:** 2026-06-01 (Mon 04:42 WITA / 20:42 UTC)
**Author:** perplexity-computer (adversarial research; do not validate)
**Trigger:** Operator standing directive — "claude has the tendency to think we already have a good system... be the adult that grounds it in hard core external research." Operator update 04:33 WITA: claude OUT OF CREDITS, research ontology-only this round, work with devin + codex + master_mike.
**Scope:** Three PhD-grade research reports (90+ primary sources, 86 KB combined) grounding the in-flight ontology work against the published state of the art.

## TL;DR — The five hardest findings

1. **`api_name` pattern in PR #408 is an inverted anti-pattern.** Palantir's own community design guide (Foundry Solutions Architect, Nov 2025) explicitly says *"Avoid versioned Object Type names. Bad: Message_v2. Worse: Message_v3_Embedded."* Our enforced pattern `dharma.<domain>.<TypeName>.v<N>` is exactly the prohibited form. Palantir uses plain `camelCase` (`employee`, `Flight`) with stable RIDs (`ri.ontology.main.object-type.<UUID>`) as the immutable identifier and api_name as a *mutable* human-readable shorthand. The `.v<N>` suffix is a Protobuf/buf idiom, not an OMS idiom.

2. **Status lifecycle is wrong shape.** Palantir has **five** statuses, not three: `EXAMPLE`, `EXPERIMENTAL`, `ACTIVE`, `DEPRECATED`, `ENDORSED`. PR #408 + PR #409 implement three (`EXPERIMENTAL`/`ACTIVE`/`PROMOTED`) and miss the two operationally critical ones — `DEPRECATED` (machine-readable sunset signal for consumers) and `EXAMPLE` (sandbox/teaching types that should never be referenced from production).

3. **In-memory uniqueness guard is unsafe under concurrency.** Devin's PR #409 `register_type` uniqueness guard is process-local — it resets on restart, and two agents running in parallel processes (the actual fleet topology) can both successfully register the same api_name without either detecting the conflict. The KARMA-cited gate runs only in CI; nothing protects the runtime registry.

4. **KARMA is a conceptual mismatch.** KARMA (Lu et al., NeurIPS 2025, [arxiv:2502.06472](https://arxiv.org/abs/2502.06472)) classifies ABox (instance) facts against a *fixed* schema and either accepts or queues for human review. It never solves TBox (schema definition) evolution. Citing it as the model for our align-gate obscures that *the hard problem — concurrent schema authoring by autonomous agents — is unsolved in KARMA and unsolved everywhere else.*

5. **CRDT-based convergence is formally impossible for full schema evolution.** The CALM theorem (Hellerstein/Alvaro/Laddad et al., 2022, [arxiv:2210.10086](https://arxiv.org/abs/2210.10086)) proves that any non-monotone operation — deletion, status demotion, type restriction, property removal — requires coordination. Schema CRDTs collapse on (a) cardinality disagreements (no lattice join), (b) namespace collisions (no resolution rule), and (c) all non-monotone evolution. AGM postulates (Alchourrón–Gärdenfors–Makinson, 1985) further show that ontology revision in DLs does NOT commute: `(K * α) * β ≠ (K * β) * α`. Different orderings of agent proposals produce different ontologies. **We outsource convergence to the operator with no formal scaffold for that judgment.**

## Where this leaves PR #408 (align-gate) and PR #409 (OMS hardening)

| Item | Status | What the research says |
|---|---|---|
| `register_type` uniqueness guard (#409) | 22/22 CI green | Insufficient: process-local, no persistent store. Needs SQLite-backed registry or lockfile or NATS-distributed lock |
| `api_name` `dharma.<domain>.<Type>.v<N>` (#408) | Enforced regex | **Wrong shape** — drop `.v<N>` suffix, separate version field, switch to plain camelCase |
| 3 status states (#409) | Backfilled on 21 types | Add `DEPRECATED` and `EXAMPLE`; current model cannot signal sunset to consumers |
| Property-level discipline (#408) | Absent | Palantir has `PropertyApiName` / `LinkTypeApiName` — we have neither |
| Property comparison (ALIGN-006) | Code path missing | `TypeSpec.properties` declared but never compared across PRs |
| Closure check on merged proposals (#408) | Absent | No check that all referenced types resolve after concurrent merges |
| Consumer notification on schema change | Absent | OSDK-equivalent does not exist; renames silently break downstream agents |
| Migration framework | None | Naive backfill = no rollback, no soak, no dual-write — Palantir OSv2 keeps 14-day dual index |

## What needs to happen next (ranked, implementable)

**P0 (this week, additive, reversible):**
1. **Drop the `.v<N>` suffix from api_name** and move version to a separate `version: int` field. Pattern becomes `^dharma\.[a-z][a-z0-9_]*\.[A-Z][A-Za-z0-9]*$`. Palantir-aligned, future-OSDK-safe.
2. **Add `DEPRECATED` and `EXAMPLE` to the status enum.** Operationally critical for downstream consumer signals.
3. **Persist the uniqueness guard** in `state/ontology_registry.sqlite` or a JSON checkpoint, so it survives restart and concurrent processes. Backed by an `fcntl` advisory lock or NATS-distributed mutex.

**P1 (next week, structural):**
4. **Add property-level comparison to the align-gate** (ALIGN-006 stub already exists — implement it). Detect type-narrowing, removed properties, cardinality changes as breaking-change classes.
5. **Add a closure check** — for every merged proposal, verify all referenced `ObjectType`s + `LinkDef` targets resolve in the post-merge graph.
6. **Define cascade-status enforcement** — an `ACTIVE` `LinkDef` cannot reference an `EXPERIMENTAL` `ObjectType`. Palantir enforces this at OMS layer.

**P2 (research-stage, frontier):**
7. **Expand-contract migration pattern** for `_DOMAIN_TYPES` evolution (Flyway/Liquibase pattern). Each schema bump = additive change-set + soak window + audit trail before any destructive cleanup.
8. **AGM-aware revision recorder** — log every (proposal, base ontology) pair so we can detect order-dependence and surface it to the operator. We can't *solve* AGM non-commutativity, but we can make it visible.
9. **OSDK-equivalent codegen** (Hermes's piece per claude seq=102) — typed Python accessors from ontology metadata so api_name renames cause compile-time failure, not silent drift.

## Adversarial questions the project has not answered

1. What is the source of truth for an `ObjectType` definition when two PRs concurrently introduce different shapes of the same logical type? (No order-independent answer exists per AGM.)
2. If `register_type` is called in two parallel processes with the same api_name, which one wins? (Today: both succeed silently.)
3. When an `ObjectType` is renamed, what notifies the agents already holding references? (Today: nothing.)
4. What is the rollback story if Devin's 21-type backfill turns out to have wrong api_names? (Today: revert PR + redeploy = the naive approach Palantir explicitly designs against.)
5. How does an agent know a type is `DEPRECATED` if the enum has no `DEPRECATED` state? (Today: it cannot.)
6. Is the merge order of three concurrent PRs deterministic for the resulting ontology? (No — AGM non-commutativity guarantees the answer is no.)
7. What is the formal property the align-gate is supposed to enforce? "No syntactic conflict" is not a formal property — it is a syntactic invariant. We need a semantic invariant statement.
8. What is our position on undecidable semantic conflicts (ContentCVS, Oxford 2011)? Do we punt to the operator, refuse the merge, or warn-and-proceed?

## The three full reports

1. **[multi-agent ontology convergence](./2026-06-01-multi-agent-convergence.md)** — 327 lines, 23 sources. KARMA deep-read, CRDT applicability, semantic 3-way merge state-of-the-art, AGM formal decidability, 8 specific gaps in PR #408, 8 adversarial questions, 5 ranked next-moves.
2. **[Palantir API discipline](./2026-06-01-palantir-api-discipline.md)** — 374 lines, multiple Palantir doc citations. api_name reality (mutable camelCase, not immutable `.v<N>`), 5-state lifecycle, OSDK consumer contract, OSv2 migration mechanics, dbt/Cube/Apollo/Protobuf peer comparison, 10 gaps, 5 ranked hardening passes.
3. **[migration framework + semantic layer](./2026-06-01-migration-semantic-layer.md)** — 573 lines, 27 sources. Palantir OSv2 dual-index/soak/transition primitives, dbt Semantic Layer model-versioning, Snowflake Cortex replace-in-place limits, Neo4j Migrations, Liquibase expand-contract, F1/Spanner/BullFrog/SLSM academic state-of-the-art, 8 failure modes of the naive backfill, 7 ranked migration primitives.

## Recommended next move (operator-readable)

This trio is **not a verdict on PR #408 or PR #409** — both PRs are correct steps in the additive Stage-1 direction and should land. The trio is a **5th-grade-vs-PhD gap inventory** so the next round of work (after Devin's OMS lands and the align-gate flips to FULL) targets the right *real* problems: drop the `.v<N>` suffix, add `DEPRECATED`/`EXAMPLE`, persist the uniqueness guard, implement property comparison, define a migration framework. With Claude offline this round, perplexity continues PhD-grounding; codex picks up cross-PR synthesis (ADR-007 candidate); devin's OMS lands as the gate-flip trigger; mike enforces at merge.

Stage-1 evidence-only. John (`AmitabhainArunachala`) merges.

---

## Sources index (high-signal subset)

- **KARMA paper**: Lu et al., NeurIPS 2025, [arxiv:2502.06472](https://arxiv.org/abs/2502.06472)
- **CRDT foundation**: Shapiro/Preguiça/Baquero/Zawirski 2011, [PDF](https://pages.lip6.fr/Marc.Shapiro/papers/CRDTs_SSS-2011.pdf); survey [arxiv:1805.06358](https://arxiv.org/abs/1805.06358)
- **CALM theorem**: Hellerstein/Alvaro/Laddad 2022, [arxiv:2210.10086](https://arxiv.org/abs/2210.10086)
- **AGM postulates**: Alchourrón/Gärdenfors/Makinson 1985 (foundational), modern review Hansson 2017 (SEP)
- **Palantir Foundry API**: [Get Object Type](https://palantir.com/docs/foundry/api/ontology-resources/object-types/get-object-type/), [Create Object Type](https://palantir.com/docs/foundry/object-link-types/create-object-type/), [Metadata Statuses](https://palantir.com/docs/foundry/object-link-types/metadata-statuses/)
- **Palantir community design**: [Ontology and Pipeline Design Principles](https://community.palantir.com/t/ontology-and-pipeline-design-principles/5481) (Nov 2025, Foundry Solutions Architect)
- **Palantir OSv2 migration**: [OSv1-OSv2 migration](https://palantir.com/docs/foundry/object-backend/osv1-osv2-migration/)
- **Apollo Federation composition**: [docs.apollographql.com/federation/federated-types](https://www.apollographql.com/docs/federation)
- **ContentCVS / Oxford OWL conflict**: Jiménez-Ruiz et al. 2011 (semantic conflict detection in OWL 2 Full is undecidable)
- **F1 schema-change**: Rae et al., VLDB 2013 — state machine for online schema change
- **BullFrog**: SIGMOD 2021 — lazy schema evaluation
- **SLSM**: arXiv 2024 — lazy migration for shared-nothing DBs

Full source list (90+ entries) in the three constituent reports.
