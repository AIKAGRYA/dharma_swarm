"""Stage 0 fixtures — the citation validator must catch each drift class.

Every fixture is synthetic and self-contained. Live-artifact defect counts are
deliberately NOT pinned here: a test that asserts today's brokenness would go
red the moment the text is repaired, which is backwards.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "scripts" / "docops"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

spec = importlib.util.spec_from_file_location(
    "vision_citations", str(SCRIPT_DIR / "vision_citations.py")
)
assert spec is not None and spec.loader is not None
vc = importlib.util.module_from_spec(spec)
sys.modules["vision_citations"] = vc
spec.loader.exec_module(vc)


OWNER = """# Owner

## 1. First section

alpha body

## II. Roman section

### Axis 3: Constraint Enables Emergence

beta body

### 3.1 Dotted subsection

gamma body
"""


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "owner.md").write_text(OWNER, encoding="utf-8")
    return tmp_path


def severities(findings) -> set[str]:
    return {finding.severity for finding in findings}


def test_resolver_handles_numeric_roman_dotted_and_titled_headings() -> None:
    for name in ("1", "II", "Axis 3", "3.1"):
        assert vc.find_section(OWNER, name) is not None, name
    assert vc.find_section(OWNER, "Nonexistent Section") is None


def test_pinned_citation_passes_when_span_hash_matches(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    span = vc.find_section(OWNER, "1")
    text = f"claim [docs/owner.md §1 #{vc.sha12_of(span)}]\n"
    assert vc.audit_text(repo, text, "T1") == []


def test_pinned_citation_drifts_when_owner_span_changes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    span = vc.find_section(OWNER, "1")
    text = f"claim [docs/owner.md §1 #{vc.sha12_of(span)}]\n"
    (repo / "docs" / "owner.md").write_text(
        OWNER.replace("alpha body", "alpha body, silently edited"), encoding="utf-8"
    )
    findings = vc.audit_text(repo, text, "T1")
    assert severities(findings) == {"DRIFTED"}


def test_missing_path_is_broken(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    findings = vc.audit_text(repo, "claim [docs/nope.md §1 #000000000000]\n", "T1")
    assert severities(findings) == {"BROKEN"}


def test_unresolvable_section_is_broken(tmp_path: Path) -> None:
    """The live defect class: a compound reference that looks precise (§II.4)
    but names no heading in the owner document."""
    repo = _repo(tmp_path)
    findings = vc.audit_text(repo, "claim [docs/owner.md §II.4]\n", "T2")
    assert severities(findings) == {"BROKEN"}


def test_section_range_is_unpinnable(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    findings = vc.audit_text(repo, "claim [docs/owner.md §1–§II]\n", "T1")
    assert severities(findings) == {"UNPINNABLE"}


def test_resolvable_but_unpinned_is_reported(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    findings = vc.audit_text(repo, "claim [docs/owner.md §1]\n", "T1")
    assert severities(findings) == {"UNPINNED"}


def test_absent_external_source_is_flagged_never_trusted(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    findings = vc.audit_text(repo, "claim [off-repo: ~/nope/absent.md §Whatever]\n", "T1")
    assert severities(findings) == {"FLAGGED"}


def test_declared_projection_is_allowed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert vc.audit_text(repo, "claim [PROJECTION: agent-authored placement]\n", "T1") == []


def test_semicolon_separated_citations_are_parsed_individually(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    span = vc.find_section(OWNER, "1")
    text = f"claim [docs/owner.md §1 #{vc.sha12_of(span)}; docs/nope.md §1 #000000000000]\n"
    findings = vc.audit_text(repo, text, "T2")
    assert severities(findings) == {"BROKEN"}
    assert len(findings) == 1


def test_markdown_links_are_not_treated_as_citations(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert vc.audit_text(repo, "see [the owner](docs/owner.md) for detail\n", "T1") == []


def test_ledger_labels_are_not_treated_as_citations(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert vc.audit_text(repo, "status [OPEN-4] and [naming-ritual]\n", "T2") == []
