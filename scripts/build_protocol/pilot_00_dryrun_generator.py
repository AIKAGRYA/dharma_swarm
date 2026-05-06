"""Generate Pilot-00 dry-run build packet artifacts.

This script is intentionally shape-only. It parses a small markdown input
spec and writes BuildPacket/WorkPacket-shaped JSON plus human-readable plan
artifacts under a dry-run output directory. It does not import live DHARMA
runtime modules, mutate SQLite, spawn agents, or create worktrees.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


DEFAULT_FORBIDDEN_FILES = (
    "dharma_swarm/orchestrate_live.py",
    "dharma_swarm/swarm.py",
    "dharma_swarm/frontier_council.py",
    "dharma_swarm/agent_runner.py",
    "dharma_swarm/guardian_crew.py",
    "dharma_swarm/insight_brief.py",
    "api/**",
    "dashboard/**",
)

DEFAULT_FORBIDDEN_DOMAINS = (
    "Operator Brief",
    "Daily Insight",
    "ontology refactor",
    "memory consolidation",
    "dashboard",
    "API",
    "provider or routing migration",
    "broad cleanup",
)

DEFAULT_GATES = ("telos", "scoped_tests", "scope_check")
UNKNOWN_MARKERS = ("i don't know", "todo", "tbd")


@dataclass(frozen=True)
class PilotSpec:
    title: str
    spec_path: Path
    telos: str
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    hot_files: tuple[str, ...]
    proof_command: str
    reviewer: str
    max_diff_lines: int = 50


def _slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "pilot-00"


def _extract_title(lines: Sequence[str], spec_path: Path) -> str:
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or spec_path.stem
    return spec_path.stem


def _extract_scalar(lines: Sequence[str], label: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(label)}\s*:\s*(.*)\s*$", re.IGNORECASE)
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        inline = match.group(1).strip()
        if inline:
            return inline
        for following in lines[index + 1 :]:
            value = following.strip()
            if value:
                return value
        return ""
    return ""


def _extract_list(lines: Sequence[str], label: str) -> tuple[str, ...]:
    pattern = re.compile(rf"^\s*{re.escape(label)}\s*:\s*$", re.IGNORECASE)
    values: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if pattern.match(line):
            in_section = True
            continue
        if not in_section:
            continue
        if not stripped:
            if values:
                break
            continue
        if stripped.endswith(":") and not stripped.startswith(("-", "*")):
            break
        if stripped.startswith(("-", "*")):
            value = stripped[1:].strip()
            if value:
                values.append(value)
            continue
        if values:
            break
    return tuple(values)


def _has_unknown(value: str) -> bool:
    lower = value.lower()
    return any(marker in lower for marker in UNKNOWN_MARKERS)


def _validate_spec(spec: PilotSpec) -> None:
    problems: list[str] = []
    if not spec.telos or _has_unknown(spec.telos):
        problems.append("telos must be concrete")
    if not spec.allowed_paths:
        problems.append("allowed paths must not be empty")
    if any(_has_unknown(path) for path in spec.allowed_paths):
        problems.append("allowed paths contain unknown markers")
    if not spec.forbidden_paths:
        problems.append("forbidden paths must not be empty")
    if not spec.proof_command or "\n" in spec.proof_command or _has_unknown(spec.proof_command):
        problems.append("proof command must be one concrete line")
    if not spec.reviewer or _has_unknown(spec.reviewer):
        problems.append("reviewer must be concrete")
    if set(spec.allowed_paths) & set(spec.forbidden_paths):
        problems.append("allowed paths and forbidden paths overlap")
    if spec.max_diff_lines <= 0:
        problems.append("max diff lines must be positive")
    if problems:
        raise ValueError("; ".join(problems))


def parse_spec(spec_path: Path) -> PilotSpec:
    text = spec_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    forbidden_paths = _extract_list(lines, "Forbidden paths") or DEFAULT_FORBIDDEN_FILES
    spec = PilotSpec(
        title=_extract_title(lines, spec_path),
        spec_path=spec_path,
        telos=_extract_scalar(lines, "Telos"),
        allowed_paths=_extract_list(lines, "Allowed paths"),
        forbidden_paths=tuple(forbidden_paths),
        hot_files=_extract_list(lines, "Hot files"),
        proof_command=_extract_scalar(lines, "Proof command"),
        reviewer=_extract_scalar(lines, "Reviewer"),
        max_diff_lines=int(_extract_scalar(lines, "Max diff lines") or "50"),
    )
    _validate_spec(spec)
    return spec


def _approval_signature(spec: PilotSpec) -> str:
    material = json.dumps(
        {
            "spec_path": str(spec.spec_path),
            "telos_statement": spec.telos,
            "hot_files": list(spec.hot_files),
            "forbidden_files": list(spec.forbidden_paths),
        },
        ensure_ascii=True,
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def _json_dump(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def _format_bullets(items: Sequence[str], *, code: bool = False) -> str:
    if not items:
        return "- None"
    if code:
        return "\n".join(f"- `{item}`" for item in items)
    return "\n".join(f"- {item}" for item in items)


def build_artifacts(spec: PilotSpec, output_dir: Path) -> None:
    work_packets_dir = output_dir / "work_packets"
    work_packets_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat()
    build_packet_id = _slugify(spec.title)

    build_packet = {
        "title": spec.title,
        "description": spec.telos,
        "status": "pending",
        "created_by": "pilot-00",
        "metadata": {
            "approval_signature": _approval_signature(spec),
            "child_task_ids": ["wp_001"],
            "created_at": created_at,
            "forbidden_domains": list(DEFAULT_FORBIDDEN_DOMAINS),
            "forbidden_files": list(spec.forbidden_paths),
            "gates_required": list(DEFAULT_GATES),
            "hot_files": list(spec.hot_files),
            "human_approver": "dhyana",
            "kind": "build_packet",
            "max_iterations": 2,
            "proof_command": spec.proof_command,
            "protocol_version": "v0",
            "spec_path": str(spec.spec_path),
            "telos_statement": spec.telos,
        },
    }

    work_packet = {
        "constraints": ["no_merge", "no_push", "no_shell_exec", "scope_locked"],
        "id": "wp_001",
        "metadata": {"dry_run": True},
        "output": ["diff", "test_output", "checkpoint_ref"],
        "payload": {
            "allowed_paths": list(spec.allowed_paths),
            "builder_agent": "unassigned",
            "checkpoint_ids": [],
            "forbidden_paths": list(spec.forbidden_paths),
            "kind": "work_packet",
            "lead_agent": "pilot-00",
            "max_diff_lines": spec.max_diff_lines,
            "parent_build_packet_id": build_packet_id,
            "protocol_version": "v0",
            "scoped_tests": [spec.proof_command],
            "worktree_path": "",
        },
        "scope": list(spec.allowed_paths),
        "sender": "pilot-00",
        "status": "queued",
        "task": spec.telos,
    }

    source_copy = output_dir / "source_spec_copy.md"
    shutil.copyfile(spec.spec_path, source_copy)
    _json_dump(output_dir / "build_packet.json", build_packet)
    _json_dump(work_packets_dir / "wp_001.json", work_packet)
    (output_dir / "proof_command.txt").write_text(spec.proof_command + "\n", encoding="utf-8")
    (output_dir / "gates_required.txt").write_text("\n".join(DEFAULT_GATES) + "\n", encoding="utf-8")
    (output_dir / "rejected_paths.txt").write_text(
        "\n".join(list(spec.forbidden_paths) + list(DEFAULT_FORBIDDEN_DOMAINS)) + "\n",
        encoding="utf-8",
    )
    (output_dir / "pre_flight_answers.md").write_text(_render_preflight(spec), encoding="utf-8")
    (output_dir / "dispatch_plan.md").write_text(_render_dispatch_plan(spec, output_dir), encoding="utf-8")
    _json_dump(
        output_dir / "validation_report.json",
        {
            "agents_spawned": False,
            "dry_run": True,
            "required_outputs": [
                "build_packet.json",
                "work_packets/wp_001.json",
                "dispatch_plan.md",
                "proof_command.txt",
                "gates_required.txt",
                "pre_flight_answers.md",
            ],
            "root": str(output_dir),
            "source_edits": False,
            "sqlite_writes": False,
            "work_packets": ["wp_001.json"],
            "worktrees_created": False,
        },
    )


def _render_preflight(spec: PilotSpec) -> str:
    return f"""# Pilot-00 Pre-Flight Answers

