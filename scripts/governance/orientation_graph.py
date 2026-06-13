#!/usr/bin/env python3
"""orientation_graph.py — one-command, whole-system orientation view.

Renders the organism AT ONCE — identity (why), organs, active tracks,
canon custody, liveness, and broken register — as one typed, queryable
packet. A fresh agent should be able to answer "what is this system,
what lives inside it, what is live, what is broken, and what is canon"
from this single command.

This command does NOT own any fact. It projects from the existing owners:

    identity   -> foundations/THE_ORGANISM.md + docs/vision_maps/NORTH_STAR.md
    organs     -> docs/governance/VENTURE_CELL_PORTFOLIO.yaml
    tracks     -> docs/governance/ACTIVE_TRACK.yaml
    custody    -> docs/docops/assertions.yaml (canonical_guard.registered) + git
    liveness   -> live ops census receipt (scripts/runtime/live_ops_census.py)
    broken     -> docs/state/BROKEN_REGISTER.md

Doctrine line that must hold (same as the reconciliation track's):
    Read models project truth from owners; they do not become authority.

Usage:
    python3 scripts/governance/orientation_graph.py          # human view
    python3 scripts/governance/orientation_graph.py --json   # machine packet
    make orient

Write behavior: never writes. Exit code: always 0 (informational).
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def _state_dir() -> Path:
    """Resolve the dharma state root the same way the census owner does
    (honors DHARMA_STATE_DIR). This view reads receipts from there; it
    never writes."""
    return Path(os.environ.get("DHARMA_STATE_DIR", "~/.dharma")).expanduser()

ORGANISM_DOC = REPO_ROOT / "foundations/THE_ORGANISM.md"
NORTH_STAR_DOC = REPO_ROOT / "docs/vision_maps/NORTH_STAR.md"
GENOME_SYNTHESIS = REPO_ROOT / "reports/swarm_genome/2026-06-11/SYNTHESIS.md"
PORTFOLIO = REPO_ROOT / "docs/governance/VENTURE_CELL_PORTFOLIO.yaml"
ACTIVE_TRACK = REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml"
ASSERTIONS = REPO_ROOT / "docs/docops/assertions.yaml"
BROKEN_REGISTER = REPO_ROOT / "docs/state/BROKEN_REGISTER.md"


def _census_receipt_path() -> Path | None:
    """Receipt path declared by the census owner (scripts/runtime/live_ops_census.py).

    State-dir knowledge stays in the owner; this view only borrows its
    DEFAULT_OUTPUT constant (which honors DHARMA_STATE_DIR).
    """
    census_src = REPO_ROOT / "scripts/runtime/live_ops_census.py"
    if not census_src.exists():
        return None
    spec = importlib.util.spec_from_file_location("_live_ops_census", census_src)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    return Path(module.DEFAULT_OUTPUT)


@dataclass
class Identity:
    one_line: str
    read_first: list[str]
    missing_sources: list[str] = field(default_factory=list)


@dataclass
class Organ:
    id: str
    instrument: str
    status: str
    external_name: str = ""


@dataclass
class Track:
    id: str
    status: str
    serves: str
    owner: str
    owned_surfaces: list[str] = field(default_factory=list)


@dataclass
class CustodyReport:
    registered_total: int
    present: int
    missing: list[str] = field(default_factory=list)


@dataclass
class Liveness:
    receipt: str
    generated_at: str = ""
    surfaces: list[dict[str, str]] = field(default_factory=list)


@dataclass
class BrokenItem:
    id: str
    status: str
    title: str


@dataclass
class Loop1Closure:
    """Loop 1 (provider chain + dispatch) closure proof, projected read-only
    from the latest delegation_runs receipt. LIVE only when that receipt
    carries a non-empty provider AND model — the spine dispatch actually
    recorded which brain answered. Owner of the fact: runtime_state's
    delegation_runs.receipt_json; this view never writes."""
    live: bool
    provider: str = ""
    model: str = ""
    detail: str = ""


@dataclass
class LoopClosure:
    """Read-only closure projection for one cybernetic loop (Phase 2).

    verdict is one of LIVE / PARTIAL / NOT-LIVE, decided by the loop's own
    liveCondition applied to its declared receipt surface. This view owns
    no fact — it reads the surface its loop's owner writes and never writes
    anything itself. Honest by construction: NOT-LIVE whenever the surface
    lacks fresh, real, discriminating data; PARTIAL when the sense/constrain
    arm is live but act/adapt does not close (typically gated behind Loop 1).
    """
    loop: int
    name: str
    verdict: str = "NOT-LIVE"
    latest: str = ""
    reason: str = ""


@dataclass
class OrientationPacket:
    identity: Identity
    organs: list[Organ]
    tracks: list[Track]
    custody: CustodyReport
    liveness: Liveness
    broken: list[BrokenItem]
    loop1: Loop1Closure
    loops: list[LoopClosure] = field(default_factory=list)


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def build_identity() -> Identity:
    read_first = [
        "foundations/THE_ORGANISM.md",
        "docs/vision_maps/NORTH_STAR.md",
        "reports/swarm_genome/2026-06-11/SYNTHESIS.md",
        "docs/MEGAFILE_INDEX.md",
    ]
    missing = [p for p in read_first if not (REPO_ROOT / p).exists()]
    one_line = ""
    if ORGANISM_DOC.exists():
        for line in ORGANISM_DOC.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("> **dharma_swarm is"):
                one_line = stripped.lstrip("> ").strip().strip("*")
                break
    if not one_line:
        one_line = ("(identity owner missing — read docs/vision_maps/"
                    "NORTH_STAR.md §1 for the telos)")
    return Identity(one_line=one_line, read_first=read_first,
                    missing_sources=missing)


def build_organs() -> list[Organ]:
    data = _load_yaml(PORTFOLIO)
    organs: list[Organ] = []
    for cell in data.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        organs.append(Organ(
            id=str(cell.get("id", "")),
            instrument=str(cell.get("instrument", "")),
            status=str(cell.get("status", "")),
            external_name=str(cell.get("external_name", "") or ""),
        ))
    return organs


def build_tracks() -> list[Track]:
    data = _load_yaml(ACTIVE_TRACK)
    tracks: list[Track] = []
    for entry in data.get("active_tracks") or []:
        if not isinstance(entry, dict):
            continue
        tracks.append(Track(
            id=str(entry.get("id", "")),
            status=str(entry.get("status", "")),
            serves=str(entry.get("serves", "")),
            owner=str(entry.get("owner", "")),
            owned_surfaces=[str(s) for s in entry.get("owned_surfaces") or []],
        ))
    return tracks


def build_custody() -> CustodyReport:
    registered: list[str] = []
    try:
        data = json.loads(ASSERTIONS.read_text(encoding="utf-8"))
        guard = data.get("canonical_guard", {})
        registered = [str(p) for p in guard.get("registered") or []]
    except Exception:
        data = _load_yaml(ASSERTIONS)
        guard = data.get("canonical_guard", {}) if isinstance(data, dict) else {}
        registered = [str(p) for p in guard.get("registered") or []]
    missing = [p for p in registered if not (REPO_ROOT / p).exists()]
    return CustodyReport(
        registered_total=len(registered),
        present=len(registered) - len(missing),
        missing=missing,
    )


def build_liveness() -> Liveness:
    receipt_path = _census_receipt_path()
    if receipt_path is None or not receipt_path.exists():
        return Liveness(receipt=(
            "no census receipt — run "
            "python3 scripts/runtime/live_ops_census.py --write"))
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception:
        return Liveness(receipt=f"unreadable receipt at {receipt_path}")
    surfaces = []
    for surface in payload.get("surfaces") or []:
        if not isinstance(surface, dict):
            continue
        surfaces.append({
            "id": str(surface.get("surface_id", "")),
            "label": str(surface.get("label", "")),
            "status": str(surface.get("status", "")),
        })
    return Liveness(
        receipt=str(receipt_path),
        generated_at=str(payload.get("generated_at", "")),
        surfaces=surfaces,
    )


_BR_HEAD = re.compile(r"^###\s+(?P<id>BR-\d+)\s*[—-]\s*(?P<title>.+)$")
_BR_STATUS = re.compile(r"^-\s*\*\*status:\*\*\s*(?P<status>[A-Z]+)")


def build_broken() -> list[BrokenItem]:
    items: list[BrokenItem] = []
    if not BROKEN_REGISTER.exists():
        return items
    current: BrokenItem | None = None
    for line in BROKEN_REGISTER.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("## CLOSED"):
            break
        head = _BR_HEAD.match(stripped)
        if head:
            current = BrokenItem(id=head.group("id"), status="OPEN",
                                 title=head.group("title").strip())
            items.append(current)
            continue
        status = _BR_STATUS.match(stripped)
        if status and current is not None:
            current.status = status.group("status")
    return [i for i in items if i.status not in {"FIXED", "CLOSED"}]


def _runtime_db_path() -> Any:
    """Resolve the runtime-state db path from its owner (runtime_state),
    not a hardcoded literal. Borrows the owner's DEFAULT_RUNTIME_DB constant."""
    try:
        from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB

        return DEFAULT_RUNTIME_DB
    except Exception:
        return Path.home() / ".dharma" / "state" / "runtime.db"


