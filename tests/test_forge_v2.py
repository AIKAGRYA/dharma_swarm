from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from dharma_swarm.forge_v1 import canonical
from dharma_swarm.forge_v1.forge_v2 import arms
from dharma_swarm.forge_v1.forge_v2 import CLOSEOUT_STATES
from dharma_swarm.forge_v1.forge_v2.arms import _win
from dharma_swarm.forge_v1.forge_v2.budget import Budget
from dharma_swarm.forge_v1.forge_v2.provenance import contamination_state, split_explore_confirm
from dharma_swarm.forge_v1.forge_v2.receipts import AttemptReceipt, Ledger, scaffold_parity_hash
from dharma_swarm.forge_v1.forge_v2.runner import _pick_generator_verifier
from dharma_swarm.forge_v1.canonical import KIMI_TEMP1, WINDOW_MODELS
from dharma_swarm.forge_v1.forge_v2.stats import (
    benjamini_hochberg,
    paired_bootstrap_ci,
    positive_claim_gate,
    replicate_variance,
)


@dataclass(frozen=True)
class Slot:
    model_id: str
    tier: str = "strong"


def test_budget_accounts_unknown_price_as_shadow_and_invalidates_over_cap() -> None:
    budget = Budget(cap_tokens=100, cap_usd=0.00001)

    budget.charge("generation", 50, usd=0.0, is_free_route=False)

    assert budget.shadow_usd > 0
    assert budget.invalid is True
    assert "over $ cap" in (budget.invalid_reason or "")


def test_budget_invalidates_token_overrun() -> None:
    budget = Budget(cap_tokens=10, cap_usd=1.0)

    budget.charge("generation", 11)

    assert budget.invalid is True
    assert budget.invalid_reason == "over token cap: 11/10"


def test_first_slice_windows_all_models_to_fit_budget_before_big_context_calls() -> None:
    assert _win(Slot("glm-5.2")) == 11000
    assert _win(Slot("moonshotai/kimi-k2.6")) == 11000


def test_proposal_receipts_prove_mutation_gene_prompt_causality(
    monkeypatch,
) -> None:
    prompts: list[str] = []
    slot = SimpleNamespace(
        model_id="digest-test-model",
        provider=SimpleNamespace(value="test"),
    )
    monkeypatch.setattr(canonical, "build_repair_prompt", lambda _inst, _ctx: "BASE")
    monkeypatch.setattr(
        canonical,
        "_provider_for_slot",
        lambda _slot, timeout_s: (object(), "wire"),
    )

    def capture_call(_provider, _wire, messages, **_kwargs):
        prompts.append(messages[0]["content"])
        return "", 0, None

    monkeypatch.setattr(canonical, "_call", capture_call)

    control = canonical._propose_slot(
        slot,
        {"problem_statement": "problem"},
        {},
        max_tokens=10,
        timeout_s=1,
        continue_rounds=0,
    )
    mutated = canonical._propose_slot(
        slot,
        {"problem_statement": "problem"},
        {},
        max_tokens=10,
        timeout_s=1,
        continue_rounds=0,
        extra_instruction="EXECUTE THIS GENE",
    )

    assert prompts == ["BASE", "EXECUTE THIS GENE\n\nBASE"]
    control_receipt = control["execution_input_receipt"]
    mutated_receipt = mutated["execution_input_receipt"]
    assert control_receipt["mutation_gene_applied"] is False
    assert control_receipt["executed_prompt_digest"] == control_receipt[
        "counterfactual_prompt_digest"
    ]
    assert mutated_receipt["mutation_gene_applied"] is True
    assert mutated_receipt["mutation_gene_digest"]
    assert mutated_receipt["counterfactual_prompt_digest"] == control_receipt[
        "counterfactual_prompt_digest"
    ]
    assert mutated_receipt["executed_prompt_digest"] != mutated_receipt[
        "counterfactual_prompt_digest"
    ]


