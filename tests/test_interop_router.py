from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.interop import router
from dharma_swarm.operator_core.interop import AgentInteropStore


def _store(tmp_path: Path) -> AgentInteropStore:
    return AgentInteropStore(
        root=tmp_path / "interop",
        cards_dir=tmp_path / "cards",
        mailbox_root=tmp_path / "mailbox",
    )


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("DHARMA_INTEROP_ROOT", str(tmp_path / "interop"))
    monkeypatch.setenv("DHARMA_A2A_CARDS_DIR", str(tmp_path / "cards"))
    monkeypatch.setenv("DHARMA_ROAMING_MAILBOX_ROOT", str(tmp_path / "mailbox"))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_interop_store_projects_default_cards_and_status(tmp_path: Path) -> None:
    store = _store(tmp_path)

    status = store.build_status()

    assert status["schema_version"] == "2026-05-03.interop.v1"
    assert status["adapter_count"] >= 10
    assert any(adapter["adapter_id"] == "codex-cli" for adapter in status["adapters"])
    assert (tmp_path / "cards" / "codex-cli.json").exists()


def test_interop_store_claim_and_response_lifecycle(tmp_path: Path) -> None:
    store = _store(tmp_path)
    task = store.enqueue_task(
        recipient="codex-cli",
        sender="operator",
        summary="Ping",
        body="Return status",
    )

    claimed = store.claim_next_task(recipient="codex-cli", worker_id="codex-worker")
    assert claimed is not None
    assert claimed["task_id"] == task["task_id"]
    assert claimed["status"] == "claimed"

    response = store.respond_to_task(
        task_id=task["task_id"],
        responder="codex-worker",
        summary="Ready",
        body="ok",
    )

    assert response["status"] == "responded"
    assert store.list_tasks(limit=1)[0]["status"] == "responded"


def test_interop_store_failed_response_status(tmp_path: Path) -> None:
    store = _store(tmp_path)
    task = store.enqueue_task(
        recipient="claude-code",
        sender="operator",
        summary="Fail",
        body="Return failure",
    )
    store.claim_next_task(recipient="claude-code", worker_id="claude-worker")

    response = store.respond_to_task(
        task_id=task["task_id"],
        responder="claude-worker",
        summary="Failed",
        body="boom",
        status="failed",
    )

    assert response["status"] == "failed"
    assert store.list_tasks(limit=1)[0]["status"] == "failed"


def test_interop_router_status_enqueue_heartbeat_claim_response_events(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    status = client.get("/api/interop/status")
    assert status.status_code == 200
    assert status.json()["data"]["schema_version"] == "2026-05-03.interop.v1"

    heartbeat = client.post(
        "/api/interop/heartbeat",
        json={
            "worker_id": "codex-worker",
            "adapter_id": "codex-cli",
            "status": "idle",
        },
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["data"]["worker_id"] == "codex-worker"

    enqueued = client.post(
        "/api/interop/tasks",
        json={
            "recipient": "codex-cli",
            "sender": "operator",
            "summary": "Router task",
            "body": "Return status",
        },
    )
    assert enqueued.status_code == 200
    task_id = enqueued.json()["data"]["task_id"]

    claimed = client.post(
        "/api/interop/claim-next",
        json={"recipient": "codex-cli", "worker_id": "codex-worker"},
    )
    assert claimed.status_code == 200
    assert claimed.json()["data"]["task_id"] == task_id

    responded = client.post(
        f"/api/interop/tasks/{task_id}/response",
        json={
            "responder": "codex-worker",
            "summary": "Done",
            "body": "ok",
        },
    )
    assert responded.status_code == 200
    assert responded.json()["data"]["status"] == "responded"

    events = client.get("/api/interop/events")
    event_types = {event["event_type"] for event in events.json()["data"]}
    assert {"worker.heartbeat", "task.queued", "task.claimed", "task.responded"} <= event_types
