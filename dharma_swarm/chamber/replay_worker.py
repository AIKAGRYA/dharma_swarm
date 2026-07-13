"""Stdlib-only bootstrap for the exact-source chamber replay worker.

Executing a package module normally runs ``dharma_swarm/__init__.py`` and,
for graph types, the broad ``graph/__init__.py`` export surface.  This worker
creates inert package shells and loads only the manifest-declared modules.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import types
from pathlib import Path
from types import ModuleType


def _package(name: str, path: Path) -> None:
    module = types.ModuleType(name)
    module.__package__ = name
    module.__path__ = [str(path)]  # type: ignore[attr-defined]
    sys.modules[name] = module


def _load(name: str, path: Path, digests: dict[str, str], repo_root: Path) -> ModuleType:
    source = path.read_bytes()
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = name.rpartition(".")[0]
    sys.modules[name] = module
    exec(compile(source, str(path), "exec"), module.__dict__)
    digests[path.relative_to(repo_root).as_posix()] = hashlib.sha256(source).hexdigest()
    return module


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-fork-bundle")
    build.add_argument("--repo-root", type=Path, default=Path.cwd())
    once = sub.add_parser("run-once")
    once.add_argument("--bundle", type=Path, required=True)
    once.add_argument("--repo-root", type=Path, required=True)
    once_stdin = sub.add_parser("run-once-stdin")
    once_stdin.add_argument("--repo-root", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--bundle", type=Path, required=True)
    verify.add_argument("--repo-root", type=Path, default=Path.cwd())
    verify.add_argument("--replays", type=int, default=100)
    return parser


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    swarm_root = repo_root / "dharma_swarm"
    chamber_root = swarm_root / "chamber"
    digests: dict[str, str] = {}
    _package("dharma_swarm", swarm_root)
    _package("dharma_swarm.chamber", chamber_root)
    _load("dharma_swarm.chamber.traces", chamber_root / "traces.py", digests, repo_root)
    contract = _load(
        "dharma_swarm.chamber.replay_contract",
        chamber_root / "replay_contract.py",
        digests,
        repo_root,
    )
    replay = _load(
        "dharma_swarm.chamber.replay", chamber_root / "replay.py", digests, repo_root
    )
    verification = _load(
        "dharma_swarm.chamber.verification",
        chamber_root / "verification.py",
        digests,
        repo_root,
    )
    worker_path = Path(__file__).resolve()
    digests[worker_path.relative_to(repo_root).as_posix()] = hashlib.sha256(
        worker_path.read_bytes()
    ).hexdigest()
    os.environ["DHARMA_CHAMBER_LOADED_SOURCE_DIGESTS"] = json.dumps(
        digests, sort_keys=True
    )
    os.environ["DHARMA_CHAMBER_ISOLATED_WORKER"] = "1"
    args = _parser().parse_args(sys.argv[1:])
    try:
        if args.command == "build-fork-bundle":
            payload = replay.build_fork_alias_bundle(args.repo_root).to_dict()
        elif args.command == "run-once":
            payload = replay.run_bundle_once(
                replay.read_bundle(args.bundle), args.repo_root
            )
        elif args.command == "run-once-stdin":
            payload = replay.run_bundle_once(
                replay.read_bundle_text(sys.stdin.read()), args.repo_root
            )
        else:
            payload = verification.verify_in_fresh_processes(
                args.bundle, repo_root=args.repo_root, replays=args.replays
            ).to_dict()
    except contract.ReplayValidationError as exc:
        print(json.dumps({"schema": "dharma_replay_error.v1", "error": str(exc)}))
        return 2
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
