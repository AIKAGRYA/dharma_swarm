"""WP-O4: CI/local admission parity for the onboarding door.

Covers O4-B5 (CI calls the same command with no weaker flags and no
continue-on-error) and O4-B10 (PR and merge-group event ranges are bound to
their complete discovered packet set). The workflow text is the contract
surface: these tests pin the invariants a drive-by workflow edit would
silently break.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = REPO_ROOT / "Makefile"
WORKFLOW = REPO_ROOT / ".github/workflows/active-track.yml"
CI_TRUTH_CONTRACT = REPO_ROOT / "docs/governance/CI_TRUTH_CONTRACT.json"
RUNNER = REPO_ROOT / "scripts/governance/run_agent_work_packet.py"
TRACK_PATH = "docs/governance/ACTIVE_TRACK.yaml"
TRACK_ID = "onboard-one-door-2026-07"
DEFAULT_OWNER = "@AmitabhainArunachala"
PACKET_SURFACE = "reports/agentops/work_packets/onboard-one-door-WP-O*.json"

_SPEC = importlib.util.spec_from_file_location("onboarding_ci_agentops", RUNNER)
assert _SPEC is not None and _SPEC.loader is not None
agentops = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = agentops
_SPEC.loader.exec_module(agentops)


def _job_block(name: str) -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(
        rf"^  {re.escape(name)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, f"workflow job {name!r} not found in active-track.yml"
    return match.group(0)


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        assert key not in result, f"duplicate CI truth contract key: {key}"
        result[key] = value
    return result


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout.strip()


def _new_event_repo(root: Path, name: str) -> tuple[Path, str, str]:
    """Create a two-commit baseline so tests have a valid wrong ancestor."""
    repo = root / name
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "ci-binding@example.invalid")
    _git(repo, "config", "user.name", "CI Binding Test")

    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "fixture bootstrap")
    bootstrap = _git(repo, "rev-parse", "HEAD")

    track = repo / "docs/governance/ACTIVE_TRACK.yaml"
    track.parent.mkdir(parents=True)
    track.write_text(
        json.dumps(
            {
                "active_tracks": [
                    {
                        "id": "onboard-one-door-2026-07",
                        "status": "ACTIVE",
                        "owner": "@AmitabhainArunachala",
                        "owned_surfaces": [
                            "owned/**",
                            "reports/agentops/work_packets/"
                            "onboard-one-door-WP-O*.json",
                        ],
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    owned = repo / "owned"
    owned.mkdir()
    for filename in ("a.txt", "b.txt", "shared.txt"):
        (owned / filename).write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture event base")
    return repo, bootstrap, _git(repo, "rev-parse", "HEAD")


def _track_row(
    *,
    track_id: str = TRACK_ID,
    status: str = "ACTIVE",
    owner: str = DEFAULT_OWNER,
    surfaces: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": track_id,
        "status": status,
        "owner": owner,
        "owned_surfaces": surfaces or ["owned/**", PACKET_SURFACE],
    }


def _tracks_text(*rows: dict[str, object]) -> str:
    return json.dumps({"active_tracks": list(rows)}, indent=2) + "\n"


def _write_ci_packet(
    repo: Path,
    *,
    work_packet: str,
    base_ref: str,
    allowed_files: list[str],
    owner: str = DEFAULT_OWNER,
    forbidden_files: list[str] | None = None,
    include_own_path: bool = True,
    worktree: str = ".",
) -> Path:
    packet_id = f"onboard-one-door-{work_packet}"
    relative = f"reports/agentops/work_packets/{packet_id}.json"
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    packet_allowed = list(allowed_files)
    if include_own_path and relative not in packet_allowed:
        packet_allowed.append(relative)
    payload: dict[str, object] = {
        "id": packet_id,
        "base_ref": base_ref,
        "branch": "ci-binding-fixture",
        "worktree": worktree,
        "intent": "Prove CI event packet discovery and range binding.",
        "allowed_files": packet_allowed,
        "forbidden_files": list(forbidden_files or []),
        "gates": [{"name": "read-only", "command": "git status --porcelain"}],
        "negative_controls": [
            {
                "name": "fixture-control",
                "command": 'python3 -c "raise SystemExit(0)"',
                "expected_exit": 0,
                "env": {},
            }
        ],
        "commit": {"allowed": False, "message": "test: CI packet fixture"},
        "approval": {"before_commit": True, "before_merge": True},
        "session_entry": {
            "schema": "dharma_swarm.session_entry.v1",
            "tool_versions": {"python": "fixture"},
            "authority_precedence": [
                "executable",
                "tests",
                "locks",
                "git",
                "owner_files",
            ],
            "work_packet": work_packet,
            "active_track": "onboard-one-door-2026-07",
            "owner": owner,
            "collision": {
                "status": "clear",
                "checked_at_sha": base_ref,
                "details": [],
            },
            "interface_mismatches": [],
            "closest_existing_implementation": ["README.md"],
            "honest_blockers": [],
            "rollback": "drop the CI binding fixture",
            "packet_digest": "0" * 64,
        },
    }
    entry = payload["session_entry"]
    assert isinstance(entry, dict)
    entry["packet_digest"] = agentops.packet_digest(payload)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _commit_event(
    repo: Path,
    *,
    changes: dict[str, str],
    packets: list[tuple[str, str, list[str]]],
    packet_owners: dict[str, str] | None = None,
    packet_forbidden: dict[str, list[str]] | None = None,
    omit_own_paths: set[str] | None = None,
    packet_worktrees: dict[str, str] | None = None,
) -> tuple[str, list[Path]]:
    for relative, content in changes.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    paths = [
        _write_ci_packet(
            repo,
            work_packet=work_packet,
            base_ref=base_ref,
            allowed_files=allowed,
            owner=(packet_owners or {}).get(work_packet, DEFAULT_OWNER),
            forbidden_files=(packet_forbidden or {}).get(work_packet, []),
            include_own_path=work_packet not in (omit_own_paths or set()),
            worktree=(packet_worktrees or {}).get(work_packet, "."),
        )
        for work_packet, base_ref, allowed in packets
    ]
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture event head")
    return _git(repo, "rev-parse", "HEAD"), paths


def _broader_ci_packet_bytes(packet_path: Path) -> bytes:
    payload = json.loads(packet_path.read_bytes())
    payload["allowed_files"].append("forbidden.txt")
    payload["forbidden_files"] = []
    payload["session_entry"]["packet_digest"] = "0" * 64
    payload["session_entry"]["packet_digest"] = agentops.packet_digest(payload)
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def _assert_workflow_packet_binding(job: str) -> None:
    pr_base = "github.event.pull_request.base.sha"
    pr_head = "github.event.pull_request.head.sha"
    group_base = "github.event.merge_group.base_sha"
    group_head = "github.event.merge_group.head_sha"

    assert f"ref: ${{{{ {pr_head} || {group_head} }}}}" in job
    assert "github.sha" not in job
    assert f"EVENT_BASE: ${{{{ {pr_base} || {group_base} }}}}" in job
    assert f"EVENT_HEAD: ${{{{ {pr_head} || {group_head} }}}}" in job
    assert "EVENT_NAME: ${{ github.event_name }}" in job
    assert job.count("scripts/governance/run_agent_work_packet.py") == 1
    assert '--ci-event "${EVENT_NAME}"' in job
    assert '--event-base "${EVENT_BASE}"' in job
    assert '--event-head "${EVENT_HEAD}"' in job
    assert "--packet" not in job
    assert '--report-root "${RUNNER_TEMP}/dharma-agentops"' in job
    artifact_root = "${{ runner.temp }}/dharma-agentops"
    artifact_block = (
        "path: |\n"
        f"            {artifact_root}\n"
        f"            !{artifact_root}/**/tool-cache/**\n"
        "          if-no-files-found: error"
    )
    assert artifact_block in job
    assert job.count(f"!{artifact_root}") == 1
    assert re.search(
        r"- name: Run the one door \(same command as local\)\n"
        r"\s+env:\n"
        r"\s+DHARMA_OPS_DIR: \$\{\{ runner\.temp \}\}/"
        r"dharma-agentops/onboarding\n",
        job,
    )
    assert re.search(
        r"- name: Bind onboarding packets to the event range\n"
        r"\s+if: always\(\)\n",
        job,
    )
    assert job.count("if: always()") == 2
    assert job.count("set -euo pipefail") == 4
    assert "continue-on-error" not in job
    assert "|| true" not in job


def test_ci_and_local_admission_command_equivalence() -> None:
    """O4-B5: the CI door is `make onboard` — the exact local command, not a
    reimplementation that can drift from it."""
    job = _job_block("onboarding-admission")
    assert "make onboard" in job
    assert "set -euo pipefail" in job


def test_ci_admission_has_no_weakening_flags() -> None:
    job = _job_block("onboarding-admission")
    assert "continue-on-error" not in job
    assert "|| true" not in job
    assert "--no-strict" not in job
    assert "timeout-minutes: 30" in job
    assert 'python-version: "3.12.13"' in job
    assert (
        'install_source="${RUNNER_TEMP}/dharma-agentops-bootstrap/package-source"'
        in job
    )
    assert 'git archive --format=tar HEAD | tar -xf - -C "${install_source}"' in job
    assert 'python3 -m pip install "${install_source}[dev]"' in job
    assert 'python3 -m pip install ".[dev]"' not in job
    assert 'python3 -m pip install -e ".[dev]"' not in job
    assert "python3 -m pip install pyyaml" not in job
    for externalized in (
        "'PYTHONDONTWRITEBYTECODE=1'",
        '"PYTHONPYCACHEPREFIX=${bootstrap}/pycache"',
        "'PYTEST_ADDOPTS=-p no:cacheprovider'",
        '"XDG_CACHE_HOME=${bootstrap}/xdg"',
        '"RUFF_CACHE_DIR=${bootstrap}/ruff"',
        '"PIP_CACHE_DIR=${bootstrap}/pip"',
    ):
        assert externalized in job

    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = project["project"]["dependencies"]
    development = project["project"]["optional-dependencies"]["dev"]
    assert any(item.startswith("pydantic>=2") for item in runtime)
    assert any(item.startswith("pyyaml>=") for item in runtime)
    for dependency in ("pytest", "pytest-timeout", "ruff"):
        assert any(
            item == dependency or item.startswith((f"{dependency}>=", f"{dependency}=="))
            for item in development
        )
    for relative in (
        "tests/test_make_onboarding_contract.py",
        "tests/test_onboarding_ci_contract.py",
        "tests/test_agent_work_packet.py",
        "tests/test_orientation_graph.py",
    ):
        assert (REPO_ROOT / relative).is_file()


def test_active_track_gate_installs_full_dev_environment_before_evaluation() -> None:
    """The blocking checker must execute criteria, not compare an empty env."""
    job = _job_block("active-track-governance")
    install = 'python3 -m pip install "${install_source}[dev]"'
    evaluate = "python3 scripts/governance/check_track_status.py"

    assert (
        'install_source="${RUNNER_TEMP}/dharma-active-track-bootstrap/package-source"'
        in job
    )
    assert 'git archive --format=tar HEAD | tar -xf - -C "${install_source}"' in job
    assert install in job
    assert "python3 -m pip install pyyaml" not in job
    assert job.index(install) < job.index(evaluate)


def test_macos_compatibility_job_is_required_and_executable() -> None:
    job = _job_block("onboarding-macos-compatibility")
    assert "runs-on: macos-14" in job
    assert "python-version: \"3.12\"" in job
    assert "python-version: \"3.12.13\"" not in job
    assert 'git archive --format=tar HEAD | tar -xf - -C "${install_source}"' in job
    assert 'python3 -m pip install "${install_source}[dev]"' in job
    assert "pip install 'pytest>=7.0'" not in job
    reproducer = "/usr/bin/make onboarding-macos-compatibility"
    assert job.count(reproducer) == 1
    makefile = MAKEFILE.read_text(encoding="utf-8")
    assert "onboarding-macos-compatibility:\n\t@set -eu;" in makefile
    for command in (
        "/usr/bin/make -n onboard",
        "/usr/bin/make -n orient",
        "/usr/bin/make -n help",
    ):
        assert command in makefile
    for proof in (
        "test_darwin_negative_confinement_executes_and_denies_outside_write",
        "test_darwin_account_temp_root_native_and_prepares_report_root",
        "test_darwin_account_temp_root_uses_getconf_with_scrubbed_environment",
        "test_darwin_report_anchor_rejects_environment_minted_temp_root",
        "test_private_report_anchor_enforces_owner_mode_and_symlink_boundaries",
    ):
        assert proof in makefile

    contract = json.loads(
        CI_TRUTH_CONTRACT.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_json_object,
    )
    required = next(
        check
        for check in contract["required"]
        if "Onboarding macOS 3.81 compatibility" in check.get("names", [])
    )
    assert required["local_command"] == reproducer


def test_ci_runner_context_is_resolved_only_after_job_assignment() -> None:
    """GitHub does not expose ``runner`` while evaluating job-level ``env``.

    A forbidden context there invalidates the entire workflow before any job
    exists, so the external cache roots must be exported from a runner step.
    """
    job = _job_block("onboarding-admission")
    job_header, steps = job.split("    steps:\n", maxsplit=1)
    assert "${{ runner." not in job_header
    assert steps.startswith(
        "      # `runner` is unavailable while GitHub evaluates job-level `env`."
    )
    assert "- name: Confine tool state outside checkout" in steps
    assert 'bootstrap="${RUNNER_TEMP}/dharma-agentops-bootstrap"' in steps
    assert '>> "${GITHUB_ENV}"' in steps


def test_ci_pr_head_and_merge_group_packet_binding(tmp_path: Path) -> None:
    """O4-B10: discovery binds the complete packet set to the checked-out
    event range and fails closed on gaps, overlap, or an unbound base."""
    job = _job_block("onboarding-admission")
    _assert_workflow_packet_binding(job)

    unrelated, _, unrelated_base = _new_event_repo(tmp_path, "unrelated-pr")
    unrelated_head, _ = _commit_event(
        unrelated, changes={"notes.txt": "not onboarding\n"}, packets=[]
    )
    assert agentops.discover_ci_packets(
        unrelated,
        event_name="pull_request",
        event_base=unrelated_base,
        event_head=unrelated_head,
    ) == []

    owned, _, owned_base = _new_event_repo(tmp_path, "owned-pr")
    owned_head, owned_packets = _commit_event(
        owned,
        changes={"owned/a.txt": "PR change\n"},
        packets=[("WP-O4", owned_base, ["owned/a.txt"])],
    )
    assert agentops.discover_ci_packets(
        owned,
        event_name="pull_request",
        event_base=owned_base,
        event_head=owned_head,
    ) == [owned_packets[0].resolve()]

    nonportable, _, nonportable_base = _new_event_repo(tmp_path, "nonportable-pr")
    nonportable_head, _ = _commit_event(
        nonportable,
        changes={"owned/a.txt": "nonportable packet\n"},
        packets=[("WP-O4", nonportable_base, ["owned/a.txt"])],
        packet_worktrees={"WP-O4": "/tmp/not-portable"},
    )
    with pytest.raises(agentops.AgentOpsError, match='portable worktree "\\."'):
        agentops.discover_ci_packets(
            nonportable,
            event_name="pull_request",
            event_base=nonportable_base,
            event_head=nonportable_head,
        )

    group, _, group_base = _new_event_repo(tmp_path, "merge-group")
    group_head, group_packets = _commit_event(
        group,
        changes={"owned/a.txt": "group A\n", "owned/b.txt": "group B\n"},
        # Deliberately create O4 first: the evaluator must return stable lexical
        # order, independent of filesystem or diff traversal order.
        packets=[
            ("WP-O4", group_base, ["owned/b.txt"]),
            ("WP-O3", group_base, ["owned/a.txt"]),
        ],
    )
    assert agentops.discover_ci_packets(
        group,
        event_name="merge_group",
        event_base=group_base,
        event_head=group_head,
    ) == sorted(path.resolve() for path in group_packets)

    overlap, _, overlap_base = _new_event_repo(tmp_path, "overlap")
    overlap_head, _ = _commit_event(
        overlap,
        changes={"owned/shared.txt": "claimed twice\n"},
        packets=[
            ("WP-O3", overlap_base, ["owned/shared.txt"]),
            ("WP-O4", overlap_base, ["owned/shared.txt"]),
        ],
    )
    with pytest.raises(agentops.AgentOpsError, match="overlap|multiple|exactly once"):
        agentops.discover_ci_packets(
            overlap,
            event_name="merge_group",
            event_base=overlap_base,
            event_head=overlap_head,
        )

    gap, _, gap_base = _new_event_repo(tmp_path, "gap")
    gap_head, _ = _commit_event(
        gap,
        changes={"owned/a.txt": "covered\n", "owned/b.txt": "uncovered\n"},
        packets=[("WP-O4", gap_base, ["owned/a.txt"])],
    )
    with pytest.raises(agentops.AgentOpsError, match="gap|uncovered|exactly once"):
        agentops.discover_ci_packets(
            gap,
            event_name="pull_request",
            event_base=gap_base,
            event_head=gap_head,
        )

    unbound, wrong_base, unbound_base = _new_event_repo(tmp_path, "unbound")
    unbound_head, _ = _commit_event(
        unbound,
        changes={"owned/a.txt": "wrong base\n"},
        packets=[("WP-O4", wrong_base, ["owned/a.txt"])],
    )
    with pytest.raises(agentops.AgentOpsError, match="base|bind"):
        agentops.discover_ci_packets(
            unbound,
            event_name="pull_request",
            event_base=unbound_base,
            event_head=unbound_head,
        )

    unrelated_history, _, unrelated_head = _new_event_repo(
        tmp_path, "unrelated-history"
    )
    unrelated_tree = _git(
        unrelated_history, "rev-parse", f"{unrelated_head}^{{tree}}"
    )
    unrelated_base = _git(
        unrelated_history,
        "commit-tree",
        unrelated_tree,
        "-m",
        "unrelated event base",
    )
    with pytest.raises(agentops.AgentOpsError, match="unrelated histories"):
        agentops.discover_ci_packets(
            unrelated_history,
            event_name="pull_request",
            event_base=unrelated_base,
            event_head=unrelated_head,
        )

    # A behind/diverged PR with no onboarding-owned change evaluates from its
    # true merge base and baseline-passes without a repository-wide freshness
    # gate.
    behind, _, behind_common = _new_event_repo(tmp_path, "behind-event-base")
    _git(behind, "switch", "-c", "feature")
    _git(behind, "switch", "main")
    behind_base, _ = _commit_event(
        behind,
        changes={"main-only.txt": "base advanced\n"},
        packets=[],
    )
    _git(behind, "switch", "feature")
    behind_unrelated_head, _ = _commit_event(
        behind,
        changes={"notes.txt": "unrelated stale-branch change\n"},
        packets=[],
    )
    assert behind_common != behind_base
    exit_code, summary = agentops.execute_ci_event(
        source_root=behind,
        event_name="pull_request",
        event_base=behind_base,
        event_head=behind_unrelated_head,
        report_root=tmp_path / "behind-unrelated-reports",
    )
    assert exit_code == 0
    assert summary["status"] == "passed"
    assert summary["packets"] == []

    # Exact-base custody remains fail-closed once the same branch carries an
    # onboarding-owned change and packet whose declared base is not in HEAD.
    behind_owned_head, _ = _commit_event(
        behind,
        changes={"owned/a.txt": "stale branch change\n"},
        packets=[("WP-O4", behind_base, ["owned/a.txt"])],
    )
    report_root = tmp_path / "behind-owned-reports"
    with pytest.raises(agentops.AgentOpsError, match="base is not an ancestor"):
        agentops.execute_ci_event(
            source_root=behind,
            event_name="pull_request",
            event_base=behind_base,
            event_head=behind_owned_head,
            report_root=report_root,
        )
    config_reports = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in report_root.rglob("report.json")
    ]
    assert len(config_reports) == 1
    assert config_reports[0]["status"] == "config_error"
    assert config_reports[0]["error"] == (
        "CI event base is not an ancestor of the event head"
    )

    # ACTIVE -> inactive changes only authority. With no concurrently owned
    # code or packet change there is nothing to bind, so this transition passes.
    deactivated, _, deactivated_base = _new_event_repo(tmp_path, "deactivated")
    deactivated_head, _ = _commit_event(
        deactivated,
        changes={TRACK_PATH: _tracks_text(_track_row(status="INACTIVE"))},
        packets=[],
    )
    assert agentops.discover_ci_packets(
        deactivated,
        event_name="pull_request",
        event_base=deactivated_base,
        event_head=deactivated_head,
    ) == []

    # An inactive endpoint contributes no authority, while a newly ACTIVE head
    # must immediately guard its declared surfaces and accept a bound packet.
    activated, _, _ = _new_event_repo(tmp_path, "activated")
    activated_base, _ = _commit_event(
        activated,
        changes={TRACK_PATH: _tracks_text(_track_row(status="INACTIVE"))},
        packets=[],
    )
    activated_head, activated_packets = _commit_event(
        activated,
        changes={
            TRACK_PATH: _tracks_text(_track_row()),
            "owned/a.txt": "activated owner change\n",
        },
        packets=[("WP-O4", activated_base, ["owned/a.txt"])],
    )
    assert agentops.discover_ci_packets(
        activated,
        event_name="pull_request",
        event_base=activated_base,
        event_head=activated_head,
    ) == [activated_packets[0].resolve()]

    # Both inactive and missing -> ACTIVE transitions must guard head surfaces
    # even before a packet exists; otherwise activation could evade admission.
    for transition, base_rows in (
        ("inactive", (_track_row(status="INACTIVE"),)),
        ("missing", ()),
    ):
        activation_gap, _, _ = _new_event_repo(
            tmp_path, f"activation-gap-{transition}"
        )
        activation_gap_base, _ = _commit_event(
            activation_gap,
            changes={TRACK_PATH: _tracks_text(*base_rows)},
            packets=[],
        )
        activation_gap_head, _ = _commit_event(
            activation_gap,
            changes={
                TRACK_PATH: _tracks_text(_track_row()),
                "owned/a.txt": f"{transition} activation without packet\n",
            },
            packets=[],
        )
        with pytest.raises(agentops.AgentOpsError, match="exactly one|packet"):
            agentops.discover_ci_packets(
                activation_gap,
                event_name="pull_request",
                event_base=activation_gap_base,
                event_head=activation_gap_head,
            )

    # No ACTIVE endpoint may authorize even a correctly shaped O packet.
    inactive_packet, _, _ = _new_event_repo(tmp_path, "both-inactive-packet")
    inactive_packet_base, _ = _commit_event(
        inactive_packet,
        changes={TRACK_PATH: _tracks_text(_track_row(status="INACTIVE"))},
        packets=[],
    )
    inactive_packet_head, _ = _commit_event(
        inactive_packet,
        changes={},
        packets=[("WP-O4", inactive_packet_base, [])],
    )
    with pytest.raises(agentops.AgentOpsError, match="without ACTIVE|authority"):
        agentops.discover_ci_packets(
            inactive_packet,
            event_name="pull_request",
            event_base=inactive_packet_base,
            event_head=inactive_packet_head,
        )

    base_owner = "@BaseOwner"
    head_owner = "@HeadOwner"
    base_surfaces = ["owned/a.txt", PACKET_SURFACE]
    head_surfaces = ["owned/b.txt", PACKET_SURFACE]

    def transfer_repo(name: str) -> tuple[Path, str]:
        repo, _, _ = _new_event_repo(tmp_path, name)
        transfer_base, _ = _commit_event(
            repo,
            changes={
                TRACK_PATH: _tracks_text(
                    _track_row(owner=base_owner, surfaces=base_surfaces)
                )
            },
            packets=[],
        )
        return repo, transfer_base

    # ACTIVE -> ACTIVE transfer takes its packet owner from head while guarding
    # the union of old and new surfaces throughout the authority handoff.
    transfer, transfer_base = transfer_repo("authority-transfer")
    transfer_head, transfer_packets = _commit_event(
        transfer,
        changes={
            TRACK_PATH: _tracks_text(
                _track_row(owner=head_owner, surfaces=head_surfaces)
            ),
            "owned/a.txt": "old surface changed during transfer\n",
            "owned/b.txt": "new surface changed during transfer\n",
        },
        packets=[("WP-O4", transfer_base, ["owned/a.txt", "owned/b.txt"])],
        packet_owners={"WP-O4": head_owner},
    )
    assert agentops.discover_ci_packets(
        transfer,
        event_name="pull_request",
        event_base=transfer_base,
        event_head=transfer_head,
    ) == [transfer_packets[0].resolve()]

    stale_owner, stale_owner_base = transfer_repo("stale-transfer-owner")
    stale_owner_head, _ = _commit_event(
        stale_owner,
        changes={
            TRACK_PATH: _tracks_text(
                _track_row(owner=head_owner, surfaces=head_surfaces)
            ),
            "owned/a.txt": "old surface with stale owner\n",
            "owned/b.txt": "new surface with stale owner\n",
        },
        packets=[("WP-O4", stale_owner_base, ["owned/a.txt", "owned/b.txt"])],
        packet_owners={"WP-O4": base_owner},
    )
    with pytest.raises(agentops.AgentOpsError, match="owner mismatch"):
        agentops.discover_ci_packets(
            stale_owner,
            event_name="pull_request",
            event_base=stale_owner_base,
            event_head=stale_owner_head,
        )

    transfer_gap, transfer_gap_base = transfer_repo("transfer-union-gap")
    transfer_gap_head, _ = _commit_event(
        transfer_gap,
        changes={
            TRACK_PATH: _tracks_text(
                _track_row(owner=head_owner, surfaces=head_surfaces)
            ),
            "owned/a.txt": "uncovered former surface\n",
            "owned/b.txt": "covered new surface\n",
        },
        packets=[("WP-O4", transfer_gap_base, ["owned/b.txt"])],
        packet_owners={"WP-O4": head_owner},
    )
    with pytest.raises(agentops.AgentOpsError, match="gap|uncovered|exactly once"):
        agentops.discover_ci_packets(
            transfer_gap,
            event_name="pull_request",
            event_base=transfer_gap_base,
            event_head=transfer_gap_head,
        )

    sibling_old = "sibling/old/**"
    sibling_kept = "sibling/kept/**"

    def sibling_repo(name: str) -> tuple[Path, str]:
        repo, _, _ = _new_event_repo(tmp_path, name)
        sibling_base, _ = _commit_event(
            repo,
            changes={
                TRACK_PATH: _tracks_text(
                    _track_row(),
                    _track_row(
                        track_id="sibling-track",
                        owner="@SiblingOwner",
                        surfaces=[sibling_old, sibling_kept],
                    ),
                ),
                "sibling/old/base.txt": "old sibling surface\n",
                "sibling/kept/base.txt": "kept sibling surface\n",
            },
            packets=[],
        )
        return repo, sibling_base

    # Sibling authority is also a base/head union. Shrinking or removing a
    # sibling at head cannot let a packet omit the former forbidden surface.
    sibling_shrink, sibling_shrink_base = sibling_repo("sibling-shrink")
    sibling_shrink_head, _ = _commit_event(
        sibling_shrink,
        changes={
            TRACK_PATH: _tracks_text(
                _track_row(),
                _track_row(
                    track_id="sibling-track",
                    owner="@SiblingOwner",
                    surfaces=[sibling_kept],
                ),
            )
        },
        packets=[("WP-O4", sibling_shrink_base, [])],
        packet_forbidden={"WP-O4": [sibling_kept]},
    )
    with pytest.raises(agentops.AgentOpsError, match="sibling/old|omit sibling"):
        agentops.discover_ci_packets(
            sibling_shrink,
            event_name="pull_request",
            event_base=sibling_shrink_base,
            event_head=sibling_shrink_head,
        )

    sibling_removed, sibling_removed_base = sibling_repo("sibling-removed")
    sibling_removed_head, _ = _commit_event(
        sibling_removed,
        changes={TRACK_PATH: _tracks_text(_track_row())},
        packets=[("WP-O4", sibling_removed_base, [])],
    )
    with pytest.raises(agentops.AgentOpsError, match="sibling/(old|kept)|omit sibling"):
        agentops.discover_ci_packets(
            sibling_removed,
            event_name="pull_request",
            event_base=sibling_removed_base,
            event_head=sibling_removed_head,
        )

    # Packet paths themselves participate in exact-once coverage. A broad
    # packet claim cannot overlap a sibling packet's self-claim, and a packet
    # cannot delegate its own canonical path to another packet.
    own_overlap, _, own_overlap_base = _new_event_repo(tmp_path, "own-overlap")
    own_overlap_head, _ = _commit_event(
        own_overlap,
        changes={},
        packets=[
            ("WP-O3", own_overlap_base, [PACKET_SURFACE]),
            ("WP-O4", own_overlap_base, []),
        ],
    )
    with pytest.raises(agentops.AgentOpsError, match="overlap|multiple"):
        agentops.discover_ci_packets(
            own_overlap,
            event_name="merge_group",
            event_base=own_overlap_base,
            event_head=own_overlap_head,
        )

    own_gap, _, own_gap_base = _new_event_repo(tmp_path, "own-gap")
    own_gap_head, _ = _commit_event(
        own_gap,
        changes={},
        packets=[
            ("WP-O3", own_gap_base, ["README.md"]),
            ("WP-O4", own_gap_base, []),
        ],
        omit_own_paths={"WP-O3"},
    )
    with pytest.raises(agentops.AgentOpsError, match="own canonical|explicitly allow|gap"):
        agentops.discover_ci_packets(
            own_gap,
            event_name="merge_group",
            event_base=own_gap_base,
            event_head=own_gap_head,
        )


def test_ci_merge_group_execution_keeps_forbidden_full_event_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A positive-claim projection must not erase an explicit forbidden path.

    Disjoint packet claims and truly unrelated event paths remain valid, but
    any full-event path matching a packet's forbidden envelope is retained in
    that packet's committed scope and fails closed.
    """

    def pass_gate(
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

    monkeypatch.setattr(agentops, "run_gate", pass_gate)
    monkeypatch.setattr(agentops, "run_negative_control", pass_gate)

    disjoint, _, disjoint_base = _new_event_repo(tmp_path, "disjoint-execution")
    disjoint_head, _ = _commit_event(
        disjoint,
        changes={
            "owned/a.txt": "packet O3\n",
            "owned/b.txt": "packet O4\n",
            "notes.txt": "truly unrelated merge-group change\n",
        },
        packets=[
            ("WP-O3", disjoint_base, ["owned/a.txt"]),
            ("WP-O4", disjoint_base, ["owned/b.txt"]),
        ],
    )
    exit_code, summary = agentops.execute_ci_event(
        source_root=disjoint,
        event_name="merge_group",
        event_base=disjoint_base,
        event_head=disjoint_head,
        report_root=tmp_path / "disjoint-reports",
    )
    assert exit_code == 0
    assert summary["status"] == "passed"

    forbidden, _, forbidden_base = _new_event_repo(tmp_path, "forbidden-execution")
    forbidden_head, _ = _commit_event(
        forbidden,
        changes={
            "owned/a.txt": "claimed change\n",
            "forbidden.txt": "outside owns but explicitly forbidden\n",
        },
        packets=[("WP-O4", forbidden_base, ["owned/a.txt"])],
        packet_forbidden={"WP-O4": ["forbidden.txt"]},
    )
    # Discovery still succeeds: exact-once coverage concerns owned surfaces.
    assert len(
        agentops.discover_ci_packets(
            forbidden,
            event_name="merge_group",
            event_base=forbidden_base,
            event_head=forbidden_head,
        )
    ) == 1
    report_root = tmp_path / "forbidden-reports"
    exit_code, summary = agentops.execute_ci_event(
        source_root=forbidden,
        event_name="merge_group",
        event_base=forbidden_base,
        event_head=forbidden_head,
        report_root=report_root,
    )
    assert exit_code == 1
    assert summary["status"] == "failed"
    reports = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in report_root.rglob("report.json")
    ]
    packet_report = next(
        report for report in reports if report["job_id"] == "onboard-one-door-WP-O4"
    )
    assert {
        "path": "forbidden.txt",
        "reason": "forbidden",
        "patterns": ["forbidden.txt"],
    } in packet_report["scope"]["violations"]


