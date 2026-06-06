"""Real-concurrency double-lease proof for the LivingAgentKernel daemon.

This closes the ``committed_bypass_found`` gap on the capstone matrix unit. The
matrix test ``test_two_racing_drains_never_double_lease_any_wake`` only proves
that the SERVICE flock serializes: it has the PARENT process hold the flock and
then asserts the second drain bounces to ``lock_held``. That asserts the lock is
honored when *deliberately held by a third party*; it does NOT prove the
invariant under a genuine race between two independent OS daemons both trying to
acquire the lock and lease from the same store at the same instant.

Here we spawn TWO ACTUAL concurrent subprocess daemons (``subprocess.Popen``)
running the real ``scripts/runtime/living_agent_kernel_service.py`` CLI — the
exact production entry point — against ONE pre-seeded store with several queued
wakes and NO externally-held lock. They synchronize on a barrier file so both
hit the ``daemon_service.lock`` acquire within microseconds of each other, then
genuinely race. We merge/parse the resulting ``wake_ledger.jsonl`` and assert,
for EVERY wake_id:

  * exactly one 'leased' transition (no double-lease), and
  * exactly one terminal (completed/review) transition (no double-completion),
  * final attempt == 1 (the wake was leased exactly once, never re-attempted),
  * the hash-chained wake ledger still verifies after two writers touched disk.

The lease primitive under test: ``KernelRunStore.lease_next_wake`` does a
non-atomic read-modify-write (read whole ledger -> pick first queued -> append a
'leased' row) with NO kernel-level file lock. Its concurrency safety is provided
*entirely* by the service-level ``fcntl.flock`` in
``living_agent_kernel_service.run_kernel_daemon_service``. The production daemon
path is always the service, so the honest test of the real invariant is two real
service processes racing — which is exactly what this file does.

Nothing is written outside ``tmp_path``. No provider client is constructed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from dharma_swarm.operator_core.living_agent_kernel import (
    AgentRunEnvelope,
    KernelRunStore,
    KernelTask,
    LivingAgentKernel,
    MemoryPlan,
    ProofRequest,
    ToolRequest,
    TriggerEnvelope,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_SCRIPT = REPO_ROOT / "scripts" / "runtime" / "living_agent_kernel_service.py"


def _envelope(correlation_id: str) -> AgentRunEnvelope:
    return AgentRunEnvelope(
        agent_uid="codex_composer",
        task=KernelTask(text=f"Race wake {correlation_id}"),
        trigger=TriggerEnvelope(source="manual", correlation_id=correlation_id),
        memory=MemoryPlan(
            read_namespaces=["agent:codex_composer:working"],
            write_namespaces=["agent:codex_composer:lessons"],
        ),
        tool_request=ToolRequest(
            requested_tools=["session_status"],
            tool_calls=[{"name": "session_status", "arguments": {}}],
        ),
        proof=ProofRequest(
            verifier_commands=["pytest tests/test_living_agent_kernel_race_double_lease.py"],
        ),
    )


def _seed_store(store_dir: Path, workspace_root: Path, wake_ids: list[str]) -> None:
    kernel = LivingAgentKernel(store=KernelRunStore(store_dir), workspace_root=workspace_root)
    for index, wake_id in enumerate(wake_ids):
        kernel.enqueue_wake(_envelope(f"race-{index}"), wake_id=wake_id)


def _spawn_daemon(
    store_dir: Path,
    workspace_root: Path,
    *,
    daemon_id: str,
    barrier: Path,
    cycles: int,
    max_wakes: int,
) -> subprocess.Popen[str]:
    """Spawn one real service-CLI daemon that waits on a barrier, then drains.

    We do NOT call the CLI directly; we wrap it in a tiny launcher that spins on
    a barrier file so both daemons release at (nearly) the same instant and race
    the lock acquire. The launcher then ``exec``s the real service module so the
    production code path (service flock + kernel lease) is what actually runs.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    launcher = (
        "import os, sys, time, runpy\n"
        f"barrier = {str(barrier)!r}\n"
        # Tight spin until the parent drops the barrier. Sub-millisecond release.
        "while not os.path.exists(barrier):\n"
        "    time.sleep(0.0002)\n"
        f"sys.argv = [{str(SERVICE_SCRIPT)!r},"
        f" '--store-dir', {str(store_dir)!r},"
        f" '--workspace-root', {str(workspace_root)!r},"
        f" '--daemon-id', {daemon_id!r},"
        f" '--cycles', {str(cycles)!r},"
        f" '--max-wakes', {str(max_wakes)!r},"
        " '--interval-seconds', '0', '--json']\n"
        f"runpy.run_path({str(SERVICE_SCRIPT)!r}, run_name='__main__')\n"
    )
    return subprocess.Popen(
        [sys.executable, "-c", launcher],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _race_once(tmp_path: Path, iteration: int, *, n_wakes: int = 6) -> dict[str, object]:
    """Run one real two-daemon race against a fresh store; return analysis dict."""
    store_dir = tmp_path / f"kernel_{iteration}"
    barrier = tmp_path / f"go_{iteration}"
    wake_ids = [f"wake-{iteration}-{i}" for i in range(n_wakes)]
    _seed_store(store_dir, tmp_path, wake_ids)

    # Enough cycles for either daemon to clear the whole queue on its own.
    cycles = n_wakes + 2
    proc_a = _spawn_daemon(
        store_dir, tmp_path, daemon_id="race-a", barrier=barrier, cycles=cycles, max_wakes=1
    )
    proc_b = _spawn_daemon(
        store_dir, tmp_path, daemon_id="race-b", barrier=barrier, cycles=cycles, max_wakes=1
    )

    # Give both children time to reach the spin loop, then release simultaneously.
    time.sleep(0.05)
    barrier.write_text("go", encoding="utf-8")

    out_a, err_a = proc_a.communicate(timeout=120)
    out_b, err_b = proc_b.communicate(timeout=120)

    # Both must exit cleanly: the production contract is winner -> 0 (completed),
    # loser -> 2 (lock_held). Neither may crash.
    assert proc_a.returncode in {0, 2}, f"iter {iteration} daemon A crashed rc={proc_a.returncode}\n{err_a}"
    assert proc_b.returncode in {0, 2}, f"iter {iteration} daemon B crashed rc={proc_b.returncode}\n{err_b}"

    statuses = []
    for out in (out_a, out_b):
        out = out.strip()
        if out:
            try:
                statuses.append(json.loads(out.splitlines()[-1])["status"])
            except (json.JSONDecodeError, KeyError, IndexError):
                statuses.append(f"unparsed:{out[:80]}")

    ledger_path = store_dir / "wake_ledger.jsonl"
    rows = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    leased = Counter(r["wake_id"] for r in rows if r["status"] == "leased")
    # A genuine completion is a 'wake_terminal_result' transition. The kernel also
    # appends a 'source_closeback_recorded' row that PRESERVES the terminal status
    # field but is NOT a second completion (same lease_owner, same attempt). Count
    # by reason so the closeback row never masquerades as a double-completion.
    terminal = Counter(
        r["wake_id"]
        for r in rows
        if r["status"] in {"completed", "review"} and r.get("reason") == "wake_terminal_result"
    )

    fresh = KernelRunStore(store_dir)
    latest = fresh.latest_wake_records()
    wake_ok, wake_errors = fresh.verify_wake_ledger()

    return {
        "iteration": iteration,
        "wake_ids": wake_ids,
        "statuses": statuses,
        "leased": dict(leased),
        "terminal": dict(terminal),
        "latest": latest,
        "wake_ok": wake_ok,
        "wake_errors": wake_errors,
        "rows": rows,
        "store_dir": store_dir,
    }


def _assert_no_double_lease(result: dict[str, object]) -> None:
    iteration = result["iteration"]
    wake_ids = result["wake_ids"]
    leased = result["leased"]
    terminal = result["terminal"]
    latest = result["latest"]

    for wake_id in wake_ids:
        # The load-bearing invariant: exactly one 'leased' transition per wake.
        lease_count = leased.get(wake_id, 0)
        assert lease_count == 1, (
            f"iter {iteration}: DOUBLE-LEASE — {wake_id} leased {lease_count} times. "
            f"leased={leased} statuses={result['statuses']}\n"
            f"leased rows for {wake_id}: "
            f"{[r for r in result['rows'] if r['wake_id'] == wake_id and r['status'] == 'leased']}"
        )
        # And never completed/reviewed twice.
        term_count = terminal.get(wake_id, 0)
        assert term_count == 1, (
            f"iter {iteration}: DOUBLE-COMPLETION — {wake_id} terminal {term_count} times. "
            f"terminal={terminal}"
        )
        record = latest[wake_id]
        assert record.status in {"completed", "review"}, (
            f"iter {iteration}: {wake_id} not terminal: {record.status}"
        )
        assert record.attempt == 1, (
            f"iter {iteration}: {wake_id} attempt={record.attempt} (re-leased under race)"
        )

    assert result["wake_ok"] is True, (
        f"iter {iteration}: wake ledger failed hash verification after concurrent writers: "
        f"{result['wake_errors']}"
    )


def test_two_real_subprocess_daemons_never_double_lease_single_iteration(tmp_path):
    """One real two-OS-daemon race; at least one daemon must actually win work."""
    result = _race_once(tmp_path, iteration=0, n_wakes=6)
    _assert_no_double_lease(result)
    # The race must have been REAL: the queue is fully drained and at least one
    # daemon reported a terminal service status (completed) — not both lock_held.
    assert "completed" in result["statuses"], (
        f"no daemon completed work — race may not have exercised the drain: {result['statuses']}"
    )


def test_two_real_subprocess_daemons_never_double_lease_stress_loop(tmp_path):
    """Stress the race across many fresh stores in-process (tight inner loop).

    Race conditions are flaky; one clean run proves little. We run the real
    two-daemon race ITERATIONS times against fresh stores and assert the
    no-double-lease invariant on every one. Combined with the shell-loop wrapper
    in the unit's verifier, this yields 50+ genuine races.
    """
    iterations = int(os.environ.get("RACE_ITERATIONS", "12"))
    n_wakes = int(os.environ.get("RACE_WAKES", "6"))
    failures: list[str] = []
    completed_seen = 0
    for iteration in range(iterations):
        result = _race_once(tmp_path, iteration=iteration, n_wakes=n_wakes)
        try:
            _assert_no_double_lease(result)
        except AssertionError as exc:  # capture evidence, keep going to count
            failures.append(str(exc))
        if "completed" in result["statuses"]:
            completed_seen += 1

    assert not failures, (
        f"{len(failures)}/{iterations} race iterations DOUBLE-LEASED:\n" + "\n---\n".join(failures)
    )
    # Sanity: the races actually exercised real drains, not all-lock_held no-ops.
    assert completed_seen == iterations, (
        f"only {completed_seen}/{iterations} iterations drained the queue; race not exercised"
    )
