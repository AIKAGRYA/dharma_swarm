from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "governance" / "check_naga_spec_citations.py"


def load_module():
    spec = importlib.util.spec_from_file_location("check_naga_spec_citations", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_docs(tmp_path: Path, core: str) -> Path:
    spec_dir = tmp_path / "specs" / "naga_ir"
    spec_dir.mkdir(parents=True)
    (spec_dir / "core.md").write_text(core, encoding="utf-8")
    (spec_dir / "receipt_wire.md").write_text("# Wire\n\n## Shape\n\nA local sibling spec.\n", encoding="utf-8")
    (spec_dir / "witness_mesh.md").write_text("# Mesh\n\n## Shape\n\nA local sibling spec.\n", encoding="utf-8")
    return spec_dir


def fake_git(monkeypatch, module, existing: set[str]):
    def run_git(args, repo_root):
        target = args[-1]
        if ":" in target:
            path = target.split(":", 1)[1]
        else:
            path = target
        return module.GitResult(0 if path in existing else 1, "", "missing")

    monkeypatch.setattr(module, "run_git", run_git)


def test_clean_triple_passes_with_inline_citations(tmp_path, monkeypatch):
    module = load_module()
    fake_git(monkeypatch, module, {"scripts/governance/assurance_boundary.py"})
    core = """# Core

## Grounding

origin/main contains `scripts/governance/assurance_boundary.py`. [confidence: 98/100] [assurance boundary](scripts/governance/assurance_boundary.py)

## Sibling

This spec's sibling wire file is cross-referenced as local structure. [confidence: 90/100] [wire](receipt_wire.md)
"""
    findings = module.run([write_docs(tmp_path, core)], repo_root=tmp_path)
    assert findings == []


def test_load_bearing_claim_without_citation_is_flagged(tmp_path, monkeypatch):
    module = load_module()
    fake_git(monkeypatch, module, {"dharma_swarm/coalgebra.py"})
    core = """# Core

## Grounding

origin/main contains `dharma_swarm/coalgebra.py` and exposes lowercase `bisimilar`. [confidence: 98/100]
"""
    findings = module.run([write_docs(tmp_path, core)], repo_root=tmp_path)
    assert any(finding.code == "uncited_load_bearing" for finding in findings)


def test_repo_path_citation_verified_via_git_show_origin_main(tmp_path, monkeypatch):
    module = load_module()
    calls: list[list[str]] = []

    def run_git(args, repo_root):
        calls.append(args)
        return module.GitResult(0, "", "")

    monkeypatch.setattr(module, "run_git", run_git)
    core = """# Core

## Grounding

origin/main contains `scripts/governance/assurance_boundary.py`. [confidence: 98/100] [assurance](scripts/governance/assurance_boundary.py)
"""
    findings = module.run([write_docs(tmp_path, core)], repo_root=tmp_path)
    assert findings == []
    assert any("show" in call and "origin/main:scripts/governance/assurance_boundary.py" in call for call in calls)


def test_missing_repo_path_citation_is_flagged(tmp_path, monkeypatch):
    module = load_module()
    fake_git(monkeypatch, module, set())
    core = """# Core

## Grounding

origin/main contains `dharma_swarm/nope.py`. [confidence: 98/100] [missing path](dharma_swarm/nope.py)
"""
    findings = module.run([write_docs(tmp_path, core)], repo_root=tmp_path)
    assert any(finding.code == "repo_path_missing" for finding in findings)


def test_relative_path_citation_resolves_locally(tmp_path, monkeypatch):
    module = load_module()
    fake_git(monkeypatch, module, set())
    core = """# Core

## Sibling

The wire sibling is local spec structure. [confidence: 90/100] [wire](receipt_wire.md)
"""
    findings = module.run([write_docs(tmp_path, core)], repo_root=tmp_path)
    assert findings == []


def test_malformed_http_citation_is_flagged(tmp_path, monkeypatch):
    module = load_module()
    fake_git(monkeypatch, module, set())
    core = """# Core

## Link

The MLIR verif dialect supports first-class contracts. [confidence: 95/100] [bad](ftp://example.com/verif)
"""
    findings = module.run([write_docs(tmp_path, core)], repo_root=tmp_path)
    assert any(finding.code == "invalid_citation_format" for finding in findings)
