"""Read-only audit tools for claude-mem.

The audit does not decide truth automatically. It creates a stratified review
packet, computes queue lag, and scores human/agent labels once reviewers add
them.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LABELS = ("true", "mostly_true", "false", "unverifiable", "stale_but_once_true", "unreviewed")


@dataclass(frozen=True)
class QueueLag:
    total_messages: int
    active_pending: int
    failed: int
    processed: int
    processing: int
    oldest_active_age_hours: float | None
    oldest_failed_age_hours: float | None
    by_status_type: list[dict[str, Any]]
    latest_summary_by_project: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_messages": self.total_messages,
            "active_pending": self.active_pending,
            "failed": self.failed,
            "processed": self.processed,
            "processing": self.processing,
            "oldest_active_age_hours": self.oldest_active_age_hours,
            "oldest_failed_age_hours": self.oldest_failed_age_hours,
            "by_status_type": self.by_status_type,
            "latest_summary_by_project": self.latest_summary_by_project,
        }


def default_db_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".claude-mem" / "claude-mem.db"


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _now_epoch_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _age_hours(epoch_ms: int | None, now_ms: int) -> float | None:
    if not epoch_ms:
        return None
    return round(max(0, now_ms - int(epoch_ms)) / 3_600_000, 2)


def queue_lag(db_path: Path, *, now_ms: int | None = None) -> QueueLag:
    now_ms = now_ms or _now_epoch_ms()
    with _connect(db_path) as conn:
        if not _table_exists(conn, "pending_messages"):
            return QueueLag(0, 0, 0, 0, 0, None, None, [], [])

        by_status_type = [
            dict(row)
            for row in conn.execute(
                """
                SELECT status, message_type, count(*) AS count,
                       min(created_at_epoch) AS oldest_created_at_epoch,
                       max(created_at_epoch) AS newest_created_at_epoch
                FROM pending_messages
                GROUP BY status, message_type
                ORDER BY status, message_type
                """
            )
        ]
        counts = {
            row["status"]: counts + int(row["count"])
            for row in by_status_type
            for counts in [0]
        }
        # The comprehension above is intentionally simple per row; merge repeats.
        counts = {}
        for row in by_status_type:
            counts[row["status"]] = counts.get(row["status"], 0) + int(row["count"])

        oldest_active = conn.execute(
            """
            SELECT min(created_at_epoch) AS oldest
            FROM pending_messages
            WHERE status IN ('pending', 'processing')
            """
        ).fetchone()["oldest"]
        oldest_failed = conn.execute(
            "SELECT min(created_at_epoch) AS oldest FROM pending_messages WHERE status='failed'"
        ).fetchone()["oldest"]

        latest_summary_by_project: list[dict[str, Any]] = []
        if _table_exists(conn, "session_summaries"):
            latest_summary_by_project = [
                {
                    **dict(row),
                    "age_hours": _age_hours(row["latest_created_at_epoch"], now_ms),
                }
                for row in conn.execute(
                    """
                    SELECT project, count(*) AS summaries,
                           max(created_at) AS latest_created_at,
                           max(created_at_epoch) AS latest_created_at_epoch
                    FROM session_summaries
                    GROUP BY project
                    ORDER BY summaries DESC
                    """
                )
            ]

    return QueueLag(
        total_messages=sum(int(row["count"]) for row in by_status_type),
        active_pending=counts.get("pending", 0) + counts.get("processing", 0),
        failed=counts.get("failed", 0),
        processed=counts.get("processed", 0),
        processing=counts.get("processing", 0),
        oldest_active_age_hours=_age_hours(oldest_active, now_ms),
        oldest_failed_age_hours=_age_hours(oldest_failed, now_ms),
        by_status_type=by_status_type,
        latest_summary_by_project=latest_summary_by_project,
    )


def _count(conn: sqlite3.Connection, table: str) -> int:
    if not _table_exists(conn, table):
        return 0
    return int(conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0])


def stats(db_path: Path) -> dict[str, Any]:
    with _connect(db_path) as conn:
        projects = []
        if _table_exists(conn, "observations"):
            projects = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT project, count(*) AS observations
                    FROM observations
                    GROUP BY project
                    ORDER BY observations DESC
                    LIMIT 20
                    """
                )
            ]
        return {
            "db_path": str(db_path),
            "observations": _count(conn, "observations"),
            "session_summaries": _count(conn, "session_summaries"),
            "sdk_sessions": _count(conn, "sdk_sessions"),
            "user_prompts": _count(conn, "user_prompts"),
            "pending_messages": _count(conn, "pending_messages"),
            "top_observation_projects": projects,
        }


