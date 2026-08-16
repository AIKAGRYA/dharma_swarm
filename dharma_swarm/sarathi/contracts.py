"""Stable, ingress-neutral contracts for the Sarathi product boundary."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Mapping, Protocol, runtime_checkable

from dharma_swarm.spine.identity import ExecutionIdentity

if TYPE_CHECKING:
    from .identity import SarathiIdentity


class TurnStatus(str, Enum):
    """Truthful durability state for one attempted turn."""

    COMPLETED = "completed"
    UNRECORDED = "unrecorded"
    FAILED = "failed"


class EffectStatus(str, Enum):
    """Authority state of an effect proposed during a turn."""

    NOT_REQUESTED = "not_requested"
    BLOCKED = "blocked"
    EXECUTED = "executed"


@dataclass(frozen=True, slots=True)
class EffectIntent:
    """An effect request, never an assertion that the effect occurred."""

    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise ValueError("EffectIntent requires a non-empty kind")


@dataclass(frozen=True, slots=True)
class EffectReport:
    """Governed disposition of an effect intent.

    ``executed`` is uninhabitable without both the authority checked at the
    consumer boundary and a correlated effect receipt. Model text cannot
    manufacture either reference.
    """

    intent: EffectIntent = field(default_factory=lambda: EffectIntent(kind="unspecified"))
    status: EffectStatus = EffectStatus.NOT_REQUESTED
    reason: str = ""
    authority_ref: str = ""
    receipt_ref: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.status, EffectStatus):
            raise TypeError("EffectReport.status must be an EffectStatus")
        if self.status is EffectStatus.EXECUTED and not (
            self.authority_ref.strip() and self.receipt_ref.strip()
        ):
            raise ValueError(
                "executed effects require both authority_ref and receipt_ref"
            )


@dataclass(frozen=True, slots=True)
class SarathiTurnRequest:
    """One caller message, independent of HTTP, MCP, A2A, CLI, or Python."""

    message: str
    caller_id: str
    session_id: str = "default"
    task_id: str = ""
    correlation_id: str = ""
    ingress: str = "python"
    history: tuple[Mapping[str, Any], ...] = ()
    context: str = ""
    effect_intents: tuple[EffectIntent, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("SarathiTurnRequest requires a non-empty message")
        if not isinstance(self.caller_id, str) or not self.caller_id.strip():
            raise ValueError("SarathiTurnRequest requires a non-empty caller_id")
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise ValueError("SarathiTurnRequest requires a non-empty session_id")
        if not isinstance(self.ingress, str) or not self.ingress.strip():
            raise ValueError("SarathiTurnRequest requires a non-empty ingress")
        object.__setattr__(self, "caller_id", self.caller_id.strip())
        object.__setattr__(self, "session_id", self.session_id.strip())
        object.__setattr__(self, "task_id", self.task_id.strip())
        object.__setattr__(self, "correlation_id", self.correlation_id.strip())
        object.__setattr__(self, "ingress", self.ingress.strip())


@dataclass(frozen=True, slots=True)
class CognitionRequest:
    """The compiled working set presented to one cognition adapter."""

    execution_identity: ExecutionIdentity
    identity: SarathiIdentity
    message: str
    history: tuple[Mapping[str, Any], ...] = ()
    context: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CognitionResult:
    """Provider response plus proposals; it contains no effect authority."""

    reply: str
    provider: str = ""
    model: str = ""
    effect_intents: tuple[EffectIntent, ...] = ()
    uncertainties: tuple[str, ...] = ()
    usage: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SarathiTurnResult:
    """One turn result joined to its canonical execution identity."""

    execution_identity: ExecutionIdentity
    turn_id: str
    session_id: str
    status: TurnStatus
    reply: str = ""
    identity_version: str = ""
    provider: str = ""
    model: str = ""
    receipt_ref: str = ""
    input_receipt_ref: str = ""
    usage: Mapping[str, int] = field(default_factory=dict)
    effect_reports: tuple[EffectReport, ...] = ()
    uncertainties: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, TurnStatus):
            raise TypeError("SarathiTurnResult.status must be a TurnStatus")
        if self.turn_id != self.execution_identity.trace_id:
            raise ValueError("turn_id must equal execution_identity.trace_id")
        if self.session_id != self.execution_identity.session_id:
            raise ValueError("session_id must equal execution_identity.session_id")
        if self.status is TurnStatus.COMPLETED and not self.receipt_ref.strip():
            raise ValueError("completed turns require a durable receipt_ref")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "dharma.sarathi.turn_result.v1",
            "execution_identity": self.execution_identity.to_dict(),
            "turn_id": self.turn_id,
            "session_id": self.session_id,
            "status": self.status.value,
            "reply": self.reply,
            "identity_version": self.identity_version,
            "provider": self.provider,
            "model": self.model,
            "receipt_ref": self.receipt_ref,
            "input_receipt_ref": self.input_receipt_ref,
            "usage": dict(self.usage),
            "effect_reports": [
                {
                    **asdict(report),
                    "status": report.status.value,
                }
                for report in self.effect_reports
            ],
            "uncertainties": list(self.uncertainties),
        }


@runtime_checkable
class CognitionPort(Protocol):
    """One model decision boundary."""

    async def complete(self, request: CognitionRequest) -> CognitionResult: ...


@runtime_checkable
class TurnStorePort(Protocol):
    """Persistence boundary used by the composition root."""

    async def load_history(
        self, session_id: str, *, caller_id: str, limit: int = 20
    ) -> tuple[Mapping[str, Any], ...]: ...

    async def record_input(
        self,
        execution_identity: ExecutionIdentity,
        request: SarathiTurnRequest,
    ) -> str: ...

    async def record_result(self, result: SarathiTurnResult) -> str: ...


__all__ = [
    "CognitionPort",
    "CognitionRequest",
    "CognitionResult",
    "EffectIntent",
    "EffectReport",
    "EffectStatus",
    "SarathiTurnRequest",
    "SarathiTurnResult",
    "TurnStatus",
    "TurnStorePort",
]
