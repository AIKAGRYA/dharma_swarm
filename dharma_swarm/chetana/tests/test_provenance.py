"""Tests for chetana.provenance — schema, signing, frontmatter parsing."""

from __future__ import annotations

import re
from datetime import date

import pytest

from dharma_swarm.chetana.provenance import (
    AtomProvenance,
    AtomSource,
    FrontmatterSchema,
    GateCheckRecord,
    assemble_atom,
    compute_axiom_signature,
    default_stale_after,
    new_atom_id,
    now_iso,
    parse_frontmatter,
    render_frontmatter_yaml,
    validate_frontmatter,
)


def _minimal_schema(**overrides) -> FrontmatterSchema:
    base = {
        "title": "Test atom",
        "atom_id": new_atom_id(),
        "type": "atomic",
        "confidence": 0.7,
        "source": [
            AtomSource(
                kind="note",
                path="/tmp/test.md",
                captured=date.today().isoformat(),
                captured_by="test",
            )
        ],
        "stale_after": default_stale_after(),
    }
    base.update(overrides)
    return FrontmatterSchema(**base)


def test_atom_id_is_uuid4():
    a = new_atom_id()
    assert re.fullmatch(r"[0-9a-f-]{36}", a)


def test_default_stale_after_is_iso_date_90_days_out():
    today = date(2026, 1, 1)
    assert default_stale_after(today=today, days=90) == "2026-04-01"


def test_compute_axiom_signature_is_deterministic():
    s1 = compute_axiom_signature("body", "kernelsig")
    s2 = compute_axiom_signature("body", "kernelsig")
    assert s1 == s2 and len(s1) == 64


def test_compute_axiom_signature_changes_with_kernel():
    s1 = compute_axiom_signature("body", "k1")
    s2 = compute_axiom_signature("body", "k2")
    assert s1 != s2


def test_validate_frontmatter_round_trip():
    schema = _minimal_schema()
    yaml_block = render_frontmatter_yaml(schema)
    full = yaml_block + "\nbody text"
    parsed, body = parse_frontmatter(full)
    assert parsed is not None
    assert parsed.title == schema.title
    assert parsed.atom_id == schema.atom_id
    assert "body text" in body


def test_parse_frontmatter_returns_none_when_no_frontmatter():
    text = "just a markdown body, no frontmatter here\n"
    parsed, body = parse_frontmatter(text)
    assert parsed is None and body == text


def test_invalid_confidence_rejected():
    with pytest.raises(Exception):
        FrontmatterSchema(
            title="x",
            atom_id=new_atom_id(),
            type="atomic",
            confidence=1.5,
            source=[
                AtomSource(
                    kind="note",
                    path="/x",
                    captured=date.today().isoformat(),
                    captured_by="t",
                )
            ],
            stale_after=default_stale_after(),
        )


def test_axiom_signature_format_validation_in_provenance():
    bad = {
        "promoted_by": "test",
        "promoted_at": now_iso(),
        "gate_check": GateCheckRecord(
            result="ALLOW", checked_at=now_iso()
        ).model_dump(),
        "axiom_signature": "not-a-sha256",
        "review_status": "staged",
    }
    with pytest.raises(Exception):
        AtomProvenance.model_validate(bad)


def test_assemble_atom_produces_parseable_text():
    schema = _minimal_schema()
    text = assemble_atom(schema, "## body\n\nsome content")
    parsed, body = parse_frontmatter(text)
    assert parsed is not None
    assert "some content" in body


def test_validate_frontmatter_dict_path():
    schema = _minimal_schema()
    fm_dict = schema.model_dump(mode="json", exclude_none=True)
    re_validated = validate_frontmatter(fm_dict)
    assert re_validated.title == schema.title


def test_validate_frontmatter_accepts_single_dict_source():
    validated = validate_frontmatter(
        {
            "title": "Bridge hypothesis atom",
            "atom_id": new_atom_id(),
            "type": "atomic",
            "confidence": 0.8,
            "source": {
                "kind": "external",
                "path": "bridge-hypothesis-extended.md",
                "captured": "2026-05-06",
                "captured_by": "test",
            },
            "stale_after": default_stale_after(),
        }
    )

    assert validated.source[0].kind == "external"
    assert validated.source[0].path == "bridge-hypothesis-extended.md"


def test_parse_frontmatter_strict_accepts_source_path_dict():
    text = f"""---
title: Source path dict
atom_id: {new_atom_id()}
type: atomic
confidence: 0.8
source:
  source: local
  path: bridge-hypothesis-extended.md
stale_after: {default_stale_after()}
---
body
"""

    parsed, body = parse_frontmatter(text)

    assert parsed is not None
    assert parsed.source[0].kind == "external"
    assert parsed.source[0].path == "bridge-hypothesis-extended.md"
    assert parsed.source[0].span == "local"
    assert body == "body\n"


def test_parse_frontmatter_lenient_flattens_category_source_map():
    text = """---
title: Category source atom
source:
  canonical:
    - foundations/EMPIRICAL_CLAIMS_REGISTRY.md
  contemplative: foundations/PILLAR_09_DADA_BHAGWAN.md
---
body
"""

    parsed, _body = parse_frontmatter(
        text, lenient=True, source_path="/tmp/bridge-hypothesis-extended.md"
    )

    assert parsed is not None
    assert [(source.path, source.span) for source in parsed.source] == [
        ("foundations/EMPIRICAL_CLAIMS_REGISTRY.md", "canonical"),
        ("foundations/PILLAR_09_DADA_BHAGWAN.md", "contemplative"),
    ]
