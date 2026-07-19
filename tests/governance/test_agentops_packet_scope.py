from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from dharma_swarm.operator_core.onboarding.contract import packet_digest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "governance" / "check_agentops_packet_scope.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "active-track.yml"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_agentops_packet_scope", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


scope_check = _load_module()


def _workflow_job(name: str) -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(
        rf"^  {re.escape(name)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, f"workflow job {name!r} not found in active-track.yml"
    return match.group(0)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _write(repo: Path, relative: str, content: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _tracks(*, status: str = "ACTIVE", owner: str = "operator") -> dict[str, Any]:
    return {
        "active_tracks": [
            {
                "id": "track-a",
                "status": status,
                "owner": owner,
                "owned_surfaces": ["feature/**"],
            }
        ]
    }


def _init_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "agentops@example.invalid")
    _git(repo, "config", "user.name", "AgentOps Test")
    _write(
        repo,
        "docs/governance/ACTIVE_TRACK.yaml",
        json.dumps(_tracks(), indent=2) + "\n",
    )
    _write(
        repo,
        "scripts/runtime/pr_merge_control.py",
        "HOT_PATH_PATTERNS = (\n"
        "    '.github/',\n"
        "    'scripts/governance/',\n"
        "    'scripts/runtime/',\n"
        "    'Makefile',\n"
        ")\n",
    )
    _write(repo, "README.md", "fixture\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture base")
    return repo, _git(repo, "rev-parse", "HEAD")


def _packet(
    *,
    packet_id: str,
    work_packet: str,
    base_ref: str,
    allowed: list[str],
    forbidden: list[str] | None = None,
    owner: str = "operator",
    active_track: str = "track-a",
    before_merge: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": packet_id,
        "base_ref": base_ref,
        "branch": "agent/fixture",
        "worktree": ".",
        "intent": "Prove the exact committed range stays inside declared scope.",
        "allowed_files": allowed,
        "forbidden_files": forbidden or [],
        "gates": [
            {"name": "diff-check", "command": "git diff --check", "expected_exit": 0}
        ],
        "negative_controls": [
            {
                "name": "negative-fixture",
                "command": "git diff --check",
                "expected_exit": 0,
            }
        ],
        "commit": {"allowed": False, "message": "test: packet scope fixture"},
        "approval": {"before_commit": True, "before_merge": before_merge},
        "session_entry": {
            "schema": "dharma_swarm.session_entry.v1",
            "tool_versions": {"git": "2.0"},
            "authority_precedence": [
                "executable",
                "tests",
                "locks",
                "git",
                "owner_files",
            ],
            "work_packet": work_packet,
            "active_track": active_track,
            "owner": owner,
            "collision": {"status": "clear", "checked_at_sha": base_ref, "details": []},
            "interface_mismatches": [],
            "closest_existing_implementation": [
                "scripts/governance/run_agent_work_packet.py"
            ],
            "honest_blockers": [],
            "rollback": "revert the packet-scoped commit",
            "packet_digest": "0" * 64,
        },
    }
    payload["session_entry"]["packet_digest"] = packet_digest(payload)
    return payload


def _commit_event(
    repo: Path,
    *,
    base: str,
    changes: dict[str, str],
    packet_specs: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    for path, content in changes.items():
        _write(repo, path, content)
    packet_paths: list[str] = []
    for spec in packet_specs:
        packet_id = str(spec["packet_id"])
        relative = f"reports/agentops/work_packets/{packet_id}.json"
        allowed = list(spec.get("allowed", []))
        if relative not in allowed:
            allowed.append(relative)
        payload = _packet(
            packet_id=packet_id,
            work_packet=str(spec["work_packet"]),
            base_ref=str(spec.get("base_ref", base)),
            allowed=allowed,
            forbidden=list(spec.get("forbidden", [])),
            owner=str(spec.get("owner", "operator")),
            active_track=str(spec.get("active_track", "track-a")),
            before_merge=bool(spec.get("before_merge", True)),
        )
        if spec.get("break_digest"):
            payload["intent"] = "tampered after sealing"
        _write(repo, relative, json.dumps(payload, indent=2) + "\n")
        packet_paths.append(relative)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "event change")
    return _git(repo, "rev-parse", "HEAD"), packet_paths


def _evaluate(repo: Path, base: str, head: str, event: str = "pull_request") -> dict:
    return scope_check.evaluate(
        repo,
        event_name=event,
        event_base=base,
        event_head=head,
    )


def test_low_risk_event_is_explicitly_not_required(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    head, _ = _commit_event(
        repo,
        base=base,
        changes={"docs/notes.md": "ordinary documentation\n"},
        packet_specs=[],
    )

    report = _evaluate(repo, base, head)

    assert report["status"] == "NOT_REQUIRED"
    assert report["passed"] is True
    assert report["hot_paths"] == []


def test_high_risk_event_without_packet_fails(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    head, _ = _commit_event(
        repo,
        base=base,
        changes={"scripts/governance/risky.py": "RISKY = True\n"},
        packet_specs=[],
    )

    report = _evaluate(repo, base, head)

    assert report["status"] == "FAILED"
    assert any("no Session Entry packet" in error for error in report["errors"])


def test_event_cannot_remove_its_own_base_risk_trigger(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    head, _ = _commit_event(
        repo,
        base=base,
        changes={
            "scripts/runtime/pr_merge_control.py": (
                "HOT_PATH_PATTERNS = ('README.md',)\n"
            )
        },
        packet_specs=[],
    )

    report = _evaluate(repo, base, head)

    assert "scripts/runtime/" in report["hot_patterns"]
    assert report["status"] == "FAILED"


def test_high_risk_pr_with_exact_packet_coverage_passes(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    risky = "scripts/governance/risky.py"
    head, packet_paths = _commit_event(
        repo,
        base=base,
        changes={risky: "RISKY = True\n"},
        packet_specs=[
            {"packet_id": "track-a-WP-1", "work_packet": "WP-1", "allowed": [risky]}
        ],
    )

    report = _evaluate(repo, base, head)

    assert report["status"] == "PASSED", report["errors"]
    assert report["packet_paths"] == packet_paths
    assert report["coverage"][risky] == packet_paths
    assert "not local preflight/closeout" in report["claim"]


def test_pull_request_packet_must_cover_non_hot_companion_changes(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    risky = "scripts/governance/risky.py"
    head, _ = _commit_event(
        repo,
        base=base,
        changes={risky: "RISKY = True\n", "docs/notes.md": "unclaimed\n"},
        packet_specs=[
            {"packet_id": "track-a-WP-1", "work_packet": "WP-1", "allowed": [risky]}
        ],
    )

    report = _evaluate(repo, base, head)

    assert report["status"] == "FAILED"
    assert any("docs/notes.md" in error and "coverage gap" in error for error in report["errors"])


def test_forbidden_overrides_allowed_across_full_event(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    risky = "scripts/governance/risky.py"
    head, _ = _commit_event(
        repo,
        base=base,
        changes={risky: "RISKY = True\n"},
        packet_specs=[
            {
                "packet_id": "track-a-WP-1",
                "work_packet": "WP-1",
                "allowed": [risky],
                "forbidden": [risky],
            }
        ],
    )

    report = _evaluate(repo, base, head)

    assert report["status"] == "FAILED"
    assert any("forbidden paths" in error for error in report["errors"])


def test_digest_owner_and_merge_approval_are_fail_closed(tmp_path: Path) -> None:
    for case in ("digest", "owner", "approval"):
        repo, base = _init_repo(tmp_path / case)
        risky = "scripts/governance/risky.py"
        spec: dict[str, Any] = {
            "packet_id": "track-a-WP-1",
            "work_packet": "WP-1",
            "allowed": [risky],
        }
        if case == "digest":
            spec["break_digest"] = True
        elif case == "owner":
            spec["owner"] = "not-the-owner"
        else:
            spec["before_merge"] = False
        head, _ = _commit_event(
            repo,
            base=base,
            changes={risky: f"CASE = {case!r}\n"},
            packet_specs=[spec],
        )

        report = _evaluate(repo, base, head)

        assert report["status"] == "FAILED", case
        assert report["errors"], case


def test_track_can_close_in_the_same_packet_bound_pr(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    risky = "scripts/governance/risky.py"
    closed_tracks = json.dumps(_tracks(status="SHIPPED"), indent=2) + "\n"
    active_track_path = "docs/governance/ACTIVE_TRACK.yaml"
    head, _ = _commit_event(
        repo,
        base=base,
        changes={risky: "RISKY = True\n", active_track_path: closed_tracks},
        packet_specs=[
            {
                "packet_id": "track-a-WP-1",
                "work_packet": "WP-1",
                "allowed": [risky, active_track_path],
            }
        ],
    )

    report = _evaluate(repo, base, head)

    assert report["status"] == "PASSED", report["errors"]


def test_merge_group_supports_disjoint_packets_and_rejects_overlap(tmp_path: Path) -> None:
    for overlap in (False, True):
        repo, base = _init_repo(tmp_path / str(overlap))
        first = "scripts/governance/first.py"
        second = "scripts/runtime/second.py"
        second_allowed = [second, first] if overlap else [second]
        head, _ = _commit_event(
            repo,
            base=base,
            changes={first: "FIRST = 1\n", second: "SECOND = 2\n"},
            packet_specs=[
                {
                    "packet_id": "track-a-WP-1",
                    "work_packet": "WP-1",
                    "allowed": [first],
                },
                {
                    "packet_id": "track-a-WP-2",
                    "work_packet": "WP-2",
                    "allowed": second_allowed,
                },
            ],
        )

        report = _evaluate(repo, base, head, event="merge_group")

        assert report["passed"] is (not overlap)
        if overlap:
            assert any("coverage overlap" in error for error in report["errors"])


def test_cli_returns_policy_and_configuration_exit_codes(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    head, _ = _commit_event(
        repo,
        base=base,
        changes={"scripts/governance/risky.py": "RISKY = True\n"},
        packet_specs=[],
    )
    failed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--event-name",
            "pull_request",
            "--event-base",
            base,
            "--event-head",
            head,
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    config_error = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--event-name",
            "pull_request",
            "--event-base",
            base,
            "--event-head",
            "0" * 40,
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert failed.returncode == 1
    assert json.loads(failed.stdout)["status"] == "FAILED"
    assert config_error.returncode == 2
    assert json.loads(config_error.stdout)["status"] == "CONFIG_ERROR"


def test_pull_request_uses_advanced_target_base_risk_policy(tmp_path: Path) -> None:
    """A stale feature branch cannot miss a hot path added later on main."""
    repo, fork_point = _init_repo(tmp_path)
    _git(repo, "checkout", "-b", "feature")
    head, _ = _commit_event(
        repo,
        base=fork_point,
        changes={"newly-hot/feature.py": "VALUE = 1\n"},
        packet_specs=[],
    )

    _git(repo, "checkout", "main")
    _write(
        repo,
        "scripts/runtime/pr_merge_control.py",
        "HOT_PATH_PATTERNS = (\n"
        "    '.github/',\n"
        "    'scripts/governance/',\n"
        "    'scripts/runtime/',\n"
        "    'Makefile',\n"
        "    'newly-hot/',\n"
        ")\n",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "advance target risk policy")
    event_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "--detach", head)

    report = _evaluate(repo, event_base, head)

    assert report["diff_base"] == fork_point
    assert "newly-hot/" in report["hot_patterns"]
    assert report["hot_paths"] == ["newly-hot/feature.py"]
    assert report["status"] == "FAILED"
    assert any("no Session Entry packet" in error for error in report["errors"])


def test_agentops_packet_scope_workflow_has_truthful_bootstrap_and_fail_closed_enforcement() -> None:
    job = _workflow_job("agentops-packet-scope")

    assert "name: AgentOps packet scope" in job
    assert "github.event_name == 'pull_request'" in job
    assert "github.event_name == 'merge_group'" in job
    assert (
        "ref: ${{ github.event.pull_request.head.sha || "
        "github.event.merge_group.head_sha }}"
    ) in job
    assert "fetch-depth: 0" in job
    assert "github.sha" not in job
    assert (
        "EVENT_BASE: ${{ github.event.pull_request.base.sha || "
        "github.event.merge_group.base_sha }}"
    ) in job
    assert (
        "EVENT_HEAD: ${{ github.event.pull_request.head.sha || "
        "github.event.merge_group.head_sha }}"
    ) in job

    assert 'git ls-tree -r --name-only "${EVENT_BASE}" -- "${CHECKER_PATH}"' in job
    assert 'git cat-file -e "${EVENT_BASE}:${CHECKER_PATH}"' in job
    # Enforcement CODE comes from the trusted event base (script executed from
    # the base worktree, first-party imports from the base-installed package,
    # -I blocking cwd/script-dir shadowing) while it RUNS against the head
    # checkout, whose git HEAD equals the declared event head — the checker's
    # own evaluate() asserts exactly that and takes repo_root from cwd. The
    # old base-cwd invocation made base != head an unconditional CONFIG_ERROR
    # on every enforced PR and must never return.
    assert 'git archive --format=tar "${EVENT_BASE}"' in job
    assert "git archive --format=tar HEAD" not in job
    assert 'git worktree add --detach "${trusted_base}" "${EVENT_BASE}"' in job
    assert '(python3 -I "${trusted_base}/${CHECKER_PATH}" \\' in job
    assert 'cd "${trusted_base}"' not in job
    assert '--event-name "${EVENT_NAME}"' in job
    assert '--event-base "${EVENT_BASE}"' in job
    assert '--event-head "${EVENT_HEAD}")' in job
    assert '| tee "${checker_report}"' in job
    assert '"status": "BOOTSTRAP_NOT_ENFORCED"' in job
    assert '"enforced": False' in job
    assert "bootstrap provenance only" in job
    assert "no packet-scope, packet-validity" in job
    assert job.count("if: steps.packet-scope-boundary.outputs.enforce == 'true'") == 3

    external_report = (
        "${{ runner.temp }}/dharma-agentops/packet-scope/report.json"
    )
    assert job.count(external_report) == 3
    assert "reports/agentops/packet_scope.json" not in job
    assert "name: agentops-packet-scope-evidence" in job
    assert "if: always()" in job
    assert "if-no-files-found: error" in job
    assert "continue-on-error" not in job
    assert "|| true" not in job


def test_pull_request_base_ref_may_be_ancestor_of_rebased_merge_base(
    tmp_path: Path,
) -> None:
    """A PR brought up to date with an advanced main keeps its original
    provenance floor: base_ref need only be an ancestor of the live merge base,
    not byte-equal to it. This ends the per-merge packet re-bind churn."""
    repo, fork_point = _init_repo(tmp_path)
    # main advances past the packet's authored base with an unrelated commit.
    _write(repo, "docs/advance.md", "main moved forward\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "advance main")
    advanced_main = _git(repo, "rev-parse", "HEAD")
    # The PR is brought up to date so its parent is the advanced main, while the
    # packet still declares the older fork point as base_ref (stale but an
    # ancestor of the live merge base).
    _git(repo, "checkout", "-b", "feature", advanced_main)
    risky = "scripts/governance/risky.py"
    head, packet_paths = _commit_event(
        repo,
        base=advanced_main,
        changes={risky: "RISKY = True\n"},
        packet_specs=[
            {
                "packet_id": "track-a-WP-1",
                "work_packet": "WP-1",
                "allowed": [risky],
                "base_ref": fork_point,
            }
        ],
    )
    _git(repo, "checkout", "--detach", head)

    report = _evaluate(repo, advanced_main, head)

    assert report["diff_base"] == advanced_main
    assert report["status"] == "PASSED", report["errors"]
    assert report["coverage"][risky] == packet_paths


def test_pull_request_base_ref_off_ancestry_is_rejected(tmp_path: Path) -> None:
    """The ancestor floor still binds: a base_ref that is not an ancestor of the
    live merge base is rejected. The relaxation is a floor, not a removed check."""
    repo, fork_point = _init_repo(tmp_path)
    # A divergent commit that never enters the PR's history.
    _git(repo, "checkout", "-b", "divergent", fork_point)
    _write(repo, "docs/divergent.md", "off the ancestry line\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "divergent commit")
    off_ancestry = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "main")
    risky = "scripts/governance/risky.py"
    head, _ = _commit_event(
        repo,
        base=fork_point,
        changes={risky: "RISKY = True\n"},
        packet_specs=[
            {
                "packet_id": "track-a-WP-1",
                "work_packet": "WP-1",
                "allowed": [risky],
                "base_ref": off_ancestry,
            }
        ],
    )

    report = _evaluate(repo, fork_point, head)

    assert report["status"] == "FAILED"
    assert any(
        "not an ancestor of pull-request merge base" in error
        for error in report["errors"]
    )


def test_unrelated_new_sibling_surface_does_not_force_packet_rebind(
    tmp_path: Path,
) -> None:
    """A sibling track claiming a surface this PR never touches — added to the
    portfolio after the packet's base_ref — must not invalidate the packet.
    forbidden_files completeness is owed only for sibling patterns that match a
    path this PR actually changes; the collision check grades the real changed
    paths against live sibling ownership regardless of the packet's declaration,
    so untouched surfaces add no safety and forced a full packet re-bind on
    every unrelated portfolio change."""
    repo, fork_point = _init_repo(tmp_path)
    active_track_path = "docs/governance/ACTIVE_TRACK.yaml"
    # main advances: a new sibling claims terminal/**, which this PR never touches.
    two_tracks = {
        "active_tracks": [
            {"id": "track-a", "status": "ACTIVE", "owner": "operator",
             "owned_surfaces": ["feature/**"]},
            {"id": "track-s", "status": "ACTIVE", "owner": "sibling-owner",
             "owned_surfaces": ["terminal/**"]},
        ]
    }
    _write(repo, active_track_path, json.dumps(two_tracks, indent=2) + "\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "sibling claims unrelated surface")
    advanced_main = _git(repo, "rev-parse", "HEAD")
    # The PR is up to date with advanced_main; its packet was bound at the fork
    # point when track-s did not exist, so forbidden_files omits terminal/**.
    _git(repo, "checkout", "-b", "feature", advanced_main)
    risky = "scripts/governance/risky.py"
    head, packet_paths = _commit_event(
        repo,
        base=advanced_main,
        changes={risky: "RISKY = True\n"},
        packet_specs=[
            {
                "packet_id": "track-a-WP-1",
                "work_packet": "WP-1",
                "allowed": [risky],
                "base_ref": fork_point,
            }
        ],
    )
    _git(repo, "checkout", "--detach", head)

    report = _evaluate(repo, advanced_main, head)

    assert report["status"] == "PASSED", report["errors"]
    assert report["coverage"][risky] == packet_paths


def test_touched_sibling_surface_still_requires_forbidden_declaration(
    tmp_path: Path,
) -> None:
    """The completeness relaxation is a narrowing, not a removal: a sibling
    pattern that matches a path this PR changes must still appear in
    forbidden_files, and omitting it is an error alongside the ownership
    collision."""
    repo, base = _init_repo(tmp_path)
    active_track_path = "docs/governance/ACTIVE_TRACK.yaml"
    two_tracks = {
        "active_tracks": [
            {"id": "track-a", "status": "ACTIVE", "owner": "operator",
             "owned_surfaces": ["feature/**"]},
            {"id": "track-s", "status": "ACTIVE", "owner": "sibling-owner",
             "owned_surfaces": ["scripts/governance/**"]},
        ]
    }
    _write(repo, active_track_path, json.dumps(two_tracks, indent=2) + "\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "sibling claims scripts/governance")
    sibling_base = _git(repo, "rev-parse", "HEAD")
    risky = "scripts/governance/risky.py"
    head, _ = _commit_event(
        repo,
        base=sibling_base,
        changes={risky: "RISKY = True\n"},
        packet_specs=[
            {"packet_id": "track-a-WP-1", "work_packet": "WP-1", "allowed": [risky]}
        ],
    )

    report = _evaluate(repo, sibling_base, head)

    assert report["status"] == "FAILED"
    assert any(
        "omit sibling surfaces" in error and "scripts/governance/**" in error
        for error in report["errors"]
    )
    assert any("collision" in error for error in report["errors"])


def test_sibling_ownership_read_at_live_merge_base_not_stale_base_ref(
    tmp_path: Path,
) -> None:
    """With an ancestor base_ref, sibling ownership must be read at the live
    merge base. A sibling surface added after base_ref (present at the merge
    base) that this PR both edits and closes must still be caught — otherwise a
    stale base_ref launders an ownership collision (P1 review, PR #1046)."""
    repo, fork_point = _init_repo(tmp_path)
    active_track_path = "docs/governance/ACTIVE_TRACK.yaml"
    # main advances: a sibling track claims scripts/governance/** after the fork.
    two_tracks = {
        "active_tracks": [
            {"id": "track-a", "status": "ACTIVE", "owner": "operator",
             "owned_surfaces": ["feature/**"]},
            {"id": "track-s", "status": "ACTIVE", "owner": "sibling-owner",
             "owned_surfaces": ["scripts/governance/**"]},
        ]
    }
    _write(repo, active_track_path, json.dumps(two_tracks, indent=2) + "\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "sibling claims scripts/governance")
    advanced_main = _git(repo, "rev-parse", "HEAD")
    # The PR is up to date with advanced_main, edits the sibling-owned path, AND
    # closes the sibling in the same commit — while pinning the older base_ref.
    _git(repo, "checkout", "-b", "feature", advanced_main)
    only_track_a = {
        "active_tracks": [
            {"id": "track-a", "status": "ACTIVE", "owner": "operator",
             "owned_surfaces": ["feature/**"]},
        ]
    }
    risky = "scripts/governance/risky.py"
    head, _ = _commit_event(
        repo,
        base=advanced_main,
        changes={
            risky: "RISKY = True\n",
            active_track_path: json.dumps(only_track_a, indent=2) + "\n",
        },
        packet_specs=[
            {
                "packet_id": "track-a-WP-1",
                "work_packet": "WP-1",
                "allowed": [risky, active_track_path],
                "base_ref": fork_point,
            }
        ],
    )
    _git(repo, "checkout", "--detach", head)

    report = _evaluate(repo, advanced_main, head)

    assert report["status"] == "FAILED", report["errors"]
    assert any(
        "scripts/governance" in error
        and ("collision" in error or "sibling surfaces" in error)
        for error in report["errors"]
    )
