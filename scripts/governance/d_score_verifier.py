#!/usr/bin/env python3
"""Write receipt-backed D-score reports for HOLON/APEX promotion evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.verify.d_score import score_agent, score_substrate, write_d_score_report  # noqa: E402

DEFAULT_TARGETS = ("codex_composer", "hermes_m5", "sarathi", "dharma_substrate")
DEFAULT_OUT_DIR = REPO_ROOT / "reports" / "agents" / "d_scores"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="Agent/system target. Repeatable. Defaults to codex_composer, hermes_m5, sarathi, dharma_substrate.",
    )
    parser.add_argument("--state-root", default=str(Path.home() / ".dharma"))
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary.")
    args = parser.parse_args(argv)

    targets = tuple(args.target or DEFAULT_TARGETS)
    out_dir = Path(args.out_dir)
    summaries: list[dict[str, object]] = []
    for target in targets:
        if target == "dharma_substrate":
            report = score_substrate(state_root=args.state_root, repo_root=args.repo_root)
        else:
            report = score_agent(target, state_root=args.state_root, repo_root=args.repo_root)
        json_path, md_path = write_d_score_report(report, out_dir)
        summaries.append(
            {
                "target": target,
                "total_score": report.total_score,
                "claimed_level": report.claimed_level,
                "verified_level": report.verified_level,
                "hard_gate_failures": report.hard_gate_failures,
                "json_path": str(json_path),
                "markdown_path": str(md_path),
            }
        )

    payload = {"status": "D_SCORE_REPORTS_WRITTEN", "reports": summaries}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(payload["status"])
        for summary in summaries:
            print(
                f"- {summary['target']}: {summary['total_score']}/50 "
                f"{summary['claimed_level']} -> {summary['verified_level']} "
                f"hard_gates={len(summary['hard_gate_failures'])}"
            )
            print(f"  json: {summary['json_path']}")
            print(f"  md:   {summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
