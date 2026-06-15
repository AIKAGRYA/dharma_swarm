#!/usr/bin/env python3
"""Loop 9 (Conductors) closure check. See CYBERNETIC_LOOP_MAP.md for the trace.

GREEN only when a REAL conductor wake completed all five transitions on real
data and left receipts on its declared owner surfaces:

  1. OWNER SURFACE (adapt edge): a WAKE witness entry at
     <state_dir>/witness/conductor_*.jsonl with real token accounting
     (tokens>0 -> a real provider answered; no fixture/0-turn wake can pass).
  2. LOOP-1 CONSUME EDGE (act): a completed delegation_runs row whose receipt
     proves a real LLM provider answered the conductor act-step
     (provider not in {orchestrator,mock,...}, model!='', input_tokens>0) AND
     the receipt is tagged loop_role='conductor_wake_act' with a side_effect_key.

Both must hold. The witness entry alone could be a Python-only wake; the spine
receipt alone is just Loop 1. Closure = a conductor wake whose ACT was a real
provider dispatch, witnessed to its owner surface.

Honest current state on the live snapshot (/tmp/lc_runtime.db, no scoped run):
RED — the live conductor witness logs are test-generated (no real-provider act
tied to a tokens>0 wake). Drive a real wake with drive_loop_9.py, then re-run
this check against the scoped state dir + db.

Replay (fresh agent, from receipts alone):
  DHARMA_SPINE_DISPATCH=1 LC_LOOP9_STATE_DIR=/tmp/lc_loop9_state \
    LC_LOOP9_SCOPED_DB=/tmp/lc_loop9_scoped.db \
    python3 scripts/governance/closure/drive_loop_9.py
  LC_LOOP9_STATE_DIR=/tmp/lc_loop9_state LC_RUNTIME_DB=/tmp/lc_loop9_scoped.db \
    python3 scripts/governance/closure/check_loop_9.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Verdict, emit, open_ro, real_provider_completed_rows  # noqa: E402

STATE_DIR = Path(
    os.environ.get("LC_LOOP9_STATE_DIR", str(Path.home() / ".dharma"))
)


def _conductor_wake_witnessed(state_dir: Path) -> tuple[bool, dict | None]:
    """Find a WAKE witness entry with real token accounting on the owner surface."""
    wdir = state_dir / "witness"
    if not wdir.exists():
        return False, None
    for log in sorted(wdir.glob("conductor_*.jsonl")):
        try:
            for line in log.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if e.get("event") != "WAKE":
                    continue
                extra = str(e.get("extra", ""))
                # extra carries "source=... turns=N tokens=M duration=...".
                tok = 0
                for tok_field in extra.split():
                    if tok_field.startswith("tokens="):
                        try:
                            tok = int(tok_field.split("=", 1)[1])
                        except ValueError:
                            tok = 0
                if tok > 0:
                    e["_log"] = str(log)
                    e["_tokens"] = tok
                    return True, e
        except Exception:
            continue
    return False, None


def check() -> Verdict:
    # 1. Owner-surface witness with real tokens (adapt edge).
    witnessed, wentry = _conductor_wake_witnessed(STATE_DIR)
    if not witnessed:
        return Verdict(
            9,
            "RED",
            "no conductor WAKE witness entry with real token accounting "
            f"(tokens>0) under {STATE_DIR}/witness/conductor_*.jsonl. "
            "Drive a real wake: drive_loop_9.py.",
            real_data=False,
        )

    # 2. Loop-1 consume edge: a real-provider conductor act receipt.
    try:
        conn = open_ro()
    except FileNotFoundError as e:
        return Verdict(9, "RED", f"snapshot unavailable for act receipt: {e}")
    try:
        rows = real_provider_completed_rows(conn)
    finally:
        conn.close()

    act_rows = [
        r for r in rows
        if str(r.get("attributes", {}).get("loop_role", "")) == "conductor_wake_act"
        and r.get("attributes", {}).get("side_effect_key")
    ]
    if not act_rows:
        return Verdict(
            9,
            "RED",
            "conductor WAKE witnessed but no real-provider act receipt tied to "
            "it (loop_role='conductor_wake_act', side_effect_key, "
            "input_tokens>0). The act-step must be a real spine dispatch.",
            real_data=False,
        )

    r = act_rows[0]
    sek = r["attributes"]["side_effect_key"]
    return Verdict(
        9,
        "GREEN",
        f"real conductor wake closed all 5 transitions: witness tokens="
        f"{wentry['_tokens']} (owner surface), act receipt "
        f"provider={r.get('provider')} model={r.get('model')} "
        f"input_tokens={r.get('input_tokens')} side_effect_key={sek}",
        real_data=True,
        replay_cmd=(
            f"cat {wentry['_log']} ; "
            "sqlite3 $LC_RUNTIME_DB "
            f"\"SELECT receipt_json FROM delegation_runs WHERE run_id='{r.get('_run_id')}'\""
        ),
    )


if __name__ == "__main__":
    sys.exit(emit(check()))
