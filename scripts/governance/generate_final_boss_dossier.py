#!/usr/bin/env python3
"""Generate an Active Track Final Boss dossier and adversarial review prompt."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import check_track_status as track_status  # type: ignore  # noqa: E402


REQUIRED_DIMENSIONS = sorted(track_status.FINAL_BOSS_DIMENSIONS)

PROFILE_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "agent_identity": {
        "required_evidence_themes": [
            "identity and passport provenance are traceable",
            "execution lease or authority boundary is enforced before side effects",
            "heartbeat/witness freshness is checked where liveness is claimed",
            "spoofing or stale identity replay is explicitly rejected",
        ],
        "hard_rejects": [
            "an agent can act without a current identity/lease proof",
            "passports, docks, or wake receipts are treated as authority without freshness checks",
            "identity claims are copied from prose instead of verified artifacts",
        ],
    },
    "filesystem_substrate": {
        "required_evidence_themes": [
            "folder contracts and schema rules are executable",
            "organizer operations are idempotent and non-destructive by default",
            "path traversal, symlink, and cross-root mutation risks are handled",
            "portable knowledge graph projections preserve provenance",
        ],
        "hard_rejects": [
            "filesystem mutation can delete, move, or rewrite user data without a bounded plan",
            "folder-as-contract rules are documented but not enforced",
            "semantic organization tests only prove happy-path examples",
            "path traversal or symlink behavior is untested for substrate claims",
        ],
    },
    "generic": {
        "required_evidence_themes": [
            "claim boundary is explicit and not over-broadened",
            "local executable evidence covers the closure claim",
            "reviewer disagreement is resolved rather than averaged away",
        ],
        "hard_rejects": [
            "confidence language replaces executable evidence",
            "local tests do not cover the claim boundary",
            "generated docs or governance reports are stale",
            "reviewer disagreement is left unresolved",
        ],
    },
    "governance_gate": {
        "required_evidence_themes": [
            "negative tests prove false-green claims are blocked",
            "generated reports are deterministic and synchronized",
            "bypass, downgrade, and stale-evidence paths are covered",
            "schema, checker, docs, and operator workflow agree",
        ],
        "hard_rejects": [
            "a weaker evidence kind can satisfy a stronger closure claim",
            "generated reports can go stale without failing a check",
            "the gate accepts model consensus without executable local verification",
            "negative fixtures are absent for the named anti-slop failure mode",
        ],
    },
    "holon_bridge": {
        "required_evidence_themes": [
            "wake receipts and living-agent state are fresh where claimed",
            "read-only versus execution-lease authority is enforced",
            "identity lineage is recorded without inheriting unproven capability",
            "command receipts are projections over existing receipt owners",
        ],
        "hard_rejects": [
            "the track claims autonomous operation from a one-shot wake proof",
            "read-only holon state can mutate protected work without a lease",
            "lineage or persona claims substitute for current executable proof",
        ],
    },
    "orchestration": {
        "required_evidence_themes": [
            "dispatch, retry, cancellation, and timeout behavior are explicit",
            "duplicate work and partial failure are idempotent or safely rejected",
            "observability and rollback paths exist for failed orchestration",
            "scheduler claims are backed by live or hermetic executable evidence",
        ],
        "hard_rejects": [
            "scheduler success can be recorded while work silently fails",
            "duplicate dispatch can double-apply side effects",
            "orchestration state is split across hidden or unreceipted owners",
            "fitness or arena claims are based only on file presence",
        ],
    },
    "provider_routing": {
        "required_evidence_themes": [
            "explicit provider/model requests override ranked defaults",
            "fallback order is deterministic and documented",
            "credential absence, provider outage, and model unavailability are safe",
            "cost/power policy is transparent and test-backed",
        ],
        "hard_rejects": [
            "explicit model/provider selection is treated as a soft hint",
            "provider fallback can silently route to an unintended model",
            "routing tests depend on live credentials without a hermetic contract",
            "provider keys or secrets can leak through prompts, receipts, or logs",
        ],
    },
    "research_depth": {
        "required_evidence_themes": [
            "source provenance and citation quality are inspectable",
            "claims are reproducible from saved artifacts",
            "speculative synthesis is marked separately from verified evidence",
            "research output changes downstream system behavior or decisions",
        ],
        "hard_rejects": [
            "citation volume is treated as truth without source verification",
            "unverified synthesis is promoted into substrate doctrine",
            "research artifacts are not reproducible from local files or receipts",
        ],
    },
    "revenue_external": {
        "required_evidence_themes": [
            "external human action or value delivery is receipted",
            "privacy, consent, payment, and legal boundaries are explicit",
            "financial claims separate gross, net, realized, and projected value",
            "operator authority and outreach permissions are verified",
        ],
        "hard_rejects": [
            "internal activity is counted as external human value",
            "revenue claims lack durable receipts or conflate projections with realized value",
            "outreach, payments, or personal data can move without explicit authority",
        ],
    },
    "runtime_transport": {
        "required_evidence_themes": [
            "real broker behavior is exercised or the claim is explicitly not production-live",
            "ack/nack, retry, duplicate publish, and handler failure semantics are protected",
            "execution identity and receipt durability precede side-effect claims",
        ],
        "required_failure_modes": sorted(track_status.RUNTIME_TRANSPORT_FAILURE_MODES),
        "hard_rejects": [
            "mock-only or fake-only evidence for a production/substrate transport claim",
            "ack/nack behavior can lie about handler success or broker outcome",
            "duplicate publish or retry can double-dispatch work",
            "execution identity can be absent before side effects",
            "receipts can be emitted without durable side-effect truth",
            "real broker, reconnect, degradation, or cross-host behavior is unproven while claiming substrate trust",
        ],
    },
    "runtime_truth": {
        "required_evidence_themes": [
            "truth projections read from authoritative owners only",
            "cache/read-model staleness is visible and bounded",
            "receipt identity, completion state, authority, and runtime readiness are separated",
            "no new truth store or authority surface is introduced by the projection",
        ],
        "hard_rejects": [
            "read models become authority or mutate source-of-truth state",
            "stale projections can be mistaken for live runtime truth",
            "receipts can be duplicated or reinterpreted outside their owner boundary",
        ],
    },
    "truth_graph": {
        "required_evidence_themes": [
            "graph edges resolve to declared owners and artifacts",
            "provenance/custody survives projection and regeneration",
            "query or context artifacts are deterministic from source inputs",
            "A2A presence claims are receipt-backed and freshness-bounded",
        ],
        "hard_rejects": [
            "the graph creates a second source of truth instead of projecting existing owners",
            "unresolved or stale edges are accepted as substrate context",
            "presence/liveness claims lack fresh receipts",
        ],
    },
}


def _safe_token(value: object) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip()).strip(".-")
    return token or "track"


def _run_git(args: list[str]) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"{type(exc).__name__}: {exc}"
    out = (proc.stdout or proc.stderr or "").strip()
    return out


def _load_portfolio() -> dict[str, Any]:
    raw = track_status.load_active_track(track_status.ACTIVE_TRACK_PATH)
    return track_status.normalize_portfolio(raw)


def _find_track(track_id: str) -> tuple[dict[str, Any], str]:
    portfolio = _load_portfolio()
    for section in ("active_tracks", "closed_tracks"):
        for track in portfolio.get(section) or []:
            if isinstance(track, dict) and track.get("id") == track_id:
                return track, section
    raise SystemExit(f"track id not found in ACTIVE_TRACK.yaml: {track_id}")


def _path_exists(path: str) -> bool:
    return track_status.repo_path(path).exists()


def _extract_paths(value: object) -> set[str]:
    text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    return set(re.findall(r"[\w./-]+\.(?:py|md|json|yaml|yml|txt|sh)", text))


def _candidate_evidence_files(track: dict[str, Any]) -> list[str]:
    paths = {
        "docs/governance/ACTIVE_TRACK.yaml",
        "reports/governance/active_track_evidence.json",
        "reports/governance/active_track_evidence.md",
        "reports/governance/track_portfolio.json",
        "docs/governance/ACTIVE_TRACK_FINAL_BOSS.md",
    }
    for item in track.get("evidence") or []:
        paths.update(_extract_paths(item))
    for criterion in (track.get("prerequisites") or []) + (track.get("completion_criteria") or []):
        if not isinstance(criterion, dict):
            continue
        for key in ("file", "test"):
            raw = criterion.get(key)
            if not raw:
                continue
            path = str(raw).split("::", 1)[0]
            paths.add(path)
    for surface in track.get("owned_surfaces") or []:
        surface = str(surface)
        if "*" not in surface:
            paths.add(surface)
    return sorted(p for p in paths if _path_exists(p))


def _local_verifiers(track: dict[str, Any]) -> list[dict[str, Any]]:
    verifiers = [
        {
            "id": "track_status",
            "command": f"{sys.executable} scripts/governance/check_track_status.py",
            "purpose": "portfolio, closure-kind, and active-track gate",
        },
        {
            "id": "rendered_includes",
            "command": f"{sys.executable} scripts/governance/render_active_track_includes.py --check",
            "purpose": "generated active-track include blocks remain in sync",
        },
    ]
    seen: set[str] = set()
    for criterion in (track.get("prerequisites") or []) + (track.get("completion_criteria") or []):
        if not isinstance(criterion, dict) or criterion.get("kind") != "test_passes":
            continue
        target = str(criterion.get("test") or "").strip()
        if target and target not in seen:
            seen.add(target)
            verifiers.append({
                "id": f"pytest:{criterion.get('id') or _safe_token(target)}",
                "command": f"{sys.executable} -m pytest {target} -q",
                "purpose": "track-authored rigorous test evidence",
            })
    for path in sorted(_extract_paths(track.get("evidence") or [])):
        if path.startswith("tests/") and path.endswith(".py") and path not in seen:
            seen.add(path)
            verifiers.append({
                "id": f"pytest:{_safe_token(path)}",
                "command": f"{sys.executable} -m pytest {path} -q",
                "purpose": "closed-track cited rigorous test evidence",
            })
    return verifiers


def build_dossier(track_id: str, target_closure_kind: str) -> dict[str, Any]:
    track, section = _find_track(track_id)
    profile = track_status._graduation_profile(track)
    profile_requirements = PROFILE_REQUIREMENTS.get(profile, PROFILE_REQUIREMENTS["generic"])
    return {
        "schema_version": "dharma.active_track_final_boss.dossier.v1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "track_id": track_id,
        "track_name": track.get("name"),
        "track_section": section,
        "current_status": track.get("status"),
        "current_closure_kind": track.get("closure_kind"),
        "target_closure_kind": target_closure_kind,
        "graduation_profile": profile,
        "serves": track.get("serves"),
        "edges": {
            "complements": track.get("complements") or [],
            "depends_on": track.get("depends_on") or [],
            "conflicts_with": track.get("conflicts_with") or [],
        },
        "claim_boundary": (track.get("description") or track.get("notes") or "").strip(),
        "non_claims": track.get("non_goals") or [],
        "owned_surfaces": track.get("owned_surfaces") or [],
        "evidence": track.get("evidence") or [],
        "evidence_files": _candidate_evidence_files(track),
        "local_verifiers": _local_verifiers(track),
        "review_dimensions": REQUIRED_DIMENSIONS,
        "profile_requirements": profile_requirements,
        "hard_rejects": profile_requirements.get("hard_rejects", []),
        "git": {
            "status_short_branch": _run_git(["status", "--short", "--branch"]),
            "head": _run_git(["log", "--oneline", "--decorate", "-1"]),
        },
        "final_boss_rule": (
            "Score 100 only when every required dimension has concrete evidence, "
            "no explicit disagreement remains, and the requested closure kind is not overclaimed."
        ),
    }


def render_prompt(dossier: dict[str, Any]) -> str:
    track_id = dossier["track_id"]
    profile = dossier["graduation_profile"]
    target = dossier["target_closure_kind"]
    return f"""# Active Track Final Boss Review

