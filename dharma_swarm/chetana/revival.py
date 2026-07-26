"""chetana.revival — re-research stale atoms, propose integration patches.

Philosophy: decay is not exile. It is the trigger for re-integration. When an
atom passes `stale_after`, the default move is NOT quarantine. The default move
is REVIVE — read the atom, scan the current graph for new neighbors / new
backlinks / answered questions / fresh evidence, and propose a refreshed atom
with an extended `stale_after`, an updated `confidence`, and a `revival_chain`
in provenance recording WHY and HOW the atom was reintegrated.

Quarantine remains available for atoms that are genuinely false, contradicted
by evidence, or no longer relevant. But the system's default response to time
is evolution, not exile.

Lifecycle states for an atom:
    fresh             — stale_after in future
    due_for_revival   — stale_after past, no revival proposal yet
    revival_proposed  — proposal written, awaiting human/agent approval
    revived           — apply done, atom rewritten with refreshed metadata +
                        revival_chain entry; new stale_after; promotion sig
                        re-computed
    quarantined       — moved to quarantine/ (last resort, opt-in)

CLI surface:
    chetana revive <atom_path>           # propose
    chetana revive <atom_path> --apply   # apply the proposal
    chetana revive --all                 # propose for every due atom
    chetana revive --all --apply         # auto-revive all due atoms (with caution)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from .governance import gate_check_atom
from .provenance import (
    FrontmatterSchema,
    assemble_atom,
    compute_axiom_signature_v2,
    default_stale_after,
    now_iso,
    parse_frontmatter,
)
from .staging import TRUSTED_DEFAULT
from .stigmergy_emit import emit_mark


logger = logging.getLogger(__name__)


_WIKILINK_RE = re.compile(r"\[\[([^\]\|\#]+)(?:[\|\#][^\]]*)?\]\]")
_QUESTION_RE = re.compile(r"([A-Z][^.?!]{12,200}\?)")


@dataclass
class NeighborMatch:
    atom_path: Path
    title: str
    captured: str
    overlap_score: float
    contribution: str  # "confirms" | "extends" | "lateral" | "contradicts"


@dataclass
class RevivalProposal:
    atom_path: Path
    atom_id: str
    title: str
    last_verified: str
    stale_after: str
    days_since_stale: int
    new_neighbors: list[NeighborMatch] = field(default_factory=list)
    new_backlinks: list[Path] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    answered_questions: list[tuple[str, Path]] = field(default_factory=list)
    proposed_related_additions: list[str] = field(default_factory=list)
    proposed_confidence_delta: float = 0.0
    proposed_new_stale_after: str = ""
    needs_external_research: list[str] = field(default_factory=list)
    revival_summary: str = ""


def propose_revival(
    *,
    atom_path: Path,
    corpus_roots: list[Path] | None = None,
    today: date | None = None,
    extend_days: int = 90,
) -> RevivalProposal:
    """Build a RevivalProposal for an atom by scanning the corpus for new evidence.

    Does NOT write anything to disk. Use `apply_revival` to materialize the
    proposal as a refreshed atom + provenance entry.
    """
    today = today or date.today()
    corpus_roots = corpus_roots or [TRUSTED_DEFAULT]

    if not atom_path.exists():
        raise FileNotFoundError(atom_path)
    text = atom_path.read_text(encoding="utf-8")
    schema, body = parse_frontmatter(text, lenient=True, source_path=str(atom_path))
    if schema is None:
        raise ValueError(f"atom has no chetana frontmatter: {atom_path}")

    last_verified = _last_verified_date(schema)
    days_since_stale = (today - date.fromisoformat(schema.stale_after)).days

    proposal = RevivalProposal(
        atom_path=atom_path,
        atom_id=schema.atom_id,
        title=schema.title,
        last_verified=last_verified.isoformat(),
        stale_after=schema.stale_after,
        days_since_stale=max(0, days_since_stale),
        proposed_new_stale_after=(today + timedelta(days=extend_days)).isoformat(),
    )

    # Walk the corpus once, collecting everything we need.
    own_tags = set(t.lower() for t in (schema.tags or []))
    own_related = set(_normalize_link(r) for r in (schema.related or []))
    own_title_norm = _normalize_link(schema.title)

    body_questions = _extract_questions(body)
    proposal.open_questions = body_questions[:]  # may be filtered as we find answers

    for root in corpus_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            if not path.is_file() or path == atom_path:
                continue
            try:
                other_text = path.read_text(encoding="utf-8")
                other_schema, other_body = parse_frontmatter(
                    other_text, lenient=True, source_path=str(path)
                )
            except Exception:
                continue
            if other_schema is None:
                continue

            captured = _captured_date(other_schema)
            is_newer = captured > last_verified

            # 1. New neighbors: overlapping tags/related, captured at-or-after last_verified.
            #    Same-day captures count too — peer atoms in the same campaign are valid neighbors.
            if captured >= last_verified:
                other_tags = set(t.lower() for t in (other_schema.tags or []))
                other_related = set(_normalize_link(r) for r in (other_schema.related or []))
                tag_overlap = len(own_tags & other_tags)
                related_overlap = len(own_related & other_related)
                if tag_overlap + related_overlap > 0:
                    score = (tag_overlap * 1.0 + related_overlap * 1.5) / max(
                        1, len(own_tags | own_related)
                    )
                    proposal.new_neighbors.append(
                        NeighborMatch(
                            atom_path=path,
                            title=other_schema.title,
                            captured=other_schema.source[0].captured if other_schema.source else "",
                            overlap_score=round(min(1.0, score), 3),
                            contribution=_classify_contribution(other_body, body),
                        )
                    )

            # 2. New backlinks: atoms whose body references THIS atom's title or atom_id.
            if is_newer and (
                own_title_norm in {_normalize_link(m.group(1)) for m in _WIKILINK_RE.finditer(other_body)}
                or schema.atom_id in other_body
            ):
                proposal.new_backlinks.append(path)

            # 3. Answered questions: any question from THIS atom's body that appears
            #    near a confident statement in a newer atom.
            for q in body_questions:
                q_keywords = _keywords(q)
                if len(q_keywords) < 2:
                    continue
                if all(k in other_body.lower() for k in q_keywords):
                    proposal.answered_questions.append((q, path))
                    if q in proposal.open_questions:
                        proposal.open_questions.remove(q)

    # Propose new related: links from the strongest neighbors.
    sorted_neighbors = sorted(proposal.new_neighbors, key=lambda n: -n.overlap_score)
    for n in sorted_neighbors[:8]:
        link = f"[[{_slugify_for_link(n.title)}]]"
        if link not in (schema.related or []):
            proposal.proposed_related_additions.append(link)

    # Confidence adjustment: confirms boosts, contradicts cuts, extends mild boost.
    confirms = sum(1 for n in proposal.new_neighbors if n.contribution == "confirms")
    contradicts = sum(1 for n in proposal.new_neighbors if n.contribution == "contradicts")
    extends = sum(1 for n in proposal.new_neighbors if n.contribution == "extends")
    proposal.proposed_confidence_delta = round(
        0.05 * confirms + 0.02 * extends - 0.10 * contradicts, 3
    )

    # Anything still open AND not echoed by anyone else → external research candidate.
    proposal.needs_external_research = list(proposal.open_questions)

    proposal.revival_summary = _summarize_proposal(proposal)
    return proposal


def apply_revival(
    proposal: RevivalProposal,
    *,
    reviewer: str = "chetana.revive",
    body_addendum: str | None = None,
    refresh_signature: bool = True,
) -> Path:
    """Apply a RevivalProposal — rewrite the atom in place with refreshed metadata
    and an appended revival_chain entry in provenance.

    Returns the (unchanged) path to the atom. Idempotent at the schema level —
    re-applying the same proposal will append another revival_chain entry but
    not duplicate the related: additions.
    """
    text = proposal.atom_path.read_text(encoding="utf-8")
    schema, body = parse_frontmatter(text)
    if schema is None or schema.provenance is None:
        raise ValueError(
            f"can only revive atoms with provenance set; this atom is unstamped: {proposal.atom_path}"
        )

    # Merge proposed related: links (deduped, preserve order).
    new_related = list(schema.related or [])
    for link in proposal.proposed_related_additions:
        if link not in new_related:
            new_related.append(link)

    new_confidence = max(
        0.0, min(1.0, schema.confidence + proposal.proposed_confidence_delta)
    )
    new_stale_after = (
        proposal.proposed_new_stale_after or default_stale_after()
    )

    # Append revival_chain entry to provenance.
    prior_provenance = schema.provenance.model_dump(exclude_none=True)
    revival_record = {
        "revival_id": f"rev-{now_iso()}",
        "revived_at": now_iso(),
        "reviewed_by": reviewer,
        "prior_signature": prior_provenance.get("axiom_signature"),
        "neighbors_added": [str(n.atom_path) for n in proposal.new_neighbors[:8]],
        "questions_resolved": [q for q, _ in proposal.answered_questions],
        "still_open_questions": list(proposal.open_questions),
        "confidence_delta": proposal.proposed_confidence_delta,
        "summary": proposal.revival_summary,
    }
    chain = list(prior_provenance.get("revival_chain") or [])
    chain.append(revival_record)
    prior_provenance["revival_chain"] = chain

    new_body = body.rstrip("\n")
    if body_addendum:
        new_body += f"\n\n## Revival addendum ({now_iso()})\n\n{body_addendum.strip()}\n"
    if proposal.answered_questions:
        new_body += "\n\n## Newly answered\n\n"
        for q, path in proposal.answered_questions:
            new_body += f"- {q}? — see [[{path.stem}]]\n"
    if proposal.needs_external_research:
        new_body += "\n\n## Still open (research queue)\n\n"
        for q in proposal.needs_external_research:
            new_body += f"- {q}?\n"
    new_body += "\n"

    if not refresh_signature:
        raise ValueError("chetana revival writes must refresh signature and pass gates")

    gov = gate_check_atom(
        atom_content=new_body,
        atom_title=schema.title,
        requested_action="chetana.revive",
        metadata={"atom_id": schema.atom_id, "revival": True},
    )
    if gov.result == "BLOCK" or not gov.can_promote:
        raise ValueError(
            "chetana revival blocked by governance gates: "
            f"{gov.record.rationale or gov.record.gates_blocked}"
        )
    prior_provenance["axiom_signature"] = gov.axiom_signature
    prior_provenance["gate_check"] = gov.record.model_dump()

    new_provenance = type(schema.provenance).model_validate(prior_provenance)
    refreshed = schema.model_copy(
        update={
            "related": new_related,
            "confidence": new_confidence,
            "stale_after": new_stale_after,
            "provenance": new_provenance,
        }
    )
    # Upgrade to v2: frontmatter (stale_after, revival_chain, …) just changed,
    # so a body-only v1 signature would leave that drift unverifiable.
    refreshed = refreshed.model_copy(
        update={
            "provenance": new_provenance.model_copy(
                update={
                    "axiom_signature": compute_axiom_signature_v2(
                        refreshed, new_body, gov.kernel_signature
                    )
                }
            )
        }
    )
    proposal.atom_path.write_text(assemble_atom(refreshed, new_body), encoding="utf-8")

    # Best-effort stigmergy emit — never blocks revival on failure.
    emit_mark(
        action="chetana.revive.apply",
        content=f"{schema.title} | revived",
        connections=["chetana", "revive", schema.atom_id],
        salience=0.7,
    )

    return proposal.atom_path


def find_due_atoms(
    *,
    today: date | None = None,
    roots: list[Path] | None = None,
    grace_days: int = 0,
) -> list[Path]:
    """Return atom paths that are past stale_after (the revive queue)."""
    today = today or date.today()
    roots = roots or [TRUSTED_DEFAULT]
    out: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            if not path.is_file():
                continue
            try:
                schema, _ = parse_frontmatter(
                    path.read_text(encoding="utf-8"),
                    lenient=True,
                    source_path=str(path),
                )
            except Exception:
                continue
            if schema is None:
                continue
            try:
                stale = date.fromisoformat(schema.stale_after)
            except ValueError:
                continue
            if (today - stale).days >= -grace_days:
                out.append(path)
    return out


def revival_summary(proposals: list[RevivalProposal]) -> str:
    lines = ["# Revival queue", ""]
    if not proposals:
        lines.append("Nothing due for revival.")
        return "\n".join(lines)
    for p in proposals:
        lines.append(f"## {p.title}")
        lines.append(f"- atom: `{p.atom_path}`")
        lines.append(
            f"- stale {p.days_since_stale}d (since {p.stale_after}); proposed new "
            f"stale_after: {p.proposed_new_stale_after}"
        )
        lines.append(f"- new neighbors: {len(p.new_neighbors)}")
        lines.append(f"- new backlinks: {len(p.new_backlinks)}")
        lines.append(f"- open questions resolved: {len(p.answered_questions)}")
        lines.append(f"- still open: {len(p.open_questions)}")
        lines.append(f"- proposed confidence delta: {p.proposed_confidence_delta:+.2f}")
        if p.proposed_related_additions:
            lines.append(f"- proposed related additions: {p.proposed_related_additions[:6]}")
        lines.append(f"- summary: {p.revival_summary}")
        lines.append("")
    return "\n".join(lines)


# ---- helpers --------------------------------------------------------------


def _last_verified_date(schema: FrontmatterSchema) -> date:
    """When was this atom last considered fresh?

    Priority: latest revival_chain entry's revived_at > provenance.promoted_at >
    earliest source.captured.
    """
    if schema.provenance is not None:
        chain = getattr(schema.provenance, "revival_chain", None) or []
        # Walk backwards for the newest entry with a real timestamp. Approval
        # events carry "ts" rather than "revived_at"; an entry with neither
        # must not default to today() (that would silently hide neighbors).
        for entry in reversed(chain):
            stamp = entry.get("revived_at") or entry.get("ts")
            if not stamp:
                continue
            try:
                return _to_date(stamp)
            except Exception:
                continue
        try:
            return _to_date(schema.provenance.promoted_at)
        except Exception:
            pass
    if schema.source:
        try:
            return _to_date(schema.source[0].captured)
        except Exception:
            pass
    return date.today()


def _captured_date(schema: FrontmatterSchema) -> date:
    if schema.source:
        try:
            return _to_date(schema.source[0].captured)
        except Exception:
            return date.today()
    return date.today()


def _to_date(s: str | None) -> date:
    if not s:
        return date.today()
    if "T" in s:
        return date.fromisoformat(s.split("T", 1)[0])
    return date.fromisoformat(s[:10])


def _normalize_link(s: str) -> str:
    s = s.strip().lower().lstrip("[").rstrip("]")
    return s.replace("_", "-").replace(" ", "-").strip("-")


def _slugify_for_link(title: str) -> str:
    s = title.strip().lower()
    s = "".join(c if c.isalnum() or c.isspace() else "-" for c in s)
    return "-".join(s.split())


def _extract_questions(body: str) -> list[str]:
    raw = _QUESTION_RE.findall(body)
    seen: set[str] = set()
    out: list[str] = []
    for q in raw:
        norm = " ".join(q.split()).rstrip("?").strip()
        if len(norm) < 16 or norm.lower() in seen:
            continue
        seen.add(norm.lower())
        out.append(norm)
    return out


def _keywords(question: str) -> list[str]:
    stop = {
        "the", "a", "an", "is", "are", "was", "were", "do", "does", "did",
        "can", "could", "should", "would", "will", "what", "why", "how",
        "when", "where", "which", "who", "of", "to", "in", "on", "for",
        "and", "or", "but", "this", "that", "with", "from", "as", "be",
        "have", "has",
    }
    words = re.findall(r"[a-zA-Z][a-zA-Z\-_]{2,}", question.lower())
    return [w for w in words if w not in stop][:6]


def _classify_contribution(other_body: str, own_body: str) -> str:
    """Heuristic: confirms / extends / lateral / contradicts."""
    bl = other_body.lower()
    if any(w in bl for w in ["contradicts", "refutes", "disproves", "incorrect", "false claim"]):
        return "contradicts"
    if any(w in bl for w in ["extends", "builds on", "expands", "follow-up", "next step"]):
        return "extends"
    if any(w in bl for w in ["confirms", "validates", "replicates", "supports"]):
        return "confirms"
    return "lateral"


def _summarize_proposal(p: RevivalProposal) -> str:
    parts = []
    if p.new_neighbors:
        parts.append(f"{len(p.new_neighbors)} new neighbor atoms found in corpus")
    if p.new_backlinks:
        parts.append(f"{len(p.new_backlinks)} new backlinks")
    if p.answered_questions:
        parts.append(f"{len(p.answered_questions)} questions now answered")
    if p.open_questions:
        parts.append(f"{len(p.open_questions)} questions still open")
    if p.proposed_confidence_delta:
        parts.append(f"confidence delta {p.proposed_confidence_delta:+.2f}")
    if not parts:
        return (
            "No new evidence found in the local corpus. Consider external research "
            "or accept the current state and re-extend stale_after."
        )
    return "; ".join(parts) + "."
