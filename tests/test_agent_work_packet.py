from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "governance" / "run_agent_work_packet.py"


def run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def init_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert run(["git", "init"], cwd=repo).returncode == 0
    assert run(["git", "config", "user.email", "test@example.invalid"], cwd=repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], cwd=repo).returncode == 0
    (repo / ".gitignore").write_text(".dharma/\n", encoding="utf-8")
    (repo / "allowed.txt").write_text("initial\n", encoding="utf-8")
    assert run(["git", "add", ".gitignore", "allowed.txt"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "init"], cwd=repo).returncode == 0
    return repo


def write_packet(repo: Path, payload: dict[str, object]) -> Path:
    packet_dir = repo / ".dharma" / "agentops" / "jobs"
    packet_dir.mkdir(parents=True)
    packet = packet_dir / "job.json"
    packet.write_text(json.dumps(payload), encoding="utf-8")
    return packet


def test_agent_work_packet_runs_commands_and_writes_report(tmp_path: Path) -> None:
    repo = init_git_repo(tmp_path)
    packet = write_packet(
        repo,
        {
            "id": "test-job",
            "scope": {"allowed_files": ["allowed.txt"]},
            "commands": [
                {
                    "name": "python-smoke",
                    "argv": [sys.executable, "-c", "print('packet ok')"],
                    "cwd": ".",
                }
            ],
        },
    )

    result = run([sys.executable, str(RUNNER), "--packet", str(packet)], cwd=repo)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Status: passed" in result.stdout
    report = json.loads((repo / ".dharma" / "agentops" / "runs" / "test-job.json").read_text())
    assert report["commands"][0]["exit_code"] == 0
    assert "packet ok" in report["commands"][0]["stdout"]


def test_agent_work_packet_blocks_dirty_files_outside_scope(tmp_path: Path) -> None:
    repo = init_git_repo(tmp_path)
    (repo / "outside.txt").write_text("not in scope\n", encoding="utf-8")
    packet = write_packet(
        repo,
        {
            "id": "scope-test",
            "scope": {"allowed_files": ["allowed.txt"]},
            "commands": [],
        },
    )

    result = run(
        [sys.executable, str(RUNNER), "--packet", str(packet), "--check-only", "--no-report"],
        cwd=repo,
    )

    assert result.returncode == 1
    assert "outside_allowed_scope: outside.txt" in result.stdout


def test_agent_work_packet_rejects_mutating_git_commands(tmp_path: Path) -> None:
    repo = init_git_repo(tmp_path)
    packet = write_packet(
        repo,
        {
            "id": "git-mutation-test",
            "scope": {"allowed_files": ["allowed.txt"]},
            "commands": [{"name": "bad", "argv": ["/usr/bin/git", "add", "."]}],
        },
    )

    result = run([sys.executable, str(RUNNER), "--packet", str(packet), "--dry-run"], cwd=repo)

    assert result.returncode == 2
    assert "forbidden mutating git command: /usr/bin/git add" in result.stderr
