"""Runnable offline scoreboard demo — no live calls, no cost.

    python -m dharma_swarm.forge_v1.demo

Shows the FULL Forge measurement loop end-to-end on fake fixtures with stub
models: champion (best-of-N on a strong single model) vs a swarm stand-in, at
EQUAL token budget, producing a swarm_lift. Swap the stubs for real providers
and the fixtures for SWE-bench-lite, and the same numbers become real."""
from __future__ import annotations

import json

from .fixtures import DEMO_TASKS
from .harness import best_of_n, run_scoreboard
from .models import FlakyStub, StrongStub


def main() -> dict:
    budget = 5000  # tokens per task, identical for both arms

    # Champion = verifier-selected best-of-N on a strong single model.
    def champion(task, broker):
        return best_of_n(StrongStub(tokens=1000), task, broker)

    # 'Swarm' stand-in (offline): a flaky model under best-of-N. The real swarm
    # (localize -> repair -> verify -> rank) plugs in behind this same arm later.
    def swarm(task, broker):
        return best_of_n(FlakyStub(hit_every=3, tokens=1000), task, broker)

    report = run_scoreboard(DEMO_TASKS, champion, swarm, budget=budget)

    summary = {k: v for k, v in report.items() if k not in ("champion", "swarm")}
    print(json.dumps(summary, indent=2))
    print(
        f"\nswarm_lift = {report['swarm_lift']:+.3f}  "
        f"({report['status']}; ship_swarm={report['ship_swarm']})"
    )
    return report


if __name__ == "__main__":
    main()
