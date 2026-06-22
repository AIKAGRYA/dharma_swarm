#!/usr/bin/env python3
"""track_health_grade.py — quality-aggregated, sign-off-gated track grading.

WHY THIS EXISTS
---------------
`check_track_status.py` grades a track by counting `file_exists` /
`file_contains` predicates. That is a PRESENCE check: a track flips
"SHIPPABLE" when a file contains a string, not when the capability runs
live. Presence is gameable and routinely OVERSTATES done-ness (a file-green
track whose real next_items are runtime witnesses that no string match can
see).

This module adds the missing QUALITY layer on top — without becoming a new
authority. It is a read-model: it projects two existing owners and never
mutates a track's truth.

  owner 1: reports/governance/active_track_evidence.json  (the file-grade,
           emitted by check_track_status.py — the deterministic presence score)
  owner 2: reports/governance/track_signoffs/*.signoff.json  (independent
           grader attestations — the quality score)

  Doctrine line (same as the reconciliation lane's):
    Read models project truth from owners; they do not become authority.

THE RUBRIC — 5 axes, each 0..4 (0 absent, 1 scaffold, 2 partial, 3 solid,
4 world-class):
  wired       on the live runtime/dispatch path, vs a side artifact
  proven      tests exist AND pass AND are non-proxy (witnessed, not a string)
  live        ran on real data recently / freshly verified
  world_class SOTA design vs scaffolding
  balanced    moves an UNDER-served spine objective vs piling on a saturated one

THE SIGN-OFF QUORUM (the "robust" part the operator asked for) — a track's
quality grade is only HONORED when it carries decorrelated, independent
attestations, mirroring the Transcendence Principle (diverse competent
graders + quality aggregation) and the loop-closure One-Wire quorum:

  MIN_SIGNOFFS distinct graders AND MIN_FAMILIES distinct model families.

Axes are aggregated by MEDIAN across sign-offs (robust to one outlier
grader), never by a single voice. A track is attested-SHIPPABLE only when
quorum holds AND median(wired) >= 3 AND median(proven) >= 3 AND a majority
of graders return verdict SHIPPABLE. Dissent is reported, not hidden — a
decorrelated minority opinion is signal, not noise.

This script is stdlib-only and READ-ONLY (advisory by default). It does not
gate merges unless invoked with --enforce; the deterministic presence gate
remains check_track_status.py.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

EVIDENCE_JSON = Path("reports/governance/active_track_evidence.json")
SIGNOFF_DIR = Path("reports/governance/track_signoffs")
OUT_JSON = Path("reports/governance/track_health.json")
OUT_MD = Path("reports/governance/track_health.md")

SIGNOFF_SCHEMA = "dharma_track_signoff.v1"
AXES = ("wired", "proven", "live", "world_class", "balanced")
# Weights sum to 1.0 — wiring + proof dominate; world-class/balance are the
# "is it bleeding-edge and does it serve the whole system" tax.
AXIS_WEIGHTS = {
    "wired": 0.30,
    "proven": 0.30,
    "live": 0.15,
    "world_class": 0.15,
    "balanced": 0.10,
}
VERDICTS = ("SHIPPABLE", "IN_PROGRESS", "OVERSTATED", "BLOCKED")

# Quorum thresholds — the decorrelation discipline.
MIN_SIGNOFFS = 3          # at least 3 independent graders
MIN_FAMILIES = 2          # spanning at least 2 distinct model families
SHIPPABLE_WIRED_FLOOR = 3
SHIPPABLE_PROVEN_FLOOR = 3


@dataclass
class TrackHealth:
    id: str
    file_passed: int = 0
    file_total: int = 0
    file_shippable: bool = False
    serves: str | None = None
    signoff_count: int = 0
    families: list[str] = field(default_factory=list)
    quorum_met: bool = False
    median_axes: dict[str, float] = field(default_factory=dict)
    score: float | None = None          # 0..100, None when ungraded
    grade: str = "UNGRADED"             # A..F or UNGRADED
    consensus_verdict: str = "UNGRADED"
    dissent: list[str] = field(default_factory=list)
    attested_shippable: bool = False
    notes: list[str] = field(default_factory=list)


def _letter(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def load_file_grades(path: Path) -> dict[str, dict[str, Any]]:
    """Project the deterministic presence grade per track id from the
    check_track_status.py evidence JSON (the file-grade owner)."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for tr in data.get("active_tracks", []) or []:
        cp = tr.get("completion_progress", {}) or {}
        out[tr.get("id")] = {
            "passed": int(cp.get("passed", 0)),
            "total": int(cp.get("total", 0)),
            "shippable": bool(tr.get("shippable")),
            "serves": tr.get("serves"),
        }
    return out


