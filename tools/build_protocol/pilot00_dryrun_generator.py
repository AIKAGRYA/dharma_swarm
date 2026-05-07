"""Pilot-00 dry-run generator for the Sovereign Build Packet Protocol.

This module is intentionally shape-only: it emits JSON and markdown artifacts
from a small markdown spec without spawning agents, creating worktrees, editing
source, enqueuing bridge tasks, or writing SQLite state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


DEFAULT_FORBIDDEN_FILES: tuple[str, ...] = (
    "dharma_swarm/orchestrate_live.py",
    "dharma_swarm/swarm.py",
    "dharma_swarm/frontier_council.py",
    "dharma_swarm/agent_runner.py",
    "dharma_swarm/guardian_crew.py",
    "dharma_swarm/insight_brief.py",
    "api/**",
    "dashboard/**",
)

DEFAULT_FORBIDDEN_DOMAINS: tuple[str, ...] = (
    "Operator Brief",
    "Daily Insight",
    "ontology refactor",
    "memory consolidation",
    "dashboard",
    "API",
    "provider or routing migration",
    "broad cleanup",
)

DEFAULT_GATES: tuple[str, ...] = ("telos", "scoped_tests", "scope_check")
DEFAULT_CONSTRAINTS: tuple[str, ...] = (
    "no_merge",
    "no_push",
    "no_shell_exec",
    "scope_locked",
)
DEFAULT_OUTPUTS: tuple[str, ...] = ("diff", "test_output", "checkpoint_ref")
UNKNOWN_MARKERS: tuple[str, ...] = ("i don't know", "todo", "tbd")


@dataclass(frozen=True)
class PilotSpec:
    title: str
    telos: str
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    proof_command: str
    reviewer: str
    hot_files: tuple[str, ...] = ()
    max_diff_lines: int = 50
    max_iterations: int = 2


@dataclass(frozen=True)
class DryRunResult:
    run_id: str
    root: Path
    build_packet_path: Path
    work_packet_paths: tuple[Path, ...]
    dispatch_plan_path: Path


def parse_spec(path: Path) -> PilotSpec:
    text = path.read_text(encoding="utf-8")
    title = _extract_title(text)
    telos = _extract_inline_field(text, "Telos")
    allowed_paths = tuple(_extract_list_block(text, "Allowed paths"))
    forbidden_paths = tuple(_extract_list_block(text, "Forbidden paths"))
    hot_files = tuple(_extract_list_block(text, "Hot files", required=False))
    proof_command = _extract_inline_or_block(text, "Proof command")
    reviewer = _extract_inline_or_block(text, "Reviewer")

    missing: list[str] = []
    if not title:
        missing.append("title")
    if not telos:
        missing.append("Telos")
    if not allowed_paths:
        missing.append("Allowed paths")
    if not proof_command:
        missing.append("Proof command")
    if not reviewer:
        missing.append("Reviewer")
    if missing:
        raise ValueError(f"missing required spec field(s): {', '.join(missing)}")

    unknown_text = "\n".join((telos, proof_command, reviewer, *allowed_paths))
    if _contains_unknown(unknown_text):
        raise ValueError("spec contains an unknown/TODO/TBD pre-flight answer")

    combined_forbidden = tuple(dict.fromkeys((*forbidden_paths, *DEFAULT_FORBIDDEN_FILES)))
    return PilotSpec(
        title=_slugify(title),
        telos=telos,
        allowed_paths=allowed_paths,
        forbidden_paths=combined_forbidden,
        proof_command=proof_command,
        reviewer=reviewer,
        hot_files=hot_files,
    )


def run_dryrun(
    spec_path: Path,
    *,
    output_base: Path | None = None,
    run_id: str | None = None,
    now: datetime | None = None,
) -> DryRunResult:
    spec_path = spec_path.expanduser().resolve()
    spec = parse_spec(spec_path)
    timestamp = now or datetime.now(timezone.utc)
    resolved_run_id = run_id or f"pilot-00-{timestamp:%Y%m%d}-{spec.title}"
    base = output_base or Path.home() / ".dharma" / "build_protocol" / "dryruns"
    root = base.expanduser() / resolved_run_id
    work_packets_dir = root / "work_packets"
    work_packets_dir.mkdir(parents=True, exist_ok=True)

    build_packet = _build_packet(spec, spec_path, timestamp)
    work_packet = _work_packet(spec)

    build_packet_path = root / "build_packet.json"
    work_packet_path = work_packets_dir / "wp_001.json"
    _write_json(build_packet_path, build_packet)
    _write_json(work_packet_path, work_packet)
    (root / "dispatch_plan.md").write_text(_dispatch_plan(spec, spec_path, root), encoding="utf-8")
    (root / "proof_command.txt").write_text(f"{spec.proof_command}\n", encoding="utf-8")
    (root / "gates_required.txt").write_text("\n".join(DEFAULT_GATES) + "\n", encoding="utf-8")
    (root / "pre_flight_answers.md").write_text(_preflight_answers(spec), encoding="utf-8")
    (root / "rejected_paths.txt").write_text(
        "\n".join((*spec.forbidden_paths, *DEFAULT_FORBIDDEN_DOMAINS)) + "\n",
        encoding="utf-8",
    )
    shutil.copyfile(spec_path, root / "source_spec_copy.md")
    _write_json(root / "validation_report.json", _validation_report(root))

    return DryRunResult(
        run_id=resolved_run_id,
        root=root,
        build_packet_path=build_packet_path,
        work_packet_paths=(work_packet_path,),
        dispatch_plan_path=root / "dispatch_plan.md",
    )


def _build_packet(spec: PilotSpec, spec_path: Path, now: datetime) -> dict[str, object]:
    return {
        "title": spec.title,
        "description": spec.telos,
        "status": "pending",
        "created_by": "pilot-00",
        "metadata": {
            "kind": "build_packet",
            "protocol_version": "v0",
            "spec_path": str(spec_path),
            "telos_statement": spec.telos,
            "hot_files": list(spec.hot_files),
            "forbidden_files": list(spec.forbidden_paths),
            "forbidden_domains": list(DEFAULT_FORBIDDEN_DOMAINS),
            "gates_required": list(DEFAULT_GATES),
            "proof_command": spec.proof_command,
            "child_task_ids": ["wp_001"],
            "human_approver": "dhyana",
            "approval_signature": _approval_signature(spec_path, spec),
            "max_iterations": spec.max_iterations,
            "created_at": now.astimezone(timezone.utc).isoformat(),
        },
    }


def _work_packet(spec: PilotSpec) -> dict[str, object]:
    return {
        "id": "wp_001",
        "sender": "pilot-00",
        "task": spec.telos,
        "scope": list(spec.allowed_paths),
        "output": list(DEFAULT_OUTPUTS),
        "constraints": list(DEFAULT_CONSTRAINTS),
        "payload": {
            "kind": "work_packet",
            "protocol_version": "v0",
            "parent_build_packet_id": spec.title,
            "lead_agent": "pilot-00",
            "builder_agent": "unassigned",
            "allowed_paths": list(spec.allowed_paths),
            "forbidden_paths": list(spec.forbidden_paths),
            "worktree_path": "",
            "scoped_tests": [spec.proof_command],
            "max_diff_lines": spec.max_diff_lines,
            "checkpoint_ids": [],
        },
        "status": "queued",
        "metadata": {
            "dry_run": True,
        },
    }


def _dispatch_plan(spec: PilotSpec, spec_path: Path, root: Path) -> str:
    allowed = _bullet(spec.allowed_paths)
    forbidden = _bullet(spec.forbidden_paths)
    gates = _bullet(DEFAULT_GATES)
    return f"""# Pilot-00 Dispatch Plan

