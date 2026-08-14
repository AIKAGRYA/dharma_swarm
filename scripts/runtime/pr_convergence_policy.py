#!/usr/bin/env python3
"""pr_convergence_policy.py — deterministic PR convergence ordering (ADVISORY).

The "convergence steward" core, the LIGHT way: a pure, reproducible policy that
ranks open PRs so the swarm self-orders instead of the operator triaging by hand.
It is ADVISORY — it never feeds Merge Master Mike's build_gate blockers and never
changes merge authority. Mike (or the operator) may consume the order as ONE
ordering input; the gate decision is unchanged.

Policy (deterministic — identical inputs always yield identical output):
  R1 drafts-don't-lead   — draft PRs rank last.
  R2 decision > impl     — PRs touching governance/decision surfaces outrank pure
                           implementation PRs.
  R3 surface-overlap->1  — when 2+ non-draft PRs touch the same HAND-EDITED owned
                           surface, elect ONE canonical lane (highest rigor grade,
                           then lowest PR#); the others are marked dependent.
  R4 escalate-when-undef — an overlap with no deterministic canonical signal
                           (equal grade AND no rigor signal at all) is added to
                           escalate[] instead of guessing; the ratchet must
                           exclude escalate-flagged PRs from auto-merge.

Regenerable outputs (active_track_evidence.json/.md, track_portfolio.json) are
NOT real collisions and are excluded from R3 — they regenerate from the gate.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]

# Two PRs both touching these is NOT a real collision (regenerated, not hand-edited).
REGENERABLE = frozenset({
    "reports/governance/active_track_evidence.json",
    "reports/governance/active_track_evidence.md",
    "reports/governance/track_portfolio.json",
})

# A PR touching any of these (hand-edited) is a "decision/governance" lane (R2).
DECISION_GLOBS = (
    "docs/governance/**",
    "docs/architecture/ADRs/**",
    "ACTIVE_TRACK.yaml",
    "docs/governance/ACTIVE_TRACK.yaml",
    "docs/governance/SOVEREIGN_MANIFEST.md",
    "docs/governance/CANONICAL_DOC_STACK.md",
)

PLAN_SCHEMA = "dharma.pr_convergence.action_plan.v1"
MAX_OPERATOR_INBOX = 5

# These are recommendations for a reasoning/execution plane, never permissions.
# In particular, QUEUE_CANDIDATE is deliberately not called MERGE or AUTHORIZE:
# the executor must re-read GitHub and reconstruct the exact candidate tuple
# before asking the native queue to admit it.
WAIT = "WAIT"
REQUEST_REVIEW = "REQUEST_REVIEW"
RERUN_TRANSIENT = "RERUN_TRANSIENT"
REFRESH_STRANDED = "REFRESH_STRANDED"
REPAIR_CODE = "REPAIR_CODE"
QUEUE_CANDIDATE = "QUEUE_CANDIDATE"
HUMAN_EXCEPTION = "HUMAN_EXCEPTION"
OPERATOR_CANCELLED = "OPERATOR_CANCELLED"
MERGED = "MERGED"

_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_QUEUE_STATES = frozenset({"AWAITING_CHECKS", "QUEUED", "LOCKED", "MERGEABLE"})
_POLICY_CLASSES = frozenset({"docs_low", "code", "operator_only"})
_RISKS = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})
_CI_STATES = frozenset({"green", "pending", "transient", "failed", "missing", "unknown"})
_REVIEW_STATES = frozenset({"clean", "changes_requested", "unknown"})
_PR_STATES = frozenset({"OPEN", "CLOSED", "MERGED"})
_OPERATOR_QUEUE_INTENTS = frozenset({"NONE", "ENQUEUED", "DEQUEUED"})
_QUEUE_ENTRY_PROVENANCE = frozenset({"NONE", "OPERATOR", "TRUSTED_LOOP"})
_MERGE_PROVENANCE = frozenset({"NONE", "NATIVE_QUEUE", "DIRECT_OR_UNKNOWN"})
_AI_EVIDENCE_STATES = frozenset({"APPROVED", "COMMENTED"})
_GITHUB_ACTIONS_APP_ID = 15368

_NO_AUTHORITY = {
    "planner_modality": "advisory_only",
    "can_merge": False,
    "can_approve": False,
    "can_bypass": False,
    "can_resolve_threads": False,
}

_POLICY_PATH = REPO_ROOT / "scripts" / "governance" / "automerge_tier_policy.json"
_ACTIVE_TRACK_PATH = REPO_ROOT / "docs" / "governance" / "ACTIVE_TRACK.yaml"
_TRUSTED_POLICY = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
if _TRUSTED_POLICY.get("schema") != "dharma.automerge_tier_policy.v3":
    raise RuntimeError(f"unrecognized trusted authority policy: {_POLICY_PATH}")


def _canonical_digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


TRUSTED_POLICY_DIGEST = _canonical_digest(_TRUSTED_POLICY)
_TRUSTED_AI_ACTORS = {
    login.strip().lower() for login in _TRUSTED_POLICY["reviewer_families"]
}
_TRUSTED_OPERATOR_ACTORS = {
    login.strip().lower()
    for login in _TRUSTED_POLICY["authority_policy"]["operator_identities"]
}


def _load_trusted_owned_surfaces(path: Path) -> tuple[str, ...]:
    surfaces = set()
    lines = path.read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped != "owned_surfaces:":
            index += 1
            continue
        parent_indent = len(line) - len(line.lstrip())
        index += 1
        while index < len(lines):
            candidate = lines[index]
            candidate_stripped = candidate.strip()
            if not candidate_stripped or candidate_stripped.startswith("#"):
                index += 1
                continue
            indent = len(candidate) - len(candidate.lstrip())
            if indent <= parent_indent:
                break
            if candidate_stripped.startswith("- "):
                value = candidate_stripped[2:].split(" #", 1)[0].strip().strip("'\"")
                if value:
                    surfaces.add(value)
            index += 1
    if not surfaces:
        raise RuntimeError(f"trusted owner registry contains no owned surfaces: {path}")
    return tuple(sorted(surfaces))


TRUSTED_OWNED_SURFACES = _load_trusted_owned_surfaces(_ACTIVE_TRACK_PATH)
TRUSTED_OWNED_SURFACES_DIGEST = hashlib.sha256(
    json.dumps(TRUSTED_OWNED_SURFACES, separators=(",", ":")).encode("utf-8")
).hexdigest()


def _matches_any(path: str, globs) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


def _policy_matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**") and not any(
        marker in pattern[:-3] for marker in ("*", "?", "[")
    ):
        return path.startswith(pattern[:-2])
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return path == pattern or fnmatch.fnmatch(path, pattern)


def _trusted_path_class(changed_paths: list[str]) -> str:
    authority = _TRUSTED_POLICY["authority_policy"]
    operator_patterns = (
        list(authority["operator_only_paths"])
        + list(_TRUSTED_POLICY["tiers"]["tier2"]["paths"])
    )
    if any(
        _policy_matches(path, pattern)
        for path in changed_paths
        for pattern in operator_patterns
    ):
        return "operator_only"
    docs_low = changed_paths and all(
        any(_policy_matches(path, pattern) for pattern in authority["docs_low_allow"])
        and not any(_policy_matches(path, pattern) for pattern in authority["docs_low_deny"])
        for path in changed_paths
    )
    return "docs_low" if docs_low else "code"


def _real_files(files):
    """Files that count for collision — regenerable outputs excluded."""
    return [f for f in files if f not in REGENERABLE]


def is_decision_pr(files) -> bool:
    return any(_matches_any(f, DECISION_GLOBS) for f in _real_files(files))


def overlapping_surface(files_a, files_b, owned_surfaces=()) -> bool:
    """True iff A and B both touch the same hand-edited file or owned-surface glob."""
    ra, rb = set(_real_files(files_a)), set(_real_files(files_b))
    if ra & rb:
        return True
    for surf in owned_surfaces:
        if any(_matches_any(f, [surf]) for f in ra) and any(_matches_any(f, [surf]) for f in rb):
            return True
    return False


def compute_convergence_order(
    open_prs,
    pr_files,
    owned_surfaces=(),
    grades=None,
    collision_excluded=(),
) -> dict:
    """Pure. open_prs: [{number:int, isDraft:bool, ...}]; pr_files: {num:[paths]};
    owned_surfaces: iterable of globs; grades: {num:int}. Returns
    {order, rationale, escalate, canonical}. Same inputs -> same output."""
    if grades is None:
        grades = {}
    if not isinstance(grades, Mapping) or not all(
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= 8
        for value in grades.values()
    ):
        raise ValueError("grades values must be integers from 0 to 8")
    excluded = set(collision_excluded)
    rationale: dict = {}
    escalate: list = []
    canonical: dict = {}
    dependent: set = set()

    drafts = {p["number"]: bool(p.get("isDraft")) for p in open_prs}
    nondraft = [
        p["number"]
        for p in open_prs
        if not drafts.get(p["number"]) and p["number"] not in excluded
    ]

    adjacency = {number: set() for number in nondraft}
    for i, a in enumerate(sorted(nondraft)):
        for b in sorted(nondraft)[i + 1:]:
            if overlapping_surface(pr_files.get(a, []), pr_files.get(b, []), owned_surfaces):
                adjacency[a].add(b)
                adjacency[b].add(a)

    seen: set[int] = set()
    for start in sorted(nondraft):
        if start in seen or not adjacency[start]:
            seen.add(start)
            continue
        component = set()
        frontier = [start]
        while frontier:
            current = frontier.pop()
            if current in component:
                continue
            component.add(current)
            frontier.extend(sorted(adjacency[current] - component, reverse=True))
        seen.update(component)
        members = sorted(component)
        max_grade = max(int(grades.get(number, 0)) for number in members)
        if max_grade == 0:
            escalate.extend(members)  # R4: no rigor signal anywhere in the component
            continue

        ranked = sorted(members, key=lambda number: (-int(grades.get(number, 0)), number))
        selected: list[int] = []
        assigned: dict[int, int] = {}
        for candidate in ranked:
            adjacent_winners = [winner for winner in selected if winner in adjacency[candidate]]
            if not adjacent_winners:
                selected.append(candidate)
                continue
            winner = min(
                adjacent_winners,
                key=lambda number: (-int(grades.get(number, 0)), number),
            )
            assigned[candidate] = winner

        for winner in selected:
            losers = sorted(loser for loser, owner in assigned.items() if owner == winner)
            if not losers:
                continue
            group = [winner, *losers]
            canonical[f"overlap:{'-'.join(str(number) for number in sorted(group))}"] = winner
            for loser in losers:
                dependent.add(loser)
                rationale[loser] = (
                    f"dependent: converge behind #{winner} (shared hand-edited surface)"
                )

    escalate = sorted(set(escalate))

    def sort_key(p):
        n = p["number"]
        return (
            1 if drafts.get(n) else 0,                               # R1: drafts last
            1 if n in dependent else 0,                              # R3: dependents after canonical
            0 if is_decision_pr(pr_files.get(n, [])) else 1,         # R2: decision first
            -int(grades.get(n, 0)),                                  # higher grade first
            n,                                                       # stable final tiebreak
        )

    order = [p["number"] for p in sorted(open_prs, key=sort_key)]
    for n in order:
        if n in rationale:
            continue
        if drafts.get(n):
            rationale[n] = "draft: ranked last (drafts don't lead)"
        elif is_decision_pr(pr_files.get(n, [])):
            rationale[n] = "decision/governance lane: outranks implementation"
        else:
            rationale[n] = "implementation lane"
    return {
        "order": order,
        "rationale": rationale,
        "escalate": escalate,
        "canonical": canonical,
        "dependent": sorted(dependent),
    }


def _item(
    number: int,
    fact: Mapping[str, Any],
    *,
    action: str,
    reason_code: str,
    explanation: str,
    repo: str,
    terminal_for_head: bool = False,
    terminal_key: dict[str, str] | None = None,
    queue_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    action_discriminator: object = None
    if action in {RERUN_TRANSIENT, REFRESH_STRANDED, REPAIR_CODE}:
        action_discriminator = {
            "attempt_ordinal": fact.get("repair_attempts"),
        }
    elif action == QUEUE_CANDIDATE:
        action_discriminator = queue_candidate
    action_key = _canonical_digest(
        {
            "schema": "dharma.pr_convergence.action_key.v1",
            "repo": repo,
            "pr": number,
            "head_sha": str(fact.get("head_sha") or ""),
            "base_sha": str(fact.get("base_sha") or ""),
            "action": action,
            "reason_code": reason_code,
            "queue_intent_event_id": fact.get("operator_queue_intent_event_id"),
            "action_discriminator": action_discriminator,
        }
    )
    return {
        "number": number,
        "url": f"https://github.com/{repo}/pull/{number}",
        "head_sha": str(fact.get("head_sha") or ""),
        "base_sha": str(fact.get("base_sha") or ""),
        "action": action,
        "reason_code": reason_code,
        "explanation": explanation,
        "action_key": action_key,
        "terminal_for_head": terminal_for_head,
        "terminal_key": terminal_key,
        "authority": dict(_NO_AUTHORITY),
        "queue_candidate": queue_candidate,
    }


def _unknown_fact(number: int, fact: Mapping[str, Any], repo: str, detail: str) -> dict[str, Any]:
    return _item(
        number,
        fact,
        action=HUMAN_EXCEPTION,
        reason_code="STATE_UNKNOWN",
        explanation=f"fail closed: {detail}",
        repo=repo,
        terminal_for_head=False,
    )


def _validate_queue_authorization_report(
    number: int,
    fact: Mapping[str, Any],
    repo: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate the owner's full unsigned evidence document for advisory admission.

    Integrity and exact bindings do not confer authority.  They only ensure a
    QUEUE_CANDIDATE cannot be built from an arbitrary 64-character string.
    """
    base_ref = fact.get("base_ref")
    title = fact.get("title")
    if not isinstance(base_ref, str) or not base_ref.strip():
        return None, "target ref is unknown"
    if not isinstance(title, str):
        return None, "current PR title is unknown"
    report = fact.get("authorization_report")
    if not isinstance(report, Mapping):
        return None, "authorization evidence report is absent"
    if report.get("schema") != "dharma.automerge_tier_policy_report.v2":
        return None, "authorization evidence report schema is untrusted"
    if report.get("passed") is not True or report.get("violations") != []:
        return None, "authorization policy report did not pass cleanly"
    evidence = report.get("authorization_evidence")
    if not isinstance(evidence, Mapping):
        return None, "authorization evidence is absent"
    if evidence.get("schema") != "dharma.merge_authorization_evidence.v1":
        return None, "authorization evidence schema is untrusted"
    expected = {
        "repo": repo,
        "pr": number,
        "head_sha": fact["head_sha"],
        "base_sha": fact["base_sha"],
        "base_ref": base_ref,
        "policy_sha256": TRUSTED_POLICY_DIGEST,
        "intent_sha256": _canonical_digest(title),
        "authority_class": fact["policy_class"],
        "provenance": "unsigned-github-snapshot",
        "actuation_eligible": False,
    }
    if any(evidence.get(field) != value for field, value in expected.items()):
        return None, "authorization evidence binding is stale or mismatched"
    evidence_ids = evidence.get("ai_evidence_ids")
    if (
        not isinstance(evidence_ids, list)
        or not evidence_ids
        or any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
            for value in evidence_ids
        )
        or len(evidence_ids) != len(set(evidence_ids))
        or fact["ai_evidence_id"] not in evidence_ids
    ):
        return None, "authorization evidence does not include the trusted AI review"
    warrant = evidence.get("operator_warrant")
    if fact["operator_warrant"]:
        if not isinstance(warrant, Mapping):
            return None, "authorization evidence lacks the operator warrant"
        if (
            warrant.get("kind") != fact["operator_warrant_kind"]
            or warrant.get("id") != fact["operator_warrant_id"]
            or str(warrant.get("actor") or "").strip().lower()
            != str(fact["operator_warrant_actor"]).strip().lower()
            or warrant.get("head_sha") != fact["head_sha"]
        ):
            return None, "authorization evidence operator warrant is mismatched"
    elif warrant is not None:
        return None, "authorization evidence claims an unobserved operator warrant"
    claimed_digest = evidence.get("digest")
    digest_payload = {key: value for key, value in evidence.items() if key != "digest"}
    if not isinstance(claimed_digest, str) or claimed_digest != _canonical_digest(digest_payload):
        return None, "authorization evidence digest is invalid"
    return dict(evidence), None


