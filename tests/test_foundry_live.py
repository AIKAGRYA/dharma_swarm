"""Tests for the live cycle — mocked HTTP, no real calls."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from dharma_swarm.foundry import live
from dharma_swarm.foundry.live import (
    FROZEN_TASKS,
    LiveResult,
    ProviderCallError,
    ProviderExhausted,
    ProviderPool,
    choose_model,
    conservative_total_tokens,
    estimate_cost_usd,
    pick_provider,
    run_live_eval,
    write_live_receipt,
)

_ANSWERS = {t.prompt: t.answer for t in FROZEN_TASKS}


def _attested(
    provider: str,
    key_name: str,
    key: str = "x",
    rate: str = "0",
) -> dict[str, str]:
    return {
        key_name: key,
        f"FOUNDRY_{provider.upper()}_USD_PER_MTOK_UPPER_BOUND": rate,
        f"FOUNDRY_{provider.upper()}_TARIFF_PROVENANCE": "test-account-tariff",
        f"FOUNDRY_{provider.upper()}_TARIFF_CHECKED_AT": "2026-08-27T00:00:00Z",
        f"FOUNDRY_{provider.upper()}_TARIFF_VALID_UNTIL": "2026-09-03T00:00:00Z",
    }


def test_no_key_returns_error():
    result = run_live_eval(env={})
    assert result.error == "no provider key present"
    assert result.accuracy == 0.0


def test_pick_provider_prefers_first_present():
    assert pick_provider(_attested("cerebras", "CEREBRAS_API_KEY"))[0] == "cerebras"
    both = {
        **_attested("groq", "GROQ_API_KEY", "g"),
        **_attested("cerebras", "CEREBRAS_API_KEY", "c"),
    }
    assert pick_provider(both)[0] == "groq"
    assert pick_provider({"GROQ_API_KEY": "present-but-unpriced"}) is None
    assert pick_provider({}) is None


def test_choose_model_prefers_general_chat_and_skips_non_chat():
    models = ["whisper-large-v3", "text-embedding-3", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    assert choose_model(models) == "llama-3.3-70b-versatile"
    # only non-chat available -> last-resort first model (never empty when models exist)
    assert choose_model(["whisper-large-v3", "nomic-embed"]) == "whisper-large-v3"
    assert choose_model([]) == ""


def test_all_correct_gives_full_accuracy():
    result = run_live_eval(
        env=_attested("groq", "GROQ_API_KEY"), model="m",
        caller=lambda m, p: _ANSWERS[p],
    )
    assert result.tasks == len(FROZEN_TASKS)
    assert result.correct == len(FROZEN_TASKS)
    assert result.accuracy == 1.0
    assert result.provider == "groq"


def test_wrong_answers_give_zero():
    result = run_live_eval(
        env=_attested("groq", "GROQ_API_KEY"), model="m",
        caller=lambda m, p: "definitely wrong",
    )
    assert result.correct == 0
    assert result.accuracy == 0.0


def test_call_error_is_scored_miss_not_crash():
    def flaky(model, prompt):
        if prompt == FROZEN_TASKS[0].prompt:
            raise TimeoutError("boom")
        return _ANSWERS[prompt]

    result = run_live_eval(
        env=_attested("groq", "GROQ_API_KEY"), model="m", caller=flaky
    )
    assert result.correct == len(FROZEN_TASKS) - 1
    assert any(pt.get("error") for pt in result.per_task)


def test_model_auto_selected_from_lister():
    result = run_live_eval(
        env=_attested("cerebras", "CEREBRAS_API_KEY"),
        model_lister=lambda: ["whisper-x", "llama-3.3-70b"],
        caller=lambda m, p: _ANSWERS[p],
    )
    assert result.model == "llama-3.3-70b"
    assert result.accuracy == 1.0


def test_receipt_written(tmp_path):
    result = LiveResult(
        "groq",
        "llama-3.3-70b",
        5,
        4,
        0.8,
        [{"ok": True}],
        provider_route_provenance={
            "groq": {
                "base_url": "https://api.groq.com/openai/v1",
                "model": "llama-3.3-70b-versatile",
                "tariff_usd_per_mtok_upper_bound": 0.0,
                "tariff_provenance": "test-account-tariff",
            }
        },
    )
    path = write_live_receipt(result, state_root=tmp_path)
    payload = json.loads(path.read_text())
    assert payload["benchmark"] == "foundry_live_frozen_v1"
    assert payload["accuracy"] == 0.8
    assert payload["provider"] == "groq"
    assert payload["provider_route_provenance"]["groq"][
        "tariff_provenance"
    ] == "test-account-tariff"


def test_live_daemon_cycle_maps_accuracy(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "run_live_eval",
                        lambda **kwargs: LiveResult("groq", "m", 5, 4, 0.8, []))
    result = live.live_daemon_cycle("x", 1, 300.0, tmp_path)
    assert result.mean_survival == 0.8
    assert result.ring2_survivors == 4
    assert result.spend_usd == 0.0


def test_cost_estimate_upper_bounds():
    assert estimate_cost_usd("groq", 1_000_000) == 5.0          # unattested lane
    assert estimate_cost_usd(
        "groq", 1_000_000, rate_upper_bound=0.0
    ) == 0.0                                                       # attested account
    assert estimate_cost_usd("zhipu", 1_000_000) == 3.0         # paid lane upper bound
    assert estimate_cost_usd("mystery", 1_000_000) == 5.0       # unknown lane -> worst case
    assert estimate_cost_usd("zhipu", 0) == 0.0


def test_paid_lane_tokens_metered_and_priced(monkeypatch):
    monkeypatch.setattr(live, "call_chat",
                        lambda base, key, m, p, **kw: (_ANSWERS[p], 40))
    result = run_live_eval(env={"ZHIPU_API_KEY": "k"}, model="glm-4.6")
    assert result.accuracy == 1.0
    assert result.total_tokens == 40 * len(FROZEN_TASKS)
    assert result.est_cost_usd == estimate_cost_usd("zhipu", result.total_tokens)
    assert result.est_cost_usd > 0.0


def test_attested_groq_failure_fails_over_to_zhipu_and_opens_circuit():
    calls: list[str] = []

    def routed_call(route, model, prompt, **kwargs):  # noqa: ARG001
        calls.append(route.name)
        if route.name == "groq":
            raise TimeoutError("request failed with secret-that-must-not-leak")
        return "ok", 17

    pool = ProviderPool(
        env={**_attested("groq", "GROQ_API_KEY"), "ZHIPU_API_KEY": "zhipu-secret"},
        chat_caller=routed_call,
        model_lister=lambda route: [],
        cooldown_seconds=300,
    )
    first = pool.call("prompt")
    second = pool.call("prompt")
    assert first.provider == second.provider == "zhipu"
    assert calls == ["groq", "groq", "zhipu", "zhipu"]
    # Two uncertain timeouts are conservatively charged for prompt + framing
    # + maximum output; the successful Zhipu calls carry reported usage.
    liability = conservative_total_tokens("prompt", 64)
    # successful Zhipu calls carry provider-reported usage.
    assert pool.total_tokens == liability * 2 + 34
    assert [a.category for a in first.attempts] == ["timeout", "timeout", "ok"]


def test_provider_exhaustion_is_typed_and_secret_free():
    def dead(route, model, prompt, **kwargs):  # noqa: ARG001
        raise ConnectionError("Bearer super-secret")

    pool = ProviderPool(
        env={**_attested("groq", "GROQ_API_KEY", "super-secret"), "ZHIPU_API_KEY": "also-secret"},
        chat_caller=dead,
        model_lister=lambda route: [],
    )
    import pytest

    with pytest.raises(ProviderExhausted) as caught:
        pool.call("prompt")
    rendered = str(caught.value)
    assert "groq:network" in rendered and "zhipu:network" in rendered
    assert "secret" not in rendered
    liability = conservative_total_tokens("prompt", 64)
    assert caught.value.billable_tokens == liability * 4
    assert all(
        attempt.usage_basis == "conservative_total_liability"
        for attempt in pool.attempt_history
    )


def test_account_dependent_route_requires_tariff_attestation_before_dispatch():
    dispatched: list[str] = []
    pool = ProviderPool(
        env={"GROQ_API_KEY": "secret"},
        chat_caller=lambda route, *args, **kwargs: dispatched.append(route.name),
    )
    import pytest

    with pytest.raises(ProviderExhausted) as caught:
        pool.call("prompt")
    assert dispatched == []
    assert caught.value.failures[0].category == "tariff_unverified"
    attempt = pool.attempt_history[0].to_dict()
    assert attempt["usage_basis"] == "no_request_route_policy"
    assert attempt["tariff_usd_per_mtok_upper_bound"] is None
    assert attempt["tariff_provenance"] == (
        "missing-stale-or-future-tariff-attestation"
    )


def test_attested_route_binds_model_endpoint_and_tariff_to_attempt():
    pool = ProviderPool(
        env=_attested("groq", "GROQ_API_KEY"),
        chat_caller=lambda route, model, prompt, **kwargs: ("ok", 7),
    )
    response = pool.call("prompt")
    attempt = response.attempts[-1].to_dict()
    assert attempt["model"] == "llama-3.3-70b-versatile"
    assert attempt["route_base_url"] == "https://api.groq.com/openai/v1"
    assert attempt["tariff_usd_per_mtok_upper_bound"] == 0.0
    assert attempt["tariff_provenance"] == "test-account-tariff"


def test_zhipu_uses_general_api_endpoint_and_pinned_model():
    pool = ProviderPool(
        env={"ZHIPU_API_KEY": "secret"},
        chat_caller=lambda route, model, prompt, **kwargs: ("ok", 7),
    )
    response = pool.call("prompt")
    assert response.model == "glm-4.6"
    attempt = response.attempts[-1].to_dict()
    assert attempt["route_base_url"] == "https://api.z.ai/api/paas/v4"
    assert attempt["tariff_usd_per_mtok_upper_bound"] == 3.0
    assert "general-api" in attempt["tariff_provenance"]
    assert attempt["tariff_checked_at"] == "2026-08-27T00:00:00+00:00"
    assert attempt["tariff_valid_until"] == "2026-09-03T00:00:00+00:00"


def test_operator_tariff_refresh_overrides_builtin_for_its_pinned_model():
    observed = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    env = {
        "ZHIPU_API_KEY": "secret",
        "FOUNDRY_ZHIPU_USD_PER_MTOK_UPPER_BOUND": "4.25",
        "FOUNDRY_ZHIPU_TARIFF_PROVENANCE": "operator:glm-4.6-general-api:2026-09-02",
        "FOUNDRY_ZHIPU_TARIFF_CHECKED_AT": "2026-09-02T00:00:00Z",
        "FOUNDRY_ZHIPU_TARIFF_VALID_UNTIL": "2026-09-09T00:00:00Z",
    }
    pool = ProviderPool(
        env=env,
        tariff_now=lambda: observed,
        chat_caller=lambda route, model, prompt, **kwargs: ("ok", 7),
    )

    response = pool.call("prompt")
    attempt = response.attempts[-1].to_dict()
    assert attempt["model"] == "glm-4.6"
    assert attempt["route_base_url"] == "https://api.z.ai/api/paas/v4"
    assert attempt["tariff_usd_per_mtok_upper_bound"] == 4.25
    assert attempt["tariff_provenance"] == (
        "operator:glm-4.6-general-api:2026-09-02"
    )
    assert attempt["tariff_checked_at"] == "2026-09-02T00:00:00+00:00"
    assert attempt["tariff_valid_until"] == "2026-09-09T00:00:00+00:00"


def test_partial_or_stale_builtin_tariff_refresh_fails_closed_pre_dispatch():
    import pytest

    observed = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    common = {
        "ZHIPU_API_KEY": "secret",
        "FOUNDRY_ZHIPU_USD_PER_MTOK_UPPER_BOUND": "4.25",
        "FOUNDRY_ZHIPU_TARIFF_PROVENANCE": "operator:glm-4.6-general-api:2026-09-02",
        "FOUNDRY_ZHIPU_TARIFF_CHECKED_AT": "2026-09-02T00:00:00Z",
    }
    for env in (
        common,
        {
            **common,
            "FOUNDRY_ZHIPU_TARIFF_VALID_UNTIL": "2026-09-02T11:59:59Z",
        },
    ):
        calls: list[str] = []
        pool = ProviderPool(
            env=env,
            tariff_now=lambda: observed,
            chat_caller=lambda route, *args, **kwargs: calls.append(route.name),
        )
        with pytest.raises(ProviderExhausted) as caught:
            pool.call("prompt")
        assert calls == []
        assert caught.value.failures[0].category == "tariff_unverified"
        assert pool.attempt_history[0].usage_basis == "no_request_route_policy"


def test_retiring_moonshot_v1_route_is_never_dispatched():
    calls: list[str] = []
    pool = ProviderPool(
        env={"MOONSHOT_API_KEY": "staged-key"},
        chat_caller=lambda route, *args, **kwargs: calls.append(route.name),
    )
    import pytest

    with pytest.raises(ProviderExhausted) as caught:
        pool.call("prompt")
    assert calls == []
    assert caught.value.failures[0].category == "route_retired"
    assert "2026-08-31" in pool.attempt_history[0].tariff_provenance


def test_paid_model_cannot_ride_a_zero_cost_pinned_route():
    calls: list[str] = []
    pool = ProviderPool(
        env={"OPENROUTER_API_KEY": "key"},
        chat_caller=lambda route, *args, **kwargs: calls.append(route.name),
    )
    import pytest

    with pytest.raises(ProviderExhausted) as caught:
        pool.call("prompt", model_hint="openai/paid-model")
    assert calls == []
    assert caught.value.failures[-1].category == "model_tariff_mismatch"
    assert pool.attempt_history[-1].usage_basis == "no_request_model_tariff_guard"


def test_stale_and_future_tariff_attestations_are_rejected_pre_dispatch():
    import pytest

    observed = datetime(2026, 8, 27, 12, tzinfo=timezone.utc)
    for updates in (
        {
            "FOUNDRY_GROQ_TARIFF_CHECKED_AT": "2026-08-20T00:00:00Z",
            "FOUNDRY_GROQ_TARIFF_VALID_UNTIL": "2026-08-27T11:59:59Z",
        },
        {
            "FOUNDRY_GROQ_TARIFF_CHECKED_AT": "2026-08-28T00:00:00Z",
            "FOUNDRY_GROQ_TARIFF_VALID_UNTIL": "2026-09-02T00:00:00Z",
        },
    ):
        calls: list[str] = []
        env = {**_attested("groq", "GROQ_API_KEY"), **updates}
        pool = ProviderPool(
            env=env,
            tariff_now=lambda: observed,
            chat_caller=lambda route, *args, **kwargs: calls.append(route.name),
        )
        with pytest.raises(ProviderExhausted) as caught:
            pool.call("prompt")
        assert calls == []
        assert caught.value.failures[0].category == "tariff_unverified"


def test_tariff_expiry_is_rechecked_by_a_long_lived_pool():
    import pytest

    current = {"now": datetime(2026, 8, 27, 12, tzinfo=timezone.utc)}
    calls: list[str] = []
    pool = ProviderPool(
        env={"ZHIPU_API_KEY": "z"},
        tariff_now=lambda: current["now"],
        chat_caller=lambda route, model, prompt, **kwargs: (
            calls.append(route.name) or ("ok", 7)
        ),
    )
    assert pool.call("prompt").provider == "zhipu"
    current["now"] = datetime(2026, 9, 3, tzinfo=timezone.utc)
    with pytest.raises(ProviderExhausted) as caught:
        pool.call("prompt")
    assert calls == ["zhipu"]
    assert caught.value.failures[-1].category == "tariff_expired"


def test_live_cycle_fully_charges_bounded_route_outage_as_zero_proposals(
    tmp_path, monkeypatch
):
    pool = ProviderPool(
        env={**_attested("groq", "GROQ_API_KEY"), "ZHIPU_API_KEY": "z"},
        chat_caller=lambda *args, **kwargs: (_ for _ in ()).throw(
            ConnectionError("offline")
        ),
        model_lister=lambda route: [],
    )
    monkeypatch.setattr(live, "ProviderPool", lambda **kwargs: pool)
    result = run_live_eval(
        env={**_attested("groq", "GROQ_API_KEY"), "ZHIPU_API_KEY": "z"}
    )
    assert result.provider_failures == len(FROZEN_TASKS)
    monkeypatch.setattr(live, "run_live_eval", lambda **kwargs: result)
    mapped = live.live_daemon_cycle("x", 1, 1.0, tmp_path)
    assert mapped.proposed == 0
    assert mapped.provider_failures == len(FROZEN_TASKS)
    assert mapped.spend_usd == result.est_cost_usd
    assert result.usage_verified is True
    assert result.total_tokens > 0


def test_pinned_models_remove_unreceipted_model_listing_requests():
    listed: list[str] = []

    def lister(route):
        listed.append(route.name)
        if route.name == "groq":
            raise ConnectionError("listing failed with moon-secret")
        return []

    pool = ProviderPool(
        env=_attested("groq", "GROQ_API_KEY", "groq-secret"),
        model_lister=lister,
        chat_caller=lambda route, model, prompt, **kwargs: ("ok", 9),
    )

    response = pool.call("prompt")
    assert response.provider == "groq"
    assert response.model == "llama-3.3-70b-versatile"
    assert listed == []
    assert pool.circuits["groq"].failures == 0


def test_malformed_post_dispatch_response_charges_max_and_marks_usage_unverifiable():
    pool = ProviderPool(
        env={"ZHIPU_API_KEY": "z"},
        chat_caller=lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("malformed JSON after dispatch")
        ),
        max_attempts_per_route=1,
    )
    import pytest

    with pytest.raises(ProviderExhausted) as caught:
        pool.call("prompt", max_tokens=123)
    liability = conservative_total_tokens("prompt", 123)
    assert caught.value.billable_tokens == liability
    assert caught.value.failures[-1].category == "invalid_response"
    assert pool.usage_verified is True
    assert pool.attempt_history[-1].liability_tokens == liability
    assert pool.attempt_history[-1].usage_basis == "conservative_total_liability"


def test_provider_cooldown_persists_across_pool_recreation(tmp_path):
    state = tmp_path / "provider-circuits.json"
    wall = {"now": 1000.0}
    calls = {"n": 0}

    def rate_limited(*args, **kwargs):
        calls["n"] += 1
        raise ProviderCallError(
            "zhipu", "rate_limited", retryable=True, status_code=429
        )

    first = ProviderPool(
        env={"ZHIPU_API_KEY": "z"},
        chat_caller=rate_limited,
        max_attempts_per_route=1,
        circuit_state_path=state,
        wall_clock=lambda: wall["now"],
    )
    import pytest

    with pytest.raises(ProviderExhausted):
        first.call("prompt")
    second = ProviderPool(
        env={"ZHIPU_API_KEY": "z"},
        chat_caller=rate_limited,
        max_attempts_per_route=1,
        circuit_state_path=state,
        wall_clock=lambda: wall["now"],
    )
    with pytest.raises(ProviderExhausted) as caught:
        second.call("prompt")
    assert calls["n"] == 1
    assert caught.value.failures[-1].category == "circuit_open"


def test_failover_spend_is_priced_per_provider(monkeypatch):
    calls = {"n": 0}

    def routed_call(route, model, prompt, **kwargs):  # noqa: ARG001
        calls["n"] += 1
        if route.name == "groq":
            raise ProviderCallError(
                "groq", "timeout", retryable=True, billable_tokens=100
            )
        return _ANSWERS[prompt], 200

    pool = ProviderPool(
        env={
            **_attested("groq", "GROQ_API_KEY", rate="4"),
            "ZHIPU_API_KEY": "z",
        },
        chat_caller=routed_call,
        model_lister=lambda route: [],
    )
    monkeypatch.setattr(live, "ProviderPool", lambda **kwargs: pool)

    result = run_live_eval(
        env={
            **_attested("groq", "GROQ_API_KEY", rate="4"),
            "ZHIPU_API_KEY": "z",
        }
    )
    assert result.accuracy == 1.0
    assert result.tokens_by_provider == {
        "groq": 200,
        "zhipu": 200 * len(FROZEN_TASKS),
    }
    assert result.est_cost_usd == round(
        estimate_cost_usd("groq", 200, rate_upper_bound=4.0)
        + estimate_cost_usd("zhipu", 200 * len(FROZEN_TASKS)),
        6,
    )


def test_payment_required_and_rate_limit_are_distinct_and_cool_down():
    import urllib.error

    errors = iter([
        urllib.error.HTTPError("https://provider.invalid", 402, "", {}, None),
        urllib.error.HTTPError("https://provider.invalid", 429, "", {}, None),
    ])
    pool = ProviderPool(
        env={**_attested("groq", "GROQ_API_KEY"), "ZHIPU_API_KEY": "z"},
        chat_caller=lambda *args, **kwargs: (_ for _ in ()).throw(next(errors)),
        model_lister=lambda route: [],
        max_attempts_per_route=1,
    )
    import pytest

    with pytest.raises(ProviderExhausted):
        pool.call("prompt")
    assert [attempt.category for attempt in pool.attempt_history] == [
        "payment_required", "rate_limited",
    ]
    liability = conservative_total_tokens("prompt", 64)
    assert [attempt.tokens for attempt in pool.attempt_history] == [
        liability, liability,
    ]
    with pytest.raises(ProviderExhausted):
        pool.call("prompt")
    assert [attempt.category for attempt in pool.attempt_history[-2:]] == [
        "circuit_open", "circuit_open",
    ]


def test_every_post_dispatch_http_error_charges_full_request_liability():
    import urllib.error
    import pytest

    for status in (400, 401, 402, 403, 404):
        pool = ProviderPool(
            env={"ZHIPU_API_KEY": "z"},
            chat_caller=lambda *args, _status=status, **kwargs: (
                _ for _ in ()
            ).throw(
                urllib.error.HTTPError(
                    "https://provider.invalid", _status, "", {}, None
                )
            ),
            max_attempts_per_route=1,
        )
        with pytest.raises(ProviderExhausted) as caught:
            pool.call("prompt", max_tokens=80)
        liability = conservative_total_tokens("prompt", 80)
        assert caught.value.billable_tokens == liability
        assert pool.attempt_history[-1].usage_basis == (
            "conservative_total_liability"
        )


def test_zero_or_missing_usage_fails_closed_with_conservative_charge():
    pool = ProviderPool(
        env={"ZHIPU_API_KEY": "z"},
        chat_caller=lambda *args, **kwargs: ("content", 0),
        model_lister=lambda route: [],
        max_attempts_per_route=1,
    )
    import pytest

    with pytest.raises(ProviderExhausted) as caught:
        pool.call("prompt", max_tokens=77)
    assert caught.value.failures[-1].category == "usage_unverifiable"
    assert caught.value.billable_tokens == conservative_total_tokens("prompt", 77)


def test_budget_guard_reserves_prompt_plus_output_liability_before_dispatch():
    calls = {"n": 0}

    def must_not_dispatch(*args, **kwargs):
        calls["n"] += 1
        return "unexpected", 1

    liability = conservative_total_tokens("large-prompt", 100)
    liability_cost = liability * 3.0 / 1_000_000
    pool = ProviderPool(
        env={"ZHIPU_API_KEY": "z"},
        chat_caller=must_not_dispatch,
        budget_cap_usd=liability_cost - 0.000001,
    )
    import pytest

    with pytest.raises(ProviderExhausted) as caught:
        pool.call("large-prompt", max_tokens=100)
    assert calls["n"] == 0
    assert caught.value.failures[-1].category == "budget_pre_dispatch"
    attempt = pool.attempt_history[-1]
    assert attempt.usage_basis == "no_request_budget_guard"
    assert attempt.liability_tokens == liability
    assert attempt.liability_cost_usd == round(liability_cost, 9)


def test_live_eval_budget_cap_blocks_every_canary_dispatch(monkeypatch):
    calls: list[str] = []

    def must_not_run(*args, **kwargs):
        calls.append("dispatched")
        return "unexpected", 1

    monkeypatch.setattr(live, "call_chat", must_not_run)
    result = run_live_eval(
        env={"ZHIPU_API_KEY": "z"},
        budget_cap_usd=0.0,
    )
    assert calls == []
    assert result.provider_failures == len(FROZEN_TASKS)
    assert result.total_tokens == 0
    assert {attempt["category"] for attempt in result.provider_attempts} == {
        "budget_pre_dispatch"
    }


def test_live_daemon_threads_durable_cycle_reservation_to_pool(
    tmp_path, monkeypatch
):
    captured: list[float | None] = []

    def evaluated(*, budget_cap_usd=None):
        captured.append(budget_cap_usd)
        return LiveResult("zhipu", "glm-4.6", 1, 1, 1.0)

    monkeypatch.setattr(live, "run_live_eval", evaluated)
    live.live_daemon_cycle("live", 1, 0.000123, tmp_path)
    assert captured == [0.000123]


def test_injected_caller_reports_zero_tokens():
    result = run_live_eval(env={"GROQ_API_KEY": "x"}, model="m",
                           caller=lambda m, p: _ANSWERS[p])
    assert result.total_tokens == 0
    assert result.est_cost_usd == 0.0


def test_live_daemon_cycle_carries_metered_spend(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "run_live_eval",
                        lambda **kwargs: LiveResult("moonshot", "m", 5, 5, 1.0, [],
                                           total_tokens=200_000, est_cost_usd=0.6))
    result = live.live_daemon_cycle("x", 1, 300.0, tmp_path)
    assert result.spend_usd == 0.6


def test_receipt_includes_token_and_cost_fields(tmp_path):
    result = LiveResult("moonshot", "m", 5, 5, 1.0, [], total_tokens=123, est_cost_usd=0.000369)
    payload = json.loads(write_live_receipt(result, state_root=tmp_path).read_text())
    assert payload["total_tokens"] == 123
    assert payload["est_cost_usd_upper_bound"] == 0.000369


def test_receipts_form_verifiable_hash_chain(tmp_path):
    paths = []
    for i in range(3):
        r = LiveResult("groq", "m", 5, 5, 1.0, [], error="",
                       )
        r.ran_at = f"2026-08-19T0{i}:00:00+00:00"  # distinct filenames, ordered
        paths.append(write_live_receipt(r, state_root=tmp_path))

    first = json.loads(paths[0].read_text())
    second = json.loads(paths[1].read_text())
    assert first["prev_digest"] == "genesis"
    assert second["prev_digest"] == first["digest"]

    ok, detail = live.verify_live_chain(tmp_path)
    assert ok, detail

    # tamper with the middle receipt -> chain must break
    middle = json.loads(paths[1].read_text())
    middle["accuracy"] = 0.0
    paths[1].write_text(json.dumps(middle))
    ok, detail = live.verify_live_chain(tmp_path)
    assert not ok
    assert "tampered" in detail or "chain break" in detail


def test_same_timestamp_live_receipts_never_overwrite(tmp_path):
    result = LiveResult("groq", "m", 5, 5, 1.0, [])
    result.ran_at = "2026-08-19T00:00:00+00:00"
    first = write_live_receipt(result, state_root=tmp_path)
    second = write_live_receipt(result, state_root=tmp_path)
    assert first != second
    assert len(list((tmp_path / "live_eval").glob("*.json"))) == 2
    ok, detail = live.verify_live_chain(tmp_path)
    assert ok, detail


def test_http_json_rejects_non_https_url():
    import pytest
    from dharma_swarm.foundry.live import _http_json
    with pytest.raises(ValueError, match="Only HTTPS URLs are permitted"):
        _http_json("http://example.com/api", "key")
    with pytest.raises(ValueError, match="Only HTTPS URLs are permitted"):
        _http_json("file:///etc/passwd", "key")
