#!/usr/bin/env python3
"""Loop 10 (Context Agent) closure check. See CYBERNETIC_LOOP_MAP.md row 10.

Loop 10 is the ecosystem's nervous system (dharma_swarm/context_agent.py). Its
five transitions:

  SENSE      NervousSystem.scan_freshness() over the owner-surface context sources.
  INTERPRET  NervousSystem.assess_health() -> health score + alerts.
  CONSTRAIN  bloat/threshold detection arms the LLM act (only a real >50KB note
             triggers a distillation dispatch).
  ACT        Intelligence.distill_notes() -> a REAL live FREE provider compresses
             the note and writes a distilled artifact to context/distilled/ (the
             Loop-1 consume edge), receipted on the spine.
  ADAPT      stigmergy mark referencing the artifact + CONTEXT_HEALTH signal +
             cycle freshness write -> feeds the next sense.

GREEN only when, on REAL data, ALL of the following hold (no fixture can pass):

  (A) ACT receipt: the scoped runtime db (LC_RUNTIME_DB) holds >=1 completed
      delegation_run whose receipt proves a REAL provider answered the context
      agent's act-step (provider not in {orchestrator,mock,...}, model!='',
      input_tokens>0) AND is tagged loop_role='context_agent_act' with a
      side_effect_key and a distilled_artifact path.
  (B) ACT artifact on the owner surface: that distilled_artifact exists under the
      state dir's context/distilled/ and carries the auto-distill header
      (genuine compressed output, not an empty/stub file).
  (C) ADAPT edge: a stigmergy mark on the scoped owner surface
      (state_dir/stigmergy/marks.jsonl) from agent='context-agent' whose
      file_path is that same distilled artifact, AND a CONTEXT_CYCLE adapt
      receipt (LC_LOOP10_DIR) whose act_side_effect_key matches the spine
      receipt's side_effect_key and whose health_score / freshness write exist.
  (D) One Wire intact: the adapt edge is an internal context write; it must NOT
      reference an archive.jsonl fitness write (fail loud if it does).

Honest current state with no scoped run present: RED — the context agent's act
edge (the real-provider distillation) has not been driven on real data in this
scope. GREEN is earned by running drive_loop_10.py (real free-provider distill +
owner-surface artifacts + spine receipt). Loop 10 consumes Loop 1; the act IS a
real Loop-1-style spine dispatch.

Replayable by a fresh agent from the scoped artifacts alone:
  LC_LOOP10_STATE_DIR=<state_dir> LC_RUNTIME_DB=<scoped_db> \
    LC_LOOP10_DIR=<dir> python3 scripts/governance/closure/check_loop_10.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Verdict, emit, open_ro, real_provider_completed_rows  # noqa: E402

STATE_DIR = Path(
    os.environ.get("LC_LOOP10_STATE_DIR", str(Path.home() / ".dharma"))
)
LOOP10_DIR = Path(os.environ.get("LC_LOOP10_DIR", "/tmp/lc_loop10"))


def check() -> Verdict:
    # (A) ACT receipt: a real-provider completed row tagged context_agent_act.
    try:
        conn = open_ro()
    except FileNotFoundError as e:
        return Verdict(
            10,
            "RED",
            f"snapshot unavailable for act receipt: {e}. Drive a real cycle: "
            "drive_loop_10.py.",
            real_data=False,
        )
    try:
        rows = real_provider_completed_rows(conn)
    finally:
        conn.close()

    act_rows = [
        r for r in rows
        if str(r.get("attributes", {}).get("loop_role", "")) == "context_agent_act"
        and r.get("attributes", {}).get("side_effect_key")
        and r.get("attributes", {}).get("distilled_artifact")
    ]
    if not act_rows:
        return Verdict(
            10,
            "RED",
            "no real-provider context-agent act receipt "
            "(loop_role='context_agent_act', side_effect_key, distilled_artifact, "
            "input_tokens>0). The act-step (distillation) must be a real spine "
            "dispatch. Drive it: drive_loop_10.py.",
            real_data=False,
        )

    r = act_rows[0]
    attrs = r["attributes"]
    sek = attrs["side_effect_key"]
    distilled_artifact = Path(attrs["distilled_artifact"])

    # (B) ACT artifact on the owner surface (context/distilled/), real content.
    if not distilled_artifact.exists():
        return Verdict(
            10,
            "RED",
            f"act receipt present but distilled artifact missing on owner surface: "
            f"{distilled_artifact}",
            real_data=False,
        )
    if "context/distilled/" not in str(distilled_artifact).replace("\\", "/"):
        return Verdict(
            10,
            "RED",
            f"distilled artifact not on the context-agent owner surface "
            f"(expected context/distilled/): {distilled_artifact}",
            real_data=False,
        )
    art_text = distilled_artifact.read_text(encoding="utf-8")
    if "Distilled" not in art_text or "Key Findings" not in art_text or len(art_text) < 200:
        return Verdict(
            10,
            "RED",
            "distilled artifact is empty/stub (missing auto-distill header or "
            "key-findings body) — distillation did not really run",
            real_data=False,
        )

    # (C) ADAPT edge: stigmergy mark on owner surface + CONTEXT_CYCLE adapt receipt.
    marks_file = STATE_DIR / "stigmergy" / "marks.jsonl"
    mark_ok = False
    if marks_file.exists():
        for line in marks_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                m = json.loads(line)
            except Exception:
                continue
            if (
                str(m.get("agent", "")) == "context-agent"
                and str(m.get("file_path", "")) == str(distilled_artifact)
            ):
                mark_ok = True
                break
    if not mark_ok:
        return Verdict(
            10,
            "RED",
            f"adapt edge missing: no context-agent stigmergy mark referencing "
            f"{distilled_artifact} in {marks_file}",
            real_data=False,
        )

    adapt_path = LOOP10_DIR / "loop10_adapt_receipt.json"
    if not adapt_path.exists():
        return Verdict(
            10,
            "RED",
            f"adapt edge missing: no CONTEXT_CYCLE receipt at {adapt_path}",
            real_data=False,
        )
    adapt = json.loads(adapt_path.read_text(encoding="utf-8"))
    if adapt.get("type") != "CONTEXT_CYCLE":
        return Verdict(10, "RED", "adapt receipt malformed (type != CONTEXT_CYCLE)", real_data=False)
    if adapt.get("act_side_effect_key") != sek:
        return Verdict(
            10,
            "RED",
            "adapt receipt side_effect_key does not match the spine act receipt "
            "(owner-surface adapt not provably derived from the audited real act)",
            real_data=False,
        )
    if not adapt.get("health_score") and adapt.get("health_score") != 0:
        return Verdict(10, "RED", "adapt receipt missing health_score (interpret edge)", real_data=False)
    fresh_path = STATE_DIR / "context" / "freshness.json"
    if not fresh_path.exists():
        return Verdict(
            10,
            "RED",
            f"adapt edge missing: cycle freshness write absent at {fresh_path}",
            real_data=False,
        )
    if not adapt.get("context_health_signals"):
        return Verdict(
            10,
            "RED",
            "adapt edge missing: no CONTEXT_HEALTH signal recorded (the emit edge "
            "that feeds other loops)",
            real_data=False,
        )

    # (D) One Wire invariant: internal context write only, never archive fitness.
    blob = adapt_path.read_text(encoding="utf-8")
    if "archive.jsonl" in blob and "no archive" not in blob:
        return Verdict(
            10,
            "RED",
            "One Wire VIOLATION: context adapt edge references an archive.jsonl "
            "fitness write (internal context must never touch archive fitness)",
            real_data=False,
        )

    return Verdict(
        10,
        "GREEN",
        f"real context-agent cycle closed all 5 transitions: sense/interpret on "
        f"{STATE_DIR} (health={adapt.get('health_score')}), constrain armed the "
        f"act (bloated note), ACT real-provider distill "
        f"provider={r.get('provider')} model={r.get('model')} "
        f"input_tokens={r.get('input_tokens')} -> owner-surface artifact "
        f"{distilled_artifact.name}; adapt edge fired (stigmergy mark + "
        f"CONTEXT_HEALTH signal + freshness write, side_effect_key={sek}); "
        f"One Wire intact",
        real_data=True,
        replay_cmd=(
            f"LC_LOOP10_STATE_DIR={STATE_DIR} LC_RUNTIME_DB={os.environ.get('LC_RUNTIME_DB','/tmp/lc_runtime.db')} "
            f"LC_LOOP10_DIR={LOOP10_DIR} python3 scripts/governance/closure/check_loop_10.py"
        ),
    )


if __name__ == "__main__":
    sys.exit(emit(check()))
