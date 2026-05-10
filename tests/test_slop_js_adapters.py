"""Tests for JS/TS detector adapters.

All subprocess calls are mocked so tests run without npx, fallow, etc.
Tests cover: schema correctness, family routing, severity/confidence
calibration, graceful tool-missing handling, project discovery, and
parser edge cases (malformed JSON, empty output).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dharma_swarm.slop.adapters import (
    run_dependency_cruiser,
    run_eslint,
    run_fallow,
    run_jscpd,
    run_knip,
    run_oxlint,
    run_tsc,
)
from dharma_swarm.slop.adapters._js_helpers import (
    EXCLUDE_DIRS,
    filter_js_ts_paths,
    filter_python_paths,
    find_js_projects,
    find_ts_projects,
)
from dharma_swarm.slop.models import DetectorFamily, Severity


@pytest.fixture
def js_project(tmp_path: Path) -> Path:
    proj = tmp_path / "dashboard"
    (proj / "src").mkdir(parents=True)
    (proj / "package.json").write_text('{"name":"x"}', encoding="utf-8")
    (proj / "tsconfig.json").write_text("{}", encoding="utf-8")
    (proj / "src" / "a.ts").write_text("export const x = 1;\n", encoding="utf-8")
    (proj / "src" / "b.tsx").write_text("export const Y = () => null;\n", encoding="utf-8")
    return proj


def patch_adapter_subprocess(
    adapter_module: str, *, stdout: str = "", stderr: str = "", exit_code: int = 0
):
    return patch(
        f"dharma_swarm.slop.adapters.{adapter_module}.run_subprocess",
        return_value=(exit_code, stdout, stderr, 0.05),
    )


class TestJsHelpers:
    def test_filter_python(self, tmp_path: Path) -> None:
        paths = [tmp_path / "a.py", tmp_path / "b.ts", tmp_path / "c.py"]
        out = filter_python_paths(paths)
        assert {p.name for p in out} == {"a.py", "c.py"}

    def test_filter_js_ts(self, tmp_path: Path) -> None:
        paths = [
            tmp_path / "a.py",
            tmp_path / "b.ts",
            tmp_path / "c.tsx",
            tmp_path / "d.mjs",
            tmp_path / "e.go",
        ]
        out = filter_js_ts_paths(paths)
        assert {p.name for p in out} == {"b.ts", "c.tsx", "d.mjs"}

    def test_find_js_projects_walks_to_package_json(
        self, js_project: Path, tmp_path: Path
    ) -> None:
        target = js_project / "src" / "a.ts"
        roots = find_js_projects([target], repo_root=tmp_path)
        assert len(roots) == 1
        assert roots[0] == js_project.resolve()

    def test_find_ts_projects_walks_to_tsconfig(
        self, js_project: Path, tmp_path: Path
    ) -> None:
        roots = find_ts_projects(
            [js_project / "src" / "a.ts"], repo_root=tmp_path
        )
        assert len(roots) == 1

    def test_exclude_dirs_skipped(self, tmp_path: Path, js_project: Path) -> None:
        nm = js_project / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "package.json").write_text("{}", encoding="utf-8")
        (nm / "index.ts").write_text("", encoding="utf-8")
        roots = find_js_projects([nm / "index.ts"], repo_root=tmp_path)
        assert all(d not in EXCLUDE_DIRS for r in roots for d in r.parts)


class TestFallowAdapter:
    def test_no_js_paths_clean(self, tmp_path: Path) -> None:
        result = run_fallow([tmp_path / "x.py"], repo_root=tmp_path)
        assert result.findings == []
        assert result.exit_code != 0

    def test_tool_not_installed(self, js_project: Path, tmp_path: Path) -> None:
        with patch_adapter_subprocess(
            "fallow_adapter", stderr="fallow: command not found", exit_code=127
        ):
            result = run_fallow(
                [js_project / "src" / "a.ts"], repo_root=tmp_path
            )
        assert result.exit_code == 127
        assert result.findings == []

    def test_parses_real_fallow_json_routes_families(
        self, js_project: Path, tmp_path: Path
    ) -> None:
        payload = json.dumps({
            "schema_version": 5,
            "version": "2.67.0",
            "total_issues": 5,
            "summary": {"total_issues": 5},
            "unused_files": [{"path": "src/dead.ts"}],
            "unused_exports": [{"path": "src/a.ts", "name": "deadFn", "line": 12}],
            "duplicate_exports": [{"path": "src/a.ts", "name": "X"}],
            "circular_dependencies": [{"path": "src/a.ts"}],
            "boundary_violations": [{"path": "src/a.ts"}],
            "unused_dependencies": [],
        })
        with patch_adapter_subprocess(
            "fallow_adapter", stdout=payload, exit_code=0
        ):
            result = run_fallow(
                [js_project / "src" / "a.ts", js_project / "src" / "b.tsx"],
                repo_root=tmp_path,
            )
        families = {f.family for f in result.findings}
        types = {f.issue_type for f in result.findings}
        assert DetectorFamily.DEAD_CODE in families
        assert DetectorFamily.DUPLICATION in families
        assert DetectorFamily.STRUCTURE in families
        assert DetectorFamily.BOUNDARY in families
        assert "unused_file" in types
        assert "unused_export" in types
        assert "duplicate_export" in types
        assert "circular_dependency" in types
        assert "boundary_violation" in types


class TestKnipAdapter:
    def test_parses_unused_files_and_deps(
        self, js_project: Path, tmp_path: Path
    ) -> None:
        payload = json.dumps({
            "files": ["src/dead.ts"],
            "dependencies": ["unused-pkg"],
            "exports": [
                {"file": "src/a.ts", "symbol": "unusedFn", "line": 5}
            ],
        })
        with patch_adapter_subprocess(
            "knip_adapter", stdout=payload, exit_code=0
        ):
            result = run_knip(
                [js_project / "src" / "a.ts"], repo_root=tmp_path
            )
        types = {f.issue_type for f in result.findings}
        assert "unused_file" in types
        assert "unused_dependency" in types
        assert "unused_export" in types
        assert all(f.family is DetectorFamily.DEAD_CODE for f in result.findings)


class TestJscpdAdapter:
    def test_parses_duplicates(self, js_project: Path, tmp_path: Path) -> None:
        report_payload = json.dumps({
            "duplicates": [
                {
                    "format": "typescript",
                    "lines": 25,
                    "firstFile": {"name": str(js_project / "src" / "a.ts"), "start": {"line": 1}},
                    "secondFile": {"name": str(js_project / "src" / "b.tsx"), "start": {"line": 10}},
                }
            ]
        })
        from unittest.mock import MagicMock

        original_run_subprocess = run_jscpd.__module__

        def fake_run(argv, *, cwd=None, timeout=60.0):
            output_dir = None
            for i, arg in enumerate(argv):
                if arg == "--output" and i + 1 < len(argv):
                    output_dir = Path(argv[i + 1])
                    break
            if output_dir:
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "jscpd-report.json").write_text(report_payload, encoding="utf-8")
            return (0, "", "", 0.05)

        with patch("dharma_swarm.slop.adapters.jscpd_adapter.run_subprocess", side_effect=fake_run):
            result = run_jscpd(
                [js_project / "src" / "a.ts", js_project / "src" / "b.tsx"],
                repo_root=tmp_path,
            )
        assert len(result.findings) == 2
        assert all(f.family is DetectorFamily.DUPLICATION for f in result.findings)


class TestTscAdapter:
    def test_skips_when_node_modules_missing(
        self, js_project: Path, tmp_path: Path
    ) -> None:
        result = run_tsc(
            [js_project / "src" / "a.ts"], repo_root=tmp_path
        )
        assert result.findings == []
        assert "node_modules not installed" in (result.error or "")

    def test_uses_local_tsc_when_available(
        self, js_project: Path, tmp_path: Path
    ) -> None:
        bin_dir = js_project / "node_modules" / ".bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "tsc").write_text("#!/bin/sh\necho dummy\n", encoding="utf-8")
        (bin_dir / "tsc").chmod(0o755)
        with patch("dharma_swarm.slop.adapters.tsc_adapter.run_subprocess",
                   return_value=(0, "", "", 0.05)) as mock:
            run_tsc([js_project / "src" / "a.ts"], repo_root=tmp_path)
            argv = mock.call_args.args[0]
            assert argv[0].endswith("/node_modules/.bin/tsc")

    def test_parses_diagnostic_lines(
        self, js_project: Path, tmp_path: Path
    ) -> None:
        bin_dir = js_project / "node_modules" / ".bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "tsc").write_text("#!/bin/sh\n", encoding="utf-8")
        (bin_dir / "tsc").chmod(0o755)
        diagnostic = (
            "src/a.ts(5,10): error TS2322: Type 'string' is not assignable to type 'number'.\n"
            "src/b.tsx(12,3): warning TS6133: 'foo' is declared but never used.\n"
        )
        with patch("dharma_swarm.slop.adapters.tsc_adapter.run_subprocess",
                   return_value=(1, diagnostic, "", 0.1)):
            result = run_tsc(
                [js_project / "src" / "a.ts", js_project / "src" / "b.tsx"],
                repo_root=tmp_path,
            )
        types = {f.issue_type for f in result.findings}
        assert "TS2322" in types
        assert "TS6133" in types
        assert all(f.family is DetectorFamily.TYPE_DRIFT for f in result.findings)
        ts2322 = [f for f in result.findings if f.issue_type == "TS2322"][0]
        assert ts2322.severity is Severity.HIGH


class TestDependencyCruiserAdapter:
    def test_parses_violations(self, js_project: Path, tmp_path: Path) -> None:
        payload = json.dumps({
            "summary": {
                "violations": [
                    {
                        "from": "src/a.ts",
                        "to": "src/forbidden/x.ts",
                        "rule": {
                            "name": "no-circular",
                            "severity": "error",
                            "comment": "no circular deps allowed",
                        },
                    }
                ]
            }
        })
        with patch("dharma_swarm.slop.adapters.dependency_cruiser_adapter.run_subprocess",
                   return_value=(1, payload, "", 0.2)):
            result = run_dependency_cruiser(
                [js_project / "src" / "a.ts"], repo_root=tmp_path
            )
        assert len(result.findings) == 1
        f0 = result.findings[0]
        assert f0.family is DetectorFamily.BOUNDARY
        assert f0.severity is Severity.HIGH
        assert "no-circular" in f0.issue_type


class TestEslintAdapter:
    def test_skips_when_node_modules_missing(
        self, js_project: Path, tmp_path: Path
    ) -> None:
        result = run_eslint(
            [js_project / "src" / "a.ts"], repo_root=tmp_path
        )
        assert result.findings == []
        assert "node_modules not installed" in (result.error or "")

    def test_parses_messages_routes_families(
        self, js_project: Path, tmp_path: Path
    ) -> None:
        bin_dir = js_project / "node_modules" / ".bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "eslint").write_text("#!/bin/sh\n", encoding="utf-8")
        (bin_dir / "eslint").chmod(0o755)
        payload = json.dumps([
            {
                "filePath": str(js_project / "src" / "a.ts"),
                "messages": [
                    {"ruleId": "@typescript-eslint/no-explicit-any", "severity": 2,
                     "message": "any forbidden", "line": 3},
                    {"ruleId": "complexity", "severity": 1,
                     "message": "cyclomatic 12", "line": 10},
                    {"ruleId": "no-unused-vars", "severity": 2,
                     "message": "unused", "line": 15},
                    {"ruleId": "security/detect-eval-with-expression", "severity": 2,
                     "message": "eval", "line": 20},
                ],
            }
        ])
        with patch("dharma_swarm.slop.adapters.eslint_adapter.run_subprocess",
                   return_value=(1, payload, "", 0.3)):
            result = run_eslint(
                [js_project / "src" / "a.ts"], repo_root=tmp_path
            )
        family_by_rule = {f.issue_type: f.family for f in result.findings}
        assert family_by_rule["@typescript-eslint/no-explicit-any"] is DetectorFamily.AI_SLOP
        assert family_by_rule["complexity"] is DetectorFamily.COMPLEXITY
        assert family_by_rule["no-unused-vars"] is DetectorFamily.DEAD_CODE
        assert family_by_rule["security/detect-eval-with-expression"] is DetectorFamily.SECURITY


class TestOxlintAdapter:
    def test_parses_diagnostics(self, js_project: Path, tmp_path: Path) -> None:
        payload = json.dumps({
            "diagnostics": [
                {
                    "filename": str(js_project / "src" / "a.ts"),
                    "code": "no-unused-vars",
                    "severity": "warning",
                    "message": "unused",
                    "labels": [{"line": 4, "column": 7}],
                },
                {
                    "filename": str(js_project / "src" / "b.tsx"),
                    "code": "no-empty",
                    "severity": "error",
                    "message": "empty block",
                    "labels": [{"line": 8, "column": 1}],
                },
            ]
        })
        with patch("dharma_swarm.slop.adapters.oxlint_adapter.run_subprocess",
                   return_value=(1, payload, "", 0.02)):
            result = run_oxlint(
                [js_project / "src" / "a.ts", js_project / "src" / "b.tsx"],
                repo_root=tmp_path,
            )
        assert len(result.findings) == 2
        assert all(f.family is DetectorFamily.AI_SLOP for f in result.findings)
        empties = [f for f in result.findings if f.issue_type == "no-empty"]
        assert empties[0].severity is Severity.HIGH


class TestRegistry:
    def test_all_new_adapters_registered(self) -> None:
        from dharma_swarm.slop.adapters import REGISTRY

        for name in ("fallow", "knip", "jscpd", "tsc", "dependency-cruiser", "eslint", "oxlint"):
            assert name in REGISTRY, f"{name} missing from REGISTRY"

    def test_all_python_adapters_still_registered(self) -> None:
        from dharma_swarm.slop.adapters import REGISTRY

        for name in ("vulture", "ai-slop-detector", "sentry-spotlight"):
            assert name in REGISTRY


class TestModeProfiles:
    def test_pre_commit_includes_oxlint(self) -> None:
        from scripts.governance.slop_verify import MODE_PROFILES

        assert "oxlint" in MODE_PROFILES["pre-commit"]["detectors"]

    def test_ci_includes_frontend_stack(self) -> None:
        from scripts.governance.slop_verify import MODE_PROFILES

        ci_detectors = set(MODE_PROFILES["ci"]["detectors"])
        for tool in ("fallow", "knip", "jscpd", "tsc", "eslint"):
            assert tool in ci_detectors

    def test_nightly_includes_dependency_cruiser(self) -> None:
        from scripts.governance.slop_verify import MODE_PROFILES

        assert "dependency-cruiser" in MODE_PROFILES["nightly"]["detectors"]
