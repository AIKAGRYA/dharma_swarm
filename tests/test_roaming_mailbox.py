from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.roaming_mailbox import RoamingMailbox


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_enqueue_task_persists_queue_record(tmp_path: Path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path / "mailbox")

    task = mailbox.enqueue_task(
        recipient="kimi-claw-phone",
        sender="dharma_swarm",
        summary="Ping",
        body="Return one-line status.",
        capabilities=["research"],
    )

    task_path = mailbox.task_path(task.task_id)
    assert task.status == "queued"
    assert task_path.exists()

    stored = _load_json(task_path)
    assert stored["recipient"] == "kimi-claw-phone"
    assert stored["summary"] == "Ping"
    assert stored["capabilities"] == ["research"]


def test_claim_next_task_prefers_oldest_queued_for_recipient(tmp_path: Path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path / "mailbox")
    first = mailbox.enqueue_task(
        recipient="kimi-claw-phone",
        sender="dharma_swarm",
        summary="First",
        body="first body",
    )
    mailbox.enqueue_task(
        recipient="other-agent",
        sender="dharma_swarm",
        summary="Other",
        body="other body",
    )
    second = mailbox.enqueue_task(
        recipient="kimi-claw-phone",
        sender="dharma_swarm",
        summary="Second",
        body="second body",
    )

    claimed = mailbox.claim_next_task("kimi-claw-phone")

    assert claimed is not None
    assert claimed.task_id == first.task_id
    assert claimed.status == "claimed"
    assert claimed.claimed_by == "kimi-claw-phone"
    assert mailbox.load_task(second.task_id).status == "queued"


def test_respond_to_task_writes_response_and_updates_task(tmp_path: Path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path / "mailbox")
    task = mailbox.enqueue_task(
        recipient="kimi-claw-phone",
        sender="dharma_swarm",
        summary="Status request",
        body="Return JSON status.",
    )
    mailbox.claim_task(task.task_id, claimed_by="kimi-claw-phone")

    response = mailbox.respond_to_task(
        task_id=task.task_id,
        responder="kimi-claw-phone",
        summary="Ready",
        body='{"status":"online"}',
    )

    task_after = mailbox.load_task(task.task_id)
    response_path = mailbox.response_path(task.task_id, "kimi-claw-phone")

    assert response_path.exists()
    assert response.status == "responded"
    assert task_after.status == "responded"
    assert task_after.response_ref == str(response_path)


def test_blocked_task_is_not_ready_or_claimable(tmp_path: Path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path / "mailbox")
    dep = mailbox.enqueue_task(
        recipient="hardening-lane", sender="s", summary="dep", body="b"
    )
    blocked = mailbox.enqueue_task(
        recipient="hardening-lane", sender="s", summary="blocked", body="b",
        depends_on=[dep.task_id],
    )
    ready_ids = [t.task_id for t in mailbox.ready_tasks(recipient="hardening-lane")]
    assert dep.task_id in ready_ids
    assert blocked.task_id not in ready_ids
    claimed = mailbox.claim_next_task("hardening-lane")
    assert claimed is not None and claimed.task_id == dep.task_id


def test_task_becomes_ready_after_dependency_responds(tmp_path: Path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path / "mailbox")
    dep = mailbox.enqueue_task(recipient="r", sender="s", summary="dep", body="b")
    blocked = mailbox.enqueue_task(
        recipient="r", sender="s", summary="blocked", body="b",
        depends_on=[dep.task_id],
    )
    assert [t.task_id for t in mailbox.ready_tasks(recipient="r")] == [dep.task_id]
    mailbox.respond_to_task(task_id=dep.task_id, responder="r", summary="done", body="d")
    assert [t.task_id for t in mailbox.ready_tasks(recipient="r")] == [blocked.task_id]


def test_unknown_dependency_fails_closed(tmp_path: Path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path / "mailbox")
    orphan = mailbox.enqueue_task(
        recipient="r", sender="s", summary="orphan", body="b",
        depends_on=["mbx_does_not_exist"],
    )
    assert mailbox.ready_tasks(recipient="r") == []
    assert mailbox.claim_next_task("r") is None
    issues = mailbox.validate_dependencies()
    assert any(orphan.task_id in issue and "unknown dependency" in issue for issue in issues)


def test_dependency_cycle_is_reported_and_never_ready(tmp_path: Path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path / "mailbox")
    a = mailbox.enqueue_task(recipient="r", sender="s", summary="a", body="b")
    b = mailbox.enqueue_task(
        recipient="r", sender="s", summary="b", body="b", depends_on=[a.task_id]
    )
    # Close the cycle by rewriting a with a dependency on b.
    rewritten = {**a.to_dict(), "depends_on": [b.task_id]}
    mailbox._write_json(mailbox.task_path(a.task_id), rewritten)
    assert mailbox.ready_tasks(recipient="r") == []
    assert any("cycle" in issue for issue in mailbox.validate_dependencies())


