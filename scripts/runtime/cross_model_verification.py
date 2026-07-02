#!/usr/bin/env python3
"""Run a small cross-model verification council and summarize the receipts."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.model_pool_registry import build_model_pool_snapshot  # noqa: E402
from dharma_swarm.models import ProviderType  # noqa: E402
from scripts.runtime.model_critic_runner import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_model_critic,
)

PASS_VERDICTS = {"pass", "approve"}
HOLD_VERDICTS = {"revise", "reject", "blocked", "failed", "insufficient_context"}
SUPPORTED_PROVIDERS = {provider.value for provider in ProviderType}
DEFAULT_SAFE_PROVIDERS = (
    "ollama",
    "nvidia_nim",
    "groq",
    "cerebras",
    "google_ai",
    "openrouter_free",
    "openrouter",
)


def _stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _safe_token(value: object, *, fallback: str = "unknown") -> str:
    chars = [char if char.isalnum() or char in ("_", "-") else "_" for char in str(value or "")]
    return ("".join(chars).strip("_-") or fallback)[:96]


def parse_critic(value: str) -> tuple[str, str]:
    if ":" not in value:
        raise ValueError(f"critic must be provider:model, got {value!r}")
    provider, model = value.split(":", 1)
    provider = provider.strip()
    model = model.strip()
    if not provider or not model:
        raise ValueError(f"critic must be provider:model, got {value!r}")
    return provider, model


def select_critics_from_model_pool(*, limit: int = 4) -> list[str]:
    """Pick a compact, provider-diverse live council from the unified model pool."""
    snapshot = build_model_pool_snapshot(refresh_nim=False)
    selected: list[str] = []
    seen_providers: set[str] = set()
    for provider in DEFAULT_SAFE_PROVIDERS:
        for entry in snapshot.entries:
            if entry.provider != provider or entry.provider in seen_providers:
                continue
            if entry.provider not in SUPPORTED_PROVIDERS:
                continue
            if entry.availability not in {"live_verified", "configured", "credential_present"}:
                continue
            selected.append(f"{entry.provider}:{entry.model}")
            seen_providers.add(entry.provider)
            break
        if len(selected) >= limit:
            break
    return selected


def _receipt_row(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "critic_agent_id": receipt.get("critic_agent_id", ""),
        "provider": (receipt.get("model_identity") or {}).get("provider", ""),
        "model": (receipt.get("model_identity") or {}).get("model", ""),
        "verdict": receipt.get("verdict", ""),
        "confidence": receipt.get("confidence", 0.0),
        "failure_type": receipt.get("failure_type", ""),
        "explicit_disagreement": receipt.get("explicit_disagreement", ""),
        "summary": receipt.get("summary", ""),
        "artifact_path": receipt.get("_artifact_path", ""),
    }


def _summarize(rows: list[dict[str, Any]], artifact_paths: list[str]) -> dict[str, Any]:
    successes = [
        row
        for row in rows
        if not row["failure_type"] and str(row["verdict"]).lower() in PASS_VERDICTS
    ]
    blockers = [
        row
        for row in rows
        if row["failure_type"] or str(row["verdict"]).lower() in HOLD_VERDICTS
    ]
    disagreements = [
        row
        for row in rows
        if str(row.get("explicit_disagreement") or "").strip()
    ]
    confidence_values = [
        float(row["confidence"])
        for row in rows
        if isinstance(row.get("confidence"), int | float)
    ]
    if len(rows) < 2:
        gate = "hold_single_critic"
    elif blockers:
        gate = "hold_blocker_or_revision"
    elif disagreements:
        gate = "hold_unresolved_disagreement"
    elif len(successes) == len(rows):
        gate = "pass_consensus"
    else:
        gate = "hold_mixed"

    return {
        "critic_count": len(rows),
        "success_count": len(successes),
        "blocker_count": len(blockers),
        "disagreement_count": len(disagreements),
        "confidence_min": min(confidence_values) if confidence_values else 0.0,
        "confidence_avg": round(sum(confidence_values) / len(confidence_values), 3)
        if confidence_values else 0.0,
        "conviction_gate": gate,
        "rows": rows,
        "artifact_paths": artifact_paths,
    }


def _write_summary(out_dir: Path, summary: dict[str, Any]) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{_stamp()}-cross-model-verification-{_safe_token(summary['conviction_gate'])}"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Cross-Model Verification",
        "",
        f"conviction_gate: **{summary['conviction_gate']}**",
        f"critics: {summary['critic_count']}",
        f"passes: {summary['success_count']}",
        f"blockers: {summary['blocker_count']}",
        f"disagreements: {summary['disagreement_count']}",
        f"confidence_min: {summary['confidence_min']}",
        f"confidence_avg: {summary['confidence_avg']}",
        "",
        "## Critics",
        "",
    ]
    for row in summary["rows"]:
        disagreement = row["explicit_disagreement"].strip()
        lines.append(
            f"- `{row['critic_agent_id']}` verdict={row['verdict']} "
            f"confidence={row['confidence']} failure={row['failure_type'] or '-'}"
        )
        if disagreement:
            lines.append(f"  disagreement: {disagreement[:300]}")
    lines.extend(["", "## Artifacts", ""])
    lines.extend(f"- `{path}`" for path in summary["artifact_paths"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"summary_json": str(json_path), "summary_markdown": str(md_path)}


def run_cross_model_verification(
    *,
    prompt_file: Path,
    critics: list[str],
    out_dir: Path = DEFAULT_OUT_DIR,
    agent_uid: str = "codex_composer",
    review_target: str = "",
    mock_response_file: Path | None = None,
    timeout_seconds: int = 180,
    repair_attempts: int = 2,
) -> dict[str, Any]:
    if not critics:
        raise ValueError("at least two critics are recommended; no critics were provided")

    rows: list[dict[str, Any]] = []
    artifact_paths: list[str] = []
    for critic in critics:
        provider, model = parse_critic(critic)
        result = run_model_critic(
            prompt_file=prompt_file,
            provider=provider,
            model=model,
            out_dir=out_dir,
            agent_uid=agent_uid,
            review_target=review_target,
            mock_response_file=mock_response_file,
            timeout_seconds=timeout_seconds,
            repair_attempts=repair_attempts,
        )
        receipt = dict(result["receipt"])
        receipt["_artifact_path"] = result["artifact_path"]
        rows.append(_receipt_row(receipt))
        artifact_paths.append(result["artifact_path"])

    summary = _summarize(rows, artifact_paths)
    summary.update(_write_summary(out_dir, summary))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--critic", action="append", default=[], help="provider:model, repeatable")
    parser.add_argument("--from-model-pool", action="store_true")
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--agent-uid", default="codex_composer")
    parser.add_argument("--review-target", default="")
    parser.add_argument("--mock-response-file", default="")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--repair-attempts", type=int, default=2)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    critics = list(args.critic)
    if args.from_model_pool:
        critics.extend(select_critics_from_model_pool(limit=args.limit))
    critics = list(dict.fromkeys(critics))

    summary = run_cross_model_verification(
        prompt_file=Path(args.prompt_file),
        critics=critics,
        out_dir=Path(args.out_dir),
        agent_uid=args.agent_uid,
        review_target=args.review_target,
        mock_response_file=Path(args.mock_response_file) if args.mock_response_file else None,
        timeout_seconds=args.timeout_seconds,
        repair_attempts=args.repair_attempts,
    )
    payload = {
        "conviction_gate": summary["conviction_gate"],
        "critic_count": summary["critic_count"],
        "summary_json": summary["summary_json"],
        "summary_markdown": summary["summary_markdown"],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"CROSS_MODEL_VERIFICATION conviction_gate={payload['conviction_gate']} "
            f"critics={payload['critic_count']}"
        )
        print(f"summary: {payload['summary_markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
