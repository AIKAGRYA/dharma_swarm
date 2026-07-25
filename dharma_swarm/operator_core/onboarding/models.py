"""Typed, dependency-light models shared by onboarding and AgentOps."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


RECEIPT_SCHEMA_V1 = "dharma_swarm.onboard_receipt.v1"
RECEIPT_SCHEMA_V2 = "dharma_swarm.onboard_receipt.v2"
SESSION_ENTRY_SCHEMA_V1 = "dharma_swarm.session_entry.v1"
AUTHORITY_PRECEDENCE = ("executable", "tests", "locks", "git", "owner_files")

# Root receipt fields whose values vary between observations.  This tuple is
# useful for replay/unknown-field checks only.  Digest computation is always an
# explicit stable_digest(stable_core), never recursive key deletion.
_VOLATILE_KEYS = (
    "observed_at",
    "primary_verdict",
    "exit_code",
    "live_delta",
    "cache",
    "delta",
    "legacy_v1",
    "extensions",
    "stable_digest",
)


class OnboardingContractError(ValueError):
    """Base class for malformed onboarding inputs."""


class AgentOpsError(OnboardingContractError):
    """A work packet or its execution envelope failed closed."""


class ConfigError(AgentOpsError):
    """Owner configuration or an external path is unsafe or malformed."""


class ReceiptValidationError(OnboardingContractError):
    """A known receipt schema failed structural or integrity validation."""


class UnsupportedReceiptSchema(ReceiptValidationError):
    """A receipt declares a syntactically valid but unsupported major."""


@dataclass(frozen=True)
class GateSpec:
    name: str
    command: str
    argv: list[str]
    env: dict[str, str]
    expected_exit: int = 0
    timeout_seconds: int = 900
    max_output_chars: int = 30_000


@dataclass(frozen=True)
class CommitPolicy:
    allowed: bool
    message: str


@dataclass(frozen=True)
class ApprovalPolicy:
    before_commit: bool
    before_merge: bool


@dataclass(frozen=True)
class CollisionRecord:
    status: str
    checked_at_sha: str
    details: list[dict[str, Any]]


@dataclass(frozen=True)
class SessionEntry:
    schema: str
    tool_versions: dict[str, str]
    authority_precedence: list[str]
    work_packet: str
    active_track: str
    owner: str
    collision: CollisionRecord
    interface_mismatches: list[Any]
    closest_existing_implementation: list[str]
    honest_blockers: list[Any]
    rollback: str
    packet_digest: str


@dataclass(frozen=True)
class WorkPacket:
    id: str
    base_ref: str
    branch: str
    worktree: Path
    intent: str
    allowed_files: list[str]
    forbidden_files: list[str]
    gates: list[GateSpec]
    commit: CommitPolicy
    approval: ApprovalPolicy
    negative_controls: list[GateSpec] = field(default_factory=list)
    session_entry: SessionEntry | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True)
class ScopeState:
    tracked_changed_files: list[str]
    staged_files: list[str]
    untracked_files: list[str]
    changed_files: list[str]
    violations: list[dict[str, Any]]

    @property
    def passed(self) -> bool:
        return not self.violations


@dataclass(frozen=True)
class LoadedReceipt:
    schema: str
    major: int
    payload: dict[str, Any]
    admission_eligible: bool


__all__ = [
    "AUTHORITY_PRECEDENCE",
    "ApprovalPolicy",
    "AgentOpsError",
    "CollisionRecord",
    "CommitPolicy",
    "ConfigError",
    "GateSpec",
    "LoadedReceipt",
    "OnboardingContractError",
    "RECEIPT_SCHEMA_V1",
    "RECEIPT_SCHEMA_V2",
    "ReceiptValidationError",
    "SESSION_ENTRY_SCHEMA_V1",
    "ScopeState",
    "SessionEntry",
    "UnsupportedReceiptSchema",
    "WorkPacket",
    "_VOLATILE_KEYS",
]
