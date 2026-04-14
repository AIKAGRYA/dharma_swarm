"""Tests for campaigns — durable campaign memory for the governance loop."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dharma_swarm.campaigns import (
    campaign_from_promise,
    complete_campaign,
    create_campaign,
    find_by_agent,
    find_campaign,
    find_campaign_domain,
    list_stale,
    load_active,
    mark_check_in,
    promise_id_from_text,
    release_campaign,
    save_active,
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


def test_save_active_is_atomic(meta_dir: Path) -> None:
    create_campaign("c", "research", ["a"], meta_dir=meta_dir)
    assert not list((meta_dir).glob("*.tmp"))  # atomic write cleans up
