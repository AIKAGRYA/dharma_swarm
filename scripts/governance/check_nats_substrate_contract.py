#!/usr/bin/env python3
"""Validate the NATS substrate contract wiring without requiring live NATS."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def _require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _repo_paths(repo_root: Path) -> dict[str, Path]:
    return {
        "spec": repo_root / "docs" / "governance" / "NATS_SUBSTRATE_MASTER_SPEC.md",
        "makefile": repo_root / "Makefile",
        "onboard": repo_root / "scripts" / "governance" / "agent_onboard.py",
        "a2a_send": repo_root / "scripts" / "runtime" / "a2a_send.py",
        "a2a_inbox_bridge": repo_root / "scripts" / "runtime" / "a2a_inbox_bridge.py",
        "a2a_domain_reply_worker": repo_root / "scripts" / "runtime" / "a2a_domain_reply_worker.py",
        "a2a_reply_capture": repo_root / "scripts" / "runtime" / "a2a_reply_capture.py",
        "nats_status": repo_root / "dharma_swarm" / "operator_core" / "nats_substrate_status.py",
        "nats_transport": repo_root / "dharma_swarm" / "a2a" / "nats_transport.py",
        "nats_transport_support": repo_root / "dharma_swarm" / "a2a" / "nats_transport_support.py",
        "a2a_cloud_contact": repo_root / "dharma_swarm" / "a2a" / "a2a_cloud_contact.py",
        "nats_live_matrix": repo_root / "scripts" / "governance" / "run_nats_live_production_matrix.py",
        "nats_live_evidence": repo_root / "scripts" / "governance" / "check_nats_live_production_evidence.py",
        "nats_transport_tests": repo_root / "tests" / "test_nats_transport.py",
        "nats_contract_tests": repo_root / "tests" / "test_nats_substrate_contract.py",
    }


def check_contract(repo_root: Path | str = REPO_ROOT) -> list[str]:
    """Return contract failures for ``repo_root``; empty means pass."""

    root = Path(repo_root).resolve()
    failures: list[str] = []
    paths = _repo_paths(root)
    for path in paths.values():
        _require(path.exists(), f"missing required NATS contract file: {path}", failures)
    if failures:
        return failures

    spec = _read(paths["spec"])
    makefile = _read(paths["makefile"])
    onboard = _read(paths["onboard"])
    a2a_send = _read(paths["a2a_send"])
    a2a_inbox_bridge = _read(paths["a2a_inbox_bridge"])
    a2a_domain_reply_worker = _read(paths["a2a_domain_reply_worker"])
    a2a_reply_capture = _read(paths["a2a_reply_capture"])
    nats_status = _read(paths["nats_status"])
    nats_transport = _read(paths["nats_transport"])
    nats_transport_contract = nats_transport + "\n" + _read(paths["nats_transport_support"])
    a2a_cloud_contact = _read(paths["a2a_cloud_contact"])
    nats_live_matrix = _read(paths["nats_live_matrix"])
    nats_live_evidence = _read(paths["nats_live_evidence"])
    nats_transport_tests = _read(paths["nats_transport_tests"])
    nats_contract_tests = _read(paths["nats_contract_tests"])

    required_spec_phrases = [
        "Filesystem and SQLite buses: compatibility mirrors",
        "DS_TASKS",
        "DS_DLQ",
        "Nats-Msg-Id",
        "dharma.nats.envelope.v1",
        "MaxDeliver",
        "dharma.dlq.<stream>.<consumer>",
        "PUBLISH_ACCEPTED",
        "DELIVERED_TO_CONSUMER",
        "HANDLER_ACKED",
        "DOMAIN_RECEIPTED",
        "`PUBLISH_ACCEPTED` alone is not live human-usable contact",
        "scripts/runtime/a2a_send.py",
        "CLI fallback can prove at most `PUBLISH_ACCEPTED`",
        "scripts/runtime/a2a_inbox_bridge.py",
        "It is not a semantic peer reply",
        "scripts/runtime/a2a_domain_reply_worker.py",
        "target-owned reply artifact",
        "scripts/runtime/a2a_reply_capture.py",
        "NO_REPLY",
    ]
    for phrase in required_spec_phrases:
        _require(phrase in spec, f"spec missing required phrase: {phrase}", failures)

    _require("nats-substrate-contract:" in makefile, "Makefile missing nats-substrate-contract target", failures)
    _require(
        "governance-all:" in makefile and "nats-substrate-contract" in makefile,
        "governance-all does not include nats-substrate-contract",
        failures,
    )
    _require(
        "tests/test_nats_substrate_contract.py" in makefile,
        "nats-substrate-contract target does not run tests/test_nats_substrate_contract.py",
        failures,
    )
    _require(
        "check_nats_live_production_evidence.py" in makefile,
        "nats-substrate-contract target does not require fresh live production evidence",
        failures,
    )
    _require(
        "nats-live-production-matrix:" in makefile and "run_nats_live_production_matrix.py" in makefile,
        "Makefile missing live NATS production matrix target",
        failures,
    )
    _require("NATS_SUBSTRATE_MASTER_SPEC.md" in onboard, "onboard does not render canonical NATS spec path", failures)
    _require("classify_contact_evidence" in a2a_send, "a2a_send missing contact evidence classifier", failures)
    _require("NATS_CLI_JETSTREAM_PUB_ACK" in a2a_send, "a2a_send missing governed NATS CLI fallback receipt marker", failures)
    _require("live_contact_claim" in a2a_send, "a2a_send receipts do not expose live_contact_claim", failures)
    _require(
        "CANONICAL_RUNTIME_TRUTH_NATS_TASK_PATH = False" in a2a_send,
        "a2a_send does not mark itself as non-canonical production evidence",
        failures,
    )
    _require(
        "cannot_satisfy_runtime_truth_nats_production_gate" in a2a_send,
        "a2a_send compatibility bypass can be mistaken for production evidence",
        failures,
    )
    _require("DELIVERED_AND_ACKED" in a2a_inbox_bridge, "a2a_inbox_bridge missing delivered-and-acked status", failures)
    _require("semantic_reply_claim" in a2a_inbox_bridge, "a2a_inbox_bridge can overclaim semantic replies", failures)
    _require("target-owned" in a2a_domain_reply_worker, "a2a_domain_reply_worker missing target-owned boundary", failures)
    _require("DOMAIN_REPLY_PUBLISHED" in a2a_domain_reply_worker, "a2a_domain_reply_worker missing publish status", failures)
    _require(
        "dharma.a2a.domain_receipt.v1" in a2a_domain_reply_worker,
        "a2a_domain_reply_worker missing typed domain receipt schema",
        failures,
    )
    _require("NO_REPLY" in a2a_reply_capture, "a2a_reply_capture missing honest no-reply status", failures)
    _require("DOMAIN_RECEIPTED" in a2a_reply_capture, "a2a_reply_capture missing domain receipt status", failures)
    _require(
        "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md" in nats_status,
        "nats_substrate_status points at the wrong spec path",
        failures,
    )

    required_transport_markers = [
        'NATS_ENVELOPE_SCHEMA = "dharma.nats.envelope.v1"',
        'DLQ_PAYLOAD_SCHEMA = "dharma.nats.dlq_failure.v1"',
        '"Nats-Msg-Id"',
        "ensure_stream_topology",
        "ensure_task_consumer",
        "DS_TASKS",
        "DS_DLQ",
        "max_deliveries",
        "retry_blocked",
        "duplicate_ack_failed",
        "dlq_subject_for_consumer",
        "_actor_fields",
        "_causality_fields",
        "NATS_MAX_DELIVER_EXHAUSTED",
        "requires A2AServer(require_execution_identity=True)",
    ]
    for marker in required_transport_markers:
        _require(
            marker in nats_transport_contract,
            f"nats_transport missing contract marker: {marker}",
            failures,
        )

    required_cloud_contact_markers = [
        "A2ANatsTransport",
        "publish_task",
        "JETSTREAM_PUBLISH_CONTRACT",
        "operator_transport_required",
    ]
    for marker in required_cloud_contact_markers:
        _require(marker in a2a_cloud_contact, f"a2a_cloud_contact missing governed transport marker: {marker}", failures)

    required_live_matrix_markers = [
        "PUBLISH_ENTRYPOINT",
        "CONSUME_ENTRYPOINT",
        "production_path_contract",
        "compatibility_bypass_contract",
        "A2ANatsTransport",
        "publish_task",
        "ModelProbe",
        "happy_path",
        "duplicate_path",
        "handler_failure_redelivery_path",
        "dlq_failure_path",
        "restart_path",
        "governance_negative_path",
        "source_fingerprints",
        "dharma.nats.live_production_matrix.v1",
    ]
    for marker in required_live_matrix_markers:
        _require(marker in nats_live_matrix, f"live matrix runner missing marker: {marker}", failures)

    required_live_evidence_markers = [
        "REQUIRED_ROWS",
        "PUBLISH_ENTRYPOINT",
        "CONSUME_ENTRYPOINT",
        "validate_production_path",
        "validate_compatibility_bypass",
        "happy_path",
        "duplicate_path",
        "max_deliver_path",
        "dlq_failure_path",
        "restart_path",
        "governance_negative_path",
        "source_fingerprints",
        "validate_source_freshness",
        "dharma.nats.live_production_matrix.v1",
    ]
    for marker in required_live_evidence_markers:
        _require(marker in nats_live_evidence, f"live evidence checker missing marker: {marker}", failures)

    required_transport_tests = [
        "test_publish_failure_is_retryable_not_duplicate",
        "test_consume_server_must_require_execution_identity",
        "test_consume_failure_redelivery_retries_handler_instead_of_duplicate_ack",
        "test_consume_stale_started_record_is_retryable",
        "test_consume_in_progress_duplicate_is_nacked_not_acked",
        "test_duplicate_consume_ack_failure_records_truth_not_duplicate_success",
        "test_consume_max_delivery_publishes_dlq_and_acks_original",
        "test_transport_can_declare_durable_stream_and_consumer_contract",
        "test_execution_identity_run_id_conflict_is_rejected",
        "dharma.nats.envelope.v1",
        "Nats-Msg-Id",
    ]
    for marker in required_transport_tests:
        _require(marker in nats_transport_tests, f"test_nats_transport missing regression marker: {marker}", failures)

    required_contract_test_markers = [
        "check_contract",
        "test_contract_checker_fails_when_nats_transport_wiring_missing",
        "test_contract_checker_fails_when_regression_tests_are_disconnected",
        "test_contract_checker_fails_when_a2a_send_can_overclaim_production",
    ]
    for marker in required_contract_test_markers:
        _require(marker in nats_contract_tests, f"contract tests missing marker: {marker}", failures)

    unavailable = _probe_unavailable(paths["nats_status"])
    _require(unavailable["ack_verified"] is False, "unreachable NATS endpoint reported ack_verified=True", failures)
    _require(
        unavailable["code"] in {"NATS_UNAVAILABLE", "NATS_ACK_FAILED", "NATS_CLIENT_MISSING"},
        f"unexpected unreachable NATS code: {unavailable['code']}",
        failures,
    )
    _require(
        unavailable["spec_path"] == "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md",
        f"probe reports wrong spec_path: {unavailable['spec_path']}",
        failures,
    )
    if root != REPO_ROOT.resolve():
        failures.append(
            "contract checker production pass requires the current repo so behavioral NATS checks can run"
        )
        return failures
    failures.extend(_check_current_repo_behavior(root))
    return failures


def _check_current_repo_behavior(repo_root: Path) -> list[str]:
    failures: list[str] = []
    old_path = list(sys.path)
    sys.path.insert(0, str(repo_root))
    try:
        asyncio.run(_check_transport_behavior(repo_root))
    except Exception as exc:
        failures.append(f"NATS transport behavioral check failed: {type(exc).__name__}: {exc}")
    finally:
        sys.path[:] = old_path

    try:
        evidence_module_path = repo_root / "scripts" / "governance" / "check_nats_live_production_evidence.py"
        spec = importlib.util.spec_from_file_location(
            "_dharma_nats_live_production_evidence_contract",
            evidence_module_path,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot import {evidence_module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        evidence_path = (
            repo_root
            / "reports"
            / "governance"
            / "nats_live_production_matrix"
            / "latest.json"
        )
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        module.validate(payload, 24, source_grace_seconds=2.0)
    except Exception as exc:
        failures.append(f"fresh live NATS production evidence check failed: {type(exc).__name__}: {exc}")
    return failures


async def _check_transport_behavior(repo_root: Path) -> None:
    from dharma_swarm.a2a.a2a_server import A2AMessage, A2AServer, A2ATask
    from dharma_swarm.a2a.nats_transport import A2ANatsTransport, NatsTransportError
    from dharma_swarm.runtime_state import RuntimeStateStore
    from dharma_swarm.spine.identity import ExecutionIdentity

    class _FakeAck:
        stream = "DS_TASKS"

        def __init__(self, seq: int) -> None:
            self.seq = seq

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
        ) -> _FakeAck:
            self.published.append((subject, payload, headers))
            return _FakeAck(len(self.published))

    with tempfile.TemporaryDirectory(prefix="nats-contract-behavior-") as tmp:
        runtime = RuntimeStateStore(Path(tmp) / "runtime.db")
        jetstream = _FakeJetStream()
        identity = ExecutionIdentity.new(
            run_id="run-nats-contract-behavior",
            task_id="task-nats-contract-behavior",
            agent_id="nats-contract-agent",
            session_id="nats-contract",
            trace_id="trace-nats-contract-behavior",
            correlation_id="corr-nats-contract-behavior",
            causation_id="cause-nats-contract-behavior",
            claim_id="claim-nats-contract-behavior",
            idempotency_key="idem-nats-contract-behavior",
        )
        task = A2ATask(
            id="a2a-nats-contract-behavior",
            from_agent="operator",
            to_agent="worker",
            capability="probe",
            history=[A2AMessage.text("prove governed NATS behavior")],
            metadata=identity.to_metadata(),
        )
        transport = A2ANatsTransport(runtime_state=runtime, jetstream=jetstream)
        ack = await transport.publish_task(task, identity=identity)
        duplicate = await transport.publish_task(task, identity=identity)
        if ack.status != "ack" or duplicate.status != "duplicate" or len(jetstream.published) != 1:
            raise AssertionError("publish idempotency behavior is not governed")
        _, encoded, headers = jetstream.published[0]
        envelope = json.loads(encoded.decode("utf-8"))
        if envelope.get("schema") != "dharma.nats.envelope.v1":
            raise AssertionError("NATS envelope schema missing")
        if not isinstance(envelope.get("actor"), dict) or not isinstance(envelope.get("causality"), dict):
            raise AssertionError("NATS envelope actor/causality fields missing")
        if headers is None or headers.get("Nats-Msg-Id") != envelope.get("message_id"):
            raise AssertionError("Nats-Msg-Id does not match envelope message_id")
        server = A2AServer(runtime_state=runtime, persist=False, require_execution_identity=False)
        try:
            A2ANatsTransport(runtime_state=runtime, server=server, jetstream=jetstream)
        except NatsTransportError:
            pass
        else:
            raise AssertionError("transport accepted an identityless A2AServer")


def _probe_unavailable(nats_status_path: Path) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location(
        "_dharma_nats_substrate_status_contract",
        nats_status_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {nats_status_path}")
    module = importlib.util.module_from_spec(spec)
    old_module = sys.modules.get(spec.name)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        status = module.probe_nats_substrate(endpoint="nats://127.0.0.1:1", verify_ack=True)
    finally:
        if old_module is None:
            sys.modules.pop(spec.name, None)
        else:
            sys.modules[spec.name] = old_module
    return status.to_dict() if hasattr(status, "to_dict") else dict(status)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)

    failures = check_contract(args.repo_root)
    if failures:
        for failure in failures:
            print(f"NATS_CONTRACT_FAIL {failure}", file=sys.stderr)
        return 1
    print("NATS_CONTRACT_OK docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
