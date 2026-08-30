"""`dgc rudra` commands: run, status, stop.

RUDRA is the supervised mission executor (docs/plans/rudra_v0). These
commands deliberately use the "rudra" name so reproduced execution truth is
never confused with structural `mission-status` inventory.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from dharma_swarm.rudra.contracts import AdmissionError
from dharma_swarm.rudra.runner import MissionRunner, RecoveryRequired
from dharma_swarm.rudra.workcell import JournalConflict, LockHeldError


def _world_locus(repo_path: Path) -> str:
    """World-locus footer: commit, host, branch (docs/governance convention)."""
    def git(*args: str) -> str:
        proc = subprocess.run(
            ["/usr/bin/git", *args], cwd=repo_path,
            capture_output=True, text=True, timeout=15,
        )
        return proc.stdout.strip() if proc.returncode == 0 else "unknown"

    return (
        f"world: commit={git('rev-parse', '--short=12', 'HEAD')} "
        f"host={__import__('platform').node()} branch={git('branch', '--show-current')}"
    )


def cmd_rudra_run(
    mission_yaml: str,
    repo_path: str = ".",
    state_dir: str | None = None,
) -> int:
    """Run one admitted mission in the foreground."""
    runner = MissionRunner(Path(repo_path), state_dir=Path(state_dir) if state_dir else None)
    try:
        result = runner.run(Path(mission_yaml))
    except AdmissionError as exc:
        print(f"RUDRA admission rejected: {exc}")
        return 3
    except LockHeldError as exc:
        print(f"RUDRA lock held: {exc}")
        return 4
    except RecoveryRequired as exc:
        print(f"RUDRA RECOVERY_REQUIRED: {exc}")
        return 5
    except JournalConflict as exc:
        print(f"RUDRA journal conflict (quarantined): {exc}")
        return 6
    print(json.dumps(result, indent=2, sort_keys=True))
    print(_world_locus(Path(repo_path).resolve()))
    return 0 if result.get("terminal") == "COMPLETE_REPRODUCED" else 2


def cmd_rudra_status(
    mission_id: str,
    as_json: bool = False,
    repo_path: str = ".",
    state_dir: str | None = None,
) -> int:
    """Read-only status; never infers liveness from stale files."""
    runner = MissionRunner(Path(repo_path), state_dir=Path(state_dir) if state_dir else None)
    result = runner.status(mission_id)
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"mission {result['mission_id']}: {result['status']}")
        if "terminal" in result:
            print(json.dumps(result["terminal"], indent=2, sort_keys=True))
    return 0


def cmd_rudra_stop(
    mission_id: str,
    reason: str,
    repo_path: str = ".",
    state_dir: str | None = None,
) -> int:
    """Write a durable stop request. Signals nothing itself."""
    runner = MissionRunner(Path(repo_path), state_dir=Path(state_dir) if state_dir else None)
    result = runner.stop(mission_id, reason)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("result") != "UNKNOWN" else 1
