"""Shared types and constants for the Operator Brief seam."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REQUIRED_GATES: tuple[str, ...] = (
    "CONSENT",
    "STEELMAN",
    "DOGMA_DRIFT",
)

ARTIFACT_SUBTYPE = "operator_brief"
ARTIFACT_TYPE = "note"
DEFAULT_AGENT_ID = "operator_brief_agent"
DEFAULT_AGENT_NAME = "OperatorBriefAgent"
OPERATOR_BRIEF_CAUSE_ID = "cause:operator_brief_v0"
OPERATOR_BRIEF_CELL_NAME = "Operator Brief v0"
OPERATOR_BRIEF_CELL_KIND = "VentureCell"
RUNTIME_INPUT_LIMIT = 8

ENABLED_ENV = "DHARMA_OPERATOR_BRIEF_ENABLED"


@dataclass
class _BriefInput:
    snapshot_hash: str
    cited_fact_ids: list[str] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)
    source_event_ids: list[str] = field(default_factory=list)
    memory_fact_ids: list[str] = field(default_factory=list)
    source_session_ids: list[str] = field(default_factory=list)
    counterargument: str = ""
    has_source: bool = True

    def is_blank(self) -> bool:
        return not self.summary_lines and not self.cited_fact_ids


@dataclass
class _DraftedBrief:
    title: str
    body_markdown: str
    cited_fact_ids: list[str]
    has_steelman: bool


@dataclass
class _RunResult:
    artifact_id: str | None
    outcome: str
    witness_log_ids: list[str]
    gate_decision_ids: list[str]
    proposal_id: str | None
    runtime_artifact_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "outcome": self.outcome,
            "witness_log_ids": list(self.witness_log_ids),
            "gate_decision_ids": list(self.gate_decision_ids),
            "proposal_id": self.proposal_id,
            "runtime_artifact_id": self.runtime_artifact_id,
        }
