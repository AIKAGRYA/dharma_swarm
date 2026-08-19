"""Tests for the default-off Darwin vibe-halt pre-apply observer."""

from __future__ import annotations

import ast
import asyncio
import json
import os
import shutil
import signal
import stat
import sys
import textwrap
from pathlib import Path

import pytest

from dharma_swarm.evolution import DarwinEngine, EvolutionStatus, Proposal
from dharma_swarm.vibe_halt_observer import (
    DEFAULT_SEED,
    DEFAULT_UNIVERSES,
    DEFAULT_WORKLOAD,
    MAX_STREAM_BYTES,
    MAX_TAIL_BYTES,
    SCHEMA,
    ObserverMode,
    ReportedOutcome,
    _blocks_apply,
    _parse_vh_run,
    run_observer,
)

VH_VARS = (
    "DHARMA_VH_OBSERVER",
    "DHARMA_VH_BIN",
    "DHARMA_VH_WORKLOAD",
    "DHARMA_VH_UNIVERSES",
    "DHARMA_VH_TIMEOUT_SECONDS",
)
_THINK_NOTES_SAFE = (
    "Risk: minimal — small targeted change. "
    "Rollback: revert single commit. "
    "Alternatives considered: no-op, full rewrite. "
    "Expected: improved resilience score."
)
STDLIB_ROOTS = {
    "asyncio",
    "collections",
    "dataclasses",
    "enum",
    "hashlib",
    "os",
    "re",
    "shutil",
    "signal",
    "stat",
    "tempfile",
    "time",
    "typing",
}


@pytest.fixture(autouse=True)
def _clear_vh_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in VH_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
async def engine(tmp_path: Path):
    eng = DarwinEngine(
        archive_path=tmp_path / "archive.jsonl",
        traces_path=tmp_path / "traces",
        predictor_path=tmp_path / "predictor.jsonl",
        archive_enforce_one_wire=False,
    )
    await eng.init()
    try:
        yield eng
    finally:
        await eng.close()


def _safe_proposal(**kw) -> Proposal:
    defaults = {
        "component": "module.py",
        "change_type": "observation",
        "description": (
            "Improve activation mechanism with consciousness witness "
            "and ecosystem resilience feedback"
        ),
        "diff": "- old_line\n+ new_line\n",
        "think_notes": _THINK_NOTES_SAFE,
    }
    defaults.update(kw)
    return Proposal(**defaults)


def _header(
    *,
    workload: str = "demo",
    seed: str = "0xd1ce",
    universes: int = 8,
    divergence: str = "true",
) -> str:
    return (
        f"vibe-halt: workload={workload} seed={seed} universes={universes} "
        f"palette=v0 divergence-check={divergence} schedule=fifo tape=false "
        f"fault-plan-schema=vh-fault-plan-v1"
    )


def _stdout_with_verdict(verdict: str, **header_kw: object) -> str:
    return f"{_header(**header_kw)}\n oracle contract: required_oracles=[demo]\n{verdict}\n"


def _write_executable(path: Path, source: str) -> Path:
    path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path.resolve()


def _pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _minimal_workspace(tmp_path: Path) -> tuple[Path, str, bytes]:
    target = tmp_path / "hello.py"
    original = b"# header\nold_value = 1\n# footer\n"
    target.write_bytes(original)
    diff = (
        "--- a/hello.py\n"
        "+++ b/hello.py\n"
        "@@ -1,3 +1,3 @@\n"
        " # header\n"
        "-old_value = 1\n"
        "+new_value = 2\n"
        " # footer\n"
    )
    return target, diff, original


