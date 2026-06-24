"""Stage-contract model + parser + DAG derivation (Slice A).

A *workspace* is a directory. *Stages* are numbered child folders, each holding
a ``CONTEXT.md`` contract with an Inputs table, a Process list, and an Outputs
table. This module reads that on-disk declaration into typed objects and emits
``Task`` objects with ``depends_on`` edges — it does NOT execute anything
(execution is stage_executor.py, which routes through spine.invoke_agent).

Design notes (the implicit why) live in
docs/research/FILESYSTEM_SUBSTRATE_SLICE_A_SPEC.md. The load-bearing one: the
folder DECLARES the DAG; the swarm's TaskBoard EXECUTES it. Declaration is not
execution — so this module stops at ``to_tasks()``.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pydantic import BaseModel, Field

from dharma_swarm.models import Task

# Stage folders look like "01-research", "02_synthesize", "3-ship".
_STAGE_DIR_RE = re.compile(r"^(\d+)[-_](.+)$")
# A markdown table row: "| a | b | c |"
_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
# A numbered process step: "1. do the thing"
_PROCESS_STEP_RE = re.compile(r"^\s*\d+[.)]\s+(.*)$")


class WorkspaceError(ValueError):
    """Raised when a workspace or stage CONTEXT.md is malformed.

    Fails closed with the offending path — a half-parsed contract that silently
    drops a dependency is worse than a hard stop (it kills the observability
    property the whole power exists for).
    """


class StageInput(BaseModel):
    """One row of a stage's Inputs table.

    The ``scope`` and ``why`` columns are the token firewall and the audit
    trail: ``scope`` lets the loader pull only part of a file into context;
    ``why`` is the human-/agent-readable justification.
    """

    source: str = ""
    location: str = ""
    scope: str = "full"
    why: str = ""


class StageOutput(BaseModel):
    """One row of a stage's Outputs table."""

    name: str = ""
    location: str = ""
    fmt: str = "markdown"


class StageContract(BaseModel):
    """One stage = one declared morphism (typed inputs -> typed outputs).

    Proposed ontology api_name (defer to owner): ``dharma.fs_substrate.StageContract``.
    The Inputs/Outputs typing is what lets stages compose into a provable DAG —
    categorical-systems-theory grounding made into a dataclass.
    """

    stage_id: str
    order: int = 0
    type: str = "stage"
    agent_role: str | None = None
    title: str = ""
    inputs: list[StageInput] = Field(default_factory=list)
    process: list[str] = Field(default_factory=list)
    outputs: list[StageOutput] = Field(default_factory=list)
    path: str = ""
    contract_sha256: str = ""


class StageWorkspace(BaseModel):
    """A workspace: a root directory + its stages sorted by order.

    Proposed ontology api_name (defer to owner): ``dharma.fs_substrate.StageWorkspace``.
    """

    root: str
    stages: list[StageContract] = Field(default_factory=list)


# ── frontmatter + section parsing ─────────────────────────────────────────


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split a leading ``---`` YAML-lite frontmatter block from the body.

    Only flat ``key: value`` pairs are supported (the contract frontmatter is
    deliberately plain: type, stage, agent, title).
    """
    if not text.lstrip().startswith("---"):
        return {}, text
    stripped = text.lstrip()
    end = stripped.find("\n---", 3)
    if end == -1:
        return {}, text
    block = stripped[3:end].strip()
    body = stripped[end + 4 :].lstrip("\n")
    meta: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        meta[key.strip()] = val.strip().strip("'\"")
    return meta, body


def _sections(body: str) -> dict[str, list[str]]:
    """Group body lines under their ``## Heading`` (lowercased heading key)."""
    out: dict[str, list[str]] = {}
    current: str | None = None
    for line in body.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower()
            out[current] = []
        elif current is not None:
            out[current].append(line)
    return out


def _table_rows(lines: list[str]) -> list[list[str]]:
    """Parse markdown table rows, dropping the header and separator rows."""
    rows: list[list[str]] = []
    for line in lines:
        m = _TABLE_ROW_RE.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        # Skip the |---|---| separator row.
        if cells and all(set(c) <= {"-", ":", " "} and c for c in cells):
            continue
        rows.append(cells)
    # First surviving row is the header.
    return rows[1:] if rows else []


