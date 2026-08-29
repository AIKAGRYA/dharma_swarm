"""Foundry kill-switch wiring.

The standing loop MUST call :func:`check` at the top of every generation and
halt if a stop is raised. Two durable stop signals are honored:

- the holon kill-switch (``dharma_swarm.holon_killswitch`` — the repo-wide
  mechanism, ``~/.dharma/agents/<holon>/control/kill_requested.json``), and
- a simple operator ``~/.dharma/foundry/STOP`` file.

The GitHub Actions loop additionally honors the ``loop-control`` branch
``docs/ops/loop_control/KILLSWITCH`` via the shared ``loop-killswitch`` action;
that is enforced in the workflow, not here.
"""

from __future__ import annotations

import json
import os
import binascii
import hashlib
import subprocess
import tempfile
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.holon_killswitch import is_kill_requested, read_kill

FOUNDRY_HOLON = "sublimation-foundry"
_STOP_FILE = Path.home() / ".dharma" / "foundry" / "STOP"
_KILL_FILE = "KILL.json"
_HALT_FILE = "HALT.json"
_CONTROL_RECEIPTS = "control_receipts"
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_SAFE_CATEGORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}")
_HALT_FIELDS = {
    "schema_version", "halt_id", "source", "category", "reason", "terminal",
    "source_evidence", "created_at", "halt_digest",
}
_MAX_RESUME_LEASE_SECONDS = 900
_MAX_RESUME_ISSUED_AGE_SECONDS = 300


class FoundryStopped(RuntimeError):
    """Raised by :func:`check` when a durable stop signal is present."""


def _stop_file(state_root: Path | None = None) -> Path:
    if state_root is not None:
        return Path(state_root) / "STOP"
    return _STOP_FILE


def terminal_kill_file(state_root: Path | None = None) -> Path:
    root = Path(state_root) if state_root is not None else _STOP_FILE.parent
    return root / _KILL_FILE


def halt_file(state_root: Path | None = None) -> Path:
    root = Path(state_root) if state_root is not None else _STOP_FILE.parent
    return root / _HALT_FILE


def _control_receipt_root(state_root: Path | None = None) -> Path:
    root = Path(state_root) if state_root is not None else _STOP_FILE.parent
    return root / _CONTROL_RECEIPTS


