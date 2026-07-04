#!/usr/bin/env python3
"""NAGA-IR citation completeness and path-resolution checker.

The checker is stdlib-only and does not fetch URLs. It verifies that
load-bearing confidence-rated technical claims have inline markdown-link
citations, that HTTP citations are structurally well formed, and that repo
path citations resolve against origin/main through git.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Iterable, Iterator, NamedTuple


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC_DIR = REPO_ROOT / "specs" / "naga_ir"
DOCOPS_HELPER = REPO_ROOT / "scripts" / "docops" / "check_docops_integrity.py"
EXIT_CLEAN = 0
EXIT_VIOLATED = 1
EXIT_BROKEN = 2

LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
BARE_HTTP_RE = re.compile(r"(?<!\]\()https?://[^\s)]+")
CONFIDENCE_RE = re.compile(r"\[confidence:\s*\d+/100\]", re.IGNORECASE)
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
REPO_PREFIXES = ("scripts/", "dharma_swarm/", "docs/", "packages/")
LOCAL_SPEC_PREFIX = "specs/naga_ir/"
TECHNICAL_TERMS = (
    "origin/main",
    "git show",
    "mlir",
    "verif",
    "viper",
    "nagini",
    "crdt",
    "rfc",
    "jcs",
    "ed25519",
    "coalgebra",
    "bisimilar",
    "assurance_boundary",
    "sab_client",
    "telos",
    "dharma_swarm/",
    "scripts/",
    "docs/",
    "packages/",
)
DEFINITION_MARKERS = (
    "this spec",
    "this draft",
    "defines ",
    "is defined",
    "names ",
    "means ",
    "field is",
    "fields are",
    "non-normative",
    "future ",
    "planned ",
)


class BrokenCheck(RuntimeError):
    pass


class Finding(NamedTuple):
    path: Path
    line: int
    code: str
    detail: str

    def render(self, root: Path) -> str:
        try:
            loc = self.path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            loc = str(self.path)
        return f"{loc}:{self.line}:{self.code}: {self.detail}"


class Link(NamedTuple):
    text: str
    target: str
    line: int


class GitResult(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


def load_docops_helpers():
    if not DOCOPS_HELPER.is_file():
        raise BrokenCheck(f"missing docops helper {DOCOPS_HELPER}")
    spec = importlib.util.spec_from_file_location("_naga_docops_helper", DOCOPS_HELPER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.extract_path_references, module.target_exists


EXTRACT_PATH_REFERENCES, TARGET_EXISTS = load_docops_helpers()


def run_git(args: list[str], repo_root: Path) -> GitResult:
    result = subprocess.run(args, cwd=repo_root, check=False, capture_output=True, text=True)
    return GitResult(result.returncode, result.stdout, result.stderr)


def spec_paths(inputs: Iterable[Path]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        item = item.resolve()
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
        raise BrokenCheck(f"missing markdown file(s): {', '.join(missing)}")
    return paths


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise BrokenCheck(f"cannot read {path}: {exc}") from exc


def paragraphs(lines: list[str]) -> Iterator[tuple[int, str]]:
    start = 0
    buf: list[str] = []
    in_fence = False
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            if buf:
                yield start, " ".join(buf)
                buf = []
            continue
        if in_fence or not stripped or stripped.startswith("#") or stripped.startswith("|"):
            if buf:
                yield start, " ".join(buf)
                buf = []
            continue
        if not buf:
            start = idx
        buf.append(stripped)
    if buf:
        yield start, " ".join(buf)


def links_in_text(text: str, start_line: int = 1) -> list[Link]:
    links: list[Link] = []
    for match in LINK_RE.finditer(text):
        links.append(Link(match.group(1), match.group(2).strip(), start_line + text[: match.start()].count("\n")))
    return links


def valid_http(target: str) -> bool:
    parsed = urllib.parse.urlparse(target)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and not any(ch.isspace() for ch in target)


def strip_target(target: str) -> str:
    target = target.strip().strip("<>").strip()
    if "#" in target:
        target = target.split("#", 1)[0]
    return target


def resolve_relative(doc: Path, target: str, repo_root: Path) -> str | None:
    stripped = strip_target(target)
    if SCHEME_RE.match(stripped) or not stripped:
        return None
    if stripped.startswith(REPO_PREFIXES):
        return stripped
    candidate = (doc.parent / stripped).resolve()
    try:
        rel = candidate.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None
    return rel


def repo_citation_path(doc: Path, target: str, repo_root: Path) -> str | None:
    rel = resolve_relative(doc, target, repo_root)
    if rel is None:
        return None
    if rel.startswith(LOCAL_SPEC_PREFIX):
        return None
    if rel.startswith(REPO_PREFIXES):
        return rel
    return None


def git_object_exists(repo_root: Path, repo_path: str, git_ref: str) -> bool:
    repo_path = repo_path.strip("/")
    shown = run_git(["git", "show", f"{git_ref}:{repo_path}"], repo_root)
    if shown.returncode == 0:
        return True
    tree = run_git(["git", "ls-tree", git_ref, repo_path], repo_root)
    return tree.returncode == 0 and bool(tree.stdout.strip())


def has_valid_citation(doc: Path, paragraph: str, repo_root: Path) -> bool:
    for link in links_in_text(paragraph):
        target = strip_target(link.target)
        if SCHEME_RE.match(target):
            if valid_http(target):
                return True
        elif repo_citation_path(doc, target, repo_root) is not None:
            return True
        elif TARGET_EXISTS(repo_root, doc, target):
            return True
    return False


def is_load_bearing(paragraph: str) -> bool:
    lower = paragraph.lower()
    if not CONFIDENCE_RE.search(paragraph):
        return False
    if any(marker in lower for marker in DEFINITION_MARKERS):
        return False
    return any(term in lower for term in TECHNICAL_TERMS)


def check_links(path: Path, repo_root: Path, git_ref: str) -> list[Finding]:
    findings: list[Finding] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    markdown_spans = [(m.start(), m.end()) for m in LINK_RE.finditer(text)]
    for match in BARE_HTTP_RE.finditer(text):
        if not any(start <= match.start() < end for start, end in markdown_spans):
            line = text[: match.start()].count("\n") + 1
            findings.append(Finding(path, line, "invalid_citation_format", "bare HTTP URL is not a markdown link citation"))
    for link in links_in_text(text):
        target = strip_target(link.target)
        if SCHEME_RE.match(target) and not valid_http(target):
            findings.append(Finding(path, link.line, "invalid_citation_format", f"non-HTTP citation target `{target}`"))
            continue
        repo_path = repo_citation_path(path, target, repo_root)
        if repo_path and not git_object_exists(repo_root, repo_path, git_ref):
            findings.append(Finding(path, link.line, "repo_path_missing", f"`{repo_path}` does not resolve on {git_ref}"))
    for ref in EXTRACT_PATH_REFERENCES(path):
        target = strip_target(ref.target)
        if repo_citation_path(path, target, repo_root) is None and not SCHEME_RE.match(target):
            TARGET_EXISTS(repo_root, path, target)
    return findings


def check_load_bearing(path: Path, repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    previous_had_citation = False
    for line_no, paragraph in paragraphs(read_lines(path)):
        has_citation = has_valid_citation(path, paragraph, repo_root)
        if is_load_bearing(paragraph) and not has_citation and not previous_had_citation:
            findings.append(Finding(path, line_no, "uncited_load_bearing", "load-bearing confidence-rated claim lacks inline citation"))
        previous_had_citation = has_citation
    return findings


def run(inputs: Iterable[Path], *, repo_root: Path = REPO_ROOT, git_ref: str = "origin/main") -> list[Finding]:
    findings: list[Finding] = []
    for path in spec_paths(inputs):
        findings.extend(check_links(path, repo_root, git_ref))
        findings.extend(check_load_bearing(path, repo_root))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check NAGA-IR citations and repo-path citation targets.")
    parser.add_argument("paths", nargs="*", type=Path, help="markdown files or directories; defaults to specs/naga_ir")
    parser.add_argument("--git-ref", default="origin/main", help="git ref for repo-path citations")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args(argv)
    try:
        findings = run(args.paths, repo_root=REPO_ROOT, git_ref=args.git_ref)
    except BrokenCheck as exc:
        print(f"broken: {exc}", file=sys.stderr)
        return EXIT_BROKEN
    if args.json:
        print(json.dumps({"ok": not findings, "findings": [f._asdict() for f in findings]}, default=str, indent=2))
    else:
        print(f"uncited_load_bearing: {sum(1 for f in findings if f.code == 'uncited_load_bearing')}")
        print(f"invalid_citation_format: {sum(1 for f in findings if f.code == 'invalid_citation_format')}")
        print(f"repo_path_resolution: {'all paths resolved' if not any(f.code == 'repo_path_missing' for f in findings) else 'violations'}")
        for finding in findings:
            print(finding.render(REPO_ROOT), file=sys.stderr)
    return EXIT_VIOLATED if findings else EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
