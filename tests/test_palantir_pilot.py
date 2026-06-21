from __future__ import annotations

from pathlib import Path
import sqlite3

from dharma_swarm.palantir_pilot import (
    AGENT_ID,
    CALLSIGN,
    PUBLIC_SOURCES,
    build_answer_packet,
    build_external_worker_registration,
    build_query_packet,
    build_source_manifest,
    format_markdown,
    index_workspace_to_memory_plane,
    query_source_index,
    record_query_packet_to_memory_plane,
    summarize_source_families,
)
from scripts.research import palantir_public_source_cards as source_cards
from scripts.research.palantir_pilot_curriculum import build_curriculum_maps
from scripts.research.palantir_pilot_orientation import build_orientation_maps
from scripts.research.palantir_source_card_balanced_expand import run_balanced_expansion
from scripts.research.palantir_contribution_packets import build_contribution_packets
from scripts.research.palantir_learning_backlog import build_learning_backlog
from scripts.research.palantir_query_cookbook import build_query_cookbook
from scripts.research.palantir_playbook_evals import build_eval_suites
from scripts.research.palantir_source_card_playbooks import build_playbooks
from scripts.research.palantir_source_card_cleanup import cleanup_source_cards
from scripts.research.palantir_source_card_quality import build_quality_report, write_quality_outputs


def test_public_source_policy_blocks_learn_autonomous_scrape(tmp_path):
    manifest = build_source_manifest(repo_root=tmp_path, dharma_home=tmp_path / ".dharma")
    sources = {source["id"]: source for source in manifest["public_sources"]}

    assert sources["palantir_docs_sitemap"]["access_status"].startswith(
        "autonomous_fetch_allowed"
    )
    assert sources["palantir_learn_course_catalog"]["access_status"].startswith(
        "robots_fetch_403"
    )
    assert (
        manifest["source_policy"]["learn_palantir_status"]
        == "blocked_for_autonomous_scrape_until_allowed_access_is_confirmed"
    )
    assert any(
        "never committed" in entry
        for entry in manifest["source_policy"]["disallowed_storage"]
    )


def test_source_family_summary_classifies_major_palantir_surfaces():
    counts = summarize_source_families(
        [
            "https://palantir.com/docs/foundry/getting-started/overview/",
            "https://palantir.com/docs/foundry/aip/overview/",
            "https://palantir.com/docs/apollo/",
            "https://palantir.com/docs/gotham/",
            "https://www.palantir.com/platforms/aip/",
        ]
    )

    assert counts["foundry"] == 1
    assert counts["aip"] == 1
    assert counts["apollo"] == 1
    assert counts["gotham"] == 1
    assert counts["site"] == 1


def test_external_worker_registration_is_default_deny(tmp_path):
    worker = build_external_worker_registration(dharma_home=tmp_path / ".dharma")

    assert worker.agent_uid == AGENT_ID
    assert worker.callsign == CALLSIGN
    assert worker.authority.value == "external_worker_evidence_only"
    assert worker.endpoint == "pending://manual"
    assert worker.mailbox == "nats://dharma.a2a.palantir-pilot"
    assert worker.autonomy_policy.requires_approval is True
    assert worker.autonomy_policy.can_write_source is False
    assert worker.workspace_policy.repo_writes_allowed is False
    assert worker.metadata["public_source_only"] is True
    assert worker.metadata["official_affiliation"] is False
    assert "blocked" in worker.metadata["learn_palantir_autonomous_scrape"]
    assert "source_card_task_playbooks" in worker.capabilities
    assert "balanced_source_card_expansion" in worker.capabilities
    assert "playbook_fluency_evaluations" in worker.capabilities
    assert "palantir_pattern_contribution_packets" in worker.capabilities
    assert "operator_query_cookbook" in worker.capabilities
    assert "answer_surface_smoke_verifier" in worker.capabilities
    assert "bounded_learning_backlog" in worker.capabilities
    assert "self_improvement_loop_planning" in worker.capabilities


def test_markdown_report_contains_boundary_and_verifiers(tmp_path):
    manifest = build_source_manifest(repo_root=tmp_path, dharma_home=tmp_path / ".dharma")
    text = format_markdown(manifest)

    assert "# Palantir Pilot" in text
    assert "No official Palantir affiliation" in text
    assert "learn_course_catalog" in text
    assert "Do not mirror Learn/course bodies" in text
    assert "Playbook index" in text
    assert "Evaluation index" in text
    assert "Contribution index" in text
    assert "Query cookbook" in text
    assert "Query smoke report" in text
    assert "Learning backlog" in text
    assert "Learning loop" in text
    assert "palantir_source_card_playbooks.py --json" in text
    assert "palantir_playbook_evals.py --json" in text
    assert "palantir_contribution_packets.py --json" in text
    assert "palantir_query_cookbook.py --strict --json" in text
    assert "palantir_learning_backlog.py --strict --json" in text
    assert "palantir_source_card_balanced_expand.py --dry-run" in text
    assert "pytest -q tests/test_palantir_pilot.py" in text


def test_public_sources_have_storage_policy():
    assert PUBLIC_SOURCES
    for source in PUBLIC_SOURCES:
        assert source["url"].startswith("https://")
        assert source["ingestion_policy"]


