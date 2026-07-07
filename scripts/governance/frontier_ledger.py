#!/usr/bin/env python3
"""frontier_ledger.py — the Frontier Ledger: our measured number vs. the field's.

Fact-owner: docs/plans/HYPERBOLIC_CHAMBER_PHASE0_DOSSIER_2026-07-07.md §(c) and
docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md §3.4. This script
owns NO fact. It projects, per capability: our measured number (from existing
receipt owners — the inward-ascent baseline receipt and the trust-gate
scoreboard) against the field's published number (receipted comparators from
NORTH_STAR §10; anything without a receipt URL renders UNKNOWN, never a guess),
plus the door panel (trust gate C1–C5) and the chamber-drift slot.

Doctrine (same honesty contract as trust_gate_status.py and
inward_ascent_baseline.py): a capability that cannot be measured on this host
is UNKNOWN, never silently green; a field number without a receipt URL is
UNKNOWN_PENDING_INGEST, never remembered prose. The C2 commensurability rule
stands: internal lift numbers are never presented as benchmark-commensurable.

Outputs (the committed surface):
  - reports/governance/chamber/frontier_ledger_receipt.json  (digest-stamped)
  - reports/governance/chamber/FRONTIER_LEDGER.md            (the one page)

Replay contract (``--check``): the markdown page must re-render byte-for-byte
as a pure function of the committed receipt; the receipt's tamper seal
(`digest`, checker-compatible with check_track_status.py::_recompute_digest)
must recompute; and the pinned sha256 of the baseline-receipt input must still
match the committed baseline receipt (staleness is a failure, not a footnote).
A re-RENDER (no flag) refreshes from the live owners; --check never writes.

Exit code: 0 on render; --check exits 1 on any finding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "reports/governance/chamber"
RECEIPT_NAME = "frontier_ledger_receipt.json"
MARKDOWN_NAME = "FRONTIER_LEDGER.md"
BASELINE_PATH = REPO_ROOT / "reports/governance/inward_ascent/baseline_receipt.json"
TRUST_GATE_SCRIPT = REPO_ROOT / "scripts/governance/trust_gate_status.py"
SCHEMA = "dharma_swarm.frontier_ledger.v1"

# Volatile fields excluded from --check field-replay comparison (the tamper
# seal `digest` still covers them, mirroring check_track_status conventions).
_VOLATILE_KEYS = ("generated_at", "host", "digest")

# Field comparators: ONLY entries with a receipt URL may carry a number.
# NORTH_STAR §10 is the source; refreshing these is the ingest lane's job
# (chamber doctrine F5: the ledger exists to replace hand-curated memory).
FIELD_COMPARATORS: dict[str, dict[str, Any]] = {
    "coding_benchmark_self_improvement": {
        "value": 50.0,
        "unit": "% SWE-bench-verified (DGM final, self-improved 20->50)",
        "receipt": "https://arxiv.org/abs/2505.22954",
    },
}


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def stable_digest(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_baseline() -> tuple[dict[str, Any] | None, str | None]:
    """The committed inward-ascent baseline receipt is the 'ours' owner for
    every ratchet surface it measures. Absent -> every surface UNKNOWN."""
    digest = sha256_file(BASELINE_PATH)
    if digest is None:
        return None, None
    try:
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8")), digest
    except (OSError, json.JSONDecodeError):
        return None, digest


def _trust_gate_payload() -> dict[str, Any] | None:
    """Run the trust-gate owner script ONCE. Any failure -> None, and the
    callers render an UNKNOWN door / lift, never a fabricated one."""
    try:
        proc = subprocess.run(
            [sys.executable, str(TRUST_GATE_SCRIPT), "--json-only"],
            capture_output=True, text=True, timeout=180, cwd=REPO_ROOT,
        )
        return json.loads(proc.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def trust_gate_snapshot(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Reduce the trust-gate payload to the door panel."""
    if payload is None:
        return {"available": False, "gate_open": None, "conditions": []}
    conditions = [
        {"id": c.get("id"), "score": c.get("score"), "verdict": c.get("verdict")}
        for c in payload.get("conditions", [])
    ]
    return {
        "available": True,
        "gate_open": bool(payload.get("gate_open", False)),
        "owner": str(payload.get("fact_owner", "docs/vision_maps/NORTH_STAR.md §8")),
        "conditions": conditions,
    }


