"""Bounded YouTube transcript enricher for world-radar observations.

This is not a scrape farm. It only walks an existing observation JSONL,
fetches captions for at most ``max_items`` YouTube URLs, and writes an
enriched JSONL the Go world-signal ingestor can receipt.

The MCP youtube-transcript server is the interactive agent path. This
module is the pipeline path: same public captions, no MCP subprocess.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qs, urlparse

DEFAULT_MAX_ITEMS = 5
WATCH_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def is_youtube_url(value: str) -> bool:
    host = (urlparse(value).hostname or "").lower().rstrip(".")
    return host in WATCH_HOSTS or host == "youtu.be"


def extract_video_id(url: str) -> str | None:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
        return candidate if VIDEO_ID_RE.match(candidate) else None
    if host not in WATCH_HOSTS:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if parts and parts[0] in {"shorts", "embed", "live"} and len(parts) > 1:
        candidate = parts[1]
        return candidate if VIDEO_ID_RE.match(candidate) else None
    query = parse_qs(parsed.query)
    candidate = (query.get("v") or [""])[0]
    return candidate if VIDEO_ID_RE.match(candidate) else None


def default_fetch_transcript(url: str) -> str | None:
    """Best-effort public captions. Returns None when the optional dep is absent."""
    video_id = extract_video_id(url)
    if not video_id:
        return None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["en"])
        snippets = getattr(fetched, "snippets", fetched)
        texts = []
        for snippet in snippets:
            text = getattr(snippet, "text", None)
            if text is None and isinstance(snippet, dict):
                text = snippet.get("text")
            if text:
                texts.append(str(text))
        joined = " ".join(texts).strip()
        return joined or None
    except Exception:
        return None


def enrich_observations(
    rows: Iterable[dict[str, Any]],
    *,
    fetch_transcript: Callable[[str], str | None] = default_fetch_transcript,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> list[dict[str, Any]]:
    if max_items < 0:
        raise ValueError("max_items must be >= 0")
    out: list[dict[str, Any]] = []
    fetched = 0
    for row in rows:
        enriched = dict(row)
        url = str(row.get("url") or row.get("source_url") or "")
        video_id = extract_video_id(url) if is_youtube_url(url) else None
        if video_id and fetched < max_items:
            transcript = fetch_transcript(url)
            fetched += 1
            metadata = dict(enriched.get("metadata") or {}) if isinstance(enriched.get("metadata"), dict) else {}
            metadata["video_id"] = video_id
            if transcript:
                metadata["transcript_chars"] = len(transcript)
                description = str(enriched.get("description") or "")
                if transcript not in description:
                    enriched["description"] = (description + "\n\n" + transcript).strip()
            else:
                metadata["transcript_status"] = "unavailable"
            enriched["metadata"] = metadata
            if not str(enriched.get("source_type") or "").strip():
                enriched["source_type"] = "youtube_atom"
        out.append(enriched)
    return out


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="observation JSONL")
    parser.add_argument("--output", required=True, help="enriched JSONL")
    parser.add_argument("--max", type=int, default=DEFAULT_MAX_ITEMS)
    args = parser.parse_args(argv)
    rows = read_jsonl(Path(args.input))
    enriched = enrich_observations(
        rows,
        fetch_transcript=default_fetch_transcript,
        max_items=args.max,
    )
    write_jsonl(Path(args.output), enriched)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
