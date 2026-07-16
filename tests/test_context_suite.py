"""Context-suite contract — regression for the 2026-07 onboarding probe.

A four-agent probe found that CLAUDE.md's full prose copy of the track
portfolio acted as a leak channel: agents answered portfolio questions from
the copy while claiming to answer from `make onboard`, masking the gate's
empty render in fresh clones. These tests encode the fix as content
assertions on the context suite (see
docs/governance/CONTEXT_SUITE_LINE_LEDGER.md for the evidence trail):

1. live portfolio state comes from the gate, never from any .md — and the
   .md files say so explicitly;
2. the managed ACTIVE_TRACK blocks are stamped digests (source-of-truth
   path + render/check commands), not full-body copies;
3. an agent can find the owner + verification boundary for any surface
   before editing (the `owns:` globs + ACTIVE_TRACK.yaml pointer);
4. the suite states what a completed onboard run does NOT prove.

If a change here is intentional (renderer format evolves), update the
asserted phrases together with the renderer — the point is that the stamp,
the digest shape, and the trust-boundary language can never silently vanish.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
DOCS_AGENTS_MD = REPO_ROOT / "docs/AGENTS.md"
SESSION_ENTRY_CONTRACT = (
    REPO_ROOT / "docs/governance/BUILD_SESSION_ENTRYPOINT.md"
)
MANAGED = [
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "docs/governance/SOVEREIGN_MANIFEST.md",
]
BLOCK_RE = re.compile(
    r"<!-- ACTIVE_TRACK:START -->(.*?)<!-- ACTIVE_TRACK:END -->", re.DOTALL
)

# Full-body render artifacts: if any of these reappear inside a managed
# block, the leak channel is back.
LEAK_MARKERS = ("**Next items:**", "**Non-goals:**", "**Track id:**")


def _block(path: Path) -> str:
    match = BLOCK_RE.search(path.read_text(encoding="utf-8"))
    assert match, f"{path} has no managed ACTIVE_TRACK block"
    return match.group(1)


def test_every_managed_block_is_stamped() -> None:
    """The include must name its source of truth and its check command."""
    for path in MANAGED:
        block = _block(path)
        for needle in (
            "source-of-truth: docs/governance/ACTIVE_TRACK.yaml",
            "render: python3 scripts/governance/render_active_track_includes.py",
            "--check",
            "newest track verified_at in source:",
        ):
            assert needle in block, f"{path}: managed block missing stamp `{needle}`"


def test_managed_blocks_are_digests_not_full_copies() -> None:
    """The probe's leak channel — a full track-body copy — must stay gone."""
    for path in MANAGED:
        block = _block(path)
        for marker in LEAK_MARKERS:
            assert marker not in block, (
                f"{path}: managed block contains `{marker}` — that is the "
                "full-body portfolio copy the 2026-07 probe flagged as a "
                "leak channel; keep the block a stamped digest"
            )


def test_blocks_say_live_state_is_not_in_markdown() -> None:
    """Quiz item 1: declared intent is not misrepresented as runtime truth."""
    for path in MANAGED:
        block = _block(path)
        assert "Declared intent comes from" in block, path
        assert "docs/governance/ACTIVE_TRACK.yaml" in block, path
        assert "NOT runtime truth" in block, path
        assert "Never answer runtime or liveness questions" in block, path


def test_blocks_carry_ownership_lookup_instruction() -> None:
    """Quiz item 2: owner + verification boundary findable before any edit."""
    for path in MANAGED:
        block = _block(path)
        assert "owns:" in block, path
        assert "Before editing any file" in block, path
        assert "docs/governance/ACTIVE_TRACK.yaml" in block, path


def test_claude_md_states_onboard_trust_boundary() -> None:
    """Quiz item 3: what a completed onboard run does and does not prove."""
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert "What an onboard run does and does not prove" in text
    assert "NOT proof" in text
    assert "not permission to edit" in text
    assert "make agent-build-preflight PACKET=<path>" in text
    assert "make organism-status" in text


def test_session_entry_contract_separates_status_from_admission() -> None:
    """The stable entrypoint stays a short boundary, not a live-state copy."""
    text = SESSION_ENTRY_CONTRACT.read_text(encoding="utf-8")
    for needle in (
        "# Session Entry Contract",
        "`make onboard`",
        "`make agent-build-preflight PACKET=<path>`",
        "`make agent-build-closeout PACKET=<path>`",
        "`make agent-register`",
        "does **not** grant permission to edit",
    ):
        assert needle in text
    assert "<!-- ACTIVE_TRACK:START -->" not in text
    assert "onboard-one-door-2026-07" not in text


def test_docs_agents_md_is_scoped_and_defers() -> None:
    """docs/AGENTS.md declares its lane and points at CLAUDE.md for the rest."""
    text = DOCS_AGENTS_MD.read_text(encoding="utf-8")
    assert "**Scope:**" in text
    assert "owned by `CLAUDE.md`" in text
    # The gate's trust boundary is owned by CLAUDE.md; this file must not
    # grow its own copy of the onboarding section again.
    assert "single remembered gate" not in text
    assert "read-only projection" in text
    assert "owner files win" in text
    assert "trust the output and fix the prose" not in text
    assert "Root `/AGENTS.md`" in text
    assert "tracked minimal entrypoint" in text


def test_suite_evidence_docs_exist() -> None:
    for rel in (
        "docs/governance/CONTEXT_SUITE_MAP.md",
        "docs/governance/CONTEXT_SUITE_LINE_LEDGER.md",
    ):
        assert (REPO_ROOT / rel).exists(), rel