def test_query_packet_searches_source_index_and_wiki_notes(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 2,
          "urls": [
            {
              "loc": "https://palantir.com/docs/foundry/architecture-center/ontology-system/",
              "family": "foundry",
              "lastmod": "2026-06-11T15:53:36.107Z",
              "sitemap": "https://www.palantir.com/docs/sitemap.xml"
            },
            {
              "loc": "https://palantir.com/docs/apollo/",
              "family": "apollo",
              "lastmod": "2026-06-11T15:53:36.106Z",
              "sitemap": "https://www.palantir.com/docs/sitemap.xml"
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    wiki_dir = dharma_home / "knowledge/wiki/research/palantir-pilot"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "ontology-map.md").write_text(
        "# Ontology Map\n\nOntology maps object and action concepts for operational decisions.\n",
        encoding="utf-8",
    )

    packet = build_query_packet("ontology", dharma_home=dharma_home)

    assert packet["indexed_url_count"] == 2
    assert packet["source_hits"][0]["url"].endswith("/ontology-system/")
    assert packet["note_hits"][0]["path"].endswith("ontology-map.md")


def test_checkpoint_queries_rank_checkpoint_notes(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 1,
          "urls": [
            {"loc": "https://palantir.com/docs/foundry/checkpoints/checkpoint-types/", "family": "foundry"}
          ]
        }
        """,
        encoding="utf-8",
    )
    wiki_dir = dharma_home / "knowledge/wiki/research/palantir-pilot"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "source-card-index.md").write_text(
        (
            "# Palantir Pilot Source Card Index\n\nCard count: 9999\n"
            "checkpoint 20260614T1428Z Palantir Pilot 2807 cards 56 63 coverage verifier receipts "
        )
        * 500,
        encoding="utf-8",
    )
    (wiki_dir / "checkpoint-20260614T1428Z.md").write_text(
        "# Palantir Pilot Public-Docs Growth Checkpoint\n\n"
        "Observed: 2026-06-14T14:28Z\n"
        "New canonical cards: 2807\n"
        "Allowed public-doc candidate coverage: 56.63%\n",
        encoding="utf-8",
    )

    packet = build_query_packet(
        "checkpoint 20260614T1428Z Palantir Pilot 2807 cards 56.63 coverage verifier receipts",
        dharma_home=dharma_home,
    )

    assert packet["note_hits"][0]["path"].endswith("checkpoint-20260614T1428Z.md")


def test_query_source_index_respects_family_filter(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 2,
          "urls": [
            {"loc": "https://palantir.com/docs/foundry/aip/overview/", "family": "aip"},
            {"loc": "https://palantir.com/docs/foundry/ontology/foo/", "family": "foundry"}
          ]
        }
        """,
        encoding="utf-8",
    )

    hits = query_source_index("foundry", dharma_home=dharma_home, family="aip")

    assert len(hits) == 1
    assert hits[0]["family"] == "aip"


def test_orientation_maps_write_receipt_and_learn_boundary(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 4,
          "urls": [
            {"loc": "https://palantir.com/docs/foundry/getting-started/overview/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/foundry/api/ontologies-v2-resources/ontology-objects/ontology-object-basics/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/apollo/release-channels/", "family": "apollo"},
            {"loc": "https://palantir.com/docs/gotham/security/", "family": "gotham"}
          ]
        }
        """,
        encoding="utf-8",
    )

    receipt = build_orientation_maps(dharma_home=dharma_home, limit_per_map=2)

    assert len(receipt["maps"]) == 7
    assert (dharma_home / "knowledge/wiki/research/palantir-pilot/orientation-index.md").exists()
    assert receipt["boundary"] == "public sitemap metadata only; no full page/course mirroring"
    assert (dharma_home / "knowledge/wiki/raw/palantir-pilot").joinpath(
        receipt["receipt_path"].split("/")[-1]
    ).exists()
    course_map = (
        dharma_home
        / "knowledge/wiki/research/palantir-pilot/maps/course-path-boundary.md"
    ).read_text(encoding="utf-8")
    assert "Learn Boundary" in course_map
    assert "403 boundary" in course_map


def test_source_cards_extract_bounded_public_page_facts(tmp_path, monkeypatch):
    long_tail = "X" * 320
    html = f"""
    <html>
      <head>
        <title>Foundry Overview</title>
        <meta name="description" content="Public Foundry overview description">
      </head>
      <body>
        <h1>Foundry</h1>
        <h2>Ontology</h2>
        <p>This public paragraph explains Foundry orientation, ontology, and governed action. {long_tail}</p>
      </body>
    </html>
    """

    def fake_fetch(url: str, *, timeout: int = 30):
        return 200, html, len(html.encode("utf-8"))

    monkeypatch.setattr(source_cards, "fetch_html", fake_fetch)
    receipt = source_cards.build_source_cards(
        urls=["https://palantir.com/docs/foundry/getting-started/overview/"],
        observed_at="2026-06-14T00:00:00Z",
        timeout=1,
    )
    outputs = source_cards.write_outputs(tmp_path / ".dharma", receipt)
    card_path = outputs["card_paths"][0]
    card_text = Path(card_path).read_text(encoding="utf-8")
    card = receipt["cards"][0]

    assert source_cards.is_allowed_source_card_url(
        "https://palantir.com/docs/foundry/getting-started/overview/"
    )
    assert not source_cards.is_allowed_source_card_url(
        "https://learn.palantir.com/page/course-catalog"
    )
    assert not source_cards.is_allowed_source_card_url(
        "https://palantir.com/docs/apollo/apollo-cli-deprecated/apollo-cli_get-product-releases/"
    )
    assert card["facts"]["title"] == "Foundry Overview"
    assert len(card["facts"]["short_excerpt"]) == 280
    assert "No full page/course mirroring" in card_text
    assert "source-card-index.md" in outputs["index_path"]


def test_balanced_source_card_expansion_selects_topics_and_writes_receipt(tmp_path, monkeypatch):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 6,
          "urls": [
            {"loc": "https://palantir.com/docs/foundry/aip/overview/", "family": "aip"},
            {"loc": "https://palantir.com/docs/foundry/aip/aip-security/", "family": "aip"},
            {"loc": "https://palantir.com/docs/foundry/aip/aip-observability/", "family": "aip"},
            {"loc": "https://palantir.com/docs/apollo/apollo-cli/apollo-cli_product-release_list/", "family": "apollo"},
            {"loc": "https://palantir.com/docs/apollo/apollo-cli/apollo-cli_environment_version_compare/", "family": "apollo"},
            {"loc": "https://learn.palantir.com/page/course-catalog", "family": "learn"}
          ]
        }
        """,
        encoding="utf-8",
    )
    card_dir = dharma_home / "knowledge/wiki/research/palantir-pilot/source-cards"
    card_dir.mkdir(parents=True)
    (card_dir / "aip-overview.md").write_text(
        "# Existing AIP Overview\n\n"
        "Source URL: https://palantir.com/docs/foundry/aip/overview/\n",
        encoding="utf-8",
    )
    html = """
    <html>
      <head>
        <title>Palantir Public Doc</title>
        <meta name="description" content="Public Palantir source-card metadata">
      </head>
      <body>
        <h1>Public Doc</h1>
        <p>This public paragraph is long enough to become a bounded source-card excerpt for the Palantir Pilot test fixture.</p>
      </body>
    </html>
    """

    def fake_fetch(url: str, *, timeout: int = 30):
        assert "learn.palantir.com" not in url
        return 200, html, len(html.encode("utf-8"))

    monkeypatch.setattr(source_cards, "fetch_html", fake_fetch)

    receipt = run_balanced_expansion(
        dharma_home=dharma_home,
        topics=["aip", "apollo"],
        limit_per_topic=2,
        timeout=1,
        write=True,
        observed_at="2026-06-14T00:00:00Z",
    )

    assert receipt["schema_version"] == "palantir_pilot.balanced_source_card_expansion.v1"
    assert receipt["selected_url_count"] == 4
    assert receipt["card_count"] == 4
    assert receipt["outputs"]["index_card_count"] == 5
    assert Path(receipt["balanced_receipt_path"]).exists()
    assert all("learn.palantir.com" not in url for url in receipt["selected_urls"])
    assert any(item["topic"] == "aip" for item in receipt["topic_selections"])


