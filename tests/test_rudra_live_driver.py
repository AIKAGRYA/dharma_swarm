"""LiveCodexDriver offline conformance: a fake app-server process speaks the
pinned JSON-RPC protocol over stdio while the driver treats it as the real
binary. Proves thread persistence, deny-and-stop, mutation no-retry, death
detection with ProcessOwner census, budget event flow, turn deadlines, and
the explicit CLI activation gate. Normative source: spec section 11.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from dharma_swarm.rudra.codex_driver import ProtocolError, ServerRequestDenied
from dharma_swarm.rudra.live_driver import (
    LIVE_DRIVER_ENV,
    DriverBindError,
    LiveCodexDriver,
    build_spawn_env,
    live_driver_factory,
)
from dharma_swarm.rudra.process_owner import ProcessOwner
from dharma_swarm.terminal_commands.rudra import (
    cmd_rudra_run,
    select_driver_factory,
)
from tests.fixtures.rudra.helpers import (
    make_base_repo,
    make_mission_yaml,
    write_mission,
)

FAKE_SERVER = Path(__file__).parent / "fixtures" / "rudra" / "fake_app_server.py"

THREAD_ECHO = {
    "thread": {"id": "th-1"},
    "model": "m",
    "modelProvider": "p",
    "approvalPolicy": "never",
    "sandbox": "workspace-write",
}


def make_driver(
    tmp_path: Path, owner: ProcessOwner, steps: list[dict]
) -> LiveCodexDriver:
    script = tmp_path / "script.json"
    script.write_text(json.dumps(steps))
    return LiveCodexDriver(
        binary_path=sys.executable,
        argv_suffix=(str(FAKE_SERVER), str(script)),
        worktree=tmp_path,
        owner=owner,
        model="m",
        model_provider="p",
        reasoning_effort="low",
        service_tier="tier",
        contract_digest="c",
        attempt_key="a",
        spawn_env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    )


def handshake_steps() -> list[dict]:
    return [
        {"expect_method": "initialize", "result": {"userAgent": "fake/1.0"}},
        {"read_request": True},  # the "initialized" client notification
        {"expect_method": "thread/start", "result": dict(THREAD_ECHO)},
    ]


def turn_steps(turn_id: str, *, usage: bool = False) -> list[dict]:
    steps: list[dict] = [
        {"expect_method": "turn/start",
         "result": {"turn": {"id": turn_id, "status": "inProgress", "items": []}}},
    ]
    if usage:
        breakdown = {
            "inputTokens": 111, "outputTokens": 22, "cachedInputTokens": 0,
            "reasoningOutputTokens": 0, "totalTokens": 133,
        }
        steps.append({"send": {
            "jsonrpc": "2.0", "method": "thread/tokenUsage/updated",
            "params": {"threadId": "th-1", "turnId": turn_id,
                       "tokenUsage": {"last": breakdown, "total": breakdown}},
        }})
        steps.append({"send": {
            "jsonrpc": "2.0", "method": "item/agentMessage/delta",
            "params": {"threadId": "th-1", "turnId": turn_id,
                       "itemId": "i1", "delta": "hello"},
        }})
        steps.append({"send": {
            "jsonrpc": "2.0", "method": "turn/diff/updated",
            "params": {"threadId": "th-1", "turnId": turn_id,
                       "diff": "diff --git a/x b/x"},
        }})
    steps.append({"send": {
        "jsonrpc": "2.0", "method": "turn/completed",
        "params": {"threadId": "th-1",
                   "turn": {"id": turn_id, "status": "completed", "items": []}},
    }})
    return steps


def test_thread_persists_across_turns(tmp_path: Path) -> None:
    owner = ProcessOwner()
    driver = make_driver(
        tmp_path, owner,
        handshake_steps() + turn_steps("t-0", usage=True) + turn_steps("t-1"),
    )
    assert driver.start_or_resume() == "th-1"
    handle = driver.process_handles[0]
    assert owner.identity_status(handle) == "alive"  # census sees the spawn
    # A second start_or_resume must not issue any new RPC (the fake's script
    # has no further thread/start step and would abort the child on one).
    assert driver.start_or_resume() == "th-1"
    first = driver.start_turn(prompt="one", logical_seq=0, deadline_seconds=30)
    second = driver.start_turn(prompt="two", logical_seq=1, deadline_seconds=30)
    assert first.thread_id == second.thread_id == "th-1"
    assert (first.turn_id, second.turn_id) == ("t-0", "t-1")
    # Budget event flow: usage notifications became observation tokens.
    assert (first.input_tokens, first.output_tokens) == (111, 22)
    assert first.reported_complete and second.reported_complete
    assert first.response_sha256 is not None
    assert first.aggregate_diff_sha256 is not None
    # No usage event on turn two: tokens stay None for conservative charge.
    assert second.input_tokens is None and second.output_tokens is None
    driver.close()
    assert owner.prove_dead(handle)


def test_server_request_mid_turn_denied_and_stops(tmp_path: Path) -> None:
    owner = ProcessOwner()
    driver = make_driver(
        tmp_path, owner,
        handshake_steps()
        + [
            {"expect_method": "turn/start",
             "result": {"turn": {"id": "t-0", "status": "inProgress", "items": []}}},
            {"send": {
                "jsonrpc": "2.0", "id": "srv-1",
                "method": "item/tool/requestUserInput", "params": {},
            }},
            {"read_error_response": True},  # the explicit denial left the host
        ],
    )
    driver.start_or_resume()
    with pytest.raises(ServerRequestDenied):
        driver.start_turn(prompt="p", logical_seq=0, deadline_seconds=30)
    driver.close()


def test_mutation_rpc_no_transport_retry(tmp_path: Path) -> None:
    """The server dies before initialize answers: one spawn, one attempt,
    failure surfaces as a bind error — never a blind resend."""
    owner = ProcessOwner()
    driver = make_driver(tmp_path, owner, [{"exit": True}])
    with pytest.raises(DriverBindError):
        driver.start_or_resume()
    assert len(driver.process_handles) == 1
    assert driver._peer is not None and driver._peer.bytes_written > 0
    driver.close()


def test_death_mid_turn_detected_and_tree_proven_dead(tmp_path: Path) -> None:
    owner = ProcessOwner()
    driver = make_driver(
        tmp_path, owner,
        handshake_steps() + [{"read_request": True}, {"exit": True}],
    )
    driver.start_or_resume()
    with pytest.raises(ProtocolError, match="lost after write"):
        driver.start_turn(prompt="p", logical_seq=0, deadline_seconds=30)
    # The dead channel is marked; no further turn may be attempted on it.
    with pytest.raises(ProtocolError, match="turn before thread start"):
        driver.start_turn(prompt="p", logical_seq=1, deadline_seconds=30)
    driver.close()
    assert owner.prove_dead(driver.process_handles[0])


def test_turn_deadline_interrupts_and_raises(tmp_path: Path) -> None:
    owner = ProcessOwner()
    driver = make_driver(
        tmp_path, owner,
        handshake_steps()
        + [
            {"expect_method": "turn/start",
             "result": {"turn": {"id": "t-9", "status": "inProgress", "items": []}}},
            {"sleep": 2.0},
            {"expect_method": "turn/interrupt", "result": {}},
        ],
    )
    driver.start_or_resume()
    with pytest.raises(ProtocolError, match="timeout"):
        driver.start_turn(prompt="p", logical_seq=0, deadline_seconds=1)
    assert driver.witness == []  # the interrupt was delivered, not dropped
    driver.close()


def test_containment_echo_mismatch_is_bind_error(tmp_path: Path) -> None:
    owner = ProcessOwner()
    driver = make_driver(
        tmp_path, owner,
        [
            {"expect_method": "initialize", "result": {"userAgent": "fake/1.0"}},
            {"read_request": True},
            {"expect_method": "thread/start",
             "result": {**THREAD_ECHO, "approvalPolicy": "on-request"}},
        ],
    )
    with pytest.raises(DriverBindError, match="approvalPolicy"):
        driver.start_or_resume()
    driver.close()


@pytest.mark.parametrize(
    "omitted", ["approvalPolicy", "sandbox", "model", "modelProvider"]
)
def test_absent_policy_echo_is_bind_error(tmp_path: Path, omitted: str) -> None:
    """A schema-drifted server that OMITS a containment/model echo field
    fails closed: an absent echo is a DriverBindError, never a vacuous
    pass — and the spawned tree is still proven dead on close."""
    owner = ProcessOwner()
    echo = {key: value for key, value in THREAD_ECHO.items() if key != omitted}
    driver = make_driver(
        tmp_path, owner,
        [
            {"expect_method": "initialize", "result": {"userAgent": "fake/1.0"}},
            {"read_request": True},
            {"expect_method": "thread/start", "result": echo},
        ],
    )
    with pytest.raises(DriverBindError):
        driver.start_or_resume()
    driver.close()
    assert owner.prove_dead(driver.process_handles[0])


def test_stderr_drained_with_bounded_witness(tmp_path: Path) -> None:
    """Spec section 11: stdout and stderr are drained concurrently with
    size limits. A server emitting far more stderr than the OS pipe buffer
    mid-turn deadlocks a piped-and-undrained pair (server blocks on write,
    driver blocks on read); the bounded witness keeps the turn flowing and
    retains a forensic tail with the overflow counted, never buffered."""
    owner = ProcessOwner()
    steps = handshake_steps() + [
        {"expect_method": "turn/start",
         "result": {"turn": {"id": "t-0", "status": "inProgress", "items": []}}},
        {"write_stderr": "x" * 4096, "repeat": 1024},  # 4 MiB >> pipe buffer
        {"send": {
            "jsonrpc": "2.0", "method": "turn/completed",
            "params": {"threadId": "th-1",
                       "turn": {"id": "t-0", "status": "completed", "items": []}},
        }},
    ]
    driver = make_driver(tmp_path, owner, steps)
    driver.start_or_resume()
    observation = driver.start_turn(prompt="p", logical_seq=0, deadline_seconds=30)
    assert observation.reported_complete
    driver.close()  # kills the tree; the drainer joins at stderr EOF
    tail = driver.stderr_witness_text()
    assert tail, "server diagnostics were not retained as evidence"
    assert len(tail.encode()) <= 1 << 16  # bounded capture, never unbounded
    witness = driver._stderr_witness
    assert witness is not None and witness.dropped_bytes > 0


def test_foreign_turn_usage_event_not_counted(tmp_path: Path) -> None:
    """Delayed or foreign tokenUsage telemetry is never attributed to the
    active turn's budget: wrong thread, wrong turn, and missing
    correlating ids are all dropped, leaving counts None so the runner
    applies its conservative per-turn ceiling charge."""
    owner = ProcessOwner()
    foreign = {
        "inputTokens": 999999, "outputTokens": 999999, "cachedInputTokens": 0,
        "reasoningOutputTokens": 0, "totalTokens": 1999998,
    }

    def usage(params: dict) -> dict:
        return {"send": {
            "jsonrpc": "2.0", "method": "thread/tokenUsage/updated",
            "params": {**params, "tokenUsage": {"last": foreign, "total": foreign}},
        }}

    steps = handshake_steps() + [
        {"expect_method": "turn/start",
         "result": {"turn": {"id": "t-0", "status": "inProgress", "items": []}}},
        usage({"threadId": "th-FOREIGN", "turnId": "t-0"}),
        usage({"threadId": "th-1", "turnId": "t-PRIOR"}),
        usage({"threadId": "th-1"}),  # no turn id: unattributable
        {"send": {
            "jsonrpc": "2.0", "method": "turn/completed",
            "params": {"threadId": "th-1",
                       "turn": {"id": "t-0", "status": "completed", "items": []}},
        }},
    ]
    driver = make_driver(tmp_path, owner, steps)
    driver.start_or_resume()
    observation = driver.start_turn(prompt="p", logical_seq=0, deadline_seconds=30)
    assert observation.reported_complete
    assert observation.input_tokens is None and observation.output_tokens is None
    driver.close()


def test_spawn_env_allowlist() -> None:
    env = build_spawn_env(
        {
            "PATH": "/usr/bin:/bin",
            "HOME": "/home/x",
            "OPENAI_API_KEY": "sk-should-not-cross",
            "DHARMA_TOKEN": "nor-this",
        }
    )
    assert env["PATH"] == "/usr/bin:/bin"
    assert env["HOME"] == "/home/x"
    assert "OPENAI_API_KEY" not in env
    assert "DHARMA_TOKEN" not in env
    assert env["LANG"] == "C.UTF-8"


def _fake_admitted(driver_name: str = "codex_app_server_stdio") -> SimpleNamespace:
    executor = SimpleNamespace(
        driver=driver_name,
        binary=SimpleNamespace(path="/bin/echo"),
        model="m", model_provider="p",
        reasoning_effort="low", service_tier="tier",
    )
    return SimpleNamespace(
        contract=SimpleNamespace(executor=executor),
        contract_digest="c",
        attempt_key="a",
    )


def test_factory_maps_executor_spec() -> None:
    owner = ProcessOwner()
    factory = live_driver_factory(owner)
    driver = factory(_fake_admitted(), Path("/tmp"))
    assert driver.binary_path == "/bin/echo"
    assert (driver.model, driver.model_provider) == ("m", "p")
    assert (driver.reasoning_effort, driver.service_tier) == ("low", "tier")


def test_factory_rejects_wrong_driver_name() -> None:
    factory = live_driver_factory(ProcessOwner())
    with pytest.raises(ProtocolError, match="not 'codex_app_server_stdio'"):
        factory(_fake_admitted("other_driver"), Path("/tmp"))


def test_cli_activation_gate(tmp_path: Path) -> None:
    """No env or wrong driver pin -> no factory -> BLOCKED_ENVIRONMENT stays."""
    repo, base = make_base_repo(tmp_path)
    mission_text = make_mission_yaml(repo, base)
    owner = ProcessOwner()
    assert select_driver_factory({}, mission_text, owner) is None
    assert select_driver_factory({LIVE_DRIVER_ENV: "0"}, mission_text, owner) is None
    mismatched = make_mission_yaml(
        repo, base, overrides={"executor.driver": "other_driver"}
    )
    assert select_driver_factory({LIVE_DRIVER_ENV: "1"}, mismatched, owner) is None
    assert select_driver_factory({LIVE_DRIVER_ENV: "1"}, mission_text, owner) is not None


def test_bind_failure_seals_blocked_environment(tmp_path: Path, monkeypatch, capsys):
    """Env opt-in with a non-app-server binary: spawn succeeds, handshake
    hits EOF, DriverBindError seals BLOCKED_ENVIRONMENT (invariant 9)."""
    repo, base = make_base_repo(tmp_path)
    mission_path = write_mission(tmp_path, make_mission_yaml(repo, base))
    monkeypatch.setenv(LIVE_DRIVER_ENV, "1")
    code = cmd_rudra_run(
        str(mission_path), repo_path=str(repo), state_dir=str(tmp_path / "state")
    )
    assert code == 2
    assert "BLOCKED_ENVIRONMENT" in capsys.readouterr().out
