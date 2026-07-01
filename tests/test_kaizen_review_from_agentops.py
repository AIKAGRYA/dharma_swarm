from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path("scripts/governance/kaizen_review_from_agentops.py")


def _write_agentops_report(
    root: Path,
    *,
    job_id: str,
    status: str,
    scope_passed: bool,
    gates: list[dict[str, object]],
    commit_hash: str | None = None,
    commit_decision: str = "not evaluated",
    runtime_refs: dict[str, object] | None = None,
) -> Path:
    report_dir = root / job_id / "20260506T000000000000Z"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "job_id": job_id,
        "status": status,
        "branch": "chore/example",
        "worktree": "/tmp/example",
        "scope": {
            "passed": scope_passed,
            "changed_files": ["dharma_swarm/example.py"],
            "violations": [] if scope_passed else [{"path": "api/main.py"}],
        },
        "gates": gates,
        "commit_hash": commit_hash,
        "commit_decision": commit_decision,
    }
    if runtime_refs:
        payload.update(runtime_refs)
    path = report_dir / "report.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
timeout=30,
)


def test_bridge_generates_json_and_markdown_from_reports_directory(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "agentops"
    _write_agentops_report(
        reports_root,
        job_id="job-green",
        status="passed",
        scope_passed=True,
        gates=[{"name": "pytest", "exit_code": 0, "passed": True}],
        commit_hash="abc123",
        commit_decision="commit permitted",
    )
    _write_agentops_report(
        reports_root,
        job_id="job-red",
        status="failed",
        scope_passed=False,
        gates=[{"name": "pytest", "exit_code": 2, "passed": False}],
        commit_hash=None,
        commit_decision="human approval required before commit",
    )

    result = _run_cli(
        str(reports_root),
        "--id",
        "kaizen-v0",
        "--output-root",
        str(tmp_path / "reports" / "kaizen"),
        cwd=Path.cwd(),
    )
    assert result.returncode == 0, result.stderr

    review_dir = tmp_path / "reports" / "kaizen" / "kaizen-v0"
    json_path = review_dir / "kaizen_review.json"
    md_path = review_dir / "kaizen_review.md"
    assert json_path.exists()
    assert md_path.exists()

    review = json.loads(json_path.read_text(encoding="utf-8"))
    assert review["summary"]["jobs"] == 2
    assert review["jobs_reviewed"] == 2
    assert len(review["source_reports"]) == 2
    assert review["gate_summary"] == review["summary"]["gate_counts"]
    assert review["scope_summary"] == review["summary"]["scope_counts"]
    assert review["commit_summary"] == review["summary"]["commit_counts"]
    assert review["approval_summary"]["human_approval_needed"] == 1
    assert review["runtime_truth_summary"]["jobs_with_refs"] == 0
    assert review["runtime_truth_summary"]["jobs_without_refs"] == 2
    assert review["runtime_truth_refs"] == []
    assert review["summary"]["gate_counts"]["green"] == 1
    assert review["summary"]["gate_counts"]["red"] == 1
    assert review["summary"]["scope_counts"]["clean"] == 1
    assert review["summary"]["scope_counts"]["violation"] == 1
    assert review["summary"]["commit_counts"]["created"] == 1
    assert review["summary"]["commit_counts"]["approval_blocked"] == 1
    assert review["what_worked"]
    assert review["what_failed"]
    assert review["playbook_update_candidates"]
    assert review["human_yds_rating"] is None
    assert review["yds_prompt_for_human"]
    assert isinstance(review["next_work_packet_recommendation"], str)
    assert review["next_work_packet_recommendation"].strip() != ""

    markdown = md_path.read_text(encoding="utf-8")
    assert "## Runtime Truth References" in markdown
    assert "No runtime truth reference keys were present" in markdown
    assert "## Human YDS Boundary" in markdown
    assert "AI does not assign authoritative YDS ratings." in markdown


def test_bridge_copies_runtime_truth_refs_without_inventing_authority(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "agentops"
    _write_agentops_report(
        reports_root,
        job_id="job-traced",
        status="passed",
        scope_passed=True,
        gates=[{"name": "pytest", "exit_code": 0, "passed": True}],
        commit_hash="abc123",
        runtime_refs={
            "trace_id": "trace-1",
            "correlation_id": "corr-1",
            "receipt_refs": ["receipt://agentops/job-traced"],
            "identity_invariant_digest": "identity-digest-1",
            "runtime_truth": {"nats_contact": "HANDLER_ACKED"},
        },
    )

    result = _run_cli(
        str(reports_root),
        "--id",
        "kaizen-runtime",
        "--output-root",
        str(tmp_path / "reports" / "kaizen"),
        cwd=Path.cwd(),
    )
    assert result.returncode == 0, result.stderr

    review_path = tmp_path / "reports" / "kaizen" / "kaizen-runtime" / "kaizen_review.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))

    assert review["runtime_truth_summary"] == {
        "jobs_with_refs": 1,
        "jobs_without_refs": 0,
        "ref_keys": [
            "correlation_id",
            "identity_invariant_digest",
            "receipt_refs",
            "runtime_truth",
            "trace_id",
        ],
    }
    assert review["jobs"][0]["runtime_truth_refs"]["trace_id"] == "trace-1"
    assert review["runtime_truth_refs"][0]["refs"]["receipt_refs"] == [
        "receipt://agentops/job-traced"
    ]
    assert review["human_yds_rating"] is None


def test_bridge_accepts_explicit_report_file_inputs(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "agentops"
    first = _write_agentops_report(
        reports_root,
        job_id="job-a",
        status="passed",
        scope_passed=True,
        gates=[{"name": "lint", "exit_code": 0, "passed": True}],
    )
    second = _write_agentops_report(
        reports_root,
        job_id="job-b",
        status="passed",
        scope_passed=True,
        gates=[{"name": "pytest", "exit_code": 0, "passed": True}],
    )

    result = _run_cli(
        str(first),
        str(second),
        "--id",
        "kaizen-files",
        "--output-root",
        str(tmp_path / "reports" / "kaizen"),
        cwd=Path.cwd(),
    )
    assert result.returncode == 0, result.stderr

    review = json.loads(
        (tmp_path / "reports" / "kaizen" / "kaizen-files" / "kaizen_review.json").read_text(
            encoding="utf-8"
        )
    )
    assert review["summary"]["jobs"] == 2
    assert len(review["jobs"]) == 2


def test_bridge_fails_when_no_reports_found(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir(parents=True)
    result = _run_cli(str(empty_dir), cwd=Path.cwd())
    assert result.returncode == 2
    assert "no agentops report.json inputs found" in result.stdout.lower()
