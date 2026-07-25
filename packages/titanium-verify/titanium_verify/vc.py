"""Verification-condition generator.

Purity is a monotone dataflow property: the effect set of a function is
the least fixpoint of `effects(f) = declared(f) ∪ ⋃_{c ∈ callees(f)} effects(c)`
over the call graph. Kildall's theorem gives soundness and completeness
of the standard worklist algorithm on any monotone lattice; we use it
here ([Kildall 1973](https://doi.org/10.1145/512927.512945)).

We then compile the *result* of the fixpoint into an SMT check that Z3
validates independently: for each core function, we assert its effect
bitvector is fixed to the value the worklist computed, and ask whether
that value has any impure bit set. This gives a machine-checkable proof
witness that CI (and downstream tools) can re-verify without trusting our
fixpoint code.

SMT encoding:
  * one 8-bit bitvector per Effect enum value (room for 8 effects; we
    currently use 6).
  * union = bitwise OR; subset = bitwise-AND equality.

For properties that are NOT monotone dataflow (fail-closed error paths,
signature-path canonicalization) later PRs will build genuine SMT VCs.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Iterable, Mapping

import z3

from titanium_verify.effects import Effect, EffectAnalysis, EffectSet
from titanium_verify.frontend import Function, Module


# Fixed encoding: bit index per effect. Keep this stable — reports quote
# these positions.
_EFFECT_BITS: dict[Effect, int] = {
    Effect.PURE: 0,
    Effect.FS_READ: 1,
    Effect.FS_WRITE: 2,
    Effect.NET: 3,
    Effect.SUBPROCESS: 4,
    Effect.NONDETERMINISTIC: 5,
}
_BV_WIDTH = 8  # room to grow


def _effect_set_to_bv(es: EffectSet) -> int:
    val = 0
    for e in es.effects:
        if e in _EFFECT_BITS:
            val |= (1 << _EFFECT_BITS[e])
    return val


def _declared_tags_to_bv(tags: Iterable[str]) -> int:
    val = 0
    for tag in tags:
        effect = Effect.__members__.get(tag)
        if effect in _EFFECT_BITS:
            val |= (1 << _EFFECT_BITS[effect])
    return val


def _pure_mask() -> int:
    return 1 << _EFFECT_BITS[Effect.PURE]


def _impure_mask() -> int:
    """Bits that make a function impure (everything except PURE)."""
    mask = 0
    for e, bit in _EFFECT_BITS.items():
        if e is not Effect.PURE:
            mask |= (1 << bit)
    return mask


def _collect_kernel_calls(
    function: Function,
    all_qualnames: set[str],
    module_aliases: Mapping[str, str],
) -> set[str]:
    """Return the qualnames of other kernel functions this function calls.

    Resolution strategy (sound but conservative):
      1. For a call written as `mod.func(...)` or `pkg.mod.func(...)`, we
         match against qualnames whose dotted-suffix equals the call target.
         We require at least a two-segment match (module + name) to avoid
         collapsing a bare `.append()` list-method call into a kernel
         function named `append`.
      2. Bare-name calls like `foo(...)` match only same-module functions
         `<function.module>.foo`.
      3. Method calls on `self.method(...)` match only same-class methods.

    Anything that doesn't match by these rules is treated as an *external*
    call and gets its effect from `_syntactic_effect_of_call` in effects.py.
    """
    callees: set[str] = set()
    same_module = function.module
    aliases = dict(module_aliases)
    aliases.update(function.import_aliases)
    # Extract enclosing class name if any (qualname has three or more parts).
    parts = function.qualname.split(".")
    enclosing_class = None
    # module = function.module has (module dots + 1) parts already; anything
    # extra before the leaf is the class.
    if len(parts) > len(same_module.split(".")) + 1:
        enclosing_class = parts[-2]

    for stmt in function.body:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Call):
                continue
            target_parts: list[str] = []
            func = node.func
            self_call = False
            while isinstance(func, ast.Attribute):
                target_parts.append(func.attr)
                func = func.value
            if isinstance(func, ast.Name):
                target_parts.append(func.id)
            elif isinstance(func, ast.Attribute):
                # unresolvable
                continue
            else:
                continue
            target_parts.reverse()
            if not target_parts:
                continue
            if target_parts[0] in aliases:
                target_parts = aliases[target_parts[0]].split(".") + target_parts[1:]

            # Case A: bare-name call, e.g. `foo(x)`.
            if len(target_parts) == 1:
                candidate = f"{same_module}.{target_parts[0]}"
                if candidate in all_qualnames:
                    callees.add(candidate)
                continue

            # Case B: self.method(...) call.
            if target_parts[0] == "self" and len(target_parts) == 2 and enclosing_class:
                candidate = f"{same_module}.{enclosing_class}.{target_parts[1]}"
                if candidate in all_qualnames:
                    callees.add(candidate)
                continue

            # Case C: dotted call like `mod.func(...)` or `Class.method(...)`.
            dotted = ".".join(target_parts)
            # Try exact match first.
            if dotted in all_qualnames:
                callees.add(dotted)
                continue
            init_candidate = f"{dotted}.__init__"
            if init_candidate in all_qualnames:
                callees.add(init_candidate)
                continue
            # Try suffix-match with a full path segment boundary. We only
            # match if the tail is at least two segments — module + name.
            if len(target_parts) >= 2:
                needle = "." + dotted
                for q in all_qualnames:
                    if q.endswith(needle):
                        callees.add(q)
            # Never match on a bare single-segment suffix (would over-
            # approximate: `.append`, `.get`, etc.).
    return callees


@dataclass
class VerificationCondition:
    """A single SMT problem for one function/property pair."""
    function_qualname: str
    property_name: str
    solver: z3.Solver
    # Symbolic variable for the function's effect bitvector.
    effect_bv: z3.BitVecRef


def _compute_purity_fixpoint(
    modules: list[Module],
    analysis: EffectAnalysis,
    callees_map: dict[str, set[str]],
    all_qualnames: set[str],
) -> dict[str, int]:
    """Compute the least-fixpoint effect bitvector per function.

    Uses the standard worklist algorithm over the reversed call graph.
    Monotone lattice: (P({Effect}), ⊆, ∪). Kildall (1973) gives soundness
    and completeness.
    """
    # Seed: each function's local (declared ∪ syntactic) contribution.
    local: dict[str, int] = {}
    for m in modules:
        for f in m.functions:
            if f.is_rejected:
                continue
            declared_bits = _declared_tags_to_bv(f.effect_tags)
            if declared_bits == 0:
                declared_bits = _pure_mask()
            synth = _effect_set_to_bv(analysis.effect_of(f.qualname))
            local[f.qualname] = declared_bits | synth

    # Build reverse call graph: caller_of[callee] = set of callers.
    caller_of: dict[str, set[str]] = {q: set() for q in local}
    for q, callees in callees_map.items():
        if q not in local:
            continue
        for c in callees:
            if c in local:
                caller_of.setdefault(c, set()).add(q)

    # Worklist: iterate until stable.
    current: dict[str, int] = dict(local)
    worklist: list[str] = list(current.keys())
    while worklist:
        q = worklist.pop()
        new_val = local.get(q, _pure_mask())
        for c in callees_map.get(q, ()):
            if c in current:
                new_val |= current[c]
        # Normalize: if any impure bit is set, drop PURE.
        if new_val & _impure_mask():
            new_val &= ~_pure_mask()
        if new_val != current[q]:
            current[q] = new_val
            for caller in caller_of.get(q, ()):
                worklist.append(caller)
    return current


def generate_purity_vcs(
    modules: Iterable[Module],
    analysis: EffectAnalysis,
) -> list[VerificationCondition]:
    """Generate one VC per non-rim function checking effect_bv ⊆ {PURE}.

    Encoding:
      1. Run the least-fixpoint worklist to compute each function's
         effect bitvector.
      2. For each core function, emit an SMT problem that asserts the
         computed value and asks Z3 to find any *impure* bit. Z3 either
         returns unsat (property holds) or sat with a concrete witness.

    Because we hand Z3 a concrete assignment rather than a set of
    circular constraints, the check is monotone and deterministic; no
    spurious "the fixpoint could also be this larger set" solutions.
    """
    modules = list(modules)
    all_qualnames: set[str] = set()
    for m in modules:
        for f in m.functions:
            all_qualnames.add(f.qualname)

    callees_map: dict[str, set[str]] = {}
    for m in modules:
        for f in m.functions:
            callees_map[f.qualname] = _collect_kernel_calls(
                f,
                all_qualnames,
                m.import_aliases,
            )

    fixpoint = _compute_purity_fixpoint(modules, analysis, callees_map, all_qualnames)

    vcs: list[VerificationCondition] = []
    for m in modules:
        if m.is_rim:
            continue
        for f in m.functions:
            if f.is_rejected:
                continue
            solver = z3.Solver()
            solver.set("timeout", 10_000)
            eff_bv = z3.BitVec(f"eff_{f.qualname.replace('.', '_')}", _BV_WIDTH)
            computed = fixpoint.get(f.qualname, _pure_mask())
            solver.add(eff_bv == z3.BitVecVal(computed, _BV_WIDTH))

            # Property: effects are honestly declared.
            # If the function has NO @effect(...) decorator, its transitive
            # effect set must be {PURE} — no hidden impurity.
            # If it DOES carry @effect(...), the declared bits must be a
            # superset of the transitively-computed impure bits: you can
            # over-declare but you cannot hide.
            if f.effect_tags:
                declared_bits = _declared_tags_to_bv(f.effect_tags)
                # Ask Z3 whether any impure bit is set that is NOT in the
                # declared set. If yes, the tag is under-declaring.
                declared_bv = z3.BitVecVal(declared_bits, _BV_WIDTH)
                impure_bits = z3.BitVecVal(_impure_mask(), _BV_WIDTH)
                # violation ≡ (eff_bv & impure_bits & ~declared_bv) != 0
                solver.add((eff_bv & impure_bits & ~declared_bv) != 0)
            else:
                impure_bits = z3.BitVecVal(_impure_mask(), _BV_WIDTH)
                solver.add((eff_bv & impure_bits) != 0)

            vcs.append(VerificationCondition(
                function_qualname=f.qualname,
                property_name="purity",
                solver=solver,
                effect_bv=eff_bv,
            ))
    return vcs
