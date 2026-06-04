from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dharma_swarm.operator_core.control_surface_pr_queue import (
    pr_queue_rows,
    rows_from_pr_queue_payload,
)
from scripts.runtime.pr_merge_control import build_queue_summary


def _queue_payload(*, generated_at: str, items: list[dict]) -> dict:
    return {
        "schema": "dharma.pr_review.queue.v1",
        "generated_at": generated_at,
        "repo": "owner/repo",
        "total": len(items),
        "counts": {},
        "items": items,
    }


def test_pr_queue_projection_preserves_pr_identity_and_gate_status(tmp_path: Path) -> None:
    payload = _queue_payload(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        items=[
            {
                "number": 465,
                "title": "feat(ops): add read-only live ops cockpit",
                "url": "https://github.example/pr/465",
                "headRefName": "codex/live-ops-cockpit-v1",
                "headRefOid": "abc123",
                "baseRefName": "main",
                "mergeable": "MERGEABLE",
                "reviewDecision": "NONE",
                "checks": {"passing": ["ci"], "pending": [], "failing": [], "unknown": [], "total": 1},
                "status": "GITHUB_GREEN_NEEDS_PACKET",
                "reasons": ["GitHub green; packet, dual review, and merge gate still required"],
            }
        ],
    )

    rows = rows_from_pr_queue_payload(payload, queue_path=tmp_path / "latest.json")

    assert len(rows) == 1
    row = rows[0]
    assert row.id == "pr.#465"
    assert row.kind == "pr_queue"
    assert row.observed_state == "merge_ready_needs_packet"
    assert row.coherence_state == "partial"
    assert row.raw["pr_number"] == 465
    assert row.raw["head_sha"] == "abc123"
    assert row.raw["queue_status"] == "GITHUB_GREEN_NEEDS_PACKET"
    assert "pr_queue_status:GITHUB_GREEN_NEEDS_PACKET" in row.gap_codes
    assert "mutation_surface:none" in row.gap_codes
    assert "merge gate" in row.next_action


def test_fresh_pr_queue_projection_count_matches_open_pr_count(tmp_path: Path) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = _queue_payload(
        generated_at=generated_at,
        items=[
            {"number": 1, "title": "ready", "status": "GITHUB_GREEN_NEEDS_PACKET", "headRefOid": "sha1"},
            {"number": 2, "title": "draft", "status": "DRAFT", "headRefOid": "sha2"},
            {"number": 3, "title": "conflict", "status": "BLOCKED_CONFLICT", "headRefOid": "sha3"},
        ],
    )

    rows = rows_from_pr_queue_payload(payload, queue_path=tmp_path / "latest.json", ttl_s=900)

    open_pr_count = payload["total"]
    pr_queue_projection_count = len(rows)
    assert pr_queue_projection_count == open_pr_count == 3
    assert all(row.raw["freshness_state"] == "fresh" for row in rows)
    assert {row.raw["pr_number"] for row in rows} == {1, 2, 3}


def test_pr_queue_projection_marks_stale_receipts(tmp_path: Path) -> None:
    stale = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = _queue_payload(
        generated_at=stale,
        items=[
            {
                "number": 12,
                "title": "blocked",
                "status": "BLOCKED_CONFLICT",
                "reasons": ["merge conflict"],
                "checks": {"passing": [], "pending": [], "failing": [], "unknown": [], "total": 0},
            }
        ],
    )

    row = rows_from_pr_queue_payload(payload, queue_path=tmp_path / "latest.json", ttl_s=60)[0]

    assert row.observed_state == "blocked_conflict"
    assert row.coherence_state == "drifted"
    assert "pr_queue_stale" in row.gap_codes
    assert "head_sha_missing" in row.gap_codes
    assert row.raw["freshness_state"] == "stale"


def test_pr_queue_missing_receipt_is_visible_not_silent(tmp_path: Path) -> None:
    rows = pr_queue_rows(tmp_path / "missing.json")

    assert len(rows) == 1
    row = rows[0]
    assert row.id == "pr.queue"
    assert row.observed_state == "missing"
    assert row.coherence_state == "unknown"
    assert "pr_queue_missing" in row.gap_codes
    assert "make pr-queue" in row.next_action
    assert row.evidence[0].status == "missing"


def test_pr_merge_control_queue_summary_includes_head_sha() -> None:
    summary = build_queue_summary(
        [
            {
                "number": 9,
                "title": "green",
                "author": {"login": "dev"},
                "headRefName": "feature",
                "headRefOid": "sha999",
                "baseRefName": "main",
                "isDraft": False,
                "mergeable": "MERGEABLE",
                "reviewDecision": "",
                "statusCheckRollup": [],
                "updatedAt": "2026-06-04T00:00:00Z",
                "url": "https://github.example/pr/9",
            }
        ],
        "owner/repo",
    )

    assert summary["items"][0]["headRefOid"] == "sha999"


def test_pr_queue_projection_reads_receipt_file(tmp_path: Path) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    queue_path = tmp_path / "latest.json"
    queue_path.write_text(json.dumps(_queue_payload(generated_at=generated_at, items=[])), encoding="utf-8")

    rows = pr_queue_rows(queue_path)

    assert rows[0].id == "pr.queue"
    assert rows[0].observed_state == "empty"
    assert rows[0].coherence_state == "bound"
    assert rows[0].raw["queue_path"] == str(queue_path)
