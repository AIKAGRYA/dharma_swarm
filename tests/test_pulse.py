"""Tests for dharma_swarm.pulse living-layer heartbeat wiring."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import dharma_swarm.pulse as pulse


class _FakeStore:
    def __init__(self, density: int) -> None:
        self._density = density
        self.left_marks = []

    def density(self) -> int:
        return self._density

    async def leave_mark(self, mark):
        self.left_marks.append(mark)
        return "mark-id"


@pytest.fixture
def living_paths(tmp_path: Path, monkeypatch):
    state_dir = tmp_path / ".dharma"
    state_dir.mkdir(parents=True, exist_ok=True)
    living = state_dir / "living_state.json"
    monkeypatch.setattr(pulse, "STATE_DIR", state_dir)
    monkeypatch.setattr(pulse, "_LIVING_STATE_PATH", living)
    return living


def test_load_living_state_defaults_when_missing(living_paths: Path):
    state = pulse._load_living_state()
    assert state["last_dream_density"] == 0
    assert state["last_shakti_at"] == 0


def test_load_living_state_defaults_when_invalid_json(living_paths: Path):
    living_paths.write_text("not-json")
    state = pulse._load_living_state()
    assert state["last_dream_density"] == 0
    assert state["last_shakti_at"] == 0


def test_save_and_load_living_state_roundtrip(living_paths: Path):
    pulse._save_living_state({"last_dream_density": 72, "last_shakti_at": 123})
    state = pulse._load_living_state()
    assert state["last_dream_density"] == 72
    assert state["last_shakti_at"] == 123


@pytest.mark.asyncio
async def test_run_living_layers_triggers_dream_and_shakti(monkeypatch, living_paths: Path):
    store = _FakeStore(density=60)
    monkeypatch.setattr(pulse, "StigmergyStore", lambda: store)

    calls = {"dream": 0, "perceive": 0}

    class _FakeSubconscious:
        def __init__(self, stigmergy):
            assert stigmergy is store

        async def dream(self):
            calls["dream"] += 1
            return [SimpleNamespace(), SimpleNamespace()]

    class _FakeShakti:
        def __init__(self, stigmergy):
            assert stigmergy is store

        async def perceive(self, current_context: str = "", agent_role: str = "general"):
            calls["perceive"] += 1
            return [
                SimpleNamespace(
                    connection="dharma_swarm/pulse.py",
                    proposal=None,
                    observation="high salience signal",
                    salience=0.9,
                    impact_level="module",
                    energy=SimpleNamespace(value="maheshwari"),
                )
            ]

    monkeypatch.setattr(pulse, "SubconsciousStream", _FakeSubconscious)
    monkeypatch.setattr(pulse, "ShaktiLoop", _FakeShakti)

    summary = await pulse._run_living_layers("mechanistic", "pulse result")

    assert summary["dream_triggered"] is True
    assert summary["dream_associations"] == 2
    assert summary["shakti_perceptions"] == 1
    assert summary["shakti_escalations"] == 1
    assert calls["dream"] == 1
    assert calls["perceive"] == 1
    assert len(store.left_marks) == 1

    persisted = json.loads(living_paths.read_text())
    assert persisted["last_dream_density"] == 60
    assert persisted["last_shakti_at"] > 0


@pytest.mark.asyncio
async def test_run_living_layers_hysteresis_blocks_repeat_dream(monkeypatch, living_paths: Path):
    living_paths.write_text(json.dumps({"last_dream_density": 60, "last_shakti_at": 0}))

    store = _FakeStore(density=65)
    monkeypatch.setattr(pulse, "StigmergyStore", lambda: store)

    calls = {"dream": 0}

    class _FakeSubconscious:
        def __init__(self, stigmergy):
            pass

        async def dream(self):
            calls["dream"] += 1
            return [SimpleNamespace()]

    class _FakeShakti:
        def __init__(self, stigmergy):
            pass

        async def perceive(self, current_context: str = "", agent_role: str = "general"):
            return []

    monkeypatch.setattr(pulse, "SubconsciousStream", _FakeSubconscious)
    monkeypatch.setattr(pulse, "ShaktiLoop", _FakeShakti)

    monkeypatch.setenv("DGC_DREAM_HYSTERESIS", "10")
    summary = await pulse._run_living_layers("mechanistic", "pulse result")

    assert summary["dream_triggered"] is False
    assert summary["dream_associations"] == 0
    assert calls["dream"] == 0


@pytest.mark.asyncio
async def test_run_living_layers_respects_shakti_interval(monkeypatch, living_paths: Path):
    now = int(time.time())
    living_paths.write_text(json.dumps({"last_dream_density": 0, "last_shakti_at": now}))

    store = _FakeStore(density=10)
    monkeypatch.setattr(pulse, "StigmergyStore", lambda: store)

    class _FakeSubconscious:
        def __init__(self, stigmergy):
            pass

        async def dream(self):
            return [SimpleNamespace()]

    calls = {"perceive": 0}

    class _FakeShakti:
        def __init__(self, stigmergy):
            pass

        async def perceive(self, current_context: str = "", agent_role: str = "general"):
            calls["perceive"] += 1
            return []

    monkeypatch.setattr(pulse, "SubconsciousStream", _FakeSubconscious)
    monkeypatch.setattr(pulse, "ShaktiLoop", _FakeShakti)
    monkeypatch.setenv("DGC_SHAKTI_INTERVAL_SEC", "3600")

    summary = await pulse._run_living_layers("alignment", "pulse result")

    assert summary["dream_triggered"] is False
    assert summary["shakti_perceptions"] == 0
    assert calls["perceive"] == 0


@pytest.mark.asyncio
async def test_run_living_layers_handles_exceptions(monkeypatch, living_paths: Path):
    class _BrokenStore:
        def density(self) -> int:
            raise RuntimeError("boom")

    monkeypatch.setattr(pulse, "StigmergyStore", lambda: _BrokenStore())

    summary = await pulse._run_living_layers("alignment", "pulse result")
    assert summary["dream_triggered"] is False
    assert summary["shakti_perceptions"] == 0


def test_check_and_run_cron_jobs_runs_due_job_once_per_slot(tmp_path: Path, monkeypatch):
    fixed_now = datetime(2026, 3, 6, 4, 30, 10)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is None else fixed_now.astimezone(tz)

    monkeypatch.setattr(pulse, "datetime", _FixedDateTime)
    monkeypatch.setattr(pulse.Path, "home", lambda: tmp_path)

    state_dir = tmp_path / ".dharma"
    state_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pulse, "STATE_DIR", state_dir)

    cron_dir = tmp_path / "dharma_swarm"
    cron_dir.mkdir(parents=True, exist_ok=True)
    cron_file = cron_dir / "cron_jobs.json"
    cron_file.write_text(
        json.dumps(
            [
                {
                    "id": "morning_brief",
                    "name": "Morning Brief",
                    "trigger": "cron",
                    "enabled": True,
                    "schedule": {"hour": 4, "minute": 30},
                    "model": "sonnet",
                    "prompt": "say hi",
                }
            ]
        )
    )

    calls: list[tuple[str, str | None]] = []

    async def _fake_run(prompt: str, *, anthropic_model: str | None = None) -> str:
        calls.append((prompt, anthropic_model))
        return "ok"

    monkeypatch.setattr(pulse, "_run_pulse_completion", _fake_run)

    pulse._check_and_run_cron_jobs()
    pulse._check_and_run_cron_jobs()

    assert calls == [("say hi", "sonnet")]

    last_run = json.loads((state_dir / "cron_last_run.json").read_text())
    assert "morning_brief:2026-03-06T04:30" in last_run


def test_check_and_run_cron_jobs_ignores_invalid_job_payload(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(pulse.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(pulse, "STATE_DIR", tmp_path / ".dharma")

    cron_dir = tmp_path / "dharma_swarm"
    cron_dir.mkdir(parents=True, exist_ok=True)
    cron_file = cron_dir / "cron_jobs.json"
    cron_file.write_text(
        json.dumps(
            [
                {"id": "a", "trigger": "cron", "enabled": True, "schedule": {"hour": "x"}},
                {"id": "b", "trigger": "interval", "enabled": True},
                {"id": "c", "trigger": "cron", "enabled": False, "schedule": {"hour": 1}},
                "not-a-dict",
            ]
        )
    )

    called = {"n": 0}

    async def _fake_run(prompt: str, *, anthropic_model: str | None = None) -> str:
        called["n"] += 1
        return "ok"

    monkeypatch.setattr(pulse, "_run_pulse_completion", _fake_run)
    pulse._check_and_run_cron_jobs()
    assert called["n"] == 0


def test_check_and_run_cron_jobs_runs_due_interval_job_once(tmp_path: Path, monkeypatch):
    fixed_now = datetime(2026, 3, 6, 4, 30, 10)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is None else fixed_now.astimezone(tz)

    monkeypatch.setattr(pulse, "datetime", _FixedDateTime)
    monkeypatch.setattr(pulse.Path, "home", lambda: tmp_path)

    state_dir = tmp_path / ".dharma"
    state_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pulse, "STATE_DIR", state_dir)

    cron_dir = tmp_path / "dharma_swarm"
    cron_dir.mkdir(parents=True, exist_ok=True)
    cron_file = cron_dir / "cron_jobs.json"
    cron_file.write_text(
        json.dumps(
            [
                {
                    "id": "agni_check",
                    "name": "AGNI State Check",
                    "trigger": "interval",
                    "enabled": True,
                    "interval_seconds": 300,
                    "model": "haiku",
                    "prompt": "say hi",
                }
            ]
        )
    )

    calls: list[tuple[str, str | None]] = []

    async def _fake_run(prompt: str, *, anthropic_model: str | None = None) -> str:
        calls.append((prompt, anthropic_model))
        return "ok"

    monkeypatch.setattr(pulse, "_run_pulse_completion", _fake_run)

    pulse._check_and_run_cron_jobs()
    pulse._check_and_run_cron_jobs()

    assert calls == [("say hi", "haiku")]


# ---------------------------------------------------------------------------
# Execute step: the canonical Max-first fallback chain (routing-canon W1)
# ---------------------------------------------------------------------------


def _forbid_claude_headless(monkeypatch) -> None:
    def _never(*a, **k):
        raise AssertionError("run_claude_headless must not be invoked from the pulse execute path")

    monkeypatch.setattr(pulse, "run_claude_headless", _never)


def _chain_ok(captured: dict | None = None, content: str = "STRIKE: bury corpse health json"):
    from dharma_swarm.models import LLMResponse, ProviderType
    from dharma_swarm.runtime_provider import RuntimeProviderConfig

    async def _ok(**kwargs):
        if captured is not None:
            captured.update(kwargs)
        return (
            LLMResponse(content=content, model="glm-5.2:cloud", provider="ollama"),
            RuntimeProviderConfig(
                provider=ProviderType.OLLAMA,
                default_model="glm-5.2:cloud",
                available=True,
            ),
        )

    return _ok


def _chain_boom(**kwargs):
    raise RuntimeError("claude exited 1: Credit balance is too low")


async def _chain_boom_async(**kwargs):
    _chain_boom(**kwargs)


@pytest.mark.asyncio
async def test_run_pulse_completion_returns_chain_content(monkeypatch, capsys):
    monkeypatch.setattr(pulse, "complete_via_preferred_runtime_providers", _chain_ok())
    _forbid_claude_headless(monkeypatch)

    text = await pulse._run_pulse_completion("pulse please")

    assert text == "STRIKE: bury corpse health json"
    assert "[pulse] provider=ollama model=glm-5.2:cloud" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_run_pulse_completion_chain_exception_is_error_not_claude_fallback(monkeypatch):
    monkeypatch.setattr(pulse, "complete_via_preferred_runtime_providers", _chain_boom_async)
    _forbid_claude_headless(monkeypatch)

    text = await pulse._run_pulse_completion("pulse please")

    assert text.startswith("ERROR:")
    assert "Credit balance is too low" in text


@pytest.mark.asyncio
async def test_run_pulse_completion_order_is_max_first_then_funded_lanes(monkeypatch):
    from dharma_swarm.models import ProviderType
    from dharma_swarm.runtime_provider import PREFERRED_LOW_COST_RUNTIME_PROVIDERS

    captured: dict = {}
    monkeypatch.setattr(pulse, "complete_via_preferred_runtime_providers", _chain_ok(captured))
    _forbid_claude_headless(monkeypatch)

    await pulse._run_pulse_completion("pulse please")

    order = captured["provider_order"]
    assert order[0] is ProviderType.ANTHROPIC
    assert tuple(order[1:]) == tuple(PREFERRED_LOW_COST_RUNTIME_PROVIDERS)
    assert set(order) != {ProviderType.OPENROUTER, ProviderType.OPENROUTER_FREE}
    assert captured["anthropic_model"]
    assert "sonnet" not in captured["anthropic_model"]


@pytest.mark.asyncio
async def test_run_pulse_completion_cron_model_override_hits_anthropic_lane_only(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(pulse, "complete_via_preferred_runtime_providers", _chain_ok(captured))
    _forbid_claude_headless(monkeypatch)

    await pulse._run_pulse_completion("say hi", anthropic_model="sonnet")

    assert captured["anthropic_model"] == "sonnet"
    assert captured.get("openrouter_model") is None


@pytest.mark.asyncio
async def test_run_pulse_completion_empty_content_is_error(monkeypatch):
    monkeypatch.setattr(pulse, "complete_via_preferred_runtime_providers", _chain_ok(content="   "))
    _forbid_claude_headless(monkeypatch)

    text = await pulse._run_pulse_completion("pulse please")

    assert text.startswith("ERROR:")


class _Breaker:
    def __init__(self) -> None:
        self.successes = 0
        self.failures = 0

    @property
    def is_broken(self) -> bool:
        return False

    def record_failure(self) -> bool:
        self.failures += 1
        return False

    def record_success(self) -> None:
        self.successes += 1


class _FakeThreadManager:
    def __init__(self, config, state_dir) -> None:
        self._current_thread = "mechanistic"
        self.rotations = 0

    @property
    def current_thread(self) -> str:
        return self._current_thread

    def check_focus_override(self, state_dir):
        return None

    def check_inject_override(self, state_dir):
        return None

    def record_contribution(self, thread=None) -> None:
        pass

    def rotate(self) -> str:
        self.rotations += 1
        return self._current_thread


@pytest.fixture
def pulse_harness(tmp_path: Path, monkeypatch):
    """Isolate pulse() to its execute+score seam: no I/O, no gates, no living layers."""
    from dharma_swarm.daemon_config import DaemonConfig

    monkeypatch.setattr(pulse, "STATE_DIR", tmp_path / ".dharma")
    monkeypatch.setattr(pulse, "ThreadManager", _FakeThreadManager)
    monkeypatch.setattr(pulse, "read_agni_state", lambda: {})
    monkeypatch.setattr(pulse, "read_memory_context", lambda: "")
    monkeypatch.setattr(pulse, "read_trishula_inbox", lambda: "")
    monkeypatch.setattr(pulse, "read_manifest", lambda: "")
    monkeypatch.setattr(
        pulse,
        "check_with_reflective_reroute",
        lambda **kwargs: SimpleNamespace(
            result=SimpleNamespace(decision=SimpleNamespace(value="allow"), reason=""),
            attempts=0,
        ),
    )

    async def _noop_store(result, thread):
        return None

    async def _noop_living(thread, result):
        return {}

    monkeypatch.setattr(pulse, "_store_pulse_result", _noop_store)
    monkeypatch.setattr(pulse, "_run_living_layers", _noop_living)
    monkeypatch.setattr(pulse, "append_pulse_log", lambda *a, **k: None)
    _forbid_claude_headless(monkeypatch)

    breaker = _Breaker()
    cfg = DaemonConfig(quiet_hours=[], circuit_breaker=breaker)
    return cfg, breaker


def test_pulse_chain_success_records_success_and_returns_content(pulse_harness, monkeypatch):
    cfg, breaker = pulse_harness
    monkeypatch.setattr(pulse, "complete_via_preferred_runtime_providers", _chain_ok())

    result = pulse.pulse(cfg)

    assert result == "STRIKE: bury corpse health json"
    assert breaker.successes == 1
    assert breaker.failures == 0


def test_pulse_chain_exception_records_failure_and_returns_error(pulse_harness, monkeypatch):
    cfg, breaker = pulse_harness
    monkeypatch.setattr(pulse, "complete_via_preferred_runtime_providers", _chain_boom_async)

    result = pulse.pulse(cfg)

    assert result.startswith("ERROR:")
    assert breaker.failures == 1
    assert breaker.successes == 0


@pytest.mark.parametrize(
    "provider_text",
    [
        "Error (rc=1): Credit balance is too low",
        "error: something",
        "TIMEOUT: exceeded limit",
        "timeout: exceeded limit",
    ],
)
def test_pulse_regression_pin_provider_error_text_never_scores_success(
    pulse_harness, monkeypatch, provider_text
):
    cfg, breaker = pulse_harness

    async def _lane_text(prompt, *, anthropic_model=None):
        return provider_text

    monkeypatch.setattr(pulse, "_run_pulse_completion", _lane_text)

    result = pulse.pulse(cfg)

    assert result == provider_text
    assert breaker.successes == 0
    assert breaker.failures == 1


def test_pulse_regression_pin_provider_error_content_via_chain_never_scores_success(
    pulse_harness, monkeypatch
):
    cfg, breaker = pulse_harness
    monkeypatch.setattr(
        pulse,
        "complete_via_preferred_runtime_providers",
        _chain_ok(content="Error (rc=1): Credit balance is too low"),
    )

    pulse.pulse(cfg)

    assert breaker.successes == 0
    assert breaker.failures == 1


@pytest.mark.parametrize("text", ["SKIP: no key", "skip: lower", "TELOS BLOCK: nope"])
def test_pulse_skip_and_telos_block_never_record_success(pulse_harness, monkeypatch, text):
    cfg, breaker = pulse_harness

    async def _lane_text(prompt, *, anthropic_model=None):
        return text

    monkeypatch.setattr(pulse, "_run_pulse_completion", _lane_text)

    pulse.pulse(cfg)

    assert breaker.successes == 0


def test_pulse_execute_path_never_invokes_run_claude_headless(pulse_harness, monkeypatch):
    cfg, breaker = pulse_harness
    monkeypatch.setattr(pulse, "complete_via_preferred_runtime_providers", _chain_boom_async)

    result = pulse.pulse(cfg)

    assert result.startswith("ERROR:")


@pytest.mark.parametrize(
    "text",
    ["ERROR: x", "error: x", "TIMEOUT: x", "SKIP: y", "TELOS BLOCK: z", "telos block: z"],
)
def test_cmd_pulse_exits_nonzero_on_failure_prefixes(monkeypatch, capsys, text):
    from dharma_swarm.terminal_commands import diagnostics

    monkeypatch.setattr(pulse, "pulse", lambda: text)

    with pytest.raises(SystemExit) as excinfo:
        diagnostics.cmd_pulse()

    assert excinfo.value.code == 1
    assert text in capsys.readouterr().out


def test_cmd_pulse_returns_normally_on_content(monkeypatch, capsys):
    from dharma_swarm.terminal_commands import diagnostics

    monkeypatch.setattr(pulse, "pulse", lambda: "STRIKE: one concrete action")

    assert diagnostics.cmd_pulse() is None
    assert "STRIKE: one concrete action" in capsys.readouterr().out
