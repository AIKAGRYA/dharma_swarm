"""Multi-tier idea DEEPEN pipeline — more than a single web run.

Stages (internal-first, then external, then synthesize, then reseed):
  D0 recall   — internal prior art FIRST (Karpathy wiki + catalytic graph via
                chetana.graph_unifier) before any external call.
  D1 reframe  — LLM (>=Kimi floor) turns the spark + internal context into a
                sharp question + search queries.
  D2 research — real external sources (web_search) attached as grounded citations.
  D3 deepen   — LLM (>=Kimi floor) rewrites the idea deeper, citing prior art.
  RECORD      — an isolated concept-graph receipt (NEVER the shared canon).
  RESEED      — index into the UnifiedIndex so the idea compounds (agent-
                retrievable + salience uptake) instead of being lost.

All LLM stages route ONLY through the Kimi-floored single router
(``deepen_routing.deepen_llm``). If no >=floor provider is reachable, those
stages are honestly marked ``floor_blocked`` (NEVER silently degraded to a
sub-floor model); the non-LLM tiers still complete so the run is never wasted.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dharma_swarm.semantic_gravity import ConceptGraph

from .deepen_routing import deepen_llm
from .paths import idea_spark_root
from .see_adapter import inject_spark, live_research_annotations, spark_to_node


@dataclass
class DeepenReport:
    correlation_id: str
    node_id: str
    internal_hits: int
    internal_coverage: dict
    external_sources: int
    reframed_question: str
    deepened_text: str
    floor_blocked: bool
    llm_provider: str
    reseeded_concepts: int
    graph_path: str
    report_path: str = ""
    notes: list = field(default_factory=list)


def _recall_internal(text: str, *, limit: int = 8):
    """Internal-first recall over the in-house substrates that work today."""
    try:
        from dharma_swarm.chetana.graph_unifier import query as graph_query

        res = graph_query(text, sources=["wiki", "catalytic"], limit_per_source=limit)
        hits = [{"source": h.source, "label": h.label} for h in res.hits[: limit * 2]]
        return hits, dict(res.coverage), list(res.notes)
    except Exception as exc:  # pragma: no cover - environment dependent
        return [], {}, [f"internal recall failed: {exc}"]


async def _llm(prompt: str, system: str, *, max_tokens: int) -> tuple[str, str]:
    """One floored LLM call. Returns ('','') if no >=floor provider is reachable."""
    try:
        r = await deepen_llm([{"role": "user", "content": prompt}], system=system, max_tokens=max_tokens)
        return r.text, r.provider
    except Exception:
        return "", ""  # floor-blocked: NEVER degrade below the Kimi floor


def deepen_idea(
    text: str,
    correlation_id: str,
    *,
    authority_level: str = "proposal",
    state_root: Path | None = None,
    max_sources: int = 4,
    live_research: bool = True,
    reseed: bool = True,
    reseed_db_path: Path | str | None = None,
) -> DeepenReport:
    notes: list[str] = []

    # D0 — internal-first recall
    internal_hits, coverage, rnotes = _recall_internal(text)
    notes.extend(rnotes)
    internal_ctx = "\n".join(f"- [{h['source']}] {h['label']}" for h in internal_hits[:12]) or "(no internal prior art found)"

    # D1 — reframe (LLM, floored)
    reframe_prompt = (
        f"Operator idea spark:\n{text}\n\nInternal prior art already in our system:\n{internal_ctx}\n\n"
        "Reframe into ONE sharp research question, then 2-3 web search queries.\n"
        "Format:\nQUESTION: <one line>\nQUERIES:\n- <q1>\n- <q2>"
    )
    reframed, prov1 = asyncio.run(_llm(reframe_prompt, "You are a rigorous research lead. Be concise.", max_tokens=400))
    floor_blocked = not reframed
    question = ""
    for line in (reframed or "").splitlines():
        if line.strip().upper().startswith("QUESTION:"):
            question = line.split(":", 1)[1].strip()
            break

    # D2 — external research (real sources)
    node = spark_to_node(text, correlation_id, authority_level=authority_level)
    ext_anns = live_research_annotations(node.id, text, max_results=max_sources) if live_research else []
    ext_ctx = "\n".join(f"- {a.summary} [{a.citation}]" for a in ext_anns[:max_sources]) or "(no external sources retrieved)"

    # D3 — deepen synthesis (LLM, floored)
    deepen_prompt = (
        f"Idea: {text}\n\nInternal prior art:\n{internal_ctx}\n\nExternal sources:\n{ext_ctx}\n\n"
        "Rewrite this idea deeper and more precise: what it really is, why it matters now, how it connects to the "
        "prior art above, and the single sharpest next experiment. 1-2 paragraphs."
    )
    deepened, prov2 = asyncio.run(_llm(deepen_prompt, "You deepen ideas with rigor and cite the given sources.", max_tokens=1200))
    if not deepened:
        floor_blocked = True
    provider = prov2 or prov1 or ""

    # RECORD — isolated concept-graph receipt (never the shared canon)
    base = idea_spark_root(state_root) / "deepened"
    base.mkdir(parents=True, exist_ok=True)
    graph_path = base / f"{correlation_id}.json"
    graph = ConceptGraph()
    inject_spark(graph, node)
    for ann in ext_anns:
        graph.add_annotation(ann)
    asyncio.run(graph.save(graph_path))

    # RESEED — into the UnifiedIndex so the idea compounds (agent-retrievable + salience uptake)
    reseeded = 0
    if reseed:
        try:
            from dharma_swarm.semantic_memory_bridge import index_concepts_into_memory

            reseeded = index_concepts_into_memory(graph, db_path=reseed_db_path)
        except Exception as exc:
            notes.append(f"reseed skipped: {exc}")

    if floor_blocked:
        notes.append(
            "LLM deepen stages floor-blocked: no >=Kimi-floor provider reachable "
            "(fund OpenRouter for kimi-k2.6, or raise gemini/ollama quota). Non-LLM tiers completed."
        )

    report = DeepenReport(
        correlation_id=correlation_id,
        node_id=node.id,
        internal_hits=len(internal_hits),
        internal_coverage=coverage,
        external_sources=len(ext_anns),
        reframed_question=question,
        deepened_text=deepened,
        floor_blocked=floor_blocked,
        llm_provider=provider,
        reseeded_concepts=reseeded,
        graph_path=str(graph_path),
    )
    report_path = base / f"{correlation_id}.report.json"
    report_path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    report.report_path = str(report_path)
    report.notes = notes
    return report