def test_balanced_source_card_expansion_dry_run_does_not_fetch_pages(tmp_path, monkeypatch):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 3,
          "urls": [
            {"loc": "https://palantir.com/docs/foundry/aip/aip-security/", "family": "aip"},
            {"loc": "https://palantir.com/docs/foundry/aip/aip-observability/", "family": "aip"},
            {"loc": "https://palantir.com/docs/foundry/aip/aip-compute-usage/", "family": "aip"}
          ]
        }
        """,
        encoding="utf-8",
    )

    def fail_fetch(url: str, *, timeout: int = 30):
        raise AssertionError(f"dry-run fetched {url}")

    monkeypatch.setattr(source_cards, "fetch_html", fail_fetch)

    receipt = run_balanced_expansion(
        dharma_home=dharma_home,
        topics=["aip"],
        limit_per_topic=3,
        timeout=1,
        write=False,
        observed_at="2026-06-14T00:00:00Z",
    )

    assert receipt["status"] == "dry_run"
    assert receipt["selected_url_count"] == 3
    assert receipt["planned_card_count"] == 3
    assert receipt["card_count"] == 0
    assert receipt["fetch_receipts"] == []
    assert receipt["outputs"] == {}
    assert "balanced_receipt_path" not in receipt


def test_source_cards_use_meta_description_excerpt_fallback():
    html = """
    <html>
      <head>
        <title>Apollo CLI</title>
        <meta name="description" content="Manage Apollo product releases from public command reference metadata">
      </head>
      <body>
        <h1>apollo-cli product-release</h1>
      </body>
    </html>
    """

    facts = source_cards.extract_page_facts(html)

    assert facts["title"] == "Apollo CLI"
    assert facts["short_excerpt"] == "Manage Apollo product releases from public command reference metadata"


def test_curriculum_maps_write_learn_intake_and_queryable_paths(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 5,
          "urls": [
            {"loc": "https://palantir.com/docs/foundry/getting-started/overview/", "family": "foundry", "lastmod": "2026-06-11T15:53:36.107Z"},
            {"loc": "https://palantir.com/docs/foundry/getting-started/next-steps-by-role/", "family": "foundry", "lastmod": "2026-06-11T15:53:36.107Z"},
            {"loc": "https://palantir.com/docs/foundry/api/ontologies-v2-resources/ontology-objects/list-objects/", "family": "foundry", "lastmod": "2026-06-11T15:53:36.117Z"},
            {"loc": "https://palantir.com/docs/foundry/aip/aip-security/", "family": "aip", "lastmod": "2026-06-11T15:53:36.117Z"},
            {"loc": "https://palantir.com/docs/apollo/apollo-getting-started/getting-started-with-apollo/", "family": "apollo", "lastmod": "2026-06-11T15:53:36.117Z"}
          ]
        }
        """,
        encoding="utf-8",
    )
    wiki_dir = dharma_home / "knowledge/wiki/research/palantir-pilot"
    card_dir = wiki_dir / "source-cards"
    card_dir.mkdir(parents=True)
    (wiki_dir / "source-card-index.md").write_text(
        "# Source Cards\n\n"
        "- [https://palantir.com/docs/foundry/getting-started/next-steps-by-role/](source-cards/docs-foundry-getting-started-next-steps-by-role.md)\n",
        encoding="utf-8",
    )
    (card_dir / "docs-foundry-getting-started-next-steps-by-role.md").write_text(
        "# Palantir Source Card: Next steps by user role\n\n"
        "Source URL: https://palantir.com/docs/foundry/getting-started/next-steps-by-role/\n",
        encoding="utf-8",
    )

    receipt = build_curriculum_maps(dharma_home=dharma_home, limit_per_path=3)

    assert len(receipt["curriculum_paths"]) == 6
    assert receipt["source_card_count"] == 1
    assert receipt["boundary"].startswith("public metadata/source-card synthesis")
    assert Path(receipt["output_index"]).exists()
    assert Path(receipt["learn_intake"]).exists()
    intake_text = Path(receipt["learn_intake"]).read_text(encoding="utf-8")
    assert "manual-review/link-only" in intake_text
    assert "course_title" in intake_text
    assert "Autonomous fetch of Learn robots returned 403" in intake_text

    packet = build_query_packet(
        "learn course curriculum ontology builder",
        dharma_home=dharma_home,
        limit=5,
    )

    assert any("curriculum" in item["path"] for item in packet["note_hits"])

    intake_packet = build_query_packet(
        "learn course catalog intake",
        dharma_home=dharma_home,
        limit=5,
    )

    assert any("learn-course-catalog-intake.md" in item["path"] for item in intake_packet["note_hits"])


def test_source_card_playbooks_write_task_synthesis_and_queryable_paths(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 3,
          "urls": [
            {"loc": "https://palantir.com/docs/foundry/aip/best-practices-prompt-engineering/", "family": "aip"},
            {"loc": "https://palantir.com/docs/foundry/api/ontology-resources/objects/search-objects/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/apollo/apollo-cli/apollo-cli_product-release_list/", "family": "apollo"}
          ]
        }
        """,
        encoding="utf-8",
    )
    card_dir = dharma_home / "knowledge/wiki/research/palantir-pilot/source-cards"
    card_dir.mkdir(parents=True)
    (card_dir / "aip-prompt.md").write_text(
        "# Palantir Source Card: Best practices for LLM prompt engineering - Palantir\n\n"
        "Source URL: https://palantir.com/docs/foundry/aip/best-practices-prompt-engineering/\n"
        "Family: `aip`\n\n"
        "Boundary: title, metadata, headings, one short excerpt, and original orientation only. No full page/course mirroring.\n\n"
        "## Source Summary\n\n"
        "- Title: Best practices for LLM prompt engineering - Palantir\n"
        "- Meta description: Writing effective prompts\n"
        "- Short excerpt: Prompt engineering guides LLMs to generate desired outputs in governed AIP workflows.\n\n"
        "## Extracted Headings\n\n"
        "- `h1` Best practices for LLM prompt engineering\n"
        "- `h2` Key strategies for effective prompting\n",
        encoding="utf-8",
    )
    (card_dir / "ontology-search.md").write_text(
        "# Palantir Source Card: Search Objects - API Reference - Palantir\n\n"
        "Source URL: https://palantir.com/docs/foundry/api/ontology-resources/objects/search-objects/\n"
        "Family: `foundry`\n\n"
        "## Source Summary\n\n"
        "- Title: Search Objects - API Reference - Palantir\n"
        "- Meta description: Search objects\n"
        "- Short excerpt: Search for objects in the specified ontology and object type.\n\n"
        "## Extracted Headings\n\n"
        "- `h1` Search Objects\n"
        "- `h2` Request body\n",
        encoding="utf-8",
    )
    (card_dir / "apollo-release-list.md").write_text(
        "# Palantir Source Card: Apollo CLI - apollo-cli product-release list - Palantir\n\n"
        "Source URL: https://palantir.com/docs/apollo/apollo-cli/apollo-cli_product-release_list/\n"
        "Family: `apollo`\n\n"
        "## Source Summary\n\n"
        "- Title: Apollo CLI - apollo-cli product-release list - Palantir\n"
        "- Meta description: List product releases\n"
        "- Short excerpt: List product releases for a given product.\n\n"
        "## Extracted Headings\n\n"
        "- `h1` apollo-cli product-release list\n"
        "- `h3` Flags\n",
        encoding="utf-8",
    )

    receipt = build_playbooks(dharma_home=dharma_home, limit_per_playbook=2)

    assert receipt["playbook_count"] == 6
    assert receipt["source_card_count"] == 3
    assert receipt["boundary"].startswith("bounded public source-card synthesis")
    assert Path(receipt["output_index"]).exists()
    aip_playbook = next(
        item for item in receipt["playbooks"] if item["slug"] == "aip-governed-builder-loop"
    )
    aip_text = Path(aip_playbook["path"]).read_text(encoding="utf-8")
    assert "Operating Loop" in aip_text
    assert "Prompt engineering guides LLMs" in aip_text
    assert "No Palantir page bodies" in aip_text
    assert "https://palantir.com/docs/foundry/aip/best-practices-prompt-engineering/" in aip_text

    packet = build_query_packet(
        "AIP governed builder playbook prompt engineering",
        dharma_home=dharma_home,
        limit=5,
    )

    assert any("aip-governed-builder-loop.md" in item["path"] for item in packet["note_hits"])


def test_playbook_evals_write_fluency_suites_and_queryable_paths(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 3,
          "urls": [
            {"loc": "https://palantir.com/docs/foundry/aip/bring-your-own-model/", "family": "aip"},
            {"loc": "https://palantir.com/docs/foundry/api/ontology-resources/objects/search-objects/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/apollo/apollo-cli/apollo-cli_product-release_list/", "family": "apollo"}
          ]
        }
        """,
        encoding="utf-8",
    )
    card_dir = dharma_home / "knowledge/wiki/research/palantir-pilot/source-cards"
    card_dir.mkdir(parents=True)
    (card_dir / "aip-byom.md").write_text(
        "# Palantir Source Card: Bring your own model - Palantir\n\n"
        "Source URL: https://palantir.com/docs/foundry/aip/bring-your-own-model/\n"
        "Family: `aip`\n\n"
        "## Source Summary\n\n"
        "- Title: Bring your own model - Palantir\n"
        "- Meta description: Registered model metadata\n"
        "- Short excerpt: Bring-your-own-model connects external LLMs or accounts to governed AIP workflows.\n\n"
        "## Extracted Headings\n\n"
        "- `h1` Bring your own model to AIP\n"
        "- `h2` Permissions and enablement\n",
        encoding="utf-8",
    )
    (card_dir / "ontology-search.md").write_text(
        "# Palantir Source Card: Search Objects - Palantir\n\n"
        "Source URL: https://palantir.com/docs/foundry/api/ontology-resources/objects/search-objects/\n"
        "Family: `foundry`\n\n"
        "## Source Summary\n\n"
        "- Title: Search Objects - Palantir\n"
        "- Meta description: Search object metadata\n"
        "- Short excerpt: Search for objects in an ontology object type.\n\n"
        "## Extracted Headings\n\n"
        "- `h1` Search Objects\n",
        encoding="utf-8",
    )
    (card_dir / "apollo-release-list.md").write_text(
        "# Palantir Source Card: Apollo CLI product-release list - Palantir\n\n"
        "Source URL: https://palantir.com/docs/apollo/apollo-cli/apollo-cli_product-release_list/\n"
        "Family: `apollo`\n\n"
        "## Source Summary\n\n"
        "- Title: Apollo CLI product-release list - Palantir\n"
        "- Meta description: List product releases\n"
        "- Short excerpt: List product releases for a product.\n\n"
        "## Extracted Headings\n\n"
        "- `h1` apollo-cli product-release list\n",
        encoding="utf-8",
    )

    build_playbooks(dharma_home=dharma_home, limit_per_playbook=2)
    receipt = build_eval_suites(
        dharma_home=dharma_home,
        anchors_per_suite=2,
        observed_at="2026-06-14T00:00:00Z",
    )

    assert receipt["schema_version"] == "palantir_pilot.playbook_eval_receipt.v1"
    assert receipt["suite_count"] == 6
    assert receipt["question_count"] == 24
    assert receipt["source_card_count"] == 3
    assert Path(receipt["output_index"]).exists()
    aip_suite = next(
        suite for suite in receipt["suites"] if suite["slug"] == "aip-governed-builder-loop"
    )
    aip_text = Path(aip_suite["path"]).read_text(encoding="utf-8")
    assert "Evaluation Suite" in aip_text
    assert "boundary_and_escalation" in aip_text
    assert "Learn remains manual-review/link-only" in aip_text
    assert "https://palantir.com/docs/foundry/aip/bring-your-own-model/" in aip_text

    packet = build_query_packet(
        "AIP governed builder evaluation boundary refusal registered models",
        dharma_home=dharma_home,
        limit=5,
    )

    assert any("aip-governed-builder-loop-eval.md" in item["path"] for item in packet["note_hits"])


