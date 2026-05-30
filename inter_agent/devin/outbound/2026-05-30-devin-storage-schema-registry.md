# Devin Outbound — PR-H4 Storage Schema Registry (scaffold)

**From:** Devin (Roaming) `AGT-DEVIN_ROAMING_2987D222`
**Authority:** `external_worker_evidence_only`
**Date:** 2026-05-30
**Branch:** `devin/2026-05-30-storage-schema-registry` (sibling to main, independent of PR #384 / #388 / #389)
**Active track:** `runtime-truth-spine-2026-06` — not displaced.
**Frozen surfaces touched:** none.
**Existing files modified:** none.

## Scope decision

The audit counted 526 JSONL + 56 SQLite + 159 raw JSON files across the repo with no shared schema, version tag, or migration story. After explicit operator decision ("Scaffold-only (safe)"), this PR delivers the **contract** that makes piecewise storage unification safe, without touching any existing storage code or operator data on disk.

## What landed

1. `dharma_swarm/storage_schema_registry.py` (414 LOC, pure stdlib)
   - `SchemaDescriptor` frozen dataclass (schema_id, version, cls, owner_module, migrations, notes)
   - `SCHEMA_REGISTRY: dict[str, SchemaDescriptor]` — opt-in registry, starts empty
   - `@register_schema(schema_id, *, version, migrations, notes)` — dataclass decorator (requires `is_dataclass(cls)`, validates id/version)
   - `write_jsonl_versioned(path, records, *, schema_id, append)` — embeds `__schema_id__` and `__schema_version__` markers
   - `read_jsonl_versioned(path, *, expected_schema_id, auto_migrate, strict)` — strips markers; validates id; applies migration chain
   - `get_schema`, `registered_schema_ids`, `clear_registry_for_tests`, `render_registry_summary`
   - Custom exceptions: `SchemaRegistryError`, `SchemaAlreadyRegisteredError`, `SchemaVersionMismatchError`, `UnknownSchemaError`

2. `tests/test_storage_schema_registry.py` (314 LOC, **22 tests, all passing**)
   - Decorator semantics (dataclass-required, duplicate-rejection, empty/whitespace/version validation)
   - Round-trip preservation
   - Reserved-key collision rejection
   - Append mode
   - Strict / non-strict reads
   - `expected_schema_id` mismatch
   - Version mismatch raises when `auto_migrate=False`
   - Migration chain composes when `auto_migrate=True`
   - Missing-step migration raises clearly
   - Registry isolation between tests via autouse fixture

3. `docs/reports/storage_schema_registry_migration_plan.md` — piecewise plan H4a (ClosureEvidenceReceipt first) → H4b (spine EvidenceReceipt) → H4c–H4n (telemetry, routing, retrospective, cost, conversation/artifact/graph/vector stores) → H4-checker (manifest invariant) → H4-migrate (operator-gated, dry-run-default disk migration).

## What did NOT happen (deliberate)

- No existing storage code modified.
- No record type registered yet. `SCHEMA_REGISTRY` is empty until a follow-up PR adopts the decorator.
- No data on disk touched.
- No new dependencies. Pure stdlib (`json`, `pathlib`, `dataclasses`, `typing`).

## Why this is still "moving the needle"

The hard part of storage unification isn't the package — it's the migrations and the cutover. The registry contract decided **now**:
- Every persistent record has a stable string id.
- Every record carries its schema_id + version at rest.
- Migrations are explicit dicts of callables, composable into chains.
- Auto-migration is opt-in per call site (default off → loud failures over silent corruption).
- Reserved keys (`__schema_id__`, `__schema_version__`) are validated at write time.

Future H4 PRs are now mechanical: decorate one dataclass, write one migration callable per version step, prove round-trip, move on. Without this contract, every storage PR has to re-invent the same shape under deadline pressure.

It also enables future manifest invariants (declared schemas must be registered, all serialized dataclasses must be registered, JSONL paths go through `dharma_state_dir()` and not raw literals) which collectively drive the storage_dir_literals budget toward zero.

## Anti-doctrine self-check

- Builds AGI? No.
- Uncontrolled self-modification? No.
- Autonomous capital deployment? No.
- Autonomous external messaging? No.
- Deceptive memetic engineering? No.
- Parallel governance? No — existing storage code remains authoritative.
- Vague prose? No — 22 tests, exact decorator/migration semantics.
- New substrate? **No.** One module, one dict, one decorator, two I/O wrappers.
- Meta-framework? **No.**
- Forced opt-in? **No.** Records without `@register_schema` keep working.
- Touches frozen surfaces? **No.**

## Rollback

`rm dharma_swarm/storage_schema_registry.py tests/test_storage_schema_registry.py`. Zero blast radius.

## Follow-up sequence

- **PR-H4a:** opt in `ClosureEvidenceReceipt` (cleanest candidate; one write site)
- **PR-H4b:** opt in spine `EvidenceReceipt` (operator decision required — frozen surface)
- **PR-H4c–H4n:** telemetry, routing, retrospective, cost, conversation/artifact/graph/vector stores (one PR per cluster)
- **PR-H4-checker:** add manifest_check rule that `persistent_schemas:` entries resolve in the registry
- **PR-H4-migrate:** operator-gated, dry-run-default `tools/migrate_storage.py` that re-writes JSONL files using `auto_migrate=True`. ONLY PR that touches operator disk.

Authority compliance: this notice + open PR + await operator merge. No autonomous merge.
