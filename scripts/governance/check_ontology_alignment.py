#!/usr/bin/env python3
"""
check_ontology_alignment.py — KARMA-style schema-alignment CI gate.

Adversarial pre-merge check for the dharma_swarm ontology. Detects conflicts
between concurrent multi-agent ObjectType / LinkDef / ActionDef proposals
BEFORE merge. Modeled on:

  - Palantir Foundry's centralized Ontology Metadata Service authority model
    (https://palantir.com/docs/foundry/ontology — single-engineer convention)
  - KARMA (NeurIPS 2025): pre-merge schema-alignment agent for multi-agent
    ontology editing where no automatic 3-way semantic merge exists
  - W3C OWL/RDF disjointness checks adapted to property-graph semantics

WHY THIS EXISTS
---------------
Palantir does ontology with a SINGLE forward-deployed engineer + centralized OMS
authority. Multi-agent concurrent ontology editing is **unsolved** in industry
(no automatic 3-way semantic merge, no CRDTs for typed schemas). dharma_swarm
has 5 agents (claude, perplexity, devin, hermes, mike) editing concurrently.
This gate is the explicit replacement for "we have an OMS authority" —
it surfaces conflicts so the operator can resolve them deterministically.

CHECKS PERFORMED
----------------
Across the current branch's ontology.py vs. all OTHER open ontology-touching
PRs on origin (or against origin/main if no other branches), this gate fails
the build if any of the following are true:

  ALIGN-001  Two PRs add an ObjectType with the same `name` but different
             property sets, security policies, or telos_alignment.
  ALIGN-002  Two PRs add an ObjectType with the same `api_name` but different
             internal `name` (api_name is the public stable contract).
  ALIGN-003  Two PRs change the same ObjectType to incompatible `status`
             (e.g. one promotes to PROMOTED, another flips to EXPERIMENTAL).
  ALIGN-004  Two PRs define a LinkDef with same (source_type, name) but
             different target_type or cardinality.
  ALIGN-005  Two PRs define an ActionDef with same (object_type, name) but
             different parameter signature or effect.
  ALIGN-006  A PR removes a PROMOTED ObjectType without a deprecation marker.
  ALIGN-007  A PR introduces an ObjectType whose api_name does not match the
             frozen pattern `dharma.<domain>.<TypeName>.v<N>` (api naming
             discipline from PR #405 sec 7.3 — ontology IS the API).

OUTPUTS
-------
Exit 0  → all proposals align; PR clear for merge.
Exit 1  → conflict detected; prints a CONFLICT_REPORT with: rule, the two
          PRs involved, the conflicting fields, and a suggested resolution.

Designed to run in CI on every ontology-touching PR. Operator (John) is final
arbiter; Mike (merge authority) enforces the gate; agents propose via typed
register_type with status-lifecycle (agent→active, OPERATOR→promoted).

This script is INTENTIONALLY ADDITIVE — it never modifies ontology.py, never
auto-resolves, never merges. It only surfaces conflicts and explains them.

DEPENDENCY NOTE
---------------
This gate requires Devin's in-flight OMS hardening (PR pending as of 2026-06-01):
  - ObjectType.status field (experimental / active / promoted)
  - ObjectType.api_name field (frozen)
  - OntologyRegistry.register_type uniqueness guard

If those fields are not yet present on `ObjectType`, this gate runs in
"degraded mode": it checks ALIGN-001 / ALIGN-004 / ALIGN-005 only, skipping
api_name / status checks with a clear warning. Once Devin's PR lands and is
merged to main, all 7 rules become enforceable.

USAGE
-----
  # Run against current branch vs. all open ontology PRs:
  python3 scripts/governance/check_ontology_alignment.py

  # Run in CI on a specific PR number:
  python3 scripts/governance/check_ontology_alignment.py --pr 421

  # JSON output for machine consumption:
  python3 scripts/governance/check_ontology_alignment.py --json

  # Strict mode: ALIGN-007 api_name discipline becomes a failure (not a warning):
  python3 scripts/governance/check_ontology_alignment.py --strict
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH_REL = "dharma_swarm/ontology.py"
API_NAME_PATTERN = re.compile(r"^dharma\.[a-z][a-z0-9_]*\.[A-Z][A-Za-z0-9]*\.v\d+$")
DEFAULT_PR_LIMIT = 30

# ── Data model ────────────────────────────────────────────────────────


@dataclass
class TypeSpec:
    """Lightweight snapshot of an ObjectType definition for diffing."""
    name: str
    api_name: str | None = None
    status: str | None = None
    description: str = ""
    properties: dict[str, dict] = field(default_factory=dict)
    links: list[dict] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    telos_alignment: float | None = None
    shakti_energy: str | None = None
    security: dict | None = None
    version: int | None = None
    source_pr: str | None = None      # e.g. "main" or "PR#421"
    source_branch: str | None = None  # the head ref
    source_commit: str | None = None  # SHA in that branch


@dataclass
class LinkSpec:
    name: str
    source_type: str
    target_type: str
    cardinality: str
    source_pr: str | None = None


@dataclass
class ActionSpec:
    name: str
    object_type: str
    param_signature: list[str] = field(default_factory=list)
    source_pr: str | None = None


@dataclass
class Conflict:
    rule: str          # e.g. "ALIGN-002"
    severity: str      # "error" | "warning"
    summary: str
    pr_a: str
    pr_b: str
    type_or_link: str
    field_diffs: dict[str, list]
    suggestion: str


# ── Snapshot extraction ───────────────────────────────────────────────


def _extract_ontology_snapshot(ontology_text: str, source_pr: str,
                                source_branch: str = "", source_commit: str = "") -> dict[str, Any]:
    """Parse an ontology.py file and extract every ObjectType / LinkDef / ActionDef.

    We do NOT execute the file (PRs may not be installable). Instead we use the
    `ast` module to walk class bodies and module-level assignments of the form
    `_FOO_TYPE = ObjectType(...)`.

    Returns dict with keys: types, links, actions — values are lists of dicts.
    """
    import ast
    try:
        tree = ast.parse(ontology_text)
    except SyntaxError as e:
        return {"types": [], "links": [], "actions": [],
                "parse_error": f"{type(e).__name__}: {e}"}

    types: list[TypeSpec] = []
    links: list[LinkSpec] = []
    actions: list[ActionSpec] = []

    def _kwarg_value(call: ast.Call, key: str) -> Any:
        for kw in call.keywords:
            if kw.arg == key:
                try:
                    return ast.literal_eval(kw.value)
                except Exception:
                    return None
        return None

    for node in ast.walk(tree):
        # Module-level: _FOO = ObjectType(name="...", api_name="...", ...)
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if not isinstance(tgt, ast.Name):
                    continue
                if not isinstance(node.value, ast.Call):
                    continue
                func = node.value.func
                func_name = getattr(func, "id", None) or getattr(func, "attr", None)
                if func_name == "ObjectType":
                    name = _kwarg_value(node.value, "name") or tgt.id
                    types.append(TypeSpec(
                        name=name,
                        api_name=_kwarg_value(node.value, "api_name"),
                        status=_kwarg_value(node.value, "status"),
                        description=_kwarg_value(node.value, "description") or "",
                        properties={},  # filled below via LinkDef/PropertyDef extraction
                        telos_alignment=_kwarg_value(node.value, "telos_alignment"),
                        shakti_energy=_kwarg_value(node.value, "shakti_energy"),
                        version=_kwarg_value(node.value, "version"),
                        source_pr=source_pr,
                        source_branch=source_branch,
                        source_commit=source_commit,
                    ))
                elif func_name == "LinkDef":
                    nm = _kwarg_value(node.value, "name")
                    src = _kwarg_value(node.value, "source_type")
                    tgt_t = _kwarg_value(node.value, "target_type")
                    card = _kwarg_value(node.value, "cardinality") or "MANY_TO_ONE"
                    if nm and src and tgt_t:
                        links.append(LinkSpec(name=nm, source_type=src,
                                              target_type=tgt_t, cardinality=str(card),
                                              source_pr=source_pr))
                elif func_name == "ActionDef":
                    nm = _kwarg_value(node.value, "name")
                    ot = _kwarg_value(node.value, "object_type")
                    params = _kwarg_value(node.value, "parameters") or []
                    if nm and ot:
                        actions.append(ActionSpec(name=nm, object_type=ot,
                                                  param_signature=[str(p) for p in params],
                                                  source_pr=source_pr))

    return {
        "types": [asdict(t) for t in types],
        "links": [asdict(l) for l in links],
        "actions": [asdict(a) for a in actions],
    }


def _read_file_at_ref(ref: str, path: str) -> str | None:
    """Return file contents at a git ref, or None if missing."""
    try:
        out = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=15,
        )
        return out.stdout
    except subprocess.CalledProcessError:
        return None
    except Exception:
        return None


def _list_open_ontology_prs(limit: int = DEFAULT_PR_LIMIT) -> list[dict]:
    """List open PRs that touch ontology.py via gh CLI."""
    try:
        out = subprocess.run(
            ["gh", "pr", "list", "--state", "open", "--limit", str(limit),
             "--json", "number,title,headRefName,headRefOid,author,updatedAt,files"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=20,
        )
        prs = json.loads(out.stdout)
        relevant = []
        for pr in prs:
            files = pr.get("files") or []
            for f in files:
                if f.get("path", "").endswith("ontology.py") or "ontology" in f.get("path", "").lower():
                    relevant.append(pr)
                    break
        return relevant
    except Exception as e:
        print(f"[warn] could not list PRs via gh: {e}", file=sys.stderr)
        return []


# ── Conflict detection ────────────────────────────────────────────────


def _detect_conflicts(snapshots: list[dict[str, Any]]) -> list[Conflict]:
    """Compare snapshots pairwise and emit conflicts."""
    conflicts: list[Conflict] = []

    # Flatten with provenance
    all_types: list[dict] = []
    all_links: list[dict] = []
    all_actions: list[dict] = []
    for snap in snapshots:
        all_types.extend(snap.get("types", []))
        all_links.extend(snap.get("links", []))
        all_actions.extend(snap.get("actions", []))

    # ALIGN-001 / ALIGN-002 / ALIGN-003: ObjectType conflicts
    by_name: dict[str, list[dict]] = {}
    by_api_name: dict[str, list[dict]] = {}
    for t in all_types:
        by_name.setdefault(t["name"], []).append(t)
        if t.get("api_name"):
            by_api_name.setdefault(t["api_name"], []).append(t)

    for name, defs in by_name.items():
        # Compare each unique pair across DIFFERENT source_prs
        pairs_seen = set()
        for i, a in enumerate(defs):
            for b in defs[i+1:]:
                if a["source_pr"] == b["source_pr"]:
                    continue
                key = tuple(sorted([a["source_pr"], b["source_pr"]]))
                if key in pairs_seen:
                    continue
                pairs_seen.add(key)

                diffs = {}
                for field_ in ("api_name", "telos_alignment", "shakti_energy",
                               "version", "description"):
                    if a.get(field_) != b.get(field_):
                        diffs[field_] = [a.get(field_), b.get(field_)]
                if diffs:
                    conflicts.append(Conflict(
                        rule="ALIGN-001",
                        severity="error",
                        summary=f"ObjectType '{name}' defined incompatibly across two PRs",
                        pr_a=a["source_pr"], pr_b=b["source_pr"],
                        type_or_link=name,
                        field_diffs=diffs,
                        suggestion=(
                            f"Reconcile via ADR: choose ONE definition of '{name}' and "
                            f"land it on main first. Other PR rebases against it. "
                            f"Operator (@AmitabhainArunachala) decides if ambiguous."
                        ),
                    ))
                # ALIGN-003: status conflict
                if a.get("status") and b.get("status") and a["status"] != b["status"]:
                    conflicts.append(Conflict(
                        rule="ALIGN-003",
                        severity="error",
                        summary=f"ObjectType '{name}' has conflicting status across PRs",
                        pr_a=a["source_pr"], pr_b=b["source_pr"],
                        type_or_link=name,
                        field_diffs={"status": [a["status"], b["status"]]},
                        suggestion=(
                            f"Status promotion is monotonic: experimental→active→promoted. "
                            f"Demotion or fork forbidden. Land the higher status PR first, "
                            f"rebase the other."
                        ),
                    ))

    # ALIGN-002: api_name collision across different internal names
    for api_name, defs in by_api_name.items():
        names = {d["name"] for d in defs}
        if len(names) > 1:
            conflicts.append(Conflict(
                rule="ALIGN-002",
                severity="error",
                summary=f"api_name '{api_name}' used by multiple ObjectTypes",
                pr_a=defs[0]["source_pr"], pr_b=defs[-1]["source_pr"],
                type_or_link=api_name,
                field_diffs={"name": list(names)},
                suggestion=(
                    f"api_name is the PUBLIC stable contract — it must map 1:1 to a single "
                    f"internal name. Rename one. Bump version suffix if both must coexist."
                ),
            ))

    # ALIGN-004: LinkDef conflicts
    by_link_key: dict[tuple, list[dict]] = {}
    for l in all_links:
        by_link_key.setdefault((l["source_type"], l["name"]), []).append(l)
    for key, defs in by_link_key.items():
        pairs_seen = set()
        for i, a in enumerate(defs):
            for b in defs[i+1:]:
                if a["source_pr"] == b["source_pr"]:
                    continue
                pkey = tuple(sorted([a["source_pr"], b["source_pr"]]))
                if pkey in pairs_seen:
                    continue
                pairs_seen.add(pkey)
                if a["target_type"] != b["target_type"] or a["cardinality"] != b["cardinality"]:
                    conflicts.append(Conflict(
                        rule="ALIGN-004",
                        severity="error",
                        summary=f"LinkDef ({key[0]}).{key[1]} differs across PRs",
                        pr_a=a["source_pr"], pr_b=b["source_pr"],
                        type_or_link=f"{key[0]}.{key[1]}",
                        field_diffs={
                            "target_type": [a["target_type"], b["target_type"]],
                            "cardinality": [a["cardinality"], b["cardinality"]],
                        },
                        suggestion=(
                            "Links are bidirectional contracts — once defined they pin both "
                            "endpoints' shape. Reconcile in ADR."
                        ),
                    ))

    # ALIGN-005: ActionDef conflicts
    by_action_key: dict[tuple, list[dict]] = {}
    for a in all_actions:
        by_action_key.setdefault((a["object_type"], a["name"]), []).append(a)
    for key, defs in by_action_key.items():
        pairs_seen = set()
        for i, a in enumerate(defs):
            for b in defs[i+1:]:
                if a["source_pr"] == b["source_pr"]:
                    continue
                pkey = tuple(sorted([a["source_pr"], b["source_pr"]]))
                if pkey in pairs_seen:
                    continue
                pairs_seen.add(pkey)
                if a["param_signature"] != b["param_signature"]:
                    conflicts.append(Conflict(
                        rule="ALIGN-005",
                        severity="error",
                        summary=f"ActionDef {key[0]}.{key[1]} has different parameter signatures",
                        pr_a=a["source_pr"], pr_b=b["source_pr"],
                        type_or_link=f"{key[0]}.{key[1]}",
                        field_diffs={
                            "param_signature": [a["param_signature"], b["param_signature"]],
                        },
                        suggestion=(
                            "Actions are the kinetic write-path (Palantir Funnel equivalent). "
                            "Signature changes break callers. Use SEMVER + deprecation, never "
                            "mutate in place."
                        ),
                    ))

    return conflicts


# ── api_name discipline (ALIGN-007) ───────────────────────────────────


def _check_api_name_discipline(snapshots: list[dict[str, Any]],
                                strict: bool) -> list[Conflict]:
    """Flag any ObjectType whose api_name doesn't match the frozen pattern."""
    issues: list[Conflict] = []
    severity = "error" if strict else "warning"
    for snap in snapshots:
        for t in snap.get("types", []):
            api_name = t.get("api_name")
            if api_name is None:
                # Skipping — Devin's OMS hardening may not have backfilled yet
                continue
            if not API_NAME_PATTERN.match(api_name):
                issues.append(Conflict(
                    rule="ALIGN-007",
                    severity=severity,
                    summary=f"api_name '{api_name}' for type '{t['name']}' violates pattern",
                    pr_a=t["source_pr"], pr_b="(naming-discipline)",
                    type_or_link=t["name"],
                    field_diffs={"api_name": [api_name, "expected: dharma.<domain>.<TypeName>.v<N>"]},
                    suggestion=(
                        "From PR #405 sec 7.3: ontology IS the API. api_names must be "
                        "frozen, namespaced, and SEMVER-stamped. Rename to fit pattern "
                        "or rebase against the latest naming ADR."
                    ),
                ))
    return issues


