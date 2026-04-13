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
