from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

from dharma_swarm.memory_kernel.write_receipts import stable_digest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "governance"
    / "loop1_consumption_check.py"
)
SPEC = importlib.util.spec_from_file_location("loop1_consumption_check", SCRIPT)
assert SPEC and SPEC.loader
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)


def _make_db(path: Path, *, self_citation: bool = False) -> Path:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE delegation_runs (
            run_id TEXT,
            started_at TEXT,
            status TEXT,
            trace_id TEXT,
            receipt_json TEXT
        )
        """
    )
    producer = {
        "trace_id": "trace-producer",
        "provider": "anthropic",
        "model": "claude",
        "status": "ok",
        "error_source": "none",
        "attributes": {"boot_id": "boot-a"},
    }
    consumer_trace = "trace-consumer"
    consumer = {
        "trace_id": consumer_trace,
        "provider": "openai",
        "model": "gpt",
        "status": "ok",
        "error_source": "none",
        "attributes": {
            "boot_id": "boot-b",
            "loop1_consumption": {
                "consumed_trace_ids": [
                    consumer_trace if self_citation else "trace-producer"
                ],
                "decision_delta": {
                    "default_order": ["anthropic", "openai"],
                    "reordered_order": ["openai", "anthropic"],
                    "demoted_providers": ["anthropic"],
                },
                "boot_id": "boot-b",
                "applied": True,
            },
        },
    }
    conn.execute(
        "INSERT INTO delegation_runs VALUES (?, ?, ?, ?, ?)",
        (
            "producer",
            "2026-07-15T00:00:00Z",
            "completed",
            "trace-producer",
            json.dumps(producer),
        ),
    )
    conn.execute(
        "INSERT INTO delegation_runs VALUES (?, ?, ?, ?, ?)",
        (
            "consumer",
            "2026-07-15T00:01:00Z",
            "completed",
            consumer_trace,
            json.dumps(consumer),
        ),
    )
    conn.commit()
    conn.close()
    return path


def _make_witness(path: Path) -> Path:
    rows: list[dict[str, object]] = []
    previous = ""
    for trace_id in ("trace-producer", "trace-consumer"):
        row: dict[str, object] = {
            "claim_id": trace_id,
            "prev_digest": previous,
            "attributes": {"trace_id": trace_id},
        }
        row["digest"] = stable_digest(row)
        previous = str(row["digest"])
        rows.append(row)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def test_check_needs_host_when_stores_are_absent(tmp_path, capsys) -> None:
    rc = checker.main(
        [
            "--check",
            "--json",
            "--db",
            str(tmp_path / "missing.db"),
            "--witness",
            str(tmp_path / "missing.jsonl"),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["outcome"] == "needs_host"
    assert payload["chain_verified"] is False


def test_passing_chain_fixture_builds_and_replays(tmp_path) -> None:
    db = _make_db(tmp_path / "runtime.db")
    witness = _make_witness(tmp_path / "claim_evidence_receipts.jsonl")
    receipt_path = tmp_path / "receipt.json"
    receipt = checker.build_receipt(
        db_path=db,
        witness_path=witness,
        host_sha="abc123",
        container_image_digest="sha256:image",
    )
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    assert receipt["chain_verified"] is True
    assert receipt["producer_boot_id"] == "boot-a"
    assert receipt["consumer_boot_id"] == "boot-b"
    assert checker.check(receipt_path, db_path=db, witness_path=witness) == []


def test_broken_witness_chain_fails(tmp_path) -> None:
    db = _make_db(tmp_path / "runtime.db")
    witness = _make_witness(tmp_path / "claim_evidence_receipts.jsonl")
    rows = witness.read_text(encoding="utf-8").splitlines()
    broken = json.loads(rows[1])
    broken["prev_digest"] = "tampered"
    rows[1] = json.dumps(broken)
    witness.write_text("\n".join(rows) + "\n", encoding="utf-8")

    _core, findings = checker.analyze(db, witness)

    assert any("witness" in finding for finding in findings)


def test_self_citation_spoof_fails(tmp_path) -> None:
    db = _make_db(tmp_path / "runtime.db", self_citation=True)
    witness = _make_witness(tmp_path / "claim_evidence_receipts.jsonl")

    _core, findings = checker.analyze(db, witness)

    assert any("self-citation" in finding for finding in findings)


def test_receipt_digest_tamper_is_detected(tmp_path) -> None:
    db = _make_db(tmp_path / "runtime.db")
    witness = _make_witness(tmp_path / "claim_evidence_receipts.jsonl")
    receipt_path = tmp_path / "receipt.json"
    receipt = checker.build_receipt(
        db_path=db,
        witness_path=witness,
        host_sha="abc123",
        container_image_digest="sha256:image",
    )
    receipt["producer_trace_id"] = "tampered"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    findings = checker.check(receipt_path, db_path=db, witness_path=witness)

    assert any("digest" in finding for finding in findings)
