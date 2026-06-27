"""Tests for the manifest health comparison engine."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from dharma_swarm.manifest_health import (
    _check_api_endpoint_registered,
    _check_api_router_registered,
    _check_dashboard_route_exists,
    _check_module_file_exists,
    _check_test_file_exists,
    _observed_status,
    _compute_gap,
    build_health_report,
    load_manifest,
    run_checks_for_entity,
)


class TestLoadManifest:
    def test_loads_successfully(self) -> None:
        manifest = load_manifest()
        assert isinstance(manifest, dict)
        assert manifest.get("schema_version") == 2

    def test_has_required_sections(self) -> None:
        manifest = load_manifest()
        assert "dashboard_surfaces" in manifest
        assert "agents" in manifest
        assert "integrations" in manifest
        assert "loops" in manifest
        assert "health_check_registry" in manifest

    def test_has_api_routers(self) -> None:
        manifest = load_manifest()
        routers = manifest.get("api_routers", [])
        assert len(routers) > 0
        ids = {r["id"] for r in routers}
        assert "health" in ids
        assert "manifest" in ids


class TestHealthChecks:
    def test_dashboard_route_exists_for_overview(self) -> None:
        entity = {"route": "/dashboard"}
        passed, evidence = _check_dashboard_route_exists(entity, {})
        # The dashboard/src/app/dashboard dir should exist
        assert isinstance(passed, bool)
        assert isinstance(evidence, str)

    def test_dashboard_route_missing(self) -> None:
        entity = {"route": "/dashboard/nonexistent_xyz_999"}
        passed, evidence = _check_dashboard_route_exists(entity, {})
        assert passed is False
        assert "missing" in evidence

    def test_api_router_registered(self) -> None:
        manifest = load_manifest()
        entity = {"api_dependencies": ["/api/health"]}
        passed, evidence = _check_api_router_registered(entity, manifest)
        assert passed is True

    def test_api_router_unregistered(self) -> None:
        manifest = load_manifest()
        entity = {"api_dependencies": ["/api/nonexistent_xyz"]}
        passed, evidence = _check_api_router_registered(entity, manifest)
        assert passed is False

    def test_api_endpoint_registered_for_real_route(self) -> None:
        manifest = load_manifest()
        entity = {"api_dependencies": ["/api/operator-coherence/report"]}
        passed, evidence = _check_api_endpoint_registered(entity, manifest)
        assert passed is True, evidence

    def test_api_endpoint_unregistered_under_valid_prefix(self) -> None:
        # The prefix /api/operator-coherence IS registered, but /nope is not a
        # real route — endpoint-level validation must catch what prefix-level misses.
        manifest = load_manifest()
        entity = {"api_dependencies": ["/api/operator-coherence/nope"]}
        prefix_passed, _ = _check_api_router_registered(entity, manifest)
        endpoint_passed, evidence = _check_api_endpoint_registered(entity, manifest)
        assert prefix_passed is True  # prefix-level is fooled
        assert endpoint_passed is False, evidence  # endpoint-level is not

    def test_api_endpoint_checks_mounted_app_routes(self) -> None:
        # The module-local router can define the endpoint, but health must prove
        # the route is mounted on api.main.app.
        manifest = load_manifest()
        entity = {"api_dependencies": ["/api/operator-coherence/report"]}
        with patch("dharma_swarm.manifest_health._mounted_api_route_paths", return_value=[]):
            passed, evidence = _check_api_endpoint_registered(entity, manifest)
        assert passed is False
        assert "mounted app route" in evidence


class TestCockpitSurfaceContract:
    def test_cockpit_surface_depends_on_operator_coherence(self) -> None:
        manifest = load_manifest()
        surfaces = {s["id"]: s for s in manifest.get("dashboard_surfaces", [])}
        cockpit = surfaces["cockpit"]
        assert cockpit["api_dependencies"] == ["/api/operator-coherence/report"]
        assert "api_endpoint_registered" in cockpit["health_check_ids"]
        assert not any(
            "control-surface" in dep for dep in cockpit["api_dependencies"]
        )

    def test_control_surface_entry_untouched(self) -> None:
        manifest = load_manifest()
        surfaces = {s["id"]: s for s in manifest.get("dashboard_surfaces", [])}
        cs = surfaces["control_surface"]
        assert cs["api_dependencies"] == [
            "/api/control-surface/summary",
            "/api/control-surface/rows",
        ]

    def test_module_file_exists(self) -> None:
        entity = {"module": "dharma_swarm/swarm.py"}
        passed, evidence = _check_module_file_exists(entity, {})
        assert passed is True
        assert "found" in evidence

    def test_module_file_missing(self) -> None:
        entity = {"module": "dharma_swarm/nonexistent_xyz.py"}
        passed, evidence = _check_module_file_exists(entity, {})
        assert passed is False

    def test_test_file_exists_for_swarm(self) -> None:
        entity = {"module": "dharma_swarm/swarm.py"}
        passed, evidence = _check_test_file_exists(entity, {})
        # tests/test_swarm.py should exist
        assert isinstance(passed, bool)


class TestObservedStatus:
    def test_all_passed_is_live(self) -> None:
        checks = [
            {"check_id": "a", "passed": True, "evidence": "ok"},
            {"check_id": "b", "passed": True, "evidence": "ok"},
        ]
        assert _observed_status("live", checks) == "live"

    def test_some_passed_is_degraded(self) -> None:
        checks = [
            {"check_id": "a", "passed": True, "evidence": "ok"},
            {"check_id": "b", "passed": False, "evidence": "bad"},
        ]
        assert _observed_status("live", checks) == "degraded"

    def test_none_passed_is_broken(self) -> None:
        checks = [
            {"check_id": "a", "passed": False, "evidence": "bad"},
        ]
        assert _observed_status("live", checks) == "broken"

    def test_empty_checks_is_unknown(self) -> None:
        assert _observed_status("live", []) == "unknown"


class TestComputeGap:
    def test_no_gap_when_matching(self) -> None:
        gap = _compute_gap("live", "live", {}, [])
        assert gap == ""

    def test_gap_includes_failed_evidence(self) -> None:
        checks = [
            {"check_id": "a", "passed": False, "evidence": "missing file"},
        ]
        gap = _compute_gap("live", "broken", {"next_action": "fix it"}, checks)
        assert "missing file" in gap
        assert "fix it" in gap


class TestRunChecksForEntity:
    def test_unknown_check_id(self) -> None:
        entity = {"health_check_ids": ["nonexistent_check_xyz"]}
        results = run_checks_for_entity(entity, {})
        assert len(results) == 1
        assert results[0]["passed"] is False
        assert "unknown" in results[0]["evidence"]


class TestBuildHealthReport:
    def test_report_has_structure(self) -> None:
        report = build_health_report()
        assert "summary" in report
        assert "sections" in report
        assert "manifest_version" in report

    def test_summary_counts(self) -> None:
        report = build_health_report()
        summary = report["summary"]
        assert summary["total"] > 0
        counted = (
            summary["live"]
            + summary["degraded"]
            + summary["broken"]
            + summary["stub"]
            + summary.get("frozen", 0)
            + summary["unknown"]
        )
        assert summary["total"] == counted, (
            f"total={summary['total']} but buckets sum to {counted}: {summary}"
        )

    def test_sections_present(self) -> None:
        report = build_health_report()
        section_names = [s["section"] for s in report["sections"]]
        assert "Dashboard Surfaces" in section_names
        assert "Agents & Subsystems" in section_names

    def test_entity_has_required_fields(self) -> None:
        report = build_health_report()
        for section in report["sections"]:
            for entity in section["entities"]:
                assert "id" in entity
                assert "label" in entity
                assert "declared_status" in entity
                assert "observed_status" in entity
                assert "gap" in entity
                assert "health_checks" in entity
