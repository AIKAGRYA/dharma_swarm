#!/usr/bin/env python3
"""Loop 1 (Swarm Task Loop) closure check — the trunk.

GREEN only when at least one completed delegation_run carries a receipt
proving a REAL LLM provider answered (provider not in
{'', 'orchestrator', 'mock', ...}, model non-empty, input_tokens > 0).

This is the two-part Loop-1 proof:
  (1) real-provider completion exists (act, on real data), and
  (2) the receipt is replayable by run_id alone (adapt feed).

Honest current state on the live snapshot: RED — the 171 completed-with-receipt
rows all carry provider='orchestrator', model='', input_tokens=null. Those are
orchestrator dispatch receipts, not LLM-provider receipts. The real blocker is
receipt instrumentation + spine-default dispatch (NOT a provider key).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Verdict, emit, open_ro, real_provider_completed_rows  # noqa: E402


def check() -> Verdict:
    try:
        conn = open_ro()
    except FileNotFoundError as e:
        return Verdict(1, "RED", f"snapshot unavailable: {e}")
    try:
        rows = real_provider_completed_rows(conn)
    finally:
        conn.close()
    if not rows:
        return Verdict(
            1,
            "RED",
            "no completed task with a real-provider receipt "
            "(provider!='orchestrator', model!='', input_tokens>0). "
            "Real blocker: receipt instrumentation + spine-default dispatch.",
            real_data=False,
        )
    r = rows[0]
    return Verdict(
        1,
        "GREEN",
        f"{len(rows)} completed run(s) with real-provider receipt "
        f"(e.g. provider={r.get('provider')} model={r.get('model')} "
        f"input_tokens={r.get('input_tokens')} run_id={r.get('_run_id')})",
        real_data=True,
        replay_cmd=(
            "sqlite3 $LC_RUNTIME_DB "
            f"\"SELECT receipt_json FROM delegation_runs WHERE run_id='{r.get('_run_id')}'\""
        ),
    )


if __name__ == "__main__":
    sys.exit(emit(check()))
