from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.provider_policy import ProviderRouteRequest
from dharma_swarm.providers import MAX_RECEIPT_DEMOTIONS, ModelRouter


CHAIN = [
    ProviderType.ANTHROPIC,
    ProviderType.OPENAI,
    ProviderType.OPENROUTER,
    ProviderType.OLLAMA,
]


class _Provider:
    def __init__(self, content: str) -> None:
        self.content = content

    async def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(content=self.content, model=request.model)


def _runtime_db(path: Path, receipts: list[dict[str, object] | str]) -> Path:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE delegation_runs (
            started_at TEXT NOT NULL,
            receipt_json TEXT
        )
        """
    )
    for index, receipt in enumerate(receipts):
        payload = receipt if isinstance(receipt, str) else json.dumps(receipt)
        conn.execute(
            "INSERT INTO delegation_runs(started_at, receipt_json) VALUES (?, ?)",
            (f"2026-07-15T00:00:{index:02d}Z", payload),
        )
    conn.commit()
    conn.close()
    return path


def _failed_receipt(
    provider: ProviderType,
    trace_id: str,
    *,
    boot_id: str = "producer-boot",
) -> dict[str, object]:
    return {
        "trace_id": trace_id,
        "provider": provider.value,
        "status": "error",
        "error_source": "provider",
        "attributes": {"boot_id": boot_id},
    }


def _router(db_path: Path) -> ModelRouter:
    return ModelRouter(
        {provider: object() for provider in CHAIN},  # type: ignore[arg-type]
        receipt_consumption_db_path=db_path,
    )


def test_failing_receipt_reorders_without_excluding_provider(tmp_path) -> None:
    db = _runtime_db(
        tmp_path / "runtime.db",
        [_failed_receipt(ProviderType.ANTHROPIC, "trace-anthropic")],
    )
    router = _router(db)

    reordered, applied, evidence = router._apply_receipt_consumption_ranking(CHAIN)

    assert applied is True
    assert reordered == [
        ProviderType.OPENAI,
        ProviderType.OPENROUTER,
        ProviderType.OLLAMA,
        ProviderType.ANTHROPIC,
    ]
    assert set(reordered) == set(CHAIN)
    assert evidence.consumed_trace_ids == ("trace-anthropic",)
    assert evidence.decision_delta["demoted_providers"] == ["anthropic"]


def test_no_failure_keeps_default_order_and_cites_nothing(tmp_path) -> None:
    db = _runtime_db(
        tmp_path / "runtime.db",
        [
            {
                "trace_id": "trace-ok",
                "provider": "anthropic",
                "status": "ok",
                "error_source": "none",
            }
        ],
    )
    router = _router(db)

    reordered, applied, evidence = router._apply_receipt_consumption_ranking(CHAIN)

    assert reordered == CHAIN
    assert applied is False
    assert evidence.consumed_trace_ids == ()
    assert evidence.decision_delta == {}


def test_malformed_store_fails_open_to_default_order(tmp_path) -> None:
    db = _runtime_db(tmp_path / "runtime.db", ["not-json"])
    router = _router(db)

    reordered, applied, evidence = router._apply_receipt_consumption_ranking(CHAIN)

    assert reordered == CHAIN
    assert applied is False
    assert evidence.consumed_trace_ids == ()
    assert evidence.fail_open_reason


def test_poisoning_bound_caps_demotions_and_keeps_every_provider(tmp_path) -> None:
    db = _runtime_db(
        tmp_path / "runtime.db",
        [
            _failed_receipt(provider, f"trace-{provider.value}")
            for provider in CHAIN
        ],
    )
    router = _router(db)

    reordered, applied, evidence = router._apply_receipt_consumption_ranking(CHAIN)

    assert applied is True
    assert set(reordered) == set(CHAIN)
    assert len(reordered) == len(CHAIN)
    assert len(evidence.decision_delta["demoted_providers"]) == MAX_RECEIPT_DEMOTIONS
    assert len(evidence.consumed_trace_ids) == MAX_RECEIPT_DEMOTIONS


def test_new_router_boot_consumes_prior_boot_receipt(tmp_path) -> None:
    db = _runtime_db(
        tmp_path / "runtime.db",
        [
            _failed_receipt(
                ProviderType.ANTHROPIC,
                "trace-prior-boot",
                boot_id="boot-a",
            )
        ],
    )
    producer_process = _router(db)
    consumer_process = _router(db)

    _, applied, evidence = consumer_process._apply_receipt_consumption_ranking(CHAIN)

    assert applied is True
    assert evidence.boot_id == consumer_process.receipt_consumption_boot_id
    assert evidence.boot_id != producer_process.receipt_consumption_boot_id
    assert evidence.consumed_trace_ids == ("trace-prior-boot",)


async def test_complete_for_task_uses_receipt_reordered_chain(tmp_path) -> None:
    db = _runtime_db(
        tmp_path / "runtime.db",
        [_failed_receipt(ProviderType.ANTHROPIC, "trace-anthropic")],
    )
    router = ModelRouter(
        {
            ProviderType.ANTHROPIC: _Provider("anthropic"),
            ProviderType.OPENAI: _Provider("openai"),
        },
        receipt_consumption_db_path=db,
        key_liveness_provider=lambda: None,
    )
    route_request = ProviderRouteRequest(
        action_name="analyze",
        risk_score=0.2,
        uncertainty=0.2,
        novelty=0.2,
        urgency=0.2,
        expected_impact=0.2,
    )
    request = LLMRequest(
        model="ignored",
        messages=[{"role": "user", "content": "analyze"}],
    )

    decision, response = await router.complete_for_task(
        route_request,
        request,
        available_provider_types=[ProviderType.ANTHROPIC, ProviderType.OPENAI],
    )

    assert decision.selected_provider == ProviderType.OPENAI
    assert "receipt_consumption_applied" in decision.reasons
    assert response.content == "openai"