Source spec path: `{root / "source_spec_copy.md"}`

## Telos

{spec.telos}

## Allowed Paths

{allowed}

## Forbidden Paths

{forbidden}

## Hot-File Status

{_hot_file_status(spec)}

## Proposed WorkPackets

### wp_001

- Builder: unassigned
- Reviewer: {spec.reviewer}
- Scope: {', '.join(f'`{p}`' for p in spec.allowed_paths)}
- Intended change: {spec.telos}
- Max diff: {spec.max_diff_lines} lines
- Constraints: {', '.join(DEFAULT_CONSTRAINTS)}

## Gates Required

{gates}

## Proof Command

```bash
{spec.proof_command}
```

## Why This Plan Is Safe

- It targets {len(spec.allowed_paths)} bounded editable path(s).
- It has a deterministic proof command.
- It does not touch Operator Brief, Daily Insight, ontology, memory consolidation, dashboard, API, providers, routing, AgentRunner, Guardian, or runtime orchestration.
- Pilot-00 creates no worktree, spawns no agent, writes no SQLite state, and edits no source.

## Reasons This Plan Would Be Rejected

- Any editable scope outside the allowed path list.
- Any missing or non-deterministic proof command.
- Any attempt to touch forbidden domains or hot files.
- Any pre-flight answer that is unknown, broad, or unbounded.
- Any generated artifact outside `{root}`.
"""


def _preflight_answers(spec: PilotSpec) -> str:
    hot_files = _bullet(spec.hot_files or ("None for this pilot.",), indent="   - ")
    forbidden = _bullet(spec.forbidden_paths, indent="   - ")
    allowed = ", ".join(f"`{p}`" for p in spec.allowed_paths)
    return f"""# Pilot-00 Pre-Flight Answers

