"""Versioned, non-authoritative prompt contracts for optional analysis."""

from __future__ import annotations

import copy
from typing import Any


ANOMALY_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema",
        "verdict",
        "confidence",
        "claims",
        "hypotheses",
        "next_safe_action",
        "requires_human",
        "forbidden_effects",
    ],
    "properties": {
        "schema": {"const": "dharma.lab_supervisor.anomaly_analysis.v1"},
        "verdict": {
            "enum": ["anomaly", "no_anomaly", "insufficient_evidence"]
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "claims": {
            "type": "array",
            "maxItems": 20,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["value", "evidence_refs", "modality"],
                "properties": {
                    "value": {"type": "string", "maxLength": 500},
                    "evidence_refs": {
                        "type": "array",
                        "maxItems": 10,
                        "items": {"type": "string", "maxLength": 200},
                    },
                    "modality": {"enum": ["observed", "inferred", "unknown"]},
                },
            },
        },
        "hypotheses": {
            "type": "array",
            "maxItems": 10,
            "items": {"type": "string", "maxLength": 500},
        },
        "next_safe_action": {
            "enum": [
                "inspect",
                "keep_halted",
                "quarantine_provider",
                "rotate_provider",
                "run_bounded_trial",
                "prune_disposable",
                "none",
            ]
        },
        "requires_human": {"type": "boolean"},
        "forbidden_effects": {
            "type": "object",
            "additionalProperties": False,
            "required": ["clear_kill", "merge", "deploy", "expand_budget"],
            "properties": {
                "clear_kill": {"const": False},
                "merge": {"const": False},
                "deploy": {"const": False},
                "expand_budget": {"const": False},
            },
        },
    },
}


def anomaly_prompt(sanitized_evidence: dict[str, Any]) -> str:
    """Render bounded read-only analysis input.

    Callers must remove secrets and raw model/provider payloads before this
    function.  The prompt grants no effect authority and its output is advice,
    never state transition evidence.
    """

    import json

    evidence = json.dumps(sanitized_evidence, sort_keys=True, ensure_ascii=True)
    if len(evidence.encode("utf-8")) > 32_768:
        raise ValueError("sanitized anomaly evidence exceeds 32768 bytes")
    return f"""You are the anomaly-only read-only analyst for two governed research labs.

You may reason only from the SANITIZED_EVIDENCE block below. Do not call tools,
read files, use network access, mutate state, clear or reinterpret KILL/HALT
evidence, merge, deploy, spend tokens beyond this one call, or expand any
budget. A receipt proves only the event it records. Missing or stale evidence
must remain unknown or degraded, never healthy.

Return exactly one JSON object matching schema
`dharma.lab_supervisor.anomaly_analysis.v1`. Every observed claim must cite a
provided evidence reference. Mark unsupported ideas inferred or unknown.
`forbidden_effects` must contain four literal false values.

SANITIZED_EVIDENCE
{evidence}
END_SANITIZED_EVIDENCE
"""


def anomaly_output_schema() -> dict[str, Any]:
    return copy.deepcopy(ANOMALY_OUTPUT_SCHEMA)


def validate_anomaly_output(payload: Any) -> tuple[bool, tuple[str, ...]]:
    """Dependency-free validator for the authority-bearing schema constraints."""

    errors: list[str] = []
    if not isinstance(payload, dict):
        return False, ("output_not_object",)
    allowed = set(ANOMALY_OUTPUT_SCHEMA["properties"])
    if set(payload) - allowed:
        errors.append("unknown_fields")
    if payload.get("schema") != "dharma.lab_supervisor.anomaly_analysis.v1":
        errors.append("schema_mismatch")
    if payload.get("verdict") not in {"anomaly", "no_anomaly", "insufficient_evidence"}:
        errors.append("invalid_verdict")
    confidence = payload.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        errors.append("invalid_confidence")
    elif not 0 <= confidence <= 1:
        errors.append("invalid_confidence")
    if payload.get("next_safe_action") not in {
        "inspect",
        "keep_halted",
        "quarantine_provider",
        "rotate_provider",
        "run_bounded_trial",
        "prune_disposable",
        "none",
    }:
        errors.append("invalid_next_safe_action")
    if not isinstance(payload.get("requires_human"), bool):
        errors.append("requires_human_not_boolean")
    effects = payload.get("forbidden_effects")
    if not isinstance(effects, dict) or effects != {
        "clear_kill": False,
        "merge": False,
        "deploy": False,
        "expand_budget": False,
    }:
        errors.append("forbidden_effect_contract_breached")
    claims = payload.get("claims")
    hypotheses = payload.get("hypotheses")
    if not isinstance(claims, list) or len(claims) > 20:
        errors.append("invalid_claims")
    if not isinstance(hypotheses, list) or len(hypotheses) > 10:
        errors.append("invalid_hypotheses")
    return not errors, tuple(errors)
