"""DHARMA COMMAND — Dashboard API.

FastAPI app with lifespan, CORS, WebSocket, and routers.

Usage:
    cd ~/dharma_swarm
    uvicorn api.main:app --port 8000 --reload
"""

from __future__ import annotations

import hmac
import logging
import os
import asyncio
from contextlib import asynccontextmanager, suppress
from dharma_swarm.daemon_config import dharma_state_dir
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dharma_swarm.api_keys import (
    API_MODE_LOCAL_DEV,
    API_MODE_PRODUCTION,
    DASHBOARD_API_KEY_ENV,
    DASHBOARD_API_MODE_ENV,
    dashboard_api_mode,
    normalize_env_aliases,
)

logger = logging.getLogger(__name__)

# ── Singleton State ───────────────────────────────────────────────

_state: dict[str, Any] = {}
_OPERATOR_STATE_DIR = dharma_state_dir()
_OPERATOR_PID_FILE = _OPERATOR_STATE_DIR / "operator.pid"


def _publish_operator_pid(pid: int | None = None) -> None:
    resolved_pid = pid or os.getpid()
    try:
        _OPERATOR_STATE_DIR.mkdir(parents=True, exist_ok=True)
        _OPERATOR_PID_FILE.write_text(f"{resolved_pid}\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to write operator pid file: %s", exc)


def _clear_operator_pid(pid: int | None = None) -> None:
    resolved_pid = str(pid or os.getpid())
    try:
        current = _OPERATOR_PID_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return
    if current != resolved_pid:
        return
    try:
        _OPERATOR_PID_FILE.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Failed to clear operator pid file: %s", exc)


def _log_auth_mode() -> None:
    api_key = _get_api_key()
    mode = dashboard_api_mode()
    if api_key is None:
        logger.warning(
            "Dashboard API bearer auth is disabled because no auth secret is "
            "configured (mode=%s). The keyless lane serves loopback clients "
            "only; non-loopback requests are refused. Set DASHBOARD_API_KEY "
            "or select DHARMA_API_MODE=production for full fail-closed mode.",
            mode,
        )
    elif not api_key.strip():
        logger.error(
            "DASHBOARD_API_KEY is set but blank; dashboard HTTP and WebSocket "
            "auth are fail-closed"
        )
    else:
        logger.info(
            "Dashboard API authentication is enforced on every non-gateway "
            "transport (mode=%s).",
            mode,
        )


def get_swarm():
    """Get or create SwarmManager singleton.

    When DHARMA_ORGANISM_ROOT=1 (default: off), an Organism is composed
    AROUND the SwarmManager singleton (composition root, D5 of
    organism-rewire-2026-07): the Organism wraps the same SwarmManager
    instance and owns identity/StrangeLoop/attractor/heartbeat, while
    dispatch stays SwarmManager's. With the flag off this function is
    behaviorally identical to the pre-flag version.
    """
    if "swarm" not in _state:
        from dharma_swarm.swarm import SwarmManager

        _state["swarm"] = SwarmManager()
        if os.environ.get("DHARMA_ORGANISM_ROOT") == "1":
            try:
                from dharma_swarm.organism import Organism, set_organism

                organism = Organism(swarm=_state["swarm"])
                _state["organism"] = organism
                set_organism(organism)
                logger.info(
                    "Organism composition root active (DHARMA_ORGANISM_ROOT=1); "
                    "strange_loop=%s",
                    "reachable" if organism.strange_loop is not None else "unavailable",
                )
            except Exception as exc:
                # The flag must never take down the default boot path; record the
                # failure so get_organism() callers can diagnose why it is None.
                _state.pop("organism", None)
                _state["organism_init_error"] = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "Organism composition root init failed (non-fatal): %s", exc
                )
    return _state["swarm"]


def get_organism():
    """Return the Organism composition root, or None when the flag is off."""
    return _state.get("organism")


def get_boardstore_outbox():
    """Return the app-scoped TaskBoard → BoardStore shadow outbox, if ready."""
    return _state.get("boardstore_outbox")


def get_agent_directory():
    """Return the app-scoped stable-UID AgentDirectory, if ready."""
    return _state.get("agent_directory")


def get_trace_store():
    """Get or create TraceStore singleton."""
    if "traces" not in _state:
        from dharma_swarm.traces import TraceStore

        _state["traces"] = TraceStore()
    return _state["traces"]


