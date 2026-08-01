#!/usr/bin/env python3
"""Verify the exact non-canonical substrate exemptions registered by MemoryKernel."""

from __future__ import annotations

import ast
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
EXEMPTION_RE = re.compile(
    r"pattern-not-regex: ['\"]([^'\"]*BridgeRegistry[^'\"]*)['\"]"
)
EXEMPT_CLASS_DEFINITION_RE = re.compile(
    r"(?m)^([ \t]*)class\s+(?:(BridgeRegistry)\s*:"
    r"|(SQLiteGraphStore)\s*\(\s*GraphStore\s*\)\s*:"
    r"|(KnowledgeStore)\s*:)"
)
EXPECTED_EXEMPTION_PATTERN = (
    r"\bclass\s+(?:BridgeRegistry\s*:"
    r"|SQLiteGraphStore\s*\(\s*GraphStore\s*\)\s*:|KnowledgeStore\s*:)"
)
SUBSTRATE_SUFFIX_RE = re.compile(r"(?:Store|Ledger|Registry|Substrate)$")
PERSISTENCE_RATIONALE_RE = re.compile(r"(?m)^# persistence-rationale:\s+\S")
IGNORED_PATH_PARTS = {
    ".git",
    ".semgrep",
    ".venv",
    "__pycache__",
    "node_modules",
    "tests",
    "venv",
}
REGISTRATIONS = {
    "BridgeRegistry": (
        "dharma_swarm/bridge_registry.py",
        "home.bridges",
        {"BridgeRegistry"},
    ),
    "SQLiteGraphStore": (
        "dharma_swarm/graph_store.py",
        "home.dharma_graphs",
        {"GraphStore", "SQLiteGraphStore"},
    ),
    "KnowledgeStore": (
        "dharma_swarm/knowledge_units.py",
        "home.state_knowledge",
        {"KnowledgeStore"},
    ),
}
DIRECT_CONNECTORS = frozenset({"aiosqlite.connect", "sqlite3.connect"})

