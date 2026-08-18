"""Live cycle — the first honest real signal: the army actually calls models.

Dry mode proves the loop runs; this proves it runs on REAL model output,
objectively scored. It calls an OpenAI-compatible free lane (Groq / Cerebras /
OpenRouter-free / NVIDIA NIM) using the provider key from the environment, runs
a FROZEN deterministic benchmark whose answers the model cannot self-grade
(reality = the known outputs), and reports accuracy. Free lanes cost $0.

Deliberately stdlib-only (``urllib``) so it deploys to a bare host with no pip
install and imports without the heavy stack. This is smoke-grade real signal —
an internal capability probe, not yet an external One Wire receipt. The harder
external targets (kernel/eval-harness benchmarks) need isolation and come next;
this is the honest first rung from rehearsal to real.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

# OpenAI-compatible lanes, in preference order: (name, base_url, key_env,
# default_model). Free lanes first ($0), then first-party paid lanes whose keys
# the operator actually holds (Moonshot/Kimi, Zhipu/GLM). default_model is a
# fallback used only when the provider's /models listing is unavailable.
PROVIDERS: tuple[tuple[str, str, str, str], ...] = (
    ("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY", ""),
    ("cerebras", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", ""),
    ("moonshot", "https://api.moonshot.ai/v1", "MOONSHOT_API_KEY", "kimi-k2-0711-preview"),
    ("zhipu", "https://api.z.ai/api/coding/paas/v4", "ZHIPU_API_KEY", "glm-4.6"),
    ("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", ""),
    ("nvidia", "https://integrate.api.nvidia.com/v1", "NVIDIA_NIM_API_KEY", ""),
)


@dataclass(frozen=True)
class Task:
    prompt: str
    answer: str  # normalized (alnum, lowercase) expected answer


# A tiny frozen, deterministic benchmark. Reality owns the answers; the model
# must actually compute/know them — it cannot grade itself. Versioned by content.
FROZEN_TASKS: tuple[Task, ...] = (
    Task("Reply with ONLY the integer result and nothing else: 17 * 23", "391"),
    Task("Reply with ONLY the integer and nothing else, the value printed by: print(sum(range(10)))", "45"),
    Task("Reply with ONLY one lowercase word and no punctuation: the capital city of Japan", "tokyo"),
    Task("Reply with ONLY the integer number of bits in one byte and nothing else", "8"),
    Task("Reply with ONLY the integer and nothing else: the length of the string 'dharma'", "6"),
)
BENCHMARK_ID = "foundry_live_frozen_v1"


def _norm(text: str) -> str:
    return "".join(ch for ch in text.strip().lower() if ch.isalnum())


def pick_provider(env: dict | None = None) -> tuple[str, str, str, str] | None:
    """First lane whose key is present in the environment.

    Returns (name, base_url, key, default_model).
    """
    env = env if env is not None else os.environ
    for name, base, key_env, default_model in PROVIDERS:
        key = env.get(key_env)
        if key:
            return name, base, key, default_model
    return None


def _http_json(url: str, key: str, *, payload: dict | None = None,
               method: str = "GET", timeout: float = 45.0) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted provider URLs)
        return json.loads(resp.read().decode("utf-8"))


def list_models(base_url: str, key: str, *, timeout: float = 30.0) -> list[str]:
    try:
        data = _http_json(f"{base_url}/models", key, timeout=timeout)
        return [m.get("id") for m in data.get("data", []) if m.get("id")]
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return []


def choose_model(models: Sequence[str]) -> str:
    """Pick a small, general chat model; skip non-chat (whisper/embed/tts/guard)."""
    prefs = ("llama-3.3-70b", "llama-3.3", "gpt-oss-120b", "qwen", "kimi", "moonshot",
             "glm", "llama-3.1-8b", "llama3.1-8b", "llama")
    chat = [m for m in models if not any(
        bad in m.lower() for bad in ("whisper", "embed", "tts", "guard", "vision", "rerank")
    )]
    for pref in prefs:
        for m in chat:
            if pref in m.lower():
                return m
    return chat[0] if chat else (models[0] if models else "")


def call_chat(base_url: str, key: str, model: str, prompt: str, *, timeout: float = 45.0) -> str:
    data = _http_json(
        f"{base_url}/chat/completions", key,
        payload={
            "model": model, "temperature": 0, "max_tokens": 32,
            "messages": [{"role": "user", "content": prompt}],
        },
        method="POST", timeout=timeout,
    )
    return data["choices"][0]["message"]["content"] or ""


@dataclass
class LiveResult:
    provider: str
    model: str
    tasks: int
    correct: int
    accuracy: float
    per_task: list = field(default_factory=list)
    error: str = ""
    ran_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def run_live_eval(
    *,
    env: dict | None = None,
    model: str | None = None,
    caller: Callable[[str, str], str] | None = None,
    model_lister: Callable[[], list[str]] | None = None,
) -> LiveResult:
    """Run the frozen benchmark against a real free-lane model. Injectable for tests."""
    env = env if env is not None else os.environ
    picked = pick_provider(env)
    if picked is None:
        return LiveResult("none", "none", 0, 0, 0.0, error="no provider key present")
    name, base, key, default_model = picked
    lister = model_lister or (lambda: list_models(base, key))
    call = caller or (lambda m, p: call_chat(base, key, m, p))

    if model is None:
        model = choose_model(lister()) or default_model
        if not model:
            return LiveResult(name, "none", 0, 0, 0.0, error="no usable chat model listed")

    correct = 0
    per: list = []
    for task in FROZEN_TASKS:
        try:
            resp = call(model, task.prompt)
            ok = _norm(resp) == task.answer or task.answer in _norm(resp)
        except Exception as exc:  # noqa: BLE001 - a failed call is a scored miss, not a crash
            per.append({"prompt": task.prompt, "ok": False, "error": type(exc).__name__})
            continue
        correct += 1 if ok else 0
        per.append({"prompt": task.prompt, "ok": ok})
    n = len(FROZEN_TASKS)
    return LiveResult(name, model, n, correct, (correct / n) if n else 0.0, per)


def write_live_receipt(result: LiveResult, *, state_root: Path) -> Path:
    root = Path(state_root) / "live_eval"
    root.mkdir(parents=True, exist_ok=True)
    stamp = result.ran_at.replace(":", "").replace("-", "")[:15]
    path = root / f"{BENCHMARK_ID}_{stamp}.json"
    path.write_text(json.dumps({
        "benchmark": BENCHMARK_ID,
        "provider": result.provider,
        "model": result.model,
        "tasks": result.tasks,
        "correct": result.correct,
        "accuracy": result.accuracy,
        "per_task": result.per_task,
        "error": result.error,
        "ran_at": result.ran_at,
    }, indent=2), encoding="utf-8")
    return path


def live_daemon_cycle(target_id: str, generations: int, budget_cap: float,
                      state_root: "Path | None"):
    """Daemon cycle that runs the live eval and maps it to a CampaignResult.

    ``mean_survival`` carries the model's accuracy so the standing kill-metrics
    treat an accuracy collapse as a real survival_collapse signal. Free lanes
    keep spend at $0.
    """
    from dharma_swarm.foundry.campaign import CampaignResult

    result = run_live_eval()
    sr = Path(state_root) if state_root is not None else Path.cwd()
    if not result.error:
        write_live_receipt(result, state_root=sr)
    return CampaignResult(
        target_id=f"live:{result.provider}:{result.model}",
        generations_run=1,
        proposed=result.tasks,
        ring1_wins=result.correct,
        ring2_checked=result.tasks,
        ring2_survivors=result.correct,
        best_fitness=result.accuracy,
        mean_survival=result.accuracy,
        spend_usd=0.0,
    )
