"""Object-capability tokens — macaroon-shaped.

Miller ocap discipline (Robust Composition, 2006): designation = authorization.
Attenuation is a first-class *caveat append* — never a re-mint — which makes
attenuation strictly monotone (never widens authority).

References:
  * Birgisson et al., "Macaroons: Cookies with Contextual Caveats" (NDSS 2014).
    https://research.google/pubs/pub41892/
  * Miller, "Robust Composition" PhD thesis, 2006.
    https://worrydream.com/refs/Miller_2006_-_Robust_Composition.pdf

Design notes:
  * We ship an in-tree ~180 LOC macaroon rather than pull `pymacaroons`.
    The kernel dep surface stays tight, and Nagini can reason about the
    entire implementation.
  * HMAC-SHA-256 chain per macaroons spec: `sig_i = HMAC(sig_{i-1}, caveat_i)`.
  * First-party caveats only in Phase 0. Third-party (discharge) caveats
    are Phase 6+ (they need bidirectional trust seams).
"""
from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Callable, Final

from icontract import ensure, require

from telos_kernel.effects import Effect, effect
from telos_kernel.result import (
    ERR_CAVEAT_FAILED,
    ERR_INVALID_SIGNATURE,
    ERR_MALFORMED_HEX,
    Err,
    KernelError,
    Ok,
    Result,
)

_SECRET_BYTES: Final[int] = 32
_MIN_KEY_BYTES: Final[int] = 32


class CapabilityError(Exception):
    """Raised when a capability check fails or a token is malformed."""


@dataclass(frozen=True)
class Caveat:
    """A first-party predicate that must be satisfied when the token is used.

    `predicate` is a canonical string, e.g. `"tier <= B"`, `"gate == U5_merkle"`,
    `"proposal_id == 3fa85f64-..."`. Verifiers evaluate caveats against a
    context dict; unknown predicates fail closed.
    """
    predicate: str


@dataclass(frozen=True)
class Macaroon:
    """An attenuable capability token.

    Attributes:
        identifier: opaque handle to the root secret (never the secret itself).
        location: kernel-level scope, e.g. "telos-kernel/gate".
        caveats: ordered list of first-party predicates.
        signature: HMAC-SHA-256 chain terminator (hex).
    """
    identifier: str
    location: str
    caveats: tuple[Caveat, ...]
    signature: str  # hex


def _is_concrete_bytes(value: object, min_len: int = 0) -> bool:
    return type(value) is bytes and len(value) >= min_len


def _is_concrete_str(value: object) -> bool:
    return type(value) is str


def _is_hex_digest(value: object) -> bool:
    if type(value) is not str or len(value) != 64:
        return False
    try:
        bytes.fromhex(value)
    except ValueError:
        return False
    return True


# ---- Minting ---------------------------------------------------------------

@require(lambda root_key: _is_concrete_bytes(root_key, _MIN_KEY_BYTES))
@require(lambda identifier: _is_concrete_str(identifier))
@require(lambda location: _is_concrete_str(location))
def mint(root_key: bytes, identifier: str, location: str) -> Macaroon:
    """Mint a fresh unattenuated macaroon."""
    sig = hmac.new(root_key, identifier.encode("utf-8"), sha256).hexdigest()
    return Macaroon(identifier=identifier, location=location, caveats=(), signature=sig)


# ---- Attenuation (monotone) ------------------------------------------------

@require(lambda m: isinstance(m, Macaroon))
@require(lambda m: _is_hex_digest(m.signature))
@require(lambda predicate: _is_concrete_str(predicate))
@ensure(lambda result, m: len(result.caveats) == len(m.caveats) + 1)
def add_first_party_caveat(m: Macaroon, predicate: str) -> Macaroon:
    """Append a first-party caveat. Never widens authority."""
    new_sig = hmac.new(
        bytes.fromhex(m.signature), predicate.encode("utf-8"), sha256
    ).hexdigest()
    return Macaroon(
        identifier=m.identifier,
        location=m.location,
        caveats=m.caveats + (Caveat(predicate),),
        signature=new_sig,
    )


# ---- Verification ----------------------------------------------------------

def _recompute_signature(root_key: bytes, m: Macaroon) -> str:
    sig = hmac.new(root_key, m.identifier.encode("utf-8"), sha256).hexdigest()
    for c in m.caveats:
        sig = hmac.new(bytes.fromhex(sig), c.predicate.encode("utf-8"), sha256).hexdigest()
    return sig


# A CaveatChecker takes (predicate_string, context_dict) and returns True/False.
CaveatChecker = Callable[[str, dict], bool]


def _default_checker(predicate: str, context: dict) -> bool:
    """Minimal first-party caveat language for Phase 0:
        - "gate == <string>"
        - "tier <= <A|B|C>"
        - "proposal_id == <uuid>"
    Any other predicate fails closed (returns False).
    """
    p = predicate.strip()
    if p.startswith("gate == "):
        return context.get("gate") == p.removeprefix("gate == ").strip()
    if p.startswith("proposal_id == "):
        return context.get("proposal_id") == p.removeprefix("proposal_id == ").strip()
    if p.startswith("tier <= "):
        expected = p.removeprefix("tier <= ").strip()
        got = context.get("tier")
        order = {"A": 0, "B": 1, "C": 2}
        if expected not in order or got not in order:
            return False
        return order[got] <= order[expected]
    return False


@require(lambda root_key: _is_concrete_bytes(root_key, _MIN_KEY_BYTES))
def verify_result(
    m: Macaroon,
    root_key: bytes,
    context: dict,
    checker: CaveatChecker | None = None,
) -> Result:
    """Structured-result verify. See `verify()` for the boolean shim.

    Returns `Ok(True)` on full success, or `Err(KernelError)` naming the
    specific failure mode. Never raises — capability checks fail closed.
    """
    try:
        expected_sig = _recompute_signature(root_key, m)
    except (TypeError, ValueError) as e:
        return Err(KernelError(ERR_MALFORMED_HEX, str(e)))
    if not hmac.compare_digest(expected_sig, m.signature):
        return Err(KernelError(ERR_INVALID_SIGNATURE, "macaroon signature mismatch"))
    ck = checker if checker is not None else _default_checker
    for c in m.caveats:
        if not ck(c.predicate, context):
            return Err(KernelError(
                ERR_CAVEAT_FAILED,
                f"caveat rejected: {c.predicate!r}",
                detail={"predicate": c.predicate},
            ))
    return Ok(True)


@require(lambda root_key: _is_concrete_bytes(root_key, _MIN_KEY_BYTES))
def verify(
    m: Macaroon,
    root_key: bytes,
    context: dict,
    checker: CaveatChecker | None = None,
) -> bool:
    """Boolean-shim over verify_result() for backwards compatibility.

    New callers should prefer verify_result() so they can distinguish
    signature failure from caveat failure. Returns False on any failure.
    """
    return verify_result(m, root_key, context, checker).is_ok


# ---- Root-key management ---------------------------------------------------

@effect(Effect.NONDETERMINISTIC)
def new_root_key() -> bytes:
    """Generate a fresh 32-byte cryptographically random root key.

    Effect: NONDETERMINISTIC — draws from `secrets.token_bytes`, which uses
    OS entropy. This is the whole point of a root-key generator.
    """
    return secrets.token_bytes(_SECRET_BYTES)
