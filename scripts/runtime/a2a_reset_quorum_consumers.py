#!/usr/bin/env python3
"""Reset selected A2A quorum consumers with before/after receipts.

This is an explicit reset path. It does not claim peer delivery, review,
handler acknowledgement, or semantic agreement.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "dharma.a2a.quorum_consumer_reset.v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATE = "2026-06-13"
DEFAULT_RECEIPT = (
    REPO_ROOT
    / "reports"
    / "a2a"
    / "nats_reset"
    / DEFAULT_DATE
    / "A2A_QUORUM_CONSUMER_RESET_APPLIED.json"
)
DEFAULT_TARGETS = (
    "fable_composer_inbox=dharma.a2a.fable_composer",
    "claude_from_hermes=dharma.a2a.hermes",
)

RunCommand = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class ResetTarget:
    consumer: str
    filter_subject: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_target(raw: str) -> ResetTarget:
    if "=" not in raw:
        raise ValueError(f"target must be CONSUMER=FILTER_SUBJECT: {raw}")
    consumer, subject = raw.split("=", 1)
    consumer = consumer.strip()
    subject = subject.strip()
    if not consumer or not subject:
        raise ValueError(f"target must be CONSUMER=FILTER_SUBJECT: {raw}")
    return ResetTarget(consumer=consumer, filter_subject=subject)


def run_command(
    command: list[str],
    *,
    timeout_s: int,
    runner: RunCommand = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    return runner(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_s + 5,
    )


def command_record(command: list[str], result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
    }


def consumer_info(
    *,
    context: str,
    stream: str,
    consumer: str,
    timeout_s: int,
    runner: RunCommand = subprocess.run,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
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
    result = run_command(command, timeout_s=timeout_s, runner=runner)
    record = command_record(command, result)
    if result.returncode != 0:
        return None, record
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        record["parse_error"] = str(exc)
        return None, record
    if not isinstance(payload, dict):
        record["parse_error"] = "consumer info returned non-object JSON"
        return None, record
    return payload, record


def reset_commands(
    *,
    context: str,
    stream: str,
    target: ResetTarget,
    timeout_s: int,
    max_deliver: int,
    max_pending: int,
    runner: RunCommand = subprocess.run,
) -> list[dict[str, Any]]:
    commands = [
        [
            "nats",
            "--context",
            context,
            f"--timeout={timeout_s}s",
            "consumer",
            "rm",
            stream,
            target.consumer,
            "--force",
        ],
        [
            "nats",
            "--context",
            context,
            f"--timeout={timeout_s}s",
            "consumer",
            "add",
            stream,
            target.consumer,
            "--pull",
            "--filter",
            target.filter_subject,
            "--deliver",
            "new",
            "--ack",
            "explicit",
            "--max-deliver",
            str(max_deliver),
            "--max-pending",
            str(max_pending),
            "--defaults",
        ],
    ]
    return [
        command_record(command, run_command(command, timeout_s=timeout_s, runner=runner))
        for command in commands
    ]


def summarize_info(info: dict[str, Any] | None) -> dict[str, Any] | None:
    if info is None:
        return None
    config = info.get("config") if isinstance(info.get("config"), dict) else {}
    delivered = info.get("delivered") if isinstance(info.get("delivered"), dict) else {}
    return {
        "name": info.get("name"),
        "filter_subject": config.get("filter_subject"),
        "deliver_policy": config.get("deliver_policy"),
        "ack_policy": config.get("ack_policy"),
        "max_deliver": config.get("max_deliver"),
        "delivered_stream_seq": delivered.get("stream_seq"),
        "num_pending": info.get("num_pending"),
        "num_ack_pending": info.get("num_ack_pending"),
        "num_redelivered": info.get("num_redelivered"),
        "num_waiting": info.get("num_waiting"),
    }


def target_reset_receipt(
    *,
    context: str,
    stream: str,
    target: ResetTarget,
    apply: bool,
    timeout_s: int,
    max_deliver: int,
    max_pending: int,
    runner: RunCommand = subprocess.run,
) -> dict[str, Any]:
    before_info, before_command = consumer_info(
        context=context,
        stream=stream,
        consumer=target.consumer,
        timeout_s=timeout_s,
        runner=runner,
    )
    mutation_commands: list[dict[str, Any]] = []
    if apply:
        mutation_commands = reset_commands(
            context=context,
            stream=stream,
            target=target,
            timeout_s=timeout_s,
            max_deliver=max_deliver,
            max_pending=max_pending,
            runner=runner,
        )
    after_info, after_command = consumer_info(
        context=context,
        stream=stream,
        consumer=target.consumer,
        timeout_s=timeout_s,
        runner=runner,
    )
    mutation_ok = all(record["returncode"] == 0 for record in mutation_commands)
    return {
        "consumer": target.consumer,
        "filter_subject": target.filter_subject,
        "before": summarize_info(before_info),
        "after": summarize_info(after_info),
        "commands": {
            "before_info": before_command,
            "mutation": mutation_commands,
            "after_info": after_command,
        },
        "mutation_applied": apply,
        "mutation_ok": mutation_ok if apply else None,
        "reset_interpretation": (
            "Consumer state was reset to deliver only new future messages. "
            "Existing stream messages were not semantic peer responses."
        ),
    }


def build_reset_receipt(
    *,
    targets: list[ResetTarget],
    context: str,
    stream: str,
    apply: bool,
    timeout_s: int,
    max_deliver: int,
    max_pending: int,
    runner: RunCommand = subprocess.run,
    created_at: str | None = None,
) -> dict[str, Any]:
    target_receipts = [
        target_reset_receipt(
            context=context,
            stream=stream,
            target=target,
            apply=apply,
            timeout_s=timeout_s,
            max_deliver=max_deliver,
            max_pending=max_pending,
            runner=runner,
        )
        for target in targets
    ]
    failures = [
        item["consumer"]
        for item in target_receipts
        if item["mutation_applied"] and not item["mutation_ok"]
    ]
    after_pending_total = sum(
        int(item["after"].get("num_pending") or 0)
        for item in target_receipts
        if isinstance(item.get("after"), dict)
    )
    status = "APPLIED" if apply and not failures else "DRY_RUN" if not apply else "FAILED"
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at or utc_now(),
        "status": status,
        "production_claim": False,
        "context": context,
        "stream": stream,
        "operation": "delete_and_recreate_selected_durable_consumers_deliver_new",
        "mutation_applied": apply,
        "stream_messages_mutated": False,
        "targets": target_receipts,
        "summary": {
            "target_count": len(target_receipts),
            "failed_consumers": failures,
            "after_pending_total": after_pending_total,
        },
        "interpretation": (
            "This resets stale quorum consumer state only. It does not prove "
            "peer delivery, reviewer consensus, handler ack, or domain receipt."
        ),
    }


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", default="agni-wss")
    parser.add_argument("--stream", default="DHARMA_A2A")
    parser.add_argument("--target", action="append", default=list(DEFAULT_TARGETS))
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--max-deliver", type=int, default=5)
    parser.add_argument("--max-pending", type=int, default=1000)
    parser.add_argument("--receipt-path", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--apply", action="store_true", help="Delete and recreate the consumers.")
    parser.add_argument("--write", action="store_true", help="Write the JSON receipt.")
    parser.add_argument("--json", action="store_true", help="Print full JSON output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    targets = [parse_target(raw) for raw in args.target]
    payload = build_reset_receipt(
        targets=targets,
        context=args.context,
        stream=args.stream,
        apply=args.apply,
        timeout_s=args.timeout,
        max_deliver=args.max_deliver,
        max_pending=args.max_pending,
    )
    if args.write:
        write_receipt(Path(args.receipt_path).expanduser(), payload)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"{payload['status']} targets={payload['summary']['target_count']} "
            f"after_pending_total={payload['summary']['after_pending_total']}"
        )
    return 0 if payload["status"] != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
