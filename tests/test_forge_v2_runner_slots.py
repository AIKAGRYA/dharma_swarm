import asyncio
from types import SimpleNamespace

from dharma_swarm.forge_v1.forge_v2 import runner_slots
from dharma_swarm.forge_v1.forge_v2.runner_slots import (
    _probe_with_receipt,
    _resolve_high_slot_pair,
    _slot_for_id,
)
from dharma_swarm.models import LLMResponse, ProviderType


def test_slot_for_id_routes_moonshot_prefix_to_moonshot_provider():
    slot = _slot_for_id("moonshot:kimi-k2.7-code")

    assert slot is not None
    assert slot.provider == ProviderType.MOONSHOT
    assert slot.model_id == "kimi-k2.7-code"
    assert slot.tier == "frontier"


class _ProbeProvider:
    def __init__(self, served_model: str, *, content: str = "OK", delay_s: float = 0):
        self.served_model = served_model
        self.content = content
        self.delay_s = delay_s
        self.complete_loop = None
        self.close_loop = None
        self.close_count = 0

    async def complete(self, _request):
        self.complete_loop = asyncio.get_running_loop()
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        return LLMResponse(content=self.content, model=self.served_model)

    async def close(self):
        self.close_loop = asyncio.get_running_loop()
        self.close_count += 1


def _slot(model_id: str):
    return SimpleNamespace(model_id=model_id, provider=ProviderType.OLLAMA, tier="strong")


def test_probe_attests_exact_served_model_and_closes_on_same_loop(monkeypatch):
    provider = _ProbeProvider("kimi-k2.7-code")
    monkeypatch.setattr(
        runner_slots,
        "_provider_for_slot",
        lambda slot, timeout_s: (provider, slot.model_id),
    )

    receipt = _probe_with_receipt(_slot("kimi-k2.7-code:cloud"), timeout_s=1)

    assert receipt["outcome"] == "callable"
    assert receipt["callable"] is True
    assert receipt["served_model"] == "kimi-k2.7-code"
    assert receipt["served_family"] == "kimi"
    assert provider.close_count == 1
    assert provider.complete_loop is provider.close_loop


def test_probe_rejects_cross_family_fallback(monkeypatch):
    provider = _ProbeProvider("kimi-k2.7-code")
    monkeypatch.setattr(
        runner_slots,
        "_provider_for_slot",
        lambda slot, timeout_s: (provider, slot.model_id),
    )

    receipt = _probe_with_receipt(_slot("deepseek-v4-pro:cloud"), timeout_s=1)

    assert receipt["callable"] is False
    assert receipt["stage"] == "response"
    assert receipt["error_type"] == "served_model_mismatch"
    assert receipt["requested_family"] == "deepseek"
    assert receipt["served_family"] == "kimi"


def test_probe_classifies_config_failure(monkeypatch):
    def fail_config(slot, timeout_s):
        raise RuntimeError("secret detail must not enter the receipt")

    monkeypatch.setattr(runner_slots, "_provider_for_slot", fail_config)

    receipt = _probe_with_receipt(_slot("glm-5.2"), timeout_s=1)

    assert receipt["callable"] is False
    assert receipt["stage"] == "config"
    assert receipt["error_type"] == "RuntimeError"
    assert "detail" not in receipt


def test_probe_closes_provider_on_timeout(monkeypatch):
    provider = _ProbeProvider("kimi-k2.7-code", delay_s=0.1)
    monkeypatch.setattr(
        runner_slots,
        "_provider_for_slot",
        lambda slot, timeout_s: (provider, slot.model_id),
    )

    receipt = _probe_with_receipt(_slot("kimi-k2.7-code:cloud"), timeout_s=0.01)

    assert receipt["callable"] is False
    assert receipt["stage"] == "timeout"
    assert provider.close_count == 1
    assert provider.complete_loop is provider.close_loop


def test_high_slot_pair_requires_two_attested_served_families(monkeypatch):
    candidates = ["kimi-k2.7-code:cloud", "deepseek-v4-pro:cloud"]
    providers = {
        model_id: _ProbeProvider(model_id.removesuffix(":cloud"))
        for model_id in candidates
    }
    monkeypatch.setattr(runner_slots, "_high_slot_candidate_ids", lambda *ids: candidates)
    monkeypatch.setattr(runner_slots, "_slot_for_id", _slot)
    monkeypatch.setattr(runner_slots, "_is_high_slot_model_id", lambda model_id: True)
    monkeypatch.setattr(
        runner_slots,
        "_provider_for_slot",
        lambda slot, timeout_s: (providers[slot.model_id], slot.model_id),
    )

    gen, ver, callable_slots, rows = _resolve_high_slot_pair(None, None, timeout_s=1)

    assert gen.model_id == "kimi-k2.7-code:cloud"
    assert ver.model_id == "deepseek-v4-pro:cloud"
    assert [slot.model_id for slot in callable_slots] == candidates
    assert [row["served_family"] for row in rows] == ["kimi", "deepseek"]


def test_high_slot_pair_stays_blocked_when_nominal_families_share_served_model(monkeypatch):
    candidates = ["kimi-k2.7-code:cloud", "deepseek-v4-pro:cloud"]
    providers = {
        candidates[0]: _ProbeProvider("kimi-k2.7-code"),
        candidates[1]: _ProbeProvider("kimi-k2.7-code"),
    }
    monkeypatch.setattr(runner_slots, "_high_slot_candidate_ids", lambda *ids: candidates)
    monkeypatch.setattr(runner_slots, "_slot_for_id", _slot)
    monkeypatch.setattr(runner_slots, "_is_high_slot_model_id", lambda model_id: True)
    monkeypatch.setattr(
        runner_slots,
        "_provider_for_slot",
        lambda slot, timeout_s: (providers[slot.model_id], slot.model_id),
    )

    gen, ver, callable_slots, rows = _resolve_high_slot_pair(None, None, timeout_s=1)

    assert gen.model_id == "kimi-k2.7-code:cloud"
    assert ver is None
    assert [slot.model_id for slot in callable_slots] == [candidates[0]]
    assert rows[1]["error_type"] == "served_model_mismatch"


def test_high_slot_pair_records_typed_unresolved_route(monkeypatch):
    monkeypatch.setattr(runner_slots, "_high_slot_candidate_ids", lambda *ids: ["unknown-model"])
    monkeypatch.setattr(runner_slots, "_slot_for_id", lambda model_id: None)

    gen, ver, callable_slots, rows = _resolve_high_slot_pair(None, None, timeout_s=1)

    assert gen is None
    assert ver is None
    assert callable_slots == []
    assert rows[0]["outcome"] == "unavailable"
    assert rows[0]["stage"] == "config"
    assert rows[0]["error_type"] == "unresolved_model_id"
