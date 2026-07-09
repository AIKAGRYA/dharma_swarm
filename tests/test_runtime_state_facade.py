"""Guard the runtime_state package facade (item 6a mechanical decomposition).

The former flat ``dharma_swarm/runtime_state.py`` (4111 lines, 100+ importers)
was split into a ``runtime_state/`` package with a backward-compatible facade.
These tests fail loudly if the facade regresses: a missing re-export, a
duplicated dataclass definition across submodules, or a submodule that no
longer imports. They assert *behaviour of the public surface*, not a mock.
"""

from __future__ import annotations

import importlib

import pytest

import dharma_swarm.runtime_state as rs

# The complete public + private surface the old flat module exposed. Captured
# from the pre-split module namespace; the facade must re-export every one of
# these unchanged (a half-built facade drops at least one and fails here).
EXPECTED_SURFACE = [
    'Any', 'ArtifactRecord', 'ContextBundleRecord', 'DEFAULT_RUNTIME_DB',
    'DelegationRun', 'ExecutionIdentity', 'IdempotencyRecord', 'MAPPING_IDENTITY_FIELDS',
    'MAPPING_ID_KINDS', 'MemoryEdge', 'MemoryFact', 'MissingExecutionIdentity',
    'OperatorAction', 'Path', 'RUNTIME_RECEIPT_TYPES', 'RuntimeReceipt',
    'RuntimeStateStore', 'SELF_MOD_RECEIPT_TYPES', 'SessionEventRecord', 'SessionState',
    'TaskClaim', 'TopologyStateRecord', 'WorkspaceLease', '_ARTIFACT_LINKS_DDL',
    '_ARTIFACT_RECORDS_DDL', '_BUSY_TIMEOUT_MS', '_CONTEXT_BUNDLES_DDL', '_DELEGATION_RUNS_DDL',
    '_EXECUTION_IDENTITIES_DDL', '_EXECUTION_IDENTITY_CONFLICT_FIELDS', '_IDEMPOTENCY_RECORDS_DDL', '_INDEXES',
    '_MEMORY_EDGES_DDL', '_MEMORY_FACTS_DDL', '_OPERATOR_ACTIONS_DDL', '_RUNTIME_RECEIPTS_DDL',
    '_SESSIONS_DDL', '_SESSION_EVENTS_DDL', '_SESSION_EVENTS_FTS_DDL', '_TASK_CLAIMS_DDL',
    '_TOPOLOGY_STATES_DDL', '_WORKSPACE_LEASES_DDL', '_apply_connection_pragmas_async', '_apply_connection_pragmas_sync',
    '_execution_identity_conflicts', '_flatten_search_text', '_fts_query', '_identity_from_metadata',
    '_json_dump', '_json_load', '_ledger_record_event_id', '_legacy_no_identity_metadata',
    '_merge_idempotency_metadata', '_metadata_with_identity', '_new_id', '_operation_hash',
    '_parse_dt', '_raise_on_execution_identity_conflict', '_require_identity_match', '_required_identity_from_metadata',
    '_row_to_artifact', '_row_to_claim', '_row_to_context_bundle', '_row_to_execution_identity',
    '_row_to_idempotency_record', '_row_to_lease', '_row_to_memory_fact', '_row_to_operator_action',
    '_row_to_run', '_row_to_runtime_receipt', '_row_to_session', '_row_to_session_event',
    '_row_to_topology_state', '_session_event_summary', '_trace_from_metadata', '_utc_now',
    '_utc_now_iso', 'aiosqlite', 'build_session_event_from_ledger_record', 'dataclass',
    'datetime', 'ensure_memory_plane_schema_async', 'ensure_memory_plane_schema_sync', 'ensure_runtime_state_schema_async',
    'ensure_runtime_state_schema_sync', 'field', 'get_correlation', 'hashlib',
    'json', 're', 'replace', 'sqlite3',
    'timezone', 'uuid4',
]

SUBMODULES = ["models", "schema", "_rows", "_identity", "_util", "store"]


def test_runtime_state_is_a_package() -> None:
    # A package has __path__; the old flat module did not. This is the
    # structural fact the decomposition establishes.
    assert hasattr(rs, "__path__"), "runtime_state must be a package after 6a"


@pytest.mark.parametrize("submodule", SUBMODULES)
def test_every_submodule_imports(submodule: str) -> None:
    mod = importlib.import_module(f"dharma_swarm.runtime_state.{submodule}")
    assert mod is not None


@pytest.mark.parametrize("name", EXPECTED_SURFACE)
def test_facade_reexports_full_surface(name: str) -> None:
    assert hasattr(rs, name), f"facade dropped re-export of {name!r}"


def test_no_duplicate_dataclass_definitions() -> None:
    # The facade name must be the *same object* as the one defined in its
    # owning submodule -- proves the split did not fork a second definition
    # (which would silently break isinstance() across import paths).
    from dharma_swarm.runtime_state import models, store

    assert rs.SessionState is models.SessionState
    assert rs.DelegationRun is models.DelegationRun
    assert rs.RuntimeReceipt is models.RuntimeReceipt
    assert rs.RuntimeStateStore is store.RuntimeStateStore
    assert rs.ensure_runtime_state_schema_sync is (
        importlib.import_module("dharma_swarm.runtime_state.schema")
        .ensure_runtime_state_schema_sync
    )


@pytest.mark.asyncio
async def test_store_roundtrip_through_facade(tmp_path) -> None:
    # End-to-end: a write+read through the facade-imported store exercises
    # store.py -> _rows.py -> models.py -> _util.py wiring in one path.
    store = rs.RuntimeStateStore(tmp_path / "runtime.db")
    await store.init_db()
    run = rs.DelegationRun(
        run_id=rs._new_id("run"), task_id="t1", assigned_to="agent-x"
    )
    saved = await store.record_delegation_run(run)
    assert isinstance(saved, rs.DelegationRun)
    got = await store.get_delegation_run(run.run_id)
    assert got is not None
    assert got.task_id == "t1"
    assert got.assigned_to == "agent-x"


def test_build_session_event_helper_through_facade() -> None:
    event = rs.build_session_event_from_ledger_record(
        session_id="sess-1",
        ledger_kind="task",
        record={"event": "task_started", "task_id": "t1"},
    )
    assert isinstance(event, rs.SessionEventRecord)
    assert event.event_name == "task_started"
    assert event.task_id == "t1"