def get_monitor():
    """Get or create SystemMonitor singleton."""
    if "monitor" not in _state:
        from dharma_swarm.monitor import SystemMonitor

        _state["monitor"] = SystemMonitor(trace_store=get_trace_store())
    return _state["monitor"]


def _initialize_node_gateway() -> None:
    """Compose the mounted A2A gateway from the existing server/card types."""
    from dharma_swarm.a2a.a2a_server import A2AServer
    from dharma_swarm.a2a.agent_card import AgentCard, CardRegistry
    from dharma_swarm.a2a.node_gateway import init_gateway

    node_id = os.getenv("DHARMA_NODE_ID", "dharma-hub")
    server = A2AServer()
    registry = CardRegistry()
    node_card = AgentCard(
        name=node_id,
        agent_uid=node_id,
        description="Dharma Swarm A2A HTTP gateway",
        endpoint=os.getenv("DHARMA_A2A_PUBLIC_ENDPOINT", "local://"),
        role="orchestrator",
        status="idle",
    )
    registry.register(node_card)
    init_gateway(
        server=server,
        registry=registry,
        node_card=node_card,
        node_id=node_id,
    )
    _state["a2a_server"] = server
    _state["card_registry"] = registry
    _state["node_card"] = node_card


def _initialize_boardstore_shadow(swarm: Any) -> None:
    """Compose one app-scoped shadow projector over the canonical TaskBoard."""
    from dharma_swarm.board.adapters.taskboard_adapter import TaskBoardAdapter
    from dharma_swarm.board.event_log import BoardEventLog
    from dharma_swarm.board.facade import BoardStoreFacade
    from dharma_swarm.board.task_command_outbox import TaskCommandOutbox

    task_board = getattr(swarm, "_task_board", None)
    if task_board is None:
        raise RuntimeError("canonical TaskBoard is not initialized")
    event_log = BoardEventLog(path=dharma_state_dir() / "board" / "event_log.sqlite3")
    facade = BoardStoreFacade(event_log=event_log)
    adapter = TaskBoardAdapter(task_board, event_log)
    outbox = TaskCommandOutbox(facade=facade, adapter=adapter)
    _state["boardstore_facade"] = facade
    _state["boardstore_outbox"] = outbox


def _initialize_agent_directory(swarm: Any) -> None:
    """Compose the credential-safe directory from existing control-plane stores."""
    from api.routers.fleet import _get_registry
    from dharma_swarm.a2a.agent_card import CardRegistry
    from dharma_swarm.a2a.agent_directory import AgentDirectory

    card_registry = _state.get("card_registry")
    if card_registry is None:
        card_registry = CardRegistry()
        _state["card_registry"] = card_registry
    node_registry = _get_registry()
    _state["node_registry"] = node_registry
    _state["agent_directory"] = AgentDirectory(
        card_registry=card_registry,
        node_registry=node_registry,
        dharma_home=dharma_state_dir("DHARMA_HOME"),
        telemetry_store=getattr(swarm, "_telemetry", None),
    )


