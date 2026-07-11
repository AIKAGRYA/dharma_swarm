from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from dharma_swarm.operator_core.onboarding.broken_register import (
    find_broken_register_references,
    parse_broken_register,
    parse_broken_register_text,
    validate_broken_register_references,
)


REPO_ROOT = Path(__file__).resolve().parents[1]

LEGACY_CONSUMER_MATRIX = {
    "agent_onboard": (27, 9, 8),
    "orientation_graph": 17,
    "trust_gate_status": (27, 9, 8),
    "repo_status": (22, 10),
    "control_surface": 8,
    "operator_coherence": 19,
}


def _diagnostic_codes(value: object) -> set[str]:
    return {diagnostic.code for diagnostic in value.diagnostics}


def test_status_markup_and_section_matrix() -> None:
    result = parse_broken_register_text(
        """# register
## OPEN ITEMS (3 open/partial)
### BR-001 — plain status
status: OPEN
### BR-002 — bullet bold status
- **status:** PARTIAL — still active
### BR-003 — bold value
**status:** **FIXED 2026-07-11** — done
### BR-004 — REOPENED 2026-07-11 — heading lifecycle
### BR-005 (CLOSED 2026-07-11) — heading closed
## STALE-CLAIM CORRECTIONS
### BR-999 — must not parse
- **status:** OPEN
## CLOSED ITEMS
### BR-006 — historical membership fallback
"""
    )

    assert set(result.by_id) == {
        "BR-001", "BR-002", "BR-003", "BR-004", "BR-005", "BR-006",
    }
    assert {br_id: result.by_id[br_id].status for br_id in result.by_id} == {
        "BR-001": "OPEN",
        "BR-002": "PARTIAL",
        "BR-003": "FIXED",
        "BR-004": "OPEN",
        "BR-005": "CLOSED",
        "BR-006": "CLOSED",
    }
    assert (result.total, result.open_count, result.closed_count) == (6, 3, 3)


def test_reopened_id_wins_over_closed_history() -> None:
    result = parse_broken_register_text(
        """## OPEN ITEMS (1 open/partial)
### BR-007 — REOPENED — current truth
- **status:** OPEN
## CLOSED ITEMS
### BR-007 (CLOSED 2026-05-10) — disproven closure
"""
    )

    entry = result.by_id["BR-007"]
    assert entry.status == "OPEN"
    assert entry.is_open_like is True
    assert [item.section for item in entry.history] == ["current", "closed"]
    assert [item.status for item in entry.history] == ["OPEN", "CLOSED"]


def test_incidental_status_words_do_not_classify() -> None:
    result = parse_broken_register_text(
        """## OPEN ITEMS (0 open/partial)
### BR-003 — Apply gate present but closed in prose
- **severity:** BLOCKER
- **root_cause:** FIXED and PARTIAL appear here, but no anchored lifecycle exists.
- **evidence:** the degraded stale path is still discussed.
"""
    )

    entry = result.by_id["BR-003"]
    assert entry.status == "UNKNOWN"
    assert entry.is_open_like is False
    assert _diagnostic_codes(entry) == {"missing_current_status"}


def test_section_and_heading_prose_boundaries() -> None:
    result = parse_broken_register_text(
        """### BR-900 — preamble must remain outside lifecycle sections
- **status:** OPEN
## OPEN ITEMS (1 open/partial)
### BR-001 — Open source dependency is stale
- **severity:** BLOCKER
### BR-002 — REOPENED 2026-07-11 — explicit heading metadata
### BR-003 (CLOSED 2026-07-11) — explicit parenthesized metadata
"""
    )

    assert "BR-900" not in result.by_id
    assert result.by_id["BR-001"].status == "UNKNOWN"
    assert _diagnostic_codes(result.by_id["BR-001"]) == {
        "missing_current_status",
    }
    assert result.by_id["BR-002"].status == "OPEN"
    assert result.by_id["BR-003"].status == "CLOSED"


def test_duplicate_current_status_is_diagnostic() -> None:
    duplicate_field = parse_broken_register_text(
        """## OPEN ITEMS (0 open/partial)
### BR-001 — duplicate status field
- **status:** OPEN
- **status:** FIXED
"""
    ).by_id["BR-001"]
    assert duplicate_field.status == "UNKNOWN"
    assert "duplicate_status_field" in _diagnostic_codes(duplicate_field)

    duplicate_entry = parse_broken_register_text(
        """## OPEN ITEMS (0 open/partial)
### BR-002 — first current occurrence
- **status:** OPEN
### BR-002 — second current occurrence
- **status:** PARTIAL
"""
    ).by_id["BR-002"]
    assert duplicate_entry.status == "UNKNOWN"
    assert "duplicate_current_entry" in _diagnostic_codes(duplicate_entry)

    contradiction = parse_broken_register_text(
        """## OPEN ITEMS (0 open/partial)
### BR-003 — REOPENED — contradictory metadata
- **status:** FIXED
"""
    ).by_id["BR-003"]
    assert contradiction.status == "UNKNOWN"
    assert "contradictory_lifecycle" in _diagnostic_codes(contradiction)


