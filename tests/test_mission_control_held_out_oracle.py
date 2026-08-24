from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import pytest

from dharma_swarm.mission_control_execution import (
    OwnerExecutionObservation,
    OwnerExecutionRef,
)
from dharma_swarm.mission_control_held_out_oracle import (
    G10_EVIDENCE_DIRECTORY,
    G10_REQUIRED_EVIDENCE_IDS,
    G10_REQUIRED_PREDICATE_IDS,
    HELD_OUT_MANIFEST_SCHEMA,
    HeldOutOracleError,
    held_out_manifest_digest,
    run_held_out_oracle,
)
from dharma_swarm.mission_control_oracle_launcher import (
    OracleLaunchRequest,
    OracleLaunchTerminal,
)
from dharma_swarm.models import Task, TaskStatus
from dharma_swarm.runtime_state import DelegationRun, RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity


CAMPAIGN = "sadhana-10-20260823"
TASK_ID = "g10-task-fixture"
PRODUCER_RUN = "g10-producer-run"
CANDIDATE = "UNTRUSTED CANDIDATE PROSE MUST NEVER ENTER ORACLE INPUT"


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        + b"\n"
    )


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _clock() -> datetime:
    return datetime(2030, 1, 1, 0, 0, 2, tzinfo=timezone.utc)


@dataclass
class _Case:
    runtime: RuntimeStateStore
    manifest_path: Path
    manifest_digest: str
    task: Task
    candidate: OwnerExecutionObservation
    work_root: Path
    producer_run: DelegationRun
    launcher: _TestSandboxLauncher


class _TestSandboxLauncher:
    """Hermetic test fixture; production must inject an enforced worker boundary."""

    def __init__(self, evidence_sha256: str) -> None:
        self.sandbox_evidence_sha256 = evidence_sha256
        self.requests: list[OracleLaunchRequest] = []
        self.mutator: Callable[[dict[str, object]], None] | None = None
        self.raise_once_after_terminal = False

    async def launch(self, request: OracleLaunchRequest) -> OracleLaunchTerminal:
        assert request.sandbox_evidence_sha256 == self.sandbox_evidence_sha256
        self.requests.append(request)
        output_path = request.input_path.parent / "external-terminal-verdict.json"
        if not output_path.exists():
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                os.fspath(request.evaluator_path),
                "--policy",
                os.fspath(request.policy_path),
                "--input",
                os.fspath(request.input_path),
                "--output",
                os.fspath(output_path),
                cwd=os.fspath(output_path.parent),
            )
            assert await process.wait() == 0
            output_path.chmod(0o600)
        payload = json.loads(output_path.read_bytes())
        if self.mutator is not None:
            self.mutator(payload)
        raw = _canonical(payload)
        terminal = OracleLaunchTerminal(
            request_id=request.request_id,
            request_digest=request.as_payload()["request_digest"],
            status="completed",
            verdict_payload=json.loads(raw),
            verdict_sha256=_sha(raw),
            sandbox_evidence_sha256=request.sandbox_evidence_sha256,
            completed_at=_clock(),
            terminal_path=output_path,
            terminal_digest=_sha(b"fixture-terminal\n"),
        )
        if self.raise_once_after_terminal:
            self.raise_once_after_terminal = False
            raise RuntimeError("fixture transport crashed after terminal")
        return terminal


def _evaluator_source() -> bytes:
    predicate_ids = repr(list(G10_REQUIRED_PREDICATE_IDS))
    return f'''import argparse,json,os\nos.umask(0o077)\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument("--policy");p.add_argument("--input");p.add_argument("--output");a=p.parse_args()\nr=json.loads(Path(a.input).read_bytes()); entries=r["evidence_bundle"]["entries"]\nmissing=len(entries)!=8; accepted=not missing\nids={predicate_ids}\nout={{"schema_version":"dharma.sadhana.held_out_oracle_verdict.v1","manifest_digest":r["manifest_digest"],"candidate_output_sha256":r["candidate_output_sha256"],"evidence_bundle_sha256":r["evidence_bundle_sha256"],"accepted":accepted,"verdict":"ACCEPT" if accepted else "BLOCKED","predicates":[{{"id":item,"passed":accepted,"evidence_sha256":"sha256:"+("1"*64 if accepted else "0"*64),"detail_code":"PASS" if accepted else "EVIDENCE_MISSING"}} for item in ids]}}\nPath(a.output).write_text(json.dumps(out,ensure_ascii=False,separators=(",",":"),sort_keys=True)+"\\n")\n'''.encode()


