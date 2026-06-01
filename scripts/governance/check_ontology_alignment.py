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
  ALIGN-006  A PR removes a PROMOTED ObjectType from the ontology snapshot.
  ALIGN-007  A PR introduces an ObjectType whose api_name does not match the
             frozen pattern `dharma.<domain>.<TypeName>` (api naming
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

OMS STATE
---------
This gate assumes the OMS hardening from PR #409 is present on main:
  - ObjectType.status field (experimental / active / promoted)
  - ObjectType.api_name field (frozen, no version suffix)
  - OntologyRegistry.register_type uniqueness and immutability guards

Branches without api_name/status still parse, but missing api_name means
ALIGN-002/007 cannot protect that ObjectType until the branch rebases onto the
OMS baseline.

USAGE
-----
  # Run against current branch vs. all open ontology PRs:
  python3 scripts/governance/check_ontology_alignment.py

  # Run in CI on a specific PR number:
  python3 scripts/governance/check_ontology_alignment.py --pr 421

  # JSON output for machine consumption:
  python3 scripts/governance/check_ontology_alignment.py --json

  # Warn-only mode: report ALIGN-007 api_name discipline without failing:
  python3 scripts/governance/check_ontology_alignment.py --warn-only-api-name
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from contracts.typed_proposal_envelope import API_NAME_PATTERN  # noqa: E402

ONTOLOGY_PATH_REL = "dharma_swarm/ontology.py"
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

    def _literal_or_name(node: ast.AST) -> Any:
        try:
            return ast.literal_eval(node)
        except Exception:
            pass
        if isinstance(node, ast.Attribute):
            return node.attr.lower()
        if isinstance(node, ast.Name):
            return node.id
        return None

    def _literal_name_or_dump(node: ast.AST) -> str:
        value = _literal_or_name(node)
        if value is not None:
            return str(value)
        return ast.dump(node, annotate_fields=True, include_attributes=False)

    def _kwarg_value(call: ast.Call, key: str) -> Any:
        for kw in call.keywords:
            if kw.arg == key:
                return _literal_or_name(kw.value)
        return None

    def _kwarg_node(call: ast.Call, key: str) -> ast.AST | None:
        for kw in call.keywords:
            if kw.arg == key:
                return kw.value
        return None

    def _kwarg_fingerprint(call: ast.Call, key: str) -> Any:
        for kw in call.keywords:
            if kw.arg == key:
                return ast.dump(kw.value, annotate_fields=True, include_attributes=False)
        return None

    def _param_signature(params: ast.AST | None) -> list[str]:
        if params is None:
            return []
        if isinstance(params, ast.Dict):
            pairs = []
            for key_node, value_node in zip(params.keys, params.values, strict=False):
                if key_node is None:
                    continue
                pairs.append((
                    _literal_name_or_dump(key_node),
                    _literal_name_or_dump(value_node),
                ))
            return [f"{key}:{value}" for key, value in sorted(pairs)]
        if isinstance(params, (ast.List, ast.Tuple)):
            return [_literal_name_or_dump(elt) for elt in params.elts]
        value = _literal_or_name(params)
        if value:
            return [str(value)]
        return []

    def _extract_action_call(call: ast.Call) -> ActionSpec | None:
        nm = _kwarg_value(call, "name")
        ot = _kwarg_value(call, "object_type")
        params = _kwarg_node(call, "input_params")
        if params is None:
            params = _kwarg_node(call, "parameters")
        if not nm or not ot:
            return None
        return ActionSpec(
            name=nm,
            object_type=ot,
            param_signature=_param_signature(params),
            source_pr=source_pr,
        )

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
                        properties=_kwarg_fingerprint(node.value, "properties") or {},
                        telos_alignment=_kwarg_value(node.value, "telos_alignment"),
                        shakti_energy=_kwarg_value(node.value, "shakti_energy"),
                        security=_kwarg_fingerprint(node.value, "security"),
                        version=_kwarg_value(node.value, "version"),
                        source_pr=source_pr,
                        source_branch=source_branch,
                        source_commit=source_commit,
                    ))
                    for kw in node.value.keywords:
                        if kw.arg != "actions" or not isinstance(kw.value, ast.List):
                            continue
                        for action_node in kw.value.elts:
                            if not isinstance(action_node, ast.Call):
                                continue
                            action_func = action_node.func
                            action_func_name = (
                                getattr(action_func, "id", None)
                                or getattr(action_func, "attr", None)
                            )
                            if action_func_name != "ActionDef":
                                continue
                            action = _extract_action_call(action_node)
                            if action:
                                actions.append(action)
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
                    action = _extract_action_call(node.value)
                    if action:
                        actions.append(action)

    return {
        "source": source_pr,
        "types": [asdict(t) for t in types],
        "links": [asdict(link) for link in links],
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


def _list_open_ontology_prs(limit: int = DEFAULT_PR_LIMIT,
                            allow_partial: bool = False) -> list[dict]:
    """List open PRs that touch ontology.py via gh CLI."""
    try:
        out = subprocess.run(
            ["gh", "pr", "list", "--state", "open", "--limit", str(limit),
             "--json", "number,title,headRefName,headRefOid,author,updatedAt"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=20,
        )
        prs = json.loads(out.stdout)
        relevant = []
        for pr in prs:
            files_out = subprocess.run(
                ["gh", "pr", "view", str(pr["number"]), "--json", "files"],
                cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=20,
            )
            files = json.loads(files_out.stdout).get("files") or []
            for f in files:
                if f.get("path", "").endswith("ontology.py") or "ontology" in f.get("path", "").lower():
                    pr["files"] = files
                    relevant.append(pr)
                    break
        return relevant
    except Exception as e:
        if allow_partial:
            print(f"[warn] could not list PRs via gh: {e}", file=sys.stderr)
            return []
        raise RuntimeError(f"could not list open ontology PRs via gh: {e}") from e


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
                               "version", "description", "properties", "security"):
                    if field_ == "api_name" and (
                        a.get("api_name") is None or b.get("api_name") is None
                    ):
                        # Pre-OMS branches lack api_name entirely. That is a
                        # rebase gap, not an incompatible alternate contract.
                        continue
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
                            "Status promotion is monotonic: experimental→active→promoted. "
                            "Demotion or fork forbidden. Land the higher status PR first, "
                            "rebase the other."
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
                    "api_name is the PUBLIC stable contract — it must map 1:1 to a single "
                    "internal name. Rename one and use ObjectType.version / deprecation "
                    "metadata if both contracts must coexist."
                ),
            ))

    # ALIGN-006: PROMOTED type removed from a branch snapshot. The typed
    # deprecation envelope is a separate artifact and is reviewed by the merge
    # authority; this checker only proves the ontology snapshot is missing the
    # promoted public contract.
    main_types = {
        t["name"]: t
        for t in all_types
        if t.get("source_pr") == "origin/main" and t.get("status") == "promoted"
    }
    if main_types:
        snapshots_by_source = {
            snap.get("source") or (
                snap.get("types", [{}])[0].get("source_pr") if snap.get("types") else "(empty)"
            ): snap
            for snap in snapshots
        }
        for source, snap in snapshots_by_source.items():
            if source == "origin/main":
                continue
            names = {t["name"] for t in snap.get("types", [])}
            for name, main_type in main_types.items():
                if name not in names:
                    conflicts.append(Conflict(
                        rule="ALIGN-006",
                        severity="error",
                        summary=f"PROMOTED ObjectType '{name}' removed from ontology snapshot",
                        pr_a="origin/main", pr_b=source,
                        type_or_link=name,
                        field_diffs={
                            "status": [main_type.get("status"), "(missing)"],
                            "api_name": [main_type.get("api_name"), "(missing)"],
                        },
                        suggestion=(
                            "Promoted ObjectTypes are public contracts. Keep the type present "
                            "or route the removal through an explicit deprecation proposal and "
                            "operator review."
                        ),
                    ))

    # ALIGN-004: LinkDef conflicts
    by_link_key: dict[tuple, list[dict]] = {}
    for link in all_links:
        by_link_key.setdefault((link["source_type"], link["name"]), []).append(link)
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
                                warn_only: bool) -> list[Conflict]:
    """Flag any ObjectType whose api_name doesn't match the frozen pattern."""
    issues: list[Conflict] = []
    severity = "warning" if warn_only else "error"
    for snap in snapshots:
        for t in snap.get("types", []):
            api_name = t.get("api_name")
            if api_name is None:
                # Branch has not rebased onto the OMS hardening baseline yet.
                continue
            if not API_NAME_PATTERN.match(api_name):
                issues.append(Conflict(
                    rule="ALIGN-007",
                    severity=severity,
                    summary=f"api_name '{api_name}' for type '{t['name']}' violates pattern",
                    pr_a=t["source_pr"], pr_b="(naming-discipline)",
                    type_or_link=t["name"],
                    field_diffs={"api_name": [api_name, "expected: dharma.<domain>.<TypeName>"]},
                    suggestion=(
                        "From PR #405 sec 7.3: ontology IS the API. api_names must be "
                        "frozen and namespaced. Version belongs in ObjectType.version, "
                        "not in the public api_name. Rename to fit the OMS api_name contract."
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
    p.add_argument("--warn-only-api-name", action="store_true",
                   help="Report ALIGN-007 api_name violations without failing")
    p.add_argument("--allow-partial-pr-scan", action="store_true",
                   help="Continue if GitHub/open-PR snapshot loading fails")
    p.add_argument("--limit", type=int, default=DEFAULT_PR_LIMIT,
                   help=f"Max open PRs to scan (default: {DEFAULT_PR_LIMIT})")
    args = p.parse_args()

    # Snapshot 1: main
    main_text = _read_file_at_ref("origin/main", ONTOLOGY_PATH_REL)
    snapshots: list[dict] = []
    if not main_text:
        print(
            f"[error] could not load authority ontology snapshot: "
            f"origin/main:{ONTOLOGY_PATH_REL}",
            file=sys.stderr,
        )
        return 1
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
    prs = _list_open_ontology_prs(
        limit=args.limit,
        allow_partial=args.allow_partial_pr_scan,
    )
    if args.pr:
        prs = [p_ for p_ in prs if p_["number"] == args.pr] + \
              [p_ for p_ in prs if p_["number"] != args.pr]
    for pr in prs:
        ref = pr["headRefOid"]
        head = pr["headRefName"]
        # Fetch the ref into local git first (best-effort)
        fetch = subprocess.run(["git", "fetch", "origin", head, "--quiet"],
                               cwd=REPO_ROOT, capture_output=True, text=True, timeout=20)
        if fetch.returncode != 0 and not args.allow_partial_pr_scan:
            print(
                f"[error] could not fetch PR#{pr['number']} branch {head}: {fetch.stderr}",
                file=sys.stderr,
            )
            return 1
        text = _read_file_at_ref(ref, ONTOLOGY_PATH_REL)
        if text is None:
            if args.allow_partial_pr_scan:
                print(f"[warn] could not load ontology snapshot for PR#{pr['number']}",
                      file=sys.stderr)
                continue
            print(f"[error] could not load ontology snapshot for PR#{pr['number']}",
                  file=sys.stderr)
            return 1
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
        print("[warn] No api_name on any ObjectType. ALIGN-002/007 skipped; "
              "branch likely needs rebase onto OMS baseline.",
              file=sys.stderr)

    # Detect conflicts
    conflicts = _detect_conflicts(snapshots)
    conflicts.extend(_check_api_name_discipline(snapshots, warn_only=args.warn_only_api_name))

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
        print("\n=== ontology alignment check ===")
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
