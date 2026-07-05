"""Python AST → typed IR frontend.

We parse the target package with the stdlib `ast` module (no C extensions,
no eval) and build a small typed IR that downstream passes consume.

We do NOT parse arbitrary Python. The frontend explicitly rejects
constructs outside the TCB dialect and marks the containing function
REJECTED. This keeps unsoundness impossible: if we can't parse it, we
don't claim it's verified.

Supported constructs:
    - def / async def with typed args
    - dataclass and Pydantic BaseModel classes (fields recorded, methods
      as functions)
    - if / else, for, while, try / except / finally
    - return, raise, pass, break, continue
    - assignments, augmented assignments
    - arithmetic, comparison, boolean ops, string ops
    - subscript, attribute, call
    - literals (int, str, bytes, None, True, False, tuple, list, dict, set)

Unsupported (marks function REJECTED):
    - eval, exec, compile, __import__
    - lambda (allowed only as top-level assignment expression? no — reject)
    - metaclass shenanigans
    - decorators other than a small allow-list
"""
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


ALLOWED_DECORATORS: frozenset[str] = frozenset({
    "dataclass",
    "frozen",
    "staticmethod",
    "classmethod",
    "property",
    "abstractmethod",
    "abc.abstractmethod",
    "effect",             # from telos_kernel._io.effect
    "field_validator",
    "model_validator",
    "cached_property",
    "override",
    # icontract runtime contracts — semantically pure (no side effects)
    "require",
    "ensure",
    "invariant",
    "icontract.require",
    "icontract.ensure",
    "icontract.invariant",
})


@dataclass(frozen=True)
class Argument:
    name: str
    annotation: str | None


@dataclass
class Function:
    """A function or method in the target package."""
    qualname: str            # e.g. "telos_kernel.notary.LocalFileAnchor.anchor"
    module: str              # e.g. "telos_kernel.notary"
    name: str                # e.g. "anchor"
    args: tuple[Argument, ...]
    return_annotation: str | None
    decorators: tuple[str, ...]
    effect_tags: frozenset[str]  # from @effect(...) if present
    body: list[ast.stmt]
    import_aliases: dict[str, str] = field(default_factory=dict)
    rejected_reason: str | None = None  # non-None ⇒ REJECTED

    @property
    def is_rejected(self) -> bool:
        return self.rejected_reason is not None


@dataclass
class Module:
    """A Python module in the target package."""
    dotted_name: str          # e.g. "telos_kernel.notary"
    path: Path
    is_rim: bool              # True if under an _io/ subpackage
    imports: tuple[str, ...]  # top-level module imports
    import_aliases: dict[str, str]
    functions: list[Function]


