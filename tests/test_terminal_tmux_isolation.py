from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "terminal/scripts/lib/codex_managed_tmux.sh"
BOOT_SMOKE = ROOT / "terminal/scripts/boot_smoke.sh"
PTY_SMOKE = ROOT / "terminal/scripts/pty_smoke.sh"
ALTERNATE_SCREEN = ROOT / "terminal/scripts/alternate_screen_check.sh"
TERMINAL_GUARDIAN = ROOT / "scripts/terminal_guardian_preflight.sh"
TRACE_COLLAPSE = ROOT / "terminal/scripts/trace_collapse_check.sh"
ASSISTANT_EVENT = ROOT / "terminal/scripts/assistant_event_check.sh"
OFFLINE_QUEUE = ROOT / "terminal/scripts/offline_queue_check.sh"
SLASH_FEEDBACK = ROOT / "terminal/scripts/slash_feedback_check.sh"


def _build_harness_sandbox(tmp_path: Path, harness: Path) -> Path:
    sandbox = tmp_path / "harness-repo"
    required_files = (
        harness,
        HELPER,
        ROOT / "specs/DGC_TERMINAL_ARCHITECTURE_v1.1.md",
        ROOT / "dharma_swarm/terminal_bridge.py",
        ROOT / "terminal/scripts/stub_bridge.py",
    )
    for source in required_files:
        destination = sandbox / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    (sandbox / "terminal/node_modules").mkdir(parents=True)
    return sandbox / harness.relative_to(ROOT)


