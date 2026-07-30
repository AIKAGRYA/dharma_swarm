"""Sarathi wake organ (PR-S2): one wake unit, end to end, thin and honest.

Covers: the full unit flow (boot pack -> plan -> delegate -> sweep -> brief
-> sink -> closeback), composition with holon_wake_cycle (including the
reversibility-gate halt and the outcome-claim artifact gate), the brief v2
delegation ledger, and the no-fabrication audit line.
"""

from __future__ import annotations

from pathlib import Path

from dharma_swarm.holon_runtime import holon_wake_cycle
from dharma_swarm.holon_system.sarathi.brief import build_operator_brief
from dharma_swarm.holon_system.sarathi.plan import BootPack
from dharma_swarm.holon_system.sarathi.wake import (
    make_wake_work_fn,
    run_wake_unit,
    sweep_responses,
)
from dharma_swarm.operator_core.autonomy_dial import AutonomyLevel
from dharma_swarm.roaming_mailbox import RoamingMailbox

ROSTER = ("hermes-m5", "codex_composer")


def _pack(**overrides) -> BootPack:
    base = dict(
        roster=ROSTER,
        open_items=(
            {"kind": "build", "summary": "extend gym battery"},
            {"kind": "merge", "summary": "land PR", "pr": 7},
        ),
    )
    base.update(overrides)
    return BootPack(**base)


async def test_wake_unit_runs_full_flow_with_ledger_and_closeback(tmp_path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path)
    briefs: list[str] = []
    closebacks: list[tuple[int, str]] = []

    task, reply = await run_wake_unit(
        load_boot_pack=lambda: _pack(
            open_items=(
                {"kind": "build", "summary": "extend gym battery"},
                {"kind": "build", "summary": "refactor arena config",
                 "body": "x"},
            )
        ),
        mailbox=mailbox,
        level=AutonomyLevel.DISPATCH,
        brief_sink=lambda text: (briefs.append(text), "brief-ref-1")[1],
        closeback=lambda outcomes, ref: closebacks.append((len(outcomes), ref)),
    )
    assert task.startswith("sarathi wake unit")
    assert "brief ref=brief-ref-1" in reply
    assert "closeback=recorded" in reply
    assert closebacks == [(2, "brief-ref-1")]
    # Both actions grade MEDIUM (unknown/refactor vocabulary) -> leased ->
    # they ride the mailbox at dispatch level.
    assert len(mailbox.list_tasks()) == 2
    brief = briefs[0]
    assert "## Delegation ledger" in brief
    assert "Planned=2" in brief


async def test_wake_unit_gates_hot_actions_and_says_so_in_ledger(tmp_path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path)
    briefs: list[str] = []
    _, reply = await run_wake_unit(
        load_boot_pack=lambda: BootPack(
            roster=ROSTER,
            open_items=(
                {"kind": "build", "summary": "force push the archive branch"},
            ),
        ),
        mailbox=mailbox,
        level=AutonomyLevel.FULL,
        brief_sink=lambda text: (briefs.append(text), "ref")[1],
    )
    assert "gated=1" in reply
    assert mailbox.list_tasks() == []
    assert "[gated] force push the archive branch" in briefs[0]


async def test_wake_unit_composes_with_holon_wake_cycle(tmp_path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path)
    work = make_wake_work_fn(
        load_boot_pack=lambda: _pack(
            open_items=({"kind": "review", "summary": "review arena report"},)
        ),
        mailbox=mailbox,
        level=AutonomyLevel.PROPOSE,
        brief_sink=lambda text: "ref-cycle",
    )
    result = await holon_wake_cycle(
        "sarathi",
        work,
        spent_usd=0.0,
        cap_usd=1.0,
        agents_root=Path(tmp_path) / "agents",
        persist=False,
    )
    # The reply avoids outcome-claim verbs, so the artifact gate must not
    # demote the cycle to halted:unverified.
    assert result["status"] == "ran"
    assert "proposed=1" in result["reply"]


async def test_planned_action_gate_still_halts_the_cycle(tmp_path) -> None:
    work = make_wake_work_fn(
        load_boot_pack=lambda: BootPack(roster=ROSTER),
        level=AutonomyLevel.SHADOW,
    )
    result = await holon_wake_cycle(
        "sarathi",
        work,
        spent_usd=0.0,
        cap_usd=1.0,
        agents_root=Path(tmp_path) / "agents",
        persist=False,
        planned_action="git push origin main",
    )
    assert result["status"] == "halted:reversibility_gate"
    assert result["reversibility_gate"]["never_auto_hit"] == "git push"


async def test_sweep_responses_projects_only_this_senders_terminal_tasks(tmp_path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path)
    mine = mailbox.enqueue_task(
        recipient="hermes-m5", sender="sarathi", summary="mine", body="b"
    )
    other = mailbox.enqueue_task(
        recipient="hermes-m5", sender="someone-else", summary="theirs", body="b"
    )
    for task_id in (mine.task_id, other.task_id):
        mailbox.claim_task(task_id, claimed_by="hermes-m5")
        mailbox.respond_to_task(
            task_id=task_id, responder="hermes-m5", summary="ok", body="ok"
        )
    swept = sweep_responses(mailbox, sender="sarathi")
    assert [row["task_id"] for row in swept] == [mine.task_id]
    assert swept[0]["responder"] == "hermes-m5"
    assert sweep_responses(None) == []


def test_brief_v2_never_fabricates_audit_state() -> None:
    missing = build_operator_brief(
        {"schema_version": "s", "roster": []}, outcomes=[], responses=[]
    )
    assert "MISSING" in missing
    present = build_operator_brief(
        {"schema_version": "s", "roster": []},
        outcomes=[],
        responses=[],
        audit={"anything": True},
    )
    assert "outranks this brief" in present
    # v1 call shape (no ledger kwargs) still renders without a ledger.
    legacy = build_operator_brief({"schema_version": "s", "roster": []})
    assert "Delegation ledger" not in legacy
