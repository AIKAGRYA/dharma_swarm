"""Schema, validation, and lifecycle primitives for the campaign store."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping

from .campaign_contract import canonical_json, content_digest

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
_SHA = re.compile(r"^sha256:[0-9a-f]{64}$")
STATES = {
    "CREATED", "PREFLIGHTING", "READY", "RUNNING", "PAUSING", "PAUSED",
    "FUSE_TRIPPED", "DRAINING", "CLOSING", "INTERRUPTED_RECOVERABLE",
    "RECOVERING", "COMPLETED", "FAILED",
}
LEASE_MODES = {"active", "recovery_only", "terminal_only"}
ATTEMPT_OUTCOMES = {"accepted", "rejected", "blocked", "failed", "quarantined"}
TRANSITIONS = {
    "CREATED": {"PREFLIGHTING", "FUSE_TRIPPED", "DRAINING"},
    "PREFLIGHTING": {"READY", "FUSE_TRIPPED", "DRAINING", "INTERRUPTED_RECOVERABLE"},
    "READY": {"RUNNING", "FUSE_TRIPPED", "DRAINING", "INTERRUPTED_RECOVERABLE"},
    "RUNNING": {"PAUSING", "FUSE_TRIPPED", "DRAINING", "INTERRUPTED_RECOVERABLE"},
    "PAUSING": {"PAUSED", "FUSE_TRIPPED", "DRAINING", "INTERRUPTED_RECOVERABLE"},
    "PAUSED": {"RECOVERING", "FUSE_TRIPPED", "DRAINING"},
    "FUSE_TRIPPED": {"PAUSING", "DRAINING", "INTERRUPTED_RECOVERABLE"},
    "DRAINING": {"CLOSING", "INTERRUPTED_RECOVERABLE"},
    "CLOSING": {"COMPLETED", "FAILED", "INTERRUPTED_RECOVERABLE"},
    "INTERRUPTED_RECOVERABLE": {"RECOVERING", "FUSE_TRIPPED", "DRAINING"},
    "RECOVERING": {
        "PREFLIGHTING", "RUNNING", "PAUSING", "FUSE_TRIPPED", "DRAINING",
        "CLOSING", "INTERRUPTED_RECOVERABLE",
    },
    "COMPLETED": set(),
    "FAILED": set(),
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS campaigns(campaign_id TEXT PRIMARY KEY,manifest_digest TEXT NOT NULL,manifest_json TEXT NOT NULL,state TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,attempt_budget INTEGER NOT NULL,terminal_attempts INTEGER NOT NULL DEFAULT 0,token_limit INTEGER,usd_limit INTEGER,request_limit INTEGER,deadline TEXT,reserved_tokens INTEGER NOT NULL DEFAULT 0,reserved_usd INTEGER NOT NULL DEFAULT 0,reserved_requests INTEGER NOT NULL DEFAULT 0,used_tokens INTEGER NOT NULL DEFAULT 0,used_usd INTEGER NOT NULL DEFAULT 0,fence_counter INTEGER NOT NULL DEFAULT 0,active_fence INTEGER,lease_holder TEXT,lease_mode TEXT,lease_expires TEXT,authority_digest TEXT,authority_json TEXT);
CREATE TABLE IF NOT EXISTS events(campaign_id TEXT NOT NULL,sequence INTEGER NOT NULL,event_id TEXT NOT NULL,event_json TEXT NOT NULL,PRIMARY KEY(campaign_id,sequence),UNIQUE(campaign_id,event_id));
CREATE TABLE IF NOT EXISTS actions(campaign_id TEXT NOT NULL,request_id TEXT NOT NULL,input_digest TEXT NOT NULL,receipt_json TEXT NOT NULL,PRIMARY KEY(campaign_id,request_id));
CREATE TABLE IF NOT EXISTS leases(campaign_id TEXT NOT NULL,fencing_token INTEGER NOT NULL,manifest_digest TEXT NOT NULL,holder TEXT NOT NULL,mode TEXT NOT NULL,acquired_at TEXT NOT NULL,expires_at TEXT NOT NULL,PRIMARY KEY(campaign_id,fencing_token));
CREATE TABLE IF NOT EXISTS checkpoints(campaign_id TEXT NOT NULL,checkpoint_id TEXT NOT NULL,payload_digest TEXT NOT NULL,receipt_json TEXT NOT NULL,fencing_token INTEGER NOT NULL,event_sequence INTEGER NOT NULL,PRIMARY KEY(campaign_id,checkpoint_id));
CREATE TABLE IF NOT EXISTS attempts(campaign_id TEXT NOT NULL,attempt_id TEXT NOT NULL,attempt_digest TEXT NOT NULL,status TEXT NOT NULL,receipt_json TEXT NOT NULL,fencing_token INTEGER NOT NULL,event_sequence INTEGER NOT NULL,PRIMARY KEY(campaign_id,attempt_id));
CREATE TABLE IF NOT EXISTS requests(campaign_id TEXT NOT NULL,request_id TEXT NOT NULL,request_digest TEXT NOT NULL,stage TEXT NOT NULL,status TEXT NOT NULL,reserved_tokens INTEGER NOT NULL,reserved_usd INTEGER NOT NULL,actual_tokens INTEGER,actual_usd INTEGER,fencing_token INTEGER NOT NULL,receipt_json TEXT NOT NULL,event_sequence INTEGER NOT NULL,PRIMARY KEY(campaign_id,request_id));
CREATE TABLE IF NOT EXISTS authorities(campaign_id TEXT PRIMARY KEY,manifest_digest TEXT NOT NULL,authority_digest TEXT NOT NULL,authority_json TEXT NOT NULL,verified_at TEXT NOT NULL,fencing_token INTEGER NOT NULL,event_sequence INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS executor_fuses(campaign_id TEXT PRIMARY KEY,state TEXT NOT NULL CHECK(state IN ('closed','open')),reason TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attempt_proof_consumptions(campaign_id TEXT NOT NULL,proof_kind TEXT NOT NULL CHECK(proof_kind IN ('request','evaluation')),proof_id TEXT NOT NULL,attempt_id TEXT NOT NULL,consumed_at TEXT NOT NULL,PRIMARY KEY(campaign_id,proof_kind,proof_id));
"""


