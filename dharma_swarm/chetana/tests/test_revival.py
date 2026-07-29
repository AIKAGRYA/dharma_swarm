"""Tests for chetana.revival — re-integrate stale atoms instead of exiling them."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from dharma_swarm.chetana.ingest import ingest
from dharma_swarm.chetana.promote import approve_atom, promote
from dharma_swarm.chetana.provenance import parse_frontmatter
from dharma_swarm.chetana.revival import (
    apply_revival,
    find_due_atoms,
    propose_revival,
)


def _seed_promoted_atom(
    *,
    title: str,
    body: str,
    stale_after: str,
    tags: list[str] | None = None,
    related: list[str] | None = None,
) -> Path:
    ing = ingest(
        source=body,
        source_kind="note",
        title=title,
        confidence=0.6,
        tags=tags or [],
        related=related or [],
    )
    pr = promote(staged_path=ing.atoms[0], promoted_by="seeder")
    assert pr.trusted_path is not None
    approved = approve_atom(path=pr.trusted_path, reviewer="seeder")
    assert approved.decision == "APPROVED"
    trusted = approved.trusted_path
    text = trusted.read_text(encoding="utf-8")
    text = text.replace(_extract_field(text, "stale_after"), stale_after, 1)
    trusted.write_text(text, encoding="utf-8")
    return trusted


def _extract_field(text: str, name: str) -> str:
    for line in text.splitlines():
        if line.startswith(f"{name}:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"no {name} field")


def test_find_due_atoms_returns_only_stale(chetana_sandbox: Path):
    past = (date.today() - timedelta(days=10)).isoformat()
    future = (date.today() + timedelta(days=10)).isoformat()
    stale = _seed_promoted_atom(title="Old A", body="x", stale_after=past)
    fresh = _seed_promoted_atom(title="New B", body="y", stale_after=future)
    due = find_due_atoms()
    assert stale in due
    assert fresh not in due


def test_propose_revival_surfaces_new_neighbors(chetana_sandbox: Path):
    past = (date.today() - timedelta(days=14)).isoformat()
    target = _seed_promoted_atom(
        title="Strange Loops",
        body="Hofstadter discusses self-reference and tangled hierarchies.",
        stale_after=past,
        tags=["consciousness", "hofstadter"],
    )

    # Drop a NEWER atom that overlaps tags with the stale one.
    _seed_promoted_atom(
        title="Eigenforms in transformers",
        body="Building on strange loops, eigenform analysis confirms self-referential geometry.",
        stale_after=(date.today() + timedelta(days=60)).isoformat(),
        tags=["consciousness", "hofstadter", "rv"],
    )

    proposal = propose_revival(atom_path=target)
    assert proposal.atom_id
    assert proposal.days_since_stale >= 14
    assert len(proposal.new_neighbors) >= 1
    # The neighbor should be classified as "confirms" (it says "confirms").
    assert any(n.contribution in {"confirms", "extends", "lateral"} for n in proposal.new_neighbors)
    assert proposal.proposed_new_stale_after > date.today().isoformat()


def test_apply_revival_writes_refreshed_atom_with_chain(chetana_sandbox: Path):
    past = (date.today() - timedelta(days=20)).isoformat()
    target = _seed_promoted_atom(
        title="Decay Lab Notes",
        body="Foundational notes about active inference and decay.",
        stale_after=past,
        tags=["friston", "active-inference"],
    )
    _seed_promoted_atom(
        title="Active Inference Update",
        body="Recent paper extends the active inference framework.",
        stale_after=(date.today() + timedelta(days=60)).isoformat(),
        tags=["friston", "active-inference", "research"],
    )

    proposal = propose_revival(atom_path=target)
    new_path = apply_revival(proposal, reviewer="test-reviewer")
    assert new_path == target

    # Read back: new stale_after, revival_chain populated.
    parsed, body = parse_frontmatter(new_path.read_text(encoding="utf-8"))
    assert parsed is not None
    assert parsed.stale_after >= date.today().isoformat()
    assert parsed.provenance is not None
    chain = parsed.provenance.revival_chain
    # Chain also carries the approve event from seeding; filter to revivals.
    revivals = [c for c in chain if "revival_id" in c]
    assert len(revivals) == 1
    assert revivals[0]["reviewed_by"] == "test-reviewer"
    assert revivals[0]["prior_signature"]
    assert "neighbors_added" in revivals[0]


def test_revive_then_revive_again_appends_chain(chetana_sandbox: Path):
    past = (date.today() - timedelta(days=30)).isoformat()
    target = _seed_promoted_atom(
        title="Twice-revived",
        body="Original body.",
        stale_after=past,
    )
    p1 = propose_revival(atom_path=target)
    apply_revival(p1, reviewer="r1")
    # Force stale again to test second cycle.
    text = target.read_text(encoding="utf-8")
    text = text.replace(_extract_field(text, "stale_after"), past, 1)
    target.write_text(text, encoding="utf-8")
    p2 = propose_revival(atom_path=target)
    apply_revival(p2, reviewer="r2")

    parsed, _ = parse_frontmatter(target.read_text(encoding="utf-8"))
    assert parsed is not None and parsed.provenance is not None
    chain = parsed.provenance.revival_chain
    revivals = [c for c in chain if "revival_id" in c]
    assert len(revivals) == 2
    assert revivals[0]["reviewed_by"] == "r1"
    assert revivals[1]["reviewed_by"] == "r2"


def test_propose_revival_marks_questions_as_open(chetana_sandbox: Path):
    past = (date.today() - timedelta(days=5)).isoformat()
    target = _seed_promoted_atom(
        title="Open-question atom",
        body="Why does the strange loop converge to a witness attractor? "
        "How is this measurable? "
        "What predicts contraction in heads other than L5?",
        stale_after=past,
    )
    proposal = propose_revival(atom_path=target)
    assert len(proposal.open_questions) >= 1
    assert proposal.needs_external_research == proposal.open_questions


def test_apply_revival_refuses_blocked_gate_without_writing(
    chetana_sandbox: Path, monkeypatch: pytest.MonkeyPatch
):
    past = (date.today() - timedelta(days=8)).isoformat()
    target = _seed_promoted_atom(
        title="Blocked revival target",
        body="Original trusted body.",
        stale_after=past,
    )
    proposal = propose_revival(atom_path=target)
    before = target.read_text(encoding="utf-8")
    blocked = SimpleNamespace(
        result="BLOCK",
        can_promote=False,
        axiom_signature="f" * 64,
        record=SimpleNamespace(
            rationale="blocked by test gate",
            gates_blocked=["test_gate"],
        ),
    )
    monkeypatch.setattr(
        "dharma_swarm.chetana.revival.gate_check_atom",
        lambda **_kwargs: blocked,
    )

    with pytest.raises(ValueError, match="revival blocked"):
        apply_revival(proposal, reviewer="test-reviewer", body_addendum="blocked addendum")

    assert target.read_text(encoding="utf-8") == before
