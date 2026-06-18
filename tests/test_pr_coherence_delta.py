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


def test_label_aliases_are_accepted() -> None:
    body = """
- Organs touched: dharma_swarm/providers.py (provider chain)
- Gap closed: BR-021 evidence at providers.py:2808
- Proof: re-ran make orient and docops
- Drift introduced: none
"""

    results = checker.validate_body(body)

    assert all(result.ok for result in results)


def test_comment_fallback_satisfies_gate() -> None:
    body = "Just a summary, no coherence delta."
    comment = """
## Coherence Delta
- Organ touched: docs/governance
- Declared-vs-actual gap closed: none — docs-only change
- Proof that re-reads the map: read COHERENCE_DELTA.md
- New drift introduced: none
"""

    results, source = checker.validate_sources(body, ["unrelated", comment])

    assert all(result.ok for result in results)
    assert source == "PR comment #2"


def test_comment_fallback_fails_when_no_source_valid() -> None:
    results, source = checker.validate_sources("nothing", ["also nothing"])

    assert not all(result.ok for result in results)
    assert source == "PR body"


def test_injected_html_comment_after_last_field_passes() -> None:
    body = """
## Coherence Delta
- Organ touched: scripts/governance/check_pr_coherence_delta.py
- Declared-vs-actual gap closed: none — gate hardening
- Proof that re-reads the map: read COHERENCE_DELTA.md and ran the checker
- New drift introduced: none

Link to Devin session: https://example.invalid/session
Requested by: @someone

<!-- greptile_comment -->
## Greptile overview
some bot-rendered review prose that should not poison the last field
<!-- /greptile_comment -->
"""

    results = checker.validate_body(body)

    assert all(result.ok for result in results)


def test_html_comment_only_answer_still_fails() -> None:
    body = """
- Organ touched: docs/governance
- Declared-vs-actual gap closed: none
- Proof that re-reads the map: read the map
- New drift introduced: <!-- named drift, or 'none' -->
"""

    results = checker.validate_body(body)

    failed = {result.name: result.reason for result in results if not result.ok}
    assert failed == {"New drift introduced": "placeholder value"}


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
