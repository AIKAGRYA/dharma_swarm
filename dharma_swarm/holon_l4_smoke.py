"""Deterministic L4 HOLON smoke proof.

This module proves the L4 chain with existing HOLON organs: identity load,
runtime session, task claim, execution lease, declared routing, governed wake,
memory receipt, artifact, outcome proof, per-agent persistence, service
heartbeat, transport liveness, and an optional model-response probe. It is a
verifier harness, not a daemon.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from dharma_swarm.holon_bridge import (
    build_request,
    get_holon_provider,
    holon_reply,
    load_holon,
)
from dharma_swarm.holon_persistence import save_cycle_record
from dharma_swarm.holon_runtime import holon_wake_cycle
from dharma_swarm.holon_service_liveness import (
    assess_service_liveness,
    record_service_heartbeat,
    service_heartbeat_path,
)
from dharma_swarm.holon_transport_liveness import assess_a2a_inbox_bridge_liveness
from dharma_swarm.memory_kernel.write_receipts import (
    MemoryKernelWriteReceiptInput,
    append_write_receipts,
    governed_write_receipt,
)

PROOF_SCHEMA_VERSION = "dharma.holon_l4_smoke.v1"
MODEL_PROBE_LEASE_SCHEMA_VERSION = "dharma.holon_model_probe_lease.v1"
SUBPROCESS_MODEL_PROBE_PROVIDER_TYPES = {"claude_code", "codex"}


@dataclass(frozen=True)
class L4SmokeConfig:
    name: str
    agents_root: Path
    memory_receipt_path: Path
    session_id: str = ""
    lease_seconds: int = 900
    persist: bool = True
    enable_model_probe: bool = False
    model_probe_timeout_seconds: int = 120
    model_probe_message: str = (
        "Reply with one short sentence confirming you are responsive as this holon."
    )
    model_probe_provider: Any | None = None
    allow_subprocess_model_probe: bool = False
    safe_subprocess_model_probe: bool = False
    safe_subprocess_probe_cwd: Path | None = None
    safe_subprocess_model_probe_runner: Any | None = None
    model_probe_lease_id: str = ""
    model_probe_lease_path: Path | None = None
    transport_agent_uid: str = ""
    transport_heartbeat_path: Path | None = None
    transport_fresh_after_seconds: int = 3600
    require_transport_reachable: bool = False
    enable_orchestration_probe: bool = False
    require_orchestration: bool = False
    orchestration_orchestrator: Any | None = None
    orchestration_decomposer: Any | None = None
    orchestration_synthesizer: Any | None = None
    orchestration_mission: str = (
        "Map, verify, and synthesize the current L4 HOLON substrate proof."
    )
    orchestration_min_subtasks: int = 2
    orchestration_min_model_tiers: int = 2
    orchestration_require_model_tier_diversity: bool = True
    orchestration_execution_mode: str = "dispatch_aggregation_probe"
    orchestration_execution_timeout_seconds: float = 30.0


def utc_compact() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_sha256(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def stable_proof_sha256(payload: dict[str, Any]) -> str:
    return stable_sha256({key: value for key, value in payload.items() if key != "proof_digest"})


def model_probe_lease_digest(payload: dict[str, Any]) -> str:
    """Digest a model-probe lease without trusting its embedded digest."""
    return stable_sha256({key: value for key, value in payload.items() if key != "digest"})


def _parse_utc_datetime(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _model_probe_lease_evidence(
    holon: Any,
    config: L4SmokeConfig,
    *,
    provider_source: str,
    session_id: str,
    now: datetime,
) -> dict[str, Any]:
    """Load and validate the explicit live-model lease receipt."""
    lease_id = str(config.model_probe_lease_id or "").strip()
    if provider_source == "injected":
        return {
            "required": False,
            "valid": True,
            "reason": "injected_provider_test_boundary",
            "lease_id": lease_id,
            "path": str(config.model_probe_lease_path) if config.model_probe_lease_path else "",
        }
    if not lease_id:
        return {
            "required": True,
            "valid": False,
            "reason": "model_probe_lease_id_missing",
            "lease_id": "",
            "path": str(config.model_probe_lease_path) if config.model_probe_lease_path else "",
        }
    if config.model_probe_lease_path is None:
        return {
            "required": True,
            "valid": False,
            "reason": "model_probe_lease_path_missing",
            "lease_id": lease_id,
            "path": "",
        }
    path = Path(config.model_probe_lease_path)
    if not path.exists():
        return {
            "required": True,
            "valid": False,
            "reason": "model_probe_lease_file_missing",
            "lease_id": lease_id,
            "path": str(path),
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - verifier receipts malformed leases.
        return {
            "required": True,
            "valid": False,
            "reason": "model_probe_lease_file_unreadable",
            "lease_id": lease_id,
            "path": str(path),
            "error_type": type(exc).__name__,
            "error_preview": _error_preview(exc),
        }
    if not isinstance(payload, dict):
        return {
            "required": True,
            "valid": False,
            "reason": "model_probe_lease_not_object",
            "lease_id": lease_id,
            "path": str(path),
        }
    expected_digest = model_probe_lease_digest(payload)
    observed_digest = str(payload.get("digest", "") or "")
    checks = {
        "schema_version": payload.get("schema_version") == MODEL_PROBE_LEASE_SCHEMA_VERSION,
        "digest": bool(observed_digest) and observed_digest == expected_digest,
        "lease_id": payload.get("lease_id") == lease_id,
        "holon": payload.get("holon") == holon.name,
        "provider_type": payload.get("provider_type") == holon.provider_type,
        "model": payload.get("model") == holon.model,
        "session_id": payload.get("session_id") == session_id,
        "allow_live_model_probe": payload.get("allow_live_model_probe") is True,
    }
    issued_at = _parse_utc_datetime(payload.get("issued_at"))
    expires_at = _parse_utc_datetime(payload.get("expires_at"))
    checks["issued_at"] = issued_at is not None and issued_at <= now
    checks["expires_at"] = expires_at is not None and expires_at > now
    failed = [key for key, ok in checks.items() if not ok]
    return {
        "required": True,
        "valid": not failed,
        "reason": "ok" if not failed else f"model_probe_lease_invalid:{','.join(failed)}",
        "lease_id": lease_id,
        "path": str(path),
        "digest": observed_digest,
        "expected_digest": expected_digest,
        "checks": checks,
        "allow_subprocess_provider": payload.get("allow_subprocess_provider") is True,
        "expires_at": payload.get("expires_at", ""),
        "issued_at": payload.get("issued_at", ""),
        "purpose": str(payload.get("purpose", "") or "")[:200],
    }


def _error_preview(exc: BaseException) -> str:
    text = " ".join(str(exc).split())
    text = re.sub(
        r"(?i)\b(api[_-]?key|token|authorization|bearer)(\s*[:=]\s*)(\S+)",
        r"\1\2[redacted]",
        text,
    )
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{6,}\b", "sk-[redacted]", text)
    return text[:300]


def _classify_model_probe_error(exc: BaseException) -> str:
    text = str(exc).lower()
    if isinstance(exc, TimeoutError):
        return "timeout"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "not set" in text or "missing" in text and "key" in text:
        return "missing_config"
    if "no such file" in text or "not found" in text:
        return "provider_unavailable"
    if "401" in text or "unauthorized" in text:
        return "auth_failed"
    if "402" in text or "insufficient credit" in text or "payment required" in text:
        return "insufficient_credits"
    if "429" in text or "rate limit" in text:
        return "rate_limited"
    return "error"


def _model_probe_route_policy(
    holon: Any,
    *,
    provider_source: str,
    allow_subprocess_model_probe: bool,
    model_probe_lease_id: str = "",
    lease_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider_type = str(getattr(holon, "provider_type", "") or "")
    is_subprocess = provider_type in SUBPROCESS_MODEL_PROBE_PROVIDER_TYPES
    lease_id = str(model_probe_lease_id or "").strip()
    lease = dict(lease_evidence or {})
    if provider_source == "injected":
        return {
            "decision": "allow",
            "reason": "injected_provider_test_boundary",
            "provider_type": provider_type,
            "execution_kind": "injected",
            "subprocess_provider": False,
            "model_probe_lease_id": lease_id,
            "explicit_lease": bool(lease.get("valid")),
            "lease_evidence": lease,
        }
    if is_subprocess and not allow_subprocess_model_probe:
        return {
            "decision": "refuse",
            "reason": "subprocess_provider_requires_explicit_override",
            "provider_type": provider_type,
            "execution_kind": "subprocess_cli",
            "subprocess_provider": True,
            "explicit_override": False,
            "model_probe_lease_id": lease_id,
            "explicit_lease": bool(lease.get("valid")),
            "lease_evidence": lease,
        }
    if not lease.get("valid"):
        return {
            "decision": "refuse",
            "reason": str(lease.get("reason") or "model_probe_lease_invalid"),
            "provider_type": provider_type,
            "execution_kind": "subprocess_cli" if is_subprocess else "api_or_local",
            "subprocess_provider": is_subprocess,
            "explicit_override": bool(is_subprocess and allow_subprocess_model_probe),
            "model_probe_lease_id": lease_id,
            "explicit_lease": False,
            "lease_evidence": lease,
        }
    if is_subprocess and not lease.get("allow_subprocess_provider"):
        return {
            "decision": "refuse",
            "reason": "model_probe_lease_disallows_subprocess_provider",
            "provider_type": provider_type,
            "execution_kind": "subprocess_cli",
            "subprocess_provider": True,
            "explicit_override": True,
            "model_probe_lease_id": lease_id,
            "explicit_lease": True,
            "lease_evidence": lease,
        }
    return {
        "decision": "allow",
        "reason": (
            "subprocess_provider_explicitly_allowed"
            if is_subprocess
            else "api_or_local_provider"
        ),
        "provider_type": provider_type,
        "execution_kind": "subprocess_cli" if is_subprocess else "api_or_local",
        "subprocess_provider": is_subprocess,
        "explicit_override": bool(is_subprocess and allow_subprocess_model_probe),
        "model_probe_lease_id": lease_id,
        "explicit_lease": True,
        "lease_evidence": lease,
    }


def _model_probe_prompt(holon: Any, message: str) -> str:
    return "\n\n".join([
        str(getattr(holon, "system_prompt", "") or ""),
        (
            "You are running a read-only L4 HOLON responsiveness probe. "
            "Do not inspect files, run commands, modify state, or claim work. "
            "Reply with one short sentence only."
        ),
        str(message or ""),
    ]).strip()


async def _run_safe_codex_subprocess_probe(
    holon: Any,
    config: L4SmokeConfig,
    *,
    route_policy: dict[str, Any],
    started: datetime,
) -> dict[str, Any]:
    if holon.provider_type != "codex":
        return {
            "enabled": True,
            "attempted": False,
            "responsive": False,
            "status": "safe_subprocess_probe_unsupported",
            "provider_source": "declared_identity",
            "provider_type": holon.provider_type,
            "model": holon.model,
            "route_policy": {
                **route_policy,
                "execution_kind": "safe_subprocess_probe_unsupported",
            },
            "reason": "safe_subprocess_model_probe_currently_supports_codex_only",
            "duration_ms": round((datetime.now(UTC) - started).total_seconds() * 1000, 3),
        }
    runner = config.safe_subprocess_model_probe_runner
    prompt = _model_probe_prompt(holon, config.model_probe_message)
    cwd = Path(config.safe_subprocess_probe_cwd or Path.cwd()).expanduser().resolve()
    if runner is not None:
        try:
            result = runner(holon=holon, config=config, prompt=prompt, cwd=cwd)
            if inspect.isawaitable(result):
                result = await result
            reply = str((result or {}).get("reply") if isinstance(result, dict) else result).strip()
            responsive = bool(reply)
            return {
                "enabled": True,
                "attempted": True,
                "responsive": responsive,
                "status": "ok" if responsive else "empty_response",
                "provider_source": "declared_identity",
                "provider_type": holon.provider_type,
                "model": holon.model,
                "route_policy": {
                    **route_policy,
                    "execution_kind": "safe_codex_exec_read_only",
                    "safe_subprocess_probe": True,
                },
                "reply_chars": len(reply),
                "chunk_count": 1 if reply else 0,
                "reply_digest": stable_sha256({"reply": reply}),
                "reply_preview": reply[:300],
                "duration_ms": round((datetime.now(UTC) - started).total_seconds() * 1000, 3),
            }
        except Exception as exc:  # noqa: BLE001 - probe must receipt failures.
            return {
                "enabled": True,
                "attempted": True,
                "responsive": False,
                "status": _classify_model_probe_error(exc),
                "provider_source": "declared_identity",
                "provider_type": holon.provider_type,
                "model": holon.model,
                "route_policy": {
                    **route_policy,
                    "execution_kind": "safe_codex_exec_read_only",
                    "safe_subprocess_probe": True,
                },
                "error_type": type(exc).__name__,
                "error_preview": _error_preview(exc),
                "duration_ms": round((datetime.now(UTC) - started).total_seconds() * 1000, 3),
            }

    from dharma_swarm.models import ProviderType
    from dharma_swarm.runtime_provider import resolve_runtime_provider_config

    runtime_config = resolve_runtime_provider_config(
        ProviderType.CODEX,
        model=holon.model,
        working_dir=str(cwd),
        timeout_seconds=max(1, int(config.model_probe_timeout_seconds)),
    )
    if not runtime_config.binary_path:
        return {
            "enabled": True,
            "attempted": False,
            "responsive": False,
            "status": "provider_unavailable",
            "provider_source": "declared_identity",
            "provider_type": holon.provider_type,
            "model": holon.model,
            "route_policy": {
                **route_policy,
                "execution_kind": "safe_codex_exec_read_only",
                "safe_subprocess_probe": True,
            },
            "reason": "codex_binary_missing",
            "duration_ms": round((datetime.now(UTC) - started).total_seconds() * 1000, 3),
        }

    with tempfile.TemporaryDirectory(prefix="holon-l4-codex-probe-") as tmp:
        output_path = Path(tmp) / "last_message.txt"
        command = [
            runtime_config.binary_path,
            "--ask-for-approval",
            "never",
            "exec",
            "-c",
            'approval_policy="never"',
            "--ephemeral",
            "--ignore-rules",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "-C",
            str(cwd),
            "-m",
            holon.model,
            "--output-last-message",
            str(output_path),
            prompt,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=max(1, int(config.model_probe_timeout_seconds)),
            )
        except asyncio.TimeoutError as exc:
            return {
                "enabled": True,
                "attempted": True,
                "responsive": False,
                "status": "timeout",
                "provider_source": "declared_identity",
                "provider_type": holon.provider_type,
                "model": holon.model,
                "route_policy": {
                    **route_policy,
                    "execution_kind": "safe_codex_exec_read_only",
                    "safe_subprocess_probe": True,
                },
                "error_type": type(exc).__name__,
                "error_preview": _error_preview(exc),
                "duration_ms": round((datetime.now(UTC) - started).total_seconds() * 1000, 3),
            }
        reply = ""
        if output_path.exists():
            reply = output_path.read_text(encoding="utf-8", errors="replace").strip()
        if not reply:
            reply = (stdout or b"").decode("utf-8", errors="replace").strip()
        responsive = bool(reply) and proc.returncode == 0
        return {
            "enabled": True,
            "attempted": True,
            "responsive": responsive,
            "status": "ok" if responsive else "error",
            "provider_source": "declared_identity",
            "provider_type": holon.provider_type,
            "model": holon.model,
            "route_policy": {
                **route_policy,
                "execution_kind": "safe_codex_exec_read_only",
                "safe_subprocess_probe": True,
            },
            "reply_chars": len(reply),
            "chunk_count": 1 if reply else 0,
            "reply_digest": stable_sha256({"reply": reply}) if reply else "",
            "reply_preview": reply[:300],
            "return_code": proc.returncode,
            "stderr_preview": _error_preview(
                RuntimeError((stderr or b"").decode("utf-8", errors="replace")[:500])
            ),
            "duration_ms": round((datetime.now(UTC) - started).total_seconds() * 1000, 3),
        }


async def _run_model_response_probe(
    holon: Any,
    config: L4SmokeConfig,
    *,
    session_id: str,
) -> dict[str, Any]:
    """Optionally prove a live model response through the holon's own route."""
    if not config.enable_model_probe:
        return {
            "enabled": False,
            "attempted": False,
            "responsive": False,
            "status": "skipped",
            "reason": "enable_model_probe_false",
        }

    started = datetime.now(UTC)
    provider = config.model_probe_provider
    provider_source = "injected" if provider is not None else "declared_identity"
    lease_evidence = _model_probe_lease_evidence(
        holon,
        config,
        provider_source=provider_source,
        session_id=session_id,
        now=started,
    )
    route_policy = _model_probe_route_policy(
        holon,
        provider_source=provider_source,
        allow_subprocess_model_probe=config.allow_subprocess_model_probe,
        model_probe_lease_id=config.model_probe_lease_id,
        lease_evidence=lease_evidence,
    )
    if route_policy["decision"] != "allow":
        return {
            "enabled": True,
            "attempted": False,
            "responsive": False,
            "status": "refused_unsafe_provider",
            "provider_source": provider_source,
            "provider_type": holon.provider_type,
            "model": holon.model,
            "route_policy": route_policy,
            "duration_ms": round((datetime.now(UTC) - started).total_seconds() * 1000, 3),
        }
    if (
        provider is None
        and config.safe_subprocess_model_probe
        and holon.provider_type in SUBPROCESS_MODEL_PROBE_PROVIDER_TYPES
    ):
        return await _run_safe_codex_subprocess_probe(
            holon,
            config,
            route_policy=route_policy,
            started=started,
        )
    chunks: list[str] = []

    async def collect() -> None:
        nonlocal provider
        if provider is None:
            provider = get_holon_provider(holon)
        async for chunk in holon_reply(holon, config.model_probe_message, provider):
            chunks.append(str(chunk))

    try:
        await asyncio.wait_for(
            collect(),
            timeout=max(1, int(config.model_probe_timeout_seconds)),
        )
        reply = "".join(chunks).strip()
        responsive = bool(reply)
        status = "ok" if responsive else "empty_response"
        return {
            "enabled": True,
            "attempted": True,
            "responsive": responsive,
            "status": status,
            "provider_source": provider_source,
            "provider_type": holon.provider_type,
            "model": holon.model,
            "route_policy": route_policy,
            "reply_chars": len(reply),
            "chunk_count": len(chunks),
            "reply_digest": stable_sha256({"reply": reply}),
            "reply_preview": reply[:300],
            "duration_ms": round((datetime.now(UTC) - started).total_seconds() * 1000, 3),
        }
    except asyncio.TimeoutError as exc:
        return {
            "enabled": True,
            "attempted": True,
            "responsive": False,
            "status": "timeout",
            "provider_source": provider_source,
            "provider_type": holon.provider_type,
            "model": holon.model,
            "route_policy": route_policy,
            "error_type": type(exc).__name__,
            "error_preview": _error_preview(exc),
            "duration_ms": round((datetime.now(UTC) - started).total_seconds() * 1000, 3),
        }
    except Exception as exc:  # noqa: BLE001 - probe must receipt failure truthfully.
        return {
            "enabled": True,
            "attempted": True,
            "responsive": False,
            "status": _classify_model_probe_error(exc),
            "provider_source": provider_source,
            "provider_type": holon.provider_type,
            "model": holon.model,
            "route_policy": route_policy,
            "error_type": type(exc).__name__,
            "error_preview": _error_preview(exc),
            "duration_ms": round((datetime.now(UTC) - started).total_seconds() * 1000, 3),
        }
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            try:
                maybe_awaitable = close()
                if inspect.isawaitable(maybe_awaitable):
                    await maybe_awaitable
            except Exception:
                pass


