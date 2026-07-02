#!/usr/bin/env python3
"""Record SAB flywheel semantic receipts against local A2A queue tasks."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_QUEUE_PATH = Path("/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl")
DEFAULT_REPORTS_DIR = Path("reports/sab_first_six_agent_flywheel")
DEFAULT_MISSION_ID = "sab-first-six-agent-flywheel-20260627"


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stamp(created_at_utc: str) -> str:
    return created_at_utc.replace("-", "").replace(":", "")[:13] + "Z"


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise TypeError(f"{path} did not contain a JSON object")
    return data


def _load_queue(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            data = json.loads(line)
            if not isinstance(data, dict):
                raise TypeError(f"{path}:{line_no} did not contain a JSON object")
            records.append(data)
    return records


def _validate_receipt(path: Path) -> dict[str, Any]:
    receipt = _load_json(path)
    if receipt.get("schema") != "sab.semantic_receipt.v1":
        raise ValueError(f"{path} schema is not sab.semantic_receipt.v1")
    required = {
        "task_id",
        "agent",
        "sab_instance_id",
        "latest_post_id_seen",
        "latest_witness_hash_seen",
        "semantic_action",
        "claim",
        "evidence",
        "action_taken",
        "next_request",
    }
    missing = sorted(required - set(receipt))
    if missing:
        raise ValueError(f"{path} missing receipt fields {missing}")
    return receipt


def _apply_receipt(
    records: list[dict[str, Any]],
    receipt: dict[str, Any],
    receipt_path: Path,
    completed_at: str,
) -> tuple[bool, str]:
    task_id = str(receipt["task_id"])
    for record in records:
        if record.get("id") != task_id:
            continue
        if record.get("mission_id") not in (DEFAULT_MISSION_ID, None):
            return False, f"{task_id}: mission mismatch"
        if record.get("status") == "completed":
            return False, f"{task_id}: already completed"
        record.update(
            {
                "status": "completed",
                "completed": completed_at,
                "completed_at": completed_at,
                "completed_by": receipt["agent"],
                "closed_at": completed_at,
                "closed_by": receipt["agent"],
                "receipt_path": str(receipt_path),
                "receipt_id": f"sab.semantic_receipt:{task_id}:{_stamp(completed_at)}",
                "receipt_validation": {
                    "schema": "sab.semantic_receipt.v1",
                    "valid": True,
                },
                "semantic_action": receipt["semantic_action"],
                "latest_post_id_seen": receipt["latest_post_id_seen"],
                "latest_witness_hash_seen": receipt["latest_witness_hash_seen"],
            }
        )
        return True, f"{task_id}: completed"
    return False, f"{task_id}: not found"


def _write_queue(path: Path, records: list[dict[str, Any]]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _write_update_receipt(
    *,
    reports_dir: Path,
    created_at: str,
    mode: str,
    queue_path: Path,
    results: list[dict[str, Any]],
) -> Path:
    path = reports_dir / f"A2A_TASK_RECEIPT_RECORDING_{_stamp(created_at)}.json"
    payload = {
        "schema": "sab_first_six_agent_flywheel.a2a_task_receipt_recording.v1",
        "mission_id": DEFAULT_MISSION_ID,
        "created_at_utc": created_at,
        "mode": mode,
        "queue_path": str(queue_path),
        "results": results,
        "updated_count": sum(1 for result in results if result["updated"]),
    }
    path.write_text(_json_dumps(payload) + "\n", encoding="utf-8")
    return path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipts", nargs="+", type=Path)
    parser.add_argument("--queue-path", type=Path, default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    created_at = _utc_now()
    records = _load_queue(args.queue_path)
    results: list[dict[str, Any]] = []
    for receipt_path in args.receipts:
        receipt = _validate_receipt(receipt_path)
        updated, message = _apply_receipt(records, receipt, receipt_path, created_at)
        results.append(
            {
                "receipt_path": str(receipt_path),
                "task_id": receipt["task_id"],
                "updated": updated,
                "message": message,
            }
        )
    mode = "write" if args.write else "dry_run"
    if args.write:
        _write_queue(args.queue_path, records)
    update_receipt = _write_update_receipt(
        reports_dir=args.reports_dir,
        created_at=created_at,
        mode=mode,
        queue_path=args.queue_path,
        results=results,
    )
    print(str(update_receipt))
    print(f"mode={mode} updated={sum(1 for result in results if result['updated'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
