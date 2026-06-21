"""Palantir Pilot public-source specialist projection.

This module defines the first conservative incarnation of a persistent
Palantir specialist holon for Dharma Swarm. It is an evidence-only external
worker: it can index public source surfaces, summarize and cite them, and keep
wiki/database receipts, but it does not bypass access controls, spend money,
call private Palantir accounts, or claim affiliation with Palantir.
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DHARMA_HOME = Path.home() / ".dharma"

AGENT_ID = "palantir_pilot"
CALLSIGN = "palantir-pilot"
DISPLAY_NAME = "Palantir Pilot"
SCHEMA_VERSION = "palantir_pilot.source_manifest.v1"
REPO_AGENT_HOME = Path("docs/agents/palantir_pilot")
SEED_FILE = REPO_AGENT_HOME / "agent.seed.yaml"
SOUL_FILE = REPO_AGENT_HOME / "SOUL.md"
CONTEXT_ENGINEERING_FILE = REPO_AGENT_HOME / "CONTEXT_ENGINEERING.md"
NATS_SUBJECT = "dharma.a2a.palantir-pilot"

WIKI_HOME = Path("knowledge/wiki/research/palantir-pilot.md")
WIKI_SOURCE_DIR = Path("knowledge/wiki/research/palantir-pilot")
RAW_SOURCE_DIR = Path("knowledge/wiki/raw/palantir-pilot")
MEMORY_PLANE_DB = Path("db/memory_plane.db")
QUERY_CONSUMER = "palantir_pilot.query"
DATABASE_SOURCE_KINDS = (
    "palantir_pilot_source_catalog",
    "palantir_pilot_wiki",
)

OWNED_SURFACES = [
    "docs/agents/palantir_pilot/**",
    "docs/agent_tasks/2026-06-14_palantir_pilot_longrun_goal.md",
    "docs/research/palantir-ontology/**",
    "dharma_swarm/palantir_pilot.py",
    "scripts/governance/palantir_pilot_audit.py",
    "scripts/governance/register_palantir_pilot.py",
    "scripts/research/palantir_public_source_index.py",
    "scripts/research/palantir_public_source_cards.py",
    "scripts/research/palantir_source_card_balanced_expand.py",
    "scripts/research/palantir_source_card_quality.py",
    "scripts/research/palantir_source_card_cleanup.py",
    "scripts/research/palantir_pilot_query.py",
    "scripts/research/palantir_pilot_orientation.py",
    "scripts/research/palantir_pilot_curriculum.py",
    "scripts/research/palantir_source_card_playbooks.py",
    "scripts/research/palantir_playbook_evals.py",
    "scripts/research/palantir_contribution_packets.py",
    "scripts/research/palantir_query_cookbook.py",
    "scripts/research/palantir_learning_backlog.py",
    "tests/test_palantir_pilot.py",
    "~/.dharma/knowledge/wiki/research/palantir-pilot.md",
    "~/.dharma/knowledge/wiki/research/palantir-pilot/**",
    "~/.dharma/knowledge/wiki/raw/palantir-pilot/**",
]

FORBIDDEN_ACTIONS = [
    "bypass login, paywall, robots.txt, rate limits, or course enrollment controls",
    "store Learn/course bodies, videos, transcripts, labs, or quizzes wholesale, or commit deep-card prose to git (full prose of robots-allowed public docs pages, kept local-only as deep-cards, is permitted)",
    "claim official Palantir affiliation, certification, access, or insider knowledge",
    "read or write provider secrets outside the declared Dharma key owner",
    "spend money, enroll accounts, submit forms, or touch live external accounts",
    "mutate repo source outside an explicit assignment and verifier receipt",
    "present summaries without source URL, retrieval date, and confidence",
]

VERIFIER_COMMANDS = [
    "python3 scripts/governance/palantir_pilot_audit.py --json",
    "python3 scripts/governance/register_palantir_pilot.py --dry-run",
    "python3 scripts/research/palantir_public_source_index.py --dry-run",
    "python3 scripts/research/palantir_public_source_cards.py --topic aip --dry-run --limit 2 --json",
    "python3 scripts/research/palantir_source_card_balanced_expand.py --dry-run --limit-per-topic 1 --max-total 3 --json",
    "python3 scripts/research/palantir_source_card_quality.py --dry-run --json",
    "python3 scripts/research/palantir_source_card_cleanup.py --dry-run --json",
    "python3 scripts/research/palantir_pilot_query.py ontology --json --limit 3",
    "python3 scripts/research/palantir_pilot_query.py ontology --answer --json --limit 3",
    "python3 scripts/research/palantir_pilot_query.py ontology --json --limit 3 --index-workspace --record-db",
    "python3 scripts/research/palantir_pilot_orientation.py --json",
    "python3 scripts/research/palantir_pilot_curriculum.py --json",
    "python3 scripts/research/palantir_source_card_playbooks.py --json",
    "python3 scripts/research/palantir_playbook_evals.py --json",
    "python3 scripts/research/palantir_contribution_packets.py --json",
    "python3 scripts/research/palantir_query_cookbook.py --strict --json",
    "python3 scripts/research/palantir_learning_backlog.py --strict --json",
    "pytest -q tests/test_palantir_pilot.py",
]

PUBLIC_SOURCES = [
    {
        "id": "palantir_www_robots",
        "url": "https://www.palantir.com/robots.txt",
        "surface": "corporate_and_docs_robots",
        "access_status": "autonomous_fetch_allowed_observed_2026-06-14",
        "ingestion_policy": "Use robots and sitemap references as crawl authority. Store the policy text only as a small receipt.",
    },
    {
        "id": "palantir_docs_sitemap",
        "url": "https://www.palantir.com/docs/sitemap.xml",
        "surface": "public_docs_sitemap",
        "access_status": "autonomous_fetch_allowed_observed_2026-06-14",
        "ingestion_policy": "Index URLs, lastmod values, product family, and distilled summaries; for robots-allowed public docs pages, also store full parsed prose as local-only deep-cards. Do not mirror Learn/course bodies or private-tenant material.",
    },
    {
        "id": "palantir_www_sitemap",
        "url": "https://www.palantir.com/sitemap.xml",
        "surface": "public_site_sitemap",
        "access_status": "autonomous_fetch_allowed_observed_2026-06-14",
        "ingestion_policy": "Index public product, platform, blog, newsroom, and policy URLs with metadata and short notes.",
    },
    {
        "id": "palantir_learn_course_catalog",
        "url": "https://learn.palantir.com/page/course-catalog",
        "surface": "learn_course_catalog",
        "access_status": "robots_fetch_403_autonomous_blocked_observed_2026-06-14",
        "ingestion_policy": "Link and manually review only until an allowed access path is confirmed. Do not scrape with autonomous fetch.",
    },
]

DOC_FAMILY_PREFIXES = {
    "aip": "/docs/foundry/aip/",
    "api_reference": "/docs/foundry/api-reference/",
    "foundry": "/docs/foundry/",
    "apollo": "/docs/apollo/",
    "gotham": "/docs/gotham/",
    "defense_osdk": "/docs/defense-osdk/",
}


def _utc_now(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _path_exists(repo_root: Path, relative: str) -> bool:
    return (repo_root / relative).exists()


def _count_markdown_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*.md") if item.is_file())


def _source_family(url: str) -> str:
    for family, prefix in DOC_FAMILY_PREFIXES.items():
        if prefix in url:
            return family
    if "/docs/" in url:
        return "docs_other"
    return "site"


def summarize_source_families(urls: list[str]) -> dict[str, int]:
    """Count Palantir public URLs by coarse product/source family."""

    counts: dict[str, int] = {}
    for url in urls:
        family = _source_family(url)
        counts[family] = counts.get(family, 0) + 1
    return dict(sorted(counts.items()))


def build_source_manifest(
    *,
    repo_root: Path | str = REPO_ROOT,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a read-only manifest for the Palantir Pilot knowledge surface."""

    repo = Path(repo_root)
    home = Path(dharma_home).expanduser()
    prior_research = repo / "docs" / "research" / "palantir-ontology"
    wiki_home = home / WIKI_HOME
    raw_dir = home / RAW_SOURCE_DIR
    source_card_dir = home / WIKI_SOURCE_DIR / "source-cards"
    source_card_index = home / WIKI_SOURCE_DIR / "source-card-index.md"
    curriculum_dir = home / WIKI_SOURCE_DIR / "curriculum"
    curriculum_index = home / WIKI_SOURCE_DIR / "curriculum-index.md"
    learn_intake = home / WIKI_SOURCE_DIR / "learn-course-catalog-intake.md"
    source_card_quality_report = home / WIKI_SOURCE_DIR / "source-card-quality-report.md"
    playbook_dir = home / WIKI_SOURCE_DIR / "playbooks"
    playbook_index = home / WIKI_SOURCE_DIR / "playbook-index.md"
    eval_dir = home / WIKI_SOURCE_DIR / "evals"
    eval_index = home / WIKI_SOURCE_DIR / "eval-index.md"
    contribution_dir = home / WIKI_SOURCE_DIR / "contributions"
    contribution_index = home / WIKI_SOURCE_DIR / "contribution-index.md"
    query_cookbook = home / WIKI_SOURCE_DIR / "query-cookbook.md"
    query_smoke_report = home / WIKI_SOURCE_DIR / "query-smoke-latest.md"
    learning_backlog = home / WIKI_SOURCE_DIR / "learning-backlog.md"
    learning_loop = home / WIKI_SOURCE_DIR / "learning-loop-latest.md"
    memory_plane_db = home / MEMORY_PLANE_DB
    source_index_files = sorted(raw_dir.glob("source-index-*.json")) if raw_dir.exists() else []
    latest_index = str(source_index_files[-1]) if source_index_files else ""

    return {
        "schema_version": SCHEMA_VERSION,
        "agent": {
            "id": AGENT_ID,
            "callsign": CALLSIGN,
            "label": DISPLAY_NAME,
            "mode": "external_worker_evidence_only",
            "repo_agent_home": str(repo / REPO_AGENT_HOME),
            "owned_surfaces": OWNED_SURFACES,
            "forbidden_actions": FORBIDDEN_ACTIONS,
        },
        "observed_at": _utc_now(now),
        "repo_root": str(repo),
        "dharma_home": str(home),
        "public_sources": PUBLIC_SOURCES,
        "source_policy": {
            "allowed_storage": [
                "URLs",
                "retrieval timestamps",
                "sitemap metadata",
                "short excerpts within copyright limits",
                "original summaries and concept maps",
                "bounded public docs source cards",
                "full-text deep-cards for robots-allowed public docs pages (local-only under ~/.dharma, never committed)",
                "balanced public docs source-card expansion receipts",
                "archive-only source-card cleanup receipts",
                "task playbooks synthesized from bounded source cards",
                "playbook evaluation prompts synthesized from bounded source cards",
                "Dharma Swarm contribution packets synthesized from bounded source cards",
                "operator query cookbook and answer-smoke receipts",
                "bounded learning backlog and self-improvement loop receipts",
                "query-answer receipts with citations",
            ],
            "disallowed_storage": [
                "full docs-page prose committed into the git repo (public deep-cards stay local-only under ~/.dharma, never committed)",
                "course videos, transcripts, labs, or quizzes copied wholesale",
                "private tenant material",
                "credentialed Palantir content unless the operator supplies explicit rights and boundaries",
            ],
            "learn_palantir_status": "blocked_for_autonomous_scrape_until_allowed_access_is_confirmed",
        },
        "product_families": sorted(DOC_FAMILY_PREFIXES),
        "prior_repo_research": {
            "path": str(prior_research),
            "exists": prior_research.exists(),
            "markdown_file_count": _count_markdown_files(prior_research),
        },
        "wiki": {
            "home_path": str(wiki_home),
            "home_exists": wiki_home.exists(),
            "source_dir": str(home / WIKI_SOURCE_DIR),
            "raw_dir": str(raw_dir),
            "latest_source_index": latest_index,
            "source_card_index": str(source_card_index),
            "source_card_count": _count_markdown_files(source_card_dir),
            "source_card_quality_report": str(source_card_quality_report),
            "source_card_quality_report_exists": source_card_quality_report.exists(),
            "curriculum_index": str(curriculum_index),
            "curriculum_path_count": _count_markdown_files(curriculum_dir),
            "learn_course_catalog_intake": str(learn_intake),
            "learn_course_catalog_intake_exists": learn_intake.exists(),
            "playbook_index": str(playbook_index),
            "playbook_count": _count_markdown_files(playbook_dir),
            "eval_index": str(eval_index),
            "eval_suite_count": _count_markdown_files(eval_dir),
            "contribution_index": str(contribution_index),
            "contribution_packet_count": _count_markdown_files(contribution_dir),
            "query_cookbook": str(query_cookbook),
            "query_cookbook_exists": query_cookbook.exists(),
            "query_smoke_report": str(query_smoke_report),
            "query_smoke_report_exists": query_smoke_report.exists(),
            "learning_backlog": str(learning_backlog),
            "learning_backlog_exists": learning_backlog.exists(),
            "learning_loop": str(learning_loop),
            "learning_loop_exists": learning_loop.exists(),
        },
        "database": {
            "memory_plane_db": str(memory_plane_db),
            "memory_plane_exists": memory_plane_db.exists(),
            "source_kinds": list(DATABASE_SOURCE_KINDS),
            "query_consumer": QUERY_CONSUMER,
            "storage_policy": "Palantir Pilot stores URL metadata, wiki notes, query snippets, and retrieval receipts only.",
        },
        "registration": {
            "external_registration": str(home / "external_agents" / AGENT_ID / "registration.json"),
            "living_agent": str(home / "agents" / AGENT_ID / "living_agent.json"),
            "a2a_card": str(home / "a2a" / "cards" / f"{CALLSIGN}.json"),
            "onboarding_receipt": str(home / "agents" / AGENT_ID / "last_receipt.json"),
        },
        "verifier_commands": VERIFIER_COMMANDS,
    }


