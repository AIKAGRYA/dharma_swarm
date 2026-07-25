"""Result[T, E] \u2014 an explicit success/failure ADT for kernel functions.

Every fail-closed path in the TCB used to swallow a broad `except (A, B, C)`
and return `False`, `None`, or an empty value. This works at runtime but is
opaque to sound static verifiers:

  - Nagini cannot express \"function returns False iff any of these exceptions
    would have fired\" without hand-written postconditions on every call site.
  - Crosshair cannot bind counterexamples to specific failure modes.
  - Downstream callers cannot distinguish \"legitimate false\" from \"crashed
    and hid it\".

`Result` replaces the pattern:

    try:
        ...
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False

with:

    r = ...
    if r.is_err:
        return r  # or map err
    ...

The `err` variant carries a short machine-readable code plus an optional
message, and the whole ADT is frozen so `titanium-verify` can enumerate
its shape statically.

References
- Rust's Result<T, E>: https://doc.rust-lang.org/std/result/
- Wadler, \"Monads for functional programming\" (1995) \u00a72.5 (exception monad).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Final, Generic, TypeVar

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    value: T
    is_ok: Final[bool] = True
    is_err: Final[bool] = False

    def unwrap(self) -> T:
        return self.value

    def unwrap_or(self, default: T) -> T:  # noqa: ARG002
        return self.value

    def map(self, f: Callable[[T], U]) -> "Result[U, E]":
        return Ok(f(self.value))  # type: ignore[return-value]

    def and_then(self, f: Callable[[T], "Result[U, E]"]) -> "Result[U, E]":
        return f(self.value)


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    error: E
    is_ok: Final[bool] = False
    is_err: Final[bool] = True

    def unwrap(self):  # noqa: ANN201
        raise ValueError(f"Err.unwrap(): {self.error!r}")

    def unwrap_or(self, default: T) -> T:
        return default

    def map(self, f):  # noqa: ANN001, ANN201, ARG002
        return self

    def and_then(self, f):  # noqa: ANN001, ANN201, ARG002
        return self


# Public alias. `Result[T, E]` is a discriminated union of `Ok[T]` and `Err[E]`.
# titanium-verify treats this as a pattern-matchable sum type.
Result = Ok | Err


# ---- Common error codes ---------------------------------------------------
# String-typed error codes give us grep-ability without paying for a giant
# enum. Any code added here should be documented in SECURITY.md if it
# changes trust-boundary behavior.

ERR_INVALID_SIGNATURE: Final[str] = "invalid_signature"
ERR_MALFORMED_HEX: Final[str] = "malformed_hex"
ERR_UNKNOWN_SIGNER: Final[str] = "unknown_signer"
ERR_QUORUM_NOT_MET: Final[str] = "quorum_not_met"
ERR_STUB_SIGNERS: Final[str] = "stub_signers_present"
ERR_CHAIN_BROKEN: Final[str] = "chain_broken"
ERR_TIMESTAMP_INVALID: Final[str] = "timestamp_invalid"
ERR_CAVEAT_FAILED: Final[str] = "caveat_failed"
ERR_UNCANONICALIZABLE: Final[str] = "uncanonicalizable_value"
ERR_IO: Final[str] = "io_error"
ERR_GIT_UNAVAILABLE: Final[str] = "git_unavailable"


@dataclass(frozen=True, slots=True)
class KernelError:
    """Structured error carrier. Small on purpose."""

    code: str
    message: str = ""
    detail: dict | None = None

    def __str__(self) -> str:
        if self.message:
            return f"{self.code}: {self.message}"
        return self.code
