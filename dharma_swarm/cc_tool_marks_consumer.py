"""Consumer for cc_tool_marks.jsonl — closes the Claude-Code → Dharma bridge.

Claude Code hooks write tool-use marks to ~/.dharma/stigmergy/cc_tool_marks.jsonl
(schema: tool, timestamp, source, file_path). Prior to this module, the stream
was write-only: thousands of observations landed on disk with zero runtime
consumer. This module is the minimum viable reader.

Sprint 1 Fix 3. The consumer:

  1. Tails cc_tool_marks.jsonl since a persisted cursor
  2. Aggregates: per-tool counts, per-file hotspots, recency
  3. Writes a summary to ~/.dharma/meta/cc_tool_marks_signals.json

Downstream readers (zeitgeist, recognition, future consumers) can read the
summary without paying the full JSONL tail cost.

Rollback: DHARMA_CC_TOOL_MARKS_CONSUMER=off. The consumer is additive and
safe: it does not modify cc_tool_marks.jsonl, only reads + writes a new
signals file. No hot-path dependency.
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_STATE_DIR = Path.home() / ".dharma"
_DEFAULT_MARKS_PATH = _DEFAULT_STATE_DIR / "stigmergy" / "cc_tool_marks.jsonl"
_DEFAULT_CURSOR_PATH = _DEFAULT_STATE_DIR / "stigmergy" / "cc_tool_marks_cursor.json"
_DEFAULT_SIGNALS_PATH = _DEFAULT_STATE_DIR / "meta" / "cc_tool_marks_signals.json"


class CcToolMarksConsumer:
    """Tails cc_tool_marks.jsonl and emits aggregated signals."""

    def __init__(
        self,
        marks_path: Path | None = None,
        cursor_path: Path | None = None,
        signals_path: Path | None = None,
    ) -> None:
        self._marks_path = marks_path or _DEFAULT_MARKS_PATH
        self._cursor_path = cursor_path or _DEFAULT_CURSOR_PATH
        self._signals_path = signals_path or _DEFAULT_SIGNALS_PATH

    def _load_cursor(self) -> int:
        if not self._cursor_path.exists():
            return 0
        try:
            data = json.loads(self._cursor_path.read_text())
            return int(data.get("byte_offset", 0))
        except Exception:
            logger.debug("cursor load failed, starting from 0", exc_info=True)
            return 0

    def _save_cursor(self, byte_offset: int) -> None:
        self._cursor_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "byte_offset": byte_offset,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._cursor_path.write_text(json.dumps(payload))

    def consume_since_cursor(self) -> dict[str, Any]:
        """Read new marks since cursor; aggregate; update cursor; return summary."""
        if os.getenv("DHARMA_CC_TOOL_MARKS_CONSUMER", "on").lower() == "off":
            return {"status": "disabled", "flag": "DHARMA_CC_TOOL_MARKS_CONSUMER=off"}

        if not self._marks_path.exists():
            return {"status": "no_marks_file", "path": str(self._marks_path)}

        cursor = self._load_cursor()
        file_size = self._marks_path.stat().st_size
        if cursor > file_size:
            cursor = 0  # file was rotated/truncated; start over

        new_lines = 0
        tool_counts: Counter[str] = Counter()
        file_counts: Counter[str] = Counter()
        source_counts: Counter[str] = Counter()
        earliest_ts: str | None = None
        latest_ts: str | None = None

        with self._marks_path.open("r") as f:
            f.seek(cursor)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                new_lines += 1
                tool = rec.get("tool", "unknown")
                fp = rec.get("file_path") or rec.get("path") or "unknown"
                src = rec.get("source", "unknown")
                ts = rec.get("timestamp")
                tool_counts[tool] += 1
                file_counts[fp] += 1
                source_counts[src] += 1
                if ts:
                    if earliest_ts is None or ts < earliest_ts:
                        earliest_ts = ts
                    if latest_ts is None or ts > latest_ts:
                        latest_ts = ts
            new_offset = f.tell()

        self._save_cursor(new_offset)

        summary = {
            "consumed_at": datetime.now(timezone.utc).isoformat(),
            "new_records": new_lines,
            "cursor_before": cursor,
            "cursor_after": new_offset,
            "top_tools": tool_counts.most_common(10),
            "hotspot_files": file_counts.most_common(10),
            "sources": dict(source_counts),
            "window_earliest": earliest_ts,
            "window_latest": latest_ts,
        }
        return summary

    def emit(self, summary: dict[str, Any]) -> Path:
        """Persist summary to signals file (merges with prior summary if present)."""
        self._signals_path.parent.mkdir(parents=True, exist_ok=True)
        prior: dict[str, Any] = {}
        if self._signals_path.exists():
            try:
                prior = json.loads(self._signals_path.read_text())
            except Exception:
                prior = {}

        cumulative_records = prior.get("cumulative_records", 0) + summary.get("new_records", 0)
        payload = {
            **summary,
            "cumulative_records": cumulative_records,
            "last_window_earliest": summary.get("window_earliest"),
            "last_window_latest": summary.get("window_latest"),
        }
        self._signals_path.write_text(json.dumps(payload, indent=2))
        return self._signals_path

    def run_once(self) -> dict[str, Any]:
        """Convenience: consume since cursor, emit, return summary."""
        summary = self.consume_since_cursor()
        if summary.get("status"):
            return summary
        self.emit(summary)
        return summary


def main() -> None:
    """CLI entry: python -m dharma_swarm.cc_tool_marks_consumer."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    consumer = CcToolMarksConsumer()
    result = consumer.run_once()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
