"""File-backed live interop substrate for external agent tools."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dharma_swarm.a2a.agent_card import AgentCapability, AgentCard, CardRegistry
from dharma_swarm.roaming_mailbox import MailboxTask, RoamingMailbox

DEFAULT_INTEROP_ROOT = Path.home() / ".dharma" / "agent_interop"
DEFAULT_A2A_CARDS_DIR = Path.home() / ".dharma" / "a2a" / "cards"
DEFAULT_MAILBOX_ROOT = DEFAULT_INTEROP_ROOT / "mailbox"

DEFAULT_ADAPTERS: tuple[dict[str, Any], ...] = (
    {"adapter_id": "codex-cli", "label": "Codex 5.5", "role": "coder", "transport": "cli", "executable": "codex", "capabilities": ["code_generation", "code_review", "testing"]},
    {"adapter_id": "claude-code", "label": "Claude Code", "role": "coder", "transport": "cli", "executable": "claude", "capabilities": ["code_generation", "code_review", "architecture"]},
    {"adapter_id": "cursor", "label": "Cursor", "role": "editor", "transport": "handoff", "capabilities": ["code_navigation", "code_editing"]},
    {"adapter_id": "warp-oz", "label": "Warp/Oz", "role": "terminal", "transport": "handoff", "capabilities": ["terminal_operation", "debugging"]},
    {"adapter_id": "perplexity-computer", "label": "Perplexity Computer", "role": "researcher", "transport": "handoff", "capabilities": ["research", "web_synthesis"]},
    {"adapter_id": "kimi-claw-phone", "label": "Kimi Claw Phone", "role": "researcher", "transport": "handoff", "capabilities": ["mobile_research", "review"]},
    {"adapter_id": "hermes", "label": "Hermes", "role": "messenger", "transport": "handoff", "capabilities": ["coordination", "message_relay"]},
    {"adapter_id": "openclaw", "label": "OpenClaw", "role": "computer_use", "transport": "handoff", "capabilities": ["computer_use", "remote_operation"]},
    {"adapter_id": "opencalw", "label": "OpenCalw", "role": "computer_use", "transport": "handoff", "capabilities": ["computer_use", "remote_operation"]},
    {"adapter_id": "claude-flow", "label": "Claude Flow", "role": "orchestrator", "transport": "handoff", "capabilities": ["coordination", "multi_agent_planning"]},
    {"adapter_id": "dharma-swarm-mcp", "label": "Dharma Swarm MCP", "role": "adapter", "transport": "mcp", "capabilities": ["tool_calling", "context_projection"]},
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=True, default=str) + "\n"


def _env_path(name: str, fallback: Path) -> Path:
    value = os.getenv(name, "").strip()
    return Path(value).expanduser() if value else fallback


def _safe_name(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_").replace(":", "_") or "unknown"


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class AgentInteropStore:
    schema_version = "2026-05-03.interop.v1"

    def __init__(
        self,
        *,
        root: Path | None = None,
        cards_dir: Path | None = None,
        mailbox_root: Path | None = None,
    ) -> None:
        self.root = root or _env_path("DHARMA_INTEROP_ROOT", DEFAULT_INTEROP_ROOT)
        self.cards_dir = cards_dir or _env_path("DHARMA_A2A_CARDS_DIR", DEFAULT_A2A_CARDS_DIR)
        self.mailbox_root = mailbox_root or _env_path("DHARMA_ROAMING_MAILBOX_ROOT", DEFAULT_MAILBOX_ROOT)
        self.events_path = self.root / "events.jsonl"
        self.workers_dir = self.root / "workers"
        self.locks_dir = self.root / "locks"
        self.prompts_dir = self.root / "prompts"
        for path in (self.root, self.cards_dir, self.mailbox_root, self.workers_dir, self.locks_dir, self.prompts_dir):
            path.mkdir(parents=True, exist_ok=True)
        self.mailbox = RoamingMailbox(queue_root=self.mailbox_root)

    def _registry(self) -> CardRegistry:
        registry = CardRegistry(cards_dir=self.cards_dir)
        for adapter in DEFAULT_ADAPTERS:
            if registry.get(str(adapter["adapter_id"])) is None:
                registry.register(self._adapter_card(adapter))
        return registry

    def _adapter_card(self, adapter: dict[str, Any]) -> AgentCard:
        executable = str(adapter.get("executable") or "")
        command_available = bool(executable and shutil.which(executable))
        transport = str(adapter.get("transport") or "handoff")
        capabilities = [
            AgentCapability(str(name), f"{adapter['label']} capability: {name}")
            for name in adapter.get("capabilities", [])
        ]
        return AgentCard(
            name=str(adapter["adapter_id"]),
            description=f"{adapter['label']} interop adapter",
            capabilities=capabilities,
            endpoint=f"interop://{adapter['adapter_id']}",
            role=str(adapter.get("role") or "adapter"),
            status="idle" if command_available or transport != "cli" else "handoff",
            metadata={
                "label": adapter.get("label"),
                "transport": transport,
                "executable": executable,
                "command_available": command_available,
            },
        )

    def list_adapters(self) -> list[dict[str, Any]]:
        active = {worker["adapter_id"] for worker in self.list_workers() if worker.get("status") != "offline"}
        adapters = []
        for card in self._registry().list_all():
            metadata = dict(card.metadata or {})
            transport = str(metadata.get("transport") or metadata.get("kind") or "a2a")
            availability = metadata.get("availability") if isinstance(metadata.get("availability"), dict) else {}
            command = str(metadata.get("command") or metadata.get("executable") or "")
            command_available = bool(
                metadata.get("command_available")
                or availability.get("ready")
                or (command and shutil.which(command))
            )
            adapters.append(
                {
                    "adapter_id": card.name,
                    "label": str(metadata.get("label") or metadata.get("display_name") or card.name),
                    "description": card.description,
                    "role": card.role,
                    "status": card.status,
                    "transport": transport,
                    "ready": transport != "cli" or command_available or card.name in active,
                    "endpoint": card.endpoint,
                    "model": card.model,
                    "provider": card.provider,
                    "capabilities": card.capability_names(),
                    "metadata": metadata,
                }
            )
        return adapters

    def list_tasks(self, limit: int = 50) -> list[dict[str, Any]]:
        tasks = [task.to_dict() for task in self.mailbox.list_tasks()]
        tasks.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return tasks[: max(0, limit)]

    def enqueue_task(
        self,
        *,
        recipient: str,
        sender: str,
        summary: str,
        body: str,
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task = self.mailbox.enqueue_task(
            recipient=recipient,
            sender=sender,
            summary=summary,
            body=body,
            capabilities=capabilities,
            metadata=metadata,
        )
        payload = task.to_dict()
        self.append_event("task.queued", summary, payload)
        return payload

    def append_event(self, event_type: str, summary: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "event_id": f"evt_{int(_utc_now().timestamp() * 1000)}_{uuid4().hex[:8]}",
            "event_type": event_type,
            "summary": summary,
            "payload": dict(payload or {}),
            "created_at": _utc_now_iso(),
        }
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=True, default=str) + "\n")
        return event

    def list_events(self, after_event_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if self.events_path.exists():
            for line in self.events_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        if after_event_id:
            for index, event in enumerate(events):
                if event.get("event_id") == after_event_id:
                    events = events[index + 1 :]
                    break
        return events[-max(0, limit):] if limit > 0 else []

    def recent_events(self, limit: int = 40) -> list[dict[str, Any]]:
        return list(reversed(self.list_events(limit=limit)))

    def heartbeat_worker(
        self,
        *,
        worker_id: str,
        adapter_id: str,
        status: str,
        current_task_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        path = self.workers_dir / f"{_safe_name(worker_id)}.json"
        previous: dict[str, Any] = {}
        if path.exists():
            try:
                previous = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                previous = {}
        payload = {
            "worker_id": worker_id,
            "adapter_id": adapter_id,
            "status": status,
            "current_task_id": current_task_id,
            "last_heartbeat": _utc_now_iso(),
            "metadata": dict(metadata or {}),
        }
        path.write_text(_json_dump(payload), encoding="utf-8")
        previous_seen = _parse_iso(str(previous.get("last_heartbeat") or ""))
        if previous_seen is not None and previous_seen.tzinfo is None:
            previous_seen = previous_seen.replace(tzinfo=timezone.utc)
        heartbeat_due = previous_seen is None or (_utc_now() - previous_seen).total_seconds() >= 60
        changed = (
            previous.get("status") != status
            or previous.get("current_task_id") != current_task_id
            or previous.get("adapter_id") != adapter_id
        )
        if changed or heartbeat_due:
            self.append_event("worker.heartbeat", f"{worker_id} {status}", payload)
        return payload

    def list_workers(self) -> list[dict[str, Any]]:
        workers: list[dict[str, Any]] = []
        offline_cutoff = _utc_now() - timedelta(seconds=120)
        for path in sorted(self.workers_dir.glob("*.json")):
            try:
                worker = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            heartbeat = str(worker.get("last_heartbeat") or worker.get("last_seen") or "")
            if heartbeat and "last_heartbeat" not in worker:
                worker["last_heartbeat"] = heartbeat
            seen = _parse_iso(heartbeat)
            if seen is not None and seen.tzinfo is None:
                seen = seen.replace(tzinfo=timezone.utc)
            if seen is None or seen < offline_cutoff:
                worker = {**worker, "status": "offline"}
            workers.append(worker)
        workers.sort(key=lambda item: (str(item.get("adapter_id") or ""), str(item.get("worker_id") or "")))
        return workers

    def _lock_path(self, task_id: str) -> Path:
        return self.locks_dir / f"{_safe_name(task_id)}.lock"

    def _acquire_task_lock(self, task_id: str, worker_id: str) -> bool:
        path = self._lock_path(task_id)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(_json_dump({"task_id": task_id, "worker_id": worker_id, "created_at": _utc_now_iso()}))
        return True

    def _release_task_lock(self, task_id: str) -> None:
        self._lock_path(task_id).unlink(missing_ok=True)

    def requeue_stale_claims(self, lease_seconds: int = 900) -> int:
        cutoff = _utc_now() - timedelta(seconds=lease_seconds)
        requeued = 0
        for task in self.mailbox.list_tasks(status="claimed"):
            claimed_at = _parse_iso(task.claimed_at)
            if claimed_at is not None and claimed_at.tzinfo is None:
                claimed_at = claimed_at.replace(tzinfo=timezone.utc)
            if claimed_at is not None and claimed_at > cutoff:
                continue
            updated = MailboxTask(**{**task.to_dict(), "status": "queued", "claimed_at": "", "claimed_by": ""})
            self.mailbox._write_json(self.mailbox.task_path(task.task_id), updated.to_dict())
            self._release_task_lock(task.task_id)
            self.append_event("task.requeued", f"Lease expired for {task.summary}", updated.to_dict())
            requeued += 1
        return requeued

    def claim_next_task(self, *, recipient: str, worker_id: str, lease_seconds: int = 900) -> dict[str, Any] | None:
        self.requeue_stale_claims(lease_seconds=lease_seconds)
        for task in self.mailbox.list_tasks(recipient=recipient, status="queued"):
            if not self._acquire_task_lock(task.task_id, worker_id):
                continue
            claimed = self.mailbox.claim_task(task.task_id, claimed_by=worker_id)
            payload = claimed.to_dict()
            self.append_event("task.claimed", f"{worker_id} claimed {claimed.summary}", payload)
            return payload
        return None

    def respond_to_task(
        self,
        *,
        task_id: str,
        responder: str,
        summary: str,
        body: str,
        status: str = "responded",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self.mailbox.respond_to_task(
            task_id=task_id,
            responder=responder,
            summary=summary,
            body=body,
            status=status,
            metadata=metadata,
        )
        payload = response.to_dict()
        self._release_task_lock(task_id)
        self.append_event(f"task.{status}", summary, payload)
        return payload

    def build_status(self) -> dict[str, Any]:
        adapters = self.list_adapters()
        tasks = self.list_tasks(limit=100)
        counts: dict[str, int] = {}
        for task in tasks:
            status = str(task.get("status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
        workers = self.list_workers()
        active_workers = [worker for worker in workers if worker.get("status") != "offline"]
        return {
            "schema_version": self.schema_version,
            "root": str(self.root),
            "cards_dir": str(self.cards_dir),
            "mailbox_root": str(self.mailbox_root),
            "adapter_count": len(adapters),
            "ready_count": sum(1 for adapter in adapters if adapter.get("ready")),
            "worker_count": len(active_workers),
            "worker_total_count": len(workers),
            "mailbox_counts": counts,
            "adapters": adapters,
            "workers": workers,
            "recent_tasks": tasks[:25],
            "recent_events": self.recent_events(limit=40),
        }
