"""Typed state and evidence models for the lab supervisor."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class LabState(StrEnum):
    """Non-coercible operational states.

    ``Halted`` dominates every other observation.  ``Blocked`` means a named
    prerequisite or safety floor prevents useful work.  Neither is a synonym
    for scientific failure.
    """

    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    HALTED = "Halted"
    BLOCKED = "Blocked"


class ActionKind(StrEnum):
    """Complete supervisor effect vocabulary."""

    INSPECT = "inspect"
    KEEP_HALTED = "keep_halted"
    QUARANTINE_PROVIDER = "quarantine_provider"
    ROTATE_PROVIDER = "rotate_provider"
    RUN_BOUNDED_TRIAL = "run_bounded_trial"
    PRUNE_DISPOSABLE = "prune_disposable"


@dataclass(frozen=True)
class EvidenceRef:
    path: str
    sha256: str
    observed_mtime: float
    size_bytes: int


@dataclass(frozen=True)
class CommandOutcome:
    available: bool
    returncode: int | None
    timed_out: bool = False
    stdout: str = ""
    stderr: str = ""
    attempts: int = 0
    command_sha256: str = ""
    error: str = ""

    @property
    def succeeded(self) -> bool:
        return self.available and not self.timed_out and self.returncode == 0


@dataclass(frozen=True)
class LabSnapshot:
    lab: str
    observed_at: float
    evidence: tuple[EvidenceRef, ...] = ()
    latest_evidence_at: float | None = None
    halt_evidence: tuple[str, ...] = ()
    provider_failures: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    probe: CommandOutcome | None = None


@dataclass(frozen=True)
class ActionResult:
    lab: str
    action: ActionKind
    status: str
    command_sha256: str = ""
    returncode: int | None = None
    detail: str = ""
    artifacts: tuple[str, ...] = ()


@dataclass(frozen=True)
class LabAssessment:
    lab: str
    state: LabState
    reasons: tuple[str, ...]
    observed_at: float
    latest_evidence_at: float | None
    halt_latched: bool
    evidence: tuple[EvidenceRef, ...] = ()
    actions: tuple[ActionResult, ...] = ()


@dataclass(frozen=True)
class ResourceStatus:
    safe: bool
    free_disk_bytes: int
    load_per_cpu: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class TickReport:
    schema: str
    tick_id: str
    observed_at: float
    state: LabState
    dry_run: bool
    assessments: tuple[LabAssessment, ...] = ()
    resource_status: ResourceStatus | None = None
    receipt_hash: str = ""
    lock_contended: bool = False
    internal_failure: bool = False
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LabRuntimeState:
    halt_latched: bool = False
    halt_reasons: list[str] = field(default_factory=list)
    consecutive_failures: int = 0
    circuit_open_until: float = 0.0
    last_trial_at: float = 0.0
    budget_date: str = ""
    actions_today: int = 0
    trials_today: int = 0
    provider_actions_today: int = 0
    cleanup_actions_today: int = 0

    def reset_daily_budget(self, date: str) -> None:
        if self.budget_date == date:
            return
        self.budget_date = date
        self.actions_today = 0
        self.trials_today = 0
        self.provider_actions_today = 0
        self.cleanup_actions_today = 0
