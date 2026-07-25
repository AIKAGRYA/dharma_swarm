#!/usr/bin/env python3
"""tam_ledger.py — Transdimensional Abundance Machine (TAM): Company-Builder Parity.

ONE plain-language, always-re-runnable instrument answering: "How close is
dharma_swarm to being a verifiably BETTER Polsia / cofounder.co — as a single
percentage and a per-capability board?" The machine's name carries the telos
(abundance across every dimension the organism serves); its single legible
output is deliberately plain: the **Company-Builder Parity %**.

NAMING (operator-resolved 2026-07-07): TAM here = Transdimensional Abundance
Machine, the instrument/organ. It does NOT overload TAM = Total Addressable
Market (foundations/FIVE_FOURTEEN_A.md:49, untouched) and does NOT write into
reports/tam/ (Darshan-owned). This machine's surface is reports/governance/tam/.

AUTHORITY: projection_only — it owns no fact. Afferent measurement only: it
reads competitor PUBLIC claims (each cell carries a source URL and a
verification label per the NORTH_STAR §5 source-pending rule) and our own
honest status owners (lane_F world triangulation, the venture-cell portfolio,
the swarm-genome organ-health table). Efferent-closed: no outreach, no
publishing, no benchmarking claims.

HONESTY RULES (the product vs Polsia's documented 4.4x claims gap):
  - only cells with a citation carry a status; an uncited competitor cell
    renders UNMEASURED, never a guess;
  - UNMEASURED rows score 0 and stay IN the denominator — not measuring a
    capability can never inflate the headline;
  - AHEAD requires a RUNS-grade organ of ours AND a cited structural
    exceed-vector; a competitor ABSENT cell requires a cited clean negative.

Usage:
    python3 scripts/governance/tam_ledger.py            # write the surface
    python3 scripts/governance/tam_ledger.py --check    # verify replay (CI)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.memory_kernel.write_receipts import (  # noqa: E402
    stable_digest,
    utc_now,
)

SCHEMA = "tam_ledger.v1"
HISTORY_SCHEMA = "tam_history.v1"
DEFAULT_OUT_DIR = ROOT / "reports" / "governance" / "tam"
RECEIPT_NAME = "tam_receipt.json"
MARKDOWN_NAME = "COMPANY_BUILDER_PARITY.md"
HISTORY_NAME = "tam_history.jsonl"
PORTFOLIO_PATH = ROOT / "docs" / "governance" / "VENTURE_CELL_PORTFOLIO.yaml"

# Volatile receipt fields excluded from replay comparison (never from digest).
_VOLATILE_KEYS = ("generated_at", "digest")

OURS_STATUSES = ("RUNS", "WIRED_BUT_DORMANT", "ASPIRATION", "ABSENT", "UNMEASURED")
COMP_STATUSES = ("SHIPPED", "CLAIMED", "ABSENT", "UNKNOWN")
VERIFICATIONS = ("vendor-claim", "third-party-report", "source-pending", "unverifiable")

BEHIND, AT_PARITY, AHEAD = "BEHIND", "AT_PARITY", "AHEAD"
NO_EQUIVALENT, UNMEASURED = "NO_EQUIVALENT", "UNMEASURED"
LANES = (BEHIND, AT_PARITY, AHEAD, NO_EQUIVALENT, UNMEASURED)
# NO_EQUIVALENT is excluded from the denominator (nothing to be at parity
# WITH) and is listed as the exceed-vector watch lane instead.
BUCKET_SCORES = {BEHIND: 0.0, AT_PARITY: 1.0, AHEAD: 1.5, UNMEASURED: 0.0}

def _load_sibling(name: str) -> Any:
    """Import a sibling governance script as a module (reuse, don't re-implement)."""
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    return mod


_TGS = _load_sibling("trust_gate_status")  # verdict_for + parse_cell_statuses
_AXES = _load_sibling("tam_axes")  # the frozen capability-axis rows (data only)


def validate_row(row: dict[str, Any]) -> None:
    """Fail loudly on any data shape that could game the headline."""
    if row["ours_status"] not in OURS_STATUSES:
        raise ValueError(f"{row['key']}: unknown ours_status {row['ours_status']!r}")
    if row["comp_status"] not in COMP_STATUSES:
        raise ValueError(f"{row['key']}: unknown comp_status {row['comp_status']!r}")
    if row["comp_sources"] and row["comp_verification"] not in VERIFICATIONS:
        raise ValueError(f"{row['key']}: unknown verification {row['comp_verification']!r}")
    if row["comp_status"] == "ABSENT" and not row["comp_sources"]:
        raise ValueError(
            f"{row['key']}: comp_status ABSENT needs a cited clean negative — "
            "an uncited ABSENT would shrink the denominator and inflate parity")
    if row["structural_exceed_cite"] and row["ours_status"] != "RUNS":
        raise ValueError(
            f"{row['key']}: structural exceed-vector claimed but our organ is "
            f"{row['ours_status']}, not RUNS — AHEAD must be earned, not narrated")


def parity_bucket(row: dict[str, Any]) -> str:
    """Pure lane assignment. Ordering is load-bearing: the honesty rules
    (uncited/unmeasured -> UNMEASURED) win over every flattering outcome."""
    if row["comp_status"] == "UNKNOWN" or not row["comp_sources"]:
        return UNMEASURED
    if row["ours_status"] == "UNMEASURED" or not row["ours_owner"]:
        return UNMEASURED
    if row["comp_status"] == "ABSENT":
        return NO_EQUIVALENT
    if row["ours_status"] == "RUNS" and row["structural_exceed_cite"]:
        return AHEAD
    if row["ours_status"] == "RUNS":
        return AT_PARITY
    return BEHIND


def compute_parity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Headline math. UNMEASURED stays in the denominator at score 0."""
    lane_counts = {lane: 0 for lane in LANES}
    numerator = 0.0
    denominator = 0
    for row in rows:
        bucket = row["bucket"]
        lane_counts[bucket] += 1
        if bucket == NO_EQUIVALENT:
            continue
        denominator += 1
        numerator += BUCKET_SCORES[bucket]
    pct = round(100.0 * numerator / denominator, 1) if denominator else 0.0
    return {
        "parity_pct": pct,
        "verdict": _TGS.verdict_for(pct / 100.0),
        "numerator": round(numerator, 2),
        "denominator": denominator,
        "lane_counts": lane_counts,
        "scoring": {
            "BEHIND": 0.0, "AT_PARITY": 1.0, "AHEAD": 1.5,
            "UNMEASURED": "0.0 and counted in the denominator (cannot inflate)",
            "NO_EQUIVALENT": "excluded from denominator; exceed-vector watch lane",
        },
    }


def build_rows() -> list[dict[str, Any]]:
    """The frozen capability axes (data owner: scripts/governance/tam_axes.py),
    validated and lane-assigned here so data edits cannot bypass the honesty rules."""
    rows = _AXES.axes()
    for row in rows:
        validate_row(row)
        row["bucket"] = parity_bucket(row)
        row["score"] = BUCKET_SCORES.get(row["bucket"])
    return rows


def build_report() -> dict[str, Any]:
    """Deterministically derive the receipt core (no timestamps, no digest)."""
    rows = build_rows()
    parity = compute_parity(rows)
    statuses = _TGS.parse_cell_statuses(PORTFOLIO_PATH)
    return {
        "schema": SCHEMA,
        "machine": "Transdimensional Abundance Machine (TAM)",
        "metric": "Company-Builder Parity %",
        "authority": "projection_only",
        "efferent_action": "none — afferent measurement only (no outreach, no publishing, no benchmark claims)",
        "baseline": _AXES.BASELINE,
        "parity_pct": parity["parity_pct"],
        "verdict": parity["verdict"],
        "parity_math": {k: parity[k] for k in ("numerator", "denominator", "scoring")},
        "lane_counts": parity["lane_counts"],
        "headline_differentiator": "honest_arr",
        "rows": rows,
        "portfolio_live_read": {
            "cells": len(statuses),
            "active_class": sorted(c for c, s in statuses.items() if s.startswith("ACTIVE")),
        },
        "naming": {
            "organ": "TAM = Transdimensional Abundance Machine (operator-resolved 2026-07-07)",
            "untouched": "TAM = Total Addressable Market (foundations/FIVE_FOURTEEN_A.md:49) "
                         "and the Darshan-owned reports/tam/ are deliberately not overloaded",
        },
    }


# ------------------------------------------------------------------- history
def read_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            rows.append(json.loads(ln))
    return rows


def append_history(path: Path, entry_core: dict[str, Any]) -> dict[str, Any]:
    """Append a digest-chained history row (prev_digest links the chain;
    digest covers every field except itself — check_track_status convention)."""
    rows = read_history(path)
    entry = dict(entry_core)
    entry["prev_digest"] = str(rows[-1]["digest"]) if rows else ""
    entry["digest"] = stable_digest({k: v for k, v in entry.items() if k != "digest"})
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def compute_velocity(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    """d(parity_pct)/dt from the last two history rows. None until 2 renders."""
    if len(history) < 2:
        return None
    a, b = history[-2], history[-1]
    d_pct = round(float(b["parity_pct"]) - float(a["parity_pct"]), 2)
    return {"from": a["generated_at"], "to": b["generated_at"],
            "d_parity_pct": d_pct,
            "direction": "closing" if d_pct > 0 else ("opening" if d_pct < 0 else "flat")}


# ------------------------------------------------------------------ markdown
_LANE_TITLES = {
    BEHIND: "Behind", AT_PARITY: "At parity", AHEAD: "Ahead",
    NO_EQUIVALENT: "No competitor equivalent (exceed-vector watch)",
    UNMEASURED: "Unmeasured",
}


def render_markdown(receipt: dict[str, Any], history: list[dict[str, Any]]) -> str:
    lanes = receipt["lane_counts"]
    math = receipt["parity_math"]
    vel = compute_velocity(history)
    vel_line = (
        f"{vel['d_parity_pct']:+.2f} pts since {vel['from']} — gap is **{vel['direction']}**"
        if vel else "unmeasured — needs a second render (this chain is the point: "
                    "the board must show d(parity)/dt over time)"
    )
    lines = [
        "# Company-Builder Parity — the TAM board",
        "",
        f"**Machine:** {receipt['machine']} · **Schema:** `{receipt['schema']}` · "
        f"**Generated:** {receipt['generated_at']}",
        f"**Replay:** `python3 scripts/governance/tam_ledger.py --check`",
        "",
        f"## Headline: Company-Builder Parity = **{receipt['parity_pct']}%** [{receipt['verdict']}]",
        "",
        f"Baseline: {receipt['baseline']}.",
        "",
        "0% = far below the Polsia/Cofounder capability baseline; 100% = at parity "
        "on everything they do; >100% = we exceed on axes they cannot match. "
        f"Math this render: {math['numerator']} / {math['denominator']} comparable "
        "capabilities (Behind=0, At parity=1, Ahead=1.5; Unmeasured=0 **and stays "
        "in the denominator** — not measuring can never inflate this number; "
        "no-equivalent rows are watched separately).",
        "",
        f"**Velocity:** {vel_line}",
        "",
        "## The board",
        "",
    ]
    by_lane: dict[str, list[dict[str, Any]]] = {lane: [] for lane in LANES}
    for row in receipt["rows"]:
        by_lane[row["bucket"]].append(row)
    for lane in LANES:
        lines.append(f"### {_LANE_TITLES[lane]} ({lanes[lane]})")
        lines.append("")
        for row in by_lane[lane]:
            star = " ⭐ headline differentiator" if row["key"] == receipt["headline_differentiator"] else ""
            lines.append(f"- **{row['capability']}**{star}")
            lines.append(f"  - ours: {row['ours_status']} — {row['ours_owner']}")
            if row["ours_note"]:
                lines.append(f"  - note: {row['ours_note']}")
            src = "; ".join(row["comp_sources"]) if row["comp_sources"] else "NO CITATION"
            lines.append(f"  - {row['comp_name']}: {row['comp_status']} "
                         f"[{row['comp_verification']}] — {row['comp_claim']} ({src})")
            if row["structural_exceed_cite"]:
                lines.append(f"  - exceed-vector: {row['structural_exceed_cite']}")
        lines.append("")
    live = receipt["portfolio_live_read"]
    lines += [
        "## Honesty & doctrine",
        "",
        f"- authority: `{receipt['authority']}` — this board owns no fact; it projects "
        "lane_F world triangulation, the venture-cell portfolio, and the genome "
        "organ-health table.",
        f"- efferent action: {receipt['efferent_action']}.",
        f"- portfolio live-read at render time: {live['cells']} cells declared; "
        f"ACTIVE-class: {live['active_class'] or 'none'}.",
        f"- naming: {receipt['naming']['organ']}; {receipt['naming']['untouched']}.",
        "- every competitor number carries a source URL and a verification label "
        "(NORTH_STAR §5 source-pending rule); anything unverifiable renders "
        "UNMEASURED with the gap named.",
        "",
    ]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------- write / check
def write_surface(out_dir: Path) -> dict[str, Any]:
    receipt = build_report()
    receipt["generated_at"] = utc_now()
    receipt["digest"] = stable_digest({k: v for k, v in receipt.items() if k != "digest"})
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / RECEIPT_NAME).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    append_history(out_dir / HISTORY_NAME, {
        "schema": HISTORY_SCHEMA,
        "generated_at": receipt["generated_at"],
        "parity_pct": receipt["parity_pct"],
        "verdict": receipt["verdict"],
        "lane_counts": receipt["lane_counts"],
        "receipt_digest": receipt["digest"],
    })
    history = read_history(out_dir / HISTORY_NAME)
    (out_dir / MARKDOWN_NAME).write_text(render_markdown(receipt, history), encoding="utf-8")
    return receipt


def check(out_dir: Path) -> list[str]:
    """Verify the committed surface replays exactly. Empty list == verified."""
    findings: list[str] = []
    receipt_path = out_dir / RECEIPT_NAME
    history_path = out_dir / HISTORY_NAME
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

    fresh_core = build_report()
    for key, fresh_value in fresh_core.items():
        if committed.get(key) != fresh_value:
            findings.append(
                f"receipt field {key!r} does not replay (stale surface — rerun "
                "scripts/governance/tam_ledger.py)")
    for key in committed:
        if key not in fresh_core and key not in _VOLATILE_KEYS:
            findings.append(f"receipt carries unknown field {key!r}")

    if not history_path.exists():
        findings.append(f"history chain missing: {history_path}")
        history = []
    else:
        history = read_history(history_path)
        prev = ""
        for i, row in enumerate(history):
            if row.get("digest") != stable_digest(
                    {k: v for k, v in row.items() if k != "digest"}):
                findings.append(f"history row {i} digest mismatch (tampered)")
            if row.get("prev_digest", "") != prev:
                findings.append(f"history chain broken at row {i}")
            prev = str(row.get("digest", ""))
        if history:
            tip = history[-1]
            if tip.get("receipt_digest") != committed.get("digest"):
                findings.append("history tip does not reference the committed receipt")
            if tip.get("parity_pct") != fresh_core["parity_pct"]:
                findings.append("history tip parity_pct does not replay")
        else:
            findings.append("history chain is empty")

    if not md_path.exists():
        findings.append(f"markdown board missing: {md_path}")
    elif md_path.read_text(encoding="utf-8") != render_markdown(committed, history):
        findings.append("markdown board is not a pure render of receipt + history")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify the committed surface replays exactly (write nothing)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR,
                        help="surface directory (default: reports/governance/tam)")
    args = parser.parse_args(argv)

    if args.check:
        findings = check(args.out)
        if findings:
            print("tam_ledger --check: FAIL")
            for f in findings:
                print(f"  - {f}")
            return 1
        print("tam_ledger --check: OK — surface replays exactly (projection_only).")
        return 0

    receipt = write_surface(args.out)
    print(f"tam_ledger: wrote {args.out / RECEIPT_NAME}")
    print(f"  Company-Builder Parity = {receipt['parity_pct']}% [{receipt['verdict']}]  "
          f"lanes={receipt['lane_counts']}")
    print(f"  headline differentiator: {receipt['headline_differentiator']} "
          "(receipted revenue — the axis incumbents structurally cannot publish)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
