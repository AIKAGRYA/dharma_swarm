#!/usr/bin/env python3
"""Report delivery/liveness state for A2A production-readiness quorum requests.

This script is read-only against NATS. It does not pull, ack, or consume agent
messages. It turns request packets, send receipts, reviewer records, and
optional live durable-consumer probes into one machine-readable status receipt.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO_ROOT / "reports" / "a2a" / "prod_readiness_quorum"
STATUS_SCHEMA = "dharma.a2a.prod_readiness_delivery_status.v1"
REVIEWER_SCHEMA = "dharma.a2a.prod_readiness_reviewer.v1"
TARGET_AGENT_ALIASES = {
    "hermes": "hermes_m5",
    "hermes-m5": "hermes_m5",
}

RunCommand = Callable[..., subprocess.CompletedProcess[str]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def request_paths(record_dir: Path) -> list[Path]:
    return sorted((record_dir / "requests").glob("*.json"))


def send_receipt_paths(record_dir: Path) -> list[Path]:
    legacy_paths = [
        path
        for path in record_dir.glob("*.json")
        if path.name.endswith("_NATS_SEND.json")
    ]
    governed_paths = list((record_dir / "send_receipts").glob("*.json"))
    return sorted(legacy_paths + governed_paths)


def reviewer_record_path(record_dir: Path, agent_id: str) -> Path:
    return record_dir / f"{agent_id}.json"


def load_requests(record_dir: Path) -> dict[str, dict[str, Any]]:
    requests: dict[str, dict[str, Any]] = {}
    for path in request_paths(record_dir):
        request = read_json(path)
        agent_id = str(request.get("target_agent_id") or path.stem)
        request["_source"] = str(path)
        requests[agent_id] = request
    return requests


def normalize_target_agent_id(agent_id: str) -> str:
    return TARGET_AGENT_ALIASES.get(agent_id, agent_id)


def target_agent_id_from_receipt(receipt: dict[str, Any]) -> str:
    explicit = receipt.get("target_agent_id")
    if isinstance(explicit, str) and explicit:
        return normalize_target_agent_id(explicit)
    request_file = receipt.get("file")
    if isinstance(request_file, str) and request_file:
        request_path = Path(request_file)
        if request_path.parent.name == "requests" and request_path.suffix == ".json":
            return normalize_target_agent_id(request_path.stem)
    for key in ("target_uid", "to"):
        value = receipt.get(key)
        if isinstance(value, str) and value:
            return normalize_target_agent_id(value)
    return ""


def load_send_receipts(record_dir: Path) -> dict[str, list[dict[str, Any]]]:
    receipts: dict[str, list[dict[str, Any]]] = {}
    for path in send_receipt_paths(record_dir):
        receipt = read_json(path)
        agent_id = target_agent_id_from_receipt(receipt)
        if not agent_id:
            continue
        receipt["_source"] = str(path)
        receipts.setdefault(agent_id, []).append(receipt)
    return receipts


def load_reviewer_record(record_dir: Path, agent_id: str) -> dict[str, Any] | None:
    path = reviewer_record_path(record_dir, agent_id)
    if not path.exists():
        return None
    record = read_json(path)
    record["_source"] = str(path)
    return record


def latest_send_receipt(receipts: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not receipts:
        return None
    return sorted(
        receipts,
        key=lambda item: str(item.get("created_at") or item.get("timestamp") or ""),
    )[-1]


def latest_consumer_witness_receipt(receipts: list[dict[str, Any]]) -> dict[str, Any] | None:
    witnessed = [
        receipt
        for receipt in receipts
        if isinstance(receipt.get("consumer_witness"), dict)
        and isinstance(receipt["consumer_witness"].get("consumer"), str)
        and receipt["consumer_witness"].get("consumer")
    ]
    return latest_send_receipt(witnessed)


def consumer_from_receipt(receipt: dict[str, Any] | None) -> str | None:
    if not receipt:
        return None
    witness = receipt.get("consumer_witness")
    if isinstance(witness, dict):
        consumer = witness.get("consumer")
        if isinstance(consumer, str) and consumer:
            return consumer
    return None


def subject_from_receipt(receipt: dict[str, Any] | None) -> str | None:
    if not receipt:
        return None
    subject = receipt.get("subject")
    return subject if isinstance(subject, str) and subject else None


def probe_consumer_info(
    *,
    context: str,
    stream: str,
    consumer: str,
    timeout_s: int,
    runner: RunCommand = subprocess.run,
) -> tuple[dict[str, Any] | None, str | None]:
    command = [
        "nats",
        "--context",
        context,
        f"--timeout={timeout_s}s",
        "consumer",
        "info",
        stream,
        consumer,
        "--json",
    ]
    result = runner(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_s + 5,
    )
    if result.returncode != 0:
        return None, (result.stderr or result.stdout or "nats consumer info failed").strip()
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return None, f"nats consumer info returned invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "nats consumer info returned non-object JSON"
    return payload, None


def consumer_summary(info: dict[str, Any] | None) -> dict[str, Any] | None:
    if info is None:
        return None
    config = info.get("config") if isinstance(info.get("config"), dict) else {}
    delivered = info.get("delivered") if isinstance(info.get("delivered"), dict) else {}
    ack_floor = info.get("ack_floor") if isinstance(info.get("ack_floor"), dict) else {}
    return {
        "name": info.get("name"),
        "filter_subject": config.get("filter_subject"),
        "deliver_policy": config.get("deliver_policy"),
        "ack_policy": config.get("ack_policy"),
        "max_deliver": config.get("max_deliver"),
        "delivered_consumer_seq": delivered.get("consumer_seq"),
        "delivered_stream_seq": delivered.get("stream_seq"),
        "ack_floor_consumer_seq": ack_floor.get("consumer_seq"),
        "ack_floor_stream_seq": ack_floor.get("stream_seq"),
        "num_pending": info.get("num_pending"),
        "num_ack_pending": info.get("num_ack_pending"),
        "num_redelivered": info.get("num_redelivered"),
        "num_waiting": info.get("num_waiting"),
    }


def classify_target(
    *,
    reviewer_record: dict[str, Any] | None,
    send_receipt: dict[str, Any] | None,
    consumer: str | None,
    consumer_info: dict[str, Any] | None,
    probe_error: str | None,
    probe_live: bool,
) -> str:
    if reviewer_record is not None:
        return "REVIEW_RECORD_PRESENT"
    if send_receipt is None:
        return "NOT_SENT"
    if consumer is None:
        return "NO_CONSUMER_WITNESS"
    if not probe_live:
        return "PUBLISH_ACCEPTED_NOT_DELIVERY_VERIFIED"
    if probe_error:
        return "DELIVERY_UNKNOWN_PROBE_FAILED"
    if consumer_info is None:
        return "DELIVERY_UNKNOWN_NO_CONSUMER_INFO"
    pending = consumer_info.get("num_pending")
    ack_pending = consumer_info.get("num_ack_pending")
    delivered = consumer_info.get("delivered")
    delivered_seq = delivered.get("consumer_seq") if isinstance(delivered, dict) else None
    if isinstance(pending, int) and pending > 0:
        return "PENDING_DELIVERY"
    if isinstance(ack_pending, int) and ack_pending > 0:
        return "DELIVERY_IN_PROGRESS_ACK_PENDING"
    if isinstance(delivered_seq, int) and delivered_seq > 0:
        return "DELIVERED_NO_REVIEW_RECORD"
    return "CONSUMER_EMPTY_NO_DELIVERY"


def build_delivery_status(
    *,
    root: Path,
    date: str,
    nats_context: str = "agni-wss",
    stream: str = "DHARMA_A2A",
    probe_live: bool = False,
    timeout_s: int = 30,
    runner: RunCommand = subprocess.run,
    created_at: str | None = None,
) -> dict[str, Any]:
    record_dir = root / date
    requests = load_requests(record_dir)
    send_receipts = load_send_receipts(record_dir)
    targets: list[dict[str, Any]] = []

    for agent_id in sorted(requests):
        request = requests[agent_id]
        receipts = send_receipts.get(agent_id, [])
        send_receipt = latest_send_receipt(receipts)
        consumer_witness_receipt = latest_consumer_witness_receipt(receipts)
        reviewer_record = load_reviewer_record(record_dir, agent_id)
        consumer = consumer_from_receipt(consumer_witness_receipt or send_receipt)
        subject = subject_from_receipt(send_receipt)
        if subject is None:
            subject = subject_from_receipt(consumer_witness_receipt)
        info: dict[str, Any] | None = None
        probe_error: str | None = None
        if probe_live and consumer:
            info, probe_error = probe_consumer_info(
                context=nats_context,
                stream=stream,
                consumer=consumer,
                timeout_s=timeout_s,
                runner=runner,
            )
        status = classify_target(
            reviewer_record=reviewer_record,
            send_receipt=send_receipt,
            consumer=consumer,
            consumer_info=info,
            probe_error=probe_error,
            probe_live=probe_live,
        )
        targets.append(
            {
                "target_agent_id": agent_id,
                "request_path": request.get("_source"),
                "reviewer_record_path": str(reviewer_record_path(record_dir, agent_id)),
                "reviewer_record_present": reviewer_record is not None,
                "requested_role": request.get("requested_role"),
                "model_family_hint": request.get("model_family_hint"),
                "send_receipt_count": len(receipts),
                "latest_send_receipt_path": send_receipt.get("_source") if send_receipt else None,
                "consumer_witness_receipt_path": consumer_witness_receipt.get("_source")
                if consumer_witness_receipt
                else None,
                "latest_send_status": send_receipt.get("status") if send_receipt else None,
                "latest_ack_tier": send_receipt.get("ack_tier") if send_receipt else None,
                "subject": subject,
                "consumer": consumer,
                "consumer_info": consumer_summary(info),
                "probe_error": probe_error,
                "delivery_status": status,
                "next_required_receipt": None
                if reviewer_record is not None
                else str(reviewer_record_path(record_dir, agent_id)),
            }
        )

    status_counts: dict[str, int] = {}
    for target in targets:
        key = str(target["delivery_status"])
        status_counts[key] = status_counts.get(key, 0) + 1

    missing_records = [
        target["target_agent_id"]
        for target in targets
        if not target["reviewer_record_present"]
    ]
    pending_delivery = [
        target["target_agent_id"]
        for target in targets
        if target["delivery_status"] == "PENDING_DELIVERY"
    ]
    delivered_without_record = [
        target["target_agent_id"]
        for target in targets
        if target["delivery_status"] == "DELIVERED_NO_REVIEW_RECORD"
    ]
    probe_errors = [
        target["target_agent_id"]
        for target in targets
        if target.get("probe_error")
    ]
    status = "ALL_REVIEW_RECORDS_PRESENT" if not missing_records else "PENDING_REVIEWER_RECORDS"
    return {
        "schema_version": STATUS_SCHEMA,
        "created_at": created_at or utc_now(),
        "date": date,
        "record_dir": str(record_dir),
        "nats_context": nats_context,
        "stream": stream,
        "probe_live": probe_live,
        "status": status,
        "production_claim": False,
        "summary": {
            "request_count": len(targets),
            "reviewer_records_present": len(targets) - len(missing_records),
            "reviewer_records_missing": len(missing_records),
            "sent_request_targets": sum(1 for target in targets if target["send_receipt_count"]),
            "pending_delivery_targets": pending_delivery,
            "delivered_without_record_targets": delivered_without_record,
            "probe_error_targets": probe_errors,
            "delivery_status_counts": status_counts,
        },
        "targets": targets,
        "next_required_actions": [
            f"{agent_id}: produce {reviewer_record_path(record_dir, agent_id)}"
            for agent_id in missing_records
        ],
    }


def write_status(root: Path, payload: dict[str, Any], *, write_latest: bool) -> Path:
    record_dir = Path(str(payload["record_dir"]))
    record_dir.mkdir(parents=True, exist_ok=True)
    output = record_dir / "QUORUM_DELIVERY_STATUS.json"
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    output.write_text(text, encoding="utf-8")
    if write_latest:
        root.mkdir(parents=True, exist_ok=True)
        (root / "latest_delivery_status.json").write_text(text, encoding="utf-8")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--nats-context", default="agni-wss")
    parser.add_argument("--stream", default="DHARMA_A2A")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--probe-live", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-latest", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build_delivery_status(
            root=args.root,
            date=args.date,
            nats_context=args.nats_context,
            stream=args.stream,
            probe_live=args.probe_live,
            timeout_s=args.timeout,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if args.write or args.write_latest:
        path = write_status(args.root, payload, write_latest=args.write_latest)
        payload["receipt_path"] = str(path)
    output = json.dumps(payload, indent=2, sort_keys=True)
    if args.json or not (args.write or args.write_latest):
        print(output)
    else:
        summary = payload["summary"]
        print(
            f"{payload['status']} requests={summary['request_count']} "
            f"missing_records={summary['reviewer_records_missing']} "
            f"receipt={payload['receipt_path']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
