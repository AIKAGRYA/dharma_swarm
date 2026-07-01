"""Append-only learning-signal store (Learning Spine v0).

Durability rules (contract-locked):
  * ``forge_learning_signals.jsonl`` — append-only signal rows (deduped on key).
  * ``ingestion_ledger.jsonl``       — append-only; one event per ingest call,
    EVEN when every signal is a duplicate (so re-ingestion is auditable).
  * ``malformed_reports.jsonl``      — append-only diagnostics; never crashes.
  * ``signal_index.json`` / ``latest.json`` / ``latest.md`` — DERIVED, rewritten
    atomically each ingest.

The store never rewrites source scheduler artifacts and never touches router,
Darwin, prompt, roster, or topology state. Negative/null rows are stored with the
same durability as positive rows.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ROOT = Path("~/.dharma/forge_v1/learning_signals").expanduser()

SIGNALS_FILE = "forge_learning_signals.jsonl"
LEDGER_FILE = "ingestion_ledger.jsonl"
MALFORMED_FILE = "malformed_reports.jsonl"
INDEX_FILE = "signal_index.json"
LATEST_JSON = "latest.json"
LATEST_MD = "latest.md"


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _as_dict(sig) -> dict:
    return sig.to_dict() if hasattr(sig, "to_dict") else dict(sig)


class LearningStore:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root).expanduser() if root else DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    # -- paths --
    @property
    def signals_path(self) -> Path:
        return self.root / SIGNALS_FILE

    @property
    def ledger_path(self) -> Path:
        return self.root / LEDGER_FILE

    @property
    def malformed_path(self) -> Path:
        return self.root / MALFORMED_FILE

    # -- append-only writers --
    def _append_jsonl(self, path: Path, row: dict) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _atomic_write(self, path: Path, text: str) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)

    # -- reads --
    def existing_keys(self) -> set:
        keys: set = set()
        if self.signals_path.exists():
            for line in self.signals_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    keys.add(json.loads(line).get("signal_key"))
                except json.JSONDecodeError:
                    continue
        return keys

    def load_signals(self) -> list[dict]:
        rows: list[dict] = []
        if self.signals_path.exists():
            for line in self.signals_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return rows

    def query(self, **filters) -> list[dict]:
        """Filter stored signals by exact field match (taskbed, mission_class,
        arm, contamination_state, action, ...)."""
        out = []
        for row in self.load_signals():
            if all(row.get(k) == v for k, v in filters.items()):
                out.append(row)
        return out

    # -- main entry --
    def append_signals(
        self,
        signals,
        *,
        source_report_sha256: str,
        run_id: str,
        ingested_at: str | None = None,
    ) -> dict:
        """Append new (deduped) signal rows and ALWAYS record an ingestion event.

        Returns a summary dict: {n_signals, n_new, n_duplicate, new_keys, ingested_at}.
        """
        ingested_at = ingested_at or _utcnow()
        rows = [_as_dict(s) for s in signals]
        known = self.existing_keys()

        new_keys: list[str] = []
        seen_this_call: set = set()
        for row in rows:
            key = row.get("signal_key")
            if key in known or key in seen_this_call:
                continue
            self._append_jsonl(self.signals_path, row)
            new_keys.append(key)
            seen_this_call.add(key)

        # Ledger event fires unconditionally — even when everything is a duplicate.
        event = {
            "event": "ingest",
            "ingested_at": ingested_at,
            "source_report_sha256": source_report_sha256,
            "run_id": run_id,
            "n_signals": len(rows),
            "n_new": len(new_keys),
            "n_duplicate": len(rows) - len(new_keys),
            "new_keys": new_keys,
        }
        self._append_jsonl(self.ledger_path, event)

        self._rebuild_derived(latest_rows=rows, latest_event=event)
        return {
            "n_signals": len(rows),
            "n_new": len(new_keys),
            "n_duplicate": len(rows) - len(new_keys),
            "new_keys": new_keys,
            "ingested_at": ingested_at,
        }

    def record_malformed(self, report_path: str, error: str, ingested_at: str | None = None) -> None:
        self._append_jsonl(
            self.malformed_path,
            {
                "event": "malformed_report",
                "ingested_at": ingested_at or _utcnow(),
                "path": str(report_path),
                "error": str(error),
            },
        )

    # -- derived (atomic overwrite) --
    def _rebuild_derived(self, *, latest_rows: list[dict], latest_event: dict) -> None:
        all_rows = self.load_signals()
        index = {
            r.get("signal_key"): {
                "arm": r.get("arm"),
                "taskbed": r.get("taskbed"),
                "mission_class": r.get("mission_class"),
                "run_id": r.get("run_id"),
                "evidence_strength": r.get("evidence_strength"),
                "action": r.get("action"),
                "n_blockers": len(r.get("promotion_blockers", []) or []),
            }
            for r in all_rows
        }
        self._atomic_write(self.root / INDEX_FILE, json.dumps(index, indent=2, sort_keys=True))
        self._atomic_write(
            self.root / LATEST_JSON,
            json.dumps({"event": latest_event, "signals": latest_rows}, indent=2, sort_keys=True),
        )
        self._atomic_write(self.root / LATEST_MD, _latest_md(latest_event, latest_rows))


def _latest_md(event: dict, rows: list[dict]) -> str:
    lines = [
        f"# Forge learning signals — latest ingest",
        "",
        f"- run_id: `{event.get('run_id')}`",
        f"- ingested_at: {event.get('ingested_at')}",
        f"- signals: {event.get('n_signals')} ({event.get('n_new')} new, {event.get('n_duplicate')} duplicate)",
        "",
        "| arm | evidence_strength | action | blockers |",
        "| --- | --- | --- | --- |",
    ]
    for r in rows:
        blockers = ", ".join(r.get("promotion_blockers", []) or []) or "—"
        lines.append(
            f"| {r.get('arm')} | {r.get('evidence_strength')} | {r.get('action')} | {blockers} |"
        )
    return "\n".join(lines) + "\n"
