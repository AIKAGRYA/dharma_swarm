#!/usr/bin/env python3
"""Generate Goal A alpha evidence membrane artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dharma_swarm.capital_lab.alpha_evidence import (
    DEFAULT_HARNESS_RUN_ID,
    DEFAULT_RUN_ID,
    MISSION_ID,
    generate_alpha_evidence_bundle,
    mirror_bundle,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_ROOT = REPO_ROOT / "spec-forge" / "dharma-capital-lab-real-data-alpha-evidence-membrane"
REPORT_ROOT = REPO_ROOT / "reports" / "capital_lab" / "goal_a_12h"
BOOTSTRAP_DIR = SPEC_ROOT / "runs" / "20260605T135403Z"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate evidence-only Goal A provider, lineage, leakage, OOS, scorecard, and report artifacts."
    )
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--mission-id", default=MISSION_ID)
    parser.add_argument("--harness-run-id", default=DEFAULT_HARNESS_RUN_ID)
    parser.add_argument("--data-root", default="/root/trading_lab")
    parser.add_argument("--bootstrap-dir", default=str(BOOTSTRAP_DIR))
    parser.add_argument("--spec-runs-root", default=str(SPEC_ROOT / "runs"))
    parser.add_argument("--report-root", default=str(REPORT_ROOT))
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--no-report-mirror", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_root = Path(args.data_root)
    if not data_root.exists():
        data_root_arg: Path | None = None
    else:
        data_root_arg = data_root

    spec_output_dir = Path(args.spec_runs_root) / args.run_id
    result = generate_alpha_evidence_bundle(
        output_dir=spec_output_dir,
        run_id=args.run_id,
        mission_id=args.mission_id,
        harness_run_id=args.harness_run_id,
        data_root=data_root_arg,
        bootstrap_dir=Path(args.bootstrap_dir),
        generated_at=args.generated_at,
    )

    report_output_dir = None
    if not args.no_report_mirror:
        report_output_dir = Path(args.report_root) / args.run_id
        mirror_bundle(spec_output_dir, report_output_dir)

    summary = {
        "clean": result["clean"],
        "live_authority": False,
        "live_readiness": 0,
        "report_output_dir": str(report_output_dir) if report_output_dir else "",
        "score": result["score"],
        "spec_output_dir": str(spec_output_dir),
        "status": result["status"],
        "validation": result["validation"]["valid"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
