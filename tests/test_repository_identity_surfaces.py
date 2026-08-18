from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLISH_SCRIPT = REPO_ROOT / "scripts/publish_canonical.sh"
CANONICAL_REPOSITORY = "AIKAGRYA/dharma_swarm"
CANONICAL_URL = f"https://github.com/{CANONICAL_REPOSITORY}.git"
EXPECTED_REPOSITORY_ID = "1176966970"
ACTIVE_OPERATIONAL_SURFACES = (
    "DEVIN.md",
    "dharma_swarm/ginko_agents.py",
    "dharma_swarm/guardian_crew.py",
    "dharma_swarm/orchestrate_live.py",
    "docs/governance/CI_GATES.md",
    "docs/governance/PR_QUALITY_GATES.md",
    "docs/ops/A2A_NATS_CENTRAL_INDEX.md",
    "docs/ops/DEVIN_NATS_PR_JANITOR_PLAYBOOK.md",
    "docs/ops/OZ_INTEGRATION.md",
    "docs/ops/RUNBOOK.md",
    "scripts/close_duplicate_guardian_issues.py",
    "scripts/governance/check_track_status.py",
    "scripts/governance/ci_parity_manifest.json",
    "scripts/governance/pr_ci_health.py",
    "scripts/governance/render_parallel_lane_map.py",
    "scripts/ops/vps_cloud_init.yaml",
    "scripts/runtime/pr_convergence_policy.py",
    "scripts/runtime/reviewer_quorum_repair.py",
)
FORBIDDEN_REPOSITORY_SLUGS = (
    "AmitabhainArunachala/dharma_swarm",
    "shakti-saraswati/dharma_swarm",
)
HISTORICAL_PR_PROVENANCE_PREFIX = (
    "- PR: https://github.com/AmitabhainArunachala/dharma_swarm/pull/"
)


FAKE_COMMAND = r"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

command = Path(sys.argv[0]).name
args = sys.argv[1:]
with Path(os.environ["FAKE_CALL_LOG"]).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({"command": command, "args": args}) + "\n")

if command == "gh":
    if args == ["auth", "status", "--hostname", "github.com"]:
        raise SystemExit(int(os.environ["FAKE_GH_AUTH_EXIT"]))
    if args and args[0] == "api":
        if "repos/AIKAGRYA/dharma_swarm" not in args:
            raise SystemExit(91)
        api_exit = int(os.environ["FAKE_GH_API_EXIT"])
        if api_exit:
            raise SystemExit(api_exit)
        sys.stdout.write(os.environ["FAKE_GH_METADATA"] + "\n")
        raise SystemExit(0)
    raise SystemExit(92)

if command != "git":
    raise SystemExit(93)

if args == ["rev-parse", "--show-toplevel"]:
    sys.stdout.write(os.environ["FAKE_GIT_TOPLEVEL"] + "\n")
    raise SystemExit(0)

origin_path = Path(os.environ["FAKE_ORIGIN_STATE"])
origin = json.loads(origin_path.read_text(encoding="utf-8"))
if args == ["config", "--local", "--get", "remote.origin.url"]:
    if not origin["present"]:
        raise SystemExit(1)
    sys.stdout.write(origin["url"] + "\n")
    raise SystemExit(0)

if len(args) == 4 and args[:3] == ["remote", "set-url", "origin"]:
    if not origin["present"]:
        raise SystemExit(2)
    origin_path.write_text(
        json.dumps({"present": True, "url": args[3]}), encoding="utf-8"
    )
    raise SystemExit(0)

if len(args) == 4 and args[:3] == ["remote", "add", "origin"]:
    if origin["present"]:
        raise SystemExit(3)
    origin_path.write_text(
        json.dumps({"present": True, "url": args[3]}), encoding="utf-8"
    )
    raise SystemExit(0)

if len(args) == 4 and args[:2] == ["ls-remote", "--exit-code"]:
    remote_exit = int(os.environ["FAKE_LS_REMOTE_EXIT"])
    if remote_exit:
        raise SystemExit(remote_exit)
    sys.stdout.write(os.environ["FAKE_LS_REMOTE_OUTPUT"] + "\n")
    raise SystemExit(0)

