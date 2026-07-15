"""Fail-closed authority check for reconciler receipt projections."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID

import aiosqlite

_FAILED_RECEIPT_STATUSES = frozenset({"failed", "dropped", "timeout", "cancelled"})


def _json_object(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


async def _table_columns(db: aiosqlite.Connection, table: str) -> frozenset[str]:
    rows = await (await db.execute(f"PRAGMA table_info({table})")).fetchall()
    return frozenset(str(row[1]) for row in rows)


def _authority_id(value: Any) -> str | None:
    """Return a non-blank string without normalizing its identity bytes."""
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def claim_run_match(claim_row: Any, run_row: Any) -> bool:
    """Whether a claim and run share the same non-blank task/agent authority."""
    claim_agent = _authority_id(claim_row["agent_id"])
    run_agent = _authority_id(run_row["assigned_to"])
    return (
        str(claim_row["task_id"]) == str(run_row["task_id"])
        and claim_agent is not None
        and claim_agent == run_agent
    )


async def has_runtime_completion(
    db: aiosqlite.Connection,
    *,
    run_id: str,
    task_id: str,
    claim_id: str,
    receipt: Mapping[str, Any],
) -> bool:
    """Require exact run/claim/agent authority for a projected completion.

    Older compatibility schemas may lack one or both agent-identity columns.
    Every identity column that exists is authoritative: it must be non-blank
    and match the receipt exactly.  The canonical runtime schema has both
    ``task_claims.agent_id`` and ``delegation_runs.assigned_to``, so it cannot
    promote an agent-less receipt.
    """
    receipt_id = str(receipt.get("receipt_id", ""))
    try:
        UUID(receipt_id)
    except (TypeError, ValueError, AttributeError):
        return False
    if (
        not run_id
        or not task_id
        or not claim_id
        or str(receipt.get("task_id", "")) != task_id
        or str(receipt.get("claim_id", "")) != claim_id
    ):
        return False

    receipt_status = str(receipt.get("status", ""))
    if receipt_status == "ok":
        expected_record_status = "completed"
    elif receipt_status in _FAILED_RECEIPT_STATUSES:
        expected_record_status = "failed"
    else:
        return False

    attributes = receipt.get("attributes")
    if not isinstance(attributes, Mapping):
        return False
    if str(attributes.get("run_id", "")) != run_id:
        return False
    idempotency_key = str(attributes.get("idempotency_key", ""))
    side_effect_key = str(attributes.get("side_effect_key", ""))
    if not idempotency_key or not side_effect_key:
        return False

    claim_columns = await _table_columns(db, "task_claims")
    run_columns = await _table_columns(db, "delegation_runs")
    if (
        not {"claim_id", "task_id"} <= claim_columns
        or not {
            "run_id",
            "task_id",
        }
        <= run_columns
    ):
        return False

    receipt_agent = _authority_id(receipt.get("agent_id"))
    authority_is_expressible = (
        "agent_id" in claim_columns or "assigned_to" in run_columns
    )
    if authority_is_expressible and receipt_agent is None:
        return False

    # A claim identifier is not sufficient authority by itself: the runtime
    # schema does not make delegation_runs.claim_id a composite foreign key to
    # (claim_id, task_id).  Fail closed if a corrupt or stale run row points at
    # a real claim owned by another task/agent (or at no durable claim at all).
    claim_projection = "task_id"
    if "agent_id" in claim_columns:
        claim_projection += ", agent_id"
    claim_rows = await (
        await db.execute(
            f"SELECT {claim_projection} FROM task_claims WHERE claim_id = ?",
            (claim_id,),
        )
    ).fetchall()
    if len(claim_rows) != 1 or str(claim_rows[0]["task_id"]) != task_id:
        return False
    if "agent_id" in claim_columns:
        claim_agent = _authority_id(claim_rows[0]["agent_id"])
        if claim_agent is None or claim_agent != receipt_agent:
            return False

    run_projection = "task_id"
    if "claim_id" in run_columns:
        run_projection += ", claim_id"
    if "assigned_to" in run_columns:
        run_projection += ", assigned_to"
    run_rows = await (
        await db.execute(
            f"SELECT {run_projection} FROM delegation_runs WHERE run_id = ?",
            (run_id,),
        )
    ).fetchall()
    if len(run_rows) != 1 or str(run_rows[0]["task_id"]) != task_id:
        return False
    if "claim_id" in run_columns and str(run_rows[0]["claim_id"]) != claim_id:
        return False
    if "assigned_to" in run_columns:
        run_agent = _authority_id(run_rows[0]["assigned_to"])
        if run_agent is None or run_agent != receipt_agent:
            return False

    rows = await (
        await db.execute(
            "SELECT idempotency_key, status, side_effect_key, metadata_json"
            " FROM idempotency_records WHERE run_id = ? AND task_id = ?"
            " AND result_receipt_id = ?",
            (run_id, task_id, receipt_id),
        )
    ).fetchall()
    if len(rows) != 1:
        return False
    row = rows[0]
    metadata = _json_object(row["metadata_json"])
    return (
        str(row["status"]) == expected_record_status
        and str(row["idempotency_key"]) == idempotency_key
        and str(row["side_effect_key"]) == side_effect_key
        and metadata.get("receipt") == dict(receipt)
    )
