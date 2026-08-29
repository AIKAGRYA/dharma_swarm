"""Durable RSI HALT latch and cryptographically explicit resume authority."""

from __future__ import annotations

import fcntl
import hashlib
import os
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from dharma_swarm.forge_lab.state_io import (
    _fsync_directory,
    atomic_json,
    canonical_json,
    content_digest,
    safe_json,
    validate_digest,
    validate_safe_id,
)
from dharma_swarm.forge_lab.unattended_receipts import (
    UnattendedError,
    append_chain,
    read_chain,
)

HALT_SCHEMA = "rsi_lab.halt.v1"
HALT_EVENT_SCHEMA = "rsi_lab.halt_event_chain.v1"
RESUME_AUTHORITY_SCHEMA = "rsi_lab.resume_authority.v1"
RESUME_SIGNATURE_NAMESPACE = "rsi-lab-resume-v1"
RESUME_SIGNER_IDENTITY = "rsi-lab-root-operator"
TRUSTED_OPERATOR_PUBLIC_KEY = Path("/root/.ssh/id_ed25519.pub")


def _paths(control_root: Path) -> tuple[Path, Path, Path]:
    return (
        control_root / "HALT",
        control_root / "halt_events.jsonl",
        control_root / "safety_mutation.lock",
    )


@contextmanager
def _safety_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise UnattendedError("SAFETY_LOCK_UNSAFE", str(exc)) from exc
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
        ):
            raise UnattendedError("SAFETY_LOCK_UNSAFE", str(path))
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        _fsync_directory(path.parent)
        yield
    finally:
        os.close(descriptor)


def _validate_halt_payload(payload: dict[str, Any], *, source: str) -> dict[str, Any]:
    if payload.get("schema") != HALT_SCHEMA or payload.get("active") is not True:
        raise UnattendedError("HALT_MALFORMED", source)
    unsigned = {key: value for key, value in payload.items() if key != "halt_digest"}
    if payload.get("halt_digest") != content_digest(unsigned):
        raise UnattendedError("HALT_DIGEST", source)
    return payload


