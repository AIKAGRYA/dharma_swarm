#!/usr/bin/env python3
"""Create governed work packets from validated prompt-pack lanes.

This script does not run an LLM and does not edit source code. It turns a
validated prompt lane into a concrete work packet an agent can execute under the
existing governance gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.governance.verify_prompt_pack import (  # noqa: E402
    JsonDict,
    load_prompt_pack,
    validate_prompt_pack,
)

DEFAULT_PACK = REPO_ROOT / "docs/governance/prompt_packs/slop_cleanup_subagents.json"
DEFAULT_OUT_DIR = REPO_ROOT / "reports/governance/prompt_lane_runs"


class PromptLaneError(ValueError):
    """Raised when a prompt-lane request is structurally invalid."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
    return slug.lower() or "prompt-lane"


def find_lane(pack: JsonDict, lane_id: str) -> JsonDict:
    lanes = pack.get("lanes")
    if not isinstance(lanes, list):
        raise PromptLaneError("prompt pack has no lanes")
    for lane in lanes:
        if isinstance(lane, dict) and lane.get("lane_id") == lane_id:
            return lane
    available = sorted(str(lane.get("lane_id")) for lane in lanes if isinstance(lane, dict))
    raise PromptLaneError(f"unknown lane_id {lane_id!r}; available: {', '.join(available)}")


def source_artifact(pack: JsonDict, filename: str) -> JsonDict:
    source = pack.get("source")
    artifacts = source.get("source_artifacts") if isinstance(source, dict) else None
    if not isinstance(artifacts, list):
        return {}
    for artifact in artifacts:
        if isinstance(artifact, dict) and artifact.get("filename") == filename:
            return artifact
    return {}


def normalize_target(target: str) -> str:
    if not target.strip():
        raise PromptLaneError("target is required")
    candidate = Path(target).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    resolved = candidate.resolve()
    try:
        relative = resolved.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise PromptLaneError(f"target must be inside repo: {target}") from exc
    if not resolved.exists():
        raise PromptLaneError(f"target does not exist: {target}")
    return "." if str(relative) == "." else relative.as_posix()


