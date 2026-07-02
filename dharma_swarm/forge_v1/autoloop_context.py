"""Context windowing helpers for Forge autoloop."""
from __future__ import annotations

import re

from dharma_swarm.forge_v1.run_real_patch import _read_files_from_image, _target_paths_from_gold
from dharma_swarm.forge_v1.swebench_real import verified_instances


_COMMON_WORDS = {
    "this", "that", "with", "from", "when", "then", "should", "would", "could",
    "change", "behaviour", "behavior", "description", "model", "models", "field",
    "value", "values", "example", "following", "instance", "being", "saved",
    "have", "does", "note", "case", "using", "code", "python", "https", "ticket",
    "issue", "your", "will", "into", "what", "which", "there", "where", "return",
    "result", "output", "expected", "actual", "above", "below", "method", "class",
    "function", "error", "raise", "raises", "test", "tests", "object", "objects",
}


def _keywords(problem: str) -> list[str]:
    """Distinctive identifiers/symbols from the bug report — used to locate the
    relevant region of a too-large file for small-context models."""
    kws = set()
    for m in re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", problem or ""):
        if len(m) >= 4 and m.lower() not in _COMMON_WORDS:
            kws.add(m)
    return list(kws)


def window_context(file_context: dict[str, str], problem: str, *, max_chars: int = 24000,
                   radius_lines: int = 160) -> dict[str, str]:
    """Return a reduced view of each file for endpoints that hang on huge input:
    the contiguous line window (≈2*radius_lines) with the highest density of
    bug-report keywords. The window is a VERBATIM substring of the file, so a
    SEARCH block copied from it still matches the full file at apply time. Files
    already under max_chars pass through unchanged."""
    kws = _keywords(problem)
    out: dict[str, str] = {}
    for path, content in file_context.items():
        if len(content) <= max_chars or not kws:
            out[path] = content
            continue
        lines = content.splitlines(keepends=True)
        score = [sum(1 for k in kws if k in ln) for ln in lines]
        win = min(len(lines), 2 * radius_lines)
        cur = sum(score[:win])
        best, best_lo = cur, 0
        for lo in range(1, len(lines) - win + 1):
            cur += score[lo + win - 1] - score[lo - 1]
            if cur > best:
                best, best_lo = cur, lo
        windowed = "".join(lines[best_lo:best_lo + win])
        out[path] = windowed[:max_chars]
    return out


def pull_context(instance_id: str):
    inst = verified_instances(instance_ids=[instance_id])[0]
    paths = _target_paths_from_gold(inst)
    ctx = _read_files_from_image(inst, paths)
    return inst, ctx
