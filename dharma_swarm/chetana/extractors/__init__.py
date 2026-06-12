"""chetana.extractors — source-kind specific parsers.

Each extractor turns a raw source into normalized text + metadata that
chetana.ingest can wrap in frontmatter.

    session       — Claude Code JSONL transcripts
    webclip       — Obsidian Web Clipper markdown drops
    markitdown_ext — PDF/PPT/DOCX/XLSX/audio/video via Microsoft MarkItDown
"""

from .session import extract_session_turns
from .webclip import extract_webclip
from .markitdown_ext import extract_via_markitdown

__all__ = [
    "extract_session_turns",
    "extract_webclip",
    "extract_via_markitdown",
]
