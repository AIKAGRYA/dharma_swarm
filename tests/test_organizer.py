"""Tests for the Slice D propose-then-apply organizer (dry-run-first, gated)."""

from __future__ import annotations

import pytest

from dharma_swarm.fs_substrate.organizer import (
    apply_proposal,
    propose_organization,
    render_proposal,
)


def _messy(tmp_path):
    (tmp_path / "a.png").write_text("img")
    (tmp_path / "notes.md").write_text("doc")
    (tmp_path / "run.py").write_text("code")
    (tmp_path / "weird.xyz").write_text("misc")
    return tmp_path


def test_propose_is_pure_and_classifies_by_family(tmp_path):
    _messy(tmp_path)
    proposal = propose_organization(tmp_path, generated_at="2026-06-24")
    dsts = {m.src: m.dst for m in proposal.moves}
    assert dsts["a.png"] == "images/a.png"
    assert dsts["notes.md"] == "docs/notes.md"
    assert dsts["run.py"] == "code/run.py"
    assert dsts["weird.xyz"] == "misc/weird.xyz"
    # Pure: nothing moved on disk.
    assert (tmp_path / "a.png").is_file()
    assert not (tmp_path / "images").exists()


def test_apply_refuses_without_confirm(tmp_path):
    _messy(tmp_path)
    proposal = propose_organization(tmp_path)
    with pytest.raises(PermissionError):
        apply_proposal(proposal)  # confirm defaults False
    assert (tmp_path / "a.png").is_file()  # still untouched


def test_apply_with_confirm_moves_files(tmp_path):
    _messy(tmp_path)
    proposal = propose_organization(tmp_path)
    result = apply_proposal(proposal, confirm=True)
    assert (tmp_path / "images" / "a.png").is_file()
    assert (tmp_path / "docs" / "notes.md").is_file()
    assert not (tmp_path / "a.png").exists()
    assert len(result.applied) == 4 and not result.skipped


def test_write_ok_predicate_can_veto(tmp_path):
    _messy(tmp_path)
    proposal = propose_organization(tmp_path)
    # Veto everything -> all skipped, nothing moved (the MemoryWritePolicy seam).
    result = apply_proposal(proposal, confirm=True, write_ok=lambda s, d: False)
    assert not result.applied and len(result.skipped) == 4
    assert (tmp_path / "a.png").is_file()


def test_render_proposal_lists_moves(tmp_path):
    _messy(tmp_path)
    text = render_proposal(propose_organization(tmp_path, generated_at="2026-06-24"))
    assert "Reorg proposal" in text and "a.png` → `images/a.png" in text
