"""Production composition tests for the control-plane P0/P1 wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dharma_swarm.a2a import node_gateway


def test_node_gateway_health_never_claims_online_before_initialization(monkeypatch) -> None:
    monkeypatch.setattr(node_gateway, "_server", None)
    monkeypatch.setattr(node_gateway, "_registry", None)
    monkeypatch.setattr(node_gateway, "_node_card", None)
    monkeypatch.setattr(node_gateway, "_node_id", "unknown")
    monkeypatch.setattr(node_gateway, "_started_at", "")

    app = FastAPI()
    app.include_router(node_gateway.router)

    response = TestClient(app).get("/a2a/health")

    assert response.status_code == 503
    assert response.json()["status"] == "uninitialized"
    assert response.json()["initialized"] is False


def test_node_gateway_health_reports_degraded_initialization_failure(monkeypatch) -> None:
    monkeypatch.setattr(node_gateway, "_server", None)
    monkeypatch.setattr(node_gateway, "_registry", None)
    monkeypatch.setattr(node_gateway, "_node_card", None)
    monkeypatch.setattr(node_gateway, "_initialization_error", "")
    node_gateway.mark_gateway_degraded("RuntimeError")

    app = FastAPI()
    app.include_router(node_gateway.router)
    response = TestClient(app).get("/a2a/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["initialization_error"] == "RuntimeError"


def test_node_gateway_failed_reinitialization_cannot_leave_partial_state_online(monkeypatch) -> None:
    monkeypatch.setattr(node_gateway, "_server", object())
    monkeypatch.setattr(node_gateway, "_registry", object())
    monkeypatch.setattr(node_gateway, "_node_card", object())
    monkeypatch.setattr(
        node_gateway,
        "_load_allowed_keys",
        lambda: (_ for _ in ()).throw(RuntimeError("secret path unavailable")),
    )

    with pytest.raises(RuntimeError, match="secret path unavailable"):
        node_gateway.init_gateway(
            server=object(),
            registry=object(),
            node_card=object(),
            node_id="partial-node",
        )

    payload = node_gateway._health_payload()
    assert payload["initialized"] is False
    assert payload["status"] == "degraded"
    assert payload["initialization_error"] == "RuntimeError"


def test_api_composition_root_initializes_node_gateway(monkeypatch) -> None:
    import api.main as api_main
    import dharma_swarm.a2a.a2a_server as server_module
    import dharma_swarm.a2a.agent_card as card_module

    class FakeServer:
        pass

    class FakeRegistry:
        def register(self, card) -> None:
            self.registered = card

    captured = {}
    monkeypatch.setattr(api_main, "_state", {})
    monkeypatch.setattr(server_module, "A2AServer", FakeServer)
    monkeypatch.setattr(card_module, "CardRegistry", FakeRegistry)
    monkeypatch.setattr(
        node_gateway,
        "init_gateway",
        lambda **kwargs: captured.update(kwargs),
    )

    api_main._initialize_node_gateway()

    assert isinstance(api_main._state["a2a_server"], FakeServer)
    assert isinstance(api_main._state["card_registry"], FakeRegistry)
    assert captured["server"] is api_main._state["a2a_server"]
    assert captured["registry"] is api_main._state["card_registry"]
    assert captured["node_card"].agent_uid == "dharma-hub"
    assert captured["node_id"] == "dharma-hub"


def test_api_composition_builds_one_app_scoped_boardstore_shadow(tmp_path, monkeypatch) -> None:
    import api.main as api_main
    from dharma_swarm.task_board import TaskBoard

    task_board = TaskBoard(tmp_path / "tasks.db")
    swarm = SimpleNamespace(_task_board=task_board)
    monkeypatch.setattr(api_main, "_state", {})
    monkeypatch.setenv("DHARMA_HOME", str(tmp_path / "home"))

    api_main._initialize_boardstore_shadow(swarm)

    outbox = api_main.get_boardstore_outbox()
    assert outbox is not None
    assert outbox.adapter.task_board is task_board
    assert outbox.facade.event_log is outbox.adapter.event_log
    assert api_main._state["boardstore_facade"] is outbox.facade


def test_api_composition_builds_app_scoped_agent_directory(tmp_path, monkeypatch) -> None:
    import api.main as api_main
    from api.routers import fleet
    from dharma_swarm.a2a.agent_card import CardRegistry
    from dharma_swarm.a2a.node_registry import NodeRegistry

    cards = CardRegistry(cards_dir=tmp_path / "cards")
    nodes = NodeRegistry(nodes_path=tmp_path / "nodes.json")
    telemetry = object()
    swarm = SimpleNamespace(_telemetry=telemetry)
    monkeypatch.setattr(api_main, "_state", {"card_registry": cards})
    monkeypatch.setattr(fleet, "_get_registry", lambda: nodes)
    monkeypatch.setenv("DHARMA_HOME", str(tmp_path / "home"))

    api_main._initialize_agent_directory(swarm)

    directory = api_main.get_agent_directory()
    assert directory.card_registry is cards
    assert directory.node_registry is nodes
    assert directory.telemetry_store is telemetry


@pytest.mark.asyncio
async def test_command_create_preserves_canonical_id_and_shadows_to_boardstore(monkeypatch) -> None:
    from api.models import CreateTaskRequest
    from api.routers import commands
    from dharma_swarm.models import TaskPriority, TaskStatus

    task = SimpleNamespace(
        id="canonical-task-id",
        title="Ship it",
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
    )
    swarm = SimpleNamespace(create_task=AsyncMock(return_value=task))
    outbox = SimpleNamespace(publish=AsyncMock(return_value=True))
    monkeypatch.setattr(commands, "_get_swarm", lambda: swarm)
    monkeypatch.setattr(commands, "_get_boardstore_outbox", lambda: outbox)

    response = await commands.create_task(
        CreateTaskRequest(title="Ship it", priority="high")
    )

    assert response.data["id"] == "canonical-task-id"
    outbox.publish.assert_awaited_once_with("canonical-task-id", operation="create")


@pytest.mark.asyncio
async def test_command_create_remains_successful_when_shadow_projection_raises(monkeypatch) -> None:
    from api.models import CreateTaskRequest
    from api.routers import commands
    from dharma_swarm.models import TaskPriority, TaskStatus

    task = SimpleNamespace(
        id="canonical-task-id",
        title="Canonical wins",
        status=TaskStatus.PENDING,
        priority=TaskPriority.NORMAL,
    )
    swarm = SimpleNamespace(create_task=AsyncMock(return_value=task))
    outbox = SimpleNamespace(publish=AsyncMock(side_effect=OSError("shadow unavailable")))
    monkeypatch.setattr(commands, "_get_swarm", lambda: swarm)
    monkeypatch.setattr(commands, "_get_boardstore_outbox", lambda: outbox)

    response = await commands.create_task(CreateTaskRequest(title="Canonical wins"))

    assert response.status == "ok"
    assert response.data["id"] == "canonical-task-id"


@pytest.mark.asyncio
async def test_boardstore_shadow_outbox_projects_existing_task_with_stable_id(tmp_path) -> None:
    from dharma_swarm.board.adapters.taskboard_adapter import TaskBoardAdapter
    from dharma_swarm.board.event_log import BoardEventLog
    from dharma_swarm.board.facade import BoardStoreFacade
    from dharma_swarm.board.task_command_outbox import TaskCommandOutbox
    from dharma_swarm.task_board import TaskBoard

    board = TaskBoard(tmp_path / "tasks.db")
    await board.init_db()
    task = await board.create("Canonical task")
    event_log = BoardEventLog(path=tmp_path / "board-events.db")
    facade = BoardStoreFacade(event_log=event_log)
    outbox = TaskCommandOutbox(
        facade=facade,
        adapter=TaskBoardAdapter(board, event_log),
    )

    assert await outbox.publish(task.id, operation="create") is True
    assert facade.get_card(f"tb_{task.id}").title == "Canonical task"
    event = event_log.read_all()[-1]
    assert event.kind == "card_created"
    assert event.detail["operation"] == "create"


@pytest.mark.asyncio
async def test_boardstore_command_boundary_transitions_and_cancels_canonical_task(tmp_path) -> None:
    from dharma_swarm.board.adapters.taskboard_adapter import TaskBoardAdapter
    from dharma_swarm.board.event_log import BoardEventLog
    from dharma_swarm.board.facade import BoardStoreFacade
    from dharma_swarm.board.task_command_outbox import TaskCommandOutbox
    from dharma_swarm.models import TaskStatus
    from dharma_swarm.task_board import TaskBoard

    board = TaskBoard(tmp_path / "tasks.db")
    await board.init_db()
    task = await board.create("Lifecycle")
    event_log = BoardEventLog(path=tmp_path / "board-events.db")
    facade = BoardStoreFacade(event_log=event_log)
    outbox = TaskCommandOutbox(
        facade=facade,
        adapter=TaskBoardAdapter(board, event_log),
    )
    await outbox.publish(task.id, operation="create")

    assigned = await outbox.transition(
        task.id,
        TaskStatus.ASSIGNED,
        agent_id="agent-uid",
    )
    cancelled = await outbox.cancel(task.id)

    assert assigned.id == f"tb_{task.id}"
    assert cancelled.id == f"tb_{task.id}"
    assert facade.get_card(cancelled.id).status == "cancelled"
    assert (await board.get(task.id)).status is TaskStatus.CANCELLED
    operations = [event.detail.get("operation") for event in event_log.read_all()]
    assert operations == ["create", "transition", "cancel"]


@pytest.mark.asyncio
async def test_boardstore_transition_preserves_canonical_success_when_shadow_fails(
    tmp_path,
    monkeypatch,
) -> None:
    from dharma_swarm.board.adapters.taskboard_adapter import TaskBoardAdapter
    from dharma_swarm.board.event_log import BoardEventLog
    from dharma_swarm.board.facade import BoardStoreFacade
    from dharma_swarm.board.task_command_outbox import TaskCommandOutbox
    from dharma_swarm.models import TaskStatus
    from dharma_swarm.task_board import TaskBoard

    board = TaskBoard(tmp_path / "tasks.db")
    await board.init_db()
    task = await board.create("Canonical transition")
    event_log = BoardEventLog(path=tmp_path / "board-events.db")
    facade = BoardStoreFacade(event_log=event_log)
    outbox = TaskCommandOutbox(facade=facade, adapter=TaskBoardAdapter(board, event_log))
    monkeypatch.setattr(
        facade,
        "project_card",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("shadow unavailable")),
    )

    card = await outbox.transition(task.id, TaskStatus.ASSIGNED, agent_id="stable-agent")

    assert card.status == "claimed"
    assert (await board.get(task.id)).status is TaskStatus.ASSIGNED
    assert outbox.last_error_type == "OSError"
