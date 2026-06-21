"""Palantir Pilot — constants, manifest building, and file-writing helpers.

This module owns the agent identity constants, public source declarations,
forbidden-action policy, `build_source_manifest`, `build_external_worker_registration`,
`format_markdown`, `write_manifest_json`, and `write_wiki_home`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DHARMA_HOME = Path.home() / ".dharma"
DHARMA_HOME_SURFACE = str(Path("~") / ".dharma")

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
    f"{DHARMA_HOME_SURFACE}/knowledge/wiki/research/palantir-pilot.md",
    f"{DHARMA_HOME_SURFACE}/knowledge/wiki/research/palantir-pilot/**",
    f"{DHARMA_HOME_SURFACE}/knowledge/wiki/raw/palantir-pilot/**",
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
