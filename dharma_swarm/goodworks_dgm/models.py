"""Models for the Goodworks DGM control surface."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\b[A-Za-z0-9_-]{24,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}"),
    re.compile(r"BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY"),
    re.compile(r"(?:OPENAI|ANTHROPIC|GOOGLE|GEMINI|XAI|MINIMAX|ZAI)_API_KEY\s*=", re.I),
)


def reject_secret_text(value: Any) -> None:
    """Raise when a request body appears to contain credential material."""
    text = str(value)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise ValueError("goal payload appears to contain secret material")


class GoalDomain(str, Enum):
    GOODWORKS_MRV = "goodworks_mrv"
    REPO_QUALITY = "repo_quality"
    WIKI_CONTEXT = "wiki_context"


class MutationMode(str, Enum):
    DRY_RUN = "dry_run"
    SHADOW = "shadow"


class GoalRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    BLOCKED = "blocked"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class GoalSpec(BaseModel):
    """Operator goal accepted by the Goodworks DGM loop.

    V1 deliberately allows only dry-run and shadow execution. Live mutation
    remains behind the existing DGM autonomy gates, outside this API.
    """

    goal_id: str = Field(default_factory=lambda: new_id("goal"))
    title: str
    objective: str
    domain: GoalDomain = GoalDomain.GOODWORKS_MRV
    success_metric: str = "increase_verified_restorative_flow_without_invalidating_ledger"
    data_sources: list[str] = Field(
        default_factory=lambda: [
            "ai_reciprocity_ledger",
            "gaia_ledger",
            "gaia_platform",
        ]
    )
    mutation_mode: MutationMode = MutationMode.DRY_RUN
    risk_level: str = "Q2"
    budget_iterations: int = Field(default=1, ge=1, le=5)
    created_by: str = "operator"
    created_at: str = Field(default_factory=utc_now_iso)
    operator_note: str = ""

    @model_validator(mode="after")
    def no_secrets(self) -> "GoalSpec":
        reject_secret_text(self.model_dump(mode="json"))
        return self


class GoodworksMetricSnapshot(BaseModel):
    """Current measurable substrate for Goodworks MRV goals."""

    reciprocity_chain_valid: bool = True
    gaia_chain_valid: bool = True
    reciprocity_entries: int = 0
    gaia_entries: int = 0
    verified_outcomes: int = 0
    evidence_records: int = 0
    audit_records: int = 0
    verified_offsets_tco2e: float = 0.0
    net_carbon_position_tco2e: float = 0.0
    routed_usd: float = 0.0
    obligation_usd: float = 0.0
    invariant_issue_count: int = 0
    conservation_violation_count: int = 0
    issue_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WikiContextReceipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: new_id("wiki"))
    goal_id: str
    created_at: str = Field(default_factory=utc_now_iso)
    source_count: int = 0
    atom_count: int = 0
    selected_sources: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AutoResearchReceipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: new_id("autoresearch"))
    goal_id: str
    created_at: str = Field(default_factory=utc_now_iso)
    dry_run: bool = True
    loop_invoked: bool = False
    candidate_count: int = 0
    target_modules: list[str] = Field(default_factory=list)
    immutable_files: list[str] = Field(default_factory=list)
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)


class DGMRunReceipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: new_id("dgm"))
    goal_id: str
    created_at: str = Field(default_factory=utc_now_iso)
    shadow_mode: bool = True
    source_file: str = ""
    fitness_delta: float = 0.0
    applied: bool = False
    rolled_back: bool = False
    lineage_depth: int = 0
    archive_growth: int = 0
    success: bool = False
    error: str | None = None


class GoalRun(BaseModel):
    run_id: str = Field(default_factory=lambda: new_id("run"))
    spec: GoalSpec
    status: GoalRunStatus = GoalRunStatus.QUEUED
    created_at: str = Field(default_factory=utc_now_iso)
    completed_at: str | None = None
    latest_score: float = 0.0
    metrics: GoodworksMetricSnapshot = Field(default_factory=GoodworksMetricSnapshot)
    wiki_receipt: WikiContextReceipt | None = None
    autoresearch_receipt: AutoResearchReceipt | None = None
    dgm_receipt: DGMRunReceipt | None = None
    receipts: list[dict[str, Any]] = Field(default_factory=list)
    next_required_action: str = ""
    error: str | None = None

    @model_validator(mode="after")
    def receipts_have_no_secrets(self) -> "GoalRun":
        reject_secret_text(self.model_dump(mode="json"))
        return self
