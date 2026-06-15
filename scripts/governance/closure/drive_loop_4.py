#!/usr/bin/env python3
"""Loop 4 (Consolidation / Memory) closure driver — run the REAL consolidation
pipeline over REAL Loop-1 agent outputs.

Loop 4 consumes Loop 1 output (the text a real provider produced for a task) and
consolidates it into searchable memory. This driver closes the fed-cascade edge
WITHOUT touching the production daemon, the live runtime.db, or archive fitness.

Loop 4 trace (CYBERNETIC_LOOP_MAP.md §"Loop 4: Consolidation Loop (Memory)"):
  SENSE     read recent agent outputs (Loop-1 completed delegation_runs)
  ACT       SleepTimeAgent.consolidate_knowledge(): KnowledgeExtractor (REAL LLM)
            decomposes each output into Propositions (facts) + Prescriptions
            (skills) and stores them in a KnowledgeStore.
  EVALUATE  dedup / scoring against outcome (real provider tokens -> success).
  ADAPT     consolidated units become searchable memory (provenance_event_id =
            the real Loop-1 run_id) and emit a consolidation_cycle receipt that
            feeds the next agent's context.

It does the following, all on REAL data:

  1. Drives N real FREE-provider dispatches with KNOWLEDGE-BEARING prompts (not
     "reply one word") through dharma_swarm.spine.invoke.invoke_agent, persisting
     Loop-1-shaped EvidenceReceipts to a SCOPED delegation_runs db. The receipt
     carries the REAL provider output text in attributes.agent_output so there is
     genuine knowledge to consolidate. (No mock provider anywhere.)
  2. SENSE: reads those real completed rows back from the scoped db.
  3. ACT/EVALUATE: runs the REAL SleepTimeAgent.consolidate_knowledge with a REAL
     live FREE provider as the extraction llm_client, once per real Loop-1 output,
     tagging every extracted unit with provenance_event_id = the real run_id, into
     a SCOPED KnowledgeStore db.
  4. ADAPT: emits ONE consolidation_cycle receipt (the memory-adapt payload that
     feeds the next agent's context) to a scoped dir, referencing the same real
     run_ids. This is an INTERNAL memory write, NOT an archive-fitness write
     (One Wire stays intact — nothing here touches archive.jsonl).

Run:
  DHARMA_SPINE_DISPATCH=1 \
    LC_LOOP4_RUNTIME_DB=/tmp/lc_loop4_runtime.db \
    LC_LOOP4_KNOWLEDGE_DB=/tmp/lc_loop4_knowledge.db \
    LC_LOOP4_DIR=/tmp/lc_loop4 \
    python3 scripts/governance/closure/drive_loop_4.py
Then:
  LC_LOOP4_RUNTIME_DB=/tmp/lc_loop4_runtime.db \
    LC_LOOP4_KNOWLEDGE_DB=/tmp/lc_loop4_knowledge.db \
    LC_LOOP4_DIR=/tmp/lc_loop4 \
    python3 scripts/governance/closure/check_loop_4.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from dharma_swarm.models import LLMRequest, ProviderType  # noqa: E402
from dharma_swarm.runtime_provider import (  # noqa: E402
    create_runtime_provider,
    resolve_runtime_provider_config,
)
from dharma_swarm.sleep_time_agent import SleepTimeAgent  # noqa: E402
from dharma_swarm.knowledge_units import KnowledgeStore  # noqa: E402
from dharma_swarm.spine.invoke import invoke_agent  # noqa: E402
from dharma_swarm.spine.receipt import EvidenceReceipt  # noqa: E402
from dharma_swarm.spine.routing import RoutingDecision  # noqa: E402

RUNTIME_DB = os.environ.get("LC_LOOP4_RUNTIME_DB", f"/tmp/lc_loop4_runtime_{int(time.time())}.db")
KNOWLEDGE_DB = os.environ.get("LC_LOOP4_KNOWLEDGE_DB", f"/tmp/lc_loop4_knowledge_{int(time.time())}.db")
LOOP4_DIR = Path(os.environ.get("LC_LOOP4_DIR", f"/tmp/lc_loop4_{int(time.time())}"))

BAD_PROVIDERS = {"", "orchestrator", "mock", "stub", "fixture", "test", "none"}

# FREE-first decorrelated candidates (live-confirmed 2026-06-16). gemini-2.5-flash
# truncates to ~6 output tokens on these prompts (too thin to consolidate), so the
# source set uses the two ollama_cloud families that reliably return substantive,
# knowledge-bearing prose: glm-5 and deepseek-v3.2 (distinct model families).
FREE_CANDIDATES: list[tuple[ProviderType, str | None]] = [
    (ProviderType.OLLAMA, "glm-5"),
    (ProviderType.OLLAMA, "deepseek-v3.2"),
    (ProviderType.OLLAMA, "glm-5"),
    (ProviderType.OLLAMA, "deepseek-v3.2"),
]

# Knowledge-bearing prompts: a real provider returns text that genuinely contains
# extractable facts (Propositions) and recommendations (Prescriptions).
TASKS = [
    "In two sentences, state one concrete fact about how SQLite WAL mode improves "
    "concurrent read performance, and recommend one practice for using it safely.",
    "In two sentences, state one fact about why decorrelated agent errors cancel in "
    "an ensemble, and recommend one way to preserve agent diversity.",
    "In two sentences, state one fact about how exponential backoff reduces retry "
    "storms, and recommend a default base delay for API clients.",
    "In two sentences, state one fact about why idempotency keys prevent duplicate "
    "side effects, and recommend where to generate the key.",
]


def _seed_runtime_db(path: str, task_ids: list[str]) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS delegation_runs (
            run_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL DEFAULT '',
            task_id TEXT NOT NULL,
            claim_id TEXT NOT NULL DEFAULT '',
            parent_run_id TEXT NOT NULL DEFAULT '',
            assigned_by TEXT NOT NULL DEFAULT '',
            assigned_to TEXT NOT NULL,
            requested_output_json TEXT NOT NULL DEFAULT '[]',
            current_artifact_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            failure_code TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            trace_id TEXT NOT NULL DEFAULT '',
            receipt_json TEXT
        )"""
    )
    now = datetime.now(timezone.utc).isoformat()
    for tid in task_ids:
        conn.execute(
            "INSERT INTO delegation_runs (run_id, task_id, assigned_to, status, started_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (f"run_{uuid4().hex[:16]}", tid, "loop4_closer", "running", now),
        )
    conn.commit()
    conn.close()