def _fake_vh_script(behavior: str, capture: Path | None = None) -> str:
    capture_init = "None" if capture is None else f"Path({str(capture)!r})"
    return f"""
    #!/usr/bin/env python3
    import json, os, sys, time
    from pathlib import Path

    BEHAVIOR = {behavior!r}
    CAPTURE = {capture_init}

    def parse():
        workload, universes = "demo", "8"
        argv = sys.argv[1:]
        i = 0
        while i < len(argv):
            if argv[i] == "--workload" and i + 1 < len(argv):
                workload = argv[i + 1]; i += 2; continue
            if argv[i] == "--universes" and i + 1 < len(argv):
                universes = argv[i + 1]; i += 2; continue
            if argv[i] == "--seed" and i + 1 < len(argv):
                i += 2; continue
            i += 1
        return workload, universes

    def header(workload, universes, seed="0xd1ce", divergence="true"):
        return (
            f"vibe-halt: workload={{workload}} seed={{seed}} universes={{universes}} "
            f"palette=v0 divergence-check={{divergence}} schedule=fifo tape=false "
            f"fault-plan-schema=vh-fault-plan-v1"
        )

    def emit(workload, universes, verdict, code):
        sys.stdout.write(header(workload, universes) + "\\n")
        sys.stdout.write(verdict + "\\n")
        sys.stdout.flush()
        return code

    def main():
        workload, universes = parse()
        if CAPTURE is not None:
            CAPTURE.write_text(json.dumps({{
                "argv": sys.argv,
                "env": dict(os.environ),
                "cwd": os.getcwd(),
                "cwd_files": os.listdir("."),
                "stdin": sys.stdin.read(),
            }}), encoding="utf-8")
        if BEHAVIOR == "clean":
            return emit(workload, universes, "  verdict: CLEAN", 0)
        if BEHAVIOR == "findings":
            return emit(workload, universes, "  verdict: FINDINGS (see above)", 1)
        if BEHAVIOR == "unchecked":
            return emit(
                workload, universes,
                "  verdict: UNCHECKED (no findings, but the workload asserts no property contract — inconclusive)",
                3,
            )
        if BEHAVIOR == "exit0_only":
            sys.stdout.write("ok\\n")
            return 0
        if BEHAVIOR == "malformed_utf8":
            sys.stdout.buffer.write(b"\\xff\\xfe not utf8\\n")
            return 0
        if BEHAVIOR == "count":
            path = Path(sys.argv[0] + ".count")
            n = int(path.read_text()) if path.exists() else 0
            path.write_text(str(n + 1))
            return emit(workload, universes, "  verdict: CLEAN", 0)
        if BEHAVIOR == "hang":
            if CAPTURE is not None:
                Path(str(CAPTURE) + ".pid").write_text(
                    f"{{os.getpid()}} {{os.getpgid(0)}}", encoding="utf-8"
                )
            grandchild = os.fork()
            if grandchild == 0:
                os.execv("/bin/sleep", ["/bin/sleep", "60"])
            Path(str(CAPTURE) + ".child").write_text(str(grandchild), encoding="utf-8")
            time.sleep(60)
            return 0
        if BEHAVIOR == "overflow_stdout":
            if CAPTURE is not None:
                Path(str(CAPTURE) + ".pid").write_text(str(os.getpid()), encoding="utf-8")
            sys.stdout.buffer.write(b"x" * ({MAX_STREAM_BYTES} + 8))
            sys.stdout.buffer.flush()
            time.sleep(5)
            return 0
        if BEHAVIOR == "overflow_stderr":
            if CAPTURE is not None:
                Path(str(CAPTURE) + ".pid").write_text(str(os.getpid()), encoding="utf-8")
            sys.stderr.buffer.write(b"y" * ({MAX_STREAM_BYTES} + 8))
            sys.stderr.buffer.flush()
            time.sleep(5)
            return 0
        if BEHAVIOR == "both_streams":
            blob = (b"S" * 4096)
            err = (b"E" * 4096)
            for _ in range(40):
                sys.stdout.buffer.write(blob)
                sys.stderr.buffer.write(err)
                sys.stdout.buffer.flush()
                sys.stderr.buffer.flush()
            sys.stdout.buffer.write(b"\\n")
            sys.stdout.buffer.flush()
            return emit(workload, universes, "  verdict: CLEAN", 0)
        if BEHAVIOR == "signal":
            os.kill(os.getpid(), 9)
            return 0
        raise SystemExit("unknown behavior")

    if __name__ == "__main__":
        raise SystemExit(main())
    """


def _install_fake_vh(tmp_path: Path, behavior: str, capture: Path | None = None) -> Path:
    return _write_executable(tmp_path / f"vh-{behavior}", _fake_vh_script(behavior, capture))


def test_module_is_stdlib_only() -> None:
    tree = ast.parse(
        Path("dharma_swarm/vibe_halt_observer.py").read_text(encoding="utf-8")
    )
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    imported.discard("__future__")
    unexpected = sorted(imported - STDLIB_ROOTS)
    assert unexpected == []
    source = Path("dharma_swarm/vibe_halt_observer.py").read_text(encoding="utf-8")
    assert "subprocess.run" not in source
    assert "create_subprocess_shell" not in source
    assert "to_thread" not in source
    assert ".communicate(" not in source
    assert "dharma_swarm.sandbox" not in source
    assert "admit_proposal" not in source
    assert "clean=True" not in source


