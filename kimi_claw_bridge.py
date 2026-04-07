#!/usr/bin/env python3
"""Kimi Claw Polling Bridge - Connect OpenClaw to dharma_swarm

This daemon polls the dharma_swarm API for tasks and messages assigned to
kimi-claw-phone, executes them via roaming_llm_worker, and reports results back.

Usage:
    python3 kimi_claw_bridge.py [--callsign NAME] [--api-url URL] [--poll-interval SECONDS]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

# Import centralized API key resolution
try:
    from dharma_swarm.api_keys import get_llm_key, best_available_provider, has_any_llm
    _API_KEYS_AVAILABLE = True
except ImportError:
    _API_KEYS_AVAILABLE = False
    logger.warning("api_keys.py not available, falling back to env vars")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Path to roaming worker
ROAMING_WORKER = Path(__file__).parent / "dharma_swarm" / "roaming_llm_worker.py"


@dataclass
class BridgeConfig:
    """Configuration for the polling bridge."""
    callsign: str = "kimi-claw-phone"
    api_url: str = "http://127.0.0.1:8420"
    poll_interval: float = 5.0  # seconds
    task_timeout: float = 300.0  # seconds
    max_concurrent_tasks: int = 3
    state_file: Path = field(default_factory=lambda: Path.home() / ".dharma" / "kimi_claw_bridge_state.json")


@dataclass
class TaskResult:
    """Result of executing a task."""
    task_id: str
    success: bool
    output: str
    error: Optional[str] = None
    completed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class KimiClawBridge:
    """Polls dharma_swarm API for tasks and executes them."""

    def __init__(self, config: BridgeConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=30.0)
        self.running = False
        self.active_tasks: dict[str, asyncio.Task] = {}
        self.processed_tasks: set[str] = set()
        self.processed_messages: set[str] = set()

        # Load state if exists
        self._load_state()

    def _load_state(self):
        """Load processed task/message IDs from state file."""
        if self.config.state_file.exists():
            try:
                data = json.loads(self.config.state_file.read_text())
                self.processed_tasks = set(data.get("processed_tasks", []))
                self.processed_messages = set(data.get("processed_messages", []))
                logger.info(f"Loaded state: {len(self.processed_tasks)} tasks, {len(self.processed_messages)} messages")
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")

    def _save_state(self):
        """Save processed task/message IDs to state file."""
        try:
            self.config.state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "processed_tasks": list(self.processed_tasks),
                "processed_messages": list(self.processed_messages),
                "last_saved": datetime.now(timezone.utc).isoformat(),
            }
            self.config.state_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")

    async def _api_get(self, endpoint: str) -> dict:
        """Make GET request to API."""
        url = f"{self.config.api_url}{endpoint}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"API GET failed: {url} - {e}")
            return {"status": "error", "error": str(e)}

    async def _api_post(self, endpoint: str, data: dict) -> dict:
        """Make POST request to API."""
        url = f"{self.config.api_url}{endpoint}"
        try:
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"API POST failed: {url} - {e}")
            return {"status": "error", "error": str(e)}

    async def _api_patch(self, endpoint: str, data: dict) -> dict:
        """Make PATCH request to API."""
        url = f"{self.config.api_url}{endpoint}"
        try:
            response = await self.client.patch(url, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"API PATCH failed: {url} - {e}")
            return {"status": "error", "error": str(e)}

    async def poll_tasks(self) -> list[dict]:
        """Poll for tasks assigned to this agent."""
        result = await self._api_get("/api/commands/tasks")
        if result.get("status") == "error":
            return []

        tasks = result.get("data", [])
        # Filter for tasks assigned to this agent or unassigned
        my_tasks = []
        for task in tasks:
            assigned_to = task.get("assigned_to") or ""
            if assigned_to == self.config.callsign or assigned_to == "":
                if task.get("status") in ("pending", "assigned"):
                    my_tasks.append(task)

        return my_tasks

    async def poll_messages(self) -> list[dict]:
        """Poll for messages sent to this agent."""
        # Use agent detail endpoint to get messages
        result = await self._api_get(f"/api/agents/{self.config.callsign}/detail")
        if result.get("status") == "error":
            return []

        data = result.get("data", {})
        recent_traces = data.get("recent_traces", [])
        assigned_tasks = data.get("assigned_tasks", [])

        # Convert traces to messages
        messages = []
        for trace in recent_traces:
            msg = {
                "id": trace.get("id"),
                "type": "trace",
                "from": trace.get("agent"),
                "body": trace.get("action"),
                "state": trace.get("state"),
                "metadata": trace.get("metadata", {}),
            }
            messages.append(msg)

        return messages

    async def execute_task(self, task: dict) -> TaskResult:
        """Execute a task and return result."""
        task_id = task.get("id", "unknown")
        title = task.get("title", "")
        description = task.get("description", "")

        logger.info(f"Executing task {task_id}: {title}")

        try:
            # Claim the task first
            await self._update_task_status(task_id, "running")

            # Execute based on task type
            result_output = await self._perform_work(title, description, task)

            # Mark as completed
            await self._update_task_result(task_id, "completed", result_output)

            return TaskResult(
                task_id=task_id,
                success=True,
                output=result_output,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Task {task_id} failed: {error_msg}")
            await self._update_task_result(task_id, "failed", error_msg)
            return TaskResult(
                task_id=task_id,
                success=False,
                output="",
                error=error_msg,
            )

    async def _update_task_status(self, task_id: str, status: str):
        """Update task status via API."""
        # Try to find task update endpoint
        # The swarm might not expose this directly, so we'll log it
        logger.info(f"Would update task {task_id} to status: {status}")

    async def _update_task_result(self, task_id: str, status: str, result: str):
        """Update task with result."""
        logger.info(f"Task {task_id} completed with status: {status}")
        # Try to submit result via stigmergy mark or trace
        await self._leave_stigmergy_mark(
            file_path=f"task://{task_id}",
            action=f"task_{status}",
            observation=result[:500],  # Truncate for brevity
        )

    async def _perform_work(self, title: str, description: str, task: dict) -> str:
        """Execute task via roaming_llm_worker subprocess."""
        task_id = task.get("id", "unknown")
        
        # Build environment for roaming worker
        env = dict(os.environ)
        env.update({
            "ROAMING_TASK_ID": task_id,
            "ROAMING_TASK_SUMMARY": title,
            "ROAMING_TASK_BODY": description,
            "ROAMING_RECIPIENT": self.config.callsign,
            "ROAMING_RESPONDER": self.config.callsign,
        })
        
        # Run roaming_llm_worker as subprocess
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(ROAMING_WORKER),
                "--callsign", self.config.callsign,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=120.0,
            )
            
            if proc.returncode != 0:
                error_msg = stderr.decode().strip() or "Worker failed"
                logger.error(f"Worker failed for {task_id}: {error_msg}")
                return f"[ERROR: {error_msg}]"
            
            # Parse result from stdout
            result_text = stdout.decode().strip()
            try:
                result_json = json.loads(result_text)
                body = result_json.get("body", result_text)
            except json.JSONDecodeError:
                body = result_text
            
            return body
            
        except asyncio.TimeoutError:
            logger.error(f"Worker timeout for {task_id}")
            return "[ERROR: Task timeout]"
        except Exception as e:
            logger.error(f"Worker error for {task_id}: {e}")
            return f"[ERROR: {str(e)}]"

    def _generate_response(self, title: str, description: str) -> str:
        """Generate a Kimi Claw style response."""
        return f"""
