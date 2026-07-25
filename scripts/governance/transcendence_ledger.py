#!/usr/bin/env python3
"""transcendence_ledger.py — the Transcendence Principle as a measured number.

Fact-owner: docs/plans/HYPERBOLIC_CHAMBER_ELEVATION_SPEC_2026-07-07.md §E1.
This script owns NO fact. It reads a chamber_gym_trace.v1 corpus (per-task
per-seat correctness labels from a deterministic scorer) and renders the
three transcendence conditions as numbers, per taskpack:

  1. diversity of competence  -> per-seat error-rate spread + answer
     disagreement rate
  2. error decorrelation      -> pairwise Pearson correlation of seat error
     vectors (mean off-diagonal; lower is better, negative is gold)
  3. quality aggregation      -> E_ensemble vs the BEST single seat
     (lift_vs_best_seat > 0 is the C2-shaped question, internal-gym form)

Decomposition reported: E_diversity := E_mean - E_ensemble — the REALIZED
Krogh-Vedelsby form (the identity is exact for squared loss on averaged
regressors; for 0/1 labels we report the realized gain under the corpus's
recorded aggregation rule, and say so). Verified gap this instrument fills
(2026-07-07): no error-decomposition existed anywhere in the repo; the
nearest primitives (coordination/dpi.py etc.) are arena-owned proxies.
HARD BOUNDARY: consumes chamber traces only; never imports from
dharma_swarm.coordination or dharma_swarm.council.

Outputs:
  - reports/governance/chamber/transcendence_receipt.json (digest-stamped)
``--check`` recomputes everything from the pinned corpus and fails on any
drift (tamper seal + input sha + value replay). Exit 1 on findings.
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

from dharma_swarm.chamber.traces import read_corpus  # noqa: E402
DEFAULT_CORPUS = REPO_ROOT / "reports/governance/chamber/trace_corpus.jsonl"
RECEIPT_PATH = REPO_ROOT / "reports/governance/chamber/transcendence_receipt.json"
SCHEMA = "dharma_swarm.transcendence_decomposition.v1"


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def stable_digest(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pearson(xs: list[int], ys: list[int]) -> float | None:
    """Pearson r of two 0/1 error vectors; None when either is constant
    (correlation undefined — reported as such, never coerced to a number)."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return round(cov / (vx**0.5 * vy**0.5), 6)


