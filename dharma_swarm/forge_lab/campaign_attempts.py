"""Fail-closed terminal-attempt validation and proof consumption."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any, Mapping

from .campaign_contract import content_digest
from .campaign_store_schema import (
    ATTEMPT_OUTCOMES,
    StoreError,
    accounting as validate_accounting,
    append_event,
    assert_executor_enabled,
    assert_fence,
    assert_powered,
    campaign_row,
    digest,
    format_time,
    json_object,
    mutation,
    text,
)
from .campaign_usage import verify_attempt_accounting

if TYPE_CHECKING:
    from .campaign_store import CampaignStore


def terminal_attempt(
    store: CampaignStore,
    campaign: str,
    *,
    attempt_id: str,
    status: str,
    parent_digest: str,
    mutation_result: Mapping[str, Any],
    evaluation_digest: str,
    accounting: Mapping[str, Any],
    terminal_receipt: Mapping[str, Any],
    fencing_token: int,
) -> dict[str, Any]:
    """Commit one fully bound attempt and atomically consume its proofs."""

    if status not in ATTEMPT_OUTCOMES:
        raise StoreError("INVALID_ATTEMPT_STATUS", "status is not terminal")
    digest(parent_digest, "parent_digest")
    digest(evaluation_digest, "evaluation_digest")
    mutation(mutation_result)
    validate_accounting(accounting)
    if not isinstance(terminal_receipt, Mapping):
        raise StoreError(
            "INVALID_TERMINAL_RECEIPT",
            "terminal receipt must be an exact object",
        )

    with store._write() as db:
        row = campaign_row(db, campaign)
        observed = store._observed()
        now = format_time(observed)
        assert_fence(
            row,
            fencing_token,
            required=True,
            observed=observed,
        )
        if row["lease_mode"] != "active":
            raise StoreError(
                "AUTHORITY_MODE_VIOLATION",
                "only an active lease can commit an attempt",
            )
        if row["state"] != "RUNNING":
            raise StoreError(
                "ATTEMPT_GATE_CLOSED",
                "attempt terminalization requires RUNNING state",
            )
        assert_executor_enabled(db, campaign)
        assert_powered(db, row, observed)
        expected_terminal_receipt = {
            "schema": "forge_lab.primary_attempt_terminal.v1",
            "campaign": campaign,
            "manifest_digest": row["manifest_digest"],
            "attempt_id": attempt_id,
            "status": status,
            "parent_digest": parent_digest,
            "mutation_result": dict(mutation_result),
            "evaluation_digest": evaluation_digest,
            "accounting_digest": content_digest(accounting),
            "authority_digest": row["authority_digest"],
            "fencing_token": fencing_token,
        }
        if dict(terminal_receipt) != expected_terminal_receipt:
            raise StoreError(
                "INVALID_TERMINAL_RECEIPT",
                "terminal receipt must exactly bind the attempt and its proofs",
            )
        body = {
            "status": status,
            "parent_digest": parent_digest,
            "mutation_result": dict(mutation_result),
            "evaluation_digest": evaluation_digest,
            "accounting": dict(accounting),
            "terminal_receipt": expected_terminal_receipt,
        }
        claim = content_digest(body)
        old = db.execute(
            """SELECT attempt_digest,receipt_json FROM attempts
            WHERE campaign_id=? AND attempt_id=?""",
            (campaign, attempt_id),
        ).fetchone()
        if old:
            if old["attempt_digest"] != claim:
                raise StoreError("ATTEMPT_ID_CONFLICT", "attempt ID reused")
            return json_object(old["receipt_json"])
        if row["terminal_attempts"] >= row["attempt_budget"]:
            raise StoreError("ATTEMPT_BUDGET_EXHAUSTED", "attempt budget complete")

        request_states = verify_attempt_accounting(db, campaign, dict(accounting))
        if request_states != {"succeeded"}:
            raise StoreError(
                "INCOMPLETE_EVALUATION",
                "attempts require nonempty successful request settlements",
            )
        for request_id in accounting["request_ids"]:
            _consume_attempt_proof(
                db,
                campaign,
                attempt_id,
                "request",
                request_id,
                now,
            )
        _consume_attempt_proof(
            db,
            campaign,
            attempt_id,
            "evaluation",
            evaluation_digest,
            now,
        )
        event = append_event(
            db,
            campaign,
            "attempt.terminal",
            attempt_id,
            row["lease_holder"],
            row["state"],
            row["state"],
            fencing_token,
            {"attempt_digest": claim, "status": status},
            recorded_at=now,
        )
        receipt = {
            "schema": "forge_lab.primary_attempt.v1",
            "campaign": campaign,
            "manifest_digest": row["manifest_digest"],
            "attempt_id": attempt_id,
            **body,
            "attempt_digest": claim,
            "fencing_token": fencing_token,
            "event_sequence": event["sequence"],
            "recorded_at": now,
        }
        receipt["digest"] = content_digest(receipt)
        db.execute(
            "INSERT INTO attempts VALUES(?,?,?,?,?,?,?)",
            (
                campaign,
                attempt_id,
                claim,
                status,
                text(receipt),
                fencing_token,
                event["sequence"],
            ),
        )
        db.execute(
            """UPDATE campaigns SET terminal_attempts=terminal_attempts+1,
            updated_at=? WHERE campaign_id=?""",
            (now, campaign),
        )
        return receipt


def _consume_attempt_proof(
    db: sqlite3.Connection,
    campaign: str,
    attempt_id: str,
    proof_kind: str,
    proof_id: str,
    consumed_at: str,
) -> None:
    owner = db.execute(
        """SELECT attempt_id FROM attempt_proof_consumptions
        WHERE campaign_id=? AND proof_kind=? AND proof_id=?""",
        (campaign, proof_kind, proof_id),
    ).fetchone()
    if owner:
        raise StoreError(
            "ATTEMPT_PROOF_ALREADY_CONSUMED",
            f"{proof_kind} proof is already bound to {owner['attempt_id']}",
        )
    db.execute(
        """INSERT INTO attempt_proof_consumptions(
        campaign_id,proof_kind,proof_id,attempt_id,consumed_at)
        VALUES(?,?,?,?,?)""",
        (campaign, proof_kind, proof_id, attempt_id, consumed_at),
    )
