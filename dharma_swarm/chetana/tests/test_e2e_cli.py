"""End-to-end CLI tests via real subprocess invocation.

Exercises the full chetana CLI surface against a sandboxed ~/.dharma/ tree.
Each test sets HOME to a tmp dir so chetana's roots redirect cleanly without
touching the operator's real wiki or staging.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


CHETANA_CLI = [sys.executable, "-m", "dharma_swarm.chetana.cli"]
REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def cli_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set HOME to a tmp dir so chetana's Path.home() resolves there."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    from dharma_swarm.dharma_kernel import DharmaKernel, KernelGuard

    asyncio.run(KernelGuard(home / ".dharma" / "kernel.json").save(DharmaKernel.create_default()))
    return home


def _run(args: list[str], home: Path, **kwargs) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    return subprocess.run(
        CHETANA_CLI + args,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        timeout=30,
        **kwargs,
    )


def test_cli_status_runs_against_empty_home(cli_home: Path):
    proc = _run(["status"], home=cli_home)
    assert proc.returncode == 0, proc.stderr
    assert "chetana status" in proc.stdout
    assert "staged    : 0" in proc.stdout
    assert "trusted   : 0" in proc.stdout
    assert "quarantine: 0" in proc.stdout
    assert str(cli_home) not in proc.stdout


def test_cli_help_shows_all_subcommands(cli_home: Path):
    proc = _run(["--help"], home=cli_home)
    assert proc.returncode == 0
    for sub in [
        "ingest",
        "promote",
        "decay",
        "revive",
        "gap-scan",
        "palace",
        "query",
        "cross-update",
        "status",
    ]:
        assert sub in proc.stdout, f"subcommand {sub} missing from --help"


def test_cli_ingest_then_status(cli_home: Path):
    proc = _run(
        [
            "ingest",
            "this is an inline note",
            "--kind", "note",
            "--title", "CLI ingest test",
            "--confidence", "0.7",
            "--captured-by", "cli-e2e-test",
        ],
        home=cli_home,
    )
    assert proc.returncode == 0, proc.stderr
    assert "1 staged" in proc.stdout

    proc2 = _run(["status"], home=cli_home)
    assert "staged    : 1" in proc2.stdout
    assert str(cli_home) not in proc2.stdout


def test_cli_full_pipeline_ingest_promote_decay_revive(cli_home: Path):
    """The complete capture → promote → decay → revive flow via CLI."""
    # 1. INGEST
    p1 = _run(
        [
            "ingest",
            "Strange loops emerge from tangled hierarchies in transformer self-attention.",
            "--kind", "note",
            "--title", "E2E pipeline atom",
            "--tag", "consciousness",
            "--tag", "hofstadter",
        ],
        home=cli_home,
    )
    assert p1.returncode == 0, p1.stderr
    # find the staged path
    staging_root = cli_home / ".dharma" / "knowledge" / "staging"
    staged_paths = list(staging_root.rglob("*.md"))
    assert len(staged_paths) == 1
    staged = staged_paths[0]

    # 2. PROMOTE — lands in the PENDING root, not the trusted projection
    p2 = _run(["promote", str(staged), "--promoted-by", "cli-e2e"], home=cli_home)
    assert p2.returncode == 0, p2.stderr
    assert "promoted" in p2.stdout.lower()

    trusted_dir = cli_home / ".dharma" / "knowledge" / "wiki" / "concepts"
    pending_dir = cli_home / ".dharma" / "knowledge" / "wiki" / "pending"
    assert list(trusted_dir.glob("*.md")) == []
    pending_paths = list(pending_dir.glob("*.md"))
    assert len(pending_paths) == 1
    assert not staged.exists()  # staged file removed after promote

    # 2b. STATUS reflects pending, not trusted
    p2s = _run(["status"], home=cli_home)
    assert "pending   : 1" in p2s.stdout
    assert "trusted   : 0" in p2s.stdout

    # 2c. APPROVE — the only door into the trusted projection
    p2a = _run(
        ["approve", str(pending_paths[0]), "--reviewer", "cli-e2e"], home=cli_home
    )
    assert p2a.returncode == 0, p2a.stderr
    assert "approved" in p2a.stdout.lower()
    trusted_paths = list(trusted_dir.glob("*.md"))
    assert len(trusted_paths) == 1
    assert not pending_paths[0].exists()

    # 3. STATUS reflects approve — on-disk only: with no signed trust
    # manifest in the sandbox home, the trusted projection stays EMPTY
    # (PR-08 fail-closed); the approved page shows up as manifest drift
    p3 = _run(["status"], home=cli_home)
    assert "trusted   : 0 (on-disk: 1)" in p3.stdout
    assert "pending   : 0" in p3.stdout
    assert "staged    : 0" in p3.stdout
    assert str(cli_home) not in p3.stdout

    verify = _run(["verify", "--show", "1"], home=cli_home)
    assert verify.returncode == 0, verify.stderr
    assert str(cli_home) not in verify.stdout
    assert trusted_paths[0].name not in verify.stdout

    # 4. DECAY (no stale yet → 0 stale, no quarantine)
    p4 = _run(["decay"], home=cli_home)
    assert p4.returncode == 0
    assert "Stale: 0" in p4.stdout

    # 5. Force the trusted atom to be stale, then DECAY again — should suggest revive
    trusted = trusted_paths[0]
    text = trusted.read_text(encoding="utf-8")
    # set stale_after to a past date (yaml-quoted to round-trip cleanly)
    new_text = []
    replaced = False
    for line in text.splitlines():
        if line.startswith("stale_after:") and not replaced:
            new_text.append("stale_after: '2020-01-01'")
            replaced = True
        else:
            new_text.append(line)
    trusted.write_text("\n".join(new_text) + "\n", encoding="utf-8")

    p5 = _run(["decay"], home=cli_home)
    assert p5.returncode == 0
    assert "Stale: 1" in p5.stdout
    assert "revive" in p5.stdout.lower(), "decay output should suggest revive"

    # 6. REVIVE --all (proposal only, no apply)
    p6 = _run(["revive", "--all"], home=cli_home)
    assert p6.returncode == 0, p6.stderr
    assert "E2E pipeline atom" in p6.stdout

    # 7. REVIVE --all --apply — atom rewritten with revival_chain
    p7 = _run(["revive", "--all", "--apply", "--reviewer", "cli-revival"], home=cli_home)
    assert p7.returncode == 0, p7.stderr

    # 8. Verify revival_chain in the trusted atom's frontmatter
    revived_text = trusted.read_text(encoding="utf-8")
    assert "revival_chain" in revived_text
    assert "cli-revival" in revived_text


def test_cli_gap_scan_runs(cli_home: Path):
    """gap-scan should run cleanly even on an empty corpus."""
    proc = _run(["gap-scan"], home=cli_home)
    assert proc.returncode == 0, proc.stderr
    assert "Gap scan" in proc.stdout


def test_cli_palace_renders_canvas(cli_home: Path):
    """palace --render produces a JSON Canvas file (even on empty corpus, rooms render)."""
    proc = _run(["palace"], home=cli_home)
    assert proc.returncode == 0, proc.stderr
    canvas_path = cli_home / ".dharma" / "knowledge" / "memory_palace.canvas"
    assert canvas_path.exists()
    canvas = json.loads(canvas_path.read_text())
    assert "nodes" in canvas
    # the 15 pillar/system rooms should always render
    rooms = [n for n in canvas["nodes"] if n.get("type") == "group"]
    assert len(rooms) >= 10


def test_cli_query_returns_coverage_block(cli_home: Path):
    proc = _run(["query", "strange loop"], home=cli_home)
    assert proc.returncode == 0, proc.stderr
    assert "Unified graph query" in proc.stdout
