"""Live cycle — the first honest real signal: the army actually calls models.

Dry mode proves the loop runs; this proves it runs on REAL model output,
objectively scored. It calls an OpenAI-compatible free lane (Groq / Cerebras /
OpenRouter-free / NVIDIA NIM) using the provider key from the environment, runs
a FROZEN deterministic benchmark whose answers the model cannot self-grade
(reality = the known outputs), and reports accuracy. Free lanes cost $0; paid
lanes (Moonshot/Zhipu) are metered — exact token counts from the API response,
priced at a documented UPPER-BOUND rate — and the estimate flows into
``CampaignResult.spend_usd`` so the daemon's budget guard sees real spend.

Deliberately stdlib-only (``urllib``) so it deploys to a bare host with no pip
install and imports without the heavy stack. This is smoke-grade real signal —
an internal capability probe, not yet an external One Wire receipt. The harder
external targets (kernel/eval-harness benchmarks) need isolation and come next;
this is the honest first rung from rehearsal to real.
"""

from __future__ import annotations

import json
import os
import socket
import time
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
    ("moonshot", "https://api.moonshot.ai/v1", "MOONSHOT_API_KEY", "moonshot-v1-8k"),
    ("zhipu", "https://api.z.ai/api/coding/paas/v4", "ZHIPU_API_KEY", "glm-4.6"),
    ("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", ""),
    ("nvidia", "https://integrate.api.nvidia.com/v1", "NVIDIA_NIM_API_KEY", ""),
)


@dataclass(frozen=True)
class ProviderRoute:
    """One credential-bound OpenAI-compatible route (the key is never rendered)."""

    name: str
    base_url: str
    key: str = field(repr=False)
    default_model: str = ""


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    model: str
    content: str
    total_tokens: int


class ProviderCallError(RuntimeError):
    """Typed, secret-free provider failure used by routing and receipts."""

    def __init__(
        self,
        provider: str,
        category: str,
        *,
        retryable: bool,
        status_code: int | None = None,
        billable_tokens: int = 0,
    ) -> None:
        self.provider = provider
        self.category = category
        self.retryable = retryable
        self.status_code = status_code
        self.billable_tokens = max(0, int(billable_tokens))
        status = f" status={status_code}" if status_code is not None else ""
        super().__init__(f"provider={provider} category={category}{status}")


class ProviderExhausted(RuntimeError):
    """All configured routes failed or had an open circuit."""

    def __init__(self, failures: tuple[ProviderCallError, ...]) -> None:
        self.failures = failures
        summary = ", ".join(f"{f.provider}:{f.category}" for f in failures) or "no-route"
        super().__init__(f"provider routes exhausted ({summary})")

    @property
    def billable_tokens(self) -> int:
        return sum(f.billable_tokens for f in self.failures)


def _typed_provider_error(provider: str, exc: BaseException) -> ProviderCallError:
    """Classify an exception without copying response bodies, URLs, or secrets."""
    if isinstance(exc, ProviderCallError):
        return exc
    if isinstance(exc, urllib.error.HTTPError):
        code = int(exc.code)
        if code in (401, 403):
            category, retryable = "authentication", False
        elif code == 429:
            category, retryable = "rate_limited", True
        elif code >= 500:
            category, retryable = "provider_unavailable", True
        else:
            category, retryable = "http_rejected", False
        return ProviderCallError(provider, category, retryable=retryable, status_code=code)
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return ProviderCallError(provider, "timeout", retryable=True)
    if isinstance(exc, (urllib.error.URLError, ConnectionError, OSError)):
        return ProviderCallError(provider, "network", retryable=True)
    if isinstance(exc, (KeyError, TypeError, ValueError, json.JSONDecodeError)):
        return ProviderCallError(provider, "invalid_response", retryable=False)
    return ProviderCallError(provider, "unexpected", retryable=False)


@dataclass
class _Circuit:
    failures: int = 0
    opened_at: float = 0.0


