"""Recursive return-address contract for bounded agent work."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

RETURN_ADDRESS_SCHEMA_VERSION = "dharma_return_address.v0"
VALID_RESUME_SURFACES = {
    "agentops_report",
    "wake_receipt",
    "board_card",
    "artifact",
    "a2a_task",
    "a2a_task_queue",
    "a2a_inbox",
    "collaboration_packet",
    "cwt_report",
}
MAX_RETURN_DEPTH = 8


@dataclass(frozen=True)
class ReturnAddressValidation:
    valid: bool
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def build_return_address(
    *,
    resume_surface: str,
    resume_ref: str,
    obligation: str,
    base_case: str,
    depth: int = 0,
    trace_id: str | None = None,
    session_id: str | None = None,
    task_id: str | None = None,
    claim_id: str | None = None,
    run_id: str | None = None,
    parent_run_id: str | None = None,
    agent_uid: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema_version": RETURN_ADDRESS_SCHEMA_VERSION,
        "resume_surface": resume_surface,
        "resume_ref": resume_ref,
        "obligation": obligation,
        "depth": depth,
        "base_case": base_case,
    }
    for key, item in (
        ("trace_id", trace_id),
        ("session_id", session_id),
        ("task_id", task_id),
        ("claim_id", claim_id),
        ("run_id", run_id),
        ("parent_run_id", parent_run_id),
        ("agent_uid", agent_uid),
    ):
        if item:
            value[key] = item
    return value


def validate_return_address(
    value: Any,
    *,
    require_base_case: bool = True,
    strict_surface: bool = False,
) -> ReturnAddressValidation:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(value, dict):
        return ReturnAddressValidation(False, ["return_address must be an object"], warnings)

    schema = value.get("schema_version")
    if schema and schema != RETURN_ADDRESS_SCHEMA_VERSION:
        errors.append(f"return_address schema_version must be {RETURN_ADDRESS_SCHEMA_VERSION}")
    elif not schema:
        warnings.append("return_address schema_version missing")

    for key in ("resume_surface", "resume_ref", "obligation"):
        if not isinstance(value.get(key), str) or not value.get(key, "").strip():
            errors.append(f"return_address.{key} is required")

    if require_base_case and (
        not isinstance(value.get("base_case"), str) or not value.get("base_case", "").strip()
    ):
        errors.append("return_address.base_case is required")

    surface = str(value.get("resume_surface") or "")
    if strict_surface and surface and surface not in VALID_RESUME_SURFACES:
        errors.append(f"unknown return_address.resume_surface: {surface}")
    elif surface and surface not in VALID_RESUME_SURFACES:
        warnings.append(f"nonstandard return_address.resume_surface: {surface}")

    depth = value.get("depth", 0)
    if not isinstance(depth, int):
        errors.append("return_address.depth must be an integer")
    elif depth < 0 or depth > MAX_RETURN_DEPTH:
        errors.append(f"return_address.depth must be between 0 and {MAX_RETURN_DEPTH}")

    return ReturnAddressValidation(not errors, errors, warnings)


def normalize_return_address(
    value: Any,
    *,
    default_resume_surface: str,
    default_resume_ref: str,
    default_obligation: str,
    default_base_case: str,
    trace_id: str | None = None,
) -> dict[str, Any]:
    if isinstance(value, dict):
        normalized = dict(value)
    else:
        normalized = {}
    normalized.setdefault("schema_version", RETURN_ADDRESS_SCHEMA_VERSION)
    normalized.setdefault("resume_surface", default_resume_surface)
    normalized.setdefault("resume_ref", default_resume_ref)
    normalized.setdefault("obligation", default_obligation)
    normalized.setdefault("depth", 0)
    normalized.setdefault("base_case", default_base_case)
    if trace_id:
        normalized.setdefault("trace_id", trace_id)
    validation = validate_return_address(normalized, require_base_case=True)
    if not validation.valid:
        raise ValueError("; ".join(validation.errors))
    return normalized
