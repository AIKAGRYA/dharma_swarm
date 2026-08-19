"""Protect the operator-confirmed source record without promoting it to canon."""

from pathlib import Path


VISION_RECORD = (
    Path(__file__).resolve().parents[2]
    / "docs/plans/2026-07-13_dharma_entelechy_vision_synthesis.md"
)

REQUIRED_DIRECTION_ANCHORS = (
    "Operator-confirmed pre-ratification direction",
    "pre-constitutional",
    "### Explicitly reserved: wealth remains open",
    "does **not** direct this record to narrow, replace, or adjudicate",
    "It grants no present spending, trading, outreach,",
    "### The first compounding organ: Code Quality Foundry",
    "`campaign_base_sha`",
    "`reviewed_final_main_sha`",
    "at least ten declared model/version identities",
    "never transmitted to a remote model provider",
    "aggregate live exposure across",
)


def direction_record_violations(text: str) -> list[str]:
    """Return missing record anchors; kept stdlib-only for the packet oracle."""
    required = (
        *REQUIRED_DIRECTION_ANCHORS,
        "**Document role:** `report`",
        "no runtime or governance authority",
        "**Subordinate to:** `docs/governance/SOVEREIGN_MANIFEST.md`",
    )
    return [anchor for anchor in required if anchor not in text]


def test_preconstitutional_direction_record_keeps_confirmed_boundaries() -> None:
    text = VISION_RECORD.read_text(encoding="utf-8")
    violations = direction_record_violations(text)

    assert not violations, f"pre-constitutional direction violations: {violations}"
