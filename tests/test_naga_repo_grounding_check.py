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


naga_grounding = _load(
    "naga_repo_grounding_check",
    REPO_ROOT / "scripts/governance/naga_repo_grounding_check.py",
)


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "mini.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_clean_repo_claims_pass(tmp_path):
    path = _write(
        tmp_path,
        """# Mini

## Local Integration

The current checkout contains `scripts/governance/assurance_boundary.py` and `dharma_swarm/coalgebra.py`. [confidence: 98/100]
`packages/telos-kernel/` is a planned future integration target. [confidence: 90/100]
`sab_client.py` exports SABContribution packets, not receipts. [confidence: 92/100]
""",
    )

    assert naga_grounding.main([str(path)]) == 0


def test_assurance_boundary_absent_claim_blocked(tmp_path, capsys):
    path = _write(
        tmp_path,
        """# Mini

## Local Integration

The checkout does not currently contain `scripts/governance/assurance_boundary.py`. [confidence: 99/100]
""",
    )

    assert naga_grounding.main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "mini.md:5" in out
    assert "assurance_boundary.py" in out


def test_bisimilar_class_form_blocked(tmp_path, capsys):
    path = _write(
        tmp_path,
        """# Mini

## Coalgebra

The reconciler calls `Bisimilar()` from `dharma_swarm/coalgebra.py`. [confidence: 90/100]
""",
    )

    assert naga_grounding.main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "mini.md:5" in out
    assert "Bisimilar" in out


def test_future_target_for_absent_object_is_allowed(tmp_path):
    path = _write(
        tmp_path,
        """# Mini

## Future Target

Later PRs may add `titanium-verify` metadata as a future integration target. [confidence: 90/100]
""",
    )

    assert naga_grounding.main([str(path)]) == 0


def test_sab_receipts_on_main_claim_blocked(tmp_path, capsys):
    path = _write(
        tmp_path,
        """# Mini

## SAB Export

`sab_client.py` shadow-exports receipts on main today. [confidence: 90/100]
""",
    )

    assert naga_grounding.main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "mini.md:5" in out
    assert "SABContribution" in out
