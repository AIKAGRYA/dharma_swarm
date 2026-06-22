#!/usr/bin/env python3
"""criterion_lint.py — static "criterion smell" linter for ACTIVE_TRACK.yaml.

WHY THIS EXISTS
---------------
A three-model Opus 4.8 audit (2026-06-22) found the track completion gate could
be satisfied by GAMEABLE criteria — green ≠ done. The worst offenders were
caught by hand:

  - a `file_contains` that greps "NATS" inside a file *named* NATS… (tautology)
  - a `file_exists` over a receipt whose body says "VERDICT: NOT CLOSED"
  - a `file_contains` on an IMPORT line that passed on a dead import
  - owned-surface modules that were declared but never created
  - a witness criterion satisfied by a file citing an operator-local /Users/ path

This linter turns that human audit into a repeatable static check so the same
smells cannot creep back in. It does NOT evaluate whether a criterion passes
(that is check_track_status.py); it evaluates whether a criterion, *if it
passed*, would actually prove anything. It is a read-only projection over
ACTIVE_TRACK.yaml — it owns no truth.

Smells (severity):
  tautological_grep        HIGH  file_contains whose literal pattern is a
                                 substring of the target file's own name
  import_only_check        HIGH  file_contains that matches an import line —
                                 passes on a declared-but-uncalled import
  operator_local_path      HIGH  criterion file/pattern names a personal abs
                                 path (/Users/, /home/<user>) — non-reproducible
  missing_owned_surface    HIGH  an owned_surface code module (*.py) declared
                                 by an ACTIVE track does not exist on disk
  presence_proxy_for_run   MED   file_exists on a doc/report for a criterion
                                 whose id claims a RUNTIME fact (landed/closed/
                                 witnessed/live/e2e/dispatch) — existence ≠ ran
  tautological_doc_grep    MED   file_contains on a doc where the pattern is a
                                 word the track itself authored as a heading

`file_not_contains` criteria are the HARDENED kind and are never flagged.

Stdlib-only. Advisory by default (exit 0); `--strict` exits non-zero when any
HIGH smell remains, for a scheduled hygiene sweep.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ACTIVE_TRACK_PATH = Path("docs/governance/ACTIVE_TRACK.yaml")
OUT_JSON = Path("reports/governance/criterion_lint.json")
OUT_MD = Path("reports/governance/criterion_lint.md")

# Words in a criterion id that assert a RUNTIME / closure fact — a fact that
# file existence alone cannot establish.
RUNTIME_ID_WORDS = (
    "landed", "closure", "closed", "witness", "witnessed", "wake", "live",
    "e2e", "dispatch", "wired", "receipt", "receipted", "ran", "probe",
    "round_trip", "roundtrip", "adopted",
)
REGEX_METACHARS = set(r"\^$.|?*+()[]{}")
PERSONAL_PATH_RE = re.compile(r"/Users/|/home/[A-Za-z0-9._-]+/")


def _load_checker():
    """Reuse check_track_status.py's YAML parser + portfolio normalizer."""
    mod_path = Path(__file__).resolve().parent / "check_track_status.py"
    spec = importlib.util.spec_from_file_location("check_track_status", mod_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("check_track_status", mod)
    spec.loader.exec_module(mod)
    return mod


@dataclass
class Smell:
    track: str
    criterion: str
    smell: str
    severity: str          # HIGH | MED
    detail: str


def _alnum(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", s).lower()


def _is_literal(pattern: str) -> bool:
    return not any(c in pattern for c in REGEX_METACHARS)


def _looks_like_doc(file_path: str) -> bool:
    p = file_path.lower()
    return p.endswith((".md", ".rst", ".txt")) and (
        p.startswith("reports/") or p.startswith("docs/"))


def _id_claims_runtime(crit_id: str) -> bool:
    cid = crit_id.lower()
    return any(w in cid for w in RUNTIME_ID_WORDS)


def lint_criterion(track_id: str, crit: dict[str, Any],
                   paired_files: set[str]) -> list[Smell]:
    """Smells for one completion criterion.

    `paired_files` = files in the same track that already carry a content check
    (file_contains / file_not_contains). A presence proxy over such a file is
    already backed by a content/witness assertion, so it is not re-flagged.
    """
    out: list[Smell] = []
    cid = str(crit.get("id", "?"))
    kind = crit.get("kind", "")
    file_path = str(crit.get("file", "") or "")
    pattern = crit.get("pattern")
    pattern = str(pattern) if isinstance(pattern, str) else ""

    # The hardened negative-assertion kind is always good.
    if kind == "file_not_contains":
        return out

    # A pattern that is a single bareword (no space, no ":") is heading-like and
    # can be tautological; a "KEY: VALUE" or multi-word phrase is a real status
    # assertion (e.g. "VERDICT: CLOSED") and is NOT a smell.
    single_token = bool(pattern) and not re.search(r"[\s:]", pattern)

    # operator-local absolute path anywhere in the criterion target.
    if PERSONAL_PATH_RE.search(file_path) or PERSONAL_PATH_RE.search(pattern):
        out.append(Smell(track_id, cid, "operator_local_path", "HIGH",
            f"criterion names a personal absolute path — not reproducible "
            f"({file_path or pattern!r})"))

    if kind == "file_contains" and pattern:
        stem = _alnum(Path(file_path).stem)
        core = _alnum(pattern)
        # tautological grep: a single-word literal already in the file's name.
        if single_token and _is_literal(pattern) and len(core) >= 3 and core in stem:
            out.append(Smell(track_id, cid, "tautological_grep", "HIGH",
                f"pattern {pattern!r} is contained in the target file name "
                f"'{Path(file_path).name}' — passes tautologically"))
        # import-only check: passes on a declared-but-uncalled import.
        if re.search(r"\bimport\b|from\s+[\w.]+", pattern):
            out.append(Smell(track_id, cid, "import_only_check", "HIGH",
                f"pattern {pattern!r} matches an import line — green on a dead "
                "import; assert an actual call/usage instead"))
        # tautological doc grep: a single-word literal matched in a doc for a
        # runtime-claim id (a real status phrase has whitespace/':' and is fine).
        if single_token and _looks_like_doc(file_path) and _is_literal(pattern) and \
                "tautological_grep" not in {s.smell for s in out} and \
                _id_claims_runtime(cid):
            out.append(Smell(track_id, cid, "tautological_doc_grep", "MED",
                f"runtime-claim id '{cid}' verified by grepping a single word in "
                f"a doc ({Path(file_path).name}) — prose match, not behavior"))

    if kind == "file_exists" and _looks_like_doc(file_path) and \
            _id_claims_runtime(cid) and file_path not in paired_files:
        out.append(Smell(track_id, cid, "presence_proxy_for_run", "MED",
            f"id '{cid}' claims a runtime fact but only checks that a doc "
            f"exists ({Path(file_path).name}); existence ≠ the thing ran — "
            "pair with a content/witness check"))

    return out


def lint_track_surfaces(track: dict[str, Any]) -> list[Smell]:
    """Owned code surfaces (*.py, non-glob) that an ACTIVE track declares but
    that do not exist on disk — the nats failure mode."""
    out: list[Smell] = []
    tid = str(track.get("id", "?"))
    for surf in track.get("owned_surfaces") or []:
        s = str(surf)
        if s.endswith(".py") and "*" not in s and not Path(s).exists():
            out.append(Smell(tid, f"owned_surface:{s}", "missing_owned_surface",
                "HIGH", f"declared owned surface '{s}' does not exist on disk"))
    return out


def run(args: argparse.Namespace) -> int:
    if not ACTIVE_TRACK_PATH.exists():
        print(f"ERROR: {ACTIVE_TRACK_PATH} not found", file=sys.stderr)
        return 2
    checker = _load_checker()
    raw = checker.load_active_track(ACTIVE_TRACK_PATH)
    portfolio = checker.normalize_portfolio(raw)
    active = [t for t in portfolio["active_tracks"] if checker._is_active(t)]

    smells: list[Smell] = []
    per_track_counts: dict[str, dict[str, int]] = {}
    for t in active:
        tid = str(t.get("id"))
        crits = t.get("completion_criteria") or []
        # Files already covered by a content check in this track — a presence
        # proxy over one of these is already paired and not re-flagged.
        paired_files = {
            str(c.get("file")) for c in crits
            if isinstance(c, dict) and c.get("kind") in ("file_contains", "file_not_contains")
            and c.get("file")
        }
        tsmells: list[Smell] = []
        for c in crits:
            if isinstance(c, dict):
                tsmells.extend(lint_criterion(tid, c, paired_files))
        tsmells.extend(lint_track_surfaces(t))
        smells.extend(tsmells)
        per_track_counts[tid] = {
            "criteria": len(crits),
            "smells": len(tsmells),
            "high": sum(1 for s in tsmells if s.severity == "HIGH"),
        }

    high = [s for s in smells if s.severity == "HIGH"]
    med = [s for s in smells if s.severity == "MED"]
    emit(smells, per_track_counts, high, med)

    for s in smells:
        stream = sys.stderr if s.severity == "HIGH" else sys.stdout
        print(f"{s.severity}: {s.smell}: [{s.track}] {s.criterion} — {s.detail}",
              file=stream)
    print(f"\nSUMMARY: {len(high)} HIGH, {len(med)} MED smells across "
          f"{len(active)} active tracks.")
    if args.strict and high:
        print(f"STRICT: {len(high)} HIGH criterion smell(s) — failing.",
              file=sys.stderr)
        return 1
    return 0


def emit(smells: list[Smell], counts: dict[str, dict[str, int]],
         high: list[Smell], med: list[Smell]) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "summary": {"high": len(high), "med": len(med),
                    "tracks": len(counts)},
        "per_track": counts,
        "smells": [asdict(s) for s in smells],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    md = ["# Criterion smell report",
          "",
          f"Generated: {payload['generated_at']}",
          "",
          "Static lint of `ACTIVE_TRACK.yaml` completion criteria: would each "
          "criterion, *if it passed*, actually prove the capability? Read-only "
          "projection — it does not evaluate pass/fail (that is "
          "`check_track_status.py`).",
          "",
          f"**{len(high)} HIGH · {len(med)} MED** smells across "
          f"{len(counts)} active tracks.",
          "",
          "| Track | criteria | smells | HIGH |",
          "|---|---|---|---|"]
    for tid, c in counts.items():
        md.append(f"| `{tid}` | {c['criteria']} | {c['smells']} | {c['high']} |")
    md.append("")
    if smells:
        md.append("## Findings")
        md.append("")
        for sev in ("HIGH", "MED"):
            group = [s for s in smells if s.severity == sev]
            if not group:
                continue
            md.append(f"### {sev}")
            md.append("")
            for s in group:
                md.append(f"- **{s.smell}** · `{s.track}` / `{s.criterion}` — {s.detail}")
            md.append("")
    else:
        md.append("No criterion smells found — the gate is clean. ✅")
        md.append("")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true",
                    help="Exit non-zero if any HIGH criterion smell remains.")
    return run(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main())