def test_ci_packet_snapshot_is_bound_from_discovery_through_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A validated packet cannot be replaced by a broader transient copy.

    The third and fourth reads model a swap after discovery followed by a
    restore before final rediscovery.  The evaluator must retain and enforce
    the exact bytes validated by discovery, not reparse the transient copy.
    """

    def pass_gate(
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

    monkeypatch.setattr(agentops, "run_gate", pass_gate)
    monkeypatch.setattr(agentops, "run_negative_control", pass_gate)

    repo, _, event_base = _new_event_repo(tmp_path, "packet-snapshot-swap")
    event_head, packet_paths = _commit_event(
        repo,
        changes={
            "owned/a.txt": "claimed change\n",
            "forbidden.txt": "must remain forbidden\n",
        },
        packets=[("WP-O4", event_base, ["owned/a.txt"])],
        packet_forbidden={"WP-O4": ["forbidden.txt"]},
    )
    packet_path = packet_paths[0]
    original_read = agentops._read_packet_bytes
    original_bytes = original_read(packet_path)
    broader_bytes = _broader_ci_packet_bytes(packet_path)
    packet_reads = 0

    def swap_then_restore(path: Path) -> bytes:
        nonlocal packet_reads
        if path.resolve() != packet_path.resolve():
            return original_read(path)
        packet_reads += 1
        if packet_reads in {3, 4}:
            return broader_bytes
        return original_bytes

    monkeypatch.setattr(agentops, "_read_packet_bytes", swap_then_restore)

    with pytest.raises(agentops.AgentOpsError, match="packet snapshot changed"):
        agentops.execute_ci_event(
            source_root=repo,
            event_name="merge_group",
            event_base=event_base,
            event_head=event_head,
            report_root=tmp_path / "packet-snapshot-reports",
        )
    assert packet_reads >= 3

    # Discovery itself must use the immutable event-head blob as its byte
    # anchor. A clean probe followed by a coordinated worktree+index swap must
    # not admit bytes that never existed in the declared event head.
    monkeypatch.setattr(agentops, "_read_packet_bytes", original_read)
    discovery_repo, _, discovery_base = _new_event_repo(
        tmp_path, "event-head-packet-snapshot"
    )
    discovery_head, discovery_packets = _commit_event(
        discovery_repo,
        changes={
            "owned/a.txt": "claimed change\n",
            "forbidden.txt": "must remain forbidden\n",
        },
        packets=[("WP-O4", discovery_base, ["owned/a.txt"])],
        packet_forbidden={"WP-O4": ["forbidden.txt"]},
    )
    discovery_packet = discovery_packets[0]
    broader_discovery_bytes = _broader_ci_packet_bytes(discovery_packet)
    original_live_scope = agentops._exact_live_scope_paths
    swapped_after_clean_probe = False

    def swap_index_and_worktree_after_clean_probe(
        repo_root: Path,
    ) -> tuple[list[str], list[str], list[str]]:
        nonlocal swapped_after_clean_probe
        scope = original_live_scope(repo_root)
        if repo_root.resolve() == discovery_repo.resolve():
            discovery_packet.write_bytes(broader_discovery_bytes)
            _git(
                discovery_repo,
                "add",
                "--",
                discovery_packet.relative_to(discovery_repo).as_posix(),
            )
            swapped_after_clean_probe = True
        return scope

    monkeypatch.setattr(
        agentops,
        "_exact_live_scope_paths",
        swap_index_and_worktree_after_clean_probe,
    )
    with pytest.raises(agentops.AgentOpsError, match="event-head packet snapshot"):
        agentops.discover_ci_packets(
            discovery_repo,
            event_name="pull_request",
            event_base=discovery_base,
            event_head=discovery_head,
        )
    assert swapped_after_clean_probe


def test_verifier_selfcheck_propagates_onboard_failure() -> None:
    """O4-B6: root validation orders the sequential, fail-closed verifier."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    match = re.search(r"^agent-build-preflight:(.*)$", makefile, re.MULTILINE)
    assert match
    prerequisites = match.group(1).split()
    assert prerequisites == ["agentops-report-root-check"]

    recipe_match = re.search(
        r"^agent-build-preflight:.*\n((?:\t.*\n|ifdef .*\n|endif\n)*)",
        makefile,
        re.MULTILINE,
    )
    assert recipe_match
    recipe = recipe_match.group(0)
    assert recipe.count("$(MAKE) -s verifier-selfcheck") == 1
    assert recipe.count("$(MAKE) -s hygiene-check") == 1
    assert recipe.count("MAKEOVERRIDES=") == 2
    assert "AGENTOPS_RECURSIVE_OVERRIDES" not in recipe
    assert recipe.index("verifier-selfcheck") < recipe.index("hygiene-check")
    assert "$(MAKE) -s onboard" not in recipe
    assert "|| true" not in recipe
