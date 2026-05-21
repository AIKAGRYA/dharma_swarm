"""MCP server for the Goodworks DGM surface."""

from __future__ import annotations

import asyncio
import json

from dharma_swarm.goodworks_dgm.models import GoalSpec, MutationMode
from dharma_swarm.goodworks_dgm.service import GoodworksDGMService

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - optional dependency guard
    raise ImportError("Install the optional 'mcp' package to run Goodworks DGM MCP.") from exc

mcp = FastMCP(
    "goodworks-dgm",
    instructions=(
        "Goodworks DGM tools expose dry-run and shadow-only goal loops over "
        "Dharma Swarm's existing reciprocity ledger, GAIA ledger, wiki context, "
        "AutoResearch planner, and DGM loop."
    ),
)


@mcp.tool(name="goodworks-dgm-status")
def goodworks_dgm_status(limit: int = 10) -> str:
    return json.dumps(GoodworksDGMService().status(limit=limit), indent=2, sort_keys=True)


@mcp.tool(name="goodworks-dgm-receipts")
def goodworks_dgm_receipts(limit: int = 20) -> str:
    return json.dumps(
        GoodworksDGMService().recent_receipts(limit=limit),
        indent=2,
        sort_keys=True,
    )


@mcp.tool(name="goodworks-dgm-score")
def goodworks_dgm_score() -> str:
    snapshot = GoodworksDGMService().score_goodworks_mrv()
    return snapshot.model_dump_json(indent=2)


@mcp.tool(name="goodworks-dgm-create-goal")
def goodworks_dgm_create_goal(
    title: str,
    objective: str,
    mutation_mode: str = "dry_run",
    run_now: bool = True,
) -> str:
    mode = MutationMode(mutation_mode)
    spec = GoalSpec(title=title, objective=objective, mutation_mode=mode)
    run = asyncio.run(GoodworksDGMService().create_goal(spec, run_now=run_now))
    return run.model_dump_json(indent=2)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
