"""Git-friendly roaming mailbox for cross-harness agent task exchange.

The mailbox is intentionally simple:

- tasks live as one JSON file each under ``roaming_mailbox/tasks/``
- responses live as one JSON file each under ``roaming_mailbox/responses/``

Because the mailbox is plain files, it can be synced through git between a
local dharma_swarm checkout and a remote OpenClaw/Claude/Codex checkout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

# Task ids are single path components — no separators, no leading dot. This
# confines every id-derived path to its directory: a dependency such as
# "../responses/<id>.worker" must never resolve outside tasks/ and satisfy
# the ready gate via a response record (Greptile + Codex reviews on
# PR #1159).
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _validated_task_id(task_id: str) -> str:
    if not _TASK_ID_RE.fullmatch(task_id or ""):
        raise ValueError(f"invalid task id: {task_id!r}")
    return task_id


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=True, default=str) + "\n"


def _default_queue_root() -> Path:
    return Path(__file__).resolve().parent.parent / "roaming_mailbox"


@dataclass(frozen=True)
class MailboxTask:
    task_id: str
    recipient: str
    sender: str
    summary: str
    body: str
    status: str = "queued"
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)
    claimed_at: str = ""
    claimed_by: str = ""
    responded_at: str = ""
    response_ref: str = ""
    # Task-medium join (ADR-010,
    # docs/architecture/ADRs/ADR-010-beads-fence-task-medium-join.md):
    # dependency edges by task_id, with ready-set semantics mirroring
    # task_board.py — a task is claimable only when every dependency has
    # status "responded". Unknown/malformed dependency ids fail closed.
    # Dependent tasks are written with status "blocked" so legacy pollers
    # that ignore this field can never claim them early.
    depends_on: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MailboxTask:
        return cls(
            task_id=str(data.get("task_id", "")),
            recipient=str(data.get("recipient", "")),
            sender=str(data.get("sender", "")),
            summary=str(data.get("summary", "")),
            body=str(data.get("body", "")),
            status=str(data.get("status", "queued")),
            capabilities=list(data.get("capabilities") or []),
            metadata=dict(data.get("metadata") or {}),
            created_at=str(data.get("created_at", "")) or _utc_now_iso(),
            claimed_at=str(data.get("claimed_at", "")),
            claimed_by=str(data.get("claimed_by", "")),
            responded_at=str(data.get("responded_at", "")),
            response_ref=str(data.get("response_ref", "")),
            depends_on=[str(dep) for dep in (data.get("depends_on") or [])],
        )


@dataclass(frozen=True)
class MailboxResponse:
    task_id: str
    responder: str
    summary: str
    body: str
    status: str = "responded"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RoamingMailbox:
    def __init__(self, queue_root: Path | None = None) -> None:
        self.queue_root = queue_root or _default_queue_root()
        self.tasks_dir = self.queue_root / "tasks"
        self.responses_dir = self.queue_root / "responses"
        self.receipts_dir = self.queue_root / "receipts"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.responses_dir.mkdir(parents=True, exist_ok=True)
        self.receipts_dir.mkdir(parents=True, exist_ok=True)

    def task_path(self, task_id: str) -> Path:
        return self.tasks_dir / f"{_validated_task_id(task_id)}.json"

    def response_path(self, task_id: str, responder: str) -> Path:
        safe = responder.replace("/", "_").replace("\\", "_")
        return self.responses_dir / f"{task_id}.{safe}.json"

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_json_dump(payload), encoding="utf-8")

    def _read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _new_task_id(self) -> str:
        return f"mbx_{uuid4().hex[:16]}"

    def enqueue_task(
        self,
        *,
        recipient: str,
        sender: str,
        summary: str,
        body: str,
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        depends_on: list[str] | None = None,
    ) -> MailboxTask:
        deps = [str(dep) for dep in (depends_on or [])]
        task = MailboxTask(
            task_id=self._new_task_id(),
            recipient=recipient,
            sender=sender,
            summary=summary,
            body=body,
            # "blocked", not "queued": legacy pollers (older checkouts that
            # ignore depends_on) claim anything queued, so a dependent task
            # must be encoded in a status they will never claim (Codex
            # review on PR #1159). ready_tasks() unblocks it.
            status="blocked" if deps else "queued",
            capabilities=list(capabilities or []),
            metadata=dict(metadata or {}),
            depends_on=deps,
        )
        self._write_json(self.task_path(task.task_id), task.to_dict())
        return task

    def load_task(self, task_id: str) -> MailboxTask:
        return MailboxTask.from_dict(self._read_json(self.task_path(task_id)))

    def list_tasks(
        self,
        *,
        recipient: str | None = None,
        status: str | None = None,
    ) -> list[MailboxTask]:
        tasks: list[MailboxTask] = []
        for path in sorted(self.tasks_dir.glob("*.json")):
            task = MailboxTask.from_dict(self._read_json(path))
            if recipient is not None and task.recipient != recipient:
                continue
            if status is not None and task.status != status:
                continue
            tasks.append(task)
        tasks.sort(key=lambda task: task.created_at)
        return tasks

    def claim_task(self, task_id: str, *, claimed_by: str) -> MailboxTask:
        task = self.load_task(task_id)
        # Only queued/blocked records are claimable: claiming a responded
        # task would overwrite its terminal status (and un-satisfy every
        # dependent), and claiming a claimed task would steal an active
        # worker's claim (Greptile review on PR #1159).
        if task.status not in {"queued", "blocked"}:
            raise ValueError(
                f"task {task_id} is not claimable (status: {task.status})"
            )
        # Every claim path enforces the dependency contract — a direct
        # claim_task call must not bypass the ready gate (Codex review on
        # PR #1159).
        unsatisfied = [
            dep for dep in task.depends_on if not self._dependency_satisfied(dep)
        ]
        if unsatisfied:
            raise ValueError(
                f"task {task_id} has unsatisfied dependencies: {unsatisfied}"
            )
        # Atomic claim fence: load/check/write alone lets two same-checkout
        # pollers both pass the checks and both "win", last writer keeping
        # claimed_by (Greptile review on PR #1159). Exclusive creation of a
        # per-task receipt makes exactly one claimant succeed. NOTE: this
        # fences one filesystem only — cross-checkout git sync stays
        # eventually consistent (the receipt travels with the sync). If a
        # worker dies between fence and work, an operator deletes the
        # receipt to release the claim.
        fence = self.receipts_dir / f"{_validated_task_id(task_id)}.claim"
        try:
            fd = os.open(fence, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise ValueError(
                f"task {task_id} already claimed (fence {fence.name} exists)"
            ) from None
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(
                _json_dump(
                    {
                        "task_id": task_id,
                        "claimed_by": claimed_by,
                        "claimed_at": _utc_now_iso(),
                    }
                )
            )
        claimed = MailboxTask(
            **{
                **task.to_dict(),
                "status": "claimed",
                "claimed_by": claimed_by,
                "claimed_at": _utc_now_iso(),
            }
        )
        self._write_json(self.task_path(task_id), claimed.to_dict())
        return claimed

    def _dependency_satisfied(self, dep_id: str) -> bool:
        """A dependency is satisfied only by a terminal "responded" record.

        Unknown ids fail closed (mirrors task_board.py's ready query, where a
        dependency row must exist COMPLETED before the dependent is ready).
        Malformed ids (path separators, traversal) and records whose own
        task_id does not match the dependency id also fail closed.
        """
        try:
            path = self.task_path(dep_id)
        except ValueError:
            return False
        if not path.exists():
            return False
        try:
            dep = MailboxTask.from_dict(self._read_json(path))
        except (OSError, json.JSONDecodeError):
            return False
        return dep.task_id == dep_id and dep.status == "responded"

    def ready_tasks(self, *, recipient: str | None = None) -> list[MailboxTask]:
        """Claimable tasks, oldest first: queued or blocked records whose
        every dependency is responded ("blocked" is the on-disk encoding of
        a dependent task; see enqueue_task)."""
        return [
            task
            for task in self.list_tasks(recipient=recipient)
            if task.status in {"queued", "blocked"}
            and all(self._dependency_satisfied(dep) for dep in task.depends_on)
        ]

    def validate_dependencies(self) -> list[str]:
        """Diagnostics: unknown dependency ids and dependency cycles."""
        tasks = {task.task_id: task for task in self.list_tasks()}
        issues: list[str] = []
        for task in tasks.values():
            for dep in task.depends_on:
                if dep not in tasks:
                    issues.append(f"{task.task_id}: unknown dependency {dep}")
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {task_id: WHITE for task_id in tasks}

        def visit(task_id: str, trail: list[str]) -> None:
            color[task_id] = GRAY
            for dep in tasks[task_id].depends_on:
                if dep not in tasks:
                    continue
                if color[dep] == GRAY:
                    cycle = trail[trail.index(dep):] if dep in trail else trail
                    issues.append(
                        f"dependency cycle: {' -> '.join([*cycle, task_id, dep])}"
                    )
                elif color[dep] == WHITE:
                    visit(dep, [*trail, dep])
            color[task_id] = BLACK

        for task_id in tasks:
            if color[task_id] == WHITE:
                visit(task_id, [task_id])
        return issues

    def claim_next_task(self, recipient: str) -> MailboxTask | None:
        for candidate in self.ready_tasks(recipient=recipient):
            try:
                return self.claim_task(candidate.task_id, claimed_by=recipient)
            except ValueError:
                # Lost the claim race (or state moved under us) — the next
                # ready task is still fair game.
                continue
        return None

    def respond_to_task(
        self,
        *,
        task_id: str,
        responder: str,
        summary: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> MailboxResponse:
        response = MailboxResponse(
            task_id=task_id,
            responder=responder,
            summary=summary,
            body=body,
            metadata=dict(metadata or {}),
        )
        response_path = self.response_path(task_id, responder)
        self._write_json(response_path, response.to_dict())

        task = self.load_task(task_id)
        updated = MailboxTask(
            **{
                **task.to_dict(),
                "status": "responded",
                "responded_at": response.created_at,
                "response_ref": str(response_path),
            }
        )
        self._write_json(self.task_path(task_id), updated.to_dict())
        return response


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Git-friendly roaming mailbox")
    parser.add_argument("--queue-root", default="")
    sub = parser.add_subparsers(dest="command", required=True)

    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("--recipient", required=True)
    enqueue.add_argument("--sender", default="dharma_swarm")
    enqueue.add_argument("--summary", required=True)
    enqueue.add_argument("--body", required=True)
    enqueue.add_argument("--capability", action="append", default=[])
    enqueue.add_argument("--depends-on", action="append", default=[])

    claim = sub.add_parser("claim-next")
    claim.add_argument("--recipient", required=True)

    ready = sub.add_parser("ready")
    ready.add_argument("--recipient", default="")

    sub.add_parser("validate")

    respond = sub.add_parser("respond")
    respond.add_argument("--task-id", required=True)
    respond.add_argument("--responder", required=True)
    respond.add_argument("--summary", required=True)
    respond.add_argument("--body", required=True)

    listing = sub.add_parser("list")
    listing.add_argument("--recipient", default="")
    listing.add_argument("--status", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    mailbox = RoamingMailbox(queue_root=Path(args.queue_root) if args.queue_root else None)

    if args.command == "enqueue":
        task = mailbox.enqueue_task(
            recipient=args.recipient,
            sender=args.sender,
            summary=args.summary,
            body=args.body,
            capabilities=list(args.capability or []),
            depends_on=list(args.depends_on or []),
        )
        print(_json_dump(task.to_dict()).rstrip())
        return 0

    if args.command == "ready":
        tasks = [
            task.to_dict()
            for task in mailbox.ready_tasks(recipient=args.recipient or None)
        ]
        print(_json_dump(tasks).rstrip())
        return 0

    if args.command == "validate":
        issues = mailbox.validate_dependencies()
        print(_json_dump(issues).rstrip())
        return 0 if not issues else 1

    if args.command == "claim-next":
        task = mailbox.claim_next_task(args.recipient)
        print(_json_dump(task.to_dict() if task else {}).rstrip())
        return 0

    if args.command == "respond":
        response = mailbox.respond_to_task(
            task_id=args.task_id,
            responder=args.responder,
            summary=args.summary,
            body=args.body,
        )
        print(_json_dump(response.to_dict()).rstrip())
        return 0

    if args.command == "list":
        tasks = [
            task.to_dict()
            for task in mailbox.list_tasks(
                recipient=args.recipient or None,
                status=args.status or None,
            )
        ]
        print(_json_dump(tasks).rstrip())
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
