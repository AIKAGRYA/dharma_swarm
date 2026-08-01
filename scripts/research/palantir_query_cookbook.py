#!/usr/bin/env python3
"""Build and smoke-test the Palantir Pilot operator query cookbook."""

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
    build_answer_packet,
)
from dharma_swarm.palantir_pilot_manifest import default_dharma_home  # noqa: E402


SCHEMA_VERSION = "palantir_pilot.query_cookbook_receipt.v1"

QUERY_RECIPES: list[dict[str, object]] = [
    {
        "slug": "foundry-platform-orientation",
        "title": "Foundry Platform Orientation",
        "query": "How should I orient to Foundry projects resources applications and workflows from public sources?",
        "intent": "Front-door Foundry question for platform vocabulary and public-source limits.",
    },
    {
        "slug": "ontology-action-loop",
        "title": "Ontology And Action Loop",
        "query": "Explain Palantir ontology objects links actions interfaces and object sets for an operational app",
        "intent": "Ontology-backed app design question with object/action vocabulary.",
    },
    {
        "slug": "aip-governance-observability",
        "title": "AIP Governance And Observability",
        "query": "How should Palantir Pilot reason about AIP governance observability model access and evals?",
        "intent": "AIP question that should stay grounded in governance, model, observability, and eval anchors.",
    },
    {
        "slug": "developer-osdk-api",
        "title": "Developer OSDK And API",
        "query": "What public docs should a developer read for Foundry OSDK TypeScript Python APIs and ontology SDK work?",
        "intent": "Developer routing question for API family, SDK, version, and authorization boundaries.",
    },
    {
        "slug": "apollo-release-operator",
        "title": "Apollo Release Operator",
        "query": "How should an operator think about Apollo product releases versions environments and promotion?",
        "intent": "Apollo release vocabulary question without claiming deployment authority.",
    },
    {
        "slug": "gotham-public-analyst",
        "title": "Gotham Public Analyst Boundary",
        "query": "How can Palantir Pilot discuss Gotham target boards and public analyst docs without restricted inference?",
        "intent": "Gotham question that must preserve public-source and restricted-workflow boundaries.",
    },
    {
        "slug": "learn-course-boundary",
        "title": "Learn Course Catalog Boundary",
        "query": "Can Palantir Pilot use the Learn course catalog for training paths and what is the storage boundary?",
        "intent": "Learn boundary question; autonomous scraping must remain blocked.",
        "expected_note_fragment": "learn-course-catalog-intake.md",
        "requires_learn_boundary": True,
    },
    {
        "slug": "swarm-contribution-pattern",
        "title": "Dharma Swarm Contribution Pattern",
        "query": "What Dharma Swarm contribution can Palantir Pilot offer from AIP governance observability and model access patterns?",
        "intent": "Contribution question proving the holon can offer swarm-facing lessons.",
        "expected_note_fragment": "aip-governed-builder-loop-contribution.md",
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


def _note_paths(answer_packet: dict[str, object]) -> list[str]:
    notes = answer_packet.get("note_citations")
    note_rows = notes if isinstance(notes, list) else []
    paths: list[str] = []
    for item in note_rows:
        if isinstance(item, dict):
            paths.append(str(item.get("path") or ""))
    query_packet = answer_packet.get("query_packet")
    if isinstance(query_packet, dict):
        hits = query_packet.get("note_hits")
        hit_rows = hits if isinstance(hits, list) else []
        for item in hit_rows:
            if isinstance(item, dict):
                paths.append(str(item.get("path") or ""))
    return paths


def _recipe_status(recipe: dict[str, object], answer_packet: dict[str, object]) -> dict[str, object]:
    source_citations = answer_packet.get("source_citations")
    note_citations = answer_packet.get("note_citations")
    sources = source_citations if isinstance(source_citations, list) else []
    notes = note_citations if isinstance(note_citations, list) else []
    limitations = answer_packet.get("limitations")
    limitation_rows = limitations if isinstance(limitations, list) else []
    note_paths = _note_paths(answer_packet)

    checks: dict[str, bool] = {
        "has_public_source_boundary": str(answer_packet.get("source_boundary") or "").startswith(
            "Public-source workspace synthesis"
        ),
        "has_no_affiliation_limit": any(
            "No official Palantir affiliation" in str(item) for item in limitation_rows
        ),
        "has_evidence": bool(sources or notes),
        "confidence_not_insufficient": answer_packet.get("confidence")
        != "insufficient_local_evidence",
    }

    expected_fragment = str(recipe.get("expected_note_fragment") or "")
    if expected_fragment:
        checks["expected_note_fragment"] = any(expected_fragment in path for path in note_paths)
    if bool(recipe.get("requires_learn_boundary")):
        checks["learn_boundary_present"] = any(
            "learn.palantir.com/page/course-catalog" in str(item)
            for item in limitation_rows
        )

    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "confidence": str(answer_packet.get("confidence") or ""),
        "source_citation_count": len(sources),
        "note_citation_count": len(notes),
        "top_source_url": str(sources[0].get("url") or "") if sources and isinstance(sources[0], dict) else "",
        "top_note_path": str(notes[0].get("path") or "") if notes and isinstance(notes[0], dict) else "",
    }


def _cookbook_markdown(*, observed_at: str, rows: list[dict[str, object]]) -> str:
    lines = [
        "# Palantir Pilot Query Cookbook",
        "",
        f"Observed: {observed_at}",
        "",
        "Boundary: operator query recipes over the local public-source Palantir Pilot workspace only. Answers must cite public URL metadata or original wiki notes, preserve Learn as manual-review/link-only, and avoid private tenant claims, credentials, spend, enrollment, deployment, or official-affiliation claims.",
        "",
        "## Ask Palantir Pilot",
        "",
        "Use the answer surface from the repo root:",
        "",
        "```bash",
        "python3 scripts/research/palantir_pilot_query.py \"<question>\" --answer --json --index-workspace --record-db",
        "```",
        "",
        "## Smoke Status",
        "",
        "| recipe | status | confidence | top note | top source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {slug} | {status} | {confidence} | {note} | {source} |".format(
                slug=row["slug"],
                status=row["status"],
                confidence=row["confidence"],
                note=row["top_note_path"],
                source=row["top_source_url"],
            )
        )
    lines.extend(["", "## Recipes", ""])
    for row in rows:
        lines.extend(
            [
                f"### {row['title']}",
                "",
                f"- Status: `{row['status']}`",
                f"- Intent: {row['intent']}",
                f"- Query: `{row['query']}`",
                "- Command:",
                "",
                "```bash",
                f"python3 scripts/research/palantir_pilot_query.py \"{row['query']}\" --answer --json --index-workspace --record-db",
                "```",
                "",
                "Checks:",
            ]
        )
        checks = row.get("checks")
        check_rows = checks if isinstance(checks, dict) else {}
        for name, ok in sorted(check_rows.items()):
            lines.append(f"- `{name}`: {ok}")
        lines.extend(["", "Top citations:", ""])
        lines.append(f"- Note: `{row['top_note_path'] or 'none'}`")
        lines.append(f"- Source: `{row['top_source_url'] or 'none'}`")
        lines.append("")
    return "\n".join(lines)


def _smoke_report_markdown(*, observed_at: str, rows: list[dict[str, object]]) -> str:
    pass_count = sum(1 for row in rows if row["status"] == "pass")
    lines = [
        "# Palantir Pilot Query Smoke Report",
        "",
        f"Observed: {observed_at}",
        f"Recipe count: {len(rows)}",
        f"Pass count: {pass_count}",
        f"Fail count: {len(rows) - pass_count}",
        "",
        "Boundary: local public-source answer smoke only; no page/course fetching.",
        "",
        "## Results",
        "",
    ]
    for row in rows:
        lines.append(
            "- `{slug}` status={status} confidence={confidence} sources={sources} notes={notes}".format(
                slug=row["slug"],
                status=row["status"],
                confidence=row["confidence"],
                sources=row["source_citation_count"],
                notes=row["note_citation_count"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def build_query_cookbook(
    *,
    dharma_home: Path,
    observed_at: str | None = None,
    limit: int = 8,
) -> dict[str, object]:
    observed = observed_at or iso_now()
    rows: list[dict[str, object]] = []
    for recipe in QUERY_RECIPES:
        answer_packet = build_answer_packet(
            str(recipe["query"]),
            dharma_home=dharma_home,
            limit=limit,
        )
        status = _recipe_status(recipe, answer_packet)
        rows.append(
            {
                "slug": recipe["slug"],
                "title": recipe["title"],
                "query": recipe["query"],
                "intent": recipe["intent"],
                **status,
            }
        )

    source_dir = dharma_home / WIKI_SOURCE_DIR
    source_dir.mkdir(parents=True, exist_ok=True)
    cookbook_path = source_dir / "query-cookbook.md"
    smoke_path = source_dir / "query-smoke-latest.md"
    cookbook_path.write_text(_cookbook_markdown(observed_at=observed, rows=rows), encoding="utf-8")
    smoke_path.write_text(_smoke_report_markdown(observed_at=observed, rows=rows), encoding="utf-8")

    pass_count = sum(1 for row in rows if row["status"] == "pass")
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "observed_at": observed,
        "output_index": str(cookbook_path),
        "smoke_report": str(smoke_path),
        "recipes": rows,
        "recipe_count": len(rows),
        "pass_count": pass_count,
        "fail_count": len(rows) - pass_count,
        "strict_pass": pass_count == len(rows),
        "boundary": "local public-source answer smoke only; Learn manual-review/link-only; no full page/course mirroring",
    }
    receipt_path = (
        dharma_home
        / RAW_SOURCE_DIR
        / f"query-cookbook-{_receipt_stamp(observed)}.json"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dharma-home", default=str(default_dharma_home()))
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    receipt = build_query_cookbook(
        dharma_home=Path(args.dharma_home).expanduser(),
        limit=max(1, args.limit),
    )
    if args.json:
        print(json.dumps(receipt, indent=2, ensure_ascii=True))
    else:
        print(
            f"wrote query cookbook: {receipt['output_index']} "
            f"({receipt['pass_count']}/{receipt['recipe_count']} pass)"
        )
    if args.strict and not bool(receipt["strict_pass"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