def test_current_register_canonical_counts() -> None:
    result = parse_broken_register(REPO_ROOT / "docs/state/BROKEN_REGISTER.md")

    assert result.present is True
    assert (result.total, result.open_count, result.closed_count, result.unknown_count) == (
        22, 9, 13, 0,
    )
    assert [(entry.id, entry.status) for entry in result.open_entries] == [
        ("BR-007", "OPEN"),
        ("BR-003", "PARTIAL"),
        ("BR-021", "WORKAROUND"),
        ("BR-022", "OPEN"),
        ("BR-023", "PARTIAL"),
        ("BR-004", "PARTIAL"),
        ("BR-005", "PARTIAL"),
        ("BR-013", "PARTIAL"),
        ("BR-014", "OPEN"),
    ]
    assert sum(len(entry.history) for entry in result.entries) == 27


def test_legacy_consumer_parity_vector_documents_intentional_deltas() -> None:
    result = parse_broken_register(REPO_ROOT / "docs/state/BROKEN_REGISTER.md")

    assert LEGACY_CONSUMER_MATRIX == {
        "agent_onboard": (27, 9, 8),
        "orientation_graph": 17,
        "trust_gate_status": (27, 9, 8),
        "repo_status": (22, 10),
        "control_surface": 8,
        "operator_coherence": 19,
    }
    assert (result.total, result.open_count, result.closed_count) == (22, 9, 13)
    assert LEGACY_CONSUMER_MATRIX["agent_onboard"] != (22, 9, 13)
    assert LEGACY_CONSUMER_MATRIX["orientation_graph"] != 9
    assert LEGACY_CONSUMER_MATRIX["repo_status"] != (22, 9)
    assert LEGACY_CONSUMER_MATRIX["control_surface"] != 9
    assert LEGACY_CONSUMER_MATRIX["operator_coherence"] != 9


def test_control_surface_public_shape_is_unchanged() -> None:
    from dharma_swarm.operator_core.control_surface_models import ControlSurfaceRow

    row = ControlSurfaceRow(id="test", kind="broken_register", label="BR-001")

    assert set(row.to_dict()) == {
        "id",
        "kind",
        "label",
        "authority_role",
        "declared_state",
        "desired_state",
        "observed_state",
        "coherence_state",
        "priority",
        "owner_module",
        "truth_owner",
        "evidence",
        "evidence_labels",
        "freshness",
        "gap_codes",
        "next_action",
        "human_decision_required",
        "human_decision",
        "source_refs",
        "source_ref_labels",
        "verification_timeline",
        "display_hints",
        "raw",
    }


def test_all_six_consumers_share_canonical_parser() -> None:
    from dharma_swarm.operator_core import control_surface
    from dharma_swarm.operator_core.operator_coherence.base import ProbeContext
    from dharma_swarm.operator_core.operator_coherence.git_governance import (
        _probe_governance,
    )
    from scripts.governance import (
        agent_onboard,
        orientation_graph,
        repo_status,
        trust_gate_status,
    )

    onboard = agent_onboard._parse_broken_register()
    assert (onboard["total"], onboard["open_count"], onboard["closed_count"]) == (
        22, 9, 13,
    )
    assert len(orientation_graph.build_broken()) == 9
    assert trust_gate_status.parse_broken_counts(
        REPO_ROOT / "docs/state/BROKEN_REGISTER.md"
    ) == (22, 9, 13)
    assert repo_status._count_broken_register() == (22, 9)
    assert len(control_surface._broken_register_rows(REPO_ROOT)) == 9
    cockpit = _probe_governance(
        ProbeContext(
            repo_root=REPO_ROOT,
            include_github=False,
            include_live_probes=False,
        )
    )
    assert cockpit["broken_register"]["open_like_count"] == 9

    consumers = (
        "scripts/governance/agent_onboard.py",
        "scripts/governance/orientation_graph.py",
        "scripts/governance/trust_gate_status.py",
        "scripts/governance/repo_status.py",
        "dharma_swarm/operator_core/control_surface.py",
        "dharma_swarm/operator_core/operator_coherence/git_governance.py",
    )
    for relative in consumers:
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert (
            "onboarding.broken_register import" in source
            or "onboarding/broken_register.py" in source
        ), relative
        assert "parse_broken_register(" in source, relative


def test_agent_onboard_remains_importable_before_dependency_bootstrap() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(REPO_ROOT / "scripts/governance/agent_onboard.py"),
            "--help",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert "--fast" in result.stdout


def test_header_count_drift_is_reported() -> None:
    result = parse_broken_register(REPO_ROOT / "docs/state/BROKEN_REGISTER.md")
    drift = [
        item for item in result.diagnostics
        if item.code == "open_header_count_drift"
    ]

    assert result.declared_open_count == 7
    assert len(drift) == 1
    assert "declares 7" in drift[0].message
    assert "observed 9" in drift[0].message


def test_drift_triage_br_ids_resolve() -> None:
    result = parse_broken_register(REPO_ROOT / "docs/state/BROKEN_REGISTER.md")
    triage_source = (
        REPO_ROOT / "dharma_swarm/dhyana/drift_triage.py"
    ).read_text(encoding="utf-8")
    references = find_broken_register_references(triage_source)

    assert references == ("BR-003", "BR-004", "BR-005", "BR-013")
    assert validate_broken_register_references(
        result, references, source="dharma_swarm/dhyana/drift_triage.py"
    ) == ()
    orphan = validate_broken_register_references(
        result, ("BR-999",), source="negative-control"
    )
    assert len(orphan) == 1
    assert orphan[0].code == "orphan_reference"
    assert orphan[0].br_id == "BR-999"
