from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.world_radar import bronze
from dharma_swarm.world_radar.bronze import (
    BOUNDARY_CONTRACT,
    RAW_RECEIPT_SCHEMA,
    VERIFIER_BOUNDARY_SCHEMA,
    fetch_hn_algolia_rows,
    ingest_rows_to_bronze,
)
from dharma_swarm.world_radar.cli import append_operator_drop, main


def test_bronze_ingest_writes_content_addressed_receipt_and_boundary(
    tmp_path: Path,
) -> None:
    state = tmp_path / ".dharma"
    row = _operator_row()

    result = ingest_rows_to_bronze(
        [row],
        state_dir=state,
        max_items=1,
        timeout_s=3,
        fetched_at="2026-06-20T00:00:00+00:00",
    )

    assert result.ok is True
    assert result.queued_receipts == 1
    assert result.duplicate_receipts == 0
    assert result.boundary_written == 1
    receipt = json.loads(Path(result.receipt_paths[0]).read_text(encoding="utf-8"))
    assert receipt["schema_version"] == RAW_RECEIPT_SCHEMA
    assert receipt["content_hash"].startswith("sha256:")
    assert receipt["source_type"] == "operator_drop"
    assert receipt["source_url"] == row["url"]
    assert receipt["fetch_method"] == "operator_drop_attested_url"
    assert receipt["license"] == "operator_attested_public_source"
    assert receipt["instruction_policy"]["payload_is_untrusted_data"] is True
    assert receipt["prov"]["entity"]["id"] == receipt["content_hash"]
    assert receipt["prov"]["activity"]["method"] == "operator_drop_attested_url"
    assert receipt["prov"]["agent"]["id"] == bronze.FETCHER_AGENT_ID
    assert receipt["corroboration"]["required_k"] == 2
    assert receipt["budget"]["frontier_model_used"] is False
    assert receipt["dedupe"]["method"] == "minhash_lsh_before_embedding"
    assert len(receipt["dedupe"]["minhash_signature"]) == 32

    boundary = json.loads(Path(result.boundary_paths[0]).read_text(encoding="utf-8"))
    assert boundary["schema_version"] == VERIFIER_BOUNDARY_SCHEMA
    assert boundary["verifier_interface"] == BOUNDARY_CONTRACT
    assert boundary["status"] == "awaiting_decorrelated_verifier"
    assert boundary["source_receipt_id"] == receipt["receipt_id"]
    assert boundary["evidence"]["raw_receipt_path"] == result.receipt_paths[0]
    assert boundary["guardrails"]["source_text_is_untrusted"] is True
    assert boundary["guardrails"]["candidate_may_not_be_applied_without_verifier_receipt"] is True
    assert boundary["guardrails"]["self_signed_runtime_verdict_allowed"] is False
    assert boundary["not_applied"] is True


def test_bronze_reingest_same_signal_is_noop(tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    row = _operator_row()

    first = ingest_rows_to_bronze(
        [row],
        state_dir=state,
        fetched_at="2026-06-20T00:00:00+00:00",
    )
    second = ingest_rows_to_bronze(
        [row],
        state_dir=state,
        fetched_at="2026-06-20T00:01:00+00:00",
    )

    assert first.queued_receipts == 1
    assert second.queued_receipts == 0
    assert second.duplicate_receipts == 1
    assert second.boundary_written == 0
    ledger = (state / "meta" / "intelligence_supply_chain" / "bronze" / "verifier_boundary.jsonl")
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1


def test_bronze_source_type_uses_parsed_host_not_url_substring(tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    row = {
        "title": "Host spoof attempt",
        "url": "https://attacker.example/read?next=https://arxiv.org/abs/2601.00001",
        "description": "The allowed host appears only in untrusted URL data.",
    }

    result = ingest_rows_to_bronze([row], state_dir=state)

    assert result.queued_receipts == 0
    assert result.boundary_written == 0
    assert result.errors == ("unsupported_source_type:unknown",)


def test_fetch_hn_algolia_rows_uses_sanctioned_public_api(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "hits": [
                        {
                            "objectID": "123",
                            "title": "Agent benchmark release",
                            "url": "https://example.com/agent-benchmark",
                            "created_at": "2026-06-20T00:00:00Z",
                            "points": 42,
                            "num_comments": 7,
                            "author": "public-user",
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(bronze, "urlopen", fake_urlopen)

    rows = fetch_hn_algolia_rows(query="agent benchmark", limit=1, timeout_s=4)

    assert captured["timeout"] == 4
    assert "hn.algolia.com/api/v1/search_by_date" in str(captured["url"])
    assert rows[0]["source"] == "hacker_news"
    assert rows[0]["source_type"] == "hn_algolia_api"
    assert rows[0]["fetch_method"] == "hn_algolia_api"
    assert rows[0]["license"] == "hn_algolia_public_api_terms"


def test_bronze_cli_admits_existing_operator_drop(tmp_path: Path, capsys) -> None:
    state = tmp_path / ".dharma"
    append_operator_drop(
        title="External agent verifier release",
        url="https://example.com/verifier",
        note="Operator-attested public source.",
        tags=("agentic", "verification"),
        state_dir=state,
    )

    rc = main(
        [
            "bronze-operator-drops",
            "--state-dir",
            str(state),
            "--max-items",
            "1",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["queued_receipts"] == 1
    assert payload["boundary_written"] == 1
    assert Path(payload["receipt_paths"][0]).exists()


def _operator_row() -> dict[str, object]:
    return {
        "id": "operator-subq-001",
        "source": "operator_drop",
        "source_type": "operator_drop",
        "title": "SubQ subquadratic long-context runtime",
        "description": "Operator saw a public signal worth verifier review.",
        "url": "https://example.com/subq-runtime",
        "keywords": ["agentic", "runtime", "benchmark"],
        "observed_at": "2026-06-20T00:00:00+00:00",
    }
