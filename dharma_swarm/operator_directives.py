"""Operator Directives — the air traffic controller.

A human-readable markdown file at ``~/.dharma/meta/OPERATOR_DIRECTIVES.md``
that every agent MUST read before doing anything.  The operator writes it;
the swarm obeys it.

Structure::

    ## Active Mission
    One sentence describing the current focus.

    ## DO (in priority order)
    1. First priority
    2. Second priority

    ## DO NOT
    - Forbidden pattern 1
    - Forbidden pattern 2

    ## Key Context
    - Free text context lines

The file is the canonical source of WHAT the swarm should work on.
Campaigns bind the HOW.  Directives bind the WHAT.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_STATE_DIR = Path.home() / ".dharma"
_FILENAME = "OPERATOR_DIRECTIVES.md"
_CACHE: dict[str, Any] = {"directives": None, "mtime": 0.0, "loaded_at": 0.0}
_CACHE_TTL = 30.0  # seconds


@dataclass(slots=True)
class OperatorDirectives:
    active_mission: str = ""
    do_items: list[str] = field(default_factory=list)
    dont_items: list[str] = field(default_factory=list)
    context_lines: list[str] = field(default_factory=list)
    raw_text: str = ""
    loaded_at: float = 0.0

    @property
    def has_content(self) -> bool:
        return bool(self.active_mission or self.do_items or self.dont_items)


_EMPTY = OperatorDirectives()


def _directives_path(state_dir: Path | None = None) -> Path:
    return (state_dir or _DEFAULT_STATE_DIR) / "meta" / _FILENAME


def _parse(text: str) -> OperatorDirectives:
    """Parse markdown sections into structured directives."""
    active_mission = ""
    do_items: list[str] = []
    dont_items: list[str] = []
    context_lines: list[str] = []

    current_section = ""
    for line in text.splitlines():
        stripped = line.strip()
        lower = stripped.lower()

        # Section headers
        if lower.startswith("## active mission"):
            current_section = "mission"
            continue
        if lower.startswith("## do not") or lower.startswith("## don't") or lower.startswith("## dont"):
            current_section = "dont"
            continue
        if lower.startswith("## do"):
            current_section = "do"
            continue
        if lower.startswith("## key context") or lower.startswith("## context"):
            current_section = "context"
            continue
        if stripped.startswith("## "):
            current_section = ""
            continue

        if not stripped:
            continue

        if current_section == "mission":
            if not active_mission:
                active_mission = stripped
        elif current_section == "do":
            # Lines starting with a digit (numbered list)
            m = re.match(r"^\d+[\.\)]\s*(.+)", stripped)
            if m:
                do_items.append(m.group(1).strip())
            elif stripped.startswith("- "):
                do_items.append(stripped[2:].strip())
        elif current_section == "dont":
            if stripped.startswith("- "):
                dont_items.append(stripped[2:].strip())
            elif stripped.startswith("Do NOT") or stripped.startswith("do not"):
                dont_items.append(stripped)
        elif current_section == "context":
            if stripped.startswith("- "):
                context_lines.append(stripped[2:].strip())
            else:
                context_lines.append(stripped)

    return OperatorDirectives(
        active_mission=active_mission,
        do_items=do_items,
        dont_items=dont_items,
        context_lines=context_lines,
        raw_text=text,
        loaded_at=time.monotonic(),
    )


def load_directives(
    state_dir: Path | None = None,
    force: bool = False,
) -> OperatorDirectives:
    """Load and cache operator directives from disk. 30s mtime cache."""
    path = _directives_path(state_dir)
    if not path.exists():
        return _EMPTY

    try:
        mtime = path.stat().st_mtime
    except Exception:
        return _EMPTY

    now = time.monotonic()
    if (
        not force
        and _CACHE["directives"] is not None
        and _CACHE["mtime"] == mtime
        and (now - _CACHE["loaded_at"]) < _CACHE_TTL
    ):
        return _CACHE["directives"]  # type: ignore[return-value]

    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("operator_directives: read failed: %s", exc)
        return _EMPTY

    directives = _parse(text)
    _CACHE.update(directives=directives, mtime=mtime, loaded_at=now)
    return directives


def invalidate_cache() -> None:
    _CACHE.update(directives=None, mtime=0.0, loaded_at=0.0)


_STRIP_PREFIX = re.compile(
    r"^(?:do\s+not|don'?t)\s+"
    r"(?:work\s+on|touch|focus\s+on|spend\s+time\s+on|let|reopen|generate|"
    r"use|create|produce|write|build|run|do|prioritize|allow)\s*",
    re.IGNORECASE,
)
_STRIP_CLAUSE = re.compile(
    r"\s+(?:when|unless|while|if|that|until|over|before|after)\s+.*$",
    re.IGNORECASE,
)


def is_forbidden(text: str, directives: OperatorDirectives | None = None) -> bool:
    """True if text matches any DON'T item (case-insensitive substring).

    Extracts noun-phrase patterns from each DON'T item by stripping:
    1. ``Do NOT`` / ``Don't`` prefix
    2. Leading verbs (``work on``, ``let``, ``reopen``, etc.)
    3. Trailing context clauses (``when ...``, ``over ...``, etc.)
    4. Parenthetical explanations

    Slash-separated alternatives (``mech-interp / R_V / contraction``) are
    each checked independently.
    """
    if directives is None or not directives.dont_items:
        return False
    text_lower = text.lower()
    for item in directives.dont_items:
        cleaned = _STRIP_PREFIX.sub("", item.strip()).strip()
        if not cleaned:
            continue
        alternatives = [t.strip() for t in re.split(r"\s*/\s*", cleaned)]
        for alt in alternatives:
            # Strip parenthetical
            noun = re.split(r"\s*\(", alt)[0].strip()
            # Strip trailing clause
            noun = _STRIP_CLAUSE.sub("", noun).strip().lower()
            if noun and len(noun) >= 3 and noun in text_lower:
                return True
    return False


def mission_context_block(directives: OperatorDirectives | None = None) -> str:
    """Format directives into a block suitable for prepending to agent context."""
    if directives is None or not directives.has_content:
        return ""
    parts: list[str] = []
    if directives.active_mission:
        parts.append(f"ACTIVE MISSION: {directives.active_mission}")
    if directives.do_items:
        parts.append("OPERATOR PRIORITIES:")
        for i, item in enumerate(directives.do_items[:5], 1):
            parts.append(f"  {i}. {item}")
    if directives.dont_items:
        parts.append("OPERATOR CONSTRAINTS:")
        for item in directives.dont_items[:5]:
            parts.append(f"  - {item}")
    return "\n".join(parts)


_SEED_CONTENT = """\
## Active Mission
NeurIPS 2026 Position Paper — abstract due May 4, paper due May 6

