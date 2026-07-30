"""Tests for typed live-host NATS evidence assessment."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


_CHECKER_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "governance"
    / "check_nats_live_production_evidence.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "check_nats_live_production_evidence_test",
    _CHECKER_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)


def _iso(when: datetime) -> str:
    return when.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _common_payload(tmp_path: Path, monkeypatch) -> dict[str, object]:
    source = tmp_path / "source.py"
    source.write_text("SOURCE = 'current'\n", encoding="utf-8")
    generated_at = datetime.now(UTC)
    monkeypatch.setattr(_MODULE, "ROOT", tmp_path)
    monkeypatch.setattr(_MODULE, "SOURCE_FRESHNESS_PATHS", ["source.py"])

    rows: list[dict[str, object]] = []
    for name in _MODULE.REQUIRED_ROWS:
        row: dict[str, object] = {
            "name": name,
            "status": "pass",
            "timestamp": _iso(generated_at),
            "broker_url": "nats://daemon.internal:4222",
            "stream_name": "DS_TASKS",
            "consumer_name": "a2a_task_handler",
        }
        if name in _MODULE.TASK_ROWS:
            row.update(
                {
                    "message_id": f"message-{name}",
                    "trace_id": f"trace-{name}",
                    "task_id": f"task-{name}",
                    "agent_id": "matrix-agent",
                    "model_provider_id": "deterministic:test",
                }
            )
        rows.append(row)

    return {
        "schema": "dharma.nats.live_production_matrix.v1",
        "host_mode": "live",
        "status": "pass",
        "generated_at": _iso(generated_at),
        "broker_url": "nats://daemon.internal:4222",
        "broker_profile": "daemon-production",
        "stream_name": "DS_TASKS",
        "dlq_stream_name": "DS_DLQ",
        "consumer_name": "a2a_task_handler",
        "required_rows": list(_MODULE.REQUIRED_ROWS),
        "missing_rows": [],
        "failed_rows": [],
        "rows": rows,
        "command": [
            sys.executable,
            str(_CHECKER_PATH.with_name("run_nats_live_production_matrix.py")),
            "--host-mode",
            "live",
        ],
        "source_fingerprints": {
            "source.py": {
                "exists": True,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        },
    }


def _full_valid_payload(tmp_path: Path, monkeypatch) -> dict[str, object]:
    payload = _common_payload(tmp_path, monkeypatch)
    rows = {row["name"]: row for row in payload["rows"]}
    ack = {"status": "ack", "action": "ack"}
    nack = {"status": "nack", "action": "nack"}
    contract = {
        "publish_entrypoint": _MODULE.PUBLISH_ENTRYPOINT,
        "transport_class": _MODULE.TRANSPORT_CLASS,
        "compatibility_publishers_can_satisfy_production_gate": False,
        "consume_entrypoint": _MODULE.CONSUME_ENTRYPOINT,
        "consumer_class": _MODULE.CONSUMER_CLASS,
        "consumer_require_execution_identity": True,
        "handler_contract": {"callable": "fixture.handler"},
    }
    for name in _MODULE.TASK_ROWS:
        rows[name]["production_path_contract"] = copy.deepcopy(contract)

    rows["topology"].update(
        {
            "dlq_stream_name": "DS_DLQ",
            "stream_subjects": ["dharma.a2a.task.>"],
            "dlq_subjects": ["dharma.dlq.>"],
            "consumer_filter_subject": "dharma.a2a.task.>",
            "consumer_ack_policy": "EXPLICIT",
            "consumer_max_deliver": 3,
            "consumer_ack_wait_seconds": 30,
        }
    )

    happy = rows["happy_path"]
    receipt = tmp_path / "semantic_receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "schema": "dharma.nats.live_matrix.semantic_receipt.v1",
                "task_id": happy["task_id"],
                "trace_id": happy["trace_id"],
                "provider": "deterministic",
                "requested_model": "test",
                "response_model": "fixture-model",
                "content": '{"ok": true}',
            }
        ),
        encoding="utf-8",
    )
    happy.update(
        {
            "publish_ack": ack,
            "consume_ack": ack,
            "side_effect_count": 1,
            "envelope_contract": {
                "schema": "dharma.nats.envelope.v1",
                "message_id": happy["message_id"],
                "actor": {
                    "from_agent": "operator",
                    "to_agent": "worker",
                    "execution_agent": "worker",
                },
                "causality": {
                    "message_id": happy["message_id"],
                    "trace_id": happy["trace_id"],
                    "span_id": "span-fixture",
                    "correlation_id": "correlation-fixture",
                    "causation_id": "causation-fixture",
                },
                "payload_schema": "dharma.a2a.nats_task.v1",
                "nats_msg_id": happy["message_id"],
            },
            "headers": {"Nats-Msg-Id": happy["message_id"]},
            "receipt_path": str(receipt),
        }
    )
    rows["duplicate_path"].update(
        {
            "production_path_contract": {
                "publish_entrypoint": _MODULE.PUBLISH_ENTRYPOINT,
                "transport_class": _MODULE.TRANSPORT_CLASS,
                "compatibility_publishers_can_satisfy_production_gate": False,
            },
            "side_effect_count_after_replay": 1,
            "broker_duplicate_probe_entrypoint": "nats.aio.client.JetStreamContext.publish",
            "broker_duplicate_probe_purpose": "direct proof only; not a production task publisher",
            "runtime_duplicate_publish_ack": {"status": "duplicate"},
        }
    )
    rows["publish_failure_path"].update(
        {
            "forced_failure": "fixture publish rejection",
            "retry_publish_ack": {"status": "ack"},
            "consume_ack": ack,
        }
    )
    rows["handler_failure_redelivery_path"].update(
        {
            "first_consume_ack": nack,
            "second_consume_ack": ack,
            "handler_attempts": 2,
        }
    )
    rows["stale_started_idempotency_path"].update(
        {"preexisting_idempotency_status": "started", "consume_ack": ack}
    )
    rows["concurrent_duplicate_path"].update(
        {
            "preexisting_idempotency_status": "started",
            "blocked_consume_ack": nack,
            "cleanup_consume_ack": ack,
            "side_effect_count": 1,
        }
    )
    rows["ack_failure_path"].update({"failed_ack": nack, "cleanup_ack": ack})
    max_deliver = rows["max_deliver_path"]
    max_deliver.update(
        {
            "deliveries": [1, 2, 3],
            "final_ack": ack,
            "dlq_subject": "dharma.dlq.DS_TASKS.a2a_task_handler",
            "dlq_envelope": {
                "schema": "dharma.nats.envelope.v1",
                "actor": {},
                "causality": {},
                "payload": {
                    "schema": "dharma.nats.dlq_failure.v1",
                    "original_message_id": max_deliver["message_id"],
                },
            },
        }
    )
    rows["dlq_failure_path"].update(
        {
            "final_ack": {"status": "nack", "action": "nack", "dlq_failed": True},
            "operator_visible": True,
            "operator_visible_state": {
                "ack_floor": {"stream_seq": 4},
                "final_stream_sequence": 5,
            },
        }
    )
    rows["restart_path"].update(
        {
            "cleanup_ack": ack,
            "first_delivery_metadata": {"stream_sequence": 9},
            "redelivery_metadata": {"stream_sequence": 9, "num_delivered": 2},
        }
    )
    rows["compatibility_bypass_contract"].update(
        {
            "compatibility_publishers_can_satisfy_production_gate": False,
            "canonical_runtime_truth_nats_task_path": _MODULE.PUBLISH_ENTRYPOINT,
            "checks": {
                "a2a_send_marks_noncanonical": True,
                "a2a_send_declares_gate_ineligible": True,
                "a2a_send_names_canonical_transport": True,
                "domain_reply_worker_uses_domain_receipt_schema": True,
                "domain_reply_worker_does_not_mint_nats_envelope_v1": True,
            },
            "gate_enforced_by": [
                "scripts/governance/check_nats_live_production_evidence.py"
            ],
            "compatibility_surfaces": [
                {
                    "path": "scripts/runtime/a2a_send.py",
                    "may_satisfy_production_gate": False,
                }
            ],
        }
    )
    rows["governance_negative_path"].update(
        {
            "negative_return_code": 1,
            "tampered_row_removed": "happy_path",
            "expected_failure_contains": "missing required rows",
            "negative_stdout": "",
            "negative_stderr": "missing required rows",
        }
    )
    return payload


def test_missing_evidence_on_non_live_host_is_needs_host(tmp_path: Path) -> None:
    assessment = _MODULE.evaluate_evidence(
        tmp_path / "missing.json",
        host_mode="non-live",
        max_age_hours=24,
        source_grace_seconds=2,
    )

    assert assessment.verdict == _MODULE.VERDICT_NEEDS_HOST
    assert assessment.exit_code == 2
    assert assessment.exit_code != _MODULE.EXIT_PASS


def test_missing_evidence_on_live_host_is_fail(tmp_path: Path) -> None:
    assessment = _MODULE.evaluate_evidence(
        tmp_path / "missing.json",
        host_mode="live",
        max_age_hours=24,
        source_grace_seconds=2,
    )

    assert assessment.verdict == _MODULE.VERDICT_FAIL
    assert assessment.exit_code == _MODULE.EXIT_FAIL


def test_stale_declared_live_evidence_is_fail(tmp_path: Path) -> None:
    path = tmp_path / "stale.json"
    path.write_text(
        json.dumps(
            {
                "schema": "dharma.nats.live_production_matrix.v1",
                "host_mode": "live",
                "status": "pass",
                "generated_at": _iso(datetime.now(UTC) - timedelta(days=3)),
            }
        ),
        encoding="utf-8",
    )

    assessment = _MODULE.evaluate_evidence(
        path,
        host_mode="live",
        max_age_hours=24,
        source_grace_seconds=2,
    )

    assert assessment.verdict == _MODULE.VERDICT_FAIL
    assert "stale" in assessment.reason


def test_fresh_valid_evidence_preserves_pass_verdict(
    tmp_path: Path,
    monkeypatch,
) -> None:
    payload = _full_valid_payload(tmp_path, monkeypatch)
    path = tmp_path / "fresh.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assessment = _MODULE.evaluate_evidence(
        path,
        host_mode="live",
        max_age_hours=24,
        source_grace_seconds=2,
        expected_broker_url="nats://daemon.internal:4222",
        expected_broker_profile="daemon-production",
        repo_root=tmp_path,
    )

    assert assessment.verdict == _MODULE.VERDICT_PASS
    assert assessment.exit_code == _MODULE.EXIT_PASS


def test_common_contract_binds_source_broker_profile_command_and_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    payload = _common_payload(tmp_path, monkeypatch)

    rows = _MODULE.validate_common(
        payload,
        24,
        source_grace_seconds=2,
        expected_broker_url="nats://daemon.internal:4222",
        expected_broker_profile="daemon-production",
        repo_root=tmp_path,
    )

    assert set(rows) == set(_MODULE.REQUIRED_ROWS)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda payload: payload["rows"].append(copy.deepcopy(payload["rows"][0])),
            "duplicate evidence row",
        ),
        (
            lambda payload: payload["rows"][1].__setitem__(
                "broker_url",
                "nats://wrong-host:4222",
            ),
            "broker_url mismatch",
        ),
        (
            lambda payload: payload.__setitem__("required_rows", []),
            "required_rows mismatch",
        ),
        (
            lambda payload: payload.__setitem__("command", [sys.executable, "other.py"]),
            "runner cannot be resolved",
        ),
    ],
)
def test_common_contract_rejects_unbound_evidence(
    tmp_path: Path,
    monkeypatch,
    mutation,
    expected: str,
) -> None:
    payload = _common_payload(tmp_path, monkeypatch)
    mutation(payload)

    with pytest.raises(_MODULE.EvidenceError, match=expected):
        _MODULE.validate_common(
            payload,
            24,
            source_grace_seconds=2,
            expected_broker_url="nats://daemon.internal:4222",
            expected_broker_profile="daemon-production",
            repo_root=tmp_path,
        )


def test_common_contract_rejects_alternate_existing_runner_with_canonical_basename(
    tmp_path: Path,
    monkeypatch,
) -> None:
    payload = _common_payload(tmp_path, monkeypatch)
    attacker = tmp_path / "attacker" / "run_nats_live_production_matrix.py"
    attacker.parent.mkdir()
    attacker.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    payload["command"][1] = str(attacker)

    with pytest.raises(_MODULE.EvidenceError, match="canonical live matrix runner"):
        _MODULE.validate_common(
            payload,
            24,
            source_grace_seconds=2,
            expected_broker_url="nats://daemon.internal:4222",
            expected_broker_profile="daemon-production",
            repo_root=tmp_path,
        )


@pytest.mark.parametrize(
    ("field", "forged_value", "expected"),
    [
        ("task_id", "forged-task", "semantic receipt task_id mismatch"),
        ("trace_id", "forged-trace", "semantic receipt trace_id mismatch"),
        ("provider", "forged-provider", "semantic receipt provider mismatch"),
        (
            "requested_model",
            "forged-model",
            "semantic receipt requested_model mismatch",
        ),
    ],
)
def test_happy_path_rejects_semantic_receipt_identity_mismatch(
    tmp_path: Path,
    monkeypatch,
    field: str,
    forged_value: str,
    expected: str,
) -> None:
    payload = _full_valid_payload(tmp_path, monkeypatch)
    rows = {row["name"]: row for row in payload["rows"]}
    receipt_path = Path(rows["happy_path"]["receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt[field] = forged_value
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    evidence = tmp_path / f"mismatched-{field}.json"
    evidence.write_text(json.dumps(payload), encoding="utf-8")

    assessment = _MODULE.evaluate_evidence(
        evidence,
        host_mode="live",
        max_age_hours=24,
        source_grace_seconds=2,
        expected_broker_url="nats://daemon.internal:4222",
        expected_broker_profile="daemon-production",
        repo_root=tmp_path,
    )

    assert assessment.verdict == _MODULE.VERDICT_FAIL
    assert assessment.exit_code == _MODULE.EXIT_FAIL
    assert expected in assessment.reason


def test_repeated_host_mode_last_live_is_accepted(tmp_path: Path, monkeypatch) -> None:
    # argparse takes the last occurrence of a repeated flag: a wrapper default
    # followed by an explicit --host-mode live runs live and must validate.
    payload = _common_payload(tmp_path, monkeypatch)
    payload["command"] = payload["command"][:2] + [
        "--host-mode",
        "non-live",
        "--host-mode",
        "live",
    ]

    rows = _MODULE.validate_common(
        payload,
        24,
        source_grace_seconds=2,
        expected_broker_url="nats://daemon.internal:4222",
        expected_broker_profile="daemon-production",
        repo_root=tmp_path,
    )

    assert set(rows) == set(_MODULE.REQUIRED_ROWS)


def test_repeated_host_mode_last_non_live_is_rejected(
    tmp_path: Path, monkeypatch
) -> None:
    # The inverse ordering runs non-live under argparse; grading the first
    # occurrence would wrongly accept it as live evidence.
    payload = _common_payload(tmp_path, monkeypatch)
    payload["command"] = payload["command"][:2] + [
        "--host-mode",
        "live",
        "--host-mode",
        "non-live",
    ]

    with pytest.raises(
        _MODULE.EvidenceError, match="did not declare --host-mode live"
    ):
        _MODULE.validate_common(
            payload,
            24,
            source_grace_seconds=2,
            expected_broker_url="nats://daemon.internal:4222",
            expected_broker_profile="daemon-production",
            repo_root=tmp_path,
        )


def test_source_hash_change_invalidates_evidence(tmp_path: Path, monkeypatch) -> None:
    payload = _common_payload(tmp_path, monkeypatch)
    (tmp_path / "source.py").write_text("SOURCE = 'changed'\n", encoding="utf-8")

    with pytest.raises(_MODULE.EvidenceError, match="source hash is stale"):
        _MODULE.validate_common(
            payload,
            24,
            source_grace_seconds=2,
            repo_root=tmp_path,
        )


def test_cli_renders_typed_needs_host_without_promoting_it(
    tmp_path: Path,
    capsys,
) -> None:
    result = _MODULE.main(
        [
            "--evidence",
            str(tmp_path / "missing.json"),
            "--host-mode",
            "non-live",
        ]
    )

    output = capsys.readouterr()
    assert result == _MODULE.EXIT_NEEDS_HOST == 2
    assert "NATS_LIVE_PRODUCTION_EVIDENCE_NEEDS_HOST" in output.out
    assert "NATS_LIVE_PRODUCTION_EVIDENCE_PASS" not in output.out


def test_non_live_default_does_not_inherit_ambient_stale_evidence(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    ambient = tmp_path / "tracked-latest.json"
    ambient.write_text(
        json.dumps(
            {
                "schema": "dharma.nats.live_production_matrix.v1",
                "host_mode": "live",
                "status": "pass",
                "generated_at": _iso(datetime.now(UTC) - timedelta(days=30)),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(_MODULE, "DEFAULT_EVIDENCE", ambient)

    result = _MODULE.main(["--host-mode", "non-live"])

    output = capsys.readouterr()
    assert result == _MODULE.EXIT_NEEDS_HOST == 2
    assert "tracked or ambient live artifacts are not inherited" in output.out


# ── matrix runner argv/environment hygiene (Codex P2s on PR #1164) ──

_RUNNER_PATH = _CHECKER_PATH.with_name("run_nats_live_production_matrix.py")
_RUNNER_SPEC = importlib.util.spec_from_file_location(
    "run_nats_live_production_matrix_under_test", _RUNNER_PATH
)
_RUNNER = importlib.util.module_from_spec(_RUNNER_SPEC)
sys.modules[_RUNNER_SPEC.name] = _RUNNER
_RUNNER_SPEC.loader.exec_module(_RUNNER)


def test_invalid_env_host_mode_fails_closed(monkeypatch, capsys) -> None:
    # choices= does not validate environment-supplied defaults; an
    # unrecognized mode must never fall through to the live branch.
    monkeypatch.setenv("DHARMA_NATS_HOST_MODE", "lvie")
    with pytest.raises(SystemExit) as excinfo:
        _RUNNER.parse_args([])
    assert excinfo.value.code == 2
    assert "must be 'non-live' or 'live'" in capsys.readouterr().err


def test_env_live_mode_is_recorded_in_command_argv(monkeypatch) -> None:
    # An environment-only live invocation must still record the explicit
    # flag its own post-run evidence validation requires.
    monkeypatch.setenv("DHARMA_NATS_HOST_MODE", "live")
    args = _RUNNER.parse_args([])
    assert args.host_mode == "live"
    assert args.command_argv[-2:] == ["--host-mode", "live"]


def test_explicit_host_mode_flag_is_not_duplicated(monkeypatch) -> None:
    monkeypatch.delenv("DHARMA_NATS_HOST_MODE", raising=False)
    args = _RUNNER.parse_args(["--host-mode", "live"])
    assert args.command_argv.count("--host-mode") == 1


def test_malformed_model_timeout_does_not_break_non_live_parse(monkeypatch) -> None:
    # The live-only timeout must stay unconverted at parse time so a
    # non-live host with inherited junk still reaches its typed verdict.
    monkeypatch.setenv("DHARMA_MATRIX_MODEL_TIMEOUT", "ninety")
    monkeypatch.delenv("DHARMA_NATS_HOST_MODE", raising=False)
    args = _RUNNER.parse_args([])
    assert args.host_mode == "non-live"
    assert args.model_timeout == "ninety"


def test_equals_form_host_mode_live_is_accepted(tmp_path: Path, monkeypatch) -> None:
    # argparse accepts --host-mode=live; the validator must not reject it
    # as a missing declaration.
    payload = _common_payload(tmp_path, monkeypatch)
    payload["command"] = payload["command"][:2] + ["--host-mode=live"]

    rows = _MODULE.validate_common(
        payload,
        24,
        source_grace_seconds=2,
        expected_broker_url="nats://daemon.internal:4222",
        expected_broker_profile="daemon-production",
        repo_root=tmp_path,
    )

    assert set(rows) == set(_MODULE.REQUIRED_ROWS)


def test_equals_form_last_non_live_is_rejected(tmp_path: Path, monkeypatch) -> None:
    # A trailing equals-form non-live override runs non-live under argparse;
    # a scan blind to the equals form would grade the earlier live token.
    payload = _common_payload(tmp_path, monkeypatch)
    payload["command"] = payload["command"][:2] + [
        "--host-mode",
        "live",
        "--host-mode=non-live",
    ]

    with pytest.raises(
        _MODULE.EvidenceError, match="did not declare --host-mode live"
    ):
        _MODULE.validate_common(
            payload,
            24,
            source_grace_seconds=2,
            expected_broker_url="nats://daemon.internal:4222",
            expected_broker_profile="daemon-production",
            repo_root=tmp_path,
        )
