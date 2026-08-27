"""Credential-safe handoff into the existing Dharma key store.

This module is deliberately not a provider registry or a second secret store.
Provider names and environment variables come from :mod:`dharma_swarm.api_keys`,
and values are written only to the already-canonical host file
``~/.dharma/agent_keys.env``.  Plans, status, and receipts contain names and
presence booleans only; they never contain a credential value or its digest.
"""

from __future__ import annotations

import fcntl
import os
import re
import shlex
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping
from uuid import uuid4

from dharma_swarm.api_keys import (
    PROVIDER_API_KEY_ENV_KEYS,
    PROVIDER_BASE_URL_ENV_KEYS,
    apply_env_assignment,
)
from dharma_swarm.forge_lab.state_io import (
    content_digest,
    now_utc,
    safe_json,
    validate_safe_id,
    write_json_exclusive,
)

STATUS_SCHEMA = "rsi_lab.provider_credential_status.v1"
PLAN_SCHEMA = "rsi_lab.provider_credential_plan.v1"
RECEIPT_SCHEMA = "rsi_lab.provider_credential_receipt.v1"
INTENT_SCHEMA = "rsi_lab.provider_credential_intent.v1"

_ASSIGNMENT_RE = re.compile(
    r"^(?P<prefix>\s*(?:export\s+)?)(?P<name>[A-Za-z_][A-Za-z0-9_]*)="
)


class CredentialHandoffError(RuntimeError):
    """Fail-closed credential mutation error with a stable machine code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def credential_store(home: Path | None = None) -> Path:
    """Return the one existing dkeys-compatible host secret file."""

    root = (home or Path.home()).expanduser().resolve(strict=False)
    if not root.is_absolute() or root == Path("/"):
        raise CredentialHandoffError("UNSAFE_HOME", "credential home must be a non-root path")
    return root / ".dharma" / "agent_keys.env"


def _provider(provider: str) -> tuple[str, str, str | None]:
    name = str(provider or "").strip().casefold()
    key_env = PROVIDER_API_KEY_ENV_KEYS.get(name)
    if key_env is None:
        raise CredentialHandoffError(
            "IMPLEMENTATION_REQUIRED",
            f"provider {name!r} is not implemented in the canonical provider registry",
        )
    return name, key_env, PROVIDER_BASE_URL_ENV_KEYS.get(name)


def _present_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    if path.is_symlink() or not path.is_file():
        raise CredentialHandoffError(
            "STORE_UNSAFE", "credential store must be a regular non-symlink file"
        )
    try:
        lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    except (OSError, UnicodeError) as exc:
        raise CredentialHandoffError("STORE_UNREADABLE", str(exc)) from exc
    parsed: dict[str, str] = {}
    for line in lines:
        apply_env_assignment(line, parsed)
    return set(parsed)


def _fsync_directory(path: Path) -> None:
    """Persist directory entries needed by the credential recovery protocol."""

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _usable_process_value(env_name: str, value: object) -> bool:
    parsed: dict[str, str] = {}
    assignment = f"export {env_name}={shlex.quote(str(value or ''))}"
    return bool(apply_env_assignment(assignment, parsed) and parsed.get(env_name))


def credential_status(
    provider: str | None = None,
    *,
    home: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return names/presence only; never load or return credential values."""

    path = credential_store(home)
    _ensure_private_directory(path.parent, create=False)
    present_in_store = _present_names(path)
    process_env = os.environ if env is None else env
    providers = [str(provider).strip().casefold()] if provider else sorted(
        PROVIDER_API_KEY_ENV_KEYS
    )
    rows: list[dict[str, Any]] = []
    for requested in providers:
        name, key_env, base_url_env = _provider(requested)
        rows.append(
            {
                "provider": name,
                "credential_env": key_env,
                "base_url_env": base_url_env,
                "credential_present_in_store": key_env in present_in_store,
                "credential_present_in_process": _usable_process_value(
                    key_env, process_env.get(key_env, "")
                ),
            }
        )
    mode = None
    if path.exists() and not path.is_symlink():
        mode = oct(path.stat().st_mode & 0o777)
    mode_safe = mode in {None, "0o600"}
    return {
        "schema": STATUS_SCHEMA,
        "ok": mode_safe
        and all(
            row["credential_present_in_store"]
            or row["credential_present_in_process"]
            for row in rows
        ),
        "read_only": True,
        "store": str(path),
        "store_exists": path.is_file() and not path.is_symlink(),
        "store_mode": mode,
        "store_mode_safe": mode_safe,
        "rows": rows,
        "secret_values_recorded": False,
    }


