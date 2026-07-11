from __future__ import annotations

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
            {"name": "declared-gate", "command": f'{sys.executable} -c "raise SystemExit(0)"',
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
    payload = session_packet(
        repo,
        gates=[
            {
                "name": "expected-seven",
                "command": f'{sys.executable} -c "raise SystemExit(7)"',
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
