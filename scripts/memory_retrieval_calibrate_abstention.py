#!/usr/bin/env python3
"""Calibrate RetrievalAbstentionConfig.min_score from live retrieval telemetry.

Reads the ``memory_retrieval_query_log`` table (written by
``GovernedRetrievalEngine._record_retrieval_telemetry``) strictly READ-ONLY
(sqlite uri ``mode=ro``) and recommends the largest min_score threshold whose
historical cost — served queries that would newly abstain — stays within
``--max-loss-rate``. Emits a JSON receipt so the recommendation is auditable
and the later DEFAULT-ON flip can cite it.

The recommendation feeds ``DHARMA_MEMORY_RETRIEVAL_CALIBRATED_MIN_SCORE`` /
``RetrievalAbstentionConfig(min_score=...)``; this script never mutates the
database or any engine config.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path.home() / ".dharma" / "vectors.db"
DEFAULT_RECEIPT_DIR = Path.home() / ".dharma" / "witness" / "retrieval_calibration"
PERCENTILES = (1, 5, 10, 25, 50, 75, 90, 99)


def _percentile(sorted_scores: list[float], pct: float) -> float:
    if not sorted_scores:
        return 0.0
    idx = min(len(sorted_scores) - 1, int(len(sorted_scores) * pct / 100.0))
    return sorted_scores[idx]


def load_telemetry(db_path: Path) -> dict[str, object]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        total, first_time, last_time = conn.execute(
            "SELECT COUNT(*), MIN(query_time), MAX(query_time) FROM memory_retrieval_query_log"
        ).fetchone()
        empty = conn.execute(
            "SELECT COUNT(*) FROM memory_retrieval_query_log WHERE result_count = 0"
        ).fetchone()[0]
        scores = [
            float(row[0])
            for row in conn.execute(
                """
                SELECT top_score FROM memory_retrieval_query_log
                WHERE result_count > 0 AND top_score IS NOT NULL
                ORDER BY top_score
                """
            )
        ]
    finally:
        conn.close()
    return {
        "row_count": int(total or 0),
        "empty_result_count": int(empty or 0),
        "served_scored_count": len(scores),
        "first_query_time": first_time,
        "last_query_time": last_time,
        "scores": scores,
    }


def recommend_min_score(
    sorted_scores: list[float],
    *,
    max_loss_rate: float,
    grid_step: float = 0.01,
) -> dict[str, object]:
    """Largest grid threshold whose newly-abstained fraction <= max_loss_rate.

    Search is capped at the served median: recommending above p50 would never
    be a calibration, only an outage.
    """

    if not sorted_scores:
        return {
            "recommended_min_score": None,
            "reason": "no_served_scored_rows",
            "newly_abstained_count": 0,
            "newly_abstained_rate": 0.0,
        }
    n = len(sorted_scores)
    cap = _percentile(sorted_scores, 50)
    best = 0.0
    best_below = 0
    steps = int(cap / grid_step) + 1
    for i in range(steps):
        threshold = round(i * grid_step, 4)
        below = _count_below(sorted_scores, threshold)
        if below / n <= max_loss_rate:
            best = threshold
            best_below = below
        else:
            break
    return {
        "recommended_min_score": best,
        "reason": "max_threshold_within_loss_budget",
        "newly_abstained_count": best_below,
        "newly_abstained_rate": round(best_below / n, 6),
    }


def _count_below(sorted_scores: list[float], threshold: float) -> int:
    lo, hi = 0, len(sorted_scores)
    while lo < hi:
        mid = (lo + hi) // 2
        if sorted_scores[mid] < threshold:
            lo = mid + 1
        else:
            hi = mid
    return lo


def build_receipt(db_path: Path, telemetry: dict[str, object], recommendation: dict[str, object], max_loss_rate: float) -> dict[str, object]:
    scores = telemetry["scores"]
    assert isinstance(scores, list)
    return {
        "script": "scripts/memory_retrieval_calibrate_abstention.py",
        "action": "calibrate_retrieval_abstention_min_score",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "db_path": str(db_path),
        "db_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "read_only": True,
        "telemetry": {k: v for k, v in telemetry.items() if k != "scores"},
        "top_score_percentiles": {
            f"p{pct}": round(_percentile(scores, pct), 4) for pct in PERCENTILES
        },
        "max_loss_rate": max_loss_rate,
        "recommendation": recommendation,
        "apply_via": (
            "DHARMA_MEMORY_RETRIEVAL_CALIBRATED_MIN_SCORE=<value> with "
            "DHARMA_MEMORY_RETRIEVAL_CALIBRATED_ABSTENTION=1, or "
            "RetrievalAbstentionConfig.calibrated(min_score=<value>)"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPT_DIR)
    parser.add_argument(
        "--max-loss-rate",
        type=float,
        default=0.001,
        help="max fraction of historically-served queries allowed to newly abstain",
    )
    parser.add_argument("--grid-step", type=float, default=0.01)
    args = parser.parse_args(argv)

    if not args.db.exists():
        print(f"error: telemetry db not found: {args.db}", file=sys.stderr)
        return 2
    try:
        telemetry = load_telemetry(args.db)
    except sqlite3.OperationalError as exc:
        print(f"error: cannot read telemetry ({exc})", file=sys.stderr)
        return 2

    scores = telemetry["scores"]
    assert isinstance(scores, list)
    recommendation = recommend_min_score(
        scores, max_loss_rate=args.max_loss_rate, grid_step=args.grid_step
    )
    receipt = build_receipt(args.db, telemetry, recommendation, args.max_loss_rate)

    args.receipt_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    receipt_path = args.receipt_dir / f"abstention_calibration_{stamp}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")

    print(json.dumps({
        "recommended_min_score": recommendation["recommended_min_score"],
        "newly_abstained_count": recommendation["newly_abstained_count"],
        "newly_abstained_rate": recommendation["newly_abstained_rate"],
        "served_scored_count": telemetry["served_scored_count"],
        "receipt": str(receipt_path),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
