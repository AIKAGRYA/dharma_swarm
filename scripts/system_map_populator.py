#!/usr/bin/env python3
"""Populate a read-only system map from operating facts and audit markdown.

The populator reads existing facts and audit reports, then writes one derived
JSON artifact. It does not mutate source code, cron config, ontology, or logs.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AUDIT_DIR = Path.home() / ".dharma" / "audit"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "system_map" / "latest.json"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.operator_core.operating_facts import (  # noqa: E402
    OperatingFactInputs,
    OrganStateFact,
    build_operating_fact_bundle,
    organ_state_facts,
)


AUDIT_ORGANS = (
    {
        "name": "metabolic_clock",
        "owns": "scheduled metabolic jobs and launchd clock attachment",
        "patterns": ("cron", "LaunchAgent", "jobs.json", "metabolic clock"),
        "open_gap": "scheduler truth is split unless launchd target, dgc verbs, and jobs.json agree",
        "next": "bind one canonical clock doc to live jobs.json and installed dgc command surface",
        "risk": "high",
    },
    {
        "name": "algedonic_stream",
        "owns": "pain/urgency signals from omega divergence and related alarms",
        "patterns": ("algedonic", "omega_divergence", "divergence"),
        "open_gap": "stream values can be present without proving the consumer loop is causal",
        "next": "show which runtime path consumes the latest algedonic value",
        "risk": "medium",
    },
    {
        "name": "onboarding_spine",
        "owns": "cold-start reading order and megafile map",
        "patterns": ("megafile", "onboarding", "CLAUDE.md", "reading order"),
        "open_gap": "onboarding files can exist without becoming the path an agent actually follows",
        "next": "keep the megafile survey tied to the first file an agent loads",
        "risk": "medium",
    },
    {
        "name": "truth_spine",
        "owns": "declared-vs-actual operating fact projection",
        "patterns": ("truth spine", "declared-vs-actual", "operating facts", "OrganState"),
        "open_gap": "declared organs remain advisory until observed facts are loaded",
        "next": "load current organ facts into reports/system_map/latest.json",
        "risk": "medium",
    },
    {
        "name": "central_loop",
        "owns": "proposal to execution to value feedback loop",
        "patterns": ("central loop", "proposal", "execution", "value event", "Contribution"),
        "open_gap": "loop edges can be documented without a complete observed chain",
        "next": "prove one proposal-to-value chain with file evidence",
        "risk": "high",
    },
    {
        "name": "self_evolution",
        "owns": "Darwin/Shakti/self-modification trace and selection memory",
        "patterns": ("self_evolution", "Darwin", "Shakti", "evolution.py", "self evolution"),
        "open_gap": "evolutionary machinery can generate volume without a compact rollup",
        "next": "summarize latest accepted/rejected changes as operating facts",
        "risk": "high",
    },
    {
        "name": "recognition_seed",
        "owns": "recognition-mediated self-model and attractor closure evidence",
        "patterns": ("recognition", "self-model", "attractor", "Attractor Closure"),
        "open_gap": "recognition is not causal until map changes alter routing or gates",
        "next": "trace one recognized drift into a runtime decision",
        "risk": "high",
    },
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Populate reports/system_map/latest.json")
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json", action="store_true", help="also print the generated payload")
    args = parser.parse_args(argv)

    payload = build_system_map(
        repo_root=args.repo_root.expanduser().resolve(),
        audit_dir=args.audit_dir.expanduser(),
    )
    output = args.output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Wrote {output} with {len(payload['organs'])} organ(s)")
    return 0


def build_system_map(*, repo_root: Path = REPO_ROOT, audit_dir: Path = DEFAULT_AUDIT_DIR) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    audit_sources = list(_audit_sources(audit_dir))
    operating_facts = list(_operating_fact_organs(repo_root))
    audit_facts = list(_audit_fact_organs(audit_sources, now))
    organs = _merge_organs(operating_facts + audit_facts)
    return {
        "schema_version": "system_map.v0",
        "generated_at": now,
        "sources": [source.as_posix() for source in audit_sources],
        "organs": [asdict(organ) for organ in sorted(organs, key=lambda item: item.name)],
    }


def _audit_sources(audit_dir: Path) -> Iterable[Path]:
    if not audit_dir.exists():
        return ()
    return tuple(sorted(path for path in audit_dir.glob("*.md") if path.is_file()))


def _operating_fact_organs(repo_root: Path) -> tuple[OrganStateFact, ...]:
    reports_dir = repo_root / "reports"
    bundle = build_operating_fact_bundle(
        OperatingFactInputs(
            agentops_reports_dir=reports_dir / "agentops",
            kaizen_reports_dir=reports_dir / "kaizen",
            yds_ratings_path=Path.home() / ".dharma" / "human_yds_ratings.jsonl",
            burn_report_path=Path.home() / ".dharma" / "audit" / "burn_report_latest.jsonl",
            revenue_notes_path=Path.home() / ".dharma" / "audit" / "revenue_notes.md",
        )
    )
    return organ_state_facts(bundle)


def _audit_fact_organs(sources: Iterable[Path], observed_at: str) -> tuple[OrganStateFact, ...]:
    facts: list[OrganStateFact] = []
    indexed_sources = tuple((source, _read_lines(source)) for source in sources)
    for spec in AUDIT_ORGANS:
        refs = _matching_refs(indexed_sources, spec["patterns"])
        coherence = _coherence_state(refs)
        observed = "audit evidence found" if refs else "UNKNOWN: no matching audit evidence found"
        facts.append(
            OrganStateFact(
                name=str(spec["name"]),
                owns=str(spec["owns"]),
                declared_state=f"owns {spec['owns']}",
                observed_state=observed,
                coherence_state=coherence,
                evidence_refs=tuple(refs[:12]),
                open_gap=str(spec["open_gap"]) if refs else "UNKNOWN: no audit source mentioned this organ",
                next_packet_hint=str(spec["next"]),
                declared_primitive=str(spec["owns"]),
                actual_runtime_primitive=observed,
                source_stores=tuple(ref.split(":", 1)[0] for ref in refs[:4]),
                sink_stores=("reports/system_map/latest.json",),
                gates_declared=(),
                gates_enforced=(),
                witness_writes=("reports/system_map/latest.json",),
                scheduled="UNKNOWN",
                merged_to_main="UNKNOWN",
                last_observed=observed_at,
                drift=str(spec["open_gap"]) if refs else "UNKNOWN",
                next_bindable_gap=str(spec["next"]),
                risk=str(spec["risk"]),
            )
        )
    return tuple(facts)


def _read_lines(path: Path) -> tuple[str, ...]:
    try:
        return tuple(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return ()


def _matching_refs(indexed_sources: Iterable[tuple[Path, tuple[str, ...]]], patterns: object) -> list[str]:
    lowered_patterns = tuple(str(pattern).lower() for pattern in patterns if str(pattern).strip())
    refs: list[str] = []
    for path, lines in indexed_sources:
        for line_no, line in enumerate(lines, start=1):
            lower = line.lower()
            if any(pattern in lower for pattern in lowered_patterns):
                refs.append(f"{path.as_posix()}:{line_no}")
                if len(refs) >= 24:
                    return refs
    return refs


def _coherence_state(refs: list[str]) -> str:
    if not refs:
        return "unknown"
    if len(refs) == 1:
        return "declared_only"
    return "partial"


def _merge_organs(facts: Iterable[OrganStateFact]) -> tuple[OrganStateFact, ...]:
    by_name: dict[str, OrganStateFact] = {}
    for fact in facts:
        if fact.name not in by_name:
            by_name[fact.name] = fact
            continue
        prior = by_name[fact.name]
        refs = tuple(dict.fromkeys((*prior.evidence_refs, *fact.evidence_refs)))
        by_name[fact.name] = OrganStateFact(
            name=fact.name,
            owns=fact.owns or prior.owns,
            declared_state=fact.declared_state or prior.declared_state,
            observed_state=fact.observed_state or prior.observed_state,
            coherence_state=_stronger_state(prior.coherence_state, fact.coherence_state),
            evidence_refs=refs,
            open_gap=fact.open_gap or prior.open_gap,
            next_packet_hint=fact.next_packet_hint or prior.next_packet_hint,
            declared_primitive=fact.declared_primitive or prior.declared_primitive,
            actual_runtime_primitive=fact.actual_runtime_primitive or prior.actual_runtime_primitive,
            source_stores=tuple(dict.fromkeys((*prior.source_stores, *fact.source_stores))),
            sink_stores=tuple(dict.fromkeys((*prior.sink_stores, *fact.sink_stores))),
            gates_declared=tuple(dict.fromkeys((*prior.gates_declared, *fact.gates_declared))),
            gates_enforced=tuple(dict.fromkeys((*prior.gates_enforced, *fact.gates_enforced))),
            witness_writes=tuple(dict.fromkeys((*prior.witness_writes, *fact.witness_writes))),
            scheduled=fact.scheduled if fact.scheduled != "UNKNOWN" else prior.scheduled,
            merged_to_main=fact.merged_to_main if fact.merged_to_main != "UNKNOWN" else prior.merged_to_main,
            last_observed=fact.last_observed or prior.last_observed,
            drift=fact.drift or prior.drift,
            next_bindable_gap=fact.next_bindable_gap or prior.next_bindable_gap,
            risk=fact.risk if fact.risk != "UNKNOWN" else prior.risk,
        )
    return tuple(by_name.values())


def _stronger_state(left: str, right: str) -> str:
    rank = {"drifted": 4, "partial": 3, "declared_only": 2, "unknown": 1, "bound": 0}
    return left if rank.get(left, 0) >= rank.get(right, 0) else right


if __name__ == "__main__":
    raise SystemExit(main())
