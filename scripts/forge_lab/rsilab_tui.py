#!/usr/bin/env python3
"""Operator menu for one supervised RSI Lab round on Meghadharma.

This is a remote control, not a second runner. Campaign mutations go through
ssh to the existing Megha binaries. n50 is refused until a VALID child digest
exists and the operator raises the 1x1x1 policy separately.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


REMOTE = "meghadharma"
REMOTE_RSI = "/root/rsi-lab/bin/rsi"
REMOTE_EXPLORE = "/root/rsi-lab/bin/rsi-unattended-explore"
FUSE_SECONDS = 2700
RUN_USD = 1.25
N50_RE = re.compile(r"(?i)(\bn50\b|--generations\s*50|--children\s*50|--tasks\s*50)")
MENU_COMMANDS = {"status", "models", "run", "halt", "menu"}
ROLES = ("mutator", "solver", "verifier")
TERMINAL_SUCCESS = {"measured_negative", "inconclusive_low_power"}


class MenuError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_cli_json(raw: str) -> dict[str, Any]:
    text = raw[raw.find("{") :] if "{" in raw else ""
    if not text.strip():
        raise MenuError("JSON_MISSING", "remote command returned no JSON")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise MenuError("JSON_SHAPE", "remote JSON was not an object")
    return payload


def unwrap(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = payload.get("result")
    return result if isinstance(result, dict) else dict(payload)


def _checks(daily: Mapping[str, Any]) -> dict[str, Any]:
    checks = daily.get("checks")
    return checks if isinstance(checks, dict) else {}


def last_attempt(daily: Mapping[str, Any]) -> dict[str, Any]:
    last = _checks(daily).get("last_unattended")
    if not isinstance(last, dict):
        return {}
    attempt = last.get("attempt")
    return attempt if isinstance(attempt, dict) else {}


def role_lines(daily: Mapping[str, Any]) -> list[str]:
    models = _checks(daily).get("models")
    bindings: Any = []
    if isinstance(models, dict):
        bindings = models.get("role_bindings") or []
    if isinstance(bindings, dict):
        bindings = [
            {"role": key, **(value if isinstance(value, dict) else {"model_id": value})}
            for key, value in bindings.items()
        ]
    lines = []
    for row in bindings:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or "?")
        provider = str(row.get("provider") or "?")
        model = str(row.get("model_id") or row.get("model") or "?")
        lines.append(f"{role}: {provider} / {model}")
    return lines


@dataclass(frozen=True)
class StatusView:
    verdict: str
    run_id: str
    digest: str | None
    modality: str
    returncode: object
    wall_seconds: object
    ready_for_next_run: bool
    last_cycle_healthy: bool
    halt_absent: bool
    halt_path: str
    timer_installed: bool
    admission_ready: bool
    silent_death: bool
    why: str
    roles: tuple[str, ...]

    def banner(self) -> str:
        digest = self.digest or "null"
        halt = "absent" if self.halt_absent else "PRESENT"
        timer = "installed" if self.timer_installed else "not installed"
        lines = [
            "RSILAB  ·  Meghadharma campaign  ·  EXPLORE_ONLY",
            f"verdict: {self.verdict}",
            f"run_id: {self.run_id or '—'}",
            f"child_result_digest: {digest}",
            f"modality: {self.modality}   rc={self.returncode}   wall_s={self.wall_seconds}",
            f"why: {self.why}",
            f"ready_for_next_run={self.ready_for_next_run}  last_cycle_healthy={self.last_cycle_healthy}",
            f"HALT={halt}  timer={timer}  admission_ready={self.admission_ready}",
            "roles:",
        ]
        lines.extend(f"  {line}" for line in self.roles or ("(none in daily projection)",))
        lines.append("n50: refused until one VALID digest exists and policy is raised.")
        return "\n".join(lines)


def summarize_daily(payload: Mapping[str, Any]) -> StatusView:
    daily = unwrap(payload)
    checks = _checks(daily)
    last = checks.get("last_unattended") if isinstance(checks.get("last_unattended"), dict) else {}
    attempt = last_attempt(daily)
    readiness = last.get("readiness") if isinstance(last, dict) else {}
    if not isinstance(readiness, dict):
        readiness = {}
    halt = checks.get("halt") if isinstance(checks.get("halt"), dict) else {}
    scheduler = checks.get("scheduler") if isinstance(checks.get("scheduler"), dict) else {}
    units = scheduler.get("units") if isinstance(scheduler.get("units"), dict) else {}
    timer = units.get("rsi-lab-explore.timer") if isinstance(units.get("rsi-lab-explore.timer"), dict) else {}
    admission = checks.get("admission") if isinstance(checks.get("admission"), dict) else {}
    digest = attempt.get("child_result_digest")
    digest_s = str(digest) if isinstance(digest, str) and digest else None
    modality = str(attempt.get("epistemic_modality") or "unknown")
    closeout = str(attempt.get("explore_closeout_state") or attempt.get("closeout_state") or "")
    terminal = bool(readiness.get("terminal_success"))
    present = bool(attempt.get("run_id"))
    silent = bool(present and digest_s is None)
    if not present:
        verdict, why = "NONE", "no unattended closeout yet"
    elif terminal and digest_s and closeout in TERMINAL_SUCCESS:
        verdict, why = "VALID", f"typed closeout {closeout}"
    elif digest_s and closeout in TERMINAL_SUCCESS:
        verdict, why = "VALID", f"digest present · {closeout}"
    elif silent:
        verdict, why = "REJECT", "silent death: child_result.json missing or validator-null"
        if modality and modality != "unknown":
            why = f"{why} · {modality}"
    else:
        verdict, why = "REJECT", modality or "closeout did not meet 1x1x1 validator"
        if closeout:
            why = f"{why} · closeout_state={closeout}"
    return StatusView(
        verdict=verdict,
        run_id=str(attempt.get("run_id") or ""),
        digest=digest_s,
        modality=modality,
        returncode=attempt.get("returncode"),
        wall_seconds=attempt.get("wall_seconds"),
        ready_for_next_run=bool(daily.get("ready_for_next_run")),
        last_cycle_healthy=bool(daily.get("last_cycle_healthy")),
        halt_absent=bool(halt.get("absent", True)),
        halt_path=str(halt.get("path") or ""),
        timer_installed=bool(timer.get("installed_digest")),
        admission_ready=bool(admission.get("ready")),
        silent_death=silent,
        why=why,
        roles=tuple(role_lines(daily)),
    )


def selectable_routes(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = unwrap(payload)
    routes = result.get("routes")
    if not isinstance(routes, list):
        return []
    out: list[dict[str, Any]] = []
    for row in routes:
        if not isinstance(row, dict):
            continue
        if row.get("runtime_selectable") is not True:
            continue
        if row.get("runtime_blocker"):
            continue
        out.append(row)
    return out


def format_routes(routes: Sequence[Mapping[str, Any]]) -> str:
    lines = []
    for index, row in enumerate(routes, start=1):
        floor = "  BELOW_FLOOR" if row.get("below_floor") else ""
        lines.append(
            f"{index:3d}  {row.get('provider')} / {row.get('model_id')}  "
            f"[{row.get('tier') or '?'}]{floor}"
        )
    return "\n".join(lines) if lines else "(no runtime_selectable routes)"


def refuse_scale(argv: Sequence[str]) -> str | None:
    joined = " ".join(argv)
    if N50_RE.search(joined):
        return "n50 is refused. Run 1 until child_result_digest is a sha256, then raise policy separately."
    for token in argv:
        lowered = token.lower()
        if lowered in {"n20", "n3", "soak", "diverse"} or lowered.startswith("n") and lowered[1:].isdigit():
            if lowered in {"n1", "n"}:
                continue
            if lowered[1:].isdigit() and int(lowered[1:]) > 1:
                return (
                    f"{token} is refused on the live lane (1 generation x 1 child x 1 task). "
                    "Use: RSILAB run"
                )
    return None


class Transport:
    def json(self, remote_command: str, *, timeout: int = 45) -> dict[str, Any]:
        raise NotImplementedError

    def stream(self, remote_command: str, *, timeout: int) -> int:
        raise NotImplementedError

    def raw(self, remote_command: str, *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        raise NotImplementedError


class SshTransport(Transport):
    def __init__(self, host: str = REMOTE) -> None:
        self.host = host

    def _ssh(self, remote_command: str, *, timeout: int, stream: bool) -> subprocess.CompletedProcess[str]:
        argv = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=20",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ServerAliveCountMax=20",
            self.host,
            remote_command,
        ]
        if stream:
            return subprocess.run(argv, timeout=timeout)
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)

    def json(self, remote_command: str, *, timeout: int = 45) -> dict[str, Any]:
        completed = self._ssh(remote_command, timeout=timeout, stream=False)
        blob = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode != 0 and "{" not in blob:
            raise MenuError(
                "SSH_FAILED",
                f"ssh {self.host} rc={completed.returncode}: {blob[-400:]}",
            )
        return parse_cli_json(blob)

    def stream(self, remote_command: str, *, timeout: int) -> int:
        completed = self._ssh(remote_command, timeout=timeout, stream=True)
        return int(completed.returncode)

    def raw(self, remote_command: str, *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        return self._ssh(remote_command, timeout=timeout, stream=False)


def load_status(transport: Transport) -> StatusView:
    payload = transport.json(f"{REMOTE_RSI} daily status --json", timeout=60)
    return summarize_daily(payload)


def load_child_why(transport: Transport, status: StatusView) -> str:
    if not status.run_id or status.digest:
        return status.why
    run_id = shlex.quote(status.run_id)
    command = (
        "python3 - <<'PY'\n"
        "import json, os\n"
        "from pathlib import Path\n"
        f"run_id = {status.run_id!r}\n"
        "root = Path('/root/rsi-lab/forge-chassis-20260706T234452Z/state/.dharma/forge_lab/unattended_explore/runs') / run_id\n"
        "path = root / 'child_result.json'\n"
        "print('exists', path.is_file())\n"
        "if path.is_file():\n"
        "    d=json.loads(path.read_text())\n"
        "    used=d.get('logical_provider_calls_by_role')\n"
        "    expected=d.get('expected_provider_calls_by_role')\n"
        "    print('execution_shape_ok', d.get('execution_shape_ok'))\n"
        "    print('closeout_state', d.get('closeout_state'))\n"
        "    print('used', used)\n"
        "    print('expected', expected)\n"
        "PY"
    )
    completed = transport.raw(command, timeout=20)
    text = (completed.stdout or "") + (completed.stderr or "")
    extra = []
    if "exists False" in text:
        extra.append("no child_result.json on disk")
    elif "exists True" in text:
        extra.append("validator-null (file present, digest not accepted)")
    if "execution_shape_ok False" in text or "execution_shape_ok false" in text:
        extra.append("execution_shape_ok=false")
    if "used {" in text and "candidate_verifier" not in text.split("expected", 1)[0]:
        extra.append("candidate_verifier missing from used map")
    if not extra:
        return status.why
    if status.silent_death:
        return "silent death: " + " · ".join(extra)
    return f"{status.why} · " + " · ".join(extra)


def cmd_status(transport: Transport, stdout: Any = None) -> int:
    stdout = stdout or sys.stdout
    view = load_status(transport)
    try:
        view_why = load_child_why(transport, view)
        if view_why != view.why:
            view = StatusView(**{**view.__dict__, "why": view_why})
    except Exception:
        pass
    print(view.banner(), file=stdout)
    return 0 if view.verdict in {"VALID", "NONE"} else 1


def _pick(routes: Sequence[Mapping[str, Any]], role: str, raw: str, stdin: Any) -> dict[str, Any]:
    if raw.strip():
        try:
            index = int(raw.strip())
        except ValueError as exc:
            raise MenuError("PICK_INVALID", f"{role} pick must be a number") from exc
    else:
        printed = input(f"{role} number (empty=keep current if listed): ").strip()
        if not printed:
            raise MenuError("PICK_REQUIRED", f"{role} requires a catalog number")
        index = int(printed)
    if index < 1 or index > len(routes):
        raise MenuError("PICK_RANGE", f"{role} pick {index} is out of range")
    return dict(routes[index - 1])


def cmd_models(
    transport: Transport,
    *,
    argv: Sequence[str],
    yes: bool,
    stdin: Any = None,
    stdout: Any = None,
) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    listed = transport.json(f"{REMOTE_RSI} provider models list --json")
    status = transport.json(f"{REMOTE_RSI} provider models status --json")
    routes = selectable_routes(listed)
    current = unwrap(status)
    print("current profile:", current.get("current_profile_digest") or "(none)", file=stdout)
    for row in current.get("role_bindings") or []:
        if isinstance(row, dict):
            print(f"  {row.get('role')}: {row.get('provider')} / {row.get('model_id')}", file=stdout)
    print("runtime_selectable catalog:", file=stdout)
    print(format_routes(routes), file=stdout)
    parser = argparse.ArgumentParser(prog="RSILAB models", add_help=False)
    for role in ROLES:
        parser.add_argument(f"--{role}")
        parser.add_argument(f"--{role}-provider")
        parser.add_argument(f"--{role}-model")
    parser.add_argument("--yes", action="store_true")
    ns, _unknown = parser.parse_known_args(list(argv))
    selected: dict[str, dict[str, Any]] = {}
    supplied = any(getattr(ns, role.replace("-", "_"), None) or getattr(ns, f"{role}_model", None) for role in ROLES)
    if not supplied and (not sys.stdin.isatty() or yes):
        print("pass --mutator-provider/--mutator-model (and solver, verifier) to apply.", file=stdout)
        return 0
    if supplied:
        for role in ROLES:
            provider = getattr(ns, f"{role}_provider", None)
            model = getattr(ns, f"{role}_model", None) or getattr(ns, role, None)
            if not provider or not model:
                match = next(
                    (
                        row
                        for row in routes
                        if str(row.get("model_id")) == str(model)
                        and (not provider or str(row.get("provider")) == str(provider))
                    ),
                    None,
                )
                if match is None:
                    raise MenuError("ROUTE_UNKNOWN", f"{role} {provider}/{model} is not runtime_selectable")
                selected[role] = match
            else:
                selected[role] = {"provider": provider, "model_id": model, "role": role}
    else:
        print("Pick catalog numbers for mutator, solver, verifier.", file=stdout)
        for role in ROLES:
            selected[role] = _pick(routes, role, "", stdin)
    flags = []
    for role in ROLES:
        row = selected[role]
        flags.extend(
            [
                f"--{role}-provider",
                str(row["provider"]),
                f"--{role}-model",
                str(row["model_id"]),
            ]
        )
    current_digest = current.get("current_profile_digest")
    plan_cmd = f"{REMOTE_RSI} provider models plan " + " ".join(shlex.quote(part) for part in flags)
    if current_digest:
        plan_cmd += f" --expected-current-digest {shlex.quote(str(current_digest))}"
    plan_cmd += " --json"
    plan = unwrap(transport.json(plan_cmd, timeout=40))
    blockers = plan.get("blockers") or []
    print(f"plan_digest: {plan.get('plan_digest')}", file=stdout)
    print(f"outcome: {plan.get('outcome')}  blockers: {blockers}", file=stdout)
    if blockers:
        raise MenuError("PLAN_BLOCKED", f"model plan blocked: {blockers}")
    if not yes:
        confirm = input("type APPLY to activate this profile on Meghadharma: ").strip()
        if confirm != "APPLY":
            print("aborted", file=stdout)
            return 2
    request_id = datetime.now(timezone.utc).strftime("operator-%Y%m%d-rsilab-models")
    apply_cmd = (
        f"{REMOTE_RSI} provider models apply "
        + " ".join(shlex.quote(part) for part in flags)
        + f" --plan-digest {shlex.quote(str(plan['plan_digest']))}"
        + f" --request-id {shlex.quote(request_id)}"
    )
    if current_digest:
        apply_cmd += f" --expected-current-digest {shlex.quote(str(current_digest))}"
    apply_cmd += " --json"
    applied = transport.json(apply_cmd, timeout=40)
    print(json.dumps(unwrap(applied), indent=2, sort_keys=True)[:2000], file=stdout)
    print("role selection only — no quality/promotion claim.", file=stdout)
    return 0


def _explore_running(transport: Transport) -> bool:
    completed = transport.raw(
        "ps -eo pid,cmd | grep -E 'rsi-unattended-explore|unattended_explore' | grep -v grep || true"
    )
    text = (completed.stdout or "") + (completed.stderr or "")
    return bool(text.strip()) and "NO_PROC" not in text


def cmd_run(
    transport: Transport,
    *,
    yes: bool,
    stdout: Any = None,
) -> int:
    stdout = stdout or sys.stdout
    view = load_status(transport)
    print(view.banner(), file=stdout)
    if not view.halt_absent:
        raise MenuError("HALT_PRESENT", f"HALT is present at {view.halt_path}")
    if _explore_running(transport):
        raise MenuError("ALREADY_RUNNING", "an unattended_explore process is already live")
    print(
        f"\nRUN 1  fuse={FUSE_SECONDS}s  reserve=${RUN_USD}  "
        "shape=1x1x1  host=meghadharma\n"
        "This spends live model tokens. n50 is not available.\n",
        file=stdout,
    )
    if not yes:
        confirm = input("type RUN to launch rsi-unattended-explore: ").strip()
        if confirm != "RUN":
            print("aborted", file=stdout)
            return 2
    rc = transport.stream(
        f"{REMOTE_EXPLORE} --timeout-seconds {FUSE_SECONDS}",
        timeout=FUSE_SECONDS + 180,
    )
    print(f"\nexplore ssh rc={rc}", file=stdout)
    after = load_status(transport)
    try:
        why = load_child_why(transport, after)
        after = StatusView(**{**after.__dict__, "why": why})
    except Exception:
        pass
    print(after.banner(), file=stdout)
    if after.verdict == "VALID":
        print("VALID — child_result_digest is a sha256. Still no promotion.", file=stdout)
        return 0
    print("REJECT — do not n50. Inspect why above.", file=stdout)
    return 1


def cmd_halt(
    transport: Transport,
    *,
    action: str | None,
    yes: bool,
    stdout: Any = None,
) -> int:
    stdout = stdout or sys.stdout
    view = load_status(transport)
    path = view.halt_path or "/root/rsi-lab/state/.dharma/forge_lab/HALT"
    print(f"HALT path: {path}", file=stdout)
    print(f"HALT absent: {view.halt_absent}", file=stdout)
    if action in (None, "status"):
        return 0
    quoted = shlex.quote(path)
    if action in {"on", "drop", "set"}:
        if not yes:
            confirm = input("type HALT to create the latch: ").strip()
            if confirm != "HALT":
                print("aborted", file=stdout)
                return 2
        transport.raw(f"mkdir -p $(dirname {quoted}) && umask 077 && : > {quoted} && echo HALT=PRESENT")
        print("HALT created. Unattended admit will refuse.", file=stdout)
        return 0
    if action in {"off", "clear", "lift"}:
        if not yes:
            confirm = input("type CLEAR to remove the latch: ").strip()
            if confirm != "CLEAR":
                print("aborted", file=stdout)
                return 2
        transport.raw(f"rm -f {quoted} && echo HALT=ABSENT")
        print("HALT removed.", file=stdout)
        return 0
    raise MenuError("HALT_ACTION", "halt action must be status, on, or off")


def interactive_menu(transport: Transport) -> int:
    while True:
        print()
        try:
            print(load_status(transport).banner())
        except MenuError as exc:
            print(f"status unavailable [{exc.code}]: {exc}")
        print(
            "\n  1) status     last digest / silent death / ready\n"
            "  2) models     pick mutator / solver / verifier (runtime_selectable)\n"
            "  3) run 1      Megha 2700s · print VALID or REJECT\n"
            "  4) halt       drop / lift HALT\n"
            "  q) quit\n"
        )
        choice = input("RSILAB> ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            return 0
        try:
            if choice in {"1", "status", "s"}:
                cmd_status(transport)
            elif choice in {"2", "models", "m"}:
                cmd_models(transport, argv=[], yes=False)
            elif choice in {"3", "run", "r", "run 1", "run1"}:
                cmd_run(transport, yes=False)
            elif choice in {"4", "halt", "h"}:
                sub = input("halt [status/on/off]: ").strip().lower() or "status"
                cmd_halt(transport, action=sub, yes=False)
            elif refuse_scale(choice.split()):
                print(refuse_scale(choice.split()))
            else:
                print("unknown command")
        except MenuError as exc:
            print(f"[{exc.code}] {exc}")
        except KeyboardInterrupt:
            print("\naborted")
            return 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="RSILAB",
        description="Supervised Meghadharma RSI Lab menu. Run 1 only. No n50.",
    )
    parser.add_argument("--yes", action="store_true", help="skip interactive confirmations")
    parser.add_argument("--host", default=os.environ.get("RSILAB_HOST", REMOTE))
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("status")
    sub.add_parser("menu")
    models = sub.add_parser("models")
    for role in ROLES:
        models.add_argument(f"--{role}-provider")
        models.add_argument(f"--{role}-model")
    run = sub.add_parser("run")
    run.add_argument("scale", nargs="?", default="1")
    halt = sub.add_parser("halt")
    halt.add_argument("action", nargs="?", default="status", choices=["status", "on", "off", "drop", "clear", "lift", "set"])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    blocked = refuse_scale(raw)
    if blocked:
        print(blocked, file=sys.stderr)
        return 3
    parser = build_parser()
    args = parser.parse_args(raw)
    transport = SshTransport(host=args.host)
    try:
        if args.cmd in (None, "menu"):
            if sys.stdin.isatty() and sys.stdout.isatty() and args.cmd != "status":
                return interactive_menu(transport)
            return cmd_status(transport)
        if args.cmd == "status":
            return cmd_status(transport)
        if args.cmd == "models":
            model_argv = []
            for role in ROLES:
                provider = getattr(args, f"{role}_provider".replace("-", "_"), None)
                model = getattr(args, f"{role}_model".replace("-", "_"), None)
                if provider:
                    model_argv.extend([f"--{role}-provider", provider])
                if model:
                    model_argv.extend([f"--{role}-model", model])
            return cmd_models(transport, argv=model_argv, yes=args.yes)
        if args.cmd == "run":
            if str(args.scale) not in {"1", "n1", ""}:
                print(refuse_scale([str(args.scale)]) or "only run 1 is admitted", file=sys.stderr)
                return 3
            return cmd_run(transport, yes=args.yes)
        if args.cmd == "halt":
            return cmd_halt(transport, action=args.action, yes=args.yes)
    except MenuError as exc:
        print(f"RSILAB failed [{exc.code}]: {exc}", file=sys.stderr)
        return 8
    except subprocess.TimeoutExpired:
        print("RSILAB failed [TIMEOUT]: remote command exceeded timeout", file=sys.stderr)
        return 9
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