def _query_observations(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    if not _table_exists(conn, "observations"):
        return []
    return [dict(row) for row in conn.execute(sql, params)]


def _sample_rows(rows: list[dict[str, Any]], limit: int, rng: random.Random) -> list[dict[str, Any]]:
    if len(rows) <= limit:
        return rows
    picks = rng.sample(range(len(rows)), limit)
    return [rows[i] for i in sorted(picks)]


def _observation_claim(row: dict[str, Any]) -> str:
    parts = [
        row.get("title") or "",
        row.get("subtitle") or "",
        row.get("facts") or "",
        row.get("narrative") or "",
        row.get("text") or "",
    ]
    return "\n".join(part for part in parts if part).strip()[:1600]


def _summary_claim(row: dict[str, Any]) -> str:
    parts = [
        row.get("request") or "",
        row.get("investigated") or "",
        row.get("learned") or "",
        row.get("completed") or "",
        row.get("next_steps") or "",
        row.get("notes") or "",
    ]
    return "\n".join(part for part in parts if part).strip()[:1600]


def _sample_item(bucket: str, source_type: str, row: dict[str, Any]) -> dict[str, Any]:
    claim = _summary_claim(row) if source_type == "summary" else _observation_claim(row)
    return {
        "bucket": bucket,
        "source_type": source_type,
        "id": row.get("id"),
        "project": row.get("project"),
        "created_at": row.get("created_at"),
        "created_at_epoch": row.get("created_at_epoch"),
        "type": row.get("type") if source_type == "observation" else "summary",
        "claim_text": claim,
        "label": "unreviewed",
        "ground_truth_ref": "",
        "review_notes": "",
    }


def sample_audit_packet(
    db_path: Path,
    *,
    project: str = "dhyana",
    seed: int = 7,
    target: int = 50,
) -> dict[str, Any]:
    rng = random.Random(seed)
    samples: list[dict[str, Any]] = []
    with _connect(db_path) as conn:
        recent = _query_observations(
            conn,
            """
            SELECT * FROM observations
            WHERE project=?
            ORDER BY created_at_epoch DESC
            LIMIT 80
            """,
            (project,),
        )
        older = _query_observations(
            conn,
            """
            SELECT * FROM observations
            WHERE project=?
            ORDER BY created_at_epoch ASC
            LIMIT 120
            """,
            (project,),
        )
        corrections = _query_observations(
            conn,
            """
            SELECT * FROM observations
            WHERE project=?
              AND (
                coalesce(title, '') || ' ' || coalesce(subtitle, '') || ' ' ||
                coalesce(facts, '') || ' ' || coalesce(narrative, '') || ' ' ||
                coalesce(text, '')
              ) LIKE '%correct%'
            ORDER BY created_at_epoch DESC
            LIMIT 80
            """,
            (project,),
        )
        high_impact = _query_observations(
            conn,
            """
            SELECT * FROM observations
            WHERE project=?
              AND (
                coalesce(title, '') || ' ' || coalesce(subtitle, '') || ' ' ||
                coalesce(facts, '') || ' ' || coalesce(narrative, '') || ' ' ||
                coalesce(text, '')
              ) LIKE '%architecture%'
            ORDER BY created_at_epoch DESC
            LIMIT 80
            """,
            (project,),
        )
        for bucket, rows, limit in (
            ("recent_observations", recent, 15),
            ("older_observations", older, 15),
            ("corrections_reversals", corrections, 10),
            ("high_impact_architecture", high_impact, 5),
        ):
            for row in _sample_rows(rows, limit, rng):
                samples.append(_sample_item(bucket, "observation", row))

        if _table_exists(conn, "session_summaries"):
            summaries = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT * FROM session_summaries
                    WHERE project=?
                    ORDER BY created_at_epoch DESC
                    LIMIT 20
                    """,
                    (project,),
                )
            ]
            for row in _sample_rows(summaries, 5, rng):
                samples.append(_sample_item("session_summaries", "summary", row))

    seen: set[tuple[str, int]] = set()
    deduped: list[dict[str, Any]] = []
    for item in samples:
        key = (str(item["source_type"]), int(item["id"] or 0))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    if len(deduped) < target:
        needed = target - len(deduped)
        with _connect(db_path) as conn:
            top_up_rows = _query_observations(
                conn,
                """
                SELECT * FROM observations
                WHERE project=?
                ORDER BY created_at_epoch DESC
                LIMIT 400
                """,
                (project,),
            )
        top_up = []
        for row in top_up_rows:
            key = ("observation", int(row.get("id") or 0))
            if key in seen:
                continue
            seen.add(key)
            top_up.append(row)
        for row in _sample_rows(top_up, needed, rng):
            deduped.append(_sample_item("top_up_observations", "observation", row))

    return {
        "_meta": {
            "kind": "claude_mem_accuracy_audit_packet",
            "db_path": str(db_path),
            "project": project,
            "seed": seed,
            "target": target,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "label_values": list(LABELS),
            "instructions": (
                "Review each claim_text against ground truth. Set label to true, "
                "mostly_true, false, unverifiable, or stale_but_once_true."
            ),
        },
        "stats": stats(db_path),
        "queue_lag": queue_lag(db_path).to_dict(),
        "samples": deduped,
    }


def score_packet(packet: dict[str, Any]) -> dict[str, Any]:
    samples = list(packet.get("samples") or [])
    counts = {label: 0 for label in LABELS}
    invalid = 0
    for sample in samples:
        label = str(sample.get("label", "unreviewed"))
        if label not in counts:
            invalid += 1
            continue
        counts[label] += 1
    reviewed = sum(counts[label] for label in LABELS if label != "unreviewed")
    falsehoods = counts["false"]
    stale = counts["stale_but_once_true"]
    unverifiable = counts["unverifiable"]
    return {
        "total_samples": len(samples),
        "reviewed_samples": reviewed,
        "counts": counts,
        "invalid_labels": invalid,
        "falsehood_rate": round(falsehoods / reviewed, 4) if reviewed else None,
        "stale_rate": round(stale / reviewed, 4) if reviewed else None,
        "unverifiable_rate": round(unverifiable / reviewed, 4) if reviewed else None,
    }


def render_doctor(db_path: Path, *, project: str = "dhyana") -> str:
    lag = queue_lag(db_path)
    info = stats(db_path)
    lines = [
        "# Claude-Mem Doctor",
        "",
        f"- DB: {db_path}",
        f"- Observations: {info['observations']}",
        f"- Session summaries: {info['session_summaries']}",
        f"- Sessions: {info['sdk_sessions']}",
        f"- User prompts: {info['user_prompts']}",
        f"- Queue total: {lag.total_messages}",
        f"- Active pending/processing: {lag.active_pending}",
        f"- Failed: {lag.failed}",
    ]
    if lag.oldest_active_age_hours is not None:
        lines.append(f"- Oldest active queue age hours: {lag.oldest_active_age_hours}")
    project_summary = next(
        (row for row in lag.latest_summary_by_project if row.get("project") == project),
        None,
    )
    if project_summary:
        lines.append(
            f"- Latest {project} summary: {project_summary.get('latest_created_at')} "
            f"({project_summary.get('age_hours')}h old)"
        )
    else:
        lines.append(f"- Latest {project} summary: none")
    verdict = "WARN" if lag.active_pending > 100 or lag.failed > 1000 else "PASS"
    lines.append(f"- Verdict: {verdict}")
    return "\n".join(lines)


def write_packet(packet: dict[str, Any], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _default_packet_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    return Path.home() / ".dharma" / "meta" / f"claude_mem_audit_{stamp}.json"


def _cmd_sample(args: argparse.Namespace) -> int:
    db = Path(args.db).expanduser().resolve()
    packet = sample_audit_packet(db, project=args.project, seed=args.seed, target=args.target)
    output = Path(args.output).expanduser().resolve() if args.output else _default_packet_path()
    write_packet(packet, output)
    print(f"samples: {len(packet['samples'])}")
    print(f"output: {output}")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    db = Path(args.db).expanduser().resolve()
    if args.json:
        payload = {"stats": stats(db), "queue_lag": queue_lag(db).to_dict()}
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_doctor(db, project=args.project))
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    packet = json.loads(Path(args.input).read_text(encoding="utf-8"))
    print(json.dumps(score_packet(packet), indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claude_mem_audit")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sample = sub.add_parser("sample", help="Create a read-only accuracy audit packet.")
    sample.add_argument("--db", default=str(default_db_path()))
    sample.add_argument("--project", default="dhyana")
    sample.add_argument("--seed", type=int, default=7)
    sample.add_argument("--target", type=int, default=50)
    sample.add_argument("--output", default=None)
    sample.set_defaults(func=_cmd_sample)

    doctor = sub.add_parser("doctor", help="Report claude-mem queue lag and summary freshness.")
    doctor.add_argument("--db", default=str(default_db_path()))
    doctor.add_argument("--project", default="dhyana")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=_cmd_doctor)

    score = sub.add_parser("score", help="Score a labeled audit packet.")
    score.add_argument("--input", required=True)
    score.set_defaults(func=_cmd_score)

    ns = parser.parse_args(argv)
    return ns.func(ns)


if __name__ == "__main__":
    sys.exit(main())
