from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dharma_swarm.mission_control_bootstrap import BootstrapResult
from dharma_swarm.mission_control_contract import MissionControlError
from dharma_swarm.mission_control_observed_input import (
    OBSERVED_INPUT_METADATA_KEY,
    artifact_record_digest,
    ingest_observed_input_manifest,
    load_observed_input_source,
    observed_input_manifest_digest,
    render_bound_observed_input_prompt,
    render_observed_input_manifest,
)
from dharma_swarm.runtime_state import ArtifactRecord, RuntimeStateStore
from dharma_swarm.task_board import TaskBoard

CAMPAIGN = "sadhana-observed-test"
GOAL = "G10_SAFETY_TCB"
PORTFOLIO = "sha256:" + "a" * 64
GOAL_DIGEST = "sha256:" + "b" * 64
CREATION_HASH = "c" * 64
OBSERVED_AT = "2026-08-23T09:05:00+09:00"


def _canonical(payload: dict) -> bytes:
    return (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        + b"\n"
    )


def _source(path: Path, content: str = "Observed state; verify it independently.\n") -> None:
    payload = {
        "schema_version": "dharma.sadhana.observed_input_source.v1",
        "campaign_id": CAMPAIGN,
        "mission_id": CAMPAIGN,
        "portfolio_contract_sha256": PORTFOLIO,
        "goals": {
            GOAL: {
                "goal_contract_sha256": GOAL_DIGEST,
                "observed_at": OBSERVED_AT,
                "epistemic_state": "observed_unverified",
                "authority_scope": "prompt_context_only",
                "media_type": "text/markdown; charset=utf-8",
                "content": content,
                "content_sha256": "sha256:"
                + hashlib.sha256(content.encode()).hexdigest(),
            }
        },
    }
    payload["manifest_digest"] = observed_input_manifest_digest(payload)
    path.write_bytes(_canonical(payload))
    path.chmod(0o600)


async def _case(tmp_path: Path):
    board = TaskBoard(tmp_path / "tasks.db")
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    await board.init_db()
    await runtime.init_db()
    task = await board.create(
        GOAL,
        metadata={
            "campaign_id": CAMPAIGN,
            "goal_id": GOAL,
            "portfolio_contract_sha256": PORTFOLIO,
            "goal_contract_sha256": GOAL_DIGEST,
            "mission_task_creation_hash": CREATION_HASH,
            "mission_task_id": "placeholder",
        },
    )
    metadata = dict(task.metadata)
    metadata["mission_task_id"] = task.id
    await board.update_task(task.id, metadata=metadata)
    bootstrap = BootstrapResult(
        mission_id=CAMPAIGN,
        contract_digest=PORTFOLIO,
        campaign_deadline="2026-09-02T02:15:12+09:00",
        dependency_order=(GOAL,),
        goal_task_map=((GOAL, task.id),),
        goal_contract_digests=((GOAL, GOAL_DIGEST),),
        canary_goal_id=GOAL,
        canary_task_id=task.id,
    )
    return board, runtime, bootstrap, task.id


@pytest.mark.asyncio
async def test_render_ingest_replay_and_prompt_are_exact(tmp_path: Path) -> None:
    board, runtime, bootstrap, task_id = await _case(tmp_path)
    source = tmp_path / "observed-inputs.source.json"
    manifest = tmp_path / "observed-inputs.json"
    _source(source)
    manifest.write_bytes(
        await render_observed_input_manifest(
            source,
            bootstrap,
            board,
            now=datetime(2026, 8, 23, 1, tzinfo=timezone.utc),
        )
    )
    manifest.chmod(0o600)

    first = await ingest_observed_input_manifest(manifest, board, runtime)
    second = await ingest_observed_input_manifest(manifest, board, runtime)

    assert (first.artifact_writes, first.receipt_writes) == (1, 1)
    assert (second.artifact_writes, second.receipt_writes) == (0, 0)
    bound = first.goals[0]
    assert bound.task_id == task_id
    assert bound.ref.artifact_record_sha256.startswith("sha256:")
    task = await board.get(task_id)
    assert task is not None
    authority = {
        "campaign_id": CAMPAIGN,
        "mission_id": CAMPAIGN,
        "goal_id": GOAL,
        "goal_contract_sha256": GOAL_DIGEST,
        "observed_input_ref": bound.ref.to_dict(),
    }
    metadata = {
        **task.metadata,
        "mission_campaign_authority": authority,
        OBSERVED_INPUT_METADATA_KEY: bound.prompt,
    }
    rendered = render_bound_observed_input_prompt(metadata)
    assert "Unverified; Prompt Context Only" in rendered
    assert "Observed state; verify it independently." in rendered


