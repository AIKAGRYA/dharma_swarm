"""Tests for semgrep adapter — pattern-based AI-slop detection.

Subprocess is mocked so tests run without semgrep installed.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dharma_swarm.slop.adapters.semgrep_adapter import (
    _BUILTIN_RULES,
    _confidence_for,
    _family_for,
    _parse_semgrep_json,
    _resolve_config_args,
    run_semgrep,
)
from dharma_swarm.slop.models import DetectorFamily, Severity


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("def f():\n    pass\n", encoding="utf-8")
    return tmp_path


def patch_subprocess(stdout: str = "", stderr: str = "", exit_code: int = 0):
    return patch(
        "dharma_swarm.slop.adapters.semgrep_adapter.run_subprocess",
        return_value=(exit_code, stdout, stderr, 0.05),
    )


class TestFamilyRouting:
    def test_security_metadata_routes_to_security(self) -> None:
        assert _family_for({"family": "security"}) is DetectorFamily.SECURITY

    def test_ai_slop_metadata_routes_to_ai_slop(self) -> None:
        assert _family_for({"family": "ai_slop"}) is DetectorFamily.AI_SLOP

    def test_dead_code_metadata(self) -> None:
        assert _family_for({"family": "dead_code"}) is DetectorFamily.DEAD_CODE

    def test_complexity_metadata(self) -> None:
        assert _family_for({"family": "complexity"}) is DetectorFamily.COMPLEXITY

    def test_boundary_metadata(self) -> None:
        assert _family_for({"family": "boundary"}) is DetectorFamily.BOUNDARY

    def test_missing_metadata_defaults_to_ai_slop(self) -> None:
        assert _family_for(None) is DetectorFamily.AI_SLOP
        assert _family_for({}) is DetectorFamily.AI_SLOP


class TestConfidenceCalibration:
    def test_severity_drives_base_confidence(self) -> None:
        assert _confidence_for(Severity.HIGH, "general") > _confidence_for(Severity.MEDIUM, "general")
        assert _confidence_for(Severity.MEDIUM, "general") > _confidence_for(Severity.LOW, "general")

    def test_error_handling_category_boosts(self) -> None:
        assert _confidence_for(Severity.MEDIUM, "error_handling") > _confidence_for(Severity.MEDIUM, "general")

    def test_ceremonial_category_boosts(self) -> None:
        assert _confidence_for(Severity.LOW, "ceremonial") > _confidence_for(Severity.LOW, "general")

    def test_confidence_capped_at_92(self) -> None:
        assert _confidence_for(Severity.HIGH, "error_handling") <= 0.92


class TestParseSemgrepJson:
    def test_parses_subagent_6_broad_except(self, tmp_repo: Path) -> None:
        payload = json.dumps({
            "results": [
                {
                    "check_id": "ai-slop.broad-except-pass",
                    "path": "src/a.py",
                    "start": {"line": 5, "col": 1},
                    "extra": {
                        "message": "broad except pass",
                        "severity": "WARNING",
                        "metadata": {"family": "ai_slop", "category": "error_handling"},
                    },
                }
            ]
        })
        findings = _parse_semgrep_json(payload, tmp_repo)
        assert len(findings) == 1
        f = findings[0]
        assert f.family is DetectorFamily.AI_SLOP
        assert f.issue_type == "ai-slop.broad-except-pass"
        assert f.severity is Severity.MEDIUM
        assert f.line == 5
        assert f.confidence > 0.65

    def test_parses_security_finding(self, tmp_repo: Path) -> None:
        payload = json.dumps({
            "results": [
                {
                    "check_id": "security.eval-or-exec",
                    "path": "src/a.py",
                    "start": {"line": 12, "col": 1},
                    "extra": {
                        "message": "eval is dangerous",
                        "severity": "ERROR",
                        "metadata": {"family": "security"},
                    },
                }
            ]
        })
        findings = _parse_semgrep_json(payload, tmp_repo)
        assert len(findings) == 1
        assert findings[0].family is DetectorFamily.SECURITY
        assert findings[0].severity is Severity.HIGH

    def test_invalid_json_returns_empty(self, tmp_repo: Path) -> None:
        assert _parse_semgrep_json("not-json", tmp_repo) == []

    def test_missing_results_key_returns_empty(self, tmp_repo: Path) -> None:
        assert _parse_semgrep_json("{}", tmp_repo) == []

    def test_skips_findings_without_path(self, tmp_repo: Path) -> None:
        payload = json.dumps({"results": [{"check_id": "x", "extra": {}}]})
        assert _parse_semgrep_json(payload, tmp_repo) == []


class TestResolveConfigArgs:
    def test_picks_up_repo_semgrep_dir(self, tmp_repo: Path) -> None:
        sem_dir = tmp_repo / ".semgrep"
        sem_dir.mkdir()
        (sem_dir / "rules.yml").write_text("rules: []", encoding="utf-8")
        (sem_dir / "extra.yml").write_text("rules: []", encoding="utf-8")
        args = _resolve_config_args(tmp_repo, None)
        configs = [args[i+1] for i, a in enumerate(args) if a == "--config"]
        assert any(c.endswith("rules.yml") for c in configs)
        assert any(c.endswith("extra.yml") for c in configs)

    def test_no_semgrep_dir_returns_empty(self, tmp_repo: Path) -> None:
        args = _resolve_config_args(tmp_repo, None)
        assert args == []

    def test_extra_configs_merged(self, tmp_repo: Path) -> None:
        args = _resolve_config_args(tmp_repo, ["p/q/special.yml"])
        assert "p/q/special.yml" in args


class TestRunSemgrep:
    def test_no_paths(self, tmp_repo: Path) -> None:
        result = run_semgrep([], repo_root=tmp_repo)
        assert result.findings == []
        assert result.exit_code != 0

    def test_tool_not_installed(self, tmp_repo: Path) -> None:
        with patch_subprocess(stderr="semgrep: command not found", exit_code=127):
            result = run_semgrep([tmp_repo / "src" / "a.py"], repo_root=tmp_repo)
        assert result.exit_code == 127

    def test_findings_flow_through(self, tmp_repo: Path) -> None:
        payload = json.dumps({
            "results": [
                {
                    "check_id": "ai-slop.broad-except-pass",
                    "path": "src/a.py",
                    "start": {"line": 1},
                    "extra": {
                        "severity": "WARNING",
                        "metadata": {"family": "ai_slop", "category": "error_handling"},
                        "message": "broad except",
                    },
                }
            ]
        })
        with patch_subprocess(stdout=payload, exit_code=1):
            result = run_semgrep([tmp_repo / "src" / "a.py"], repo_root=tmp_repo)
        assert len(result.findings) == 1
        assert result.findings[0].family is DetectorFamily.AI_SLOP

    def test_no_config_returns_error(self, tmp_repo: Path) -> None:
        result = run_semgrep(
            [tmp_repo / "src" / "a.py"],
            repo_root=tmp_repo,
            use_builtin=False,
        )
        assert "no semgrep config" in (result.error or "")


class TestBuiltinRules:
    def test_has_subagent_6_patterns(self) -> None:
        rule_ids = {r["id"] for r in _BUILTIN_RULES["rules"]}
        assert "ai-slop.broad-except-pass" in rule_ids
        assert "ai-slop.broad-except-silent" in rule_ids

    def test_has_useless_try_pattern(self) -> None:
        rule_ids = {r["id"] for r in _BUILTIN_RULES["rules"]}
        assert "ai-slop.useless-try" in rule_ids

    def test_has_debug_print_pattern(self) -> None:
        rule_ids = {r["id"] for r in _BUILTIN_RULES["rules"]}
        assert "ai-slop.debug-print-in-prod" in rule_ids

    def test_all_rules_have_metadata(self) -> None:
        for rule in _BUILTIN_RULES["rules"]:
            assert "metadata" in rule
            assert "family" in rule["metadata"]
            assert "category" in rule["metadata"]


class TestRegistry:
    def test_semgrep_in_registry(self) -> None:
        from dharma_swarm.slop.adapters import REGISTRY

        assert "semgrep" in REGISTRY


class TestModeProfiles:
    def test_pre_commit_includes_semgrep(self) -> None:
        from scripts.governance.slop_verify import MODE_PROFILES

        assert "semgrep" in MODE_PROFILES["pre-commit"]["detectors"]

    def test_ci_includes_semgrep_and_grimp(self) -> None:
        from scripts.governance.slop_verify import MODE_PROFILES

        ci_detectors = set(MODE_PROFILES["ci"]["detectors"])
        assert "semgrep" in ci_detectors
        assert "grimp" in ci_detectors
