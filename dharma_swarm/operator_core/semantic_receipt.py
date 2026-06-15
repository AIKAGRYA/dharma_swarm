"""SemanticReceipt v1 validation for model-authored critique artifacts.

SemanticReceipt is a typed semantic layer over the existing receipt spine. It
does not create a new authority store: JSON artifacts remain filesystem
receipts and BoardStore/control-surface adapters project them read-only.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

SCHEMA_VERSION = "dharma.semantic_receipt.v1"
SEMANTIC_ATTR_PREFIX = "dharma.semantic."

VALID_VERDICTS = {
    "pass",
    "approve",
    "revise",
    "reject",
    "blocked",
    "failed",
    "insufficient_context",
}

PASSING_VERDICTS = {"pass", "approve"}
FAILURE_VERDICTS = {"blocked", "failed"}

VALID_FAILURE_TYPES = {
    "",
    "provider_unavailable",
    "provider_unreachable",
    "provider_failed",
    "provider_quota_blocked",
    "provider_auth_failed",
    "provider_timeout",
    "empty_response",
    "schema_validation_failed",
    "json_parse_failed",
    "internal_error",
}

REQUIRED_FIELDS = (
    "schema_version",
    "receipt_id",
    "created_at",
    "agent_uid",
    "critic_agent_id",
    "model_identity",
    "authored_by_model",
    "review_target",
    "intent_ack",
    "capability_match",
    "understood_request",
    "missing_context",
    "verdict",
    "summary",
    "recommendations",
    "acceptance_gates",
    "explicit_disagreement",
    "evidence_refs",
    "confidence",
    "not_claimed_agents",
    "failure_type",
    "failure_reason",
    "correlation_id",
    "reply_to",
    "model_call_latency_ms",
)


class SemanticReceiptValidationError(ValueError):
    """Raised when a SemanticReceipt payload does not satisfy v1 rules."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def utc_now_iso() -> str:
    """Return UTC time in the repo's receipt-friendly ISO form."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_number_0_1(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and 0.0 <= float(value) <= 1.0


def _list_of_strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _list_of_objects(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, Mapping) for item in value)


def normalize_semantic_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep-copied receipt with all v1 fields present.

    Missing optional failure fields are filled so downstream adapters can treat
    every artifact uniformly. This function does not prove semantic truth; call
    ``semantic_reply_claim_from_validation`` after validation for that.
    """
    receipt = deepcopy(dict(payload))
    for key in REQUIRED_FIELDS:
        receipt.setdefault(key, "" if key not in {"model_identity"} else {})
    receipt.setdefault("semantic_reply_claim", False)
    receipt.setdefault("peer_model_processed_claim", False)
    receipt.setdefault("raw_response_sha256", "")
    receipt.setdefault("prompt_sha256", "")
    return receipt