def prompt_hash(pack: JsonDict, lane: JsonDict, target: str, base_ref: str) -> str:
    payload = {
        "pack_id": pack.get("pack_id"),
        "lane_id": lane.get("lane_id"),
        "target": target,
        "base_ref": base_ref,
        "transcript": lane.get("transcript"),
        "required_gates": lane.get("required_gates"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def build_agent_prompt(
    *,
    pack: JsonDict,
    lane: JsonDict,
    target: str,
    base_ref: str,
    packet_hash: str,
    extra_context: str = "",
) -> str:
    constraints = _string_list(pack.get("global_constraints"))
    required_gates = _string_list(lane.get("required_gates"))
    allowed_actions = _string_list(lane.get("allowed_actions"))
    forbidden_actions = _string_list(lane.get("forbidden_actions"))
    detectors = _string_list(lane.get("required_detectors"))

    sections = [
        "# Governed Prompt Lane Work Packet",
        "",
        f"Prompt hash: `{packet_hash}`",
        f"Pack: `{pack.get('pack_id')}`",
        f"Lane: `{lane.get('lane_id')}` - {lane.get('title')}",
        f"Target: `{target}`",
        f"Base ref: `{base_ref}`",
        f"Risk: `{lane.get('risk_level')}`",
        "",
        "## Source Prompt",
        "",
        str(lane.get("transcript", "")).strip(),
        "",
        "## Objective",
        "",
        str(lane.get("objective", "")).strip(),
        "",
        "## Required Detectors",
        "",
        *[f"- `{detector}`" for detector in detectors],
        "",
        "## Required Gates Before Claiming Done",
        "",
        *[f"- `{gate}`" for gate in required_gates],
        "",
        "## Allowed Actions",
        "",
        *[f"- {action}" for action in allowed_actions],
        "",
        "## Forbidden Actions",
        "",
        *[f"- {action}" for action in forbidden_actions],
        "",
        "## Global Constraints",
        "",
        *[f"- `{constraint}`" for constraint in constraints],
        "",
        "## Execution Rules",
        "",
        "- Validate the prompt pack before starting.",
        "- Run impact analysis before editing any target symbol.",
        "- Make the smallest coherent batch of changes.",
        "- Preserve user and unrelated worktree changes.",
        "- Write before/after evidence.",
        "- Do not auto-delete, auto-merge, or silently bypass gates.",
        "- Route normalized findings through the slop governance surface.",
    ]
    if extra_context.strip():
        sections.extend(["", "## Additional Context", "", extra_context.strip()])
    return "\n".join(sections).rstrip() + "\n"


def build_work_packet(
    *,
    pack_path: Path,
    pack: JsonDict,
    lane: JsonDict,
    target: str,
    base_ref: str,
    extra_context: str = "",
) -> JsonDict:
    artifact = source_artifact(pack, str(lane.get("source_artifact", "")))
    packet_hash = prompt_hash(pack, lane, target, base_ref)
    agent_prompt = build_agent_prompt(
        pack=pack,
        lane=lane,
        target=target,
        base_ref=base_ref,
        packet_hash=packet_hash,
        extra_context=extra_context,
    )
    raw_source = pack.get("source")
    source: JsonDict = raw_source if isinstance(raw_source, dict) else {}
    raw_gate_contract = pack.get("gate_contract")
    gate_contract: JsonDict = raw_gate_contract if isinstance(raw_gate_contract, dict) else {}
    return {
        "schema_version": 1,
        "kind": "prompt_lane_work_packet",
        "created_utc": utc_now_iso(),
        "prompt_hash": packet_hash,
        "pack": {
            "path": str(pack_path.relative_to(REPO_ROOT) if pack_path.is_relative_to(REPO_ROOT) else pack_path),
            "pack_id": pack.get("pack_id"),
            "status": pack.get("status"),
            "source_completeness": source.get("completeness"),
            "known_missing_slides": source.get("known_missing_slides", []),
        },
        "lane": {
            "lane_id": lane.get("lane_id"),
            "title": lane.get("title"),
            "risk_level": lane.get("risk_level"),
            "source_artifact": lane.get("source_artifact"),
            "source_sha256": artifact.get("sha256"),
            "transcript": lane.get("transcript"),
            "objective": lane.get("objective"),
            "required_detectors": _string_list(lane.get("required_detectors")),
            "required_gates": _string_list(lane.get("required_gates")),
            "allowed_actions": _string_list(lane.get("allowed_actions")),
            "forbidden_actions": _string_list(lane.get("forbidden_actions")),
            "manual_review_required": lane.get("manual_review_required") is True,
            "requires_blast_radius": lane.get("requires_blast_radius") is True,
        },
        "target": {
            "path": target,
            "base_ref": base_ref,
        },
        "preflight": {
            "pack_validated": True,
            "before_agent_run": _string_list(gate_contract.get("before_agent_run")),
        },
        "post_run_requirements": _string_list(gate_contract.get("after_agent_run")),
        "authority": {
            "authorizes_source_edits": False,
            "authorizes_deletion": False,
            "authorizes_auto_merge": False,
            "note": "This packet authorizes investigation and bounded proposals only; source edits require normal repo discipline and gate evidence.",
        },
        "agent_prompt": agent_prompt,
    }


def render_markdown(packet: JsonDict) -> str:
    lane = packet["lane"]
    target = packet["target"]
    lines = [
        f"# Prompt Lane Run: {lane['lane_id']}",
        "",
        f"- Prompt hash: `{packet['prompt_hash']}`",
        f"- Pack: `{packet['pack']['pack_id']}`",
        f"- Target: `{target['path']}`",
        f"- Base ref: `{target['base_ref']}`",
        f"- Risk: `{lane['risk_level']}`",
        f"- Source artifact: `{lane['source_artifact']}`",
        f"- Source sha256: `{lane.get('source_sha256')}`",
        "",
        "## Agent Prompt",
        "",
        packet["agent_prompt"].rstrip(),
        "",
    ]
    return "\n".join(lines)


def write_work_packet(packet: JsonDict, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    lane_id = slugify(str(packet["lane"]["lane_id"]))
    stamp = str(packet["created_utc"]).replace(":", "").replace("+0000", "z").replace("+00:00", "z")
    stem = f"{stamp}_{lane_id}_{packet['prompt_hash']}"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(packet), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--lane", required=True, help="Prompt pack lane_id to prepare")
    parser.add_argument("--target", required=True, help="Repo-relative file or directory target")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--context", default="", help="Additional agent context")
    parser.add_argument("--check-source-files", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--format", choices=["text", "json", "prompt"], default="text")
    args = parser.parse_args()

    pack_path = args.pack if args.pack.is_absolute() else REPO_ROOT / args.pack
    pack = load_prompt_pack(pack_path)
    errors = validate_prompt_pack(pack, check_source_files=args.check_source_files)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    try:
        lane = find_lane(pack, args.lane)
        target = normalize_target(args.target)
    except PromptLaneError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    packet = build_work_packet(
        pack_path=pack_path,
        pack=pack,
        lane=lane,
        target=target,
        base_ref=args.base_ref,
        extra_context=args.context,
    )
    written: tuple[Path, Path] | None = None
    if not args.no_write:
        out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
        written = write_work_packet(packet, out_dir)

    if args.format == "json":
        result = dict(packet)
        if written:
            result["written"] = {"json": str(written[0]), "markdown": str(written[1])}
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.format == "prompt":
        print(packet["agent_prompt"], end="")
    else:
        print(
            f"prepared lane={packet['lane']['lane_id']} target={target} "
            f"hash={packet['prompt_hash']}"
        )
        if written:
            print(f"json={written[0]}")
            print(f"markdown={written[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
