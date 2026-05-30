"""Cross-language SafePrimitive parity test (the triangle-closing seam).

The TelosProof v1 allow-list vocabulary lives in THREE places that must agree
exactly, or an operation "named safe" in one language could be unnamed / renamed
in another and silently drift:

  1. Python  — ``dharma_swarm.telosproof.allowlist.SAFE_PRIMITIVES`` (frozenset).
  2. JSON    — ``specs/contracts/change_summary.schema.json`` $defs.SafePrimitive.enum.
  3. Lean    — the ``SafePrimitive`` inductive constructors in
               ``specs/proofs/telosproof/Primitives.lean`` (camelCase), mapped to
               snake_case.

This test closes the triangle:

    set(schema enum) == allowlist.SAFE_PRIMITIVES == snake_case(Lean constructors)

It parses the real ``.lean`` file for the constructor identifiers (it does NOT
hard-code them), so adding/removing/renaming a Lean constructor without updating
the Python frozenset and the JSON enum fails CI loudly. The Lean file is a
STRUCTURAL/TYPE-LEVEL SCAFFOLD (it shares the vocabulary, it is not a body-level
safety proof); the only property this test relies on is name parity.

ADVISORY ONLY. Pure assertions over committed text files + an importable Python
frozenset; no I/O beyond reading the schema and the .lean source, no live wiring.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from dharma_swarm.telosproof.allowlist import SAFE_PRIMITIVES

# This test file lives at <repo>/tests/, so both artifacts are one directory up.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_PATH = _REPO_ROOT / "specs" / "contracts" / "change_summary.schema.json"
_LEAN_PATH = _REPO_ROOT / "specs" / "proofs" / "telosproof" / "Primitives.lean"

# Match the body of the `SafePrimitive` inductive: from the `inductive SafePrimitive`
# header up to (but not including) the next top-level `inductive`/`def`/`abbrev`/
# `structure`/`theorem`/`instance` declaration. Within that body, constructor lines
# are `  | constructorName`.
_INDUCTIVE_BLOCK_RE = re.compile(
    r"inductive\s+SafePrimitive\b.*?(?=\n(?:inductive|def|abbrev|structure|theorem|instance|namespace|end)\b)",
    re.DOTALL,
)
_CONSTRUCTOR_RE = re.compile(r"^\s*\|\s*([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)


def _camel_to_snake(name: str) -> str:
    """addPureFunction -> add_pure_function (the cross-language naming map)."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _schema_enum() -> set[str]:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return set(schema["$defs"]["SafePrimitive"]["enum"])


def _lean_constructor_names_snake() -> set[str]:
    """Parse Primitives.lean for the SafePrimitive inductive's constructor names."""
    text = _LEAN_PATH.read_text(encoding="utf-8")
    block_match = _INDUCTIVE_BLOCK_RE.search(text)
    assert block_match, (
        "could not locate the `inductive SafePrimitive` block in "
        f"{_LEAN_PATH}; parity cannot be checked"
    )
    block = block_match.group(0)
    constructors = _CONSTRUCTOR_RE.findall(block)
    return {_camel_to_snake(c) for c in constructors}


def test_artifacts_exist():
    assert _SCHEMA_PATH.exists(), f"missing schema at {_SCHEMA_PATH}"
    assert _LEAN_PATH.exists(), f"missing Lean source at {_LEAN_PATH}"


def test_schema_enum_matches_python_frozenset():
    """JSON enum set == Python SAFE_PRIMITIVES frozenset (exact set equality)."""
    enum = _schema_enum()
    assert enum == set(SAFE_PRIMITIVES), (
        "schema/Python drift: "
        f"only-in-schema={sorted(enum - set(SAFE_PRIMITIVES))} "
        f"only-in-python={sorted(set(SAFE_PRIMITIVES) - enum)}"
    )


def test_lean_constructors_parse_and_are_nonempty():
    """The Lean inductive yields a non-empty constructor set (parser sanity)."""
    lean = _lean_constructor_names_snake()
    assert lean, "no SafePrimitive constructors parsed from Primitives.lean"
    # The closed allow-list is exactly five primitives in this increment.
    assert len(lean) == 5, f"expected 5 Lean constructors, got {sorted(lean)}"


def test_full_triangle_parity():
    """set(schema enum) == SAFE_PRIMITIVES == snake_case(Lean constructors)."""
    enum = _schema_enum()
    python = set(SAFE_PRIMITIVES)
    lean = _lean_constructor_names_snake()
    assert enum == python == lean, (
        "CROSS-LANGUAGE PARITY VIOLATION (schema / Python / Lean diverge):\n"
        f"  schema enum      = {sorted(enum)}\n"
        f"  SAFE_PRIMITIVES  = {sorted(python)}\n"
        f"  Lean (snake)     = {sorted(lean)}\n"
        f"  schema-only      = {sorted(enum - (python & lean))}\n"
        f"  python-only      = {sorted(python - (enum & lean))}\n"
        f"  lean-only        = {sorted(lean - (enum & python))}"
    )


def test_no_constructor_camelcase_mapping_collision():
    """Each Lean camelCase constructor maps to a DISTINCT snake_case name.

    Guards against two distinct Lean constructors collapsing to the same
    snake_case name (which would silently shrink the cross-language set).
    """
    text = _LEAN_PATH.read_text(encoding="utf-8")
    block = _INDUCTIVE_BLOCK_RE.search(text).group(0)
    raw = _CONSTRUCTOR_RE.findall(block)
    snake = [_camel_to_snake(c) for c in raw]
    assert len(snake) == len(set(snake)), (
        f"camelCase->snake_case collision among Lean constructors: {raw}"
    )
