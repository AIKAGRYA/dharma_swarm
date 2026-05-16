#!/usr/bin/env python3
"""Run fast read-only operator production coherence checks."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_MEMORY_ROW_IDS = {
    "memory.census",
    "memory.adapter_coverage",
    "memory.readiness",
    "memory.writer_sentinel",
    "memory.context_shadow",
    "memory.context_canary",
    "memory.knowledgeops_intake",
    "memory.promotion_queue",
    "memory.rollout_gate",
    "memory.rollback_switch",
}


@dataclass(frozen=True)
class SmokeCheck:
    name: str
    ok: bool
    detail: str

    def to_json(self) -> dict[str, object]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def check_api_boot() -> SmokeCheck:
    try:
        from api.main import app

        routes = len(getattr(app, "routes", ()))
        return SmokeCheck("api_boot", routes > 0, f"routes={routes}")
    except Exception as exc:
        return SmokeCheck("api_boot", False, str(exc))


def load_control_surface_rows(repo_root: Path) -> list[Any]:
    from dharma_swarm.operator_core.control_surface import build_control_surface_rows

    return build_control_surface_rows(repo_root=repo_root)


def check_row_projection(rows: list[Any]) -> SmokeCheck:
    try:
        ids = {row.id for row in rows}
        missing = sorted(REQUIRED_MEMORY_ROW_IDS - ids)
        return SmokeCheck(
            "memory_row_projection",
            not missing,
            "missing=" + ",".join(missing) if missing else f"memory_rows={len(REQUIRED_MEMORY_ROW_IDS)}",
        )
    except Exception as exc:
        return SmokeCheck("memory_row_projection", False, str(exc))


def check_memory_writer_sentinel(repo_root: Path) -> SmokeCheck:
    try:
        from dharma_swarm.memory_kernel import (
            DiscoveryTriageCategory,
            MemoryWriterSentinel,
            WriterClassification,
            WriterStatus,
        )

        sentinel = MemoryWriterSentinel(repo_root=repo_root)
        observations = sentinel.run()
        discoveries = sentinel.discover_write_paths(max_files=2000)
        action_required = sum(
            1
            for item in discoveries
            if item.triage_category
            in {
                DiscoveryTriageCategory.MEMORY_WRITER_NEEDS_SPEC,
                DiscoveryTriageCategory.SURFACE_NEEDS_REGISTRY,
            }
        )
        missing = sum(
            1
            for item in observations
            if item.status == WriterStatus.MISSING
            and item.spec.classification != WriterClassification.DORMANT
        )
        unregistered = sum(
            1 for item in observations if item.status == WriterStatus.UNREGISTERED_SURFACE
        )
        ok = missing == 0 and unregistered == 0 and action_required == 0
        return SmokeCheck(
            "memory_writer_sentinel_summary",
            ok,
            (
                f"writers={len(observations)} missing={missing} "
                f"unregistered_surfaces={unregistered} action_required={action_required}"
            ),
        )
    except Exception as exc:
        return SmokeCheck("memory_writer_sentinel_summary", False, str(exc))


def check_context_shadow_report() -> SmokeCheck:
    try:
        from dharma_swarm.operator_core.control_surface_memory import (
            project_context_canary_report,
        )

        report = project_context_canary_report()
        hard_failures = int(report.get("hard_failure_count", 0) or 0)
        warnings = int(report.get("warning_count", 0) or 0)
        return SmokeCheck(
            "context_shadow_canary_report",
            hard_failures > 0,
            f"hard_failures={hard_failures} warnings={warnings}",
        )
    except Exception as exc:
        return SmokeCheck("context_shadow_canary_report", False, str(exc))


def check_readiness_contract(rows: list[Any]) -> SmokeCheck:
    try:
        by_id = {row.id: row for row in rows}
        row = by_id.get("memory.readiness")
        raw = getattr(row, "raw", {}) if row is not None else {}
        required_fields = (
            "readiness_status",
            "strict_readiness_state",
            "strict_ready",
            "accounted_surface_count",
            "accounted_surface_total",
            "required_surface_count",
            "required_accounted_surface_count",
            "warning_count",
        )
        missing_fields = [field for field in required_fields if field not in raw]
        accounted_count = _int_value(raw.get("accounted_surface_count"))
        accounted_total = _int_value(raw.get("accounted_surface_total"))
        required_count = _int_value(raw.get("required_surface_count"))
        required_accounted = _int_value(raw.get("required_accounted_surface_count"))
        warning_count = _int_value(raw.get("warning_count"))
        ok = (
            row is not None
            and raw.get("schema_version") == "memory_kernel_readiness.v1"
            and raw.get("readiness_status") == "ready"
            and raw.get("strict_readiness_state") == "strict_ready"
            and raw.get("strict_ready") is True
            and accounted_total > 0
            and accounted_count == accounted_total
            and required_count > 0
            and required_accounted == required_count
            and warning_count == 0
            and not missing_fields
        )
        detail = (
            f"status={raw.get('readiness_status', '<missing>')} "
            f"strict={raw.get('strict_readiness_state', '<missing>')} "
            f"accounted={raw.get('accounted_surface_count', '<missing>')}/"
            f"{raw.get('accounted_surface_total', '<missing>')} "
            f"required={raw.get('required_accounted_surface_count', '<missing>')}/"
            f"{raw.get('required_surface_count', '<missing>')} "
            f"warnings={raw.get('warning_count', '<missing>')}"
        )
        if missing_fields:
            detail += " missing_fields=" + ",".join(missing_fields)
        return SmokeCheck("memory_readiness_contract", ok, detail)
    except Exception as exc:
        return SmokeCheck("memory_readiness_contract", False, str(exc))


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def check_rollback_switch_presence(rows: list[Any]) -> SmokeCheck:
    try:
        by_id = {row.id: row for row in rows}
        rollback = by_id.get("memory.rollback_switch")
        gate = by_id.get("memory.rollout_gate")
        ok = (
            rollback is not None
            and gate is not None
            and bool(rollback.raw.get("switch_present"))
            and tuple(gate.raw.get("allowed_states", ())) == ("off", "shadow", "preview", "canary", "live")
        )
        detail = (
            f"rollback={getattr(rollback, 'observed_state', '<missing>')} "
            f"rollout={getattr(gate, 'observed_state', '<missing>')}"
        )
        return SmokeCheck("rollback_switch_presence", ok, detail)
    except Exception as exc:
        return SmokeCheck("rollback_switch_presence", False, str(exc))


def check_burn_in_safety(rows: list[Any]) -> SmokeCheck:
    try:
        by_id = {row.id: row for row in rows}
        gate = by_id.get("memory.rollout_gate")
        raw = getattr(gate, "raw", {}) if gate is not None else {}
        blockers = tuple(raw.get("burn_in_blockers", ()))
        safe = bool(raw.get("burn_in_safe"))
        ok = gate is not None and safe and "burn_in_safety_state" in raw
        detail = (
            f"rollout={getattr(gate, 'observed_state', '<missing>')} "
            f"safety={raw.get('burn_in_safety_state', '<missing>')} "
            f"blockers={','.join(str(item) for item in blockers) or '<none>'}"
        )
        return SmokeCheck("memory_burn_in_safety", ok, detail)
    except Exception as exc:
        return SmokeCheck("memory_burn_in_safety", False, str(exc))


def run_smoke(repo_root: Path) -> tuple[SmokeCheck, ...]:
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    checks: list[SmokeCheck] = [check_api_boot()]
    try:
        rows = load_control_surface_rows(repo_root)
    except Exception as exc:
        rows = []
        checks.append(SmokeCheck("control_surface_projection", False, str(exc)))
    else:
        checks.append(
            SmokeCheck(
                "control_surface_projection",
                bool(rows),
                f"rows={len(rows)}",
            )
        )

    checks.extend(
        [
            check_row_projection(rows),
            check_memory_writer_sentinel(repo_root),
            check_context_shadow_report(),
            check_readiness_contract(rows),
            check_rollback_switch_presence(rows),
            check_burn_in_safety(rows),
        ]
    )
    return tuple(checks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    checks = run_smoke(args.repo_root.resolve())
    payload = {
        "ok": all(check.ok for check in checks),
        "checks": [check.to_json() for check in checks],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