# ── Lifespan ──────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize subsystems on startup, cleanup on shutdown."""
    # WP-0S (TIT-010): production-shaped startup is refused outright when the
    # required authentication material is absent or blank.
    if dashboard_api_mode() == API_MODE_PRODUCTION and not (_get_api_key() or "").strip():
        raise RuntimeError(
            "Refusing production-shaped startup: DASHBOARD_API_KEY is absent or "
            f"blank ({DASHBOARD_API_MODE_ENV}="
            f"{os.environ.get(DASHBOARD_API_MODE_ENV, '')!r}). Configure the key "
            f"or select {DASHBOARD_API_MODE_ENV}={API_MODE_LOCAL_DEV} for the "
            "loopback-bound development lane."
        )
    logger.info("DHARMA COMMAND API starting...")
    operator_pid = os.getpid()
    _publish_operator_pid(operator_pid)

    # Normalize dkeys/external env aliases before any provider resolution.
    aliased = normalize_env_aliases()
    if aliased:
        logger.info(
            "env alias normalization applied for %d configured credential(s)",
            len(aliased),
        )

    from dharma_swarm.ontology_runtime import get_shared_registry

    get_shared_registry()

    # Initialize trace store
    trace_store = get_trace_store()
    await trace_store.init()

    # Initialize swarm (connects to existing daemon state)
    swarm = get_swarm()
    swarm_init_task: asyncio.Task[None] | None = None
    try:
        init_timeout = float(os.getenv("DHARMA_SWARM_INIT_TIMEOUT_SECONDS", "3"))
        swarm_init_task = asyncio.create_task(swarm.init())
        _state["swarm_init_task"] = swarm_init_task
        await asyncio.wait_for(asyncio.shield(swarm_init_task), timeout=init_timeout)
        _state.pop("swarm_init_task", None)
    except TimeoutError:
        logger.warning(
            "Swarm init exceeded %.1fs; cancelling warmup to keep dashboard API responsive",
            init_timeout,
        )
        if swarm_init_task is not None and not swarm_init_task.done():
            swarm_init_task.cancel()
            with suppress(asyncio.CancelledError):
                await swarm_init_task
        _state.pop("swarm_init_task", None)
    except Exception as e:
        logger.warning("Swarm init partial: %s", e)

    try:
        _initialize_boardstore_shadow(swarm)
    except Exception as exc:
        _state["boardstore_shadow_error"] = type(exc).__name__
        logger.warning(
            "BoardStore shadow init failed; TaskBoard remains canonical: %s", exc
        )

    try:
        _initialize_node_gateway()
    except Exception as exc:
        from dharma_swarm.a2a.node_gateway import mark_gateway_degraded

        mark_gateway_degraded(type(exc).__name__)
        logger.warning("Node gateway init failed; health remains degraded: %s", exc)

    try:
        _initialize_agent_directory(swarm)
    except Exception as exc:
        _state["agent_directory_error"] = type(exc).__name__
        logger.warning(
            "AgentDirectory init failed; existing registries remain active: %s", exc
        )

    _log_auth_mode()
    logger.info("DHARMA COMMAND API ready on port 8420")
    try:
        yield
    finally:
        logger.info("DHARMA COMMAND API shutting down")
        pending_swarm_init = _state.pop("swarm_init_task", None)
        if pending_swarm_init is not None and not pending_swarm_init.done():
            pending_swarm_init.cancel()
            with suppress(asyncio.CancelledError):
                await pending_swarm_init
        if _state.pop("organism", None) is not None:
            from dharma_swarm.organism import set_organism

            set_organism(None)
        _state.clear()
        _clear_operator_pid(operator_pid)


# ── Auth ──────────────────────────────────────────────────────────


def _get_api_key() -> str | None:
    """Read DASHBOARD_API_KEY from environment (per-request, supports rotation)."""
    return os.environ.get(DASHBOARD_API_KEY_ENV)


# Routes that never require authentication (method, path).
_PUBLIC_ROUTES: set[tuple[str, str]] = {
    ("GET", "/"),
    ("GET", "/api/health"),
    ("GET", "/api/verify/health"),
    ("GET", "/docs"),
    ("GET", "/openapi.json"),
    ("GET", "/redoc"),
    ("POST", "/api/verify/webhook"),
    ("GET", "/a2a/health"),
    ("GET", "/.well-known/agent-card.json"),
}

_AUTH_FAILURE_RESPONSE = {
    "error": "unauthorized",
    "detail": "Invalid or missing API credential. Configure dashboard bearer auth and pass an Authorization header.",
}

_AUTH_CONFIGURATION_FAILURE_RESPONSE = {
    "error": "auth_misconfigured",
    "detail": "DASHBOARD_API_KEY is set but blank; unset it for loopback dev mode or configure a nonblank secret.",
}

_PRODUCTION_KEYLESS_RESPONSE = {
    "error": "auth_misconfigured",
    "detail": "Production-shaped mode requires DASHBOARD_API_KEY; every non-public ingress is fail-closed until it is configured.",
}

_WEBHOOK_MATERIAL_FAILURE_RESPONSE = {
    "error": "webhook_verification_unavailable",
    "detail": "Production-shaped mode refuses the webhook transport while DHARMA_VERIFY_WEBHOOK_SECRET is absent; the signature check cannot fail closed without it.",
}

# Webhook verification material; source of truth for the env name is
# dharma_swarm/verify/github_app.py (VerifyWebhookHandler webhook_secret
# fallback), which returns success for any payload when the secret is unset.
_VERIFY_WEBHOOK_SECRET_ENV = "DHARMA_VERIFY_WEBHOOK_SECRET"
_WEBHOOK_ROUTE = ("POST", "/api/verify/webhook")

