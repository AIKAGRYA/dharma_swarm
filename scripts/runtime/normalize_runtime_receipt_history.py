#!/usr/bin/env python3
"""Normalize historical runtime receipts to the current receipt contract.

This is stronger than the idempotency-only backfill. It may update historical
``runtime_receipts`` rows, but only when the replacement can be derived from
the current runtime contract or from recorded delegation state. Every payload
touch is marked with a normalization schema/version.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB, RuntimeStateStore


SCHEMA_VERSION = "runtime_receipt_history_normalization.v1"
MAJOR_RECEIPT_TYPES = ("delegation_run", "a2a_task")
SIDE_EFFECT_RECEIPT_TYPES = ("delegation_run", "task_claim")


@dataclass(frozen=True)
class SideEffectCandidate:
    receipt_id: str
    receipt_type: str
    run_id: str
    task_id: str
    trace_id: str
    correlation_id: str
    idempotency_key: str
    derived_side_effect_key: str
    receipt_status: str
    receipt_created_at: str


@dataclass(frozen=True)
class IdempotencyCandidate:
    receipt_id: str
    receipt_type: str
    run_id: str
    task_id: str
    trace_id: str
    correlation_id: str
    idempotency_key: str
    side_effect_key: str
    receipt_status: str
    receipt_created_at: str
    side_effect_key_was_derived: bool = False


@dataclass
class ReceiptPatch:
    receipt_id: str
    payload: dict[str, Any]
    fields: set[str] = field(default_factory=set)
    side_effect_key: str | None = None


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _connect(db_path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    return db


def _safe_json(raw: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(raw or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _payload_has_mission(payload: dict[str, Any]) -> bool:
    return bool(payload.get("mission_id") or payload.get("mission") or payload.get("missionId"))


def _payload_has_artifact_ref(payload: dict[str, Any]) -> bool:
    return bool(
        payload.get("artifact_refs")
        or payload.get("artifact_ref")
        or payload.get("artifact_id")
        or payload.get("artifactId")
        or payload.get("artifacts")
    )


def _payload_has_explicit_artifact_absence(payload: dict[str, Any]) -> bool:
    missing = payload.get("missing_machine_fields") or []
    return (
        isinstance(missing, list)
        and "artifact_refs" in {str(item) for item in missing}
    ) or bool(payload.get("no_artifact_refs_reason"))


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _normalization_marker(applied_at: str, fields: set[str]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "applied_at": applied_at,
        "fields": sorted(fields),
    }


def _derive_mission(row: sqlite3.Row) -> tuple[str, str, str]:
    metadata = _safe_json(row["delegation_metadata_json"])
    explicit_mission_id = _first_text(metadata.get("mission_id"), metadata.get("missionId"))
    explicit_mission = _first_text(metadata.get("mission"))
    fallback = _first_text(row["delegation_session_id"], row["task_id"])
    mission = _first_text(explicit_mission, explicit_mission_id, fallback)
    mission_id = _first_text(explicit_mission_id, explicit_mission, mission)
    source = (
        "explicit_delegation_metadata_mission_id"
        if explicit_mission_id
        else "explicit_delegation_metadata_mission"
        if explicit_mission
        else "historical_runtime_lifecycle_fallback"
    )
    return mission_id, mission, source


def _artifact_absence_reason(row: sqlite3.Row) -> str:
    failure_code = _first_text(row["delegation_failure_code"])
    status = _first_text(row["status"])
    if failure_code:
        return f"historical_{failure_code}_receipt_no_artifact_recorded"
    if status in {"claimed", "queued", "running"}:
        return "historical_non_terminal_receipt_no_artifact_recorded"
    return "historical_receipt_no_artifact_recorded"


def _side_effect_candidates(db: sqlite3.Connection) -> list[SideEffectCandidate]:
    rows = db.execute(
        """
        SELECT
          rr.receipt_id,
          rr.receipt_type,
          rr.run_id,
          rr.task_id,
          rr.trace_id,
          rr.correlation_id,
          rr.idempotency_key,
          rr.status,
          rr.created_at,
          dr.claim_id
        FROM runtime_receipts rr
        LEFT JOIN delegation_runs dr
          ON rr.run_id != ''
         AND rr.run_id = dr.run_id
        WHERE rr.receipt_type IN ('delegation_run', 'task_claim')
          AND coalesce(rr.side_effect_key, '') = ''
          AND coalesce(rr.idempotency_key, '') != ''
        ORDER BY rr.created_at ASC, rr.receipt_id ASC
        """
    ).fetchall()
    candidates: list[SideEffectCandidate] = []
    for row in rows:
        receipt_type = str(row["receipt_type"])
        status = str(row["status"] or "")
        run_id = str(row["run_id"] or "")
        claim_id = str(row["claim_id"] or "")
        if receipt_type == "delegation_run" and run_id:
            side_effect_key = f"delegation_run:{run_id}:{status}"
        elif receipt_type == "task_claim" and claim_id:
            side_effect_key = f"task_claim:{claim_id}:{status}"
        else:
            continue
        candidates.append(
            SideEffectCandidate(
                receipt_id=str(row["receipt_id"]),
                receipt_type=receipt_type,
                run_id=run_id,
                task_id=str(row["task_id"] or ""),
                trace_id=str(row["trace_id"] or ""),
                correlation_id=str(row["correlation_id"] or ""),
                idempotency_key=str(row["idempotency_key"]),
                derived_side_effect_key=side_effect_key,
                receipt_status=status,
                receipt_created_at=str(row["created_at"] or ""),
            )
        )
    return candidates


def _payload_patches(
    db: sqlite3.Connection,
    *,
    applied_at: str,
) -> dict[str, ReceiptPatch]:
    rows = db.execute(
        """
        SELECT
          rr.receipt_id,
          rr.run_id,
          rr.task_id,
          rr.status,
          rr.payload_json,
          dr.session_id AS delegation_session_id,
          dr.failure_code AS delegation_failure_code,
          dr.metadata_json AS delegation_metadata_json,
          EXISTS(
            SELECT 1
            FROM artifact_records ar
            WHERE (rr.run_id != '' AND rr.run_id = ar.run_id)
               OR (rr.task_id != '' AND rr.task_id = ar.task_id)
          ) AS has_artifact_record
        FROM runtime_receipts rr
        LEFT JOIN delegation_runs dr
          ON rr.run_id != ''
         AND rr.run_id = dr.run_id
        WHERE rr.receipt_type = 'delegation_run'
        ORDER BY rr.created_at ASC, rr.receipt_id ASC
        """
    ).fetchall()
    patches: dict[str, ReceiptPatch] = {}
    for row in rows:
        payload = _safe_json(row["payload_json"])
        fields: set[str] = set()
        if not _payload_has_mission(payload):
            mission_id, mission, source = _derive_mission(row)
            if mission_id:
                payload["mission_id"] = mission_id
                payload["mission"] = mission
                payload["mission_id_source"] = source
                fields.add("mission_payload")
        if (
            not int(row["has_artifact_record"] or 0)
            and not _payload_has_artifact_ref(payload)
            and not _payload_has_explicit_artifact_absence(payload)
        ):
            payload["no_artifact_refs_reason"] = _artifact_absence_reason(row)
            payload["artifact_refs_source"] = "historical_runtime_receipt_normalization"
            fields.add("artifact_absence")
        if fields:
            payload["historical_runtime_receipt_normalization"] = _normalization_marker(
                applied_at,
                fields,
            )
            patches[str(row["receipt_id"])] = ReceiptPatch(
                receipt_id=str(row["receipt_id"]),
                payload=payload,
                fields=fields,
            )
    return patches


def _idempotency_candidates(
    db: sqlite3.Connection,
    *,
    side_candidates: list[SideEffectCandidate],
) -> list[IdempotencyCandidate]:
    existing = {
        (str(row["idempotency_key"]), str(row["side_effect_key"]))
        for row in db.execute("SELECT idempotency_key, side_effect_key FROM idempotency_records")
    }
    candidates: dict[tuple[str, str], IdempotencyCandidate] = {}
    side_by_receipt = {item.receipt_id: item for item in side_candidates}
    for row in db.execute(
        """
        SELECT
          receipt_id,
          receipt_type,
          run_id,
          task_id,
          trace_id,
          correlation_id,
          idempotency_key,
          side_effect_key,
          status,
          created_at
        FROM runtime_receipts
        WHERE receipt_type IN ('delegation_run', 'task_claim', 'a2a_task')
          AND coalesce(idempotency_key, '') != ''
        ORDER BY created_at ASC, receipt_id ASC
        """
    ):
        receipt_id = str(row["receipt_id"])
        side_candidate = side_by_receipt.get(receipt_id)
        side_effect_key = (
            side_candidate.derived_side_effect_key
            if side_candidate is not None
            else str(row["side_effect_key"] or "")
        )
        if not side_effect_key:
            continue
        idempotency_key = str(row["idempotency_key"])
        key = (idempotency_key, side_effect_key)
        if key in existing or key in candidates:
            continue
        candidates[key] = IdempotencyCandidate(
            receipt_id=receipt_id,
            receipt_type=str(row["receipt_type"]),
            run_id=str(row["run_id"] or ""),
            task_id=str(row["task_id"] or ""),
            trace_id=str(row["trace_id"] or ""),
            correlation_id=str(row["correlation_id"] or ""),
            idempotency_key=idempotency_key,
            side_effect_key=side_effect_key,
            receipt_status=str(row["status"] or ""),
            receipt_created_at=str(row["created_at"] or ""),
            side_effect_key_was_derived=side_candidate is not None,
        )
    return list(candidates.values())


def _candidate_counts(
    side_candidates: list[SideEffectCandidate],
    payload_patches: dict[str, ReceiptPatch],
    idempotency_candidates: list[IdempotencyCandidate],
) -> dict[str, Any]:
    payload_fields: dict[str, int] = {}
    for patch in payload_patches.values():
        for field_name in patch.fields:
            payload_fields[field_name] = payload_fields.get(field_name, 0) + 1
    return {
        "side_effect_key_candidates": len(side_candidates),
        "payload_candidates": len(payload_patches),
        "idempotency_record_candidates": len(idempotency_candidates),
        "payload_fields": dict(sorted(payload_fields.items())),
        "side_effect_by_type": _count_by_attr(side_candidates, "receipt_type"),
        "idempotency_by_type": _count_by_attr(idempotency_candidates, "receipt_type"),
    }


def _count_by_attr(items: list[Any], attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(getattr(item, attr))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _idempotency_metadata(candidate: IdempotencyCandidate) -> str:
    return json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "source": "runtime_receipt_history_normalization",
            "receipt_id": candidate.receipt_id,
            "receipt_type": candidate.receipt_type,
            "receipt_status": candidate.receipt_status,
            "receipt_created_at": candidate.receipt_created_at,
            "created_from_existing_runtime_receipt": True,
            "side_effect_key_was_derived": candidate.side_effect_key_was_derived,
            "runtime_receipt_was_rewritten": candidate.side_effect_key_was_derived,
        },
        sort_keys=True,
    )


def normalize_runtime_receipt_history(
    db_path: Path,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    db_path = db_path.expanduser()
    RuntimeStateStore(db_path, include_memory_plane=False).init_db_sync()
    applied_at = _utc_now_iso()
    with _connect(db_path) as db:
        side_candidates = _side_effect_candidates(db)
        payload_patches = _payload_patches(db, applied_at=applied_at)
        for candidate in side_candidates:
            patch = payload_patches.setdefault(
                candidate.receipt_id,
                ReceiptPatch(
                    receipt_id=candidate.receipt_id,
                    payload=_payload_for_receipt(db, candidate.receipt_id),
                ),
            )
            patch.side_effect_key = candidate.derived_side_effect_key
            patch.payload["side_effect_key_source"] = (
                "historical_runtime_contract_reconstruction"
            )
            patch.payload["side_effect_key_was_reconstructed"] = True
            patch.fields.add("side_effect_key")
            patch.payload["historical_runtime_receipt_normalization"] = (
                _normalization_marker(applied_at, patch.fields)
            )
        idempotency_candidates = _idempotency_candidates(
            db,
            side_candidates=side_candidates,
        )

    counts = _candidate_counts(side_candidates, payload_patches, idempotency_candidates)
    updated_side_effect = 0
    updated_payload = 0
    inserted_idempotency = 0
    if apply:
        with sqlite3.connect(db_path) as db:
            for patch in payload_patches.values():
                if patch.side_effect_key is not None:
                    cur = db.execute(
                        "UPDATE runtime_receipts"
                        " SET side_effect_key = ?, payload_json = ?"
                        " WHERE receipt_id = ? AND coalesce(side_effect_key, '') = ''",
                        (
                            patch.side_effect_key,
                            _json_dump(patch.payload),
                            patch.receipt_id,
                        ),
                    )
                    updated_side_effect += int(cur.rowcount or 0)
                    if int(cur.rowcount or 0):
                        updated_payload += 1
                else:
                    cur = db.execute(
                        "UPDATE runtime_receipts"
                        " SET payload_json = ?"
                        " WHERE receipt_id = ?",
                        (_json_dump(patch.payload), patch.receipt_id),
                    )
                    updated_payload += int(cur.rowcount or 0)
            rows = [
                (
                    candidate.idempotency_key,
                    candidate.side_effect_key,
                    candidate.run_id,
                    candidate.task_id,
                    candidate.trace_id,
                    candidate.correlation_id,
                    "completed",
                    candidate.receipt_id,
                    _idempotency_metadata(candidate),
                    applied_at,
                    applied_at,
                )
                for candidate in idempotency_candidates
            ]
            if rows:
                cur = db.executemany(
                    "INSERT OR IGNORE INTO idempotency_records ("
                    " idempotency_key, side_effect_key, run_id, task_id, trace_id,"
                    " correlation_id, status, result_receipt_id, metadata_json,"
                    " created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    rows,
                )
                inserted_idempotency = int(cur.rowcount or 0)
            db.commit()

    return {
        "schema_version": SCHEMA_VERSION,
        "db_path": str(db_path),
        "mode": "apply" if apply else "dry_run",
        "applied_at": applied_at if apply else "",
        "counts": counts,
        "updated_side_effect_key_count": updated_side_effect,
        "updated_payload_count": updated_payload,
        "inserted_idempotency_record_count": inserted_idempotency,
        "sample_side_effect_candidates": [asdict(item) for item in side_candidates[:10]],
        "sample_idempotency_candidates": [
            asdict(item) for item in idempotency_candidates[:10]
        ],
        "safety": {
            "updates_runtime_receipts": True,
            "derives_side_effect_keys_from_current_contract": True,
            "derives_mission_from_recorded_delegation_or_fallback": True,
            "marks_payload_normalization": True,
            "overwrites_existing_mission_or_artifact_refs": False,
        },
    }


def _payload_for_receipt(db: sqlite3.Connection, receipt_id: str) -> dict[str, Any]:
    row = db.execute(
        "SELECT payload_json FROM runtime_receipts WHERE receipt_id = ?",
        (receipt_id,),
    ).fetchone()
    return _safe_json(row["payload_json"] if row is not None else "{}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_RUNTIME_DB)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="mutate runtime_receipts/idempotency_records; default is read-only",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = normalize_runtime_receipt_history(args.db, apply=bool(args.apply))
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"mode: {result['mode']}")
        print(f"db: {result['db_path']}")
        print(f"side_effect_key candidates: {result['counts']['side_effect_key_candidates']}")
        print(f"payload candidates: {result['counts']['payload_candidates']}")
        print(f"idempotency candidates: {result['counts']['idempotency_record_candidates']}")
        print(f"updated side_effect_key: {result['updated_side_effect_key_count']}")
        print(f"updated payloads: {result['updated_payload_count']}")
        print(f"inserted idempotency_records: {result['inserted_idempotency_record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
