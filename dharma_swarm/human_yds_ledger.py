"""Append-only human YDS rating ledger.

The ledger is intentionally small and path-injected. It records human/operator
quality ratings in the JSONL shape already consumed by the Daily Operating
Brief, without becoming a self-grader, dashboard, runtime authority, ontology
writer, or memory consolidation path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


HUMAN_SOURCE_MARKERS = ("human", "operator", "dhyana")
DEFAULT_HUMAN_SOURCE = "human_operator"


@dataclass(frozen=True)
class HumanYDSRating:
    """One authoritative human quality rating for one artifact."""

    timestamp: str
    rating: str
    artifact: str
    human_comment: str = ""
    source: str = DEFAULT_HUMAN_SOURCE
    operator_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        """Return the JSONL record shape consumed by Daily Operating Brief."""

        record: dict[str, Any] = {
            "timestamp": self.timestamp,
            "rating": self.rating,
            "artifact": self.artifact,
            "source": self.source,
        }
        if self.human_comment:
            record["human_comment"] = self.human_comment
        if self.operator_id:
            record["operator_id"] = self.operator_id
        if self.metadata:
            record["metadata"] = self.metadata
        return record


def append_human_yds_rating(
    ledger_path: Path,
    *,
    artifact: str,
    rating: str,
    human_comment: str = "",
    source: str = DEFAULT_HUMAN_SOURCE,
    operator_id: str = "",
    timestamp: datetime | str | None = None,
    metadata: dict[str, Any] | None = None,
) -> HumanYDSRating:
    """Append one human-authoritative YDS rating to an explicit JSONL path."""

    normalized = HumanYDSRating(
        timestamp=_timestamp(timestamp),
        rating=_required("rating", rating),
        artifact=_required("artifact", artifact),
        human_comment=str(human_comment).strip(),
        source=_human_source(source),
        operator_id=str(operator_id).strip(),
        metadata=dict(metadata or {}),
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized.to_record(), sort_keys=True) + "\n")
    return normalized


def load_human_yds_ratings(
    ledger_path: Path,
    *,
    include_advisory: bool = False,
) -> list[HumanYDSRating]:
    """Load human ratings from JSONL, ignoring malformed or incomplete rows."""

    if not ledger_path.exists():
        return []
    ratings: list[HumanYDSRating] = []
    for record in _iter_jsonl_records(ledger_path):
        source = str(record.get("source") or "").strip()
        if not include_advisory and not is_human_source(source):
            continue
        rating = str(record.get("rating") or record.get("yds") or "").strip()
        artifact = str(record.get("artifact") or "").strip()
        timestamp = str(record.get("timestamp") or "").strip()
        if not rating or not artifact or not timestamp:
            continue
        ratings.append(
            HumanYDSRating(
                timestamp=timestamp,
                rating=rating,
                artifact=artifact,
                human_comment=str(
                    record.get("human_comment") or record.get("comment") or ""
                ).strip(),
                source=source,
                operator_id=str(record.get("operator_id") or "").strip(),
                metadata=record.get("metadata")
                if isinstance(record.get("metadata"), dict)
                else {},
            )
        )
    return ratings


def is_human_source(source: str) -> bool:
    """Return whether a source string names a human/operator authority."""

    lowered = source.lower()
    return any(marker in lowered for marker in HUMAN_SOURCE_MARKERS)


def _human_source(source: str) -> str:
    normalized = _required("source", source)
    if not is_human_source(normalized):
        raise ValueError("source must identify a human/operator authority")
    return normalized


def _required(field_name: str, value: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _timestamp(value: datetime | str | None) -> str:
    if value is None:
        value = datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    normalized = str(value).strip()
    if not normalized:
        raise ValueError("timestamp is required")
    return normalized


def _iter_jsonl_records(path: Path) -> Iterable[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            yield record


__all__ = [
    "DEFAULT_HUMAN_SOURCE",
    "HUMAN_SOURCE_MARKERS",
    "HumanYDSRating",
    "append_human_yds_rating",
    "is_human_source",
    "load_human_yds_ratings",
]