def _valid_halt(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise UnattendedError("HALT_PATH_UNSAFE", str(path))
    payload = safe_json(path)
    if payload is None:
        raise UnattendedError("HALT_MALFORMED", str(path))
    return _validate_halt_payload(payload, source=str(path))


def _event_state(events: list[dict[str, Any]]) -> tuple[str | None, dict[str, Any] | None]:
    active_digest: str | None = None
    active_payload: dict[str, Any] | None = None
    for event in events:
        kind = event.get("kind")
        digest = str(event.get("halt_digest") or "")
        if kind == "halt_latched":
            if active_digest is not None:
                raise UnattendedError("HALT_CHAIN_SEMANTICS", "latch while already active")
            try:
                validate_digest(digest)
            except ValueError as exc:
                raise UnattendedError("HALT_CHAIN_SEMANTICS", "invalid halt digest") from exc
            event_payload = event.get("halt")
            active_payload = dict(event_payload) if isinstance(event_payload, dict) else None
            if active_payload is not None:
                _validate_halt_payload(active_payload, source="embedded halt_latched payload")
                if active_payload.get("halt_digest") != digest:
                    raise UnattendedError("HALT_CHAIN_SEMANTICS", "event payload digest mismatch")
            active_digest = digest
        elif kind == "halt_reasserted":
            if active_digest is None or digest != active_digest:
                raise UnattendedError("HALT_CHAIN_SEMANTICS", "reassertion lacks active latch")
        elif kind == "resume_authorized":
            if active_digest is None or digest != active_digest:
                raise UnattendedError("HALT_CHAIN_SEMANTICS", "resume lacks matching latch")
            active_digest = None
            active_payload = None
        else:
            raise UnattendedError("HALT_CHAIN_SEMANTICS", f"unknown event: {kind}")
    return active_digest, active_payload


def _halt_status_unlocked(control_root: Path) -> dict[str, Any]:
    halt_path, events_path, _lock_path = _paths(control_root)
    events = read_chain(events_path, schema=HALT_EVENT_SCHEMA, digest_field="event_digest")
    active_digest, _payload = _event_state(events)
    if active_digest is None:
        if halt_path.exists():
            _valid_halt(halt_path)
            raise UnattendedError(
                "HALT_PROJECTION_UNAUTHORIZED",
                "HALT marker exists without an unresolved authoritative halt event",
            )
        return {
            "active": False,
            "path": str(halt_path),
            "event_count": len(events),
            "last_event_digest": events[-1]["event_digest"] if events else None,
        }
    if not halt_path.exists():
        raise UnattendedError(
            "HALT_PROJECTION_MISSING",
            f"authoritative unresolved halt {active_digest} has no marker projection",
        )
    payload = _valid_halt(halt_path)
    if payload["halt_digest"] != active_digest:
        raise UnattendedError("HALT_PROJECTION_DIVERGED", active_digest)
    return {
        "active": True,
        "path": str(halt_path),
        "halt": payload,
        "halt_digest": active_digest,
        "event_count": len(events),
        "last_event_digest": events[-1]["event_digest"],
    }


def halt_status(control_root: Path) -> dict[str, Any]:
    _halt_path, _events_path, lock_path = _paths(control_root)
    with _safety_lock(lock_path):
        return _halt_status_unlocked(control_root)


def latch_halt(
    control_root: Path,
    *,
    at: str,
    code: str,
    reason: str,
    source: str,
    run_id: str | None = None,
    operator_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Latch once under a shared lock; reassertions never clear first cause."""

    halt_path, events_path, lock_path = _paths(control_root)
    if operator_id is not None:
        operator_id = validate_safe_id(operator_id, field="operator_id")
    if request_id is not None:
        request_id = validate_safe_id(request_id, field="request_id")
    with _safety_lock(lock_path):
        events = read_chain(events_path, schema=HALT_EVENT_SCHEMA, digest_field="event_digest")
        active_digest, recoverable_payload = _event_state(events)
        if active_digest is not None:
            if halt_path.exists():
                current = _valid_halt(halt_path)
                if current["halt_digest"] != active_digest:
                    raise UnattendedError("HALT_PROJECTION_DIVERGED", active_digest)
            elif recoverable_payload is not None:
                current = recoverable_payload
                atomic_json(halt_path, current)
            else:
                raise UnattendedError("HALT_PROJECTION_MISSING", active_digest)
            append_chain(
                events_path,
                {
                    "kind": "halt_reasserted",
                    "at": at,
                    "halt_digest": active_digest,
                    "code": str(code)[:96],
                    "reason": str(reason)[:500],
                    "source": str(source)[:128],
                    "run_id": run_id,
                    "operator_id": operator_id,
                    "request_id": request_id,
                },
                schema=HALT_EVENT_SCHEMA,
                digest_field="event_digest",
            )
            return current
        if halt_path.exists():
            _valid_halt(halt_path)
            raise UnattendedError("HALT_PROJECTION_UNAUTHORIZED", str(halt_path))
        payload: dict[str, Any] = {
            "schema": HALT_SCHEMA,
            "active": True,
            "halted_at": at,
            "code": str(code)[:96],
            "reason": str(reason)[:500],
            "source": str(source)[:128],
            "run_id": run_id,
            "operator_id": operator_id,
            "request_id": request_id,
            "resume_requires": [
                "operator_id",
                "request_id",
                "reason",
                "expected_halt_digest",
                "openssh_signature",
            ],
        }
        payload["halt_digest"] = content_digest(payload)
        append_chain(
            events_path,
            {
                "kind": "halt_latched",
                "at": at,
                "halt_digest": payload["halt_digest"],
                "halt": payload,
                "code": payload["code"],
                "reason": payload["reason"],
                "source": payload["source"],
                "run_id": run_id,
                "operator_id": operator_id,
                "request_id": request_id,
            },
            schema=HALT_EVENT_SCHEMA,
            digest_field="event_digest",
        )
        atomic_json(halt_path, payload)
        return payload


def resume_authority_statement(
    *, operator_id: str, request_id: str, reason: str, expected_halt_digest: str
) -> dict[str, str]:
    return {
        "expected_halt_digest": validate_digest(expected_halt_digest),
        "operator_id": validate_safe_id(operator_id, field="operator_id"),
        "reason": str(reason).strip(),
        "request_id": validate_safe_id(request_id, field="request_id"),
        "schema": RESUME_AUTHORITY_SCHEMA,
    }


def resume_authority_bytes(**kwargs: str) -> bytes:
    statement = resume_authority_statement(**kwargs)
    if not statement["reason"]:
        raise UnattendedError("RESUME_REASON_REQUIRED", "resume reason is required")
    return canonical_json(statement)


def _verify_resume_signature(
    message: bytes,
    *,
    signature_path: Path,
    trusted_public_key: Path,
) -> dict[str, Any]:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        signature_fd = os.open(signature_path, flags)
    except OSError as exc:
        raise UnattendedError("RESUME_SIGNATURE_UNSAFE", str(signature_path)) from exc
    try:
        signature_stat = os.fstat(signature_fd)
        if not stat.S_ISREG(signature_stat.st_mode) or signature_stat.st_size > 64 * 1024:
            raise UnattendedError("RESUME_SIGNATURE_UNSAFE", str(signature_path))
        signature_bytes = os.read(signature_fd, 64 * 1024 + 1)
        os.lseek(signature_fd, 0, os.SEEK_SET)
        try:
            key_fd = os.open(trusted_public_key, flags)
        except OSError as exc:
            raise UnattendedError("RESUME_TRUST_KEY_MISSING", str(trusted_public_key)) from exc
        try:
            key_stat = os.fstat(key_fd)
            if not stat.S_ISREG(key_stat.st_mode) or key_stat.st_size > 16 * 1024:
                raise UnattendedError("RESUME_TRUST_KEY_UNREADABLE", str(trusted_public_key))
            key_bytes = os.read(key_fd, 16 * 1024 + 1)
        finally:
            os.close(key_fd)
        try:
            public_key = key_bytes.decode("utf-8").strip()
        except UnicodeError as exc:
            raise UnattendedError("RESUME_TRUST_KEY_UNREADABLE", str(trusted_public_key)) from exc
        if not public_key.startswith(("ssh-ed25519 ", "sk-ssh-ed25519@openssh.com ")):
            raise UnattendedError("RESUME_TRUST_KEY_TYPE", "trusted operator key must be Ed25519")
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8") as allowed:
                allowed.write(f"{RESUME_SIGNER_IDENTITY} {public_key}\n")
                allowed.flush()
                os.fsync(allowed.fileno())
                result = subprocess.run(
                    [
                        "ssh-keygen",
                        "-Y",
                        "verify",
                        "-f",
                        allowed.name,
                        "-I",
                        RESUME_SIGNER_IDENTITY,
                        "-n",
                        RESUME_SIGNATURE_NAMESPACE,
                        "-s",
                        f"/proc/self/fd/{signature_fd}",
                    ],
                    input=message,
                    capture_output=True,
                    check=False,
                    timeout=20,
                    pass_fds=(signature_fd,),
                )
        except (OSError, subprocess.SubprocessError) as exc:
            raise UnattendedError("RESUME_SIGNATURE_VERIFIER", type(exc).__name__) from exc
    finally:
        os.close(signature_fd)
    if result.returncode != 0:
        raise UnattendedError("RESUME_SIGNATURE_INVALID", "OpenSSH signature verification failed")
    return {
        "signature_namespace": RESUME_SIGNATURE_NAMESPACE,
        "signer_identity": RESUME_SIGNER_IDENTITY,
        "trusted_public_key_path": str(trusted_public_key),
        "trusted_public_key_sha256": "sha256:"
        + hashlib.sha256((public_key + "\n").encode("utf-8")).hexdigest(),
        "signature_sha256": "sha256:" + hashlib.sha256(signature_bytes).hexdigest(),
    }


def resume_halt(
    control_root: Path,
    *,
    at: str,
    operator_id: str,
    request_id: str,
    reason: str,
    expected_halt_digest: str,
    signature_path: Path,
    _trusted_public_key: Path = TRUSTED_OPERATOR_PUBLIC_KEY,
) -> dict[str, Any]:
    """Verify the existing operator key, receipt authority, then clear projection."""

    message = resume_authority_bytes(
        operator_id=operator_id,
        request_id=request_id,
        reason=reason,
        expected_halt_digest=expected_halt_digest,
    )
    proof = _verify_resume_signature(
        message,
        signature_path=signature_path.expanduser(),
        trusted_public_key=_trusted_public_key.expanduser(),
    )
    statement_digest = "sha256:" + hashlib.sha256(message).hexdigest()
    halt_path, events_path, lock_path = _paths(control_root)
    with _safety_lock(lock_path):
        events = read_chain(events_path, schema=HALT_EVENT_SCHEMA, digest_field="event_digest")
        active_digest, _payload = _event_state(events)
        prior = next(
            (
                row
                for row in reversed(events)
                if row.get("kind") == "resume_authorized" and row.get("request_id") == request_id
            ),
            None,
        )
        if prior is not None:
            if (
                prior.get("halt_digest") != expected_halt_digest
                or prior.get("authority_statement_digest") != statement_digest
            ):
                raise UnattendedError("RESUME_REQUEST_CONFLICT", request_id)
            if halt_path.exists():
                current = _valid_halt(halt_path)
                if current["halt_digest"] != expected_halt_digest:
                    raise UnattendedError("RESUME_HALT_CHANGED", request_id)
                halt_path.unlink()
                _fsync_directory(halt_path.parent)
            return prior
        if active_digest is None:
            raise UnattendedError("HALT_NOT_ACTIVE", str(halt_path))
        if active_digest != expected_halt_digest:
            raise UnattendedError("RESUME_HALT_CHANGED", expected_halt_digest)
        if not halt_path.exists():
            raise UnattendedError("HALT_PROJECTION_MISSING", active_digest)
        current = _valid_halt(halt_path)
        if current["halt_digest"] != active_digest:
            raise UnattendedError("HALT_PROJECTION_DIVERGED", active_digest)
        receipt = append_chain(
            events_path,
            {
                "kind": "resume_authorized",
                "at": at,
                "halt_digest": expected_halt_digest,
                "operator_id": operator_id,
                "request_id": request_id,
                "reason": str(reason).strip()[:500],
                "authority_statement_digest": statement_digest,
                **proof,
            },
            schema=HALT_EVENT_SCHEMA,
            digest_field="event_digest",
        )
        halt_path.unlink()
        _fsync_directory(halt_path.parent)
        return receipt


__all__ = [
    "HALT_EVENT_SCHEMA",
    "HALT_SCHEMA",
    "RESUME_AUTHORITY_SCHEMA",
    "RESUME_SIGNATURE_NAMESPACE",
    "TRUSTED_OPERATOR_PUBLIC_KEY",
    "halt_status",
    "latch_halt",
    "resume_authority_bytes",
    "resume_authority_statement",
    "resume_halt",
]