def _validate_native_queue_merge_observation(
    number: int,
    fact: Mapping[str, Any],
) -> str | None:
    observation = fact.get("merge_observation")
    if not isinstance(observation, Mapping):
        return "native-queue merge observation is absent"
    expected = {
        "schema": "dharma.native_queue_merge_observation.v1",
        "pr": number,
        "pr_head_sha": fact["head_sha"],
        "base_sha": fact["base_sha"],
        "merge_method": "SQUASH",
        "queue_removal_reason": "MERGED",
        "timeline_complete": True,
    }
    if any(observation.get(field) != value for field, value in expected.items()):
        return "native-queue merge observation binding is stale or mismatched"
    merge_group_sha = observation.get("merge_group_sha")
    merge_commit_sha = observation.get("merge_commit_sha")
    if (
        not isinstance(merge_group_sha, str)
        or not _HEX_40.fullmatch(merge_group_sha)
        or merge_commit_sha != merge_group_sha
    ):
        return "native-queue merge candidate/final commit proof is invalid"
    for field in (
        "queue_entry_event_id",
        "merge_event_id",
        "queue_removal_event_id",
    ):
        if not isinstance(observation.get(field), str) or not observation[field].strip():
            return f"native-queue {field} is absent"
    claimed_digest = observation.get("digest")
    digest_payload = {key: value for key, value in observation.items() if key != "digest"}
    if not isinstance(claimed_digest, str) or claimed_digest != _canonical_digest(digest_payload):
        return "native-queue merge observation digest is invalid"
    return None


