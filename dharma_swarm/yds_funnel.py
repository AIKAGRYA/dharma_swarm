"""Fast human YDS rating funnel.

This module is intentionally small: agents need one obvious place to turn a
human utterance like "YDS this 5.12c, note: clicked because..." into the
canonical machine-readable ledger.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from dharma_swarm.operator_core.operating_facts import (
    HumanQualityRatingFact,
    append_human_yds_rating,
    resolve_yds_ratings_path,
)


YDS_RATING_IN_TEXT_RE = re.compile(
    r"\b(5\.(?:6|7|8|9|10|11|12|13|14|15))\s*([abcdABCD])?\b"
)
NOTE_RE = re.compile(r"\bnote\s*:\s*(?P<note>.+)$", re.IGNORECASE)


def extract_yds_rating(text: str) -> str:
    """Extract and normalize a YDS grade from operator text."""

    match = YDS_RATING_IN_TEXT_RE.search(text)
    if not match:
        raise ValueError("no YDS grade found; expected a grade like 5.12c")
    base, suffix = match.groups()
    return f"{base}{(suffix or '').lower()}"


def extract_yds_note(text: str) -> str:
    """Extract a note, falling back to the full utterance.

    The fallback is deliberate: a human rating should be easy to file even when
    the operator does not use a perfect command syntax.
    """

    match = NOTE_RE.search(text)
    if match:
        note = match.group("note").strip()
        if note:
            return note
    if " - " in text:
        note = text.rsplit(" - ", 1)[1].strip()
        if note:
            return note
    return text.strip()


def record_yds_from_text(
    text: str,
    *,
    artifact_uri: str = "conversation:current",
    title: str = "",
    operator_id: str = "dhyana",
    artifact_kind: str = "operator_artifact",
    ledger_path: Path | None = None,
    evidence_refs: Sequence[str] = (),
) -> HumanQualityRatingFact:
    """Record a human-authoritative YDS rating from an operator utterance."""

    rating = extract_yds_rating(text)
    note = extract_yds_note(text)
    return append_human_yds_rating(
        resolve_yds_ratings_path(ledger_path),
        artifact_uri=artifact_uri,
        rating=rating,
        human_note=note,
        operator_id=operator_id,
        artifact_kind=artifact_kind,
        title=title,
        evidence_refs=evidence_refs,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record a human-authoritative YDS rating.")
    parser.add_argument("text", help="Operator phrase containing a YDS grade, e.g. 'YDS 5.12c note: ...'")
    parser.add_argument("--artifact-uri", default="conversation:current")
    parser.add_argument("--title", default="")
    parser.add_argument("--operator-id", default="dhyana")
    parser.add_argument("--artifact-kind", default="operator_artifact")
    parser.add_argument("--ledger-path", type=Path, default=None)
    parser.add_argument("--evidence-ref", action="append", default=[])
    args = parser.parse_args(argv)

    fact = record_yds_from_text(
        args.text,
        artifact_uri=args.artifact_uri,
        title=args.title,
        operator_id=args.operator_id,
        artifact_kind=args.artifact_kind,
        ledger_path=args.ledger_path,
        evidence_refs=tuple(args.evidence_ref),
    )
    print(json.dumps(asdict(fact), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
