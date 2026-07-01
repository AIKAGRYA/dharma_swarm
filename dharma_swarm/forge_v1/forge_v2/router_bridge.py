"""Shadow router bridge (Learning Spine v0).

Projects learning signals into SHADOW route-outcome / retrospective artifacts and
writes them ONLY under ``<store_root>/shadow_router/``. It never imports or touches
``RoutingMemoryStore`` (so the live ``routing_memory.sqlite3`` cannot be mutated),
never changes ``ModelRouter`` reward state, ``model_hierarchy`` defaults, provider
order, keys, or any live routing surface.

Semantic-leap guard: a Forge ARM (self_moa / verify_chain / mixed_moa) is a
COORDINATION STRATEGY, not a provider. We therefore record outcomes against a
sentinel ``forge_coordination_arm`` provider and state in ``reasons`` that this is
a coordination-strategy signal, NOT a provider-capability claim. Registry/capability
data are priors, not truth: a Forge result may reorder a recommendation, never
assert global model capability without held-out measurement.

No live callability checks are performed in v0; if any are added later they MUST go
through the single door (resolve_runtime_provider_config -> create_runtime_provider).
"""
from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.router_retrospective import (
    RouteOutcomeRecord,
    build_route_retrospective,
)

PROVIDER_SENTINEL = "forge_coordination_arm"
_DOWNWEIGHT_ACTIONS = ("downrank_or_ablate", "avoid_default_use_on_this_taskbed", "quarantine")


def _quality_proxy(signal: dict) -> float:
    """Map the arm's observed lift to a [0,1] quality proxy (0.5 == parity)."""
    overall = signal.get("overall_ci", {}) or {}
    return max(0.0, min(1.0, 0.5 + float(overall.get("mean", 0.0))))


def signal_to_route_outcome(signal: dict) -> RouteOutcomeRecord:
    """Build a SHADOW RouteOutcomeRecord for one signal. Never persisted to live state."""
    action = str(signal.get("action", ""))
    underperformed = action in _DOWNWEIGHT_ACTIONS or bool(signal.get("null_survived"))
    return RouteOutcomeRecord(
        action_name=f"forge_arm::{signal.get('mission_class', 'unknown')}",
        route_path="deliberative",
        selected_provider=PROVIDER_SENTINEL,
        selected_model=str(signal.get("arm", "unknown")),
        confidence=float(signal.get("evidence_strength", 0.0)),
        quality_score=_quality_proxy(signal),
        result="failure" if underperformed else "success",
        task_signature=f"{signal.get('taskbed')}|{signal.get('mission_class')}",
        latency_ms=0.0,
        total_tokens=0,
        reasons=[
            f"forge_action={action}",
            f"evidence_strength={signal.get('evidence_strength')}",
            f"null_survived={bool(signal.get('null_survived'))}",
            f"contamination={signal.get('contamination_state')}",
            "SHADOW_ONLY: coordination-strategy signal, NOT a provider-capability claim",
            "priors_not_truth: Forge evidence may reorder a recommendation only",
        ],
        signals={
            "taskbed": signal.get("taskbed"),
            "mission_class": signal.get("mission_class"),
            "arm": signal.get("arm"),
            "contamination_state": signal.get("contamination_state"),
            "null_survived": bool(signal.get("null_survived")),
            "promotion_blockers": signal.get("promotion_blockers", []),
        },
        failures=[],
    )


def project_signals(signals, *, store_root: Path | str) -> dict:
    """Write shadow route-outcome records (+ any retrospectives) under shadow_router/.

    Returns a summary; mutates only files beneath ``store_root/shadow_router``.
    """
    root = Path(store_root).expanduser() / "shadow_router"
    root.mkdir(parents=True, exist_ok=True)
    outcomes_path = root / "route_outcomes.jsonl"
    retro_path = root / "retrospectives.jsonl"

    n_outcomes = 0
    n_retros = 0
    with outcomes_path.open("a", encoding="utf-8") as out_fh:
        for s in signals:
            sig = s if isinstance(s, dict) else s.to_dict()
            record = signal_to_route_outcome(sig)
            out_fh.write(record.model_dump_json() + "\n")
            n_outcomes += 1
            # A retrospective is only raised for high-confidence underperformance
            # (router_retrospective's own floors). Weak/null evidence -> None (honest).
            artifact = build_route_retrospective(record)
            if artifact is not None:
                with retro_path.open("a", encoding="utf-8") as r_fh:
                    r_fh.write(artifact.model_dump_json() + "\n")
                n_retros += 1

    return {
        "shadow_router_dir": str(root),
        "n_route_outcomes": n_outcomes,
        "n_retrospectives": n_retros,
        "live_routing_touched": False,
    }