def _validate_fact(
    number: int,
    fact: Mapping[str, Any],
    repo: str,
    changed_paths: list[str],
) -> dict[str, Any] | None:
    """Return a fail-closed item when a required epistemic input is unknown."""
    observed_number = fact.get("number", number)
    if (
        not isinstance(observed_number, int)
        or isinstance(observed_number, bool)
        or observed_number != number
    ):
        return _unknown_fact(number, fact, repo, "snapshot PR number does not match")
    if not isinstance(fact.get("head_sha"), str) or not _HEX_40.fullmatch(fact["head_sha"]):
        return _unknown_fact(number, fact, repo, "head SHA is not a full commit OID")
    if not isinstance(fact.get("base_sha"), str) or not _HEX_40.fullmatch(fact["base_sha"]):
        return _unknown_fact(number, fact, repo, "base SHA is not a full commit OID")
    required_bools = (
        "head_observed_current",
        "base_observed_current",
        "is_draft",
        "is_cross_repository",
        "ai_evidence",
        "operator_warrant",
        "repairable_threads",
        "policy_gate_observed",
        "policy_gate_passed",
        "queue_timeline_complete",
    )
    for name in required_bools:
        if not isinstance(fact.get(name), bool):
            return _unknown_fact(number, fact, repo, f"{name} is unknown")
    operator_intent = str(fact.get("operator_queue_intent") or "")
    if operator_intent not in _OPERATOR_QUEUE_INTENTS:
        return _unknown_fact(number, fact, repo, "latest operator queue intent is unknown")
    intent_head = fact.get("operator_queue_intent_head_sha")
    intent_event_id = fact.get("operator_queue_intent_event_id")
    intent_actor = str(fact.get("operator_queue_intent_actor") or "").strip().lower()
    if not fact["queue_timeline_complete"]:
        return _unknown_fact(number, fact, repo, "queue timeline pagination is incomplete")
    if operator_intent == "NONE":
        if intent_head is not None or intent_event_id is not None or intent_actor:
            return _unknown_fact(number, fact, repo, "absent operator intent claims evidence")
    else:
        if intent_head != fact["head_sha"]:
            return _unknown_fact(number, fact, repo, "operator queue intent is not bound to this head")
        if not isinstance(intent_event_id, str) or not intent_event_id.strip():
            return _unknown_fact(number, fact, repo, "operator queue intent event is unknown")
        if intent_actor not in _TRUSTED_OPERATOR_ACTORS:
            return _unknown_fact(number, fact, repo, "operator queue intent actor is untrusted")
    if str(fact.get("policy_class") or "") not in _POLICY_CLASSES:
        return _unknown_fact(number, fact, repo, "policy class is unknown")
    if fact["policy_class"] != _trusted_path_class(changed_paths):
        return _unknown_fact(number, fact, repo, "policy class disagrees with trusted path policy")
    if fact.get("policy_digest") != TRUSTED_POLICY_DIGEST:
        return _unknown_fact(number, fact, repo, "authority policy digest is stale or untrusted")
    if str(fact.get("risk") or "") not in _RISKS:
        return _unknown_fact(number, fact, repo, "risk is unknown")
    if str(fact.get("ci_state") or "") not in _CI_STATES:
        return _unknown_fact(number, fact, repo, "CI state is unknown")
    if str(fact.get("review_state") or "") not in _REVIEW_STATES:
        return _unknown_fact(number, fact, repo, "review state is unknown")
    if str(fact.get("pr_state") or "") not in _PR_STATES:
        return _unknown_fact(number, fact, repo, "PR state is unknown")
    merge_provenance = str(fact.get("merge_provenance") or "")
    if merge_provenance not in _MERGE_PROVENANCE:
        return _unknown_fact(number, fact, repo, "merge provenance is unknown")
    if fact["pr_state"] == "MERGED" and merge_provenance == "NONE":
        return _unknown_fact(number, fact, repo, "merged PR lacks merge provenance")
    if fact["pr_state"] != "MERGED" and merge_provenance != "NONE":
        return _unknown_fact(number, fact, repo, "open or closed PR claims merge provenance")
    if fact["pr_state"] == "MERGED" and merge_provenance == "NATIVE_QUEUE":
        merge_error = _validate_native_queue_merge_observation(number, fact)
        if merge_error is not None:
            return _unknown_fact(number, fact, repo, merge_error)
    elif fact.get("merge_observation") is not None:
        return _unknown_fact(number, fact, repo, "non-queue state claims a merge observation")
    mergeable = str(fact.get("mergeable") or "")
    if mergeable not in {"MERGEABLE", "CONFLICTING", "UNKNOWN"}:
        return _unknown_fact(number, fact, repo, "mergeability is unknown")
    queue_state = str(fact.get("queue_state") or "")
    if queue_state not in _QUEUE_STATES | {"NONE"}:
        return _unknown_fact(number, fact, repo, "native queue state is unknown")
    queue_provenance = str(fact.get("queue_entry_provenance") or "")
    if queue_provenance not in _QUEUE_ENTRY_PROVENANCE:
        return _unknown_fact(number, fact, repo, "queue entry provenance is unknown")
    if queue_state == "NONE" and queue_provenance != "NONE":
        return _unknown_fact(number, fact, repo, "absent queue entry claims provenance")
    if queue_state != "NONE" and queue_provenance == "NONE":
        return _unknown_fact(number, fact, repo, "live queue entry lacks provenance")
    queue_entry_id = fact.get("queue_entry_id")
    queue_entry_head = fact.get("queue_entry_head_sha")
    queue_entry_actor = str(fact.get("queue_entry_actor") or "").strip().lower()
    if queue_state == "NONE":
        if queue_entry_id is not None or queue_entry_head is not None or queue_entry_actor:
            return _unknown_fact(number, fact, repo, "absent queue entry claims identity")
    else:
        if not isinstance(queue_entry_id, str) or not queue_entry_id.strip():
            return _unknown_fact(number, fact, repo, "queue entry identity is unknown")
        if queue_entry_head != fact["head_sha"]:
            return _unknown_fact(number, fact, repo, "queue entry is stale-head evidence")
        if queue_provenance == "OPERATOR" and queue_entry_actor not in _TRUSTED_OPERATOR_ACTORS:
            return _unknown_fact(number, fact, repo, "queue entry operator actor is untrusted")
        if queue_provenance == "TRUSTED_LOOP":
            trusted_loop_actors = {
                str(actor).strip().lower()
                for actor in _TRUSTED_POLICY["authority_policy"].get(
                    "trusted_loop_actors", []
                )
            }
            if queue_entry_actor not in trusted_loop_actors:
                return _unknown_fact(number, fact, repo, "queue entry loop actor is untrusted")
    if operator_intent == "DEQUEUED" and queue_state != "NONE":
        return _unknown_fact(number, fact, repo, "dequeue intent conflicts with a live queue entry")
    for present_field, id_field, head_field in (
        ("ai_evidence", "ai_evidence_id", "ai_evidence_head_sha"),
        ("operator_warrant", "operator_warrant_id", "operator_warrant_head_sha"),
    ):
        present = fact[present_field]
        evidence_id = fact.get(id_field)
        evidence_head = fact.get(head_field)
        if present:
            if (
                not isinstance(evidence_id, int)
                or isinstance(evidence_id, bool)
                or evidence_id <= 0
            ):
                return _unknown_fact(number, fact, repo, f"{id_field} is unknown")
            if evidence_head != fact["head_sha"]:
                return _unknown_fact(number, fact, repo, f"{present_field} is stale-head evidence")
        elif evidence_id is not None or evidence_head is not None:
            return _unknown_fact(number, fact, repo, f"absent {present_field} claims evidence")
    ai_actor = str(fact.get("ai_evidence_actor") or "").strip().lower()
    ai_state = str(fact.get("ai_evidence_state") or "").upper()
    if fact["ai_evidence"]:
        if ai_actor not in _TRUSTED_AI_ACTORS or ai_state not in _AI_EVIDENCE_STATES:
            return _unknown_fact(number, fact, repo, "AI evidence actor or state is untrusted")
    elif ai_actor or ai_state:
        return _unknown_fact(number, fact, repo, "absent AI evidence claims actor state")
    warrant_actor = str(fact.get("operator_warrant_actor") or "").strip().lower()
    warrant_kind = str(fact.get("operator_warrant_kind") or "")
    warrant_state = str(fact.get("operator_warrant_state") or "").upper()
    if fact["operator_warrant"]:
        if (
            warrant_actor not in _TRUSTED_OPERATOR_ACTORS
            or warrant_kind != "github_review"
            or warrant_state != "APPROVED"
        ):
            return _unknown_fact(number, fact, repo, "operator warrant provenance is untrusted")
    elif warrant_actor or warrant_kind or warrant_state:
        return _unknown_fact(number, fact, repo, "absent operator warrant claims provenance")
    if fact["policy_gate_observed"]:
        check_id = fact.get("policy_gate_check_id")
        if not isinstance(check_id, int) or isinstance(check_id, bool) or check_id <= 0:
            return _unknown_fact(number, fact, repo, "policy gate check identity is unknown")
        if fact.get("policy_gate_head_sha") != fact["head_sha"]:
            return _unknown_fact(number, fact, repo, "policy gate is stale-head evidence")
        if fact.get("policy_gate_base_sha") != fact["base_sha"]:
            return _unknown_fact(number, fact, repo, "policy gate is stale-base evidence")
        if fact.get("policy_gate_app_id") != _GITHUB_ACTIONS_APP_ID:
            return _unknown_fact(number, fact, repo, "policy gate publisher App is untrusted")
    elif (
        fact["policy_gate_passed"]
        or fact.get("policy_gate_check_id") is not None
        or fact.get("policy_gate_head_sha") is not None
        or fact.get("policy_gate_base_sha") is not None
        or fact.get("policy_gate_app_id") is not None
    ):
        return _unknown_fact(number, fact, repo, "absent policy gate claims evidence")
    for name in ("unresolved_threads", "repair_attempts", "behind_by"):
        value = fact.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return _unknown_fact(number, fact, repo, f"{name} is unknown")
    return None


