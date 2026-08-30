"""Layers D/E: lock, journal, workcell identity, and process containment.

Normative source: docs/plans/rudra_v0/TEST_AND_BURNIN_PLAN.md sections
2D-2E and RUDRA_BUILD_SPEC.md section 10.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from dharma_swarm.rudra.contracts import ProcessHandle
from dharma_swarm.rudra.goal_gate import GoalGate
from dharma_swarm.rudra.workcell import (
    Journal,
    JournalConflict,
    JournalCorrupt,
    LockHeldError,
    MissionLock,
    ProcessOwner,
    SealedJournalViolation,
    Workcell,
    descendants_of,
    os_boot_id,
    rudra_state_root,
)
from tests.fixtures.rudra.helpers import git, make_base_repo, make_mission_yaml


# ---------------------------------------------------------------------------
# Workcell identity and base preservation
# ---------------------------------------------------------------------------


def test_workcell_create_preserves_base(tmp_path: Path) -> None:
    repo, base = make_base_repo(tmp_path)
    text = make_mission_yaml(repo, base)
    gate = GoalGate(repo, state_dir=tmp_path / "state")
    adm = gate.admit(text)
    workcell = Workcell(
        Path(adm.attempt_dir), repo, base, gate.state_root
    )
    # Private git dir under the state root; pointer inside the worktree.
    assert str(workcell.private_git).startswith(str(gate.state_root))
    assert (workcell.worktree / ".git").is_file()
    # Exact base checkout content.
    assert (workcell.worktree / "src" / "target.py").read_text() == (
        repo / "src" / "target.py"
    ).read_text()
    assert workcell.head_sha() == base
    # Base received zero refs/objects/index/HEAD mutation.
    refs = git(repo, "for-each-ref", "refs/rudra")
    assert refs.strip() == ""
    assert gate.prove_base_preserved(adm)
    # Base object store is an alternate, not a copy.
    alternates = (workcell.private_git / "objects" / "info" / "alternates").read_text()
    assert str(repo / ".git" / "objects") in alternates


def test_state_root_rejects_repo_residence(tmp_path: Path) -> None:
    repo, _base = make_base_repo(tmp_path)
    with pytest.raises(Exception):
        GoalGate(repo, state_dir=repo / "inside")


# ---------------------------------------------------------------------------
# Mission lock
# ---------------------------------------------------------------------------


def test_lock_single_owner(tmp_path: Path) -> None:
    mission_dir = tmp_path / "m"
    mission_dir.mkdir()
    first = MissionLock(mission_dir)
    with pytest.raises(LockHeldError):
        MissionLock(mission_dir)
    first.close()
    second = MissionLock(mission_dir)  # same never-unlinked inode
    second.close()
    assert (mission_dir / "supervisor.lock").exists()


def test_lock_barrier_contention(tmp_path: Path) -> None:
    """One held winner per round; every other contender observes the loss."""
    contenders = int(os.environ.get("RUDRA_LOCK_CONTENDERS", "8"))
    rounds = int(os.environ.get("RUDRA_LOCK_ROUNDS", "20"))
    mission_dir = tmp_path / "m"
    mission_dir.mkdir()
    barrier = threading.Barrier(contenders)
    wins: list[int] = []
    errors: list[BaseException] = []

    def contend() -> None:
        for _ in range(rounds):
            barrier.wait()
            try:
                lock = MissionLock(mission_dir)
            except LockHeldError:
                continue
            except BaseException as exc:  # pragma: no cover
                errors.append(exc)
                continue
            try:
                wins.append(threading.get_ident())
                time.sleep(0.001)
            finally:
                lock.close()

    threads = [threading.Thread(target=contend) for _ in range(contenders)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors
    assert len(wins) == rounds, f"{len(wins)} winners over {rounds} rounds"


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------


@pytest.fixture()
def journal(tmp_path: Path) -> Journal:
    return Journal(tmp_path / "run.jsonl", "mkey", "akey")


def test_journal_append_and_seq(journal: Journal) -> None:
    journal.append("PROPOSAL_VALIDATED", {"x": 1})
    journal.effect_intent("e1", {"p": 1})
    journal.effect_result("e1", {"o": 2})
    rows = journal.rows()
    assert [r["seq"] for r in rows] == [1, 2, 3]
    assert rows[2]["event"] == "EFFECT_RESULT"


def test_journal_effect_result_idempotent_and_conflicting(journal: Journal) -> None:
    journal.effect_intent("e1", {"p": 1})
    first = journal.effect_result("e1", {"o": 2})
    again = journal.effect_result("e1", {"o": 2})
    assert first["event_id"] == again["event_id"]
    with pytest.raises(JournalConflict):
        journal.effect_result("e1", {"o": 3})


def test_journal_corrupt_middle_quarantines(journal: Journal) -> None:
    journal.append("A", {})
    journal.append("B", {})
    raw = journal.path.read_bytes()
    lines = raw.split(b"\n")
    lines[0] = b'{"seq": 1, "event_id": "tampered'
    journal.path.write_bytes(b"\n".join(lines))
    journal._rows = None
    with pytest.raises(JournalCorrupt):
        journal.rows()


def test_journal_sequence_gap_quarantines(journal: Journal) -> None:
    journal.append("A", {})
    with open(journal.path, "ab") as fh:
        fh.write(b'{"seq": 9, "event_id": "x", "event": "B"}\n')
    journal._rows = None
    with pytest.raises(JournalCorrupt):
        journal.rows()


def test_journal_torn_tail_repair(journal: Journal) -> None:
    journal.append("A", {})
    with open(journal.path, "ab") as fh:
        fh.write(b'{"seq": 2, "event_id": "torn", "ev')  # torn final line
    journal._rows = None
    assert journal.has_torn_tail()
    assert journal.repair_torn_tail()
    rows = journal.rows()
    assert [r["event"] for r in rows] == ["A", "JOURNAL_TAIL_REPAIRED"]
    assert journal.path.with_suffix(".torn-tail").exists()


def test_terminal_compare_and_seal(journal: Journal) -> None:
    journal.append("A", {})
    sealed = journal.compare_and_seal_terminal("COMPLETE_REPRODUCED", {"c": "x"})
    retry = journal.compare_and_seal_terminal("COMPLETE_REPRODUCED", {"c": "x"})
    assert sealed["event_id"] == retry["event_id"]
    with pytest.raises(JournalConflict):
        journal.compare_and_seal_terminal("FAILED_BUDGET", {"c": "y"})
    with pytest.raises(SealedJournalViolation):
        journal.append("GATE_RESULT", {})


def test_post_seal_row_is_invariant_violation(journal: Journal) -> None:
    journal.append("A", {})
    journal.compare_and_seal_terminal("COMPLETE_REPRODUCED", {"c": "x"})
    # A post-seal lifecycle row written by a crash-torn path is detected.
    journal._rows = None
    with open(journal.path, "ab") as fh:
        row = {"seq": 3, "event_id": "late", "event": "GATE_RESULT", "payload": {}}
        fh.write((json.dumps(row) + "\n").encode())
    journal._rows = None
    assert journal.post_seal_violation()


# ---------------------------------------------------------------------------
# ProcessOwner
# ---------------------------------------------------------------------------


def _spawn_sleeper(owner: ProcessOwner, code: str) -> ProcessHandle:
    proc, handle = owner.spawn(
        [sys.executable, "-c", code],
        env={"PATH": "/usr/bin:/bin"},
        cwd=Path("/tmp"),
    )
    return handle


def test_process_identity_and_teardown(tmp_path: Path) -> None:
    owner = ProcessOwner()
    handle = _spawn_sleeper(owner, "import time; time.sleep(60)")
    assert owner.identity_status(handle) == "alive"
    assert owner.terminate_tree(handle)
    assert owner.prove_dead(handle)


def test_process_tree_including_grandchildren(tmp_path: Path) -> None:
    owner = ProcessOwner()
    handle = _spawn_sleeper(
        owner,
        "import subprocess,sys,time;"
        "subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
        "time.sleep(60)",
    )
    time.sleep(0.3)
    assert descendants_of(handle.pid), "grandchild not enumerated"
    assert owner.terminate_tree(handle)
    assert owner.prove_dead(handle)
    leftovers = subprocess.run(
        ["/usr/bin/pgrep", "-f", "time.sleep(60)"], capture_output=True, text=True
    ).stdout.strip()
    assert leftovers == ""


def test_setsid_escapee_is_enumerated_and_killed(tmp_path: Path) -> None:
    """The launch probe: a child calling setsid cannot escape ownership."""
    owner = ProcessOwner()
    handle = _spawn_sleeper(
        owner,
        "import os,subprocess,sys,time;"
        "subprocess.Popen([sys.executable,'-c',"
        "'import os,time;os.setsid();time.sleep(60)']);"
        "time.sleep(60)",
    )
    time.sleep(0.5)
    escapees = descendants_of(handle.pid)
    assert escapees, "setsid escapee invisible to ppid census"
    assert owner.terminate_tree(handle), "escapee survived teardown"
    assert owner.prove_dead(handle)


def test_reused_pid_is_not_signaled(tmp_path: Path) -> None:
    """A handle whose pid was reused by another process reads as dead or
    ambiguous, never as the original owner."""
    owner = ProcessOwner()
    handle = _spawn_sleeper(owner, "import time; time.sleep(5)")
    assert owner.terminate_tree(handle)
    forged = ProcessHandle(
        pid=handle.pid,
        pgid=handle.pgid,
        os_boot_id=os_boot_id(),
        process_start_id="Wed Jan  1 00:00:00 1970",
        executable=handle.executable,
        cwd=handle.cwd,
        run_nonce="forged",
    )
    assert owner.identity_status(forged) in ("dead", "ambiguous")
    # Terminating a dead identity is a no-op, never an error.
    assert owner.terminate_tree(forged)


def test_status_for_recovery_blocks_on_survivor(tmp_path: Path) -> None:

    owner = ProcessOwner()
    handle = _spawn_sleeper(owner, "import time; time.sleep(60)")
    result = owner.status_for_recovery([handle])
    assert result is None  # survivor was terminated and proven dead
    assert owner.prove_dead(handle)


def test_rudra_state_root_not_symlink(tmp_path: Path) -> None:
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(Exception):
        rudra_state_root(link)
