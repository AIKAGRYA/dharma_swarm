"""Vendored RFC 8785 JSON Canonicalization Scheme encoder.

Receipt identity is SHA-256 over JCS bytes, following
[RFC 8785](https://datatracker.ietf.org/doc/html/rfc8785). This module is a
small local encoder so P0 does not add a runtime dependency.
"""

from __future__ import annotations

import math
from typing import Any

_ESCAPE_MAP: dict[int, str] = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}


def canonicalize(value: Any) -> bytes:
    out: list[str] = []
    _encode(value, out, 0)
    return "".join(out).encode("utf-8")


def _encode(value: Any, out: list[str], depth: int) -> None:
    if depth > 64:
        raise RecursionError("JCS nesting depth exceeds 64")
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, int) and not isinstance(value, bool):
        out.append(str(value))
    elif isinstance(value, float):
        _encode_float(value, out)
    elif isinstance(value, str):
        _encode_string(value, out)
    elif isinstance(value, list):
        _encode_array(value, out, depth)
    elif isinstance(value, dict):
        _encode_object(value, out, depth)
    else:
        raise ValueError(f"JCS cannot encode {type(value).__name__}")


def _encode_float(value: float, out: list[str]) -> None:
    if math.isnan(value) or math.isinf(value):
        raise ValueError("JCS forbids non-finite numbers")
    if value == 0.0:
        out.append("0")
        return
    text = repr(value).lower()
    if "e" in text:
        text = _normalize_exponent_text(text)
    elif text.endswith(".0"):
        text = text[:-2]
    out.append(text)


def _normalize_exponent_text(text: str) -> str:
    mantissa, exponent = text.split("e")
    exponent_int = int(exponent)
    negative = mantissa.startswith("-")
    unsigned = mantissa[1:] if negative else mantissa
    integer_part, _, fraction_part = unsigned.partition(".")
    digits = integer_part + fraction_part
    decimal_index = len(integer_part) + exponent_int
    sign = "-" if negative else ""
    magnitude = abs(float(text))
    if 1e-6 <= magnitude < 1e21:
        if decimal_index <= 0:
            body = "0." + ("0" * -decimal_index) + digits
        elif decimal_index >= len(digits):
            body = digits + ("0" * (decimal_index - len(digits)))
        else:
            body = digits[:decimal_index] + "." + digits[decimal_index:]
        if "." in body:
            body = body.rstrip("0").rstrip(".")
        return sign + body
    exp = decimal_index - 1
    if len(digits) == 1:
        body = digits
    else:
        body = (digits[0] + "." + digits[1:]).rstrip("0").rstrip(".")
    exp_sign = "+" if exp >= 0 else "-"
    return f"{sign}{body}e{exp_sign}{abs(exp)}"


def _encode_string(value: str, out: list[str]) -> None:
    out.append('"')
    for char in value:
        codepoint = ord(char)
        if 0xD800 <= codepoint <= 0xDFFF:
            raise ValueError("JCS forbids lone surrogate codepoints")
        escaped = _ESCAPE_MAP.get(codepoint)
        if escaped is not None:
            out.append(escaped)
        elif codepoint < 0x20:
            out.append(f"\\u{codepoint:04x}")
        else:
            out.append(char)
    out.append('"')


def _encode_array(value: list[Any], out: list[str], depth: int) -> None:
    out.append("[")
    for index, item in enumerate(value):
        if index:
            out.append(",")
        _encode(item, out, depth + 1)
    out.append("]")


def _encode_object(value: dict[Any, Any], out: list[str], depth: int) -> None:
    for key in value:
        if not isinstance(key, str):
            raise ValueError("JCS object keys must be strings")
    out.append("{")
    for index, key in enumerate(sorted(value, key=_utf16_sort_key)):
        if index:
            out.append(",")
        _encode_string(key, out)
        out.append(":")
        _encode(value[key], out, depth + 1)
    out.append("}")


def _utf16_sort_key(value: str) -> list[int]:
    encoded = value.encode("utf-16-be", "surrogatepass")
    return [
        (encoded[index] << 8) + encoded[index + 1]
        for index in range(0, len(encoded), 2)
    ]