def test_public_api_has_no_clean_factory() -> None:
    import dharma_swarm.vibe_halt_observer as mod

    assert not hasattr(mod, "admit_proposal")
    names = [name for name in dir(mod) if "clean" in name.lower() and not name.startswith("_")]
    assert names == []


@pytest.mark.parametrize("value", [None, "", "off", " OFF "])
async def test_off_returns_before_malformed_optional_settings(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv("DHARMA_VH_OBSERVER", raising=False)
    else:
        monkeypatch.setenv("DHARMA_VH_OBSERVER", value)
    monkeypatch.setenv("DHARMA_VH_BIN", "not-absolute")
    monkeypatch.setenv("DHARMA_VH_WORKLOAD", "!!!")
    monkeypatch.setenv("DHARMA_VH_UNIVERSES", "nope")
    monkeypatch.setenv("DHARMA_VH_TIMEOUT_SECONDS", "0")
    assert await run_observer() is None


async def test_off_skips_lookup_and_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a, **_k):
        raise AssertionError("off mode must not look up or invoke vh")

    monkeypatch.setenv("DHARMA_VH_OBSERVER", "off")
    monkeypatch.setattr("dharma_swarm.vibe_halt_observer.shutil.which", boom)
    monkeypatch.setattr("dharma_swarm.vibe_halt_observer.os.stat", boom)
    monkeypatch.setattr("dharma_swarm.vibe_halt_observer.hashlib.sha256", boom)
    monkeypatch.setattr("dharma_swarm.vibe_halt_observer.asyncio.create_subprocess_exec", boom)
    monkeypatch.setattr("dharma_swarm.vibe_halt_observer.tempfile.TemporaryDirectory", boom)
    assert await run_observer() is None


async def test_unknown_mode_is_invalid_and_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a, **_k):
        raise AssertionError("invalid mode must not look up a binary")

    monkeypatch.setenv("DHARMA_VH_OBSERVER", "halt-please")
    monkeypatch.setenv("DHARMA_VH_BIN", "not-absolute")
    monkeypatch.setattr("dharma_swarm.vibe_halt_observer.shutil.which", boom)
    observation = await run_observer()
    assert observation is not None
    assert observation.mode == "invalid"
    assert observation.ran is False
    assert observation.blocks_apply is True
    assert observation.reported_outcome is ReportedOutcome.ERROR


async def test_invalid_optional_config_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_UNIVERSES", "0")
    observation = await run_observer()
    assert observation is not None
    assert observation.reported_outcome is ReportedOutcome.ERROR
    assert observation.ran is False
    assert observation.reason == "invalid_universes"
    assert observation.blocks_apply is False


@pytest.mark.parametrize(
    ("mode", "outcome", "blocked"),
    [
        (ObserverMode.OBSERVE, ReportedOutcome.CLEAN, False),
        (ObserverMode.OBSERVE, ReportedOutcome.FINDINGS, True),
        (ObserverMode.OBSERVE, ReportedOutcome.UNCHECKED, False),
        (ObserverMode.OBSERVE, ReportedOutcome.ERROR, False),
        (ObserverMode.OBSERVE, ReportedOutcome.MISSING, False),
        (ObserverMode.REQUIRE, ReportedOutcome.CLEAN, False),
        (ObserverMode.REQUIRE, ReportedOutcome.FINDINGS, True),
        (ObserverMode.REQUIRE, ReportedOutcome.UNCHECKED, True),
        (ObserverMode.REQUIRE, ReportedOutcome.ERROR, True),
        (ObserverMode.REQUIRE, ReportedOutcome.MISSING, True),
        (ObserverMode.INVALID, ReportedOutcome.ERROR, True),
    ],
)
def test_observe_require_policy_matrix(
    mode: ObserverMode, outcome: ReportedOutcome, blocked: bool
) -> None:
    assert _blocks_apply(mode, outcome) is blocked


async def test_defaults_are_demo_seed_and_eight_universes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    capture = tmp_path / "capture.json"
    binary = _install_fake_vh(tmp_path, "clean", capture)
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    observation = await run_observer()
    assert observation is not None
    assert observation.request["workload"] == DEFAULT_WORKLOAD == "demo"
    assert observation.request["seed"] == "0xD1CE"
    assert observation.request["universes"] == DEFAULT_UNIVERSES == 8
    dumped = json.loads(capture.read_text(encoding="utf-8"))
    assert dumped["argv"][1:] == [
        "run", "--workload", "demo", "--seed", "0xD1CE", "--universes", "8",
    ]
    assert "demo-buggy" not in dumped["argv"]


