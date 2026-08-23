"""Background task execution helper for :mod:`dharma_swarm.orchestrator`.

The public host method remains on ``Orchestrator``.  This import-leaf helper
preserves its lifecycle control flow, await points, and operation ordering
while allowing the host module to remain within its immutable line budget.
Traceback/source/qualname frames inside this helper intentionally differ.
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from dharma_swarm.models import TaskStatus


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
    # Yield immediately so the dispatching coroutine can finish its loop
    # before this background task starts its synchronous pre-LLM work
    await asyncio.sleep(0)
    run_started = float(td.metadata.get("run_started_monotonic", time.monotonic()))
    timeout_seconds = max(
        0.01,
        self._coerce_float(td.timeout_seconds, self._default_timeout_seconds),
    )

    correlation_token = None
    reset_correlation = None

    # Set CorrelationContext with execution identity for room-scoped tracing.
    # The token is reset in finally to avoid context leakage across tasks.
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
        if self._pool is None:
            if self._active_dispatches.get(td.task_id) is td:
                self._active_dispatches.pop(td.task_id, None)
            return True
        if campaign_principal and campaign_reservation_token is not None:
            released = await self._pool.release_reservation(
                td.agent_id,
                td.task_id,
                reservation_token=campaign_reservation_token,
            )
            if released and self._active_dispatches.get(td.task_id) is td:
                self._active_dispatches.pop(td.task_id, None)
            return bool(released)
        await self._pool.release(td.agent_id)
        self._active_dispatches.pop(td.task_id, None)
        return True

    try:
        await self._runtime_lifecycle.record_delegation_run(
            td,
            task=task,
            status="running",
        )
        if self._spine_dispatch_enabled():
            # Route execution through the Runtime Truth Spine's one blessed
            # path (invoke_agent), emitting exactly one EvidenceReceipt.
            # Explicit false-like DHARMA_SPINE_DISPATCH values preserve the
            # legacy direct path as a rollback lane.
            if campaign_effect_fence is None:
                result = await self._run_task_via_spine(
                    runner,
                    task,
                    td,
                    timeout_seconds,
                )
            else:
                result = await self._run_task_via_spine(
                    runner,
                    task,
                    td,
                    timeout_seconds,
                    campaign_effect_fence=campaign_effect_fence,
                    campaign_effect_ready=campaign_effect_ready,
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
        try:
            from dharma_swarm.mission_contract import (
                honors_checkpoint_passed,
                load_completion_contract,
                load_honors_checkpoint,
            )

            completion_contract = load_completion_contract(task.metadata)
            honors_checkpoint = load_honors_checkpoint(task.metadata)
            if completion_contract is not None and not honors_checkpoint_passed(task.metadata):
                error = (
                    "Honors checkpoint missing or failed: task returned a result "
                    "without a passing judge pack"
                )
                await release_dispatch_owner()
                await self._handle_task_failure(
                    td=td,
                    task=task,
                    error=error,
                    source="honors_checkpoint",
                )
                return
        except Exception as exc:
            logger.exception("Task %s honors checkpoint validation failed: %s", td.task_id, exc)
            await release_dispatch_owner()
            await self._handle_task_failure(
                td=td,
                task=task,
                error=f"Honors checkpoint validation failed: {exc}",
                source="honors_checkpoint",
            )
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
        await self._safe_update_task(
            td.task_id,
            status=TaskStatus.COMPLETED,
            result=result,
            metadata=success_meta,
        )
        await release_dispatch_owner()
        # Release YogaNode capacity for this agent
        if self._yoga is not None:
            self._yoga.record_completion(td.agent_id)
        logger.info("Task %s completed by agent %s", td.task_id, td.agent_id)
        duration_sec = max(0.0, time.monotonic() - run_started)
        await self._runtime_lifecycle.record_task_claim(
            td,
            task=task,
            status="completed",
        )
        await self._runtime_lifecycle.record_delegation_run(
            td,
            task=task,
            status="completed",
            result=result,
        )

        # Emit to signal_bus so organism heartbeat, evolution loop,
        # and consolidation loop can sense completed work.
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

        # P1: Perception loop — task completion → TelosGraph progress
        # Uses supervised task tracking to prevent silent GC before completion
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

        # Record edge in catalytic graph: agent → task_type
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

        # Emit room-scoped task completion signal for kaizen review
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
                recovered = await finish_campaign_before_effect(ticket)
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
        if campaign_owner:
            await release_dispatch_owner()
        else:
            if self._pool is not None:
                await self._pool.release(td.agent_id)
            self._active_dispatches.pop(td.task_id, None)
        await self._handle_task_failure(
            td=td,
            task=task,
            error=error,
            source="timeout",
        )
    except asyncio.CancelledError:
        if not campaign_owner:
            raise
        pre_effect, ticket = prepare_campaign_before_effect()
        recovered = await asyncio.shield(
            finish_campaign_before_effect(ticket)
        )
        if pre_effect:
            logger.error(
                "Campaign task %s cancelled before provider boundary; recovered=%s",
                td.task_id,
                recovered,
            )
        else:
            await asyncio.shield(release_dispatch_owner())
        raise
    except Exception as exc:
        if campaign_owner:
            pre_effect, ticket = prepare_campaign_before_effect()
            if pre_effect:
                recovered = await finish_campaign_before_effect(ticket)
                logger.exception(
                    "Campaign task %s failed before provider boundary; recovered=%s",
                    td.task_id,
                    recovered,
                )
                if recovered:
                    return
                raise
        logger.exception("Task %s failed: %s", td.task_id, exc)
        if campaign_owner:
            await release_dispatch_owner()
        else:
            if self._pool is not None:
                await self._pool.release(td.agent_id)
            self._active_dispatches.pop(td.task_id, None)
        await self._handle_task_failure(
            td=td,
            task=task,
            error=str(exc),
            source="execution_error",
        )
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
