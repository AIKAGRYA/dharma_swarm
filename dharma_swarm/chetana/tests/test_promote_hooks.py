from __future__ import annotations

import asyncio
from pathlib import Path
from threading import Event

import pytest

import dharma_swarm.chetana.promote as promote_mod
from dharma_swarm.chetana.ingest import ingest
from dharma_swarm.chetana.promote import (
    drain_promotion_hooks,
    promote,
    promotion_hooks,
)
from dharma_swarm.chetana.provenance import parse_frontmatter
from dharma_swarm.chetana.runtime_emission import emit_memory_fact_for_atom
from dharma_swarm.runtime_state import RuntimeStateStore


def test_promote_runs_context_managed_hook(chetana_sandbox: Path):
    ingested = ingest(
        source="hook body",
        source_kind="note",
        title="Hook test",
        confidence=0.8,
    )
    called = Event()
    seen = {}

    def hook(result, schema, body):
        seen["decision"] = result.decision
        seen["title"] = schema.title
        seen["body"] = body
        called.set()

    with promotion_hooks(hook):
        pr = promote(staged_path=ingested.atoms[0], promoted_by="tester")
        drain_promotion_hooks()

    assert pr.trusted_path is not None
    assert called.is_set()
    assert seen == {
        "decision": pr.decision,
        "title": "Hook test",
        "body": "hook body\n",
    }


def test_promote_hook_failure_does_not_fail_promotion(
    chetana_sandbox: Path, monkeypatch: pytest.MonkeyPatch
):
    warnings = []

    def capture_warning(message, *args, **kwargs):
        warnings.append(message % args if args else message)

    monkeypatch.setattr(promote_mod.logger, "warning", capture_warning)
    ingested = ingest(
        source="failure hook body",
        source_kind="note",
        title="Hook failure test",
        confidence=0.8,
    )

    def bad_hook(result, schema, body):
        raise RuntimeError("boom")

    with promotion_hooks(bad_hook):
        pr = promote(staged_path=ingested.atoms[0], promoted_by="tester")
        drain_promotion_hooks()

    assert pr.trusted_path is not None
    assert pr.trusted_path.exists()
    assert any("promotion hook failed" in warning for warning in warnings)


def test_runtime_emission_hook_writes_promoted_atom_fact(
    chetana_sandbox: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from dharma_swarm import runtime_state as runtime_state_mod

    db_path = tmp_path / "runtime.db"
    monkeypatch.setattr(runtime_state_mod, "DEFAULT_RUNTIME_DB", db_path)
    ingested = ingest(
        source="runtime fact body",
        source_kind="note",
        title="Runtime Emission Atom",
        confidence=0.8,
    )
    staged = ingested.atoms[0]
    staged_schema, _ = parse_frontmatter(staged.read_text(encoding="utf-8"))
    assert staged_schema is not None

    with promotion_hooks(emit_memory_fact_for_atom):
        pr = promote(staged_path=staged, promoted_by="tester", auto_promote=True)
        drain_promotion_hooks()

    store = RuntimeStateStore(db_path)
    facts = asyncio.run(store.list_memory_facts(limit=10))

    assert pr.trusted_path is not None
    assert len(facts) == 1
    assert facts[0].fact_kind == "chetana.atomic"
    expected_truth_state = "promoted" if pr.review_status == "auto_promoted" else "candidate"
    assert facts[0].truth_state == expected_truth_state
    assert facts[0].source_artifact_id == staged_schema.atom_id
    assert facts[0].provenance["source"] == "chetana.promote"
    assert facts[0].provenance["admission"]["admitter"] == "MemoryLattice.admit_memory_fact"
