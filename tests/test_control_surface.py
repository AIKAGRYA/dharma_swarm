"""Tests for the Control Surface Projector v0.

Verifies that declared manifest intent is NOT treated as observed truth.
Observed reality comes from code, runtime, evidence adapters — not YAML.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import pytest
import yaml

from dharma_swarm.operator_core.control_surface import (
    COHERENCE_STATES,
    ControlSurfaceRow,
    _broken_register_rows,
    _manifest_api_router_rows,
    _manifest_dashboard_page_rows,
    _needs_human_decision,
    _observe_api_router,
    _observe_dashboard_page,
    build_control_surface_rows,
    build_control_surface_summary,
    load_active_surface_manifest,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal repo layout for testing."""
    manifest = {
        "schema_version": 2,
        "last_updated": "2026-05-11",
        "api_routers": [
            {"id": "health", "prefix": "/api/health", "module": "api.routers.health"},
            {"id": "missing", "prefix": "/api/missing", "module": "api.routers.nonexistent"},
        ],
        "dashboard_surfaces": [
            {
                "id": "overview",
                "label": "Overview",
                "route": "/dashboard",
                "status": "live",
                "priority": "p0",
                "health_check_ids": [],
                "api_dependencies": [],
            },
            {
                "id": "ghost",
                "label": "Ghost Page",
                "route": "/dashboard/ghost",
                "status": "live",
                "priority": "p1",
                "health_check_ids": [],
                "api_dependencies": [],
            },
        ],
        "agents": [
            {
                "id": "test_agent",
                "label": "Test Agent",
                "module": "dharma_swarm/test_agent.py",
                "status": "live",
                "priority": "p0",
                "health_check_ids": [],
                "wired_to": [],
            },
        ],
        "integrations": [],
        "loops": [],
    }
    manifest_path = tmp_path / "ACTIVE_SURFACE_MANIFEST.yaml"
    manifest_path.write_text(yaml.dump(manifest, default_flow_style=False))

    # API directory with main.py that registers /api/health
    api_dir = tmp_path / "api"
    api_dir.mkdir()
    routers_dir = api_dir / "routers"
    routers_dir.mkdir()
    (routers_dir / "health.py").write_text("router = None\n")
    (api_dir / "main.py").write_text(
        'include_router(health_router)  # prefix /api/health\n'
    )

    # Dashboard page for overview (exists) but not ghost
    dash_dir = tmp_path / "dashboard" / "src" / "app" / "dashboard"
    dash_dir.mkdir(parents=True)
    (dash_dir / "page.tsx").write_text("export default function Overview(){}\n")

    # Agent module exists
    ds_dir = tmp_path / "dharma_swarm"
    ds_dir.mkdir()
    (ds_dir / "test_agent.py").write_text("# agent\n")

    # Tests directory with test file for agent
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_test_agent.py").write_text("def test_ok(): pass\n")

    return tmp_path


@pytest.fixture()
def tmp_broken_register(tmp_path: Path) -> Path:
    """Create a minimal BROKEN_REGISTER.md."""
    br_dir = tmp_path / "docs" / "state"
    br_dir.mkdir(parents=True)
    br_path = br_dir / "BROKEN_REGISTER.md"
    br_path.write_text(textwrap.dedent("""\
        # BROKEN REGISTER

        ## OPEN ITEMS

        ### BR-099 — Test broken item
        - **first_observed:** 2026-05-01
        - **last_verified:** 2026-05-11
        - **severity:** BLOCKER
        - **domain:** runtime
        - **root_cause:** Something is broken at file:123
        - **blast_radius:** Everything downstream
        - **evidence:** file:123 shows the problem
        - **status:** OPEN

        ### BR-100 — Another broken item
        - **first_observed:** 2026-05-10
        - **last_verified:** 2026-05-11
        - **severity:** DEGRADED
        - **domain:** docs
        - **root_cause:** Docs are stale
        - **blast_radius:** Onboarding
        - **evidence:** docs/stale.md
        - **status:** PARTIAL

        ## CLOSED ITEMS

        ### BR-001 — Fixed item
        - **status:** FIXED
    """))
    return tmp_path


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------


