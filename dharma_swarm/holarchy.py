"""Falsifiable Holarchy — the acceptance test, as running code.

Doctrine (operator-locked 2026-06-18; memory ``feedback_falsifiable_holarchy``):
a system proves its own coherence *from the inside* not by self-authored passing
tests, but by **independent, decorrelated holons that can falsify each other**.

This module is the smallest runnable instance of that law. A coordinator hands a
single **bounded, self-contained packet** to N >= ``quorum`` **stateless workers**
(the cure for context-dilution/drift: each worker inherits {objective, schema,
boundaries} and nothing else), collects exactly **one independent EvidenceReceipt
per worker**, then a verifier asks the only question that matters:

    Do the decorrelated workers CROSS-FALSIFY — converge on the same checkable
    answer, or expose each other's errors?

Outcomes (mirrors the honest-quorum discipline — agreement is earned, never assumed):
  * CONVERGED    — >= quorum workers returned ok AND they agree. Coherence proven
                   from the inside by decorrelated independent agreement.
  * DIVERGED     — >= quorum returned ok but they disagree. The holons falsified
                   each other; that is a real, valuable internal reality-check,
                   NOT a failure of the mechanism.
  * INCONCLUSIVE — < quorum returned ok. Infrastructure failure, NEVER a coherence
                   claim. (You may not call a thing coherent because the check
                   could not run — that is the hall of mirrors.)

Uses existing substrate only (``spine.EvidenceReceipt``); the live worker factory
imports the provider stack lazily so this module + its tests stay import-light and
deterministic. No parallel rebuild.
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Sequence

from dharma_swarm.spine.receipt import EvidenceReceipt

# A worker is STATELESS: it receives one bounded packet and returns its answer
# plus exactly one independent receipt. It knows nothing of the other workers.
Packet = dict[str, Any]
WorkerResult = tuple[str, EvidenceReceipt]
Worker = Callable[[Packet], Awaitable[WorkerResult]]

Verdict = str  # "CONVERGED" | "DIVERGED" | "INCONCLUSIVE"


def default_normalize(answer: str) -> str:
    """Collapse decorrelated phrasings to a comparable core.

    Decorrelated workers phrase the same answer differently; the cross-check must
    compare the *content*, not the prose. Lowercase, strip punctuation/whitespace,
    and — if a trailing bare token/number is present — prefer it (probes like
    "reply with the integer" put the checkable answer last).
    """
    text = (answer or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    # Prefer a final standalone token/number if the model padded with prose.
    # Internal . _ - are kept (decimals like 3.5, ids like llama-4) but trailing
    # punctuation is dropped ("yes." -> "yes", "42." -> "42").
    tokens = re.findall(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", text)
    if tokens:
        return tokens[-1]
    return text


@dataclass(frozen=True, slots=True)
class CrossFalsifyVerdict:
    """The single receipt the holarchy emits for one cross-falsification round."""

    objective: str
    verdict: Verdict
    converged: bool
    quorum: int
    agreement: float                     # modal-agreement over the ok receipts
    modal_answer: str | None
    answers: dict[str, str]              # worker_id -> normalized answer (ok only)
    ok_count: int
    failed_count: int
    receipts: list[EvidenceReceipt] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"[{self.verdict}] '{self.objective[:60]}' "
            f"ok={self.ok_count} failed={self.failed_count} "
            f"agreement={self.agreement:.2f} modal={self.modal_answer!r} "
            f"(quorum={self.quorum})"
        )


async def run_cross_falsify(
    objective: str,
    workers: Sequence[tuple[str, Worker]],
    *,
    quorum: int = 2,
    agreement_threshold: float = 0.66,
    schema: str | None = None,
    boundaries: str | None = None,
    normalize: Callable[[str], str] = default_normalize,
    timeout_s: float = 120.0,
) -> CrossFalsifyVerdict:
    """Dispatch one bounded packet to N stateless workers and verify cross-falsification.

    ``workers`` is a list of ``(worker_id, worker)``; each worker is decorrelated
    (different model/family/approach) and receives the SAME bounded packet. They
    run concurrently and independently — no shared state, the whole point.
    """
    if quorum < 2:
        raise ValueError("quorum must be >= 2 — a single source cannot falsify itself")

    packet: Packet = {
        "objective": objective,
        "schema": schema,
        "boundaries": boundaries,
    }

    async def _run(worker_id: str, worker: Worker) -> tuple[str, str | None, EvidenceReceipt]:
        try:
            answer, receipt = await asyncio.wait_for(worker(dict(packet)), timeout=timeout_s)
            return worker_id, answer, receipt
        except Exception as exc:  # a worker failure is INCONCLUSIVE, never a verdict
            receipt = EvidenceReceipt(
                agent_id=worker_id,
                status="failed",
                error_source="provider_failed",
                error_detail=str(exc)[:300],
                attributes={"worker_id": worker_id, "objective": objective},
            )
            return worker_id, None, receipt

    results = await asyncio.gather(*(_run(wid, w) for wid, w in workers))

    receipts: list[EvidenceReceipt] = [r for _, _, r in results]
    ok = [(wid, ans, r) for wid, ans, r in results if r.status == "ok" and ans is not None]
    failed_count = len(results) - len(ok)

    answers = {wid: normalize(ans) for wid, ans, _ in ok}

    if len(ok) < quorum:
        # The check could not run with enough independent sources. Honest non-answer.
        return CrossFalsifyVerdict(
            objective=objective,
            verdict="INCONCLUSIVE",
            converged=False,
            quorum=quorum,
            agreement=0.0,
            modal_answer=None,
            answers=answers,
            ok_count=len(ok),
            failed_count=failed_count,
            receipts=receipts,
        )

    counts = Counter(answers.values())
    modal_answer, modal_n = counts.most_common(1)[0]
    agreement = modal_n / len(ok)
    converged = modal_n >= quorum and agreement >= agreement_threshold

    return CrossFalsifyVerdict(
        objective=objective,
        verdict="CONVERGED" if converged else "DIVERGED",
        converged=converged,
        quorum=quorum,
        agreement=agreement,
        modal_answer=modal_answer,
        answers=answers,
        ok_count=len(ok),
        failed_count=failed_count,
        receipts=receipts,
    )


def provider_worker(model_id: str, provider: str | None = None) -> tuple[str, Worker]:
    """Build a LIVE stateless worker bound to one model on the existing provider stack.

    Lazy imports keep this module import-light. The worker resolves the runtime
    provider config -> creates the provider -> completes the bounded packet, and
    wraps the result in an independent EvidenceReceipt. Gated by the caller
    (live mode); the deterministic tests use injected fake workers instead.
    """

    async def _worker(packet: Packet) -> WorkerResult:
        from dharma_swarm.models import LLMRequest, ProviderType
        from dharma_swarm.runtime_provider import (
            create_runtime_provider,
            resolve_runtime_provider_config,
        )

        ptype = ProviderType(provider) if provider else ProviderType.NVIDIA_NIM
        config = resolve_runtime_provider_config(ptype, model=model_id, timeout_seconds=90)
        prov = create_runtime_provider(config)
        try:
            obj = packet["objective"]
            schema = packet.get("schema")
            sys_msg = "You are a stateless cross-falsification worker. Answer the objective directly and concisely."
            if schema:
                sys_msg += f" Output contract: {schema}"
            req = LLMRequest(
                model=model_id,
                system=sys_msg,
                messages=[{"role": "user", "content": obj}],
                max_tokens=256,
                temperature=0.0,
            )
            resp = await prov.complete(req)
            content = resp.content or ""
            receipt = EvidenceReceipt(
                agent_id=f"{ptype.value}:{model_id}",
                provider=ptype.value,
                model=model_id,
                status="ok" if content.strip() else "failed",
                provider_attempted=True,
                attributes={"worker_id": model_id, "answer_preview": content[:180]},
            )
            return content, receipt
        finally:
            close = getattr(prov, "close", None)
            if callable(close):
                res = close()
                if asyncio.iscoroutine(res):
                    await res

    return f"nim:{model_id}" if provider is None else f"{provider}:{model_id}", _worker


async def _cli(objective: str, model_ids: list[str], quorum: int) -> int:
    workers = [provider_worker(m) for m in model_ids]
    verdict = await run_cross_falsify(objective, workers, quorum=quorum)
    print(verdict.summary())
    for wid, ans in verdict.answers.items():
        print(f"  {wid}: {ans}")
    # CONVERGED or DIVERGED are both honest, complete runs; INCONCLUSIVE is infra failure.
    return 0 if verdict.verdict in ("CONVERGED", "DIVERGED") else 1


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Falsifiable Holarchy cross-falsification round")
    parser.add_argument("objective", help="the checkable objective to put to N decorrelated workers")
    parser.add_argument("--model", action="append", dest="models", required=True, help="NIM model id (repeatable)")
    parser.add_argument("--quorum", type=int, default=2)
    args = parser.parse_args()
    return asyncio.run(_cli(args.objective, args.models, args.quorum))


__all__ = [
    "CrossFalsifyVerdict",
    "Worker",
    "WorkerResult",
    "default_normalize",
    "run_cross_falsify",
    "provider_worker",
]


if __name__ == "__main__":
    raise SystemExit(main())
