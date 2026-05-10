"""Tests for BR-002, BR-007, BR-008 closures.

BR-002: refill_frontier_tasks_pending + frontier queue drain
BR-007: store_sync (ontology outcomes → runtime artifacts) + path drift fix
BR-008: VentureCell ontology ↔ fractal room polymorphism
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# BR-002: refill_frontier_tasks_pending
# ---------------------------------------------------------------------------


class TestFrontierRefill:
    """Tests for the frontier refill bridge (BR-002 closure)."""

    def _write_board(self, path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    def test_refill_empty_board(self, tmp_path: Path) -> None:
        from dharma_swarm.opportunity_refill import refill_frontier_tasks_pending

        board_path = tmp_path / "board.json"
        result = refill_frontier_tasks_pending(board_path=board_path)
        assert result.board_count == 0
        assert result.appended_rows == 0

    def test_refill_promotes_top_k(self, tmp_path: Path) -> None:
        from dharma_swarm.opportunity_refill import (
            OPPORTUNITY_STAGES,
            refill_frontier_tasks_pending,
        )

        board_path = tmp_path / "board.json"
        frontier_path = tmp_path / "frontier.jsonl"
        self._write_board(board_path, [
            {"id": "opp-1", "title": "Alpha", "type": "external_revenue", "final_score": 90},
            {"id": "opp-2", "title": "Beta", "type": "external_revenue", "final_score": 80},
            {"id": "opp-3", "title": "Gamma", "type": "external_revenue", "final_score": 70},
            {"id": "opp-4", "title": "Delta", "type": "external_revenue", "final_score": 60},
        ])
        result = refill_frontier_tasks_pending(
            top_k=2, board_path=board_path, frontier_path=frontier_path,
        )
        assert result.board_count == 4
        assert result.addressed_count == 2
        assert result.appended_rows == 2 * len(OPPORTUNITY_STAGES)
        assert set(result.appended_opportunity_ids) == {"opp-1", "opp-2"}

        lines = frontier_path.read_text().strip().splitlines()
        assert len(lines) == 2 * len(OPPORTUNITY_STAGES)
        first_row = json.loads(lines[0])
        assert first_row["metadata"]["opportunity_id"] in {"opp-1", "opp-2"}

    def test_refill_skips_addressed(self, tmp_path: Path) -> None:
        from dharma_swarm.opportunity_refill import refill_frontier_tasks_pending

        board_path = tmp_path / "board.json"
        frontier_path = tmp_path / "frontier.jsonl"
        self._write_board(board_path, [
            {"id": "opp-1", "title": "Done", "final_score": 90, "addressed": True},
            {"id": "opp-2", "title": "Pending", "final_score": 80},
        ])
        result = refill_frontier_tasks_pending(
            board_path=board_path, frontier_path=frontier_path,
        )
        assert result.addressed_count == 1
        assert "opp-2" in result.appended_opportunity_ids
        assert "opp-1" not in result.appended_opportunity_ids

    def test_refill_dry_run(self, tmp_path: Path) -> None:
        from dharma_swarm.opportunity_refill import refill_frontier_tasks_pending

        board_path = tmp_path / "board.json"
        frontier_path = tmp_path / "frontier.jsonl"
        self._write_board(board_path, [
            {"id": "opp-1", "title": "Alpha", "final_score": 90},
        ])
        result = refill_frontier_tasks_pending(
            dry_run=True, board_path=board_path, frontier_path=frontier_path,
        )
        assert result.appended_rows > 0
        assert not frontier_path.exists()

    def test_refill_marks_addressed(self, tmp_path: Path) -> None:
        from dharma_swarm.opportunity_refill import refill_frontier_tasks_pending

        board_path = tmp_path / "board.json"
        frontier_path = tmp_path / "frontier.jsonl"
        self._write_board(board_path, [
            {"id": "opp-1", "title": "Alpha", "final_score": 90},
        ])
        refill_frontier_tasks_pending(
            board_path=board_path, frontier_path=frontier_path,
        )
        updated_board = json.loads(board_path.read_text())
        assert updated_board[0]["addressed"] is True

    def test_refill_respects_min_telos(self, tmp_path: Path) -> None:
        from dharma_swarm.opportunity_refill import refill_frontier_tasks_pending

        board_path = tmp_path / "board.json"
        frontier_path = tmp_path / "frontier.jsonl"
        self._write_board(board_path, [
            {"id": "opp-1", "title": "Low", "final_score": 0.3},
            {"id": "opp-2", "title": "High", "final_score": 0.8},
        ])
        result = refill_frontier_tasks_pending(
            min_telos_alignment=0.5,
            board_path=board_path,
            frontier_path=frontier_path,
        )
        assert result.addressed_count == 1
        assert "opp-2" in result.appended_opportunity_ids


# ---------------------------------------------------------------------------
# BR-007: store_sync
# ---------------------------------------------------------------------------


class TestStoreSync:
    """Tests for the ontology→runtime sync (BR-007 closure)."""

    def test_sync_no_ontology_file(self, tmp_path: Path) -> None:
        from dharma_swarm.store_sync import sync_outcomes_to_artifacts

        result = sync_outcomes_to_artifacts(
            ontology_db_path=tmp_path / "nonexistent.db",
            runtime_db_path=tmp_path / "state" / "runtime.db",
        )
        assert result.outcomes_scanned == 0
        assert result.artifacts_created == 0

    def _persist_ontology(self, ont_path: Path, registry: "OntologyRegistry") -> None:
        from dharma_swarm.ontology_hub import OntologyHub
        hub = OntologyHub(db_path=ont_path)
        hub.sync_from_registry(registry)
        hub.close()

    def test_sync_materializes_outcomes(self, tmp_path: Path) -> None:
        from dharma_swarm.ontology import OntologyRegistry
        from dharma_swarm.store_sync import sync_outcomes_to_artifacts

        ont_path = tmp_path / "ontology.db"
        registry = OntologyRegistry.create_dharma_registry()

        obj, errors = registry.create_object(
            "Outcome",
            properties={
                "proposal_id": "prop-001",
                "task_id": "task-123",
                "agent_id": "agent-test",
                "success": True,
                "result_summary": "test outcome",
            },
            created_by="test",
        )
        assert not errors
        assert obj is not None
        self._persist_ontology(ont_path, registry)

        rt_path = tmp_path / "state" / "runtime.db"
        result = sync_outcomes_to_artifacts(
            ontology_db_path=ont_path,
            runtime_db_path=rt_path,
        )
        assert result.outcomes_scanned == 1
        assert result.artifacts_created == 1

        db = sqlite3.connect(str(rt_path))
        row = db.execute(
            "SELECT artifact_kind, metadata_json FROM artifact_records WHERE artifact_id = ?",
            (f"ont-{obj.id}",),
        ).fetchone()
        db.close()
        assert row is not None
        assert row[0] == "outcome"
        meta = json.loads(row[1])
        assert meta["success"] is True

    def test_sync_idempotent(self, tmp_path: Path) -> None:
        from dharma_swarm.ontology import OntologyRegistry
        from dharma_swarm.store_sync import sync_outcomes_to_artifacts

        ont_path = tmp_path / "ontology.db"
        registry = OntologyRegistry.create_dharma_registry()
        registry.create_object(
            "Outcome",
            properties={
                "proposal_id": "prop-002",
                "task_id": "task-456",
                "agent_id": "agent-test",
                "success": True,
                "result_summary": "x",
            },
            created_by="test",
        )
        self._persist_ontology(ont_path, registry)

        rt_path = tmp_path / "state" / "runtime.db"
        r1 = sync_outcomes_to_artifacts(ontology_db_path=ont_path, runtime_db_path=rt_path)
        r2 = sync_outcomes_to_artifacts(ontology_db_path=ont_path, runtime_db_path=rt_path)
        assert r1.artifacts_created == 1
        assert r2.artifacts_created == 0
        assert r2.skipped_existing == 1


# ---------------------------------------------------------------------------
# BR-008: VentureCell ontology ↔ fractal room polymorphism
# ---------------------------------------------------------------------------


class TestVentureCellPolymorphism:
    """Tests for VentureCell ontology ↔ FractalRoom bridge (BR-008)."""

    def _registry(self) -> "OntologyRegistry":
        from dharma_swarm.ontology import OntologyRegistry
        return OntologyRegistry.create_dharma_registry()

    def test_cell_to_ontology(self) -> None:
        from dharma_swarm.fractal.fractal_room import RoomKind, RoomStatus, VentureCellV1
        from dharma_swarm.fractal.room_bridge import venture_cell_to_ontology

        registry = self._registry()
        cell = VentureCellV1(
            id="revenue-wedge",
            kind=RoomKind.VENTURE_CELL,
            purpose="Generate intelligence reports",
            status=RoomStatus.ACTIVE,
            budget_tokens=50000,
            autonomy_stage=2,
            value_proposition="Intelligence reports",
        )
        obj, errors = venture_cell_to_ontology(cell, registry)
        assert not errors, errors
        assert obj is not None
        assert obj.type_name == "VentureCell"
        assert obj.properties["name"] == "revenue-wedge"
        assert obj.properties["autonomy_stage"] == 2
        assert obj.properties["status"] == "active"

    def test_ontology_to_cell(self) -> None:
        from dharma_swarm.fractal.fractal_room import RoomKind, VentureCellV1
        from dharma_swarm.fractal.room_bridge import ontology_to_venture_cell

        registry = self._registry()
        obj, errors = registry.create_object(
            "VentureCell",
            properties={
                "name": "test-cell",
                "description": "A test cell",
                "domain": "economic",
                "autonomy_stage": 3,
                "status": "active",
                "budget_tokens": 10000,
                "kpis": {},
            },
            created_by="test",
        )
        assert not errors, errors

        cell = ontology_to_venture_cell(obj)
        assert cell is not None
        assert isinstance(cell, VentureCellV1)
        assert cell.kind == RoomKind.VENTURE_CELL
        assert cell.autonomy_stage == 3
        assert cell.budget_tokens == 10000

    def test_roundtrip(self) -> None:
        from dharma_swarm.fractal.fractal_room import RoomKind, RoomStatus, VentureCellV1
        from dharma_swarm.fractal.room_bridge import (
            ontology_to_venture_cell,
            venture_cell_to_ontology,
        )

        registry = self._registry()
        cell = VentureCellV1(
            id="rt-test",
            kind=RoomKind.VENTURE_CELL,
            purpose="roundtrip test",
            status=RoomStatus.ACTIVE,
            budget_tokens=5000,
            autonomy_stage=1,
        )
        obj, errors = venture_cell_to_ontology(cell, registry)
        assert not errors, errors
        assert obj is not None

        hydrated = ontology_to_venture_cell(obj)
        assert hydrated is not None
        assert hydrated.purpose == "roundtrip test"
        assert hydrated.budget_tokens == 5000

    def test_sync_registry_to_ontology(self) -> None:
        from dharma_swarm.fractal.fractal_room import (
            FractalRoom,
            RoomKind,
            RoomRegistry,
            RoomStatus,
            VentureCellV1,
        )
        from dharma_swarm.fractal.room_bridge import sync_registry_to_ontology

        room_reg = RoomRegistry()
        room_reg.register(FractalRoom(
            id="core-ops", status=RoomStatus.ACTIVE, purpose="Core operations",
            operator="system",
        ))
        room_reg.register(VentureCellV1(
            id="rev-wedge",
            kind=RoomKind.VENTURE_CELL,
            status=RoomStatus.ACTIVE,
            budget_tokens=50000,
            revenue_target=10000,
            purpose="Revenue generation",
            operator="system",
            customer_or_beneficiary="Substack subscribers",
            kill_conditions=["budget_depletion_90pct"],
        ))

        ont_reg = self._registry()
        errors = sync_registry_to_ontology(room_reg, ont_reg)
        assert not errors

        cells = ont_reg.get_objects_by_type("VentureCell")
        assert len(cells) == 1
        assert cells[0].properties["name"] == "rev-wedge"

    def test_update_existing_cell(self) -> None:
        from dharma_swarm.fractal.fractal_room import RoomKind, RoomStatus, VentureCellV1
        from dharma_swarm.fractal.room_bridge import venture_cell_to_ontology

        registry = self._registry()
        cell = VentureCellV1(
            id="upd-test",
            kind=RoomKind.VENTURE_CELL,
            purpose="v1",
            status=RoomStatus.ACTIVE,
            budget_tokens=1000,
            autonomy_stage=1,
        )
        obj1, err1 = venture_cell_to_ontology(cell, registry)
        assert not err1, err1
        assert obj1 is not None

        cell.purpose = "v2"
        cell.autonomy_stage = 3
        obj2, err2 = venture_cell_to_ontology(cell, registry)
        assert not err2, err2


# ---------------------------------------------------------------------------
# BR-002: opportunity_dispatcher.main
# ---------------------------------------------------------------------------


class TestOpportunityDispatcherMain:
    """Tests for the opportunity_dispatcher CLI entrypoint."""

    def test_main_no_board(self) -> None:
        from dharma_swarm.opportunity_dispatcher import main
        rc = main(["--dry-run"])
        assert rc == 0

    def test_main_with_board(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from dharma_swarm.opportunity_dispatcher import main

        board_path = tmp_path / ".dharma" / "meta" / "opportunity_board.json"
        board_path.parent.mkdir(parents=True, exist_ok=True)
        board_path.write_text(json.dumps([
            {"id": "opp-1", "title": "Test", "final_score": 90},
        ]))
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        rc = main(["--dry-run"])
        assert rc == 0
