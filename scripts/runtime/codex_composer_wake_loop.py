#!/usr/bin/env python3
"""Governed manual wake loop for admitted agent seats (default codex_composer).

This is a repo-owned control shell for an admitted agent identity. It
does not grant source-write authority, approve work, install launchd/cron jobs,
or treat a broker publish as live collaboration. The default ``once`` command
rehydrates canonical context, runs a bounded read-only orientation pass, checks
assigned work surfaces, and writes heartbeat/status/receipt artifacts.

Agent identity is threaded through a :class:`WakeProfile` so that additional
seats (e.g. ``fable_composer``) reuse this one governed loop instead of forking
a near-duplicate god-file per agent. Select the seat with ``--agent-uid``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.model_hierarchy import default_model  # noqa: E402
from dharma_swarm.models import ProviderType  # noqa: E402
from dharma_swarm.operator_core.execution_lease import (  # noqa: E402
    ExecutionLeaseError,
    find_execution_lease_for_task,
    load_execution_lease,
    load_revoked_lease_ids,
    validate_execution_lease,
)

DEFAULT_AGENT_UID = "codex_composer"
AUTHORITY_MODE = "read_only_until_execution_lease"
DEFAULT_DHARMA_HOME = Path("~/.dharma")
DEFAULT_INTERVAL_S = 900.0
WAKE_LOOP_START_ACTION = "wake_loop_start"


@dataclass(frozen=True)
class WakeProfile:
    """Per-seat identity for the governed wake loop.

    Threading identity through a profile lets a single governed loop serve every
    admitted seat. Authority stays ``read_only_until_execution_lease`` for all
    seats; a profile never widens authority.
    """

    agent_uid: str
    callsign: str
    display_name: str
    model_identity: str
    schema_prefix: str
    session: str
    extra_addresses: tuple[str, ...] = ()


def _codex_model_identity() -> str:
    return os.getenv("DGC_DIRECTOR_CODEX_MODEL", "").strip() or default_model(ProviderType.CODEX)


def _claude_model_identity() -> str:
    # Fable's Tier-2 mind is the Claude Max-plan claude_code route, not a metered
    # API model. Fall back gracefully if the provider enum lacks CLAUDE_CODE.
    override = os.getenv("DGC_DIRECTOR_FABLE_MODEL", "").strip()
    if override:
        return override
    provider = getattr(ProviderType, "CLAUDE_CODE", None)
    if provider is not None:
        try:
            return default_model(provider)
        except Exception:  # noqa: BLE001 - defensive: never fail wake on model lookup
            pass
    return "claude-code"


def _sarathi_model_identity() -> str:
    # PR-S3 (operator ruling 2026-07-30): the apex seat defaults to a frontier
    # mind, never a flash-tier one. DGC_DIRECTOR_SARATHI_MODEL stays the
    # operator override; the fallback chain resolves the Anthropic frontier
    # default from model_hierarchy rather than pinning a dated string here.
    override = os.getenv("DGC_DIRECTOR_SARATHI_MODEL", "").strip()
    if override:
        return override
    try:
        return default_model(ProviderType.ANTHROPIC)
    except Exception:  # noqa: BLE001 - defensive: never fail wake on model lookup
        return "claude-opus-4-6"


def _slug(agent_uid: str) -> str:
    return agent_uid.replace("_", "-")


# Registry of admitted seats. Adding a seat here (plus its canonical context
# files on disk) is all that is required to reuse the governed loop — no fork.
WAKE_PROFILES: dict[str, WakeProfile] = {
    "codex_composer": WakeProfile(
        agent_uid="codex_composer",
        callsign="codex_composer",
        display_name="Codex Composer",
        model_identity=_codex_model_identity(),
        schema_prefix="dharma.codex_composer",
        session="codex-composer-wake",
        extra_addresses=("codex", "codex-composer"),
    ),
    "fable_composer": WakeProfile(
        agent_uid="fable_composer",
        callsign="fable_composer",
        display_name="Fable Composer",
        model_identity=_claude_model_identity(),
        schema_prefix="dharma.fable_composer",
        session="fable-composer-wake",
        extra_addresses=("fable", "fable-composer", "fable_5_cursor", "fable-5-cursor"),
    ),
    "sarathi": WakeProfile(
        agent_uid="sarathi",
        callsign="sarathi",
        display_name="Sarathi Apex",
        model_identity=_sarathi_model_identity(),
        schema_prefix="dharma.sarathi",
        session="sarathi-wake",
        extra_addresses=("sarathi-apex", "apex-holon", "chief-of-staff"),
    ),
}


def resolve_profile(agent_uid: str | None) -> WakeProfile:
    """Return the WakeProfile for an admitted seat.

    Unknown but well-formed agent uids get a conservative generic profile so the
    loop degrades safely instead of crashing; authority stays lease-gated.
    """
    uid = (agent_uid or DEFAULT_AGENT_UID).strip()
    if not uid:
        uid = DEFAULT_AGENT_UID
    if uid in WAKE_PROFILES:
        return WAKE_PROFILES[uid]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", uid):
        raise ValueError(f"invalid agent uid: {uid!r}")
    return WakeProfile(
        agent_uid=uid,
        callsign=uid,
        display_name=uid.replace("_", " ").title(),
        model_identity=os.getenv("DGC_DIRECTOR_WAKE_MODEL", "").strip() or "unspecified",
        schema_prefix=f"dharma.{uid}",
        session=f"{_slug(uid)}-wake",
    )

OPEN_STATUSES = {"", "pending", "open", "ready", "new", "unread"}
TERMINAL_STATUSES = {"completed", "failed", "blocked", "done", "closed", "cancelled"}
SECRET_NAME_RE = re.compile(r"(secret|token|password|private[_-]?key|api[_-]?key|credential)", re.I)
SECRET_VALUE_RE = re.compile(
    r"(?i)\b(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|AKIA[0-9A-Z]{12,}|xox[baprs]-[A-Za-z0-9-]{12,})\b"
)

WRITE_CAPABLE_TERMS = {
    "write",
    "edit",
    "modify",
    "patch",
    "apply",
    "commit",
    "push",
    "merge",
    "approve",
    "deploy",
    "start",
    "stop",
    "kill",
    "restart",
    "cron",
    "launchd",
    "tmux",
    "daemon",
    "service",
    "register",
    "delete",
    "remove",
    "secret",
    "credential",
}

PROTECTED_TERMS = {
    "governance/kernel",
    "dharma kernel",
    "meta_dharma",
    "telos",
    "dgm",
    "protected governance",
    "context bundle",
    "pr approval",
}

def canonical_context_layout(agent_uid: str) -> tuple[tuple[str, str], ...]:
    """Canonical context file map for a seat, relative to the dharma home.

    Fable's seat body keeps its cold-boot procedure at ``agents/<uid>/BOOT.md``
    and its nest under ``external_agents/<uid>/nest``; codex uses
    ``HOLON_CONTEXT.md``. Both optional names are listed so a seat surfaces
    whichever it actually has instead of always reporting one as missing.
    """
    return (
        ("holon_context", f"agents/{agent_uid}/HOLON_CONTEXT.md"),
        ("boot", f"agents/{agent_uid}/BOOT.md"),
        ("identity", f"agents/{agent_uid}/identity.json"),
        ("a2a_card", f"a2a/cards/{agent_uid}.json"),
        ("agent_passport", f"agent_passports/{agent_uid}.json"),
        ("external_registration", f"external_agents/{agent_uid}/registration.json"),
        ("bridge_heartbeat", f"a2a_bus/bridge_heartbeats/{agent_uid}.json"),
        ("a2a_state", f"a2a_bus/state/{agent_uid}.json"),
        ("external_authority_passport", f"external_agents/{agent_uid}/authority/passport.json"),
    )


# Context files that are optional (a seat may legitimately have only one of a
# holon_context / boot pair). These are not counted as "missing" for status.
OPTIONAL_CONTEXT_KEYS = {"holon_context", "boot", "external_registration", "external_authority_passport"}


@dataclass(frozen=True)
class CommandResult:
    code: int
    stdout: str
    stderr: str
    duration_s: float


@dataclass(frozen=True)
class ComposerPaths:
    dharma_home: Path
    repo_root: Path
    agent_home: Path
    external_home: Path
    nest: Path
    logs: Path
    receipts: Path
    actions: Path
    wake_receipts: Path
    action_log: Path
    status: Path
    heartbeat: Path
    latest_receipt: Path
    living_agent: Path
    assigned_inbox: Path
    external_inbox: Path
    task_queue: Path
    leases: Path
    future_orchestration: Path
    agent_uid: str = DEFAULT_AGENT_UID
    profile: WakeProfile = field(default_factory=lambda: WAKE_PROFILES[DEFAULT_AGENT_UID])


Runner = Callable[[list[str], Path, float], CommandResult]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def expand(path: str | Path) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


def composer_paths(
    dharma_home: str | Path = DEFAULT_DHARMA_HOME,
    *,
    repo_root: str | Path = REPO_ROOT,
    agent_uid: str | None = None,
    profile: WakeProfile | None = None,
) -> ComposerPaths:
    resolved = profile or resolve_profile(agent_uid)
    uid = resolved.agent_uid
    root = expand(dharma_home)
    external = root / "external_agents" / uid
    nest = external / "nest"
    return ComposerPaths(
        dharma_home=root,
        repo_root=expand(repo_root),
        agent_home=root / "agents" / uid,
        external_home=external,
        nest=nest,
        logs=external / "logs",
        receipts=nest / "receipts",
        actions=nest / "actions",
        wake_receipts=external / "logs" / "wake_receipts.jsonl",
        action_log=external / "logs" / "action_log.jsonl",
        status=nest / "status.json",
        heartbeat=nest / "heartbeat.json",
        latest_receipt=nest / "latest_receipt.json",
        living_agent=root / "agents" / uid / "living_agent.json",
        assigned_inbox=root / "a2a_bus" / "inboxes" / uid,
        external_inbox=external / "inbox",
        task_queue=root / "a2a_bus" / "tasks" / "queue.jsonl",
        leases=root / "a2a_bus" / "leases",
        future_orchestration=nest / "future_orchestration.json",
        agent_uid=uid,
        profile=resolved,
    )


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, default=_json_default) + "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _line in handle)


def last_jsonl(path: Path) -> dict[str, Any] | None:
    last = None
    for row in read_jsonl(path):
        last = row
    return last


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def scrub_text(value: str, *, limit: int = 500) -> str:
    cleaned = SECRET_VALUE_RE.sub("[REDACTED_SECRET]", " ".join(value.split()))
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def safe_json_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"type": type(payload).__name__}
    keys = sorted(str(key) for key in payload.keys())
    summary: dict[str, Any] = {"keys": keys[:80]}
    for key in (
        "agent_uid",
        "agent",
        "callsign",
        "authority",
        "authority_mode",
        "registration_authority",
        "status",
        "l4_status",
        "wake_loop_active",
        "wake_policy_id",
        "last_seen_at",
        "last_active",
        "timestamp",
        "subject",
        "consumer",
        "stream",
    ):
        if key in payload and not SECRET_NAME_RE.search(key):
            summary[key] = payload.get(key)
    if "autonomy_policy" in payload and isinstance(payload["autonomy_policy"], dict):
        policy = payload["autonomy_policy"]
        summary["autonomy_policy"] = {
            key: policy.get(key)
            for key in sorted(policy)
            if key in {"mode", "requires_approval", "can_approve_prs", "can_write_source", "can_mutate_telos"}
        }
    if "capabilities" in payload:
        caps = payload["capabilities"]
        if isinstance(caps, dict):
            summary["capabilities"] = {
                key: caps.get(key)
                for key in ("allowed", "gated", "forbidden")
                if key in caps
            }
        elif isinstance(caps, list):
            summary["capability_count"] = len(caps)
    return summary


def canonical_context_paths(paths: ComposerPaths) -> dict[str, Path]:
    layout = canonical_context_layout(paths.agent_uid)
    return {name: paths.dharma_home / relative for name, relative in layout}


def rehydrate_context(paths: ComposerPaths) -> dict[str, Any]:
    files: dict[str, Any] = {}
    missing: list[str] = []
    authority_facts: dict[str, Any] = {
        "agent_uid": paths.agent_uid,
        "default_authority": AUTHORITY_MODE,
        "no_self_approval": True,
        "no_pr_approval": True,
        "protected_mutation_allowed": False,
        "secrets_in_artifacts_allowed": False,
    }
    for name, path in canonical_context_paths(paths).items():
        entry: dict[str, Any] = {"path": str(path), "exists": path.exists()}
        if not path.exists():
            if name not in OPTIONAL_CONTEXT_KEYS:
                missing.append(name)
            files[name] = entry
            continue
        data = path.read_bytes()
        stat = path.stat()
        entry.update(
            {
                "bytes": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
                "sha256": sha256_bytes(data),
            }
        )
        if path.suffix == ".json":
            entry["summary"] = safe_json_summary(read_json(path, {}))
        elif name == "holon_context":
            text = data.decode("utf-8", errors="replace")
            entry["summary"] = {
                "title": next((line.strip("# ").strip() for line in text.splitlines() if line.startswith("#")), ""),
                "mentions_read_only_until_execution_lease": "read_only_until_execution_lease" in text,
                "mentions_publish_acceptance_boundary": "PUBLISH_ACCEPTED" in text,
                "mentions_wake_loop_not_ratified": "standing wake loop" in text or "wake loop is not" in text,
            }
        files[name] = entry

    identity = files.get("identity", {}).get("summary", {})
    state = files.get("a2a_state", {}).get("summary", {})
    passport = files.get("agent_passport", {}).get("summary", {})
    external_passport = files.get("external_authority_passport", {}).get("summary", {})
    authority_facts.update(
        {
            "identity_authority_mode": identity.get("authority_mode"),
            "identity_wake_loop_active": identity.get("wake_loop_active"),
            "state_wake_loop_active": state.get("wake_loop_active"),
            "passport_authority_mode": passport.get("authority_mode"),
            "external_registration_authority": files.get("external_registration", {}).get("summary", {}).get("authority"),
            "external_passport_rank": external_passport.get("status"),
        }
    )
    return {
        "schema_version": f"{paths.profile.schema_prefix}.rehydrated_context.v1",
        "generated_at": utc_now(),
        "files": files,
        "missing": missing,
        "authority_facts": authority_facts,
    }


def repo_python(repo_root: Path) -> Path:
    venv = repo_root / ".venv" / "bin" / "python"
    return venv if venv.exists() else Path(sys.executable)


def default_runner(command: list[str], cwd: Path, timeout_s: float) -> CommandResult:
    started = time.monotonic()
    env = dict(os.environ)
    for key in list(env):
        if SECRET_NAME_RE.search(key):
            env.pop(key, None)
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
        env=env,
    )
    return CommandResult(
        code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        duration_s=round(time.monotonic() - started, 3),
    )


def command_receipt(result: CommandResult, command: list[str]) -> dict[str, Any]:
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    return {
        "command": command,
        "command_display": " ".join(shlex.quote(part) for part in command),
        "exit_code": result.code,
        "duration_s": result.duration_s,
        "stdout_sha256": sha256_text(stdout),
        "stderr_sha256": sha256_text(stderr),
        "stdout_tail": scrub_text(stdout[-1600:], limit=1600),
        "stderr_tail": scrub_text(stderr[-1600:], limit=1600),
    }


def run_orientation_cycle(
    paths: ComposerPaths,
    *,
    runner: Runner = default_runner,
    timeout_s: float = 30.0,
    skip_orientation_command: bool = False,
) -> dict[str, Any]:
    commands: list[list[str]] = [
        ["git", "status", "--short", "--branch"],
        ["git", "rev-parse", "HEAD"],
    ]
    if not skip_orientation_command:
        commands.append([str(repo_python(paths.repo_root)), "scripts/governance/orientation_graph.py", "--json"])

    receipts = []
    for command in commands:
        try:
            result = runner(command, paths.repo_root, timeout_s)
        except FileNotFoundError as exc:
            result = CommandResult(code=127, stdout="", stderr=str(exc), duration_s=0.0)
        except subprocess.TimeoutExpired as exc:
            result = CommandResult(
                code=124,
                stdout=exc.stdout if isinstance(exc.stdout, str) else "",
                stderr=exc.stderr if isinstance(exc.stderr, str) else "timeout",
                duration_s=timeout_s,
            )
        receipts.append(command_receipt(result, command))
    return {
        "schema_version": f"{paths.profile.schema_prefix}.orientation_cycle.v1",
        "generated_at": utc_now(),
        "bounded": True,
        "read_only_intent": True,
        "commands": receipts,
        "errors": [item for item in receipts if item["exit_code"] != 0],
    }


def stable_trigger_id(kind: str, source: str, payload_digest: str) -> str:
    return hashlib.sha256(f"{kind}:{source}:{payload_digest}".encode("utf-8")).hexdigest()[:20]


def payload_digest(payload: Any) -> str:
    return sha256_text(json.dumps(payload, sort_keys=True, default=_json_default))


def assigned_addresses(context: Mapping[str, Any], profile: WakeProfile | None = None) -> set[str]:
    profile = profile or WAKE_PROFILES[DEFAULT_AGENT_UID]
    addresses = {profile.agent_uid, profile.callsign, *profile.extra_addresses}
    card = context.get("files", {}).get("a2a_card", {}).get("summary", {})
    agent_name = card.get("agent") or card.get("agent_uid")
    if agent_name:
        addresses.add(str(agent_name))
    return {address for item in list(addresses) for address in (item, item.lower())}


def message_summary(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        for key in ("subject", "summary", "body", "message", "type", "id", "task_id"):
            value = payload.get(key)
            if value:
                return scrub_text(str(value), limit=220)
    if isinstance(payload, str):
        return scrub_text(payload, limit=220)
    return fallback


def trigger_record(kind: str, source_path: Path, payload: Any, *, status: str = "") -> dict[str, Any]:
    digest = payload_digest(payload)
    return {
        "trigger_id": stable_trigger_id(kind, str(source_path), digest),
        "kind": kind,
        "source_path": str(source_path),
        "status": status,
        "summary": message_summary(payload, source_path.name),
        "payload_sha256": digest,
        "payload_keys": sorted(str(key) for key in payload.keys()) if isinstance(payload, dict) else [],
    }


def collect_inbox_messages(paths: ComposerPaths) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for inbox in (paths.assigned_inbox, paths.external_inbox):
        if not inbox.exists():
            continue
        for path in sorted(item for item in inbox.iterdir() if item.is_file()):
            if path.suffix.lower() == ".json":
                payload = read_json(path, {})
            else:
                payload = {"body": path.read_text(encoding="utf-8", errors="replace"), "file_name": path.name}
            status = str(payload.get("status") if isinstance(payload, dict) else "").lower()
            read_flag = bool(payload.get("read") is True) if isinstance(payload, dict) else False
            if status in TERMINAL_STATUSES or read_flag:
                continue
            messages.append(trigger_record("inbox", path, payload, status=status))
    return messages


def collect_task_messages(paths: ComposerPaths, addresses: set[str]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if not paths.task_queue.exists():
        return messages
    for row in read_jsonl(paths.task_queue):
        to_value = str(row.get("to") or row.get("agent_uid") or row.get("recipient") or "").strip()
        if not to_value or (to_value not in addresses and to_value.lower() not in addresses):
            continue
        status = str(row.get("status") or "pending").lower()
        if status not in OPEN_STATUSES:
            continue
        messages.append(trigger_record("task", paths.task_queue, row, status=status))
    return messages


def collect_assigned_work(paths: ComposerPaths, context: Mapping[str, Any]) -> dict[str, Any]:
    addresses = assigned_addresses(context, paths.profile)
    inbox = collect_inbox_messages(paths)
    tasks = collect_task_messages(paths, addresses)
    return {
        "schema_version": f"{paths.profile.schema_prefix}.assigned_work.v1",
        "checked_surfaces": [
            str(paths.assigned_inbox),
            str(paths.external_inbox),
            str(paths.task_queue),
        ],
        "addresses": sorted(addresses),
        "observed_messages": [*inbox, *tasks],
    }


def text_requires_execution_lease(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in WRITE_CAPABLE_TERMS | PROTECTED_TERMS)


def payload_field(payload: Mapping[str, Any], *keys: str) -> str:
    """Return the first non-empty top-level or envelope field."""
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)
    envelope = payload.get("envelope")
    if isinstance(envelope, Mapping):
        for key in keys:
            value = envelope.get(key)
            if value:
                return str(value)
    return ""


def payload_task_id(payload: Mapping[str, Any], record: Mapping[str, Any]) -> str:
    return (
        payload_field(payload, "id", "task_id", "packet_id", "correlation_id")
        or str(record.get("trigger_id") or "")
    )


def payload_correlation_id(payload: Mapping[str, Any]) -> str:
    return payload_field(payload, "correlation_id", "packet_id")


def payload_request_text(payload: Mapping[str, Any], summary: str = "") -> str:
    """Extract requested work text without letting lease fields describe scope."""
    parts = [summary]
    request_keys = (
        "title",
        "body",
        "task",
        "message",
        "description",
        "instruction",
        "content",
        "summary",
    )
    for container in (payload, payload.get("envelope")):
        if not isinstance(container, Mapping):
            continue
        for key in request_keys:
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
    return " ".join(dict.fromkeys(part for part in parts if part)).strip()


def payload_declared_actions(payload: Mapping[str, Any]) -> list[str]:
    """Return the action scope explicitly declared by the task producer."""
    actions: list[str] = []
    for container in (payload, payload.get("envelope")):
        if not isinstance(container, Mapping):
            continue
        explicit = container.get("requested_actions")
        if isinstance(explicit, str) and explicit.strip():
            actions.append(explicit.strip())
        elif isinstance(explicit, list):
            actions.extend(str(item).strip() for item in explicit if str(item).strip())
    return list(dict.fromkeys(actions))


def payload_requested_actions(payload: Mapping[str, Any], request_text: str) -> list[str]:
    """Union declared scope with conservative prose projections.

    The projection can only narrow a declaration; it cannot replace the typed
    ``requested_actions`` field for lease-required work.
    """
    actions = payload_declared_actions(payload)

    lowered = request_text.lower()
    projections = (
        (r"\b(write|edit|modify|patch|apply|create|update)\b", "write_artifact"),
        (r"\b(commit|push|merge)\b", "git_push"),
        (r"\b(start|restart|tmux|daemon|service|launchd)\b", WAKE_LOOP_START_ACTION),
        (r"\b(close|complete)\b", "close_task"),
        (r"\b(publish|reply)\b", "publish_domain_reply"),
        (r"\b(delete|remove)\b", "delete_artifact"),
        (r"\b(spend|purchase|pay)\b", "spend"),
        (r"\b(email|external contact|contact externally)\b", "external_contact"),
    )
    for pattern, action in projections:
        if re.search(pattern, lowered):
            actions.append(action)
    return list(dict.fromkeys(actions))


def payload_requested_paths(payload: Mapping[str, Any]) -> list[str]:
    """Extract only explicit target paths; never infer a path from prose."""
    paths: list[str] = []
    for container in (payload, payload.get("envelope")):
        if not isinstance(container, Mapping):
            continue
        for key in ("path", "target_path", "output_path", "workspace_path"):
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                paths.append(value.strip())
        explicit = container.get("requested_paths")
        if isinstance(explicit, str) and explicit.strip():
            paths.append(explicit.strip())
        elif isinstance(explicit, list):
            paths.extend(str(item).strip() for item in explicit if str(item).strip())
    return list(dict.fromkeys(paths))


def payload_execution_lease_status(
    payload: Mapping[str, Any],
    *,
    agent_uid: str = "",
    task_id: str = "",
    lease_root: Path | None = None,
    requested_actions: Sequence[str] = (),
    requested_paths: Sequence[str | Path] = (),
) -> dict[str, Any]:
    lease = payload.get("execution_lease") or payload.get("lease")
    loaded_from = "embedded"
    matched_by = ""
    if not isinstance(lease, dict):
        lease_id = str(
            payload_field(payload, "execution_lease_id", "lease_id")
            or (lease if isinstance(lease, str) else "")
            or ""
        ).strip()
        if not lease_id:
            correlation_id = payload_correlation_id(payload)
            if lease_root is not None:
                match = find_execution_lease_for_task(
                    lease_root,
                    agent_uid=agent_uid,
                    task_id=task_id,
                    correlation_id=correlation_id,
                )
                if match is not None:
                    path, lease, _ = match
                    loaded_from = str(path)
                    matched_by = "task_or_correlation_id"
            if not isinstance(lease, dict):
                return {
                    "present": False,
                    "valid": False,
                    "errors": ["missing execution lease"],
                    "warnings": [],
                    "task_id": task_id,
                    "correlation_id": correlation_id,
                    "requested_actions": list(requested_actions),
                    "requested_paths": [str(path) for path in requested_paths],
                }
        else:
            if lease_root is None:
                return {
                    "present": True,
                    "valid": False,
                    "lease_id": lease_id,
                    "errors": ["lease_id present but no lease_root was available"],
                    "warnings": [],
                }
            try:
                lease = load_execution_lease(lease_root, lease_id)
                loaded_from = str(lease_root)
            except (ExecutionLeaseError, OSError, json.JSONDecodeError) as exc:
                return {
                    "present": True,
                    "valid": False,
                    "lease_id": lease_id,
                    "errors": [f"lease load failed: {type(exc).__name__}: {exc}"],
                    "warnings": [],
                }

    revoked = load_revoked_lease_ids(lease_root) if lease_root is not None else set()
    validation = validate_execution_lease(
        lease,
        agent_uid=agent_uid,
        task_id=task_id,
        requested_actions=requested_actions,
        requested_paths=requested_paths,
        revoked_lease_ids=revoked,
    )
    return {
        "present": True,
        "valid": validation.valid,
        "lease_id": validation.lease_id,
        "errors": list(validation.errors),
        "warnings": list(validation.warnings),
        "loaded_from": loaded_from,
        "matched_by": matched_by,
        "requested_actions": list(requested_actions),
        "requested_paths": [str(path) for path in requested_paths],
    }


def payload_has_execution_lease(
    payload: Mapping[str, Any],
    *,
    agent_uid: str = "",
    task_id: str = "",
    lease_root: Path | None = None,
) -> bool:
    return bool(
        payload_execution_lease_status(
            payload,
            agent_uid=agent_uid,
            task_id=task_id,
            lease_root=lease_root,
        )["valid"]
    )


def classify_record(
    record: Mapping[str, Any],
    original_payload: Any | None = None,
    *,
    agent_uid: str = "",
    lease_root: Path | None = None,
) -> dict[str, Any]:
    payload = original_payload if isinstance(original_payload, dict) else {}
    summary = str(record.get("summary") or "")
    text = payload_request_text(payload, summary)
    envelope = payload.get("envelope") if isinstance(payload.get("envelope"), Mapping) else {}
    explicit_requires = bool(
        payload.get("requires_execution_lease")
        or payload.get("requires_approval")
        or envelope.get("requires_execution_lease")
        or envelope.get("requires_approval")
    )
    task_id = payload_task_id(payload, record)
    declared_actions = payload_declared_actions(payload)
    requested_actions = payload_requested_actions(payload, text)
    requested_paths = payload_requested_paths(payload)
    lease_status = payload_execution_lease_status(
        payload,
        agent_uid=agent_uid,
        task_id=task_id,
        lease_root=lease_root,
        requested_actions=requested_actions,
        requested_paths=requested_paths,
    )
    scope_declaration_required = explicit_requires or text_requires_execution_lease(text)
    if scope_declaration_required and not declared_actions:
        lease_status = dict(lease_status)
        lease_status["valid"] = False
        lease_status["errors"] = list(lease_status.get("errors") or []) + [
            "lease-required payload must declare non-empty requested_actions"
        ]
    has_lease = bool(lease_status["valid"])
    requires_lease = scope_declaration_required and not has_lease
    contact_evidence = str(payload.get("contact_evidence") or payload.get("ack_tier") or payload.get("evidence_tier") or "")
    publish_only = contact_evidence.upper() in {"PUBLISH_ACCEPTED", "NATS_CLI_JETSTREAM_PUB_ACK", "CORE_FLUSH_ONLY"}
    blocked = requires_lease or str(record.get("status") or "").lower() == "blocked"
    return {
        "trigger_id": record["trigger_id"],
        "kind": record["kind"],
        "source_path": record["source_path"],
        "summary": record["summary"],
        "requires_execution_lease": requires_lease,
        "has_execution_lease": has_lease,
        "execution_lease": lease_status,
        "declared_actions": declared_actions,
        "requested_actions": requested_actions,
        "requested_paths": requested_paths,
        "blocked": blocked,
        "block_reason": "execution_lease_required" if requires_lease else ("status_blocked" if blocked else ""),
        "publish_acceptance_only": publish_only,
        "live_collaboration_claim": False if publish_only else bool(payload.get("semantic_reply_claim") or payload.get("domain_receipt_claim")),
    }


def load_original_payload_for_record(record: Mapping[str, Any]) -> Any:
    path = Path(str(record.get("source_path") or ""))
    expected_digest = str(record.get("payload_sha256") or "")
    if record.get("kind") == "task" and path.exists():
        for row in read_jsonl(path):
            if payload_digest(row) == expected_digest:
                return row
        return {}
    if path.suffix.lower() == ".json":
        return read_json(path, {})
    if path.exists():
        return {"body": path.read_text(encoding="utf-8", errors="replace"), "file_name": path.name}
    return {}


def classify_work(
    work: Mapping[str, Any],
    profile: WakeProfile | None = None,
    lease_root: Path | None = None,
) -> dict[str, Any]:
    profile = profile or WAKE_PROFILES[DEFAULT_AGENT_UID]
    observed = list(work.get("observed_messages") or [])
    classifications: list[dict[str, Any]] = []
    for record in observed:
        payload = load_original_payload_for_record(record)
        classifications.append(
            classify_record(
                record,
                payload,
                agent_uid=profile.agent_uid,
                lease_root=lease_root,
            )
        )

    requiring_lease = [item for item in classifications if item["requires_execution_lease"]]
    blocked = [item for item in classifications if item["blocked"]]
    accepted = [
        {
            **item,
            "claim_scope": "receipt_only_read_only_analysis",
            "queue_mutation_performed": False,
        }
        for item in classifications
        if item["kind"] == "task" and not item["requires_execution_lease"] and not item["blocked"]
    ]
    completed_read_only = [
        {
            "analysis_id": f"{profile.agent_uid}_orientation_and_assigned_surface_triage",
            "status": "completed",
            "observed_message_count": len(observed),
            "accepted_read_only_claim_count": len(accepted),
            "execution_lease_required_count": len(requiring_lease),
            "blocked_count": len(blocked),
        }
    ]
    return {
        "schema_version": f"{profile.schema_prefix}.work_classification.v1",
        "observed_messages": classifications,
        "accepted_task_claims": accepted,
        "work_requiring_execution_lease": requiring_lease,
        "blocked_work": blocked,
        "completed_read_only_analysis": completed_read_only,
        "publish_acceptance_guard": {
            "rule": "publish acceptance is not live collaboration without handler ack, domain receipt, or semantic reply evidence",
            "publish_only_count": sum(1 for item in classifications if item["publish_acceptance_only"]),
        },
    }


def nest_readme(profile: WakeProfile | None = None) -> str:
    profile = profile or WAKE_PROFILES[DEFAULT_AGENT_UID]
    uid = profile.agent_uid
    return f"""# {uid} Wake Nest

