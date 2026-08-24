from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.runtime import sadhana_oracle_sandbox as sandbox


EVIDENCE_DIGEST = "sha256:" + "9" * 64


def _manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "dharma.sadhana.held_out_oracle_manifest.v1",
        "campaign_id": sandbox.MISSION_ID,
        "mission_id": sandbox.MISSION_ID,
        "goal_id": sandbox.GOAL_ID,
        "task_id": "task-g10",
        "task_creation_hash": "8" * 64,
        "evaluator_path": str(sandbox.EVALUATOR_PATH),
        "evaluator_sha256": f"sha256:{sandbox.EVALUATOR_SHA256}",
        "policy_path": str(sandbox.POLICY_PATH),
        "policy_sha256": f"sha256:{sandbox.POLICY_SHA256}",
        "required_evidence_ids": ["P06_ORACLE_SANDBOX"],
        "oracle_version": "v1",
    }
    payload["manifest_digest"] = sandbox._digest(payload)
    return payload


def _request(manifest: dict[str, object]) -> dict[str, str]:
    idempotency = "g10-oracle-idempotency"
    run_id = "g10-verifier-run"
    payload = {
        "schema_version": sandbox.REQUEST_SCHEMA,
        "request_id": hashlib.sha256(idempotency.encode("utf-8")).hexdigest(),
        "idempotency_key": idempotency,
        "campaign_id": sandbox.MISSION_ID,
        "mission_id": sandbox.MISSION_ID,
        "goal_id": sandbox.GOAL_ID,
        "task_id": str(manifest["task_id"]),
        "verifier_run_id": run_id,
        "manifest_digest": str(manifest["manifest_digest"]),
        "evaluator_path": str(sandbox.EVALUATOR_PATH),
        "evaluator_sha256": f"sha256:{sandbox.EVALUATOR_SHA256}",
        "policy_path": str(sandbox.POLICY_PATH),
        "policy_sha256": f"sha256:{sandbox.POLICY_SHA256}",
        "input_path": str(sandbox.INPUT_ROOT / run_id / "input.json"),
        "input_sha256": "sha256:" + "7" * 64,
        "sandbox_evidence_sha256": EVIDENCE_DIGEST,
    }
    payload["request_digest"] = sandbox._digest(payload)
    return payload


def test_request_decoder_binds_exact_static_paths_and_self_digest() -> None:
    manifest = _manifest()
    request = _request(manifest)
    name = f"{request['request_id']}.oracle.json"
    assert sandbox._decode_request(
        sandbox._canonical(request),
        filename=name,
        evidence_digest=EVIDENCE_DIGEST,
        held_out_manifest=manifest,
    ) == request

    for field, value in (
        ("evaluator_path", "/tmp/attacker.py"),
        ("policy_path", "/tmp/attacker.json"),
        ("input_path", "/tmp/attacker-input.json"),
        ("sandbox_evidence_sha256", "sha256:" + "1" * 64),
    ):
        drift = dict(request)
        drift[field] = value
        drift["request_digest"] = sandbox._digest(drift, omit="request_digest")
        with pytest.raises(sandbox.InvalidOracleRequest):
            sandbox._decode_request(
                sandbox._canonical(drift),
                filename=name,
                evidence_digest=EVIDENCE_DIGEST,
                held_out_manifest=manifest,
            )


def _private_directory(path: Path, mode: int) -> None:
    path.mkdir(parents=True, mode=mode)
    os.chown(path, -1, os.getegid())
    path.chmod(mode)


