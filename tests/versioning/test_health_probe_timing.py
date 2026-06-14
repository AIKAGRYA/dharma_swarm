import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "health_probe_timing",
    Path(__file__).resolve().parents[2] / "scripts" / "runtime" / "health_probe_timing.py",
)
hpt = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(hpt)


def test_run_emits_valid_shape_against_dead_port():
    # Nothing listening on this port -> all timeouts, but shape must be valid.
    result = hpt.run("127.0.0.1", 1, "/health", samples=3, timeout=0.2)
    assert result["samples"] == 3
    assert result["timeout_count"] == 3
    assert result["timeout_rate"] == 1.0
    assert "latency_ms_p50" in result and "latency_ms_p99" in result
    assert result["target"].startswith("http://127.0.0.1:1")


def test_probe_once_returns_tuple_on_failure():
    ok, elapsed = hpt.probe_once("127.0.0.1", 1, "/health", timeout=0.2)
    assert ok is False
    assert isinstance(elapsed, float)