## DO (in priority order)
1. Support NeurIPS abstract writing — competitive landscape, related work synthesis, framing
2. Maintain daemon health — gauntlet, guardian, basic infrastructure
3. Produce swarm-relevant research — agent landscape, architecture patterns, self-assessment
4. Advance GAIA MVP spec — one pilot with full morphism chain (post-abstract)

## DO NOT
- Do NOT work on mech-interp / R_V / contraction / geometric_lens (Dhyana's personal research, separate codebase)
- Do NOT reopen quarantined synthesis loops (eval_probe_loop, latent_followup_loop)
- Do NOT prioritize background metabolism / consolidation churn / pulse churn over campaign work
- Do NOT generate revenue artifacts until paper and GAIA MVP are proven

## Key Context
- Primary campaign is authoritative: ~/.dharma/meta/active_campaigns.json
- The swarm's job is self-governance and world-facing artifacts, NOT Dhyana's personal MI research
- 18 days to NeurIPS abstract — that is the credibility foundation
"""


def seed_if_absent(state_dir: Path | None = None) -> Path:
    """Create the directives file with seed content if it doesn't exist.

    Returns the path regardless.
    """
    path = _directives_path(state_dir)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_SEED_CONTENT)
        logger.info("operator_directives: seeded %s", path)
    return path


__all__ = [
    "OperatorDirectives",
    "load_directives",
    "invalidate_cache",
    "is_forbidden",
    "mission_context_block",
    "seed_if_absent",
]
