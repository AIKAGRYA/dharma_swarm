#!/usr/bin/env python3
"""Rubric-frozen DharmaGraph x LangGraph parity gauntlet.

The rubric is committed before this runner by design.  This module executes
the existing real-LangGraph oracle lineage, seals the mechanically computed
grade, and verifies replay without treating a sub-100 grade as success.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.memory_kernel.write_receipts import stable_digest  # noqa: E402
from tests.oracle_support.dharmagraph_gauntlet import (  # noqa: E402
    langgraph_public_surface_manifest,
    run_capability_probes,
)


BASE_RUBRIC_PATH = (
    ROOT / "docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V1.json"
)
RUBRIC_PATH = ROOT / "docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V2.json"
REPORT_DIR = ROOT / "reports/governance/dharmagraph_parity"
BUILDER_RECEIPT = REPORT_DIR / "builder_receipt.json"
JUDGE_RECEIPT = REPORT_DIR / "judge_receipt.json"
MATRIX_PATH = REPORT_DIR / "PARITY_MATRIX.md"
# Detached promotion authority: deliberately excluded from
# RELEVANT_SOURCE_ROOTS, because a judge signature binds the measured source
# digest. Keeping its allowlist inside that measured source creates an
# impossible fixed-point (ratification changes the digest it ratifies).
JUDGE_RATIFICATIONS_PATH = (
    ROOT / "docs/langgraph_parity/DHARMAGRAPH_JUDGE_RATIFICATIONS_V1.json"
)
JUDGE_RATIFICATIONS_SCHEMA = "dharma_swarm.dharmagraph_judge_ratifications.v1"
RELEVANT_SOURCE_ROOTS = (
    "dharma_swarm/graph",
    "dharma_swarm/langgraph_parity",
    "tests/oracle_support",
    "tests/test_dharmagraph_parity_gauntlet.py",
    "tests/test_graph_neutral_langgraph_oracle.py",
    "tests/test_langgraph_differential_oracle.py",
    "scripts/governance/dharmagraph_parity_gauntlet.py",
    "docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V1.json",
    "docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V2.json",
    ".github/workflows/langgraph-oracle.yml",
    "pyproject.toml",
    "uv.lock",
)


class GauntletError(RuntimeError):
    """Fail-closed gauntlet or custody error."""


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise GauntletError(f"git {' '.join(args)} failed: {detail}")
    return proc.stdout.strip()


def _git_success(*args: str) -> bool:
    proc = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=False
    )
    return proc.returncode == 0


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "NOT_INSTALLED"


_LATEST_DRIFT_PROGRAM = r"""
import json
import sys
from importlib.metadata import version

from scripts.governance.dharmagraph_parity_gauntlet import _load_materialized_rubric
from tests.oracle_support.dharmagraph_gauntlet import (
    langgraph_public_surface_manifest,
    run_capability_probes,
)