This is the durable local nest for the governed {uid} wake loop.

The nest stores receipts, heartbeat, status, and future orchestration slots. It
is not a new authority source. The canonical identity, card, passport, and A2A
state files remain the owners.

Default authority:

- read-only until an execution lease exists;
- no self-approval;
- no PR approval;
- no protected governance, kernel, telos, or DGM mutation;
- no secret values in artifacts.

Primary commands:

```bash
.venv/bin/python scripts/runtime/codex_composer_wake_loop.py --agent-uid {uid} once
.venv/bin/python scripts/runtime/codex_composer_wake_loop.py --agent-uid {uid} status
.venv/bin/python scripts/runtime/codex_composer_wake_loop.py --agent-uid {uid} start --activation-lease <operator-approved-id>
.venv/bin/python scripts/runtime/codex_composer_wake_loop.py --agent-uid {uid} stop
```

`once` is the safe default. `start` refuses to launch a repeated loop unless an
activation lease is supplied.
"""


def commands_doc(profile: WakeProfile | None = None) -> str:
    profile = profile or WAKE_PROFILES[DEFAULT_AGENT_UID]
    uid = profile.agent_uid
    base = f".venv/bin/python scripts/runtime/codex_composer_wake_loop.py --agent-uid {uid}"
    return f"""# {uid} Wake Commands

