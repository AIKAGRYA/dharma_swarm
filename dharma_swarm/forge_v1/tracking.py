"""L3 — track everything + the leave-one-edge-out ablation.

Two jobs:
1. RunLedger: append a rich record of every scoreboard run to a JSONL ledger
   under ~/.dharma/forge_v1/ (NEVER into the git tree — runtime receipts rule),
   so we can learn from history, not just read the last scalar.
2. ablate_edges: measure whether COORDINATION actually helped, by removing one
   swarm edge at a time and re-scoring at the same budget. An edge whose removal
   doesn't drop the score is not earning its tokens — exactly the measurement v0
   never had (it asserted `consumed_by_final_action=True` instead of measuring)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path

from .harness import run_scoreboard
from .swarm import SwarmConfig, build_arm

LEDGER_DIR = Path.home() / ".dharma" / "forge_v1"


@dataclass
class RunLedger:
    path: Path = field(default_factory=lambda: LEDGER_DIR / "runs.jsonl")

    def __post_init__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, record: dict) -> None:
        with self.path.open("a") as fh:
            fh.write(json.dumps(record, default=_json_default) + "\n")

    def all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]


def _json_default(o):
    if is_dataclass(o):
        return asdict(o)
    return str(o)


def ablate_edges(config: SwarmConfig, tasks, champion, budget: int) -> dict:
    """Leave-one-edge-out: full swarm vs the swarm with each coordination edge
    removed, at the SAME budget. Returns each edge's measured contribution to
    swarm_lift. Edges considered: each extra proposer beyond the first, and the
    verify-gate. Contribution <= 0 means the edge isn't earning its tokens."""
    full = build_arm(config)
    base = run_scoreboard(tasks, champion, full, budget)["swarm_lift"]

    contributions = {}

    # edge: the verify-gate
    if config.verify_gate:
        ablated = SwarmConfig(list(config.proposers), verify_gate=False,
                              tokens_per_call=config.tokens_per_call)
        lift = run_scoreboard(tasks, champion, build_arm(ablated), budget)["swarm_lift"]
        contributions["verify_gate"] = round(base - lift, 4)

    # edge: each extra proposer (drop one at a time)
    if len(config.proposers) > 1:
        for i in range(len(config.proposers)):
            reduced = [p for j, p in enumerate(config.proposers) if j != i]
            ablated = SwarmConfig(reduced, verify_gate=config.verify_gate,
                                  tokens_per_call=config.tokens_per_call)
            lift = run_scoreboard(tasks, champion, build_arm(ablated), budget)["swarm_lift"]
            contributions[f"proposer[{i}]"] = round(base - lift, 4)

    return {"base_swarm_lift": round(base, 4), "edge_contributions": contributions}
