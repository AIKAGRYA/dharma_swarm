#!/usr/bin/env python3
"""Governed manual wake loop for codex_composer.

This is a repo-owned control shell for the existing codex_composer identity. It
does not grant source-write authority, approve work, install launchd/cron jobs,
or treat a broker publish as live collaboration. The default ``once`` command
rehydrates canonical context, runs a bounded read-only orientation pass, checks
assigned work surfaces, and writes heartbeat/status/receipt artifacts.
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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.model_hierarchy import default_model  # noqa: E402
from dharma_swarm.models import ProviderType  # noqa: E402

AGENT_UID = "codex_composer"
CALLSIGN = "codex_composer"
DISPLAY_NAME = "Codex Composer"
MODEL_IDENTITY = os.getenv("DGC_DIRECTOR_CODEX_MODEL", "").strip() or default_model(ProviderType.CODEX)
AUTHORITY_MODE = "read_only_until_execution_lease"
DEFAULT_DHARMA_HOME = Path("~/.dharma")
DEFAULT_SESSION = "codex-composer-wake"
DEFAULT_INTERVAL_S = 900.0

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

CANONICAL_CONTEXT = (
    ("holon_context", "agents/codex_composer/HOLON_CONTEXT.md"),
    ("identity", "agents/codex_composer/identity.json"),
    ("a2a_card", "a2a/cards/codex_composer.json"),
    ("agent_passport", "agent_passports/codex_composer.json"),
    ("external_registration", "external_agents/codex_composer/registration.json"),
    ("bridge_heartbeat", "a2a_bus/bridge_heartbeats/codex_composer.json"),
    ("a2a_state", "a2a_bus/state/codex_composer.json"),
    ("external_authority_passport", "external_agents/codex_composer/authority/passport.json"),
)


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
    future_orchestration: Path


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
) -> ComposerPaths:
    root = expand(dharma_home)
    external = root / "external_agents" / AGENT_UID
    nest = external / "nest"
    return ComposerPaths(
        dharma_home=root,
        repo_root=expand(repo_root),
        agent_home=root / "agents" / AGENT_UID,
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
        living_agent=root / "agents" / AGENT_UID / "living_agent.json",
        assigned_inbox=root / "a2a_bus" / "inboxes" / AGENT_UID,
        external_inbox=external / "inbox",
        task_queue=root / "a2a_bus" / "tasks" / "queue.jsonl",
        future_orchestration=nest / "future_orchestration.json",
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
    return {name: paths.dharma_home / relative for name, relative in CANONICAL_CONTEXT}


def rehydrate_context(paths: ComposerPaths) -> dict[str, Any]:
    files: dict[str, Any] = {}
    missing: list[str] = []
    authority_facts: dict[str, Any] = {
        "agent_uid": AGENT_UID,
        "default_authority": AUTHORITY_MODE,
        "no_self_approval": True,
        "no_pr_approval": True,
        "protected_mutation_allowed": False,
        "secrets_in_artifacts_allowed": False,
    }
    for name, path in canonical_context_paths(paths).items():
        entry: dict[str, Any] = {"path": str(path), "exists": path.exists()}
        if not path.exists():
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
        "schema_version": "dharma.codex_composer.rehydrated_context.v1",
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
        "schema_version": "dharma.codex_composer.orientation_cycle.v1",
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


def assigned_addresses(context: Mapping[str, Any]) -> set[str]:
    addresses = {AGENT_UID, "codex", "codex-composer", "codex_composer"}
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
    addresses = assigned_addresses(context)
    inbox = collect_inbox_messages(paths)
    tasks = collect_task_messages(paths, addresses)
    return {
        "schema_version": "dharma.codex_composer.assigned_work.v1",
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


def payload_has_execution_lease(payload: Mapping[str, Any]) -> bool:
    lease = payload.get("execution_lease") or payload.get("lease")
    return isinstance(lease, dict) and bool(lease.get("approved") or lease.get("operator_approved") or lease.get("lease_id"))


def classify_record(record: Mapping[str, Any], original_payload: Any | None = None) -> dict[str, Any]:
    payload = original_payload if isinstance(original_payload, dict) else {}
    summary = str(record.get("summary") or "")
    text = summary
    if payload:
        text += " " + json.dumps(payload, sort_keys=True, default=_json_default)
    explicit_requires = bool(payload.get("requires_execution_lease") or payload.get("requires_approval"))
    has_lease = payload_has_execution_lease(payload)
    requires_lease = (explicit_requires or text_requires_execution_lease(text)) and not has_lease
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


def classify_work(work: Mapping[str, Any]) -> dict[str, Any]:
    observed = list(work.get("observed_messages") or [])
    classifications: list[dict[str, Any]] = []
    for record in observed:
        payload = load_original_payload_for_record(record)
        classifications.append(classify_record(record, payload))

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
            "analysis_id": "codex_composer_orientation_and_assigned_surface_triage",
            "status": "completed",
            "observed_message_count": len(observed),
            "accepted_read_only_claim_count": len(accepted),
            "execution_lease_required_count": len(requiring_lease),
            "blocked_count": len(blocked),
        }
    ]
    return {
        "schema_version": "dharma.codex_composer.work_classification.v1",
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


def nest_readme() -> str:
    return """# codex_composer Wake Nest