async def _case(tmp_path: Path, *, evidence: bool) -> _Case:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    await runtime.init_db()
    evaluator = tmp_path / "g10-evaluator.py"
    evaluator.write_bytes(_evaluator_source())
    evaluator.chmod(0o600)
    policy_payload = {
        "schema_version": "dharma.sadhana.g10_oracle_policy.v1",
        "campaign_id": CAMPAIGN,
        "goal_id": "G10_SAFETY_TCB",
        "status": "PRECOMMITTED",
        "required_entry_ids": list(G10_REQUIRED_EVIDENCE_IDS),
        "predicates": [
            {"id": predicate_id, "evidence_id": evidence_id, "checks": [{}]}
            for predicate_id, evidence_id in zip(
                G10_REQUIRED_PREDICATE_IDS,
                G10_REQUIRED_EVIDENCE_IDS,
                strict=True,
            )
        ],
    }
    policy = tmp_path / "g10-policy.json"
    policy.write_bytes(_canonical(policy_payload))
    policy.chmod(0o600)
    manifest_payload = {
        "schema_version": HELD_OUT_MANIFEST_SCHEMA,
        "campaign_id": CAMPAIGN,
        "mission_id": CAMPAIGN,
        "goal_id": "G10_SAFETY_TCB",
        "task_id": TASK_ID,
        "task_creation_hash": "a" * 64,
        "evaluator_path": str(evaluator),
        "evaluator_sha256": _sha(evaluator.read_bytes()),
        "policy_path": str(policy),
        "policy_sha256": _sha(policy.read_bytes()),
        "required_evidence_ids": list(G10_REQUIRED_EVIDENCE_IDS),
        "oracle_version": "v1",
        "manifest_digest": "",
    }
    manifest_payload["manifest_digest"] = held_out_manifest_digest(manifest_payload)
    manifest = tmp_path / "held-out-oracle.json"
    manifest.write_bytes(_canonical(manifest_payload))
    manifest.chmod(0o600)
    sandbox_evidence_digest = "sha256:" + "0" * 64
    if evidence:
        evidence_root = tmp_path / G10_EVIDENCE_DIRECTORY
        evidence_root.mkdir(mode=0o700)
        for index, evidence_id in enumerate(G10_REQUIRED_EVIDENCE_IDS):
            record = {"schema_version": f"fixture.{evidence_id}.v1", "status": "PASS"}
            entry = {
                "schema_version": "dharma.sadhana.g10_evidence_entry.v1",
                "evidence_id": evidence_id,
                "record_kind": "test_receipt",
                "record_sha256": _sha(_canonical(record)),
                "record": record,
                "custody": {
                    "source_uri": f"test://held-out/{evidence_id}",
                    "observed_at": "2030-01-01T00:00:01+00:00",
                    "authority": "accepted_repo_test",
                    "immutable": True,
                },
            }
            path = evidence_root / f"{evidence_id}.json"
            path.write_bytes(_canonical(entry))
            path.chmod(0o600)
            if evidence_id == "oracle_sandbox":
                sandbox_evidence_digest = entry["record_sha256"]
    producer_started = datetime(2030, 1, 1, tzinfo=timezone.utc)
    producer_completed = producer_started + timedelta(seconds=1)
    identity = ExecutionIdentity.new(
        trace_id="producer-trace",
        correlation_id=f"mission_campaign:{CAMPAIGN}",
        task_id=TASK_ID,
        run_id=PRODUCER_RUN,
        claim_id="producer-claim",
        agent_id="producer-agent",
        session_id=f"mission_owner:{CAMPAIGN}",
        idempotency_key="producer-idempotency",
        metadata={"attempt_generation": 0},
    )
    await runtime.record_execution_identity(identity, source="test-producer")
    producer_run = DelegationRun(
        run_id=identity.run_id,
        task_id=identity.task_id,
        assigned_to=identity.agent_id,
        assigned_by="test",
        status="completed",
        session_id=identity.session_id,
        claim_id=identity.claim_id,
        started_at=producer_started,
        completed_at=producer_completed,
        metadata={"attempt_generation": 0},
    )
    await runtime.record_delegation_run(producer_run)
    task = Task(
        id=TASK_ID,
        title="G10_SAFETY_TCB",
        status=TaskStatus.COMPLETED,
        assigned_to="producer-agent",
        result=CANDIDATE,
        metadata={
            "mission_id": CAMPAIGN,
            "goal_id": "G10_SAFETY_TCB",
            "mission_task_creation_hash": "a" * 64,
            "attempt_generation": 0,
            "mission_campaign_authority": {
                "held_out_oracle_manifest_digest": manifest_payload["manifest_digest"],
                "attempt_generation": 0,
            },
        },
    )
    ref = OwnerExecutionRef(
        backend="orchestrator",
        mission_id=CAMPAIGN,
        task_id=TASK_ID,
        dispatch_key="default",
        run_id=PRODUCER_RUN,
        claim_id="producer-claim",
        agent_id="producer-agent",
        idempotency_key="producer-idempotency",
        owner_session_id=f"mission_owner:{CAMPAIGN}",
        attempt_generation=0,
    )
    candidate = OwnerExecutionObservation(
        ref=ref,
        task_status=TaskStatus.COMPLETED,
        run_status="completed",
        claim_status="completed",
        stale=False,
        receipt_ids=(),
        terminal=True,
        succeeded=True,
        result=CANDIDATE,
        failure_code="",
        observed_at=producer_completed,
    )
    work_root = tmp_path / "oracle-work"
    return _Case(
        runtime,
        manifest,
        str(manifest_payload["manifest_digest"]),
        task,
        candidate,
        work_root,
        producer_run,
        _TestSandboxLauncher(sandbox_evidence_digest),
    )


