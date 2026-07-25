"""TCB size ceiling — SECURITY.md §1: TCB LOC ≤ 5 000."""
from __future__ import annotations

from pathlib import Path

KERNEL_ROOT = Path(__file__).resolve().parents[1]
TCB_LOC_CEILING = 5000


def _tcb_files() -> list[Path]:
    return [
        p for p in sorted(KERNEL_ROOT.rglob("*.py"))
        if "/tests/" not in str(p).replace("\\", "/")
    ]


def _count_lines(path: Path) -> int:
    """Non-blank, non-comment lines (SLOC)."""
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        n += 1
    return n


def test_tcb_loc_ceiling():
    total = sum(_count_lines(p) for p in _tcb_files())
    print(f"TCB SLOC = {total}")
    assert total <= TCB_LOC_CEILING, (
        f"TCB SLOC={total} exceeds ceiling={TCB_LOC_CEILING}. "
        f"Widening the TCB requires a manifest edit under K=3/N=5 quorum (§U2)."
    )


def test_per_file_breakdown_is_readable():
    """Not an assertion — prints the per-file breakdown to aid budget planning."""
    for p in _tcb_files():
        print(f"  {_count_lines(p):5d}  {p.relative_to(KERNEL_ROOT)}")
