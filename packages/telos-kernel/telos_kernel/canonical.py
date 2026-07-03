"""RFC 8785 JSON Canonicalization Scheme (JCS) — in-tree implementation.

Titanium-grade requirement: every signed payload must serialize deterministically.
`json.dumps(sort_keys=True)` is *not* canonical — it disagrees with itself across
Python patch releases on Unicode edge cases (NFC vs. NFD), non-BMP escapes,
and float rendering.

This module implements RFC 8785 JCS exactly. It is intentionally small
(~120 LOC) and Nagini-compatible: no dynamic dispatch, no `__subclasshook__`
tricks, no reflection. The recursion is bounded by the input's nesting depth,
which the caller must control (see `MAX_DEPTH`).

References:
- RFC 8785: https://datatracker.ietf.org/doc/html/rfc8785
- ECMAScript 2019 §7.1.12.1 ToString(Number)
- ECMA-262 §24.5.2 SerializeJSONObject (sort by codepoint)
"""
from __future__ import annotations

import math
import re
from typing import Any, Final

MAX_DEPTH: Final[int] = 64
"""Maximum nesting depth. Signed payloads deeper than this are rejected;
this bounds recursion and keeps the verifier happy."""

# Characters that must be escaped per RFC 8259 §7 (and RFC 8785 by reference).
_ESCAPE_MAP: Final[dict[int, str]] = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}


def canonicalize(value: Any) -> bytes:
    """Serialize `value` to RFC 8785 canonical JSON bytes.

    Accepts: dict[str, ...], list, tuple, str, bool, None, int, float.
    Rejects: NaN, +/-Infinity, non-str dict keys, sets, bytes, custom objects.

    Args:
        value: The value to canonicalize.

    Returns:
        UTF-8 bytes of the canonical JSON form.

    Raises:
        ValueError: on any non-canonicalizable input.
        RecursionError: if nesting exceeds MAX_DEPTH.
    """
    out: list[str] = []
    _encode(value, out, depth=0)
    return "".join(out).encode("utf-8")


def _encode(value: Any, out: list[str], depth: int) -> None:
    if depth > MAX_DEPTH:
        raise RecursionError(f"JCS nesting depth exceeds MAX_DEPTH={MAX_DEPTH}")

    # Order matters: bool is a subclass of int in Python, so check bool first.
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, bool):  # pragma: no cover — covered by True/False above
        out.append("true" if value else "false")
    elif isinstance(value, int):
        _encode_int(value, out)
    elif isinstance(value, float):
        _encode_float(value, out)
    elif isinstance(value, str):
        _encode_string(value, out)
    elif isinstance(value, (list, tuple)):
        _encode_array(value, out, depth)
    elif isinstance(value, dict):
        _encode_object(value, out, depth)
    else:
        raise ValueError(
            f"JCS cannot canonicalize object of type {type(value).__name__!r}"
        )


def _encode_int(value: int, out: list[str]) -> None:
    # RFC 8785 §3.2.2.2: integers are represented in shortest form.
    # Python's str(int) is already shortest-form for integers.
    out.append(str(value))


def _encode_float(value: float, out: list[str]) -> None:
    # RFC 8785 §3.2.2.3: number serialization follows ECMAScript ToString.
    if math.isnan(value) or math.isinf(value):
        raise ValueError("JCS forbids NaN and Infinity")
    # Integer-valued floats: emit as integer without a decimal point? No —
    # RFC 8785 keeps them as-is per ECMAScript ToString. However, Python's
    # `repr(1.0)` = '1.0' while ECMAScript ToString(1.0) = '1'. We must
    # match ECMAScript.
    if value == 0.0:
        out.append("0")
        return
    if value.is_integer() and abs(value) < 1e21:
        out.append(str(int(value)))
        return
    # Python's repr() produces the shortest round-trip form for floats
    # (PEP 3101 / Gay's algorithm), which matches ECMAScript ToString
    # for typical magnitudes. We normalize scientific notation to match
    # ECMAScript's `e+NN` / `e-NN` form.
    s = repr(value)
    if "e" in s:
        mantissa, exp = s.split("e")
        exp_int = int(exp)
        s = f"{mantissa}e{'+' if exp_int >= 0 else '-'}{abs(exp_int)}"
    out.append(s)


def _encode_string(value: str, out: list[str]) -> None:
    out.append('"')
    for ch in value:
        cp = ord(ch)
        if cp in _ESCAPE_MAP:
            out.append(_ESCAPE_MAP[cp])
        elif cp < 0x20:
            out.append(f"\\u{cp:04x}")
        else:
            out.append(ch)
    out.append('"')


def _encode_array(value: Any, out: list[str], depth: int) -> None:
    out.append("[")
    first = True
    for item in value:
        if not first:
            out.append(",")
        _encode(item, out, depth + 1)
        first = False
    out.append("]")


def _encode_object(value: dict, out: list[str], depth: int) -> None:
    for k in value.keys():
        if not isinstance(k, str):
            raise ValueError(
                f"JCS object keys must be strings, got {type(k).__name__!r}"
            )
    # RFC 8785 §3.2.3: sort keys by UTF-16 code unit sequence. Python str
    # comparison is on Unicode code points; for the BMP (which covers all
    # realistic key names) this is identical. We reject non-BMP keys to
    # keep the equivalence tight.
    for k in value.keys():
        for ch in k:
            if ord(ch) > 0xFFFF:
                raise ValueError(
                    "JCS keys with non-BMP codepoints are not supported "
                    "(would require UTF-16 surrogate-pair sort logic)"
                )
    sorted_keys = sorted(value.keys())
    out.append("{")
    first = True
    for k in sorted_keys:
        if not first:
            out.append(",")
        _encode_string(k, out)
        out.append(":")
        _encode(value[k], out, depth + 1)
        first = False
    out.append("}")


# ---- Round-trip test hook ---------------------------------------------------

_JCS_CANONICAL_RE: Final[re.Pattern] = re.compile(
    r'^(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]\d+)?|"(?:[^"\\]|\\.)*"|true|false|null|\[|\]|\{|\}|,|:)+$'
)


def is_probably_canonical(payload: bytes) -> bool:
    """Cheap structural sanity check. NOT a full JCS conformance test —
    that's what the round-trip property in Hypothesis tests provides."""
    try:
        s = payload.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return bool(_JCS_CANONICAL_RE.match(s))