def build_external_worker_registration(
    *,
    dharma_home: Path | str | None = None,
    repo_root: Path | str = REPO_ROOT,
):
    """Construct the Stage-1 registration record for Palantir Pilot."""

    from dharma_swarm.external_agent_registration import (
        AutonomyPolicy,
        ExternalAgentAuthority,
        ExternalAgentStatus,
        ExternalRoamingWorker,
        WorkspacePolicy,
        external_agent_sandbox_root,
    )

    home = Path(dharma_home).expanduser() if dharma_home else DEFAULT_DHARMA_HOME
    repo = Path(repo_root)
    return ExternalRoamingWorker(
        agent_uid=AGENT_ID,
        callsign=CALLSIGN,
        display_name=DISPLAY_NAME,
        harness="codex",
        model_identity="codex",
        department="research",
        role="palantir_public_source_specialist",
        squad_id="platform_intelligence",
        team_id="dharma_swarm",
        endpoint="pending://manual",
        mailbox=f"nats://{NATS_SUBJECT}",
        authority=ExternalAgentAuthority.EXTERNAL_WORKER_EVIDENCE_ONLY,
        autonomy_policy=AutonomyPolicy(
            mode="manual",
            requires_approval=True,
            explicit_task_assignment_required=True,
        ),
        workspace_policy=WorkspacePolicy(
            sandbox_root=str(external_agent_sandbox_root(home) / AGENT_ID),
            repo_writes_allowed=False,
            canonical_dharma_dir_writes_allowed=False,
        ),
        memory_namespace=f"agent:{AGENT_ID}",
        trace_identity=f"trace:{AGENT_ID}",
        status=ExternalAgentStatus.REGISTERED,
        is_returning_historical_embodiment=False,
        notes=(
            "Independent public-source Palantir specialist for Dharma Swarm. "
            "Evidence-only Stage-1 worker: indexes public Palantir docs/site "
            "metadata, writes original summaries and query receipts, and refuses "
            "credential bypass, wholesale copyrighted copying, spend, PR approval, "
            "or source-tree writes without explicit assignment."
        ),
        registration_source="palantir_pilot_registration",
        capabilities=(
            "palantir_public_docs_indexing",
            "foundry_architecture_mapping",
            "aip_workflow_mapping",
            "ontology_design_comparison",
            "gotham_apollo_osdk_orientation",
            "course_catalog_manual_review",
            "citation_grounded_qa",
            "local_query_surface",
            "local_answer_surface",
            "bounded_public_docs_source_cards",
            "balanced_source_card_expansion",
            "source_card_quality_coverage_report",
            "source_card_cleanup_archive",
            "public_source_curriculum_paths",
            "source_card_task_playbooks",
            "playbook_fluency_evaluations",
            "palantir_pattern_contribution_packets",
            "operator_query_cookbook",
            "answer_surface_smoke_verifier",
            "bounded_learning_backlog",
            "self_improvement_loop_planning",
            "learn_catalog_manual_intake_schema",
            "memory_plane_database_surface",
        ),
        metadata={
            "repo_home": str(repo / REPO_AGENT_HOME),
            "seed_path": str(repo / SEED_FILE),
            "soul_file": str(repo / SOUL_FILE),
            "context_engineering_desk": str(repo / CONTEXT_ENGINEERING_FILE),
            "wiki_home": str(home / WIKI_HOME),
            "raw_source_dir": str(home / RAW_SOURCE_DIR),
            "memory_plane_db": str(home / MEMORY_PLANE_DB),
            "retrieval_log_consumer": QUERY_CONSUMER,
            "manifest_agent_id": AGENT_ID,
            "nats_subject": NATS_SUBJECT,
            "nats_runtime_status": "declared_not_started",
            "a2a_transport_status": "card_registered_only_after_onboarding",
            "authority_boundary": "external_worker_evidence_only",
            "public_source_only": True,
            "learn_palantir_autonomous_scrape": "blocked_until_allowed_access_confirmed",
            "copyright_policy": "store_links_metadata_summaries_and_small_excerpts_not_full_pages",
            "official_affiliation": False,
        },
    )