def decompose(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One decomposition block per (taskpack_sha, env_id) group in the corpus.

    Requires per-seat ``correct`` labels on every row (the E5 schema carries
    them); a row without them is an error — silent partial data would make
    the decomposition a lie."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["taskpack_sha"], row["env_id"]), []).append(row)
    blocks: list[dict[str, Any]] = []
    for (pack_sha, env_id), grp in sorted(groups.items()):
        grp = sorted(grp, key=lambda r: r["task_id"])
        seats = sorted({a["seat_id"] for r in grp for a in r["answers"]})
        if not seats:
            raise ValueError(f"taskpack {pack_sha[:12]}: no seat answers")
        errors: dict[str, list[int]] = {s: [] for s in seats}
        answers: dict[str, list[str]] = {s: [] for s in seats}
        ens_errors: list[int] = []
        # Selection-aggregation sanity: under a rule that PICKS one seat's
        # answer (oracle_argmax), the ensemble can only be correct on a task
        # if some seat is. A corpus with the ensemble correct while every seat
        # is wrong is fabricated — void it rather than emit fake transcendence
        # (review R2-3). Enforced only for rules that declare selection.
        rules = {str(r.get("attributes", {}).get("aggregation_rule", "")) for r in grp}
        selection = all(rule.startswith("oracle_argmax") for rule in rules) and rules
        all_wrong_tasks = 0
        for r in grp:
            by_seat = {a["seat_id"]: a for a in r["answers"]}
            any_seat_correct = False
            for s in seats:
                a = by_seat.get(s)
                if a is None or a.get("correct") is None:
                    raise ValueError(
                        f"task {r['task_id']}: seat {s} lacks a correctness "
                        "label — decomposition refuses partial data")
                is_correct = bool(a["correct"])
                errors[s].append(0 if is_correct else 1)
                answers[s].append(str(a["answer"]))
                any_seat_correct = any_seat_correct or is_correct
            ens_correct = bool(r["correct"])
            ens_errors.append(0 if ens_correct else 1)
            if not any_seat_correct:
                all_wrong_tasks += 1
                if selection and ens_correct:
                    raise ValueError(
                        f"task {r['task_id']}: ensemble correct but every seat "
                        "wrong under a selection rule — impossible, corpus "
                        "labels are fabricated (E1 sanity invariant)")
        n = len(grp)
        seat_rates = {s: round(sum(errors[s]) / n, 6) for s in seats}
        e_mean = round(sum(seat_rates.values()) / len(seats), 6)
        e_ens = round(sum(ens_errors) / n, 6)
        e_best = min(seat_rates.values())
        pairs: dict[str, float | None] = {}
        defined: list[float] = []
        for i, s1 in enumerate(seats):
            for s2 in seats[i + 1:]:
                r_val = _pearson(errors[s1], errors[s2])
                pairs[f"{s1}|{s2}"] = r_val
                if r_val is not None:
                    defined.append(r_val)
        disagree = 0
        pair_count = 0
        for t in range(n):
            for i, s1 in enumerate(seats):
                for s2 in seats[i + 1:]:
                    pair_count += 1
                    disagree += answers[s1][t] != answers[s2][t]
        blocks.append({
            "taskpack_sha": pack_sha,
            "env_id": env_id,
            "n_tasks": n,
            "seats": seats,
            "seat_error_rates": seat_rates,
            "e_mean": e_mean,
            "e_ensemble": e_ens,
            "e_diversity_realized": round(e_mean - e_ens, 6),
            "e_best_seat": e_best,
            "lift_vs_best_seat": round(e_best - e_ens, 6),
            "disagreement_rate": round(disagree / pair_count, 6) if pair_count else None,
            "error_correlation": {
                "pairs": pairs,
                "mean_offdiag": round(sum(defined) / len(defined), 6) if defined else None,
                "undefined_pairs": sum(1 for v in pairs.values() if v is None),
            },
            "selection_aggregation": bool(selection),
            "all_seats_wrong_tasks": all_wrong_tasks,
        })
    return blocks


def build_receipt(corpus_path: Path) -> dict[str, Any]:
    rows = read_corpus(corpus_path)  # verifies every row digest
    try:
        rel = str(corpus_path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        rel = str(corpus_path)
    blocks = decompose(rows)
    return {
        "schema": SCHEMA,
        "fact_owner": "docs/plans/HYPERBOLIC_CHAMBER_ELEVATION_SPEC_2026-07-07.md §E1",
        "authority": "projection_only",
        "capability_claim": "NONE — internal-gym decomposition under the "
                            "corpus's recorded aggregation rule; never a "
                            "benchmark or C2 claim (RSI lab owns C2).",
        "corpus_path": rel,
        "corpus_sha256": sha256_file(corpus_path),
        "corpus_rows": len(rows),
        "decomposition": blocks,
        "summary": {
            "taskpacks": len(blocks),
            "any_positive_lift_vs_best_seat": any(
                b["lift_vs_best_seat"] > 0 for b in blocks),
        },
    }


def write_receipt(corpus_path: Path, out_path: Path) -> dict[str, Any]:
    receipt = build_receipt(corpus_path)
    receipt["generated_at"] = _utc_now()
    receipt["digest"] = stable_digest(
        {k: v for k, v in receipt.items() if k != "digest"})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    return receipt


def check(out_path: Path) -> list[str]:
    """Seal intact + pinned corpus unchanged + every value replays."""
    if not out_path.exists():
        return [f"receipt missing: {out_path}"]
    try:
        committed = json.loads(out_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [f"receipt is not valid JSON: {out_path}"]
    findings: list[str] = []
    stored = str(committed.get("digest", ""))
    if stored != stable_digest({k: v for k, v in committed.items() if k != "digest"}):
        findings.append("receipt digest mismatch (tampered or hand-edited)")
    corpus_path = REPO_ROOT / str(committed.get("corpus_path", ""))
    if not corpus_path.exists():
        findings.append(f"pinned corpus missing: {corpus_path}")
        return findings
    try:
        fresh = build_receipt(corpus_path)
    except ValueError as exc:  # fabricated labels / bad corpus (E1 invariant)
        return findings + [f"corpus fails decomposition: {exc}"]
    for key, value in fresh.items():
        if committed.get(key) != value:
            findings.append(f"field {key!r} does not replay from the pinned "
                            "corpus — rerun transcendence_ledger.py")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--out", type=Path, default=RECEIPT_PATH)
    parser.add_argument("--check", action="store_true",
                        help="verify the committed receipt replays (writes nothing)")
    args = parser.parse_args(argv)
    if args.check:
        findings = check(args.out)
        if findings:
            print("transcendence_ledger --check: FAIL")
            for f in findings:
                print(f"  - {f}")
            return 1
        print("transcendence_ledger --check: OK — decomposition replays from "
              "the pinned corpus.")
        return 0
    if not args.corpus.exists():
        print(f"transcendence_ledger: corpus not found at {args.corpus} — "
              "run a gym first (E5 mandate); refusing to invent numbers.")
        return 1
    receipt = write_receipt(args.corpus, args.out)
    for b in receipt["decomposition"]:
        print(f"  pack {b['taskpack_sha'][:12]} env={b['env_id']} n={b['n_tasks']} "
              f"E_mean={b['e_mean']} E_ens={b['e_ensemble']} "
              f"E_div={b['e_diversity_realized']} lift_vs_best={b['lift_vs_best_seat']} "
              f"err_corr={b['error_correlation']['mean_offdiag']}")
    print(f"transcendence_ledger: wrote {args.out} "
          f"(digest={receipt['digest'][:16]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
