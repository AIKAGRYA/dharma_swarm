#!/usr/bin/env python3
"""Verify desktop installation and the real Helm seat on a disposable private socket."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dharma_swarm.helm_desktop.config import DesktopConfig  # noqa: E402 -- executable source bootstrap
from dharma_swarm.terminal_bridge_desktop_status import read_status  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".dharma/helm-desktop-build/verification")
    parser.add_argument("--skip-native", action="store_true", help="record native verification as skipped")
    parser.add_argument("--skip-live", action="store_true", help="verify configuration without starting an isolated TUI")
    args = parser.parse_args()
    token = f"{os.getpid()}_{uuid.uuid4().hex[:8]}"
    run_dir = args.state_dir.expanduser().resolve() / token
    config = DesktopConfig(ROOT, run_dir / "desktop", socket=f"CODEX_MANAGED_hdverify_{token}", session="helm_verify")
    run_dir.mkdir(parents=True, mode=0o700)
    receipt_path = run_dir / "receipt.json"
    environment = config.environment()
    environment["DHARMA_PYTHON"] = sys.executable
    checks: list[dict] = []
    receipt = {"schema": "dharma.helm.desktop_verification.v1", "started_at": datetime.now(timezone.utc).isoformat(),
               "repo_root": str(ROOT), "seat": config.seat(), "state_dir": str(config.state_dir), "checks": checks,
               "scope": "isolated real terminal bridge; no model request or GUI activation"}
    owns_session = False
    owner_pid: int | None = None

    def command(argv: list[str], *, timeout: float = 35) -> subprocess.CompletedProcess:
        return subprocess.run(argv, cwd=ROOT, env=environment, text=True, capture_output=True, timeout=timeout)

    def cli(*arguments: str) -> dict:
        argv = [sys.executable, str(ROOT / "scripts/helm_desktop.py"), "--json", "--state-dir", str(config.state_dir),
                "--repo-root", str(ROOT), "--socket", config.socket, "--session", config.session, *arguments]
        result = command(argv)
        if result.returncode:
            raise RuntimeError(f"CLI {' '.join(arguments)} failed: {(result.stderr or result.stdout)[-2000:]}")
        return json.loads(result.stdout)

    def tmux(*arguments: str):
        return command(["tmux", "-L", config.socket, "-f", "/dev/null", *arguments], timeout=5)

    def record(name: str, **details):
        checks.append({"name": name, "passed": True, **details})

    try:
        preview = cli("install", "preview")
        assert preview["ready"] and not config.state_dir.exists(), "preview created files or conflicts"
        record("preview_has_no_writes", artifacts=len(preview["files"]))
        installed = cli("install", "apply", "--apply")
        wrapper = command([installed["launcher"], "--json", "status"])
        assert wrapper.returncode == 0 and json.loads(wrapper.stdout)["availability"] == "unavailable"
        record("installed_wrapper_reads_status")
        repeated = cli("install", "preview")
        assert all(item["action"] == "unchanged" for item in repeated["files"])
        record("install_is_idempotent")
        profile = cli("workspace", "preview")
        assert profile["profile"]["schema"] == "dharma.helm.desktop_profile.v1"
        assert any(item["kind"] == "helm" and not item["starts_bridge"] for item in profile["actions"])
        record("typed_workspace_preview", schema=profile["profile"]["schema"])
        native: Path | None = None
        if not args.skip_native and sys.platform == "darwin":
            built = command([sys.executable, str(ROOT / "scripts/build_helm_menu.py"),
                             "--state-dir", str(run_dir / "native"), "--json"], timeout=240)
            if built.returncode:
                raise RuntimeError(f"Native build failed: {built.stderr[-2000:]}")
            native = Path(json.loads(built.stdout)["executable"])
            record("native_compiled", executable=str(native))
        else:
            checks.append({"name": "native_compiled", "skipped": True, "reason": "explicit flag or non-macOS host"})
        if not args.skip_live:
            assert tmux("has-session", "-t", f"={config.session}").returncode != 0, "disposable seat unexpectedly exists"
            owns_session = True
            started = cli("start")
            status = cli("status")
            assert status["availability"] == "fresh", status
            snapshot = status["snapshot"]
            owner_pid = snapshot["owner"]["pid"]
            assert snapshot["seat"] == config.seat()
            # The Python bridge intentionally sets repo_root to the terminal's
            # source root; the desktop consumer also verifies this equality.
            assert snapshot["repo_root"] == str(ROOT)
            again = cli("start")
            assert again["outcome"] == "already_running"
            assert cli("status")["snapshot"]["owner"] == snapshot["owner"]
            record("real_owner_started_once", owner=snapshot["owner"], outcome=started["outcome"])
            tmux("resize-window", "-t", f"={config.session}:", "-x", "80", "-y", "24")
            deadline = time.monotonic() + 5
            rendered = ""
            while time.monotonic() < deadline:
                rendered = tmux("capture-pane", "-p", "-t", f"={config.session}:").stdout
                if "Dharma" in rendered:
                    break
                time.sleep(0.05)
            assert "Dharma" in rendered, "80x24 cockpit did not paint its identity"
            record("compact_cockpit_rendered")
            if native:
                decoded = command([str(native), "--check-status", "--status-file", str(config.status_path),
                                   "--repo-root", str(ROOT), "--socket", config.socket, "--session", config.session])
                view = json.loads(decoded.stdout)
                assert view["availability"] == "fresh" and view["owner_id"] == snapshot["owner"]["id"]
                record("native_mirrors_real_owner", owner_id=view["owner_id"])
            samples = []
            for _ in range(1000):
                start = time.perf_counter_ns()
                observed = read_status(config.status_path)
                samples.append((time.perf_counter_ns() - start) / 1_000_000)
                assert observed["availability"] == "fresh"
            ordered = sorted(samples)
            record("bounded_file_read", count=len(samples), p50_ms=statistics.median(samples),
                   p95_ms=ordered[949], p99_ms=ordered[989], measured_boundary="Python status read only; excludes UI and process launch")
        else:
            checks.append({"name": "live_seat", "skipped": True, "reason": "explicit --skip-live"})
        restored = cli("restore", "--apply")
        assert restored["outcome"] == "restored" and not Path(installed["launcher"]).exists()
        record("restoration_removed_generated_artifacts")
        receipt["passed"] = True
    except (OSError, ValueError, AssertionError, RuntimeError, subprocess.SubprocessError) as exc:
        receipt["passed"] = False
        receipt["error"] = str(exc)
    finally:
        if owns_session:
            tmux("send-keys", "-t", f"={config.session}:", "C-c")
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline and tmux("has-session", "-t", f"={config.session}").returncode == 0:
                time.sleep(0.05)
            if tmux("has-session", "-t", f"={config.session}").returncode == 0:
                tmux("kill-session", "-t", f"={config.session}")
            stopped = tmux("has-session", "-t", f"={config.session}").returncode != 0
            if owner_pid is not None:
                deadline = time.monotonic() + 4
                while True:
                    try:
                        os.kill(owner_pid, 0)
                    except ProcessLookupError:
                        break
                    if time.monotonic() >= deadline:
                        stopped = False
                        break
                    time.sleep(0.05)
            checks.append({"name": "disposable_executor_stopped", "passed": stopped})
            receipt["passed"] = bool(receipt.get("passed")) and stopped
        receipt["completed_at"] = datetime.now(timezone.utc).isoformat()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        receipt_path.chmod(0o600)
        print(json.dumps({"passed": receipt.get("passed", False), "receipt": str(receipt_path),
                          "error": receipt.get("error"), "checks": checks}, indent=2))
    return 0 if receipt.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