def _swarm_lift(payload: dict[str, Any] | None) -> tuple[float | None, str]:
    """C2's evidence names the last real lift measurement and its receipt.
    Parsed, not remembered; unparseable -> UNKNOWN with the gap named."""
    if payload is None:
        return None, "trust-gate owner unavailable on this host"
    for cond in payload.get("conditions", []):
        if cond.get("id") != "C2":
            continue
        for line in cond.get("evidence", []):
            m = re.search(r"latest measured lift = (-?\d+(?:\.\d+)?)\s*\((\S+?)\)", line)
            if m:
                return float(m.group(1)), m.group(2)
    return None, "no measured-lift line in C2 evidence"


def _baseline_surface(baseline: dict[str, Any] | None, sid: str) -> dict[str, Any]:
    for s in (baseline or {}).get("surfaces", []):
        if s.get("id") == sid:
            return {"value": s.get("value"), "unit": s.get("unit"),
                    "measured": bool(s.get("measured")),
                    "receipt": "reports/governance/inward_ascent/baseline_receipt.json"}
    return {"value": None, "unit": None, "measured": False,
            "receipt": "reports/governance/inward_ascent/baseline_receipt.json (surface absent)"}


def _field_for(capability: str) -> dict[str, Any]:
    row = FIELD_COMPARATORS.get(capability)
    if row is None:
        return {"value": None, "unit": None,
                "receipt": "UNKNOWN_PENDING_INGEST — the ingest lane supplies field numbers (F5)"}
    return dict(row)


