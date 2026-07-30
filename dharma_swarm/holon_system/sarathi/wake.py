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

from typing import Any, Callable, Mapping, Sequence

from dharma_swarm.operator_core.autonomy_dial import AutonomyLevel

from .brief import build_operator_brief
from .delegate import DelegationOutcome, delegate_all
from .plan import BootPack, build_plan
from .pulse import sarathi_pulse


def sweep_responses(mailbox: Any, *, sender: str = "sarathi") -> list[dict[str, Any]]:
    """Collect terminal responses to tasks this sender delegated.

    Pure projection over the mailbox: tasks with status ``responded`` whose
    ``sender`` matches. Returns plain dicts for the brief's completed rows.
    """
    if mailbox is None:
        return []
    swept: list[dict[str, Any]] = []
    for task in mailbox.list_tasks(status="responded"):
        if task.sender != sender:
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
    pack = load_boot_pack()
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
    )
    brief_ref = "unrecorded"
    if brief_sink is not None:
        brief_ref = str(brief_sink(brief))

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


__all__ = ["sweep_responses", "run_wake_unit", "make_wake_work_fn"]
