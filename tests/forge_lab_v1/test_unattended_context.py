from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm.forge_lab import unattended_context as context
from dharma_swarm.forge_lab import unattended_judge as judge_custody
from dharma_swarm.forge_lab.state_io import content_digest
from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256

TASK_ID = "django__django-12209"


def _judge_row(fixture: dict[str, Any]) -> dict[str, str]:
    return {
        "repo": fixture["repo"],
        "instance_id": TASK_ID,
        "base_commit": fixture["base_commit"],
        "patch": "gold body must remain judge-only",
        "test_patch": "hidden test body must remain judge-only",
        "problem_statement": "judge statement",
        "hints_text": "",
        "created_at": "2026-01-01T00:00:00Z",
        "version": "1.0",
        "FAIL_TO_PASS": json.dumps(["tests.test_regression"]),
        "PASS_TO_PASS": "[]",
        "environment_setup_commit": "a" * 40,
        "difficulty": "fixture",
    }


def _task_row(fixture: dict[str, Any]) -> dict[str, object]:
    raw = {
        "FAIL_TO_PASS": ["tests.test_regression"],
        "base_commit": fixture["base_commit"],
        "instance_id": TASK_ID,
        "problem_statement": "bounded fixture",
        "repo": fixture["repo"],
    }
    task_sha256 = canonical_sha256(raw)
    provenance = {"task_sha256": task_sha256}
    task = {
        **raw,
        "task_id": TASK_ID,
        "provenance": provenance,
        "sealed_provenance": provenance,
        "contamination_state": "possible_pretrain",
        "taskbed": fixture["taskbed"],
        "source": fixture["source"],
        "max_uses_per_epoch": 1,
    }
    fixture["task_sha256"] = task_sha256
    fixture["task_payload_digest"] = content_digest(task)
    return {
        "active": 1,
        "source": fixture["source"],
        "taskbed": fixture["taskbed"],
        "provenance": provenance,
        "task": task,
    }


def _install_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], dict[str, object], dict[str, str]]:
    fixture = dict(context.ADMITTED_TASK_IMAGES[TASK_ID])
    fixture["judge_dataset_revision"] = "f" * 40
    fixture["judge_dataset_rows"] = 1
    judge = _judge_row(fixture)
    fixture["judge_row_sha256"] = canonical_sha256(judge)
    task_row = _task_row(fixture)

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DOCKER_HOST", "unix:///var/run/docker.sock")
    context.sanitize_unattended_docker_env()
    hub = Path(context.os.environ["HF_HUB_CACHE"])
    snapshot = (
        hub / "datasets--fixture" / "snapshots" / fixture["judge_dataset_revision"]
    )
    parquet = snapshot / "data" / "test-00000-of-00001.parquet"
    parquet.parent.mkdir(parents=True)
    parquet.write_bytes(b"sealed parquet fixture")
    fixture["judge_cache_file_digest"] = (
        "sha256:" + context.hashlib.sha256(parquet.read_bytes()).hexdigest()
    )
    monkeypatch.setitem(context.ADMITTED_TASK_IMAGES, TASK_ID, fixture)
    monkeypatch.setattr(context, "_task_for_id", lambda *_args: task_row)
    monkeypatch.setattr(
        judge_custody,
        "_load_release_dataset",
        lambda *_args: ([judge], list(context.JUDGE_FIELDS), snapshot, parquet),
    )
    return fixture, task_row, judge


def _image_inspect(*, image_id: str | None = None) -> str:
    fixture = context.ADMITTED_TASK_IMAGES[TASK_ID]
    expected_id = image_id or fixture["image_id"]
    return json.dumps(
        [
            {
                "Id": expected_id,
                "Os": fixture["os"],
                "Architecture": fixture["architecture"],
                "RepoTags": [fixture["image_reference"]],
                "RepoDigests": [fixture["repo_digest"]],
            }
        ]
    )