def format_markdown(manifest: dict[str, Any]) -> str:
    """Render a concise wiki/report page for the Palantir Pilot state."""

    agent = manifest["agent"]
    prior = manifest["prior_repo_research"]
    wiki = manifest["wiki"]
    database = manifest["database"]
    rows = []
    for source in manifest["public_sources"]:
        rows.append(
            "| {id} | {surface} | {status} | {url} |".format(
                id=source["id"],
                surface=source["surface"],
                status=source["access_status"],
                url=source["url"],
            )
        )

    return "\n".join(
        [
            "# Palantir Pilot",
            "",
            f"Observed: {manifest['observed_at']}",
            "",
            "## Identity",
            "",
            f"- Agent: `{agent['id']}` / `{agent['callsign']}`",
            "- Role: independent public-source Palantir specialist for Dharma Swarm",
            "- Authority: evidence-only Stage-1 external worker",
            "- Affiliation: No official Palantir affiliation or private access claimed",
            "",
            "## Source Boundary",
            "",
            "| id | surface | status | url |",
            "| --- | --- | --- | --- |",
            *rows,
            "",
            "## Storage Rule",
            "",
            "Store links, metadata, timestamps, original summaries, concept maps, short excerpts, and — for robots-allowed public docs pages — full parsed prose as local-only deep-cards (under ~/.dharma, never committed to git). Do not mirror Learn/course bodies, videos, labs, quizzes, or private-tenant material.",
            "",
            "## Current Workspace",
            "",
            f"- Prior repo research: `{prior['path']}` ({prior['markdown_file_count']} markdown files)",
            f"- Wiki home: `{wiki['home_path']}`",
            f"- Raw source index dir: `{wiki['raw_dir']}`",
            f"- Latest source index: `{wiki['latest_source_index'] or 'none yet'}`",
            f"- Source card index: `{wiki['source_card_index']}` ({wiki['source_card_count']} cards)",
            f"- Source card quality report: `{wiki['source_card_quality_report']}` (exists={wiki['source_card_quality_report_exists']})",
            f"- Curriculum index: `{wiki['curriculum_index']}` ({wiki['curriculum_path_count']} paths)",
            f"- Playbook index: `{wiki['playbook_index']}` ({wiki['playbook_count']} playbooks)",
            f"- Evaluation index: `{wiki['eval_index']}` ({wiki['eval_suite_count']} suites)",
            f"- Contribution index: `{wiki['contribution_index']}` ({wiki['contribution_packet_count']} packets)",
            f"- Query cookbook: `{wiki['query_cookbook']}` (exists={wiki['query_cookbook_exists']})",
            f"- Query smoke report: `{wiki['query_smoke_report']}` (exists={wiki['query_smoke_report_exists']})",
            f"- Learning backlog: `{wiki['learning_backlog']}` (exists={wiki['learning_backlog_exists']})",
            f"- Learning loop: `{wiki['learning_loop']}` (exists={wiki['learning_loop_exists']})",
            f"- Learn manual intake: `{wiki['learn_course_catalog_intake']}` (exists={wiki['learn_course_catalog_intake_exists']})",
            "",
            "## Database Surface",
            "",
            f"- Memory plane DB: `{database['memory_plane_db']}`",
            f"- Query receipt consumer: `{database['query_consumer']}`",
            f"- Indexed source kinds: `{', '.join(database['source_kinds'])}`",
            "- Database storage: URL metadata, original wiki notes, query snippets, and retrieval receipts only",
            "",
            "## Verifiers",
            "",
            *[f"- `{cmd}`" for cmd in manifest["verifier_commands"]],
            "",
        ]
    )


