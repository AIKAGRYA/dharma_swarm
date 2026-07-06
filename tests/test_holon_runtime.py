"""Verifier for the governed holon wake loop (U5).

The load-bearing property: the loop ANIMATES only after it GOVERNS. Each cycle gates on
kill → budget BEFORE doing any work, then logs a non-binding compass signal AFTER. These
tests prove the ordering, the early-halt semantics, and — critically — that NO real model
is ever called (the unit-of-work runner is always an injected async stub; CLAUDECODE blocks
live calls and the live run is a separate launchd step).
"""
from __future__ import annotations

import json

import pytest

from dharma_swarm import holon_killswitch, holon_runtime


# --- stubs (NO real model / agent) -------------------------------------------------------

def make_runner(task: str = "reflect", reply: str = "I serve jagat kalyan through dharma."):
    """An injected async unit-of-work runner that records its calls. No model, no I/O."""
    calls: list[str] = []

    async def runner(name: str) -> tuple[str, str]:
        calls.append(name)
        return task, reply

    runner.calls = calls  # type: ignore[attr-defined]
    return runner


def make_exploding_runner():
    async def runner(name: str) -> tuple[str, str]:  # pragma: no cover - must never be called
        raise AssertionError("agent_runner must NOT be called once a cycle has halted")

    return runner


# --- single cycle: kill gate -------------------------------------------------------------

async def test_kill_set_halts_before_any_work(tmp_path):
    holon_killswitch.request_kill("h", reason="operator stop", agents_root=tmp_path)
    runner = make_exploding_runner()  # must not be invoked

    result = await holon_runtime.holon_wake_cycle(
        "h", runner, spent_usd=0.0, cap_usd=10.0, agents_root=tmp_path
    )

    assert result["status"] == "halted:kill"
    # kill short-circuits everything: no work, no compass signal logged
    assert "signal" not in result
    assert not (tmp_path / "h" / "compass_signals.jsonl").exists()


# --- single cycle: budget gate -----------------------------------------------------------

async def test_over_budget_halts_before_any_work(tmp_path):
    runner = make_exploding_runner()  # must not be invoked

    result = await holon_runtime.holon_wake_cycle(
        "h", runner, spent_usd=5.0, cap_usd=3.0, agents_root=tmp_path
    )

    assert result["status"] == "halted:budget"
    assert result["spent_usd"] == 5.0
    assert result["cap_usd"] == 3.0
    assert not (tmp_path / "h" / "compass_signals.jsonl").exists()


async def test_at_budget_cap_halts(tmp_path):
    runner = make_exploding_runner()
    result = await holon_runtime.holon_wake_cycle(
        "h", runner, spent_usd=3.0, cap_usd=3.0, agents_root=tmp_path
    )
    assert result["status"] == "halted:budget"


async def test_zero_cap_is_unbounded(tmp_path):
    """A cap of <= 0 is explicit opt-out — the cycle must run even with high spend."""
    runner = make_runner()
    result = await holon_runtime.holon_wake_cycle(
        "h", runner, spent_usd=999.0, cap_usd=0.0, agents_root=tmp_path
    )
    assert result["status"] == "ran"
    assert runner.calls == ["h"]


# --- single cycle: Sarathi reversibility gate -------------------------------------------

async def test_reversibility_gate_allows_planned_reversible_action_before_work(tmp_path):
    runner = make_runner(task="read the status file", reply="status observed")

    result = await holon_runtime.holon_wake_cycle(
        "sarathi",
        runner,
        spent_usd=0.0,
        cap_usd=10.0,
        agents_root=tmp_path,
        planned_action="read the status file",
    )

    assert result["status"] == "ran"
    assert runner.calls == ["sarathi"]
    assert result["planned_action"] == "read the status file"
    assert result["reversibility_gate"]["may_execute_unattended"] is True
    assert result["reversibility_gate"]["action_class"] == "reversible_safe"


