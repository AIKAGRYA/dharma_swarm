"""Tests for fleet control plane: node_gateway, node_registry, remote dispatch.

Covers:
    - NodeRegistry CRUD, persistence, discovery, heartbeat degradation
    - NodeGateway endpoint routing (agent card, submit, status, cancel, health)
    - A2AClient remote dispatch (sync + async)
    - Fleet API router (list, register, dispatch)
    - Security: API key validation on gateway endpoints
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dharma_swarm.a2a.agent_card import AgentCapability, AgentCard, CardRegistry
from dharma_swarm.a2a.a2a_server import A2AServer
from dharma_swarm.a2a.a2a_client import A2AClient, _is_remote
from dharma_swarm.a2a.node_registry import (
    NodeRegistry,
    RemoteNode,
    _mark_stale,
    _HEARTBEAT_STALE_SECONDS,
    _HEARTBEAT_OFFLINE_SECONDS,
)
from dharma_swarm.a2a import node_gateway


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def nodes_path(tmp_path: Path) -> Path:
    return tmp_path / "nodes.json"


@pytest.fixture
def node_registry(nodes_path: Path) -> NodeRegistry:
    return NodeRegistry(nodes_path=nodes_path)


@pytest.fixture
def sample_node() -> RemoteNode:
    return RemoteNode(
        node_id="agni",
        endpoint="http://157.245.193.15:8420",
        ssh_alias="agni",
        status="online",
        capabilities=["code_review", "testing"],
        api_key="test-key-123",
    )


@pytest.fixture
def cards_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cards"
    d.mkdir()
    return d


@pytest.fixture
def card_registry(cards_dir: Path) -> CardRegistry:
    return CardRegistry(cards_dir=cards_dir)


@pytest.fixture
def a2a_server() -> A2AServer:
    return A2AServer()


@pytest.fixture
def gateway_app(a2a_server: A2AServer, card_registry: CardRegistry) -> FastAPI:
    """Create a test FastAPI app with the gateway router."""
    test_card = AgentCard(
        name="test-node",
        description="Test node for unit tests",
        capabilities=[AgentCapability("code_review", "Reviews code")],
        endpoint="local://",
        role="coder",
    )

    app = FastAPI()
    app.include_router(node_gateway.router)

    node_gateway.init_gateway(
        server=a2a_server,
        registry=card_registry,
        node_card=test_card,
        node_id="test-node",
    )

    # Set up allowed keys for auth testing
    node_gateway._allowed_keys = {"valid-key-abc"}

    return app


@pytest.fixture
def gateway_client(gateway_app: FastAPI) -> TestClient:
    return TestClient(gateway_app)


# ===========================================================================
# NodeRegistry Tests
# ===========================================================================


class TestNodeRegistry:
    """Test NodeRegistry CRUD, persistence, and discovery."""

    def test_register_and_retrieve(
        self, node_registry: NodeRegistry, sample_node: RemoteNode
    ) -> None:
        node_registry.register(sample_node)
        retrieved = node_registry.get("agni")
        assert retrieved is not None
        assert retrieved.node_id == "agni"
        assert retrieved.endpoint == "http://157.245.193.15:8420"

    def test_persistence(
        self, nodes_path: Path, sample_node: RemoteNode
    ) -> None:
        reg1 = NodeRegistry(nodes_path=nodes_path)
        reg1.register(sample_node)
        assert nodes_path.exists()

        reg2 = NodeRegistry(nodes_path=nodes_path)
        loaded = reg2.get("agni")
        assert loaded is not None
        assert loaded.node_id == "agni"
        assert loaded.ssh_alias == "agni"

    def test_persistence_omits_plaintext_api_key(
        self, nodes_path: Path, sample_node: RemoteNode
    ) -> None:
        reg = NodeRegistry(nodes_path=nodes_path)
        reg.register(sample_node)

        raw = nodes_path.read_text(encoding="utf-8")
        data = json.loads(raw)

        assert sample_node.api_key not in raw
        assert "api_key" not in data[0]
        assert data[0]["api_key_env"] == "DHARMA_NODE_KEY_AGNI"

    def test_persistence_sanitizes_env_ref_and_metadata_secrets(
        self, nodes_path: Path
    ) -> None:
        reg = NodeRegistry(nodes_path=nodes_path)
        reg.register(RemoteNode(
            node_id="agni.prod-1",
            api_key="plain-runtime-secret",
            metadata={
                "label": "prod",
                "headers": {"Authorization": "Bearer secret-token"},
                "nested": [{"api_key": "nested-secret"}],
            },
        ))

        raw = nodes_path.read_text(encoding="utf-8")
        data = json.loads(raw)

        assert "plain-runtime-secret" not in raw
        assert "secret-token" not in raw
        assert "nested-secret" not in raw
        assert data[0]["api_key_env"] == "DHARMA_NODE_KEY_AGNI_PROD_1"
        assert data[0]["metadata"]["headers"]["Authorization"] == "<redacted>"
        assert data[0]["metadata"]["nested"][0]["api_key"] == "<redacted>"

    def test_load_resolves_safe_env_reference(
        self, nodes_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DHARMA_NODE_KEY_AGNI", "env-secret")
        nodes_path.write_text(
            json.dumps([
                {
                    "node_id": "agni",
                    "endpoint": "http://example.test",
                    "api_key_env": "DHARMA_NODE_KEY_AGNI",
                }
            ]),
            encoding="utf-8",
        )

        reg = NodeRegistry(nodes_path=nodes_path)
        loaded = reg.get("agni")

        assert loaded is not None
        assert loaded.api_key == ""
        assert loaded.resolved_api_key() == "env-secret"

    def test_load_legacy_plaintext_key_scrubs_next_persist(
        self, nodes_path: Path
    ) -> None:
        nodes_path.write_text(
            json.dumps([
                {
                    "node_id": "agni",
                    "endpoint": "http://example.test",
                    "api_key": "legacy-secret",
                }
            ]),
            encoding="utf-8",
        )

        reg = NodeRegistry(nodes_path=nodes_path)
        loaded = reg.get("agni")
        assert loaded is not None
        assert loaded.api_key == "legacy-secret"
        assert loaded.resolved_api_key() == "legacy-secret"

        reg.register(loaded)
        raw = nodes_path.read_text(encoding="utf-8")
        data = json.loads(raw)

        assert "legacy-secret" not in raw
        assert "api_key" not in data[0]
        assert data[0]["api_key_env"] == "DHARMA_NODE_KEY_AGNI"

    def test_unregister(
        self, node_registry: NodeRegistry, sample_node: RemoteNode
    ) -> None:
        node_registry.register(sample_node)
        assert node_registry.unregister("agni")
        assert node_registry.get("agni") is None
        assert not node_registry.unregister("agni")

    def test_list_all(self, node_registry: NodeRegistry) -> None:
        node_registry.register(RemoteNode(node_id="a", status="online"))
        node_registry.register(RemoteNode(node_id="b", status="offline"))
        node_registry.register(RemoteNode(node_id="c", status="degraded"))
        assert len(node_registry.list_all()) == 3
        assert len(node_registry.list_online()) == 2  # a + c

    def test_discover_by_capability(
        self, node_registry: NodeRegistry
    ) -> None:
        node_registry.register(RemoteNode(
            node_id="agni", status="online",
            capabilities=["code_review", "testing"],
        ))
        node_registry.register(RemoteNode(
            node_id="rushabdev", status="online",
            capabilities=["research", "synthesis"],
        ))
        code_nodes = node_registry.discover("code_review")
        assert len(code_nodes) == 1
        assert code_nodes[0].node_id == "agni"

    def test_empty_registry(self, node_registry: NodeRegistry) -> None:
        assert node_registry.count() == 0
        assert node_registry.list_all() == []
        assert node_registry.discover("anything") == []

    def test_to_dict_excludes_api_key(self, sample_node: RemoteNode) -> None:
        d = sample_node.to_dict()
        assert "api_key" not in d
        assert d["node_id"] == "agni"


class TestHeartbeatDegradation:
    """Test heartbeat-based status degradation."""

    def test_stale_heartbeat_degrades(self) -> None:
        now = datetime.now(timezone.utc)
        node = RemoteNode(
            node_id="test",
            status="online",
            last_heartbeat=(now - timedelta(seconds=_HEARTBEAT_STALE_SECONDS + 10)).isoformat(),
        )
        _mark_stale(node, now=now)
        assert node.status == "degraded"

    def test_very_stale_heartbeat_goes_offline(self) -> None:
        now = datetime.now(timezone.utc)
        node = RemoteNode(
            node_id="test",
            status="online",
            last_heartbeat=(now - timedelta(seconds=_HEARTBEAT_OFFLINE_SECONDS + 10)).isoformat(),
        )
        _mark_stale(node, now=now)
        assert node.status == "offline"

    def test_fresh_heartbeat_stays_online(self) -> None:
        now = datetime.now(timezone.utc)
        node = RemoteNode(
            node_id="test",
            status="online",
            last_heartbeat=(now - timedelta(seconds=30)).isoformat(),
        )
        _mark_stale(node, now=now)
        assert node.status == "online"

    def test_no_heartbeat_stays_unknown(self) -> None:
        node = RemoteNode(node_id="test", status="unknown")
        _mark_stale(node)
        assert node.status == "unknown"

    def test_degrade_stale_nodes(self, node_registry: NodeRegistry) -> None:
        now = datetime.now(timezone.utc)
        stale_time = (now - timedelta(seconds=_HEARTBEAT_STALE_SECONDS + 10)).isoformat()
        node_registry.register(RemoteNode(
            node_id="stale", status="online", last_heartbeat=stale_time,
        ))
        node_registry.register(RemoteNode(
            node_id="fresh", status="online",
            last_heartbeat=now.isoformat(),
        ))
        changed = node_registry.degrade_stale_nodes()
        assert "stale" in changed
        assert "fresh" not in changed


# ===========================================================================
# NodeGateway Tests
# ===========================================================================


class TestNodeGateway:
    """Test node gateway HTTP endpoints."""

    def test_agent_card_endpoint(self, gateway_client: TestClient) -> None:
        resp = gateway_client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-node"
        assert len(data["capabilities"]) == 1

    def test_health_endpoint(self, gateway_client: TestClient) -> None:
        resp = gateway_client.get("/a2a/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["node_id"] == "test-node"
        assert data["status"] == "online"
        assert "capabilities" in data

    def _auth_headers(self) -> dict[str, str]:
        return {"X-A2A-Key": "valid-key-abc"}

    def test_submit_task(self, gateway_client: TestClient) -> None:
        resp = gateway_client.post("/a2a/tasks", json={
            "from_agent": "hub",
            "capability": "code_review",
            "messages": [{"role": "user", "content": "Review this"}],
        }, headers=self._auth_headers())
        assert resp.status_code in (201, 422)
        data = resp.json()
        assert "id" in data
        assert "status" in data

    def test_get_task_not_found(self, gateway_client: TestClient) -> None:
        resp = gateway_client.get("/a2a/tasks/nonexistent", headers=self._auth_headers())
        assert resp.status_code == 404

    def test_cancel_nonexistent_task(self, gateway_client: TestClient) -> None:
        resp = gateway_client.post("/a2a/tasks/nonexistent/cancel", headers=self._auth_headers())
        assert resp.status_code == 409

    def test_capabilities_endpoint(self, gateway_client: TestClient) -> None:
        resp = gateway_client.get("/a2a/capabilities", headers=self._auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["node_id"] == "test-node"

    def test_submit_and_retrieve_task(
        self, gateway_client: TestClient, a2a_server: A2AServer,
    ) -> None:
        a2a_server.set_default_handler(lambda t: t)

        resp = gateway_client.post("/a2a/tasks", json={
            "from_agent": "hub",
            "message": "Simple task",
        }, headers=self._auth_headers())
        assert resp.status_code == 201
        task_id = resp.json()["id"]

        resp2 = gateway_client.get(
            f"/a2a/tasks/{task_id}", headers=self._auth_headers(),
        )
        assert resp2.status_code == 200
        assert resp2.json()["id"] == task_id

    def test_auth_rejected_without_key(self, gateway_client: TestClient) -> None:
        resp = gateway_client.post("/a2a/tasks", json={"message": "no auth"})
        assert resp.status_code == 401


# ===========================================================================
# A2AClient Remote Dispatch Tests
# ===========================================================================


class TestClientRemoteDispatch:
    """Test A2AClient routing between local and remote agents."""

    def test_is_remote_http(self) -> None:
        card = AgentCard(name="remote", endpoint="http://example.com:8420")
        assert _is_remote(card)

    def test_is_remote_https(self) -> None:
        card = AgentCard(name="remote", endpoint="https://example.com:8420")
        assert _is_remote(card)

    def test_is_not_remote_local(self) -> None:
        card = AgentCard(name="local", endpoint="local://")
        assert not _is_remote(card)

    def test_local_delegation_unchanged(
        self, card_registry: CardRegistry, a2a_server: A2AServer,
    ) -> None:
        a2a_server.set_default_handler(lambda t: t)
        card = AgentCard(
            name="local-agent",
            capabilities=[AgentCapability("testing", "test")],
            endpoint="local://",
        )
        card_registry.register(card)

        client = A2AClient(registry=card_registry, server=a2a_server)
        result = client.delegate_to("local-agent", "Run tests")
        assert result.success
        assert result.agent_name == "local-agent"

    def test_remote_delegation_sync(
        self, card_registry: CardRegistry, a2a_server: A2AServer,
    ) -> None:
        card = AgentCard(
            name="remote-agent",
            capabilities=[AgentCapability("code_review", "reviews")],
            endpoint="http://fake-node:8420",
            metadata={"api_key": "key123"},
        )
        card_registry.register(card)

        client = A2AClient(registry=card_registry, server=a2a_server)

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "task-123",
            "status": "completed",
            "result": "LGTM",
        }
        mock_response.raise_for_status = MagicMock()

        with patch(
            "dharma_swarm.a2a.a2a_client.httpx.post",
            return_value=mock_response,
        ) as mock_post:
            result = client.delegate_to("remote-agent", "Review this code")

        assert result.success
        assert result.agent_name == "remote-agent"
        assert result.result_text == "LGTM"
        mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_remote_delegation_async(
        self, card_registry: CardRegistry, a2a_server: A2AServer,
    ) -> None:
        card = AgentCard(
            name="async-agent",
            capabilities=[AgentCapability("research", "researches")],
            endpoint="https://remote-node:8420",
        )
        card_registry.register(card)

        client = A2AClient(registry=card_registry, server=a2a_server)

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "task-456",
            "status": "working",
        }
        mock_response.raise_for_status = MagicMock()

        class FakeAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, *args, **kwargs):
                return mock_response

        with patch(
            "dharma_swarm.a2a.a2a_client.httpx.AsyncClient",
            return_value=FakeAsyncClient(),
        ):
            result = await client.delegate_to_async("async-agent", "Research this")

        assert result.success
        assert result.agent_name == "async-agent"

    def test_remote_dispatch_failure(
        self, card_registry: CardRegistry, a2a_server: A2AServer,
    ) -> None:
        card = AgentCard(
            name="failing-agent",
            endpoint="http://unreachable:8420",
        )
        card_registry.register(card)

        client = A2AClient(registry=card_registry, server=a2a_server)

        with patch("httpx.post", side_effect=ConnectionError("refused")):
            result = client.delegate_to("failing-agent", "Will fail")

        assert not result.success
        assert "Remote dispatch failed" in result.error

    def test_delegate_auto_routes_remote(
        self, card_registry: CardRegistry, a2a_server: A2AServer,
    ) -> None:
        card = AgentCard(
            name="remote-coder",
            capabilities=[AgentCapability("coding", "writes code")],
            endpoint="http://remote:8420",
            status="idle",
        )
        card_registry.register(card)

        client = A2AClient(registry=card_registry, server=a2a_server)

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"status": "completed", "result": "done"}
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "dharma_swarm.a2a.a2a_client.httpx.post",
            return_value=mock_resp,
        ):
            result = client.delegate("coding", "Write a function")

        assert result.success


# ===========================================================================
# Fleet API Router Tests
# ===========================================================================


class TestFleetRouter:
    """Test fleet management API endpoints."""

    @pytest.fixture(autouse=True)
    def _setup_fleet_router(self, nodes_path: Path) -> None:
        from api.routers import fleet
        fleet._registry = NodeRegistry(nodes_path=nodes_path)

    def _app(self) -> FastAPI:
        from api.routers.fleet import router
        app = FastAPI()
        app.include_router(router)
        return app

    def test_list_nodes_empty(self) -> None:
        client = TestClient(self._app())
        resp = client.get("/api/fleet/nodes")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_register_and_list(self) -> None:
        client = TestClient(self._app())
        resp = client.post("/api/fleet/nodes", json={
            "node_id": "agni",
            "endpoint": "http://157.245.193.15:8420",
        })
        assert resp.status_code == 201

        resp2 = client.get("/api/fleet/nodes")
        assert resp2.json()["count"] == 1

    def test_get_specific_node(self) -> None:
        client = TestClient(self._app())
        client.post("/api/fleet/nodes", json={"node_id": "agni"})
        resp = client.get("/api/fleet/nodes/agni")
        assert resp.status_code == 200
        assert resp.json()["node_id"] == "agni"

    def test_get_nonexistent_node(self) -> None:
        client = TestClient(self._app())
        resp = client.get("/api/fleet/nodes/missing")
        assert resp.status_code == 404

    def test_delete_node(self) -> None:
        client = TestClient(self._app())
        client.post("/api/fleet/nodes", json={"node_id": "agni"})
        resp = client.delete("/api/fleet/nodes/agni")
        assert resp.status_code == 200
        assert resp.json()["removed"] == "agni"

    def test_capabilities_endpoint(self) -> None:
        from api.routers import fleet
        fleet._registry.register(RemoteNode(
            node_id="agni", status="online",
            capabilities=["coding", "testing"],
        ))
        client = TestClient(self._app())
        resp = client.get("/api/fleet/capabilities")
        assert resp.status_code == 200
        caps = resp.json()["capabilities"]
        assert "coding" in caps
