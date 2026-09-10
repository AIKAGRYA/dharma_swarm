#!/usr/bin/env python3
"""Build the optional native status menu; no login item or global config changes."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile
import time


def bundle_identifier(state: Path) -> str:
    # LaunchServices otherwise reuses another state directory's running bundle
    # and silently ignores --args. Different private mirrors have distinct IDs.
    return "org.aikagrya.helm-menu.s" + hashlib.sha256(str(state).encode()).hexdigest()[:16]


def instance_status(state: Path, configuration: dict[str, str]) -> dict:
    """A held OS lock proves liveness; its private receipt describes configuration."""
    try:
        descriptor = os.open(state / "menu-instance.lock", os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return {"outcome": "not_running"}
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("unsafe menu instance lock")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            return {"outcome": "not_running"}
        except BlockingIOError:
            pass
        try:
            receipt_fd = os.open(state / "menu-instance.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        except FileNotFoundError:
            return {"outcome": "starting"}
        try:
            info = os.fstat(receipt_fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError("unsafe menu instance receipt")
            receipt = json.loads(os.read(receipt_fd, 65_537))
        finally:
            os.close(receipt_fd)
        if (not isinstance(receipt, dict) or receipt.get("schema") != "dharma.helm.menu_instance.v1"
                or type(receipt.get("pid")) is not int or not isinstance(receipt.get("configuration"), dict)):
            raise ValueError("invalid menu instance receipt")
        return {"outcome": "reused" if receipt["configuration"] == configuration else "config_mismatch",
                "pid": receipt["pid"]}
    finally:
        os.close(descriptor)


def launch_menu(app: Path, state: Path, configuration: dict[str, str], *, runner=subprocess.run,
                observe=instance_status, timeout_seconds: float = 3.0) -> dict:
    """Reuse matching live state or report a mismatch; never kill or duplicate it."""
    descriptor = os.open(state / "menu-launch.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"outcome": "launch_pending", "launch_requested": False,
                    "detail": "Another menu launch is in progress; retry when it finishes", "ok": False}
        deadline = time.monotonic() + timeout_seconds
        current = observe(state, configuration)
        while current["outcome"] == "starting" and time.monotonic() < deadline:
            time.sleep(0.025)
            current = observe(state, configuration)
        if current["outcome"] == "reused":
            return {**current, "launch_requested": False, "reused": True, "ok": True}
        if current["outcome"] == "config_mismatch":
            return {**current, "launch_requested": False, "reused": False, "ok": False,
                    "detail": "Quit Menu before launching the changed configuration or build; the existing menu is unchanged"}
        if current["outcome"] == "starting":
            return {**current, "launch_requested": False, "ok": False,
                    "detail": "A private menu is starting, but its configuration could not be observed"}
        # Detect an older menu that predates instance receipts. An exact
        # executable match is enough to refuse another launch, never to kill it.
        listing = runner(["/bin/ps", "-axo", "pid=,comm="], capture_output=True, text=True, timeout=5, check=True)
        executable = str(app / "Contents/MacOS/HelmMenu")
        for line in listing.stdout.splitlines():
            fields = line.strip().split(None, 1)
            if len(fields) == 2 and fields[1] == executable:
                return {"outcome": "config_mismatch", "launch_requested": False, "reused": False, "ok": False,
                        "detail": "Quit Menu before relaunching: the running menu predates configuration receipts"}
        argv = [part for pair in configuration.items() for part in pair]
        runner(["open", str(app), "--args", *argv], check=True, timeout=10)
        deadline = time.monotonic() + timeout_seconds
        current = observe(state, configuration)
        while current["outcome"] in {"not_running", "starting"} and time.monotonic() < deadline:
            time.sleep(0.025)
            current = observe(state, configuration)
        if current["outcome"] == "reused":
            return {**current, "outcome": "launched", "launch_requested": True, "reused": False, "ok": True}
        return {**current, "outcome": "config_mismatch" if current["outcome"] == "config_mismatch" else "launch_requested",
                "launch_requested": True, "reused": False, "ok": False,
                "detail": "macOS accepted the launch, but a matching menu instance was not observed; inspect the existing menu"}
    finally:
        os.close(descriptor)


def private_directory(path: Path) -> Path:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("state directory must be an absolute path without '..'")
    for parent in (*reversed(path.parents), path):
        if parent.is_symlink():
            raise ValueError(f"refusing symlink directory: {parent}")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def build_menu(repo: Path, state: Path) -> Path:
    if sys.platform != "darwin" or not shutil.which("xcrun"):
        raise RuntimeError("The native menu requires macOS and the Xcode command line tools")
    sources = [repo / "terminal/desktop/macos" / name for name in ("DesktopStatus.swift", "DesktopLifecycle.swift", "main.swift")]
    app = private_directory(state / "apps" / "Helm.app")
    contents = private_directory(app / "Contents")
    executable_dir = private_directory(contents / "MacOS")
    cache = private_directory(state / "cache" / "swift")
    executable = executable_dir / "HelmMenu"
    receipt = contents / "build.json"
    plist = contents / "Info.plist"
    for output in (executable, receipt, plist):
        if output.is_symlink():
            raise ValueError(f"refusing symlink output: {output}")
    version = subprocess.check_output(["xcrun", "swiftc", "--version"], text=True, timeout=15)
    digest = hashlib.sha256(version.encode() + b"".join(source.read_bytes() for source in sources)).hexdigest()
    try:
        previous = json.loads(receipt.read_text())
    except (OSError, ValueError):
        previous = {}
    if previous.get("source_sha256") != digest or not executable.is_file():
        fd, temporary = tempfile.mkstemp(prefix=".HelmMenu-", dir=executable_dir)
        os.close(fd)
        try:
            subprocess.run(["xcrun", "swiftc", "-O", "-swift-version", "5", "-module-cache-path", str(cache),
                            *map(str, sources), "-o", temporary], check=True, timeout=180)
            os.chmod(temporary, 0o700)
            os.replace(temporary, executable)
        finally:
            Path(temporary).unlink(missing_ok=True)
        receipt.write_text(json.dumps({"schema": "dharma.helm.menu_build.v1", "source_sha256": digest,
                                       "source_root": str(repo), "compiler": version.strip()}, indent=2) + "\n")
        receipt.chmod(0o600)
    plist.write_bytes(plistlib.dumps({
        "CFBundleExecutable": "HelmMenu", "CFBundleIdentifier": bundle_identifier(state),
        "CFBundleName": "Helm", "CFBundleDisplayName": "Helm", "CFBundleVersion": "1",
        "CFBundlePackageType": "APPL", "LSUIElement": True, "NSHighResolutionCapable": True,
    }))
    return app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".dharma/helm_desktop")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--profile", default="research")
    parser.add_argument("--socket", default="CODEX_MANAGED_helm_desktop")
    parser.add_argument("--session", default="helm_desktop")
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        state = private_directory(args.state_dir.expanduser())
        repo = args.repo_root.expanduser().resolve(strict=True)
        app = build_menu(repo, state)
        lifecycle = {"outcome": "built", "launch_requested": False, "reused": False, "ok": True}
        if args.launch:
            build = json.loads((app / "Contents/build.json").read_text())
            configuration = {"--status-file": str(state / "status.json"), "--python": sys.executable,
                             "--cli": str(repo / "scripts/helm_desktop.py"), "--state-dir": str(state),
                             "--repo-root": str(repo), "--profile": args.profile, "--socket": args.socket,
                             "--session": args.session, "--exec-path": os.environ.get("PATH", os.defpath),
                             "--build-id": build["source_sha256"]}
            lifecycle = launch_menu(app, state, configuration)
        result = {"app": str(app), "executable": str(app / "Contents/MacOS/HelmMenu"),
                  "state_dir": str(state), "repo_root": str(repo), **lifecycle}
        print(json.dumps(result) if args.json else f"Built: {app}\n" + (lifecycle.get("detail") or lifecycle["outcome"]
              if args.launch else "Launch with: scripts/helm_desktop.sh menu"))
        return 0 if lifecycle["ok"] else 1
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}) if args.json else str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
