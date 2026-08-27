#!/usr/bin/env python3
"""Run a non-Codex model critique and write a SemanticReceipt artifact."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.operator_core.semantic_receipt import (  # noqa: E402
    SCHEMA_VERSION,
    SemanticReceiptValidationError,
    semantic_receipt_json_schema,
    validate_semantic_receipt,
    utc_now_iso,
)
from dharma_swarm.daemon_config import runtime_report_dir  # noqa: E402

DEFAULT_OUT_DIR = runtime_report_dir("agentops", "semantic_receipts")
DEFAULT_OLLAMA_ENDPOINT = "http://127.0.0.1:11434/api/generate"


def _read_text(path: Path) -> str:
    return path.expanduser().resolve().read_text(encoding="utf-8")


def _safe_token(value: object, *, fallback: str = "unknown") -> str:
    chars = [char if char.isalnum() or char in ("_", "-") else "_" for char in str(value or "")]
    return ("".join(chars).strip("_-") or fallback)[:96]


def _stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _strict_prompt(*, user_prompt: str, provider: str, model: str, review_target: str) -> str:
    schema = json.dumps(semantic_receipt_json_schema(), indent=2, sort_keys=True)
    return f"""You are an external non-Codex model critic.

Return JSON only. Do not use markdown fences, prose before JSON, or comments.
Populate the SemanticReceipt v1 schema below.

Fixed values you must use:
- schema_version: {SCHEMA_VERSION}
- agent_uid: codex_composer
- critic_agent_id: {provider}:{model}
- model_identity.provider: {provider}
- model_identity.model: {model}
- authored_by_model: true
- review_target: {review_target}
- failure_type: ""
- failure_reason: ""
- not_claimed_agents must include at least "codex", "claude", "fable", "hermes", and "devin" unless the receipt truly speaks for one of them.

Verdict enum: pass, approve, revise, reject, blocked, failed, insufficient_context.
If verdict is not pass/approve, explicit_disagreement must be a non-empty string.

JSON Schema:
{schema}