async def test_demo_buggy_is_never_implicit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    binary = _install_fake_vh(tmp_path, "clean")
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    observation = await run_observer()
    assert observation is not None
    assert observation.request["workload"] != "demo-buggy"


def test_parser_exact_header_clean_exit_zero_succeeds() -> None:
    outcome, reason = _parse_vh_run(
        _stdout_with_verdict("  verdict: CLEAN"),
        "",
        0,
        workload="demo",
        universes=8,
    )
    assert outcome is ReportedOutcome.CLEAN
    assert reason == "clean"


def test_parser_findings_exit_one_succeeds() -> None:
    outcome, reason = _parse_vh_run(
        _stdout_with_verdict("  verdict: FINDINGS (see above)"),
        "",
        1,
        workload="demo",
        universes=8,
    )
    assert outcome is ReportedOutcome.FINDINGS
    assert reason == "findings"


def test_parser_unchecked_exit_three_succeeds() -> None:
    outcome, reason = _parse_vh_run(
        _stdout_with_verdict(
            "  verdict: UNCHECKED (no findings, but the workload asserts no property contract — inconclusive)"
        ),
        "",
        3,
        workload="demo",
        universes=8,
    )
    assert outcome is ReportedOutcome.UNCHECKED
    assert reason == "unchecked"


def test_parser_exit_zero_without_clean_is_error() -> None:
    outcome, _reason = _parse_vh_run("ok\n", "", 0, workload="demo", universes=8)
    assert outcome is ReportedOutcome.ERROR


def test_parser_clean_with_exit_one_is_error() -> None:
    outcome, reason = _parse_vh_run(
        _stdout_with_verdict("  verdict: CLEAN"),
        "",
        1,
        workload="demo",
        universes=8,
    )
    assert outcome is ReportedOutcome.ERROR
    assert reason == "exit_mismatch"


def test_parser_findings_with_exit_zero_is_error() -> None:
    outcome, reason = _parse_vh_run(
        _stdout_with_verdict("  verdict: FINDINGS (see above)"),
        "",
        0,
        workload="demo",
        universes=8,
    )
    assert outcome is ReportedOutcome.ERROR
    assert reason == "exit_mismatch"


def test_parser_duplicate_header_is_error() -> None:
    text = _stdout_with_verdict("  verdict: CLEAN") + _header() + "\n"
    outcome, reason = _parse_vh_run(text, "", 0, workload="demo", universes=8)
    assert outcome is ReportedOutcome.ERROR
    assert reason == "duplicate_header"


def test_parser_duplicate_verdict_is_error() -> None:
    text = _stdout_with_verdict("  verdict: CLEAN") + "  verdict: CLEAN\n"
    outcome, reason = _parse_vh_run(text, "", 0, workload="demo", universes=8)
    assert outcome is ReportedOutcome.ERROR
    assert reason == "duplicate_verdict"


def test_parser_contradictory_verdict_is_error() -> None:
    text = (
        _stdout_with_verdict("  verdict: CLEAN")
        + "  verdict: FINDINGS (see above)\n"
    )
    outcome, reason = _parse_vh_run(text, "", 0, workload="demo", universes=8)
    assert outcome is ReportedOutcome.ERROR
    assert reason == "contradictory_verdict"


def test_parser_stderr_only_verdict_is_error() -> None:
    outcome, reason = _parse_vh_run(
        _header() + "\n",
        "  verdict: CLEAN\n",
        0,
        workload="demo",
        universes=8,
    )
    assert outcome is ReportedOutcome.ERROR
    assert reason == "stderr_verdict"


def test_parser_anchored_stderr_verdict_is_error() -> None:
    outcome, reason = _parse_vh_run(
        _stdout_with_verdict("  verdict: CLEAN"),
        "  verdict: CLEAN\n",
        0,
        workload="demo",
        universes=8,
    )
    assert outcome is ReportedOutcome.ERROR
    assert reason == "stderr_verdict"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"workload": "other"},
        {"seed": "0xd1cf"},
        {"universes": 7},
        {"divergence": "false"},
    ],
)
def test_parser_header_field_mismatch_is_error(kwargs: dict[str, object]) -> None:
    header_kw = {"workload": "demo", "seed": "0xd1ce", "universes": 8, "divergence": "true"}
    header_kw.update(kwargs)
    outcome, reason = _parse_vh_run(
        _stdout_with_verdict("  verdict: CLEAN", **header_kw),
        "",
        0,
        workload="demo",
        universes=8,
    )
    assert outcome is ReportedOutcome.ERROR
    assert reason == "header_mismatch"


