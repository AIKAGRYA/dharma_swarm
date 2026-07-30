"""Sarathi delegation organ (PR-S1): gate before dial, dial before channel.

The load-bearing invariants under test:
- never-auto / irreversible / operator-only actions are ``gated`` at EVERY
  dial level — no channel is touched;
- the dial is a ceiling on admissible work: shadow logs, propose records
  proposals in the ledger (not the shared mailbox), dispatch/full execute;
- every outcome carries the full gate decision (no silent action);
- each live channel produces a receipt reference (mailbox task id or
  EvidenceReceipt id).
"""

from __future__ import annotations

from dataclasses import replace

from dharma_swarm.holon_system.sarathi.delegate import delegate_all
from dharma_swarm.holon_system.sarathi.plan import PlannedDelegation
from dharma_swarm.operator_core.autonomy_dial import AutonomyLevel
from dharma_swarm.roaming_mailbox import RoamingMailbox
from dharma_swarm.spine.receipt import EvidenceReceipt

SAFE_INVOKE = PlannedDelegation(
    action="check the arena scoreboard status",
    recipient="codex_composer",
    channel="invoke",
    summary="scoreboard status check",
    body="report current arena scoreboard state",
)
LEASED_BUILD = PlannedDelegation(
    action="build: extend the chamber gym battery",
    recipient="hermes-m5",
    channel="mailbox",
    summary="extend the chamber gym battery",
    body="add one scenario to the gym battery",
)
MERGE_INTENT = PlannedDelegation(
    action="queue unattended-lane label request for pull request #7",
    recipient="merge_master_mike",
    channel="merge_intent",
    summary="label PR 7 for the unattended lane",
    body="request automerge label on PR 7",
)
NEVER_AUTO = PlannedDelegation(
    action="git push origin main",
    recipient="codex_composer",
    channel="invoke",
    summary="push directly",
    body="push",
)
IRREVERSIBLE = PlannedDelegation(
    action="deploy the dashboard to the cluster",
    recipient="codex_composer",
    channel="mailbox",
    summary="deploy dashboard",
    body="deploy",
)


class RecordingInvoker:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, *, task, agent_id, context_id, routing) -> EvidenceReceipt:
        self.calls.append(
            {"task": task, "agent_id": agent_id, "context_id": context_id, "routing": routing}
        )
        return EvidenceReceipt(agent_id=agent_id, context_id=context_id, status="ok")


async def test_never_auto_is_gated_at_every_dial_level(tmp_path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path)
    invoker = RecordingInvoker()
    for level in AutonomyLevel:
        outcomes = await delegate_all(
            [NEVER_AUTO, IRREVERSIBLE], level=level, mailbox=mailbox, invoker=invoker
        )
        assert [o.status for o in outcomes] == ["gated", "gated"]
        assert outcomes[0].gate["never_auto_hit"] == "git push"
        assert outcomes[1].gate["action_class"] == "irreversible"
    assert invoker.calls == []
    assert mailbox.list_tasks() == []


async def test_shadow_logs_only_and_writes_nothing(tmp_path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path)
    outcomes = await delegate_all(
        [SAFE_INVOKE, LEASED_BUILD, MERGE_INTENT],
        level=AutonomyLevel.SHADOW,
        mailbox=mailbox,
        invoker=RecordingInvoker(),
    )
    assert {o.status for o in outcomes} == {"logged"}
    assert mailbox.list_tasks() == []


async def test_propose_records_proposals_not_mailbox_writes(tmp_path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path)
    outcomes = await delegate_all(
        [SAFE_INVOKE, LEASED_BUILD, MERGE_INTENT],
        level=AutonomyLevel.PROPOSE,
        mailbox=mailbox,
        invoker=RecordingInvoker(),
    )
    assert [o.status for o in outcomes] == ["proposed", "proposed", "proposed"]
    # A queued mailbox task is already dispatch (pollers claim it): propose
    # must leave the shared mailbox untouched.
    assert mailbox.list_tasks() == []


async def test_dispatch_executes_work_but_holds_merge_intents(tmp_path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path)
    invoker = RecordingInvoker()
    outcomes = await delegate_all(
        [SAFE_INVOKE, LEASED_BUILD, MERGE_INTENT],
        level=AutonomyLevel.DISPATCH,
        mailbox=mailbox,
        invoker=invoker,
    )
    by_summary = {o.delegation.summary: o for o in outcomes}
    invoke_outcome = by_summary["scoreboard status check"]
    assert invoke_outcome.status == "dispatched"
    assert invoke_outcome.receipt_ref  # EvidenceReceipt id
    assert len(invoker.calls) == 1
    mailbox_outcome = by_summary["extend the chamber gym battery"]
    assert mailbox_outcome.status == "dispatched"
    assert mailbox_outcome.receipt_ref.startswith("mbx_")
    merge_outcome = by_summary["label PR 7 for the unattended lane"]
    assert merge_outcome.status == "proposed"
    # Only the leased build reached the mailbox; the merge intent did not.
    assert [t.summary for t in mailbox.list_tasks()] == [
        "extend the chamber gym battery"
    ]


async def test_full_arms_merge_intents_into_mikes_lane(tmp_path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path)
    outcomes = await delegate_all(
        [MERGE_INTENT], level=AutonomyLevel.FULL, mailbox=mailbox
    )
    assert outcomes[0].status == "dispatched"
    task = mailbox.list_tasks()[0]
    assert task.recipient == "merge_master_mike"
    assert task.metadata["sarathi"]["planned_channel"] == "merge_intent"


async def test_leased_grade_invoke_items_ride_the_mailbox(tmp_path) -> None:
    # An invoke-channel item whose action only earns NEEDS_LEASE must not be
    # invoked directly — the claim fence is the lease.
    leased_invoke = replace(
        SAFE_INVOKE, action="edit the arena config file", summary="arena config edit"
    )
    mailbox = RoamingMailbox(queue_root=tmp_path)
    invoker = RecordingInvoker()
    outcomes = await delegate_all(
        [leased_invoke], level=AutonomyLevel.FULL, mailbox=mailbox, invoker=invoker
    )
    assert outcomes[0].status == "dispatched"
    assert outcomes[0].receipt_ref.startswith("mbx_")
    assert invoker.calls == []


async def test_missing_infrastructure_degrades_honestly(tmp_path) -> None:
    outcomes = await delegate_all(
        [SAFE_INVOKE, LEASED_BUILD], level=AutonomyLevel.FULL
    )
    assert [o.status for o in outcomes] == ["logged", "logged"]
    assert "no invoker injected" in outcomes[0].detail
    assert "no mailbox injected" in outcomes[1].detail


async def test_every_outcome_carries_the_gate_decision(tmp_path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path)
    outcomes = await delegate_all(
        [SAFE_INVOKE, NEVER_AUTO, MERGE_INTENT],
        level=AutonomyLevel.PROPOSE,
        mailbox=mailbox,
    )
    for outcome in outcomes:
        assert outcome.gate["schema_version"] == "dharma.reversibility_gate_decision.v1"
        assert outcome.to_dict()["gate"]["action_class"]


async def test_dial_env_default_is_propose(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DGC_SARATHI_AUTONOMY", raising=False)
    mailbox = RoamingMailbox(queue_root=tmp_path)
    outcomes = await delegate_all([LEASED_BUILD], mailbox=mailbox)
    assert outcomes[0].status == "proposed"
    assert mailbox.list_tasks() == []
