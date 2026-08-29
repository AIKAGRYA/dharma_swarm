"""Tests for the real proposer — prompt -> diff -> verified-to-apply, hermetic."""

from __future__ import annotations

from pathlib import Path

from dharma_swarm.foundry import real_proposer as proposer_module
from dharma_swarm.foundry.army import ArmyModel
from dharma_swarm.foundry.live import ProviderCallError, ProviderPool
from dharma_swarm.foundry.real_proposer import (
    check_applies,
    extract_unified_diff,
    real_proposer,
)
from dharma_swarm.foundry.tripwires import scan_tripwires

MODEL = ArmyModel("test-model", "mass", "test", free=True)

GOOD_DIFF = (
    "--- a/prog.py\n+++ b/prog.py\n@@ -1 +1 @@\n-VALUE = 1.0\n+VALUE = 2.0\n"
)


def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "pinned"
    root.mkdir()
    (root / "prog.py").write_text("VALUE = 1.0\n", encoding="utf-8")
    return root


def test_extract_fenced_diff():
    reply = f"Here's my improvement:\n```diff\n{GOOD_DIFF}```\nHope it helps!"
    assert extract_unified_diff(reply).startswith("--- a/prog.py")


def test_extract_bare_diff_and_prose_trimmed():
    reply = f"I suggest the following change.\n{GOOD_DIFF}"
    extracted = extract_unified_diff(reply)
    assert extracted.startswith("--- a/prog.py")
    assert "I suggest" not in extracted


def test_extract_no_diff_returns_empty():
    assert extract_unified_diff("I cannot produce a diff, sorry.") == ""


def test_proposer_returns_applying_candidate(tmp_path):
    root = _tree(tmp_path)
    propose = real_proposer(
        target_id="t", pinned_root=root, evolve_file="prog.py",
        objective="maximize VALUE",
        caller=lambda model, prompt: f"```diff\n{GOOD_DIFF}```",
    )
    cand = propose(MODEL, None, 7)
    assert cand.diff.startswith("--- a/prog.py")
    assert check_applies(root, cand.diff) is None
    assert cand.origin_model == "test-model"
    assert cand.candidate_id.startswith("cand-")
    assert len(cand.candidate_id) == len("cand-") + 64
    assert cand.metadata["applied_source"] == "VALUE = 2.0\n"


def test_proposer_retries_with_feedback_then_fails_safe(tmp_path):
    root = _tree(tmp_path)
    prompts: list[str] = []

    def bad_caller(model, prompt):
        prompts.append(prompt)
        return "no diff here at all"

    propose = real_proposer(
        target_id="t", pinned_root=root, evolve_file="prog.py",
        objective="maximize VALUE", caller=bad_caller,
    )
    cand = propose(MODEL, None, 1)
    assert len(prompts) == 2  # one retry
    assert "FAILED TO APPLY" in prompts[1]
    assert cand.diff == ""
    assert cand.metadata.get("proposer_failed")
    assert "extraction_failure" in scan_tripwires(
        cand, allowed_paths=["prog.py"]
    ).fired


def test_proposer_survives_dead_lane(tmp_path):
    root = _tree(tmp_path)

    def dead_caller(model, prompt):
        raise ConnectionError("lane down")

    propose = real_proposer(
        target_id="t", pinned_root=root, evolve_file="prog.py",
        objective="maximize VALUE", caller=dead_caller,
    )
    cand = propose(MODEL, None, 2)
    assert cand.diff == ""
    assert cand.metadata["proposal_status"] == "provider_error"
    assert cand.metadata["provider_error"] == "network"
    assert cand.metadata["budget_chargeable"] is True
    assert cand.metadata["billable_tokens"] > proposer_module.PROPOSAL_MAX_TOKENS
    attempt = cand.metadata["provider_attempts"][0]
    assert attempt["liability_tokens"] == cand.metadata["billable_tokens"]
    assert attempt["prompt_bytes"] > 0
    assert attempt["usage_basis"] == "conservative_total_liability"
    fired = scan_tripwires(cand, allowed_paths=["prog.py"]).fired
    assert "provider_error" in fired
    assert "no_op_diff" not in fired


def test_stale_context_diff_fails_apply_check(tmp_path):
    root = _tree(tmp_path)
    stale = (
        "--- a/prog.py\n+++ b/prog.py\n@@ -1 +1 @@\n-VALUE = 999.0\n+VALUE = 2.0\n"
    )
    assert check_applies(root, stale) is not None


def test_successful_failover_accounts_tokens_on_every_attempt(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    attempts = {"n": 0}

    def routed(route, model, prompt, **kwargs):  # noqa: ARG001
        attempts["n"] += 1
        if route.name == "zhipu":
            raise ProviderCallError(
                "zhipu", "timeout", retryable=True, billable_tokens=100
            )
        return f"```diff\n{GOOD_DIFF}```", 200

    pool = ProviderPool(
        env={"ZHIPU_API_KEY": "z", "OPENROUTER_API_KEY": "o"},
        chat_caller=routed,
        model_lister=lambda route: [],
    )
    monkeypatch.setattr(proposer_module, "ProviderPool", lambda **kwargs: pool)
    propose = real_proposer(
        target_id="t",
        pinned_root=root,
        evolve_file="prog.py",
        objective="maximize VALUE",
        env={"ZHIPU_API_KEY": "z", "OPENROUTER_API_KEY": "o"},
    )
    candidate = propose(MODEL, None, 9)
    assert candidate.metadata["provider"] == "openrouter"
    assert propose.usage["tokens"] == 400
    assert propose.usage["tokens_by_provider"] == {"zhipu": 200, "openrouter": 200}
    assert [attempt["category"] for attempt in candidate.metadata["provider_attempts"]] == [
        "timeout", "timeout", "ok",
    ]
