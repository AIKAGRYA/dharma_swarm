"""Import-leaf background execution for :mod:`dharma_swarm.orchestrator`.

The public host method stays on ``Orchestrator``; helper frame names differ.
"""

from __future__ import annotations

import asyncio
import copy
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Awaitable, Callable

from dharma_swarm.models import TaskStatus
from dharma_swarm.spine.adapters import identity_metadata
from dharma_swarm.spine.identity import ExecutionIdentity


class CampaignFenceStore:
    """Prove campaign invoker custody while generic callers remain fail-open."""

    def __init__(self, store: Any) -> None:
        self._store = store
        self.acquired = False

    def __getattr__(self, name: str) -> Any:
        if self._store is None:
            raise AttributeError(name)
        return getattr(self._store, name)

    async def try_begin_idempotent_side_effect_with_token(
        self, *args: Any, **kwargs: Any
    ) -> Any:
        token = await self._store.try_begin_idempotent_side_effect_with_token(
            *args, **kwargs
        )
        self.acquired = isinstance(token, datetime) and token.tzinfo is not None
        return token

    async def try_reclaim_idempotent_side_effect_with_token(
        self, *args: Any, **kwargs: Any
    ) -> Any:
        token = await self._store.try_reclaim_idempotent_side_effect_with_token(
            *args, **kwargs
        )
        self.acquired = isinstance(token, datetime) and token.tzinfo is not None
        return token

    def require_acquired(self) -> None:
        if not self.acquired:
            raise RuntimeError(
                "authenticated campaign lacks a durable idempotency fence"
            )


def require_campaign_dispatch_durable(
    receipt: Any, invoker: Any, *, receipt_persisted: bool
) -> None:
    """Reject every post-effect campaign outcome lacking durable authority."""
    if bool(getattr(receipt, "attributes", {}).get("unprotected_dispatch")):
        raise RuntimeError("authenticated campaign produced an unprotected receipt")
    if int(getattr(invoker, "audit_failures", 0) or 0):
        raise RuntimeError("authenticated campaign idempotency completion failed")
    if receipt_persisted is not True:
        raise RuntimeError("authenticated campaign receipt persistence failed")


def honors_checkpoint_error(task: Any) -> str:
    """Return the semantic rejection before a receipt can claim success."""
    try:
        from dharma_swarm.mission_contract import (
            honors_checkpoint_passed,
            load_completion_contract,
        )

        contract = load_completion_contract(getattr(task, "metadata", {}))
        if contract is not None and not honors_checkpoint_passed(task.metadata):
            return (
                "Honors checkpoint missing or failed: task returned a result "
                "without a passing judge pack"
            )
    except Exception as exc:
        return f"Honors checkpoint validation failed: {exc}"
    return ""


def retry_execution_candidates(task: Any | None, agents: list[Any]) -> list[Any]:
    """Require a retry to rotate away from its prior provider-effect owner."""
    metadata = getattr(task, "metadata", None)
    metadata = metadata if isinstance(metadata, dict) else {}
    failed_agent = str(metadata.get("last_failed_agent") or "").strip()
    try:
        is_retry = int(metadata.get("retry_count") or 0) > 0
    except (TypeError, ValueError):
        is_retry = False
    if not is_retry or not failed_agent:
        return agents
    return [agent for agent in agents if agent.id != failed_agent]


def prepare_retry_execution_identity(task: Any | None, td: Any) -> None:
    """Preserve exact lineage while clearing the prior attempt's aliases."""
    metadata = getattr(task, "metadata", None)
    metadata = metadata if isinstance(metadata, dict) else {}
    nested = metadata.get("execution_identity")
    incoming_claim = str(td.metadata.get("claim_id") or "")
    if not isinstance(nested, dict) or nested.get("claim_id") == incoming_claim:
        return
    prior = ExecutionIdentity.from_metadata(metadata, require=True)
    if prior is None or prior.task_id != td.task_id:
        raise RuntimeError("retry lacks an exact prior execution identity")
    for key in identity_metadata(prior, surface="orchestrator"):
        task.metadata.pop(key, None)
    td.metadata.update(
        correlation_id=prior.correlation_id,
        causation_id=prior.causation_id,
        parent_run_id=prior.run_id,
        external_a2a_task_id=prior.external_a2a_task_id,
    )


