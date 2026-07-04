from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


naga_constraints = _load(
    "naga_spec_constraint_check",
    REPO_ROOT / "scripts/governance/naga_spec_constraint_check.py",
)


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "mini.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_clean_mini_spec_passes(tmp_path):
    path = _write(
        tmp_path,
        """# Mini

Status: draft

## Clean Claim

MiniSpec defines a bounded receipt predicate. [confidence: 99/100]
The measured object is `receipt`; the threshold is one admissible modality. [confidence: 99/100] [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785)

## Local Integration

`packages/telos-kernel/` is a planned target with TCB <= 5000 LOC. [confidence: 90/100]
""",
    )

    assert naga_constraints.main([str(path)]) == 0


def test_emoji_violation_flagged_with_line(tmp_path, capsys):
    path = _write(
        tmp_path,
        """# Mini

## Clean Claim

This sentence contains an emoji 🙂. [confidence: 90/100]
""",
    )

    assert naga_constraints.main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "mini.md:5" in out
    assert "NAGA-FMT-EMOJI" in out


def test_single_asterisk_emphasis_flagged(tmp_path, capsys):
    path = _write(
        tmp_path,
        """# Mini

## Clean Claim

This has *italic emphasis*. [confidence: 90/100]
""",
    )

    assert naga_constraints.main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "mini.md:5" in out
    assert "NAGA-FMT-ITALIC" in out


def test_long_header_flagged(tmp_path, capsys):
    path = _write(
        tmp_path,
        """# Mini

## One Two Three Four Five Six Seven

MiniSpec defines a bounded receipt predicate. [confidence: 99/100]
""",
    )

    assert naga_constraints.main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "mini.md:3" in out
    assert "NAGA-FMT-HEADER" in out


def test_tcb_ceiling_gap_flagged(tmp_path, capsys):
    path = _write(
        tmp_path,
        """# Mini

## Local Integration

The proposal adds `packages/telos-kernel/` as a verifier target. [confidence: 90/100]
""",
    )

    assert naga_constraints.main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "mini.md:5" in out
    assert "NAGA-CONSTRAINT-TCB" in out
