"""Tests for A2A 1.0 spec conformance.

Covers all new spec features added in the a2a-spec-1.0-conformance branch:
- 8 task states (REJECTED, AUTH_REQUIRED)
- contextId for grouping related tasks
- Part as strict one-of (text|raw|url|data) with mediaType/filename
- Artifact distinct from Message (outputs vs conversation)
- extensions[] with required flag
- AgentSkill (with id, tags, examples, per-skill security)
- SecurityScheme (APIKey, HTTPAuth, OAuth2, MutualTLS, OpenIdConnect)
- AgentCard with signatures[], supported_interfaces[], extensions[]
- Gateway spec-standard endpoints (/tasks, /tasks/{id}:cancel, etc.)
- SSE streaming endpoint
- Cycle detection on dispatch chains
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from dharma_swarm.a2a.a2a_server import (
    A2AArtifact,
    A2AExtension,
    A2AMessage,
    A2APart,
    A2APartType,
    A2AServer,
    A2ATask,
    A2ATaskStatus,
)
from dharma_swarm.a2a.agent_card import (
    AgentCapability,
    AgentCard,
    AgentSkill,
    CardRegistry,
    SecurityScheme,
)
from dharma_swarm.a2a.a2a_client import A2AClient
from dharma_swarm.a2a.node_gateway import init_gateway, router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cards_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cards"
    d.mkdir()
    return d


@pytest.fixture
def registry(cards_dir: Path) -> CardRegistry:
    return CardRegistry(cards_dir=cards_dir)


@pytest.fixture
def server() -> A2AServer:
    return A2AServer()


@pytest.fixture
def client(registry: CardRegistry, server: A2AServer) -> A2AClient:
    return A2AClient(registry=registry, server=server, default_from="test-client")


@pytest.fixture
def gateway_app(server: A2AServer, registry: CardRegistry) -> FastAPI:
    from dharma_swarm.a2a import node_gateway
    app = FastAPI()
    card = AgentCard(
        name="test-node",
        description="Test node",
        skills=[AgentSkill(name="code_review", description="Review code")],
    )
    init_gateway(server, registry, card, node_id="test-node")
    node_gateway._allowed_keys = {"test-key"}
    app.include_router(router)
    return app


@pytest.fixture
def http_client(gateway_app: FastAPI) -> TestClient:
    return TestClient(gateway_app)


# ---------------------------------------------------------------------------
# Task state tests
# ---------------------------------------------------------------------------


class TestTaskStates:
    """A2A 1.0 mandates 8 task states."""

    def test_all_8_states_exist(self):
        states = [s.value for s in A2ATaskStatus]
        assert "submitted" in states
        assert "working" in states
        assert "input-required" in states
        assert "completed" in states
        assert "failed" in states
        assert "cancelled" in states
        assert "rejected" in states
        assert "auth-required" in states
        assert len(states) == 8

    def test_terminal_states(self):
        terminals = A2ATaskStatus.terminal_states()
        assert A2ATaskStatus.COMPLETED in terminals
        assert A2ATaskStatus.FAILED in terminals
        assert A2ATaskStatus.CANCELLED in terminals
        assert A2ATaskStatus.REJECTED in terminals
        assert A2ATaskStatus.WORKING not in terminals
        assert A2ATaskStatus.AUTH_REQUIRED not in terminals

    def test_is_terminal_method(self):
        task = A2ATask()
        task.status = A2ATaskStatus.COMPLETED
        assert task.is_terminal()
        task.status = A2ATaskStatus.REJECTED
        assert task.is_terminal()
        task.status = A2ATaskStatus.WORKING
        assert not task.is_terminal()
        task.status = A2ATaskStatus.AUTH_REQUIRED
        assert not task.is_terminal()

    def test_reject_task(self, server: A2AServer):
        def pause(t: A2ATask) -> A2ATask:
            t.status = A2ATaskStatus.INPUT_REQUIRED
            return t

        server.register_handler("test", pause)
        task = server.submit(A2ATask(capability="test", messages=[A2AMessage.text("hi")]))
        assert task.status == A2ATaskStatus.INPUT_REQUIRED
        assert server.reject(task.id, "not authorized")
        assert server.get_status(task.id) == A2ATaskStatus.REJECTED
        assert server.get_task(task.id).error == "not authorized"
        # Can't reject a terminal task
        assert not server.reject(task.id, "again")

    def test_require_auth(self, server: A2AServer):
        def pause(t: A2ATask) -> A2ATask:
            t.status = A2ATaskStatus.INPUT_REQUIRED
            return t

        server.register_handler("test", pause)
        task = server.submit(A2ATask(capability="test", messages=[A2AMessage.text("hi")]))
        assert task.status == A2ATaskStatus.INPUT_REQUIRED
        assert server.require_auth(task.id, "needs OAuth2")
        assert server.get_status(task.id) == A2ATaskStatus.AUTH_REQUIRED
        # AUTH_REQUIRED is not terminal, can still cancel
        assert server.cancel(task.id)
        assert server.get_status(task.id) == A2ATaskStatus.CANCELLED


# ---------------------------------------------------------------------------
# contextId tests
# ---------------------------------------------------------------------------


class TestContextId:
    """A2A 1.0: contextId groups related tasks."""

    def test_auto_generated_context_id(self, server: A2AServer):
        server.set_default_handler(lambda t: t)
        task = server.submit(A2ATask(messages=[A2AMessage.text("hello")]))
        assert task.context_id, "context_id should be auto-generated"
        assert len(task.context_id) == 12

    def test_explicit_context_id_preserved(self, server: A2AServer):
        server.set_default_handler(lambda t: t)
        task = server.submit(A2ATask(
            context_id="my-context-123",
            messages=[A2AMessage.text("hello")],
        ))
        assert task.context_id == "my-context-123"

    def test_filter_tasks_by_context_id(self, server: A2AServer):
        server.set_default_handler(lambda t: t)
        server.submit(A2ATask(context_id="ctx-a", messages=[A2AMessage.text("1")]))
        server.submit(A2ATask(context_id="ctx-a", messages=[A2AMessage.text("2")]))
        server.submit(A2ATask(context_id="ctx-b", messages=[A2AMessage.text("3")]))

        ctx_a_tasks = server.list_tasks(context_id="ctx-a")
        assert len(ctx_a_tasks) == 2
        ctx_b_tasks = server.list_tasks(context_id="ctx-b")
        assert len(ctx_b_tasks) == 1


# ---------------------------------------------------------------------------
# Part one-of tests
# ---------------------------------------------------------------------------


class TestPartOneOf:
    """A2A 1.0: Part is strict one-of (text|raw|url|data)."""

    def test_text_part(self):
        p = A2APart(type=A2APartType.TEXT, content="hello world")
        assert p.type == A2APartType.TEXT
        assert p.content == "hello world"

    def test_raw_part_with_media_type(self):
        p = A2APart(type=A2APartType.RAW, content="<binary>", media_type="application/octet-stream")
        assert p.type == A2APartType.RAW
        assert p.media_type == "application/octet-stream"

    def test_url_part_with_filename(self):
        p = A2APart(
            type=A2APartType.URL,
            content="https://example.com/report.pdf",
            media_type="application/pdf",
            filename="report.pdf",
        )
        assert p.type == A2APartType.URL
        assert p.filename == "report.pdf"
        assert p.media_type == "application/pdf"

    def test_data_part(self):
        p = A2APart(type=A2APartType.DATA, content='{"key": "value"}', media_type="application/json")
        assert p.type == A2APartType.DATA
        assert p.media_type == "application/json"

    def test_file_backward_compat(self):
        p = A2APart(type=A2APartType.FILE, content="/path/to/file")
        assert p.type == A2APartType.FILE
        assert p.type.value == "file"

    def test_all_part_types_exist(self):
        types = {t.value for t in A2APartType}
        assert types == {"text", "raw", "url", "data", "file"}


# ---------------------------------------------------------------------------
# Artifact tests
# ---------------------------------------------------------------------------


class TestArtifact:
    """A2A 1.0: Artifact distinct from Message."""

    def test_artifact_creation(self):
        a = A2AArtifact(
            parts=[A2APart(type=A2APartType.TEXT, content="code review result")],
            name="review-output",
            description="Code review findings",
        )
        assert a.id
        assert a.name == "review-output"
        assert len(a.parts) == 1

    def test_task_artifacts_vs_history(self):
        task = A2ATask(
            history=[A2AMessage.text("Please review")],
            artifacts=[
                A2AArtifact(parts=[A2APart(content="LGTM")], name="result"),
            ],
        )
        assert len(task.history) == 1
        assert len(task.artifacts) == 1
        assert task.history[0].parts[0].content == "Please review"
        assert task.artifacts[0].parts[0].content == "LGTM"

    def test_artifact_with_extensions(self):
        ext = A2AExtension(uri="dharma:witness-packet", required=True, data={"gate": "harm-prevention"})
        a = A2AArtifact(
            parts=[A2APart(content="verified output")],
            extensions=[ext],
        )
        assert len(a.extensions) == 1
        assert a.extensions[0].uri == "dharma:witness-packet"
        assert a.extensions[0].required is True


# ---------------------------------------------------------------------------
# Extension tests
# ---------------------------------------------------------------------------


class TestExtensions:
    """A2A 1.0: extensions[] with required flag."""

    def test_extension_on_task(self):
        ext = A2AExtension(
            uri="dharma:telos-gate",
            required=True,
            data={"gate_id": "harm-prevention", "passed": True},
        )
        task = A2ATask(
            messages=[A2AMessage.text("test")],
            extensions=[ext],
        )
        assert len(task.extensions) == 1
        assert task.extensions[0].uri == "dharma:telos-gate"
        assert task.extensions[0].required is True

    def test_multiple_extensions(self):
        exts = [
            A2AExtension(uri="dharma:telos-gate", required=True),
            A2AExtension(uri="dharma:witness-packet", required=False),
            A2AExtension(uri="dharma:gnani-lodestone", required=False, data={"fitness": 0.87}),
        ]
        task = A2ATask(extensions=exts)
        assert len(task.extensions) == 3
        required = [e for e in task.extensions if e.required]
        assert len(required) == 1


# ---------------------------------------------------------------------------
# AgentSkill tests
# ---------------------------------------------------------------------------


class TestAgentSkill:
    """A2A 1.0: AgentSkill with id, tags, examples."""

    def test_skill_creation(self):
        skill = AgentSkill(
            name="code_review",
            description="Review code for bugs",
            tags=["review", "quality"],
            examples=["Review this PR for security issues"],
        )
        assert skill.id == "code_review"  # auto-derived from name
        assert skill.name == "code_review"
        assert "review" in skill.tags

    def test_skill_matches_by_tag(self):
        skill = AgentSkill(
            name="deploy",
            description="Deploy services",
            tags=["deployment", "infrastructure", "ops"],
        )
        assert skill.matches("ops")
        assert skill.matches("infrastructure")
        assert not skill.matches("review")

    def test_backward_compat_alias(self):
        assert AgentCapability is AgentSkill
        cap = AgentCapability("test_cap", "Test capability")
        assert cap.name == "test_cap"
        assert cap.id == "test_cap"

    def test_skill_with_security(self):
        skill = AgentSkill(
            name="deploy",
            description="Deploy services",
            security_requirements=["api_key_auth", "oauth2_prod"],
        )
        assert len(skill.security_requirements) == 2

    def test_skill_explicit_id(self):
        skill = AgentSkill(name="review", id="custom-id")
        assert skill.id == "custom-id"
        assert skill.name == "review"


# ---------------------------------------------------------------------------
# AgentCard tests
# ---------------------------------------------------------------------------


class TestAgentCardSpec:
    """A2A 1.0: AgentCard with security schemes, signatures, interfaces."""

    def test_card_with_security_schemes(self):
        card = AgentCard(
            name="secure-agent",
            security_schemes=[
                SecurityScheme(scheme_type="APIKey", in_field="header", name="X-A2A-Key"),
                SecurityScheme(scheme_type="OAuth2", flows={"clientCredentials": {"tokenUrl": "/token"}}),
                SecurityScheme(scheme_type="MutualTLS"),
            ],
        )
        assert len(card.security_schemes) == 3
        types = [s.scheme_type for s in card.security_schemes]
        assert "APIKey" in types
        assert "OAuth2" in types
        assert "MutualTLS" in types

    def test_card_with_signatures(self):
        card = AgentCard(
            name="signed-agent",
            signatures=["eyJhbGciOiJSUzI1NiJ9.test.sig1", "eyJhbGciOiJFUzI1NiJ9.test.sig2"],
        )
        assert len(card.signatures) == 2

    def test_card_with_supported_interfaces(self):
        card = AgentCard(
            name="multi-transport",
            supported_interfaces=[
                {"protocolBinding": "JSONRPC", "url": "https://agent.example.com/jsonrpc"},
                {"protocolBinding": "GRPC", "url": "grpc://agent.example.com:50051"},
                {"protocolBinding": "HTTP+JSON", "url": "https://agent.example.com/api"},
            ],
        )
        assert len(card.supported_interfaces) == 3
        bindings = [i["protocolBinding"] for i in card.supported_interfaces]
        assert "JSONRPC" in bindings
        assert "GRPC" in bindings

    def test_card_with_extensions(self):
        card = AgentCard(
            name="dharma-agent",
            extensions=[
                {"uri": "dharma:telos-gate", "required": True},
                {"uri": "dharma:witness", "required": False},
            ],
        )
        assert len(card.extensions) == 2

    def test_backward_compat_capabilities_kwarg(self):
        card = AgentCard(
            name="legacy-agent",
            capabilities=[
                AgentCapability("code_review", "Review code"),
            ],
        )
        assert len(card.skills) == 1
        assert card.skills[0].name == "code_review"
        assert card.capabilities is card.skills

    def test_skills_preferred_over_capabilities(self):
        card = AgentCard(
            name="modern-agent",
            skills=[
                AgentSkill(name="deploy", description="Deploy services", tags=["ops"]),
            ],
        )
        assert len(card.skills) == 1
        assert card.capabilities is card.skills

    def test_from_dict_with_skills_key(self):
        data = {
            "name": "test-agent",
            "skills": [
                {"name": "review", "description": "Review code", "tags": ["review"]},
            ],
            "security_schemes": [
                {"scheme_type": "APIKey", "name": "X-Key"},
            ],
        }
        card = AgentCard.from_dict(data)
        assert len(card.skills) == 1
        assert card.skills[0].tags == ["review"]
        assert len(card.security_schemes) == 1

    def test_from_dict_with_legacy_capabilities_key(self):
        data = {
            "name": "legacy",
            "capabilities": [
                {"name": "test", "description": "Testing"},
            ],
        }
        card = AgentCard.from_dict(data)
        assert len(card.skills) == 1
        assert card.skills[0].name == "test"

    def test_to_dict_roundtrip(self):
        card = AgentCard(
            name="roundtrip",
            skills=[AgentSkill(name="test", description="Test skill", tags=["qa"])],
            security_schemes=[SecurityScheme(scheme_type="APIKey")],
            signatures=["sig1"],
            supported_interfaces=[{"protocolBinding": "HTTP+JSON"}],
        )
        d = card.to_dict()
        card2 = AgentCard.from_dict(d)
        assert card2.name == card.name
        assert len(card2.skills) == 1
        assert card2.skills[0].tags == ["qa"]


# ---------------------------------------------------------------------------
# Gateway spec-standard endpoint tests
# ---------------------------------------------------------------------------


class TestGatewaySpecEndpoints:
    """A2A 1.0: spec-standard endpoint paths."""

    def test_agent_card_discovery(self, http_client: TestClient):
        resp = http_client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-node"

    def test_submit_task_spec_path(self, http_client: TestClient, server: A2AServer):
        server.set_default_handler(lambda t: t)
        resp = http_client.post("/tasks", json={
            "from_agent": "test",
            "capability": "code_review",
            "messages": [{"role": "user", "content": "Review this"}],
        }, headers={"X-A2A-Key": "test-key"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["context_id"]  # auto-generated
        assert data["status"] == "completed"

    def test_get_task_spec_path(self, http_client: TestClient, server: A2AServer):
        server.set_default_handler(lambda t: t)
        submit = http_client.post("/tasks", json={
            "from_agent": "test",
            "messages": [{"content": "hello"}],
        }, headers={"X-A2A-Key": "test-key"})
        task_id = submit.json()["id"]
        resp = http_client.get(f"/tasks/{task_id}", headers={"X-A2A-Key": "test-key"})
        assert resp.status_code == 200

    def test_cancel_spec_path(self, http_client: TestClient, server: A2AServer):
        def pause(t: A2ATask) -> A2ATask:
            t.status = A2ATaskStatus.INPUT_REQUIRED
            return t

        server.register_handler("long_task", pause)
        submit = http_client.post("/tasks", json={
            "capability": "long_task",
            "messages": [{"content": "go"}],
        }, headers={"X-A2A-Key": "test-key"})
        task_id = submit.json()["id"]
        resp = http_client.post(f"/tasks/{task_id}:cancel", headers={"X-A2A-Key": "test-key"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_reject_spec_path(self, http_client: TestClient, server: A2AServer):
        def pause(t: A2ATask) -> A2ATask:
            t.status = A2ATaskStatus.INPUT_REQUIRED
            return t

        server.register_handler("gated_task", pause)
        submit = http_client.post("/tasks", json={
            "capability": "gated_task",
            "messages": [{"content": "do this"}],
        }, headers={"X-A2A-Key": "test-key"})
        task_id = submit.json()["id"]
        resp = http_client.post(
            f"/tasks/{task_id}:reject",
            json={"reason": "telos gate failed"},
            headers={"X-A2A-Key": "test-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"
        assert resp.json()["reason"] == "telos gate failed"

    def test_health_spec_path(self, http_client: TestClient):
        resp = http_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["spec_version"] == "a2a-1.0"
        assert data["gateway_version"] == "2.0.0"
        assert "skills" in data

    def test_skills_endpoint(self, http_client: TestClient, registry: CardRegistry):
        registry.register(AgentCard(
            name="coder",
            skills=[AgentSkill(name="code_review", description="Review code", tags=["review"])],
        ))
        resp = http_client.get("/skills", headers={"X-A2A-Key": "test-key"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["agents"]) > 0

    def test_sse_stream_endpoint(self, http_client: TestClient, server: A2AServer):
        server.set_default_handler(lambda t: t)
        submit = http_client.post("/tasks", json={
            "messages": [{"content": "stream me"}],
        }, headers={"X-A2A-Key": "test-key"})
        task_id = submit.json()["id"]
        resp = http_client.get(
            f"/tasks/{task_id}:stream",
            headers={"X-A2A-Key": "test-key"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        # Completed task should emit statusUpdate then end
        assert "statusUpdate" in resp.text

    def test_legacy_endpoints_still_work(self, http_client: TestClient, server: A2AServer):
        server.set_default_handler(lambda t: t)
        resp = http_client.post("/a2a/tasks", json={
            "messages": [{"content": "legacy"}],
        }, headers={"X-A2A-Key": "test-key"})
        assert resp.status_code == 201

        resp = http_client.get("/a2a/health")
        assert resp.status_code == 200

    def test_context_id_in_gateway_response(self, http_client: TestClient, server: A2AServer):
        server.set_default_handler(lambda t: t)
        resp = http_client.post("/tasks", json={
            "context_id": "gateway-ctx-123",
            "messages": [{"content": "with context"}],
        }, headers={"X-A2A-Key": "test-key"})
        data = resp.json()
        assert data["context_id"] == "gateway-ctx-123"


# ---------------------------------------------------------------------------
# Cycle detection tests
# ---------------------------------------------------------------------------


class TestCycleDetection:
    """Cycle detection on A2A dispatch chains."""

    def test_direct_cycle_detected(self, client: A2AClient, registry: CardRegistry, server: A2AServer):
        registry.register(AgentCard(name="agent-a", skills=[AgentSkill("task", "Do stuff")]))
        registry.register(AgentCard(name="agent-b", skills=[AgentSkill("task", "Do stuff")]))
        server.set_default_handler(lambda t: t)

        ctx = "cycle-test-1"
        r1 = client.delegate_to("agent-a", "do task", capability="task", from_agent="agent-b", context_id=ctx)
        assert r1.success

        # Same triple (agent-b -> agent-a, "task") should be detected as cycle
        r2 = client.delegate_to("agent-a", "do task again", capability="task", from_agent="agent-b", context_id=ctx)
        assert not r2.success
        assert "Cycle detected" in r2.error

    def test_depth_limit(self, client: A2AClient, registry: CardRegistry, server: A2AServer):
        max_depth = 3
        client._max_depth = max_depth
        server.set_default_handler(lambda t: t)

        for i in range(max_depth + 2):
            registry.register(AgentCard(name=f"agent-{i}", skills=[AgentSkill(f"task-{i}", "stuff")]))

        ctx = "depth-test-1"
        for i in range(max_depth):
            r = client.delegate_to(f"agent-{i}", "task", capability=f"task-{i}", from_agent=f"sender-{i}", context_id=ctx)
            assert r.success, f"Delegation {i} should succeed"

        r = client.delegate_to(f"agent-{max_depth}", "task", capability=f"task-{max_depth}", from_agent=f"sender-{max_depth}", context_id=ctx)
        assert not r.success
        assert "depth limit" in r.error

    def test_no_cycle_without_context(self, client: A2AClient, registry: CardRegistry, server: A2AServer):
        registry.register(AgentCard(name="agent-x", skills=[AgentSkill("do", "stuff")]))
        server.set_default_handler(lambda t: t)

        # Without context_id, cycle detection is skipped
        r1 = client.delegate_to("agent-x", "first", capability="do", from_agent="sender")
        assert r1.success
        r2 = client.delegate_to("agent-x", "second", capability="do", from_agent="sender")
        assert r2.success

    def test_different_contexts_independent(self, client: A2AClient, registry: CardRegistry, server: A2AServer):
        registry.register(AgentCard(name="agent-y", skills=[AgentSkill("work", "do work")]))
        server.set_default_handler(lambda t: t)

        r1 = client.delegate_to("agent-y", "task1", capability="work", from_agent="boss", context_id="ctx-1")
        assert r1.success
        # Same triple but different context should NOT be a cycle
        r2 = client.delegate_to("agent-y", "task2", capability="work", from_agent="boss", context_id="ctx-2")
        assert r2.success


# ---------------------------------------------------------------------------
# Backward compatibility tests
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    """Ensure all existing patterns still work."""

    def test_messages_kwarg_on_task(self):
        task = A2ATask(
            from_agent="test",
            to_agent="reviewer",
            messages=[A2AMessage.text("Review this")],
        )
        assert len(task.messages) == 1
        assert len(task.history) == 1
        assert task.messages is task.history

    def test_capabilities_kwarg_on_card(self):
        card = AgentCard(
            name="test",
            capabilities=[AgentCapability("review", "Review code")],
        )
        assert len(card.skills) == 1
        assert card.capabilities is card.skills

    def test_agent_capability_positional_args(self):
        cap = AgentCapability("code_review", "Review code for bugs")
        assert cap.name == "code_review"
        assert cap.description == "Review code for bugs"
        assert cap.matches("code_review")

    def test_file_part_type_still_works(self):
        p = A2APart(type=A2APartType.FILE, content="/path/to/file")
        assert p.type == A2APartType.FILE

    def test_server_submit_with_messages(self, server: A2AServer):
        server.set_default_handler(lambda t: t)
        task = server.submit(A2ATask(
            from_agent="test",
            capability="test",
            messages=[A2AMessage.text("hello")],
        ))
        assert task.status == A2ATaskStatus.COMPLETED
        assert len(task.history) == 1

    def test_bridge_part_types(self):
        from dharma_swarm.a2a.a2a_bridge import A2ABridge
        bridge = A2ABridge(
            server=A2AServer(),
            registry=CardRegistry(cards_dir=Path("/tmp/test-cards-dummy")),
        )
        msg = {
            "from": "hermes",
            "to": "devin",
            "subject": "Test",
            "body": "Hello",
            "type": "task",
            "attachments": ["/path/to/file.txt"],
        }
        task = bridge.trishula_message_to_a2a_task(msg)
        assert len(task.history) == 1
        assert len(task.history[0].parts) == 2
        assert task.history[0].parts[0].type == A2APartType.TEXT
        assert task.history[0].parts[1].type == A2APartType.FILE


# ---------------------------------------------------------------------------
# AgentCard from_agent_identity tests
# ---------------------------------------------------------------------------


class TestFromAgentIdentity:
    """Verify role -> skills mapping produces valid AgentSkill objects."""

    def test_coder_identity(self):
        identity = {"name": "coder-1", "role": "coder", "model": "gpt-4"}
        card = AgentCard.from_agent_identity(identity)
        assert len(card.skills) == 3
        assert all(s.id for s in card.skills)
        assert all(s.tags for s in card.skills)
        assert card.has_capability("code_review")

    def test_unknown_role_fallback(self):
        identity = {"name": "custom", "role": "wizard"}
        card = AgentCard.from_agent_identity(identity)
        assert len(card.skills) == 1
        assert card.skills[0].id == "wizard"
        assert card.skills[0].tags == ["wizard"]
