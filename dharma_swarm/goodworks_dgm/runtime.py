"""Runtime tick helpers for Goodworks DGM.

These helpers are default-off. Operators can run one dry tick manually or wrap
the CLI in launchd/cron after reviewing receipts.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from dharma_swarm.goodworks_dgm.models import GoalSpec, MutationMode
from dharma_swarm.goodworks_dgm.seed import seed_goodworks_mrv_pilot
from dharma_swarm.goodworks_dgm.service import GoodworksDGMService


async def run_goodworks_dgm_tick(
    *,
    mutation_mode: MutationMode = MutationMode.DRY_RUN,
    state_dir: Path | None = None,
    ledger_root: Path | None = None,
    seed_pilot: bool = False,
) -> dict[str, Any]:
    seed_result = seed_goodworks_mrv_pilot(ledger_root=ledger_root) if seed_pilot else None
    service = GoodworksDGMService(state_dir=state_dir, ledger_root=ledger_root)
    spec = GoalSpec(
        title="Goodworks DGM scheduled tick",
        objective=(
            "Score Goodworks MRV ledgers, compile wiki context, bind AutoResearch "
            "candidate planning, and optionally run one DGM shadow iteration."
        ),
        mutation_mode=mutation_mode,
        budget_iterations=1,
        created_by="goodworks_dgm_tick",
    )
    run = await service.create_goal(spec, run_now=True)
    return {
        "seed": seed_result,
        "run": run.model_dump(mode="json"),
    }


async def run_goodworks_dgm_loop(
    *,
    interval_seconds: float,
    max_ticks: int,
    mutation_mode: MutationMode = MutationMode.DRY_RUN,
    state_dir: Path | None = None,
    ledger_root: Path | None = None,
    seed_pilot: bool = False,
) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for index in range(max_ticks):
        receipts.append(
            await run_goodworks_dgm_tick(
                mutation_mode=mutation_mode,
                state_dir=state_dir,
                ledger_root=ledger_root,
                seed_pilot=seed_pilot and index == 0,
            )
        )
        if index < max_ticks - 1:
            await asyncio.sleep(interval_seconds)
    return receipts
