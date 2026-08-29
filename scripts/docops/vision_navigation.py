#!/usr/bin/env python3
"""Vision transmission + navigation projection (`make vision`).

Read-only, offline, deterministic, stdlib-only. Renders the tiered
transmission artifact (docs/vision_maps/VISION_TRANSMISSION.md) and the
UNRATIFIED draft vision registry (docs/MEGAFILE_INDEX.md Slot-1 machine
block). It owns no facts: owner documents win, and no mode grants
ratification, scheduling, implementation-proof, edit-admission, or merge
authority.

Modes (at most one):
  (default)    T1 one-page slice + read-ladder footer + boundary footer
  --crystal    T0 crystal slice + boundary footer
  --full       T0+T1+T2 slices + registry table + open conflicts + footer
  --registry   the specced navigation view (25 rows grouped by function)
  --json       dharma_swarm.vision_navigation.v1 packet (pointers, no content)
  --check      validate registry + transmission (typed exits, see below)
  --packet     self-contained external paste block (stdout only)

Typed exits: 0 ok · 2 bad arguments · 3 malformed registry · 4 transmission rot.

This script never writes, never spawns subprocesses (no git), and produces
byte-identical output across consecutive runs on an unchanged tree.
`--root` overrides the repo root (used by tests against fixture copies).
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = "dharma_swarm.vision_navigation.v1"
AUTHORITY = "navigation_only"
BOUNDARY = (
    "This output is not ratification, scheduling, implementation proof, "
    "edit admission, or merge authority."
)
# The spec renders the boundary footer across two lines; --registry keeps that
# verbatim shape. Other text modes use the single-line form above.
BOUNDARY_TWO_LINE = (
    "This output is not ratification, scheduling, implementation proof,\n"
    "edit admission, or merge authority."
)

ARTIFACT_REL = "docs/vision_maps/VISION_TRANSMISSION.md"
INDEX_REL = "docs/MEGAFILE_INDEX.md"
KERNEL_REL = "dharma_swarm/dharma_kernel.py"
GATES_REL = "dharma_swarm/telos_gates.py"

BLOCK_BEGIN = "<!-- VISION_REGISTRY:BEGIN -->"
BLOCK_END = "<!-- VISION_REGISTRY:END -->"
TIERS = ("T0", "T1", "T2")
FOOTER_BEGIN = "<!-- FOOTER:BEGIN -->"
FOOTER_END = "<!-- FOOTER:END -->"

REGISTRY_ROW_COUNT = 25
OPEN_ROW_COUNT = 8
OPEN_ROW_RE = re.compile(r"\*\*OPEN-\d ·")
EFFECT_SIZE_RE = re.compile(r"AUROC|[dg]\s*=\s*-?\d|\d+(\.\d+)?\s*%")
KERNEL_PRINCIPLE_COUNT = 25
CORE_GATE_COUNT = 11
PACKET_GATE_QUESTIONS = (1, 2, 3, 5, 8)

# Declared-modality role set from the recovered command spec (extracts 1-2):
# canon, reference, report, working plan, active spec, draft, historical.
# UNDECLARED is always allowed and is never inferred by this tool.
ROLE_SET = frozenset(
    {
        "CANON",
        "REFERENCE",
        "REPORT",
        "WORKING_PLAN",
        "ACTIVE_SPEC",
        "DRAFT",
        "HISTORICAL",
        "UNDECLARED",
    }
)
EVIDENCE_CLASS_RE = re.compile(r"^(EXEC|LINT|PROSE|HOLLOW)")

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_REGISTRY = 3
EXIT_ROT = 4
EXIT_CITATION = 5


class RegistryError(Exception):
    """Slot-1 registry block is missing or malformed (exit 3)."""


class RotError(Exception):
    """Transmission artifact is missing, drifted, or rotten (exit 4)."""


# --------------------------------------------------------------------------
# Slicing


def tier_anchors(tier: str) -> tuple[str, str]:
    return (f"<!-- TIER:{tier}:BEGIN -->", f"<!-- TIER:{tier}:END -->")


def slice_between(text: str, begin: str, end: str, *, label: str) -> str:
    """Bytes strictly between the BEGIN-anchor line and the END-anchor line."""
    if text.count(begin) != 1 or text.count(end) != 1:
        raise RotError(f"anchor pair for {label} must appear exactly once")
    begin_at = text.index(begin)
    start = text.index("\n", begin_at) + 1
    end_at = text.index(end)
    line_start = text.rfind("\n", 0, end_at) + 1
    if line_start < start:
        raise RotError(f"anchors for {label} are out of order")
    return text[start:line_start]


def tier_slice(artifact_text: str, tier: str) -> str:
    begin, end = tier_anchors(tier)
    return slice_between(artifact_text, begin, end, label=f"TIER:{tier}")


def footer_slice(artifact_text: str) -> str:
    return slice_between(artifact_text, FOOTER_BEGIN, FOOTER_END, label="FOOTER")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def section_slice(tier_text: str, heading_prefix: str) -> str:
    """One `## §N` section of a tier slice, up to the next `## ` heading."""
    lines = tier_text.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if line.startswith(heading_prefix):
            start = i
            break
    if start is None:
        raise RotError(f"heading {heading_prefix!r} not found in tier slice")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "".join(lines[start:end])


# --------------------------------------------------------------------------
# Registry (MEGAFILE_INDEX Slot-1 machine block)


def load_registry(repo_root: Path) -> dict:
    index_path = repo_root / INDEX_REL
    if not index_path.is_file():
        raise RegistryError(f"missing {INDEX_REL}")
    text = index_path.read_text(encoding="utf-8")
    if text.count(BLOCK_BEGIN) != 1 or text.count(BLOCK_END) != 1:
        raise RegistryError(
            f"{INDEX_REL} must contain exactly one {BLOCK_BEGIN}..{BLOCK_END} block"
        )
    block = text[text.index(BLOCK_BEGIN) : text.index(BLOCK_END)]

    status = None
    by_task = None
    rows: list[dict] = []
    open_conflicts: list[dict] = []
    tier_pins: dict[str, dict] = {}

    oc_re = re.compile(r"^- (OC-\d+) · (.+)$")
    for raw in block.splitlines():
        line = raw.strip()
        if line.startswith("STATUS:"):
            status = line[len("STATUS:") :].strip()
            continue
        if line.startswith("BY_TASK:"):
            by_task = line[len("BY_TASK:") :].strip()
            continue
        oc = oc_re.match(line)
        if oc:
            open_conflicts.append({"id": oc.group(1), "summary": oc.group(2)})
            continue
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            cells = [cell for cell in cells]
            if len(cells) == 7 and cells[0].isdigit():
                rows.append(
                    {
                        "index": int(cells[0]),
                        "group": cells[1],
                        "path": cells[2],
                        "role": cells[3],
                        "declared_role": cells[4],
                        "read_for": cells[5],
                        "evidence": cells[6],
                    }
                )
            elif len(cells) == 4 and cells[0] in TIERS:
                tier_pins[cells[0]] = {
                    "path": cells[1],
                    "anchor": cells[2],
                    "sha256": cells[3],
                }

    if status is None:
        raise RegistryError("Slot-1 block has no STATUS line")
    if by_task is None:
        raise RegistryError("Slot-1 block has no BY_TASK line")
    checkout = re.search(r"checkout ([0-9a-f]{7,40})", status)
    if not checkout:
        raise RegistryError("STATUS line carries no checkout sha")
    if len(rows) != REGISTRY_ROW_COUNT:
        raise RegistryError(
            f"registry must have exactly {REGISTRY_ROW_COUNT} rows, found {len(rows)}"
        )
    if [row["index"] for row in rows] != list(range(1, REGISTRY_ROW_COUNT + 1)):
        raise RegistryError("registry rows must be numbered 1..25 in order")
    if missing_tiers := [tier for tier in TIERS if tier not in tier_pins]:
        raise RegistryError(f"missing transmission tier pins: {missing_tiers}")

    return {
        "status": status,
        "checkout": checkout.group(1),
        "by_task": by_task,
        "rows": rows,
        "open_conflicts": open_conflicts,
        "tier_pins": tier_pins,
    }


def validate_registry(repo_root: Path, registry: dict) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for row in registry["rows"]:
        path = row["path"]
        if path in seen:
            problems.append(f"duplicate registry path: {path}")
        seen.add(path)
        if path.startswith(("/", "~")):
            problems.append(f"registry path not repo-relative: {path}")
        if ".." in Path(path).parts:
            problems.append(f"registry path escapes the repo: {path}")
        if not (repo_root / path).is_file():
            problems.append(f"registry path missing on disk: {path}")
        if row["role"] not in ROLE_SET:
            problems.append(
                f"row {row['index']}: role {row['role']!r} not in the declared set "
                f"(UNDECLARED is allowed; roles are never inferred)"
            )
        if not EVIDENCE_CLASS_RE.match(row["evidence"]):
            problems.append(
                f"row {row['index']}: evidence must start with EXEC|LINT|PROSE|HOLLOW"
            )
    return problems


# --------------------------------------------------------------------------
# Artifact loading + validation


def load_artifact(repo_root: Path) -> str:
    artifact_path = repo_root / ARTIFACT_REL
    if not artifact_path.is_file():
        raise RotError(f"missing {ARTIFACT_REL}")
    return artifact_path.read_text(encoding="utf-8")


def check_anchor_order(text: str) -> None:
    sequence = []
    for tier in TIERS:
        sequence.extend(tier_anchors(tier))
    sequence.extend((FOOTER_BEGIN, FOOTER_END))
    positions = []
    for anchor in sequence:
        if text.count(anchor) != 1:
            raise RotError(f"anchor {anchor!r} must appear exactly once")
        positions.append(text.index(anchor))
    if positions != sorted(positions):
        raise RotError("tier/footer anchors are out of order")


def frontmatter_value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*(\S+)\s*$", text, re.MULTILINE)
    if not match:
        raise RotError(f"frontmatter key {key!r} not found in {ARTIFACT_REL}")
    return match.group(1)


def _class_body(tree: ast.Module, class_name: str) -> list[ast.stmt]:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node.body
    raise RotError(f"class {class_name} not found")


def count_enum_members(source: str, class_name: str) -> int:
    body = _class_body(ast.parse(source), class_name)
    count = 0
    for stmt in body:
        if isinstance(stmt, ast.Assign):
            targets = stmt.targets
            if len(targets) == 1 and isinstance(targets[0], ast.Name):
                count += 1
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            count += 1
    return count


def count_core_gates(source: str) -> int:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target.id
            value = node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(
            node.targets[0], ast.Name
        ):
            target = node.targets[0].id
            value = node.value
        else:
            continue
        if target == "CORE_GATES" and isinstance(value, ast.Dict):
            return len(value.keys)
    raise RotError("CORE_GATES dict literal not found")


def validate_transmission(repo_root: Path, registry: dict) -> list[str]:
    problems: list[str] = []
    text = load_artifact(repo_root)
    check_anchor_order(text)

    for tier in TIERS:
        pin = registry["tier_pins"][tier]
        if pin["path"] != ARTIFACT_REL:
            problems.append(f"tier {tier} pin points at {pin['path']!r}, not {ARTIFACT_REL}")
        actual = sha256_text(tier_slice(text, tier))
        if actual != pin["sha256"]:
            problems.append(
                f"tier {tier} slice sha256 drifted: pinned {pin['sha256'][:12]}…, "
                f"actual {actual[:12]}… (transmission rot)"
            )

    signature = frontmatter_value(text, "kernel_signature")
    if not re.fullmatch(r"[0-9a-f]{64}", signature):
        problems.append("frontmatter kernel_signature is not a sha256 hex digest")
    body = text[text.index("\n---", 1) :]
    if signature not in body:
        problems.append(
            "frontmatter kernel_signature is not restated verbatim in the document body"
        )
    kernel_path = repo_root / KERNEL_REL
    gates_path = repo_root / GATES_REL
    if not kernel_path.is_file() or not gates_path.is_file():
        problems.append("kernel/gate sources missing; cannot cross-check the law layer")
    else:
        principle_count = count_enum_members(
            kernel_path.read_text(encoding="utf-8"), "MetaPrinciple"
        )
        if principle_count != KERNEL_PRINCIPLE_COUNT:
            problems.append(
                f"MetaPrinciple has {principle_count} members, doc claims "
                f"{KERNEL_PRINCIPLE_COUNT}"
            )
        gate_count = count_core_gates(gates_path.read_text(encoding="utf-8"))
        if gate_count != CORE_GATE_COUNT:
            problems.append(
                f"CORE_GATES has {gate_count} entries, doc claims {CORE_GATE_COUNT}"
            )

    t2 = tier_slice(text, "T2")
    open_rows = len(OPEN_ROW_RE.findall(section_slice(t2, "## §9")))
    if open_rows != OPEN_ROW_COUNT:
        problems.append(
            f"§9 OPEN row count is {open_rows}, pinned {OPEN_ROW_COUNT} "
            "(rows may not be added or resolved without an ADJUDICATED-ON receipt)"
        )

    mechanism = section_slice(t2, "## §4")
    hit = EFFECT_SIZE_RE.search(mechanism)
    if hit:
        problems.append(
            f"§4 effect-size firewall tripped: {hit.group(0)!r} "
            "(the mechanism section must stay numeral-free on effect sizes; OPEN-8)"
        )

    if "UNRATIFIED" not in text:
        problems.append("UNRATIFIED banner missing from the artifact")
    footer = footer_slice(text)
    if "Not ratification" not in footer or "merge authority" not in footer:
        problems.append("boundary footer missing or altered in the artifact")
    return problems


# --------------------------------------------------------------------------
# Rendering


def grouped_rows(rows: list[dict]) -> list[tuple[str, list[dict]]]:
    order: list[str] = []
    buckets: dict[str, list[dict]] = {}
    for row in rows:
        group = row["group"]
        if group not in buckets:
            order.append(group)
            buckets[group] = []
        buckets[group].append(row)
    return [(group, buckets[group]) for group in order]


def render_registry_body(repo_root: Path, registry: dict) -> str:
    present = sum(
        1 for row in registry["rows"] if (repo_root / row["path"]).is_file()
    )
    lines = [
        "CURATED VISION CORPUS — 25 documents, grouped by function",
        f"Coverage: {present}/{REGISTRY_ROW_COUNT} selected documents present",
        "",
    ]
    for group, rows in grouped_rows(registry["rows"]):
        lines.append(f"## {group}")
        for row in rows:
            lines.append(
                f"{row['index']:02d}  [{row['role']}] {row['path']} — "
                f"{row['read_for']}  [{row['evidence']}]"
            )
        lines.append("")
    lines.append("OPEN CONFLICTS (registry-level; disagreements are data, never flattened)")
    for conflict in registry["open_conflicts"]:
        lines.append(f"  {conflict['id']} · {conflict['summary']}")
    return "\n".join(lines)


def render_read_ladder(registry: dict) -> str:
    lines = ["READ LADDER — top-5 of the draft registry (UNRATIFIED; rank is navigation, never a prize):"]
    for row in registry["rows"][:5]:
        lines.append(f"  {row['index']}. {row['path']} — {row['read_for']}")
    lines.append(f"BY TASK: {registry['by_task']}")
    return "\n".join(lines)


def render_default(repo_root: Path, registry: dict) -> str:
    text = load_artifact(repo_root)
    return "\n".join(
        [
            "DHARMA SWARM — VISION TRANSMISSION (T1 · ONE PAGE) · UNRATIFIED DRAFT",
            f"Source: {ARTIFACT_REL} · registry: {INDEX_REL} § Slot 1 · owners win",
            "",
            tier_slice(text, "T1").rstrip("\n"),
            "",
            render_read_ladder(registry),
            "",
            footer_slice(text).rstrip("\n"),
            "",
        ]
    )


def render_crystal(repo_root: Path) -> str:
    text = load_artifact(repo_root)
    return "\n".join(
        [
            tier_slice(text, "T0").rstrip("\n"),
            "",
            footer_slice(text).rstrip("\n"),
            "",
        ]
    )


def render_full(repo_root: Path, registry: dict) -> str:
    text = load_artifact(repo_root)
    return "\n".join(
        [
            "DHARMA SWARM — VISION TRANSMISSION (T0+T1+T2 · FULL LATTICE) · UNRATIFIED DRAFT",
            f"Source: {ARTIFACT_REL} · registry: {INDEX_REL} § Slot 1 · owners win",
            f"STATUS: {registry['status']}",
            "",
            tier_slice(text, "T0").rstrip("\n"),
            "",
            tier_slice(text, "T1").rstrip("\n"),
            "",
            tier_slice(text, "T2").rstrip("\n"),
            "",
            render_registry_body(repo_root, registry),
            "",
            footer_slice(text).rstrip("\n"),
            "",
        ]
    )


def render_registry_view(repo_root: Path, registry: dict) -> str:
    return "\n".join(
        [
            "DHARMA VISION — curated navigation, owns no facts",
            f"Source: {INDEX_REL} § Slot 1",
            f"STATUS: {registry['status']}",
            "",
            render_registry_body(repo_root, registry),
            "",
            BOUNDARY_TWO_LINE,
            "",
        ]
    )


def render_json(repo_root: Path, registry: dict) -> str:
    text = load_artifact(repo_root)
    transmission = {}
    for tier in TIERS:
        transmission[tier] = {
            "anchor": f"TIER:{tier}",
            "path": ARTIFACT_REL,
            "sha256": sha256_text(tier_slice(text, tier)),
        }
    payload = {
        "authority": AUTHORITY,
        "boundary": BOUNDARY,
        "checkout": registry["checkout"],
        "open_conflicts": registry["open_conflicts"],
        "registry": registry["rows"],
        "schema": SCHEMA,
        "status": registry["status"],
        "transmission": transmission,
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def gate_questions(t2_text: str) -> dict[int, str]:
    gate = section_slice(t2_text, "## §GATE")
    questions: dict[int, str] = {}
    current = None
    for line in gate.splitlines():
        numbered = re.match(r"^(\d)\. (.*)$", line)
        if numbered:
            current = int(numbered.group(1))
            questions[current] = numbered.group(2).strip()
        elif current is not None and line.startswith("   "):
            questions[current] += " " + line.strip()
        else:
            current = None
    return questions


def render_packet(repo_root: Path, registry: dict) -> str:
    text = load_artifact(repo_root)
    t2 = tier_slice(text, "T2")
    questions = gate_questions(t2)
    missing = [n for n in PACKET_GATE_QUESTIONS if n not in questions]
    if missing:
        raise RotError(f"§GATE is missing packet questions {missing}")
    question_lines = [
        f"{position}. {questions[number]} [§GATE Q{number}]"
        for position, number in enumerate(PACKET_GATE_QUESTIONS, start=1)
    ]
    return "\n".join(
        [
            (
                "DHARMA SWARM — VISION TRANSMISSION PACKET · generated from "
                f"checkout {registry['checkout']} · UNRATIFIED DRAFT"
            ),
            "",
            tier_slice(text, "T0").rstrip("\n"),
            "",
            tier_slice(text, "T1").rstrip("\n"),
            "",
            section_slice(t2, "## §9").rstrip("\n"),
            "",
            section_slice(t2, "## §10").rstrip("\n"),
            "",
            "GATE — answer these to your operator or a judge of a different",
            "model family before building on this packet (self-grading is void):",
            "",
            *question_lines,
            "",
            footer_slice(text).rstrip("\n"),
            "",
        ]
    )


def run_check(repo_root: Path) -> int:
    lines: list[str] = []
    registry = None
    registry_problems: list[str] = []
    rot_problems: list[str] = []
    try:
        registry = load_registry(repo_root)
        registry_problems.extend(validate_registry(repo_root, registry))
    except RegistryError as exc:
        registry_problems.append(str(exc))

    if registry is not None:
        try:
            rot_problems.extend(validate_transmission(repo_root, registry))
        except RotError as exc:
            rot_problems.append(str(exc))

    citation_problems, citation_backlog = check_citations(repo_root)

    for problem in registry_problems:
        lines.append(f"FAIL registry: {problem}")
    for problem in rot_problems:
        lines.append(f"FAIL transmission: {problem}")
    for problem in citation_problems:
        lines.append(f"FAIL citation: {problem}")
    if citation_backlog:
        lines.append(f"WARN citation: {citation_backlog}")
    if not registry_problems and not rot_problems and not citation_problems:
        lines.append(
            f"OK vision registry: {REGISTRY_ROW_COUNT} rows · "
            f"{OPEN_ROW_COUNT} OPEN rows · tier pins T0/T1/T2 verified · "
            "kernel signature restated · law-layer counts 25/11"
        )
    lines.append(BOUNDARY)
    sys.stdout.write("\n".join(lines) + "\n")
    if registry_problems:
        return EXIT_REGISTRY
    if rot_problems:
        return EXIT_ROT
    if citation_problems:
        return EXIT_CITATION
    return EXIT_OK


def check_citations(repo_root: Path) -> tuple[list[str], str]:
    """Stage 0 source-fidelity gate, run over the render path.

    Hard failures (BROKEN / DRIFTED / UNPINNABLE) mean a citation points at
    something that is not there or no longer says what was claimed. UNPINNED
    and FLAGGED are the migration backlog: reported with a count so the ratchet
    is visible, not silent, but not yet blocking.
    """
    import vision_citations as citations

    try:
        text = load_artifact(repo_root)
        for tier in TIERS:
            tier_slice(text, tier)
    except (RotError, OSError):
        # A missing or structurally broken artifact is the rot gate's finding,
        # not a citation finding; do not mask its typed exit.
        return [], ""
    hard: list[str] = []
    backlog: dict[str, int] = {}
    for tier in TIERS:
        findings = citations.audit_text(repo_root, tier_slice(text, tier), tier)
        for finding in findings:
            if finding.severity in ("BROKEN", "DRIFTED", "UNPINNABLE"):
                hard.append(finding.render())
            else:
                backlog[finding.severity] = backlog.get(finding.severity, 0) + 1
    summary = ""
    if backlog:
        detail = " · ".join(f"{key} {value}" for key, value in sorted(backlog.items()))
        summary = f"{detail} — citations resolve but are not yet span-pinned (migration backlog)"
    return hard, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vision_navigation.py",
        description="Read-only vision transmission + navigation projection.",
    )
    for flag, help_text in (
        ("--crystal", "T0 crystal slice + boundary footer"),
        ("--full", "all tiers + registry + open conflicts"),
        ("--registry", "specced navigation view (25 rows grouped by function)"),
        ("--json", "machine packet (pointers only, no content)"),
        ("--check", "validate registry + transmission; typed exits 0/2/3/4"),
        ("--packet", "self-contained external paste block"),
    ):
        parser.add_argument(flag, action="store_true", help=help_text)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repo root override (tests only)",
    )
    args = parser.parse_args(argv)

    modes = [
        name
        for name in ("crystal", "full", "registry", "json", "check", "packet")
        if getattr(args, name)
    ]
    if len(modes) > 1:
        parser.error(f"choose at most one mode, got: {', '.join(modes)}")
    mode = modes[0] if modes else "default"
    repo_root = args.root.resolve()

    if mode == "check":
        return run_check(repo_root)

    try:
        if mode == "crystal":
            sys.stdout.write(render_crystal(repo_root))
            return EXIT_OK
        registry = load_registry(repo_root)
        problems = validate_registry(repo_root, registry)
        if problems:
            raise RegistryError("; ".join(problems))
        renderer = {
            "default": lambda: render_default(repo_root, registry),
            "full": lambda: render_full(repo_root, registry),
            "registry": lambda: render_registry_view(repo_root, registry),
            "json": lambda: render_json(repo_root, registry),
            "packet": lambda: render_packet(repo_root, registry),
        }[mode]
        sys.stdout.write(renderer())
        return EXIT_OK
    except RegistryError as exc:
        sys.stderr.write(f"BROKEN registry (render refused): {exc}\n{BOUNDARY}\n")
        return EXIT_REGISTRY
    except RotError as exc:
        sys.stderr.write(f"BROKEN transmission (render refused): {exc}\n{BOUNDARY}\n")
        return EXIT_ROT


if __name__ == "__main__":
    sys.exit(main())
