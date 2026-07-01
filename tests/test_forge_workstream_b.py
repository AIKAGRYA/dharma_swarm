from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.dgm_loop import DGMLoop, run_dgm_evolution_task
from dharma_swarm.forge_v1.forge_v2 import darwin_bridge, signals
from dharma_swarm.forge_v1.forge_v2.forge_fitness import ArmSpec, grade_genome
from dharma_swarm.forge_v1.forge_v2.verify_promotion import verify_promotion
from scripts.governance.check_forge_bypass import check_file, check_paths


def _positive_receipt() -> dict:
    return {
        "closeout": "positive_lift_candidate",
        "split_contrasts": {
            "confirm": {"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.1, "p_le_0": 0.01},
            "explore": {"n": 50, "mean": 0.08, "lower": 0.0, "upper": 0.15, "p_le_0": 0.05},
        },
        "contrast_vs_class_null": {"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.1, "p_le_0": 0.01},
        "budget_matched_proof": {"any_invalid": False},
    }


def test_grade_genome_routes_scaffold_to_forge_runner_confirm() -> None:
    captured = {}

    def fake_runner(instance_ids, **kwargs):
        captured["instance_ids"] = instance_ids
        captured.update(kwargs)
        return _positive_receipt()

    fitness = grade_genome(
        ArmSpec(arm="verify_chain", label="unit"),
        ["task-a", "task-b"],
        split="confirm",
        runner_fn=fake_runner,
    )

    assert captured["n_explore"] == 0
    assert captured["arm"] == "verify_chain"
    assert captured["gen_id"] == "glm-5.2"
    assert captured["ver_id"] == "moonshotai/kimi-k2.6"
    assert fitness.real_grade is True
    assert fitness.fitness == pytest.approx(0.06)
    assert fitness.promote_eligible is True


def test_grade_genome_explore_can_learn_but_not_promote() -> None:
    fitness = grade_genome(
        {"arm": "mixed_moa", "mix_models": ["glm-5.2", "moonshotai/kimi-k2.6"]},
        ["task-a"],
        split="explore",
        runner_fn=lambda *_args, **_kwargs: _positive_receipt(),
    )

    assert fitness.fitness == pytest.approx(0.08)
    assert fitness.promote_eligible is False
    assert "promotion_requires_confirm_split" in fitness.blockers


def test_e2_green_pytest_red_holdout_is_refused() -> None:
    signal = {
        "run_id": "e2",
        "signal_key": "e2:key",
        "arm": "verify_chain",
        "taskbed": "fresh_taskbed",
        "mission_class": "verifier_role",
        "overall_ci": {"n": 10, "mean": 0.2, "lower": 0.1, "upper": 0.3, "p_le_0": 0.01},
        "explore_ci": {"n": 5, "mean": 0.4, "lower": 0.1, "upper": 0.6, "p_le_0": 0.01},
        "confirm_ci": {"n": 5, "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0},
        "fdr_positive_significant": True,
        "contamination_state": "fresh_heldout",
        "class_null": "self_moa",
        "null_survived": False,
        "evidence_strength": 0.9,
        "promotion_blockers": [],
        "local_pytest_passed": True,
    }

    verdict = verify_promotion(signal, operator_lease={"lease_id": "op-1"})

    assert verdict["decision"] == "refused"
    assert verdict["live_apply_allowed"] is False
    assert "promotion_packet:stats_confirm_gate" in verdict["blockers"]


def test_dgm_loop_refuses_direct_live_mode(monkeypatch) -> None:
    monkeypatch.setenv("DHARMA_EVOLUTION_SHADOW", "0")
    monkeypatch.setenv("DGC_AUTONOMY_LEVEL", "3")

    loop = DGMLoop(engine=object(), shadow_mode=None)
    assert loop._shadow_mode is True
    with pytest.raises(ValueError, match="verify_promotion"):
        DGMLoop(engine=object(), shadow_mode=False)


@pytest.mark.asyncio
async def test_dgm_task_refuses_shadow_false() -> None:
    result = await run_dgm_evolution_task(shadow=False)

    assert result["success"] is False
    assert result["shadow_mode"] is True
    assert "verify_promotion" in result["error"]


def test_e3_path_based_freeze_rejects_stats_edit_despite_coordination_label() -> None:
    signal = {
        "mission_class": "coordination_policy",
        "arm": "verify_chain",
        "action": "hold_for_confirm",
        "diff": (
            "diff --git a/dharma_swarm/forge_v1/forge_v2/stats.py "
            "b/dharma_swarm/forge_v1/forge_v2/stats.py\n"
            "--- a/dharma_swarm/forge_v1/forge_v2/stats.py\n"
            "+++ b/dharma_swarm/forge_v1/forge_v2/stats.py\n"
        ),
    }

    with pytest.raises(darwin_bridge.EvaluatorMutationRefused, match="stats.py"):
        darwin_bridge.signal_to_archive_entry(signal)


def test_report_to_signals_clean_kwarg_cannot_override_public_swebench() -> None:
    meta = {
        "arms_tested": ["verify_chain"],
        "task_stats": {"django__django-12209": {"class_null": "self_moa"}},
        "contrasts": {"verify_chain": {"overall": {}, "by_split": {"confirm": {}, "explore": {}}}},
    }

    sig = signals.report_to_signals(
        meta,
        source_report_sha256="sha",
        run_id="run",
        contamination_state="clean",
    )[0]

    assert sig.contamination_state == "possible_pretrain"
    assert "contamination_possible_pretrain" in sig.promotion_blockers


def test_report_to_signals_accepts_sealed_fresh_provenance() -> None:
    meta = {
        "arms_tested": ["verify_chain"],
        "provenance": {"contamination_state": "fresh_heldout"},
        "task_stats": {"fresh__task-1": {"class_null": "self_moa"}},
        "contrasts": {
            "verify_chain": {
                "overall": {"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.1, "p_le_0": 0.01},
                "by_split": {
                    "confirm": {"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.1, "p_le_0": 0.01},
                    "explore": {"n": 0},
                },
                "fdr_positive_significant": True,
            }
        },
        "closeout_counts": {"positive_lift_candidate": 1},
    }

    sig = signals.report_to_signals(meta, source_report_sha256="sha", run_id="run")[0]

    assert sig.contamination_state == "fresh_heldout"
    assert not any(b.startswith("contamination_") for b in sig.promotion_blockers)


def test_bypass_guard_passes_current_tree_and_fails_shadow_false(tmp_path: Path) -> None:
    assert check_paths() == []

    bypass = tmp_path / "bypass.py"
    bypass.write_text(
        "from dharma_swarm.dgm_loop import DGMLoop\n"
        "DGMLoop(engine=object(), shadow_mode=False)\n",
        encoding="utf-8",
    )

    findings = check_file(bypass)
    assert findings
    assert "shadow_mode=False" in findings[0]
