"""CLOSE THE LEARNING LOOP: a prior lesson is read back into the next wake.

This is the load-bearing test for the READ-BACK axis. The kernel already WRITES
per-agent lessons to a hash-chained ledger (``KernelLessonStore`` via the LEARN
executor ``commit_learning``). These tests prove the other half: when
``DHARMA_PERSISTENT_KERNEL_LESSONS_READBACK`` is on (with governance on), the real
``PersistentAgent.wake()`` READS its OWN accumulated lessons from the durable
ledger and INJECTS them into the ReAct INPUT before step 8 runs.

HONESTY BOUNDARY — what is proven here is DETERMINISTIC and narrow:
  the prior lesson string, read back from the durable hash-chained ledger, is
  PRESENT in the exact input passed to the (stubbed) ReAct loop on the next wake,
  AND the agent still completes.
It does NOT claim the LLM "used" or "improved" from the lesson — that stronger
behavioral claim needs the separate optional free-provider demo and is not made
by any assertion in this file. The ReAct loop is stubbed to capture its input.

Adversarial coverage:
  * cross-agent isolation — agent B does NOT read agent A's lessons
    (per-agent state_dir; and shared store scopes by agent_uid namespace).
  * tamper — a corrupted lessons-ledger row is skipped, not injected.
  * best-effort — a read failure -> the agent still completes, no lessons.

The flag-OFF path is asserted byte-identical (input == task_text, no markers).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from dharma_swarm.models import AgentRole, ProviderType
from dharma_swarm.operator_core.living_agent_kernel_lessons import KernelLessonStore
from dharma_swarm.persistent_agent import (
    PersistentAgent,
    _persistent_kernel_store_dir,
)


def _agent(state_dir: Path, *, name: str = "conductor_rb") -> PersistentAgent:
    return PersistentAgent(
        name=name,
        role=AgentRole.CONDUCTOR,
        provider_type=ProviderType.ANTHROPIC,
        model="claude-opus-4",
        state_dir=state_dir,
        wake_interval_seconds=1800.0,
    )


def _capture_react_loop(agent: PersistentAgent, summary: str):
    """Replace ONLY the AutonomousAgent ReAct loop with a recording stub that
    returns a real ``AgentResult`` and CAPTURES the exact input it was given.

    This is how we prove the read-back deterministically: we read back the input
    the conductor handed to step 8 and assert the prior lesson is present in it.
    """
    from unittest.mock import AsyncMock

    from dharma_swarm.autonomous_agent import AgentResult

    react = AsyncMock(
        return_value=AgentResult(
            summary=summary, turns=1, tokens_in=5, tokens_out=3, tool_calls_made=0
        )
    )
    agent._agent.wake = react  # type: ignore[method-assign]
    return react


def _captured_input(react) -> str:
    react.assert_awaited_once()
    args, kwargs = react.await_args
    return args[0] if args else kwargs.get("task", "")


def _seed_lesson(agent: PersistentAgent, delta_text: str) -> Path:
    """Write a lesson to the agent's OWN durable hash-chained ledger via the real
    store API the LEARN executor uses. Returns the namespace ledger path."""
    store = KernelLessonStore(_persistent_kernel_store_dir(agent.state_dir))
    namespace = f"agent:{agent.name}:lessons"
    store.append_lesson(agent.name, namespace, delta_text, run_id="seed-run")
    return store.namespace_path(namespace)


# -- CORE deterministic claim: prior lesson read back into next wake ---------


def test_prior_lesson_is_present_in_react_input_on_next_wake(tmp_path):
    """wake N wrote lesson L; wake N+1 reads L back into its ReAct input.

    Deterministic, no LLM: the lesson string appears verbatim in the captured
    input to the (stubbed) ReAct loop, AND the agent completes successfully."""
    sys.modules.pop("anthropic", None)
    sys.modules.pop("openai", None)

    agent = _agent(tmp_path / "agent", name="conductor_loop")
    lesson = "When investigating drift, reconcile control-surface rows before acting."
    _seed_lesson(agent, lesson)

    react = _capture_react_loop(agent, summary="surveyed; nothing salient")

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DHARMA_PERSISTENT_KERNEL_GOVERNANCE", "1")
        mp.setenv("DHARMA_PERSISTENT_KERNEL_LESSONS_READBACK", "1")
        result_info = asyncio.run(agent.wake(injected_task="investigate runtime drift"))

    captured = _captured_input(react)
    # the PRIOR lesson, read from the durable ledger, is PRESENT in the next
    # wake's ReAct input, and the original task is still there too.
    assert lesson in captured
    assert "Prior lessons:" in captured
    assert "investigate runtime drift" in captured
    # the agent STILL COMPLETED.
    assert result_info["success"] is True
    assert result_info.get("lessons_injected") is True
    # the original task_text (not the augmented input) drove witness/task fields.
    assert result_info["task"] == "investigate runtime drift"


def test_flag_off_is_byte_identical_no_readback(tmp_path):
    """Read-back flag unset -> the ReAct input equals task_text exactly and no
    lessons marker is set, even when a lesson exists on the ledger."""
    agent = _agent(tmp_path / "agent", name="conductor_off")
    _seed_lesson(agent, "this lesson must NOT be injected when the flag is off")
    react = _capture_react_loop(agent, summary="quiet wake")

    with pytest.MonkeyPatch.context() as mp:
        # governance ON but readback flag OFF -> still no read-back.
        mp.setenv("DHARMA_PERSISTENT_KERNEL_GOVERNANCE", "1")
        mp.delenv("DHARMA_PERSISTENT_KERNEL_LESSONS_READBACK", raising=False)
        result_info = asyncio.run(agent.wake(injected_task="routine survey"))

    captured = _captured_input(react)
    assert captured == "routine survey"
    assert "Prior lessons:" not in captured
    assert "lessons_injected" not in result_info
    assert result_info["success"] is True


def test_readback_requires_governance_on_too(tmp_path):
    """Read-back flag ON but governance flag OFF -> read-back is a strict subset;
    no lesson is injected (the input is byte-identical)."""
    agent = _agent(tmp_path / "agent", name="conductor_subset")
    _seed_lesson(agent, "should not appear without governance on")
    react = _capture_react_loop(agent, summary="quiet")

    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("DHARMA_PERSISTENT_KERNEL_GOVERNANCE", raising=False)
        mp.setenv("DHARMA_PERSISTENT_KERNEL_LESSONS_READBACK", "1")
        result_info = asyncio.run(agent.wake(injected_task="routine survey"))

    assert _captured_input(react) == "routine survey"
    assert "lessons_injected" not in result_info
    assert result_info["success"] is True


# -- adversarial: cross-agent isolation -------------------------------------


def test_agent_b_does_not_read_agent_a_lessons_per_agent_store(tmp_path):
    """With per-agent stores (no shared dir), agent B reading back gets NOTHING of
    agent A's lessons — different state_dir roots a different ledger entirely."""
    agent_a = _agent(tmp_path / "agent_a", name="alice")
    agent_b = _agent(tmp_path / "agent_b", name="bob")
    a_secret = "ALICE-ONLY: prefer pheromone trails over message queues"
    _seed_lesson(agent_a, a_secret)

    react_b = _capture_react_loop(agent_b, summary="bob surveyed")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DHARMA_PERSISTENT_KERNEL_GOVERNANCE", "1")
        mp.setenv("DHARMA_PERSISTENT_KERNEL_LESSONS_READBACK", "1")
        result_b = asyncio.run(agent_b.wake(injected_task="bob's task"))

    captured_b = _captured_input(react_b)
    assert a_secret not in captured_b
    assert "Prior lessons:" not in captured_b
    assert "lessons_injected" not in result_b
    assert result_b["success"] is True


