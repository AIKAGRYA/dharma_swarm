"""Multi-tier deepen pipeline tests (deterministic: LLM + recall + research mocked)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import dharma_swarm.idea_spark.deepen as deepen_mod
from dharma_swarm.idea_spark.deepen import deepen_idea
from dharma_swarm.idea_spark.deepen_routing import DeepenLLMResult
from dharma_swarm.semantic_gravity import ResearchAnnotation, ResearchConnectionType

SPARK = "Validate gap-scan reference counts against the actual concepts directory before declaring gaps."
CORR = "corr_deepen_test"


def _patch_nonllm(monkeypatch):
    monkeypatch.setattr(
        deepen_mod,
        "_recall_internal",
        lambda text, limit=8: ([{"source": "wiki", "label": "gap-scan concept"}], {"wiki": 1, "catalytic": 0}, []),
    )

    def fake_research(concept_id, query, *, max_results=4, backend="arxiv"):
        return [
            ResearchAnnotation(
                concept_id=concept_id,
                connection_type=ResearchConnectionType.VALIDATION,
                external_source="arxiv",
                citation="http://arxiv.org/abs/x",
                summary="related paper",
                field="arxiv",
            )
        ]

    monkeypatch.setattr(deepen_mod, "live_research_annotations", fake_research)


def test_deepen_happy_path_when_floor_provider_available(monkeypatch):
    _patch_nonllm(monkeypatch)

    async def fake_deepen_llm(messages, system="", *, max_tokens=2048, temperature=0.4):
        return DeepenLLMResult(
            text="QUESTION: how to validate gaps?\nQUERIES:\n- gap validation",
            provider="GOOGLE_AI",
            model="gemini-2.5-flash",
        )

    monkeypatch.setattr(deepen_mod, "deepen_llm", fake_deepen_llm)

    db = Path(tempfile.mkdtemp()) / "mem.db"
    state = Path(tempfile.mkdtemp())
    rep = deepen_idea(SPARK, CORR, state_root=state, reseed=True, reseed_db_path=db)

    assert rep.floor_blocked is False
    assert rep.internal_hits == 1  # internal-first recall ran
    assert rep.external_sources == 1  # external research ran
    assert rep.reframed_question  # LLM reframe parsed
    assert rep.deepened_text  # LLM deepen produced text
    assert rep.reseeded_concepts >= 1  # compounded into the UnifiedIndex
    assert Path(rep.graph_path).exists()
    assert Path(rep.report_path).exists()


def test_deepen_floor_blocked_still_completes_nonllm_tiers(monkeypatch):
    _patch_nonllm(monkeypatch)

    async def raising_deepen_llm(*a, **k):
        raise RuntimeError("no >=floor provider reachable")

    monkeypatch.setattr(deepen_mod, "deepen_llm", raising_deepen_llm)

    db = Path(tempfile.mkdtemp()) / "mem.db"
    state = Path(tempfile.mkdtemp())
    rep = deepen_idea(SPARK, CORR, state_root=state, reseed=True, reseed_db_path=db)

    assert rep.floor_blocked is True  # honest: did NOT degrade below the Kimi floor
    assert rep.deepened_text == ""
    assert rep.internal_hits == 1  # non-LLM tiers still completed
    assert rep.external_sources == 1
    assert rep.reseeded_concepts >= 1
    assert any("floor-blocked" in n for n in rep.notes)
