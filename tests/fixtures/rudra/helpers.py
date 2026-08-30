"""Shared RUDRA test fixture builders.

Every fixture is offline: a throwaway Git repository, the real local
interpreter/toolchain bound by digest, and a generated mission contract whose
base, executable, and lock bindings are computed fresh per test (copied
placeholders would be a hard admission failure by design).
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import yaml

GIT = "/usr/bin/git"
CANONICAL_REMOTE = "https://github.com/AIKAGRYA/dharma_swarm.git"

BASE_TARGET = "def answer():\n    return 0\n"
FIXED_TARGET = "def answer():\n    return 42\n"
BASE_TEST = (
    "from src.target import answer\n\n\n"
    "def test_answer():\n"
    "    assert answer() == 42\n"
)
LOCK_CONTENT = "rudra-test-lock v1\n"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def version_of(path: str) -> str:
    proc = subprocess.run(
        [path, "--version"], capture_output=True, text=True, timeout=15
    )
    return (proc.stdout or proc.stderr).strip()


def git(repo: Path, *args: str) -> str:
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(repo),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_AUTHOR_NAME": "rudra-test",
        "GIT_AUTHOR_EMAIL": "rudra@test",
        "GIT_COMMITTER_NAME": "rudra-test",
        "GIT_COMMITTER_EMAIL": "rudra@test",
    }
    proc = subprocess.run(
        [GIT, *args], cwd=repo, env=env, capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, f"git {args}: {proc.stderr}"
    return proc.stdout


def make_base_repo(tmp_path: Path, *, fixed: bool = False) -> tuple[Path, str]:
    """A clean repository whose gate is red at base (green when fixed=True)."""
    repo = tmp_path / "base"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "remote.origin.url", CANONICAL_REMOTE)
    (repo / "src" / "__init__.py").write_text("")
    (repo / "src" / "target.py").write_text(FIXED_TARGET if fixed else BASE_TARGET)
    (repo / "tests" / "__init__.py").write_text("")
    (repo / "tests" / "test_target.py").write_text(BASE_TEST)
    (repo / "uv.lock").write_text(LOCK_CONTENT)
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    base_sha = git(repo, "rev-parse", "HEAD").strip()
    return repo, base_sha


def make_mission_yaml(
    repo: Path,
    base_sha: str,
    *,
    mission_id: str = "smoke-mission",
    python_path: str | None = None,
    junit: bool = False,
    extra_verifier: dict | None = None,
    overrides: dict | None = None,
) -> str:
    """A normative-shaped contract with freshly computed bindings."""
    python_path = python_path or sys.executable
    python_binding = {
        "path": python_path,
        "sha256": sha256_file(Path(python_path)),
        "version": version_of(python_path),
    }
    check_argv = [
        python_path,
        "-c",
        "from pathlib import Path; import sys; "
        "ok = Path('src/target.py').read_text().strip().endswith('return 42'); "
        "print('RUDRA_OK' if ok else 'RUDRA_RED'); sys.exit(0 if ok else 1)",
    ]
    commands: list[dict] = [
        {
            "id": "target-fixed",
            "argv": check_argv,
            "timeout_seconds": 60,
            "expect": {"exit_code": 0, "stdout_must_match": ["^RUDRA_OK\\s*$"]},
        }
    ]
    if junit:
        commands.append(
            {
                "id": "pytest-node",
                "argv": [
                    python_path, "-m", "pytest", "-q",
                    "-p", "no:cacheprovider",
                    "--junitxml=${RUDRA_ARTIFACT_DIR}/t.junit.xml",
                    "tests/test_target.py",
                ],
                "timeout_seconds": 180,
                "expect": {
                    "exit_code": 0,
                    "structured_result": {
                        "kind": "pytest_junit",
                        "artifact": "t.junit.xml",
                        "required_testcases": ["tests.test_target::test_answer"],
                        "require_counts": {
                            "passed": 1, "skipped": 0, "failures": 0, "errors": 0
                        },
                    },
                },
            }
        )
    if extra_verifier is not None:
        commands.append(extra_verifier)
    mission: dict = {
        "schema_version": "rudra.mission.v0",
        "mission_id": mission_id,
        "objective": "Make src/target.py answer() return 42. Do not edit tests.",
        "repository": {
            "canonical_remote": CANONICAL_REMOTE,
            "base_sha": base_sha,
        },
        "scope": {
            "required_changed_paths": ["src/target.py"],
            "allowed_changed_paths": ["src/target.py"],
            "forbidden_changed_paths": ["tests/**", ".github/**", "uv.lock"],
            "forbidden_diff_literals": ["pytest.skip"],
            "reject_symlinks": True,
            "max_changed_files": 3,
            "max_diff_bytes": 50000,
        },
        "toolchain": {
            "lockfile": {"path": "uv.lock", "sha256": sha256_file(repo / "uv.lock")},
            "environment_manifest": {
                "kind": "installed-environment-v1",
                "covers": ["resolved_interpreter"],
                "sha256": hashlib.sha256(b"rudra-test-env-manifest").hexdigest(),
            },
            "executables": {"python": python_binding},
            "require_first_party_imports_from_workcell": True,
            "allowed_pytest_plugins": [],
        },
        "acceptance": {
            "cwd": ".",
            "commands": commands,
            "environment": {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        },
        "executor": {
            "driver": "codex_app_server_stdio",
            "binary": dict(python_binding),  # copy: YAML anchors are rejected
            "protocol_schema_sha256": hashlib.sha256(b"rudra-test-schema").hexdigest(),
            "model": "stub-model",
            "model_provider": "stub",
            "reasoning_effort": "low",
            "service_tier": "stub",
        },
        "containment": {
            "risk_class": "trusted_operator_coding",
            "sandbox": "workspace-write",
            "writable_roots": ["WORKCELL_ONLY"],
            "provider_egress": "configured_model_service_only",
            "tool_network_access": False,
            "approval_policy": "never",
            "allow_mcp": False,
            "allow_plugins": False,
            "allow_external_effects": False,
            "allow_dependency_install": False,
        },
        "budgets": {
            "max_turns": 5,
            "max_total_tokens": 100000,
            "max_tokens_per_turn": 20000,
            "max_wall_seconds": 900,
            "max_turn_seconds": 300,
            "max_verifier_seconds": 300,
            "max_cpu_seconds": 600,
            "max_memory_bytes": 4294967296,
            "max_processes": 32,
            "max_disk_bytes": 1073741824,
            "max_captured_output_bytes": 1048576,
            "max_context_resets": 1,
            "max_consecutive_no_delta_turns": 2,
        },
        "recovery": {
            "resume_policy": "prefer_same_thread",
            "resume_failure": "one_verified_compact_handoff",
            "max_fresh_thread_handoffs": 1,
            "unresolved_turn_token_charge": "max_tokens_per_turn",
            "rpc_retry_policy": {
                "read_only_before_response": 2,
                "thread_start_after_any_byte": "reconcile_only",
                "turn_start_after_any_byte": "reconcile_only",
            },
        },
        "result": {
            "require_baseline_red": True,
            "require_nonempty_diff": True,
            "require_local_candidate_commit": True,
            "require_final_clean_worktree": True,
            "allow_push": False,
            "allow_merge": False,
        },
    }
    if overrides:
        for dotted, value in overrides.items():
            node = mission
            parts = dotted.split(".")
            for part in parts[:-1]:
                node = node[part]
            node[parts[-1]] = value
    return yaml.safe_dump(mission, sort_keys=False)


def write_mission(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "mission.yaml"
    path.write_text(text)
    return path