class TestLoadManifest:
    def test_loads_valid_manifest(self, tmp_repo: Path) -> None:
        manifest = load_active_surface_manifest(tmp_repo)
        assert manifest["schema_version"] == 2
        assert len(manifest["api_routers"]) == 2

    def test_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        manifest = load_active_surface_manifest(tmp_path)
        assert manifest == {}


# ---------------------------------------------------------------------------
# Manifest is declared intent, NOT observed truth
# ---------------------------------------------------------------------------


class TestManifestIsNotObservedTruth:
    """Core test: manifest status must never be treated as observed reality."""

    def test_api_router_missing_module_is_drifted(self, tmp_repo: Path) -> None:
        manifest = load_active_surface_manifest(tmp_repo)
        rows = _manifest_api_router_rows(manifest)
        missing_row = [r for r in rows if r.id == "api.missing"][0]

        # Before observation, observed_state is empty (not set from manifest)
        assert missing_row.observed_state == ""

        # Now observe reality
        _observe_api_router(missing_row, tmp_repo)

        # The module file does not exist — observed state should be drifted
        assert missing_row.coherence_state == "drifted"
        assert missing_row.observed_state == "module file missing"
        assert "module_missing" in missing_row.gap_codes

    def test_existing_router_is_bound(self, tmp_repo: Path) -> None:
        manifest = load_active_surface_manifest(tmp_repo)
        rows = _manifest_api_router_rows(manifest)
        health_row = [r for r in rows if r.id == "api.health"][0]
        _observe_api_router(health_row, tmp_repo)

        assert health_row.observed_state == "live"
        assert health_row.coherence_state == "bound"

    def test_dashboard_page_declared_live_but_missing_is_drifted(self, tmp_repo: Path) -> None:
        manifest = load_active_surface_manifest(tmp_repo)
        rows = _manifest_dashboard_page_rows(manifest)
        ghost_row = [r for r in rows if r.id == "dashboard.ghost"][0]

        assert ghost_row.declared_state == "live"

        _observe_dashboard_page(ghost_row, tmp_repo)

        assert ghost_row.coherence_state == "drifted"
        assert "dashboard_page_missing" in ghost_row.gap_codes

    def test_existing_dashboard_page_is_bound(self, tmp_repo: Path) -> None:
        manifest = load_active_surface_manifest(tmp_repo)
        rows = _manifest_dashboard_page_rows(manifest)
        overview = [r for r in rows if r.id == "dashboard.overview"][0]
        _observe_dashboard_page(overview, tmp_repo)

        assert overview.coherence_state == "bound"
        assert overview.observed_state == "live"


# ---------------------------------------------------------------------------
# Broken Register adapter
# ---------------------------------------------------------------------------


class TestBrokenRegister:
    def test_parses_open_items(self, tmp_broken_register: Path) -> None:
        rows = _broken_register_rows(tmp_broken_register)
        assert len(rows) >= 2

        br099 = [r for r in rows if "BR-099" in r.label][0]
        assert br099.kind == "broken_register"
        assert br099.coherence_state == "drifted"
        assert br099.priority == "p0"  # BLOCKER -> p0
        assert br099.desired_state == "FIXED"

    def test_closed_items_excluded(self, tmp_broken_register: Path) -> None:
        rows = _broken_register_rows(tmp_broken_register)
        ids = [r.id for r in rows]
        assert not any("br_001" in rid for rid in ids)

    def test_degraded_severity_gets_p1(self, tmp_broken_register: Path) -> None:
        rows = _broken_register_rows(tmp_broken_register)
        br100 = [r for r in rows if "BR-100" in r.label][0]
        assert br100.priority == "p1"


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_counts_by_coherence_state(self, tmp_repo: Path) -> None:
        rows = build_control_surface_rows(repo_root=tmp_repo)
        summary = build_control_surface_summary(rows)

        assert summary["total"] == len(rows)
        assert summary["total"] > 0

        state_sum = (
            summary["bound"]
            + summary["partial"]
            + summary["drifted"]
            + summary["declared_only"]
            + summary["unknown"]
        )
        assert state_sum == summary["total"]

    def test_summary_has_required_fields(self, tmp_repo: Path) -> None:
        summary = build_control_surface_summary(repo_root=tmp_repo)
        required = [
            "total", "bound", "partial", "drifted", "declared_only",
            "unknown", "human_decision_required_count", "p0_count",
            "p1_count", "generated_at", "sources_consulted",
        ]
        for field in required:
            assert field in summary, f"missing field: {field}"


