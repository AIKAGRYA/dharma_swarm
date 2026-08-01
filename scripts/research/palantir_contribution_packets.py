#!/usr/bin/env python3
"""Build Dharma Swarm contribution packets from Palantir Pilot source cards."""

from __future__ import annotations

import argparse
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
from scripts.research.palantir_source_card_playbooks import (  # noqa: E402
    PLAYBOOK_SPECS,
    _select_cards,
    load_source_cards,
)


SCHEMA_VERSION = "palantir_pilot.contribution_packet_receipt.v1"

CONTRIBUTION_INTENTS: dict[str, dict[str, object]] = {
    "foundry-platform-foundation": {
        "swarm_value": "Use Foundry-style project/resource vocabulary to keep Dharma workspace surfaces named, bounded, and queryable.",
        "patterns": (
            "Treat every workspace as a governed project with explicit resources.",
            "Keep provenance and ownership close to the artifact instead of relying on ambient context.",
            "Separate platform language from tenant-specific implementation claims.",
        ),
        "risks": (
            "Do not imply Foundry compatibility where Dharma Swarm only borrows the public pattern.",
            "Do not overfit Dharma architecture to URL-level evidence without direct public-page review.",
        ),
    },
    "ontology-application-loop": {
        "swarm_value": "Use ontology/action thinking to make Dharma Swarm objects, links, and mutations explicit.",
        "patterns": (
            "Model objects, relationships, actions, and interfaces before automating a workflow.",
            "Bind action outputs to receipts so state changes remain explainable.",
            "Use object-set style questions when scoping what an agent can see or mutate.",
        ),
        "risks": (
            "Do not invent private ontology design guidance.",
            "Do not collapse public object vocabulary into tenant-specific schema advice.",
        ),
    },
    "aip-governed-builder-loop": {
        "swarm_value": "Use AIP-style governance to separate model execution, observability, evaluation, and permission boundaries.",
        "patterns": (
            "Pair every model-facing workflow with usage, observability, and evaluation receipts.",
            "Treat model access and registered-model language as governed capability, not generic chat.",
            "Make refusal and escalation paths first-class parts of agent answers.",
        ),
        "risks": (
            "Do not claim private AIP behavior from public docs alone.",
            "Do not provide tenant setup instructions without authorized tenant context.",
        ),
    },
    "developer-api-osdk-loop": {
        "swarm_value": "Use public API/OSDK routing patterns to improve Dharma developer surfaces and version checks.",
        "patterns": (
            "Start developer answers with resource family, version, and authorization checks.",
            "Prefer typed client or SDK boundaries over ad hoc endpoint guessing.",
            "Log missing version/context as a gap instead of turning it into advice.",
        ),
        "risks": (
            "Do not produce implementation code that assumes credentials or tenant state.",
            "Do not blur public API reference metadata with runnable integration authority.",
        ),
    },
    "apollo-release-operator-loop": {
        "swarm_value": "Use Apollo release vocabulary to harden Dharma Swarm promotion, rollback, and environment thinking.",
        "patterns": (
            "Name product, release, version, and environment separately in operational runbooks.",
            "Require comparison receipts before promotion-like claims.",
            "Treat rollback/recall language as a governed operator action with proof.",
        ),
        "risks": (
            "Do not pretend to run Apollo or mutate deployments.",
            "Do not infer private deployment workflow from public CLI names.",
        ),
    },
    "gotham-public-analyst-loop": {
        "swarm_value": "Use Gotham public-source caution to improve analyst surfaces without restricted workflow inference.",
        "patterns": (
            "Keep analyst-facing terms tied to public API/security vocabulary.",
            "Distinguish target, board, and workbench concepts from operational doctrine.",
            "Mark public-source confidence low when real-world procedures are implied.",
        ),
        "risks": (
            "Do not infer intelligence, defense, or operational procedure from API names.",
            "Do not translate public Gotham names into restricted or sensitive guidance.",
        ),
    },
}


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _receipt_stamp(observed_at: str) -> str:
    return (
        observed_at.replace("-", "")
        .replace(":", "")
        .replace(".", "")
        .replace("Z", "Z")
    )


def _safe_title(value: object) -> str:
    text = str(value or "").strip()
    return text.replace("[", "(").replace("]", ")") or "Untitled Palantir anchor"


def _anchor_line(card: dict[str, object]) -> str:
    excerpt = str(card.get("short_excerpt") or "")
    excerpt_note = f" - {excerpt[:180]}" if excerpt else ""
    return (
        "- score={score} family={family} [{title}]({url}) "
        "source_card=`{path}`{excerpt_note}"
    ).format(
        score=card.get("score", 0),
        family=card.get("family", ""),
        title=_safe_title(card.get("title") or card.get("url")),
        url=card.get("url", ""),
        path=card.get("path", ""),
        excerpt_note=excerpt_note,
    )


