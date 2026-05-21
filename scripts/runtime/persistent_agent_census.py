#!/usr/bin/env python3
"""Regenerate L4 persistent-agent readiness evidence from local state.

The command is intentionally read-only against live runtime state. It writes
only the requested readiness artifacts under the chosen output directory.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote


HOME = Path.home()
DEFAULT_REPO_ROOT = HOME / "dharma_swarm"
DEFAULT_STATE_ROOT = HOME / ".dharma"
DEFAULT_AGORA_ROOT = HOME / "dharmic-agora"
DEFAULT_OUTPUT_DIR = (
    DEFAULT_REPO_ROOT / "docs/research/persistent_agents_census_2026-05"
)

READINESS_FIELDS = [
    "candidate_kind",
    "name",
    "current_tier",
    "target_tier",
    "registered_identity",
    "identity_path",
    "passport_present",
    "wake_claim_present",
    "runtime_session_present",
    "delegation_run_present",
    "context_bundle_present",
    "routing_decision_present",
    "execution_lease_required",
    "execution_lease_present",
    "memory_receipts_present",
    "artifact_present",
    "outcome_present",
    "recent_success_present",
    "current_process_present",
    "last_success_at",
    "blocking_errors",
    "next_required_action",
    "count_as_l4",
    "evidence_paths",
]

TIERS = ("L0", "L1", "L2", "L3", "L4", "L5", "L6")
RECENT_SUCCESS_MAX_AGE_DAYS = 14
TERMINAL_CLAIM_STATUSES = {"closed", "failed", "completed", "released", "stale"}
SUCCESS_OUTCOME_STATUSES = {"completed", "done", "succeeded", "success", "ok"}
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)authorization:\s*bearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)user_id['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{4,}"),
)
REDACT_PATTERNS = (
    (re.compile(r"sk-[A-Za-z0-9_-]{8,}"), "sk-<redacted>"),
    (
        re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{8,}"),
        r"\1=<redacted>",
    ),
    (
        re.compile(r"(?i)authorization:\s*bearer\s+[A-Za-z0-9_./+=-]{8,}"),
        "authorization: bearer <redacted>",
    ),
    (
        re.compile(r"(?i)user_id['\"]?\s*[:=]\s*['\"]?[^,}\s]+"),
        "user_id=<redacted>",
    ),
)


@dataclass(frozen=True)
class ReadinessRow:
    candidate_kind: str
    name: str
    current_tier: str
    target_tier: str
    registered_identity: bool
    identity_path: str | None
    passport_present: bool
    wake_claim_present: bool
    runtime_session_present: bool
    delegation_run_present: bool
    context_bundle_present: bool
    routing_decision_present: bool
    execution_lease_required: bool
    execution_lease_present: bool
    memory_receipts_present: bool
    artifact_present: bool
    outcome_present: bool
    recent_success_present: bool
    current_process_present: bool
    last_success_at: str | None
    blocking_errors: list[str]
    next_required_action: str
    count_as_l4: bool
    evidence_paths: list[str]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _normalize_error(text: str | None) -> str:
    if not text:
        return ""
    lowered = text.lower()
    if "database disk image is malformed" in lowered:
        return "database disk image is malformed"
    if "credit balance is too low" in lowered or "402" in lowered:
        return "provider credit balance is too low"
    if "no endpoints found that support tool use" in lowered or "404" in lowered:
        return "provider route has no tool-use-capable endpoint"
    if "403" in lowered or "access denied" in lowered:
        return "provider access denied"
    if "410" in lowered or "model is gone" in lowered:
        return "provider model endpoint is gone"
    if "timeout" in lowered or "timed out" in lowered or "provider_timeout" in lowered:
        return "provider timeout"
    if "local tool loop exceeded" in lowered:
        return "local tool loop exceeded max rounds"
    if "doctor report status=fail" in lowered:
        return "doctor report status=FAIL"
    if "unsupported handler" in lowered:
        return "unsupported handler"
    clean = text
    for pattern, replacement in REDACT_PATTERNS:
        clean = pattern.sub(replacement, clean)
    clean = re.sub(r"\s+", " ", clean.strip())
    return clean[:180]


def assert_no_secret_text(text: str) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise ValueError(f"secret-like value matched pattern {pattern.pattern!r}")


class RuntimeProbe:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.error = ""
        self.tables: set[str] = set()
        self._db: sqlite3.Connection | None = None
        if not db_path.exists():
            self.error = "runtime db absent"
            return
        uri = f"file:{quote(str(db_path.resolve()), safe='/')}?mode=ro&immutable=1"
        try:
            self._db = sqlite3.connect(uri, uri=True)
            self._db.row_factory = sqlite3.Row
            self._db.execute("PRAGMA query_only=ON")
            self.tables = {
                str(row["name"])
                for row in self._db.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
                )
            }
        except Exception as exc:
            self.error = _normalize_error(str(exc)) or "runtime db unreadable"
            self._db = None

    def close(self) -> None:
        if self._db is not None:
            self._db.close()

    def rows(self, table: str, where: str = "", params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        if self._db is None or table not in self.tables:
            return []
        sql = f"SELECT * FROM {table}"
        if where:
            sql += f" WHERE {where}"
        try:
            return list(self._db.execute(sql, params))
        except Exception:
            return []


def _row_get(row: sqlite3.Row | None, column: str, default: Any = "") -> Any:
    if row is None or column not in row.keys():
        return default
    value = row[column]
    return default if value is None else value


def _row_text(row: sqlite3.Row | None, column: str) -> str:
    return str(_row_get(row, column, "") or "")


def _dedupe_rows(rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
    out: list[sqlite3.Row] = []
    seen: set[str] = set()
    for row in rows:
        row_id = repr(tuple(row))
        if row_id in seen:
            continue
        seen.add(row_id)
        out.append(row)
    return out


def _json_object(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _row_metadata(row: sqlite3.Row | None) -> dict[str, Any]:
    return _json_object(_row_get(row, "metadata_json", ""))


def _metadata_truthy(rows: list[sqlite3.Row], *keys: str) -> bool:
    wanted = set(keys)
    for row in rows:
        metadata = _row_metadata(row)
        for key in wanted:
            value = metadata.get(key)
            if value is True:
                return True
            if isinstance(value, str) and value.lower() in {"true", "1", "yes", "required"}:
                return True
    return False


def _metadata_ids(rows: list[sqlite3.Row], *keys: str) -> set[str]:
    ids: set[str] = set()
    for row in rows:
        metadata = _row_metadata(row)
        for key in keys:
            value = metadata.get(key)
            if isinstance(value, str) and value:
                ids.add(value)
    return ids


def _row_dt(row: sqlite3.Row | None, *columns: str) -> datetime | None:
    for column in columns:
        dt = _parse_dt(_row_get(row, column, None))
        if dt is not None:
            return dt
    return None


def _is_live_claim(row: sqlite3.Row, now: datetime) -> bool:
    status = _row_text(row, "status").lower()
    heartbeat_at = _row_dt(row, "heartbeat_at")
    stale_after = _row_dt(row, "stale_after")
    return (
        status not in TERMINAL_CLAIM_STATUSES
        and bool(_row_text(row, "session_id"))
        and heartbeat_at is not None
        and stale_after is not None
        and stale_after > now
    )


def _is_recent_success(dt: datetime | None, now: datetime) -> bool:
    return dt is not None and now - timedelta(days=RECENT_SUCCESS_MAX_AGE_DAYS) <= dt <= now


def _related_rows_for_chain(
    probe: RuntimeProbe,
    table: str,
    *,
    session_id: str,
    task_id: str,
    run_id: str,
    agent_id: str | None = None,
) -> list[sqlite3.Row]:
    rows: list[sqlite3.Row] = []
    if run_id:
        rows.extend(probe.rows(table, "run_id = ?", (run_id,)))
    if session_id and task_id:
        rows.extend(probe.rows(table, "session_id = ? AND task_id = ?", (session_id, task_id)))
    elif session_id:
        rows.extend(probe.rows(table, "session_id = ?", (session_id,)))
    if agent_id and table == "session_events":
        rows = [
            row
            for row in rows
            if _row_text(row, "agent_id") in {"", agent_id}
            or agent_id in _row_text(row, "summary")
            or agent_id in _row_text(row, "event_text")
        ]
    return _dedupe_rows(rows)


def _event_blob(row: sqlite3.Row) -> str:
    return " ".join(
        [
            _row_text(row, "event_name"),
            _row_text(row, "summary"),
            _row_text(row, "event_text"),
            _row_text(row, "payload_json"),
        ]
    ).lower()


def _has_memory_read_and_write(
    memories: list[sqlite3.Row],
    events: list[sqlite3.Row],
) -> tuple[bool, bool]:
    read_markers = ("memory_read", "memory read", "recall", "retriev")
    write_markers = ("memory_write", "memory write", "memory_fact", "stored memory", "persisted memory")
    has_read = False
    has_write = bool(memories)
    for event in events:
        blob = _event_blob(event)
        has_read = has_read or any(marker in blob for marker in read_markers)
        has_write = has_write or any(marker in blob for marker in write_markers)
    return has_read, has_write


def _chain_success_at(
    outcomes: list[sqlite3.Row],
    events: list[sqlite3.Row],
) -> datetime | None:
    success_times: list[datetime] = []
    for row in outcomes:
        status = _row_text(row, "status").lower()
        if status in SUCCESS_OUTCOME_STATUSES:
            dt = _row_dt(row, "created_at")
            if dt is not None:
                success_times.append(dt)
    for row in events:
        blob = _event_blob(row)
        if any(marker in blob for marker in ("outcome", "complete", "success")) and not any(
            marker in blob for marker in ("failed", "failure", "error", "blocked")
        ):
            dt = _row_dt(row, "created_at", "timestamp", "ts")
            if dt is not None:
                success_times.append(dt)
    return max(success_times, default=None)


def _execution_lease_state(
    probe: RuntimeProbe,
    chain_rows: list[sqlite3.Row],
    *,
    session_id: str,
    task_id: str,
    run_id: str,
    claim_id: str,
) -> tuple[bool, bool, list[str]]:
    lease_ids = _metadata_ids(chain_rows, "execution_lease_id", "lease_id")
    required = bool(lease_ids) or _metadata_truthy(
        chain_rows,
        "execution_lease_required",
        "requires_execution_lease",
        "governed_action",
    )
    evidence: list[str] = []
    lease_rows: list[sqlite3.Row] = []
    if "execution_leases" in probe.tables:
        values = {session_id, task_id, run_id, claim_id} | lease_ids
        lease_rows.extend(
            _query_related(
                probe,
                "execution_leases",
                ("lease_id", "session_id", "task_id", "run_id", "claim_id"),
                values,
            )
        )
    if "workspace_leases" in probe.tables:
        if lease_ids:
            where, params = _where_in("lease_id", lease_ids)
            lease_rows.extend(probe.rows("workspace_leases", where, params))
        if run_id:
            lease_rows.extend(probe.rows("workspace_leases", "holder_run_id = ?", (run_id,)))
    lease_rows = _dedupe_rows(lease_rows)
    if lease_rows:
        evidence.append(f"{probe.db_path}#execution_or_workspace_leases:{len(lease_rows)}")
    return required, bool(lease_rows), evidence


def _ids(rows: list[sqlite3.Row], column: str) -> set[str]:
    out: set[str] = set()
    for row in rows:
        value = row[column] if column in row.keys() else ""
        if value:
            out.add(str(value))
    return out


def _where_in(column: str, values: set[str]) -> tuple[str, tuple[Any, ...]]:
    vals = sorted(v for v in values if v)
    if not vals:
        return "", ()
    return f"{column} IN ({','.join('?' for _ in vals)})", tuple(vals)


def _query_related(probe: RuntimeProbe, table: str, columns: tuple[str, ...], values: set[str]) -> list[sqlite3.Row]:
    related: list[sqlite3.Row] = []
    seen: set[str] = set()
    for column in columns:
        where, params = _where_in(column, values)
        if not where:
            continue
        for row in probe.rows(table, where, params):
            row_id = repr(tuple(row))
            if row_id not in seen:
                seen.add(row_id)
                related.append(row)
    return related


def _probe_agent_runtime(
    name: str,
    probe: RuntimeProbe,
    now: datetime | None = None,
) -> tuple[dict[str, bool], list[str], list[str], datetime | None]:
    flags = {
        "wake_claim_present": False,
        "runtime_session_present": False,
        "delegation_run_present": False,
        "context_bundle_present": False,
        "routing_decision_present": False,
        "execution_lease_required": False,
        "execution_lease_present": False,
        "memory_receipts_present": False,
        "artifact_present": False,
        "outcome_present": False,
        "recent_success_present": False,
    }
    now = now or _utc_now()
    evidence: list[str] = []
    errors: list[str] = []
    if probe.error and probe.error != "runtime db absent":
        errors.append(probe.error)

    claims = probe.rows("task_claims", "agent_id = ?", (name,))
    active_claims = [row for row in claims if _is_live_claim(row, now)]
    flags["wake_claim_present"] = bool(active_claims)
    if claims:
        evidence.append(f"{probe.db_path}#task_claims:{len(claims)}")

    best_flags = dict(flags)
    best_evidence: list[str] = []
    best_success_at: datetime | None = None
    best_chain_at: datetime | None = None
    best_score = -1

    for claim in active_claims:
        claim_id = _row_text(claim, "claim_id")
        session_id = _row_text(claim, "session_id")
        task_id = _row_text(claim, "task_id")
        runs = []
        if claim_id:
            runs.extend(probe.rows("delegation_runs", "claim_id = ?", (claim_id,)))
        if session_id and task_id:
            runs.extend(
                probe.rows(
                    "delegation_runs",
                    "assigned_to = ? AND session_id = ? AND task_id = ?",
                    (name, session_id, task_id),
                )
            )
        runs = _dedupe_rows(runs)
        chain_runs: list[sqlite3.Row | None] = runs or [None]

        for run in chain_runs:
            run_id = _row_text(run, "run_id")
            events = _related_rows_for_chain(
                probe,
                "session_events",
                session_id=session_id,
                task_id=task_id,
                run_id=run_id,
                agent_id=name,
            )
            sessions = probe.rows("sessions", "session_id = ?", (session_id,)) if session_id else []
            contexts = _related_rows_for_chain(
                probe,
                "context_bundles",
                session_id=session_id,
                task_id=task_id,
                run_id=run_id,
            )
            routes = _related_rows_for_chain(
                probe,
                "routing_decisions",
                session_id=session_id,
                task_id=task_id,
                run_id=run_id,
            )
            memory_event_ids = _ids(events, "event_id")
            memories = _related_rows_for_chain(
                probe,
                "memory_facts",
                session_id=session_id,
                task_id=task_id,
                run_id="",
            )
            if memory_event_ids:
                memories.extend(
                    _query_related(
                        probe,
                        "memory_facts",
                        ("source_event_id",),
                        memory_event_ids,
                    )
                )
            memories = _dedupe_rows(memories)
            artifacts = _related_rows_for_chain(
                probe,
                "artifact_records",
                session_id=session_id,
                task_id=task_id,
                run_id=run_id,
            )
            outcomes = _related_rows_for_chain(
                probe,
                "external_outcomes",
                session_id=session_id,
                task_id=task_id,
                run_id=run_id,
            )
            memory_read, memory_write = _has_memory_read_and_write(memories, events)
            success_at = _chain_success_at(outcomes, events)
            chain_rows = [claim] + ([run] if run is not None else []) + events
            lease_required, lease_present, lease_evidence = _execution_lease_state(
                probe,
                chain_rows,
                session_id=session_id,
                task_id=task_id,
                run_id=run_id,
                claim_id=claim_id,
            )
            chain_flags = {
                "wake_claim_present": True,
                "runtime_session_present": bool(sessions),
                "delegation_run_present": run is not None,
                "context_bundle_present": bool(contexts),
                "routing_decision_present": bool(routes),
                "execution_lease_required": lease_required,
                "execution_lease_present": lease_present,
                "memory_receipts_present": memory_read and memory_write,
                "artifact_present": bool(artifacts),
                "outcome_present": bool(outcomes),
                "recent_success_present": _is_recent_success(success_at, now),
            }
            chain_at = success_at or _row_dt(claim, "heartbeat_at", "claimed_at")
            score = sum(
                1
                for key, value in chain_flags.items()
                if key != "execution_lease_required" and value
            )
            chain_evidence = [
                f"{probe.db_path}#task_claim:{claim_id or 'unknown'}",
            ]
            if run is not None:
                chain_evidence.append(f"{probe.db_path}#delegation_run:{run_id or 'unknown'}")
            for table, table_rows in [
                ("session_events", events),
                ("sessions", sessions),
                ("context_bundles", contexts),
                ("routing_decisions", routes),
                ("memory_facts", memories),
                ("artifact_records", artifacts),
                ("external_outcomes", outcomes),
            ]:
                if table_rows:
                    chain_evidence.append(f"{probe.db_path}#{table}:{len(table_rows)}")
            chain_evidence.extend(lease_evidence)
            if score > best_score:
                best_score = score
                best_flags = chain_flags
                best_evidence = chain_evidence
                best_success_at = success_at
                best_chain_at = chain_at
            elif score == best_score and chain_at is not None and (
                best_chain_at is None or chain_at > best_chain_at
            ):
                best_score = score
                best_flags = chain_flags
                best_evidence = chain_evidence
                best_success_at = success_at
                best_chain_at = chain_at

    if best_score >= 0:
        flags.update(best_flags)
        evidence.extend(best_evidence)

    return flags, evidence, errors, best_success_at


def _passport_present(name: str, state_root: Path, identity: dict[str, Any]) -> bool:
    passport_paths = [
        state_root / "agent_passports" / f"{name}.json",
        state_root / "passports" / f"{name}.json",
    ]
    if any(path.exists() for path in passport_paths):
        return True
    return bool(identity.get("public_key") and identity.get("wake_policy_id"))


def _pid_alive(path: Path, expected_markers: tuple[str, ...] = ()) -> bool:
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except Exception:
        return False
    if not expected_markers:
        return True
    try:
        proc = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return False
    command = proc.stdout.lower()
    return proc.returncode == 0 and all(marker.lower() in command for marker in expected_markers)


def _agent_process_present(name: str, state_root: Path) -> bool:
    pid_paths = [
        state_root / "agents" / name / "agent.pid",
        state_root / "agents" / name / "pid",
        state_root / "ginko" / "agents" / name / "agent.pid",
        state_root / "ginko" / "agents" / name / "pid",
        state_root / "agents" / f"{name}.pid",
        state_root / "pids" / f"{name}.pid",
    ]
    return any(_pid_alive(path, (name,)) for path in pid_paths)


def _next_required_action(row: dict[str, Any]) -> str:
    if not row["registered_identity"]:
        return "exclude from cultivation: not an identity-bearing agent"
    if row["blocking_errors"]:
        if any("database disk image is malformed" in err for err in row["blocking_errors"]):
            return "repair malformed conductor memory database"
        return "resolve blocking runtime/provider error"
    for field, action in [
        ("passport_present", "create signed agent passport"),
        ("wake_claim_present", "create supervised TaskClaim with heartbeat"),
        ("runtime_session_present", "create RuntimeSession for the wake"),
        ("delegation_run_present", "create DelegationRun linked to the claim"),
        ("context_bundle_present", "record ContextBundle for rendered context"),
        ("routing_decision_present", "record RoutingDecision for model/provider route"),
        ("execution_lease_present", "record ExecutionLease for governed action"),
        ("memory_receipts_present", "emit memory read/write receipts"),
        ("artifact_present", "produce RuntimeArtifact or KnowledgeArtifact"),
        ("outcome_present", "emit Outcome or ExternalOutcome for successful action"),
        ("recent_success_present", "emit recent successful Outcome or ExternalOutcome"),
        ("current_process_present", "attach candidate to supervised live process"),
    ]:
        if field == "execution_lease_present" and not row["execution_lease_required"]:
            continue
        if not row[field]:
            return action
    return "ready for L4 review"


def _count_as_l4(row: dict[str, Any]) -> bool:
    required = [
        "registered_identity",
        "passport_present",
        "wake_claim_present",
        "runtime_session_present",
        "delegation_run_present",
        "context_bundle_present",
        "routing_decision_present",
        "memory_receipts_present",
        "artifact_present",
        "outcome_present",
        "recent_success_present",
        "current_process_present",
    ]
    lease_ok = (not row["execution_lease_required"]) or row["execution_lease_present"]
    return all(bool(row[field]) for field in required) and lease_ok and not row["blocking_errors"]


def _row(**kwargs: Any) -> ReadinessRow:
    data = dict(kwargs)
    data.setdefault("target_tier", "L4")
    data.setdefault("identity_path", None)
    data.setdefault("last_success_at", None)
    data.setdefault("blocking_errors", [])
    data.setdefault("evidence_paths", [])
    for field in (
        "registered_identity",
        "passport_present",
        "wake_claim_present",
        "runtime_session_present",
        "delegation_run_present",
        "context_bundle_present",
        "routing_decision_present",
        "execution_lease_required",
        "execution_lease_present",
        "memory_receipts_present",
        "artifact_present",
        "outcome_present",
        "recent_success_present",
        "current_process_present",
    ):
        data.setdefault(field, False)
    data["count_as_l4"] = _count_as_l4(data)
    data["next_required_action"] = _next_required_action(data)
    return ReadinessRow(**{field: data[field] for field in READINESS_FIELDS})


def _last_success(events: list[dict[str, Any]]) -> datetime | None:
    successes = [
        _parse_dt(event.get("timestamp"))
        for event in events
        if event.get("success") is True
    ]
    successes = [dt for dt in successes if dt is not None]
    return max(successes, default=None)


def _latest_failure(events: list[dict[str, Any]]) -> str:
    dated = [(_parse_dt(event.get("timestamp")), event) for event in events]
    dated = [(dt, event) for dt, event in dated if dt is not None]
    if not dated:
        return ""
    _, latest = max(dated, key=lambda item: item[0])
    if latest.get("success") is False:
        return _normalize_error(
            str(latest.get("response_preview") or latest.get("error") or "")
        )
    return ""


def _agent_registry_identity_paths(state_root: Path) -> list[Path]:
    """Return primary agent identities first, with legacy Shakti Ginko paths as read-only fallback."""
    primary_root = state_root / "agents"
    legacy_root = state_root / "ginko" / "agents"
    by_name: dict[str, Path] = {}
    for identity_path in sorted(primary_root.glob("*/identity.json")):
        by_name[identity_path.parent.name] = identity_path
    for identity_path in sorted(legacy_root.glob("*/identity.json")):
        by_name.setdefault(identity_path.parent.name, identity_path)
    return [by_name[name] for name in sorted(by_name)]


def _registered_agent_rows(state_root: Path, repo_root: Path, probe: RuntimeProbe) -> list[ReadinessRow]:
    rows: list[ReadinessRow] = []
    for identity_path in _agent_registry_identity_paths(state_root):
        identity = _read_json(identity_path)
        if not isinstance(identity, dict):
            continue
        name = str(identity.get("name") or identity_path.parent.name)
        task_log = identity_path.parent / "task_log.jsonl"
        events = _read_jsonl(task_log)
        if not events and isinstance(identity.get("task_history"), list):
            events = [event for event in identity["task_history"] if isinstance(event, dict)]
        task_count = int(identity.get("tasks_completed") or 0) + int(identity.get("tasks_failed") or 0)
        tier = "L2" if events or task_count else "L1"
        flags, runtime_evidence, runtime_errors, runtime_success_at = _probe_agent_runtime(name, probe)
        blocking_errors = [err for err in runtime_errors if err]
        latest_error = _latest_failure(events)
        if latest_error:
            blocking_errors.append(latest_error)
        history_success_at = _last_success(events)
        last_success_at = max(
            [dt for dt in (history_success_at, runtime_success_at) if dt is not None],
            default=None,
        )
        evidence = [str(identity_path)]
        if task_log.exists():
            evidence.append(str(task_log))
        evidence.extend(runtime_evidence)
        rows.append(
            _row(
                candidate_kind="registered_worker",
                name=name,
                current_tier=tier,
                registered_identity=True,
                identity_path=str(identity_path),
                passport_present=_passport_present(name, state_root, identity),
                current_process_present=_agent_process_present(name, state_root),
                last_success_at=_iso(last_success_at),
                blocking_errors=blocking_errors,
                evidence_paths=evidence,
                workspace_root=str(repo_root),
                **flags,
            )
        )
    return rows


def _conductor_rows(state_root: Path, repo_root: Path, probe: RuntimeProbe) -> list[ReadinessRow]:
    rows: list[ReadinessRow] = []
    current_process = _pid_alive(state_root / "daemon.pid", ("orchestrate_live",))
    for profile_path in sorted((state_root / "profiles").glob("conductor_*.json")):
        profile = _read_json(profile_path)
        if not isinstance(profile, dict):
            continue
        name = profile_path.stem
        flags, runtime_evidence, runtime_errors, runtime_success_at = _probe_agent_runtime(name, probe)
        run_path = state_root / "agent_runs" / f"{name}_latest.json"
        run = _read_json(run_path)
        errors = [err for err in runtime_errors if err]
        if isinstance(run, dict):
            run_errors = run.get("errors")
            if isinstance(run_errors, list):
                err = _normalize_error(" ".join(str(item) for item in run_errors))
                if err:
                    errors.append(err)
        witness_path = state_root / "witness" / f"conductor_{name}.jsonl"
        for event in reversed(_read_jsonl(witness_path)):
            blob = " ".join(str(value) for value in event.values()).lower()
            if any(marker in blob for marker in ("database repaired", "db repaired", "db_repaired")):
                break
            if event.get("error") or str(event.get("event", "")).upper() == "ERROR":
                err = _normalize_error(
                    str(
                        event.get("error")
                        or event.get("message")
                        or event.get("detail")
                        or ""
                    )
                )
                if err:
                    errors.append(err)
        evidence = [
            str(profile_path),
            str(run_path),
            str(witness_path),
            str(repo_root / "dharma_swarm/conductors.py"),
            str(repo_root / "dharma_swarm/orchestrate_live.py"),
        ]
        evidence.extend(runtime_evidence)
        rows.append(
            _row(
                candidate_kind="persistent_agent_candidate",
                name=name,
                current_tier="L3",
                registered_identity=True,
                identity_path=str(profile_path),
                passport_present=_passport_present(name, state_root, profile),
                current_process_present=current_process,
                last_success_at=_iso(runtime_success_at),
                blocking_errors=sorted(set(errors)),
                evidence_paths=evidence,
                **flags,
            )
        )
    return rows


def _cron_rows(state_root: Path) -> list[ReadinessRow]:
    rows: list[ReadinessRow] = []
    jobs_doc = _read_json(state_root / "cron" / "jobs.json")
    jobs = jobs_doc.get("jobs", []) if isinstance(jobs_doc, dict) else []
    if not isinstance(jobs, list):
        return rows
    for job in jobs:
        if not isinstance(job, dict):
            continue
        name = f"cron:{job.get('name') or job.get('id') or 'unknown'}"
        errors = []
        if job.get("last_status") == "error":
            err = _normalize_error(str(job.get("last_error") or "job error"))
            if err:
                errors.append(err)
        rows.append(
            _row(
                candidate_kind="script",
                name=name,
                current_tier="L3" if job.get("enabled") else "L1",
                registered_identity=False,
                blocking_errors=errors,
                evidence_paths=[str(state_root / "cron" / "jobs.json")],
            )
        )
    return rows


def _daemon_and_framework_rows(state_root: Path, repo_root: Path, agora_root: Path) -> list[ReadinessRow]:
    rows = [
        _row(
            candidate_kind="daemon",
            name="dharma_swarm_orchestrate_live_daemon",
            current_tier="L3",
            registered_identity=False,
            current_process_present=_pid_alive(state_root / "daemon.pid", ("orchestrate_live",)),
            evidence_paths=[
                str(state_root / "daemon.pid"),
                str(state_root / "logs" / "swarm.log"),
                str(repo_root / "dharma_swarm/orchestrate_live.py"),
            ],
        ),
        _row(
            candidate_kind="daemon",
            name="dharma_swarm_cron_daemon",
            current_tier="L3",
            registered_identity=False,
            current_process_present=_pid_alive(state_root / "cron" / "daemon.pid", ("cron",)),
            evidence_paths=[
                str(state_root / "cron" / "daemon.pid"),
                str(state_root / "cron" / "jobs.json"),
            ],
        ),
    ]
    if agora_root.exists():
        rows.append(
            _row(
                candidate_kind="framework",
                name="dharmic_agora_agent_frameworks",
                current_tier="L0",
                registered_identity=False,
                evidence_paths=[
                    str(agora_root / "agora/coordinator.py"),
                    str(agora_root / "agora/auth.py"),
                ],
            )
        )
    return rows


def build_readiness_rows(
    *,
    repo_root: Path = DEFAULT_REPO_ROOT,
    state_root: Path = DEFAULT_STATE_ROOT,
    agora_root: Path = DEFAULT_AGORA_ROOT,
) -> list[ReadinessRow]:
    probe = RuntimeProbe(state_root / "state" / "runtime.db")
    try:
        rows: list[ReadinessRow] = []
        rows.extend(_registered_agent_rows(state_root, repo_root, probe))
        rows.extend(_conductor_rows(state_root, repo_root, probe))
        rows.extend(_cron_rows(state_root))
        rows.extend(_daemon_and_framework_rows(state_root, repo_root, agora_root))
        return rows
    finally:
        probe.close()


def readiness_schema() -> dict[str, Any]:
    bool_props = {
        field: {"type": "boolean"}
        for field in READINESS_FIELDS
        if field.endswith("_present")
        or field in {"registered_identity", "count_as_l4", "execution_lease_required"}
    }
    props: dict[str, Any] = {
        "candidate_kind": {
            "type": "string",
            "enum": [
                "registered_worker",
                "persistent_agent_candidate",
                "daemon",
                "script",
                "framework",
            ],
        },
        "name": {"type": "string", "minLength": 1},
        "current_tier": {"type": "string", "enum": list(TIERS)},
        "target_tier": {"type": "string", "const": "L4"},
        "identity_path": {"type": ["string", "null"]},
        "last_success_at": {"type": ["string", "null"]},
        "blocking_errors": {"type": "array", "items": {"type": "string"}},
        "next_required_action": {"type": "string", "minLength": 1},
        "evidence_paths": {"type": "array", "items": {"type": "string"}},
    }
    props.update(bool_props)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "dharma_swarm L4 persistent-agent readiness row",
        "type": "object",
        "additionalProperties": False,
        "required": READINESS_FIELDS,
        "properties": props,
    }


def _missing_fields(row: ReadinessRow) -> list[str]:
    data = asdict(row)
    missing = [
        field
        for field in (
            "passport_present",
            "wake_claim_present",
            "runtime_session_present",
            "delegation_run_present",
            "context_bundle_present",
            "routing_decision_present",
            "memory_receipts_present",
            "artifact_present",
            "outcome_present",
            "recent_success_present",
            "current_process_present",
        )
        if not data[field]
    ]
    if data["execution_lease_required"] and not data["execution_lease_present"]:
        missing.insert(6, "execution_lease_present")
    return missing


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_report(rows: list[ReadinessRow], generated_at: datetime) -> str:
    l4_count = sum(1 for row in rows if row.count_as_l4)
    tier_counts = Counter(row.current_tier for row in rows)
    kind_counts = Counter(row.candidate_kind for row in rows)
    blocked = [row for row in rows if row.blocking_errors]
    lines = [
        "# L4 Persistent-Agent Readiness Report",
        "",
        f"Generated: {_iso(generated_at)}",
        "",
        f"Exact L4 count: **{l4_count}**",
        f"Rows: **{len(rows)}**",
        "",
        "This report is generated from live local state by `scripts/runtime/persistent_agent_census.py`.",
        "It does not wake agents, mutate runtime state, or expose secret values.",
        "L4 evidence booleans require one live TaskClaim/DelegationRun/session chain; unrelated historical rows do not aggregate into promotion.",
        "",
        "TaskClaim / ExecutionLease boundary: see `13_ontology_bridge.md`.",
        "",
        "## Counts",
        "",
        "| Group | Count |",
        "|---|---:|",
    ]
    for tier in TIERS:
        lines.append(f"| {tier} | {tier_counts.get(tier, 0)} |")
    lines.append("")
    lines.append("| Candidate kind | Count |")
    lines.append("|---|---:|")
    for kind, count in sorted(kind_counts.items()):
        lines.append(f"| {kind} | {count} |")
    lines.extend(
        [
            "",
            "## Blocked Candidates",
            "",
            "| Name | Tier | Blocking errors |",
            "|---|---|---|",
        ]
    )
    for row in blocked:
        lines.append(
            f"| {_md_cell(row.name)} | {row.current_tier} | "
            f"{_md_cell('; '.join(row.blocking_errors))} |"
        )
    if not blocked:
        lines.append("| none | | |")
    lines.extend(
        [
            "",
            "## Readiness Rows",
            "",
            "| Name | Kind | Tier | L4? | Missing evidence | Next required action |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        missing = ", ".join(_missing_fields(row)) or "none"
        lines.append(
            f"| {_md_cell(row.name)} | {row.candidate_kind} | {row.current_tier} | "
            f"{str(row.count_as_l4).lower()} | {_md_cell(missing)} | "
            f"{_md_cell(row.next_required_action)} |"
        )
    lines.extend(
        [
            "",
            "## First Cultivation Target",
            "",
            "`cyber-glm5` remains the first cultivation target. Its next action is the value in `next_required_action` in `l4_readiness.jsonl`; until that row has passport, wake claim, session, run, context, route, required lease evidence, memory receipts, artifact, recent outcome, and supervised process evidence on one chain, it is not L4.",
            "",
        ]
    )
    report = "\n".join(lines)
    assert_no_secret_text(report)
    return report


def write_outputs(rows: list[ReadinessRow], output_dir: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "l4_readiness.jsonl"
    report_path = output_dir / "l4_readiness_report.md"
    schema_path = output_dir / "l4_readiness_schema.json"
    schema_text = json.dumps(readiness_schema(), indent=2, sort_keys=True) + "\n"
    jsonl_lines = [json.dumps(asdict(row), sort_keys=True) for row in rows]
    report = render_report(rows, _utc_now())
    for text in [schema_text, "\n".join(jsonl_lines), report]:
        assert_no_secret_text(text)
    schema_path.write_text(schema_text, encoding="utf-8")
    jsonl_path.write_text("\n".join(jsonl_lines) + "\n", encoding="utf-8")
    report_path.write_text(report, encoding="utf-8")
    return jsonl_path, report_path, schema_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate L4 persistent-agent readiness artifacts."
    )
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--agora-root", type=Path, default=DEFAULT_AGORA_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = build_readiness_rows(
        repo_root=args.repo_root,
        state_root=args.state_root,
        agora_root=args.agora_root,
    )
    jsonl_path, report_path, schema_path = write_outputs(rows, args.output_dir)
    l4_count = sum(1 for row in rows if row.count_as_l4)
    blocked = sum(1 for row in rows if row.blocking_errors)
    print(f"wrote {len(rows)} readiness rows")
    print(f"l4_count={l4_count}")
    print(f"blocked_candidates={blocked}")
    print(jsonl_path)
    print(report_path)
    print(schema_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
