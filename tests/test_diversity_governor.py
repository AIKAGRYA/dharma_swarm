from __future__ import annotations

from dharma_swarm.diversity_governor import DiversityGovernor, DiversitySnapshot
from dharma_swarm.models import ProviderType, Task


def test_reorder_providers_demotes_ollama_under_monoculture(monkeypatch) -> None:
    governor = DiversityGovernor()
    monkeypatch.setattr(
        governor,
        "snapshot",
        lambda: DiversitySnapshot(
            window_hours=1.0,
            total_calls=100,
            top_model="glm-5",
            top_model_share=0.72,
            top_provider="ollama",
            top_provider_share=0.72,
            inward_share=0.61,
            unknown_share=0.0,
            active_sources=("sleep_time_agent", "swarm.coordination_synthesis"),
        ),
    )

    reordered, reasons = governor.reorder_providers(
        [ProviderType.OLLAMA, ProviderType.OPENROUTER, ProviderType.NVIDIA_NIM],
        default_model_hints={
            ProviderType.OLLAMA: "glm-5:cloud",
            ProviderType.OPENROUTER: "moonshotai/kimi-k2.5",
            ProviderType.NVIDIA_NIM: "nvidia/llama-3.1-nemotron-ultra-253b-v1",
        },
    )

    assert reordered[0] == ProviderType.OPENROUTER
    assert reordered[-1] == ProviderType.OLLAMA
    assert "diversity_promote_challenger_lanes" in reasons


def test_reorder_ready_tasks_demotes_internal_tasks_when_inward_heavy(monkeypatch) -> None:
    governor = DiversityGovernor()
    monkeypatch.setattr(
        governor,
        "snapshot",
        lambda: DiversitySnapshot(
            window_hours=1.0,
            total_calls=20,
            top_model="glm-5",
            top_model_share=0.6,
            top_provider="ollama",
            top_provider_share=0.6,
            inward_share=0.7,
            unknown_share=0.1,
            active_sources=("sleep_time_agent",),
        ),
    )

    tasks = [
        Task(id="t-inward", title="knowledge extraction follow-up", metadata={"source": "sleep_time_agent"}),
        Task(id="t-neutral", title="Review staging", metadata={}),
        Task(id="t-outward", title="Publish artifact report", metadata={"artifact_contract": True}),
    ]

    reordered, reasons = governor.reorder_ready_tasks(tasks)

    assert [task.id for task in reordered] == ["t-outward", "t-neutral", "t-inward"]
    assert "diversity_demote_internal_tasks" in reasons


# ---------------------------------------------------------------------------
# Calibration fixes (2026-04-14): cascading window + lowered threshold.
# ---------------------------------------------------------------------------


def test_monoculture_threshold_catches_glm_natural_share() -> None:
    """GLM's observed 24h share is ~0.46-0.53. Old default (0.55) missed it.

    New default 0.40 must fire for anything in that band.
    """
    snap = DiversitySnapshot(
        window_hours=6.0,
        total_calls=46,
        top_model="glm-5",
        top_model_share=0.457,  # observed 6h reality
        top_provider="ollama",
        top_provider_share=0.522,
        inward_share=0.870,
        unknown_share=0.0,
        active_sources=("swarm.coordination_synthesis", "sleep_time_agent"),
    )
    assert snap.model_monoculture is True, (
        "GLM at natural 46% must trip monoculture under new calibration"
    )


def test_monoculture_threshold_respects_env_override(monkeypatch) -> None:
    monkeypatch.setenv("DGC_DIVERSITY_MAX_MODEL_SHARE", "0.60")
    snap = DiversitySnapshot(
        window_hours=6.0, total_calls=46,
        top_model="glm-5", top_model_share=0.457,
        top_provider="ollama", top_provider_share=0.522,
        inward_share=0.870, unknown_share=0.0, active_sources=(),
    )
    assert snap.model_monoculture is False


def test_cascading_window_falls_back_on_empty_recent_hour(monkeypatch) -> None:
    """Bursty traffic: 1h empty → cascade to 6h with data."""
    calls_by_window: dict[float, dict] = {
        1.0: {"calls": 0, "by_model": {}, "by_provider": {}, "by_source": {}},
        6.0: {
            "calls": 46,
            "by_model": {"glm-5": {"calls": 21}, "llama-3.3-70b": {"calls": 20}},
            "by_provider": {"ollama": {"calls": 24}, "openrouter": {"calls": 20}},
            "by_source": {"swarm.coordination_synthesis": {"calls": 24}},
        },
        24.0: {"calls": 157, "by_model": {}, "by_provider": {}, "by_source": {}},
    }

    def fake_summarize(window: float) -> dict:
        return calls_by_window[window]

    monkeypatch.setattr(
        "dharma_swarm.diversity_governor.summarize_costs", fake_summarize,
    )
    governor = DiversityGovernor()  # default window 1.0
    snap = governor.snapshot()
    assert snap.total_calls == 46
    assert snap.window_hours == 6.0  # cascade landed on 6h
    assert snap.top_model == "glm-5"


def test_cascading_window_uses_primary_when_non_empty(monkeypatch) -> None:
    """Don't fall back unnecessarily — if 1h has data, use it."""
    calls_by_window: dict[float, dict] = {
        1.0: {
            "calls": 5,
            "by_model": {"kimi-k2.5": {"calls": 5}},
            "by_provider": {"ollama": {"calls": 5}},
            "by_source": {"pulse": {"calls": 5}},
        },
        6.0: {"calls": 100, "by_model": {"glm-5": {"calls": 100}}, "by_provider": {}, "by_source": {}},
    }
    monkeypatch.setattr(
        "dharma_swarm.diversity_governor.summarize_costs",
        lambda w: calls_by_window.get(w, {"calls": 0}),
    )
    governor = DiversityGovernor()
    snap = governor.snapshot()
    assert snap.window_hours == 1.0
    assert snap.top_model == "kimi-k2.5"


def test_cascading_window_all_empty_stays_on_primary(monkeypatch) -> None:
    """Truly idle daemon — cascade exhausts, governor returns a no-data
    snapshot on the configured primary window."""
    monkeypatch.setattr(
        "dharma_swarm.diversity_governor.summarize_costs",
        lambda w: {"calls": 0, "by_model": {}, "by_provider": {}, "by_source": {}},
    )
    governor = DiversityGovernor(window_hours=2.0)
    snap = governor.snapshot()
    assert snap.total_calls == 0
    assert snap.window_hours == 2.0


def test_cascading_window_env_override(monkeypatch) -> None:
    monkeypatch.setenv("DGC_DIVERSITY_WINDOW_CASCADE", "2,48")
    calls_by_window: dict[float, dict] = {
        1.0: {"calls": 0, "by_model": {}, "by_provider": {}, "by_source": {}},
        2.0: {"calls": 0, "by_model": {}, "by_provider": {}, "by_source": {}},
        48.0: {
            "calls": 500,
            "by_model": {"minimax-m2.7": {"calls": 500}},
            "by_provider": {"ollama": {"calls": 500}},
            "by_source": {"pulse": {"calls": 500}},
        },
    }
    monkeypatch.setattr(
        "dharma_swarm.diversity_governor.summarize_costs",
        lambda w: calls_by_window.get(w, {"calls": 0, "by_model": {}, "by_provider": {}, "by_source": {}}),
    )
    governor = DiversityGovernor()
    snap = governor.snapshot()
    assert snap.window_hours == 48.0
    assert snap.top_model == "minimax-m2.7"
