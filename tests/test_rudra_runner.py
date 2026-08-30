"""Runner integration: the one loop, honest terminals, kill-and-recover.

Normative source: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md sections 12-13.
All runs use the deterministic stub executor; nothing touches a network or
a provider key.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.rudra.codex_driver import StubCodexDriver, StubTurn
from dharma_swarm.rudra.goal_gate import GoalGate
from dharma_swarm.rudra.runner import MissionRunner, RecoveryRequired
from dharma_swarm.rudra.workcell import ProcessOwner
from tests.fixtures.rudra.helpers import (
    FIXED_TARGET,
    make_base_repo,
    make_mission_yaml,
    write_mission,
)


def _stub_factory(plan):
    def factory(admitted, workcell_root):
        return StubCodexDriver(
            workcell_root,
            plan,
            allowed_changed_paths=["src/target.py"],
            attempt_key=admitted.attempt_key,
            contract_digest=admitted.contract_digest,
        )

    return factory


@pytest.fixture()
def mission(tmp_path: Path):
    repo, base = make_base_repo(tmp_path)
    text = make_mission_yaml(repo, base)
    path = write_mission(tmp_path, text)
    return repo, base, path, tmp_path / "state"


def test_complete_reproduced_fresh_path(mission) -> None:
    """Requirements 1-8: one admitted mission converges only through fresh
    GoalGate evidence against the exact candidate commit."""
    repo, base, path, state = mission
    runner = MissionRunner(
        repo, state_dir=state,
        driver_factory=_stub_factory(
            [StubTurn({"src/target.py": FIXED_TARGET}, reported_complete=True)]
        ),
    )
    result = runner.run(path)
    assert result["terminal"] == "COMPLETE_REPRODUCED"
    reproduced = result["reproduced"]
    assert reproduced["base_sha"] == base
    assert reproduced["candidate_sha"] == result["candidate_sha"]
    # Base checkout preserved byte-for-byte.
    gate = GoalGate(repo, state_dir=state)
    assert gate.base_digests()
    status = __import__("subprocess").run(
        ["/usr/bin/git", "status", "--porcelain"], cwd=repo,
        capture_output=True, text=True,
    ).stdout
    assert status.strip() == ""


def test_relaunch_returns_identical_sealed_terminal(mission) -> None:
    """R18: a duplicate launch returns the immutable terminal; nothing is
    re-executed and no second attempt is created."""
    repo, _base, path, state = mission
    plan = [StubTurn({"src/target.py": FIXED_TARGET})]
    first = MissionRunner(
        repo, state_dir=state, driver_factory=_stub_factory(plan)
    ).run(path)
    second = MissionRunner(
        repo, state_dir=state, driver_factory=_stub_factory(plan)
    ).run(path)
    assert first["terminal"] == second["terminal"] == "COMPLETE_REPRODUCED"
    assert first["candidate_sha"] == second["candidate_sha"]
    missions = state / "rudra" / "missions"
    attempts = list(next(missions.iterdir()).glob("attempts/*"))
    assert len(attempts) == 1


def test_false_green_rejected_budget_terminal(mission) -> None:
    """The executor reports completion with no valid change; the mission can
    never mint COMPLETE and dies honestly on the no-delta budget."""
    repo, _base, path, state = mission
    plan = [StubTurn({}, reported_complete=True) for _ in range(4)]
    runner = MissionRunner(
        repo, state_dir=state, driver_factory=_stub_factory(plan)
    )
    result = runner.run(path)
    assert result["terminal"] == "FAILED_BUDGET"


def test_kill_and_recover_no_double_execution(mission) -> None:
    """Supervisor death mid-turn: the new supervisor proves the former
    process tree dead before any new turn, and converges exactly once."""
    repo, base, path, state = mission

    class SupervisorKilled(RuntimeError):
        pass

    def dying_factory(admitted, workcell_root):
        owner = ProcessOwner()
        _proc, handle = owner.spawn(
            [__import__("sys").executable, "-c", "import time; time.sleep(300)"],
            env={"PATH": "/usr/bin:/bin"},
            cwd=workcell_root,
        )
        stub = StubCodexDriver(
            workcell_root,
            [StubTurn({"src/target.py": FIXED_TARGET})],
            allowed_changed_paths=["src/target.py"],
            attempt_key=admitted.attempt_key,
            contract_digest=admitted.contract_digest,
        )
        stub.process_handles = [handle]
        original_turn = stub.start_turn

        def turn_then_die(**kwargs):
            original_turn(**kwargs)
            raise SupervisorKilled  # no cleanup: journal and child survive

        stub.start_turn = turn_then_die
        return stub

    with pytest.raises(SupervisorKilled):
        MissionRunner(
            repo, state_dir=state, driver_factory=dying_factory
        ).run(path)
    # Recovery (R09): the mutation completed before its observation row.
    # The new supervisor kills the orphan, reconciles Git, runs GoalGate
    # first — and converges from workspace truth without replaying the turn.
    recovered = MissionRunner(
        repo, state_dir=state,
        driver_factory=_stub_factory([StubTurn({"src/target.py": FIXED_TARGET})]),
    ).run(path)
    assert recovered["terminal"] == "COMPLETE_REPRODUCED"
    leftovers = __import__("subprocess").run(
        ["/usr/bin/pgrep", "-f", "time.sleep(300)"], capture_output=True, text=True
    ).stdout.strip()
    assert leftovers == ""
    # Exactly one attempt; the ambiguous turn was never re-issued.
    missions = state / "rudra" / "missions"
    attempt = next(next(missions.iterdir()).glob("attempts/*"))
    rows = [
        json.loads(line)
        for line in (attempt / "run.jsonl").read_text().splitlines()
    ]
    observed = [r for r in rows if r["event"] == "TURN_OBSERVED"]
    assert observed == [], "ambiguous turn was replayed"
    assert sum(1 for r in rows if r["event"] == "TURN_INTENT") == 1
    assert any(r["event"] == "RECOVERED" for r in rows)


def test_recovery_blocks_when_tree_unprovable(mission, monkeypatch) -> None:
    """No new turn begins while a former executor may still be alive."""
    repo, _base, path, state = mission

    def dying_factory(admitted, workcell_root):
        gate = GoalGate(repo, state_dir=state)
        _proc, handle = gate.owner.spawn(
            [__import__("sys").executable, "-c", "import time; time.sleep(300)"],
            env={"PATH": "/usr/bin:/bin"},
            cwd=workcell_root,
        )
        stub = StubCodexDriver(workcell_root, [], attempt_key=admitted.attempt_key)
        stub.process_handles = [handle]

        class Dead(RuntimeError):
            pass

        stub.start_turn = lambda **kw: (_ for _ in ()).throw(Dead())
        return stub

    with pytest.raises(Exception):
        MissionRunner(repo, state_dir=state, driver_factory=dying_factory).run(path)
    monkeypatch.setattr(
        ProcessOwner, "status_for_recovery",
        lambda self, handles: __import__(
            "dharma_swarm.rudra.contracts", fromlist=["DerivedStatus"]
        ).DerivedStatus.RECOVERY_REQUIRED,
    )
    with pytest.raises(RecoveryRequired):
        MissionRunner(
            repo, state_dir=state,
            driver_factory=_stub_factory([StubTurn({"src/target.py": FIXED_TARGET})]),
        ).run(path)
    # Cleanup the orphan left by the dying factory.
    __import__("subprocess").run(
        ["/usr/bin/pkill", "-f", "time.sleep(300)"], capture_output=True
    )


def test_operator_stop_beats_pending_green(mission) -> None:
    """G19: a durable stop request fsynced before any terminal intent wins;
    cancellation is never misclassified."""
    repo, _base, path, state = mission
    runner = MissionRunner(repo, state_dir=state)
    def factory(admitted, workcell_root):
        stub = StubCodexDriver(
            workcell_root,
            [StubTurn({"src/target.py": FIXED_TARGET})],
            allowed_changed_paths=["src/target.py"],
            attempt_key=admitted.attempt_key,
            contract_digest=admitted.contract_digest,
        )
        original = stub.start_turn

        def turn_and_stop(**kwargs):
            observation = original(**kwargs)
            runner.stop(admitted.contract.mission_id, "operator test stop")
            return observation

        stub.start_turn = turn_and_stop
        return stub

    runner.driver_factory = factory
    result = runner.run(path)
    assert result["terminal"] == "CANCELLED_OPERATOR"
    # stop after the seal returns the immutable terminal without appending.
    after = runner.stop("smoke-mission", "too late")
    assert after["result"] == "ALREADY_SEALED"
    assert after["terminal"]["terminal"] == "CANCELLED_OPERATOR"


def test_status_honesty(mission) -> None:
    """Status reports RUNNING only with a live kernel lock; stale files
    alone yield RECOVERY_REQUIRED."""
    repo, _base, path, state = mission
    gate = GoalGate(repo, state_dir=state)
    gate.admit(path.read_text())  # attempt exists; no supervisor running
    runner = MissionRunner(repo, state_dir=state)
    result = runner.status("smoke-mission")
    assert result["status"] == "RECOVERY_REQUIRED"
    # After a sealed run, status reflects the immutable terminal.
    runner.driver_factory = _stub_factory(
        [StubTurn({"src/target.py": FIXED_TARGET})]
    )
    runner.run(path)
    assert runner.status("smoke-mission")["status"] == "COMPLETE_REPRODUCED"
    assert runner.status("no-such-mission")["status"] == "UNKNOWN"


def test_blocked_environment_without_driver(mission) -> None:
    """Invariant 9: a missing executor binding is BLOCKED_ENVIRONMENT,
    never a host fallback."""
    repo, _base, path, state = mission
    runner = MissionRunner(repo, state_dir=state, driver_factory=None)
    result = runner.run(path)
    assert result["terminal"] == "BLOCKED_ENVIRONMENT"