def write_manifest_json(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True, default=str) + "\n", encoding="utf-8")


def write_wiki_home(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_markdown(manifest), encoding="utf-8")


def latest_source_index_path(dharma_home: Path | str = DEFAULT_DHARMA_HOME) -> Path | None:
    """Return the newest Palantir Pilot source-index JSON path, if present."""

    raw_dir = Path(dharma_home).expanduser() / RAW_SOURCE_DIR
    if not raw_dir.exists():
        return None
    paths = sorted(raw_dir.glob("source-index-*.json"))
    return paths[-1] if paths else None


def memory_plane_db_path(dharma_home: Path | str = DEFAULT_DHARMA_HOME) -> Path:
    """Return the local Dharma memory-plane DB path for Palantir Pilot receipts."""

    return Path(dharma_home).expanduser() / MEMORY_PLANE_DB


def _query_terms(query: str) -> list[str]:
    terms: list[str] = []
    current: list[str] = []
    for char in query.lower():
        if char.isalnum():
            current.append(char)
        elif current:
            term = "".join(current)
            if len(term) > 1:
                terms.append(term)
            current = []
    if current:
        term = "".join(current)
        if len(term) > 1:
            terms.append(term)
    return terms


def _score_text(text: str, terms: list[str]) -> int:
    haystack = text.lower()
    return sum(haystack.count(term) for term in terms)


