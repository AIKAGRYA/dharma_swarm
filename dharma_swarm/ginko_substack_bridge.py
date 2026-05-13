"""Bridge Agni VWrite Substack publish state into runtime operator actions.

The actual Substack publisher lives on Agni under ``/root/agent/vwrite``.
This module intentionally does not publish, authenticate, or inspect secrets.
It consumes the publisher's append-only ``published.jsonl`` log and records
operator-visible facts in Dharma's runtime database.
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm.runtime_state import (
    DEFAULT_RUNTIME_DB,
    OperatorAction,
    RuntimeStateStore,
    operator_action_id_for_payload,
)

logger = logging.getLogger(__name__)

DEFAULT_AGNI_PUBLISHED_LOG = Path("/root/agent/vwrite/state/published.jsonl")
PUBLISH_CHANNEL = "substack"
SOURCE_NAME = "agni_vwrite_published_jsonl"


@dataclass(frozen=True)
class SubstackPublishRecord:
    """One sanitized row from Agni's VWrite published.jsonl log."""

    timestamp: datetime
    timestamp_raw: str
    filename: str
    title: str
    subtitle: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    publication: str = ""
    success: bool = False
    method: str = ""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(raw: Any) -> datetime:
    if isinstance(raw, str) and raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            logger.debug("Invalid Substack publish timestamp: %r", raw)
    return _utc_now()


def _as_tags(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def parse_substack_publish_entry(entry: dict[str, Any]) -> SubstackPublishRecord | None:
    """Parse one VWrite publish row, returning None for unusable rows."""
    filename = str(entry.get("filename") or "").strip()
    title = str(entry.get("title") or "").strip()
    if not filename or not title:
        return None

    timestamp_raw = str(entry.get("timestamp") or "")
    return SubstackPublishRecord(
        timestamp=_parse_timestamp(timestamp_raw),
        timestamp_raw=timestamp_raw,
        filename=filename,
        title=title,
        subtitle=str(entry.get("subtitle") or ""),
        tags=_as_tags(entry.get("tags")),
        publication=str(entry.get("publication") or ""),
        success=bool(entry.get("success")),
        method=str(entry.get("method") or ""),
    )


def iter_substack_publish_records(path: Path | str) -> Iterable[SubstackPublishRecord]:
    """Yield sanitized publish records from a local copy of published.jsonl."""
    log_path = Path(path)
    if not log_path.exists():
        return

    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("Skipping invalid Substack publish JSONL row")
            continue
        if not isinstance(raw, dict):
            continue
        record = parse_substack_publish_entry(raw)
        if record is not None:
            yield record


def substack_publish_operator_action(
    record: SubstackPublishRecord,
    *,
    actor: str = "agni_vwrite",
    source_log: Path | str = DEFAULT_AGNI_PUBLISHED_LOG,
) -> OperatorAction:
    """Convert one sanitized publish record into a deterministic action."""
    action_name = (
        "ginko_substack_post_published"
        if record.success
        else "ginko_substack_publish_failed"
    )
    reason = (
        "Agni VWrite Substack publish succeeded"
        if record.success
        else "Agni VWrite Substack publish failed"
    )
    stable_payload = {
        "publish_channel": PUBLISH_CHANNEL,
        "timestamp": record.timestamp_raw or record.timestamp.isoformat(),
        "filename": record.filename,
        "title": record.title,
        "publication": record.publication,
        "success": record.success,
        "method": record.method,
    }
    payload = {
        **stable_payload,
        "subtitle": record.subtitle,
        "tags": list(record.tags),
        "source": SOURCE_NAME,
        "source_log": str(source_log),
    }
    return OperatorAction(
        action_id=operator_action_id_for_payload(
            action_name=action_name,
            actor=actor,
            reason=reason,
            payload=stable_payload,
        ),
        action_name=action_name,
        actor=actor,
        reason=reason,
        payload=payload,
        created_at=record.timestamp,
    )


def record_substack_publish_actions(
    published_log: Path | str = DEFAULT_AGNI_PUBLISHED_LOG,
    *,
    runtime_db: Path | str = DEFAULT_RUNTIME_DB,
    actor: str = "agni_vwrite",
    include_failures: bool = True,
) -> list[OperatorAction]:
    """Ingest Agni publish rows into runtime operator_actions idempotently."""
    runtime = RuntimeStateStore(Path(runtime_db))
    actions: list[OperatorAction] = []
    for record in iter_substack_publish_records(published_log):
        if not include_failures and not record.success:
            continue
        action = substack_publish_operator_action(
            record,
            actor=actor,
            source_log=published_log,
        )
        actions.append(runtime.record_operator_action_sync(action))
    return actions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest Agni VWrite Substack publish log into runtime operator_actions."
    )
    parser.add_argument(
        "--published-log",
        type=Path,
        default=DEFAULT_AGNI_PUBLISHED_LOG,
        help="Path to Agni VWrite published.jsonl or a local copy",
    )
    parser.add_argument(
        "--runtime-db",
        type=Path,
        default=DEFAULT_RUNTIME_DB,
        help="Runtime SQLite database path",
    )
    parser.add_argument(
        "--actor",
        default="agni_vwrite",
        help="Actor label to store on operator_actions",
    )
    parser.add_argument(
        "--success-only",
        action="store_true",
        help="Record successful publishes only",
    )
    args = parser.parse_args(argv)

    actions = record_substack_publish_actions(
        args.published_log,
        runtime_db=args.runtime_db,
        actor=args.actor,
        include_failures=not args.success_only,
    )
    print(f"Recorded {len(actions)} Substack publish operator action(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
