"""Unified schema for the slop-verification system.

Every detector emits a list[Finding] with these exact fields. The
aggregator and router consume only this schema — no detector-specific
shapes leak past the adapter boundary.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DetectorFamily(str, Enum):
    """Weight classes in the noisy-OR aggregator.

    Keep this list aligned with dharma_swarm.slop.aggregate.FAMILY_WEIGHTS.
    Adding a family without updating weights = bug.
    """

    AI_SLOP = "ai_slop"
    DEAD_CODE = "dead_code"
    COMPLEXITY = "complexity"
    STRUCTURE = "structure"
    PROVENANCE = "provenance"
    BEHAVIORAL = "behavioral"
    ADVERSARIAL = "adversarial"
    SECURITY = "security"
    DUPLICATION = "duplication"
    TYPE_DRIFT = "type_drift"
    BOUNDARY = "boundary"


@dataclass(frozen=True, slots=True)
class Finding:
    tool: str
    family: DetectorFamily
    issue_type: str
    path: str
    line: int | None
    symbol: str | None
    severity: Severity
    confidence: float
    evidence: str
    suggested_action: str = ""
    introduced: str | None = None
    owner: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be in [0,1], got {self.confidence} from {self.tool}"
            )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["family"] = self.family.value
        d["severity"] = self.severity.value
        return d


@dataclass(frozen=True, slots=True)
class DetectorResult:
    tool: str
    family: DetectorFamily
    findings: list[Finding]
    duration_sec: float
    exit_code: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and self.error is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "family": self.family.value,
            "duration_sec": self.duration_sec,
            "exit_code": self.exit_code,
            "error": self.error,
            "finding_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass(frozen=True, slots=True)
class ModuleScore:
    path: str
    p_raw: float
    p: float
    agreement: int
    family_scores: dict[str, float]
    finding_count: int
    capped: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SlopLedgerEntry:
    timestamp: str
    mode: str
    module_score: ModuleScore
    action: str
    findings: list[Finding] = field(default_factory=list)

    @classmethod
    def now(
        cls,
        mode: str,
        score: ModuleScore,
        action: str,
        findings: list[Finding],
    ) -> SlopLedgerEntry:
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            mode=mode,
            module_score=score,
            action=action,
            findings=findings,
        )

    def to_jsonl_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "mode": self.mode,
            "module_score": self.module_score.to_dict(),
            "action": self.action,
            "findings": [f.to_dict() for f in self.findings],
        }
