"""Live worker pool for arena measurement over zero-cost Ollama lanes.

This is the live seam ``fixtures.FixturePool`` deliberately left unbuilt
(spec §3, §11): a worker-response source backed by the LOCAL Ollama daemon
(which also proxies ``:cloud`` models when the daemon is signed in). It is
NEVER the default arena path — the hermetic ``FixturePool`` remains the
default; a live pool must be constructed explicitly by the measurement CLI
(``dharma_swarm.coordination.arena.measure``).

Anti-corruption properties (mirrors the fixture pool's boundary):
  * The pool is constructed from the taskpack's PUBLIC view only — it never
    holds or reads sealed labels, so the candidate path cannot be contaminated
    through it. Correctness stays with the scorer alone.
  * FAIL CLOSED: any provider error raises ``LiveDispatchError``. There is no
    silent fallback to fixtures or to another model — a half-live run can
    never masquerade as a measurement (kill-list doctrine).
  * Budget parity instrumentation: every call carries the SAME per-call token
    cap (``per_call_cap`` -> Ollama ``num_predict``) and the measured token
    spend (prompt_eval_count + eval_count) becomes ``WorkerResponse.cost``, so
    the runner's parity ledger reports real measured tokens. Provider-reported
    completion tokens must stay within that cap.
  * Roster identity is fail-closed: the model identity returned by the provider
    must exactly match the requested seat and is bound into every call receipt.
  * Determinism/replayability: temperature is 0.0 and every unique
    ``(model_id, task_id)`` response is cached and recorded. Repeat dispatches
    (self-MoA, the parity control's resamples) replay the cached sample —
    at temperature 0 a resample is the same draw, the cache just makes that
    exact — while still billing the granted budget per dispatch, so parity
    accounting stays honest with zero extra network spend. The recorded
    receipts feed ``RecordedReplayPool`` for offline re-runs.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Optional

from dharma_swarm.coordination.arena.fixtures import WorkerResponse
from dharma_swarm.ollama_config import OLLAMA_LOCAL_BASE_URL

# Public prompt view entry: {"task_id": ..., "family": ..., "prompt": ...}
PublicTask = dict[str, str]

# One instruction for every seat and every arm — no per-model prompt tuning,
# which would be an uncontrolled advantage for whichever arm got the better
# prompt. Mechanical and label-blind.
ANSWER_INSTRUCTION = (
    "Answer with ONLY the final answer. No explanation, no punctuation, "
    "no units, no restating the question. If the answer is a word, use "
    "lowercase."
)

RECORDED_SCHEMA = "orchestration_arena_v1_live_receipts.v1"

Transport = Callable[[str, dict[str, Any], float], dict[str, Any]]


class LiveDispatchError(RuntimeError):
    """A live worker call failed. The run must fail closed — never fall back."""


def _urllib_transport(
    url: str, payload: dict[str, Any], timeout: float
) -> dict[str, Any]:
    """Default HTTP transport (stdlib-only, injectable for tests)."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (http(s) only)
        return json.loads(resp.read().decode("utf-8"))


def clean_answer(raw: str) -> str:
    """Mechanical, label-blind normalization of a model's free-text answer.

    Strips markdown/quote wrappers, a leading "the answer is", and a trailing
    period; keeps the LAST non-empty line (models sometimes prefix a
    restatement even when told not to). Never consults any label.
    """
    text = (raw or "").strip()
    if not text:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    text = lines[-1] if lines else ""
    text = text.strip("`").strip()
    for quote in ('"', "'"):
        if len(text) >= 2 and text.startswith(quote) and text.endswith(quote):
            text = text[1:-1].strip()
    lowered = text.lower()
    for prefix in ("the answer is", "answer:", "answer is"):
        if lowered.startswith(prefix):
            text = text[len(prefix) :].strip(" :")
            break
    if text.endswith("."):
        text = text[:-1].strip()
    return text


