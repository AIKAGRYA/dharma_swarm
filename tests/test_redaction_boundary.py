"""Secret/PII scan at memory-plane write boundaries (audit P0-9 / WS-I).

Fixtures with sk-/ghp_/high-entropy shapes must never persist raw through
record_turn, harvest_turn, ingest_envelope, or source-chunk writes; a scanner
error must quarantine (placeholder + context_admissible=False), never persist
raw.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

import dharma_swarm.redaction as redaction_mod
from dharma_swarm.engine.conversation_memory import ConversationMemoryStore
from dharma_swarm.engine.event_memory import EventMemoryStore
from dharma_swarm.engine.unified_index import UnifiedIndex
from dharma_swarm.redaction import (
    BoundaryScanResult,
    scan_json_values_for_write,
    scan_text_for_write,
)
from dharma_swarm.runtime_contract import RuntimeEnvelope, RuntimeEventType

SK_TOKEN = "sk-" + "a1b2c3d4e5f6g7h8j9k0"
GHP_TOKEN = "ghp_" + "A" * 24
HIGH_ENTROPY = "Zx9Qw8Er7Ty6Ui5Op4As3Df2Gh1Jk0Lz"

SECRET_FIXTURES = pytest.mark.parametrize(
    "secret", [SK_TOKEN, GHP_TOKEN, HIGH_ENTROPY], ids=["sk", "ghp", "entropy"]
)


def _raise_scanner_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(text: str) -> None:
        raise RuntimeError("scanner exploded")

    monkeypatch.setattr(redaction_mod, "redact_text", boom)


@SECRET_FIXTURES
def test_scan_text_for_write_redacts_secret_fixtures(secret: str) -> None:
    scan = scan_text_for_write(f"deploy notes with {secret} inline")
    assert secret not in scan.text
    assert scan.sensitive_count >= 1
    assert not scan.quarantined
    assert scan.has_secret


def test_scan_text_for_write_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _raise_scanner_error(monkeypatch)
    scan = scan_text_for_write(f"payload {SK_TOKEN}")
    assert scan.quarantined
    assert SK_TOKEN not in scan.text
    assert scan.text.startswith("<QUARANTINED_SCAN_ERROR")


def test_scan_json_values_preserves_structure() -> None:
    scan = scan_json_values_for_write(
        {"action_name": "dispatch", "detail": {"note": f"key {GHP_TOKEN}"}, "n": 3}
    )
    assert scan.value["action_name"] == "dispatch"
    assert scan.value["n"] == 3
    assert GHP_TOKEN not in json.dumps(scan.value)
    assert scan.sensitive_count >= 1


def test_verifier_ranker_reexport_is_shared_module() -> None:
    from dharma_swarm.verifier_ranker_v0 import redaction as compat

    assert compat.redact_text is redaction_mod.redact_text
    assert compat.redact_record is redaction_mod.redact_record


@SECRET_FIXTURES
def test_record_turn_never_persists_raw_secret(tmp_path, secret: str) -> None:
    store = ConversationMemoryStore(tmp_path / "memory_plane.db")
    store.record_turn(
        session_id="sess-secret",
        task_id="task-secret",
        role="user",
        content=(
            f"Maybe we should rotate the leaked key {secret} in the agent runtime.\n"
            "We could build a memory index plan for the context telemetry graph."
        ),
        turn_index=1,
    )

    with sqlite3.connect(str(tmp_path / "memory_plane.db")) as db:
        turn_rows = db.execute(
            "SELECT content, metadata_json FROM conversation_turns"
        ).fetchall()
        shard_rows = db.execute(
            "SELECT text, source_span, metadata_json FROM idea_shards"
        ).fetchall()

    assert len(turn_rows) == 1
    content, metadata_json = turn_rows[0]
    assert secret not in content
    assert "<REDACTED_" in content
    metadata = json.loads(metadata_json)
    assert metadata["pii_risk"] == "high"
    assert metadata["redaction_findings"] >= 1
    for text, source_span, shard_meta in shard_rows:
        assert secret not in text
        assert secret not in source_span
        assert secret not in shard_meta


def test_record_turn_scan_error_quarantines(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _raise_scanner_error(monkeypatch)
    store = ConversationMemoryStore(tmp_path / "memory_plane.db")
    store.record_turn(
        session_id="sess-error",
        role="user",
        content=f"Maybe we should build a plan around {SK_TOKEN} for the memory index.",
        turn_index=1,
    )

    with sqlite3.connect(str(tmp_path / "memory_plane.db")) as db:
        content, metadata_json = db.execute(
            "SELECT content, metadata_json FROM conversation_turns"
        ).fetchone()
        shard_count = db.execute("SELECT COUNT(*) FROM idea_shards").fetchone()[0]

    assert SK_TOKEN not in content
    assert content.startswith("<QUARANTINED_SCAN_ERROR")
    metadata = json.loads(metadata_json)
    assert metadata["context_admissible"] is False
    assert metadata["redaction_scan"] == "error"
    assert shard_count == 0


def test_harvest_turn_redacts_foreign_turn_candidates(tmp_path) -> None:
    db_path = tmp_path / "memory_plane.db"
    store = ConversationMemoryStore(db_path)
    turn_id = "turn_foreignwriter0000000000000001"
    with sqlite3.connect(str(db_path)) as db:
        db.execute(
            "INSERT INTO conversation_turns"
            " (turn_id, session_id, task_id, role, content, flow_state, turn_index,"
            " metadata_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                turn_id,
                "sess-foreign",
                "task-foreign",
                "user",
                f"Maybe we should build the memory index graph agent runtime plan"
                f" with context telemetry and rotate {GHP_TOKEN} now.",
                "steady",
                1,
                "{}",
                "2026-07-25T00:00:00+00:00",
            ),
        )
        db.commit()

    shards = store.harvest_turn(turn_id)
    assert shards, "expected at least one harvested shard"
    for shard in shards:
        assert GHP_TOKEN not in shard.text
        assert shard.metadata.get("pii_risk") == "high"


def test_harvest_turn_skips_quarantined_turn(tmp_path) -> None:
    db_path = tmp_path / "memory_plane.db"
    store = ConversationMemoryStore(db_path)
    turn_id = "turn_quarantined0000000000000001"
    with sqlite3.connect(str(db_path)) as db:
        db.execute(
            "INSERT INTO conversation_turns"
            " (turn_id, session_id, task_id, role, content, flow_state, turn_index,"
            " metadata_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                turn_id,
                "sess-q",
                "",
                "user",
                "<QUARANTINED_SCAN_ERROR:sha256:deadbeefdeadbeef>",
                "steady",
                1,
                json.dumps({"context_admissible": False, "redaction_scan": "error"}),
                "2026-07-25T00:00:00+00:00",
            ),
        )
        db.commit()

    assert store.harvest_turn(turn_id) == []


def _action_envelope(payload_extra: dict, event_id: str = "evt-secret") -> RuntimeEnvelope:
    return RuntimeEnvelope.create(
        event_type=RuntimeEventType.ACTION_EVENT,
        source="test.runtime",
        agent_id="agent-1",
        session_id="sess-1",
        trace_id="trace-1",
        event_id=event_id,
        emitted_at="2026-07-25T00:00:00+00:00",
        payload={
            "action_name": "dispatch_assigned",
            "decision": "recorded",
            "confidence": 1.0,
            **payload_extra,
        },
    )


@pytest.mark.asyncio
@SECRET_FIXTURES
async def test_ingest_envelope_never_persists_raw_secret(tmp_path, secret: str) -> None:
    store = EventMemoryStore(tmp_path / "memory_plane.db")
    await store.init_db()
    envelope = _action_envelope({"note": f"credential leak {secret} observed"})
    assert await store.ingest_envelope(envelope) is True

    with sqlite3.connect(str(tmp_path / "memory_plane.db")) as db:
        payload_json = db.execute("SELECT payload_json FROM event_log").fetchone()[0]

    assert secret not in payload_json
    payload = json.loads(payload_json)
    assert payload["_redaction"]["pii_risk"] == "high"
    assert payload["_redaction"]["sensitive_count"] >= 1
    assert payload["action_name"] == "dispatch_assigned"

    rows = await store.replay_session("sess-1")
    assert secret not in json.dumps(rows)


@pytest.mark.asyncio
async def test_ingest_envelope_scan_error_quarantines(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = EventMemoryStore(tmp_path / "memory_plane.db")
    await store.init_db()
    envelope = _action_envelope({"note": f"leak {SK_TOKEN}"}, event_id="evt-error")
    _raise_scanner_error(monkeypatch)
    assert await store.ingest_envelope(envelope) is True

    with sqlite3.connect(str(tmp_path / "memory_plane.db")) as db:
        payload_json = db.execute("SELECT payload_json FROM event_log").fetchone()[0]

    assert SK_TOKEN not in payload_json
    payload = json.loads(payload_json)
    assert payload["_redaction"]["quarantined"] is True
    assert payload["_redaction"]["context_admissible"] is False
    assert "action_name" not in payload


@SECRET_FIXTURES
def test_source_chunk_write_never_persists_raw_secret(tmp_path, secret: str) -> None:
    index = UnifiedIndex(tmp_path / "memory_plane.db")
    index.index_document(
        "note",
        "notes/secret.md",
        f"# Ops note\n\nRotate the deploy credential {secret} before release.\n",
        {},
    )

    with sqlite3.connect(str(tmp_path / "memory_plane.db")) as db:
        rows = db.execute("SELECT text, metadata_json FROM source_chunks").fetchall()

    assert rows
    for text, metadata_json in rows:
        assert secret not in text
    flagged = [json.loads(meta) for _text, meta in rows]
    assert any(meta.get("pii_risk") == "high" for meta in flagged)


def test_source_chunk_scan_error_quarantines(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _raise_scanner_error(monkeypatch)
    index = UnifiedIndex(tmp_path / "memory_plane.db")
    index.index_document(
        "note",
        "notes/error.md",
        f"# Ops note\n\nRotate {SK_TOKEN} before release.\n",
        {},
    )

    with sqlite3.connect(str(tmp_path / "memory_plane.db")) as db:
        rows = db.execute("SELECT text, metadata_json FROM source_chunks").fetchall()

    assert rows
    for text, metadata_json in rows:
        assert SK_TOKEN not in text
        assert text.startswith("<QUARANTINED_SCAN_ERROR")
        metadata = json.loads(metadata_json)
        assert metadata["context_admissible"] is False
        assert metadata["redaction_scan"] == "error"


def test_wiki_vector_ingest_excludes_secret_files(tmp_path) -> None:
    from dharma_swarm.wiki_vector_ingest import ingest_wiki_concepts

    wiki_dir = tmp_path / "wiki" / "concepts"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "clean.md").write_text(
        "---\ntitle: Clean Concept\n---\nOrchestrator routing concept body.\n",
        encoding="utf-8",
    )
    (wiki_dir / "leaky.md").write_text(
        f"---\ntitle: Leaky Concept\n---\nApi key {SK_TOKEN} pasted by mistake.\n",
        encoding="utf-8",
    )
    state_dir = tmp_path / "state"

    receipt = ingest_wiki_concepts(
        state_dir=state_dir,
        wiki_concepts_dir=wiki_dir,
        max_files=10,
    )

    assert receipt.discovered_files == 2
    assert receipt.skipped_secret_files == 1
    assert receipt.scan_error_files == 0
    raw = SK_TOKEN.encode("utf-8")
    for path in state_dir.rglob("*"):
        if path.is_file():
            assert raw not in path.read_bytes(), f"raw secret leaked into {path}"


def test_boundary_scan_result_secret_flag() -> None:
    assert BoundaryScanResult(
        text="x", sensitive_count=1, quarantined=False, categories=("token",)
    ).has_secret
    assert not BoundaryScanResult(
        text="x", sensitive_count=1, quarantined=False, categories=("email",)
    ).has_secret
