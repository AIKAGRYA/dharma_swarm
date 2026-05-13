from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "governance" / "kaizen_review_from_agentops.py"

spec = importlib.util.spec_from_file_location("kaizen_review_from_agentops", SCRIPT_PATH)
assert spec is not None
kaizen = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = kaizen
spec.loader.exec_module(kaizen)


def sample_report(**overrides: object) -> dict[str, object]:
    report: dict[str, object] = {
        "job_id": "job-green",
        "base_ref": "HEAD",
        "branch": "chore/example",
        "worktree": "/tmp/example",
        "intent": "Run a small AgentOps packet.",
        "status": "passed",
        "approval": {
            "before_commit": False,
            "before_merge": True,
        },
        "scope": {
            "tracked_changed_files": ["docs/example.md"],
            "staged_files": [],
            "untracked_files": [],
            "changed_files": ["docs/example.md"],
            "violations": [],
            "passed": True,
        },
        "gates": [
            {
                "name": "diff-check",
                "command": "git diff --check",
                "exit_code": 0,
                "passed": True,
                "timed_out": False,
                "duration_seconds": 0.1,
                "output": "",
            }
        ],
        "commit_hash": "abc123",
        "commit_decision": "commit permitted",
        "final_git_status": "",
    }
    report.update(overrides)
    return report


def write_agentops_report(root: Path, report: dict[str, object], *, job: str = "job") -> Path:
    path = root / "reports" / "agentops" / job / "20260505T000000000000Z" / "report.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def build_review(tmp_path: Path, *reports: dict[str, object]) -> dict[str, object]:
    paths = [
        write_agentops_report(tmp_path, report, job=f"job-{index}")
        for index, report in enumerate(reports)
    ]
    return kaizen.build_kaizen_review(paths, generated_at="2026-05-05T00:00:00+00:00")


def test_reads_minimal_agentops_report(tmp_path: Path) -> None:
    review = build_review(tmp_path, sample_report())

    assert review["jobs_reviewed"] == 1
    assert review["source_reports"][0]["job_id"] == "job-green"


