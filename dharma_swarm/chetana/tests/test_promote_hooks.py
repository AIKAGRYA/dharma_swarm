from __future__ import annotations

import asyncio
from pathlib import Path
from threading import Event

import pytest

import dharma_swarm.chetana.promote as promote_mod
from dharma_swarm.chetana.ingest import ingest
from dharma_swarm.chetana.promote import (
    _HOOK_EXECUTOR_MAX_WORKERS,
    drain_promotion_hooks,
    promote,
    promotion_hooks,
    shutdown_hook_executor,
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


def test_drain_logs_overdue_hooks_without_blocking(
    chetana_sandbox: Path, monkeypatch: pytest.MonkeyPatch
):
    """A hung hook should be logged as overdue, not block drain forever."""
    warnings: list[str] = []
    monkeypatch.setattr(
        promote_mod.logger,
        "warning",
        lambda message, *args, **kwargs: warnings.append(message % args if args else message),
    )

    blocker = Event()
    started = Event()

    def hung_hook(result, schema, body):
        started.set()
        # Wait far longer than the drain timeout so the future is overdue.
        blocker.wait(timeout=5.0)

    ingested = ingest(
        source="hung hook body",
        source_kind="note",
        title="Hung hook",
        confidence=0.8,
    )

    try:
        with promotion_hooks(hung_hook):
            promote(staged_path=ingested.atoms[0], promoted_by="tester")
            assert started.wait(timeout=2.0), "hook never started"
            drain_promotion_hooks(timeout=0.05)
    finally:
        blocker.set()
        drain_promotion_hooks(timeout=2.0)

    assert any("still running after" in w for w in warnings), warnings


def test_shutdown_hook_executor_is_idempotent_and_recreates(chetana_sandbox: Path):
    """Calling shutdown twice is safe; subsequent submits get a fresh executor."""
    shutdown_hook_executor(wait_for_pending=False)
    shutdown_hook_executor(wait_for_pending=False)  # second call is no-op
    seen: dict[str, bool] = {}

    def hook(result, schema, body):
        seen["ran"] = True

    ingested = ingest(
        source="post-shutdown body",
        source_kind="note",
        title="Post-shutdown hook",
        confidence=0.8,
    )

    with promotion_hooks(hook):
        promote(staged_path=ingested.atoms[0], promoted_by="tester")
        drain_promotion_hooks()

    assert seen.get("ran") is True


def test_executor_uses_multiple_workers_so_one_hung_hook_does_not_block_all(
    chetana_sandbox: Path,
):
    """With max_workers > 1, a hung hook should not block all subsequent hooks."""
    assert _HOOK_EXECUTOR_MAX_WORKERS >= 2, "lifecycle hardening requires >1 worker"
    blocker = Event()
    other_ran = Event()

    def hang(result, schema, body):
        blocker.wait(timeout=5.0)

    def quick(result, schema, body):
        other_ran.set()

    a = ingest(source="A", source_kind="note", title="A", confidence=0.8).atoms[0]
    b = ingest(source="B", source_kind="note", title="B", confidence=0.8).atoms[0]

    try:
        with promotion_hooks(hang, quick):
            promote(staged_path=a, promoted_by="tester")
            promote(staged_path=b, promoted_by="tester")
            assert other_ran.wait(timeout=2.0), "non-hung hook never ran"
    finally:
        blocker.set()
        drain_promotion_hooks(timeout=2.0)
