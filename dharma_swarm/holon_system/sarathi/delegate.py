"""Gate-enforced delegation organ for the Sarathi apex (PR-S1).

Every planned delegation faces the deterministic reversibility gate BEFORE any
channel is touched — a NEVER_AUTO hit or an IRREVERSIBLE/OPERATOR_ONLY class
is hard-blocked and logged, never dispatched, at every dial level. The
operator dial (``dharma_swarm.operator_core.autonomy_dial``) is the ceiling on
what admissible work may EXECUTE; it never widens the gate.

Channels:

- ``mailbox`` — a :class:`~dharma_swarm.roaming_mailbox.RoamingMailbox` task;
  the claim fence (exclusive receipt) is the execution lease, so NEEDS_LEASE
  work belongs here.
- ``invoke`` — a direct ``invoke_agent`` call producing an EvidenceReceipt;
  reserved for gate-grade REVERSIBLE_SAFE work at dispatch level or above.
- ``merge_intent`` — a mailbox task addressed to Merge Master Mike's lane;
  Sarathi never merges or pushes (both are NEVER_AUTO). The merge itself is
  decided by Mike under the tier policy's decorrelated-review door.

Autonomy dial semantics here:

- ``shadow``: nothing is written anywhere; every admissible item is ``logged``.
- ``propose``: proposals are recorded in the returned outcome ledger (which
  the operator brief renders), NOT in the shared mailbox — writing a queued
  mailbox task is already dispatch, because live pollers claim queued tasks.
- ``dispatch``: mailbox and invoke channels go live; merge intents stay
  proposals.
- ``full``: merge intents are enqueued into Mike's lane as well.

Every outcome carries the full gate decision — no silent action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import dataclasses
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from dharma_swarm.operator_core.autonomy_dial import (
    AutonomyLevel,
    current_autonomy_level,
    may_arm_automerge,
    may_dispatch_work,
    may_write_proposals,
)
from dharma_swarm.operator_core.reversibility_gate import ActionClass, classify_action

from .plan import PlannedDelegation, plan_dedup_key

GATED_CLASSES = (ActionClass.IRREVERSIBLE, ActionClass.OPERATOR_ONLY)

# Where durable invoke-receipt evidence lands, relative to the mailbox queue
# root. The sakshi auditor resolves invoke receipt_refs here, so a direct
# dispatch leaves resolvable evidence just like a mailbox task does.
INVOKE_RECEIPTS_DIRNAME = "sarathi_invoke_receipts"


def _gate_input(delegation: PlannedDelegation) -> str:
    """The exact text the reversibility gate classifies for one delegation.

    Greptile/Codex P1: classifying only the derived ``action`` let a benign
    ``kind``/``summary`` smuggle an operator-only instruction through the
    ``body``/``metadata`` that the worker actually executes. The gate input
    must cover the COMPLETE payload the recipient receives — except for merge
    intents, whose body/summary are constructed display text handed to Merge
    Master Mike's lane (which re-gates under the tier policy); their caller
    summary/body may legitimately contain "merge" and are not worker-executed.
    """
    parts: list[str] = [delegation.action]
    if delegation.channel != "merge_intent":
        # Non-merge channels deliver summary + body + metadata to a worker that
        # may execute them, so all of it must face the floor. Merge intents
        # carry only a constructed label request to Mike's lane (he re-gates
        # under the tier policy); their caller summary/body AND planner
        # bookkeeping metadata (e.g. sarathi_kind=merge) are not worker-executed
        # — and including that metadata mis-classified the benign label request
        # as a direct "merge" (IRREVERSIBLE), gating every planner-produced
        # merge intent (Codex P1 on PR #1170). Merge intents classify on the
        # constructed action alone.
        parts.extend([delegation.summary, delegation.body])
        for key, value in sorted(delegation.metadata.items()):
            parts.append(f"{key}={value}")
    return "\n".join(str(part) for part in parts if part)


def _persist_invoke_receipt(mailbox: Any, receipt: Any) -> str:
    """Write a durable JSON copy of an EvidenceReceipt; return its resolvable ref.

    Codex P1: ``invoke_agent`` is a pass-through and stores nothing, so a bare
    receipt UUID cannot be resolved after the process exits and the auditor
    would (correctly) flag the dispatched row as unbacked. Persist the receipt
    beside the mailbox state so ``invoke_receipt_exists`` can resolve it.
    """
    receipt_id = str(receipt.receipt_id)
    root = Path(mailbox.queue_root) / INVOKE_RECEIPTS_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{receipt_id}.json"
    payload = dataclasses.asdict(receipt) if dataclasses.is_dataclass(receipt) else {}
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return receipt_id


def invoke_receipt_path(mailbox: Any, receipt_ref: str) -> Path:
    """Resolve the durable path for an invoke receipt_ref (auditor helper)."""
    return Path(mailbox.queue_root) / INVOKE_RECEIPTS_DIRNAME / f"{receipt_ref}.json"


@dataclass(frozen=True)
class DelegationOutcome:
    """Auditable result of one delegation attempt."""

    delegation: PlannedDelegation
    gate: Mapping[str, Any]
    status: str  # "gated" | "logged" | "proposed" | "dispatched" | "failed"
    receipt_ref: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "dharma.sarathi.delegation_outcome.v1",
            "action": self.delegation.action,
            "recipient": self.delegation.recipient,
            "channel": self.delegation.channel,
            "summary": self.delegation.summary,
            "status": self.status,
            "receipt_ref": self.receipt_ref,
            "detail": self.detail,
            "gate": dict(self.gate),
        }


def _task_metadata(
    delegation: PlannedDelegation, gate: Mapping[str, Any], level: AutonomyLevel
) -> dict[str, Any]:
    metadata = dict(delegation.metadata)
    metadata["sarathi"] = {
        "autonomy_level": level.value,
        "planned_channel": delegation.channel,
        "gate_action_class": gate.get("action_class"),
        # Persist the planner's full-identity dedup key so a later wake compares
        # stored keys instead of reconstructing one from divergent task fields
        # (Greptile P1 plan.py L127). Keyed on the delegation, not the augmented
        # task metadata, so it stays stable across dial levels.
        "dedup_key": plan_dedup_key(delegation),
    }
    return metadata


async def _dispatch_invoke(
    delegation: PlannedDelegation,
    gate: Mapping[str, Any],
    *,
    invoker: Any,
    context_id: str,
    mailbox: Any,
) -> DelegationOutcome:
    from dharma_swarm.spine.invoke import invoke_agent
    from dharma_swarm.spine.routing import RoutingDecision

    routing = RoutingDecision(
        agent_id=delegation.recipient,
        reason="sarathi delegation (gate: reversible_safe)",
        router_name="sarathi.delegate",
        context_id=context_id,
        attributes={"gate": dict(gate)},
    )
    receipt = await invoke_agent(
        task={
            "summary": delegation.summary,
            "body": delegation.body,
            "metadata": dict(delegation.metadata),
        },
        agent_id=delegation.recipient,
        context_id=context_id,
        routing=routing,
        invoker=invoker,
    )
    # Durable receipt: the auditor requires a resolvable ref, so persist the
    # EvidenceReceipt beside the mailbox state before reducing it to an id.
    receipt_ref = _persist_invoke_receipt(mailbox, receipt)
    return DelegationOutcome(
        delegation=delegation,
        gate=gate,
        status="dispatched",
        receipt_ref=receipt_ref,
        detail=f"invoke_agent receipt status={receipt.status} (persisted)",
    )


async def delegate_all(
    plan: Sequence[PlannedDelegation],
    *,
    level: AutonomyLevel | None = None,
    mailbox: Any = None,
    invoker: Any = None,
    operator_reachable: bool = False,
    sender: str = "sarathi",
    context_id: str = "sarathi-wake",
) -> list[DelegationOutcome]:
    """Run the gate over every planned delegation, then honor the dial.

    Total and auditable: every input yields exactly one outcome carrying the
    gate decision. Missing infrastructure (no mailbox / no invoker) degrades
    to an honest ``logged`` outcome with the reason in ``detail`` — never a
    silent skip, never a fabricated dispatch.
    """
    effective = level if level is not None else current_autonomy_level()
    outcomes: list[DelegationOutcome] = []
    for delegation in plan:
        # Classify the COMPLETE dispatched payload, not just the derived action
        # (Greptile/Codex P1). Display still uses delegation.action; the gate
        # dict records exactly what was classified.
        decision = classify_action(
            _gate_input(delegation), operator_reachable=operator_reachable
        )
        gate = decision.to_dict()

        # (1) The floor: never-auto / irreversible / operator-only actions are
        # hard-blocked and logged at EVERY dial level.
        if decision.never_auto_hit or decision.action_class in GATED_CLASSES:
            outcomes.append(
                DelegationOutcome(
                    delegation=delegation,
                    gate=gate,
                    status="gated",
                    detail="blocked by reversibility gate; never dispatched",
                )
            )
            continue

        # (2) The ceiling: the dial bounds execution of admissible work.
        if not may_write_proposals(effective):
            outcomes.append(
                DelegationOutcome(
                    delegation=delegation,
                    gate=gate,
                    status="logged",
                    detail=f"autonomy dial {effective.value}: log only",
                )
            )
            continue

        is_merge_intent = delegation.channel == "merge_intent"
        may_go_live = (
            may_arm_automerge(effective)
            if is_merge_intent
            else may_dispatch_work(effective)
        )
        if not may_go_live:
            outcomes.append(
                DelegationOutcome(
                    delegation=delegation,
                    gate=gate,
                    status="proposed",
                    detail=(
                        f"autonomy dial {effective.value}: proposal recorded in "
                        "ledger; dispatch held"
                    ),
                )
            )
            continue

        # (3) Live channels. A channel failure (provider timeout, disk error)
        # must NOT abort the batch — each delegation yields exactly one outcome
        # (Codex P2), so any exception becomes an explicit ``failed`` outcome
        # and the loop continues.
        try:
            # The invoke channel needs a mailbox to persist its receipt
            # durably; without one it cannot leave resolvable evidence, so it
            # falls back to the mailbox path (and is logged if that too is
            # absent) rather than claiming an unbacked dispatch.
            if (
                delegation.channel == "invoke"
                and decision.may_execute_unattended
                and mailbox is not None
                and invoker is not None
            ):
                outcomes.append(
                    await _dispatch_invoke(
                        delegation,
                        gate,
                        invoker=invoker,
                        context_id=context_id,
                        mailbox=mailbox,
                    )
                )
                continue
            # An invoke item without a live invoker is NOT dropped to "logged":
            # it falls through to the leased mailbox below so the planner's
            # invoke channel still executes via a claiming worker (Codex P2 on
            # PR #1170). Only a fully absent mailbox degrades to logged.

            # Everything else admissible rides the mailbox: the claim fence is
            # the execution lease (NEEDS_LEASE work, merge intents, invoke-grade
            # items without a durable receipt sink).
            if mailbox is None:
                outcomes.append(
                    DelegationOutcome(
                        delegation=delegation,
                        gate=gate,
                        status="logged",
                        detail="mailbox channel unavailable: no mailbox injected",
                    )
                )
                continue
            task = mailbox.enqueue_task(
                recipient=delegation.recipient,
                sender=sender,
                summary=delegation.summary,
                body=delegation.body,
                metadata=_task_metadata(delegation, gate, effective),
                depends_on=list(delegation.depends_on),
            )
            outcomes.append(
                DelegationOutcome(
                    delegation=delegation,
                    gate=gate,
                    status="dispatched",
                    receipt_ref=task.task_id,
                    detail=f"mailbox task enqueued (status={task.status})",
                )
            )
        except Exception as exc:  # noqa: BLE001 - one bad channel != lost batch
            outcomes.append(
                DelegationOutcome(
                    delegation=delegation,
                    gate=gate,
                    status="failed",
                    detail=f"channel dispatch failed: {str(exc)[:160]}",
                )
            )
    return outcomes


__all__ = [
    "GATED_CLASSES",
    "INVOKE_RECEIPTS_DIRNAME",
    "DelegationOutcome",
    "delegate_all",
    "invoke_receipt_path",
]
