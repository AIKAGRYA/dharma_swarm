from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.world_radar.youtube_transcript import (
    enrich_observations,
    extract_video_id,
    is_youtube_url,
    main,
)


def test_extract_video_id_watch_shorts_and_be() -> None:
    assert extract_video_id("https://www.youtube.com/watch?v=xnUYnd-Pgeg") == "xnUYnd-Pgeg"
    assert extract_video_id("https://youtu.be/xnUYnd-Pgeg") == "xnUYnd-Pgeg"
    assert extract_video_id("https://www.youtube.com/shorts/xnUYnd-Pgeg") == "xnUYnd-Pgeg"
    assert extract_video_id("https://example.com/watch?v=xnUYnd-Pgeg") is None


def test_is_youtube_url_uses_host_not_query_substring() -> None:
    assert is_youtube_url("https://www.youtube.com/watch?v=xnUYnd-Pgeg")
    assert not is_youtube_url(
        "https://attacker.example/read?next=https://www.youtube.com/watch?v=xnUYnd-Pgeg"
    )


def test_enrich_observations_is_capped_and_injectable() -> None:
    calls: list[str] = []

    def fake_fetch(url: str) -> str | None:
        calls.append(url)
        return "caption text for " + url

    rows = [
        {"title": "one", "url": "https://www.youtube.com/watch?v=aaaaaaaaaaa"},
        {"title": "two", "url": "https://youtu.be/bbbbbbbbbbb"},
        {"title": "three", "url": "https://www.youtube.com/watch?v=ccccccccccc"},
        {"title": "hn", "url": "https://news.ycombinator.com/item?id=1"},
    ]
    enriched = enrich_observations(rows, fetch_transcript=fake_fetch, max_items=2)

    assert len(calls) == 2
    assert "caption text" in enriched[0]["description"]
    assert enriched[0]["metadata"]["video_id"] == "aaaaaaaaaaa"
    assert "caption text" in enriched[1]["description"]
    assert "caption text" not in str(enriched[2].get("description") or "")
    assert "metadata" not in enriched[3]


def test_cli_writes_jsonl(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "obs.jsonl"
    dst = tmp_path / "out.jsonl"
    src.write_text(
        json.dumps(
            {
                "title": "seed",
                "url": "https://www.youtube.com/watch?v=xnUYnd-Pgeg",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "dharma_swarm.world_radar.youtube_transcript.default_fetch_transcript",
        lambda url: "CI must speak to the agent.",
    )
    assert main(["--input", str(src), "--output", str(dst), "--max", "1"]) == 0
    row = json.loads(dst.read_text(encoding="utf-8").splitlines()[0])
    assert "CI must speak to the agent." in row["description"]