def test_verify_chain_calls_verifier_for_empty_generator_without_laundering_arm(
    monkeypatch,
) -> None:
    calls: list[dict] = []
    generator = SimpleNamespace(
        model_id="generator",
        provider=SimpleNamespace(value="test"),
    )
    verifier = SimpleNamespace(
        model_id="verifier",
        provider=SimpleNamespace(value="test"),
    )

    def propose(slot, _inst, _ctx, **kwargs):
        calls.append({"model": slot.model_id, **kwargs})
        return {
            "patch": "" if slot is generator else "verifier-only patch",
            "tokens": 2,
            "execution_input_receipt": {
                "schema": "rsi_lab.execution_input_receipt.v1",
                "mutation_gene_applied": bool(kwargs.get("extra_instruction")),
            },
        }

    monkeypatch.setattr(arms, "_propose_slot", propose)
    result = arms.verify_chain_arm(
        generator,
        verifier,
        {},
        {},
        Budget(cap_tokens=100, cap_usd=1.0),
        per_call_tokens=10,
        timeout_s=1,
        extra_instruction="EXECUTE THIS GENE",
    )

    assert [call["model"] for call in calls] == ["generator", "verifier"]
    assert calls[0]["extra_instruction"] == "EXECUTE THIS GENE"
    assert "<EMPTY_PATCH>" in calls[1]["extra_instruction"]
    assert result["final_patch"] == ""
    evidence = result["execution_evidence"]
    assert evidence["generator_empty_patch"] is True
    assert evidence["verifier_called"] is True
    assert evidence["verifier_empty_patch"] is False
    assert evidence["final_patch_empty"] is True


def test_kimi_code_alias_uses_window_and_temperature_wall_repairs() -> None:
    assert "kimi-code" in WINDOW_MODELS
    assert "kimi-code" in KIMI_TEMP1


def test_provenance_split_and_contamination_are_explicit() -> None:
    explore, confirm = split_explore_confirm(["a", "b", "c", "d", "e"], 3)
    assert explore == ["a", "b", "c"]
    assert confirm == ["d", "e"]

    state = contamination_state({"created_at": "2022-01-25T10:37:44Z"})
    assert state["state"] == "possible_pretrain"
    assert "post-cutoff" in state["strong_control_todo"]


def test_stats_are_paired_and_fdr_ready() -> None:
    ci = paired_bootstrap_ci([1.0, 0.0, -1.0], samples=100, seed=1)
    assert ci["n"] == 3
    assert ci["lower"] <= ci["mean"] <= ci["upper"]

    sig = benjamini_hochberg([0.001, 0.2, 0.02], alpha=0.05)
    assert sig == [True, False, True]

    var = replicate_variance([1.0, 0.0, 1.0])
    assert var["n"] == 3
    assert var["var"] > 0


def test_positive_claim_gate_requires_confirm_split() -> None:
    overall = {"n": 4, "mean": 1.0, "lower": 1.0}
    explore_only = {"explore": {"n": 4, "mean": 1.0, "lower": 1.0}, "confirm": {"n": 0}}

    assert positive_claim_gate(overall, explore_only) is False
    assert positive_claim_gate(overall, {"confirm": {"n": 2, "mean": 1.0, "lower": 1.0}}) is True


def test_pick_generator_verifier_handles_empty_and_same_family_rosters() -> None:
    assert _pick_generator_verifier([]) == (None, None)

    gen, ver = _pick_generator_verifier(
        [Slot("glm-5.2"), Slot("glm-4.6")],
        gen_id="glm-5.2",
        ver_id="glm-4.6",
    )

    assert gen is not None
    assert gen.model_id == "glm-5.2"
    assert ver is None


def test_receipt_ledger_writes_attempt_rows_with_required_fields(tmp_path: Path) -> None:
    receipt = AttemptReceipt(
        task_id="task-1",
        mission_class="verifier_role",
        split="explore",
        arm="verify_chain",
        class_null="self_moa",
        replicate=0,
        generator="glm-5.2",
        verifier="moonshotai/kimi-k2.6",
        selection_reasons="cross-family verifier",
        scaffold_parity_hash=scaffold_parity_hash("a", "b"),
        contamination_state={"state": "possible_pretrain"},
        budget=Budget(cap_tokens=100, cap_usd=1.0).to_dict(),
        resolved=False,
        grade_seconds=0.0,
    )

    path = tmp_path / "ledger.jsonl"
    row_id = Ledger(path).append(receipt)
    row = json.loads(path.read_text(encoding="utf-8"))

    assert row["_row_id"] == row_id
    assert row["class_null"] == "self_moa"
    assert row["contamination_state"]["state"] == "possible_pretrain"
    assert row["scaffold_parity_hash"]


def test_closeout_state_contract_is_finite() -> None:
    assert set(CLOSEOUT_STATES) == {
        "positive_lift_candidate",
        "measured_negative",
        "invalid_budget",
        "contaminated_quarantine",
        "inconclusive_low_power",
        "blocked_with_evidence",
    }
