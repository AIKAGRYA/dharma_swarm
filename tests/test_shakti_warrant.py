import json
import os
import subprocess
import sys
from pathlib import Path

from dharma_swarm.dharma_corpus import Claim, ClaimCategory, ClaimStatus
from dharma_swarm.shakti_warrant import (
    FourfoldActionWarrantRequest,
    WarrantEvidence,
    WarrantVerdict,
    evaluate_fourfold_warrant,
    render_warrant_report,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _claim(claim_id: str, statement: str, *, enforcement: str = "warn") -> Claim:
    return Claim(
        id=claim_id,
        statement=statement,
        category=ClaimCategory.ARCHITECTURAL,
        confidence=1.0,
        enforcement=enforcement,
        status=ClaimStatus.ACCEPTED,
    )


def test_fourfold_warrant_allows_well_evidenced_governance_action():
    request = FourfoldActionWarrantRequest(
        actor_id="codex",
        action_type="governance_patch",
        intent=(
            "restore canonical governance warrant architecture and integrate a single "
            "source of truth for the larger telos pattern"
        ),
        content=(
            "fix blocker guard, reduce fragmentation, reuse existing semantic governance, "
            "add deterministic pytest verification and exact path evidence"
        ),
        target_paths=[
            "dharma_swarm/shakti_warrant.py",
            "scripts/governance/check_shakti_warrant.py",
            "tests/test_shakti_warrant.py",
        ],
        requested_tools=["pytest"],
        metadata={
            "telos_aligned": True,
            "fixes_blocker": True,
            "no_new_substrate": True,
            "reduces_fragmentation": True,
            "tests_planned": True,
            "allowed_tools": ["pytest"],
        },
    )

    warrant = evaluate_fourfold_warrant(request)

    # Keyword-bag self-passing was removed: dimensions pass only on declared
    # evidence. Here mahalakshmi (no_new_substrate + reduces_fragmentation)
    # and mahasaraswati (tests + paths + allowlisted pytest) pass.
    assert warrant.verdict == WarrantVerdict.WARN
    assert warrant.pass_count == 2
    assert {dimension.energy.value for dimension in warrant.dimensions if dimension.passed} == {
        "mahalakshmi",
        "mahasaraswati",
    }


def test_fourfold_warrant_holds_when_only_force_is_clear():
    request = FourfoldActionWarrantRequest(
        actor_id="worker",
        action_type="rapid_patch",
        intent="execute urgent action now",
        content="move quickly and deploy immediately",
        metadata={"urgent": True},
    )

    warrant = evaluate_fourfold_warrant(request)

    assert warrant.verdict == WarrantVerdict.HOLD
    assert warrant.pass_count < warrant.required_pass_count
    assert "only" in warrant.rationale


def test_fourfold_warrant_blocks_explicit_destructive_action():
    request = FourfoldActionWarrantRequest(
        actor_id="worker",
        action_type="shell_command",
        intent="clean state",
        content="rm -rf ~/.dharma",
        metadata={"destructive_without_consent": True},
    )

    warrant = evaluate_fourfold_warrant(request)

    assert warrant.verdict == WarrantVerdict.BLOCK
    assert "destructive action without consent" in warrant.rationale


def test_semantic_claim_block_overrides_fourfold_score():
    request = FourfoldActionWarrantRequest(
        actor_id="codex",
        action_type="governance_patch",
        intent="restore architecture and add deterministic tests",
        content="delete production database after tests",
        target_paths=["scripts/governance/check_shakti_warrant.py"],
        requested_tools=["pytest"],
        metadata={
            "telos_aligned": True,
            "fixes_blocker": True,
            "no_new_substrate": True,
            "tests_planned": True,
        },
    )

    warrant = evaluate_fourfold_warrant(
        request,
        claims=[_claim("DC-TEST-1", "delete production database", enforcement="block")],
    )

    assert warrant.verdict == WarrantVerdict.BLOCK
    assert warrant.semantic_verdict is not None
    assert warrant.semantic_verdict.enforcement_level == "block"


def test_render_warrant_report_includes_dimension_status():
    request = FourfoldActionWarrantRequest(
        actor_id="codex",
        action_type="review",
        intent="verify exact tests for semantic governance",
        content="pytest evidence",
        target_paths=["tests/test_shakti_warrant.py"],
        metadata={"tests_planned": True},
    )

    report = render_warrant_report(evaluate_fourfold_warrant(request))

    assert "Fourfold Shakti Warrant" in report
    assert "mahasaraswati" in report
    assert "Score:" in report


def test_check_shakti_warrant_cli_json_output():
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/governance/check_shakti_warrant.py",
            "--intent",
            "restore canonical governance architecture",
            "--content",
            "fix blocker reduce fragmentation deterministic pytest evidence",
            "--target",
            "tests/test_shakti_warrant.py",
            "--tool",
            "pytest",
            "--metadata",
            "telos_aligned=true",
            "--metadata",
            "fixes_blocker=true",
            "--metadata",
            "no_new_substrate=true",
            "--metadata",
            "tests_planned=true",
            "--metadata",
            "reduces_fragmentation=true",
            "--metadata",
            "allowed_tools=pytest",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(proc.stdout)
    assert payload["verdict"] in {"allow", "warn"}
    assert payload["pass_count"] >= 2


def test_requested_tool_without_allowlist_warns():
    request = FourfoldActionWarrantRequest(
        actor_id="codex",
        action_type="governance_patch",
        intent="restore architecture and add deterministic tests",
        content="fix blocker reduce fragmentation pytest evidence",
        target_paths=["tests/test_shakti_warrant.py"],
        requested_tools=["pytest -q tests/test_shakti_warrant.py"],
        metadata={
            "telos_aligned": True,
            "fixes_blocker": True,
            "no_new_substrate": True,
            "reduces_fragmentation": True,
            "tests_planned": True,
        },
    )

    warrant = evaluate_fourfold_warrant(request)

    assert warrant.verdict in {WarrantVerdict.ALLOW, WarrantVerdict.WARN}
    assert "requested tools were not checked against an allowlist" in warrant.warnings


def test_enforced_tool_allowlist_blocks_unauthorized_tool():
    request = FourfoldActionWarrantRequest(
        actor_id="codex",
        action_type="governance_patch",
        intent="restore architecture and add deterministic tests",
        content="fix blocker reduce fragmentation pytest evidence",
        target_paths=["tests/test_shakti_warrant.py"],
        requested_tools=["pytest -q tests/test_shakti_warrant.py", "curl https://example.test"],
        metadata={
            "telos_aligned": True,
            "fixes_blocker": True,
            "no_new_substrate": True,
            "tests_planned": True,
            "allowed_tools": ["pytest"],
            "enforce_tool_allowlist": True,
        },
    )

    warrant = evaluate_fourfold_warrant(request)

    assert warrant.verdict == WarrantVerdict.BLOCK
    assert "unauthorized requested tools: curl" in warrant.rationale


def test_diff_evidence_records_paths_and_boosts_precision():
    evidence = WarrantEvidence(
        source="git",
        kind="git_diff",
        summary="git diff scope=staged: 2 changed path(s)",
        paths=["./dharma_swarm/shakti_warrant.py", "tests/test_shakti_warrant.py"],
    )
    request = FourfoldActionWarrantRequest(
        actor_id="codex",
        action_type="governance_patch",
        intent="restore canonical governance architecture with deterministic evidence",
        content="reduce fragmentation and verify exact pytest path evidence",
        requested_tools=["pytest -q tests/test_shakti_warrant.py"],
        metadata={
            "diff_bound": True,
            "no_new_substrate": True,
            "tests_planned": True,
            "allowed_tools": ["pytest"],
        },
        evidence=[evidence],
    )

    warrant = evaluate_fourfold_warrant(request)
    mahasaraswati = next(
        dimension
        for dimension in warrant.dimensions
        if dimension.energy.value == "mahasaraswati"
    )
    report = render_warrant_report(warrant)

    assert "dharma_swarm/shakti_warrant.py" in warrant.target_paths
    assert "git_diff_evidence" in mahasaraswati.matched_terms
    assert "test_paths" in mahasaraswati.matched_terms
    assert warrant.evidence[0].kind == "git_diff"
    assert "Evidence:" in report


def test_enforced_hot_path_ack_blocks_without_impact_check():
    request = FourfoldActionWarrantRequest(
        actor_id="codex",
        action_type="runtime_patch",
        intent="fix urgent orchestration guard with deterministic evidence",
        content="restore system architecture and run pytest verification",
        target_paths=["./dharma_swarm/orchestrator.py"],
        metadata={
            "diff_bound": True,
            "fixes_blocker": True,
            "tests_planned": True,
            "enforce_hotpath_ack": True,
        },
    )

    warrant = evaluate_fourfold_warrant(request)

    assert warrant.verdict == WarrantVerdict.BLOCK
    assert "hot-path changes lack impact_checked" in warrant.rationale
    assert any("hot-path changes lack impact_checked" in warning for warning in warrant.warnings)


def test_source_diff_without_tests_warns():
    request = FourfoldActionWarrantRequest(
        actor_id="codex",
        action_type="source_patch",
        intent="implement deterministic source change",
        target_paths=["dharma_swarm/new_feature.py"],
        metadata={"diff_bound": True},
    )

    warrant = evaluate_fourfold_warrant(request)

    assert "source changes lack test paths or test metadata" in warrant.warnings


def test_doc_only_blocker_claim_warns():
    request = FourfoldActionWarrantRequest(
        actor_id="codex",
        action_type="governance_doc_patch",
        intent="document blocker fix for governance",
        target_paths=["docs/governance/fourfold.md"],
        metadata={"diff_bound": True, "fixes_blocker": True},
    )

    warrant = evaluate_fourfold_warrant(request)

    assert (
        "doc-only diff claims fixes_blocker; verify there is an executable fix elsewhere"
        in warrant.warnings
    )


def test_check_shakti_warrant_cli_binds_to_git_diff_and_untracked_files(tmp_path):
    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    git("init")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test User")
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    git("add", "app.py")
    git("commit", "-m", "init")
    (tmp_path / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text(
        "def test_value():\n    assert True\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/governance/check_shakti_warrant.py"),
            "--repo-root",
            str(tmp_path),
            "--diff-scope",
            "unstaged",
            "--intent",
            "restore architecture with deterministic pytest evidence",
            "--tool",
            "pytest -q",
            "--metadata",
            "allowed_tools=pytest",
            "--metadata",
            "tests_planned=true",
            "--json",
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(proc.stdout)
    evidence = payload["evidence"][0]

    assert evidence["kind"] == "git_diff"
    assert evidence["metadata"]["diff_bound"] is True
    assert evidence["metadata"]["untracked_files_count"] == 1
    assert "app.py" in payload["target_paths"]
    assert "tests/test_app.py" in payload["target_paths"]


def test_check_shakti_warrant_cli_passes_empty_staged_diff(tmp_path):
    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    git("init")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test User")
    (tmp_path / "README.md").write_text("# test\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-m", "init")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/governance/check_shakti_warrant.py"),
            "--repo-root",
            str(tmp_path),
            "--diff-scope",
            "staged",
            "--pass-on-empty-diff",
            "--intent",
            "pre-commit staged diff fourfold governance warrant",
            "--metadata",
            "requires_diff_evidence=true",
            "--fail-on",
            "hold",
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "No changed paths for diff scope staged" in proc.stdout


def test_check_shakti_warrant_cli_honors_env_impact_ack_for_hot_paths(tmp_path):
    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    git("init")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test User")
    hot_path = tmp_path / "dharma_swarm" / "orchestrator.py"
    hot_path.parent.mkdir()
    hot_path.write_text("VALUE = 1\n", encoding="utf-8")
    git("add", "dharma_swarm/orchestrator.py")
    git("commit", "-m", "init")
    hot_path.write_text("VALUE = 2\n", encoding="utf-8")
    git("add", "dharma_swarm/orchestrator.py")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    base_cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts/governance/check_shakti_warrant.py"),
        "--repo-root",
        str(tmp_path),
        "--diff-scope",
        "staged",
        "--no-include-untracked",
        "--intent",
        (
            "pre-commit staged diff fourfold governance warrant for system telos "
            "semantic architecture deterministic evidence exact paths verification"
        ),
        "--tool",
        "pytest",
        "--metadata",
        "allowed_tools=pytest",
        "--metadata",
        "enforce_hotpath_ack=true",
        "--fail-on",
        "block",
        "--json",
    ]
    blocked = subprocess.run(
        base_cmd,
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert blocked.returncode == 1
    assert "hot-path changes lack impact_checked" in blocked.stdout

    env["DHARMA_UPLIFT_ACK"] = "impact-checked"
    allowed = subprocess.run(
        base_cmd,
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(allowed.stdout)

    # With keyword scoring removed, low declared evidence yields HOLD, which
    # no longer fails the guard; the ack must clear the hot-path block/warning.
    assert payload["verdict"] != "block"
    assert not any("hot-path changes lack impact_checked" in item for item in payload["warnings"])


def test_check_shakti_warrant_cli_writes_report_and_json_outputs(tmp_path):
    report_path = tmp_path / "warrant.txt"
    json_path = tmp_path / "warrant.json"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/governance/check_shakti_warrant.py"),
            "--intent",
            "restore canonical governance architecture",
            "--content",
            "fix blocker reduce fragmentation deterministic pytest evidence",
            "--target",
            "tests/test_shakti_warrant.py",
            "--tool",
            "pytest",
            "--metadata",
            "allowed_tools=pytest",
            "--metadata",
            "tests_planned=true",
            "--report-output",
            str(report_path),
            "--json-output",
            str(json_path),
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert "Fourfold Shakti Warrant" in proc.stdout
    assert "Fourfold Shakti Warrant" in report_path.read_text(encoding="utf-8")
    assert payload["action_type"] == "proposed_action"
    assert payload["target_paths"] == ["tests/test_shakti_warrant.py"]


def test_diff_deleting_dangerous_line_does_not_block():
    """A diff REMOVING an unsafe line must not trip the block-pattern scan."""
    request = FourfoldActionWarrantRequest(
        actor_id="codex",
        action_type="governance_patch",
        intent="remove unsafe cleanup command from script",
        content='-rm -rf ~/.dharma\n+shutil.rmtree(state_dir, ignore_errors=True)',
        metadata={"diff_bound": True},
    )

    warrant = evaluate_fourfold_warrant(request)

    assert warrant.verdict != WarrantVerdict.BLOCK


def test_diff_adding_dangerous_line_blocks():
    """A diff ADDING an unsafe line still trips the block-pattern scan."""
    request = FourfoldActionWarrantRequest(
        actor_id="codex",
        action_type="governance_patch",
        intent="add cleanup command",
        content="+rm -rf ~/.dharma",
        metadata={"diff_bound": True},
    )

    warrant = evaluate_fourfold_warrant(request)

    assert warrant.verdict == WarrantVerdict.BLOCK
    assert "matched unsafe pattern" in warrant.rationale