def build_rows(baseline: dict[str, Any] | None,
               trust_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    lift, lift_receipt = _swarm_lift(trust_payload)
    rows: list[dict[str, Any]] = []

    def add(capability: str, ours: dict[str, Any], *, commensurable: bool,
            note: str) -> None:
        field = _field_for(capability)
        delta = None
        if commensurable and isinstance(ours.get("value"), (int, float)) \
                and isinstance(field.get("value"), (int, float)):
            delta = round(float(ours["value"]) - float(field["value"]), 6)
        rows.append({"capability": capability, "ours": ours, "field": field,
                     "delta": delta, "commensurable": commensurable, "note": note})

    add("coding_benchmark_self_improvement",
        {"value": None, "unit": "% SWE-bench-verified", "measured": False,
         "receipt": "never run — env 15 is operator-gated compute (decision queue)"},
        commensurable=True,
        note="The literal trust-gate C2 bar. Ours stays UNKNOWN until a real "
             "public-benchmark run under budget-parity controls exists.")
    add("swarm_lift_vs_best_single",
        {"value": lift, "unit": "lift vs own best seat", "measured": lift is not None,
         "receipt": lift_receipt},
        commensurable=False,
        note="Internal measurement owned by the RSI/arena lab; NOT "
             "benchmark-commensurable (trust_gate_status admissibility rule). "
             "Negative = the transcendence conditions currently fail in wiring.")
    add("ingest_metabolism",
        _baseline_surface(baseline, "ingest_volume"),
        commensurable=False,
        note="Bronze receipts landed under corroboration. Field column is N/A "
             "by construction (internal capacity surface).")
    add("forecast_brier",
        _baseline_surface(baseline, "forecast_brier"),
        commensurable=False,
        note="Time-lagged reality grading (gym G2); resolution from ingest "
             "ONLY (oracle rule, discipline 10). Ratchets DOWN.")
    add("memory_hit_rate",
        _baseline_surface(baseline, "memory_hit_rate"),
        commensurable=False,
        note="G3 arm-A held-out accuracy — the first measured C5 instrument.")
    add("gate_catch_rate",
        _baseline_surface(baseline, "gate_catch_rate"),
        commensurable=False,
        note="Deferred with the gate gym until the attack corpus is IMPORTED "
             "(class-2), never self-generated.")
    add("ontology_coverage",
        _baseline_surface(baseline, "ontology_coverage"),
        commensurable=False,
        note="ontology.db lives on the daemon host (BR-007); daemon-host "
             "baseline run is in the decision queue.")
    add("routing_regret",
        _baseline_surface(baseline, "routing_regret"),
        commensurable=False,
        note="G4 off-policy regret vs ~2k real delegation_runs; operator-gated "
             "on a sanitized runtime.db snapshot. Ratchets DOWN.")
    add("distilled_seat_cost_per_iteration",
        {"value": None, "unit": "USD / scored iteration", "measured": False,
         "receipt": "env 12 (trace distillation) not built — no cost ledger yet"},
        commensurable=False,
        note="The compute-ROI denominator (discipline 9). Every environment "
             "must declare cost-per-scored-iteration before its first "
             "evolution run; this row aggregates them.")
    return rows


def build_drift() -> dict[str, Any]:
    """Chamber-drift metric (discipline 11): gym-score trend vs time-lagged
    reality-graded trend. Two series, neither of which exists yet — the slot
    renders UNVALUED with its alert rule, so the instrument precedes the data."""
    return {
        "status": "UNVALUED",
        "gym_score_trend": None,
        "reality_graded_trend": None,
        "requires": "≥2 gym receipts on one environment AND ≥1 reality-graded "
                    "receipt (envs G2/G10 class) in the same window",
        "alert_rule": "gym trend rising while reality-graded trend is flat or "
                      "falling over a 14-day window ⇒ CHAMBER DRIFT alert on "
                      "this page (we are overfitting the chamber; the mirror "
                      "is reassembling)",
    }


def build_receipt_core() -> dict[str, Any]:
    baseline, baseline_sha = load_baseline()
    trust_payload = _trust_gate_payload()
    trust = trust_gate_snapshot(trust_payload)
    rows = build_rows(baseline, trust_payload)
    measured = sum(1 for r in rows if r["ours"].get("measured"))
    return {
        "schema": SCHEMA,
        "fact_owner": "docs/plans/HYPERBOLIC_CHAMBER_PHASE0_DOSSIER_2026-07-07.md §(c)",
        "authority": "projection_only",
        "capability_claim": "NONE. Every number here is either an internal "
                            "instrument reading or a receipted external "
                            "publication; nothing is a production capability "
                            "claim (chamber doctrine, arena non-goal 1).",
        "inputs": {
            "baseline_receipt": {
                "path": "reports/governance/inward_ascent/baseline_receipt.json",
                "sha256": baseline_sha,
                "present": baseline is not None,
            },
            "trust_gate": trust,
        },
        "rows": rows,
        "door": {
            "gate_open": trust.get("gate_open"),
            "conditions": trust.get("conditions", []),
            "review_cadence_days": 30,
            "next_review": "PENDING_OPERATOR (decision queue item 6)",
        },
        "chamber_drift": build_drift(),
        "summary": {"rows": len(rows), "measured": measured,
                    "unknown": len(rows) - measured},
    }


def _fmt(v: Any, unit: Any = None) -> str:
    if v is None:
        return "UNKNOWN"
    return f"{v} {unit}".strip() if unit else str(v)


def render_markdown(receipt: dict[str, Any]) -> str:
    door = receipt["door"]
    drift = receipt["chamber_drift"]
    s = receipt["summary"]
    gate = door.get("gate_open")
    door_line = ("**DOOR: OPEN**" if gate
                 else "**DOOR: CLOSED**" if gate is False
                 else "**DOOR: UNKNOWN** (trust gate unmeasurable this host)")
    lines = [
        "# FRONTIER LEDGER — the chamber's one page (read-only projection)",
        "",
        f"**Schema:** `{receipt['schema']}` · **Generated:** {receipt['generated_at']}",
        "**Replay:** `python3 scripts/governance/frontier_ledger.py --check` · "
        "**Refresh:** `python3 scripts/governance/frontier_ledger.py`",
        "",
        "> **NO CAPABILITY CLAIM.** " + receipt["capability_claim"],
        "",
        f"## The door — trust gate (owner: NORTH_STAR §8) — {door_line}",
        "",
        "| Cond | Verdict | Score |",
        "|---|---|---|",
    ]
    for c in door.get("conditions", []):
        lines.append(f"| {c['id']} | {c['verdict']} | {c['score']} |")
    if not door.get("conditions"):
        lines.append("| — | UNKNOWN | — |")
    lines += [
        "",
        f"30-day review cadence · next review: {door['next_review']}",
        "",
        "## Capabilities — our measured number vs the field's published number",
        "",
        "| Capability | Ours | Field | Δ | Commensurable | Receipts (ours · field) |",
        "|---|---|---|---|---|---|",
    ]
    for r in receipt["rows"]:
        ours, field = r["ours"], r["field"]
        lines.append(
            f"| {r['capability']} | {_fmt(ours.get('value'), ours.get('unit'))} "
            f"| {_fmt(field.get('value'), field.get('unit'))} "
            f"| {_fmt(r['delta'])} | {'yes' if r['commensurable'] else 'no'} "
            f"| {ours.get('receipt')} · {field.get('receipt')} |")
    lines += [
        "",
        "Notes per row live in the receipt (`rows[].note`).",
        "",
        f"## Chamber drift (discipline 11) — status: {drift['status']}",
        "",
        f"- requires: {drift['requires']}",
        f"- alert rule: {drift['alert_rule']}",
        "",
        f"**Honesty line:** {s['measured']}/{s['rows']} capabilities measured, "
        f"{s['unknown']}/{s['rows']} UNKNOWN. That IS the day-one frontier: "
        "this page exists to convert each UNKNOWN into a number, never to "
        "narrate around one.",
        "",
        f"*Inputs pinned: baseline receipt sha256 "
        f"`{(receipt['inputs']['baseline_receipt']['sha256'] or 'ABSENT')[:16]}…` · "
        "trust-gate snapshot recorded in-receipt.*",
        "",
    ]
    return "\n".join(lines) + "\n"


def write_surface(out_dir: Path) -> dict[str, Any]:
    receipt = build_receipt_core()
    receipt["generated_at"] = _utc_now()
    receipt["digest"] = stable_digest(
        {k: v for k, v in receipt.items() if k != "digest"})
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / RECEIPT_NAME).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / MARKDOWN_NAME).write_text(render_markdown(receipt), encoding="utf-8")
    return receipt


