"""Build the Forge Lab operator-history projection."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from dharma_swarm.forge_lab.operator_history_rendering import (
    _history_row as _history_row,
    _index_table as _index_table,
    _json_text as _json_text,
    _lineage_markdown as _lineage_markdown,
    _run_readme as _run_readme,
    _safe_symlink as _safe_symlink,
    _scorecard_table as _scorecard_table,
    _sources_markdown as _sources_markdown,
    _write_scorecard_directory as _write_scorecard_directory,
    _write_text as _write_text,
)
from dharma_swarm.forge_lab.operator_history_scorecards import (
    _scorecard_for_native as _scorecard_for_native,
    _scorecard_for_run as _scorecard_for_run,
)
from dharma_swarm.forge_lab.operator_history_sources import (
    MARKER_NAME,
    METRIC_KEYS,
    VIEW_SCHEMA,
    _associate_runs,
    _discover_experiments,
    _discover_runs,
    _iso,
    _parse_time,
    _utc_now,
)


def _build_tree(
    target: Path,
    state_root: Path,
    generated_at: datetime,
) -> dict[str, Any]:
    experiments = _discover_experiments(state_root)
    runs = _discover_runs(state_root)
    linked = _associate_runs(runs, experiments)
    scorecards = [_scorecard_for_run(run) for run in runs]
    paired = sorted(
        zip(scorecards, runs, strict=True),
        key=lambda pair: (
            _parse_time(pair[0].get("started_at"))
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    )
    entries: list[tuple[dict[str, Any], str]] = []
    for scorecard, run in paired:
        relative = _write_scorecard_directory(target, scorecard, run)
        entries.append((scorecard, relative))

    native_only_entries: list[tuple[dict[str, Any], str]] = []
    for experiment_id, experiment in sorted(
        experiments.items(),
        key=lambda item: (
            item[1].get("started_at_dt") or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    ):
        if experiment_id in linked:
            continue
        scorecard = _scorecard_for_native(experiment)
        relative = _write_scorecard_directory(target, scorecard, None)
        native_only_entries.append((scorecard, relative))

    marker = {
        "schema": VIEW_SCHEMA,
        "purpose": "safe replacement marker for generated operator history",
    }
    _write_text(target / MARKER_NAME, _json_text(marker))
    readme = f"""# Read this first — RSI operator run history

This is a **regeneratable, read-only projection** of canonical Forge Lab receipts.
It exists outside the rotating `current` checkout so operators get stable,
obvious paths. Do not hand-edit generated files.

## Start here

- `LATEST/` — symlink to the newest operator session.
- `LATEST.md` — newest run's ten-metric scorecard.
- `LATEST_10.md` — fast comparison of the ten newest sessions.
- `ALL_RUNS.md` — every operator session, newest first.
- `runs/YYYY-MM-DD/` — dated, descriptive run folders.
- `native-only/` — imported or manual native experiments that cannot be honestly linked to an operator session.
- `history.v1.jsonl` — line-oriented machine-readable projection rows.

Folder names are sortable and descriptive:

`UTC-start__run-kind__mode__model`

Verdicts are kept inside each folder. Mode/model labels may become more specific
when missing receipts arrive, because this is a regenerated projection rather
than an immutable archive path.
Missing evidence stays `unknown`/`null`; it is never silently converted to zero.

## Refresh

```bash
/root/rsi-lab/current/repo/scripts/forge_lab/operator-history
```

