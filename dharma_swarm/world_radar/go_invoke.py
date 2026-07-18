"""Go subprocess invocation + health parsing for the world-radar bridge.

Split out of ``go_bridge.py`` (module line budget, Rule 10): this layer owns
how the Go organs (``tools/world_scout_go``, ``tools/world_signal_ingestor_go``)
are invoked (prebuilt binary vs ``go run .``) and how their untrusted health
JSON is parsed into counts and structured per-source errors. ``go_bridge``
re-exports these names so existing callers and tests keep patching
``go_bridge._run_go_scout`` / ``go_bridge._run_go_ingestor``.
"""

from __future__ import annotations

from pathlib import Path
import os
import re
import shutil
import subprocess
from typing import Any

from dharma_swarm.operator_core.world_radar.receipt_bridge import (
    project_world_signal_receipts,
    receipt_paths,
)
from dharma_swarm.world_radar.io_utils import (
    read_json as _read_json,
    read_jsonl as _read_jsonl,
    repo_root as _repo_root,
)


def _version_tuple(major: str, minor: str, patch: str | None) -> tuple[int, int, int]:
    # A missing patch component is a .0 floor: `go 1.26` means 1.26.0, which is
    # satisfied by any 1.26.x toolchain.
    return int(major), int(minor), int(patch) if patch is not None else 0


def go_module_directive(module_dir: Path) -> tuple[int, int, int] | None:
    """Parse the ``go X.Y[.Z]`` directive from ``module_dir/go.mod``.

    Returns a full ``(major, minor, patch)`` tuple (patch defaults to 0 when
    the directive omits it — Go treats ``go 1.26`` as the ``1.26.0`` minimum).
    Returns ``None`` when the file is unreadable or carries no directive —
    callers must treat ``None`` as fail-closed (WP-0C2, TIT-003: an
    unreadable ``go.mod`` never authorizes execution).
    """
    try:
        text = (module_dir / "go.mod").read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"^go (\d+)\.(\d+)(?:\.(\d+))?", text, re.MULTILINE)
    if match is None:
        return None
    return _version_tuple(match.group(1), match.group(2), match.group(3))


