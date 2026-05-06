from __future__ import annotations

from pathlib import Path


def test_insight_brief_is_canonical_daily_brief_surface_on_this_branch() -> None:
    doc = Path(
        "docs/governance/CANONICAL_DAILY_BRIEF_WRITER_2026-05-02.md"
    ).read_text(encoding="utf-8")

    assert "`dharma_swarm.insight_brief` is the canonical" in doc
    assert "`operator_brief` from PR57 is parked" in doc
    assert "DHARMA_OPERATOR_BRIEF_ENABLED" in doc


def test_parked_operator_brief_package_is_not_active_on_this_branch() -> None:
    assert Path("dharma_swarm/insight_brief.py").is_file()
    assert not Path("dharma_swarm/operator_brief").exists()


def test_cron_dispatch_uses_canonical_insight_brief_handler() -> None:
    cron_runner = Path("dharma_swarm/cron_runner.py").read_text(encoding="utf-8")

    assert 'if handler == "insight_brief":' in cron_runner
    assert "return _run_insight_brief(job)" in cron_runner
    assert 'handler == "operator_brief"' not in cron_runner


def test_canonical_insight_brief_records_publish_action_history() -> None:
    insight_brief = Path("dharma_swarm/insight_brief.py").read_text(encoding="utf-8")
    existing_test = Path("tests/test_insight_brief.py").read_text(encoding="utf-8")

    assert "execute_action_or_fail(" in insight_brief
    assert '"KnowledgeArtifact"' in insight_brief
    assert '"Publish"' in insight_brief
    assert "registry.action_history(brief.id, \"Publish\")" in existing_test
