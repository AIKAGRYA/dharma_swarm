from scripts.governance import check_pr_coherence_delta as checker


def test_valid_coherence_delta_body_passes() -> None:
    body = """
## Coherence Delta

- Organ touched: docs/governance and PR template
- Declared-vs-actual gap closed: BR-019 closes honor-system-only merge gate
- Proof that re-reads the map: read COHERENCE_DELTA.md and ran docops
- New drift introduced: none
"""

    results = checker.validate_body(body)

    assert all(result.ok for result in results)


def test_missing_field_fails() -> None:
    body = """
- Organ touched: docs
- Declared-vs-actual gap closed: none
- Proof that re-reads the map: read the map
"""

    results = checker.validate_body(body)

    failed = {result.name: result.reason for result in results if not result.ok}
    assert failed == {"New drift introduced": "missing field"}


def test_unknown_without_reason_fails() -> None:
    body = """
- Organ touched: UNKNOWN
- Declared-vs-actual gap closed: none
- Proof that re-reads the map: read the map
- New drift introduced: none
"""

    results = checker.validate_body(body)

    failed = {result.name: result.reason for result in results if not result.ok}
    assert failed["Organ touched"] == "UNKNOWN requires a reason"


def test_multiline_answer_is_accepted_until_next_field() -> None:
    body = """
- Organ touched:
  docs/state/BROKEN_REGISTER.md
  docs/MEGAFILE_INDEX.md
- Declared-vs-actual gap closed: BR-010
- Proof that re-reads the map: audit and DocOps
- New drift introduced: none
"""

    value = checker.extract_field(body, "Organ touched")

    assert value is not None
    assert "BROKEN_REGISTER" in value
    assert "MEGAFILE_INDEX" in value
