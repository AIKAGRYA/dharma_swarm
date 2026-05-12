"""Worker loop for live external-agent interop adapters."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import time
from pathlib import Path

from dharma_swarm.operator_core.interop import AgentInteropStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Dharma interop worker")
    parser.add_argument("--adapter-id", required=True)
    parser.add_argument("--worker-id", default="")
    parser.add_argument("--command-template", default="")
    parser.add_argument("--repo-root", default=str(Path.cwd()))
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--lease-seconds", type=int, default=900)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--once", action="store_true")
    return parser


def _prompt_for_task(task: dict, repo_root: Path) -> str:
    capabilities = ", ".join(str(item) for item in task.get("capabilities", []) or [])
    metadata = task.get("metadata") or {}
    return "\n".join(
        [
            "# Dharma Swarm Interop Task",
            "",
            f"Task ID: {task.get('task_id')}",
            f"Recipient: {task.get('recipient')}",
            f"Sender: {task.get('sender')}",
            f"Repository: {repo_root}",
            f"Capabilities: {capabilities or 'none'}",
            f"Metadata: {metadata}",
            "",
            "## Summary",
            str(task.get("summary") or ""),
            "",
            "## Body",
            str(task.get("body") or ""),
            "",
            "Return a concise execution report. If you changed files, list them.",
        ]
    )


def _render_command(template: str, *, prompt_file: Path, repo_root: Path, task_id: str) -> list[str]:
    return shlex.split(
        template.format(prompt_file=str(prompt_file), repo_root=str(repo_root), task_id=task_id)
    )


def _run_task(
    *,
    store: AgentInteropStore,
    task: dict,
    adapter_id: str,
    worker_id: str,
    command_template: str,
    repo_root: Path,
    timeout_seconds: int,
) -> None:
    task_id = str(task.get("task_id") or "")
    prompt_file = store.prompts_dir / f"{task_id}.md"
    prompt_file.write_text(_prompt_for_task(task, repo_root), encoding="utf-8")
    store.heartbeat_worker(
        worker_id=worker_id,
        adapter_id=adapter_id,
        status="working",
        current_task_id=task_id,
        metadata={"prompt_file": str(prompt_file)},
    )
    try:
        result = subprocess.run(
            _render_command(command_template, prompt_file=prompt_file, repo_root=repo_root, task_id=task_id),
            cwd=repo_root,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        body = result.stdout.strip()
        if result.stderr.strip():
            body = f"{body}\n\nSTDERR:\n{result.stderr.strip()}".strip()
        status = "responded" if result.returncode == 0 else "failed"
        summary = f"{adapter_id} completed task" if result.returncode == 0 else f"{adapter_id} failed task"
        metadata = {"returncode": result.returncode, "prompt_file": str(prompt_file)}
    except Exception as exc:
        body = str(exc)
        status = "failed"
        summary = f"{adapter_id} worker exception"
        metadata = {"prompt_file": str(prompt_file), "error": type(exc).__name__}
    store.respond_to_task(
        task_id=task_id,
        responder=worker_id,
        summary=summary,
        body=body,
        status=status,
        metadata=metadata,
    )
    store.heartbeat_worker(
        worker_id=worker_id,
        adapter_id=adapter_id,
        status="idle",
        metadata={"last_task_id": task_id, "last_status": status},
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    adapter_id = args.adapter_id
    worker_id = args.worker_id or f"{adapter_id}-worker"
    repo_root = Path(args.repo_root).expanduser().resolve()
    store = AgentInteropStore()
    if not args.command_template:
        while True:
            store.heartbeat_worker(
                worker_id=worker_id,
                adapter_id=adapter_id,
                status="waiting_for_command",
                metadata={"mode": "handoff"},
            )
            if args.once:
                break
            time.sleep(max(0.2, args.poll_seconds))
        return 0

    while True:
        store.heartbeat_worker(worker_id=worker_id, adapter_id=adapter_id, status="idle")
        task = store.claim_next_task(
            recipient=adapter_id,
            worker_id=worker_id,
            lease_seconds=args.lease_seconds,
        )
        if task is not None:
            _run_task(
                store=store,
                task=task,
                adapter_id=adapter_id,
                worker_id=worker_id,
                command_template=args.command_template,
                repo_root=repo_root,
                timeout_seconds=args.timeout_seconds,
            )
        if args.once:
            break
        time.sleep(max(0.2, args.poll_seconds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
