"""Darshan Pack generator + onboard KNOWLEDGE STORES section contracts.

Covers scripts/governance/darshan_pack.py (the organism self-view artifact:
identity One Line, active-track list, guarded state-fullness counts, task
board snapshot) and the surgical KNOWLEDGE STORES addition to
scripts/governance/agent_onboard.py (a fresh clone announces the emptiness
of its knowledge stores; --json output stays pure JSON).
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_SCRIPT = REPO_ROOT / "scripts/governance/darshan_pack.py"
ONBOARD_SCRIPT = REPO_ROOT / "scripts/governance/agent_onboard.py"

ONE_LINE_FRAGMENT = "dharma_swarm is a self-evolving emergent organism"


def _run_pack(
    *args: str, home: Path, cwd: Path = REPO_ROOT
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(cwd / "scripts/governance/darshan_pack.py"), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _seed_dharma_home(home: Path) -> None:
    """Create a minimal ~/.dharma with known row counts."""
    dharma = home / ".dharma"
    (dharma / "agent_memory").mkdir(parents=True)
    (dharma / "state").mkdir(parents=True)
    (dharma / "board").mkdir(parents=True)

    con = sqlite3.connect(dharma / "ontology.db")
    con.execute("CREATE TABLE objects (id TEXT)")
    con.executemany("INSERT INTO objects VALUES (?)", [("a",), ("b",), ("c",)])
    con.commit()
    con.close()

    con = sqlite3.connect(dharma / "agent_memory/memories.db")
    con.execute("CREATE TABLE memories (id TEXT)")
    con.execute("INSERT INTO memories VALUES ('m1')")
    con.commit()
    con.close()

    con = sqlite3.connect(dharma / "state/knowledge.db")
    con.execute("CREATE TABLE propositions (id TEXT)")
    con.commit()
    con.close()

    con = sqlite3.connect(dharma / "board/event_log.sqlite3")
    con.execute("CREATE TABLE board_events (kind TEXT)")
    con.executemany(
        "INSERT INTO board_events VALUES (?)",
        [("card_created",), ("card_created",), ("card_claimed",)],
    )
    con.commit()
    con.close()


def test_pack_runs_and_emits_identity_one_line(tmp_path: Path) -> None:
    result = _run_pack(home=tmp_path / "home")
    assert result.returncode == 0, result.stderr[-2000:]
    assert ONE_LINE_FRAGMENT in result.stdout
    assert "DARSHAN PACK" in result.stdout


def test_pack_emits_counts_and_board_sections_with_live_dbs(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _seed_dharma_home(home)
    result = _run_pack(home=home)
    assert result.returncode == 0, result.stderr[-2000:]
    out = result.stdout
    assert "## 3. State fullness" in out
    assert "Ontology objects (~/.dharma/ontology.db): 3" in out
    assert "Memory atoms (~/.dharma/agent_memory/memories.db): 1" in out
    assert "Knowledge propositions (~/.dharma/state/knowledge.db): 0" in out
    assert "## 4. Task board snapshot" in out
    assert "event_log.sqlite3: 3 event(s)" in out
    assert "card_created: 2" in out


def test_pack_handles_absent_dbs_without_creating_them(tmp_path: Path) -> None:
    home = tmp_path / "empty-home"
    home.mkdir()
    result = _run_pack(home=home)
    assert result.returncode == 0, result.stderr[-2000:]
    out = result.stdout
    assert "Ontology objects (~/.dharma/ontology.db): absent" in out
    assert "Knowledge propositions (~/.dharma/state/knowledge.db): absent" in out
    assert "Task board: absent" in out
    # Looking must never create runtime state (read-only doctrine).
    assert not (home / ".dharma").exists()


def test_pack_lists_active_tracks_from_declared_intent(tmp_path: Path) -> None:
    result = _run_pack(home=tmp_path / "home")
    assert result.returncode == 0
    assert "## 2. Active tracks" in result.stdout
    # At least one ACTIVE track id from ACTIVE_TRACK.yaml must appear;
    # portfolio floor is min_active: 1 (docs/governance/ACTIVE_TRACK.yaml).
    assert "- `" in result.stdout.split("## 2. Active tracks", 1)[1]


def test_pack_out_flag_writes_file(tmp_path: Path) -> None:
    out_path = tmp_path / "pack" / "darshan_pack.md"
    result = _run_pack("--out", str(out_path), home=tmp_path / "home")
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout == ""
    text = out_path.read_text(encoding="utf-8")
    assert ONE_LINE_FRAGMENT in text


def test_pack_stays_under_token_ceiling(tmp_path: Path) -> None:
    result = _run_pack(home=tmp_path / "home")
    # <=4000 tokens at the conservative ~4 chars/token bound used by the
    # generator (MAX_PACK_CHARS in darshan_pack.py).
    assert len(result.stdout) <= 16000


def test_pack_is_deterministic_for_fixed_state(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _seed_dharma_home(home)
    first = _run_pack(home=home)
    second = _run_pack(home=home)
    assert first.stdout == second.stdout


# --- onboard KNOWLEDGE STORES section -----------------------------------------


def _clean_committed_checkout(destination: Path) -> None:
    """Clone the repo and overlay the working implementation, committed.

    Mirrors tests/test_make_onboarding_contract.py::_copy_tracked_checkout but
    also overlays untracked non-ignored files so a not-yet-committed
    implementation (this feature during development) is exercised. Committing
    everything gives onboard a genuinely clean tree, so its verdict is READY
    regardless of the developer working tree's state.
    """
    subprocess.run(
        ["git", "clone", "--quiet", "--shared", str(REPO_ROOT), str(destination)],
        check=True,
        timeout=120,
    )
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        timeout=60,
    ).stdout
    for raw_relative in listed.split(b"\0"):
        if not raw_relative:
            continue
        relative = os.fsdecode(raw_relative)
        source = REPO_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.unlink(missing_ok=True)
            target.symlink_to(os.readlink(source))
        elif source.is_file():
            target.write_bytes(source.read_bytes())
        elif not source.exists():
            target.unlink(missing_ok=True)
    subprocess.run(
        ["git", "-C", str(destination), "add", "-A"], check=True, timeout=60
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(destination),
            "-c",
            "user.name=Darshan Pack Test",
            "-c",
            "user.email=darshan-pack-test@example.invalid",
            "commit",
            "--quiet",
            "--allow-empty",
            "-m",
            "snapshot implementation under test",
        ],
        check=True,
        timeout=60,
    )


@pytest.mark.timeout(180)
def test_onboard_exits_zero_and_prints_knowledge_stores(tmp_path: Path) -> None:
    checkout = tmp_path / "clean-checkout"
    _clean_committed_checkout(checkout)
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "scripts/governance/agent_onboard.py"],
        cwd=checkout,
        env=env,
        capture_output=True,
        text=True,
        timeout=150,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-3000:]
    out = result.stdout
    assert "KNOWLEDGE STORES" in out
    assert "Wiki pages (docs/wiki/*.md):" in out
    # Fresh HOME: every runtime store must be announced as absent, not hidden.
    assert "Memory atoms (~/.dharma/agent_memory/memories.db): absent" in out
    assert "Ontology objects (~/.dharma/ontology.db): absent" in out
    assert "Knowledge propositions (~/.dharma/state/knowledge.db): absent" in out


@pytest.mark.timeout(120)
def test_onboard_json_output_stays_pure_json(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT), "--json"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=110,
    )
    payload = json.loads(result.stdout)  # must not raise
    assert "KNOWLEDGE STORES" not in result.stdout
    assert isinstance(payload, dict)
