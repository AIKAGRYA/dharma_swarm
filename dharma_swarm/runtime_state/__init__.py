"""Backward-compatible facade for the runtime_state package.

Mechanical decomposition of the former ``dharma_swarm/runtime_state.py`` (item
6a): the module became a package split into ``models`` / ``schema`` / ``_rows``
/ ``_identity`` / ``_util`` / ``store``. This facade re-exports every name that
was importable from the old flat module, unchanged, so all 100+ importers keep
working with zero call-site edits.
"""

from __future__ import annotations

# Preserve the exact external module-level bindings the old flat module exposed
# (so `from dharma_swarm.runtime_state import <stdlib/dharma name>` still works).
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiosqlite

from dharma_swarm.correlation_context import get_correlation
from dharma_swarm.engine.event_memory import (
    ensure_memory_plane_schema_async,
    ensure_memory_plane_schema_sync,
)
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity

from ._util import (
    _fts_query,
    _json_dump,
    _json_load,
    _new_id,
    _parse_dt,
    _utc_now,
    _utc_now_iso,
)
from .models import (
    MAPPING_ID_KINDS,
    MAPPING_IDENTITY_FIELDS,
    RUNTIME_RECEIPT_TYPES,
    SELF_MOD_RECEIPT_TYPES,
    ArtifactRecord,
    ContextBundleRecord,
    DelegationRun,
    IdempotencyRecord,
    MemoryEdge,
    MemoryFact,
    OperatorAction,
    RuntimeReceipt,
    SessionEventRecord,
    SessionState,
    TaskClaim,
    TopologyStateRecord,
    WorkspaceLease,
    _EXECUTION_IDENTITY_CONFLICT_FIELDS,
)
from .schema import (
    DEFAULT_RUNTIME_DB,
    _ARTIFACT_LINKS_DDL,
    _ARTIFACT_RECORDS_DDL,
    _BUSY_TIMEOUT_MS,
    _CONTEXT_BUNDLES_DDL,
    _DELEGATION_RUNS_DDL,
    _EXECUTION_IDENTITIES_DDL,
    _IDEMPOTENCY_RECORDS_DDL,
    _INDEXES,
    _MEMORY_EDGES_DDL,
    _MEMORY_FACTS_DDL,
    _OPERATOR_ACTIONS_DDL,
    _RUNTIME_RECEIPTS_DDL,
    _SESSION_EVENTS_DDL,
    _SESSION_EVENTS_FTS_DDL,
    _SESSIONS_DDL,
    _TASK_CLAIMS_DDL,
    _TOPOLOGY_STATES_DDL,
    _WORKSPACE_LEASES_DDL,
    _apply_connection_pragmas_async,
    _apply_connection_pragmas_sync,
    ensure_runtime_state_schema_async,
    ensure_runtime_state_schema_sync,
)
from ._rows import (
    _flatten_search_text,
    _ledger_record_event_id,
    _row_to_artifact,
    _row_to_claim,
    _row_to_context_bundle,
    _row_to_execution_identity,
    _row_to_idempotency_record,
    _row_to_lease,
    _row_to_memory_fact,
    _row_to_operator_action,
    _row_to_run,
    _row_to_runtime_receipt,
    _row_to_session,
    _row_to_session_event,
    _row_to_topology_state,
    _session_event_summary,
    build_session_event_from_ledger_record,
)
from ._identity import (
    _execution_identity_conflicts,
    _identity_from_metadata,
    _legacy_no_identity_metadata,
    _merge_idempotency_metadata,
    _metadata_with_identity,
    _operation_hash,
    _raise_on_execution_identity_conflict,
    _require_identity_match,
    _required_identity_from_metadata,
    _trace_from_metadata,
)
from .store import RuntimeStateStore
