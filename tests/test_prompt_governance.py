from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.governance.verify_prompt_pack import (
    load_prompt_pack,
    validate_prompt_pack,
)


PACK = Path("docs/governance/prompt_packs/slop_cleanup_subagents.json")


def test_slop_cleanup_prompt_pack_is_valid() -> None:
    pack = load_prompt_pack(PACK)

    assert validate_prompt_pack(pack) == []


def test_partial_source_must_declare_missing_slides() -> None:
    pack = load_prompt_pack(PACK)
    broken = copy.deepcopy(pack)
    broken["source"].pop("known_missing_slides")

    errors = validate_prompt_pack(broken)

    assert "partial source must declare known_missing_slides" in errors


def test_lane_must_reference_declared_source_artifact() -> None:
    pack = load_prompt_pack(PACK)
    broken = copy.deepcopy(pack)
    broken["lanes"][0]["source_artifact"] = "missing.png"

    errors = validate_prompt_pack(broken)

    assert any("source_artifact is not declared" in error for error in errors)


def test_destructive_lane_requires_manual_review() -> None:
    pack = load_prompt_pack(PACK)
    broken = copy.deepcopy(pack)
    broken["lanes"][2]["manual_review_required"] = False

    errors = validate_prompt_pack(broken)

    assert any("destructive lane requires manual_review_required" in error for error in errors)


def test_source_hash_check_accepts_matching_file(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("prompt evidence", encoding="utf-8")
    sha = __import__("hashlib").sha256(artifact.read_bytes()).hexdigest()
    pack = {
        "schema_version": 1,
        "pack_id": "test-pack",
        "status": "advisory",
        "global_constraints": [
            "no_single_detector_blocks",
            "no_auto_delete",
            "no_auto_merge",
            "before_after_evidence_required",
        ],
        "gate_contract": {
            "before_agent_run": ["validate pack"],
            "after_agent_run": ["pytest targeted"],
        },
        "source": {
            "kind": "test",
            "completeness": "complete",
            "source_artifacts": [
                {
                    "filename": "artifact.txt",
                    "source_path": str(artifact),
                    "sha256": sha,
                }
            ],
        },
        "lanes": [
            {
                "lane_id": "sample",
                "title": "Sample Prompt",
                "source_artifact": "artifact.txt",
                "transcript": (
                    "Scan the target and report findings with enough evidence to reproduce them, "
                    "including the exact gate output and the source prompt artifact."
                ),
                "objective": "Report findings without mutating source.",
                "required_detectors": ["semgrep"],
                "required_gates": ["pytest targeted"],
                "allowed_actions": ["report"],
                "forbidden_actions": ["do not auto-delete"],
                "manual_review_required": True,
                "requires_blast_radius": False,
                "risk_level": "low",
            }
        ],
    }

    assert validate_prompt_pack(json.loads(json.dumps(pack)), check_source_files=True) == []