def _write_fake_tmux(tmp_path: Path) -> tuple[Path, Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log_path = tmp_path / "tmux.argv"
    fake = fake_bin / "tmux"
    fake.write_text(
        textwrap.dedent(
            """\
            #!/bin/sh
            {
              printf 'root=%s\\ttmux_env=%s' "${TMUX_TMPDIR-}" "${TMUX-}"
              for arg in "$@"; do
                printf '\\targ=%s' "$arg"
              done
              printf '\\n'
            } >>"$FAKE_TMUX_LOG"
            if [ "${FAKE_TMUX_REJECT_DEFAULT:-0}" = 1 ]; then
              if [ "$#" -lt 4 ] || [ "$1" != -L ] || [ "$3" != -f ] \
                || [ "$4" != /dev/null ]; then
                : >"$FAKE_TMUX_DEFAULT_CONTACT"
                exit 91
              fi
            fi
            socket_name=${2-}
            state_file="$FAKE_TMUX_STATE_DIR/$socket_name"
            focus_file="$state_file.focus"
            gate_file="$state_file.gate"
            read_state() {
              if [ -f "$state_file" ]; then
                cat "$state_file"
              else
                printf '0\n'
              fi
            }
            write_state() {
              printf '%s\n' "$1" >"$state_file"
            }
            read_focus() {
              if [ -f "$focus_file" ]; then
                cat "$focus_file"
              else
                printf 'composer\n'
              fi
            }
            write_focus() {
              printf '%s\n' "$1" >"$focus_file"
            }
            command_name=${5-}
            case "$command_name" in
              new-session|resize-window)
                width=
                height=
                next=
                command_arg=
                for arg in "$@"; do
                  command_arg=$arg
                  if [ "$next" = width ]; then width=$arg; next=; continue; fi
                  if [ "$next" = height ]; then height=$arg; next=; continue; fi
                  case "$arg" in
                    -x) next=width ;;
                    -y) next=height ;;
                  esac
                done
                if [ -n "$width" ] && [ -n "$height" ]; then
                  printf '%sx%s\n' "$width" "$height" >"$FAKE_TMUX_GEOMETRY"
                fi
                if [ "$command_name" = new-session ]; then
                  write_state 0
                  write_focus composer
                  case "$socket_name" in
                    CODEX_MANAGED_offline_queue_*)
                      printf '%s\n' "$command_arg" \
                        | sed -n "s/.*DHARMA_PYTHON='\\{0,1\\}\\([^ ']*\\)'\\{0,1\\}.*/\\1/p" >"$gate_file"
                      ;;
                  esac
                fi
                ;;
              has-session)
                case "$2" in
                  CODEX_MANAGED_boot_smoke_*|CODEX_MANAGED_pty_smoke_*) exit 1 ;;
                esac
                ;;
              capture-pane)
                state=$(read_state)
                case "$socket_name" in
                  CODEX_MANAGED_alternate_screen_*|CODEX_MANAGED_terminal_guardian_*)
                    printf 'Dharma Helm\n?/7 offline\n'
                    ;;
                  CODEX_MANAGED_trace_collapse_*)
                    printf 'Dharma Helm\nbridge ready\n'
                    case "$state" in
                      collapsed)
                        printf 'The Helm hears you loud and clear.\n'
                        printf '■ done · stub · ^T details\n'
                        ;;
                      expanded)
                        printf 'The Helm hears you loud and clear.\n'
                        printf 'weighing the reply\n'
                        printf '■ done · stub · ^T collapse\n'
                        ;;
                    esac
                    ;;
                  CODEX_MANAGED_assistant_event_*)
                    printf 'Dharma Helm\nbridge ready\n'
                    case "$state" in
                      turn1|turn2_prompted|turn2)
                        printf 'I am the Helm. Identity intents route straight through me.\n'
                        printf '■ done · stub · ^T details\n'
                        ;;
                    esac
                    if [ "$state" = turn2 ]; then
                      printf 'no response — turn ended without output\n'
                      printf '✖ failed · stub · ^T details\n'
                    fi
                    ;;
                  CODEX_MANAGED_offline_queue_*)
                    case "$state" in
                      queued)
                        printf 'Dharma Helm · bridge offline\n'
                        printf '> what is the helm\n'
                        printf '○ queued (backend offline) · stub · ^T details\n'
                        ;;
                      expanded)
                        printf 'Dharma Helm · bridge offline\n'
                        printf '> what is the helm\n'
                        printf '○ queued (backend offline) · stub · ^T details\n'
                        printf 'Status | queued (backend offline)\n'
                        ;;
                      recollapsed)
                        gate_path=$(cat "$gate_file")
                        if [ -L "$gate_path" ]; then
                          write_state resolved
                          printf 'Dharma Helm\nThe Helm hears you loud and clear.\n'
                          printf '■ done · stub · ^T details\n'
                        else
                          printf 'Dharma Helm · bridge offline\n'
                          printf '> what is the helm\n'
                          printf '○ queued (backend offline) · stub · ^T details\n'
                        fi
                        ;;
                      resolved)
                        printf 'Dharma Helm\nThe Helm hears you loud and clear.\n'
                        printf '■ done · stub · ^T details\n'
                        ;;
                      *) printf 'Dharma Helm · bridge offline\n' ;;
                    esac
                    ;;
                  CODEX_MANAGED_slash_feedback_*)
                    printf 'Dharma Helm · bridge offline\n'
                    case "$state" in
                      help|status_prompted|status)
                        printf '> /help\n'
                        printf '○ queued (backend offline) · stub · ^T details\n'
                        ;;
                    esac
                    if [ "$state" = status ]; then
                      printf '> /status\n'
                      printf '○ queued (backend offline) · stub · ^T details\n'
                    fi
                    ;;
                esac
                ;;
              send-keys)
                last_arg=
                for arg in "$@"; do last_arg=$arg; done
                state=$(read_state)
                focus=$(read_focus)
                if [ "$last_arg" = Escape ]; then
                  write_focus navigation
                  focus=navigation
                fi
                case "$socket_name" in
                  CODEX_MANAGED_trace_collapse_*)
                    if [ "$last_arg" = "what is the helm" ] && [ "$state" = 0 ]; then
                      write_state prompted
                    elif [ "$last_arg" = Enter ] && [ "$state" = prompted ]; then
                      write_state collapsed
                    elif [ "$last_arg" = C-t ] && [ "$focus" = navigation ]; then
                      case "$state" in
                        collapsed) write_state expanded ;;
                        expanded) write_state collapsed ;;
                      esac
                    fi
                    ;;
                  CODEX_MANAGED_assistant_event_*)
                    case "$last_arg:$state" in
                      "who are you and what can you do:0") write_state turn1_prompted ;;
                      "Enter:turn1_prompted") write_state turn1 ;;
                      "second question with no answer:turn1") write_state turn2_prompted ;;
                      "Enter:turn2_prompted") write_state turn2 ;;
                    esac
                    ;;
                  CODEX_MANAGED_offline_queue_*)
                    if [ "$last_arg" = "what is the helm" ] && [ "$state" = 0 ]; then
                      write_state prompted
                    elif [ "$last_arg" = Enter ] && [ "$state" = prompted ]; then
                      write_state queued
                    elif [ "$last_arg" = C-t ] && [ "$focus" = navigation ]; then
                      case "$state" in
                        queued) write_state expanded ;;
                        expanded) write_state recollapsed ;;
                      esac
                    fi
                    ;;
                  CODEX_MANAGED_slash_feedback_*)
                    case "$last_arg:$state" in
                      "/help:0") write_state help_prompted ;;
                      "Enter:help_prompted") write_state help ;;
                      "/status:help") write_state status_prompted ;;
                      "Enter:status_prompted") write_state status ;;
                    esac
                    ;;
                esac
                ;;
              display-message)
                case " $* " in
                  *" alternate=#{alternate_on} "*)
                    printf '%s alternate=1 dead=0\n' "$(cat "$FAKE_TMUX_GEOMETRY")"
                    ;;
                  *" #{pane_pid} "*) printf '999999\n' ;;
                  *" #{pid} "*) printf '999998\n' ;;
                  *) cat "$FAKE_TMUX_GEOMETRY" ;;
                esac
                ;;
            esac
            case " $* " in
              *" kill-server "*)
                if [ "${FAKE_TMUX_HANG:-0}" = 1 ]; then
                  exec "$FAKE_HANG_PYTHON" -c \
                    'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)'
                fi
                ;;
            esac
            exit 0
            """
        ),
        encoding="utf-8",
    )
    fake.chmod(0o755)
    fake_bun = fake_bin / "bun"
    fake_bun.write_text(
        "#!/bin/sh\n"
        "if [ \"${1-}\" = --version ]; then printf '1.3.11\\n'; fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake_bun.chmod(0o755)
    fake_mktemp = fake_bin / "mktemp"
    fake_mktemp.write_text(
        textwrap.dedent(
            """\
            #!/bin/sh
            : "${TMPDIR:?TMPDIR must name the fixture-local writable directory}"
            case "${1-}" in
              -d)
                path="$TMPDIR/fake-mktemp-dir-$$"
                mkdir -p "$path" || exit 1
                ;;
              *)
                path="$TMPDIR/fake-mktemp-file-$$"
                : >"$path" || exit 1
                ;;
            esac
            printf '%s\n' "$path" >>"$FAKE_MKTEMP_LOG"
            printf '%s\n' "$path"
            """
        ),
        encoding="utf-8",
    )
    fake_mktemp.chmod(0o755)
    return fake_bin, log_path


def _fake_env(tmp_path: Path, fake_bin: Path, log_path: Path) -> dict[str, str]:
    runtime_tmp = (tmp_path / "runtime-tmp").resolve()
    runtime_tmp.mkdir()
    state_dir = (tmp_path / "tmux-state").resolve()
    state_dir.mkdir()
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["FAKE_TMUX_LOG"] = str(log_path)
    env["FAKE_TMUX_DEFAULT_CONTACT"] = str(tmp_path / "default-contact")
    env["FAKE_TMUX_GEOMETRY"] = str(tmp_path / "tmux.geometry")
    env["FAKE_TMUX_STATE_DIR"] = str(state_dir)
    env["FAKE_HANG_PYTHON"] = sys.executable
    env["FAKE_MKTEMP_LOG"] = str(tmp_path / "mktemp.paths")
    env["TMPDIR"] = str(runtime_tmp)
    env["TMUX_TMPDIR"] = str(tmp_path / "tmux-root")
    env["TMUX"] = "/tmp/operator-default,4242,0"
    return env


@pytest.mark.parametrize(
    ("harness", "purpose", "overrides", "expected_exit", "expected_output"),
    [
        pytest.param(
            BOOT_SMOKE,
            "boot_smoke",
            {
                "BOOT_SMOKE_EXIT_TIMEOUT": "1",
                "BOOT_SMOKE_START_CMD": "true",
                "BOOT_SMOKE_TIMEOUT": "1",
            },
            1,
            "captured frame is empty",
            id="boot-smoke",
        ),
        pytest.param(
            PTY_SMOKE,
            "pty_smoke",
            {
                "PTY_SMOKE_ECHO_TIMEOUT": "1",
                "PTY_SMOKE_EXIT_TIMEOUT": "1",
                "PTY_SMOKE_START_CMD": "true",
                "PTY_SMOKE_TIMEOUT": "1",
            },
            1,
            "app never rendered interactive frame",
            id="pty-smoke",
        ),
        pytest.param(
            ALTERNATE_SCREEN,
            "alternate_screen",
            {},
            0,
            "alternate_screen_check: OK",
            id="alternate-screen",
        ),
        pytest.param(
            TERMINAL_GUARDIAN,
            "terminal_guardian",
            {},
            1,
            "terminal bridge was not running",
            id="terminal-guardian",
        ),
    ],
)
def test_target_harnesses_use_only_managed_calls(
    tmp_path: Path,
    harness: Path,
    purpose: str,
    overrides: dict[str, str],
    expected_exit: int,
    expected_output: str,
) -> None:
    fake_bin, log_path = _write_fake_tmux(tmp_path)
    env = _fake_env(tmp_path, fake_bin, log_path)
    sandboxed_harness = _build_harness_sandbox(tmp_path, harness)
    env.update(overrides)
    env["FAKE_TMUX_REJECT_DEFAULT"] = "1"

    completed = subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", str(sandboxed_harness)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert not Path(env["FAKE_TMUX_DEFAULT_CONTACT"]).exists(), (
        f"{purpose} contacted the default tmux server"
    )
    assert completed.returncode == expected_exit, completed.stderr
    assert expected_output in f"{completed.stdout}\n{completed.stderr}"

    calls = [line.split("\t") for line in log_path.read_text().splitlines()]
    assert any("arg=new-session" in call for call in calls)
    for call in calls:
        assert call[:6] == [
            f"root={env['TMUX_TMPDIR']}",
            "tmux_env=",
            "arg=-L",
            call[3],
            "arg=-f",
            "arg=/dev/null",
        ]
        assert re.fullmatch(rf"arg=CODEX_MANAGED_{purpose}_[0-9]+", call[3])


@pytest.mark.parametrize(
    ("harness", "purpose", "dimensions", "overrides", "expected_output"),
    [
        pytest.param(
            TRACE_COLLAPSE,
            "trace_collapse",
            "100x30",
            {},
            "trace_collapse_check: OK",
            id="trace-collapse",
        ),
        pytest.param(
            ASSISTANT_EVENT,
            "assistant_event",
            "100x30",
            {},
            "assistant_event_check: OK",
            id="assistant-event",
        ),
        pytest.param(
            OFFLINE_QUEUE,
            "offline_queue",
            "120x40",
            {
                "OFFLINE_QUEUE_OBSERVE_SECONDS": "0",
                "OFFLINE_QUEUE_POST_TOGGLE_PAUSE": "0",
                "OFFLINE_QUEUE_RECONNECT_ATTEMPTS": "2",
                "OFFLINE_QUEUE_RECONNECT_PAUSE": "0",
            },
            "offline_queue_check: OK",
            id="offline-queue",
        ),
        pytest.param(
            SLASH_FEEDBACK,
            "slash_feedback",
            "120x40",
            {},
            "slash_feedback_check: OK",
            id="slash-feedback",
        ),
    ],
)
def test_e2e_harnesses_use_only_managed_calls(
    tmp_path: Path,
    harness: Path,
    purpose: str,
    dimensions: str,
    overrides: dict[str, str],
    expected_output: str,
) -> None:
    fake_bin, log_path = _write_fake_tmux(tmp_path)
    env = _fake_env(tmp_path, fake_bin, log_path)
    sandboxed_harness = _build_harness_sandbox(tmp_path, harness)
    env.update(overrides)
    env["FAKE_TMUX_REJECT_DEFAULT"] = "1"

    completed = subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", str(sandboxed_harness)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )

    assert not Path(env["FAKE_TMUX_DEFAULT_CONTACT"]).exists(), (
        f"{purpose} contacted the default tmux server"
    )
    assert completed.returncode == 0, completed.stderr
    assert expected_output in completed.stdout
    assert Path(env["FAKE_TMUX_GEOMETRY"]).read_text().strip() == dimensions
    created_paths = [
        Path(line) for line in Path(env["FAKE_MKTEMP_LOG"]).read_text().splitlines()
    ]
    assert created_paths
    assert all(not path.exists() for path in created_paths)

    calls = [line.split("\t") for line in log_path.read_text().splitlines()]
    command_sequence = [call[6].removeprefix("arg=") for call in calls]
    commands = set(command_sequence)
    assert {
        "new-session",
        "set-option",
        "resize-window",
        "display-message",
        "capture-pane",
        "send-keys",
        "kill-server",
    } <= commands
    setup_end = max(
        command_sequence.index("new-session"),
        command_sequence.index("set-option"),
        command_sequence.index("resize-window"),
        command_sequence.index("display-message"),
    )
    first_journey_action = min(
        command_sequence.index("capture-pane"),
        command_sequence.index("send-keys"),
    )
    assert setup_end < first_journey_action
    assert command_sequence[-1] == "kill-server"
    new_session_call = calls[command_sequence.index("new-session")]
    assert any(field.startswith("arg=sleep 1;") for field in new_session_call)
    for call in calls:
        assert call[:6] == [
            f"root={env['TMUX_TMPDIR']}",
            "tmux_env=",
            "arg=-L",
            call[3],
            "arg=-f",
            "arg=/dev/null",
        ]
        assert re.fullmatch(rf"arg=CODEX_MANAGED_{purpose}_[0-9]+", call[3])


@pytest.mark.parametrize(
    ("harness", "purpose", "overrides"),
    [
        pytest.param(TRACE_COLLAPSE, "trace_collapse", {}, id="trace-collapse"),
        pytest.param(ASSISTANT_EVENT, "assistant_event", {}, id="assistant-event"),
        pytest.param(
            OFFLINE_QUEUE,
            "offline_queue",
            {
                "OFFLINE_QUEUE_OBSERVE_SECONDS": "0",
                "OFFLINE_QUEUE_POST_TOGGLE_PAUSE": "0",
                "OFFLINE_QUEUE_RECONNECT_ATTEMPTS": "2",
                "OFFLINE_QUEUE_RECONNECT_PAUSE": "0",
            },
            id="offline-queue",
        ),
        pytest.param(SLASH_FEEDBACK, "slash_feedback", {}, id="slash-feedback"),
    ],
)
def test_e2e_harnesses_fail_and_preserve_state_when_cleanup_hangs(
    tmp_path: Path,
    harness: Path,
    purpose: str,
    overrides: dict[str, str],
) -> None:
    fake_bin, log_path = _write_fake_tmux(tmp_path)
    env = _fake_env(tmp_path, fake_bin, log_path)
    sandboxed_harness = _build_harness_sandbox(tmp_path, harness)
    env.update(overrides)
    env["FAKE_TMUX_REJECT_DEFAULT"] = "1"
    env["FAKE_TMUX_HANG"] = "1"

    completed = subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", str(sandboxed_harness)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=25,
    )

    assert not Path(env["FAKE_TMUX_DEFAULT_CONTACT"]).exists(), (
        f"{purpose} contacted the default tmux server"
    )
    assert completed.returncode == 1, completed.stderr
    assert ": OK" not in completed.stdout
    assert (
        "kill-server timed out; refusing to unlink a potentially live socket"
        in completed.stderr
    )
    assert "preserv" in completed.stderr.lower()

    created_paths = [
        Path(line) for line in Path(env["FAKE_MKTEMP_LOG"]).read_text().splitlines()
    ]
    assert created_paths
    assert all(path.exists() for path in created_paths)

    calls = [line.split("\t") for line in log_path.read_text().splitlines()]
    command_sequence = [call[6].removeprefix("arg=") for call in calls]
    # After a hung kill-server, cleanup probes server liveness before refusing.
    assert command_sequence[-2:] == ["kill-server", "list-sessions"]
    for call in calls:
        assert re.fullmatch(rf"arg=CODEX_MANAGED_{purpose}_[0-9]+", call[3])


