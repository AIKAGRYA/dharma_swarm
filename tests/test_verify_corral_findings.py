"""Unit tests for ``scripts/governance/verify_corral_findings.py``.

These tests use a tmp_path-backed fake corral and fake repo tree, so they do
not depend on the real ``DE_BUG_CORRAL/`` (which only lives on a branch).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "governance"
    / "verify_corral_findings.py"
)

# Load the module by path so we do not require an installed package layout.
spec_loader = pytest.importorskip("importlib.util")
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("verify_corral_findings", SCRIPT_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules["verify_corral_findings"] = mod
spec.loader.exec_module(mod)  # type: ignore[union-attr]


def _setup_repo(root: Path) -> None:
    # Fake a project with a python file the corral can cite.
    (root / "dharma_swarm").mkdir()
    (root / "dharma_swarm" / "ontology.py").write_text(
        "\n".join(f"# line {i}" for i in range(1, 51)) + "\n",
        encoding="utf-8",
    )
    # A file referenced only by basename.
    (root / "dharma_swarm" / "evolution.py").write_text(
        "\n".join(f"# line {i}" for i in range(1, 101)) + "\n",
        encoding="utf-8",
    )


def _setup_corral(root: Path) -> Path:
    corral = root / "DE_BUG_CORRAL"
    corral.mkdir()
    (corral / "01.md").write_text(
        """# Truth Verifiers

### CRITICAL · TV-01 · Live reference

- Sources: somewhere
- Detail: see `dharma_swarm/ontology.py:25` for the call.
- Status: OPEN

### MAJOR · TV-02 · Past EOF

- Detail: cited `dharma_swarm/ontology.py:9999` should fail.
- Status: OPEN

### MAJOR · TV-03 · Bare basename

- Detail: see `evolution.py:42` (unprefixed).
- Status: OPEN

### MAJOR · TV-04 · Gone

- Detail: see `dharma_swarm/never_existed.py:1`.
- Status: OPEN
""",
        encoding="utf-8",
    )
    (corral / "00.md").write_text("# index — should be skipped\n", encoding="utf-8")
    (corral / "09.md").write_text("# provenance — should be skipped\n", encoding="utf-8")
    return corral


def test_parses_and_classifies(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    corral = _setup_corral(tmp_path)
    # Reset the basename cache between tests since it is process-global.
    mod._BASENAME_CACHE.clear()
    findings = mod.gather_findings(tmp_path, corral)
    by_id = {f.fid: f for f in findings}

    assert set(by_id) == {"TV-01", "TV-02", "TV-03", "TV-04"}
    assert by_id["TV-01"].verdict() == "OK"
    assert by_id["TV-02"].verdict() == "STALE-LINES-PAST-EOF"
    assert by_id["TV-03"].verdict() == "OK"  # resolved via basename
    assert by_id["TV-04"].verdict() == "STALE-PATHS-GONE"


def test_skips_index_and_provenance(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    corral = _setup_corral(tmp_path)
    mod._BASENAME_CACHE.clear()
    findings = mod.gather_findings(tmp_path, corral)
    # 00.md (index) and 09.md (provenance) carry no `### SEV · ID ·` headers
    # in our fixture, but the script also skips them by stem.  All 4 findings
    # must come from 01.md only.
    sources = {f.source_file for f in findings}
    assert all("01.md" in s for s in sources)


def test_status_parsing(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    corral = _setup_corral(tmp_path)
    mod._BASENAME_CACHE.clear()
    findings = mod.gather_findings(tmp_path, corral)
    for f in findings:
        assert f.declared_status == "OPEN", f.fid


def test_strict_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_repo(tmp_path)
    corral = _setup_corral(tmp_path)
    mod._BASENAME_CACHE.clear()
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    rc = mod.main(["--dir", "DE_BUG_CORRAL", "--strict"])
    assert rc == 1  # we seeded stale findings, so strict should fail


def test_strict_exit_code_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_repo(tmp_path)
    corral = tmp_path / "DE_BUG_CORRAL"
    corral.mkdir()
    (corral / "01.md").write_text(
        """# OK only

### MAJOR · TV-99 · all live

- Detail: see `dharma_swarm/ontology.py:10`.
- Status: OPEN
""",
        encoding="utf-8",
    )
    mod._BASENAME_CACHE.clear()
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    rc = mod.main(["--dir", "DE_BUG_CORRAL", "--strict"])
    assert rc == 0
