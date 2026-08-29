from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dharma_swarm.forge_lab import provider_selftest
from dharma_swarm.models import LLMRequest, LLMResponse


def test_receipt_root_defaults_to_stable_state_anchor(monkeypatch, tmp_path):
    state = tmp_path / "state"
    monkeypatch.setenv("RSI_LAB_STATE", str(state))
    monkeypatch.delenv("DHARMA_HOME", raising=False)
    monkeypatch.delenv("RSI_LAB_PROVIDER_SELFTEST_ROOT", raising=False)
    assert provider_selftest._receipt_root() == (
        state / ".dharma" / "forge_lab" / "provider_selftests"
    ).resolve()


def test_config_mode_never_claims_callability(monkeypatch):
    monkeypatch.setattr(
        provider_selftest,
        "profile_model_ids",
        lambda profile, current_model=None: [
            "zhipu:glm-5.2",
            "ollama:glm-5.1:cloud",
        ],
    )
    payload = provider_selftest.run_provider_selftest(
        profile="staged", live=False, require_independent_routes=2
    )
    assert payload["schema"] == "rsi_lab.provider_selftest.v3"
    assert payload["ok"] is False
    assert payload["callable_count"] == 0
    assert payload["independent_route_count"] == 0
    assert {row["provider"] for row in payload["rows"]} == {"zhipu", "ollama"}
    assert "live_probe_required_for_independent_routes" in payload["failures"]


def _pricing(model: str) -> dict[str, object]:
    return {
        "pricing_id": f"fixture-{model}",
        "input_usd_per_token": 0.000001,
        "output_usd_per_token": 0.000002,
        "endpoint_policy_id": "fixture",
        "currency": "USD",
        "cached_input_discount_claimed": False,
        "model": model,
        "unattended_max_call_liability_usd": 0.04,
        "unattended_accounting_reservation_usd": 0.25,
        "unattended_budget_eligible": True,
    }


def _probe_receipt(slot, *, priced: bool = True) -> dict[str, object]:
    provider = str(getattr(slot.provider, "value", slot.provider))
    model = str(slot.model_id)
    usage = {"input_tokens": 8, "output_tokens": 2, "total_tokens": 10}
    pricing = _pricing(model) if priced else None
    return {
        "outcome": "callable",
        "callable": True,
        "requested_route_model": model,
        "requested_model": model,
        "requested_family": provider_selftest._family(model),
        "served_model": model,
        "served_family": provider_selftest._family(model),
        "wire_model": model,
        "route_to_wire_mapping": "identity",
        "endpoint_policy_id": provider_selftest._endpoint_policy_id(provider),
        "stage": "complete",
        "latency_ms": 1,
        "probe_calls": 1,
        "transport_requests_verified": 1,
        "retry_liability": "max_retries_zero_exactly_one_dispatch",
        "usage": usage,
        "usage_verified": True,
        "provider_usd_verified": 0.000012 if priced else None,
        "pricing": pricing,
        "pricing_verified": priced,
        "unattended_budget_eligible": priced,
        "reserved_usd": provider_selftest.PROBE_RESERVED_USD,
        "within_reserved_usd": True if priced else None,
        "usd_reservation_scope": (
            "pinned_public_tariff_bound"
            if priced
            else "internal_ledger_not_vendor_liability_cap"
        ),
        "vendor_liability_ceiling_usd": 0.001 if priced else None,
        "cost_basis": "fixture",
    }


def _live_fixture(monkeypatch, tmp_path, routes, *, priced=True):
    monkeypatch.setenv("RSI_LAB_PROVIDER_SELFTEST_ROOT", str(tmp_path))
    monkeypatch.setattr(
        provider_selftest,
        "profile_model_ids",
        lambda profile, current_model=None: list(routes),
    )

    def probe(slot, timeout_s):
        del timeout_s
        is_priced = priced(slot) if callable(priced) else bool(priced)
        return _probe_receipt(slot, priced=is_priced)

    monkeypatch.setattr(provider_selftest, "_probe_route_with_receipt", probe)

    def pinned(provider, model):
        del provider
        return _pricing(model) if bool(priced) else None

    monkeypatch.setattr(provider_selftest, "_pinned_pricing", pinned)


