from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

import dharma_swarm.mission_control_oracle_launcher as launcher_module
from dharma_swarm.mission_control_oracle_launcher import (
    ORACLE_LAUNCH_TERMINAL_SCHEMA,
    FilesystemOracleSandboxLauncher,
    OracleLaunchRequest,
    OracleLauncherError,
)


SANDBOX_EVIDENCE = "sha256:" + "6" * 64


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _request(tmp_path: Path) -> OracleLaunchRequest:
    return OracleLaunchRequest(
        campaign_id="sadhana-10-20260823",
        mission_id="sadhana-10-20260823",
        goal_id="G10_SAFETY_TCB",
        task_id="task-g10",
        verifier_run_id="run-g10-oracle",
        idempotency_key="oracle-idempotency",
        manifest_digest="sha256:" + "1" * 64,
        evaluator_path=tmp_path / "evaluator.py",
        evaluator_sha256="sha256:" + "2" * 64,
        policy_path=tmp_path / "policy.json",
        policy_sha256="sha256:" + "3" * 64,
        input_path=tmp_path / "input.json",
        input_sha256="sha256:" + "4" * 64,
        sandbox_evidence_sha256=SANDBOX_EVIDENCE,
    )


def _roots(tmp_path: Path) -> tuple[Path, Path]:
    request_root = tmp_path / "requests"
    terminal_root = tmp_path / "terminals"
    request_root.mkdir(mode=0o700)
    terminal_root.mkdir(mode=0o750)
    request_root.chmod(0o700)
    terminal_root.chmod(0o750)
    return request_root, terminal_root


def _terminal_payload(request: OracleLaunchRequest) -> dict[str, object]:
    verdict = {"schema_version": "fixture.verdict.v1", "accepted": True}
    payload: dict[str, object] = {
        "schema_version": ORACLE_LAUNCH_TERMINAL_SCHEMA,
        "request_id": request.request_id,
        "request_digest": request.as_payload()["request_digest"],
        "status": "completed",
        "verdict_payload": verdict,
        "verdict_sha256": _digest(verdict),
        "sandbox_evidence_sha256": SANDBOX_EVIDENCE,
        "completed_at": datetime(2030, 1, 1, tzinfo=timezone.utc).isoformat(),
        "failure_code": "",
    }
    payload["terminal_digest"] = _digest(payload)
    return payload


def _launcher(
    request_root: Path,
    terminal_root: Path,
    **kwargs: object,
) -> FilesystemOracleSandboxLauncher:
    options: dict[str, object] = {
        "timeout_seconds": 0.1,
        "poll_interval_seconds": 0.01,
    }
    options.update(kwargs)
    return FilesystemOracleSandboxLauncher(
        sandbox_evidence_sha256=SANDBOX_EVIDENCE,
        request_root=request_root,
        terminal_root=terminal_root,
        terminal_root_owner_uid=os.geteuid(),
        **options,
    )


@pytest.mark.asyncio
async def test_publishes_exact_request_then_accepts_root_finalized_terminal(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    request_root, terminal_root = _roots(tmp_path)
    terminal_path = terminal_root / f"{request.request_id}.terminal.json"
    terminal_path.write_bytes(_canonical(_terminal_payload(request)))
    terminal_path.chmod(0o600)

    launcher = _launcher(request_root, terminal_root)
    first = await launcher.launch(request)
    request_path = request_root / f"{request.request_id}.oracle.json"
    request_stat = request_path.stat()
    second = await launcher.launch(request)

    assert request_path.read_bytes() == _canonical(request.as_payload())
    assert request_path.stat().st_mtime_ns == request_stat.st_mtime_ns
    assert first == second
    assert first.terminal_path == terminal_path


@pytest.mark.asyncio
async def test_request_is_visible_before_poll_and_terminal_directory_is_not_written(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    request_root, terminal_root = _roots(tmp_path)
    terminal_path = terminal_root / f"{request.request_id}.terminal.json"
    observations: list[tuple[bool, tuple[str, ...]]] = []

    async def publish_after_request(_: float) -> None:
        observations.append(
            (
                (request_root / f"{request.request_id}.oracle.json").exists(),
                tuple(path.name for path in terminal_root.iterdir()),
            )
        )
        terminal_path.write_bytes(_canonical(_terminal_payload(request)))
        terminal_path.chmod(0o600)

    result = await _launcher(
        request_root,
        terminal_root,
        sleep=publish_after_request,
    ).launch(request)

    assert observations == [(True, ())]
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_conflicting_request_replay_fails_closed(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request_root, terminal_root = _roots(tmp_path)
    request_path = request_root / f"{request.request_id}.oracle.json"
    request_path.write_bytes(b"{}\n")
    request_path.chmod(0o600)

    with pytest.raises(OracleLauncherError, match="replay conflicts"):
        await _launcher(request_root, terminal_root).launch(request)


@pytest.mark.asyncio
@pytest.mark.parametrize("custody", ["mode", "hardlink", "symlink"])
async def test_terminal_custody_fails_closed(tmp_path: Path, custody: str) -> None:
    request = _request(tmp_path)
    request_root, terminal_root = _roots(tmp_path)
    terminal_path = terminal_root / f"{request.request_id}.terminal.json"
    target = tmp_path / "foreign-terminal.json"
    target.write_bytes(_canonical(_terminal_payload(request)))
    target.chmod(0o600)
    if custody == "symlink":
        terminal_path.symlink_to(target)
    else:
        terminal_path.write_bytes(target.read_bytes())
        terminal_path.chmod(0o644 if custody == "mode" else 0o600)
        if custody == "hardlink":
            os.link(terminal_path, tmp_path / "terminal-hardlink")

    with pytest.raises(OracleLauncherError, match="terminal"):
        await _launcher(request_root, terminal_root).launch(request)


@pytest.mark.asyncio
async def test_terminal_digest_or_request_binding_tamper_fails_closed(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    request_root, terminal_root = _roots(tmp_path)
    payload = _terminal_payload(request)
    payload["request_digest"] = "sha256:" + "9" * 64
    unsigned = dict(payload)
    unsigned.pop("terminal_digest")
    payload["terminal_digest"] = _digest(unsigned)
    path = terminal_root / f"{request.request_id}.terminal.json"
    path.write_bytes(_canonical(payload))
    path.chmod(0o600)

    with pytest.raises(ValueError, match="coordinates conflict"):
        await _launcher(request_root, terminal_root).launch(request)


@pytest.mark.asyncio
async def test_missing_terminal_times_out_without_creating_terminal(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request_root, terminal_root = _roots(tmp_path)

    with pytest.raises(TimeoutError, match="not published"):
        await _launcher(
            request_root,
            terminal_root,
            timeout_seconds=0.01,
            poll_interval_seconds=0.001,
        ).launch(request)

    assert list(terminal_root.iterdir()) == []
    assert (request_root / f"{request.request_id}.oracle.json").is_file()


def test_launcher_requires_nofollow_and_directory_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_root, _ = _roots(tmp_path)
    monkeypatch.delattr(launcher_module.os, "O_NOFOLLOW")

    with pytest.raises(OracleLauncherError, match="O_NOFOLLOW and O_DIRECTORY"):
        launcher_module._open_directory(
            request_root,
            owner_uid=os.geteuid(),
            group_gid=os.getegid(),
            mode=0o700,
        )