# ---------------------------------------------------------------------------
# Human decision policy
# ---------------------------------------------------------------------------


class TestHumanDecisionPolicy:
    def test_p0_drifted_needs_human(self) -> None:
        row = ControlSurfaceRow(
            id="test",
            kind="api_router",
            label="test",
            priority="p0",
            coherence_state="drifted",
        )
        assert _needs_human_decision(row) is True

    def test_broken_register_open_needs_human(self) -> None:
        row = ControlSurfaceRow(
            id="br.test",
            kind="broken_register",
            label="BR-999: test",
            declared_state="OPEN",
        )
        assert _needs_human_decision(row) is True

    def test_incubating_store_needs_human(self) -> None:
        row = ControlSurfaceRow(
            id="state.test",
            kind="state_writer",
            label="test store",
            authority_role="incubating",
        )
        assert _needs_human_decision(row) is True

    def test_bound_p1_does_not_need_human(self) -> None:
        row = ControlSurfaceRow(
            id="test",
            kind="api_router",
            label="test",
            priority="p1",
            coherence_state="bound",
        )
        assert _needs_human_decision(row) is False


# ---------------------------------------------------------------------------
# Full build integration
# ---------------------------------------------------------------------------


class TestFullBuild:
    def test_build_produces_rows(self, tmp_repo: Path) -> None:
        rows = build_control_surface_rows(repo_root=tmp_repo)
        assert len(rows) > 0

    def test_row_contract_fields(self, tmp_repo: Path) -> None:
        rows = build_control_surface_rows(repo_root=tmp_repo)
        required_fields = {
            "id", "kind", "label", "authority_role", "declared_state",
            "desired_state", "observed_state", "coherence_state", "priority",
            "owner_module", "truth_owner", "evidence", "freshness",
            "gap_codes", "next_action", "human_decision_required", "source_refs",
        }
        for row in rows:
            row_dict = row.to_dict()
            for field in required_fields:
                assert field in row_dict, f"row {row.id} missing field: {field}"

    def test_coherence_states_are_valid(self, tmp_repo: Path) -> None:
        rows = build_control_surface_rows(repo_root=tmp_repo)
        for row in rows:
            assert row.coherence_state in COHERENCE_STATES, (
                f"row {row.id} has invalid coherence_state: {row.coherence_state}"
            )

    def test_at_least_one_drifted_row(self, tmp_repo: Path) -> None:
        """At least one declared manifest entry should be observed as degraded/drifted."""
        rows = build_control_surface_rows(repo_root=tmp_repo)
        drifted = [r for r in rows if r.coherence_state == "drifted"]
        assert len(drifted) > 0, "expected at least one drifted row from manifest vs reality"

    def test_at_least_one_human_decision_row(self, tmp_repo: Path) -> None:
        """At least one row should require human decision."""
        rows = build_control_surface_rows(repo_root=tmp_repo)
        human = [r for r in rows if r.human_decision_required]
        assert len(human) > 0, "expected at least one human_decision_required row"
