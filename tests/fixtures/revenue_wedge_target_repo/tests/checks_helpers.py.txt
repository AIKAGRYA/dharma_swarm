"""Fixture test evidence covering helpers only.

Named `checks_helpers.py` so the parent repository's pytest run does not
collect it; the audit kit counts it as test evidence because it lives under
`tests/`. It deliberately never mentions the other source module, leaving a
known coverage gap for the scanner to find.
"""

from src.helpers import normalize_record


def check_normalize_record_drops_none_values() -> None:
    assert normalize_record({"A ": 1, "b": None}) == {"a": 1}
