"""Tests for the Control Surface Projector v0.

Verifies that declared manifest intent is NOT treated as observed truth.
Observed reality comes from code, runtime, evidence adapters — not YAML.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import textwrap
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

import dharma_swarm.operator_core.control_surface as control_surface
import dharma_swarm.operator_core.control_surface_memory as control_surface_memory_module
from dharma_swarm.operator_core.control_surface import (
    COHERENCE_STATES,
    AgentHandoffPrompt,
    ControlSurfaceRow,
    DisplayHints,
    EvidenceItem,
    HumanDecisionContext,
    SourceRef,
    VerificationEvent,
    _broken_register_rows,
    _build_human_decision_context,
    _go_receipt_rows,
    _manifest_api_router_rows,
    _manifest_dashboard_page_rows,
    _needs_human_decision,
    _observe_api_router,
    _observe_dashboard_page,
    build_control_surface_rows,
    build_control_surface_summary,
    generate_handoff_prompt,
    load_active_surface_manifest,
)
from dharma_swarm.operator_core.control_surface_models import (
    ControlSurfaceEnvelope,
    SourceError,
    _compute_display_hints,
)
from dharma_swarm.operator_core.control_surface_memory import (
    ROLLOUT_ENV_VAR,
    ROLLOUT_STATES,
    memory_kernel_control_rows,
    project_context_canary_report,
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


def _write_control_surface_runtime_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE runtime_receipts (
                receipt_id TEXT PRIMARY KEY,
                receipt_type TEXT NOT NULL,
                run_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL DEFAULT '',
                trace_id TEXT NOT NULL DEFAULT '',
                correlation_id TEXT NOT NULL DEFAULT '',
                causation_id TEXT NOT NULL DEFAULT '',
                parent_run_id TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL DEFAULT '',
                idempotency_key TEXT NOT NULL DEFAULT '',
                side_effect_key TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE idempotency_records (
                idempotency_key TEXT NOT NULL,
                side_effect_key TEXT NOT NULL,
                run_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL DEFAULT '',
                trace_id TEXT NOT NULL DEFAULT '',
                correlation_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                result_receipt_id TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (idempotency_key, side_effect_key)
            );
            """
        )
        conn.execute(
            "INSERT INTO runtime_receipts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "receipt-control-1",
                "a2a_task",
                "run-control-1",
                "task-control-1",
                "trace-control-1",
                "corr-control-1",
                "",
                "",
                "agent-control-1",
                "idem-control-1",
                "a2a.submit",
                "completed",
                "{}",
                "2026-06-04T01:04:00+00:00",
            ),
        )
        conn.execute(
            "INSERT INTO idempotency_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "idem-control-1",
                "a2a.submit",
                "run-control-1",
                "task-control-1",
                "trace-control-1",
                "corr-control-1",
                "completed",
                "receipt-control-1",
                "{}",
                "2026-06-04T01:00:00+00:00",
                "2026-06-04T01:04:00+00:00",
            ),
        )
        conn.commit()


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

    def test_build_rows_appends_live_ops_projection(self, monkeypatch, tmp_repo: Path) -> None:
        sentinel = ControlSurfaceRow(
            id="live_ops.test",
            kind="fleet",
            label="Live Ops Sentinel",
            authority_role="observed_authority",
            declared_state="live",
            desired_state="live",
            observed_state="live",
            coherence_state="bound",
            priority="p0",
            owner_module="scripts/runtime/live_ops_census.py",
            truth_owner="live_ops_census",
        )

        monkeypatch.setattr(control_surface, "_live_ops_census_rows", lambda _root: [sentinel])

        rows = build_control_surface_rows(repo_root=tmp_repo)
        assert any(row.id == "live_ops.test" for row in rows)


# ---------------------------------------------------------------------------
# Broken Register adapter
# ---------------------------------------------------------------------------


class TestBrokenRegister:
    def test_parses_open_items(self, tmp_broken_register: Path) -> None:
        rows = _broken_register_rows(tmp_broken_register)
        assert len(rows) == 2

        br099 = [r for r in rows if "BR-099" in r.label][0]
        assert br099.kind == "broken_register"
        assert br099.raw["status"] == "OPEN"
        assert br099.raw["is_open_like"] is True
        assert br099.raw["is_closed_like"] is False
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
# Runtime truth projection
# ---------------------------------------------------------------------------


class TestRuntimeTruthProjection:
    def test_runtime_state_row_uses_explicit_runtime_db_projection(
        self,
        tmp_repo: Path,
        tmp_path: Path,
    ) -> None:
        runtime_db = tmp_path / "runtime.db"
        _write_control_surface_runtime_db(runtime_db)
        before_hash = hashlib.sha256(runtime_db.read_bytes()).hexdigest()
        before_sidecars = sorted(path.name for path in tmp_path.glob("runtime.db*"))

        rows = build_control_surface_rows(repo_root=tmp_repo, runtime_db=runtime_db)
        row = next(item for item in rows if item.id == "runtime.state_db")
        after_hash = hashlib.sha256(runtime_db.read_bytes()).hexdigest()
        after_sidecars = sorted(path.name for path in tmp_path.glob("runtime.db*"))

        assert before_hash == after_hash
        assert before_sidecars == after_sidecars == ["runtime.db"]
        assert row.raw["runtime_truth_summary"]["latest_receipt"] == (
            "runtime_receipts:receipt-control-1"
        )
        assert row.raw["runtime_truth_summary"]["run_id"] == "run-control-1"
        assert any(
            evidence.kind == "db_probe"
            and evidence.source == "runtime_receipts:receipt-control-1"
            and "RuntimeTruthPacket" in evidence.provenance_chain
            for evidence in row.evidence
        )


