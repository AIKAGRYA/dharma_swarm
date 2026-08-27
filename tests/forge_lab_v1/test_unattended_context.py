from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from dharma_swarm.forge_lab import unattended_context as context

TASK_ID = "django__django-12209"


def _task_row() -> dict[str, object]:
    fixture = context.ADMITTED_TASK_IMAGES[TASK_ID]
    return {
        "active": 1,
        "source": fixture["source"],
        "taskbed": fixture["taskbed"],
        "provenance": {"task_sha256": fixture["task_sha256"]},
        "task": {
            "task_id": TASK_ID,
            "instance_id": TASK_ID,
            "repo": fixture["repo"],
            "base_commit": fixture["base_commit"],
            "problem_statement": "bounded fixture",
        },
    }


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
    monkeypatch.setenv("DOCKER_HOST", "unix:///var/run/docker.sock")
    monkeypatch.setattr(context, "_task_for_id", lambda *_args: _task_row())

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
    assert files == {"django/db/models/base.py": "source context\n"}
    assert binding["pull_allowed"] is False
    assert binding["container_network_disabled"] is True
    assert binding["gold_patch_loaded"] is False
    run_argv = calls[1]
    assert calls[0] == [
        "docker",
        "image",
        "inspect",
        context.ADMITTED_TASK_IMAGES[TASK_ID]["image_reference"],
    ]
    assert "pull" not in run_argv
    assert "--pull=never" in run_argv
    assert run_argv[run_argv.index("--network") + 1] == "none"
    assert context.ADMITTED_TASK_IMAGES[TASK_ID]["image_id"] in run_argv


def test_context_refuses_cached_image_identity_mismatch_before_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOCKER_HOST", "unix:///var/run/docker.sock")
    monkeypatch.setattr(context, "_task_for_id", lambda *_args: _task_row())
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


def test_unattended_docker_env_discards_tls_and_api_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    assert context.os.environ["RSI_LAB_REQUIRE_PINNED_SWEBENCH_IMAGE"] == "1"
