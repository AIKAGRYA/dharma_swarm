from __future__ import annotations

import ast
import base64
import json
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import dharma_swarm._mission_control_operator_control_fs as control_fs
import dharma_swarm.mission_control_operator_control as control_module
from dharma_swarm.mission_control_operator_control import (
    ApplicationStatus,
    AuthorityApplication,
    CONTROL_SCHEMA,
    ControlAuthenticationError,
    ControlAction,
    ControlConfigurationError,
    ControlExpiredError,
    ControlFutureRequestError,
    ControlIdempotencyConflict,
    ControlInboxPublisher,
    ControlSchemaError,
    InboxKind,
    InboxUnavailable,
    OPERATOR_CONTROL_SEMANTICS_SHA256,
    OPERATOR_CONTROL_AUTHORITY_BINDING_SHA256,
    OPERATOR_CONTROL_HTTP_BINDING_SHA256,
    OperatorControlEnvelope,
    OperatorControlError,
    OperatorControlInboxReconciler,
    OperatorControlRequest,
    ReconcileStatus,
    SupervisorControlCallbacks,
    UnsafeInboxEntry,
    control_filename,
    decode_and_verify_envelope,
    read_control_candidate,
    terminal_filename,
)

NOW = datetime(2026, 8, 23, 0, 0, 30, tzinfo=timezone.utc)
SECRET = b"operator-control-test-hmac-key-32-bytes-minimum"
LOGIN = "operator@example.com"