def build_loop1_closure(db_path: Any = None) -> Loop1Closure:
    """Project Loop 1 closure from the latest delegation_runs receipt.

    LIVE only when the most recent receipt (by started_at, then rowid) carries
    a non-empty provider AND model. This view owns nothing — it reads the
    receipt_json column the spine dispatch writes (runtime_state owner)."""
    import sqlite3

    path = Path(db_path) if db_path is not None else _runtime_db_path()
    if not Path(path).exists():
        return Loop1Closure(live=False, detail=f"no runtime db at {path}")
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except Exception:
        try:
            conn = sqlite3.connect(str(path))
        except Exception as exc:  # pragma: no cover - defensive
            return Loop1Closure(live=False, detail=f"db unreadable: {exc}")
    try:
        row = conn.execute(
            "SELECT receipt_json FROM delegation_runs "
            "WHERE receipt_json IS NOT NULL AND receipt_json != '' "
            "ORDER BY started_at DESC, rowid DESC LIMIT 1"
        ).fetchone()
    except Exception as exc:
        conn.close()
        return Loop1Closure(live=False, detail=f"delegation_runs query failed: {exc}")
    conn.close()
    if not row or not row[0]:
        return Loop1Closure(live=False, detail="no persisted EvidenceReceipt yet")
    try:
        blob = json.loads(row[0])
    except Exception:
        return Loop1Closure(live=False, detail="latest receipt_json unparseable")
    provider = str(blob.get("provider", "") or "")
    model = str(blob.get("model", "") or "")
    live = bool(provider and model)
    detail = (
        "latest dispatch receipt carries provider+model"
        if live
        else "latest receipt missing provider and/or model"
    )
    return Loop1Closure(live=live, provider=provider, model=model, detail=detail)