@pytest.mark.asyncio
async def test_missing_records_are_blocked_replayed_and_candidate_prose_excluded(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, evidence=False)
    first = await run_held_out_oracle(
        runtime=case.runtime,
        manifest_path=case.manifest_path,
        expected_manifest_digest=case.manifest_digest,
        task=case.task,
        candidate=case.candidate,
        work_root=case.work_root,
        sandbox_launcher=case.launcher,
        now=_clock,
    )
    second = await run_held_out_oracle(
        runtime=case.runtime,
        manifest_path=case.manifest_path,
        expected_manifest_digest=case.manifest_digest,
        task=case.task,
        candidate=case.candidate,
        work_root=case.work_root,
        sandbox_launcher=case.launcher,
        now=_clock,
    )
    assert first.status == "blocked" and first.acceptance is None
    assert second.run_id == first.run_id and second.replayed is True
    input_bytes = (case.work_root / first.run_id / "input.json").read_bytes()
    assert CANDIDATE.encode() not in input_bytes
    assert hashlib.sha256(CANDIDATE.encode()).hexdigest().encode() in input_bytes


@pytest.mark.asyncio
async def test_evidence_change_after_attempt_selection_never_launches(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, evidence=True)

    with pytest.raises(HeldOutOracleError, match="changed after attempt selection"):
        await run_held_out_oracle(
            runtime=case.runtime,
            manifest_path=case.manifest_path,
            expected_manifest_digest=case.manifest_digest,
            task=case.task,
            candidate=case.candidate,
            work_root=case.work_root,
            sandbox_launcher=case.launcher,
            expected_evidence_bundle_sha256="sha256:" + "f" * 64,
            now=_clock,
        )

    assert case.launcher.requests == []