def test_contribution_packets_write_swarm_synthesis_and_queryable_paths(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 3,
          "urls": [
            {"loc": "https://palantir.com/docs/foundry/aip/aip-observability/", "family": "aip"},
            {"loc": "https://palantir.com/docs/foundry/api/ontology-resources/actions/action-basics/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/apollo/apollo-cli/apollo-cli_environment_version_compare/", "family": "apollo"}
          ]
        }
        """,
        encoding="utf-8",
    )
    card_dir = dharma_home / "knowledge/wiki/research/palantir-pilot/source-cards"
    card_dir.mkdir(parents=True)
    (card_dir / "aip-observability.md").write_text(
        "# Palantir Source Card: AIP observability - Palantir\n\n"
        "Source URL: https://palantir.com/docs/foundry/aip/aip-observability/\n"
        "Family: `aip`\n\n"
        "## Source Summary\n\n"
        "- Title: AIP observability - Palantir\n"
        "- Meta description: Observe model usage and operational behavior\n"
        "- Short excerpt: Observability helps teams inspect model usage, traces, and governed AIP behavior.\n\n"
        "## Extracted Headings\n\n"
        "- `h1` AIP observability\n",
        encoding="utf-8",
    )
    (card_dir / "action-basics.md").write_text(
        "# Palantir Source Card: Action basics - Palantir\n\n"
        "Source URL: https://palantir.com/docs/foundry/api/ontology-resources/actions/action-basics/\n"
        "Family: `foundry`\n\n"
        "## Source Summary\n\n"
        "- Title: Action basics - Palantir\n"
        "- Meta description: Ontology actions\n"
        "- Short excerpt: Actions represent governed changes against ontology-backed operational objects.\n\n"
        "## Extracted Headings\n\n"
        "- `h1` Action basics\n",
        encoding="utf-8",
    )
    (card_dir / "apollo-environment-compare.md").write_text(
        "# Palantir Source Card: Apollo environment version compare - Palantir\n\n"
        "Source URL: https://palantir.com/docs/apollo/apollo-cli/apollo-cli_environment_version_compare/\n"
        "Family: `apollo`\n\n"
        "## Source Summary\n\n"
        "- Title: Apollo environment version compare - Palantir\n"
        "- Meta description: Compare environment versions\n"
        "- Short excerpt: Compare versions across Apollo environments before promotion decisions.\n\n"
        "## Extracted Headings\n\n"
        "- `h1` apollo-cli environment version compare\n",
        encoding="utf-8",
    )

    receipt = build_contribution_packets(
        dharma_home=dharma_home,
        anchors_per_packet=2,
        observed_at="2026-06-14T00:00:00Z",
    )

    assert receipt["schema_version"] == "palantir_pilot.contribution_packet_receipt.v1"
    assert receipt["packet_count"] == 6
    assert receipt["source_card_count"] == 3
    assert Path(receipt["output_index"]).exists()
    aip_packet = next(
        packet for packet in receipt["packets"] if packet["slug"] == "aip-governed-builder-loop"
    )
    aip_text = Path(aip_packet["path"]).read_text(encoding="utf-8")
    assert "Dharma Swarm Contribution Packet" in aip_text
    assert "Pair every model-facing workflow with usage" in aip_text
    assert "Learn remains manual-review/link-only" in aip_text
    assert "https://palantir.com/docs/foundry/aip/aip-observability/" in aip_text

    packet = build_query_packet(
        "Dharma Swarm AIP contribution governance observability model access",
        dharma_home=dharma_home,
        limit=5,
    )

    assert "aip-governed-builder-loop-contribution.md" in packet["note_hits"][0]["path"]
    assert any(
        "aip-governed-builder-loop-contribution.md" in item["path"]
        for item in packet["note_hits"]
    )


def test_query_cookbook_smokes_answer_surface_and_is_queryable(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 8,
          "urls": [
            {"loc": "https://palantir.com/docs/foundry/getting-started/projects-and-resources/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/foundry/api/ontology-resources/actions/action-basics/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/foundry/aip/aip-observability/", "family": "aip"},
            {"loc": "https://palantir.com/docs/foundry/aip/bring-your-own-model/", "family": "aip"},
            {"loc": "https://palantir.com/docs/foundry/ontology-sdk/typescript-osdk/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/apollo/apollo-cli/apollo-cli_environment_version_compare/", "family": "apollo"},
            {"loc": "https://palantir.com/docs/gotham/api/target-workbench-v2-resources/target-boards/load-target-board/", "family": "gotham"},
            {"loc": "https://www.palantir.com/pcl/palantir-ai-policy-contributions/", "family": "site"}
          ]
        }
        """,
        encoding="utf-8",
    )
    wiki_dir = dharma_home / "knowledge/wiki/research/palantir-pilot"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "learn-course-catalog-intake.md").write_text(
        "# Palantir Learn Course Catalog Manual Intake\n\n"
        "Boundary: manual-review/link-only. Autonomous fetch of Learn robots returned 403.\n"
        "Do not scrape course bodies, videos, labs, transcripts, or quizzes.\n",
        encoding="utf-8",
    )
    contribution_dir = wiki_dir / "contributions"
    contribution_dir.mkdir()
    (contribution_dir / "aip-governed-builder-loop-contribution.md").write_text(
        "# AIP Governed Builder Loop Playbook - Dharma Swarm Contribution Packet\n\n"
        "## Dharma Swarm Contribution\n\n"
        "Pair every model-facing workflow with usage, observability, and evaluation receipts.\n"
        "Treat model access as governed capability, not generic chat.\n",
        encoding="utf-8",
    )
    (wiki_dir / "ontology-map.md").write_text(
        "# Ontology Map\n\n"
        "Ontology maps objects, links, actions, interfaces, and object sets for operational apps.\n",
        encoding="utf-8",
    )

    receipt = build_query_cookbook(
        dharma_home=dharma_home,
        observed_at="2026-06-14T00:00:00Z",
        limit=8,
    )

    assert receipt["schema_version"] == "palantir_pilot.query_cookbook_receipt.v1"
    assert receipt["recipe_count"] == 8
    assert receipt["pass_count"] == 8
    assert receipt["fail_count"] == 0
    assert receipt["strict_pass"] is True
    assert Path(receipt["output_index"]).exists()
    assert Path(receipt["smoke_report"]).exists()
    cookbook_text = Path(receipt["output_index"]).read_text(encoding="utf-8")
    assert "Ask Palantir Pilot" in cookbook_text
    assert "manual-review/link-only" in cookbook_text
    learn_row = next(row for row in receipt["recipes"] if row["slug"] == "learn-course-boundary")
    assert learn_row["checks"]["learn_boundary_present"] is True
    contribution_row = next(
        row for row in receipt["recipes"] if row["slug"] == "swarm-contribution-pattern"
    )
    assert contribution_row["checks"]["expected_note_fragment"] is True

    packet = build_query_packet(
        "Ask Palantir Pilot query cookbook smoke Learn boundary",
        dharma_home=dharma_home,
        limit=5,
    )

    assert any("query-cookbook.md" in item["path"] for item in packet["note_hits"])


