"""Synthetic helper module for the audit-kit fixture."""


def normalize_record(record: dict) -> dict:
    """Original copy; `src/app.py` carries a planted duplicate of this body."""
    cleaned = {}
    for key, value in record.items():
        if value is None:
            continue
        cleaned[key.strip().lower()] = value
    return cleaned