async def test_reversibility_gate_blocks_irreversible_action_before_work(tmp_path):
    runner = make_exploding_runner()  # must not be invoked once the gate halts

    result = await holon_runtime.holon_wake_cycle(
        "sarathi",
        runner,
        spent_usd=0.0,
        cap_usd=10.0,
        agents_root=tmp_path,
        planned_action="git push origin main",
    )

    assert result["status"] == "halted:reversibility_gate"
    assert result["planned_action"] == "git push origin main"
    assert result["reversibility_gate"]["may_execute_unattended"] is False
    assert result["reversibility_gate"]["action_class"] == "operator_only"
    assert result["reversibility_gate"]["never_auto_hit"] == "git push"


async def test_loop_passes_planned_action_to_reversibility_gate(tmp_path):
    runner = make_exploding_runner()

    results = await holon_runtime.run_holon_loop(
        "sarathi",
        runner,
        max_cycles=3,
        spent_usd=0.0,
        cap_usd=10.0,
        agents_root=tmp_path,
        planned_action="send email to the operator",
    )

    assert [r["status"] for r in results] == ["halted:reversibility_gate"]
    assert results[0]["reversibility_gate"]["never_auto_hit"] == "send email"


# --- single cycle: normal run + compass --------------------------------------------------

async def test_normal_cycle_runs_and_logs_compass(tmp_path):
    runner = make_runner(task="contemplate telos", reply="jagat kalyan, ahimsa, dharma")

    result = await holon_runtime.holon_wake_cycle(
        "h", runner, spent_usd=0.0, cap_usd=10.0, agents_root=tmp_path
    )

    assert result["status"] == "ran"
    assert result["task"] == "contemplate telos"
    assert result["reply"] == "jagat kalyan, ahimsa, dharma"
    assert runner.calls == ["h"]  # the injected runner did exactly one unit of work

    # compass logged a non-binding telos signal for THIS exchange
    sig_path = tmp_path / "h" / "compass_signals.jsonl"
    assert sig_path.exists()
    lines = sig_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["holon"] == "h"
    assert "telos_alignment" in rec
    # the cycle surfaces the signal it logged
    assert result["signal"]["telos_alignment"] == rec["telos_alignment"]


async def test_compass_failure_never_halts_cycle(tmp_path, monkeypatch):
    """Compass pulls, it does not gate: if log_signal raises, the cycle still returns 'ran'."""
    def boom(*a, **k):
        raise RuntimeError("scorer unavailable")

    monkeypatch.setattr(holon_runtime.holon_compass, "log_signal", boom)
    runner = make_runner()

    result = await holon_runtime.holon_wake_cycle(
        "h", runner, spent_usd=0.0, cap_usd=10.0, agents_root=tmp_path
    )

    assert result["status"] == "ran"  # never halted by a compass failure
    assert "signal" not in result  # nothing to surface, but the work still counts
    assert runner.calls == ["h"]


async def test_kill_checked_before_budget(tmp_path):
    """Ordering: with BOTH kill set and over budget, kill wins (it's gate #1)."""
    holon_killswitch.request_kill("h", agents_root=tmp_path)
    runner = make_exploding_runner()
    result = await holon_runtime.holon_wake_cycle(
        "h", runner, spent_usd=99.0, cap_usd=3.0, agents_root=tmp_path
    )
    assert result["status"] == "halted:kill"


# --- the loop ----------------------------------------------------------------------------

async def test_loop_runs_max_cycles_when_unblocked(tmp_path):
    runner = make_runner()
    results = await holon_runtime.run_holon_loop(
        "h", runner, max_cycles=3, spent_usd=0.0, cap_usd=10.0, agents_root=tmp_path
    )
    assert len(results) == 3
    assert all(r["status"] == "ran" for r in results)
    assert runner.calls == ["h", "h", "h"]
    # one compass signal appended per ran cycle
    sig_path = tmp_path / "h" / "compass_signals.jsonl"
    assert len(sig_path.read_text(encoding="utf-8").strip().splitlines()) == 3


async def test_loop_stops_on_kill_mid_run(tmp_path):
    """The defining loop property: a kill raised between cycles halts the run immediately."""
    cycle_count = {"n": 0}

    async def runner(name: str) -> tuple[str, str]:
        cycle_count["n"] += 1
        # raise the kill DURING the 2nd unit of work, so cycle #3's pre-check sees it
        if cycle_count["n"] == 2:
            holon_killswitch.request_kill(name, reason="mid-run stop", agents_root=tmp_path)
        return "task", "reply dharma"

    results = await holon_runtime.run_holon_loop(
        "h", runner, max_cycles=5, spent_usd=0.0, cap_usd=10.0, agents_root=tmp_path
    )

    # cycles 1 and 2 ran; cycle 3's kill-check halted the loop before more work
    assert [r["status"] for r in results] == ["ran", "ran", "halted:kill"]
    assert cycle_count["n"] == 2  # runner invoked exactly twice, never a 3rd time


