"""Closed request types and public facade for governed patch evidence.

This layer only parses/snapshots evidence. It never runs an oracle, applies a
diff, mints a warrant, or authorizes a repository effect.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Final

from dharma_swarm.foundry.patches import scoped_regular_file

GOVERNED_PATCH_REQUEST_SCHEMA: Final[str] = "dharma.a2a.governed_patch_request.v1"
CANDIDATE_BUNDLE_SCHEMA: Final[str] = (
    "dharma.governed_patch.candidate_no_effect_bundle.v1"
)
NO_EFFECT_RESULT_SCHEMA: Final[str] = "dharma.governed_patch.no_effect_result.v1"
GOVERNED_PATCH_TARGET_ID: Final[str] = "dharma_swarm"
_REQUEST_KEYS = frozenset(
    """schema_version mission_id task_id attempt_id lease_id packet_id
    correlation_id delivery_id proposal_id base_sha executor_agent_uid
    executor_run_id executor_process_boot_id authorized_source_path
    oracle_argv""".split()
)
_BINDING_FIELDS = (
    "mission_id",
    "task_id",
    "attempt_id",
    "lease_id",
    "packet_id",
    "correlation_id",
    "delivery_id",
    "proposal_id",
    "base_sha",
    "executor_agent_uid",
    "executor_run_id",
    "executor_process_boot_id",
)
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@+-]{0,255}$")
_DELIVERY_RE = re.compile(r"^[0-9a-f]{24}$")
_GIT_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_RAW_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_FOUNDRY_SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_MAX_CONTENT_BYTES = 128 * 1024
_MAX_DIFF_BYTES = 2 * 1024 * 1024
MAX_SOURCE_BYTES: Final[int] = 2 * 1024 * 1024
MAX_VERIFIER_EVIDENCE_BYTES: Final[int] = 512 * 1024
_SHELL_EXECUTABLES = frozenset(
    "bash cmd cmd.exe csh dash fish ksh powershell pwsh sh tcsh zsh".split()
)


class GovernedPatchEvidenceError(ValueError):
    """An input or immutable evidence bundle is malformed, stale, or unsafe."""


class NoEffectOutcome(str, Enum):
    """Caller classifications stored without signature-validation authority."""

    CANDIDATE_PRODUCED = "candidate_produced"
    FOUNDRY_REJECTED = "foundry_rejected"
    FOUNDRY_INCONCLUSIVE = "foundry_inconclusive"
    VIBE_REJECTED = "vibe_rejected"
    VIBE_INCONCLUSIVE = "vibe_inconclusive"
    CALLER_ASSERTED_NO_EFFECT = "caller_asserted_no_effect"


@dataclass(frozen=True, slots=True)
class NativePatchBindings:
    """Mission-Control/A2A identity that must match the request exactly."""

    mission_id: str
    task_id: str
    attempt_id: str
    lease_id: str
    packet_id: str
    correlation_id: str
    delivery_id: str
    proposal_id: str
    base_sha: str
    executor_agent_uid: str
    executor_run_id: str
    executor_process_boot_id: str

    def to_dict(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in _BINDING_FIELDS}


@dataclass(frozen=True, slots=True)
class GovernedPatchRequest:
    """Validated request plus exact source and A2A content snapshots."""

    bindings: NativePatchBindings
    authorized_source_path: str
    oracle_argv: tuple[str, ...]
    request_content_sha256: str
    source_sha256: str
    repo_root: Path
    request_bytes: bytes
    source_bytes: bytes


def _raw_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_regular_bounded(
    path: Path,
    *,
    field: str,
    max_bytes: int,
) -> bytes:
    """Read at most ``max_bytes`` through a no-follow regular-file handle."""

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise GovernedPatchEvidenceError(f"{field} is unreadable") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise GovernedPatchEvidenceError(f"{field} is not a regular file")
        if metadata.st_size > max_bytes:
            raise GovernedPatchEvidenceError(f"{field} exceeds the bounded size")
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        if len(data) > max_bytes:
            raise GovernedPatchEvidenceError(f"{field} exceeds the bounded size")
        return data
    finally:
        os.close(descriptor)


def _strict_json_value(value: Any, *, surface: str) -> Any:
    active: set[int] = set()

    def normalize(inner: Any, path: str) -> Any:
        if inner is None or type(inner) in {bool, int}:
            return inner
        if type(inner) is str:
            try:
                inner.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise GovernedPatchEvidenceError(
                    f"{surface} contains invalid Unicode at {path}"
                ) from exc
            return inner
        if type(inner) is float:
            if not math.isfinite(inner):
                raise GovernedPatchEvidenceError(
                    f"{surface} contains a non-finite number at {path}"
                )
            return inner
        if isinstance(inner, Mapping):
            marker = id(inner)
            if marker in active:
                raise GovernedPatchEvidenceError(
                    f"{surface} contains a recursive object at {path}"
                )
            active.add(marker)
            try:
                result: dict[str, Any] = {}
                for key, child in inner.items():
                    if type(key) is not str:
                        raise GovernedPatchEvidenceError(
                            f"{surface} requires string keys at {path}"
                        )
                    if key in result:
                        raise GovernedPatchEvidenceError(
                            f"{surface} contains duplicate key {key!r} at {path}"
                        )
                    result[key] = normalize(child, f"{path}.{key}")
                return result
            finally:
                active.remove(marker)
        if type(inner) in {list, tuple}:
            marker = id(inner)
            if marker in active:
                raise GovernedPatchEvidenceError(
                    f"{surface} contains a recursive array at {path}"
                )
            active.add(marker)
            try:
                return [
                    normalize(child, f"{path}[{i}]") for i, child in enumerate(inner)
                ]
            finally:
                active.remove(marker)
        raise GovernedPatchEvidenceError(
            f"{surface} contains non-JSON value {type(inner).__name__} at {path}"
        )

    return normalize(value, "$")


def _canonical_json_bytes(value: Any, *, surface: str) -> bytes:
    return json.dumps(
        _strict_json_value(value, surface=surface),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _parse_json(raw: str, *, surface: str) -> Any:
    if type(raw) is not str:
        raise GovernedPatchEvidenceError(f"{surface} must be an exact string")
    try:
        encoded = raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise GovernedPatchEvidenceError(f"{surface} is not valid UTF-8") from exc
    if len(encoded) > _MAX_CONTENT_BYTES:
        raise GovernedPatchEvidenceError(f"{surface} exceeds the bounded size")

    def reject_constant(constant: str) -> None:
        raise GovernedPatchEvidenceError(
            f"{surface} contains non-finite JSON constant {constant}"
        )

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, child in pairs:
            if key in result:
                raise GovernedPatchEvidenceError(
                    f"{surface} contains duplicate JSON key {key!r}"
                )
            result[key] = child
        return result

    try:
        value = json.loads(
            raw,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicates,
        )
    except GovernedPatchEvidenceError:
        raise
    except (json.JSONDecodeError, RecursionError, TypeError) as exc:
        raise GovernedPatchEvidenceError(f"{surface} is malformed JSON") from exc
    return _strict_json_value(value, surface=surface)


def _closed_shape(
    payload: Mapping[str, Any], keys: frozenset[str], surface: str
) -> None:
    actual = frozenset(payload)
    if actual == keys:
        return
    missing, extra = sorted(keys - actual), sorted(actual - keys)
    detail = []
    if missing:
        detail.append("missing=" + ",".join(missing))
    if extra:
        detail.append("unexpected=" + ",".join(extra))
    raise GovernedPatchEvidenceError(
        f"{surface} has a non-closed shape: {'; '.join(detail)}"
    )


def _validate_token(value: Any, field: str) -> str:
    if type(value) is not str or _TOKEN_RE.fullmatch(value) is None:
        raise GovernedPatchEvidenceError(f"invalid {field}")
    return value


def _validate_bindings(bindings: NativePatchBindings) -> None:
    if type(bindings) is not NativePatchBindings:
        raise GovernedPatchEvidenceError("native bindings must use NativePatchBindings")
    for field in (
        "mission_id",
        "task_id",
        "attempt_id",
        "packet_id",
        "proposal_id",
        "executor_agent_uid",
        "executor_run_id",
        "executor_process_boot_id",
    ):
        _validate_token(getattr(bindings, field), field)
    if type(bindings.lease_id) is not str or not _DELIVERY_RE.fullmatch(
        bindings.lease_id
    ):
        raise GovernedPatchEvidenceError("invalid lease_id")
    if type(bindings.delivery_id) is not str or not _DELIVERY_RE.fullmatch(
        bindings.delivery_id
    ):
        raise GovernedPatchEvidenceError("invalid delivery_id")
    if bindings.attempt_id != bindings.packet_id:
        raise GovernedPatchEvidenceError("attempt_id must equal packet_id")
    if bindings.lease_id != bindings.delivery_id:
        raise GovernedPatchEvidenceError("lease_id must equal delivery_id")
    if bindings.correlation_id != (
        f"a2a_send:{bindings.executor_agent_uid}:{bindings.packet_id}"
    ):
        raise GovernedPatchEvidenceError(
            "correlation_id must bind executor_agent_uid and packet_id"
        )
    if type(bindings.base_sha) is not str or not _GIT_SHA_RE.fullmatch(
        bindings.base_sha
    ):
        raise GovernedPatchEvidenceError("invalid base_sha")


def _bindings_from_payload(payload: Mapping[str, Any]) -> NativePatchBindings:
    bindings = NativePatchBindings(
        **{field: payload.get(field) for field in _BINDING_FIELDS}
    )
    _validate_bindings(bindings)
    return bindings


def _validate_source_path(value: Any) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise GovernedPatchEvidenceError("invalid authorized_source_path")
    path = PurePosixPath(value)
    if (
        value.startswith("/")
        or "\\" in value
        or "\x00" in value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise GovernedPatchEvidenceError("unsafe authorized_source_path")
    return path.as_posix()


def _validate_oracle_argv(value: Any) -> tuple[str, ...]:
    if type(value) is not list or not 1 <= len(value) <= 64:
        raise GovernedPatchEvidenceError("oracle_argv must be a bounded JSON argv")
    argv: list[str] = []
    total = 0
    for item in value:
        if (
            type(item) is not str
            or not item
            or len(item) > 4096
            or any(character in item for character in ("\x00", "\r", "\n"))
        ):
            raise GovernedPatchEvidenceError("oracle_argv contains an unsafe argument")
        total += len(item.encode("utf-8"))
        argv.append(item)
    if total > 16 * 1024:
        raise GovernedPatchEvidenceError("oracle_argv exceeds the bounded size")
    if os.path.basename(argv[0]).lower() in _SHELL_EXECUTABLES:
        raise GovernedPatchEvidenceError("oracle_argv may not invoke a shell")
    return tuple(argv)


def parse_governed_patch_request(
    content: str,
    *,
    repo_root: Path,
    expected: NativePatchBindings,
    accepted_base_sha: str,
    expected_content_sha256: str | None = None,
) -> GovernedPatchRequest:
    """Parse and bind one closed A2A content object without executing anything."""

    payload = _parse_json(content, surface="governed patch request")
    if type(payload) is not dict:
        raise GovernedPatchEvidenceError("governed patch request must be a JSON object")
    _closed_shape(payload, _REQUEST_KEYS, "governed patch request")
    if payload["schema_version"] != GOVERNED_PATCH_REQUEST_SCHEMA:
        raise GovernedPatchEvidenceError("unsupported governed patch request schema")
    bindings = _bindings_from_payload(payload)
    _validate_bindings(expected)
    if bindings != expected:
        raise GovernedPatchEvidenceError(
            "request native bindings do not match observation"
        )
    if (
        type(accepted_base_sha) is not str
        or not _GIT_SHA_RE.fullmatch(accepted_base_sha)
        or bindings.base_sha != accepted_base_sha
    ):
        raise GovernedPatchEvidenceError(
            "request base_sha does not match accepted base"
        )
    request_bytes = content.encode("utf-8")
    request_sha = _raw_sha256(request_bytes)
    if expected_content_sha256 is not None and (
        type(expected_content_sha256) is not str
        or not _RAW_SHA_RE.fullmatch(expected_content_sha256)
        or request_sha != expected_content_sha256
    ):
        raise GovernedPatchEvidenceError("A2A content sha256 mismatch")
    source_path = _validate_source_path(payload["authorized_source_path"])
    argv = _validate_oracle_argv(payload["oracle_argv"])
    try:
        repo = Path(repo_root).resolve(strict=True)
    except OSError as exc:
        raise GovernedPatchEvidenceError(
            "canonical repository root is unavailable"
        ) from exc
    if not repo.is_dir():
        raise GovernedPatchEvidenceError("canonical repository root is not a directory")
    source = scoped_regular_file(
        repo,
        source_path,
        field="authorized source",
        error_type=GovernedPatchEvidenceError,
    )
    source_bytes = _read_regular_bounded(
        source,
        field="authorized source",
        max_bytes=MAX_SOURCE_BYTES,
    )
    try:
        source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GovernedPatchEvidenceError(
            "authorized source is not strict UTF-8"
        ) from exc
    return GovernedPatchRequest(
        bindings,
        source_path,
        argv,
        request_sha,
        _raw_sha256(source_bytes),
        repo,
        request_bytes,
        source_bytes,
    )


# Lazy facade imports keep the three modules acyclic.
def build_candidate_bundle(*args: Any, **kwargs: Any) -> Any:
    from dharma_swarm.governed_patch_candidate_bundle import (
        build_candidate_bundle as impl,
    )

    return impl(*args, **kwargs)


def load_candidate_bundle(*args: Any, **kwargs: Any) -> Any:
    from dharma_swarm.governed_patch_candidate_bundle import (
        load_candidate_bundle as impl,
    )

    return impl(*args, **kwargs)


def verify_candidate_bundle(*args: Any, **kwargs: Any) -> Any:
    from dharma_swarm.governed_patch_candidate_bundle import (
        verify_candidate_bundle as impl,
    )

    return impl(*args, **kwargs)


def record_no_effect_result(*args: Any, **kwargs: Any) -> Any:
    from dharma_swarm.governed_patch_no_effect import record_no_effect_result as impl

    return impl(*args, **kwargs)


def verify_no_effect_bundle(*args: Any, **kwargs: Any) -> Any:
    from dharma_swarm.governed_patch_no_effect import verify_no_effect_bundle as impl

    return impl(*args, **kwargs)


__all__ = [
    "CANDIDATE_BUNDLE_SCHEMA",
    "GOVERNED_PATCH_REQUEST_SCHEMA",
    "NO_EFFECT_RESULT_SCHEMA",
    "GovernedPatchEvidenceError",
    "GovernedPatchRequest",
    "NativePatchBindings",
    "NoEffectOutcome",
    "build_candidate_bundle",
    "load_candidate_bundle",
    "parse_governed_patch_request",
    "record_no_effect_result",
    "verify_candidate_bundle",
    "verify_no_effect_bundle",
]
