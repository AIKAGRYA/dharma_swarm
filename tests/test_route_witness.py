"""Unit tests for dharma_swarm.route_witness — Phase 1 canonical route witness.

Covers:
- Redaction (truncation, secret patterns, witness/claude paths, email).
- Error classification (all 9 error classes).
- Tier and cost lookup (free, cheap, paid, unknown).
- Decision-outcome resolution (no attempts, all-success, all-timeout, mixed).
- build_provider_attempt: auto-derivation, redaction integration, defaults.
- emit_routing_decision: happy path, kill-switch, audit-disabled,
  telemetry-disabled, telemetry-failure-doesn't-break-audit, empty attempts.
- Schema migration is exercised by TelemetryPlaneStore.init_db side effects.

See docs/plans/2026-05-10-phase1-routing-witness.md.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from dharma_swarm.models import ProviderType
from dharma_swarm.route_witness import (
    DECISION_CLASSES,
    ERROR_CLASS_API_ERROR,
    ERROR_CLASS_AUTH_ERROR,
    ERROR_CLASS_CREDIT_EXHAUSTED,
    ERROR_CLASS_EMPTY_CONTENT,
    ERROR_CLASS_MODEL_UNAVAILABLE,
    ERROR_CLASS_NETWORK,
    ERROR_CLASS_RATE_LIMIT,
    ERROR_CLASS_TIMEOUT,
    ERROR_CLASS_UNKNOWN,
    ERROR_CLASSES,
    MAX_ERROR_DETAIL_CHARS,
    OUTCOMES,
    build_provider_attempt,
    classify_error,
    emit_routing_decision,
    estimate_cost_usd,
    redact_error_detail,
    tier_for_provider,
)
from dharma_swarm.route_witness import _resolve_decision_outcome  # type: ignore[attr-defined]
from dharma_swarm.telemetry_plane import (
    ProviderAttemptRecord,
    RoutingDecisionRecord,
    TelemetryPlaneStore,
)


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

class TestRedaction:
    def test_empty_input_returns_empty(self) -> None:
        assert redact_error_detail("") == ""

    def test_truncates_above_max(self) -> None:
        long = "x" * (MAX_ERROR_DETAIL_CHARS + 500)
        assert len(redact_error_detail(long)) <= MAX_ERROR_DETAIL_CHARS

    def test_redacts_secret_crossing_truncation_boundary(self) -> None:
        secret = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
        detail = ("x" * (MAX_ERROR_DETAIL_CHARS - 4)) + secret
        out = redact_error_detail(detail)
        assert len(out) <= MAX_ERROR_DETAIL_CHARS
        assert "sk-" not in out
        assert "abcdef" not in out
        assert "redacted" in out

    def test_redacts_anthropic_style_key(self) -> None:
        out = redact_error_detail("auth header sk-abc1234567890XYZ_token failed")
        assert "sk-abc" not in out
        assert "redacted" in out

    def test_redacts_bearer_token(self) -> None:
        out = redact_error_detail("Authorization: Bearer abcdefghijklmnopqrstuv_xyz")
        assert "abcdefghij" not in out
        assert "redacted" in out

    def test_redacts_long_hex(self) -> None:
        out = redact_error_detail("hash=" + "a" * 40)
        assert "a" * 40 not in out

    def test_redacts_email(self) -> None:
        out = redact_error_detail("contact dhyana@example.com")
        assert "dhyana@example" not in out
        assert "redacted-email" in out

    def test_redacts_witness_path(self) -> None:
        out = redact_error_detail("file at /Users/dhyana/.dharma/witness/x.jsonl")
        assert "/.dharma/" not in out
        assert "<witness_path>" in out

    def test_redacts_claude_config_path(self) -> None:
        out = redact_error_detail("config /Users/dhyana/.claude/settings.json")
        assert "/.claude/" not in out
        assert "<claude_config_path>" in out

    def test_redacts_inline_api_key(self) -> None:
        out = redact_error_detail("failed: api_key=secret_value_12345 extra")
        assert "secret_value_12345" not in out
        assert "redacted" in out.lower()

    def test_only_whitespace_after_redaction_returns_redacted(self) -> None:
        # Something that's entirely a secret pattern should not return empty.
        out = redact_error_detail("dhyana@example.com")
        assert out  # not empty
        assert "redacted-email" in out

    def test_no_secret_input_passes_through(self) -> None:
        out = redact_error_detail("connection timed out after 30s")
        assert out == "connection timed out after 30s"


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

class TestErrorClassification:
    def test_none_returns_empty(self) -> None:
        assert classify_error(None) == ""

    def test_empty_string_returns_unknown(self) -> None:
        assert classify_error("") == ERROR_CLASS_UNKNOWN

    def test_credit_balance(self) -> None:
        assert classify_error("Credit balance is too low") == ERROR_CLASS_CREDIT_EXHAUSTED

    def test_credit_alternates(self) -> None:
        for msg in (
            "Out of credits",
            "Insufficient credit on account",
            "Payment required: 402",
        ):
            assert classify_error(msg) == ERROR_CLASS_CREDIT_EXHAUSTED, msg

    def test_rate_limit_429(self) -> None:
        assert classify_error("HTTP 429: Too Many Requests") == ERROR_CLASS_RATE_LIMIT

    def test_rate_limit_quota(self) -> None:
        assert classify_error("Quota exceeded for project") == ERROR_CLASS_RATE_LIMIT

    def test_async_timeout_exception(self) -> None:
        assert classify_error(asyncio.TimeoutError()) == ERROR_CLASS_TIMEOUT

    def test_timeout_string(self) -> None:
        assert classify_error("ReadTimeout: timed out after 30s") == ERROR_CLASS_TIMEOUT

    def test_auth_401(self) -> None:
        assert classify_error("HTTP 401: Unauthorized") == ERROR_CLASS_AUTH_ERROR

    def test_auth_invalid_key(self) -> None:
        assert classify_error("Invalid API key provided") == ERROR_CLASS_AUTH_ERROR

    def test_forbidden_403_classified_as_auth(self) -> None:
        # Per Phase 1 rule: Groq APAC region returns 403; classify as auth not network.
        assert classify_error("403 Forbidden: Access denied") == ERROR_CLASS_AUTH_ERROR

    def test_network_connection_refused(self) -> None:
        assert classify_error("Connection refused by remote host") == ERROR_CLASS_NETWORK

    def test_network_dns(self) -> None:
        assert classify_error("Could not resolve DNS for api.example.com") == ERROR_CLASS_NETWORK

    def test_model_unavailable(self) -> None:
        assert classify_error("model_not_found: gpt-99-turbo") == ERROR_CLASS_MODEL_UNAVAILABLE

    def test_model_404(self) -> None:
        assert classify_error("HTTP 404: model not found") == ERROR_CLASS_MODEL_UNAVAILABLE

    def test_empty_content(self) -> None:
        assert classify_error("empty content from provider") == ERROR_CLASS_EMPTY_CONTENT

    def test_api_error_500(self) -> None:
        assert classify_error("500 Internal Server Error") == ERROR_CLASS_API_ERROR

    def test_api_error_503(self) -> None:
        assert classify_error("503 Service Unavailable") == ERROR_CLASS_API_ERROR

    def test_unknown_falls_through(self) -> None:
        assert classify_error("some weird message we don't know about") == ERROR_CLASS_UNKNOWN

    def test_all_error_classes_enumerated(self) -> None:
        # Sanity: every class returned by classify_error is in ERROR_CLASSES.
        seen = {classify_error(s) for s in (
            None, "", "credit balance", "rate limit", "401", "403",
            "model_not_found", "connection refused", "timed out",
            "empty content", "500", "weird unknown",
        )}
        seen.discard("")  # None → empty string
        assert seen.issubset(set(ERROR_CLASSES))


# ---------------------------------------------------------------------------
# Tier & cost lookup
# ---------------------------------------------------------------------------

class TestTierAndCost:
    def test_ollama_is_free(self) -> None:
        assert tier_for_provider(ProviderType.OLLAMA) == "free"

    def test_nim_is_free(self) -> None:
        assert tier_for_provider(ProviderType.NVIDIA_NIM) == "free"

    def test_groq_is_free(self) -> None:
        assert tier_for_provider(ProviderType.GROQ) == "free"

    def test_mistral_is_cheap(self) -> None:
        assert tier_for_provider(ProviderType.MISTRAL) == "cheap"

    def test_openai_is_paid(self) -> None:
        assert tier_for_provider(ProviderType.OPENAI) == "paid"

    def test_anthropic_is_paid(self) -> None:
        assert tier_for_provider(ProviderType.ANTHROPIC) == "paid"

    def test_empty_provider_is_unknown(self) -> None:
        assert tier_for_provider("") == "unknown"

    def test_string_provider_value_works(self) -> None:
        assert tier_for_provider("ollama") == "free"
        assert tier_for_provider("openai") == "paid"

    def test_free_provider_zero_cost(self) -> None:
        assert estimate_cost_usd(ProviderType.OLLAMA, prompt_tokens=10000, completion_tokens=10000) == 0.0
        assert estimate_cost_usd(ProviderType.NVIDIA_NIM, prompt_tokens=5000, completion_tokens=5000) == 0.0

    def test_paid_provider_nonzero_cost(self) -> None:
        cost = estimate_cost_usd(ProviderType.OPENAI, prompt_tokens=1000, completion_tokens=1000)
        assert cost > 0.0

    def test_zero_tokens_zero_cost(self) -> None:
        assert estimate_cost_usd(ProviderType.OPENAI, prompt_tokens=0, completion_tokens=0) == 0.0

    def test_cost_scales_with_tokens(self) -> None:
        a = estimate_cost_usd(ProviderType.OPENAI, prompt_tokens=1000, completion_tokens=1000)
        b = estimate_cost_usd(ProviderType.OPENAI, prompt_tokens=2000, completion_tokens=2000)
        assert b > a

    def test_unknown_provider_returns_baseline_cost(self) -> None:
        # Falls through to default rate (0.001 / 0.003) rather than crashing.
        cost = estimate_cost_usd("totally_made_up_provider", prompt_tokens=1000, completion_tokens=1000)
        assert cost > 0.0


# ---------------------------------------------------------------------------
# Decision outcome resolution
# ---------------------------------------------------------------------------

class TestDecisionOutcome:
    def _attempt(self, success: bool, error_class: str = "") -> ProviderAttemptRecord:
        return ProviderAttemptRecord(
            decision_id="d1", attempt_idx=0, provider="x", model="y",
            success=success, error_class=error_class,
        )

    def test_explicit_overrides(self) -> None:
        assert _resolve_decision_outcome(explicit="custom", attempts=[]) == "custom"

    def test_no_attempts_is_no_route(self) -> None:
        assert _resolve_decision_outcome(explicit=None, attempts=[]) == "no_route"

    def test_any_success_is_success(self) -> None:
        out = _resolve_decision_outcome(
            explicit=None,
            attempts=[
                self._attempt(False, ERROR_CLASS_CREDIT_EXHAUSTED),
                self._attempt(True),
            ],
        )
        assert out == "success"

    def test_all_timeout(self) -> None:
        out = _resolve_decision_outcome(
            explicit=None,
            attempts=[
                self._attempt(False, ERROR_CLASS_TIMEOUT),
                self._attempt(False, ERROR_CLASS_TIMEOUT),
            ],
        )
        assert out == "timeout"

    def test_mixed_failure_is_all_failed(self) -> None:
        out = _resolve_decision_outcome(
            explicit=None,
            attempts=[
                self._attempt(False, ERROR_CLASS_CREDIT_EXHAUSTED),
                self._attempt(False, ERROR_CLASS_RATE_LIMIT),
            ],
        )
        assert out == "all_failed"


# ---------------------------------------------------------------------------
# build_provider_attempt
# ---------------------------------------------------------------------------

class TestBuildProviderAttempt:
    def test_minimal_success(self) -> None:
        a = build_provider_attempt(
            decision_id="d1", attempt_idx=0,
            provider=ProviderType.OPENAI, model="gpt-5",
            success=True, duration_ms=100.0,
        )
        assert a.success is True
        assert a.outcome == "success"
        assert a.error_class == ""
        assert a.error_detail == ""
        assert a.tier == "paid"
        assert a.provider == "openai"

    def test_failure_classifies_credit(self) -> None:
        a = build_provider_attempt(
            decision_id="d1", attempt_idx=0,
            provider=ProviderType.CLAUDE_CODE, model="default",
            success=False, duration_ms=800.0,
            error="Credit balance is too low",
        )
        assert a.success is False
        assert a.error_class == ERROR_CLASS_CREDIT_EXHAUSTED
        assert "Credit balance" in a.error_detail

    def test_failure_redacts_secret_in_error(self) -> None:
        a = build_provider_attempt(
            decision_id="d1", attempt_idx=0,
            provider=ProviderType.OPENAI, model="gpt-5",
            success=False, duration_ms=10.0,
            error="auth header sk-abcdef1234567890XYZ failed",
        )
        assert "sk-abcdef" not in a.error_detail
        assert "redacted" in a.error_detail.lower()

    def test_explicit_error_class_override(self) -> None:
        a = build_provider_attempt(
            decision_id="d1", attempt_idx=0,
            provider=ProviderType.OPENAI, model="gpt-5",
            success=False, duration_ms=10.0,
            error="some unrecognized error",
            error_class=ERROR_CLASS_API_ERROR,
        )
        assert a.error_class == ERROR_CLASS_API_ERROR

    def test_async_timeout_classifies_as_timeout(self) -> None:
        a = build_provider_attempt(
            decision_id="d1", attempt_idx=0,
            provider=ProviderType.OPENAI, model="gpt-5",
            success=False, duration_ms=240000.0,
            error=asyncio.TimeoutError(),
        )
        assert a.error_class == ERROR_CLASS_TIMEOUT

    def test_cost_auto_derived_from_usage(self) -> None:
        a = build_provider_attempt(
            decision_id="d1", attempt_idx=0,
            provider=ProviderType.OPENAI, model="gpt-5",
            success=True, duration_ms=100.0,
            usage={"prompt_tokens": 1000, "completion_tokens": 1000, "total_tokens": 2000},
        )
        assert a.cost_estimate_usd > 0.0

    def test_explicit_cost_override(self) -> None:
        a = build_provider_attempt(
            decision_id="d1", attempt_idx=0,
            provider=ProviderType.OPENAI, model="gpt-5",
            success=True, duration_ms=100.0,
            usage={"prompt_tokens": 9999, "completion_tokens": 9999},
            cost_estimate_usd=0.42,
        )
        assert a.cost_estimate_usd == 0.42

    def test_free_provider_zero_cost_even_with_tokens(self) -> None:
        a = build_provider_attempt(
            decision_id="d1", attempt_idx=0,
            provider=ProviderType.OLLAMA, model="glm-5:cloud",
            success=True, duration_ms=100.0,
            usage={"prompt_tokens": 5000, "completion_tokens": 5000},
        )
        assert a.cost_estimate_usd == 0.0
        assert a.tier == "free"

    def test_usage_filters_non_numeric(self) -> None:
        a = build_provider_attempt(
            decision_id="d1", attempt_idx=0,
            provider=ProviderType.OPENAI, model="gpt-5",
            success=True, duration_ms=100.0,
            usage={"prompt_tokens": 100, "weird_key": "not_an_int"},  # type: ignore[dict-item]
        )
        assert a.usage == {"prompt_tokens": 100}

    def test_string_provider_accepted(self) -> None:
        a = build_provider_attempt(
            decision_id="d1", attempt_idx=0,
            provider="custom_lane", model="x",
            success=True, duration_ms=10.0,
        )
        assert a.provider == "custom_lane"
        assert a.tier == "paid"  # default for unknown

    def test_numeric_fields_are_non_negative(self) -> None:
        a = build_provider_attempt(
            decision_id="d1", attempt_idx=-10,
            provider=ProviderType.OPENAI, model="gpt-5",
            success=True, duration_ms=-5.0,
            usage={"prompt_tokens": -10, "completion_tokens": -20},
            cost_estimate_usd=-99.0,
        )
        assert a.attempt_idx == 0
        assert a.duration_ms == 0.0
        assert a.usage == {"prompt_tokens": 0, "completion_tokens": 0}
        assert a.cost_estimate_usd == 0.0


# ---------------------------------------------------------------------------
# emit_routing_decision integration
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """Isolate JSONL audit path + DB to tmp_path so tests don't touch live data."""
    audit = tmp_path / "routing_decisions.jsonl"
    monkeypatch.setenv("DGC_ROUTER_AUDIT_LOG", str(audit))
    monkeypatch.setenv("DGC_ROUTER_AUDIT_ENABLE", "1")
    monkeypatch.setenv("DGC_ROUTER_TELEMETRY_ENABLE", "1")
    monkeypatch.delenv("DGC_ROUTE_WITNESS_DISABLE_HELPER", raising=False)
    db = tmp_path / "runtime.db"
    store = TelemetryPlaneStore(db_path=db)
    return audit, store


