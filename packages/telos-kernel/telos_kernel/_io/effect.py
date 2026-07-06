"""Effect tagging for the I/O rim.

Every rim function is decorated with `@effect(...)` naming the external
effects it may perform. This is:

  1. Documentation \u2014 the effect set is visible at the call site.
  2. Introspectable \u2014 `fn.__effects__` is a frozenset.
  3. Enforceable \u2014 `test_no_effects_in_core.py` walks the AST of every
     core module and asserts no imports from `_io`.

We do not attempt a full effect-typing system. The purpose is discipline,
not soundness: soundness comes from the import-boundary check that keeps
these functions out of the verified core in the first place.

References
- Wadler & Thiemann, \"The marriage of effects and monads\" (TOCL 2003).
- Koka's effect rows: https://koka-lang.github.io/koka/doc/book.html#sec-effects.
"""
from __future__ import annotations

import enum
import functools
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable)


class Effect(str, enum.Enum):
    FS_READ = "fs_read"
    FS_WRITE = "fs_write"
    NET = "net"
    SUBPROCESS = "subprocess"
    NONDETERMINISTIC = "nondeterministic"  # clock, random, uuid4


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