Prompt to critique:
{user_prompt}
"""


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("model response JSON must be an object")
    return data


def _call_ollama(
    *,
    model: str,
    prompt: str,
    endpoint: str,
    timeout_seconds: int,
) -> tuple[str, dict[str, Any], int]:
    if not endpoint.lower().startswith(("http://", "https://")):
        raise ValueError(f"unsupported critic endpoint scheme: {endpoint!r}")
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": semantic_receipt_json_schema(),
        "options": {"temperature": 0},
    }
    started = time.perf_counter()
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
        body = json.loads(response.read().decode("utf-8"))
    latency_ms = int((time.perf_counter() - started) * 1000)
    return str(body.get("response") or ""), body, latency_ms


def _failure_receipt(
    *,
    provider: str,
    model: str,
    agent_uid: str,
    review_target: str,
    prompt_sha256: str,
    failure_type: str,
    failure_reason: str,
    latency_ms: int = 0,
    reply_to: str = "",
    correlation_id: str = "",
    raw_response: str = "",
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": f"semr_{uuid4().hex}",
        "created_at": utc_now_iso(),
        "agent_uid": agent_uid,
        "critic_agent_id": f"{provider}:{model}",
        "model_identity": {"provider": provider, "model": model},
        "authored_by_model": False,
        "review_target": review_target,
        "intent_ack": False,
        "capability_match": 0.0,
        "understood_request": False,
        "missing_context": [],
        "verdict": "failed" if failure_type == "internal_error" else "blocked",
        "summary": f"Model critic runner could not produce a validated semantic receipt: {failure_type}",
        "recommendations": [
            {
                "priority": "p0",
                "action": "Inspect typed failure and retry with a reachable provider or fixture.",
                "rationale": failure_reason[:500],
            }
        ],
        "acceptance_gates": [
            {
                "name": "typed_failure_recorded",
                "condition": "SemanticReceipt failure artifact records provider/model/failure_type",
                "met": True,
            }
        ],
        "explicit_disagreement": failure_reason[:1000] or failure_type,
        "evidence_refs": list(evidence_refs or []),
        "confidence": 0.0,
        "not_claimed_agents": ["codex", "claude", "fable", "hermes", "devin"],
        "failure_type": failure_type,
        "failure_reason": failure_reason,
        "correlation_id": correlation_id,
        "reply_to": reply_to,
        "model_call_latency_ms": latency_ms,
        "prompt_sha256": prompt_sha256,
        "raw_response_sha256": _sha256_text(raw_response) if raw_response else "",
    }
    return validate_semantic_receipt(receipt)


def _apply_runner_provenance(
    receipt: dict[str, Any],
    *,
    provider: str,
    model: str,
    agent_uid: str,
    review_target: str,
    reply_to: str,
    correlation_id: str,
    latency_ms: int,
    prompt_hash: str,
    response_text: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    """Overwrite fields that must come from the runner, not model prose."""
    receipt["receipt_id"] = f"semr_{uuid4().hex}"
    receipt["schema_version"] = SCHEMA_VERSION
    receipt["created_at"] = utc_now_iso()
    receipt["agent_uid"] = agent_uid
    receipt["critic_agent_id"] = f"{provider}:{model}"
    receipt["model_identity"] = {"provider": provider, "model": model}
    receipt["authored_by_model"] = True
    receipt["review_target"] = review_target
    receipt["failure_type"] = ""
    receipt["failure_reason"] = ""
    receipt["correlation_id"] = correlation_id
    receipt["reply_to"] = reply_to
    receipt["model_call_latency_ms"] = latency_ms
    receipt["prompt_sha256"] = prompt_hash
    receipt["raw_response_sha256"] = _sha256_text(response_text)
    receipt["evidence_refs"] = list(dict.fromkeys([*receipt.get("evidence_refs", []), *evidence_refs]))
    return receipt


def _artifact_path(out_dir: Path, *, provider: str, model: str, receipt: dict[str, Any]) -> Path:
    receipt_id = _safe_token(receipt.get("receipt_id"))
    return out_dir / f"{_stamp()}-{_safe_token(provider)}-{_safe_token(model)}-{receipt_id}.json"


def run_model_critic(
    *,
    prompt_file: Path,
    provider: str = "ollama",
    model: str = "glm-5:cloud",
    out_dir: Path = DEFAULT_OUT_DIR,
    agent_uid: str = "codex_composer",
    review_target: str = "",
    reply_to: str = "",
    correlation_id: str = "",
    mock_response_file: Path | None = None,
    ollama_endpoint: str = DEFAULT_OLLAMA_ENDPOINT,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    """Run one model critique and write a success or typed failure artifact."""
    prompt_file = prompt_file.expanduser().resolve()
    out_dir = out_dir.expanduser().resolve()
    user_prompt = _read_text(prompt_file)
    prompt_hash = _sha256_text(user_prompt)
    review_target = review_target or f"prompt:{prompt_file}"
    evidence_refs = [str(prompt_file)]

    response_text = ""
    latency_ms = 0
    try:
        if mock_response_file is not None:
            started = time.perf_counter()
            response_text = _read_text(mock_response_file)
            latency_ms = int((time.perf_counter() - started) * 1000)
            raw_payload: dict[str, Any] = {"mock_response_file": str(mock_response_file)}
        elif provider == "ollama":
            strict = _strict_prompt(user_prompt=user_prompt, provider=provider, model=model, review_target=review_target)
            response_text, raw_payload, latency_ms = _call_ollama(
                model=model,
                prompt=strict,
                endpoint=ollama_endpoint,
                timeout_seconds=timeout_seconds,
            )
            if not response_text.strip():
                raise RuntimeError("empty model response")
        else:
            raise RuntimeError(f"provider is not supported by this runner: {provider}")

        try:
            receipt = _extract_json_object(response_text)
            receipt = _apply_runner_provenance(
                receipt,
                provider=provider,
                model=model,
                agent_uid=agent_uid,
                review_target=review_target,
                reply_to=reply_to,
                correlation_id=correlation_id,
                latency_ms=latency_ms,
                prompt_hash=prompt_hash,
                response_text=response_text,
                evidence_refs=evidence_refs,
            )
            validated = validate_semantic_receipt(receipt)
        except (json.JSONDecodeError, ValueError, SemanticReceiptValidationError) as first_error:
            if mock_response_file is not None or provider != "ollama":
                raise
            retry_prompt = _strict_prompt(
                user_prompt=(
                    f"{user_prompt}\n\nYour previous response failed SemanticReceipt validation with: "
                    f"{first_error}. Return corrected JSON only."
                ),
                provider=provider,
                model=model,
                review_target=review_target,
            )
            response_text, raw_payload, latency_ms = _call_ollama(
                model=model,
                prompt=retry_prompt,
                endpoint=ollama_endpoint,
                timeout_seconds=timeout_seconds,
            )
            receipt = _extract_json_object(response_text)
            receipt = _apply_runner_provenance(
                receipt,
                provider=provider,
                model=model,
                agent_uid=agent_uid,
                review_target=review_target,
                reply_to=reply_to,
                correlation_id=correlation_id,
                latency_ms=latency_ms,
                prompt_hash=prompt_hash,
                response_text=response_text,
                evidence_refs=evidence_refs,
            )
            validated = validate_semantic_receipt(receipt)

        validated["model_runner"] = {
            "provider": provider,
            "model": model,
            "raw_payload_keys": sorted(raw_payload.keys()),
        }
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        validated = _failure_receipt(
            provider=provider,
            model=model,
            agent_uid=agent_uid,
            review_target=review_target,
            prompt_sha256=prompt_hash,
            failure_type="provider_failed",
            failure_reason=f"HTTP {exc.code}: {raw[:1500]}",
            latency_ms=latency_ms,
            reply_to=reply_to,
            correlation_id=correlation_id,
            raw_response=raw,
            evidence_refs=evidence_refs,
        )
    except TimeoutError as exc:
        validated = _failure_receipt(
            provider=provider,
            model=model,
            agent_uid=agent_uid,
            review_target=review_target,
            prompt_sha256=prompt_hash,
            failure_type="provider_timeout",
            failure_reason=str(exc),
            latency_ms=latency_ms,
            reply_to=reply_to,
            correlation_id=correlation_id,
            evidence_refs=evidence_refs,
        )
    except SemanticReceiptValidationError as exc:
        validated = _failure_receipt(
            provider=provider,
            model=model,
            agent_uid=agent_uid,
            review_target=review_target,
            prompt_sha256=prompt_hash,
            failure_type="schema_validation_failed",
            failure_reason="; ".join(exc.errors),
            latency_ms=latency_ms,
            reply_to=reply_to,
            correlation_id=correlation_id,
            raw_response=response_text,
            evidence_refs=evidence_refs,
        )
    except json.JSONDecodeError as exc:
        validated = _failure_receipt(
            provider=provider,
            model=model,
            agent_uid=agent_uid,
            review_target=review_target,
            prompt_sha256=prompt_hash,
            failure_type="json_parse_failed",
            failure_reason=str(exc),
            latency_ms=latency_ms,
            reply_to=reply_to,
            correlation_id=correlation_id,
            raw_response=response_text,
            evidence_refs=evidence_refs,
        )
    except Exception as exc:
        failure_type = "provider_unavailable" if provider != "ollama" else "internal_error"
        validated = _failure_receipt(
            provider=provider,
            model=model,
            agent_uid=agent_uid,
            review_target=review_target,
            prompt_sha256=prompt_hash,
            failure_type=failure_type,
            failure_reason=f"{type(exc).__name__}: {exc}",
            latency_ms=latency_ms,
            reply_to=reply_to,
            correlation_id=correlation_id,
            raw_response=response_text,
            evidence_refs=evidence_refs,
        )

    out_path = _artifact_path(out_dir, provider=provider, model=model, receipt=validated)
    _write_json(out_path, validated)
    return {"artifact_path": str(out_path), "receipt": validated}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--model", default="glm-5:cloud")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--agent-uid", default="codex_composer")
    parser.add_argument("--review-target", default="")
    parser.add_argument("--reply-to", default="")
    parser.add_argument("--correlation-id", default="")
    parser.add_argument("--mock-response-file", default="")
    parser.add_argument("--ollama-endpoint", default=DEFAULT_OLLAMA_ENDPOINT)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = run_model_critic(
        prompt_file=Path(args.prompt_file),
        provider=args.provider,
        model=args.model,
        out_dir=Path(args.out_dir),
        agent_uid=args.agent_uid,
        review_target=args.review_target,
        reply_to=args.reply_to,
        correlation_id=args.correlation_id,
        mock_response_file=Path(args.mock_response_file) if args.mock_response_file else None,
        ollama_endpoint=args.ollama_endpoint,
        timeout_seconds=args.timeout_seconds,
    )
    payload = {
        "status": "SEMANTIC_RECEIPT_WRITTEN",
        "artifact_path": result["artifact_path"],
        "semantic_reply_claim": bool(result["receipt"].get("semantic_reply_claim")),
        "peer_model_processed_claim": bool(result["receipt"].get("peer_model_processed_claim")),
        "failure_type": str(result["receipt"].get("failure_type") or ""),
        "verdict": str(result["receipt"].get("verdict") or ""),
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"{payload['status']} verdict={payload['verdict']} "
            f"semantic_reply_claim={payload['semantic_reply_claim']}"
        )
        print(f"artifact: {payload['artifact_path']}")
        if payload["failure_type"]:
            print(f"failure_type: {payload['failure_type']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
