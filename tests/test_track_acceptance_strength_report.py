from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))

import track_acceptance_strength_report as strength  # type: ignore  # noqa: E402
from check_track_status import RIGOROUS_KINDS  # type: ignore  # noqa: E402


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


def test_supported_rigorous_kinds_are_scored_from_main_checker() -> None:
    supported = set(strength.SUPPORTED_KINDS)
    assert RIGOROUS_KINDS <= supported
    assert {"test_passes", "receipt_valid", "commit_on_main", "pr_merged"} <= supported

    expectations = {
        "file_exists": 0,
        "file_contains": 1,
        "commit_on_main": 2,
        "json_collection_values_match": 2,
        "json_count_equals": 2,
        "json_count_greater_than": 2,
        "json_mapping_keys_nonempty": 2,
        "pr_merged": 2,
        "test_passes": 3,
        "receipt_valid": 5,
    }
    for kind, expected_strength in expectations.items():
        crit = {"id": kind, "kind": kind}
        if kind in {"file_exists", "file_contains", "receipt_valid"}:
            crit["file"] = "CLAUDE.md"
        if kind == "file_contains":
            crit["pattern"] = "dharma"
        if kind in {"json_count_equals", "json_count_greater_than"}:
            crit.update({
                "file": "reports/loop_closure/cybernetics_codex/latest_audit.json",
                "collection": "loop_statuses",
                "field": "verdict",
                "value": "CLOSED_LIVE",
            })
            if kind == "json_count_equals":
                crit["expected"] = 0
            else:
                crit["threshold"] = 0
        if kind == "json_collection_values_match":
            crit.update({
                "file": "reports/loop_closure/cybernetics_codex/latest_audit.json",
                "collection": "loop_statuses",
                "key_field": "number",
                "value_field": "verdict",
                "expected": {"1": "HARNESS_PROVEN"},
            })
        if kind == "json_mapping_keys_nonempty":
            crit.update({
                "file": "reports/loop_closure/cybernetics_codex/latest_audit.json",
                "mapping": "live_owner_surface_criteria",
                "keys": ["loop1"],
            })
        if kind == "commit_on_main":
            crit["commit"] = "deadbeef"
        if kind == "test_passes":
            crit["test"] = "tests/test_track_closure_rigor.py"
        if kind == "pr_merged":
            crit["pr"] = 1
        scored = strength.classify_criterion(crit, 0)
        assert scored.supported_by_status_checker is True
        assert scored.strength == expected_strength


def test_file_backed_loop_closure_downgrades_to_declaration_complete(tmp_path: Path) -> None:
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

    assert track["strongest_criterion_strength"] == 1
    assert track["weakest_criterion_strength"] == 0
    assert track["maturity_floor"] == 0
    assert track["maturity"] == "file present"
    assert track["thin_ratio"] == 1.0
    assert any(w["code"] == "closure_scope_claim" for w in track["warnings"])
    assert "declaration-complete" in track["recommended_claim"]
    assert "closure complete" in track["recommended_claim"]


def test_mixed_weak_and_strong_criteria_use_floor_not_max(tmp_path: Path) -> None:
    track_file = tmp_path / "ACTIVE_TRACK.yaml"
    _write_track_yaml(
        track_file,
        """  - id: runtime-spine-test
    name: Runtime Spine Adoption
    status: ACTIVE
    serves: substrate-nativeness
    completion_criteria:
      - id: manifest_exists
        kind: file_exists
        file: docs/runtime.md
      - id: runtime_receipt_valid
        kind: receipt_valid
        file: reports/governance/runtime_receipt.json
        requires_keys: [run_id, status]
""",
    )

    report = strength.build_report(track_file)
    track = report["tracks"][0]

    assert track["strongest_criterion_strength"] == 5
    assert track["weakest_criterion_strength"] == 0
    assert track["maturity_floor"] == 0
    assert track["maturity"] == "file present"
    assert any(w["code"] == "runtime_scope_claim" for w in track["warnings"])


def test_unsupported_kind_warns_and_does_not_suppress_claim_warning(tmp_path: Path) -> None:
    track_file = tmp_path / "ACTIVE_TRACK.yaml"
    _write_track_yaml(
        track_file,
        """  - id: runtime-thin
    name: Runtime Platform Truth
    status: ACTIVE
    serves: substrate-nativeness
    completion_criteria:
      - id: invented_runtime_receipt
        kind: runtime_receipt
        file: reports/runtime.json
""",
    )

    report = strength.build_report(track_file)
    track = report["tracks"][0]

    assert track["unsupported_kind_count"] == 1
    assert track["maturity_floor"] == 0
    codes = {w["code"] for w in track["warnings"]}
    assert "unsupported_by_status_checker" in codes
    assert "runtime_scope_claim" in codes
    assert "platform_scope_claim" in codes
    assert "truth_scope_claim" in codes


