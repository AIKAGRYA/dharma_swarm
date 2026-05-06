from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dharma_swarm.daily_operating_brief import (
    DailyOperatingBriefInputs,
    build_daily_operating_brief,
    render_markdown,
)
from dharma_swarm.human_yds_ledger import (
    append_human_yds_rating,
    is_human_source,
    load_human_yds_ratings,
)


def test_appends_human_rating_to_explicit_jsonl_path(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ratings" / "yds.jsonl"
    timestamp = datetime(2026, 5, 6, 1, 2, tzinfo=timezone.utc)

    rating = append_human_yds_rating(
        ledger_path,
        artifact="daily-brief-v0",
        rating="5.10a",
        human_comment="clear enough to operate from",
        operator_id="dhyana",
        timestamp=timestamp,
        metadata={"branch": "chore/daily-operating-brief-v0"},
    )

    assert rating.timestamp == "2026-05-06T01:02:00Z"
    records = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(records) == 1
    payload = json.loads(records[0])
    assert payload["artifact"] == "daily-brief-v0"
    assert payload["rating"] == "5.10a"
    assert payload["source"] == "human_operator"
    assert payload["human_comment"] == "clear enough to operate from"
    assert payload["operator_id"] == "dhyana"
    assert payload["metadata"]["branch"] == "chore/daily-operating-brief-v0"


def test_append_is_append_only(tmp_path: Path) -> None:
    ledger_path = tmp_path / "yds.jsonl"

    append_human_yds_rating(ledger_path, artifact="a", rating="5.8")
    append_human_yds_rating(ledger_path, artifact="b", rating="5.9")

    assert len(ledger_path.read_text(encoding="utf-8").splitlines()) == 2
    loaded = load_human_yds_ratings(ledger_path)
    assert [rating.artifact for rating in loaded] == ["a", "b"]


def test_rejects_non_human_authoritative_source(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="human/operator"):
        append_human_yds_rating(
            tmp_path / "yds.jsonl",
            artifact="self-score",
            rating="5.13d",
            source="ai_self_grader",
        )


def test_load_filters_advisory_non_human_rows(tmp_path: Path) -> None:
    ledger_path = tmp_path / "yds.jsonl"
    ledger_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-05-06T01:00:00Z",
                "artifact": "human-artifact",
                "rating": "5.9",
                "source": "human_operator",
            }
        )
        + "\n"
        + json.dumps(
            {
                "timestamp": "2026-05-06T02:00:00Z",
                "artifact": "ai-artifact",
                "rating": "5.12",
                "source": "ai_self_grader",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    authoritative = load_human_yds_ratings(ledger_path)
    advisory_included = load_human_yds_ratings(ledger_path, include_advisory=True)

    assert [rating.artifact for rating in authoritative] == ["human-artifact"]
    assert [rating.artifact for rating in advisory_included] == [
        "human-artifact",
        "ai-artifact",
    ]


def test_ledger_records_feed_daily_operating_brief(tmp_path: Path) -> None:
    ledger_path = tmp_path / "yds.jsonl"
    append_human_yds_rating(
        ledger_path,
        artifact="docops-integrity-v0",
        rating="5.10b",
        human_comment="useful enough to merge after review",
        source="operator_dhyana",
        timestamp="2026-05-06T03:00:00Z",
    )

    brief = build_daily_operating_brief(
        DailyOperatingBriefInputs(yds_ratings_path=ledger_path)
    )

    rendered = render_markdown(brief)
    assert "`docops-integrity-v0` rated `5.10b`" in rendered
    assert "useful enough to merge after review" in rendered


def test_missing_ledger_loads_empty_and_does_not_touch_home(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(fake_home))

    assert load_human_yds_ratings(tmp_path / "missing.jsonl") == []
    assert not (fake_home / ".dharma").exists()


def test_human_source_detection_is_explicit() -> None:
    assert is_human_source("human_operator") is True
    assert is_human_source("operator_dhyana") is True
    assert is_human_source("ai_self_grader") is False