WRITER_FIELDS = (
    "writer_id",
    "owner_module",
    "symbol",
    "writes_to",
    "write_mode",
    "classification",
    "risk",
    "notes",
)
SURFACE_FIELDS = (
    "surface_id",
    "path_template",
    "owner_module",
    "role",
    "category",
    "authority_level",
    "write_mode",
    "adapter_mode",
    "active_status",
    "provenance_quality",
    "promotion_path",
    "canon_risk",
    "pii_secrets_risk",
    "latency_risk",
    "known_writers",
    "known_readers",
    "feeds",
    "source_of_truth_for",
    "projection_of",
    "migration_status",
    "do_not_migrate_reason",
    "sqlite_count_tables",
    "metadata",
)
EXPECTED_WRITER_CONTRACTS: dict[str, dict[str, Any]] = {
    "bridge_registry.store": {
        "writer_id": "bridge_registry.store",
        "owner_module": "dharma_swarm.bridge_registry",
        "symbol": "BridgeRegistry",
        "writes_to": ("home.bridges",),
        "write_mode": "WriteMode.READ_WRITE",
        "classification": "WriterClassification.REVIEW_REQUIRED",
        "risk": "RiskLevel.HIGH",
    },
    "graph_store.sqlite": {
        "writer_id": "graph_store.sqlite",
        "owner_module": "dharma_swarm.graph_store",
        "symbol": "SQLiteGraphStore",
        "writes_to": ("home.dharma_graphs",),
        "write_mode": "WriteMode.PROJECTION_WRITE",
        "classification": "WriterClassification.REVIEW_REQUIRED",
        "risk": "RiskLevel.HIGH",
    },
    "knowledge_units.store": {
        "writer_id": "knowledge_units.store",
        "owner_module": "dharma_swarm.knowledge_units",
        "symbol": "KnowledgeStore",
        "writes_to": ("home.state_knowledge",),
        "write_mode": "WriteMode.READ_WRITE",
        "classification": "WriterClassification.REVIEW_REQUIRED",
        "risk": "RiskLevel.HIGH",
    },
}
EXPECTED_SURFACE_CONTRACTS: dict[str, dict[str, Any]] = {
    "home.bridges": {
        "surface_id": "home.bridges",
        "path_template": "{home}/.dharma/db/bridges.db",
        "owner_module": "dharma_swarm.bridge_registry",
        "role": "MemorySurfaceRole.KNOWLEDGE_GRAPH",
        "category": "SurfaceCategory.PROJECTION",
        "authority_level": "AuthorityLevel.LOW",
        "write_mode": "WriteMode.READ_WRITE",
        "adapter_mode": "AdapterMode.READ_ONLY",
        "canon_risk": "RiskLevel.HIGH",
        "source_of_truth_for": (),
    },
    "home.dharma_graphs": {
        "surface_id": "home.dharma_graphs",
        "path_template": "{home}/.dharma/data/dharma_graphs.db",
        "owner_module": "dharma_swarm.graph_store",
        "role": "MemorySurfaceRole.KNOWLEDGE_GRAPH",
        "category": "SurfaceCategory.PROJECTION",
        "authority_level": "AuthorityLevel.LOW",
        "write_mode": "WriteMode.PROJECTION_WRITE",
        "adapter_mode": "AdapterMode.READ_ONLY",
        "canon_risk": "RiskLevel.HIGH",
        "source_of_truth_for": (),
    },
    "home.state_knowledge": {
        "surface_id": "home.state_knowledge",
        "path_template": "{home}/.dharma/state/knowledge.db",
        "owner_module": "dharma_swarm.knowledge_*",
        "role": "MemorySurfaceRole.KNOWLEDGE_GRAPH",
        "category": "SurfaceCategory.KNOWLEDGE_METABOLISM",
        "authority_level": "AuthorityLevel.LOW",
        "write_mode": "WriteMode.READ_WRITE",
        "adapter_mode": "AdapterMode.READ_ONLY",
        "canon_risk": "RiskLevel.HIGH",
        "source_of_truth_for": (),
    },
}


def _production_python_paths(repo_root: Path) -> list[Path]:
    return sorted(
        path
        for path in repo_root.rglob("*.py")
        if not any(
            part in IGNORED_PATH_PARTS for part in path.relative_to(repo_root).parts
        )
    )


def _node_value(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Tuple):
        return tuple(_node_value(item) for item in node.elts)
    if isinstance(node, ast.List):
        return [_node_value(item) for item in node.elts]
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_node_value(node.value)}.{node.attr}"
    return ast.dump(node, include_attributes=False)


def _constructor_calls(tree: ast.AST, constructor: str) -> list[ast.Call]:
    aliases = {constructor}
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for imported in node.names:
                    if imported.name == constructor:
                        alias = imported.asname or imported.name
                        if alias not in aliases:
                            aliases.add(alias)
                            changed = True
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            assignment = _assignment_parts(node)
            if assignment is None:
                continue
            targets, value = assignment
            if value is None:
                continue
            terminal = (
                value.id
                if isinstance(value, ast.Name)
                else value.attr
                if isinstance(value, ast.Attribute)
                else None
            )
            if terminal in aliases:
                new_aliases = _target_names(targets) - aliases
                aliases.update(new_aliases)
                changed = changed or bool(new_aliases)
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id in aliases)
            or (isinstance(node.func, ast.Attribute) and node.func.attr == constructor)
        )
    ]


def _call_fields(call: ast.Call, field_names: tuple[str, ...]) -> dict[str, Any] | None:
    if len(call.args) > len(field_names) or any(
        isinstance(argument, ast.Starred) for argument in call.args
    ):
        return None
    fields = {
        field_names[index]: _node_value(argument)
        for index, argument in enumerate(call.args)
    }
    for keyword in call.keywords:
        if (
            keyword.arg is None
            or keyword.arg not in field_names
            or keyword.arg in fields
        ):
            return None
        fields[keyword.arg] = _node_value(keyword.value)
    return fields


