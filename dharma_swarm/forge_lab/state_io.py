"""Small, anchored filesystem primitives for the RSI operator surface.

This is not a second state store.  It gives the versioned CLI one way to find
the host-owned ``DHARMA_HOME`` anchor and to read/write the JSON artifacts
already required by the Forge Lab specification.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from dharma_swarm.daemon_config import dharma_state_dir

DIGEST_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


def now_utc() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def dharma_home() -> Path:
    """Return the stable host state anchor, never the source checkout.

    The default branch delegates to the canonical state-dir owner
    (``dharma_swarm.daemon_config.dharma_state_dir``) so ``~/.dharma``
    ownership stays centralized (ANTI_SLOP_RULES Rule 1).
    """

    explicit = os.environ.get("DHARMA_HOME", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve(strict=False)
    state = os.environ.get("RSI_LAB_STATE", "").strip()
    if state:
        return (Path(state).expanduser() / ".dharma").resolve(strict=False)
    return dharma_state_dir().resolve(strict=False)


def forge_state_root() -> Path:
    return dharma_home() / "forge_lab"


def provider_selftest_root() -> Path:
    """Return the single receipt root used by writers and every reader.

    An explicit override is useful for isolated tests, but the production
    launcher pins it below the stable ``RSI_LAB_STATE`` anchor.  Keeping this
    resolver here prevents a successful refresher from writing evidence that
    ``doctor`` cannot observe.
    """

    explicit = os.environ.get("RSI_LAB_PROVIDER_SELFTEST_ROOT", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve(strict=False)
    return forge_state_root() / "provider_selftests"


def canonical_json(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def content_digest(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def validate_digest(value: str) -> str:
    if not DIGEST_RE.fullmatch(str(value or "")):
        raise ValueError("digest must be sha256 followed by 64 lowercase hex characters")
    return value


def validate_safe_id(value: str, *, field: str = "id") -> str:
    if not SAFE_ID_RE.fullmatch(str(value or "")):
        raise ValueError(f"{field} must contain 1-96 safe characters")
    return value


def safe_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def atomic_json(path: Path, payload: dict[str, Any], *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid4().hex[:8]}")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json_exclusive(
    path: Path,
    payload: dict[str, Any],
    *,
    mode: int = 0o600,
) -> None:
    """Create one immutable JSON receipt, refusing an existing path.

    ``atomic_json`` is appropriate for mutable operator projections. Evidence
    receipts are different: replacing a prior observation, even atomically,
    destroys history. ``O_EXCL`` makes that distinction an operating-system
    invariant rather than a caller convention.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        # If serialization or fsync fails, a partial path must never masquerade
        # as a durable receipt. The caller still receives the original error.
        path.unlink(missing_ok=True)
        raise


def append_jsonl(path: Path, payload: dict[str, Any], *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, mode)
    with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
        handle.write(canonical_json(payload).decode("utf-8") + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines: Iterable[str] = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return rows
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


__all__ = [
    "DIGEST_RE",
    "append_jsonl",
    "atomic_json",
    "canonical_json",
    "content_digest",
    "dharma_home",
    "forge_state_root",
    "now_utc",
    "read_jsonl",
    "safe_json",
    "validate_digest",
    "validate_safe_id",
    "write_json_exclusive",
]