def _classify_action(
    number: int,
    fact: Mapping[str, Any],
    *,
    repo: str,
    ambiguous: bool,
    dependent: bool,
    changed_paths: list[str],
    owned_surfaces_complete: bool,
) -> dict[str, Any]:
    invalid = _validate_fact(number, fact, repo, changed_paths)
    if invalid is not None:
        return invalid

    if not fact["head_observed_current"]:
        return _unknown_fact(number, fact, repo, "head moved after the snapshot")
    if fact["pr_state"] == "MERGED":
        if fact["merge_provenance"] != "NATIVE_QUEUE":
            return _item(
                number,
                fact,
                action=HUMAN_EXCEPTION,
                reason_code="MERGED_OUTSIDE_NATIVE_QUEUE",
                explanation="merged state bypassed or cannot prove the native queue boundary",
                repo=repo,
                terminal_for_head=True,
            )
        return _item(
            number,
            fact,
            action=MERGED,
            reason_code="MERGED_BY_NATIVE_QUEUE",
            explanation="GitHub records this exact-head convergence lane as merged",
            repo=repo,
            terminal_for_head=True,
            terminal_key={
                "head_sha": fact["head_sha"],
                "merge_observation_digest": fact["merge_observation"]["digest"],
            },
        )
    if fact["pr_state"] == "CLOSED":
        return _item(
            number,
            fact,
            action=WAIT,
            reason_code="PR_CLOSED",
            explanation="GitHub reports the PR closed; no queue action is available",
            repo=repo,
            terminal_for_head=False,
        )
    if fact["operator_queue_intent"] == "DEQUEUED":
        return _item(
            number,
            fact,
            action=OPERATOR_CANCELLED,
            reason_code="CANCELLED_BY_OPERATOR",
            explanation="manual dequeue is a terminal operator decision for this exact head",
            repo=repo,
            terminal_for_head=False,
            terminal_key={
                "head_sha": fact["head_sha"],
                "queue_intent_event_id": fact["operator_queue_intent_event_id"],
            },
        )
    if fact["is_draft"]:
        return _item(
            number, fact, action=WAIT, reason_code="DRAFT",
            explanation="draft PRs are not convergence candidates", repo=repo,
        )
    if fact["queue_state"] in _QUEUE_STATES:
        if (
            fact["queue_entry_provenance"] == "TRUSTED_LOOP"
            and (fact["policy_class"] == "operator_only" or fact["risk"] in {"HIGH", "CRITICAL"})
        ):
            return _item(
                number,
                fact,
                action=HUMAN_EXCEPTION,
                reason_code="UNAUTHORIZED_QUEUE_ENTRY",
                explanation="trusted automation may not enqueue an operator-only change",
                repo=repo,
                terminal_for_head=True,
            )
        return _item(
            number, fact, action=WAIT, reason_code="IN_NATIVE_QUEUE",
            explanation="native merge queue owns integration and final checks", repo=repo,
            terminal_for_head=True,
        )
    if ambiguous:
        return _item(
            number, fact, action=HUMAN_EXCEPTION, reason_code="AMBIGUOUS_OVERLAP",
            explanation="shared hand-edited surface has no deterministic canonical lane",
            repo=repo, terminal_for_head=True,
        )
    if dependent:
        return _item(
            number, fact, action=WAIT, reason_code="DEPENDENT_SURFACE",
            explanation="wait behind the elected canonical PR for the shared surface", repo=repo,
        )
    if fact["is_cross_repository"]:
        return _item(
            number, fact, action=HUMAN_EXCEPTION, reason_code="FORK",
            explanation="the bounded writer never mutates a fork", repo=repo,
            terminal_for_head=True,
        )
    if fact["mergeable"] != "MERGEABLE":
        return _item(
            number, fact, action=HUMAN_EXCEPTION, reason_code="MERGE_CONFLICT",
            explanation="conflict or unknown mergeability requires operator handling", repo=repo,
            terminal_for_head=True,
        )
    if fact["policy_class"] == "operator_only" or fact["risk"] in {"HIGH", "CRITICAL"}:
        return _item(
            number, fact, action=HUMAN_EXCEPTION, reason_code="OPERATOR_ONLY",
            explanation="high-risk and operator-only changes are outside unattended authority",
            repo=repo, terminal_for_head=True,
        )
    if fact["review_state"] == "changes_requested":
        return _item(
            number, fact, action=HUMAN_EXCEPTION, reason_code="CHANGES_REQUESTED",
            explanation="a state-bearing review blocks automation", repo=repo,
            terminal_for_head=True,
        )
    if fact["review_state"] == "unknown":
        return _unknown_fact(number, fact, repo, "review state read failed")
    if not fact["base_observed_current"]:
        return _unknown_fact(number, fact, repo, "target base moved after the snapshot")
    if fact["unresolved_threads"] and fact["repairable_threads"]:
        if fact["repair_attempts"] >= 2:
            return _item(
                number, fact, action=HUMAN_EXCEPTION, reason_code="ATTEMPTS_EXHAUSTED",
                explanation="two bounded review-feedback repairs failed for this exact head",
                repo=repo, terminal_for_head=True,
            )
        return _item(
            number, fact, action=REPAIR_CODE, reason_code="REVIEW_FEEDBACK_REPAIR",
            explanation="prepare a bounded patch; the planner cannot resolve the thread",
            repo=repo,
        )
    if fact["unresolved_threads"]:
        return _item(
            number, fact, action=HUMAN_EXCEPTION, reason_code="UNRESOLVED_THREADS",
            explanation="substantive review threads require an authorized resolution",
            repo=repo, terminal_for_head=True,
        )

    ci_state = fact["ci_state"]
    if ci_state == "pending":
        return _item(
            number, fact, action=WAIT, reason_code="CI_PENDING",
            explanation="wait for the current exact-head checks", repo=repo,
        )
    if ci_state == "transient":
        if fact["repair_attempts"] >= 2:
            return _item(
                number, fact, action=HUMAN_EXCEPTION, reason_code="ATTEMPTS_EXHAUSTED",
                explanation="two bounded attempts failed for this exact head", repo=repo,
                terminal_for_head=True,
            )
        return _item(
            number, fact, action=RERUN_TRANSIENT, reason_code="TRANSIENT_CI",
            explanation=(
                f"run bounded retry {fact['repair_attempts'] + 1} of 2 for this exact head"
            ),
            repo=repo,
        )
    if ci_state == "missing":
        if not fact["is_cross_repository"] and fact["behind_by"] > 0:
            if fact["repair_attempts"] >= 1:
                return _item(
                    number,
                    fact,
                    action=HUMAN_EXCEPTION,
                    reason_code="REFRESH_ATTEMPT_EXHAUSTED",
                    explanation="one safe refresh attempt failed to create CI",
                    repo=repo,
                    terminal_for_head=True,
                )
            return _item(
                number, fact, action=REFRESH_STRANDED, reason_code="CI_STRANDED",
                explanation="safe exact-head refresh may create the missing CI event", repo=repo,
            )
        return _item(
            number, fact, action=HUMAN_EXCEPTION, reason_code="CI_NEVER_RAN",
            explanation="checkless current-base PR needs an explicit trusted trigger decision",
            repo=repo, terminal_for_head=True,
        )
    if ci_state == "failed":
        if fact["repair_attempts"] >= 2:
            return _item(
                number, fact, action=HUMAN_EXCEPTION, reason_code="ATTEMPTS_EXHAUSTED",
                explanation="two bounded repair attempts failed for this exact head", repo=repo,
                terminal_for_head=True,
            )
        return _item(
            number, fact, action=REPAIR_CODE, reason_code="REAL_TEST_OR_LINT_FAILURE",
            explanation="prepare and verify a bounded exact-head patch", repo=repo,
        )
    if ci_state == "unknown":
        return _unknown_fact(number, fact, repo, "CI read failed")

    if not fact["ai_evidence"]:
        return _item(
            number, fact, action=REQUEST_REVIEW, reason_code="AI_EVIDENCE_REQUIRED",
            explanation="request current-head trusted AI review evidence", repo=repo,
        )
    if not fact["policy_gate_observed"] or not fact["policy_gate_passed"]:
        return _item(
            number, fact, action=HUMAN_EXCEPTION, reason_code="POLICY_GATE_UNPROVEN",
            explanation="trusted current-head unattended policy evaluation is absent or red",
            repo=repo, terminal_for_head=True,
        )
    if fact["policy_class"] == "code" and not fact["operator_warrant"]:
        return _item(
            number, fact, action=HUMAN_EXCEPTION, reason_code="OPERATOR_WARRANT_REQUIRED",
            explanation="code requires an exact-head operator warrant", repo=repo,
            terminal_for_head=True,
        )
    if not owned_surfaces_complete:
        return _unknown_fact(number, fact, repo, "owned-surface collision scan is incomplete")

    policy_digest = str(fact.get("policy_digest") or "")
    gate_fingerprint = str(fact.get("gate_fingerprint") or "")
    if not _HEX_64.fullmatch(policy_digest) or not _HEX_64.fullmatch(gate_fingerprint):
        return _unknown_fact(number, fact, repo, "queue evidence binding is incomplete")
    authorization_evidence, evidence_error = _validate_queue_authorization_report(
        number, fact, repo
    )
    if evidence_error is not None or authorization_evidence is None:
        return _unknown_fact(number, fact, repo, evidence_error or "authorization evidence is invalid")
    candidate = {
        "schema": "dharma.pr_convergence.queue_candidate.v1",
        "repo": repo,
        "number": number,
        "head_sha": fact["head_sha"],
        "base_sha": fact["base_sha"],
        "policy_digest": policy_digest,
        "gate_fingerprint": gate_fingerprint,
        "authorization_evidence_digest": authorization_evidence["digest"],
        "owned_surfaces_digest": TRUSTED_OWNED_SURFACES_DIGEST,
        "ai_evidence_id": fact["ai_evidence_id"],
        "ai_evidence_actor": fact["ai_evidence_actor"],
        "operator_warrant_id": fact.get("operator_warrant_id"),
        "operator_warrant_actor": fact.get("operator_warrant_actor"),
        "effect": "request_native_queue_admission_after_live_revalidation",
        "not_a_merge_permit": True,
    }
    return _item(
        number, fact, action=QUEUE_CANDIDATE, reason_code="POLICY_GATES_SATISFIED",
        explanation="candidate may be revalidated for native-queue admission",
        repo=repo, queue_candidate=candidate,
    )


