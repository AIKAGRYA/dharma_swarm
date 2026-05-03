"""Memory Census Engine.

This module measures memory surfaces across dharma_swarm, ~/.dharma,
~/.claude, ~/.smriti, MCP/plugin state, and dormant skill promises. It is
read-only except for the caller-selected report output.

Default CLI:
    python -m dharma_swarm.memory_census scan
    python scripts/memory_census.py scan --json-only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

CENSUS_VERSION = 2

KNOWN_SUBSTRATES = (
    "python",
    "jsonl",
    "sqlite",
    "markdown",
    "json",
    "json_canvas",
    "lancedb",
    "mcp",
    "plugin",
    "directory",
    "log",
    "parquet",
    "unknown",
)

KNOWN_ROLES = (
    "write_authority",
    "projection_index",
    "distiller_consolidator",
    "agent_local",
    "human_curated",
    "external_mcp_plugin",
    "dormant_promise",
    "unknown",
)

# Backwards-compatible name from the v0 tests/report.
KNOWN_CLASSES = KNOWN_ROLES

VERIFICATION_STATUSES = ("verified", "probable", "stale", "false", "needs_owner")
GOVERNANCE_STATUSES = ("governed", "partially_governed", "ungoverned", "unknown")
POLICY_STATUSES = ("present", "absent", "unknown")
AUTHORITY_LEVELS = ("human", "system", "agent", "external", "unknown")
RISK_LEVELS = ("critical", "high", "medium", "low")


@dataclass(frozen=True)
class Evidence:
    """One factual support item for a census row."""

    kind: str
    source: str
    note: str = ""


@dataclass(frozen=True)
class MemorySurface:
    """One durable memory surface in the ecosystem."""

    surface_id: str
    name: str
    paths: list[str]
    substrate: str
    role: str
    authority_level: str
    owner_module: str | None
    runtime_owner: str | None
    read_callers: list[str] = field(default_factory=list)
    write_callers: list[str] = field(default_factory=list)
    size_bytes: int = 0
    last_modified: str = ""
    governance_status: str = "unknown"
    decay_policy: str = "unknown"
    provenance_policy: str = "unknown"
    verification_status: str = "needs_owner"
    risk: str = "low"
    evidence: list[Evidence] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def path(self) -> str:
        """Compatibility for v0 callers."""
        return self.paths[0] if self.paths else ""

    @property
    def class_hint(self) -> str:
        return self.role

    @property
    def risk_hint(self) -> str:
        return self.risk

    @property
    def owner_module_hint(self) -> str | None:
        return self.owner_module

    @property
    def in_state_dir_owners(self) -> bool:
        return self.governance_status in {"governed", "partially_governed"}

    @property
    def in_semgrep_allowlist(self) -> bool:
        return any(e.kind == "semgrep_allowlist" for e in self.evidence)

    @property
    def reconciliation_tag(self) -> str:
        return self.verification_status

    def to_dict(self) -> dict:
        return asdict(self)


def _surface_id(path: str) -> str:
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]


def _display_name(path: Path) -> str:
    if path.name:
        return path.name
    return str(path)


def _detect_substrate(path: Path) -> str:
    if path.is_dir() and path.name.lower() == "lancedb":
        return "lancedb"
    if path.name == ".mcp.json":
        return "mcp"
    if path.is_dir() and "plugins" in path.parts:
        return "plugin"
    if path.is_dir():
        return "directory"
    suffix = path.suffix.lower()
    return {
        ".py": "python",
        ".jsonl": "jsonl",
        ".db": "sqlite",
        ".sqlite": "sqlite",
        ".sqlite3": "sqlite",
        ".md": "markdown",
        ".json": "json",
        ".canvas": "json_canvas",
        ".parquet": "parquet",
        ".log": "log",
    }.get(suffix, "unknown")


def _last_modified(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except (OSError, PermissionError):
        return ""


def _size_bytes(path: Path) -> int:
    """Measure size without opening content. Uses du for large directories."""
    try:
        if path.is_file():
            return path.stat().st_size
        if path.is_dir():
            result = subprocess.run(
                ["du", "-sk", str(path)],
                capture_output=True,
                check=False,
                text=True,
                timeout=20,
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.split()[0]) * 1024
    except (OSError, PermissionError, subprocess.SubprocessError, ValueError):
        pass
    return _fallback_dir_size(path)


def _fallback_dir_size(path: Path) -> int:
    total = 0
    try:
        for sub in path.rglob("*"):
            try:
                if sub.is_file():
                    total += sub.stat().st_size
            except (OSError, PermissionError):
                continue
    except (OSError, PermissionError):
        return 0
    return total


def _load_state_dir_owners(repo_root: Path) -> set[str]:
    doc = repo_root / "docs" / "governance" / "STATE_DIR_OWNERS.md"
    if not doc.exists():
        return set()
    owners: set[str] = set()
    for line in doc.read_text(encoding="utf-8").splitlines():
        owners.update(re.findall(r"`(dharma_swarm/[\w./_-]+\.py)`", line))
    return owners


def _load_semgrep_allowlist(repo_root: Path) -> set[str]:
    yml = repo_root / ".semgrep" / "dharma-anti-slop.yml"
    if not yml.exists():
        return set()
    paths: set[str] = set()
    for line in yml.read_text(encoding="utf-8").splitlines():
        match = re.search(r'-\s+"(dharma_swarm/[\w./_-]+\.py)"', line)
        if match:
            paths.add(match.group(1))
    return paths


_DHARMA_LITERAL = re.compile(r'Path\.home\(\)\s*/\s*"\.dharma"')


def _find_dharma_writers(repo_root: Path) -> dict[str, str]:
    """Map literal ~/.dharma path tails to first repo module writer."""
    writers: dict[str, str] = {}
    pkg_root = repo_root / "dharma_swarm"
    if not pkg_root.exists():
        return writers
    for py in sorted(pkg_root.rglob("*.py")):
        try:
            text = py.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not _DHARMA_LITERAL.search(text):
            continue
        rel_owner = str(py.relative_to(repo_root))
        for match in re.finditer(
            r'Path\.home\(\)\s*/\s*"\.dharma"((?:\s*/\s*"[^"]+")+)', text
        ):
            tail = "/".join(re.findall(r'"([^"]+)"', match.group(1)))
            writers.setdefault(tail, rel_owner)
            if "/" in tail:
                writers.setdefault(tail.split("/", 1)[0], rel_owner)
    return writers


def _repo_python_files(repo_root: Path) -> list[Path]:
    pkg_root = repo_root / "dharma_swarm"
    if not pkg_root.exists():
        return []
    return sorted(pkg_root.rglob("*.py"))


def _find_call_sites(
    repo_root: Path,
    needles: Iterable[str],
    *,
    skip: Path | None = None,
    limit: int = 25,
) -> list[str]:
    hits: list[str] = []
    needle_set = {n for n in needles if n}
    if not needle_set:
        return hits
    for py in _repo_python_files(repo_root):
        if skip is not None and py == skip:
            continue
        try:
            lines = py.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for idx, line in enumerate(lines, start=1):
            if any(n in line for n in needle_set):
                hits.append(f"{py.relative_to(repo_root)}:{idx}")
                if len(hits) >= limit:
                    return hits
                break
    return hits


_PYTHON_ROLE_HINTS = (
    (re.compile(r"class\s+\w*(Store|Ledger|Registry)\b"), "write_authority"),
    (re.compile(r"class\s+\w*(Index|Retriever|Cache)\b"), "projection_index"),
    (re.compile(r"\bdef\s+(decay|revive|prune|consolidate)\b"), "distiller_consolidator"),
    (re.compile(r"class\s+\w*Memory\b"), "agent_local"),
)


def _classify_python(text: str, path: Path | None = None) -> str:
    name = path.name.lower() if path else ""
    if name.startswith("ginko_"):
        return "write_authority"
    for pattern, role in _PYTHON_ROLE_HINTS:
        if pattern.search(text):
            return role
    return "unknown"


def _policy_status(text: str, words: Iterable[str]) -> str:
    lowered = text.lower()
    return "present" if any(word in lowered for word in words) else "absent"


def _governance_status(owner: str | None, owners: set[str], allowlist: set[str]) -> str:
    if owner and owner in owners and owner in allowlist:
        return "governed"
    if owner and (owner in owners or owner in allowlist):
        return "partially_governed"
    if owner:
        return "ungoverned"
    return "unknown"


def _verification_status(
    *,
    path_exists: bool,
    role: str,
    governance: str,
    owner: str | None,
) -> str:
    if not path_exists:
        return "false"
    if role == "dormant_promise":
        return "stale"
    if role in {"write_authority", "projection_index"} and not owner:
        return "needs_owner"
    if governance == "governed":
        return "verified"
    return "probable"


def _risk_for(surface: MemorySurface) -> str:
    gb = surface.size_bytes / (1024**3)
    ungoverned = surface.governance_status in {"ungoverned", "unknown"}
    if gb >= 50 and ungoverned:
        return "critical"
    if gb >= 10 and ungoverned:
        return "high"
    if surface.role == "write_authority" and ungoverned:
        return "high"
    if surface.role == "dormant_promise":
        return "medium"
    if surface.role == "human_curated" and surface.governance_status != "governed":
        return "medium"
    if surface.size_bytes >= 100 * 1024**2 and ungoverned:
        return "medium"
    return "low"


_MEMORY_FILENAME_TOKENS = (
    "memory",
    "store",
    "ledger",
    "archive",
    "log",
    "journal",
    "cache",
    "buffer",
    "history",
    "registry",
    "recorder",
    "recall",
    "remember",
    "replay",
    "episode",
    "stigmergy",
    "trace",
    "witness",
    "digest",
    "ginko",
    "vector_store",
    "graph",
    "lattice",
    "palace",
)


def _is_python_memory_candidate(path: Path) -> bool:
    return path.suffix == ".py" and any(t in path.name.lower() for t in _MEMORY_FILENAME_TOKENS)


def _walk_python_memory_modules(
    pkg_root: Path,
    *,
    extra_owners: Iterable[str] = (),
) -> Iterator[Path]:
    if not pkg_root.exists():
        return
    repo_root = pkg_root.parent
    extra_set = set(extra_owners)
    for py in sorted(pkg_root.rglob("*.py")):
        rel = str(py.relative_to(repo_root))
        if _is_python_memory_candidate(py) or rel in extra_set:
            yield py


_DHARMA_DEEP_PATTERNS = (
    "*.jsonl",
    "*.json",
    "*.db",
    "*.md",
    "*.canvas",
    "**/marks.jsonl",
    "**/register_marks.jsonl",
    "**/archive.jsonl",
    "**/experiments.jsonl",
    "**/meta_archive.jsonl",
    "**/witness_*.jsonl",
    "**/_pending.jsonl",
    "**/mutations.jsonl",
)


def _walk_dharma_surfaces(dharma_root: Path) -> Iterator[Path]:
    if not dharma_root.exists():
        return
    seen: set[Path] = set()
    for entry in sorted(dharma_root.iterdir()):
        if entry.name.startswith("."):
            continue
        seen.add(entry)
        yield entry
    for pattern in _DHARMA_DEEP_PATTERNS:
        for match in sorted(dharma_root.glob(pattern)):
            if match not in seen:
                seen.add(match)
                yield match


def _walk_claude_surfaces(claude_root: Path) -> Iterator[Path]:
    candidates = [
        claude_root / ".mcp.json",
        claude_root / "cabinet",
        claude_root / "agent-memory",
        claude_root / "projects" / "-Users-dhyana" / "memory",
        claude_root / "homunculus",
        claude_root / "plugins" / "data",
        claude_root / "plugins" / "marketplaces",
        claude_root / "rules",
        claude_root / "sessions",
    ]
    for candidate in candidates:
        if candidate.exists():
            yield candidate
    yield from _walk_skill_promises(claude_root / "skills")


_DORMANT_SKILL_PATTERNS = (
    re.compile(r"DharmicMem0Layer", re.IGNORECASE),
    re.compile(r"\bclass\s+HopRAG\b|\bHopRAG\b", re.IGNORECASE),
    re.compile(r"capability_registry", re.IGNORECASE),
)


def _walk_skill_promises(skills_root: Path) -> Iterator[Path]:
    if not skills_root.exists():
        return
    for skill in sorted(skills_root.iterdir()):
        spec = skill / "SKILL.md"
        if not spec.exists():
            continue
        skill_name = skill.name.lower()
        if any(token in skill_name for token in ("mem0", "agentic-rag", "a2a")):
            yield skill
            continue
        try:
            text = spec.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if any(pattern.search(text) for pattern in _DORMANT_SKILL_PATTERNS):
            yield skill


def _walk_smriti(smriti_root: Path) -> Iterator[Path]:
    if not smriti_root.exists():
        return
    db = smriti_root / "smriti.db"
    if db.exists():
        yield db
    else:
        yield smriti_root


def _dharma_owner_for(path: Path, *, home: Path, writers: dict[str, str]) -> str | None:
    dharma_root = home / ".dharma"
    try:
        rel = path.relative_to(dharma_root)
    except ValueError:
        return None
    candidates = [str(rel), rel.parts[0] if rel.parts else ""]
    if len(rel.parts) > 1:
        candidates.append("/".join(rel.parts[:2]))
    if path.is_file() and len(rel.parts) > 1:
        candidates.append(str(rel.parent))
    for candidate in candidates:
        if candidate in writers:
            return writers[candidate]
    return None


def _make_python_surface(
    path: Path,
    *,
    repo_root: Path,
    owners: set[str],
    allowlist: set[str],
) -> MemorySurface:
    rel = str(path.relative_to(repo_root))
    evidence = [Evidence("path_exists", str(path), "python memory candidate")]
    notes: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = ""
        notes.append("could_not_read_python_source")
    role = _classify_python(text, path)
    if rel in owners:
        evidence.append(Evidence("state_dir_owner", f"docs/governance/STATE_DIR_OWNERS.md", rel))
    if rel in allowlist:
        evidence.append(Evidence("semgrep_allowlist", ".semgrep/dharma-anti-slop.yml", rel))
    dotted = rel.removesuffix(".py").replace("/", ".")
    callers = _find_call_sites(repo_root, {rel, dotted, path.stem}, skip=path)
    governance = _governance_status(rel, owners, allowlist)
    surface = MemorySurface(
        surface_id=_surface_id(str(path.resolve())),
        name=_display_name(path),
        paths=[str(path.resolve())],
        substrate="python",
        role=role,
        authority_level="system",
        owner_module=rel,
        runtime_owner=None,
        read_callers=callers,
        write_callers=callers,
        size_bytes=_size_bytes(path),
        last_modified=_last_modified(path),
        governance_status=governance,
        decay_policy=_policy_status(text, {"decay", "prune", "forget", "ttl"}),
        provenance_policy=_policy_status(text, {"provenance", "source_ref", "signature"}),
        verification_status=_verification_status(
            path_exists=True, role=role, governance=governance, owner=rel
        ),
        evidence=evidence,
        notes=notes,
    )
    return replace(surface, risk=_risk_for(surface))


def _make_runtime_surface(
    path: Path,
    *,
    repo_root: Path,
    home: Path,
    owners: set[str],
    allowlist: set[str],
    writers: dict[str, str],
) -> MemorySurface:
    abs_path = str(path.resolve())
    substrate = _detect_substrate(path)
    evidence = [Evidence("path_exists", abs_path, "runtime memory surface")]
    notes: list[str] = []
    owner = _dharma_owner_for(path, home=home, writers=writers)
    if owner is None:
        notes.append("owner_unresolved")
    elif owner in owners:
        evidence.append(Evidence("state_dir_owner", "docs/governance/STATE_DIR_OWNERS.md", owner))
    if owner in allowlist:
        evidence.append(Evidence("semgrep_allowlist", ".semgrep/dharma-anti-slop.yml", owner))

    role = "write_authority" if owner else "unknown"
    authority = "system" if owner else "unknown"
    runtime_owner = None
    if path.name == "lancedb":
        role = "projection_index"
        runtime_owner = "unknown_lancedb_writer"
        notes.append("critical_claim_verified:lancedb_store_present")
    elif path.name == "conversation_log":
        role = "write_authority"
        runtime_owner = "conversation_hooks"
    elif path.name == "knowledge":
        role = "write_authority"
        runtime_owner = "chetana"
    elif path.name == "ginko":
        role = "write_authority"
        runtime_owner = "ginko"

    callers = _find_call_sites(repo_root, {str(path.relative_to(home)) if home in path.parents else path.name})
    governance = _governance_status(owner, owners, allowlist)
    surface = MemorySurface(
        surface_id=_surface_id(abs_path),
        name=_display_name(path),
        paths=[abs_path],
        substrate=substrate,
        role=role,
        authority_level=authority,
        owner_module=owner,
        runtime_owner=runtime_owner,
        read_callers=callers,
        write_callers=callers if owner else [],
        size_bytes=_size_bytes(path),
        last_modified=_last_modified(path),
        governance_status=governance,
        decay_policy="unknown",
        provenance_policy="unknown",
        verification_status=_verification_status(
            path_exists=True, role=role, governance=governance, owner=owner
        ),
        evidence=evidence,
        notes=notes,
    )
    return replace(surface, risk=_risk_for(surface))


def _make_claude_surface(path: Path, *, home: Path) -> MemorySurface:
    abs_path = str(path.resolve())
    evidence = [Evidence("path_exists", abs_path, "Claude Code memory surface")]
    role = "agent_local"
    authority = "agent"
    runtime_owner = "claude_code"
    substrate = _detect_substrate(path)
    notes: list[str] = []

    if path.name == "cabinet":
        role = "human_curated"
        authority = "human"
        runtime_owner = "dhyana"
        md_count = sum(1 for _ in path.rglob("*.md")) if path.exists() else 0
        evidence.append(Evidence("size_scan", abs_path, f"cabinet_markdown_count={md_count}"))
        if md_count != 352:
            notes.append(f"prior_claim_false:cabinet_markdown_count_352 actual={md_count}")
    elif path.name in {"data", "marketplaces"} and "plugins" in path.parts:
        role = "external_mcp_plugin"
        authority = "external"
        runtime_owner = "claude_plugins"
    elif path.name == ".mcp.json":
        role = "external_mcp_plugin"
        authority = "external"
        runtime_owner = "mcp_config"
        evidence.append(Evidence("mcp_config", abs_path, "mounted memory providers may exist"))
    elif path.parent.name == "skills":
        role = "dormant_promise"
        authority = "external"
        runtime_owner = "skill_spec"
        evidence.append(Evidence("skill_spec", str(path / "SKILL.md"), "persistent memory promise"))

    surface = MemorySurface(
        surface_id=_surface_id(abs_path),
        name=_display_name(path),
        paths=[abs_path],
        substrate=substrate,
        role=role,
        authority_level=authority,
        owner_module=None,
        runtime_owner=runtime_owner,
        size_bytes=_size_bytes(path),
        last_modified=_last_modified(path),
        governance_status="ungoverned",
        decay_policy="unknown",
        provenance_policy="unknown",
        verification_status=_verification_status(
            path_exists=True, role=role, governance="ungoverned", owner=runtime_owner
        ),
        evidence=evidence,
        notes=notes,
    )
    return replace(surface, risk=_risk_for(surface))


def _make_smriti_surface(path: Path) -> MemorySurface:
    abs_path = str(path.resolve())
    evidence = [Evidence("path_exists", abs_path, "smriti memory substrate")]
    if path.suffix == ".db":
        evidence.append(Evidence("sqlite_schema", abs_path, "schema inspection deferred to DB tools"))
    surface = MemorySurface(
        surface_id=_surface_id(abs_path),
        name=_display_name(path),
        paths=[abs_path],
        substrate=_detect_substrate(path),
        role="write_authority",
        authority_level="system",
        owner_module=None,
        runtime_owner="smriti_skill",
        size_bytes=_size_bytes(path),
        last_modified=_last_modified(path),
        governance_status="ungoverned",
        decay_policy="unknown",
        provenance_policy="unknown",
        verification_status="needs_owner",
        evidence=evidence,
        notes=["separate_memory_authority"],
    )
    return replace(surface, risk=_risk_for(surface))


def scan(*, repo_root: Path | None = None, home: Path | None = None) -> list[MemorySurface]:
    """Return current memory-surface inventory without mutating scanned stores."""
    repo_root = (repo_root or Path(__file__).resolve().parents[1]).resolve()
    home = (home or Path.home()).resolve()
    owners = _load_state_dir_owners(repo_root)
    allowlist = _load_semgrep_allowlist(repo_root)
    writers = _find_dharma_writers(repo_root)

    surfaces: list[MemorySurface] = []
    seen: set[str] = set()

    def add(path: Path, maker) -> None:
        key = str(path.resolve())
        if key in seen:
            return
        seen.add(key)
        try:
            surfaces.append(maker(path))
        except Exception as exc:  # noqa: BLE001 - census should not abort on one bad row
            surfaces.append(
                MemorySurface(
                    surface_id=_surface_id(key),
                    name=_display_name(path),
                    paths=[key],
                    substrate="unknown",
                    role="unknown",
                    authority_level="unknown",
                    owner_module=None,
                    runtime_owner=None,
                    verification_status="needs_owner",
                    risk="medium",
                    evidence=[Evidence("scan_error", key, repr(exc))],
                )
            )

    extra_owners = set(writers.values()) | owners | allowlist
    for py in _walk_python_memory_modules(repo_root / "dharma_swarm", extra_owners=extra_owners):
        add(py, lambda p: _make_python_surface(p, repo_root=repo_root, owners=owners, allowlist=allowlist))
    for path in _walk_dharma_surfaces(home / ".dharma"):
        add(
            path,
            lambda p: _make_runtime_surface(
                p,
                repo_root=repo_root,
                home=home,
                owners=owners,
                allowlist=allowlist,
                writers=writers,
            ),
        )
    for path in _walk_claude_surfaces(home / ".claude"):
        add(path, lambda p: _make_claude_surface(p, home=home))
    for path in _walk_smriti(home / ".smriti"):
        add(path, _make_smriti_surface)

    return sorted(surfaces, key=lambda s: (s.risk, s.surface_id))


def build_inventory(surfaces: list[MemorySurface], *, scanned_at: str | None = None) -> dict:
    scanned_at = scanned_at or datetime.now(timezone.utc).isoformat()
    surfaces_sorted = sorted(surfaces, key=lambda s: s.surface_id)
    counts: dict[str, dict[str, int]] = {"role": {}, "risk": {}, "verification_status": {}}
    for surface in surfaces_sorted:
        counts["role"][surface.role] = counts["role"].get(surface.role, 0) + 1
        counts["risk"][surface.risk] = counts["risk"].get(surface.risk, 0) + 1
        status = surface.verification_status
        counts["verification_status"][status] = counts["verification_status"].get(status, 0) + 1
    return {
        "_meta": {
            "census_version": CENSUS_VERSION,
            "scanned_at": scanned_at,
            "surface_count": len(surfaces_sorted),
            "counts": counts,
        },
        "surfaces": [surface.to_dict() for surface in surfaces_sorted],
    }


def write_inventory(
    surfaces: list[MemorySurface],
    output_dir: Path,
    *,
    json_only: bool = False,
    scanned_at: str | None = None,
) -> tuple[Path, Path | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory = build_inventory(surfaces, scanned_at=scanned_at)
    json_path = output_dir / "memory_surface_inventory.json"
    json_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path = None
    if not json_only:
        md_path = output_dir / "memory_surface_inventory.md"
        md_path.write_text(render_markdown(inventory), encoding="utf-8")
    return json_path, md_path


def render_markdown(inventory: dict) -> str:
    meta = inventory["_meta"]
    lines = [
        "# Memory Surface Inventory",
        "",
        f"- Census version: {meta['census_version']}",
        f"- Scanned at: {meta['scanned_at']}",
        f"- Surface count: {meta['surface_count']}",
        "",
        "## Highest Risk",
        "",
        "| Risk | Role | Verification | Name | Owner | Size |",
        "| --- | --- | --- | --- | --- | ---: |",
    ]
    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    rows = sorted(
        inventory["surfaces"],
        key=lambda s: (risk_order.get(s["risk"], 9), s["name"], s["surface_id"]),
    )
    for row in rows[:80]:
        owner = row.get("owner_module") or row.get("runtime_owner") or ""
        lines.append(
            f"| {row['risk']} | {row['role']} | {row['verification_status']} "
            f"| {row['name']} | {owner} | {row['size_bytes']} |"
        )
    lines.append("")
    return "\n".join(lines)


def default_output_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".dharma" / "meta"


def default_output_path(home: Path | None = None) -> Path:
    """Compatibility path for v0 JSONL callers."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    return (home or Path.home()) / ".dharma" / "meta" / "memory_census" / f"{stamp}.jsonl"


