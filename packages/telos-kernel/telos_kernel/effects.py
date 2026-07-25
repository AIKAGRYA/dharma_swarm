"""Effect tags — pure labels attached to core and rim functions.

The decorator itself is pure: it wraps a function and stamps it with a
frozenset `__effects__`. No I/O, no state.

Effect labels serve three purposes:
  1. Documentation — the effect set is visible at the call site.
  2. Introspection — `fn.__effects__` is a frozenset callers can inspect.
  3. Verification — `titanium-verify` reads @effect(...) decorations and
     requires every non-pure core function to honestly declare its effects.
     Hiding an impurity is caught by the verifier's fixpoint analysis.

This module lives in core (not _io/) because tagging is itself a pure
operation — the tag doesn't perform the effect. Actual I/O still lives
exclusively in `telos_kernel/_io/`.

References:
- Wadler & Thiemann, \"The marriage of effects and monads\" (TOCL 2003).
- Koka's effect rows: https://koka-lang.github.io/koka/doc/book.html#sec-effects.
"""
from __future__ import annotations

import enum
import functools
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable)


class Effect(str, enum.Enum):
    # Uppercase values so titanium-verify's Effect enum matches by name.
    FS_READ = "FS_READ"
    FS_WRITE = "FS_WRITE"
    NET = "NET"
    SUBPROCESS = "SUBPROCESS"
    NONDETERMINISTIC = "NONDETERMINISTIC"  # clock, random, uuid4


def effect(*effects: Effect) -> Callable[[F], F]:
    """Attach an effect set to a function.

    Usage:
        @effect(Effect.FS_READ, Effect.SUBPROCESS)
        def load_something(...): ...
    """
    frozen = frozenset(effects)

    def deco(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            return fn(*a, **kw)

        wrapper.__effects__ = frozen  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return deco
