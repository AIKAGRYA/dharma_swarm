"""Tests for chetana.stigmergy_emit — best-effort pheromone trail.

Verifies:
1. emit_mark() persists a real mark when StigmergyStore is importable.
2. emit_mark() returns False (not raises) when StigmergyStore can't be imported.
3. promote / revive / ingest call emit_mark() on success (mocked).
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch


from dharma_swarm.chetana import stigmergy_emit as emit_mod
from dharma_swarm.chetana.ingest import ingest
from dharma_swarm.chetana.promote import promote
from dharma_swarm.chetana.revival import apply_revival, propose_revival


# ---------------------------------------------------------------------------
# 1. emit_mark() works when StigmergyStore is present
# ---------------------------------------------------------------------------


def test_emit_mark_writes_to_store_when_importable():
    """A real call should land a JSON line in the sandboxed marks.jsonl."""
    from dharma_swarm import stigmergy as stigmergy_mod

    ok = emit_mod.emit_mark(
        action="chetana.test",
        content="emit_mark smoke test",
        connections=["chetana", "test"],
        salience=0.5,
    )
    assert ok is True

    # Verify the mark hit the (sandboxed) marks file.
    marks_file = stigmergy_mod._DEFAULT_BASE / "marks.jsonl"
    assert marks_file.exists()
    content = marks_file.read_text(encoding="utf-8")
    assert "chetana.test" in content or "emit_mark smoke test" in content


# ---------------------------------------------------------------------------
# 2. emit_mark() fails silently when StigmergyStore is NOT importable
# ---------------------------------------------------------------------------


def test_emit_mark_returns_false_when_stigmergy_not_importable(monkeypatch):
    """If dharma_swarm.stigmergy is missing, emit_mark must return False, not raise."""
    # Force the import inside emit_mark to fail by hiding the module.
    monkeypatch.setitem(sys.modules, "dharma_swarm.stigmergy", None)

    ok = emit_mod.emit_mark(
        action="chetana.test",
        content="should fail silently",
    )
    assert ok is False  # Graceful failure — no exception bubbled up


def test_emit_mark_returns_false_when_leave_mark_raises(monkeypatch):
    """If leave_mark() itself raises, emit_mark must catch and return False."""
    from dharma_swarm import stigmergy as stigmergy_mod

    class _BoomStore:
        def __init__(self):
            pass

        def leave_mark(self, mark):  # not async on purpose — exercises the catch
            raise RuntimeError("simulated stigmergy outage")

    monkeypatch.setattr(stigmergy_mod, "StigmergyStore", _BoomStore)

    ok = emit_mod.emit_mark(action="chetana.test", content="boom")
    assert ok is False


# ---------------------------------------------------------------------------
# 3. promote / revive / ingest call emit_mark() on success
# ---------------------------------------------------------------------------


def test_ingest_calls_emit_mark_once_per_ingest(chetana_sandbox: Path):
    """A single ingest() call should fire exactly one emit_mark."""
    with patch("dharma_swarm.chetana.ingest.emit_mark") as mock_emit:
        result = ingest(
            source="hello world",
            source_kind="note",
            title="emit-test",
        )
        assert result.staged_count == 1
        assert mock_emit.call_count == 1
        kwargs = mock_emit.call_args.kwargs
        assert kwargs["action"] == "chetana.ingest"
        assert "note" in kwargs["content"]
        assert "1 atoms staged" in kwargs["content"]
        assert "chetana" in kwargs["connections"]
        assert "ingest" in kwargs["connections"]


def test_promote_calls_emit_mark_on_success(chetana_sandbox: Path):
    """A successful promote() should fire emit_mark with action=chetana.promote."""
    ing = ingest(
        source="atom body for emit test",
        source_kind="note",
        title="Promote emit test",
        confidence=0.7,
    )
    staged = ing.atoms[0]

    with patch("dharma_swarm.chetana.promote.emit_mark") as mock_emit:
        pr = promote(staged_path=staged, promoted_by="test-emit")
        assert pr.decision in {"ALLOW", "WARN"}
        assert mock_emit.call_count == 1
        kwargs = mock_emit.call_args.kwargs
        assert kwargs["action"] == "chetana.promote"
        assert "Promote emit test" in kwargs["content"]
        assert pr.decision in kwargs["content"]
        # connections include chetana, promote, atom_type, review_status
        conns = kwargs["connections"]
        assert "chetana" in conns and "promote" in conns
        # salience should reflect schema confidence
        assert kwargs["salience"] == 0.7


def test_revival_apply_calls_emit_mark(chetana_sandbox: Path):
    """apply_revival() should fire emit_mark with action=chetana.revive.apply."""
    past = (date.today() - timedelta(days=10)).isoformat()
    ing = ingest(
        source="aging body needing revival",
        source_kind="note",
        title="Revive emit test",
        confidence=0.5,
    )
    pr = promote(staged_path=ing.atoms[0], promoted_by="seeder")
    assert pr.trusted_path is not None

    # Force the atom into stale territory.
    text = pr.trusted_path.read_text(encoding="utf-8")
    new_text = []
    for line in text.splitlines():
        if line.startswith("stale_after:"):
            new_text.append(f"stale_after: {past}")
        else:
            new_text.append(line)
    pr.trusted_path.write_text("\n".join(new_text) + "\n", encoding="utf-8")

    proposal = propose_revival(atom_path=pr.trusted_path)

    with patch("dharma_swarm.chetana.revival.emit_mark") as mock_emit:
        apply_revival(proposal, reviewer="test-emit")
        assert mock_emit.call_count == 1
        kwargs = mock_emit.call_args.kwargs
        assert kwargs["action"] == "chetana.revive.apply"
        assert "revived" in kwargs["content"]
        assert "chetana" in kwargs["connections"]
        assert "revive" in kwargs["connections"]
        assert kwargs["salience"] == 0.7


def test_promote_succeeds_when_stigmergy_subsystem_is_broken(chetana_sandbox, monkeypatch):
    """End-to-end: promote() must complete even when leave_mark raises internally.

    The contract is that chetana operations are atomic; stigmergy is best-effort.
    The internal try/except in emit_mark is the safety net. We verify it
    actually catches the failure by breaking StigmergyStore at the source.
    """
    from dharma_swarm import stigmergy as stigmergy_mod

    class _BrokenStore:
        def __init__(self):
            pass

        def leave_mark(self, mark):
            raise RuntimeError("stigmergy filesystem outage")

    monkeypatch.setattr(stigmergy_mod, "StigmergyStore", _BrokenStore)

    ing = ingest(
        source="atom that must promote even if stigmergy is down",
        source_kind="note",
        title="Resilience test",
        confidence=0.5,
    )
    staged = ing.atoms[0]

    # Should NOT raise — emit_mark's try/except swallows the failure.
    pr = promote(staged_path=staged, promoted_by="test-resilience")
    assert pr.decision in {"ALLOW", "WARN"}
    assert pr.trusted_path is not None and pr.trusted_path.exists()
