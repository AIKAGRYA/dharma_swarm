"""WIRE IT IN — continuous frontier-routing proof on the CANONICAL runtime.db at $0.

Drives ~24 REAL spine dispatches (Orchestrator._run_task_via_spine, gated by
DHARMA_SPINE_DISPATCH=1) through the canonical orchestrator path, each one a real
network call to a VERIFIED-LIVE >=Kimi-K2.6 frontier brain on a free/subscription
lane (ollama-cloud subscription + NVIDIA NIM free tier). Every dispatch persists a
served-truth EvidenceReceipt to the CANONICAL delegation_runs.receipt_json with
provider+model = the frontier brain that ACTUALLY served.

This is the canonical-surface version of prove_served_receipt_multiprovider.py /
prove_loop1_spine_ollama.py: same blessed spine sequence, but runtime_db points at
/Users/dhyana/.dharma/state/runtime.db so make-orient's Loop 1 + routing-truth
panel reads the climbing receipt-fill and the >=K2.6 floor PASS on the latest
served model.

$0 hard cap: ONLY free/subscription lanes. NO paid (no openai/anthropic/
openrouter-paid). Every model is >=K2.6 frontier (deepseek-v4-pro, glm-5.1,
kimi-k2.6, kimi-k2.7-code, minimax-m3, qwen3-coder:480b, mistral-large-3) — no
llama-70b / kimi-k2.5 / sub-floor siblings.
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# CANONICAL runtime db — the operator surface orientation_graph.py reads by
# default (runtime_state.DEFAULT_RUNTIME_DB). Loop 1 closes on THIS file.
CANONICAL_DB = Path("/Users/dhyana/.dharma/state/runtime.db")

os.environ["DHARMA_SPINE_DISPATCH"] = "1"
os.environ["OLLAMA_USE_CLOUD"] = "1"  # subscription cloud lane

from dharma_swarm.models import (
    AgentConfig,
    ProviderType,
    Task,
    TaskDispatch,
    TopologyType,
)
from dharma_swarm.runtime_provider import (
    resolve_runtime_provider_config,
    create_runtime_provider,
)
from dharma_swarm.agent_runner import AgentRunner
from dharma_swarm.orchestrator import Orchestrator


# --- The verified-live >=K2.6 frontier stable (all $0). model strings carry a
#     FRONTIER_FLOOR substring so the receipt classifies AT-OR-ABOVE. ---
FRONTIER_STABLE = [
    # (label, provider_type, model, env_overrides)
    ("ollama_deepseek_v4_pro", ProviderType.OLLAMA, "deepseek-v4-pro:cloud", {"OLLAMA_USE_CLOUD": "1"}),
    ("ollama_glm_5_1",         ProviderType.OLLAMA, "glm-5.1:cloud",         {"OLLAMA_USE_CLOUD": "1"}),
    ("ollama_kimi_k2_6",       ProviderType.OLLAMA, "kimi-k2.6:cloud",       {"OLLAMA_USE_CLOUD": "1"}),
    ("ollama_kimi_k2_7_code",  ProviderType.OLLAMA, "kimi-k2.7-code:cloud",  {"OLLAMA_USE_CLOUD": "1"}),
    ("ollama_minimax_m3",      ProviderType.OLLAMA, "minimax-m3:cloud",      {"OLLAMA_USE_CLOUD": "1"}),
    ("ollama_qwen3_coder_480b", ProviderType.OLLAMA, "qwen3-coder:480b-cloud", {"OLLAMA_USE_CLOUD": "1"}),
    ("nvidia_kimi_k2_6",       ProviderType.NVIDIA_NIM, "moonshotai/kimi-k2.6", None),
    ("nvidia_minimax_m3",      ProviderType.NVIDIA_NIM, "minimaxai/minimax-m3", None),
    ("nvidia_mistral_large_3", ProviderType.NVIDIA_NIM, "mistralai/mistral-large-3-675b-instruct-2512", None),
]

PROMPTS = [
    "Reply with one short sentence about a river finding its banks.",
    "In one short sentence, what makes constraint enable emergence?",
    "One short sentence: why does a witness attractor contract representation space?",
]


def _fill(db: Path) -> dict:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        total = conn.execute("SELECT COUNT(*) FROM delegation_runs").fetchone()[0]
        receipted = conn.execute(
            "SELECT COUNT(*) FROM delegation_runs "
            "WHERE receipt_json IS NOT NULL AND receipt_json != ''"
        ).fetchone()[0]
        today_total = conn.execute(
            "SELECT COUNT(*) FROM delegation_runs WHERE date(started_at)=date('now')"
        ).fetchone()[0]
        today_receipted = conn.execute(
            "SELECT COUNT(*) FROM delegation_runs "
            "WHERE date(started_at)=date('now') "
            "AND receipt_json IS NOT NULL AND receipt_json != ''"
        ).fetchone()[0]
    finally:
        conn.close()
    return {
        "total": total,
        "receipted": receipted,
        "today_total": today_total,
        "today_receipted": today_receipted,
    }


async def dispatch_once(orch, runner, cfg, title) -> dict:
    task = Task(title=title, description="frontier-routing canonical proof")
    td = TaskDispatch(task_id=task.id, agent_id=cfg.id, topology=TopologyType.FAN_OUT)
    await orch._runtime_lifecycle.record_delegation_run(td, task=task, status="running")
    result = None
    err = None
    try:
        result = await orch._run_task_via_spine(runner, task, td, 120.0)
        status = "completed"
    except Exception as exc:
        err = repr(exc)
        status = "failed"
    if status == "completed":
        await orch._runtime_lifecycle.record_task_claim(td, task=task, status="completed")
        await orch._runtime_lifecycle.record_delegation_run(
            td, task=task, status="completed", result=result
        )
    else:
        await orch._runtime_lifecycle.record_delegation_run(
            td, task=task, status="failed", error=err or "spine dispatch failed"
        )
    receipt = getattr(orch, "_last_evidence_receipt", None)
    return {
        "status": status,
        "error": err,
        "result_chars": len(result or ""),
        "served_provider": getattr(runner, "_last_served_provider", None),
        "served_model": getattr(runner, "_last_served_model", None),
        "receipt_provider": getattr(receipt, "provider", None),
        "receipt_model": getattr(receipt, "model", None),
        "receipt_status": getattr(receipt, "status", None),
        "receipt_latency_ms": getattr(receipt, "latency_ms", None),
        "result_preview": (result or "")[:80],
    }


async def dispatch_frontier(orch, label, provider_type, model, prompt, env_overrides) -> dict:
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
        for k, v in env_overrides.items():
            os.environ[k] = v
    cfg_rp = resolve_runtime_provider_config(provider_type, model=model, env=env)
    provider = create_runtime_provider(cfg_rp)
    cfg = AgentConfig(
        name=f"frontier_{label}",
        id=f"frontier_{label}",
        provider=provider_type,
        model=cfg_rp.default_model or model or "",
    )
    runner = AgentRunner(config=cfg, provider=provider)
    out = await dispatch_once(orch, runner, cfg, f"[{label}] {prompt}")

    # Served model is source of truth; receipt must carry it (ollama/nvidia
    # response.provider is '' -> spine falls back to config provider, which IS
    # the actually-served lane on the single-provider path).
    served_m = out["served_model"] or (cfg_rp.default_model or model or "")
    expected_p = (out["served_provider"] or provider_type.value).lower()
    out.update({
        "label": label,
        "configured_provider": provider_type.value,
        "configured_model": cfg_rp.default_model or model,
        "served_model_effective": served_m,
        "receipt_ok": bool(
            out["status"] == "completed"
            and out["result_chars"] > 0
            and (out["receipt_latency_ms"] or 0) > 0
            and (out["receipt_provider"] or "").lower() == expected_p
            and out["receipt_model"]
        ),
    })
    return out


# Mirror of orientation_graph.classify_floor — the >=K2.6 power floor.
FRONTIER_FLOOR = (
    "kimi-k2.6", "kimi-k2.7", "deepseek-v4-pro", "glm-5.1", "minimax-m3",
    "qwen3-coder", "mistral-large-3", "gpt-5.5", "claude-opus-4-8",
    "claude-opus-4.8", "gemini-3-pro",
)


def floor_class(model: str) -> str:
    if not model:
        return "UNKNOWN"
    name = str(model).lower()
    for sub in FRONTIER_FLOOR:
        if sub in name:
            return "AT-OR-ABOVE"
    return "BELOW"


async def main() -> dict:
    CANONICAL_DB.parent.mkdir(parents=True, exist_ok=True)
    fill_before = _fill(CANONICAL_DB)

    orch = Orchestrator(runtime_db_path=CANONICAL_DB)

    results = []
    n_dispatches = 24
    for i in range(n_dispatches):
        label, ptype, model, env_ov = FRONTIER_STABLE[i % len(FRONTIER_STABLE)]
        prompt = PROMPTS[i % len(PROMPTS)]
        # retry-once on a transient (nvidia cold-404 / cloud burst throttle)
        out = None
        for attempt in range(2):
            out = await dispatch_frontier(orch, label, ptype, model, prompt, env_ov)
            if out["receipt_ok"]:
                break
            await asyncio.sleep(4)
        out["attempts"] = attempt + 1
        out["dispatch_index"] = i
        out["floor_class"] = floor_class(out["served_model_effective"])
        results.append(out)
        print(
            f"[{i+1:2}/{n_dispatches}] {label:26} "
            f"served={out['served_model_effective']:34} "
            f"floor={out['floor_class']:11} "
            f"receipt_ok={out['receipt_ok']} "
            f"chars={out['result_chars']} lat_ms={out['receipt_latency_ms']}",
            flush=True,
        )

    fill_after = _fill(CANONICAL_DB)

    served_dist: dict[str, int] = {}
    for r in results:
        sm = r["served_model_effective"]
        served_dist[sm] = served_dist.get(sm, 0) + 1

    all_above_floor = all(
        floor_class(r["served_model_effective"]) == "AT-OR-ABOVE"
        for r in results if r["receipt_ok"]
    )
    n_ok = sum(1 for r in results if r["receipt_ok"])
    n_fail = len(results) - n_ok

    return {
        "db_path": str(CANONICAL_DB),
        "n_dispatches": n_dispatches,
        "n_receipt_ok": n_ok,
        "n_failed": n_fail,
        "fill_before": fill_before,
        "fill_after": fill_after,
        "served_distribution": served_dist,
        "all_above_floor": all_above_floor,
        "results": results,
        "now_utc": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import json
    out = asyncio.run(main())
    print("PROOF_JSON_START")
    print(json.dumps(out, indent=2, default=str))
    print("PROOF_JSON_END")
