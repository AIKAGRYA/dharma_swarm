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
DEFAULT_YDS_RATINGS = Path.home() / ".dharma" / "human_yds_ratings.jsonl"
DEFAULT_BURN_REPORT = Path.home() / ".dharma" / "audit" / "burn_report_latest.jsonl"
DEFAULT_REVENUE_NOTES = Path.home() / ".dharma" / "audit" / "revenue_notes.md"
DEFAULT_TELIC_ONTOLOGY_DB = Path.home() / ".dharma" / "ontology.db"

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
    parser.add_argument("--yds-ratings-path", type=Path, default=DEFAULT_YDS_RATINGS)
    parser.add_argument("--burn-report-path", type=Path, default=DEFAULT_BURN_REPORT)
    parser.add_argument("--revenue-notes-path", type=Path, default=DEFAULT_REVENUE_NOTES)
    parser.add_argument("--telic-ontology-db-path", type=Path, default=DEFAULT_TELIC_ONTOLOGY_DB)
    parser.add_argument("--json", action="store_true", help="also print the generated payload")
    args = parser.parse_args(argv)

    payload = build_system_map(
        repo_root=args.repo_root.expanduser().resolve(),
        audit_dir=args.audit_dir.expanduser(),
        yds_ratings_path=args.yds_ratings_path.expanduser(),
        burn_report_path=args.burn_report_path.expanduser(),
        revenue_notes_path=args.revenue_notes_path.expanduser(),
        telic_ontology_db_path=args.telic_ontology_db_path.expanduser(),
    )
    output = args.output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Wrote {output} with {len(payload['organs'])} organ(s)")
    return 0


def build_system_map(
    *,
    repo_root: Path = REPO_ROOT,
    audit_dir: Path = DEFAULT_AUDIT_DIR,
    yds_ratings_path: Path | None = DEFAULT_YDS_RATINGS,
    burn_report_path: Path | None = DEFAULT_BURN_REPORT,
    revenue_notes_path: Path | None = DEFAULT_REVENUE_NOTES,
    telic_ontology_db_path: Path | None = DEFAULT_TELIC_ONTOLOGY_DB,
) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    audit_sources = list(_audit_sources(audit_dir))
    operating_facts = list(
        _operating_fact_organs(
            repo_root,
            yds_ratings_path=yds_ratings_path,
            burn_report_path=burn_report_path,
            revenue_notes_path=revenue_notes_path,
            telic_ontology_db_path=telic_ontology_db_path,
        )
    )
    audit_facts = list(_audit_fact_organs(audit_sources, now))
    organs = _merge_organs(operating_facts + [_core_circuit_organ(operating_facts, now)] + audit_facts)
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


def _operating_fact_organs(
    repo_root: Path,
    *,
    yds_ratings_path: Path | None,
    burn_report_path: Path | None,
    revenue_notes_path: Path | None,
    telic_ontology_db_path: Path | None,
) -> tuple[OrganStateFact, ...]:
    reports_dir = repo_root / "reports"
    bundle = build_operating_fact_bundle(
        OperatingFactInputs(
            agentops_reports_dir=reports_dir / "agentops",
            kaizen_reports_dir=reports_dir / "kaizen",
            yds_ratings_path=yds_ratings_path,
            burn_report_path=burn_report_path,
            revenue_notes_path=revenue_notes_path,
            telic_ontology_db_path=telic_ontology_db_path,
        )
    )
    return organ_state_facts(bundle)


