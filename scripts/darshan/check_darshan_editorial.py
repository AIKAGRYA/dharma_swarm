"""Mechanical gate for the Darshan editorial pipeline.

Validates every article directory under ``reports/darshan/articles/`` against
the pipeline contract in ``docs/plans/DARSHAN_EDITORIAL_PIPELINE_2026-08-19.md``,
which operationalizes the editorial law of
``docs/plans/DARSHAN_CHARTER_2026-07-12.md``. Read-only: this checker writes
nothing anywhere.

Ran by tests/test_darshan_editorial_pipeline.py inside the merge-required
pytest gate, so an article with an incomplete process chain cannot merge.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

DESKS = (
    "bridge",
    "instrument",
    "witness-ledger",
    "noosphere-weather",
    "field-notes",
    "readings-in-fire",
    "polity",
)

REGISTERS = ("FACT", "HYPOTHESIS", "WILD")

VERDICT_RE = re.compile(r"^VERDICT:\s*(SURVIVED|KILLED)\s*$", re.MULTILINE)

REQUIRED_COMPLETE = (
    "commission.json",
    "dossier.md",
    "piece.md",
    "fire_attack.md",
    "fire_counter.md",
    "approval.json",
    "emissions.json",
)


@dataclass
class Finding:
    piece: str
    problem: str

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.piece}: {self.problem}"


def _load_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _check_commission(piece: str, path: Path, findings: list[Finding]) -> None:
    data = _load_json(path)
    if not isinstance(data, dict):
        findings.append(Finding(piece, "commission.json unreadable or not an object"))
        return
    for key in ("desk", "thesis", "why_now", "proposed_by", "approved_by", "date"):
        if not str(data.get(key, "")).strip():
            findings.append(Finding(piece, f"commission.json missing {key}"))
    desk = str(data.get("desk", ""))
    if desk and desk not in DESKS:
        findings.append(
            Finding(piece, f"commission desk {desk!r} is not one of the seven desks")
        )


def _check_registers(piece: str, path: Path, findings: list[Finding]) -> None:
    """Charter law 2: every claim tagged; FACT rows must carry a source."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    rows = re.findall(
        r"^\|\s*(FACT|HYPOTHESIS|WILD)\s*\|(.+)$", text, flags=re.MULTILINE
    )
    if not rows:
        findings.append(
            Finding(piece, "dossier.md has no register-tagged claims table rows")
        )
        return
    for tag, rest in rows:
        if tag == "FACT":
            cells = [c.strip() for c in rest.strip().strip("|").split("|")]
            if len(cells) < 2 or not cells[-1]:
                findings.append(
                    Finding(piece, "FACT claim row without a source cell")
                )


def _check_fire(piece: str, path: Path, findings: list[Finding]) -> str | None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = VERDICT_RE.search(text)
    if not match:
        findings.append(
            Finding(piece, f"{path.name} has no 'VERDICT: SURVIVED|KILLED' line")
        )
        return None
    return match.group(1)


def _check_approval(piece: str, path: Path, findings: list[Finding]) -> None:
    data = _load_json(path)
    if not isinstance(data, dict):
        findings.append(Finding(piece, "approval.json unreadable or not an object"))
        return
    for key in ("approved_by", "date"):
        if not str(data.get(key, "")).strip():
            findings.append(Finding(piece, f"approval.json missing {key}"))


def _check_emissions(piece: str, path: Path, findings: list[Finding]) -> None:
    """Charter law 6: a piece that spawns nothing downstream is decoration."""
    data = _load_json(path)
    items = data.get("emissions") if isinstance(data, dict) else data
    if not isinstance(items, list) or not items:
        findings.append(
            Finding(piece, "emissions.json has no downstream work items (law 6)")
        )


def _check_killed(piece: str, path: Path, findings: list[Finding]) -> None:
    """Charter law 5: salvage with every kill."""
    data = _load_json(path)
    if not isinstance(data, dict):
        findings.append(Finding(piece, "killed.json unreadable or not an object"))
        return
    for key in ("stage", "reason", "salvage"):
        if not str(data.get(key, "")).strip():
            findings.append(Finding(piece, f"killed.json missing {key} (law 5)"))


def check_piece_dir(piece_dir: Path, root: Path) -> list[Finding]:
    piece = piece_dir.relative_to(root).as_posix()
    findings: list[Finding] = []

    desk_dir = piece_dir.parent.name
    if desk_dir not in DESKS:
        findings.append(
            Finding(piece, f"desk directory {desk_dir!r} is not one of the seven desks")
        )

    if (piece_dir / "killed.json").is_file():
        _check_killed(piece, piece_dir / "killed.json", findings)
        if (piece_dir / "commission.json").is_file():
            _check_commission(piece, piece_dir / "commission.json", findings)
        else:
            findings.append(
                Finding(piece, "killed piece still needs its commission.json")
            )
        return findings

    for name in REQUIRED_COMPLETE:
        if not (piece_dir / name).is_file():
            findings.append(Finding(piece, f"missing required artifact {name}"))
    if findings and any("missing required" in f.problem for f in findings):
        return findings

    _check_commission(piece, piece_dir / "commission.json", findings)
    _check_registers(piece, piece_dir / "dossier.md", findings)
    attack = _check_fire(piece, piece_dir / "fire_attack.md", findings)
    counter = _check_fire(piece, piece_dir / "fire_counter.md", findings)
    if attack == "KILLED" or counter == "KILLED":
        findings.append(
            Finding(
                piece,
                "a fire verdict is KILLED but the piece has no killed.json "
                "(only the double-survivor advances; law 1)",
            )
        )
    _check_approval(piece, piece_dir / "approval.json", findings)
    _check_emissions(piece, piece_dir / "emissions.json", findings)
    return findings


def check_articles_root(root: Path) -> list[Finding]:
    """Validate every piece directory. An absent or empty tree is lawful."""
    if not root.is_dir():
        return []
    findings: list[Finding] = []
    for desk_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for piece_dir in sorted(p for p in desk_dir.iterdir() if p.is_dir()):
            findings.extend(check_piece_dir(piece_dir, root))
    return findings


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    root = Path(args[0]) if args else Path("reports/darshan/articles")
    findings = check_articles_root(root)
    for finding in findings:
        print(f"DARSHAN-EDITORIAL VIOLATION — {finding}", file=sys.stderr)
    if findings:
        return 1
    print(f"darshan-editorial: OK ({root})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
