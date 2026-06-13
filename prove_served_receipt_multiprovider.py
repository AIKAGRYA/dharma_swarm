"""Prove the served-provider EvidenceReceipt is ROBUST across multiple real
free providers AND under a configured!=served FALLBACK — all at $0.

Two regimes, both through the REAL routing path and the REAL spine
(Orchestrator._run_task_via_spine, gated by DHARMA_SPINE_DISPATCH=1):

A) PER-PROVIDER (single-provider real path)
   For each live free provider: resolve it through
   runtime_provider.resolve_runtime_provider_config -> create_runtime_provider
   (THE ONE WAY), wrap in a real AgentRunner, dispatch ONE small real task via
   _run_task_via_spine, then assert the EvidenceReceipt.provider/model match the
   provider/model that ACTUALLY served (runner._last_served_* <- response.provider
   / response.model), with latency_ms > 0 and a non-empty result.

B) FALLBACK (configured != served)
   Build a REAL ModelRouter whose primary (configured) provider is a dead /
   unreachable provider, with a LIVE free provider as fallback. The router walks
   its real chain, the dead primary fails, the live free one serves. Dispatch
   through the same spine path and assert the receipt names the SERVED (fallback)
   provider, NOT the configured-dead one.

Lane-local runtime DB (NOT canonical ~/.dharma/state/runtime.db).
$0: only free providers (ollama local+cloud subscription, nvidia_nim free tier).
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

LANE_DIR = Path("/Users/dhyana/ds_loop_closure/_proof_state")
LANE_DB = LANE_DIR / "served_receipt_proof.db"

os.environ["DHARMA_SPINE_DISPATCH"] = "1"

from dharma_swarm.models import (
    AgentConfig,
    LLMRequest,
    LLMResponse,
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


# ---------------------------------------------------------------------------
# Shared spine dispatch (mirrors orchestrator._execute_task's canonical path)
# ---------------------------------------------------------------------------
async def dispatch_via_spine(orch, runner, cfg, title) -> dict:
    return await dispatch_via_spine_with_meta(orch, runner, cfg, None, title)


async def dispatch_via_spine_with_meta(orch, runner, cfg, task_meta, title) -> dict:
    task = Task(
        title=title,
        description="served-receipt robustness proof",
        metadata=dict(task_meta) if task_meta else {},
    )
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
        "result": result,
        "result_chars": len(result or ""),
        "served_provider": getattr(runner, "_last_served_provider", None),
        "served_model": getattr(runner, "_last_served_model", None),
        "receipt_provider": getattr(receipt, "provider", None),
        "receipt_model": getattr(receipt, "model", None),
        "receipt_status": getattr(receipt, "status", None),
        "receipt_latency_ms": getattr(receipt, "latency_ms", None),
    }


# ---------------------------------------------------------------------------
# A) Per-provider, single-provider REAL routing path
# ---------------------------------------------------------------------------
async def prove_provider(orch, label, provider_type, model, env_overrides=None) -> dict:
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
        # Mirror overrides into the live process env so the concrete provider's
        # complete() (which re-reads os.environ at request time) honors them.
        for k, v in env_overrides.items():
            os.environ[k] = v
        # Local ollama: the concrete provider must NOT carry the cloud token,
        # else providers.py prefers the cloud transport at request time.
        _saved_key = None
        if env_overrides.get("OLLAMA_FORCE_LOCAL") == "1":
            _saved_key = os.environ.pop("OLLAMA_API_KEY", None)
            env.pop("OLLAMA_API_KEY", None)
    # THE ONE WAY: resolve -> create.
    cfg_rp = resolve_runtime_provider_config(provider_type, model=model, env=env)
    provider = create_runtime_provider(cfg_rp)
    cfg = AgentConfig(
        name=f"served_prover_{label}",
        id=f"served_prover_{label}",
        provider=provider_type,
        model=cfg_rp.default_model or model or "",
    )
    runner = AgentRunner(config=cfg, provider=provider)
    try:
        out = await dispatch_via_spine(orch, runner, cfg, f"[{label}] reply with one short sentence.")
    finally:
        # Restore process env so overrides don't leak into later providers.
        if env_overrides:
            for k in env_overrides:
                os.environ.pop(k, None)
            if env_overrides.get("OLLAMA_FORCE_LOCAL") == "1" and _saved_key is not None:
                os.environ["OLLAMA_API_KEY"] = _saved_key

    served_p = (out["served_provider"] or "").lower()
    served_m = (out["served_model"] or "")
    rcpt_p = (out["receipt_provider"] or "").lower()
    rcpt_m = (out["receipt_model"] or "")

    # The served provider/model is the SOURCE OF TRUTH. Assert the receipt copied it.
    # served_provider may be empty for some concrete providers (e.g. ollama
    # response.provider==''); in that case the spine falls back to config
    # provider, which for the single-provider path IS the actually-served one.
    expected_p = served_p or provider_type.value.lower()
    expected_m = served_m or (cfg_rp.default_model or model or "")

    matches = (
        out["status"] == "completed"
        and out["result_chars"] > 0
        and (out["receipt_latency_ms"] or 0) > 0
        and rcpt_p == expected_p
        and (rcpt_m == expected_m or (served_m and rcpt_m == served_m))
    )
    out.update({
        "label": label,
        "regime": "per_provider",
        "expected_provider": expected_p,
        "expected_model": expected_m,
        "matches": bool(matches),
        "result_preview": (out["result"] or "")[:80],
    })
    out.pop("result", None)
    return out


# ---------------------------------------------------------------------------
# Dead provider — unreachable; .complete() raises like a real network failure.
# ---------------------------------------------------------------------------
class DeadProvider:
    def __init__(self, name="dead-primary"):
        self.name = name

    async def complete(self, request: LLMRequest) -> LLMResponse:
        raise RuntimeError(f"{self.name}: connection refused (simulated dead provider)")

    async def health_check(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# B) FALLBACK via REAL ModelRouter chain (configured-dead -> served-live)
# ---------------------------------------------------------------------------
class PinnedModelProvider:
    """Wraps a real provider, forcing a known-available model. The router's
    complexity classifier upgrades NVIDIA_NIM to nvidia/llama-3.1-nemotron-
    ultra-253b-v1 on REASONING-tier requests (the 85KB orchestrator memory
    context trips REASONING), and that serverless function 404s for this free
    account. Pinning the model is a LANE-side availability fix only — the real
    routing chain, fallback walk, and response.provider stamping are untouched.
    The served provider identity (response.provider) still comes from the REAL
    router, not from this wrapper."""

    def __init__(self, inner, model):
        self._inner = inner
        self._model = model

    async def complete(self, request):
        from dataclasses import replace as _dc_replace
        try:
            req = request.model_copy(update={"model": self._model})  # pydantic
        except AttributeError:
            req = _dc_replace(request, model=self._model)
        return await self._inner.complete(req)

    def __getattr__(self, name):
        return getattr(self._inner, name)


async def prove_fallback(orch, dead_type, live_type, live_model, env_overrides=None) -> dict:
    from dharma_swarm.providers import ModelRouter, RetryPolicy

    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    live_cfg = resolve_runtime_provider_config(live_type, model=live_model, env=env)
    live_provider = create_runtime_provider(live_cfg)
    pinned_model = live_cfg.default_model or live_model or ""
    live_provider = PinnedModelProvider(live_provider, pinned_model)

    providers = {dead_type: DeadProvider(), live_type: live_provider}
    # max_attempts=1: one attempt per provider = honest fallback semantics
    # (dead fails once -> try next).
    router = ModelRouter(providers=providers, retry_policy=RetryPolicy(max_attempts=1))

    # Configured primary = the DEAD provider. The metadata allowlist limits the
    # router to exactly {dead, live}; the real policy router then SELECTS the
    # dead provider as primary (dead_type ranks first in the free hierarchy),
    # so the real chain attempts it FIRST and falls through to the live one when
    # its .complete() raises. Verified in isolation: chain=[dead, live],
    # response.provider==live.
    routing_meta = {
        "available_provider_types": [dead_type.value, live_type.value],
        "preferred_provider": dead_type.value,
        # Pin the live provider's known-good model so the router does not
        # substitute a stale serverless-function model on the fallback hop.
        "preferred_model": live_cfg.default_model or live_model or "",
        "preserve_requested_model": True,
    }
    cfg = AgentConfig(
        name="served_prover_fallback",
        id="served_prover_fallback",
        provider=dead_type,                 # CONFIGURED = dead
        model=live_cfg.default_model or live_model or "",
        metadata=dict(routing_meta),
    )
    runner = AgentRunner(config=cfg, provider=router)
    out = await dispatch_via_spine_with_meta(
        orch, runner, cfg, routing_meta,
        "[fallback] reply with one short sentence about banks of a river.",
    )

    served_p = (out["served_provider"] or "").lower()
    rcpt_p = (out["receipt_provider"] or "").lower()

    fallback_proven = (
        out["status"] == "completed"
        and out["result_chars"] > 0
        and (out["receipt_latency_ms"] or 0) > 0
        and rcpt_p == live_type.value.lower()       # receipt names SERVED (live)
        and rcpt_p != dead_type.value.lower()       # NOT the configured-dead
        and served_p == live_type.value.lower()
    )
    out.update({
        "label": "fallback",
        "regime": "fallback",
        "configured_dead_provider": dead_type.value,
        "served_live_provider": live_type.value,
        "receipt_names_served_not_dead": bool(fallback_proven),
        "result_preview": (out["result"] or "")[:80],
    })
    out.pop("result", None)
    return out


async def main() -> dict:
    LANE_DIR.mkdir(parents=True, exist_ok=True)
    if LANE_DB.exists():
        LANE_DB.unlink()
    orch = Orchestrator(runtime_db_path=LANE_DB)

    results = []

    # --- B) FALLBACK FIRST (run while nvidia_nim is fresh / not burst-throttled).
    # configured-dead (ollama) -> served-live (nvidia_nim).
    # ollama ranks #1 in the free hierarchy, so the REAL policy router selects
    # the (dead) ollama provider as primary -> chain=[ollama, nvidia_nim]. The
    # dead ollama .complete() raises, the router walks to nvidia_nim, which
    # serves. response.provider == 'nvidia_nim' (the SERVED brain), NOT the
    # configured-dead ollama. nvidia's serverless function can cold-404 under a
    # retry burst; retry the whole fallback dispatch once on that transient.
    fb = None
    for attempt in range(3):
        fb = await prove_fallback(orch, ProviderType.OLLAMA, ProviderType.NVIDIA_NIM, None)
        if fb.get("receipt_names_served_not_dead"):
            break
        await asyncio.sleep(5)
    fb["fallback_attempts"] = attempt + 1
    results.append(fb)

    # --- A) Per-provider real-path proofs (free only) ---
    # ollama LOCAL (free, localhost mistral) — distinct serving backend.
    results.append(await prove_provider(
        orch, "ollama_local", ProviderType.OLLAMA, "mistral:latest",
        env_overrides={"OLLAMA_FORCE_LOCAL": "1", "OLLAMA_BASE_URL": "http://localhost:11434"},
    ))
    # ollama CLOUD (free subscription, glm-5:cloud) — distinct serving backend.
    results.append(await prove_provider(
        orch, "ollama_cloud_glm5", ProviderType.OLLAMA, "glm-5:cloud",
        env_overrides={"OLLAMA_USE_CLOUD": "1"},
    ))
    # ollama CLOUD deepseek (free subscription) — distinct model family.
    results.append(await prove_provider(
        orch, "ollama_cloud_deepseek", ProviderType.OLLAMA, "deepseek-v3.2:cloud",
        env_overrides={"OLLAMA_USE_CLOUD": "1"},
    ))
    # ollama CLOUD qwen-coder (free subscription) — distinct model family.
    results.append(await prove_provider(
        orch, "ollama_cloud_qwen", ProviderType.OLLAMA, "qwen3-coder:480b-cloud",
        env_overrides={"OLLAMA_USE_CLOUD": "1"},
    ))
    # nvidia_nim (FREE tier, 50 req/day).
    results.append(await prove_provider(
        orch, "nvidia_nim", ProviderType.NVIDIA_NIM, None,
    ))

    return {"results": results, "db_path": str(LANE_DB)}


if __name__ == "__main__":
    import json
    out = asyncio.run(main())
    print("PROOF_JSON_START")
    print(json.dumps(out, indent=2, default=str))
    print("PROOF_JSON_END")
