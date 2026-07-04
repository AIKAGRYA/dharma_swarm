"""AST discovery helpers for memory-like write paths."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.memory_kernel.writer_models import (
    DiscoveredWriteStatus,
    DiscoveryTriageCategory,
    MemoryWriterSpec,
)


def _symbol_exists(source_path: Path, symbol: str) -> bool:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    parts = symbol.split(".")
    if len(parts) == 1:
        return any(_node_name(node) == parts[0] for node in ast.walk(tree))
    class_name, member_name = parts[0], parts[1]
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return any(_node_name(child) == member_name for child in node.body)
    return False


def _node_name(node: ast.AST) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    return None


@dataclass(frozen=True)
class _DiscoveredWriteCandidate:
    source_path: str
    symbol: str
    line: int
    operation: str
    target: str
    mode: str
    reason: str


class _MemoryWriteVisitor(ast.NodeVisitor):
    def __init__(self, *, source_path: Path, repo_root: Path) -> None:
        self.source_path = source_path
        self.repo_root = repo_root
        self.discovered: list[_DiscoveredWriteCandidate] = []
        self._class_stack: list[str] = []
        self._function_stack: list[str] = []
        self._memory_var_stack: list[dict[str, str]] = []
        self._sql_write_stack: list[bool] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_stack.append(node.name)
        self._memory_var_stack.append({})
        self._sql_write_stack.append(_contains_sql_write(node))
        self.generic_visit(node)
        self._sql_write_stack.pop()
        self._memory_var_stack.pop()
        self._function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function_stack.append(node.name)
        self._memory_var_stack.append({})
        self._sql_write_stack.append(_contains_sql_write(node))
        self.generic_visit(node)
        self._sql_write_stack.pop()
        self._memory_var_stack.pop()
        self._function_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        value_expr = _safe_unparse(node.value)
        if self._memory_var_stack and _is_memory_like_expr(value_expr):
            for target in node.targets:
                for name in _assigned_names(target):
                    self._memory_var_stack[-1][name] = value_expr
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if (
            self._memory_var_stack
            and node.value is not None
            and _is_memory_like_expr(_safe_unparse(node.value))
        ):
            value_expr = _safe_unparse(node.value)
            for name in _assigned_names(node.target):
                self._memory_var_stack[-1][name] = value_expr
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        detected = _detect_memory_write_call(
            node,
            memory_vars=self._memory_vars(),
            sql_write_context=any(self._sql_write_stack),
        )
        if detected is not None:
            operation, mode, target, reason = detected
            self.discovered.append(
                _DiscoveredWriteCandidate(
                    source_path=_relative_path(self.source_path, self.repo_root),
                    symbol=self._symbol(),
                    line=int(getattr(node, "lineno", 0)),
                    operation=operation,
                    target=target,
                    mode=mode,
                    reason=reason,
                )
            )
        self.generic_visit(node)

    def _symbol(self) -> str:
        class_name = self._class_stack[-1] if self._class_stack else ""
        function_name = self._function_stack[-1] if self._function_stack else ""
        if class_name and function_name:
            return f"{class_name}.{function_name}"
        if function_name:
            return function_name
        if class_name:
            return class_name
        return "<module>"

    def _memory_vars(self) -> dict[str, str]:
        merged: dict[str, str] = {}
        for scope in self._memory_var_stack:
            merged.update(scope)
        return merged


def _detect_memory_write_call(
    node: ast.Call,
    *,
    memory_vars: dict[str, str],
    sql_write_context: bool,
) -> tuple[str, str, str, str] | None:
    call_name = _call_name(node.func)
    target = _safe_unparse(node)
    origin = _memory_var_origin(target, memory_vars)
    effective_target = f"{target} [origin: {origin}]" if origin else target
    mode = _call_mode(node, path_open=call_name.endswith(".open") and call_name != "open")
    memory_like = _is_memory_like_expr(target) or origin is not None
    if call_name in {"sqlite3.connect", "aiosqlite.connect"} and memory_like and sql_write_context:
        return (
            "sqlite_connect",
            "read_write",
            effective_target,
            "sqlite connection in function containing schema/write SQL",
        )
    if call_name in {"open", "aiofiles.open"} and _is_write_mode(mode) and memory_like:
        return (
            "file_open_write",
            mode or "unknown_write",
            effective_target,
            "file open with write/append mode on memory-like path expression",
        )
    if call_name.endswith(".open") and _is_write_mode(mode) and memory_like:
        return (
            "path_open_write",
            mode or "unknown_write",
            effective_target,
            "Path.open with write/append mode on memory-like path expression",
        )
    if (
        (call_name.endswith(".write_text") or call_name.endswith(".write_bytes"))
        and memory_like
    ):
        return (
            "path_write",
            "write",
            effective_target,
            "Path write helper on memory-like path expression",
        )
    return None


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _call_mode(node: ast.Call, *, path_open: bool = False) -> str:
    if path_open and node.args:
        value = _constant_string(node.args[0])
        if value:
            return value
    if len(node.args) >= 2:
        value = _constant_string(node.args[1])
        if value:
            return value
    for keyword in node.keywords:
        if keyword.arg == "mode":
            value = _constant_string(keyword.value)
            if value:
                return value
    return ""


def _constant_string(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _is_write_mode(mode: str) -> bool:
    return any(flag in mode for flag in ("a", "w", "x", "+"))


def _is_memory_like_expr(expr: str) -> bool:
    lowered = expr.lower()
    tokens = (
        ".dharma",
        "agent_memory",
        "codex",
        "conversation",
        "db_path",
        "default_",
        "knowledge",
        "log_dir",
        "memory",
        "ontology",
        "routing",
        "semantic",
        "smriti",
        "state",
        "telos",
        "vector",
        "witness",
        ".jsonl",
        ".sqlite",
        ".sqlite3",
        ".db",
    )
    return any(token in lowered for token in tokens)


def _contains_sql_write(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        call_name = _call_name(child.func)
        if not (
            call_name.endswith(".execute")
            or call_name.endswith(".executescript")
            or call_name in {"execute", "executescript"}
        ):
            continue
        sql = _first_sql_literal(child)
        if _is_sql_write(sql):
            return True
    return False


def _first_sql_literal(node: ast.Call) -> str:
    if not node.args:
        return ""
    arg = node.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    if isinstance(arg, ast.JoinedStr):
        return "".join(
            value.value for value in arg.values if isinstance(value, ast.Constant) and isinstance(value.value, str)
        )
    return ""


def _is_sql_write(sql: str) -> bool:
    normalized = " ".join(sql.lower().split())
    if not normalized:
        return False
    prefixes = (
        "alter ",
        "create ",
        "delete ",
        "drop ",
        "insert ",
        "pragma journal_mode",
        "replace ",
        "update ",
    )
    return normalized.startswith(prefixes) or any(
        token in normalized
        for token in (
            " insert into ",
            " create table ",
            " update ",
            " delete from ",
            " replace into ",
        )
    )


def _memory_var_origin(expr: str, memory_vars: dict[str, str]) -> str | None:
    for name, origin in memory_vars.items():
        if expr == name or expr.startswith(f"{name}."):
            return origin
    return None


def _assigned_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for element in target.elts:
            names.update(_assigned_names(element))
        return names
    return set()


def _safe_unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return node.__class__.__name__


def _matching_writer_ids(
    candidate: _DiscoveredWriteCandidate,
    registered: dict[str, tuple[MemoryWriterSpec, ...]],
) -> tuple[str, ...]:
    specs = registered.get(candidate.source_path, ())
    matches: list[str] = []
    for spec in specs:
        if _symbol_matches(candidate.symbol, spec.symbol):
            matches.append(spec.writer_id)
    return tuple(matches)


def _triage_discovered_write(
    candidate: _DiscoveredWriteCandidate,
    *,
    status: DiscoveredWriteStatus,
) -> tuple[DiscoveryTriageCategory, str]:
    source = candidate.source_path.lower()
    symbol = candidate.symbol.lower()
    target = candidate.target.lower()
    if status == DiscoveredWriteStatus.REGISTERED:
        return (
            DiscoveryTriageCategory.REGISTERED_MEMORY_WRITER,
            "matched an explicit MemoryWriterSpec",
        )
    if _is_test_or_experiment_source(source):
        return (
            DiscoveryTriageCategory.TEST_OR_EXPERIMENT,
            "test, smoke, experiment, or one-off validation surface",
        )
    if source.endswith("db_utils.py"):
        return (
            DiscoveryTriageCategory.READ_WRITE_HELPER,
            "shared database helper; classify callers rather than this helper alone",
        )
    if _is_generated_artifact_source(source, target):
        return (
            DiscoveryTriageCategory.GENERATED_ARTIFACT,
            "writes generated reports, manifests, handoffs, or derived files",
        )
    if _is_operational_state_source(source, symbol, target):
        return (
            DiscoveryTriageCategory.OPERATIONAL_STATE,
            "writes operational runtime/control state rather than semantic memory",
        )
    if _is_known_memory_writer_cluster(source, symbol, target):
        return (
            DiscoveryTriageCategory.MEMORY_WRITER_NEEDS_SPEC,
            "known memory/projection/witness writer cluster needs explicit writer spec",
        )
    if candidate.operation == "sqlite_connect":
        return (
            DiscoveryTriageCategory.SURFACE_NEEDS_REGISTRY,
            "SQLite write path needs surface classification or explicit exclusion",
        )
    if "witness" in target or "witness" in symbol or "jsonl" in target:
        return (
            DiscoveryTriageCategory.MEMORY_WRITER_NEEDS_SPEC,
            "append-style evidence/witness path needs explicit writer spec",
        )
    return (
        DiscoveryTriageCategory.OPERATIONAL_STATE,
        "file write looks operational/generated; review before excluding",
    )


def _is_test_or_experiment_source(source: str) -> bool:
    filename = source.rsplit("/", 1)[-1]
    return (
        source.startswith("tests/")
        or "/tests/" in source
        or source.startswith("scripts/experiments/")
        or "test" in filename
        or "smoke" in filename
        or "probe" in filename
        or "experiment" in filename
    )


def _is_generated_artifact_source(source: str, target: str) -> bool:
    generated_markers = (
        "artifact",
        "audit",
        "distill",
        "handoff",
        "authority_map",
        "gap_map",
        "manifest",
        "morning",
        "report",
        "review",
        "risk_map",
        "snapshot",
        "synthesis",
        "xray",
    )
    generated_sources = (
        "codex_overnight.py",
        "conversation_distiller.py",
        "dual_audit.py",
        "artifact_manifest.py",
        "immune_mission_xray.py",
        "knowledge_ops/cli.py",
        "merge_snapshot.py",
        "organism_council.py",
        "offline_training_bridge.py",
        "governance/run_nats_live_production_matrix.py",
        "allout_autopilot.py",
        "scout_audit.py",
        "strange_loop.py",
    )
    return source.endswith(generated_sources) or any(marker in target for marker in generated_markers)


def _is_operational_state_source(source: str, symbol: str, target: str) -> bool:
    operational_sources = (
        "active_inference.py",
        "custodians.py",
        "economic_spine.py",
        "thread_manager.py",
        "tui/",
        "tui_legacy.py",
        "zeitgeist.py",
        "cron",
        "terminal",
    )
    operational_markers = (
        "focus_file",
        "pid",
        "state_file",
        "trust_mode",
        "launchd",
        "prediction_error",
    )
    return any(part in source for part in operational_sources) or any(
        marker in target or marker in symbol for marker in operational_markers
    )


def _is_known_memory_writer_cluster(source: str, symbol: str, target: str) -> bool:
    writer_sources = (
        "agent_memory_manager.py",
        "algedonic_bridge.py",
        "bhed_gnan_monitor.py",
        "contracts/intelligence_adapters.py",
        "engine/conversation_memory.py",
        "engine/event_memory.py",
        "engine/retrieval_feedback.py",
        "engine/unified_index.py",
        "memory.py",
        "organism_memory.py",
        "runtime_state.py",
        "semantic_memory_bridge.py",
        "swarm.py",
        "telemetry_plane.py",
        "telos_gates.py",
        "vector_store.py",
    )
    writer_markers = (
        "memory",
        "retrieval",
        "runtime_state",
        "semantic",
        "telemetry",
        "vector",
        "witness",
    )
    return source.endswith(writer_sources) or any(
        marker in source or marker in symbol or marker in target for marker in writer_markers
    )


def _symbol_matches(candidate_symbol: str, registered_symbol: str) -> bool:
    if candidate_symbol == registered_symbol:
        return True
    return candidate_symbol.startswith(f"{registered_symbol}.")


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _skip_scan_path(path: Path) -> bool:
    skip_parts = {".git", ".venv", "__pycache__", "node_modules", "site-packages"}
    return any(part in skip_parts for part in path.parts)
