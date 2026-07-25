"""Small identity-name helpers for facades; no runtime store."""

from __future__ import annotations


def canonical_agent_uid(value: str) -> str:
    """Normalize spelling for lookup only; does not mutate runtime state."""
    return str(value or "").strip().replace("-", "_")


__all__ = ["canonical_agent_uid"]
