"""Domain classification for tasks and free text.

Maps arbitrary text (or a Task) to one of the 8 operational domains defined
in ``shakti_zeitgeist_executive.DOMAINS``.  Uses the theme keyword table from
``thinkodynamic_director`` (imported lazily — that module is large) and the
theme→domain mapping already curated by the executive.

The caller protocol is deliberately small:

    domain = infer_domain(task)
    domain = classify_text("write NeurIPS abstract section 2")

Missing/empty/unknown → ``"internal_maintenance"`` (the neutral sink).
"""

from __future__ import annotations

from typing import Any

from dharma_swarm.shakti_zeitgeist_executive import DOMAINS, THEME_TO_DOMAIN

_DEFAULT_DOMAIN = "internal_maintenance"


def _valid_domain(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower().replace(" ", "_")
    return v if v in DOMAINS else None


def classify_text(text: str) -> str:
    """Return one of ``DOMAINS`` by keyword scoring. Falls back on empty text."""
    if not text or not text.strip():
        return _DEFAULT_DOMAIN
    try:
        from dharma_swarm.thinkodynamic_director import _theme_scores_from_text
    except Exception:
        return _DEFAULT_DOMAIN
    scores = _theme_scores_from_text(text)
    if not scores:
        return _DEFAULT_DOMAIN
    top_theme = max(scores, key=scores.get)  # type: ignore[arg-type]
    return THEME_TO_DOMAIN.get(top_theme, _DEFAULT_DOMAIN)


def infer_domain(task: Any) -> str:
    """Resolve a domain for a task.

    Order:
    1. ``task.metadata["domain"]`` if set and valid
    2. ``task.metadata["campaign_id"]`` present → classify campaign's domain via loader
    3. Classify ``title + description`` via keywords
    """
    metadata: dict[str, Any] = {}
    try:
        metadata = dict(getattr(task, "metadata", {}) or {})
    except Exception:
        metadata = {}

    explicit = _valid_domain(metadata.get("domain"))
    if explicit:
        return explicit

    campaign_id = metadata.get("campaign_id")
    if campaign_id:
        try:
            from dharma_swarm.campaigns import find_campaign_domain
            campaign_domain = _valid_domain(find_campaign_domain(campaign_id))
            if campaign_domain:
                return campaign_domain
        except Exception:
            pass

    title = str(getattr(task, "title", "") or "")
    description = str(getattr(task, "description", "") or "")
    return classify_text(f"{title}\n{description}")


__all__ = ["classify_text", "infer_domain", "DOMAINS", "THEME_TO_DOMAIN"]