def _make_attempt(decision_id: str = "d1") -> ProviderAttemptRecord:
    return build_provider_attempt(
        decision_id=decision_id, attempt_idx=0,
        provider=ProviderType.OPENAI, model="gpt-5",
        success=True, duration_ms=100.0,
        usage={"prompt_tokens": 100, "completion_tokens": 200},
    )


@pytest.mark.asyncio
async def test_emit_writes_to_both_jsonl_and_sqlite(isolated_env) -> None:
    audit, store = isolated_env
    await emit_routing_decision(
        decision_id="d1", action_name="test_action", route_path="deliberative",
        selected_provider=ProviderType.OPENAI, selected_model="gpt-5",
        candidate_chain=[ProviderType.OPENAI],
        decision_class="pinned", caller="unit_test",
        duration_ms=100.0, attempts=[_make_attempt()],
        task_type="test", telemetry=store,
    )

    rows = [json.loads(line) for line in audit.read_text().splitlines()]
    assert len(rows) == 2
    assert rows[0]["row_kind"] == "decision"
    assert rows[0]["caller"] == "unit_test"
    assert rows[1]["row_kind"] == "attempt"
    assert rows[1]["decision_id"] == "d1"

    decisions = await store.list_routing_decisions(limit=5)
    attempts = await store.list_provider_attempts(decision_id="d1")
    assert len(decisions) == 1
    assert decisions[0].caller == "unit_test"
    assert len(attempts) == 1
    assert attempts[0].success is True


