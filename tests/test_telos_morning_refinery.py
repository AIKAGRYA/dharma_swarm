"""Contract tests for the TELOS Morning Refinery design surface.

These are intentionally document-level tests for the current seed track. They
protect the privacy/order boundary before any product implementation exists.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _compact(text: str) -> str:
    return " ".join(text.split())


def test_telos_product_surface_is_registered_without_claiming_receipt() -> None:
    product = _read("PRODUCT_SURFACE.md")
    compact = _compact(product)

    assert "TELOS Morning Refinery" in product
    assert "/dashboard/telos" in product
    assert "not yet a public product claim" in compact
    assert "has no external receipt" in compact
    assert "must not introduce a parallel GUI" in compact


def test_noetic_pass_precedes_empire_pass() -> None:
    spec = _read("docs/vision_maps/TELOS_MORNING_REFINERY_V0.md")
    compact = _compact(spec)

    noetic_idx = spec.index("Essence / Noetic Agents")
    empire_idx = spec.index("Empire / Idea-Portfolio Agents")

    assert noetic_idx < empire_idx
    assert "Empire agents never read raw morning pages" in compact
    assert "The first council protects depth and source truth." in compact
    assert "The second council turns hardened essence into outward options." in compact


def test_consent_boundary_defaults_private_and_blocks_raw_upward_flow() -> None:
    spec = _read("docs/vision_maps/TELOS_MORNING_REFINERY_V0.md")

    assert "raw_shared: false" in spec
    assert "Default is `private`" in spec
    assert "never raw morning pages or identifiable vectors flow upward" in spec
    assert "It must not secretly connect raw souls to markets" in spec


def test_empire_agents_are_second_stage_portfolio_screeners() -> None:
    empire = _read("docs/research/telos_ai/empire_agents/README.md")

    assert "second stage only" in empire
    assert "They do not read raw morning pages" in empire
    assert "100-300 IdeaSeed candidates" in empire
    assert "15 bull agents" in empire
    assert "15 bear agents" in empire
    assert "Portfolio / Quality-Diversity Curator" in empire
    assert "A receipt template is not a receipt" in empire


def test_external_action_operator_packet_is_not_the_receipt() -> None:
    packet_path = REPO_ROOT / "reports/telos_ai/EXTERNAL_ACTION_OPERATOR_PACKET_2026-06-30.md"
    first_receipt_path = REPO_ROOT / "reports/telos_ai/FIRST_EXTERNAL_ACTED_RECEIPT.md"
    packet = packet_path.read_text(encoding="utf-8")
    compact = _compact(packet)

    assert packet_path.exists()
    assert not first_receipt_path.exists()
    assert "operator handoff only; not an external acted receipt" in compact
    assert "This operator packet is not a receipt" in compact
    assert "Do not mark the TELOS active track shippable from this packet alone." in packet
    assert "Raw morning-page text" in packet
    assert "external human action exists" in packet


def test_sanitized_external_output_candidate_is_safe_but_unacted() -> None:
    candidate_path = REPO_ROOT / "reports/telos_ai/SANITIZED_EXTERNAL_OUTPUT_CANDIDATE_2026-06-30.md"
    packet = _read("reports/telos_ai/EXTERNAL_ACTION_OPERATOR_PACKET_2026-06-30.md")
    candidate = candidate_path.read_text(encoding="utf-8")
    compact = _compact(candidate)

    assert candidate_path.exists()
    assert "SANITIZED_EXTERNAL_OUTPUT_CANDIDATE_2026-06-30.md" in packet
    assert "ready-to-review candidate only; not sent; not acted" in compact
    assert "public/spec-derived TELOS concept note" in compact
    assert "Private source material:** none included" in candidate
    assert "not `reports/telos_ai/FIRST_EXTERNAL_ACTED_RECEIPT.md`" in candidate
    assert "No external human action has been performed" in candidate

    forbidden_markers = (
        "/Users/dhyana/.dharma/telos/raw",
        "working_source_ref:",
        "raw_source_ref:",
        "source_original_typo_preserving",
        "credential:",
    )
    for marker in forbidden_markers:
        assert marker not in candidate


def test_telos_external_receipt_gate_requires_acted_receipt_predicate() -> None:
    active_track = _read("docs/governance/ACTIVE_TRACK.yaml")
    compact = _compact(active_track)

    assert "id: first_external_receipt_exists kind: external_acted_receipt" in compact
    assert "file: reports/telos_ai/FIRST_EXTERNAL_ACTED_RECEIPT.md" in compact
