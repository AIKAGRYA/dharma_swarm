"""Tests for grimp circular-dependency adapter."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from dharma_swarm.slop.adapters.grimp_adapter import (
    _detect_python_packages,
    _module_to_path,
    _tarjan_scc,
    run_grimp,
)
from dharma_swarm.slop.models import DetectorFamily, Severity

grimp_missing = pytest.mark.skipif(
    importlib.util.find_spec("grimp") is None,
    reason="optional grimp detector is not installed",
)


class TestTarjanScc:
    def test_no_cycles_returns_empty(self) -> None:
        adj = {"a": {"b"}, "b": {"c"}, "c": set()}
        assert _tarjan_scc(adj) == []

    def test_two_node_cycle_detected(self) -> None:
        adj = {"a": {"b"}, "b": {"a"}}
        sccs = _tarjan_scc(adj)
        assert len(sccs) == 1
        assert set(sccs[0]) == {"a", "b"}

    def test_three_node_cycle_detected(self) -> None:
        adj = {"a": {"b"}, "b": {"c"}, "c": {"a"}}
        sccs = _tarjan_scc(adj)
        assert len(sccs) == 1
        assert set(sccs[0]) == {"a", "b", "c"}

    def test_disjoint_cycles(self) -> None:
        adj = {"a": {"b"}, "b": {"a"}, "c": {"d"}, "d": {"c"}}
        sccs = _tarjan_scc(adj)
        sccs_sets = sorted([frozenset(s) for s in sccs], key=lambda s: sorted(s)[0])
        assert frozenset({"a", "b"}) in sccs_sets
        assert frozenset({"c", "d"}) in sccs_sets

    def test_skips_self_loops_and_singletons(self) -> None:
        adj = {"a": {"a"}, "b": {"c"}, "c": set()}
        assert _tarjan_scc(adj) == []


class TestPackageDetection:
    def test_finds_python_package_root(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").touch()
        (pkg / "mod.py").touch()
        roots = _detect_python_packages([pkg / "mod.py"], tmp_path)
        assert roots == ["mypkg"]

    def test_skips_non_python_paths(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").touch()
        roots = _detect_python_packages([pkg / "x.ts"], tmp_path)
        assert roots == []

    def test_skips_paths_outside_repo(self, tmp_path: Path) -> None:
        outside = Path("/tmp/some_random_path/file.py")
        roots = _detect_python_packages([outside], tmp_path)
        assert roots == []


class TestModuleToPath:
    def test_resolves_module_to_file(self, tmp_path: Path) -> None:
        pkg = tmp_path / "p"
        pkg.mkdir()
        (pkg / "__init__.py").touch()
        (pkg / "m.py").touch()
        assert _module_to_path("p.m", tmp_path) == "p/m.py"

    def test_resolves_subpackage_to_init(self, tmp_path: Path) -> None:
        sub = tmp_path / "p" / "sub"
        sub.mkdir(parents=True)
        (tmp_path / "p" / "__init__.py").touch()
        (sub / "__init__.py").touch()
        assert _module_to_path("p.sub", tmp_path) == "p/sub/__init__.py"


class TestRunGrimpIntegration:
    def test_no_paths(self, tmp_path: Path) -> None:
        result = run_grimp([], repo_root=tmp_path)
        assert result.findings == []
        assert result.exit_code != 0

    def test_no_python_packages(self, tmp_path: Path) -> None:
        (tmp_path / "x.txt").touch()
        result = run_grimp([tmp_path / "x.txt"], repo_root=tmp_path)
        assert result.findings == []
        assert "no Python package roots" in (result.error or "")

    @grimp_missing
    def test_real_package_with_no_cycles(self, tmp_path: Path) -> None:
        pkg = tmp_path / "leafpkg"
        pkg.mkdir()
        (pkg / "__init__.py").touch()
        (pkg / "a.py").write_text("X = 1\n", encoding="utf-8")
        (pkg / "b.py").write_text("from leafpkg.a import X\n", encoding="utf-8")
        import sys
        sys.path.insert(0, str(tmp_path))
        try:
            result = run_grimp([pkg / "a.py"], repo_root=tmp_path)
        finally:
            sys.path.remove(str(tmp_path))
        assert result.exit_code == 0
        cycle_findings = [
            f for f in result.findings if f.issue_type == "circular_dependency"
        ]
        assert cycle_findings == []

    @grimp_missing
    def test_real_package_with_cycle(self, tmp_path: Path) -> None:
        pkg = tmp_path / "cycpkg"
        pkg.mkdir()
        (pkg / "__init__.py").touch()
        (pkg / "a.py").write_text("from cycpkg import b\n", encoding="utf-8")
        (pkg / "b.py").write_text("from cycpkg import a\n", encoding="utf-8")
        import sys
        sys.path.insert(0, str(tmp_path))
        try:
            result = run_grimp([pkg / "a.py", pkg / "b.py"], repo_root=tmp_path)
        finally:
            sys.path.remove(str(tmp_path))
        cycle_findings = [
            f for f in result.findings if f.issue_type == "circular_dependency"
        ]
        assert len(cycle_findings) == 2
        assert all(f.family is DetectorFamily.STRUCTURE for f in cycle_findings)
        assert all("SCC" in f.evidence for f in cycle_findings)


class TestSeverityCalibration:
    def test_severity_grows_with_cycle_size(self) -> None:
        from dharma_swarm.slop.adapters.grimp_adapter import _severity_for

        assert _severity_for(2) is Severity.LOW
        assert _severity_for(3) is Severity.MEDIUM
        assert _severity_for(5) is Severity.HIGH
        assert _severity_for(8) is Severity.HIGH

    def test_confidence_grows_with_cycle_size(self) -> None:
        from dharma_swarm.slop.adapters.grimp_adapter import _confidence_for

        assert _confidence_for(2) < _confidence_for(5)
        assert _confidence_for(10) <= 0.92