def parse_context_md(text: str, path: str) -> StageContract:
    """Parse a single stage CONTEXT.md into a StageContract.

    Fails closed (WorkspaceError) if a required section is missing — the parse
    must not lie about what a stage declares.
    """
    meta, body = _split_frontmatter(text)
    secs = _sections(body)

    stage_label = meta.get("stage") or Path(path).parent.name
    m = _STAGE_DIR_RE.match(stage_label)
    order = int(m.group(1)) if m else 0

    for required in ("inputs", "process", "outputs"):
        if required not in secs:
            raise WorkspaceError(
                f"stage CONTEXT.md missing required '## {required.title()}' "
                f"section: {path}"
            )

    inputs = [
        StageInput(
            source=r[0] if len(r) > 0 else "",
            location=r[1] if len(r) > 1 else "",
            scope=r[2] if len(r) > 2 else "full",
            why=r[3] if len(r) > 3 else "",
        )
        for r in _table_rows(secs["inputs"])
    ]
    outputs = [
        StageOutput(
            name=r[0] if len(r) > 0 else "",
            location=r[1] if len(r) > 1 else "",
            fmt=r[2] if len(r) > 2 else "markdown",
        )
        for r in _table_rows(secs["outputs"])
    ]
    process = [
        m2.group(1).strip()
        for line in secs["process"]
        if (m2 := _PROCESS_STEP_RE.match(line))
    ]

    return StageContract(
        stage_id=stage_label,
        order=order,
        type=meta.get("type", "stage"),
        agent_role=meta.get("agent"),
        title=meta.get("title", ""),
        inputs=inputs,
        process=process,
        outputs=outputs,
        path=path,
        contract_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


# ── workspace loading ──────────────────────────────────────────────────────


def load_workspace(root: str | Path) -> StageWorkspace:
    """Load a workspace: parse every ``stages/NN-name/CONTEXT.md``.

    Layout: ``<root>/stages/<NN-name>/CONTEXT.md``. Stages are returned sorted
    by their numeric order.
    """
    root_path = Path(root).resolve()
    stages_dir = root_path / "stages"
    if not stages_dir.is_dir():
        raise WorkspaceError(f"workspace has no stages/ directory: {root_path}")

    contracts: list[StageContract] = []
    for child in sorted(stages_dir.iterdir()):
        if not child.is_dir() or not _STAGE_DIR_RE.match(child.name):
            continue
        ctx = child / "CONTEXT.md"
        if not ctx.is_file():
            raise WorkspaceError(f"stage folder missing CONTEXT.md: {child}")
        contracts.append(parse_context_md(ctx.read_text(encoding="utf-8"), str(ctx)))

    if not contracts:
        raise WorkspaceError(f"workspace has no numbered stage folders: {stages_dir}")

    contracts.sort(key=lambda c: c.order)
    return StageWorkspace(root=str(root_path), stages=contracts)


def _within(root: Path, candidate: Path) -> bool:
    """True if *candidate* resolves inside *root* (path-traversal guard)."""
    try:
        candidate.resolve().relative_to(root)
        return True
    except ValueError:
        return False


def _upstream_stage_ids(contract: StageContract, by_id: dict[str, StageContract]) -> list[str]:
    """Stage ids whose output/ dir is referenced by this stage's Inputs (explicit edges)."""
    ups: list[str] = []
    for inp in contract.inputs:
        loc = inp.location.replace("\\", "/")
        for other_id in by_id:
            if other_id == contract.stage_id:
                continue
            # An input that points into "../<other>/..." is a real data edge.
            if f"/{other_id}/" in loc or loc.startswith(f"../{other_id}"):
                if other_id not in ups:
                    ups.append(other_id)
    return ups


def derive_dependencies(ws: StageWorkspace) -> dict[str, list[str]]:
    """The stage-id dependency graph: {stage_id: [upstream stage_ids]}.

    Single source of the DAG, used by BOTH to_tasks() (Task.depends_on) and the
    executor (run_workspace ordering). Rules, in order:
      1. Explicit — depend on any stage whose output/ this stage lists as input.
      2. Fallback — otherwise depend on ALL stages at the immediately-lower order
         (ICM's numeric default). Preserves same-order fan-out: two order-2 stages
         with no explicit sibling input both depend on order-1, never on each other.

    Fails closed (WorkspaceError) on: a duplicate stage_id, an input that escapes
    the workspace, a self-dependency, or a dependency cycle.
    """
    root = Path(ws.root).resolve()

    # Duplicate stage_id guard — two folders sharing a `stage:` would otherwise
    # collapse onto one identifier, silently merging their deps and receipts.
    seen: set[str] = set()
    for c in ws.stages:
        if c.stage_id in seen:
            raise WorkspaceError(
                f"duplicate stage_id '{c.stage_id}' — stage identifiers must be unique"
            )
        seen.add(c.stage_id)
    by_id = {c.stage_id: c for c in ws.stages}

    # Path-traversal guard: every input must resolve inside the workspace.
    for c in ws.stages:
        base = Path(c.path).parent
        for inp in c.inputs:
            if inp.location and not _within(root, base / inp.location):
                raise WorkspaceError(
                    f"stage '{c.stage_id}' input escapes workspace: {inp.location}"
                )

    orders = sorted({c.order for c in ws.stages})

    def _prev_order_ids(order: int) -> list[str]:
        lower = [o for o in orders if o < order]
        if not lower:
            return []
        target = max(lower)
        return [c.stage_id for c in ws.stages if c.order == target]

    deps: dict[str, list[str]] = {}
    for c in ws.stages:
        ups = _upstream_stage_ids(c, by_id)
        if not ups:
            ups = _prev_order_ids(c.order)  # same-order fan-out preserved
        if c.stage_id in ups:
            raise WorkspaceError(f"stage '{c.stage_id}' depends on itself")
        deps[c.stage_id] = ups

    _assert_acyclic(deps)
    return deps


def to_tasks(ws: StageWorkspace) -> list[Task]:
    """Map a workspace to Task objects with depends_on edges.

    The folder is the source of the DAG; TaskBoard is the executor of the DAG.
    Raises WorkspaceError per derive_dependencies (dup id / escape / cycle).
    """
    deps = derive_dependencies(ws)
    id_to_task: dict[str, str] = {}
    tasks: list[Task] = []

    for c in ws.stages:
        t = Task(
            title=c.title or c.stage_id,
            description=c.title or c.stage_id,
            created_by="fs_substrate",
            metadata={
                "stage_id": c.stage_id,
                "stage_contract_sha256": c.contract_sha256,
                "agent_role": c.agent_role or "",
                "stage_order": c.order,
            },
        )
        id_to_task[c.stage_id] = t.id
        tasks.append(t)

    for c, t in zip(ws.stages, tasks):
        t.depends_on = [id_to_task[u] for u in deps[c.stage_id] if u in id_to_task]
    return tasks


def topological_order(
    ws: StageWorkspace, deps: dict[str, list[str]] | None = None
) -> list[StageContract]:
    """Stage contracts in dependency order (every upstream before its dependents)."""
    deps = deps if deps is not None else derive_dependencies(ws)
    by_id = {c.stage_id: c for c in ws.stages}
    state: dict[str, int] = {}
    order: list[str] = []

    def visit(sid: str) -> None:
        if state.get(sid) == 2:
            return
        if state.get(sid) == 1:
            return  # a cycle would already have been rejected by derive_dependencies
        state[sid] = 1
        for up in deps.get(sid, ()):
            visit(up)
        state[sid] = 2
        order.append(sid)

    for c in ws.stages:
        visit(c.stage_id)
    return [by_id[sid] for sid in order if sid in by_id]


def _assert_acyclic(deps: dict[str, list[str]]) -> None:
    """Raise WorkspaceError if the stage-id dependency graph has a cycle."""
    state: dict[str, int] = {}  # 0=unseen,1=visiting,2=done

    def visit(node: str) -> None:
        if state.get(node) == 2:
            return
        if state.get(node) == 1:
            raise WorkspaceError(f"dependency cycle through stage {node}")
        state[node] = 1
        for dep in deps.get(node, ()):
            visit(dep)
        state[node] = 2

    for node in deps:
        visit(node)