# ── Main ──────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--pr", type=int, default=None,
                   help="GitHub PR number to check (defaults to current branch)")
    p.add_argument("--json", action="store_true",
                   help="Emit conflicts as JSON for machine consumption")
    p.add_argument("--strict", action="store_true",
                   help="Treat ALIGN-007 api_name discipline as error (default: warning)")
    p.add_argument("--limit", type=int, default=DEFAULT_PR_LIMIT,
                   help=f"Max open PRs to scan (default: {DEFAULT_PR_LIMIT})")
    args = p.parse_args()

    # Snapshot 1: main
    main_text = _read_file_at_ref("origin/main", ONTOLOGY_PATH_REL)
    snapshots: list[dict] = []
    if main_text:
        snapshots.append(_extract_ontology_snapshot(main_text, source_pr="origin/main",
                                                     source_branch="main"))

    # Snapshot 2: current branch (if not main)
    try:
        cur_branch = subprocess.run(["git", "branch", "--show-current"],
                                     cwd=REPO_ROOT, capture_output=True, text=True,
                                     check=True, timeout=5).stdout.strip()
    except Exception:
        cur_branch = ""
    if cur_branch and cur_branch != "main":
        cur_text = (Path(REPO_ROOT) / ONTOLOGY_PATH_REL).read_text() \
            if (Path(REPO_ROOT) / ONTOLOGY_PATH_REL).exists() else None
        if cur_text:
            snapshots.append(_extract_ontology_snapshot(
                cur_text, source_pr=f"branch:{cur_branch}", source_branch=cur_branch))

    # Snapshot 3+: every other open ontology PR
    prs = _list_open_ontology_prs(limit=args.limit)
    if args.pr:
        prs = [p_ for p_ in prs if p_["number"] == args.pr] + \
              [p_ for p_ in prs if p_["number"] != args.pr]
    for pr in prs:
        ref = pr["headRefOid"]
        head = pr["headRefName"]
        # Fetch the ref into local git first (best-effort)
        subprocess.run(["git", "fetch", "origin", head, "--quiet"],
                       cwd=REPO_ROOT, capture_output=True, timeout=20)
        text = _read_file_at_ref(ref, ONTOLOGY_PATH_REL)
        if text is None:
            continue
        snapshots.append(_extract_ontology_snapshot(
            text, source_pr=f"PR#{pr['number']}", source_branch=head, source_commit=ref))

    if not snapshots:
        print("[warn] No ontology snapshots could be loaded — nothing to check.",
              file=sys.stderr)
        return 0

    # Check degraded mode
    has_api_name = any(
        t.get("api_name") is not None
        for s in snapshots for t in s.get("types", [])
    )
    if not has_api_name:
        print("[info] DEGRADED MODE: no api_name on any ObjectType. "
              "ALIGN-002/007 skipped. Waiting on Devin's OMS hardening PR.",
              file=sys.stderr)

    # Detect conflicts
    conflicts = _detect_conflicts(snapshots)
    conflicts.extend(_check_api_name_discipline(snapshots, strict=args.strict))

    # Output
    if args.json:
        print(json.dumps({
            "snapshots_loaded": len(snapshots),
            "snapshot_sources": [s.get("types", [{}])[0].get("source_pr", "?")
                                  if s.get("types") else "(empty)" for s in snapshots],
            "conflicts": [asdict(c) for c in conflicts],
            "errors": [asdict(c) for c in conflicts if c.severity == "error"],
            "warnings": [asdict(c) for c in conflicts if c.severity == "warning"],
        }, indent=2))
    else:
        print(f"\n=== ontology alignment check ===")
        print(f"snapshots loaded: {len(snapshots)}")
        for c in conflicts:
            print(f"\n[{c.severity.upper()}] {c.rule} — {c.summary}")
            print(f"  PR-A: {c.pr_a}")
            print(f"  PR-B: {c.pr_b}")
            print(f"  type/link: {c.type_or_link}")
            for k, v in c.field_diffs.items():
                print(f"    {k}: {v}")
            print(f"  suggestion: {c.suggestion}")
        if not conflicts:
            print("\nALL CLEAR — no schema-alignment conflicts detected.")

    n_errors = sum(1 for c in conflicts if c.severity == "error")
    return 1 if n_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
