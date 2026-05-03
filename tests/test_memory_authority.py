"""Tests for the memory authority review layer."""

from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.memory_authority import (
    load_manifest,
    review_authority,
    render_review,
)


def _surface(
    name: str,
    *,
    role: str,
    substrate: str = "directory",
    risk: str = "low",
    verification_status: str = "probable",
) -> dict:
    return {
        "surface_id": f"id-{name}",
        "name": name,
        "paths": [f"/tmp/{name}"],
        "substrate": substrate,
        "role": role,
        "authority_level": "unknown",
        "owner_module": None,
        "runtime_owner": None,
        "size_bytes": 0,
        "verification_status": verification_status,
        "risk": risk,
        "evidence": [],
        "notes": [],
    }


def _entry(
    authority_id: str,
    name: str,
    *,
    authority_role: str,
    expected_surface_role: str,
    owner: str = "owner",
    substrate: str | None = None,
    session_start_context: str = "deny",
    truth_authority: bool = False,
    status: str = "active",
    allowed_writers: list[str] | None = None,
) -> dict:
    match: dict[str, list[str]] = {"names": [name]}
    if substrate:
        match["substrates"] = [substrate]
    return {
        "authority_id": authority_id,
        "surface_ids": [],
        "match": match,
        "owner": owner,
        "authority_role": authority_role,
        "expected_surface_role": expected_surface_role,
        "authority_level": "system",
        "allowed_writers": list(allowed_writers or []),
        "allowed_readers": [],
        "retention_class": "test",
        "promotion_path": "test",
        "session_start_context": session_start_context,
        "truth_authority": truth_authority,
        "status": status,
    }


def _manifest(*entries: dict) -> dict:
    return {"version": 1, "surfaces": list(entries)}


def test_lancedb_without_manifest_fails_needs_owner() -> None:
    surfaces = [
        _surface(
            "lancedb",
            role="projection_index",
            substrate="lancedb",
            risk="critical",
            verification_status="needs_owner",
        )
    ]
    review = review_authority(surfaces, _manifest())
    assert review.failed
    assert review.needs_owner[0].surface_name == "lancedb"
    assert "critical needs-owner" in review.needs_owner[0].message


def test_lancedb_owned_projection_passes() -> None:
    surfaces = [
        _surface(
            "lancedb",
            role="projection_index",
            substrate="lancedb",
            risk="critical",
            verification_status="needs_owner",
        )
    ]
    review = review_authority(
        surfaces,
        _manifest(
            _entry(
                "lancedb",
                "lancedb",
                authority_role="projection_index",
                expected_surface_role="projection_index",
                owner="dharma_swarm.memory_palace",
                substrate="lancedb",
            )
        ),
    )
    assert not review.failed
    assert review.approved[0].surface_name == "lancedb"


def test_conversation_log_marked_trusted_memory_fails() -> None:
    surfaces = [_surface("conversation_log", role="write_authority")]
    review = review_authority(
        surfaces,
        _manifest(
            _entry(
                "conversation_log",
                "conversation_log",
                authority_role="trusted_memory",
                expected_surface_role="write_authority",
                session_start_context="allow",
                truth_authority=True,
            )
        ),
    )
    assert review.failed
    assert review.misclassified[0].authority_id == "conversation_log"


def test_cabinet_with_autonomous_writer_fails() -> None:
    surfaces = [_surface("cabinet", role="human_curated")]
    review = review_authority(
        surfaces,
        _manifest(
            _entry(
                "cabinet",
                "cabinet",
                authority_role="human_curated_high_trust",
                expected_surface_role="human_curated",
                session_start_context="allow",
                truth_authority=True,
                allowed_writers=["some.autonomous.writer"],
            )
        ),
    )
    assert review.failed
    assert review.dangerous_context_source[0].surface_name == "cabinet"


def test_smriti_as_canonical_truth_fails() -> None:
    surfaces = [_surface("smriti.db", role="write_authority", substrate="sqlite")]
    review = review_authority(
        surfaces,
        _manifest(
            _entry(
                "smriti",
                "smriti.db",
                authority_role="operator_session_memory",
                expected_surface_role="write_authority",
                substrate="sqlite",
                session_start_context="allow_operator_only",
                truth_authority=True,
            )
        ),
    )
    assert review.failed
    assert review.dangerous_context_source[0].authority_id == "smriti"


def test_dormant_promise_marked_active_warns() -> None:
    surfaces = [_surface("mem0-integration", role="dormant_promise")]
    review = review_authority(
        surfaces,
        _manifest(
            _entry(
                "mem0_integration",
                "mem0-integration",
                authority_role="planned_future",
                expected_surface_role="dormant_promise",
                status="active",
            )
        ),
    )
    assert not review.failed
    assert review.warnings[0].surface_name == "mem0-integration"


def test_default_manifest_covers_the_five_hot_decisions() -> None:
    manifest_path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "governance"
        / "memory_authority_manifest.json"
    )
    manifest = load_manifest(manifest_path)
    authority_ids = {entry["authority_id"] for entry in manifest["surfaces"]}
    assert {
        "lancedb",
        "conversation_log",
        "smriti",
        "cabinet",
        "mem0_integration",
        "agentic_rag",
        "a2a_protocol",
    }.issubset(authority_ids)


def test_review_renders_one_page_report() -> None:
    surfaces = [_surface("cabinet", role="human_curated")]
    review = review_authority(
        surfaces,
        _manifest(
            _entry(
                "cabinet",
                "cabinet",
                authority_role="human_curated_high_trust",
                expected_surface_role="human_curated",
                session_start_context="allow",
                truth_authority=True,
            )
        ),
    )
    text = render_review(review)
    assert "# Memory Authority Review" in text
    assert "Verdict: PASS" in text


def test_cli_review_accepts_census_json(tmp_path: Path, capsys) -> None:
    from dharma_swarm.memory_authority import main

    census = tmp_path / "census.json"
    manifest = tmp_path / "manifest.json"
    census.write_text(
        json.dumps({"surfaces": [_surface("cabinet", role="human_curated")]}),
        encoding="utf-8",
    )
    manifest.write_text(
        json.dumps(
            _manifest(
                _entry(
                    "cabinet",
                    "cabinet",
                    authority_role="human_curated_high_trust",
                    expected_surface_role="human_curated",
                    session_start_context="allow",
                    truth_authority=True,
                )
            )
        ),
        encoding="utf-8",
    )
    rc = main(["review", "--census", str(census), "--manifest", str(manifest)])
    assert rc == 0
    assert "Verdict: PASS" in capsys.readouterr().out
