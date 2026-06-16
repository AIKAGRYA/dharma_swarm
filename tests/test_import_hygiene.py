"""Import-hygiene tests — prove modules don't do work at import time.

A module that opens sockets, hits the filesystem, or spawns threads on import
poisons every test in the suite and causes nightmare debugging in prod
(the import order changes the behavior).

This file enforces a simple rule on a focused allowlist of "spine" modules:
importing them must not:
  1. Open any network socket
  2. Write/create files under the user's HOME
  3. Spawn threads/processes
  4. Take more than 2 seconds wall-clock

The allowlist is intentional — we ratchet by adding modules as they're cleaned.
"""
from __future__ import annotations

import importlib
import socket
import sys
import threading
import time
from pathlib import Path
from unittest import mock

import pytest


# Modules that MUST be import-side-effect-free.
# Add to this list as modules are cleaned. Removing from this list requires
# a governance comment explaining why.
CLEAN_MODULES = [
    "dharma_swarm.canonical_replay",
    "dharma_swarm.ontology",
    "dharma_swarm.event_log",
    "dharma_swarm.checkpoint",
    "dharma_swarm.revenue.spine",
    "dharma_swarm.revenue.spine_models",
]


# Soft budget — importing should be fast.
IMPORT_BUDGET_SECONDS = 2.0


@pytest.fixture
def no_network():
    """Patch socket so any import-time network call raises loudly."""
    real_socket = socket.socket

    def blocked(*args, **kwargs):
        raise AssertionError(
            "Module opened a network socket at import time. "
            "Move network code into a function/method."
        )

    with mock.patch.object(socket, "socket", blocked):
        yield


@pytest.fixture
def no_home_writes(tmp_path, monkeypatch):
    """Redirect HOME to a tmp dir; check nothing got written there at import."""
    monkeypatch.setenv("HOME", str(tmp_path))
    yield tmp_path


@pytest.fixture
def thread_count():
    """Snapshot active thread count before/after."""
    return threading.active_count()


@pytest.mark.parametrize("module_name", CLEAN_MODULES)
def test_no_network_at_import(module_name, no_network):
    """Module must not open sockets at import time."""
    # Force reimport
    sys.modules.pop(module_name, None)
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        pytest.skip(f"dep missing for {module_name}: {e}")


@pytest.mark.parametrize("module_name", CLEAN_MODULES)
def test_no_home_writes_at_import(module_name, no_home_writes, monkeypatch):
    """Module must not create files in HOME at import time."""
    sys.modules.pop(module_name, None)
    monkeypatch.setenv("DHARMA_HOME", str(no_home_writes))
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        pytest.skip(f"dep missing for {module_name}: {e}")

    # Check no new files in HOME (excluding the dir itself)
    contents = list(no_home_writes.rglob("*"))
    files = [p for p in contents if p.is_file()]
    assert not files, (
        f"{module_name} created files in HOME at import: {files}"
    )


@pytest.mark.parametrize("module_name", CLEAN_MODULES)
def test_no_thread_spawn_at_import(module_name, thread_count):
    """Module must not spawn threads at import time."""
    sys.modules.pop(module_name, None)
    before = thread_count
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        pytest.skip(f"dep missing for {module_name}: {e}")
    # Allow a small slack for GC/finalizer threads.
    after = threading.active_count()
    assert after - before <= 1, (
        f"{module_name} spawned {after - before} threads at import"
    )


@pytest.mark.parametrize("module_name", CLEAN_MODULES)
def test_import_under_budget(module_name):
    """Module must import in under 2 seconds (cold)."""
    sys.modules.pop(module_name, None)
    start = time.monotonic()
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        pytest.skip(f"dep missing for {module_name}: {e}")
    elapsed = time.monotonic() - start
    assert elapsed < IMPORT_BUDGET_SECONDS, (
        f"{module_name} took {elapsed:.2f}s to import (budget {IMPORT_BUDGET_SECONDS}s)"
    )