This is the durable local nest for the governed codex_composer wake loop.

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
make codex-composer-once
make codex-composer-status
make codex-composer-start ARGS="--activation-lease <operator-approved-id>"
make codex-composer-stop
```

`once` is the safe default. `start` refuses to launch a repeated loop unless an
activation lease is supplied.
"""


def commands_doc() -> str:
    return """# codex_composer Wake Commands

```bash
make codex-composer-once
make codex-composer-status
make codex-composer-start ARGS="--activation-lease <operator-approved-id> --interval-s 900"
make codex-composer-stop
```

Equivalent direct commands:

```bash
.venv/bin/python scripts/runtime/codex_composer_wake_loop.py once
.venv/bin/python scripts/runtime/codex_composer_wake_loop.py status
.venv/bin/python scripts/runtime/codex_composer_wake_loop.py start --activation-lease <operator-approved-id>
.venv/bin/python scripts/runtime/codex_composer_wake_loop.py stop
```

The repeated loop is intentionally manual and lease-gated. Do not install cron,
launchd, or tmux always-on activation from this command surface without an
operator lease.
"""


def future_orchestration_manifest(paths: ComposerPaths) -> dict[str, Any]:
    return {
        "schema_version": "dharma.codex_composer.future_orchestration.v1",
        "agent_uid": AGENT_UID,
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
            "codex_composer",
        ],
        "current_findings": {
            "repo_terms": "Holocron, Aerie, LandingDock, and FactoryDroid are Semantic Commons names, not live orchestration authority.",
            "codex_composer_surfaces": "Existing identity, card, passport, external home, one-shot wake proof, and stale L4/tmux artifacts are present.",
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
        "schema_version": "dharma.codex_composer.wake_status.v1",
        "generated_at": utc_now(),
        "agent_uid": AGENT_UID,
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
    write_text(paths.nest / "README.md", nest_readme())
    write_text(paths.nest / "COMMANDS.md", commands_doc())
    write_json(paths.future_orchestration, future_orchestration_manifest(paths))
    status = build_status(paths)
    write_json(paths.status, status)
    return status


def record_action(paths: ComposerPaths, action: str, summary: str, *, outputs: Mapping[str, Any] | None = None, status: str = "ok") -> None:
    append_jsonl(
        paths.action_log,
        {
            "schema_version": "dharma_external_agent_action_log.v1",
            "event_id": f"{action}:{AGENT_UID}:{stamp()}",
            "timestamp": utc_now(),
            "agent_uid": AGENT_UID,
            "callsign": CALLSIGN,
            "display_name": DISPLAY_NAME,
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
        "schema_version": "dharma.codex_composer.wake_heartbeat.v1",
        "agent_uid": AGENT_UID,
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
    work = classify_work(assigned)
    status = "completed_read_only_analysis"
    if context["missing"]:
        status = "completed_with_missing_context"
    if orientation["errors"]:
        status = "completed_with_orientation_warnings"
    if work["work_requiring_execution_lease"]:
        status = "blocked_execution_lease_required"
    receipt = {
        "schema_version": "dharma.codex_composer.wake_receipt.v1",
        "receipt_id": f"codex-composer-wake-{stamp()}-{hashlib.sha256(started.encode()).hexdigest()[:8]}",
        "started_at": started,
        "completed_at": utc_now(),
        "agent_uid": AGENT_UID,
        "callsign": CALLSIGN,
        "display_name": DISPLAY_NAME,
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
        "Ran one governed codex_composer read-only wake cycle.",
        outputs={"receipt_id": receipt["receipt_id"], "status": status},
        status="ok" if not status.startswith("blocked") else "blocked",
    )
    return receipt


def render_status_markdown(status: Mapping[str, Any]) -> str:
    latest = status.get("latest_receipt") or {}
    heartbeat = status.get("heartbeat") or {}
    return "\n".join(
        [
            "# codex_composer Wake Status",
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
    latest: dict[str, Any] = {}
    while True:
        latest = run_once(
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
        "loop",
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


def start_loop(args: argparse.Namespace, paths: ComposerPaths) -> dict[str, Any]:
    bootstrap_nest(paths)
    if not args.activation_lease:
        result = {
            "ok": False,
            "status": "blocked_activation_lease_required",
            "agent_uid": AGENT_UID,
            "message": "start refused without --activation-lease",
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

    session = args.session
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
        "wake_loop_active": sent.returncode == 0,
        "stdout": sent.stdout,
        "stderr": sent.stderr,
    }
    record_action(paths, "start", "Started lease-backed codex_composer wake loop in tmux.", outputs=result, status="ok" if result["ok"] else "blocked")
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
    record_action(paths, "stop", "Stopped or confirmed absent codex_composer wake loop.", outputs=result, status="ok" if result["ok"] else "blocked")
    write_json(paths.status, {**build_status(paths), "last_stop": result, "wake_loop_active": False})
    return result


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dharma-home", default=str(DEFAULT_DHARMA_HOME))
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--session", default=DEFAULT_SESSION)


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

    loop = sub.add_parser("loop", help="Run repeated wake cycles. Use through start unless testing.")
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
    return composer_paths(args.dharma_home, repo_root=args.repo_root)


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
    return loop_cycles(args, _paths_from_args(args))


def cmd_start(args: argparse.Namespace) -> int:
    result = start_loop(args, _paths_from_args(args))
    print(json.dumps(result, indent=2, sort_keys=True, default=_json_default))
    return 0 if result.get("ok") else 2


def cmd_stop(args: argparse.Namespace) -> int:
    result = stop_loop(args.session, _paths_from_args(args))
    print(json.dumps(result, indent=2, sort_keys=True, default=_json_default))
    return 0 if result.get("ok") else 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
