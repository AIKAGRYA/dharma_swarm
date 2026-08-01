#!/usr/bin/env python3
"""Build task playbooks from Palantir Pilot bounded source cards."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.palantir_pilot import (  # noqa: E402
    RAW_SOURCE_DIR,
    WIKI_SOURCE_DIR,
)
from dharma_swarm.palantir_pilot_manifest import default_dharma_home  # noqa: E402
from scripts.research import palantir_public_source_cards as source_cards  # noqa: E402
from scripts.research.palantir_public_source_index import classify_url  # noqa: E402


PLAYBOOK_SPECS: list[dict[str, object]] = [
    {
        "slug": "foundry-platform-foundation",
        "title": "Foundry Platform Foundation Playbook",
        "operator_question": "How should an agent orient to Foundry before making tenant-specific claims?",
        "families": ("foundry",),
        "terms": (
            "foundry",
            "platform",
            "getting-started",
            "project",
            "resource",
            "filesystem",
            "application",
            "workflow",
        ),
        "loop": (
            "Start from public overview and project/resource anchors.",
            "Separate platform vocabulary from tenant-specific implementation details.",
            "Map projects, resources, applications, and workflows before advising on build paths.",
            "Escalate to authorized tenant docs or operator-provided context before implementation.",
            "Record answer citations and confidence in the Palantir Pilot query log.",
        ),
    },
    {
        "slug": "ontology-application-loop",
        "title": "Ontology Application Loop Playbook",
        "operator_question": "How do objects, links, actions, interfaces, and object sets shape an operational app?",
        "families": ("foundry", "api_reference"),
        "terms": (
            "ontology",
            "ontologies",
            "object",
            "objects",
            "linked",
            "action",
            "actions",
            "interface",
            "object-set",
            "aggregate",
        ),
        "loop": (
            "Identify the public ontology object and action vocabulary first.",
            "Distinguish object modeling from API operation names.",
            "Trace object relationships through linked-object and object-set anchors.",
            "Use public docs for conceptual routing, not private ontology design claims.",
            "Turn repeated patterns into cited Dharma Swarm notes.",
        ),
    },
    {
        "slug": "aip-governed-builder-loop",
        "title": "AIP Governed Builder Loop Playbook",
        "operator_question": "How should Palantir Pilot reason about AIP without becoming a generic chatbot advisor?",
        "families": ("aip", "foundry"),
        "terms": (
            "aip",
            "llm",
            "model",
            "prompt",
            "governance",
            "security",
            "observability",
            "compute",
            "eval",
        ),
        "loop": (
            "Anchor AIP answers in model, prompt, compute, observability, and governance cards.",
            "Treat operational context and ontology grounding as part of the answer boundary.",
            "Separate documented public AIP behavior from private model or tenant configuration.",
            "Flag security, usage, and observability as mandatory review topics.",
            "Contribute reusable AIP answer patterns back to the swarm wiki.",
        ),
    },
    {
        "slug": "developer-api-osdk-loop",
        "title": "Developer API and OSDK Loop Playbook",
        "operator_question": "How should a developer approach public Foundry, transforms, OSDK, and Defense OSDK APIs?",
        "families": ("foundry", "api_reference", "defense_osdk"),
        "terms": (
            "api",
            "osdk",
            "sdk",
            "developer",
            "client",
            "python",
            "typescript",
            "transforms",
            "dataset",
            "ontology",
        ),
        "loop": (
            "Start with the public API family and versioned resource name.",
            "Use source cards to locate request/response concepts and developer entry points.",
            "Verify tenant authorization and exact API version before implementation decisions.",
            "Keep code guidance tied to cited public docs and authorized local context.",
            "Record gaps when public docs are not enough for a concrete build.",
        ),
    },
    {
        "slug": "apollo-release-operator-loop",
        "title": "Apollo Release Operator Loop Playbook",
        "operator_question": "How should an operator reason about Apollo product releases from public docs?",
        "families": ("apollo",),
        "terms": (
            "apollo",
            "release",
            "product",
            "version",
            "deployment",
            "environment",
            "terraform",
            "cli",
        ),
        "loop": (
            "Orient around products, product releases, versions, and environments.",
            "Use CLI cards to identify command families without pretending to run Apollo.",
            "Separate public release vocabulary from private deployment authority.",
            "Treat promotion, enrollment, and environment operations as tenant-authorized work only.",
            "Summarize operational sequences with direct public citations.",
        ),
    },
    {
        "slug": "gotham-public-analyst-loop",
        "title": "Gotham Public Analyst Loop Playbook",
        "operator_question": "How can Palantir Pilot use public Gotham docs without inferring restricted doctrine?",
        "families": ("gotham",),
        "terms": (
            "gotham",
            "target",
            "target-board",
            "target-workbench",
            "gaia",
            "geotime",
            "security",
            "third-party",
        ),
        "loop": (
            "Limit Gotham answers to public API and security vocabulary.",
            "Use target and target-board cards as public orientation anchors.",
            "Avoid operational, intelligence, or restricted workflow inference.",
            "Escalate to authorized materials before any real-world procedure claims.",
            "Maintain explicit public-source confidence on every Gotham answer.",
        ),
    },
]


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _receipt_stamp(observed_at: str) -> str:
    return (
        observed_at.replace("-", "")
        .replace(":", "")
        .replace(".", "")
        .replace("Z", "Z")
    )


def _clean_field(value: str) -> str:
    cleaned = " ".join(value.split()).strip()
    if cleaned.lower() == "not extracted":
        return ""
    return cleaned


def _read_source_card(path: Path) -> dict[str, object] | None:
    url = source_cards.card_source_url(path)
    if not url:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    title = ""
    summary_title = ""
    short_excerpt = ""
    headings: list[str] = []
    for line in text.splitlines():
        if line.startswith("# Palantir Source Card: "):
            title = line.split("# Palantir Source Card: ", 1)[1].strip()
        elif line.startswith("- Title: "):
            summary_title = line.split("- Title: ", 1)[1].strip()
        elif line.startswith("- Short excerpt: "):
            short_excerpt = line.split("- Short excerpt: ", 1)[1].strip()
        elif line.startswith("- `"):
            headings.append(line.lstrip("- ").strip())

    return {
        "url": url,
        "path": str(path),
        "family": classify_url(url),
        "title": _clean_field(summary_title or title or url),
        "short_excerpt": _clean_field(short_excerpt),
        "headings": headings[:8],
        "search_text": " ".join([url, title, summary_title, short_excerpt, " ".join(headings)]).lower(),
    }


def load_source_cards(dharma_home: Path) -> list[dict[str, object]]:
    card_dir = dharma_home / WIKI_SOURCE_DIR / "source-cards"
    if not card_dir.exists():
        return []
    cards: list[dict[str, object]] = []
    for path in sorted(card_dir.glob("*.md")):
        card = _read_source_card(path)
        if card:
            cards.append(card)
    return cards


def _score_card(card: dict[str, object], spec: dict[str, object]) -> int:
    families = {str(item) for item in spec.get("families", ())}
    terms = [str(item).lower() for item in spec.get("terms", ())]
    family = str(card.get("family") or "")
    search_text = str(card.get("search_text") or "")
    score = 0
    if family in families:
        score += 16
    for term in terms:
        score += search_text.count(term) * 3
    title = str(card.get("title") or "").lower()
    if any(term in title for term in terms):
        score += 4
    return score


def _select_cards(
    cards: list[dict[str, object]],
    spec: dict[str, object],
    *,
    limit: int,
) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for card in cards:
        score = _score_card(card, spec)
        if score <= 0:
            continue
        selected.append({**card, "score": score})
    selected.sort(key=lambda item: (-int(item["score"]), str(item["family"]), str(item["url"])))
    return selected[: max(1, limit)]


def _anchor_line(card: dict[str, object]) -> str:
    excerpt = str(card.get("short_excerpt") or "")
    excerpt_note = f" - {excerpt[:180]}" if excerpt else ""
    return (
        "- score={score} family={family} [{title}]({url}) "
        "source_card=`{path}`{excerpt_note}"
    ).format(
        score=card.get("score", 0),
        family=card.get("family", ""),
        title=str(card.get("title") or card.get("url") or "").replace("[", "(").replace("]", ")"),
        url=card.get("url", ""),
        path=card.get("path", ""),
        excerpt_note=excerpt_note,
    )


def _playbook_markdown(
    *,
    spec: dict[str, object],
    observed_at: str,
    cards: list[dict[str, object]],
    total_source_cards: int,
) -> str:
    family_counts = Counter(str(card.get("family") or "unknown") for card in cards)
    lines = [
        f"# {spec['title']}",
        "",
        f"Observed: {observed_at}",
        f"Source cards considered: {total_source_cards}",
        f"Selected anchors: {len(cards)}",
        "",
        "Boundary: original task synthesis from bounded public source cards only. No Palantir page bodies, Learn course content, videos, labs, quizzes, private tenant material, credentialed content, or hidden implementation details are stored here.",
        "",
        "## Operator Question",
        "",
        str(spec["operator_question"]),
        "",
        "## Operating Loop",
        "",
    ]
    for index, step in enumerate(spec.get("loop", ()), start=1):
        lines.append(f"{index}. {step}")
    lines.extend(
        [
            "",
            "## What Palantir Pilot Can Answer From This",
            "",
            "- Which public source-card anchors are relevant to this workflow.",
            "- Which concepts are public-source observed versus tenant-specific or implementation-dependent.",
            "- What the next cited reading or source-card expansion target should be.",
            "- Where a stronger answer requires authorized Palantir training, tenant docs, or operator-provided context.",
            "",
            "## Source-Card Anchors",
            "",
        ]
    )
    if not cards:
        lines.append("- No bounded source-card anchors selected yet.")
    for card in cards:
        lines.append(_anchor_line(card))
    lines.extend(
        [
            "",
            "## Anchor Family Mix",
            "",
        ]
    )
    if not family_counts:
        lines.append("- none")
    for family, count in sorted(family_counts.items()):
        lines.append(f"- `{family}`: {count}")
    lines.extend(
        [
            "",
            "## Contribution Queue",
            "",
            "- Promote thin public-source gaps into new source cards before answering implementation-level questions.",
            "- Add short original synthesis notes when multiple source cards repeatedly appear together in answers.",
            "- Keep Learn/course-catalog material link-only unless an allowed access path and storage rights are confirmed.",
            "",
            "## Confidence",
            "",
            "Medium when cited anchors cover the operator question; low when the answer depends on tenant state, training content, private docs, or product behavior not present in public source cards.",
            "",
        ]
    )
    return "\n".join(lines)


def build_playbooks(
    *,
    dharma_home: Path,
    limit_per_playbook: int = 10,
) -> dict[str, object]:
    observed_at = iso_now()
    cards = load_source_cards(dharma_home)
    out_dir = dharma_home / WIKI_SOURCE_DIR / "playbooks"
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[dict[str, object]] = []
    for spec in PLAYBOOK_SPECS:
        selected = _select_cards(cards, spec, limit=limit_per_playbook)
        path = out_dir / f"{spec['slug']}.md"
        path.write_text(
            _playbook_markdown(
                spec=spec,
                observed_at=observed_at,
                cards=selected,
                total_source_cards=len(cards),
            ),
            encoding="utf-8",
        )
        written.append(
            {
                "slug": spec["slug"],
                "path": str(path),
                "selected_card_count": len(selected),
                "top_urls": [str(card.get("url") or "") for card in selected[:5]],
            }
        )

    index_path = dharma_home / WIKI_SOURCE_DIR / "playbook-index.md"
    index_lines = [
        "# Palantir Pilot Playbook Index",
        "",
        f"Observed: {observed_at}",
        f"Source cards considered: {len(cards)}",
        "",
        "Boundary: task synthesis from bounded public source cards only. No full page/course mirroring and no Learn scraping.",
        "",
        "## Playbooks",
        "",
    ]
    for item in written:
        index_lines.append(
            f"- [{item['slug']}](playbooks/{item['slug']}.md) - {item['selected_card_count']} source-card anchors"
        )
    index_lines.extend(
        [
            "",
            "## Query Surface",
            "",
            "Use `python3 scripts/research/palantir_pilot_query.py \"AIP governed builder playbook\" --answer --json --index-workspace --record-db` to refresh and query this layer.",
            "",
        ]
    )
    index_path.write_text("\n".join(index_lines), encoding="utf-8")

    receipt = {
        "schema_version": "palantir_pilot.playbook_receipt.v1",
        "observed_at": observed_at,
        "output_index": str(index_path),
        "playbooks": written,
        "playbook_count": len(written),
        "source_card_count": len(cards),
        "boundary": "bounded public source-card synthesis only; Learn manual-review/link-only; no full page/course mirroring",
    }
    receipt_path = (
        dharma_home
        / RAW_SOURCE_DIR
        / f"playbook-receipt-{_receipt_stamp(observed_at)}.json"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dharma-home", default=str(default_dharma_home()))
    parser.add_argument("--limit-per-playbook", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    receipt = build_playbooks(
        dharma_home=Path(args.dharma_home).expanduser(),
        limit_per_playbook=max(1, args.limit_per_playbook),
    )
    if args.json:
        print(json.dumps(receipt, indent=2, ensure_ascii=True))
    else:
        print(f"wrote {receipt['playbook_count']} playbooks: {receipt['output_index']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
