"""RUDRA live-driver selftest: one real app-server session, one read-only turn.

Authorized minimal liveness proof for the section 11 binding. Exactly one
``codex app-server`` session is spawned through ``ProcessOwner`` and asked to
echo a nonce; no file mutation is requested and the scratch workcell is
witnessed unchanged afterwards. The receipt carries world-locus (commit,
host, branch), binary identity, token/wall truth, and the containment object
that was actually sent. If no working app-server binary or credential exists
on the host, the missing piece surfaces as ``DriverBindError`` — liveness is
never faked.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import secrets
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from dharma_swarm.rudra.live_driver import LiveCodexDriver
from dharma_swarm.rudra.process_owner import ProcessOwner

SELFTEST_PROMPT = (
    "Read-only protocol probe. Reply with exactly this nonce and nothing "
    "else: {nonce}\nDo not create, modify, or delete any file. "
    "Do not run any command."
)


def _world_locus(repo_path: Path) -> dict[str, str]:
    def git(*args: str) -> str:
        proc = subprocess.run(
            ["/usr/bin/git", *args], cwd=repo_path,
            capture_output=True, text=True, timeout=15,
        )
        return proc.stdout.strip() if proc.returncode == 0 else "unknown"

    return {
        "commit": git("rev-parse", "--short=12", "HEAD"),
        "host": platform.node(),
        "branch": git("branch", "--show-current"),
    }


def run_live_selftest(
    receipt_root: Path,
    *,
    repo_path: Path,
    binary_path: str | None = None,
    model: str | None = None,
    model_provider: str | None = None,
    reasoning_effort: str | None = None,
    service_tier: str | None = None,
    deadline_seconds: float = 300.0,
) -> dict[str, Any]:
    """Run the single-session probe and fsync one receipt under receipt_root."""
    receipt_root = Path(receipt_root)
    scratch = receipt_root / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    binary = binary_path or shutil.which("codex")
    if binary is None:
        raise FileNotFoundError("no codex binary on PATH; cannot bind app-server")
    version = subprocess.run(
        [binary, "--version"], capture_output=True, text=True, timeout=30
    ).stdout.strip()
    binary_sha256 = hashlib.sha256(Path(binary).read_bytes()).hexdigest()

    nonce = secrets.token_hex(8)
    owner = ProcessOwner()
    driver = LiveCodexDriver(
        binary_path=binary,
        worktree=scratch,
        owner=owner,
        model=model,
        model_provider=model_provider,
        reasoning_effort=reasoning_effort,
        service_tier=service_tier,
        contract_digest="rudra-live-selftest",
        attempt_key=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
    )
    started = time.time()
    observation = None
    bind_error: str | None = None
    try:
        driver.start_or_resume()
        observation = driver.start_turn(
            prompt=SELFTEST_PROMPT.format(nonce=nonce),
            logical_seq=0,
            deadline_seconds=deadline_seconds,
        )
    except Exception as exc:  # receipt records the failure honestly, then raise
        bind_error = f"{type(exc).__name__}: {exc}"
    wall_seconds = time.time() - started
    driver.close()
    tree_dead = (
        all(owner.prove_dead(handle) for handle in driver.process_handles)
        if driver.process_handles
        else None
    )
    scratch_entries = sorted(p.name for p in scratch.iterdir())
    response_text = driver.last_response_text
    receipt: dict[str, Any] = {
        "receipt": "rudra.live_selftest.v1",
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "world": _world_locus(Path(repo_path)),
        "binary": {"path": binary, "sha256": binary_sha256, "version": version},
        "server_agent": driver.server_agent,
        "requested": {
            "model": model, "model_provider": model_provider,
            "reasoning_effort": reasoning_effort, "service_tier": service_tier,
        },
        "containment_sent": {
            "approvalPolicy": "never",
            "sandboxPolicy": driver.sandbox_policy(),
        },
        "nonce": nonce,
        "nonce_echoed": bool(response_text and nonce in response_text),
        "thread_id": driver.thread_id,
        "turn": observation.model_dump(mode="json") if observation else None,
        "bind_error": bind_error,
        "wall_seconds": round(wall_seconds, 3),
        "scratch_unchanged": scratch_entries == [],
        "scratch_entries": scratch_entries,
        "process_tree_proven_dead": tree_dead,
        "witness": driver.witness,
        "signal_failures": owner.signal_failures,
    }
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    path = receipt_root / f"selftest-{stamp}.json"
    receipt["receipt_path"] = str(path)
    line = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        view = memoryview(line.encode())
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    if bind_error is not None:
        raise RuntimeError(f"live selftest bind failed: {bind_error}")
    return receipt
