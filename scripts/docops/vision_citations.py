#!/usr/bin/env python3
"""Stage 0 — citation fidelity for the vision transmission artifact.

The integrity check in ``vision_navigation.py`` pins the artifact's own bytes.
That proves the artifact has not changed; it proves nothing about whether the
artifact's claims still match the documents they cite. This module supplies the
missing property: **source fidelity**.

Grammar (the bracket convention, formalized):

    [path §Section #sha12]        pinned  — sha12 = sha256(owner span)[:12]
    [path §Section]               unpinned — resolvable, not yet pinned
    [off-repo: path §Section]     external — checked when present, never trusted when absent
    [memory:name ...]             external — off-repo by construction
    [PROJECTION: reason]          agent-authored, declared, no source claimed

Rules this enforces, in order of severity:

* a repo citation whose path does not resolve                → BROKEN
* a repo citation whose §Section does not resolve             → BROKEN
* a pinned citation whose owner span no longer hashes to sha12 → DRIFTED
* an external citation whose file is absent                   → FLAGGED (never trusted)
* a resolvable citation carrying no #sha12                    → UNPINNED

It runs over the **render path** (each emitted tier), not only the source file,
because a hand-compressed tier can silently re-attach a citation that is
correct in the full document — which is exactly how the §10 firewall drift
survived review.

Stdlib only. No subprocess. No network.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

# A bracket run that is not a markdown link (not followed by "(") and not a
# wiki-style [[link]]. Citations never span lines in the artifact.
CITATION_RE = re.compile(r"(?<!\[)\[([^\[\]\n]+)\](?!\()")

SHA_RE = re.compile(r"#([0-9a-f]{12})\b")
SECTION_RE = re.compile(r"§\s*([^#\]]+?)\s*(?=#[0-9a-f]{12}|$)")
REPO_PATH_RE = re.compile(
    r"\b((?:docs|foundations|lodestones|specs|scripts|dharma_swarm|reports|architecture|tests|packages)"
    r"/[A-Za-z0-9_./-]+\.(?:md|py|yaml|yml|json))"
)
EXTERNAL_PREFIX_RE = re.compile(r"^\s*(?:off-repo:|memory:)|(?:^|\s)~/")
PROJECTION_RE = re.compile(r"^\s*PROJECTION\b", re.IGNORECASE)

# Bracket runs that are prose, not citations: enumerations, asides, and the
# ledger's own status labels. Anything here is ignored by the scanner.
NON_CITATION_HINTS = (
    "OPEN-",
    "naming-ritual",
    "RECOVERED-MEMORY",
    "UNRATIFIED",
    "same doc",
    "same §",
    "judge verdict",
)

REPO_ROOT_MARKERS = ("dharma_swarm", "pyproject.toml")


@dataclass(frozen=True)
class Citation:
    raw: str
    line: int
    kind: str  # repo | external | projection | unparsed
    path: str | None
    section: str | None
    sha12: str | None


@dataclass(frozen=True)
class Finding:
    severity: str  # BROKEN | DRIFTED | FLAGGED | UNPINNED
    where: str
    citation: str
    message: str

    def render(self) -> str:
        return f"{self.severity}: {self.where}: [{self.citation}] — {self.message}"


def sha12_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def classify(inner: str) -> str:
    if PROJECTION_RE.search(inner):
        return "projection"
    if EXTERNAL_PREFIX_RE.search(inner):
        return "external"
    if REPO_PATH_RE.search(inner):
        return "repo"
    return "unparsed"


def parse_citation(inner: str, line: int) -> Citation:
    kind = classify(inner)
    path_match = REPO_PATH_RE.search(inner)
    section_match = SECTION_RE.search(inner)
    sha_match = SHA_RE.search(inner)
    section = section_match.group(1).strip() if section_match else None
    if section:
        # Trailing qualifiers ("§The One Line, verbatim") are not part of the name.
        section = section.split(",")[0].strip()
    return Citation(
        raw=inner.strip(),
        line=line,
        kind=kind,
        path=path_match.group(1) if path_match else None,
        section=section,
        sha12=sha_match.group(1) if sha_match else None,
    )


def iter_citations(text: str) -> list[Citation]:
    citations: list[Citation] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in CITATION_RE.finditer(line):
            inner = match.group(1)
            if any(hint in inner for hint in NON_CITATION_HINTS):
                continue
            # One bracket may carry several citations separated by ";".
            for part in inner.split(";"):
                if not (REPO_PATH_RE.search(part) or EXTERNAL_PREFIX_RE.search(part)
                        or PROJECTION_RE.search(part)):
                    continue
                citations.append(parse_citation(part, line_no))
    return citations


def find_section(doc_text: str, name: str) -> str | None:
    """Body of the markdown heading whose title matches ``name``.

    Matching is deliberately forgiving on decoration (numbering, §, case) and
    strict on content: the cited name must appear in the normalized heading.
    """
    raw_target = name.strip().lstrip("§").strip()
    target = re.sub(r"[^a-z0-9 ]+", " ", raw_target.lower()).strip()
    if not target:
        return None
    # "§3" / "§3.1" address a heading by its own numbering; the number is the
    # whole identity, so it must be matched before decoration is stripped.
    numeric_target = (
        raw_target.upper()
        if re.fullmatch(r"(?:\d+(?:\.\d+)*|[IVXLC]+)", raw_target, re.IGNORECASE)
        else None
    )
    lines = doc_text.splitlines()
    for index, line in enumerate(lines):
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if not heading:
            continue
        level = len(heading.group(1))
        heading_text = heading.group(2).strip()
        numbering = re.match(r"^§?\s*(\d+(?:\.\d+)*|[IVXLC]+)(?=[.\s:])", heading_text)
        title = re.sub(r"[^a-z0-9 ]+", " ", heading_text.lower()).strip()
        stripped = re.sub(r"^\s*\d+(\s+\d+)*\s*", "", title).strip()
        if numeric_target is not None:
            if not numbering or numbering.group(1).upper() != numeric_target:
                continue
        elif target not in stripped and stripped not in target and target not in title:
            continue
        body: list[str] = []
        for following in lines[index + 1:]:
            deeper = re.match(r"^(#{1,6})\s+", following)
            if deeper and len(deeper.group(1)) <= level:
                break
            body.append(following)
        return "\n".join(body).strip()
    return None


def resolve_external(path_text: str) -> Path | None:
    cleaned = path_text.strip()
    for prefix in ("off-repo:", "memory:"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    token = cleaned.split()[0].rstrip(",;") if cleaned.split() else ""
    if token.startswith("~/"):
        return Path(token).expanduser()
    return None


def check_citation(repo_root: Path, citation: Citation, where: str) -> list[Finding]:
    if citation.kind == "projection":
        return []

    if citation.kind == "external":
        target = resolve_external(citation.raw)
        if target is None or not target.is_file():
            return [
                Finding(
                    "FLAGGED",
                    where,
                    citation.raw,
                    "external source not present in this checkout — never trusted, "
                    "must stay labelled off-repo",
                )
            ]
        text = target.read_text(encoding="utf-8", errors="ignore")
        return _check_span(text, citation, where, pinned_required=False)

    if citation.kind == "unparsed":
        return [
            Finding(
                "BROKEN",
                where,
                citation.raw,
                "citation does not parse as [path §Section #sha12], external, or PROJECTION",
            )
        ]

    assert citation.path is not None
    owner = repo_root / citation.path
    if not owner.is_file():
        return [Finding("BROKEN", where, citation.raw, f"path does not resolve: {citation.path}")]
    return _check_span(owner.read_text(encoding="utf-8", errors="ignore"), citation, where,
                       pinned_required=True)


def _check_span(doc_text: str, citation: Citation, where: str, *, pinned_required: bool) -> list[Finding]:
    if citation.section is None:
        if citation.sha12:
            actual = sha12_of(doc_text.strip())
            if actual != citation.sha12:
                return [
                    Finding("DRIFTED", where, citation.raw,
                            f"whole-file pin stale: declared #{citation.sha12}, actual #{actual}")
                ]
            return []
        return [Finding("UNPINNED", where, citation.raw,
                        "no §Section and no #sha12 — nothing to verify against")]

    # A range ("§1–§4", "§I-§V") names no single span, so no hash can pin it.
    # That is a grammar defect, not a resolution failure: it must be split.
    if re.search(r"[–—]\s*§|§\s*\S+\s*[–—]", citation.section):
        return [Finding("UNPINNABLE", where, citation.raw,
                        "cites a range of sections; split into one citation per span")]

    span = find_section(doc_text, citation.section)
    if span is None:
        return [Finding("BROKEN", where, citation.raw,
                        f"§{citation.section} does not resolve in the owner document")]
    actual = sha12_of(span)
    if citation.sha12 is None:
        severity = "UNPINNED" if pinned_required else "FLAGGED"
        return [Finding(severity, where, citation.raw,
                        f"resolves, but carries no pin; owner span is #{actual}")]
    if actual != citation.sha12:
        return [Finding("DRIFTED", where, citation.raw,
                        f"owner span changed: declared #{citation.sha12}, actual #{actual}")]
    return []


def audit_text(repo_root: Path, text: str, where: str) -> list[Finding]:
    findings: list[Finding] = []
    for citation in iter_citations(text):
        findings.extend(check_citation(repo_root, citation, f"{where}:{citation.line}"))
    return findings


def summarize(findings: list[Finding], total: int) -> str:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    parts = [f"{severity} {counts[severity]}" for severity in sorted(counts)]
    return f"{total} citations · " + (" · ".join(parts) if parts else "all verified")