seed = int(sys.argv[1])
rubric = _load_materialized_rubric()
result = run_capability_probes(rubric, seed=seed, performance_iterations=1)
summary = {
    "langgraph_version": version("langgraph"),
    "capabilities": {
        row_id: {
            "points": row["points"],
            "facet_statuses": {
                facet: cell["status"] for facet, cell in sorted(row["facets"].items())
            },
        }
        for row_id, row in sorted(result["capabilities"].items())
    },
    "workload_verdicts": {
        name: value["semantic_comparison_verdict"]
        for name, value in sorted(result["raw_evidence"]["workloads"].items())
    },
    "control_failed_as_required": result["control"]["expected_failure_observed"],
    "surface_manifest": langgraph_public_surface_manifest(),
}
print(json.dumps(summary, sort_keys=True))
"""


def _run_latest_stable_drift(
    rubric: Mapping[str, Any], seed: int, pinned_raw: Mapping[str, Any]
) -> dict[str, Any]:
    """Run a non-gating latest-stable surface/outcome probe in an isolated target."""

    drift_target = rubric.get("non_gating_drift_target", {})
    latest_version = str(drift_target.get("version", ""))
    adapter = str(
        rubric.get("comparison_target", {}).get(
            "persistent_checkpoint_adapter", "langgraph-checkpoint-sqlite==3.1.0"
        )
    )
    started = time.perf_counter()
    base = {
        "target": drift_target,
        "installed_grade_target": _package_version("langgraph"),
        "gating": False,
    }
    if not latest_version:
        return {
            **base,
            "status": "EXECUTION_FAILED_NON_GATING",
            "behavioral_execution_against_latest": False,
            "finding": "The frozen latest-stable target has no version.",
        }

    with tempfile.TemporaryDirectory(prefix="dharmagraph-latest-drift-") as raw:
        target = Path(raw) / "site"
        install = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-warn-script-location",
                "--quiet",
                "--target",
                str(target),
                f"langgraph=={latest_version}",
                adapter,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=90,
            check=False,
        )
        if install.returncode != 0:
            detail = (install.stderr or install.stdout).strip()[-4000:]
            return {
                **base,
                "status": "EXECUTION_FAILED_NON_GATING",
                "behavioral_execution_against_latest": False,
                "elapsed_seconds": time.perf_counter() - started,
                "finding": f"isolated latest-stable install failed: {detail}",
            }

        environment = os.environ.copy()
        inherited = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = os.pathsep.join(
            item for item in (str(target), str(ROOT), inherited) if item
        )
        probe = subprocess.run(
            [sys.executable, "-c", _LATEST_DRIFT_PROGRAM, str(seed)],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if probe.returncode != 0:
            detail = (probe.stderr or probe.stdout).strip()[-4000:]
            return {
                **base,
                "status": "EXECUTION_FAILED_NON_GATING",
                "behavioral_execution_against_latest": False,
                "elapsed_seconds": time.perf_counter() - started,
                "finding": f"isolated latest-stable probe failed: {detail}",
            }
        try:
            latest = json.loads(probe.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            return {
                **base,
                "status": "EXECUTION_FAILED_NON_GATING",
                "behavioral_execution_against_latest": False,
                "elapsed_seconds": time.perf_counter() - started,
                "finding": f"latest-stable output was not JSON: {type(exc).__name__}",
            }

    pinned_capabilities = {
        row_id: {
            "points": row["points"],
            "facet_statuses": {
                facet: cell["status"] for facet, cell in sorted(row["facets"].items())
            },
        }
        for row_id, row in sorted(pinned_raw["capabilities"].items())
    }
    pinned_workloads = {
        name: value["semantic_comparison_verdict"]
        for name, value in sorted(pinned_raw["raw_evidence"]["workloads"].items())
    }
    pinned_surface = set(langgraph_public_surface_manifest())
    latest_surface = set(latest["surface_manifest"])
    capability_changes = {
        row_id: {
            "pinned": pinned_capabilities.get(row_id),
            "latest": latest["capabilities"].get(row_id),
        }
        for row_id in sorted(set(pinned_capabilities) | set(latest["capabilities"]))
        if pinned_capabilities.get(row_id) != latest["capabilities"].get(row_id)
    }
    workload_changes = {
        name: {
            "pinned": pinned_workloads.get(name),
            "latest": latest["workload_verdicts"].get(name),
        }
        for name in sorted(set(pinned_workloads) | set(latest["workload_verdicts"]))
        if pinned_workloads.get(name) != latest["workload_verdicts"].get(name)
    }
    surface_added = sorted(latest_surface - pinned_surface)
    surface_removed = sorted(pinned_surface - latest_surface)
    drift_observed = bool(
        capability_changes or workload_changes or surface_added or surface_removed
    )
    return {
        **base,
        "status": "DRIFT_OBSERVED" if drift_observed else "NO_OBSERVED_DRIFT",
        "behavioral_execution_against_latest": True,
        "observed_latest_version": latest["langgraph_version"],
        "control_failed_as_required": latest["control_failed_as_required"],
        "capability_changes": capability_changes,
        "workload_verdict_changes": workload_changes,
        "public_surface_added": surface_added,
        "public_surface_removed": surface_removed,
        "public_surface_counts": {
            "pinned": len(pinned_surface),
            "latest": len(latest_surface),
        },
        "elapsed_seconds": time.perf_counter() - started,
        "finding": (
            "Latest-stable drift is reported only; the frozen 1.2.4 grade is unchanged."
        ),
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GauntletError(f"cannot load {path}: {type(exc).__name__}: {exc}") from exc
    if not isinstance(data, dict):
        raise GauntletError(f"{path} is not a JSON object")
    return data


def _load_materialized_rubric() -> dict[str, Any]:
    """Materialize the immutable V1 rubric plus the committed V2 overlay."""

    overlay = _load_json(RUBRIC_PATH)
    base_spec = overlay.get("base_rubric")
    if not isinstance(base_spec, Mapping):
        raise GauntletError("V2 rubric has no base_rubric custody block")
    declared_base = ROOT / str(base_spec.get("path", ""))
    if declared_base.resolve() != BASE_RUBRIC_PATH.resolve():
        raise GauntletError("V2 rubric base path does not match the immutable V1 path")

    rubric = copy.deepcopy(_load_json(BASE_RUBRIC_PATH))
    rubric["schema"] = "dharma_swarm.dharmagraph_parity_gauntlet.rubric.v2"
    rubric["status"] = str(overlay["status"])
    rubric["frozen_on"] = str(overlay["frozen_on"])
    rubric["subject"] = str(overlay["subject"])
    rubric["base_rubric"] = copy.deepcopy(base_spec)
    rubric["supersedes"] = copy.deepcopy(overlay["supersedes"])
    rubric["completeness_critic"] = copy.deepcopy(overlay["completeness_critic"])
    rubric["operator_ratified_exclusions"] = copy.deepcopy(
        overlay.get("operator_ratified_exclusions", [])
    )

    rows = rubric.get("capabilities")
    if not isinstance(rows, list):
        raise GauntletError("V1 base rubric has no capability list")
    row_lookup = {str(row["id"]): row for row in rows}
    for row_id, facets in overlay.get("facet_additions", {}).items():
        if row_id not in row_lookup or not isinstance(facets, list):
            raise GauntletError(f"invalid V2 facet addition for {row_id}")
        existing = row_lookup[row_id].get("facets")
        if not isinstance(existing, list):
            raise GauntletError(f"base row {row_id} has no facet list")
        for facet in facets:
            if facet in existing:
                raise GauntletError(f"V2 facet {row_id}/{facet} already exists")
            existing.append(str(facet))

    for row_id, update in overlay.get("weight_updates", {}).items():
        if row_id not in row_lookup or not isinstance(update, Mapping):
            raise GauntletError(f"invalid V2 weight update for {row_id}")
        if int(row_lookup[row_id]["weight"]) != int(update.get("from", -1)):
            raise GauntletError(f"V2 weight update base mismatch for {row_id}")
        row_lookup[row_id]["weight"] = int(update["to"])

    additions = overlay.get("capability_additions")
    if not isinstance(additions, list):
        raise GauntletError("V2 rubric has no capability_additions list")
    for addition in additions:
        if (
            not isinstance(addition, Mapping)
            or str(addition.get("id", "")) in row_lookup
        ):
            raise GauntletError("V2 capability addition is invalid or duplicated")
        materialized = copy.deepcopy(dict(addition))
        rows.append(materialized)
        row_lookup[str(materialized["id"])] = materialized

    corpus_additions = overlay.get("corpus_additions")
    if not isinstance(corpus_additions, Mapping):
        raise GauntletError("V2 rubric has no corpus_additions block")
    extra_workloads = corpus_additions.get("new_parametric_workloads", [])
    if not isinstance(extra_workloads, list):
        raise GauntletError("V2 corpus workload additions are invalid")
    rubric["corpus"]["new_parametric_workloads"].extend(extra_workloads)
    rubric["corpus"]["completeness_control"] = copy.deepcopy(
        corpus_additions["completeness_control"]
    )
    rubric["weighting"]["completeness_overlay"] = copy.deepcopy(
        overlay["weighting_assertion"]
    )
    rubric["scope"]["installed_prebuilt"] = (
        "In scope because langgraph-prebuilt is installed with the pinned Python distribution; PB01 carries the coverage floor."
    )
    rubric["prior_scores"]["v1_provisional"] = (
        "VOID_INCOMPLETE_RUBRIC_NO_RESULT_ARTIFACT_COMMITTED"
    )

    assertion = overlay["weighting_assertion"]
    expected_rows = int(assertion["materialized_row_count"])
    expected_total = int(assertion["materialized_total"])
    if (
        len(rows) != expected_rows
        or sum(int(row["weight"]) for row in rows) != expected_total
    ):
        raise GauntletError("V2 rubric materialization count/weight assertion failed")
    return rubric


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return repr(value)


def _rubric_custody(rubric: Mapping[str, Any]) -> dict[str, Any]:
    rel = RUBRIC_PATH.relative_to(ROOT).as_posix()
    commit = _git("log", "-1", "--format=%H", "--", rel)
    if not commit:
        raise GauntletError("rubric has no committing ancestor")
    head = _git("rev-parse", "HEAD")
    if not _git_success("merge-base", "--is-ancestor", commit, head):
        raise GauntletError(f"rubric commit {commit} is not an ancestor of HEAD {head}")
    committed = _git("show", f"{commit}:{rel}")
    current = RUBRIC_PATH.read_text(encoding="utf-8")
    if committed != current.rstrip("\n") and committed + "\n" != current:
        raise GauntletError("rubric bytes changed after their freeze commit")
    dirty = _git("status", "--porcelain", "--", rel)
    if dirty:
        raise GauntletError(f"rubric is dirty after freeze: {dirty}")

    overlay = _load_json(RUBRIC_PATH)
    base_spec = overlay.get("base_rubric", {})
    base_rel = BASE_RUBRIC_PATH.relative_to(ROOT).as_posix()
    base_commit = _git("log", "-1", "--format=%H", "--", base_rel)
    declared_base_commit = str(base_spec.get("freeze_commit_sha", ""))
    if base_commit != declared_base_commit:
        raise GauntletError(
            "V1 base rubric commit does not match the V2 overlay declaration"
        )
    if not _git_success("merge-base", "--is-ancestor", base_commit, head):
        raise GauntletError("V1 base rubric freeze is not an ancestor of HEAD")
    base_committed = _git("show", f"{base_commit}:{base_rel}")
    base_current = BASE_RUBRIC_PATH.read_text(encoding="utf-8")
    if (
        base_committed != base_current.rstrip("\n")
        and base_committed + "\n" != base_current
    ):
        raise GauntletError("V1 base rubric bytes changed after freeze")
    base_dirty = _git("status", "--porcelain", "--", base_rel)
    if base_dirty:
        raise GauntletError(f"V1 base rubric is dirty after freeze: {base_dirty}")
    return {
        "rubric_commit_sha": commit,
        "base_rubric_commit_sha": base_commit,
        "rubric_blob_digest": stable_digest(rubric),
        "head_sha": head,
        "rubric_predates_head": commit != head,
        "rubric_unchanged": True,
    }


def _tracked_relevant_files() -> list[str]:
    tracked = _git("ls-files").splitlines()
    selected: list[str] = []
    for path in tracked:
        if any(
            path == root or path.startswith(root.rstrip("/") + "/")
            for root in RELEVANT_SOURCE_ROOTS
        ):
            selected.append(path)
    return sorted(set(selected))


def _source_tree_digest() -> tuple[str, list[dict[str, str]]]:
    manifest: list[dict[str, str]] = []
    for rel in _tracked_relevant_files():
        path = ROOT / rel
        if path.is_file():
            manifest.append(
                {"path": rel, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            )
    return stable_digest(manifest), manifest


def _load_judge_ratifications(
    path: Path = JUDGE_RATIFICATIONS_PATH,
) -> dict[str, frozenset[str]]:
    """Load the detached exact-digest promotion authority.

    This registry authorizes content-bound attestations after source review;
    it is not cryptographic authentication of the named judge.
    """
    return _normalize_judge_ratifications(_load_json(path))


def _normalize_judge_ratifications(
    payload: Mapping[str, Any],
) -> dict[str, frozenset[str]]:
    if payload.get("schema") != JUDGE_RATIFICATIONS_SCHEMA:
        raise GauntletError("judge ratification registry schema mismatch")
    custody = payload.get("custody")
    if (
        not isinstance(custody, Mapping)
        or custody.get("authority") != "source_review"
        or custody.get("candidate_measurement") != "excluded"
    ):
        raise GauntletError("judge ratification registry custody is malformed")
    raw = payload.get("ratifications")
    if not isinstance(raw, Mapping):
        raise GauntletError("judge ratification registry has no ratifications map")
    normalized: dict[str, frozenset[str]] = {}
    for raw_judge_id, raw_digests in raw.items():
        judge_id = str(raw_judge_id).strip()
        if (
            not judge_id
            or isinstance(raw_digests, (str, bytes))
            or not isinstance(raw_digests, Sequence)
        ):
            raise GauntletError("judge ratification registry entry is malformed")
        digests = frozenset(str(item) for item in raw_digests)
        if not digests or any(
            len(item) != 64 or any(char not in "0123456789abcdef" for char in item)
            for item in digests
        ):
            raise GauntletError(
                f"judge ratification registry has invalid digest for {judge_id!r}"
            )
        normalized[judge_id] = digests
    return normalized


def _assert_judge_trust_root_custody(
    path: Path = JUDGE_RATIFICATIONS_PATH,
) -> tuple[dict[str, str], dict[str, frozenset[str]]]:
    """Return one immutable, committed authority snapshot plus its custody."""
    try:
        rel = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise GauntletError("judge ratification registry escapes repository") from exc
    if rel in _tracked_relevant_files():
        raise GauntletError("judge ratification registry entered candidate measurement")
    if not _git_success("ls-files", "--error-unmatch", "--", rel):
        raise GauntletError("judge ratification registry is not source-controlled")
    dirty = _git("status", "--porcelain", "--", rel)
    if dirty:
        raise GauntletError(f"judge ratification registry is dirty: {dirty}")
    # Authorize from the committed blob, not a second worktree read. This
    # removes the check/use window in which a local writer could swap the
    # allowlist after custody validation.
    blob_sha = _git("rev-parse", f"HEAD:{rel}")
    committed = _git("cat-file", "blob", blob_sha)
    try:
        payload = json.loads(committed)
    except json.JSONDecodeError as exc:
        raise GauntletError(
            "committed judge ratification registry is invalid JSON"
        ) from exc
    if not isinstance(payload, Mapping):
        raise GauntletError("committed judge ratification registry is not an object")
    ratifications = _normalize_judge_ratifications(payload)
    custody = {
        "path": rel,
        "git_blob_sha": blob_sha,
        "sha256": hashlib.sha256(committed.encode("utf-8")).hexdigest(),
    }
    return custody, ratifications


def _assert_relevant_source_clean() -> None:
    dirty = _git("status", "--porcelain", "--", *RELEVANT_SOURCE_ROOTS)
    if dirty:
        raise GauntletError(
            "relevant gauntlet source is dirty; commit code before grading: "
            + dirty.replace("\n", "; ")
        )


def _validate_rubric(rubric: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = rubric.get("capabilities")
    if not isinstance(rows, list) or not rows:
        raise GauntletError("rubric capabilities must be a non-empty list")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    total = 0
    for item in rows:
        if not isinstance(item, dict):
            raise GauntletError("rubric capability row is not an object")
        row_id = str(item.get("id", ""))
        if not row_id or row_id in seen:
            raise GauntletError(f"duplicate or empty rubric row id: {row_id!r}")
        seen.add(row_id)
        weight = int(item.get("weight", -1))
        if weight <= 0:
            raise GauntletError(f"rubric row {row_id} has invalid weight {weight}")
        facets = item.get("facets")
        if not isinstance(facets, list) or not facets:
            raise GauntletError(f"rubric row {row_id} has no facets")
        total += weight
        normalized.append(dict(item))
    expected = int(rubric.get("weighting", {}).get("total_weight", -1))
    if total != expected or total != 100:
        raise GauntletError(
            f"rubric weights sum to {total}, expected {expected} and 100"
        )
    return normalized


def _ratified_exclusion_ids(exclusions: Any) -> frozenset[str]:
    ids: set[str] = set()
    for entry in exclusions or []:
        if isinstance(entry, str) and entry.strip():
            ids.add(entry.strip())
        elif isinstance(entry, Mapping):
            for key in ("capability_id", "row_id", "id"):
                value = entry.get(key)
                if isinstance(value, str) and value.strip():
                    ids.add(value.strip())
    return frozenset(ids)


def _normalize_capability(
    row: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    ratified_ids: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    row_id = str(row["id"])
    points = observation.get("points")
    if points not in (0, 1, 2, "N/A"):
        raise GauntletError(f"probe {row_id} returned invalid points {points!r}")
    if points == "N/A":
        citation = observation.get("operator_ratified_non_goal")
        if not isinstance(citation, str) or not citation.strip():
            points = 0
        elif row_id not in ratified_ids:
            # na_rule (frozen, V1:48): N/A only via a frozen operator-ratified
            # exclusion citing the exact row id. Free-text rationale from the
            # builder or judge is exactly the self-declaration the rule voids.
            raise GauntletError(
                f"probe {row_id} claims N/A without a frozen operator-ratified "
                "exclusion citing this row id (na_rule: self-declared "
                "rationales score 0)"
            )
    expected_facets = {str(item) for item in row["facets"]}
    facets = observation.get("facets")
    if not isinstance(facets, Mapping):
        raise GauntletError(f"probe {row_id} returned no facet mapping")
    observed_facets = {str(key) for key in facets}
    missing = expected_facets - observed_facets
    extra = observed_facets - expected_facets
    if missing or extra:
        raise GauntletError(
            f"probe {row_id} changed frozen facets: "
            f"missing={sorted(missing)} extra={sorted(extra)}"
        )
    allowed = {"pass", "partial", "missing", "fail"}
    statuses: list[str] = []
    for facet_id in expected_facets:
        cell = facets[facet_id]
        if not isinstance(cell, Mapping) or cell.get("status") not in allowed:
            raise GauntletError(f"probe {row_id}/{facet_id} has invalid status")
        statuses.append(str(cell["status"]))
        evidence = cell.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise GauntletError(f"probe {row_id}/{facet_id} has no executed evidence")
        for item in evidence:
            if not isinstance(item, Mapping):
                raise GauntletError(f"probe {row_id}/{facet_id} has malformed evidence")
            required = ("kind", "id", "command_or_probe", "outcome")
            if any(not str(item.get(field, "")).strip() for field in required):
                raise GauntletError(
                    f"probe {row_id}/{facet_id} has incomplete executed evidence"
                )
            citations = item.get("citations")
            if not isinstance(citations, list) or not any(
                isinstance(citation, str) and citation.strip() for citation in citations
            ):
                raise GauntletError(f"probe {row_id}/{facet_id} has no source citation")
            if "dharma" not in item or "langgraph" not in item:
                raise GauntletError(
                    f"probe {row_id}/{facet_id} has no two-arm/absence output"
                )
    if points != "N/A":
        mechanical_points = (
            2
            if all(status == "pass" for status in statuses)
            else 1
            if any(status == "pass" for status in statuses)
            else 0
        )
        if int(points) != mechanical_points:
            raise GauntletError(
                f"probe {row_id} points {points} disagree with frozen facet rule "
                f"({mechanical_points})"
            )
    normalized = dict(_jsonable(observation))
    normalized.update(
        {
            "id": row_id,
            "name": str(row["name"]),
            "class": str(row["class"]),
            "weight": int(row["weight"]),
            "gap_card": str(row["gap_card"]),
            "points": points,
        }
    )
    return normalized


def _score(rows: Sequence[Mapping[str, Any]]) -> tuple[Decimal, int]:
    earned = Decimal("0")
    denominator = 0
    for row in rows:
        if row["points"] == "N/A":
            continue
        weight = int(row["weight"])
        denominator += weight
        earned += Decimal(weight) * Decimal(int(row["points"])) / Decimal(2)
    if denominator <= 0:
        raise GauntletError("all rubric rows are N/A")
    normalized = (earned / Decimal(denominator) * Decimal(100)).quantize(
        Decimal("0.01")
    )
    return normalized, denominator


def _stable_capability(row: Mapping[str, Any]) -> dict[str, Any]:
    facets = row.get("facets", {})
    return {
        "id": row["id"],
        "weight": row["weight"],
        "points": row["points"],
        "verdict": row.get("verdict", ""),
        "facet_statuses": {
            str(key): str(value.get("status", ""))
            for key, value in sorted(facets.items())
        },
        "caveats": sorted(str(item) for item in row.get("caveats", [])),
    }


def _receipt_digest(receipt: Mapping[str, Any]) -> str:
    return stable_digest(
        {key: value for key, value in receipt.items() if key != "digest"}
    )


def _judge_attestation_digest(
    *,
    judge_id: str,
    judge_stable_digest: str,
    builder_receipt_digest: str,
    rubric_commit_sha: str,
) -> str:
    return stable_digest(
        {
            "attestation_role": "judge",
            "judge_id": judge_id,
            "judge_stable_digest": judge_stable_digest,
            "builder_receipt_digest": builder_receipt_digest,
            "rubric_commit_sha": rubric_commit_sha,
        }
    )


def _validate_receipt_digest(receipt: Mapping[str, Any]) -> None:
    stored = receipt.get("digest")
    if not isinstance(stored, str) or stored != _receipt_digest(receipt):
        raise GauntletError("receipt digest mismatch")
    stable_core = receipt.get("stable_core")
    stable = receipt.get("stable_digest")
    if not isinstance(stable_core, Mapping) or stable != stable_digest(stable_core):
        raise GauntletError("receipt stable_digest mismatch")


def _build_receipt(
    *,
    rubric: Mapping[str, Any],
    role: str,
    seed: int,
    performance_iterations: int,
    judge_id: str,
    latest_drift: bool,
) -> dict[str, Any]:
    rows = _validate_rubric(rubric)
    _assert_relevant_source_clean()
    custody = _rubric_custody(rubric)
    if not custody["rubric_predates_head"]:
        raise GauntletError(
            "rubric freeze commit must predate the committed gauntlet implementation"
        )

    target = rubric.get("comparison_target")
    if not isinstance(target, Mapping):
        raise GauntletError("rubric comparison_target is missing")
    environment = {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "langgraph_version": _package_version("langgraph"),
        "langgraph_checkpoint_version": _package_version("langgraph-checkpoint"),
        "langgraph_checkpoint_sqlite_version": _package_version(
            "langgraph-checkpoint-sqlite"
        ),
    }
    expected_versions = {
        "langgraph_version": str(target.get("version", "")),
        "langgraph_checkpoint_version": str(
            target.get("checkpoint_distribution", "")
        ).partition("==")[2],
        "langgraph_checkpoint_sqlite_version": str(
            target.get("persistent_checkpoint_adapter", "")
        ).partition("==")[2],
    }
    for field, expected in expected_versions.items():
        if not expected or environment[field] != expected:
            raise GauntletError(
                f"comparison environment mismatch for {field}: "
                f"installed={environment[field]!r} expected={expected!r}"
            )

    source_digest, source_manifest = _source_tree_digest()
    raw = _jsonable(
        run_capability_probes(
            rubric, seed=seed, performance_iterations=performance_iterations
        )
    )
    _assert_relevant_source_clean()
    source_digest_after, _ = _source_tree_digest()
    if source_digest_after != source_digest:
        raise GauntletError("relevant source changed while the gauntlet was executing")
    if not isinstance(raw, Mapping):
        raise GauntletError("harness returned a non-mapping result")
    observations = raw.get("capabilities")
    if not isinstance(observations, Mapping):
        raise GauntletError("harness returned no capability observations")
    expected_ids = {str(row["id"]) for row in rows}
    observed_ids = {str(row_id) for row_id in observations}
    if observed_ids != expected_ids:
        raise GauntletError(
            f"probe/rubric row mismatch: missing={sorted(expected_ids - observed_ids)} "
            f"extra={sorted(observed_ids - expected_ids)}"
        )
    ratified_ids = _ratified_exclusion_ids(rubric.get("operator_ratified_exclusions"))
    capabilities = [
        _normalize_capability(
            row, observations[str(row["id"])], ratified_ids=ratified_ids
        )
        for row in rows
    ]
    control = raw.get("control")
    if not isinstance(control, Mapping):
        raise GauntletError("harness returned no broken control")
    control_spec = rubric.get("corpus", {}).get("broken_control", {})
    if (
        control.get("id") != control_spec.get("id")
        or not bool(control.get("must_fail"))
        or control.get("comparison_verdict") == "parity"
        or not isinstance(control.get("evidence"), list)
        or not control.get("evidence")
        or not bool(control.get("expected_failure_observed"))
    ):
        raise GauntletError("CTRL01 did not fail as required; harness is invalid")
    completeness = raw.get("completeness_control")
    completeness_spec = rubric.get("corpus", {}).get("completeness_control", {})
    if (
        not isinstance(completeness, Mapping)
        or completeness.get("id") != completeness_spec.get("id")
        or not bool(completeness.get("expected_observation_present"))
    ):
        raise GauntletError("COMPLETE01 completeness control is missing")

    corpus = raw.get("corpus")
    expected_task_ids = list(rubric.get("corpus", {}).get("june_tasks", []))
    if (
        not isinstance(corpus, Mapping)
        or not bool(corpus.get("supplementary_only"))
        or bool(corpus.get("score_inherited"))
        or corpus.get("task_count") != len(expected_task_ids)
        or corpus.get("task_ids") != expected_task_ids
        or int(corpus.get("executed_result_count", 0)) < len(expected_task_ids)
    ):
        raise GauntletError("26-task supplementary corpus custody mismatch")

    performance = raw.get("performance")
    expected_performance = set(
        rubric.get("corpus", {}).get("performance_workloads", [])
    )
    if (
        not isinstance(performance, Mapping)
        or performance.get("iterations") != performance_iterations
        or bool(performance.get("timing_decides_semantic_parity"))
        or set(performance.get("workloads", {})) != expected_performance
    ):
        raise GauntletError("three-workload performance evidence mismatch")

    raw_evidence = raw.get("raw_evidence")
    expected_scenarios = set(
        rubric.get("corpus", {}).get("existing_real_oracle_scenarios", [])
    )
    if (
        not isinstance(raw_evidence, Mapping)
        or set(raw_evidence.get("applications", {})) != expected_scenarios
        or len(raw_evidence.get("surface_probes", {}))
        != sum(len(row["facets"]) for row in rows)
    ):
        raise GauntletError("application/public-surface evidence inventory mismatch")
    score, denominator = _score(capabilities)
    gaps = [
        {
            "capability_id": row["id"],
            "name": row["name"],
            "points": row["points"],
            "weight": row["weight"],
            "gap_card": row["gap_card"],
            "closure_condition": "All frozen facets prove 2/2 in an independent judge rerun.",
        }
        for row in capabilities
        if row["points"] != "N/A" and int(row["points"]) < 2
    ]
    drift_check = (
        _run_latest_stable_drift(rubric, seed, raw)
        if latest_drift
        else {
            "target": rubric["non_gating_drift_target"],
            "installed_grade_target": environment["langgraph_version"],
            "latest_target_differs": (
                str(rubric["non_gating_drift_target"].get("version", ""))
                != environment["langgraph_version"]
            ),
            "behavioral_execution_against_latest": False,
            "status": "NOT_REPLAYED_NON_GATING",
            "gating": False,
            "finding": (
                "The builder receipt carries the executed latest-stable drift run; "
                "routine --check replays only the frozen grade target."
            ),
        }
    )
    _assert_relevant_source_clean()
    drift_source_digest, _ = _source_tree_digest()
    if drift_source_digest != source_digest:
        raise GauntletError("relevant source changed during latest-stable drift probe")
    stable_core = {
        "schema": "dharma_swarm.dharmagraph_parity_receipt.stable.v1",
        "rubric_schema": rubric["schema"],
        "rubric_commit_sha": custody["rubric_commit_sha"],
        "rubric_blob_digest": custody["rubric_blob_digest"],
        "target": rubric["comparison_target"],
        "source_tree_digest": source_digest,
        "seed": seed,
        "capabilities": [_stable_capability(row) for row in capabilities],
        "control": {
            "id": control.get("id"),
            "must_fail": bool(control.get("must_fail")),
            "comparison_verdict": control.get("comparison_verdict"),
            "expected_failure_observed": bool(control.get("expected_failure_observed")),
        },
        "completeness_control": {
            "id": completeness.get("id"),
            "expected_observation_present": bool(
                completeness.get("expected_observation_present")
            ),
        },
        "score": f"{score:.2f}",
        "weight_denominator": denominator,
        "gap_ids": [gap["capability_id"] for gap in gaps],
        "closeout_blocked": score < Decimal("100"),
    }
    receipt: dict[str, Any] = {
        "schema": "dharma_swarm.dharmagraph_parity_receipt.v1",
        "role": role,
        "observed_at": _utc_now(),
        "claim_boundary": "CLOSED_NOT_PROD; this receipt grades engine parity only.",
        "verdict": "FINISHED" if score == Decimal("100") else "NOT_FINISHED",
        "closeout_blocked": score < Decimal("100"),
        "score": {
            "earned": f"{score:.2f}",
            "possible": "100.00",
            "display": f"{score:.2f}/100",
        },
        "rubric": custody,
        "environment": environment,
        "shas": {
            "dharma_git_sha": custody["head_sha"],
            "langgraph_git_sha": rubric["comparison_target"]["git_sha"],
            "rubric_commit_sha": custody["rubric_commit_sha"],
        },
        "non_gating_drift_check": drift_check,
        "source_tree_digest": source_digest,
        "source_manifest": source_manifest,
        "capabilities": capabilities,
        "gaps": gaps,
        "control": control,
        "completeness_control": completeness,
        "performance": raw.get("performance", {}),
        "corpus": raw.get("corpus", {}),
        "raw_evidence": raw.get("raw_evidence", {}),
        "stable_core": stable_core,
        "stable_digest": stable_digest(stable_core),
    }
    if role == "judge":
        if not judge_id.strip():
            raise GauntletError("judge emit requires --judge-id")
        builder = _load_json(BUILDER_RECEIPT)
        _validate_receipt_digest(builder)
        match = (
            builder.get("stable_digest") == receipt["stable_digest"]
            and builder.get("score", {}).get("earned") == receipt["score"]["earned"]
        )
        receipt["judge"] = {
            "judge_id": judge_id,
            "attestation": (
                "I independently re-ran the committed gauntlet and compared the "
                "mechanical grade to the builder receipt."
            ),
            "builder_receipt_digest": builder["digest"],
            "builder_stable_digest": builder["stable_digest"],
            "reconciliation": "MATCH" if match else "DISCREPANCY",
            "discrepancy_is_finding": not match,
        }
        receipt["judge"]["signature"] = _judge_attestation_digest(
            judge_id=judge_id,
            judge_stable_digest=receipt["stable_digest"],
            builder_receipt_digest=builder["digest"],
            rubric_commit_sha=custody["rubric_commit_sha"],
        )
    receipt["digest"] = _receipt_digest(receipt)
    return receipt


def _evidence_pointer(row: Mapping[str, Any]) -> str:
    pointers: list[str] = []
    for facet_id, cell in sorted(row.get("facets", {}).items()):
        for evidence in cell.get("evidence", []):
            if isinstance(evidence, Mapping):
                evidence_id = (
                    evidence.get("id") or evidence.get("probe") or evidence.get("kind")
                )
                if evidence_id:
                    pointers.append(f"{facet_id}:{evidence_id}")
                    break
        if len(pointers) >= 3:
            break
    return ", ".join(pointers) if pointers else "missing evidence"


def render_matrix(receipt: Mapping[str, Any]) -> str:
    score = str(receipt["score"]["display"])
    gaps = receipt.get("gaps", [])
    lines = [
        f"# DharmaGraph x LangGraph parity: {score}",
        "",
        f"**Verdict: {receipt['verdict']}. Closeout blocked: {str(receipt['closeout_blocked']).lower()}.**",
        "",
        (
            f"Target: LangGraph `{receipt['environment']['langgraph_version']}` "
            f"at tag SHA `{receipt['shas']['langgraph_git_sha']}`. Rubric commit: "
            f"`{receipt['rubric']['rubric_commit_sha']}`. Dharma SHA: "
            f"`{receipt['shas']['dharma_git_sha']}`."
        ),
        "",
        "## Gaps",
        "",
    ]
    if gaps:
        lines.extend(
            f"- `{gap['capability_id']}` — {gap['name']} ({gap['points']}/2, weight {gap['weight']}); card `{gap['gap_card']}`."
            for gap in gaps
        )
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Capability matrix",
            "",
            "| ID | Capability | Weight | Points | Contribution | Evidence | Caveats |",
            "|---|---|---:|---:|---:|---|---|",
        ]
    )
    for row in receipt.get("capabilities", []):
        points = row["points"]
        contribution = (
            "N/A"
            if points == "N/A"
            else f"{Decimal(int(row['weight'])) * Decimal(int(points)) / Decimal(2):.2f}"
        )
        caveats = "; ".join(str(item) for item in row.get("caveats", [])) or "—"
        lines.append(
            f"| `{row['id']}` | {row['name']} | {row['weight']} | {points} | "
            f"{contribution} | {_evidence_pointer(row)} | {caveats} |"
        )
    control = receipt.get("control", {})
    completeness = receipt.get("completeness_control", {})
    drift = receipt.get("non_gating_drift_check", {})
    lines.extend(
        [
            "",
            "## Harness integrity",
            "",
            f"- Broken control `{control.get('id', 'CTRL01')}` verdict: `{control.get('comparison_verdict', 'missing')}`.",
            f"- Required failure observed: `{str(bool(control.get('expected_failure_observed'))).lower()}`.",
            f"- Completeness control `{completeness.get('id', 'COMPLETE01')}` recorded: `{str(bool(completeness.get('expected_observation_present'))).lower()}`.",
            "",
            "## Latest-stable drift (reported, non-gating)",
            "",
            f"- Status: `{drift.get('status', 'missing')}`.",
            f"- Behavioral execution: `{str(bool(drift.get('behavioral_execution_against_latest'))).lower()}`.",
            f"- Target: `{drift.get('target', {}).get('version', 'missing')}`; frozen grade remains `{receipt['environment']['langgraph_version']}`.",
            "",
            "## Performance (reported, not a win requirement)",
            "",
            "```json",
            json.dumps(receipt.get("performance", {}), indent=2, sort_keys=True),
            "```",
            "",
            f"Receipt stable digest: `{receipt['stable_digest']}`.",
            "",
        ]
    )
    return "\n".join(lines)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def emit(args: argparse.Namespace) -> int:
    rubric = _load_materialized_rubric()
    receipt = _build_receipt(
        rubric=rubric,
        role=args.role,
        seed=args.seed,
        performance_iterations=args.performance_iterations,
        judge_id=args.judge_id,
        latest_drift=args.latest_drift,
    )
    default = BUILDER_RECEIPT if args.role == "builder" else JUDGE_RECEIPT
    output = Path(args.output).resolve() if args.output else default
    _write(output, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    if args.role == "builder":
        matrix = Path(args.matrix).resolve() if args.matrix else MATRIX_PATH
        _write(matrix, render_matrix(receipt))
    print(
        json.dumps(
            {
                "role": args.role,
                "score": receipt["score"]["display"],
                "gaps": len(receipt["gaps"]),
                "control_failed_as_required": receipt["control"][
                    "expected_failure_observed"
                ],
                "receipt": str(output),
                "digest": receipt["digest"],
            },
            sort_keys=True,
        )
    )
    if args.role == "judge" and receipt["judge"]["reconciliation"] != "MATCH":
        # The receipt is still written — a discrepancy is itself a reportable
        # finding — but the exit code must make it mechanically ungreen.
        return 1
    return 0


def _presentation_findings(stored: Mapping[str, Any]) -> list[str]:
    """The human-facing grade fields are derived, not sealed — re-derive them
    from the sealed core so a receipt whose presentation was edited after
    sealing (verdict, display, gap list, closeout flag) cannot replay PASS."""
    core = stored.get("stable_core", {})
    findings: list[str] = []
    sealed_score = str(core.get("score", ""))
    if stored.get("score", {}).get("earned") != sealed_score:
        findings.append("presented earned score diverges from sealed core")
    if stored.get("score", {}).get("display") != f"{sealed_score}/100":
        findings.append("presented score display diverges from sealed core")
    expected_verdict = "FINISHED" if sealed_score == "100.00" else "NOT_FINISHED"
    if stored.get("verdict") != expected_verdict:
        findings.append("presented verdict diverges from sealed core")
    if bool(stored.get("closeout_blocked")) != bool(core.get("closeout_blocked")):
        findings.append("presented closeout_blocked diverges from sealed core")
    presented_gaps = [gap.get("capability_id") for gap in stored.get("gaps", [])]
    if presented_gaps != list(core.get("gap_ids", [])):
        findings.append("presented gap list diverges from sealed core")
    return findings


def _judge_findings(
    stored: Mapping[str, Any],
    judge: Mapping[str, Any],
    *,
    ratifications: Mapping[str, frozenset[str]] | None = None,
) -> list[str]:
    findings: list[str] = []
    if stored.get("role") != "builder":
        findings.append("stored receipt role is not builder")
    if judge.get("role") != "judge":
        findings.append("judge receipt role is not judge")
    try:
        _validate_receipt_digest(judge)
    except GauntletError:
        return ["judge receipt digest invalid"]
    judge_block = judge.get("judge", {})
    if not isinstance(judge_block, Mapping):
        return ["judge attestation block is malformed"]
    judge_id = str(judge_block.get("judge_id", ""))
    rubric = judge.get("rubric", {})
    rubric_commit_sha = (
        str(rubric.get("rubric_commit_sha", "")) if isinstance(rubric, Mapping) else ""
    )
    expected_signature = _judge_attestation_digest(
        judge_id=judge_id,
        judge_stable_digest=str(judge.get("stable_digest", "")),
        builder_receipt_digest=str(judge_block.get("builder_receipt_digest", "")),
        rubric_commit_sha=rubric_commit_sha,
    )
    signature = judge_block.get("signature")
    if not isinstance(signature, str) or not hmac.compare_digest(
        signature, expected_signature
    ):
        findings.append("judge attestation digest does not match its content")
    authority = _load_judge_ratifications() if ratifications is None else ratifications
    ratified = authority.get(judge_id, frozenset())
    if not isinstance(signature, str) or signature not in ratified:
        findings.append("judge attestation digest is not source-ratified")
    if judge_block.get("builder_receipt_digest") != stored.get("digest"):
        findings.append("judge receipt does not bind the stored builder receipt")
    if judge_block.get("builder_stable_digest") != stored.get("stable_digest"):
        findings.append("judge attestation does not bind the builder stable digest")
    if judge.get("stable_digest") != stored.get("stable_digest"):
        findings.append("judge stable digest diverges from builder")
    if judge_block.get("reconciliation") != "MATCH":
        findings.append("judge reconciliation is not MATCH")
    if judge.get("score", {}).get("earned") != stored.get("score", {}).get("earned"):
        findings.append("judge score diverges from builder")
    return findings


def check(args: argparse.Namespace) -> int:
    stored = _load_json(BUILDER_RECEIPT)
    _validate_receipt_digest(stored)
    rubric = _load_materialized_rubric()
    replay = _build_receipt(
        rubric=rubric,
        role="builder",
        seed=args.seed,
        performance_iterations=args.performance_iterations,
        judge_id="",
        latest_drift=False,
    )
    findings: list[str] = []
    findings.extend(_presentation_findings(stored))
    if not JUDGE_RECEIPT.exists():
        findings.append("judge receipt is missing")
    else:
        _, ratifications = _assert_judge_trust_root_custody()
        findings.extend(
            _judge_findings(
                stored,
                _load_json(JUDGE_RECEIPT),
                ratifications=ratifications,
            )
        )
    if replay["stable_digest"] != stored["stable_digest"]:
        findings.append("stable semantic digest changed")
    if replay["score"]["earned"] != stored["score"]["earned"]:
        findings.append("score changed")
    if not bool(replay["control"].get("expected_failure_observed")):
        findings.append("broken control did not fail")
    expected_matrix = render_matrix(stored)
    try:
        actual_matrix = MATRIX_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"matrix unreadable: {type(exc).__name__}")
    else:
        if actual_matrix != expected_matrix:
            findings.append("matrix does not match stored builder receipt")
    result = {
        "check": "PASS" if not findings else "FAIL",
        "score": stored["score"]["display"],
        "gaps": len(stored.get("gaps", [])),
        "findings": findings,
        "stored_digest": stored["digest"],
        "replay_stable_digest": replay["stable_digest"],
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if not findings else 1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emit", action="store_true", help="execute and write a receipt")
    mode.add_argument(
        "--check", action="store_true", help="replay and validate builder evidence"
    )
    parser.add_argument("--role", choices=("builder", "judge"), default="builder")
    parser.add_argument("--output", help="receipt output path")
    parser.add_argument("--matrix", help="builder matrix output path")
    parser.add_argument("--judge-id", default=os.environ.get("DHARMA_JUDGE_ID", ""))
    parser.add_argument("--seed", type=int, default=20260711)
    parser.add_argument("--performance-iterations", type=int, default=5)
    parser.add_argument(
        "--latest-drift",
        action="store_true",
        help="also run the frozen non-gating latest-stable surface/outcome probe",
    )
    args = parser.parse_args(argv)
    if args.performance_iterations < 1:
        parser.error("--performance-iterations must be >= 1")
    if args.check and args.role != "builder":
        parser.error("--check validates the builder receipt; omit --role")
    if args.check and args.latest_drift:
        parser.error("--latest-drift is an emit-only non-gating probe")
    if args.emit and args.role == "judge" and not args.judge_id.strip():
        parser.error("judge emit requires --judge-id or DHARMA_JUDGE_ID")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return check(args) if args.check else emit(args)
    except GauntletError as exc:
        print(json.dumps({"check": "FAIL", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
