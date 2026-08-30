"""Runner integration: the one loop, honest terminals, kill-and-recover.

Normative source: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md sections 12-13.
All runs use the deterministic stub executor; nothing touches a network or
a provider key.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.rudra.goal_gate import GoalGate
from dharma_swarm.rudra.runner import MissionRunner, RecoveryRequired
from dharma_swarm.rudra.workcell import Journal, ProcessOwner
from tests.fixtures.rudra.stub_driver import StubCodexDriver, StubTurn
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


def test_bind_failure_proves_spawned_tree_dead_before_seal(mission) -> None:
    """A bind failure after a successful spawn must not leave a live
    unowned model process: the BLOCKED_ENVIRONMENT seal is withheld until
    the ProcessOwner census proves zero descendants of the spawned tree."""
    from dharma_swarm.rudra.live_driver import DriverBindError
    from dharma_swarm.rudra.process_owner import descendants_of

    repo, _base, path, state = mission
    runner = MissionRunner(repo, state_dir=state)
    spawned: dict = {}

    def factory(admitted, workcell_root):
        _proc, handle = runner.owner.spawn(
            [__import__("sys").executable, "-c", "import time; time.sleep(300)"],
            env={"PATH": "/usr/bin:/bin"},
            cwd=workcell_root,
        )
        spawned["handle"] = handle
        stub = StubCodexDriver(workcell_root, [], attempt_key=admitted.attempt_key)
        stub.process_handles = [handle]

        def bind_fails(**_kw):
            raise DriverBindError("containment echo rejected")

        stub.start_or_resume = bind_fails
        return stub

    runner.driver_factory = factory
    result = runner.run(path)
    assert result["terminal"] == "BLOCKED_ENVIRONMENT"
    assert "executor bind failed" in result["reason"]
    handle = spawned["handle"]
    # Census semantics: zero group members, zero descendants, dead identity.
    assert runner.owner.prove_dead(handle)
    assert descendants_of(handle.pid) == set()


def test_restore_budgets_from_journal(tmp_path: Path) -> None:
    """Spec 12: token, wall, and no-delta state is rebuilt from the journal,
    never optimistically zeroed after a supervisor restart."""
    from dharma_swarm.rudra.contracts import BudgetSpec

    budgets = BudgetSpec(
        max_turns=10,
        max_total_tokens=100000,
        max_tokens_per_turn=20000,
        max_wall_seconds=900,
        max_turn_seconds=300,
        max_verifier_seconds=300,
        max_cpu_seconds=600,
        max_memory_bytes=4294967296,
        max_processes=32,
        max_disk_bytes=1073741824,
        max_captured_output_bytes=1048576,
        max_context_resets=1,
        max_consecutive_no_delta_turns=3,
    )
    journal = Journal(tmp_path / "run.jsonl", "m", "a")
    first = journal.append("PROPOSAL_VALIDATED", {})
    journal.append("GATE_RESULT", {"digest": "g0"})
    journal.append(
        "TURN_OBSERVED",
        {"observation": {"input_tokens": 100, "output_tokens": 50}},
    )
    journal.append("GATE_RESULT", {"digest": "g1"})  # turn 0 produced a delta
    journal.append(
        "TURN_OBSERVED",
        {"observation": {"input_tokens": None, "output_tokens": None}},
    )
    journal.append("GATE_RESULT", {"digest": "g1"})  # turn 1: no delta
    journal.append(
        "TURN_OBSERVED",
        {"observation": {"input_tokens": 10, "output_tokens": 10}},
    )
    journal.append("GATE_RESULT", {"digest": "g1"})  # turn 2: no delta again

    tokens, no_delta, started, last = MissionRunner._restore_budgets(
        journal, budgets
    )
    # 150 observed + one conservative per-turn ceiling + 20 observed.
    assert tokens == 150 + budgets.max_tokens_per_turn + 20
    assert no_delta == 2  # two trailing gate pairs without a delta
    assert started == first["at"]  # wall clock runs from the first row
    assert last == "g1"

    # A turn observed after the last gate row was never measured: charge it.
    journal.append(
        "TURN_OBSERVED",
        {"observation": {"input_tokens": 1, "output_tokens": 1}},
    )
    tokens, no_delta, _started, _last = MissionRunner._restore_budgets(
        journal, budgets
    )
    assert tokens == 150 + budgets.max_tokens_per_turn + 20 + 2
    assert no_delta == 3

    # Fresh attempt: nothing consumed.
    empty = Journal(tmp_path / "fresh.jsonl", "m", "a")
    tokens, no_delta, _started, last = MissionRunner._restore_budgets(
        empty, budgets
    )
    assert (tokens, no_delta, last) == (0, 0, None)


def test_token_budget_survives_supervisor_restart(tmp_path: Path) -> None:
    """Invariant 11 + spec 12: a mission killed and restarted cannot spend
    past its token cap; the restarted supervisor re-charges consumed turns
    from the journal instead of restarting at zero."""
    repo, base = make_base_repo(tmp_path)
    text = make_mission_yaml(
        repo,
        base,
        overrides={
            "budgets.max_total_tokens": 2500,
            "budgets.max_tokens_per_turn": 2000,
            "budgets.max_turns": 10,
            "budgets.max_consecutive_no_delta_turns": 5,
        },
    )
    path = write_mission(tmp_path, text)
    state = tmp_path / "state"
    plan = [
        StubTurn({"src/target.py": "def answer():\n    return 1\n"}),
        StubTurn({"src/target.py": "def answer():\n    return 2\n"}),
    ]

    class SupervisorKilled(RuntimeError):
        pass

    def dying_factory(admitted, workcell_root):
        stub = StubCodexDriver(
            workcell_root,
            plan,
            allowed_changed_paths=["src/target.py"],
            attempt_key=admitted.attempt_key,
            contract_digest=admitted.contract_digest,
        )
        original = stub.start_turn

        def die_on_second_turn(**kwargs):
            if kwargs["logical_seq"] == 1:
                raise SupervisorKilled  # turn 0 is journaled; then death
            return original(**kwargs)

        stub.start_turn = die_on_second_turn
        return stub

    with pytest.raises(SupervisorKilled):
        MissionRunner(
            repo, state_dir=state, driver_factory=dying_factory
        ).run(path)
    # Turn 0 burned 1500 of 2500. A reset budget would let turn 1 spend
    # another 1500 and continue; cumulative accounting seals the cap.
    result = MissionRunner(
        repo, state_dir=state, driver_factory=_stub_factory(plan)
    ).run(path)
    assert result["terminal"] == "FAILED_BUDGET"
    assert result["budget"] == "tokens"
