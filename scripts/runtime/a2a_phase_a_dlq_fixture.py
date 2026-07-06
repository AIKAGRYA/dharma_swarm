#!/usr/bin/env python3
"""Write a Phase A fixture-backed NATS DLQ proof receipt.

The fixture uses the real ``A2ANatsTransport.consume_message`` max-deliver path
with an in-memory JetStream boundary. It proves poison delivery publishes a
typed ``dharma.nats.dlq_failure.v1`` envelope, records a runtime DLQ receipt,
and acks the original message instead of infinite-redelivering it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.a2a.a2a_server import A2AMessage, A2AServer, A2ATask  # noqa: E402
from dharma_swarm.a2a.nats_transport import A2ANatsTransport, NatsTransportConfig  # noqa: E402
from dharma_swarm.runtime_state import RuntimeStateStore  # noqa: E402
from dharma_swarm.spine.identity import ExecutionIdentity  # noqa: E402
from scripts.runtime.a2a_resident_executor import stamp, utc_now  # noqa: E402


@dataclass
class _FakePubAck:
    stream: str = "DS_TASKS"
    seq: int = 1


class _FakeJetStream:
    def __init__(self) -> None:
        self.published: list[tuple[str, bytes, dict[str, str] | None]] = []

    async def publish(
        self,
        subject: str,
        payload: bytes,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> _FakePubAck:
        del timeout
        self.published.append((subject, payload, headers))
        return _FakePubAck(seq=len(self.published))


class _FakeMessage:
    def __init__(self, subject: str, data: bytes, *, delivery_count: int) -> None:
        self.subject = subject
        self.data = data
        self.delivery_count = delivery_count
        self.acked = 0
        self.nacked = 0

    async def ack(self) -> None:
        self.acked += 1

    async def nak(self) -> None:
        self.nacked += 1

    @property
    def metadata(self) -> Any:
        return type(
            "FakeNatsMetadata",
            (),
            {
                "num_delivered": self.delivery_count,
                "stream": "DS_TASKS",
                "consumer": "a2a_task_handler",
            },
        )()


def _json_default(value: Any) -> str:
    return str(value)


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def _identity() -> ExecutionIdentity:
    return ExecutionIdentity.new(
        task_id="phase-a-dlq-task",
        agent_id="codex_composer",
        session_id="phase-a-dlq-fixture",
        trace_id="trace-phase-a-dlq",
        correlation_id="corr-phase-a-dlq",
        run_id=f"run-phase-a-dlq-{stamp()}",
        claim_id="claim-phase-a-dlq",
        idempotency_key=f"idem-phase-a-dlq-{stamp()}",
    )


def _task(identity: ExecutionIdentity) -> A2ATask:
    return A2ATask(
        id="phase-a-dlq-task",
        from_agent="operator",
        to_agent="worker",
        capability="probe",
        history=[A2AMessage.text("run poison probe")],
        metadata=identity.to_metadata(),
    )


async def run_dlq_fixture(*, receipt_root: Path) -> dict[str, Any]:
    runtime = RuntimeStateStore(receipt_root / "runtime_state" / "dlq_fixture_runtime.db")
    fake_js = _FakeJetStream()
    identity = _identity()
    server = A2AServer(runtime_state=runtime, persist=False, require_execution_identity=True)

    def handler(task: A2ATask) -> A2ATask:
        del task
        raise RuntimeError("phase-a poison message")

    server.register_handler("probe", handler)
    transport = A2ANatsTransport(
        runtime_state=runtime,
        server=server,
        jetstream=fake_js,
        config=NatsTransportConfig(max_deliveries=3),
    )
    await transport.publish_task(_task(identity), identity=identity)
    message = _FakeMessage("dharma.a2a.task.worker.probe", fake_js.published[0][1], delivery_count=3)
    ack = await transport.consume_message(message)
    if len(fake_js.published) < 2:
        raise RuntimeError("DLQ publish did not occur")
    dlq_subject, dlq_bytes, dlq_headers = fake_js.published[1]
    dlq_envelope = json.loads(dlq_bytes.decode("utf-8"))
    ledger = await runtime.get_run_ledger(identity.run_id)
    runtime_receipts = [
        {
            "receipt_id": receipt.receipt_id,
            "receipt_type": receipt.receipt_type,
            "status": receipt.status,
            "payload": receipt.payload,
        }
        for receipt in ledger["receipts"]
    ]
    proof = {
        "schema_version": "dharma.a2a.phase_a.dlq_fixture_receipt.v1",
        "timestamp": utc_now(),
        "status": "pass" if ack.status == "dlq" and message.acked == 1 and message.nacked == 0 else "fail",
        "proof_mode": "local_fixture",
        "transport_ack": {
            "task_id": ack.task_id,
            "subject": ack.subject,
            "action": ack.action,
            "status": ack.status,
            "receipt_id": ack.receipt_id,
            "message_id": ack.message_id,
            "error": ack.error,
        },
        "broker_side_effect": {
            "original_message_acked": message.acked,
            "original_message_nacked": message.nacked,
            "infinite_redelivery_prevented": message.acked == 1 and message.nacked == 0,
        },
        "dlq_publish": {
            "subject": dlq_subject,
            "headers": dlq_headers or {},
            "envelope": dlq_envelope,
            "payload_schema": (dlq_envelope.get("payload") or {}).get("schema"),
            "operator_blocker": (dlq_envelope.get("payload") or {}).get("operator_blocker"),
            "delivery_count": (dlq_envelope.get("payload") or {}).get("delivery_count"),
            "max_deliveries": (dlq_envelope.get("payload") or {}).get("max_deliveries"),
        },
        "runtime_receipts": runtime_receipts,
    }
    receipt_path = _write_json(receipt_root / f"PHASE_A_DLQ_FIXTURE_RECEIPT_{stamp()}.json", proof)
    proof["receipt_path"] = str(receipt_path)
    _write_json(receipt_path, proof)
    return proof


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--receipt-root", default=str(REPO_ROOT / "reports" / "a2a" / "phase_a" / "dlq_receipts"))
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    proof = asyncio.run(run_dlq_fixture(receipt_root=Path(args.receipt_root).expanduser().resolve()))
    if args.json:
        print(json.dumps(proof, indent=2, sort_keys=True, default=_json_default))
    else:
        print(
            " ".join(
                [
                    f"status={proof['status']}",
                    f"payload_schema={proof['dlq_publish']['payload_schema']}",
                    f"receipt_path={proof['receipt_path']}",
                ]
            )
        )
    return 0 if proof["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