def check(out_dir: Path) -> list[str]:
    """Verify the committed surface: seal intact, inputs still pinned, page a
    pure render of the receipt. Empty list == verified."""
    findings: list[str] = []
    receipt_path = out_dir / RECEIPT_NAME
    md_path = out_dir / MARKDOWN_NAME
    if not receipt_path.exists():
        return [f"receipt missing: {receipt_path}"]
    try:
        committed = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [f"receipt is not valid JSON: {receipt_path}"]

    stored = str(committed.get("digest", ""))
    if stored != stable_digest({k: v for k, v in committed.items() if k != "digest"}):
        findings.append("receipt digest mismatch (tampered or hand-edited)")

    pinned = committed.get("inputs", {}).get("baseline_receipt", {})
    live_sha = sha256_file(BASELINE_PATH)
    if pinned.get("sha256") != live_sha:
        findings.append(
            "baseline-receipt input drifted since render "
            f"(pinned {str(pinned.get('sha256'))[:16]}… vs live "
            f"{str(live_sha)[:16]}…) — rerun scripts/governance/frontier_ledger.py")

    if not md_path.exists():
        findings.append(f"markdown surface missing: {md_path}")
    elif md_path.read_text(encoding="utf-8") != render_markdown(committed):
        findings.append("FRONTIER_LEDGER.md is not a pure render of the "
                        "committed receipt (hand-edited or stale)")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify the committed surface (write nothing)")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    if args.check:
        findings = check(args.out)
        if findings:
            print("frontier_ledger --check: FAIL")
            for f in findings:
                print(f"  - {f}")
            return 1
        print("frontier_ledger --check: OK — seal intact, inputs pinned, "
              "page renders purely from the receipt.")
        return 0

    receipt = write_surface(args.out)
    s = receipt["summary"]
    print(f"frontier_ledger: wrote {args.out / RECEIPT_NAME}")
    print(f"  rows={s['rows']} measured={s['measured']} unknown={s['unknown']} "
          f"gate_open={receipt['door']['gate_open']}")
    print(f"  digest={receipt['digest'][:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
