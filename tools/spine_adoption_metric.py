from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


VALID_STATUSES = ("joined", "adapter-ready", "missing", "quarantine", "legacy")
DEFAULT_OUTPUT = Path("reports/governance/spine_adoption_metric.json")
DOC_ANCHORS = (
    "docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md",
    "reports/governance/execution_identity_lineage_blast_radius_audit.md",
    "dharma_swarm/a2a/README.md",
)


@dataclass(frozen=True)
class PatternSpec:
    key: str
    regex: str
    description: str


@dataclass(frozen=True)
class SurfaceRule:
    surface_id: str
    label: str
    category: str
    path_patterns: tuple[str, ...]
    joined: tuple[PatternSpec, ...] = ()
    adapter_ready: tuple[PatternSpec, ...] = ()
    quarantine: tuple[PatternSpec, ...] = ()
    legacy: tuple[PatternSpec, ...] = ()
    priority: int = 50


def p(key: str, regex: str, description: str) -> PatternSpec:
    return PatternSpec(key=key, regex=regex, description=description)


SURFACE_RULES: tuple[SurfaceRule, ...] = (
    SurfaceRule(
        surface_id="identity_contract",
        label="Canonical ExecutionIdentity contract",
        category="identity",
        path_patterns=("dharma_swarm/spine/identity.py",),
        joined=(
            p("execution_identity_class", r"\bclass ExecutionIdentity\b", "ExecutionIdentity type exists"),
            p("metadata_hydration", r"\bdef from_metadata\b", "identity can be recovered from metadata"),
            p("dispatch_requirement", r"\bdef require_for_dispatch\b", "dispatch can require mandatory identity fields"),
        ),
        adapter_ready=(p("identity_name_seen", r"ExecutionIdentity", "identity symbol is present"),),
        priority=1,
    ),
    SurfaceRule(
        surface_id="runtime_state_ledger",
        label="RuntimeStateStore durable ledger",
        category="ledger",
        path_patterns=("dharma_swarm/runtime_state.py",),
        joined=(
            p("store_class", r"\bclass RuntimeStateStore\b", "RuntimeStateStore type exists"),
            p("identity_table", r"execution_identities", "execution identity table is declared"),
            p("receipt_table", r"runtime_receipts", "runtime receipt table is declared"),
            p("idempotency_table", r"idempotency_records", "idempotency table is declared"),
            p("run_ledger_query", r"\bdef get_run_ledger\b", "run ledger query exists"),
        ),
        adapter_ready=(p("runtime_state_name_seen", r"RuntimeStateStore", "runtime store symbol is present"),),
        legacy=(p("legacy_bypass_flag", r"legacy_no_identity_allowed", "legacy identity bypass flag is present"),),
        priority=1,
    ),
    SurfaceRule(
        surface_id="runtime_lifecycle_adapter",
        label="Runtime lifecycle adapter",
        category="dispatch",
        path_patterns=("dharma_swarm/runtime_lifecycle.py",),
        joined=(
            p("ensure_identity", r"\bdef ensure_execution_identity\b", "lifecycle can create/require identity"),
            p("task_claim_receipt", r"\basync def record_task_claim\b", "task claim lifecycle path exists"),
            p("delegation_receipt", r"\basync def record_delegation_run\b", "delegation run lifecycle path exists"),
            p("artifact_receipt", r"\basync def record_artifact\b", "artifact lifecycle path exists"),
            p("runtime_receipt", r"RuntimeReceipt", "runtime receipts are emitted"),
        ),
        adapter_ready=(p("identity_import", r"ExecutionIdentity", "identity imported"),),
        priority=2,
    ),
    SurfaceRule(
        surface_id="task_board_ingress",
        label="TaskBoard local ingress",
        category="ingress",
        path_patterns=("dharma_swarm/task_board.py",),
        joined=(
            p("identity_import", r"ExecutionIdentity", "identity imported"),
            p("require_identity", r"require_identity", "required identity option exists"),
            p("runtime_store", r"RuntimeStateStore", "runtime store accepted"),
            p("identity_receipt", r"record_receipt_for_identity", "task receipts are written to the ledger"),
        ),
        adapter_ready=(p("task_create", r"\basync def create\b", "task create path exists"),),
        priority=2,
    ),
    SurfaceRule(
        surface_id="orchestrator_dispatch",
        label="Orchestrator dispatch path",
        category="dispatch",
        path_patterns=("dharma_swarm/orchestrator.py",),
        joined=(
            p("ensure_identity", r"ensure_execution_identity", "dispatch attaches identity"),
            p("claim_receipt", r"record_task_claim", "dispatch records task claims"),
            p("delegation_receipt", r"record_delegation_run", "dispatch records delegation runs"),
        ),
        adapter_ready=(p("runtime_lifecycle", r"_runtime_lifecycle", "orchestrator has lifecycle adapter seam"),),
        priority=3,
    ),
    SurfaceRule(
        surface_id="message_bus_transport",
        label="MessageBus internal event transport",
        category="event",
        path_patterns=("dharma_swarm/message_bus.py",),
        joined=(
            p("identity_import", r"ExecutionIdentity", "identity imported"),
            p("require_identity", r"require_identity", "required identity option exists"),
            p("begin_idempotent", r"try_begin_idempotent_side_effect", "idempotency is checked before send/emit side effects"),
            p("complete_idempotent", r"complete_idempotent_side_effect", "idempotency completion is recorded"),
            p("message_consumed_receipt", r"message_consumed", "message consumption receipt exists"),
        ),
        adapter_ready=(p("events_table", r"\bCREATE TABLE IF NOT EXISTS events\b", "event table exists"),),
        priority=3,
    ),
    SurfaceRule(
        surface_id="a2a_server_ingress",
        label="A2A task ingress",
        category="external-agent",
        path_patterns=("dharma_swarm/a2a/a2a_server.py",),
        joined=(
            p("identity_import", r"ExecutionIdentity", "identity imported"),
            p("runtime_store", r"RuntimeStateStore", "runtime store accepted"),
            p("a2a_external_id", r"external_a2a_task_id", "external A2A task ID maps into identity"),
            p("begin_idempotent", r"try_begin_idempotent_side_effect_sync", "A2A handler is idempotency-gated"),
            p("a2a_receipt", r"receipt_type=\"a2a_task\"", "A2A task receipt is recorded"),
        ),
        adapter_ready=(p("a2a_task_model", r"\bclass A2ATask\b", "A2A task model exists"),),
        legacy=(
            p("memory_task_store", r"self\._tasks: dict", "A2A still keeps a process-local task map"),
            p("jsonl_task_log", r"task_log\.jsonl", "A2A still writes a JSONL projection"),
        ),
        priority=4,
    ),
    SurfaceRule(
        surface_id="artifact_store",
        label="Runtime artifact store",
        category="artifact",
        path_patterns=("dharma_swarm/artifact_store.py",),
        joined=(
            p("identity_import", r"ExecutionIdentity", "identity imported"),
            p("require_identity", r"require_identity", "required identity option exists"),
            p("artifact_intent", r"_record_artifact_intent_sync", "artifact intent receipt is recorded"),
            p("artifact_complete", r"_record_artifact_complete_sync", "artifact completion receipt is recorded"),
            p("store_artifact", r"record_artifact", "artifact row is written to RuntimeStateStore"),
        ),
        adapter_ready=(p("artifact_store_class", r"\bclass RuntimeArtifactStore\b", "artifact store exists"),),
        priority=4,
    ),
    SurfaceRule(
        surface_id="tool_registry_dispatch",
        label="ToolRegistry side-effect dispatch",
        category="tool",
        path_patterns=("dharma_swarm/tool_registry.py",),
        joined=(
            p("identity_import", r"ExecutionIdentity", "identity imported"),
            p("require_identity", r"require_identity", "required identity option exists"),
            p("begin_idempotent", r"try_begin_idempotent_side_effect", "tool side effects are idempotency-gated"),
            p("complete_idempotent", r"complete_idempotent_side_effect_sync", "tool idempotency completion is recorded"),
        ),
        adapter_ready=(
            p("identity_import", r"ExecutionIdentity", "identity imported"),
            p("intent_receipt", r"record_side_effect_intent_sync", "tool intent receipt is recorded"),
            p("complete_receipt", r"(record_side_effect_complete_sync|complete_idempotent_side_effect_sync)", "tool completion receipt is recorded"),
        ),
        priority=5,
    ),
    SurfaceRule(
        surface_id="ontology_action_tollbooth",
        label="Ontology typed action tollbooth",
        category="ontology",
        path_patterns=("dharma_swarm/ontology.py",),
        joined=(
            p("identity_import", r"ExecutionIdentity", "ontology actions receive execution identity"),
            p("runtime_store", r"RuntimeStateStore", "ontology actions write to runtime ledger"),
            p("ontology_receipt", r"record_ontology_action_receipt", "ontology action receipts are recorded"),
            p("modifies_enforced", r"action_def\.modifies", "ActionDef.modifies is read at execution time"),
            p("approval_enforced", r"action_def\.requires_approval", "requires_approval is read at execution time"),
        ),
        adapter_ready=(
            p("action_def", r"\bclass ActionDef\b", "ActionDef declares typed actions"),
            p("execute_action", r"\bdef execute_action\b", "typed action execution chokepoint exists"),
            p("modifies_declared", r"modifies:", "modifies contract is declared"),
            p("approval_declared", r"requires_approval", "approval contract is declared"),
        ),
        priority=5,
    ),
    SurfaceRule(
        surface_id="self_modification_loop",
        label="Self-modification propose/gate/apply/verify loop",
        category="self-modification",
        path_patterns=(
            "dharma_swarm/evolution.py",
            "dharma_swarm/self_improve.py",
            "dharma_swarm/diff_applier.py",
        ),
        joined=(
            p("identity_import", r"ExecutionIdentity", "self-modification receives execution identity"),
            p("runtime_store", r"RuntimeStateStore", "self-modification writes to runtime ledger"),
            p("self_mod_receipt", r"record_self_mod_receipt", "self-modification receipts are recorded"),
            p("begin_idempotent", r"try_begin_idempotent_side_effect", "apply path is idempotency-gated"),
        ),
        adapter_ready=(
            p("proposal_model", r"\bclass Proposal\b", "proposal model exists"),
            p("gate_check", r"\bgate_check\b", "gate phase exists"),
            p("apply_and_test", r"apply_diff_and_test|apply_and_test", "apply/test phase exists"),
            p("rollback", r"\brollback\b", "rollback path exists"),
        ),
        priority=6,
    ),
    SurfaceRule(
        surface_id="workflow_checkpoint_replay",
        label="Workflow/checkpoint/replay path",
        category="checkpoint-replay",
        path_patterns=(
            "dharma_swarm/workflow.py",
            "dharma_swarm/checkpoint.py",
            "dharma_swarm/graph/checkpoint.py",
            "dharma_swarm/canonical_replay.py",
        ),
        joined=(
            p("identity_import", r"ExecutionIdentity", "workflow/checkpoint path receives execution identity"),
            p("runtime_store", r"RuntimeStateStore", "workflow/checkpoint path writes to runtime ledger"),
            p("runtime_receipt", r"record_runtime_receipt|get_run_ledger", "workflow/checkpoint path is ledger-reconstructable"),
        ),
        adapter_ready=(
            p("workflow_id", r"workflow_id", "workflow identity exists"),
            p("checkpoint", r"checkpoint", "checkpointing exists"),
            p("replay", r"replay", "replay harness exists"),
        ),
        legacy=(
            p("filesystem_checkpoint", r"checkpoint_dir|state\.json|CheckpointStore", "filesystem checkpoint state exists"),
            p("event_log_replay", r"EventLog", "replay uses a separate event log"),
        ),
        priority=6,
    ),
    SurfaceRule(
        surface_id="mcp_tool_access",
        label="MCP/tool access boundary",
        category="tool",
        path_patterns=("dharma_swarm/mcp_server.py", "dharma_swarm/dharma_context_mcp.py"),
        joined=(
            p("identity_import", r"ExecutionIdentity", "MCP tools receive execution identity"),
            p("runtime_store", r"RuntimeStateStore", "MCP tools write to runtime ledger"),
            p("side_effect_receipt", r"record_side_effect", "MCP side effects emit receipts"),
        ),
        adapter_ready=(p("mcp_surface", r"MCP|mcp|tool", "MCP/tool surface exists"),),
        priority=7,
    ),
    SurfaceRule(
        surface_id="nats_jetstream_transport",
        label="NATS/JetStream event transport",
        category="event",
        path_patterns=("dharma_swarm/nats*.py", "dharma_swarm/**/nats*.py"),
        joined=(
            p("nats_client", r"\bnats\b|JetStream", "NATS/JetStream client code exists"),
            p("identity_import", r"ExecutionIdentity", "NATS events carry execution identity"),
            p("begin_idempotent", r"try_begin_idempotent_side_effect", "NATS receiver is idempotency-gated"),
            p("ack_contract", r"\back\b|\bnack\b", "ack/nack contract is visible"),
        ),
        adapter_ready=(p("nats_name_seen", r"NATS|JetStream|nats", "NATS terms are present"),),
        priority=8,
    ),
    SurfaceRule(
        surface_id="opportunity_refill_research_backend",
        label="Opportunity refill research backend",
        category="quarantine",
        path_patterns=("dharma_swarm/opportunity_refill.py",),
        joined=(
            p("identity_import", r"ExecutionIdentity", "opportunity refill carries execution identity"),
            p("runtime_store", r"RuntimeStateStore", "opportunity refill writes to runtime ledger"),
        ),
        adapter_ready=(p("stage_results", r"StageResult", "stage-result surface exists"),),
        quarantine=(
            p("quarantine_marker", r"QUARANTINE_MARKER|quarantined", "surface has explicit quarantine mode"),
            p("backend_quarantine", r"DHARMA_RESEARCH_BACKEND=quarantine", "backend can be forced into quarantine"),
        ),
        priority=9,
    ),
    SurfaceRule(
        surface_id="legacy_no_identity_escape_hatch",
        label="Legacy no-identity escape hatch",
        category="legacy",
        path_patterns=("dharma_swarm/runtime_state.py", "tests/test_runtime_state_invariants.py"),
        joined=(),
        adapter_ready=(),
        legacy=(
            p("legacy_flag", r"legacy_no_identity_allowed", "legacy bypass must stay explicit"),
            p("legacy_tests", r"fail_closed_without_identity_unless_flagged", "legacy bypass has invariant coverage"),
        ),
        priority=10,
    ),
)


