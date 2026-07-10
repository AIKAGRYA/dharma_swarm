#!/usr/bin/env python3
"""Substrate audit — one door for the static-analysis toolbelt.

Runs ruff, vulture, radon, bandit, and grimp with pinned flags, prints a
count table, and ratchets against a committed baseline
(reports/governance/substrate_baseline.json).

Doctrine (matches slop_ratchet / hygiene lifecycle):
- default run is ADVISORY: prints counts + delta vs baseline, always exit 0;
- --strict exits 1 if any metric regressed above baseline (delta-ratchet);
- --write-baseline replaces the baseline with current counts;
- --tools ruff,vulture,... runs a subset (fast local loops, tests).

The baseline holds COUNTS only; full findings go to the detail report at
/tmp/dharma-substrate-audit.txt. Counts may only go down (or baseline is
consciously rewritten) — the same one-way door as every other ratchet here.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = REPO_ROOT / "reports" / "governance" / "substrate_baseline.json"
DETAIL_REPORT = Path("/tmp/dharma-substrate-audit.txt")
SCHEMA = "dharma_swarm.substrate_baseline.v1"

SRC = ["dharma_swarm", "scripts"]
PKG = "dharma_swarm"


def _run(cmd: list[str], timeout: int = 600) -> tuple[int, str, str]:
    """Return (exit, stdout, stderr). NEVER concatenate the streams before
    parsing: a stderr warning would corrupt JSON output (real CI failure,
    2026-07-10 — ruff emitted a warning locally absent, JSON became
    unparseable)."""
    try:
        proc = subprocess.run(
            cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return 127, "", f"tool not found: {cmd[0]} (run: make substrate-tools)"
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout: {' '.join(cmd)}"


def audit_ruff(detail: list[str]) -> dict[str, int]:
    code, out, err = _run(["ruff", "check", *SRC, "--output-format", "json"])
    if code == 127:
        detail.append(err)
        return {"ruff_unavailable": 1}
    try:
        findings = json.loads(out)
    except json.JSONDecodeError:
        detail.append(
            f"ruff: unparseable stdout (exit {code})\nstdout: {out[:1000]}\nstderr: {err[:1000]}"
        )
        return {"ruff_unparseable": 1}
    detail.append(f"== ruff ({len(findings)} findings)")
    detail.extend(
        f"  {f['filename']}:{f['location']['row']} {f['code']} {f['message']}"
        for f in findings[:400]
    )
    return {"ruff_total": len(findings)}


def audit_vulture(detail: list[str]) -> dict[str, int]:
    code, out, err = _run(["vulture", PKG, "--min-confidence", "90"])
    if code == 127:
        detail.append(err)
        return {"vulture_unavailable": 1}
    lines = [ln for ln in out.splitlines() if ": unused" in ln]
    detail.append(f"== vulture min-confidence 90 ({len(lines)} findings)")
    detail.extend(f"  {ln}" for ln in lines)
    return {"vulture_dead_90": len(lines)}


def audit_radon(detail: list[str]) -> dict[str, int]:
    code, out, err = _run(["radon", "cc", PKG, "-s", "-n", "E"])
    if code == 127:
        detail.append(err)
        return {"radon_unavailable": 1}
    blocks = [ln for ln in out.splitlines() if " - E (" in ln or " - F (" in ln]
    f_blocks = [ln for ln in blocks if " - F (" in ln]
    detail.append(f"== radon cc grade E or worse ({len(blocks)} blocks)")
    detail.extend(f"  {ln.strip()}" for ln in blocks)
    return {"radon_grade_e_plus": len(blocks), "radon_grade_f": len(f_blocks)}


def audit_bandit(detail: list[str]) -> dict[str, int]:
    code, out, err = _run(["bandit", "-r", PKG, "-q", "-f", "json"])
    if code == 127:
        detail.append(err)
        return {"bandit_unavailable": 1}
    try:
        data = json.loads(out[out.index("{"):])
    except (ValueError, json.JSONDecodeError):
        detail.append(f"bandit: unparseable stdout (exit {code}); stderr: {err[:500]}")
        return {"bandit_unparseable": 1}
    results = data.get("results", [])
    high = [r for r in results if r.get("issue_severity") == "HIGH"]
    medium = [r for r in results if r.get("issue_severity") == "MEDIUM"]
    detail.append(f"== bandit ({len(high)} high, {len(medium)} medium)")
    detail.extend(
        f"  {r['filename']}:{r['line_number']} [{r['test_id']}] {r['issue_text']}"
        for r in high + medium[:100]
    )
    return {"bandit_high": len(high), "bandit_medium": len(medium)}


def audit_grimp(detail: list[str]) -> dict[str, int]:
    """Mutual top-level import pairs — the executable form of axiom A7."""
    try:
        import itertools

        import grimp
    except ImportError:
        detail.append("grimp not importable (run: make substrate-tools)")
        return {"grimp_unavailable": 1}
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    graph = grimp.build_graph(PKG)
    tops = sorted({m for m in graph.modules if m.count(".") == 1})
    pairs = []
    for a, b in itertools.combinations(tops, 2):
        try:
            if graph.direct_import_exists(
                importer=a, imported=b, as_packages=True
            ) and graph.direct_import_exists(importer=b, imported=a, as_packages=True):
                pairs.append(f"{a.split('.')[1]} <-> {b.split('.')[1]}")
        except Exception:  # grimp raises on squashed/invalid subpackages
            continue
    detail.append(f"== grimp mutual top-level import pairs ({len(pairs)}) [axiom A7]")
    detail.extend(f"  {p}" for p in pairs)
    return {"grimp_mutual_pairs": len(pairs)}


AUDITS = {
    "ruff": audit_ruff,
    "vulture": audit_vulture,
    "radon": audit_radon,
    "bandit": audit_bandit,
    "grimp": audit_grimp,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true", help="exit 1 on ratchet regression")
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--tools", default=",".join(AUDITS), help="comma-separated subset")
    args = ap.parse_args()

    selected = [t.strip() for t in args.tools.split(",") if t.strip()]
    unknown = [t for t in selected if t not in AUDITS]
    if unknown:
        print(f"unknown tools: {unknown}; known: {sorted(AUDITS)}", file=sys.stderr)
        return 2

    detail: list[str] = []
    counts: dict[str, int] = {}
    for tool in selected:
        counts.update(AUDITS[tool](detail))

    DETAIL_REPORT.write_text("\n".join(detail) + "\n")

    baseline = {}
    if BASELINE.exists():
        try:
            baseline = json.loads(BASELINE.read_text()).get("counts", {})
        except json.JSONDecodeError:
            print("WARN: baseline unparseable — treating as absent", file=sys.stderr)

    regressions = []
    print(f"{'metric':30} {'now':>7} {'base':>7} {'delta':>7}")
    for key in sorted(counts):
        base = baseline.get(key)
        delta = "" if base is None else counts[key] - base
        print(f"{key:30} {counts[key]:>7} {base if base is not None else '—':>7} {delta:>7}")
        if base is not None and counts[key] > base:
            regressions.append(f"{key}: {base} -> {counts[key]}")
    print(f"detail: {DETAIL_REPORT}")

    if args.write_baseline:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema": SCHEMA, "tools": selected, "counts": counts}
        BASELINE.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(f"baseline written: {BASELINE.relative_to(REPO_ROOT)}")
        return 0

    if regressions:
        print("RATCHET REGRESSION:" if args.strict else "advisory regression:",
              "; ".join(regressions))
        return 1 if args.strict else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