def test_two_priced_exact_routes_settle_and_attest_independently(monkeypatch, tmp_path):
    _live_fixture(
        monkeypatch,
        tmp_path,
        ["zhipu:priced-a", "openrouter:priced-b"],
    )
    payload = provider_selftest.run_provider_selftest(
        profile="staged", live=True, require_independent_routes=2, max_probes=2
    )
    assert payload["ok"] is True
    assert payload["callable_count"] == 2
    assert payload["admission_eligible_count"] == 2
    assert payload["independent_route_count"] == 2
    assert payload["budget"]["accounting_valid"] is True
    assert payload["budget"]["unverifiable_dimensions"] == []
    assert provider_selftest.validate_provider_receipt(
        json.loads(Path(payload["receipt"]).read_text()), path=Path(payload["receipt"])
    ) == []


def test_unpriced_callable_route_is_not_admitted_or_green(monkeypatch, tmp_path):
    _live_fixture(monkeypatch, tmp_path, ["ollama:glm-5.1:cloud"], priced=False)
    payload = provider_selftest.run_provider_selftest(
        profile="staged", live=True, require_independent_routes=1, max_probes=1
    )
    row = payload["rows"][0]
    assert row["callable"] is True
    assert row["admission_eligible"] is False
    assert row["provider_usd_verified"] is None
    assert payload["independent_route_count"] == 0
    assert payload["budget"]["accounting_valid"] is False
    assert "usd" in payload["budget"]["unverifiable_dimensions"]
    assert payload["ok"] is False
    assert "provider_probe_usage_unverifiable" in payload["failures"]


def test_same_provider_routes_are_not_independent(monkeypatch, tmp_path):
    _live_fixture(monkeypatch, tmp_path, ["zhipu:priced-a", "zhipu:priced-b"])
    payload = provider_selftest.run_provider_selftest(
        profile="staged", live=True, require_independent_routes=2, max_probes=2
    )
    assert payload["admission_eligible_count"] == 2
    assert payload["independent_route_count"] == 1
    assert payload["ok"] is False


def test_pinned_pricing_is_exact_endpoint_and_model_bound():
    priced = provider_selftest._probe_cost_evidence(
        "zhipu",
        "glm-5.1",
        {"input_tokens": 8, "output_tokens": 2, "total_tokens": 10},
    )
    assert priced["pricing_verified"] is True
    assert priced["pricing"]["endpoint_policy_id"] == "zhipu_general_paas_v4"
    assert priced["unattended_budget_eligible"] is True
    assert priced["within_reserved_usd"] is True
    assert provider_selftest._probe_cost_evidence("zhipu", "glm-5.2", {})[
        "pricing_verified"
    ] is False
    assert provider_selftest._probe_cost_evidence("ollama", "glm-5.1", {})[
        "pricing_verified"
    ] is False

    moonshot = provider_selftest._probe_cost_evidence(
        "moonshot",
        "kimi-k2.7-code",
        {"input_tokens": 1_000_000, "output_tokens": 1_000_000},
    )
    assert moonshot["pricing_verified"] is True
    assert moonshot["pricing"]["endpoint_policy_id"] == (
        "moonshot_first_party_open_platform_v1"
    )
    assert moonshot["provider_usd_verified"] == 4.95
    assert moonshot["pricing"]["cached_input_discount_claimed"] is False
    assert moonshot["pricing"]["unattended_max_call_liability_usd"] == 0.0548


def test_model_identity_never_strips_cloud_alias():
    assert provider_selftest._probe_model_identity("glm-5.1:cloud") != (
        provider_selftest._probe_model_identity("glm-5.1")
    )
    assert (
        provider_selftest._wire_model_for_provider("ollama", "glm-5.1:cloud")
        == "glm-5.1"
    )