def test_context_uses_exact_cached_image_without_pull_or_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    fixture, _task_row_value, _judge = _install_fixture(tmp_path, monkeypatch)

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(argv, 0, _image_inspect(), "")
        return subprocess.CompletedProcess(argv, 0, "source context\n", "")

    monkeypatch.setattr(context.subprocess, "run", run)
    task, files, binding = context.load_admitted_task_context(
        TASK_ID,
        state_root=tmp_path,
    )

    assert task["task_id"] == TASK_ID
    assert set(task) == set(context.PROMPT_TASK_FIELDS)
    assert "FAIL_TO_PASS" not in task
    assert "provenance" not in task
    assert files == {"django/db/models/base.py": "source context\n"}
    assert binding["pull_allowed"] is False
    assert binding["container_network_disabled"] is True
    assert binding["judge_row_loaded_for_digest"] is True
    assert binding["judge_row_exposed_to_model"] is False
    assert binding["gold_patch_exposed_to_model"] is False
    assert binding["task_payload_digest"] == fixture["task_payload_digest"]
    assert (
        binding["judge_dataset"]["dataset_revision"]
        == fixture["judge_dataset_revision"]
    )
    binding_text = json.dumps(binding, sort_keys=True)
    assert "gold body must remain judge-only" not in binding_text
    assert "hidden test body must remain judge-only" not in binding_text
    assert "tests.test_regression" not in binding_text
    run_argv = calls[1]
    assert calls[0] == [
        "docker",
        "image",
        "inspect",
        fixture["image_reference"],
    ]
    assert "pull" not in run_argv
    assert "--pull=never" in run_argv
    assert run_argv[run_argv.index("--network") + 1] == "none"
    assert fixture["image_id"] in run_argv