class _ModelTaggedProvider:
    """Thin pass-through over a real runtime provider that surfaces `.model`.

    KnowledgeExtractor._call_llm reads llm_client.model; the runtime provider does
    not expose it. This wrapper delegates .complete unchanged (real provider, real
    network call) and only exposes the correct free-provider default model so the
    LLMRequest targets the live provider instead of the Anthropic fallback string.
    """

    def __init__(self, provider, model: str) -> None:  # noqa: ANN001
        self._provider = provider
        self.model = model

    async def complete(self, request):  # noqa: ANN001
        if not getattr(request, "model", None):
            request.model = self.model
        return await self._provider.complete(request)


class _ScopedSyncDB:
    """Minimal async-shim over a sync sqlite conn matching spine.persistence.AsyncDB."""

    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path)
        self._last = None

    async def execute(self, sql: str, parameters: tuple = ()):  # noqa: ANN001
        self._last = self._conn.execute(sql, parameters)
        return self._last

    async def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


async def _real_provider_invoker(task, agent_id, context_id, routing):  # noqa: ANN001
    """The blessed invoker: call a REAL live FREE provider, return a real receipt
    carrying the REAL provider output text (attributes.agent_output) so Loop 4 has
    genuine knowledge to consolidate. No mock."""
    pt: ProviderType = task["_provider_type"]
    model_hint: str | None = task["_model_hint"]
    prompt: str = task["prompt"]

    cfg = resolve_runtime_provider_config(pt, model=model_hint)
    if not cfg.available:
        raise RuntimeError(f"provider {pt.value} unavailable (no live key)")
    provider = create_runtime_provider(cfg)
    req = LLMRequest(
        model=cfg.default_model or model_hint or "",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=160,
        temperature=0,
    )
    t0 = time.monotonic()
    resp = await asyncio.wait_for(provider.complete(req), timeout=90)
    latency_ms = int((time.monotonic() - t0) * 1000)

    usage = resp.usage or {}
    in_tok = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    out_tok = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    real_provider = resp.provider or pt.value
    real_model = resp.model or cfg.default_model or ""

    side_effect_key = (
        f"{real_provider}:{real_model}:in{in_tok}:out{out_tok}:"
        f"{abs(hash(resp.content)) & 0xFFFFFFFF:08x}"
    )

    return EvidenceReceipt(
        trace_id=task["_trace_id"],
        context_id=context_id,
        task_id=task["_task_id"],
        agent_id=agent_id,
        provider=real_provider,
        model=real_model,
        operation="invoke_agent",
        provider_attempted=True,
        status="ok",
        error_source="none",
        finished_at=datetime.now(timezone.utc),
        latency_ms=latency_ms,
        input_tokens=in_tok,
        output_tokens=out_tok,
        routing_decision_id=routing.decision_id,
        attributes={
            "router": "loop4_closer_free_first",
            "side_effect_key": side_effect_key,
            # the REAL provider output — this is the agent output Loop 4 consolidates:
            "agent_output": resp.content,
            "task_prompt": prompt,
            "free_first": True,
        },
    )


