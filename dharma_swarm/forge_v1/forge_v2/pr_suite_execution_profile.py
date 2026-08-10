"""Digest-bound PR-suite execution profiles and validator trust material."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from typing import Any, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


PROFILE_SCHEMA = "forge_v2.pr_suite_execution_profile.v1"
PROFILE_ENV = "FORGE_PR_SUITE_EXECUTION_PROFILE"
VALIDATOR_SIGNING_KEY_ENV = "FORGE_PR_SUITE_VALIDATOR_SIGNING_KEY"
VALIDATOR_TRUST_ROOT_ENV = "FORGE_PR_SUITE_VALIDATOR_TRUST_ROOT"
VALIDATOR_ATTESTATION_SCHEMA = "forge_v2.pr_suite_validator_attestation.v1"
VALIDATOR_PRIVATE_KEY_SCHEMA = "forge_v2.pr_suite_validator_private_key.v1"
VALIDATOR_TRUST_ROOT_SCHEMA = "forge_v2.pr_suite_validator_trust_root.v1"
DEFAULT_TEST_COMMAND = ("{python}", "-m", "pytest", "-q", "{targets}")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
_USER_RE = re.compile(r"^(?P<uid>[1-9][0-9]*):(?P<gid>[1-9][0-9]*)$")
_KEY_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
_NONCE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{15,255}$")
_SECRET_NAME_RE = re.compile(
    r"(?:api[_-]?key|access[_-]?token|secret|password|credential)",
    re.IGNORECASE,
)
_URL_USERINFO_RE = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)[^/@\s]+@")
_ALLOWED_FIELDS = frozenset({"python", "checkout", "target", "targets"})


class ExecutionBoundaryError(RuntimeError):
    """Base class for typed, fail-closed evaluator errors."""


class IsolationUnavailable(ExecutionBoundaryError):
    """No attested isolation backend is available."""


class ProfileTampered(ExecutionBoundaryError):
    """The execution profile does not match its declared digest/contract."""


class UnsafeTargetPath(ExecutionBoundaryError):
    """A test target could escape the checkout."""


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _validate_command_tokens(
    tokens: Sequence[str], *, field: str, require_targets: bool
) -> tuple[str, ...]:
    normalized = tuple(str(token) for token in tokens)
    if not normalized:
        if require_targets:
            raise ValueError(f"{field} must not be empty")
        return ()
    fields: set[str] = set()
    for token in normalized:
        if not token or "\x00" in token or "\n" in token or "\r" in token:
            raise ValueError(f"{field} contains an empty or control-character token")
        if _SECRET_NAME_RE.search(token):
            raise ValueError(f"{field} must not embed credentials")
        for _, name, _, _ in Formatter().parse(token):
            if name:
                fields.add(name)
    unknown = fields - _ALLOWED_FIELDS
    if unknown:
        raise ValueError(f"{field} contains unsupported placeholders: {sorted(unknown)}")
    if require_targets and not ({"target", "targets"} & fields):
        raise ValueError(f"{field} must select a target")
    if normalized[0] not in {"{python}"}:
        raise ValueError(f"{field} executable must be the profile's {{python}}")
    return normalized


@dataclass(frozen=True)
class ExecutionProfile:
    """Digestable command and resource contract for one container image."""

    profile_id: str
    backend: str
    runtime: str
    image: str
    user: str
    python: str
    test_command: tuple[str, ...] = DEFAULT_TEST_COMMAND
    setup_command: tuple[str, ...] = ()
    network_mode: str = "none"
    read_only_rootfs: bool = True
    cap_drop: tuple[str, ...] = ("ALL",)
    no_new_privileges: bool = True
    pull_policy: str = "never"
    memory_bytes: int = 2 * 1024 * 1024 * 1024
    cpu_count: float = 2.0
    pids_limit: int = 128
    nofile_limit: int = 256
    file_size_bytes: int = 64 * 1024 * 1024
    tmpfs_bytes: int = 256 * 1024 * 1024
    output_limit_bytes: int = 256 * 1024
    stdin_limit_bytes: int = 4 * 1024 * 1024

    def __post_init__(self) -> None:
        if not _ID_RE.fullmatch(self.profile_id):
            raise ValueError("invalid execution profile id")
        if self.backend not in {"docker", "podman"}:
            raise ValueError("PR-suite execution supports only docker or podman")
        runtime = Path(self.runtime)
        if not runtime.is_absolute():
            raise ValueError("container runtime path must be absolute")
        if not re.search(r"@sha256:[0-9a-f]{64}$", self.image):
            raise ValueError("container image must be pinned by sha256 digest")
        match = _USER_RE.fullmatch(self.user)
        if match is None or int(match.group("uid")) == 0 or int(match.group("gid")) == 0:
            raise ValueError("container user must be an explicit non-root uid:gid")
        if not self.python.startswith("/") or "\x00" in self.python:
            raise ValueError("profile python must be an absolute container path")
        if (
            self.network_mode != "none"
            or self.read_only_rootfs is not True
            or tuple(self.cap_drop) != ("ALL",)
            or self.no_new_privileges is not True
            or self.pull_policy != "never"
        ):
            raise ValueError("isolation controls are non-negotiable")
        object.__setattr__(self, "cap_drop", tuple(self.cap_drop))
        object.__setattr__(
            self,
            "test_command",
            _validate_command_tokens(
                self.test_command,
                field="test_command",
                require_targets=True,
            ),
        )
        object.__setattr__(
            self,
            "setup_command",
            _validate_command_tokens(
                self.setup_command,
                field="setup_command",
                require_targets=False,
            ),
        )
        limits = {
            "memory_bytes": (self.memory_bytes, 64 * 1024 * 1024, 64 * 1024 * 1024 * 1024),
            "pids_limit": (self.pids_limit, 8, 4096),
            "nofile_limit": (self.nofile_limit, 32, 65536),
            "file_size_bytes": (self.file_size_bytes, 1024 * 1024, 1024 * 1024 * 1024),
            "tmpfs_bytes": (
                self.tmpfs_bytes,
                16 * 1024 * 1024,
                4 * 1024 * 1024 * 1024,
            ),
            "output_limit_bytes": (self.output_limit_bytes, 1024, 4 * 1024 * 1024),
            "stdin_limit_bytes": (self.stdin_limit_bytes, 1024, 64 * 1024 * 1024),
        }
        for name, (value, minimum, maximum) in limits.items():
            if not minimum <= int(value) <= maximum:
                raise ValueError(f"{name} outside safe bounds")
        if not 0.1 <= float(self.cpu_count) <= 32.0:
            raise ValueError("cpu_count outside safe bounds")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema": PROFILE_SCHEMA,
            "profile_id": self.profile_id,
            "backend": self.backend,
            "runtime": self.runtime,
            "image": self.image,
            "user": self.user,
            "python": self.python,
            "test_command": list(self.test_command),
            "setup_command": list(self.setup_command),
            "network_mode": self.network_mode,
            "read_only_rootfs": self.read_only_rootfs,
            "cap_drop": list(self.cap_drop),
            "no_new_privileges": self.no_new_privileges,
            "pull_policy": self.pull_policy,
            "memory_bytes": self.memory_bytes,
            "cpu_count": self.cpu_count,
            "pids_limit": self.pids_limit,
            "nofile_limit": self.nofile_limit,
            "file_size_bytes": self.file_size_bytes,
            "tmpfs_bytes": self.tmpfs_bytes,
            "output_limit_bytes": self.output_limit_bytes,
            "stdin_limit_bytes": self.stdin_limit_bytes,
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(_canonical_json(self.to_mapping())).hexdigest()

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "ExecutionProfile":
        payload = dict(raw)
        schema = str(payload.pop("schema", ""))
        if schema != PROFILE_SCHEMA:
            raise ProfileTampered(f"unsupported execution profile schema: {schema!r}")
        payload.pop("profile_sha256", None)
        try:
            return cls(**payload)
        except (TypeError, ValueError) as exc:
            raise ProfileTampered(str(exc)) from exc


def load_execution_profile(path: Path | str) -> ExecutionProfile:
    profile_path = Path(path).expanduser()
    try:
        fd = os.open(profile_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as exc:
        raise IsolationUnavailable(f"execution profile unavailable: {profile_path}") from exc
    try:
        profile_stat = os.fstat(fd)
        if (
            not stat.S_ISREG(profile_stat.st_mode)
            or profile_stat.st_mode & 0o022
            or profile_stat.st_uid not in {0, os.geteuid()}
            or profile_stat.st_size > 1024 * 1024
        ):
            raise ProfileTampered("execution profile must be a trusted regular file")
        raw_bytes = os.read(fd, profile_stat.st_size + 1)
    finally:
        os.close(fd)
    try:
        raw = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProfileTampered(f"invalid execution profile: {exc}") from exc
    declared = str(raw.get("profile_sha256") or "")
    if not _DIGEST_RE.fullmatch(declared):
        raise ProfileTampered("execution profile is missing a valid profile_sha256")
    profile = ExecutionProfile.from_mapping(raw)
    if not hmac.compare_digest(declared, profile.sha256):
        raise ProfileTampered("execution profile digest mismatch")
    return profile


def resolve_execution_profile(
    profile: ExecutionProfile | Path | str | None,
) -> ExecutionProfile:
    if isinstance(profile, ExecutionProfile):
        return profile
    configured = profile or os.environ.get(PROFILE_ENV, "").strip()
    if not configured:
        raise IsolationUnavailable("explicit PR-suite execution profile required")
    return load_execution_profile(configured)


def _load_trusted_json(path: Path | str, *, private: bool) -> dict[str, Any]:
    candidate = Path(path).expanduser()
    try:
        descriptor = os.open(candidate, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as exc:
        raise IsolationUnavailable(f"validator trust material unavailable: {candidate}") from exc
    try:
        metadata = os.fstat(descriptor)
        forbidden_mode = 0o077 if private else 0o022
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_mode & forbidden_mode
            or metadata.st_uid not in {0, os.geteuid()}
            or metadata.st_size > 1024 * 1024
        ):
            raise ProfileTampered("validator trust material is not a trusted regular file")
        raw = os.read(descriptor, metadata.st_size + 1)
    finally:
        os.close(descriptor)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProfileTampered("validator trust material is invalid JSON") from exc
    if not isinstance(value, dict):
        raise ProfileTampered("validator trust material must be an object")
    return value


def load_validator_trust_root(path: Path | str | None = None) -> dict[str, bytes]:
    configured = path or os.environ.get(VALIDATOR_TRUST_ROOT_ENV, "").strip()
    if not configured:
        raise IsolationUnavailable("explicit validator receipt trust root required")
    value = _load_trusted_json(configured, private=False)
    if set(value) != {"schema", "keys"} or value.get("schema") != VALIDATOR_TRUST_ROOT_SCHEMA:
        raise ProfileTampered("validator trust root schema/shape is invalid")
    keys = value.get("keys")
    if not isinstance(keys, dict) or not keys:
        raise ProfileTampered("validator trust root has no keys")
    trusted: dict[str, bytes] = {}
    for key_id, encoded in keys.items():
        if not isinstance(key_id, str) or not _KEY_ID_RE.fullmatch(key_id):
            raise ProfileTampered("validator trust root key id is invalid")
        if not isinstance(encoded, str) or not re.fullmatch(r"[0-9a-f]{64}", encoded):
            raise ProfileTampered("validator public key must be 32-byte lowercase hex")
        trusted[key_id] = bytes.fromhex(encoded)
    return trusted


def resolve_validator_signer(
    signing_key: Ed25519PrivateKey | None,
    key_id: str | None,
) -> tuple[Ed25519PrivateKey, str]:
    if signing_key is not None:
        if not isinstance(signing_key, Ed25519PrivateKey):
            raise ProfileTampered("validator signing key must be Ed25519")
        if not isinstance(key_id, str) or not _KEY_ID_RE.fullmatch(key_id):
            raise ProfileTampered("validator signing key id is invalid")
        return signing_key, key_id
    configured = os.environ.get(VALIDATOR_SIGNING_KEY_ENV, "").strip()
    if not configured:
        raise IsolationUnavailable("explicit validator receipt signing key required")
    value = _load_trusted_json(configured, private=True)
    if (
        set(value) != {"schema", "key_id", "private_key"}
        or value.get("schema") != VALIDATOR_PRIVATE_KEY_SCHEMA
    ):
        raise ProfileTampered("validator private key schema/shape is invalid")
    encoded = value.get("private_key")
    loaded_id = value.get("key_id")
    if not isinstance(loaded_id, str) or not _KEY_ID_RE.fullmatch(loaded_id):
        raise ProfileTampered("validator private key id is invalid")
    if not isinstance(encoded, str) or not re.fullmatch(r"[0-9a-f]{64}", encoded):
        raise ProfileTampered("validator private key must be 32-byte lowercase hex")
    try:
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(encoded)), loaded_id
    except ValueError as exc:
        raise ProfileTampered("validator private key is invalid") from exc


def sign_validator_receipt(
    receipt: dict[str, Any],
    *,
    signing_key: Ed25519PrivateKey,
    key_id: str,
    nonce: str,
) -> dict[str, Any]:
    if not _KEY_ID_RE.fullmatch(key_id) or not _NONCE_RE.fullmatch(nonce):
        raise ProfileTampered("validator signer identity or nonce is invalid")
    signed = dict(receipt)
    signed.pop("receipt_sha256", None)
    signed.pop("validator_signature", None)
    public = signing_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    signed["validator_attestation"] = {
        "schema": VALIDATOR_ATTESTATION_SCHEMA,
        "algorithm": "ed25519",
        "key_id": key_id,
        "public_key": public.hex(),
        "nonce": nonce,
    }
    signed["validator_signature"] = signing_key.sign(_canonical_json(signed)).hex()
    return signed


def verify_validator_receipt_signature(
    receipt: dict[str, Any],
    *,
    trusted_public_keys: dict[str, bytes | str] | None = None,
) -> dict[str, Any]:
    attestation = receipt.get("validator_attestation")
    if not isinstance(attestation, dict) or set(attestation) != {
        "schema",
        "algorithm",
        "key_id",
        "public_key",
        "nonce",
    }:
        raise ProfileTampered("validator receipt attestation shape is invalid")
    if (
        attestation.get("schema") != VALIDATOR_ATTESTATION_SCHEMA
        or attestation.get("algorithm") != "ed25519"
        or not isinstance(attestation.get("key_id"), str)
        or not _KEY_ID_RE.fullmatch(attestation["key_id"])
        or not isinstance(attestation.get("nonce"), str)
        or not _NONCE_RE.fullmatch(attestation["nonce"])
    ):
        raise ProfileTampered("validator receipt attestation is invalid")
    declared = attestation.get("public_key")
    signature = receipt.get("validator_signature")
    if not isinstance(declared, str) or not re.fullmatch(r"[0-9a-f]{64}", declared):
        raise ProfileTampered("validator receipt public key is invalid")
    if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{128}", signature):
        raise ProfileTampered("validator receipt signature is invalid")
    trusted = (
        load_validator_trust_root()
        if trusted_public_keys is None
        else trusted_public_keys
    )
    candidate = trusted.get(attestation["key_id"])
    if isinstance(candidate, str):
        if not re.fullmatch(r"[0-9a-f]{64}", candidate):
            raise ProfileTampered("trusted validator public key is invalid")
        candidate = bytes.fromhex(candidate)
    if not isinstance(candidate, bytes) or candidate != bytes.fromhex(declared):
        raise ProfileTampered("validator receipt signer is not trusted")
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    body.pop("validator_signature", None)
    try:
        Ed25519PublicKey.from_public_bytes(candidate).verify(
            bytes.fromhex(signature),
            _canonical_json(body),
        )
    except (InvalidSignature, ValueError) as exc:
        raise ProfileTampered("validator receipt signature verification failed") from exc
    return dict(attestation)


__all__ = [
    "DEFAULT_TEST_COMMAND",
    "ExecutionBoundaryError",
    "ExecutionProfile",
    "IsolationUnavailable",
    "PROFILE_ENV",
    "PROFILE_SCHEMA",
    "ProfileTampered",
    "UnsafeTargetPath",
    "VALIDATOR_ATTESTATION_SCHEMA",
    "VALIDATOR_PRIVATE_KEY_SCHEMA",
    "VALIDATOR_SIGNING_KEY_ENV",
    "VALIDATOR_TRUST_ROOT_ENV",
    "VALIDATOR_TRUST_ROOT_SCHEMA",
    "load_execution_profile",
    "load_validator_trust_root",
    "resolve_execution_profile",
    "resolve_validator_signer",
    "sign_validator_receipt",
    "verify_validator_receipt_signature",
]
