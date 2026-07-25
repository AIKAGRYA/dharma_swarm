"""Tests for image-baked container provenance and its shell boundary."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "runtime" / "dharma_swarm_container_runner.sh"


def _sealed_source(tmp_path: Path) -> tuple[Path, Path]:
    app = tmp_path / "app"
    source = app / "dharma_swarm"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text('"""sealed"""', encoding="utf-8")
    (source / "worker.py").write_text("VALUE = 1\n", encoding="utf-8")
    lines = []
    for path in sorted(item for item in source.rglob("*") if item.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  ./{path.relative_to(source).as_posix()}")
    manifest = app / ".dharma-runtime-source.sha256"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return source, manifest


def _test_runner(
    tmp_path: Path,
    *,
    source: Path,
    manifest: Path,
) -> tuple[Path, Path]:
    call_log = tmp_path / "container-python.log"
    python = tmp_path / "python"
    python.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" > \"${CONTAINER_RUNNER_CALL_LOG}\"\n"
        "printf '%s\\n' \"${DHARMA_RUNTIME_PROVENANCE_MODE}\" >> "
        "\"${CONTAINER_RUNNER_CALL_LOG}\"\n"
        "printf '%s\\n' \"${DHARMA_RUNTIME_SOURCE_DIGEST}\" >> "
        "\"${CONTAINER_RUNNER_CALL_LOG}\"\n",
        encoding="utf-8",
    )
    python.chmod(0o755)
    text = RUNNER.read_text(encoding="utf-8")
    text = text.replace(
        'source_root="/app/dharma_swarm"',
        f'source_root="{source}"',
    )
    text = text.replace(
        'manifest="/app/.dharma-runtime-source.sha256"',
        f'manifest="{manifest}"',
    )
    text = text.replace(
        'runtime_python="/usr/local/bin/python"',
        f'runtime_python="{python}"',
    )
    runner = tmp_path / "container-runner"
    runner.write_text(text, encoding="utf-8")
    runner.chmod(0o755)
    return runner, call_log


def test_container_runner_verifies_manifest_before_python(tmp_path: Path) -> None:
    source, manifest = _sealed_source(tmp_path)
    runner, call_log = _test_runner(
        tmp_path,
        source=source,
        manifest=manifest,
    )
    environment = os.environ.copy()
    environment["CONTAINER_RUNNER_CALL_LOG"] = str(call_log)

    result = subprocess.run(
        ["/bin/bash", str(runner)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert calls[0] == "-B -I -m dharma_swarm.orchestrate_live"
    assert calls[1] == "container-image"
    assert calls[2] == hashlib.sha256(manifest.read_bytes()).hexdigest()

    call_log.unlink()
    verify = subprocess.run(
        ["/bin/bash", str(runner), "--verify-only"],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert verify.returncode == 0, verify.stderr
    assert call_log.read_text(encoding="utf-8").splitlines()[0] == (
        "-B -I -m dharma_swarm.runtime_admission"
    )


def test_container_runner_denies_source_tampering_before_python(
    tmp_path: Path,
) -> None:
    source, manifest = _sealed_source(tmp_path)
    runner, call_log = _test_runner(
        tmp_path,
        source=source,
        manifest=manifest,
    )
    (source / "worker.py").write_text("VALUE = 2\n", encoding="utf-8")
    environment = os.environ.copy()
    environment["CONTAINER_RUNNER_CALL_LOG"] = str(call_log)

    result = subprocess.run(
        ["/bin/bash", str(runner)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 78
    assert "does not match its baked manifest" in result.stderr
    assert not call_log.exists()


def test_swarm_image_uses_manifest_runner_without_checkout_overlay() -> None:
    dockerignore = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")
    dockerfile = (REPO_ROOT / "Dockerfile.swarm").read_text(encoding="utf-8")
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "dharma_swarm/**/*.py[cod]" in dockerignore
    assert "dharma_swarm_container_runner.sh" in dockerfile
    assert 'CMD ["/usr/local/bin/dharma-swarm-container-runner"]' in dockerfile
    assert "./dharma_swarm:/app/dharma_swarm" not in compose