async def _dispatch_one(runtime_db, task_id, trace_id, prompt, pt, model_hint):  # noqa: ANN001
    if os.environ.get("DHARMA_SPINE_DISPATCH") != "1":
        raise RuntimeError("DHARMA_SPINE_DISPATCH must be set to 1 for real dispatch")

    routing = RoutingDecision(
        agent_id="loop4_closer",
        provider=pt.value,
        model=model_hint or "",
        reason="free-first decorrelated consolidation-source dispatch",
        router_name="loop4_closer_free_first",
        context_id=trace_id,
        task_id=task_id,
    )
    task = {
        "prompt": prompt,
        "_provider_type": pt,
        "_model_hint": model_hint,
        "_task_id": task_id,
        "_trace_id": trace_id,
    }
    receipt = await invoke_agent(
        task=task,
        agent_id="loop4_closer",
        context_id=trace_id,
        routing=routing,
        invoker=_real_provider_invoker,
    )
    from dharma_swarm.spine.persistence import persist_receipt

    db = _ScopedSyncDB(runtime_db)
    try:
        await persist_receipt(receipt, db)
        await db.execute(
            "UPDATE delegation_runs SET status='completed', completed_at=? WHERE task_id=?",
            (datetime.now(timezone.utc).isoformat(), task_id),
        )
        await db.commit()
    finally:
        db.close()
    return receipt


def _read_real_loop1_rows(db_path: str) -> list[dict]:
    """SENSE: read REAL-provider completed delegation_runs (the agent outputs)."""
    p = Path(db_path)
    if not p.exists():
        raise FileNotFoundError(f"runtime db missing: {db_path}")
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    out: list[dict] = []
    try:
        cur = conn.execute(
            "SELECT run_id, task_id, receipt_json FROM delegation_runs "
            "WHERE status='completed' AND receipt_json IS NOT NULL AND receipt_json!=''"
        )
        for run_id, task_id, rj in cur:
            try:
                r = json.loads(rj)
            except Exception:
                continue
            provider = str(r.get("provider", "")).strip().lower()
            model = str(r.get("model", "")).strip()
            itok = r.get("input_tokens")
            if provider in BAD_PROVIDERS or not model:
                continue
            if not isinstance(itok, (int, float)) or itok <= 0:
                continue
            attrs = r.get("attributes", {}) or {}
            agent_output = attrs.get("agent_output", "")
            if not agent_output or not str(agent_output).strip():
                continue
            out.append({"run_id": run_id, "task_id": task_id, "receipt": r, "agent_output": agent_output})
    finally:
        conn.close()
    return out


