"""Sentry Spotlight adapter — local-dev telemetry to slop signal.

Two evidence sources, both opt-in, both fail-graceful:

1. **Live probe** (HTTP): checks if a Spotlight sidecar is reachable
   (default http://localhost:8969). Liveness alone is metadata, not a
   finding — it tells the system whether behavioral evidence is even
   available for this run.

2. **Offline envelope reader**: parses Sentry envelopes captured during
   a prior test run from ~/.dharma/spotlight_events/<date>/*.json.
   Operator workflow: run tests with Sentry SDK pointed at Spotlight,
   export the buffer, drop into the directory. This adapter then mines
   the envelopes for slop signals.

Findings produced (when envelopes are present):

  AI_SLOP family
    - broad_exception_swallow: error events with type=Exception and
      no message, suggesting `except Exception: pass`-style code
    - implausible_perf: span events with duration < 1ms on operations
      that nominally do real work (heuristic on op name)
    - silent_no_op: function trace with no child spans and no return
      side effects (heuristic on transaction shape)

  BEHAVIORAL family
    - zero_trace: source files in scope with no traces in the
      envelope set — cold-path / dead-on-this-run signal
    - high_error_rate: source files with err/event ratio above
      threshold

Live SSE event capture and full MCP integration are explicit Phase 3
follow-ups; this adapter ships the offline path that's testable today.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.slop.adapters.base import empty_result, normalize_path
from dharma_swarm.slop.models import (
    DetectorFamily,
    DetectorResult,
    Finding,
    Severity,
)

TOOL = "sentry-spotlight"
DEFAULT_URL = os.environ.get("SPOTLIGHT_URL", "http://localhost:8969")
DEFAULT_EVENTS_DIR = Path(
    os.environ.get(
        "SPOTLIGHT_EVENTS_DIR",
        str(Path.home() / ".dharma" / "spotlight_events"),
    )
)
LIVENESS_TIMEOUT_SEC = 0.5
IMPLAUSIBLE_PERF_MS = 1.0
HIGH_ERROR_RATE = 0.10


@dataclass(frozen=True, slots=True)
class SpotlightProbe:
    url: str
    reachable: bool
    error: str | None = None


def probe_spotlight(url: str = DEFAULT_URL, *, timeout: float = LIVENESS_TIMEOUT_SEC) -> SpotlightProbe:
    """HTTP HEAD/GET probe to confirm a Spotlight sidecar is up.

    Spotlight's sidecar serves health on the root path. We accept any
    2xx/3xx as 'reachable' since the sidecar's exact health route varies
    by version.
    """
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ok = 200 <= resp.status < 400
        return SpotlightProbe(url=url, reachable=ok)
    except urllib.error.URLError as exc:
        return SpotlightProbe(url=url, reachable=False, error=str(exc.reason))
    except (TimeoutError, socket.timeout) as exc:
        return SpotlightProbe(url=url, reachable=False, error=f"timeout: {exc}")
    except OSError as exc:
        return SpotlightProbe(url=url, reachable=False, error=str(exc))


def _iter_envelope_files(events_dir: Path) -> list[Path]:
    if not events_dir.exists() or not events_dir.is_dir():
        return []
    return sorted(p for p in events_dir.rglob("*.json") if p.is_file())


def _parse_envelope(raw: str) -> dict | None:
    raw = raw.strip()
    if not raw:
        return None
    if "\n" in raw:
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and ("type" in obj or "event_id" in obj or "exception" in obj):
                return obj
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _classify_envelope(env: dict, repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    typ = (env.get("type") or "").lower()
    transaction = env.get("transaction")
    contexts = env.get("contexts") or {}

    location = _location_from_envelope(env, repo_root)
    if not location:
        return findings
    path, line = location

    if typ == "event" or "exception" in env:
        exc = env.get("exception") or {}
        values = exc.get("values") if isinstance(exc, dict) else None
        if values and isinstance(values, list) and values:
            v0 = values[0]
            exc_type = str(v0.get("type") or "")
            exc_value = str(v0.get("value") or "").strip()
            if exc_type in ("Exception", "BaseException") and not exc_value:
                findings.append(
                    Finding(
                        tool=TOOL,
                        family=DetectorFamily.AI_SLOP,
                        issue_type="broad_exception_swallow",
                        path=path,
                        line=line,
                        symbol=transaction,
                        severity=Severity.MEDIUM,
                        confidence=0.75,
                        evidence=f"raised {exc_type} with no message at {transaction}",
                        suggested_action="Replace bare 'except Exception' with specific exception type and meaningful message",
                    )
                )

    if typ == "transaction" or "spans" in env:
        duration_ms = _duration_ms(env)
        spans = env.get("spans") or []
        if duration_ms is not None and duration_ms < IMPLAUSIBLE_PERF_MS:
            op = (env.get("contexts") or {}).get("trace", {}).get("op", "")
            heavy_op = any(
                marker in str(op).lower()
                for marker in ("db", "query", "http", "compute", "process", "transform")
            )
            if heavy_op:
                findings.append(
                    Finding(
                        tool=TOOL,
                        family=DetectorFamily.AI_SLOP,
                        issue_type="implausible_perf",
                        path=path,
                        line=line,
                        symbol=transaction,
                        severity=Severity.LOW,
                        confidence=0.55,
                        evidence=f"op={op} ran in {duration_ms:.3f}ms (claims real work, no observable computation)",
                        suggested_action="Verify the function actually performs the work it claims; mimicry pattern",
                    )
                )
        if duration_ms is not None and not spans and transaction:
            findings.append(
                Finding(
                    tool=TOOL,
                    family=DetectorFamily.AI_SLOP,
                    issue_type="silent_no_op",
                    path=path,
                    line=line,
                    symbol=transaction,
                    severity=Severity.LOW,
                    confidence=0.45,
                    evidence=f"transaction {transaction} had no child spans (no observable side effects)",
                    suggested_action="Confirm function produces actual side effects; ceremonial-code pattern",
                )
            )
    return findings


def _location_from_envelope(env: dict, repo_root: Path) -> tuple[str, int | None] | None:
    """Best-effort extraction of (path, line) from a Sentry envelope."""
    exc = env.get("exception")
    if isinstance(exc, dict):
        values = exc.get("values") or []
        if values and isinstance(values[0], dict):
            stacktrace = values[0].get("stacktrace") or {}
            frames = stacktrace.get("frames") or []
            for frame in reversed(frames):
                if not isinstance(frame, dict):
                    continue
                if frame.get("in_app") is False:
                    continue
                fname = frame.get("filename") or frame.get("abs_path")
                if not fname:
                    continue
                lineno = frame.get("lineno")
                return normalize_path(str(fname), repo_root), int(lineno) if isinstance(lineno, int) else None
    contexts = env.get("contexts") or {}
    trace = contexts.get("trace") if isinstance(contexts, dict) else None
    if isinstance(trace, dict):
        location = trace.get("location") or trace.get("file")
        if location:
            return normalize_path(str(location), repo_root), None
    transaction = env.get("transaction")
    if transaction and "/" in str(transaction):
        return normalize_path(str(transaction).split(":")[0], repo_root), None
    return None


def _duration_ms(env: dict) -> float | None:
    start = env.get("start_timestamp")
    end = env.get("timestamp")
    if not (isinstance(start, (int, float)) and isinstance(end, (int, float))):
        return None
    delta = (end - start) * 1000.0
    return delta if delta >= 0 else None


def _scope_paths(paths: Iterable[Path], repo_root: Path) -> set[str]:
    scope: set[str] = set()
    for p in paths:
        try:
            scope.add(str(p.resolve().relative_to(repo_root.resolve())))
        except ValueError:
            scope.add(str(p))
    return scope


def _high_error_rate_findings(
    envelope_files: list[Path],
    repo_root: Path,
) -> list[Finding]:
    """Aggregate error/total ratio per file; flag files above HIGH_ERROR_RATE."""
    total_per_path: dict[str, int] = {}
    error_per_path: dict[str, int] = {}
    for env_file in envelope_files:
        try:
            env = _parse_envelope(env_file.read_text(encoding="utf-8"))
        except OSError:
            continue
        if env is None:
            continue
        loc = _location_from_envelope(env, repo_root)
        if not loc:
            continue
        path = loc[0]
        total_per_path[path] = total_per_path.get(path, 0) + 1
        is_error = (env.get("type") or "").lower() == "event" or "exception" in env
        if is_error:
            error_per_path[path] = error_per_path.get(path, 0) + 1
    findings: list[Finding] = []
    for path, total in total_per_path.items():
        if total < 4:
            continue
        errors = error_per_path.get(path, 0)
        rate = errors / total
        if rate >= HIGH_ERROR_RATE:
            findings.append(
                Finding(
                    tool=TOOL,
                    family=DetectorFamily.BEHAVIORAL,
                    issue_type="high_error_rate",
                    path=path,
                    line=None,
                    symbol=None,
                    severity=Severity.MEDIUM,
                    confidence=min(0.85, 0.40 + rate),
                    evidence=f"{errors}/{total} captured events were errors ({rate:.1%}, threshold {HIGH_ERROR_RATE:.0%})",
                    suggested_action="Investigate failure modes; high error density suggests undertested or AI-shipped logic",
                )
            )
    return findings


def _zero_trace_findings(
    scope_paths: set[str],
    seen_paths: set[str],
) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(scope_paths - seen_paths):
        findings.append(
            Finding(
                tool=TOOL,
                family=DetectorFamily.BEHAVIORAL,
                issue_type="zero_trace",
                path=path,
                line=None,
                symbol=None,
                severity=Severity.INFO,
                confidence=0.40,
                evidence="no Sentry events for this file across captured envelopes",
                suggested_action="Confirm file is exercised by tests; if intentionally inert, mark as such",
            )
        )
    return findings


def run_spotlight(
    paths: Iterable[Path],
    *,
    repo_root: Path | None = None,
    events_dir: Path | None = None,
    url: str | None = None,
    require_envelopes: bool = False,
) -> DetectorResult:
    repo_root = repo_root or Path.cwd()
    events_dir = events_dir or DEFAULT_EVENTS_DIR
    paths_list = list(paths)
    if not paths_list:
        return empty_result(TOOL, DetectorFamily.BEHAVIORAL, "no paths supplied")

    probe = probe_spotlight(url or DEFAULT_URL)
    envelope_files = _iter_envelope_files(events_dir)

    if not envelope_files and not probe.reachable:
        msg = (
            f"Spotlight not reachable at {probe.url} ({probe.error}); "
            f"no envelope files in {events_dir}"
        )
        return DetectorResult(
            tool=TOOL,
            family=DetectorFamily.BEHAVIORAL,
            findings=[],
            duration_sec=0.0,
            exit_code=0 if not require_envelopes else 1,
            error=msg if require_envelopes else None,
        )

    findings: list[Finding] = []
    seen_paths: set[str] = set()
    for env_file in envelope_files:
        try:
            env = _parse_envelope(env_file.read_text(encoding="utf-8"))
        except OSError:
            continue
        if env is None:
            continue
        loc = _location_from_envelope(env, repo_root)
        if loc:
            seen_paths.add(loc[0])
        findings.extend(_classify_envelope(env, repo_root))

    if envelope_files:
        scope = _scope_paths(paths_list, repo_root)
        findings.extend(_zero_trace_findings(scope, seen_paths))
        findings.extend(_high_error_rate_findings(envelope_files, repo_root))

    return DetectorResult(
        tool=TOOL,
        family=DetectorFamily.BEHAVIORAL,
        findings=findings,
        duration_sec=0.0,
        exit_code=0,
        error=None,
    )


__all__ = [
    "DEFAULT_EVENTS_DIR",
    "DEFAULT_URL",
    "SpotlightProbe",
    "probe_spotlight",
    "run_spotlight",
]
