"""Secret scan at the chetana promote → write_trusted boundary (audit WS-I)."""

from __future__ import annotations

from pathlib import Path

import pytest

import dharma_swarm.redaction as redaction_mod
from dharma_swarm.chetana.ingest import ingest
from dharma_swarm.chetana.promote import promote
from dharma_swarm.chetana.provenance import parse_frontmatter

SK_TOKEN = "sk-" + "a1b2c3d4e5f6g7h8j9k0"


@pytest.fixture(autouse=True)
def _no_vector_ingest(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DHARMA_WIKI_VECTOR_AUTO_INGEST", "0")


def test_promote_redacts_secret_body_before_write_trusted(chetana_sandbox: Path):
    ingested = ingest(
        source=f"Deployment note mentioning credential {SK_TOKEN} for rotation.",
        source_kind="note",
        title="Secret Body Promotion",
        confidence=0.8,
    )
    result = promote(staged_path=ingested.atoms[0], promoted_by="tester")

    assert result.decision in {"ALLOW", "WARN"}
    assert result.trusted_path is not None and result.trusted_path.exists()
    raw_text = result.trusted_path.read_text(encoding="utf-8")
    assert SK_TOKEN not in raw_text
    assert "<REDACTED_" in raw_text
    schema, _body = parse_frontmatter(raw_text)
    assert schema is not None
    assert "pii_risk:high" in schema.tags
    assert any("redaction:" in note for note in result.notes)


def test_promote_scan_error_quarantines_without_trusted_write(
    chetana_sandbox: Path, monkeypatch: pytest.MonkeyPatch
):
    ingested = ingest(
        source=f"Body with {SK_TOKEN} that must never reach trusted on scan error.",
        source_kind="note",
        title="Scan Error Promotion",
        confidence=0.8,
    )
    staged = ingested.atoms[0]

    def boom(text: str) -> None:
        raise RuntimeError("scanner exploded")

    monkeypatch.setattr(redaction_mod, "redact_text", boom)
    result = promote(staged_path=staged, promoted_by="tester")

    assert result.decision == "BLOCK"
    assert result.review_status == "rejected"
    assert result.trusted_path is None
    assert not staged.exists()

    trusted_root = chetana_sandbox / "wiki" / "concepts"
    assert not any(trusted_root.rglob("*.md"))
    quarantined = list((chetana_sandbox / "quarantine").rglob("*.md"))
    assert len(quarantined) == 1
