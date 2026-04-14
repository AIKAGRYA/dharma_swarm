"""Tests for agent_direct — directive write + watcher loop."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dharma_swarm.agent_direct import scan_once, watcher_loop, write_directive
from dharma_swarm.campaigns import create_campaign
from dharma_swarm.conductors import register, unregister


class FakeRole:
    value = "conductor"


class FakeQueue:
    def __init__(self, sink: list[str]) -> None:
        self._sink = sink

    def qsize(self) -> int:
        return len(self._sink)


class FakeAgent:
    def __init__(self, name: str) -> None:
        self.name = name
        self.role = FakeRole()
        self.model = "fake-model"
        self.received: list[str] = []
        self._task_queue = FakeQueue(self.received)

    async def accept_task(self, task: str) -> None:
        self.received.append(task)


class FailingAgent(FakeAgent):
    async def accept_task(self, task: str) -> None:  # noqa: ARG002
        raise RuntimeError("boom")


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "directives", tmp_path / "witness"


@pytest.fixture(autouse=True)
async def _clean_registry():
    yield
    from dharma_swarm.conductors import ACTIVE_CONDUCTORS
    ACTIVE_CONDUCTORS.clear()


async def test_write_directive_creates_structured_record(dirs: tuple[Path, Path]) -> None:
    droot, _ = dirs
    path = write_directive("conductor_a", "Do X", directives_dir=droot)
    assert path.exists()
    rec = json.loads(path.read_text())
    assert rec["agent"] == "conductor_a"
    assert rec["task"] == "Do X"
    assert rec["priority"] == "normal"
    assert rec["directive_id"]
    assert rec["created"]


async def test_scan_once_dispatches_to_registered_agent(
    dirs: tuple[Path, Path],
) -> None:
    droot, wdir = dirs
    agent = FakeAgent("conductor_a")
    await register("conductor_a", agent)

    write_directive("conductor_a", "Task 1", directives_dir=droot)
    write_directive("conductor_a", "Task 2", directives_dir=droot)

    n = await scan_once(directives_dir=droot, witness_dir=wdir)
    assert n == 2
    assert sorted(agent.received) == ["Task 1", "Task 2"]

    # Witness log written
    wlog = wdir / "directives_conductor_a.jsonl"
    assert wlog.exists()
    assert len(wlog.read_text().splitlines()) == 2

    # Directives dir empty
    assert not any(droot.glob("*.json"))


async def test_scan_once_unmatched_agent_goes_to_quarantine(
    dirs: tuple[Path, Path],
) -> None:
    droot, wdir = dirs
    write_directive("ghost_agent", "Task", directives_dir=droot)
    n = await scan_once(directives_dir=droot, witness_dir=wdir)
    assert n == 0

    unmatched = list((droot / "_unmatched").iterdir())
    assert len(unmatched) == 1
    rec = json.loads(unmatched[0].read_text())
    assert "conductor_not_registered" in rec["unmatched_reason"]
    assert rec["unmatched_at"]


async def test_scan_once_malformed_json_goes_to_quarantine(
    dirs: tuple[Path, Path],
) -> None:
    droot, wdir = dirs
    droot.mkdir(parents=True, exist_ok=True)
    (droot / "bad.json").write_text("{not valid")

    n = await scan_once(directives_dir=droot, witness_dir=wdir)
    assert n == 0
    assert not (droot / "bad.json").exists()
    assert (droot / "_unmatched" / "bad.json").exists()


async def test_scan_once_accept_task_failure_requeues_to_unmatched(
    dirs: tuple[Path, Path],
) -> None:
    droot, wdir = dirs
    await register("conductor_fail", FailingAgent("conductor_fail"))
    write_directive("conductor_fail", "won't take", directives_dir=droot)

    n = await scan_once(directives_dir=droot, witness_dir=wdir)
    assert n == 0
    unmatched = list((droot / "_unmatched").iterdir())
    assert len(unmatched) == 1
    rec = json.loads(unmatched[0].read_text())
    assert "accept_task_failed" in rec["unmatched_reason"]


async def test_scan_once_expired_directive_moved_to_unmatched(
    dirs: tuple[Path, Path],
) -> None:
    droot, wdir = dirs
    await register("conductor_a", FakeAgent("conductor_a"))
    path = write_directive("conductor_a", "Old", directives_dir=droot)
    # Backdate the record to 8 days ago
    rec = json.loads(path.read_text())
    rec["created"] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    path.write_text(json.dumps(rec))

    n = await scan_once(directives_dir=droot, witness_dir=wdir)
    assert n == 0
    unmatched = list((droot / "_unmatched").iterdir())
    assert any(
        json.loads(p.read_text()).get("unmatched_reason") == "expired"
        for p in unmatched
    )


async def test_scan_once_campaign_prefix_resolved(
    dirs: tuple[Path, Path], tmp_path: Path, monkeypatch,
) -> None:
    droot, wdir = dirs
    meta = tmp_path / "meta"
    meta.mkdir()
    monkeypatch.setattr(
        "dharma_swarm.campaigns._DEFAULT_META_DIR", meta,
    )
    create_campaign("neurips", "artifact_publication", ["conductor_a"],
                    title="NeurIPS", meta_dir=meta)

    agent = FakeAgent("conductor_a")
    await register("conductor_a", agent)
    write_directive(
        "conductor_a", "draft section 2",
        campaign_id="neurips", directives_dir=droot,
    )
    n = await scan_once(directives_dir=droot, witness_dir=wdir)
    assert n == 1
    assert agent.received == ["CAMPAIGN: neurips — draft section 2"]


async def test_scan_once_missing_agent_field_moves_to_unmatched(
    dirs: tuple[Path, Path],
) -> None:
    droot, wdir = dirs
    droot.mkdir(parents=True, exist_ok=True)
    (droot / "x.json").write_text(json.dumps({"task": "only", "created": "2026-04-14T00:00:00Z"}))
    n = await scan_once(directives_dir=droot, witness_dir=wdir)
    assert n == 0
    unmatched = list((droot / "_unmatched").iterdir())
    assert unmatched
    assert "missing_agent_or_task" in json.loads(unmatched[0].read_text())["unmatched_reason"]


async def test_scan_once_empty_dir_returns_zero(dirs: tuple[Path, Path]) -> None:
    droot, wdir = dirs
    n = await scan_once(directives_dir=droot, witness_dir=wdir)
    assert n == 0


async def test_watcher_loop_stops_on_shutdown(dirs: tuple[Path, Path]) -> None:
    droot, wdir = dirs
    shutdown = asyncio.Event()
    task = asyncio.create_task(
        watcher_loop(shutdown, directives_dir=droot, poll_interval=0.05, witness_dir=wdir)
    )
    await asyncio.sleep(0.1)
    shutdown.set()
    await asyncio.wait_for(task, timeout=1.0)
    assert task.done()