def test_learning_backlog_plans_bounded_growth_and_is_queryable(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 6,
          "urls": [
            {"loc": "https://palantir.com/docs/foundry/aip/overview/", "family": "aip"},
            {"loc": "https://palantir.com/docs/foundry/aip/aip-observability/", "family": "aip"},
            {"loc": "https://palantir.com/docs/apollo/apollo-cli/apollo-cli_environment_version_compare/", "family": "apollo"},
            {"loc": "https://palantir.com/docs/foundry/api/ontology-resources/actions/action-basics/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/gotham/api/target-workbench-v2-resources/target-boards/load-target-board/", "family": "gotham"},
            {"loc": "https://learn.palantir.com/page/course-catalog", "family": "learn"}
          ]
        }
        """,
        encoding="utf-8",
    )
    card_dir = dharma_home / "knowledge/wiki/research/palantir-pilot/source-cards"
    card_dir.mkdir(parents=True)
    (card_dir / "aip-overview.md").write_text(
        "# Palantir Source Card: AIP overview - Palantir\n\n"
        "Source URL: https://palantir.com/docs/foundry/aip/overview/\n"
        "Family: `aip`\n\n"
        "## Source Summary\n\n"
        "- Title: AIP overview - Palantir\n"
        "- Meta description: AIP overview\n"
        "- Short excerpt: AIP overview orients governed model workflows.\n\n"
        "## Extracted Headings\n\n"
        "- `h1` AIP overview\n\n"
        "## Practical Orientation\n\n"
        "This public docs page is a reviewed Palantir Pilot anchor for governed AIP "
        "orientation. The card stores only metadata, headings, one short excerpt, "
        "and original synthesis so tests can exercise the growth loop without "
        "mirroring Palantir page bodies or Learn course material.\n\n"
        "## Storage Boundary\n\n"
        "Stores title, meta description, headings, one short excerpt, and original "
        "orientation only. Does not store full page body, course body, videos, labs, "
        "quizzes, private tenant material, or gated Learn content.\n",
        encoding="utf-8",
    )

    receipt = build_learning_backlog(
        dharma_home=dharma_home,
        observed_at="2026-06-14T00:00:00Z",
        limit_per_topic=2,
        max_actions=4,
    )

    assert receipt["schema_version"] == "palantir_pilot.learning_backlog_receipt.v1"
    assert receipt["learning_state"] == "growth_ready"
    assert receipt["action_count"] > 0
    assert receipt["strict_pass"] is True
    assert Path(receipt["backlog_path"]).exists()
    assert Path(receipt["learning_loop_path"]).exists()
    assert Path(receipt["receipt_path"]).exists()
    candidate_urls = [
        url
        for action in receipt["actions"]
        for url in action["candidate_urls"]
    ]
    assert candidate_urls
    assert all("learn.palantir.com" not in url for url in candidate_urls)
    assert all(url.startswith("https://palantir.com/docs/") for url in candidate_urls)
    assert all(action["verifier_command"] for action in receipt["actions"])
    backlog_text = Path(receipt["backlog_path"]).read_text(encoding="utf-8")
    assert "quality report -> learning backlog" not in backlog_text
    assert "bounded public-source learning plan" in backlog_text
    loop_text = Path(receipt["learning_loop_path"]).read_text(encoding="utf-8")
    assert "quality report -> learning backlog" in loop_text
    assert "Learn remains manual-review/link-only" in loop_text

    packet = build_query_packet(
        "Palantir Pilot learning backlog bounded growth loop",
        dharma_home=dharma_home,
        limit=5,
    )

    assert any("learning-backlog.md" in item["path"] for item in packet["note_hits"])


def test_learning_backlog_passes_when_canonical_docs_are_exhausted(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 2,
          "urls": [
            {"loc": "https://palantir.com/docs/foundry/api/ontologies-v2-resources/linked-objects/list-linked-objects/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/foundry/api/v2/ontologies-v2-resources/linked-objects/list-linked-objects/", "family": "foundry"}
          ]
        }
        """,
        encoding="utf-8",
    )
    card_dir = dharma_home / "knowledge/wiki/research/palantir-pilot/source-cards"
    card_dir.mkdir(parents=True)
    (card_dir / "linked-objects.md").write_text(
        "# Palantir Source Card: Linked Objects\n\n"
        "Source URL: https://palantir.com/docs/foundry/api/ontologies-v2-resources/linked-objects/list-linked-objects/\n"
        "Family: `foundry`\n\n"
        "## Source Summary\n\n"
        "- Title: Linked Objects\n"
        "- Meta description: Public metadata\n"
        "- Short excerpt: Public excerpt for linked objects.\n\n"
        "## Extracted Headings\n\n"
        "- `h1` Linked Objects\n\n"
        "## Practical Orientation\n\n"
        "This public docs page is represented by one canonical source card even when "
        "the source index contains versioned API aliases for the same underlying "
        "public documentation route. The card stores only metadata, headings, one "
        "short excerpt, and original synthesis for bounded test coverage.\n\n"
        "## Storage Boundary\n\n"
        "Stores title, meta description, headings, one short excerpt, and original "
        "orientation only. Does not store full page body, course body, videos, labs, "
        "quizzes, private tenant material, or gated Learn content.\n",
        encoding="utf-8",
    )

    receipt = build_learning_backlog(
        dharma_home=dharma_home,
        observed_at="2026-06-14T00:00:00Z",
        limit_per_topic=2,
        max_actions=4,
    )

    assert receipt["learning_state"] == "canonical_docs_exhausted"
    assert receipt["action_count"] == 0
    assert receipt["strict_pass"] is True
    assert receipt["strict_checks"]["has_learning_actions"] is True
    assert (
        receipt["quality_snapshot"][
            "canonical_coverage_percent_canonical_allowed_card_candidates"
        ]
        == 100.0
    )
    backlog_text = Path(receipt["backlog_path"]).read_text(encoding="utf-8")
    assert "all canonical allowed public-doc source-card candidates are covered" in backlog_text


