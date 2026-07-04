#!/usr/bin/env python3
"""Fetch and sanity-check NĀGA-IR markdown-link citations.

Each external markdown-link URL is fetched with urllib and checked for a
successful HTTP result plus topical support for the paragraph it cites. The
support test is intentionally heuristic: enough significant terms from the
claim must appear in the fetched text, final URL, or link text.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC_DIR = REPO_ROOT / "specs" / "naga_ir"

EXIT_CLEAN = 0
EXIT_VIOLATED = 1
EXIT_BROKEN = 2
REPORT_SCHEMA_VERSION = "naga_citation_report.v1"

LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
STOPWORDS = {
    "about",
    "above",
    "after",
    "again",
    "against",
    "also",
    "because",
    "before",
    "being",
    "below",
    "between",
    "canonical",
    "claim",
    "claims",
    "confidence",
    "current",
    "does",
    "evidence",
    "field",
    "fields",
    "fragment",
    "from",
    "into",
    "itself",
    "must",
    "named",
    "naga",
    "naga-ir",
    "only",
    "over",
    "receipt",
    "receipts",
    "spec",
    "state",
    "than",
    "that",
    "their",
    "therefore",
    "these",
    "this",
    "threshold",
    "trust",
    "under",
    "when",
    "while",
    "with",
    "within",
}


class BrokenCheck(RuntimeError):
    """The checker could not read the requested files."""


@dataclass(frozen=True)
class Citation:
    path: Path
    line: int
    text: str
    url: str
    paragraph: str


@dataclass(frozen=True)
class FetchResult:
    ok: bool
    status: int | None
    final_url: str
    text: str
    error: str = ""


@dataclass(frozen=True)
class Finding:
    code: str
    path: Path
    line: int
    detail: str

    def render(self, root: Path) -> str:
        location = self.path.relative_to(root).as_posix() if self.path.is_relative_to(root) else str(self.path)
        return f"{self.code} {location}:{self.line}: {self.detail}"


Fetcher = Callable[[str, float], FetchResult]


def spec_paths(inputs: Iterable[Path]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        if item.is_dir():
            paths.extend(sorted(item.glob("*.md")))
        else:
            paths.append(item)
    if not paths:
        paths = sorted(DEFAULT_SPEC_DIR.glob("*.md"))
    if not paths:
        raise BrokenCheck(f"no markdown files found under {DEFAULT_SPEC_DIR}")
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise BrokenCheck(f"missing spec file(s): {', '.join(missing)}")
    return paths


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise BrokenCheck(f"cannot read {path}: {exc}") from exc


def paragraph_blocks(lines: list[str]) -> Iterator[tuple[int, str]]:
    start = 0
    buf: list[str] = []
    in_fence = False
    for idx, line in enumerate(lines, start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            if buf:
                yield start, " ".join(buf)
                buf = []
            continue
        if in_fence or not line.strip() or line.startswith("#") or line.startswith("|"):
            if buf:
                yield start, " ".join(buf)
                buf = []
            continue
        if not buf:
            start = idx
        buf.append(line.strip())
    if buf:
        yield start, " ".join(buf)


def extract_citations(path: Path) -> list[Citation]:
    citations: list[Citation] = []
    for start, paragraph in paragraph_blocks(read_lines(path)):
        for match in LINK_RE.finditer(paragraph):
            prefix = paragraph[:match.start()]
            line = start + prefix.count("\n")
            citations.append(Citation(path, line, match.group(1), match.group(2), paragraph))
    return citations


def fetch_url(url: str, timeout: float) -> FetchResult:
    request = urllib.request.Request(url, headers={"User-Agent": "naga-citation-check/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", response.getcode())
            data = response.read(250_000)
            content_type = response.headers.get("content-type", "")
            charset = response.headers.get_content_charset() or "utf-8"
            if "pdf" in content_type.lower():
                text = data.decode("latin-1", errors="ignore")
            else:
                text = data.decode(charset, errors="ignore")
            return FetchResult(200 <= status < 400, status, response.geturl(), text)
    except urllib.error.HTTPError as exc:
        body = exc.read(20_000).decode("utf-8", errors="ignore")
        return FetchResult(False, exc.code, exc.geturl(), body, f"HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return FetchResult(False, None, url, "", str(exc))


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def tokens(text: str) -> set[str]:
    normalized = normalize(text)
    found = set(re.findall(r"[a-z][a-z0-9-]{3,}", normalized))
    return {token for token in found if token not in STOPWORDS and not token.isdigit()}


def claim_text(paragraph: str) -> str:
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", " ", paragraph)
    text = re.sub(r"\[confidence:\s*\d+/100\]", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"`[^`]*`", " ", text)
    return text


def url_terms(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(parsed.path)
    return f"{parsed.netloc} {path.replace('/', ' ').replace('-', ' ').replace('_', ' ')}"


def topically_supports(citation: Citation, result: FetchResult) -> bool:
    claim_terms = tokens(claim_text(citation.paragraph))
    if not claim_terms:
        return True
    support_corpus = f"{citation.text} {url_terms(citation.url)} {url_terms(result.final_url)} {result.text}"
    support_terms = tokens(support_corpus)
    overlap = claim_terms & support_terms
    link_terms = tokens(citation.text)
    if len(link_terms) >= 3:
        return True
    if citation.url.lower().endswith(".pdf") or result.final_url.lower().endswith(".pdf"):
        if overlap or (len(link_terms & support_terms) >= max(1, min(3, len(link_terms)))):
            return True
    required = 1 if len(claim_terms) <= 3 else min(3, max(2, len(claim_terms) // 4))
    if len(overlap) >= required:
        return True
    strong_terms = {term for term in claim_terms if len(term) >= 8}
    return bool(strong_terms & support_terms)


def check_citation(citation: Citation, fetcher: Fetcher, timeout: float) -> Finding | None:
    result = fetcher(citation.url, timeout)
    if not result.ok:
        status = f"status {result.status}" if result.status is not None else "no HTTP status"
        return Finding("NAGA-CITE-DEAD", citation.path, citation.line, f"{citation.url} did not resolve cleanly ({status}: {result.error})")
    if not topically_supports(citation, result):
        return Finding("NAGA-CITE-OFFTOPIC", citation.path, citation.line, f"{citation.url} resolved but did not topically support the attached claim")
    return None


def run(paths: Iterable[Path], *, timeout: float = 8.0, fetcher: Fetcher = fetch_url) -> list[Finding]:
    findings: list[Finding] = []
    for path in spec_paths(paths):
        for citation in extract_citations(path):
            finding = check_citation(citation, fetcher, timeout)
            if finding is not None:
                findings.append(finding)
    return findings


def main(argv: list[str] | None = None, *, fetcher: Fetcher = fetch_url) -> int:
    parser = argparse.ArgumentParser(description="Fetch NĀGA-IR citations and check topical support.")
    parser.add_argument("paths", nargs="*", type=Path, help="spec files or directories; defaults to specs/naga_ir/*.md")
    parser.add_argument("--timeout", type=float, default=8.0, help="per-URL timeout in seconds")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        findings = run(args.paths, timeout=args.timeout, fetcher=fetcher)
    except BrokenCheck as exc:
        print(f"naga-citation: BROKEN: {exc}", file=sys.stderr)
        return EXIT_BROKEN
    if args.json:
        print(json.dumps({"schema_version": REPORT_SCHEMA_VERSION, "findings": [f.render(REPO_ROOT) for f in findings]}, indent=2))
    else:
        if not findings:
            print("naga-citation: clean")
        for finding in findings:
            print(finding.render(REPO_ROOT))
    return EXIT_VIOLATED if findings else EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
