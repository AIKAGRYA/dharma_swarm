"""Fail-closed MemoryKernel context canary hooks."""

from __future__ import annotations

import json
import logging
import os
import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Literal

from dharma_swarm.memory_kernel.context_safety import (
    detect_text_safety_issues,
    safe_eval_ref,
)
from dharma_swarm.runtime_state import ContextBundleRecord

logger = logging.getLogger(__name__)

MemoryKernelContextMode = Literal["off", "shadow", "append"]

_VALID_CONTEXT_MODES = {"off", "shadow", "append"}
_MODE_ENV = "DHARMA_MEMORY_KERNEL_CONTEXT_MODE"
_HOME_ENV = "DHARMA_MEMORY_KERNEL_HOME"
_SURFACE_ENV_NAMES = (
    "DHARMA_MEMORY_KERNEL_CONTEXT_SURFACE_IDS",
    "DHARMA_MEMORY_KERNEL_CONTEXT_SURFACES",
)
_COMPILER_SURFACE_ENV_NAMES = (
    "DHARMA_MEMORY_KERNEL_CONTEXT_COMPILER_SURFACE_IDS",
    "DHARMA_MEMORY_KERNEL_CONTEXT_COMPILER_SURFACES",
    *_SURFACE_ENV_NAMES,
)
_SENSITIVE_FINDINGS = {
    "sensitive_path_detected",
    "secret_like_text_detected",
    "memory_pack_output_path_leak",
    "serialized_eval_output_path_leak",
}
_STALE_FRESHNESS = {"snapshot", "dormant", "missing", "unknown"}


@dataclass(frozen=True)
class MemoryKernelContextCanaryResult:
    mode: MemoryKernelContextMode
    rendered_text: str
    appended_section: str
    appended: bool
    report: object | None
    metadata: dict[str, object]
    fallback_reason: str | None = None


def run_memory_kernel_context_canary(
    legacy_text: str,
    *,
    query: str | None,
    limit: int = 5,
    token_budget: int | None = None,
    enabled: bool = False,
    requested_mode: str | None = None,
    home: Path | None = None,
    surface_ids: tuple[str, ...] = (),
    surface_env_names: tuple[str, ...] = _SURFACE_ENV_NAMES,
    legacy_shadow_env_names: tuple[str, ...] = ("DHARMA_MEMORY_KERNEL_CONTEXT_SHADOW",),
    memory_atoms: Iterable[object] | None = None,
) -> MemoryKernelContextCanaryResult:
    """Run the MemoryKernel context canary and return legacy text on failure."""

    mode, mode_warning = resolve_memory_kernel_context_mode(
        requested_mode,
        enabled=enabled,
        legacy_shadow_env_names=legacy_shadow_env_names,
    )
    if mode == "off" and mode_warning is None:
        return MemoryKernelContextCanaryResult(
            mode="off",
            rendered_text=legacy_text,
            appended_section="",
            appended=False,
            report=None,
            metadata={},
        )

    resolved_surface_ids = _resolve_surface_ids(surface_ids, surface_env_names)
    resolved_home = home or _path_env(_HOME_ENV)
    budget = _memory_context_budget(mode, limit=limit, token_budget=token_budget)
    warnings: list[str] = []
    if mode_warning:
        warnings.append(mode_warning)

    if mode_warning == "invalid_mode":
        return _metadata_only_result(
            legacy_text,
            mode=mode,
            surface_ids=resolved_surface_ids,
            fallback_reason="invalid_mode",
            warnings=warnings,
            hard_failures=1,
        )

    try:
        report = None
        atoms: tuple[object, ...] | None = None
        if memory_atoms is not None:
            atoms = tuple(memory_atoms)
        elif resolved_home is None or not resolved_surface_ids:
            report = _run_parity_report(
                legacy_text,
                query=query,
                memory_atoms=None,
                memory_kernel=None,
                surface_ids=(),
                budget=budget,
            )
            metadata = _canary_metadata(
                mode=mode,
                surface_ids=resolved_surface_ids,
                report=report,
                warnings=warnings,
                fallback_reason="missing_config",
                hard_failure_override=None,
            )
            return MemoryKernelContextCanaryResult(
                mode=mode,
                rendered_text=legacy_text,
                appended_section="",
                appended=False,
                report=replace(report, metadata=metadata),
                metadata=metadata,
                fallback_reason="missing_config",
            )
        else:
            atoms = _collect_live_atoms(
                home=resolved_home,
                surface_ids=resolved_surface_ids,
                budget=budget,
            )

        report = _run_parity_report(
            legacy_text,
            query=query,
            memory_atoms=atoms,
            memory_kernel=None,
            surface_ids=resolved_surface_ids,
            budget=budget,
        )
        fallback_reason = _fallback_reason_for_report(report, atoms or ())
        appended_section = ""
        appended = False
        rendered_text = legacy_text
        if mode == "append" and fallback_reason is None:
            appended_section = render_memory_kernel_append_section(report)
            scan_reason, scan_warnings = _scan_append_section(appended_section)
            warnings.extend(scan_warnings)
            if scan_reason:
                fallback_reason = scan_reason
                appended_section = ""
            else:
                rendered_text = _append_context_section(legacy_text, appended_section)
                appended = True
        elif mode == "shadow":
            fallback_reason = fallback_reason or None

        metadata = _canary_metadata(
            mode=mode,
            surface_ids=resolved_surface_ids,
            report=report,
            warnings=warnings,
            fallback_reason=fallback_reason,
            hard_failure_override=None,
        )
        return MemoryKernelContextCanaryResult(
            mode=mode,
            rendered_text=rendered_text,
            appended_section=appended_section,
            appended=appended,
            report=replace(report, metadata=metadata),
            metadata=metadata,
            fallback_reason=fallback_reason,
        )
    except Exception as exc:
        logger.debug("MemoryKernel context canary failed", exc_info=True)
        return _metadata_only_result(
            legacy_text,
            mode=mode,
            surface_ids=resolved_surface_ids,
            fallback_reason="exception",
            warnings=(
                *warnings,
                f"exception:{safe_eval_ref(type(exc).__name__)}",
            ),
            hard_failures=1,
        )