class ProviderPool:
    """Bounded failover with a per-route circuit breaker.

    A failed route is opened after ``failure_threshold`` consecutive failures.
    It is retried only after ``cooldown_seconds``. Failed zero-token calls add
    exactly zero to ``total_tokens`` and therefore zero to spend accounting.
    """

    def __init__(
        self,
        *,
        env: dict | None = None,
        failure_threshold: int = 1,
        cooldown_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
        chat_caller: Callable[..., tuple[str, int]] | None = None,
        model_lister: Callable[[ProviderRoute], list[str]] | None = None,
    ) -> None:
        source = env if env is not None else os.environ
        self.routes = tuple(
            ProviderRoute(name, base, str(source[key_env]), default_model)
            for name, base, key_env, default_model in PROVIDERS
            if source.get(key_env)
        )
        self.failure_threshold = max(1, int(failure_threshold))
        self.cooldown_seconds = max(0.0, float(cooldown_seconds))
        self.clock = clock
        self.chat_caller = chat_caller or self._call_route
        self.model_lister = model_lister or (
            lambda route: list_models(route.base_url, route.key)
        )
        self.circuits = {route.name: _Circuit() for route in self.routes}
        self.total_tokens = 0
        self.tokens_by_provider: dict[str, int] = {}
        self.successful_calls = 0

    @staticmethod
    def _call_route(
        route: ProviderRoute,
        model: str,
        prompt: str,
        **kwargs,
    ) -> tuple[str, int]:
        return call_chat(
            route.base_url,
            route.key,
            model,
            prompt,
            provider=route.name,
            **kwargs,
        )

    def _is_open(self, route: ProviderRoute) -> bool:
        circuit = self.circuits[route.name]
        if circuit.failures < self.failure_threshold:
            return False
        if (self.clock() - circuit.opened_at) >= self.cooldown_seconds:
            circuit.failures = 0
            circuit.opened_at = 0.0
            return False
        return True

    def call(
        self,
        prompt: str,
        *,
        model_hint: str = "",
        max_tokens: int = 64,
        temperature: float = 0.0,
        timeout: float = 45.0,
    ) -> ProviderResponse:
        failures: list[ProviderCallError] = []
        for route in self.routes:
            if self._is_open(route):
                failures.append(
                    ProviderCallError(route.name, "circuit_open", retryable=True)
                )
                continue
            try:
                model = (
                    model_hint
                    or choose_model(self.model_lister(route))
                    or route.default_model
                )
                if not model:
                    raise ProviderCallError(
                        route.name, "no_usable_model", retryable=False
                    )
                content, tokens = self.chat_caller(
                    route,
                    model,
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=timeout,
                )
            except Exception as exc:  # noqa: BLE001 - classified, bounded failover
                error = _typed_provider_error(route.name, exc)
                failures.append(error)
                self.total_tokens += error.billable_tokens
                self.tokens_by_provider[route.name] = (
                    self.tokens_by_provider.get(route.name, 0) + error.billable_tokens
                )
                circuit = self.circuits[route.name]
                circuit.failures += 1
                circuit.opened_at = self.clock()
                continue
            circuit = self.circuits[route.name]
            circuit.failures = 0
            circuit.opened_at = 0.0
            safe_tokens = max(0, int(tokens))
            self.total_tokens += safe_tokens
            self.tokens_by_provider[route.name] = (
                self.tokens_by_provider.get(route.name, 0) + safe_tokens
            )
            self.successful_calls += 1
            return ProviderResponse(route.name, model, content, safe_tokens)
        raise ProviderExhausted(tuple(failures))


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


# Deliberate UPPER BOUNDS in USD per 1M tokens (not list prices): honest
# accounting overstates spend rather than hiding it. Free lanes are 0.0;
# unknown lanes assume the worst.
UPPER_BOUND_USD_PER_MTOK: dict[str, float] = {
    "groq": 0.0,
    "cerebras": 0.0,
    "openrouter": 0.0,
    "nvidia": 0.0,
    "moonshot": 3.0,
    "zhipu": 3.0,
}
_UNKNOWN_LANE_USD_PER_MTOK = 5.0


def estimate_cost_usd(provider: str, total_tokens: int) -> float:
    rate = UPPER_BOUND_USD_PER_MTOK.get(provider, _UNKNOWN_LANE_USD_PER_MTOK)
    return round(total_tokens * rate / 1_000_000, 6)


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
    if not url.startswith("https://"):
        raise ValueError(f"Only HTTPS URLs are permitted; got: {url!r}")
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
    # Prefer stable, non-thinking chat models that answer a short prompt cleanly.
    prefs = ("moonshot-v1-8k", "llama-3.3-70b", "llama-3.3", "gpt-oss-120b", "glm-4-flash",
             "glm-4", "qwen", "moonshot-v1", "kimi-k2.5", "kimi-k2", "llama-3.1-8b",
             "llama3.1-8b", "llama")
    chat = [m for m in models if not any(
        bad in m.lower() for bad in
        ("whisper", "embed", "tts", "guard", "vision", "rerank", "code", "highspeed", "auto")
    )]
    for pref in prefs:
        for m in chat:
            if pref in m.lower():
                return m
    return chat[0] if chat else (models[0] if models else "")


