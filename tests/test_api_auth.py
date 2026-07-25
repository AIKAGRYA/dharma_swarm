"""WP-0S ingress contract (TIT-010): minimum fail-closed floor for the dashboard API.

Pins the transport-classification matrix in api/main.py and the mode
resolution in dharma_swarm/api_keys.py:

- production-shaped mode refuses startup and fail-closes every non-public
  ingress when DASHBOARD_API_KEY is absent;
- the bearer decision covers every non-gateway transport (REST under any
  prefix, /holon, /graphql) instead of the old /api path-prefix scope;
- the keyless local-development lane is bound to loopback clients only;
- WebSocket handshakes are covered at the ASGI layer (BaseHTTPMiddleware
  never sees websocket scope);
- the public webhook route fails closed in production-shaped mode when its
  verification material is absent (the handler itself is fail-open keyless:
  dharma_swarm/verify/github_app.py verify_signature).

Authority: docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md (WP-0S).
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import api.main as api_main
from dharma_swarm.api_keys import (
    API_MODE_AMBIGUOUS,
    API_MODE_LOCAL_DEV,
    API_MODE_PRODUCTION,
    DASHBOARD_API_MODE_ENV,
    dashboard_api_mode,
)

FIXTURE_KEY = "fixture-token-not-live-wp0s"
NON_LOOPBACK = ("203.0.113.9", 51000)
LOOPBACK = ("127.0.0.1", 51000)

# A mutating route outside the old /api prefix scope: the TIT-010 bypass.
HOLON_PATH = "/holon/no-such-holon-fixture/chat"
HOLON_BODY = {"message": "fixture"}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("DASHBOARD_API_KEY", raising=False)
    monkeypatch.delenv(DASHBOARD_API_MODE_ENV, raising=False)
    monkeypatch.delenv("DHARMA_VERIFY_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("DHARMA_API_ALLOW_LOCAL_NOAUTH", raising=False)


def _client() -> TestClient:
    return TestClient(api_main.app)


def _http_status(path: str, *, method: str = "GET", client: tuple[str, int],
                 headers: dict[str, str] | None = None,
                 body: bytes = b'{"message": "fixture"}') -> int:
    """Drive the real ASGI app with a controlled client address."""
    header_items = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    if method == "POST":
        header_items.append((b"content-type", b"application/json"))
        header_items.append((b"content-length", str(len(body)).encode("latin-1")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("latin-1"),
        "query_string": b"",
        "scheme": "http",
        "headers": header_items,
        "client": client,
        "server": ("testserver", 80),
        "root_path": "",
    }
    messages: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(api_main.app(scope, receive, send))
    return next(
        m["status"] for m in messages if m["type"] == "http.response.start"
    )


def _ws_close_code(path: str, *, client: tuple[str, int]) -> int | None:
    """Drive a raw websocket handshake; return the close code or None if accepted."""
    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0"},
        "path": path,
        "raw_path": path.encode("latin-1"),
        "query_string": b"",
        "scheme": "ws",
        "headers": [],
        "client": client,
        "server": ("testserver", 80),
        "root_path": "",
        "subprotocols": [],
    }
    messages: list[dict] = []
    connected = {"sent": False}

    async def receive():
        if not connected["sent"]:
            connected["sent"] = True
            return {"type": "websocket.connect"}
        return {"type": "websocket.disconnect", "code": 1000}

    async def send(message):
        messages.append(message)
        if message["type"] in {"websocket.close", "websocket.accept"}:
            raise _HandshakeSettled

    class _HandshakeSettled(Exception):
        pass

    post_handshake_errors: list[BaseException] = []
    try:
        asyncio.run(api_main.app(scope, receive, send))
    except _HandshakeSettled:
        pass
    except Exception as exc:
        # Post-accept route errors do not decide the handshake verdict, but
        # they are captured (not swallowed) so a failure below can show them.
        post_handshake_errors.append(exc)
    for message in messages:
        if message["type"] == "websocket.close":
            return message["code"]
        if message["type"] == "websocket.accept":
            return None
    pytest.fail(
        "handshake produced neither accept nor close: "
        f"{messages}; post-handshake errors: {post_handshake_errors}"
    )


# ── Mode resolution (dharma_swarm/api_keys.py) ─────────────────────


class TestModeResolution:
    @pytest.mark.parametrize("value", ["production", "production-shaped", "prod", " PRODUCTION "])
    def test_explicit_production_values(self, value):
        assert dashboard_api_mode({DASHBOARD_API_MODE_ENV: value}) == API_MODE_PRODUCTION

    @pytest.mark.parametrize("value", ["local-development", "local-dev", "dev", " Local-Development "])
    def test_explicit_local_development_values(self, value):
        assert dashboard_api_mode({DASHBOARD_API_MODE_ENV: value}) == API_MODE_LOCAL_DEV

    @pytest.mark.parametrize("env", [{}, {DASHBOARD_API_MODE_ENV: ""}, {DASHBOARD_API_MODE_ENV: "banana"}])
    def test_everything_else_is_ambiguous(self, env):
        assert dashboard_api_mode(env) == API_MODE_AMBIGUOUS


# ── Production-shaped mode, key absent: fail closed ────────────────


class TestProductionKeyless:
    def test_startup_refused_without_key(self, monkeypatch):
        monkeypatch.setenv(DASHBOARD_API_MODE_ENV, "production")
        with pytest.raises(RuntimeError, match="production-shaped startup"):
            with TestClient(api_main.app):
                pass

    def test_startup_refused_with_blank_key(self, monkeypatch):
        monkeypatch.setenv(DASHBOARD_API_MODE_ENV, "production")
        monkeypatch.setenv("DASHBOARD_API_KEY", "   ")
        with pytest.raises(RuntimeError, match="production-shaped startup"):
            with TestClient(api_main.app):
                pass

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/api/chat/status"),
            ("POST", HOLON_PATH),
            ("GET", "/graphql/search"),
        ],
    )
    def test_http_ingress_fails_closed(self, monkeypatch, method, path):
        monkeypatch.setenv(DASHBOARD_API_MODE_ENV, "production")
        response = _client().request(method, path, json=HOLON_BODY if method == "POST" else None)
        assert response.status_code == 503

    def test_websocket_handshake_fails_closed(self, monkeypatch):
        monkeypatch.setenv(DASHBOARD_API_MODE_ENV, "production")
        with pytest.raises(WebSocketDisconnect):
            with _client().websocket_connect("/ws/agents"):
                pass

    def test_public_root_stays_open(self, monkeypatch):
        monkeypatch.setenv(DASHBOARD_API_MODE_ENV, "production")
        assert _client().get("/").status_code == 200


# ── Key configured: one bearer decision across every transport ─────


class TestKeySetEnforcement:
    @pytest.fixture(autouse=True)
    def _key(self, monkeypatch):
        monkeypatch.setenv("DASHBOARD_API_KEY", FIXTURE_KEY)

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/api/chat/status"),
            ("POST", HOLON_PATH),
            ("GET", "/graphql/search"),
            ("GET", "/graphql/stigmergy_marks"),
        ],
    )
    def test_missing_bearer_rejected_on_every_transport(self, method, path):
        response = _client().request(method, path, json=HOLON_BODY if method == "POST" else None)
        assert response.status_code == 401

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/api/chat/status"),
            ("POST", HOLON_PATH),
            ("GET", "/graphql/search"),
        ],
    )
    def test_invalid_bearer_rejected_on_every_transport(self, method, path):
        response = _client().request(
            method,
            path,
            json=HOLON_BODY if method == "POST" else None,
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert response.status_code == 401

    def test_valid_bearer_reaches_holon_route(self):
        response = _client().post(
            HOLON_PATH,
            json=HOLON_BODY,
            headers={"Authorization": f"Bearer {FIXTURE_KEY}"},
        )
        # 404 (unknown holon) proves the request passed authorization and
        # reached the route handler; 401 would mean the bearer was refused.
        assert response.status_code == 404

    def test_valid_bearer_reaches_graphql_route(self):
        response = _client().get(
            "/graphql/search",
            headers={"Authorization": f"Bearer {FIXTURE_KEY}"},
        )
        # 422 (missing required query params) proves auth admitted the call.
        assert response.status_code != 401

    def test_public_routes_stay_open_without_bearer(self):
        assert _client().get("/").status_code == 200
        assert _client().get("/docs").status_code == 200

    def test_gateway_transport_keeps_its_own_authority(self):
        # /a2a/health is the gateway's own route; the dashboard bearer
        # decision must not gate the gateway transport (X-A2A-Key owner:
        # dharma_swarm/a2a/node_gateway.py). Without lifespan init the
        # gateway reports its own uninitialized state — reaching that
        # handler (a node_id payload, not the bearer 401) is the proof.
        response = _client().get("/a2a/health")
        assert response.status_code != 401
        assert "node_id" in response.json()

    def test_blank_key_fails_closed(self, monkeypatch):
        monkeypatch.setenv("DASHBOARD_API_KEY", "   ")
        response = _client().get("/api/chat/status", headers={"Authorization": "Bearer "})
        assert response.status_code == 503
        assert response.json()["error"] == "auth_misconfigured"


# ── Keyless development lane: loopback only ────────────────────────


class TestKeylessLoopbackLane:
    def test_testclient_loopback_reaches_routes(self):
        # TestClient presents the in-process "testclient" host; the keyless
        # lane admits it so the documented local dev flow keeps working.
        response = _client().post(HOLON_PATH, json=HOLON_BODY)
        assert response.status_code == 404

    @pytest.mark.parametrize("mode_value", [None, "local-development"])
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/api/chat/status"),
            ("POST", HOLON_PATH),
        ],
    )
    def test_non_loopback_client_is_rejected(self, monkeypatch, mode_value, method, path):
        if mode_value is not None:
            monkeypatch.setenv(DASHBOARD_API_MODE_ENV, mode_value)
        assert _http_status(path, method=method, client=NON_LOOPBACK) == 401

    def test_loopback_ip_rejected_by_default(self, monkeypatch):
        # A same-host reverse proxy presents every remote caller as loopback,
        # so a loopback IP is NOT trusted for the keyless lane by default.
        monkeypatch.delenv("DHARMA_API_ALLOW_LOCAL_NOAUTH", raising=False)
        assert _http_status(HOLON_PATH, method="POST", client=LOOPBACK) == 401

    def test_loopback_ip_admitted_only_with_explicit_optin(self, monkeypatch):
        # Mirrors the A2A gateway's A2A_ALLOW_LOCAL_NOAUTH opt-in: only when
        # the operator explicitly trusts loopback does the IP lane open.
        monkeypatch.setenv("DHARMA_API_ALLOW_LOCAL_NOAUTH", "1")
        # 404 from the holon router (unknown name) proves admission.
        assert _http_status(HOLON_PATH, method="POST", client=LOOPBACK) == 404

    def test_in_process_testclient_stays_admitted_without_optin(self, monkeypatch):
        # The in-process TestClient sentinel is not a network peer, so it keeps
        # the documented keyless dev/test flow working with no opt-in.
        monkeypatch.delenv("DHARMA_API_ALLOW_LOCAL_NOAUTH", raising=False)
        assert _client().post(HOLON_PATH, json=HOLON_BODY).status_code == 404

    def test_public_route_open_for_non_loopback(self):
        assert _http_status("/", client=NON_LOOPBACK) == 200

    def test_keyless_websocket_non_loopback_rejected(self):
        assert _ws_close_code("/ws/agents", client=NON_LOOPBACK) is not None

    def test_keyless_websocket_loopback_rejected_by_default(self):
        assert _ws_close_code("/ws/agents", client=LOOPBACK) is not None

    def test_keyless_websocket_loopback_admitted_with_optin(self, monkeypatch):
        monkeypatch.setenv("DHARMA_API_ALLOW_LOCAL_NOAUTH", "1")
        assert _ws_close_code("/ws/agents", client=LOOPBACK) is None

    def test_unknown_peer_client_is_rejected(self):
        # A scope with no client address (some ASGI servers / proxy adapters
        # omit it) must fail closed, not be admitted to the keyless lane.
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "path": "/api/chat/status",
            "raw_path": b"/api/chat/status",
            "query_string": b"",
            "scheme": "http",
            "headers": [],
            "client": None,
            "server": ("testserver", 80),
            "root_path": "",
        }
        messages: list[dict] = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        asyncio.run(api_main.app(scope, receive, send))
        status = next(
            m["status"] for m in messages if m["type"] == "http.response.start"
        )
        assert status == 401


# ── Webhook verification material (production-shaped) ──────────────


class TestWebhookMaterial:
    def test_production_without_material_fails_closed(self, monkeypatch):
        monkeypatch.setenv(DASHBOARD_API_MODE_ENV, "production")
        monkeypatch.setenv("DASHBOARD_API_KEY", FIXTURE_KEY)
        response = _client().post("/api/verify/webhook", json={})
        assert response.status_code == 503

    def test_production_with_material_reaches_handler(self, monkeypatch):
        monkeypatch.setenv(DASHBOARD_API_MODE_ENV, "production")
        monkeypatch.setenv("DASHBOARD_API_KEY", FIXTURE_KEY)
        monkeypatch.setenv("DHARMA_VERIFY_WEBHOOK_SECRET", "fixture-webhook-secret")
        response = _client().post("/api/verify/webhook", json={})
        assert response.status_code != 503

    def test_dev_lane_webhook_unchanged(self):
        response = _client().post("/api/verify/webhook", json={})
        assert response.status_code != 503