def resolve_memory_kernel_context_mode(
    requested_mode: str | None = None,
    *,
    enabled: bool = False,
    legacy_shadow_env_names: tuple[str, ...] = (),
) -> tuple[MemoryKernelContextMode, str | None]:
    raw_mode = (requested_mode or os.environ.get(_MODE_ENV, "")).strip().lower()
    if raw_mode:
        if raw_mode in _VALID_CONTEXT_MODES:
            return raw_mode, None  # type: ignore[return-value]
        return "off", "invalid_mode"
    if enabled or any(_truthy_env(name) for name in legacy_shadow_env_names):
        return "shadow", None
    return "off", None


def render_memory_kernel_append_section(report: object) -> str:
    memory_report = getattr(report, "memory_report", None)
    pack = getattr(memory_report, "pack", None)
    admitted_items = (
        [item for item in getattr(pack, "items", ()) if getattr(item, "admitted", False)]
        if pack is not None
        else []
    )
    surface_ids = _report_surface_ids(report)
    lines = [
        "## MemoryKernel Context Canary",
        "",
        "- mode: `append`",
        f"- surface_ids: `{', '.join(surface_ids) if surface_ids else '<none>'}`",
        f"- admitted_count: `{getattr(pack, 'admitted_count', 0) if pack is not None else 0}`",
        f"- hard_failures: `{getattr(report, 'hard_failure_count', 0)}`",
        "",
    ]
    if admitted_items:
        lines.append("### Admitted Atoms")
        lines.append("")
        for item in admitted_items[:8]:
            lines.append(
                f"- rank=`{getattr(item, 'rank', '')}` surface=`{getattr(item, 'surface_id', '')}` "
                f"type=`{_enum_value(getattr(item, 'atom_type', ''))}` "
                f"truth=`{_enum_value(getattr(item, 'truth_state', ''))}` "
                f"authority=`{_enum_value(getattr(item, 'authority_level', ''))}`"
            )
            snippet = getattr(item, "content_snippet", None)
            if snippet:
                lines.append(f"  snippet: `{_inline(snippet, 420)}`")
    else:
        lines.append("- no admitted atoms")
    return "\n".join(lines).rstrip()


async def notify_memory_kernel_context_callback(
    callback: Callable[[object], object] | None,
    report: object | None,
) -> None:
    if callback is None or report is None:
        return
    callback_result = callback(report)
    if hasattr(callback_result, "__await__"):
        await callback_result


async def notify_memory_kernel_context_canary(
    callback: Callable[[object], object] | None,
    canary: MemoryKernelContextCanaryResult,
) -> None:
    try:
        await notify_memory_kernel_context_callback(callback, canary.report)
    except Exception:
        logger.debug("MemoryKernel context canary callback failed", exc_info=True)


