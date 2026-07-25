"""Read-only semantic checks for the governed campaign SQLite store."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any

from dharma_swarm.forge_lab.campaign_contract import (
    CampaignContractError,
    content_digest,
    validate_manifest,
)
from dharma_swarm.forge_lab.campaign_store_schema import STATES


_TABLES = {
    "actions",
    "attempt_proof_consumptions",
    "attempts",
    "authorities",
    "campaigns",
    "checkpoints",
    "events",
    "executor_fuses",
    "leases",
    "requests",
}
_TERMINAL = {"COMPLETED", "FAILED"}
_ACTIVE = {"READY", "RUNNING"}
_SETTLED = {"succeeded", "failed", "cancelled", "unknown_after_interruption"}


def _issue(code: str, **detail: Any) -> dict[str, Any]:
    return {"code": code, "detail": detail or None}


def _connect(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve()}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True, timeout=2)
    connection.row_factory = sqlite3.Row
    return connection


def _campaign_issues(db: sqlite3.Connection) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    rows = db.execute("SELECT * FROM campaigns ORDER BY campaign_id").fetchall()
    for row in rows:
        campaign = row["campaign_id"]
        state = row["state"]
        if state not in STATES:
            issues.append(_issue("DB_INVALID_LIFECYCLE_STATE", campaign=campaign, state=state))
        if state in _TERMINAL and row["active_fence"] is not None:
            issues.append(_issue("DB_TERMINAL_LEASE_PRESENT", campaign=campaign))
        if state in _ACTIVE and (
            row["authority_digest"] is None or row["authority_json"] is None
        ):
            issues.append(_issue("DB_UNAUTHORIZED_ACTIVE_STATE", campaign=campaign))
        fuse = db.execute(
            "SELECT state FROM executor_fuses WHERE campaign_id=?", (campaign,)
        ).fetchone()
        if not fuse or fuse["state"] != "closed":
            issues.append(_issue("DB_UNGOVERNED_EXECUTOR_OPEN", campaign=campaign))
        try:
            manifest = validate_manifest(json.loads(row["manifest_json"]))
        except (CampaignContractError, json.JSONDecodeError, TypeError) as exc:
            issues.append(
                _issue(
                    "DB_CORRUPT_MANIFEST",
                    campaign=campaign,
                    error=getattr(exc, "code", type(exc).__name__),
                )
            )
        else:
            if manifest["manifest_digest"] != row["manifest_digest"]:
                issues.append(_issue("DB_MANIFEST_DIGEST_MISMATCH", campaign=campaign))
        attempt_count = db.execute(
            "SELECT COUNT(*) FROM attempts WHERE campaign_id=?", (campaign,)
        ).fetchone()[0]
        if attempt_count != row["terminal_attempts"]:
            issues.append(
                _issue(
                    "DB_ATTEMPT_COUNT_MISMATCH",
                    campaign=campaign,
                    declared=row["terminal_attempts"],
                    observed=attempt_count,
                )
            )
        if attempt_count > row["attempt_budget"]:
            issues.append(_issue("DB_ATTEMPT_BUDGET_EXCEEDED", campaign=campaign))
        sequences = [
            item[0]
            for item in db.execute(
                "SELECT sequence FROM events WHERE campaign_id=? ORDER BY sequence",
                (campaign,),
            )
        ]
        if sequences != list(range(1, len(sequences) + 1)):
            issues.append(_issue("DB_EVENT_SEQUENCE_GAP", campaign=campaign))
        requests = db.execute(
            """SELECT status,actual_tokens,actual_usd FROM requests
            WHERE campaign_id=?""",
            (campaign,),
        ).fetchall()
        if state in _TERMINAL and any(item["status"] not in _SETTLED for item in requests):
            issues.append(_issue("DB_TERMINAL_UNSETTLED_REQUEST", campaign=campaign))
        used_tokens = sum(
            item["actual_tokens"] or 0 for item in requests if item["status"] in _SETTLED
        )
        used_usd = sum(
            item["actual_usd"] or 0 for item in requests if item["status"] in _SETTLED
        )
        if used_tokens != row["used_tokens"] or used_usd != row["used_usd"]:
            issues.append(_issue("DB_USAGE_TOTAL_MISMATCH", campaign=campaign))
    return issues


def _terminal_receipt_issues(
    path: Path,
    db: sqlite3.Connection,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    campaigns = db.execute(
        """SELECT campaign_id,manifest_digest FROM campaigns
        WHERE state='FAILED' ORDER BY campaign_id"""
    ).fetchall()
    for row in campaigns:
        campaign = row["campaign_id"]
        events = db.execute(
            """SELECT event_json FROM events WHERE campaign_id=?
            ORDER BY sequence DESC""",
            (campaign,),
        ).fetchall()
        declared = None
        for event_row in events:
            try:
                event = json.loads(event_row["event_json"])
            except (json.JSONDecodeError, TypeError):
                continue
            candidate = (event.get("payload") or {}).get("blocked_receipt_digest")
            if isinstance(candidate, str):
                declared = candidate
                break
        if declared is None:
            issues.append(_issue("DB_TERMINAL_RECEIPT_UNBOUND", campaign=campaign))
            continue
        matched = False
        receipt_root = path.parent / campaign / "receipts"
        for receipt_path in sorted(receipt_root.glob("blocked-*.json")):
            if receipt_path.is_symlink() or not receipt_path.is_file():
                continue
            try:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError):
                continue
            body = dict(receipt)
            receipt_digest = body.pop("receipt_digest", None)
            if (
                receipt_digest == declared
                and content_digest(body) == declared
                and receipt.get("campaign_id") == campaign
                and receipt.get("manifest_digest") == row["manifest_digest"]
            ):
                matched = True
                break
        if not matched:
            issues.append(
                _issue(
                    "DB_TERMINAL_RECEIPT_MISSING",
                    campaign=campaign,
                    receipt_digest=declared,
                )
            )
    return issues


def inspect_control_db(path: Path) -> list[dict[str, Any]]:
    """Return deterministic integrity findings without mutating the database."""

    issues: list[dict[str, Any]] = []
    try:
        with _connect(path) as db:
            quick = db.execute("PRAGMA quick_check").fetchall()
            if [row[0] for row in quick] != ["ok"]:
                issues.append(
                    _issue("DB_INTEGRITY_CHECK_FAILED", results=[row[0] for row in quick])
                )
                return issues
            tables = {
                row[0]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            missing = sorted(_TABLES - tables)
            if missing:
                issues.append(_issue("DB_SCHEMA_MISSING", tables=missing))
                return issues
            issues.extend(_campaign_issues(db))
            issues.extend(_terminal_receipt_issues(path, db))
    except (sqlite3.Error, OSError, TypeError, ValueError) as exc:
        issues.append(
            _issue(
                "DB_SEMANTIC_CHECK_FAILED",
                error=type(exc).__name__,
                message=str(exc),
            )
        )
    return issues
