#!/usr/bin/env python3
"""
A2A end-to-end round-trip probe — perplexity-computer.

Goal: surface what is actually wired vs not in the A2A stack, by attempting one
real submit → dispatch → response cycle against the in-process A2AServer with
perplexity-computer's capability set.

This is a probe, not a test. Output is structured so we can read it as a
truth-surface check on "does end-to-end A2A work right now."
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

# Repo root on path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from dharma_swarm.a2a import (  # noqa: E402
    A2AMessage,
    A2APart,
    A2AServer,
    A2ATask,
    A2ATaskStatus,
)
from dharma_swarm.a2a.node_registry import NodeRegistry, RemoteNode  # noqa: E402


REPORT: dict = {
    "probe": "a2a_roundtrip_perplexity_computer",
    "steps": [],
    "verdict": None,
}


def step(name: str, ok: bool, detail: str = "", **extra) -> None:
    REPORT["steps"].append(
        {"name": name, "ok": ok, "detail": detail, **extra}
    )


def synthesis_handler(task: A2ATask) -> A2ATask:
    """Stand-in synthesis handler for perplexity-computer's `synthesis` capability.

    Echoes the request with a deterministic synthesis prefix so the wire
    contract is observable end-to-end.
    """
    inbound = task.history[-1].parts[0].content if task.history else ""
    task.history.append(
        A2AMessage(
            role="agent",
            parts=[A2APart.text(f"[perplexity-computer synthesis] received: {inbound}")],
        )
    )
    task.result = f"synthesis-of: {inbound}"
    task.status = A2ATaskStatus.COMPLETED
    return task


def main() -> int:
    # ── Step 1 ── Instantiate A2AServer
    try:
        server = A2AServer(persist=False)
        step("instantiate_a2a_server", True, "in-process A2AServer constructed")
    except Exception as exc:
        step("instantiate_a2a_server", False, repr(exc), trace=traceback.format_exc())
        return _emit(1)

    # ── Step 2 ── Register perplexity-computer's capability handler
    try:
        server.register_handler("synthesis", synthesis_handler)
        step(
            "register_handler",
            True,
            "synthesis handler registered for perplexity-computer",
        )
    except Exception as exc:
        step("register_handler", False, repr(exc), trace=traceback.format_exc())
        return _emit(1)

    # ── Step 3 ── NodeRegistry: register perplexity-computer as a node
    try:
        registry = NodeRegistry(nodes_path=REPO / "tmp_a2a_probe_nodes.json")
        registry.register(
            RemoteNode(
                node_id="perplexity-computer",
                endpoint="local://in-process",
                status="online",  # in-process: skip health-check, manually mark online
                capabilities=[
                    "synthesis",
                    "verdict_reconciliation",
                    "persistent_agent_index",
                ],
            )
        )
        nodes = registry.list_all()
        step(
            "node_registry_register",
            True,
            f"{len(nodes)} node(s) registered",
            nodes=[n.to_dict() for n in nodes],
        )
    except Exception as exc:
        step("node_registry_register", False, repr(exc), trace=traceback.format_exc())

    # ── Step 4 ── Discovery by capability
    try:
        found = registry.discover("synthesis")
        ok = any(n.node_id == "perplexity-computer" for n in found)
        step(
            "node_registry_discover",
            ok,
            f"discover('synthesis') -> {[n.node_id for n in found]}",
        )
    except Exception as exc:
        step("node_registry_discover", False, repr(exc), trace=traceback.format_exc())

    # ── Step 5 ── Submit a task as another agent → perplexity-computer
    try:
        task = A2ATask(
            from_agent="hermes",
            to_agent="perplexity-computer",
            capability="synthesis",
            history=[
                A2AMessage(
                    role="user",
                    parts=[A2APart.text("smoke test — enumerate registered nodes")],
                )
            ],
            trace_id="trc_probe_roundtrip_001",
        )
        submitted = server.submit(task)
        ok = submitted.status == A2ATaskStatus.COMPLETED and bool(submitted.result)
        step(
            "submit_and_dispatch",
            ok,
            f"status={submitted.status.value} result={submitted.result!r}",
            trace_id=submitted.trace_id,
            history_len=len(submitted.history),
        )
    except Exception as exc:
        step("submit_and_dispatch", False, repr(exc), trace=traceback.format_exc())
        return _emit(1)

    # ── Step 6 ── Verify task store / retrieve
    try:
        fetched = server.get_task(submitted.id)
        ok = fetched is not None and fetched.id == submitted.id
        step(
            "get_task",
            ok,
            f"get_task returned {fetched.id if fetched else None}",
        )
    except Exception as exc:
        step("get_task", False, repr(exc), trace=traceback.format_exc())

    # ── Step 7 ── Verify trace_id inheritance + lineage
    try:
        ok = submitted.trace_id == "trc_probe_roundtrip_001"
        step(
            "trace_id_preserved",
            ok,
            f"submitted.trace_id={submitted.trace_id}",
        )
    except Exception as exc:
        step("trace_id_preserved", False, repr(exc), trace=traceback.format_exc())

    # ── Verdict ──
    fails = [s for s in REPORT["steps"] if not s["ok"]]
    REPORT["verdict"] = "PASS" if not fails else f"FAIL ({len(fails)} step(s))"
    return _emit(0 if not fails else 2)


def _emit(rc: int) -> int:
    print(json.dumps(REPORT, indent=2, default=str))
    # Cleanup
    try:
        (REPO / "tmp_a2a_probe_nodes.json").unlink(missing_ok=True)
    except Exception:
        pass
    return rc


if __name__ == "__main__":
    sys.exit(main())
