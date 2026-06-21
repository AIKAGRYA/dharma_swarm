#!/usr/bin/env python3
"""Deterministic Step-3 synthesis scaffold: bucket deep cards into operating-domain
submaps and build per-domain index notes the specialist can query.

This is the NON-LLM half of the titanium re-synthesis. It organizes the 5,586
deep cards into operating domains and extracts each domain's heading taxonomy,
producing index notes under the wiki research dir (so index_workspace_to_memory_plane
ingests them). The LLM prose operating-models are written ON TOP of these later,
ideally on the free-model fleet so they cost no Claude allowance.

Zero network, zero LLM, zero credit cost.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

WIKI_DEEP = Path.home() / ".dharma/knowledge/wiki/research/palantir-pilot/deep-cards"
OUT_DIR = Path.home() / ".dharma/knowledge/wiki/research/palantir-pilot/domain-submaps"

# slug form: docs-<family>-<path-segments>...  e.g. docs-foundry-ontology-object-types
# Ordered: first matching rule wins.
DOMAIN_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("ontology-and-actions", ("docs-foundry-ontology", "docs-foundry-action-types", "docs-foundry-object")),
    ("lineage", ("docs-foundry-data-lineage",)),
    ("functions-transforms-pipelines", (
        "docs-foundry-functions", "docs-foundry-transforms", "docs-foundry-pipeline",
        "docs-foundry-code", "docs-foundry-data-integration",
    )),
    ("api-and-osdk", (
        "docs-foundry-api", "docs-foundry-ontology-sdk", "docs-foundry-foundryts",
        "docs-defense-osdk", "docs-foundry-available",
    )),
    ("governance-and-security", (
        "docs-foundry-security", "docs-foundry-administration", "docs-foundry-data-governance",
        "docs-foundry-data-protection",
    )),
    ("aip", ("docs-foundry-aip",)),
    ("workflow-apps", (
        "docs-foundry-workshop", "docs-foundry-slate", "docs-foundry-notepad",
        "docs-foundry-map", "docs-foundry-quiver", "docs-foundry-vertex",
        "docs-foundry-carbon", "docs-foundry-object-explorer",
    )),
    ("apollo-deployment", ("docs-apollo",)),
    ("gotham", ("docs-gotham",)),
    ("defense", ("docs-defense",)),
]
FALLBACK_FOUNDRY = "foundry-other"
FALLBACK_NONDOC = "site-and-newsroom"


def domain_for(slug: str) -> str:
    for name, prefixes in DOMAIN_RULES:
        if any(slug.startswith(p) for p in prefixes):
            return name
    if slug.startswith("docs-foundry"):
        return FALLBACK_FOUNDRY
    if slug.startswith("docs-"):
        return "docs-other"
    return FALLBACK_NONDOC


def card_headings(path: Path) -> list[str]:
    out: list[str] = []
    in_headings = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip() == "## Headings":
            in_headings = True
            continue
        if in_headings:
            if line.startswith("## "):
                break
            m = re.match(r"-\s+h[1-3]:\s+(.*)", line.strip())
            if m:
                out.append(m.group(1).strip())
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deep-dir", default=str(WIKI_DEEP))
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args(argv)

    deep_dir = Path(args.deep_dir).expanduser()
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    cards = sorted(p for p in deep_dir.glob("*.md") if not p.name.startswith("_"))
    buckets: dict[str, list[Path]] = {}
    for c in cards:
        buckets.setdefault(domain_for(c.stem), []).append(c)

    summary: dict[str, int] = {}
    for domain, paths in sorted(buckets.items()):
        heading_counter: Counter[str] = Counter()
        for p in paths:
            for h in card_headings(p):
                if 2 <= len(h) <= 80:
                    heading_counter[h] += 1
        top_headings = heading_counter.most_common(40)

        lines = [
            f"# Palantir Operating Submap: {domain}",
            "",
            f"Domain card count: {len(paths)}",
            "",
            "Boundary: internal RAG synthesis scaffold over public www.palantir.com docs "
            "(robots Allow: /). Deterministic clustering only; LLM operating-model prose is "
            "layered on top separately. Not redistributed externally.",
            "",
            "## Heading Taxonomy (most common concepts in this domain)",
            "",
        ]
        lines += [f"- {h}  ({n})" for h, n in top_headings] or ["- (no headings extracted)"]
        lines += ["", "## Source Cards In Domain", ""]
        lines += [f"- deep-cards/{p.name}" for p in paths[:400]]
        if len(paths) > 400:
            lines += [f"- ...and {len(paths) - 400} more"]
        lines += [""]
        (out_dir / f"submap-{domain}.md").write_text("\n".join(lines), encoding="utf-8")
        summary[domain] = len(paths)

    receipt = {
        "schema_version": "palantir_pilot.domain_submaps_receipt.v1",
        "deep_dir": str(deep_dir),
        "out_dir": str(out_dir),
        "total_cards": len(cards),
        "domains": dict(sorted(summary.items(), key=lambda kv: -kv[1])),
        "note": "Structural synthesis scaffold; LLM prose operating-models staged for free-model fleet.",
    }
    (out_dir / "_submaps_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
