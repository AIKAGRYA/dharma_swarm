"""Shared helpers for the loop-closure check harness.

Verdict contract (binary + earned):
  GREEN   -> automated check passed on REAL data (real provider tokens / real receipt). exit 0.
  RED     -> wired but not closed on real data (the honest current state). exit 1.
  BLOCKED -> correctly gated (e.g. One Wire quorum N>=5/M>=3 unmet). exit 2.

A loop flips RED->GREEN only when its check exits 0 on real data, replayable
by a fresh agent from receipts alone. No fixtures, no --dry-run, no smoke.
"""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path

GREEN, RED, BLOCKED = "GREEN", "RED", "BLOCKED"
_EXIT = {GREEN: 0, RED: 1, BLOCKED: 2}

# Read-only snapshot defaults (never lock the live db). Override via env.
RUNTIME_DB = os.environ.get("LC_RUNTIME_DB", "/tmp/lc_runtime.db")
ARCHIVE_JSONL = os.environ.get("LC_ARCHIVE_JSONL", "/tmp/lc_archive.jsonl")


@dataclass
class Verdict:
    loop: int
    verdict: str
    reason: str
    real_data: bool = False
    replay_cmd: str = ""

    def exit_code(self) -> int:
        return _EXIT[self.verdict]

    def line(self) -> str:
        return f"LOOP {self.loop}: {self.verdict} + {self.reason}"

    def to_dict(self) -> dict:
        return asdict(self)


def open_ro(db_path: str = RUNTIME_DB) -> sqlite3.Connection:
    """Open the snapshot read-only so a live db is never locked."""
    p = Path(db_path)
    if not p.exists():
        raise FileNotFoundError(f"snapshot db missing: {db_path}")
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def real_provider_completed_rows(conn: sqlite3.Connection) -> list[dict]:
    """Completed delegation_runs whose receipt proves a REAL LLM provider answered.

    Hard filters that no fixture / orchestrator-dispatch receipt can pass:
      - status = 'completed'
      - receipt_json present
      - receipt.provider is a real model provider (NOT '', 'orchestrator', 'mock', 'stub')
      - receipt.model is non-empty
      - receipt.input_tokens > 0  (a real provider returns token accounting)
    """
    bad_providers = {"", "orchestrator", "mock", "stub", "fixture", "test", "none"}
    out: list[dict] = []
    cur = conn.execute(
        "SELECT run_id, receipt_json FROM delegation_runs "
        "WHERE status='completed' AND receipt_json IS NOT NULL AND receipt_json!=''"
    )
    for run_id, rj in cur:
        try:
            r = json.loads(rj)
        except Exception:
            continue
        provider = str(r.get("provider", "")).strip().lower()
        model = str(r.get("model", "")).strip()
        itok = r.get("input_tokens")
        if provider in bad_providers:
            continue
        if not model:
            continue
        if not isinstance(itok, (int, float)) or itok <= 0:
            continue
        r["_run_id"] = run_id
        out.append(r)
    return out


def emit(verdict: Verdict) -> int:
    print(verdict.line())
    return verdict.exit_code()
