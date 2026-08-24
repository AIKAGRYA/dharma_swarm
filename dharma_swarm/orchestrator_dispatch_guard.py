"""Bounded assignment and shutdown custody for :mod:`dharma_swarm.orchestrator`."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, NamedTuple


class CampaignRecoveryTicket(NamedTuple):
    task_id: str
    principal: str
    generation: int


def require_admission(host: Any) -> None:
    """Fence every post-await setup prefix after shutdown begins."""
    if getattr(host, "_stopping", False):
        raise asyncio.CancelledError


def prepare_campaign_before_effect_recovery(
    host: Any,
    td: Any,
    principal: str,
    token: dict[str, Any],
    *,
    allow_uninstalled_active: bool,
    active_owner_key: str,
) -> CampaignRecoveryTicket | None:
    """Revoke provider authority into a census-visible recovery tombstone."""
    matching_keys = [
        key for key, registered in host._campaign_reservations.items()
        if registered is token
    ]
    key = matching_keys[0] if len(matching_keys) == 1 else None
    key_shape_exact = bool(
        isinstance(key, tuple) and len(key) == 3
        and isinstance(key[0], str) and isinstance(key[1], str)
        and type(key[2]) is int
    )
    task_id = key[0] if key_shape_exact else ""
    registered_principal = key[1] if key_shape_exact else ""
    generation = key[2] if key_shape_exact else -1
    active = host._active_dispatches.get(task_id) if task_id else None
    active_installed = bool(td.metadata.get(active_owner_key))
    owns_reservation = getattr(host._pool, "owns_reservation", None)
    try:
        pool_exact = bool(
            key_shape_exact and callable(owns_reservation)
            and owns_reservation(
                registered_principal, task_id, reservation_token=token,
            )
        )
    except Exception:
        pool_exact = False
    active_exact = active is td or (
        allow_uninstalled_active and not active_installed and active is None
    )
    token_exact = bool(
        token.get("attempt_generation") == generation
        and token.get("provider_task_scheduled") is False
    )
    td_exact = bool(
        key_shape_exact and td.task_id == task_id
        and td.agent_id == registered_principal == principal
        and td.metadata.get("attempt_generation") == generation
    )
    ticket = (
        CampaignRecoveryTicket(task_id, principal, generation)
        if td_exact and active_exact and pool_exact and token_exact else None
    )
    local_custody = bool(
        matching_keys
        or any(owner is td for owner in host._active_dispatches.values())
    )
    if local_custody:
        existing_recovery = host._campaign_recovery_owners.get(id(token))
        if (
            isinstance(existing_recovery, list)
            and len(existing_recovery) == 4
            and existing_recovery[0] is td
            and existing_recovery[1] is token
        ):
            existing_recovery[2] = ticket
        else:
            host._campaign_recovery_owners[id(token)] = [td, token, ticket, False]
    for active_task_id, owner in tuple(host._active_dispatches.items()):
        if owner is td:
            host._active_dispatches.pop(active_task_id, None)
    for matching_key in matching_keys:
        if host._campaign_reservations.get(matching_key) is token:
            host._campaign_reservations.pop(matching_key, None)
    return ticket


async def finish_campaign_before_effect_recovery(
    host: Any,
    token: dict[str, Any],
    ticket: CampaignRecoveryTicket,
) -> bool:
    """Release and repair Board state before clearing the tombstone."""
    recovery_key = id(token)
    entry = host._campaign_recovery_owners.get(recovery_key)
    if (
        not isinstance(entry, list) or len(entry) != 4
        or entry[1] is not token or entry[2] is not ticket
    ):
        return False
    if entry[3] is not True:
        release = getattr(host._pool, "release_reservation", None)
        if not callable(release) or not await release(
            ticket.principal, ticket.task_id, reservation_token=token,
        ):
            return False
        entry[3] = True
    task = await host._safe_get_task(ticket.task_id)
    if not host._campaign_recovery_task_is_exact(
        task, ticket.task_id, ticket.principal, ticket.generation,
    ):
        return False
    outcome = await host._board.resolve_campaign_pre_effect_failure(
        ticket.task_id,
        expected_status=task.status,
        expected_agent_id=task.assigned_to,
        expected_metadata=dict(task.metadata),
        authenticated_principal=ticket.principal,
        provider_task_scheduled=False,
    )
    resolved = outcome in {"pending", "indeterminate"}
    if resolved and host._campaign_recovery_owners.get(recovery_key) is entry:
        host._campaign_recovery_owners.pop(recovery_key, None)
    return resolved


async def shield_recovery(
    host: Any,
    recovery_key: str,
    factory: Callable[[], Awaitable[bool]],
) -> bool:
    """Shield one cleanup while keeping its Task inside the stop census."""
    recovery_task = host._recovery_tasks.get(recovery_key)
    if recovery_task is None:
        recovery_task = asyncio.create_task(
            factory(),
            name=f"dispatch-cleanup-{recovery_key.split(chr(0), 2)[1][:16]}",
        )
        host._recovery_tasks[recovery_key] = recovery_task
    try:
        return bool(await asyncio.shield(recovery_task))
    finally:
        if recovery_task.done() and host._recovery_tasks.get(recovery_key) is recovery_task:
            host._recovery_tasks.pop(recovery_key, None)


async def assign_dispatch(
    host: Any,
    td: Any,
    *,
    authenticated_principal_id: str,
    reservation_token: dict[str, Any] | None,
    campaign_effect_fence: Callable[[], Awaitable[None]] | None,
    logger: Any,
) -> bool:
    """Track setup as custody so shutdown can cancel and join it."""
    if getattr(host, "_stopping", False):
        return False
    recovery_owners = (
        *host._generic_recovery_owners.values(),
        *host._campaign_recovery_owners.values(),
    )
    if any(
        isinstance(entry, list) and entry and entry[0].task_id == td.task_id
        for entry in recovery_owners
    ):
        return False
    current = asyncio.current_task()
    if current is None:
        raise RuntimeError("dispatch assignment lacks an asyncio task owner")
    prior = host._assignment_tasks.get(td.task_id)
    if prior is not None and not prior.done():
        raise RuntimeError("task already has an in-progress assignment owner")
    if any(owner is current for owner in host._assignment_tasks.values()):
        raise RuntimeError("asyncio task already owns an in-progress assignment")
    host._assignment_tasks[td.task_id] = current
    try:
        accepted = await host._assign_dispatch_inner(
            td,
            authenticated_principal_id=authenticated_principal_id,
            reservation_token=reservation_token,
            campaign_effect_fence=campaign_effect_fence,
        )
        if accepted and getattr(host, "_stopping", False):
            raise asyncio.CancelledError
        return accepted
    except BaseException as exc:
        if not authenticated_principal_id:
            from dharma_swarm.orchestrator_execution import (
                abort_generic_dispatch_setup,
            )

            try:
                await shield_recovery(
                    host,
                    f"generic\0{td.task_id}",
                    lambda cause=exc: abort_generic_dispatch_setup(host, td, cause),
                )
            except BaseException as cleanup_exc:
                logger.error("Generic dispatch cleanup failed: %r", cleanup_exc)
        raise
    finally:
        if host._assignment_tasks.get(td.task_id) is current:
            host._assignment_tasks.pop(td.task_id, None)


async def _cancel_and_join(
    tasks: list[asyncio.Task[Any]],
    *,
    deadline: float,
) -> int:
    tasks = list(dict.fromkeys(tasks))
    cancelled = 0
    for task in tasks:
        if not task.done():
            task.cancel()
            cancelled += 1
    pending = [task for task in tasks if not task.done()]
    if pending:
        remaining = max(0.0, deadline - asyncio.get_running_loop().time())
        await asyncio.wait(
            pending,
            timeout=remaining,
            return_when=asyncio.ALL_COMPLETED,
        )
    for task in tasks:
        if task.done():
            try:
                task.result()
            except (asyncio.CancelledError, Exception):
                pass
    return cancelled


async def _graceful_stop_once(
    host: Any,
    timeout: float,
    *,
    logger: Any,
) -> dict[str, Any]:
    """Stop admission, join setup first, and retain every live owner."""
    host._running = False
    host._stopping = True
    deadline = asyncio.get_running_loop().time() + max(0.0, timeout)

    assignments = list(host._assignment_tasks.items())
    assignment_cancelled = await _cancel_and_join(
        [task for _, task in assignments],
        deadline=deadline,
    )
    assignment_live = {
        task_id
        for task_id, task in assignments
        if not task.done() and host._assignment_tasks.get(task_id) is task
    }

    snapshot = list(host._running_tasks.items())
    completed = sum(task.done() for _, task in snapshot)
    cancelled = await _cancel_and_join(
        [task for _, task in snapshot],
        deadline=deadline,
    )
    for task_id, task in snapshot:
        if not task.done() or host._running_tasks.get(task_id) is not task:
            continue
        host._running_tasks.pop(task_id, None)
        owner = host._running_dispatch_owners.get(task_id)
        if owner is not None and owner[0] is task:
            active_is_owner = host._active_dispatches.get(task_id) is owner[1]
            if host._pool is None or not active_is_owner:
                host._running_dispatch_owners.pop(task_id, None)
                if host._pool is None and active_is_owner:
                    host._active_dispatches.pop(task_id, None)

    running_live = {
        task_id
        for task_id, task in host._running_tasks.items()
        if not task.done()
    }
    recovered = 0

    def collect_recovery_results() -> None:
        nonlocal recovered
        for recovery_key, recovery_task in tuple(host._recovery_tasks.items()):
            if not recovery_task.done():
                continue
            if host._recovery_tasks.get(recovery_key) is recovery_task:
                host._recovery_tasks.pop(recovery_key, None)
            try:
                recovered += bool(recovery_task.result())
            except (asyncio.CancelledError, Exception):
                logger.exception("Dispatch recovery failed for %s", recovery_key)

    collect_recovery_results()
    for task_id, td in tuple(host._active_dispatches.items()):
        if task_id in assignment_live or task_id in running_live:
            continue
        owner = host._running_dispatch_owners.get(task_id)
        if owner is not None and owner[1] is td and not owner[0].done():
            continue
        from dharma_swarm.orchestrator_execution import abort_generic_dispatch_setup

        recovery_key = f"generic\0{task_id}"
        if recovery_key not in host._recovery_tasks:
            error = RuntimeError("graceful stop before background execution")
            host._recovery_tasks[recovery_key] = asyncio.create_task(
                abort_generic_dispatch_setup(host, td, error),
                name=f"recover-generic-{task_id[:16]}",
            )
    for token_key, entry in tuple(host._campaign_recovery_owners.items()):
        if not isinstance(entry, list) or len(entry) != 4 or entry[2] is None:
            continue
        td, token, ticket, _ = entry
        if td.task_id in assignment_live or td.task_id in running_live:
            continue
        recovery_key = f"campaign\0{td.task_id}\0{token_key}"
        if recovery_key not in host._recovery_tasks:
            host._recovery_tasks[recovery_key] = asyncio.create_task(
                finish_campaign_before_effect_recovery(host, token, ticket),
                name=f"recover-campaign-{td.task_id[:16]}",
            )
    pending_recovery = [
        task for task in host._recovery_tasks.values() if not task.done()
    ]
    if pending_recovery:
        remaining = max(0.0, deadline - asyncio.get_running_loop().time())
        await asyncio.wait(
            list(dict.fromkeys(pending_recovery)),
            timeout=remaining,
            return_when=asyncio.ALL_COMPLETED,
        )
    collect_recovery_results()
    for task_id, owner in tuple(host._running_dispatch_owners.items()):
        if (
            owner[0].done()
            and host._active_dispatches.get(task_id) is not owner[1]
        ):
            host._running_dispatch_owners.pop(task_id, None)

    unreleased = set(host._active_dispatches) - running_live - assignment_live
    recovery_live = {
        recovery_key.split("\0", 2)[1]
        for recovery_key, task in host._recovery_tasks.items()
        if not task.done() and "\0" in recovery_key
    }
    campaign_owners = {
        entry[0].task_id: entry[0]
        for entry in host._campaign_recovery_owners.values()
        if isinstance(entry, list) and len(entry) == 4
    }
    generic_owners = {
        entry[0].task_id: entry[0]
        for entry in host._generic_recovery_owners.values()
        if isinstance(entry, list) and len(entry) == 2
    }
    campaign_live = set(campaign_owners)
    generic_live = set(generic_owners)
    live_ids = sorted(
        running_live | assignment_live | unreleased | recovery_live
        | campaign_live | generic_live
    )
    summary: dict[str, Any] = {"cancelled": cancelled, "completed": completed}
    if assignment_cancelled:
        summary["assignment_cancelled"] = assignment_cancelled
    if recovered:
        summary["recovered"] = recovered
    if unreleased:
        summary["unreleased_owner_task_ids"] = sorted(unreleased)
    if recovery_live:
        summary["recovery_pending_task_ids"] = sorted(recovery_live)
    if campaign_live:
        summary["campaign_recovery_task_ids"] = sorted(campaign_live)
    if generic_live:
        summary["indeterminate_custody_task_ids"] = sorted(generic_live)
    if live_ids:
        summary["live"] = len(live_ids)
        summary["live_task_ids"] = live_ids
        summary["live_owners"] = {
            task_id: getattr(
                host._active_dispatches.get(task_id)
                or campaign_owners.get(task_id)
                or generic_owners.get(task_id),
                "agent_id",
                None,
            )
            for task_id in live_ids
        }
        logger.error("Orchestrator stop retained live custody: %s", summary)
    logger.info(
        "Orchestrator graceful stop: %d running cancelled, %d setup cancelled, "
        "%d already completed, %d live",
        cancelled,
        assignment_cancelled,
        completed,
        len(live_ids),
    )
    return summary


async def graceful_stop(
    host: Any,
    timeout: float,
    *,
    logger: Any,
) -> dict[str, Any]:
    """Share one cancellation-resistant stop operation among all callers."""
    current = asyncio.current_task()
    tracked = tuple(host._assignment_tasks.values()) + tuple(
        host._running_tasks.values()
    )
    if current is not None and any(current is task for task in tracked):
        raise RuntimeError("tracked dispatch owner cannot synchronously stop itself")
    operation = host._stop_operation
    if operation is None or operation.done():
        operation = asyncio.create_task(
            _graceful_stop_once(host, timeout, logger=logger),
            name="orchestrator-graceful-stop",
        )
        host._stop_operation = operation
    try:
        return await asyncio.shield(operation)
    finally:
        if operation.done() and host._stop_operation is operation:
            host._stop_operation = None


__all__ = ["assign_dispatch", "graceful_stop", "require_admission", "shield_recovery"]