def _write_delegation_runs_db(db_path: Path) -> None:
    """Minimal runtime DB with a delegation_runs receipt_json row (spine pulse source)."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE delegation_runs ("
            "run_id TEXT PRIMARY KEY, task_id TEXT, status TEXT, "
            "started_at TEXT, trace_id TEXT DEFAULT '', receipt_json TEXT)"
        )

        def _mk(run_id: str, status: str, provider: str, ago_seconds: int) -> None:
            ts = (now - timedelta(seconds=ago_seconds)).isoformat()
            blob = json.dumps(
                {
                    "trace_id": f"trace-{run_id}",
                    "provider": provider,
                    "model": "m1",
                    "status": status,
                    "started_at": ts,
                }
            )
            conn.execute(
                "INSERT INTO delegation_runs VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, f"task-{run_id}", "completed", ts, f"trace-{run_id}", blob),
            )

        _mk("r1", "ok", "anthropic", 30)
        _mk("r2", "ok", "openrouter", 120)
        _mk("r3", "dropped", "none", 300)
        _mk("r4", "ok", "groq", 5000)  # older than the 1h window


class TestSpinePulseProjection:
    def test_spine_pulse_row_projects_metrics_read_only(
        self,
        tmp_repo: Path,
        tmp_path: Path,
    ) -> None:
        runtime_db = tmp_path / "runtime.db"
        _write_delegation_runs_db(runtime_db)
        before_hash = hashlib.sha256(runtime_db.read_bytes()).hexdigest()

        rows = build_control_surface_rows(repo_root=tmp_repo, runtime_db=runtime_db)
        row = next(item for item in rows if item.id == "spine.pulse")

        after_hash = hashlib.sha256(runtime_db.read_bytes()).hexdigest()
        assert before_hash == after_hash  # read-only, no mutation
        assert row.coherence_state == "bound"
        assert row.raw["present"] is True
        assert row.raw["receipts_last_hour"] == 3
        assert row.raw["dispatch_dropoff_count"] == 1
        assert row.raw["last_receipt_age_seconds"] is not None
        assert row.raw["last_receipt_age_seconds"] >= 0

    def test_spine_pulse_row_graceful_absence(
        self,
        tmp_repo: Path,
        tmp_path: Path,
    ) -> None:
        runtime_db = tmp_path / "absent-runtime.db"  # never created
        rows = build_control_surface_rows(repo_root=tmp_repo, runtime_db=runtime_db)
        row = next(item for item in rows if item.id == "spine.pulse")

        assert row.raw["present"] is False
        assert row.coherence_state == "declared_only"
        assert "spine_not_live" in row.gap_codes
        assert "spine not live on this host" in row.raw["detail"]


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
            raw={
                "status": "OPEN",
                "is_open_like": True,
                "is_closed_like": False,
            },
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


# ---------------------------------------------------------------------------
# MemoryKernel operator controls
# ---------------------------------------------------------------------------


class TestMemoryKernelOperatorRows:
    def test_projects_required_memory_kernel_rows(self, tmp_repo: Path) -> None:
        rows = memory_kernel_control_rows(tmp_repo)
        ids = {row.id for row in rows}

        assert {
            "memory.census",
            "memory.adapter_coverage",
            "memory.readiness",
            "memory.writer_sentinel",
            "memory.context_shadow",
            "memory.context_canary",
            "memory.knowledgeops_intake",
            "memory.promotion_queue",
            "memory.knowledgeops_bridge",
            "memory.write_receipts",
            "memory.live_promotion",
            "memory.rollout_gate",
            "memory.rollback_switch",
        }.issubset(ids)

    def test_rollout_gate_defaults_safe_off(
        self,
        tmp_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv(ROLLOUT_ENV_VAR, raising=False)

        rows = memory_kernel_control_rows(tmp_repo)
        gate = [row for row in rows if row.id == "memory.rollout_gate"][0]

        assert gate.observed_state == "off"
        assert tuple(gate.raw["allowed_states"]) == ROLLOUT_STATES
        assert gate.raw["default_state"] == "off"
        assert gate.raw["burn_in_safety_state"] == "safe"
        assert gate.raw["burn_in_safe"] is True
        assert gate.raw["burn_in_blockers"] == ()
        assert gate.raw["max_ready_tier"] in set(gate.raw["ready_tiers"])
        assert gate.raw["rollout_exceeds_ready_tier"] is False

    def test_invalid_rollout_state_resolves_to_off(
        self,
        tmp_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(ROLLOUT_ENV_VAR, "unsafe-now")

        rows = memory_kernel_control_rows(tmp_repo)
        gate = [row for row in rows if row.id == "memory.rollout_gate"][0]

        assert gate.observed_state == "off"
        assert "memory_kernel_rollout_invalid_state" in gate.gap_codes
        assert gate.raw["burn_in_safety_state"] == "blocked"
        assert "rollout_state_valid" in gate.raw["burn_in_blockers"]

    def test_readiness_row_projects_strict_accounting_fields(
        self,
        tmp_repo: Path,
    ) -> None:
        rows = memory_kernel_control_rows(tmp_repo)
        readiness = [row for row in rows if row.id == "memory.readiness"][0]

        assert readiness.raw["schema_version"] == "memory_kernel_readiness.v1"
        assert readiness.raw["strict_readiness_state"] in {
            "strict_ready",
            "strict_blocked",
        }
        assert "accounted_surface_count" in readiness.raw
        assert "accounted_surface_total" in readiness.raw
        assert "required_accounted_surface_count" in readiness.raw
        assert "required_surface_count" in readiness.raw

    def test_preview_rollout_is_blocked_without_strict_readiness(
        self,
        tmp_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(ROLLOUT_ENV_VAR, "preview")
        monkeypatch.setenv("DHARMA_MEMORY_KERNEL_HOME", str(tmp_repo / "empty-home"))

        rows = memory_kernel_control_rows(tmp_repo)
        gate = [row for row in rows if row.id == "memory.rollout_gate"][0]

        assert gate.observed_state == "preview"
        assert gate.raw["burn_in_safety_state"] == "blocked"
        assert gate.raw["burn_in_safe"] is False
        assert "memory_kernel_burn_in_blocked" in gate.gap_codes
        assert gate.raw["required_ready_tier"] == "m3_safe_context_preview"

    def test_knowledgeops_bridge_row_requires_linked_receipts(self, tmp_repo: Path) -> None:
        rows = memory_kernel_control_rows(tmp_repo)
        bridge = [row for row in rows if row.id == "memory.knowledgeops_bridge"][0]

        assert bridge.observed_state == "blocked"
        assert bridge.raw["schema_version"] == "memory_kernel_knowledgeops_bridge.v1"
        assert bridge.raw["ready"] is False
        assert "no_linked_knowledgeops_canonical_receipt" in bridge.raw["blockers"]

    def test_context_canary_projects_failures(self) -> None:
        report = project_context_canary_report()

        assert report["projection_kind"] == "synthetic_canary"
        assert report["persistence"] == "projected_not_persisted"
        assert report["hard_failure_count"] >= 1

    def test_snapshot_depth_defers_deep_memory_kernel_probe(
        self,
        tmp_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fail_deep_probe(_repo_root: Path):  # noqa: ANN202
            raise AssertionError("snapshot projection must not run deep MemoryKernel probe")

        monkeypatch.setattr(control_surface_memory_module, "_kernel_projection", fail_deep_probe)

        rows = memory_kernel_control_rows(tmp_repo, depth="snapshot")
        readiness = [row for row in rows if row.id == "memory.readiness"][0]
        census = [row for row in rows if row.id == "memory.census"][0]

        assert readiness.raw["projection_mode"] == "snapshot_deep_probe_deferred"
        assert readiness.raw["deep_probe_deferred"] is True
        assert "memory_deep_probe_deferred" in readiness.gap_codes
        assert census.raw["schema_version"] == "memory_kernel_control_snapshot.v1"


# ---------------------------------------------------------------------------
# Go receipt lane adapter
# ---------------------------------------------------------------------------


class TestGoReceiptRows:
    """Existing G-track files should project through their real repo paths."""

    def test_go_receipt_rows_use_operator_core_bridge_paths(
        self,
        tmp_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("DHARMA_STATE_DIR", str(tmp_repo / ".dharma"))
        paths = [
            "dharma_swarm/operator_core/go_evidence_bridge.py",
            "dharma_swarm/operator_core/go_github_bridge.py",
            "tools/go_sdk/receipt/receipt.go",
            "tools/go_sdk/adaptercontract/contract.go",
            "tools/evidence_ingestor_go/main.go",
            "tools/github_ingestor_go/adapter.go",
            "tools/world_signal_ingestor_go/adapter.go",
        ]
        for rel in paths:
            path = tmp_repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("// test\n", encoding="utf-8")

        rows = _go_receipt_rows(tmp_repo)
        by_id = {row.id: row for row in rows}

        assert set(by_id) == {
            "go.evidence_bridge",
            "go.github_bridge",
            "go.receipt_sdk",
            "go.adapter_contract",
            "go.evidence_ingestor",
            "go.github_ingestor",
            "go.world_signal_ingestor",
            "go.world_signal_receipts",
        }
        assert (
            by_id["go.evidence_bridge"].owner_module
            == "dharma_swarm/operator_core/go_evidence_bridge.py"
        )
        assert (
            by_id["go.github_bridge"].owner_module
            == "dharma_swarm/operator_core/go_github_bridge.py"
        )
        assert not any(
            row.owner_module == "dharma_swarm/go_evidence_bridge.py"
            for row in rows
        )
        assert by_id["go.world_signal_receipts"].coherence_state == "declared_only"

    def test_world_radar_health_row_surfaces_per_source_errors(
        self,
        tmp_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from dharma_swarm.operator_core.control_surface_go import (
            _go_world_radar_health_rows,
        )

        state = tmp_repo / ".dharma"
        monkeypatch.setenv("DHARMA_STATE_DIR", str(state))

        # No health file yet: the loop never ran on this host, no row.
        assert _go_world_radar_health_rows() == []

        health_path = state / "meta" / "world_radar" / "world_radar_health.json"
        health_path.parent.mkdir(parents=True, exist_ok=True)
        health_path.write_text(
            json.dumps(
                {
                    "ok": False,
                    "status": "degraded",
                    "checked_at": "2026-07-02T00:00:00+00:00",
                    "successful_sources": 3,
                    "failed_sources": 1,
                    "scout_invocation_mode": "binary",
                    "ingestor_invocation_mode": "go_run",
                    "source_errors": [
                        {"source": "arxiv_agents", "stage": "scout", "error": "503"}
                    ],
                }
            ),
            encoding="utf-8",
        )

        rows = _go_world_radar_health_rows()
        assert len(rows) == 1
        row = rows[0]
        assert row.id == "go.world_radar_health"
        assert row.coherence_state == "partial"
        assert "1 failed sources" in row.observed_state
        assert "go_world_radar_source_errors" in row.gap_codes
        assert row.raw["scout_invocation_mode"] == "binary"
        assert row.raw["ingestor_invocation_mode"] == "go_run"
        assert row.raw["source_errors"] == [
            {"source": "arxiv_agents", "stage": "scout", "error": "503"}
        ]
        error_evidence = [
            item for item in row.evidence if "source_error source=arxiv_agents" in item.source
        ]
        assert len(error_evidence) == 1

    def test_world_radar_health_row_surfaces_needs_host(
        self,
        tmp_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Toolchain-checked invocation: needs_host reaches the cockpit row."""
        from dharma_swarm.operator_core.control_surface_go import (
            _go_world_radar_health_rows,
        )

        state = tmp_repo / ".dharma"
        monkeypatch.setenv("DHARMA_STATE_DIR", str(state))
        health_path = state / "meta" / "world_radar" / "world_radar_health.json"
        health_path.parent.mkdir(parents=True, exist_ok=True)
        health_path.write_text(
            json.dumps(
                {
                    "ok": False,
                    "status": "degraded",
                    "checked_at": "2026-07-03T00:00:00+00:00",
                    "successful_sources": 0,
                    "failed_sources": 0,
                    "scout_invocation_mode": "needs_host",
                    "ingestor_invocation_mode": "needs_host",
                    "source_errors": [
                        {
                            "source": "world_scout_go",
                            "stage": "scout",
                            "error": (
                                "no prebuilt world_scout_go binary and no Go toolchain "
                                "on PATH — run `make go-build` (or install Go) on this host"
                            ),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        rows = _go_world_radar_health_rows()
        assert len(rows) == 1
        row = rows[0]
        assert row.coherence_state == "partial"
        assert "needs_host" in row.observed_state
        assert "go_world_radar_needs_host" in row.gap_codes
        assert "go_world_radar_source_errors" in row.gap_codes
        assert "make go-build" in row.next_action


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


def _control_surface_client() -> TestClient:
    from api.routers.control_surface import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestControlSurfaceAPI:
    """Tests for /api/control-surface/* endpoints."""

    def test_summary_returns_envelope_with_counts(self) -> None:
        client = _control_surface_client()
        resp = client.get("/api/control-surface/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["schema_version"] == "0.2.0"
        assert body["request_id"]
        assert body["generated_at"]
        assert isinstance(body["source_errors"], list)
        data = body["data"]
        assert data["total"] > 0
        state_sum = (
            data["bound"] + data["partial"] + data["drifted"]
            + data["declared_only"] + data["unknown"]
        )
        assert state_sum == data["total"]
        assert "sources_consulted" in data

    def test_rows_returns_envelope_with_list(self) -> None:
        client = _control_surface_client()
        resp = client.get("/api/control-surface/rows")
        assert resp.status_code == 200
        body = resp.json()
        assert body["schema_version"] == "0.2.0"
        assert body["request_id"]
        assert body["generated_at"]
        rows = body["data"]
        assert isinstance(rows, list)
        assert len(rows) > 0
        first = rows[0]
        assert "id" in first
        assert "coherence_state" in first
        assert "declared_state" in first
        assert "observed_state" in first

    def test_rows_keep_evidence_and_source_refs_structured(self) -> None:
        client = _control_surface_client()
        resp = client.get("/api/control-surface/rows")
        assert resp.status_code == 200
        rows = resp.json()["data"]
        memory_row = [row for row in rows if row["id"] == "memory.census"][0]

        assert isinstance(memory_row["evidence"][0], dict)
        assert "source" in memory_row["evidence"][0]
        assert isinstance(memory_row["source_refs"][0], dict)
        assert "path" in memory_row["source_refs"][0]

    def test_rows_default_to_snapshot_memory_depth(self) -> None:
        client = _control_surface_client()
        resp = client.get("/api/control-surface/rows")
        assert resp.status_code == 200
        rows = resp.json()["data"]
        readiness = [row for row in rows if row["id"] == "memory.readiness"][0]

        assert readiness["raw"]["projection_mode"] == "snapshot_deep_probe_deferred"
        assert readiness["raw"]["deep_probe_deferred"] is True
        assert "memory_deep_probe_deferred" in readiness["gap_codes"]

    def test_summary_reports_snapshot_memory_depth(self) -> None:
        client = _control_surface_client()
        resp = client.get("/api/control-surface/summary")
        assert resp.status_code == 200

        assert resp.json()["data"]["memory_depth"] == "snapshot"

    def test_active_tracks_returns_ten_slot_target_operating_model(self) -> None:
        client = _control_surface_client()
        resp = client.get("/api/control-surface/active-tracks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["source_errors"] == []
        data = body["data"]
        assert data["slot_count"] == len(data["slots"]) == 10
        assert data["policy_slot_capacity"] == data["policy"]["max_active"]
        if data["policy"]["max_active"] != 10:
            assert any("differs from ACTIVE_TRACK.yaml max_active" in warning for warning in data["warnings"])
        titles = {slot["title"] for slot in data["slots"]}
        assert "Spine Runtime Truth" in titles
        assert "A2A Lattice & Shared State" in titles
        assert "Revenue & External Humans Served" in titles
        assert "AgentOps Build Factory" in titles
        assert "North Star & Coherence Governance" in titles
        for slot in data["slots"]:
            assert len(slot["layers"]) == 4
            for layer in slot["layers"]:
                assert "make onboard" in layer["handoff_prompt"]
                assert "make hygiene" in layer["handoff_prompt"]
                assert "/dashboard/cockpit is John's human command front door" in layer["handoff_prompt"]

    def test_apex_command_map_returns_read_only_envelope(self, monkeypatch) -> None:
        import api.routers.control_surface as control_surface_router

        def _fake_builder(*, repo_root=None):
            return {
                "schema_version": "dharma.apex_command_map.v1",
                "authority": {
                    "mode": "read_only",
                    "protected_actions_allowed": False,
                },
                "apex": {"agent_uid": "sarathi"},
                "agents": [{"agent_uid": "codex_composer", "chat_href": "/holon/codex_composer/chat"}],
                "substrate": {},
                "active_missions": {},
                "receipt_roots": {},
                "blockers": ["d4_semantic_receipt_missing"],
            }

        monkeypatch.setattr(control_surface_router, "_get_apex_command_map_builder", lambda: _fake_builder)
        client = _control_surface_client()

        resp = client.get("/api/control-surface/apex/command-map")

        assert resp.status_code == 200
        body = resp.json()
        assert body["schema_version"] == "0.2.0"
        assert body["source_errors"] == []
        assert body["data"]["schema_version"] == "dharma.apex_command_map.v1"
        assert body["data"]["authority"]["protected_actions_allowed"] is False
        assert body["data"]["agents"][0]["chat_href"] == "/holon/codex_composer/chat"

    def test_row_by_id_returns_envelope(self) -> None:
        client = _control_surface_client()
        rows_resp = client.get("/api/control-surface/rows")
        first_id = rows_resp.json()["data"][0]["id"]
        resp = client.get(f"/api/control-surface/rows/{first_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["schema_version"] == "0.2.0"
        assert body["data"]["id"] == first_id

    def test_row_not_found_returns_404(self) -> None:
        client = _control_surface_client()
        resp = client.get("/api/control-surface/rows/nonexistent_row_id")
        assert resp.status_code == 404

    def test_unique_request_ids(self) -> None:
        client = _control_surface_client()
        resp1 = client.get("/api/control-surface/rows")
        resp2 = client.get("/api/control-surface/rows")
        assert resp1.json()["request_id"] != resp2.json()["request_id"]


# ---------------------------------------------------------------------------
# Dashboard page existence
# ---------------------------------------------------------------------------


class TestDashboardControlSurfacePage:
    """Verify /dashboard/control-surface route file exists."""

    def test_control_surface_page_file_exists(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        page = repo_root / "dashboard" / "src" / "app" / "dashboard" / "control-surface" / "page.tsx"
        assert page.exists(), f"control-surface page missing: {page}"

    def test_cockpit_page_file_exists(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        page = repo_root / "dashboard" / "src" / "app" / "dashboard" / "cockpit" / "page.tsx"
        assert page.exists(), f"cockpit page missing: {page}"

    def test_cockpit_renders_operator_coherence_page(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        page = repo_root / "dashboard" / "src" / "app" / "dashboard" / "cockpit" / "page.tsx"
        text = page.read_text(encoding="utf-8")
        assert "OperatorCoherenceCockpit" in text
        assert 'from "@/components/operator-coherence/OperatorCoherenceCockpit"' in text

    def test_control_surface_renders_ops_runbook_panel(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        page = repo_root / "dashboard" / "src" / "app" / "dashboard" / "control-surface" / "page.tsx"
        text = page.read_text(encoding="utf-8")
        assert "OpsRunbookPanel" in text
        assert 'from "@/components/cockpit/OpsRunbookPanel"' in text
        assert "<OpsRunbookPanel rows={rows} selectedRow={selectedRow} />" in text

    def test_control_surface_renders_active_track_portfolio_first(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        page = repo_root / "dashboard" / "src" / "app" / "dashboard" / "control-surface" / "page.tsx"
        text = page.read_text(encoding="utf-8")
        assert "ActiveTrackPortfolioBoard" in text
        assert 'from "@/components/cockpit/ActiveTrackPortfolioBoard"' in text
        assert text.index("<ActiveTrackPortfolioBoard />") < text.index("<NeedsJohnQueue")

    def test_control_surface_renders_ds_goal_mission_cards_panel(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        page = repo_root / "dashboard" / "src" / "app" / "dashboard" / "control-surface" / "page.tsx"
        text = page.read_text(encoding="utf-8")
        assert "DsGoalMissionCardsPanel" in text
        assert 'from "@/components/cockpit/DsGoalMissionCardsPanel"' in text
        assert "<DsGoalMissionCardsPanel />" in text

    def test_control_surface_renders_agentops_work_packet_cards_panel(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        page = repo_root / "dashboard" / "src" / "app" / "dashboard" / "control-surface" / "page.tsx"
        text = page.read_text(encoding="utf-8")
        assert "AgentOpsWorkPacketCardsPanel" in text
        assert 'from "@/components/cockpit/AgentOpsWorkPacketCardsPanel"' in text
        assert "<AgentOpsWorkPacketCardsPanel />" in text

    def test_control_surface_renders_a2a_send_cards_panel(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        page = repo_root / "dashboard" / "src" / "app" / "dashboard" / "control-surface" / "page.tsx"
        text = page.read_text(encoding="utf-8")
        assert "A2ASendCardsPanel" in text
        assert 'from "@/components/cockpit/A2ASendCardsPanel"' in text
        assert "<A2ASendCardsPanel />" in text

    def test_control_surface_page_does_not_import_shell_control(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        page = repo_root / "dashboard" / "src" / "app" / "dashboard" / "control-surface" / "page.tsx"
        text = page.read_text(encoding="utf-8")
        assert "controlPlaneShell" not in text
        assert "runCommand" not in text
        assert "executeCommand" not in text

    def test_ops_runbook_panel_is_display_only(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        panel = repo_root / "dashboard" / "src" / "components" / "cockpit" / "OpsRunbookPanel.tsx"
        text = panel.read_text(encoding="utf-8")
        forbidden_tokens = [
            "onClick",
            "fetch(",
            "window.",
            "navigator.",
            "child_process",
            "controlPlaneShell",
            "runCommand",
            "executeCommand",
            "exec(",
            "spawn(",
            "tracking-",
            "rounded-xl",
        ]
        for token in forbidden_tokens:
            assert token not in text
        assert "restartCommand" in text
        assert "stopPolicy" in text
        assert "<code" in text
        assert "break-words" in text

    def test_static_dashboard_nav_links_cockpit(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        nav = repo_root / "dashboard" / "src" / "lib" / "dashboardNav.ts"
        text = nav.read_text(encoding="utf-8")
        assert 'label: "Cockpit"' in text
        assert 'href: "/dashboard/cockpit"' in text

    def test_control_surface_stays_available_as_technical_route_not_nav_front_door(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        manifest = load_active_surface_manifest(repo_root)
        nav_sections = manifest.get("dashboard_nav_sections", [])
        all_items: list[str] = []
        for section in nav_sections:
            all_items.extend(section.get("items", []))
        assert "Control Surface" not in all_items, (
            "Control Surface should not compete with Cockpit as a second front door"
        )
        surface_ids = [surface.get("id") for surface in manifest.get("dashboard_surfaces", [])]
        assert "control_surface" in surface_ids

    def test_cockpit_in_manifest_nav(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        manifest = load_active_surface_manifest(repo_root)
        nav_sections = manifest.get("dashboard_nav_sections", [])
        all_items: list[str] = []
        for section in nav_sections:
            all_items.extend(section.get("items", []))
        assert "Cockpit" in all_items, "Cockpit not in manifest dashboard_nav_sections"


# ---------------------------------------------------------------------------
# Doctrine: manifest = declared intent, not observed truth
# ---------------------------------------------------------------------------


class TestManifestDoctrine:
    """Manifest rows carry declared_state only; observed_state is computed."""

    def test_manifest_rows_have_empty_observed_state(self, tmp_repo: Path) -> None:
        manifest = load_active_surface_manifest(tmp_repo)
        rows = _manifest_api_router_rows(manifest)
        for row in rows:
            assert row.observed_state == "", (
                f"row {row.id} has observed_state set before observation"
            )

    def test_declared_live_but_missing_is_never_green(self, tmp_repo: Path) -> None:
        manifest = load_active_surface_manifest(tmp_repo)
        rows = _manifest_api_router_rows(manifest)
        missing = [r for r in rows if r.id == "api.missing"][0]
        _observe_api_router(missing, tmp_repo)
        assert missing.coherence_state != "bound", (
            "missing module must not be marked bound"
        )
        assert missing.coherence_state in ("drifted", "partial")


# ---------------------------------------------------------------------------
# EvidenceItem model tests
# ---------------------------------------------------------------------------


class TestEvidenceItem:
    def test_evidence_item_creation(self) -> None:
        item = EvidenceItem(
            kind="file",
            source="dharma_swarm/swarm.py",
            observed_at="2026-05-13T00:00:00+00:00",
            status="present",
            provenance_chain=["manifest api_routers", "file_exists_check"],
        )
        assert item.kind == "file"
        assert item.source == "dharma_swarm/swarm.py"
        assert item.status == "present"
        assert len(item.provenance_chain) == 2

    def test_evidence_item_serialization(self) -> None:
        item = EvidenceItem(
            kind="api_route",
            source="/api/health",
            status="present",
        )
        d = item.model_dump()
        assert d["kind"] == "api_route"
        assert d["source"] == "/api/health"
        assert d["line_range"] is None

    def test_evidence_item_with_line_range(self) -> None:
        item = EvidenceItem(
            kind="file",
            source="some/file.py",
            line_range=(10, 20),
        )
        assert item.line_range == (10, 20)

    def test_evidence_item_raw_content_truncation(self) -> None:
        row = ControlSurfaceRow(id="test", kind="api_router", label="test")
        row.add_evidence("file", "test.py", raw_content="x" * 1000)
        assert len(row.evidence[0].raw_content) == 500  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# SourceRef model tests
# ---------------------------------------------------------------------------


class TestSourceRef:
    def test_source_ref_creation(self) -> None:
        ref = SourceRef(kind="file", path="dharma_swarm/swarm.py", exists=True)
        assert ref.kind == "file"
        assert ref.exists is True

    def test_source_ref_serialization(self) -> None:
        ref = SourceRef(kind="api_route", path="/api/health", exists=False)
        d = ref.model_dump()
        assert d["kind"] == "api_route"
        assert d["exists"] is False


# ---------------------------------------------------------------------------
# VerificationEvent model tests
# ---------------------------------------------------------------------------


class TestVerificationEvent:
    def test_verification_event_creation(self) -> None:
        ev = VerificationEvent(
            timestamp="2026-05-13T00:00:00+00:00",
            event_type="observed",
            detail="First observation",
        )
        assert ev.event_type == "observed"
        assert ev.agent_id is None

    def test_verification_event_with_agent(self) -> None:
        ev = VerificationEvent(
            timestamp="2026-05-13T00:00:00+00:00",
            event_type="fix_attempted",
            detail="Applied patch",
            agent_id="agent-123",
        )
        assert ev.agent_id == "agent-123"


# ---------------------------------------------------------------------------
# Structured evidence in rows
# ---------------------------------------------------------------------------


class TestStructuredEvidenceInRows:
    def test_add_evidence_helper(self) -> None:
        row = ControlSurfaceRow(id="test", kind="api_router", label="test")
        row.add_evidence("file", "some/file.py", status="present")
        assert len(row.evidence) == 1
        assert isinstance(row.evidence[0], EvidenceItem)
        assert row.evidence[0].source == "some/file.py"
        assert row.evidence_labels == ["some/file.py"]

    def test_add_source_ref_helper(self) -> None:
        row = ControlSurfaceRow(id="test", kind="api_router", label="test")
        row.add_source_ref("file", "some/file.py", exists=True)
        assert len(row.source_refs) == 1
        assert isinstance(row.source_refs[0], SourceRef)
        assert row.source_ref_labels == ["some/file.py"]

    def test_to_dict_serializes_structured_evidence(self) -> None:
        row = ControlSurfaceRow(id="test", kind="api_router", label="test")
        row.add_evidence("file", "a.py", status="present")
        row.add_source_ref("file", "a.py", exists=True)
        d = row.to_dict()
        assert isinstance(d["evidence"], list)
        assert isinstance(d["evidence"][0], dict)
        assert d["evidence"][0]["kind"] == "file"
        assert isinstance(d["source_refs"], list)
        assert isinstance(d["source_refs"][0], dict)

    def test_observed_rows_have_structured_evidence(self, tmp_repo: Path) -> None:
        manifest = load_active_surface_manifest(tmp_repo)
        rows = _manifest_api_router_rows(manifest)
        health_row = [r for r in rows if r.id == "api.health"][0]
        _observe_api_router(health_row, tmp_repo)
        assert len(health_row.evidence) > 0
        assert all(isinstance(e, EvidenceItem) for e in health_row.evidence)

    def test_full_build_rows_have_structured_evidence(self, tmp_repo: Path) -> None:
        rows = build_control_surface_rows(repo_root=tmp_repo)
        for row in rows:
            for e in row.evidence:
                assert isinstance(e, EvidenceItem), (
                    f"row {row.id} has non-EvidenceItem: {type(e)}"
                )

    def test_full_build_rows_have_structured_source_refs(self, tmp_repo: Path) -> None:
        rows = build_control_surface_rows(repo_root=tmp_repo)
        for row in rows:
            for ref in row.source_refs:
                assert isinstance(ref, SourceRef), (
                    f"row {row.id} has non-SourceRef: {type(ref)}"
                )

    def test_evidence_labels_backward_compat(self, tmp_repo: Path) -> None:
        rows = build_control_surface_rows(repo_root=tmp_repo)
        for row in rows:
            assert len(row.evidence_labels) == len(row.evidence)


# ---------------------------------------------------------------------------
# HumanDecisionContext tests
# ---------------------------------------------------------------------------


class TestHumanDecisionContext:
    def test_p0_drifted_gets_context(self) -> None:
        row = ControlSurfaceRow(
            id="test",
            kind="api_router",
            label="test",
            priority="p0",
            coherence_state="drifted",
        )
        ctx = _build_human_decision_context(row)
        assert ctx.required is True
        assert "drifted" in ctx.why_now.lower()
        assert ctx.recommended_action != ""

    def test_broken_register_open_gets_context(self) -> None:
        row = ControlSurfaceRow(
            id="br.br_099",
            kind="broken_register",
            label="BR-099: test",
            declared_state="OPEN",
            raw={
                "status": "OPEN",
                "is_open_like": True,
                "is_closed_like": False,
            },
        )
        ctx = _build_human_decision_context(row)
        assert ctx.required is True
        assert "broken register" in ctx.why_now.lower()

    def test_bound_p1_no_decision(self) -> None:
        row = ControlSurfaceRow(
            id="test",
            kind="api_router",
            label="test",
            priority="p1",
            coherence_state="bound",
        )
        ctx = _build_human_decision_context(row)
        assert ctx.required is False

    def test_full_build_populates_human_decision(self, tmp_repo: Path) -> None:
        rows = build_control_surface_rows(repo_root=tmp_repo)
        for row in rows:
            assert row.human_decision is not None
            assert isinstance(row.human_decision, HumanDecisionContext)
            assert row.human_decision.required == row.human_decision_required

    def test_human_decision_in_to_dict(self) -> None:
        row = ControlSurfaceRow(
            id="test",
            kind="api_router",
            label="test",
            priority="p0",
            coherence_state="drifted",
        )
        row.human_decision = _build_human_decision_context(row)
        row.human_decision_required = row.human_decision.required
        d = row.to_dict()
        assert "human_decision" in d
        assert d["human_decision"]["required"] is True


# ---------------------------------------------------------------------------
# AgentHandoffPrompt tests
# ---------------------------------------------------------------------------


class TestAgentHandoffPrompt:
    def test_generate_prompt_for_drifted_row(self, tmp_repo: Path) -> None:
        manifest = load_active_surface_manifest(tmp_repo)
        rows = _manifest_api_router_rows(manifest)
        missing = [r for r in rows if r.id == "api.missing"][0]
        _observe_api_router(missing, tmp_repo)

        prompt = generate_handoff_prompt(missing, repo_root=tmp_repo)
        assert isinstance(prompt, AgentHandoffPrompt)
        assert prompt.row_id == "api.missing"
        assert "api.missing" in prompt.prompt_text
        assert len(prompt.context_files) > 0
        assert len(prompt.expected_tests) > 0
        assert prompt.invariant != ""
        assert prompt.generated_at != ""

    def test_generate_prompt_for_agent_row(self, tmp_repo: Path) -> None:
        rows = build_control_surface_rows(repo_root=tmp_repo)
        agent_rows = [r for r in rows if r.kind == "agent_subsystem"]
        if agent_rows:
            prompt = generate_handoff_prompt(agent_rows[0], repo_root=tmp_repo)
            assert "agent_subsystem" in prompt.prompt_text or "agent" in prompt.prompt_text.lower()

    def test_prompt_contains_anti_slop_gates(self, tmp_repo: Path) -> None:
        rows = build_control_surface_rows(repo_root=tmp_repo)
        prompt = generate_handoff_prompt(rows[0], repo_root=tmp_repo)
        assert "Anti-slop" in prompt.prompt_text
        assert "impact-checked" in prompt.prompt_text


# ---------------------------------------------------------------------------
# API endpoint: handoff prompt
# ---------------------------------------------------------------------------


class TestHandoffPromptAPI:
    def test_handoff_prompt_returns_envelope(self) -> None:
        client = _control_surface_client()
        rows_resp = client.get("/api/control-surface/rows")
        first_id = rows_resp.json()["data"][0]["id"]
        resp = client.post(f"/api/control-surface/rows/{first_id}/handoff-prompt")
        assert resp.status_code == 200
        body = resp.json()
        assert body["schema_version"] == "0.2.0"
        assert body["request_id"]
        data = body["data"]
        assert data["row_id"] == first_id
        assert "prompt_text" in data
        assert "context_files" in data
        assert "expected_tests" in data

    def test_handoff_prompt_404(self) -> None:
        client = _control_surface_client()
        resp = client.post("/api/control-surface/rows/nonexistent/handoff-prompt")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# API endpoint: SSE stream
# ---------------------------------------------------------------------------


class TestSSEStream:
    def test_stream_route_registered(self) -> None:
        """Verify the /stream route is registered in the router."""
        from api.routers.control_surface import router as cs_router
        stream_routes = [
            r for r in cs_router.routes
            if hasattr(r, "path") and "/stream" in r.path  # type: ignore[union-attr]
        ]
        assert len(stream_routes) == 1


# ---------------------------------------------------------------------------
# VerificationTimeline in rows
# ---------------------------------------------------------------------------


class TestVerificationTimeline:
    def test_row_has_empty_timeline_by_default(self) -> None:
        row = ControlSurfaceRow(id="test", kind="api_router", label="test")
        assert row.verification_timeline == []

    def test_timeline_serialization(self) -> None:
        row = ControlSurfaceRow(id="test", kind="api_router", label="test")
        row.verification_timeline.append(
            VerificationEvent(
                timestamp="2026-05-13T00:00:00+00:00",
                event_type="observed",
                detail="First observation",
            )
        )
        d = row.to_dict()
        assert len(d["verification_timeline"]) == 1
        assert d["verification_timeline"][0]["event_type"] == "observed"

    def test_full_build_includes_timeline(self, tmp_repo: Path) -> None:
        rows = build_control_surface_rows(repo_root=tmp_repo)
        for row in rows:
            assert isinstance(row.verification_timeline, list)


# ---------------------------------------------------------------------------
# Backward compatibility: row contract still intact
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_control_surface_row_public_mapping_is_exactly_23_keys(self) -> None:
        payload = ControlSurfaceRow(
            id="test",
            kind="api_router",
            label="test",
        ).to_dict()

        expected_keys = {
            "id", "kind", "label", "authority_role", "declared_state",
            "desired_state", "observed_state", "coherence_state", "priority",
            "owner_module", "truth_owner", "evidence", "evidence_labels",
            "freshness", "gap_codes", "next_action",
            "human_decision_required", "human_decision", "source_refs",
            "source_ref_labels", "verification_timeline", "display_hints",
            "raw",
        }
        assert len(payload) == 23
        assert set(payload) == expected_keys

    def test_row_dict_has_all_original_fields(self, tmp_repo: Path) -> None:
        rows = build_control_surface_rows(repo_root=tmp_repo)
        original_fields = {
            "id", "kind", "label", "authority_role", "declared_state",
            "desired_state", "observed_state", "coherence_state", "priority",
            "owner_module", "truth_owner", "evidence", "freshness",
            "gap_codes", "next_action", "human_decision_required", "source_refs",
            "raw",
        }
        for row in rows:
            d = row.to_dict()
            for field in original_fields:
                assert field in d, f"row {row.id} missing original field: {field}"

    def test_row_dict_has_new_fields(self, tmp_repo: Path) -> None:
        rows = build_control_surface_rows(repo_root=tmp_repo)
        new_fields = {
            "evidence_labels", "source_ref_labels",
            "human_decision", "verification_timeline",
            "display_hints",
        }
        for row in rows:
            d = row.to_dict()
            for field in new_fields:
                assert field in d, f"row {row.id} missing new field: {field}"


# ---------------------------------------------------------------------------
# Display hints
# ---------------------------------------------------------------------------


class TestDisplayHints:
    def test_display_hints_model_creation(self) -> None:
        hints = DisplayHints(severity_rank=1, tone="critical", icon_key="server", group="api")
        assert hints.severity_rank == 1
        assert hints.tone == "critical"
        assert hints.freshness_state == "unknown"
        assert hints.available_actions == []

    def test_display_hints_serialization(self) -> None:
        hints = DisplayHints(
            severity_rank=2,
            tone="warning",
            icon_key="alert-triangle",
            group="issues",
            freshness_state="stale",
            available_actions=["investigate", "handoff"],
        )
        d = hints.model_dump()
        assert d["severity_rank"] == 2
        assert d["tone"] == "warning"
        assert d["available_actions"] == ["investigate", "handoff"]

    def test_drifted_p0_gets_critical_tone(self) -> None:
        row = ControlSurfaceRow(
            id="test", kind="api_router", label="test",
            coherence_state="drifted", priority="p0",
        )
        hints = _compute_display_hints(row)
        assert hints.tone == "critical"
        assert hints.severity_rank == 0
        assert "investigate" in hints.available_actions
        assert "handoff" in hints.available_actions

    def test_bound_p1_gets_ok_tone(self) -> None:
        row = ControlSurfaceRow(
            id="test", kind="organ", label="test",
            coherence_state="bound", priority="p1",
        )
        hints = _compute_display_hints(row)
        assert hints.tone == "ok"
        assert hints.severity_rank == 11
        assert "investigate" not in hints.available_actions
        assert "handoff" not in hints.available_actions

    def test_partial_gets_warning_tone(self) -> None:
        row = ControlSurfaceRow(
            id="test", kind="dashboard_page", label="test",
            coherence_state="partial", priority="p1",
        )
        hints = _compute_display_hints(row)
        assert hints.tone == "warning"
        assert hints.group == "dashboard"
        assert hints.icon_key == "layout-dashboard"

    def test_broken_register_gets_close_br_action(self) -> None:
        row = ControlSurfaceRow(
            id="br.001", kind="broken_register", label="BR-001",
            coherence_state="drifted", priority="p0",
            human_decision_required=True,
        )
        hints = _compute_display_hints(row)
        assert "close_br" in hints.available_actions
        assert "decide" in hints.available_actions
        assert hints.group == "issues"
        assert hints.icon_key == "alert-triangle"

    def test_kind_group_mapping(self) -> None:
        for kind, expected_group in [
            ("api_router", "api"),
            ("dashboard_page", "dashboard"),
            ("runtime_store", "runtime"),
            ("agent_subsystem", "agents"),
            ("go_receipt", "go_sdk"),
            ("feedback_loop", "loops"),
            ("cron_job", "cron"),
        ]:
            row = ControlSurfaceRow(id="t", kind=kind, label="t")
            hints = _compute_display_hints(row)
            assert hints.group == expected_group, f"{kind} → {hints.group}, expected {expected_group}"

    def test_full_build_populates_display_hints(self, tmp_repo: Path) -> None:
        rows = build_control_surface_rows(repo_root=tmp_repo)
        for row in rows:
            assert row.display_hints is not None, f"row {row.id} has no display_hints"
            assert row.display_hints.tone in ("critical", "warning", "info", "ok")
            assert isinstance(row.display_hints.severity_rank, int)
            assert isinstance(row.display_hints.available_actions, list)

    def test_display_hints_in_to_dict(self) -> None:
        row = ControlSurfaceRow(
            id="test", kind="api_router", label="test",
            coherence_state="drifted", priority="p0",
        )
        row.display_hints = _compute_display_hints(row)
        d = row.to_dict()
        assert "display_hints" in d
        assert d["display_hints"]["tone"] == "critical"
        assert d["display_hints"]["icon_key"] == "server"


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


class TestControlSurfaceEnvelope:
    def test_envelope_model_creation(self) -> None:
        envelope = ControlSurfaceEnvelope(
            schema_version="0.2.0",
            request_id="abc-123",
            generated_at="2026-05-11T12:00:00+00:00",
            data={"total": 42},
        )
        assert envelope.schema_version == "0.2.0"
        assert envelope.request_id == "abc-123"
        assert envelope.data == {"total": 42}
        assert envelope.source_errors == []

    def test_envelope_with_source_errors(self) -> None:
        err = SourceError(source="operating_facts", error="import failed")
        envelope = ControlSurfaceEnvelope(
            schema_version="0.2.0",
            request_id="abc-123",
            generated_at="2026-05-11T12:00:00+00:00",
            source_errors=[err],
            data=None,
        )
        d = envelope.model_dump()
        assert len(d["source_errors"]) == 1
        assert d["source_errors"][0]["source"] == "operating_facts"

    def test_envelope_serialization(self) -> None:
        envelope = ControlSurfaceEnvelope(
            schema_version="0.2.0",
            request_id="test-id",
            generated_at="2026-05-11T12:00:00+00:00",
            freshness_window="5s",
            data=[{"id": "test"}],
        )
        d = envelope.model_dump()
        assert d["schema_version"] == "0.2.0"
        assert d["freshness_window"] == "5s"
        assert d["data"] == [{"id": "test"}]

    def test_api_rows_envelope_fields(self) -> None:
        client = _control_surface_client()
        resp = client.get("/api/control-surface/rows")
        body = resp.json()
        assert "schema_version" in body
        assert "request_id" in body
        assert "generated_at" in body
        assert "source_errors" in body
        assert "data" in body

    def test_api_rows_contain_display_hints(self) -> None:
        client = _control_surface_client()
        resp = client.get("/api/control-surface/rows")
        rows = resp.json()["data"]
        for row in rows:
            assert "display_hints" in row
            hints = row["display_hints"]
            assert "tone" in hints
            assert "severity_rank" in hints
            assert "icon_key" in hints
            assert "group" in hints
            assert "available_actions" in hints