raise SystemExit(94)
"""


@dataclass(frozen=True)
class GuardRun:
    result: subprocess.CompletedProcess[str]
    calls: tuple[dict[str, object], ...]
    origin: dict[str, object]


def _metadata(
    *,
    full_name: str = CANONICAL_REPOSITORY,
    repository_id: str = EXPECTED_REPOSITORY_ID,
    private: str = "false",
    visibility: str = "public",
    default_branch: str = "main",
) -> str:
    return "\t".join((full_name, repository_id, private, visibility, default_branch))


def _run_guard(
    tmp_path: Path,
    *,
    metadata: str | None = None,
    raw_origin: str | None = CANONICAL_URL,
    repair_origin: bool = False,
    auth_exit: int = 0,
    api_exit: int = 0,
    ls_remote_exit: int = 0,
    ls_remote_output: str | None = None,
) -> GuardRun:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    for command in ("gh", "git"):
        command_path = bin_dir / command
        command_path.write_text(FAKE_COMMAND, encoding="utf-8")
        command_path.chmod(0o755)

    call_log = tmp_path / "calls.jsonl"
    origin_state = tmp_path / "origin.json"
    origin_state.write_text(
        json.dumps({"present": raw_origin is not None, "url": raw_origin or ""}),
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{bin_dir}{os.pathsep}{environment['PATH']}",
            "FAKE_CALL_LOG": str(call_log),
            "FAKE_GH_AUTH_EXIT": str(auth_exit),
            "FAKE_GH_API_EXIT": str(api_exit),
            "FAKE_GH_METADATA": metadata or _metadata(),
            "FAKE_GIT_TOPLEVEL": str(REPO_ROOT),
            "FAKE_ORIGIN_STATE": str(origin_state),
            "FAKE_LS_REMOTE_EXIT": str(ls_remote_exit),
            "FAKE_LS_REMOTE_OUTPUT": ls_remote_output or f"{'a' * 40}\trefs/heads/main",
        }
    )
    arguments = ["bash", str(PUBLISH_SCRIPT)]
    if repair_origin:
        arguments.append("--repair-origin")
    result = subprocess.run(
        arguments,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    calls = tuple(
        json.loads(line) for line in call_log.read_text(encoding="utf-8").splitlines()
    )
    return GuardRun(
        result=result,
        calls=calls,
        origin=json.loads(origin_state.read_text(encoding="utf-8")),
    )


def _calls_for(run: GuardRun, command: str) -> list[list[str]]:
    return [entry["args"] for entry in run.calls if entry["command"] == command]


@pytest.mark.parametrize(
    "relative_path", (*ACTIVE_OPERATIONAL_SURFACES, "scripts/publish_canonical.sh")
)
def test_active_repository_identity_surfaces_exclude_operational_legacy_slugs(
    relative_path: str,
) -> None:
    path = REPO_ROOT / relative_path
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        for forbidden_slug in FORBIDDEN_REPOSITORY_SLUGS:
            if forbidden_slug not in line:
                continue
            historical_pr_suffix = line.removeprefix(HISTORICAL_PR_PROVENANCE_PREFIX)
            is_allowlisted_provenance = (
                relative_path == "docs/ops/A2A_NATS_CENTRAL_INDEX.md"
                and forbidden_slug == FORBIDDEN_REPOSITORY_SLUGS[0]
                and line.startswith(HISTORICAL_PR_PROVENANCE_PREFIX)
                and historical_pr_suffix.isdigit()
            )
            assert is_allowlisted_provenance, (
                f"{relative_path}:{line_number} targets legacy repository "
                f"{forbidden_slug}"
            )


def test_active_surfaces_never_execute_gh_against_a_legacy_repository() -> None:
    for relative_path in ACTIVE_OPERATIONAL_SURFACES:
        path = REPO_ROOT / relative_path
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if "gh " not in line or "--repo" not in line:
                continue
            for forbidden_slug in FORBIDDEN_REPOSITORY_SLUGS:
                assert forbidden_slug not in line, (
                    f"{relative_path}:{line_number} executes gh against "
                    f"{forbidden_slug}"
                )


def test_publish_guard_is_nonpublishing_and_reads_raw_origin_config() -> None:
    text = PUBLISH_SCRIPT.read_text(encoding="utf-8")
    assert "gh repo create" not in text
    assert "git push" not in text
    assert "git remote get-url" not in text
    assert "git config --local --get remote.origin.url" in text
    assert f'EXPECTED_REPOSITORY_ID="{EXPECTED_REPOSITORY_ID}"' in text
    assert f'CANONICAL_REPOSITORY="{CANONICAL_REPOSITORY}"' in text
    assert "git ls-remote --exit-code" in text


def test_publish_guard_accepts_only_verified_canonical_identity(tmp_path: Path) -> None:
    run = _run_guard(tmp_path)

    assert run.result.returncode == 0, run.result.stderr
    assert "Canonical repository identity verified" in run.result.stdout
    git_calls = _calls_for(run, "git")
    assert ["config", "--local", "--get", "remote.origin.url"] in git_calls
    assert [
        "ls-remote",
        "--exit-code",
        CANONICAL_URL,
        "refs/heads/main",
    ] in git_calls
    assert not any(args[:2] == ["remote", "set-url"] for args in git_calls)
    assert not any(args[:2] == ["remote", "add"] for args in git_calls)
    assert run.origin == {"present": True, "url": CANONICAL_URL}


@pytest.mark.parametrize(
    ("metadata", "diagnostic"),
    (
        (
            _metadata(full_name="AmitabhainArunachala/dharma_swarm"),
            "Live full_name mismatch",
        ),
        (_metadata(repository_id="1"), "Live repository ID mismatch"),
        (_metadata(private="true"), "Live repository is not public"),
        (_metadata(visibility="private"), "Live visibility mismatch"),
        (_metadata(default_branch="develop"), "Live default branch mismatch"),
    ),
)
def test_publish_guard_rejects_each_live_identity_mismatch_before_local_mutation(
    tmp_path: Path,
    metadata: str,
    diagnostic: str,
) -> None:
    run = _run_guard(tmp_path, metadata=metadata, repair_origin=True)

    assert run.result.returncode != 0
    assert diagnostic in run.result.stderr
    git_calls = _calls_for(run, "git")
    assert not any(args and args[0] == "remote" for args in git_calls)
    assert not any(args and args[0] == "ls-remote" for args in git_calls)
    assert run.origin == {"present": True, "url": CANONICAL_URL}


def test_publish_guard_reports_exact_repair_without_opt_in(tmp_path: Path) -> None:
    old_url = "https://github.com/shakti-saraswati/dharma_swarm.git"
    run = _run_guard(tmp_path, raw_origin=old_url)

    assert run.result.returncode != 0
    assert f"git remote set-url origin {CANONICAL_URL}" in run.result.stderr
    git_calls = _calls_for(run, "git")
    assert ["remote", "set-url", "origin", CANONICAL_URL] not in git_calls
    assert not any(args and args[0] == "ls-remote" for args in git_calls)
    assert run.origin == {"present": True, "url": old_url}


def test_publish_guard_repairs_origin_only_with_explicit_opt_in(tmp_path: Path) -> None:
    run = _run_guard(
        tmp_path,
        raw_origin="git@github.com:wrong-owner/dharma_swarm.git",
        repair_origin=True,
    )

    assert run.result.returncode == 0, run.result.stderr
    assert ["remote", "set-url", "origin", CANONICAL_URL] in _calls_for(run, "git")
    assert run.origin == {"present": True, "url": CANONICAL_URL}


def test_publish_guard_requires_explicit_opt_in_to_add_missing_origin(
    tmp_path: Path,
) -> None:
    refused = _run_guard(tmp_path / "refused", raw_origin=None)
    assert refused.result.returncode != 0
    assert f"git remote add origin {CANONICAL_URL}" in refused.result.stderr
    assert refused.origin == {"present": False, "url": ""}

    repaired = _run_guard(tmp_path / "repaired", raw_origin=None, repair_origin=True)
    assert repaired.result.returncode == 0, repaired.result.stderr
    assert ["remote", "add", "origin", CANONICAL_URL] in _calls_for(repaired, "git")
    assert repaired.origin == {"present": True, "url": CANONICAL_URL}


@pytest.mark.parametrize(
    ("ls_remote_exit", "ls_remote_output"),
    (
        (2, f"{'a' * 40}\trefs/heads/main"),
        (0, "not-an-object-id\trefs/heads/main"),
        (0, f"{'a' * 40}\trefs/heads/not-main"),
        (0, f"{'a' * 40}\trefs/heads/main\n{'b' * 40}\trefs/heads/main"),
    ),
)
def test_publish_guard_rejects_unverified_or_ambiguous_remote_main(
    tmp_path: Path,
    ls_remote_exit: int,
    ls_remote_output: str,
) -> None:
    run = _run_guard(
        tmp_path,
        ls_remote_exit=ls_remote_exit,
        ls_remote_output=ls_remote_output,
    )

    assert run.result.returncode != 0
    assert "Remote main" in run.result.stderr or "refs/heads/main" in run.result.stderr