async def transition_task_board_exact(
    task_board: Any,
    task_id: str,
    *,
    status: TaskStatus,
    assigned_to: str,
    metadata: dict[str, Any],
    write_assigned_to: bool = False,
) -> Any | None:
    """Write one pre-effect Board state and attest its exact readback."""
    if task_board is None:
        return None
    board_get = getattr(task_board, "get", None)
    if not callable(board_get):
        raise RuntimeError("task board exact readback is unavailable")
    fields: dict[str, Any] = {"status": status, "metadata": dict(metadata)}
    if write_assigned_to:
        fields["assigned_to"] = assigned_to
    await task_board.update_task(task_id, **fields)
    observed = await board_get(task_id)
    if (
        observed is None
        or getattr(observed, "id", None) != task_id
        or getattr(observed, "status", None) is not status
        or getattr(observed, "assigned_to", None) != assigned_to
        or getattr(observed, "metadata", None) != metadata
    ):
        raise RuntimeError(
            f"task board {status.value} write lacks exact readback for {task_id}"
        )
    return observed


async def release_generic_dispatch(orchestrator: Any, td: Any) -> bool:
    """Release only the generic pool custody still owned by ``td``."""
    self = orchestrator
    active = self._active_dispatches.get(td.task_id)
    legacy = self._legacy_dispatch_owners
    legacy_owner = legacy.get(td.agent_id)
    if legacy_owner is not None:
        if legacy_owner is not td or active is not td:
            return False
        release = getattr(self._pool, "release", None)
        if not callable(release):
            return False
        await release(td.agent_id)
        if legacy.get(td.agent_id) is not td or self._active_dispatches.get(td.task_id) is not td:
            return False
        legacy.pop(td.agent_id, None)
        self._active_dispatches.pop(td.task_id, None)
        return True
    if active is not None and active is not td:
        return False
    if self._pool is None:
        if active is td:
            self._active_dispatches.pop(td.task_id, None)
        return True
    reserve = getattr(self._pool, "reserve", None)
    release = getattr(self._pool, "release_reservation", None)
    if not callable(reserve) or not callable(release):
        return False
    released = await release(td.agent_id, td.task_id, reservation_token=td)
    if released and self._active_dispatches.get(td.task_id) is td:
        self._active_dispatches.pop(td.task_id, None)
    return bool(released)


async def reserve_generic_dispatch(orchestrator: Any, td: Any) -> bool:
    """Acquire exact custody; legacy assign/release requires exclusive adapter use."""
    self = orchestrator
    reserve = getattr(self._pool, "reserve", None)
    exact_release = getattr(self._pool, "release_reservation", None)
    if callable(reserve) and callable(exact_release):
        self._active_dispatches[td.task_id] = td
        td.metadata["_generic_reservation_provisional"] = True
        acquired = bool(await reserve(td.agent_id, td.task_id, reservation_token=td))
        if acquired:
            td.metadata.pop("_generic_reservation_provisional", None)
        elif self._active_dispatches.get(td.task_id) is td:
            self._active_dispatches.pop(td.task_id, None)
            td.metadata.pop("_generic_reservation_provisional", None)
        return acquired
    assign = getattr(self._pool, "assign", None)
    release = getattr(self._pool, "release", None)
    if not callable(assign) or not callable(release):
        raise RuntimeError("agent pool lacks a complete generic custody API")
    if (self._legacy_dispatch_owners.get(td.agent_id) is not None
            or self._active_dispatches.get(td.task_id) is not None):
        return False
    self._legacy_dispatch_owners[td.agent_id] = td
    self._active_dispatches[td.task_id] = td
    await assign(td.agent_id, td.task_id)
    return (
        self._legacy_dispatch_owners.get(td.agent_id) is td
        and self._active_dispatches.get(td.task_id) is td
    )


async def commit_generic_transition(
    orchestrator: Any, td: Any, status: TaskStatus, metadata: dict[str, Any],
    *, assign: bool = False,
) -> Any | None:
    observed = await transition_task_board_exact(
        orchestrator._board, td.task_id, status=status,
        assigned_to=td.agent_id, metadata=metadata, write_assigned_to=assign,
    )
    if observed is None:
        await release_generic_dispatch(orchestrator, td)
    return observed