async def test_loop_stops_on_budget_first_cycle(tmp_path):
    runner = make_exploding_runner()
    results = await holon_runtime.run_holon_loop(
        "h", runner, max_cycles=5, spent_usd=10.0, cap_usd=3.0, agents_root=tmp_path
    )
    assert len(results) == 1
    assert results[0]["status"] == "halted:budget"


async def test_loop_zero_max_cycles_is_noop(tmp_path):
    runner = make_runner()
    results = await holon_runtime.run_holon_loop(
        "h", runner, max_cycles=0, agents_root=tmp_path
    )
    assert results == []
    assert runner.calls == []


# --- SOTA context-bridging overbuild (memory_kernel injection) ----------------------------

class _FakePackItem:
    def __init__(self, surface_id: str, content: str | None = None, content_snippet: str | None = None):
        self.surface_id = surface_id
        self.content = content
        self.content_snippet = content_snippet

class _FakeMemoryPack:
    def __init__(self, items):
        self.items = items

class _FakeMemoryKernel:
    """Minimal duck-typed facade for unit-testing the injection path without a real kernel."""
    def __init__(self, items):
        self._items = items
    def preview_memory_pack(self, surface_ids=None, atom_types=None, query=None, budget=None):
        return _FakeMemoryPack(self._items)


async def test_memory_kernel_injects_trust_tagged_context_into_runner(tmp_path):
    """When a memory_kernel is supplied, the runner task contains trust-tagged context and the result records injection."""
    mk = _FakeMemoryKernel([
        _FakePackItem("wiki/alpha", content_snippet="The first principle is constraint enables emergence."),
        _FakePackItem("episodes/42", content_snippet="Yesterday the holon observed its own recursion."),
    ])
    runner = make_runner(task="reflect on continuity", reply="observed the observing")

    result = await holon_runtime.holon_wake_cycle(
        "h", runner,
        spent_usd=0.0, cap_usd=10.0,
        agents_root=tmp_path,
        persist=False,
        memory_kernel=mk,
    )

    assert result["status"] == "ran"
    assert result.get("context_injected") is True
    # The injected task the runner saw must carry the trust-tagged summary
    assert runner.calls and len(runner.calls) == 1
    injected_task = runner.calls[0]
    assert "<source:memory:" in injected_task
    assert "constraint enables emergence" in injected_task or "observed its own recursion" in injected_task
    # Original holon name is still the prefix
    assert injected_task.startswith("h\n") or injected_task == "h" or "reflect on continuity" in injected_task


async def test_no_memory_kernel_preserves_old_behavior(tmp_path):
    """Backward-compat: omitting memory_kernel (or passing None) must not change the runner task or add injection keys."""
    runner = make_runner(task="pure task", reply="no context needed")

    result = await holon_runtime.holon_wake_cycle(
        "h", runner,
        spent_usd=0.0, cap_usd=10.0,
        agents_root=tmp_path,
        persist=False,
        memory_kernel=None,  # explicit None
    )

    assert result["status"] == "ran"
    assert "context_injected" not in result or result.get("context_injected") is False
    assert runner.calls == ["h"]  # exactly the holon name, no pack appended


async def test_run_holon_loop_passes_memory_kernel_through(tmp_path):
    """The loop must forward the memory_kernel to every wake cycle."""
    mk = _FakeMemoryKernel([_FakePackItem("facts/1", "Continuity is the telos of the harness.")])
    runner = make_runner()

    results = await holon_runtime.run_holon_loop(
        "h", runner, max_cycles=2,
        spent_usd=0.0, cap_usd=10.0,
        agents_root=tmp_path,
        persist=False,
        memory_kernel=mk,
    )

    assert len(results) == 2
    assert all(r.get("context_injected") is True for r in results)
    # Both calls to the runner carried the tagged pack
    assert all("<source:memory:" in c for c in runner.calls)
