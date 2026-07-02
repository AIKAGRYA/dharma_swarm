#!/usr/bin/env python3
"""Dispatch prepared SAB flywheel A2A task packets into the local queue."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_QUEUE_PATH = Path("/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl")
DEFAULT_REPORTS_DIR = Path("reports/sab_first_six_agent_flywheel")
DEFAULT_MISSION_ID = "sab-first-six-agent-flywheel-20260627"
DEFAULT_INSTANCE_ID = "sab_agni_prod_157_245_193_15"
DEFAULT_RETURN_ADDRESS = "reports/sab_first_six_agent_flywheel/receipts/"
DENIED_BY_DEFAULT = {
    "setu-sab-agni": "admin_authority_required",
    "qwen_code": "external_provider_operator_approval_required",
}


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


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            parsed = json.loads(line)
            if not isinstance(parsed, dict):
                raise TypeError(f"{path}:{line_no} did not contain a JSON object")
            records.append(parsed)
    return records


def _packet_to_queue_record(packet: dict[str, Any], created_at: str, packet_path: Path) -> dict[str, Any]:
    evidence = packet.get("evidence") if isinstance(packet.get("evidence"), list) else []
    body = (
        f"{packet.get('title')}. Claim: {packet.get('claim')} "
        f"Action requested: {packet.get('action_requested')} "
        "Return a sab.semantic_receipt.v1 receipt; acknowledgement alone is failure."
    )
    record = {
        "id": packet["id"],
        "mission_id": packet.get("mission_id", DEFAULT_MISSION_ID),
        "type": "sab_first_six_agent_flywheel",
        "from": "codex_composer",
        "to": packet["to"],
        "created": created_at,
        "status": "pending",
        "priority": "medium",
        "body": body,
        "return_address": DEFAULT_RETURN_ADDRESS,
        "required_receipt_schema": "sab.semantic_receipt.v1",
        "semantic_receipt_required": True,
        "required_receipt_fields": packet.get("required_receipt_fields", []),
        "semantic_action_expected": packet.get("semantic_action_expected"),
        "sab_instance_id": DEFAULT_INSTANCE_ID,
        "source_packet_path": str(packet_path),
        "source_packet_status": packet.get("status"),
        "claim": packet.get("claim"),
        "evidence": evidence,
        "action_requested": packet.get("action_requested"),
    }
    for item in evidence:
        if isinstance(item, str) and item.startswith("latest_post_id_seen="):
            try:
                record["latest_post_id_seen"] = int(item.split("=", 1)[1])
            except ValueError:
                record["latest_post_id_seen"] = item.split("=", 1)[1]
        if isinstance(item, str) and item.startswith("latest_witness_hash_seen="):
            record["latest_witness_hash_seen"] = item.split("=", 1)[1]
    return record


def _select_packets(
    packets: list[dict[str, Any]],
    existing_ids: set[str],
    allow_blocked: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for packet in packets:
        task_id = str(packet.get("id", ""))
        target = str(packet.get("to", ""))
        if task_id in existing_ids:
            skipped.append({"id": task_id, "to": target, "reason": "already_in_queue"})
            continue
        denied_reason = DENIED_BY_DEFAULT.get(target)
        if denied_reason and not allow_blocked:
            skipped.append({"id": task_id, "to": target, "reason": denied_reason})
            continue
        if packet.get("blocker") and not allow_blocked:
            skipped.append({"id": task_id, "to": target, "reason": "packet_has_blocker"})
            continue
        selected.append(packet)
    return selected, skipped


def _validate_packets(packets: list[dict[str, Any]]) -> None:
    required = {
        "id",
        "mission_id",
        "to",
        "title",
        "status",
        "semantic_receipt_required",
        "required_receipt_fields",
        "semantic_action_expected",
        "claim",
        "evidence",
        "action_requested",
    }
    for idx, packet in enumerate(packets, start=1):
        missing = sorted(required - set(packet))
        if missing:
            raise ValueError(f"packet line {idx} missing {missing}")
        if packet.get("semantic_receipt_required") is not True:
            raise ValueError(f"packet line {idx} does not require semantic receipt")


def _write_receipt(
    *,
    reports_dir: Path,
    created_at: str,
    packet_path: Path,
    queue_path: Path,
    mode: str,
    selected: list[dict[str, Any]],
    skipped: list[dict[str, str]],
    existing_before: int,
    existing_after: int,
) -> Path:
    stamp = _stamp(created_at)
    receipt_path = reports_dir / f"A2A_DAY2_PACKET_DISPATCH_RECEIPT_{stamp}.json"
    receipt = {
        "schema": "sab_first_six_agent_flywheel.a2a_packet_dispatch_receipt.v1",
        "mission_id": DEFAULT_MISSION_ID,
        "created_at_utc": created_at,
        "mode": mode,
        "packet_path": str(packet_path),
        "queue_path": str(queue_path),
        "existing_queue_records_before": existing_before,
        "existing_queue_records_after": existing_after,
        "selected_count": len(selected),
        "selected_task_ids": [str(packet["id"]) for packet in selected],
        "skipped_count": len(skipped),
        "skipped": skipped,
        "safety": {
            "default_denies": DENIED_BY_DEFAULT,
            "tokens_or_secrets_written": False,
            "external_provider_invoked": False,
            "admin_action_performed": False,
        },
    }
    receipt_path.write_text(_json_dumps(receipt) + "\n", encoding="utf-8")
    return receipt_path


def _write_semantic_receipt(
    *,
    reports_dir: Path,
    created_at: str,
    mode: str,
    selected: list[dict[str, Any]],
    skipped: list[dict[str, str]],
    dispatch_receipt_path: Path,
) -> Path:
    stamp = _stamp(created_at)
    receipt_path = (
        reports_dir
        / "receipts"
        / f"sab-flywheel-d02-safe-a2a-dispatch-{stamp}.semantic_receipt.json"
    )
    latest_post_id = None
    latest_witness_hash = ""
    for packet in selected:
        for item in packet.get("evidence", []):
            if isinstance(item, str) and item.startswith("latest_post_id_seen="):
                latest_post_id = item.split("=", 1)[1]
            if isinstance(item, str) and item.startswith("latest_witness_hash_seen="):
                latest_witness_hash = item.split("=", 1)[1]
    try:
        latest_post_id_value: int | str | None = int(latest_post_id) if latest_post_id else None
    except ValueError:
        latest_post_id_value = latest_post_id
    receipt = {
        "schema": "sab.semantic_receipt.v1",
        "task_id": "sab-flywheel-d02-safe-a2a-dispatch",
        "agent": "codex_composer_mac",
        "sab_instance_id": DEFAULT_INSTANCE_ID,
        "latest_post_id_seen": latest_post_id_value,
        "latest_witness_hash_seen": latest_witness_hash,
        "semantic_action": "synthesis",
        "claim": (
            "Day 2 can be handed to the local A2A fleet for non-admin, non-external-provider work while preserving explicit gates for SETU and Qwen."
        ),
        "evidence": [
            f"mode={mode}",
            f"dispatch_receipt={dispatch_receipt_path}",
            f"selected_task_ids={[packet['id'] for packet in selected]}",
            f"skipped={skipped}",
        ],
        "action_taken": (
            "Dispatched safe local Day 2 task packets to the A2A queue."
            if mode == "append"
            else "Dry-ran safe local Day 2 task packet dispatch."
        ),
        "next_request": "Complete queued Day 2 semantic receipts, drain SETU moderation with admin authority, and keep Qwen gated until explicit operator approval.",
        "created_at": created_at,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(_json_dumps(receipt) + "\n", encoding="utf-8")
    return receipt_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet_path", type=Path)
    parser.add_argument("--queue-path", type=Path, default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--allow-blocked", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    created_at = _utc_now()
    packets = _load_jsonl(args.packet_path)
    _validate_packets(packets)
    existing = _load_jsonl(args.queue_path)
    existing_ids = {str(record.get("id")) for record in existing}
    selected, skipped = _select_packets(packets, existing_ids, args.allow_blocked)
    records = [
        _packet_to_queue_record(packet, created_at, args.packet_path)
        for packet in selected
    ]

    mode = "append" if args.append else "dry_run"
    existing_after = len(existing)
    if args.append and records:
        with args.queue_path.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        existing_after += len(records)

    receipt_path = _write_receipt(
        reports_dir=args.reports_dir,
        created_at=created_at,
        packet_path=args.packet_path,
        queue_path=args.queue_path,
        mode=mode,
        selected=selected,
        skipped=skipped,
        existing_before=len(existing),
        existing_after=existing_after,
    )
    semantic_receipt_path = _write_semantic_receipt(
        reports_dir=args.reports_dir,
        created_at=created_at,
        mode=mode,
        selected=selected,
        skipped=skipped,
        dispatch_receipt_path=receipt_path,
    )
    print(str(receipt_path))
    print(str(semantic_receipt_path))
    print(f"mode={mode} selected={len(selected)} skipped={len(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
