#!/usr/bin/env python3
"""One-shot structural hardening for Humming V2 A0.

The script runs only on the temporary child branch used to repair PR #1189.
It mutates governance intent/projections only, creates no implementation
surface, and grants no merge, deployment, credential, or runtime authority.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

TRACK_PATH = Path("docs/governance/ACTIVE_TRACK.yaml")
MANIFEST_PATH = Path("docs/governance/SOVEREIGN_MANIFEST.md")
LEDGER_PATH = Path(
    "docs/plans/handoffs/HUMMING_V2_EXECUTION_LEDGER_2026-08-01.md"
)

EXPECTED_NEXT_ITEMS = {
    "loop-closure-2026-06": {
        "humming-v2-p0-b-root-loop",
        "humming-v2-e1-cron-authority",
    },
    "merge-master-mike-d4-2026-06": {
        "humming-v2-enforcement-ack",
    },
    "organism-rewire-2026-07": {"humming-v2-host-ack"},
    "dharmagraph-engine-2026-07": {"humming-v2-p0-graph-adapter"},
    "sovereign-safety-tcb-2026-07": {
        "humming-v2-p0-k",
        "humming-v2-p0-h1a",
        "humming-v2-p0-h1b",
        "humming-v2-p0-h2a",
        "humming-v2-p0-h3-contract",
        "humming-v2-p0-b-contract",
    },
    "repository-titanium-hardening-2026-07": {
        "humming-v2-p0-harness-consumers",
        "humming-v2-p0-h6",
        "humming-v2-p0-b-adapters",
    },
}


def load_tracks(text: str) -> tuple[dict, dict[str, dict]]:
    data = yaml.safe_load(text)
    tracks = {item["id"]: item for item in data["active_tracks"]}
    return data, tracks


def track_span(text: str, track_id: str) -> tuple[int, int]:
    marker = f"  - id: {track_id}\n"
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"missing track: {track_id}")
    ends = [
        pos
        for pos in (
            text.find("\n  - id: ", start + len(marker)),
            text.find("\nclosed_tracks:", start + len(marker)),
        )
        if pos >= 0
    ]
    if not ends:
        raise SystemExit(f"cannot delimit track: {track_id}")
    return start, min(ends)


def parsed_track(text: str, track_id: str) -> dict:
    _, tracks = load_tracks(text)
    return tracks[track_id]


def move_item_to_next_items(text: str, track_id: str, item_id: str) -> str:
    current = parsed_track(text, track_id)
    next_ids = {str(item.get("id")) for item in current.get("next_items") or []}
    if item_id in next_ids:
        return text

    start, end = track_span(text, track_id)
    block = text[start:end]
    marker = f"      - id: {item_id}\n"
    item_start = block.find(marker)
    if item_start < 0:
        raise SystemExit(f"{track_id}: missing item block {item_id}")

    boundaries: list[int] = []
    for token in (
        "\n      - id: ",
        "\n    non_goals:",
        "\n    next_items:",
        "\n    completion_criteria:",
        "\n    prerequisites:",
    ):
        pos = block.find(token, item_start + len(marker))
        if pos >= 0:
            boundaries.append(pos)
    if not boundaries:
        raise SystemExit(f"{track_id}: cannot delimit {item_id}")
    item_end = min(boundaries)
    item_text = block[item_start:item_end].rstrip("\n") + "\n"
    block = block[:item_start] + block[item_end:]

    next_marker = "    next_items:\n"
    next_start = block.find(next_marker)
    if next_start < 0:
        raise SystemExit(f"{track_id}: no next_items field")
    payload_start = next_start + len(next_marker)
    next_field = re.search(
        r"\n    [A-Za-z_][A-Za-z0-9_]*:",
        block[payload_start:],
    )
    insert_at = (
        payload_start + next_field.start()
        if next_field is not None
        else len(block)
    )
    block = (
        block[:insert_at].rstrip("\n")
        + "\n"
        + item_text
        + block[insert_at:]
    )
    return text[:start] + block + text[end:]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, observed {count}")
    return text.replace(old, new, 1)


def harden_track_file() -> None:
    text = TRACK_PATH.read_text(encoding="utf-8")

    for owner, item_id in (
        ("loop-closure-2026-06", "humming-v2-p0-b-root-loop"),
        ("loop-closure-2026-06", "humming-v2-e1-cron-authority"),
        ("merge-master-mike-d4-2026-06", "humming-v2-enforcement-ack"),
    ):
        text = move_item_to_next_items(text, owner, item_id)

    text = replace_once(
        text,
        "      - dharma_swarm/action_effects/**\n",
        """      - dharma_swarm/action_effects/__init__.py
      - dharma_swarm/action_effects/envelope.py
      - dharma_swarm/action_effects/dispatcher.py
      - dharma_swarm/action_effects/budget.py
""",
        "exact action-effect ownership",
    )
    text = replace_once(
        text,
        """      - tests/test_telos_hook.py
      - docs/plans/handoffs/HUMMING_V2_EXECUTION_LEDGER_2026-08-01.md
""",
        """      - tests/test_telos_hook.py
      - tests/test_action_budget.py
      - docs/plans/handoffs/HUMMING_V2_EXECUTION_LEDGER_2026-08-01.md
