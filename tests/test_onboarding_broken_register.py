from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_PARSER_PATH = (
    REPO_ROOT / "dharma_swarm/operator_core/onboarding/broken_register.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "_dharma_broken_register_test",
    _PARSER_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_PARSER = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _PARSER
_SPEC.loader.exec_module(_PARSER)

find_broken_register_references = _PARSER.find_broken_register_references
parse_broken_register = _PARSER.parse_broken_register
parse_broken_register_text = _PARSER.parse_broken_register_text
validate_broken_register_references = _PARSER.validate_broken_register_references


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
### BR-004 (REOPENED 2026-07-11) — heading lifecycle
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


def test_entries_before_first_lifecycle_section_are_excluded() -> None:
    result = parse_broken_register_text(
        """# BROKEN REGISTER
### BR-900 — introductory example, not a register occurrence
- **status:** OPEN
## OPEN ITEMS (1 open/partial)
### BR-001 — current defect
- **status:** OPEN
"""
    )

    assert set(result.by_id) == {"BR-001"}
    assert (result.total, result.open_count, result.closed_count) == (1, 1, 0)


def test_entry_outside_lifecycle_section_is_diagnostic() -> None:
    result = parse_broken_register_text(
        """# BROKEN REGISTER
## OPEN ITEM
### BR-900 — singular near-miss section must not admit an entry
- **status:** OPEN
"""
    )

    outside = [
        diagnostic
        for diagnostic in result.diagnostics
        if diagnostic.code == "entry_outside_lifecycle_section"
    ]
    assert result.entries == ()
    assert len(outside) >= 1
    assert outside[0].br_id == "BR-900"


def test_non_lifecycle_h2_does_not_open_register_section() -> None:
    result = parse_broken_register_text(
        """# BROKEN REGISTER
## OPEN SOURCE NOTES
### BR-900 — example mentioned in notes
- **status:** OPEN
## OPEN ITEMS (1 open/partial)
### BR-001 — current defect
- **status:** OPEN
"""
    )

    assert set(result.by_id) == {"BR-001"}
    assert (result.total, result.open_count, result.closed_count) == (1, 1, 0)


def test_prose_heading_does_not_supply_lifecycle() -> None:
    result = parse_broken_register_text(
        """## OPEN ITEMS (0 open/partial)
### BR-003 — OPEN source documentation mentions this example
- **severity:** DEGRADED
"""
    )

    entry = result.by_id["BR-003"]
    assert entry.status == "UNKNOWN"
    assert entry.is_open_like is False
    assert _diagnostic_codes(entry) == {"missing_current_status"}


def test_closed_and_fixed_metadata_are_equivalent() -> None:
    for heading_status, field_status in (("CLOSED", "FIXED"), ("FIXED", "CLOSED")):
        result = parse_broken_register_text(
            f"""## OPEN ITEMS (0 open/partial)
### BR-003 ({heading_status} 2026-07-13) — resolved defect
- **status:** {field_status} 2026-07-13 — independently verified
"""
        )

        entry = result.by_id["BR-003"]
        assert entry.status == field_status
        assert entry.is_closed_like is True
        assert "contradictory_lifecycle" not in _diagnostic_codes(entry)


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
### BR-003 (REOPENED) — contradictory metadata
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
        ("BR-022", "PARTIAL"),
        ("BR-023", "PARTIAL"),
        ("BR-004", "PARTIAL"),
        ("BR-005", "PARTIAL"),
        ("BR-013", "PARTIAL"),
        ("BR-014", "OPEN"),
    ]
    assert sum(len(entry.history) for entry in result.entries) == 27


def test_sovereign_manifest_verified_metric_rows_are_unique() -> None:
    manifest = (
        REPO_ROOT / "docs/governance/SOVEREIGN_MANIFEST.md"
    ).read_text(encoding="utf-8")
    start = manifest.index("## VERIFIED NUMBERS")
    end = manifest.index("## SYSTEM TOPOGRAPHY", start)
    labels = [
        line.split("|", 2)[1].strip()
        for line in manifest[start:end].splitlines()
        if line.startswith("| ") and not line.startswith("| Metric ")
    ]

    assert len(labels) == len(set(labels)), labels
    assert labels.count("Tests collected (pytest)") == 1
    assert labels.count("Collection errors") == 1


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


def test_agent_onboard_remains_importable_before_dependency_bootstrap(
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "minimal-onboard-repo"
    fixture_files = (
        "scripts/governance/agent_onboard.py",
        "dharma_swarm/operator_core/onboarding/broken_register.py",
    )
    for relative in fixture_files:
        source = REPO_ROOT / relative
        target = fixture_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-I",
            "-S",
            str(fixture_root / "scripts/governance/agent_onboard.py"),
            "--help",
        ],
        cwd=fixture_root,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert "--fast" in result.stdout
    assert not list(fixture_root.rglob("__pycache__"))
    assert not list(fixture_root.rglob("*.pyc"))


def test_header_count_drift_is_reported() -> None:
    result = parse_broken_register_text(
        """# BROKEN REGISTER
## OPEN ITEMS (1 open/partial)
### BR-001 — first open item
- **status:** OPEN
### BR-002 — second open-like item
- **status:** PARTIAL
## CLOSED ITEMS
"""
    )
    drift = [
        item for item in result.diagnostics
        if item.code == "open_header_count_drift"
    ]

    assert result.declared_open_count == 1
    assert result.open_count == 2
    assert len(drift) == 1
    assert "declares 1" in drift[0].message
    assert "observed 2" in drift[0].message


def test_header_count_and_br007_map_match_canonical_truth() -> None:
    register_path = REPO_ROOT / "docs/state/BROKEN_REGISTER.md"
    result = parse_broken_register(register_path)
    register_text = register_path.read_text(encoding="utf-8")
    mismatch_map = (REPO_ROOT / "INTERFACE_MISMATCH_MAP.md").read_text(
        encoding="utf-8"
    )
    br007_row = next(
        line for line in mismatch_map.splitlines()
        if line.startswith("| BR-007:")
    )

    assert result.declared_open_count == result.open_count == 9
    assert not any(
        item.code == "open_header_count_drift"
        for item in result.diagnostics
    )
    assert "REOPENED" in br007_row
    assert "✅ RESOLVED" not in br007_row
    assert "operator-Mac host-local witness" in br007_row
    assert "Clean clone/CI and other seats remain Unobserved" in br007_row
    assert "evidence (host-local witness" in register_text
    assert "sqlite3 -readonly ~/.dharma/ontology.db" in register_text
    assert (
        "Clean clone/CI and every other seat remain **Unobserved**"
        in register_text
    )


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


def _run_dependency_free_control(argv: list[str]) -> int:
    if argv == ["--negative-malformed"]:
        test_incidental_status_words_do_not_classify()
        test_duplicate_current_status_is_diagnostic()
        test_entry_outside_lifecycle_section_is_diagnostic()
        test_header_count_drift_is_reported()
        return 0
    if argv == ["--negative-orphan"]:
        test_drift_triage_br_ids_resolve()
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_run_dependency_free_control(sys.argv[1:]))
