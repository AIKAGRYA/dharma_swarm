from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/runtime/long_running_harness.py"


def load_module():
    spec = importlib.util.spec_from_file_location("long_running_harness", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_active_track(repo: Path) -> None:
    path = repo / "docs/governance/ACTIVE_TRACK.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        """
schema_version: 2
active_tracks:
  - id: command-plane-phase-2-context-shell-2026-05
    primary: true
    name: Command Plane Phase 2 Context Shell
    status: ACTIVE
closed_tracks: []
""".lstrip(),
        encoding="utf-8",
    )


def test_init_command_plane_run_creates_required_artifacts(tmp_path):
    module = load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    write_active_track(repo)
    state = tmp_path / "state"

    rc = module.main([
        "--repo-root",
        str(repo),
        "--state-root",
        str(state),
        "init",
        "--run-id",
        "cp-context-shell",
        "--mode",
        "command-plane",
        "--goal",
        "Command-plane PR 2 context shell",
    ])

    assert rc == 0
    root = state / "cp-context-shell"
    for artifact in module.REQUIRED_ARTIFACTS:
        assert (root / artifact).exists(), artifact

    run = json.loads((root / "run.json").read_text())
    assert run["active_track"]["id"] == "command-plane-phase-2-context-shell-2026-05"
    assert run["mode"] == "command-plane"
    assert run["harness_standard"]["id"] == "pge"
    assert run["harness_standard"]["min_contract_criteria"] >= 20

    contract = json.loads((root / "contracts/contract.json").read_text())
    assert contract["status"] == "draft"
    assert len(contract["criteria"]) >= 20
    assert any("No new route" in item for item in contract["criteria"])
    assert any("self-assessment" in item.lower() or "separate roles" in item.lower() for item in contract["criteria"])


def test_validate_fails_when_required_artifact_missing(tmp_path):
    module = load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    write_active_track(repo)
    state = tmp_path / "state"

    assert module.main([
        "--repo-root",
        str(repo),
        "--state-root",
        str(state),
        "init",
        "--run-id",
        "missing-artifact",
        "--goal",
        "Missing artifact test",
    ]) == 0

    (state / "missing-artifact" / "handoff/HANDOFF.md").unlink()

    rc = module.main([
        "--repo-root",
        str(repo),
        "--state-root",
        str(state),
        "validate",
        "--run-id",
        "missing-artifact",
    ])

    assert rc == 3


def test_validate_contract_phase_fails_until_contract_is_accepted(tmp_path):
    module = load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    write_active_track(repo)
    state = tmp_path / "state"

    assert module.main([
        "--repo-root",
        str(repo),
        "--state-root",
        str(state),
        "init",
        "--run-id",
        "draft-contract",
        "--goal",
        "Draft contract test",
    ]) == 0

    assert module.main([
        "--repo-root",
        str(repo),
        "--state-root",
        str(state),
        "validate",
        "--run-id",
        "draft-contract",
        "--phase",
        "scaffold",
    ]) == 0

    assert module.main([
        "--repo-root",
        str(repo),
        "--state-root",
        str(state),
        "validate",
        "--run-id",
        "draft-contract",
        "--phase",
        "contract",
    ]) == 3
