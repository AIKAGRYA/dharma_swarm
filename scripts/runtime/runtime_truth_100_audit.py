#!/usr/bin/env python3
"""Final evidence audit for runtime truth spine 100/100 readiness."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT_FOR_IMPORT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_FOR_IMPORT))

from dharma_swarm.operator_core.live_ops_census_contract import (  # noqa: E402
    DEFAULT_STATE_ROOT,
)
from scripts.runtime.runtime_truth_closeout import (  # noqa: E402
    DEFAULT_MAX_CLEAN_EPOCH_DECLARATIONS,
    DEFAULT_MIN_LATEST_MAJOR,
    DEFAULT_MIN_TERMINAL_MAJOR,
    _build_census,
    evaluate_closeout,
)


SCHEMA_VERSION = "runtime_truth_100_audit.v1"
DEFAULT_DAEMON_URL = "http://127.0.0.1:7433/runtime-truth"
DEFAULT_DASHBOARD_URL = "http://127.0.0.1:8420/api/health?runtime_truth=true"
DEFAULT_REPORT = Path("reports/runtime_truth/runtime_truth_100_audit_latest.json")
TWO_HOUR_PATTERN = "runtime_truth_burn_in_2h_*.json"
OVERNIGHT_PATTERN = "runtime_truth_burn_in_overnight_*.json"
DEFAULT_MAX_BURN_IN_AGE_HOURS = 24.0


@dataclass(frozen=True)
class AuditCheck:
    check_id: str
    passed: bool
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.check_id,
            "status": "pass" if self.passed else "fail",
            "passed": self.passed,
            "evidence": self.evidence,
        }


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _utc_now_datetime() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _parse_timestamp(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _fetch_json(url: str, *, timeout: float = 5.0) -> tuple[dict[str, Any], str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, json.JSONDecodeError, urllib.error.URLError) as exc:
        return {}, exc.__class__.__name__
    return payload if isinstance(payload, dict) else {}, "ok"


def _find_latest_report(repo_root: Path, pattern: str) -> Path | None:
    report_dir = repo_root / "reports" / "runtime_truth"
    candidates = sorted(
        (path for path in report_dir.glob(pattern) if path.is_file()),
        key=lambda path: (path.stat().st_mtime, path.name),
    )
    return candidates[-1] if candidates else None


def _dashboard_runtime_truth(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return {}
    truth = data.get("runtime_truth")
    return truth if isinstance(truth, dict) else {}


def _burn_in_duration_evidence(
    report: dict[str, Any],
    *,
    min_duration_seconds: float,
    report_path: Path | None = None,
    max_age_hours: float | None = None,
    now: datetime | None = None,
) -> tuple[bool, str]:
    if not report:
        return False, "report missing"
    passed = report.get("passed") is True
    strict = report.get("strict_unpaused_proven") is True
    duration = float(report.get("requested_duration_seconds") or 0.0)
    samples_met = report.get("sample_count_met") is True
    samples_passed = report.get("all_samples_passed") is True
    sample_count = int(report.get("sample_count") or 0)
    min_samples = int(report.get("min_samples") or 0)
    freshness_ok = True
    freshness_evidence = "freshness=not_checked"
    if max_age_hours is not None:
        completed_at = _parse_timestamp(
            report.get("completed_at") or report.get("generated_at")
        )
        timestamp_source = "completed_at"
        if completed_at is None and report_path is not None:
            try:
                completed_at = datetime.fromtimestamp(report_path.stat().st_mtime, UTC)
                timestamp_source = "file_mtime"
            except OSError:
                completed_at = None
        if completed_at is None:
            freshness_ok = False
            freshness_evidence = f"freshness=missing; max_age_hours={max_age_hours:g}"
        else:
            anchor = now or _utc_now_datetime()
            age_hours = (anchor - completed_at).total_seconds() / 3600.0
            freshness_ok = 0.0 <= age_hours <= max_age_hours
            freshness_evidence = (
                f"freshness={timestamp_source}; "
                f"age_hours={age_hours:.2f}/{max_age_hours:g}"
            )
    ok = (
        passed
        and strict
        and duration >= min_duration_seconds
        and samples_met
        and samples_passed
        and freshness_ok
    )
    return (
        ok,
        (
            f"passed={passed}; strict={strict}; "
            f"duration={duration:g}/{min_duration_seconds:g}; "
            f"samples={sample_count}/{min_samples}; "
            f"all_samples_passed={samples_passed}; "
            f"{freshness_evidence}"
        ),
    )


def _path_text(path: Path | None, repo_root: Path) -> str:
    if path is None:
        return "missing"
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def build_audit(
    *,
    repo_root: Path,
    state_root: Path,
    two_hour_report: Path | None,
    overnight_report: Path | None,
    daemon_url: str,
    dashboard_url: str,
    http_timeout_seconds: float,
    min_two_hour_seconds: float,
    min_overnight_seconds: float,
    min_latest_major: int,
    min_terminal_major: int,
    max_clean_epoch_declarations: int,
    max_burn_in_age_hours: float | None,
    skip_http: bool,
) -> dict[str, Any]:
    repo_root = repo_root.expanduser().resolve()
    state_root = state_root.expanduser()
    two_hour_path = two_hour_report or _find_latest_report(repo_root, TWO_HOUR_PATTERN)
    overnight_path = overnight_report or _find_latest_report(repo_root, OVERNIGHT_PATTERN)

    closeout = evaluate_closeout(
        _build_census(repo_root, state_root),
        state_root=state_root,
        min_latest_major=min_latest_major,
        min_terminal_major=min_terminal_major,
        max_clean_epoch_declarations=max_clean_epoch_declarations,
    )
    two_hour = _load_json(two_hour_path)
    overnight = _load_json(overnight_path)

    checks: list[AuditCheck] = [
        AuditCheck(
            "runtime_truth_closeout",
            closeout.get("passed") is True,
            f"status={closeout.get('status')}; canonical_db={closeout.get('canonical_db')}",
        ),
    ]

    if skip_http:
        checks.append(AuditCheck("daemon_runtime_truth_endpoint", True, "skipped"))
        checks.append(AuditCheck("dashboard_runtime_truth_health", True, "skipped"))
    else:
        daemon_payload, daemon_error = _fetch_json(
            daemon_url,
            timeout=http_timeout_seconds,
        )
        checks.append(
            AuditCheck(
                "daemon_runtime_truth_endpoint",
                daemon_payload.get("passed") is True,
                (
                    f"status={daemon_payload.get('status')}; url={daemon_url}"
                    if daemon_payload
                    else f"error={daemon_error}; url={daemon_url}"
                ),
            )
        )
        dashboard_payload, dashboard_error = _fetch_json(
            dashboard_url,
            timeout=http_timeout_seconds,
        )
        dashboard_truth = _dashboard_runtime_truth(dashboard_payload)
        dashboard_data = dashboard_payload.get("data")
        dashboard_status = (
            dashboard_data.get("overall_status")
            if isinstance(dashboard_data, dict)
            else None
        )
        checks.append(
            AuditCheck(
                "dashboard_runtime_truth_health",
                dashboard_truth.get("passed") is True and dashboard_status == "healthy",
                (
                    f"overall_status={dashboard_status}; "
                    f"runtime_truth={dashboard_truth.get('status')}; url={dashboard_url}"
                    if dashboard_payload
                    else f"error={dashboard_error}; url={dashboard_url}"
                ),
            )
        )

    ci_target = (repo_root / "Makefile").read_text(encoding="utf-8")
    workflow_path = repo_root / ".github" / "workflows" / "runtime-truth.yml"
    checks.append(
        AuditCheck(
            "runtime_truth_ci_declared",
            "runtime-truth-ci:" in ci_target and workflow_path.exists(),
            f"make_target={'runtime-truth-ci:' in ci_target}; workflow={workflow_path.exists()}",
        )
    )

    two_hour_passed, two_hour_evidence = _burn_in_duration_evidence(
        two_hour,
        min_duration_seconds=min_two_hour_seconds,
        report_path=two_hour_path,
        max_age_hours=max_burn_in_age_hours,
    )
    checks.append(
        AuditCheck(
            "two_hour_strict_burn_in",
            two_hour_passed,
            f"path={_path_text(two_hour_path, repo_root)}; {two_hour_evidence}",
        )
    )

    overnight_passed, overnight_evidence = _burn_in_duration_evidence(
        overnight,
        min_duration_seconds=min_overnight_seconds,
        report_path=overnight_path,
        max_age_hours=max_burn_in_age_hours,
    )
    checks.append(
        AuditCheck(
            "overnight_strict_burn_in",
            overnight_passed,
            f"path={_path_text(overnight_path, repo_root)}; {overnight_evidence}",
        )
    )

    passed = all(check.passed for check in checks)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "status": "pass" if passed else "fail",
        "passed": passed,
        "repo_root": str(repo_root),
        "state_root": str(state_root),
        "inputs": {
            "two_hour_report": _path_text(two_hour_path, repo_root),
            "overnight_report": _path_text(overnight_path, repo_root),
            "daemon_url": daemon_url,
            "dashboard_url": dashboard_url,
            "http_timeout_seconds": http_timeout_seconds,
            "min_two_hour_seconds": min_two_hour_seconds,
            "min_overnight_seconds": min_overnight_seconds,
            "min_latest_major": min_latest_major,
            "min_terminal_major": min_terminal_major,
            "max_clean_epoch_declarations": max_clean_epoch_declarations,
            "max_burn_in_age_hours": max_burn_in_age_hours,
            "skip_http": skip_http,
        },
        "closeout": closeout,
        "checks": [check.to_dict() for check in checks],
    }


def _print_text(report: dict[str, Any]) -> None:
    print("RUNTIME TRUTH 100 AUDIT")
    print(f"status: {report['status']}")
    for check in report.get("checks") or []:
        print(
            f"{str(check.get('status', '')).upper():<4} {check.get('id')}: "
            f"{check.get('evidence') or ''}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT_FOR_IMPORT)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--two-hour-report", type=Path, default=None)
    parser.add_argument("--overnight-report", type=Path, default=None)
    parser.add_argument("--daemon-url", default=DEFAULT_DAEMON_URL)
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL)
    parser.add_argument("--http-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--min-two-hour-seconds", type=float, default=7200.0)
    parser.add_argument("--min-overnight-seconds", type=float, default=28800.0)
    parser.add_argument("--min-latest-major", type=int, default=DEFAULT_MIN_LATEST_MAJOR)
    parser.add_argument("--min-terminal-major", type=int, default=DEFAULT_MIN_TERMINAL_MAJOR)
    parser.add_argument(
        "--max-clean-epoch-declarations",
        type=int,
        default=DEFAULT_MAX_CLEAN_EPOCH_DECLARATIONS,
    )
    parser.add_argument(
        "--max-burn-in-age-hours",
        type=float,
        default=DEFAULT_MAX_BURN_IN_AGE_HOURS,
        help="Reject older burn-in reports; pass a negative value to disable.",
    )
    parser.add_argument("--skip-http", action="store_true")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--no-write-report", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = build_audit(
        repo_root=args.repo_root,
        state_root=args.state_root,
        two_hour_report=args.two_hour_report,
        overnight_report=args.overnight_report,
        daemon_url=str(args.daemon_url),
        dashboard_url=str(args.dashboard_url),
        http_timeout_seconds=max(1.0, args.http_timeout_seconds),
        min_two_hour_seconds=max(0.0, args.min_two_hour_seconds),
        min_overnight_seconds=max(0.0, args.min_overnight_seconds),
        min_latest_major=max(0, args.min_latest_major),
        min_terminal_major=max(0, args.min_terminal_major),
        max_clean_epoch_declarations=max(0, args.max_clean_epoch_declarations),
        max_burn_in_age_hours=(
            None
            if args.max_burn_in_age_hours < 0
            else max(0.0, args.max_burn_in_age_hours)
        ),
        skip_http=args.skip_http,
    )
    if not args.no_write_report:
        _write_json_atomic(args.report.expanduser(), report)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_text(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
