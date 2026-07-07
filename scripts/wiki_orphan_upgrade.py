#!/usr/bin/env python3
"""Upgrade Karpathy-style wiki orphans into linked, structured knowledge.

The wiki index defines an orphan as an atom with zero inbound wikilinks. This
script does two things:

1. Enriches orphan atoms with stronger frontmatter and an ideation block.
2. Builds MOC pages that link to recovered atoms so they gain real inbound
   backlinks and become part of the navigable graph.

Default mode is dry-run. Use --apply to write changes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

WIKI_SCRIPT_DIR = Path.home() / ".dharma" / "scripts"
if str(WIKI_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(WIKI_SCRIPT_DIR))

from wiki_lib import (  # type: ignore  # noqa: E402
    FRONTMATTER_RE,
    VALID_CROSSES,
    VALID_DOMAINS,
    VALID_ENERGY,
    VALID_PARA,
    VALID_STATUS,
    WIKILINK_RE,
    iter_atoms,
)


SCRIPT_VERSION = "wiki-orphan-upgrade-v1"
DEFAULT_WIKI_ROOT = Path.home() / ".dharma" / "knowledge" / "wiki"
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can",
    "for", "from", "has", "have", "how", "in", "into", "is", "it",
    "its", "of", "on", "or", "so", "that", "the", "their", "this",
    "to", "was", "we", "what", "when", "where", "which", "with",
    "you", "your",
}
DOMAIN_KEYWORDS = {
    "computational": {
        "agent", "api", "code", "compute", "context", "daemon", "dgc",
        "github", "kernel", "llm", "memory", "model", "nats", "python",
        "receipt", "runtime", "test", "vector", "wiki",
    },
    "governance": {
        "audit", "canonical", "claim", "contract", "gate", "governance",
        "policy", "proof", "receipt", "review", "risk", "safety",
        "trust", "witness",
    },
    "infra": {
        "cron", "daemon", "deploy", "gateway", "launchd", "log", "nats",
        "server", "service", "tmux", "worker",
    },
    "science": {
        "biology", "causal", "decoherence", "evidence", "metric", "paper",
        "physics", "quantum", "research", "science", "study",
    },
    "contemplative": {
        "akram", "attention", "dharma", "gnan", "jain", "nagarjuna",
        "samaya", "vignan", "witness",
    },
    "economic": {
        "bounty", "cash", "cost", "economy", "market", "money", "revenue",
        "trading", "venture",
    },
}
FALLBACK_HUBS = (
    "karpathy-wiki-pattern",
    "knowledge-compiler",
    "orphaned-insights-pattern",
    "MOC-wiki-health",
)
UPGRADE_BEGIN = "<!-- ORPHAN_UPGRADE_BEGIN -->"
UPGRADE_END = "<!-- ORPHAN_UPGRADE_END -->"


@dataclass(frozen=True)
class WikiHealth:
    total_atoms: int
    orphan_count: int
    with_density: int
    missing_sources: int
    missing_status: int
    missing_para: int
    by_kind: dict[str, int]
    by_domain: dict[str, int]
    sample_orphans: tuple[str, ...]


@dataclass(frozen=True)
class UpgradeReceipt:
    run_id: str
    applied: bool
    wiki_root: str
    before: WikiHealth
    selected_orphans: int
    upgraded_atoms: int
    moc_pages_written: int
    backup_dir: str | None
    report_path: str | None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-root", default=str(DEFAULT_WIKI_ROOT))
    parser.add_argument("--apply", action="store_true", help="write upgrades")
    parser.add_argument("--status", action="store_true", help="print health summary only")
    parser.add_argument("--limit", type=int, default=0, help="limit upgraded orphans")
    parser.add_argument("--max-print", type=int, default=12)
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument(
        "--repair-recovered",
        action="store_true",
        help="reprocess atoms that already carry orphan_recovery metadata",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    wiki_root = Path(args.wiki_root).expanduser().resolve()
    atoms = _load_atoms(wiki_root)
    backlinks = _backlink_counts(atoms)
    orphans = [a for a in atoms if backlinks.get(a.slug, 0) == 0]
    health = _health(atoms, orphans, max_print=max(0, args.max_print))

    if args.status:
        if args.json:
            print(json.dumps(asdict(health), indent=2, sort_keys=True))
        else:
            print(_render_status(health))
        return 0

    recovered = [a for a in atoms if isinstance(a.fm.get("orphan_recovery"), dict)]
    pool = recovered if args.repair_recovered else orphans
    selected = pool[: args.limit] if args.limit and args.limit > 0 else pool
    candidates = _candidate_index(atoms)
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = None
    if args.apply and selected and not args.no_backup:
        backup_dir = wiki_root.parent / "_wiki_orphan_backups" / run_id
        backup_dir.mkdir(parents=True, exist_ok=True)

    upgraded = 0
    if args.apply:
        for atom in selected:
            related = _suggest_related(atom, candidates)
            before_text = atom.path.read_text(encoding="utf-8")
            after_text = _upgrade_text(atom, related, run_id)
            if after_text != before_text:
                if backup_dir is not None:
                    target = backup_dir / atom.path.relative_to(wiki_root)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(atom.path, target)
                atom.path.write_text(after_text, encoding="utf-8")
                upgraded += 1
        if selected:
            _write_moc_pages(wiki_root, selected, run_id)
        report_path = _write_report(wiki_root, run_id, health, selected, upgraded, backup_dir)
    else:
        upgraded = len(selected)
        report_path = None

    receipt = UpgradeReceipt(
        run_id=run_id,
        applied=bool(args.apply),
        wiki_root=str(wiki_root),
        before=health,
        selected_orphans=len(selected),
        upgraded_atoms=upgraded,
        moc_pages_written=2 if args.apply and selected else 0,
        backup_dir=str(backup_dir) if backup_dir else None,
        report_path=str(report_path) if report_path else None,
    )
    if args.json:
        print(json.dumps(receipt.to_json(), indent=2, sort_keys=True))
    else:
        print(_render_receipt(receipt))
    return 0


def _load_atoms(wiki_root: Path):
    roots = [
        wiki_root / "concepts",
        wiki_root / "connections",
        wiki_root / "mocs",
        wiki_root / "voices",
        wiki_root / "decisions",
        wiki_root / "external_voices",
        wiki_root / "atoms",
        wiki_root / "inter_agent",
        wiki_root / "tooling",
    ]
    return list(iter_atoms(roots=roots))


def _backlink_counts(atoms) -> dict[str, int]:
    backlinks: dict[str, int] = defaultdict(int)
    for atom in atoms:
        for slug in atom.related:
            backlinks[slug] += 1
        for slug in atom.body_wikilinks:
            backlinks[slug] += 1
    return dict(backlinks)


def _health(atoms, orphans, *, max_print: int) -> WikiHealth:
    by_kind = Counter(a.path.parent.name for a in atoms)
    by_domain = Counter(str(a.fm.get("domain", "unset")) for a in atoms)
    return WikiHealth(
        total_atoms=len(atoms),
        orphan_count=len(orphans),
        with_density=sum(1 for a in atoms if isinstance(a.fm.get("semantic_density"), (int, float))),
        missing_sources=sum(1 for a in atoms if not _as_list(a.fm.get("sources") or a.fm.get("source"))),
        missing_status=sum(1 for a in atoms if not a.fm.get("status")),
        missing_para=sum(1 for a in atoms if not a.fm.get("para")),
        by_kind=dict(sorted(by_kind.items())),
        by_domain=dict(sorted(by_domain.items())),
        sample_orphans=tuple(a.slug for a in orphans[:max_print]),
    )


def _candidate_index(atoms) -> list[dict[str, Any]]:
    out = []
    for atom in atoms:
        text = f"{atom.slug} {atom.fm.get('title', '')} {' '.join(_as_list(atom.fm.get('tags')))} {atom.body[:2500]}"
        out.append(
            {
                "slug": atom.slug,
                "title": atom.fm.get("title", atom.slug),
                "tokens": _tokens(text),
                "domain": _infer_domain(atom),
            }
        )
    return out


def _suggest_related(atom, candidates: list[dict[str, Any]], *, limit: int = 5) -> list[str]:
    atom_tokens = _tokens(f"{atom.slug} {atom.fm.get('title', '')} {atom.body[:3500]}")
    domain = _infer_domain(atom)
    scored: list[tuple[float, str]] = []
    for candidate in candidates:
        slug = candidate["slug"]
        if slug == atom.slug:
            continue
        overlap = atom_tokens & candidate["tokens"]
        if not overlap:
            continue
        score = len(overlap)
        if candidate["domain"] == domain:
            score += 1.5
        if slug.startswith("MOC-"):
            score += 0.75
        scored.append((score, slug))
    scored.sort(reverse=True)
    related = [slug for _, slug in scored[:limit]]
    for fallback in FALLBACK_HUBS:
        if fallback != atom.slug and fallback not in related:
            related.append(fallback)
    return related[: max(limit, len(FALLBACK_HUBS))]


def _upgrade_text(atom, related: list[str], run_id: str) -> str:
    raw = atom.path.read_text(encoding="utf-8")
    fm = dict(atom.fm or {})
    body = atom.body if FRONTMATTER_RE.match(raw) else raw
    rel_path = str(atom.path.relative_to(DEFAULT_WIKI_ROOT)) if atom.path.is_relative_to(DEFAULT_WIKI_ROOT) else str(atom.path)
    title = _title(atom)
    original_sources = _as_list(fm.get("sources") or fm.get("source"))
    source_quality = _source_quality(original_sources)
    inferred_domain = _infer_domain(atom)
    inferred_crosses = _infer_crosses(atom, inferred_domain)
    existing_related = _normalize_related(_as_list(fm.get("related")))
    merged_related = _dedupe(existing_related + related + ["MOC-orphan-recovery", "MOC-wiki-health"])

    fm["title"] = title
    fm["confidence"] = _confidence(fm.get("confidence"), source_quality)
    fm["sources"] = original_sources or [
        f"local-wiki-existing-atom:{rel_path}",
        f"orphan-upgrade-run:{run_id}",
    ]
    fm["stale_after"] = str(fm.get("stale_after") or _future_date(days=90))
    fm["related"] = merged_related[:14]
    fm["status"] = fm.get("status") if fm.get("status") in VALID_STATUS else "draft"
    fm["para"] = fm.get("para") if fm.get("para") in VALID_PARA else _infer_para(atom)
    fm["energy"] = fm.get("energy") if fm.get("energy") in VALID_ENERGY else _infer_energy(atom)
    fm["tags"] = _dedupe(_as_list(fm.get("tags")) + _infer_tags(atom, inferred_domain))
    fm["crosses_domain"] = _normalize_crosses(_as_list(fm.get("crosses_domain")) + inferred_crosses)
    fm["domain"] = fm.get("domain") if fm.get("domain") in VALID_DOMAINS else inferred_domain
    fm["captured"] = str(fm.get("captured") or dt.date.today().isoformat())
    fm["captured_by"] = str(fm.get("captured_by") or SCRIPT_VERSION)
    fm["epistemic_status"] = str(fm.get("epistemic_status") or "orphan-recovered")
    if len(fm["crosses_domain"]) > 1:
        fm["anekantavada"] = bool(fm.get("anekantavada", True))
    fm["semantic_density"] = max(
        float(fm.get("semantic_density", 0) or 0),
        _density_score(body, fm),
    )
    fm["source_quality"] = str(fm.get("source_quality") or source_quality)
    fm["review_status"] = str(
        fm.get("review_status")
        or ("needs-source-hardening" if source_quality == "self-provenance-only" else "needs-human-review")
    )
    fm["orphan_recovery"] = {
        "run_id": run_id,
        "recovered_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "previous_backlink_count": 0,
        "inbound_anchor": "MOC-orphan-recovery",
    }
    fm["cross_pollination_targets"] = merged_related[:6]
    fm["ideation_seeds"] = _ideation_seeds(title, merged_related)
    fm["adoption_hooks"] = [
        "make wiki-orphan-status",
        "make wiki-orphan-upgrade",
        "make orient",
    ]

    yaml_text = yaml.safe_dump(
        fm,
        allow_unicode=True,
        sort_keys=False,
        width=100,
    ).strip()
    upgraded_body = _replace_upgrade_block(body, title, merged_related, source_quality, run_id)
    return f"---\n{yaml_text}\n---\n\n{upgraded_body.lstrip()}"


def _replace_upgrade_block(body: str, title: str, related: list[str], source_quality: str, run_id: str) -> str:
    targets = ", ".join(f"[[{slug}]]" for slug in related[:5])
    block = "\n".join(
        [
            UPGRADE_BEGIN,
            f"- Recovery run: `{run_id}` via `{SCRIPT_VERSION}`.",
            "- Inbound anchor: [[MOC-orphan-recovery]].",
            f"- Cross-pollination targets: {targets}.",
            f"- Ideation prompt: What does `{title}` change when read against {targets}?",
            "- Ideation prompt: Extract one claim, one contradiction, and one reusable rule from this atom.",
            f"- Source hardening: `{source_quality}`; replace self-provenance with primary sources when promoting.",
            UPGRADE_END,
        ]
    )
    section = f"\n\n## Ideation Cross-Pollination\n\n{block}\n"
    pattern = re.compile(
        r"\n*## Ideation Cross-Pollination\s*\n\s*"
        + re.escape(UPGRADE_BEGIN)
        + r".*?"
        + re.escape(UPGRADE_END)
        + r"\s*",
        re.DOTALL,
    )
    if pattern.search(body):
        return pattern.sub(section, body).rstrip() + "\n"
    return body.rstrip() + section


def _write_moc_pages(wiki_root: Path, selected, run_id: str) -> None:
    mocs = wiki_root / "mocs"
    mocs.mkdir(parents=True, exist_ok=True)
    by_domain: dict[str, list] = defaultdict(list)
    for atom in selected:
        by_domain[_infer_domain(atom)].append(atom)
    total = len(selected)
    today = dt.date.today().isoformat()
    health = mocs / "MOC-wiki-health.md"
    recovery = mocs / "MOC-orphan-recovery.md"
    health.write_text(
        "\n".join(
            [
                "---",
                'title: "MOC — Wiki Health and Adoption"',
                "confidence: 0.92",
                "sources:",
                "  - /Users/dhyana/.dharma/knowledge/wiki/_meta/wiki-charter.md",
                "  - /Users/dhyana/dharma_swarm/scripts/wiki_orphan_upgrade.py",
                f'stale_after: "{_future_date(days=60)}"',
                "related: [MOC-orphan-recovery, karpathy-wiki-pattern, knowledge-compiler, orphaned-insights-pattern]",
                "status: trusted",
                "tags: [moc, wiki-health, knowledge-ops, governance]",
                "para: project",
                "energy: hi",
                "crosses_domain: [computational, governance, infra]",
                "domain: governance",
                f'captured: "{today}"',
                f"captured_by: {SCRIPT_VERSION}",
                "semantic_density: 0.78",
                "---",
                "",
                "# MOC — Wiki Health and Adoption",
                "",
                "This is the always-on culture hook for the Karpathy-style wiki. Every agent should treat wiki health as part of orientation, not as a separate cleanup chore.",
                "",
                "## Operating Rule",
                "",
                "- Run `make orient` or `make onboard` before serious work.",
                "- Read the wiki health block those targets print.",
                "- If orphan count rises, run `make wiki-orphan-status` and decide whether `make wiki-orphan-upgrade` is appropriate.",
                "- File hard-won answers back into the wiki so they compound instead of disappearing into chat.",
                "",
                "## Live Surfaces",
                "",
                "- [[MOC-orphan-recovery]] — recovered orphan atoms and cross-pollination map.",
                "- [[karpathy-wiki-pattern]] — upstream operating method inside this system.",
                "- [[knowledge-compiler]] — compilation layer.",
                "- [[orphaned-insights-pattern]] — failure mode this MOC is designed to kill.",
                "",
                "## Adoption Hooks",
                "",
                "- `make onboard` prints wiki orphan health.",
                "- `make orient` prints wiki orphan health.",
                "- `make wiki-orphan-status` gives the current health summary.",
                "- `make wiki-orphan-upgrade` runs the deterministic recovery pass.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    lines = [
        "---",
        'title: "MOC — Orphan Recovery"',
        "confidence: 0.88",
        "sources:",
        "  - /Users/dhyana/.dharma/knowledge/wiki/index.md",
        "  - /Users/dhyana/dharma_swarm/scripts/wiki_orphan_upgrade.py",
        f'stale_after: "{_future_date(days=30)}"',
        "related: [MOC-wiki-health, karpathy-wiki-pattern, knowledge-compiler, semantic-gravity]",
        "status: trusted",
        "tags: [moc, wiki-health, orphan-recovery, cross-pollination]",
        "para: project",
        "energy: hi",
        "crosses_domain: [computational, governance, infra]",
        "domain: governance",
        f'captured: "{today}"',
        f"captured_by: {SCRIPT_VERSION}",
        "semantic_density: 0.86",
        "---",
        "",
        "# MOC — Orphan Recovery",
        "",
        f"Recovery run `{run_id}` linked and enriched {total} orphan atoms. This page is intentionally dense: it is the inbound anchor that pulls isolated atoms back into the graph.",
        "",
        "## Recovery Logic",
        "",
        "- Every recovered atom receives stronger frontmatter, cross-pollination targets, ideation seeds, and source-hardening status.",
        "- This MOC links to recovered atoms by inferred domain so the graph has real inbound edges.",
        "- Self-provenance-only atoms remain draft until a human or agent replaces placeholder provenance with primary sources.",
        "",
    ]
    for domain in sorted(by_domain):
        atoms = sorted(by_domain[domain], key=lambda a: a.slug)
        lines.append(f"## {domain.title()} ({len(atoms)})")
        lines.append("")
        for atom in atoms:
            lines.append(f"- [[{atom.slug}]] — {_title(atom)}")
        lines.append("")
    recovery.write_text("\n".join(lines), encoding="utf-8")


def _write_report(wiki_root: Path, run_id: str, health: WikiHealth, selected, upgraded: int, backup_dir: Path | None) -> Path:
    meta = wiki_root / "_meta"
    meta.mkdir(parents=True, exist_ok=True)
    report = {
        "run_id": run_id,
        "script": SCRIPT_VERSION,
        "before": asdict(health),
        "selected_orphans": len(selected),
        "upgraded_atoms": upgraded,
        "backup_dir": str(backup_dir) if backup_dir else None,
        "mocs": [
            str(wiki_root / "mocs" / "MOC-wiki-health.md"),
            str(wiki_root / "mocs" / "MOC-orphan-recovery.md"),
        ],
    }
    path = meta / f"orphan-upgrade-{run_id}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _title(atom) -> str:
    if atom.fm.get("title"):
        return str(atom.fm["title"]).strip()
    for line in atom.body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return atom.slug.replace("-", " ").strip().title()


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9]{2,}", text.lower())
        if token not in STOPWORDS
    }


def _infer_domain(atom) -> str:
    existing = atom.fm.get("domain")
    if existing in VALID_DOMAINS:
        return str(existing)
    text = " ".join(
        [
            atom.slug,
            str(atom.fm.get("title", "")),
            " ".join(_as_list(atom.fm.get("tags"))),
            atom.body[:3000],
        ]
    ).lower()
    scores = {
        domain: sum(1 for word in words if word in text)
        for domain, words in DOMAIN_KEYWORDS.items()
    }
    best, score = max(scores.items(), key=lambda item: item[1])
    return best if score > 0 and best in VALID_DOMAINS else "mixed"


def _infer_crosses(atom, domain: str) -> list[str]:
    text = f"{atom.slug} {atom.fm.get('title', '')} {' '.join(_as_list(atom.fm.get('tags')))} {atom.body[:2500]}".lower()
    crosses = [domain] if domain in VALID_CROSSES else []
    for candidate, words in DOMAIN_KEYWORDS.items():
        if candidate in VALID_CROSSES and candidate != domain and sum(1 for word in words if word in text) >= 2:
            crosses.append(candidate)
    return _dedupe(crosses or ["computational", "governance"])


def _infer_tags(atom, domain: str) -> list[str]:
    tags = ["wiki-health", "orphan-recovery"]
    if domain != "mixed":
        tags.append(domain)
    kind = atom.path.parent.name
    if kind in {"concepts", "connections", "mocs", "atoms", "inter_agent", "tooling"}:
        tags.append(kind.rstrip("s"))
    return tags


def _infer_para(atom) -> str:
    kind = atom.path.parent.name
    if kind in {"atoms", "inter_agent"}:
        return "archive"
    if kind in {"mocs", "tooling"}:
        return "resource"
    return "resource"


def _infer_energy(atom) -> str:
    words = len(atom.body.split())
    if words > 900:
        return "hi"
    if words > 200:
        return "mid"
    return "lo"


def _confidence(value: Any, source_quality: str) -> float:
    if isinstance(value, (int, float)):
        return round(min(1.0, max(0.0, float(value))), 3)
    return 0.62 if source_quality == "source-backed" else 0.48


def _source_quality(sources: list[Any]) -> str:
    real_sources = [
        str(source)
        for source in sources
        if not str(source).startswith("local-wiki-existing-atom:")
        and not str(source).startswith("orphan-upgrade-run:")
    ]
    return "source-backed" if real_sources else "self-provenance-only"


def _density_score(body: str, fm: dict[str, Any]) -> float:
    words = len(body.split())
    sources = len(_as_list(fm.get("sources")))
    links = len(WIKILINK_RE.findall(body)) + len(_as_list(fm.get("related")))
    fm_fields = len(fm)
    score = 0.12
    score += min(0.28, words / 1800.0 * 0.28)
    score += min(0.20, sources / 4.0 * 0.20)
    score += min(0.24, links / 10.0 * 0.24)
    score += min(0.16, fm_fields / 24.0 * 0.16)
    return round(min(0.92, score), 3)


def _ideation_seeds(title: str, related: list[str]) -> list[str]:
    links = ", ".join(f"[[{slug}]]" for slug in related[:3])
    return [
        f"Read `{title}` against {links}; name the strongest contradiction or reusable design rule.",
        f"Promote one sourced claim from `{title}` into a connection atom if it survives source hardening.",
    ]


def _normalize_related(values: list[Any]) -> list[str]:
    out = []
    for value in values:
        if not isinstance(value, str):
            continue
        match = WIKILINK_RE.search(value)
        cleaned = match.group(1) if match else value.strip().strip("[]")
        if cleaned:
            out.append(cleaned)
    return out


def _normalize_crosses(values: list[Any]) -> list[str]:
    out = []
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if cleaned in VALID_CROSSES:
            out.append(cleaned)
    return _dedupe(out or ["computational", "governance"])


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _dedupe(values: list[Any]) -> list[Any]:
    out = []
    seen = set()
    for value in values:
        if value is None:
            continue
        key = str(value)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _future_date(*, days: int) -> str:
    return (dt.date.today() + dt.timedelta(days=days)).isoformat()


def _render_status(health: WikiHealth) -> str:
    return "\n".join(
        [
            "# Wiki Orphan Health",
            "",
            f"Total atoms: `{health.total_atoms}`",
            f"Orphans: `{health.orphan_count}`",
            f"With semantic_density: `{health.with_density}/{health.total_atoms}`",
            f"Missing sources: `{health.missing_sources}`",
            f"Missing status: `{health.missing_status}`",
            f"Missing PARA: `{health.missing_para}`",
            f"By kind: `{health.by_kind}`",
            "",
            "Use `make wiki-orphan-upgrade` to enrich orphans, create inbound MOC anchors, regenerate the index, and re-ingest the wiki seam.",
            "",
            "Sample orphans:",
            *[f"- [[{slug}]]" for slug in health.sample_orphans],
        ]
    )


def _render_receipt(receipt: UpgradeReceipt) -> str:
    mode = "APPLIED" if receipt.applied else "DRY RUN"
    return "\n".join(
        [
            f"# Wiki Orphan Upgrade: {mode}",
            "",
            f"Run id: `{receipt.run_id}`",
            f"Wiki root: `{receipt.wiki_root}`",
            f"Before orphans: `{receipt.before.orphan_count}`",
            f"Selected orphans: `{receipt.selected_orphans}`",
            f"Upgraded atoms: `{receipt.upgraded_atoms}`",
            f"MOC pages written: `{receipt.moc_pages_written}`",
            f"Backup dir: `{receipt.backup_dir or 'none'}`",
            f"Report: `{receipt.report_path or 'dry-run only'}`",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
