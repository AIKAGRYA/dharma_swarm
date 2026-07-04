from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "governance" / "check_naga_spec_constraints.py"


def load_module():
    spec = importlib.util.spec_from_file_location("check_naga_spec_constraints", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def clean_core() -> str:
    return """# Core

## Lineage

NAGA-IR is a dialect-level assurance IR in the MLIR verif family and not a rename of ETH Nagini. Nagini output lifts into NAGA-IR as `Proven_by` evidence. [confidence: 96/100] [Nagini](https://example.com/nagini)

## Canonization

Canonization is bounded by evidence horizon, trust base, and TTL. It is not a claim that no morphism to bottom exists. [confidence: 96/100]

## Sunyata

The technical rendering is that no claim has authority by svabhava, only through context, witness, trust base, freshness, and unresolved-challenge status. [confidence: 95/100]

## Kernel

The future `packages/telos-kernel/` TCB ceiling is <= 5000 LOC. [confidence: 90/100]

## Wall

Cursor owns the acceleration of authorship. Dharma owns the conservation of authority.

A code change is not authoritative because it exists, or because an agent produced it, or because CI passed. It is authoritative only when its claim is inhabited by admissible evidence, under a known trust base, inside a live context, without unresolved challenge.
"""


def write_triple(tmp_path: Path, *, core: str | None = None, witness: str = "") -> Path:
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    (spec_dir / "core.md").write_text(core if core is not None else clean_core(), encoding="utf-8")
    (spec_dir / "receipt_wire.md").write_text("# Wire\n\n## Shape\n\nA shape note.\n", encoding="utf-8")
    (spec_dir / "witness_mesh.md").write_text("# Mesh\n\n## Role\n\nA mesh note.\n" + witness, encoding="utf-8")
    return spec_dir


def run_checker(tmp_path: Path, *, core: str | None = None, witness: str = ""):
    module = load_module()
    spec_dir = write_triple(tmp_path, core=core, witness=witness)
    return module.main([str(spec_dir)])


def test_clean_triple_passes(tmp_path, capsys):
    assert run_checker(tmp_path) == 0
    captured = capsys.readouterr()
    assert "wall_sentences: 0 violations" in captured.out


@pytest.mark.parametrize(
    ("injection", "diagnostic"),
    [
        ("Emoji here 🙂.\n", "emoji"),
        ("Fullwidth bang here！\n", "exclamation"),
        ("This prose uses *italic* markup.\n", "italics"),
        ("This prose uses _italic_ markup.\n", "italics"),
        ("Footnote prose [^bad].\n", "footnote_refs"),
        ("## One two three four five six seven\n", "header"),
        ("Madhyamaka is literally the same object as category theory.\n", "isomorphism_overclaim"),
        ("sunyata is the terminal object.\n", "sunyata_terminal"),
        ("Canonization means no morphism to bottom exists.\n", "unbounded_canonization"),
        ("NAGA-IR is a rename of Nagini.\n", "nagini_conflation"),
        ("Moltbook supports this authority model. [confidence: 95/100] [Moltbook](https://example.com)\n", "moltbook_load_bearing"),
    ],
)
def test_planted_constraint_violations_fail(tmp_path, capsys, injection, diagnostic):
    core = clean_core() + "\n## Extra\n\n" + injection
    assert run_checker(tmp_path, core=core) == 1
    captured = capsys.readouterr()
    assert diagnostic in captured.err
    assert "core.md:" in captured.err


def test_missing_tcb_ceiling_fails(tmp_path, capsys):
    core = clean_core().replace(" TCB ceiling is <= 5000 LOC", " is planned")
    assert run_checker(tmp_path, core=core) == 1
    captured = capsys.readouterr()
    assert "tcb_ceiling" in captured.err


def test_missing_bounded_canonization_fails(tmp_path, capsys):
    core = clean_core().replace("Canonization is bounded by evidence horizon, trust base, and TTL.", "Canonization is stable when reviewed.")
    assert run_checker(tmp_path, core=core) == 1
    captured = capsys.readouterr()
    assert "bounded_canonization" in captured.err


def test_missing_wall_sentence_fails(tmp_path, capsys):
    core = clean_core().replace("Cursor owns the acceleration of authorship. Dharma owns the conservation of authority.", "")
    assert run_checker(tmp_path, core=core) == 1
    captured = capsys.readouterr()
    assert "wall_sentence_1" in captured.err


def test_bold_and_inline_code_are_not_italics(tmp_path):
    core = clean_core() + "\n## Formatting\n\nThe `claim_hash_value` field and **bold term** are allowed.\n"
    assert run_checker(tmp_path, core=core) == 0


def test_code_block_prose_rules_are_excluded(tmp_path):
    core = clean_core() + "\n## Example\n\n```text\n*not italic prose*\n[^not-a-prose-footnote]\n```\n"
    assert run_checker(tmp_path, core=core) == 0


def test_single_file_violation_reports_file(tmp_path, capsys):
    assert run_checker(tmp_path, witness="\n## Bad\n\nWitness has ⚠.\n") == 1
    captured = capsys.readouterr()
    assert "witness_mesh.md:" in captured.err
    assert "emoji" in captured.err
