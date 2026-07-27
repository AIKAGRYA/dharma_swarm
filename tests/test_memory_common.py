from __future__ import annotations

import json
import os
from pathlib import Path

from dharma_swarm.memory_common import (
    _latest_gate_score,
    create_memory_common_cron_job,
    memory_common_cron_run_fn,
    memory_common_summary,
    render_agent_memory_pack,
    render_memory_common_command,
    render_memory_common_status,
    render_memory_query,
    render_memory_schedule,
    run_memory_metabolism,
)
from dharma_swarm.vector_store import VectorStore


class _StubGateReceipt:
    def __init__(self, payload: dict, *, passed: bool = True) -> None:
        self._payload = payload
        self.passed = passed

    def to_json(self) -> dict:
        return self._payload


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
    # Rescheduling refreshes the stored row instead of returning it stale.
    assert job2["top_k"] == 3
    assert job2["schedule_display"] == "every 360m"


def test_memory_common_schedule_refreshes_disabled_job_and_state_dir(
    monkeypatch, tmp_path: Path
) -> None:
    from dharma_swarm.cron_scheduler import load_jobs, save_jobs

    _redirect_cron_storage(tmp_path, monkeypatch)
    state_dir = tmp_path / "custom-state"

    created = create_memory_common_cron_job(schedule="every 24h", top_k=10, state_dir=state_dir)
    assert created["state_dir"] == str(state_dir)

    jobs = load_jobs()
    jobs[0]["enabled"] = False
    save_jobs(jobs)

    other_state = tmp_path / "other-state"
    refreshed = create_memory_common_cron_job(
        schedule="every 6h", top_k=4, state_dir=other_state
    )

    assert refreshed["id"] == created["id"]
    assert refreshed["enabled"] is True
    assert refreshed["top_k"] == 4
    assert refreshed["state_dir"] == str(other_state)
    persisted = load_jobs()[0]
    assert persisted["enabled"] is True
    assert persisted["schedule_display"] == "every 360m"
    assert persisted["state_dir"] == str(other_state)


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


def test_run_memory_metabolism_receipts_land_under_state_dir(monkeypatch, tmp_path: Path) -> None:
    import scripts.memory_retrieval_system_gate as system_gate_mod
    import scripts.wiki_vector_live_gate as wiki_gate_mod
    from dharma_swarm import wiki_vector_ingest

    state_dir = _seed_state(tmp_path)
    monkeypatch.setattr(
        wiki_vector_ingest,
        "ingest_wiki_concepts",
        lambda **_: _StubGateReceipt({"discovered_files": 1}),
        raising=True,
    )
    monkeypatch.setattr(
        wiki_gate_mod,
        "run_gate",
        lambda **_: _StubGateReceipt({"score": 96.0, "passed": True}),
        raising=True,
    )
    monkeypatch.setattr(
        system_gate_mod,
        "run_system_gate",
        lambda **_: {"score": 88.0, "max_score": 100, "passed": True},
        raising=True,
    )

    receipt = run_memory_metabolism(state_dir=state_dir, top_k=2)

    sink = state_dir / "reports" / "memory_kernel"
    receipt_path = Path(receipt["receipt_path"])
    assert receipt_path.parent == sink
    assert receipt_path.exists()
    assert receipt["passed"] is True
    assert list(sink.glob("WIKI_VECTOR_LIVE_GATE_*FINAL.json"))
    assert list(sink.glob("MEMORY_RETRIEVAL_SYSTEM_GATE_*FINAL.json"))

    summary = memory_common_summary(state_dir=state_dir)
    assert summary.wiki_gate_score == 96.0
    assert summary.system_gate_score == 88.0


def test_memory_common_summary_gate_scores_null_without_receipts(tmp_path: Path) -> None:
    summary = memory_common_summary(state_dir=tmp_path / ".dharma")

    assert summary.wiki_gate_score is None
    assert summary.system_gate_score is None


def test_latest_gate_score_skips_malformed_and_uses_newest_valid(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    sink = state_dir / "reports" / "memory_kernel"
    sink.mkdir(parents=True)
    valid = sink / "WIKI_VECTOR_LIVE_GATE_20260101T000000Z_FINAL.json"
    valid.write_text(json.dumps({"score": 50.0}), encoding="utf-8")
    malformed = sink / "WIKI_VECTOR_LIVE_GATE_20260201T000000Z_FINAL.json"
    malformed.write_text("not json", encoding="utf-8")
    os.utime(valid, (1, 1))

    score = _latest_gate_score("WIKI_VECTOR_LIVE_GATE_*FINAL.json", state_dir=state_dir)

    assert score == 50.0


def test_memory_common_command_rejects_unknown_mode(tmp_path: Path) -> None:
    rendered = render_memory_common_command("bogus", state_dir=tmp_path / ".dharma")

    assert "Unknown memory mode: `bogus`" in rendered


def test_memory_common_command_reports_parse_error(tmp_path: Path) -> None:
    rendered = render_memory_common_command("query 'unterminated", state_dir=tmp_path / ".dharma")

    assert "Memory command parse error" in rendered


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


def test_broad_sweep_negative_count_above_seed_pool_generates_distinct_cases() -> None:
    from scripts.memory_retrieval_broad_sweep import _negative_cases

    cases = _negative_cases(11)

    assert len(cases) == 11
    assert len({case.query for case in cases}) == 11
    assert all(case.expect_empty for case in cases)


def test_broad_sweep_missing_store_yields_empty_rows_without_creating_db(tmp_path: Path) -> None:
    from scripts.memory_retrieval_broad_sweep import load_indexed_rows

    state_dir = tmp_path / ".dharma"
    state_dir.mkdir()

    assert load_indexed_rows(state_dir) == []
    assert not (state_dir / "vectors.db").exists()


def test_system_gate_skip_live_is_neutral_not_unattainable(tmp_path: Path) -> None:
    from scripts.memory_retrieval_system_gate import run_system_gate

    payload = run_system_gate(state_dir=tmp_path / ".dharma", run_live=False, top_k=1)

    live_check = next(
        check for check in payload["checks"] if check["name"] == "live_semantic_gate"
    )
    assert live_check["max_score"] == 0.0
    assert live_check["passed"] is True
    assert live_check["details"] == {"skipped": True}
    # 20 live points are excluded from the attainable maximum, not forfeited.
    assert payload["max_score"] == 80.0


def test_gate_run_case_survives_worker_thread(tmp_path: Path) -> None:
    import threading

    from scripts.memory_retrieval_broad_sweep import BroadCase, alarm_usable, run_case

    class _StubResult:
        candidates = ()
        timings_ms = {"total": 1.0}

    class _StubEngine:
        def retrieve(self, _query):
            return _StubResult()

    case = BroadCase(
        name="negative_thread",
        query="xyzzq impossible",
        case_kind="adversarial_negative",
        expect_empty=True,
    )
    outcome: dict = {}

    def worker() -> None:
        outcome["alarm_usable"] = alarm_usable()
        try:
            outcome["row"] = run_case(_StubEngine(), case, top_k=1, timeout_s=1)
        except Exception as exc:  # pragma: no cover - the regression under test
            outcome["error"] = exc

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=10)

    assert "error" not in outcome, f"run_case raised off main thread: {outcome.get('error')}"
    assert outcome["alarm_usable"] is False
    assert outcome["row"]["passed"] is True
