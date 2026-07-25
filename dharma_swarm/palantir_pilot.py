"""Palantir Pilot public-source specialist projection.

This module is the public API facade for the Palantir Pilot specialist.
Implementation is split across three sub-modules to satisfy the 1000-line budget:

- ``palantir_pilot_manifest``: agent constants, ``build_source_manifest``, and
  ``build_external_worker_registration``.
- ``palantir_pilot_index``: source-index loading, memory-plane indexing, and
  ``query_source_index`` / ``query_wiki_notes``.
- ``palantir_pilot_answers``: ``build_query_packet``, ``build_answer_packet``, and
  ``record_query_packet_to_memory_plane``.

All names that were public in this module remain importable from here for
backward compatibility.
"""
# ruff: noqa: F401  -- public API facade: imported names ARE the public surface

from __future__ import annotations

from dharma_swarm.palantir_pilot_manifest import (
    AGENT_ID,
    CALLSIGN,
    CONTEXT_ENGINEERING_FILE,
    DATABASE_SOURCE_KINDS,
    DEFAULT_DHARMA_HOME,
    DISPLAY_NAME,
    DOC_FAMILY_PREFIXES,
    FORBIDDEN_ACTIONS,
    MEMORY_PLANE_DB,
    NATS_SUBJECT,
    OWNED_SURFACES,
    PUBLIC_SOURCES,
    QUERY_CONSUMER,
    RAW_SOURCE_DIR,
    REPO_AGENT_HOME,
    REPO_ROOT,
    SCHEMA_VERSION,
    SEED_FILE,
    SOUL_FILE,
    VERIFIER_COMMANDS,
    WIKI_HOME,
    WIKI_SOURCE_DIR,
    _count_markdown_files,
    _path_exists,
    _source_family,
    _utc_now,
    build_external_worker_registration,
    build_source_manifest,
    format_markdown,
    summarize_source_families,
    write_manifest_json,
    write_wiki_home,
)
from dharma_swarm.palantir_pilot_index import (
    _catalog_documents_from_source_index,
    _load_latest_source_index,
    _prune_stale_palantir_wiki_documents,
    _query_observed_at,
    _query_terms,
    _score_text,
    _score_wiki_note,
    _snippet,
    _stable_id,
    _wiki_markdown_paths,
    index_workspace_to_memory_plane,
    latest_source_index_path,
    memory_plane_db_path,
    query_source_index,
    query_wiki_notes,
)
from dharma_swarm.palantir_pilot_answers import (
    _answer_confidence,
    _answer_focus_terms,
    _extract_note_answer_claim,
    _first_sentence,
    _is_answer_synthesis_note,
    _strip_markdown_noise,
    _top_families,
    build_answer_packet,
    build_answer_packet_from_query_packet,
    build_query_packet,
    record_query_packet_to_memory_plane,
)

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
