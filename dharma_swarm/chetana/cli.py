"""chetana.cli — command-line interface.

Usage:
    python -m dharma_swarm.chetana.cli ingest --kind session ~/path/to/session.jsonl
    python -m dharma_swarm.chetana.cli promote ~/.dharma/knowledge/staging/.../<id>.md
    python -m dharma_swarm.chetana.cli decay --quarantine
    python -m dharma_swarm.chetana.cli gap-scan
    python -m dharma_swarm.chetana.cli palace --render
    python -m dharma_swarm.chetana.cli query "strange loop"
    python -m dharma_swarm.chetana.cli status

Pure-stdlib argparse — no click dependency, so chetana imports cleanly even
when dharma_swarm's CI hasn't installed click yet.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .decay import decay_summary, scan_decay
from .gap_scan import gap_scan, gap_summary, write_gap_queue
from .graph_unifier import coverage_summary, query as unified_query
from .ingest import ingest
from .palace import palace_summary, render_palace
from .promote import promote
from .staging import (
    QUARANTINE_ROOT,
    STAGING_ROOT,
    TRUSTED_DEFAULT,
    list_quarantine,
    list_staged,
    list_trusted,
)


logger = logging.getLogger(__name__)


def _cmd_ingest(args: argparse.Namespace) -> int:
    src_path = Path(args.source).expanduser().resolve() if Path(args.source).expanduser().exists() else args.source
    result = ingest(
        source=src_path,
        source_kind=args.kind,
        title=args.title,
        atom_type=args.type,
        para_class=args.para,
        confidence=args.confidence,
        captured_by=args.captured_by,
        tags=args.tags or [],
        related=args.related or [],
    )
    print(f"chetana.ingest → {result.staged_count} staged, {result.skipped_count} skipped")
    for atom in result.atoms:
        print(f"  → {atom}")
    for note in result.notes:
        print(f"  · {note}")
    return 0


def _cmd_promote(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser().resolve()
    if not path.exists() and STAGING_ROOT.exists():
        # Allow user to pass just the atom_id; resolve under staging root.
        candidates = list(STAGING_ROOT.rglob(f"{args.path}.md"))
        if candidates:
            path = candidates[0]
    result = promote(
        staged_path=path,
        promoted_by=args.promoted_by,
        reviewer=args.reviewer,
        auto_promote=args.auto_promote,
        confidence_override=args.confidence,
    )
    print(f"chetana.promote → {result.decision} ({result.review_status})")
    for note in result.notes:
        print(f"  · {note}")
    if result.trusted_path:
        print(f"  → {result.trusted_path}")
    if result.rationale:
        print(f"  rationale: {result.rationale}")
    return 0 if result.decision != "BLOCK" else 2


def _cmd_decay(args: argparse.Namespace) -> int:
    report = scan_decay(quarantine=args.quarantine, grace_days=args.grace_days)
    print(decay_summary(report))
    if args.json:
        payload = {
            "scanned": report.scanned,
            "stale_count": report.stale_count,
            "quarantined": [str(p) for p in report.quarantined],
            "stale": [a.__dict__ | {"path": str(a.path)} for a in report.stale],
        }
        Path(args.json).expanduser().write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0


def _cmd_gap_scan(args: argparse.Namespace) -> int:
    report = gap_scan(focus_topic=args.focus, min_occurrences=args.min_occurrences)
    print(gap_summary(report))
    if args.queue:
        path = write_gap_queue(report, path=Path(args.queue).expanduser())
        print(f"\nqueue written → {path}")
    return 0


def _cmd_palace(args: argparse.Namespace) -> int:
    out, snap = render_palace()
    print(palace_summary(snap))
    print(f"\ncanvas → {out}")
    return 0


def _cmd_query(args: argparse.Namespace) -> int:
    result = unified_query(args.text, sources=args.sources)
    print(coverage_summary(result))
    print()
    for h in result.hits[: args.limit]:
        print(f"[{h.source}] {h.kind}: {h.id} — {h.label}")
    return 0


def _cmd_status(_args: argparse.Namespace) -> int:
    staged = list_staged()
    trusted = list_trusted()
    quarantined = list_quarantine()
    print("# chetana status")
    print(f"- staged    : {len(staged)} (root: {STAGING_ROOT})")
    print(f"- trusted   : {len(trusted)} (root: {TRUSTED_DEFAULT})")
    print(f"- quarantine: {len(quarantined)} (root: {QUARANTINE_ROOT})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="chetana", description="chetana PKM CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sp_ing = sub.add_parser("ingest", help="capture raw → staged atom")
    sp_ing.add_argument("source", help="path or inline text")
    sp_ing.add_argument(
        "--kind",
        choices=["session", "webclip", "pdf", "note", "wiki_extract", "voice", "external", "synthesis"],
        default="note",
    )
    sp_ing.add_argument("--title", default=None)
    sp_ing.add_argument(
        "--type",
        choices=["atomic", "reference", "method", "framework", "spec", "tool", "concept", "decision"],
        default="atomic",
    )
    sp_ing.add_argument("--para", choices=["P", "A", "R", "Ar"], default=None)
    sp_ing.add_argument("--confidence", type=float, default=0.5)
    sp_ing.add_argument("--captured-by", dest="captured_by", default="chetana.cli")
    sp_ing.add_argument("--tag", action="append", dest="tags", default=[])
    sp_ing.add_argument("--related", action="append", default=[])
    sp_ing.set_defaults(func=_cmd_ingest)

    sp_pr = sub.add_parser("promote", help="staged → trusted (gate check)")
    sp_pr.add_argument("path", help="staged atom path or atom_id")
    sp_pr.add_argument("--promoted-by", dest="promoted_by", default="chetana.cli")
    sp_pr.add_argument("--reviewer", default=None)
    sp_pr.add_argument("--auto-promote", dest="auto_promote", action="store_true")
    sp_pr.add_argument("--confidence", type=float, default=None)
    sp_pr.set_defaults(func=_cmd_promote)

    sp_dec = sub.add_parser("decay", help="scan stale_after, quarantine on demand")
    sp_dec.add_argument("--quarantine", action="store_true")
    sp_dec.add_argument("--grace-days", dest="grace_days", type=int, default=0)
    sp_dec.add_argument("--json", default=None, help="write JSON report to this path")
    sp_dec.set_defaults(func=_cmd_decay)

    sp_gs = sub.add_parser("gap-scan", help="recurring topics + open questions")
    sp_gs.add_argument("--focus", default=None)
    sp_gs.add_argument("--min-occurrences", dest="min_occurrences", type=int, default=2)
    sp_gs.add_argument("--queue", default=None, help="write JSONL queue to this path")
    sp_gs.set_defaults(func=_cmd_gap_scan)

    sp_pal = sub.add_parser("palace", help="render JSON Canvas memory palace")
    sp_pal.add_argument("--render", action="store_true", default=True)
    sp_pal.set_defaults(func=_cmd_palace)

    sp_q = sub.add_parser("query", help="unified graph query")
    sp_q.add_argument("text")
    sp_q.add_argument("--sources", nargs="*", default=None)
    sp_q.add_argument("--limit", type=int, default=20)
    sp_q.set_defaults(func=_cmd_query)

    sp_st = sub.add_parser("status", help="show staged / trusted / quarantine counts")
    sp_st.set_defaults(func=_cmd_status)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