def load_signoffs(directory: Path) -> list[dict[str, Any]]:
    """Read every *.signoff.json attestation. Malformed receipts are skipped
    with a stderr note — a bad receipt must never crash the grader."""
    receipts: list[dict[str, Any]] = []
    if not directory.exists():
        return receipts
    for p in sorted(directory.glob("*.signoff.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARN: skipping malformed sign-off {p}: {exc}", file=sys.stderr)
            continue
        if doc.get("schema") != SIGNOFF_SCHEMA:
            print(f"WARN: {p} is not {SIGNOFF_SCHEMA}, skipping", file=sys.stderr)
            continue
        doc["_source"] = str(p)
        receipts.append(doc)
    return receipts


def _clamp_axis(v: Any) -> int | None:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return max(0, min(4, n))


def grade_track(tid: str, file_grade: dict[str, Any],
                receipts: list[dict[str, Any]]) -> TrackHealth:
    th = TrackHealth(
        id=tid,
        file_passed=file_grade.get("passed", 0),
        file_total=file_grade.get("total", 0),
        file_shippable=file_grade.get("shippable", False),
        serves=file_grade.get("serves"),
    )

    # Collect this track's attestations across all graders.
    per_grader: list[tuple[str, str, dict[str, int], str]] = []
    for r in receipts:
        tr = (r.get("tracks") or {}).get(tid)
        if not isinstance(tr, dict):
            continue
        axes_raw = tr.get("axes") or {}
        axes = {a: _clamp_axis(axes_raw.get(a)) for a in AXES}
        if any(v is None for v in axes.values()):
            th.notes.append(f"grader {r.get('grader','?')} gave incomplete axes; ignored")
            continue
        grader = str(r.get("grader") or r.get("_source"))
        family = str(r.get("model_family") or "unknown")
        verdict = str(tr.get("verdict") or "").upper()
        if verdict not in VERDICTS:
            verdict = "IN_PROGRESS"
        per_grader.append((grader, family, axes, verdict))  # type: ignore[arg-type]

    th.signoff_count = len(per_grader)
    th.families = sorted({fam for _, fam, _, _ in per_grader})
    th.quorum_met = (th.signoff_count >= MIN_SIGNOFFS
                     and len(th.families) >= MIN_FAMILIES)

    if not per_grader:
        th.notes.append("no sign-offs — quality grade withheld (file-grade only)")
        return th

    # Quality aggregation: MEDIAN per axis (robust to a single outlier grader).
    th.median_axes = {
        a: float(statistics.median([axes[a] for _, _, axes, _ in per_grader]))
        for a in AXES
    }
    th.score = round(
        sum(AXIS_WEIGHTS[a] * (th.median_axes[a] / 4.0) for a in AXES) * 100, 1)

    # Consensus verdict = plurality; ties broken toward the more conservative
    # verdict (BLOCKED > OVERSTATED > IN_PROGRESS > SHIPPABLE).
    order = {"BLOCKED": 0, "OVERSTATED": 1, "IN_PROGRESS": 2, "SHIPPABLE": 3}
    tally: dict[str, int] = {}
    for _, _, _, v in per_grader:
        tally[v] = tally.get(v, 0) + 1
    best = max(tally.items(), key=lambda kv: (kv[1], -order.get(kv[0], 9)))
    th.consensus_verdict = best[0]
    th.dissent = sorted(
        f"{g}:{v}" for g, _, _, v in per_grader if v != th.consensus_verdict)

    if th.quorum_met:
        th.grade = _letter(th.score)
        majority_shippable = tally.get("SHIPPABLE", 0) > (len(per_grader) / 2)
        th.attested_shippable = (
            majority_shippable
            and th.median_axes["wired"] >= SHIPPABLE_WIRED_FLOOR
            and th.median_axes["proven"] >= SHIPPABLE_PROVEN_FLOOR
        )
        if th.file_shippable and not th.attested_shippable:
            th.notes.append(
                "file-grade says SHIPPABLE but quality quorum does NOT attest it "
                "(OVERSTATED): presence passed, capability not proven live")
    else:
        th.grade = f"PROVISIONAL-{_letter(th.score)}"
        th.notes.append(
            f"below sign-off quorum ({th.signoff_count}/{MIN_SIGNOFFS} graders, "
            f"{len(th.families)}/{MIN_FAMILIES} families) — grade is provisional")
    return th


def portfolio_grade(tracks: list[TrackHealth],
                    served_objectives: set[str],
                    total_objectives: int) -> dict[str, Any]:
    """A portfolio is more than the mean of its tracks. Concentration on one
    spine objective while others sit uncovered is itself a health defect — so
    we cap the portfolio grade by coverage, echoing the spine-coverage WARN in
    check_track_status.py but turning it into a number."""
    graded = [t for t in tracks if t.score is not None]
    mean = round(statistics.mean([t.score for t in graded]), 1) if graded else 0.0
    coverage = (len(served_objectives) / total_objectives) if total_objectives else 1.0
    # Coverage cap: a monothematic portfolio (1 of N objectives) cannot exceed
    # a B no matter how strong each track is — value must spread across the spine.
    cap = 100.0 if coverage >= 0.99 else (89.9 if coverage >= 0.5 else 84.9)
    capped = min(mean, cap)
    return {
        "track_mean": mean,
        "objective_coverage": round(coverage, 2),
        "coverage_cap": cap,
        "portfolio_score": capped,
        "portfolio_grade": _letter(capped),
        "attested_shippable": sorted(t.id for t in tracks if t.attested_shippable),
        "overstated": sorted(
            t.id for t in tracks
            if t.file_shippable and t.quorum_met and not t.attested_shippable),
    }


def emit(tracks: list[TrackHealth], portfolio: dict[str, Any],
         receipts: list[dict[str, Any]]) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "rubric": {"axes": list(AXES), "weights": AXIS_WEIGHTS,
                   "min_signoffs": MIN_SIGNOFFS, "min_families": MIN_FAMILIES},
        "graders": sorted({r.get("grader", r.get("_source", "?")) for r in receipts}),
        "portfolio": portfolio,
        "tracks": [
            {
                "id": t.id,
                "file_grade": f"{t.file_passed}/{t.file_total}",
                "file_shippable": t.file_shippable,
                "serves": t.serves,
                "signoff_count": t.signoff_count,
                "families": t.families,
                "quorum_met": t.quorum_met,
                "median_axes": t.median_axes,
                "score": t.score,
                "grade": t.grade,
                "consensus_verdict": t.consensus_verdict,
                "dissent": t.dissent,
                "attested_shippable": t.attested_shippable,
                "notes": t.notes,
            }
            for t in tracks
        ],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    md: list[str] = [
        "# Track Health — quality-aggregated, sign-off-gated grade",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "Projects two owners: `active_track_evidence.json` (file/presence grade) "
        "and `track_signoffs/*.signoff.json` (independent grader attestations). "
        "Read-only — it grades, it does not own track truth.",
        "",
        f"**Sign-off quorum:** {MIN_SIGNOFFS} independent graders across "
        f"{MIN_FAMILIES}+ model families. Axes aggregated by median; "
        "attested-SHIPPABLE requires median wired>=3 AND proven>=3 AND a "
        "grader majority verdict of SHIPPABLE.",
        "",
        f"**Graders this run:** {', '.join(payload['graders']) or '(none)'}",
        "",
        "## Portfolio",
        "",
        f"- Track-mean score: **{portfolio['track_mean']}** · "
        f"objective coverage: **{portfolio['objective_coverage']}** "
        f"(cap {portfolio['coverage_cap']})",
        f"- **Portfolio grade: {portfolio['portfolio_grade']} "
        f"({portfolio['portfolio_score']})**",
        f"- Attested-SHIPPABLE: {portfolio['attested_shippable'] or '(none)'}",
        f"- OVERSTATED (file-green, quorum withholds): "
        f"{portfolio['overstated'] or '(none)'}",
        "",
        "## Tracks",
        "",
        "| Track | File | Sign-offs | Score | Grade | Consensus | Attested? |",
        "|---|---|---|---|---|---|---|",
    ]
    for t in tracks:
        fams = f"{t.signoff_count} ({'/'.join(t.families) or '-'})"
        score = "—" if t.score is None else f"{t.score}"
        att = "✅" if t.attested_shippable else ("⚠️ overstated"
              if t.file_shippable and t.quorum_met else "—")
        md.append(
            f"| `{t.id}` | {t.file_passed}/{t.file_total}"
            f"{' ✓' if t.file_shippable else ''} | {fams} | {score} | "
            f"{t.grade} | {t.consensus_verdict} | {att} |")
    md.append("")
    for t in tracks:
        md.append(f"### `{t.id}` — {t.grade}")
        if t.median_axes:
            axisline = " · ".join(f"{a}={t.median_axes[a]:g}" for a in AXES)
            md.append(f"- median axes: {axisline}")
        md.append(f"- consensus verdict: **{t.consensus_verdict}**"
                  + (f" · dissent: {t.dissent}" if t.dissent else ""))
        for n in t.notes:
            md.append(f"- note: {n}")
        md.append("")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    file_grades = load_file_grades(EVIDENCE_JSON)
    if not file_grades:
        print(f"ERROR: {EVIDENCE_JSON} missing or empty — run "
              "check_track_status.py first.", file=sys.stderr)
        return 2
    receipts = load_signoffs(SIGNOFF_DIR)

    tracks = [grade_track(tid, fg, receipts) for tid, fg in file_grades.items()]
    served = {t.serves for t in tracks if t.serves}
    # Total spine objectives is read from the evidence JSON when present.
    try:
        ev = json.loads(EVIDENCE_JSON.read_text(encoding="utf-8"))
        total_obj = len([o for o in ev.get("spine_objectives", []) if o.get("id")]) or 1
    except (json.JSONDecodeError, OSError):
        total_obj = 1
    portfolio = portfolio_grade(tracks, served, total_obj)

    emit(tracks, portfolio, receipts)

    for t in tracks:
        line = (f"{t.id}: file {t.file_passed}/{t.file_total} | "
                f"grade {t.grade} | {t.consensus_verdict} | "
                f"attested_shippable={t.attested_shippable}")
        print(line)
    print(f"PORTFOLIO: grade {portfolio['portfolio_grade']} "
          f"({portfolio['portfolio_score']}) | overstated={portfolio['overstated']}")

    if args.enforce:
        # In enforce mode, an OVERSTATED track (file-green but quorum withholds)
        # is a blocking finding — you may not close it on presence alone.
        if portfolio["overstated"]:
            print("ERROR: overstated tracks present — cannot close on file-grade "
                  f"alone: {portfolio['overstated']}", file=sys.stderr)
            return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--enforce", action="store_true",
                    help="Exit non-zero when a file-green track is not "
                         "quorum-attested (OVERSTATED). Advisory off by default.")
    return run(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main())