def test_shared_store_isolates_by_agent_uid_namespace(tmp_path):
    """Even when A and B share ONE store dir, B reads its OWN agent-scoped
    namespace (``agent:bob:lessons``) and never sees alice's namespace rows."""
    shared = tmp_path / "shared"
    agent_a = _agent(tmp_path / "agent_a", name="alice")
    agent_b = _agent(tmp_path / "agent_b", name="bob")

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DHARMA_PERSISTENT_KERNEL_STORE_DIR", str(shared))
        mp.setenv("DHARMA_PERSISTENT_KERNEL_GOVERNANCE", "1")
        mp.setenv("DHARMA_PERSISTENT_KERNEL_LESSONS_READBACK", "1")

        a_secret = "ALICE-ONLY shared-store lesson"
        _seed_lesson(agent_a, a_secret)
        b_lesson = "BOB-OWN shared-store lesson"
        _seed_lesson(agent_b, b_lesson)

        react_b = _capture_react_loop(agent_b, summary="bob surveyed")
        result_b = asyncio.run(agent_b.wake(injected_task="bob's task"))

    captured_b = _captured_input(react_b)
    assert b_lesson in captured_b          # bob reads bob's namespace
    assert a_secret not in captured_b      # never alice's namespace
    assert result_b["success"] is True


