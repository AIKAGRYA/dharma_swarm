"""Microsoft MarkItDown extractor.

MarkItDown converts heterogeneous sources (PDF, PPTX, DOCX, XLSX, images, audio,
HTML, CSV/JSON/XML, ZIP, YouTube URLs, EPub) to markdown. Two access modes:

    1. CLI: `markitdown <file>` — works if the package is pip-installed
    2. MCP: invoke via the markitdown MCP server (already running on this box)

We prefer CLI for simplicity. If the CLI binary isn't available, return an
empty result and let the caller route through the MCP client.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MarkItDownResult:
    ok: bool
    body: str
    source_path: str
    error: str | None = None


def extract_via_markitdown(path: Path, *, timeout: int = 30) -> MarkItDownResult:
    if not path.exists():
        return MarkItDownResult(ok=False, body="", source_path=str(path), error="file missing")
    cli = subprocess.run(
        ["which", "markitdown"], capture_output=True, text=True, timeout=2
    )
    if cli.returncode != 0:
        return MarkItDownResult(
            ok=False,
            body="",
            source_path=str(path),
            error="markitdown CLI not found; install with `pip install markitdown` or route via MCP",
        )
    try:
        proc = subprocess.run(
            ["markitdown", str(path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return MarkItDownResult(
            ok=False, body="", source_path=str(path), error="timeout"
        )
    if proc.returncode != 0:
        return MarkItDownResult(
            ok=False,
            body="",
            source_path=str(path),
            error=f"exit {proc.returncode}: {proc.stderr[:120].strip()}",
        )
    return MarkItDownResult(ok=True, body=proc.stdout, source_path=str(path))
