"""Shared test fixtures for DHARMA SWARM."""

import os
from pathlib import Path

import pytest

pytest_plugins = (
    ("pytest_asyncio.plugin",)
    if os.getenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD") == "1"
    else ()
)

try:
    from hypothesis import settings, Verbosity

    # Configure Hypothesis profiles for property-based testing
    settings.register_profile("ci", max_examples=100, verbosity=Verbosity.verbose)
    settings.register_profile("dev", max_examples=20, verbosity=Verbosity.normal)
    settings.register_profile("deep", max_examples=1000, deadline=None)

    # Use dev profile by default, CI profile in GitHub Actions
    if os.getenv("CI"):
        settings.load_profile("ci")
    else:
        settings.load_profile("dev")
except ImportError:
    pass  # hypothesis not installed — property-based tests will be skipped


@pytest.fixture(autouse=True)
def _memory_quarantine_off(monkeypatch):
    """Default the quality-quarantine gate off under pytest.

    The gate's global default is shadow, which appends telemetry receipts
    under the caller's state dir — for tests that hit context.py readers
    with the default state_dir that would be the LIVE ~/.dharma witness
    file, contaminating the shadow denominators the enforce decision reads.
    Quarantine tests opt back in with monkeypatch.setenv.
    """
    monkeypatch.setenv("DHARMA_MEMORY_QUALITY_QUARANTINE", "off")


@pytest.fixture
def tmp_path_factory_custom(tmp_path):
    """Provide a temporary directory for test databases and state."""
    return tmp_path


@pytest.fixture
def state_dir(tmp_path):
    """Create a temporary .dharma state directory."""
    d = tmp_path / ".dharma"
    d.mkdir()
    (d / "memory").mkdir()
    (d / "tasks").mkdir()
    (d / "messages").mkdir()
    return d


@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary SQLite database path."""
    return tmp_path / "test.db"


@pytest.fixture(autouse=True)
def _restore_os_environ():
    """Snapshot and restore os.environ around every test.

    Library code raw-writes env vars (e.g. api_keys.py sets
    DHARMA_RUNTIME_ENV_LOADED), which monkeypatch cannot undo when the test
    never registered the write. Conftest-level autouse setup runs before
    per-test fixtures, so this teardown runs after monkeypatch's undo — the
    two compose.
    """
    snapshot = os.environ.copy()
    yield
    for k in list(os.environ):
        if k not in snapshot:
            del os.environ[k]
    for k, v in snapshot.items():
        if os.environ.get(k) != v:
            os.environ[k] = v


# Prefixes whose env vars leak runtime config into routing/scheduling tests.
_DGC_LEAK_PREFIXES = ("DGC_ROUTER_", "DGC_AGENT_")


@pytest.fixture(autouse=True)
def _isolate_dgc_env(monkeypatch):
    """Strip DGC_ROUTER_* and DGC_AGENT_* env vars so tests don't inherit runtime config."""
    for key in list(os.environ):
        if any(key.startswith(prefix) for prefix in _DGC_LEAK_PREFIXES):
            monkeypatch.delenv(key)


@pytest.fixture(autouse=True)
def _isolate_stigmergy(tmp_path, monkeypatch):
    """Redirect StigmergyStore to a tmpdir so tests never pollute ~/.dharma/stigmergy/marks.jsonl."""
    test_base = tmp_path / "_stigmergy_isolated"
    monkeypatch.setattr("dharma_swarm.stigmergy._DEFAULT_BASE", test_base)
    # Reset module-level singleton so each test gets a fresh store with the redirected path
    monkeypatch.setattr("dharma_swarm.stigmergy._default_store", None)


_REPO_ROOT_DHARMA = Path(__file__).resolve().parents[1] / ".dharma"


@pytest.fixture(autouse=True)
def _isolate_agent_state_dir(monkeypatch):
    """Block agent_runner's CWD-based state fallback from ever resolving to
    this checkout's real, ambient <repo>/.dharma/ (WP-0D: unisolated
    AgentConfig/AgentRunner/AgentPool tests were a suite-context-only
    timeout — the shared ontology.db that fallback resolves to grows with
    every such test run, until writes against it cross test-fast's per-test
    budget). Wraps the real resolver rather than reimplementing its
    metadata-first logic, so a test that deliberately chdirs elsewhere
    (e.g. to exercise the fallback itself against an isolated tmp_path)
    keeps seeing real, unmodified behavior — only the literal repo-root
    path is ever suppressed."""
    import dharma_swarm.agent_runner as _agent_runner_mod

    real_resolve = _agent_runner_mod._resolve_config_state_dir

    def _guarded(config):
        resolved = real_resolve(config)
        if resolved is not None and resolved.resolve() == _REPO_ROOT_DHARMA.resolve():
            return None
        return resolved

    monkeypatch.setattr(
        "dharma_swarm.agent_runner._resolve_config_state_dir", _guarded
    )


@pytest.fixture
def fast_gate():
    """Mock telos gate to return ALLOW instantly.

    Use in tests that don't care about gate behavior to avoid
    the ~10s overhead of the full reflective reroute cycle.
    """
    from unittest.mock import patch
    from dharma_swarm.models import GateCheckResult, GateDecision
    from dharma_swarm.telos_gates import ReflectiveGateOutcome

    allow = ReflectiveGateOutcome(
        result=GateCheckResult(
            decision=GateDecision.ALLOW,
            reason="All gates passed (test mock)",
        ),
    )
    with patch(
        "dharma_swarm.agent_runner.check_with_reflective_reroute",
        return_value=allow,
    ):
        yield allow
