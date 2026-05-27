from __future__ import annotations

import json
import subprocess
from pathlib import Path

from dharma_swarm.world_radar import go_bridge as bridge


def test_world_radar_promotes_operator_drop_with_fake_ingestor(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = tmp_path / ".dharma"
    _write_jsonl(
        state / "meta" / "world_operator_drops.jsonl",
        [_signal("operator_drop", score=0.86)],
    )
    monkeypatch.setattr(bridge, "_run_go_ingestor", _fake_ingestor)

    result = bridge.run_world_radar_go_once(state_dir=state, scout_fetch=False)

    assert result.ok is True
    assert result.promotion_ready == 1
    inbox = _read_jsonl(state / "meta" / "world_zeitgeist_inbox.jsonl")
    assert inbox[0]["source"] == "world_zeitgeist"
    assert "first_principles_questions" in inbox[0]["metadata"]


def test_world_radar_incubates_single_source_and_writes_rnd(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = tmp_path / ".dharma"
    _write_jsonl(
        state / "meta" / "world_radar_observations.jsonl",
        [_signal("hacker_news", score=0.72)],
    )
    monkeypatch.setattr(bridge, "_run_go_ingestor", _fake_ingestor)

    result = bridge.run_world_radar_go_once(state_dir=state, scout_fetch=False)

    assert result.ok is True
    assert result.promotion_ready == 0
    assert result.incubations_written >= 4
    board = json.loads((state / "meta" / "world_signal_board.json").read_text())
    assert board["movements"][0]["status"] == "incubating"
    assert list((state / "meta" / "world_radar" / "incubations").glob("*/evolve.md"))
    assert (state / "meta" / "world_radar" / "world_radar_health.json").exists()


def test_world_radar_cascade_can_promote_after_second_source(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = tmp_path / ".dharma"

    def fake_scout(**kwargs):
        if kwargs.get("cascade_for"):
            return [_signal("github", score=0.74)], None, {"successful_sources": 1, "failed_sources": 0}
        return [_signal("hacker_news", score=0.72)], None, {"successful_sources": 1, "failed_sources": 0}

    monkeypatch.setattr(bridge, "_run_go_scout", fake_scout)
    monkeypatch.setattr(bridge, "_run_go_ingestor", _fake_ingestor)

    result = bridge.run_world_radar_go_once(state_dir=state, scout_fetch=True)

    assert result.ok is True
    assert result.promotion_ready == 1
    health = json.loads((state / "meta" / "world_radar" / "world_radar_health.json").read_text())
    assert health["successful_sources"] == 2


def test_world_radar_source_weights_feedback_persists(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = tmp_path / ".dharma"
    meta = state / "meta"
    meta.mkdir(parents=True)
    (meta / "opportunity_board.json").write_text(
        json.dumps(
            [
                {
                    "source_inputs": [{"raw_source": "github"}],
                    "realized_outcomes": [{"success": True}],
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(bridge, "_run_go_ingestor", _fake_ingestor)

    result = bridge.run_world_radar_go_once(state_dir=state, scout_fetch=False)
    second = bridge.run_world_radar_go_once(state_dir=state, scout_fetch=False)

    assert result.ok is True
    assert second.ok is True
    weights = json.loads((meta / "world_radar" / "source_weights.json").read_text())
    assert weights["github"] == 0.89
    health = json.loads((meta / "world_radar" / "world_radar_health.json").read_text())
    assert health["feedback_events_applied"] == 0
    ledger = json.loads((meta / "world_radar" / "source_feedback_ledger.json").read_text())
    assert len(ledger["applied_event_ids"]) == 1


def test_no_fetch_pass_preserves_prior_radar_raw_observations(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = tmp_path / ".dharma"
    raw_path = state / "meta" / "world_radar" / "raw_observations.jsonl"
    _write_jsonl(
        raw_path,
        [
            _signal("hacker_news", score=0.72),
            _signal("github", score=0.74),
        ],
    )
    monkeypatch.setattr(bridge, "_run_go_ingestor", _fake_ingestor)

    result = bridge.run_world_radar_go_once(state_dir=state, scout_fetch=False)

    assert result.ok is True
    assert result.raw_observations == 2
    assert len(_read_jsonl(raw_path)) == 2
    assert result.promotion_ready == 1



def test_run_go_scout_plumbs_archive_flags(monkeypatch, tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    output_path = tmp_path / "observations.jsonl"
    health_path = tmp_path / "health.json"
    archive_dir = tmp_path / "archive"
    url_file = tmp_path / "urls.txt"
    url_file.write_text("https://cofounder.co/how-to/start\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(cmd, cwd, capture_output, text, timeout):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        _write_jsonl(output_path, [_signal("cofounder", score=0.91)])
        health_path.write_text(
            json.dumps(
                {
                    "successful_sources": 1,
                    "failed_sources": 0,
                    "archive_enabled": True,
                    "archive_count": 2,
                    "dedupe_count": 0,
                    "archive_dir": str(archive_dir),
                    "archive_index_path": str(archive_dir / "archive_index.jsonl"),
                    "archive_manifest_path": str(archive_dir / "manifest.json"),
                    "archive_discovered_count": 3,
                    "archive_workers": 8,
                    "archive_total_bytes": 1234,
                    "archive_error_count": 1,
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)

    rows, error, counts = bridge._run_go_scout(
        state=state,
        output_path=output_path,
        health_path=health_path,
        timeout_s=30,
        archive=True,
        archive_dir=archive_dir,
        archive_urls=["https://cofounder.co/how-to/start"],
        archive_url_files=[str(url_file)],
        archive_max_bytes=123_456,
        archive_max_pages=4,
        archive_max_depth=0,
        archive_same_domain=False,
        archive_rate_limit_ms=250,
        archive_robots=False,
        archive_default_crawl_delay_ms=75,
        archive_max_retries=3,
        archive_retry_base_delay_ms=11,
        archive_retry_max_delay_ms=99,
        archive_max_fetch_duration_ms=1234,
        archive_exclude=["app.cofounder.co"],
        archive_workers=8,
        archive_discover_llms=True,
        archive_discover_sitemap=True,
        archive_sitemap_max_urls=25,
    )

    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert error is None
    assert rows[0]["source"] == "cofounder"
    assert counts["archive_enabled"] is True
    assert counts["archive_count"] == 2
    assert counts["archive_index_path"] == str(archive_dir / "archive_index.jsonl")
    assert counts["archive_discovered_count"] == 3
    assert counts["archive_workers"] == 8
    assert counts["archive_total_bytes"] == 1234
    assert counts["archive_error_count"] == 1
    assert "--archive" in cmd
    assert "--archive-discover-llms" in cmd
    assert "--archive-discover-sitemap" in cmd
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-workers"] == ["8"]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-sitemap-max-urls"] == ["25"]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-max-bytes"] == ["123456"]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-rate-limit-ms"] == ["250"]
    assert "--archive-same-domain=false" in cmd
    assert "--archive-robots=false" in cmd
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-default-crawl-delay-ms"] == ["75"]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-max-retries"] == ["3"]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-retry-base-delay-ms"] == ["11"]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-retry-max-delay-ms"] == ["99"]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-max-fetch-duration-ms"] == ["1234"]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--query-url"] == [
        "https://cofounder.co/how-to/start"
    ]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--query-url-file"] == [str(url_file)]
    assert "app.cofounder.co" in cmd


def _fake_ingestor(
    *,
    input_path: Path,
    output_path: Path,
    min_score: float,
    timeout_s: int,
) -> tuple[list[dict[str, object]], None]:
    rows = [
        row
        for row in _read_jsonl(input_path)
        if float(row.get("relevance_score", 0.0) or 0.0) >= min_score
    ]
    _write_jsonl(output_path, rows)
    return rows, None


def _signal(source: str, *, score: float) -> dict[str, object]:
    return {
        "id": f"{source}-subq",
        "source": source,
        "source_type": source,
        "category": "company",
        "title": "SubQ managed agent runtime",
        "description": "Managed agent execution infrastructure signal.",
        "relevance_score": score,
        "keywords": ["agentic", "runtime"],
        "url": f"https://example.com/{source}",
        "metadata": {"movement_key": "subq managed agent runtime"},
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
