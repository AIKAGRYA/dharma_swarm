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
import inspect
import json
import logging
import sys
from pathlib import Path

from .decay import decay_summary, scan_decay
from .cross_update import cross_update_summary, cross_update_trusted
from .gap_scan import gap_scan, gap_summary, write_gap_queue
from .graph_unifier import coverage_summary, query as unified_query
from .ingest import ingest
from .palace import palace_summary, render_palace
from .promote import promote
from .revival import (
    apply_revival,
    find_due_atoms,
    propose_revival,
    revival_summary,
)
from .staging import (
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


def _cmd_revive(args: argparse.Namespace) -> int:
    """Propose (or apply) revival for stale atoms."""
    targets: list = []
    if args.all:
        targets = find_due_atoms(grace_days=args.grace_days)
    else:
        targets = [Path(args.path).expanduser().resolve()]
    proposals = []
    for t in targets:
        try:
            p = propose_revival(atom_path=t, extend_days=args.extend_days)
        except Exception as e:
            print(f"  · skipped {t}: {e}")
            continue
        proposals.append(p)
        if args.apply:
            new_path = apply_revival(p, reviewer=args.reviewer)
            print(f"  ✓ revived {new_path}")
    print(revival_summary(proposals))
    return 0


def _cmd_decay(args: argparse.Namespace) -> int:
    report = scan_decay(quarantine=args.quarantine, grace_days=args.grace_days)
    print(decay_summary(report))
    if not args.quarantine and report.stale_count > 0:
        print(
            "\n→ Default chetana response to stale is REVIVE, not quarantine. "
            "Run `chetana revive --all` to re-research and re-integrate."
        )
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


def _cmd_cross_update(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser().resolve()
    if not path.exists() and TRUSTED_DEFAULT.exists():
        candidates = list(TRUSTED_DEFAULT.glob(f"{args.path}.md"))
        if candidates:
            path = candidates[0]
    result = cross_update_trusted(path)
    print(cross_update_summary(result))
    for related in result.missing_related:
        print(f"  · missing related page: {related}")
    return 0


def _cmd_approve(args: argparse.Namespace) -> int:
    """Human-explicit approval transitioning staged → approved.

    Distinct from `chetana promote`:
      - promote: gates check + sigs computed + atom enters trusted with
        review_status = staged | auto_promoted | rejected
      - approve: human explicitly accepts a staged atom; review_status →
        approved. This is the path the `approved` literal was reserved for
        but had no CLI surface until now (D2 fix per 2026-04-28 plan).

    Accepts either a staged-atom path OR an already-trusted atom whose
    review_status is staged|auto_promoted (post-promote, pre-human-review).
    Updates provenance.review_status to "approved", sets reviewer, appends
    an approval event to revival_chain. If the atom is still in staging,
    moves it to the trusted layer.
    """
    from .provenance import parse_frontmatter, now_iso
    from .staging import STAGING_ROOT, write_trusted

    path = Path(args.path).expanduser().resolve()
    if not path.exists():
        # Try resolving as atom_id under staging
        candidates = list(STAGING_ROOT.rglob(f"{args.path}.md")) if STAGING_ROOT.exists() else []
        if candidates:
            path = candidates[0]
    if not path.exists():
        print(f"error: {args.path} not found")
        return 2

    text = path.read_text(encoding="utf-8")
    try:
        schema, body = parse_frontmatter(text, source_path=str(path))
    except Exception as e:
        print(f"error: cannot parse atom: {e}")
        return 2

    if schema.provenance is None:
        print("error: atom has no provenance — must be promoted before approval")
        print("       run `chetana promote <staged>` first")
        return 2

    current_status = schema.provenance.review_status
    if current_status == "approved":
        print(f"already approved by {schema.provenance.reviewer or 'unknown'}")
        return 0
    if current_status == "rejected":
        print("error: atom was rejected; cannot approve a rejected atom")
        return 2
    if current_status not in ("staged", "auto_promoted"):
        print(f"error: unexpected review_status '{current_status}'; cannot approve")
        return 2

    # Build new provenance with approved status + reviewer + revival_chain entry
    approval_entry = {
        "event": "approve",
        "ts": now_iso(),
        "reviewer": args.reviewer,
        "prior_status": current_status,
    }
    new_revival_chain = list(schema.provenance.revival_chain) + [approval_entry]
    new_provenance = schema.provenance.model_copy(update={
        "review_status": "approved",
        "reviewer": args.reviewer,
        "revival_chain": new_revival_chain,
    })
    new_schema = schema.model_copy(update={"provenance": new_provenance})

    # Determine if atom is staged or already trusted
    try:
        path.relative_to(STAGING_ROOT.resolve())
        is_staged = True
    except ValueError:
        is_staged = False

    if is_staged:
        # Move to trusted layer; remove staged copy
        _trusted_path = write_trusted(new_schema, body=body)
        try:
            path.unlink()
        except OSError as e:
            print(f"warning: failed to remove staged file <redacted>: {type(e).__name__}")
        print("approved → trusted layer")
    else:
        # Write back in place
        from .provenance import assemble_atom
        path.write_text(assemble_atom(new_schema, body), encoding="utf-8")
        print("approved (updated in place)")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    """Round-trip every trusted atom's axiom_signature against current kernel.

    Reports four buckets:
      - verified      : recomputed sig matches stored sig under current kernel
      - zero-sig      : atom was signed with the "0"*64 placeholder (silent
                        integrity failure surfaced by the 2026-04-28 governance fix)
      - kernel-drift  : atom signature does not match current kernel and is not
                        zero-sig — kernel has rotated since this atom was promoted
      - malformed     : frontmatter doesn't parse or has no axiom_signature
    """
    from .provenance import compute_axiom_signature, parse_frontmatter
    from .staging import list_trusted

    placeholder = "0" * 64
    current_kernel_sig = placeholder
    try:
        from dharma_swarm.dharma_kernel import KernelGuard  # type: ignore
        kernel = KernelGuard()
        loaded = kernel.load()
        if inspect.isawaitable(loaded):
            import asyncio
            loaded = asyncio.run(loaded)
        resolved = (
            getattr(loaded, "signature", None)
            or getattr(getattr(kernel, "_kernel", None), "signature", None)
        )
        if resolved:
            current_kernel_sig = resolved
        else:
            print("warning: KernelGuard loaded but no signature; using placeholder")
    except Exception as e:
        print(f"warning: KernelGuard unavailable ({e}); using placeholder")

    targets: list[Path]
    if args.path and args.path != ".":
        targets = [Path(args.path)]
    else:
        targets = list_trusted()

    buckets = {
        "verified": [],
        "zero-sig": [],
        "kernel-drift": [],
        "no-provenance": [],   # parses as v1 wiki atom; chetana never promoted it
        "schema-error": [],    # malformed YAML or unrecoverable parse failure
    }
    for p in targets:
        try:
            text = p.read_text(encoding="utf-8")
            try:
                schema, body = parse_frontmatter(text, source_path=str(p))
            except Exception:
                # Most likely a v1 wiki atom missing chetana-strict fields.
                # Distinguish that from genuinely malformed YAML.
                if text.lstrip().startswith("---"):
                    buckets["no-provenance"].append(str(p))
                else:
                    buckets["schema-error"].append(str(p))
                continue
            stored = schema.provenance.axiom_signature if schema.provenance else None
            if not stored:
                buckets["no-provenance"].append(str(p))
                continue
            if compute_axiom_signature(body, current_kernel_sig) == stored:
                buckets["verified"].append(str(p))
            elif compute_axiom_signature(body, placeholder) == stored:
                buckets["zero-sig"].append(str(p))
            else:
                buckets["kernel-drift"].append(str(p))
        except Exception as e:
            buckets["schema-error"].append(f"{p}: {type(e).__name__}")

    print("# chetana verify\n- current kernel sig: <redacted; compare via dgc dharma status>")
    for label in ("verified", "zero-sig", "kernel-drift", "no-provenance", "schema-error"):
        rows = buckets[label]
        print(f"- {label:14s}: {len(rows)}")
        if args.show and rows:
            for idx in range(1, min(len(rows), args.show) + 1):
                print(f"    <redacted atom path {idx}>")
            if len(rows) > args.show:
                print(f"    (... {len(rows) - args.show} more)")
    print("\nlegend:")
    print("  verified      = sig matches under current kernel ✓")
    print("  zero-sig      = signed with placeholder (silent integrity failure)")
    print("  kernel-drift  = sig is real but kernel has rotated")
    print("  no-provenance = pre-chetana wiki atom; never went through promote pipeline")
    print("  schema-error  = malformed YAML or unrecoverable parse failure")
    # exit non-zero only on actual integrity failures, not on pre-chetana atoms
    return 0 if not buckets["zero-sig"] and not buckets["schema-error"] else 1


def _cmd_status(_args: argparse.Namespace) -> int:
    staged = list_staged()
    trusted = list_trusted()
    quarantined = list_quarantine()
    print("# chetana status")
    print(f"- staged    : {len(staged)}")
    print(f"- trusted   : {len(trusted)}")
    print(f"- quarantine: {len(quarantined)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="chetana", description="chetana PKM CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sp_ing = sub.add_parser("ingest", help="capture raw → staged atom")
    sp_ing.add_argument("source", help="path or inline text")
    sp_ing.add_argument(
        "--kind",
        choices=[
            "session",
            "webclip",
            "pdf",
            "document",
            "note",
            "wiki_extract",
            "voice",
            "external",
            "synthesis",
        ],
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

    sp_dec = sub.add_parser(
        "decay",
        help="surface stale_after atoms; quarantine is opt-in last resort",
    )
    sp_dec.add_argument(
        "--quarantine",
        action="store_true",
        help="actually move stale atoms to quarantine/ (default: just surface)",
    )
    sp_dec.add_argument("--grace-days", dest="grace_days", type=int, default=0)
    sp_dec.add_argument("--json", default=None, help="write JSON report to this path")
    sp_dec.set_defaults(func=_cmd_decay)

    sp_rev = sub.add_parser(
        "revive",
        help="re-research stale atoms; find new neighbors / backlinks / answered questions",
    )
    sp_rev.add_argument(
        "path",
        nargs="?",
        default=".",
        help="atom path (omit when using --all)",
    )
    sp_rev.add_argument("--all", action="store_true", help="propose revival for every due atom")
    sp_rev.add_argument(
        "--apply",
        action="store_true",
        help="actually rewrite the atom with refreshed metadata + revival_chain",
    )
    sp_rev.add_argument(
        "--extend-days",
        dest="extend_days",
        type=int,
        default=90,
        help="how many days to extend stale_after on apply (default 90)",
    )
    sp_rev.add_argument(
        "--reviewer",
        default="chetana.cli",
        help="recorded as reviewed_by in the revival_chain entry",
    )
    sp_rev.add_argument("--grace-days", dest="grace_days", type=int, default=0)
    sp_rev.set_defaults(func=_cmd_revive)

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

    sp_cu = sub.add_parser("cross-update", help="update index/backlinks for a trusted atom")
    sp_cu.add_argument("path", help="trusted atom path or slug")
    sp_cu.set_defaults(func=_cmd_cross_update)

    sp_vf = sub.add_parser(
        "verify",
        help="round-trip atom axiom_signature against current kernel; surface drift + zero-sigs",
    )
    sp_vf.add_argument("path", nargs="?", default=".", help="atom path (omit to verify all trusted)")
    sp_vf.add_argument("--show", type=int, default=0, help="show first N paths per bucket")
    sp_vf.set_defaults(func=_cmd_verify)

    sp_ap = sub.add_parser(
        "approve",
        help="human-explicit approval: staged → approved (distinct from auto_promoted)",
    )
    sp_ap.add_argument("path", help="staged atom path or atom_id (resolved under staging)")
    sp_ap.add_argument(
        "--reviewer",
        default=None,
        help="recorded as reviewer in provenance + revival_chain entry",
    )
    sp_ap.set_defaults(func=_cmd_approve)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