def write_jsonl(surfaces: list[MemorySurface], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"_meta": build_inventory(surfaces)["_meta"]}, sort_keys=True) + "\n")
        for surface in sorted(surfaces, key=lambda s: s.surface_id):
            f.write(json.dumps(surface.to_dict(), sort_keys=True) + "\n")
    return output_path


def _load_run(path: Path) -> dict[str, dict]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        payload = json.loads(text)
        return {row["surface_id"]: row for row in payload.get("surfaces", [])}
    out: dict[str, dict] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if "surface_id" in row:
            out[row["surface_id"]] = row
    return out


def diff_runs(prior_path: Path, current_path: Path) -> dict[str, list[str]]:
    prior = _load_run(prior_path)
    current = _load_run(current_path)
    common = set(prior) & set(current)
    changed_size = sorted(
        sid for sid in common if prior[sid].get("size_bytes") != current[sid].get("size_bytes")
    )
    changed_risk = sorted(sid for sid in common if prior[sid].get("risk") != current[sid].get("risk"))
    return {
        "added": sorted(set(current) - set(prior)),
        "removed": sorted(set(prior) - set(current)),
        "changed_size": changed_size,
        "changed_risk": changed_risk,
    }


def _critical_unknown_owner(surfaces: list[MemorySurface]) -> list[MemorySurface]:
    return [
        s
        for s in surfaces
        if s.risk == "critical" and s.verification_status == "needs_owner"
    ]


