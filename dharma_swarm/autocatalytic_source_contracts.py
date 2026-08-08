"""Typed, content-addressed source contracts for project adapters."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from dharma_swarm.autocatalytic_contract_primitives import (
    SemanticPromotionError,
    _nested_value,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise SemanticPromotionError(f"duplicate JSON key {key!r}")
        value[key] = item
    return value


def _json_object(relative_path: str) -> dict[str, Any] | None:
    """Load an object without JSON's unsafe last-key-wins behaviour."""
    path = _REPO_ROOT / relative_path
    if not path.is_file():
        return None
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SemanticPromotionError(
            f"invalid project source JSON {relative_path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SemanticPromotionError(
            f"invalid project source JSON {relative_path}: expected object"
        )
    return value


def _declared_source_digest(payload: Mapping[str, Any]) -> str:
    """Reproduce governance receipt hashing (escaped Unicode by design)."""
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_snapshot(
    relative_path: str,
    *,
    kind: str = "structured_json",
    expected_schema: str | None = None,
    schema_field: str = "schema",
    required_types: Mapping[str, type | tuple[type, ...]] | None = None,
    require_digest: bool = False,
    optional: bool = False,
    row_schema: str | None = None,
    row_required_types: Mapping[str, type | tuple[type, ...]] | None = None,
    fact_paths: Sequence[str] = (),
) -> dict[str, Any]:
    """Validate and content-address one explicitly typed project source."""
    path = _REPO_ROOT / relative_path
    if not path.is_file():
        if not optional:
            raise SemanticPromotionError(
                f"required project source missing: {relative_path}"
            )
        return {
            "path": relative_path,
            "source_kind": kind,
            "present": False,
            "valid": True,
            "status": "optional_absent",
            "sha256": None,
            "size_bytes": 0,
            "schema": None,
            "generated_at": None,
            "declared_digest_valid": None,
            "facts": {},
        }
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise SemanticPromotionError(
            f"invalid project source {relative_path}: not readable UTF-8"
        ) from exc
    if not text.strip():
        raise SemanticPromotionError(f"invalid project source {relative_path}: empty")
    base: dict[str, Any] = {
        "path": relative_path,
        "source_kind": kind,
        "present": True,
        "valid": True,
        "status": "validated",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "schema": None,
        "generated_at": None,
        "declared_digest_valid": None,
        "facts": {},
    }
    if kind in {"raw_utf8_text", "raw_utf8_markdown"}:
        return base

    def _require_fields(
        value: Mapping[str, Any],
        fields: Mapping[str, type | tuple[type, ...]],
        label: str,
    ) -> None:
        for dotted, expected in fields.items():
            observed = _nested_value(value, dotted)
            accepted = expected if isinstance(expected, tuple) else (expected,)
            if type(observed) not in accepted or (
                type(observed) is str and not observed.strip()
            ):
                names = "/".join(item.__name__ for item in accepted)
                raise SemanticPromotionError(
                    f"invalid project source {relative_path}: {label} field "
                    f"{dotted!r} must be {names}"
                )

    if kind == "jsonl":
        rows: list[dict[str, Any]] = []
        for index, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line, object_pairs_hook=_reject_duplicate_keys)
            except json.JSONDecodeError as exc:
                raise SemanticPromotionError(
                    f"invalid project source JSONL {relative_path} row {index}: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise SemanticPromotionError(
                    f"invalid project source JSONL {relative_path} row {index}: "
                    "object required"
                )
            if row_schema is not None and row.get("schema") != row_schema:
                raise SemanticPromotionError(
                    f"invalid project source JSONL {relative_path} row {index}: "
                    "wrong schema"
                )
            _require_fields(row, row_required_types or {}, f"row {index}")
            rows.append(row)
        if not rows:
            raise SemanticPromotionError(
                f"invalid project source JSONL {relative_path}: no rows"
            )
        return {**base, "schema": row_schema, "row_count": len(rows)}
    if kind != "structured_json":
        raise SemanticPromotionError(f"unknown project source kind: {kind}")
    value = _json_object(relative_path)
    if value is None:
        raise SemanticPromotionError(
            f"required project source missing: {relative_path}"
        )
    if expected_schema is not None and value.get(schema_field) != expected_schema:
        raise SemanticPromotionError(
            f"invalid project source {relative_path}: expected {schema_field} "
            f"{expected_schema!r}"
        )
    _require_fields(value, required_types or {}, "object")
    digest_valid: bool | None = None
    if require_digest:
        if not isinstance(value.get("digest"), str):
            raise SemanticPromotionError(
                f"invalid project source {relative_path}: required digest missing"
            )
        unsigned = {key: item for key, item in value.items() if key != "digest"}
        digest_valid = value["digest"] == _declared_source_digest(unsigned)
        if not digest_valid:
            raise SemanticPromotionError(
                f"invalid project source {relative_path}: digest mismatch"
            )
    return {
        **base,
        "schema": value.get(schema_field),
        "generated_at": value.get("generated_at") or value.get("observed_at"),
        "declared_digest_valid": digest_valid,
        "facts": {fact: _nested_value(value, fact) for fact in fact_paths},
    }
