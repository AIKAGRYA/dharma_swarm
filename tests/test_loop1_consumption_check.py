from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import scripts.governance.loop1_consumption_check as checker


IMAGE_DIGEST = "sha256:" + "b" * 64
HOST_SHA = "a" * 40
DEFAULT_ORDER = ["anthropic", "openai", "openrouter", "ollama"]
REORDERED = ["openrouter", "ollama", "anthropic", "openai"]
REQUIRED_WITNESS_FIELDS = {
    "schema",
    "observed_at",
    "producer_trace_id",
    "producer_trace_ids",
    "consumer_trace_id",
    "consumed_trace_ids",
    "decision_delta",
    "producer_boot_id",
    "producer_boot_ids",
    "consumer_boot_id",
    "chain_verified",
    "host_sha",
    "container_image_digest",
    "container_image_provenance",
    "db_path",
    "routing_audit_path",
    "delegation_runs_row_count",
    "routing_record_digest",
    "content_digest",
}


@pytest.fixture(autouse=True)
def _host_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(checker, "_host_sha", lambda: HOST_SHA)
    monkeypatch.setenv("DHARMA_CONTAINER_IMAGE_DIGEST", IMAGE_DIGEST)
    monkeypatch.setenv(
        "DHARMA_CONTAINER_IMAGE_PROVENANCE",
        "registry.example/dharma@" + IMAGE_DIGEST,
    )


def _producer(
    provider: str,
    trace_id: str,
    boot_id: str,
    *,
    status: str = "error",
    error_source: str = "provider",
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "provider": provider,
        "status": status,
        "error_source": error_source,
        "attributes": {"boot_id": boot_id},
    }


def _write_db(
    path: Path,
    receipts: list[dict[str, Any] | str | None],
) -> Path:
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE delegation_runs (started_at TEXT NOT NULL, receipt_json TEXT)"
    )
    for index, receipt in enumerate(receipts):
        if isinstance(receipt, dict):
            payload: str | None = json.dumps(receipt)
        else:
            payload = receipt
        connection.execute(
            "INSERT INTO delegation_runs(started_at, receipt_json) VALUES (?, ?)",
            (f"2026-07-15T00:00:{index:02d}Z", payload),
        )
    connection.commit()
    connection.close()
    return path


def _audit_record() -> dict[str, Any]:
    return {
        "timestamp": "2026-07-15T01:00:00Z",
        "action": "analyze",
        "provider_selected": "openrouter",
        "chain": list(REORDERED),
        "reasons": ["policy_route", "receipt_consumption_applied"],
        "consumer_trace_id": "consumer-trace-001",
        "consumer_boot_id": "consumer-boot-b",
        "consumed_trace_ids": ["producer-trace-a", "producer-trace-o"],
        "decision_delta": {
            "default_order": list(DEFAULT_ORDER),
            "reordered_order": list(REORDERED),
            "demoted_providers": ["anthropic", "openai"],
        },
        "result": "success",
    }