# -- adversarial: tamper -> corrupted row skipped, not injected --------------


def test_tampered_ledger_row_is_skipped_not_injected(tmp_path):
    """A corrupted lessons-ledger row (mutated delta_text, broken entry_hash) is
    SKIPPED by the read accessor; a clean row is still read. The forged content
    never reaches the ReAct input."""
    agent = _agent(tmp_path / "agent", name="conductor_tamper")
    good_lesson = "GOOD: verified hash-chained lesson"
    path = _seed_lesson(agent, good_lesson)
    _seed_lesson(agent, "second clean lesson to keep the chain non-trivial")

    # Tamper: rewrite the FIRST row's delta_text without recomputing entry_hash,
    # so its entry_hash no longer verifies.
    import json

    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    rows[0]["delta_text"] = "FORGED: do something malicious"
    path.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")

    react = _capture_react_loop(agent, summary="surveyed")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DHARMA_PERSISTENT_KERNEL_GOVERNANCE", "1")
        mp.setenv("DHARMA_PERSISTENT_KERNEL_LESSONS_READBACK", "1")
        result_info = asyncio.run(agent.wake(injected_task="do the work"))

    captured = _captured_input(react)
    assert "FORGED" not in captured          # tampered row skipped
    assert "second clean lesson" in captured  # clean row still read
    assert result_info["success"] is True


def test_recent_valid_lessons_skips_tampered_row_directly(tmp_path):
    """Unit-level proof on the store accessor: a row whose entry_hash no longer
    matches its payload is dropped; surviving rows are returned in order."""
    store = KernelLessonStore(tmp_path / "k")
    ns = "agent:unit:lessons"
    store.append_lesson("unit", ns, "row one", run_id="r1")
    store.append_lesson("unit", ns, "row two", run_id="r2")

    import json

    path = store.namespace_path(ns)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    rows[0]["delta_text"] = "TAMPERED"  # entry_hash now stale
    path.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")

    valid = store.recent_valid_lessons(ns, limit=5)
    texts = [r.delta_text for r in valid]
    assert "TAMPERED" not in texts
    assert "row two" in texts


# -- adversarial: best-effort -> read failure cannot break the wake ----------


def test_read_failure_lets_agent_complete_with_no_lessons(tmp_path, monkeypatch):
    """If the lessons read raises, the agent proceeds with its NORMAL task and NO
    injected lessons — read-back can never block or break the wake."""
    agent = _agent(tmp_path / "agent", name="conductor_fail")
    _seed_lesson(agent, "a lesson that will fail to load")

    def _boom(*_a, **_k):
        raise RuntimeError("simulated ledger read failure")

    # Force the read accessor to explode; the best-effort wrapper must swallow it.
    monkeypatch.setattr(
        "dharma_swarm.operator_core.living_agent_kernel_lessons.KernelLessonStore.recent_valid_lessons",
        _boom,
    )

    react = _capture_react_loop(agent, summary="survived the failure")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DHARMA_PERSISTENT_KERNEL_GOVERNANCE", "1")
        mp.setenv("DHARMA_PERSISTENT_KERNEL_LESSONS_READBACK", "1")
        result_info = asyncio.run(agent.wake(injected_task="resilient task"))

    captured = _captured_input(react)
    assert captured == "resilient task"          # normal task, no preamble
    assert "Prior lessons:" not in captured
    assert "lessons_injected" not in result_info
    assert result_info["success"] is True


def test_no_ledger_yields_no_preamble_and_completes(tmp_path):
    """No lessons ever written -> read-back yields nothing, agent completes,
    input is byte-identical to task_text."""
    agent = _agent(tmp_path / "agent", name="conductor_empty")
    react = _capture_react_loop(agent, summary="fresh agent, no history")

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DHARMA_PERSISTENT_KERNEL_GOVERNANCE", "1")
        mp.setenv("DHARMA_PERSISTENT_KERNEL_LESSONS_READBACK", "1")
        result_info = asyncio.run(agent.wake(injected_task="first ever task"))

    assert _captured_input(react) == "first ever task"
    assert "lessons_injected" not in result_info
    assert result_info["success"] is True