Generated at {_iso(generated_at)} from `{state_root}`.
"""
    _write_text(target / "README_FIRST.md", readme)
    _write_text(
        target / "ALL_RUNS.md",
        "# All operator sessions\n\n" + _index_table(entries) + "\n",
    )
    _write_text(
        target / "LATEST_10.md",
        "# Ten newest operator sessions\n\n" + _index_table(entries[:10]) + "\n",
    )
    _write_text(
        target / "NATIVE_ONLY.md",
        "# Native-only and imported experiments\n\n"
        "These are deliberately separate because no trustworthy operator-session link exists.\n\n"
        + _index_table(native_only_entries)
        + "\n",
    )
    history_lines = [
        json.dumps(
            _history_row(scorecard, relative), sort_keys=True, ensure_ascii=False
        )
        for scorecard, relative in entries
    ]
    _write_text(
        target / "history.v1.jsonl",
        "\n".join(history_lines) + ("\n" if history_lines else ""),
    )
    if entries:
        latest_scorecard, latest_relative = entries[0]
        _safe_symlink(Path(latest_relative), target / "LATEST")
        _write_text(
            target / "LATEST.md",
            f"# Latest operator session\n\n"
            f"Open [`{latest_scorecard['run_id']}`]({latest_relative}/README.md).\n\n"
            + _scorecard_table(latest_scorecard)
            + "\n",
        )
    else:
        _write_text(
            target / "LATEST.md",
            "# Latest operator session\n\nNo operator sessions found.\n",
        )
    refresh = """#!/usr/bin/env bash
set -euo pipefail
exec /root/rsi-lab/current/repo/scripts/forge_lab/operator-history "$@"
"""
    _write_text(target / "REFRESH.sh", refresh, executable=True)
    manifest = {
        "schema": VIEW_SCHEMA,
        "generated_at": _iso(generated_at),
        "source_state_root": str(state_root),
        "operator_run_count": len(entries),
        "linked_native_experiment_count": len(linked),
        "native_experiment_count": len(experiments),
        "native_only_experiment_count": len(native_only_entries),
        "latest_run_id": entries[0][0]["run_id"] if entries else None,
        "metric_groups": list(METRIC_KEYS),
    }
    _write_text(target / "VIEW_MANIFEST.json", _json_text(manifest))
    return manifest


def _replace_generated_tree(staging: Path, output_root: Path) -> None:
    if output_root.is_symlink():
        raise ValueError(f"Refusing to replace symlink output root: {output_root}")
    if not output_root.exists():
        os.replace(staging, output_root)
        return
    marker = output_root / MARKER_NAME
    if not marker.is_file():
        raise ValueError(
            f"Refusing to replace non-generated directory without {MARKER_NAME}: {output_root}"
        )
    try:
        marker_payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Refusing to replace output with an invalid generated marker: {output_root}"
        ) from exc
    if (
        not isinstance(marker_payload, Mapping)
        or marker_payload.get("schema") != VIEW_SCHEMA
    ):
        raise ValueError(
            f"Refusing to replace output with an unrecognized generated marker: {output_root}"
        )
    backup = output_root.parent / f".{output_root.name}.previous-{os.getpid()}"
    if backup.exists() or backup.is_symlink():
        raise ValueError(f"Refusing to overwrite stale backup: {backup}")
    os.replace(output_root, backup)
    try:
        os.replace(staging, output_root)
    except BaseException:
        os.replace(backup, output_root)
        raise
    shutil.rmtree(backup)


def build_operator_history(
    state_root: Path,
    output_root: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build and atomically install the operator-facing history projection."""

    state = Path(state_root).expanduser().resolve()
    requested_output = Path(output_root).expanduser().absolute()
    if requested_output.is_symlink():
        raise ValueError(f"Output root must not be a symlink: {requested_output}")
    output = requested_output.resolve(strict=False)
    if not state.is_dir():
        raise FileNotFoundError(f"State root does not exist: {state}")
    if output == state or state in output.parents or output in state.parents:
        raise ValueError(
            "Output must be a second location outside the canonical state root"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.build-", dir=output.parent))
    try:
        manifest = _build_tree(staging, state, generated_at or _utc_now())
        _replace_generated_tree(staging, output)
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="operator-history",
        description="build a human-first projection of Forge Lab run receipts",
    )
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = build_operator_history(args.state_root, args.output_root)
    print(
        "operator history refreshed: "
        f"{args.output_root} "
        f"runs={manifest['operator_run_count']} "
        f"native_only={manifest['native_only_experiment_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
