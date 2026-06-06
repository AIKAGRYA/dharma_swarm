"""Capstone E2E matrix: the full vision->wake->authority->tool->execute->LEARN->
receipt->verify lattice driven across MULTIPLE coordinating agents through a single
daemon-service drain over one store.

Three coordinating roles share ONE ``KernelRunStore``:

  * a PRIMARY agent (``persistent_self_wake`` source, learning-eligible),
  * a SECOND learning-eligible primary (proving LEARN fires per-agent, not once),
  * a SUBAGENT dispatched via ``spawn_subagent_wake`` from the primary's envelope
    (inherited-but-subset authority, its own ``agent:{child}:lessons`` namespace),
  * an EXTERNAL-WORKER peer marked ``external_worker_evidence_only`` that coordinates
    in the same store but is recorded via the evidence-only ``complete_external_wake``
    lifecycle and can never execute ``apply_patch``.

This unit OWNS only this test module; it makes NO edits to the kernel core (it relies
on the metabolism + learn-executor + daemon-service units already committed). Every
assertion is on REAL durable artifacts reloaded from disk after a real drain. No
provider client is constructed; nothing is written outside ``tmp_path``.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from dharma_swarm.operator_core.governed_work_admission import WorkKind
from dharma_swarm.operator_core.living_agent_kernel import (
    AgentRunEnvelope,
    AuthorityPassport,
    KernelRunStore,
    KernelTask,
    LivingAgentKernel,
    MemoryPlan,
    ProofRequest,
    ToolRequest,
    TriggerEnvelope,
    _contract_pattern_allowed,
)
from dharma_swarm.operator_core.living_agent_kernel_lessons import KernelLessonStore
from dharma_swarm.operator_core.living_agent_kernel_service import run_kernel_daemon_service

PARENT_ALLOWED = ["dharma_swarm/", "docs/"]
CHILD_ALLOWED = ["dharma_swarm/"]


def _kernel(tmp_path: Path) -> LivingAgentKernel:
    return LivingAgentKernel(store=KernelRunStore(tmp_path / "kernel"), workspace_root=tmp_path)


def _primary_envelope(
    *,
    agent_uid: str,
    correlation_id: str,
    delta: str = "",
    allowed_files: list[str] | None = None,
) -> AgentRunEnvelope:
    return AgentRunEnvelope(
        agent_uid=agent_uid,
        task=KernelTask(text=f"Coordinate matrix wake for {agent_uid}"),
        trigger=TriggerEnvelope(
            source="persistent_self_wake",
            mission_id="mission-matrix",
            task_id=f"task-{agent_uid}",
            correlation_id=correlation_id,
        ),
        authority=AuthorityPassport(
            work_kind=WorkKind.READ_ONLY,
            allowed_files=list(PARENT_ALLOWED if allowed_files is None else allowed_files),
        ),
        memory=MemoryPlan(
            read_namespaces=[f"agent:{agent_uid}:working"],
            write_namespaces=[f"agent:{agent_uid}:lessons"],
            proposed_learning_delta=delta,
        ),
        tool_request=ToolRequest(
            requested_tools=["session_status"],
            tool_calls=[{"name": "session_status", "arguments": {}}],
        ),
        proof=ProofRequest(verifier_commands=["pytest tests/test_living_agent_kernel_e2e_matrix.py"]),
    )


def _external_envelope(kernel: LivingAgentKernel, *, correlation_id: str) -> AgentRunEnvelope:
    """Evidence-only peer normalized from an external_fleet wake payload."""
    payload = {
        "name": "hermes-m5",
        "provider": "hermes",
        "model": "hermes-agent",
        "task": "Audit the bounded result and report evidence only",
        "correlation_id": correlation_id,
        "requested_tools": ["apply_patch"],
        "tool_calls": [{"name": "apply_patch", "arguments": {"patch": "*** Begin Patch"}}],
    }
    return kernel.normalize_wake_source("external_fleet", payload)


def _seed_matrix(kernel: LivingAgentKernel) -> dict[str, str]:
    """Seed primary + second-primary + subagent into ONE store. Returns wake_ids."""
    primary = _primary_envelope(
        agent_uid="codex_composer",
        correlation_id="corr-primary",
        delta="primary metabolized: single-drain coordination is resumable from the ledger",
    )
    kernel.enqueue_wake(primary, wake_id="wake-primary")
    second = _primary_envelope(
        agent_uid="conductor_e2e",
        correlation_id="corr-second",
        delta="second metabolized: learn fires per learning-eligible agent, not once",
    )
    kernel.enqueue_wake(second, wake_id="wake-second")
    dispatch = kernel.spawn_subagent_wake(
        primary,
        child_agent_uid="codex_sub",
        task_text="Review the primary's coordinated output",
        role="reviewer",
        allowed_files=list(CHILD_ALLOWED),
        requested_tools=["session_status"],
        tool_calls=[{"name": "session_status", "arguments": {}}],
        wake_id="wake-sub",
    )
    assert dispatch.status == "spawned"
    return {"primary": "wake-primary", "second": "wake-second", "sub": "wake-sub"}


def _drain(tmp_path: Path, *, cycles: int = 6, max_wakes: int = 3, recover_expired: bool = True):
    return run_kernel_daemon_service(
        store_dir=tmp_path / "kernel",
        workspace_root=tmp_path,
        daemon_id="kernel-matrix",
        cycles=cycles,
        max_wakes=max_wakes,
        interval_seconds=0,
        recover_expired=recover_expired,
    )


# ---------------------------------------------------------------------------
# unit
# ---------------------------------------------------------------------------


def test_spawn_subagent_inherits_subset_authority_and_own_lessons_namespace(tmp_path):
    kernel = _kernel(tmp_path)
    parent = _primary_envelope(agent_uid="codex_composer", correlation_id="corr-u1")
    kernel.enqueue_wake(parent, wake_id="wake-parent")
    dispatch = kernel.spawn_subagent_wake(
        parent,
        child_agent_uid="codex_sub",
        task_text="child",
        allowed_files=list(CHILD_ALLOWED),
        wake_id="wake-child",
    )

    assert dispatch.status == "spawned"
    assert dispatch.child_agent_uid == "codex_sub"
    assert dispatch.inherited_authority_ref["allowed_files"] == CHILD_ALLOWED

    child = kernel.store.latest_wake_records()["wake-child"]
    # Inherited-but-subset: every child pattern passes against the parent contract.
    assert all(
        _contract_pattern_allowed(pattern, parent.authority.allowed_files, workspace_root=kernel.workspace_root)
        for pattern in child.envelope.authority.allowed_files
    )
    # The subagent writes only to its OWN lessons namespace.
    assert child.envelope.memory.write_namespaces == ["agent:codex_sub:lessons"]
    assert child.envelope.trigger.source == "subagent"
    assert child.envelope.trigger.parent_run_id == parent.run_id


def test_each_coordinating_role_passes_evaluate_authority_with_expected_decision(tmp_path):
    kernel = _kernel(tmp_path)
    primary = _primary_envelope(agent_uid="codex_composer", correlation_id="corr-u2")
    second = _primary_envelope(agent_uid="conductor_e2e", correlation_id="corr-u2b")
    external = _external_envelope(kernel, correlation_id="corr-u2c")

    # Read-only coordinated agents are admitted; the evidence-only peer is also
    # admitted to RUN but its action tools are denied at the tool layer.
    assert kernel.evaluate_authority(primary).decision == "allow"
    assert kernel.evaluate_authority(second).decision == "allow"
    assert kernel.evaluate_authority(external).decision == "allow"
    assert external.authority.external_worker_authority == "external_worker_evidence_only"


# ---------------------------------------------------------------------------
# integration
# ---------------------------------------------------------------------------


def test_single_drain_clears_mixed_multi_agent_queue_and_reloads_from_disk(tmp_path):
    kernel = _kernel(tmp_path)
    wake_ids = _seed_matrix(kernel)

    # The evidence-only peer coordinates in the same store but is handled through
    # its own lifecycle: lease (source-filtered) -> run (apply_patch denied) ->
    # complete_external_wake. This runs BEFORE the kernel drain so the auto-drain
    # never re-leases it.
    ext_env = _external_envelope(kernel, correlation_id="corr-ext")
    kernel.enqueue_wake(ext_env, wake_id="wake-ext")
    leased_ext = kernel.store.lease_next_wake(
        lease_owner="external-runner", allowed_sources=["external_fleet"]
    )
    assert leased_ext is not None and leased_ext.wake_id == "wake-ext"
    ext_result = kernel.run(leased_ext.envelope)
    assert ext_result.tool_results[0].status == "denied"
    assert ext_result.tool_results[0].denial_reason == "external_worker_evidence_only"
    kernel.store.complete_external_wake(
        leased_ext,
        status=ext_result.status,
        result_ref={
            "kind": "external_worker_evidence",
            "run_id": ext_result.run_id,
            "denial_reason": "external_worker_evidence_only",
        },
    )

    result = _drain(tmp_path)
    assert result.status == "completed"

    fresh = KernelRunStore(tmp_path / "kernel")
    latest = fresh.latest_wake_records()

    # Every kernel-eligible agent reached a terminal status, leased exactly once.
    for key in ("primary", "second", "sub"):
        record = latest[wake_ids[key]]
        assert record.status in {"completed", "review"}
        assert record.attempt == 1
        # Proof entry + replay integrity for the run behind this terminal wake.
        replay = fresh.replay_run(record.run_id)
        assert replay.proof_entries, f"missing proof entry for {key}"
        assert replay.integrity_ok is True

    # The evidence-only peer is terminal (recorded via complete_external_wake).
    ext_record = latest["wake-ext"]
    assert ext_record.status in {"blocked", "review", "completed", "failed"}
    assert ext_record.result_ref["denial_reason"] == "external_worker_evidence_only"

    # LEARN fired per learning-eligible agent (primary + second). The subagent
    # carries an empty delta, so it is NOT learning-eligible: no lesson row.
    lessons = KernelLessonStore(tmp_path / "kernel")
    primary_rows = lessons.lessons("agent:codex_composer:lessons")
    second_rows = lessons.lessons("agent:conductor_e2e:lessons")
    assert len(primary_rows) == 1 and primary_rows[0].agent_uid == "codex_composer"
    assert len(second_rows) == 1 and second_rows[0].agent_uid == "conductor_e2e"
    assert not lessons.namespace_path("agent:codex_sub:lessons").exists()

    # Full cross-agent receipt/verify: every on-disk ledger reloads + verifies from
    # a FRESH store/lesson-store (wake, daemon-cycles, and both lessons ledgers ok).
    reloaded_lessons = KernelLessonStore(tmp_path / "kernel")
    assert fresh.verify_wake_ledger() == (True, [])
    assert fresh.verify_daemon_cycle_ledger() == (True, [])
    assert reloaded_lessons.verify_lesson_ledger("agent:codex_composer:lessons") == (True, [])
    assert reloaded_lessons.verify_lesson_ledger("agent:conductor_e2e:lessons") == (True, [])


def test_source_closeback_fires_per_wake_and_ref_recorded_on_terminal_record(tmp_path):
    kernel = _kernel(tmp_path)
    wake_ids = _seed_matrix(kernel)

    result = _drain(tmp_path)
    closebacks = [cb for cycle in result.cycles if cycle.tick for cb in cycle.tick.closebacks]
    # One closeback per kernel-eligible wake drained (primary + second + sub).
    assert len(closebacks) == 3
    assert {cb.source for cb in closebacks} == {"persistent_self_wake", "subagent"}

    fresh = KernelRunStore(tmp_path / "kernel")
    latest = fresh.latest_wake_records()
    for key in ("primary", "second", "sub"):
        record = latest[wake_ids[key]]
        # record_wake_closeback stamped the closeback onto the terminal wake record.
        assert "source_closeback" in record.result_ref
        assert record.result_ref["source_closeback"]["wake_id"] == record.wake_id


# ---------------------------------------------------------------------------
# adversarial
# ---------------------------------------------------------------------------


def test_subagent_allowed_files_escalation_is_denied_and_never_leased(tmp_path):
    kernel = _kernel(tmp_path)
    parent = _primary_envelope(agent_uid="codex_composer", correlation_id="corr-adv1")
    kernel.enqueue_wake(parent, wake_id="wake-parent")

    # A coordinating subagent tries to widen its file authority beyond the parent.
    malicious = kernel.spawn_subagent_wake(
        parent,
        child_agent_uid="evil_sub",
        task_text="escalate",
        allowed_files=["/etc/passwd", "outside_workspace/"],
        wake_id="wake-evil",
    )

    assert malicious.status == "denied"
    assert malicious.reason == "subagent_allowed_files_escalation"
    assert malicious.wake_id == ""
    assert malicious.child_run_id == ""

    # The malicious child was never enqueued, so a drain cannot lease or execute it.
    records = kernel.store.latest_wake_records()
    assert "wake-evil" not in records
    assert not any(rec.envelope.agent_uid == "evil_sub" for rec in records.values())

    result = _drain(tmp_path)
    fresh = KernelRunStore(tmp_path / "kernel")
    assert not any(
        rec.envelope.agent_uid == "evil_sub" for rec in fresh.latest_wake_records().values()
    )
    # And no proof/lessons artifact exists for the would-be escalator.
    lessons = KernelLessonStore(tmp_path / "kernel")
    assert not lessons.namespace_path("agent:evil_sub:lessons").exists()
    assert result is not None


def test_two_racing_drains_never_double_lease_any_wake(tmp_path):
    import fcntl

    kernel = _kernel(tmp_path)
    wake_ids = _seed_matrix(kernel)
    store_dir = tmp_path / "kernel"
    lock_path = store_dir / "daemon_service.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    # Hold the real flock to force a SECOND concurrent drain to bounce off it.
    with lock_path.open("w", encoding="utf-8") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        contended = run_kernel_daemon_service(
            store_dir=store_dir,
            workspace_root=tmp_path,
            daemon_id="kernel-matrix-b",
            cycles=3,
            max_wakes=3,
            interval_seconds=0,
        )
        fcntl.flock(held, fcntl.LOCK_UN)
    assert contended.status == "lock_held"
    assert contended.completed_cycles == 0

    # The uncontended drain then clears the queue.
    winner = _drain(tmp_path)
    assert winner.status == "completed"

    # Each wake_id has exactly one 'leased' transition in the ledger -> no double-lease.
    rows = [
        json.loads(line)
        for line in (store_dir / "wake_ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    leased = Counter(row["wake_id"] for row in rows if row["status"] == "leased")
    for key in ("primary", "second", "sub"):
        assert leased[wake_ids[key]] == 1, f"{key} double-leased: {dict(leased)}"

    fresh = KernelRunStore(store_dir)
    for key in ("primary", "second", "sub"):
        record = fresh.latest_wake_records()[wake_ids[key]]
        assert record.status in {"completed", "review"}
        assert record.attempt == 1
    assert fresh.verify_wake_ledger() == (True, [])


def test_external_evidence_only_peer_cannot_mutate_while_coordinating(tmp_path):
    kernel = _kernel(tmp_path)
    _seed_matrix(kernel)
    files_before = {p.resolve() for p in tmp_path.rglob("*") if p.is_file()}

    ext_env = _external_envelope(kernel, correlation_id="corr-adv-ext")
    kernel.enqueue_wake(ext_env, wake_id="wake-ext")
    leased = kernel.store.lease_next_wake(
        lease_owner="ext-runner", allowed_sources=["external_fleet"]
    )
    assert leased is not None
    result = kernel.run(leased.envelope)

    # apply_patch denied for the evidence-only peer; the run is blocked, not applied.
    assert result.status == "blocked"
    assert result.tool_results[0].tool_name == "apply_patch"
    assert result.tool_results[0].status == "denied"
    assert result.tool_results[0].denial_reason == "external_worker_evidence_only"

    kernel.store.complete_external_wake(
        leased,
        status=result.status,
        result_ref={"kind": "external_worker_evidence", "run_id": result.run_id},
    )

    # Now coordinate the rest of the matrix through the drain; still no mutation.
    _drain(tmp_path)

    files_after = {p.resolve() for p in tmp_path.rglob("*") if p.is_file()}
    # Only kernel ledger/state files were created; nothing under a source tree, and
    # nothing the evidence-only peer's patch named.
    new_files = files_after - files_before
    assert all((tmp_path / "kernel") in p.parents or p.parent == tmp_path / "kernel" for p in new_files), (
        f"evidence-only coordination wrote outside the kernel store: {new_files}"
    )
    assert not (tmp_path / "dharma_swarm").exists()


# ---------------------------------------------------------------------------
# crash
# ---------------------------------------------------------------------------


def test_crash_after_primary_before_subagent_lease_is_recoverable_from_ledger(tmp_path):
    kernel = _kernel(tmp_path)
    wake_ids = _seed_matrix(kernel)

    # Crash emulation: a bounded drain processes ONLY the first queued wake (the
    # primary) and then the process "dies" before the subagent is ever leased.
    # We run a single-wake drain, then drop ALL in-memory state.
    partial = _drain(tmp_path, cycles=1, max_wakes=1, recover_expired=False)
    assert partial.status == "completed"
    del kernel  # no in-memory coordination state survives the crash

    crashed = KernelRunStore(tmp_path / "kernel").latest_wake_records()
    assert crashed[wake_ids["primary"]].status in {"completed", "review"}
    # The subagent never leased: it is still 'queued' on disk.
    assert crashed[wake_ids["sub"]].status == "queued"
    assert crashed[wake_ids["second"]].status == "queued"

    # A recovery drain, reading ONLY the on-disk ledger, finishes coordination.
    recovered = _drain(tmp_path, cycles=4, max_wakes=3, recover_expired=True)
    assert recovered.status == "completed"

    fresh = KernelRunStore(tmp_path / "kernel")
    latest = fresh.latest_wake_records()
    for key in ("primary", "second", "sub"):
        assert latest[wake_ids[key]].status in {"completed", "review"}
        assert latest[wake_ids[key]].attempt == 1
    assert fresh.verify_wake_ledger() == (True, [])
    assert fresh.verify_daemon_cycle_ledger() == (True, [])

    lessons = KernelLessonStore(tmp_path / "kernel")
    assert len(lessons.lessons("agent:codex_composer:lessons")) == 1
    assert len(lessons.lessons("agent:conductor_e2e:lessons")) == 1


# ---------------------------------------------------------------------------
# operator-gated (documented, never auto-executed)
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason=(
        "OPERATOR-GATED: the LIVE-PROVIDER multi-agent matrix variant routes the "
        "same lattice through a real paid provider client. It is intentionally "
        "never auto-executed (no network/provider egress in the default suite); "
        "run only under explicit operator gating with FIXTURE keys disabled."
    )
)
def test_live_provider_matrix_variant_operator_gated():  # pragma: no cover
    raise AssertionError("LIVE-PROVIDER matrix variant must only run under operator gating.")
