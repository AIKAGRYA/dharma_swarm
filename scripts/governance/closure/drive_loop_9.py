#!/usr/bin/env python3
"""Loop 9 (Conductors) closure driver — fire a REAL conductor wake on real data.

This is the close-unit's Generator + Evaluator. It does NOT touch the production
daemon, the live runtime.db, the live witness dir, or archive fitness. It runs
ALL FIVE conductor transitions on real data:

  sense      -> PersistentAgent.wake() reads stigmergy hot_paths + high_salience
                marks + the message bus (steps 2-4 of the wake cycle).
  interpret  -> _generate_self_task() / message routing picks the wake task.
  constrain  -> _check_gate() -> telos_gates.check_with_reflective_reroute with
                think_phase='conductor_wake' (real gate, not bypassed).
  act        -> AutonomousAgent.wake() ReAct loop calls a LIVE FREE provider.
                We pin the act-step LLM call to a confirmed-live FREE provider
                (real provider; real usage; NO mock anywhere in the path) so the
                dispatch is deterministic and decorrelated from a dead key.
  adapt      -> stigmergy leave_mark + _write_witness('WAKE', ...) to the owner
                surface (state_dir/witness/conductor_<name>.jsonl) + profile
                record -> feeds the next wake's sense.

Loop 9 consumes Loop 1 output: the conductor act-step IS a real Loop-1-style
spine dispatch. We persist a real-provider spine EvidenceReceipt for the
conductor task (the same proven Loop-1 path) so the conductor run is tied to a
real delegation_run with provider/model/input_tokens>0 and a side_effect_key.

Everything is scoped to /tmp:
  - state_dir          -> scoped temp dir (witness owner surface lands here)
  - spine receipt db   -> scoped temp delegation_runs db
  - stigmergy/bus      -> read from the real state dir read-only-ish (no writes
                          to production fitness); the conductor's OWN marks go
                          to the scoped state_dir via its StigmergyStore default.

Run:  DHARMA_SPINE_DISPATCH=1 python3 scripts/governance/closure/drive_loop_9.py
Then: LC_LOOP9_STATE_DIR=<scoped> LC_RUNTIME_DB=<scoped_db> \
      python3 scripts/governance/closure/check_loop_9.py
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

STATE_DIR = Path(
    os.environ.get("LC_LOOP9_STATE_DIR", f"/tmp/lc_loop9_state_{int(time.time())}")
)
SCOPED_DB = os.environ.get(
    "LC_LOOP9_SCOPED_DB", f"/tmp/lc_loop9_scoped_{int(time.time())}.db"
)

# FREE-first decorrelated, live-confirmed 2026-06-16. Each is a real LLM
# provider; none is 'orchestrator'/'mock'. Tried in order until one answers.
FREE_CANDIDATES: list[tuple[ProviderType, str | None]] = [
    (ProviderType.GOOGLE_AI, None),   # gemini-2.5-flash
    (ProviderType.OLLAMA, None),      # ollama_cloud -> glm-5
    (ProviderType.OLLAMA, "deepseek-v3.2"),
]


# ---------------------------------------------------------------------------
# Real-provider call (shared by the act-step pin and the spine receipt).
# ---------------------------------------------------------------------------


async def _live_free_complete(prompt: str):
    """Call the first live FREE provider. Returns (resp, pt, cfg). No mock."""
    last_exc: Exception | None = None
    for pt, model_hint in FREE_CANDIDATES:
        cfg = resolve_runtime_provider_config(pt, model=model_hint)
        if not cfg.available:
            continue
        provider = create_runtime_provider(cfg)
        try:
            req = LLMRequest(
                model=cfg.default_model or model_hint or "",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=64,
                temperature=0,
            )
            resp = await asyncio.wait_for(provider.complete(req), timeout=90)
            return resp, pt, cfg
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
        finally:
            close = getattr(provider, "close", None)
            if callable(close):
                try:
                    await close()
                except Exception:
                    pass
    raise RuntimeError(
        f"no live FREE provider answered (last error: {last_exc})"
    )


# ---------------------------------------------------------------------------
# Scoped spine receipt sink (the Loop-1 consume edge).
# ---------------------------------------------------------------------------


def _seed_scoped_db(path: str, task_id: str) -> str:
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
    run_id = f"run_{uuid4().hex[:16]}"
    conn.execute(
        "INSERT INTO delegation_runs (run_id, task_id, assigned_to, status, started_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, task_id, "conductor_claude", "running",
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()
    return run_id


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


async def _persist_conductor_spine_receipt(
    task_id: str, resp, pt: ProviderType, model: str
) -> EvidenceReceipt:
    """Persist a real-provider EvidenceReceipt for the conductor act (Loop-1 edge)."""
    if os.environ.get("DHARMA_SPINE_DISPATCH") != "1":
        raise RuntimeError("DHARMA_SPINE_DISPATCH must be set to 1 for real dispatch")

    usage = resp.usage or {}
    in_tok = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    out_tok = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    real_provider = resp.provider or pt.value
    real_model = resp.model or model
    side_effect_key = (
        f"{real_provider}:{real_model}:in{in_tok}:out{out_tok}:"
        f"{abs(hash(resp.content)) & 0xFFFFFFFF:08x}"
    )
    trace_id = f"trace_loop9_{uuid4().hex[:12]}"

    routing = RoutingDecision(
        agent_id="conductor_claude",
        provider=real_provider,
        model=real_model,
        reason="conductor wake act-step (free-first decorrelated)",
        router_name="loop9_conductor_free_first",
        context_id=trace_id,
        task_id=task_id,
    )

    async def _invoker(task, agent_id, context_id, routing):  # noqa: ANN001
        return EvidenceReceipt(
            trace_id=trace_id,
            context_id=context_id,
            task_id=task_id,
            agent_id=agent_id,
            provider=real_provider,
            model=real_model,
            operation="invoke_agent",
            provider_attempted=True,
            status="ok",
            error_source="none",
            finished_at=datetime.now(timezone.utc),
            latency_ms=0,
            input_tokens=in_tok,
            output_tokens=out_tok,
            routing_decision_id=routing.decision_id,
            attributes={
                "loop": 9,
                "loop_role": "conductor_wake_act",
                "router": "loop9_conductor_free_first",
                "side_effect_key": side_effect_key,
                "content_preview": resp.content[:60],
                "free_first": True,
            },
        )

    receipt = await invoke_agent(
        task={"prompt": "conductor wake act"},
        agent_id="conductor_claude",
        context_id=trace_id,
        routing=routing,
        invoker=_invoker,
    )

    from dharma_swarm.spine.persistence import persist_receipt

    db = _ScopedSyncDB(SCOPED_DB)
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


# ---------------------------------------------------------------------------
# The real conductor wake (all 5 transitions on real data).
# ---------------------------------------------------------------------------


async def main() -> int:
    if os.environ.get("DHARMA_SPINE_DISPATCH") != "1":
        print("ERROR: DHARMA_SPINE_DISPATCH must be 1 for real dispatch")
        return 1

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    from dharma_swarm.persistent_agent import PersistentAgent
    from dharma_swarm.conductors import CONDUCTOR_CLAUDE_CONFIG

    cfg = dict(CONDUCTOR_CLAUDE_CONFIG)
    # Build the real conductor scoped to the temp state_dir. Owner-surface
    # witness lands at STATE_DIR/witness/conductor_conductor_claude.jsonl.
    conductor = PersistentAgent(
        name=cfg["name"],
        role=cfg["role"],
        provider_type=cfg["provider_type"],
        model=cfg["model"],
        state_dir=STATE_DIR,
        wake_interval_seconds=cfg["wake_interval_seconds"],
        system_prompt="You are conductor_claude. Reply with one short sentence.",
        max_turns=1,
    )

    # ACT-STEP PIN: route the conductor's act-step LLM call to a live FREE
    # provider. Real provider, real usage, NO mock. This is the Loop-1 consume
    # edge — the conductor's act is a real provider dispatch. We capture the
    # real LLMResponse so the spine receipt and witness tokens are genuine.
    captured: dict[str, object] = {}

    async def _pinned_call_llm(system, messages, tools):  # noqa: ANN001
        # The conductor's interpreted task is the last user message.
        prompt = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                c = m.get("content")
                prompt = c if isinstance(c, str) else json.dumps(c)
                break
        resp, pt, rcfg = await _live_free_complete(prompt or "Report system state.")
        usage = resp.usage or {}
        in_tok = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        out_tok = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        captured["resp"] = resp
        captured["pt"] = pt
        captured["model"] = resp.model or rcfg.default_model or ""
        # Normalize to the ReAct shape AutonomousAgent expects. No tool_uses ->
        # the loop ends after one real turn (stop_reason end_turn).
        return {
            "text": [resp.content],
            "tool_uses": [],
            "raw_content": resp.content,
            "stop_reason": "end_turn",
            "tokens_in": in_tok,
            "tokens_out": out_tok,
        }

    conductor._agent._call_llm = _pinned_call_llm  # type: ignore[attr-defined]

    # FIRE THE WAKE — sense, interpret, constrain, act, adapt — on real data.
    wake_info = await conductor.wake()

    print("WAKE INFO:", json.dumps(wake_info, default=str, indent=2)[:800])

    if not wake_info.get("success"):
        print(f"CONDUCTOR WAKE not successful: {wake_info.get('error') or wake_info}")
        return 1
    if int(wake_info.get("tokens", 0)) <= 0:
        print("CONDUCTOR WAKE produced 0 tokens — no real provider answered")
        return 1

    resp = captured.get("resp")
    if resp is None:
        print("act-step did not capture a real provider response")
        return 1

    # Persist the Loop-1 consume-edge spine receipt for the conductor act.
    task_id = f"task_loop9_{uuid4().hex[:12]}"
    _seed_scoped_db(SCOPED_DB, task_id)
    receipt = await _persist_conductor_spine_receipt(
        task_id, resp, captured["pt"], str(captured["model"])  # type: ignore[arg-type]
    )

    print(
        f"\nSPINE RECEIPT  provider={receipt.provider} model={receipt.model} "
        f"in_tok={receipt.input_tokens} out_tok={receipt.output_tokens} "
        f"side_effect_key={receipt.attributes.get('side_effect_key')}"
    )
    print(f"STATE_DIR={STATE_DIR}")
    print(f"SCOPED_DB={SCOPED_DB}")
    print(f"WITNESS_LOG={conductor._witness_log}")  # type: ignore[attr-defined]
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
