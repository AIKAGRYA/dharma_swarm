"""Holon session persistence/replay (U6) — append-only cycle-record log so a holon
survives restart and resumes rather than repeating.

Pure file I/O, append-only, JSONL. Reuses the canonical agent home and the witness /
conversation_log / compass-signal append pattern (``_path`` helper +
``mkdir(parents=True, exist_ok=True)`` + line-delimited JSON). Does NOT create a new
top-level tree: events live alongside the holon's other per-agent state in
``~/.dharma/agents/<name>/holon_events.jsonl``.

A "cycle record" is whatever the loop wants to persist for one cycle (an arbitrary JSON
dict). This layer is storage-only: it does not interpret governance, never blocks, never
calls a model. Restart-replay = read prior events back in order; ``resume_point`` returns
the last cycle so a restarted loop continues from cycle N+1.
"""
from __future__ import annotations

import json
import logging
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AGENTS_ROOT = Path.home() / ".dharma" / "agents"


def _events_path(name: str, agents_root: Path | None = None) -> Path:
    return (agents_root or AGENTS_ROOT) / name / "holon_events.jsonl"


def _talk_receipts_path(name: str, agents_root: Path | None = None) -> Path:
    return (agents_root or AGENTS_ROOT) / name / "talk_receipts.jsonl"


def _conversation_receipt_dir(name: str, agents_root: Path | None = None) -> Path:
    return (agents_root or AGENTS_ROOT) / name / "dialogue" / "conversation_receipts"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def save_cycle_record(
    name: str,
    record: dict[str, Any],
    agents_root: Path | None = None,
) -> dict[str, Any]:
    """Append one cycle record to ``~/.dharma/agents/<name>/holon_events.jsonl``.

    The stored event wraps the caller's ``record`` with a monotonically increasing
    ``cycle`` index (derived from the count of prior events) and an ``at`` UTC timestamp,
    so a restarted loop can read the last ``cycle`` and continue from the next one. The
    original record payload is preserved under the ``record`` key (and the event is
    returned). Append-only: never rewrites or truncates the file.
    """
    if not isinstance(record, dict):
        raise TypeError(f"record must be a dict, got {type(record).__name__}")

    path = _events_path(name, agents_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    cycle = len(load_session(name, agents_root))
    event = {
        "cycle": cycle,
        "holon": name,
        "at": datetime.now(timezone.utc).isoformat(),
        "record": record,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def load_session(name: str, agents_root: Path | None = None) -> list[dict[str, Any]]:
    """Return the holon's prior cycle events in append order (empty list if none).

    Missing file → ``[]``. Malformed/blank lines are skipped with a warning so a single
    corrupt append can never make a restart unreplayable (replay must degrade, not crash).
    """
    path = _events_path(name, agents_root)
    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            logger.warning(
                "[holon %s] skipping malformed event at line %d: %s", name, lineno, exc
            )
    return events


def resume_point(name: str, agents_root: Path | None = None) -> dict[str, Any] | None:
    """Return the last cycle event (so a restarted loop continues at cycle+1), or None.

    None means no prior session → a restarted loop starts fresh at cycle 0. The returned
    event carries ``cycle`` (last completed index) and ``record`` (its payload); the loop
    resumes from ``cycle + 1``.
    """
    events = load_session(name, agents_root)
    if not events:
        return None
    return events[-1]


def append_talk_receipt(
    name: str,
    receipt: dict[str, Any],
    agents_root: Path | None = None,
) -> dict[str, Any]:
    """Append one direct-dialogue receipt under the holon's LivingDock.

    The legacy ``talk_receipts.jsonl`` path stays the compact operator ledger.
    A fuller JSON receipt is also written under ``dialogue/conversation_receipts``
    so D-score and dashboard surfaces can inspect the dialogue proof without
    introducing another store.
    """
    if not isinstance(receipt, dict):
        raise TypeError(f"receipt must be a dict, got {type(receipt).__name__}")

    at = str(receipt.get("at") or _utc_now())
    reply = str(receipt.get("reply") or "")
    message = str(receipt.get("you") or receipt.get("message") or "")
    normalized = {
        "schema_version": "dharma.holon_conversation_receipt.v1",
        "holon": name,
        "at": at,
        "routing_mode": str(receipt.get("routing_mode") or "holon_route"),
        "model": str(receipt.get("model") or ""),
        "session_id": str(receipt.get("session_id") or f"holon-{name}"),
        "you": message,
        "reply": reply,
        "reply_chars": len(reply),
        "message_sha256": _hash_text(message),
        "reply_sha256": _hash_text(reply),
        "context_refs": list(receipt.get("context_refs") or []),
        "policy_ceiling": str(receipt.get("policy_ceiling") or "read_only_dialogue_no_privileged_action"),
        "protected_action_claim": bool(receipt.get("protected_action_claim", False)),
        "follow_up_mission_refs": list(receipt.get("follow_up_mission_refs") or []),
    }
    for key, value in receipt.items():
        normalized.setdefault(key, value)

    receipt_dir = _conversation_receipt_dir(name, agents_root)
    receipt_dir.mkdir(parents=True, exist_ok=True)
    token = f"{at}-{name}".replace(":", "").replace("/", "-")
    receipt_path = receipt_dir / f"{token}.json"
    normalized["receipt_path"] = str(receipt_path)

    path = _talk_receipts_path(name, agents_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(normalized, ensure_ascii=False) + "\n")

    receipt_path.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return normalized


def load_talk_receipts(
    name: str,
    agents_root: Path | None = None,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Load direct-dialogue receipts from ``talk_receipts.jsonl``."""
    path = _talk_receipts_path(name, agents_root)
    if not path.exists():
        return []
    receipts: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning(
                "[holon %s] skipping malformed talk receipt at line %d: %s",
                name,
                lineno,
                exc,
            )
            continue
        if isinstance(item, dict):
            receipts.append(item)
    if limit > 0:
        return receipts[-limit:]
    return receipts
