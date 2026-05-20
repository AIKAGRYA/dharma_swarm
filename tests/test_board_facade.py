"""Tests for the BoardStore facade — Card schema, event log, and facade lifecycle."""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from dharma_swarm.board.models import (
    Card,
    CardId,
    ClaimLease,
    AcceptanceCriterion,
    LeaseId,
    AgentId,
    IsoDatetime,
    Version,
)
from dharma_swarm.board.event_log import BoardEvent, BoardEventLog
from dharma_swarm.board.facade import (
    BoardStoreFacade,
    VersionConflictError,
)
from dharma_swarm.correlation_context import correlation_scope_sync


class TestCardSchema:
    """Card schema matches SWARM_BOARDSTORE_SPEC.md §3."""

    def test_card_has_all_required_fields(self) -> None:
        card = Card(
            id=CardId("card_001"),
            title="Test card",
            body="A test body",
            status="inbox",
            arjuna_weight=0.8,
            source_surface="cli",
        )
        assert card.id == "card_001"
        assert card.status == "inbox"
        assert card.arjuna_weight == 0.8
        assert card.version == 1

    def test_card_defaults(self) -> None:
        card = Card(
            id=CardId("card_002"),
            title="Defaults",
            body="",
            status="claimable",
        )
        assert card.claim_lease is None
        assert card.assignee_kind == "unknown"
        assert card.capability_required == []
        assert card.cost_ceiling_usd == Decimal("0.00")
        assert card.render_hints.view_priority == 0

    def test_card_with_lease(self) -> None:
        lease = ClaimLease(
            lease_id=LeaseId("lease_001"),
            card_id=CardId("card_003"),
            agent_id=AgentId("devin-abc"),
            agent_kind="devin",
            claimed_at=IsoDatetime("2026-05-20T10:00:00+00:00"),
            expires_at=IsoDatetime("2026-05-20T10:30:00+00:00"),
        )
        card = Card(
            id=CardId("card_003"),
            title="Claimed card",
            body="",
            status="claimed",
            claim_lease=lease,
            assignee_kind="devin",
        )
        assert card.claim_lease is not None
        assert card.claim_lease.agent_kind == "devin"

    def test_acceptance_criteria(self) -> None:
        criterion = AcceptanceCriterion(
            id="test_passes",
            text="All tests pass",
            kind="test",
            verifier="pytest",
        )
        card = Card(
            id=CardId("card_004"),
            title="With criteria",
            body="",
            status="planned",
            acceptance_criteria=[criterion],
        )
        assert len(card.acceptance_criteria) == 1
        assert card.acceptance_criteria[0].kind == "test"


class TestBoardEventLog:
    """Event log is append-only and persists as JSONL."""

    def test_append_and_read(self, tmp_path: Path) -> None:
        log = BoardEventLog(path=tmp_path / "events.jsonl")
        event = BoardEvent(kind="card_created", card_id=CardId("card_001"))
        log.append(event)

        events = log.read_all()
        assert len(events) == 1
        assert events[0].kind == "card_created"
        assert events[0].card_id == "card_001"

    def test_event_log_uses_sqlite_schema(self, tmp_path: Path) -> None:
        db_path = tmp_path / "events.sqlite3"
        log = BoardEventLog(path=db_path)
        log.append(BoardEvent(kind="card_created", card_id=CardId("card_sqlite")))

        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT kind, card_id FROM board_events ORDER BY sequence"
            ).fetchall()

        assert rows == [("card_created", "card_sqlite")]

    def test_append_multiple(self, tmp_path: Path) -> None:
        log = BoardEventLog(path=tmp_path / "events.jsonl")
        log.append(BoardEvent(kind="card_created", card_id=CardId("c1")))
        log.append(BoardEvent(kind="card_transitioned", card_id=CardId("c1")))
        log.append(BoardEvent(kind="card_claimed", card_id=CardId("c1")))

        assert log.count() == 3
        assert log.tail(2)[-1].kind == "card_claimed"

    def test_read_for_card(self, tmp_path: Path) -> None:
        log = BoardEventLog(path=tmp_path / "events.jsonl")
        log.append(BoardEvent(kind="card_created", card_id=CardId("c1")))
        log.append(BoardEvent(kind="card_created", card_id=CardId("c2")))
        log.append(BoardEvent(kind="card_transitioned", card_id=CardId("c1")))

        c1_events = log.read_for_card(CardId("c1"))
        assert len(c1_events) == 2

    def test_read_for_trace(self, tmp_path: Path) -> None:
        log = BoardEventLog(path=tmp_path / "events.sqlite3")
        log.append(BoardEvent(
            kind="card_created",
            card_id=CardId("c1"),
            trace_id="trc-board",
            trace_id_source="operator_supplied",
        ))
        log.append(BoardEvent(kind="card_created", card_id=CardId("c2")))

        trace_events = log.read_for_trace("trc-board")

        assert len(trace_events) == 1
        assert trace_events[0].card_id == "c1"
        assert trace_events[0].trace_id_source == "operator_supplied"

    def test_empty_log(self, tmp_path: Path) -> None:
        log = BoardEventLog(path=tmp_path / "events.jsonl")
        assert log.read_all() == []
        assert log.count() == 0


