"""The Darshan editorial pipeline gate, enforced inside required pytest.

An article under reports/darshan/articles/ whose process chain (commission →
dossier → both fires → approval → emissions, per
docs/plans/DARSHAN_EDITORIAL_PIPELINE_2026-08-19.md) is incomplete fails here
— the same required check that blocks broken code from merging."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.darshan.check_darshan_editorial import (  # noqa: E402
    DESKS,
    check_articles_root,
    main,
)

PIPELINE_DOC = REPO_ROOT / "docs/plans/DARSHAN_EDITORIAL_PIPELINE_2026-08-19.md"
CHARTER = REPO_ROOT / "docs/plans/DARSHAN_CHARTER_2026-07-12.md"


def _write_complete_piece(piece: Path, *, desk_ok: bool = True) -> Path:
    piece.mkdir(parents=True)
    (piece / "commission.json").write_text(
        json.dumps(
            {
                "desk": "field-notes" if desk_ok else "growth-hacks",
                "thesis": "One sentence.",
                "why_now": "Because now.",
                "proposed_by": "agent",
                "approved_by": "operator",
                "date": "2026-08-19",
            }
        ),
        encoding="utf-8",
    )
    (piece / "dossier.md").write_text(
        "| register | claim | source |\n|---|---|---|\n"
        "| FACT | the receipt exists | reports/governance/x.md |\n"
        "| HYPOTHESIS | readers will care (test: launch metrics) | - |\n",
        encoding="utf-8",
    )
    (piece / "piece.md").write_text("---\ndesk: field-notes\n---\nBody.\n", encoding="utf-8")
    (piece / "fire_attack.md").write_text("attacked hard.\nVERDICT: SURVIVED\n", encoding="utf-8")
    (piece / "fire_counter.md").write_text("countered hard.\nVERDICT: SURVIVED\n", encoding="utf-8")
    (piece / "approval.json").write_text(
        json.dumps({"approved_by": "operator", "date": "2026-08-19", "notes": ""}),
        encoding="utf-8",
    )
    (piece / "emissions.json").write_text(
        json.dumps({"emissions": [{"type": "research_question", "text": "measure X"}]}),
        encoding="utf-8",
    )
    return piece


def test_desks_mirror_the_charter():
    text = CHARTER.read_text(encoding="utf-8")
    assert "The seven desks" in text
    assert len(DESKS) == 7


def test_pipeline_doc_names_all_stages_and_the_gate():
    text = PIPELINE_DOC.read_text(encoding="utf-8")
    for token in (
        "COMMISSION",
        "DOSSIER",
        "BOTH FIRES",
        "EDITORIAL VERDICT",
        "EMISSIONS",
        "PUBLICATION",
        "KILL WITH SALVAGE",
        "check_darshan_editorial.py",
    ):
        assert token in text, f"pipeline doc lost its {token} stage"


def test_empty_or_absent_articles_tree_is_lawful(tmp_path):
    assert check_articles_root(tmp_path / "nope") == []
    (tmp_path / "articles").mkdir()
    assert check_articles_root(tmp_path / "articles") == []


def test_complete_piece_passes(tmp_path):
    root = tmp_path / "articles"
    _write_complete_piece(root / "field-notes" / "2026-08-19-example")
    assert check_articles_root(root) == []
    assert main([str(root)]) == 0


def test_each_missing_artifact_fails(tmp_path):
    for removed in (
        "commission.json",
        "dossier.md",
        "fire_attack.md",
        "approval.json",
        "emissions.json",
    ):
        root = tmp_path / f"articles_{removed.replace('.', '_')}"
        piece = _write_complete_piece(root / "field-notes" / "2026-08-19-x")
        (piece / removed).unlink()
        assert check_articles_root(root), f"missing {removed} must fail the gate"


def test_unapproved_commission_and_bad_desk_fail(tmp_path):
    root = tmp_path / "articles"
    piece = _write_complete_piece(root / "field-notes" / "2026-08-19-x")
    commission = json.loads((piece / "commission.json").read_text())
    commission["approved_by"] = ""
    (piece / "commission.json").write_text(json.dumps(commission))
    problems = [f.problem for f in check_articles_root(root)]
    assert any("approved_by" in p for p in problems)

    root2 = tmp_path / "articles2"
    bad_desk = root2 / "growth-hacks" / "2026-08-19-x"
    _write_complete_piece(bad_desk)
    problems = [f.problem for f in check_articles_root(root2)]
    assert any("seven desks" in p for p in problems)


def test_fact_without_source_fails(tmp_path):
    root = tmp_path / "articles"
    piece = _write_complete_piece(root / "field-notes" / "2026-08-19-x")
    (piece / "dossier.md").write_text(
        "| register | claim | source |\n|---|---|---|\n| FACT | uncited claim | |\n",
        encoding="utf-8",
    )
    problems = [f.problem for f in check_articles_root(root)]
    assert any("FACT claim row without a source" in p for p in problems)


def test_killed_fire_verdict_requires_kill_record(tmp_path):
    root = tmp_path / "articles"
    piece = _write_complete_piece(root / "field-notes" / "2026-08-19-x")
    (piece / "fire_attack.md").write_text("fatal.\nVERDICT: KILLED\n", encoding="utf-8")
    problems = [f.problem for f in check_articles_root(root)]
    assert any("double-survivor" in p for p in problems)


def test_killed_piece_needs_salvage(tmp_path):
    root = tmp_path / "articles"
    piece = root / "field-notes" / "2026-08-19-killed"
    piece.mkdir(parents=True)
    (piece / "commission.json").write_text(
        json.dumps(
            {
                "desk": "field-notes",
                "thesis": "t",
                "why_now": "w",
                "proposed_by": "a",
                "approved_by": "operator",
                "date": "2026-08-19",
            }
        )
    )
    (piece / "killed.json").write_text(
        json.dumps({"stage": "both_fires", "reason": "framing died", "salvage": ""})
    )
    problems = [f.problem for f in check_articles_root(root)]
    assert any("salvage" in p for p in problems)

    (piece / "killed.json").write_text(
        json.dumps(
            {"stage": "both_fires", "reason": "framing died", "salvage": "keep the metaphor"}
        )
    )
    assert check_articles_root(root) == []


def test_repo_articles_tree_is_lawful_right_now():
    """The live gate: every committed Darshan article obeys the pipeline."""
    root = REPO_ROOT / "reports/darshan/articles"
    findings = check_articles_root(root)
    assert not findings, "\n".join(str(f) for f in findings)