class LiveWorkerPool:
    """Live worker-response source over the local Ollama daemon (opt-in only)."""

    mode = "live_ollama"

    def __init__(
        self,
        public_tasks: list[PublicTask],
        *,
        base_url: str = OLLAMA_LOCAL_BASE_URL,
        per_call_cap: int = 64,
        temperature: float = 0.0,
        timeout: float = 180.0,
        transport: Optional[Transport] = None,
    ) -> None:
        # PUBLIC view only: {task_id: prompt}. No labels can enter this pool.
        self._prompts = {t["task_id"]: t["prompt"] for t in public_tasks}
        self.base_url = base_url.rstrip("/")
        self.per_call_cap = int(per_call_cap)
        self.temperature = float(temperature)
        self.timeout = float(timeout)
        self._transport = transport or _urllib_transport
        self._cache: dict[tuple[str, str], WorkerResponse] = {}
        self.call_receipts: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ dispatch
    def dispatch(self, model_id: str, task_id: str) -> WorkerResponse:
        """Return the (cached) live response for ``(model_id, task_id)``.

        Raises ``LiveDispatchError`` on any provider failure — fail closed.
        """
        key = (model_id, task_id)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        prompt = self._prompts.get(task_id)
        if prompt is None:
            raise LiveDispatchError(f"unknown task_id {task_id!r} (not in public view)")
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": ANSWER_INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                # Identical decode settings for every seat and every arm — this
                # IS the per-call half of the budget-parity contract.
                "temperature": self.temperature,
                "num_predict": self.per_call_cap,
            },
        }
        t0 = time.time()
        try:
            data = self._transport(f"{self.base_url}/api/chat", payload, self.timeout)
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            OSError,
            TimeoutError,
        ) as exc:
            raise LiveDispatchError(
                f"live dispatch failed for model={model_id!r} task={task_id!r}: {exc}"
            ) from exc
        message = data.get("message") or {}
        raw = str(message.get("content") or "").strip()
        if not raw:
            # Thinking models may put output in "thinking" with empty content.
            raw = str(message.get("thinking") or "").strip()
        answer = clean_answer(raw)
        provider_model_id = str(data.get("model") or "").strip()
        if provider_model_id != model_id:
            disclosed = provider_model_id or "<missing>"
            raise LiveDispatchError(
                "provider model identity mismatch for "
                f"requested={model_id!r} returned={disclosed!r} task={task_id!r}"
            )
        prompt_tokens = int(data.get("prompt_eval_count") or 0)
        completion_tokens = int(data.get("eval_count") or 0)
        if completion_tokens < 0 or completion_tokens > self.per_call_cap:
            raise LiveDispatchError(
                "provider completion token cap violated for "
                f"model={model_id!r} task={task_id!r}: "
                f"observed={completion_tokens} cap={self.per_call_cap}"
            )
        cost = prompt_tokens + completion_tokens
        if cost <= 0:
            # A zero-token "success" is not a measurement — refuse it.
            raise LiveDispatchError(
                f"no token accounting returned for model={model_id!r} task={task_id!r}"
            )
        response = WorkerResponse(
            model_id=model_id, task_id=task_id, answer=answer, cost=cost
        )
        self._cache[key] = response
        self.call_receipts.append(
            {
                "model_id": model_id,
                "provider_model_id": provider_model_id,
                "task_id": task_id,
                "raw_answer": raw,
                "answer": answer,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost": cost,
                "latency_s": round(time.time() - t0, 3),
            }
        )
        return response

    # ------------------------------------------------------------------ receipts
    def receipts_payload(self) -> dict[str, Any]:
        return {
            "schema": RECORDED_SCHEMA,
            "base_url": self.base_url,
            "per_call_cap": self.per_call_cap,
            "temperature": self.temperature,
            "responses": self.call_receipts,
        }

    def write_receipts(self, path: Path) -> None:
        path.write_text(
            json.dumps(self.receipts_payload(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


class RecordedReplayPool:
    """Replay a recorded live run from its receipts file (offline, exact)."""

    mode = "live_ollama_replay"

    def __init__(self, payload: dict[str, Any]) -> None:
        if payload.get("schema") != RECORDED_SCHEMA:
            raise LiveDispatchError(
                f"unexpected receipts schema: {payload.get('schema')!r}"
            )
        self.per_call_cap = int(payload.get("per_call_cap") or 0)
        self._responses: dict[tuple[str, str], WorkerResponse] = {}
        for row in payload.get("responses", []):
            key = (str(row["model_id"]), str(row["task_id"]))
            self._responses[key] = WorkerResponse(
                model_id=key[0],
                task_id=key[1],
                answer=str(row["answer"]),
                cost=int(row["cost"]),
            )

    @classmethod
    def from_file(cls, path: Path) -> "RecordedReplayPool":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def dispatch(self, model_id: str, task_id: str) -> WorkerResponse:
        resp = self._responses.get((model_id, task_id))
        if resp is None:
            # Fail closed: a replay must never invent an answer.
            raise LiveDispatchError(
                f"no recorded response for model={model_id!r} task={task_id!r}"
            )
        return resp


__all__ = [
    "ANSWER_INSTRUCTION",
    "RECORDED_SCHEMA",
    "LiveDispatchError",
    "LiveWorkerPool",
    "PublicTask",
    "RecordedReplayPool",
    "clean_answer",
]