def test_fake_tmux_observes_private_socket_and_frozen_root(tmp_path: Path) -> None:
    fake_bin, log_path = _write_fake_tmux(tmp_path)
    env = _fake_env(tmp_path, fake_bin, log_path)
    frozen_root = Path(env["TMUX_TMPDIR"])
    frozen_root.mkdir()
    script = textwrap.dedent(
        """\
        set -eu
        source "$1"
        codex_managed_tmux_init fake_probe
        saved_socket="$CODEX_MANAGED_TMUX_SOCKET"
        socket_dir="$CODEX_MANAGED_TMUX_ROOT/tmux-$(id -u)"
        mkdir -p "$socket_dir"
        : >"$socket_dir/$saved_socket"
        : >"$socket_dir/CODEX_MANAGED_fake_probe_999999"
        TMUX_TMPDIR="$socket_dir/drifted"
        export TMUX_TMPDIR
        codex_managed_tmux new-session -d -s probe -x 80 -y 24 'sleep 1'
        codex_managed_tmux_cleanup
        test ! -e "$socket_dir/$saved_socket"
        test -e "$socket_dir/CODEX_MANAGED_fake_probe_999999"
        printf '%s\\n' "$saved_socket"
        """
    )
    completed = subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-c", script, "bash", str(HELPER)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    socket = completed.stdout.strip()
    assert re.fullmatch(r"CODEX_MANAGED_fake_probe_[0-9]+", socket)

    calls = [line.split("\t") for line in log_path.read_text().splitlines()]
    assert len(calls) == 2
    for call in calls:
        assert call[:6] == [
            f"root={frozen_root}",
            "tmux_env=",
            "arg=-L",
            f"arg={socket}",
            "arg=-f",
            "arg=/dev/null",
        ]
    assert calls[0][6:8] == ["arg=new-session", "arg=-d"]
    assert calls[1][6:] == ["arg=kill-server"]
    neighbor = frozen_root / f"tmux-{os.getuid()}" / "CODEX_MANAGED_fake_probe_999999"
    assert neighbor.exists()


