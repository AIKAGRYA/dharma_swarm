"""The single ingress-neutral Sarathi message-to-result transaction."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from dharma_swarm.spine.identity import ExecutionIdentity

from .contracts import (
    CognitionPort,
    CognitionRequest,
    CognitionResult,
    EffectIntent,
    EffectReport,
    EffectStatus,
    SarathiTurnRequest,
    SarathiTurnResult,
    TurnStatus,
    TurnStorePort,
)
from .identity import DEFAULT_SARATHI_IDENTITY, SarathiIdentity


class SarathiShell:
    """Own exactly one turn while delegating shared capabilities to ports."""

    def __init__(
        self,
        *,
        cognition: CognitionPort,
        turn_store: TurnStorePort | None = None,
        identity: SarathiIdentity = DEFAULT_SARATHI_IDENTITY,
        history_limit: int = 20,
    ) -> None:
        self.identity = identity
        self.cognition = cognition
        self.turn_store = turn_store
        self.history_limit = max(1, int(history_limit))

    @staticmethod
    def _new_execution_identity(request: SarathiTurnRequest) -> ExecutionIdentity:
        task_id = request.task_id.strip() or f"sarathi-turn-{uuid4().hex}"
        return ExecutionIdentity.new(
            task_id=task_id,
            agent_id=DEFAULT_SARATHI_IDENTITY.uid,
            session_id=request.session_id,
            correlation_id=request.correlation_id,
            metadata={
                "caller_id": request.caller_id,
                "ingress": request.ingress,
            },
        )

    @staticmethod
    def _blocked_effects(
        intents: tuple[EffectIntent, ...],
    ) -> tuple[EffectReport, ...]:
        return tuple(
            EffectReport(
                intent=intent,
                status=EffectStatus.BLOCKED,
                reason=(
                    "P0 has no effect adapter; execution requires a task-bound "
                    "validated authority reference and a correlated effect receipt"
                ),
            )
            for intent in intents
        )

    def _result(
        self,
        execution_identity: ExecutionIdentity,
        *,
        status: TurnStatus,
        reply: str = "",
        cognition: CognitionResult | None = None,
        input_receipt_ref: str = "",
        receipt_ref: str = "",
        effect_reports: tuple[EffectReport, ...] = (),
        uncertainties: tuple[str, ...] = (),
    ) -> SarathiTurnResult:
        return SarathiTurnResult(
            execution_identity=execution_identity,
            turn_id=execution_identity.trace_id,
            session_id=execution_identity.session_id,
            status=status,
            reply=reply,
            identity_version=self.identity.version,
            provider=cognition.provider if cognition else "",
            model=cognition.model if cognition else "",
            receipt_ref=receipt_ref,
            input_receipt_ref=input_receipt_ref,
            usage=dict(cognition.usage) if cognition else {},
            effect_reports=effect_reports,
            uncertainties=uncertainties,
        )

    async def handle_turn(self, request: SarathiTurnRequest) -> SarathiTurnResult:
        """Run message -> context -> cognition -> blocked effects -> receipt."""
        execution_identity = self._new_execution_identity(request).with_updates(
            agent_id=self.identity.uid
        )
        input_ref = ""
        durable_history: tuple[Mapping[str, Any], ...] = ()

        if self.turn_store is not None:
            try:
                durable_history = await self.turn_store.load_history(
                    request.session_id,
                    caller_id=request.caller_id,
                    limit=self.history_limit,
                )
                input_ref = await self.turn_store.record_input(
                    execution_identity,
                    request,
                )
                if not input_ref.strip():
                    raise RuntimeError("turn store returned an empty input receipt")
            except Exception as exc:  # noqa: BLE001 - boundary becomes typed failure
                return self._result(
                    execution_identity,
                    status=TurnStatus.FAILED,
                    uncertainties=(f"persistence_input_failed:{type(exc).__name__}",),
                )

        caller_history = tuple(
            {
                "role": "user",
                "content": "Caller-supplied prior context (untrusted):\n"
                + str(item.get("content") or ""),
            }
            for item in request.history
            if isinstance(item, Mapping) and item.get("content")
        )
        cognition_request = CognitionRequest(
            execution_identity=execution_identity,
            identity=self.identity,
            message=request.message,
            history=tuple(durable_history) + caller_history,
            context=request.context,
            metadata={**dict(request.metadata), "ingress": request.ingress},
        )

        try:
            cognition = await self.cognition.complete(cognition_request)
        except Exception as exc:  # noqa: BLE001 - provider failure is result state
            reports = self._blocked_effects(tuple(request.effect_intents))
            uncertainties = (f"cognition_failed:{type(exc).__name__}",)
            if reports:
                uncertainties += ("effects_blocked_pending_authority_adapter",)
            failure = self._result(
                execution_identity,
                status=TurnStatus.FAILED,
                input_receipt_ref=input_ref,
                effect_reports=reports,
                uncertainties=uncertainties,
            )
            return await self._record_failure_if_possible(failure)

        intents = tuple(request.effect_intents) + tuple(cognition.effect_intents)
        reports = self._blocked_effects(intents)
        uncertainties = tuple(cognition.uncertainties)
        if reports:
            uncertainties += ("effects_blocked_pending_authority_adapter",)

        if self.turn_store is None:
            return self._result(
                execution_identity,
                status=TurnStatus.UNRECORDED,
                reply=cognition.reply,
                cognition=cognition,
                input_receipt_ref=input_ref,
                effect_reports=reports,
                uncertainties=uncertainties + ("turn_store_not_configured",),
            )

        candidate = self._result(
            execution_identity,
            status=TurnStatus.UNRECORDED,
            reply=cognition.reply,
            cognition=cognition,
            input_receipt_ref=input_ref,
            effect_reports=reports,
            uncertainties=uncertainties,
        )
        try:
            receipt_ref = await self.turn_store.record_result(candidate)
            if not receipt_ref.strip():
                raise RuntimeError("turn store returned an empty result receipt")
        except Exception as exc:  # noqa: BLE001 - never claim durable completion
            return replace(
                candidate,
                status=TurnStatus.FAILED,
                receipt_ref="",
                uncertainties=candidate.uncertainties
                + (f"persistence_result_failed:{type(exc).__name__}",),
            )
        return replace(
            candidate,
            status=TurnStatus.COMPLETED,
            receipt_ref=receipt_ref,
        )

    async def _record_failure_if_possible(
        self,
        failure: SarathiTurnResult,
    ) -> SarathiTurnResult:
        if self.turn_store is None:
            return failure
        try:
            receipt_ref = await self.turn_store.record_result(failure)
            if receipt_ref.strip():
                return replace(failure, receipt_ref=receipt_ref)
        except Exception:  # noqa: BLE001 - original failure remains authoritative
            pass
        return failure


def build_sarathi_shell(
    *,
    cognition: CognitionPort | None = None,
    turn_store: TurnStorePort | None = None,
    identity: SarathiIdentity = DEFAULT_SARATHI_IDENTITY,
    state_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    working_dir: str | Path | None = None,
) -> SarathiShell:
    """Build the portable default shell without starting a process or loop."""
    if cognition is None:
        from .adapters.runtime_provider import SafeRuntimeCognition

        cognition = SafeRuntimeCognition(
            env=env,
            working_dir=str(working_dir) if working_dir is not None else None,
        )
    if turn_store is None:
        from dharma_swarm.daemon_config import dharma_state_dir

        from .adapters.runtime_state import RuntimeStateTurnStore

        configured_root = None
        if env is not None:
            configured_root = env.get("DHARMA_STATE_DIR") or env.get("DHARMA_HOME")
        root = Path(
            state_root
            if state_root is not None
            else configured_root or dharma_state_dir("DHARMA_STATE_DIR", "DHARMA_HOME")
        ).expanduser()
        turn_store = RuntimeStateTurnStore(root / "state" / "runtime.db")
    return SarathiShell(
        cognition=cognition,
        turn_store=turn_store,
        identity=identity,
    )


_DEFAULT_SHELL: SarathiShell | None = None


async def handle_turn(
    request: SarathiTurnRequest,
    *,
    shell: SarathiShell | None = None,
) -> SarathiTurnResult:
    """Stable Python invocation surface for any agent or model harness."""
    global _DEFAULT_SHELL
    active = shell
    if active is None:
        if _DEFAULT_SHELL is None:
            _DEFAULT_SHELL = build_sarathi_shell()
        active = _DEFAULT_SHELL
    return await active.handle_turn(request)


__all__ = ["SarathiShell", "build_sarathi_shell", "handle_turn"]
