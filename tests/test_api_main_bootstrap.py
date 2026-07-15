from __future__ import annotations

import builtins
import importlib
import sys

from fastapi.testclient import TestClient


class TestOrganismCompositionRoot:
    """DHARMA_ORGANISM_ROOT gates the Organism composition root in get_swarm().

    Flag off (default): byte-identical behavior — plain SwarmManager,
    no Organism constructed. Flag on: Organism wraps the SAME SwarmManager
    instance; StrangeLoop is production-reachable through it.
    """

    def _fresh(self, monkeypatch):
        import api.main as api_main
        import dharma_swarm.organism as organism_mod

        monkeypatch.setattr(api_main, "_state", {})
        monkeypatch.setattr(organism_mod, "_global_organism", None)
        monkeypatch.setattr(organism_mod, "_global_graph_store", None)
        return api_main, organism_mod

    def test_flag_off_no_organism_constructed(self, monkeypatch) -> None:
        api_main, organism_mod = self._fresh(monkeypatch)
        monkeypatch.delenv("DHARMA_ORGANISM_ROOT", raising=False)

        class _Boom:
            def __init__(self, *args, **kwargs):
                raise AssertionError(
                    "Organism must not be constructed when DHARMA_ORGANISM_ROOT is off"
                )

        monkeypatch.setattr(organism_mod, "Organism", _Boom)

        from dharma_swarm.swarm import SwarmManager

        swarm = api_main.get_swarm()
        assert isinstance(swarm, SwarmManager)
        assert "organism" not in api_main._state
        assert api_main.get_organism() is None
        assert organism_mod.get_organism() is None
        # Singleton behavior unchanged
        assert api_main.get_swarm() is swarm

    def test_flag_zero_is_off(self, monkeypatch) -> None:
        api_main, organism_mod = self._fresh(monkeypatch)
        monkeypatch.setenv("DHARMA_ORGANISM_ROOT", "0")
        api_main.get_swarm()
        assert "organism" not in api_main._state
        assert organism_mod.get_organism() is None

    def test_flag_on_organism_wraps_same_swarm(self, monkeypatch, tmp_path) -> None:
        api_main, organism_mod = self._fresh(monkeypatch)
        monkeypatch.setenv("DHARMA_ORGANISM_ROOT", "1")
        # Isolate organism state writes from the ambient ~/.dharma
        monkeypatch.setattr(organism_mod, "dharma_state_dir", lambda *args: tmp_path)

        from dharma_swarm.swarm import SwarmManager

        swarm = api_main.get_swarm()
        assert isinstance(swarm, SwarmManager)

        organism = api_main._state.get("organism")
        assert organism is not None
        # Composition root: the Organism wraps the SAME SwarmManager instance
        assert organism.swarm is swarm
        # Discoverable via both the api seam and the organism module registry
        assert api_main.get_organism() is organism
        assert organism_mod.get_organism() is organism

        # StrangeLoop is production-reachable with a read-only status surface
        assert organism.strange_loop is not None
        sl_status = organism.strange_loop_status()
        assert sl_status["available"] is True
        assert "total_mutations" in sl_status

        # Idempotent: second call reuses both singletons
        assert api_main.get_swarm() is swarm
        assert api_main._state.get("organism") is organism

    def test_flag_on_organism_failure_is_nonfatal(self, monkeypatch) -> None:
        api_main, organism_mod = self._fresh(monkeypatch)
        monkeypatch.setenv("DHARMA_ORGANISM_ROOT", "1")

        class _Boom:
            def __init__(self, *args, **kwargs):
                raise RuntimeError("boom")

        monkeypatch.setattr(organism_mod, "Organism", _Boom)

        from dharma_swarm.swarm import SwarmManager

        swarm = api_main.get_swarm()  # must not raise
        assert isinstance(swarm, SwarmManager)
        assert "organism" not in api_main._state


def test_api_main_imports_without_api_keys(monkeypatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "api_keys" and name not in sys.modules:
            raise ModuleNotFoundError("No module named 'api_keys'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    for module_name in ("api.main", "api.routers.chat"):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("api.main")

    assert module.app.title == "DHARMA COMMAND"


def test_api_main_registers_dashboard_websocket_routes() -> None:
    import api.main as api_main

    websocket_paths = {
        route.path
        for route in api_main.app.routes
        if type(route).__name__ == "APIWebSocketRoute"
    }

    assert "/ws/agents" in websocket_paths
    assert "/api/ws/agents" in websocket_paths
    assert "/ws/chat/session/{session_id}" in websocket_paths


def test_api_main_fails_closed_for_blank_configured_key(monkeypatch) -> None:
    import api.main as api_main

    monkeypatch.setenv("DASHBOARD_API_KEY", "   ")
    response = TestClient(api_main.app).get(
        "/api/chat/status",
        headers={"Authorization": "Bearer "},
    )

    assert response.status_code == 503
    assert response.json()["error"] == "auth_misconfigured"
