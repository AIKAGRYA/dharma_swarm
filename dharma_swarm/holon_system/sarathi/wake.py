"""Sarathi wake organ (PR-S2): the work-fn a governed wake cycle runs.

``make_wake_work_fn`` binds injected dependencies and returns an async
``agent_runner(name) -> (task, reply)`` compatible with
``dharma_swarm.holon_runtime.holon_wake_cycle``. One wake unit is:

    load boot pack -> build_plan -> delegate_all -> sweep_responses
    -> build_operator_brief v2 -> brief_sink -> closeback

Gate-9 thin-source invariant: this module holds NO runtime liveness
constants, paths, schedules, or ``wake_loop_active`` claims — the runtime
wrapper (outside the repo) supplies the boot-pack loader, mailbox, invoker,
brief sink, and closeback, and only runtime proof may ever claim liveness.
The reply string deliberately avoids outcome-claim verbs (see
``holon_bridge._OUTCOME_RE``): an unproven "done" would be governed into
``halted:unverified`` — correctly — so the reply points at the brief ref and
lets receipts speak.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from dharma_swarm.operator_core.autonomy_dial import AutonomyLevel

from .brief import build_operator_brief
from .delegate import DelegationOutcome, delegate_all

from .plan import BootPack, build_plan
from .pulse import sarathi_pulse

# Consumption markers live beside the mailbox state so a completed response is
# reported in exactly ONE brief (Greptile P1: an un-cursored sweep re-counted
# every prior completion in every later brief).
SWEPT_MARKER_DIRNAME = "sarathi_swept_responses"


def _swept_marker_path(mailbox: Any, task_id: str) -> Path:
    return Path(mailbox.queue_root) / SWEPT_MARKER_DIRNAME / f"{task_id}.json"


def sweep_responses(mailbox: Any, *, sender: str = "sarathi") -> list[dict[str, Any]]:
    """Return this sender's NEWLY-completed responses (not yet reported).

    A projection over the mailbox for ``responded`` tasks this sender sent,
    minus any already carrying a consumption marker. This call does NOT write
    markers — the caller marks them consumed only after the brief that reports
    them is durably recorded (see ``mark_responses_consumed``), so a reporting
    failure re-surfaces the response next wake rather than dropping it.
    """
    if mailbox is None:
        return []
    swept: list[dict[str, Any]] = []
    for task in mailbox.list_tasks(status="responded"):
        if task.sender != sender:
            continue
        if _swept_marker_path(mailbox, task.task_id).exists():
            continue
        swept.append(
            {
                "task_id": task.task_id,
                "summary": task.summary,
                "responder": task.claimed_by or "",
                "responded_at": task.responded_at,
                "response_ref": task.response_ref,
            }
        )
    return swept


def mark_responses_consumed(mailbox: Any, responses: Sequence[Mapping[str, Any]]) -> None:
    """Write a consumption marker per reported response (idempotent)."""
    if mailbox is None:
        return
    for response in responses:
        task_id = str(response.get("task_id") or "")
        if not task_id:
            continue
        path = _swept_marker_path(mailbox, task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"task_id": task_id, "reported": True}, sort_keys=True) + "\n",
            encoding="utf-8",
        )


async def run_wake_unit(
    *,
    load_boot_pack: Callable[[], BootPack],
    mailbox: Any = None,
    invoker: Any = None,
    level: AutonomyLevel | None = None,
    operator_reachable: bool = False,
    sender: str = "sarathi",
    context_id: str = "sarathi-wake",
    brief_sink: Callable[[str], str] | None = None,
    closeback: Callable[[Sequence[DelegationOutcome], str], None] | None = None,
    audit: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """Run ONE wake unit and return ``(task, reply)`` for the wake cycle.

    Missing collaborators degrade honestly: no ``brief_sink`` means the brief
    is rendered but unrecorded (ref ``unrecorded``); ``closeback`` failures
    are surfaced in the reply, never swallowed into a success claim.
    """
    # Off the event loop. The loader does blocking I/O -- it lists the mailbox
    # and (since the memory organ landed) performs a governed memory read across
    # registered surfaces. Called inline it stalled the loop for as long as the
    # slowest surface took, so delegation and control work could not be serviced
    # meanwhile; Greptile measured 201ms of blocked control against a 250ms
    # preview. An exception handler does not help here, because a slow read is
    # not an error. Offloading the whole loader also covers the mailbox listing.
    pack = await asyncio.to_thread(load_boot_pack)
    plan = build_plan(pack)
    outcomes = await delegate_all(
        plan,
        level=level,
        mailbox=mailbox,
        invoker=invoker,
        operator_reachable=operator_reachable,
        sender=sender,
        context_id=context_id,
    )
    responses = sweep_responses(mailbox, sender=sender)
    effective_audit = audit if audit is not None else pack.audit
    brief = build_operator_brief(
        sarathi_pulse(pack.roster),
        outcomes=outcomes,
        responses=responses,
        audit=effective_audit,
        memory=pack.memory,
    )

    # Dispatch above already happened. A brief-persistence failure must NOT
    # escape this function (that would make holon_wake_cycle record
    # halted:error and skip closeback, so a later wake re-dispatches the same
    # work — Codex P1). Contain the sink failure, still close back the
    # outcomes, and only mark responses consumed when the brief that reports
    # them was actually recorded.
    brief_recorded = False
    if brief_sink is None:
        brief_ref = "unrecorded"
    else:
        try:
            brief_ref = str(brief_sink(brief))
            brief_recorded = True
        except Exception as exc:  # noqa: BLE001 - contained, never lost work
            brief_ref = f"unrecorded:brief_sink_error:{str(exc)[:100]}"

    if brief_recorded:
        mark_responses_consumed(mailbox, responses)

    closeback_note = "closeback=none"
    if closeback is not None:
        try:
            closeback(outcomes, brief_ref)
            closeback_note = "closeback=recorded"
        except Exception as exc:  # noqa: BLE001 - surfaced, never swallowed
            closeback_note = f"closeback=error:{str(exc)[:120]}"

    counts: dict[str, int] = {}
    for outcome in outcomes:
        counts[outcome.status] = counts.get(outcome.status, 0) + 1
    ledger = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "empty plan"
    task = f"sarathi wake unit ({context_id})"
    reply = (
        f"wake unit ran with ledger [{ledger}]; responses swept={len(responses)}; "
        f"brief ref={brief_ref}; {closeback_note}"
    )
    return task, reply


def make_wake_work_fn(
    *,
    load_boot_pack: Callable[[], BootPack],
    **bound: Any,
) -> Callable[[str], Any]:
    """Bind dependencies and return an ``agent_runner`` for the wake cycle."""
    fixed_context = bound.pop("context_id", None)

    async def _work(name: str) -> tuple[str, str]:
        return await run_wake_unit(
            load_boot_pack=load_boot_pack,
            context_id=fixed_context or f"sarathi-wake:{name}",
            **bound,
        )

    return _work


__all__ = [
    "sweep_responses",
    "mark_responses_consumed",
    "run_wake_unit",
    "make_wake_work_fn",
]
