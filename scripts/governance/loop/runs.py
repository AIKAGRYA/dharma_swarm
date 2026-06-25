#!/usr/bin/env python3
"""Runs orchestration for the Cybernetic Ratchet Loop (architecture §10).

Manages the ``runs/YYYY-WW/<run_id>/`` layout with the six stage subdirs
(``audit``, ``fixes``, ``verdicts``, ``ratchet``, ``ledger``, ``receipts``),
writes a ``manifest.json`` per run (warrant ref, scope, findings, gates, DoD
checklist, timestamps), and provides stage I/O helpers so each stage reads its
input from and writes its output to the run dir, chaining correctly.

The runs root defaults to the Desktop suite runs dir (where the Phase-0 proof
lives) and is overridable via the ``LOOP_RUNS_DIR`` environment variable. Run
artifacts are generated outputs and are NOT committed to the repo.

Usage:
    python3 scripts/governance/loop/runs.py create --run-id <id> [--warrant <yaml>] [--scope <json>]
    python3 scripts/governance/loop/runs.py path --run-id <id>
    python3 scripts/governance/loop/runs.py list

Exit codes:
    0   command succeeded
    2   hard error (run not found, unreadable warrant/scope, malformed input)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

DEFAULT_RUNS_ROOT = "/Users/dhyana/Desktop/complexity_code_testing_prompts/runs"

RUN_SUBDIRS: tuple[str, ...] = (
    "audit",
    "fixes",
    "verdicts",
    "ratchet",
    "ledger",
    "receipts",
)

MANIFEST_NAME = "manifest.json"
ACCEPTED_FINDINGS_NAME = "accepted_findings.jsonl"
SCOPE_NAME = "scope.json"


def runs_root() -> str:
    """Return the configured runs root (``LOOP_RUNS_DIR`` or the default)."""
    return os.environ.get("LOOP_RUNS_DIR", DEFAULT_RUNS_ROOT)


def current_week_bucket(now: datetime | None = None) -> str:
    """Return the ISO ``YYYY-WW`` bucket for ``now`` (UTC by default)."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    iso_year, iso_week, _ = current.isocalendar()
    return f"{iso_year:04d}-W{iso_week:02d}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Run:
    """A single run dir ``runs/YYYY-WW/<run_id>/`` with stage I/O helpers."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.run_id = run_dir.name

    # --- path properties ---

    @property
    def manifest_path(self) -> Path:
        return self.run_dir / MANIFEST_NAME

    @property
    def audit_dir(self) -> Path:
        return self.run_dir / "audit"

    @property
    def fixes_dir(self) -> Path:
        return self.run_dir / "fixes"

    @property
    def verdicts_dir(self) -> Path:
        return self.run_dir / "verdicts"

    @property
    def ratchet_dir(self) -> Path:
        return self.run_dir / "ratchet"

    @property
    def ledger_dir(self) -> Path:
        return self.run_dir / "ledger"

    @property
    def receipts_dir(self) -> Path:
        return self.run_dir / "receipts"

    # --- stage artifact paths ---

    def scope_path(self) -> Path:
        return self.run_dir / SCOPE_NAME

    def accepted_findings_path(self) -> Path:
        return self.run_dir / ACCEPTED_FINDINGS_NAME

    def audit_path(self, prompt_id: str) -> Path:
        return self.audit_dir / f"{prompt_id}.json"

    def fix_proposal_path(self, finding_id: str) -> Path:
        return self.fixes_dir / f"fix_proposal_{finding_id}.yaml"

    def verifier_verdict_path(self, finding_id: str) -> Path:
        return self.verdicts_dir / f"verifier_verdict_{finding_id}.yaml"

    def ratchet_path(self, finding_id: str) -> Path:
        return self.ratchet_dir / f"ratchet_{finding_id}.yaml"

    def ledger_entry_path(self, finding_id: str) -> Path:
        return self.ledger_dir / f"ledger_entry_{finding_id}.yaml"

    def receipt_path(self, name: str) -> Path:
        return self.receipts_dir / name

    # --- manifest helpers ---

    def read_manifest(self) -> dict:
        if not self.manifest_path.is_file():
            return {}
        return json.loads(self.manifest_path.read_text())

    def write_manifest(self, manifest: dict) -> None:
        self.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    def _update_manifest(self, mutator) -> dict:
        manifest = self.read_manifest()
        mutator(manifest)
        ts = manifest.setdefault("timestamps", {})
        ts["updated_utc"] = _utc_now_iso()
        self.write_manifest(manifest)
        return manifest

    def add_finding(self, finding_id: str) -> dict:
        def _m(manifest: dict) -> None:
            findings = manifest.setdefault("findings", [])
            if finding_id not in findings:
                findings.append(finding_id)

        return self._update_manifest(_m)

    def add_gate(self, gate: dict) -> dict:
        def _m(manifest: dict) -> None:
            gates = manifest.setdefault("gates", [])
            gates.append(gate)

        return self._update_manifest(_m)

    def set_dod_checklist(self, checklist: dict) -> dict:
        def _m(manifest: dict) -> None:
            manifest["dod_checklist"] = dict(checklist)

        return self._update_manifest(_m)

    # --- generic I/O helpers ---

    def write_json(self, path: Path, doc: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")

    def read_json(self, path: Path) -> dict:
        return json.loads(path.read_text())

    def write_jsonl(self, path: Path, records: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(r, sort_keys=True) for r in records]
        path.write_text("\n".join(lines) + ("\n" if lines else ""))

    def read_jsonl(self, path: Path) -> list[dict]:
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def write_yaml(self, path: Path, doc: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(doc, sort_keys=False))

    def read_yaml(self, path: Path) -> dict:
        return yaml.safe_load(path.read_text())

    # --- stage input discovery ---

    def list_audits(self) -> list[Path]:
        if not self.audit_dir.is_dir():
            return []
        return sorted(self.audit_dir.glob("*.json"))

    def list_fix_proposals(self) -> list[Path]:
        if not self.fixes_dir.is_dir():
            return []
        return sorted(self.fixes_dir.glob("fix_proposal_*.yaml"))

    def list_verifier_verdicts(self) -> list[Path]:
        if not self.verdicts_dir.is_dir():
            return []
        return sorted(self.verdicts_dir.glob("verifier_verdict_*.yaml"))

    def list_ratchets(self) -> list[Path]:
        if not self.ratchet_dir.is_dir():
            return []
        return sorted(self.ratchet_dir.glob("ratchet_*.yaml"))

    def list_ledger_entries(self) -> list[Path]:
        if not self.ledger_dir.is_dir():
            return []
        return sorted(self.ledger_dir.glob("ledger_entry_*.yaml"))


class RunManager:
    """Factory + locator for ``Run`` objects."""

    @staticmethod
    def _week_root(week: str | None = None) -> Path:
        bucket = week or current_week_bucket()
        return Path(runs_root()) / bucket

    @staticmethod
    def create_run(
        run_id: str,
        warrant: dict | None = None,
        scope: dict | None = None,
        week: str | None = None,
    ) -> Run:
        """Create the run dir tree + initial manifest and return the ``Run``."""
        week_root = RunManager._week_root(week)
        run_dir = week_root / run_id
        for sub in RUN_SUBDIRS:
            (run_dir / sub).mkdir(parents=True, exist_ok=True)

        manifest: dict = {
            "run_id": run_id,
            "warrant": _warrant_ref(warrant) if warrant else {},
            "scope": scope or {},
            "findings": [],
            "gates": [],
            "dod_checklist": {},
            "timestamps": {"created_utc": _utc_now_iso(), "updated_utc": _utc_now_iso()},
        }
        run = Run(run_dir)
        run.write_manifest(manifest)
        return run

    @staticmethod
    def open_run(run_id: str, week: str | None = None) -> Run:
        """Locate an existing run by id (searching the week bucket, then all weeks)."""
        root = Path(runs_root())
        if week is not None:
            candidate = root / week / run_id
            if candidate.is_dir():
                return Run(candidate)
            raise FileNotFoundError(f"run not found: {week}/{run_id}")
        # search the current week first, then any week bucket
        current = current_week_bucket()
        candidate = root / current / run_id
        if candidate.is_dir():
            return Run(candidate)
        for week_dir in sorted(root.glob("*-W*"), reverse=True):
            candidate = week_dir / run_id
            if candidate.is_dir():
                return Run(candidate)
        raise FileNotFoundError(f"run not found: {run_id}")

    @staticmethod
    def list_runs(week: str | None = None) -> list[Run]:
        """List runs under a week bucket (or all week buckets)."""
        root = Path(runs_root())
        buckets = [root / week] if week else sorted(root.glob("*-W*"))
        runs: list[Run] = []
        for bucket in buckets:
            if not bucket.is_dir():
                continue
            for run_dir in sorted(bucket.iterdir()):
                if run_dir.is_dir():
                    runs.append(Run(run_dir))
        return runs


def _warrant_ref(warrant: dict) -> dict:
    """Project a warrant dict into the manifest's warrant ref."""
    scope = warrant.get("scope", {}) if isinstance(warrant, dict) else {}
    return {
        "id": warrant.get("id"),
        "authority_level": warrant.get("authority_level"),
        "merge_policy": warrant.get("merge_policy"),
        "base_ref": scope.get("base_ref") if isinstance(scope, dict) else None,
        "head_ref": scope.get("head_ref") if isinstance(scope, dict) else None,
        "councils": scope.get("councils", []) if isinstance(scope, dict) else [],
        "write_set": warrant.get("write_set", []),
        "budget": warrant.get("budget", {}),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _emit_error(message: str) -> int:
    sys.stderr.write(message + "\n")
    return 2


def _load_warrant(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"warrant file not found: {path}")
    return yaml.safe_load(path.read_text()) or {}


def _load_scope(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"scope file not found: {path}")
    return json.loads(path.read_text())


def _cmd_create(args) -> int:
    warrant = None
    if args.warrant:
        try:
            warrant = _load_warrant(Path(args.warrant))
        except (FileNotFoundError, yaml.YAMLError) as exc:
            return _emit_error(f"warrant load failed: {exc}")
    scope = None
    if args.scope:
        try:
            scope = _load_scope(Path(args.scope))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            return _emit_error(f"scope load failed: {exc}")
    run = RunManager.create_run(run_id=args.run_id, warrant=warrant, scope=scope, week=args.week)
    sys.stdout.write(str(run.run_dir) + "\n")
    return 0


def _cmd_path(args) -> int:
    try:
        run = RunManager.open_run(args.run_id, week=args.week)
    except FileNotFoundError as exc:
        return _emit_error(str(exc))
    sys.stdout.write(str(run.run_dir) + "\n")
    return 0


def _cmd_list(args) -> int:
    for run in RunManager.list_runs(week=args.week):
        sys.stdout.write(str(run.run_dir) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manage runs/YYYY-WW/<run_id>/ layout + manifest for the Cybernetic Ratchet Loop.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="create a new run dir tree + manifest")
    p_create.add_argument("--run-id", required=True, help="unique run id (the <run_id> dir name)")
    p_create.add_argument("--warrant", default=None, help="path to a warrant YAML (recorded in manifest)")
    p_create.add_argument("--scope", default=None, help="path to a scope.json (recorded in manifest)")
    p_create.add_argument("--week", default=None, help="override the YYYY-WW bucket (default: current week)")

    p_path = sub.add_parser("path", help="print the run dir path for an existing run id")
    p_path.add_argument("--run-id", required=True)
    p_path.add_argument("--week", default=None)

    p_list = sub.add_parser("list", help="list run dirs under the runs root")
    p_list.add_argument("--week", default=None)

    args = parser.parse_args(argv)

    if args.command == "create":
        return _cmd_create(args)
    if args.command == "path":
        return _cmd_path(args)
    if args.command == "list":
        return _cmd_list(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