@pytest.mark.asyncio
async def test_ingest_resumes_artifact_first_partial_crash(tmp_path: Path) -> None:
    board, runtime, bootstrap, _ = await _case(tmp_path)
    source = tmp_path / "source.json"
    manifest = tmp_path / "manifest.json"
    _source(source)
    manifest.write_bytes(await render_observed_input_manifest(source, bootstrap, board))
    manifest.chmod(0o600)
    payload = json.loads(manifest.read_bytes())
    goal = payload["goals"][GOAL]
    observed_at = datetime.fromisoformat(goal["observed_at"])
    artifact = ArtifactRecord(
        artifact_id=goal["artifact_id"],
        artifact_kind="mission_observed_input",
        session_id=CAMPAIGN,
        task_id=goal["task_id"],
        checksum=goal["content_sha256"],
        promotion_state="observed_unverified",
        created_at=observed_at,
        metadata={
            "schema_version": "dharma.sadhana.observed_input_artifact.v1",
            "campaign_id": CAMPAIGN,
            "mission_id": CAMPAIGN,
            "goal_id": GOAL,
            "manifest_digest": payload["manifest_digest"],
            "goal_contract_sha256": GOAL_DIGEST,
            "task_creation_hash": CREATION_HASH,
            "observed_at": goal["observed_at"],
            "epistemic_state": "observed_unverified",
            "authority_scope": "prompt_context_only",
            "media_type": "text/markdown; charset=utf-8",
            "content": goal["content"],
            "content_sha256": goal["content_sha256"],
            "receipt_id": goal["receipt_id"],
        },
    )
    await runtime.insert_artifact_exact(artifact)
    result = await ingest_observed_input_manifest(manifest, board, runtime)
    assert (result.artifact_writes, result.receipt_writes) == (0, 1)
    assert result.goals[0].ref.artifact_record_sha256 == artifact_record_digest(artifact)


def test_source_rejects_noncanonical_bytes_and_revoked_oracle_leak(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    _source(source)
    payload = json.loads(source.read_bytes())
    source.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    source.chmod(0o600)
    with pytest.raises(MissionControlError, match="not canonical bytes"):
        load_observed_input_source(source)


@pytest.mark.asyncio
async def test_prompt_tamper_and_conflicting_artifact_fail_closed(tmp_path: Path) -> None:
    board, runtime, bootstrap, task_id = await _case(tmp_path)
    source = tmp_path / "source.json"
    manifest = tmp_path / "manifest.json"
    _source(source)
    manifest.write_bytes(await render_observed_input_manifest(source, bootstrap, board))
    manifest.chmod(0o600)
    first = await ingest_observed_input_manifest(manifest, board, runtime)
    bound = first.goals[0]
    task = await board.get(task_id)
    assert task is not None
    prompt = {**bound.prompt, "content": "forged content"}
    with pytest.raises(MissionControlError, match="content digest conflicts"):
        render_bound_observed_input_prompt(
            {
                **task.metadata,
                "mission_campaign_authority": {
                    "campaign_id": CAMPAIGN,
                    "mission_id": CAMPAIGN,
                    "goal_id": GOAL,
                    "goal_contract_sha256": GOAL_DIGEST,
                    "observed_input_ref": bound.ref.to_dict(),
                },
                OBSERVED_INPUT_METADATA_KEY: prompt,
            }
        )
    artifact = await runtime.get_artifact(bound.ref.artifact_id)
    assert artifact is not None
    with pytest.raises(ValueError, match="conflicting evidence"):
        await runtime.insert_artifact_exact(
            replace(artifact, checksum="sha256:" + "f" * 64)
        )
