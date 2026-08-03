#!/usr/bin/env python3
"""WP-0F2 reproof harness: mechanically re-verify every consumer of the
ratified merge-blocking required-context set.

The ratified set defaults to scripts/governance/ci_parity_manifest.json
(branch-protection SSOT); override with --contexts when the operator is
evaluating a candidate set that has not landed yet. Every check either
imports the consumer's own code or executes its own validation program —
no re-derived copies of consumer logic.

Checks (NETWORK = talks to GitHub, skipped under --offline):
  manifest_shape            manifest schema, non-empty, unique, trimmed
  contract_manifest_parity  ci_truth.load_contract's own parity binding
  ratified_vs_manifest      ratified set == manifest set (exact diff)
  automerge_jq              automerge.yml's own jq validator, executed
  loop_watcher_required     loop_watcher._required_contexts() imported
  rollup_green / rollup_missing / rollup_pending
                            pr_merge_control.evaluate_ci_rollup fixtures
  lane_deliver_denylist     policy files present in DENY_PREFIXES
  tier_policy_paths         tier2 referee paths cover the policy files
  parity_guard_workflows    check_ci_parity.run_check, protection=None
  parity_guard_live         NETWORK: live branch protection == ratified

Run:  python3 scripts/governance/wp0f2_reproof.py [--offline] [--json]
              [--contexts "a,b,c"] [--repo-root PATH]
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_REL = "scripts/governance/ci_parity_manifest.json"
CONTRACT_REL = "docs/governance/CI_TRUTH_CONTRACT.json"
AUTOMERGE_REL = ".github/workflows/automerge.yml"
TIER_POLICY_REL = "scripts/governance/automerge_tier_policy.json"


def _import_consumers(repo_root: Path):
    for entry in (str(repo_root), str(repo_root / "scripts" / "governance")):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    from scripts.governance import check_ci_parity, loop_watcher
    from scripts.runtime import ci_truth, lane_deliver, pr_merge_control

    return ci_truth, pr_merge_control, lane_deliver, loop_watcher, check_ci_parity


def _result(name: str, status: str, detail: str) -> dict:
    return {"name": name, "status": status, "detail": detail}


def _set_diff(expected: set[str], actual: set[str]) -> str:
    return (
        f"missing={sorted(expected - actual)} unexpected={sorted(actual - expected)}"
    )


def synthetic_rollup(contexts: list[str], *, drop: str | None = None,
                     pending: str | None = None) -> list[dict]:
    rollup = []
    for name in contexts:
        if name == drop:
            continue
        if name == pending:
            rollup.append({"name": name, "status": "IN_PROGRESS", "conclusion": ""})
        else:
            rollup.append({"name": name, "status": "COMPLETED", "conclusion": "SUCCESS"})
    return rollup


def extract_automerge_jq(workflow_text: str) -> str:
    anchor = workflow_text.index("id: required_contexts")
    match = re.search(
        r"jq -ce '(.*?)' scripts/governance/ci_parity_manifest\.json",
        workflow_text[anchor:],
        re.DOTALL,
    )
    if not match:
        raise ValueError("automerge.yml required_contexts jq program not found")
    return match.group(1)


def run_all(repo_root: Path = REPO_ROOT, contexts: list[str] | None = None,
            offline: bool = False) -> list[dict]:
    ci_truth, prc, lane_deliver, loop_watcher, check_ci_parity = _import_consumers(repo_root)
    results: list[dict] = []
    manifest_path = repo_root / MANIFEST_REL
    contract_path = repo_root / CONTRACT_REL

    # 1. Manifest shape via ci_truth's own loader (duplicate-key fail-closed,
    #    non-empty, unique) plus the trim rule automerge.yml enforces.
    try:
        manifest = ci_truth.load_json(manifest_path)
        manifest_names = ci_truth.manifest_required_context_names(manifest)
        blank = [c for c in manifest_names if not c.strip() or c != c.strip()]
        if blank:
            results.append(_result("manifest_shape", "FAIL", f"non-trimmed contexts: {blank}"))
        else:
            results.append(_result(
                "manifest_shape", "PASS",
                f"{len(manifest_names)} unique non-blank contexts"))
    except ci_truth.CITruthError as exc:
        results.append(_result("manifest_shape", "FAIL", str(exc)))
        return results
    ratified = list(contexts) if contexts else manifest_names
    if not ratified:
        results.append(_result("ratified_set", "FAIL", "ratified context set is empty"))
        return results
    ratified_set = set(ratified)

    # 2. Contract loads through its own parity binding (required_contexts_manifest
    #    indirection is mandatory and validated inside load_contract), and the
    #    contract's canonical required names equal the ratified set.
    try:
        contract = ci_truth.load_contract(contract_path)
        contract_names = set(ci_truth.required_context_names(contract))
        if contract_names == ratified_set:
            results.append(_result("contract_manifest_parity", "PASS",
                                   f"contract v{contract.get('version')} == ratified set"))
        else:
            results.append(_result("contract_manifest_parity", "FAIL",
                                   _set_diff(ratified_set, contract_names)))
    except ci_truth.CITruthError as exc:
        results.append(_result("contract_manifest_parity", "FAIL", str(exc)))
        contract = None

    # 3. Ratified set vs manifest (identity when no --contexts override).
    if ratified_set == set(manifest_names):
        results.append(_result("ratified_vs_manifest", "PASS", "sets equal"))
    else:
        results.append(_result("ratified_vs_manifest", "FAIL",
                               _set_diff(ratified_set, set(manifest_names))))

    # 4. automerge.yml's own jq validator, executed against the manifest.
    jq_bin = shutil.which("jq")
    if jq_bin is None:
        results.append(_result("automerge_jq", "SKIP", "jq binary not available"))
    else:
        try:
            program = extract_automerge_jq((repo_root / AUTOMERGE_REL).read_text(encoding="utf-8"))
            proc = subprocess.run([jq_bin, "-ce", program, str(manifest_path)],
                                  capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                results.append(_result("automerge_jq", "FAIL",
                                       f"jq rejected manifest: {proc.stderr.strip()}"))
            else:
                emitted = json.loads(proc.stdout)
                if emitted == manifest_names and set(emitted) == ratified_set:
                    results.append(_result("automerge_jq", "PASS",
                                           "workflow jq accepts manifest and emits ratified set"))
                else:
                    results.append(_result("automerge_jq", "FAIL",
                                           f"jq emitted {emitted}"))
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            results.append(_result("automerge_jq", "FAIL", str(exc)))

    # 5. loop_watcher's imported required list.
    watcher_names = loop_watcher._required_contexts()
    if Path(loop_watcher.MANIFEST_PATH) != manifest_path:
        results.append(_result("loop_watcher_required", "FAIL",
                               f"MANIFEST_PATH is {loop_watcher.MANIFEST_PATH}"))
    elif set(watcher_names) == ratified_set:
        results.append(_result("loop_watcher_required", "PASS",
                               "loop_watcher._required_contexts() == ratified set"))
    else:
        results.append(_result("loop_watcher_required", "FAIL",
                               _set_diff(ratified_set, set(watcher_names))))

    # 6. pr_merge_control's evaluate_ci_rollup on synthetic fixtures. The
    #    contract is loaded through pr_merge_control's own path resolution
    #    (honors DHARMA_CI_TRUTH_CONTRACT), and required entries are matched
    #    against the RATIFIED strings, proving name-level agreement.
    if contract is not None:
        gate_contract = prc.load_ci_truth_contract(prc.ci_truth_contract_path(None))
        green = prc.evaluate_ci_rollup(synthetic_rollup(ratified), gate_contract)
        req_status = {r["id"]: r["status"] for r in green["required"]}
        if green["merge_blockers"] or any(s != "PASS" for s in req_status.values()):
            results.append(_result("rollup_green", "FAIL",
                                   f"blockers={green['merge_blockers']} required={req_status}"))
        else:
            results.append(_result("rollup_green", "PASS",
                                   f"all-green fixture: verdict={green['verdict']}, no blockers"))
        dropped = ratified[0]
        missing = prc.evaluate_ci_rollup(
            synthetic_rollup(ratified, drop=dropped), gate_contract)
        if missing["verdict"] == "FAIL" and missing["merge_blockers"]:
            results.append(_result("rollup_missing", "PASS",
                                   f"dropping {dropped!r} blocks merge"))
        else:
            results.append(_result("rollup_missing", "FAIL",
                                   f"dropping {dropped!r} did NOT block: {missing['verdict']}"))
        pending = prc.evaluate_ci_rollup(
            synthetic_rollup(ratified, pending=dropped), gate_contract)
        if pending["verdict"] == "FAIL" and pending["merge_blockers"]:
            results.append(_result("rollup_pending", "PASS",
                                   f"pending {dropped!r} blocks merge"))
        else:
            results.append(_result("rollup_pending", "FAIL",
                                   f"pending {dropped!r} did NOT block: {pending['verdict']}"))
    else:
        for name in ("rollup_green", "rollup_missing", "rollup_pending"):
            results.append(_result(name, "SKIP", "contract failed to load"))

    # 7. lane_deliver refuses lane edits to the policy files.
    denied = [p for p in (CONTRACT_REL, MANIFEST_REL)
              if p not in lane_deliver.DENY_PREFIXES]
    if denied:
        results.append(_result("lane_deliver_denylist", "FAIL",
                               f"not in DENY_PREFIXES: {denied}"))
    else:
        results.append(_result("lane_deliver_denylist", "PASS",
                               "contract + manifest are lane-delivery denied"))

    # 8. Tier-2 referee paths cover the policy surface.
    tier_policy = ci_truth.load_json(repo_root / TIER_POLICY_REL)
    tier2_paths = set((tier_policy.get("tiers", {}).get("tier2", {})).get("paths", []))
    wanted = {CONTRACT_REL, MANIFEST_REL,
              "scripts/runtime/ci_truth.py", "scripts/runtime/pr_merge_control.py"}
    uncovered = sorted(wanted - tier2_paths)
    if uncovered:
        results.append(_result("tier_policy_paths", "FAIL",
                               f"tier2 paths missing: {uncovered}"))
    else:
        results.append(_result("tier_policy_paths", "PASS",
                               "tier2 referee paths cover contract/manifest/gate code"))

    # 9. Parity guard, offline half: workflow wiring for every manifest context.
    workflows_dir = repo_root / ".github" / "workflows"
    wf_report = check_ci_parity.run_check(copy.deepcopy(manifest), workflows_dir, None)
    if wf_report.drift:
        results.append(_result("parity_guard_workflows", "FAIL",
                               "; ".join(wf_report.drift)))
    else:
        results.append(_result("parity_guard_workflows", "PASS",
                               f"workflow wiring clean (warnings: {len(wf_report.warnings)})"))

    # 10. NETWORK: live branch protection equals the ratified set.
    if offline:
        results.append(_result("parity_guard_live", "SKIP", "NETWORK check skipped (--offline)"))
    else:
        repo = str(manifest.get("repo") or "")
        branch = str(manifest.get("branch") or "main")
        try:
            protection = check_ci_parity.fetch_live_protection(repo, branch)
            live = check_ci_parity.actual_contexts_from_protection(protection)
            live_report = check_ci_parity.run_check(
                copy.deepcopy(manifest), workflows_dir, protection)
            if live == ratified_set and not live_report.drift:
                results.append(_result("parity_guard_live", "PASS",
                                       f"NETWORK: live protection on {repo}@{branch} == ratified set"))
            else:
                results.append(_result("parity_guard_live", "FAIL",
                                       f"NETWORK: {_set_diff(ratified_set, live)}; "
                                       f"drift={live_report.drift}"))
        except (RuntimeError, json.JSONDecodeError) as exc:
            results.append(_result("parity_guard_live", "FAIL", f"NETWORK: {exc}"))

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contexts", default="",
                        help="Comma-separated ratified context override (default: manifest)")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--offline", action="store_true",
                        help="Skip NETWORK checks (live branch protection)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    contexts = [c.strip() for c in args.contexts.split(",") if c.strip()] or None
    results = run_all(Path(args.repo_root), contexts, args.offline)
    failed = [r for r in results if r["status"] == "FAIL"]
    if args.json:
        print(json.dumps({"schema": "dharma.wp0f2_reproof.v1",
                          "verdict": "FAIL" if failed else "PASS",
                          "results": results}, indent=2))
    else:
        for r in results:
            print(f"{r['status']:<5} {r['name']:<24} {r['detail']}")
        print(f"\nVERDICT: {'FAIL' if failed else 'PASS'} "
              f"({len(results) - len(failed)}/{len(results)} checks clean)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