```bash
{base} once
{base} status
{base} start --activation-lease <operator-approved-id> --interval-s 900
{base} stop
```

The repeated loop is intentionally manual and lease-gated. Do not install cron,
launchd, or tmux always-on activation from this command surface without an
operator lease.
"""


def future_orchestration_manifest(paths: ComposerPaths) -> dict[str, Any]:
    return {
        "schema_version": f"{paths.profile.schema_prefix}.future_orchestration.v1",
        "agent_uid": paths.agent_uid,
        "generated_at": utc_now(),
        "living_dock_projection": str(paths.agent_home),
        "external_sandbox": str(paths.external_home),
        "durable_nest": str(paths.nest),
        "search_terms": [
            "Holocron",
            "Holocron Nest",
            "Aerie",
            "LandingDock",
            "FactoryDroid",
            "DroidFactory",
            paths.agent_uid,
        ],
        "current_findings": {
            "repo_terms": "Holocron, Aerie, LandingDock, and FactoryDroid are Semantic Commons names, not live orchestration authority.",
            f"{paths.agent_uid}_surfaces": "Existing identity, card, passport, external home, one-shot wake proof, and stale L4/tmux artifacts are present.",
        },
        "reserved_slots": {
            "holocron": str(paths.nest / "holocron"),
            "aerie": str(paths.nest / "aerie"),
            "landing_dock": str(paths.nest / "landing_dock"),
            "droid_factory": str(paths.nest / "droid_factory"),
        },
        "load_policy": {
            "status": "reserved_not_loaded",
            "requires_operator_execution_lease": True,
            "may_not_load_from_chat_memory": True,
            "must_record_receipt_before_use": True,
        },
    }


def build_status(paths: ComposerPaths) -> dict[str, Any]:
    latest = read_json(paths.latest_receipt, None)
    return {
        "schema_version": f"{paths.profile.schema_prefix}.wake_status.v1",
        "generated_at": utc_now(),
        "agent_uid": paths.agent_uid,
        "authority_mode": AUTHORITY_MODE,
        "repo_root": str(paths.repo_root),
        "nest": str(paths.nest),
        "wake_loop_active": False,
        "wake_loop_active_reason": "manual mode only unless start records a lease-backed running supervisor",
        "heartbeat": read_json(paths.heartbeat, None),
        "latest_receipt": latest,
        "wake_receipts_count": count_lines(paths.wake_receipts),
        "action_log_count": count_lines(paths.action_log),
        "latest_wake_log": last_jsonl(paths.wake_receipts),
        "future_orchestration": read_json(paths.future_orchestration, None),
        "forbidden": [
            "self_approve_execution_lease",
            "approve_prs",
            "mutate_protected_governance_kernel_telos_dgm",
            "store_secret_values_in_artifacts",
            "treat_publish_accepted_as_live_collaboration",
        ],
    }


def bootstrap_nest(paths: ComposerPaths) -> dict[str, Any]:
    reserved_slots = (
        paths.nest / "holocron",
        paths.nest / "aerie",
        paths.nest / "landing_dock",
        paths.nest / "droid_factory",
    )
    for directory in (paths.external_home, paths.nest, paths.logs, paths.receipts, paths.actions, *reserved_slots):
        directory.mkdir(parents=True, exist_ok=True)
    paths.wake_receipts.touch(exist_ok=True)
    paths.action_log.touch(exist_ok=True)
    write_text(paths.nest / "README.md", nest_readme(paths.profile))
    write_text(paths.nest / "COMMANDS.md", commands_doc(paths.profile))
    write_json(paths.future_orchestration, future_orchestration_manifest(paths))
    status = build_status(paths)
    write_json(paths.status, status)
    return status


def record_action(paths: ComposerPaths, action: str, summary: str, *, outputs: Mapping[str, Any] | None = None, status: str = "ok") -> None:
    append_jsonl(
        paths.action_log,
        {
            "schema_version": "dharma_external_agent_action_log.v1",
            "event_id": f"{action}:{paths.agent_uid}:{stamp()}",
            "timestamp": utc_now(),
            "agent_uid": paths.agent_uid,
            "callsign": paths.profile.callsign,
            "display_name": paths.profile.display_name,
            "authority": AUTHORITY_MODE,
            "action": action,
            "summary": summary,
            "outputs": dict(outputs or {}),
            "status": status,
        },
    )


def write_cycle_artifacts(paths: ComposerPaths, receipt: Mapping[str, Any]) -> None:
    receipt_id = str(receipt["receipt_id"])
    receipt_path = paths.receipts / f"{receipt_id}.json"
    write_json(receipt_path, receipt)
    write_json(paths.latest_receipt, {**receipt, "receipt_path": str(receipt_path)})
    heartbeat = {
        "schema_version": f"{paths.profile.schema_prefix}.wake_heartbeat.v1",
        "agent_uid": paths.agent_uid,
        "updated_at": receipt["completed_at"],
        "status": receipt["status"],
        "receipt_id": receipt_id,
        "receipt_path": str(receipt_path),
        "observed_message_count": len(receipt["work"]["observed_messages"]),
        "execution_lease_required_count": len(receipt["work"]["work_requiring_execution_lease"]),
        "wake_loop_active": False,
    }
    write_json(paths.heartbeat, heartbeat)
    append_jsonl(paths.wake_receipts, {**receipt, "receipt_path": str(receipt_path)})
    write_json(paths.status, build_status(paths))


def run_once(
    paths: ComposerPaths,
    *,
    runner: Runner = default_runner,
    orientation_timeout_s: float = 30.0,
    skip_orientation_command: bool = False,
    mode: str = "manual_once",
) -> dict[str, Any]:
    started = utc_now()
    bootstrap_nest(paths)
    context = rehydrate_context(paths)
    orientation = run_orientation_cycle(
        paths,
        runner=runner,
        timeout_s=orientation_timeout_s,
        skip_orientation_command=skip_orientation_command,
    )
    assigned = collect_assigned_work(paths, context)
    work = classify_work(assigned, paths.profile, paths.leases)
    status = "completed_read_only_analysis"
    if context["missing"]:
        status = "completed_with_missing_context"
    if orientation["errors"]:
        status = "completed_with_orientation_warnings"
    if work["work_requiring_execution_lease"]:
        status = "blocked_execution_lease_required"
    receipt = {
        "schema_version": f"{paths.profile.schema_prefix}.wake_receipt.v1",
        "receipt_id": f"{_slug(paths.agent_uid)}-wake-{stamp()}-{hashlib.sha256(started.encode()).hexdigest()[:8]}",
        "started_at": started,
        "completed_at": utc_now(),
        "agent_uid": paths.agent_uid,
        "callsign": paths.profile.callsign,
        "display_name": paths.profile.display_name,
        "authority_mode": AUTHORITY_MODE,
        "mode": mode,
        "status": status,
        "context": context,
        "orientation": orientation,
        "assigned_surfaces": assigned["checked_surfaces"],
        "work": work,
        "safety": {
            "repo_write_performed": False,
            "source_mutation_performed": False,
            "git_mutation_performed": False,
            "external_message_sent": False,
            "execution_lease_self_approved": False,
            "secrets_copied": False,
            "publish_acceptance_live_collaboration_claim": False,
        },
        "next_activation_gate": "operator_execution_lease_required_for_repeated_start_or_write_capable_work",
    }
    write_cycle_artifacts(paths, receipt)
    record_action(
        paths,
        "wake_once",
        f"Ran one governed {paths.agent_uid} read-only wake cycle.",
        outputs={"receipt_id": receipt["receipt_id"], "status": status},
        status="ok" if not status.startswith("blocked") else "blocked",
    )
    return receipt


def render_status_markdown(status: Mapping[str, Any]) -> str:
    latest = status.get("latest_receipt") or {}
    heartbeat = status.get("heartbeat") or {}
    agent_uid = status.get("agent_uid", DEFAULT_AGENT_UID)
    return "\n".join(
        [
            f"# {agent_uid} Wake Status",
            "",
            f"- Generated: `{status['generated_at']}`",
            f"- Agent: `{status['agent_uid']}`",
            f"- Authority: `{status['authority_mode']}`",
            f"- Nest: `{status['nest']}`",
            f"- Wake loop active: `{status['wake_loop_active']}`",
            f"- Active reason: `{status['wake_loop_active_reason']}`",
            f"- Wake receipts: `{status['wake_receipts_count']}`",
            f"- Action log rows: `{status['action_log_count']}`",
            f"- Heartbeat status: `{heartbeat.get('status')}`",
            f"- Latest receipt: `{latest.get('receipt_id')}` status=`{latest.get('status')}`",
            "",
            "This surface does not grant write authority, PR approval, protected mutation, or live-collaboration claims from publish acceptance alone.",
            "",
        ]
    )


def loop_cycles(args: argparse.Namespace, paths: ComposerPaths) -> int:
    cycles = 0
    while True:
        lease_status = activation_lease_status(args.activation_lease, paths)
        if not lease_status["valid"]:
            result = {
                "ok": False,
                "status": "blocked_activation_lease_invalid",
                "agent_uid": paths.agent_uid,
                "activation_lease_validation": lease_status,
                "wake_loop_active": False,
                "cycles_completed": cycles,
            }
            record_action(
                paths,
                "loop_blocked",
                "Repeated wake loop halted because its activation lease is no longer valid.",
                outputs=result,
                status="blocked",
            )
            write_json(
                paths.status,
                {**build_status(paths), "last_loop_block": result, "wake_loop_active": False},
            )
            return 2
        run_once(
            paths,
            orientation_timeout_s=args.orientation_timeout_s,
            skip_orientation_command=args.skip_orientation_command,
            mode="lease_backed_loop",
        )
        cycles += 1
        if args.max_cycles and cycles >= args.max_cycles:
            return 0
        time.sleep(max(5.0, args.interval_s))


def build_loop_command(args: argparse.Namespace, paths: ComposerPaths) -> list[str]:
    command = [
        sys.executable,
        str(paths.repo_root / "scripts" / "runtime" / "codex_composer_wake_loop.py"),
        "--dharma-home",
        str(paths.dharma_home),
        "--repo-root",
        str(paths.repo_root),
        "--agent-uid",
        paths.agent_uid,
        "loop",
        "--activation-lease",
        str(args.activation_lease),
        "--interval-s",
        str(args.interval_s),
        "--orientation-timeout-s",
        str(args.orientation_timeout_s),
    ]
    if args.max_cycles:
        command.extend(["--max-cycles", str(args.max_cycles)])
    if args.skip_orientation_command:
        command.append("--skip-orientation-command")
    return command


def activation_lease_status(lease_id: str, paths: ComposerPaths) -> dict[str, Any]:
    """Load and strictly scope the local v1 lease used to start a wake loop.

    This closes the previous ``non-empty string == authority`` gap.  The v1
    checksum is still only local integrity evidence, not an operator signature;
    that assurance limit is explicit in every result.
    """
    requested_task = f"wake-loop-start:{paths.agent_uid}"
    assurance = "local_scoped_checksum_not_operator_signature"
    if not str(lease_id or "").strip():
        return {
            "valid": False,
            "lease_id": "",
            "errors": ["missing activation lease id"],
            "warnings": ["execution lease v1 is not cryptographically signed"],
            "requested_action": WAKE_LOOP_START_ACTION,
            "requested_task": requested_task,
            "authority_assurance": assurance,
        }
    try:
        lease = load_execution_lease(paths.leases, str(lease_id).strip())
    except (ExecutionLeaseError, OSError, json.JSONDecodeError) as exc:
        return {
            "valid": False,
            "lease_id": str(lease_id).strip(),
            "errors": [f"lease load failed: {type(exc).__name__}: {exc}"],
            "warnings": ["execution lease v1 is not cryptographically signed"],
            "requested_action": WAKE_LOOP_START_ACTION,
            "requested_task": requested_task,
            "authority_assurance": assurance,
        }

    validation = validate_execution_lease(
        lease,
        agent_uid=paths.agent_uid,
        task_id=requested_task,
        requested_actions=[WAKE_LOOP_START_ACTION],
        revoked_lease_ids=load_revoked_lease_ids(paths.leases),
    )
    errors = list(validation.errors)
    if str(lease.get("task_id") or "") != requested_task:
        errors.append(f"lease task_id must be exactly {requested_task!r}")
    if str(lease.get("issuer") or "") != "operator":
        errors.append("activation lease issuer must be 'operator'")
    return {
        "valid": not errors,
        "lease_id": validation.lease_id or str(lease_id).strip(),
        "errors": errors,
        "warnings": list(validation.warnings)
        + ["execution lease v1 is not cryptographically signed"],
        "requested_action": WAKE_LOOP_START_ACTION,
        "requested_task": requested_task,
        "authority_assurance": assurance,
    }


def start_loop(args: argparse.Namespace, paths: ComposerPaths) -> dict[str, Any]:
    bootstrap_nest(paths)
    lease_status = activation_lease_status(args.activation_lease, paths)
    if not lease_status["valid"]:
        missing = not str(args.activation_lease or "").strip()
        result = {
            "ok": False,
            "status": (
                "blocked_activation_lease_required"
                if missing
                else "blocked_activation_lease_invalid"
            ),
            "agent_uid": paths.agent_uid,
            "message": "start refused: a valid, scoped activation lease is required",
            "activation_lease_validation": lease_status,
            "wake_loop_active": False,
        }
        record_action(paths, "start_blocked", result["message"], outputs=result, status="blocked")
        write_json(paths.status, {**build_status(paths), "last_start": result})
        return result

    tmux = shutil.which("tmux")
    command = build_loop_command(args, paths)
    command_text = " ".join(shlex.quote(part) for part in command)
    if not tmux:
        result = {"ok": False, "status": "blocked_tmux_missing", "command": command_text, "wake_loop_active": False}
        record_action(paths, "start_blocked", "tmux not found.", outputs=result, status="blocked")
        write_json(paths.status, {**build_status(paths), "last_start": result})
        return result

    session = _session_for(args, paths)
    has_session = subprocess.run([tmux, "has-session", "-t", session], capture_output=True, text=True, check=False)
    if has_session.returncode != 0:
        created = subprocess.run([tmux, "new-session", "-d", "-s", session, "-n", "wake", "-c", str(paths.repo_root)], capture_output=True, text=True, check=False)
        if created.returncode != 0:
            result = {"ok": False, "status": "blocked_tmux_create_failed", "stderr": created.stderr, "stdout": created.stdout}
            record_action(paths, "start_blocked", "tmux session create failed.", outputs=result, status="blocked")
            write_json(paths.status, {**build_status(paths), "last_start": result})
            return result
    sent = subprocess.run([tmux, "send-keys", "-t", f"{session}:wake", command_text, "C-m"], capture_output=True, text=True, check=False)
    result = {
        "ok": sent.returncode == 0,
        "status": "started" if sent.returncode == 0 else "blocked_tmux_send_failed",
        "session": session,
        "command": command_text,
        "activation_lease": args.activation_lease,
        "activation_lease_validation": lease_status,
        "wake_loop_active": sent.returncode == 0,
        "stdout": sent.stdout,
        "stderr": sent.stderr,
    }
    record_action(paths, "start", f"Started lease-backed {paths.agent_uid} wake loop in tmux.", outputs=result, status="ok" if result["ok"] else "blocked")
    write_json(paths.status, {**build_status(paths), "last_start": result, "wake_loop_active": bool(result["ok"])})
    return result


def stop_loop(session: str, paths: ComposerPaths) -> dict[str, Any]:
    bootstrap_nest(paths)
    tmux = shutil.which("tmux")
    if not tmux:
        result = {"ok": True, "status": "not_running_tmux_missing", "session": session, "wake_loop_active": False}
    else:
        has_session = subprocess.run([tmux, "has-session", "-t", session], capture_output=True, text=True, check=False)
        if has_session.returncode != 0:
            result = {"ok": True, "status": "not_running", "session": session, "wake_loop_active": False}
        else:
            stopped = subprocess.run([tmux, "send-keys", "-t", f"{session}:wake", "C-c"], capture_output=True, text=True, check=False)
            result = {
                "ok": stopped.returncode == 0,
                "status": "stop_signal_sent" if stopped.returncode == 0 else "stop_signal_failed",
                "session": session,
                "wake_loop_active": False,
                "stdout": stopped.stdout,
                "stderr": stopped.stderr,
            }
    record_action(paths, "stop", f"Stopped or confirmed absent {paths.agent_uid} wake loop.", outputs=result, status="ok" if result["ok"] else "blocked")
    write_json(paths.status, {**build_status(paths), "last_stop": result, "wake_loop_active": False})
    return result


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dharma-home", default=str(DEFAULT_DHARMA_HOME))
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument(
        "--agent-uid",
        default=DEFAULT_AGENT_UID,
        help="admitted seat to wake (default: codex_composer)",
    )
    parser.add_argument(
        "--session",
        default="",
        help="tmux session for the lease-backed loop (default: derived from the seat profile)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap = sub.add_parser("bootstrap", help="Create/update the codex_composer wake nest")
    bootstrap.set_defaults(func=cmd_bootstrap)

    once = sub.add_parser("once", help="Run one governed read-only wake cycle")
    once.add_argument("--orientation-timeout-s", type=float, default=30.0)
    once.add_argument("--skip-orientation-command", action="store_true")
    once.set_defaults(func=cmd_once)

    status = sub.add_parser("status", help="Render current wake-loop status")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    loop = sub.add_parser("loop", help="Run repeated wake cycles with a scoped activation lease")
    loop.add_argument("--activation-lease", required=True)
    loop.add_argument("--interval-s", type=float, default=DEFAULT_INTERVAL_S)
    loop.add_argument("--max-cycles", type=int, default=0)
    loop.add_argument("--orientation-timeout-s", type=float, default=30.0)
    loop.add_argument("--skip-orientation-command", action="store_true")
    loop.set_defaults(func=cmd_loop)

    start = sub.add_parser("start", help="Start repeated wake loop only with an activation lease")
    start.add_argument("--activation-lease", default="")
    start.add_argument("--interval-s", type=float, default=DEFAULT_INTERVAL_S)
    start.add_argument("--max-cycles", type=int, default=0)
    start.add_argument("--orientation-timeout-s", type=float, default=30.0)
    start.add_argument("--skip-orientation-command", action="store_true")
    start.set_defaults(func=cmd_start)

    stop = sub.add_parser("stop", help="Stop the lease-backed tmux loop if present")
    stop.set_defaults(func=cmd_stop)
    return parser


def _paths_from_args(args: argparse.Namespace) -> ComposerPaths:
    return composer_paths(
        args.dharma_home,
        repo_root=args.repo_root,
        agent_uid=getattr(args, "agent_uid", DEFAULT_AGENT_UID),
    )


def _session_for(args: argparse.Namespace, paths: ComposerPaths) -> str:
    session = (getattr(args, "session", "") or "").strip() or paths.profile.session
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", session):
        raise ValueError("tmux session must be a single safe token")
    return session


def cmd_bootstrap(args: argparse.Namespace) -> int:
    status = bootstrap_nest(_paths_from_args(args))
    print(json.dumps(status, indent=2, sort_keys=True, default=_json_default))
    return 0


def cmd_once(args: argparse.Namespace) -> int:
    receipt = run_once(
        _paths_from_args(args),
        orientation_timeout_s=args.orientation_timeout_s,
        skip_orientation_command=args.skip_orientation_command,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True, default=_json_default))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    paths = _paths_from_args(args)
    bootstrap_nest(paths)
    status = build_status(paths)
    write_json(paths.status, status)
    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True, default=_json_default))
    else:
        print(render_status_markdown(status))
    return 0


def cmd_loop(args: argparse.Namespace) -> int:
    paths = _paths_from_args(args)
    lease_status = activation_lease_status(args.activation_lease, paths)
    if not lease_status["valid"]:
        result = {
            "ok": False,
            "status": "blocked_activation_lease_invalid",
            "agent_uid": paths.agent_uid,
            "activation_lease_validation": lease_status,
            "wake_loop_active": False,
        }
        record_action(
            paths,
            "loop_blocked",
            "Repeated wake loop refused an invalid activation lease.",
            outputs=result,
            status="blocked",
        )
        print(json.dumps(result, indent=2, sort_keys=True, default=_json_default))
        return 2
    return loop_cycles(args, paths)


def cmd_start(args: argparse.Namespace) -> int:
    result = start_loop(args, _paths_from_args(args))
    print(json.dumps(result, indent=2, sort_keys=True, default=_json_default))
    return 0 if result.get("ok") else 2


def cmd_stop(args: argparse.Namespace) -> int:
    paths = _paths_from_args(args)
    result = stop_loop(_session_for(args, paths), paths)
    print(json.dumps(result, indent=2, sort_keys=True, default=_json_default))
    return 0 if result.get("ok") else 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
