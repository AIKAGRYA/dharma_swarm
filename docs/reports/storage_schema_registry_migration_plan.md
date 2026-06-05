# Storage Schema Registry Migration Plan (PR-H4 scaffold → PR-H4a/H4b/...)

**Status:** scaffold landed; piecewise migration pending.
**Doctrine posture:** zero new substrate, additive only.

## What landed in PR-H4 (scaffold)

`dharma_swarm/storage_schema_registry.py` (414 LOC, pure stdlib):

- `SchemaDescriptor` — frozen dataclass: schema_id, version, cls, owner_module, migrations, notes
- `SCHEMA_REGISTRY: dict[str, SchemaDescriptor]` — opt-in registry, starts empty
- `@register_schema(schema_id, *, version, migrations, notes)` — dataclass decorator
- `write_jsonl_versioned(path, records, *, schema_id, append)` — embeds `__schema_id__` and `__schema_version__` markers; rejects unknown schemas
- `read_jsonl_versioned(path, *, expected_schema_id, auto_migrate, strict)` — strips markers; validates id; applies migration chain when `auto_migrate=True`; raises `UnknownSchemaError`/`SchemaVersionMismatchError` otherwise
- `get_schema()`, `registered_schema_ids()`, `clear_registry_for_tests()`, `render_registry_summary()`
- Custom exceptions: `SchemaRegistryError`, `SchemaAlreadyRegisteredError`, `SchemaVersionMismatchError`, `UnknownSchemaError`

`tests/test_storage_schema_registry.py` (314 LOC, 22 tests, all passing) — verifies decorator semantics, round-trip, migration chain, append mode, strict/non-strict reads, version mismatch detection.

**No existing storage code is modified.** The 526 JSONL writes, 56 SQLite stores, 159 raw JSON dumps remain on their current code paths.

## Why scaffold-only first

Unifying storage means touching ~600 write sites across the repo and the data on every operator's disk. The hard part is **migrations**, not the package layout. The registry contract gives every future migration PR a stable target: opt one record type in, write its migration callables, prove round-trip, move on.

## The piecewise plan

### PR-H4a — opt in `ClosureEvidenceReceipt` (the simplest record)

After PR-H1 lands, `ClosureEvidenceReceipt` is a clean candidate:
- It's a frozen dataclass already.
- It has exactly one write site (`record_evidence_receipt()`).
- It already round-trips through `to_jsonable()` + `write_json()` / `read_json()` in `closure_v0.py`.

The PR-H4a change:
- Decorate the class: `@register_schema("closure_v0.ClosureEvidenceReceipt", version=1)` above the existing `@dataclass(frozen=True)`.
- Update `write_json` / `read_json` callers to use `write_jsonl_versioned` / `read_jsonl_versioned` **only at the closure_v0 boundary**. (Or keep the existing JSON path and just claim the schema_id reservation; the choice is the PR's call.)

Tiny PR, validates the contract on a real record.

### PR-H4b — opt in `EvidenceReceipt` (the spine runtime receipt)

Same pattern. Note: `spine/receipt.py` is a frozen surface. Opting it in requires either:
- An operator-blessed unfreezing of just the decorator addition (one line above the class), or
- A wrapper module elsewhere that re-imports + decorates without touching the frozen file.

Defer the decision to the operator.

### PR-H4c–H4n — opt in remaining record types one PR per cluster

Cluster by owner module:
1. `telemetry_plane.py` — `EconomicEventRecord`, `ExternalOutcomeRecord`, `PolicyDecisionRecord`, `RoutingDecisionRecord`
2. `routing_memory.py` — task signature records
3. `router_retrospective.py` — `RouteOutcomeRecord`
4. `cost_tracker.py` — cost records
5. Conversation/artifact/graph/vector stores — each its own PR
6. Random one-off JSONL writers in scripts/ — lowest priority

After each PR: `registered_schema_ids()` grows; all tests pass; storage behavior identical (markers embedded, but the data is still the same).

### PR-H4-checker — manifest invariant: declared schemas must be registered

Add a check to `tools/manifest_check.py`:
- New manifest section: `persistent_schemas: [{schema_id, owner_module, version}]`.
- Check 6: every declared schema_id resolves in `SCHEMA_REGISTRY` at import time, and the registered version matches the manifest.

This catches the case where someone bumps a schema version without updating the manifest, or vice versa.

### PR-H4-migrate — actual data migration (operator-gated)

Once enough records are registered, write a `tools/migrate_storage.py` that:
- Walks `dharma_state_dir() / "**/*.jsonl"`.
- For files matching known schemas (by path prefix convention), reads with `auto_migrate=True` and re-writes the migrated version.
- Dry-run mode (default), `--apply` mode for actual writes.

This is the only PR in the chain that touches **operator data on disk**. Operator-gated, dry-run-default, reversible via JSONL backup.

## Manifest invariants this enables

Future additions to `tools/manifest_check.py`:

- **Check 6:** every entry in `persistent_schemas:` resolves in `SCHEMA_REGISTRY`. Catches missing imports.
- **Check 7:** every JSONL written by `write_jsonl_versioned` is under `dharma_state_dir()` and not a raw `~/.dharma/...` literal. Drives the `state_dir_literals` budget toward zero.
- **Check 8:** every `@dataclass` in `dharma_swarm/*.py` that's serialized to disk (heuristic: writes through `json.dump` or `path.write_text(json.dumps(...))`) must be decorated with `@register_schema`. Drives accidental ad-hoc records toward the registry.

## Anti-doctrine self-check

- New substrate? **No.** One module of data + helpers.
- Meta-framework? **No.** One decorator, two I/O wrappers around `json.dump` / `json.loads`.
- Parallel governance? **No.** Existing storage code is authoritative until opted in.
- Forced opt-in? **No.** Records without `@register_schema` keep working.
- Touches frozen surfaces? **No.** `spine/**`, `orchestrator.py`, `agent_runner.py`, `runtime_state.py` unchanged.

## Rollback

`rm dharma_swarm/storage_schema_registry.py tests/test_storage_schema_registry.py`. Zero blast radius.

## Why ratchet is safer than rewrite

Past attempts at "storage unification" PRs tend to die in code review because they're sprawling — they need to migrate 100+ sites and the data on every operator's disk simultaneously. Each migration PR in this plan is small enough to read in 10 minutes and verify against round-trip tests. The aggregate is large; each step is small.
