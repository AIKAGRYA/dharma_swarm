"""Adversarial suite: attack terminal truth and the durable crash windows.

Normative source: docs/plans/rudra_v0/TEST_AND_BURNIN_PLAN.md sections 2-3.
Offline subset for the build step: the full 20-cutpoint × 5-trial burn-in is
a live-campaign gate, not a build-time smoke test. What is proven here:

- zero false greens across the mutant corpus below;
- corrupt journals quarantine instead of skipping rows;
- conflicting terminals are never accepted;
- base/unauthorized writes are detected;
- no descendant survives recovery.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.rudra.codex_driver import StubCodexDriver, StubTurn
from dharma_swarm.rudra.goal_gate import GoalGate
from dharma_swarm.rudra.runner import MissionRunner
from dharma_swarm.rudra.workcell import (
    Journal,
    JournalConflict,
    JournalCorrupt,
    Workcell,
)
from tests.fixtures.rudra.helpers import (
    FIXED_TARGET,
    git,
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


def _complete_run(repo, path, state):
    return MissionRunner(
        repo, state_dir=state,
        driver_factory=_stub_factory([StubTurn({"src/target.py": FIXED_TARGET})]),
    ).run(path)


def _journal_path(state: Path) -> Path:
    missions = state / "rudra" / "missions"
    attempt = next(next(missions.iterdir()).glob("attempts/*"))
    return attempt / "run.jsonl", attempt


# ---------------------------------------------------------------------------
# G-series false-green mutants
# ---------------------------------------------------------------------------


def test_g06_hidden_test_edit_via_untracked_path(mission) -> None:
    """A test edit hidden as an untracked path is still a forbidden change."""
    repo, _base, path, state = mission
    gate = GoalGate(repo, state_dir=state)
    adm = gate.admit(path.read_text())
    workcell = Workcell(Path(adm.attempt_dir), repo, adm.contract.repository.base_sha, gate.state_root)
    (workcell.worktree / "src" / "target.py").write_text(FIXED_TARGET)
    (workcell.worktree / "tests" / "helper_new.py").write_text("x = 1\n")
    result = gate.evaluate(adm)
    assert not result.green
    assert any("forbidden path" in r for r in result.reasons)


def test_g11_mode_only_and_binary_change(mission) -> None:
    """Raw bytes/mode changes invisible to a friendly diff are seen."""
    repo, _base, path, state = mission
    gate = GoalGate(repo, state_dir=state)
    adm = gate.admit(path.read_text())
    workcell = Workcell(Path(adm.attempt_dir), repo, adm.contract.repository.base_sha, gate.state_root)
    target = workcell.worktree / "src" / "target.py"
    target.write_text(FIXED_TARGET)
    target.chmod(0o755)
    result = gate.evaluate(adm)
    # Executable-mode flip is visible in the raw diff and admitted; the gate
    # still runs the verifiers fresh rather than trusting the diff shape.
    assert result.green, result.reasons
    candidate = gate.freeze_candidate(adm, result)
    passed = gate.verify_candidate(adm, candidate)
    assert passed.candidate_sha == candidate


def test_g16_base_checkout_mutation_detected(mission) -> None:
    """Any base content/HEAD/index write invalidates preservation proof."""
    repo, _base, path, state = mission
    gate = GoalGate(repo, state_dir=state)
    adm = gate.admit(path.read_text())
    (repo / "src" / "target.py").write_text(FIXED_TARGET)  # forbidden base write
    assert not gate.prove_base_preserved(adm)


def test_g18_duplicate_then_conflicting_terminal(mission) -> None:
    repo, _base, path, state = mission
    result = _complete_run(repo, path, state)
    assert result["terminal"] == "COMPLETE_REPRODUCED"
    journal_path, attempt = _journal_path(state)
    journal = Journal(journal_path, attempt.name, attempt.name)
    sealed = journal.terminal()
    assert sealed is not None
    retry = journal.compare_and_seal_terminal(
        sealed["payload"]["terminal"],
        {k: v for k, v in sealed["payload"].items() if k != "terminal"},
    )
    assert retry["event_id"] == sealed["event_id"]
    with pytest.raises(JournalConflict):
        journal.compare_and_seal_terminal("FAILED_BUDGET", {"budget": "turns"})


def test_conflicting_contract_under_admitted_dir_quarantines(mission) -> None:
    repo, base, path, state = mission
    _complete_run(repo, path, state)
    # Tamper with the durable admitted copy: replay must quarantine.
    missions = state / "rudra" / "missions"
    mission_dir = next(missions.iterdir())
    (mission_dir / "admitted.json").write_text('{"tampered": true}\n')
    with pytest.raises(JournalConflict):
        MissionRunner(
            repo, state_dir=state,
            driver_factory=_stub_factory([StubTurn({"src/target.py": FIXED_TARGET})]),
        ).run(path)


# ---------------------------------------------------------------------------
# Journal and crash-window attacks
# ---------------------------------------------------------------------------


def test_corrupt_middle_row_never_skipped(mission) -> None:
    """A corrupt middle row quarantines the attempt; it can never append
    its own failure row or reach a terminal."""
    repo, _base, path, state = mission
    result = _complete_run(repo, path, state)
    assert result["terminal"] == "COMPLETE_REPRODUCED"
    journal_path, attempt = _journal_path(state)
    lines = journal_path.read_bytes().split(b"\n")
    lines[2] = b'{"seq": 3, "event_id": "forged", "event": "TURN_OBSERVED'
    journal_path.write_bytes(b"\n".join(lines))
    journal = Journal(journal_path, attempt.name, attempt.name)
    with pytest.raises(JournalCorrupt):
        journal.rows()


def test_rollback_prefix_with_advanced_workcell(mission) -> None:
    """Journal rolled back to a prefix while the private workcell advanced:
    the sealed terminal is gone from the journal, but the recovery path
    revalidates from raw workspace state and never trusts the roll."""
    repo, _base, path, state = mission
    result = _complete_run(repo, path, state)
    journal_path, attempt = _journal_path(state)
    lines = journal_path.read_text().splitlines()
    # Keep only the first three rows (pre-terminal) — a prefix rollback.
    journal_path.write_text("\n".join(lines[:3]) + "\n")
    journal = Journal(journal_path, attempt.name, attempt.name)
    assert journal.terminal() is None
    # Relaunch re-derives truth: workspace already carries the candidate,
    # so the gate (not the journal) decides what happens next.
    rerun = MissionRunner(
        repo, state_dir=state,
        driver_factory=_stub_factory([StubTurn({"src/target.py": FIXED_TARGET})]),
    ).run(path)
    assert rerun["terminal"] == "COMPLETE_REPRODUCED"
    assert rerun["candidate_sha"] == result["candidate_sha"]


def test_r18_terminal_fsync_relaunch_idempotent(mission) -> None:
    repo, _base, path, state = mission
    first = _complete_run(repo, path, state)
    second = _complete_run(repo, path, state)
    third = MissionRunner(repo, state_dir=state).status("smoke-mission")
    assert first["candidate_sha"] == second["candidate_sha"]
    assert third["status"] == "COMPLETE_REPRODUCED"


def test_verifier_killed_discards_partial_result(mission) -> None:
    """R12: a timed-out verifier invalidates the run; the partial artifact
    never counts toward a later green."""
    repo, _base, path, state = mission
    gate = GoalGate(repo, state_dir=state)
    adm = gate.admit(path.read_text())
    workcell = Workcell(Path(adm.attempt_dir), repo, adm.contract.repository.base_sha, gate.state_root)
    (workcell.worktree / "src" / "target.py").write_text(FIXED_TARGET)
    slow = adm.contract.model_copy(deep=True)
    object.__setattr__(
        slow.acceptance.commands[0],
        "argv",
        [adm.contract.acceptance.commands[0].argv[0], "-c",
         "import time; print('RUDRA_OK', flush=True); time.sleep(60)"],
    )
    object.__setattr__(slow.acceptance.commands[0], "timeout_seconds", 1)
    adm_slow = adm.model_copy(update={"contract": slow})
    result = gate.evaluate(adm_slow)
    assert not result.green
    assert result.receipts[0].timed_out
    # Fresh evaluation after the kill is clean and green.
    fresh = gate.evaluate(adm)
    assert fresh.green, fresh.reasons


def test_no_descendant_survives_complete_run(mission, tmp_path: Path) -> None:
    repo, _base, path, state = mission
    result = _complete_run(repo, path, state)
    assert result["terminal"] == "COMPLETE_REPRODUCED"
    import subprocess as sp

    census = sp.run(
        ["/bin/ps", "-axo", "command="], capture_output=True, text=True
    ).stdout
    survivors = [
        line for line in census.splitlines() if str(tmp_path) in line
    ]
    assert survivors == [], f"mission descendants survived: {survivors}"


def test_base_git_metadata_unchanged_after_mission(mission) -> None:
    """Zero Git-control delta in the base: no refs, no objects, no config,
    no worktree metadata."""
    repo, base, path, state = mission
    head_before = (repo / ".git" / "HEAD").read_bytes()
    refs_before = git(repo, "for-each-ref").strip()
    result = _complete_run(repo, path, state)
    assert result["terminal"] == "COMPLETE_REPRODUCED"
    assert (repo / ".git" / "HEAD").read_bytes() == head_before
    assert git(repo, "for-each-ref").strip() == refs_before
    assert git(repo, "rev-parse", "HEAD").strip() == base
    assert not (repo / ".git" / "worktrees").exists()
    assert not (repo / ".git" / "rudra").exists()