""",
        "budget test ownership",
    )
    text = replace_once(
        text,
        """          constitutional ActionEnvelope and one action-effect dispatcher under
          dharma_swarm/action_effects/**, reusing ExecutionIdentity,
          RuntimeStateStore idempotency, Shakti warrants, EvidenceReceipt,
          reversibility gates, and existing runtime storage. The action class,
          never the caller, derives required fields. Initial migrated coverage
""",
        """          constitutional ActionEnvelope in action_effects/envelope.py and one
          action-effect dispatcher in action_effects/dispatcher.py, reusing
          ExecutionIdentity, RuntimeStateStore idempotency, Shakti warrants,
          EvidenceReceipt, reversibility gates, and existing runtime storage.
          Because semantic_governance.py already owns a semantic-only
          ActionEnvelope, rename that model to SemanticActionProposal and retain
          at most one tested deprecated alias; two unrelated canonical
          ActionEnvelope classes are forbidden. Keep dharma_swarm/graph/effects.py
          reserved for ambient time, randomness, and dispatch ordering. The
          action class, never the caller, derives required fields. Initial
          migrated coverage
""",
        "ActionEnvelope naming boundary",
    )
    text = replace_once(
        text,
        """          Establish one hierarchical parent/child budget reservation contract
          for loops, graph nodes, retries, provider fallbacks, and
""",
        """          Establish one hierarchical parent/child budget reservation contract
          in dharma_swarm/action_effects/budget.py, with contract tests in
          tests/test_action_budget.py, for loops, graph nodes, retries, provider
          fallbacks, and
""",
        "budget contract exact surfaces",
    )

    TRACK_PATH.write_text(text, encoding="utf-8")


def harden_manifest() -> None:
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "## VERIFIED NUMBERS (2026-07-29 COUNT REFRESH)",
        "## VERIFIED NUMBERS (2026-08-01 COUNT REFRESH)",
        "verified-number provenance date",
    )
    MANIFEST_PATH.write_text(text, encoding="utf-8")


def append_correction_log() -> None:
    text = LEDGER_PATH.read_text(encoding="utf-8")
    marker = "## A0 pre-merge correction log"
    if marker in text:
        return
    text = text.rstrip() + """

## A0 pre-merge correction log

- 2026-08-01: the first generated admission joined four newly owned surfaces
  to the preceding YAML scalar. Generic YAML parsing, track reconciliation,
  DocOps, and 147 focused tests still passed; an exact-membership negative
  control caught the false ownership. The four joins were repaired before
  independent A0 review.
- 2026-08-01: rendered blocker counts exposed that the Loop Closure and Merge
  Master additions had parsed under `completion_criteria` because those tracks
  order `non_goals` before `next_items`. They were moved into the actual owner
  queues, and the hardening evidence rejects every Humming item outside its
  declared track's `next_items`.
"""
    LEDGER_PATH.write_text(text, encoding="utf-8")


def assert_hardened() -> None:
    raw = TRACK_PATH.read_text(encoding="utf-8")
    data, tracks = load_tracks(raw)
    if len(data["active_tracks"]) != 10:
        raise SystemExit(f"active-track count changed: {len(data['active_tracks'])}")
    if any(track_id.startswith("humming-") for track_id in tracks):
        raise SystemExit("A0 created a forbidden Humming active track")

    expected_all = set().union(*EXPECTED_NEXT_ITEMS.values())
    for owner, expected in EXPECTED_NEXT_ITEMS.items():
        ids = [str(item.get("id")) for item in tracks[owner].get("next_items") or []]
        bad = sorted(item_id for item_id in expected if ids.count(item_id) != 1)
        if bad:
            raise SystemExit(f"{owner}: next-item multiplicity failure: {bad}")

    for owner, track in tracks.items():
        criterion_ids = {
            str(item.get("id"))
            for item in track.get("completion_criteria") or []
        }
        misplaced = sorted(criterion_ids & expected_all)
        if misplaced:
            raise SystemExit(
                f"{owner}: Humming items in completion_criteria: {misplaced}"
            )

    safety_owned = set(tracks["sovereign-safety-tcb-2026-07"]["owned_surfaces"])
    exact_action_files = {
        "dharma_swarm/action_effects/__init__.py",
        "dharma_swarm/action_effects/envelope.py",
        "dharma_swarm/action_effects/dispatcher.py",
        "dharma_swarm/action_effects/budget.py",
        "tests/test_action_budget.py",
    }
    missing = sorted(exact_action_files - safety_owned)
    if missing:
        raise SystemExit(f"missing exact action-effect surfaces: {missing}")
    if "dharma_swarm/action_effects/**" in safety_owned:
        raise SystemExit("broad action_effects owner expansion remains")
    if "SemanticActionProposal" not in raw:
        raise SystemExit("semantic ActionEnvelope migration is not explicit")
    if "dharma_swarm/graph/effects.py" not in raw:
        raise SystemExit("ambient graph effects boundary is not explicit")
    if "tests/test_action_budget.py" not in raw:
        raise SystemExit("budget contract test surface is absent")

    manifest = MANIFEST_PATH.read_text(encoding="utf-8")
    if "## VERIFIED NUMBERS (2026-08-01 COUNT REFRESH)" not in manifest:
        raise SystemExit("verified-number date remains stale")
    ledger = LEDGER_PATH.read_text(encoding="utf-8")
    if "## A0 pre-merge correction log" not in ledger:
        raise SystemExit("correction log missing")

    print("A0 structural hardening assertions: PASS")


def main() -> int:
    harden_track_file()
    harden_manifest()
    append_correction_log()
    assert_hardened()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