def installed_go_version(go_bin: str | None = None) -> tuple[int, int, int] | None:
    """Return the installed Go toolchain's ``(major, minor, patch)``, or None.

    ``None`` covers every failure mode — no binary on PATH, the binary not
    executing, a NON-ZERO exit from ``go version`` (a broken shim can still
    emit a parseable banner), or malformed output — so consumers fail closed
    (WP-0C2, TIT-003: presence is not capability). The patch component is
    preserved so a ``go 1.26.1`` module is not treated as satisfied by a
    ``go1.26.0`` host.
    """
    binary = go_bin if go_bin is not None else shutil.which("go")
    if binary is None:
        return None
    try:
        proc = subprocess.run(
            [binary, "version"], text=True, capture_output=True,
            check=False, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    match = re.search(r"go(\d+)\.(\d+)(?:\.(\d+))?", proc.stdout or "")
    if match is None:
        return None
    return _version_tuple(match.group(1), match.group(2), match.group(3))


def go_toolchain_capable(module_dir: Path, go_bin: str | None = None) -> bool:
    """One version-aware Go capability answer for every Go bridge (WP-0C2).

    True only when an installed toolchain's version satisfies the module's
    exact ``go`` directive. Any unreadable input — missing toolchain,
    malformed ``go version`` output, unreadable ``go.mod`` — is False
    (fail closed). Promoted from the version check previously private to
    tests/test_go_adapter_contracts.py so tests and production share one
    oracle (TIT-003: Go presence was mistaken for Go compatibility).
    """
    required = go_module_directive(module_dir)
    if required is None:
        return False
    installed = installed_go_version(go_bin)
    if installed is None:
        return False
    return installed >= required


def _go_invocation(module_dir: Path) -> tuple[list[str], str]:
    """Prefer a prebuilt module binary (see `make go-build`); fall back to `go run .`.

    The binary convention matches plain ``go build`` output: the module dir
    name inside the module dir (e.g. ``tools/world_scout_go/world_scout_go``).
    Returns the argv prefix and the invocation mode ("binary", "go_run", or
    "needs_host"). Version-aware (WP-0C2, TIT-003): ``go run .`` is offered
    only when :func:`go_toolchain_capable` confirms the installed toolchain
    satisfies the module's ``go.mod`` directive — a present-but-incompatible
    toolchain is ``needs_host``, not an execution attempt. A prebuilt binary
    works without any toolchain. With neither, the mode is ``needs_host``
    with an empty argv, and callers must NOT invoke — they return a
    structured per-source error (see :func:`_needs_host_error`) instead of
    letting the subprocess raise ``FileNotFoundError``.
    """
    binary = module_dir / module_dir.name
    if binary.is_file() and os.access(binary, os.X_OK):
        return [str(binary)], "binary"
    if go_toolchain_capable(module_dir):
        return ["go", "run", "."], "go_run"
    return [], "needs_host"


def _needs_host_error(module_name: str) -> str:
    """Structured needs-host message naming the missing prerequisite + fix."""
    return (
        f"no prebuilt {module_name} binary and no Go toolchain satisfying the "
        "module's go.mod directive — run `make go-build` (or install a "
        "compatible Go) on this host"
    )


def _run_go_scout(
    *,
    state: Path,
    output_path: Path,
    health_path: Path,
    timeout_s: int,
    queries: list[str] | None = None,
    cascade_for: str = "",
    beats: bool = False,
    archive: bool = False,
    archive_dir: Path | None = None,
    archive_urls: list[str] | None = None,
    archive_url_files: list[str] | None = None,
    archive_source_specs: list[str] | None = None,
    archive_max_bytes: int = 2_000_000,
    archive_max_pages: int = 100,
    archive_max_depth: int = 0,
    archive_same_domain: bool = True,
    archive_rate_limit_ms: int = 100,
    archive_robots: bool = True,
    archive_default_crawl_delay_ms: int = 0,
    archive_max_retries: int = 1,
    archive_retry_base_delay_ms: int = 250,
    archive_retry_max_delay_ms: int = 2000,
    archive_max_fetch_duration_ms: int = 30000,
    archive_include: list[str] | None = None,
    archive_exclude: list[str] | None = None,
    archive_workers: int = 6,
    archive_discover_llms: bool = False,
    archive_discover_sitemap: bool = False,
    archive_sitemap_max_urls: int = 100,
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any]]:
    module_dir = _repo_root() / "tools" / "world_scout_go"
    if not module_dir.exists():
        return [], f"missing Go scout module: {module_dir}", {}
    cmd, invocation_mode = _go_invocation(module_dir)
    if invocation_mode == "needs_host":
        error = _needs_host_error("world_scout_go")
        return (
            [],
            error,
            {
                "successful_sources": 0,
                "failed_sources": 0,
                "invocation_mode": invocation_mode,
                "source_errors": [
                    {"source": "world_scout_go", "stage": "scout", "error": error}
                ],
            },
        )
    cmd += [
        "--state-dir",
        str(state),
        "--output",
        str(output_path),
        "--health",
        str(health_path),
        "--fetch",
    ]
    if cascade_for:
        cmd.extend(["--cascade-for", cascade_for])
    for query in queries or []:
        cmd.extend(["--query", query])
    if beats:
        cmd.append("--beats")
    if archive:
        effective_archive_dir = archive_dir or (state / "meta" / "world_radar" / "archive" / "world_scout")
        cmd.extend(["--archive", "--archive-dir", str(effective_archive_dir)])
        cmd.extend(["--archive-max-bytes", str(archive_max_bytes)])
        cmd.extend(["--archive-max-pages", str(archive_max_pages)])
        cmd.extend(["--archive-max-depth", str(archive_max_depth)])
        cmd.append(f"--archive-same-domain={str(archive_same_domain).lower()}")
        cmd.extend(["--archive-rate-limit-ms", str(archive_rate_limit_ms)])
        cmd.append(f"--archive-robots={str(archive_robots).lower()}")
        cmd.extend(["--archive-default-crawl-delay-ms", str(archive_default_crawl_delay_ms)])
        cmd.extend(["--archive-max-retries", str(archive_max_retries)])
        cmd.extend(["--archive-retry-base-delay-ms", str(archive_retry_base_delay_ms)])
        cmd.extend(["--archive-retry-max-delay-ms", str(archive_retry_max_delay_ms)])
        cmd.extend(["--archive-max-fetch-duration-ms", str(archive_max_fetch_duration_ms)])
        cmd.extend(["--archive-workers", str(archive_workers)])
        cmd.extend(["--archive-sitemap-max-urls", str(archive_sitemap_max_urls)])
        if archive_discover_llms:
            cmd.append("--archive-discover-llms")
        if archive_discover_sitemap:
            cmd.append("--archive-discover-sitemap")
        for raw_url in archive_urls or []:
            cmd.extend(["--query-url", raw_url])
        for url_file in archive_url_files or []:
            cmd.extend(["--query-url-file", url_file])
        for spec_file in archive_source_specs or []:
            cmd.extend(["--source-spec", spec_file])
        for pattern in archive_include or []:
            cmd.extend(["--archive-include", pattern])
        for pattern in archive_exclude or []:
            cmd.extend(["--archive-exclude", pattern])
    try:
        proc = subprocess.run(cmd, cwd=module_dir, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        return [], f"world_scout_go could not start: {exc}", {"invocation_mode": invocation_mode}
    except subprocess.TimeoutExpired:
        health = _read_json(health_path, default={})
        counts = _source_counts(health)
        counts["invocation_mode"] = invocation_mode
        counts["source_errors"] = _health_source_errors(health)
        return [], f"world_scout_go timed out after {timeout_s}s", counts
    health = _read_json(health_path, default={})
    counts = _source_counts(health)
    counts["invocation_mode"] = invocation_mode
    counts["source_errors"] = _health_source_errors(health)
    if proc.returncode != 0:
        return [], (proc.stderr or proc.stdout or "world_scout_go failed").strip()[:1000], counts
    return _read_jsonl(output_path), _partial_source_error(health), counts


def _run_go_ingestor(
    *,
    input_path: Path,
    output_path: Path,
    min_score: float,
    timeout_s: int,
    receipt_dir: Path | None = None,
    correlation_id: str = "",
) -> tuple[list[dict[str, Any]], str | None, str]:
    module_dir = _repo_root() / "tools" / "world_signal_ingestor_go"
    if not module_dir.exists():
        return [], f"missing Go ingestor module: {module_dir}", ""
    cmd, invocation_mode = _go_invocation(module_dir)
    if invocation_mode == "needs_host":
        return [], _needs_host_error("world_signal_ingestor_go"), invocation_mode
    cmd += [
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--min-score",
        str(min_score),
    ]
    if receipt_dir is not None and correlation_id:
        cmd.extend(["--receipt-dir", str(receipt_dir), "--correlation-id", correlation_id])
    try:
        proc = subprocess.run(cmd, cwd=module_dir, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        return [], f"world_signal_ingestor_go could not start: {exc}", invocation_mode
    except subprocess.TimeoutExpired:
        return [], f"world_signal_ingestor_go timed out after {timeout_s}s", invocation_mode
    if proc.returncode != 0:
        return (
            [],
            (proc.stderr or proc.stdout or "world_signal_ingestor_go failed").strip()[:1000],
            invocation_mode,
        )
    if receipt_dir is not None and correlation_id:
        projected_rows = _project_receipts_for_correlation(receipt_dir, correlation_id)
        if projected_rows:
            return projected_rows, None, invocation_mode
    return _read_jsonl(output_path), None, invocation_mode


def _project_receipts_for_correlation(receipt_dir: Path, correlation_id: str) -> list[dict[str, Any]]:
    rows = project_world_signal_receipts(receipt_paths(receipt_dir))
    return [
        row
        for row in rows
        if isinstance(row.get("metadata"), dict)
        and row["metadata"].get("correlation_id") == correlation_id
    ]


def _coerce_int(value: Any) -> int:
    """Best-effort int coercion for untrusted Go-subprocess health JSON.

    Never raises: a malformed/non-numeric field (missing, null, or a string
    that isn't a number) becomes 0 instead of crashing the caller -- health
    parsing must stay advisory, never fatal to the scout (Copilot review
    finding, go_bridge.py:933).
    """
    try:
        parsed = int(float(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(parsed, 0)


def _source_counts(health: Any) -> dict[str, Any]:
    if not isinstance(health, dict):
        return {"successful_sources": 0, "failed_sources": 0}
    return {
        "successful_sources": _coerce_int(health.get("successful_sources")),
        "failed_sources": _coerce_int(health.get("failed_sources")),
        "retry_count": _coerce_int(health.get("retry_count")),
        "archive_enabled": bool(health.get("archive_enabled", False)),
        "archive_count": _coerce_int(health.get("archive_count")),
        "dedupe_count": _coerce_int(health.get("dedupe_count")),
        "archive_dir": str(health.get("archive_dir", "") or ""),
        "archive_index_path": str(health.get("archive_index_path", "") or ""),
        "archive_replay_index_path": str(health.get("archive_replay_index_path", "") or ""),
        "archive_manifest_path": str(health.get("archive_manifest_path", "") or ""),
        "archive_discovered_count": _coerce_int(health.get("archive_discovered_count")),
        "archive_workers": _coerce_int(health.get("archive_workers")),
        "archive_total_bytes": _coerce_int(health.get("archive_total_bytes")),
        "archive_clean_text_count": _coerce_int(health.get("archive_clean_text_count")),
        "archive_clean_text_bytes": _coerce_int(health.get("archive_clean_text_bytes")),
        "archive_error_count": _coerce_int(health.get("archive_error_count")),
    }


def _health_source_errors(health: Any, *, stage: str = "scout") -> list[dict[str, str]]:
    """Parse the Go scout health ``errors`` list into structured per-source rows.

    The Go side records failures as ``"<source_name>: <error>"`` strings
    (tools/world_scout_go/scout.go); non-conforming entries keep the whole
    string as the error with the module as the source.
    """
    if not isinstance(health, dict):
        return []
    raw_errors = health.get("errors") if isinstance(health.get("errors"), list) else []
    structured: list[dict[str, str]] = []
    for item in raw_errors:
        text = str(item).strip()
        if not text:
            continue
        source, sep, detail = text.partition(": ")
        if sep and source and " " not in source:
            structured.append({"source": source, "stage": stage, "error": detail.strip()})
        else:
            structured.append({"source": "world_scout_go", "stage": stage, "error": text})
    return structured


def _merged_source_errors(
    counts: Any,
    flat_error: str | None,
    *,
    source: str,
    stage: str,
) -> list[dict[str, str]]:
    """Combine structured per-source errors from counts with a module-level error."""
    structured: list[dict[str, str]] = []
    raw = counts.get("source_errors") if isinstance(counts, dict) else None
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            structured.append(
                {
                    "source": str(entry.get("source") or source),
                    "stage": stage,
                    "error": str(entry.get("error") or ""),
                }
            )
    if flat_error and not structured:
        structured.append({"source": source, "stage": stage, "error": str(flat_error)})
    return structured


def _partial_source_error(health: Any) -> str | None:
    if not isinstance(health, dict):
        return None
    successful = _coerce_int(health.get("successful_sources"))
    failed = _coerce_int(health.get("failed_sources"))
    if failed <= 0:
        return None
    if successful > 0:
        return None
    errors = health.get("errors") if isinstance(health.get("errors"), list) else []
    detail = "; ".join(str(item) for item in errors[:3])
    if detail:
        return f"world_scout_go partial source failures={failed}: {detail}"[:1000]
    return f"world_scout_go partial source failures={failed}"