async def main() -> int:
    # ── 1. Drive real FREE-provider dispatches with knowledge-bearing prompts ──
    task_ids = [f"task_loop4_{uuid4().hex[:12]}" for _ in TASKS]
    _seed_runtime_db(RUNTIME_DB, task_ids)

    dispatched = 0
    errors: list[str] = []
    for i, prompt in enumerate(TASKS):
        pt, model_hint = FREE_CANDIDATES[i % len(FREE_CANDIDATES)]
        trace_id = f"trace_loop4_{uuid4().hex[:12]}"
        try:
            r = await _dispatch_one(RUNTIME_DB, task_ids[i], trace_id, prompt, pt, model_hint)
            dispatched += 1
            print(
                f"DISPATCH OK  task={task_ids[i]} provider={r.provider} model={r.model} "
                f"in_tok={r.input_tokens} out_tok={r.output_tokens} "
                f"output_chars={len(r.attributes.get('agent_output', ''))}"
            )
        except Exception as e:  # noqa: BLE001
            errors.append(f"{pt.value}: {type(e).__name__}: {str(e)[:140]}")
            print(f"DISPATCH ERR task={task_ids[i]} {pt.value}: {e}")

    if dispatched < 3:
        print(f"\nRED: only {dispatched} real dispatches (need >=3). errors: {json.dumps(errors)}")
        return 1

    # ── 2. SENSE: read the real agent outputs back ──
    rows = _read_real_loop1_rows(RUNTIME_DB)
    if len(rows) < 3:
        print(f"RED: only {len(rows)} real outputs with text to consolidate (need >=3)")
        return 1

    # ── 3. ACT/EVALUATE: REAL consolidation with a REAL free-provider LLM client ──
    # The extraction client is itself a live FREE provider (decorrelated from the
    # generating provider where possible). No mock anywhere in the consolidation path.
    extract_cfg = resolve_runtime_provider_config(ProviderType.OLLAMA, model="glm-5")
    if not extract_cfg.available:
        extract_cfg = resolve_runtime_provider_config(ProviderType.GOOGLE_AI)
    if not extract_cfg.available:
        print("RED: no live FREE provider available for the extraction llm_client")
        return 1
    # KnowledgeExtractor._call_llm reads llm_client.model to build the LLMRequest and
    # falls back to an Anthropic model string if absent — which makes the request fail
    # against a free provider and silently returns "[]". The runtime provider exposes
    # no `.model`, so wrap it with the correct default model. (Real provider, real
    # .complete — only the model attr is surfaced; no mock, no behavior change.)
    extractor_client = _ModelTaggedProvider(
        create_runtime_provider(extract_cfg), extract_cfg.default_model or ""
    )

    LOOP4_DIR.mkdir(parents=True, exist_ok=True)
    store = KnowledgeStore(KNOWLEDGE_DB)
    agent = SleepTimeAgent()

    consolidated = []  # per real run_id: counts
    total_props = 0
    total_prescs = 0
    try:
        for row in rows:
            run_id = row["run_id"]
            # tag every extracted unit with the real Loop-1 run_id as provenance so
            # the check can JOIN consolidated memory back to its real source.
            task_context = (
                f"[provenance_event_id:{run_id}] Task output to consolidate:\n"
                f"{row['agent_output']}"
            )
            stats = await agent.consolidate_knowledge(
                task_context=task_context,
                task_outcome={"success": True, "run_id": run_id},
                llm_client=extractor_client,
                knowledge_store=store,
            )
            # The extractor sets provenance_context from the context head; ensure the
            # run_id is also discoverable via provenance_context (it is embedded above).
            consolidated.append(
                {
                    "run_id": run_id,
                    "propositions": stats.get("propositions", 0),
                    "prescriptions": stats.get("prescriptions", 0),
                    "errors": stats.get("errors", []),
                }
            )
            total_props += stats.get("propositions", 0)
            total_prescs += stats.get("prescriptions", 0)
            print(
                f"CONSOLIDATE run={run_id} props={stats.get('propositions', 0)} "
                f"prescs={stats.get('prescriptions', 0)} errs={len(stats.get('errors', []))}"
            )
    finally:
        store.close()

    runs_with_knowledge = [c for c in consolidated if (c["propositions"] + c["prescriptions"]) > 0]

    # ── 4. ADAPT: emit the consolidation_cycle receipt (memory feeds next context) ──
    adapt_receipt = {
        "type": "CONSOLIDATION_CYCLE",
        "source": "loop4_closer",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "knowledge_db": KNOWLEDGE_DB,
        "runtime_db": RUNTIME_DB,
        "total_propositions": total_props,
        "total_prescriptions": total_prescs,
        "consolidated_per_run": consolidated,
        # provenance: every consolidated unit traces to a real Loop-1 run receipt
        "joined_delegation_run_ids": [c["run_id"] for c in runs_with_knowledge],
        "extraction_provider": extract_cfg.default_model,
        "one_wire_note": "internal memory consolidation only; no archive.jsonl write",
    }
    adapt_path = LOOP4_DIR / "loop4_adapt_receipt.json"
    adapt_path.write_text(json.dumps(adapt_receipt, indent=2))

    print(f"\nKNOWLEDGE_DB={KNOWLEDGE_DB}")
    print(f"LOOP4_DIR={LOOP4_DIR}")
    print(
        f"runs consolidated with knowledge: {len(runs_with_knowledge)}/{len(rows)} "
        f"(need >=3); props={total_props} prescs={total_prescs}"
    )
    print(f"adapt receipt: {adapt_path}")
    return 0 if len(runs_with_knowledge) >= 3 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