async def abort_generic_dispatch_setup(orchestrator: Any, td: Any,
                                       cause: BaseException) -> bool:
    self = orchestrator
    if td.metadata.get("authenticated_campaign_principal_id") or td.metadata.get("_campaign_failure_authority") is True:
        return False
    running = self._running_dispatch_owners.get(td.task_id)
    if (running is not None and running[1] is td and not running[0].done()
            and running[0] is not asyncio.current_task()
            and (getattr(self, "_stopping", False) or not running[0].cancelling())):
        return False
    active = self._active_dispatches.get(td.task_id)
    legacy_owned = self._legacy_dispatch_owners.get(td.agent_id) is td and active is td
    owns = getattr(self._pool, "owns_reservation", None)
    exact_owned = bool(callable(owns) and owns(
        td.agent_id, td.task_id, reservation_token=td))
    if not legacy_owned and not exact_owned and active is not td:
        return False
    recovery_owner = [td, f"generic cleanup is indeterminate: {type(cause).__name__}"]
    self._generic_recovery_owners[id(td)] = recovery_owner
    task = await self._safe_get_task(td.task_id)
    status = getattr(task, "status", None)
    if (
        td.metadata.get("_generic_reservation_provisional") is True
        and status is TaskStatus.PENDING
        and callable(owns)
        and not exact_owned
    ):
        if self._active_dispatches.get(td.task_id) is td:
            self._active_dispatches.pop(td.task_id, None)
        td.metadata.pop("_generic_reservation_provisional", None)
        if self._generic_recovery_owners.get(id(td)) is recovery_owner:
            self._generic_recovery_owners.pop(id(td), None)
        return True
    if self._board is not None and task is None:
        return False
    if status in {TaskStatus.ASSIGNED, TaskStatus.RUNNING} and getattr(
        task, "assigned_to", None
    ) != td.agent_id:
        return False
    if task is not None and status in {TaskStatus.ASSIGNED, TaskStatus.RUNNING} and getattr(task, "assigned_to", None) == td.agent_id:
        metadata = self._task_meta(task)
        metadata.pop("active_claim", None)
        metadata["dispatch_setup_recovery"] = {
            "schema_version": "dharma.dispatch_setup_recovery.v1", "state": "quarantined",
            "prior_status": status.value, "cause": type(cause).__name__,
        }
        await transition_task_board_exact(
            self._board, td.task_id, status=TaskStatus.FAILED,
            assigned_to=td.agent_id, metadata=metadata)
    released = await release_generic_dispatch(self, td)
    if (
        not released
        and not exact_owned
        and self._active_dispatches.get(td.task_id) is td
    ):
        self._active_dispatches.pop(td.task_id, None)
    if released and self._generic_recovery_owners.get(id(td)) is recovery_owner:
        self._generic_recovery_owners.pop(id(td), None)
    return released


