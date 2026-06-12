"""chetana.gap_scan — find recurring topics + unanswered questions in the wiki.

Two modes:

    topic_coverage  — for each cluster of related atoms, identify topics that
                      are mentioned in body text but lack their own atom.
    open_questions  — extract sentences ending in '?' or matching open-loop
                      patterns from atom bodies; build a queue of unanswered
                      research questions, ranked by how often they recur.

The output is a markdown gap report + a structured gap queue (JSONL) that the
operator approves manually before any agent does the research.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .provenance import parse_frontmatter
from .staging import TRUSTED_DEFAULT


logger = logging.getLogger(__name__)


GAP_QUEUE_FILE = Path.home() / ".dharma" / "campaign_chetana" / "gap_queue.jsonl"


_OPEN_LOOP_PATTERNS = [
    re.compile(r"\bTODO\b[:\- ](.{8,200})", re.IGNORECASE),
    re.compile(r"\bopen question\b[:\- ](.{8,200})", re.IGNORECASE),
    re.compile(r"\bunresolved\b[:\- ](.{8,200})", re.IGNORECASE),
    re.compile(r"\b(should|must|need to)\b ([^.\n]{8,200})", re.IGNORECASE),
]
_QUESTION_RE = re.compile(r"([A-Z][^.?!]{12,200}\?)")


@dataclass
class GapItem:
    kind: str  # "topic_coverage" | "open_question"
    topic_or_question: str
    occurrences: int
    sample_paths: list[str]
    priority: float  # 0.0-1.0
    detected_at: str


@dataclass
class GapScanReport:
    scanned: int = 0
    topic_gaps: list[GapItem] = field(default_factory=list)
    open_questions: list[GapItem] = field(default_factory=list)


def gap_scan(
    *,
    roots: list[Path] | None = None,
    focus_topic: str | None = None,
    min_occurrences: int = 2,
    today: date | None = None,
) -> GapScanReport:
    today = today or date.today()
    roots = roots or [TRUSTED_DEFAULT]
    report = GapScanReport()

    titles_lower: set[str] = set()
    body_corpus: list[tuple[Path, str]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
                schema, body = parse_frontmatter(text, lenient=True, source_path=str(path))
            except Exception:
                continue
            report.scanned += 1
            if schema is not None:
                titles_lower.add(schema.title.lower())
            body_corpus.append((path, body))

    report.topic_gaps = _detect_topic_gaps(
        body_corpus, titles_lower, focus_topic, min_occurrences, today
    )
    report.open_questions = _detect_open_questions(body_corpus, min_occurrences, today)

    return report


def _detect_topic_gaps(
    body_corpus: list[tuple[Path, str]],
    titles_lower: set[str],
    focus_topic: str | None,
    min_occurrences: int,
    today: date,
) -> list[GapItem]:
    # Find [[wikilink]] references whose target doesn't exist as a wiki article.
    link_re = re.compile(r"\[\[([^\]\|\#]+)(?:[\|\#][^\]]*)?\]\]")
    refs: Counter[str] = Counter()
    sample: dict[str, list[str]] = {}
    for path, body in body_corpus:
        for m in link_re.finditer(body):
            target = m.group(1).strip().lower()
            if not target:
                continue
            if focus_topic and focus_topic.lower() not in target:
                continue
            if target in titles_lower:
                continue
            if target.replace(" ", "-") in {t.replace(" ", "-") for t in titles_lower}:
                continue
            refs[target] += 1
            sample.setdefault(target, []).append(str(path))

    gaps: list[GapItem] = []
    for target, count in refs.most_common(50):
        if count < min_occurrences:
            continue
        gaps.append(
            GapItem(
                kind="topic_coverage",
                topic_or_question=target,
                occurrences=count,
                sample_paths=sample[target][:5],
                priority=min(1.0, 0.3 + 0.1 * count),
                detected_at=today.isoformat(),
            )
        )
    return gaps


def _detect_open_questions(
    body_corpus: list[tuple[Path, str]],
    min_occurrences: int,
    today: date,
) -> list[GapItem]:
    questions: Counter[str] = Counter()
    sample: dict[str, list[str]] = {}
    for path, body in body_corpus:
        for m in _QUESTION_RE.finditer(body):
            q = " ".join(m.group(1).split()).rstrip("?")
            if len(q) < 16:
                continue
            key = q.lower()[:160]
            questions[key] += 1
            sample.setdefault(key, []).append(str(path))
        for pat in _OPEN_LOOP_PATTERNS:
            for m in pat.finditer(body):
                snippet = " ".join(m.group(0).split())
                key = snippet.lower()[:160]
                questions[key] += 1
                sample.setdefault(key, []).append(str(path))

    items: list[GapItem] = []
    for key, count in questions.most_common(50):
        if count < min_occurrences:
            continue
        items.append(
            GapItem(
                kind="open_question",
                topic_or_question=key,
                occurrences=count,
                sample_paths=sample[key][:5],
                priority=min(1.0, 0.4 + 0.15 * count),
                detected_at=today.isoformat(),
            )
        )
    return items


def write_gap_queue(report: GapScanReport, *, path: Path | None = None) -> Path:
    path = path or GAP_QUEUE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    items = report.topic_gaps + report.open_questions
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item.__dict__) + "\n")
    return path


def gap_summary(report: GapScanReport) -> str:
    lines = [
        "# Gap scan",
        "",
        f"- Scanned: {report.scanned} atoms",
        f"- Topic gaps: {len(report.topic_gaps)}",
        f"- Open questions: {len(report.open_questions)}",
        "",
    ]
    if report.topic_gaps:
        lines.append("## Topic gaps (referenced but no article)")
        for g in sorted(report.topic_gaps, key=lambda x: -x.occurrences)[:20]:
            lines.append(f"- `{g.topic_or_question}` — {g.occurrences}× (priority {g.priority:.2f})")
        lines.append("")
    if report.open_questions:
        lines.append("## Open questions (most frequent)")
        for g in sorted(report.open_questions, key=lambda x: -x.occurrences)[:20]:
            sentence = g.topic_or_question[:120]
            lines.append(f"- `{sentence}…` — {g.occurrences}× (priority {g.priority:.2f})")
    return "\n".join(lines)
