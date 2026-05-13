"""Three-pass R&D incubation for high-upside world signals."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_incubations(
    movements: list[dict[str, Any]],
    *,
    output_dir: Path,
) -> list[dict[str, Any]]:
    """Write markdown + JSON incubation artifacts and return movement updates."""
    output_dir.mkdir(parents=True, exist_ok=True)
    updates: list[dict[str, Any]] = []
    for movement in movements:
        payload = build_incubation_payload(movement)
        slug = _slug(str(movement.get("movement_id") or movement.get("title") or "signal"))
        stem = f"{datetime.now(timezone.utc).strftime('%Y%m%d')}_{slug}"
        json_path = output_dir / f"{stem}.json"
        md_path = output_dir / f"{stem}.md"
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(render_incubation_markdown(payload), encoding="utf-8")
        updates.append(
            {
                "movement_id": movement.get("movement_id"),
                "incubation_json_path": str(json_path),
                "incubation_markdown_path": str(md_path),
                "incubation_id": payload["incubation_id"],
            }
        )
    return updates


def build_incubation_payload(movement: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic verify/connect/evolve content for one movement."""
    signals = list(movement.get("signals") or [])
    top = dict(signals[0]) if signals else {}
    title = str(movement.get("title") or top.get("title") or "Untitled signal")
    evidence = [
        {
            "source": signal.get("source"),
            "raw_source": signal.get("raw_source"),
            "url": signal.get("url"),
            "title": signal.get("title"),
            "score": signal.get("weighted_score"),
        }
        for signal in signals[:8]
    ]
    queries = list(movement.get("cascade_queries") or [])[:12]
    questions = list(movement.get("questions") or [])[:10] or _default_questions(title)
    return {
        "incubation_id": _stable_id(str(movement.get("movement_id") or title)),
        "movement_id": movement.get("movement_id"),
        "title": title,
        "status": "incubating",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "promotion_rule": "promote only after two independent sources, or operator drop plus concrete evidence URL",
        "uncertainty": movement.get("uncertainty"),
        "weighted_score": movement.get("weighted_score"),
        "pass_1_verify": {
            "goal": "Establish whether the claim is real, recent, and source-backed.",
            "checklist": [
                "Open the primary URL and capture title, publisher, and date.",
                "Find at least one independent adjacent witness.",
                "Reject or downgrade if source, date, or claim cannot be verified.",
            ],
            "evidence": evidence,
        },
        "pass_2_connect": {
            "goal": "Connect the signal to adjacent companies, repos, papers, and movements.",
            "cascade_queries": queries,
            "adjacent_searches": list(movement.get("adjacent_searches") or [])[:10],
        },
        "pass_3_evolve": {
            "goal": "Turn the signal into a stronger Dharma-native research direction.",
            "first_principles_questions": questions,
            "prototype_angles": _prototype_angles(title),
            "strategic_moves": list(movement.get("strategic_moves") or [])[:10],
            "governance_risks": [
                "Do not treat hype as evidence.",
                "Do not initiate external outreach or spend without human approval.",
                "Preserve source links and uncertainty in every promoted artifact.",
            ],
        },
        "draft_task_proposal": {
            "title": f"Research incubation: {title}",
            "domain": "ecosystem_scan",
            "thesis": "world_signal_incubation",
            "suggested_action": "Verify, connect, and evolve this signal before Shakti promotion.",
        },
    }


def render_incubation_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# World Signal Incubation: {payload['title']}",
        "",
        f"- Status: {payload['status']}",
        f"- Movement: {payload.get('movement_id')}",
        f"- Uncertainty: {payload.get('uncertainty')}",
        f"- Score: {payload.get('weighted_score')}",
        "",
        "## Pass 1: Verify",
        payload["pass_1_verify"]["goal"],
        "",
    ]
    for item in payload["pass_1_verify"]["checklist"]:
        lines.append(f"- {item}")
    lines.extend(["", "Evidence:"])
    for item in payload["pass_1_verify"]["evidence"]:
        lines.append(f"- {item.get('source')}: {item.get('title')} ({item.get('url')})")
    lines.extend(["", "## Pass 2: Connect", payload["pass_2_connect"]["goal"], ""])
    for query in payload["pass_2_connect"]["cascade_queries"]:
        lines.append(f"- {query}")
    lines.extend(["", "## Pass 3: Evolve", payload["pass_3_evolve"]["goal"], ""])
    for question in payload["pass_3_evolve"]["first_principles_questions"]:
        lines.append(f"- {question}")
    lines.extend(["", "Prototype angles:"])
    for angle in payload["pass_3_evolve"]["prototype_angles"]:
        lines.append(f"- {angle}")
    return "\n".join(lines).rstrip() + "\n"


def _default_questions(title: str) -> list[str]:
    return [
        "What primitive capability or constraint does this reveal?",
        f"What made {title} possible now?",
        "What is the smallest truthful Dharma-native prototype?",
        "Which adjacent companies, repos, papers, or communities are moving similarly?",
        "What evidence would prove this is signal rather than hype?",
        "What can be copied, what must be re-invented, and what should be avoided?",
        "Which current substrate can absorb this without creating a sibling runtime?",
        "What research draft would be useful by tomorrow morning?",
        "What governance or reputation risk is attached?",
        "What outcome would justify Shakti promotion?",
    ]


def _prototype_angles(title: str) -> list[str]:
    return [
        f"Reverse-engineer the workflow behind {title}.",
        "Draft a one-page competitor and adjacent-possible map.",
        "Design a 24-hour internal prototype that produces a visible artifact.",
        "Define the evidence threshold for promotion to an opportunity.",
    ]


def _stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]


def _slug(value: str) -> str:
    raw = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    raw = "-".join(part for part in raw.split("-") if part)
    return raw[:80] or "signal"
