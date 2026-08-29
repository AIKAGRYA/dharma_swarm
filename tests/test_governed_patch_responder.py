from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from scripts.runtime.governed_patch_responder import (
    CANDIDATE_DURABLE,
    INPUT_COMMITTED,
    PROVIDER_CALL_STARTED,
    PROVIDER_REFUSED,
    AuthorshipOutcome,
    BridgeEvidenceError,
    GovernedPatchResponderError,
    InputDriftError,
    LeaseUnavailableError,
    LedgerCorruptionError,
    ParsedRequest,
    ProviderCallUncertainError,
    SemanticProjection,
    _build_default_request_parser,
    _canonical_custody_paths,
    _git_blob_at_head,
    _git_head,
    _ledger_connection,
    _main_async,
    _normalize_outcome,
    _semantic_approval_checkpoint,
    load_bridge_delivery,
    process_once,
)


def _sha(value: str | bytes) -> str:
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


@dataclass
class _Fixture:
    root: Path
    repo: Path
    bridge_db: Path
    delivery_path: Path
    ledger_db: Path
    event_id: str
    artifact_sha: str


@pytest.fixture
def responder_fixture(tmp_path: Path) -> _Fixture:
    repo = tmp_path / "release"
    repo.mkdir()
    (repo / "target.py").write_text("VALUE = 1\n", encoding="utf-8")
    event_id = "packet-1"
    agent_uid = "codex_composer"
    subject = "dharma.a2a.agent.codex_composer.inbox"
    intent = {
        "schema_version": "dharma.a2a.governed_patch_intent.v1",
        "mission_id": "mission-1",
        "task_id": "task-1",
        "proposal_id": "proposal-1",
        "base_sha": "a" * 40,
        "authorized_source_path": "target.py",
        "oracle_argv": ["python3", "-m", "pytest", "-q"],
        "semantic_intent": "Change VALUE from one to two.",
    }
    content = json.dumps(
        intent, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    envelope = {
        "schema_version": "dharma.a2a.send.v1",
        "packet_id": event_id,
        "timestamp": "2026-08-28T00:00:00Z",
        "from": "operator",
        "to": agent_uid,
        "kind": "task",
        "route": "agent_inbox",
        "target_uid": agent_uid,
        "subject": subject,
        "ack_subject": f"{subject}.ack.{event_id}",
        "reply_subject": f"{subject}.reply.{event_id}",
        "content": content,
        "sha256": _sha(content),
    }
    envelope_json = json.dumps(envelope, ensure_ascii=True, sort_keys=True)
    envelope_sha = _sha(envelope_json)
    delivery = {
        "schema_version": "dharma.a2a.inbox_delivery.v1",
        "delivered_at": "2026-08-28T00:00:01Z",
        "agent_uid": agent_uid,
        "bridge_kind": "filesystem_delivery_handler",
        "source_subject": subject,
        "stream": "DHARMA_A2A",
        "consumer": "codex-composer",
        "envelope_sha256": envelope_sha,
        "envelope": envelope,
        "semantic_reply_claim": False,
        "peer_model_processed_claim": False,
    }
    delivery_path = tmp_path / "inboxes" / agent_uid / f"{event_id}.json"
    _write_json(delivery_path, delivery)
    bridge_db = tmp_path / "semantic_jobs.sqlite3"
    connection = sqlite3.connect(bridge_db)
    try:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            """
            CREATE TABLE semantic_jobs (
                event_id TEXT PRIMARY KEY,
                envelope_sha256 TEXT NOT NULL,
                envelope_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO semantic_jobs VALUES (?, ?, ?, 'PENDING', ?, ?)",
            (event_id, envelope_sha, envelope_json, "now", "now"),
        )
        connection.commit()
    finally:
        connection.close()
    return _Fixture(
        root=tmp_path,
        repo=repo,
        bridge_db=bridge_db,
        delivery_path=delivery_path,
        ledger_db=tmp_path / "external" / "governed_patch.sqlite3",
        event_id=event_id,
        artifact_sha="b" * 64,
    )


def _validator(fixture: _Fixture, *, marker: str = "stable"):
    async def validate(delivery):
        return SemanticProjection(
            semantic_artifact_sha256=fixture.artifact_sha,
            checkpoint={
                "schema_version": "test.semantic_projection.v1",
                "marker": marker,
                "packet_id": delivery.packet_id,
                "delivery_id": delivery.delivery_id,
                "artifact_sha256": fixture.artifact_sha,
            },
        )

    return validate


def _parser(
    boot_id: str,
    *,
    semantic_sha: str = "c" * 64,
    task_snapshot_sha: str = "d" * 64,
):
    async def parse(delivery, projection, prior_checkpoint):
        del projection
        bindings = {
            "mission_id": "mission-1",
            "task_id": "task-1",
            "attempt_id": delivery.packet_id,
            "lease_id": delivery.delivery_id,
            "packet_id": delivery.packet_id,
            "correlation_id": f"a2a_send:codex_composer:{delivery.packet_id}",
            "delivery_id": delivery.delivery_id,
            "proposal_id": "proposal-1",
            "base_sha": "a" * 40,
            "executor_agent_uid": "codex_composer",
            "executor_run_id": f"run-{boot_id}",
            "executor_process_boot_id": boot_id,
        }
        if prior_checkpoint is not None:
            bindings = dict(prior_checkpoint["native_bindings"])
        request_sha = _sha(json.dumps(bindings, sort_keys=True))
        checkpoint = {
            "schema_version": "dharma.a2a.governed_patch_request.v2",
            "native_bindings": bindings,
            "authorized_source_path": "target.py",
            "oracle_argv": ["python3", "-m", "pytest", "-q"],
            "request_content_sha256": request_sha,
            "source_sha256": _sha("VALUE = 1\n"),
            "semantic_intent_sha256": semantic_sha,
            "task_snapshot_sha256": task_snapshot_sha,
        }
        return ParsedRequest(request={"checkpoint": checkpoint}, checkpoint=checkpoint)

    return parse


def _receipt(request: dict[str, Any], call_id: str, artifact_sha: str, *, status: str):
    checkpoint = request["checkpoint"]
    receipt = {
        "schema_version": "dharma.governed_patch.provider_authorship.v1",
        "status": status,
        "provider_call_id": call_id,
        "native_bindings": checkpoint["native_bindings"],
        "request_content_sha256": checkpoint["request_content_sha256"],
        "source_sha256": checkpoint["source_sha256"],
        "semantic_intent_sha256": checkpoint["semantic_intent_sha256"],
        "task_snapshot_sha256": checkpoint["task_snapshot_sha256"],
        "semantic_artifact_sha256": artifact_sha,
        "authorized_source_path": checkpoint["authorized_source_path"],
        "candidate_bundle_sha256": "f" * 64 if status == "authored" else None,
        "diff_sha256": "2" * 64 if status == "authored" else None,
        "repository_effect_authorized": False,
        "repository_effect_performed": False,
        "mission_control_completion_authorized": False,
    }
    receipt["receipt_sha256"] = _sha(
        json.dumps(receipt, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    )
    return receipt


def _candidate(request: dict[str, Any]) -> dict[str, Any]:
    bindings = request["checkpoint"]["native_bindings"]
    return {
        "bundle_root": "/external/evidence",
        "repo_root": "/immutable/release",
        "relative_dir": f"candidates/sha256/{'f' * 64}",
        "bundle_sha256": "f" * 64,
        "candidate_digest": f"sha256:{'1' * 64}",
        "diff_sha256": "2" * 64,
        "request_content_sha256": request["checkpoint"]["request_content_sha256"],
        "source_sha256": request["checkpoint"]["source_sha256"],
        "authorized_source_path": request["checkpoint"]["authorized_source_path"],
        "semantic_artifact_sha256": "b" * 64,
        "semantic_intent_sha256": request["checkpoint"]["semantic_intent_sha256"],
        "task_snapshot_sha256": request["checkpoint"]["task_snapshot_sha256"],
        "executor_agent_uid": bindings["executor_agent_uid"],
        "executor_run_id": bindings["executor_run_id"],
        "executor_process_boot_id": bindings["executor_process_boot_id"],
    }


def _test_outcome_verifier(
    value: object,
    *,
    request: object,
    call_id: str,
    semantic_artifact_sha256: str,
    request_checkpoint: Mapping[str, Any],
) -> AuthorshipOutcome:
    """Explicit dependency-injection seam; production never accepts this shape."""
    assert type(request) is dict
    assert type(value) is AuthorshipOutcome
    receipt = dict(value.receipt)
    assert set(receipt) == {
        "schema_version",
        "receipt_sha256",
        "status",
        "provider_call_id",
        "native_bindings",
        "request_content_sha256",
        "source_sha256",
        "semantic_intent_sha256",
        "task_snapshot_sha256",
        "semantic_artifact_sha256",
        "authorized_source_path",
        "candidate_bundle_sha256",
        "diff_sha256",
        "repository_effect_authorized",
        "repository_effect_performed",
        "mission_control_completion_authorized",
    }
    body = {key: child for key, child in receipt.items() if key != "receipt_sha256"}
    assert receipt["receipt_sha256"] == _sha(
        json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    )
    assert receipt["provider_call_id"] == call_id
    assert receipt["semantic_artifact_sha256"] == semantic_artifact_sha256
    assert receipt["native_bindings"] == request_checkpoint["native_bindings"]
    for field in (
        "request_content_sha256",
        "source_sha256",
        "semantic_intent_sha256",
        "task_snapshot_sha256",
        "authorized_source_path",
    ):
        assert receipt[field] == request_checkpoint[field]
    assert receipt["repository_effect_authorized"] is False
    assert receipt["repository_effect_performed"] is False
    assert receipt["mission_control_completion_authorized"] is False
    if receipt["status"] == "refused":
        assert value.candidate is None
        return AuthorshipOutcome(receipt=receipt, candidate=None)
    assert receipt["status"] == "authored"
    assert value.candidate is not None
    candidate = dict(value.candidate)
    assert candidate["authorized_source_path"] == request_checkpoint[
        "authorized_source_path"
    ]
    assert candidate["semantic_artifact_sha256"] == semantic_artifact_sha256
    assert candidate["semantic_intent_sha256"] == request_checkpoint[
        "semantic_intent_sha256"
    ]
    assert candidate["task_snapshot_sha256"] == request_checkpoint[
        "task_snapshot_sha256"
    ]
    candidate.update(
        repository_effect_authorized=False,
        repository_effect_performed=False,
        mission_control_completion_authorized=False,
    )
    return AuthorshipOutcome(receipt=receipt, candidate=candidate)


def _author(fixture: _Fixture, calls: list[str], *, refused: bool = False):
    async def author(request, *, semantic_artifact_sha256, provider_call_id):
        calls.append(provider_call_id)
        status = "refused" if refused else "authored"
        return AuthorshipOutcome(
            receipt=_receipt(
                request, provider_call_id, semantic_artifact_sha256, status=status
            ),
            candidate=None if refused else _candidate(request),
        )

    return author


@pytest.mark.parametrize("forgery", ("extra_receipt_key", "missing_schema", "wrong_path"))
def test_production_outcome_boundary_rejects_injected_mapping(
    responder_fixture: _Fixture, forgery: str
) -> None:
    delivery = load_bridge_delivery(
        responder_fixture.bridge_db,
        responder_fixture.event_id,
        responder_fixture.delivery_path,
    )
    parsed = asyncio.run(_parser("boot-forgery")(delivery, None, None))
    call_id = "gpr_" + "1" * 64
    receipt = _receipt(
        parsed.request,
        call_id,
        responder_fixture.artifact_sha,
        status="authored",
    )
    candidate = _candidate(parsed.request)
    if forgery == "extra_receipt_key":
        receipt["untyped_completion_authority"] = True
    elif forgery == "missing_schema":
        receipt.pop("schema_version")
    else:
        candidate["authorized_source_path"] = "different.py"
    with pytest.raises(
        GovernedPatchResponderError,
        match="production outcome verification requires GovernedPatchRequest",
    ):
        _normalize_outcome(
            AuthorshipOutcome(receipt=receipt, candidate=candidate),
            request=parsed.request,
            call_id=call_id,
            semantic_artifact_sha256=responder_fixture.artifact_sha,
            request_checkpoint=parsed.checkpoint,
        )


def _run(
    fixture: _Fixture,
    *,
    boot_id: str,
    author,
    clock=lambda: 100.0,
    parser=None,
    validator=None,
    recover=None,
    inspector=None,
    hook=None,
    lease_seconds: float = 10.0,
):
    return asyncio.run(
        process_once(
            bridge_db=fixture.bridge_db,
            delivery_record_path=fixture.delivery_path,
            ledger_db=fixture.ledger_db,
            repo_root=fixture.repo,
            event_id=fixture.event_id,
            owner_id="codex_composer",
            boot_id=boot_id,
            validate_semantic_projection=validator or _validator(fixture),
            parse_delivery=parser or _parser(boot_id),
            author_candidate=author,
            recover_candidate=recover,
            inspect_provider_call=inspector,
            verify_authorship_outcome=_test_outcome_verifier,
            lease_seconds=lease_seconds,
            clock=clock,
            checkpoint_hook=hook,
        )
    )


def _bridge_row(fixture: _Fixture) -> tuple[Any, ...]:
    connection = sqlite3.connect(fixture.bridge_db)
    try:
        return connection.execute("SELECT * FROM semantic_jobs").fetchone()
    finally:
        connection.close()


def test_concurrent_claim_calls_provider_exactly_once(
    responder_fixture: _Fixture,
) -> None:
    calls: list[str] = []
    entered = threading.Event()
    release = threading.Event()

    async def slow_author(request, *, semantic_artifact_sha256, provider_call_id):
        calls.append(provider_call_id)
        entered.set()
        assert release.wait(timeout=5)
        return AuthorshipOutcome(
            receipt=_receipt(
                request,
                provider_call_id,
                semantic_artifact_sha256,
                status="authored",
            ),
            candidate=_candidate(request),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            _run,
            responder_fixture,
            boot_id="boot-a",
            author=slow_author,
        )
        assert entered.wait(timeout=5)
        second = pool.submit(
            _run,
            responder_fixture,
            boot_id="boot-b",
            author=slow_author,
        )
        with pytest.raises(LeaseUnavailableError):
            second.result(timeout=5)
        release.set()
        result = first.result(timeout=5)
    assert result.status == CANDIDATE_DURABLE
    assert result.provider_called is True
    assert len(calls) == 1


def test_crash_before_provider_checkpoint_reclaims_expired_lease(
    responder_fixture: _Fixture,
) -> None:
    calls: list[str] = []

    def crash(phase: str, row) -> None:
        del row
        if phase == INPUT_COMMITTED:
            raise RuntimeError("simulated process death")

    with pytest.raises(RuntimeError, match="simulated"):
        _run(
            responder_fixture,
            boot_id="boot-old",
            author=_author(responder_fixture, calls),
            clock=lambda: 100.0,
            hook=crash,
        )
    result = _run(
        responder_fixture,
        boot_id="boot-new",
        author=_author(responder_fixture, calls),
        clock=lambda: 111.0,
    )
    assert result.status == CANDIDATE_DURABLE
    assert result.authored_by_boot_id == "boot-new"
    assert result.authored_in_this_boot is True
    assert len(calls) == 1


def test_restart_after_terminal_reuses_candidate_and_preserves_author_boot(
    responder_fixture: _Fixture,
) -> None:
    calls: list[str] = []
    first = _run(
        responder_fixture,
        boot_id="boot-author",
        author=_author(responder_fixture, calls),
    )
    second = _run(
        responder_fixture,
        boot_id="boot-observer",
        author=_author(responder_fixture, calls),
    )
    assert first.status == second.status == CANDIDATE_DURABLE
    assert second.provider_called is False
    assert second.authored_in_this_boot is False
    assert second.authored_by_boot_id == "boot-author"
    assert second.observed_by_boot_id == "boot-observer"
    assert len(calls) == 1


def test_crash_after_immutable_outcome_recovers_without_second_provider_call(
    responder_fixture: _Fixture,
) -> None:
    calls: list[str] = []
    saved: list[AuthorshipOutcome] = []

    async def author(request, *, semantic_artifact_sha256, provider_call_id):
        calls.append(provider_call_id)
        outcome = AuthorshipOutcome(
            receipt=_receipt(
                request,
                provider_call_id,
                semantic_artifact_sha256,
                status="authored",
            ),
            candidate=_candidate(request),
        )
        saved.append(outcome)
        return outcome

    def crash(phase: str, row) -> None:
        del row
        if phase == "PROVIDER_OUTCOME_READY":
            raise RuntimeError("crash after provider artifact")

    with pytest.raises(RuntimeError, match="provider artifact"):
        _run(
            responder_fixture,
            boot_id="boot-author",
            author=author,
            hook=crash,
        )

    async def recover(request, *, semantic_artifact_sha256, provider_call_id):
        del request, semantic_artifact_sha256, provider_call_id
        return saved[0]

    result = _run(
        responder_fixture,
        boot_id="boot-recovery",
        author=author,
        recover=recover,
        clock=lambda: 111.0,
    )
    assert result.status == CANDIDATE_DURABLE
    assert result.recovered is True
    assert result.provider_called is False
    assert result.authored_by_boot_id == "boot-author"
    assert result.observed_by_boot_id == "boot-recovery"
    assert len(calls) == 1


def test_started_checkpoint_without_provider_claim_safely_enters_provider_once(
    responder_fixture: _Fixture,
) -> None:
    calls: list[str] = []

    def crash(phase: str, row) -> None:
        del row
        if phase == PROVIDER_CALL_STARTED:
            raise RuntimeError("crash before provider invocation")

    with pytest.raises(RuntimeError):
        _run(
            responder_fixture,
            boot_id="boot-author",
            author=_author(responder_fixture, calls),
            hook=crash,
        )

    async def absent(*args, **kwargs):
        del args, kwargs
        return "absent"

    result = _run(
        responder_fixture,
        boot_id="boot-recovery",
        author=_author(responder_fixture, calls),
        inspector=absent,
        clock=lambda: 111.0,
    )
    assert result.status == CANDIDATE_DURABLE
    assert result.provider_called is True
    assert result.authored_by_boot_id == "boot-recovery"
    assert len(calls) == 1


def test_started_call_with_durable_claim_never_recalls_provider(
    responder_fixture: _Fixture,
) -> None:
    calls: list[str] = []

    def crash(phase: str, row) -> None:
        del row
        if phase == PROVIDER_CALL_STARTED:
            raise RuntimeError("crash after provider admission")

    with pytest.raises(RuntimeError):
        _run(
            responder_fixture,
            boot_id="boot-author",
            author=_author(responder_fixture, calls),
            hook=crash,
        )

    async def claimed(*args, **kwargs):
        del args, kwargs
        return "claimed"

    with pytest.raises(ProviderCallUncertainError, match="redrive forbidden"):
        _run(
            responder_fixture,
            boot_id="boot-recovery",
            author=_author(responder_fixture, calls),
            inspector=claimed,
            clock=lambda: 111.0,
        )
    assert calls == []


def test_provider_refusal_is_terminal_and_reused(responder_fixture: _Fixture) -> None:
    calls: list[str] = []
    first = _run(
        responder_fixture,
        boot_id="boot-a",
        author=_author(responder_fixture, calls, refused=True),
    )
    second = _run(
        responder_fixture,
        boot_id="boot-b",
        author=_author(responder_fixture, calls, refused=True),
    )
    assert first.status == second.status == PROVIDER_REFUSED
    assert first.candidate_checkpoint is None
    assert second.provider_called is False
    assert len(calls) == 1


def test_active_input_lease_denies_foreign_boot(responder_fixture: _Fixture) -> None:
    calls: list[str] = []

    def crash(phase: str, row) -> None:
        del row
        if phase == INPUT_COMMITTED:
            raise RuntimeError("pause")

    with pytest.raises(RuntimeError):
        _run(
            responder_fixture,
            boot_id="boot-a",
            author=_author(responder_fixture, calls),
            hook=crash,
        )
    with pytest.raises(LeaseUnavailableError):
        _run(
            responder_fixture,
            boot_id="boot-b",
            author=_author(responder_fixture, calls),
            clock=lambda: 109.0,
        )
    assert calls == []


def test_delivery_or_projection_drift_fails_closed(responder_fixture: _Fixture) -> None:
    calls: list[str] = []
    _run(
        responder_fixture,
        boot_id="boot-a",
        author=_author(responder_fixture, calls),
    )
    with pytest.raises(InputDriftError):
        _run(
            responder_fixture,
            boot_id="boot-b",
            author=_author(responder_fixture, calls),
            validator=_validator(responder_fixture, marker="drifted"),
        )

    delivery = json.loads(responder_fixture.delivery_path.read_text(encoding="utf-8"))
    delivery["consumer"] = "tampered"
    _write_json(responder_fixture.delivery_path, delivery)
    with pytest.raises(InputDriftError):
        _run(
            responder_fixture,
            boot_id="boot-c",
            author=_author(responder_fixture, calls),
        )
    assert len(calls) == 1


def test_canonical_task_snapshot_drift_fails_closed(
    responder_fixture: _Fixture,
) -> None:
    calls: list[str] = []
    _run(
        responder_fixture,
        boot_id="boot-a",
        author=_author(responder_fixture, calls),
    )
    with pytest.raises(InputDriftError):
        _run(
            responder_fixture,
            boot_id="boot-b",
            author=_author(responder_fixture, calls),
            parser=_parser("boot-b", task_snapshot_sha="9" * 64),
        )
    assert len(calls) == 1


def test_terminal_external_evidence_must_match_ledger(
    responder_fixture: _Fixture,
) -> None:
    calls: list[str] = []
    first = _run(
        responder_fixture,
        boot_id="boot-a",
        author=_author(responder_fixture, calls),
    )

    async def conflicting_recovery(
        request,
        *,
        semantic_artifact_sha256,
        provider_call_id,
    ):
        receipt = _receipt(
            request,
            provider_call_id,
            semantic_artifact_sha256,
            status="authored",
        )
        candidate = _candidate(request)
        candidate["candidate_digest"] = f"sha256:{'8' * 64}"
        return AuthorshipOutcome(receipt=receipt, candidate=candidate)

    with pytest.raises(InputDriftError, match="contradicts terminal"):
        _run(
            responder_fixture,
            boot_id="boot-b",
            author=_author(responder_fixture, calls),
            recover=conflicting_recovery,
        )
    assert first.status == CANDIDATE_DURABLE
    assert len(calls) == 1


def test_corrupt_checkpoint_digest_fails_closed(responder_fixture: _Fixture) -> None:
    calls: list[str] = []
    _run(
        responder_fixture,
        boot_id="boot-a",
        author=_author(responder_fixture, calls),
    )
    connection = sqlite3.connect(responder_fixture.ledger_db)
    try:
        connection.execute(
            "UPDATE governed_patch_jobs SET author_boot_id = 'forged-boot'"
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(LedgerCorruptionError):
        _run(
            responder_fixture,
            boot_id="boot-b",
            author=_author(responder_fixture, calls),
        )
    assert len(calls) == 1


def test_bridge_row_is_never_mutated(responder_fixture: _Fixture) -> None:
    before = _bridge_row(responder_fixture)
    calls: list[str] = []
    result = _run(
        responder_fixture,
        boot_id="boot-a",
        author=_author(responder_fixture, calls),
    )
    assert result.repository_effect_authorized is False
    assert result.mission_control_completion_authorized is False
    assert _bridge_row(responder_fixture) == before
    assert before[3] == "PENDING"


def test_bridge_requires_wal_and_canonical_pending_row(
    responder_fixture: _Fixture,
) -> None:
    connection = sqlite3.connect(responder_fixture.bridge_db)
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(BridgeEvidenceError, match="WAL mode"):
        load_bridge_delivery(
            responder_fixture.bridge_db,
            responder_fixture.event_id,
            responder_fixture.delivery_path,
        )


def test_bridge_rejects_recursive_view_before_packet_query(tmp_path: Path) -> None:
    database = tmp_path / "poison.sqlite3"
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            """
            CREATE VIEW semantic_jobs(
                event_id, envelope_sha256, envelope_json,
                status, created_at, updated_at
            ) AS
            WITH RECURSIVE endless(value) AS (
                SELECT 1 UNION ALL SELECT value + 1 FROM endless
            )
            SELECT CAST(value AS TEXT), '', '', 'PENDING', '', '' FROM endless
            """
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(BridgeEvidenceError, match="not one exact SQLite table"):
        load_bridge_delivery(database, "never", tmp_path / "never.json")


def test_unrelated_database_is_unchanged_when_ledger_custody_refuses(
    tmp_path: Path,
) -> None:
    database = tmp_path / "unrelated.sqlite3"
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE precious_data(value TEXT NOT NULL)")
        connection.execute("INSERT INTO precious_data VALUES ('preserve-me')")
        connection.commit()
    finally:
        connection.close()
    database.chmod(0o600)
    before = database.read_bytes()
    repo = tmp_path / "release"
    repo.mkdir()
    with pytest.raises(LedgerCorruptionError, match="custody marker"):
        _ledger_connection(database, repo_root=repo)
    assert database.read_bytes() == before
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall() == [("precious_data",)]
    finally:
        connection.close()


def test_intent_has_no_cryptographic_delivery_self_reference(
    responder_fixture: _Fixture,
) -> None:
    delivery = load_bridge_delivery(
        responder_fixture.bridge_db,
        responder_fixture.event_id,
        responder_fixture.delivery_path,
    )
    intent = json.loads(delivery.content)
    assert set(intent) == {
        "schema_version",
        "mission_id",
        "task_id",
        "proposal_id",
        "base_sha",
        "authorized_source_path",
        "oracle_argv",
        "semantic_intent",
    }
    assert "delivery_id" not in delivery.content
    assert "lease_id" not in delivery.content
    assert "executor_process_boot_id" not in delivery.content


def test_default_parser_constructs_v2_request_from_observed_delivery(
    responder_fixture: _Fixture,
) -> None:
    subprocess.run(["git", "init", "-q"], cwd=responder_fixture.repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=responder_fixture.repo,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Responder Test"],
        cwd=responder_fixture.repo,
        check=True,
    )
    subprocess.run(["git", "add", "target.py"], cwd=responder_fixture.repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture"],
        cwd=responder_fixture.repo,
        check=True,
    )
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=responder_fixture.repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    delivery_payload = json.loads(
        responder_fixture.delivery_path.read_text(encoding="utf-8")
    )
    envelope = delivery_payload["envelope"]
    intent = json.loads(envelope["content"])
    intent["base_sha"] = base_sha
    envelope["content"] = json.dumps(
        intent,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    envelope["sha256"] = _sha(envelope["content"])
    envelope_json = json.dumps(envelope, ensure_ascii=True, sort_keys=True)
    delivery_payload["envelope_sha256"] = _sha(envelope_json)
    _write_json(responder_fixture.delivery_path, delivery_payload)
    connection = sqlite3.connect(responder_fixture.bridge_db)
    try:
        connection.execute(
            "UPDATE semantic_jobs SET envelope_sha256 = ?, envelope_json = ?",
            (delivery_payload["envelope_sha256"], envelope_json),
        )
        connection.commit()
    finally:
        connection.close()
    delivery = load_bridge_delivery(
        responder_fixture.bridge_db,
        responder_fixture.event_id,
        responder_fixture.delivery_path,
    )

    task_db = responder_fixture.root / "tasks.sqlite3"
    connection = sqlite3.connect(task_db)
    try:
        connection.executescript(
            """
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY, title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL,
                priority TEXT NOT NULL, assigned_to TEXT, created_by TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                result TEXT, metadata TEXT NOT NULL, trace_id TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE task_dependencies (
                task_id TEXT NOT NULL, depends_on_id TEXT NOT NULL,
                PRIMARY KEY (task_id, depends_on_id)
            );
            """
        )
        metadata = {
            "schema_version": "dharma.mission_control.v1",
            "mission_id": "mission-1",
            "mission_task_creation_hash": "7" * 64,
            "completion_contract": "governed_patch_effect_v1",
            "a2a_binding": {
                "schema_version": "dharma.mission_control.a2a_binding.v1",
                "agent_uid": "codex_composer",
                "packet_id": delivery.packet_id,
                "correlation_id": (
                    f"a2a_send:codex_composer:{delivery.packet_id}"
                ),
                "delivery_id": delivery.delivery_id,
                "proposal_id": "proposal-1",
                "content_sha256": delivery.content_sha256,
            },
        }
        connection.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "task-1",
                "Patch target",
                "Change the bounded constant",
                "pending",
                "normal",
                None,
                "operator",
                "2026-08-28T00:00:00+00:00",
                "2026-08-28T00:00:00+00:00",
                None,
                json.dumps(metadata),
                "",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    native_ref = SimpleNamespace(
        mission_id="mission-1",
        task_id="task-1",
        packet_id=delivery.packet_id,
        delivery_id=delivery.delivery_id,
        correlation_id=f"a2a_send:codex_composer:{delivery.packet_id}",
        proposal_id="proposal-1",
        agent_uid="codex_composer",
        content_sha256=delivery.content_sha256,
    )
    semantic = SemanticProjection(
        semantic_artifact_sha256=responder_fixture.artifact_sha,
        checkpoint={"artifact_sha256": responder_fixture.artifact_sha},
        native=SimpleNamespace(native_ref=native_ref),
    )
    parser = _build_default_request_parser(
        repo_root=responder_fixture.repo,
        task_db=task_db,
        owner_id="codex_composer",
        executor_run_id="run-live",
        boot_id="boot-live",
    )
    parsed = asyncio.run(parser(delivery, semantic, None))
    request = parsed.request
    assert request.bindings.delivery_id == delivery.delivery_id
    assert request.bindings.executor_process_boot_id == "boot-live"
    assert request.semantic_intent == "Change VALUE from one to two."
    assert request.task_snapshot_sha256 == parsed.checkpoint["task_snapshot_sha256"]
    assert request.request_bytes != delivery.content.encode("utf-8")

    connection = sqlite3.connect(task_db)
    try:
        rebound = dict(metadata)
        rebound["a2a_binding"] = dict(metadata["a2a_binding"])
        rebound["a2a_binding"]["packet_id"] = "packet-rebound"
        connection.execute(
            "UPDATE tasks SET metadata = ? WHERE id = ?",
            (json.dumps(rebound), native_ref.task_id),
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(GovernedPatchResponderError, match="A2A binding changed"):
        asyncio.run(parser(delivery, semantic, None))

    connection = sqlite3.connect(task_db)
    try:
        connection.execute(
            "UPDATE tasks SET status = 'completed', result = 'stale', metadata = ? "
            "WHERE id = ?",
            (json.dumps(metadata), native_ref.task_id),
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(GovernedPatchResponderError, match="not pending"):
        asyncio.run(parser(delivery, semantic, None))


def test_git_head_ignores_ambient_repo_redirection_and_requires_clean_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    heads: list[str] = []
    repos: list[Path] = []
    for index in range(2):
        repo = tmp_path / f"repo-{index}"
        repo.mkdir()
        (repo / "tracked.txt").write_text(f"repo {index}\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "user.email=test@example.invalid", "-c", "user.name=Test", "add", "tracked.txt"],
            cwd=repo,
            check=True,
        )
        subprocess.run(
            ["git", "-c", "user.email=test@example.invalid", "-c", "user.name=Test", "commit", "-q", "-m", "fixture"],
            cwd=repo,
            check=True,
        )
        repos.append(repo)
        heads.append(
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    assert heads[0] != heads[1]

    git_environment = os.environ.copy()
    git_environment.pop("GIT_DIR", None)
    git_environment.pop("GIT_WORK_TREE", None)
    git_environment.pop("GIT_NO_REPLACE_OBJECTS", None)
    monkeypatch.setenv("GIT_DIR", str(repos[1] / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(repos[1]))
    assert _git_head(repos[0]) == heads[0]
    assert _git_blob_at_head(repos[0], heads[0], "tracked.txt") == b"repo 0\n"
    original_blob = subprocess.run(
        ["git", "rev-parse", f"{heads[0]}:tracked.txt"],
        cwd=repos[0],
        check=True,
        capture_output=True,
        text=True,
        env=git_environment,
    ).stdout.strip()
    replacement_blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=repos[0],
        check=True,
        input="replacement object\n",
        capture_output=True,
        text=True,
        env=git_environment,
    ).stdout.strip()
    subprocess.run(
        ["git", "replace", original_blob, replacement_blob],
        cwd=repos[0],
        check=True,
        env=git_environment,
    )
    assert subprocess.run(
        ["git", "cat-file", "blob", f"{heads[0]}:tracked.txt"],
        cwd=repos[0],
        check=True,
        capture_output=True,
        env=git_environment,
    ).stdout == b"replacement object\n"
    assert _git_blob_at_head(repos[0], heads[0], "tracked.txt") == b"repo 0\n"
    (repos[0] / "tracked.txt").write_text("sandwich drift\n", encoding="utf-8")
    assert _git_blob_at_head(repos[0], heads[0], "tracked.txt") == b"repo 0\n"
    (repos[0] / "tracked.txt").write_text("repo 0\n", encoding="utf-8")

    (repos[0] / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(GovernedPatchResponderError, match="must be clean"):
        _git_head(repos[0])


def test_custody_requires_the_projection_owned_bridge_database(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "release"
    repo.mkdir()
    semantic_jobs = tmp_path / "a2a" / "semantic_jobs"
    semantic_jobs.mkdir(parents=True)
    canonical = semantic_jobs / "codex_composer.sqlite3"
    canonical.write_bytes(b"canonical bridge placeholder")
    copied_root = tmp_path / "copied"
    copied_root.mkdir()
    copied = copied_root / canonical.name
    copied.write_bytes(canonical.read_bytes())

    with pytest.raises(GovernedPatchResponderError, match="not the canonical"):
        _canonical_custody_paths(
            bridge_db=copied,
            semantic_job_root=semantic_jobs,
            repo_root=repo,
            owner_id="codex_composer",
        )
    assert not (copied_root / "governed_patch_custody").exists()

    ledger, evidence = _canonical_custody_paths(
        bridge_db=canonical,
        semantic_job_root=semantic_jobs,
        repo_root=repo,
        owner_id="codex_composer",
    )
    assert ledger == (
        semantic_jobs
        / "governed_patch_custody"
        / "codex_composer"
        / "responder.sqlite3"
    )
    assert evidence == ledger.parent / "evidence"


def _semantic_receipt(
    *, verdict: str = "approve", intent_ack: bool = True, understood: bool = True
) -> dict[str, Any]:
    from dharma_swarm.operator_core.semantic_receipt import (
        validate_semantic_receipt,
    )

    return validate_semantic_receipt(
        {
            "schema_version": "dharma.semantic_receipt.v1",
            "receipt_id": "semantic-1",
            "created_at": "2026-08-28T00:00:00Z",
            "agent_uid": "codex_composer",
            "critic_agent_id": "critic-1",
            "model_identity": {"provider": "ollama", "model": "glm-5.2"},
            "authored_by_model": True,
            "review_target": "a2a:packet-1",
            "intent_ack": intent_ack,
            "capability_match": 1.0,
            "understood_request": understood,
            "missing_context": [],
            "verdict": verdict,
            "summary": "Bounded semantic review.",
            "recommendations": [],
            "acceptance_gates": [],
            "explicit_disagreement": (
                "The requested patch should not advance."
                if verdict not in {"pass", "approve"}
                else ""
            ),
            "evidence_refs": ["delivery"],
            "confidence": 0.95,
            "not_claimed_agents": ["other-agents"],
            "failure_type": "",
            "failure_reason": "",
            "correlation_id": "packet-1",
            "reply_to": "reply.packet-1",
            "model_call_latency_ms": 10,
        }
    )


@pytest.mark.parametrize(
    ("verdict", "intent_ack", "understood"),
    (
        ("reject", True, True),
        ("revise", True, True),
        ("approve", False, True),
        ("approve", True, False),
    ),
)
def test_semantic_execution_without_approval_cannot_author(
    tmp_path: Path,
    verdict: str,
    intent_ack: bool,
    understood: bool,
) -> None:
    outbox = tmp_path / "outbox"
    receipts = tmp_path / "receipts"
    semantic_path = receipts / "semantic.json"
    _write_json(
        semantic_path,
        _semantic_receipt(
            verdict=verdict,
            intent_ack=intent_ack,
            understood=understood,
        ),
    )
    artifact = {
        "schema_version": "dharma.a2a.domain_reply_artifact.v1",
        "semantic_receipt_path": str(semantic_path),
    }
    artifact_path = outbox / "codex_composer" / "packet-1-domain-reply.json"
    _write_json(artifact_path, artifact)
    with pytest.raises(GovernedPatchResponderError, match="does not carry"):
        _semantic_approval_checkpoint(
            outbox_root=outbox,
            trusted_receipt_roots=(receipts,),
            agent_uid="codex_composer",
            packet_id="packet-1",
            expected_artifact_sha256=_sha(artifact_path.read_bytes()),
        )


def test_passing_semantic_approval_is_content_addressed(tmp_path: Path) -> None:
    outbox = tmp_path / "outbox"
    receipts = tmp_path / "receipts"
    semantic_path = receipts / "semantic.json"
    _write_json(semantic_path, _semantic_receipt())
    artifact_path = outbox / "codex_composer" / "packet-1-domain-reply.json"
    _write_json(
        artifact_path,
        {
            "schema_version": "dharma.a2a.domain_reply_artifact.v1",
            "semantic_receipt_path": str(semantic_path),
        },
    )
    checkpoint = _semantic_approval_checkpoint(
        outbox_root=outbox,
        trusted_receipt_roots=(receipts,),
        agent_uid="codex_composer",
        packet_id="packet-1",
        expected_artifact_sha256=_sha(artifact_path.read_bytes()),
    )
    assert checkpoint["verdict"] == "approve"
    assert checkpoint["semantic_receipt_sha256"] == _sha(
        semantic_path.read_bytes()
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("lease_seconds", 0.0),
        ("provider_timeout", float("inf")),
        ("provider_timeout", float("nan")),
        ("interval_seconds", -1.0),
    ),
)
def test_cli_rejects_unbounded_timing_before_custody_mutation(
    tmp_path: Path, field: str, value: float
) -> None:
    values = {
        "mode": "once",
        "packet_id": "packet-1",
        "delivery_record": "delivery.json",
        "lease_seconds": 10.0,
        "provider_timeout": 10.0,
        "interval_seconds": 1.0,
    }
    values[field] = value
    with pytest.raises(GovernedPatchResponderError, match="positive and finite"):
        asyncio.run(_main_async(SimpleNamespace(**values)))
    assert list(tmp_path.iterdir()) == []
