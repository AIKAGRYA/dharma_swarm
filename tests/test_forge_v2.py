from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.forge_v1.forge_v2 import CLOSEOUT_STATES
from dharma_swarm.forge_v1.forge_v2 import arms
from dharma_swarm.forge_v1.forge_v2.arms import _win, mixed_moa_arm
from dharma_swarm.forge_v1.forge_v2.budget import Budget
from dharma_swarm.forge_v1.forge_v2.provenance import (
    aggregate_contamination_states,
    contamination_state,
    split_explore_confirm,
)
from dharma_swarm.forge_v1.forge_v2.receipts import AttemptReceipt, Ledger, RunReceipt, scaffold_parity_hash
from dharma_swarm.forge_v1.forge_v2.stats import (
    benjamini_hochberg,
    paired_bootstrap_ci,
    positive_claim_gate,
    replicate_variance,
)


@dataclass(frozen=True)
class Slot:
    model_id: str
    provider: str = "test"


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


def test_mixed_moa_charges_generation_and_selection_without_oracle(monkeypatch) -> None:
    calls = []

    def fake_propose(slot, inst, ctx, *, max_tokens, timeout_s, window_chars, extra_instruction=None):
        calls.append((slot.model_id, extra_instruction))
        return {"patch": f"patch from {slot.model_id}", "tokens": 10}

    monkeypatch.setattr(arms, "_propose_slot", fake_propose)
    budget = Budget(cap_tokens=100, cap_usd=1.0)
    result = mixed_moa_arm(
        [Slot("glm-5.2"), Slot("moonshotai/kimi-k2.6")],
        Slot("glm-5.2"),
        {"instance_id": "x"},
        {},
        budget,
        per_call_tokens=16,
        timeout_s=1,
    )

    assert result["arm"] == "mixed_moa"
    assert result["models"] == ["glm-5.2", "moonshotai/kimi-k2.6"]
    assert budget.components["generation"] == 20
    assert budget.components["selection"] == 10
    assert len(calls) == 3


def test_provenance_split_and_contamination_are_explicit() -> None:
    explore, confirm = split_explore_confirm(["a", "b", "c", "d", "e"], 3)
    assert explore == ["a", "b", "c"]
    assert confirm == ["d", "e"]

    state = contamination_state({"created_at": "2022-01-25T10:37:44Z"})
    assert state["state"] == "possible_pretrain"
    assert "post-cutoff" in state["strong_control_todo"]

    aggregate = aggregate_contamination_states({"task-a": state})
    assert aggregate["state"] == "possible_pretrain"
    assert aggregate["task_count"] == 1
    assert aggregate["task_states"]["task-a"]["created_at"] == "2022-01-25T10:37:44Z"


def test_stats_are_paired_and_fdr_ready() -> None:
    ci = paired_bootstrap_ci([1.0, 0.0, -1.0], samples=100, seed=1)
    assert ci["n"] == 3
    assert ci["lower"] <= ci["mean"] <= ci["upper"]

    sig = benjamini_hochberg([0.001, 0.2, 0.02], alpha=0.05)
    assert sig == [True, False, True]

    var = replicate_variance([1.0, 0.0, 1.0])
    assert var["n"] == 3
    assert var["var"] > 0


def test_positive_claim_gate_requires_confirmed_ci() -> None:
    overall = {"n": 20, "mean": 0.2, "lower": 0.1, "upper": 0.3}
    confirmed = {"confirm": {"n": 10, "mean": 0.2, "lower": 0.1, "upper": 0.3}}
    explore_only = {"explore": {"n": 10, "mean": 0.4, "lower": 0.2, "upper": 0.6}}
    weak_confirm = {"confirm": {"n": 10, "mean": 0.2, "lower": 0.0, "upper": 0.4}}

    assert positive_claim_gate(overall, confirmed) is True
    assert positive_claim_gate(overall, explore_only) is False
    assert positive_claim_gate(overall, weak_confirm) is False


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


def test_run_ledger_row_contains_its_own_row_id(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path)
    row_id = ledger.append(RunReceipt(mission_class="verifier_role", closeout="inconclusive_low_power"))
    row = json.loads(path.read_text(encoding="utf-8"))

    assert row["_row_id"] == row_id
    assert row["ledger_row_ids"] == [row_id]


def test_closeout_state_contract_is_finite() -> None:
    assert set(CLOSEOUT_STATES) == {
        "positive_lift_candidate",
        "measured_negative",
        "invalid_budget",
        "contaminated_quarantine",
        "inconclusive_low_power",
        "blocked_with_evidence",
    }
