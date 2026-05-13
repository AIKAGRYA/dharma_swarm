#!/usr/bin/env python3
"""Report MemoryKernel M2A memory-like writer inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dharma_swarm.memory_kernel.writers import (
    DiscoveredWriteStatus,
    DiscoveryTriageCategory,
    MemoryWriterSentinel,
    WriterStatus,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--details", action="store_true", help="Include per-writer observations.")
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Run the AST discovery pass for likely memory-like writes.",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help=(
            "Run the CI safety profile: registered writer checks, bounded discovery, "
            "and action-required discovery failure gates."
        ),
    )
    parser.add_argument(
        "--discovery-details",
        action="store_true",
        help="Include per-call write discovery observations.",
    )
    parser.add_argument(
        "--max-discovery-files",
        type=int,
        default=2000,
        help="Maximum Python files to scan during --discover.",
    )
    parser.add_argument(
        "--fail-on-unregistered",
        action="store_true",
        help="Return non-zero if a present writer targets an unregistered surface.",
    )
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Return non-zero if a registered writer symbol is missing.",
    )
    parser.add_argument(
        "--fail-on-unregistered-discovery",
        action="store_true",
        help="Return non-zero if --discover finds write calls outside registered writer specs.",
    )
    parser.add_argument(
        "--fail-on-action-required-discovery",
        action="store_true",
        help=(
            "Return non-zero if --discover finds untriaged memory writers or surfaces "
            "that require MemoryKernel registration."
        ),
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        help="Write a human-readable Markdown review report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.ci:
        args.discover = True
        args.fail_on_unregistered = True
        args.fail_on_missing = True
        args.fail_on_action_required_discovery = True
    sentinel = MemoryWriterSentinel(repo_root=args.repo_root)
    observations = sentinel.run()
    summary = sentinel.summarize(observations)
    payload: dict[str, object] = {"summary": summary.to_json()}
    if args.details:
        payload["writers"] = [observation.to_json() for observation in observations]
    discoveries = ()
    if args.discover:
        discoveries = sentinel.discover_write_paths(max_files=args.max_discovery_files)
        discovery_summary = sentinel.summarize_discoveries(
            discoveries,
            scanned_file_count=sentinel.count_scan_files(max_files=args.max_discovery_files),
            parse_error_count=sentinel.count_parse_errors(max_files=args.max_discovery_files),
        )
        payload["discovery_summary"] = discovery_summary.to_json()
        if args.discovery_details:
            payload["discovered_writes"] = [discovery.to_json() for discovery in discoveries]
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(
            render_markdown_report(observations, discoveries),
            encoding="utf-8",
        )
    print(json.dumps(payload, indent=2, sort_keys=True))

    if args.fail_on_unregistered and any(
        observation.status == WriterStatus.UNREGISTERED_SURFACE for observation in observations
    ):
        return 2
    if args.fail_on_missing and any(
        observation.status == WriterStatus.MISSING for observation in observations
    ):
        return 3
    if args.fail_on_unregistered_discovery and any(
        discovery.status == DiscoveredWriteStatus.UNREGISTERED for discovery in discoveries
    ):
        return 4
    if args.fail_on_action_required_discovery and any(
        discovery.triage_category
        in {
            DiscoveryTriageCategory.MEMORY_WRITER_NEEDS_SPEC,
            DiscoveryTriageCategory.SURFACE_NEEDS_REGISTRY,
        }
        for discovery in discoveries
    ):
        return 5
    return 0


def render_markdown_report(observations, discoveries) -> str:
    lines: list[str] = [
        "# Memory Writer Sentinel Report",
        "",
        "This is a read-only MemoryKernel writer inventory. It does not enforce, intercept, or redirect writes.",
        "",
        "## Registered Writers",
        "",
    ]
    lines.append(f"- Registered writers: `{len(observations)}`")
    lines.append(f"- Present: `{sum(1 for item in observations if item.present)}`")
    lines.append(
        f"- Missing: `{sum(1 for item in observations if item.status.value == 'missing')}`"
    )
    lines.append(
        "- Targeting unregistered surfaces: "
        f"`{sum(1 for item in observations if item.status.value == 'unregistered_surface')}`"
    )
    lines.append("")

    problem_rows = [
        item
        for item in observations
        if item.status.value in {"missing", "unregistered_surface", "error"}
    ]
    if problem_rows:
        lines.extend(["## Registered Writer Issues", ""])
        for item in problem_rows:
            lines.append(
                f"- `{item.spec.writer_id}`: `{item.status.value}` "
                f"at `{item.source_path}`"
            )
            if item.unregistered_surfaces:
                lines.append(f"  - surfaces: `{', '.join(item.unregistered_surfaces)}`")
        lines.append("")

    if discoveries:
        unregistered = [
            item for item in discoveries if item.status.value == "unregistered"
        ]
        registered = [item for item in discoveries if item.status.value == "registered"]
        lines.extend(["## Static Discovery", ""])
        lines.append(f"- Discovered likely memory-like writes: `{len(discoveries)}`")
        lines.append(f"- Matched registered writer specs: `{len(registered)}`")
        lines.append(f"- Discovered but unregistered: `{len(unregistered)}`")
        lines.append("")
        lines.extend(["## Discovery Triage", ""])
        for category, count in _category_counts(discoveries):
            lines.append(f"- `{category}`: `{count}`")
        lines.append("")
        lines.extend(["## Top Unregistered Sources", ""])
        for source_path, count in _top_sources(unregistered):
            lines.append(f"- `{source_path}`: `{count}`")
        lines.append("")
        lines.extend(["## First Unregistered Discoveries", ""])
        for item in unregistered[:30]:
            lines.append(
                f"- `{item.source_path}:{item.line}` `{item.symbol}` "
                f"`{item.operation}` `{item.triage_category.value}`"
            )
        lines.append("")

    lines.extend(
        [
            "## Gate Guidance",
            "",
            "- Registered-writer fail gates can run when registered issues are zero.",
            "- Action-required discovery gates can run once MEMORY_WRITER_NEEDS_SPEC and SURFACE_NEEDS_REGISTRY are zero.",
            "- Strict unregistered discovery gates should stay opt-in; generated artifacts and operational state may be intentionally unregistered.",
            "- Do not treat discovery hits as proof of semantic memory mutation; classify them first.",
            "",
        ]
    )
    return "\n".join(lines)


def _top_sources(discoveries) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for item in discoveries:
        counts[item.source_path] = counts.get(item.source_path, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]


def _category_counts(discoveries) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for item in discoveries:
        counts[item.triage_category.value] = counts.get(item.triage_category.value, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


if __name__ == "__main__":
    raise SystemExit(main())
