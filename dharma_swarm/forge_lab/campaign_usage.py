"""Hard cumulative provider reservation and settlement accounting."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .campaign_contract import content_digest
from .campaign_store_schema import (
    StoreError,
    append_event,
    assert_executor_enabled,
    assert_fence,
    assert_powered,
    campaign_row,
    counter,
    format_time,
    identifier,
    json_object,
    text,
    within,
)

if TYPE_CHECKING:
    from .campaign_store import CampaignStore

_TERMINAL = {"succeeded", "failed", "cancelled", "unknown_after_interruption"}


def reserve_request(
    store: CampaignStore,
    campaign_id: str,
    *,
    request_id: str,
    stage: str,
    token_ceiling: int,
    usd_micros_ceiling: int,
    fencing_token: int,
) -> dict[str, Any]:
    campaign, request_id, stage = (
        identifier(campaign_id), identifier(request_id), identifier(stage)
    )
    counter(token_ceiling, "token_ceiling")
    counter(usd_micros_ceiling, "usd_micros_ceiling")
    observed = store._observed()
    now = format_time(observed)
    body = {
        "stage": stage,
        "token_ceiling": token_ceiling,
        "usd_micros_ceiling": usd_micros_ceiling,
    }
    claim = content_digest(body)
    with store._write() as db:
        row = campaign_row(db, campaign)
        assert_fence(row, fencing_token, required=True, observed=observed)
        if row["lease_mode"] != "active":
            raise StoreError("AUTHORITY_MODE_VIOLATION", "only active lease may spend")
        assert_executor_enabled(db, campaign)
        if row["state"] != "RUNNING":
            raise StoreError("DISPATCH_CLOSED", "provider dispatch requires RUNNING state")
        old = db.execute(
            """SELECT request_digest,receipt_json FROM requests
            WHERE campaign_id=? AND request_id=?""", (campaign, request_id)
        ).fetchone()
        if old:
            if old["request_digest"] != claim:
                raise StoreError("REQUEST_ID_CONFLICT", "request ID reused")
            return json_object(old["receipt_json"])
        assert_powered(db, row, observed)
        totals = (
            row["reserved_tokens"] + token_ceiling,
            row["reserved_usd"] + usd_micros_ceiling,
            row["reserved_requests"] + 1,
        )
        within(totals[0], row["token_limit"], "TOKEN_CEILING_EXCEEDED")
        within(totals[1], row["usd_limit"], "USD_CEILING_EXCEEDED")
        within(totals[2], row["request_limit"], "REQUEST_CEILING_EXCEEDED")
        event = append_event(
            db, campaign, "request.reserved", request_id, row["lease_holder"],
            row["state"], row["state"], fencing_token, body, recorded_at=now,
        )
        receipt = {
            "schema": "forge_lab.model_request_receipt.v1", "campaign": campaign,
            "manifest_digest": row["manifest_digest"], "request_id": request_id,
            **body, "status": "reserved", "actual_tokens": None,
            "actual_usd_micros": None, "fencing_token": fencing_token,
            "event_sequence": event["sequence"], "recorded_at": now,
        }
        receipt["digest"] = content_digest(receipt)
        db.execute(
            """INSERT INTO requests(
            campaign_id,request_id,request_digest,stage,status,reserved_tokens,
            reserved_usd,actual_tokens,actual_usd,fencing_token,receipt_json,event_sequence)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (campaign, request_id, claim, stage, "reserved", token_ceiling,
             usd_micros_ceiling, None, None, fencing_token, text(receipt),
             event["sequence"]),
        )
        db.execute(
            """UPDATE campaigns SET reserved_tokens=?,reserved_usd=?,
            reserved_requests=?,updated_at=? WHERE campaign_id=?""",
            (*totals, now, campaign),
        )
        return receipt


def settle_request(
    store: CampaignStore,
    campaign_id: str,
    *,
    request_id: str,
    status: str,
    actual_tokens: int,
    actual_usd_micros: int,
    fencing_token: int,
) -> dict[str, Any]:
    campaign, request_id = identifier(campaign_id), identifier(request_id)
    if status not in _TERMINAL:
        raise StoreError("INVALID_REQUEST_STATUS", "request status is not terminal")
    counter(actual_tokens, "actual_tokens")
    counter(actual_usd_micros, "actual_usd_micros")
    with store._write() as db:
        campaign_row_value = campaign_row(db, campaign)
        observed = store._observed()
        now = format_time(observed)
        assert_fence(
            campaign_row_value,
            fencing_token,
            required=True,
            observed=observed,
        )
        row = db.execute(
            "SELECT * FROM requests WHERE campaign_id=? AND request_id=?",
            (campaign, request_id),
        ).fetchone()
        if not row:
            raise StoreError("REQUEST_NOT_FOUND", f"unknown request {request_id}")
        terminal = {
            "status": status, "actual_tokens": actual_tokens,
            "actual_usd_micros": actual_usd_micros,
        }
        if row["status"] in _TERMINAL:
            prior = json_object(row["receipt_json"])
            if all(prior.get(key) == value for key, value in terminal.items()):
                return prior
            raise StoreError("REQUEST_ID_CONFLICT", "terminal request bytes changed")
        if actual_tokens > row["reserved_tokens"] or actual_usd_micros > row["reserved_usd"]:
            raise StoreError("REQUEST_RESERVATION_EXCEEDED", "usage exceeded reservation")
        event = append_event(
            db, campaign, "request.settled", f"{request_id}:settle",
            campaign_row_value["lease_holder"], campaign_row_value["state"],
            campaign_row_value["state"], fencing_token, terminal, recorded_at=now,
        )
        receipt = {**json_object(row["receipt_json"]), **terminal}
        receipt.update({"event_sequence": event["sequence"], "settled_at": now})
        receipt.pop("digest", None)
        receipt["digest"] = content_digest(receipt)
        db.execute(
            """UPDATE requests SET status=?,actual_tokens=?,actual_usd=?,
            receipt_json=?,event_sequence=? WHERE campaign_id=? AND request_id=?""",
            (status, actual_tokens, actual_usd_micros, text(receipt),
             event["sequence"], campaign, request_id),
        )
        db.execute(
            """UPDATE campaigns SET used_tokens=used_tokens+?,
            used_usd=used_usd+?,updated_at=? WHERE campaign_id=?""",
            (actual_tokens, actual_usd_micros, now, campaign),
        )
        return receipt


def verify_attempt_accounting(db, campaign: str, accounting: dict) -> set[str]:
    tokens = usd = 0
    statuses: set[str] = set()
    for request_id in accounting["request_ids"]:
        row = db.execute(
            """SELECT status,actual_tokens,actual_usd FROM requests
            WHERE campaign_id=? AND request_id=?""", (campaign, request_id)
        ).fetchone()
        if not row or row["status"] not in _TERMINAL:
            raise StoreError("INCOMPLETE_ACCOUNTING", "request is not settled")
        statuses.add(row["status"])
        tokens += row["actual_tokens"]
        usd += row["actual_usd"]
    if tokens != accounting["tokens"] or usd != accounting["usd_micros"]:
        raise StoreError("ACCOUNTING_MISMATCH", "usage differs from request receipts")
    return statuses
