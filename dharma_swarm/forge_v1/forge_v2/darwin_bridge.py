"""Shadow Darwin bridge (Learning Spine v0).

Builds Darwin ``ArchiveEntry`` proposals from learning signals and persists them to
a SEPARATE shadow archive under the store root — NEVER the live evolution archive
(``~/.dharma/evolution/archive.jsonl``). It reuses the engine's schema for fidelity
but writes the rows itself (sync, fully controlled) so there is no path by which an
engine default location, merkle log, or live grid is touched.

Hard invariants (never executed here — listed so review can grep for violations):
  * never call DarwinEngine.auto_evolve(..., shadow=False)
  * never call DarwinEngine.apply_diff_and_test / apply_sealed_packet(..., shadow=False)
  * never construct DGMLoop(..., shadow_mode=False)
  * never write a code diff (v0: diff is always empty; proposals are policy overlays)

Trap 6 (evaluator-freeze): a proposal must NOT target the evaluator/scorer lane.
``signal_to_archive_entry`` refuses to build an entry whose mutation target is any
Forge measurement module — the ruler is frozen while it judges.
"""
from __future__ import annotations

from pathlib import Path

from dharma_swarm.archive import ArchiveEntry, FitnessScore

LIVE_ARCHIVE = Path("~/.dharma/evolution/archive.jsonl").expanduser()
SHADOW_ARCHIVE_NAME = "darwin_shadow_archive.jsonl"

# The evaluator/scorer lane — proposing a mutation here in the same experiment is
# the single most dangerous move (fake-green by making the test easier). Refused.
EVALUATOR_MODULES = frozenset(
    {"stats", "critic", "runner", "budget", "provenance", "promote", "signals",
     "scheduler", "analysis", "receipts"}
)


class EvaluatorMutationRefused(Exception):
    """Raised if a proposal would mutate the frozen evaluator lane."""


def _fitness_from_signal(signal: dict) -> FitnessScore:
    """Honest, low, provenance-only fitness for an UNVALIDATED shadow proposal."""
    strength = float(signal.get("evidence_strength", 0.0))
    return FitnessScore(
        correctness=strength,
        dharmic_alignment=0.0,
        swabhaav_alignment=0.0,
        performance=0.0,
        utilization=0.0,
        economic_value=0.0,
        elegance=0.0,
        efficiency=0.0,
        safety=1.0,  # a shadow proposal that changes nothing live is safe
    )


def signal_to_archive_entry(signal: dict) -> ArchiveEntry:
    """Build a SHADOW, unvalidated ArchiveEntry (policy overlay; no code diff)."""
    mission = str(signal.get("mission_class", "unknown"))
    arm = str(signal.get("arm", "unknown"))
    action = str(signal.get("action", ""))

    # v0 mutation target is the coordination/arm-selection policy for this mission
    # class — explicitly NOT an evaluator module.
    target = f"coordination_policy::{mission}"
    if mission in EVALUATOR_MODULES or arm in EVALUATOR_MODULES:
        raise EvaluatorMutationRefused(f"refused evaluator-lane target: {mission}/{arm}")

    description = (
        f"SHADOW proposal: {action} arm '{arm}' for mission '{mission}' on taskbed "
        f"'{signal.get('taskbed')}'. Evidence_strength={signal.get('evidence_strength')}; "
        f"blockers={signal.get('promotion_blockers')}; contamination="
        f"{signal.get('contamination_state')}. Shadow-only; not promotable."
    )
    return ArchiveEntry(
        parent_id=None,
        component=target,
        change_type="coordination_policy_overlay",
        description=description,
        spec_ref=signal.get("signal_key"),
        requirement_refs=["forge_learning_signal"],
        diff="",  # v0: never a code diff
        fitness=_fitness_from_signal(signal),
        test_results={
            "forge_overall_ci": signal.get("overall_ci"),
            "forge_confirm_ci": signal.get("confirm_ci"),
            "forge_action": action,
            "run_id": signal.get("run_id"),
        },
        evidence_tier="unvalidated",
        promotion_state="candidate",
        gates_passed=[],
        gates_failed=[],
        agent_id="forge_darwin_bridge_v0",
        model="",
        tokens_used=0,
        status="proposed",
    )


def project_signals(signals, *, store_root: Path | str) -> dict:
    """Append shadow ArchiveEntry rows under store_root/darwin_shadow/. Live archive
    is never opened. Returns a summary."""
    shadow_dir = Path(store_root).expanduser() / "darwin_shadow"
    shadow_dir.mkdir(parents=True, exist_ok=True)
    shadow_path = shadow_dir / SHADOW_ARCHIVE_NAME

    # Defensive: never let the shadow path collapse onto the live archive.
    assert shadow_path.resolve() != LIVE_ARCHIVE.resolve(), "shadow path == live archive"

    n_written = 0
    n_refused = 0
    with shadow_path.open("a", encoding="utf-8") as fh:
        for s in signals:
            sig = s if isinstance(s, dict) else s.to_dict()
            try:
                entry = signal_to_archive_entry(sig)
            except EvaluatorMutationRefused:
                n_refused += 1
                continue
            fh.write(entry.model_dump_json() + "\n")
            n_written += 1

    return {
        "shadow_archive": str(shadow_path),
        "n_proposals": n_written,
        "n_evaluator_refused": n_refused,
        "live_archive_touched": False,
    }