def test_parser_uppercase_seed_is_numeric_match() -> None:
    outcome, _reason = _parse_vh_run(
        _stdout_with_verdict("  verdict: CLEAN", seed="0xD1CE"),
        "",
        0,
        workload="demo",
        universes=8,
    )
    assert outcome is ReportedOutcome.CLEAN
    assert DEFAULT_SEED == 0xD1CE


def test_parser_signal_termination_is_error() -> None:
    outcome, reason = _parse_vh_run(
        _stdout_with_verdict("  verdict: CLEAN"),
        "",
        -signal.SIGKILL,
        workload="demo",
        universes=8,
    )
    assert outcome is ReportedOutcome.ERROR
    assert reason == "signal_termination"


async def test_child_signal_termination_is_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    binary = _install_fake_vh(tmp_path, "signal")
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    observation = await run_observer()
    assert observation is not None
    assert observation.reported_outcome is ReportedOutcome.ERROR
    assert observation.reason == "signal_termination"
    assert observation.process["exit_code"] is not None
    assert observation.process["exit_code"] < 0


async def test_which_is_called_once_when_bin_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    binary = _install_fake_vh(tmp_path, "clean")
    calls: list[str] = []

    def fake_which(name: str) -> str | None:
        calls.append(name)
        return str(binary)

    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setattr("dharma_swarm.vibe_halt_observer.shutil.which", fake_which)
    observation = await run_observer()
    assert observation is not None
    assert observation.reported_outcome is ReportedOutcome.CLEAN
    assert calls == ["vh"]
    assert Path(observation.binary["resolved_path"]).is_absolute()


async def test_malformed_utf8_is_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    binary = _install_fake_vh(tmp_path, "malformed_utf8")
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    observation = await run_observer()
    assert observation is not None
    assert observation.reported_outcome is ReportedOutcome.ERROR
    assert observation.reason == "utf8_error"


async def test_truncated_or_overflowed_output_is_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    binary = _install_fake_vh(tmp_path, "overflow_stdout")
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    monkeypatch.setenv("DHARMA_VH_TIMEOUT_SECONDS", "5")
    observation = await run_observer()
    assert observation is not None
    assert observation.reported_outcome is ReportedOutcome.ERROR
    assert observation.reason == "output_overflow"
    assert observation.process["output_limited"] is True


async def test_uses_create_subprocess_exec_absolute_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    binary = _install_fake_vh(tmp_path, "count")
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    original = asyncio.create_subprocess_exec

    async def wrapped(*args, **kwargs):
        calls.append((args, kwargs))
        return await original(*args, **kwargs)

    async def no_shell(*_a, **_k):
        raise AssertionError("observer must not use a shell")

    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", wrapped)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", no_shell)
    observation = await run_observer()
    assert observation is not None
    assert observation.reported_outcome is ReportedOutcome.CLEAN
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert Path(str(args[0])).is_absolute()
    assert args[0] == str(binary)
    assert kwargs["start_new_session"] is True
    assert kwargs["stdin"] is asyncio.subprocess.DEVNULL
    count_path = Path(str(binary) + ".count")
    assert count_path.read_text(encoding="utf-8") == "1"


async def test_child_environment_excludes_parent_sentinel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    capture = tmp_path / "capture.json"
    binary = _install_fake_vh(tmp_path, "clean", capture)
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    monkeypatch.setenv("DHARMA_VH_PARENT_SENTINEL", "secret-parent-value")
    observation = await run_observer()
    assert observation is not None
    dumped = json.loads(capture.read_text(encoding="utf-8"))
    assert "DHARMA_VH_PARENT_SENTINEL" not in dumped["env"]
    assert dumped["env"]["LANG"] == "C"
    assert dumped["env"]["LC_ALL"] == "C"
    assert dumped["cwd_files"] == []
    workspace = tmp_path / "proposal-workspace"
    workspace.mkdir()
    assert Path(dumped["cwd"]) != workspace
    assert Path(dumped["cwd"]).is_absolute()


