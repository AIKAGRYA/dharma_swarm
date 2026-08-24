from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from dharma_swarm.forge_lab import provider_selftest
from dharma_swarm.forge_lab.newrun import (
    DEFAULT_DIVERSE_MUTATOR,
    DEFAULT_DIVERSE_SOLVER,
    DEFAULT_DIVERSE_VERIFIER,
)
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

    assert payload["schema"] == "rsi_lab.provider_selftest.v2"
    assert payload["ok"] is False
    assert payload["live"] is False
    assert [row["slot_resolved"] for row in payload["rows"]] == [True, True]
    assert [row["outcome"] for row in payload["rows"]] == ["not_probed", "not_probed"]
    assert payload["callable_count"] == 0
    assert payload["failures"] == ["config_only_no_callable_route_attestation"]


def test_diverse_profile_defaults_are_slot_resolvable_in_config_mode():
    payload = provider_selftest.run_provider_selftest(profile="newrun", live=False)

    rows = {row["model_id"]: row for row in payload["rows"]}
    for model_id in (
        DEFAULT_DIVERSE_SOLVER,
        DEFAULT_DIVERSE_VERIFIER,
        DEFAULT_DIVERSE_MUTATOR,
    ):
        assert rows[model_id]["slot_resolved"] is True
        assert "error_type" not in rows[model_id]


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
    assert "config_only_no_callable_route_attestation" in payload["failures"]
    assert "live_probe_required_for_independent_routes" in payload["failures"]


def test_provider_selftest_live_counts_attested_independent_families(monkeypatch, tmp_path):
    monkeypatch.setenv("RSI_LAB_PROVIDER_SELFTEST_ROOT", str(tmp_path))
    monkeypatch.setattr(provider_selftest, "profile_model_ids", lambda profile, current_model=None: ["glm-5.2", "kimi-code", "deepseek-v4-pro"])
    from dharma_swarm.forge_v1.forge_v2 import runner_slots

    providers = {
        "glm-5.2": ProviderType.OLLAMA,
        "kimi-code": ProviderType.KIMI_CODE,
        "deepseek-v4-pro": ProviderType.OPENROUTER,
    }
    monkeypatch.setattr(
        runner_slots,
        "_slot_for_id",
        lambda model_id: _slot(model_id, providers[model_id]),
    )

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
    assert payload["independent_routes"] == ["kimi_code", "ollama"]
    assert payload["receipt"]
    assert tmp_path.joinpath(payload["receipt"]).exists() or payload["receipt"].startswith(str(tmp_path))