class StoreError(RuntimeError):
    """Stable machine-classifiable store refusal."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise StoreError("INVALID_ID", "identifier must contain 3-128 safe characters")
    return value


def digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise StoreError("INVALID_DIGEST", f"{field} must be a sha256 digest")
    return value


def counter(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise StoreError("INVALID_COUNTER", f"{field} must be nonnegative")
    return value


def within(value: int, limit: int, code: str) -> None:
    if value > limit:
        raise StoreError(code, f"cumulative {value} exceeds ceiling {limit}")


def require_transition(previous: str, target: str) -> None:
    if target == previous:
        raise StoreError("INVALID_TRANSITION", "state transition must change state")
    if target not in TRANSITIONS.get(previous, set()):
        raise StoreError("INVALID_TRANSITION", f"{previous} cannot transition to {target}")


def mutation(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping) or value.get("outcome") not in {
        "candidate", "blocked", "failed"
    }:
        raise StoreError("INCOMPLETE_ATTEMPT", "mutation outcome is missing")
    if value["outcome"] == "candidate":
        digest(value.get("candidate_digest"), "candidate_digest")
    elif not isinstance(value.get("reason"), str) or not value["reason"]:
        raise StoreError("INCOMPLETE_ATTEMPT", "blocked/failed mutation needs reason")


def accounting(value: Mapping[str, Any]) -> None:
    keys = {
        "settled", "request_ids", "requests", "tokens", "usd_micros",
        "lineage_digest", "task_accounting_digest", "usage_digest",
    }
    if not isinstance(value, Mapping) or set(value) != keys or value["settled"] is not True:
        raise StoreError("INCOMPLETE_ACCOUNTING", "accounting is incomplete")
    ids = value["request_ids"]
    if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids):
        raise StoreError(
            "INCOMPLETE_ACCOUNTING",
            "request IDs must be a nonempty unique list",
        )
    for item in ids:
        identifier(item)
    for field in ("requests", "tokens", "usd_micros"):
        counter(value[field], field)
    if value["requests"] != len(ids):
        raise StoreError("INCOMPLETE_ACCOUNTING", "request count differs from IDs")
    for field in ("lineage_digest", "task_accounting_digest", "usage_digest"):
        digest(value[field], field)


def text(value: Mapping[str, Any]) -> str:
    return canonical_json(value).decode()


def json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise StoreError("CORRUPT_STORE", "stored record is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise StoreError("CORRUPT_STORE", "stored record is not an object")
    return parsed


def now_utc() -> str:
    return format_time(datetime.now(timezone.utc))


def parse_time(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise StoreError("INVALID_TIMESTAMP", "time must be timezone-aware")
        return value.astimezone(timezone.utc).replace(microsecond=0)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise StoreError("INVALID_TIMESTAMP", "invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise StoreError("INVALID_TIMESTAMP", "time must include timezone")
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def campaign_row(db: sqlite3.Connection, campaign: str) -> sqlite3.Row:
    row = db.execute(
        "SELECT * FROM campaigns WHERE campaign_id=?", (campaign,)
    ).fetchone()
    if not row:
        raise StoreError("CAMPAIGN_NOT_FOUND", f"unknown campaign {campaign}")
    return row


def project_campaign(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema": "forge_lab.campaign_status.v1", "campaign": row["campaign_id"],
        "manifest_digest": row["manifest_digest"], "manifest": json_object(row["manifest_json"]),
        "state": row["state"], "attempt_budget": row["attempt_budget"],
        "terminal_attempts": row["terminal_attempts"],
        "remaining_attempts": row["attempt_budget"] - row["terminal_attempts"],
        "limits": {
            "total_tokens": row["token_limit"], "total_usd_micros": row["usd_limit"],
            "total_requests": row["request_limit"], "deadline_utc": row["deadline"],
        },
        "usage": {
            "reserved_tokens": row["reserved_tokens"],
            "reserved_usd_micros": row["reserved_usd"],
            "reserved_requests": row["reserved_requests"],
            "used_tokens": row["used_tokens"],
            "used_usd_micros": row["used_usd"],
        },
        "authority_digest": row["authority_digest"],
        "lease": {
            "fencing_token": row["active_fence"], "holder": row["lease_holder"],
            "mode": row["lease_mode"], "expires_at": row["lease_expires"],
        },
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def action_replay(
    db: sqlite3.Connection, campaign: str, request_id: str, claim: str
) -> dict[str, Any] | None:
    row = db.execute(
        """SELECT input_digest,receipt_json FROM actions
        WHERE campaign_id=? AND request_id=?""", (campaign, request_id)
    ).fetchone()
    if not row:
        return None
    if row["input_digest"] != claim:
        raise StoreError("IDEMPOTENCY_CONFLICT", "request ID reused with new bytes")
    return json_object(row["receipt_json"])


def save_action(
    db: sqlite3.Connection, campaign: str, request_id: str,
    claim: str, receipt: Mapping[str, Any],
) -> None:
    db.execute(
        "INSERT INTO actions VALUES(?,?,?,?)",
        (campaign, request_id, claim, text(receipt)),
    )


def append_event(
    db: sqlite3.Connection, campaign: str, event_type: str, key: str,
    actor: str | None, previous: str | None, state: str, fence: int | None,
    payload: Mapping[str, Any], *, recorded_at: str,
) -> dict[str, Any]:
    row = campaign_row(db, campaign)
    seq = db.execute(
        "SELECT COALESCE(MAX(sequence),0)+1 n FROM events WHERE campaign_id=?",
        (campaign,),
    ).fetchone()["n"]
    event = {
        "schema": "forge_lab.campaign_event.v1", "campaign": campaign,
        "manifest_digest": row["manifest_digest"], "sequence": seq,
        "type": event_type, "idempotency_key": key, "actor": actor,
        "previous_state": previous, "state": state, "fencing_token": fence,
        "payload": dict(payload), "recorded_at": recorded_at,
    }
    event["event_id"] = content_digest(event)
    db.execute(
        "INSERT INTO events VALUES(?,?,?,?)",
        (campaign, seq, event["event_id"], text(event)),
    )
    return event


def action_receipt(
    campaign: str, request_id: str, action: str, actor: str,
    manifest: str, fence: int | None, state: str, event: Mapping[str, Any],
    *, previous_state: str | None = None,
    payload: Mapping[str, Any] | None = None,
    recorded_at: str,
) -> dict[str, Any]:
    receipt = {
        "schema": "forge_lab.operator_action.v1", "campaign": campaign,
        "request_id": request_id, "action": action, "actor": actor,
        "manifest_digest": manifest, "fencing_token": fence,
        "previous_state": previous_state, "state": state,
        "payload": dict(payload or {}), "event_sequence": event["sequence"],
        "recorded_at": recorded_at,
    }
    receipt["digest"] = content_digest(receipt)
    return receipt


def assert_fence(
    row: sqlite3.Row, token: int | None, *, required: bool = False,
    observed: datetime,
) -> None:
    if token is not None and (
        not isinstance(token, int) or isinstance(token, bool) or token < 1
    ):
        raise StoreError("INVALID_FENCING_TOKEN", "fencing token must be positive")
    active = row["active_fence"]
    if required and active is None:
        raise StoreError("LEASE_REQUIRED", "campaign has no active authority")
    if active is not None and token != active:
        raise StoreError("STALE_FENCING_TOKEN", "missing or stale fencing token")
    if active is None and token is not None:
        raise StoreError("STALE_FENCING_TOKEN", "no lease owns this token")
    if active is not None and row["lease_expires"]:
        if observed >= parse_time(row["lease_expires"]):
            raise StoreError("LEASE_EXPIRED", "manager lease expired")


def assert_holder(row: sqlite3.Row, actor: str) -> None:
    if row["lease_holder"] != actor:
        raise StoreError(
            "LEASE_HOLDER_MISMATCH",
            "mutation actor is not the current lease holder",
        )


def assert_executor_enabled(db: sqlite3.Connection, campaign: str) -> None:
    fuse = db.execute(
        "SELECT state FROM executor_fuses WHERE campaign_id=?",
        (campaign,),
    ).fetchone()
    if not fuse or fuse["state"] != "open":
        raise StoreError(
            "GOVERNED_EXECUTOR_NOT_IMPLEMENTED",
            "provider execution is disabled by the durable campaign fuse",
        )


def assert_powered(
    db: sqlite3.Connection,
    row: sqlite3.Row,
    observed: datetime,
) -> None:
    fields = ("token_limit", "usd_limit", "request_limit", "deadline")
    if any(row[field] is None for field in fields):
        raise StoreError("MISSING_SPEND_AUTHORITY", "campaign ceilings are null")
    if row["authority_digest"] is None or row["authority_json"] is None:
        raise StoreError(
            "MISSING_OPERATOR_ENVELOPE",
            "exact ceilings exist but no verified operator envelope is bound",
        )
    authority = db.execute(
        """SELECT manifest_digest,authority_digest,authority_json
        FROM authorities WHERE campaign_id=?""",
        (row["campaign_id"],),
    ).fetchone()
    if (
        not authority
        or authority["manifest_digest"] != row["manifest_digest"]
        or authority["authority_digest"] != row["authority_digest"]
        or authority["authority_json"] != row["authority_json"]
    ):
        raise StoreError(
            "CORRUPT_AUTHORITY",
            "campaign authority has no matching verification record",
        )
    envelope = json_object(authority["authority_json"])
    manifest = json_object(row["manifest_json"])
    expected = {
        "schema": "forge_lab.operator_envelope.v1",
        "campaign_name": row["campaign_id"],
        "manifest_digest": row["manifest_digest"],
        "total_tokens": row["token_limit"],
        "total_usd_micros": row["usd_limit"],
        "total_requests": row["request_limit"],
        "deadline_utc": row["deadline"],
        "host_caps": manifest["limits"]["host_caps"],
    }
    if any(envelope.get(field) != value for field, value in expected.items()):
        raise StoreError(
            "CORRUPT_AUTHORITY",
            "persisted authority no longer binds exact campaign ceilings",
        )
    if content_digest(envelope) != row["authority_digest"]:
        raise StoreError("CORRUPT_AUTHORITY", "persisted authority digest differs")
    if observed >= parse_time(row["deadline"]):
        raise StoreError("SPEND_DEADLINE_EXPIRED", "spend deadline passed")