def test_depends_on_round_trips_through_json(tmp_path: Path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path / "mailbox")
    dep = mailbox.enqueue_task(recipient="r", sender="s", summary="dep", body="b")
    task = mailbox.enqueue_task(
        recipient="r", sender="s", summary="t", body="b", depends_on=[dep.task_id]
    )
    stored = _load_json(mailbox.task_path(task.task_id))
    assert stored["depends_on"] == [dep.task_id]
    assert mailbox.load_task(task.task_id).depends_on == [dep.task_id]
    # Legacy records without the field stay loadable (default []).
    legacy = {k: v for k, v in stored.items() if k != "depends_on"}
    mailbox._write_json(mailbox.task_path(task.task_id), legacy)
    assert mailbox.load_task(task.task_id).depends_on == []

def test_dependent_tasks_are_encoded_blocked_for_legacy_pollers(tmp_path: Path) -> None:
    """Older checkouts ignore depends_on and claim anything "queued" — a
    dependent task must be written in a status they can never claim."""
    mailbox = RoamingMailbox(queue_root=tmp_path / "mailbox")
    dep = mailbox.enqueue_task(recipient="r", sender="s", summary="dep", body="b")
    dependent = mailbox.enqueue_task(
        recipient="r", sender="s", summary="t", body="b", depends_on=[dep.task_id]
    )
    assert dependent.status == "blocked"
    assert _load_json(mailbox.task_path(dependent.task_id))["status"] == "blocked"
    queued_ids = [t.task_id for t in mailbox.list_tasks(status="queued")]
    assert dependent.task_id not in queued_ids
    # New readers still surface it once the dependency responds.
    mailbox.respond_to_task(task_id=dep.task_id, responder="r", summary="d", body="d")
    assert [t.task_id for t in mailbox.ready_tasks(recipient="r")] == [
        dependent.task_id
    ]


def test_traversal_dependency_never_satisfies_ready_gate(tmp_path: Path) -> None:
    """A depends_on like "../responses/<id>.<responder>" must not resolve a
    response JSON into a satisfied dependency (Greptile P1 on PR #1159)."""
    mailbox = RoamingMailbox(queue_root=tmp_path / "mailbox")
    dep = mailbox.enqueue_task(recipient="r", sender="s", summary="dep", body="b")
    mailbox.respond_to_task(task_id=dep.task_id, responder="worker", summary="d", body="d")
    traversal = f"../responses/{dep.task_id}.worker"
    assert (mailbox.responses_dir / f"{dep.task_id}.worker.json").exists()
    victim = mailbox.enqueue_task(
        recipient="r", sender="s", summary="victim", body="b",
        depends_on=[traversal],
    )
    ready_ids = [t.task_id for t in mailbox.ready_tasks(recipient="r")]
    assert victim.task_id not in ready_ids
    assert mailbox.claim_next_task("r") is None
    assert any("unknown dependency" in issue for issue in mailbox.validate_dependencies())


def test_dependency_record_must_match_its_own_id(tmp_path: Path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path / "mailbox")
    dep = mailbox.enqueue_task(recipient="r", sender="s", summary="dep", body="b")
    mailbox.respond_to_task(task_id=dep.task_id, responder="r", summary="d", body="d")
    # A copied/renamed responded record whose embedded id differs never counts.
    forged = {**_load_json(mailbox.task_path(dep.task_id)), "task_id": "mbx_other"}
    mailbox._write_json(mailbox.tasks_dir / "mbx_forged.json", forged)
    victim = mailbox.enqueue_task(
        recipient="r", sender="s", summary="v", body="b", depends_on=["mbx_forged"]
    )
    assert victim.task_id not in [t.task_id for t in mailbox.ready_tasks(recipient="r")]


def test_invalid_task_ids_are_rejected_at_the_path_boundary(tmp_path: Path) -> None:
    mailbox = RoamingMailbox(queue_root=tmp_path / "mailbox")
    for bad in ("../responses/x", "a/b", "..", ".hidden", ""):
        try:
            mailbox.task_path(bad)
        except ValueError:
            continue
        raise AssertionError(f"task_path accepted invalid id: {bad!r}")


def test_direct_claim_of_unsatisfied_dependency_is_refused(tmp_path: Path) -> None:
    """claim_task itself enforces the contract — not only claim_next_task
    (Codex P2 on PR #1159)."""
    mailbox = RoamingMailbox(queue_root=tmp_path / "mailbox")
    dep = mailbox.enqueue_task(recipient="r", sender="s", summary="dep", body="b")
    dependent = mailbox.enqueue_task(
        recipient="r", sender="s", summary="t", body="b", depends_on=[dep.task_id]
    )
    try:
        mailbox.claim_task(dependent.task_id, claimed_by="r")
        raise AssertionError("direct claim bypassed the dependency gate")
    except ValueError:
        pass
    assert mailbox.load_task(dependent.task_id).status == "blocked"
    mailbox.respond_to_task(task_id=dep.task_id, responder="r", summary="d", body="d")
    claimed = mailbox.claim_task(dependent.task_id, claimed_by="r")
    assert claimed.status == "claimed"