def test_different_model_families_on_one_provider_are_not_independent_routes(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("RSI_LAB_PROVIDER_SELFTEST_ROOT", str(tmp_path))
    monkeypatch.setattr(
        provider_selftest,
        "profile_model_ids",
        lambda profile, current_model=None: ["glm-5.2", "kimi-code"],
    )
    from dharma_swarm.forge_v1.forge_v2 import runner_slots

    monkeypatch.setattr(
        runner_slots,
        "_slot_for_id",
        lambda model_id: _slot(model_id, ProviderType.OLLAMA),
    )
    monkeypatch.setattr(
        runner_slots,
        "_probe_with_receipt",
        lambda slot, timeout_s: {
            "outcome": "callable",
            "callable": True,
            "requested_model": slot.model_id,
            "requested_family": provider_selftest._family(slot.model_id),
            "served_model": slot.model_id,
            "served_family": provider_selftest._family(slot.model_id),
            "stage": "complete",
            "latency_ms": 1,
        },
    )

    payload = provider_selftest.run_provider_selftest(
        profile="frontier",
        live=True,
        require_independent_routes=2,
    )

    assert payload["ok"] is False
    assert payload["independent_route_count"] == 1
    assert payload["independent_families"] == ["glm", "kimi"]
    assert "independent_routes:1/2" in payload["failures"]


def test_empty_staged_profile_and_zero_callable_routes_never_report_ok(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("RSI_LAB_PROVIDER_SELFTEST_ROOT", str(tmp_path))
    monkeypatch.delenv("RSI_LAB_STAGED_MODELS", raising=False)
    payload = provider_selftest.run_provider_selftest(
        profile="staged",
        live=True,
        require_independent_routes=2,
    )
    assert payload["ok"] is False
    assert payload["callable_count"] == 0
    assert payload["rows"] == []
    assert "zero_profile_targets" in payload["failures"]
    assert "zero_callable_routes" in payload["failures"]


def test_versioned_refresh_model_names_resolve_to_two_provider_entitlements(monkeypatch):
    monkeypatch.setenv(
        "RSI_LAB_STAGED_MODELS",
        "moonshot:kimi-k2.7-code,glm-5.2",
    )
    payload = provider_selftest.run_provider_selftest(profile="staged", live=False)
    assert payload["ok"] is False
    assert payload["requested_models"] == ["moonshot:kimi-k2.7-code", "glm-5.2"]
    assert [row["slot_resolved"] for row in payload["rows"]] == [True, True]
    assert {row["provider"] for row in payload["rows"]} == {"moonshot", "zhipu"}


def test_live_receipt_and_payload_never_record_secret_values(monkeypatch, tmp_path):
    secret = "bearer-value-that-must-not-appear"
    monkeypatch.setenv("RSI_LAB_PROVIDER_SELFTEST_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    monkeypatch.setattr(
        provider_selftest,
        "profile_model_ids",
        lambda profile, current_model=None: ["deepseek-v4-pro"],
    )
    from dharma_swarm.forge_v1.forge_v2 import runner_slots

    monkeypatch.setattr(
        runner_slots,
        "_slot_for_id",
        lambda model_id: _slot(model_id, ProviderType.OPENROUTER),
    )
    monkeypatch.setattr(
        runner_slots,
        "_probe_with_receipt",
        lambda slot, timeout_s: {
            "outcome": "callable",
            "callable": True,
            "requested_model": slot.model_id,
            "requested_family": "deepseek",
            "served_model": slot.model_id,
            "served_family": "deepseek",
            "stage": "complete",
            "latency_ms": 1,
        },
    )

    payload = provider_selftest.run_provider_selftest(
        profile="frontier",
        live=True,
        require_independent_routes=1,
    )

    rendered = json.dumps(payload)
    rendered += Path(payload["receipt"]).read_text(encoding="utf-8")
    assert payload["ok"] is True
    assert secret not in rendered
    assert "Authorization" not in rendered


def test_refresh_interval_reuses_receipt_without_a_second_probe(monkeypatch, tmp_path):
    monkeypatch.setenv("RSI_LAB_PROVIDER_SELFTEST_ROOT", str(tmp_path))
    monkeypatch.setattr(
        provider_selftest,
        "profile_model_ids",
        lambda profile, current_model=None: ["glm-5.2"],
    )
    from dharma_swarm.forge_v1.forge_v2 import runner_slots

    monkeypatch.setattr(
        runner_slots,
        "_slot_for_id",
        lambda model_id: _slot(model_id, ProviderType.ZHIPU),
    )
    calls = 0

    def probe(slot, timeout_s):
        nonlocal calls
        calls += 1
        return {
            "outcome": "callable",
            "callable": True,
            "requested_model": slot.model_id,
            "requested_family": "glm",
            "served_model": slot.model_id,
            "served_family": "glm",
            "stage": "complete",
            "latency_ms": 1,
        }

    monkeypatch.setattr(runner_slots, "_probe_with_receipt", probe)
    first = provider_selftest.run_provider_selftest(
        profile="frontier",
        live=True,
        require_independent_routes=1,
        min_refresh_interval_s=3600,
    )
    second = provider_selftest.run_provider_selftest(
        profile="frontier",
        live=True,
        require_independent_routes=1,
        min_refresh_interval_s=3600,
    )

    assert first["ok"] is True
    assert second["ok"] is True
    assert second["cached"] is True
    assert second["refresh_skipped"] == "minimum_refresh_interval"
    assert calls == 1


def test_live_receipts_are_unique_append_only_and_policy_bound(monkeypatch, tmp_path):
    monkeypatch.setenv("RSI_LAB_PROVIDER_SELFTEST_ROOT", str(tmp_path))
    monkeypatch.setattr(
        provider_selftest,
        "profile_model_ids",
        lambda profile, current_model=None: ["glm-5.2"],
    )
    from dharma_swarm.forge_v1.forge_v2 import runner_slots

    monkeypatch.setattr(
        runner_slots,
        "_slot_for_id",
        lambda model_id: _slot(model_id, ProviderType.ZHIPU),
    )
    calls = 0

    def probe(slot, timeout_s):
        nonlocal calls
        calls += 1
        return {
            "outcome": "callable",
            "callable": True,
            "requested_model": slot.model_id,
            "requested_family": "glm",
            "served_model": slot.model_id,
            "served_family": "glm",
            "stage": "complete",
            "latency_ms": 1,
        }

    monkeypatch.setattr(runner_slots, "_probe_with_receipt", probe)
    first = provider_selftest.run_provider_selftest(
        profile="frontier",
        live=True,
        require_independent_routes=1,
        timeout_s=20,
        max_probes=1,
    )
    second = provider_selftest.run_provider_selftest(
        profile="frontier",
        live=True,
        require_independent_routes=1,
        timeout_s=21,
        max_probes=1,
    )

    assert calls == 2
    assert first["receipt"] != second["receipt"]
    assert first["receipt_id"] != second["receipt_id"]
    assert first["policy_digest"] != second["policy_digest"]
    assert Path(first["receipt"]).exists()
    assert Path(second["receipt"]).exists()
    assert provider_selftest.validate_provider_receipt(
        json.loads(Path(first["receipt"]).read_text(encoding="utf-8")),
        path=Path(first["receipt"]),
    ) == []


def test_cache_reuse_requires_exact_source_config_and_probe_policy(monkeypatch, tmp_path):
    monkeypatch.setenv("RSI_LAB_PROVIDER_SELFTEST_ROOT", str(tmp_path))
    monkeypatch.setattr(
        provider_selftest,
        "profile_model_ids",
        lambda profile, current_model=None: ["glm-5.2"],
    )
    from dharma_swarm.forge_v1.forge_v2 import runner_slots

    monkeypatch.setattr(
        runner_slots,
        "_slot_for_id",
        lambda model_id: _slot(model_id, ProviderType.ZHIPU),
    )
    calls = 0

    def probe(slot, timeout_s):
        nonlocal calls
        calls += 1
        return {
            "outcome": "callable",
            "callable": True,
            "requested_model": slot.model_id,
            "requested_family": "glm",
            "served_model": slot.model_id,
            "served_family": "glm",
            "stage": "complete",
            "latency_ms": 1,
        }

    monkeypatch.setattr(runner_slots, "_probe_with_receipt", probe)
    provider_selftest.run_provider_selftest(
        profile="frontier",
        live=True,
        require_independent_routes=1,
        timeout_s=20,
        max_probes=1,
        min_refresh_interval_s=3600,
    )
    changed_policy = provider_selftest.run_provider_selftest(
        profile="frontier",
        live=True,
        require_independent_routes=1,
        timeout_s=21,
        max_probes=1,
        min_refresh_interval_s=3600,
    )
    assert calls == 2
    assert changed_policy["cached"] is False


def test_zhipu_declared_one_minor_successor_requires_bounded_confirmation(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("RSI_LAB_PROVIDER_SELFTEST_ROOT", str(tmp_path))
    monkeypatch.setattr(
        provider_selftest,
        "profile_model_ids",
        lambda profile, current_model=None: ["glm-5.2"],
    )
    from dharma_swarm.forge_v1.forge_v2 import runner_slots

    monkeypatch.setattr(
        runner_slots,
        "_slot_for_id",
        lambda model_id: _slot(model_id, ProviderType.ZHIPU),
    )

    def probe(slot, timeout_s):
        if slot.model_id == "glm-5.2":
            return {
                "outcome": "unavailable",
                "callable": False,
                "requested_model": "glm-5.2",
                "requested_family": "glm",
                "served_model": "glm-5.3",
                "served_family": "glm",
                "stage": "response",
                "error_type": "served_model_mismatch",
                "latency_ms": 1,
            }
        return {
            "outcome": "callable",
            "callable": True,
            "requested_model": "glm-5.3",
            "requested_family": "glm",
            "served_model": "glm-5.3",
            "served_family": "glm",
            "stage": "complete",
            "latency_ms": 1,
        }

    monkeypatch.setattr(runner_slots, "_probe_with_receipt", probe)
    payload = provider_selftest.run_provider_selftest(
        profile="frontier",
        live=True,
        require_independent_routes=1,
        max_probes=2,
    )
    row = payload["rows"][0]
    assert payload["ok"] is True
    assert payload["probe_call_count"] == 2
    assert row["outcome"] == "callable_authorized_successor_alias"
    assert row["identity_relation"] == "authorized_successor_alias"
    assert row["alias_policy"] == provider_selftest.ALIAS_POLICY_VERSION
    assert row["alias_confirmation"]["callable"] is True


def test_authorized_alias_cannot_bypass_probe_call_cap(monkeypatch, tmp_path):
    monkeypatch.setenv("RSI_LAB_PROVIDER_SELFTEST_ROOT", str(tmp_path))
    monkeypatch.setattr(
        provider_selftest,
        "profile_model_ids",
        lambda profile, current_model=None: ["glm-5.2"],
    )
    from dharma_swarm.forge_v1.forge_v2 import runner_slots

    monkeypatch.setattr(
        runner_slots,
        "_slot_for_id",
        lambda model_id: _slot(model_id, ProviderType.ZHIPU),
    )
    monkeypatch.setattr(
        runner_slots,
        "_probe_with_receipt",
        lambda slot, timeout_s: {
            "outcome": "unavailable",
            "callable": False,
            "requested_model": "glm-5.2",
            "requested_family": "glm",
            "served_model": "glm-5.3",
            "served_family": "glm",
            "stage": "response",
            "error_type": "served_model_mismatch",
            "latency_ms": 1,
        },
    )
    payload = provider_selftest.run_provider_selftest(
        profile="frontier",
        live=True,
        require_independent_routes=1,
        max_probes=1,
    )
    assert payload["ok"] is False
    assert payload["probe_call_count"] == 1
    assert payload["rows"][0]["error_type"] == (
        "alias_confirmation_probe_budget_exhausted"
    )