def test_cli_produces_json_and_markdown_outputs(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports" / "agentops"
    write_agentops_report(tmp_path, sample_report())
    output_dir = tmp_path / "kaizen"

    exit_code = kaizen.main(["--input", str(reports_dir), "--output", str(output_dir)])

    assert exit_code == 0
    json_path = output_dir / "kaizen_review.json"
    md_path = output_dir / "kaizen_review.md"
    assert json_path.exists()
    assert md_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["jobs_reviewed"] == 1
    assert "# KaizenReview" in md_path.read_text(encoding="utf-8")


def test_summarizes_green_gates(tmp_path: Path) -> None:
    review = build_review(tmp_path, sample_report())

    assert review["gate_summary"]["all_green"] == 1
    assert review["gate_summary"]["some_red"] == 0
    assert review["source_reports"][0]["gate_classification"] == "all green"


def test_detects_red_gates(tmp_path: Path) -> None:
    report = sample_report(
        job_id="job-red",
        status="failed",
        gates=[
            {
                "name": "pytest",
                "exit_code": 1,
                "passed": False,
            }
        ],
        commit_hash=None,
        commit_decision="one or more gates failed",
    )
    review = build_review(tmp_path, report)

    assert review["gate_summary"]["some_red"] == 1
    assert review["gate_summary"]["failed_gates"] == {"pytest": 1}
    assert "failed gate (1 report)" in review["waste_patterns"]
    assert review["next_work_packet_recommendation"] == "fix failed gate"


def test_detects_scope_violations(tmp_path: Path) -> None:
    report = sample_report(
        job_id="job-scope",
        commit_hash=None,
        scope={
            "changed_files": ["api/main.py"],
            "violations": [
                {
                    "path": "api/main.py",
                    "reason": "outside_allowed_scope",
                    "patterns": [],
                }
            ],
            "passed": False,
        },
        commit_decision="scope gate failed",
    )
    review = build_review(tmp_path, report)

    assert review["scope_summary"]["violations"] == 1
    assert review["scope_summary"]["violation_files"] == ["api/main.py"]
    assert "out-of-scope files (1 report)" in review["waste_patterns"]
    assert review["next_work_packet_recommendation"] == "repeat with narrower allowed_files"


def test_detects_approval_before_commit_block(tmp_path: Path) -> None:
    report = sample_report(
        job_id="job-approval",
        commit_hash=None,
        approval={"before_commit": True, "before_merge": True},
        commit_decision="human approval required before commit",
    )
    review = build_review(tmp_path, report)

    assert review["commit_summary"]["blocked_by_approval"] == 1
    assert review["approval_summary"]["human_approval_needed"] == 1
    assert "approval blocked (1 report)" in review["waste_patterns"]


def test_human_yds_rating_is_null(tmp_path: Path) -> None:
    review = build_review(tmp_path, sample_report())

    assert review["human_yds_rating"] is None
    assert "Human-only" in review["yds_prompt_for_human"]


def test_human_yds_rating_ignores_report_embedded_values(tmp_path: Path) -> None:
    report = sample_report(human_yds_rating={"rating_value": "5.15"})

    review = build_review(tmp_path, report)

    assert review["human_yds_rating"] is None


def test_reads_matching_human_yds_rating_from_supplied_ledger(tmp_path: Path) -> None:
    report_path = write_agentops_report(tmp_path, sample_report())
    ledger = tmp_path / "human_quality_ratings.jsonl"
    rating = {
        "schema_version": "human_yds_rating.v1",
        "rating_id": "yds_20260505T000000Z_ab12cd34",
        "created_at": "2026-05-05T00:00:00Z",
        "operator_id": "dhyana",
        "rating_scale": "YDS",
        "rating_value": "5.12",
        "artifact": {
            "kind": "agentops_report",
            "uri": "external://" + report_path.as_posix(),
            "title": "AgentOps report",
        },
        "human_note": "Clean scoped packet.",
        "evidence_refs": [],
        "context": {"source": "operator_cli"},
        "supersedes_rating_id": None,
    }
    ledger.write_text(json.dumps(rating) + "\n", encoding="utf-8")

    review = kaizen.build_kaizen_review([report_path], yds_ledger=ledger)

    assert review["human_yds_rating"]["rating_count"] == 1
    assert review["human_yds_rating"]["ratings"][0]["rating_value"] == "5.12"


def test_supplied_ledger_without_match_keeps_human_yds_null(tmp_path: Path) -> None:
    report_path = write_agentops_report(tmp_path, sample_report())
    ledger = tmp_path / "human_quality_ratings.jsonl"
    rating = {
        "schema_version": "human_yds_rating.v1",
        "rating_id": "yds_20260505T000000Z_ab12cd34",
        "created_at": "2026-05-05T00:00:00Z",
        "operator_id": "dhyana",
        "rating_scale": "YDS",
        "rating_value": "5.12",
        "artifact": {
            "kind": "agentops_report",
            "uri": "repo://some/other/report.json",
            "title": "Other report",
        },
        "human_note": "Different artifact.",
        "evidence_refs": [],
        "context": {"source": "operator_cli"},
        "supersedes_rating_id": None,
    }
    ledger.write_text(json.dumps(rating) + "\n", encoding="utf-8")

    review = kaizen.build_kaizen_review([report_path], yds_ledger=ledger)

    assert review["human_yds_rating"] is None


def test_exactly_one_next_work_packet_recommendation(tmp_path: Path) -> None:
    review = build_review(tmp_path, sample_report())

    assert isinstance(review["next_work_packet_recommendation"], str)
    assert review["next_work_packet_recommendation"]


def test_does_not_require_existing_reports_on_disk(tmp_path: Path) -> None:
    report_path = write_agentops_report(tmp_path, sample_report())

    review = kaizen.build_kaizen_review([report_path])

    assert review["jobs_reviewed"] == 1


def test_does_not_call_mutating_git_commands() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "subprocess" not in source
    assert "os.system" not in source
    assert "git commit" not in source
    assert "git push" not in source
    assert "git merge" not in source
