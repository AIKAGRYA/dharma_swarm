"""Tests for scripts/governance/module_metabolism_report.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure scripts/governance is importable
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts" / "governance"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from module_metabolism_report import (
    _build_import_graph,
    _confidence_flags,
    _detect_cycles,
    _family_for_module,
    _suggest_action,
    format_text,
    generate_report,
)


class TestFamilyClassification:
    def test_exact_match(self) -> None:
        assert _family_for_module("models") == "core"

    def test_prefix_match(self) -> None:
        assert _family_for_module("model_hierarchy") == "providers"

    def test_unclassified(self) -> None:
        assert _family_for_module("zxcvbnm_unknown") == "unclassified"

    def test_subdir_mapping(self) -> None:
        assert _family_for_module("session", "dharma_swarm/operator_core/session.py") == "operator_core"

    def test_subdir_assurance(self) -> None:
        assert _family_for_module("runner", "dharma_swarm/assurance/runner.py") == "assurance"

    def test_evolution_family(self) -> None:
        assert _family_for_module("evolution") == "evolution"
        assert _family_for_module("meta_evolution") == "evolution"

    def test_governance_family(self) -> None:
        assert _family_for_module("dharma_kernel") == "governance"
        assert _family_for_module("telos_gate") == "governance"

    def test_orchestration_family(self) -> None:
        assert _family_for_module("agent_runner") == "orchestration"
        assert _family_for_module("swarm") == "orchestration"

    def test_surfaces_family(self) -> None:
        assert _family_for_module("dgc_cli") == "surfaces"
        assert _family_for_module("terminal_bridge", "dharma_swarm/terminal_adapters/bridge.py") == "surfaces"


class TestImportGraph:
    def test_builds_inbound_map(self) -> None:
        modules = [
            {"path": "dharma_swarm/a.py", "imports_from_package": ["b", "c"]},
            {"path": "dharma_swarm/b.py", "imports_from_package": ["c"]},
            {"path": "dharma_swarm/c.py", "imports_from_package": []},
        ]
        inbound = _build_import_graph(modules)
        assert "a" in inbound.get("b", set())
        assert "a" in inbound.get("c", set())
        assert "b" in inbound.get("c", set())
        assert inbound.get("a") is None or len(inbound.get("a", set())) == 0

    def test_empty_modules(self) -> None:
        assert _build_import_graph([]) == {}


class TestCycleDetection:
    def test_detects_simple_cycle(self) -> None:
        modules = [
            {"path": "dharma_swarm/a.py", "imports_from_package": ["b"]},
            {"path": "dharma_swarm/b.py", "imports_from_package": ["a"]},
        ]
        cycles = _detect_cycles(modules)
        assert len(cycles) >= 1
        cycle_strs = [" -> ".join(c) for c in cycles]
        assert any("a" in s and "b" in s for s in cycle_strs)

    def test_no_cycle(self) -> None:
        modules = [
            {"path": "dharma_swarm/a.py", "imports_from_package": ["b"]},
            {"path": "dharma_swarm/b.py", "imports_from_package": []},
        ]
        cycles = _detect_cycles(modules)
        assert len(cycles) == 0

    def test_three_node_cycle(self) -> None:
        modules = [
            {"path": "dharma_swarm/a.py", "imports_from_package": ["b"]},
            {"path": "dharma_swarm/b.py", "imports_from_package": ["c"]},
            {"path": "dharma_swarm/c.py", "imports_from_package": ["a"]},
        ]
        cycles = _detect_cycles(modules)
        assert len(cycles) >= 1


class TestSuggestAction:
    def test_over_3000_loc_split(self) -> None:
        mod = {"loc": 4000, "write_surface_hits": 0, "test_references": 5}
        assert _suggest_action(mod, inbound_count=10, cycle_member=False) == "split-review"

    def test_no_inbound_no_tests_archive(self) -> None:
        mod = {"loc": 100, "write_surface_hits": 0, "test_references": 0}
        assert _suggest_action(mod, inbound_count=0, cycle_member=False) == "archive-review"

    def test_cycle_member_facade(self) -> None:
        mod = {"loc": 200, "write_surface_hits": 0, "test_references": 3}
        assert _suggest_action(mod, inbound_count=5, cycle_member=True) == "facade"

    def test_high_write_surface_merge(self) -> None:
        mod = {"loc": 300, "write_surface_hits": 5, "test_references": 2}
        assert _suggest_action(mod, inbound_count=3, cycle_member=False) == "merge-review"

    def test_normal_module_keep(self) -> None:
        mod = {"loc": 200, "write_surface_hits": 1, "test_references": 1}
        assert _suggest_action(mod, inbound_count=2, cycle_member=False) == "keep"


class TestConfidenceFlags:
    def test_entrypoint_possible(self) -> None:
        mod = {"test_references": 1, "write_surface_hits": 0}
        flags = _confidence_flags(mod, inbound_count=0)
        assert "entrypoint_possible" in flags

    def test_test_signal_missing(self) -> None:
        mod = {"test_references": 0, "write_surface_hits": 0}
        flags = _confidence_flags(mod, inbound_count=5)
        assert "test_signal_missing" in flags

    def test_write_surface(self) -> None:
        mod = {"test_references": 1, "write_surface_hits": 4}
        flags = _confidence_flags(mod, inbound_count=1)
        assert "write_surface" in flags

    def test_core_hub(self) -> None:
        mod = {"test_references": 5, "write_surface_hits": 0}
        flags = _confidence_flags(mod, inbound_count=15)
        assert "core_hub" in flags

    def test_no_flags(self) -> None:
        mod = {"test_references": 3, "write_surface_hits": 1}
        flags = _confidence_flags(mod, inbound_count=5)
        assert flags == []


class TestGenerateReport:
    def test_report_structure(self) -> None:
        report = generate_report()
        assert "meta" in report
        assert "summary" in report
        assert "family_distribution" in report
        assert "action_distribution" in report
        assert "cycles" in report
        assert "modules" in report

    def test_summary_keys(self) -> None:
        report = generate_report()
        s = report["summary"]
        assert "total_modules" in s
        assert "total_loc" in s
        assert "over_500_loc" in s
        assert "over_1000_loc" in s
        assert "over_3000_loc" in s
        assert "import_cycles" in s
        assert "parse_errors" in s

    def test_no_parse_errors(self) -> None:
        report = generate_report()
        assert report["summary"]["parse_errors"] == 0

    def test_total_modules_positive(self) -> None:
        report = generate_report()
        assert report["summary"]["total_modules"] > 400

    def test_modules_have_required_fields(self) -> None:
        report = generate_report()
        for mod in report["modules"][:5]:
            assert "path" in mod
            assert "loc" in mod
            assert "family" in mod
            assert "suggested_action" in mod
            assert "confidence_flags" in mod


class TestFormatText:
    def test_produces_nonempty_output(self) -> None:
        report = generate_report()
        text = format_text(report)
        assert len(text) > 100
        assert "MODULE METABOLISM REPORT" in text

    def test_contains_summary_stats(self) -> None:
        report = generate_report()
        text = format_text(report)
        assert "Total modules:" in text
        assert "Total LOC:" in text

    def test_json_roundtrip(self, tmp_path: Path) -> None:
        report = generate_report()
        out = tmp_path / "report.json"
        out.write_text(json.dumps(report, indent=2, default=str))
        loaded = json.loads(out.read_text())
        assert loaded["summary"]["total_modules"] == report["summary"]["total_modules"]