1. What files are hot?
   {_format_bullets(spec.hot_files)}

2. What files are forbidden?
   {_format_bullets(spec.forbidden_paths)}

3. What is the smallest proof of success?
   - `{spec.proof_command}`

4. What can a builder edit?
   {_format_bullets(spec.allowed_paths, code=True)}

5. What happens if tests fail?
   - The WorkPacket stays unapproved and would require one scoped FixupPacket or human rejection. Pilot-00 does not run the fixup.

6. Who reviews before merge?
   - `{spec.reviewer}`; human merge approval remains with Dhyana.
"""


def _render_dispatch_plan(spec: PilotSpec, output_dir: Path) -> str:
    hot_status = (
        "No hot files are in scope."
        if not spec.hot_files
        else "Hot files require explicit human scope approval: " + ", ".join(spec.hot_files) + "."
    )
    return f"""# Pilot-00 Dispatch Plan

Source spec path: `{spec.spec_path}`

## Telos

{spec.telos}

## Allowed Paths

{_format_bullets(spec.allowed_paths, code=True)}

## Forbidden Paths

{_format_bullets(spec.forbidden_paths, code=True)}

## Hot-File Status

{hot_status}

## Proposed WorkPackets

### wp_001

- Builder: unassigned
- Reviewer: {spec.reviewer}
- Scope: {", ".join(f"`{path}`" for path in spec.allowed_paths)}
- Intended change: {spec.telos}
- Max diff: {spec.max_diff_lines} lines
- Constraints: no merge, no push, no shell exec, scope locked