async def test_timeout_kills_and_reaps_leftover_child_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    capture = tmp_path / "hang"
    binary = _install_fake_vh(tmp_path, "hang", capture)
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    monkeypatch.setenv("DHARMA_VH_TIMEOUT_SECONDS", "1")
    observation = await run_observer()
    assert observation is not None
    assert observation.reason == "timeout"
    pid_text = Path(str(capture) + ".pid").read_text(encoding="utf-8").split()
    leader = int(pid_text[0])
    child = int(Path(str(capture) + ".child").read_text(encoding="utf-8"))
    await asyncio.sleep(0.2)
    assert not _pid_running(leader)
    assert not _pid_running(child)


async def test_cancellation_kills_and_reaps_leftover_child_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    capture = tmp_path / "cancel"
    binary = _install_fake_vh(tmp_path, "hang", capture)
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    monkeypatch.setenv("DHARMA_VH_TIMEOUT_SECONDS", "30")
    task = asyncio.create_task(run_observer())
    pid_path = Path(str(capture) + ".pid")
    child_path = Path(str(capture) + ".child")
    for _ in range(50):
        if pid_path.exists() and child_path.exists():
            break
        await asyncio.sleep(0.05)
    assert pid_path.exists()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    leader = int(pid_path.read_text(encoding="utf-8").split()[0])
    child = int(child_path.read_text(encoding="utf-8"))
    await asyncio.sleep(0.2)
    assert not _pid_running(leader)
    assert not _pid_running(child)


async def test_stdout_overflow_kills_and_reaps_leftover_child_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    capture = tmp_path / "overflow-out"
    binary = _install_fake_vh(tmp_path, "overflow_stdout", capture)
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    monkeypatch.setenv("DHARMA_VH_TIMEOUT_SECONDS", "5")
    observation = await run_observer()
    assert observation is not None
    assert observation.reason == "output_overflow"
    assert len(observation.process["stdout_tail"]) <= MAX_TAIL_BYTES
    leader = int(Path(str(capture) + ".pid").read_text(encoding="utf-8"))
    await asyncio.sleep(0.2)
    assert not _pid_running(leader)


async def test_stderr_overflow_kills_and_reaps_leftover_child_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    capture = tmp_path / "overflow-err"
    binary = _install_fake_vh(tmp_path, "overflow_stderr", capture)
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    monkeypatch.setenv("DHARMA_VH_TIMEOUT_SECONDS", "5")
    observation = await run_observer()
    assert observation is not None
    assert observation.reason == "output_overflow"
    assert len(observation.process["stderr_tail"]) <= MAX_TAIL_BYTES
    leader = int(Path(str(capture) + ".pid").read_text(encoding="utf-8"))
    await asyncio.sleep(0.2)
    assert not _pid_running(leader)


async def test_concurrent_stdout_stderr_do_not_deadlock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    binary = _install_fake_vh(tmp_path, "both_streams")
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    observation = await asyncio.wait_for(run_observer(), timeout=5)
    assert observation is not None
    assert observation.reported_outcome is ReportedOutcome.CLEAN
    assert len(observation.process["stdout_tail"]) <= MAX_TAIL_BYTES
    assert len(observation.process["stderr_tail"]) <= MAX_TAIL_BYTES


