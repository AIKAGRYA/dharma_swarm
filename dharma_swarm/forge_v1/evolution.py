"""L4 — the Karpathy/DGM evolutionary loop. The eval (the honest scoreboard) IS
the fitness function. Each generation branches mutations off archived configs
(stepping-stones, including non-top ancestors — DGM, not greedy hill-climbing),
scores each via the verifier-grounded scoreboard at fixed budget, and keeps the
best-so-far. The archive is a monotone record of what actually scored better.

SELF-CONTAINED: writes its own archive under ~/.dharma/forge_v1/. It does NOT
touch dharma_swarm's evolution/archive.jsonl or the One-Wire governance invariant
— that wiring is gated behind a separate operator ruling. Archive-before-signal
is an anti-pattern; prove the loop closes on an unfakeable eval here first."""
from __future__ import annotations

import json
import random
from pathlib import Path

from .harness import run_arm, run_scoreboard
from .swarm import SwarmConfig, build_arm


def _fitness(config: SwarmConfig, tasks, budget: int) -> float:
    return run_arm(build_arm(config), tasks, budget)["pass_at_1"]


def _mutate_once(config: SwarmConfig, rng: random.Random) -> SwarmConfig:
    proposers = list(config.proposers)
    gate = config.verify_gate
    op = rng.choice(["add", "remove", "tweak", "gate"])
    if op == "add" and len(proposers) < 6:
        proposers.append((rng.randint(0, 9999), rng.choice([2, 3])))
    elif op == "remove" and len(proposers) > 1:
        proposers.pop(rng.randrange(len(proposers)))
    elif op == "tweak" and proposers:
        i = rng.randrange(len(proposers))
        proposers[i] = (rng.randint(0, 9999), rng.choice([2, 3]))
    elif op == "gate":
        gate = not gate
    return SwarmConfig(proposers, verify_gate=gate, tokens_per_call=config.tokens_per_call)


def _mutate(config: SwarmConfig, rng: random.Random) -> SwarmConfig:
    """Apply 1-3 atomic mutations, so the search can reach multi-proposer + gate
    configs in a few steps instead of needing a lucky single hop each time."""
    cfg = config
    for _ in range(rng.choice([1, 1, 2, 3])):
        cfg = _mutate_once(cfg, rng)
    return cfg


def evolve(tasks, champion, budget, generations=20, seed=0,
           archive_path: str | None = None, ledger=None) -> tuple[dict, SwarmConfig, list]:
    rng = random.Random(seed)
    seed_cfg = SwarmConfig([(1, 3)], verify_gate=False)  # deliberately weak start
    archive = [{"gen": 0, "config": seed_cfg,
                "fitness": _fitness(seed_cfg, tasks, budget), "parent": None}]
    best = archive[0]
    curve = [round(best["fitness"], 4)]

    for g in range(1, generations + 1):
        # DGM parent selection: top-3 stepping-stones + 2 random (incl. non-top),
        # exploiting the frontier while keeping diversity against local optima.
        ranked = sorted(archive, key=lambda e: -e["fitness"])
        parents = [e["config"] for e in ranked[:3]]
        parents += [rng.choice(archive)["config"] for _ in range(2)]
        for parent in parents:
            child = _mutate(parent, rng)
            fit = _fitness(child, tasks, budget)
            entry = {"gen": g, "config": child, "fitness": fit,
                     "parent": parent.fingerprint()}
            archive.append(entry)
            if fit > best["fitness"]:
                best = entry
        curve.append(round(best["fitness"], 4))

    report = run_scoreboard(tasks, champion, build_arm(best["config"]), budget)
    out = {
        "generations": generations,
        "fitness_curve": curve,                      # best-so-far swarm pass@1 / gen
        "best_config": best["config"].fingerprint(),
        "swarm_pass_at_1": round(report["swarm_pass_at_1"], 4),
        "champion_pass_at_1": round(report["champion_pass_at_1"], 4),
        "final_swarm_lift": round(report["swarm_lift"], 4),
        "final_lift_ci": report["paired_bootstrap_ci"],
        "ship_swarm": report["ship_swarm"],
        "archive_size": len(archive),
    }

    if archive_path:
        p = Path(archive_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w") as fh:
            for e in archive:
                fh.write(json.dumps({
                    "gen": e["gen"], "fitness": round(e["fitness"], 4),
                    "config": e["config"].fingerprint(), "parent": e["parent"],
                }) + "\n")
    if ledger is not None:
        ledger.record({"event": "evolve", **out})

    return out, best["config"], archive
