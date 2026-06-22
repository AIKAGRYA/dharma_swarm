#!/usr/bin/env python3
"""track_coherence.py — one unified coherence projection over the track lane.

A coherence cockpit shouldn't have to stitch four governance feeds together.
This read-model joins them into ONE per-track + per-umbrella record:

  presence grade        reports/governance/active_track_evidence.json
  quality + attestation reports/governance/track_health.json   (Opus 4.8 quorum)
  audit consensus       reports/governance/track_audits/*.audit.json (3 Opus runs)
  criterion smells      reports/governance/criterion_lint.json
  intent / edges / TTL  docs/governance/ACTIVE_TRACK.yaml

It also rolls the 7 tracks up to the 3 consolidation UMBRELLAS and reports
spine-objective coverage. It owns NO truth — every field is projected from an
existing owner (doctrine: read models project truth; they do not become
authority). Generate fresh inputs first with `make track-health` and
`make criterion-lint`.

Per-track coherence_state (the single signal a cockpit row leads with):
  CLOSE_READY  attested by the Opus quorum, claim holds, no HIGH smell
  OVERSTATED   file-grade green but the quorum withholds attestation
  STALE        verified_at older than ttl_days
  IN_PROGRESS  honestly not yet file-shippable
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

ACTIVE_TRACK_PATH = Path("docs/governance/ACTIVE_TRACK.yaml")
EVIDENCE_JSON = Path("reports/governance/active_track_evidence.json")
HEALTH_JSON = Path("reports/governance/track_health.json")
LINT_JSON = Path("reports/governance/criterion_lint.json")
AUDIT_DIR = Path("reports/governance/track_audits")
OUT_JSON = Path("reports/governance/track_coherence.json")
OUT_MD = Path("reports/governance/track_coherence.md")

# The 3-umbrella consolidation (a documented GROUPING, not a new owner). The
# keystone of umbrella A is the track every other member projects from.
UMBRELLAS: dict[str, dict[str, Any]] = {
    "runtime-truth-spine": {
        "name": "Runtime Truth Spine",
        "keystone": "runtime-truth-spine-adoption-2026-06",
        "members": [
            "runtime-truth-spine-adoption-2026-06",
            "runtime-truth-reconciliation-2026-06",
            "runtime-truth-nats-2026-06",
            "truth-graph-platform-2026-06",
        ],
    },
    "cybernetic-closure-routing": {
        "name": "Cybernetic Closure & Routing",
        "keystone": "loop-closure-2026-06",
        "members": ["loop-closure-2026-06", "provider-routing-consolidation-2026-06"],
    },
    "sovereign-holons": {
        "name": "Sovereign Holons",
        "keystone": "composer-holon-spine-longrun-2026-06",
        "members": ["composer-holon-spine-longrun-2026-06"],
    },
}

# Worst -> best, for conservative consensus rollups.
OPINION_ORDER = ["ADVERSE", "DISCLAIMER", "QUALIFIED", "CLEAN", "UNKNOWN"]
STATE_ORDER = ["IN_PROGRESS", "STALE", "OVERSTATED", "CLOSE_READY", "UNKNOWN"]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _load_checker():
    mod_path = Path(__file__).resolve().parent / "check_track_status.py"
    spec = importlib.util.spec_from_file_location("check_track_status", mod_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("check_track_status", mod)
    spec.loader.exec_module(mod)
    return mod


def _days_since(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        return (date.today() - datetime.strptime(date_str, "%Y-%m-%d").date()).days
    except (TypeError, ValueError):
        return None


def audit_consensus() -> dict[str, dict[str, Any]]:
    """Aggregate every *.audit.json: conservative opinion + claim-holds vote."""
    out: dict[str, dict[str, list[Any]]] = {}
    for p in sorted(AUDIT_DIR.glob("*.audit.json")):
        doc = _load_json(p)
        for tid, rec in (doc.get("tracks") or {}).items():
            if not isinstance(rec, dict):
                continue
            slot = out.setdefault(tid, {"opinions": [], "holds": []})
            slot["opinions"].append(str(rec.get("audit_opinion", "UNKNOWN")).upper())
            slot["holds"].append(bool(rec.get("completion_claim_holds")))
    consensus: dict[str, dict[str, Any]] = {}
    for tid, slot in out.items():
        ops = slot["opinions"]
        # Plurality; ties broken to the more conservative (worse) opinion.
        best = min(  # min index in OPINION_ORDER among the most frequent
            set(ops),
            key=lambda o: (-ops.count(o), OPINION_ORDER.index(o)
                           if o in OPINION_ORDER else 99))
        holds = slot["holds"]
        consensus[tid] = {
            "opinion": best,
            "runs": len(ops),
            "claim_holds": sum(holds) > len(holds) / 2,
            "holds_votes": f"{sum(holds)}/{len(holds)}",
            "opinion_spread": sorted(set(ops)),
        }
    return consensus


def build(checker) -> dict[str, Any]:
    raw = checker.load_active_track(ACTIVE_TRACK_PATH)
    portfolio = checker.normalize_portfolio(raw)
    active = [t for t in portfolio["active_tracks"] if checker._is_active(t)]
    spine_ids = [o.get("id") for o in portfolio["spine_objectives"] if o.get("id")]

    evidence = {t.get("id"): t for t in _load_json(EVIDENCE_JSON).get("active_tracks", [])}
    health = {t.get("id"): t for t in _load_json(HEALTH_JSON).get("tracks", [])}
    lint = _load_json(LINT_JSON).get("per_track", {})
    audits = audit_consensus()

    umbrella_of = {m: uid for uid, u in UMBRELLAS.items() for m in u["members"]}

    rows: dict[str, dict[str, Any]] = {}
    for t in active:
        tid = str(t.get("id"))
        ev = evidence.get(tid, {})
        cp = ev.get("completion_progress", {}) or {}
        passed, total = int(cp.get("passed", 0)), int(cp.get("total", 0))
        file_ship = bool(ev.get("shippable"))
        h = health.get(tid, {})
        attested = bool(h.get("attested_shippable"))
        a = audits.get(tid, {})
        high_smells = int((lint.get(tid) or {}).get("high", 0))
        age = _days_since(t.get("verified_at"))
        ttl = int(t.get("ttl_days", 14))
        stale = age is not None and age > ttl
        blockers = sum(1 for n in (t.get("next_items") or [])
                       if isinstance(n, dict) and n.get("blocker"))

        if attested and a.get("claim_holds", False) and high_smells == 0:
            state = "CLOSE_READY"
        elif file_ship and not attested:
            state = "OVERSTATED"
        elif stale:
            state = "STALE"
        else:
            state = "IN_PROGRESS"

        rows[tid] = {
            "id": tid,
            "umbrella": umbrella_of.get(tid),
            "serves": t.get("serves"),
            "owner": t.get("owner"),
            "coherence_state": state,
            "presence": f"{passed}/{total}",
            "file_shippable": file_ship,
            "quality_grade": h.get("grade"),
            "quality_score": h.get("score"),
            "attested_shippable": attested,
            "audit_opinion": a.get("opinion", "UNKNOWN"),
            "claim_holds": a.get("claim_holds"),
            "holds_votes": a.get("holds_votes"),
            "opinion_spread": a.get("opinion_spread", []),
            "high_smells": high_smells,
            "verified_age_days": age,
            "ttl_days": ttl,
            "stale": stale,
            "open_blockers": blockers,
            "depends_on": t.get("depends_on") or [],
        }

    # Umbrella rollups — a parent is only as coherent as its weakest member.
    umbrellas = []
    for uid, u in UMBRELLAS.items():
        members = [rows[m] for m in u["members"] if m in rows]
        if not members:
            continue
        worst = min((m["coherence_state"] for m in members),
                    key=lambda s: STATE_ORDER.index(s) if s in STATE_ORDER else 99)
        umbrellas.append({
            "id": uid, "name": u["name"], "keystone": u["keystone"],
            "members": [m["id"] for m in members],
            "rollup_state": worst,
            "close_ready": sorted(m["id"] for m in members
                                  if m["coherence_state"] == "CLOSE_READY"),
            "blocked_on": sorted(m["id"] for m in members
                                 if m["coherence_state"] in ("OVERSTATED", "IN_PROGRESS", "STALE")),
        })

    served = {r["serves"] for r in rows.values() if r["serves"]}
    coverage = {oid: (oid in served) for oid in spine_ids}

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "doctrine": "read model: projects from owners; owns no truth",
        "portfolio": {
            "active": len(rows),
            "close_ready": sorted(r["id"] for r in rows.values()
                                  if r["coherence_state"] == "CLOSE_READY"),
            "overstated": sorted(r["id"] for r in rows.values()
                                 if r["coherence_state"] == "OVERSTATED"),
            "objective_coverage": coverage,
            "uncovered_objectives": [o for o, c in coverage.items() if not c],
        },
        "umbrellas": umbrellas,
        "tracks": list(rows.values()),
    }


def emit(data: dict[str, Any]) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    p = data["portfolio"]
    md = ["# Track coherence — unified projection",
          "",
          f"Generated: {data['generated_at']}",
          "",
          "One read-model joining presence grade, Opus-4.8 quorum quality + "
          "attestation, 3-run audit consensus, criterion smells, and spine "
          "coverage. Projects from owners; owns no truth.",
          "",
          f"- **Close-ready:** {p['close_ready'] or '(none)'}",
          f"- **Overstated:** {p['overstated'] or '(none)'}",
          f"- **Uncovered spine objectives:** {p['uncovered_objectives'] or '(none)'}",
          ""]
    md.append("## Umbrellas")
    md.append("")
    md.append("| Umbrella | rollup | keystone | close-ready | blocked-on |")
    md.append("|---|---|---|---|---|")
    for u in data["umbrellas"]:
        md.append(f"| {u['name']} | **{u['rollup_state']}** | `{u['keystone']}` | "
                  f"{u['close_ready'] or '—'} | {u['blocked_on'] or '—'} |")
    md.append("")
    md.append("## Tracks")
    md.append("")
    md.append("| Track | state | presence | quality | attested | audit | holds | smells | stale |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for t in data["tracks"]:
        md.append(
            f"| `{t['id']}` | **{t['coherence_state']}** | {t['presence']} | "
            f"{t['quality_grade']} ({t['quality_score']}) | "
            f"{'✅' if t['attested_shippable'] else '—'} | {t['audit_opinion']} | "
            f"{t['holds_votes']} | {t['high_smells']} | "
            f"{'⚠️' if t['stale'] else '—'} |")
    md.append("")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    if not ACTIVE_TRACK_PATH.exists():
        print(f"ERROR: {ACTIVE_TRACK_PATH} not found", file=sys.stderr)
        return 2
    data = build(_load_checker())
    emit(data)
    if args.json:
        print(json.dumps(data, indent=2))
        return 0
    p = data["portfolio"]
    for t in data["tracks"]:
        print(f"{t['coherence_state']:12} {t['id']:42} "
              f"presence={t['presence']:>5} quality={t['quality_grade']} "
              f"audit={t['audit_opinion']} holds={t['holds_votes']} "
              f"smells={t['high_smells']}")
    print(f"\nclose_ready={p['close_ready']}  overstated={p['overstated']}  "
          f"uncovered={p['uncovered_objectives']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="print the full projection as JSON")
    return run(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main())
