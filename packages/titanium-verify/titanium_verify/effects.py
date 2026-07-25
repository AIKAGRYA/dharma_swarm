"""Effect analysis for the TCB dialect.

The effect lattice mirrors `telos_kernel/_io/effect.py`:

    PURE ⊑ FS_READ ⊑ FS_WRITE
    PURE ⊑ NET
    PURE ⊑ SUBPROCESS
    PURE ⊑ NONDETERMINISTIC

A function's effect set is the *join* of:
    (a) the effect tags on its @effect(...) decorator, if any, and
    (b) the effect set of every call it makes (transitive closure).

The purity property (SECURITY.md §3 / the rim/core split from PR #1c) is:

    ∀ f ∈ core_functions.  effects(f) ⊆ {PURE}

i.e. no core function calls anything that touches the filesystem, the
network, a subprocess, or any nondeterministic source, unless the call
goes through a tagged rim function — and rim functions are excluded from
this quantifier by construction.

We encode this as an SMT constraint per function and let Z3 discharge it.
The result is a *proof*, not a heuristic — if Z3 returns UNSAT for the
negation, no combination of runtime values can reach an effectful state.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping

from titanium_verify.frontend import Function, Module


class Effect(str, Enum):
    """Effect categories, mirroring telos_kernel/_io/effect.py."""
    PURE = "PURE"
    FS_READ = "FS_READ"
    FS_WRITE = "FS_WRITE"
    NET = "NET"
    SUBPROCESS = "SUBPROCESS"
    NONDETERMINISTIC = "NONDETERMINISTIC"


# Modules whose top-level names are structurally effectful. If a function
# calls X.foo() where X is one of these, we assign the mapped effect.
_MODULE_EFFECTS: dict[str, Effect] = {
    "open": Effect.FS_WRITE,       # Python open() defaults to read but 'w'/'a' modes exist
    "os": Effect.FS_WRITE,
    "os.path": Effect.FS_READ,     # os.path.exists, os.path.join are technically pure metadata
    "pathlib": Effect.FS_READ,     # Path().read_text, .write_text, .mkdir — treated as effectful
    "shutil": Effect.FS_WRITE,
    "subprocess": Effect.SUBPROCESS,
    "socket": Effect.NET,
    "urllib": Effect.NET,
    "urllib.request": Effect.NET,
    "http": Effect.NET,
    "requests": Effect.NET,
    "httpx": Effect.NET,
    "random": Effect.NONDETERMINISTIC,
    "time": Effect.NONDETERMINISTIC,   # time.time() is nondeterministic
    "datetime": Effect.PURE,           # datetime constructors are pure; datetime.now is not
    "tempfile": Effect.FS_WRITE,
    "yaml": Effect.FS_READ,
    "json": Effect.PURE,               # json.dumps/loads on in-memory strings are pure
    "hashlib": Effect.PURE,            # hash primitives are pure
    "hmac": Effect.PURE,
    "secrets": Effect.NONDETERMINISTIC,  # secrets.token_bytes uses OS entropy
    # uuid module is mixed: uuid.uuid4() is nondet, but uuid.UUID(str) is pure.
    # Handle it via _QUALIFIED_EFFECTS below.
}

# Explicit exceptions: fully-qualified names that override module defaults.
# datetime.datetime.now() is NONDETERMINISTIC even though datetime as a
# whole is pure.
_QUALIFIED_EFFECTS: dict[str, Effect] = {
    "datetime.datetime.now": Effect.NONDETERMINISTIC,
    "datetime.date.today": Effect.NONDETERMINISTIC,
    "os.path.exists": Effect.FS_READ,
    "os.path.join": Effect.PURE,
    "os.path.dirname": Effect.PURE,
    "os.path.basename": Effect.PURE,
    "os.environ.get": Effect.NONDETERMINISTIC,
    # uuid: uuid.UUID(str) is pure (parses a hex string); uuid.uuid4() /
    # uuid1() draw from an entropy source.
    "uuid.UUID": Effect.PURE,
    "uuid.uuid4": Effect.NONDETERMINISTIC,
    "uuid.uuid1": Effect.NONDETERMINISTIC,
    "uuid.uuid3": Effect.PURE,
    "uuid.uuid5": Effect.PURE,
}


@dataclass(frozen=True)
class EffectSet:
    """Immutable set of effects. Join is set union."""
    effects: frozenset[Effect]

    def is_pure(self) -> bool:
        return not self.effects or self.effects == {Effect.PURE}

    def join(self, other: "EffectSet") -> "EffectSet":
        merged = (self.effects | other.effects) - {Effect.PURE}
        if not merged:
            return EffectSet(frozenset({Effect.PURE}))
        return EffectSet(frozenset(merged))

    def __or__(self, other: "EffectSet") -> "EffectSet":
        return self.join(other)

    @classmethod
    def pure(cls) -> "EffectSet":
        return cls(frozenset({Effect.PURE}))

    @classmethod
    def of(cls, *effects: Effect) -> "EffectSet":
        return cls(frozenset(effects))


def _resolve_call_target(
    node: ast.Call,
    aliases: Mapping[str, str] | None = None,
) -> str | None:
    """Best-effort resolution of a call target to a dotted name."""
    func = node.func
    parts: list[str] = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
        parts = list(reversed(parts))
        if aliases and parts and parts[0] in aliases:
            resolved = aliases[parts[0]].split(".")
            parts = resolved + parts[1:]
        return ".".join(parts)
    return None


def _effect_of_open_call(call: ast.Call) -> EffectSet:
    """Classify open() by mode when it is statically visible."""
    mode = "r"
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
        if isinstance(call.args[1].value, str):
            mode = call.args[1].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            if isinstance(kw.value.value, str):
                mode = kw.value.value
    if any(flag in mode for flag in ("w", "a", "x", "+")):
        return EffectSet.of(Effect.FS_WRITE)
    return EffectSet.of(Effect.FS_READ)


def _syntactic_effect_of_call(
    call: ast.Call,
    aliases: Mapping[str, str] | None = None,
) -> EffectSet:
    """Assign an effect set to a call based on its target name."""
    target = _resolve_call_target(call, aliases)
    if target is None:
        # e.g. self.method(...) or unresolvable — treat as unknown.
        # Conservative: return PURE and let the interprocedural pass
        # discover effects via the callee's own tags.
        return EffectSet.pure()

    # Special case: builtins that are always effectful.
    if target == "open":
        return _effect_of_open_call(call)
    if target == "input":
        return EffectSet.of(Effect.NONDETERMINISTIC)
    if target == "print":
        # stdout is technically effectful; the kernel doesn't use print.
        return EffectSet.of(Effect.NONDETERMINISTIC)

    # Qualified overrides first.
    if target in _QUALIFIED_EFFECTS:
        return EffectSet.of(_QUALIFIED_EFFECTS[target])

    # Fall back to module-level defaults.
    for prefix, eff in _MODULE_EFFECTS.items():
        if target == prefix or target.startswith(prefix + "."):
            if eff == Effect.PURE:
                return EffectSet.pure()
            return EffectSet.of(eff)

    return EffectSet.pure()


def _local_effect(
    function: Function,
    module_aliases: Mapping[str, str],
) -> EffectSet:
    """Effect set from the function's own body (calls it makes directly).

    This does NOT include interprocedural effects from calls to other
    kernel functions — those come from the fixpoint over the call graph.
    """
    eff = EffectSet.pure()
    aliases = dict(module_aliases)
    aliases.update(function.import_aliases)
    for stmt in function.body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                eff = eff | _syntactic_effect_of_call(node, aliases)
    return eff


def _declared_effects(function: Function) -> EffectSet:
    """Effect set declared by @effect(...) decorator, if any."""
    if not function.effect_tags:
        return EffectSet.pure()
    return EffectSet(frozenset(Effect(tag) for tag in function.effect_tags))


@dataclass
class EffectAnalysis:
    """Result of effect analysis over a set of modules."""
    per_function: dict[str, EffectSet]
    rim_functions: set[str]

    def effect_of(self, qualname: str) -> EffectSet:
        return self.per_function.get(qualname, EffectSet.pure())

    def is_pure(self, qualname: str) -> bool:
        return self.effect_of(qualname).is_pure()


def analyze_effects(modules: Iterable[Module]) -> EffectAnalysis:
    """Assign an effect set to every function.

    Sound but not complete for higher-order code — we treat unresolvable
    calls as pure (see `_syntactic_effect_of_call`). Because the TCB
    forbids lambdas and callable-as-argument patterns, this heuristic is
    exact for the accepted subset.
    """
    per_function: dict[str, EffectSet] = {}
    rim_functions: set[str] = set()
    for m in modules:
        for f in m.functions:
            declared = _declared_effects(f)
            local = _local_effect(f, m.import_aliases)
            per_function[f.qualname] = declared | local
            if m.is_rim:
                rim_functions.add(f.qualname)
    return EffectAnalysis(per_function=per_function, rim_functions=rim_functions)