async def record_terminal_projection(
    orchestrator: Any,
    td: Any,
    task: Any | None,
    *,
    status: str,
    board_result: str,
    board_metadata_set: dict[str, Any],
    board_metadata_remove: list[str],
    failure_code: str = "",
    action: str = "receipt",
    logger: Any,
) -> Any | None:
    """Commit terminal runtime truth, then best-effort replay its Board outbox."""
    self = orchestrator
    protocol_keys = {
        "graph_reconcile_projection",
        "graph_reconcile_projection_history",
        "task_board_completion_binding",
    }
    board_metadata_before = self._task_meta(task)
    desired_metadata = dict(board_metadata_set)
    board_metadata_set = {
        key: value for key, value in desired_metadata.items()
        if key not in protocol_keys
        and (key not in board_metadata_before or board_metadata_before[key] != value)
    }
    board_metadata_remove = sorted(
        key for key in set(board_metadata_remove)
        if key in board_metadata_before
        and key not in desired_metadata
        and key not in protocol_keys
    )
    if action in {"receipt", "retry"} and not str(
        td.metadata.get("evidence_receipt_id") or ""
    ):
        raise RuntimeError("terminal receipt projection lacks exact evidence")
    if task is None:
        await self._runtime_lifecycle.record_task_claim(
            td,
            task=None,
            status=status,
            failure_code=failure_code,
            error=board_result if status == "failed" else "",
        )
        await self._runtime_lifecycle.record_delegation_run(
            td,
            task=None,
            status=status,
            failure_code=failure_code,
            error=board_result if status == "failed" else "",
            result=board_result if status == "completed" else None,
        )
        return None

    from dharma_swarm.graph.reconcile_board import (
        BOARD_COMPLETION_BINDING_KEY,
        build_task_board_completion_binding,
        settle_task_board,
    )
    identity = self._runtime_lifecycle.ensure_execution_identity(
        td, task=task, require=True
    )
    runtime_task = copy.copy(task)
    runtime_task.metadata = dict(board_metadata_before)
    if action in {"receipt", "retry"}:
        runtime_task.metadata[BOARD_COMPLETION_BINDING_KEY] = (
            build_task_board_completion_binding(td, result=board_result)
        )
    td.metadata["_task_board_projection_metadata_set"] = dict(board_metadata_set)
    td.metadata["_task_board_projection_metadata_remove"] = board_metadata_remove
    error = board_result if status == "failed" else ""
    await self._runtime_lifecycle.record_task_claim(
        td,
        task=runtime_task,
        status=status,
        failure_code=failure_code,
        error=error,
        require_identity=True,
    )
    await self._runtime_lifecycle.record_delegation_run(
        td,
        task=runtime_task,
        status=status,
        failure_code=failure_code,
        error=error,
        result=board_result if status == "completed" else None,
        require_identity=True,
        project_task_board=True,
        task_board_projection_action=action,
    )
    report = SimpleNamespace(errors=[])
    try:
        await settle_task_board(
            runtime_state=self._runtime_lifecycle._runtime_state_store(),
            task_board=self._board,
            report=report,
            now=datetime.now(timezone.utc),
            logger=logger,
            run_id=identity.run_id,
        )
    except Exception:
        logger.warning(
            "Task %s terminal Board projection remains pending replay",
            td.task_id,
            exc_info=True,
        )
    if report.errors:
        logger.warning(
            "Task %s terminal Board projection remains pending: %s",
            td.task_id,
            report.errors,
        )
    return report