def test_evaluator_run_persists_receipt_before_terminal_and_replays(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid = os.geteuid()
    gid = os.getegid()
    service = SimpleNamespace(pw_uid=uid, pw_gid=gid)
    oracle = SimpleNamespace(pw_uid=uid, pw_gid=gid)
    input_root = tmp_path / "inputs"
    claim_root = tmp_path / "claims"
    run_root = tmp_path / "runs"
    receipt_root = tmp_path / "receipts"
    terminal_root = tmp_path / "terminals"
    for path, mode in (
        (input_root, 0o700),
        (claim_root, 0o700),
        (run_root, 0o710),
        (receipt_root, 0o700),
        (terminal_root, 0o750),
    ):
        _private_directory(path, mode)
    monkeypatch.setattr(sandbox, "INPUT_ROOT", input_root)
    monkeypatch.setattr(sandbox, "CLAIM_ROOT", claim_root)
    monkeypatch.setattr(sandbox, "RUN_ROOT", run_root)
    monkeypatch.setattr(sandbox, "RECEIPT_ROOT", receipt_root)
    monkeypatch.setattr(sandbox, "TERMINAL_ROOT", terminal_root)

    manifest = _manifest()
    request = _request(manifest)
    request["input_path"] = str(
        input_root / request["verifier_run_id"] / "input.json"
    )
    input_payload = {"schema_version": "fixture.oracle.input.v1", "candidate": "x"}
    input_raw = sandbox._canonical(input_payload)
    request["input_sha256"] = "sha256:" + hashlib.sha256(input_raw).hexdigest()
    request["request_digest"] = sandbox._digest(request, omit="request_digest")
    source = input_root / request["verifier_run_id"]
    _private_directory(source, 0o700)
    (source / "input.json").write_bytes(input_raw)
    (source / "input.json").chmod(0o600)
    raw = sandbox._canonical(request)
    calls: list[tuple[str, ...]] = []

    def evaluator(argv, **kwargs):  # noqa: ANN001, ANN202
        calls.append(tuple(argv))
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["stdout"] is subprocess.DEVNULL
        assert kwargs["stderr"] is subprocess.DEVNULL
        assert "OLLAMA_API_KEY" not in kwargs["env"]
        output = Path(argv[-1])
        verdict = {
            "schema_version": "dharma.sadhana.held_out_oracle_verdict.v1",
            "manifest_digest": request["manifest_digest"],
            "candidate_output_sha256": "sha256:" + "4" * 64,
            "evidence_bundle_sha256": "sha256:" + "5" * 64,
            "accepted": False,
            "verdict": "BLOCKED",
            "predicates": [],
        }
        output.write_bytes(sandbox._canonical(verdict))
        output.chmod(0o600)
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    completed = datetime(2026, 8, 23, 4, 0, tzinfo=timezone.utc)
    sandbox._run_one(
        request,
        raw=raw,
        evaluator=b"# evaluator\n",
        policy=b"{}\n",
        evidence_digest=EVIDENCE_DIGEST,
        service=service,
        oracle=oracle,
        runner=evaluator,
        now=lambda: completed,
        process_barrier=lambda: None,
        root_uid=uid,
        root_gid=gid,
    )
    assert len(calls) == 1
    assert calls[0][0] == sandbox.SETPRIV_PATH
    assert calls[0][9] == sandbox.PYTHON_PATH
    assert calls[0][-6::2] == ("--policy", "--input", "--output")
    request_id = request["request_id"]
    receipt_path = receipt_root / f"{request_id}.sandbox.json"
    terminal_path = terminal_root / f"{request_id}.terminal.json"
    receipt = json.loads(receipt_path.read_bytes())
    terminal = json.loads(terminal_path.read_bytes())
    assert receipt["request_digest"] == request["request_digest"]
    assert receipt["evaluator_sha256"] == request["evaluator_sha256"]
    assert receipt["policy_sha256"] == request["policy_sha256"]
    assert receipt["input_sha256"] == request["input_sha256"]
    assert receipt["output_identity"]["size"] > 0
    assert receipt["terminal_digest"] == terminal["terminal_digest"]
    assert receipt["terminal_payload"] == terminal
    assert terminal["sandbox_evidence_sha256"] == EVIDENCE_DIGEST

    def must_not_execute(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("durable receipt replay must not execute evaluator")

    sandbox._run_one(
        request,
        raw=raw,
        evaluator=b"# evaluator\n",
        policy=b"{}\n",
        evidence_digest=EVIDENCE_DIGEST,
        service=service,
        oracle=oracle,
        runner=must_not_execute,
        now=lambda: completed,
        process_barrier=lambda: None,
        root_uid=uid,
        root_gid=gid,
    )
    assert terminal_path.read_bytes() == sandbox._canonical(terminal)


def test_sandbox_evidence_is_exactly_release_and_unit_bound() -> None:
    receipt: dict[str, object] = {
        "schema_version": sandbox.SANDBOX_EVIDENCE_SCHEMA,
        "campaign_id": sandbox.MISSION_ID,
        "release_sha": "a" * 40,
        "worker_unit_path": str(sandbox.WORKER_UNIT_PATH),
        "worker_unit_sha256": "b" * 64,
        "private_network": True,
        "network_interfaces": ["lo"],
        "non_loopback_route_count": 0,
        "protect_system_strict": True,
        "no_new_privileges": True,
        "oracle_identity_separated": True,
        "canonical_state_inaccessible": True,
        "credential_root_inaccessible": True,
        "probe_output_created_and_removed": True,
        "evaluator_executed": False,
        "verdict": "PASS",
        "receipt_digest": "",
    }
    receipt["receipt_digest"] = sandbox._digest(receipt, omit="receipt_digest")
    assert sandbox._decode_evidence(
        sandbox._canonical(receipt),
        release_sha="a" * 40,
        worker_unit_sha256="b" * 64,
    )["receipt_digest"] == receipt["receipt_digest"]
    with pytest.raises(sandbox.OracleSandboxError, match="binding"):
        sandbox._decode_evidence(
            sandbox._canonical(receipt),
            release_sha="a" * 40,
            worker_unit_sha256="c" * 64,
        )


def test_evaluator_cgroup_barrier_rejects_a_lingering_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = tmp_path / "proc"
    cgroup = tmp_path / "cgroup"
    (proc / "self").mkdir(parents=True)
    (proc / "self/cgroup").write_text("0::/unit/oracle\n", encoding="ascii")
    members = cgroup / "unit/oracle"
    members.mkdir(parents=True)
    monkeypatch.setattr(sandbox.os, "getpid", lambda: 41)
    (members / "cgroup.procs").write_text("41\n", encoding="ascii")
    sandbox._require_solo_unit_process(proc_root=proc, cgroup_root=cgroup)
    (members / "cgroup.procs").write_text("41\n42\n", encoding="ascii")
    with pytest.raises(sandbox.OracleSandboxError, match="surviving child"):
        sandbox._require_solo_unit_process(proc_root=proc, cgroup_root=cgroup)


def test_oracle_clock_is_exactly_half_open() -> None:
    assert sandbox._guard_clock(sandbox.CAMPAIGN_START) == sandbox.CAMPAIGN_START
    with pytest.raises(sandbox.OracleSandboxError, match="timebox"):
        sandbox._guard_clock(sandbox.CAMPAIGN_START.replace(year=2025))
    with pytest.raises(sandbox.OracleSandboxError, match="timebox"):
        sandbox._guard_clock(sandbox.CAMPAIGN_STOP)
