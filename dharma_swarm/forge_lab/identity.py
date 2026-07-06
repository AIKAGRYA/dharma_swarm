"""Candidate identity helpers for Forge Lab.

The intended canonicalizer is telos-kernel JCS.  The main dharma_swarm test
path does not currently put ``packages/telos-kernel`` on ``PYTHONPATH``, so this
module uses telos when importable and records a deterministic fallback name when
it is not.  Receipts include the canonicalizer so this temporary packaging gap
does not become invisible.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return repr(value)


def canonical_bytes(value: Any) -> tuple[bytes, str]:
    """Return deterministic bytes plus the canonicalizer name."""

    safe_value = _json_safe(value)
    try:
        from telos_kernel.canonical import canonicalize  # type: ignore

        return canonicalize(safe_value), "telos_kernel.jcs"
    except Exception:  # noqa: BLE001 - explicit fallback recorded in receipts.
        payload = json.dumps(
            safe_value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return payload, "json.sort_keys.fallback"


def canonical_sha256(value: Any) -> tuple[str, str]:
    payload, canonicalizer = canonical_bytes(value)
    return hashlib.sha256(payload).hexdigest(), canonicalizer


def candidate_id_for_genome(genome: dict[str, Any]) -> tuple[str, str]:
    digest, canonicalizer = canonical_sha256(genome)
    return f"cand_{digest[:24]}", canonicalizer