def test_context_refuses_cached_image_identity_mismatch_before_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixture, _task_row_value, _judge = _install_fixture(tmp_path, monkeypatch)
    calls: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(
            argv,
            0,
            _image_inspect(image_id="sha256:" + "0" * 64),
            "",
        )

    monkeypatch.setattr(context.subprocess, "run", run)
    with pytest.raises(context.UnattendedContextError) as error:
        context.load_admitted_task_context(TASK_ID, state_root=tmp_path)
    assert error.value.code == "TASK_IMAGE_IDENTITY_MISMATCH"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "field",
    ["FAIL_TO_PASS", "base_commit", "instance_id", "problem_statement", "repo"],
)
def test_context_refuses_any_oracle_task_field_mutation_before_judge_or_image(
    field: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixture, task_row, _judge = _install_fixture(tmp_path, monkeypatch)
    task = task_row["task"]
    assert isinstance(task, dict)
    task[field] = ["changed"] if field == "FAIL_TO_PASS" else "changed"
    judge_calls: list[object] = []
    docker_calls: list[object] = []
    monkeypatch.setattr(
        judge_custody,
        "_load_release_dataset",
        lambda *_args: judge_calls.append(object()),
    )
    monkeypatch.setattr(
        context.subprocess,
        "run",
        lambda *_args, **_kwargs: docker_calls.append(object()),
    )

    with pytest.raises(context.UnattendedContextError) as error:
        context.load_admitted_task_context(TASK_ID, state_root=tmp_path)

    assert error.value.code in {"TASK_FIXTURE_MISMATCH", "TASK_ORACLE_DIGEST_MISMATCH"}
    assert judge_calls == []
    assert docker_calls == []


def test_context_binds_full_stored_task_payload_before_judge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixture, task_row, _judge = _install_fixture(tmp_path, monkeypatch)
    task = task_row["task"]
    assert isinstance(task, dict)
    task["max_uses_per_epoch"] = 2
    judge_calls: list[object] = []
    monkeypatch.setattr(
        judge_custody,
        "_load_release_dataset",
        lambda *_args: judge_calls.append(object()),
    )

    with pytest.raises(context.UnattendedContextError) as error:
        context.load_admitted_task_context(TASK_ID, state_root=tmp_path)

    assert error.value.code == "TASK_PAYLOAD_DIGEST_MISMATCH"
    assert judge_calls == []


@pytest.mark.parametrize(
    "field",
    [
        "patch",
        "test_patch",
        "FAIL_TO_PASS",
        "PASS_TO_PASS",
        "version",
        "environment_setup_commit",
        "difficulty",
    ],
)
def test_judge_row_mutation_is_refused_by_whole_row_digest(
    field: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, _task_row_value, judge = _install_fixture(tmp_path, monkeypatch)
    changed = dict(judge)
    changed[field] = changed[field] + " changed"
    hub = Path(context.os.environ["HF_HUB_CACHE"])
    snapshot = (
        hub / "datasets--fixture" / "snapshots" / fixture["judge_dataset_revision"]
    )
    parquet = snapshot / "data" / "test-00000-of-00001.parquet"
    monkeypatch.setattr(
        judge_custody,
        "_load_release_dataset",
        lambda *_args: ([changed], list(context.JUDGE_FIELDS), snapshot, parquet),
    )

    with pytest.raises(context.UnattendedContextError) as error:
        context.load_admitted_judge_dataset(
            fixture["judge_dataset_name"],
            fixture["judge_dataset_split"],
            [TASK_ID],
        )

    assert error.value.code == "JUDGE_ROW_DIGEST_MISMATCH"


@pytest.mark.parametrize("rows", [[], ["duplicate"]])
def test_judge_dataset_row_count_is_release_bound(
    rows: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, _task_row_value, judge = _install_fixture(tmp_path, monkeypatch)
    selected = [] if not rows else [judge, dict(judge)]
    hub = Path(context.os.environ["HF_HUB_CACHE"])
    snapshot = hub / "datasets--fixture" / "snapshots" / fixture[
        "judge_dataset_revision"
    ]
    parquet = snapshot / "data" / "test-00000-of-00001.parquet"
    monkeypatch.setattr(
        judge_custody,
        "_load_release_dataset",
        lambda *_args: (selected, list(context.JUDGE_FIELDS), snapshot, parquet),
    )

    with pytest.raises(context.UnattendedContextError) as error:
        context.load_admitted_judge_dataset(
            fixture["judge_dataset_name"],
            fixture["judge_dataset_split"],
            [TASK_ID],
        )

    assert error.value.code == "JUDGE_DATASET_SHAPE_MISMATCH"


def test_judge_revision_and_cache_digest_are_release_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, _task_row_value, judge = _install_fixture(tmp_path, monkeypatch)
    hub = Path(context.os.environ["HF_HUB_CACHE"])
    wrong_snapshot = hub / "datasets--fixture" / "snapshots" / ("e" * 40)
    parquet = wrong_snapshot / "data" / "test-00000-of-00001.parquet"
    parquet.parent.mkdir(parents=True)
    parquet.write_bytes(b"sealed parquet fixture")
    monkeypatch.setattr(
        judge_custody,
        "_load_release_dataset",
        lambda *_args: ([judge], list(context.JUDGE_FIELDS), wrong_snapshot, parquet),
    )

    with pytest.raises(context.UnattendedContextError) as error:
        context.load_admitted_judge_dataset(
            fixture["judge_dataset_name"],
            fixture["judge_dataset_split"],
            [TASK_ID],
        )

    assert error.value.code == "JUDGE_CACHE_DIGEST_MISMATCH"


def test_unattended_docker_env_discards_tls_and_api_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("DOCKER_TLS_VERIFY", "1")
    monkeypatch.setenv("DOCKER_CERT_PATH", "/untrusted")
    monkeypatch.setenv("DOCKER_API_VERSION", "0.0")
    monkeypatch.setattr(context.platform, "system", lambda: "Linux")

    context.sanitize_unattended_docker_env()

    assert "DOCKER_TLS_VERIFY" not in context.os.environ
    assert "DOCKER_CERT_PATH" not in context.os.environ
    assert "DOCKER_API_VERSION" not in context.os.environ
    assert context.os.environ["DOCKER_HOST"] == "unix:///var/run/docker.sock"
    assert context.os.environ["DOCKER_CONTEXT"] == "default"
    assert context.os.environ["HF_DATASETS_OFFLINE"] == "1"
    assert context.os.environ["HF_HUB_OFFLINE"] == "1"
    assert context.os.environ["HF_HOME"] == str(tmp_path / ".cache" / "huggingface")
    assert context.os.environ["RSI_LAB_REQUIRE_PINNED_SWEBENCH_IMAGE"] == "1"
