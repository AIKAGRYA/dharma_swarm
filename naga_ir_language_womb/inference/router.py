"""Minimal NAGA-IR Language Womb inference router."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from naga_ir_language_womb.inference.receipts_hooks import emit_womb_receipt, hash_json

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_SYSTEM_PROMPT = """You are a NAGA-IR Language Womb research model route.

Answer the research question directly. Preserve uncertainty. Do not promote
model output beyond Attested_by. Cite sources only when they are present in the
prompt or retrieval context; do not invent bibliographic details.
"""


@dataclass(frozen=True)
class InferenceRunRecord:
    schema_version: str
    question_hash: str
    response_hash: str
    receipt_hash: str
    receipt_path: Path
    provider: str
    model: str
    modality: str
    latency_seconds: float


async def route_question(
    *,
    repo_root: Path,
    question: str,
    modality_target: str = "Attested_by",
    provider_name: str = DEFAULT_PROVIDER,
    model: str = DEFAULT_MODEL,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    max_tokens: int = 4096,
    temperature: float = 0.2,
    dry_run: bool = False,
) -> InferenceRunRecord:
    prompt = _build_prompt(question)
    started = time.monotonic()
    response_content = ""
    usage: dict[str, Any] = {}
    resolved_provider = provider_name
    resolved_model = model
    provider_status = "dry_run" if dry_run else "ok"

    if dry_run:
        response_content = "DRY RUN: provider call skipped."
    else:
        provider = _build_provider(
            provider_name=provider_name,
            model=model,
            repo_root=repo_root,
            max_tokens=max_tokens,
        )
        try:
            response = await provider.complete(_llm_request(model=model, system_prompt=system_prompt, prompt=prompt, max_tokens=max_tokens, temperature=temperature))
            response_content = response.content
            usage = dict(response.usage or {})
            resolved_provider = response.provider or provider_name
            resolved_model = response.model or model
        except Exception as exc:
            provider_status = "failed"
            latency_seconds = time.monotonic() - started
            receipt_record = _emit_inference_receipt(
                repo_root=repo_root,
                question=question,
                prompt=prompt,
                response="",
                provider=provider_name,
                model=model,
                modality=_single_model_modality(modality_target),
                latency_seconds=latency_seconds,
                usage={},
                provider_status=provider_status,
                error_type=type(exc).__name__,
            )
            raise RuntimeError(
                f"inference provider failed; receipt={receipt_record.receipt_path}"
            ) from exc
        finally:
            close = getattr(provider, "close", None)
            if callable(close):
                await close()

    latency_seconds = time.monotonic() - started
    modality = _single_model_modality(modality_target)
    receipt_record = _emit_inference_receipt(
        repo_root=repo_root,
        question=question,
        prompt=prompt,
        response=response_content,
        provider=resolved_provider,
        model=resolved_model,
        modality=modality,
        latency_seconds=latency_seconds,
        usage=usage,
        provider_status=provider_status,
        error_type=None,
    )
    return InferenceRunRecord(
        schema_version="naga_ir_language_womb.inference_run_record.v1",
        question_hash=hash_json({"question": question}),
        response_hash=hash_json({"response": response_content}),
        receipt_hash=receipt_record.receipt_hash,
        receipt_path=receipt_record.receipt_path,
        provider=resolved_provider,
        model=resolved_model,
        modality=modality,
        latency_seconds=latency_seconds,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Route a NAGA-IR Language Womb research question.")
    question_group = parser.add_mutually_exclusive_group(required=True)
    question_group.add_argument("--question", help="Question text to route.")
    question_group.add_argument("--question-file", type=Path, help="Path to a question markdown/text file.")
    parser.add_argument("--provider", default=DEFAULT_PROVIDER, help="dharma_swarm ProviderType value.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Provider model id or alias.")
    parser.add_argument("--modality-target", default="Attested_by", help="Requested modality ceiling.")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--dry-run", action="store_true", help="Emit a receipt without making a model call.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    question = args.question if args.question is not None else args.question_file.read_text(encoding="utf-8")
    record = asyncio.run(
        route_question(
            repo_root=args.repo_root.resolve(),
            question=question,
            modality_target=args.modality_target,
            provider_name=args.provider,
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            dry_run=args.dry_run,
        )
    )
    print(json.dumps(_record_to_json(record, args.repo_root.resolve()), indent=2, sort_keys=True))
    return 0


def _build_prompt(question: str) -> str:
    return (
        "Research question:\n"
        f"{question.strip()}\n\n"
        "Return a compact answer with uncertainty markers. This run is a womb "
        "attestation, not proof."
    )


def _build_provider(*, provider_name: str, model: str, repo_root: Path, max_tokens: int) -> Any:
    from dharma_swarm.runtime_provider import (
        ProviderType,
        create_runtime_provider,
        resolve_runtime_provider_config,
    )

    provider_type = ProviderType(provider_name)
    config = resolve_runtime_provider_config(
        provider_type,
        model=model,
        working_dir=str(repo_root),
        timeout_seconds=max(60, max_tokens // 16),
    )
    if not config.available:
        raise RuntimeError(f"provider {provider_type.value} is not available in this environment")
    return create_runtime_provider(config)


def _llm_request(*, model: str, system_prompt: str, prompt: str, max_tokens: int, temperature: float) -> Any:
    from dharma_swarm.models import LLMRequest

    return LLMRequest(
        model=model,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )


def _single_model_modality(modality_target: str) -> str:
    if modality_target == "Assumed":
        return "Assumed"
    return "Attested_by"


def _emit_inference_receipt(
    *,
    repo_root: Path,
    question: str,
    prompt: str,
    response: str,
    provider: str,
    model: str,
    modality: str,
    latency_seconds: float,
    usage: dict[str, Any],
    provider_status: str,
    error_type: str | None,
):
    response_hash = hash_json({"response": response})
    prompt_hash = hash_json({"prompt": prompt})
    cost_signature = hash_json(
        {
            "provider": provider,
            "model": model,
            "usage": usage,
            "latency_seconds_rounded": round(latency_seconds, 3),
        }
    )
    return emit_womb_receipt(
        repo_root=repo_root,
        receipt_class="naga_ir_language_womb.inference.v1",
        subject={
            "kind": "inference_response",
            "content_hash": response_hash,
            "model": model,
            "provider": provider,
        },
        claim={
            "claim_id": f"naga_ir_language_womb.inference.{prompt_hash.removeprefix('sha256:')[:16]}",
            "claim_class": "runtime-observation",
            "claim_strength": "observational" if modality == "Witnessed_by" else "attested",
            "fragment_id": "naga_ir_language_womb.fragment.v1",
            "statement": "A model route produced the recorded response for the recorded prompt.",
            "scope": {
                "paths": ["naga_ir_language_womb/inference/router.py"],
                "symbols": ["route_question"],
            },
        },
        evidence=[
            {
                "modality": modality,
                "method": "naga_ir_language_womb.inference.router",
                "result": "pass" if provider_status in {"ok", "dry_run"} else "fail",
                "body": {
                    "question": question,
                    "prompt": prompt,
                    "prompt_hash": prompt_hash,
                    "response": response,
                    "response_hash": response_hash,
                    "latency_seconds": latency_seconds,
                    "cost_signature": cost_signature,
                    "usage": usage,
                    "provider": provider,
                    "model": model,
                    "provider_status": provider_status,
                    "error_type": error_type,
                    "modality_rule": "single_model_outputs_are_at_most_attested_by",
                },
            }
        ],
        causal_origin={
            "producer": "naga_ir_language_womb.inference.router",
            "artifact_trace": "local_cli_or_experiment",
            "provider": provider,
            "model": model,
        },
    )


def _record_to_json(record: InferenceRunRecord, repo_root: Path) -> dict[str, str | float]:
    return {
        "schema_version": record.schema_version,
        "question_hash": record.question_hash,
        "response_hash": record.response_hash,
        "receipt_hash": record.receipt_hash,
        "receipt_path": record.receipt_path.relative_to(repo_root).as_posix(),
        "provider": record.provider,
        "model": record.model,
        "modality": record.modality,
        "latency_seconds": record.latency_seconds,
    }


if __name__ == "__main__":
    raise SystemExit(main())