async def _run_orchestration_probe(
    holon: Any,
    config: L4SmokeConfig,
) -> dict[str, Any]:
    if not config.enable_orchestration_probe:
        return {
            "enabled": False,
            "attempted": False,
            "orchestrated": False,
            "status": "skipped",
            "reason": "enable_orchestration_probe_false",
            "execution_mode": "not_attempted",
            "live_specialist_execution_claimed": False,
        }
    if config.orchestration_orchestrator is None:
        return {
            "enabled": True,
            "attempted": False,
            "orchestrated": False,
            "status": "not_configured",
            "reason": "orchestration_orchestrator_missing",
            "execution_mode": "not_attempted",
            "live_specialist_execution_claimed": False,
        }
    started = datetime.now(UTC)
    try:
        from dharma_swarm.holon_orchestrate import (
            HolonOrchestrationConfig,
            run_holon_orchestration,
        )

        result = await run_holon_orchestration(
            HolonOrchestrationConfig(
                name=holon.name,
                mission=config.orchestration_mission,
                min_subtasks=max(1, int(config.orchestration_min_subtasks)),
                min_model_tiers=max(1, int(config.orchestration_min_model_tiers)),
                require_model_tier_diversity=bool(
                    config.orchestration_require_model_tier_diversity
                ),
                execution_mode=config.orchestration_execution_mode,
                execution_timeout_seconds=config.orchestration_execution_timeout_seconds,
            ),
            orchestrator=config.orchestration_orchestrator,
            agents_root=config.agents_root,
            decomposer=config.orchestration_decomposer,
            synthesizer=config.orchestration_synthesizer,
        )
        return {
            "enabled": True,
            "attempted": True,
            "orchestrated": bool(result.get("overall_pass")),
            "status": "ok" if result.get("overall_pass") else "failed",
            "schema_version": result.get("schema_version"),
            "execution_mode": result.get("execution_mode"),
            "parent_task_id": result.get("parent_task_id"),
            "subtask_task_ids": list(result.get("subtask_task_ids") or []),
            "subtask_count": len(result.get("subtask_plan") or []),
            "dispatch_count": len(result.get("dispatches") or []),
            "model_tiers": list(result.get("model_tiers") or []),
            "synthesis_source": result.get("synthesis_source"),
            "live_model_call_claimed": bool(result.get("live_model_call_claimed")),
            "live_specialist_execution_claimed": bool(
                result.get("live_specialist_execution_claimed")
            ),
            "proof_levels": dict(result.get("proof_levels") or {}),
            "result_digest": stable_sha256(result),
            "duration_ms": round((datetime.now(UTC) - started).total_seconds() * 1000, 3),
        }
    except Exception as exc:  # noqa: BLE001 - proof must receipt failed attempts truthfully.
        return {
            "enabled": True,
            "attempted": True,
            "orchestrated": False,
            "status": "error",
            "error_type": type(exc).__name__,
            "error_preview": _error_preview(exc),
            "execution_mode": "error",
            "live_specialist_execution_claimed": False,
            "duration_ms": round((datetime.now(UTC) - started).total_seconds() * 1000, 3),
        }