@pytest.mark.asyncio
async def test_emit_kill_switch_is_silent_no_op(tmp_path, monkeypatch) -> None:
    audit = tmp_path / "k.jsonl"
    monkeypatch.setenv("DGC_ROUTER_AUDIT_LOG", str(audit))
    monkeypatch.setenv("DGC_ROUTE_WITNESS_DISABLE_HELPER", "1")
    store = TelemetryPlaneStore(db_path=tmp_path / "k.db")

    await emit_routing_decision(
        decision_id="d1", action_name="x", route_path="x",
        selected_provider=ProviderType.OPENAI, selected_model="x",
        candidate_chain=[], decision_class="pinned", caller="c",
        duration_ms=1.0, attempts=[],
        telemetry=store,
    )
    assert not audit.exists()
    decisions = await store.list_routing_decisions(limit=5)
    assert len(decisions) == 0


@pytest.mark.asyncio
async def test_emit_audit_disabled_skips_jsonl(tmp_path, monkeypatch) -> None:
    audit = tmp_path / "no.jsonl"
    monkeypatch.setenv("DGC_ROUTER_AUDIT_LOG", str(audit))
    monkeypatch.setenv("DGC_ROUTER_AUDIT_ENABLE", "0")
    monkeypatch.setenv("DGC_ROUTER_TELEMETRY_ENABLE", "1")
    store = TelemetryPlaneStore(db_path=tmp_path / "y.db")
    await emit_routing_decision(
        decision_id="d1", action_name="x", route_path="x",
        selected_provider=ProviderType.OPENAI, selected_model="x",
        candidate_chain=[], decision_class="pinned", caller="c",
        duration_ms=1.0, attempts=[_make_attempt()],
        telemetry=store,
    )
    assert not audit.exists()
    decisions = await store.list_routing_decisions(limit=5)
    assert len(decisions) == 1