async def test_observe_findings_blocks_diff_without_mutation(
    engine: DarwinEngine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    target, diff, original = _minimal_workspace(workspace)
    marker = workspace / "RAN"
    binary = _install_fake_vh(tmp_path, "findings")
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    proposal = _safe_proposal(
        diff=diff,
        metadata={"keep_me": True, "note": "unrelated"},
    )
    proposal_out, results = await engine.apply_diff_and_test(
        proposal,
        test_command=f"{sys.executable} -c \"open('RAN','w').write('1')\"",
        workspace=workspace,
    )
    assert proposal_out.status is EvolutionStatus.REJECTED
    assert target.read_bytes() == original
    assert not marker.exists()
    assert results["pass_rate"] == 0.0
    assert results["observer_blocks_apply"] is True
    assert results["applied"] is False
    assert results["tests_run"] is False
    assert "rolled_back" not in results
    receipt = proposal_out.metadata["vibe_halt_observer"]
    assert receipt["schema"] == SCHEMA
    assert receipt["blocks_apply"] is True
    assert proposal_out.metadata["keep_me"] is True


async def test_require_missing_binary_blocks_diff_without_mutation(
    engine: DarwinEngine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    target, diff, original = _minimal_workspace(workspace)
    marker = workspace / "RAN"
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "require")
    monkeypatch.setattr("dharma_swarm.vibe_halt_observer.shutil.which", lambda _name: None)
    proposal = _safe_proposal(diff=diff, metadata={"keep_me": 1})
    proposal_out, results = await engine.apply_diff_and_test(
        proposal,
        test_command=f"{sys.executable} -c \"open('RAN','w').write('1')\"",
        workspace=workspace,
    )
    assert proposal_out.status is EvolutionStatus.REJECTED
    assert target.read_bytes() == original
    assert not marker.exists()
    assert results["pass_rate"] == 0.0
    assert results["observer_blocks_apply"] is True
    assert proposal_out.metadata["keep_me"] == 1


async def test_valid_clean_runs_existing_diff_path(
    engine: DarwinEngine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    target, diff, _original = _minimal_workspace(workspace)
    binary = _install_fake_vh(tmp_path, "clean")
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    proposal = _safe_proposal(diff=diff)
    _proposal_out, results = await engine.apply_diff_and_test(
        proposal,
        test_command="true",
        workspace=workspace,
    )
    assert results.get("observer_blocks_apply") is not True
    assert "new_value = 2" in target.read_text(encoding="utf-8")
    assert results["pass_rate"] == 1.0


async def test_observe_error_is_nonblocking_for_diff(
    engine: DarwinEngine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    target, diff, _original = _minimal_workspace(workspace)
    binary = _install_fake_vh(tmp_path, "exit0_only")
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    proposal = _safe_proposal(diff=diff)
    proposal_out, results = await engine.apply_diff_and_test(
        proposal,
        test_command="true",
        workspace=workspace,
    )
    assert proposal_out.status is not EvolutionStatus.REJECTED
    assert "new_value = 2" in target.read_text(encoding="utf-8")
    receipt = proposal_out.metadata["vibe_halt_observer"]
    assert receipt["reported_outcome"] == "error"
    assert receipt["blocks_apply"] is False
    assert results.get("observer_blocks_apply") is not True


async def test_off_missing_binary_keeps_existing_diff_behavior(
    engine: DarwinEngine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    target, diff, _original = _minimal_workspace(workspace)

    def boom(_name: str) -> str | None:
        raise AssertionError("off mode must not call which")

    monkeypatch.setattr("dharma_swarm.vibe_halt_observer.shutil.which", boom)
    proposal = _safe_proposal(diff=diff)
    _proposal_out, results = await engine.apply_diff_and_test(
        proposal, test_command="true", workspace=workspace
    )
    assert "new_value = 2" in target.read_text(encoding="utf-8")
    assert results["pass_rate"] == 1.0
    assert proposal.metadata is None or "vibe_halt_observer" not in (proposal.metadata or {})


async def test_child_has_no_proposal_context(
    engine: DarwinEngine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _target, diff, _original = _minimal_workspace(workspace)
    capture = tmp_path / "capture.json"
    binary = _install_fake_vh(tmp_path, "clean", capture)
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    secret = "unique-proposal-token-9f3a"
    proposal = _safe_proposal(
        component=f"secret-{secret}.py",
        description=f"change {secret}",
        diff=diff + f"# {secret}\n",
    )
    await engine.apply_diff_and_test(proposal, test_command="true", workspace=workspace)
    dumped = json.loads(capture.read_text(encoding="utf-8"))
    blob = json.dumps(dumped)
    assert secret not in blob
    assert secret not in dumped["stdin"]
    assert Path(dumped["cwd"]) != workspace
    assert dumped["cwd_files"] == []


async def test_findings_blocks_before_sandbox_construction(
    engine: DarwinEngine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    binary = _install_fake_vh(tmp_path, "findings")
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))

    def boom(*_a, **_k):
        raise AssertionError("sandbox must not be constructed")

    monkeypatch.setattr("dharma_swarm.sandbox.LocalSandbox", boom)
    proposal = _safe_proposal(diff="")
    proposal_out, sr = await engine.apply_in_sandbox(proposal, test_command="echo ran")
    assert proposal_out.status is EvolutionStatus.REJECTED
    assert sr.exit_code != 0
    assert sr.stdout == ""
    assert sr.timed_out is False
    assert sr.duration_seconds == 0.0
    parsed = DarwinEngine._parse_sandbox_result(sr)
    assert parsed["pass_rate"] == 0.0


async def test_require_missing_binary_blocks_before_sandbox_construction(
    engine: DarwinEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "require")
    monkeypatch.setattr("dharma_swarm.vibe_halt_observer.shutil.which", lambda _n: None)

    def boom(*_a, **_k):
        raise AssertionError("sandbox must not be constructed")

    monkeypatch.setattr("dharma_swarm.sandbox.LocalSandbox", boom)
    proposal = _safe_proposal(diff="")
    proposal_out, sr = await engine.apply_in_sandbox(proposal, test_command="echo ran")
    assert proposal_out.status is EvolutionStatus.REJECTED
    assert sr.stdout == ""
    assert sr.exit_code != 0


async def test_clean_permits_existing_sandbox_command(
    engine: DarwinEngine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    binary = _install_fake_vh(tmp_path, "clean")
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    proposal = _safe_proposal(diff="")
    _proposal_out, sr = await engine.apply_in_sandbox(
        proposal, test_command="echo 'test passed'", timeout=5.0
    )
    assert sr.exit_code == 0
    assert "test passed" in sr.stdout


async def test_observe_error_permits_existing_sandbox_command(
    engine: DarwinEngine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    binary = _install_fake_vh(tmp_path, "exit0_only")
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    proposal = _safe_proposal(diff="")
    proposal_out, sr = await engine.apply_in_sandbox(
        proposal, test_command="echo 'test passed'", timeout=5.0
    )
    assert sr.exit_code == 0
    receipt = proposal_out.metadata["vibe_halt_observer"]
    assert receipt["blocks_apply"] is False
    assert receipt["reported_outcome"] == "error"


async def test_off_preserves_sandbox_echo_behavior(engine: DarwinEngine) -> None:
    proposal = _safe_proposal(diff="")
    proposal_out, sr = await engine.apply_in_sandbox(
        proposal, test_command="echo 'test passed'", timeout=5.0
    )
    assert sr.exit_code == 0
    assert proposal_out.status == EvolutionStatus.TESTING


async def test_blocked_proposal_stays_rejected_after_evaluate(
    engine: DarwinEngine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _target, diff, _original = _minimal_workspace(workspace)
    binary = _install_fake_vh(tmp_path, "findings")
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_BIN", str(binary))
    before = engine._mutations_today
    proposal = _safe_proposal(diff=diff)
    proposal, results = await engine.apply_diff_and_test(
        proposal, test_command="true", workspace=workspace
    )
    assert engine._mutations_today == before
    evaluated = await engine.evaluate(proposal, test_results=results)
    assert evaluated.status is EvolutionStatus.REJECTED
    assert evaluated.actual_fitness is not None
    assert evaluated.actual_fitness.weighted() == 0.0
    assert evaluated.test_results["observer_blocks_apply"] is True
    assert evaluated.test_results["pass_rate"] == 0.0
    assert DarwinEngine._derive_archive_status(evaluated) == "gated"
    entry_id = await engine.archive_result(evaluated)
    assert evaluated.status is EvolutionStatus.ARCHIVED
    entry = await engine.archive.get_entry(entry_id)
    assert entry is not None
    assert entry.status == "gated"


async def test_stale_blocking_receipt_cannot_reject_later_success(
    engine: DarwinEngine,
) -> None:
    stale = {
        "schema": SCHEMA,
        "proposal_id": "old-id",
        "blocks_apply": True,
        "reported_outcome": "findings",
    }
    proposal = _safe_proposal(metadata={"vibe_halt_observer": stale})
    proposal.status = EvolutionStatus.GATED
    evaluated = await engine.evaluate(proposal, test_results={"pass_rate": 1.0})
    assert evaluated.status is EvolutionStatus.EVALUATED
    assert evaluated.test_results.get("observer_blocks_apply") is not True
    assert evaluated.test_results["pass_rate"] == 1.0

    reuse = _safe_proposal(metadata={"vibe_halt_observer": dict(stale)})
    reuse.id = "old-id"
    reuse.status = EvolutionStatus.GATED
    evaluated_reuse = await engine.evaluate(reuse, test_results={"pass_rate": 1.0})
    assert evaluated_reuse.status is EvolutionStatus.EVALUATED


@pytest.mark.skipif(not shutil.which("vh"), reason="vh not installed")
async def test_live_demo_reports_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    observation = await run_observer()
    assert observation is not None
    assert observation.process["exit_code"] == 0
    assert observation.reported_outcome is ReportedOutcome.CLEAN


@pytest.mark.skipif(not shutil.which("vh"), reason="vh not installed")
async def test_live_explicit_demo_buggy_reports_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DHARMA_VH_OBSERVER", "observe")
    monkeypatch.setenv("DHARMA_VH_WORKLOAD", "demo-buggy")
    observation = await run_observer()
    assert observation is not None
    assert observation.process["exit_code"] == 1
    assert observation.reported_outcome is ReportedOutcome.FINDINGS
