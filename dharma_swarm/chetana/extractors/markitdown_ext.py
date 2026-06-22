"""Microsoft MarkItDown extractor.

MarkItDown converts heterogeneous sources (PDF, PPTX, DOCX, XLSX, images, audio,
HTML, CSV/JSON/XML, ZIP, YouTube URLs, EPub) to markdown. Two access modes:

    1. CLI: `markitdown <file>` — works if the package is pip-installed
    2. API/MCP: left to callers that want richer hosted extraction

Chetana deliberately treats MarkItDown output as staged/untrusted text. The
extractor only normalizes heterogeneous documents into markdown; promote owns
provenance, gates, signatures, and trust.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
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
    cli = _find_markitdown_cli()
    if cli is None:
        return MarkItDownResult(
            ok=False,
            body="",
            source_path=str(path),
            error=(
                "markitdown CLI not found; install with `pip install markitdown` "
                "before document ingest"
            ),
        )
    try:
        proc = subprocess.run(
            [cli, str(path)],
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


def _find_markitdown_cli() -> str | None:
    cli = shutil.which("markitdown")
    if cli is not None:
        return cli
    sibling = Path(sys.executable).with_name("markitdown")
    if sibling.exists():
        return str(sibling)
    return None
