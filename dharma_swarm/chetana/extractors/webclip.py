"""Obsidian Web Clipper extractor.

Web Clipper drops markdown files with YAML frontmatter into a watched directory
(typically ~/.dharma/sources/inbox/webclip/). This extractor strips the
clipper-specific frontmatter and returns (title, body, source_url).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(?P<frontmatter>.*?)\n---\s*\n(?P<body>.*)$", re.DOTALL
)


@dataclass
class WebClip:
    title: str
    body: str
    source_url: str | None
    captured_at: str | None
    tags: list[str]


def extract_webclip(path: Path) -> WebClip:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return WebClip(
            title=path.stem.replace("-", " ").title(),
            body=text,
            source_url=None,
            captured_at=None,
            tags=[],
        )
    fm = yaml.safe_load(m.group("frontmatter")) or {}
    if not isinstance(fm, dict):
        fm = {}
    title = str(fm.get("title") or path.stem)
    return WebClip(
        title=title,
        body=m.group("body").strip(),
        source_url=fm.get("source") or fm.get("url"),
        captured_at=fm.get("created") or fm.get("captured"),
        tags=list(fm.get("tags") or []),
    )