You are reviewing `{track_id}` for `{target}` under graduation profile `{profile}`.

Treat this as the final irreversible active-track gate. If a weak track passes here,
future agents will treat it as substrate truth and the failure will compound. Do
not reward confidence language, clean YAML, or passing tests unless they actually
prove the requested closure kind.

Return JSON only. No markdown fences. No prose outside JSON.

Required dimensions:
{json.dumps(dossier["review_dimensions"], indent=2)}

Profile requirements:
{json.dumps(dossier["profile_requirements"], indent=2, sort_keys=True)}

Hard reject if any of these apply:
{json.dumps(dossier["hard_rejects"], indent=2)}

Evidence files to inspect:
{json.dumps(dossier["evidence_files"], indent=2)}

Local verifiers:
{json.dumps(dossier["local_verifiers"], indent=2)}

Dossier:
{json.dumps(dossier, indent=2, sort_keys=True)}

Return this JSON object:
{{
  "track_id": "{track_id}",
  "target_closure_kind": "{target}",
  "verdict": "pass|approve|revise|reject|blocked|insufficient_context",
  "score": 0,
  "score_label": "???/100",
  "one_sentence_verdict": "",
  "evidence_checked": [],
  "strongest_evidence": [],
  "weakest_evidence": [],
  "production_risks": [],
  "anti_slop_findings": [],
  "integration_quality_findings": [],
  "required_changes_before_graduation": [],
  "non_blocking_hardening": [],
  "explicit_disagreement": ""
}}
"""


def write_artifacts(dossier: dict[str, Any], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{_safe_token(dossier['track_id'])}-{_safe_token(dossier['target_closure_kind']).lower()}"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    prompt_path = out_dir / f"{stem}-prompt.md"
    json_path.write_text(json.dumps(dossier, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(dossier), encoding="utf-8")
    prompt_path.write_text(render_prompt(dossier), encoding="utf-8")
    return {
        "dossier_json": str(json_path),
        "dossier_markdown": str(md_path),
        "review_prompt": str(prompt_path),
    }


def render_markdown(dossier: dict[str, Any]) -> str:
    lines = [
        "# Active Track Final Boss Dossier",
        "",
        f"track_id: `{dossier['track_id']}`",
        f"target_closure_kind: `{dossier['target_closure_kind']}`",
        f"graduation_profile: `{dossier['graduation_profile']}`",
        f"current_status: `{dossier.get('current_status')}`",
        f"current_closure_kind: `{dossier.get('current_closure_kind')}`",
        "",
        "## Evidence Files",
        "",
    ]
    lines.extend(f"- `{path}`" for path in dossier["evidence_files"])
    lines.extend(["", "## Local Verifiers", ""])
    lines.extend(f"- `{row['command']}` - {row['purpose']}" for row in dossier["local_verifiers"])
    lines.extend(["", "## Hard Rejects", ""])
    lines.extend(f"- {item}" for item in dossier["hard_rejects"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track-id", required=True)
    parser.add_argument("--target-closure-kind", default="SUBSTRATE_TRUSTED")
    parser.add_argument("--out-dir", default=str(REPORT_DIR()))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    target = track_status._as_upper_token(args.target_closure_kind)
    dossier = build_dossier(args.track_id, target)
    paths = write_artifacts(dossier, Path(args.out_dir))
    if args.json:
        print(json.dumps(paths, indent=2, sort_keys=True))
    else:
        print(f"FINAL_BOSS_DOSSIER {paths['dossier_markdown']}")
        print(f"prompt: {paths['review_prompt']}")
    return 0


def REPORT_DIR() -> Path:
    return REPO_ROOT / "reports" / "governance" / "final_boss"


if __name__ == "__main__":
    raise SystemExit(main())