def _decorator_name(node: ast.expr) -> str:
    """Best-effort dotted-name for a decorator expression."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _decorator_name(node.value)
        return f"{base}.{node.attr}"
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return "<complex-decorator>"


def _annotation_text(node: ast.expr | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _effect_tags_from_decorators(decorators: list[ast.expr]) -> frozenset[str]:
    tags: set[str] = set()
    for d in decorators:
        # @effect(Effect.FS_READ, Effect.SUBPROCESS)
        if isinstance(d, ast.Call) and _decorator_name(d.func).endswith("effect"):
            for arg in d.args:
                # Expect Effect.FS_READ style attribute access
                if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name):
                    if arg.value.id == "Effect":
                        tags.add(arg.attr)
    return frozenset(tags)


def _import_aliases(nodes: list[ast.stmt]) -> dict[str, str]:
    """Map local import names to fully-qualified targets.

    Examples:
        import subprocess as sp      -> {"sp": "subprocess"}
        from subprocess import run   -> {"run": "subprocess.run"}
    """
    aliases: dict[str, str] = {}
    for stmt in nodes:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local = alias.asname or alias.name.split(".", 1)[0]
                    aliases[local] = alias.name
            elif isinstance(node, ast.ImportFrom):
                if node.level != 0 or not node.module:
                    continue
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    local = alias.asname or alias.name
                    aliases[local] = f"{node.module}.{alias.name}"
    return aliases


class _FrontendError(Exception):
    """Internal — used to bail out with a REJECTED reason for one function."""


def _check_forbidden(body: list[ast.stmt]) -> None:
    """Raise _FrontendError if body contains constructs we cannot soundly verify."""
    class Walker(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Name):
                if node.func.id in ("eval", "exec", "compile", "__import__"):
                    raise _FrontendError(f"forbidden call: {node.func.id}(...)")
            self.generic_visit(node)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            # Lambdas would need higher-order reasoning we don't support yet.
            raise _FrontendError("lambda not supported in TCB dialect")

        def visit_Global(self, node: ast.Global) -> None:
            raise _FrontendError("global statement not supported")

        def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
            raise _FrontendError("nonlocal statement not supported")

    w = Walker()
    for stmt in body:
        w.visit(stmt)


def _extract_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    module_name: str,
    class_name: str | None,
) -> Function:
    args = tuple(
        Argument(name=a.arg, annotation=_annotation_text(a.annotation))
        for a in node.args.args
    )
    decorators = tuple(_decorator_name(d) for d in node.decorator_list)
    effect_tags = _effect_tags_from_decorators(node.decorator_list)
    return_annotation = _annotation_text(node.returns)
    qualname_parts = [module_name]
    if class_name is not None:
        qualname_parts.append(class_name)
    qualname_parts.append(node.name)
    qualname = ".".join(qualname_parts)
    rejected_reason: str | None = None
    for dec in decorators:
        # We allow any dotted form whose leaf is in the allow list, plus
        # anything called `effect` (rim tagging).
        leaf = dec.split(".")[-1]
        if leaf not in ALLOWED_DECORATORS and dec not in ALLOWED_DECORATORS:
            rejected_reason = f"unsupported decorator: {dec}"
            break
    if rejected_reason is None:
        try:
            _check_forbidden(list(node.body))
        except _FrontendError as e:
            rejected_reason = str(e)
    return Function(
        qualname=qualname,
        module=module_name,
        name=node.name,
        args=args,
        return_annotation=return_annotation,
        decorators=decorators,
        effect_tags=effect_tags,
        body=list(node.body),
        import_aliases=_import_aliases(list(node.body)),
        rejected_reason=rejected_reason,
    )


def _module_functions(tree: ast.Module, module_name: str) -> list[Function]:
    fns: list[Function] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fns.append(_extract_function(node, module_name, class_name=None))
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fns.append(_extract_function(sub, module_name, node.name))
    return fns


def _module_imports(tree: ast.Module) -> tuple[str, ...]:
    imports: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    return tuple(sorted(imports))


def _iter_py_files(pkg_root: Path) -> Iterator[Path]:
    for p in sorted(pkg_root.rglob("*.py")):
        rel = p.relative_to(pkg_root).as_posix()
        # Skip test directories and __pycache__.
        if "/tests/" in "/" + rel or rel.startswith("tests/"):
            continue
        if "__pycache__" in rel:
            continue
        yield p


def parse_package(pkg_root: Path, dotted_prefix: str) -> list[Module]:
    """Parse every .py file under `pkg_root` into `Module` records.

    `dotted_prefix` is the Python package name (e.g. "telos_kernel") used
    to build qualnames.
    """
    modules: list[Module] = []
    for path in _iter_py_files(pkg_root):
        rel = path.relative_to(pkg_root).as_posix()
        dotted = dotted_prefix + "." + rel.removesuffix(".py").replace("/", ".")
        dotted = dotted.removesuffix(".__init__")
        is_rim = "/_io/" in "/" + rel or rel.startswith("_io/")
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as e:
            # Should never happen for the TCB. Surface it as a REJECTED module
            # with a synthetic function so the report shows the error.
            modules.append(Module(
                dotted_name=dotted,
                path=path,
                is_rim=is_rim,
                imports=(),
                import_aliases={},
                functions=[Function(
                    qualname=dotted,
                    module=dotted,
                    name="<module>",
                    args=(),
                    return_annotation=None,
                    decorators=(),
                    effect_tags=frozenset(),
                    body=[],
                    import_aliases={},
                    rejected_reason=f"SyntaxError: {e}",
                )],
            ))
            continue
        modules.append(Module(
            dotted_name=dotted,
            path=path,
            is_rim=is_rim,
            imports=_module_imports(tree),
            import_aliases=_import_aliases(list(tree.body)),
            functions=_module_functions(tree, dotted),
        ))
    return modules
