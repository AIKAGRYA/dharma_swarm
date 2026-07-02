"""Schemas for Dharma Semantic Receipt Graph v0 and model output v0."""

from __future__ import annotations

from typing import Any

GRAPH_SCHEMA_VERSION = "dharma.semantic_receipt_graph.v0"
MODEL_OUTPUT_SCHEMA_VERSION = "dharma.verifier_ranker_output.v0"

GRAPH_RECORD_TYPES = [
    "agent_event",
    "provider_attempt",
    "routing_decision",
    "semantic_receipt",
    "verifier_outcome",
    "artifact_ref",
    "claim_evidence",
    "a2a_delivery",
    "eval_result",
    "human_or_council_label",
]

PRIVACY_TAGS = [
    "public",
    "internal_redacted",
    "internal_hash_only",
    "private_metadata",
    "quarantine_sensitive",
    "excluded_raw_secret",
    "excluded_raw_message",
    "excluded_provider_payload",
]

LABEL_TAXONOMY = [
    "valid_receipt",
    "unsupported_claim",
    "weak_completion",
    "bad_route",
    "privacy_violation",
    "good_next_action",
    "needs_external_verification",
    "real_completion",
]

COMMON_PROPERTIES: dict[str, Any] = {
    "schema_version": {"const": GRAPH_SCHEMA_VERSION},
    "record_type": {"enum": GRAPH_RECORD_TYPES},
    "record_id": {"type": "string", "minLength": 12},
    "source_ref": {"type": "string", "minLength": 1},
    "source_hash": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
    "content_hash": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
    "created_at": {"type": "string", "minLength": 1},
    "observed_at": {"type": "string"},
    "provenance": {
        "type": "object",
        "required": ["collector", "collector_version", "extraction_mode"],
        "properties": {
            "collector": {"type": "string"},
            "collector_version": {"type": "string"},
            "extraction_mode": {"enum": ["metadata_only", "redacted_content", "hash_only"]},
            "upstream_schema": {"type": "string"},
            "upstream_record_id": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "privacy_tags": {
        "type": "array",
        "items": {"enum": PRIVACY_TAGS},
        "minItems": 1,
    },
    "evidence_refs": {"type": "array", "items": {"type": "string"}},
    "label_fields": {
        "type": "object",
        "properties": {
            "weak_labels": {"type": "array", "items": {"type": "string"}},
            "gold_labels": {"type": "array", "items": {"enum": LABEL_TAXONOMY}},
            "label_source": {"type": "string"},
            "labeler_id_hash": {"type": "string"},
            "adjudication_state": {
                "enum": ["unlabeled", "single_label", "needs_adjudication", "adjudicated"]
            },
        },
        "additionalProperties": True,
    },
    "payload": {"type": "object", "additionalProperties": True},
}

SEMANTIC_RECEIPT_GRAPH_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://dharma.local/schemas/dharma_semantic_receipt_graph_v0.schema.json",
    "title": "Dharma Semantic Receipt Graph v0",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "record_type",
        "record_id",
        "source_ref",
        "source_hash",
        "content_hash",
        "created_at",
        "provenance",
        "privacy_tags",
        "evidence_refs",
        "label_fields",
        "payload",
    ],
    "properties": COMMON_PROPERTIES,
    "allOf": [
        {
            "if": {"properties": {"record_type": {"const": "provider_attempt"}}},
            "then": {
                "properties": {
                    "payload": {
                        "type": "object",
                        "required": ["provider", "model", "success", "outcome", "duration_ms"],
                    }
                }
            },
        },
        {
            "if": {"properties": {"record_type": {"const": "routing_decision"}}},
            "then": {
                "properties": {
                    "payload": {
                        "type": "object",
                        "required": ["decision_id", "route_path", "selected_provider", "confidence"],
                    }
                }
            },
        },
        {
            "if": {"properties": {"record_type": {"const": "verifier_outcome"}}},
            "then": {
                "properties": {
                    "payload": {
                        "type": "object",
                        "required": ["verdict", "score", "gate_failures", "missing_evidence"],
                    }
                }
            },
        },
        {
            "if": {"properties": {"record_type": {"const": "human_or_council_label"}}},
            "then": {
                "properties": {
                    "label_fields": {
                        "type": "object",
                        "required": ["gold_labels", "label_source", "adjudication_state"],
                    }
                }
            },
        },
    ],
}

MODEL_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://dharma.local/schemas/dharma_verifier_ranker_output_v0.schema.json",
    "title": "DharmaVerifier-Ranker v0 Output",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "verdict",
        "quality_score",
        "evidence_sufficiency",
        "claim_integrity_risk",
        "privacy_risk",
        "route_risk",
        "gate_failures",
        "missing_evidence",
        "next_required_action",
        "confidence",
        "rationale_refs",
    ],
    "properties": {
        "verdict": {
            "enum": ["approve", "revise", "block", "escalate", "insufficient_context"]
        },
        "quality_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "evidence_sufficiency": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "claim_integrity_risk": {"enum": ["low", "medium", "high"]},
        "privacy_risk": {"enum": ["low", "medium", "high"]},
        "route_risk": {"enum": ["low", "medium", "high"]},
        "gate_failures": {"type": "array", "items": {"type": "string"}},
        "missing_evidence": {"type": "array", "items": {"type": "string"}},
        "next_required_action": {"type": "string", "minLength": 1},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "rationale_refs": {"type": "array", "items": {"type": "string"}},
    },
}
