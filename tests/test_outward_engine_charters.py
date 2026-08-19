"""Constitutional anchors for the outward engine (Lane 2/3)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEPENDENCE = REPO_ROOT / "docs" / "governance" / "INDEPENDENCE_CHARTER.md"
CONTINUITY = REPO_ROOT / "docs" / "governance" / "CONTINUITY_OF_INTENT.md"


def test_independence_charter_pins_unconflicted_auditor_rules() -> None:
    text = INDEPENDENCE.read_text(encoding="utf-8")
    lower = text.lower()
    assert "never audit systems we build" in lower
    assert "never suppress failed invariant logs" in lower
    assert "all misses are published" in lower
    assert "2,500" in text or "2500" in text
    assert "flat" in lower
    assert "decoupled from audit outcome" in lower
    assert "dharma_swarm" in lower
    assert "vibe-halt" in lower


def test_continuity_of_intent_pins_telos_rings_and_silence_halt() -> None:
    text = CONTINUITY.read_text(encoding="utf-8")
    lower = text.lower()
    assert "jagat kalyan" in lower
    assert "krishna" in lower
    assert "arjuna" in lower
    assert "3-ring" in lower or "three-ring" in lower or "three ring" in lower
    assert "fail-closed" in lower or "fail closed" in lower
    assert "30 days" in lower or "thirty days" in lower
    assert "no human" in lower or "human input" in lower
    assert "publish_public_ledger.py" in text
    assert "generate_client_report.py" in text
    assert INDEPENDENCE.name in text