# Transports that own their authorization decision end-to-end: the A2A
# gateway (dharma_swarm/a2a/node_gateway.py) enforces X-A2A-Key on every
# mutating route and rejects remote callers when no keys are configured.
_GATEWAY_PATH_PREFIXES = ("/a2a", "/tasks", "/skills", "/.well-known")
_GATEWAY_EXACT_PATHS = frozenset({"/health"})

# The fixed in-process peer name Starlette's TestClient presents. A real
# socket peer can only ever present a network address, never this literal, so
# admitting it cannot admit a network caller — it keeps the documented
# local/test flow working keyless without opening any reachable surface.
_IN_PROCESS_CLIENT_HOST = "testclient"

# Real loopback addresses. A same-host reverse proxy presents EVERY remote
# caller to the ASGI server as one of these, so a loopback peer is not proof
# of local access. Trusting it for the keyless lane therefore requires an
# explicit operator opt-in, mirroring the A2A gateway's A2A_ALLOW_LOCAL_NOAUTH
# guard (dharma_swarm/a2a/node_gateway.py) which refuses to treat a
# proxy-local peer as trusted without the same explicit signal.
_LOOPBACK_ADDRESSES = frozenset({"127.0.0.1", "::1", "localhost"})
_ALLOW_LOOPBACK_NOAUTH_ENV = "DHARMA_API_ALLOW_LOCAL_NOAUTH"


def _is_gateway_path(path: str) -> bool:
    if path in _GATEWAY_EXACT_PATHS:
        return True
    return any(
        path == prefix or path.startswith(prefix + "/")
        for prefix in _GATEWAY_PATH_PREFIXES
    )


def _client_is_loopback(scope) -> bool:
    """Whether the keyless lane may admit this peer. Fail closed by default.

    - Unknown peer (scope["client"] omitted by an adapter): refused.
    - The in-process TestClient sentinel: admitted (never a network caller).
    - A real loopback address: refused UNLESS the operator explicitly sets
      DHARMA_API_ALLOW_LOCAL_NOAUTH=1, because a same-host reverse proxy
      presents every remote caller as loopback (Greptile/Codex P1, #1026).
    - Anything else: refused.
    """
    client = scope.get("client")
    host = client[0] if client else None
    if host is None:
        return False
    if host == _IN_PROCESS_CLIENT_HOST:
        return True
    if host in _LOOPBACK_ADDRESSES:
        return os.environ.get(_ALLOW_LOOPBACK_NOAUTH_ENV) == "1"
    return False


def _bearer_authorized(scope, api_key: str) -> bool:
    auth_header = ""
    for name, value in scope.get("headers", []):
        if name == b"authorization":
            auth_header = value.decode("latin-1")
            break
    if not auth_header.startswith("Bearer "):
        return False
    return hmac.compare_digest(auth_header[7:], api_key)


def _ingress_decision(scope) -> tuple[int, dict[str, Any]] | None:
    """One fail-closed authorization decision for HTTP and WebSocket ingress.

    Returns None to admit the request, or ``(status, payload)`` to refuse it.
    Classification (WP-0S, TIT-010):

    - ``_PUBLIC_ROUTES`` are open, except the webhook transport in
      production-shaped mode without its verification material;
    - gateway paths keep their own fail-closed X-A2A-Key authority;
    - everything else — REST under any prefix, /holon, /graphql, and both
      WebSocket routers — is authenticated ingress behind one decision.

    Credentialed WebSocket handshakes are admitted here and validated
    fail-closed at the route by api.ws.authenticate_dashboard_websocket,
    which owns the subprotocol/cookie credential formats.
    """
    is_ws = scope["type"] == "websocket"
    path = (scope.get("path") or "/").rstrip("/") or "/"
    method = "GET" if is_ws else str(scope.get("method", "GET")).upper()
    mode = dashboard_api_mode()

    if not is_ws and (method, path) in _PUBLIC_ROUTES:
        if (
            (method, path) == _WEBHOOK_ROUTE
            and mode == API_MODE_PRODUCTION
            and not os.environ.get(_VERIFY_WEBHOOK_SECRET_ENV, "").strip()
        ):
            return 503, _WEBHOOK_MATERIAL_FAILURE_RESPONSE
        return None
    if _is_gateway_path(path):
        return None

    api_key = _get_api_key()
    if api_key is None:
        if mode == API_MODE_PRODUCTION:
            return 503, _PRODUCTION_KEYLESS_RESPONSE
        # Ambiguous or explicit local-development mode: the keyless escape
        # hatch is loopback-bound — the safer selection for an ambiguous
        # deployment, and the documented boundary for the explicit dev lane.
        if _client_is_loopback(scope):
            return None
        return 401, _AUTH_FAILURE_RESPONSE
    if not api_key.strip():
        # A blank configured secret is neither dev mode nor a credential.
        return 503, _AUTH_CONFIGURATION_FAILURE_RESPONSE
    if is_ws:
        return None
    if _bearer_authorized(scope, api_key):
        return None
    return 401, _AUTH_FAILURE_RESPONSE