def plan_convergence_actions(
    open_prs: list[dict[str, Any]],
    pr_files: Mapping[int, list[str]],
    facts: Mapping[int, Mapping[str, Any]],
    *,
    repo: str,
    owned_surfaces=(),
    grades=None,
    max_operator_items: int = MAX_OPERATOR_INBOX,
    owned_surfaces_complete: bool = False,
) -> dict[str, Any]:
    """Pure exception-driven plan. It cannot construct merge authority."""
    if not _REPO.fullmatch(repo):
        raise ValueError("repo must be owner/name")
    if (
        not isinstance(max_operator_items, int)
        or isinstance(max_operator_items, bool)
        or max_operator_items < 0
        or max_operator_items > MAX_OPERATOR_INBOX
    ):
        raise ValueError(f"max_operator_items must be an integer from 0 to {MAX_OPERATOR_INBOX}")
    effective_owned_surfaces = tuple(
        sorted(set(TRUSTED_OWNED_SURFACES) | set(owned_surfaces))
    )
    collision_excluded = set()
    pr_rows = {row.get("number"): row for row in open_prs if isinstance(row, Mapping)}
    for number, row in pr_rows.items():
        fact = facts.get(number)
        paths = pr_files.get(number)
        if (
            isinstance(number, int)
            and isinstance(fact, Mapping)
            and isinstance(paths, list)
            and paths
            and all(isinstance(path, str) and path for path in paths)
            and isinstance(fact.get("is_draft"), bool)
            and row.get("isDraft") == fact["is_draft"]
            and _validate_fact(number, fact, repo, paths) is None
            and fact["head_observed_current"]
            and (
                fact["pr_state"] in {"MERGED", "CLOSED"}
                or fact["operator_queue_intent"] == "DEQUEUED"
            )
        ):
            collision_excluded.add(number)
    order = compute_convergence_order(
        open_prs,
        pr_files,
        effective_owned_surfaces,
        grades,
        collision_excluded=collision_excluded,
    )
    ambiguous = set(order["escalate"])
    dependent = set(order["dependent"])
    items = []
    for number in order["order"]:
        fact = facts.get(number)
        if not isinstance(fact, Mapping):
            fact = {"number": number}
        paths = pr_files.get(number)
        if (
            not isinstance(paths, list)
            or not paths
            or not all(isinstance(path, str) and path for path in paths)
        ):
            items.append(_unknown_fact(number, fact, repo, "changed-file evidence is incomplete"))
            continue
        source_draft = pr_rows.get(number, {}).get("isDraft")
        if isinstance(fact.get("is_draft"), bool) and source_draft != fact["is_draft"]:
            items.append(_unknown_fact(number, fact, repo, "draft state sources disagree"))
            continue
        items.append(
            _classify_action(
                number,
                fact,
                repo=repo,
                ambiguous=number in ambiguous,
                dependent=number in dependent,
                changed_paths=paths,
                owned_surfaces_complete=owned_surfaces_complete,
            )
        )
    exceptions = [row for row in items if row["action"] == HUMAN_EXCEPTION]
    return {
        "schema": PLAN_SCHEMA,
        "repo": repo,
        "planner_authority": dict(_NO_AUTHORITY),
        "owned_surface_policy": {
            "source": str(_ACTIVE_TRACK_PATH.relative_to(REPO_ROOT)),
            "sha256": TRUSTED_OWNED_SURFACES_DIGEST,
            "surface_count": len(TRUSTED_OWNED_SURFACES),
        },
        "order": order,
        "items": items,
        "operator_inbox": exceptions[:max_operator_items],
        "operator_inbox_overflow": max(0, len(exceptions) - max_operator_items),
    }


