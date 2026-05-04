from __future__ import annotations

import builtins
import importlib
import sys


_SENTINEL = object()


def test_api_main_imports_without_api_keys(monkeypatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "api_keys" and name not in sys.modules:
            raise ModuleNotFoundError("No module named 'api_keys'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    module_names = ("api.main", "api.routers.chat")
    saved_modules = {name: sys.modules.get(name) for name in module_names}
    api_pkg = sys.modules.get("api")
    routers_pkg = sys.modules.get("api.routers")
    saved_api_main = getattr(api_pkg, "main", _SENTINEL) if api_pkg else _SENTINEL
    saved_router_chat = (
        getattr(routers_pkg, "chat", _SENTINEL) if routers_pkg else _SENTINEL
    )

    try:
        for module_name in module_names:
            sys.modules.pop(module_name, None)

        module = importlib.import_module("api.main")
    finally:
        for module_name, saved_module in saved_modules.items():
            if saved_module is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = saved_module
        if api_pkg is not None:
            if saved_api_main is _SENTINEL:
                try:
                    delattr(api_pkg, "main")
                except AttributeError:
                    pass
            else:
                setattr(api_pkg, "main", saved_api_main)
        if routers_pkg is not None:
            if saved_router_chat is _SENTINEL:
                try:
                    delattr(routers_pkg, "chat")
                except AttributeError:
                    pass
            else:
                setattr(routers_pkg, "chat", saved_router_chat)

    assert module.app.title == "DHARMA COMMAND"