class IngressAuthMiddleware:
    """Pure-ASGI ingress gate for HTTP and WebSocket scopes.

    BaseHTTPMiddleware structurally never runs on ``websocket`` scope, which
    left the WS handshake outside the middleware decision (TIT-010); this
    class applies ``_ingress_decision`` to both transports at the ASGI layer.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        decision = _ingress_decision(scope)
        if decision is None:
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await receive()  # consume websocket.connect
            await send({"type": "websocket.close", "code": 4401})
            return
        status_code, payload = decision
        response = JSONResponse(status_code=status_code, content=payload)
        await response(scope, receive, send)


# ── App ───────────────────────────────────────────────────────────

app = FastAPI(
    title="DHARMA COMMAND",
    description="Neo-Tokyo Swarm Dashboard API",
    version="0.1.0",
    lifespan=lifespan,
)

# Auth middleware must be added BEFORE CORS so unauthenticated requests
# are rejected before CORS headers are applied.
app.add_middleware(IngressAuthMiddleware)

# CORS for Next.js dev server — explicit origins, not wildcard
_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "DASHBOARD_CORS_ORIGINS",
        "http://localhost:3000,http://localhost:3001,http://localhost:8420",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Register Routers ─────────────────────────────────────────────


def _register_routers(api_app: FastAPI) -> None:
    from api.routers.health import router as health_router
    from api.routers.agents import (
        router as agents_router,
        ws_router as agents_ws_router,
    )
    from api.routers.evolution import router as evolution_router
    from api.routers.ontology import router as ontology_router
    from api.routers.lineage import router as lineage_router
    from api.routers.stigmergy import router as stigmergy_router
    from api.routers.commands import router as commands_router
    from api.routers.modules import router as modules_router
    from api.routers.dashboard_new import router as dashboard_new_router
    from api.routers.telemetry import router as telemetry_router
    from api.routers.graphql_router import router as graphql_router
    from api.routers.verify import router as verify_router
    from api.routers.opportunities import router as opportunities_router
    from api.routers.manifest import router as manifest_router
    from api.routers.revenue import router as revenue_router
    from api.routers.control_surface import router as control_surface_router
    from api.routers.model_pool import router as model_pool_router
    from api.routers.operator_coherence import router as operator_coherence_router
    from api.routers.holon import router as holon_router
    from api.routers.runtime import router as runtime_router

    api_app.include_router(holon_router)
    api_app.include_router(runtime_router)
    api_app.include_router(health_router)
    api_app.include_router(agents_router)
    api_app.include_router(agents_ws_router)
    api_app.include_router(evolution_router)
    api_app.include_router(ontology_router)
    api_app.include_router(lineage_router)
    api_app.include_router(stigmergy_router)
    api_app.include_router(commands_router)
    api_app.include_router(modules_router)
    api_app.include_router(dashboard_new_router)
    api_app.include_router(telemetry_router)
    api_app.include_router(graphql_router)
    api_app.include_router(verify_router)
    api_app.include_router(opportunities_router)
    api_app.include_router(manifest_router)
    api_app.include_router(revenue_router)
    api_app.include_router(control_surface_router)
    api_app.include_router(model_pool_router)
    api_app.include_router(operator_coherence_router)

    from api.routers.chat import router as chat_router, ws_router as chat_ws_router
    from api.routers.fleet import router as fleet_router
    from dharma_swarm.a2a.node_gateway import router as gateway_router

    api_app.include_router(chat_router)
    api_app.include_router(chat_ws_router)
    api_app.include_router(fleet_router)
    api_app.include_router(gateway_router)


_register_routers(app)


# ── Root ──────────────────────────────────────────────────────────


@app.get("/")
async def root():
    return {
        "name": "DHARMA COMMAND",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health",
    }
