"""Critic run/skip unit tests (codex acceptance #4, the gap test_forge_v2.py leaves).

The critic 'run' path is exercised offline by monkeypatching the live model calls,
so majority-refute / minority-allow / cross-family-exclusion are all verified
without any network or Docker. The 'skip' path (critic only runs on a positive
interpretation) is the runner's gate; here we assert the predicate directly.
"""
from __future__ import annotations

import json
import types

from dharma_swarm.forge_v1.forge_v2 import critic


def _fake_slot(model_id, provider_value):
    return types.SimpleNamespace(model_id=model_id, provider=types.SimpleNamespace(value=provider_value))


def _patch(monkeypatch, slots, refute_seq):
    monkeypatch.setattr(critic, "pool_slots", lambda n, strategy="explore": slots)
    monkeypatch.setattr(critic, "_provider_for_slot", lambda s, timeout_s=90: (object(), s.model_id))
    seq = iter(refute_seq)
    monkeypatch.setattr(
        critic, "_call",
        lambda prov, wire, prompt, *, max_tokens, temperature, timeout_s:
            (json.dumps({"refuted": next(seq), "reason": "t"}), 1, "stop"),
    )


def test_majority_refute_kills_promotion(monkeypatch):
    slots = [_fake_slot("gemini-x", "google_ai"), _fake_slot("deepseek-x", "deepseek"),
             _fake_slot("minimax-x", "ollama")]
    _patch(monkeypatch, slots, [True, True, False])      # 2/3 refute
    v = critic.refute_pass("claim", {"ci": {}}, generator_family="glm", n=3)
    assert v["n_refuted"] == 2 and v["refuted_majority"] is True


def test_minority_refute_allows(monkeypatch):
    slots = [_fake_slot("gemini-x", "google_ai"), _fake_slot("deepseek-x", "deepseek"),
             _fake_slot("minimax-x", "ollama")]
    _patch(monkeypatch, slots, [False, False, True])     # 1/3 refute
    v = critic.refute_pass("claim", {"ci": {}}, generator_family="glm", n=3)
    assert v["n_refuted"] == 1 and v["refuted_majority"] is False


def test_no_cross_family_critic_is_conservative(monkeypatch):
    # every callable critic shares the generator family -> none eligible -> refute
    slots = [_fake_slot("glm-a", "zai"), _fake_slot("glm-b", "zai")]
    _patch(monkeypatch, slots, [False, False])
    v = critic.refute_pass("claim", {}, generator_family="glm", n=3)
    assert v["n_critics"] == 0 and v["refuted_majority"] is True


def test_unreachable_critic_defaults_to_refute(monkeypatch):
    slots = [_fake_slot("gemini-x", "google_ai")]
    monkeypatch.setattr(critic, "pool_slots", lambda n, strategy="explore": slots)

    def boom(s, timeout_s=90):
        raise RuntimeError("provider down")

    monkeypatch.setattr(critic, "_provider_for_slot", boom)
    v = critic.refute_pass("claim", {}, generator_family="glm", n=3)
    assert v["votes"][0]["refuted"] is True   # burden of proof on the swarm


def test_skip_gate_predicate():
    # the runner runs the critic ONLY on a positive interpretation (mean>0 and lower>0)
    def positive(ci):
        return ci["mean"] > 0 and ci["lower"] > 0
    assert positive({"mean": 0.3, "lower": 0.1}) is True
    assert positive({"mean": 0.0, "lower": 0.0}) is False   # null survived -> skip critic
    assert positive({"mean": 0.3, "lower": -0.1}) is False  # CI includes 0 -> skip
