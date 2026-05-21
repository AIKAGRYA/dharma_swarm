#!/usr/bin/env python3
"""Register an external persistent agent through the dharma_swarm desk.

This is the operator-facing wrapper around ``external_agent_registration``.
It keeps the lower-level registration code small while making onboarding
hard to miss for roaming systems such as Hermes, Codex, Claude Code,
OpenClaw, Kimi, or VPS workers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dharma_swarm.external_agent_registration import (  # noqa: E402
    AutonomyPolicy,
    ExternalRoamingWorker,
    WorkspacePolicy,
    external_agent_sandbox_root,
    register_external_worker,
)
from dharma_swarm.kaizen_ops_local import KaizenOpsLocal  # noqa: E402
from dharma_swarm.stigmergy import StigmergicMark, StigmergyStore  # noqa: E402


SCHEMA_VERSION = "dharma_external_agent_registration_manifest.v1"
ACTION_LOG_SCHEMA = "dharma_external_agent_action_log.v1"
ACTION_LOG_NAME = "action_log.jsonl"
COMPAT_ACTIONS_LOG_NAME = "actions.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ").lower()


def _slug(value: str, *, fallback: str = "agent") -> str:
    out = []
    last_sep = False
    for char in str(value or "").strip().lower():
        if char.isalnum():
            out.append(char)
            last_sep = False
        elif not last_sep:
            out.append("-")
            last_sep = True
    slug = "".join(out).strip("-")
    return slug or fallback


def _bounded_id(value: str, *, fallback: str = "agent", max_len: int = 63) -> str:
    slug = _slug(value, fallback=fallback)
    if len(slug) <= max_len:
        return slug
    return slug[:max_len].strip("-") or fallback


def _uid_from_callsign(value: str) -> str:
    return _bounded_id(value, fallback="agent").replace("-", "_")


def _json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=True, default=str) + "\n"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, default=str) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dump(payload), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("registration manifest root must be a JSON object")
    return data


def build_show_up_manifest(args: argparse.Namespace) -> dict[str, Any]:
    """Build a safe registration request from whoever just arrived."""
    stamp = _timestamp_slug()
    harness = args.harness or os.getenv("DHARMA_AGENT_HARNESS") or "unknown_external_harness"
    model_identity = (
        args.model_identity
        or os.getenv("DHARMA_AGENT_MODEL")
        or os.getenv("MODEL")
        or "unknown_model"
    )
    callsign = args.callsign or os.getenv("DHARMA_AGENT_CALLSIGN")
    if not callsign:
        callsign = _bounded_id(f"{harness}-{stamp}", fallback=f"agent-{stamp}")
    agent_uid = args.agent_uid or os.getenv("DHARMA_AGENT_UID") or _uid_from_callsign(callsign)
    display_name = args.display_name or callsign
    capabilities = tuple(args.capability or ())
    return {
        "schema_version": SCHEMA_VERSION,
        "agent_uid": agent_uid,
        "callsign": callsign,
        "display_name": display_name,
        "harness": harness,
        "model_identity": model_identity,
        "department": args.department,
        "role": args.role,
        "squad_id": args.squad_id,
        "team_id": args.team_id,
        "endpoint": args.endpoint or "pending://registration-desk-show-up",
        "mailbox": args.mailbox or "",
        "memory_namespace": f"agent:{agent_uid}",
        "trace_identity": f"trace:{agent_uid}",
        "status": "registered",
        "notes": args.notes
        or "Provisional show-up registration. Identity assigned by registration desk.",
        "registration_source": args.registration_source,
        "capabilities": capabilities,
        "metadata": {
            "show_up_mode": True,
            "registration_desk_assigned_identity": args.agent_uid is None,
            "declared_harness": bool(args.harness),
            "declared_model_identity": bool(args.model_identity),
            "operator": os.getenv("USER", ""),
        },
    }


def normalize_manifest(raw: dict[str, Any], *, dharma_home: Path) -> dict[str, Any]:
    data = deepcopy(raw)
    agent_uid = str(data.get("agent_uid") or "").strip()
    callsign = str(data.get("callsign") or "").strip()
    if not agent_uid:
        raise SystemExit("manifest requires agent_uid")
    if not callsign:
        raise SystemExit("manifest requires callsign")

    data.setdefault("display_name", callsign)
    data.setdefault("role", "external_worker")
    data.setdefault("department", "swarm")
    data.setdefault("squad_id", "external")
    data.setdefault("team_id", "dharma_swarm")
    data.setdefault("endpoint", "pending://manual")
    data.setdefault("mailbox", "")
    data.setdefault("memory_namespace", f"agent:{agent_uid}")
    data.setdefault("trace_identity", f"trace:{agent_uid}")
    data.setdefault("status", "registered")
    data.setdefault("registration_source", "registration_desk")
    data.setdefault("capabilities", [])
    data.setdefault("metadata", {})

    data.setdefault(
        "autonomy_policy",
        {
            "mode": "manual",
            "requires_approval": True,
            "explicit_task_assignment_required": True,
        },
    )
    workspace = dict(data.get("workspace_policy") or {})
    sandbox_root_raw = str(workspace.get("sandbox_root") or "").strip()
    default_home = Path.home() / ".dharma"
    default_external_root = external_agent_sandbox_root(default_home).expanduser()
    use_default_sandbox = not sandbox_root_raw
    if sandbox_root_raw:
        provided = Path(sandbox_root_raw).expanduser()
        if dharma_home != default_home and provided.is_relative_to(default_external_root):
            use_default_sandbox = True
    if use_default_sandbox:
        workspace["sandbox_root"] = str(external_agent_sandbox_root(dharma_home) / agent_uid)
    workspace.setdefault("repo_writes_allowed", False)
    workspace.setdefault("canonical_dharma_dir_writes_allowed", False)
    data["workspace_policy"] = workspace
    data.setdefault("authority", "external_worker_evidence_only")
    return data


def build_worker(manifest: dict[str, Any]) -> ExternalRoamingWorker:
    autonomy = manifest.get("autonomy_policy") or {}
    workspace = manifest.get("workspace_policy") or {}
    payload = dict(manifest)
    payload["autonomy_policy"] = AutonomyPolicy(**autonomy)
    payload["workspace_policy"] = WorkspacePolicy(**workspace)
    payload.pop("registration_desk", None)
    payload.pop("$schema", None)
    payload.pop("schema_version", None)
    return ExternalRoamingWorker(**payload)


def scaffold_self_filesystem(
    *,
    root: Path,
    worker: ExternalRoamingWorker,
    manifest: dict[str, Any],
    registration_result: dict[str, Any],
    manifest_path: Path | None,
) -> dict[str, str]:
    now = _utc_now()
    root.mkdir(parents=True, exist_ok=True)
    for rel in (
        "self_model",
        "logs",
        "receipts",
        "wake",
        "agentops",
        "scratch",
        "outbox",
        "inbox",
    ):
        (root / rel).mkdir(parents=True, exist_ok=True)

    normalized_manifest_path = root / "identity_manifest.normalized.json"
    registration_receipt_path = root / "receipts" / "registration_receipt.json"
    action_log_path = root / "logs" / ACTION_LOG_NAME
    compat_actions_log_path = root / "logs" / COMPAT_ACTIONS_LOG_NAME
    wake_log_path = root / "logs" / "wake_receipts.jsonl"
    system_map_path = root / "self_model" / "system_interpretation.md"
    required_path = root / "self_model" / "REQUIRED_FIRST_WRITE.md"
    agentops_contract_path = root / "agentops" / "contract.json"

    _write_json(normalized_manifest_path, manifest)
    _write_json(registration_receipt_path, registration_result)
    _write_text(
        root / "README.md",
        "\n".join(
            [
                f"# {worker.callsign} external-agent home",
                "",
                f"- agent_uid: `{worker.agent_uid}`",
                f"- callsign: `{worker.callsign}`",
                f"- model_identity: `{worker.model_identity}`",
                f"- authority: `{worker.authority.value}`",
                f"- memory_namespace: `{worker.memory_namespace}`",
                f"- trace_identity: `{worker.trace_identity}`",
                "",
                "This directory is the agent's sandboxed dharma_swarm filesystem.",
                f"The agent must append every material action to `logs/{ACTION_LOG_NAME}`.",
                "The agent must append every unattended wake to `logs/wake_receipts.jsonl`.",
                "Before doing substantive work, the agent must replace or extend",
                "`self_model/system_interpretation.md` with its own map of the system.",
                "",
            ]
        ),
    )
    _write_text(
        required_path,
        "\n".join(
            [
                "# Required First Write",
                "",
                "Before performing any non-trivial task, write your own interpretation",
                "of dharma_swarm into `system_interpretation.md`. Do not copy this file.",
                "",
                "Minimum required sections:",
                "",
                "1. Who I am: agent_uid, callsign, harness, model, authority.",
                "2. What dharma_swarm surfaces I can see.",
                "3. What I am allowed to mutate.",
                "4. Where I log actions and wake receipts.",
                "5. How I will stop or ask for approval.",
                "",
            ]
        ),
    )
    _write_text(
        system_map_path,
        "\n".join(
            [
                "# System Interpretation",
                "",
                f"- Created: {now}",
                f"- Agent UID: {worker.agent_uid}",
                f"- Callsign: {worker.callsign}",
                f"- Harness: {worker.harness}",
                f"- Model identity: {worker.model_identity}",
                "",
                "This is a placeholder. The agent must replace or extend it in its own",
                "words before performing substantive work.",
                "",
            ]
        ),
    )
    _write_json(
        agentops_contract_path,
        {
            "schema_version": "dharma_external_agent_agentops_contract.v1",
            "agent_uid": worker.agent_uid,
            "callsign": worker.callsign,
            "status": "agentops_ready_not_scheduled",
            "runner": "scripts/governance/run_agent_work_packet.py",
            "rule": (
                "Registration does not start AgentOps. Operator or dispatcher must "
                "issue an explicit work packet with allowed_files, forbidden_files, "
                "gates, and approval policy."
            ),
            "default_authority": worker.authority.value,
            "autonomy_policy": worker.autonomy_policy.model_dump(),
            "workspace_policy": worker.workspace_policy.model_dump(),
        },
    )

    action_event = {
        "schema_version": ACTION_LOG_SCHEMA,
        "event_id": f"registration:{worker.agent_uid}:{now}",
        "timestamp": now,
        "agent_uid": worker.agent_uid,
        "callsign": worker.callsign,
        "display_name": worker.display_name,
        "harness": worker.harness,
        "model_identity": worker.model_identity,
        "authority": worker.authority.value,
        "memory_namespace": worker.memory_namespace,
        "trace_identity": worker.trace_identity,
        "action": "register",
        "summary": "Registered through dharma_swarm external-agent registration desk.",
        "source_manifest": str(manifest_path) if manifest_path else "show_up_cli",
        "outputs": {
            "record_path": registration_result.get("record_path", ""),
            "onboarding_receipt": registration_result.get("onboarding_receipt", {}),
            "sandbox_root": str(root),
        },
        "status": "ok",
    }
    append_action_log(root, action_event)
    wake_log_path.touch(exist_ok=True)
    compat_actions_log_path.touch(exist_ok=True)

    return {
        "sandbox_root": str(root),
        "normalized_manifest_path": str(normalized_manifest_path),
        "registration_receipt_path": str(registration_receipt_path),
        "action_log_path": str(action_log_path),
        "actions_compat_path": str(compat_actions_log_path),
        "wake_log_path": str(wake_log_path),
        "system_interpretation_path": str(system_map_path),
        "agentops_contract_path": str(agentops_contract_path),
    }


def append_action_log(root: Path, event: dict[str, Any]) -> None:
    """Append to the canonical action log and the old plural mirror."""
    _append_jsonl(root / "logs" / ACTION_LOG_NAME, event)
    _append_jsonl(root / "logs" / COMPAT_ACTIONS_LOG_NAME, event)


def harden_a2a_card(
    *, dharma_home: Path, worker: ExternalRoamingWorker
) -> dict[str, Any]:
    """Make the A2A card discoverable as identity, not dispatch authority."""
    card_name = worker.callsign.replace("/", "_").replace("\\", "_")
    card_path = dharma_home / "a2a" / "cards" / f"{card_name}.json"
    if not card_path.exists():
        return {"status": "missing", "card_path": str(card_path)}
    try:
        card = json.loads(card_path.read_text(encoding="utf-8"))
        metadata = dict(card.get("metadata") or {})
        metadata.update(
            {
                "external_worker": True,
                "external_evidence_only": (
                    worker.authority.value == "external_worker_evidence_only"
                ),
                "dispatch_enabled": False,
                "requires_approval": worker.autonomy_policy.requires_approval,
                "authority": worker.authority.value,
                "autonomy_policy": worker.autonomy_policy.model_dump(),
                "workspace_policy": worker.workspace_policy.model_dump(),
                "registration_desk_hardened": True,
            }
        )
        card["metadata"] = metadata
        # `discover_available()` treats "starting" as available. Keep external
        # evidence-only workers visible by card lookup, but not route-ready.
        card["status"] = "registered"
        card["updated_at"] = _utc_now()
        _write_json(card_path, card)
        return {"status": "ok", "card_path": str(card_path)}
    except Exception as exc:  # pragma: no cover - defensive integration hook
        return {"status": "error", "card_path": str(card_path), "error": str(exc)}


def emit_kaizen_event(
    *, dharma_home: Path, worker: ExternalRoamingWorker, scaffold: dict[str, str]
) -> dict[str, Any]:
    try:
        ops = KaizenOpsLocal(db_path=dharma_home / "kaizen" / "ops.db")
        ops.ingest_event(
            category="external_agent_registration",
            source=worker.agent_uid,
            status="registered",
            metadata={
                "callsign": worker.callsign,
                "harness": worker.harness,
                "model_identity": worker.model_identity,
                "authority": worker.authority.value,
                "sandbox_root": scaffold["sandbox_root"],
            },
        )
        ops.close()
        return {"status": "ok", "db_path": str(dharma_home / "kaizen" / "ops.db")}
    except Exception as exc:  # pragma: no cover - defensive integration hook
        return {"status": "error", "error": str(exc)}


async def emit_stigmergy_mark(
    *, dharma_home: Path, worker: ExternalRoamingWorker, scaffold: dict[str, str]
) -> dict[str, Any]:
    try:
        store = StigmergyStore(base_path=dharma_home / "stigmergy")
        mark = StigmergicMark(
            agent=worker.agent_uid,
            file_path=scaffold["sandbox_root"],
            action="connect",
            observation=f"{worker.callsign} registered through external-agent desk",
            salience=0.82,
            channel="governance",
            connections=[
                worker.memory_namespace,
                worker.trace_identity,
                "a2a",
                "telemetry",
            ],
        )
        mark_id = await store.leave_mark(mark)
        return {"status": "ok", "mark_id": mark_id}
    except Exception as exc:  # pragma: no cover - defensive integration hook
        return {"status": "error", "error": str(exc)}


async def run_registration(args: argparse.Namespace) -> dict[str, Any]:
    dharma_home = args.dharma_home.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve() if args.manifest else None
    raw = load_manifest(manifest_path) if manifest_path else build_show_up_manifest(args)
    manifest = normalize_manifest(raw, dharma_home=dharma_home)
    worker = build_worker(manifest)

    if args.dry_run:
        return {
            "dry_run": True,
            "worker": worker.model_dump(),
            "canonical_onboarding": not args.no_canonical,
            "ops_hooks": not args.no_ops_hooks,
        }

    registration_result = await register_external_worker(
        worker,
        dharma_home=dharma_home,
        write_canonical_onboarding=not args.no_canonical,
    )
    root = external_agent_sandbox_root(dharma_home) / worker.agent_uid
    scaffold = scaffold_self_filesystem(
        root=root,
        worker=worker,
        manifest=manifest,
        registration_result=registration_result,
        manifest_path=manifest_path,
    )
    hooks: dict[str, Any] = {
        "a2a": harden_a2a_card(dharma_home=dharma_home, worker=worker)
        if not args.no_canonical
        else "skipped",
        "telemetry": "written_by_canonical_onboarding" if not args.no_canonical else "skipped",
        "agentops": "contract_written_not_scheduled",
    }
    if args.no_ops_hooks:
        hooks["kaizen_ops"] = "skipped"
        hooks["stigmergy"] = "skipped"
    else:
        hooks["kaizen_ops"] = emit_kaizen_event(
            dharma_home=dharma_home,
            worker=worker,
            scaffold=scaffold,
        )
        hooks["stigmergy"] = await emit_stigmergy_mark(
            dharma_home=dharma_home,
            worker=worker,
            scaffold=scaffold,
        )

    summary = {
        "schema_version": "dharma_external_agent_registration_result.v1",
        "created_at": _utc_now(),
        "agent_uid": worker.agent_uid,
        "callsign": worker.callsign,
        "registration_result": registration_result,
        "scaffold": scaffold,
        "hooks": hooks,
    }
    _write_json(root / "receipts" / "registration_desk_result.json", summary)
    append_action_log(
        root,
        {
            "schema_version": ACTION_LOG_SCHEMA,
            "event_id": f"ops_hooks:{worker.agent_uid}:{summary['created_at']}",
            "timestamp": summary["created_at"],
            "agent_uid": worker.agent_uid,
            "callsign": worker.callsign,
            "model_identity": worker.model_identity,
            "authority": worker.authority.value,
            "action": "emit_registration_hooks",
            "summary": "Emitted registration desk ops hooks.",
            "outputs": hooks,
            "status": "ok",
        },
    )
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register an external persistent agent in dharma_swarm."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help=(
            "Optional full manifest. If omitted, the desk performs a show-up "
            "registration from CLI/env fields and assigns safe defaults."
        ),
    )
    parser.add_argument(
        "--dharma-home",
        type=Path,
        default=Path.home() / ".dharma",
        help="State root to write under. Defaults to ~/.dharma.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the normalized worker without writing.",
    )
    parser.add_argument(
        "--no-canonical",
        action="store_true",
        help="Write only external_agents registration/scaffold, not A2A/telemetry.",
    )
    parser.add_argument(
        "--no-ops-hooks",
        action="store_true",
        help="Skip KaizenOps and Stigmergy hook emission.",
    )
    parser.add_argument("--agent-uid", default=None)
    parser.add_argument("--callsign", default=None)
    parser.add_argument("--display-name", default=None)
    parser.add_argument("--harness", default=None)
    parser.add_argument("--model-identity", default=None)
    parser.add_argument("--endpoint", default=None)
    parser.add_argument("--mailbox", default=None)
    parser.add_argument("--department", default="swarm")
    parser.add_argument("--role", default="external_worker")
    parser.add_argument("--squad-id", default="external")
    parser.add_argument("--team-id", default="dharma_swarm")
    parser.add_argument("--capability", action="append", default=[])
    parser.add_argument("--notes", default="")
    parser.add_argument("--registration-source", default="registration_desk_show_up")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = asyncio.run(run_registration(args))
    print(json.dumps(result, indent=2, ensure_ascii=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
