from __future__ import annotations

from pathlib import Path

from dharma_swarm.memory_common import (
    create_memory_common_cron_job,
    memory_common_cron_run_fn,
    render_agent_memory_pack,
    render_memory_common_command,
    render_memory_common_status,
    render_memory_query,
    render_memory_schedule,
)
from dharma_swarm.vector_store import VectorStore


def _seed_state(tmp_path: Path) -> Path:
    state_dir = tmp_path / ".dharma"
    store = VectorStore(state_dir=state_dir, dim=32)
    store.upsert(
        "Mixture-of-Experts routes tokens through expert subnetworks.",
        source="text_file:wiki-concepts-mixture-of-experts",
        layer="source_file",
        metadata={"source_file": "wiki/concepts/mixture-of-experts.md"},
    )
    return state_dir


def _redirect_cron_storage(tmp_path: Path, monkeypatch) -> None:
    from dharma_swarm import cron_scheduler

    cron_dir = tmp_path / "cron"
    monkeypatch.setattr(cron_scheduler, "DHARMA_DIR", tmp_path)
    monkeypatch.setattr(cron_scheduler, "CRON_DIR", cron_dir)
    monkeypatch.setattr(cron_scheduler, "JOBS_FILE", cron_dir / "jobs.json")
    monkeypatch.setattr(cron_scheduler, "OUTPUT_DIR", cron_dir / "output")
    monkeypatch.setattr(cron_scheduler, "LOCK_FILE", cron_dir / ".tick.lock")


def test_memory_common_status_reports_vector_db(tmp_path: Path) -> None:
    state_dir = _seed_state(tmp_path)

    rendered = render_memory_common_status(state_dir=state_dir)

    assert "# Memory Common" in rendered
    assert "Vector DB: `present`" in rendered


def test_memory_common_query_uses_governed_retrieval(tmp_path: Path) -> None:
    state_dir = _seed_state(tmp_path)

    rendered = render_memory_query(
        "Mixture-of-Experts expert routing",
        state_dir=state_dir,
        top_k=1,
    )

    assert "# Memory Query" in rendered
    assert "wiki-concepts-mixture-of-experts" in rendered


def test_memory_common_pack_is_agent_handoff(tmp_path: Path) -> None:
    state_dir = _seed_state(tmp_path)

    rendered = render_agent_memory_pack(
        "explain Mixture-of-Experts",
        state_dir=state_dir,
        top_k=1,
    )

    assert "# Memory Common Pack" in rendered
    assert "Agent contract:" in rendered
    assert "wiki-concepts-mixture-of-experts" in rendered


def test_memory_common_command_dispatches_query(tmp_path: Path) -> None:
    state_dir = _seed_state(tmp_path)

    rendered = render_memory_common_command(
        "query Mixture-of-Experts expert routing",
        state_dir=state_dir,
        top_k=1,
    )

    assert "# Memory Query" in rendered
    assert "wiki-concepts-mixture-of-experts" in rendered


def test_memory_common_command_dispatches_metabolism(monkeypatch, tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    monkeypatch.setattr(
        "dharma_swarm.memory_common.render_memory_metabolism",
        lambda **kwargs: "metabolism rendered",
        raising=True,
    )

    rendered = render_memory_common_command("metabolize", state_dir=state_dir)

    assert rendered == "metabolism rendered"


def test_memory_common_schedule_registers_idempotent_cron_job(monkeypatch, tmp_path: Path) -> None:
    _redirect_cron_storage(tmp_path, monkeypatch)

    job1 = create_memory_common_cron_job(schedule="every 12h", top_k=7)
    job2 = create_memory_common_cron_job(schedule="every 6h", top_k=3)

    assert job2["id"] == job1["id"]
    assert job1["name"] == "memory-common-metabolism"
    assert job1["handler"] == "memory_common_metabolism"
    assert job1["top_k"] == 7
    assert job1["schedule_display"] == "every 720m"


def test_memory_common_command_dispatches_schedule(monkeypatch, tmp_path: Path) -> None:
    _redirect_cron_storage(tmp_path, monkeypatch)

    rendered = render_memory_common_command("schedule every 12h", top_k=4)

    assert "# Memory Common Schedule" in rendered
    assert "memory-common-metabolism" in rendered
    assert "memory_common_metabolism" in rendered


def test_memory_common_schedule_renderer(monkeypatch, tmp_path: Path) -> None:
    _redirect_cron_storage(tmp_path, monkeypatch)

    rendered = render_memory_schedule(schedule="every 24h", top_k=10)

    assert "# Memory Common Schedule" in rendered
    assert "Requires the existing cron daemon" in rendered


def test_memory_common_cron_run_fn_uses_metabolism_receipt(monkeypatch, tmp_path: Path) -> None:
    receipt = {
        "passed": True,
        "receipt_path": str(tmp_path / "receipt.json"),
        "ingest": {"discovered_files": 2},
        "wiki_gate": {"score": 100},
        "system_gate": {"score": 100, "max_score": 100},
    }

    def fake_run_memory_metabolism(**kwargs):
        assert kwargs["state_dir"] == tmp_path / ".dharma"
        assert kwargs["top_k"] == 3
        return receipt

    monkeypatch.setattr(
        "dharma_swarm.memory_common.run_memory_metabolism",
        fake_run_memory_metabolism,
        raising=True,
    )

    ok, output, error = memory_common_cron_run_fn(
        {"state_dir": str(tmp_path / ".dharma"), "top_k": "3"}
    )

    assert ok is True
    assert error is None
    assert "# Memory Metabolism" in output
    assert "Passed: `True`" in output


def test_memory_common_cron_run_fn_fails_when_gate_receipt_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "dharma_swarm.memory_common.run_memory_metabolism",
        lambda **_: {
            "passed": False,
            "receipt_path": "/tmp/receipt.json",
            "ingest": {"discovered_files": 1},
            "wiki_gate": {"score": 80},
            "system_gate": {"score": 90, "max_score": 100},
        },
        raising=True,
    )

    ok, output, error = memory_common_cron_run_fn({"top_k": 1})

    assert ok is False
    assert "Passed: `False`" in output
    assert error == "Memory Common metabolism gate failed"
