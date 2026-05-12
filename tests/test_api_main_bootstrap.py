from __future__ import annotations

import builtins
import importlib
import sys


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
    route_paths = {getattr(route, "path", "") for route in module.app.routes}
    assert "/api/viz/snapshot" in route_paths
    assert "/api/viz/events" in route_paths
    assert "/api/viz/timeline" in route_paths
