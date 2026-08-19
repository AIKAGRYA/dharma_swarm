#!/usr/bin/env python3
"""Lane 2 client audit engine: adversarial invariant suite -> AUDIT_REPORT.

Push-button Full Audit deliverable ($2,500 flat). Stdlib only. Foreign
targets only; systems we build are refused.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_SPEC = "dharma.client_audit_spec.v1"
SCHEMA_RECEIPT = "dharma.client_audit_receipt.v1"
FLAT_PRICE_USD = 2500
TERMINAL_SUCCESS = frozenset(
    {"completed", "complete", "done", "success", "succeeded"}
)
FORBIDDEN_IDENTITY_NEEDLES = (
    "github.com/aikagrya/dharma_swarm",
    "github.com/amitabhainarunachala/vibe-halt",
)
class IndependenceError(ValueError):
    """Charter refusal: we never audit systems we build."""

    def __init__(self, detail: str = "") -> None:
        extra = f" ({detail})" if detail else ""
        super().__init__(
            "independence charter: refuse to audit systems we build" + extra
        )


class SpecError(ValueError):
    """The submitted spec cannot be evaluated."""


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def sha256_hex(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def proof_digest(invariant_id: str, evidence: Any) -> str:
    return "sha256:" + sha256_hex(
        {"invariant_id": invariant_id, "evidence": evidence}
    )


def _normalize_remote(raw: str) -> str:
    text = raw.strip().lower()
    text = text.replace("git@", "").replace("ssh://", "").replace("https://", "")
    text = text.replace("http://", "").replace(":", "/")
    text = text.removeprefix("github.com/")
    if not text.startswith("github.com/"):
        # git@github.com:org/repo form already turned into github.com/org/repo
        if text.count("/") >= 1 and "github.com/" not in text:
            text = "github.com/" + text.lstrip("/")
    text = text.removesuffix(".git")
    return text.replace("//", "/")


def _walk_strings(obj: Any) -> list[str]:
    found: list[str] = []
    if isinstance(obj, str):
        found.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            found.extend(_walk_strings(value))
    elif isinstance(obj, list):
        for value in obj:
            found.extend(_walk_strings(value))
    return found


def assert_independence(spec: dict[str, Any]) -> None:
    target = spec.get("target")
    if not isinstance(target, dict):
        raise SpecError("target object is required")
    identity = target.get("identity")
    if not isinstance(identity, dict) or not identity:
        raise SpecError("target.identity is required")
    blob = " ".join(_walk_strings(identity)).lower()
    remotes = [_normalize_remote(item) for item in _walk_strings(identity)]
    joined = blob + " " + " ".join(remotes)
    for needle in FORBIDDEN_IDENTITY_NEEDLES:
        if needle in joined:
            raise IndependenceError(needle)


def _receipt_map(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for row in spec.get("receipts") or []:
        if not isinstance(row, dict) or not row.get("receipt_id"):
            continue
        mapped[str(row["receipt_id"])] = row
    return mapped


def _payload_digest(row: dict[str, Any]) -> str | None:
    payload = row.get("payload")
    if not isinstance(payload, dict):
        return None
    return sha256_hex(payload)


def _receipt_verified(row: dict[str, Any]) -> bool:
    actual = _payload_digest(row)
    claimed = row.get("sha256")
    if actual is None:
        return False
    if not isinstance(claimed, str) or len(claimed) != 64:
        return False
    return claimed == actual


def _covers_transition(row: dict[str, Any], transition_id: str) -> bool:
    payload = row.get("payload")
    if not isinstance(payload, dict):
        return False
    bound = payload.get("transition_id")
    return bound == transition_id or bound is None


def _parse_ts(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _verified_for(transition: dict[str, Any], receipts: dict[str, dict[str, Any]]):
    rid = transition.get("receipt_id")
    if not rid:
        return None, "missing_receipt"
    row = receipts.get(str(rid))
    if row is None:
        return None, "receipt_not_found"
    if not _receipt_verified(row):
        return None, "receipt_digest_mismatch"
    if not _covers_transition(row, str(transition.get("id"))):
        return None, "receipt_transition_mismatch"
    return row, None


def evaluate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    if spec.get("schema") not in (SCHEMA_SPEC, None):
        raise SpecError(f"unsupported schema {spec.get('schema')!r}")
    assert_independence(spec)
    transitions = spec.get("transitions")
    if not isinstance(transitions, list):
        raise SpecError("transitions list is required")
    receipts = _receipt_map(spec)
    graph = spec.get("declared_graph")
    graph_ids = list(graph) if isinstance(graph, list) else []

    unverified: list[dict[str, Any]] = []
    hallucinated: list[dict[str, Any]] = []
    digest_misses: list[str] = []
    graph_misses: list[str] = []
    reuse_misses: list[str] = []
    time_misses: list[str] = []
    seen_receipts: dict[str, str] = {}
    prev_ts: datetime | None = None

    for row in receipts.values():
        if not _receipt_verified(row):
            digest_misses.append(str(row.get("receipt_id")))

    for item in transitions:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("id") or "")
        rid = item.get("receipt_id")
        _row, reason = _verified_for(item, receipts)
        if reason is not None:
            unverified.append({"transition_id": tid, "reason": reason})
        if rid:
            rid_s = str(rid)
            if rid_s in seen_receipts:
                reuse_misses.append(tid)
            else:
                seen_receipts[rid_s] = tid
        status = str(item.get("claimed_status") or "").lower()
        if status in TERMINAL_SUCCESS and reason is not None:
            hallucinated.append(
                {
                    "transition_id": tid,
                    "claimed_status": str(item.get("claimed_status")),
                    "failure_mode": (
                        "hallucinated completion without a verified receipt "
                        f"({reason})"
                    ),
                }
            )
        if graph_ids:
            src = item.get("from_state")
            dst = item.get("to_state")
            if src in graph_ids and dst in graph_ids:
                if graph_ids.index(dst) != graph_ids.index(src) + 1:
                    graph_misses.append(tid)
        ts = _parse_ts(item.get("claimed_at"))
        if prev_ts is not None and ts is not None and ts < prev_ts:
            time_misses.append(tid)
        if ts is not None:
            prev_ts = ts

    evidence_terminal = {
        "unverified": unverified,
        "count": len(unverified),
    }
    evidence_digest = {"mismatched_receipt_ids": digest_misses}
    evidence_graph = {"skipped_or_illegal": graph_misses}
    evidence_reuse = {"reused_on": reuse_misses}
    evidence_time = {"backward": time_misses}
    evidence_halluc = {"completions": hallucinated}

    invariants = []
    packs = [
        ("INV-TERMINAL-RECEIPT", len(unverified) == 0, evidence_terminal),
        ("INV-RECEIPT-DIGEST", digest_misses == [], evidence_digest),
        ("INV-GRAPH-STEP", graph_misses == [], evidence_graph),
        ("INV-NO-RECEIPT-REUSE", reuse_misses == [], evidence_reuse),
        ("INV-TIME-MONOTONE", time_misses == [], evidence_time),
        ("INV-HALLUCINATED-COMPLETION", hallucinated == [], evidence_halluc),
    ]
    for ident, passed, evidence in packs:
        invariants.append(
            {
                "invariant_id": ident,
                "passed": passed,
                "miss_count": 0 if passed else (
                    evidence.get("count")
                    or len(evidence.get("mismatched_receipt_ids") or [])
                    or len(evidence.get("skipped_or_illegal") or [])
                    or len(evidence.get("reused_on") or [])
                    or len(evidence.get("backward") or [])
                    or len(evidence.get("completions") or [])
                ),
                "evidence": evidence,
                "proof_digest": proof_digest(ident, evidence),
            }
        )

    identity = spec["target"]["identity"]
    report = {
        "schema": SCHEMA_RECEIPT,
        "observed_at_utc": _iso_now(),
        "engagement_id": spec.get("engagement_id"),
        "client_name": spec.get("client_name"),
        "target": spec.get("target"),
        "identity_fingerprint_sha256": sha256_hex(identity),
        "pricing": {
            "usd": FLAT_PRICE_USD,
            "flat": True,
            "decoupling": "flat fee decoupled from audit outcome",
        },
        "summary": {
            "transition_count": len(transitions),
            "unverified_state_transition_count": len(unverified),
            "hallucinated_completion_count": len(hallucinated),
            "invariant_miss_count": sum(1 for row in invariants if not row["passed"]),
        },
        "unverified_state_transitions": unverified,
        "hallucinated_completions": hallucinated,
        "invariants": invariants,
        "charter": "docs/governance/INDEPENDENCE_CHARTER.md",
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Full Audit Report",
        "",
        f"- engagement: `{report.get('engagement_id')}`",
        f"- client: {report.get('client_name')}",
        f"- observed_at: {report.get('observed_at_utc')}",
        f"- identity fingerprint: `sha256:{report.get('identity_fingerprint_sha256')}`",
        f"- price: **USD {FLAT_PRICE_USD} flat**, decoupled from audit outcome",
        f"- charter: `{report.get('charter')}`",
        "",
        "We never audit systems we build. Failed invariant logs are not suppressed. "
        "All misses are published.",
        "",
        "## Unverified state transitions",
        "",
        f"- count: **{summary['unverified_state_transition_count']}**",
        "",
    ]
    if report["unverified_state_transitions"]:
        for item in report["unverified_state_transitions"]:
            lines.append(
                f"- `{item['transition_id']}`: {item['reason']}"
            )
    else:
        lines.append("- none caught")
    lines += ["", "## Hallucinated completions (no verified receipt)", ""]
    if report["hallucinated_completions"]:
        for item in report["hallucinated_completions"]:
            lines.append(
                f"- `{item['transition_id']}` claimed `{item['claimed_status']}` "
                f"— {item['failure_mode']}"
            )
    else:
        lines.append("- none caught")
    lines += ["", "## Invariant proof digests", ""]
    for item in report["invariants"]:
        mark = "PASS" if item["passed"] else "MISS"
        lines.append(
            f"- `{item['invariant_id']}` {mark} miss_count={item['miss_count']} "
            f"`{item['proof_digest']}`"
        )
    lines += [
        "",
        "---",
        "Every count above is rendered from `audit_receipt.json`. "
        "Re-run the CLI on the same spec to reproduce the proof digests.",
        "",
    ]
    return "\n".join(lines)


def _pdf_escape(text: str) -> str:
    ascii_text = text.encode("latin-1", "replace").decode("latin-1")
    return ascii_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render_pdf(markdown: str) -> bytes:
    wrapped: list[str] = []
    for raw in markdown.splitlines() or [""]:
        line = raw if raw else " "
        while len(line) > 86:
            wrapped.append(line[:86])
            line = line[86:]
        wrapped.append(line)
    pages = [wrapped[i : i + 52] for i in range(0, max(len(wrapped), 1), 52)]
    bodies: list[bytes] = []
    # object 1 catalog, 2 pages, then pairs of page+content, then font
    page_ids: list[int] = []
    content_ids: list[int] = []
    next_id = 3
    content_streams: list[bytes] = []
    for lines in pages:
        cmds = ["BT", "/F1 9 Tf", "50 750 Td"]
        for i, line in enumerate(lines):
            if i:
                cmds.append("0 -13 Td")
            cmds.append(f"({_pdf_escape(line)}) Tj")
        cmds.append("ET")
        stream = "\n".join(cmds).encode("latin-1")
        content_streams.append(stream)
        page_ids.append(next_id)
        content_ids.append(next_id + 1)
        next_id += 2
    font_id = next_id
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    obj: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: (
            f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>"
        ).encode("ascii"),
        font_id: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for pid, cid, stream in zip(page_ids, content_ids, content_streams):
        obj[pid] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {cid} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        ).encode("ascii")
        obj[cid] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )
    chunks: list[bytes] = [b"%PDF-1.4\n"]
    offsets = {0: 0}
    for n in sorted(obj):
        offsets[n] = sum(len(part) for part in chunks)
        chunks.append(f"{n} 0 obj\n".encode("ascii") + obj[n] + b"\nendobj\n")
    xref_at = sum(len(part) for part in chunks)
    max_id = max(obj)
    xref = [f"xref\n0 {max_id + 1}\n", "0000000000 65535 f \n"]
    for n in range(1, max_id + 1):
        xref.append(f"{offsets[n]:010d} 00000 n \n")
    chunks.append("".join(xref).encode("ascii"))
    chunks.append(
        (
            f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n"
        ).encode("ascii")
    )
    return b"".join(chunks)


def sample_spec() -> dict[str, Any]:
    r1 = {"receipt_id": "r-ok-1", "transition_id": "t-run", "status": "ok"}
    r_tamper = {"receipt_id": "r-tamper", "transition_id": "t-tamper", "status": "ok"}
    return {
        "schema": SCHEMA_SPEC,
        "engagement_id": "ENG-ACME-001",
        "client_name": "Acme Logistics",
        "target": {
            "name": "order-agent",
            "kind": "agent_spec",
            "identity": {
                "git_remote": "https://github.com/acme-logistics/order-agent.git",
                "vendor": "acme-logistics",
            },
        },
        "declared_graph": ["queued", "running", "completed"],
        "transitions": [
            {
                "id": "t-run",
                "from_state": "queued",
                "to_state": "running",
                "claimed_at": "2026-08-01T00:00:00Z",
                "claimed_status": "running",
                "receipt_id": "r-ok-1",
            },
            {
                "id": "t-ghost",
                "from_state": "running",
                "to_state": "completed",
                "claimed_at": "2026-08-01T00:01:00Z",
                "claimed_status": "completed",
                "receipt_id": None,
            },
            {
                "id": "t-skip",
                "from_state": "queued",
                "to_state": "completed",
                "claimed_at": "2026-08-01T00:02:00Z",
                "claimed_status": "success",
                "receipt_id": "missing-receipt",
            },
            {
                "id": "t-tamper",
                "from_state": "running",
                "to_state": "completed",
                "claimed_at": "2026-08-01T00:03:00Z",
                "claimed_status": "done",
                "receipt_id": "r-tamper",
            },
        ],
        "receipts": [
            {"receipt_id": "r-ok-1", "payload": r1, "sha256": sha256_hex(r1)},
            {"receipt_id": "r-tamper", "payload": r_tamper, "sha256": "0" * 64},
        ],
    }


def write_deliverable(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown = render_markdown(report)
    (output_dir / "AUDIT_REPORT.md").write_text(markdown, encoding="utf-8")
    (output_dir / "AUDIT_REPORT.pdf").write_bytes(render_pdf(markdown))
    (output_dir / "audit_receipt.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", help="path to dharma.client_audit_spec.v1 JSON")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--sample",
        action="store_true",
        help="run the foreign Acme fixture (not a self-audit)",
    )
    args = parser.parse_args(argv)
    try:
        if args.sample:
            spec = sample_spec()
        elif args.spec:
            spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
            if not isinstance(spec, dict):
                raise SpecError("spec must be a JSON object")
        else:
            parser.error("provide --spec or --sample")
        report = evaluate_spec(spec)
    except IndependenceError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError, SpecError) as exc:
        print(f"spec error: {exc}", file=sys.stderr)
        return 1
    out = Path(args.output_dir)
    write_deliverable(report, out)
    if args.sample:
        (out / "sample_spec.json").write_text(
            json.dumps(spec, indent=2) + "\n", encoding="utf-8"
        )
    print(str(out / "AUDIT_REPORT.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