def test_malformed_and_non_dict_criteria_are_warned(tmp_path: Path) -> None:
    track_file = tmp_path / "ACTIVE_TRACK.yaml"
    track_file.write_text(
        """schema_version: 2
active_tracks:
  - id: malformed
    name: Malformed Runtime
    status: ACTIVE
    completion_criteria:
      - just-a-string
      - id: missing_test_target
        kind: test_passes
closed_tracks: []
""",
        encoding="utf-8",
    )

    report = strength.build_report(track_file)
    track = report["tracks"][0]

    assert track["criterion_count"] == 2
    assert track["maturity_floor"] == 0
    assert any(c["malformed"] for c in track["criteria"])
    assert any(w["code"] == "malformed_criteria" for w in track["warnings"])


def test_json_count_kinds_require_kind_specific_keys() -> None:
    base = {
        "id": "json-count",
        "file": "reports/loop_closure/cybernetics_codex/latest_audit.json",
        "collection": "loop_statuses",
        "field": "verdict",
        "value": "CLOSED_LIVE",
    }

    equals_missing_expected = strength.classify_criterion(
        {"kind": "json_count_equals", "threshold": 0, **base},
        0,
    )
    greater_missing_threshold = strength.classify_criterion(
        {"kind": "json_count_greater_than", "expected": 0, **base},
        1,
    )
    base_without_value = {k: v for k, v in base.items() if k != "value"}
    equals_missing_value = strength.classify_criterion(
        {"kind": "json_count_equals", "expected": 0, **base_without_value},
        2,
    )
    greater_missing_value = strength.classify_criterion(
        {"kind": "json_count_greater_than", "threshold": 0, **base_without_value},
        3,
    )
    equals_valid = strength.classify_criterion(
        {"kind": "json_count_equals", "expected": 0, **base},
        4,
    )
    greater_valid = strength.classify_criterion(
        {"kind": "json_count_greater_than", "threshold": 0, **base},
        5,
    )
    equals_missing_nested_value = strength.classify_criterion(
        {
            "kind": "json_count_equals",
            "expected": 0,
            "file": base["file"],
            "collection": base["collection"],
            "field": base["field"],
            "id": base["id"],
        },
        6,
    )
    greater_missing_nested_value = strength.classify_criterion(
        {
            "kind": "json_count_greater_than",
            "threshold": 0,
            "file": base["file"],
            "collection": base["collection"],
            "field": base["field"],
            "id": base["id"],
        },
        7,
    )

    assert equals_missing_expected.malformed is True
    assert greater_missing_threshold.malformed is True
    assert equals_missing_nested_value.malformed is True
    assert greater_missing_nested_value.malformed is True
    assert equals_valid.malformed is False
    assert greater_valid.malformed is False
    assert equals_missing_value.malformed is True
    assert greater_missing_value.malformed is True


def test_non_active_statuses_are_not_counted_as_active(tmp_path: Path) -> None:
    track_file = tmp_path / "ACTIVE_TRACK.yaml"
    _write_track_yaml(
        track_file,
        """  - id: active-one
    name: Active Truth
    status: ACTIVE
    completion_criteria:
      - id: doc
        kind: file_contains
        file: CLAUDE.md
        pattern: dharma
  - id: paused-one
    name: Paused Runtime
    status: PAUSED
    completion_criteria:
      - id: invented
        kind: runtime_receipt
""",
    )

    report = strength.build_report(track_file)

    assert report["summary"]["active_tracks"] == 1
    assert [t["id"] for t in report["tracks"]] == ["active-one"]


def test_cli_emits_json_and_strict_fails_on_warnings(tmp_path: Path) -> None:
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

    base_cmd = [
        sys.executable,
        "scripts/governance/track_acceptance_strength_report.py",
        "--track-file",
        str(track_file),
    ]
    default = subprocess.run(base_cmd + ["--json"], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    assert default.returncode == 0
    payload = json.loads(default.stdout)
    assert payload["summary"]["declaration_complete_tracks"] == 1
    assert payload["tracks"][0]["warnings"]

    strict = subprocess.run(base_cmd + ["--strict"], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    assert strict.returncode == 1
    assert "declaration-complete" in strict.stdout
