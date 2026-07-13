#!/usr/bin/env python3
"""Audit-only, network-denied counterexamples for Dharma at the frozen SHA.

Run from a clean checkout of EXPECTED_SHA with that checkout first on
PYTHONPATH.  The probes write only to temporary directories and use fixture
credentials/endpoints.  Exit zero means every named negative behavior was
observed; it is not a product-readiness signal.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from unittest.mock import patch


EXPECTED_SHA = "c14b950bc5009f2200d9425155010be508ead981"


def _assert_frozen_checkout() -> None:
    observed = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, cwd=Path.cwd()
    ).strip()
    if observed != EXPECTED_SHA:
        raise RuntimeError(f"expected {EXPECTED_SHA}, observed {observed}")


def persistence_lost_update() -> dict[str, object]:
    from dharma_swarm.graph.persistence import GraphPersistenceKernel
    from dharma_swarm.graph.types import RunCheckpoint

    with tempfile.TemporaryDirectory(prefix="dharma-audit-persist-") as raw:
        root = Path(raw)
        left = GraphPersistenceKernel(root)
        right = GraphPersistenceKernel(root)
        barrier = Barrier(2)

        def synchronize_read(kernel: GraphPersistenceKernel) -> None:
            original = kernel._read_thread

            def wrapped(thread_id: str, *, create: bool = True):
                state = original(thread_id, create=create)
                barrier.wait(timeout=5)
                return state

            kernel._read_thread = wrapped  # type: ignore[method-assign]

        synchronize_read(left)
        synchronize_read(right)

        def write(kernel: GraphPersistenceKernel, suffix: str) -> None:
            checkpoint = RunCheckpoint(
                graph_run_id=f"run-{suffix}",
                graph_id="audit-race",
                superstep=0,
                state_digest=suffix * 64,
                channels={"x": {"value": suffix, "version": 1}},
                versions_seen={},
            )
            kernel.put_run_checkpoint(
                "shared-thread", checkpoint, checkpoint_id=f"cp-{suffix}"
            )

        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(write, left, "a"), pool.submit(write, right, "b")]
            for future in futures:
                try:
                    future.result(timeout=10)
                except Exception as exc:  # pragma: no cover - diagnostic path
                    errors.append(type(exc).__name__)

        persisted = GraphPersistenceKernel(root).get_state_history("shared-thread")
        reproduced = not errors and len(persisted) == 1
        return {
            "reproduced": reproduced,
            "attempted": 2,
            "persisted": len(persisted),
            "writer_errors": errors,
        }


def checkpoint_fork_alias() -> dict[str, object]:
    from dharma_swarm.graph.types import RunCheckpoint

    channels = {"x": {"value": 1, "version": 1}}
    seen = {"node": {"x": 1}}
    parent = RunCheckpoint("parent", "audit-fork", 0, "a" * 64, channels, seen)
    child = parent.fork("child")
    child.channels["x"]["value"] = 99  # type: ignore[index]
    child.versions_seen["node"]["x"] = 99  # type: ignore[index]
    reproduced = (
        parent.channels is child.channels
        and parent.versions_seen is child.versions_seen
        and parent.channels["x"]["value"] == 99
    )
    return {"reproduced": reproduced, "parent_value_after_child_mutation": 99}


async def invalid_pending_write_poison() -> dict[str, object]:
    from dharma_swarm.graph import END, START, GraphBuilder, LastValueChannel
    from dharma_swarm.graph.persistence import GraphPersistenceKernel

    with tempfile.TemporaryDirectory(prefix="dharma-audit-pending-") as raw:
        compiled = (
            GraphBuilder("audit-pending")
            .add_channel("x", LastValueChannel)
            .add_node("a", lambda state: {"x": 1})
            .add_node("b", lambda state: {"x": 2})
            .add_edge(START, "a")
            .add_edge(START, "b")
            .add_edge("a", END)
            .add_edge("b", END)
            .compile()
        )
        kernel = GraphPersistenceKernel(Path(raw))
        failures: list[str] = []
        try:
            await compiled.invoke(
                {}, graph_run_id="run-pending", persistence=kernel,
                thread_id="thread-pending"
            )
        except Exception as exc:
            failures.append(type(exc).__name__)
        before = kernel.recover_pending_writes("thread-pending")
        try:
            await compiled.invoke(
                input=None, persistence=kernel, thread_id="thread-pending"
            )
        except Exception as exc:
            failures.append(type(exc).__name__)
        after = kernel.recover_pending_writes("thread-pending")
        reproduced = len(failures) == 2 and len(before) == len(after) == 1
        return {
            "reproduced": reproduced,
            "failure_types": failures,
            "pending_before_resume": len(before),
            "pending_after_resume": len(after),
        }


def parity_judge_identity_forge() -> dict[str, object]:
    from scripts.governance import dharmagraph_parity_gauntlet as cli

    core = {"score": "31.00"}
    builder = {
        "score": {"earned": "31.00"},
        "stable_core": core,
        "stable_digest": cli.stable_digest(core),
    }
    builder["digest"] = cli._receipt_digest(builder)
    judge = {
        "score": {"earned": "31.00"},
        "stable_core": core,
        "stable_digest": builder["stable_digest"],
        "judge": {
            "judge_id": "attacker-controlled-id",
            "signature": "forged-fixture",
            "builder_receipt_digest": builder["digest"],
            "reconciliation": "MATCH",
        },
    }
    judge["digest"] = cli._receipt_digest(judge)
    findings = cli._judge_findings(builder, judge)
    return {"reproduced": findings == [], "findings": findings}


def import_only_partial_credit() -> dict[str, object]:
    from tests.oracle_support.dharmagraph_gauntlet import _finalize_rows

    capabilities = {
        "FIXTURE": {
            "facets": {
                "importable_shape": {"status": "partial", "evidence": [{}]},
                "behavior": {"status": "missing", "evidence": [{}]},
            }
        }
    }
    _finalize_rows(capabilities)
    row = capabilities["FIXTURE"]
    return {
        "reproduced": row["points"] == 1,
        "points": row["points"],
        "verdict": row["verdict"],
        "behavior_status": row["facets"]["behavior"]["status"],
    }


async def status_only_receipt_promotion() -> dict[str, object]:
    from dharma_swarm.graph.reconciler import GraphReconciler
    from dharma_swarm.runtime_state import RuntimeStateStore

    now = datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory(prefix="dharma-audit-reconcile-") as raw:
        store = RuntimeStateStore(Path(raw) / "runtime.db")
        store.init_db_sync()
        with sqlite3.connect(store.db_path) as db:
            db.execute(
                "INSERT INTO delegation_runs (run_id, task_id, claim_id, assigned_to,"
                " status, started_at, metadata_json, receipt_json)"
                " VALUES (?, ?, ?, 'agent-1', 'running', ?, '{}', ?)",
                (
                    "run-status-only", "task-1", "claim-status-only",
                    (now - timedelta(minutes=10)).isoformat(),
                    json.dumps({"status": "ok", "task_id": "task-1"}),
                ),
            )
            db.execute(
                "INSERT INTO task_claims (claim_id, task_id, agent_id, status,"
                " claimed_at, acked_at, retry_count)"
                " VALUES (?, ?, 'agent-1', 'running', ?, ?, 0)",
                (
                    "claim-status-only", "task-1",
                    (now - timedelta(minutes=10)).isoformat(),
                    (now - timedelta(minutes=9)).isoformat(),
                ),
            )
            db.commit()
        report = await GraphReconciler(store).reconcile(now=now)
        with sqlite3.connect(store.db_path) as db:
            status = db.execute(
                "SELECT status FROM delegation_runs WHERE run_id = ?",
                ("run-status-only",),
            ).fetchone()[0]
        return {
            "reproduced": status == "completed",
            "run_status": status,
            "completed_from_receipt": report.completed_from_receipt,
        }


async def stigmergy_cross_instance_lost_append() -> dict[str, object]:
    from dharma_swarm.stigmergy import StigmergicMark, StigmergyStore

    with tempfile.TemporaryDirectory(prefix="dharma-audit-stigmergy-") as raw:
        root = Path(raw)
        rewriter = StigmergyStore(root)
        appender = StigmergyStore(root)
        old = StigmergicMark(
            agent="audit-old", file_path="old", observation="old fixture",
            timestamp=datetime.now(timezone.utc) - timedelta(days=10)
        )
        new = StigmergicMark(
            agent="audit-new", file_path="new", observation="new fixture"
        )
        await rewriter.leave_mark(old)
        loaded = asyncio.Event()
        resume = asyncio.Event()
        original = rewriter._load_marks

        async def paused_load():
            marks = await original()
            loaded.set()
            await resume.wait()
            return marks

        rewriter._load_marks = paused_load  # type: ignore[method-assign]
        decay_task = asyncio.create_task(rewriter.decay(max_age_hours=1))
        await loaded.wait()
        await appender.leave_mark(new)
        resume.set()
        await decay_task
        surviving_ids = {mark.id for mark in await appender.read_marks(limit=20)}
        return {
            "reproduced": new.id not in surviving_ids,
            "new_mark_survived": new.id in surviving_ids,
        }


async def failed_prerequisite_ready() -> dict[str, object]:
    from dharma_swarm.models import TaskStatus
    from dharma_swarm.task_board import TaskBoard

    with tempfile.TemporaryDirectory(prefix="dharma-audit-taskboard-") as raw:
        board = TaskBoard(Path(raw) / "tasks.db")
        await board.init_db()
        parent = await board.create("parent")
        child = await board.create("child", depends_on=[parent.id])
        await board.assign(parent.id, "fixture-agent")
        await board.start(parent.id)
        await board._set_status(parent.id, TaskStatus.FAILED, result="fixture")
        ready_ids = {task.id for task in await board.get_ready_tasks()}
        return {"reproduced": child.id in ready_ids, "child_ready": child.id in ready_ids}


def provider_base_url_discarded() -> dict[str, object]:
    import openai
    from dharma_swarm.runtime_provider import (
        ProviderType,
        create_runtime_provider,
        resolve_runtime_provider_config,
    )

    requested = "https://fixture-proxy.invalid/v1"
    observed: dict[str, object] = {}

    class FakeClient:
        def __init__(self, **kwargs):
            observed.update(kwargs)

    config = resolve_runtime_provider_config(
        ProviderType.GROQ,
        api_key="fixture-token-not-live",
        base_url=requested,
        env={},
    )
    provider = create_runtime_provider(config)
    with patch.object(openai, "AsyncOpenAI", FakeClient):
        provider._client_or_raise()
    actual = str(observed.get("base_url"))
    return {
        "reproduced": config.base_url == requested and actual != requested,
        "resolved_base_url": config.base_url,
        "client_base_url": actual,
    }


def logical_provider_pseudodiversity() -> dict[str, object]:
    from dharma_swarm.runtime_provider import ProviderType, resolve_runtime_provider_config

    anthropic = resolve_runtime_provider_config(ProviderType.ANTHROPIC, env={})
    claude_code = resolve_runtime_provider_config(ProviderType.CLAUDE_CODE, env={})
    same = anthropic.provider == claude_code.provider == ProviderType.CLAUDE_CODE
    return {
        "reproduced": same,
        "anthropic_resolves_to": anthropic.provider.value,
        "claude_code_resolves_to": claude_code.provider.value,
    }


def websocket_auth_bypass() -> dict[str, object]:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.main import BearerAuthMiddleware
    from api.routers.chat import ws_router

    fixture_app = FastAPI()
    fixture_app.add_middleware(BearerAuthMiddleware)
    fixture_app.include_router(ws_router)
    with patch.dict(os.environ, {"DASHBOARD_API_KEY": "fixture-token-not-live"}):
        with TestClient(fixture_app) as client:
            with client.websocket_connect("/ws/chat/session/audit-no-token") as socket:
                snapshot = socket.receive_json()
    return {
        "reproduced": snapshot.get("event") == "chat_snapshot",
        "received_event": snapshot.get("event"),
    }


def signal_bus_mutable_alias() -> dict[str, object]:
    from dharma_swarm.signal_bus import SignalBus

    bus = SignalBus()
    bus.subscribe("AUDIT", lambda event: event.update(mutated_by_subscriber=True))
    bus.emit({"type": "AUDIT", "value": 1})
    queued = bus.drain()[0]
    return {
        "reproduced": queued.get("mutated_by_subscriber") is True,
        "queued_value": queued,
    }


def main() -> int:
    _assert_frozen_checkout()
    probes = (
        ("persistence_lost_update", persistence_lost_update),
        ("checkpoint_fork_alias", checkpoint_fork_alias),
        ("invalid_pending_write_poison", invalid_pending_write_poison),
        ("parity_judge_identity_forge", parity_judge_identity_forge),
        ("import_only_partial_credit", import_only_partial_credit),
        ("status_only_receipt_promotion", status_only_receipt_promotion),
        ("stigmergy_cross_instance_lost_append", stigmergy_cross_instance_lost_append),
        ("failed_prerequisite_ready", failed_prerequisite_ready),
        ("provider_base_url_discarded", provider_base_url_discarded),
        ("logical_provider_pseudodiversity", logical_provider_pseudodiversity),
        ("websocket_auth_bypass", websocket_auth_bypass),
        ("signal_bus_mutable_alias", signal_bus_mutable_alias),
    )
    results: dict[str, dict[str, object]] = {}
    for name, function in probes:
        value = function()
        if asyncio.iscoroutine(value):
            value = asyncio.run(value)
        results[name] = value
        print(json.dumps({"probe": name, **value}, sort_keys=True))
    all_reproduced = all(bool(item.get("reproduced")) for item in results.values())
    print(json.dumps({"all_reproduced": all_reproduced, "count": len(results)}))
    return 0 if all_reproduced else 1


if __name__ == "__main__":
    raise SystemExit(main())