def validate_semantic_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a SemanticReceipt v1 payload.

    Provider failures are valid artifacts when they use a failure verdict and a
    typed ``failure_type``. Successful semantic claims additionally require
    ``authored_by_model=true`` and a provider/model identity.
    """
    receipt = normalize_semantic_receipt(payload)
    errors: list[str] = []

    if receipt.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")

    for key in ("receipt_id", "created_at", "agent_uid", "critic_agent_id", "review_target"):
        if not _is_non_empty_string(receipt.get(key)):
            errors.append(f"{key} must be a non-empty string")

    model_identity = receipt.get("model_identity")
    if not isinstance(model_identity, Mapping):
        errors.append("model_identity must be an object")
    else:
        if not _is_non_empty_string(model_identity.get("provider")):
            errors.append("model_identity.provider must be a non-empty string")
        if not _is_non_empty_string(model_identity.get("model")):
            errors.append("model_identity.model must be a non-empty string")

    for key in ("authored_by_model", "intent_ack", "understood_request"):
        if not isinstance(receipt.get(key), bool):
            errors.append(f"{key} must be a boolean")

    for key in ("capability_match", "confidence"):
        if not _is_number_0_1(receipt.get(key)):
            errors.append(f"{key} must be a number between 0 and 1")
        else:
            receipt[key] = float(receipt[key])

    if not _list_of_strings(receipt.get("missing_context")):
        errors.append("missing_context must be a list of strings")
    if not _list_of_objects(receipt.get("recommendations")):
        errors.append("recommendations must be a list of objects")
    if not _list_of_objects(receipt.get("acceptance_gates")):
        errors.append("acceptance_gates must be a list of objects")
    if not _list_of_strings(receipt.get("evidence_refs")):
        errors.append("evidence_refs must be a list of strings")
    if not _list_of_strings(receipt.get("not_claimed_agents")) or not receipt.get("not_claimed_agents"):
        errors.append("not_claimed_agents must be a non-empty list of strings")

    verdict = str(receipt.get("verdict") or "").strip()
    if verdict not in VALID_VERDICTS:
        errors.append(f"verdict must be one of {sorted(VALID_VERDICTS)}")
    else:
        receipt["verdict"] = verdict

    if not _is_non_empty_string(receipt.get("summary")):
        errors.append("summary must be a non-empty string")

    failure_type = str(receipt.get("failure_type") or "").strip()
    receipt["failure_type"] = failure_type
    if failure_type not in VALID_FAILURE_TYPES:
        errors.append(f"failure_type must be one of {sorted(VALID_FAILURE_TYPES)}")

    failure_reason = str(receipt.get("failure_reason") or "")
    if failure_type and verdict not in FAILURE_VERDICTS:
        errors.append("failure_type requires verdict blocked or failed")
    if failure_type and not failure_reason.strip():
        errors.append("failure_reason is required when failure_type is set")

    if not bool(receipt.get("authored_by_model")) and not failure_type:
        errors.append("authored_by_model must be true unless this is a typed failure artifact")

    disagreement = receipt.get("explicit_disagreement")
    if verdict not in PASSING_VERDICTS and not _is_non_empty_string(disagreement):
        errors.append("explicit_disagreement is required when verdict is not pass/approve")

    latency = receipt.get("model_call_latency_ms")
    if not isinstance(latency, int | float) or isinstance(latency, bool) or float(latency) < 0:
        errors.append("model_call_latency_ms must be a non-negative number")
    else:
        receipt["model_call_latency_ms"] = int(float(latency))

    if errors:
        raise SemanticReceiptValidationError(errors)

    semantic_claim = semantic_reply_claim_from_validation(receipt)
    receipt["semantic_reply_claim"] = semantic_claim
    receipt["peer_model_processed_claim"] = semantic_claim
    receipt["semantic_claim_basis"] = (
        "validated_non_codex_model_artifact" if semantic_claim else "typed_failure_or_non_model_artifact"
    )
    return receipt


def semantic_reply_claim_from_validation(receipt: Mapping[str, Any]) -> bool:
    """Return true only for validated, model-authored semantic artifacts."""
    return bool(receipt.get("authored_by_model")) and not str(receipt.get("failure_type") or "").strip()


def semantic_attributes(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Project SemanticReceipt fields into EvidenceReceipt attribute keys."""
    normalized = normalize_semantic_receipt(receipt)
    attrs = {
        "schema_version": normalized["schema_version"],
        "authored_by_model": bool(normalized["authored_by_model"]),
        "model_identity.provider": normalized.get("model_identity", {}).get("provider", ""),
        "model_identity.model": normalized.get("model_identity", {}).get("model", ""),
        "review_target": normalized["review_target"],
        "intent_ack": bool(normalized["intent_ack"]),
        "capability_match": normalized["capability_match"],
        "understood_request": bool(normalized["understood_request"]),
        "missing_context": list(normalized["missing_context"]),
        "verdict": normalized["verdict"],
        "summary": normalized["summary"],
        "recommendations": list(normalized["recommendations"]),
        "acceptance_gates": list(normalized["acceptance_gates"]),
        "explicit_disagreement": normalized["explicit_disagreement"],
        "confidence": normalized["confidence"],
        "not_claimed_agents": list(normalized["not_claimed_agents"]),
        "failure_type": normalized["failure_type"],
        "failure_reason": normalized["failure_reason"],
        "correlation_id": normalized["correlation_id"],
    }
    return {f"{SEMANTIC_ATTR_PREFIX}{key}": value for key, value in attrs.items()}


def semantic_receipt_json_schema() -> dict[str, Any]:
    """Return a compact JSON Schema for model prompting and docs."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Dharma SemanticReceipt v1",
        "type": "object",
        "additionalProperties": True,
        "required": list(REQUIRED_FIELDS),
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "receipt_id": {"type": "string", "minLength": 1},
            "created_at": {"type": "string", "minLength": 1},
            "agent_uid": {"type": "string", "minLength": 1},
            "critic_agent_id": {"type": "string", "minLength": 1},
            "model_identity": {
                "type": "object",
                "required": ["provider", "model"],
                "properties": {
                    "provider": {"type": "string", "minLength": 1},
                    "model": {"type": "string", "minLength": 1},
                },
            },
            "authored_by_model": {"type": "boolean"},
            "review_target": {"type": "string", "minLength": 1},
            "intent_ack": {"type": "boolean"},
            "capability_match": {"type": "number", "minimum": 0, "maximum": 1},
            "understood_request": {"type": "boolean"},
            "missing_context": {"type": "array", "items": {"type": "string"}},
            "verdict": {"type": "string", "enum": sorted(VALID_VERDICTS)},
            "summary": {"type": "string", "minLength": 1},
            "recommendations": {"type": "array", "items": {"type": "object"}},
            "acceptance_gates": {"type": "array", "items": {"type": "object"}},
            "explicit_disagreement": {"type": "string"},
            "evidence_refs": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "not_claimed_agents": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "failure_type": {"type": "string", "enum": sorted(VALID_FAILURE_TYPES)},
            "failure_reason": {"type": "string"},
            "correlation_id": {"type": "string"},
            "reply_to": {"type": "string"},
            "model_call_latency_ms": {"type": "number", "minimum": 0},
        },
    }