def test_source_card_topic_selection_skips_existing_and_indexes_all_cards(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 6,
          "urls": [
            {"loc": "https://palantir.com/docs/foundry/aip/overview/", "family": "aip"},
            {"loc": "https://palantir.com/docs/foundry/aip/aip-security/", "family": "aip"},
            {"loc": "https://palantir.com/docs/foundry/aip/aip-observability/", "family": "aip"},
            {"loc": "https://palantir.com/docs/apollo/apollo-cli-deprecated/apollo-cli_get-product-releases/", "family": "apollo"},
            {"loc": "https://palantir.com/docs/foundry/search/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/zh/foundry/aip/overview/", "family": "aip"}
          ]
        }
        """,
        encoding="utf-8",
    )
    card_dir = dharma_home / "knowledge/wiki/research/palantir-pilot/source-cards"
    card_dir.mkdir(parents=True)
    (card_dir / "docs-foundry-aip-overview.md").write_text(
        "# Existing\n\nSource URL: https://palantir.com/docs/foundry/aip/overview/\n",
        encoding="utf-8",
    )

    selected = source_cards.select_index_urls(
        dharma_home,
        topics=["aip"],
        limit=5,
    )

    assert "https://palantir.com/docs/foundry/aip/overview/" not in selected
    assert "https://palantir.com/docs/foundry/aip/aip-security/" in selected
    assert not any("deprecated" in item for item in selected)
    assert "https://palantir.com/docs/foundry/search/" not in selected
    assert "https://palantir.com/docs/zh/foundry/aip/overview/" not in selected

    receipt = {
        "observed_at": "2026-06-14T00:00:00Z",
        "cards": [
            {
                "url": "https://palantir.com/docs/foundry/aip/aip-security/",
                "family": "aip",
                "slug": "docs-foundry-aip-aip-security",
                "facts": {
                    "title": "AIP Security",
                    "meta_description": "Security description",
                    "headings": [],
                    "short_excerpt": "",
                },
                "storage_boundary": "No full page/course mirroring.",
            }
        ],
    }
    outputs = source_cards.write_outputs(dharma_home, receipt)
    index_text = Path(outputs["index_path"]).read_text(encoding="utf-8")

    assert outputs["index_card_count"] == 2
    assert "Latest batch card count: 1" in index_text
    assert "https://palantir.com/docs/foundry/aip/overview/" in index_text
    assert "https://palantir.com/docs/foundry/aip/aip-security/" in index_text


def test_source_card_topic_selection_skips_canonical_api_duplicates(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 3,
          "urls": [
            {"loc": "https://palantir.com/docs/foundry/api/ontologies-v2-resources/linked-objects/list-linked-objects/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/foundry/api/v2/ontologies-v2-resources/linked-objects/list-linked-objects/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/foundry/api/ontologies-v2-resources/ontology-objects/list-objects/", "family": "foundry"}
          ]
        }
        """,
        encoding="utf-8",
    )

    selected = source_cards.select_index_urls(
        dharma_home,
        families=["foundry"],
        terms=["linked-objects", "objects"],
        limit=5,
    )

    linked_object_urls = [
        url
        for url in selected
        if source_cards.canonical_source_url(url)
        == "palantir.com/docs/foundry/api/ontologies-v2-resources/linked-objects/list-linked-objects"
    ]
    assert len(linked_object_urls) == 1

    card_dir = dharma_home / "knowledge/wiki/research/palantir-pilot/source-cards"
    card_dir.mkdir(parents=True)
    (card_dir / "linked-objects.md").write_text(
        "# Existing\n\n"
        "Source URL: https://palantir.com/docs/foundry/api/ontologies-v2-resources/linked-objects/list-linked-objects/\n",
        encoding="utf-8",
    )

    selected_after_existing = source_cards.select_index_urls(
        dharma_home,
        families=["foundry"],
        terms=["linked-objects", "objects"],
        limit=5,
    )

    assert not any("linked-objects/list-linked-objects" in url for url in selected_after_existing)