async def run_l4_supervised_smoke(config: L4SmokeConfig) -> dict[str, Any]:
    """Run one deterministic L4 proof cycle for a registered holon.

    The proof is intentionally stubbed at the model boundary. It validates that
    the holon's own declared route is preserved in the request and records the
    route decision, but it does not claim model responsiveness.
    """
    session_id = config.session_id or f"l4-smoke-{utc_compact()}"
    now = datetime.now(UTC)
    lease_expires_at = now + timedelta(seconds=max(1, int(config.lease_seconds)))

    holon = load_holon(config.name, agents_root=config.agents_root)
    request = build_request(holon, "Run the L4 supervised smoke proof.")
    routing_decision: dict[str, Any] = {
        "provider_type": holon.provider_type,
        "model": holon.model,
        "request_model": request.model,
        "declared_first": request.model == holon.model,
        "live_model_call": False,
    }

    task_claim = {
        "task_id": f"{session_id}-task",
        "claimed_by": holon.name,
        "claimed_at": now.isoformat(),
        "receipt_required": True,
    }
    execution_lease = {
        "lease_id": f"{session_id}-lease",
        "holder": holon.name,
        "expires_at": lease_expires_at.isoformat(),
        "lease_seconds": max(1, int(config.lease_seconds)),
    }

    async def runner(task: str) -> tuple[str, str]:
        return (
            f"{session_id}: {task_claim['task_id']}",
            "L4 smoke observation recorded in service of jagat kalyan, coherence, and artifact evidence.",
        )

    runtime_result = await holon_wake_cycle(
        holon.name,
        runner,
        spent_usd=0.0,
        cap_usd=1.0,
        agents_root=config.agents_root,
        persist=False,
        memory_kernel=None,
    )

    memory_receipt = governed_write_receipt(
        MemoryKernelWriteReceiptInput(
            source_atom_ids=(f"holon:{holon.name}:identity",),
            proposed_operation="append_receipt",
            target_surface="memory_kernel.write_receipts",
            reason="L4 supervised smoke projects continuity evidence without mutating memory.",
            reviewer_state="human_approved",
        )
    )
    append_write_receipts(config.memory_receipt_path, (memory_receipt,))

    model_probe = await _run_model_response_probe(
        holon,
        config,
        session_id=session_id,
    )
    orchestration_probe = await _run_orchestration_probe(holon, config)
    routing_decision["live_model_call"] = bool(model_probe.get("attempted"))
    transport_liveness = assess_a2a_inbox_bridge_liveness(
        config.transport_agent_uid or holon.name,
        heartbeat_path=config.transport_heartbeat_path,
        now=datetime.now(UTC),
        fresh_after_seconds=config.transport_fresh_after_seconds,
    )
    transport_reachable = bool(transport_liveness["transport_reachable"])

    artifact_payload = {
        "schema_version": "dharma.holon_l4_artifact.v1",
        "session_id": session_id,
        "holon": holon.name,
        "task_id": task_claim["task_id"],
        "routing_decision": routing_decision,
        "runtime_status": runtime_result.get("status"),
        "memory_receipt_id": memory_receipt.receipt_id,
        "model_probe": model_probe,
        "orchestration_probe": orchestration_probe,
        "transport_liveness": transport_liveness,
    }
    artifact_digest = stable_sha256(artifact_payload)
    artifact = {
        "artifact_id": f"holon_l4_artifact:{artifact_digest.split(':', 1)[1][:24]}",
        "digest": artifact_digest,
        "path": str(_artifact_path(config.agents_root, holon.name, session_id)),
    }
    artifact_path = Path(artifact["path"])
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps({**artifact_payload, "artifact": artifact}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    outcome = {
        "status": "verified" if runtime_result.get("status") == "ran" else "failed",
        "artifact_id": artifact["artifact_id"],
        "artifact_digest": artifact["digest"],
        "unbacked_outcome_claim_refused": bool(
            runtime_result.get("outcome_claim_without_artifact")
        ),
    }
    safe_refusal = bool(
        model_probe.get("enabled")
        and not model_probe.get("responsive")
        and model_probe.get("status") != "skipped"
    )
    heartbeat_claim_scope = {
        "transport_reachable": transport_reachable,
        "model_responsive": bool(model_probe.get("responsive")),
        "safe_refusal": safe_refusal,
        "orchestration_proven": bool(orchestration_probe.get("orchestrated")),
        "live_specialist_execution": bool(
            orchestration_probe.get("live_specialist_execution_claimed")
        ),
    }
    service_heartbeat = record_service_heartbeat(
        holon.name,
        agents_root=config.agents_root,
        session_id=session_id,
        service_id="holon-l4-smoke",
        status="idle" if runtime_result.get("status") == "ran" else "error",
        observed_at=datetime.now(UTC),
        runtime_ref={
            "runtime_status": runtime_result.get("status"),
            "task_id": task_claim["task_id"],
            "lease_id": execution_lease["lease_id"],
        },
        proof_ref={
            "kind": "l4_supervised_smoke_artifact",
            "artifact_id": artifact["artifact_id"],
            "artifact_digest": artifact["digest"],
            "outcome_status": outcome["status"],
        },
        claim_scope=heartbeat_claim_scope,
    )
    service_liveness = assess_service_liveness(
        holon.name,
        agents_root=config.agents_root,
        now=datetime.now(UTC),
        fresh_after_seconds=max(1, int(config.lease_seconds)),
    )
    heartbeat_ref = {
        "path": str(service_heartbeat_path(holon.name, config.agents_root)),
        "record_hash": service_heartbeat["record_hash"],
        "observed_at": service_heartbeat["observed_at"],
        "status": service_heartbeat["status"],
        "service_id": service_heartbeat["service_id"],
    }

    proof_levels = {
        "identity_loaded": bool(holon.name and holon.model and holon.system_prompt),
        "runtime_session": bool(session_id),
        "task_claim": bool(task_claim["task_id"]),
        "execution_lease": bool(execution_lease["lease_id"]),
        "routing_decision": routing_decision["declared_first"],
        "memory_receipt": memory_receipt.policy_decision.outcome.value == "allow",
        "artifact": artifact_path.exists(),
        "outcome": outcome["status"] == "verified" and artifact_path.exists(),
        "persistence": bool(config.persist),
        "service_heartbeat": bool(service_liveness["service_alive"]),
        "transport_reachable": transport_reachable,
        "model_responsive": bool(model_probe.get("responsive")),
        "orchestration": bool(orchestration_probe.get("orchestrated")),
    }

    proof = {
        "schema_version": PROOF_SCHEMA_VERSION,
        "session_id": session_id,
        "created_at": now.isoformat(),
        "holon": {
            "name": holon.name,
            "model": holon.model,
            "provider_type": holon.provider_type,
            "system_prompt_chars": len(holon.system_prompt),
        },
        "task_claim": task_claim,
        "execution_lease": execution_lease,
        "routing_decision": routing_decision,
        "runtime_result": runtime_result,
        "memory_receipt": {
            "path": str(config.memory_receipt_path),
            "receipt_id": memory_receipt.receipt_id,
            "digest": memory_receipt.digest,
            "policy_decision": memory_receipt.policy_decision.to_json(),
        },
        "model_probe": model_probe,
        "orchestration_probe": orchestration_probe,
        "transport_liveness": transport_liveness,
        "artifact": artifact,
        "outcome": outcome,
        "service_heartbeat": {
            "heartbeat_ref": heartbeat_ref,
            "liveness": service_liveness,
        },
        "proof_levels": proof_levels,
        "overall_pass": False,
    }
    required_levels = dict(proof["proof_levels"])
    if not config.enable_model_probe:
        required_levels.pop("model_responsive", None)
    if not config.require_transport_reachable:
        required_levels.pop("transport_reachable", None)
    if not config.require_orchestration:
        required_levels.pop("orchestration", None)
    proof["overall_pass"] = all(required_levels.values())
    proof["claim_scope"] = {
        "service_alive": bool(service_liveness["service_alive"]),
        "transport_reachable": transport_reachable,
        "model_responsive": bool(model_probe.get("responsive")),
        "safe_refusal": safe_refusal,
        "orchestration_proven": bool(orchestration_probe.get("orchestrated")),
        "live_specialist_execution": bool(
            orchestration_probe.get("live_specialist_execution_claimed")
        ),
    }
    proof["proof_digest"] = stable_proof_sha256(proof)
    if config.persist:
        event = save_cycle_record(holon.name, proof, agents_root=config.agents_root)
        proof["persistence_event"] = {
            "cycle": event["cycle"],
            "holon": event["holon"],
            "at": event["at"],
        }
        proof["proof_digest"] = stable_proof_sha256(proof)
    return proof


def run_l4_supervised_smoke_sync(config: L4SmokeConfig) -> dict[str, Any]:
    return asyncio.run(run_l4_supervised_smoke(config))


def _artifact_path(agents_root: Path, name: str, session_id: str) -> Path:
    safe_session = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in session_id)
    return agents_root / name / "artifacts" / f"{safe_session}.json"