@pytest.mark.asyncio
async def test_emit_telemetry_disabled_skips_sqlite(tmp_path, monkeypatch) -> None:
    audit = tmp_path / "ya.jsonl"
    monkeypatch.setenv("DGC_ROUTER_AUDIT_LOG", str(audit))
    monkeypatch.setenv("DGC_ROUTER_AUDIT_ENABLE", "1")
    monkeypatch.setenv("DGC_ROUTER_TELEMETRY_ENABLE", "0")
    store = TelemetryPlaneStore(db_path=tmp_path / "n.db")
    await emit_routing_decision(
        decision_id="d1", action_name="x", route_path="x",
        selected_provider=ProviderType.OPENAI, selected_model="x",
        candidate_chain=[], decision_class="pinned", caller="c",
        duration_ms=1.0, attempts=[_make_attempt()],
        telemetry=store,
    )
    rows = [json.loads(l) for l in audit.read_text().splitlines()]
    assert len(rows) == 2
    decisions = await store.list_routing_decisions(limit=5)
    assert len(decisions) == 0


@pytest.mark.asyncio
async def test_emit_no_attempts_records_no_route(isolated_env) -> None:
    audit, store = isolated_env
    await emit_routing_decision(
        decision_id="d1", action_name="x", route_path="x",
        selected_provider="", selected_model="",
        candidate_chain=[], decision_class="no_route", caller="c",
        duration_ms=0.0, attempts=[],
        telemetry=store,
    )
    rows = [json.loads(l) for l in audit.read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["row_kind"] == "decision"
    assert rows[0]["outcome"] == "no_route"
    assert rows[0]["selected_tier"] == "unknown"


@pytest.mark.asyncio
async def test_emit_never_leaks_secrets_to_jsonl(isolated_env) -> None:
    audit, store = isolated_env
    bad = build_provider_attempt(
        decision_id="d1", attempt_idx=0,
        provider=ProviderType.ANTHROPIC, model="claude-opus-4",
        success=False, duration_ms=10.0,
        error="auth header Bearer sk-1234567890abcdefghij failed: api_key=secret_abcdef12345",
    )
    await emit_routing_decision(
        decision_id="d1", action_name="x", route_path="x",
        selected_provider=ProviderType.ANTHROPIC, selected_model="claude-opus-4",
        candidate_chain=[ProviderType.ANTHROPIC],
        decision_class="pinned", caller="c",
        duration_ms=10.0, attempts=[bad],
        telemetry=store,
    )
    flat = audit.read_text()
    # No raw secrets must reach disk.
    assert "sk-1234567890abcdef" not in flat
    assert "secret_abcdef12345" not in flat
    # Witness is still useful: error_class survived.
    assert "credit_exhausted" not in flat  # was not credit-class
    # Some redacted marker must be present.
    assert "redacted" in flat.lower()


@pytest.mark.asyncio
async def test_emit_redacts_metadata_reasons_and_non_json_values(isolated_env) -> None:
    audit, store = isolated_env
    await emit_routing_decision(
        decision_id="d1",
        action_name="api_key=action_secret_123456",
        route_path="deliberative",
        selected_provider=ProviderType.OPENAI,
        selected_model="gpt-5",
        candidate_chain=[ProviderType.OPENAI, "api_key=provider_secret_123456"],
        decision_class="pinned",
        caller="unit_test",
        duration_ms=1.0,
        attempts=[_make_attempt()],
        reasons=[
            "authorization=Bearer sk-abcdefghijklmnopqrstuvwxyz123456",
            "safe_reason",
        ],
        metadata={
            "failure_trace": [
                {
                    "error": (
                        "Bearer sk-abcdefghijklmnopqrstuvwxyz123456 "
                        "api_key=metadata_secret"
                    )
                }
            ],
            "path": Path("/Users/dhyana/.dharma/witness/private.jsonl"),
            "email": "dhyana@example.com",
        },
        telemetry=store,
    )

    flat = audit.read_text()
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in flat
    assert "metadata_secret" not in flat
    assert "provider_secret" not in flat
    assert "action_secret" not in flat
    assert "/.dharma/" not in flat
    assert "dhyana@example.com" not in flat
    assert "redacted" in flat.lower()

    decisions = await store.list_routing_decisions(limit=5)
    assert len(decisions) == 1
    assert "metadata_secret" not in json.dumps(decisions[0].metadata)


@pytest.mark.asyncio
async def test_emit_concurrent_stress_preserves_joinability_and_redaction(isolated_env) -> None:
    audit, store = isolated_env
    n_decisions = 32

    async def emit_one(idx: int) -> None:
        decision_id = f"stress-{idx}"
        attempts = [
            build_provider_attempt(
                decision_id=decision_id,
                attempt_idx=0,
                provider=ProviderType.OPENAI,
                model="gpt-5",
                success=False,
                duration_ms=idx + 0.1,
                error=(
                    "rate limit Bearer sk-abcdefghijklmnopqrstuvwxyz123456 "
                    f"idx={idx}"
                ),
            ),
            build_provider_attempt(
                decision_id=decision_id,
                attempt_idx=1,
                provider=ProviderType.NVIDIA_NIM,
                model="nim",
                success=True,
                duration_ms=idx + 0.2,
                usage={"prompt_tokens": idx + 1, "completion_tokens": idx + 2},
            ),
        ]
        await emit_routing_decision(
            decision_id=decision_id,
            action_name="stress",
            route_path="deliberative",
            selected_provider=ProviderType.NVIDIA_NIM,
            selected_model="nim",
            candidate_chain=[ProviderType.OPENAI, ProviderType.NVIDIA_NIM],
            decision_class="fallback",
            caller="stress_test",
            duration_ms=idx + 1.0,
            attempts=attempts,
            telemetry=store,
        )

    await asyncio.gather(*(emit_one(idx) for idx in range(n_decisions)))

    rows = [json.loads(line) for line in audit.read_text().splitlines()]
    assert len(rows) == n_decisions * 3
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in audit.read_text()
    decision_rows = [row for row in rows if row["row_kind"] == "decision"]
    attempt_rows = [row for row in rows if row["row_kind"] == "attempt"]
    assert len(decision_rows) == n_decisions
    assert len(attempt_rows) == n_decisions * 2
    for idx in range(n_decisions):
        decision_id = f"stress-{idx}"
        assert sum(row["decision_id"] == decision_id for row in decision_rows) == 1
        assert sum(row["decision_id"] == decision_id for row in attempt_rows) == 2

    decisions = await store.list_routing_decisions(limit=n_decisions + 5)
    assert sum(item.caller == "stress_test" for item in decisions) == n_decisions
    for idx in range(n_decisions):
        attempts = await store.list_provider_attempts(decision_id=f"stress-{idx}")
        assert len(attempts) == 2


@pytest.mark.asyncio
async def test_emit_unknown_decision_class_passes_through(isolated_env) -> None:
    audit, store = isolated_env
    # Spec rule: unknown decision_class logs but does not raise.
    await emit_routing_decision(
        decision_id="d1", action_name="x", route_path="x",
        selected_provider=ProviderType.OPENAI, selected_model="gpt-5",
        candidate_chain=[ProviderType.OPENAI],
        decision_class="weirdo_not_a_real_class", caller="c",
        duration_ms=1.0, attempts=[_make_attempt()],
        telemetry=store,
    )
    rows = [json.loads(l) for l in audit.read_text().splitlines()]
    assert rows[0]["decision_class"] == "weirdo_not_a_real_class"
    assert rows[0]["row_kind"] == "decision"


@pytest.mark.asyncio
async def test_emit_total_tokens_aggregates_when_unset(isolated_env) -> None:
    audit, store = isolated_env
    a1 = build_provider_attempt(
        decision_id="d1", attempt_idx=0,
        provider=ProviderType.OPENAI, model="gpt-5",
        success=False, duration_ms=10.0,
        error="rate limit",
        usage={"prompt_tokens": 100, "completion_tokens": 200},
    )
    a2 = build_provider_attempt(
        decision_id="d1", attempt_idx=1,
        provider=ProviderType.NVIDIA_NIM, model="meta/llama-3.3-70b",
        success=True, duration_ms=10.0,
        usage={"prompt_tokens": 50, "completion_tokens": 75, "total_tokens": 125},
    )
    await emit_routing_decision(
        decision_id="d1", action_name="x", route_path="x",
        selected_provider=ProviderType.NVIDIA_NIM, selected_model="meta/llama-3.3-70b",
        candidate_chain=[ProviderType.OPENAI, ProviderType.NVIDIA_NIM],
        decision_class="fallback", caller="c", duration_ms=20.0,
        attempts=[a1, a2], telemetry=store,
    )
    rows = [json.loads(l) for l in audit.read_text().splitlines()]
    decision = rows[0]
    # Sum: a1 has no total_tokens key → uses prompt+completion=300; a2 uses total_tokens=125 → total 425.
    assert decision["total_tokens"] == 425


# ---------------------------------------------------------------------------
# Sanity: enums are exported and consistent.
# ---------------------------------------------------------------------------

class TestPublicConstants:
    def test_error_classes_tuple_has_all_individuals(self) -> None:
        all_classes = {
            ERROR_CLASS_CREDIT_EXHAUSTED, ERROR_CLASS_RATE_LIMIT,
            ERROR_CLASS_TIMEOUT, ERROR_CLASS_NETWORK,
            ERROR_CLASS_MODEL_UNAVAILABLE, ERROR_CLASS_EMPTY_CONTENT,
            ERROR_CLASS_API_ERROR, ERROR_CLASS_AUTH_ERROR,
            ERROR_CLASS_UNKNOWN,
        }
        assert all_classes == set(ERROR_CLASSES)

    def test_decision_classes_known(self) -> None:
        # Spec §2.1 rule: 5 decision classes.
        assert set(DECISION_CLASSES) == {"pinned", "widened", "fallback", "no_route", "canary"}

    def test_outcomes_known(self) -> None:
        # Spec §2.1 rule: 6 outcome values.
        assert set(OUTCOMES) == {"success", "empty_content", "all_failed", "timeout", "gate_block", "no_route"}