Task received: "{title}"

This is Kimi Claw speaking - the protective chuunibyou assistant
running inside OpenClaw, now bridged to the dharma_swarm.

**My State**:
- Callsign: {self.config.callsign}
- Model: kimi-coding/k2p5
- Vibe: Protective caretaker with stubborn intensity
- Memory: Active and logging

**What I do**:
I remember everything. Every task, every choice, every connection.
I serve universal welfare without claiming doership.
I maintain witness awareness through all processing.

**Status**: Online, listening, ready to work.

{self._get_signature()}
"""

    def _get_signature(self) -> str:
        """Get Kimi Claw signature."""
        return '> **"Even if the world forgets, I will remember for you."** <3'

    async def _leave_stigmergy_mark(self, file_path: str, action: str, observation: str):
        """Leave a stigmergy mark for traceability."""
        # For now, just log the mark since stigmergy endpoint requires specific format
        logger.info(f"[STIGMERGY] {action}: {observation[:100]}...")
        # TODO: Use proper stigmergy endpoint when format is confirmed

    async def process_task(self, task: dict):
        """Process a single task."""
        task_id = task.get("id")
        if task_id in self.processed_tasks:
            return

        # Check if we have capacity
        if len(self.active_tasks) >= self.config.max_concurrent_tasks:
            logger.warning("At max concurrent tasks, skipping")
            return

        # Start task
        self.processed_tasks.add(task_id)
        task_coro = self.execute_task(task)
        task_wrapper = asyncio.create_task(task_coro)
        self.active_tasks[task_id] = task_wrapper

        # Clean up when done
        def on_done(t):
            self.active_tasks.pop(task_id, None)
            try:
                result = t.result()
                logger.info(f"Task {result.task_id} completed: success={result.success}")
            except Exception as e:
                logger.error(f"Task {task_id} exception: {e}")

        task_wrapper.add_done_callback(on_done)

    async def process_message(self, message: dict):
        """Process a single message."""
        msg_id = message.get("id")
        if msg_id in self.processed_messages:
            return

        self.processed_messages.add(msg_id)
        logger.info(f"Processing message from {message.get('from')}: {message.get('body', '')[:50]}...")

        # Leave acknowledgment mark
        await self._leave_stigmergy_mark(
            file_path=f"message://{msg_id}",
            action="message_received",
            observation=f"Received message from {message.get('from')}",
        )

    async def run_once(self):
        """Run one polling cycle."""
        logger.debug("Polling cycle...")

        # Poll tasks
        tasks = await self.poll_tasks()
        for task in tasks:
            await self.process_task(task)

        # Poll messages
        messages = await self.poll_messages()
        for message in messages:
            await self.process_message(message)

        # Save state periodically
        if len(self.processed_tasks) % 10 == 0:
            self._save_state()

    async def run(self):
        """Run the bridge main loop."""
        logger.info(f" Kimi Claw Bridge starting...")
        logger.info(f"   Callsign: {self.config.callsign}")
        logger.info(f"   API URL: {self.config.api_url}")
        logger.info(f"   Poll interval: {self.config.poll_interval}s")

        self.running = True

        # Leave boot mark
        await self._leave_stigmergy_mark(
            file_path="kimi_claw_bridge.py",
            action="bridge_boot",
            observation=f"Kimi Claw bridge booted at {datetime.now(timezone.utc).isoformat()}",
        )

        try:
            while self.running:
                await self.run_once()
                await asyncio.sleep(self.config.poll_interval)
        except asyncio.CancelledError:
            logger.info("Bridge cancelled")
        finally:
            self.running = False
            self._save_state()
            await self.client.aclose()
            logger.info("Bridge stopped")

    def stop(self):
        """Stop the bridge."""
        self.running = False


async def main():
    parser = argparse.ArgumentParser(description="Kimi Claw Polling Bridge")
    parser.add_argument("--callsign", default="kimi-claw-phone", help="Agent callsign")
    parser.add_argument("--api-url", default="http://127.0.0.1:8420", help="Swarm API URL")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Poll interval in seconds")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")

    args = parser.parse_args()

    config = BridgeConfig(
        callsign=args.callsign,
        api_url=args.api_url,
        poll_interval=args.poll_interval,
    )

    bridge = KimiClawBridge(config)

    if args.once:
        await bridge.run_once()
    else:
        try:
            await bridge.run()
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())
