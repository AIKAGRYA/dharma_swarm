from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from api.routers import goodworks_dgm as goodworks_dgm_router
from api.chat_tools import exec_goodworks_dgm
from dharma_swarm.goodworks_dgm import (
    DGMRunReceipt,
    GoalSpec,
    GoodworksDGMService,
    MutationMode,
)
from dharma_swarm.goodworks_dgm.runtime import run_goodworks_dgm_tick
from dharma_swarm.goodworks_dgm.seed import seed_goodworks_mrv_pilot


def test_goal_spec_rejects_secret_like_payload() -> None:
    with pytest.raises(ValidationError):
        GoalSpec(
            title="bad payload",
            objective="Use OPENAI_API_KEY=sk-this-should-not-be-here-1234567890",
        )


@pytest.mark.asyncio
async def test_dry_run_scores_empty_goodworks_ledgers(tmp_path) -> None:
    service = GoodworksDGMService(
        state_dir=tmp_path / "state",
        ledger_root=tmp_path / "ledger",
        repo_root=tmp_path / "repo",
    )
    spec = GoalSpec(
        title="MRV baseline",
        objective="Measure current Goodworks ledger readiness.",
        mutation_mode=MutationMode.DRY_RUN,
    )

    run = await service.create_goal(spec)

    assert run.status == "succeeded"
    assert run.metrics.reciprocity_entries == 0
    assert run.metrics.gaia_entries == 0
    assert run.metrics.reciprocity_chain_valid is True
    assert run.metrics.gaia_chain_valid is True
    assert "ai_reciprocity_ledger has no entries" in run.metrics.warnings
    assert run.autoresearch_receipt is not None
    assert run.autoresearch_receipt.dry_run is True
    assert run.autoresearch_receipt.loop_invoked is False
    assert run.dgm_receipt is None
    assert service.status()["run_count"] == 1


def test_wiki_context_compiles_goodworks_atoms(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    docs = repo_root / "docs" / "loomwork"
    docs.mkdir(parents=True)
    (repo_root / "WHAT_IT_WANTS_TO_BECOME.md").write_text(
        "# Goodworks MRV\n\nDGM should improve GAIA reciprocity ledger verification.\n",
        encoding="utf-8",
    )
    (docs / "wiki_weaving_engine.md").write_text(
        "# Wiki Loom\n\nGoodworks context links telos, MRV, and verification.\n",
        encoding="utf-8",
    )
    service = GoodworksDGMService(
        state_dir=tmp_path / "state",
        ledger_root=tmp_path / "ledger",
        repo_root=repo_root,
    )
    spec = GoalSpec(title="Goodworks MRV", objective="Build the wiki context.")

    receipt = service.compile_wiki_context(spec)

    assert receipt.source_count == 2
    assert receipt.atom_count >= 2
    assert "mrv" in receipt.patterns
    assert not receipt.warnings


def test_seed_goodworks_mrv_pilot_is_idempotent(tmp_path) -> None:
    first = seed_goodworks_mrv_pilot(ledger_root=tmp_path / "ledger")
    second = seed_goodworks_mrv_pilot(ledger_root=tmp_path / "ledger")

    assert first["created"] is True
    assert second["created"] is False
    assert second["reciprocity_entries"] >= 9
    assert second["gaia_entries"] >= 3


@pytest.mark.asyncio
async def test_runtime_tick_can_seed_and_dry_run(tmp_path) -> None:
    payload = await run_goodworks_dgm_tick(
        state_dir=tmp_path / "state",
        ledger_root=tmp_path / "ledger",
        seed_pilot=True,
    )

    assert payload["seed"]["created"] is True
    assert payload["run"]["status"] == "succeeded"
    assert payload["run"]["metrics"]["reciprocity_entries"] >= 9


@pytest.mark.asyncio
async def test_shadow_goal_invokes_existing_dgm_surface(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_shadow(
        self: GoodworksDGMService, spec: GoalSpec, _metrics
    ) -> DGMRunReceipt:
        return DGMRunReceipt(
            goal_id=spec.goal_id,
            shadow_mode=True,
            source_file="agent_runner.py",
            fitness_delta=0.1,
            success=True,
        )

    monkeypatch.setattr(GoodworksDGMService, "_run_shadow_dgm", fake_shadow)
    service = GoodworksDGMService(
        state_dir=tmp_path / "state",
        ledger_root=tmp_path / "ledger",
        repo_root=tmp_path / "repo",
    )
    spec = GoalSpec(
        title="Shadow DGM MRV",
        objective="Try one non-mutating DGM iteration.",
        mutation_mode=MutationMode.SHADOW,
    )

    run = await service.create_goal(spec)

    assert run.status == "succeeded"
    assert run.dgm_receipt is not None
    assert run.dgm_receipt.shadow_mode is True
    assert run.dgm_receipt.applied is False
    assert service.recent_receipts(limit=10)[-1]["source_file"] == "agent_runner.py"


def test_goodworks_dgm_router_dry_run(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DHARMA_GOODWORKS_DGM_STATE_DIR", str(tmp_path / "state"))
    app = FastAPI()
    app.include_router(goodworks_dgm_router.router)
    client = TestClient(app)

    response = client.post(
        "/api/goodworks-dgm/goal",
        json={
            "title": "Goodworks MRV dry run",
            "objective": "Score the existing Goodworks substrate.",
            "mutation_mode": "dry_run",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["data"]["spec"]["domain"] == "goodworks_mrv"
    assert body["data"]["status"] == "succeeded"
    assert body["data"]["autoresearch_receipt"]["dry_run"] is True
    assert body["data"]["dgm_receipt"] is None

    status = client.get("/api/goodworks-dgm/status").json()
    assert status["data"]["run_count"] == 1
    assert status["data"]["live_mutation_exposed"] is False


@pytest.mark.asyncio
async def test_chat_tool_exposes_goodworks_status(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DHARMA_GOODWORKS_DGM_STATE_DIR", str(tmp_path / "state"))

    response = await exec_goodworks_dgm({"action": "status", "limit": 2})

    assert "Goodworks Intelligence Core" in response
    assert "repo_contains_key_values" in response
