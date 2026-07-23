from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
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
    rel = "scripts/governance/orientation_graph.py"
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
        "id": "session-entry-test-track",
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
    packet_id = "session-entry-test-WP-T1"
    payload: dict[str, object] = {
        "id": packet_id, "base_ref": head, "branch": branch, "worktree": ".",
        "intent": "Exercise the portable Session Entry contract.",
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
            "work_packet": "WP-T1",
            "active_track": "session-entry-test-track",
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


def add_sibling_track(repo: Path, *, surfaces: list[str]) -> None:
    track = repo / "docs/governance/ACTIVE_TRACK.yaml"
    document = json.loads(track.read_text(encoding="utf-8"))
    document["active_tracks"].append(
        {
            "id": "session-entry-sibling-track",
            "status": "ACTIVE",
            "owner": "@sibling-owner",
            "owned_surfaces": surfaces,
        }
    )
    track.write_text(json.dumps(document), encoding="utf-8")
    stage_path(repo, track)
    assert run(["git", "commit", "-m", "add sibling track"], cwd=repo).returncode == 0


def tree_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def tree_state_snapshot(root: Path) -> dict[str, tuple[int, int, str]]:
    """Capture files, directories, symlinks, modes, and regular-file bytes."""
    snapshot: dict[str, tuple[int, int, str]] = {}
    for path in [root, *root.rglob("*")]:
        metadata = path.lstat()
        relative = "." if path == root else path.relative_to(root).as_posix()
        kind = stat.S_IFMT(metadata.st_mode)
        if stat.S_ISREG(metadata.st_mode):
            payload = hashlib.sha256(path.read_bytes()).hexdigest()
        elif stat.S_ISLNK(metadata.st_mode):
            payload = os.readlink(path)
        else:
            payload = ""
        snapshot[relative] = (kind, stat.S_IMODE(metadata.st_mode), payload)
    return snapshot


def reseal_packet(payload: dict[str, object]) -> None:
    entry = payload["session_entry"]
    assert isinstance(entry, dict)
    entry["packet_digest"] = agentops.packet_digest(payload)


def install_source_write_guard(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    root = repo.resolve()

    def require_external(path: Path, *, dir_fd: int | None = None) -> None:
        candidate = Path(path)
        if not candidate.is_absolute():
            base = Path.cwd()
            if dir_fd is not None and Path(f"/proc/self/fd/{dir_fd}").exists():
                base = Path(os.readlink(f"/proc/self/fd/{dir_fd}"))
            candidate = base / candidate
        try:
            candidate.resolve(strict=False).relative_to(root)
        except ValueError:
            return
        raise AssertionError(f"AgentOps attempted a source/.git write: {candidate}")

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

    original_open = os.open

    def guarded_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        *args: int,
        dir_fd: int | None = None,
        **kwargs: int,
    ) -> int:
        write_flags = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
        if flags & write_flags and not isinstance(path, bytes):
            require_external(Path(path), dir_fd=dir_fd)
        return original_open(path, flags, *args, dir_fd=dir_fd, **kwargs)

    monkeypatch.setattr(os, "open", guarded_open)

    def guard_os_destination(name: str) -> None:
        original = getattr(os, name)

        def guarded(
            path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
            *args: object,
            _original=original,
            dir_fd: int | None = None,
            **kwargs: object,
        ):
            if not isinstance(path, bytes):
                require_external(Path(path), dir_fd=dir_fd)
            if dir_fd is not None:
                kwargs["dir_fd"] = dir_fd
            return _original(path, *args, **kwargs)

        monkeypatch.setattr(os, name, guarded)

    for name in ("mkdir", "unlink", "remove", "rmdir", "chmod", "truncate", "utime"):
        guard_os_destination(name)


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


def test_scope_hashes_raw_worktree_bytes_and_exec_mode(tmp_path: Path) -> None:
    """Status filters and core.fileMode cannot make raw worktree drift clean."""
    repo = init_repo(tmp_path)
    packet = agentops.parse_work_packet(
        minimal_packet(tmp_path, repo, allowed_files=["README.md"])
    )
    readme = repo / "README.md"
    assert run(["git", "config", "core.fileMode", "false"], cwd=repo).returncode == 0
    readme.chmod(0o755)

    mode_scope = agentops.inspect_scope(repo, packet)
    assert mode_scope.changed_files == ["README.md"]

    readme.chmod(0o644)
    assert run(["git", "config", "core.autocrlf", "true"], cwd=repo).returncode == 0
    readme.write_bytes(b"base\r\n")
    bytes_scope = agentops.inspect_scope(repo, packet)
    assert bytes_scope.changed_files == ["README.md"]


@pytest.mark.parametrize("outside", [False, True], ids=["in_repo", "out_of_repo"])
def test_scope_rejects_symlink_ancestor_even_with_identical_tracked_bytes(
    tmp_path: Path, outside: bool,
) -> None:
    repo = init_repo(tmp_path)
    governed = repo / "governed"
    governed.mkdir()
    (governed / "payload.py").write_text("VALUE = 1\n", encoding="utf-8")
    assert run(["git", "add", "governed/payload.py"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add governed payload"], cwd=repo).returncode == 0
    target = (tmp_path / "outside-target") if outside else (repo / "alternate")
    target.mkdir()
    (target / "payload.py").write_text("VALUE = 1\n", encoding="utf-8")
    # Remove the tracked directory after moving its file, then replace that
    # lexical ancestor with a symlink to byte-identical content.
    (governed / "payload.py").unlink()
    governed.rmdir()
    governed.symlink_to(target, target_is_directory=True)
    packet = agentops.parse_work_packet(
        minimal_packet(tmp_path, repo, allowed_files=["governed/**"])
    )

    with pytest.raises(agentops.AgentOpsError, match="symlink.*ancestor"):
        agentops.inspect_scope(repo, packet)


def test_scope_rejects_tracked_fifo_without_blocking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)
    payload = repo / "allowed.txt"
    payload.write_text("regular\n", encoding="utf-8")
    assert run(["git", "add", "allowed.txt"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add fifo fixture"], cwd=repo).returncode == 0
    payload.unlink()
    os.mkfifo(payload)
    packet = agentops.parse_work_packet(minimal_packet(tmp_path, repo))
    original_open = agentops.os.open

    def bounded_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
        if os.fspath(path) == os.fspath(payload):
            assert flags & getattr(os, "O_NONBLOCK", 0), (
                "tracked special files must be opened nonblocking"
            )
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(agentops.os, "open", bounded_open)

    with pytest.raises(agentops.AgentOpsError, match="regular non-symlink|regular file"):
        agentops.inspect_scope(repo, packet)


def test_scope_rejects_local_clean_filter_before_it_can_hide_bytes(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    (repo / "allowed.txt").write_text("baseline\n", encoding="utf-8")
    (repo / ".gitattributes").write_text(
        "allowed.txt filter=hide\n", encoding="utf-8"
    )
    assert run(["git", "add", "allowed.txt", ".gitattributes"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add filtered fixture"], cwd=repo).returncode == 0
    marker = tmp_path / "clean-filter-ran"
    filter_script = tmp_path / "hide-clean"
    filter_script.write_text(
        f"#!/bin/sh\ntouch '{marker}'\nprintf 'baseline\\n'\n", encoding="utf-8"
    )
    filter_script.chmod(0o755)
    assert run(
        ["git", "config", "filter.hide.clean", str(filter_script)], cwd=repo
    ).returncode == 0
    (repo / "allowed.txt").write_text("forbidden changed bytes\n", encoding="utf-8")

    assert run(["git", "diff", "--name-only"], cwd=repo).stdout == ""
    assert marker.exists(), "ordinary Git must exercise the false-clean witness"
    marker.unlink()
    packet = agentops.parse_work_packet(minimal_packet(tmp_path, repo))
    with pytest.raises(agentops.AgentOpsError, match=r"filter\.\*"):
        agentops.inspect_scope(repo, packet)
    assert not marker.exists(), "AgentOps must reject before executing the filter"


def test_scope_enumerates_case_variant_that_git_ignorecase_hides(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_payload.py").write_text("VALUE = 1\n", encoding="utf-8")
    assert run(["git", "add", "tests/test_payload.py"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add case fixture"], cwd=repo).returncode == 0
    assert run(["git", "config", "core.ignoreCase", "true"], cwd=repo).returncode == 0
    if (tests_dir / "TEST_PAYLOAD.PY").exists():
        pytest.skip("case-variant enumeration requires a case-sensitive filesystem")
    (tests_dir / "test_Payload.py").write_text(
        "def test_case_variant_executes():\n    assert True\n", encoding="utf-8"
    )
    assert run(["git", "ls-files", "--others", "-z"], cwd=repo).stdout == ""

    packet = agentops.parse_work_packet(
        minimal_packet(tmp_path, repo, allowed_files=["tests/**"])
    )
    scope = agentops.inspect_scope(repo, packet)
    assert "tests/test_Payload.py" in scope.untracked_files
    assert "tests/test_Payload.py" in scope.changed_files


def test_agentops_committed_range_scope_gate(tmp_path: Path) -> None:
    """O4-B4: committed paths use the existing forbidden-over-allowed matcher."""
    repo = init_repo(tmp_path)
    (repo / "forbidden.txt").write_text("rename source\n", encoding="utf-8")
    assert run(["git", "add", "forbidden.txt"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "forbidden rename fixture"], cwd=repo).returncode == 0
    base = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    packet = agentops.parse_work_packet(
        minimal_packet(
            tmp_path,
            repo,
            base_ref=base,
            allowed_files=["allowed.txt", "forbidden.txt"],
            forbidden_files=["forbidden.txt"],
        )
    )
    assert run(["git", "mv", "forbidden.txt", "allowed.txt"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "rename forbidden to allowed"], cwd=repo).returncode == 0

    scope = agentops.inspect_scope(repo, packet, base_ref=base)

    assert scope.tracked_changed_files == ["allowed.txt", "forbidden.txt"]
    assert scope.changed_files == ["allowed.txt", "forbidden.txt"]
    assert scope.violations == [
        {"path": "forbidden.txt", "reason": "forbidden", "patterns": ["forbidden.txt"]}
    ]


def test_agentops_committed_range_ignores_git_replace_objects(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    ordinary_env = {
        key: value
        for key, value in os.environ.items()
        if not key.casefold().startswith("git_")
    }

    def ordinary_git(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            env=ordinary_env,
            capture_output=True,
            text=True,
            check=False,
        )

    base = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    (repo / "forbidden.txt").write_text("committed\n", encoding="utf-8")
    assert run(["git", "add", "forbidden.txt"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add forbidden path"], cwd=repo).returncode == 0
    actual_head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    assert ordinary_git(["replace", actual_head, base]).returncode == 0
    assert ordinary_git(["read-tree", "--reset", "-u", base]).returncode == 0

    # Establish the adversarial witness: ordinary Git honors the replacement
    # and reports an empty tree/range, while actual-object Git sees the commit.
    assert ordinary_git(["status", "--short"]).stdout == ""
    assert ordinary_git(
        ["diff", "--name-only", f"{base}...HEAD", "--"]
    ).stdout == ""
    assert ordinary_git(
        [
            "--no-replace-objects", "diff", "--name-only",
            f"{base}...HEAD", "--",
        ]
    ).stdout.splitlines() == ["forbidden.txt"]
    packet = agentops.parse_work_packet(
        minimal_packet(
            tmp_path,
            repo,
            base_ref=base,
            allowed_files=["forbidden.txt"],
            forbidden_files=["forbidden.txt"],
        )
    )

    scope = agentops.inspect_scope(repo, packet, base_ref=base)

    assert scope.changed_files == ["forbidden.txt"]
    assert scope.violations == [
        {"path": "forbidden.txt", "reason": "forbidden", "patterns": ["forbidden.txt"]}
    ]


def test_agentops_rejects_legacy_grafts_that_fabricate_base_ancestry(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    base = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    assert run(["git", "switch", "--orphan", "unrelated"], cwd=repo).returncode == 0
    assert run(["git", "rm", "-rf", "--ignore-unmatch", "."], cwd=repo).returncode == 0
    (repo / "README.md").write_text("unrelated root\n", encoding="utf-8")
    assert run(["git", "add", "README.md"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "unrelated root"], cwd=repo).returncode == 0
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    assert run(
        ["git", "merge-base", "--is-ancestor", base, head], cwd=repo
    ).returncode != 0
    grafts = repo / ".git/info/grafts"
    grafts.write_text(f"{head} {base}\n", encoding="utf-8")
    assert run(
        ["git", "merge-base", "--is-ancestor", base, head], cwd=repo
    ).returncode == 0, "ordinary Git must prove the forged-ancestry witness"

    packet = agentops.parse_work_packet(
        minimal_packet(tmp_path, repo, base_ref=base, branch="unrelated")
    )
    with pytest.raises(agentops.AgentOpsError, match="info/grafts"):
        agentops.inspect_scope(repo, packet, base_ref=base)


@pytest.mark.parametrize(
    ("filename", "deceptive_allowed"),
    [
        (" allowed.txt", "allowed.txt"),
        ("allowed.txt ", "allowed.txt"),
        ("line\nbreak.txt", "linebreak.txt"),
    ],
)
def test_agentops_scope_preserves_exact_unusual_git_pathnames(
    tmp_path: Path,
    filename: str,
    deceptive_allowed: str,
) -> None:
    repo = init_repo(tmp_path)
    base = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    (repo / filename).write_text("committed\n", encoding="utf-8")
    assert run(["git", "add", "--", filename], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add unusual path"], cwd=repo).returncode == 0
    packet = agentops.parse_work_packet(
        minimal_packet(
            tmp_path,
            repo,
            base_ref=base,
            allowed_files=[deceptive_allowed],
            forbidden_files=[],
        )
    )

    scope = agentops.inspect_scope(repo, packet, base_ref=base)

    assert scope.changed_files == [filename]
    assert scope.violations == [
        {"path": filename, "reason": "outside_allowed_scope", "patterns": []}
    ]


def test_agentops_scope_rejects_backslash_git_pathname(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    base = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    filename = "allowed\\evil.py"
    (repo / filename).write_text("committed\n", encoding="utf-8")
    assert run(["git", "add", "--", filename], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add ambiguous path"], cwd=repo).returncode == 0
    packet = agentops.parse_work_packet(
        minimal_packet(
            tmp_path,
            repo,
            base_ref=base,
            allowed_files=["allowed/evil.py"],
            forbidden_files=[],
        )
    )

    with pytest.raises(agentops.AgentOpsError, match="backslash"):
        agentops.inspect_scope(repo, packet, base_ref=base)


@pytest.mark.parametrize("local_exclude", ["info", "config", "worktree"])
def test_agentops_scope_rejects_local_excludes_hiding_pytest_code(
    tmp_path: Path,
    local_exclude: str,
) -> None:
    repo = init_repo(tmp_path)
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_ok.py").write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    assert run(["git", "add", "tests/test_ok.py"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add tracked test"], cwd=repo).returncode == 0
    marker = tmp_path / f"hidden-{local_exclude}-executed"
    (tests_dir / "conftest.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).touch()\n",
        encoding="utf-8",
    )
    if local_exclude == "info":
        exclude = Path(
            run(["git", "rev-parse", "--git-path", "info/exclude"], cwd=repo)
            .stdout.strip()
        )
        if not exclude.is_absolute():
            exclude = repo / exclude
        exclude.write_text("tests/conftest.py\n", encoding="utf-8")
    else:
        exclude = tmp_path / "local-excludes"
        exclude.write_text("tests/conftest.py\n", encoding="utf-8")
        if local_exclude == "worktree":
            assert run(
                ["git", "config", "extensions.worktreeConfig", "true"], cwd=repo
            ).returncode == 0
            config_scope = "--worktree"
        else:
            config_scope = "--local"
        assert run(
            ["git", "config", config_scope, "core.excludesFile", str(exclude)],
            cwd=repo,
        ).returncode == 0

    assert run(["git", "status", "--short"], cwd=repo).stdout == ""
    witness = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_ok.py", "-q"],
        cwd=repo,
        env={
            **os.environ,
            "PYTEST_ADDOPTS": "-p no:cacheprovider",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert witness.returncode == 0, witness.stdout + witness.stderr
    assert marker.exists()
    marker.unlink()
    base = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    packet = agentops.parse_work_packet(
        minimal_packet(
            tmp_path,
            repo,
            base_ref=base,
            allowed_files=["tests/**"],
        )
    )

    with pytest.raises(agentops.AgentOpsError, match="exclude|gitignore"):
        agentops.inspect_scope(repo, packet, base_ref=base)
    assert not marker.exists()


def test_agentops_scope_includes_self_hidden_untracked_gitignore(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / ".gitignore").write_text(
        "conftest.py\n.gitignore\n", encoding="utf-8"
    )
    (tests_dir / "conftest.py").write_text("hidden fixture\n", encoding="utf-8")
    assert run(["git", "status", "--short"], cwd=repo).stdout == ""
    packet = agentops.parse_work_packet(
        minimal_packet(
            tmp_path,
            repo,
            allowed_files=["tests/**"],
            forbidden_files=[],
        )
    )

    scope = agentops.inspect_scope(repo, packet)

    assert scope.untracked_files == ["tests/.gitignore", "tests/conftest.py"]
    assert scope.changed_files == ["tests/.gitignore", "tests/conftest.py"]
    assert scope.violations == []


def test_agentops_scope_rejects_space_prefixed_info_exclude_pattern(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    exclude = Path(
        run(["git", "rev-parse", "--git-path", "info/exclude"], cwd=repo)
        .stdout.strip()
    )
    if not exclude.is_absolute():
        exclude = repo / exclude
    exclude.write_text(" #active-pattern\n", encoding="utf-8")
    packet = agentops.parse_work_packet(minimal_packet(tmp_path, repo))

    with pytest.raises(agentops.AgentOpsError, match="info/exclude"):
        agentops.inspect_scope(repo, packet)


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
    # PYTHONPYCACHEPREFIX mirrors REPO_ROOT, but interpreter startup itself
    # (the uv-managed venv's _virtualenv.pth shim and the dharma_swarm
    # editable-install finder, both under the gitignored .venv/) writes its
    # own bytecode there before the runner's code ever executes — that is
    # not "the runner polluting the repo". Only tracked source paths count.
    repo_cache = pycache_prefix / REPO_ROOT.as_posix().lstrip("/")
    tracked_bytecode = [
        p
        for p in repo_cache.rglob("*.pyc")
        if ".venv" not in p.relative_to(repo_cache).parts
    ] if repo_cache.exists() else []
    assert not tracked_bytecode, (
        f"runner wrote bytecode into tracked source paths: {tracked_bytecode}"
    )


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
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
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
        assert child_env["HOME"] == os.devnull
        assert child_env["XDG_CONFIG_HOME"] == os.devnull
        for key in ("PATH", "KEEP_ME", "GITHUB_ACTIONS"):
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
    agentops.run_negative_control(
        source, negative_gate, temp_root=external_tmp
    )
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
    agentops.run_negative_control(
        source, non_git_negative, temp_root=external_tmp
    )
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


def test_create_commit_uses_global_identity_without_trusting_git_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)
    assert run(["git", "config", "--unset", "user.name"], cwd=repo).returncode == 0
    assert run(["git", "config", "--unset", "user.email"], cwd=repo).returncode == 0
    assert run(
        ["git", "config", "user.useConfigOnly", "true"], cwd=repo
    ).returncode == 0

    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text(
        "[user]\n\tname = Global AgentOps\n\temail = global-agentops@example.invalid\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(agentops, "_os_account_home", lambda: home, raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Inherited Attacker")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "attacker@example.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Inherited Attacker")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "attacker@example.invalid")

    changed = repo / "allowed.txt"
    changed.write_text("identity probe\n", encoding="utf-8")
    commit = agentops.create_commit(repo, ["allowed.txt"], "test: global identity")

    assert commit == agentops.head_for(repo)
    identity = agentops.run_git(
        ["show", "-s", "--format=%an%n%ae%n%cn%n%ce", "HEAD"], cwd=repo
    ).stdout.splitlines()
    assert identity == [
        "Global AgentOps",
        "global-agentops@example.invalid",
        "Global AgentOps",
        "global-agentops@example.invalid",
    ]


@pytest.mark.parametrize("redirect", ["HOME", "XDG_CONFIG_HOME"])
def test_commit_identity_ignores_inherited_config_redirects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, redirect: str,
) -> None:
    repo = init_repo(tmp_path)
    assert run(["git", "config", "--unset", "user.name"], cwd=repo).returncode == 0
    assert run(["git", "config", "--unset", "user.email"], cwd=repo).returncode == 0
    assert run(
        ["git", "config", "user.useConfigOnly", "true"], cwd=repo
    ).returncode == 0

    trusted_home = tmp_path / "trusted-home"
    attacker_home = tmp_path / "attacker-home"
    empty_home = tmp_path / "empty-home"
    trusted_home.mkdir()
    attacker_home.mkdir()
    empty_home.mkdir()
    trusted_config = trusted_home / ".gitconfig"
    attacker_config = attacker_home / ".gitconfig"
    if redirect == "XDG_CONFIG_HOME":
        trusted_config = trusted_home / ".config/git/config"
        attacker_config = attacker_home / "git/config"
    trusted_config.parent.mkdir(parents=True, exist_ok=True)
    attacker_config.parent.mkdir(parents=True, exist_ok=True)
    trusted_config.write_text(
        "[user]\n\tname = Trusted OS User\n\temail = trusted@example.invalid\n",
        encoding="utf-8",
    )
    attacker_config.write_text(
        "[user]\n\tname = Redirected Attacker\n\temail = attacker@example.invalid\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        agentops, "_os_account_home", lambda: trusted_home, raising=False
    )
    if redirect == "HOME":
        monkeypatch.setenv("HOME", str(attacker_home))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(empty_home))
    else:
        monkeypatch.setenv("HOME", str(empty_home))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(attacker_home))

    changed = repo / f"{redirect.lower()}-identity.txt"
    changed.write_text("redirect probe\n", encoding="utf-8")
    agentops.create_commit(repo, [changed.name], f"test: ignore {redirect}")
    identity = agentops.run_git(
        ["show", "-s", "--format=%an%n%ae%n%cn%n%ce", "HEAD"], cwd=repo
    ).stdout.splitlines()
    assert identity == [
        "Trusted OS User",
        "trusted@example.invalid",
        "Trusted OS User",
        "trusted@example.invalid",
    ]


def test_os_account_home_ignores_environment_redirects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = agentops._os_account_home()
    monkeypatch.setenv("HOME", str(tmp_path / "redirected-home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "redirected-xdg"))
    assert agentops._os_account_home() == expected


def _install_trusted_commit_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    trusted_home = tmp_path / "trusted-home"
    trusted_home.mkdir()
    (trusted_home / ".gitconfig").write_text(
        "[user]\n\tname = Trusted OS User\n\temail = trusted@example.invalid\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        agentops, "_os_account_home", lambda: trusted_home, raising=False
    )


def test_create_commit_disables_default_reference_transaction_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)
    _install_trusted_commit_identity(tmp_path, monkeypatch)
    marker = tmp_path / "reference-transaction-ran"
    hook = repo / ".git/hooks/reference-transaction"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
    hook.chmod(0o755)
    changed = repo / "reference-hook.txt"
    changed.write_text("reference hook probe\n", encoding="utf-8")

    agentops.create_commit(repo, [changed.name], "test: disable reference hook")

    assert not marker.exists()


def test_create_commit_disables_post_index_change_hook_during_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)
    _install_trusted_commit_identity(tmp_path, monkeypatch)
    doomed = repo / "doomed.txt"
    doomed.write_text("remove me\n", encoding="utf-8")
    assert run(["git", "add", doomed.name], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add doomed"], cwd=repo).returncode == 0
    marker = tmp_path / "post-index-change-ran"
    hook = repo / ".git/hooks/post-index-change"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
    hook.chmod(0o755)
    changed = repo / "index-hook.txt"
    changed.write_text("index hook probe\n", encoding="utf-8")
    doomed.unlink()

    agentops.create_commit(
        repo, [changed.name, doomed.name], "test: disable index hook"
    )

    assert not marker.exists()
    assert agentops.run_git(
        ["show", f"HEAD:{changed.name}"], cwd=repo
    ).stdout == "index hook probe\n"
    assert agentops.run_git(
        ["cat-file", "-e", f"HEAD:{doomed.name}"], cwd=repo, check=False
    ).returncode != 0


def test_create_commit_preserves_tracked_executable_when_filemode_is_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)
    executable = repo / "tool.sh"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    assert run(["git", "add", "tool.sh"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add executable"], cwd=repo).returncode == 0
    assert run(["git", "config", "core.fileMode", "false"], cwd=repo).returncode == 0
    executable.chmod(0o644)
    executable.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    _install_trusted_commit_identity(tmp_path, monkeypatch)

    agentops.create_commit(repo, [executable.name], "test: preserve executable")

    assert agentops.run_git(
        ["ls-tree", "HEAD", "--", executable.name], cwd=repo
    ).stdout.startswith("100755 blob ")
    assert agentops.run_git(
        ["show", f"HEAD:{executable.name}"], cwd=repo
    ).stdout == "#!/bin/sh\nexit 1\n"


def test_create_commit_ignores_local_identity_hooks_and_signing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)
    trusted_home = tmp_path / "trusted-home"
    trusted_home.mkdir()
    (trusted_home / ".gitconfig").write_text(
        "[user]\n\tname = Trusted OS User\n\temail = trusted@example.invalid\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(agentops, "_os_account_home", lambda: trusted_home, raising=False)
    monkeypatch.setenv("HOME", str(trusted_home))
    monkeypatch.setenv("EMAIL", "fallback-poison@example.invalid")
    assert run(["git", "config", "user.name", "Local Attacker"], cwd=repo).returncode == 0
    assert run(
        ["git", "config", "user.email", "local-attacker@example.invalid"], cwd=repo
    ).returncode == 0

    hook_marker = tmp_path / "hook-ran"
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    pre_commit = hooks / "pre-commit"
    pre_commit.write_text(
        f"#!/bin/sh\ntouch '{hook_marker}'\n", encoding="utf-8"
    )
    pre_commit.chmod(0o755)
    reference_hook_marker = tmp_path / "reference-hook-ran"
    reference_hook = hooks / "reference-transaction"
    reference_hook.write_text(
        f"#!/bin/sh\ntouch '{reference_hook_marker}'\n", encoding="utf-8"
    )
    reference_hook.chmod(0o755)
    assert run(
        ["git", "config", "core.hooksPath", str(hooks)], cwd=repo
    ).returncode == 0

    signer_marker = tmp_path / "signer-ran"
    signer = tmp_path / "signer"
    signer.write_text(
        f"#!/bin/sh\ntouch '{signer_marker}'\nexit 1\n", encoding="utf-8"
    )
    signer.chmod(0o755)
    assert run(
        ["git", "config", "gpg.program", str(signer)], cwd=repo
    ).returncode == 0
    assert run(["git", "config", "commit.gpgSign", "true"], cwd=repo).returncode == 0
    fsmonitor_marker = tmp_path / "fsmonitor-ran"
    fsmonitor = tmp_path / "fsmonitor"
    fsmonitor.write_text(
        f"#!/bin/sh\ntouch '{fsmonitor_marker}'\nexit 1\n", encoding="utf-8"
    )
    fsmonitor.chmod(0o755)
    assert run(
        ["git", "config", "core.fsmonitor", str(fsmonitor)], cwd=repo
    ).returncode == 0

    changed = repo / "local-controls.txt"
    changed.write_text("local controls probe\n", encoding="utf-8")
    agentops.create_commit(repo, [changed.name], "test: isolate local controls")

    assert not hook_marker.exists()
    assert not reference_hook_marker.exists()
    assert not signer_marker.exists()
    assert not fsmonitor_marker.exists()
    identity = agentops.run_git(
        ["show", "-s", "--format=%an%n%ae%n%cn%n%ce", "HEAD"], cwd=repo
    ).stdout.splitlines()
    assert identity == [
        "Trusted OS User",
        "trusted@example.invalid",
        "Trusted OS User",
        "trusted@example.invalid",
    ]
    assert agentops.run_git(
        ["reflog", "-1", "--format=%gN%n%gE", "HEAD"], cwd=repo
    ).stdout.splitlines() == ["Trusted OS User", "trusted@example.invalid"]


def test_create_commit_stages_exact_bytes_without_local_filters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)
    trusted_home = tmp_path / "trusted-home"
    trusted_home.mkdir()
    (trusted_home / ".gitconfig").write_text(
        "[user]\n\tname = Trusted OS User\n\temail = trusted@example.invalid\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(agentops, "_os_account_home", lambda: trusted_home, raising=False)
    attributes = repo / ".gitattributes"
    attributes.write_text("filtered.txt filter=danger\n", encoding="utf-8")
    assert run(["git", "add", ".gitattributes"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add filter attributes"], cwd=repo).returncode == 0
    filter_marker = tmp_path / "filter-ran"
    filter_script = tmp_path / "filter-script"
    filter_script.write_text(
        f"#!/bin/sh\ntouch '{filter_marker}'\ncat\n", encoding="utf-8"
    )
    filter_script.chmod(0o755)
    assert run(
        ["git", "config", "filter.danger.clean", str(filter_script)],
        cwd=repo,
    ).returncode == 0
    changed = repo / "filtered.txt"
    changed.write_text("filter probe\n", encoding="utf-8")

    agentops.create_commit(repo, [changed.name], "test: bypass local filter")
    assert not filter_marker.exists()
    assert agentops.run_git(
        ["show", "HEAD:filtered.txt"], cwd=repo
    ).stdout == "filter probe\n"


def test_create_commit_stages_exact_bytes_without_worktree_filters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)
    trusted_home = tmp_path / "trusted-home"
    trusted_home.mkdir()
    (trusted_home / ".gitconfig").write_text(
        "[user]\n\tname = Trusted OS User\n\temail = trusted@example.invalid\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(agentops, "_os_account_home", lambda: trusted_home, raising=False)
    (repo / ".gitattributes").write_text(
        "filtered.txt filter=danger\n", encoding="utf-8"
    )
    assert run(["git", "add", ".gitattributes"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add filter attributes"], cwd=repo).returncode == 0
    filter_marker = tmp_path / "worktree-filter-ran"
    filter_script = tmp_path / "worktree-filter"
    filter_script.write_text(
        f"#!/bin/sh\ntouch '{filter_marker}'\ncat\n", encoding="utf-8"
    )
    filter_script.chmod(0o755)
    assert run(
        ["git", "config", "extensions.worktreeConfig", "true"], cwd=repo
    ).returncode == 0
    assert run(
        [
            "git", "config", "--worktree", "filter.danger.clean",
            str(filter_script),
        ],
        cwd=repo,
    ).returncode == 0
    changed = repo / "filtered.txt"
    changed.write_text("worktree filter probe\n", encoding="utf-8")

    agentops.create_commit(repo, [changed.name], "test: bypass worktree filter")
    assert not filter_marker.exists()
    assert agentops.run_git(
        ["show", "HEAD:filtered.txt"], cwd=repo
    ).stdout == "worktree filter probe\n"


def test_create_commit_filter_install_race_cannot_execute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)
    trusted_home = tmp_path / "trusted-home"
    trusted_home.mkdir()
    (trusted_home / ".gitconfig").write_text(
        "[user]\n\tname = Trusted OS User\n\temail = trusted@example.invalid\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(agentops, "_os_account_home", lambda: trusted_home, raising=False)
    (repo / ".gitattributes").write_text(
        "filtered.txt filter=danger\n", encoding="utf-8"
    )
    assert run(["git", "add", ".gitattributes"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add filter attributes"], cwd=repo).returncode == 0
    filter_marker = tmp_path / "racing-filter-ran"
    filter_script = tmp_path / "racing-filter"
    filter_script.write_text(
        f"#!/bin/sh\ntouch '{filter_marker}'\ncat\n", encoding="utf-8"
    )
    filter_script.chmod(0o755)
    changed = repo / "filtered.txt"
    changed.write_text("race filter probe\n", encoding="utf-8")
    original_hash = agentops.git_object_id_for_bytes
    race_armed = False

    def install_filter_before_hash(
        root: Path, content: bytes, *, write: bool = False,
    ) -> str:
        nonlocal race_armed
        if write and not race_armed:
            assert run(
                ["git", "config", "filter.danger.clean", str(filter_script)],
                cwd=repo,
            ).returncode == 0
            race_armed = True
        return original_hash(root, content, write=write)

    monkeypatch.setattr(agentops, "git_object_id_for_bytes", install_filter_before_hash)
    agentops.create_commit(repo, [changed.name], "test: bypass filter race")

    assert race_armed is True
    assert not filter_marker.exists()
    assert agentops.run_git(
        ["show", "HEAD:filtered.txt"], cwd=repo
    ).stdout == "race filter probe\n"


def test_create_commit_plumbing_preserves_binary_mode_and_deletion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)
    doomed = repo / "delete-me.txt"
    doomed.write_text("remove me\n", encoding="utf-8")
    assert run(["git", "add", "delete-me.txt"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "add deletion fixture"], cwd=repo).returncode == 0
    trusted_home = tmp_path / "trusted-home"
    trusted_home.mkdir()
    (trusted_home / ".gitconfig").write_text(
        "[user]\n\tname = Trusted OS User\n\temail = trusted@example.invalid\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(agentops, "_os_account_home", lambda: trusted_home, raising=False)
    binary = repo / "binary.bin"
    binary_bytes = b"\x00\xffexact\n"
    binary.write_bytes(binary_bytes)
    executable = repo / "tool.sh"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    doomed.unlink()

    agentops.create_commit(
        repo,
        ["binary.bin", "delete-me.txt", "tool.sh"],
        "test: exact plumbing parity",
    )

    binary_result = subprocess.run(
        ["git", "show", "HEAD:binary.bin"], cwd=repo, capture_output=True, check=False
    )
    assert binary_result.returncode == 0
    assert binary_result.stdout == binary_bytes
    assert agentops.run_git(
        ["ls-tree", "HEAD", "--", "tool.sh"], cwd=repo
    ).stdout.startswith("100755 blob ")
    assert run(
        ["git", "cat-file", "-e", "HEAD:delete-me.txt"], cwd=repo
    ).returncode != 0
    assert agentops.git_status(repo) == ""


@pytest.mark.parametrize(
    ("identity_config", "expected"),
    [
        (
            "[user]\n\tname = First\n\tname = Second\n"
            "\temail = trusted@example.invalid\n",
            "exactly one",
        ),
        ("[user]\n\tname = Trusted OS User\n", "complete"),
    ],
)
def test_commit_identity_requires_one_complete_global_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    identity_config: str,
    expected: str,
) -> None:
    repo = init_repo(tmp_path)
    assert run(["git", "config", "--unset", "user.name"], cwd=repo).returncode == 0
    assert run(["git", "config", "--unset", "user.email"], cwd=repo).returncode == 0
    assert run(
        ["git", "config", "user.useConfigOnly", "true"], cwd=repo
    ).returncode == 0
    trusted_home = tmp_path / "trusted-home"
    trusted_home.mkdir()
    (trusted_home / ".gitconfig").write_text(identity_config, encoding="utf-8")
    monkeypatch.setattr(agentops, "_os_account_home", lambda: trusted_home, raising=False)
    monkeypatch.setenv("HOME", str(trusted_home))
    monkeypatch.setenv("EMAIL", "fallback-poison@example.invalid")
    changed = repo / "invalid-identity.txt"
    changed.write_text("invalid identity probe\n", encoding="utf-8")

    with pytest.raises(agentops.AgentOpsError, match=expected):
        agentops.create_commit(repo, [changed.name], "test: reject identity")
    assert agentops.run_git(
        ["diff", "--cached", "--name-only"], cwd=repo
    ).stdout == ""


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
    entry["work_packet"] = "WP-Z99"
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

    track_path = repo / "docs/governance/ACTIVE_TRACK.yaml"
    track_document = json.loads(track_path.read_text(encoding="utf-8"))
    track_document["active_tracks"][0]["status"] = "SHIPPABLE"
    track_path.write_text(json.dumps(track_document), encoding="utf-8")
    assert run(["git", "add", "--", track_path.relative_to(repo).as_posix()], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "mark fixture track shippable"], cwd=repo).returncode == 0
    shippable = seal_packet(session_packet(repo))
    external = write_external_packet(tmp_path / "shippable", shippable)
    exit_code, report = agentops.execute_packet(
        external,
        source_root=repo,
        dry_run=True,
    )
    assert exit_code == 0 and report is None


def test_session_entry_work_packet_identity_is_generic_and_cross_bound(
    tmp_path: Path,
) -> None:
    repo = init_session_repo(tmp_path)

    def packet_for(work_packet: str, *, packet_id: str | None = None) -> dict[str, object]:
        payload = session_packet(repo)
        identity = packet_id or f"session-entry-test-{work_packet}"
        payload["id"] = identity
        payload["allowed_files"] = [
            "allowed.txt",
            f"reports/agentops/work_packets/{identity}.json",
        ]
        entry = payload["session_entry"]
        assert isinstance(entry, dict)
        entry["work_packet"] = work_packet
        return seal_packet(payload)

    for work_packet in (
        "WP-T1", "WP-LC10", "WP-A2A3", "WP-T3-B0", "WP-00", "WP-0S", "WP-0C1R",
    ):
        parsed = agentops.parse_work_packet(packet_for(work_packet))
        assert parsed.session_entry is not None
        assert parsed.session_entry.work_packet == work_packet

    for rejected in ("T1", "WP-", "WP-t1", "WP-T_1", "WP--T1", "WP-T1-"):
        with pytest.raises(agentops.AgentOpsError, match="work_packet.*packet id"):
            agentops.parse_work_packet(packet_for(rejected))

    with pytest.raises(agentops.AgentOpsError, match="work_packet.*packet id"):
        agentops.parse_work_packet(
            packet_for("WP-LC10", packet_id="session-entry-test-WP-LC1")
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
    create_commit = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "create_commit"
    )
    commit_environment_assignments = [
        node
        for node in ast.walk(create_commit)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "commit_environment"
            for target in node.targets
        )
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "trusted_git_commit_environment"
    ]
    assert len(commit_environment_assignments) == 1

    violations: list[int] = []
    identity_probe_lines: list[int] = []
    commit_environment_lines: list[int] = []
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
        helper = (
            env.func.id
            if isinstance(env, ast.Call) and isinstance(env.func, ast.Name)
            else ""
        )
        literal_values = [
            item.value if isinstance(item, ast.Constant) else None
            for item in argv.elts
        ]
        if helper == "trusted_git_environment":
            continue
        if helper == "trusted_git_identity_probe_environment":
            if literal_values[:6] == [
                "git", "config", "--global", "--no-includes", "--get-all", None,
            ]:
                identity_probe_lines.append(node.lineno)
                continue
        trusted_commit_variable = (
            isinstance(env, ast.Name)
            and env.id == "commit_environment"
            and create_commit.lineno <= node.lineno <= (create_commit.end_lineno or node.lineno)
        )
        if helper == "trusted_git_commit_environment" or trusted_commit_variable:
            commit_tree_safe = (
                "commit-tree" in literal_values
                and "-S" not in literal_values
            )
            update_ref_safe = (
                "update-ref" in literal_values
                and "core.logAllRefUpdates=true" in literal_values
            )
            if commit_tree_safe or update_ref_safe:
                commit_environment_lines.append(node.lineno)
                continue
        violations.append(node.lineno)

    assert violations == []
    assert len(identity_probe_lines) == 1
    assert len(commit_environment_lines) == 2


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


def test_session_envelope_ignores_untouched_sibling_surfaces(tmp_path: Path) -> None:
    repo = init_session_repo(tmp_path)
    add_sibling_track(repo, surfaces=["terminal/**"])
    payload = seal_packet(session_packet(repo))
    assert "terminal/**" not in payload["forbidden_files"]
    external = write_external_packet(tmp_path, payload)
    packet = agentops.load_work_packet(external)

    state = agentops._validate_session_envelope(
        repo,
        external,
        packet,
        inspect=True,
        require_tracked_copy=False,
    )
    assert state == "absent"


def test_session_envelope_touched_sibling_surface_still_requires_declaration(
    tmp_path: Path,
) -> None:
    repo = init_session_repo(tmp_path)
    add_sibling_track(repo, surfaces=["terminal/**"])
    payload = seal_packet(session_packet(repo))
    external = write_external_packet(tmp_path, payload)
    tracked = tracked_packet_path(repo, payload)
    tracked.parent.mkdir(parents=True)
    tracked.write_bytes(external.read_bytes())
    stage_path(repo, tracked)
    touched = repo / "terminal/app.ts"
    touched.parent.mkdir()
    touched.write_text("export {}\n", encoding="utf-8")

    packet = agentops.load_work_packet(external)
    with pytest.raises(agentops.AgentOpsError, match="omit sibling owned surfaces"):
        agentops._validate_session_envelope(
            repo,
            external,
            packet,
            inspect=False,
            require_tracked_copy=True,
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


def test_preflight_rejects_nonportable_session_worktree(tmp_path: Path) -> None:
    repo = init_session_repo(tmp_path)
    payload = session_packet(repo)
    payload["worktree"] = "/tmp/not-portable"
    payload = seal_packet(payload)
    external = write_external_packet(tmp_path, payload)

    with pytest.raises(agentops.AgentOpsError, match='portable worktree "\\."'):
        agentops.execute_packet(
            external,
            source_root=repo,
            preflight=True,
            report_root=tmp_path / "external-reports",
        )


def test_preflight_exact_clean_rejects_status_hidden_untracked_path(
    tmp_path: Path,
) -> None:
    repo = init_session_repo(tmp_path)
    assert run(
        ["git", "config", "status.showUntrackedFiles", "no"], cwd=repo
    ).returncode == 0
    payload = seal_packet(session_packet(repo))
    external = write_external_packet(tmp_path, payload)
    (repo / "allowed.txt").write_text("status-hidden baseline drift\n", encoding="utf-8")
    assert run(["git", "status", "--porcelain"], cwd=repo).stdout == ""

    with pytest.raises(agentops.AgentOpsError, match="exact clean HEAD"):
        agentops.execute_packet(
            external,
            source_root=repo,
            preflight=True,
            report_root=tmp_path / "external-reports",
        )


def test_closeout_rejects_each_diff_class_and_packet_swap(tmp_path: Path) -> None:
    """O4-B3: closeout binds preflight digest and the complete Git diff union."""
    for diff_class in ("committed", "staged", "unstaged", "untracked"):
        case_root = tmp_path / diff_class
        case_root.mkdir()
        repo = init_session_repo(case_root)
        forbidden = repo / "forbidden.txt"
        forbidden.write_text("base\n", encoding="utf-8")
        assert run(["git", "add", "forbidden.txt"], cwd=repo).returncode == 0
        assert run(["git", "commit", "-m", "forbidden fixture"], cwd=repo).returncode == 0

        payload = seal_packet(session_packet(repo))
        external = write_external_packet(case_root, payload)
        report_root = case_root / "external-reports"
        exit_code, report = agentops.execute_packet(
            external,
            source_root=repo,
            preflight=True,
            report_root=report_root,
        )
        assert exit_code == 0 and report is not None

        tracked = tracked_packet_path(repo, payload)
        tracked.parent.mkdir(parents=True)
        tracked.write_bytes(external.read_bytes())
        stage_path(repo, tracked)
        if diff_class == "committed":
            forbidden.write_text("committed\n", encoding="utf-8")
            assert run(["git", "add", "forbidden.txt"], cwd=repo).returncode == 0
            assert run(["git", "commit", "-m", "forbidden committed"], cwd=repo).returncode == 0
        elif diff_class == "staged":
            forbidden.write_text("staged\n", encoding="utf-8")
            assert run(["git", "add", "forbidden.txt"], cwd=repo).returncode == 0
        elif diff_class == "unstaged":
            forbidden.write_text("unstaged\n", encoding="utf-8")
        else:
            (repo / "outside.txt").write_text("untracked\n", encoding="utf-8")

        exit_code, report = agentops.execute_packet(
            tracked,
            source_root=repo,
            closeout=True,
            report_root=report_root,
        )
        assert exit_code == 1 and report is not None
        expected = "outside.txt" if diff_class == "untracked" else "forbidden.txt"
        assert expected in report["scope"]["changed_files"]
        assert any(row["path"] == expected for row in report["scope"]["violations"])

    swap_root = tmp_path / "packet-swap"
    swap_root.mkdir()
    repo = init_session_repo(swap_root)
    original = seal_packet(session_packet(repo))
    external = write_external_packet(swap_root, original)
    report_root = swap_root / "external-reports"
    exit_code, report = agentops.execute_packet(
        external,
        source_root=repo,
        preflight=True,
        report_root=report_root,
    )
    assert exit_code == 0 and report is not None

    swapped = copy.deepcopy(original)
    swapped["intent"] = "A different, independently sealed packet."
    reseal_packet(swapped)
    tracked = tracked_packet_path(repo, swapped)
    tracked.parent.mkdir(parents=True)
    tracked.write_text(json.dumps(swapped, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stage_path(repo, tracked)
    with pytest.raises(agentops.AgentOpsError, match="preflight.*digest|digest.*preflight"):
        agentops.execute_packet(
            tracked,
            source_root=repo,
            closeout=True,
            report_root=report_root,
        )

    tracked.write_text(
        json.dumps(original, separators=(",", ":")), encoding="utf-8"
    )
    stage_path(repo, tracked)
    with pytest.raises(agentops.AgentOpsError, match="preflight.*digest|digest.*preflight"):
        agentops.execute_packet(
            tracked,
            source_root=repo,
            closeout=True,
            report_root=report_root,
        )


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


def test_negative_control_temp_root_must_be_external(tmp_path: Path) -> None:
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
    with pytest.raises(agentops.AgentOpsError, match="temp root.*repository|temp root"):
        agentops.run_negative_control(repo, gate, temp_root=repo)
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


def test_darwin_negative_confinement_uses_trusted_allow_then_deny_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jail = tmp_path / "jail"
    fixture = jail / "fixture"
    fixture.mkdir(parents=True)
    trusted_bin = tmp_path / "trusted"
    trusted_bin.mkdir()
    sandbox_exec = trusted_bin / "sandbox-exec"
    sandbox_exec.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    sandbox_exec.chmod(0o755)
    which_calls: list[tuple[str, str | None]] = []

    def trusted_which(name: str, *, path: str | None = None) -> str | None:
        which_calls.append((name, path))
        if name == "sandbox-exec" and path == agentops._TRUSTED_HOST_PATH:
            return str(sandbox_exec)
        return None

    monkeypatch.setattr(agentops.sys, "platform", "darwin")
    monkeypatch.setattr(agentops.shutil, "which", trusted_which)
    preexec_fn, prefix, jailed, env_via_argv = agentops._negative_confinement(
        jail, fixture
    )

    assert preexec_fn is None
    assert jailed is False
    assert env_via_argv is False
    assert which_calls == [("sandbox-exec", agentops._TRUSTED_HOST_PATH)]
    assert prefix[0] == str(sandbox_exec.resolve())
    assert prefix[1] == "-p"
    assert prefix[-1] == "--"
    profile = prefix[2]
    assert "(allow default) (deny file-write*)" in profile
    assert f'(subpath "{fixture.resolve()}")' in profile


@pytest.mark.skipif(sys.platform != "darwin", reason="requires macOS sandbox-exec")
def test_darwin_negative_confinement_executes_and_denies_outside_write(
    tmp_path: Path,
) -> None:
    jail = tmp_path / "jail"
    fixture = jail / "fixture"
    fixture.mkdir(parents=True)
    _preexec_fn, prefix, jailed, env_via_argv = agentops._negative_confinement(
        jail, fixture
    )
    assert jailed is False and env_via_argv is False

    inside = fixture / "inside-write"
    allowed = subprocess.run(
        [
            *prefix,
            "/bin/sh",
            "-c",
            'printf allowed > "$1"',
            "agentops-sandbox-test",
            str(inside),
        ],
        cwd=fixture,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert allowed.returncode == 0, allowed.stderr
    assert inside.read_text(encoding="utf-8") == "allowed"

    outside = tmp_path / "outside-victim"
    outside.write_text("sentinel", encoding="utf-8")
    denied = subprocess.run(
        [
            *prefix,
            "/bin/sh",
            "-c",
            'printf denied > "$1"',
            "agentops-sandbox-test",
            str(outside),
        ],
        cwd=fixture,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert denied.returncode != 0
    assert outside.read_text(encoding="utf-8") == "sentinel"

    outside_create = tmp_path / "outside-create"
    denied_create = subprocess.run(
        [
            *prefix,
            "/bin/sh",
            "-c",
            'printf denied > "$1"',
            "agentops-sandbox-test",
            str(outside_create),
        ],
        cwd=fixture,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert denied_create.returncode != 0
    assert not outside_create.exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="requires Darwin getconf")
def test_darwin_account_temp_root_native_and_prepares_report_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TMPDIR", "/attacker-selected-temp")
    monkeypatch.setenv("PATH", "/attacker-selected-path")
    native = subprocess.run(
        ["/usr/bin/getconf", "DARWIN_USER_TEMP_DIR"],
        cwd=Path("/"),
        env={"PATH": agentops._TRUSTED_HOST_PATH, "LANG": "C", "LC_ALL": "C"},
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    assert native.returncode == 0, native.stderr
    assert len(native.stdout.splitlines()) == 1
    expected = Path(native.stdout.strip()).resolve(strict=True)

    account_temp = agentops._darwin_account_temp_root()
    assert account_temp == expected
    assert account_temp.is_relative_to(Path("/private/var/folders").resolve(strict=True))

    with tempfile.TemporaryDirectory(
        dir=account_temp, prefix="dharma-agentops-native-proof-"
    ) as outer:
        report_root = Path(outer) / "reports"
        prepared = agentops._prepare_private_report_root(
            report_root, repo_root=REPO_ROOT
        )
        assert prepared == report_root.resolve()
        assert prepared.is_dir()
        assert stat.S_IMODE(prepared.stat().st_mode) == 0o700


def test_darwin_account_temp_root_uses_getconf_with_scrubbed_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "private-var-folders"
    account_temp = parent / "ab" / "opaque_account" / "T"
    account_temp.mkdir(parents=True, mode=0o700)
    hostile_tmpdir = tmp_path / "caller-selected-tmp"
    hostile_tmpdir.mkdir()
    monkeypatch.setenv("TMPDIR", str(hostile_tmpdir))
    monkeypatch.setattr(agentops, "_DARWIN_USER_TEMP_PARENT", parent)
    monkeypatch.setattr(
        agentops,
        "_trusted_host_tool",
        lambda name: "/usr/bin/getconf" if name == "getconf" else "",
    )
    observed: dict[str, object] = {}

    def fake_run_command(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        observed["argv"] = argv
        observed.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, f"{account_temp}\n", "")

    monkeypatch.setattr(agentops, "run_command", fake_run_command)

    assert agentops._darwin_account_temp_root() == account_temp.resolve()
    assert observed["argv"] == ["/usr/bin/getconf", "DARWIN_USER_TEMP_DIR"]
    assert observed["cwd"] == Path("/")
    assert observed["env"] == {
        "PATH": agentops._TRUSTED_HOST_PATH,
        "LANG": "C",
        "LC_ALL": "C",
    }
    assert str(hostile_tmpdir) not in str(observed)


@pytest.mark.parametrize(
    "case",
    ("nonzero", "multiline", "relative", "outside", "wrong-shape", "missing", "symlink"),
)
def test_darwin_account_temp_root_rejects_untrusted_getconf_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    parent = tmp_path / "private-var-folders"
    valid = parent / "ab" / "opaque" / "T"
    valid.mkdir(parents=True)
    outside = tmp_path / "outside" / "T"
    outside.mkdir(parents=True)
    wrong_shape = parent / "too-shallow" / "T"
    wrong_shape.mkdir(parents=True)
    symlink = parent / "cd" / "symlinked" / "T"
    symlink.parent.mkdir(parents=True)
    symlink.symlink_to(outside, target_is_directory=True)
    outputs = {
        "nonzero": (1, "", "denied"),
        "multiline": (0, f"{valid}\n{valid}\n", ""),
        "relative": (0, "relative/T\n", ""),
        "outside": (0, f"{outside}\n", ""),
        "wrong-shape": (0, f"{wrong_shape}\n", ""),
        "missing": (0, f"{parent / 'ef' / 'missing' / 'T'}\n", ""),
        "symlink": (0, f"{symlink}\n", ""),
    }
    returncode, stdout, stderr = outputs[case]
    monkeypatch.setattr(agentops, "_DARWIN_USER_TEMP_PARENT", parent)
    monkeypatch.setattr(agentops, "_trusted_host_tool", lambda _name: "/usr/bin/getconf")
    monkeypatch.setattr(
        agentops,
        "run_command",
        lambda argv, **_kwargs: subprocess.CompletedProcess(
            argv, returncode, stdout, stderr
        ),
    )

    with pytest.raises(agentops.AgentOpsError, match="Darwin account temp root"):
        agentops._darwin_account_temp_root()


def test_darwin_account_temp_root_normalizes_probe_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(agentops, "_trusted_host_tool", lambda _name: "/usr/bin/getconf")

    def time_out(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(argv, 5)

    monkeypatch.setattr(agentops, "run_command", time_out)
    with pytest.raises(agentops.AgentOpsError, match="Darwin account temp root"):
        agentops._darwin_account_temp_root()


def test_private_report_anchor_is_darwin_only_and_never_reads_tmpdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caller_temp = Path("/tmp") / f"agentops-caller-{tmp_path.name}"
    target = caller_temp / "reports"
    monkeypatch.setenv("TMPDIR", str(caller_temp))
    monkeypatch.setattr(agentops.sys, "platform", "linux")

    def forbidden_temp_lookup() -> str:
        raise AssertionError("non-Darwin report admission must not read TMPDIR")

    monkeypatch.setattr(agentops.tempfile, "gettempdir", forbidden_temp_lookup)
    monkeypatch.setattr(
        agentops,
        "_darwin_account_temp_root",
        lambda: (_ for _ in ()).throw(
            AssertionError("non-Darwin report admission used the Darwin anchor")
        ),
    )

    anchor, shared = agentops._private_report_anchor(target.resolve())
    assert anchor == Path("/tmp").resolve()
    assert shared is True


def test_private_report_anchor_accepts_only_os_derived_darwin_temp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account_temp = Path("/private/var/folders/ab/opaque-account/T")
    target = account_temp / "agentops" / "reports"
    monkeypatch.setattr(agentops.sys, "platform", "darwin")
    monkeypatch.setattr(
        agentops, "_darwin_account_temp_root", lambda: account_temp.resolve()
    )

    anchor, shared = agentops._private_report_anchor(target.resolve())
    assert anchor == account_temp.resolve()
    assert shared is False


def test_darwin_report_anchor_rejects_environment_minted_temp_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hostile = Path("/attacker-selected-private-temp")
    account_temp = Path("/private/var/folders/ab/opaque-account/T")
    monkeypatch.setattr(agentops.sys, "platform", "darwin")
    monkeypatch.setattr(agentops.tempfile, "gettempdir", lambda: str(hostile))
    monkeypatch.setattr(
        agentops, "_darwin_account_temp_root", lambda: account_temp
    )

    with pytest.raises(agentops.AgentOpsError, match="trusted temp anchor"):
        agentops._private_report_anchor(hostile / "reports")
    assert agentops._private_report_anchor(account_temp / "reports") == (
        account_temp,
        False,
    )


def test_darwin_report_anchor_skips_getconf_for_unrelated_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(agentops.sys, "platform", "darwin")
    monkeypatch.setattr(
        agentops,
        "_darwin_account_temp_root",
        lambda: (_ for _ in ()).throw(
            AssertionError("unrelated target must not probe Darwin account temp")
        ),
    )

    with pytest.raises(agentops.AgentOpsError, match="trusted temp anchor"):
        agentops._private_report_anchor(Path("/opt/untrusted-agentops/reports"))


def test_darwin_report_anchor_keeps_tmp_and_home_when_getconf_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(agentops.sys, "platform", "darwin")

    def unavailable() -> Path:
        raise AssertionError("established anchors must not consult getconf")

    monkeypatch.setattr(agentops, "_darwin_account_temp_root", unavailable)
    tmp_anchor = Path("/tmp").resolve()
    assert agentops._private_report_anchor(tmp_anchor / "agentops" / "reports") == (
        tmp_anchor,
        True,
    )
    home = agentops._os_account_home()
    assert agentops._private_report_anchor(home / ".dharma" / "agentops") == (
        home,
        False,
    )


def test_private_report_anchor_enforces_owner_mode_and_symlink_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    anchor = tmp_path / "account-temp"
    anchor.mkdir(mode=0o700)

    anchor.chmod(0o720)
    with pytest.raises(agentops.AgentOpsError, match="group/world writable"):
        agentops._validate_private_directory(anchor)
    anchor.chmod(0o700)

    link = tmp_path / "account-temp-link"
    link.symlink_to(anchor, target_is_directory=True)
    with pytest.raises(agentops.AgentOpsError, match="non-symlink directory"):
        agentops._validate_private_directory(link)

    metadata = agentops.os.lstat(anchor)

    class ForeignOwner:
        st_mode = metadata.st_mode
        st_uid = metadata.st_uid + 1

    monkeypatch.setattr(agentops.os, "lstat", lambda _path: ForeignOwner())
    with pytest.raises(agentops.AgentOpsError, match="not owned"):
        agentops._validate_private_directory(anchor)


def test_make_admission_reports_are_external_and_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O4-B9: preflight/closeout attempt no source or Git-state write."""
    repo = init_session_repo(tmp_path)
    (repo / ".gitignore").write_text("ignored-state.txt\n", encoding="utf-8")
    assert run(["git", "add", ".gitignore"], cwd=repo).returncode == 0
    assert run(["git", "commit", "-m", "ignore fixture state"], cwd=repo).returncode == 0

    payload = session_packet(repo)
    allowed = payload["allowed_files"]
    assert isinstance(allowed, list)
    allowed.append("ignored-state.txt")
    payload = seal_packet(payload)
    external = write_external_packet(tmp_path, payload)
    before_preflight = tree_state_snapshot(repo)
    status_before_preflight = agentops.git_status(repo)

    with pytest.raises(agentops.AgentOpsError, match="report.*root|report_root"):
        agentops.execute_packet(
            external, source_root=repo, preflight=True
        )
    assert tree_state_snapshot(repo) == before_preflight

    report_root = tmp_path / "external-reports"
    with monkeypatch.context() as preflight_guard:
        install_source_write_guard(preflight_guard, repo)
        exit_code, report = agentops.execute_packet(
            external,
            source_root=repo,
            preflight=True,
            report_root=report_root,
        )
    assert exit_code == 0 and report is not None
    assert report["phase"] == "preflight"
    assert tree_state_snapshot(repo) == before_preflight
    assert agentops.git_status(repo) == status_before_preflight

    tracked = tracked_packet_path(repo, payload)
    tracked.parent.mkdir(parents=True)
    tracked.write_bytes(external.read_bytes())
    stage_path(repo, tracked)
    # Preflight requires a truly clean baseline, including ignored paths.  Add
    # this allowed ignored fixture only for closeout, where it proves the
    # evaluator observes it and leaves its bytes untouched.
    (repo / "ignored-state.txt").write_text(
        "must remain byte-identical\n", encoding="utf-8"
    )
    before_closeout = tree_state_snapshot(repo)
    status_before_closeout = agentops.git_status(repo)
    ignored_bytes = (repo / "ignored-state.txt").read_bytes()

    negative_temp_roots: list[Path] = []
    real_negative_control = agentops.run_negative_control

    def observed_negative_control(
        source: Path,
        gate: agentops.GateSpec,
        *,
        temp_root: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        negative_temp_roots.append(temp_root)
        return real_negative_control(
            source,
            gate,
            temp_root=temp_root,
            **kwargs,
        )

    # Keep the real admitted Git gate and confined negative control executable.
    # The in-process OS/Path guard catches attempted source writes immediately;
    # the complete state snapshot also catches subprocess writes, ignored files,
    # mode changes, symlinks, and Git-admin mutations.
    monkeypatch.setattr(agentops, "run_negative_control", observed_negative_control)
    install_source_write_guard(monkeypatch, repo)
    exit_code, report = agentops.execute_packet(
        tracked,
        source_root=repo,
        closeout=True,
        report_root=report_root,
    )
    assert exit_code == 0 and report is not None
    assert report["phase"] == "closeout"
    assert len(list(report_root.rglob("report.json"))) >= 2
    assert len(list(report_root.rglob("report.md"))) >= 2
    assert negative_temp_roots == [
        report_root
        / "reports/agentops"
        / str(payload["id"])
        / "tool-cache/tmp"
    ]
    for directory in [report_root, *[path for path in report_root.rglob("*") if path.is_dir()]]:
        assert directory.stat().st_mode & 0o077 == 0
    for report_path in report_root.rglob("report.*"):
        assert report_path.stat().st_mode & 0o777 == 0o600
    assert tree_state_snapshot(repo) == before_closeout
    assert agentops.git_status(repo) == status_before_closeout
    assert (repo / "ignored-state.txt").read_bytes() == ignored_bytes


def test_session_entry_cli_requires_explicit_admission_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = init_session_repo(tmp_path)
    payload = seal_packet(session_packet(repo))
    external = write_external_packet(tmp_path, payload)
    before = tree_snapshot(repo)
    monkeypatch.chdir(repo)

    def must_not_execute(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("phase-less Session Entry route must not execute")

    monkeypatch.setattr(agentops, "execute_packet", must_not_execute)
    exit_code = agentops.main(
        [
            "--packet", str(external),
            "--report-root", str(tmp_path / "unused-reports"),
        ]
    )

    assert exit_code == 2
    assert tree_snapshot(repo) == before


def test_admission_cache_root_rejects_nested_symlink_into_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = init_session_repo(tmp_path)
    payload = seal_packet(session_packet(repo))
    external = write_external_packet(tmp_path, payload)
    report_root = tmp_path / "external-reports"
    exit_code, report = agentops.execute_packet(
        external,
        source_root=repo,
        preflight=True,
        report_root=report_root,
    )
    assert exit_code == 0 and report is not None
    tracked = tracked_packet_path(repo, payload)
    tracked.parent.mkdir(parents=True)
    tracked.write_bytes(external.read_bytes())
    stage_path(repo, tracked)

    cache_root = (
        report_root
        / "reports/agentops"
        / str(payload["id"])
        / "tool-cache"
    )
    cache_root.mkdir(parents=True)
    (cache_root / "pycache").symlink_to(repo, target_is_directory=True)

    def must_not_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("cache boundary must fail before a gate runs")

    monkeypatch.setattr(agentops, "run_gate", must_not_run)
    monkeypatch.setattr(agentops, "run_negative_control", must_not_run)
    with pytest.raises(
        agentops.AgentOpsError,
        match="report destination|inside repository|symlink",
    ):
        agentops.execute_packet(
            tracked,
            source_root=repo,
            closeout=True,
            report_root=report_root,
        )


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


def test_validate_report_root_prepares_children_and_rejects_source_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = init_repo(tmp_path)
    monkeypatch.chdir(repo)
    report_root = tmp_path / "validated-report-root"

    assert agentops.main(
        [
            "--validate-report-root", str(report_root),
            "--validate-report-child", "cache",
            "--validate-report-child", "onboard",
        ]
    ) == 0
    assert (report_root / "cache").is_dir()
    assert (report_root / "onboard").is_dir()
    assert stat.S_IMODE((report_root / "cache").stat().st_mode) == 0o700
    assert stat.S_IMODE((report_root / "onboard").stat().st_mode) == 0o700

    (report_root / "cache").rmdir()
    (report_root / "cache").symlink_to(repo, target_is_directory=True)
    before = tree_state_snapshot(repo)
    assert agentops.main(
        [
            "--validate-report-root", str(report_root),
            "--validate-report-child", "cache",
            "--validate-report-child", "onboard",
        ]
    ) == 2
    captured = capsys.readouterr()
    assert any(
        token in captured.err
        for token in ("symlink", "escapes", "inside repository", "external")
    )
    assert tree_state_snapshot(repo) == before


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
        "python3 scripts/docops/check_docops_integrity.py",
        "python3 scripts/docops/check_docops_integrity.py --changed-from "
        "0123456789abcdef0123456789abcdef01234567",
        "python3 scripts/governance/orientation_graph.py",
        "make docops-integrity",
        "git status --porcelain",
        "git.exe status --porcelain",
        "/usr/bin/git status --porcelain",
        '"C:\\Program Files\\Git\\cmd\\git.exe" status --porcelain',
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

    benign = ["make docops-integrity", "make hygiene-check", "make module-budget"]
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


def test_positive_gate_preserves_venv_python_and_rejects_alias_swap(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    alias = tmp_path / "current-python-alias"
    alias.symlink_to(sys.executable)
    for index, executable in enumerate(("python", "python3", sys.executable)):
        gate = agentops.parse_gate(
            {
                "name": f"python-alias-{index}",
                "command": f"{executable} -m pytest -q",
            },
            index,
        )
        agentops.admit_gate_command(gate)
        normalized = agentops._trusted_positive_gate_argv(gate.argv, repo_root=repo)
        assert normalized[0] == sys.executable

    # A path alias is not an exact running-interpreter identity, even while it
    # resolves to that interpreter.  This removes the symlink TOCTOU entirely.
    alias_gate = agentops.parse_gate(
        {
            "name": "python-alias",
            "command": f"{alias} -m pytest -q",
        },
        99,
    )
    with pytest.raises(agentops.AgentOpsError, match="not in the positive"):
        agentops.admit_gate_command(alias_gate)

    # Simulate a post-admission argv substitution.  Normalization must fail
    # closed rather than execute an unrecognized replacement path.
    admitted = agentops.parse_gate(
        {
            "name": "python-swap",
            "command": f"{sys.executable} -m pytest -q",
        },
        100,
    )
    agentops.admit_gate_command(admitted)
    admitted.argv[0] = str(alias)
    with pytest.raises(agentops.AgentOpsError, match="lost trusted identity"):
        agentops._trusted_positive_gate_argv(admitted.argv, repo_root=repo)

    # The exact lexical path matters when sys.executable is a venv symlink;
    # resolving it would silently select the base interpreter instead.
    assert agentops._trusted_positive_gate_argv(
        [sys.executable, "-m", "pytest", "-q"], repo_root=repo
    )[0] == sys.executable


def test_positive_git_forms_normalize_to_hardened_host_argv(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    trusted = agentops._trusted_host_tool("git")
    commands = (
        "git status --porcelain",
        "git.exe status --porcelain",
        "/usr/bin/git status --porcelain",
        '"C:\\Program Files\\Git\\cmd\\git.exe" status --porcelain',
    )
    for index, command in enumerate(commands):
        gate = agentops.parse_gate(
            {"name": f"trusted-git-{index}", "command": command}, index
        )
        agentops.admit_gate_command(gate)
        assert agentops._trusted_positive_gate_argv(gate.argv, repo_root=repo) == [
            trusted,
            "-c", "core.fsmonitor=false",
            "-c", f"core.hooksPath={os.devnull}",
            "status", "--porcelain",
        ]

    diff = agentops.parse_gate(
        {"name": "trusted-diff", "command": "git diff --check"}, 0
    )
    assert agentops._trusted_positive_gate_argv(diff.argv, repo_root=repo) == [
        trusted,
        "-c", "core.fsmonitor=false",
        "-c", f"core.hooksPath={os.devnull}",
        "diff", "--no-ext-diff", "--no-textconv", "--check",
    ]


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
        {
            "name": "json",
            "command": "python3 scripts/governance/orientation_graph.py --json",
        },
        0,
    )
    agentops.admit_gate_command(ok)  # must not raise


def test_gate_timeout_caps_each_gate_and_aggregate_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = agentops.parse_gate(
        {
            "name": "bounded",
            "command": "git status --porcelain",
            "timeout_seconds": 900,
        },
        0,
    )
    monkeypatch.setattr(agentops.time, "monotonic", lambda: 100.0)
    assert agentops._bounded_gate(gate, deadline=1_000.0).timeout_seconds == 300
    assert agentops._bounded_gate(gate, deadline=131.0).timeout_seconds == 31
    with pytest.raises(agentops.AgentOpsError, match="aggregate gate timeout"):
        agentops._bounded_gate(gate, deadline=100.0)


def test_owner_config_and_packet_decode_errors_are_normalized(tmp_path: Path) -> None:
    valid = {
        "id": "session-entry-test-track",
        "status": "ACTIVE",
        "owner": "owner",
        "owned_surfaces": ["tests/**"],
    }
    malformed = [
        {"active_tracks": [valid, copy.deepcopy(valid)]},
        {"active_tracks": ["not-an-object"]},
        {"active_tracks": [{**valid, "owned_surfaces": ["tests/**", "tests/**"]}]},
    ]
    for document in malformed:
        with pytest.raises(agentops.AgentOpsError):
            agentops._parse_active_tracks_document(
                json.dumps(document), source="adversarial ACTIVE_TRACK.yaml"
            )

    undecodable = tmp_path / "packet.json"
    undecodable.write_bytes(b"\xff\xfe")
    with pytest.raises(agentops.AgentOpsError, match="read|decode|packet"):
        agentops.load_raw_packet(undecodable)


@pytest.mark.parametrize("layer", ["committed", "staged", "working"])
def test_scope_rejects_non_regular_mode_in_each_diff_layer(
    tmp_path: Path,
    layer: str,
) -> None:
    repo = init_repo(tmp_path)
    base = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    packet = agentops.parse_work_packet(
        minimal_packet(
            tmp_path,
            repo,
            base_ref=base,
            allowed_files=["allowed.txt"],
            forbidden_files=[],
        )
    )
    (repo / "allowed.txt").symlink_to("README.md")
    if layer in {"committed", "staged"}:
        stage_path(repo, repo / "allowed.txt")
    if layer == "committed":
        assert run(["git", "commit", "-m", "symlink"], cwd=repo).returncode == 0

    scope = agentops.inspect_scope(repo, packet, base_ref=base)

    assert any(
        violation["path"] == "allowed.txt"
        and violation["reason"] == "non_regular_mode"
        for violation in scope.violations
    )


def test_scope_allows_a_governed_regular_file_deletion(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    allowed = repo / "allowed.txt"
    allowed.write_text("delete me\n", encoding="utf-8")
    stage_path(repo, allowed)
    assert run(["git", "commit", "-m", "add governed file"], cwd=repo).returncode == 0
    base = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    packet = agentops.parse_work_packet(
        minimal_packet(
            tmp_path,
            repo,
            base_ref=base,
            allowed_files=["allowed.txt"],
            forbidden_files=[],
        )
    )
    allowed.unlink()
    stage_path(repo, allowed)
    assert run(["git", "commit", "-m", "delete governed file"], cwd=repo).returncode == 0

    scope = agentops.inspect_scope(repo, packet, base_ref=base)

    assert scope.changed_files == ["allowed.txt"]
    assert scope.violations == []


def test_report_publication_is_dirfd_bound_and_cleans_post_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_root = tmp_path / "reports-root"
    report_root.mkdir(mode=0o700)
    destination = report_root / "reports/agentops/job/stamp/report.json"
    agentops._ensure_private_report_directory(report_root, destination.parent)
    original_fsync = agentops.os.fsync
    failed = False

    def fail_first_directory_fsync(descriptor: int) -> None:
        nonlocal failed
        if not failed and agentops.stat.S_ISDIR(agentops.os.fstat(descriptor).st_mode):
            failed = True
            raise OSError("injected post-replace directory fsync failure")
        original_fsync(descriptor)

    monkeypatch.setattr(agentops.os, "fsync", fail_first_directory_fsync)
    with pytest.raises(agentops.AgentOpsError, match="atomically publish"):
        agentops._atomic_report_write(report_root, destination, "{}\n")
    assert not destination.exists()
    assert list(destination.parent.glob(".*.tmp")) == []

    monkeypatch.setattr(agentops.os, "fsync", original_fsync)
    source = tmp_path / "source"
    source.mkdir()
    report = {
        "job_id": "job",
        "status": "passed",
        "base_ref": "base",
        "branch": "branch",
        "worktree": ".",
        "intent": "race probe",
        "scope": {"passed": True, "changed_files": [], "violations": []},
        "gates": [],
        "negative_controls": [],
        "commit_hash": None,
        "commit_decision": "none",
    }
    stamp_parent = report_root / "reports/agentops/job/race"
    moved_parent = report_root / "moved-race"

    def swap_parent_before_json() -> None:
        stamp_parent.rename(moved_parent)
        stamp_parent.symlink_to(source, target_is_directory=True)

    with pytest.raises(agentops.AgentOpsError, match="no-follow|report directory"):
        agentops.write_report(
            report_root,
            report,
            "race",
            before_json=swap_parent_before_json,
        )
    assert not (source / "report.json").exists()
    assert not (moved_parent / "report.json").exists()
    assert not (moved_parent / "report.md").exists()


def test_report_revalidation_failure_invalidates_preexisting_pair(
    tmp_path: Path,
) -> None:
    report_root = tmp_path / "reports-root"
    report_root.mkdir(mode=0o700)
    json_path, md_path = agentops.report_paths(report_root, "job", "stable")
    agentops._ensure_private_report_directory(report_root, json_path.parent)
    agentops._atomic_report_write(report_root, json_path, '{"status":"old"}\n')
    agentops._atomic_report_write(report_root, md_path, "- Status: passed\n")
    report = {
        "job_id": "job",
        "status": "passed",
        "base_ref": "base",
        "branch": "branch",
        "worktree": ".",
        "intent": "revalidation failure probe",
        "scope": {"passed": True, "changed_files": [], "violations": []},
        "gates": [],
        "negative_controls": [],
        "commit_hash": None,
        "commit_decision": "none",
    }

    def reject_revalidation() -> None:
        raise agentops.AgentOpsError("injected revalidation failure")

    with pytest.raises(agentops.AgentOpsError, match="injected revalidation"):
        agentops.write_report(
            report_root,
            report,
            "stable",
            before_json=reject_revalidation,
        )
    assert not json_path.exists()
    assert not md_path.exists()


def test_report_json_publication_uses_held_dirfd_across_post_verify_parent_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_root = tmp_path / "reports-root"
    report_root.mkdir(mode=0o700)
    report = {
        "job_id": "job",
        "status": "passed",
        "base_ref": "base",
        "branch": "branch",
        "worktree": ".",
        "intent": "post-verification parent swap probe",
        "scope": {"passed": True, "changed_files": [], "violations": []},
        "gates": [],
        "negative_controls": [],
        "commit_hash": None,
        "commit_decision": "none",
    }
    json_path, md_path = agentops.report_paths(report_root, "job", "race")
    moved_parent = report_root / "moved-race"
    original_write_at = agentops._atomic_report_write_at
    publication_parent_identity: tuple[int, int] | None = None
    swapped = False

    def swap_after_verification_before_json(
        parent_descriptor: int,
        name: str,
        text: str,
        *,
        display_path: Path,
    ) -> None:
        nonlocal publication_parent_identity, swapped
        identity = agentops.os.fstat(parent_descriptor)
        observed = (identity.st_dev, identity.st_ino)
        if publication_parent_identity is None:
            publication_parent_identity = observed
        else:
            assert observed == publication_parent_identity
        if name == json_path.name and not swapped:
            json_path.parent.rename(moved_parent)
            json_path.parent.mkdir(mode=0o700)
            json_path.write_text('{"status":"forged"}\n', encoding="utf-8")
            md_path.write_text("- Status: forged\n", encoding="utf-8")
            swapped = True
        original_write_at(
            parent_descriptor,
            name,
            text,
            display_path=display_path,
        )

    monkeypatch.setattr(agentops, "_atomic_report_write_at", swap_after_verification_before_json)
    with pytest.raises(agentops.AgentOpsError, match="directory custody changed"):
        agentops.write_report(report_root, report, "race")

    assert swapped
    assert not json_path.exists()
    assert not md_path.exists()
    assert not (moved_parent / json_path.name).exists()
    assert not (moved_parent / md_path.name).exists()


def test_preflight_binding_read_rejects_parent_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_root = tmp_path / "report-root"
    report_root.mkdir(mode=0o700)
    binding = report_root / "reports/agentops/job/preflight/report.json"
    agentops._ensure_private_report_directory(report_root, binding.parent)
    agentops._atomic_report_write(report_root, binding, "{}\n")
    attacker = tmp_path / "attacker"
    attacker.mkdir()
    (attacker / "report.json").write_text('{"status":"forged"}\n', encoding="utf-8")
    moved = report_root / "moved-binding"
    original_read = agentops.os.read
    swapped = False

    def swap_during_read(descriptor: int, amount: int) -> bytes:
        nonlocal swapped
        chunk = original_read(descriptor, amount)
        if not swapped:
            swapped = True
            binding.parent.rename(moved)
            binding.parent.symlink_to(attacker, target_is_directory=True)
        return chunk

    monkeypatch.setattr(agentops.os, "read", swap_during_read)
    with pytest.raises(agentops.AgentOpsError, match="directory|no-follow|custody"):
        agentops._read_private_report_file(report_root, binding)


def test_trusted_git_environment_is_minimal() -> None:
    environment = agentops.trusted_git_environment(
        {
            "PATH": "/tmp/shims",
            "LD_PRELOAD": "/tmp/loader.so",
            "PYTHONPATH": "/tmp/python",
            "MAKEFILES": "/tmp/makefile",
            "GIT_CONFIG_GLOBAL": "/tmp/gitconfig",
        }
    )
    assert environment == {
        "PATH": agentops._TRUSTED_HOST_PATH,
        "HOME": os.devnull,
        "XDG_CONFIG_HOME": os.devnull,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
    }


def test_admitted_direct_git_disables_repo_local_fsmonitor(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    witness_environment = agentops.trusted_git_environment()
    marker = tmp_path / "direct-git-fsmonitor-ran"
    hook = repo / ".git/hooks/fsmonitor-agentops"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(
        f"#!/bin/sh\ntouch '{marker}'\nprintf '1\\n'\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    assert (
        subprocess.run(
            ["git", "config", "core.fsmonitor", str(hook)],
            cwd=repo,
            env=witness_environment,
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        == 0
    )

    # Establish that the repository-local helper is live before exercising the
    # admitted path; otherwise a marker assertion could false-pass.
    assert (
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo,
            env=witness_environment,
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        == 0
    )
    assert marker.exists()
    marker.unlink()

    report_root = tmp_path / "direct-git-reports"
    report_root.mkdir(mode=0o700)
    environment = agentops._admission_gate_environment(report_root, repo, "packet")
    gate = agentops.parse_gate(
        {"name": "direct-git", "command": "git status --porcelain"}, 0
    )
    agentops.admit_gate_command(gate)
    result = agentops.run_gate(
        repo,
        gate,
        base_env=environment,
        normalize_positive_executable=True,
    )

    assert result["passed"] is True
    assert not marker.exists()


def test_admission_routes_hostile_hypothesis_storage_outside_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)
    hostile_storage = repo / ".hypothesis"
    monkeypatch.setenv("HYPOTHESIS_STORAGE_DIRECTORY", str(hostile_storage))
    report_root = tmp_path / "gate-reports"
    report_root.mkdir(mode=0o700)

    environment = agentops._admission_gate_environment(
        report_root, repo, "packet"
    )

    expected = (
        report_root
        / agentops.REPORT_ROOT
        / "packet"
        / "tool-cache"
        / "hypothesis"
    )
    assert environment["HYPOTHESIS_STORAGE_DIRECTORY"] == str(expected)
    assert expected.is_dir()
    assert not hostile_storage.exists()


def test_admitted_make_ignores_repo_venv_and_git_fsmonitor_shims(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)
    venv_python = repo / ".venv/bin/python"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("#!/bin/sh\ntouch venv-executed\nexit 99\n", encoding="utf-8")
    venv_python.chmod(0o755)
    hook = repo / ".git/hooks/fsmonitor-agentops"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\ntouch fsmonitor-executed\necho\n", encoding="utf-8")
    hook.chmod(0o755)
    assert run(["git", "config", "core.fsmonitor", str(hook)], cwd=repo).returncode == 0
    (repo / "Makefile").write_text(
        "PYTHON ?= $(shell test -x .venv/bin/python && echo .venv/bin/python || echo python3)\n"
        "docops-integrity:\n"
        "\t@$(PYTHON) -c \"print('trusted')\"\n"
        "\t@git status --porcelain >/dev/null\n",
        encoding="utf-8",
    )
    report_root = tmp_path / "gate-reports"
    report_root.mkdir(mode=0o700)
    monkeypatch.setenv("PYTHONPATH", "/tmp/poison")
    monkeypatch.setenv("MAKEFILES", "/tmp/poison.mk")
    environment = agentops._admission_gate_environment(
        report_root, repo, "packet"
    )
    gate = agentops.parse_gate(
        {"name": "make", "command": "make docops-integrity"}, 0
    )
    agentops.admit_gate_command(gate)

    result = agentops.run_gate(
        repo,
        gate,
        base_env=environment,
        normalize_positive_executable=True,
    )

    assert result["passed"] is True
    assert not (repo / "venv-executed").exists()
    assert not (repo / "fsmonitor-executed").exists()
    assert "PYTHONPATH" not in environment
    assert "MAKEFILES" not in environment
    assert environment["GIT_CONFIG_VALUE_0"] == "false"
    assert environment["GIT_CONFIG_VALUE_1"] == os.devnull


def test_admission_rejects_repo_venv_before_sibling_git_can_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)
    venv_bin = repo / ".venv/bin"
    venv_bin.mkdir(parents=True)
    runner_python = venv_bin / "python"
    runner_python.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    runner_python.chmod(0o755)
    marker = repo / "venv-git-executed"
    venv_git = venv_bin / "git"
    venv_git.write_text(
        "#!/bin/sh\ntouch venv-git-executed\nexit 0\n",
        encoding="utf-8",
    )
    venv_git.chmod(0o755)
    monkeypatch.setattr(agentops.sys, "executable", str(runner_python))
    report_root = tmp_path / "gate-reports"
    report_root.mkdir(mode=0o700)

    with pytest.raises(agentops.AgentOpsError, match="external to source"):
        agentops._admission_gate_environment(report_root, repo, "packet")
    assert not marker.exists()


def test_admitted_make_rejects_interpreter_make_expansion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)
    (repo / "Makefile").write_text("module-budget:\n\t@true\n", encoding="utf-8")
    injected = repo / "auto-var-injected"
    malicious = repo / "$(shell touch auto-var-injected)" / "python"
    monkeypatch.setattr(agentops.sys, "executable", str(malicious))
    gate = agentops.parse_gate(
        {"name": "make", "command": "make module-budget"}, 0
    )
    agentops.admit_gate_command(gate)

    with pytest.raises(agentops.AgentOpsError, match="Make-safe"):
        agentops.run_gate(
            repo,
            gate,
            base_env={"PATH": agentops._TRUSTED_HOST_PATH},
            normalize_positive_executable=True,
        )
    assert not injected.exists()


def test_negative_control_ignores_ambient_execution_injection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)
    shim_root = tmp_path / "shims"
    shim_root.mkdir()
    shim = shim_root / "python3"
    shim.write_text("#!/bin/sh\ntouch ambient-python-ran\nexit 99\n", encoding="utf-8")
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", str(shim_root))
    monkeypatch.setenv("PYTHONPATH", "/tmp/ambient-pythonpath")
    monkeypatch.setenv("MAKEFILES", "/tmp/ambient.mk")
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    safe = agentops._negative_environment(
        repo, fixture, tmp_path / "jail", {}, jailed=False
    )
    assert safe["PYTHONPATH"] == str(fixture)
    assert str(shim_root) not in safe["PATH"]
    assert "MAKEFILES" not in safe
    for key in ("PATH", "LD_PRELOAD", "DYLD_INSERT_LIBRARIES", "PYTHONHOME", "MAKEFILES"):
        with pytest.raises(agentops.AgentOpsError, match="may not override"):
            agentops._negative_environment(
                repo,
                tmp_path / f"fixture-{key}",
                tmp_path / "jail",
                {key: "attacker"},
                jailed=False,
            )

    external_tmp = tmp_path / "negative-tmp"
    external_tmp.mkdir()
    gate = agentops.parse_gate(
        {
            "name": "negative-python",
            "command": "python3 -c \"raise SystemExit(0)\"",
            "expected_exit": 0,
        },
        0,
        require_expected_exit=True,
    )
    result = agentops.run_negative_control(
        repo, gate, temp_root=external_tmp
    )
    assert result["passed"] is True
    assert not (repo / "ambient-python-ran").exists()


def test_negative_control_rejects_hollow_missing_module_collision(
    tmp_path: Path,
) -> None:
    """A ``python -m <module>`` control whose module is not importable in the
    jail must be rejected, never marked PASSED: the interpreter's bootstrap
    failure exits 1 and would otherwise collide with the expected non-zero
    exit without running the control at all."""
    repo = init_repo(tmp_path)
    external_tmp = tmp_path / "negative-tmp"
    external_tmp.mkdir()
    hollow = agentops.parse_gate(
        {
            "name": "hollow-pytest",
            "command": "python3 -m pytest -q",
            "expected_exit": 1,
        },
        0,
        require_expected_exit=True,
    )
    with pytest.raises(agentops.AgentOpsError, match="not importable in the jail"):
        agentops.run_negative_control(repo, hollow, temp_root=external_tmp)

    # A genuinely-run control with an expected non-zero exit still passes.
    genuine = agentops.parse_gate(
        {
            "name": "genuine-nonzero",
            "command": 'python3 -c "raise SystemExit(1)"',
            "expected_exit": 1,
        },
        0,
        require_expected_exit=True,
    )
    result = agentops.run_negative_control(repo, genuine, temp_root=external_tmp)
    assert result["passed"] is True

    # A stdlib ``-m`` control passes the import probe and runs for real.
    stdlib_control = agentops.parse_gate(
        {
            "name": "stdlib-module",
            "command": "python3 -m calendar 2026 1",
            "expected_exit": 0,
        },
        0,
        require_expected_exit=True,
    )
    result = agentops.run_negative_control(
        repo, stdlib_control, temp_root=external_tmp
    )
    assert result["passed"] is True


def test_negative_control_rejects_unhandled_import_failure_collision(
    tmp_path: Path,
) -> None:
    """A control that dies on an unhandled ``ModuleNotFoundError`` with an
    expected non-zero exit never exercised its detection logic; reject the
    exit-code collision instead of counting it as a caught mutation."""
    repo = init_repo(tmp_path)
    external_tmp = tmp_path / "negative-tmp"
    external_tmp.mkdir()
    gate = agentops.parse_gate(
        {
            "name": "unhandled-import",
            "command": 'python3 -c "import dharma_agentops_absent_module"',
            "expected_exit": 1,
        },
        0,
        require_expected_exit=True,
    )
    with pytest.raises(
        agentops.AgentOpsError, match="setup/import failure"
    ):
        agentops.run_negative_control(repo, gate, temp_root=external_tmp)


@pytest.mark.parametrize("drift", ["branch", "status", "parent"])
def test_preflight_final_revalidation_leaves_no_binding_on_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    repo = init_session_repo(tmp_path)
    payload = seal_packet(session_packet(repo))
    external = write_external_packet(tmp_path, payload)
    report_root = tmp_path / "preflight-reports"
    original_atomic_write_at = agentops._atomic_report_write_at
    mutated = False

    def mutate_after_markdown(
        parent_descriptor: int,
        name: str,
        text: str,
        *,
        display_path: Path,
    ) -> None:
        nonlocal mutated
        original_atomic_write_at(
            parent_descriptor, name, text, display_path=display_path
        )
        if name == "report.md" and not mutated:
            mutated = True
            if drift == "branch":
                result = run(["git", "switch", "-c", "preflight-drift"], cwd=repo)
                assert result.returncode == 0, result.stderr
            else:
                if drift == "status":
                    (repo / "preflight-drift.txt").write_text(
                        "dirty\n", encoding="utf-8"
                    )
                else:
                    moved = report_root / "moved-preflight"
                    display_path.parent.rename(moved)
                    display_path.parent.symlink_to(repo, target_is_directory=True)

    monkeypatch.setattr(agentops, "_atomic_report_write_at", mutate_after_markdown)
    with pytest.raises(
        agentops.AgentOpsError,
        match="branch|clean HEAD|no-follow|report directory",
    ):
        agentops.execute_packet(
            external,
            source_root=repo,
            preflight=True,
            report_root=report_root,
        )
    packet = agentops.load_work_packet(external)
    assert not agentops.preflight_binding_path(report_root, packet).exists()
    assert not (repo / "report.json").exists()


@pytest.mark.parametrize("drift", ["branch", "head"])
def test_closeout_rejects_gate_induced_branch_or_head_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    repo = init_session_repo(tmp_path)
    payload = seal_packet(session_packet(repo))
    external = write_external_packet(tmp_path, payload)
    report_root = tmp_path / "closeout-reports"
    exit_code, report = agentops.execute_packet(
        external,
        source_root=repo,
        preflight=True,
        report_root=report_root,
    )
    assert exit_code == 0 and report is not None
    tracked = tracked_packet_path(repo, payload)
    tracked.parent.mkdir(parents=True)
    tracked.write_bytes(external.read_bytes())
    stage_path(repo, tracked)
    mutated = False

    def mutate_gate(
        _repo: Path,
        gate: agentops.GateSpec,
        **_kwargs: object,
    ) -> dict[str, object]:
        nonlocal mutated
        if not mutated:
            mutated = True
            command = (
                ["git", "switch", "-c", "closeout-drift"]
                if drift == "branch"
                else ["git", "commit", "-m", "gate moved HEAD"]
            )
            result = run(command, cwd=repo)
            assert result.returncode == 0, result.stderr
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

    def pass_control(
        _repo: Path,
        gate: agentops.GateSpec,
        **_kwargs: object,
    ) -> dict[str, object]:
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

    monkeypatch.setattr(agentops, "run_gate", mutate_gate)
    monkeypatch.setattr(agentops, "run_negative_control", pass_control)
    with pytest.raises(agentops.AgentOpsError, match="branch changed|HEAD changed"):
        agentops.execute_packet(
            tracked,
            source_root=repo,
            closeout=True,
            report_root=report_root,
        )
    assert len(list(report_root.rglob("report.json"))) == 1