def repo_root_from(path: Path | None = None) -> Path:
    root = path or Path.cwd()
    return root.resolve()


def git_tracked_files(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files"],
        check=True,
        text=True,
        capture_output=True,
    )
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


def git_head(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def git_status_porcelain(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=all"],
        check=True,
        text=True,
        capture_output=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def load_tracked_sources(repo_root: Path, tracked_files: Iterable[str]) -> dict[str, list[str]]:
    sources: dict[str, list[str]] = {}
    for rel_path in tracked_files:
        path = repo_root / rel_path
        if path.suffix not in {".py", ".json", ".yaml", ".yml", ".toml", ".md"}:
            continue
        try:
            sources[rel_path] = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
    return sources


def _matches_path(rel_path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(rel_path, pattern) for pattern in patterns)


def _scan_pattern(pattern: PatternSpec, source_map: dict[str, list[str]], paths: list[str]) -> dict[str, Any]:
    compiled = re.compile(pattern.regex)
    hits: list[dict[str, Any]] = []
    for rel_path in paths:
        for line_number, line in enumerate(source_map.get(rel_path, []), start=1):
            if compiled.search(line):
                hits.append(
                    {
                        "path": rel_path,
                        "line": line_number,
                        "text": line.strip()[:220],
                    }
                )
                break
    return {
        "key": pattern.key,
        "description": pattern.description,
        "regex": pattern.regex,
        "matched": bool(hits),
        "hits": hits,
    }


def _scan_patterns(
    patterns: tuple[PatternSpec, ...],
    source_map: dict[str, list[str]],
    paths: list[str],
) -> list[dict[str, Any]]:
    return [_scan_pattern(pattern, source_map, paths) for pattern in patterns]


def _all_matched(results: list[dict[str, Any]]) -> bool:
    return bool(results) and all(bool(result["matched"]) for result in results)


def _any_matched(results: list[dict[str, Any]]) -> bool:
    return any(bool(result["matched"]) for result in results)


def classify_surface(rule: SurfaceRule, source_map: dict[str, list[str]]) -> dict[str, Any]:
    paths = sorted(rel_path for rel_path in source_map if _matches_path(rel_path, rule.path_patterns))
    joined = _scan_patterns(rule.joined, source_map, paths)
    adapter_ready = _scan_patterns(rule.adapter_ready, source_map, paths)
    quarantine = _scan_patterns(rule.quarantine, source_map, paths)
    legacy = _scan_patterns(rule.legacy, source_map, paths)

    if not paths:
        status = "missing"
    elif _all_matched(joined):
        status = "joined"
    elif _any_matched(quarantine):
        status = "quarantine"
    elif _any_matched(legacy):
        status = "legacy"
    elif _all_matched(adapter_ready):
        status = "adapter-ready"
    else:
        status = "missing"

    missing_joined = [
        {
            "key": result["key"],
            "description": result["description"],
            "regex": result["regex"],
        }
        for result in joined
        if not result["matched"]
    ]
    return {
        "id": rule.surface_id,
        "label": rule.label,
        "category": rule.category,
        "status": status,
        "priority": rule.priority,
        "path_patterns": list(rule.path_patterns),
        "files": paths,
        "joined_evidence": joined,
        "adapter_ready_evidence": adapter_ready,
        "quarantine_evidence": quarantine,
        "legacy_evidence": legacy,
        "missing_joined_patterns": missing_joined,
    }


def summarize_surfaces(surfaces: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {status: 0 for status in VALID_STATUSES}
    for surface in surfaces:
        counts[surface["status"]] += 1
    total = len(surfaces)
    joined = counts["joined"]
    adapter_ready = counts["adapter-ready"]
    joined_or_adapter_ready = joined + adapter_ready
    return {
        "total_surfaces": total,
        "status_counts": counts,
        "joined_count": joined,
        "adapter_ready_count": adapter_ready,
        "joined_or_adapter_ready_count": joined_or_adapter_ready,
        "joined_percent": round((joined / total) * 100, 1) if total else 0.0,
        "joined_or_adapter_ready_percent": round((joined_or_adapter_ready / total) * 100, 1) if total else 0.0,
        "adoption_pct": round((joined_or_adapter_ready / total) * 100, 1) if total else 0.0,
        "missing_count": counts["missing"],
        "quarantine_count": counts["quarantine"],
        "legacy_count": counts["legacy"],
        "non_joined_surface_ids": [surface["id"] for surface in surfaces if surface["status"] != "joined"],
    }


def top_saturation_targets(surfaces: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    status_rank = {
        "missing": 0,
        "adapter-ready": 1,
        "legacy": 2,
        "quarantine": 3,
        "joined": 9,
    }
    targets = sorted(
        (surface for surface in surfaces if surface["status"] != "joined"),
        key=lambda surface: (status_rank[surface["status"]], surface["priority"], surface["id"]),
    )
    return [
        {
            "id": surface["id"],
            "label": surface["label"],
            "category": surface["category"],
            "status": surface["status"],
            "missing_joined_patterns": surface["missing_joined_patterns"],
            "files": surface["files"],
        }
        for surface in targets[:limit]
    ]


def generate_report(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root_from(repo_root)
    tracked_files = git_tracked_files(root)
    status_entries = git_status_porcelain(root)
    source_map = load_tracked_sources(root, tracked_files)
    surfaces = [classify_surface(rule, source_map) for rule in SURFACE_RULES]
    summary = summarize_surfaces(surfaces)
    missing_doc_anchors = [path for path in DOC_ANCHORS if path not in tracked_files]
    return {
        "metric": "spine_adoption_metric",
        "audit_sha": git_head(root),
        "source_status": "clean" if not status_entries else "dirty",
        "source_status_entries": status_entries,
        "tracked_file_count": len(tracked_files),
        "classification_vocabulary": list(VALID_STATUSES),
        "classification_rule": (
            "joined requires all joined evidence patterns; adapter-ready requires all adapter evidence patterns "
            "when joined is incomplete; quarantine and legacy require explicit source markers; missing means "
            "no tracked surface or insufficient evidence."
        ),
        "doc_anchor_status": "ok" if not missing_doc_anchors else "missing",
        "missing_doc_anchors": missing_doc_anchors,
        "summary": summary,
        "top_saturation_targets": top_saturation_targets(surfaces),
        "surfaces": surfaces,
    }


def write_report(report: dict[str, Any], output: Path, repo_root: Path) -> None:
    path = output if output.is_absolute() else repo_root / output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure Runtime Truth Spine adoption from tracked source files.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"Write the report JSON to this path. Omit for read-only checks. Default report path: {DEFAULT_OUTPUT}",
    )
    parser.add_argument("--print", action="store_true", dest="print_json", help="Print the report JSON to stdout.")
    parser.add_argument("--require-clean-source", action="store_true", help="Exit before writing when git status is dirty.")
    parser.add_argument(
        "--fail-below-adoption",
        type=float,
        default=None,
        help="Exit non-zero when joined-or-adapter-ready adoption is below this percentage.",
    )
    parser.add_argument("--fail-on-doc-drift", action="store_true", help="Exit non-zero when tracked doc anchors are missing.")
    parser.add_argument(
        "--fail-on",
        choices=VALID_STATUSES,
        action="append",
        default=[],
        help="Exit non-zero if any surface has this status. May be provided more than once.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = repo_root_from(args.repo_root)
    if args.require_clean_source:
        status_entries = git_status_porcelain(repo_root)
        if status_entries:
            print("spine_adoption_metric: source tree is not clean", file=sys.stderr)
            for entry in status_entries:
                print(entry, file=sys.stderr)
            return 1
    report = generate_report(repo_root)
    if args.output is not None:
        write_report(report, args.output, repo_root)
    if args.print_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    blocked = sorted(set(args.fail_on) & set(report["summary"]["status_counts"]))
    for status in blocked:
        if report["summary"]["status_counts"][status] > 0:
            return 1
    if args.fail_below_adoption is not None and report["summary"]["adoption_pct"] < args.fail_below_adoption:
        return 1
    if args.fail_on_doc_drift and report["doc_anchor_status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
