"""PR 9 verifier — end-to-end operator idea spark ingest (the trust claim).

Deterministic, no-network, temp roots only. Drives a local idea note, a
transcript-shaped file, and an idea-shard-shaped input through the full chain
and proves retrieval reconstructs each one by correlation_id:

    source receipt -> IdeaSparkCandidate -> Chetana staged atom
      -> MemoryKernel receipt -> Semantic Commons owner route
      -> proposal / task / BetCard -> mock implementation receipt
      -> retrieval proof by correlation_id
"""

from __future__ import annotations

import asyncio

import pytest
import yaml

from dharma_swarm.idea_spark.fixtures import (
    IDEA_SHARD_FIXTURE,
    NOTE_FIXTURE,
    TRANSCRIPT_FIXTURE,
)
from dharma_swarm.idea_spark.orchestrator import run_operator_idea_spark
from dharma_swarm.idea_spark.retrieval import probe_by_correlation_id, retrieve
from dharma_swarm.semantic_commons import SemanticCommons

FIXED_NOW = "2026-06-26T00:00:00Z"


def _temp_commons(tmp_path) -> SemanticCommons:
    tmp_path.mkdir(parents=True, exist_ok=True)
    objects = {
        "schema_version": "semantic-commons-v0",
        "owner_track": "idea-spark-e2e",
        "lifecycle_values": ["seed", "working", "preferred", "canonical", "deprecated", "forbidden"],
        "objects": [
            {
                "id": "semobj.idea_refinery",
                "canonical_name": "Idea Refinery",
                "api_name": "dharma.ingest.IdeaRefinery",
                "lifecycle": "working",
                "owner_surface": "dharma_swarm/idea_spark/",
                "authority_level": "projection",
                "source_path": "dharma_swarm/idea_spark/__init__.py",
                "aliases": [
                    "idea refinery",
                    "governed memory",
                    "memory kernel",
                    "agent runtime",
                    "chetana staging",
                    "correlation id",
                ],
                "forbidden_aliases": [],
                "supersedes": [],
                "superseded_by": [],
            }
        ],
    }
    (tmp_path / "semantic_objects.yaml").write_text(yaml.safe_dump(objects), encoding="utf-8")
    (tmp_path / "semantic_aliases.yaml").write_text(
        yaml.safe_dump({"schema_version": "semantic-commons-v0", "aliases": []}), encoding="utf-8"
    )
    return SemanticCommons.load(tmp_path)


@pytest.fixture
def e2e_env(tmp_path, monkeypatch):
    """Hermetic temp roots for Chetana + idea_spark state + a temp ontology."""
    from dharma_swarm.chetana import staging as staging_mod

    staging_root = tmp_path / "chetana" / "staging"
    quarantine_root = tmp_path / "chetana" / "quarantine"
    wiki_root = tmp_path / "chetana" / "wiki"
    trusted_root = wiki_root / "concepts"
    for directory in (staging_root, quarantine_root, wiki_root, trusted_root):
        directory.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(staging_mod, "STAGING_ROOT", staging_root, raising=True)
    monkeypatch.setattr(staging_mod, "QUARANTINE_ROOT", quarantine_root, raising=True)
    monkeypatch.setattr(staging_mod, "WIKI_ROOT", wiki_root, raising=True)
    monkeypatch.setattr(staging_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)

    try:
        from dharma_swarm import stigmergy as stig

        monkeypatch.setattr(stig, "_DEFAULT_BASE", tmp_path / "stig", raising=False)
        monkeypatch.setattr(stig, "_default_store", None, raising=False)
    except Exception:
        pass
    try:
        from dharma_swarm.chetana import governance as gov

        monkeypatch.setattr(gov, "WITNESS_DIR", tmp_path / "witness", raising=False)
    except Exception:
        pass

    from dharma_swarm import dharma_kernel as kernel_mod

    kernel_path = tmp_path / "kernel.json"
    asyncio.run(kernel_mod.KernelGuard(kernel_path).save(kernel_mod.DharmaKernel.create_default()))
    monkeypatch.setattr(kernel_mod, "_DEFAULT_KERNEL_PATH", kernel_path, raising=True)

    state_root = tmp_path / "state"
    state_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state_root))

    commons = _temp_commons(tmp_path / "ontology")
    return state_root, commons


