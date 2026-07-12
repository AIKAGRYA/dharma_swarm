from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from dharma_swarm.memory_kernel.write_receipts import stable_digest


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
        # Positive gates must come from an O4-B11 allowlisted family.
        "gates": [{"name": "smoke", "command": "git status --porcelain"}],
        "commit": {"allowed": False, "message": "chore(agentops): test"},
        "approval": {"before_commit": True, "before_merge": True},
    }
    payload.update(overrides)
    return payload


def stub_gate_script(repo: Path, body: str) -> str:
    """Install a committed fixture stub at an O4-B11-allowlisted script path.

    Positive gates pass the command-family allowlist before execution, so
    fixtures that need scripted gate behavior (specific exits, file writes)
    route through an enumerated repo-script name instead of ``python -c``.
    The allowlist is lexical command-family confinement by design — the
    stub demonstrates, not defeats, that boundary."""
    rel = "scripts/governance/agent_onboard.py"
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    assert run(["git", "add", rel], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "fixture: stub gate script"], cwd=repo).returncode == 0
    return f"{sys.executable} {rel}"


def write_packet(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "packet.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def init_session_repo(tmp_path: Path) -> Path:
    repo = init_repo(tmp_path)
    track = repo / "docs/governance/ACTIVE_TRACK.yaml"
    track.parent.mkdir(parents=True)
    row = {
        "id": "onboard-one-door-2026-07",
        "status": "ACTIVE",
        "owner": "@AmitabhainArunachala",
        "owned_surfaces": ["tests/**", "reports/agentops/work_packets/**"],
    }
    track.write_text(
        json.dumps({"active_tracks": [row]}), encoding="utf-8"
    )
    assert run(["git", "add", track.relative_to(repo).as_posix()], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add active track"], cwd=repo).returncode == 0
    return repo


def session_packet(repo: Path, **overrides: object) -> dict[str, object]:
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    branch = run(["git", "branch", "--show-current"], cwd=repo).stdout.strip()
    packet_id = "onboard-one-door-WP-O1-test"
    payload: dict[str, object] = {
        "id": packet_id, "base_ref": head, "branch": branch, "worktree": ".",
        "intent": "Exercise the portable WP-O1 Session Entry contract.",
        "allowed_files": ["allowed.txt", f"reports/agentops/work_packets/{packet_id}.json"],
        "forbidden_files": ["forbidden.txt"],
        "gates": [
            {"name": "declared-gate", "command": "git status --porcelain",
             "expected_exit": 0}
        ],
        "negative_controls": [
            {"name": "declared-negative", "command": f'{sys.executable} -c "raise SystemExit(0)"',
             "expected_exit": 0}
        ],
        "commit": {"allowed": False, "message": "test: session packet"},
        "approval": {"before_commit": True, "before_merge": True},
        "session_entry": {
            "schema": "dharma_swarm.session_entry.v1",
            "tool_versions": {
                "python": agentops._probe_tool_version("python", repo),
                "git": agentops._probe_tool_version("git", repo),
            },
            "authority_precedence": ["executable", "tests", "locks", "git", "owner_files"],
            "work_packet": "WP-O1",
            "active_track": "onboard-one-door-2026-07",
            "owner": "@AmitabhainArunachala",
            "collision": {"status": "clear", "checked_at_sha": head, "details": []},
            "interface_mismatches": [],
            "closest_existing_implementation": ["README.md"],
            "honest_blockers": [],
            "rollback": "remove the test packet",
            "packet_digest": "",
        },
    }
    payload.update(overrides)
    return payload


def seal_packet(payload: dict[str, object]) -> dict[str, object]:
    sealed = copy.deepcopy(payload)
    reseal_packet(sealed)
    return sealed


def write_external_packet(root: Path, payload: dict[str, object]) -> Path:
    path = root / "ops/session-entry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def tracked_packet_path(repo: Path, payload: dict[str, object]) -> Path:
    return repo / "reports/agentops/work_packets" / f"{payload['id']}.json"


def stage_path(repo: Path, path: Path) -> None:
    relative = path.relative_to(repo).as_posix()
    assert run(["git", "add", "--", relative], cwd=repo).returncode == 0


def tree_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def reseal_packet(payload: dict[str, object]) -> None:
    entry = payload["session_entry"]
    assert isinstance(entry, dict)
    entry["packet_digest"] = agentops.packet_digest(payload)


def install_source_write_guard(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    def require_external(path: Path) -> None:
        try:
            path.resolve().relative_to(repo.resolve())
        except ValueError:
            return
        raise AssertionError(f"AgentOps attempted a source/.git write: {path}")

    def guard(name: str) -> None:
        original = getattr(Path, name)
        def guarded(path: Path, *args: object, _original=original, **kwargs: object):
            require_external(path)
            return _original(path, *args, **kwargs)
        monkeypatch.setattr(Path, name, guarded)
    for name in ("write_text", "write_bytes", "mkdir", "touch"):
        guard(name)

    original_replace = Path.replace
    def guarded_replace(path: Path, target: Path) -> Path:
        require_external(path)
        require_external(Path(target))
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", guarded_replace)


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
    assert not agentops.path_matches_pattern("gitignore", ".gitignore")
    assert not agentops.path_matches_pattern(".gitignore", "gitignore")
    assert not agentops.path_matches_pattern(
        "github/workflows/structure.yml", ".github/workflows/structure.yml"
    )


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


def test_runner_minimal_help_writes_no_repo_bytecode(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    pycache_prefix = tmp_path / "pycache-prefix"
    env["PYTHONPYCACHEPREFIX"] = str(pycache_prefix)

    result = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "--help"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    repo_cache = pycache_prefix / REPO_ROOT.as_posix().lstrip("/")
    assert not repo_cache.exists()


def test_commit_policy_refuses_when_gates_fail(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    fail_command = stub_gate_script(repo, "raise SystemExit(7)\n")
    payload = minimal_packet(
        tmp_path,
        repo,
        gates=[{"name": "fail", "command": fail_command}],
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
    write_command = stub_gate_script(
        repo,
        "from pathlib import Path\n"
        "Path('allowed.txt').write_text('dirty', encoding='utf-8')\n",
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
    for command in (
        "sh -c 'git push origin HEAD'",
        "bash -lc 'git merge main'",
        "env sh -c 'git push origin HEAD'",
        "env git push origin HEAD",
        "sudo -n git push origin HEAD",
    ):
        try:
            agentops.parse_gate({"name": "blocked-shell", "command": command}, 0)
        except agentops.AgentOpsError as exc:
            assert "shell/wrapper executable" in str(exc)
        else:  # pragma: no cover
            raise AssertionError(f"expected {command} to be rejected")


def test_gate_command_normalization_rejects_live_targets_without_blocking_safe_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def must_not_execute(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("command normalization must not execute a gate")

    monkeypatch.setattr(agentops, "run_command", must_not_execute)
    rejected = (
        "live_swarm",
        "live-swarm",
        "orchestrate-live",
        "autonomy-daemon",
        "autonomous-daemon",
        "./live_swarm",
        "scripts/runtime/live_swarm.py",
        "./scripts/runtime/live_swarm.py",
        "/absolute/path/to/live_swarm.py",
        "python3 scripts/runtime/live_swarm.py",
        "python3 ./scripts/runtime/live_swarm.py",
        "python3 -m dharma_swarm.live_swarm",
        "python3 -m Dharma_Swarm.LIVE_SWARM",
        "python dharma_swarm/orchestrate_live.py",
        "python3.13 -m dharma_swarm.orchestrate_live",
        ".venv/bin/python scripts/runtime/autonomy-daemon.py",
        "/usr/bin/python3 -m dharma_swarm.autonomy_daemon",
        "python.exe scripts/runtime/autonomous-daemon.py",
        'python.exe "C:\\scripts\\runtime\\live_swarm.py"',
        'python.exe "C:\\scripts\\runtime\\live_swarm.py."',
        'python.exe "C:\\scripts\\runtime\\live_swarm.py "',
        'python.exe "C:\\scripts\\runtime\\live_swarm.py.::$DATA"',
        "python.exe C:live_swarm.py",
        "python.exe C:orchestrate_live.py",
        "C:live_swarm.exe",
        "py -3 -m dharma_swarm.autonomous_daemon",
    )
    accepted = (
        (
            "python3 -m pytest tests/test_agent_work_packet.py -q",
            ["python3", "-m", "pytest", "tests/test_agent_work_packet.py", "-q"],
        ),
        (
            "python3 scripts/governance/check_track_status.py",
            ["python3", "scripts/governance/check_track_status.py"],
        ),
        ("make docops-integrity", ["make", "docops-integrity"]),
        (
            "python3 scripts/governance/check_name_drift.py",
            ["python3", "scripts/governance/check_name_drift.py"],
        ),
        (
            "python3 scripts/governance/repo_status.py",
            ["python3", "scripts/governance/repo_status.py"],
        ),
        (
            'python3 -c "print(\'ordinary non-live Python\')"',
            ["python3", "-c", "print('ordinary non-live Python')"],
        ),
        (
            "python3 scripts/runtime/live_swarm_report.py",
            ["python3", "scripts/runtime/live_swarm_report.py"],
        ),
        (
            "python3 -m dharma_swarm.live_swarm_report",
            ["python3", "-m", "dharma_swarm.live_swarm_report"],
        ),
    )
    rejected_results: list[tuple[str, list[str] | None, str | None]] = []
    accepted_results: list[tuple[str, list[str] | None, list[str]]] = []
    for index, command in enumerate(rejected):
        try:
            gate = agentops.parse_gate({"name": f"live-rejected-{index}", "command": command}, index)
        except agentops.AgentOpsError as exc:
            rejected_results.append((command, None, str(exc)))
        else:
            rejected_results.append((command, gate.argv, None))
    for index, (command, expected_argv) in enumerate(accepted):
        try:
            gate = agentops.parse_gate({"name": f"live-accepted-{index}", "command": command}, index)
        except agentops.AgentOpsError:
            accepted_results.append((command, None, expected_argv))
        else:
            accepted_results.append((command, gate.argv, expected_argv))

    assert all(
        error and "live swarm/autonomy" in error
        for _, _, error in rejected_results
    ), rejected_results
    assert all(actual == expected for _, actual, expected in accepted_results), accepted_results


def test_gate_rejects_git_global_options_and_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def must_not_execute(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("direct Git lexical validation must not execute a gate")

    monkeypatch.setattr(agentops, "run_command", must_not_execute)
    rejected_commands = [
        "git -C . status --short",
        "git -c core.sshCommand=/bin/false status --short",
        "git --git-dir=.git status --short",
        "git --git-dir .git status --short",
        "git --work-tree=. status --short",
        "git --work-tree . status --short",
        "git --exec-path=/tmp status --short",
        "git --config-env=core.sshCommand=GIT_SSH_COMMAND status --short",
        "git --no-pager status --short",
        "git -c alias.x=push x origin HEAD",
        'git -c "alias.x=!printf ALIAS_EXECUTED" x',
        "git x",
        "git fetch origin main",
        "git push origin HEAD",
        "git merge main",
        "git diff --output=/tmp/agentops-write",
        "git diff --output /tmp/agentops-write",
        "git diff --ext-diff HEAD",
        "git diff --textconv HEAD",
        "git-push origin HEAD",
        "/usr/local/libexec/git-core/git-push origin HEAD",
        "git-send-pack origin HEAD",
        "git-http-push origin HEAD",
        "./git status --short",
        "bin/git diff --check",
        "../git rev-parse HEAD",
        "./git.exe status --short",
        '"bin\\git.exe" status --short',
        "C:git.exe status --short",
        "/tmp/git status --short",
        "/usr/local/bin/git status --short",
        '"\\\\server\\share\\git.exe" status --short',
        '"D:\\Program Files\\Git\\cmd\\git.exe" status --short',
        "ℊit status --short",
        "ｇｉｔ.exe status --short", '"./ｇｉｔ.exe." status --short', '"./ｇｉｔ＿push.exe" status --short',
        '"./ℊit" diff --check',
        "git-push.git status --short",
        "/tmp/git-push.git status --short",
        "git-push.exe.git status --short",
        "git_push.git status --short",
        "GIT-PUSH.GIT status --short",
        "git-push.git. status --short",
        "git-push.git::$DATA status --short",
        "/tmp/git.fake status --short",
        "git.fake status --short",
        "GIT.FAKE status --short",
        '"C:\\tmp\\git.fake" status --short',
        "git.fake. status --short",
        "git.fake::$DATA status --short",
        "git. status --short",
        "git.exe. status --short",
        '"git.exe " status --short',
        "git.exe::$DATA status --short",
        "git.exe.::$DATA status --short",
        "git.exe:payload status --short",
        '"git " status --short',
        "git:payload status --short",
        "git::$DATA status --short",
        '"./git " status --short',
        '"./git:payload" status --short',
        '"C:\\tmp\\git " status --short',
        '"C:\\tmp\\git::$DATA" status --short',
        "/tmp/C:git.exe status --short",
        "./C:git status --short",
        "/tmp/C:git::$DATA status --short",
        '"./C:git " status --short',
        "/tmp/C:git.exe. status --short",
        "/tmp/C:git-push status --short",
        '"C:\\Program Files\\Git\\cmd\\git.exe." status --short',
        '"C:\\Program Files\\Git\\cmd\\git.exe " status --short',
        '"C:\\Program Files\\Git\\cmd\\git.exe.::$DATA" status --short',
        '"C:\\Program Files\\Git\\cmd\\git.exe:payload" status --short', '"./ｇｉｔ-push.exe." status --short', "C:ｇｉｔ.exe status --short",
        '"C:\\Program Files\\Git\\mingw64\\libexec\\git-core\\git-push.exe" origin HEAD',
        '"C:\\Program Files\\Git\\cmd\\git.exe." push origin HEAD',
        '"C:\\Program Files\\Git\\cmd\\git.exe " push origin HEAD',
        '"C:\\Program Files\\Git\\cmd\\git.exe.::$DATA" push origin HEAD',
        "C:git.exe push origin HEAD",
        "C:git-push.exe origin HEAD",
        "git.exe push origin HEAD",
        "git status --branch",
        "git status --porcelain=v3",
        "git status --short --branch HEAD",
        "git diff HEAD --check",
        "git diff --check --",
        "git diff --check /absolute/path",
        "git diff --check C:outside",
        "git diff --check ../outside",
        'git diff --check "foo\\.. \\outside"',
        'git diff --check "foo\\.. .\\outside"',
        'git diff --check "foo\\... \\outside"',
        'git diff --check "foo\\.. ..\\outside"',
        'git diff --check "bad\npath"',
        "git diff --check -- ':(literal)../outside'",
        "git diff --check -- ':!../outside'",
        "git diff --check -- ':(glob)../*'",
        "git diff --check -- ':(literal)/etc/passwd'",
        "git diff --check ':(literal)../outside'",
        "git diff --check ':!../outside'",
        "git diff --check ':(glob)../*'",
        "git diff --check ':0:../outside'",
        "git diff --check ':../outside'",
        "git diff --check 'HEAD:../outside'",
        "git diff --check 'HEAD:/outside'",
        "git diff --check 'HEAD@{10:00}:../outside'",
        "git diff --check 'HEAD@{2026-07-10T10:00:00}:../outside'",
        "git diff --check 'HEAD^{/foo:bar}:../outside'",
        "git diff --check 'HEAD^{/../}:../outside'",
        "git diff --check 'HEAD@{2026/../10}:../outside'",
        "git diff --check '..::$DATA'",
        "git diff --check -- '..::$DATA'",
        "git diff --check -- '..:secret:$DATA'",
        "git diff --check -- '..::$INDEX_ALLOCATION'",
        "git diff --check -- '.. .::$DATA'",
        "git diff --check -- '...::$DATA'",
        'git diff --check -- "foo\\..::$DATA"',
        "git rev-parse --verify origin/main",
        "git merge-base --is-ancestor HEAD",
        "git merge-base --is-ancestor --fork-point HEAD HEAD",
        "git merge-base --is-ancestor 'HEAD:../outside' HEAD",
        "git merge-base --is-ancestor 'HEAD@{10:00}:../outside' HEAD",
        "git merge-base --is-ancestor 'HEAD^{/../}:../outside' HEAD",
        "git ls-files --others",
        "git ls-files --others --exclude-standard docs",
        "git ls-files --others --exclude-standard -- C:outside",
        "git ls-files --others --exclude-standard -- ../outside",
        'git ls-files --others --exclude-standard -- "foo\\.. \\outside"',
        'git ls-files --others --exclude-standard -- "foo\\.. .\\outside"',
        'git ls-files --others --exclude-standard -- "foo\\... \\outside"',
        'git ls-files --others --exclude-standard -- "foo\\.. ..\\outside"',
        'git ls-files --others --exclude-standard -- "bad\tpath"',
        "git ls-files --others --exclude-standard -- ':(literal)../outside'",
        "git ls-files --others --exclude-standard -- ':!../outside'",
        "git ls-files --others --exclude-standard -- ':(glob)../*'",
        "git ls-files --others --exclude-standard -- ':(literal)/etc/passwd'",
        "git ls-files --others --exclude-standard -- '..::$DATA'",
        "git ls-files --others --exclude-standard -- '..:secret:$DATA'",
        "git ls-files --others --exclude-standard -- '..::$INDEX_ALLOCATION'",
        "git ls-files --others --exclude-standard -- '.. .::$DATA'",
        "git ls-files --others --exclude-standard -- '...::$DATA'",
        'git ls-files --others --exclude-standard -- "foo\\..::$DATA"',
    ]
    mutating_subcommands = (
        "am",
        "cherry-pick",
        "clean",
        "commit",
        "merge",
        "pull",
        "push",
        "rebase",
        "reset",
        "restore",
        "revert",
        "stash",
    )
    rejected_commands.extend(f"git {subcommand}" for subcommand in mutating_subcommands)
    rejected_commands.extend(f"git {subcommand}" for subcommand in ("branch", "config", "fetch", "remote", "show"))
    rejected_env = (
        {"command": "git status --short", "env": {"PATH": "/tmp/fake-git"}},
        {"command": "git diff --check", "env": {"GIT_EXTERNAL_DIFF": "/tmp/helper"}},
        {
            "command": "git diff --check",
            "env": {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "diff.external",
                "GIT_CONFIG_VALUE_0": "/tmp/helper",
            },
        },
    )
    accepted = (
        ("git status --short", ["git", "status", "--short"]),
        ("git status --short --branch", ["git", "status", "--short", "--branch"]),
        ("git status --porcelain=v2 --branch", ["git", "status", "--porcelain=v2", "--branch"]),
        ("git diff --check", ["git", "diff", "--check"]),
        ("git diff --check HEAD", ["git", "diff", "--check", "HEAD"]),
        (
            "git diff --check origin/main...HEAD",
            ["git", "diff", "--check", "origin/main...HEAD"],
        ),
        ("git diff --check ':/Merge'", ["git", "diff", "--check", ":/Merge"]),
        ("git diff --check ':/../'", ["git", "diff", "--check", ":/../"]),
        (
            "git diff --check 'HEAD:docs/file'",
            ["git", "diff", "--check", "HEAD:docs/file"],
        ),
        ("git diff --check ':0:docs/file'", ["git", "diff", "--check", ":0:docs/file"]),
        ("git diff --check 'HEAD:'", ["git", "diff", "--check", "HEAD:"]),
        (
            "git diff --check 'HEAD@{10:00}'",
            ["git", "diff", "--check", "HEAD@{10:00}"],
        ),
        ("git diff --check 'topic{draft'", ["git", "diff", "--check", "topic{draft"]),
        (
            "git diff --check 'HEAD^{/foo:bar}'",
            ["git", "diff", "--check", "HEAD^{/foo:bar}"],
        ),
        (
            "git diff --check 'HEAD^{/feature:../path}'",
            ["git", "diff", "--check", "HEAD^{/feature:../path}"],
        ),
        (
            "git diff --check 'HEAD@{2026/../10}'",
            ["git", "diff", "--check", "HEAD@{2026/../10}"],
        ),
        (
            "git diff --check 'HEAD@{10:00}:docs/file'",
            ["git", "diff", "--check", "HEAD@{10:00}:docs/file"],
        ),
        (
            "git diff --check -- docs/governance/AGENTOPS.md",
            ["git", "diff", "--check", "--", "docs/governance/AGENTOPS.md"],
        ),
        ("git rev-parse HEAD", ["git", "rev-parse", "HEAD"]),
        ("git rev-parse --verify HEAD", ["git", "rev-parse", "--verify", "HEAD"]),
        ("git rev-parse --show-toplevel", ["git", "rev-parse", "--show-toplevel"]),
        (
            "git rev-parse --abbrev-ref HEAD",
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        ),
        (
            "git merge-base --is-ancestor HEAD HEAD",
            ["git", "merge-base", "--is-ancestor", "HEAD", "HEAD"],
        ),
        (
            "git ls-files --others --exclude-standard",
            ["git", "ls-files", "--others", "--exclude-standard"],
        ),
        ("/usr/bin/git status --short", ["/usr/bin/git", "status", "--short"]),
        ("git.exe status --short", ["git.exe", "status", "--short"]),
        (
            '"C:\\Program Files\\Git\\cmd\\git.exe" status --short',
            ["C:\\Program Files\\Git\\cmd\\git.exe", "status", "--short"],
        ),
        ("git.foo/tool status --short", ["git.foo/tool", "status", "--short"]),
        ("./git.foo/tool status --short", ["./git.foo/tool", "status", "--short"]),
    )
    rejected_results: list[
        tuple[str, list[str] | None, dict[str, str] | None, str | None]
    ] = []
    for index, command in enumerate(rejected_commands):
        try:
            gate = agentops.parse_gate({"name": f"git-rejected-{index}", "command": command}, index)
        except agentops.AgentOpsError as exc:
            rejected_results.append((command, None, None, str(exc)))
        else:
            rejected_results.append((command, gate.argv, gate.env, None))
    for index, raw in enumerate(rejected_env, start=len(rejected_commands)):
        try:
            gate = agentops.parse_gate({"name": f"git-env-rejected-{index}", **raw}, index)
        except agentops.AgentOpsError as exc:
            rejected_results.append((str(raw), None, None, str(exc)))
        else:
            rejected_results.append((str(raw), gate.argv, gate.env, None))
    accepted_results: list[tuple[str, list[str] | None, dict[str, str] | None, list[str]]] = []
    for index, (command, expected_argv) in enumerate(accepted):
        try:
            gate = agentops.parse_gate({"name": f"git-accepted-{index}", "command": command}, index)
        except agentops.AgentOpsError:
            accepted_results.append((command, None, None, expected_argv))
        else:
            accepted_results.append((command, gate.argv, gate.env, expected_argv))

    assert all(
        error and "not allowed" in error
        for _, _, _, error in rejected_results
    ), rejected_results
    assert all(
        actual == expected and env == {}
        for _, actual, env, expected in accepted_results
    ), accepted_results


def test_wp_o1r_lexical_helper_remains_private_and_subordinate() -> None:
    onboarding = REPO_ROOT / "dharma_swarm/operator_core/onboarding"
    helper = onboarding / "_command_lexical.py"
    contract = onboarding / "contract.py"
    runner = REPO_ROOT / "scripts/governance/run_agent_work_packet.py"

    assert sorted(onboarding.glob("*lexical*.py")) == [helper]
    helper_source = helper.read_text(encoding="utf-8")
    helper_tree = ast.parse(helper_source)
    allowed_imports = {"__future__", "pathlib", "re", "shlex", "typing", "unicodedata"}
    imported: set[str] = set()
    for node in helper_tree.body:
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            imported.add((node.module or "").split(".", 1)[0])
    assert imported <= allowed_imports
    assert not any(isinstance(node, (ast.ClassDef, ast.Raise)) for node in ast.walk(helper_tree))
    assert not any(isinstance(node, (ast.Assign, ast.AnnAssign)) for node in helper_tree.body)
    assert not {
        "AgentOpsError", "GateSpec", "SessionEntry", "WorkPacket", "parse_gate", "subprocess",
    } & {node.id for node in ast.walk(helper_tree) if isinstance(node, ast.Name)}
    functions = [node for node in helper_tree.body if isinstance(node, ast.FunctionDef)]
    assert functions and all(node.returns is not None for node in functions)

    init_source = (onboarding / "__init__.py").read_text(encoding="utf-8")
    assert "_command_lexical" not in init_source
    production_consumers = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in REPO_ROOT.rglob("*.py")
        if path not in {helper, contract}
        and "tests" not in path.relative_to(REPO_ROOT).parts
        and b"_command_lexical" in path.read_bytes()
    )
    assert production_consumers == []
    contract_source = contract.read_text(encoding="utf-8")
    contract_tree = ast.parse(contract_source)
    contract_symbols = {
        node.name for node in contract_tree.body if isinstance(node, ast.FunctionDef)
    }
    assert {
        "_parse_command", "_validate_git_gate", "build_gate_environment", "parse_gate",
    } <= contract_symbols
    grammar_constants = {
        "_GIT_EXECUTABLE", "_ALLOWED_GIT_STATUS_FORMATS", "_GIT_STATUS_BRANCH",
        "_GIT_DIFF_CHECK", "_GIT_SEPARATOR", "_ALLOWED_GIT_REV_PARSE_ARGS",
        "_GIT_MERGE_BASE_ANCESTOR", "_GIT_LS_FILES_PREFIX",
    }
    assigned = {
        target.id
        for node in contract_tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name)
    }
    assert grammar_constants <= assigned
    assert "AgentOpsError" in contract_source
    assert "_command_lexical" in contract_source
    runner_source = runner.read_text(encoding="utf-8")
    assert "build_gate_environment" in runner_source
    assert "_command_lexical" not in runner_source
    assert "git_executable_identity" not in runner_source
    assert len(contract_source.splitlines()) <= 500
    assert len(helper_source.splitlines()) <= 500


def test_direct_git_gate_strips_inherited_git_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    captured: list[dict[str, object]] = []

    def capture_run(
        argv: list[str], *, cwd: Path, env: dict[str, str] | None = None,
        timeout_seconds: int | None = None, preexec_fn: object = None,
    ) -> subprocess.CompletedProcess[str]:
        captured.append({"argv": list(argv), "cwd": cwd, "env": dict(env or {})})
        return subprocess.CompletedProcess(argv, 0, "ok\n", "")

    monkeypatch.setattr(agentops, "run_command", capture_run)
    poisoned = {
        "gIt_DiR": "/poison/repository",
        "Git_Work_Tree": "/poison/worktree",
        "GIT_INDEX_FILE": "/poison/index",
        "git_object_directory": "/poison/objects",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": "/poison/alternate",
        "GIT_CONFIG_GLOBAL": "/poison/global-config",
        "git_config_system": "/poison/system-config",
        "GIT_CONFIG_COUNT": "1",
        "Git_Config_Key_0": "core.fsmonitor",
        "GIT_CONFIG_VALUE_0": "/poison/helper",
        "GIT_EXTERNAL_DIFF": "/poison/diff-helper",
        "Git_SSH_Command": "/poison/ssh-helper",
        "GIT_TRACE": "/poison/trace",
        "git_trace2_event": "/poison/trace2",
        "GIT_REDIRECT_STDERR": "/poison/redirect",
        "Git_Optional_Locks": "1",
        "HOME": "/trusted/home",
        "XDG_CONFIG_HOME": "/trusted/xdg",
        "PATH": "/trusted/bin",
        "KEEP_ME": "yes",
        "GITHUB_ACTIONS": "true",
    }
    original = dict(poisoned)
    safe_git = {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
    }
    commands = (
        "git status --short",
        "git.exe status --short",
        "/usr/bin/git status --short",
        '"C:\\Program Files\\Git\\cmd\\git.exe" status --short',
    )
    for index, command in enumerate(commands):
        gate = agentops.parse_gate({"name": f"git-env-{index}", "command": command}, index)
        agentops.run_gate(repo, gate, base_env=poisoned)
        child = captured.pop()
        assert child["argv"] == gate.argv
        assert child["cwd"] == repo
        child_env = child["env"]
        assert isinstance(child_env, dict)
        assert {
            key: value for key, value in child_env.items()
            if key.casefold().startswith("git_")
        } == safe_git
        for key in ("HOME", "XDG_CONFIG_HOME", "PATH", "KEEP_ME", "GITHUB_ACTIONS"):
            assert child_env[key] == poisoned[key]
        assert poisoned == original

    non_git = agentops.parse_gate(
        {
            "name": "non-git-env",
            "command": "python3 -c pass",
            "env": {"CUSTOM": "packet", "GIT_TRACE": "packet-trace"},
        },
        0,
    )
    non_git_base = {"HOME": "/home", "Git_Dir": "inherited", "CUSTOM": "base"}
    agentops.run_gate(repo, non_git, base_env=non_git_base)
    expected_non_git = dict(non_git_base)
    expected_non_git.update(non_git.env)
    assert captured.pop()["env"] == expected_non_git

    disguised_git = (
        "/tmp/git.fake status --short",
        "git.fake status --short",
        "GIT.FAKE status --short",
        '"C:\\tmp\\git.fake" status --short',
        "git.fake. status --short",
        "git.fake::$DATA status --short",
        "git. status --short",
        "git.exe. status --short",
        '"git.exe " status --short',
        "git.exe::$DATA status --short",
        "git.exe.::$DATA status --short",
        "git.exe:payload status --short",
        '"git " status --short',
        "git:payload status --short",
        "git::$DATA status --short",
        '"./git " status --short',
        '"./git:payload" status --short',
        '"C:\\tmp\\git " status --short',
        '"C:\\tmp\\git::$DATA" status --short',
        "/tmp/C:git.exe status --short",
        "./C:git status --short",
        "/tmp/C:git::$DATA status --short",
        '"./C:git " status --short',
        "/tmp/C:git.exe. status --short",
        "/tmp/C:git-push status --short",
        '"C:\\Program Files\\Git\\cmd\\git.exe." status --short',
        '"C:\\Program Files\\Git\\cmd\\git.exe " status --short',
        '"C:\\Program Files\\Git\\cmd\\git.exe.::$DATA" status --short',
        '"C:\\Program Files\\Git\\cmd\\git.exe:payload" status --short',
    )
    for command in disguised_git:
        with pytest.raises(agentops.AgentOpsError, match="not allowed"):
            agentops.parse_gate(
                {"name": "disguised-git", "command": command}, 0,
            )

    for command in (
        "evil.git status --short", "tool.GIT status --short",
        "git.foo/tool status --short", "./git.foo/tool status --short",
    ):
        dotted_non_git = agentops.parse_gate(
            {"name": "dotted-non-git", "command": command}, 0,
        )
        agentops.run_gate(repo, dotted_non_git, base_env=poisoned)
        assert captured.pop()["env"] == poisoned
    assert poisoned == original

    source = tmp_path / "source"
    source.mkdir()
    (source / ".git").mkdir()
    (source / "README.md").write_text("fixture\n", encoding="utf-8")
    external_tmp = tmp_path / "external-tmp"
    external_tmp.mkdir()
    monkeypatch.setenv("TMPDIR", str(external_tmp))
    monkeypatch.setattr(
        agentops, "_negative_confinement",
        lambda _jail, _fixture: (None, ["/usr/bin/env", "-i", "--"], False, True),
    )
    monkeypatch.setattr(
        agentops, "_negative_environment",
        lambda *_args, **_kwargs: dict(poisoned),
    )
    negative_gate = agentops.parse_gate(
        {"name": "negative-git-env", "command": "git status --short"}, 0,
    )
    agentops.run_negative_control(source, negative_gate)
    negative_child = captured.pop()
    negative_argv = negative_child["argv"]
    assert isinstance(negative_argv, list)
    shell_index = negative_argv.index("/bin/sh")
    encoded = [token for token in negative_argv[:shell_index] if "=" in token]
    encoded_git = {
        token.split("=", 1)[0]: token.split("=", 1)[1]
        for token in encoded
        if token.split("=", 1)[0].casefold().startswith("git_")
    }
    assert encoded_git == safe_git
    assert poisoned == original

    remapped = {"PYTHONPATH": "/fixture", "KEEP_ME": "yes"}
    monkeypatch.setattr(
        agentops, "_negative_environment",
        lambda *_args, **_kwargs: dict(remapped),
    )
    non_git_negative = agentops.parse_gate(
        {
            "name": "negative-non-git-env",
            "command": "python3 -c pass",
            "env": {"PYTHONPATH": "/source/must-not-return"},
        },
        0,
    )
    agentops.run_negative_control(source, non_git_negative)
    non_git_argv = captured.pop()["argv"]
    assert isinstance(non_git_argv, list)
    shell_index = non_git_argv.index("/bin/sh")
    encoded_non_git = {
        token.split("=", 1)[0]: token.split("=", 1)[1]
        for token in non_git_argv[:shell_index]
        if "=" in token
    }
    assert encoded_non_git["PYTHONPATH"] == "/fixture"
    assert encoded_non_git["KEEP_ME"] == "yes"


def test_session_entry_rejects_each_missing_required_field(tmp_path: Path) -> None:
    repo = init_session_repo(tmp_path)
    valid = seal_packet(session_packet(repo))
    parsed = agentops.parse_work_packet(valid)
    assert parsed.gates[0].expected_exit == 0
    assert parsed.negative_controls[0].expected_exit == 0

    fields = "schema tool_versions authority_precedence work_packet active_track owner collision interface_mismatches closest_existing_implementation honest_blockers rollback packet_digest".split()
    fields += [f"collision.{name}" for name in ("status", "checked_at_sha", "details")]
    for field_path in fields:
        broken = copy.deepcopy(valid)
        entry = broken["session_entry"]
        assert isinstance(entry, dict)
        parts = field_path.split(".")
        target = entry if len(parts) == 1 else entry[parts[0]]
        assert isinstance(target, dict)
        target.pop(parts[-1])
        if field_path != "packet_digest":
            reseal_packet(broken)
        with pytest.raises(agentops.AgentOpsError, match=parts[-1]):
            agentops.parse_work_packet(broken)

    no_controls = copy.deepcopy(valid)
    no_controls.pop("negative_controls")
    reseal_packet(no_controls)
    with pytest.raises(agentops.AgentOpsError, match="negative_controls"):
        agentops.parse_work_packet(no_controls)

    missing_expected = copy.deepcopy(valid)
    controls = missing_expected["negative_controls"]
    assert isinstance(controls, list) and isinstance(controls[0], dict)
    controls[0].pop("expected_exit")
    reseal_packet(missing_expected)
    with pytest.raises(agentops.AgentOpsError, match="expected_exit"):
        agentops.parse_work_packet(missing_expected)

    legacy_gate = copy.deepcopy(valid)
    gates = legacy_gate["gates"]
    assert isinstance(gates, list) and isinstance(gates[0], dict)
    gates[0].pop("expected_exit")
    reseal_packet(legacy_gate)
    assert agentops.parse_work_packet(legacy_gate).gates[0].expected_exit == 0


def test_session_entry_tool_versions_are_probed_exactly(tmp_path: Path) -> None:
    repo = init_session_repo(tmp_path)
    payload = session_packet(repo)
    entry = payload["session_entry"]
    assert isinstance(entry, dict)
    tools = entry["tool_versions"]
    assert isinstance(tools, dict)
    tools["python"] = "999.999.999"
    external = write_external_packet(tmp_path, seal_packet(payload))

    with pytest.raises(agentops.AgentOpsError, match="tool version mismatch.*python"):
        agentops.execute_packet(external, source_root=repo, dry_run=True)

    payload = session_packet(repo)
    entry = payload["session_entry"]
    assert isinstance(entry, dict)
    entry["tool_versions"] = {"unknown-tool": "1.0"}
    external = write_external_packet(tmp_path, seal_packet(payload))
    with pytest.raises(agentops.AgentOpsError, match="unsupported tool"):
        agentops.execute_packet(external, source_root=repo, dry_run=True)


def test_session_entry_truth_fields_are_cross_bound(tmp_path: Path) -> None:
    repo = init_session_repo(tmp_path)

    wrong_packet = session_packet(repo)
    entry = wrong_packet["session_entry"]
    assert isinstance(entry, dict)
    entry["work_packet"] = "WP-O99"
    with pytest.raises(agentops.AgentOpsError, match="work_packet.*packet id"):
        agentops.parse_work_packet(seal_packet(wrong_packet))

    placeholder = session_packet(repo)
    entry = placeholder["session_entry"]
    assert isinstance(entry, dict)
    entry["rollback"] = "revert <candidate commit>"
    with pytest.raises(agentops.AgentOpsError, match="angle-bracket placeholder"):
        agentops.parse_work_packet(seal_packet(placeholder))

    empty_gates = session_packet(repo, gates=[])
    with pytest.raises(agentops.AgentOpsError, match="at least one gate"):
        agentops.parse_work_packet(seal_packet(empty_gates))


def test_session_entry_accepts_exact_wp_o1r_identity_only(tmp_path: Path) -> None:
    repo = init_session_repo(tmp_path)

    def packet_for(work_packet: str, *, packet_id: str | None = None) -> dict[str, object]:
        payload = session_packet(repo)
        identity = packet_id or f"onboard-one-door-{work_packet}"
        payload["id"] = identity
        payload["allowed_files"] = [
            "allowed.txt",
            f"reports/agentops/work_packets/{identity}.json",
        ]
        entry = payload["session_entry"]
        assert isinstance(entry, dict)
        entry["work_packet"] = work_packet
        return seal_packet(payload)

    for work_packet in ("WP-O1", "WP-O10", "WP-O1R"):
        parsed = agentops.parse_work_packet(packet_for(work_packet))
        assert parsed.session_entry is not None
        assert parsed.session_entry.work_packet == work_packet

    for rejected in ("WP-O2R", "WP-O1RR", "WP-O1R2", "WP-O1r"):
        with pytest.raises(agentops.AgentOpsError, match="work_packet.*packet id"):
            agentops.parse_work_packet(packet_for(rejected))

    with pytest.raises(agentops.AgentOpsError, match="work_packet.*packet id"):
        agentops.parse_work_packet(
            packet_for("WP-O1R", packet_id="onboard-one-door-WP-O1")
        )


def test_inspect_accepts_successor_packet_but_execution_requires_tracked_custody(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = init_session_repo(tmp_path)

    stale_payload = seal_packet(session_packet(repo))
    stale_external = write_external_packet(tmp_path / "stale", stale_payload)
    tracked = tracked_packet_path(repo, stale_payload)
    tracked.parent.mkdir(parents=True)
    tracked.write_bytes(stale_external.read_bytes())
    stage_path(repo, tracked)
    committed = run(
        ["git", "commit", "-m", "fixture: stale tracked session packet"],
        cwd=repo,
    )
    assert committed.returncode == 0, committed.stderr

    payload = seal_packet(session_packet(repo))
    external = write_external_packet(tmp_path / "fresh", payload)
    report_root = tmp_path / "external-reports"
    entry = payload["session_entry"]
    assert isinstance(entry, dict)
    assert tracked_packet_path(repo, payload) == tracked
    assert tracked.read_bytes() != external.read_bytes()

    executed: list[str] = []

    def pass_without_io(
        _repo: Path,
        gate: agentops.GateSpec,
        **_kwargs: object,
    ) -> dict[str, object]:
        executed.append(gate.name)
        return {
            "name": gate.name,
            "command": gate.command,
            "expected_exit": gate.expected_exit,
            "exit_code": gate.expected_exit,
            "passed": True,
            "timed_out": False,
            "output": "",
            "duration_seconds": 0.0,
        }

    monkeypatch.setattr(agentops, "run_gate", pass_without_io)
    monkeypatch.setattr(agentops, "run_negative_control", pass_without_io)

    exit_code, report = agentops.execute_packet(
        external,
        source_root=repo,
        dry_run=True,
    )
    assert exit_code == 0 and report is None
    summary = json.loads(capsys.readouterr().out)
    assert summary["packet_digest"] == entry["packet_digest"]
    assert summary["tracked_copy_state"] == "present_nonidentical"
    assert summary["gates"] == [
        {
            "name": "declared-gate",
            "command": "git status --porcelain",
            "expected_exit": 0,
        }
    ]
    assert summary["negative_controls"] == [
        {
            "name": "declared-negative",
            "command": payload["negative_controls"][0]["command"],
            "expected_exit": 0,
        }
    ]
    assert executed == []

    with pytest.raises(agentops.AgentOpsError, match="byte-identical|tracked copy"):
        agentops.execute_packet(
            external,
            source_root=repo,
            allow_existing_changes=True,
            report_root=report_root,
        )
    assert executed == []

    tracked.write_bytes(external.read_bytes())
    with pytest.raises(agentops.AgentOpsError, match="index|stage|unstaged|custody"):
        agentops.execute_packet(
            external,
            source_root=repo,
            allow_existing_changes=True,
            report_root=report_root,
        )
    assert executed == []

    stage_path(repo, tracked)
    exit_code, report = agentops.execute_packet(
        external,
        source_root=repo,
        allow_existing_changes=True,
        report_root=report_root,
    )
    assert exit_code == 0 and report is not None
    assert report["status"] == "passed"
    assert executed == ["declared-gate", "declared-negative"]


def test_session_entry_requires_canonical_tracked_path_in_allowed_files(
    tmp_path: Path,
) -> None:
    repo = init_session_repo(tmp_path)
    payload = session_packet(repo)
    payload["allowed_files"] = ["allowed.txt"]
    external = write_external_packet(tmp_path, seal_packet(payload))

    with pytest.raises(agentops.AgentOpsError, match="allowed_files"):
        agentops.execute_packet(external, source_root=repo, dry_run=True)


def test_session_entry_rejects_symlinked_tracked_custody(tmp_path: Path) -> None:
    repo = init_session_repo(tmp_path)
    payload = seal_packet(session_packet(repo))
    external = write_external_packet(tmp_path, payload)
    tracked = tracked_packet_path(repo, payload)
    tracked.parent.mkdir(parents=True)
    tracked.symlink_to(external)
    stage_path(repo, tracked)

    packet = agentops.load_work_packet(external)
    with pytest.raises(agentops.AgentOpsError, match="regular|symlink"):
        agentops._validate_session_envelope(
            repo,
            external,
            packet,
            inspect=False,
            require_tracked_copy=True,
        )


@pytest.mark.parametrize("hidden_flag", ["--assume-unchanged", "--skip-worktree"])
def test_session_entry_rejects_hidden_index_custody_flags(
    tmp_path: Path,
    hidden_flag: str,
) -> None:
    repo = init_session_repo(tmp_path)
    payload = seal_packet(session_packet(repo))
    external = write_external_packet(tmp_path, payload)
    tracked = tracked_packet_path(repo, payload)
    tracked.parent.mkdir(parents=True)
    tracked.write_text("{}\n", encoding="utf-8")
    stage_path(repo, tracked)
    relative = tracked.relative_to(repo).as_posix()
    flagged = run(["git", "update-index", hidden_flag, "--", relative], cwd=repo)
    assert flagged.returncode == 0, flagged.stderr
    tracked.write_bytes(external.read_bytes())

    packet = agentops.load_work_packet(external)
    with pytest.raises(agentops.AgentOpsError, match="index|flag|custody"):
        agentops._validate_session_envelope(
            repo,
            external,
            packet,
            inspect=False,
            require_tracked_copy=True,
        )


def test_session_entry_custody_ignores_inherited_git_index_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_session_repo(tmp_path)
    payload = seal_packet(session_packet(repo))
    external = write_external_packet(tmp_path, payload)
    tracked = tracked_packet_path(repo, payload)
    tracked.parent.mkdir(parents=True)
    tracked.write_text("{}\n", encoding="utf-8")
    stage_path(repo, tracked)

    actual_index = repo / ".git/index"
    alternate_index = tmp_path / "alternate-index"
    alternate_index.write_bytes(actual_index.read_bytes())
    monkeypatch.setenv("GIT_INDEX_FILE", str(alternate_index))
    tracked.write_bytes(external.read_bytes())
    stage_path(repo, tracked)

    packet = agentops.load_work_packet(external)
    with pytest.raises(agentops.AgentOpsError, match="index|custody"):
        agentops._validate_session_envelope(
            repo,
            external,
            packet,
            inspect=False,
            require_tracked_copy=True,
        )


def test_all_internal_git_subprocesses_use_trusted_environment() -> None:
    tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
    probe = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_probe_tool_version"
    )
    probe_calls = {
        node.func.id
        for node in ast.walk(probe)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "run_git" in probe_calls

    violations: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        argv = node.args[0]
        if not isinstance(argv, (ast.List, ast.Tuple)) or not argv.elts:
            continue
        head = argv.elts[0]
        if not isinstance(head, ast.Constant) or head.value != "git":
            continue
        env = next((item.value for item in node.keywords if item.arg == "env"), None)
        trusted = (
            isinstance(env, ast.Call)
            and isinstance(env.func, ast.Name)
            and env.func.id == "trusted_git_environment"
        )
        if not trusted:
            violations.append(node.lineno)

    assert violations == []


def test_session_envelope_rejects_custody_free_execution_mode(tmp_path: Path) -> None:
    repo = init_session_repo(tmp_path)
    payload = seal_packet(session_packet(repo))
    external = write_external_packet(tmp_path, payload)
    packet = agentops.load_work_packet(external)

    with pytest.raises(agentops.AgentOpsError, match="envelope mode|custody"):
        agentops._validate_session_envelope(
            repo,
            external,
            packet,
            inspect=False,
            require_tracked_copy=False,
        )


def test_execution_rechecks_external_packet_custody_after_gates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_session_repo(tmp_path)
    payload = seal_packet(session_packet(repo))
    external = write_external_packet(tmp_path, payload)
    tracked = tracked_packet_path(repo, payload)
    tracked.parent.mkdir(parents=True)
    tracked.write_bytes(external.read_bytes())
    stage_path(repo, tracked)

    def mutate_external(
        _repo: Path,
        gate: agentops.GateSpec,
        **_kwargs: object,
    ) -> dict[str, object]:
        external.write_bytes(external.read_bytes() + b" ")
        return {
            "name": gate.name,
            "command": gate.command,
            "expected_exit": gate.expected_exit,
            "exit_code": gate.expected_exit,
            "passed": True,
            "timed_out": False,
            "output": "",
            "duration_seconds": 0.0,
        }

    monkeypatch.setattr(agentops, "run_gate", mutate_external)
    monkeypatch.setattr(agentops, "run_negative_control", mutate_external)

    with pytest.raises(agentops.AgentOpsError, match="changed|custody|byte-identical"):
        agentops.execute_packet(
            external,
            source_root=repo,
            allow_existing_changes=True,
            report_root=tmp_path / "external-reports",
        )


def test_external_entry_packet_bootstrap_and_digest_binding(tmp_path: Path) -> None:
    repo = init_session_repo(tmp_path)
    payload = seal_packet(session_packet(repo))
    digest = agentops.packet_digest(payload)
    self_reference_probe = copy.deepcopy(payload)
    entry = self_reference_probe["session_entry"]
    assert isinstance(entry, dict)
    entry["packet_digest"] = "f" * 64
    assert agentops.packet_digest(self_reference_probe) == digest

    external = write_external_packet(tmp_path, payload)
    report_root = tmp_path / "external-reports"
    def execute(**kwargs: object):
        return agentops.execute_packet(
            external, source_root=repo, report_root=report_root, **kwargs
        )

    canonical = copy.deepcopy(payload)
    canonical_entry = canonical["session_entry"]
    assert isinstance(canonical_entry, dict)
    canonical_entry.pop("packet_digest")
    assert digest == stable_digest(canonical)
    exit_code, report = execute(dry_run=True)
    assert exit_code == 0 and report is None

    tracked = tracked_packet_path(repo, payload)
    tracked.parent.mkdir(parents=True)
    tracked.write_bytes(external.read_bytes())
    with pytest.raises(agentops.AgentOpsError, match="Git index"):
        execute(allow_existing_changes=True)
    stage_path(repo, tracked)
    exit_code, report = execute(allow_existing_changes=True)
    assert exit_code == 0 and report is not None

    tracked.write_bytes(external.read_bytes() + b" ")
    with pytest.raises(agentops.AgentOpsError, match="byte-identical|tracked copy"):
        execute(allow_existing_changes=True)
    tracked.write_bytes(external.read_bytes())

    tampered = copy.deepcopy(payload)
    tampered["intent"] = "changed without resealing"
    external.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(agentops.AgentOpsError, match="digest"):
        execute(dry_run=True)

    external.write_bytes(tracked.read_bytes())
    tracked.unlink()
    (repo / "new-head.txt").write_text("new head\n", encoding="utf-8")
    assert run(["git", "add", "new-head.txt"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "advance head"], cwd=repo).returncode == 0
    with pytest.raises(agentops.AgentOpsError, match="exact|HEAD|base_ref"):
        execute(dry_run=True)


def test_external_packet_rejects_lexical_resolved_and_git_admin_paths(
    tmp_path: Path,
) -> None:
    repo = init_session_repo(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    lexical_link = repo / "packet-link.json"
    lexical_link.symlink_to(outside)
    with pytest.raises(agentops.AgentOpsError, match="external.*Git state|source"):
        agentops._validate_external_packet_path(repo, lexical_link)

    inside = repo / "inside.json"
    inside.write_text("{}", encoding="utf-8")
    resolved_link = tmp_path / "resolved-link.json"
    resolved_link.symlink_to(inside)
    with pytest.raises(agentops.AgentOpsError, match="external.*Git state|source"):
        agentops._validate_external_packet_path(repo, resolved_link)

    git_admin = next(iter(agentops._git_admin_roots(repo)))
    with pytest.raises(agentops.AgentOpsError, match="external.*Git state|source"):
        agentops._validate_external_packet_path(repo, git_admin / "packet.json")


def test_declared_expected_exits_and_isolated_negative_controls(tmp_path: Path) -> None:
    repo = init_session_repo(tmp_path)
    seven_command = stub_gate_script(repo, "raise SystemExit(7)\n")
    payload = session_packet(
        repo,
        gates=[
            {
                "name": "expected-seven",
                "command": seven_command,
                "expected_exit": 7,
            }
        ],
        negative_controls=[
            {
                "name": "isolated-write-and-three",
                "command": (
                    f'{sys.executable} -c "import subprocess; from pathlib import Path; '
                    "subprocess.run(['git', 'show', 'HEAD:README.md'], check=True, capture_output=True); "
                    "Path('negative-control.txt').write_text('fixture only'); "
                    'raise SystemExit(3)"'
                ),
                "expected_exit": 3,
            }
        ],
    )
    payload = seal_packet(payload)
    external = write_external_packet(tmp_path, payload)
    tracked = tracked_packet_path(repo, payload)
    tracked.parent.mkdir(parents=True)
    tracked.write_bytes(external.read_bytes())
    stage_path(repo, tracked)

    exit_code, report = agentops.execute_packet(
        external,
        source_root=repo,
        allow_existing_changes=True,
        report_root=tmp_path / "external-reports",
    )
    assert exit_code == 0 and report is not None
    assert report["gates"][0]["expected_exit"] == 7
    assert report["gates"][0]["exit_code"] == 7
    assert report["gates"][0]["passed"] is True
    assert report["negative_controls"][0]["expected_exit"] == 3
    assert report["negative_controls"][0]["exit_code"] == 3
    assert report["negative_controls"][0]["passed"] is True
    assert not (repo / "negative-control.txt").exists()


def test_negative_controls_confine_absolute_env_and_pythonpath_source_escapes(
    tmp_path: Path,
) -> None:
    repo = init_session_repo(tmp_path)
    probe = repo / "confinement_probe.py"
    probe.write_text(
        """from pathlib import Path
import os
import sys

mode = sys.argv[1]
if mode == "absolute":
    target = Path(sys.argv[2])
    try:
        target.write_bytes(target.read_bytes())
    except OSError:
        raise SystemExit(0)
    raise SystemExit(9)
if mode == "pythonpath":
    assert Path(os.environ["PYTHONPATH"]).resolve() == Path.cwd().resolve()
    raise SystemExit(0)
raise SystemExit(8)
""",
        encoding="utf-8",
    )
    assert run(["git", "add", "confinement_probe.py"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add confinement probe"], cwd=repo).returncode == 0
    victim = (repo / "README.md").resolve()
    before = victim.read_bytes()
    controls = [
        {
            "name": "absolute-source-write-denied",
            "command": f"{sys.executable} confinement_probe.py absolute {victim}",
            "expected_exit": 0,
        },
        {
            "name": "source-pythonpath-remapped",
            "command": f"{sys.executable} confinement_probe.py pythonpath",
            "expected_exit": 0,
            "env": {"PYTHONPATH": str(repo)},
        },
    ]
    payload = seal_packet(session_packet(repo, negative_controls=controls))
    external = write_external_packet(tmp_path, payload)
    tracked = tracked_packet_path(repo, payload)
    tracked.parent.mkdir(parents=True)
    tracked.write_bytes(external.read_bytes())
    stage_path(repo, tracked)

    exit_code, report = agentops.execute_packet(
        external,
        source_root=repo,
        allow_existing_changes=True,
        report_root=tmp_path / "external-reports",
    )
    assert exit_code == 0 and report is not None
    assert all(row["passed"] for row in report["negative_controls"])
    assert victim.read_bytes() == before

    escaped_env = session_packet(
        repo,
        negative_controls=[
            {
                "name": "env-source-route",
                "command": f"{sys.executable} -c \"raise SystemExit(0)\"",
                "expected_exit": 0,
                "env": {"ESCAPE_TARGET": str(victim)},
            }
        ],
    )
    escaped_env = seal_packet(escaped_env)
    external = write_external_packet(tmp_path / "env", escaped_env)
    tracked.write_bytes(external.read_bytes())
    stage_path(repo, tracked)
    with pytest.raises(agentops.AgentOpsError, match="env.*points into source"):
        agentops.execute_packet(
            external,
            source_root=repo,
            allow_existing_changes=True,
            report_root=tmp_path / "env-reports",
        )
    assert victim.read_bytes() == before


def test_negative_control_rejects_fixture_symlink_back_to_source(tmp_path: Path) -> None:
    repo = init_session_repo(tmp_path)
    victim = (repo / "README.md").resolve()
    (repo / "source-link").symlink_to(victim)
    assert run(["git", "add", "source-link"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add source escape link"], cwd=repo).returncode == 0
    payload = seal_packet(session_packet(repo))
    external = write_external_packet(tmp_path, payload)
    tracked = tracked_packet_path(repo, payload)
    tracked.parent.mkdir(parents=True)
    tracked.write_bytes(external.read_bytes())
    stage_path(repo, tracked)

    with pytest.raises(agentops.AgentOpsError, match="symlink escapes isolation"):
        agentops.execute_packet(
            external,
            source_root=repo,
            allow_existing_changes=True,
            report_root=tmp_path / "external-reports",
        )


def test_negative_control_temp_root_must_be_external(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = init_session_repo(tmp_path)
    gate = agentops.parse_gate(
        {
            "name": "unsafe-temp-root",
            "command": f'{sys.executable} -c "raise SystemExit(0)"',
            "expected_exit": 0,
        },
        0,
        require_expected_exit=True,
    )
    before = tree_snapshot(repo)
    monkeypatch.setenv("TMPDIR", str(repo))

    with pytest.raises(agentops.AgentOpsError, match="temp root.*repository|temp root"):
        agentops.run_negative_control(repo, gate)
    assert tree_snapshot(repo) == before


def test_nonroot_linux_uses_passwordless_sudo_chroot_with_uid_drop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jail = tmp_path / "jail"
    fixture = jail / "fixture"
    fixture.mkdir(parents=True)
    paths = {
        "unshare": "/usr/bin/unshare",
        "chroot": "/usr/sbin/chroot",
        "sudo": "/usr/bin/sudo",
        "env": "/usr/bin/env",
    }
    probes: list[list[str]] = []
    which_calls: list[tuple[str, str | None]] = []

    monkeypatch.setattr(agentops.sys, "platform", "linux")
    monkeypatch.setattr(agentops.os, "geteuid", lambda: 1001)
    monkeypatch.setattr(agentops.os, "getuid", lambda: 1001)
    monkeypatch.setattr(agentops.os, "getgid", lambda: 1002)
    def trusted_which(name: str, *, path: str | None = None) -> str | None:
        which_calls.append((name, path))
        if path != agentops._TRUSTED_HOST_PATH:
            return f"/tmp/attacker/{name}"
        return paths.get(name)

    monkeypatch.setattr(agentops.shutil, "which", trusted_which)

    def probe(
        argv: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        probes.append(argv)
        return subprocess.CompletedProcess(
            argv, 0 if argv[0] == paths["sudo"] else 1, "", ""
        )

    monkeypatch.setattr(agentops, "run_command", probe)
    preexec_fn, prefix, jailed, env_via_argv = agentops._negative_confinement(
        jail, fixture
    )

    assert preexec_fn is None
    assert jailed is True
    assert env_via_argv is True
    assert probes == [
        [paths["unshare"], "--user", "--map-root-user", "true"],
        [paths["sudo"], "-n", "--", paths["chroot"], "--version"],
    ]
    assert which_calls == [
        ("unshare", agentops._TRUSTED_HOST_PATH),
        ("chroot", agentops._TRUSTED_HOST_PATH),
        ("sudo", agentops._TRUSTED_HOST_PATH),
        ("env", agentops._TRUSTED_HOST_PATH),
    ]
    assert prefix == [
        paths["sudo"],
        "-n",
        "--",
        paths["chroot"],
        "--userspec=1001:1002",
        "--groups=1002",
        str(jail),
        paths["env"],
        "-i",
        "--",
    ]
    assert "-E" not in prefix

    monkeypatch.setattr(
        agentops,
        "run_command",
        lambda argv, **_kwargs: subprocess.CompletedProcess(argv, 1, "", "denied"),
    )
    with pytest.raises(agentops.AgentOpsError, match="confinement is unavailable"):
        agentops._negative_confinement(jail, fixture)


def test_external_report_root_is_mandatory_and_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = init_session_repo(tmp_path)
    (repo / ".gitignore").write_text("ignored-state.txt\n", encoding="utf-8")
    assert run(["git", "add", ".gitignore"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "ignore fixture state"], cwd=repo).returncode == 0
    (repo / "ignored-state.txt").write_text("must remain byte-identical\n", encoding="utf-8")

    payload = seal_packet(session_packet(repo))
    external = write_external_packet(tmp_path, payload)
    tracked = tracked_packet_path(repo, payload)
    tracked.parent.mkdir(parents=True)
    tracked.write_bytes(external.read_bytes())
    stage_path(repo, tracked)
    before = tree_snapshot(repo)

    with pytest.raises(agentops.AgentOpsError, match="report.*root|report_root"):
        agentops.execute_packet(
            external, source_root=repo, allow_existing_changes=True
        )
    assert tree_snapshot(repo) == before

    install_source_write_guard(monkeypatch, repo)
    report_root = tmp_path / "external-reports"
    exit_code, report = agentops.execute_packet(
        external,
        source_root=repo,
        allow_existing_changes=True,
        report_root=report_root,
    )
    assert exit_code == 0 and report is not None
    assert list(report_root.rglob("report.json"))
    assert list(report_root.rglob("report.md"))
    assert tree_snapshot(repo) == before


def test_external_report_root_rejects_nested_symlink_into_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = init_session_repo(tmp_path)
    payload = seal_packet(session_packet(repo))
    external = write_external_packet(tmp_path, payload)
    tracked = tracked_packet_path(repo, payload)
    tracked.parent.mkdir(parents=True)
    tracked.write_bytes(external.read_bytes())
    stage_path(repo, tracked)
    before = tree_snapshot(repo)
    report_root = tmp_path / "nested-report-root"
    report_root.mkdir()
    (report_root / "reports").symlink_to(repo, target_is_directory=True)

    def must_not_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("report destination must be rejected before execution")

    monkeypatch.setattr(agentops, "run_gate", must_not_run)
    monkeypatch.setattr(agentops, "run_negative_control", must_not_run)

    with pytest.raises(agentops.AgentOpsError, match="report destination"):
        agentops.execute_packet(
            external,
            source_root=repo,
            allow_existing_changes=True,
            report_root=report_root,
        )
    assert tree_snapshot(repo) == before


def test_session_entry_collision_adversarial_matrix() -> None:
    # The collision helper takes the selected packet's allowed patterns, a
    # track-id -> owned-patterns map, and the actual tracked/diff path universe.
    cases = (
        ("exact", ["src/a.py"], {"sibling": ["src/a.py"]}, []),
        ("containment", ["src/**"], {"sibling": ["src/pkg/**"]}, []),
        ("containment", ["src/pkg/file.py"], {"sibling": ["src"]}, []),
        (
            "glob_intersection",
            ["docs/**/test_*.py"],
            {"sibling": ["docs/governance/**/*.py"]},
            [],
        ),
        (
            "actual_file_overlap",
            ["plugins/*/config.json"],
            {"sibling": ["plugins/prod/*.json"]},
            ["plugins/prod/config.json"],
        ),
    )
    for expected_kind, allowed, siblings, actual_paths in cases:
        collisions = agentops.detect_surface_collisions(
            allowed_patterns=allowed,
            sibling_patterns=siblings,
            actual_paths=actual_paths,
        )
        assert expected_kind in {item["kind"] for item in collisions}

    assert agentops.detect_surface_collisions(
        allowed_patterns=["docs/**"],
        sibling_patterns={"sibling": ["api/**"]},
        actual_paths=["docs/a.md", "api/main.py"],
    ) == []


def test_positive_gate_command_family_allowlist_rejects_transitive_routes() -> None:
    """O4-B11: positive gates pass one fail-closed command-family allowlist
    BEFORE subprocess execution. The five spec witnesses must be rejected;
    the enumerated pytest/ruff/read-only-script/make/direct-Git families pass.
    Negative controls are exempt (they exist to prove rejection, jailed)."""
    witnesses = [
        "python3 -c \"import subprocess; subprocess.run(['git','push','origin','HEAD'])\"",
        "python3 -c \"import os; os.system('git push origin HEAD')\"",
        "gh pr merge 1",
        "ssh host git-receive-pack repo",
        "curl -X POST https://api.github.invalid/merges",
    ]
    for index, command in enumerate(witnesses):
        try:
            gate = agentops.parse_gate({"name": f"witness-{index}", "command": command}, index)
        except agentops.AgentOpsError:
            continue  # rejected even earlier, by O1R lexical admission
        with pytest.raises(agentops.AgentOpsError):
            agentops.admit_gate_command(gate)

    rejected_families = [
        "python3 - <<'PY'\nprint('stdin')\nPY",
        "node -e \"require('child_process')\"",
        "wget https://example.invalid/x",
        "python3 scripts/runtime/pr_merge_control.py",
        "python3 scripts/governance/orientation_graph.py --write-context",
        "make evolve",
        "rsync -a . remote:copy",
    ]
    for index, command in enumerate(rejected_families):
        try:
            gate = agentops.parse_gate({"name": f"family-{index}", "command": command}, index)
        except agentops.AgentOpsError:
            continue
        with pytest.raises(agentops.AgentOpsError):
            agentops.admit_gate_command(gate)

    accepted = [
        "python3 -m pytest tests/test_agent_work_packet.py -q",
        "python3 -m ruff check dharma_swarm/operator_core/onboarding",
        "python3 scripts/governance/agent_onboard.py --json",
        "python3 scripts/docops/check_docops_integrity.py",
        "python3 scripts/governance/orientation_graph.py",
        "make onboard",
        "make agent-build-preflight PACKET=reports/agentops/work_packets/x.json",
        "git status --porcelain",
    ]
    for index, command in enumerate(accepted):
        gate = agentops.parse_gate({"name": f"accepted-{index}", "command": command}, index)
        agentops.admit_gate_command(gate)  # must not raise


def test_positive_gate_allowlist_rejects_packet_supplied_environment() -> None:
    """Packet-supplied env is empty by default and no family enumerates an
    allowed key — an env-carrying gate fails closed (O4-B11)."""
    gate = agentops.parse_gate(
        {"name": "env-carrier", "command": "python3 -m pytest -q",
         "env": {"PYTHONPATH": "/tmp/injected"}},
        0,
    )
    with pytest.raises(agentops.AgentOpsError):
        agentops.admit_gate_command(gate)


def test_positive_gate_allowlist_rejects_make_variable_injection() -> None:
    """Make expands `$(ARGS)`/`$(PACKET)` unquoted in a shell and runs
    `$(shell …)` during recipe expansion, so a variable value is executable
    surface. Values carrying shell/make metacharacters fail closed
    (Greptile + Codex P1 on #897); benign flag/path values still pass."""
    injections = [
        "make onboard 'ARGS=$(shell git push origin HEAD)'",
        "make onboard 'ARGS=--json;id'",
        "make onboard 'ARGS=--json && id'",
        "make onboard 'ARGS=`id`'",
        "make onboard 'ARGS=--json|tee /tmp/x'",
        "make agent-build-preflight 'PACKET=$(shell touch /tmp/x)'",
    ]
    for index, command in enumerate(injections):
        gate = agentops.parse_gate({"name": f"inject-{index}", "command": command}, index)
        with pytest.raises(agentops.AgentOpsError):
            agentops.admit_gate_command(gate)

    benign = [
        "make onboard ARGS=--json",
        "make onboard 'ARGS=--deep --net'",
        "make agent-build-preflight PACKET=reports/agentops/work_packets/x.json",
    ]
    for index, command in enumerate(benign):
        gate = agentops.parse_gate({"name": f"benign-{index}", "command": command}, index)
        agentops.admit_gate_command(gate)  # must not raise


def test_positive_gate_allowlist_rejects_path_qualified_shims() -> None:
    """The basename may look trusted, but subprocess.run executes the literal
    argv[0] — a path-qualified shim runs attacker code (Codex P1 on #897).
    Bare `python3`/`make`/`git` and the exact running interpreter still pass."""
    shims = [
        "./python3 -m pytest -q",
        "/tmp/make onboard",
        "/tmp/git status --porcelain",
        "../evil/python3 -m pytest",
    ]
    for index, command in enumerate(shims):
        try:
            gate = agentops.parse_gate({"name": f"shim-{index}", "command": command}, index)
        except agentops.AgentOpsError:
            continue  # rejected even earlier by O1R lexical admission
        with pytest.raises(agentops.AgentOpsError):
            agentops.admit_gate_command(gate)

    # The exact running interpreter (absolute path) is the trusted host python.
    trusted = agentops.parse_gate(
        {"name": "host-python", "command": f"{sys.executable} -m pytest -q"}, 0
    )
    agentops.admit_gate_command(trusted)  # must not raise


def test_positive_gate_allowlist_rejects_abbreviated_write_context() -> None:
    """argparse admits any unambiguous prefix, so `--write` resolves to
    `--write-context` — the exact-token check must reject every abbreviation
    (Codex P2 on #897)."""
    for abbrev in ("--write", "--w", "--writ", "--write-c"):
        command = f"python3 scripts/governance/orientation_graph.py {abbrev}"
        gate = agentops.parse_gate({"name": "abbrev", "command": command}, 0)
        with pytest.raises(agentops.AgentOpsError):
            agentops.admit_gate_command(gate)
    # A genuinely different flag that is not a prefix of the forbidden one passes.
    ok = agentops.parse_gate(
        {"name": "json", "command": "python3 scripts/governance/orientation_graph.py --json"}, 0
    )
    agentops.admit_gate_command(ok)  # must not raise
