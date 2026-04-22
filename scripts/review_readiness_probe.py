#!/usr/bin/env python3
"""Produce a bounded review-readiness snapshot for the dharma_swarm repo."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.codex_overnight import GitSnapshot, gather_git_snapshot


HOME = Path.home()
HOME_ROOT = HOME / "dharma_swarm"
STATE_DIR = HOME / ".dharma"
RUN_ROOT = STATE_DIR / "review_readiness"
LATEST_RUN_FILE = RUN_ROOT / "latest_run.txt"
CODEX_RUN_FILE = STATE_DIR / "codex_overnight_run_dir.txt"
VERIFY_RUN_FILE = STATE_DIR / "verification_lane_run_dir.txt"


@dataclass(frozen=True)
class CheckSpec:
    name: str
    cmd: list[str]
    cwd: Path
    timeout: int
    critical: bool
    description: str


def utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_text(text: str, limit: int = 400) -> str:
    squashed = " ".join(text.split())
    if len(squashed) <= limit:
        return squashed
    return squashed[: limit - 3] + "..."


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def read_run_dir(path: Path) -> Path | None:
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def read_last_jsonl(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    last = ""
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.strip():
                last = line
    if not last:
        return {}
    try:
        return json.loads(last)
    except json.JSONDecodeError:
        return {}


def run_cmd(cmd: Sequence[str], *, cwd: Path, timeout: int) -> dict[str, Any]:
    start = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory(prefix="review-readiness-probe-") as tmp_dir:
        stdout_path = Path(tmp_dir) / "stdout.log"
        stderr_path = Path(tmp_dir) / "stderr.log"
        with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr_handle:
            proc = subprocess.Popen(
                list(cmd),
                cwd=str(cwd),
                text=True,
                stdout=stdout_handle,
                stderr=stderr_handle,
            )
            try:
                rc = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                stdout = stdout_path.read_text(encoding="utf-8", errors="ignore").strip()
                stderr = stderr_path.read_text(encoding="utf-8", errors="ignore").strip()
                return {
                    "rc": 124,
                    "started_at": start.isoformat(),
                    "stdout": stdout[-8000:],
                    "stderr": stderr[-4000:],
                    "headline": "timeout",
                }

        stdout = stdout_path.read_text(encoding="utf-8", errors="ignore").strip()
        stderr = stderr_path.read_text(encoding="utf-8", errors="ignore").strip()
        headline = stdout.splitlines()[0] if stdout else (stderr.splitlines()[0] if stderr else "")
        return {
            "rc": rc,
            "started_at": start.isoformat(),
            "stdout": stdout[-8000:],
            "stderr": stderr[-4000:],
            "headline": headline[:240],
        }


def build_check_specs(mode: str, repo_root: Path) -> list[CheckSpec]:
    specs = [
        CheckSpec(
            name="desktop_runtime_smoke",
            cmd=["env", "DHARMA_SMOKE_SKIP_START=1", "bash", "./scripts/smoke.sh"],
            cwd=repo_root / "desktop-shell",
            timeout=180,
            critical=True,
            description="Desktop shell can reach the canonical runtime and dashboard route.",
        ),
        CheckSpec(
            name="dashboard_build",
            cmd=["npm", "run", "build"],
            cwd=repo_root / "dashboard",
            timeout=900,
            critical=True,
            description="Canonical web dashboard builds cleanly.",
        ),
        CheckSpec(
            name="desktop_shell_bundle",
            cmd=["npm", "run", "build"],
            cwd=repo_root / "desktop-shell",
            timeout=1800,
            critical=True,
            description="Desktop shell builds into a native macOS app bundle.",
        ),
        CheckSpec(
            name="desktop_shell_tests",
            cmd=["cargo", "test"],
            cwd=repo_root / "desktop-shell" / "src-tauri",
            timeout=900,
            critical=True,
            description="Desktop shell Rust tests stay green.",
        ),
        CheckSpec(
            name="overnight_automation_tests",
            cmd=[
                "pytest",
                "-q",
                "tests/test_codex_overnight.py",
                "tests/test_dashboard_ctl_script.py",
                "tests/test_review_readiness_probe.py",
                "tests/test_review_readiness_scripts.py",
            ],
            cwd=repo_root,
            timeout=1200,
            critical=True,
            description="Overnight automation and review-readiness helpers stay green.",
        ),
    ]
    if mode == "quick":
        return specs[:1]
    return specs


def derive_overall_status(snapshot: GitSnapshot, checks: dict[str, dict[str, Any]]) -> tuple[str, bool, list[str]]:
    blockers: list[str] = []
    failing = [name for name, result in checks.items() if result.get("critical") and result.get("rc") != 0]
    if failing:
        blockers.append("failing checks: " + ", ".join(failing))
    if snapshot.dirty:
        blockers.append(
            "dirty worktree: "
            f"staged={snapshot.staged_count} unstaged={snapshot.unstaged_count} "
            f"untracked={snapshot.untracked_count}"
        )
    ready = not blockers
    status = "ready" if ready else "blocked"
    return status, ready, blockers


def collect_lane_context() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "review_run_dir": str(read_run_dir(LATEST_RUN_FILE) or ""),
        "codex_run_dir": str(read_run_dir(CODEX_RUN_FILE) or ""),
        "verification_run_dir": str(read_run_dir(VERIFY_RUN_FILE) or ""),
        "codex_latest": {},
        "verification_latest": {},
    }
    codex_run_dir = read_run_dir(CODEX_RUN_FILE)
    if codex_run_dir:
        latest_json = codex_run_dir / "latest.json"
        if latest_json.exists():
            try:
                payload["codex_latest"] = json.loads(read_text(latest_json))
            except json.JSONDecodeError:
                payload["codex_latest"] = {}
    verify_run_dir = read_run_dir(VERIFY_RUN_FILE)
    if verify_run_dir:
        payload["verification_latest"] = read_last_jsonl(verify_run_dir / "snapshots.jsonl")
    return payload


def write_probe_outputs(
    *,
    output_dir: Path,
    phase: str,
    payload: dict[str, Any],
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"{phase}_{stamp}.json"
    md_path = output_dir / f"{phase}_{stamp}.md"
    latest_json = output_dir / f"{phase}_latest.json"
    latest_md = output_dir / f"{phase}_latest.md"

    json_text = json.dumps(payload, ensure_ascii=True, indent=2) + "\n"
    json_path.write_text(json_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")

    git_snapshot = payload["git_snapshot"]
    checks = payload["checks"]
    lane_ctx = payload["lane_context"]
    blockers = payload["blockers"]
    lines = [
        f"# Review Readiness Probe — {phase}",
        "",
        f"- timestamp: `{payload['timestamp']}`",
        f"- mode: `{payload['mode']}`",
        f"- overall_status: `{payload['overall_status']}`",
        f"- review_ready: `{payload['review_ready']}`",
        f"- branch: `{git_snapshot['branch']}`",
        f"- head: `{git_snapshot['head']}`",
        f"- dirty: `{git_snapshot['dirty']}`",
        f"- staged_count: `{git_snapshot['staged_count']}`",
        f"- unstaged_count: `{git_snapshot['unstaged_count']}`",
        f"- untracked_count: `{git_snapshot['untracked_count']}`",
        "",
        "## Check Results",
        "",
    ]
    for name, result in checks.items():
        lines.extend(
            [
                f"### {name}",
                f"- rc: `{result['rc']}`",
                f"- critical: `{result['critical']}`",
                f"- description: {result['description']}",
                f"- headline: {result['headline'] or '(none)'}",
                "",
            ]
        )
    lines.extend(
        [
            "## Blockers",
            "",
            *([f"- {item}" for item in blockers] if blockers else ["- none"]),
            "",
            "## Lane Context",
            "",
            f"- review_run_dir: `{lane_ctx['review_run_dir'] or '(none)'}`",
            f"- codex_run_dir: `{lane_ctx['codex_run_dir'] or '(none)'}`",
            f"- verification_run_dir: `{lane_ctx['verification_run_dir'] or '(none)'}`",
        ]
    )
    codex_latest = lane_ctx.get("codex_latest") or {}
    if codex_latest:
        lines.extend(
            [
                "",
                "## Latest Codex Cycle",
                "",
                f"- cycle: `{codex_latest.get('cycle', 0)}`",
                f"- result: {safe_text(str(codex_latest.get('summary_fields', {}).get('result', '')) or '(missing)')}",
                f"- tests: {safe_text(str(codex_latest.get('summary_fields', {}).get('tests', '')) or 'not reported')}",
                f"- blockers: {safe_text(str(codex_latest.get('summary_fields', {}).get('blockers', '')) or 'none')}",
            ]
        )
    verification_latest = lane_ctx.get("verification_latest") or {}
    if verification_latest:
        lines.extend(
            [
                "",
                "## Latest Verification Snapshot",
                "",
                f"- loop: `{verification_latest.get('loop', 0)}`",
                f"- health_score: `{verification_latest.get('health_score', 'n/a')}`",
                f"- health_label: `{verification_latest.get('health_label', 'n/a')}`",
            ]
        )

    md_text = "\n".join(lines) + "\n"
    md_path.write_text(md_text, encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")
    return json_path, md_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run review-readiness checks for dharma_swarm.")
    parser.add_argument("--repo-root", default=str(HOME_ROOT))
    parser.add_argument("--state-dir", default=str(STATE_DIR))
    parser.add_argument("--run-dir", default="", help="Existing review-readiness run dir.")
    parser.add_argument("--phase", default="manual", help="baseline, checkpoint, final, or manual.")
    parser.add_argument("--mode", default="full", choices=["quick", "full"])
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).expanduser()
    state_dir = Path(args.state_dir).expanduser()
    run_dir = Path(args.run_dir).expanduser() if args.run_dir else None
    if run_dir is None:
        run_dir = RUN_ROOT / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    probe_dir = run_dir / "probes"

    snapshot = gather_git_snapshot(repo_root)
    checks: dict[str, dict[str, Any]] = {}
    for spec in build_check_specs(args.mode, repo_root):
        result = run_cmd(spec.cmd, cwd=spec.cwd, timeout=spec.timeout)
        result["critical"] = spec.critical
        result["description"] = spec.description
        checks[spec.name] = result

    lane_context = collect_lane_context()
    overall_status, review_ready, blockers = derive_overall_status(snapshot, checks)
    payload = {
        "timestamp": utc_ts(),
        "phase": args.phase,
        "mode": args.mode,
        "overall_status": overall_status,
        "review_ready": review_ready,
        "blockers": blockers,
        "git_snapshot": asdict(snapshot),
        "checks": checks,
        "lane_context": lane_context,
    }
    json_path, md_path = write_probe_outputs(output_dir=probe_dir, phase=args.phase, payload=payload)

    if args.phase == "final":
        shared_dir = state_dir / "shared"
        shared_dir.mkdir(parents=True, exist_ok=True)
        (shared_dir / "review_readiness_morning.md").write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
        (shared_dir / "review_readiness_morning.json").write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")

    print(
        f"review_readiness_probe phase={args.phase} mode={args.mode} "
        f"status={overall_status} ready={review_ready} "
        f"json={json_path} md={md_path}"
    )
    return 0 if review_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
