"""icontract pre/post-conditions consolidated for kernel-exported functions.

The hardwiring plan calls for a single-file contracts module (not a subpackage).
Contracts live *next to* their functions via `@require`/`@ensure` decorators
on the kernel modules themselves; this file provides the shared invariants and
helpers used by those decorators.
"""
from __future__ import annotations

import re
from typing import Any

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


def is_hex_hash(s: Any) -> bool:
    return isinstance(s, str) and bool(_HEX_64.match(s))


def is_iso_utc(ts: Any) -> bool:
    if not isinstance(ts, str):
        return False
    # Accept trailing 'Z' or '+00:00'; reject naive timestamps.
    return ts.endswith("Z") or ts.endswith("+00:00")


def is_verdict(v: Any) -> bool:
    return isinstance(v, str) and v in {"ALLOW", "WARN", "REVIEW", "BLOCK"}


def is_tier(t: Any) -> bool:
    return isinstance(t, str) and t in {"A", "B", "C"}
