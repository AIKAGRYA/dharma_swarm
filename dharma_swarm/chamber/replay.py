"""Executable V0 replay around the real RunCheckpoint.fork seam.

The chamber registers one scenario and one corrected control. It is not a
scheduler, provider harness, network simulator, or authority source.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib.abc import SourceLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from typing import Any, Sequence, cast

from dharma_swarm.chamber.replay_contract import (
    FORK_BUNDLE_ID,
    FORK_CONTROL_CANDIDATE_ID,
    FORK_PROPERTY_ID,
    FORK_SCENARIO_ID,
    FORK_SPECIMEN_CANDIDATE_ID,
    REPLAY_EXECUTED_SOURCE_PATHS,
    REQUIRED_MANIFEST_PATHS,
    SINGLE_REPLAY_SCHEMA,
    ChoiceV1,
    ManifestEntryV1,
    ReplayBundleV1,
    ReplayExpectationV1,
    ReplayValidationError,
    WorldV1,
    validate_bundle_contract,
    validate_world_contract,
)
from dharma_swarm.chamber.traces import stable_digest


@dataclass(frozen=True, slots=True)
class ScenarioObservation:
    strategy: str
    original_parent_values: tuple[Any, ...]
    parent_values: tuple[Any, ...]
    child_values: tuple[Any, ...]
    nested_object_aliased: bool
    property_verdicts: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "original_parent_values": list(self.original_parent_values),
            "parent_values": list(self.parent_values),
            "child_values": list(self.child_values),
            "nested_object_aliased": self.nested_object_aliased,
            "property_verdicts": dict(self.property_verdicts),
        }

    @property
    def semantic_digest(self) -> str:
        return stable_digest(self.to_dict())


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_for(repo_root: Path) -> tuple[ManifestEntryV1, ...]:
    root = repo_root.resolve()
    entries: list[ManifestEntryV1] = []
    for relative in REQUIRED_MANIFEST_PATHS:
        path = root / relative
        if not path.is_file():
            raise ReplayValidationError(f"manifest input missing: {relative}")
        entries.append(ManifestEntryV1(relative, _sha256_file(path)))
    return tuple(entries)


def _source_revision_for(
    repo_root: Path,
    manifest: tuple[ManifestEntryV1, ...],
) -> str:
    head = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    revision = head.stdout.strip()
    if head.returncode != 0 or len(revision) != 40:
        return "WORKTREE"
    for entry in manifest:
        blob = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{revision}:{entry.path}"],
            capture_output=True,
            check=False,
        )
        if blob.returncode != 0 or hashlib.sha256(blob.stdout).hexdigest() != entry.sha256:
            return "WORKTREE"
    return revision


def _validated_manifest_snapshot(
    bundle: ReplayBundleV1,
    repo_root: Path,
) -> dict[str, bytes]:
    validate_bundle_contract(bundle)
    expected_paths = tuple(sorted(REQUIRED_MANIFEST_PATHS))
    actual_paths = tuple(sorted(entry.path for entry in bundle.manifest))
    if actual_paths != expected_paths or len(set(actual_paths)) != len(actual_paths):
        raise ReplayValidationError(
            f"manifest paths are not exact: expected={expected_paths}, actual={actual_paths}"
        )
    root = repo_root.resolve()
    try:
        snapshot = {entry.path: (root / entry.path).read_bytes() for entry in bundle.manifest}
    except OSError as exc:
        raise ReplayValidationError("manifest input became unreadable") from exc
    actual = {path: hashlib.sha256(source).hexdigest() for path, source in snapshot.items()}
    declared = {entry.path: entry.sha256 for entry in bundle.manifest}
    drift = {
        path: {"expected": declared[path], "actual": actual[path]}
        for path in sorted(declared)
        if actual[path] != declared[path]
    }
    if drift:
        raise ReplayValidationError(f"manifest scope drift: {drift}")
    if bundle.source_revision != "WORKTREE":
        object_type = subprocess.run(
            ["git", "-C", str(repo_root), "cat-file", "-t", bundle.source_revision],
            capture_output=True,
            text=True,
            check=False,
        )
        if object_type.returncode != 0 or object_type.stdout.strip() != "commit":
            raise ReplayValidationError("source revision is not a git commit")
        for entry in bundle.manifest:
            blob = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "show",
                    f"{bundle.source_revision}:{entry.path}",
                ],
                capture_output=True,
                check=False,
            )
            if (
                blob.returncode != 0
                or hashlib.sha256(blob.stdout).hexdigest() != entry.sha256
            ):
                raise ReplayValidationError(
                    f"source revision does not bind manifest entry: {entry.path}"
                )
    return snapshot


def validate_manifest(bundle: ReplayBundleV1, repo_root: Path) -> None:
    _validated_manifest_snapshot(bundle, repo_root)


def _fork_world(strategy: str) -> WorldV1:
    return WorldV1(
        scenario_id=FORK_SCENARIO_ID,
        fixtures={
            "checkpoint": {
                "graph_run_id": "parent-run",
                "graph_id": "fixture-graph",
                "superstep": 1,
                "state_digest": "fixture-state-digest",
                "channels": {"messages": {"values": ["parent-only"]}},
                "versions_seen": {"node-a": {"messages": 1}},
            },
            "child_run_id": "child-run",
        },
        choices=(
            ChoiceV1("fork_strategy", strategy),
            ChoiceV1("append_value", "child-only"),
        ),
        faults=(),
        activated_properties=(FORK_PROPERTY_ID,),
        declared_nondeterminism=(),
    )


class _SnapshotSourceLoader(SourceLoader):
    """Execute one immutable source snapshot without rereading its path."""

    def __init__(self, name: str, source: bytes, source_path: Path) -> None:
        self._name = name
        self._source = source
        self._source_path = source_path

    def get_filename(self, fullname: str) -> str:
        if fullname != self._name:
            raise ImportError(f"snapshot loader cannot serve {fullname!r}")
        return str(self._source_path)

    def get_data(self, path: str) -> bytes:
        if Path(path) != self._source_path:
            raise OSError(f"snapshot loader refuses undeclared path: {path}")
        return self._source

    def path_stats(self, path: str) -> dict[str, int]:
        raise OSError(f"snapshot loader disables bytecode caching: {path}")


def _run_checkpoint_type(source: bytes, source_path: Path) -> type[Any]:
    """Load exact graph/types.py bytes without executing graph/__init__.py."""
    try:
        tree = ast.parse(source, filename=str(source_path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        raise ReplayValidationError("graph types source cannot be parsed") from exc
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".", 1)[0])
    unexpected = imports - {"__future__", "dataclasses", "typing"}
    if unexpected:
        raise ReplayValidationError(
            f"graph types source widened its import closure: {sorted(unexpected)}"
        )

    digest = hashlib.sha256(source).hexdigest()
    module_name = f"_dharma_chamber_graph_types_{digest}"
    module = sys.modules.get(module_name)
    if module is None:
        loader = _SnapshotSourceLoader(module_name, source, source_path)
        spec = spec_from_loader(module_name, loader)
        if spec is None:
            raise ReplayValidationError("cannot create graph types module spec")
        module = module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            loader.exec_module(module)
        except BaseException:
            sys.modules.pop(module_name, None)
            raise
    checkpoint = getattr(module, "RunCheckpoint", None)
    if not isinstance(checkpoint, type):
        raise ReplayValidationError("graph types source has no RunCheckpoint type")
    return checkpoint


def _graph_types_source(repo_root: Path) -> tuple[bytes, Path]:
    path = repo_root.resolve() / "dharma_swarm/graph/types.py"
    try:
        return path.read_bytes(), path
    except OSError as exc:
        raise ReplayValidationError("cannot read graph types source") from exc


def execute_world(
    world: WorldV1,
    *,
    graph_types_source: bytes | None = None,
    graph_types_path: Path | None = None,
) -> ScenarioObservation:
    validate_world_contract(world)
    if graph_types_source is None:
        graph_types_source, default_path = _graph_types_source(
            Path(__file__).resolve().parents[2]
        )
        graph_types_path = graph_types_path or default_path
    if graph_types_path is None:
        raise ReplayValidationError("graph types source path is missing")
    RunCheckpoint = _run_checkpoint_type(graph_types_source, graph_types_path)

    checkpoint_raw = cast(dict[str, Any], copy.deepcopy(world.fixtures["checkpoint"]))
    parent = RunCheckpoint(**checkpoint_raw)
    choices = {choice.name: choice.value for choice in world.choices}
    strategy = str(choices["fork_strategy"])
    forked = parent.fork(str(world.fixtures["child_run_id"]))
    if strategy == "production":
        child = forked
    else:
        child = RunCheckpoint(
            graph_run_id=forked.graph_run_id,
            graph_id=forked.graph_id,
            superstep=forked.superstep,
            state_digest=forked.state_digest,
            channels=copy.deepcopy(forked.channels),
            versions_seen=copy.deepcopy(forked.versions_seen),
        )

    parent_values = cast(list[Any], parent.channels["messages"]["values"])
    child_values = cast(list[Any], child.channels["messages"]["values"])
    original = tuple(copy.deepcopy(parent_values))
    child_values.append(copy.deepcopy(choices["append_value"]))
    held = tuple(parent_values) == original
    return ScenarioObservation(
        strategy=strategy,
        original_parent_values=original,
        parent_values=tuple(copy.deepcopy(parent_values)),
        child_values=tuple(copy.deepcopy(child_values)),
        nested_object_aliased=parent_values is child_values,
        property_verdicts={FORK_PROPERTY_ID: held},
    )


def build_fork_alias_bundle(repo_root: Path) -> ReplayBundleV1:
    world, control = _fork_world("production"), _fork_world("deepcopy_control")
    manifest = manifest_for(repo_root)
    graph_source, graph_path = _graph_types_source(repo_root)
    observed = execute_world(
        world,
        graph_types_source=graph_source,
        graph_types_path=graph_path,
    )
    control_observed = execute_world(
        control,
        graph_types_source=graph_source,
        graph_types_path=graph_path,
    )
    if observed.property_verdicts[FORK_PROPERTY_ID] is not False:
        raise ReplayValidationError("fork-alias specimen no longer violates the property")
    if control_observed.property_verdicts[FORK_PROPERTY_ID] is not True:
        raise ReplayValidationError("deep-copy control does not satisfy the property")
    return ReplayBundleV1(
        bundle_id=FORK_BUNDLE_ID,
        scenario_candidate_id=FORK_SPECIMEN_CANDIDATE_ID,
        control_candidate_id=FORK_CONTROL_CANDIDATE_ID,
        source_revision=_source_revision_for(repo_root, manifest),
        world=world,
        control_world=control,
        manifest=manifest,
        expectation=ReplayExpectationV1(
            property_id=FORK_PROPERTY_ID,
            scenario_semantic_digest=observed.semantic_digest,
            control_semantic_digest=control_observed.semantic_digest,
            scenario_verdict=False,
            control_verdict=True,
        ),
    )


def write_bundle(bundle: ReplayBundleV1, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_bundle(path: Path) -> ReplayBundleV1:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReplayValidationError(f"cannot read replay bundle: {exc}") from exc
    return read_bundle_text(text)


def read_bundle_text(text: str) -> ReplayBundleV1:
    try:
        payload = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayValidationError(f"cannot read replay bundle: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReplayValidationError("bundle root is not an object")
    return ReplayBundleV1.from_dict(payload)


def run_bundle_once(bundle: ReplayBundleV1, repo_root: Path) -> dict[str, Any]:
    snapshot = _validated_manifest_snapshot(bundle, repo_root)
    graph_path = repo_root.resolve() / "dharma_swarm/graph/types.py"
    graph_source = snapshot["dharma_swarm/graph/types.py"]
    observed = execute_world(
        bundle.world,
        graph_types_source=graph_source,
        graph_types_path=graph_path,
    )
    control = execute_world(
        bundle.control_world,
        graph_types_source=graph_source,
        graph_types_path=graph_path,
    )
    expected = bundle.expectation
    checks = (
        (observed.semantic_digest, expected.scenario_semantic_digest, "scenario digest"),
        (control.semantic_digest, expected.control_semantic_digest, "control digest"),
        (
            observed.property_verdicts[FORK_PROPERTY_ID],
            expected.scenario_verdict,
            "scenario verdict",
        ),
        (
            control.property_verdicts[FORK_PROPERTY_ID],
            expected.control_verdict,
            "control verdict",
        ),
    )
    for actual, wanted, label in checks:
        if type(actual) is not type(wanted) or actual != wanted:
            raise ReplayValidationError(f"{label} differs from bundle")
    control_valid = (
        observed.property_verdicts[FORK_PROPERTY_ID] is False
        and control.property_verdicts[FORK_PROPERTY_ID] is True
    )
    semantic_digest = stable_digest(
        {
            "scope_digest": bundle.scope_digest,
            "scenario": observed.to_dict(),
            "control": control.to_dict(),
        }
    )
    loaded_sources: set[str] = set()
    root = repo_root.resolve()
    for module in tuple(sys.modules.values()):
        raw_path = getattr(module, "__file__", None)
        if not raw_path:
            continue
        try:
            relative = Path(raw_path).resolve().relative_to(root).as_posix()
        except (OSError, ValueError):
            continue
        if relative.startswith("dharma_swarm/"):
            loaded_sources.add(relative)
    isolated_worker = os.environ.get("DHARMA_CHAMBER_ISOLATED_WORKER") == "1"
    if isolated_worker and tuple(sorted(loaded_sources)) != tuple(
        sorted(REPLAY_EXECUTED_SOURCE_PATHS)
    ):
        raise ReplayValidationError(
            "isolated worker executed unmanifested repository source: "
            f"{sorted(loaded_sources)}"
        )
    loaded_digests: dict[str, str] = {}
    if isolated_worker:
        try:
            raw_digests = json.loads(
                os.environ.get("DHARMA_CHAMBER_LOADED_SOURCE_DIGESTS", "")
            )
        except json.JSONDecodeError as exc:
            raise ReplayValidationError("worker source digest record is invalid") from exc
        if not isinstance(raw_digests, dict) or not all(
            isinstance(path, str) and isinstance(digest, str)
            for path, digest in raw_digests.items()
        ):
            raise ReplayValidationError("worker source digest record has invalid fields")
        loaded_digests = dict(raw_digests)
        loaded_digests["dharma_swarm/graph/types.py"] = hashlib.sha256(
            graph_source
        ).hexdigest()
        declared = {entry.path: entry.sha256 for entry in bundle.manifest}
        if set(loaded_digests) != set(REPLAY_EXECUTED_SOURCE_PATHS) or any(
            declared[path] != digest for path, digest in loaded_digests.items()
        ):
            raise ReplayValidationError("executed source digests differ from manifest")
    git_executable = shutil.which("git") or ""
    git_digest = _sha256_file(Path(git_executable)) if git_executable else ""
    return {
        "schema": SINGLE_REPLAY_SCHEMA,
        "bundle_id": bundle.bundle_id,
        "scenario_candidate_id": bundle.scenario_candidate_id,
        "control_candidate_id": bundle.control_candidate_id,
        "bundle_digest": bundle.to_dict()["bundle_digest"],
        "source_revision": bundle.source_revision,
        "scope_digest": bundle.scope_digest,
        "semantic_digest": semantic_digest,
        "scenario_semantic_digest": observed.semantic_digest,
        "control_semantic_digest": control.semantic_digest,
        "property_verdicts": dict(observed.property_verdicts),
        "control_property_verdicts": dict(control.property_verdicts),
        "control_valid": control_valid,
        "pid": os.getpid(),
        "process_environment": {
            "python_executable": sys.executable,
            "python_version": sys.version.split()[0],
            "python_implementation": platform.python_implementation(),
            "python_hash_seed": os.environ.get("PYTHONHASHSEED", ""),
            "pythonpath": os.environ.get("PYTHONPATH", ""),
            "path": os.environ.get("PATH", ""),
            "home": os.environ.get("HOME", ""),
            "git_executable": git_executable,
            "git_sha256": git_digest,
            "isolated_worker": isolated_worker,
            "loaded_project_sources": sorted(loaded_sources),
            "loaded_project_source_digests": loaded_digests,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    forwarded = list(argv) if argv is not None else sys.argv[1:]
    worker = Path(__file__).resolve().with_name("replay_worker.py")
    os.execv(sys.executable, [sys.executable, str(worker), *forwarded])
    return 127  # pragma: no cover - os.execv either replaces this process or raises


if __name__ == "__main__":  # pragma: no cover - exercised by fresh processes
    raise SystemExit(main())


__all__ = [
    "FORK_BUNDLE_ID",
    "FORK_PROPERTY_ID",
    "FORK_SCENARIO_ID",
    "ChoiceV1",
    "ManifestEntryV1",
    "ReplayBundleV1",
    "ReplayExpectationV1",
    "ReplayValidationError",
    "ScenarioObservation",
    "WorldV1",
    "build_fork_alias_bundle",
    "execute_world",
    "manifest_for",
    "read_bundle",
    "read_bundle_text",
    "run_bundle_once",
    "validate_manifest",
    "write_bundle",
]
