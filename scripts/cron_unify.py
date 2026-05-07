#!/usr/bin/env python3
"""v2.1 Phase 2 — Cron substrate unification.

The repo declares 17 jobs in ``dharma_swarm/cron_jobs.json`` (flat list, schema A);
the live daemon reads 6 jobs from ``~/.dharma/cron/jobs.json`` (``{jobs:[...]}`` form,
schema B). The two share ONE id (``ontology_insight_brief``); 16 repo declarations
are orphaned. ``cron_daemon.py:84`` only ticks the live file, so the live file is
canonical. This script proposes a merge into ``~/.dharma/cron/jobs.unified.json``
WITHOUT touching the live file. Operator reviews, then explicitly swaps.

Schema translation (repo → live):

  ``trigger=interval, interval_seconds=N`` → ``schedule={kind:"interval", minutes:N//60}``
  ``cadence={hour:H, minute:M}``           → ``schedule={kind:"cron", expr:"M H * * *"}``
  No recognized trigger                    → ``enabled=false`` with note

Defaults: ``handler="headless_prompt"`` (matches ``launchd_job_runner.py:143``);
``prompt`` carried verbatim; ``enabled`` carried unless mapping fails.

Conflict policy: when ids overlap, LIVE wins (it's the running ground truth).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_FILE = Path(__file__).resolve().parent.parent / "cron_jobs.json"
LIVE_FILE = Path(os.path.expanduser("~/.dharma/cron/jobs.json"))
OUT_DIR = Path(os.path.expanduser("~/.dharma/audit"))
PROPOSED_FILE = LIVE_FILE.parent / "jobs.unified.json"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _translate_repo_job(repo: dict) -> tuple[dict | None, str]:
    """Translate a repo-schema job dict to live-schema. Returns (live_job, note)."""
    job_id = repo.get("id")
    if not job_id:
        return None, "missing id"

    schedule: dict[str, Any] | None = None
    trigger = repo.get("trigger")
    repo_schedule = repo.get("schedule")  # repo schema names this `schedule` (object form)
    cadence = repo.get("cadence")          # alternate name in some entries
    src = repo_schedule if isinstance(repo_schedule, dict) else cadence
    if trigger == "interval" and "interval_seconds" in repo:
        secs = int(repo["interval_seconds"])
        minutes = max(1, secs // 60)
        schedule = {"kind": "interval", "minutes": minutes, "display": f"every {minutes}m"}
    elif trigger == "cron" and isinstance(src, dict) and "hour" in src and "minute" in src:
        h, m = int(src["hour"]), int(src["minute"])
        expr = f"{m} {h} * * *"
        schedule = {"kind": "cron", "expr": expr, "display": expr}
    elif isinstance(src, dict) and "hour" in src and "minute" in src:
        h, m = int(src["hour"]), int(src["minute"])
        expr = f"{m} {h} * * *"
        schedule = {"kind": "cron", "expr": expr, "display": expr}
    elif trigger in (None, "manual"):
        return {
            "id": job_id,
            "name": repo.get("name", job_id),
            "prompt": repo.get("prompt", ""),
            "handler": repo.get("handler", "headless_prompt"),
            "schedule": None,
            "enabled": False,
            "urgent": False,
            "deliver": "local",
            "_unify_note": "no recognized cadence; disabled pending operator decision",
        }, "no cadence"
    else:
        return None, f"unrecognized trigger: {trigger!r}"

    return {
        "id": job_id,
        "name": repo.get("name", job_id),
        "prompt": repo.get("prompt", ""),
        "handler": repo.get("handler", "headless_prompt"),
        "schedule": schedule,
        "schedule_display": schedule["display"],
        "enabled": bool(repo.get("enabled", True)),
        "urgent": bool(repo.get("urgent", False)),
        "deliver": repo.get("deliver", "local"),
        "_unify_origin": "repo",
        "_unify_translated_at": _utc_iso(),
    }, "translated"


def main() -> int:
    disable_new = "--disable-new" in sys.argv[1:]
    if not REPO_FILE.exists():
        print(f"missing {REPO_FILE}", file=sys.stderr)
        return 1
    if not LIVE_FILE.exists():
        print(f"missing {LIVE_FILE}", file=sys.stderr)
        return 1

    repo_jobs = json.loads(REPO_FILE.read_text())
    if not isinstance(repo_jobs, list):
        print(f"{REPO_FILE} is not a list", file=sys.stderr)
        return 1

    live_blob = json.loads(LIVE_FILE.read_text())
    live_jobs = live_blob.get("jobs", [])

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    live_ids = {j["id"]: j for j in live_jobs if "id" in j}
    proposed: list[dict] = []
    notes: list[str] = []
    skipped: list[dict] = []

    # Carry every live job through unchanged (preserve running state, run history, etc).
    for j in live_jobs:
        proposed.append(j)

    # Translate each repo job; skip on id collision (live wins).
    for repo in repo_jobs:
        rid = repo.get("id")
        if rid in live_ids:
            notes.append(f"repo {rid}: skipped (live wins on id collision)")
            continue
        translated, note = _translate_repo_job(repo)
        notes.append(f"repo {rid}: {note}")
        if translated is None:
            skipped.append({"id": rid, "reason": note, "repo_job": repo})
            continue
        if disable_new:
            translated["enabled"] = False
            translated.setdefault("_unify_note", "imported with enabled=false; opt-in after prereqs verified")
        proposed.append(translated)

    proposed_blob = {
        "jobs": proposed,
        "updated_at": _utc_iso(),
        "_unify_meta": {
            "live_count_before": len(live_jobs),
            "repo_count": len(repo_jobs),
            "translated_count": len(proposed) - len(live_jobs),
            "skipped_count": len(skipped),
            "notes": notes,
        },
    }

    PROPOSED_FILE.write_text(json.dumps(proposed_blob, indent=2))
    audit_path = OUT_DIR / f"cron_split_brain_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    audit_path.write_text(json.dumps({
        "live_before": live_blob,
        "repo_before": repo_jobs,
        "proposed": proposed_blob,
        "skipped": skipped,
    }, indent=2))

    print(f"PROPOSED unified file -> {PROPOSED_FILE}")
    print(f"AUDIT (both originals + proposed + skipped) -> {audit_path}")
    print()
    print(f"Live before:  {len(live_jobs)} jobs")
    print(f"Repo:         {len(repo_jobs)} jobs")
    print(f"Translated:   {len(proposed) - len(live_jobs)} new jobs added")
    print(f"Skipped:      {len(skipped)} (see audit file)")
    print(f"Proposed:     {len(proposed)} jobs total")
    print()
    print("Notes:")
    for n in notes:
        print(f"  - {n}")
    print()
    print("LIVE FILE NOT TOUCHED. Review the proposed file, then atomic-swap manually:")
    print(f"  cp {LIVE_FILE} {LIVE_FILE.with_suffix('.json.bak')}")
    print(f"  mv {PROPOSED_FILE} {LIVE_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