# ---------------------------------------------------------------------------
# Phase 2 — read-only closure checks for the fed-cascade loops.
# Each builder reads ONLY the receipt surface its loop's owner writes, applies
# that loop's liveCondition, and returns LIVE / PARTIAL / NOT-LIVE. No surface
# is written. Verdicts are honest: NOT-LIVE when fresh real data is absent.
# ---------------------------------------------------------------------------

_FRESH_WINDOW_S = 24 * 3600


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _parse_ts(value: Any) -> datetime.datetime | None:
    """Parse either an ISO-8601 string (with or without Z/offset) or a unix
    epoch float into a tz-aware UTC datetime. Returns None on failure."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(float(value), datetime.timezone.utc)
        except Exception:
            return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return datetime.datetime.fromtimestamp(float(s), datetime.timezone.utc)
    except (ValueError, OSError):
        pass
    iso = s.replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(iso)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def _age_seconds(dt: datetime.datetime | None) -> float | None:
    if dt is None:
        return None
    return (_now_utc() - dt).total_seconds()


def _iter_jsonl(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except Exception:
            continue


def _witness_path(state_dir: Path, when: datetime.datetime | None = None) -> Path:
    when = when or _now_utc()
    return state_dir / "witness" / f"witness_{when:%Y%m%d}.jsonl"


# Real loop-driven action prefixes (pulse, dispatch, landscape-probe, etc.).
# A row counts as "real loop work" by matching one of these positively;
# sentinel/test-fixture probes (closure-proof, destructive-command probes)
# simply fail to match and are excluded.
_REAL_ACTION_MARKERS = (
    "pulse",
    "dispatch task",
    "landscape probe",
    "mark task done",
)


def build_loop6_closure(state_dir: Path | None = None) -> LoopClosure:
    """Loop 6 (Witness Auditor). Receipt: witness_<today>.jsonl daily log.

    LIVE-arm condition: latest entry < 24h old, phase+outcome+action populated,
    outcomes discriminating (BLOCKED/WARN present, not all PASS), and rows
    dominated by real loop actions (pulse/dispatch/landscape-probe), not only
    sentinel probes. FULL closure also needs the ADAPT arm (WitnessAuditor LLM
    findings -> evolution fitness) which is provider-gated behind Loop 1 -> so
    the honest ceiling here is PARTIAL even when the sense/constrain arm is live.
    """
    sd = state_dir or _state_dir()
    loop = LoopClosure(loop=6, name="Witness Auditor")
    path = _witness_path(sd)
    rows = list(_iter_jsonl(path))
    if not rows:
        loop.reason = f"no witness rows in {path}"
        return loop
    latest = rows[-1]
    age = _age_seconds(_parse_ts(latest.get("ts")))
    fresh = age is not None and age < _FRESH_WINDOW_S
    populated = all(latest.get(k) for k in ("phase", "outcome", "action"))
    outcomes = {str(r.get("outcome", "")) for r in rows}
    discriminating = bool(outcomes & {"BLOCKED", "WARN"}) and "PASS" in outcomes
    real = sum(
        1 for r in rows
        if any(m in str(r.get("action", "")).lower() for m in _REAL_ACTION_MARKERS)
    )
    real_dominated = real > len(rows) // 2
    loop.latest = f"{latest.get('ts','')} outcome={latest.get('outcome','')}"
    if fresh and populated and discriminating and real_dominated:
        loop.verdict = "PARTIAL"
        loop.reason = (
            f"sense+constrain LIVE ({len(rows)} rows, outcomes={sorted(outcomes)}, "
            f"{real} real-action rows); ADAPT arm (WitnessAuditor LLM findings -> "
            "evolution fitness) gated behind Loop 1, so not FULL closure"
        )
    else:
        loop.verdict = "NOT-LIVE"
        loop.reason = (
            f"fresh={fresh} populated={populated} discriminating={discriminating} "
            f"real_dominated={real_dominated} ({real}/{len(rows)} real-action rows)"
        )
    return loop


def build_loop2_closure(state_dir: Path | None = None) -> LoopClosure:
    """Loop 2 (Organism Heartbeat). Receipts: algedonic_signals.jsonl
    (omega_divergence/telos_drift rows = heartbeat-sourced) + the heartbeat
    decision store organism_memory/entities.jsonl (algedonic_event/gnani_verdict).

    LIVE needs: a heartbeat-sourced row < 24h old whose value moves across the
    window (real moving OrganismPulse invariant, not a constant sentinel) AND a
    corresponding fresh heartbeat-decision row in the same window (INTERPRET+act).
    PARTIAL when SENSE->INTERPRET fired but the decision store is stale / no
    daemon running (ACT/ADAPT does not close).
    """
    sd = state_dir or _state_dir()
    loop = LoopClosure(loop=2, name="Organism Heartbeat")
    sig_path = sd / "algedonic_signals.jsonl"
    hb = [r for r in _iter_jsonl(sig_path)
          if str(r.get("kind")) in {"omega_divergence", "telos_drift"}]
    if not hb:
        loop.reason = f"no heartbeat-sourced rows in {sig_path}"
        return loop
    latest = hb[-1]
    age = _age_seconds(_parse_ts(latest.get("timestamp")))
    sense_fresh = age is not None and age < _FRESH_WINDOW_S
    values = {round(float(r.get("value", 0.0)), 6) for r in hb if "value" in r}
    moving = len(values) > 1
    loop.latest = (f"{latest.get('kind')} value={latest.get('value')} "
                   f"age_h={round(age/3600,1) if age is not None else 'NA'}")

    # ACT/ADAPT: fresh heartbeat-decision row in organism_memory/entities.jsonl.
    ent_path = sd / "organism_memory" / "entities.jsonl"
    decision_age: float | None = None
    for r in _iter_jsonl(ent_path):
        if str(r.get("entity_type")) in {"algedonic_event", "gnani_verdict"}:
            a = _age_seconds(_parse_ts(r.get("timestamp")))
            if a is not None and (decision_age is None or a < decision_age):
                decision_age = a
    decision_fresh = decision_age is not None and decision_age < _FRESH_WINDOW_S

    if sense_fresh and moving and decision_fresh:
        loop.verdict = "LIVE"
        loop.reason = ("SENSE->INTERPRET->ACT closes: fresh moving heartbeat "
                       "signal + fresh heartbeat-decision row")
    elif sense_fresh and moving:
        loop.verdict = "PARTIAL"
        da = "none" if decision_age is None else f"{round(decision_age/3600,1)}h old"
        loop.reason = ("SENSE->INTERPRET LIVE (fresh moving OrganismPulse) but "
                       f"ACT/ADAPT does not close: heartbeat-decision store {da}")
    else:
        loop.verdict = "NOT-LIVE"
        loop.reason = (f"sense_fresh={sense_fresh} moving={moving} "
                       f"({len(values)} distinct values)")
    return loop


def build_loop5_closure(state_dir: Path | None = None) -> LoopClosure:
    """Loop 5 (Zeitgeist Scanner). Receipt: meta/gate_pressure.json — the
    ADAPT-half surface that closes the S3<->S4 feedback (telos_gates reads it).

    Mechanically LIVE needs: file exists, expires > now (signal not expired),
    trust_mode_override non-empty, mtime recent. FULL closure additionally
    requires the driving witness BLOCKED window to contain real agent-attributed
    actions rather than test fixtures — when the gate-block signal derives from
    test-fixture witness rows, the loop adapts on synthetic data -> PARTIAL.
    """
    sd = state_dir or _state_dir()
    loop = LoopClosure(loop=5, name="Zeitgeist Scanner")
    gp_path = sd / "meta" / "gate_pressure.json"
    if not gp_path.exists():
        loop.reason = f"no gate_pressure.json at {gp_path}"
        return loop
    try:
        gp = json.loads(gp_path.read_text(encoding="utf-8"))
    except Exception as exc:
        loop.reason = f"gate_pressure.json unreadable: {exc}"
        return loop
    now = _now_utc().timestamp()
    not_expired = float(gp.get("expires", 0) or 0) > now
    override = str(gp.get("trust_mode_override", "") or "")
    try:
        mtime_age = now - gp_path.stat().st_mtime
    except Exception:
        mtime_age = None
    mtime_recent = mtime_age is not None and mtime_age < _FRESH_WINDOW_S
    loop.latest = f"override={override!r} expires_in_s={round(float(gp.get('expires',0) or 0)-now)}"
    mechanically_live = not_expired and bool(override) and mtime_recent
    if not mechanically_live:
        loop.verdict = "NOT-LIVE"
        loop.reason = (f"not_expired={not_expired} override={bool(override)} "
                       f"mtime_recent={mtime_recent}")
        return loop

    # FULL closure gate: are the BLOCKED witness rows real-agent-attributed?
    rows = list(_iter_jsonl(_witness_path(sd)))[-200:]
    blocked = [r for r in rows if str(r.get("outcome")) == "BLOCKED"]
    real_blocked = sum(
        1 for r in blocked
        if any(m in str(r.get("action", "")).lower() for m in _REAL_ACTION_MARKERS)
    )
    if blocked and real_blocked > 0:
        loop.verdict = "LIVE"
        loop.reason = (f"S3<->S4 closed on real data: {real_blocked}/{len(blocked)} "
                       "BLOCKED rows carry real loop-action work (pulse/dispatch/"
                       "landscape-probe), not test fixtures")
    else:
        loop.verdict = "PARTIAL"
        loop.reason = (f"loop mechanically closed (signal fresh) but driven by "
                       f"{0 if not blocked else 'test-fixture'} real-agent BLOCKED "
                       f"rows ({real_blocked}/{len(blocked)} real) — adapts on synthetic")
    return loop


def build_loop9_closure(state_dir: Path | None = None) -> LoopClosure:
    """Loop 9 (Conductors). Real receipt: conductor_wake witness entries +
    conductor_*_notes.md narrative updates.

    LIVE needs a conductor_wake entry < 24h old whose outcome is an ACTED
    result (not just a pre-action telos-gate WARN on a proposed self-task) AND
    a fresh conductor-notes update. When wakes only emit WARN proposals (no
    provider-backed act/adapt receipt) and notes are stale -> NOT-LIVE.
    """
    sd = state_dir or _state_dir()
    loop = LoopClosure(loop=9, name="Conductors")
    rows = [r for r in _iter_jsonl(_witness_path(sd))
            if "conductor_wake" in {str(r.get("phase")), str(r.get("think_phase"))}]
    acted = [r for r in rows
             if str(r.get("outcome", "")).upper() not in {"WARN", ""}
             and (_age_seconds(_parse_ts(r.get("ts"))) or _FRESH_WINDOW_S * 2)
             < _FRESH_WINDOW_S]
    # Fresh conductor-notes update in the same window?
    notes_fresh = False
    now = _now_utc().timestamp()
    for note in ("conductor_claude_notes.md", "conductor_codex_notes.md"):
        p = sd / "shared" / note
        if p.exists() and (now - p.stat().st_mtime) < _FRESH_WINDOW_S:
            notes_fresh = True
            break
    if rows:
        warn = sum(1 for r in rows if str(r.get("outcome", "")).upper() == "WARN")
        loop.latest = f"{len(rows)} conductor_wake rows ({warn} WARN)"
    else:
        loop.latest = "no conductor_wake rows today"
    if acted and notes_fresh:
        loop.verdict = "LIVE"
        loop.reason = "fresh acted conductor_wake + fresh conductor notes"
    else:
        loop.verdict = "NOT-LIVE"
        loop.reason = (
            "conductor wakes are pre-action telos-gate WARN proposals only "
            "(no provider-backed act/adapt receipt); conductor work still blocked "
            "on an available LLM (gated behind Loop 1)")
    return loop


def _loop1_gated(loop: int, name: str, detail: str) -> LoopClosure:
    """Loops whose act/adapt arm cannot close until Loop 1's provider chain
    closes. They run sense/record on real or fixture data, but the closing arm
    is provider-gated. Honest verdict: NOT-LIVE (closing arm absent) with the
    Loop-1 dependency named. No receipt surface here proves a closed cycle."""
    return LoopClosure(
        loop=loop, name=name, verdict="NOT-LIVE",
        latest="closing arm provider-gated", reason=detail)


def build_loop3_closure(state_dir: Path | None = None) -> LoopClosure:
    """Loop 3 (Evolution / DarwinEngine). Closing arm = real FitnessScore from
    completed tasks archived to evolution/archive.jsonl. Real fitness
    computation is blocked on Loop 1 producing completed tasks."""
    return _loop1_gated(
        3, "Evolution Loop",
        "evolution machinery records meta-updates, but real FitnessScore "
        "computation (ADAPT arm) is blocked on Loop 1 producing completed tasks")


def build_loop4_closure(state_dir: Path | None = None) -> LoopClosure:
    """Loop 4 (Consolidation / Memory). Closing arm = consolidating real
    agent-produced outputs. Only heartbeat data exists to consolidate; no
    agent outputs until Loop 1 closes."""
    return _loop1_gated(
        4, "Consolidation Loop",
        "consolidation pipeline + dedup work on heartbeat data, but there are "
        "no agent-produced outputs to consolidate until Loop 1 closes")


def build_loop7_closure(state_dir: Path | None = None) -> LoopClosure:
    """Loop 7 (Training Flywheel). Closing arm = scoring real agent
    trajectories and reinforcing strategies. Traces are test fixtures until
    Loop 1 produces real trajectories."""
    return _loop1_gated(
        7, "Training Flywheel",
        "quality-gate evaluations run, but trajectory scoring/reinforcement "
        "(ADAPT arm) has no real agent trajectories until Loop 1 closes")


def build_loop8_closure(state_dir: Path | None = None) -> LoopClosure:
    """Loop 8 (Recognition / Strange Loop). Closing arm = cascade eigenform
    convergence feeding the recognition seed from real loop history. Periodic
    trigger depends on LoopEngine schedule activation, itself gated by Loop 1."""
    return _loop1_gated(
        8, "Recognition Loop",
        "recognition-seed computation is wired, but eigenform convergence over "
        "real loop history (ADAPT arm) awaits LoopEngine activation gated by Loop 1")


def build_loop10_closure(state_dir: Path | None = None) -> LoopClosure:
    """Loop 10 (Context Agent). Depends entirely on Loop 1 (a running
    AgentRunner with a real provider). No closing receipt until then."""
    return _loop1_gated(
        10, "Context Agent",
        "depends on a running AgentRunner with a real provider; no closing "
        "receipt exists until Loop 1 closes")


def build_loop11_closure(state_dir: Path | None = None) -> LoopClosure:
    """Loop 11 (Replication Monitor). Replication path is structurally correct
    but no trigger events have fired; closing arm gated behind Loop 1."""
    return _loop1_gated(
        11, "Replication Monitor",
        "replication path structurally correct (MM-02/03 resolved) but no "
        "trigger events yet; closing arm gated behind Loop 1")


# Builder registry in render order (fed cascade: 6,2,5,9 then 3,4,7,8,10,11).
_LOOP_BUILDERS = [
    build_loop6_closure,
    build_loop2_closure,
    build_loop5_closure,
    build_loop9_closure,
    build_loop3_closure,
    build_loop4_closure,
    build_loop7_closure,
    build_loop8_closure,
    build_loop10_closure,
    build_loop11_closure,
]


def build_loop_closures(state_dir: Path | None = None) -> list[LoopClosure]:
    return [b(state_dir) for b in _LOOP_BUILDERS]


def build_packet() -> OrientationPacket:
    return OrientationPacket(
        identity=build_identity(),
        organs=build_organs(),
        tracks=build_tracks(),
        custody=build_custody(),
        liveness=build_liveness(),
        broken=build_broken(),
        loop1=build_loop1_closure(),
        loops=build_loop_closures(),
    )


def _section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def render(packet: OrientationPacket) -> None:
    _section("ORIENTATION — the whole organism at once (projection, not authority)")
    print(f"  {packet.identity.one_line}")
    print("  Read-first:")
    for path in packet.identity.read_first:
        marker = "MISSING " if path in packet.identity.missing_sources else ""
        print(f"    - {marker}{path}")

    _section(f"ORGANS ({len(packet.organs)}) — owner: docs/governance/VENTURE_CELL_PORTFOLIO.yaml")
    for organ in packet.organs:
        name = f" ({organ.external_name})" if organ.external_name else ""
        print(f"  [{organ.status:<18}] {organ.id}{name} — {organ.instrument}")

    _section(f"ACTIVE TRACKS ({len(packet.tracks)}) — owner: docs/governance/ACTIVE_TRACK.yaml")
    for track in packet.tracks:
        print(f"  [{track.status}] {track.id} serves={track.serves} owner={track.owner}")
        for surface in track.owned_surfaces:
            print(f"      owns {surface}")

    _section("CANON CUSTODY — owner: docs/docops/assertions.yaml canonical_guard.registered")
    print(f"  Registered canon docs: {packet.custody.registered_total} "
          f"(present in this checkout: {packet.custody.present})")
    for path in packet.custody.missing:
        print(f"  MISSING: {path}")

    _section("LIVENESS — owner: live ops census receipt (read-only)")
    print(f"  Receipt: {packet.liveness.receipt}")
    if packet.liveness.generated_at:
        print(f"  Generated: {packet.liveness.generated_at}")
    for surface in packet.liveness.surfaces:
        print(f"  [{surface['status']:<8}] {surface['id']} — {surface['label']}")

    _section("LOOP CLOSURE — owners: delegation_runs + ~/.dharma receipt surfaces (read-only)")
    c = packet.loop1
    print(f"  Loop 1 (provider chain + dispatch): {'LIVE' if c.live else 'NOT-LIVE'}")
    if c.provider or c.model:
        print(f"    latest receipt: provider={c.provider!r} model={c.model!r}")
    if c.detail:
        print(f"    {c.detail}")
    for lp in packet.loops:
        print(f"  Loop {lp.loop} ({lp.name}): {lp.verdict}")
        if lp.latest:
            print(f"    latest: {lp.latest}")
        if lp.reason:
            print(f"    {lp.reason}")

    _section(f"BROKEN REGISTER — open-like items ({len(packet.broken)})")
    for item in packet.broken:
        print(f"  [{item.status}] {item.id} — {item.title}")

    print()
    print("  Depth: make onboard (state) · docs/MEGAFILE_INDEX.md (maps)")
    print("  This view writes nothing and owns nothing.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render the whole organism at once from its owners.")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="print the machine packet JSON to stdout")
    args = parser.parse_args(argv)
    packet = build_packet()
    if args.as_json:
        print(json.dumps(asdict(packet), sort_keys=True, indent=1))
    else:
        render(packet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
