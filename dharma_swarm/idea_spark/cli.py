"""Operator-facing CLI for the Idea Spark ingest lifecycle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dharma_swarm.semantic_commons import SemanticCommons

from .health import ingest_health, render_lines, write_health_receipt
from .orchestrator import LifecycleRunResult, run_operator_idea_spark
from .paths import (
    candidates_path,
    idea_spark_root,
    input_receipt_path,
    lifecycle_receipt_path,
    routing_receipt_path,
)
from .retrieval import retrieve
from .see_adapter import elevate_to_graph

SOURCE_KINDS = (
    "note",
    "transcript",
    "youtube_transcript",
    "session",
    "url",
    "file",
    "world_signal",
    "go_receipt",
    "idea_shard",
)
SOURCE_RIGHTS = ("owned", "operator_supplied", "public_excerpt", "link_only", "unknown")
AUTHORITY_LEVELS = (
    "observation",
    "proposal",
    "task_candidate",
    "experiment_candidate",
    "trusted_memory",
)
REDACTION_POLICIES = ("none", "pii_redacted", "summary_only", "link_only")


def _looks_like_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _path_uri(path: Path) -> str:
    return path.expanduser().resolve().as_uri()


def _state_root(value: str | None) -> Path | None:
    return Path(value).expanduser() if value else None


def _load_commons(value: str | None) -> SemanticCommons | None:
    if not value:
        return None
    try:
        return SemanticCommons.load(Path(value).expanduser())
    except OSError as exc:
        raise ValueError(f"cannot load commons root {value}: {exc}") from exc


def _default_source_rights(source_kind: str, *, link_only: bool) -> str:
    if link_only:
        return "link_only"
    if source_kind in {"url", "youtube_transcript", "world_signal", "go_receipt"}:
        return "public_excerpt"
    return "operator_supplied"


def _resolve_ingest_input(args: argparse.Namespace) -> dict[str, str]:
    if args.file and args.text:
        raise ValueError("use either --file or --text, not both")
    if args.url and args.file:
        raise ValueError("use either --url or --file, not both")

    positional = args.input or ""
    source_kind = args.kind
    source_ref = args.source_ref or ""
    content = args.text or ""
    link_only = False

    if args.url:
        source_kind = source_kind or "url"
        source_ref = source_ref or args.url
        if not content:
            content = f"Link-only URL drop: {args.url}"
            link_only = True
    elif args.file:
        source_kind = source_kind or "file"
        path = Path(args.file).expanduser()
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"cannot read file {args.file}: {exc}") from exc
        source_ref = source_ref or _path_uri(path)
    elif args.stdin:
        source_kind = source_kind or "note"
        content = sys.stdin.read()
        source_ref = source_ref or f"operator://{source_kind}/stdin"
    elif content:
        source_kind = source_kind or "note"
        source_ref = source_ref or f"operator://{source_kind}/inline"
    elif positional:
        if _looks_like_url(positional) and not args.kind:
            source_kind = "url"
            source_ref = source_ref or positional
            if not content:
                content = f"Link-only URL drop: {positional}"
                link_only = True
        else:
            source_kind = source_kind or "note"
            content = content or positional
            source_ref = source_ref or f"operator://{source_kind}/inline"
    else:
        raise ValueError("provide --text, --file, --stdin, --url, or an inline note/URL")

    if not source_kind:
        source_kind = "note"
    if source_kind not in SOURCE_KINDS:
        raise ValueError(f"unsupported source kind: {source_kind}")
    if not content.strip():
        raise ValueError("ingest content is empty")
    if not source_ref:
        source_ref = f"operator://{source_kind}/drop"

    return {
        "source_kind": source_kind,
        "source_ref": source_ref,
        "content": content,
        "source_rights": args.source_rights
        or _default_source_rights(source_kind, link_only=link_only),
    }


def _run_summary(result: LifecycleRunResult, state_root: Path | None) -> dict[str, Any]:
    lifecycle_path = lifecycle_receipt_path(result.correlation_id, state_root)
    routing_path = routing_receipt_path(result.correlation_id, state_root)
    status = result.probe.lifecycle.status if result.probe.lifecycle else ""
    return {
        "schema_version": "operator_idea_spark_cli_result.v0",
        "correlation_id": result.correlation_id,
        "input_id": result.input_receipt.input_id,
        "candidate_id": result.candidate.candidate_id,
        "source_kind": result.input_receipt.source_kind,
        "source_rights": result.input_receipt.source_rights,
        "redaction_policy": result.input_receipt.redaction_policy,
        "status": status,
        "state_root": str(idea_spark_root(state_root)),
        "receipts": {
            "input": str(input_receipt_path(result.input_receipt.input_id, state_root)),
            "candidates": str(candidates_path(state_root)),
            "lifecycle": str(lifecycle_path),
            "routing": str(routing_path) if routing_path.exists() else "",
            "memory_write": str(result.memory.write_receipt_path),
            "memory_decision": str(result.memory.decision_path),
            "memory_canonical": str(result.memory.canonical_receipt_path),
        },
        "chetana_staged_atom_id": result.staged.atom_id,
        "chetana_staged_path": str(result.staged.path),
        "memory_write_receipt_id": result.memory.write_receipt_id,
        "memory_canonical_receipt_id": result.memory.canonical_receipt_id,
        "memory_promotion_ready": result.memory.promotion_ready,
        "semantic_route": result.route.canonical_target,
        "owner_surface": result.route.owner_surface,
        "action_lane": result.action.lane,
        "proposal_id": result.action.proposal_id,
        "task_id": result.action.task_id,
        "bet_id": result.action.bet_id,
        "implementation_receipt_id": result.implementation_receipt_id,
        "retrieval_probe_id": result.probe.retrieval_probe_id,
        "retrieval_found": result.probe.found,
        "blockers": list(result.probe.blockers),
    }


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, sort_keys=True, indent=2))


def _cmd_ingest(args: argparse.Namespace) -> int:
    resolved = _resolve_ingest_input(args)
    state_root = _state_root(args.state_root)
    result = run_operator_idea_spark(
        source_kind=resolved["source_kind"],  # type: ignore[arg-type]
        source_ref=resolved["source_ref"],
        content=resolved["content"],
        source_rights=resolved["source_rights"],  # type: ignore[arg-type]
        captured_by=args.captured_by,
        claim=args.claim or resolved["content"],
        title=args.title,
        why_now=args.why_now or "",
        domain=args.domain or "",
        authority_level=args.authority_level,
        redaction_policy=args.redaction_policy,
        commons=_load_commons(args.commons_root),
        state_root=state_root,
        created_at=args.created_at,
        grant_authority=args.grant_authority,
    )
    summary = _run_summary(result, state_root)
    if args.elevate:
        graph_path = idea_spark_root(state_root) / "elevated" / f"{result.correlation_id}.json"
        elevation = elevate_to_graph(
            result.candidate.claim,
            result.correlation_id,
            graph_path,
            authority_level=args.authority_level or "observation",
        )
        summary["elevation"] = {
            "node_id": elevation.node_id,
            "salience": elevation.salience,
            "computed_salience": elevation.computed_salience,
            "annotation_count": elevation.annotation_count,
            "body_redacted": elevation.body_redacted,
            "research_is_live": elevation.research_is_live,
            "graph_path": elevation.graph_path,
        }
    if args.json:
        _print_json(summary)
    else:
        print(f"correlation_id: {summary['correlation_id']}")
        print(f"candidate_id: {summary['candidate_id']}")
        print(f"status: {summary['status']}")
        print(f"owner_surface: {summary['owner_surface'] or '<unresolved>'}")
        print(f"action_lane: {summary['action_lane']}")
        print(f"lifecycle_receipt: {summary['receipts']['lifecycle']}")
        if args.elevate:
            e = summary["elevation"]
            print(
                f"elevated: node={e['node_id']} salience={e['salience']} "
                f"(computed {e['computed_salience']:.3f}) "
                f"annotations={e['annotation_count']} research_live={e['research_is_live']}"
            )
            print(f"elevated_graph: {e['graph_path']}")
    return 0


def _cmd_health(args: argparse.Namespace) -> int:
    state_root = _state_root(args.state_root)
    health = ingest_health(
        state_root,
        include_chetana_backlog=args.include_chetana_backlog,
    )
    if args.write_receipt:
        path = write_health_receipt(
            state_root,
            include_chetana_backlog=args.include_chetana_backlog,
        )
        health["health_receipt_path"] = str(path)
    if args.json:
        _print_json(health)
    else:
        for line in render_lines(health):
            print(line)
    return 0


def _cmd_retrieve(args: argparse.Namespace) -> int:
    state_root = _state_root(args.state_root)
    probes = retrieve(
        correlation_id=args.correlation_id,
        text=args.text,
        title=args.title,
        semantic_route=args.semantic_route,
        state_root=state_root,
    )
    payload = [probe.to_summary() for probe in probes]
    if args.json:
        _print_json(payload)
    else:
        for row in payload:
            print(
                f"{row['correlation_id']} found={row['found']} "
                f"status={row['status']} candidate={row['candidate_id']}"
            )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="operator-idea-spark",
        description="Receipt-backed Operator Idea Spark ingest front door.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="ingest one note, transcript, URL, or snippet")
    ingest.add_argument("input", nargs="?", help="inline note text or URL")
    ingest.add_argument("--text", help="inline content/excerpt to hash and route")
    ingest.add_argument("--file", help="text file, transcript, session snippet, or OCR output")
    ingest.add_argument("--stdin", action="store_true", help="read content from stdin")
    ingest.add_argument("--url", help="URL drop; link-only unless --text supplies an excerpt")
    ingest.add_argument("--kind", choices=SOURCE_KINDS)
    ingest.add_argument("--source-ref", help="stable source reference stored in the input receipt")
    ingest.add_argument("--source-rights", choices=SOURCE_RIGHTS)
    ingest.add_argument("--redaction-policy", choices=REDACTION_POLICIES)
    ingest.add_argument("--captured-by", default="operator")
    ingest.add_argument("--claim", help="candidate claim; defaults to supplied content")
    ingest.add_argument("--title")
    ingest.add_argument("--why-now")
    ingest.add_argument("--domain")
    ingest.add_argument("--authority-level", choices=AUTHORITY_LEVELS)
    ingest.add_argument("--state-root")
    ingest.add_argument("--commons-root", help="test/override Semantic Commons ontology root")
    ingest.add_argument("--created-at", help="fixed UTC timestamp for deterministic trials")
    ingest.add_argument("--grant-authority", action="store_true")
    ingest.add_argument(
        "--elevate",
        action="store_true",
        help="also run the spark through the Semantic Evolution Engine "
        "(digest->provenance-floor->research) into an isolated idea_spark graph "
        "receipt; never mutates the shared semantic canon",
    )
    ingest.add_argument("--json", action="store_true")
    ingest.set_defaults(func=_cmd_ingest)

    health = sub.add_parser("health", help="show read-only ingest health")
    health.add_argument("--state-root")
    health.add_argument("--include-chetana-backlog", action="store_true")
    health.add_argument("--write-receipt", action="store_true")
    health.add_argument("--json", action="store_true")
    health.set_defaults(func=_cmd_health)

    retrieve_cmd = sub.add_parser("retrieve", help="prove lifecycle retrieval")
    retrieve_cmd.add_argument("--correlation-id")
    retrieve_cmd.add_argument("--text")
    retrieve_cmd.add_argument("--title")
    retrieve_cmd.add_argument("--semantic-route")
    retrieve_cmd.add_argument("--state-root")
    retrieve_cmd.add_argument("--json", action="store_true")
    retrieve_cmd.set_defaults(func=_cmd_retrieve)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