def _packet_markdown(
    *,
    spec: dict[str, object],
    observed_at: str,
    cards: list[dict[str, object]],
    total_source_cards: int,
) -> str:
    slug = str(spec["slug"])
    intent = CONTRIBUTION_INTENTS[slug]
    lines = [
        f"# {spec['title']} - Dharma Swarm Contribution Packet",
        "",
        f"Observed: {observed_at}",
        f"Source cards considered: {total_source_cards}",
        f"Selected anchors: {len(cards)}",
        "",
        "Boundary: original Dharma Swarm synthesis from bounded public Palantir source cards only. No Palantir page bodies, Learn course content, videos, labs, quizzes, private tenant material, credentialed content, or official-affiliation claims are stored here.",
        "",
        "## Swarm Contribution",
        "",
        str(intent["swarm_value"]),
        "",
        "## Reusable Patterns",
        "",
    ]
    for pattern in intent["patterns"]:
        lines.append(f"- {pattern}")
    lines.extend(
        [
            "",
            "## Contribution Proposal",
            "",
            "- Promote this packet into Dharma Swarm design review when a matching local workflow appears.",
            "- Cite the evidence anchors before borrowing any Palantir-adjacent language.",
            "- Convert repeated use into a local verifier, runbook, or ontology note rather than an uncited convention.",
            "",
            "## Risks And Refusals",
            "",
        ]
    )
    for risk in intent["risks"]:
        lines.append(f"- {risk}")
    lines.extend(
        [
            "- Learn remains manual-review/link-only unless access and storage rights are clear.",
            "- Tenant-specific implementation, credentials, spend, deployment, enrollment, or account actions require explicit operator authority.",
            "",
            "## Evidence Anchors",
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
            "## Query Handles",
            "",
            f"- `{slug} contribution`",
            "- `Dharma Swarm implication`",
            "- `Palantir public-source pattern`",
            "",
        ]
    )
    return "\n".join(lines)


def build_contribution_packets(
    *,
    dharma_home: Path,
    anchors_per_packet: int = 8,
    observed_at: str | None = None,
) -> dict[str, object]:
    """Write contribution packets and a machine receipt."""

    observed = observed_at or iso_now()
    cards = load_source_cards(dharma_home)
    out_dir = dharma_home / WIKI_SOURCE_DIR / "contributions"
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[dict[str, object]] = []
    for spec in PLAYBOOK_SPECS:
        slug = str(spec["slug"])
        selected = _select_cards(cards, spec, limit=max(1, anchors_per_packet))
        path = out_dir / f"{slug}-contribution.md"
        path.write_text(
            _packet_markdown(
                spec=spec,
                observed_at=observed,
                cards=selected,
                total_source_cards=len(cards),
            ),
            encoding="utf-8",
        )
        written.append(
            {
                "slug": slug,
                "path": str(path),
                "anchor_count": len(selected),
                "top_urls": [str(card.get("url") or "") for card in selected[:5]],
            }
        )

    index_path = dharma_home / WIKI_SOURCE_DIR / "contribution-index.md"
    index_lines = [
        "# Palantir Pilot Contribution Index",
        "",
        f"Observed: {observed}",
        f"Source cards considered: {len(cards)}",
        "",
        "Boundary: Dharma Swarm contribution synthesis from bounded public source cards only. No Learn scraping and no full page/course mirroring.",
        "",
        "## Contribution Packets",
        "",
    ]
    for item in written:
        index_lines.append(
            f"- [{item['slug']}](contributions/{item['slug']}-contribution.md) - {item['anchor_count']} source-card anchors"
        )
    index_lines.extend(
        [
            "",
            "## Query Surface",
            "",
            "Use `python3 scripts/research/palantir_pilot_query.py \"Dharma Swarm AIP contribution governance\" --answer --json --index-workspace --record-db` to refresh and query this layer.",
            "",
        ]
    )
    index_path.write_text("\n".join(index_lines), encoding="utf-8")

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "observed_at": observed,
        "output_index": str(index_path),
        "packets": written,
        "packet_count": len(written),
        "source_card_count": len(cards),
        "boundary": "bounded public source-card contribution synthesis only; Learn manual-review/link-only; no full page/course mirroring",
    }
    receipt_path = (
        dharma_home
        / RAW_SOURCE_DIR
        / f"contribution-packets-{_receipt_stamp(observed)}.json"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dharma-home", default=str(default_dharma_home()))
    parser.add_argument("--anchors-per-packet", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    receipt = build_contribution_packets(
        dharma_home=Path(args.dharma_home).expanduser(),
        anchors_per_packet=max(1, args.anchors_per_packet),
    )
    if args.json:
        print(json.dumps(receipt, indent=2, ensure_ascii=True))
    else:
        print(f"wrote {receipt['packet_count']} contribution packets: {receipt['output_index']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