def plan_credential(provider: str, *, home: Path | None = None) -> dict[str, Any]:
    """Build a value-free, replayable plan for one provider key handoff."""

    name, key_env, base_url_env = _provider(provider)
    status = credential_status(name, home=home, env={})
    plan = {
        "schema": PLAN_SCHEMA,
        "provider": name,
        "credential_env": key_env,
        "base_url_env": base_url_env,
        "store": status["store"],
        "action": "upsert",
        "input_channel": "hidden_prompt_or_stdin_only",
        "secret_values_recorded": False,
        "secret_digests_recorded": False,
    }
    plan["plan_digest"] = content_digest(plan)
    return plan


def validate_plan(
    plan_digest: str,
    provider: str,
    *,
    home: Path | None = None,
) -> dict[str, Any]:
    plan = plan_credential(provider, home=home)
    if str(plan_digest or "") != plan["plan_digest"]:
        raise CredentialHandoffError(
            "PLAN_CHANGED",
            "credential plan digest changed; inspect a fresh plan before applying",
        )
    return plan


@contextmanager
def _store_lock(path: Path) -> Iterator[None]:
    _ensure_private_directory(path.parent, create=True)
    lock_path = path.parent / ".agent_keys.lock"
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise CredentialHandoffError("STORE_LOCK_UNSAFE", str(exc)) from exc
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _ensure_private_directory(path: Path, *, create: bool) -> None:
    created = False
    try:
        if path.is_symlink():
            raise CredentialHandoffError(
                "STORE_PATH_UNSAFE", f"credential directory is a symlink: {path}"
            )
        if path.exists():
            if not path.is_dir():
                raise CredentialHandoffError(
                    "STORE_PATH_UNSAFE", f"credential directory is not a directory: {path}"
                )
        elif create:
            path.mkdir(mode=0o700, parents=False, exist_ok=False)
            created = True
        else:
            return
        if create:
            os.chmod(path, 0o700)
        if created:
            _fsync_directory(path.parent)
    except CredentialHandoffError:
        raise
    except OSError as exc:
        raise CredentialHandoffError("STORE_PATH_UNSAFE", str(exc)) from exc


def _validate_secret(env_name: str, secret: str) -> None:
    if (
        not isinstance(secret, str)
        or secret != secret.strip()
        or "\n" in secret
        or "\r" in secret
        or "\x00" in secret
        or len(secret) < 8
    ):
        raise CredentialHandoffError(
            "INVALID_SECRET",
            "credential must be at least eight characters with no surrounding whitespace",
        )
    parsed: dict[str, str] = {}
    assignment = f"export {env_name}={shlex.quote(secret)}"
    if not apply_env_assignment(assignment, parsed) or parsed.get(env_name) != secret:
        raise CredentialHandoffError(
            "INVALID_SECRET", "credential does not round-trip through the canonical loader"
        )


def _atomic_upsert(path: Path, env_name: str, secret: str) -> None:
    _validate_secret(env_name, secret)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise CredentialHandoffError(
            "STORE_UNSAFE", "credential store must be a regular non-symlink file"
        )
    if path.exists() and (path.stat().st_mode & 0o077):
        raise CredentialHandoffError(
            "STORE_MODE_UNSAFE", "credential store must not be group/world accessible"
        )
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = original.splitlines()
    replacement = f"export {env_name}={shlex.quote(secret)}"
    output: list[str] = []
    replaced = False
    for line in lines:
        match = _ASSIGNMENT_RE.match(line)
        if match and match.group("name") == env_name:
            if not replaced:
                output.append(replacement)
                replaced = True
            continue
        output.append(line)
    if not replaced:
        output.append(replacement)
    payload = "\n".join(output) + "\n"
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid4().hex[:8]}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _record_digest(payload: Mapping[str, Any], field: str) -> str:
    return content_digest({key: value for key, value in payload.items() if key != field})


def _validated_record(
    path: Path,
    *,
    schema: str,
    digest_field: str,
    request_id: str,
    provider: str,
    plan_digest: str,
    store: Path,
) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise CredentialHandoffError("RECEIPT_INVALID", f"unsafe evidence path: {path}")
    payload = safe_json(path)
    path_field = "intent" if schema == INTENT_SCHEMA else "receipt"
    if (
        payload is None
        or payload.get("schema") != schema
        or payload.get("request_id") != request_id
        or payload.get("provider") != provider
        or payload.get("plan_digest") != plan_digest
        or payload.get("store") != str(store)
        or payload.get(path_field) != str(path)
        or payload.get(digest_field) != _record_digest(payload, digest_field)
    ):
        raise CredentialHandoffError(
            "REQUEST_ID_REUSED", "request evidence belongs to another credential intent"
        )
    return payload