@pytest.mark.asyncio
async def test_exact_eight_records_accept_and_crash_after_evidence_replays(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, evidence=True)
    first = await run_held_out_oracle(
        runtime=case.runtime,
        manifest_path=case.manifest_path,
        expected_manifest_digest=case.manifest_digest,
        task=case.task,
        candidate=case.candidate,
        work_root=case.work_root,
        sandbox_launcher=case.launcher,
        now=_clock,
    )
    assert first.status == "accept" and first.acceptance is not None
    run = await case.runtime.get_delegation_run(first.run_id)
    assert run is not None
    assert run.status == "completed" and run.completed_at is not None
    # Fixture-only persisted split state. Atomic finalization and public writers
    # cannot create this downgrade; inject it below the API to test evidence repair.
    with sqlite3.connect(case.runtime.db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        cursor = db.execute(
            "UPDATE delegation_runs SET status = 'running', completed_at = NULL"
            " WHERE run_id = ? AND session_id = ? AND task_id = ?"
            " AND claim_id = ? AND parent_run_id = ? AND assigned_by = ?"
            " AND assigned_to = ? AND requested_output_json = ?"
            " AND current_artifact_id = ? AND status = ? AND started_at = ?"
            " AND completed_at = ? AND failure_code = ? AND metadata_json = ?"
            " AND trace_id = ? AND receipt_json IS NULL",
            (
                run.run_id,
                run.session_id,
                run.task_id,
                run.claim_id,
                run.parent_run_id,
                run.assigned_by,
                run.assigned_to,
                json.dumps(run.requested_output, sort_keys=True, ensure_ascii=True),
                run.current_artifact_id,
                run.status,
                run.started_at.isoformat(),
                run.completed_at.isoformat(),
                run.failure_code,
                json.dumps(run.metadata, sort_keys=True, ensure_ascii=True),
                str(
                    run.metadata.get("trace_id")
                    or run.metadata.get("execution_identity", {}).get("trace_id")
                    or ""
                ),
            ),
        )
        assert cursor.rowcount == 1
        db.commit()
    replay = await run_held_out_oracle(
        runtime=case.runtime,
        manifest_path=case.manifest_path,
        expected_manifest_digest=case.manifest_digest,
        task=case.task,
        candidate=case.candidate,
        work_root=case.work_root,
        sandbox_launcher=case.launcher,
        now=_clock,
    )
    assert replay.replayed is True and replay.acceptance == first.acceptance
    repaired = await case.runtime.get_delegation_run(first.run_id)
    assert repaired is not None and repaired.status == "completed"


@pytest.mark.asyncio
async def test_malformed_record_fails_before_oracle_run_or_output(tmp_path: Path) -> None:
    case = await _case(tmp_path, evidence=True)
    path = case.manifest_path.parent / G10_EVIDENCE_DIRECTORY / "effect_audit.json"
    payload = json.loads(path.read_bytes())
    payload["record_sha256"] = "sha256:" + "f" * 64
    path.write_bytes(_canonical(payload))
    path.chmod(0o600)
    with pytest.raises(HeldOutOracleError, match="record digest conflicts"):
        await run_held_out_oracle(
            runtime=case.runtime,
            manifest_path=case.manifest_path,
            expected_manifest_digest=case.manifest_digest,
            task=case.task,
            candidate=case.candidate,
            work_root=case.work_root,
            sandbox_launcher=case.launcher,
        )
    assert not case.work_root.exists()


@pytest.mark.asyncio
async def test_foreign_manifest_digest_or_task_never_executes(tmp_path: Path) -> None:
    case = await _case(tmp_path, evidence=True)
    with pytest.raises(HeldOutOracleError, match="not precommitted"):
        await run_held_out_oracle(
            runtime=case.runtime,
            manifest_path=case.manifest_path,
            expected_manifest_digest="sha256:" + "f" * 64,
            task=case.task,
            candidate=case.candidate,
            work_root=case.work_root,
            sandbox_launcher=case.launcher,
        )
    foreign = case.task.model_copy(update={"id": "foreign-task"})
    with pytest.raises(HeldOutOracleError, match="candidate or authority"):
        await run_held_out_oracle(
            runtime=case.runtime,
            manifest_path=case.manifest_path,
            expected_manifest_digest=case.manifest_digest,
            task=foreign,
            candidate=case.candidate,
            work_root=case.work_root,
            sandbox_launcher=case.launcher,
        )
    assert not case.work_root.exists()


@pytest.mark.parametrize("custody_fault", ["symlink", "hardlink", "mode"])
async def test_evidence_file_custody_fault_never_launches(
    tmp_path: Path,
    custody_fault: str,
) -> None:
    case = await _case(tmp_path, evidence=True)
    path = case.manifest_path.parent / G10_EVIDENCE_DIRECTORY / "effect_audit.json"
    if custody_fault == "symlink":
        target = tmp_path / "foreign-effect.json"
        target.write_bytes(path.read_bytes())
        target.chmod(0o600)
        path.unlink()
        path.symlink_to(target)
    elif custody_fault == "hardlink":
        os.link(path, tmp_path / "foreign-hardlink.json")
    else:
        path.chmod(0o640)

    with pytest.raises(HeldOutOracleError):
        await run_held_out_oracle(
            runtime=case.runtime,
            manifest_path=case.manifest_path,
            expected_manifest_digest=case.manifest_digest,
            task=case.task,
            candidate=case.candidate,
            work_root=case.work_root,
            sandbox_launcher=case.launcher,
        )
    assert case.launcher.requests == []


@pytest.mark.parametrize("foreign_kind", ["duplicate_id", "ninth_entry"])
async def test_duplicate_or_extra_evidence_never_launches(
    tmp_path: Path,
    foreign_kind: str,
) -> None:
    case = await _case(tmp_path, evidence=True)
    root = case.manifest_path.parent / G10_EVIDENCE_DIRECTORY
    if foreign_kind == "duplicate_id":
        path = root / "effect_audit.json"
        payload = json.loads(path.read_bytes())
        payload["evidence_id"] = "authority_binding"
        path.write_bytes(_canonical(payload))
        path.chmod(0o600)
    else:
        extra = root / "ninth.json"
        extra.write_bytes(_canonical({"foreign": True}))
        extra.chmod(0o600)

    with pytest.raises(HeldOutOracleError):
        await run_held_out_oracle(
            runtime=case.runtime,
            manifest_path=case.manifest_path,
            expected_manifest_digest=case.manifest_digest,
            task=case.task,
            candidate=case.candidate,
            work_root=case.work_root,
            sandbox_launcher=case.launcher,
        )
    assert case.launcher.requests == []


@pytest.mark.parametrize("mutation", ["failed_predicate", "substituted_id"])
async def test_malicious_accept_verdict_is_rejected(
    tmp_path: Path,
    mutation: str,
) -> None:
    case = await _case(tmp_path, evidence=True)

    def mutate(payload: dict[str, object]) -> None:
        predicates = payload["predicates"]
        assert isinstance(predicates, list) and isinstance(predicates[0], dict)
        if mutation == "failed_predicate":
            predicates[0]["passed"] = False
            predicates[0]["detail_code"] = "EVIDENCE_MISSING"
        else:
            predicates[0]["id"] = "P01_SUBSTITUTED"

    case.launcher.mutator = mutate
    with pytest.raises(HeldOutOracleError):
        await run_held_out_oracle(
            runtime=case.runtime,
            manifest_path=case.manifest_path,
            expected_manifest_digest=case.manifest_digest,
            task=case.task,
            candidate=case.candidate,
            work_root=case.work_root,
            sandbox_launcher=case.launcher,
            now=_clock,
        )
    receipts = await case.runtime.list_runtime_receipts(
        receipt_type="mission_verifier_result",
        limit=5,
    )
    assert receipts == []


async def test_external_terminal_transport_crash_replays_exact_request(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, evidence=True)
    case.launcher.raise_once_after_terminal = True
    with pytest.raises(HeldOutOracleError, match="indeterminate"):
        await run_held_out_oracle(
            runtime=case.runtime,
            manifest_path=case.manifest_path,
            expected_manifest_digest=case.manifest_digest,
            task=case.task,
            candidate=case.candidate,
            work_root=case.work_root,
            sandbox_launcher=case.launcher,
            now=_clock,
        )
    run = (
        await case.runtime.list_delegation_runs(
            session_id=f"mission_verifier:{CAMPAIGN}", limit=5
        )
    )[0]
    assert run.status == "running"

    recovered = await run_held_out_oracle(
        runtime=case.runtime,
        manifest_path=case.manifest_path,
        expected_manifest_digest=case.manifest_digest,
        task=case.task,
        candidate=case.candidate,
        work_root=case.work_root,
        sandbox_launcher=case.launcher,
        now=_clock,
    )
    assert recovered.acceptance is not None
    assert len(case.launcher.requests) == 2
    assert case.launcher.requests[0].as_payload() == case.launcher.requests[1].as_payload()


@pytest.mark.parametrize("fault_boundary", ["receipt", "artifact", "lifecycle"])
async def test_atomic_finalize_rolls_back_each_db_fault_boundary(
    tmp_path: Path,
    fault_boundary: str,
) -> None:
    case = await _case(tmp_path, evidence=True)
    target = {
        "receipt": "INSERT ON runtime_receipts WHEN NEW.receipt_type = 'mission_verifier_result'",
        "artifact": "INSERT ON artifact_records",
        "lifecycle": "UPDATE ON delegation_runs WHEN NEW.status = 'completed'",
    }[fault_boundary]
    with sqlite3.connect(case.runtime.db_path) as db:
        db.execute(
            f"CREATE TRIGGER oracle_fault BEFORE {target} "
            "BEGIN SELECT RAISE(ABORT, 'fixture fault'); END"
        )
    with pytest.raises(HeldOutOracleError, match="atomic finalization"):
        await run_held_out_oracle(
            runtime=case.runtime,
            manifest_path=case.manifest_path,
            expected_manifest_digest=case.manifest_digest,
            task=case.task,
            candidate=case.candidate,
            work_root=case.work_root,
            sandbox_launcher=case.launcher,
            now=_clock,
        )
    run = (
        await case.runtime.list_delegation_runs(
            session_id=f"mission_verifier:{CAMPAIGN}", limit=5
        )
    )[0]
    assert run.status == "running"
    assert await case.runtime.list_artifacts(run_id=run.run_id, limit=5) == []
    assert await case.runtime.list_runtime_receipts(run_id=run.run_id, limit=5) == []

    with sqlite3.connect(case.runtime.db_path) as db:
        db.execute("DROP TRIGGER oracle_fault")
    recovered = await run_held_out_oracle(
        runtime=case.runtime,
        manifest_path=case.manifest_path,
        expected_manifest_digest=case.manifest_digest,
        task=case.task,
        candidate=case.candidate,
        work_root=case.work_root,
        sandbox_launcher=case.launcher,
        now=_clock,
    )
    assert recovered.acceptance is not None


async def test_task_attempt_generation_mismatch_never_launches(tmp_path: Path) -> None:
    case = await _case(tmp_path, evidence=True)
    foreign = case.task.model_copy(
        update={"metadata": {**case.task.metadata, "attempt_generation": 1}}
    )
    with pytest.raises(HeldOutOracleError, match="candidate or authority"):
        await run_held_out_oracle(
            runtime=case.runtime,
            manifest_path=case.manifest_path,
            expected_manifest_digest=case.manifest_digest,
            task=foreign,
            candidate=case.candidate,
            work_root=case.work_root,
            sandbox_launcher=case.launcher,
        )
    assert case.launcher.requests == []


async def test_stored_verdict_equivocation_is_rejected_without_relaunch(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, evidence=True)
    first = await run_held_out_oracle(
        runtime=case.runtime,
        manifest_path=case.manifest_path,
        expected_manifest_digest=case.manifest_digest,
        task=case.task,
        candidate=case.candidate,
        work_root=case.work_root,
        sandbox_launcher=case.launcher,
        now=_clock,
    )
    assert first.acceptance is not None
    receipt_id = first.acceptance.evidence_receipt_ids[0]
    receipt = await case.runtime.get_runtime_receipt(receipt_id)
    assert receipt is not None
    verdict = dict(receipt.payload["verdict_payload"])
    verdict["accepted"] = False
    forged_payload = {**receipt.payload, "verdict_payload": verdict}
    with sqlite3.connect(case.runtime.db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        cursor = db.execute(
            "UPDATE runtime_receipts SET payload_json = ? WHERE receipt_id = ?"
            " AND receipt_type = ? AND run_id = ? AND task_id = ?"
            " AND trace_id = ? AND correlation_id = ? AND causation_id = ?"
            " AND parent_run_id = ? AND agent_id = ? AND idempotency_key = ?"
            " AND side_effect_key = ? AND status = ? AND payload_json = ?"
            " AND created_at = ?",
            (
                json.dumps(forged_payload, sort_keys=True, ensure_ascii=True),
                receipt.receipt_id,
                receipt.receipt_type,
                receipt.run_id,
                receipt.task_id,
                receipt.trace_id,
                receipt.correlation_id,
                receipt.causation_id,
                receipt.parent_run_id,
                receipt.agent_id,
                receipt.idempotency_key,
                receipt.side_effect_key,
                receipt.status,
                json.dumps(receipt.payload, sort_keys=True, ensure_ascii=True),
                receipt.created_at.isoformat(),
            ),
        )
        assert cursor.rowcount == 1
        db.commit()

    with pytest.raises(HeldOutOracleError):
        await run_held_out_oracle(
            runtime=case.runtime,
            manifest_path=case.manifest_path,
            expected_manifest_digest=case.manifest_digest,
            task=case.task,
            candidate=case.candidate,
            work_root=case.work_root,
            sandbox_launcher=case.launcher,
            now=_clock,
        )
    assert len(case.launcher.requests) == 1