async def execute_task(
    orchestrator: Any,
    runner: Any,
    task: Any,
    td: Any,
    *,
    campaign_effect_fence: Callable[[], Awaitable[None]] | None = None,
    campaign_effect_ready: Callable[[], None] | None = None,
    campaign_principal: str = "",
    campaign_reservation_token: dict[str, Any] | None = None,
    logger: Any,
) -> None:
    """Execute the host orchestrator lifecycle without changing its ordering."""
    self = orchestrator
    campaign_owner = bool(
        campaign_principal and campaign_reservation_token is not None
    )
    td.metadata["_campaign_failure_authority"] = bool(campaign_principal)
    # Let the dispatch coroutine finish before synchronous pre-provider work.
    await asyncio.sleep(0)
    run_started = float(td.metadata.get("run_started_monotonic", time.monotonic()))
    timeout_seconds = max(
        0.01,
        self._coerce_float(td.timeout_seconds, self._default_timeout_seconds),
    )

    correlation_token = None
    reset_correlation = None
    terminal_outcome_started = False
    dispatch_owner_released = False

    cell_id = td.metadata.get("cell_id", "")
    identity_meta = td.metadata.get("execution_identity")
    if not isinstance(identity_meta, dict):
        identity_meta = {}
    trace_id = str(identity_meta.get("trace_id", "") or "")
    session_id = str(identity_meta.get("session_id", "") or "")
    if cell_id or trace_id:
        try:
            from dharma_swarm.correlation_context import (
                CorrelationContext,
                set_correlation,
                reset_correlation as _reset_correlation,
                get_correlation,
            )
            current = get_correlation()
            ctx = CorrelationContext(
                trace_id=trace_id or current.trace_id,
                proposal_id=current.proposal_id,
                session_id=session_id or current.session_id,
                cell_id=cell_id or current.cell_id,
            )
            correlation_token = set_correlation(ctx)
            reset_correlation = _reset_correlation
        except Exception:
            logger.debug("execution correlation context setup failed", exc_info=True)

    def prepare_campaign_before_effect() -> tuple[bool, Any | None]:
        applicable = bool(
            campaign_principal
            and campaign_reservation_token is not None
            and campaign_reservation_token.get("provider_task_scheduled") is False
        )
        if not applicable:
            return False, None
        ticket = self._prepare_campaign_before_effect_recovery(
            td,
            campaign_principal,
            campaign_reservation_token,
            allow_uninstalled_active=False,
        )
        return True, ticket

    async def finish_campaign_before_effect(ticket: Any | None) -> bool:
        if ticket is None:
            return False
        return await self._finish_campaign_before_effect_recovery(
            campaign_reservation_token,
            ticket,
        )

    async def release_dispatch_owner() -> bool:
        nonlocal dispatch_owner_released
        if dispatch_owner_released:
            return True
        if self._pool is None:
            if self._active_dispatches.get(td.task_id) is td:
                self._active_dispatches.pop(td.task_id, None)
            released = True
        elif campaign_principal and campaign_reservation_token is not None:
            released = await self._pool.release_reservation(
                td.agent_id,
                td.task_id,
                reservation_token=campaign_reservation_token,
            )
            if released and self._active_dispatches.get(td.task_id) is td:
                self._active_dispatches.pop(td.task_id, None)
            key = (td.task_id, campaign_principal, td.metadata.get("attempt_generation"))
            if released and self._campaign_reservations.get(key) is campaign_reservation_token:
                self._campaign_reservations.pop(key, None)
        else:
            released = await release_generic_dispatch(self, td)
        dispatch_owner_released = bool(released)
        if dispatch_owner_released:
            owners = self._campaign_recovery_owners if campaign_owner else self._generic_recovery_owners
            key = id(campaign_reservation_token) if campaign_owner else id(td)
            entry = owners.get(key)
            if isinstance(entry, list) and entry and entry[0] is td:
                owners.pop(key, None)
        return dispatch_owner_released

    def retain_indeterminate_custody(reason: str) -> None:
        if campaign_owner:
            key = id(campaign_reservation_token)
            entry = self._campaign_recovery_owners.get(key)
            if not (isinstance(entry, list) and entry and entry[0] is td):
                self._campaign_recovery_owners[key] = [td, campaign_reservation_token, None, False]
        else:
            self._generic_recovery_owners[id(td)] = [td, reason]

    async def fail_before_release(error: str, source: str) -> bool:
        retain_indeterminate_custody(f"{source} projection is indeterminate")
        await self._handle_task_failure(td=td, task=task, error=error, source=source)
        if self._board is not None:
            board_get = getattr(self._board, "get", None)
            observed = await board_get(td.task_id) if callable(board_get) else None
            active = {TaskStatus.ASSIGNED, TaskStatus.RUNNING}
            if observed is None or observed.status in active or (
                observed.status is TaskStatus.PENDING and observed.assigned_to
            ):
                return False
        return await release_dispatch_owner()

    from dharma_swarm.orchestrator_dispatch_guard import shield_recovery

    try:
        await self._runtime_lifecycle.record_delegation_run(
            td,
            task=task,
            status="running",
        )
        spine_dispatch_enabled = self._spine_dispatch_enabled()
        if campaign_principal and not spine_dispatch_enabled:
            raise RuntimeError(
                "authenticated campaign dispatch requires Runtime Truth Spine"
            )
        if spine_dispatch_enabled:
            # Route through the Runtime Truth Spine's blessed invoke path.
            if campaign_effect_fence is None:
                result = await self._run_task_via_spine(
                    runner,
                    task,
                    td,
                    timeout_seconds,
                    campaign_fail_closed=campaign_owner,
                )
            else:
                result = await self._run_task_via_spine(
                    runner,
                    task,
                    td,
                    timeout_seconds,
                    campaign_effect_fence=campaign_effect_fence,
                    campaign_effect_ready=campaign_effect_ready,
                    campaign_fail_closed=campaign_owner,
                )
        else:
            result = await asyncio.wait_for(
                runner.run_task(
                    task,
                    **(
                        {
                            "campaign_effect_fence": campaign_effect_fence,
                            "campaign_effect_ready": campaign_effect_ready,
                        }
                        if campaign_effect_fence is not None
                        else {}
                    ),
                ),
                timeout=timeout_seconds,
            )
        honors_error = honors_checkpoint_error(task)
        if honors_error:
            terminal_outcome_started = True
            settled = await shield_recovery(
                self,
                f"terminal\0{td.task_id}\0honors",
                lambda: fail_before_release(honors_error, "honors_checkpoint"),
            )
            if not settled:
                raise RuntimeError("honors failure retained indeterminate custody")
            return
        success_meta = self._task_meta(task)
        success_meta.pop("active_claim", None)
        success_meta.pop("retry_not_before_epoch", None)
        success_meta["last_completed_at"] = datetime.now(timezone.utc).isoformat()
        success_meta["last_result_chars"] = len(result or "")
        try:
            from dharma_swarm.mission_contract import load_honors_checkpoint

            honors_checkpoint = load_honors_checkpoint(success_meta)
            if honors_checkpoint is not None:
                success_meta["honors_checkpoint_score"] = honors_checkpoint.judge_pack.final_score
                success_meta["honors_checkpoint_accepted"] = honors_checkpoint.judge_pack.accepted
        except Exception:
            logger.debug("Honors checkpoint summary extraction failed", exc_info=True)
        terminal_outcome_started = True
        if not td.metadata.get("evidence_receipt_id") and not campaign_principal:
            await self._runtime_lifecycle.record_task_claim(
                td, task=task, status="completed", require_identity=True
            )
            await self._runtime_lifecycle.record_delegation_run(
                td, task=task, status="completed", result=result,
                require_identity=True,
            )
            await self._safe_update_task(
                td.task_id, status=TaskStatus.COMPLETED, result=result,
                metadata=success_meta,
            )
        else:
            await record_terminal_projection(
                self,
                td,
                task,
                status="completed",
                board_result=str(result or ""),
                board_metadata_set=success_meta,
                board_metadata_remove=["active_claim", "retry_not_before_epoch"],
                logger=logger,
            )
        if self._board is not None:
            board_get = getattr(self._board, "get", None)
            observed = await board_get(td.task_id) if callable(board_get) else None
            if observed is None or observed.status is not TaskStatus.COMPLETED:
                retain_indeterminate_custody(
                    "completion projection lacks exact Board readback"
                )
                raise RuntimeError("completion projection is not durable on Board")
        if not await release_dispatch_owner():
            retain_indeterminate_custody("terminal owner release is indeterminate")
            raise RuntimeError("terminal owner release is indeterminate")
        if self._yoga is not None:
            self._yoga.record_completion(td.agent_id)
        logger.info("Task %s completed by agent %s", td.task_id, td.agent_id)
        duration_sec = max(0.0, time.monotonic() - run_started)
        try:
            from dharma_swarm.signal_bus import SignalBus, SIGNAL_LIFECYCLE_COMPLETED
            SignalBus.get().emit({
                "type": SIGNAL_LIFECYCLE_COMPLETED,
                "task_id": td.task_id,
                "agent_id": td.agent_id,
                "duration_sec": round(duration_sec, 4),
                "result_chars": len(result or ""),
            })
        except Exception:
            pass  # signal_bus emission is non-critical

        try:
            from dharma_swarm.telos_tracker import record_task_completion
            _t1 = asyncio.create_task(
                record_task_completion(
                    task_title=getattr(task, 'title', ''),
                    task_description=getattr(task, 'description', ''),
                    result=result,
                    state_dir=self._runtime_root(),
                )
            )
            _t1.add_done_callback(
                lambda t: (
                    logger.debug("telos_tracker failed: %s", t.exception())
                    if not t.cancelled() and t.exception() else None
                )
            )
        except Exception:
            pass  # Never block task completion

        # P4: Knowledge consolidation → KnowledgeStore via SleepTimeAgent.
        # An authenticated campaign may perform model-backed consolidation only
        # as a separately dispatched and fenced task.  The legacy generic path
        # remains unchanged.
        if not campaign_principal:
            try:
                from dharma_swarm.models import LLMRequest
                from dharma_swarm.runtime_provider import (
                    complete_via_preferred_runtime_providers,
                )
                from dharma_swarm.sleep_time_agent import SleepTimeAgent

                class _MinimalLLMClient:
                    """Thin adapter matching KnowledgeExtractor._call_llm."""

                    async def complete(self, request_or_prompt, **kwargs):
                        from dharma_swarm.models import ProviderType

                        if isinstance(request_or_prompt, str):
                            req = LLMRequest(
                                model="",
                                messages=[
                                    {"role": "user", "content": request_or_prompt}
                                ],
                                system=(
                                    "Extract factual claims and recommendations from "
                                    "text. Return valid JSON array only."
                                ),
                                max_tokens=kwargs.get("max_tokens", 512),
                                temperature=0.1,
                            )
                        else:
                            req = request_or_prompt
                            req.model = req.model or ""
                            req.max_tokens = min(
                                getattr(req, "max_tokens", 512) or 512,
                                512,
                            )

                        cheap_providers = [
                            ProviderType.OLLAMA,
                            ProviderType.GROQ,
                            ProviderType.NVIDIA_NIM,
                            ProviderType.CEREBRAS,
                            ProviderType.OPENROUTER,
                            ProviderType.OPENROUTER_FREE,
                        ]
                        for provider_type in cheap_providers:
                            try:
                                from dharma_swarm.runtime_provider import (
                                    create_default_provider_map,
                                )

                                provider = create_default_provider_map().get(
                                    provider_type
                                )
                                if provider and getattr(provider, "available", False):
                                    response = await provider.complete(req)
                                    if response and getattr(response, "content", None):
                                        return response
                            except Exception:
                                continue

                        try:
                            return await complete_via_preferred_runtime_providers(req)
                        except Exception as exc:
                            logger.debug(
                                "_MinimalLLMClient: all providers failed: %s",
                                exc,
                            )

                            class _EmptyResponse:
                                content = "[]"
                                text = "[]"

                            return _EmptyResponse()

                sleep_time_agent = SleepTimeAgent()
                sleep_time_task = asyncio.create_task(
                    sleep_time_agent.consolidate_knowledge(
                        task_context=result or "",
                        task_outcome={
                            "success": True,
                            "task_title": getattr(task, "title", ""),
                            "source": "task_completion",
                        },
                        llm_client=_MinimalLLMClient(),
                    )
                )
                sleep_time_task.add_done_callback(
                    lambda completed: (
                        logger.warning(
                            "SleepTimeAgent consolidation failed: %s",
                            completed.exception(),
                        )
                        if not completed.cancelled() and completed.exception()
                        else None
                    )
                )
            except Exception:
                pass  # Never block generic task completion

        try:
            from dharma_swarm.catalytic_graph import CatalyticGraph
            cg = CatalyticGraph()
            cg.load()
            quality = min(1.0, len(result or "") / 2000.0)
            cg.add_edge(
                source=f"agent:{td.agent_id}",
                target=f"task:{task.title[:40]}",
                edge_type="enables",
                strength=round(max(0.1, quality), 2),
                evidence=f"Completed in {duration_sec:.0f}s",
            )
            cg.save()
        except Exception:
            pass

        self._record_progress_event(
            "task_completed",
                task_id=td.task_id,
                agent_id=td.agent_id,
                duration_sec=round(duration_sec, 4),
                result_chars=len(result or ""),
                timeout_seconds=timeout_seconds,
            )
        await self._emit_lifecycle_event(
            "task_completed",
            task_id=td.task_id,
            agent_id=td.agent_id,
            extra={"duration_sec": round(duration_sec, 4)},
        )
        # Land a trace the Witness auditor (Loop 6) and trace-reading cascade
        # loops can sense — otherwise they only ever see boot/heartbeat and
        # never real agent work.
        await self._emit_completion_trace(
            task=task,
            agent_id=td.agent_id,
            duration_sec=duration_sec,
            result=result,
            success=True,
        )
        # Emit durable event for evolution loop consumption
        if self._bus is not None:
            emit = getattr(self._bus, "emit_event", None)
            if emit:
                try:
                    await emit(
                        "AGENT_LIFECYCLE_COMPLETED",
                        task_id=td.task_id,
                        agent_id=td.agent_id,
                        payload={"event": "task_completed", "duration_sec": round(duration_sec, 4)},
                    )
                except Exception:
                    logger.debug("Lifecycle event emit failed (non-critical)", exc_info=True)

        # Legacy compatibility only: free-text task descriptions must not
        # choose infrastructure write paths unless a structured caller opts in.
        task_metadata = getattr(task, "metadata", {}) or {}
        if (
            not campaign_principal
            and task_metadata.get("allow_free_text_result_path") is True
        ):
            try:
                desc = task.description or ""
                path_match = re.search(
                    r"[Ww]rite [\w\s]*?(?:to |report to |results to |output to |findings to )(~/[^\s,\"]+\.md)",
                    desc,
                )
                if path_match and result and len(result) > 200:
                    target = Path(path_match.group(1)).expanduser()
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(result, encoding="utf-8")
                    logger.info("Auto-extracted %d chars to %s", len(result), target)
            except Exception:
                logger.debug("Auto-extract failed", exc_info=True)

        # Persist result to shared notes and stigmergy
        runner_cfg = getattr(runner, "_config", None)
        agent_name = runner_cfg.name if runner_cfg else td.agent_id[:8]
        model_name = getattr(runner_cfg, "model", "unknown")
        provider_name = (
            getattr(getattr(runner_cfg, "provider", None), "value", None)
            or str(getattr(runner_cfg, "provider", "unknown"))
        )
        await self._persist_result(
            agent_name=agent_name,
            model_name=str(model_name),
            provider_name=str(provider_name),
            task=task,
            result=result,
            run_id=str(td.metadata.get("runtime_run_id", "") or ""),
        )

        cell_id = td.metadata.get("cell_id", "")
        if cell_id and self._bus is not None:
            try:
                emit = getattr(self._bus, "emit_event", None)
                if emit:
                    await emit(
                        "ROOM_TASK_COMPLETED",
                        task_id=td.task_id,
                        agent_id=td.agent_id,
                        payload={
                            "cell_id": cell_id,
                            "task_title": task.title[:120],
                            "duration_sec": round(duration_sec, 4),
                            "result_chars": len(result or ""),
                        },
                    )
            except Exception:
                logger.debug("Room task completion signal failed", exc_info=True)

    except asyncio.TimeoutError:
        if campaign_owner:
            pre_effect, ticket = prepare_campaign_before_effect()
            if pre_effect:
                recovered = await shield_recovery(
                    self,
                    f"campaign\0{td.task_id}\0{id(campaign_reservation_token)}",
                    lambda: finish_campaign_before_effect(ticket),
                )
                logger.error(
                    "Campaign task %s timed out before provider boundary; recovered=%s",
                    td.task_id,
                    recovered,
                )
                if recovered:
                    return
                raise
        error = f"Task execution timed out after {timeout_seconds:.1f}s"
        logger.warning("Task %s timeout on agent %s", td.task_id, td.agent_id)
        settled = await shield_recovery(
            self,
            f"terminal\0{td.task_id}\0timeout",
            lambda: fail_before_release(error, "timeout"),
        )
        if not settled:
            raise RuntimeError("timeout retained indeterminate custody")
    except asyncio.CancelledError as exc:
        if dispatch_owner_released:
            raise
        if not campaign_owner:
            await shield_recovery(
                self,
                f"generic\0{td.task_id}",
                lambda cause=exc: abort_generic_dispatch_setup(self, td, cause),
            )
            raise
        pre_effect, ticket = prepare_campaign_before_effect()
        if pre_effect:
            recovered = await shield_recovery(
                self,
                f"campaign\0{td.task_id}\0{id(campaign_reservation_token)}",
                lambda: finish_campaign_before_effect(ticket),
            )
            logger.error(
                "Campaign task %s cancelled before provider boundary; recovered=%s",
                td.task_id,
                recovered,
            )
        else:
            await shield_recovery(
                self,
                f"terminal\0{td.task_id}\0campaign-cancelled",
                lambda: fail_before_release(
                    "Task execution cancelled after provider boundary", "cancelled"
                ),
            )
        raise
    except Exception as exc:
        if terminal_outcome_started:
            if not dispatch_owner_released:
                retain_indeterminate_custody(
                    "terminal projection or release raised before proof"
                )
            raise
        if campaign_owner:
            pre_effect, ticket = prepare_campaign_before_effect()
            if pre_effect:
                recovered = await shield_recovery(
                    self,
                    f"campaign\0{td.task_id}\0{id(campaign_reservation_token)}",
                    lambda: finish_campaign_before_effect(ticket),
                )
                logger.exception(
                    "Campaign task %s failed before provider boundary; recovered=%s",
                    td.task_id,
                    recovered,
                )
                if recovered:
                    return
                raise
        logger.exception("Task %s failed: %s", td.task_id, exc)
        settled = await shield_recovery(
            self,
            f"terminal\0{td.task_id}\0execution-error",
            lambda error=str(exc): fail_before_release(error, "execution_error"),
        )
        if not settled:
            raise RuntimeError("execution failure retained indeterminate custody")
    finally:
        if correlation_token is not None and reset_correlation is not None:
            try:
                reset_correlation(correlation_token)
            except Exception:
                logger.debug("cell_id correlation context reset failed", exc_info=True)
        # NOTE: Do NOT pop from _running_tasks here.
        # _collect_completed() is the sole cleanup mechanism — it checks
        # atask.done() and counts settled tasks. If we pop here, the task
        # vanishes before _collect_completed can see it, causing settled=0.
        pass
