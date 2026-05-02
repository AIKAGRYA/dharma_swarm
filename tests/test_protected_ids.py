from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTECTED_IDS = ROOT / ".dharma_protected_ids.jsonl"
KNOWN_TYPES = {"module", "skill", "rule", "file", "agent"}
REQUIRED_FIELDS = {
    "artifact_id",
    "artifact_type",
    "path",
    "reason",
    "added_by",
    "added_at",
    "immutable",
}


def _load_entries() -> list[dict]:
    entries: list[dict] = []
    for line in PROTECTED_IDS.read_text(encoding="utf-8").splitlines():
        assert line.strip(), "blank lines are not allowed in protected ids jsonl"
        entries.append(json.loads(line))
    return entries


def _resolve_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return ROOT / path


def test_protected_ids_jsonl_parses_cleanly() -> None:
    entries = _load_entries()
    assert len(entries) == 11
    assert len({entry["artifact_id"] for entry in entries}) == len(entries)


def test_protected_ids_schema_and_types() -> None:
    for entry in _load_entries():
        assert REQUIRED_FIELDS <= set(entry)
        assert entry["artifact_type"] in KNOWN_TYPES
        assert entry["immutable"] is True
        assert entry["reason"].strip()
        assert entry["added_by"].strip()


def test_protected_ids_paths_exist() -> None:
    missing = [entry["path"] for entry in _load_entries() if not _resolve_path(entry["path"]).exists()]
    assert missing == []


def test_protected_ids_timestamps_are_iso8601() -> None:
    for entry in _load_entries():
        parsed = datetime.fromisoformat(entry["added_at"])
        assert parsed.tzinfo is not None


def test_protected_ids_file_is_stable_across_rereads() -> None:
    first = hashlib.sha256(PROTECTED_IDS.read_bytes()).hexdigest()
    second = hashlib.sha256(PROTECTED_IDS.read_bytes()).hexdigest()
    assert first == second
