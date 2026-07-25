from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Callable


_CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "governance" / "check_nats_substrate_contract.py"
_SPEC = importlib.util.spec_from_file_location("check_nats_substrate_contract_test", _CHECKER_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
check_contract: Callable[[Path | str], list[str]] = _MODULE.check_contract

_RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "governance" / "run_nats_live_production_matrix.py"
_RUNNER_SPEC = importlib.util.spec_from_file_location("run_nats_live_production_matrix_test", _RUNNER_PATH)
assert _RUNNER_SPEC is not None and _RUNNER_SPEC.loader is not None
_RUNNER_MODULE = importlib.util.module_from_spec(_RUNNER_SPEC)
_RUNNER_SPEC.loader.exec_module(_RUNNER_MODULE)


def test_contract_checker_rejects_marker_only_repo(tmp_path: Path) -> None:
    _write_contract_repo(tmp_path)

    failures = check_contract(tmp_path)

    assert any("production pass requires the current repo" in failure for failure in failures)


def test_contract_checker_fails_when_nats_transport_wiring_missing(tmp_path: Path) -> None:
    paths = _write_contract_repo(tmp_path)
    transport = paths["nats_transport"]
    transport.write_text(
        transport.read_text(encoding="utf-8").replace('"Nats-Msg-Id"', '"Nats-Not-Msg-Id"'),
        encoding="utf-8",
    )

    failures = check_contract(tmp_path)

    assert any("nats_transport missing contract marker: \"Nats-Msg-Id\"" in failure for failure in failures)


def test_contract_checker_fails_when_regression_tests_are_disconnected(tmp_path: Path) -> None:
    paths = _write_contract_repo(tmp_path)
    tests = paths["nats_transport_tests"]
    tests.write_text(
        tests.read_text(encoding="utf-8").replace(
            "test_consume_failure_redelivery_retries_handler_instead_of_duplicate_ack",
            "test_consume_failure_redelivery_removed",
        ),
        encoding="utf-8",
    )

    failures = check_contract(tmp_path)

    assert any(
        "test_nats_transport missing regression marker: "
        "test_consume_failure_redelivery_retries_handler_instead_of_duplicate_ack" in failure
        for failure in failures
    )


def test_contract_checker_fails_when_a2a_send_can_overclaim_production(tmp_path: Path) -> None:
    paths = _write_contract_repo(tmp_path)
    a2a_send = paths["a2a_send"]
    a2a_send.write_text(
        a2a_send.read_text(encoding="utf-8").replace(
            "cannot_satisfy_runtime_truth_nats_production_gate",
            "production_gate_claim_allowed",
        ),
        encoding="utf-8",
    )

    failures = check_contract(tmp_path)

    assert any("a2a_send compatibility bypass can be mistaken for production evidence" in failure for failure in failures)


def test_live_matrix_deterministic_probe_writes_semantic_receipt(tmp_path: Path) -> None:
    probe = _RUNNER_MODULE.ModelProbe("deterministic", "local-deterministic", 1.0, tmp_path)

    receipt = probe.call("prove live transport", "task-1", "trace-1")

    assert receipt["provider"] == "deterministic"
    assert receipt["response_model"] == "local-deterministic"
    assert "deterministic_transport_probe" in receipt["content"]
    assert Path(receipt["receipt_path"]).exists()


def _write_contract_repo(root: Path) -> dict[str, Path]:
    paths = {
        "spec": root / "docs" / "governance" / "NATS_SUBSTRATE_MASTER_SPEC.md",
        "makefile": root / "Makefile",
        "onboard": root / "scripts" / "governance" / "agent_onboard.py",
        "a2a_send": root / "scripts" / "runtime" / "a2a_send.py",
        "a2a_inbox_bridge": root / "scripts" / "runtime" / "a2a_inbox_bridge.py",
        "a2a_domain_reply_worker": root / "scripts" / "runtime" / "a2a_domain_reply_worker.py",
        "a2a_reply_capture": root / "scripts" / "runtime" / "a2a_reply_capture.py",
        "nats_status": root / "dharma_swarm" / "operator_core" / "nats_substrate_status.py",
        "nats_transport": root / "dharma_swarm" / "a2a" / "nats_transport.py",
        "nats_transport_support": root / "dharma_swarm" / "a2a" / "nats_transport_support.py",
        "a2a_cloud_contact": root / "dharma_swarm" / "a2a" / "a2a_cloud_contact.py",
        "nats_live_matrix": root / "scripts" / "governance" / "run_nats_live_production_matrix.py",
        "nats_live_evidence": root / "scripts" / "governance" / "check_nats_live_production_evidence.py",
        "nats_transport_tests": root / "tests" / "test_nats_transport.py",
        "nats_contract_tests": root / "tests" / "test_nats_substrate_contract.py",
    }
    _write(
        paths["spec"],
        """
Filesystem and SQLite buses: compatibility mirrors
DS_TASKS
DS_DLQ
Nats-Msg-Id
dharma.nats.envelope.v1
MaxDeliver
dharma.dlq.<stream>.<consumer>
PUBLISH_ACCEPTED
DELIVERED_TO_CONSUMER
HANDLER_ACKED
DOMAIN_RECEIPTED
`PUBLISH_ACCEPTED` alone is not live human-usable contact
scripts/runtime/a2a_send.py
CLI fallback can prove at most `PUBLISH_ACCEPTED`
scripts/runtime/a2a_inbox_bridge.py
It is not a semantic peer reply
scripts/runtime/a2a_domain_reply_worker.py
target-owned reply artifact
scripts/runtime/a2a_reply_capture.py
NO_REPLY
""",
    )
    _write(
        paths["makefile"],
        """
nats-substrate-contract:
\tpython scripts/governance/check_nats_substrate_contract.py
\tpython scripts/governance/check_nats_live_production_evidence.py --max-age-hours 24
\tpytest tests/test_nats_substrate_contract.py
nats-live-production-matrix:
\tpython scripts/governance/run_nats_live_production_matrix.py
governance-all: semgrep nats-substrate-contract
""",
    )
    _write(paths["onboard"], "NATS_SUBSTRATE_MASTER_SPEC.md\n")
    _write(
        paths["a2a_send"],
        """
classify_contact_evidence
NATS_CLI_JETSTREAM_PUB_ACK
live_contact_claim
CANONICAL_RUNTIME_TRUTH_NATS_TASK_PATH = False
cannot_satisfy_runtime_truth_nats_production_gate
""",
    )
    _write(paths["a2a_inbox_bridge"], "DELIVERED_AND_ACKED semantic_reply_claim\n")
    _write(paths["a2a_domain_reply_worker"], "target-owned DOMAIN_REPLY_PUBLISHED dharma.a2a.domain_receipt.v1\n")
    _write(paths["a2a_reply_capture"], "NO_REPLY DOMAIN_RECEIPTED\n")
    _write(
        paths["nats_status"],
        """
class _Status:
    def to_dict(self):
        return {
            "ack_verified": False,
            "code": "NATS_UNAVAILABLE",
            "spec_path": "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md",
        }

def probe_nats_substrate(*, endpoint=None, verify_ack=False):
    return _Status()
""",
    )
    _write(
        paths["nats_transport"],
        '''
NATS_ENVELOPE_SCHEMA = "dharma.nats.envelope.v1"
DLQ_PAYLOAD_SCHEMA = "dharma.nats.dlq_failure.v1"
"Nats-Msg-Id"
ensure_stream_topology
ensure_task_consumer
DS_TASKS
DS_DLQ
max_deliveries
retry_blocked
duplicate_ack_failed
dlq_subject_for_consumer
_actor_fields
_causality_fields
NATS_MAX_DELIVER_EXHAUSTED
requires A2AServer(require_execution_identity=True)
''',
    )
    _write(paths["nats_transport_support"], "wire helpers\n")
    _write(paths["a2a_cloud_contact"], "A2ANatsTransport publish_task JETSTREAM_PUBLISH_CONTRACT operator_transport_required\n")
    _write(
        paths["nats_live_matrix"],
        """
PUBLISH_ENTRYPOINT
CONSUME_ENTRYPOINT
production_path_contract
compatibility_bypass_contract
A2ANatsTransport
publish_task
ModelProbe
happy_path
duplicate_path
handler_failure_redelivery_path
dlq_failure_path
restart_path
governance_negative_path
source_fingerprints
dharma.nats.live_production_matrix.v1
""",
    )
    _write(
        paths["nats_live_evidence"],
        """
REQUIRED_ROWS
PUBLISH_ENTRYPOINT
CONSUME_ENTRYPOINT
validate_production_path
validate_compatibility_bypass
happy_path
duplicate_path
max_deliver_path
dlq_failure_path
restart_path
governance_negative_path
source_fingerprints
validate_source_freshness
dharma.nats.live_production_matrix.v1
""",
    )
    _write(
        paths["nats_transport_tests"],
        """
test_publish_failure_is_retryable_not_duplicate
test_consume_server_must_require_execution_identity
test_consume_failure_redelivery_retries_handler_instead_of_duplicate_ack
test_consume_stale_started_record_is_retryable
test_consume_in_progress_duplicate_is_nacked_not_acked
test_duplicate_consume_ack_failure_records_truth_not_duplicate_success
test_consume_max_delivery_publishes_dlq_and_acks_original
test_transport_can_declare_durable_stream_and_consumer_contract
test_execution_identity_run_id_conflict_is_rejected
dharma.nats.envelope.v1
Nats-Msg-Id
""",
    )
    _write(
        paths["nats_contract_tests"],
        """
check_contract
test_contract_checker_fails_when_nats_transport_wiring_missing
test_contract_checker_fails_when_regression_tests_are_disconnected
test_contract_checker_fails_when_a2a_send_can_overclaim_production
""",
    )
    return paths


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")