def _core_circuit_organ(operating_facts: Iterable[OrganStateFact], observed_at: str) -> OrganStateFact:
    state_by_name = {fact.name: fact for fact in operating_facts}
    required = ("agentops", "kaizen_review", "daily_operating_brief", "telic_value")
    required_facts = tuple(state_by_name.get(name) for name in required)
    evidence_refs = tuple(
        dict.fromkeys(ref for fact in required_facts if fact is not None for ref in fact.evidence_refs)
    )
    missing = tuple(name for name, fact in zip(required, required_facts) if fact is None)
    not_bound = tuple(
        fact.name
        for fact in required_facts
        if fact is not None and fact.coherence_state != "bound"
    )
    drifted = tuple(
        fact.name
        for fact in required_facts
        if fact is not None and fact.coherence_state == "drifted"
    )
    if drifted:
        coherence = "drifted"
        observed = "core circuit has drifted leg(s): " + ", ".join(drifted)
        open_gap = "fix red or scope-violating circuit leg(s) before calling the loop closed"
        next_gap = "rerun the first drifted leg under AgentOps and reload operating facts"
    elif not missing and not not_bound:
        coherence = "bound"
        observed = "AgentOps -> KaizenReview -> Telic value -> Daily Brief circuit loaded"
        open_gap = ""
        next_gap = "replay the circuit against a live operator-selected packet"
    else:
        coherence = "partial"
        unresolved = tuple(dict.fromkeys((*missing, *not_bound)))
        observed = "core circuit is missing bound leg(s): " + ", ".join(unresolved)
        open_gap = "one or more core circuit legs is not backed by loaded evidence"
        next_gap = "bind " + ", ".join(unresolved)

    return OrganStateFact(
        name="central_loop",
        owns="proposal to execution to value feedback loop",
        declared_state="AgentOps, KaizenReview, Telic value, and Daily Brief close one operating circuit",
        observed_state=observed,
        coherence_state=coherence,
        evidence_refs=evidence_refs,
        open_gap=open_gap,
        next_packet_hint=next_gap,
        declared_primitive="core operating circuit",
        actual_runtime_primitive=observed,
        source_stores=required,
        sink_stores=("reports/system_map/latest.json",),
        gates_declared=("AgentOps scope gate", "KaizenReview report gate", "Telic value chain gate"),
        gates_enforced=tuple(name for name in required if state_by_name.get(name, None) is not None),
        witness_writes=evidence_refs,
        last_observed=observed_at,
        drift=open_gap,
        next_bindable_gap=next_gap,
        risk="high" if coherence != "bound" else "bound",
    )


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
        preferred = _preferred_fact(prior, fact)
        refs = tuple(dict.fromkeys((*prior.evidence_refs, *fact.evidence_refs)))
        by_name[fact.name] = OrganStateFact(
            name=fact.name,
            owns=preferred.owns,
            declared_state=preferred.declared_state,
            observed_state=preferred.observed_state,
            coherence_state=preferred.coherence_state,
            evidence_refs=refs,
            open_gap=preferred.open_gap,
            next_packet_hint=preferred.next_packet_hint,
            declared_primitive=preferred.declared_primitive,
            actual_runtime_primitive=preferred.actual_runtime_primitive,
            source_stores=tuple(dict.fromkeys((*prior.source_stores, *fact.source_stores))),
            sink_stores=tuple(dict.fromkeys((*prior.sink_stores, *fact.sink_stores))),
            gates_declared=tuple(dict.fromkeys((*prior.gates_declared, *fact.gates_declared))),
            gates_enforced=tuple(dict.fromkeys((*prior.gates_enforced, *fact.gates_enforced))),
            witness_writes=tuple(dict.fromkeys((*prior.witness_writes, *fact.witness_writes))),
            scheduled=preferred.scheduled,
            merged_to_main=preferred.merged_to_main,
            last_observed=preferred.last_observed,
            drift=preferred.drift,
            next_bindable_gap=preferred.next_bindable_gap,
            risk=preferred.risk,
        )
    return tuple(by_name.values())


def _preferred_fact(left: OrganStateFact, right: OrganStateFact) -> OrganStateFact:
    return left if _stronger_state(left.coherence_state, right.coherence_state) == left.coherence_state else right


def _stronger_state(left: str, right: str) -> str:
    rank = {"unknown": 0, "declared_only": 1, "partial": 2, "bound": 3, "drifted": 4}
    return left if rank.get(left, 0) >= rank.get(right, 0) else right


if __name__ == "__main__":
    raise SystemExit(main())
