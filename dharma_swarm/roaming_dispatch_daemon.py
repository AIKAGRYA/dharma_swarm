"""Local-side dispatcher/collector for roaming mailbox workers.

This is the bootstrap control loop for roaming agents:

1. optionally sync the mailbox repo from git
2. collect completed roaming responses back into OperatorBridge
3. dispatch new OperatorBridge work into the roaming mailbox
4. optionally push the updated mailbox state
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import time

from dharma_swarm.roaming_mailbox import RoamingMailbox
from dharma_swarm.roaming_operator_bridge import RoamingOperatorBridge, _build_bridge


@dataclass(frozen=True)
class DaemonCycleResult:
    collected_bridge_task_ids: list[str] = field(default_factory=list)
    dispatched_mailbox_task_ids: list[str] = field(default_factory=list)


class MailboxRepoSync:
    def __init__(self, repo_root: Path, branch: str) -> None:
        self.repo_root = repo_root
        self.branch = branch

    async def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        process = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(self.repo_root),
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(
                process.returncode or -1,
                ["git", "-C", str(self.repo_root), *args],
                output=stdout.decode(),
                stderr=stderr.decode(),
            )
        return subprocess.CompletedProcess(
            args=["git", "-C", str(self.repo_root), *args],
            returncode=process.returncode or 0,
            stdout=stdout.decode(),
            stderr=stderr.decode(),
        )

    async def sync_inbound(self) -> None:
        await self._run("fetch", "origin", self.branch)
        await self._run("checkout", self.branch)
        await self._run("pull", "--ff-only", "origin", self.branch)

    async def sync_outbound(self, *, note: str) -> None:
        result = await self._run(
            "status",
            "--short",
            "--",
            "roaming_mailbox/tasks",
            "roaming_mailbox/responses",
            "roaming_mailbox/receipts",
        )
        status = result.stdout.strip()
        if not status:
            return
        await self._run(
            "add",
            "roaming_mailbox/tasks",
            "roaming_mailbox/responses",
            "roaming_mailbox/receipts",
        )
        await self._run("commit", "-m", note)
        await self._run("push", "origin", f"HEAD:refs/heads/{self.branch}")


class RoamingDispatchDaemon:
    def __init__(
        self,
        *,
        adapter: RoamingOperatorBridge,
        recipient: str,
        responder: str,
        dispatch_limit: int = 1,
        git_sync: MailboxRepoSync | None = None,
    ) -> None:
        self.adapter = adapter
        self.recipient = recipient
        self.responder = responder
        self.dispatch_limit = max(1, int(dispatch_limit))
        self.git_sync = git_sync

    @property
    def mailbox(self) -> RoamingMailbox:
        return self.adapter.mailbox

    def _receipt_exists(self, mailbox_task_id: str) -> bool:
        return self.mailbox.receipts_dir.joinpath(
            f"{mailbox_task_id}.{self.responder.replace('/', '_').replace(chr(92), '_')}.imported.json"
        ).exists()

    async def collect_available(self) -> list[str]:
        collected: list[str] = []
        responded = self.mailbox.list_tasks(recipient=self.recipient, status="responded")
        for task in responded:
            if self._receipt_exists(task.task_id):
                continue
            updated = await self.adapter.collect_response(
                mailbox_task_id=task.task_id,
                responder=self.responder,
            )
            collected.append(updated.id)
        return collected

    async def dispatch_available(self) -> list[str]:
        dispatched: list[str] = []
        for _ in range(self.dispatch_limit):
            task = await self.adapter.dispatch_next(recipient=self.recipient)
            if task is None:
                break
            dispatched.append(task.task_id)
        return dispatched

    async def cycle_once(self) -> DaemonCycleResult:
        if self.git_sync is not None:
            await self.git_sync.sync_inbound()

        collected = await self.collect_available()
        dispatched = await self.dispatch_available()

        if self.git_sync is not None and (collected or dispatched):
            parts: list[str] = []
            if collected:
                parts.append(f"collect {len(collected)}")
            if dispatched:
                parts.append(f"dispatch {len(dispatched)}")
            await self.git_sync.sync_outbound(note=f"Roaming daemon {' + '.join(parts)} for {self.recipient}")

        return DaemonCycleResult(
            collected_bridge_task_ids=collected,
            dispatched_mailbox_task_ids=dispatched,
        )

    async def run_loop(self, *, interval_seconds: float = 10.0) -> None:
        while True:
            try:
                await self.cycle_once()
            except Exception:
                pass
            await asyncio.sleep(interval_seconds)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local roaming dispatch/collect daemon.")
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--mailbox-root", default="")
    parser.add_argument("--ledger-dir", default="")
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--responder", required=True)
    parser.add_argument("--dispatch-limit", type=int, default=1)
    parser.add_argument("--repo-root", default="")
    parser.add_argument("--git-branch", default="")
    sub = parser.add_subparsers(dest="mode", required=True)
    once = sub.add_parser("run-once")
    once.add_argument("--json", action="store_true")
    loop = sub.add_parser("run-loop")
    loop.add_argument("--interval", type=float, default=10.0)
    return parser


async def _main_async(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    adapter = _build_bridge(
        db_path=Path(args.db_path),
        mailbox_root=Path(args.mailbox_root) if args.mailbox_root else None,
        ledger_dir=Path(args.ledger_dir) if args.ledger_dir else None,
    )
    git_sync = None
    if args.repo_root and args.git_branch:
        git_sync = MailboxRepoSync(repo_root=Path(args.repo_root), branch=args.git_branch)
    daemon = RoamingDispatchDaemon(
        adapter=adapter,
        recipient=args.recipient,
        responder=args.responder,
        dispatch_limit=args.dispatch_limit,
        git_sync=git_sync,
    )

    if args.mode == "run-once":
        result = await daemon.cycle_once()
        if args.json:
            print(json.dumps(result.__dict__, indent=2, ensure_ascii=True))
        return 0

    if args.mode == "run-loop":
        await daemon.run_loop(interval_seconds=args.interval)
        return 0

    parser.error("unknown mode")
    return 2


def main(argv: list[str] | None = None) -> int:
    import asyncio

    return asyncio.run(_main_async(argv))


if __name__ == "__main__":
    raise SystemExit(main())