def memory_kernel_context_metadata(
    metadata: dict[str, Any] | None,
    canary: MemoryKernelContextCanaryResult,
) -> dict[str, Any]:
    payload = dict(metadata or {})
    if canary.metadata:
        payload["memory_kernel_context"] = dict(canary.metadata)
    return payload


def memory_kernel_context_source_refs(
    canary: MemoryKernelContextCanaryResult,
) -> tuple[str, ...]:
    surface_ids = canary.metadata.get("surface_ids", ()) if canary.metadata else ()
    return tuple(f"memory_kernel:{surface_id}" for surface_id in surface_ids)


def memory_kernel_context_section_dict(
    canary: MemoryKernelContextCanaryResult,
) -> dict[str, Any]:
    return {
        "name": "MemoryKernel Context Canary",
        "priority": 99,
        "content": canary.appended_section,
        "source_refs": list(memory_kernel_context_source_refs(canary)),
        "metadata": dict(canary.metadata),
    }


def bundle_with_memory_kernel_context_canary(
    bundle: ContextBundleRecord,
    canary: MemoryKernelContextCanaryResult,
) -> ContextBundleRecord:
    if not canary.metadata and not canary.appended:
        return bundle

    sections = list(bundle.sections)
    source_refs = list(bundle.source_refs)
    rendered_text = bundle.rendered_text
    if canary.appended:
        rendered_text = canary.rendered_text
        sections.append(memory_kernel_context_section_dict(canary))
        source_refs = _dedupe((*source_refs, *memory_kernel_context_source_refs(canary)))

    metadata = memory_kernel_context_metadata(bundle.metadata, canary)
    checksum = bundle.checksum
    if rendered_text != bundle.rendered_text or source_refs != bundle.source_refs:
        checksum = _sha256(
            _canonical_json(
                {
                    "session_id": bundle.session_id,
                    "task_id": bundle.task_id,
                    "run_id": bundle.run_id,
                    "rendered_text": rendered_text,
                    "source_refs": source_refs,
                }
            )
        )

    return replace(
        bundle,
        rendered_text=rendered_text,
        sections=sections,
        source_refs=source_refs,
        checksum=checksum,
        metadata=metadata,
    )


async def run_memory_kernel_context_compiler_shadow(
    bundle: ContextBundleRecord,
    *,
    query: str | None,
    token_budget: int,
    enabled: bool,
    home: Path | None,
    surface_ids: tuple[str, ...],
    callback: Callable[[object], object] | None,
) -> None:
    """Compatibility hook for callers that still ask for compiler shadow."""

    result = run_memory_kernel_context_canary(
        bundle.rendered_text,
        query=query,
        token_budget=token_budget,
        enabled=enabled,
        requested_mode=None,
        home=home,
        surface_ids=surface_ids,
        surface_env_names=_COMPILER_SURFACE_ENV_NAMES,
        legacy_shadow_env_names=(
            "DHARMA_MEMORY_KERNEL_CONTEXT_COMPILER_SHADOW",
            "DHARMA_MEMORY_KERNEL_CONTEXT_SHADOW",
        ),
    )
    await notify_memory_kernel_context_callback(callback, result.report)
    if result.mode == "off" and not result.metadata:
        return
    logger.debug(
        "MemoryKernel context compiler canary: bundle_id=%s mode=%s appended=%s fallback=%s metadata=%s",
        bundle.bundle_id,
        result.mode,
        result.appended,
        result.fallback_reason,
        result.metadata,
    )


def _collect_live_atoms(
    *,
    home: Path,
    surface_ids: tuple[str, ...],
    budget: object,
) -> tuple[object, ...]:
    from dharma_swarm.memory_kernel import (
        CensusConfig,
        MemoryKernel,
        MemoryKernelConfig,
        MemoryQuery,
    )

    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(
                repo_root=Path.cwd(),
                home=home,
                include_discovered=False,
            )
        )
    )
    query = MemoryQuery(
        limit_total=getattr(budget, "max_candidate_atoms"),
        limit_per_surface=getattr(budget, "max_candidate_atoms"),
        include_content=getattr(budget, "include_content"),
    )
    return tuple(
        kernel.iter_memory_atoms(
            surface_ids=surface_ids,
            query=query,
        )
    )


def _run_parity_report(
    legacy_text: str,
    *,
    query: str | None,
    memory_atoms: tuple[object, ...] | None,
    memory_kernel: object | None,
    surface_ids: tuple[str, ...],
    budget: object,
) -> object:
    from dharma_swarm.memory_kernel import run_context_parity_eval

    return run_context_parity_eval(
        query=query,
        current_context_text=legacy_text,
        state_dir=None,
        memory_kernel=memory_kernel,
        memory_atoms=memory_atoms,
        memory_surface_ids=surface_ids,
        budget=budget,
        allow_current_semantic_search=False,
    )


