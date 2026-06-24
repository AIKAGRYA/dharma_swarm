from __future__ import annotations

import fcntl
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from dharma_swarm.holon_l4_service import run_holon_l4_service
from dharma_swarm.holon_l4_smoke import L4SmokeConfig
from dharma_swarm.holon_service_liveness import (
    assess_service_liveness,
    latest_service_heartbeat,
    service_heartbeat_path,
)


def _make_agent(root: Path, name: str = "codex_composer") -> Path:
    agent_dir = root / name
    (agent_dir / "prompt_variants").mkdir(parents=True)
    (agent_dir / "identity.json").write_text(
        json.dumps(
            {
                "model": "identity-model",
                "provider": "ollama",
                "system_prompt": "fallback prompt",
            }
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt_variants" / "active.txt").write_text(
        "I am codex_composer.",
        encoding="utf-8",
    )
    return root


def _config(tmp_path: Path, *, session_id: str = "l4-service-test") -> L4SmokeConfig:
    agents_root = _make_agent(tmp_path / "agents")
    return L4SmokeConfig(
        name="codex_composer",
        agents_root=agents_root,
        memory_receipt_path=tmp_path / "reports" / "l4_memory_write_receipts.jsonl",
        session_id=session_id,
        transport_heartbeat_path=tmp_path / "missing_transport.json",
    )


def test_l4_service_runs_unattended_cycle_under_lock(tmp_path: Path) -> None:
    result = run_holon_l4_service(
        _config(tmp_path),
        cycles=1,
        interval_seconds=0,
        lock_path=tmp_path / "service.lock",
    )

    assert result["schema_version"] == "dharma.holon_l4_service_run.v1"
    assert result["status"] == "completed"
    assert result["completed_cycles"] == 1
    assert result["cycles"][0]["status"] == "passed"
    assert result["cycles"][0]["overall_pass"] is True
    assert result["cycles"][0]["proof_digest"].startswith("sha256:")
    assert Path(result["cycles"][0]["artifact"]["path"]).exists()

    liveness = assess_service_liveness("codex_composer", agents_root=tmp_path / "agents")
    latest = latest_service_heartbeat("codex_composer", agents_root=tmp_path / "agents")
    assert liveness["service_alive"] is True
    assert latest["service_id"] == "holon-l4-service"
    assert latest["status"] == "idle"
    assert latest["session_id"] == "l4-service-test"


def test_l4_service_multiple_cycles_use_distinct_sessions_and_sleep(
    tmp_path: Path,
) -> None:
    observed_sleeps: list[float] = []
    result = run_holon_l4_service(
        _config(tmp_path, session_id="l4-service-multi"),
        cycles=2,
        interval_seconds=3,
        lock_path=tmp_path / "service.lock",
        sleep_fn=observed_sleeps.append,
    )

    assert result["status"] == "completed"
    assert result["completed_cycles"] == 2
    assert [cycle["session_id"] for cycle in result["cycles"]] == [
        "l4-service-multi",
        "l4-service-multi-cycle-2",
    ]
    assert observed_sleeps == [3.0]
    assert result["cycles"][0]["artifact"]["path"] != result["cycles"][1]["artifact"]["path"]


def test_l4_service_can_limit_model_probe_to_first_cycle(tmp_path: Path) -> None:
    observed_model_probe_flags: list[tuple[bool, str]] = []
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text("{}", encoding="utf-8")

    async def runner(config: L4SmokeConfig) -> dict:
        observed_model_probe_flags.append(
            (config.enable_model_probe, config.model_probe_lease_id)
        )
        return {
            "session_id": config.session_id,
            "overall_pass": True,
            "proof_digest": f"sha256:{len(observed_model_probe_flags)}",
            "artifact": {
                "artifact_id": "artifact",
                "digest": "sha256:artifact",
                "path": str(artifact_path),
            },
            "proof_levels": {
                "service_heartbeat": True,
                "model_responsive": bool(config.enable_model_probe),
            },
            "claim_scope": {
                "service_alive": True,
                "model_responsive": bool(config.enable_model_probe),
            },
        }

    result = run_holon_l4_service(
        replace(
            _config(tmp_path, session_id="l4-model-first"),
            enable_model_probe=True,
            allow_subprocess_model_probe=True,
            model_probe_lease_id="lease:test:first-cycle",
            model_probe_lease_path=tmp_path / "lease.json",
        ),
        cycles=2,
        interval_seconds=0,
        lock_path=tmp_path / "service.lock",
        cycle_runner=runner,
        model_probe_first_cycle_only=True,
    )

    assert result["status"] == "completed"
    assert observed_model_probe_flags == [
        (True, "lease:test:first-cycle"),
        (False, ""),
    ]
    assert result["cycles"][0]["claim_scope"]["model_responsive"] is True
    assert result["cycles"][1]["claim_scope"]["model_responsive"] is False


def test_l4_service_pauses_without_running_cycle_when_global_pause_present(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, session_id="l4-service-paused")
    (tmp_path / ".PAUSE").write_text("operator pause\n", encoding="utf-8")

    async def runner(_config: L4SmokeConfig) -> dict:
        raise AssertionError("paused service must not run L4 smoke cycle")

    result = run_holon_l4_service(
        config,
        cycles=1,
        interval_seconds=0,
        lock_path=tmp_path / "service.lock",
        cycle_runner=runner,
    )

    assert result["status"] == "paused"
    assert result["completed_cycles"] == 0
    assert result["cycles"] == []
    latest = latest_service_heartbeat("codex_composer", agents_root=tmp_path / "agents")
    assert latest is not None
    assert latest["status"] == "paused"
    assert latest["claim_scope"]["runtime_paused"] is True
    assert latest["runtime_ref"]["pause_path"] == str(tmp_path / ".PAUSE")


def test_l4_service_lock_prevents_split_brain(tmp_path: Path) -> None:
    config = _config(tmp_path)
    lock_path = tmp_path / "service.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("w", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = run_holon_l4_service(
            config,
            cycles=1,
            interval_seconds=0,
            lock_path=lock_path,
        )
        fcntl.flock(lock_handle, fcntl.LOCK_UN)

    assert result["status"] == "lock_held"
    assert result["completed_cycles"] == 0
    assert result["lock_ref"]["held"] is True
    assert not service_heartbeat_path("codex_composer", config.agents_root).exists()


def test_l4_service_cli_json_runs_one_cycle(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path / "agents")
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "holon_l4_service.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "codex_composer",
            "--agents-root",
            str(agents_root),
            "--memory-receipt-path",
            str(tmp_path / "reports" / "l4_memory_write_receipts.jsonl"),
            "--session-id",
            "l4-service-cli",
            "--cycles",
            "1",
            "--interval-seconds",
            "0",
            "--lock-path",
            str(tmp_path / "cli.lock"),
            "--json",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["status"] == "completed"
    assert payload["completed_cycles"] == 1
    assert payload["cycles"][0]["session_id"] == "l4-service-cli"
