"""chetana.quality_gate — admission quality layer for the trusted wiki.

This is an ADDITIVE layer that runs in chetana.promote BEFORE write_trusted,
*after* the telos safety gate (governance.gate_check_atom). The telos gate
answers "is this atom dharmically safe to admit?"; the quality gate answers
"is this atom worth admitting as a wiki concept, or is it slop?".

Motivation: ~4674 of the live wiki's concepts/*.md are un-curated session
"turn-N" fragments bulk-promoted 2026-06-06. Many are empty-equivalent
("none recorded" / "unknown" / "no files" / "N/A") or too thin to carry
meaning. The curated tier (~258) is rich (links, sources, confidence,
stale_after). This gate keeps the slop out without inventing any content.

Grades:
    REJECT — empty-equivalent body, under the meaningful-token floor, or a
             near-duplicate of an existing trusted atom. The staged atom is
             NOT written to concepts/; promote quarantines it for audit.
    WARN   — passes the REJECT bar but is thin / low-signal (few meaningful
             tokens or zero [[wikilinks]]). promote writes it to a review
             queue dir instead of concepts/ so an operator can grade it.
    PASS   — admit to concepts/ as usual.

Dedup reuses revival.py's normalization helpers (``_normalize_link``,
``_slugify_for_link``) so slug/title overlap detection matches the rest of
chetana, plus an exact normalized-content hash.

Nothing here writes to disk; promote.py owns routing. Nothing here invents
content; every decision is a function of the atom's own body + the existing
trusted corpus.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .provenance import parse_frontmatter
from .revival import _WIKILINK_RE, _normalize_link, _slugify_for_link

QualityGrade = Literal["PASS", "WARN", "REJECT"]

# Floors. Tuned to the live problem: "none recorded" (2 tokens) and section-
# label-only stubs sit far under MIN; the curated tier sits well over WARN.
MIN_MEANINGFUL_TOKENS = 25
WARN_FLOOR_TOKENS = 45

# Phrases that, when they make up the whole substantive body, mean "empty".
EMPTY_EQUIVALENT_PHRASES = frozenset(
    {
        "none recorded",
        "none",
        "no files",
        "no file",
        "no files changed",
        "no changes",
        "no content",
        "no notes",
        "no summary",
        "no data",
        "nothing recorded",
        "nothing",
        "unknown",
        "n/a",
        "na",
        "tbd",
        "todo",
        "to be determined",
        "placeholder",
        "-",
        "--",
    }
)

# Section-label noise that should not count as "substantive" content lines.
_SECTION_LABELS = frozenset(
    {
        "files",
        "files changed",
        "summary",
        "notes",
        "context",
        "content",
        "body",
        "title",
        "turn",
        "session",
        "outcome",
        "result",
    }
)

_WORD_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9\-'/]+")

# Small, generic stopword set. We are counting *meaningful* tokens, so common
# function words don't lift a slop atom over the floor.
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "but", "if", "of", "to", "in", "on",
        "for", "with", "as", "at", "by", "is", "are", "was", "were", "be",
        "been", "being", "this", "that", "these", "those", "it", "its", "from",
        "into", "than", "then", "so", "such", "not", "no", "yes", "we", "you",
        "i", "he", "she", "they", "them", "his", "her", "their", "our", "your",
        "do", "does", "did", "has", "have", "had", "will", "would", "can",
        "could", "should", "may", "might", "must", "about", "over", "under",
        "out", "up", "down", "all", "any", "some", "more", "most", "via",
    }
)


@dataclass
class QualityResult:
    grade: QualityGrade
    reason: str
    meaningful_tokens: int
    wikilinks: int
    content_hash: str
    duplicate_of: Path | None = None

    @property
    def admit(self) -> bool:
        """True iff the atom may be written to the trusted concepts/ tier."""
        return self.grade == "PASS"


def content_hash(body: str) -> str:
    """Normalized sha256 of the body — whitespace-collapsed, lowercased.

    Used for exact near-duplicate detection across the trusted corpus.
    """
    norm = re.sub(r"\s+", " ", body.strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _condensed_content_lines(body: str) -> list[str]:
    """Substantive content lines, stripped of markdown markers and labels."""
    out: list[str] = []
    for raw in body.splitlines():
        line = re.sub(r"^[#>*\-\d\.\)\s]+", "", raw).strip()
        # drop trailing punctuation/markers used as separators
        line = line.strip(" :*`-").lower()
        if not line:
            continue
        if line in _SECTION_LABELS:
            continue
        out.append(line)
    return out


def is_empty_equivalent(body: str) -> bool:
    """True if the body carries no substantive content.

    Catches blank bodies, single-marker bodies, and bodies whose every
    content line is an empty-equivalent phrase ("none recorded", "unknown",
    "no files", "N/A", ...) or a bare section label.
    """
    condensed = re.sub(r"[\s#>*\-\.\[\]()`:]+", " ", body.strip().lower()).strip()
    if not condensed:
        return True
    if condensed in EMPTY_EQUIVALENT_PHRASES:
        return True
    lines = _condensed_content_lines(body)
    if not lines:
        return True
    return all(line in EMPTY_EQUIVALENT_PHRASES for line in lines)


def meaningful_token_count(body: str) -> int:
    """Count word-like tokens that are not stopwords (links count as content)."""
    return sum(
        1
        for w in _WORD_RE.findall(body.lower())
        if w not in _STOPWORDS and len(w) >= 2
    )


def wikilink_count(body: str) -> int:
    return len(_WIKILINK_RE.findall(body))


def find_duplicate(
    *, title: str, body: str, trusted_root: Path, this_hash: str | None = None
) -> Path | None:
    """Find an existing trusted atom that this atom duplicates.

    A duplicate is: identical normalized body hash, OR a normalized title /
    slug collision with an existing trusted atom. Reuses revival.py's
    ``_normalize_link`` / ``_slugify_for_link`` so detection matches chetana's
    own linking semantics.
    """
    if not trusted_root.exists():
        return None
    this_hash = this_hash or content_hash(body)
    norm_title = _normalize_link(title)
    this_slug = _slugify_for_link(title)
    for path in sorted(trusted_root.glob("*.md")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
            other_schema, other_body = parse_frontmatter(
                text, lenient=True, source_path=str(path)
            )
        except Exception:
            continue
        if other_schema is None:
            continue
        if content_hash(other_body) == this_hash:
            return path
        if _normalize_link(other_schema.title) == norm_title and norm_title:
            return path
        if _slugify_for_link(other_schema.title) == this_slug and this_slug:
            return path
    return None


def quality_check_atom(
    *,
    title: str,
    body: str,
    trusted_root: Path,
    min_tokens: int = MIN_MEANINGFUL_TOKENS,
    warn_floor: int = WARN_FLOOR_TOKENS,
) -> QualityResult:
    """Grade an atom for admission to the trusted wiki. Pure / read-only."""
    h = content_hash(body)
    tokens = meaningful_token_count(body)
    links = wikilink_count(body)

    if is_empty_equivalent(body):
        return QualityResult(
            grade="REJECT",
            reason="empty_equivalent: body carries no substantive content",
            meaningful_tokens=tokens,
            wikilinks=links,
            content_hash=h,
        )

    if tokens < min_tokens:
        return QualityResult(
            grade="REJECT",
            reason=f"too_thin: {tokens} meaningful tokens < {min_tokens} floor",
            meaningful_tokens=tokens,
            wikilinks=links,
            content_hash=h,
        )

    dup = find_duplicate(title=title, body=body, trusted_root=trusted_root, this_hash=h)
    if dup is not None:
        return QualityResult(
            grade="REJECT",
            reason=f"near_duplicate: matches existing trusted atom {dup.name}",
            meaningful_tokens=tokens,
            wikilinks=links,
            content_hash=h,
            duplicate_of=dup,
        )

    if tokens < warn_floor or links == 0:
        return QualityResult(
            grade="WARN",
            reason=(
                f"thin_or_unlinked: {tokens} meaningful tokens, {links} [[links]] "
                f"(below {warn_floor}-token rich floor or no cross-links)"
            ),
            meaningful_tokens=tokens,
            wikilinks=links,
            content_hash=h,
        )

    return QualityResult(
        grade="PASS",
        reason=f"admit: {tokens} meaningful tokens, {links} [[links]]",
        meaningful_tokens=tokens,
        wikilinks=links,
        content_hash=h,
    )


def review_queue_root() -> Path:
    """Where WARN-grade atoms land instead of concepts/ — resolved live so
    test sandboxes that monkeypatch staging.WIKI_ROOT are honored."""
    from . import staging as staging_mod

    return staging_mod.WIKI_ROOT / "review_queue"