1. What files are hot?
{hot_files}

2. What files are forbidden?
{forbidden}

3. What is the smallest proof of success?
   - `{spec.proof_command}`

4. What can a builder edit?
   - {allowed} only.

5. What happens if tests fail?
   - The WorkPacket stays unapproved and requires one scoped FixupPacket or human rejection. Pilot-00 does not run the fixup.

6. Who reviews before merge?
   - `{spec.reviewer}`; human merge approval remains with Dhyana.
"""


def _validation_report(root: Path) -> dict[str, object]:
    return {
        "dry_run": True,
        "run_id": root.name,
        "root": str(root),
        "required_outputs": [
            "build_packet.json",
            "dispatch_plan.md",
            "gates_required.txt",
            "pre_flight_answers.md",
            "proof_command.txt",
            "rejected_paths.txt",
            "source_spec_copy.md",
            "work_packets",
        ],
        "work_packets": ["wp_001.json"],
        "source_edits": False,
        "sqlite_writes": False,
        "agents_spawned": False,
        "worktrees_created": False,
    }


def _extract_title(text: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def _extract_inline_field(text: str, label: str) -> str:
    match = re.search(rf"^{re.escape(label)}:\s*(.+?)\s*$", text, flags=re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _extract_inline_or_block(text: str, label: str) -> str:
    inline = _extract_inline_field(text, label)
    if inline:
        return inline
    block = _extract_block_lines(text, label)
    return block[0].strip() if block else ""


def _extract_list_block(text: str, label: str, *, required: bool = True) -> list[str]:
    lines = _extract_block_lines(text, label)
    values = [line[2:].strip() for line in lines if line.startswith("- ")]
    if required and not values:
        return []
    return [value for value in values if value]


def _extract_block_lines(text: str, label: str) -> list[str]:
    lines = text.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        if re.match(rf"^{re.escape(label)}:\s*$", line, flags=re.IGNORECASE):
            start = index + 1
            break
    if start is None:
        return []

    block: list[str] = []
    for line in lines[start:]:
        if not line.strip():
            if block:
                break
            continue
        if re.match(r"^[A-Za-z][A-Za-z0-9 _-]+:\s*", line):
            break
        block.append(line.strip())
    return block


def _approval_signature(spec_path: Path, spec: PilotSpec) -> str:
    payload = "\n".join((
        str(spec_path),
        spec.telos,
        "\0".join(spec.hot_files),
        "\0".join(spec.forbidden_paths),
    ))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _bullet(items: Sequence[str], *, indent: str = "- ") -> str:
    return "\n".join(f"{indent}`{item}`" if item != "None for this pilot." else f"{indent}{item}" for item in items)


def _hot_file_status(spec: PilotSpec) -> str:
    if spec.hot_files:
        return "Hot files are declared and require human approval before live dispatch."
    return "No hot files are in scope."


def _contains_unknown(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in UNKNOWN_MARKERS)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "pilot_00"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit Pilot-00 dry-run artifacts from a markdown spec.")
    parser.add_argument("spec_path", type=Path)
    parser.add_argument("--output-base", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)

    result = run_dryrun(args.spec_path, output_base=args.output_base, run_id=args.run_id)
    print(result.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