def test_zero_placeholder_usage_is_unverifiable():
    assert provider_selftest._usage_is_coherent(
        {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    ) is False
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2, total_tokens=5)
    )
    assert provider_selftest._safe_usage(response) == {
        "input_tokens": 3,
        "output_tokens": 2,
        "total_tokens": 5,
    }


@pytest.mark.parametrize(
    ("exc", "category"),
    [
        (provider_selftest._SanitizedProviderHTTPError(429), "rate_limited"),
        (provider_selftest._SanitizedProviderHTTPError(402), "quota_or_payment"),
        (TimeoutError(), "timeout"),
        (RuntimeError("opaque"), "provider_error_unclassified"),
    ],
)
def test_failure_evidence_is_typed_without_body_or_url(exc, category):
    status = provider_selftest._sanitized_http_status(exc)
    assert provider_selftest._exception_hint(exc, status) == category


def test_sdk_transport_disables_retries_and_forces_zhipu_general_endpoint():
    class Client:
        max_retries = 2

        def with_options(self, *, max_retries):
            assert max_retries == 0
            self.max_retries = max_retries
            return self

    class Provider:
        _base_url = "https://api.z.ai/api/coding/paas/v4"

        def __init__(self):
            self._client = None
            self.client = Client()
            self.calls = 0

        def _client_or_raise(self):
            return self.client

        async def complete(self, request):
            self.calls += 1
            return LLMResponse(
                content="OK",
                model=request.model,
                usage={"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            )

        async def close(self):
            return None

    provider = Provider()
    dispatches = 0

    def before_dispatch():
        nonlocal dispatches
        dispatches += 1

    response = asyncio.run(
        provider_selftest._complete_exactly_one_transport(
            provider,
            LLMRequest(model="glm-5.1", messages=[{"role": "user", "content": "OK"}]),
            provider_name="zhipu",
            timeout_s=2,
            before_dispatch=before_dispatch,
        )
    )
    assert response.model == "glm-5.1"
    assert provider._base_url == provider_selftest.ZHIPU_GENERAL_BASE_URL
    assert provider.client.max_retries == 0
    assert provider.calls == dispatches == 1


def test_moonshot_transport_is_retry_free_and_first_party_endpoint_bound():
    class Client:
        max_retries = 2

        def with_options(self, *, max_retries):
            assert max_retries == 0
            self.max_retries = max_retries
            return self

    class Provider:
        _base_url = "https://operator-supplied-proxy.invalid/v1"

        def __init__(self):
            self._client = None
            self.client = Client()
            self.calls = 0

        def _client_or_raise(self):
            return self.client

        async def complete(self, request):
            self.calls += 1
            return LLMResponse(
                content="OK",
                model=request.model,
                usage={"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            )

        async def close(self):
            return None

    provider = Provider()
    response = asyncio.run(
        provider_selftest._complete_exactly_one_transport(
            provider,
            LLMRequest(
                model="kimi-k2.7-code",
                messages=[{"role": "user", "content": "OK"}],
            ),
            provider_name="moonshot",
            timeout_s=2,
        )
    )
    assert response.model == "kimi-k2.7-code"
    assert provider._base_url == provider_selftest.MOONSHOT_FIRST_PARTY_BASE_URL
    assert provider.client.max_retries == 0
    assert provider.calls == 1


def test_refresh_cache_rejects_future_receipt(monkeypatch, tmp_path):
    _live_fixture(monkeypatch, tmp_path, ["zhipu:priced-a"])
    first = provider_selftest.run_provider_selftest(
        profile="staged",
        live=True,
        require_independent_routes=1,
        max_probes=1,
        min_refresh_interval_s=3600,
    )
    path = Path(first["receipt"])
    payload = json.loads(path.read_text())
    payload["checked_at"] = "2999-01-01T00:00:00Z"
    payload["receipt_digest"] = provider_selftest._receipt_digest(payload)
    path.write_text(json.dumps(payload))
    second = provider_selftest.run_provider_selftest(
        profile="staged",
        live=True,
        require_independent_routes=1,
        max_probes=1,
        min_refresh_interval_s=3600,
    )
    assert second["cached"] is False
    assert second["receipt"] != str(path)
