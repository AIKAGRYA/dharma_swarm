#!/usr/bin/env python3
"""Loop 1 closure driver — dispatch REAL tasks through the spine to LIVE FREE providers.

This is the close-unit's Generator + Evaluator. It does NOT touch the production
daemon, the live runtime.db, or archive fitness. It:

  1. Creates a SCOPED temp delegation_runs db (its own file under /tmp).
  2. Seeds one delegation_runs row per task (the orchestrator surface persist
     keys receipts by task_id, so the row must exist first).
  3. For each task: routes through dharma_swarm.spine.invoke.invoke_agent with an
     invoker that calls a REAL live FREE provider via runtime_provider, captures
     the REAL provider / model / input_tokens off the LLMResponse, builds the
     canonical EvidenceReceipt, and persists it via spine.persistence.persist_receipt.
  4. Marks the row status='completed'.

The receipt carries a real provider name (google_ai / ollama|glm / deepseek),
non-empty model, input_tokens>0, and a side_effect_key (the routing decision +
real usage). That is exactly what check_loop_1 demands. No mock provider anywhere
in the closure path; the only synthetic part is the seed task text.

Run:  DHARMA_SPINE_DISPATCH=1 python3 scripts/governance/closure/drive_loop_1.py
Then: LC_RUNTIME_DB=<scoped_db> python3 scripts/governance/closure/check_loop_1.py
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
from dharma_swarm.spine.invoke import invoke_agent  # noqa: E402
from dharma_swarm.spine.receipt import EvidenceReceipt  # noqa: E402
from dharma_swarm.spine.routing import RoutingDecision  # noqa: E402

SCOPED_DB = os.environ.get(
    "LC_SCOPED_DB", f"/tmp/lc_loop1_scoped_{int(time.time())}.db"
)

# FREE-first decorrelated candidates (live-confirmed 2026-06-16). Each is a real
# LLM provider; none is 'orchestrator'/'mock'. We require >=3 SUCCESSFUL real
# dispatches; the list gives decorrelation (distinct families) and fallback.
FREE_CANDIDATES: list[tuple[ProviderType, str | None]] = [
    (ProviderType.GOOGLE_AI, None),   # gemini-2.5-flash
    (ProviderType.OLLAMA, None),      # ollama_cloud -> glm-5
    (ProviderType.GOOGLE_AI, "gemini-2.5-flash"),
    (ProviderType.OLLAMA, "deepseek-v3.2"),
]

TASKS = [
    "Reply with exactly one word: ALPHA",
    "Reply with exactly one word: BRAVO",
    "Reply with exactly one word: CHARLIE",
    "Reply with exactly one word: DELTA",
]


def _seed_scoped_db(path: str, task_ids: list[str]) -> None:
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
            (f"run_{uuid4().hex[:16]}", tid, "loop1_closer", "running", now),
        )
    conn.commit()
    conn.close()


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
    """The blessed invoker: call a REAL live FREE provider, return a real receipt.

    Captures real provider/model/input_tokens from the LLMResponse.usage. No mock.
    """
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
        max_tokens=32,
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

    # side_effect_key: stable hash of the real side effect (provider+model+tokens+content).
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
            "router": "loop1_closer_free_first",
            "side_effect_key": side_effect_key,
            "content_preview": resp.content[:60],
            "free_first": True,
        },
    )


async def _dispatch_one(scoped_db_path, task_id, trace_id, prompt, pt, model_hint):  # noqa: ANN001
    if os.environ.get("DHARMA_SPINE_DISPATCH") != "1":
        raise RuntimeError("DHARMA_SPINE_DISPATCH must be set to 1 for real dispatch")

    routing = RoutingDecision(
        agent_id="loop1_closer",
        provider=pt.value,
        model=model_hint or "",
        reason="free-first decorrelated closure dispatch",
        router_name="loop1_closer_free_first",
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
        agent_id="loop1_closer",
        context_id=trace_id,
        routing=routing,
        invoker=_real_provider_invoker,
    )
    # Persist via the canonical spine sink, then flip status -> completed.
    from dharma_swarm.spine.persistence import persist_receipt

    db = _ScopedSyncDB(scoped_db_path)
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


async def main() -> int:
    task_ids = [f"task_loop1_{uuid4().hex[:12]}" for _ in TASKS]
    _seed_scoped_db(SCOPED_DB, task_ids)

    successes: list[EvidenceReceipt] = []
    errors: list[str] = []
    for i, prompt in enumerate(TASKS):
        pt, model_hint = FREE_CANDIDATES[i % len(FREE_CANDIDATES)]
        trace_id = f"trace_loop1_{uuid4().hex[:12]}"
        try:
            r = await _dispatch_one(
                SCOPED_DB, task_ids[i], trace_id, prompt, pt, model_hint
            )
            successes.append(r)
            print(
                f"DISPATCH OK  task={task_ids[i]} provider={r.provider} "
                f"model={r.model} in_tok={r.input_tokens} out_tok={r.output_tokens} "
                f"side_effect_key={r.attributes.get('side_effect_key')}"
            )
        except Exception as e:  # noqa: BLE001
            errors.append(f"{pt.value}: {type(e).__name__}: {str(e)[:140]}")
            print(f"DISPATCH ERR task={task_ids[i]} {pt.value}: {e}")

    print(f"\nSCOPED_DB={SCOPED_DB}")
    print(f"REAL successful dispatches: {len(successes)} (need >=3)")
    if errors:
        print("errors:", json.dumps(errors, indent=2))
    return 0 if len(successes) >= 3 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