def _literal_call_identity(
    call: ast.Call,
    *,
    field_names: tuple[str, ...],
    identity_field: str,
) -> str | None:
    identity_index = field_names.index(identity_field)
    identity_node: ast.AST | None = None
    if len(call.args) > identity_index:
        identity_node = call.args[identity_index]
    else:
        for keyword in call.keywords:
            if keyword.arg == identity_field:
                identity_node = keyword.value
                break
    if isinstance(identity_node, ast.Constant) and isinstance(identity_node.value, str):
        return identity_node.value
    return None


def _contract_calls(
    calls: list[ast.Call],
    *,
    field_names: tuple[str, ...],
    identity_field: str,
    identity: str,
) -> list[dict[str, Any] | None]:
    matches: list[dict[str, Any] | None] = []
    for call in calls:
        call_identity = _literal_call_identity(
            call,
            field_names=field_names,
            identity_field=identity_field,
        )
        if call_identity == identity:
            matches.append(_call_fields(call, field_names))
    return matches


def _semantic_registration_errors(
    writer_specs: str,
    surface_specs: str,
) -> list[str]:
    errors: list[str] = []
    writer_tree = ast.parse(writer_specs, filename="writer_specs.py")
    surface_tree = ast.parse(surface_specs, filename="surface_specs_core.py")

    writer_calls = _constructor_calls(writer_tree, "MemoryWriterSpec")
    if any(
        _call_fields(call, WRITER_FIELDS) is None
        or _literal_call_identity(
            call,
            field_names=WRITER_FIELDS,
            identity_field="writer_id",
        )
        is None
        for call in writer_calls
    ):
        errors.append("MemoryKernel writers contain an unsupported constructor form")
    for writer_id, expected in EXPECTED_WRITER_CONTRACTS.items():
        matches = _contract_calls(
            writer_calls,
            field_names=WRITER_FIELDS,
            identity_field="writer_id",
            identity=writer_id,
        )
        if len(matches) != 1:
            errors.append(
                f"MemoryKernel writer {writer_id} must have exactly one registration"
            )
            continue
        fields = matches[0]
        if (
            fields is None
            or any(fields.get(name) != value for name, value in expected.items())
            or not (isinstance(fields.get("notes"), str) and fields["notes"].strip())
        ):
            errors.append(f"MemoryKernel writer {writer_id} semantic contract drifted")

    surface_calls = _constructor_calls(surface_tree, "SurfaceSpec")
    if any(
        _call_fields(call, SURFACE_FIELDS) is None
        or _literal_call_identity(
            call,
            field_names=SURFACE_FIELDS,
            identity_field="surface_id",
        )
        is None
        for call in surface_calls
    ):
        errors.append("MemoryKernel surfaces contain an unsupported constructor form")
    for surface_id, expected in EXPECTED_SURFACE_CONTRACTS.items():
        matches = _contract_calls(
            surface_calls,
            field_names=SURFACE_FIELDS,
            identity_field="surface_id",
            identity=surface_id,
        )
        if len(matches) != 1:
            errors.append(
                f"MemoryKernel surface {surface_id} must have exactly one registration"
            )
            continue
        fields = matches[0]
        if fields is None:
            errors.append(
                f"MemoryKernel surface {surface_id} semantic contract drifted"
            )
            continue
        fields.setdefault("source_of_truth_for", ())
        if any(fields.get(name) != value for name, value in expected.items()) or not (
            isinstance(fields.get("do_not_migrate_reason"), str)
            and fields["do_not_migrate_reason"].strip()
        ):
            errors.append(
                f"MemoryKernel surface {surface_id} semantic contract drifted"
            )
    return errors