def call_chat(base_url: str, key: str, model: str, prompt: str, *,
              timeout: float = 45.0, max_tokens: int = 64,
              temperature: float = 0.0, provider: str = "unknown") -> tuple[str, int]:
    """Returns (content, total_tokens) — token count straight from the API's usage block.

    The tiny default ``max_tokens`` fits the frozen heartbeat benchmark;
    mutation proposals (unified diffs) pass a much larger budget.
    """
    try:
        data = _http_json(
            f"{base_url}/chat/completions", key,
            payload={
                "model": model, "temperature": temperature, "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            method="POST", timeout=timeout,
        )
        content = data["choices"][0]["message"]["content"] or ""
        tokens = int((data.get("usage") or {}).get("total_tokens") or 0)
        return content, tokens
    except Exception as exc:  # noqa: BLE001 - converted to secret-free typed failure
        raise _typed_provider_error(provider, exc) from exc


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
    total_tokens: int = 0
    est_cost_usd: float = 0.0
    tokens_by_provider: dict[str, int] = field(default_factory=dict)
    provider_failures: int = 0


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
    usage_tokens: list[int] = []

    pool = ProviderPool(env=env) if caller is None else None
    routed: list[tuple[str, str]] = []

    def _default_call(m: str, p: str) -> str:
        assert pool is not None
        response = pool.call(p, model_hint=m)
        usage_tokens.append(response.total_tokens)
        routed.append((response.provider, response.model))
        return response.content

    call = caller or _default_call

    if model is None:
        # The provider pool must resolve a model independently per route; a
        # Moonshot model name is not valid evidence that Zhipu can serve it.
        model = "" if caller is None and model_lister is None else (
            choose_model(lister()) or default_model
        )
        if caller is not None and not model:
            return LiveResult(name, "none", 0, 0, 0.0, error="no usable chat model listed")

    correct = 0
    provider_failures = 0
    per: list = []
    for task in FROZEN_TASKS:
        try:
            resp = call(model, task.prompt)
            ok = _norm(resp) == task.answer or task.answer in _norm(resp)
        except Exception as exc:  # noqa: BLE001 - typed miss evidence, not a crash
            if isinstance(exc, ProviderExhausted):
                provider_failures += 1
            per.append({"prompt": task.prompt, "ok": False, "error": type(exc).__name__})
            continue
        correct += 1 if ok else 0
        per.append({"prompt": task.prompt, "ok": ok})
    n = len(FROZEN_TASKS)
    provider_tokens = (
        dict(pool.tokens_by_provider)
        if pool is not None
        else ({name: sum(usage_tokens)} if usage_tokens else {})
    )
    tokens = sum(provider_tokens.values())
    cost = round(sum(
        estimate_cost_usd(provider, count)
        for provider, count in provider_tokens.items()
    ), 6)
    if routed:
        name, model = routed[-1]
    return LiveResult(
        name, model, n, correct, (correct / n) if n else 0.0, per,
        total_tokens=tokens, est_cost_usd=cost, tokens_by_provider=provider_tokens,
        provider_failures=provider_failures,
    )


def _latest_receipt(root: Path) -> Path | None:
    records = _live_records(root)
    return records[-1][0] if records else None


def _live_records(root: Path) -> list[tuple[Path, dict]]:
    records: list[tuple[Path, dict]] = []
    for path in sorted(root.glob(f"{BENCHMARK_ID}_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            data = {}
        records.append((path, data))
    legacy = [item for item in records if int(item[1].get("sequence", 0) or 0) <= 0]
    chained = [item for item in records if int(item[1].get("sequence", 0) or 0) > 0]
    chained.sort(key=lambda item: int(item[1]["sequence"]))
    return legacy + chained


def _chain_prev_digest(root: Path) -> str:
    """Digest of the newest existing receipt, or the genesis marker.

    Each receipt embeds its predecessor's digest, forming a hash chain:
    rewriting any historical receipt breaks every digest after it. This is
    tamper-EVIDENT, not tamper-proof (see the honest gap note in
    docs/foundry/ — local disk is still rewritable wholesale; ring 3 anchors
    in venues we don't control remain the strongest link).
    """
    records = _live_records(root)
    if not records:
        return "genesis"
    return str(records[-1][1].get("digest", "genesis"))


def write_live_receipt(result: LiveResult, *, state_root: Path) -> Path:
    from dharma_swarm.foundry.evaluator import canonical_digest
    from dharma_swarm.foundry.receipts import ReceiptChainError, _chain_lock

    root = Path(state_root) / "live_eval"
    root.mkdir(parents=True, exist_ok=True)
    with _chain_lock(root):
        ok, detail = verify_live_chain(Path(state_root))
        if not ok:
            raise ReceiptChainError(f"refusing to append live receipt: {detail}")
        records = _live_records(root)
        sequences = [int(data.get("sequence", 0) or 0) for _, data in records]
        sequence = max(sequences, default=0) + 1
        stamp = result.ran_at.replace(":", "").replace("-", "")[:15]
        payload = {
            "benchmark": BENCHMARK_ID,
            "sequence": sequence,
            "provider": result.provider,
            "model": result.model,
            "tasks": result.tasks,
            "correct": result.correct,
            "accuracy": result.accuracy,
            "per_task": result.per_task,
            "error": result.error,
            "ran_at": result.ran_at,
            "total_tokens": result.total_tokens,
            "est_cost_usd_upper_bound": result.est_cost_usd,
            "tokens_by_provider": result.tokens_by_provider,
            "prev_digest": _chain_prev_digest(root),
        }
        payload["digest"] = canonical_digest(payload)
        short = payload["digest"].removeprefix("sha256:")[:16]
        path = root / f"{BENCHMARK_ID}_{sequence:08d}__{stamp}__{short}.json"
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return path


def verify_live_chain(state_root: Path) -> tuple[bool, str]:
    """Walk the live-receipt chain; return (ok, detail).

    Recomputes every digest and checks each ``prev_digest`` pointer. Any
    rewritten or deleted-in-the-middle receipt surfaces as a break.
    """
    from dharma_swarm.foundry.evaluator import canonical_digest

    root = Path(state_root) / "live_eval"
    receipts = _live_records(root)
    expected_prev = "genesis"
    expected_sequence = 1
    for path, data in receipts:
        if not data:
            return False, f"unreadable receipt at {path.name}"
        claimed = data.get("digest", "")
        if "prev_digest" not in data:
            # Pre-chain receipt (before this feature): treat as chain genesis.
            expected_prev = claimed or "genesis"
            continue
        sequence = int(data.get("sequence", 0) or 0)
        if sequence > 0:
            if sequence != expected_sequence:
                return False, (
                    f"chain break at {path.name}: sequence "
                    f"expected={expected_sequence} actual={sequence}"
                )
            expected_sequence += 1
        if data["prev_digest"] != expected_prev:
            return False, f"chain break at {path.name}: prev_digest mismatch"
        body = {k: v for k, v in data.items() if k != "digest"}
        if canonical_digest(body) != claimed:
            return False, f"tampered receipt at {path.name}: digest mismatch"
        expected_prev = claimed
    return True, f"chain intact over {len(receipts)} receipts"


def live_daemon_cycle(target_id: str, generations: int, budget_cap: float,
                      state_root: "Path | None"):
    """Daemon cycle that runs the live eval and maps it to a CampaignResult.

    ``mean_survival`` carries the model's accuracy so the standing kill-metrics
    treat an accuracy collapse as a real survival_collapse signal.
    ``spend_usd`` carries the metered upper-bound cost so the daemon's budget
    guard accounts for paid lanes honestly (free lanes stay $0).
    """
    from dharma_swarm.foundry.campaign import CampaignResult

    result = run_live_eval()
    sr = Path(state_root) if state_root is not None else Path.cwd()
    if not result.error:
        write_live_receipt(result, state_root=sr)
    return CampaignResult(
        target_id=f"live:{result.provider}:{result.model}",
        generations_run=1,
        proposed=max(0, result.tasks - result.provider_failures),
        provider_failures=result.provider_failures,
        ring1_wins=result.correct,
        ring2_checked=result.tasks,
        ring2_survivors=result.correct,
        best_fitness=result.accuracy,
        mean_survival=result.accuracy,
        spend_usd=result.est_cost_usd,
    )