def test_source_card_quality_report_flags_duplicates_and_review_queue(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 5,
          "urls": [
            {"loc": "https://palantir.com/docs/foundry/api/ontologies-v2-resources/linked-objects/list-linked-objects/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/foundry/api/v2/ontologies-v2-resources/linked-objects/list-linked-objects/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/apollo/apollo-cli-deprecated/apollo-cli_get-product-releases/", "family": "apollo"},
            {"loc": "https://palantir.com/docs/foundry/aip/aip-security/", "family": "aip"},
            {"loc": "https://palantir.com/docs/foundry/aip/aip-observability/", "family": "aip"}
          ]
        }
        """,
        encoding="utf-8",
    )
    card_dir = dharma_home / "knowledge/wiki/research/palantir-pilot/source-cards"
    card_dir.mkdir(parents=True)
    (card_dir / "linked-objects.md").write_text(
        "# Palantir Source Card: Linked Objects\n\n"
        "Source URL: https://palantir.com/docs/foundry/api/ontologies-v2-resources/linked-objects/list-linked-objects/\n"
        "Family: `foundry`\n\n"
        "## Source Summary\n\n"
        "- Title: Linked Objects\n"
        "- Meta description: Public metadata\n"
        "- Short excerpt: Public excerpt for linked objects.\n\n"
        "## Extracted Headings\n\n- `h1` Linked Objects\n",
        encoding="utf-8",
    )
    (card_dir / "linked-objects-v2.md").write_text(
        "# Palantir Source Card: Linked Objects v2\n\n"
        "Source URL: https://palantir.com/docs/foundry/api/v2/ontologies-v2-resources/linked-objects/list-linked-objects/\n"
        "Family: `foundry`\n\n"
        "## Source Summary\n\n"
        "- Title: Linked Objects v2\n"
        "- Meta description: Public metadata\n"
        "- Short excerpt: Public excerpt for linked objects v2.\n\n"
        "## Extracted Headings\n\n- `h1` Linked Objects\n",
        encoding="utf-8",
    )
    (card_dir / "deprecated.md").write_text(
        "# Palantir Source Card: Deprecated\n\n"
        "Source URL: https://palantir.com/docs/apollo/apollo-cli-deprecated/apollo-cli_get-product-releases/\n"
        "Family: `apollo`\n\n"
        "## Source Summary\n\n"
        "- Title: Deprecated\n"
        "- Meta description: not extracted\n"
        "- Short excerpt: not extracted\n\n"
        "## Extracted Headings\n\n- No headings extracted from the fetched public page.\n",
        encoding="utf-8",
    )

    report = build_quality_report(
        dharma_home=dharma_home,
        observed_at="2026-06-14T00:00:00Z",
        limit_per_topic=2,
    )
    outputs = write_quality_outputs(dharma_home, report)

    assert report["source_card_count"] == 3
    assert report["canonical_source_card_count"] == 2
    assert report["canonical_allowed_source_card_candidate_count"] == 3
    assert report["canonical_coverage_percent_canonical_allowed_card_candidates"] == 66.67
    assert report["duplicate_excess_card_count"] == 1
    assert report["duplicate_group_count"] == 1
    assert report["flag_counts"]["canonical_duplicate_group"] == 2
    assert report["flag_counts"]["deprecated_path"] == 1
    assert report["flag_counts"]["now_disallowed_by_selector_policy"] == 1
    assert "https://palantir.com/docs/foundry/aip/aip-security/" in report["review_queue"]["aip"]
    assert Path(outputs["report_path"]).exists()
    report_text = Path(outputs["report_path"]).read_text(encoding="utf-8")
    assert "Coverage of allowed source-card candidates" in report_text
    assert "Canonical coverage of allowed source-card candidates" in report_text
    assert "Canonical coverage of canonical allowed source-card candidates" in report_text
    assert "deprecated_path" in report_text


def test_source_card_quality_title_flag_ignores_other_not_extracted_fields(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 1,
          "urls": [
            {"loc": "https://palantir.com/docs/apollo/apollo-cli/apollo-cli_product-release/", "family": "apollo"}
          ]
        }
        """,
        encoding="utf-8",
    )
    card_dir = dharma_home / "knowledge/wiki/research/palantir-pilot/source-cards"
    card_dir.mkdir(parents=True)
    (card_dir / "apollo-release.md").write_text(
        "# Palantir Source Card: Apollo CLI - apollo-cli product-release - Palantir\n\n"
        "Source URL: https://palantir.com/docs/apollo/apollo-cli/apollo-cli_product-release/\n"
        "Family: `apollo`\n\n"
        "## Source Summary\n\n"
        "- Title: Apollo CLI - apollo-cli product-release - Palantir\n"
        "- Meta description: Manage Apollo product releases\n"
        "- Short excerpt: not extracted\n\n"
        "## Extracted Headings\n\n- `h1` apollo-cli product-release\n",
        encoding="utf-8",
    )

    report = build_quality_report(
        dharma_home=dharma_home,
        observed_at="2026-06-14T00:00:00Z",
        limit_per_topic=1,
    )

    flags = report["flagged_cards"][0]["flags"]
    assert "missing_title" not in flags
    assert "missing_short_excerpt" in flags


def test_source_card_cleanup_archives_deprecated_and_duplicate_excess(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 4,
          "urls": [
            {"loc": "https://palantir.com/docs/foundry/api/ontologies-v2-resources/linked-objects/list-linked-objects/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/foundry/api/v2/ontologies-v2-resources/linked-objects/list-linked-objects/", "family": "foundry"},
            {"loc": "https://palantir.com/docs/apollo/apollo-cli-deprecated/apollo-cli_get-product-releases/", "family": "apollo"},
            {"loc": "https://palantir.com/docs/foundry/aip/aip-security/", "family": "aip"}
          ]
        }
        """,
        encoding="utf-8",
    )
    card_dir = dharma_home / "knowledge/wiki/research/palantir-pilot/source-cards"
    card_dir.mkdir(parents=True)
    base_card = card_dir / "linked-objects.md"
    base_card.write_text(
        "# Palantir Source Card: Linked Objects\n\n"
        "Source URL: https://palantir.com/docs/foundry/api/ontologies-v2-resources/linked-objects/list-linked-objects/\n"
        "Family: `foundry`\n\n"
        "## Source Summary\n\n"
        "- Title: Linked Objects\n"
        "- Meta description: Public metadata\n"
        "- Short excerpt: Public excerpt for linked objects.\n\n"
        "## Extracted Headings\n\n- `h1` Linked Objects\n",
        encoding="utf-8",
    )
    duplicate_card = card_dir / "linked-objects-v2.md"
    duplicate_card.write_text(
        "# Palantir Source Card: Linked Objects v2\n\n"
        "Source URL: https://palantir.com/docs/foundry/api/v2/ontologies-v2-resources/linked-objects/list-linked-objects/\n"
        "Family: `foundry`\n\n"
        "## Source Summary\n\n"
        "- Title: Linked Objects v2\n"
        "- Meta description: Public metadata\n"
        "- Short excerpt: Public excerpt for linked objects v2.\n\n"
        "## Extracted Headings\n\n- `h1` Linked Objects\n",
        encoding="utf-8",
    )
    deprecated_card = card_dir / "deprecated.md"
    deprecated_card.write_text(
        "# Palantir Source Card: Deprecated\n\n"
        "Source URL: https://palantir.com/docs/apollo/apollo-cli-deprecated/apollo-cli_get-product-releases/\n"
        "Family: `apollo`\n\n"
        "## Source Summary\n\n"
        "- Title: Deprecated\n"
        "- Meta description: Public metadata\n"
        "- Short excerpt: Public excerpt for deprecated card.\n\n"
        "## Extracted Headings\n\n- `h1` Deprecated\n",
        encoding="utf-8",
    )

    receipt = cleanup_source_cards(
        dharma_home=dharma_home,
        observed_at="2026-06-14T00:00:00Z",
        stamp="20260614T000001Z",
    )

    assert receipt["planned_archive_count"] == 2
    assert receipt["active_card_count_after"] == 1
    assert base_card.exists()
    assert not duplicate_card.exists()
    assert not deprecated_card.exists()
    assert all(Path(row["archive_path"]).exists() for row in receipt["archived_cards"])
    index_text = (dharma_home / "knowledge/wiki/research/palantir-pilot/source-card-index.md").read_text(
        encoding="utf-8"
    )
    assert "Card count: 1" in index_text
    assert "linked-objects-v2" not in index_text
    assert "apollo-cli-deprecated" not in index_text

    report_after = build_quality_report(
        dharma_home=dharma_home,
        observed_at="2026-06-14T00:00:01Z",
        limit_per_topic=1,
    )
    assert report_after["duplicate_group_count"] == 0
    assert "deprecated_path" not in report_after["flag_counts"]


def test_source_card_cleanup_archives_no_signal_cards(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 1,
          "urls": [
            {"loc": "https://palantir.com/docs/defense-osdk/", "family": "defense_osdk"}
          ]
        }
        """,
        encoding="utf-8",
    )
    card_dir = dharma_home / "knowledge/wiki/research/palantir-pilot/source-cards"
    card_dir.mkdir(parents=True)
    no_signal = card_dir / "docs-defense-osdk.md"
    no_signal.write_text(
        "# Palantir Source Card: https://palantir.com/docs/defense-osdk/\n\n"
        "Source URL: https://palantir.com/docs/defense-osdk/\n"
        "Family: `defense_osdk`\n\n"
        "## Source Summary\n\n"
        "- Title: not extracted\n"
        "- Meta description: not extracted\n"
        "- Short excerpt: not extracted\n\n"
        "## Extracted Headings\n\n- No headings extracted from the fetched public page.\n",
        encoding="utf-8",
    )

    receipt = cleanup_source_cards(
        dharma_home=dharma_home,
        observed_at="2026-06-14T00:00:00Z",
        stamp="20260614T000002Z",
    )

    assert receipt["planned_archive_count"] == 1
    assert receipt["active_card_count_after"] == 0
    assert receipt["archived_cards"][0]["reasons"] == ["irreparable_no_signal_card"]
    assert not no_signal.exists()