def _run(fixture, authority_level, e2e_env):
    state_root, commons = e2e_env
    return run_operator_idea_spark(
        source_kind=fixture.source_kind,
        source_ref=fixture.source_ref,
        content=fixture.content,
        source_rights=fixture.source_rights,
        claim=fixture.content,
        domain="agent runtime",
        authority_level=authority_level,
        commons=commons,
        state_root=state_root,
        created_at=FIXED_NOW,
        proposals_path=state_root / "evolution" / "pending_proposals.jsonl",
        frontier_path=state_root / "meta" / "frontier_tasks_pending.jsonl",
    )


def _assert_full_chain(summary, *, lane_id_key) -> None:
    assert summary["found"] is True
    assert summary["input_id"]
    assert summary["candidate_id"]
    assert summary["chetana_staged_atom_id"]
    assert summary["memory_canonical_receipt_id"]
    assert summary["memory_write_receipt_id"]
    assert summary["semantic_route"]
    assert summary["owner_surface"] == "dharma_swarm/idea_spark/"
    assert summary[lane_id_key]
    assert summary["implementation_receipt_id"]
    assert summary["status"] == "implemented"


def test_note_to_proposal_full_chain(e2e_env) -> None:
    state_root, _commons = e2e_env
    result = _run(NOTE_FIXTURE, "proposal", e2e_env)
    assert result.route.resolved is True
    assert result.memory.promotion_ready is True
    assert result.action.lane == "proposal"
    # Hermetic: staged atom lives under the temp Chetana root, never ~/.dharma.
    assert str(state_root.parent) in str(result.staged.path)
    assert "/.dharma/" not in str(result.staged.path)

    probe = probe_by_correlation_id(result.correlation_id, state_root)
    _assert_full_chain(probe.to_summary(), lane_id_key="proposal_id")


def test_transcript_to_task_full_chain(e2e_env) -> None:
    state_root, _commons = e2e_env
    result = _run(TRANSCRIPT_FIXTURE, "task_candidate", e2e_env)
    assert result.action.lane == "task"
    probe = probe_by_correlation_id(result.correlation_id, state_root)
    _assert_full_chain(probe.to_summary(), lane_id_key="task_id")


def test_idea_shard_to_bet_full_chain(e2e_env) -> None:
    state_root, _commons = e2e_env
    result = _run(IDEA_SHARD_FIXTURE, "experiment_candidate", e2e_env)
    assert result.action.lane == "bet"
    probe = probe_by_correlation_id(result.correlation_id, state_root)
    _assert_full_chain(probe.to_summary(), lane_id_key="bet_id")


def test_three_inputs_are_independently_retrievable(e2e_env) -> None:
    state_root, _commons = e2e_env
    note = _run(NOTE_FIXTURE, "proposal", e2e_env)
    transcript = _run(TRANSCRIPT_FIXTURE, "task_candidate", e2e_env)
    shard = _run(IDEA_SHARD_FIXTURE, "experiment_candidate", e2e_env)

    correlation_ids = {note.correlation_id, transcript.correlation_id, shard.correlation_id}
    assert len(correlation_ids) == 3  # distinct lifecycles

    # Each is retrievable by its own correlation_id.
    for cid in correlation_ids:
        assert probe_by_correlation_id(cid, state_root).found is True

    # Shared text recalls multiple lifecycles (memory kernel appears in 2+).
    by_text = retrieve(text="memory kernel", state_root=state_root)
    found = {p.correlation_id for p in by_text}
    assert transcript.correlation_id in found
    assert shard.correlation_id in found


def test_run_is_idempotent_by_correlation_id(e2e_env) -> None:
    state_root, _commons = e2e_env
    first = _run(NOTE_FIXTURE, "proposal", e2e_env)
    second = _run(NOTE_FIXTURE, "proposal", e2e_env)
    # Same fired-in content -> same correlation + candidate + memory receipt.
    assert first.correlation_id == second.correlation_id
    assert first.candidate.candidate_id == second.candidate.candidate_id
    assert first.memory.canonical_receipt_id == second.memory.canonical_receipt_id