def _score_wiki_note(path: Path, text: str, terms: list[str]) -> int:
    path_text = " ".join([path.name, path.stem, " ".join(path.parts[-5:])])
    score = _score_text(text, terms) + (_score_text(path_text, terms) * 8)
    term_set = set(terms)
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    product_map_query = bool({"product", "family", "families", "compare", "map", "maps"} & term_set)
    named_family_terms = {"foundry", "aip", "ontology", "osdk", "api", "apollo", "gotham", "defense", "learn"}
    broad_product_map_query = product_map_query and len(term_set & named_family_terms) >= 3
    if name.startswith("titanium-"):
        titanium_terms = {
            "bench",
            "blocked",
            "boundary",
            "claim",
            "claims",
            "compare",
            "corpus",
            "debt",
            "dharma",
            "evaluation",
            "expert",
            "exhausted",
            "family",
            "first",
            "gap",
            "gaps",
            "hard",
            "map",
            "maps",
            "mastery",
            "model",
            "operating",
            "principles",
            "product",
            "qa",
            "ratchet",
            "synthesis",
            "swarm",
            "titanium",
            "transfer",
            "unjustified",
            "weak",
        }
        overlap = term_set & titanium_terms
        if overlap:
            score += 900 + (120 * len(overlap))
        if {"first", "principles", "model", "operating"} & term_set and "first-principles" in name:
            score += 1200
        if {"product", "family", "families", "compare", "map", "maps"} & term_set and "product-family" in name:
            score += 1200
            if broad_product_map_query:
                score += 4200
        if {"dharma", "swarm", "transfer", "patterns"} & term_set and "dharma-swarm-application" in name:
            score += 1200
        if {"gap", "gaps", "blocked", "weak", "unjustified", "claims"} & term_set and "gap-ledger" in name:
            score += 1200
        if {"qa", "question", "questions", "expert", "bench", "hard"} & term_set and "expert-qa" in name:
            score += 1200
        if {"corpus", "coverage", "indexed"} & term_set and "corpus-map" in name:
            score += 1200
        if {"next", "synthesis", "debt", "exhausted", "canonical"} & term_set and "synthesis-debt" in name:
            score += 3600
    if {"contribution", "packet"} & term_set and "contributions" in parts:
        score += 2400
    if {"dharma", "swarm", "aip", "governance", "observability", "model"} & term_set and "contributions" in parts:
        score += 1600
    if {"evaluation", "eval"} & term_set and "evals" in parts:
        score += 60
    if "playbook" in term_set and "playbooks" in parts:
        score += 40
    if {"learn", "course", "catalog"} & term_set and path.name == "learn-course-catalog-intake.md":
        score += 1200 if broad_product_map_query else 5200
    if "checkpoint" in term_set:
        if path.name.startswith("checkpoint-"):
            path_lower = path.name.lower()
            score += 6000
            score += sum(2000 for term in term_set if term in path_lower)
        elif path.name in {"source-card-index.md", "query-cookbook.md", "query-smoke-latest.md"}:
            score = max(1, score // 4)
    elif path.name in {"source-card-index.md", "curriculum-index.md", "orientation-index.md", "query-cookbook.md", "query-smoke-latest.md"}:
        score = max(1, score // 12)
    return score


def _load_latest_source_index(dharma_home: Path | str = DEFAULT_DHARMA_HOME) -> tuple[Path | None, dict[str, Any]]:
    path = latest_source_index_path(dharma_home)
    if path is None:
        return None, {}
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path, {}


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _query_observed_at(packet: dict[str, Any]) -> datetime:
    raw = str(packet.get("observed_at") or "")
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        return datetime.fromisoformat(raw).astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _wiki_markdown_paths(dharma_home: Path | str = DEFAULT_DHARMA_HOME) -> list[Path]:
    home = Path(dharma_home).expanduser()
    paths: list[Path] = []
    wiki_home = home / WIKI_HOME
    if wiki_home.exists():
        paths.append(wiki_home)
    source_dir = home / WIKI_SOURCE_DIR
    if source_dir.exists():
        paths.extend(
            sorted(
                path
                for path in source_dir.rglob("*.md")
                if path.is_file() and "source-cards-archive" not in path.parts
            )
        )
    deduped: dict[str, Path] = {str(path): path for path in paths}
    return [deduped[key] for key in sorted(deduped)]


def _prune_stale_palantir_wiki_documents(db_path: Path, active_paths: set[str]) -> int:
    from dharma_swarm.engine.event_memory import ensure_memory_plane_schema_sync

    with sqlite3.connect(str(db_path)) as db:
        ensure_memory_plane_schema_sync(db)
        rows = db.execute(
            "SELECT doc_id, source_path FROM source_documents WHERE source_kind = ?",
            ("palantir_pilot_wiki",),
        ).fetchall()
        stale_doc_ids = [
            str(doc_id)
            for doc_id, source_path in rows
            if str(source_path) not in active_paths
            or "source-cards-archive" in Path(str(source_path)).parts
        ]
        for doc_id in stale_doc_ids:
            db.execute("DELETE FROM source_chunks WHERE doc_id = ?", (doc_id,))
            db.execute("DELETE FROM source_documents WHERE doc_id = ?", (doc_id,))
        db.commit()
    return len(stale_doc_ids)


def _catalog_documents_from_source_index(
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    batch_size: int = 75,
) -> list[tuple[str, str, str, dict[str, Any]]]:
    index_path, payload = _load_latest_source_index(dharma_home)
    rows_raw = payload.get("urls")
    rows = [row for row in rows_raw if isinstance(row, dict)] if isinstance(rows_raw, list) else []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        family = str(row.get("family") or "unknown")
        grouped.setdefault(family, []).append(row)

    documents: list[tuple[str, str, str, dict[str, Any]]] = []
    for family in sorted(grouped):
        family_rows = sorted(grouped[family], key=lambda row: str(row.get("loc") or ""))
        lines = [
            f"# Palantir Pilot Source Catalog - {family}",
            "",
            f"Source index: `{index_path or ''}`",
            f"URL count: {len(family_rows)}",
            "",
            "Boundary: public sitemap metadata only. This catalog stores URLs and metadata, not Palantir page bodies or course material.",
            "",
        ]
        size = max(1, batch_size)
        for batch_number, start in enumerate(range(0, len(family_rows), size), start=1):
            end = min(start + size, len(family_rows))
            lines.extend([f"## URLs {start + 1}-{end}", ""])
            for row in family_rows[start:end]:
                lines.append(
                    "- {url} | lastmod={lastmod} | changefreq={changefreq} | sitemap={sitemap}".format(
                        url=str(row.get("loc") or ""),
                        lastmod=str(row.get("lastmod") or ""),
                        changefreq=str(row.get("changefreq") or ""),
                        sitemap=str(row.get("sitemap") or ""),
                    )
                )
            lines.append("")
        metadata = {
            "agent_id": AGENT_ID,
            "callsign": CALLSIGN,
            "family": family,
            "source_index": str(index_path) if index_path else "",
            "url_count": len(family_rows),
            "boundary": "public sitemap metadata only",
        }
        documents.append(
            (
                family,
                f"palantir-pilot/source-catalog/{family}.md",
                "\n".join(lines),
                metadata,
            )
        )
    return documents


def index_workspace_to_memory_plane(
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    db_path: Path | str | None = None,
    source_url_batch_size: int = 75,
) -> dict[str, Any]:
    """Index Palantir Pilot wiki notes and source URL catalogs into Memory Palace.

    The indexed source catalog contains sitemap URL metadata only. It never
    stores Palantir page bodies, Learn course content, videos, labs, or private
    tenant material.
    """

    from dharma_swarm.engine.unified_index import UnifiedIndex

    home = Path(dharma_home).expanduser()
    db = Path(db_path).expanduser() if db_path else memory_plane_db_path(home)
    index = UnifiedIndex(db)

    wiki_paths = _wiki_markdown_paths(home)
    pruned_wiki_documents = _prune_stale_palantir_wiki_documents(
        db,
        {str(path) for path in wiki_paths},
    )
    wiki_documents = 0
    for path in wiki_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        index.index_document(
            "palantir_pilot_wiki",
            str(path),
            text,
            {
                "agent_id": AGENT_ID,
                "callsign": CALLSIGN,
                "source_role": "palantir_pilot_wiki_note",
                "boundary": "original notes and source-grounded summaries only",
            },
        )
        wiki_documents += 1

    source_catalog_documents = 0
    source_urls = 0
    for _family, source_path, text, metadata in _catalog_documents_from_source_index(
        dharma_home=home,
        batch_size=source_url_batch_size,
    ):
        index.index_document(
            "palantir_pilot_source_catalog",
            source_path,
            text,
            metadata,
        )
        source_catalog_documents += 1
        source_urls += int(metadata.get("url_count") or 0)

    return {
        "schema_version": "palantir_pilot.memory_plane_index_receipt.v1",
        "agent": {"id": AGENT_ID, "callsign": CALLSIGN},
        "observed_at": _utc_now(),
        "db_path": str(db),
        "wiki_documents_indexed": wiki_documents,
        "source_catalog_documents_indexed": source_catalog_documents,
        "source_urls_indexed": source_urls,
        "pruned_wiki_documents": pruned_wiki_documents,
        "source_kinds": list(DATABASE_SOURCE_KINDS),
        "storage_boundary": "URLs, metadata, original wiki notes, summaries, and deep-card prose from robots-allowed public www.palantir.com pages; no Learn/course bodies and no private-tenant material",
        "index_stats": index.stats(),
    }


def query_source_index(
    query: str,
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    limit: int = 10,
    family: str | None = None,
) -> list[dict[str, Any]]:
    """Search the URL/metadata-only source index.

    The result intentionally contains source metadata only. It never reads or
    returns Palantir page bodies.
    """

    terms = _query_terms(query)
    if not terms:
        return []
    _path, payload = _load_latest_source_index(dharma_home)
    rows = payload.get("urls")
    if not isinstance(rows, list):
        return []

    hits: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_family = str(row.get("family") or "")
        if family and row_family != family:
            continue
        searchable = " ".join(
            str(row.get(key) or "")
            for key in ("loc", "family", "sitemap", "lastmod", "changefreq")
        )
        score = _score_text(searchable, terms)
        if score <= 0:
            continue
        hits.append(
            {
                "score": score,
                "url": str(row.get("loc") or ""),
                "family": row_family,
                "lastmod": str(row.get("lastmod") or ""),
                "sitemap": str(row.get("sitemap") or ""),
            }
        )

    hits.sort(key=lambda item: (-int(item["score"]), item["family"], item["url"]))
    return hits[: max(0, limit)]


def _snippet(text: str, terms: list[str], *, max_chars: int = 260) -> str:
    collapsed = " ".join(text.split())
    lower = collapsed.lower()
    start = 0
    positions = [lower.find(term) for term in terms if lower.find(term) >= 0]
    if positions:
        start = max(0, min(positions) - 80)
    end = min(len(collapsed), start + max_chars)
    prefix = "..." if start else ""
    suffix = "..." if end < len(collapsed) else ""
    return f"{prefix}{collapsed[start:end]}{suffix}"


def query_wiki_notes(
    query: str,
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Search Palantir Pilot markdown notes and return short snippets."""

    terms = _query_terms(query)
    if not terms:
        return []
    candidates = _wiki_markdown_paths(dharma_home)

    hits: list[dict[str, Any]] = []
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        score = _score_wiki_note(path, text, terms)
        if score <= 0:
            continue
        hits.append(
            {
                "score": score,
                "path": str(path),
                "snippet": _snippet(text, terms),
            }
        )
    hits.sort(key=lambda item: (-int(item["score"]), item["path"]))
    return hits[: max(0, limit)]


def build_query_packet(
    query: str,
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    limit: int = 10,
    family: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build an auditable local query packet for Palantir Pilot."""

    index_path, payload = _load_latest_source_index(dharma_home)
    return {
        "schema_version": "palantir_pilot.query_packet.v1",
        "agent": {"id": AGENT_ID, "callsign": CALLSIGN},
        "query": query,
        "observed_at": _utc_now(now),
        "source_boundary": (
            "Local search over source metadata, original wiki notes, and deep-card prose "
            "from robots-allowed public www.palantir.com pages; no private Palantir "
            "material and no Learn/course body storage."
        ),
        "latest_source_index": str(index_path) if index_path else "",
        "indexed_url_count": int(payload.get("url_count") or 0) if isinstance(payload, dict) else 0,
        "family_filter": family or "",
        "source_hits": query_source_index(
            query,
            dharma_home=dharma_home,
            limit=limit,
            family=family,
        ),
        "note_hits": query_wiki_notes(
            query,
            dharma_home=dharma_home,
            limit=min(limit, 5),
        ),
    }


def _answer_confidence(packet: dict[str, Any]) -> str:
    source_hits = packet.get("source_hits")
    note_hits = packet.get("note_hits")
    source_count = len(source_hits) if isinstance(source_hits, list) else 0
    note_count = len(note_hits) if isinstance(note_hits, list) else 0
    if source_count >= 2 and note_count >= 1:
        return "medium_public_source_grounded"
    if source_count or note_count:
        return "low_partial_public_source_grounding"
    return "insufficient_local_evidence"


def _answer_focus_terms(query: str) -> list[str]:
    stopwords = {
        "about",
        "after",
        "from",
        "into",
        "palantir",
        "please",
        "show",
        "that",
        "this",
        "what",
        "with",
    }
    terms = []
    for term in _query_terms(query):
        if term in stopwords or len(term) < 3:
            continue
        terms.append(term)
    return terms[:6]


def _top_families(packet: dict[str, Any]) -> list[str]:
    source_hits = packet.get("source_hits")
    counts: dict[str, int] = {}
    source_rows = source_hits if isinstance(source_hits, list) else []
    for item in source_rows:
        if not isinstance(item, dict):
            continue
        family = str(item.get("family") or "unknown")
        counts[family] = counts.get(family, 0) + 1
    return [
        family
        for family, _count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def _first_sentence(text: str) -> str:
    collapsed = " ".join(text.split())
    for delimiter in (". ", "\n"):
        if delimiter in collapsed:
            return collapsed.split(delimiter, 1)[0].strip(" .") + "."
    return collapsed[:220]


def _is_answer_synthesis_note(path_text: str) -> bool:
    path = Path(path_text)
    name = path.name.lower()
    if name.startswith(("checkpoint-", "source-index-")):
        return False
    if name in {
        "source-card-index.md",
        "curriculum-index.md",
        "orientation-index.md",
        "query-cookbook.md",
        "query-smoke-latest.md",
    }:
        return False
    if any(part.lower() in {"logs", "raw"} for part in path.parts):
        return False
    return True


def _strip_markdown_noise(lines: list[str]) -> str:
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if kept:
                break
            continue
        if stripped.startswith(("#", "|", "```")):
            continue
        if stripped.lower().startswith(("observed:", "source index:", "indexed url count:", "boundary:")):
            continue
        kept.append(stripped.lstrip("- ").strip())
    return " ".join(kept).strip()


def _extract_note_answer_claim(path_text: str, fallback: str) -> str:
    path = Path(path_text)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return _first_sentence(fallback)

    preferred_sections = {
        "source summary",
        "working thesis",
        "working interpretation",
        "focus",
        "outcome",
        "learning stages",
        "practical orientation",
        "learn catalog handling",
        "allowed intake fields",
        "current status",
        "dharma swarm contribution",
        "content",
    }
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("## "):
            continue
        title = stripped[3:].strip().lower()
        if title not in preferred_sections:
            continue
        section_lines: list[str] = []
        for candidate in lines[index + 1 :]:
            if candidate.strip().startswith("## "):
                break
            section_lines.append(candidate)
        claim = _strip_markdown_noise(section_lines)
        if claim:
            return claim[:1400]
    return _first_sentence(fallback)


def build_answer_packet_from_query_packet(
    packet: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a conservative source-grounded answer from a Palantir query packet."""

    query = str(packet.get("query") or "")
    source_hits = packet.get("source_hits")
    note_hits = packet.get("note_hits")
    sources = [item for item in source_hits if isinstance(item, dict)] if isinstance(source_hits, list) else []
    notes = [item for item in note_hits if isinstance(item, dict)] if isinstance(note_hits, list) else []
    answer_notes = [
        item
        for item in notes
        if _is_answer_synthesis_note(str(item.get("path") or ""))
    ]
    focus_terms = _answer_focus_terms(query)
    families = _top_families(packet)
    confidence_packet = {**packet, "note_hits": answer_notes}
    confidence = _answer_confidence(confidence_packet)

    cited_note_claims: list[str] = []
    for item in answer_notes[:3]:
        snippet = str(item.get("snippet") or "").strip()
        path = str(item.get("path") or "")
        claim = _extract_note_answer_claim(path, snippet) if path or snippet else ""
        if claim:
            cited_note_claims.append(claim)

    answer_lines = [
        (
            "Palantir Pilot can answer this from the local public-source workspace, "
            "but only as public-source synthesis."
        )
    ]
    if focus_terms:
        answer_lines.append(f"Focus terms found: {', '.join(focus_terms)}.")
    if families:
        answer_lines.append(f"Strongest public source families: {', '.join(families)}.")
    if cited_note_claims:
        answer_lines.append("Relevant workspace synthesis: " + " ".join(cited_note_claims))
    elif sources:
        answer_lines.append(
            "The local index currently has URL-level public-source anchors, but no stronger local note summary for this query yet."
        )
    else:
        answer_lines.append(
            "The local Palantir Pilot workspace does not yet contain enough evidence to answer this query."
        )

    limitations = [
        "No official Palantir affiliation, certification, private tenant access, or insider knowledge is claimed.",
        "Source hits are public URL metadata unless a cited wiki note is present.",
        "Do not treat this as a substitute for authorized Palantir training, docs access, or tenant-specific guidance.",
    ]
    if any(term in query.lower() for term in ("learn", "course", "catalog", "training")):
        limitations.append(
            "learn.palantir.com/page/course-catalog remains manual-review/link-only under the observed 403 boundary."
        )

    return {
        "schema_version": "palantir_pilot.answer_packet.v1",
        "agent": {"id": AGENT_ID, "callsign": CALLSIGN, "label": DISPLAY_NAME},
        "query": query,
        "observed_at": _utc_now(now),
        "answer": " ".join(answer_lines),
        "confidence": confidence,
        "source_boundary": (
            "Public-source workspace synthesis over URL metadata, original wiki notes, and "
            "deep-card prose from robots-allowed public www.palantir.com pages; no private "
            "Palantir material and no Learn/course body storage."
        ),
        "source_citations": [
            {
                "url": str(item.get("url") or ""),
                "family": str(item.get("family") or ""),
                "lastmod": str(item.get("lastmod") or ""),
                "evidence_type": "public_url_metadata",
            }
            for item in sources[:5]
        ],
        "note_citations": [
            {
                "path": str(item.get("path") or ""),
                "snippet": str(item.get("snippet") or ""),
                "evidence_type": "original_wiki_note_snippet",
            }
            for item in answer_notes[:5]
        ],
        "limitations": limitations,
        "next_steps": [
            "Read cited public docs directly before using the answer for implementation decisions.",
            "Promote stronger summaries into the Palantir Pilot wiki after source-specific review.",
            "Keep Learn/course-catalog material manual-review only unless an allowed access path is established.",
        ],
        "query_packet": packet,
    }


def build_answer_packet(
    query: str,
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    limit: int = 10,
    family: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a Palantir Pilot answer packet from the local public workspace."""

    packet = build_query_packet(
        query,
        dharma_home=dharma_home,
        limit=limit,
        family=family,
        now=now,
    )
    return build_answer_packet_from_query_packet(packet, now=now)


def record_query_packet_to_memory_plane(
    packet: dict[str, Any],
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    db_path: Path | str | None = None,
    task_id: str | None = None,
    consumer: str = QUERY_CONSUMER,
) -> dict[str, Any]:
    """Record a Palantir Pilot query packet in the Memory Palace retrieval log."""

    from dharma_swarm.engine.hybrid_retriever import RetrievalHit
    from dharma_swarm.engine.knowledge_store import KnowledgeRecord
    from dharma_swarm.engine.retrieval_feedback import RetrievalFeedbackStore

    home = Path(dharma_home).expanduser()
    db = Path(db_path).expanduser() if db_path else memory_plane_db_path(home)
    created_at = _query_observed_at(packet)
    query = str(packet.get("query") or "")
    hits: list[RetrievalHit] = []

    source_hits = packet.get("source_hits")
    source_rows = source_hits if isinstance(source_hits, list) else []
    for item in source_rows:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        if not url:
            continue
        text = " ".join(
            part
            for part in (
                "Palantir public source URL",
                f"family={item.get('family', '')}",
                f"lastmod={item.get('lastmod', '')}",
                f"url={url}",
            )
            if part
        )
        record = KnowledgeRecord(
            text=text,
            metadata={
                "agent_id": AGENT_ID,
                "callsign": CALLSIGN,
                "source_kind": "palantir_pilot_source_catalog",
                "source_path": url,
                "source_ref": str(packet.get("latest_source_index") or ""),
                "family": str(item.get("family") or ""),
                "boundary": "public URL metadata only",
            },
            record_id=_stable_id("palantir_source", url),
            created_at=created_at,
        )
        hits.append(
            RetrievalHit(
                record=record,
                score=float(item.get("score") or 0),
                evidence={"hit_kind": "source_index", "packet_schema": packet.get("schema_version")},
            )
        )

    note_hits = packet.get("note_hits")
    note_rows = note_hits if isinstance(note_hits, list) else []
    for item in note_rows:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        snippet = str(item.get("snippet") or "")
        if not path and not snippet:
            continue
        record = KnowledgeRecord(
            text=snippet or path,
            metadata={
                "agent_id": AGENT_ID,
                "callsign": CALLSIGN,
                "source_kind": "palantir_pilot_wiki",
                "source_path": path,
                "source_ref": Path(path).name if path else "",
                "boundary": "original wiki note snippet only",
            },
            record_id=_stable_id("palantir_note", path or snippet),
            created_at=created_at,
        )
        hits.append(
            RetrievalHit(
                record=record,
                score=float(item.get("score") or 0),
                evidence={"hit_kind": "wiki_note", "packet_schema": packet.get("schema_version")},
            )
        )

    store = RetrievalFeedbackStore(db)
    effective_task_id = task_id or f"{CALLSIGN}:{_stable_id('query', query)}"
    logged = store.log_hits(
        query,
        hits,
        consumer=consumer,
        task_id=effective_task_id,
    )
    stats = store.stats()
    return {
        "schema_version": "palantir_pilot.database_query_receipt.v1",
        "agent": {"id": AGENT_ID, "callsign": CALLSIGN},
        "observed_at": _utc_now(),
        "db_path": str(db),
        "consumer": consumer,
        "query": query,
        "task_id": effective_task_id,
        "logged_hit_count": logged,
        "retrieval_log_rows": stats["retrieval_log"],
        "storage_boundary": "query text, result metadata, and short snippets only",
    }


__all__ = [
    "AGENT_ID",
    "CALLSIGN",
    "DISPLAY_NAME",
    "FORBIDDEN_ACTIONS",
    "NATS_SUBJECT",
    "PUBLIC_SOURCES",
    "VERIFIER_COMMANDS",
    "build_answer_packet",
    "build_answer_packet_from_query_packet",
    "build_external_worker_registration",
    "build_query_packet",
    "build_source_manifest",
    "format_markdown",
    "index_workspace_to_memory_plane",
    "latest_source_index_path",
    "memory_plane_db_path",
    "query_source_index",
    "query_wiki_notes",
    "record_query_packet_to_memory_plane",
    "summarize_source_families",
    "write_manifest_json",
    "write_wiki_home",
]
