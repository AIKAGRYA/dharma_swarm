"""Tests for the live cycle — mocked HTTP, no real calls."""

from __future__ import annotations

import json

from dharma_swarm.foundry import live
from dharma_swarm.foundry.live import (
    FROZEN_TASKS,
    LiveResult,
    ProviderCallError,
    ProviderExhausted,
    ProviderPool,
    choose_model,
    estimate_cost_usd,
    pick_provider,
    run_live_eval,
    write_live_receipt,
)

_ANSWERS = {t.prompt: t.answer for t in FROZEN_TASKS}


def test_no_key_returns_error():
    result = run_live_eval(env={})
    assert result.error == "no provider key present"
    assert result.accuracy == 0.0


def test_pick_provider_prefers_first_present():
    assert pick_provider({"CEREBRAS_API_KEY": "x"})[0] == "cerebras"
    assert pick_provider({"GROQ_API_KEY": "g", "CEREBRAS_API_KEY": "c"})[0] == "groq"
    assert pick_provider({}) is None


def test_choose_model_prefers_general_chat_and_skips_non_chat():
    models = ["whisper-large-v3", "text-embedding-3", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    assert choose_model(models) == "llama-3.3-70b-versatile"
    # only non-chat available -> last-resort first model (never empty when models exist)
    assert choose_model(["whisper-large-v3", "nomic-embed"]) == "whisper-large-v3"
    assert choose_model([]) == ""


def test_all_correct_gives_full_accuracy():
    result = run_live_eval(
        env={"GROQ_API_KEY": "x"}, model="m",
        caller=lambda m, p: _ANSWERS[p],
    )
    assert result.tasks == len(FROZEN_TASKS)
    assert result.correct == len(FROZEN_TASKS)
    assert result.accuracy == 1.0
    assert result.provider == "groq"


def test_wrong_answers_give_zero():
    result = run_live_eval(
        env={"GROQ_API_KEY": "x"}, model="m",
        caller=lambda m, p: "definitely wrong",
    )
    assert result.correct == 0
    assert result.accuracy == 0.0


def test_call_error_is_scored_miss_not_crash():
    def flaky(model, prompt):
        if prompt == FROZEN_TASKS[0].prompt:
            raise TimeoutError("boom")
        return _ANSWERS[prompt]

    result = run_live_eval(env={"GROQ_API_KEY": "x"}, model="m", caller=flaky)
    assert result.correct == len(FROZEN_TASKS) - 1
    assert any(pt.get("error") for pt in result.per_task)


def test_model_auto_selected_from_lister():
    result = run_live_eval(
        env={"CEREBRAS_API_KEY": "x"},
        model_lister=lambda: ["whisper-x", "llama-3.3-70b"],
        caller=lambda m, p: _ANSWERS[p],
    )
    assert result.model == "llama-3.3-70b"
    assert result.accuracy == 1.0


def test_receipt_written(tmp_path):
    result = LiveResult("groq", "llama-3.3-70b", 5, 4, 0.8, [{"ok": True}])
    path = write_live_receipt(result, state_root=tmp_path)
    payload = json.loads(path.read_text())
    assert payload["benchmark"] == "foundry_live_frozen_v1"
    assert payload["accuracy"] == 0.8
    assert payload["provider"] == "groq"


def test_live_daemon_cycle_maps_accuracy(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "run_live_eval",
                        lambda: LiveResult("groq", "m", 5, 4, 0.8, []))
    result = live.live_daemon_cycle("x", 1, 300.0, tmp_path)
    assert result.mean_survival == 0.8
    assert result.ring2_survivors == 4
    assert result.spend_usd == 0.0


def test_cost_estimate_upper_bounds():
    assert estimate_cost_usd("groq", 1_000_000) == 0.0          # free lane
    assert estimate_cost_usd("moonshot", 1_000_000) == 3.0      # paid lane upper bound
    assert estimate_cost_usd("mystery", 1_000_000) == 5.0       # unknown lane -> worst case
    assert estimate_cost_usd("moonshot", 0) == 0.0


def test_paid_lane_tokens_metered_and_priced(monkeypatch):
    monkeypatch.setattr(live, "call_chat",
                        lambda base, key, m, p, **kw: (_ANSWERS[p], 40))
    result = run_live_eval(env={"MOONSHOT_API_KEY": "k"}, model="moonshot-v1-8k")
    assert result.accuracy == 1.0
    assert result.total_tokens == 40 * len(FROZEN_TASKS)
    assert result.est_cost_usd == estimate_cost_usd("moonshot", result.total_tokens)
    assert result.est_cost_usd > 0.0


def test_moonshot_failure_fails_over_to_zhipu_and_opens_circuit():
    calls: list[str] = []

    def routed_call(route, model, prompt, **kwargs):  # noqa: ARG001
        calls.append(route.name)
        if route.name == "moonshot":
            raise TimeoutError("request failed with secret-that-must-not-leak")
        return "ok", 17

    pool = ProviderPool(
        env={"MOONSHOT_API_KEY": "moon-secret", "ZHIPU_API_KEY": "zhipu-secret"},
        chat_caller=routed_call,
        model_lister=lambda route: [],
        cooldown_seconds=300,
    )
    first = pool.call("prompt")
    second = pool.call("prompt")
    assert first.provider == second.provider == "zhipu"
    assert calls == ["moonshot", "zhipu", "zhipu"]
    assert pool.total_tokens == 34  # failed zero-token Moonshot call costs zero


def test_provider_exhaustion_is_typed_and_secret_free():
    def dead(route, model, prompt, **kwargs):  # noqa: ARG001
        raise ConnectionError("Bearer super-secret")

    pool = ProviderPool(
        env={"MOONSHOT_API_KEY": "super-secret", "ZHIPU_API_KEY": "also-secret"},
        chat_caller=dead,
        model_lister=lambda route: [],
    )
    import pytest

    with pytest.raises(ProviderExhausted) as caught:
        pool.call("prompt")
    rendered = str(caught.value)
    assert "moonshot:network" in rendered and "zhipu:network" in rendered
    assert "secret" not in rendered
    assert caught.value.billable_tokens == 0


def test_live_cycle_exposes_all_route_outage_as_zero_proposals(tmp_path, monkeypatch):
    pool = ProviderPool(
        env={"MOONSHOT_API_KEY": "m", "ZHIPU_API_KEY": "z"},
        chat_caller=lambda *args, **kwargs: (_ for _ in ()).throw(
            ConnectionError("offline")
        ),
        model_lister=lambda route: [],
    )
    monkeypatch.setattr(live, "ProviderPool", lambda env: pool)
    result = run_live_eval(env={"MOONSHOT_API_KEY": "m", "ZHIPU_API_KEY": "z"})
    assert result.provider_failures == len(FROZEN_TASKS)
    monkeypatch.setattr(live, "run_live_eval", lambda: result)
    campaign = live.live_daemon_cycle("x", 1, 1.0, tmp_path)
    assert campaign.proposed == 0
    assert campaign.provider_failures == len(FROZEN_TASKS)


def test_model_listing_failure_is_typed_and_fails_over():
    listed: list[str] = []

    def lister(route):
        listed.append(route.name)
        if route.name == "moonshot":
            raise ConnectionError("listing failed with moon-secret")
        return []

    pool = ProviderPool(
        env={"MOONSHOT_API_KEY": "moon-secret", "ZHIPU_API_KEY": "zhipu-secret"},
        model_lister=lister,
        chat_caller=lambda route, model, prompt, **kwargs: ("ok", 9),
    )

    response = pool.call("prompt")
    assert response.provider == "zhipu"
    assert listed == ["moonshot", "zhipu"]
    assert pool.circuits["moonshot"].failures == 1


def test_failover_spend_is_priced_per_provider(monkeypatch):
    calls = {"n": 0}

    def routed_call(route, model, prompt, **kwargs):  # noqa: ARG001
        calls["n"] += 1
        if calls["n"] == 1:
            raise ProviderCallError(
                "moonshot", "timeout", retryable=True, billable_tokens=100
            )
        return _ANSWERS[prompt], 200

    pool = ProviderPool(
        env={"MOONSHOT_API_KEY": "m", "ZHIPU_API_KEY": "z"},
        chat_caller=routed_call,
        model_lister=lambda route: [],
    )
    monkeypatch.setattr(live, "ProviderPool", lambda env: pool)

    result = run_live_eval(
        env={"MOONSHOT_API_KEY": "m", "ZHIPU_API_KEY": "z"}
    )
    assert result.accuracy == 1.0
    assert result.tokens_by_provider == {
        "moonshot": 100,
        "zhipu": 200 * len(FROZEN_TASKS),
    }
    assert result.est_cost_usd == round(
        estimate_cost_usd("moonshot", 100)
        + estimate_cost_usd("zhipu", 200 * len(FROZEN_TASKS)),
        6,
    )


def test_injected_caller_reports_zero_tokens():
    result = run_live_eval(env={"GROQ_API_KEY": "x"}, model="m",
                           caller=lambda m, p: _ANSWERS[p])
    assert result.total_tokens == 0
    assert result.est_cost_usd == 0.0


def test_live_daemon_cycle_carries_metered_spend(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "run_live_eval",
                        lambda: LiveResult("moonshot", "m", 5, 5, 1.0, [],
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
