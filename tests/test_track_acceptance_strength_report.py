from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))

import track_acceptance_strength_report as strength  # type: ignore  # noqa: E402


def _write_track_yaml(path: Path, track_block: str) -> None:
    path.write_text(
        f"""schema_version: 2
spine_objectives:
  - id: substrate-nativeness
    name: Substrate Nativeness
track_policy:
  max_active: 10
  warn_active: 5
active_tracks:
{track_block}
closed_tracks: []
""",
        encoding="utf-8",
    )


def test_file_backed_loop_closure_is_declared_shippable_only(tmp_path: Path) -> None:
    track_file = tmp_path / "ACTIVE_TRACK.yaml"
    _write_track_yaml(
        track_file,
        """  - id: loop-closure-test
    name: Loop Closure — wire all 13 loops
    status: ACTIVE
    serves: substrate-nativeness
    completion_criteria:
      - id: retrospective_exists
        kind: file_exists
        file: reports/loop_closure/RETROSPECTIVE.md
      - id: status_table_mentions_loops
        kind: file_contains
        file: reports/loop_closure/RETROSPECTIVE.md
        pattern: "Loop 1"
""",
    )

    report = strength.build_report(track_file)
    track = report["tracks"][0]

    assert track["max_strength"] == 1
    assert track["evidence_state"] == "declared-shippable"
    assert track["thin_ratio"] == 1.0
    assert any(w["code"] == "system_scope_closure" for w in track["warnings"])
    assert "do not claim loop/system closure complete" in track["recommended_claim"]


def test_runtime_receipt_criteria_can_support_system_shippable_language(tmp_path: Path) -> None:
    track_file = tmp_path / "ACTIVE_TRACK.yaml"
    _write_track_yaml(
        track_file,
        """  - id: runtime-spine-test
    name: Runtime Spine Adoption
    status: ACTIVE
    serves: substrate-nativeness
    completion_criteria:
      - id: runtime_receipt_exists
        kind: runtime_receipt
        file: reports/governance/runtime_receipt.json
      - id: adversarial_bypass_test
        kind: test
        test: tests/test_runtime_spine.py::test_rejects_bypass
""",
    )

    report = strength.build_report(track_file)
    track = report["tracks"][0]

    assert track["max_strength"] == 5
    assert track["evidence_state"] == "system-shippable"
    assert not any(w["code"] == "runtime_scope_claim" for w in track["warnings"])
    criteria = {c["id"]: c for c in track["criteria"]}
    assert criteria["adversarial_bypass_test"]["strength"] == 4


def test_cli_emits_json_and_exits_zero_by_default(tmp_path: Path) -> None:
    track_file = tmp_path / "ACTIVE_TRACK.yaml"
    _write_track_yaml(
        track_file,
        """  - id: thin-platform
    name: Platform Truth
    status: ACTIVE
    serves: substrate-nativeness
    completion_criteria:
      - id: doc_exists
        kind: file_exists
        file: docs/platform.md
""",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/governance/track_acceptance_strength_report.py",
            "--track-file",
            str(track_file),
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["thin_declared_tracks"] == 1
    assert payload["tracks"][0]["warnings"]


def test_strict_mode_fails_on_warnings(tmp_path: Path) -> None:
    track_file = tmp_path / "ACTIVE_TRACK.yaml"
    _write_track_yaml(
        track_file,
        """  - id: runtime-thin
    name: Runtime Thing
    status: ACTIVE
    serves: substrate-nativeness
    completion_criteria:
      - id: doc_exists
        kind: file_exists
        file: docs/runtime.md
""",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/governance/track_acceptance_strength_report.py",
            "--track-file",
            str(track_file),
            "--strict",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "declared-shippable" in result.stdout
