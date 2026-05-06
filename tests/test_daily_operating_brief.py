from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.daily_operating_brief import (
    DailyOperatingBriefInputs,
    build_daily_operating_brief,
    render_markdown,
    write_daily_operating_brief,
)


REQUIRED_SECTIONS = [
    "## 1. What happened",
    "## 2. Gate health",
    "## 3. Value produced",
    "## 4. Burn / cost signals",
    "## 5. Human YDS ratings",
    "## 6. Revenue / self-funding moves",
    "## 7. Stop doing",
    "## 8. Next highest-leverage move",
    "## 9. Doc drift / claim integrity",
    "## 10. Missing sources",
]


def test_produces_markdown_with_all_required_sections(tmp_path: Path) -> None:
    brief = build_daily_operating_brief(DailyOperatingBriefInputs())

    markdown = render_markdown(brief)

    for section in REQUIRED_SECTIONS:
        assert section in markdown


def test_gracefully_handles_all_sources_missing() -> None:
    brief = build_daily_operating_brief(DailyOperatingBriefInputs())
    markdown = render_markdown(brief)

    assert "No AgentOps reports found." in markdown
    assert "No KaizenReview reports found." in markdown
    assert "No human YDS ratings found." in markdown
    assert "No burn source found." in markdown
    assert "No revenue source found." in markdown
    assert "No DocOps integrity report found." in markdown


