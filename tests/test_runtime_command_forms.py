"""Every liveness surface must recognise every real launch spelling.

Review on the liveness-oracle PR found the inverse bug: the sentinel and the
doctor knew only the module invocation (``-m dharma_swarm.dgc_cli
orchestrate-live``) while ``com.dharma.swarm.plist`` — the way the organism is
actually started on this host — execs the console script ``dgc
orchestrate-live``. A watchdog that reports a healthy host dead is worse than
no watchdog, so the command forms are pinned here against the real launch
definitions rather than against each other.
"""

from __future__ import annotations

import plistlib
from pathlib import Path

import scripts.runtime.organism_liveness_sentinel as sentinel
from dharma_swarm.doctor import _list_daemon_like_processes  # noqa: F401  (import guard)
from dharma_swarm.runtime_process_identity import (
    ORCHESTRATE_COMMAND_NEEDLES,
    daemon_pid_alive,
    looks_like_runtime_command,
    matches_orchestrate_command,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _plist_command() -> str:
    with (REPO_ROOT / "com.dharma.swarm.plist").open("rb") as handle:
        payload = plistlib.load(handle)
    args = payload["ProgramArguments"]
    return " ".join(str(a) for a in args)


def _release_runner_command() -> str:
    text = (REPO_ROOT / "scripts" / "runtime" / "dharma_swarm_release_runner.sh").read_text(
        encoding="utf-8"
    )
    lines = [ln for ln in text.splitlines() if "orchestrate-live" in ln]
    assert lines, "release runner no longer launches orchestrate-live"
    return " ".join(ln.strip() for ln in lines)


def _dockerfile_command() -> str:
    text = (REPO_ROOT / "Dockerfile.swarm").read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if "orchestrate_live" in ln]
    assert lines, "Dockerfile.swarm no longer launches orchestrate_live"
    return " ".join(ln.strip() for ln in lines)


def _observed_launch_commands() -> dict[str, str]:
    return {
        "com.dharma.swarm.plist": _plist_command(),
        "dharma_swarm_release_runner.sh": _release_runner_command(),
        "Dockerfile.swarm": _dockerfile_command(),
    }


def test_doctor_needles_match_every_real_launch_command() -> None:
    for source, command in _observed_launch_commands().items():
        assert matches_orchestrate_command(command), (
            f"{source} launches a command no doctor needle matches: {command!r} "
            f"(needles={ORCHESTRATE_COMMAND_NEEDLES})"
        )


def test_sentinel_forms_match_every_real_launch_command() -> None:
    for source, command in _observed_launch_commands().items():
        assert any(form in command for form in sentinel.ORCHESTRATE_COMMAND_FORMS), (
            f"{source} launches a command the sentinel cannot see: {command!r} "
            f"(forms={sentinel.ORCHESTRATE_COMMAND_FORMS})"
        )


def test_console_script_form_is_covered_by_both_matchers() -> None:
    """The exact regression: the plist's console-script spelling."""
    command = "/Users/dhyana/dharma_swarm/.venv/bin/python /Users/dhyana/dharma_swarm/.venv/bin/dgc orchestrate-live"

    assert matches_orchestrate_command(command)
    assert any(form in command for form in sentinel.ORCHESTRATE_COMMAND_FORMS)


def test_sentinel_forms_are_a_subset_of_the_package_needles() -> None:
    """The sentinel stays stdlib-only, so its copy is pinned here instead."""
    assert set(sentinel.ORCHESTRATE_COMMAND_FORMS) <= set(ORCHESTRATE_COMMAND_NEEDLES)


def test_unrelated_command_is_not_mistaken_for_the_organism() -> None:
    assert not matches_orchestrate_command("/usr/bin/vim notes.txt")
    assert not looks_like_runtime_command("/usr/bin/vim notes.txt")
    assert not any(
        form in "/usr/bin/vim notes.txt" for form in sentinel.ORCHESTRATE_COMMAND_FORMS
    )


def test_recycled_pid_is_not_reported_alive(monkeypatch) -> None:
    """kill -0 succeeds on a recycled pid; identity must still say dead."""
    monkeypatch.setattr(
        "dharma_swarm.runtime_process_identity.pid_alive", lambda pid: True
    )
    monkeypatch.setattr(
        "dharma_swarm.runtime_process_identity.pid_command",
        lambda pid, timeout=5.0: "/usr/bin/vim notes.txt",
    )

    assert daemon_pid_alive(4242) is False


def test_unreadable_command_never_downgrades_a_live_pid(monkeypatch) -> None:
    """No ps output must not manufacture a false death."""
    monkeypatch.setattr(
        "dharma_swarm.runtime_process_identity.pid_alive", lambda pid: True
    )
    monkeypatch.setattr(
        "dharma_swarm.runtime_process_identity.pid_command",
        lambda pid, timeout=5.0: None,
    )

    assert daemon_pid_alive(4242) is True


def test_live_orchestrator_pid_is_reported_alive(monkeypatch) -> None:
    monkeypatch.setattr(
        "dharma_swarm.runtime_process_identity.pid_alive", lambda pid: True
    )
    monkeypatch.setattr(
        "dharma_swarm.runtime_process_identity.pid_command",
        lambda pid, timeout=5.0: (
            "/Users/dhyana/dharma_swarm/.venv/bin/python "
            "/Users/dhyana/dharma_swarm/.venv/bin/dgc orchestrate-live"
        ),
    )

    assert daemon_pid_alive(4242) is True
