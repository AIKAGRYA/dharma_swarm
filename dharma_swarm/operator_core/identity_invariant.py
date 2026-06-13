"""Stable identity invariant digests for registered agents."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

IDENTITY_INVARIANT_SCHEMA_VERSION = "dharma_identity_invariant.v1"


def canonical_serial(agent_uid: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", str(agent_uid or "agent")).strip("_")
    return f"AGT-{(safe or 'AGENT').upper()}"


def identity_invariant_payload(
    *,
    agent_uid: str,
    authority_floor: str,
    memory_namespace: str,
    trace_identity: str,
    serial: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": IDENTITY_INVARIANT_SCHEMA_VERSION,
        "agent_uid": agent_uid,
        "authority_floor": authority_floor,
        "memory_namespace": memory_namespace,
        "trace_identity": trace_identity,
        "serial": serial or canonical_serial(agent_uid),
        "created_at": created_at or "",
    }


def identity_invariant_digest(payload: dict[str, Any]) -> str:
    stable = {key: value for key, value in payload.items() if key != "digest"}
    encoded = json.dumps(stable, ensure_ascii=True, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_identity_invariant(
    *,
    agent_uid: str,
    authority_floor: str,
    memory_namespace: str,
    trace_identity: str,
    serial: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    payload = identity_invariant_payload(
        agent_uid=agent_uid,
        authority_floor=authority_floor,
        memory_namespace=memory_namespace,
        trace_identity=trace_identity,
        serial=serial,
        created_at=created_at,
    )
    payload["digest"] = identity_invariant_digest(payload)
    return payload


def validate_identity_invariant(value: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return {"valid": False, "errors": ["identity_invariant must be an object"]}
    for key in (
        "schema_version",
        "agent_uid",
        "authority_floor",
        "memory_namespace",
        "trace_identity",
        "serial",
        "digest",
    ):
        if not value.get(key):
            errors.append(f"missing identity_invariant.{key}")
    if value.get("schema_version") and value.get("schema_version") != IDENTITY_INVARIANT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {IDENTITY_INVARIANT_SCHEMA_VERSION}")
    if value.get("digest") and value.get("digest") != identity_invariant_digest(value):
        errors.append("identity_invariant.digest mismatch")
    return {"valid": not errors, "errors": errors}
