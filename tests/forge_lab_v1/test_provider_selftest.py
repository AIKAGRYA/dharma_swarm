from __future__ import annotations

from types import SimpleNamespace

from dharma_swarm.forge_lab import provider_selftest
from dharma_swarm.models import ProviderType


def _slot(model_id: str, provider: ProviderType = ProviderType.OLLAMA) -> SimpleNamespace:
    return SimpleNamespace(model_id=model_id, provider=provider, tier="frontier")


def test_provider_selftest_config_mode_resolves_without_live_probe(monkeypatch):
    monkeypatch.setattr(provider_selftest, "profile_model_ids", lambda profile, current_model=None: ["glm-5.2", "kimi-code"])
    from dharma_swarm.forge_v1.forge_v2 import runner_slots

    monkeypatch.setattr(runner_slots, "_slot_for_id", lambda model_id: _slot(model_id))

    payload = provider_selftest.run_provider_selftest(
        profile="frontier",
        live=False,
        require_independent_routes=None,
    )

    assert payload["schema"] == "rsi_lab.provider_selftest.v1"
    assert payload["ok"] is True
    assert payload["live"] is False
    assert [row["slot_resolved"] for row in payload["rows"]] == [True, True]
    assert [row["outcome"] for row in payload["rows"]] == ["not_probed", "not_probed"]


def test_provider_selftest_requires_live_for_independent_route_claim(monkeypatch):
    monkeypatch.setattr(provider_selftest, "profile_model_ids", lambda profile, current_model=None: ["glm-5.2"])
    from dharma_swarm.forge_v1.forge_v2 import runner_slots

    monkeypatch.setattr(runner_slots, "_slot_for_id", lambda model_id: _slot(model_id))

    payload = provider_selftest.run_provider_selftest(
        profile="frontier",
        live=False,
        require_independent_routes=2,
    )

    assert payload["ok"] is False
    assert payload["failures"] == ["live_probe_required_for_independent_routes"]


def test_provider_selftest_live_counts_attested_independent_families(monkeypatch, tmp_path):
    monkeypatch.setenv("RSI_LAB_PROVIDER_SELFTEST_ROOT", str(tmp_path))
    monkeypatch.setattr(provider_selftest, "profile_model_ids", lambda profile, current_model=None: ["glm-5.2", "kimi-code", "deepseek-v4-pro"])
    from dharma_swarm.forge_v1.forge_v2 import runner_slots

    monkeypatch.setattr(runner_slots, "_slot_for_id", lambda model_id: _slot(model_id))

    def fake_probe(slot, timeout_s):
        family = provider_selftest._family(slot.model_id)
        return {
            "outcome": "callable",
            "callable": True,
            "requested_model": slot.model_id,
            "requested_family": family,
            "served_model": slot.model_id,
            "served_family": family,
            "stage": "complete",
            "latency_ms": 1,
        }

    monkeypatch.setattr(runner_slots, "_probe_with_receipt", fake_probe)

    payload = provider_selftest.run_provider_selftest(
        profile="frontier",
        live=True,
        require_independent_routes=2,
    )

    assert payload["ok"] is True
    assert payload["independent_route_count"] == 2
    assert payload["probed_models"] == ["glm-5.2", "kimi-code"]
    assert payload["receipt"]
    assert tmp_path.joinpath(payload["receipt"]).exists() or payload["receipt"].startswith(str(tmp_path))