def test_reads_one_agentops_report_and_summarizes_gate_health(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports" / "agentops"
    _write_agentops_report(reports_dir, job_id="job-green")

    brief = build_daily_operating_brief(
        DailyOperatingBriefInputs(agentops_reports_dir=reports_dir)
    )

    assert any("AgentOps `job-green` ended `passed`" in line for line in brief.what_happened)
    assert any("all green" in line for line in brief.gate_health)
    assert any("abc123" in line for line in brief.value_produced)


def test_reads_failed_gate_and_marks_gate_health_not_all_green(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports" / "agentops"
    _write_agentops_report(
        reports_dir,
        job_id="job-red",
        status="failed",
        gates=[{"name": "pytest", "exit_code": 2, "passed": False}],
    )

    brief = build_daily_operating_brief(
        DailyOperatingBriefInputs(agentops_reports_dir=reports_dir)
    )

    assert any("not all green" in line for line in brief.gate_health)
    assert any("Stop integrating `job-red`" in line for line in brief.stop_doing)


def test_reads_kaizen_review_from_agentops_bridge_output(tmp_path: Path) -> None:
    kaizen_dir = tmp_path / "reports" / "kaizen" / "kaizen-v0"
    kaizen_dir.mkdir(parents=True)
    (kaizen_dir / "kaizen_review.json").write_text(
        json.dumps(
            {
                "id": "kaizen-v0",
                "title": "KaizenReview for kaizen-v0",
                "status": "recorded",
                "quality_score": 0.82,
                "human_yds_rating": None,
            }
        ),
        encoding="utf-8",
    )

    brief = build_daily_operating_brief(
        DailyOperatingBriefInputs(kaizen_reports_dir=tmp_path / "reports" / "kaizen")
    )

    rendered = render_markdown(brief)
    assert "KaizenReview `KaizenReview for kaizen-v0` recorded, advisory score `0.82`." in rendered


def test_reads_human_yds_jsonl_rating_and_includes_it(tmp_path: Path) -> None:
    yds_path = tmp_path / "yds.jsonl"
    yds_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-05-05T01:00:00Z",
                "rating": "5.10a",
                "artifact": "daily-brief-v0",
                "human_comment": "clear and useful",
                "source": "human_operator",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    brief = build_daily_operating_brief(
        DailyOperatingBriefInputs(yds_ratings_path=yds_path)
    )

    rendered = render_markdown(brief)
    assert "`daily-brief-v0` rated `5.10a`" in rendered
    assert "clear and useful" in rendered


def test_does_not_treat_ai_or_self_yds_as_authoritative(tmp_path: Path) -> None:
    yds_path = tmp_path / "yds.jsonl"
    yds_path.write_text(
        json.dumps(
            {
                "rating": "5.13d",
                "artifact": "self-score",
                "source": "ai_self_grader",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    brief = build_daily_operating_brief(
        DailyOperatingBriefInputs(yds_ratings_path=yds_path)
    )

    rendered = render_markdown(brief)
    assert "No human YDS ratings found." in rendered
    assert "Advisory only" in rendered
    assert "`self-score` rated `5.13d`" in rendered


def test_reads_simple_cost_json_when_provided(tmp_path: Path) -> None:
    cost_path = tmp_path / "cost.json"
    cost_path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "provider": "openrouter",
                        "model": "claude-sonnet",
                        "input_tokens": 1000,
                        "output_tokens": 500,
                        "estimated_cost_usd": 0.0123,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    brief = build_daily_operating_brief(
        DailyOperatingBriefInputs(cost_report_path=cost_path)
    )

    rendered = render_markdown(brief)
    assert "$0.0123 observed" in rendered
    assert "1,500 token(s)" in rendered
    assert "openrouter / claude-sonnet" in rendered


def test_reads_simple_cost_jsonl_when_provided(tmp_path: Path) -> None:
    cost_path = tmp_path / "cost.jsonl"
    cost_path.write_text(
        json.dumps({"cost_usd": 0.1, "tokens": 42, "task_id": "brief"}) + "\n",
        encoding="utf-8",
    )

    brief = build_daily_operating_brief(
        DailyOperatingBriefInputs(cost_report_path=cost_path)
    )

    rendered = render_markdown(brief)
    assert "$0.1000 observed" in rendered
    assert "42 token(s)" in rendered


def test_reads_llm_burn_state_dir_when_explicitly_provided(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports" / "agentops"
    _write_agentops_report(reports_dir, job_id="job-green")
    state = tmp_path / ".dharma"
    traces = state / "traces"
    traces.mkdir(parents=True)
    now = datetime(2026, 5, 9, 1, tzinfo=timezone.utc)
    (state / "cost_log.jsonl").write_text(
        json.dumps(
            {
                "timestamp": now.timestamp(),
                "provider": "openai",
                "model": "gpt-4o",
                "input_tokens": 100,
                "output_tokens": 50,
                "estimated_cost_usd": 0.000625,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (traces / "traces_2026-05-09.jsonl").write_text(
        json.dumps(
            {
                "trace_id": "trace-1",
                "span_id": "span-1",
                "kind": "agent_dispatch",
                "status": "error",
                "end_time": now.isoformat(),
                "attributes": {"success": False, "error": "provider failed"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    brief = build_daily_operating_brief(
        DailyOperatingBriefInputs(
            agentops_reports_dir=reports_dir,
            llm_burn_state_dir=state,
            now=now,
        )
    )

    rendered = render_markdown(brief)
    assert "OpenInference-style LLM burn spans: 2 span(s)" in rendered
    assert "estimated=$0.0006" in rendered
    assert "zero-token=1" in rendered
    assert "unpriced=1" in rendered
    assert "Close the unpriced LLM span gap" in rendered


def test_reads_simple_revenue_notes_when_provided(tmp_path: Path) -> None:
    notes_path = tmp_path / "revenue.md"
    notes_path.write_text(
        "- Customer wedge: sell a daily operating cockpit audit.\n"
        "- Random note without signal.\n"
        "- Stripe checkout remains deferred.\n",
        encoding="utf-8",
    )

    brief = build_daily_operating_brief(
        DailyOperatingBriefInputs(revenue_notes_path=notes_path)
    )

    rendered = render_markdown(brief)
    assert "Customer wedge" in rendered
    assert "Stripe checkout" in rendered
    assert "Random note without signal" not in rendered


def test_reads_docops_report_and_renders_claim_integrity_section(tmp_path: Path) -> None:
    report_path = tmp_path / "reports" / "docops" / "check.json"
    inventory_path = tmp_path / "reports" / "docops" / "corpus_inventory.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps(
            {
                "date": "2026-05-06",
                "passed": True,
                "failure_count": 0,
                "warning_count": 1,
                "metrics": {
                    "markdown_files": 632,
                    "authority_candidate_docs": 259,
                    "doc_assertions": 12,
                },
                "findings": [],
            }
        ),
        encoding="utf-8",
    )
    inventory_path.write_text(
        json.dumps(
            {
                "absolute_path_ref_count": 1516,
                "broken_path_ref_count": 0,
                "canonical_claim_count": 74,
            }
        ),
        encoding="utf-8",
    )

    brief = build_daily_operating_brief(
        DailyOperatingBriefInputs(
            docops_check_report_path=report_path,
            docops_inventory_path=inventory_path,
        )
    )

    rendered = render_markdown(brief)
    assert "## 9. Doc drift / claim integrity" in rendered
    assert "DocOps integrity passed on 2026-05-06: 0 failure(s), 1 warning(s)." in rendered
    assert "632 markdown file(s)" in rendered
    assert "259 authority-candidate doc(s)" in rendered
    assert "1516 absolute path reference(s)" in rendered
    assert "74 canonical/source-of-truth claim(s)" in rendered


def test_failed_docops_report_becomes_conservative_next_move(tmp_path: Path) -> None:
    report_path = tmp_path / "check.json"
    inventory_path = tmp_path / "corpus_inventory.json"
    report_path.write_text(
        json.dumps(
            {
                "passed": False,
                "failure_count": 2,
                "warning_count": 3,
                "findings": [
                    {
                        "rule_id": "path-exists",
                        "path": "docs/example.md",
                        "message": "referenced path missing",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    inventory_path.write_text(json.dumps({"path_ref_count": 4}), encoding="utf-8")

    brief = build_daily_operating_brief(
        DailyOperatingBriefInputs(
            agentops_reports_dir=_green_agentops_dir(tmp_path),
            docops_check_report_path=report_path,
            docops_inventory_path=inventory_path,
        )
    )

    rendered = render_markdown(brief)
    assert "DocOps integrity failed: 2 failure(s), 3 warning(s)." in rendered
    assert "DocOps finding: path-exists - docs/example.md - referenced path missing." in rendered
    assert (
        "Fix DocOps integrity failures before adding or promoting more documentation."
        in rendered
    )


def test_writes_markdown_to_explicit_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "briefs" / "today.md"

    result = write_daily_operating_brief(DailyOperatingBriefInputs(), output_path)

    assert result == output_path
    assert output_path.exists()
    assert "# Daily Operating Brief" in output_path.read_text(encoding="utf-8")


def test_does_not_require_dharma_home_or_live_runtime_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(fake_home))

    brief = build_daily_operating_brief(DailyOperatingBriefInputs())

    assert "No AgentOps reports found." in render_markdown(brief)
    assert not (fake_home / ".dharma").exists()


def _write_agentops_report(
    root: Path,
    *,
    job_id: str,
    status: str = "passed",
    gates: list[dict[str, object]] | None = None,
) -> Path:
    report_dir = root / job_id / "20260505T000000000000Z"
    report_dir.mkdir(parents=True)
    report = {
        "job_id": job_id,
        "branch": "chore/example",
        "worktree": "/tmp/example",
        "status": status,
        "commit_hash": "abc123" if status == "passed" else None,
        "scope": {
            "passed": status == "passed",
            "changed_files": ["dharma_swarm/example.py"],
            "violations": [],
        },
        "gates": gates
        if gates is not None
        else [{"name": "pytest", "exit_code": 0, "passed": True}],
    }
    path = report_dir / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def _green_agentops_dir(tmp_path: Path) -> Path:
    reports_dir = tmp_path / "reports" / "agentops"
    _write_agentops_report(reports_dir, job_id="job-green")
    return reports_dir