def _memory_context_budget(
    mode: MemoryKernelContextMode,
    *,
    limit: int,
    token_budget: int | None,
) -> object:
    from dharma_swarm.memory_kernel import MemoryContextBudget

    atom_budget = _canary_atom_budget(limit=limit, token_budget=token_budget)
    return MemoryContextBudget(
        max_candidate_atoms=atom_budget,
        max_admitted_atoms=max(1, min(atom_budget, 8)),
        max_total_chars=max(600, min(4000, atom_budget * 500)),
        max_atom_chars=500,
        include_content=mode == "append",
    )


def _canary_atom_budget(*, limit: int, token_budget: int | None) -> int:
    if token_budget is not None:
        return _shadow_atom_budget(token_budget)
    return max(1, min(50, max(1, int(limit))))


def _shadow_atom_budget(token_budget: int) -> int:
    return max(1, min(50, max(1, int(token_budget)) // 100))


def _fallback_reason_for_report(report: object, atoms: tuple[object, ...]) -> str | None:
    if getattr(report, "hard_failure_count", 0):
        return "hard_failures"
    memory_report = getattr(report, "memory_report", None)
    if memory_report is None:
        return "missing_memory_report"
    if _has_leak_findings(report):
        return "leak_findings"
    if _has_unsafe_admissions(memory_report):
        return "unsafe_admissions"
    if _has_projection_candidate(memory_report, atoms):
        return "projections"
    if _has_stale_reads(memory_report, atoms):
        return "stale_reads"
    return None


def _has_leak_findings(report: object) -> bool:
    if any(str(warning) in _SENSITIVE_FINDINGS for warning in getattr(report, "warnings", ())):
        return True
    memory_report = getattr(report, "memory_report", None)
    findings = getattr(memory_report, "findings", ()) if memory_report is not None else ()
    for finding in findings:
        if str(getattr(finding, "kind", "")) in _SENSITIVE_FINDINGS:
            return True
    payload = json.dumps(report.to_json(), sort_keys=True, default=str)
    return any(issue.kind in _SENSITIVE_FINDINGS for issue in detect_text_safety_issues(payload))


def _has_unsafe_admissions(memory_report: object) -> bool:
    pack = getattr(memory_report, "pack", None)
    if pack is None:
        return True
    for item in getattr(pack, "items", ()):
        if not getattr(item, "admitted", False):
            continue
        if getattr(item, "omission_reasons", ()):
            return True
        if _enum_value(getattr(item, "truth_state", "")) in {"rejected", "superseded"}:
            return True
        if _enum_value(getattr(item, "canon_risk", "")) in {"high", "critical"}:
            return True
        if _enum_value(getattr(item, "pii_risk", "")) in {"high", "critical"}:
            return True
    return False


def _has_projection_candidate(memory_report: object, atoms: tuple[object, ...]) -> bool:
    pack = getattr(memory_report, "pack", None)
    for item in getattr(pack, "items", ()) if pack is not None else ():
        if (
            _enum_value(getattr(item, "surface_category", "")) == "projection"
            or _enum_value(getattr(item, "memory_lane", "")) == "projection"
            or bool(getattr(item, "projection_of", ()))
        ):
            return True
    for atom in atoms:
        if (
            _enum_value(getattr(atom, "surface_category", "")) == "projection"
            or _enum_value(getattr(atom, "memory_lane", "")) == "projection"
            or bool(getattr(atom, "projection_of", ()))
        ):
            return True
    return False


def _has_stale_reads(memory_report: object, atoms: tuple[object, ...]) -> bool:
    for atom in atoms:
        if str(getattr(atom, "freshness", "")).lower() in _STALE_FRESHNESS:
            return True
        valid_until = getattr(atom, "valid_until", None)
        if _is_expired(valid_until):
            return True
    pack = getattr(memory_report, "pack", None)
    for item in getattr(pack, "items", ()) if pack is not None else ():
        warnings = tuple(str(warning).lower() for warning in getattr(item, "warnings", ()))
        if any("stale" in warning or "snapshot" in warning or "wal" in warning for warning in warnings):
            return True
    return False


def _scan_append_section(section: str) -> tuple[str | None, list[str]]:
    try:
        from dharma_swarm.injection_scanner import scan_content

        scan = scan_content(section, "memory_kernel_context_canary")
    except Exception:
        logger.debug("MemoryKernel append section scan failed", exc_info=True)
        return "scanner_findings", ["scanner_exception"]
    if not scan.is_clean:
        return "scanner_findings", [f"scanner:{finding}" for finding in scan.findings]
    issues = detect_text_safety_issues(section)
    if issues:
        return "leak_findings", [f"leak:{issue.kind}" for issue in issues]
    return None, []


def _canary_metadata(
    *,
    mode: MemoryKernelContextMode,
    surface_ids: tuple[str, ...],
    report: object | None,
    warnings: Iterable[str],
    fallback_reason: str | None,
    hard_failure_override: int | None,
) -> dict[str, object]:
    admitted_count = 0
    candidate_count = 0
    if report is not None:
        memory_report = getattr(report, "memory_report", None)
        pack = getattr(memory_report, "pack", None)
        if pack is not None:
            admitted_count = int(getattr(pack, "admitted_count", 0))
            candidate_count = int(getattr(pack, "candidate_count", 0))
    hard_failures = (
        hard_failure_override
        if hard_failure_override is not None
        else int(getattr(report, "hard_failure_count", 0) if report is not None else 0)
    )
    all_warnings = tuple(dict.fromkeys((*_report_warnings(report), *tuple(warnings))))
    return {
        "mode": mode,
        "surface_ids": surface_ids,
        "candidate_count": candidate_count,
        "admitted_count": admitted_count,
        "warnings": all_warnings,
        "hard_failures": hard_failures,
        "fallback_reason": fallback_reason,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _report_warnings(report: object | None) -> tuple[str, ...]:
    if report is None:
        return ()
    rows: list[str] = [str(warning) for warning in getattr(report, "warnings", ())]
    memory_report = getattr(report, "memory_report", None)
    if memory_report is not None:
        rows.extend(str(warning) for warning in getattr(memory_report, "warnings", ()))
        pack = getattr(memory_report, "pack", None)
        for item in getattr(pack, "items", ()) if pack is not None else ():
            rows.extend(str(warning) for warning in getattr(item, "warnings", ()))
    for metric in getattr(report, "metrics", ()):
        if str(getattr(metric, "status", "")) == "warn":
            rows.append(str(getattr(metric, "name", "warning_metric")))
    return tuple(dict.fromkeys(rows))


def _metadata_only_result(
    legacy_text: str,
    *,
    mode: MemoryKernelContextMode,
    surface_ids: tuple[str, ...],
    fallback_reason: str,
    warnings: Iterable[str],
    hard_failures: int,
) -> MemoryKernelContextCanaryResult:
    metadata = _canary_metadata(
        mode=mode,
        surface_ids=surface_ids,
        report=None,
        warnings=warnings,
        fallback_reason=fallback_reason,
        hard_failure_override=hard_failures,
    )
    return MemoryKernelContextCanaryResult(
        mode=mode,
        rendered_text=legacy_text,
        appended_section="",
        appended=False,
        report=None,
        metadata=metadata,
        fallback_reason=fallback_reason,
    )


def _append_context_section(legacy_text: str, appended_section: str) -> str:
    if not appended_section:
        return legacy_text
    if not legacy_text:
        return appended_section
    return legacy_text.rstrip() + "\n\n" + appended_section


def _resolve_surface_ids(
    surface_ids: tuple[str, ...],
    env_names: tuple[str, ...],
) -> tuple[str, ...]:
    explicit = _dedupe(surface_ids)
    if explicit:
        return explicit
    for name in env_names:
        values = _csv_env(name)
        if values:
            return values
    return ()


def _report_surface_ids(report: object) -> tuple[str, ...]:
    memory_report = getattr(report, "memory_report", None)
    pack = getattr(memory_report, "pack", None)
    surface_ids = tuple(
        str(getattr(item, "surface_id", ""))
        for item in getattr(pack, "items", ()) if pack is not None
        if str(getattr(item, "surface_id", ""))
    )
    return tuple(dict.fromkeys(surface_ids))


def _is_expired(value: object) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed <= datetime.now(timezone.utc)


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _inline(value: object, max_chars: int) -> str:
    text = safe_eval_ref(str(value).replace("\n", " "), max_chars=max_chars)
    return text.replace("`", "'")


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str) -> tuple[str, ...]:
    value = os.environ.get(name, "")
    return _dedupe(value.split(","))


def _path_env(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    return Path(value).expanduser() if value else None


def _dedupe(values: Iterable[object]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return tuple(out)
