"""Cross-language contract test (Generator 4 — the languages-verify-each-other seam).

Asserts that the Python ``ChangeSummary`` frozen dataclass conforms to the single
source of truth at ``specs/contracts/change_summary.schema.json``. The schema is the
shared contract both the Python dataclass and the Lean ``SafePrimitives.lean``
structure reference; this test pins the Python side of that conformance so drift in
either direction (a field added/removed/retyped in the dataclass, or a key changed in
the schema) fails CI loudly.

ADVISORY ONLY. Pure assertions over field metadata + a JSON document; no I/O beyond
reading the committed schema file, no live-path wiring.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from dharma_swarm.telosproof.change_summary import (
    ChangeSummary,
    extract_change_summary,
)

# Repo-rooted path to the cross-language contract. This test file lives at
# <repo>/tests/, so the schema is one directory up under specs/contracts/.
_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "specs"
    / "contracts"
    / "change_summary.schema.json"
)

# JSON-Schema "type" string expected for each Python field annotation. The
# dataclass uses tuple[str, ...] for the three path inventories (serialised as a
# JSON array) and bool for every flag (serialised as a JSON boolean).
_TUPLE_FIELDS = {"touched_paths", "added_paths", "deleted_paths"}


def _load_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _dataclass_field_names() -> set[str]:
    return {f.name for f in dataclasses.fields(ChangeSummary)}


def test_schema_file_exists_and_parses():
    """The contract document is present at its canonical path and is valid JSON."""
    assert _SCHEMA_PATH.exists(), f"missing contract schema at {_SCHEMA_PATH}"
    schema = _load_schema()
    assert schema.get("title") == "ChangeSummary"
    assert schema.get("type") == "object"
    # Deny-by-default on structure too: no field may sneak in unannounced.
    assert schema.get("additionalProperties") is False


def test_dataclass_fields_match_schema_required():
    """Every dataclass field is a `required` schema key and vice-versa (exact set)."""
    schema = _load_schema()
    schema_required = set(schema["required"])
    dataclass_fields = _dataclass_field_names()

    missing_in_schema = dataclass_fields - schema_required
    extra_in_schema = schema_required - dataclass_fields
    assert not missing_in_schema, (
        f"dataclass fields absent from schema `required`: {sorted(missing_in_schema)}"
    )
    assert not extra_in_schema, (
        f"schema `required` keys with no dataclass field: {sorted(extra_in_schema)}"
    )


def test_dataclass_fields_match_schema_properties():
    """`properties` keys are exactly the dataclass field set (no drift either way)."""
    schema = _load_schema()
    schema_properties = set(schema["properties"])
    dataclass_fields = _dataclass_field_names()
    assert schema_properties == dataclass_fields, (
        "schema.properties keys diverge from dataclass fields: "
        f"only-in-schema={sorted(schema_properties - dataclass_fields)} "
        f"only-in-dataclass={sorted(dataclass_fields - schema_properties)}"
    )


def test_field_json_types_match_python_annotations():
    """tuple[str, ...] fields are JSON arrays; bool fields are JSON booleans."""
    schema = _load_schema()
    props = schema["properties"]
    for field in dataclasses.fields(ChangeSummary):
        prop = props[field.name]
        if field.name in _TUPLE_FIELDS:
            assert prop["type"] == "array", f"{field.name} should be a JSON array"
            assert prop["items"]["type"] == "string", (
                f"{field.name} array items should be strings"
            )
        else:
            assert prop["type"] == "boolean", (
                f"{field.name} should be a JSON boolean (Python bool)"
            )


def _summary_to_dict(summary: ChangeSummary) -> dict:
    """Serialise a ChangeSummary to a JSON-compatible dict (tuples -> lists)."""
    raw = dataclasses.asdict(summary)
    return {
        k: (list(v) if isinstance(v, tuple) else v) for k, v in raw.items()
    }


def test_real_extract_round_trips_under_schema():
    """A real extract_change_summary(...) output validates against the schema.

    Validation is skipped cleanly if jsonschema is unavailable; the structural
    field-parity tests above are the load-bearing assertions and run unconditionally.
    """
    diff = (
        "diff --git a/dharma_swarm/util/helpers.py b/dharma_swarm/util/helpers.py\n"
        "--- a/dharma_swarm/util/helpers.py\n"
        "+++ b/dharma_swarm/util/helpers.py\n"
        "@@ -1,2 +1,4 @@\n"
        " def existing():\n"
        "     return 1\n"
        "+def added_pure():\n"
        "+    return 2\n"
    )
    summary = extract_change_summary(diff)
    payload = _summary_to_dict(summary)

    # The payload must carry exactly the required keys (mirror of the dataclass).
    schema = _load_schema()
    assert set(payload) == set(schema["required"])

    try:
        import jsonschema
    except ImportError:  # pragma: no cover - advisory degrade-clean
        return
    # Raises jsonschema.ValidationError on any drift; additionalProperties:false
    # makes an unexpected serialised key a hard failure.
    jsonschema.validate(instance=payload, schema=schema)


def test_safe_primitive_enum_present_and_closed():
    """The cross-language SafePrimitive enum is defined and is the expected closed set."""
    schema = _load_schema()
    enum = schema["$defs"]["SafePrimitive"]["enum"]
    assert enum == [
        "add_pure_function",
        "edit_comment_or_docstring",
        "add_test",
        "edit_non_safety_file_body",
        "add_non_persistence_file",
    ]
    # No duplicates — a closed allow-list must be a set under the hood.
    assert len(enum) == len(set(enum))