def plan_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build a plan from a JSON-compatible exact-head snapshot payload."""
    if not isinstance(payload, Mapping):
        raise ValueError("snapshot root must be an object")
    open_prs = payload.get("open_prs")
    pr_files_raw = payload.get("pr_files")
    facts_raw = payload.get("facts")
    if not isinstance(open_prs, list) or not all(isinstance(row, dict) for row in open_prs):
        raise ValueError("open_prs must be a list of objects")
    if not isinstance(pr_files_raw, dict) or not isinstance(facts_raw, dict):
        raise ValueError("pr_files and facts must be objects keyed by PR number")
    numbers = []
    for row in open_prs:
        number = row.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
            raise ValueError("every open_prs row must have a positive integer number")
        if not isinstance(row.get("isDraft"), bool):
            raise ValueError("every open_prs row must have a boolean isDraft")
        numbers.append(number)
    if len(numbers) != len(set(numbers)):
        raise ValueError("open_prs contains duplicate PR numbers")

    def normalize_keys(raw: Mapping[str, Any], name: str) -> dict[int, Any]:
        normalized = {}
        for key, value in raw.items():
            key_text = str(key)
            if not key_text.isascii() or not key_text.isdigit() or str(int(key_text)) != key_text:
                raise ValueError(f"{name} keys must be canonical positive PR numbers")
            number = int(key_text)
            if number <= 0 or number in normalized:
                raise ValueError(f"{name} keys must be unique positive PR numbers")
            normalized[number] = value
        return normalized

    pr_files_normalized = normalize_keys(pr_files_raw, "pr_files")
    facts_normalized = normalize_keys(facts_raw, "facts")
    expected_numbers = set(numbers)
    if set(pr_files_normalized) != expected_numbers or set(facts_normalized) != expected_numbers:
        raise ValueError("pr_files and facts must exactly cover open_prs")
    if not all(
        isinstance(value, list) and all(isinstance(path, str) for path in value)
        for value in pr_files_normalized.values()
    ):
        raise ValueError("pr_files values must be lists of paths")
    if not all(isinstance(value, Mapping) for value in facts_normalized.values()):
        raise ValueError("facts values must be objects")
    pr_files = {key: list(value) for key, value in pr_files_normalized.items()}
    facts = dict(facts_normalized)
    grades_raw = payload.get("grades") or {}
    if not isinstance(grades_raw, dict):
        raise ValueError("grades must be an object keyed by PR number")
    grades = normalize_keys(grades_raw, "grades")
    if not set(grades).issubset(expected_numbers):
        raise ValueError("grades contains a PR outside open_prs")
    if not all(
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= 8
        for value in grades.values()
    ):
        raise ValueError("grades values must be integers from 0 to 8")
    owned_surfaces = payload.get("owned_surfaces") or ()
    if not isinstance(owned_surfaces, (list, tuple)) or not all(
        isinstance(surface, str) for surface in owned_surfaces
    ):
        raise ValueError("owned_surfaces must be a list of globs")
    owned_surfaces_complete = payload.get("owned_surfaces_complete")
    if not isinstance(owned_surfaces_complete, bool):
        raise ValueError("owned_surfaces_complete must be a boolean")
    max_operator_items = payload.get("max_operator_items", MAX_OPERATOR_INBOX)
    if not isinstance(max_operator_items, int) or isinstance(max_operator_items, bool):
        raise ValueError("max_operator_items must be an integer")
    return plan_convergence_actions(
        open_prs,
        pr_files,
        facts,
        repo=str(payload.get("repo") or ""),
        owned_surfaces=owned_surfaces,
        grades=grades,
        max_operator_items=max_operator_items,
        owned_surfaces_complete=owned_surfaces_complete,
    )


def _fetch_live(limit: int) -> dict:
    """ADVISORY live run: reuse the existing owners for reads; never mutate."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))  # repo-root only — never shadow bare names
    from scripts.runtime.pr_merge_control import fetch_open_prs, fetch_pr_files  # noqa: E402
    from scripts.governance.check_track_status import (  # noqa: E402
        ACTIVE_TRACK_PATH, load_active_track, normalize_portfolio,
    )
    repo = "AIKAGRYA/dharma_swarm"
    prs = fetch_open_prs(limit)
    pr_files = {p["number"]: [f["path"] for f in fetch_pr_files(p["number"], repo)] for p in prs}
    portfolio = normalize_portfolio(load_active_track(ACTIVE_TRACK_PATH))
    owned = [s for t in portfolio.get("active_tracks", []) for s in (t.get("owned_surfaces") or [])]
    return compute_convergence_order(prs, pr_files, owned_surfaces=owned)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument(
        "--snapshot-json",
        type=Path,
        help="plan from an exact-head JSON snapshot instead of querying GitHub",
    )
    args = ap.parse_args(argv)
    if args.snapshot_json:
        with args.snapshot_json.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        result = plan_from_payload(payload)
    else:
        result = _fetch_live(args.limit)
    print(json.dumps(result, indent=2))
    escalations = result.get("operator_inbox") or result.get("escalate") or []
    if escalations:
        print(f"\nescalate to operator: {escalations}", file=sys.stderr)
    return 0  # advisory — always exits 0


if __name__ == "__main__":
    raise SystemExit(main())