def _valid_halt_body(payload: Any) -> dict[str, Any] | None:
    if (
        not isinstance(payload, dict)
        or set(payload) != _HALT_FIELDS
        or payload.get("schema_version") != "foundry_halt.v1"
    ):
        return None
    halt_id = str(payload.get("halt_id", ""))
    if not _SAFE_ID.fullmatch(halt_id):
        return None
    if not _SAFE_CATEGORY.fullmatch(str(payload.get("source", ""))):
        return None
    if not _SAFE_CATEGORY.fullmatch(str(payload.get("category", ""))):
        return None
    if not isinstance(payload.get("reason"), str) or len(payload["reason"]) > 4096:
        return None
    if not isinstance(payload.get("terminal"), bool):
        return None
    if not isinstance(payload.get("source_evidence"), dict):
        return None
    try:
        created = datetime.fromisoformat(
            str(payload.get("created_at", "")).replace("Z", "+00:00")
        )
        if created.tzinfo is None:
            return None
        if (created.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds() > 300:
            return None
    except (TypeError, ValueError):
        return None
    claimed = str(payload.get("halt_digest", ""))
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", claimed):
        return None
    body = {key: value for key, value in payload.items() if key != "halt_digest"}
    try:
        valid_digest = claimed and claimed == _digest(body)
    except (TypeError, ValueError):
        return None
    return payload if valid_digest else None


def _unresolved_halt_receipt(state_root: Path | None = None) -> dict[str, Any] | None:
    """Return an immutable halt event not consumed by a valid resume receipt."""
    root = _control_receipt_root(state_root)
    if not root.is_dir():
        return None
    resolved: set[str] = set()
    for path in sorted(root.glob("resume__*.json")):
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        claimed = str(receipt.get("digest", "")) if isinstance(receipt, dict) else ""
        body = {key: value for key, value in receipt.items() if key != "digest"} \
            if isinstance(receipt, dict) else {}
        halt = body.get("halt")
        if (
            body.get("schema_version") == "foundry_resume_receipt.v1"
            and claimed == _digest(body)
            and _valid_halt_body(halt)
        ):
            resolved.add(str(halt["halt_digest"]))
    for path in sorted(root.glob("halt__*.json")):
        try:
            halt = _valid_halt_body(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            halt = None
        if halt is None:
            return {
                "schema_version": "foundry_halt.corrupt",
                "category": "corrupt_control_halt_receipt",
                "reason": "immutable halt receipt is unreadable or invalid",
                "terminal": True,
            }
        if str(halt["halt_digest"]) not in resolved:
            return halt
    return None


def _ensure_halt_receipt(state_root: Path | None, halt: dict[str, Any]) -> Path:
    valid = _valid_halt_body(halt)
    if valid is None:
        raise FoundryStopped("refusing to record malformed durable halt")
    root = _control_receipt_root(state_root)
    short = str(valid["halt_digest"]).removeprefix("sha256:")[:16]
    path = root / f"halt__{valid['halt_id']}__{short}.json"
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            raise FoundryStopped("immutable halt receipt is corrupt") from exc
        if existing != valid:
            raise FoundryStopped("immutable halt receipt conflicts with halt projection")
        return path
    _write_new_json(path, valid)
    return path


def read_halt(state_root: Path | None = None) -> dict[str, Any] | None:
    path = halt_file(state_root)
    if not path.exists():
        return _unresolved_halt_receipt(state_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {
            "schema_version": "foundry_halt.corrupt",
            "category": "corrupt_halt_marker",
            "reason": "durable HALT marker is unreadable",
            "terminal": True,
        }
    valid = _valid_halt_body(payload)
    return valid if valid is not None else {
        "schema_version": "foundry_halt.corrupt",
        "category": "corrupt_halt_marker",
        "reason": "durable HALT marker is malformed or fails its digest",
        "terminal": True,
    }


def read_terminal_kill(state_root: Path | None = None) -> dict[str, Any] | None:
    path = terminal_kill_file(state_root)
    if not path.exists():
        halt = read_halt(state_root)
        if halt and halt.get("terminal"):
            embedded = halt.get("source_evidence")
            return embedded if isinstance(embedded, dict) else halt
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        return {
            "schema_version": "foundry_terminal_kill.corrupt",
            "category": "corrupt_kill_marker",
            "reason": f"terminal KILL marker unreadable ({type(exc).__name__})",
        }
    if not isinstance(payload, dict):
        return {
            "schema_version": "foundry_terminal_kill.corrupt",
            "category": "corrupt_kill_marker",
            "reason": "terminal KILL marker is not an object",
        }
    return payload


def persist_terminal_kill(
    state_root: Path,
    *,
    category: str,
    reason: str,
    evidence: dict[str, Any] | None = None,
) -> Path:
    """Persist the first terminal verdict; later restarts cannot erase it."""
    if not _SAFE_CATEGORY.fullmatch(str(category)):
        raise ValueError("terminal kill category is invalid")
    if not isinstance(reason, str) or not reason or len(reason) > 4096:
        raise ValueError("terminal kill reason is invalid")
    if evidence is not None and not isinstance(evidence, dict):
        raise ValueError("terminal kill evidence must be an object")
    path = terminal_kill_file(state_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "foundry_terminal_kill.v1",
        "category": category,
        "reason": reason,
        "evidence": evidence or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        _canonical(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("terminal kill evidence is non-canonical") from exc
    try:
        _write_new_json(path, payload)
    except FileExistsError:
        # Terminal means terminal: preserve the original causal receipt.
        latch_current_stop(state_root=state_root)
        return path
    latch_current_stop(state_root=state_root)
    return path


def has_terminal_kill(state_root: Path | None = None) -> bool:
    halt = read_halt(state_root)
    return terminal_kill_file(state_root).exists() or bool(
        halt and halt.get("terminal")
    )


def _canonical(payload: Any) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _digest(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(payload)).hexdigest()


def _write_new_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = (
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def latch_current_stop(
    *,
    agents_root: Path | None = None,
    state_root: Path | None = None,
) -> Path | None:
    """Convert any observed STOP/KILL into one durable, non-self-clearing HALT."""
    existing = halt_file(state_root)
    if existing.exists():
        payload = read_halt(state_root)
        if payload and payload.get("schema_version") == "foundry_halt.v1":
            _ensure_halt_receipt(state_root, payload)
        return existing
    unresolved = _unresolved_halt_receipt(state_root)
    if unresolved is not None:
        if unresolved.get("schema_version") == "foundry_halt.v1":
            try:
                _write_new_json(existing, unresolved)
            except FileExistsError:
                pass
        # A corrupt immutable event deliberately cannot be projected into a
        # normal resumable marker, but its presence still fails closed.
        return existing
    terminal = read_terminal_kill(state_root)
    stop = _stop_file(state_root)
    quarantine = next((p for p in _quarantine_files(state_root) if p.exists()), None)
    holon = read_kill(FOUNDRY_HOLON, agents_root)
    source = ""
    evidence: dict[str, Any] = {}
    reason = ""
    is_terminal = False
    if terminal:
        source, evidence = "KILL", terminal
        reason = str(terminal.get("reason", "terminal safety verdict"))
        is_terminal = True
    elif quarantine is not None:
        source = "QUARANTINE"
        evidence = {
            "path": quarantine.name,
            "sha256": hashlib.sha256(quarantine.read_bytes()).hexdigest(),
        }
        reason = "evidence quarantine requires operator review"
        is_terminal = True
    elif holon:
        source, evidence = "HOLON_KILL", dict(holon)
        reason = str(holon.get("reason", "holon kill requested"))
        is_terminal = True
    elif stop.exists():
        source = "STOP"
        try:
            stop_digest = hashlib.sha256(stop.read_bytes()).hexdigest()
        except OSError:
            stop_digest = "unreadable"
            is_terminal = True
        evidence = {"path": stop.name, "sha256": stop_digest}
        reason = "operator STOP observed; explicit signed resume required"
    else:
        return None
    body = {
        "schema_version": "foundry_halt.v1",
        "halt_id": str(uuid.uuid4()),
        "source": source,
        "category": str(evidence.get("category", source.lower())),
        "reason": reason,
        "terminal": is_terminal,
        "source_evidence": evidence,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    body["halt_digest"] = _digest(body)
    # The immutable receipt is authoritative; HALT.json is only a convenient
    # projection.  Event-first ordering makes a crash or marker deletion fail
    # closed on the next startup.
    _ensure_halt_receipt(state_root, body)
    try:
        _write_new_json(existing, body)
    except FileExistsError:
        pass
    return existing


class ResumeAuthorityError(RuntimeError):
    """A resume envelope is missing, stale, untrusted, or not halt-bound."""


def _verify_openssh_resume_signature(
    body: dict[str, Any],
    signature: dict[str, Any],
    trusted_public_keys: tuple[str, ...] | list[str],
) -> None:
    if signature.get("namespace") != "foundry-resume":
        raise ResumeAuthorityError("OpenSSH resume signature namespace mismatch")
    armored = signature.get("signature")
    if not isinstance(armored, str) or not armored.startswith("-----BEGIN SSH SIGNATURE-----"):
        raise ResumeAuthorityError("OpenSSH resume signature is missing")
    if len(armored.encode("utf-8")) > 16_384:
        raise ResumeAuthorityError("OpenSSH resume signature is oversized")
    normalized: list[str] = []
    for raw in trusted_public_keys:
        fields = str(raw).strip().split()
        if len(fields) < 2 or fields[0] != "ssh-ed25519":
            raise ResumeAuthorityError("trusted OpenSSH resume key is invalid")
        normalized.append(f"foundry-operator {fields[0]} {fields[1]}\n")
    if not normalized:
        raise ResumeAuthorityError("no trusted OpenSSH resume key is configured")
    try:
        with tempfile.TemporaryDirectory(prefix="foundry_resume_verify_") as temp:
            root = Path(temp)
            allowed = root / "allowed_signers"
            sig_path = root / "resume.sig"
            allowed.write_text("".join(normalized), encoding="utf-8")
            sig_path.write_text(armored, encoding="utf-8")
            proc = subprocess.run(
                [
                    "ssh-keygen", "-Y", "verify", "-f", str(allowed),
                    "-I", "foundry-operator", "-n", "foundry-resume",
                    "-s", str(sig_path),
                ],
                input=_canonical(body),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ResumeAuthorityError("OpenSSH resume signature verification unavailable") from exc
    if proc.returncode != 0:
        raise ResumeAuthorityError("OpenSSH resume signature invalid")


def resume_with_authority(
    state_root: Path,
    envelope: dict[str, Any],
    *,
    trusted_public_keys: tuple[str, ...] | list[str] = (),
    trusted_openssh_public_keys: tuple[str, ...] | list[str] = (),
    now: datetime | None = None,
) -> Path:
    """Consume one trusted Ed25519 envelope and preserve all halt evidence.

    Deleting ``STOP``/``KILL.json`` is never a resume.  This is the sole local
    resume primitive: it verifies authority, halt binding, scope and expiry,
    appends an immutable receipt, then archives the markers losslessly.
    """
    import fcntl
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    root = Path(state_root)
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".control.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            latch_current_stop(state_root=root)
            halt = read_halt(root)
            if not halt:
                raise ResumeAuthorityError("no durable halt is present")
            if any(path.exists() for path in _quarantine_files(root)):
                raise ResumeAuthorityError(
                    "quarantine cannot be cleared by a normal resume envelope"
                )
            body = {k: v for k, v in envelope.items() if k != "signature"}
            required = {
                "schema_version", "authority_id", "lease_id", "scope",
                "halt_digest", "issued_at", "expires_at", "nonce",
            }
            if set(body) != required or body.get("schema_version") != "foundry_resume_authority.v1":
                raise ResumeAuthorityError("resume envelope schema/fields invalid")
            if body.get("scope") != "foundry.resume":
                raise ResumeAuthorityError("resume authority scope mismatch")
            if body.get("halt_digest") != halt.get("halt_digest"):
                raise ResumeAuthorityError("resume envelope is not bound to this halt")
            if _valid_halt_body(halt) is None:
                raise ResumeAuthorityError("active durable halt is malformed")
            for field in ("authority_id", "lease_id", "nonce"):
                if not _SAFE_ID.fullmatch(str(body.get(field, ""))):
                    raise ResumeAuthorityError(f"resume {field} is invalid")
            supplied_now = now or datetime.now(timezone.utc)
            if supplied_now.tzinfo is None:
                raise ResumeAuthorityError("resume verification time must be timezone-aware")
            effective_now = supplied_now.astimezone(timezone.utc)
            try:
                issued = datetime.fromisoformat(str(body["issued_at"]).replace("Z", "+00:00"))
                expires = datetime.fromisoformat(str(body["expires_at"]).replace("Z", "+00:00"))
                if issued.tzinfo is None or expires.tzinfo is None:
                    raise ValueError("naive authority time")
            except (TypeError, ValueError) as exc:
                raise ResumeAuthorityError("resume authority time invalid") from exc
            issued = issued.astimezone(timezone.utc)
            expires = expires.astimezone(timezone.utc)
            lifetime = (expires - issued).total_seconds()
            issued_age = (effective_now - issued).total_seconds()
            if (
                issued > effective_now
                or not issued < expires
                or expires <= effective_now
                or lifetime > _MAX_RESUME_LEASE_SECONDS
                or issued_age > _MAX_RESUME_ISSUED_AGE_SECONDS
            ):
                raise ResumeAuthorityError("resume authority is not currently valid")
            nonce_matches = list(
                _control_receipt_root(root).glob(f"resume__{body['nonce']}__*.json")
            )
            if nonce_matches:
                raise ResumeAuthorityError("resume nonce was already consumed")
            signature = envelope.get("signature")
            if not isinstance(signature, dict):
                raise ResumeAuthorityError("resume signature missing or unsupported")
            if signature.get("scheme") == "ed25519":
                public_key_hex = str(signature.get("public_key", "")).lower()
                trusted = {str(key).strip().lower() for key in trusted_public_keys}
                if not trusted or public_key_hex not in trusted:
                    raise ResumeAuthorityError("resume signer is not trusted")
                try:
                    Ed25519PublicKey.from_public_bytes(
                        binascii.unhexlify(public_key_hex)
                    ).verify(
                        binascii.unhexlify(str(signature.get("signature", ""))),
                        _canonical(body),
                    )
                except Exception as exc:
                    raise ResumeAuthorityError("resume signature invalid") from exc
            elif signature.get("scheme") == "openssh-sshsig":
                _verify_openssh_resume_signature(
                    body, signature, trusted_openssh_public_keys
                )
            else:
                raise ResumeAuthorityError("resume signature missing or unsupported")

            receipt_body = {
                "schema_version": "foundry_resume_receipt.v1",
                "halt": halt,
                "authority_envelope": envelope,
                "resumed_at": effective_now.isoformat(),
            }
            receipt_body["digest"] = _digest(receipt_body)
            receipt_root = _control_receipt_root(root)
            short = receipt_body["digest"].removeprefix("sha256:")[:16]
            receipt_path = receipt_root / f"resume__{body['nonce']}__{short}.json"
            _write_new_json(receipt_path, receipt_body)

            history = root / "control_history" / str(halt["halt_id"])
            history.mkdir(parents=True, exist_ok=False)
            for marker in (halt_file(root), terminal_kill_file(root), _stop_file(root)):
                if marker.exists():
                    os.replace(marker, history / marker.name)
            directory_fd = os.open(root, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            return receipt_path
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _quarantine_files(state_root: Path | None = None) -> tuple[Path, Path]:
    root = Path(state_root) if state_root is not None else _STOP_FILE.parent
    return root / "QUARANTINE.json", root / "QUARANTINE"


def is_stopped(*, agents_root: Path | None = None, state_root: Path | None = None) -> bool:
    return (
        has_terminal_kill(state_root)
        or read_halt(state_root) is not None
        or any(path.exists() for path in _quarantine_files(state_root))
        or is_kill_requested(FOUNDRY_HOLON, agents_root)
        or _stop_file(state_root).exists()
    )


def stop_reason(*, agents_root: Path | None = None, state_root: Path | None = None) -> str:
    terminal = read_terminal_kill(state_root)
    if terminal:
        return (
            f"terminal KILL [{terminal.get('category', 'unknown')}]: "
            f"{terminal.get('reason') or '(no reason given)'}"
        )
    halt = read_halt(state_root)
    if halt:
        return (
            f"durable HALT [{halt.get('category', 'unknown')}]: "
            f"{halt.get('reason') or '(no reason given)'}"
        )
    quarantine = next(
        (path for path in _quarantine_files(state_root) if path.exists()),
        None,
    )
    if quarantine is not None:
        return f"evidence quarantine requires operator review: {quarantine}"
    if _stop_file(state_root).exists():
        return f"operator STOP file present: {_stop_file(state_root)}"
    marker = read_kill(FOUNDRY_HOLON, agents_root)
    if marker:
        return f"holon kill requested: {marker.get('reason') or '(no reason given)'}"
    return ""


def check(*, agents_root: Path | None = None, state_root: Path | None = None) -> None:
    """Raise :class:`FoundryStopped` if any durable stop signal is present."""
    if is_stopped(agents_root=agents_root, state_root=state_root):
        latch_current_stop(agents_root=agents_root, state_root=state_root)
        raise FoundryStopped(stop_reason(agents_root=agents_root, state_root=state_root))