@pytest.mark.parametrize(
    "purpose",
    ["", "Uppercase", "9prefix", "two-words", "../escape", "under score"],
)
def test_invalid_purposes_fail_without_publishing_owner(
    tmp_path: Path, purpose: str
) -> None:
    fake_bin, log_path = _write_fake_tmux(tmp_path)
    env = _fake_env(tmp_path, fake_bin, log_path)
    script = textwrap.dedent(
        """\
        source "$1"
        if codex_managed_tmux_init "$2"; then
          exit 9
        fi
        test -z "$CODEX_MANAGED_TMUX_PURPOSE"
        test -z "$CODEX_MANAGED_TMUX_OWNER_PID"
        test -z "$CODEX_MANAGED_TMUX_SOCKET"
        test -z "$CODEX_MANAGED_TMUX_ROOT"
        codex_managed_tmux_cleanup
        """
    )
    completed = subprocess.run(
        [
            "/bin/bash",
            "--noprofile",
            "--norc",
            "-c",
            script,
            "bash",
            str(HELPER),
            purpose,
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert not log_path.exists()


def test_relative_tmux_root_fails_without_publishing_owner(tmp_path: Path) -> None:
    fake_bin, log_path = _write_fake_tmux(tmp_path)
    env = _fake_env(tmp_path, fake_bin, log_path)
    env["TMUX_TMPDIR"] = "relative/root"
    script = textwrap.dedent(
        """\
        source "$1"
        if codex_managed_tmux_init relative_root; then
          exit 9
        fi
        test -z "$CODEX_MANAGED_TMUX_PURPOSE"
        test -z "$CODEX_MANAGED_TMUX_OWNER_PID"
        test -z "$CODEX_MANAGED_TMUX_SOCKET"
        test -z "$CODEX_MANAGED_TMUX_ROOT"
        codex_managed_tmux_cleanup
        """
    )
    completed = subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-c", script, "bash", str(HELPER)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert not log_path.exists()


def test_tampered_owner_cannot_invoke_tmux_or_unlink_socket(tmp_path: Path) -> None:
    fake_bin, log_path = _write_fake_tmux(tmp_path)
    env = _fake_env(tmp_path, fake_bin, log_path)
    Path(env["TMUX_TMPDIR"]).mkdir()
    script = textwrap.dedent(
        """\
        set -u
        source "$1"
        codex_managed_tmux_init owner_check
        socket_dir="$CODEX_MANAGED_TMUX_ROOT/tmux-$(id -u)"
        mkdir -p "$socket_dir"
        CODEX_MANAGED_TMUX_OWNER_PID=999999
        CODEX_MANAGED_TMUX_SOCKET=CODEX_MANAGED_owner_check_999999
        victim="$socket_dir/$CODEX_MANAGED_TMUX_SOCKET"
        : >"$victim"
        if codex_managed_tmux_cleanup; then
          exit 9
        fi
        test -e "$victim"
        """
    )
    completed = subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-c", script, "bash", str(HELPER)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert not log_path.exists()


def test_cleanup_is_bounded_and_keeps_socket_when_kill_server_hangs(
    tmp_path: Path,
) -> None:
    fake_bin, log_path = _write_fake_tmux(tmp_path)
    env = _fake_env(tmp_path, fake_bin, log_path)
    env["FAKE_TMUX_HANG"] = "1"
    Path(env["TMUX_TMPDIR"]).mkdir()
    script = textwrap.dedent(
        """\
        set -u
        source "$1"
        codex_managed_tmux_init bounded_cleanup
        socket_dir="$CODEX_MANAGED_TMUX_ROOT/tmux-$(id -u)"
        mkdir -p "$socket_dir"
        victim="$socket_dir/$CODEX_MANAGED_TMUX_SOCKET"
        : >"$victim"
        if codex_managed_tmux_cleanup; then
          exit 9
        fi
        test -e "$victim"
        """
    )
    started = time.monotonic()
    completed = subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-c", script, "bash", str(HELPER)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=6,
    )
    elapsed = time.monotonic() - started
    assert completed.returncode == 0, completed.stderr
    assert elapsed < 5
    assert "refusing to unlink" in completed.stderr
    assert "arg=kill-server" in log_path.read_text()


def test_real_private_80x24_probe_leaves_sandboxed_default_server_unchanged() -> None:
    tmux = shutil.which("tmux")
    if tmux is None:
        pytest.skip("tmux is required for the real private-server probe")

    # Darwin's Unix-domain socket path limit is short; pytest's nested tmp_path
    # can exceed it before tmux adds /tmux-UID/SOCKET.
    tmux_root = Path(tempfile.mkdtemp(prefix="helm-tmux-", dir="/tmp"))
    env = os.environ.copy()
    env["TMUX_TMPDIR"] = str(tmux_root)
    env.pop("TMUX", None)

    def default_tmux(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [tmux, "-f", "/dev/null", *args],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

    created = default_tmux(
        "new-session",
        "-d",
        "-s",
        "default-sentinel",
        "-x",
        "91",
        "-y",
        "31",
        "sleep 30",
    )
    try:
        assert created.returncode == 0, created.stderr
        before = default_tmux("list-sessions", "-F", "#{session_name}:#{window_width}x#{window_height}")
        assert before.returncode == 0, before.stderr
        script = textwrap.dedent(
            """\
            set -eu
            source "$1"
            codex_managed_tmux_init real_probe
            trap 'codex_managed_tmux_cleanup || true' EXIT
            saved_socket="$CODEX_MANAGED_TMUX_SOCKET"
            codex_managed_tmux new-session -d -s managed -x 80 -y 24 'sleep 30'
            codex_managed_tmux set-option -g status off
            codex_managed_tmux resize-window -t managed:0 -x 80 -y 24
            dimensions=$(codex_managed_tmux display-message -p -t managed:0.0 \
              '#{pane_width}x#{pane_height}')
            test "$dimensions" = 80x24
            server_pid=$(codex_managed_tmux display-message -p '#{pid}')
            pane_pid=$(codex_managed_tmux display-message -p -t managed:0.0 '#{pane_pid}')
            codex_managed_tmux_cleanup
            printf '%s\\n%s\\n%s\\n%s\\n' \
              "$saved_socket" "$dimensions" "$server_pid" "$pane_pid"
            """
        )
        probe = subprocess.run(
            ["/bin/bash", "--noprofile", "--norc", "-c", script, "bash", str(HELPER)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        assert probe.returncode == 0, probe.stderr
        socket, dimensions, server_pid_text, pane_pid_text = probe.stdout.splitlines()
        assert dimensions == "80x24"
        assert re.fullmatch(r"CODEX_MANAGED_real_probe_[0-9]+", socket)
        private_socket = tmux_root / f"tmux-{os.getuid()}" / socket
        assert not private_socket.exists()
        for pid_text in (server_pid_text, pane_pid_text):
            pid = int(pid_text)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.02)
            else:
                pytest.fail(f"managed tmux process {pid} survived cleanup")

        after = default_tmux("list-sessions", "-F", "#{session_name}:#{window_width}x#{window_height}")
        assert after.returncode == 0, after.stderr
        assert after.stdout == before.stdout
        assert "default-sentinel" in after.stdout
    finally:
        if created.returncode == 0:
            default_tmux("kill-server")
        shutil.rmtree(tmux_root, ignore_errors=True)