def _dotted_name(node: ast.AST, module_aliases: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return module_aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        owner = _dotted_name(node.value, module_aliases)
        return f"{owner}.{node.attr}" if owner else None
    return None


def _unwrap_await(node: ast.AST | None) -> ast.AST | None:
    return node.value if isinstance(node, ast.Await) else node


def _lexical_nodes(statements: list[ast.stmt]) -> list[ast.AST]:
    """Return nodes in one lexical scope without crossing nested definitions."""
    nodes: list[ast.AST] = []
    pending: list[ast.AST] = list(statements)
    while pending:
        node = pending.pop()
        if isinstance(
            node,
            (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef, ast.Lambda),
        ):
            continue
        nodes.append(node)
        for child in ast.iter_child_nodes(node):
            if isinstance(
                child,
                (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef, ast.Lambda),
            ):
                continue
            pending.append(child)
    return nodes


def _assignment_parts(node: ast.AST) -> tuple[list[ast.expr], ast.AST | None] | None:
    if isinstance(node, ast.Assign):
        return node.targets, _unwrap_await(node.value)
    if isinstance(node, ast.AnnAssign):
        return [node.target], _unwrap_await(node.value)
    return None


def _target_names(targets: list[ast.expr]) -> set[str]:
    return {target.id for target in targets if isinstance(target, ast.Name)}


def _returns_connector(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    callables: set[str],
    module_aliases: dict[str, str],
) -> bool:
    nodes = _lexical_nodes(function.body)
    local_callables = set(callables)
    connector_values: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in nodes:
            assignment = _assignment_parts(node)
            if assignment is None:
                continue
            targets, value = assignment
            names = _target_names(targets)
            callable_name = (
                _dotted_name(value, module_aliases) if value is not None else None
            )
            if callable_name in local_callables:
                new_names = names - local_callables
                local_callables.update(new_names)
                changed = changed or bool(new_names)
            if isinstance(value, ast.Lambda):
                body = _unwrap_await(value.body)
                if (
                    isinstance(body, ast.Call)
                    and _dotted_name(body.func, module_aliases) in local_callables
                ):
                    new_names = names - local_callables
                    local_callables.update(new_names)
                    changed = changed or bool(new_names)
            if isinstance(value, ast.Call) and (
                _dotted_name(value.func, module_aliases) in local_callables
            ):
                new_names = names - connector_values
                connector_values.update(new_names)
                changed = changed or bool(new_names)
            if isinstance(value, ast.Name) and value.id in connector_values:
                new_names = names - connector_values
                connector_values.update(new_names)
                changed = changed or bool(new_names)

    for node in nodes:
        if not isinstance(node, ast.Return):
            continue
        value = _unwrap_await(node.value)
        if isinstance(value, ast.Call) and (
            _dotted_name(value.func, module_aliases) in local_callables
        ):
            return True
        if isinstance(value, ast.Name) and value.id in connector_values:
            return True
    return False


def _module_connector_callables(tree: ast.Module) -> tuple[set[str], dict[str, str]]:
    module_aliases: dict[str, str] = {}
    callables = set(DIRECT_CONNECTORS)
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                if alias.name in {"aiosqlite", "sqlite3"}:
                    module_aliases[alias.asname or alias.name] = alias.name
        elif isinstance(statement, ast.ImportFrom) and statement.module in {
            "aiosqlite",
            "sqlite3",
        }:
            for alias in statement.names:
                if alias.name == "connect":
                    callables.add(alias.asname or alias.name)

    changed = True
    while changed:
        changed = False
        for statement in tree.body:
            targets: list[ast.expr] = []
            value: ast.expr | None = None
            if isinstance(statement, ast.Assign):
                targets = statement.targets
                value = statement.value
            elif isinstance(statement, ast.AnnAssign):
                targets = [statement.target]
                value = statement.value
            if value is not None:
                source = _dotted_name(value, module_aliases)
                if source in callables:
                    for target in targets:
                        if isinstance(target, ast.Name) and target.id not in callables:
                            callables.add(target.id)
                            changed = True
                if isinstance(value, ast.Lambda):
                    body = _unwrap_await(value.body)
                    if (
                        isinstance(body, ast.Call)
                        and _dotted_name(body.func, module_aliases) in callables
                    ):
                        for target in targets:
                            if (
                                isinstance(target, ast.Name)
                                and target.id not in callables
                            ):
                                callables.add(target.id)
                                changed = True
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                returns_connector = _returns_connector(
                    statement,
                    callables=callables,
                    module_aliases=module_aliases,
                )
                if returns_connector and statement.name not in callables:
                    callables.add(statement.name)
                    changed = True
    return callables, module_aliases


def _class_lexical_nodes(class_node: ast.ClassDef) -> list[ast.AST]:
    nodes: list[ast.AST] = []
    for statement in class_node.body:
        if isinstance(statement, ast.ClassDef):
            continue
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nodes.extend(_lexical_nodes(statement.body))
            continue
        nodes.extend(_lexical_nodes([statement]))
    return nodes


def _connector_calls(
    nodes: list[ast.AST],
    *,
    callables: set[str],
    module_aliases: dict[str, str],
) -> list[ast.Call]:
    local_callables = set(callables)
    changed = True
    while changed:
        changed = False
        for node in nodes:
            assignment = _assignment_parts(node)
            if assignment is None:
                continue
            targets, value = assignment
            names = _target_names(targets)
            callable_name = (
                _dotted_name(value, module_aliases) if value is not None else None
            )
            if callable_name in local_callables:
                new_names = names - local_callables
                local_callables.update(new_names)
                changed = changed or bool(new_names)
            if isinstance(value, ast.Lambda):
                body = _unwrap_await(value.body)
                if (
                    isinstance(body, ast.Call)
                    and _dotted_name(body.func, module_aliases) in local_callables
                ):
                    new_names = names - local_callables
                    local_callables.update(new_names)
                    changed = changed or bool(new_names)
    return [
        node
        for node in nodes
        if isinstance(node, ast.Call)
        and _dotted_name(node.func, module_aliases) in local_callables
    ]


def _substrate_connector_sites(source: str, *, filename: str) -> Counter[str]:
    tree = ast.parse(source, filename=filename)
    callables, module_aliases = _module_connector_callables(tree)
    findings: Counter[str] = Counter()
    for class_node in (
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and SUBSTRATE_SUFFIX_RE.search(node.name)
    ):
        findings[class_node.name] += len(
            _connector_calls(
                _class_lexical_nodes(class_node),
                callables=callables,
                module_aliases=module_aliases,
            )
        )
        if findings[class_node.name] == 0:
            del findings[class_node.name]
    return findings


def _substrate_constructor_errors(repo_root: Path) -> list[str]:
    expected = Counter(
        {
            f"{relative}:{class_name}": 1
            for class_name, (relative, _surface_id, _classes) in REGISTRATIONS.items()
        }
    )
    actual: Counter[str] = Counter()
    for class_name, (relative, _surface_id, _classes) in REGISTRATIONS.items():
        sites = _substrate_connector_sites(
            (repo_root / relative).read_text(), filename=relative
        )
        actual[f"{relative}:{class_name}"] = sites.get(class_name, 0)
    if actual == expected:
        return []
    return [
        "persistence constructor sites drifted: "
        f"expected={dict(sorted(expected.items()))}, "
        f"actual={dict(sorted(actual.items()))}"
    ]


def _exempt_class_declarations(
    repo_root: Path,
) -> dict[str, list[tuple[str, str]]]:
    declarations = {class_name: [] for class_name in REGISTRATIONS}
    for path in _production_python_paths(repo_root):
        relative = path.relative_to(repo_root).as_posix()
        for match in EXEMPT_CLASS_DEFINITION_RE.finditer(path.read_text()):
            class_name = next(group for group in match.groups()[1:] if group)
            declarations[class_name].append((relative, match.group(1)))
    return declarations


def validate(repo_root: Path = REPO_ROOT) -> list[str]:
    """Return contract violations; setup/read/parse failures raise distinctly."""
    config = (repo_root / ".semgrep/dharma-anti-slop.yml").read_text()
    match = EXEMPTION_RE.search(config)
    if match is None:
        return ["no-new-substrate lacks the exact registered-writer exemption"]

    errors: list[str] = []
    if match.group(1) != EXPECTED_EXEMPTION_PATTERN:
        errors.append("registered-writer exemption signatures drifted")
    exempted = {
        class_name
        for class_name in REGISTRATIONS
        if re.search(rf"\b{re.escape(class_name)}\b", match.group(1))
    }
    if exempted != set(REGISTRATIONS):
        errors.append(f"unexpected exempt class set: {sorted(exempted)}")

    expected_declarations = {
        class_name: [(relative, "")]
        for class_name, (relative, _surface_id, _classes) in REGISTRATIONS.items()
    }
    actual_declarations = _exempt_class_declarations(repo_root)
    if actual_declarations != expected_declarations:
        errors.append(f"exempt class declarations drifted: {actual_declarations}")

    errors.extend(_substrate_constructor_errors(repo_root))

    writer_specs = (
        repo_root / "dharma_swarm/memory_kernel/writer_specs.py"
    ).read_text()
    surface_specs = (
        repo_root / "dharma_swarm/memory_kernel/surface_specs_core.py"
    ).read_text()
    errors.extend(_semantic_registration_errors(writer_specs, surface_specs))
    for _class_name, (relative, _surface_id, expected_classes) in REGISTRATIONS.items():
        source = (repo_root / relative).read_text()
        if source.count("# persistence-role: exempt") != 1:
            errors.append(f"{relative}: expected exactly one exempt role marker")
        if len(PERSISTENCE_RATIONALE_RE.findall(source)) != 1:
            errors.append(f"{relative}: persistence rationale drifted")
        classes = Counter(
            node.name
            for node in ast.walk(ast.parse(source, filename=relative))
            if isinstance(node, ast.ClassDef) and SUBSTRATE_SUFFIX_RE.search(node.name)
        )
        expected_class_counts = Counter(expected_classes)
        if classes != expected_class_counts:
            errors.append(
                f"{relative}: unadjudicated substrate class inventory "
                f"{dict(sorted(classes.items()))}"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args not in ([], ["--negative-control"]):
        print("usage: check_registered_substrate_roles.py [--negative-control]")
        return 3
    negative_control = args == ["--negative-control"]
    try:
        if negative_control:
            relative = "dharma_swarm/bridge_registry.py"
            source_path = REPO_ROOT / relative
            source = source_path.read_text()
            marker = "# persistence-role: exempt"
            if source.count(marker) != 1:
                raise RuntimeError("negative-control mutation anchor is not unique")
            source_path.write_text(
                source.replace(marker, "# persistence-role: omitted", 1)
            )
        errors = validate()
    except (OSError, RuntimeError, SyntaxError) as exc:
        print(f"substrate-role verifier setup failure: {exc}", file=sys.stderr)
        return 3
    if negative_control:
        expected = [
            "dharma_swarm/bridge_registry.py: expected exactly one exempt role marker"
        ]
        if errors == expected:
            print("negative control: missing role marker detected")
            return 1
        if errors:
            print(f"negative-control setup drift: {errors}", file=sys.stderr)
            return 3
        print(
            "negative control failed: missing role marker was accepted", file=sys.stderr
        )
        return 0
    if errors:
        for error in errors:
            print(f"substrate-role violation: {error}", file=sys.stderr)
        return 1
    print("registered substrate roles: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
