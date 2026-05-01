"""Tests for campaigns — durable campaign memory for the governance loop."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dharma_swarm.campaigns import (
    active_primary,
    campaign_from_promise,
    complete_campaign,
    create_campaign,
    find_by_agent,
    find_campaign,
    find_campaign_domain,
    list_stale,
    load_active,
    mark_check_in,
    mark_task_check_in,
    promise_id_from_text,
    release_campaign,
    save_active,
    set_primary,
)


@pytest.fixture
def meta_dir(tmp_path: Path) -> Path:
    d = tmp_path / "meta"
    d.mkdir()
    return d


def test_create_and_load_roundtrip(meta_dir: Path) -> None:
    c = create_campaign(
        "neurips",
        "artifact_publication",
        ["conductor_claude"],
        title="NeurIPS abstract",
        success_criteria="abstract_submitted",
        deadline="2026-05-04T23:59Z",
        meta_dir=meta_dir,
    )
    assert c["campaign_id"] == "neurips"
    active = load_active(meta_dir)
    assert len(active) == 1
    assert active[0]["status"] == "active"
    assert active[0]["check_in_count"] == 0


def test_create_is_idempotent(meta_dir: Path) -> None:
    create_campaign("c", "research", ["a"], meta_dir=meta_dir)
    create_campaign("c", "research", ["b"], meta_dir=meta_dir)
    assert len(load_active(meta_dir)) == 1


def test_mark_check_in_appends_marker(meta_dir: Path) -> None:
    create_campaign("c", "research", ["agent_a"], meta_dir=meta_dir)
    updated = mark_check_in("c", "agent_a", note="Progress: step 1", meta_dir=meta_dir)
    assert updated is not None
    assert updated["check_in_count"] == 1
    assert len(updated["progress_markers"]) == 1
    assert updated["progress_markers"][0]["agent"] == "agent_a"


def test_mark_check_in_missing_returns_none(meta_dir: Path) -> None:
    assert mark_check_in("nope", "agent", meta_dir=meta_dir) is None


def test_mark_task_check_in_records_task_context(meta_dir: Path) -> None:
    create_campaign("c", "research", ["agent_a"], meta_dir=meta_dir)
    updated = mark_task_check_in(
        "c",
        task_id="task-123",
        task_title="Campaign nurture: Alpha",
        task_status="completed",
        agent="agent_a",
        note="wrote durable next-step artifact",
        meta_dir=meta_dir,
    )
    assert updated is not None
    marker = updated["progress_markers"][-1]
    assert marker["source"] == "task_board"
    assert marker["task_id"] == "task-123"
    assert marker["task_status"] == "completed"
    assert "wrote durable next-step artifact" in marker["note"]


def test_complete_migrates_to_history(meta_dir: Path) -> None:
    create_campaign("c", "research", ["a"], meta_dir=meta_dir)
    done = complete_campaign("c", outcome="shipped it", meta_dir=meta_dir)
    assert done is not None
    assert done["status"] == "completed"
    assert done["outcome"] == "shipped it"
    assert load_active(meta_dir) == []

    history_path = meta_dir / "campaign_history.jsonl"
    assert history_path.exists()
    lines = history_path.read_text().strip().splitlines()
    record = json.loads(lines[-1])
    assert record["campaign_id"] == "c"


def test_release_agent_keeps_campaign_when_others_remain(meta_dir: Path) -> None:
    create_campaign("c", "research", ["a", "b"], meta_dir=meta_dir)
    out = release_campaign("c", "a", meta_dir=meta_dir)
    assert out is not None
    assert out["pinned_agents"] == ["b"]
    assert load_active(meta_dir)  # still active


def test_release_last_agent_closes_campaign(meta_dir: Path) -> None:
    create_campaign("c", "research", ["a"], meta_dir=meta_dir)
    out = release_campaign("c", "a", meta_dir=meta_dir)
    assert out is not None
    assert out["status"] == "abandoned"
    assert load_active(meta_dir) == []


def test_release_without_agent_closes_campaign(meta_dir: Path) -> None:
    create_campaign("c", "research", ["a", "b"], meta_dir=meta_dir)
    out = release_campaign("c", None, meta_dir=meta_dir)
    assert out is not None
    assert out["status"] == "abandoned"
    assert load_active(meta_dir) == []


def test_find_by_agent_returns_multiple(meta_dir: Path) -> None:
    create_campaign("c1", "research", ["a"], meta_dir=meta_dir)
    create_campaign("c2", "reliability", ["a", "b"], meta_dir=meta_dir)
    create_campaign("c3", "productization", ["b"], meta_dir=meta_dir)
    for_a = find_by_agent("a", meta_dir)
    assert {c["campaign_id"] for c in for_a} == {"c1", "c2"}


def test_find_campaign_domain_lookup(meta_dir: Path) -> None:
    create_campaign("c", "revenue_exploration", ["a"], meta_dir=meta_dir)
    assert find_campaign_domain("c", meta_dir) == "revenue_exploration"
    assert find_campaign_domain("missing", meta_dir) is None


def test_list_stale_filters_by_elapsed(meta_dir: Path) -> None:
    create_campaign("fresh", "research", ["a"], meta_dir=meta_dir)
    create_campaign("stale", "research", ["a"], meta_dir=meta_dir)
    # Manually backdate stale
    active = load_active(meta_dir)
    for c in active:
        if c["campaign_id"] == "stale":
            c["last_check_in"] = (
                datetime.now(timezone.utc) - timedelta(hours=10)
            ).isoformat()
    save_active(active, meta_dir)

    stale = list_stale(
        executive_interval_s=2700.0,
        staleness_factor=2.0,
        meta_dir=meta_dir,
    )
    ids = {c["campaign_id"] for c in stale}
    assert ids == {"stale"}


def test_promise_id_is_stable(tmp_path: Path) -> None:
    p1 = promise_id_from_text("Run R_V experiment (Mistral-7B)")
    p2 = promise_id_from_text("run r_v experiment (mistral-7b)   ")
    assert p1 == p2


def test_campaign_from_promise_creates_linked_record(meta_dir: Path) -> None:
    c = campaign_from_promise(
        "Run R_V experiment (Mistral-7B)",
        agent="conductor_claude",
        domain="research",
        meta_dir=meta_dir,
    )
    assert c["source"] == "promise"
    assert c["linked_promise"].startswith("promise_")
    assert c["campaign_id"].startswith("camp_")
    assert find_campaign(c["campaign_id"], meta_dir) is not None


def test_load_active_ignores_malformed_file(meta_dir: Path) -> None:
    (meta_dir / "active_campaigns.json").write_text("{not json")
    assert load_active(meta_dir) == []


def test_load_active_normalizes_legacy_campaign_envelope(meta_dir: Path) -> None:
    (meta_dir / "active_campaigns.json").write_text(
        json.dumps(
            {
                "primary_campaign": "startup_world_facing",
                "campaigns": [
                    {
                        "name": "startup_world_facing",
                        "priority": "primary",
                        "status": "active",
                        "artifact_path": "/tmp/startup_world_facing.md",
                        "last_updated": "2026-04-30T00:30:00Z",
                    }
                ],
            }
        ),
    )
    active = load_active(meta_dir)
    assert len(active) == 1
    assert active[0]["campaign_id"] == "startup_world_facing"
    assert active[0]["primary"] is True
    assert active[0]["last_check_in"] == "2026-04-30T00:30:00Z"
    assert active[0]["artifact_path"] == "/tmp/startup_world_facing.md"
    assert active[0]["pinned_agents"] == []


def test_save_active_is_atomic(meta_dir: Path) -> None:
    create_campaign("c", "research", ["a"], meta_dir=meta_dir)
    assert not list((meta_dir).glob("*.tmp"))  # atomic write cleans up


# ---------------------------------------------------------------------------
# active_primary — Phase 1 helper (soft-primary today, hard primary Phase 4)
# ---------------------------------------------------------------------------


def test_active_primary_none_when_no_campaigns(meta_dir: Path) -> None:
    assert active_primary(meta_dir) is None


def test_active_primary_returns_sole_active_as_soft_primary(meta_dir: Path) -> None:
    create_campaign("lone", "research", ["a"], meta_dir=meta_dir)
    p = active_primary(meta_dir)
    assert p is not None
    assert p["campaign_id"] == "lone"


def test_active_primary_prefers_earliest_created_as_soft(meta_dir: Path) -> None:
    create_campaign("first", "research", ["a"], meta_dir=meta_dir)
    create_campaign("second", "reliability", ["b"], meta_dir=meta_dir)
    # Clear explicit primaries, then force second to have an earlier created ts.
    active = load_active(meta_dir)
    for c in active:
        c["primary"] = False
        if c["campaign_id"] == "first":
            c["created"] = "2026-04-14T09:00:00+00:00"
        if c["campaign_id"] == "second":
            c["created"] = "2026-04-13T09:00:00+00:00"
    save_active(active, meta_dir)
    p = active_primary(meta_dir)
    assert p["campaign_id"] == "second"


def test_active_primary_explicit_primary_beats_soft(meta_dir: Path) -> None:
    create_campaign("first", "research", ["a"], meta_dir=meta_dir)
    create_campaign("marked", "reliability", ["b"], meta_dir=meta_dir)
    # Demote the default primary and mark "marked" as primary=True.
    active = load_active(meta_dir)
    for c in active:
        if c["campaign_id"] == "first":
            c["primary"] = False
        if c["campaign_id"] == "marked":
            c["primary"] = True
    save_active(active, meta_dir)
    p = active_primary(meta_dir)
    assert p["campaign_id"] == "marked"


def test_active_primary_skips_non_active_status(meta_dir: Path) -> None:
    create_campaign("alpha", "research", ["a"], meta_dir=meta_dir)
    # Manually mark as abandoned
    active = load_active(meta_dir)
    active[0]["status"] = "abandoned"
    save_active(active, meta_dir)
    assert active_primary(meta_dir) is None


def test_create_campaign_marks_first_campaign_primary(meta_dir: Path) -> None:
    first = create_campaign("first", "research", ["a"], meta_dir=meta_dir)
    second = create_campaign("second", "reliability", ["b"], meta_dir=meta_dir)
    assert first["primary"] is True
    assert second["primary"] is False
    primary = active_primary(meta_dir)
    assert primary is not None
    assert primary["campaign_id"] == "first"


def test_set_primary_enforces_single_winner(meta_dir: Path) -> None:
    create_campaign("first", "research", ["a"], meta_dir=meta_dir)
    create_campaign("second", "reliability", ["b"], meta_dir=meta_dir)
    updated = set_primary("second", meta_dir=meta_dir)
    assert updated is not None
    active = load_active(meta_dir)
    assert sum(1 for c in active if c.get("primary") is True) == 1
    assert active_primary(meta_dir)["campaign_id"] == "second"


def test_create_campaign_assigns_default_artifact_path(meta_dir: Path) -> None:
    created = create_campaign("artifactful", "research", ["a"], meta_dir=meta_dir)
    assert created["artifact_path"] == "~/.dharma/shared/campaigns/artifactful.md"
