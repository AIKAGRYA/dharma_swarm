"""CLI for the Forge production-contract harness."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from dharma_swarm.forge_prod_contracts.receipts import write_scoreboard_report
from dharma_swarm.forge_prod_contracts.scoreboard import (
    BudgetPolicy,
    run_offline_scoreboard,
)
from dharma_swarm.forge_prod_contracts.taskbed import (
    DEFAULT_SEED,
    default_private_code_repair_tasks,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the offline Forge production-contract scoreboard."
    )
    parser.add_argument(
        "--output-dir",
        default="reports/forge/production_contracts/offline_scoreboard_private_taskbed",
        help="Directory for scoreboard_report.json, scoreboard_report.md, and receipt.",
    )
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--token-budget", type=int, default=1200)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args(argv)

    report = run_offline_scoreboard(
        tasks=default_private_code_repair_tasks(seed=args.seed),
        budget_policy=BudgetPolicy(token_budget=args.token_budget),
        run_id=args.run_id,
    )
    json_path, markdown_path, receipt_path = write_scoreboard_report(
        report,
        args.output_dir,
    )
    print(f"wrote {json_path}")
    print(f"wrote {markdown_path}")
    print(f"wrote {receipt_path}")
    print(json.dumps(report.summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
