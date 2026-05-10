"""Canonical data contracts for Dharma slop governance."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


def _repo_root() -> Path:
    """Resolve the dharma_swarm repo root.

    Order of resolution:
      1. DHARMA_REPO_ROOT env var (explicit override).
      2. Walk up from this file until a `pyproject.toml` is found.
      3. Fall back to ~/dharma_swarm.
    """
    explicit = os.environ.get("DHARMA_REPO_ROOT")
    if explicit:
        return Path(explicit).resolve()
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return (Path.home() / "dharma_swarm").resolve()


_REPO_ROOT_STR = str(_repo_root())


class DetectorFamily(str, Enum):
    STRUCTURE = "structure"
    DEAD_CODE = "dead_code"
    COMPLEXITY = "complexity"
    SECURITY = "security"
    TYPE_SAFETY = "type_safety"
    DEPENDENCY = "dependency"
    COVERAGE = "coverage"
    AI_SLOP = "ai_slop"
    PROVENANCE = "provenance"
    BEHAVIOR = "behavior"
    SEMANTIC = "semantic"
    ADVERSARIAL = "adversarial"


class SlopSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SlopMode(str, Enum):
    PRE_COMMIT = "pre-commit"
    CI = "ci"
    NIGHTLY = "nightly"


class RouterAction(str, Enum):
    LOG = "log"
    WARN = "warn"
    BLOCK_REGRESSION = "block_regression"
    OPEN_REFACTOR_PR = "open_refactor_pr"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SlopFinding(BaseModel):
    tool: str
    detector_family: DetectorFamily
    issue_type: str
    path: str
    line: int | None = Field(default=None, ge=1)

    @field_validator("path", mode="before")
    @classmethod
    def _normalize_path(cls, v: Any) -> str:
        """Normalize to repo-relative POSIX path; prevents same file appearing
        as both `dharma_swarm/foo.py` and `/Users/.../dharma_swarm/foo.py`.
        """
        if v is None:
            return ""
        s = str(v).strip()
        if not s:
            return ""
        if s.startswith(_REPO_ROOT_STR):
            s = s[len(_REPO_ROOT_STR):].lstrip("/\\")
        # Some tools emit paths absolute via different roots (worktree mirrors,
        # symlinks). Strip any trailing absolute prefix that contains the
        # canonical "/dharma_swarm/dharma_swarm/" segment.
        marker = "/dharma_swarm/"
        if s.startswith("/") and marker in s:
            idx = s.find(marker)
            s = s[idx + 1 :]  # keep "dharma_swarm/..."
        return s.replace("\\", "/")
    symbol: str | None = None
    severity: SlopSeverity = SlopSeverity.LOW
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    introduced: bool = False
    owner: str | None = None
    evidence: str = ""
    suggested_action: str = "review"
    mode: SlopMode = SlopMode.CI
    base_ref: str = "origin/main"
    commit: str = "HEAD"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DetectorResult(BaseModel):
    tool: str
    detector_family: DetectorFamily
    mode: SlopMode = SlopMode.CI
    findings: list[SlopFinding] = Field(default_factory=list)
    elapsed_ms: int = Field(default=0, ge=0)
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModuleScore(BaseModel):
    path: str
    slop_probability: float = Field(ge=0.0, le=1.0)
    family_scores: dict[str, float] = Field(default_factory=dict)
    findings: list[SlopFinding] = Field(default_factory=list)
    introduced: bool = False


class ActionDecision(BaseModel):
    action: RouterAction
    blocks: bool = False
    reason: str
    requires_human_review: bool = False


class SlopLedgerEntry(BaseModel):
    timestamp: datetime = Field(default_factory=utc_now)
    module: ModuleScore
    decision: ActionDecision
    schema_version: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)