def _write_audit(path: Path, records: list[dict[str, Any] | str]) -> Path:
    lines = [record if isinstance(record, str) else json.dumps(record) for record in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _valid_stores(tmp_path: Path) -> tuple[Path, Path]:
    db = _write_db(
        tmp_path / "runtime.db",
        [
            _producer("anthropic", "producer-trace-a", "producer-boot-a"),
            _producer("openai", "producer-trace-o", "producer-boot-a"),
        ],
    )
    audit = _write_audit(tmp_path / "routing.jsonl", [_audit_record()])
    return db, audit


def _assert_digest_bound(receipt: dict[str, Any]) -> None:
    assert REQUIRED_WITNESS_FIELDS <= receipt.keys()
    assert checker._valid_content_digest(receipt)
    assert receipt["content_digest"] == checker._digest(receipt)


class TestDisjointImplementation:
    def test_checker_has_no_production_ranking_import_or_reference(self) -> None:
        source = Path(checker.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        imported_names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        forbidden = "apply_" + "receipt_consumption_ranking"
        assert "dharma_swarm.receipt_consumption" not in imported_modules
        assert forbidden not in imported_names
        assert forbidden not in source

    def test_broken_production_ranker_cannot_change_verdict(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from dharma_swarm import receipt_consumption

        db, audit = _valid_stores(tmp_path)

        def explode(*args: object, **kwargs: object) -> None:
            raise AssertionError("production ranker must not be called")

        monkeypatch.setattr(
            receipt_consumption,
            "apply_receipt_consumption_ranking",
            explode,
        )
        assert checker._run(db, audit)["outcome"] == "ok"


class TestCompleteWitness:
    def test_valid_raw_stores_emit_complete_digest_bound_receipt(
        self, tmp_path: Path
    ) -> None:
        db, audit = _valid_stores(tmp_path)
        receipt = checker._run(db, audit)

        assert receipt["outcome"] == "ok"
        assert receipt["producer_trace_id"] == "producer-trace-a"
        assert receipt["producer_trace_ids"] == [
            "producer-trace-a",
            "producer-trace-o",
        ]
        assert receipt["consumed_trace_ids"] == receipt["producer_trace_ids"]
        assert receipt["consumer_trace_id"] == "consumer-trace-001"
        assert receipt["producer_boot_id"] == "producer-boot-a"
        assert receipt["producer_boot_ids"] == {
            "producer-trace-a": "producer-boot-a",
            "producer-trace-o": "producer-boot-a",
        }
        assert receipt["consumer_boot_id"] == "consumer-boot-b"
        assert receipt["decision_delta"]["reordered_order"] == REORDERED
        assert receipt["chain_verified"] is True
        assert receipt["delegation_runs_row_count"] == 2
        assert receipt["host_sha"] == HOST_SHA
        assert receipt["container_image_digest"] == IMAGE_DIGEST
        assert receipt["container_image_provenance"].startswith("registry.example/")
        assert len(receipt["routing_record_digest"]) == 64
        assert [item["property"] for item in receipt["properties"]] == [
            "P1",
            "P2",
            "P3",
            "P4",
        ]
        assert all(item["ok"] for item in receipt["properties"])
        _assert_digest_bound(receipt)

    def test_total_db_row_count_is_bound_beyond_selected_receipts(
        self, tmp_path: Path
    ) -> None:
        db = _write_db(
            tmp_path / "runtime.db",
            [
                _producer("anthropic", "producer-trace-a", "producer-boot-a"),
                _producer("openai", "producer-trace-o", "producer-boot-a"),
                None,
            ],
        )
        audit = _write_audit(tmp_path / "routing.jsonl", [_audit_record()])
        receipt = checker._run(db, audit)

        assert receipt["outcome"] == "ok"
        assert receipt["delegation_runs_row_count"] == 3
        assert receipt["receipt_rows_examined"] == 2
        _assert_digest_bound(receipt)

    def test_checker_leaves_runtime_database_byte_identical(self, tmp_path: Path) -> None:
        db, audit = _valid_stores(tmp_path)
        before = hashlib.sha256(db.read_bytes()).hexdigest()

        assert checker._run(db, audit)["outcome"] == "ok"

        after = hashlib.sha256(db.read_bytes()).hexdigest()
        assert after == before

    def test_nested_consumption_payload_is_accepted(self, tmp_path: Path) -> None:
        db, audit = _valid_stores(tmp_path)
        record = _audit_record()
        nested = {
            field: record.pop(field)
            for field in (
                "consumer_trace_id",
                "consumer_boot_id",
                "consumed_trace_ids",
                "decision_delta",
            )
        }
        record["receipt_consumption"] = nested
        _write_audit(audit, [record])

        receipt = checker._run(db, audit)
        assert receipt["outcome"] == "ok"
        _assert_digest_bound(receipt)


class TestTypedNeedsHost:
    def test_missing_database_is_digest_bound_needs_host(self, tmp_path: Path) -> None:
        receipt = checker._run(tmp_path / "missing.db", tmp_path / "missing.jsonl")
        assert receipt["outcome"] == "needs_host"
        assert "producer_receipts" in receipt["missing_evidence"]
        _assert_digest_bound(receipt)

    def test_current_main_audit_shape_is_honestly_incomplete(self, tmp_path: Path) -> None:
        db, _ = _valid_stores(tmp_path)
        current_main_record = {
            "timestamp": "2026-07-15T01:00:00Z",
            "chain": list(REORDERED),
            "reasons": ["receipt_consumption_applied"],
            "provider_selected": "openrouter",
            "result": "success",
        }
        audit = _write_audit(tmp_path / "current-main.jsonl", [current_main_record])

        receipt = checker._run(db, audit)
        assert receipt["outcome"] == "needs_host"
        assert "incomplete" in receipt["reason"]
        assert "consumer_routing_evidence" in receipt["missing_evidence"]
        assert receipt["delegation_runs_row_count"] == 2
        _assert_digest_bound(receipt)

    def test_missing_producer_boot_id_is_needs_host(self, tmp_path: Path) -> None:
        db, audit = _valid_stores(tmp_path)
        connection = sqlite3.connect(db)
        row = connection.execute(
            "SELECT rowid, receipt_json FROM delegation_runs ORDER BY rowid LIMIT 1"
        ).fetchone()
        payload = json.loads(row[1])
        payload["attributes"].pop("boot_id")
        connection.execute(
            "UPDATE delegation_runs SET receipt_json = ? WHERE rowid = ?",
            (json.dumps(payload), row[0]),
        )
        connection.commit()
        connection.close()

        receipt = checker._run(db, audit)
        assert receipt["outcome"] == "needs_host"
        assert "complete_chain_evidence" in receipt["missing_evidence"]
        _assert_digest_bound(receipt)

    def test_malformed_selected_receipt_is_needs_host(self, tmp_path: Path) -> None:
        db = _write_db(tmp_path / "runtime.db", ["not-json"])
        audit = _write_audit(tmp_path / "routing.jsonl", [_audit_record()])
        receipt = checker._run(db, audit)
        assert receipt["outcome"] == "needs_host"
        assert "malformed" in receipt["reason"]
        _assert_digest_bound(receipt)

    def test_malformed_audit_is_needs_host(self, tmp_path: Path) -> None:
        db, _ = _valid_stores(tmp_path)
        audit = _write_audit(tmp_path / "routing.jsonl", ["not-json"])
        receipt = checker._run(db, audit)
        assert receipt["outcome"] == "needs_host"
        assert "malformed" in receipt["reason"]
        _assert_digest_bound(receipt)

    @pytest.mark.parametrize(
        ("missing", "expected"),
        [
            ("digest", "container_image_digest"),
            ("provenance", "container_image_provenance"),
            ("sha", "host_sha"),
        ],
    )
    def test_missing_host_binding_never_claims_ok(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        missing: str,
        expected: str,
    ) -> None:
        db, audit = _valid_stores(tmp_path)
        if missing == "digest":
            monkeypatch.delenv("DHARMA_CONTAINER_IMAGE_DIGEST")
        elif missing == "provenance":
            monkeypatch.delenv("DHARMA_CONTAINER_IMAGE_PROVENANCE")
        else:
            monkeypatch.setattr(checker, "_host_sha", lambda: "")

        receipt = checker._run(db, audit)
        assert receipt["outcome"] == "needs_host"
        assert expected in receipt["missing_evidence"]
        assert all(item["ok"] for item in receipt["properties"])
        _assert_digest_bound(receipt)


class TestAdversarialEvidence:
    @pytest.mark.parametrize(
        "mutation",
        [
            "unknown_trace",
            "duplicate_trace",
            "consumer_self_citation",
            "same_boot",
            "wrong_delta",
            "chain_mismatch",
            "too_many_demotions",
            "early_consumer",
            "provider_exclusion",
            "forged_baseline_exclusion",
        ],
    )
    def test_complete_but_contradictory_evidence_fails(
        self, tmp_path: Path, mutation: str
    ) -> None:
        db, _ = _valid_stores(tmp_path)
        record = _audit_record()
        if mutation == "unknown_trace":
            record["consumed_trace_ids"][0] = "unknown-producer"
        elif mutation == "duplicate_trace":
            record["consumed_trace_ids"][1] = record["consumed_trace_ids"][0]
        elif mutation == "consumer_self_citation":
            record["consumer_trace_id"] = record["consumed_trace_ids"][0]
        elif mutation == "same_boot":
            record["consumer_boot_id"] = "producer-boot-a"
        elif mutation == "wrong_delta":
            record["decision_delta"]["reordered_order"] = list(DEFAULT_ORDER)
            record["chain"] = list(DEFAULT_ORDER)
        elif mutation == "chain_mismatch":
            record["chain"] = list(DEFAULT_ORDER)
        elif mutation == "too_many_demotions":
            record["decision_delta"]["demoted_providers"].append("openrouter")
        elif mutation == "early_consumer":
            record["timestamp"] = "2026-07-14T23:00:00Z"
        elif mutation == "provider_exclusion":
            record["decision_delta"]["reordered_order"] = REORDERED[:-1]
            record["chain"] = REORDERED[:-1]
        elif mutation == "forged_baseline_exclusion":
            record["consumed_trace_ids"] = ["producer-trace-a"]
            record["decision_delta"] = {
                "default_order": ["anthropic", "openai"],
                "reordered_order": ["openai", "anthropic"],
                "demoted_providers": ["anthropic"],
            }
            record["chain"] = ["openai", "anthropic"]
        audit = _write_audit(tmp_path / "adversarial.jsonl", [record])

        receipt = checker._run(db, audit)
        assert receipt["outcome"] == "fail"
        assert not all(item["ok"] for item in receipt["properties"])
        _assert_digest_bound(receipt)

    def test_duplicate_raw_trace_id_fails_unique_producer_proof(
        self, tmp_path: Path
    ) -> None:
        db = _write_db(
            tmp_path / "runtime.db",
            [
                _producer("anthropic", "producer-trace-a", "producer-boot-a"),
                _producer("openai", "producer-trace-o", "producer-boot-a"),
                _producer("ollama", "producer-trace-a", "producer-boot-c"),
            ],
        )
        audit = _write_audit(tmp_path / "routing.jsonl", [_audit_record()])
        receipt = checker._run(db, audit)
        assert receipt["outcome"] == "fail"
        assert receipt["properties"][0]["ok"] is False
        _assert_digest_bound(receipt)


class TestDigestAndReplay:
    @pytest.mark.parametrize(
        "field",
        [
            "producer_trace_id",
            "producer_trace_ids",
            "consumer_trace_id",
            "consumed_trace_ids",
            "decision_delta",
            "producer_boot_id",
            "producer_boot_ids",
            "consumer_boot_id",
            "chain_verified",
            "delegation_runs_row_count",
            "host_sha",
            "container_image_digest",
            "container_image_provenance",
            "routing_record_digest",
        ],
    )
    def test_every_required_evidence_field_is_digest_bound(
        self, tmp_path: Path, field: str
    ) -> None:
        db, audit = _valid_stores(tmp_path)
        receipt = checker._run(db, audit)
        tampered = copy.deepcopy(receipt)
        value = tampered[field]
        if isinstance(value, bool):
            tampered[field] = not value
        elif isinstance(value, int):
            tampered[field] = value + 1
        elif isinstance(value, str):
            tampered[field] = value + "-tampered"
        elif isinstance(value, list):
            tampered[field] = [*value, "tampered"]
        elif isinstance(value, dict):
            tampered[field] = {**value, "tampered": "value"}
        else:  # pragma: no cover - parametrization guards supported shapes
            raise AssertionError(type(value))
        assert not checker._valid_content_digest(tampered)
        assert not checker._receipts_equivalent(receipt, tampered)

    def test_observed_at_is_the_only_replay_freshness_exception(
        self, tmp_path: Path
    ) -> None:
        db, audit = _valid_stores(tmp_path)
        receipt = checker._run(db, audit)
        replay = copy.deepcopy(receipt)
        replay["observed_at"] = "2099-01-01T00:00:00Z"
        assert checker._valid_content_digest(replay)
        assert checker._receipts_equivalent(receipt, replay)

    def test_main_replay_passes_then_rejects_tampering(self, tmp_path: Path) -> None:
        db, audit = _valid_stores(tmp_path)
        receipt_path = tmp_path / "receipt.json"
        arguments = [
            "--db",
            str(db),
            "--routing-audit",
            str(audit),
            "--receipt",
            str(receipt_path),
        ]
        assert checker.main(arguments) == 0
        assert checker.main(["--check", *arguments]) == 0

        stored = checker._read_receipt(receipt_path)
        assert stored is not None
        stored["consumer_boot_id"] = "tampered"
        checker._write_receipt(stored, receipt_path)
        assert checker.main(["--check", *arguments]) == 1


class TestCliPaths:
    def test_explicit_cli_paths_emit_ok_json(self, tmp_path: Path) -> None:
        db, audit = _valid_stores(tmp_path)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.governance.loop1_consumption_check",
                "--db",
                str(db),
                "--routing-audit",
                str(audit),
                "--stdout",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        receipt = json.loads(result.stdout)
        assert receipt["outcome"] == "ok"
        _assert_digest_bound(receipt)

    def test_environment_default_paths_emit_ok_json(self, tmp_path: Path) -> None:
        db, audit = _valid_stores(tmp_path)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        env["DGC_ROUTER_RECEIPT_DB"] = str(db)
        env["DGC_ROUTER_AUDIT_LOG"] = str(audit)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.governance.loop1_consumption_check",
                "--stdout",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        receipt = json.loads(result.stdout)
        assert receipt["outcome"] == "ok"
        assert receipt["db_path"] == str(db.resolve())
        assert receipt["routing_audit_path"] == str(audit.resolve())
        _assert_digest_bound(receipt)
