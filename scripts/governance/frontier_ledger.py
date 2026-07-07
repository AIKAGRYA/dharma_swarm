#!/usr/bin/env python3
"""frontier_ledger.py — the Frontier Ledger: our measured number vs. the field's.

Fact-owner: docs/plans/HYPERBOLIC_CHAMBER_PHASE0_DOSSIER_2026-07-07.md §(c) and
docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md §3.4. This script
owns NO fact. Row construction lives in dharma_swarm/chamber/ledger_rows.py;
velocity (E6) lives in dharma_swarm/chamber/ledger_history.py. Every render
appends one row to a digest-chained history so d(delta)/dt is tamper-evident.

Honesty contract (same as trust_gate_status.py / inward_ascent_baseline.py):
UNKNOWN is rendered, never guessed; field numbers require receipt URLs; the
C2 commensurability rule stands.

Outputs (the committed surface):
  - reports/governance/chamber/frontier_ledger_receipt.json  (digest-stamped)
  - reports/governance/chamber/FRONTIER_LEDGER.md            (the one page)
  - reports/governance/chamber/ledger_history.jsonl          (E6 chain)

Replay contract (``--check``): tamper seal recomputes; pinned inputs
(baseline + transcendence receipts) unchanged; the page re-renders
byte-for-byte from the receipt; the history chain is intact with its tip
referencing this receipt; the velocity block replays from the chain; and the
DOOR has not drifted at verdict level (trust gate re-run live — C1 is
excluded from drift comparison because it measures working-tree cleanliness,
which is volatile by design; C2–C5 verdicts and gate_open must match).
A re-RENDER (no flag) refreshes from the live owners; --check never writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.chamber.chain import BrokenChainError  # noqa: E402
from dharma_swarm.chamber.ledger_history import (  # noqa: E402
    append_history,
    compute_velocity,
    read_chain,
)
from dharma_swarm.chamber.ledger_rows import (  # noqa: E402
    BASELINE_PATH,
    TRANSCENDENCE_PATH,
    build_rows,
    capability_summary,
    load_baseline,
    sha256_file,
    swarm_lift,
    trust_gate_payload,
    trust_gate_snapshot,
)

OUT_DIR = REPO_ROOT / "reports/governance/chamber"
RECEIPT_NAME = "frontier_ledger_receipt.json"
MARKDOWN_NAME = "FRONTIER_LEDGER.md"
HISTORY_NAME = "ledger_history.jsonl"
SCHEMA = "dharma_swarm.frontier_ledger.v1"
# C1 measures runtime-tree cleanliness — volatile across hosts/renders by
# design; door drift compares the stable, repo-content-derived conditions.
DRIFT_STABLE_CONDITIONS = ("C2", "C3", "C4", "C5")


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def stable_digest(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def build_receipt_core(generated_at: str, history_path: Path) -> dict[str, Any]:
    baseline, baseline_sha = load_baseline()
    payload = trust_gate_payload()
    trust = trust_gate_snapshot(payload)
    rows = build_rows(baseline, payload)
    measured = sum(1 for r in rows if r["ours"].get("measured"))
    velocity = compute_velocity(read_chain(history_path),
                                capability_summary(rows), generated_at)
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
            "transcendence_receipt": {
                "path": "reports/governance/chamber/transcendence_receipt.json",
                "sha256": sha256_file(TRANSCENDENCE_PATH),
                "present": TRANSCENDENCE_PATH.exists(),
            },
            "trust_gate": trust,
        },
        "rows": rows,
        "velocity": velocity,
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
    velocity = receipt.get("velocity", {})
    vcaps = velocity.get("capabilities", {})
    valued = [(c, v) for c, v in sorted(vcaps.items()) if v.get("status") == "VALUED"]
    lines += [
        "",
        "Notes per row live in the receipt (`rows[].note`).",
        "",
        f"## Velocity (E6) — d(delta)/dt · renders in history: "
        f"{velocity.get('renders_in_history', 0)} · valued: "
        f"{velocity.get('valued', 0)}/{len(vcaps)}",
        "",
    ]
    if valued:
        lines += ["| Capability | d(delta)/dt per day | Closing? | Window |",
                  "|---|---|---|---|"]
        lines += [f"| {c} | {v['d_delta_dt_per_day']} | "
                  f"{'yes' if v['closing'] else 'NO'} | {v['window'][0]} → "
                  f"{v['window'][1]} |" for c, v in valued]
    else:
        lines.append("All capabilities UNVALUED (requires ≥2 renders with a "
                     "numeric delta). The history chain has begun; velocity "
                     "values itself from the second render onward.")
    lines += [
        "",
        f"- loop latency vs field cadence: "
        f"{velocity.get('loop_latency', {}).get('status', 'UNVALUED')} — "
        f"{velocity.get('loop_latency', {}).get('requires', '')}",
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
    generated_at = _utc_now()
    receipt = build_receipt_core(generated_at, out_dir / HISTORY_NAME)
    receipt["generated_at"] = generated_at
    receipt["digest"] = stable_digest(
        {k: v for k, v in receipt.items() if k != "digest"})
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / RECEIPT_NAME).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / MARKDOWN_NAME).write_text(render_markdown(receipt), encoding="utf-8")
    append_history(out_dir / HISTORY_NAME, generated_at=generated_at,
                   receipt_digest=receipt["digest"],
                   capabilities=capability_summary(receipt["rows"]))
    return receipt


def _transcendence_check() -> list[str]:
    """Replay the transcendence receipt via its own instrument. Imported by
    file path (scripts/governance is not a package); any import/execution
    failure is itself a finding, never a silent pass."""
    import importlib.util
    path = REPO_ROOT / "scripts/governance/transcendence_ledger.py"
    try:
        spec = importlib.util.spec_from_file_location("transcendence_ledger", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.check(mod.RECEIPT_PATH)
    except Exception as exc:  # noqa: BLE001 — surfaced as a finding, not swallowed
        return [f"could not replay transcendence instrument: {type(exc).__name__}: {exc}"]


def _door_drift(committed: dict[str, Any]) -> list[str]:
    """Codex review (PR #830): --check must not bless a stale door. Re-run
    the trust gate and compare stable verdicts + gate_open + measured lift."""
    payload = trust_gate_payload()
    fresh = trust_gate_snapshot(payload)
    if not fresh.get("available"):
        return ["trust gate unmeasurable on this host — door drift UNKNOWN "
                "(not blessing staleness silently)"]
    findings: list[str] = []
    door = committed.get("door", {})
    fresh_v = {c["id"]: c["verdict"] for c in fresh["conditions"]
               if c["id"] in DRIFT_STABLE_CONDITIONS}
    committed_v = {c.get("id"): c.get("verdict")
                   for c in door.get("conditions", [])
                   if c.get("id") in DRIFT_STABLE_CONDITIONS}
    if fresh.get("gate_open") != door.get("gate_open") or fresh_v != committed_v:
        findings.append(f"trust-gate door drifted since render (now {fresh_v}, "
                        f"gate_open={fresh.get('gate_open')}) — rerun "
                        "scripts/governance/frontier_ledger.py")
    lift, _ = swarm_lift(payload)
    committed_lift = next(
        (r["ours"].get("value") for r in committed.get("rows", [])
         if r.get("capability") == "swarm_lift_vs_best_single"), None)
    if lift != committed_lift:
        findings.append("measured swarm lift drifted since render — rerun "
                        "scripts/governance/frontier_ledger.py")
    return findings


def check(out_dir: Path) -> list[str]:
    """Verify the committed surface: seal intact, inputs pinned, page a pure
    render, history chain + velocity replay, door not stale."""
    receipt_path = out_dir / RECEIPT_NAME
    md_path = out_dir / MARKDOWN_NAME
    if not receipt_path.exists():
        return [f"receipt missing: {receipt_path}"]
    try:
        committed = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [f"receipt is not valid JSON: {receipt_path}"]

    findings: list[str] = []
    stored = str(committed.get("digest", ""))
    if stored != stable_digest({k: v for k, v in committed.items() if k != "digest"}):
        findings.append("receipt digest mismatch (tampered or hand-edited)")

    for key, path in (("baseline_receipt", BASELINE_PATH),
                      ("transcendence_receipt", TRANSCENDENCE_PATH)):
        pinned = committed.get("inputs", {}).get(key, {})
        if pinned.get("sha256") != sha256_file(path):
            findings.append(f"{key} input drifted since render — rerun "
                            "scripts/governance/frontier_ledger.py")

    # A file-sha pin only proves the transcendence receipt is unchanged — not
    # that it honestly replays from its corpus. Chain the anchor: run the
    # transcendence instrument's own --check so a stale/fabricated receipt
    # fails frontier --check too (review R2-4), not just its own gate.
    if TRANSCENDENCE_PATH.exists():
        findings.extend(f"transcendence receipt: {f}"
                        for f in _transcendence_check())

    if not md_path.exists():
        findings.append(f"markdown surface missing: {md_path}")
    elif md_path.read_text(encoding="utf-8") != render_markdown(committed):
        findings.append("FRONTIER_LEDGER.md is not a pure render of the "
                        "committed receipt (hand-edited or stale)")

    # E6: history chain intact, tip matches this receipt, velocity replays.
    try:
        history = read_chain(out_dir / HISTORY_NAME)
    except BrokenChainError as exc:
        return findings + [f"ledger history chain broken: {exc}"]
    if not history:
        return findings + [f"ledger history missing/empty: {out_dir / HISTORY_NAME}"]
    tip = history[-1]
    if tip.get("receipt_digest") != committed.get("digest"):
        findings.append("history tip does not reference the committed receipt "
                        "(receipt and history must be re-rendered together)")
        return findings
    summary = capability_summary(committed.get("rows", []))
    if tip.get("capabilities") != summary:
        findings.append("history tip capabilities do not match the receipt rows")
    replayed = compute_velocity(history[:-1], summary,
                                str(committed.get("generated_at", "")))
    if committed.get("velocity") != replayed:
        findings.append("velocity block does not replay from the committed "
                        "history chain")

    findings.extend(_door_drift(committed))
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
              "page renders purely, history+velocity replay, door fresh.")
        return 0

    receipt = write_surface(args.out)
    s = receipt["summary"]
    print(f"frontier_ledger: wrote {args.out / RECEIPT_NAME}")
    print(f"  rows={s['rows']} measured={s['measured']} unknown={s['unknown']} "
          f"gate_open={receipt['door']['gate_open']} "
          f"velocity_valued={receipt['velocity']['valued']}")
    print(f"  digest={receipt['digest'][:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
