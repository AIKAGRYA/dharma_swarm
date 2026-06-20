"""The WHOLE Forge, end-to-end, offline — all four layers in one run:

    python -m dharma_swarm.forge_v1.demo_full

L1 real-model adapter (here: offline competence models; flip to providers.LiveModel
   + PoolCompletion to go live on gpt-5.5/opus-4.8),
L2 the coordinated swarm vs best-of-N on the single best model, on benchmark-shaped
   tasks (here: hard local fixtures; flip swebench.bench_tasks to SWE-bench-Verified),
L3 tracking everything (run ledger) + the leave-one-edge-out ablation,
L4 the Karpathy/DGM evolutionary loop that improves the swarm against the honest
   scoreboard and archives the stepping-stones.

No live calls, no cost. The two flips to make it real (live providers, real
SWE-bench) are the only things between this and the full vision."""
from __future__ import annotations

import json

from .evolution import evolve
from .harness import best_of_n
from .swarm import QualityModel
from .swebench import synthetic_tasks
from .tracking import LEDGER_DIR, RunLedger, ablate_edges


def main() -> dict:
    tasks = synthetic_tasks(24)  # well-powered offline set (vs v0's n=3)
    budget = 8000  # tokens per task per arm (≈ up to 8 proposer calls)

    # Champion = verifier-selected best-of-N on the single best callable model.
    def champion(task, broker):
        return best_of_n(QualityModel("champ", seed=7, comp_period=2), task, broker)

    ledger = RunLedger()
    out, best_cfg, archive = evolve(
        tasks, champion, budget,
        generations=20, seed=42,
        archive_path=str(LEDGER_DIR / "archive.jsonl"),
        ledger=ledger,
    )
    abl = ablate_edges(best_cfg, tasks, champion, budget)

    print("=" * 64)
    print("FORGE v1 — end-to-end (offline). L1 models · L2 swarm-vs-best-of-N ·")
    print("           L3 tracking+ablation · L4 Karpathy/DGM evolution")
    print("=" * 64)
    print(f"\nL4  fitness curve (best swarm pass@1 / generation):\n    {out['fitness_curve']}")
    print(f"\nL2  best evolved swarm: {out['best_config']}")
    print(f"      swarm    pass@1 = {out['swarm_pass_at_1']:.3f}")
    print(f"      champion pass@1 = {out['champion_pass_at_1']:.3f}   (best-of-N, single model)")
    ci = out["final_lift_ci"]
    print(f"      swarm_lift      = {out['final_swarm_lift']:+.3f}   "
          f"({'SHIP swarm' if out['ship_swarm'] else 'freeze swarm, ship best-of-N'})")
    print(f"      paired CI       = [{ci['lower']:+.3f}, {ci['upper']:+.3f}]   "
          "ship requires lower > 0")
    print(f"\nL3  ablation (did each coordination edge earn its tokens?):")
    print("    " + json.dumps(abl).replace("{", "{\n      ").replace(", ", ",\n      "))
    print(f"\n    archive: {out['archive_size']} configs  ->  {LEDGER_DIR / 'archive.jsonl'}")
    print(f"    run ledger                              ->  {ledger.path}")
    return {"evolution": out, "ablation": abl}


if __name__ == "__main__":
    main()