## Gates Required

{_format_bullets(DEFAULT_GATES, code=True)}

## Proof Command

```bash
{spec.proof_command}
```

## Why This Plan Is Safe

- It targets bounded allowed paths only.
- It has a deterministic proof command.
- It does not touch Operator Brief, Daily Insight, ontology, memory consolidation, dashboard, API, providers, routing, AgentRunner, Guardian, or runtime orchestration unless those paths are explicitly listed in allowed paths and hot scope is human-approved.
- Pilot-00 creates no worktree, spawns no agent, writes no SQLite state, and edits no source.

## Reasons This Plan Would Be Rejected

- Any editable scope outside the allowed paths.
- Any missing or non-deterministic proof command.
- Any attempt to touch forbidden domains or hot files without human approval.
- Any pre-flight answer that is unknown, broad, or unbounded.
- Any generated artifact outside `{output_dir}`.
"""


def generate(spec_path: Path, output_root: Path, run_id: str | None, overwrite: bool = False) -> Path:
    spec = parse_spec(spec_path)
    resolved_run_id = run_id or f"{_slugify(spec.title)}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    output_dir = output_root / resolved_run_id
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(f"dry-run directory already exists: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    build_artifacts(spec, output_dir)
    return output_dir


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_spec", type=Path, help="Markdown Pilot-00 input spec.")
    parser.add_argument(
        "--dry-run-id",
        help="Stable dry-run directory name. Defaults to title plus UTC timestamp.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path.home() / ".dharma" / "build_protocol" / "dryruns",
        help="Root directory for dry-run artifacts.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing dry-run directory with the same id.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        output_dir = generate(
            args.input_spec,
            args.output_root,
            args.dry_run_id,
            overwrite=args.overwrite,
        )
    except Exception as exc:
        print(f"pilot-00 dry-run generation failed: {exc}", file=sys.stderr)
        return 1
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
