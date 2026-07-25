#!/usr/bin/env python3
"""Run the live Runtime Truth NATS production evidence matrix.

This script intentionally uses a live NATS/JetStream broker and the governed
``A2ANatsTransport.publish_task`` path for task publication. It writes a
machine-readable receipt suitable for governance gates and hostile review.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.a2a.a2a_server import A2AMessage, A2AServer, A2ATask, A2ATaskStatus  # noqa: E402
from dharma_swarm.a2a.nats_transport import (  # noqa: E402
    A2ANatsTransport,
    NatsPublishAck,
    NatsTransportConfig,
    NatsTransportError,
)
from dharma_swarm.models import LLMRequest, ProviderType  # noqa: E402
from dharma_swarm.runtime_provider import (  # noqa: E402
    create_runtime_provider,
    resolve_runtime_provider_config,
)
from dharma_swarm.runtime_state import RuntimeStateStore  # noqa: E402
from dharma_swarm.spine.identity import ExecutionIdentity  # noqa: E402


DEFAULT_EVIDENCE_ROOT = ROOT / "reports" / "governance" / "nats_live_production_matrix"
DEFAULT_A2A_ROOT = ROOT / "reports" / "a2a" / "nats_live_production_matrix"

PUBLISH_ENTRYPOINT = "dharma_swarm.a2a.nats_transport.A2ANatsTransport.publish_task"
CONSUME_ENTRYPOINT = "dharma_swarm.a2a.nats_transport.A2ANatsTransport.consume_message"
TRANSPORT_CLASS = "dharma_swarm.a2a.nats_transport.A2ANatsTransport"
CONSUMER_CLASS = "dharma_swarm.a2a.a2a_server.A2AServer"

SOURCE_FRESHNESS_PATHS = [
    "Makefile",
    "dharma_swarm/a2a/nats_transport.py",
    "dharma_swarm/a2a/nats_transport_support.py",
    "dharma_swarm/a2a/a2a_server.py",
    "dharma_swarm/a2a/a2a_bridge.py",
    "dharma_swarm/runtime_state.py",
    "dharma_swarm/operator_core/nats_live_contact.py",
    "dharma_swarm/operator_core/nats_substrate_status.py",
    "dharma_swarm/a2a/a2a_cloud_contact.py",
    "scripts/runtime/a2a_send.py",
    "scripts/runtime/a2a_inbox_bridge.py",
    "scripts/runtime/a2a_domain_reply_worker.py",
    "scripts/runtime/a2a_reply_capture.py",
    "scripts/governance/check_nats_substrate_contract.py",
    "scripts/governance/check_nats_live_production_evidence.py",
    "scripts/governance/run_nats_live_production_matrix.py",
    "scripts/governance/check_track_status.py",
    "tests/test_nats_transport.py",
    "tests/test_nats_live_contact.py",
    "tests/test_nats_live_production_evidence.py",
    "tests/test_nats_substrate_contract.py",
    "tests/test_nats_verification_split.py",
    "tests/test_a2a_cloud_contact.py",
    "docs/governance/ACTIVE_TRACK.yaml",
    "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md",
]


class MatrixFailure(RuntimeError):
    """Raised when a required live matrix row cannot be proven."""


def import_nats_client() -> Any:
    try:
        import nats
    except ImportError as exc:
        raise MatrixFailure("nats-py is required to run the live NATS production matrix") from exc
    return nats


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if dataclasses.is_dataclass(value):
        return jsonable(dataclasses.asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def source_fingerprints() -> dict[str, dict[str, Any]]:
    fingerprints: dict[str, dict[str, Any]] = {}
    for rel in SOURCE_FRESHNESS_PATHS:
        path = ROOT / rel
        if not path.exists():
            fingerprints[rel] = {"exists": False}
            continue
        data = path.read_bytes()
        stat = path.stat()
        fingerprints[rel] = {
            "exists": True,
            "mtime": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat().replace("+00:00", "Z"),
            "size": stat.st_size,
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    return fingerprints


def run_command(command: list[str], cwd: Path = ROOT) -> dict[str, Any]:
    started = utc_now()
    proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    return {
        "timestamp": started,
        "command": command,
        "return_code": proc.returncode,
        "stdout": proc.stdout[-12000:],
        "stderr": proc.stderr[-12000:],
    }


def msg_metadata(message: Any) -> dict[str, Any]:
    try:
        meta = message.metadata
    except Exception as exc:  # pragma: no cover - defensive for broker/client drift
        return {"error": f"{type(exc).__name__}: {exc}"}
    sequence = getattr(meta, "sequence", None)
    num_delivered = getattr(meta, "num_delivered", None)
    timestamp = getattr(meta, "timestamp", None)
    return {
        "stream_sequence": getattr(sequence, "stream", None),
        "consumer_sequence": getattr(sequence, "consumer", None),
        "num_delivered": num_delivered,
        "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
    }


def decode_envelope(message: Any) -> dict[str, Any]:
    return json.loads(message.data.decode("utf-8"))


def message_headers(message: Any) -> dict[str, Any]:
    headers = getattr(message, "headers", None) or {}
    return {str(k): str(v) for k, v in headers.items()}


def is_broker_acked(ack: dict[str, Any] | None) -> bool:
    if not ack:
        return False
    return ack.get("status") in {"ack", "dlq", "duplicate"} and ack.get("action") in {"ack", "dlq"}


def side_effect_key(task_id: str, label: str) -> str:
    return f"{task_id}:{label}"


class ModelProbe:
    def __init__(self, provider: str, model: str, timeout_seconds: float, receipt_dir: Path) -> None:
        self.provider = provider
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.receipt_dir = receipt_dir
        self.calls = 0

    def call(self, prompt: str, task_id: str, trace_id: str) -> dict[str, Any]:
        self.calls += 1
        started = utc_now()
        receipt_path = self.receipt_dir / f"{task_id}.semantic_receipt.json"
        if self.provider in {"deterministic", "offline", "local-deterministic"}:
            digest = hashlib.sha256(f"{task_id}\n{trace_id}\n{prompt}".encode("utf-8")).hexdigest()
            receipt = {
                "schema": "dharma.nats.live_matrix.semantic_receipt.v1",
                "timestamp": utc_now(),
                "provider": self.provider,
                "requested_model": self.model,
                "response_model": self.model,
                "usage": {"prompt_chars": len(prompt), "completion_chars": 96},
                "content": json.dumps(
                    {
                        "ok": True,
                        "mode": "deterministic_transport_probe",
                        "task_id": task_id,
                        "digest": digest[:16],
                    },
                    sort_keys=True,
                ),
                "task_id": task_id,
                "trace_id": trace_id,
                "started_at": started,
            }
            write_json(receipt_path, receipt)
            receipt["receipt_path"] = str(receipt_path)
            return receipt
        result_box: dict[str, Any] = {}

        def target() -> None:
            async def invoke() -> dict[str, Any]:
                cfg = resolve_runtime_provider_config(
                    ProviderType(self.provider),
                    model=self.model,
                    timeout_seconds=self.timeout_seconds,
                )
                runtime = create_runtime_provider(cfg)
                request = LLMRequest(
                    model=cfg.default_model or self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a live handler. Return compact JSON only.",
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    max_tokens=256,
                    temperature=0.0,
                )
                response = await asyncio.wait_for(runtime.complete(request), timeout=self.timeout_seconds)
                return {
                    "schema": "dharma.nats.live_matrix.semantic_receipt.v1",
                    "timestamp": utc_now(),
                    "provider": self.provider,
                    "requested_model": self.model,
                    "response_model": response.model,
                    "usage": response.usage,
                    "content": response.content,
                    "task_id": task_id,
                    "trace_id": trace_id,
                }

            try:
                result_box["value"] = asyncio.run(invoke())
            except Exception as exc:  # pragma: no cover - depends on live provider
                result_box["error"] = f"{type(exc).__name__}: {exc}"

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(self.timeout_seconds + 5)
        if thread.is_alive():
            raise MatrixFailure(f"model handler timed out after {self.timeout_seconds}s")
        if "error" in result_box:
            raise MatrixFailure(f"model handler failed: {result_box['error']}")
        receipt = result_box["value"]
        receipt["started_at"] = started
        write_json(receipt_path, receipt)
        receipt["receipt_path"] = str(receipt_path)
        return receipt


class SideEffectLedger:
    def __init__(self) -> None:
        self.effects: dict[str, int] = {}

    def add(self, key: str) -> int:
        self.effects[key] = self.effects.get(key, 0) + 1
        return self.effects[key]

    def count(self, key: str) -> int:
        return self.effects.get(key, 0)


class AckFailMessage:
    """A live NATS message wrapper that forces the broker ack call to fail."""

    def __init__(self, message: Any, error: Exception | None = None) -> None:
        self._message = message
        self._error = error or RuntimeError("forced broker ack failure for matrix row")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._message, name)

    async def ack(self) -> None:
        raise self._error

    async def nak(self) -> None:
        await self._message.nak()


class DLQFailingJetStream:
    def __init__(self, jetstream: Any) -> None:
        self._jetstream = jetstream

    def __getattr__(self, name: str) -> Any:
        return getattr(self._jetstream, name)

    async def publish(self, subject: str, *args: Any, **kwargs: Any) -> Any:
        if subject.startswith("dharma.dlq."):
            raise RuntimeError("forced DLQ publish failure for matrix row")
        return await self._jetstream.publish(subject, *args, **kwargs)


class PublishFailingJetStream:
    def __init__(self, jetstream: Any) -> None:
        self._jetstream = jetstream

    def __getattr__(self, name: str) -> Any:
        return getattr(self._jetstream, name)

    async def publish(self, subject: str, *args: Any, **kwargs: Any) -> Any:
        if subject.startswith("dharma.a2a.task."):
            raise RuntimeError("forced task publish failure for matrix row")
        return await self._jetstream.publish(subject, *args, **kwargs)


class MatrixRunner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.run_id = f"nats-live-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        self.safe_run_id = self.run_id.replace("-", "_").replace(":", "_")
        self.evidence_dir = Path(args.output_dir or DEFAULT_EVIDENCE_ROOT / self.run_id).resolve()
        self.a2a_dir = Path(args.a2a_output_dir or DEFAULT_A2A_ROOT / self.run_id).resolve()
        self.runtime_db = self.evidence_dir / "runtime_state.sqlite"
        self.receipts_dir = self.a2a_dir / "receipts"
        self.endpoint = args.endpoint
        self.stream = args.stream
        self.dlq_stream = args.dlq_stream
        self.consumer = args.consumer
        self.config = NatsTransportConfig(
            endpoint=self.endpoint,
            stream_name=self.stream,
            dlq_stream_name=self.dlq_stream,
            consumer_name=self.consumer,
            max_deliveries=args.max_deliveries,
            idempotency_stale_after_s=args.idempotency_stale_after_s,
        )
        self.runtime = RuntimeStateStore(self.runtime_db)
        self.ledger = SideEffectLedger()
        self.model_probe = ModelProbe(args.provider, args.model, args.model_timeout, self.receipts_dir)
        self.rows: list[dict[str, Any]] = []
        self.commands: list[dict[str, Any]] = []
        self.nc: Any = None
        self.js: Any = None

    async def connect(self) -> None:
        nats_client = import_nats_client()
        self.nc = await nats_client.connect(self.endpoint)
        self.js = self.nc.jetstream()

    async def close(self) -> None:
        if self.nc is not None and not self.nc.is_closed:
            await self.nc.drain()

    def identity(self, label: str, task_id: str | None = None) -> ExecutionIdentity:
        resolved_task_id = task_id or f"{label}-{uuid.uuid4().hex[:8]}"
        identity_run_id = f"{self.run_id}:{label}:{resolved_task_id}"
        trace = identity_run_id
        return ExecutionIdentity.new(
            run_id=identity_run_id,
            agent_id=f"nats-live-matrix-{label}",
            session_id=self.run_id,
            task_id=resolved_task_id,
            trace_id=trace,
            correlation_id=trace,
            causation_id=trace,
            claim_id=f"claim-{identity_run_id}",
            idempotency_key=f"{identity_run_id}:idem",
            parent_run_id=self.run_id,
        )

    def task(self, label: str, payload: dict[str, Any] | None = None) -> A2ATask:
        task_id = f"{self.safe_run_id}_{label}_{uuid.uuid4().hex[:8]}"
        return A2ATask(
            id=task_id,
            from_agent="nats_live_matrix",
            to_agent=f"{self.safe_run_id}_{label}",
            capability=f"matrix_{label}",
            messages=[
                A2AMessage.text(
                    json.dumps(payload or {"label": label, "run_id": self.run_id}, sort_keys=True)
                )
            ],
        )

    def handler_contract(self, handler: Callable[[A2ATask], A2ATask] | None) -> dict[str, Any] | None:
        if handler is None:
            return None
        return {
            "callable": f"{handler.__module__}.{handler.__qualname__}",
            "name": getattr(handler, "__name__", ""),
            "module": getattr(handler, "__module__", ""),
            "qualname": getattr(handler, "__qualname__", ""),
        }

    def production_path_contract(
        self,
        handler: Callable[[A2ATask], A2ATask] | None,
        *,
        consumes: bool = True,
    ) -> dict[str, Any]:
        return {
            "publish_entrypoint": PUBLISH_ENTRYPOINT,
            "transport_class": TRANSPORT_CLASS,
            "consume_entrypoint": CONSUME_ENTRYPOINT if consumes else None,
            "consumer_class": CONSUMER_CLASS if consumes else None,
            "consumer_require_execution_identity": True if consumes else None,
            "handler_contract": self.handler_contract(handler) if consumes else None,
            "compatibility_publishers_can_satisfy_production_gate": False,
        }

    async def publish_task(self, task: A2ATask, identity: ExecutionIdentity) -> NatsPublishAck:
        transport = A2ANatsTransport(runtime_state=self.runtime, jetstream=self.js, config=self.config)
        return await transport.publish_task(task, identity=identity)

    async def subscribe(self) -> Any:
        return await self.js.pull_subscribe(
            "dharma.a2a.task.>",
            durable=self.consumer,
            stream=self.stream,
        )

    async def fetch_matching(
        self,
        label: str,
        expected_task_id: str,
        timeout_seconds: float = 15,
        batch: int = 4,
    ) -> Any:
        deadline = time.monotonic() + timeout_seconds
        sub = await self.subscribe()
        last_error: str | None = None
        while time.monotonic() < deadline:
            try:
                messages = await sub.fetch(batch=batch, timeout=min(2, max(0.2, deadline - time.monotonic())))
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                await asyncio.sleep(0.2)
                continue
            for msg in messages:
                try:
                    envelope = decode_envelope(msg)
                    body = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
                    task = body.get("task") if isinstance(body.get("task"), dict) else envelope.get("task")
                    task_id = task.get("id") if isinstance(task, dict) else None
                except Exception:
                    task_id = None
                if task_id == expected_task_id:
                    return msg
                # This durable is production-scoped. Do not ack unrelated work.
                await msg.nak()
        raise MatrixFailure(f"{label}: did not receive task_id={expected_task_id}; last_error={last_error}")

    async def consume_with_handler(
        self,
        message: Any,
        handler: Callable[[A2ATask], A2ATask],
        *,
        stale_after_s: int | None = None,
        jetstream: Any | None = None,
    ) -> dict[str, Any]:
        server = A2AServer(runtime_state=self.runtime, persist=False, require_execution_identity=True)
        server.set_default_handler(handler)
        contract = self.production_path_contract(handler)
        contract["consumer_require_execution_identity"] = bool(
            getattr(server, "_require_execution_identity", False)
        )
        cfg = dataclasses.replace(
            self.config,
            idempotency_stale_after_s=stale_after_s
            if stale_after_s is not None
            else self.config.idempotency_stale_after_s,
        )
        transport = A2ANatsTransport(
            runtime_state=self.runtime,
            server=server,
            jetstream=jetstream or self.js,
            config=cfg,
        )
        envelope: dict[str, Any] = {}
        identity: ExecutionIdentity | None = None
        try:
            envelope = decode_envelope(message)
            identity = ExecutionIdentity.from_metadata(
                envelope.get("execution_identity") or envelope.get("payload", {}).get("execution_identity"),
                require=True,
            )
        except Exception:
            identity = None
        started = time.monotonic()
        try:
            ack = await transport.consume_message(message)
            ack_payload = dataclasses.asdict(ack)
        except NatsTransportError as exc:
            receipts = []
            if identity is not None:
                receipts = await self.runtime.list_runtime_receipts(
                    run_id=identity.run_id,
                    trace_id=identity.trace_id,
                    receipt_type="nats_consume",
                    limit=20,
                )
            receipt_payloads = [dataclasses.asdict(receipt) for receipt in receipts]
            statuses = [str(receipt.status) for receipt in receipts]
            last_receipt = receipt_payloads[-1] if receipt_payloads else {}
            ack_payload = {
                "task_id": (envelope.get("payload", {}).get("task") or envelope.get("task") or {}).get("id", ""),
                "subject": getattr(message, "subject", ""),
                "action": str((last_receipt.get("payload") or {}).get("action") or "nack"),
                "status": str(last_receipt.get("status") or "nack"),
                "receipt_id": str(last_receipt.get("receipt_id") or ""),
                "duplicate": False,
                "error": str(exc),
                "message_id": str(envelope.get("message_id") or ""),
                "dlq_failed": "dlq_failed" in statuses,
                "runtime_receipts": receipt_payloads,
            }
        return {
            "ack": ack_payload,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "production_path_contract": contract,
        }

    def handler_success(self, label: str) -> Callable[[A2ATask], A2ATask]:
        def handler(task: A2ATask) -> A2ATask:
            count = self.ledger.add(side_effect_key(task.id, label))
            task.status = A2ATaskStatus.COMPLETED
            task.result = json.dumps({"side_effect_count": count, "label": label, "run_id": self.run_id}, sort_keys=True)
            return task

        return handler

    def handler_model(self, label: str) -> Callable[[A2ATask], A2ATask]:
        def handler(task: A2ATask) -> A2ATask:
            count = self.ledger.add(side_effect_key(task.id, label))
            receipt = self.model_probe.call(
                prompt=(
                    "Confirm live semantic execution for Runtime Truth NATS. "
                    f"Return JSON with run_id={self.run_id}, task_id={task.id}, label={label}."
                ),
                task_id=task.id,
                trace_id=f"{self.run_id}:{label}:{task.id}",
            )
            task.status = A2ATaskStatus.COMPLETED
            task.result = json.dumps(
                {
                    "side_effect_count": count,
                    "semantic_receipt_path": receipt["receipt_path"],
                    "provider": receipt["provider"],
                    "response_model": receipt["response_model"],
                },
                sort_keys=True,
            )
            return task

        return handler

    def handler_fail_then_success(self, label: str) -> Callable[[A2ATask], A2ATask]:
        attempts: dict[str, int] = {}

        def handler(task: A2ATask) -> A2ATask:
            attempts[task.id] = attempts.get(task.id, 0) + 1
            self.ledger.add(side_effect_key(task.id, f"{label}:attempt"))
            if attempts[task.id] == 1:
                raise RuntimeError("forced first handler failure")
            self.ledger.add(side_effect_key(task.id, label))
            task.status = A2ATaskStatus.COMPLETED
            task.result = json.dumps({"attempts": attempts[task.id], "label": label}, sort_keys=True)
            return task

        return handler

    def handler_always_fail(self, label: str) -> Callable[[A2ATask], A2ATask]:
        def handler(task: A2ATask) -> A2ATask:
            self.ledger.add(side_effect_key(task.id, f"{label}:attempt"))
            raise RuntimeError(f"forced handler failure for {label}")

        return handler

    async def topology_row(self) -> None:
        stream_info = await self.js.stream_info(self.stream)
        dlq_info = await self.js.stream_info(self.dlq_stream)
        consumer_info = await self.js.consumer_info(self.stream, self.consumer)
        stream_cfg = stream_info.config
        dlq_cfg = dlq_info.config
        consumer_cfg = consumer_info.config
        row = {
            "name": "topology",
            "status": "pass",
            "timestamp": utc_now(),
            "broker_url": self.endpoint,
            "stream_name": self.stream,
            "dlq_stream_name": self.dlq_stream,
            "consumer_name": self.consumer,
            "stream_subjects": list(stream_cfg.subjects or []),
            "stream_retention": str(stream_cfg.retention),
            "stream_storage": str(stream_cfg.storage),
            "stream_duplicate_window_seconds": getattr(stream_cfg, "duplicate_window", None),
            "dlq_subjects": list(dlq_cfg.subjects or []),
            "dlq_retention": str(dlq_cfg.retention),
            "consumer_filter_subject": consumer_cfg.filter_subject,
            "consumer_ack_policy": str(consumer_cfg.ack_policy),
            "consumer_ack_wait_seconds": getattr(consumer_cfg.ack_wait, "total_seconds", lambda: consumer_cfg.ack_wait)(),
            "consumer_max_deliver": consumer_cfg.max_deliver,
            "consumer_delivered": jsonable(getattr(consumer_info, "delivered", None)),
            "consumer_ack_floor": jsonable(getattr(consumer_info, "ack_floor", None)),
            "consumer_num_pending": consumer_info.num_pending,
            "consumer_num_ack_pending": consumer_info.num_ack_pending,
        }
        expected = [
            "dharma.a2a.task.>" in row["stream_subjects"],
            "dharma.dlq.>" in row["dlq_subjects"],
            consumer_cfg.filter_subject == "dharma.a2a.task.>",
            "EXPLICIT" in row["consumer_ack_policy"].upper(),
            consumer_cfg.max_deliver == self.args.max_deliveries,
        ]
        if not all(expected):
            row["status"] = "fail"
            row["failure"] = "live topology does not match production contract"
        self.rows.append(row)

    async def happy_path(self) -> tuple[A2ATask, dict[str, Any], Any]:
        label = "happy_path"
        task = self.task(label)
        identity = self.identity(label, task.id)
        publish_ack = await self.publish_task(task, identity)
        msg = await self.fetch_matching(label, task.id)
        envelope = decode_envelope(msg)
        headers = message_headers(msg)
        handler = self.handler_model(label)
        consume = await self.consume_with_handler(msg, handler)
        row = {
            "name": label,
            "status": "pass" if is_broker_acked(consume["ack"]) else "fail",
            "timestamp": utc_now(),
            "broker_url": self.endpoint,
            "stream_name": self.stream,
            "consumer_name": self.consumer,
            "message_id": publish_ack.message_id,
            "trace_id": identity.trace_id,
            "task_id": task.id,
            "agent_id": task.to_agent,
            "model_provider_id": f"{self.args.provider}:{self.args.model}",
            "production_path_contract": consume["production_path_contract"],
            "publish_ack": dataclasses.asdict(publish_ack),
            "headers": headers,
            "envelope_contract": {
                "schema": envelope.get("schema"),
                "message_id": envelope.get("message_id"),
                "causality": envelope.get("causality"),
                "actor": envelope.get("actor"),
                "from_agent": envelope.get("from_agent"),
                "to_agent": envelope.get("to_agent"),
                "subject": envelope.get("subject"),
                "kind": envelope.get("kind"),
                "payload_schema": envelope.get("payload", {}).get("schema"),
                "nats_msg_id": headers.get("Nats-Msg-Id"),
            },
            "metadata": msg_metadata(msg),
            "consume_ack": consume["ack"],
            "side_effect_count": self.ledger.count(side_effect_key(task.id, label)),
            "receipt_path": self.receipts_dir / f"{task.id}.semantic_receipt.json",
        }
        row["status"] = "pass" if is_broker_acked(row["consume_ack"]) and row["side_effect_count"] == 1 else "fail"
        self.rows.append(row)
        return task, envelope, headers

    async def duplicate_path(self, original_task: A2ATask, original_headers: dict[str, str], original_payload: dict[str, Any]) -> None:
        label = "duplicate_path"
        identity = self.identity("happy_path", original_task.id)
        runtime_duplicate_ack = await self.publish_task(original_task, identity)
        broker_duplicate_ack = await self.js.publish(
            original_payload["subject"],
            json.dumps(original_payload, sort_keys=True).encode("utf-8"),
            headers={"Nats-Msg-Id": original_headers["Nats-Msg-Id"], "Nats-Expected-Stream": self.stream},
        )
        row = {
            "name": label,
            "status": "pass",
            "timestamp": utc_now(),
            "broker_url": self.endpoint,
            "stream_name": self.stream,
            "consumer_name": self.consumer,
            "message_id": original_headers["Nats-Msg-Id"],
            "trace_id": f"{self.run_id}:happy_path:{original_task.id}",
            "task_id": original_task.id,
            "agent_id": original_task.to_agent,
            "model_provider_id": f"{self.args.provider}:{self.args.model}",
            "production_path_contract": self.production_path_contract(None, consumes=False),
            "broker_duplicate_probe_entrypoint": "nats.aio.client.JetStreamContext.publish",
            "broker_duplicate_probe_purpose": "duplicate-window verification only; not a production task publisher",
            "runtime_duplicate_publish_ack": dataclasses.asdict(runtime_duplicate_ack),
            "broker_duplicate_probe": {
                "stream": getattr(broker_duplicate_ack, "stream", None),
                "seq": getattr(broker_duplicate_ack, "seq", None),
                "duplicate": getattr(broker_duplicate_ack, "duplicate", None),
            },
            "side_effect_count_after_replay": self.ledger.count(side_effect_key(original_task.id, "happy_path")),
        }
        if row["side_effect_count_after_replay"] != 1:
            row["status"] = "fail"
            row["failure"] = "duplicate replay double-executed side effects"
        self.rows.append(row)

    async def publish_failure_path(self) -> None:
        label = "publish_failure_path"
        task = self.task(label)
        identity = self.identity(label, task.id)
        failed_transport = A2ANatsTransport(
            runtime_state=self.runtime,
            jetstream=PublishFailingJetStream(self.js),
            config=self.config,
        )
        failure: str | None = None
        try:
            await failed_transport.publish_task(task, identity=identity)
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"
        retry_ack = await self.publish_task(task, identity)
        msg = await self.fetch_matching(label, task.id)
        handler = self.handler_success(label)
        consume = await self.consume_with_handler(msg, handler, stale_after_s=0)
        row = {
            "name": label,
            "status": "pass" if failure and is_broker_acked(consume["ack"]) else "fail",
            "timestamp": utc_now(),
            "broker_url": self.endpoint,
            "stream_name": self.stream,
            "consumer_name": self.consumer,
            "message_id": retry_ack.message_id,
            "trace_id": identity.trace_id,
            "task_id": task.id,
            "agent_id": task.to_agent,
            "model_provider_id": f"{self.args.provider}:{self.args.model}",
            "production_path_contract": consume["production_path_contract"],
            "failure_injection": "JetStream publish raised before broker acceptance",
            "forced_failure": failure,
            "retry_publish_ack": dataclasses.asdict(retry_ack),
            "consume_ack": consume["ack"],
            "metadata": msg_metadata(msg),
        }
        self.rows.append(row)

    async def handler_failure_redelivery_path(self) -> None:
        label = "handler_failure_redelivery_path"
        task = self.task(label)
        identity = self.identity(label, task.id)
        publish_ack = await self.publish_task(task, identity)
        handler = self.handler_fail_then_success(label)
        first_msg = await self.fetch_matching(label, task.id)
        first = await self.consume_with_handler(first_msg, handler)
        second_msg = await self.fetch_matching(label, task.id)
        second = await self.consume_with_handler(second_msg, handler)
        row = {
            "name": label,
            "status": "pass"
            if (not is_broker_acked(first["ack"]) and is_broker_acked(second["ack"]) and self.ledger.count(side_effect_key(task.id, f"{label}:attempt")) == 2)
            else "fail",
            "timestamp": utc_now(),
            "broker_url": self.endpoint,
            "stream_name": self.stream,
            "consumer_name": self.consumer,
            "message_id": publish_ack.message_id,
            "trace_id": identity.trace_id,
            "task_id": task.id,
            "agent_id": task.to_agent,
            "model_provider_id": f"{self.args.provider}:{self.args.model}",
            "production_path_contract": second["production_path_contract"],
            "first_production_path_contract": first["production_path_contract"],
            "second_production_path_contract": second["production_path_contract"],
            "first_delivery_metadata": msg_metadata(first_msg),
            "first_consume_ack": first["ack"],
            "redelivery_metadata": msg_metadata(second_msg),
            "second_consume_ack": second["ack"],
            "handler_attempts": self.ledger.count(side_effect_key(task.id, f"{label}:attempt")),
        }
        self.rows.append(row)

    async def stale_started_idempotency_path(self) -> None:
        label = "stale_started_idempotency_path"
        task = self.task(label)
        identity = self.identity(label, task.id)
        publish_ack = await self.publish_task(task, identity)
        msg = await self.fetch_matching(label, task.id)
        envelope = decode_envelope(msg)
        msg_identity = ExecutionIdentity.from_metadata(
            envelope.get("execution_identity") or envelope.get("payload", {}).get("execution_identity"),
            require=True,
        )
        msg_identity = msg_identity.with_updates(message_id=envelope["message_id"], task_id=task.id)
        consume_side_effect_key = f"nats_consume:{getattr(msg, 'subject', '')}:{task.id}"
        stale_inserted = await self.runtime.try_begin_idempotent_side_effect(
            msg_identity,
            consume_side_effect_key,
            metadata={"matrix_seed": "stale-started-record"},
            stale_after_seconds=300,
        )
        stale_record = await self.runtime.get_idempotency_record(msg_identity.idempotency_key, consume_side_effect_key)
        handler = self.handler_success(label)
        consume = await self.consume_with_handler(msg, handler, stale_after_s=0)
        row = {
            "name": label,
            "status": "pass" if stale_inserted and stale_record and stale_record.status == "started" and is_broker_acked(consume["ack"]) else "fail",
            "timestamp": utc_now(),
            "broker_url": self.endpoint,
            "stream_name": self.stream,
            "consumer_name": self.consumer,
            "message_id": publish_ack.message_id,
            "trace_id": identity.trace_id,
            "task_id": task.id,
            "agent_id": task.to_agent,
            "model_provider_id": f"{self.args.provider}:{self.args.model}",
            "production_path_contract": consume["production_path_contract"],
            "preexisting_idempotency_status": stale_record.status if stale_record else "",
            "seeded_side_effect_key": consume_side_effect_key,
            "consume_ack": consume["ack"],
            "metadata": msg_metadata(msg),
        }
        self.rows.append(row)

    async def concurrent_duplicate_path(self) -> None:
        label = "concurrent_duplicate_path"
        task = self.task(label)
        identity = self.identity(label, task.id)
        publish_ack = await self.publish_task(task, identity)
        msg = await self.fetch_matching(label, task.id)
        envelope = decode_envelope(msg)
        msg_identity = ExecutionIdentity.from_metadata(
            envelope.get("execution_identity") or envelope.get("payload", {}).get("execution_identity"),
            require=True,
        )
        msg_identity = msg_identity.with_updates(message_id=envelope["message_id"], task_id=task.id)
        consume_side_effect_key = f"nats_consume:{getattr(msg, 'subject', '')}:{task.id}"
        started_inserted = await self.runtime.try_begin_idempotent_side_effect(
            msg_identity,
            consume_side_effect_key,
            metadata={"matrix_seed": "in-progress-record"},
            stale_after_seconds=300,
        )
        started_record = await self.runtime.get_idempotency_record(msg_identity.idempotency_key, consume_side_effect_key)
        handler = self.handler_success(label)
        blocked = await self.consume_with_handler(msg, handler, stale_after_s=300)
        cleanup_msg = await self.fetch_matching(label, task.id)
        cleanup = await self.consume_with_handler(cleanup_msg, handler, stale_after_s=0)
        row = {
            "name": label,
            "status": "pass"
            if started_inserted
            and started_record
            and started_record.status == "started"
            and not is_broker_acked(blocked["ack"])
            and is_broker_acked(cleanup["ack"])
            else "fail",
            "timestamp": utc_now(),
            "broker_url": self.endpoint,
            "stream_name": self.stream,
            "consumer_name": self.consumer,
            "message_id": publish_ack.message_id,
            "trace_id": identity.trace_id,
            "task_id": task.id,
            "agent_id": task.to_agent,
            "model_provider_id": f"{self.args.provider}:{self.args.model}",
            "production_path_contract": cleanup["production_path_contract"],
            "blocked_production_path_contract": blocked["production_path_contract"],
            "cleanup_production_path_contract": cleanup["production_path_contract"],
            "preexisting_idempotency_status": started_record.status if started_record else "",
            "seeded_side_effect_key": consume_side_effect_key,
            "blocked_consume_ack": blocked["ack"],
            "cleanup_consume_ack": cleanup["ack"],
            "side_effect_count": self.ledger.count(side_effect_key(task.id, label)),
            "metadata": msg_metadata(msg),
            "cleanup_metadata": msg_metadata(cleanup_msg),
        }
        self.rows.append(row)

    async def ack_failure_path(self) -> None:
        label = "ack_failure_path"
        task = self.task(label)
        identity = self.identity(label, task.id)
        publish_ack = await self.publish_task(task, identity)
        msg = await self.fetch_matching(label, task.id)
        handler = self.handler_success(label)
        failed_ack = await self.consume_with_handler(AckFailMessage(msg), handler)
        redelivery = await self.fetch_matching(label, task.id)
        cleanup = await self.consume_with_handler(redelivery, handler, stale_after_s=0)
        row = {
            "name": label,
            "status": "pass" if not is_broker_acked(failed_ack["ack"]) and is_broker_acked(cleanup["ack"]) else "fail",
            "timestamp": utc_now(),
            "broker_url": self.endpoint,
            "stream_name": self.stream,
            "consumer_name": self.consumer,
            "message_id": publish_ack.message_id,
            "trace_id": identity.trace_id,
            "task_id": task.id,
            "agent_id": task.to_agent,
            "model_provider_id": f"{self.args.provider}:{self.args.model}",
            "production_path_contract": cleanup["production_path_contract"],
            "failed_ack_production_path_contract": failed_ack["production_path_contract"],
            "cleanup_production_path_contract": cleanup["production_path_contract"],
            "failure_injection": "message.ack raised before broker ack; original was nacked and redelivered",
            "failed_ack": failed_ack["ack"],
            "redelivery_metadata": msg_metadata(redelivery),
            "cleanup_ack": cleanup["ack"],
        }
        self.rows.append(row)

    async def max_deliver_path(self) -> None:
        label = "max_deliver_path"
        task = self.task(label)
        identity = self.identity(label, task.id)
        publish_ack = await self.publish_task(task, identity)
        deliveries: list[dict[str, Any]] = []
        final_ack: dict[str, Any] | None = None
        handler = self.handler_always_fail(label)
        final_contract: dict[str, Any] | None = None
        for _ in range(self.args.max_deliveries):
            msg = await self.fetch_matching(label, task.id)
            consume = await self.consume_with_handler(msg, handler)
            deliveries.append({"metadata": msg_metadata(msg), "consume_ack": consume["ack"]})
            final_ack = consume["ack"]
            final_contract = consume["production_path_contract"]
            if is_broker_acked(consume["ack"]):
                break
        dlq_msg = await self.fetch_dlq_for_message(publish_ack.message_id)
        dlq_envelope = decode_envelope(dlq_msg)
        await dlq_msg.ack()
        row = {
            "name": label,
            "status": "pass"
            if final_ack
            and is_broker_acked(final_ack)
            and (dlq_envelope.get("payload") or {}).get("schema") == "dharma.nats.dlq_failure.v1"
            else "fail",
            "timestamp": utc_now(),
            "broker_url": self.endpoint,
            "stream_name": self.stream,
            "consumer_name": self.consumer,
            "message_id": publish_ack.message_id,
            "trace_id": identity.trace_id,
            "task_id": task.id,
            "agent_id": task.to_agent,
            "model_provider_id": f"{self.args.provider}:{self.args.model}",
            "production_path_contract": final_contract,
            "deliveries": deliveries,
            "final_ack": final_ack,
            "dlq_subject": getattr(dlq_msg, "subject", None),
            "dlq_metadata": msg_metadata(dlq_msg),
            "dlq_envelope": dlq_envelope,
        }
        self.rows.append(row)

    async def fetch_dlq_for_message(self, message_id: str, timeout_seconds: float = 15) -> Any:
        deadline = time.monotonic() + timeout_seconds
        durable = f"{self.consumer}_matrix_dlq_reader_{self.safe_run_id}".lower()
        sub = await self.js.pull_subscribe("dharma.dlq.>", durable=durable, stream=self.dlq_stream)
        last_error: str | None = None
        while time.monotonic() < deadline:
            try:
                messages = await sub.fetch(batch=4, timeout=min(2, max(0.2, deadline - time.monotonic())))
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                await asyncio.sleep(0.2)
                continue
            for msg in messages:
                try:
                    envelope = decode_envelope(msg)
                    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
                    original_id = payload.get("original_message_id") or (
                        payload.get("original_payload", {}).get("message_id")
                        if isinstance(payload.get("original_payload"), dict)
                        else None
                    )
                except Exception:
                    original_id = None
                if original_id == message_id:
                    return msg
                await msg.ack()
        raise MatrixFailure(f"did not receive DLQ envelope for message_id={message_id}; last_error={last_error}")

    async def dlq_failure_path(self) -> None:
        label = "dlq_failure_path"
        task = self.task(label)
        identity = self.identity(label, task.id)
        publish_ack = await self.publish_task(task, identity)
        deliveries: list[dict[str, Any]] = []
        final_ack: dict[str, Any] | None = None
        handler = self.handler_always_fail(label)
        final_contract: dict[str, Any] | None = None
        for _ in range(self.args.max_deliveries):
            msg = await self.fetch_matching(label, task.id)
            consume = await self.consume_with_handler(
                msg,
                handler,
                jetstream=DLQFailingJetStream(self.js),
            )
            deliveries.append({"metadata": msg_metadata(msg), "consume_ack": consume["ack"]})
            final_ack = consume["ack"]
            final_contract = consume["production_path_contract"]
            if consume["ack"].get("dlq_failed"):
                break
        consumer_info = await self.js.consumer_info(self.stream, self.consumer)
        final_stream_sequence = None
        if deliveries:
            final_stream_sequence = (deliveries[-1].get("metadata") or {}).get("stream_sequence")
        ack_floor = getattr(consumer_info, "ack_floor", None)
        delivered_state = getattr(consumer_info, "delivered", None)
        ack_floor_stream = getattr(ack_floor, "stream_seq", None)
        operator_visible = (
            isinstance(final_stream_sequence, int)
            and isinstance(ack_floor_stream, int)
            and ack_floor_stream < final_stream_sequence
        )
        row = {
            "name": label,
            "status": "pass"
            if final_ack and final_ack.get("dlq_failed") and not is_broker_acked(final_ack) and operator_visible
            else "fail",
            "timestamp": utc_now(),
            "broker_url": self.endpoint,
            "stream_name": self.stream,
            "consumer_name": self.consumer,
            "message_id": publish_ack.message_id,
            "trace_id": identity.trace_id,
            "task_id": task.id,
            "agent_id": task.to_agent,
            "model_provider_id": f"{self.args.provider}:{self.args.model}",
            "production_path_contract": final_contract,
            "failure_injection": "DLQ publish raised at MaxDeliver; original was not acked and remains beyond the consumer ack floor",
            "deliveries": deliveries,
            "final_ack": final_ack,
            "operator_visible": operator_visible,
            "operator_visible_state": {
                "final_stream_sequence": final_stream_sequence,
                "ack_floor": jsonable(ack_floor),
                "delivered": jsonable(delivered_state),
                "num_ack_pending": consumer_info.num_ack_pending,
                "num_pending": consumer_info.num_pending,
                "num_redelivered": consumer_info.num_redelivered,
            },
        }
        self.rows.append(row)

    async def restart_path(self) -> None:
        label = "restart_path"
        task = self.task(label)
        identity = self.identity(label, task.id)
        publish_ack = await self.publish_task(task, identity)
        msg = await self.fetch_matching(label, task.id)
        first_meta = msg_metadata(msg)
        # Simulate process death after delivery by closing the broker connection
        # without acking or nacking the in-flight message.
        await self.nc.close()
        await asyncio.sleep(self.args.restart_wait_s)
        await self.connect()
        redelivery = await self.fetch_matching(label, task.id, timeout_seconds=max(15, self.args.restart_wait_s + 5))
        handler = self.handler_success(label)
        cleanup = await self.consume_with_handler(redelivery, handler, stale_after_s=0)
        row = {
            "name": label,
            "status": "pass" if is_broker_acked(cleanup["ack"]) else "fail",
            "timestamp": utc_now(),
            "broker_url": self.endpoint,
            "stream_name": self.stream,
            "consumer_name": self.consumer,
            "message_id": publish_ack.message_id,
            "trace_id": identity.trace_id,
            "task_id": task.id,
            "agent_id": task.to_agent,
            "model_provider_id": f"{self.args.provider}:{self.args.model}",
            "production_path_contract": cleanup["production_path_contract"],
            "first_delivery_metadata": first_meta,
            "restart_wait_seconds": self.args.restart_wait_s,
            "redelivery_metadata": msg_metadata(redelivery),
            "cleanup_ack": cleanup["ack"],
        }
        self.rows.append(row)

    def compatibility_bypass_contract(self) -> None:
        label = "compatibility_bypass_contract"
        a2a_send = (ROOT / "scripts" / "runtime" / "a2a_send.py").read_text(encoding="utf-8")
        domain_worker = (ROOT / "scripts" / "runtime" / "a2a_domain_reply_worker.py").read_text(encoding="utf-8")
        checks = {
            "a2a_send_marks_noncanonical": "CANONICAL_RUNTIME_TRUTH_NATS_TASK_PATH = False" in a2a_send,
            "a2a_send_declares_gate_ineligible": "cannot_satisfy_runtime_truth_nats_production_gate" in a2a_send,
            "a2a_send_names_canonical_transport": "A2ANatsTransport.publish_task" in a2a_send,
            "domain_reply_worker_uses_domain_receipt_schema": "dharma.a2a.domain_receipt.v1" in domain_worker,
            "domain_reply_worker_does_not_mint_nats_envelope_v1": "dharma.nats.envelope.v1" not in domain_worker,
        }
        row = {
            "name": label,
            "status": "pass" if all(checks.values()) else "fail",
            "timestamp": utc_now(),
            "broker_url": self.endpoint,
            "stream_name": self.stream,
            "consumer_name": self.consumer,
            "message_id": None,
            "trace_id": self.run_id,
            "task_id": None,
            "agent_id": "governance",
            "model_provider_id": f"{self.args.provider}:{self.args.model}",
            "compatibility_publishers_can_satisfy_production_gate": False,
            "canonical_runtime_truth_nats_task_path": PUBLISH_ENTRYPOINT,
            "gate_enforced_by": [
                "scripts/governance/check_nats_substrate_contract.py",
                "scripts/governance/check_nats_live_production_evidence.py",
                "docs/governance/ACTIVE_TRACK.yaml:nats_live_production_evidence_fresh",
            ],
            "checks": checks,
            "compatibility_surfaces": [
                {
                    "path": "scripts/runtime/a2a_send.py",
                    "classification": "operator_contact_compatibility_only",
                    "may_satisfy_production_gate": False,
                },
                {
                    "path": "scripts/runtime/a2a_domain_reply_worker.py",
                    "classification": "domain_reply_publisher_not_task_transport",
                    "may_mint_nats_envelope_v1": False,
                    "may_satisfy_production_gate": False,
                },
            ],
        }
        self.rows.append(row)

    def governance_negative_path(self, evidence_path: Path) -> None:
        label = "governance_negative_path"
        tampered = json.loads(evidence_path.read_text(encoding="utf-8"))
        tampered["rows"] = [row for row in tampered.get("rows", []) if row.get("name") != "happy_path"]
        tampered["status"] = "pass"
        tampered["missing_rows"] = []
        tampered["failed_rows"] = []
        with tempfile.TemporaryDirectory(prefix="nats-matrix-negative-") as tmp:
            tampered_path = Path(tmp) / "tampered.json"
            write_json(tampered_path, tampered)
            cmd = [
                sys.executable,
                str(ROOT / "scripts" / "governance" / "check_nats_live_production_evidence.py"),
                "--evidence",
                str(tampered_path),
                "--max-age-hours",
                "999999",
                "--host-mode",
                "live",
                "--expected-broker-url",
                self.endpoint,
                "--expected-broker-profile",
                self.args.broker_profile,
            ]
            result = run_command(cmd)
        self.commands.append(result)
        row = {
            "name": label,
            "status": "pass" if result["return_code"] != 0 else "fail",
            "timestamp": utc_now(),
            "broker_url": self.endpoint,
            "stream_name": self.stream,
            "consumer_name": self.consumer,
            "message_id": None,
            "trace_id": self.run_id,
            "task_id": None,
            "agent_id": "governance",
            "model_provider_id": f"{self.args.provider}:{self.args.model}",
            "tamper_description": "removed the required happy_path row from otherwise fresh live evidence",
            "tampered_row_removed": "happy_path",
            "expected_failure_contains": "missing required rows",
            "negative_command": result["command"],
            "negative_return_code": result["return_code"],
            "negative_stdout": result["stdout"],
            "negative_stderr": result["stderr"],
        }
        self.rows.append(row)

    def payload(self) -> dict[str, Any]:
        failed_rows = [row for row in self.rows if row.get("status") != "pass"]
        required_rows = [
            "topology",
            "happy_path",
            "duplicate_path",
            "publish_failure_path",
            "handler_failure_redelivery_path",
            "stale_started_idempotency_path",
            "concurrent_duplicate_path",
            "ack_failure_path",
            "max_deliver_path",
            "dlq_failure_path",
            "restart_path",
            "compatibility_bypass_contract",
            "governance_negative_path",
        ]
        present = {row.get("name") for row in self.rows}
        missing = [name for name in required_rows if name not in present]
        return {
            "schema": "dharma.nats.live_production_matrix.v1",
            "host_mode": "live",
            "run_id": self.run_id,
            "generated_at": utc_now(),
            "status": "pass" if not failed_rows and not missing else "fail",
            "broker_url": self.endpoint,
            "broker_profile": self.args.broker_profile,
            "stream_name": self.stream,
            "dlq_stream_name": self.dlq_stream,
            "consumer_name": self.consumer,
            "provider": self.args.provider,
            "model": self.args.model,
            "runtime_db": str(self.runtime_db),
            "a2a_receipts_dir": str(self.receipts_dir),
            "required_rows": required_rows,
            "missing_rows": missing,
            "failed_rows": [row.get("name") for row in failed_rows],
            "rows": self.rows,
            "commands": self.commands,
            "command": [
                sys.executable,
                str(Path(__file__).resolve()),
                *self.args.command_argv,
            ],
            "source_fingerprints": source_fingerprints(),
            "process": {
                "pid": os.getpid(),
                "cwd": str(ROOT),
                "python": sys.executable,
            },
        }

    async def run(self) -> Path:
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.a2a_dir.mkdir(parents=True, exist_ok=True)
        await self.connect()
        try:
            await self.topology_row()
            happy_task, happy_payload, happy_headers = await self.happy_path()
            await self.duplicate_path(happy_task, happy_headers, happy_payload)
            await self.publish_failure_path()
            await self.handler_failure_redelivery_path()
            await self.stale_started_idempotency_path()
            await self.concurrent_duplicate_path()
            await self.ack_failure_path()
            await self.max_deliver_path()
            await self.dlq_failure_path()
            await self.restart_path()
            self.compatibility_bypass_contract()
            evidence_path = self.evidence_dir / "evidence.json"
            write_json(evidence_path, self.payload())
            self.governance_negative_path(evidence_path)
            write_json(evidence_path, self.payload())
            latest = DEFAULT_EVIDENCE_ROOT / "latest.json"
            latest.parent.mkdir(parents=True, exist_ok=True)
            latest.write_text(evidence_path.read_text(encoding="utf-8"), encoding="utf-8")
            return evidence_path
        finally:
            await self.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--host-mode",
        choices=["non-live", "live"],
        default=os.environ.get("DHARMA_NATS_HOST_MODE", "non-live"),
    )
    parser.add_argument("--endpoint", default=os.environ.get("NATS_URL", "nats://127.0.0.1:4222"))
    parser.add_argument("--broker-profile", default=os.environ.get("NATS_PROFILE", "local-live-jetstream"))
    parser.add_argument("--stream", default="DS_TASKS")
    parser.add_argument("--dlq-stream", default="DS_DLQ")
    parser.add_argument("--consumer", default="a2a_task_handler")
    parser.add_argument("--provider", default=os.environ.get("DHARMA_MATRIX_PROVIDER", "ollama"))
    parser.add_argument("--model", default=os.environ.get("DHARMA_MATRIX_MODEL", "glm-5.2:cloud"))
    parser.add_argument("--model-timeout", type=float, default=float(os.environ.get("DHARMA_MATRIX_MODEL_TIMEOUT", "90")))
    parser.add_argument("--bad-endpoint", default="nats://127.0.0.1:1")
    parser.add_argument("--max-deliveries", type=int, default=3)
    parser.add_argument("--idempotency-stale-after-s", type=int, default=300)
    parser.add_argument("--restart-wait-s", type=float, default=65)
    parser.add_argument("--output-dir")
    parser.add_argument("--a2a-output-dir")
    parser.add_argument("--evidence")
    parser.add_argument("--max-age-hours", type=float, default=24)
    parser.add_argument("--source-grace-seconds", type=float, default=2.0)
    args = parser.parse_args(argv)
    args.command_argv = list(argv)
    return args


def check_evidence(
    evidence_path: Path | None,
    args: argparse.Namespace,
    *,
    host_mode: str,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "governance" / "check_nats_live_production_evidence.py"),
        "--max-age-hours",
        str(args.max_age_hours),
        "--source-grace-seconds",
        str(args.source_grace_seconds),
        "--host-mode",
        host_mode,
        "--expected-broker-url",
        args.endpoint,
        "--expected-broker-profile",
        args.broker_profile,
    ]
    if evidence_path is not None:
        command.extend(["--evidence", str(evidence_path)])
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def render_evidence_check(completed: subprocess.CompletedProcess[str]) -> None:
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)


async def async_main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.host_mode == "non-live":
        explicit_evidence = Path(args.evidence) if args.evidence is not None else None
        completed = check_evidence(explicit_evidence, args, host_mode="non-live")
        render_evidence_check(completed)
        return completed.returncode

    runner = MatrixRunner(args)
    evidence_path: Path | None = None
    try:
        evidence_path = await runner.run()
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        completed = check_evidence(evidence_path, args, host_mode="live")
        render_evidence_check(completed)
        if completed.returncode != 0:
            return completed.returncode
        print(json.dumps({"status": payload["status"], "evidence": str(evidence_path)}, sort_keys=True))
        return 0 if payload["status"] == "pass" else 1
    except Exception as exc:
        failure_payload = runner.payload()
        failure_payload["status"] = "fail"
        failure_payload["fatal_error"] = f"{type(exc).__name__}: {exc}"
        failure_path = runner.evidence_dir / "evidence.json"
        write_json(failure_path, failure_payload)
        latest = DEFAULT_EVIDENCE_ROOT / "latest.json"
        latest.parent.mkdir(parents=True, exist_ok=True)
        latest.write_text(failure_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(json.dumps({"status": "fail", "evidence": str(failure_path), "error": failure_payload["fatal_error"]}, sort_keys=True), file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(async_main(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