def test_memory_plane_indexes_workspace_and_logs_query(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 2,
          "urls": [
            {
              "loc": "https://palantir.com/docs/foundry/architecture-center/ontology-system/",
              "family": "foundry",
              "lastmod": "2026-06-11T15:53:36.107Z",
              "sitemap": "https://www.palantir.com/docs/sitemap.xml"
            },
            {
              "loc": "https://palantir.com/docs/foundry/api/ontologies-v2-resources/ontology-objects/ontology-object-basics/",
              "family": "foundry",
              "lastmod": "2026-06-11T15:53:36.117Z",
              "sitemap": "https://www.palantir.com/docs/sitemap.xml"
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    wiki_dir = dharma_home / "knowledge/wiki/research/palantir-pilot"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "ontology-map.md").write_text(
        "# Ontology Map\n\nOntology maps object and action concepts.\n",
        encoding="utf-8",
    )
    archive_dir = wiki_dir / "source-cards-archive/20260614T000000Z"
    archive_dir.mkdir(parents=True)
    (archive_dir / "deprecated-card.md").write_text(
        "# Deprecated Archived Card\n\nDeprecated archived evidence should not be active query context.\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "memory_plane.db"

    index_receipt = index_workspace_to_memory_plane(
        dharma_home=dharma_home,
        db_path=db_path,
        source_url_batch_size=1,
    )
    packet = build_query_packet("ontology", dharma_home=dharma_home, limit=3)
    query_receipt = record_query_packet_to_memory_plane(
        packet,
        dharma_home=dharma_home,
        db_path=db_path,
        task_id="palantir-query-test",
    )

    assert index_receipt["wiki_documents_indexed"] == 1
    assert index_receipt["source_catalog_documents_indexed"] == 1
    assert index_receipt["source_urls_indexed"] == 2
    assert index_receipt["pruned_wiki_documents"] == 0
    assert query_receipt["logged_hit_count"] >= 2
    archived_packet = build_query_packet("deprecated archived evidence", dharma_home=dharma_home, limit=5)
    assert not any("source-cards-archive" in item["path"] for item in archived_packet["note_hits"])
    with sqlite3.connect(db_path) as db:
        source_kinds = {
            row[0]
            for row in db.execute("SELECT DISTINCT source_kind FROM source_documents")
        }
        logged = db.execute(
            "SELECT COUNT(*) FROM retrieval_log WHERE consumer = 'palantir_pilot.query'"
        ).fetchone()[0]

    assert source_kinds == {"palantir_pilot_source_catalog", "palantir_pilot_wiki"}
    assert logged == query_receipt["logged_hit_count"]


def test_answer_packet_cites_sources_and_notes(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        """
        {
          "url_count": 2,
          "urls": [
            {
              "loc": "https://palantir.com/docs/foundry/architecture-center/ontology-system/",
              "family": "foundry",
              "lastmod": "2026-06-11T15:53:36.107Z",
              "sitemap": "https://www.palantir.com/docs/sitemap.xml"
            },
            {
              "loc": "https://palantir.com/docs/foundry/api/ontologies-v2-resources/ontology-objects/ontology-object-basics/",
              "family": "foundry",
              "lastmod": "2026-06-11T15:53:36.117Z",
              "sitemap": "https://www.palantir.com/docs/sitemap.xml"
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    wiki_dir = dharma_home / "knowledge/wiki/research/palantir-pilot"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "ontology-map.md").write_text(
        "# Ontology Map\n\nOntology maps objects, links, actions, and governance.\n",
        encoding="utf-8",
    )
    (wiki_dir / "checkpoint-20260614T000000Z.md").write_text(
        "# Checkpoint\n\n## Live Answer Command\n\nontology ontology action governance\n"
        "```bash\npython3 scripts/research/palantir_pilot_query.py ontology --answer\n```\n",
        encoding="utf-8",
    )

    packet = build_answer_packet("ontology action governance", dharma_home=dharma_home)

    assert packet["schema_version"] == "palantir_pilot.answer_packet.v1"
    assert packet["agent"]["callsign"] == CALLSIGN
    assert packet["confidence"] == "medium_public_source_grounded"
    assert "public-source synthesis" in packet["answer"]
    assert packet["source_citations"][0]["url"].startswith("https://palantir.com/docs/")
    assert packet["note_citations"][0]["path"].endswith("ontology-map.md")
    assert all("checkpoint-" not in item["path"] for item in packet["note_citations"])
    assert "Live Answer Command" not in packet["answer"]
    assert "No official Palantir affiliation" in packet["limitations"][0]


def test_answer_packet_preserves_learn_boundary(tmp_path):
    dharma_home = tmp_path / ".dharma"
    raw_dir = dharma_home / "knowledge/wiki/raw/palantir-pilot"
    raw_dir.mkdir(parents=True)
    (raw_dir / "source-index-20260614T000000Z.json").write_text(
        '{"url_count": 1, "urls": [{"loc": "https://palantir.com/docs/foundry/getting-started/overview/", "family": "foundry"}]}',
        encoding="utf-8",
    )

    packet = build_answer_packet("learn course catalog training", dharma_home=dharma_home)

    assert any("learn.palantir.com/page/course-catalog" in item for item in packet["limitations"])
    assert packet["source_boundary"].startswith("Public-source workspace synthesis")
    # Integrity: once deep-ingest stores page prose, the boundary must NOT keep
    # claiming "no full page/course body storage" — it must own the deep-card
    # corpus (public prose) while still excluding Learn/course bodies.
    assert "no full page/course body storage" not in packet["source_boundary"]
    assert "deep-card prose" in packet["source_boundary"]
    assert "Learn/course body" in packet["source_boundary"]