def _cmd_scan(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo).resolve() if args.repo else None
    home = Path(args.home).resolve() if args.home else None
    surfaces = scan(repo_root=repo_root, home=home)
    if args.output and str(args.output).endswith(".jsonl"):
        jsonl = write_jsonl(surfaces, Path(args.output).resolve())
        print(f"surfaces: {len(surfaces)}")
        print(f"output: {jsonl}")
    else:
        output_dir = Path(args.output_dir).resolve() if args.output_dir else default_output_dir(home)
        json_path, md_path = write_inventory(surfaces, output_dir, json_only=args.json_only)
        print(f"surfaces: {len(surfaces)}")
        print(f"json: {json_path}")
        if md_path:
            print(f"markdown: {md_path}")
    if args.fail_on_critical_unknown_owner:
        blockers = _critical_unknown_owner(surfaces)
        if blockers:
            print(
                "critical unknown-owner surfaces: "
                + ", ".join(surface.name for surface in blockers),
                file=sys.stderr,
            )
            return 2
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    result = diff_runs(Path(args.prior).resolve(), Path(args.current).resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="memory_census")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="Scan memory surfaces and emit inventory.")
    p_scan.add_argument("--repo", "--repo-root", dest="repo", default=None)
    p_scan.add_argument("--home", default=None)
    p_scan.add_argument("--output-dir", default=None)
    p_scan.add_argument("--output", default=None, help="Compatibility JSONL path when suffix is .jsonl.")
    p_scan.add_argument("--json-only", action="store_true")
    p_scan.add_argument("--fail-on-critical-unknown-owner", action="store_true")
    p_scan.set_defaults(func=_cmd_scan)

    p_diff = sub.add_parser("diff", help="Compare two inventory JSON/JSONL runs.")
    p_diff.add_argument("prior")
    p_diff.add_argument("current")
    p_diff.set_defaults(func=_cmd_diff)

    ns = parser.parse_args(argv)
    return ns.func(ns)


if __name__ == "__main__":
    sys.exit(main())