class TestBoardStoreFacade:
    """Facade lifecycle: create, transition, version conflict."""

    def test_create_card(self, tmp_path: Path) -> None:
        facade = BoardStoreFacade(event_log=BoardEventLog(path=tmp_path / "e.jsonl"))
        card = facade.create_card(
            title="Implement drift triage",
            body="Rank DEGRADED zones by priority",
            source_surface="cli",
            arjuna_weight=0.9,
        )
        assert card.status == "inbox"
        assert card.version == 1
        assert len(card.audit_log) == 1
        assert card.audit_log[0].action == "card_created"

    def test_transition(self, tmp_path: Path) -> None:
        facade = BoardStoreFacade(event_log=BoardEventLog(path=tmp_path / "e.jsonl"))
        card = facade.create_card(
            title="Test transition",
            body="",
            source_surface="noticer",
            arjuna_weight=0.5,
        )
        updated = facade.transition(
            card_id=card.id,
            to_status="triaged",
            expected_version=Version(1),
            reason="Auto-triaged by noticer",
        )
        assert updated.status == "triaged"
        assert updated.version == 2
        assert len(updated.audit_log) == 2

    def test_version_conflict(self, tmp_path: Path) -> None:
        facade = BoardStoreFacade(event_log=BoardEventLog(path=tmp_path / "e.jsonl"))
        card = facade.create_card(
            title="Conflict test",
            body="",
            source_surface="cli",
            arjuna_weight=0.3,
        )
        # First transition succeeds
        facade.transition(card.id, "triaged", Version(1))
        # Second with stale version fails
        with pytest.raises(VersionConflictError):
            facade.transition(card.id, "planned", Version(1))

    def test_list_cards(self, tmp_path: Path) -> None:
        facade = BoardStoreFacade(event_log=BoardEventLog(path=tmp_path / "e.jsonl"))
        facade.create_card(title="A", body="", source_surface="cli", arjuna_weight=0.5)
        facade.create_card(title="B", body="", source_surface="noticer", arjuna_weight=0.7)

        assert facade.card_count() == 2
        cli_cards = facade.list_cards(source_surface="cli")
        assert len(cli_cards) == 1
        assert cli_cards[0].title == "A"

    def test_event_log_records_operations(self, tmp_path: Path) -> None:
        log = BoardEventLog(path=tmp_path / "e.jsonl")
        facade = BoardStoreFacade(event_log=log)
        card = facade.create_card(
            title="Evented",
            body="",
            source_surface="dashboard",
            arjuna_weight=0.6,
        )
        facade.transition(card.id, "triaged", Version(1))

        events = log.read_all()
        assert len(events) == 2
        assert events[0].kind == "card_created"
        assert events[1].kind == "card_transitioned"
        assert events[1].from_status == "inbox"
        assert events[1].to_status == "triaged"

    def test_facade_writes_trace_metadata(self, tmp_path: Path) -> None:
        log = BoardEventLog(path=tmp_path / "e.sqlite3")
        facade = BoardStoreFacade(event_log=log)
        card = facade.create_card(
            title="Trace card",
            body="",
            source_surface="dashboard",
            arjuna_weight=0.6,
            trace_id="trc-facade",
            trace_id_source="operator_supplied",
        )
        facade.transition(
            card.id,
            "triaged",
            Version(1),
            trace_id="trc-facade",
            trace_id_source="operator_supplied",
        )

        events = log.read_for_trace("trc-facade")
        assert [event.kind for event in events] == [
            "card_created",
            "card_transitioned",
        ]

    def test_facade_defaults_trace_metadata_from_correlation_context(
        self,
        tmp_path: Path,
    ) -> None:
        log = BoardEventLog(path=tmp_path / "e.sqlite3")
        facade = BoardStoreFacade(event_log=log)

        with correlation_scope_sync(trace_id="trc-context-board"):
            card = facade.create_card(
                title="Context trace card",
                body="",
                source_surface="dashboard",
                arjuna_weight=0.6,
            )

        events = log.read_for_trace("trc-context-board")
        assert len(events) == 1
        assert events[0].card_id == card.id
        assert events[0].trace_id_source == "correlation_context"