def apply_credential(
    provider: str,
    *,
    plan_digest: str,
    request_id: str,
    secret: str,
    home: Path | None = None,
) -> dict[str, Any]:
    """Apply one hidden-input credential and write a value-free receipt."""

    try:
        request_id = validate_safe_id(request_id, field="request_id")
    except ValueError as exc:
        raise CredentialHandoffError("INVALID_REQUEST_ID", str(exc)) from exc
    path = credential_store(home)
    plan = validate_plan(plan_digest, provider, home=home)
    with _store_lock(path):
        receipt_root = path.parent / "provider_credential_receipts"
        _ensure_private_directory(receipt_root, create=True)
        intent_root = receipt_root / "intents"
        applied_root = receipt_root / "applied"
        _ensure_private_directory(intent_root, create=True)
        _ensure_private_directory(applied_root, create=True)
        intent_path = intent_root / f"{request_id}.json"
        receipt_path = applied_root / f"{request_id}.json"
        if receipt_path.exists() or receipt_path.is_symlink():
            prior = _validated_record(
                receipt_path,
                schema=RECEIPT_SCHEMA,
                digest_field="receipt_digest",
                request_id=request_id,
                provider=str(plan["provider"]),
                plan_digest=str(plan["plan_digest"]),
                store=path,
            )
            _validated_record(
                intent_path,
                schema=INTENT_SCHEMA,
                digest_field="intent_digest",
                request_id=request_id,
                provider=str(plan["provider"]),
                plan_digest=str(plan["plan_digest"]),
                store=path,
            )
            status = credential_status(str(plan["provider"]), home=home, env={})
            if not status.get("ok"):
                raise CredentialHandoffError(
                    "REQUEST_STATE_MISMATCH",
                    "applied receipt exists but the canonical store is not ready",
                )
            return {**prior, "ok": True, "idempotent_replay": True}

        _validate_secret(str(plan["credential_env"]), secret)
        if intent_path.exists() or intent_path.is_symlink():
            _validated_record(
                intent_path,
                schema=INTENT_SCHEMA,
                digest_field="intent_digest",
                request_id=request_id,
                provider=str(plan["provider"]),
                plan_digest=str(plan["plan_digest"]),
                store=path,
            )
            raise CredentialHandoffError(
                "OUTCOME_UNKNOWN",
                "a durable credential intent has no terminal receipt; inspect store status "
                "and use a new request id for an explicit replacement",
            )
        else:
            intent = {
                "schema": INTENT_SCHEMA,
                "request_id": request_id,
                "created_at": now_utc(),
                "provider": plan["provider"],
                "credential_env": plan["credential_env"],
                "store": str(path),
                "plan_digest": plan["plan_digest"],
                "intent": str(intent_path),
                "secret_value_recorded": False,
                "secret_digest_recorded": False,
            }
            intent["intent_digest"] = _record_digest(intent, "intent_digest")
            try:
                write_json_exclusive(intent_path, intent)
                _fsync_directory(intent_root)
            except OSError as exc:
                raise CredentialHandoffError("INTENT_WRITE_FAILED", str(exc)) from exc

        try:
            _atomic_upsert(path, str(plan["credential_env"]), secret)
        except CredentialHandoffError:
            raise
        except OSError as exc:
            raise CredentialHandoffError("STORE_WRITE_FAILED", str(exc)) from exc
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "request_id": request_id,
            "applied_at": now_utc(),
            "provider": plan["provider"],
            "credential_env": plan["credential_env"],
            "store": str(path),
            "plan_digest": plan["plan_digest"],
            "store_mode": oct(path.stat().st_mode & 0o777),
            "receipt": str(receipt_path),
            "intent": str(intent_path),
            "intent_digest": intent["intent_digest"],
            "secret_value_recorded": False,
            "secret_digest_recorded": False,
        }
        receipt["receipt_digest"] = _record_digest(receipt, "receipt_digest")
        try:
            write_json_exclusive(receipt_path, receipt)
            _fsync_directory(applied_root)
        except OSError as exc:
            raise CredentialHandoffError(
                "RECEIPT_WRITE_FAILED",
                "credential intent is durable but the terminal receipt failed; inspect "
                "credential status. Reusing this request id will report OUTCOME_UNKNOWN; "
                "use a new request id only for an explicit replacement: " + str(exc),
            ) from exc
        return {
            **receipt,
            "receipt": str(receipt_path),
            "ok": True,
        }


__all__ = [
    "CredentialHandoffError",
    "PLAN_SCHEMA",
    "RECEIPT_SCHEMA",
    "STATUS_SCHEMA",
    "apply_credential",
    "credential_status",
    "credential_store",
    "plan_credential",
    "validate_plan",
]
