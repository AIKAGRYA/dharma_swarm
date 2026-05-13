"""Tests for Agni VWrite Substack publish bridge."""

from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.ginko_substack_bridge import (
    iter_substack_publish_records,
    record_substack_publish_actions,
    substack_publish_operator_action,
)
from dharma_swarm.runtime_state import RuntimeStateStore


def _write_published_log(path: Path) -> None:
    rows = [
        {
            "timestamp": "2026-04-19T07:03:04.703400+00:00",
            "filename": "2026-03-26-before-the-ruling.md",
            "title": "Before the Ruling",
            "subtitle": "March 26, 2026. The ruling is pending.",
            "tags": ["markets", "risk"],
            "publication": "https://agnirecursivefire.substack.com",
            "success": True,
            "method": "api",
        },
        {"not": "usable"},
        "{bad json",
        {
            "timestamp": "2026-04-20T08:00:00+00:00",
            "filename": "failed-post.md",
            "title": "Failed Post",
            "subtitle": "",
            "tags": [],
            "publication": "https://agnirecursivefire.substack.com",
            "success": False,
            "method": "api",
        },
    ]
    lines = []
    for row in rows:
        if isinstance(row, dict):
            lines.append(json.dumps(row))
        else:
            lines.append(row)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_iter_substack_publish_records_skips_unusable_rows(tmp_path: Path) -> None:
    log_path = tmp_path / "published.jsonl"
    _write_published_log(log_path)

    records = list(iter_substack_publish_records(log_path))

    assert [record.filename for record in records] == [
        "2026-03-26-before-the-ruling.md",
        "failed-post.md",
    ]
    assert records[0].success is True
    assert records[0].tags == ("markets", "risk")
    assert records[1].success is False


def test_substack_publish_operator_action_is_sanitized(tmp_path: Path) -> None:
    log_path = tmp_path / "published.jsonl"
    _write_published_log(log_path)
    record = next(iter_substack_publish_records(log_path))

    action = substack_publish_operator_action(
        record,
        actor="test-agni",
        source_log=log_path,
    )

    assert action.action_name == "ginko_substack_post_published"
    assert action.actor == "test-agni"
    assert action.created_at.isoformat() == "2026-04-19T07:03:04.703400+00:00"
    assert action.payload["publish_channel"] == "substack"
    assert action.payload["source"] == "agni_vwrite_published_jsonl"
    assert "body" not in action.payload
    assert "token" not in json.dumps(action.payload).lower()
    assert "cookie" not in json.dumps(action.payload).lower()


def test_record_substack_publish_actions_is_idempotent(tmp_path: Path) -> None:
    log_path = tmp_path / "published.jsonl"
    db_path = tmp_path / "runtime.db"
    _write_published_log(log_path)

    first = record_substack_publish_actions(
        log_path,
        runtime_db=db_path,
        actor="test-agni",
    )
    second = record_substack_publish_actions(
        log_path,
        runtime_db=db_path,
        actor="test-agni",
    )

    assert len(first) == 2
    assert len(second) == 2
    actions = RuntimeStateStore(db_path).list_operator_actions_sync(limit=10)
    assert len(actions) == 2
    assert {action.action_name for action in actions} == {
        "ginko_substack_post_published",
        "ginko_substack_publish_failed",
    }


def test_record_substack_publish_actions_can_skip_failures(tmp_path: Path) -> None:
    log_path = tmp_path / "published.jsonl"
    db_path = tmp_path / "runtime.db"
    _write_published_log(log_path)

    actions = record_substack_publish_actions(
        log_path,
        runtime_db=db_path,
        actor="test-agni",
        include_failures=False,
    )

    assert len(actions) == 1
    assert actions[0].action_name == "ginko_substack_post_published"
