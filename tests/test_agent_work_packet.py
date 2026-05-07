from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = REPO_ROOT / "scripts" / "governance" / "run_agent_work_packet.py"

spec = importlib.util.spec_from_file_location("run_agent_work_packet", RUNNER_PATH)
assert spec is not None
agentops = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = agentops
spec.loader.exec_module(agentops)


def run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert run(["git", "init"], cwd=repo).returncode == 0
    assert run(["git", "config", "user.email", "agentops@example.invalid"], cwd=repo).returncode == 0
    assert run(["git", "config", "user.name", "AgentOps Test"], cwd=repo).returncode == 0
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    assert run(["git", "add", "README.md"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "init"], cwd=repo).returncode == 0
    return repo


def minimal_packet(tmp_path: Path, repo: Path, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "agentops-test",
        "base_ref": "HEAD",
        "branch": "chore/agentops-test",
        "worktree": str(tmp_path / "worktree"),
        "intent": "Verify AgentOps test packet.",
        "allowed_files": ["allowed.txt", "reports/agentops/**"],
        "forbidden_files": ["forbidden.txt"],
        "gates": [{"name": "smoke", "command": f"{sys.executable} -c \"print('ok')\""}],
        "commit": {"allowed": False, "message": "chore(agentops): test"},
        "approval": {"before_commit": True, "before_merge": True},
    }
    payload.update(overrides)
    return payload


def write_packet(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "packet.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_parses_minimal_valid_work_packet(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    packet = agentops.parse_work_packet(minimal_packet(tmp_path, repo))

    assert packet.id == "agentops-test"
    assert packet.base_ref == "HEAD"
    assert packet.branch == "chore/agentops-test"
    assert packet.allowed_files == ["allowed.txt", "reports/agentops/**"]
    assert packet.forbidden_files == ["forbidden.txt"]
    assert packet.gates[0].name == "smoke"
    assert packet.commit.allowed is False
    assert packet.approval.before_merge is True


def test_rejects_missing_required_fields(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    payload = minimal_packet(tmp_path, repo)
    del payload["base_ref"]

    try:
        agentops.parse_work_packet(payload)
    except agentops.AgentOpsError as exc:
        assert "base_ref" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected missing field rejection")


def test_allowed_file_matching() -> None:
    assert agentops.path_matches_pattern("docs/governance/AGENTOPS.md", "docs/**")
    assert agentops.path_matches_pattern("docs/governance/AGENTOPS.md", "docs/governance/AGENTOPS.md")
    assert not agentops.path_matches_pattern("api/main.py", "docs/**")


def test_forbidden_file_matching() -> None:
    assert agentops.matching_patterns("api/main.py", ["api/**"])
    assert agentops.matching_patterns("dharma_swarm/telos_gates.py", ["dharma_swarm/telos_gates.py"])
    assert not agentops.matching_patterns("docs/governance/AGENTOPS.md", ["api/**"])


def test_detects_out_of_scope_changed_files(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    packet = agentops.parse_work_packet(minimal_packet(tmp_path, repo))
    (repo / "outside.txt").write_text("dirty\n", encoding="utf-8")

    scope = agentops.inspect_scope(repo, packet)

    assert scope.violations == [
        {"path": "outside.txt", "reason": "outside_allowed_scope", "patterns": []}
    ]


def test_detects_forbidden_changed_files(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    packet = agentops.parse_work_packet(minimal_packet(tmp_path, repo))
    (repo / "forbidden.txt").write_text("dirty\n", encoding="utf-8")

    scope = agentops.inspect_scope(repo, packet)

    assert scope.violations == [
        {"path": "forbidden.txt", "reason": "forbidden", "patterns": ["forbidden.txt"]}
    ]


def test_gate_result_recording(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    gate = agentops.parse_gate(
        {"name": "record", "command": f"{sys.executable} -c \"print('gate output')\""},
        0,
    )

    result = agentops.run_gate(repo, gate)

    assert result["name"] == "record"
    assert result["command"].startswith(sys.executable)
    assert result["exit_code"] == 0
    assert result["passed"] is True
    assert "gate output" in result["output"]


def test_dry_run_does_not_mutate(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    payload = minimal_packet(tmp_path, repo)
    packet_path = write_packet(tmp_path, payload)
    worktree = Path(str(payload["worktree"]))

    exit_code, report = agentops.execute_packet(packet_path, source_root=repo, dry_run=True)

    assert exit_code == 0
    assert report is None
    assert not worktree.exists()


def test_commit_policy_refuses_when_gates_fail(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    payload = minimal_packet(
        tmp_path,
        repo,
        gates=[{"name": "fail", "command": f"{sys.executable} -c \"raise SystemExit(7)\""}],
        commit={"allowed": True, "message": "chore(agentops): should not commit"},
        approval={"before_commit": False, "before_merge": True},
    )
    packet_path = write_packet(tmp_path, payload)

    exit_code, report = agentops.execute_packet(packet_path, source_root=repo)

    assert exit_code == 1
    assert report is not None
    assert report["commit_hash"] is None
    assert report["commit_decision"] == "one or more gates failed"


def test_commit_policy_refuses_when_human_approval_required(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    write_command = (
        f"{sys.executable} -c "
        "\"from pathlib import Path; Path('allowed.txt').write_text('dirty', encoding='utf-8')\""
    )
    payload = minimal_packet(
        tmp_path,
        repo,
        gates=[{"name": "write-allowed", "command": write_command}],
        commit={"allowed": True, "message": "chore(agentops): should wait"},
        approval={"before_commit": True, "before_merge": True},
    )
    packet_path = write_packet(tmp_path, payload)

    exit_code, report = agentops.execute_packet(packet_path, source_root=repo)

    assert exit_code == 0
    assert report is not None
    assert report["commit_hash"] is None
    assert report["commit_decision"] == "human approval required before commit"


def test_report_paths_are_predictable(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    json_path, md_path = agentops.report_paths(repo, "job-1", "20260101T000000000000Z")

    assert json_path == repo / "reports" / "agentops" / "job-1" / "20260101T000000000000Z" / "report.json"
    assert md_path == repo / "reports" / "agentops" / "job-1" / "20260101T000000000000Z" / "report.md"


def test_no_merge_no_push_behavior_is_structurally_enforced() -> None:
    for command in ("git merge main", "git push origin HEAD"):
        try:
            agentops.parse_gate({"name": "blocked", "command": command}, 0)
        except agentops.AgentOpsError as exc:
            assert "not allowed" in str(exc)
        else:  # pragma: no cover
            raise AssertionError(f"expected {command} to be rejected")


def test_gate_commands_may_not_hide_mutation_inside_shell() -> None:
    for command in ("sh -c 'git push origin HEAD'", "bash -lc 'git merge main'"):
        try:
            agentops.parse_gate({"name": "blocked-shell", "command": command}, 0)
        except agentops.AgentOpsError as exc:
            assert "shell executable" in str(exc)
        else:  # pragma: no cover
            raise AssertionError(f"expected {command} to be rejected")