def test_public_module_preserves_filesystem_exception_identity() -> None:
    for name in (
        "ControlConfigurationError",
        "ControlSchemaError",
        "ControlIdempotencyConflict",
        "UnsafeInboxEntry",
    ):
        assert getattr(control_module, name) is getattr(control_fs, name)
    assert callable(control_module.decode_and_verify_envelope)
    assert callable(control_module.OperatorControlInboxReconciler)


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _request(
    action: str = "pause",
    *,
    request_id: str = "request-001",
    idempotency_key: str = "idempotency-001",
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    reason: str = "Operator requested a bounded control change",
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    issued = issued_at or NOW - timedelta(seconds=5)
    expires = expires_at or NOW + timedelta(seconds=55)
    value: dict[str, object] = {
        "action": action,
        "request_id": request_id,
        "idempotency_key": idempotency_key,
        "issued_at": _timestamp(issued),
        "expires_at": _timestamp(expires),
        "reason": reason,
    }
    if extra:
        value.update(extra)
    return value


@pytest.fixture
def inboxes(tmp_path: Path) -> tuple[Path, Path]:
    normal = tmp_path / "control" / "normal"
    emergency = tmp_path / "control" / "emergency"
    normal.mkdir(parents=True)
    emergency.mkdir()
    return normal, emergency


def test_exact_request_and_envelope_are_canonical_and_authenticated() -> None:
    request = OperatorControlRequest.from_mapping(_request())
    envelope = OperatorControlEnvelope.sign(
        request,
        operator_login=LOGIN,
        secret=SECRET,
        now=NOW,
    )

    raw = envelope.canonical_bytes()
    assert raw == (
        b'{"hmac_sha256":"'
        + envelope.hmac_sha256.encode()
        + b'","operator_login":"operator@example.com","request":'
        + b'{"action":"pause","expires_at":"2026-08-23T00:01:25.000Z",'
        + b'"idempotency_key":"idempotency-001",'
        + b'"issued_at":"2026-08-23T00:00:25.000Z",'
        + b'"reason":"Operator requested a bounded control change",'
        + b'"request_id":"request-001"},'
        + b'"schema":"dharma.sadhana.operator_control.v1"}'
    )
    verified = decode_and_verify_envelope(raw, secret=SECRET, now=NOW)
    assert verified == envelope
    assert verified.schema == CONTROL_SCHEMA


@pytest.mark.parametrize(
    "mutation",
    [
        {"extra": True},
        {"reason": ""},
        {"reason": " leading-space"},
        {"request_id": "unsafe request id"},
        {"issued_at": "2026-08-23 00:00:25Z"},
    ],
)
def test_request_rejects_extra_fields_and_malformed_values(
    mutation: dict[str, object],
) -> None:
    payload = _request()
    payload.update(mutation)
    with pytest.raises(ControlSchemaError):
        OperatorControlRequest.from_mapping(payload)


def test_request_rejects_unknown_and_decision_actions() -> None:
    for action in ("restart", "approve", "reject"):
        with pytest.raises(ControlSchemaError, match="operational action"):
            OperatorControlRequest.from_mapping(_request(action))


def test_noncanonical_bytes_duplicate_keys_and_bad_hmac_fail_closed() -> None:
    request = OperatorControlRequest.from_mapping(_request())
    envelope = OperatorControlEnvelope.sign(
        request, operator_login=LOGIN, secret=SECRET, now=NOW
    )
    pretty = json.dumps(envelope.as_dict(), indent=2).encode()
    with pytest.raises(ControlSchemaError, match="not canonical"):
        decode_and_verify_envelope(pretty, secret=SECRET, now=NOW)

    duplicate = envelope.canonical_bytes().replace(
        b'{"hmac_sha256":', b'{"schema":"duplicate","hmac_sha256":', 1
    )
    with pytest.raises(ControlSchemaError, match="duplicate key"):
        decode_and_verify_envelope(duplicate, secret=SECRET, now=NOW)

    tampered = json.loads(envelope.canonical_bytes())
    tampered["request"]["reason"] = "Tampered after signing"
    tampered_raw = json.dumps(tampered, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ControlAuthenticationError, match="verification"):
        decode_and_verify_envelope(tampered_raw, secret=SECRET, now=NOW)


def test_expiry_future_skew_and_max_ttl_are_enforced() -> None:
    expired = OperatorControlRequest.from_mapping(
        _request(
            issued_at=NOW - timedelta(seconds=60),
            expires_at=NOW,
        )
    )
    with pytest.raises(ControlExpiredError):
        OperatorControlEnvelope.sign(
            expired, operator_login=LOGIN, secret=SECRET, now=NOW
        )

    future = OperatorControlRequest.from_mapping(
        _request(
            issued_at=NOW + timedelta(seconds=16),
            expires_at=NOW + timedelta(seconds=30),
        )
    )
    with pytest.raises(ControlFutureRequestError):
        OperatorControlEnvelope.sign(
            future, operator_login=LOGIN, secret=SECRET, now=NOW
        )

    with pytest.raises(ControlSchemaError, match="120 seconds"):
        OperatorControlRequest.from_mapping(
            _request(
                issued_at=NOW,
                expires_at=NOW + timedelta(seconds=121),
            )
        )


def test_hmac_secret_line_break_is_a_visible_configuration_fault() -> None:
    request = OperatorControlRequest.from_mapping(_request())
    with pytest.raises(ControlConfigurationError, match="without CR/LF"):
        OperatorControlEnvelope.sign(
            request,
            operator_login=LOGIN,
            secret=b"x" * 32 + b"\n",
            now=NOW,
        )


def test_atomic_publish_routes_normal_and_emergency_with_mode_0640(
    inboxes: tuple[Path, Path],
) -> None:
    normal, emergency = inboxes
    publisher = ControlInboxPublisher(normal, emergency)
    pause = OperatorControlRequest.from_mapping(_request())
    stop = OperatorControlRequest.from_mapping(
        _request(
            "emergency_stop",
            request_id="request-stop",
            idempotency_key="idempotency-stop",
            reason="Immediate operator stop",
        )
    )

    normal_result = publisher.publish(
        pause, operator_login=LOGIN, secret=SECRET, now=NOW
    )
    stop_result = publisher.publish(stop, operator_login=LOGIN, secret=SECRET, now=NOW)

    assert normal_result.inbox is InboxKind.NORMAL
    assert stop_result.inbox is InboxKind.EMERGENCY
    assert normal_result.path.parent == normal
    assert stop_result.path.parent == emergency
    assert normal_result.path.name == control_filename(pause.idempotency_key)
    assert normal_result.applied is False
    assert normal_result.effect_executed is False
    for path in (normal_result.path, stop_result.path):
        identity = path.stat()
        assert stat.S_IMODE(identity.st_mode) == 0o640
        assert identity.st_nlink == 1
        assert not path.read_bytes().endswith(b"\n")


def test_exact_replay_does_not_rewrite_and_conflict_is_rejected(
    inboxes: tuple[Path, Path],
) -> None:
    normal, emergency = inboxes
    publisher = ControlInboxPublisher(normal, emergency)
    request = OperatorControlRequest.from_mapping(_request())
    first = publisher.publish(request, operator_login=LOGIN, secret=SECRET, now=NOW)
    before = first.path.stat()
    replay = publisher.publish(request, operator_login=LOGIN, secret=SECRET, now=NOW)
    after = first.path.stat()
    assert first.replayed is False
    assert replay.replayed is True
    assert before.st_ino == after.st_ino
    assert before.st_mtime_ns == after.st_mtime_ns

    conflict = OperatorControlRequest.from_mapping(
        _request(reason="Different request under the same idempotency key")
    )
    with pytest.raises(ControlIdempotencyConflict):
        publisher.publish(conflict, operator_login=LOGIN, secret=SECRET, now=NOW)


def test_concurrent_replay_creates_one_candidate(inboxes: tuple[Path, Path]) -> None:
    normal, emergency = inboxes
    publisher = ControlInboxPublisher(normal, emergency)
    request = OperatorControlRequest.from_mapping(_request())

    def publish() -> bool:
        return publisher.publish(
            request, operator_login=LOGIN, secret=SECRET, now=NOW
        ).replayed

    with ThreadPoolExecutor(max_workers=8) as pool:
        replayed = list(pool.map(lambda _: publish(), range(8)))

    assert replayed.count(False) == 1
    assert replayed.count(True) == 7
    assert [
        path.name for path in normal.iterdir() if not path.name.startswith(".")
    ] == [control_filename(request.idempotency_key)]


def test_publish_crash_after_noreplace_rename_recovers_as_single_link_replay(
    inboxes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    normal, emergency = inboxes
    publisher = ControlInboxPublisher(normal, emergency)
    request = OperatorControlRequest.from_mapping(_request())
    original_rename = control_fs.rename_noreplace
    crashed = False

    def rename_then_crash(*args):
        nonlocal crashed
        original_rename(*args)
        if not crashed:
            crashed = True
            raise RuntimeError("crash after no-replace publish")

    monkeypatch.setattr(control_fs, "rename_noreplace", rename_then_crash)
    with pytest.raises(RuntimeError, match="crash after no-replace publish"):
        publisher.publish(request, operator_login=LOGIN, secret=SECRET, now=NOW)

    candidate = normal / control_filename(request.idempotency_key)
    assert candidate.is_file()
    assert candidate.stat().st_nlink == 1
    assert not list(normal.glob(".*.part"))
    replay = publisher.publish(request, operator_login=LOGIN, secret=SECRET, now=NOW)
    assert replay.replayed is True
    assert candidate.stat().st_nlink == 1


def test_custody_race_cannot_overwrite_new_destination(
    inboxes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    normal, emergency, inflight, _, _ = _normal_custody(inboxes)
    request = OperatorControlRequest.from_mapping(_request())
    publication = ControlInboxPublisher(normal, emergency).publish(
        request, operator_login=LOGIN, secret=SECRET, now=NOW
    )
    collision = inflight / publication.path.name
    collision_bytes = b"race-created-different-candidate"
    original_rename = control_fs.rename_noreplace
    injected = False

    def inject_destination_then_rename(*args):
        nonlocal injected
        if not injected:
            injected = True
            collision.write_bytes(collision_bytes)
            collision.chmod(0o640)
        return original_rename(*args)

    monkeypatch.setattr(control_fs, "rename_noreplace", inject_destination_then_rename)
    with pytest.raises(ControlIdempotencyConflict, match="different canonical bytes"):
        control_module._atomic_move_regular(publication.path, inflight)
    assert publication.path.is_file()
    assert collision.read_bytes() == collision_bytes


@pytest.mark.parametrize("flag", ["O_NOFOLLOW", "O_DIRECTORY"])
def test_filesystem_custody_requires_nofollow_and_directory_flags(
    inboxes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, flag: str
) -> None:
    normal, emergency = inboxes
    request = OperatorControlRequest.from_mapping(_request())
    monkeypatch.delattr(control_fs.os, flag)
    with pytest.raises(ControlConfigurationError, match=flag):
        ControlInboxPublisher(normal, emergency).publish(
            request, operator_login=LOGIN, secret=SECRET, now=NOW
        )


def test_replay_cleanup_substitution_cannot_replace_authority_candidate(
    inboxes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    normal, emergency, inflight, _, _ = _normal_custody(inboxes)
    request = OperatorControlRequest.from_mapping(_request())
    publication = ControlInboxPublisher(normal, emergency).publish(
        request, operator_login=LOGIN, secret=SECRET, now=NOW
    )
    canonical = publication.path.read_bytes()
    destination = inflight / publication.path.name
    destination.write_bytes(canonical)
    destination.chmod(0o640)
    hostile = b"substituted-after-replay-comparison"
    original_rename = control_fs.rename_noreplace
    calls = 0

    def substitute_before_private_claim(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            publication.path.unlink()
            publication.path.write_bytes(hostile)
            publication.path.chmod(0o640)
        return original_rename(*args)

    monkeypatch.setattr(control_fs, "rename_noreplace", substitute_before_private_claim)
    with pytest.raises(UnsafeInboxEntry, match="private replay cleanup"):
        control_module._atomic_move_regular(publication.path, inflight)
    assert destination.read_bytes() == canonical
    assert not publication.path.exists()
    quarantined = list(inflight.glob(f".replay.{publication.path.name}.*"))
    assert len(quarantined) == 1
    assert quarantined[0].read_bytes() == hostile


def test_candidate_reader_rejects_same_size_metadata_mutation(
    inboxes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    normal, emergency = inboxes
    request = OperatorControlRequest.from_mapping(_request())
    publication = ControlInboxPublisher(normal, emergency).publish(
        request, operator_login=LOGIN, secret=SECRET, now=NOW
    )
    directory_descriptor = os.open(normal, os.O_RDONLY | os.O_DIRECTORY)
    original_fstat = control_fs.os.fstat
    calls = 0

    def changing_fstat(descriptor: int):
        nonlocal calls
        identity = original_fstat(descriptor)
        calls += 1
        if calls == 1:
            return identity
        values = {
            field: getattr(identity, field)
            for field in (
                "st_dev",
                "st_ino",
                "st_mode",
                "st_nlink",
                "st_size",
                "st_mtime_ns",
                "st_ctime_ns",
            )
        }
        values["st_ctime_ns"] += 1
        return SimpleNamespace(**values)

    monkeypatch.setattr(control_fs.os, "fstat", changing_fstat)
    try:
        with pytest.raises(UnsafeInboxEntry, match="changed while being read"):
            control_fs.read_regular_entry(directory_descriptor, publication.path.name)
    finally:
        os.close(directory_descriptor)


def test_symlink_inbox_and_symlink_candidate_are_rejected(
    tmp_path: Path, inboxes: tuple[Path, Path]
) -> None:
    normal, emergency = inboxes
    publisher = ControlInboxPublisher(normal, emergency)
    request = OperatorControlRequest.from_mapping(_request())
    linked_inbox = tmp_path / "linked-normal"
    linked_inbox.symlink_to(normal, target_is_directory=True)
    with pytest.raises((UnsafeInboxEntry, InboxUnavailable)):
        ControlInboxPublisher(linked_inbox, emergency).publish(
            request, operator_login=LOGIN, secret=SECRET, now=NOW
        )

    candidate = normal / control_filename(request.idempotency_key)
    candidate.symlink_to(tmp_path / "foreign")
    with pytest.raises(UnsafeInboxEntry):
        publisher.publish(request, operator_login=LOGIN, secret=SECRET, now=NOW)


def test_hardlink_candidate_is_rejected(
    tmp_path: Path, inboxes: tuple[Path, Path]
) -> None:
    normal, emergency = inboxes
    request = OperatorControlRequest.from_mapping(_request())
    foreign = tmp_path / "foreign"
    foreign.write_bytes(b"foreign")
    foreign.chmod(0o640)
    os.link(foreign, normal / control_filename(request.idempotency_key))

    with pytest.raises(UnsafeInboxEntry, match="single-link"):
        ControlInboxPublisher(normal, emergency).publish(
            request, operator_login=LOGIN, secret=SECRET, now=NOW
        )


def test_reader_rejects_noncanonical_bytes_and_wrong_filename(
    inboxes: tuple[Path, Path],
) -> None:
    normal, _ = inboxes
    request = OperatorControlRequest.from_mapping(_request())
    envelope = OperatorControlEnvelope.sign(
        request, operator_login=LOGIN, secret=SECRET, now=NOW
    )
    path = normal / control_filename(request.idempotency_key)
    path.write_bytes(json.dumps(envelope.as_dict(), indent=2).encode())
    path.chmod(0o640)
    with pytest.raises(ControlSchemaError, match="not canonical"):
        read_control_candidate(path, secret=SECRET, now=NOW)

    path.unlink()
    wrong = normal / ("0" * 64 + ".control.json")
    wrong.write_bytes(envelope.canonical_bytes())
    wrong.chmod(0o640)
    with pytest.raises(ControlIdempotencyConflict, match="filename"):
        read_control_candidate(wrong, secret=SECRET, now=NOW)


def _normal_custody(
    inboxes: tuple[Path, Path],
) -> tuple[Path, Path, Path, Path, Path]:
    normal, emergency = inboxes
    inflight = normal.parent / "inflight"
    applied = normal.parent / "applied"
    rejected = normal.parent / "rejected"
    inflight.mkdir()
    applied.mkdir()
    rejected.mkdir()
    return normal, emergency, inflight, applied, rejected


def _authority_application(
    request: OperatorControlRequest,
    envelope_sha256: str,
    *,
    status: ApplicationStatus = ApplicationStatus.APPLIED,
) -> AuthorityApplication:
    return AuthorityApplication(
        request_id=request.request_id,
        idempotency_key=request.idempotency_key,
        envelope_sha256=envelope_sha256,
        status=status,
        authority_receipt_ref=f"campaign-control:{request.action.value}:{request.request_id}",
        authority_receipt_sha256="sha256:" + "a" * 64,
        effect_observed=False,
    )


def test_authority_application_bounds_receipt_ref_and_effect_claim() -> None:
    request = OperatorControlRequest.from_mapping(_request())
    with pytest.raises(ValueError, match="canonical bounds"):
        AuthorityApplication(
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            envelope_sha256="sha256:" + "b" * 64,
            status=ApplicationStatus.APPLIED,
            authority_receipt_ref="x" * 513,
            authority_receipt_sha256="sha256:" + "a" * 64,
        )
    with pytest.raises(ValueError, match="observed effect"):
        AuthorityApplication(
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            envelope_sha256="sha256:" + "b" * 64,
            status=ApplicationStatus.APPLIED,
            authority_receipt_ref="campaign-control:receipt",
            authority_receipt_sha256="sha256:" + "a" * 64,
            effect_observed=True,
        )


async def test_reconciler_separates_inbox_ack_from_applied_authority(
    inboxes: tuple[Path, Path],
) -> None:
    normal, emergency, inflight, applied, rejected = _normal_custody(inboxes)
    request = OperatorControlRequest.from_mapping(_request())
    publication = ControlInboxPublisher(normal, emergency).publish(
        request, operator_login=LOGIN, secret=SECRET, now=NOW
    )
    applications = []

    async def apply(control, login, envelope_sha256):
        assert login == LOGIN
        assert not publication.path.exists()
        assert (inflight / publication.path.name).is_file()
        assert not (applied / publication.path.name).exists()
        applications.append((control, envelope_sha256))
        return _authority_application(control, envelope_sha256)

    reconciler = OperatorControlInboxReconciler(
        normal_inbox=normal,
        inflight_inbox=inflight,
        applied_inbox=applied,
        rejected_inbox=rejected,
        secret=SECRET,
    )

    [result] = await reconciler.reconcile_once(
        SupervisorControlCallbacks(apply=apply), now=NOW
    )
    assert result.status is ReconcileStatus.APPLIED
    assert result.inbox_acknowledged is True
    assert result.applied is True
    assert result.effect_observed is False
    assert len(applications) == 1
    assert not list(normal.glob("*.control.json"))
    assert not list(inflight.glob("*.control.json"))
    assert (applied / publication.path.name).is_file()
    terminal = json.loads(
        (
            applied / publication.path.name.replace(".control.json", ".terminal.json")
        ).read_text()
    )
    assert terminal["status"] == "applied"
    assert terminal["authority_applied"] is True
    assert terminal["effect_observed"] is False
    assert terminal["envelope_sha256"].startswith("sha256:")
    assert terminal[
        "control_semantics_sha256"
    ] == OPERATOR_CONTROL_SEMANTICS_SHA256.removeprefix("sha256:")
    assert terminal["control_http_binding_sha256"] == (
        OPERATOR_CONTROL_HTTP_BINDING_SHA256.removeprefix("sha256:")
    )
    assert terminal["control_authority_binding_sha256"] == (
        OPERATOR_CONTROL_AUTHORITY_BINDING_SHA256.removeprefix("sha256:")
    )


async def test_inbox_ack_does_not_become_applied_when_authority_callback_fails(
    inboxes: tuple[Path, Path],
) -> None:
    normal, emergency, inflight, applied, rejected = _normal_custody(inboxes)
    request = OperatorControlRequest.from_mapping(_request())
    publication = ControlInboxPublisher(normal, emergency).publish(
        request, operator_login=LOGIN, secret=SECRET, now=NOW
    )

    async def fail_apply(*_):
        raise RuntimeError("authority owner unavailable")

    reconciler = OperatorControlInboxReconciler(
        normal_inbox=normal,
        inflight_inbox=inflight,
        applied_inbox=applied,
        rejected_inbox=rejected,
        secret=SECRET,
    )

    [result] = await reconciler.reconcile_once(
        SupervisorControlCallbacks(apply=fail_apply), now=NOW
    )
    assert result.status is ReconcileStatus.DEFERRED
    assert result.inbox_acknowledged is True
    assert result.applied is False
    assert result.effect_observed is False
    assert result.error_code == "authority_callback_failed"
    assert (inflight / publication.path.name).is_file()
    assert not list(applied.iterdir())
    assert not list(rejected.iterdir())


async def test_deferred_authority_result_retains_inflight_for_bounded_replay(
    inboxes: tuple[Path, Path],
) -> None:
    normal, emergency, inflight, applied, rejected = _normal_custody(inboxes)
    request = OperatorControlRequest.from_mapping(_request())
    publication = ControlInboxPublisher(normal, emergency).publish(
        request, operator_login=LOGIN, secret=SECRET, now=NOW
    )

    async def defer(control, _login, digest):
        return _authority_application(
            control, digest, status=ApplicationStatus.DEFERRED
        )

    reconciler = OperatorControlInboxReconciler(
        normal_inbox=normal,
        inflight_inbox=inflight,
        applied_inbox=applied,
        rejected_inbox=rejected,
        secret=SECRET,
    )
    [result] = await reconciler.reconcile_once(
        SupervisorControlCallbacks(apply=defer), now=NOW
    )
    assert result.status is ReconcileStatus.DEFERRED
    assert (inflight / publication.path.name).is_file()
    assert not list(applied.iterdir())
    assert not list(rejected.iterdir())


async def test_crash_after_owner_apply_replays_through_authority_cas(
    inboxes: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    normal, emergency, inflight, applied, rejected = _normal_custody(inboxes)
    request = OperatorControlRequest.from_mapping(_request())
    publication = ControlInboxPublisher(normal, emergency).publish(
        request, operator_login=LOGIN, secret=SECRET, now=NOW
    )
    durable = {}
    callback_calls = 0
    mutations = 0

    async def apply(control, _login, digest):
        nonlocal callback_calls, mutations
        callback_calls += 1
        existing = durable.get(control.idempotency_key)
        if existing is not None:
            return existing
        mutations += 1
        application = _authority_application(control, digest)
        durable[control.idempotency_key] = application
        return application

    reconciler = OperatorControlInboxReconciler(
        normal_inbox=normal,
        inflight_inbox=inflight,
        applied_inbox=applied,
        rejected_inbox=rejected,
        secret=SECRET,
    )
    original_terminalize = reconciler._terminalize

    def crash(*_args, **_kwargs):
        raise RuntimeError("crash after authority commit")

    monkeypatch.setattr(reconciler, "_terminalize", crash)
    with pytest.raises(RuntimeError, match="crash after authority commit"):
        await reconciler.reconcile_once(
            SupervisorControlCallbacks(apply=apply), now=NOW
        )
    assert (inflight / publication.path.name).is_file()
    monkeypatch.setattr(reconciler, "_terminalize", original_terminalize)
    [recovered] = await reconciler.reconcile_once(
        SupervisorControlCallbacks(apply=apply), now=NOW + timedelta(minutes=5)
    )
    assert recovered.status is ReconcileStatus.APPLIED
    assert callback_calls == 2
    assert mutations == 1
    assert (applied / publication.path.name).is_file()


async def test_unapplied_expired_inflight_is_authority_rejected_without_mutation(
    inboxes: tuple[Path, Path],
) -> None:
    normal, emergency, inflight, applied, rejected = _normal_custody(inboxes)
    request = OperatorControlRequest.from_mapping(_request())
    publication = ControlInboxPublisher(normal, emergency).publish(
        request, operator_login=LOGIN, secret=SECRET, now=NOW
    )
    mutations = 0

    async def lookup_then_apply(control, _login, digest):
        nonlocal mutations
        expires = datetime.fromisoformat(control.expires_at.replace("Z", "+00:00"))
        if NOW + timedelta(minutes=5) >= expires:
            return _authority_application(
                control, digest, status=ApplicationStatus.REJECTED
            )
        mutations += 1
        return _authority_application(control, digest)

    reconciler = OperatorControlInboxReconciler(
        normal_inbox=normal,
        inflight_inbox=inflight,
        applied_inbox=applied,
        rejected_inbox=rejected,
        secret=SECRET,
    )
    [result] = await reconciler.reconcile_once(
        SupervisorControlCallbacks(apply=lookup_then_apply),
        now=NOW + timedelta(minutes=5),
    )
    assert result.status is ReconcileStatus.REJECTED
    assert result.applied is False
    assert mutations == 0
    assert not list(inflight.iterdir())
    assert not list(applied.iterdir())
    assert (rejected / publication.path.name).is_file()


async def test_crash_after_terminal_sidecar_recovers_without_second_authority_mutation(
    inboxes: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    normal, emergency, inflight, applied, rejected = _normal_custody(inboxes)
    request = OperatorControlRequest.from_mapping(_request())
    publication = ControlInboxPublisher(normal, emergency).publish(
        request, operator_login=LOGIN, secret=SECRET, now=NOW
    )
    durable: dict[str, AuthorityApplication] = {}
    mutations = 0

    async def apply(control, _login, digest):
        nonlocal mutations
        if control.idempotency_key not in durable:
            mutations += 1
            durable[control.idempotency_key] = _authority_application(control, digest)
        return durable[control.idempotency_key]

    reconciler = OperatorControlInboxReconciler(
        normal_inbox=normal,
        inflight_inbox=inflight,
        applied_inbox=applied,
        rejected_inbox=rejected,
        secret=SECRET,
    )
    original_move = control_module._atomic_move_regular
    crashed = False

    def crash_after_sidecar(source: Path, destination: Path) -> bytes:
        nonlocal crashed
        if source.parent == inflight and destination == applied and not crashed:
            crashed = True
            terminal = applied / terminal_filename(source.name)
            assert terminal.is_file()
            raise RuntimeError("crash after terminal sidecar")
        return original_move(source, destination)

    monkeypatch.setattr(control_module, "_atomic_move_regular", crash_after_sidecar)
    with pytest.raises(RuntimeError, match="crash after terminal sidecar"):
        await reconciler.reconcile_once(
            SupervisorControlCallbacks(apply=apply), now=NOW
        )
    assert (inflight / publication.path.name).is_file()
    [recovered] = await reconciler.reconcile_once(
        SupervisorControlCallbacks(apply=apply), now=NOW
    )
    assert recovered.status is ReconcileStatus.APPLIED
    assert mutations == 1
    assert not list(inflight.glob("*.control.json"))
    assert (applied / publication.path.name).is_file()
    assert len(list(applied.glob("*.terminal.json"))) == 1


async def test_authority_echo_mismatch_is_terminally_rejected(
    inboxes: tuple[Path, Path],
) -> None:
    normal, emergency, inflight, applied, rejected = _normal_custody(inboxes)
    request = OperatorControlRequest.from_mapping(_request())
    publication = ControlInboxPublisher(normal, emergency).publish(
        request, operator_login=LOGIN, secret=SECRET, now=NOW
    )

    async def apply(control, _login, _digest):
        return _authority_application(control, "sha256:" + "b" * 64)

    reconciler = OperatorControlInboxReconciler(
        normal_inbox=normal,
        inflight_inbox=inflight,
        applied_inbox=applied,
        rejected_inbox=rejected,
        secret=SECRET,
    )
    [result] = await reconciler.reconcile_once(
        SupervisorControlCallbacks(apply=apply), now=NOW
    )
    assert result.status is ReconcileStatus.CONFLICT
    assert result.inbox_acknowledged is True
    assert result.applied is False
    assert not list(inflight.glob("*.control.json"))
    assert not list(applied.iterdir())
    assert (rejected / publication.path.name).is_file()
    receipt = json.loads(
        (rejected / terminal_filename(publication.path.name)).read_text()
    )
    assert receipt["error_code"] == "idempotency_conflict"
    assert receipt["authority_applied"] is False


async def test_poison_entry_is_rejected_without_starving_valid_candidate(
    tmp_path: Path,
    inboxes: tuple[Path, Path],
) -> None:
    normal, emergency, inflight, applied, rejected = _normal_custody(inboxes)
    poison = normal / ("0" * 64 + ".control.json")
    poison.symlink_to(tmp_path / "foreign")
    request = OperatorControlRequest.from_mapping(
        _request(request_id="valid", idempotency_key="valid-key")
    )
    publication = ControlInboxPublisher(normal, emergency).publish(
        request, operator_login=LOGIN, secret=SECRET, now=NOW
    )

    async def apply(control, _login, digest):
        return _authority_application(control, digest)

    reconciler = OperatorControlInboxReconciler(
        normal_inbox=normal,
        inflight_inbox=inflight,
        applied_inbox=applied,
        rejected_inbox=rejected,
        secret=SECRET,
        max_candidates_per_cycle=1,
    )
    results = await reconciler.reconcile_once(
        SupervisorControlCallbacks(apply=apply), now=NOW
    )
    assert [result.status for result in results] == [
        ReconcileStatus.INVALID,
        ReconcileStatus.APPLIED,
    ]
    assert not poison.exists()
    assert list(rejected.glob(".unsafe.*"))
    assert (applied / publication.path.name).is_file()


async def test_reconciler_rejects_emergency_on_normal_transport(
    inboxes: tuple[Path, Path],
) -> None:
    normal, _, inflight, applied, rejected = _normal_custody(inboxes)
    request = OperatorControlRequest.from_mapping(
        _request("emergency_stop", request_id="stop", idempotency_key="stop-key")
    )
    ControlInboxPublisher(normal, normal).publish(
        request, operator_login=LOGIN, secret=SECRET, now=NOW
    )
    calls = []

    async def apply(*args):
        calls.append(args)
        raise AssertionError("emergency must never reach normal authority callback")

    reconciler = OperatorControlInboxReconciler(
        normal_inbox=normal,
        inflight_inbox=inflight,
        applied_inbox=applied,
        rejected_inbox=rejected,
        secret=SECRET,
    )
    [result] = await reconciler.reconcile_once(
        SupervisorControlCallbacks(apply=apply), now=NOW
    )
    assert result.status is ReconcileStatus.INVALID
    assert result.error_code == "invalid_schema"
    assert calls == []
    assert list(rejected.glob("*.control.json"))


def test_semantics_contract_hash_is_pinned() -> None:
    assert OPERATOR_CONTROL_SEMANTICS_SHA256 == (
        "sha256:69a0eb088277882e333ac41a6fb7014f6ed9d792e6d4a4b2b8510f20de15077c"
    )
    assert OPERATOR_CONTROL_HTTP_BINDING_SHA256 == (
        "sha256:9e1aec44c75cf6b24341389b8227f57fe4d4cf48328992f2125bffca34fcf3eb"
    )
    assert OPERATOR_CONTROL_AUTHORITY_BINDING_SHA256 == (
        "sha256:495f16964248948c68f97b5ec02b7e5d3e00e006979bf283ea783127e303d52d"
    )


def test_shared_emergency_decoder_vectors() -> None:
    fixture = json.loads(
        Path("tests/fixtures/sadhana_operator_control_vectors.v1.json").read_text()
    )
    assert fixture["semantics_contract_sha256"] == (
        OPERATOR_CONTROL_SEMANTICS_SHA256.removeprefix("sha256:")
    )
    assert fixture["authority_binding_contract_sha256"] == (
        OPERATOR_CONTROL_AUTHORITY_BINDING_SHA256.removeprefix("sha256:")
    )
    secret = fixture["test_only_hmac_secret_utf8"].encode()
    verify_at = datetime.fromisoformat(fixture["verify_at"].replace("Z", "+00:00"))
    for vector in fixture["vectors"]:
        raw = base64.b64decode(vector["raw_base64"], validate=True)
        if vector["name"] == "filename_binding_mismatch":
            envelope = decode_and_verify_envelope(
                raw,
                secret=secret,
                now=verify_at,
                expected_actions=frozenset({ControlAction.EMERGENCY_STOP}),
            )
            with pytest.raises(ControlIdempotencyConflict):
                if vector["filename"] != control_filename(
                    envelope.request.idempotency_key
                ):
                    raise ControlIdempotencyConflict("filename binding mismatch")
            continue
        if vector["accepted"]:
            envelope = decode_and_verify_envelope(
                raw,
                secret=secret,
                now=verify_at,
                expected_actions=frozenset({ControlAction.EMERGENCY_STOP}),
            )
            assert envelope.operator_login == fixture["operator_login"]
            assert envelope.request.action is ControlAction.EMERGENCY_STOP
            assert vector["filename"] == control_filename(
                envelope.request.idempotency_key
            )
            continue
        with pytest.raises(OperatorControlError) as caught:
            decode_and_verify_envelope(
                raw,
                secret=secret,
                now=verify_at,
                expected_actions=frozenset({ControlAction.EMERGENCY_STOP}),
            )
        assert caught.value.code == vector["error_code"]


def test_module_has_no_store_database_provider_tool_or_systemctl_boundary() -> None:
    source = Path("dharma_swarm/mission_control_operator_control.py").read_text(
        encoding="utf-8"
    )
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = set(
        "sqlite3 aiosqlite subprocess dharma_swarm.mission_control_campaign "
        "dharma_swarm.mission_control_lifecycle dharma_swarm.runtime_state "
        "dharma_swarm.task_board dharma_swarm.providers dharma_swarm.tool_registry".split()
    )
    assert imported.isdisjoint(forbidden)
