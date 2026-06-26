"""PR 0 + PR 8 verifier — read-only ingest health + onboard section.

Deterministic, no-network. Health counts the append-only stores without writing
or promoting; the onboard section renders read-only and never raises.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

from dharma_swarm.idea_spark.action_routing import emit_proposal
from dharma_swarm.idea_spark.fixtures import NOTE_FIXTURE
from dharma_swarm.idea_spark.health import (
    INGEST_HEALTH_SCHEMA,
    ingest_health,
    load_health_receipt,
    render_lines,
    wiki_cli_available,
    write_health_receipt,
)
from dharma_swarm.idea_spark.projection import candidate_from_operator_receipt
from dharma_swarm.idea_spark.store import (
    append_candidate,
    update_lifecycle_receipt,
    write_input_receipt,
)

FIXED_NOW = "2026-06-26T00:00:00Z"
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _seed_chain(tmp_path):
    receipt = NOTE_FIXTURE.build_receipt()
    write_input_receipt(receipt, tmp_path)
    candidate = candidate_from_operator_receipt(
        receipt, claim=NOTE_FIXTURE.content, domain="tooling", now=FIXED_NOW
    ).model_copy(update={"authority_level": "proposal", "owner_surface": "dharma_swarm/idea_spark/"})
    append_candidate(candidate, tmp_path)
    update_lifecycle_receipt(
        candidate.correlation_id,
        tmp_path,
        status="captured",
        input_id=receipt.input_id,
        candidate_id=candidate.candidate_id,
    )
    emit_proposal(
        candidate,
        state_root=tmp_path,
        proposals_path=tmp_path / "evolution" / "pending_proposals.jsonl",
    )
    update_lifecycle_receipt(candidate.correlation_id, tmp_path, status="implemented")
    return candidate


def test_empty_health_is_zeroed(tmp_path) -> None:
    health = ingest_health(tmp_path, now=FIXED_NOW)
    assert health["schema_version"] == INGEST_HEALTH_SCHEMA
    assert health["generated_at"] == FIXED_NOW
    assert health["input_receipts"] == 0
    assert health["candidates"]["total"] == 0
    assert health["lifecycle"]["total"] == 0
    assert health["lifecycle"]["completion_rate"] == 0.0
    # Read-only: no files created by reading health.
    assert not (tmp_path / "meta" / "idea_spark" / "health").exists()


def test_health_counts_reflect_seeded_chain(tmp_path) -> None:
    candidate = _seed_chain(tmp_path)
    health = ingest_health(tmp_path, now=FIXED_NOW)
    assert health["input_receipts"] == 1
    assert health["candidates"]["total"] == 1
    assert health["lifecycle"]["total"] == 1
    assert health["lifecycle"]["proposals"] == 1
    assert health["lifecycle"]["implemented"] == 1
    assert health["lifecycle"]["completion_rate"] == 1.0
    assert candidate.candidate_id  # sanity
    lines = render_lines(health)
    assert any("Input receipts" in line for line in lines)


def test_wiki_cli_check_matches_path() -> None:
    assert wiki_cli_available() == (shutil.which("wiki") is not None)
    health = ingest_health(now=FIXED_NOW)
    assert health["executable_knowledge_path"] == "python -m dharma_swarm.chetana.cli status"


def test_health_receipt_round_trip(tmp_path) -> None:
    _seed_chain(tmp_path)
    path = write_health_receipt(tmp_path, now=FIXED_NOW)
    assert path.exists()
    loaded = load_health_receipt(tmp_path)
    assert loaded is not None
    assert loaded["schema_version"] == INGEST_HEALTH_SCHEMA
    assert loaded["generated_at"] == FIXED_NOW
    assert loaded["lifecycle"]["total"] == 1


def _load_onboard():
    path = _REPO_ROOT / "scripts" / "governance" / "agent_onboard.py"
    spec = importlib.util.spec_from_file_location("_agent_onboard_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_onboard_section_renders_read_only(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("DHARMA_STATE_DIR", str(tmp_path))
    _seed_chain(tmp_path)
    onboard = _load_onboard()
    onboard.render_idea_spark_ingest_health()
    out = capsys.readouterr().out
    assert "IDEA SPARK INGEST HEALTH" in out
    assert "Authority" in out
    # Rendering wrote nothing.
    assert not (tmp_path / "meta" / "idea_spark" / "health").exists()


def test_onboard_section_tolerates_missing_dir(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("DHARMA_STATE_DIR", str(tmp_path / "empty"))
    onboard = _load_onboard()
    onboard.render_idea_spark_ingest_health()
    out = capsys.readouterr().out
    assert "IDEA SPARK INGEST HEALTH" in out
    assert "none yet" in out
