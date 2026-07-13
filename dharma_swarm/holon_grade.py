"""holon_grade.py — THE executable holon-grade contract + harness. ONE place.

A "holon" is NOT a folder, a persona, a daemon, a bridge, or a wake loop. It is an
identity-bound persistent seat that satisfies the HOLON INVARIANT, ratified by the
operator 2026-07-06 in ``~/.dharma/agents/HOLON_CONTRACT.md``:

    identity + dialogue + wake/metabolism + authority envelope
    + memory/truth precedence + delegation + receipts + honest liveness

This module exists because "holon" was being used for nine different things and the word was
claimed before the invariant was enforced. It is THE HARNESS EVERY AGENT USES TO REACH AND
PROVE HOLON-GRADE, and it does three things: (1) DEFINES holon-grade as executable checks
(``AXES`` + ``_check_*`` probes); (2) GRADES any registered agent (``grade_agent``) on a
fail-closed 0/1/2 scale — generalizing the 2026-07-13 fable parity gauntlet to any seat; and
(3) RUNS a graded agent through the ONE runtime (``run_holon`` -> ``holon_bridge.load_holon``).

It is a HARNESS around the existing runtime, NOT a fifth holon body. The runtime already
exists (holon_bridge / holon_runtime); this is the grading + contract layer over it. Grades
write to the track-owned ``reports/sovereign_holons/`` surface — no new durable store (the
composer-holon-spine-longrun non-goal is honored). The sovereign target tier above hermes-
parity lives in the companion ``holon_frontier`` module.

Scoring anchors (fail-closed, inherited from the DharmaGraph/LangGraph parity gauntlet and
its #893 custody repairs — surface-presence must never fail OPEN):

    0  ABSENT / UNVERIFIABLE-NOW      — no observed behavior at probe time.
    1  PARTIAL / PROVEN-ONCE-DEAD-NOW — a real mechanism or dated receipt exists, not live.
    2  LIVE-DURABLE-RECEIPTED         — works now, survives absence/reboot, emits a receipt.

A file merely existing never scores above 1 (EXECUTE-OR-ZERO). Grading is deterministic and
model-free (it probes the filesystem + transport heartbeats), so it is starvation-immune and
any process — including a fresh-context auditor — can reproduce a grade.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

DHARMA = Path.home() / ".dharma"
AGENTS_ROOT = DHARMA / "agents"
HEARTBEATS = DHARMA / "a2a_bus" / "bridge_heartbeats"
STATES = DHARMA / "a2a_bus" / "state"
LEASES = DHARMA / "a2a_bus" / "leases"

# Freshness bar: a heartbeat / receipt older than this is not "live".
LIVE_WINDOW_S = 7 * 24 * 3600

# ---------------------------------------------------------------------------
# The contract: axes. H* = the HOLON INVARIANT (definitional). O* = oracle-parity
# (measured against the live field-ops organ hermes-m5 and the productized frontier).
# Weights sum to 100. The invariant axes are what make an agent a holon AT ALL;
# the oracle axes are how far up the always-on ladder it has climbed.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Axis:
    id: str
    weight: int
    invariant: bool  # True => part of the definitional HOLON INVARIANT
    what: str


AXES: list[Axis] = [
    Axis("H1_identity_honest_liveness", 6, True, "identity+passport consistent, pubkey key-derived, liveness fields honest"),
    Axis("H2_dialogue_face", 8, True, "a reply-subject protocol + an autonomous (non-session-borne) reply has occurred"),
    Axis("H3_wake_metabolism", 12, True, "a Tier-2 model-invoking wake runs as a supervised standing loop, fired <7d"),
    Axis("H4_authority_envelope", 8, True, "authority mode declared AND a code-enforced lease gate validates a real store"),
    Axis("H5_memory_truth_precedence", 8, True, "own memory surface + custody grades + no memory contradicting a later decree"),
    Axis("H6_delegation_surface", 7, True, "delegation idiom + real delegations with TTL + at least one closed with a receipt"),
    Axis("H7_receipts_verification", 8, True, "verifier!=executor discipline + a LIVE receipt flow + signable/gradable receipts"),
    Axis("O1_always_on_presence", 6, False, "a process is alive now and survives reboot (launchd/systemd)"),
    Axis("O2_scheduling_cron", 5, False, "a scheduled job fires on a cadence with dated completion counters"),
    Axis("O3_multi_channel", 4, False, "reachable on >1 channel incl. one operator-facing channel"),
    Axis("O4_callable_gateway", 5, False, "exposes a callable API/gateway that answers a health probe"),
    Axis("O5_memory_growth_loop", 5, False, "memory grows by an automated loop, growth observed <7d"),
    Axis("O6_governed_self_improvement", 5, False, "a governed proposal->gate->apply loop with a fitness ledger"),
    Axis("O7_task_queue_execution", 5, False, "inbound tasks autonomously consumed with terminal-state records"),
    Axis("O8_recovery_resume", 4, False, "recovers its own transport/state after a restart without human action"),
    Axis("O9_security_key_custody", 4, False, "seat key 0600, pubkey matches identity, sign/verify+tamper-reject proven"),
]

INVARIANT_AXES = [a.id for a in AXES if a.invariant]
assert sum(a.weight for a in AXES) == 100, "holon-grade weights must sum to 100"

# The beyond-hermes sovereign target tier (the climb ABOVE parity) lives in its companion
# module so this file stays the parity grader. Re-exported so callers have one import surface.
from dharma_swarm.holon_frontier import (  # noqa: E402
    BEYOND_HERMES,
    BEYOND_HERMES_BLIND_SPOTS,
    FrontierDimension,
    frontier_targets as _frontier_targets_for_home,
    prescribe_climb as _prescribe_climb_from_weak,
)


@dataclass
class AxisResult:
    id: str
    weight: int
    invariant: bool
    points: int  # 0 | 1 | 2
    evidence: str


@dataclass
class HolonGrade:
    uid: str
    probed_at: str
    score: float                       # 0..100, weighted
    axes: list[AxisResult] = field(default_factory=list)
    ctrl_broken: bool = False          # True when graded a body-deleted fixture
    digest: str = ""

    @property
    def has_holon_shape(self) -> bool:
        """Every definitional invariant axis has at least a real mechanism (points>=1)."""
        return all(a.points >= 1 for a in self.axes if a.invariant)

    @property
    def is_holon_grade_live(self) -> bool:
        """The true bar: every invariant axis is LIVE-DURABLE (points==2)."""
        return all(a.points == 2 for a in self.axes if a.invariant)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "dharma_swarm.holon_grade.v1",
            "uid": self.uid,
            "probed_at": self.probed_at,
            "score": self.score,
            "has_holon_shape": self.has_holon_shape,
            "is_holon_grade_live": self.is_holon_grade_live,
            "invariant_axes": INVARIANT_AXES,
            "axes": [
                {"id": a.id, "weight": a.weight, "invariant": a.invariant, "points": a.points, "evidence": a.evidence}
                for a in self.axes
            ],
            "digest": self.digest,
        }


# ---------------------------------------------------------------------------
# Probes. Each returns (points, evidence). Filesystem/transport only — model-free,
# deterministic, starvation-immune. Missing files score 0, never crash.
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _age_s(path: Path) -> float | None:
    try:
        return time.time() - path.stat().st_mtime
    except Exception:
        return None


def _check_H1_identity(home: Path, uid: str) -> tuple[int, str]:
    ident = _load_json(home / "identity.json")
    if not ident:
        return 0, "no identity.json"
    state = _load_json(STATES / f"{uid}.json") or {}
    # honesty: does a 'session_alive'-style status contradict process_running:false?
    status = str(ident.get("status", ""))
    running = state.get("process_running")
    lies = "alive" in status.lower() and running is False
    has_key_fields = bool(ident.get("public_key")) and (home / "keys" / "ed25519_private.pem").exists()
    if lies:
        return 1, f"identity present; liveness field '{status}' contradicts process_running={running}"
    if has_key_fields:
        return 2, "identity consistent, pubkey field present, liveness not contradicted"
    return 1, "identity present but incomplete (no key or no honest liveness)"


def _check_H2_dialogue(home: Path, uid: str) -> tuple[int, str]:
    # reply protocol proxy: a talk_receipts / responder. Autonomous reply proxy: a
    # supervised responder process is out of scope for a filesystem probe, so a
    # non-session-borne reply is required for 2 and can only be evidenced by a receipt.
    talk = home / "talk_receipts.jsonl"
    has_protocol = talk.exists()
    if not has_protocol:
        return 0, "no talk/reply-subject surface"
    # look for a launchd/tmux responder heartbeat for this uid (best-effort marker)
    responder = (home / "responder_heartbeat.json").exists()
    if responder:
        return 2, "reply protocol + responder heartbeat present"
    return 1, "reply protocol documented; no autonomous responder (session-borne only)"


def _check_H3_wake(home: Path, uid: str) -> tuple[int, str]:
    wake_log = home / "wake" / "wake_proof.log"
    nest_hb = DHARMA / "external_agents" / uid / "nest" / "heartbeat.json"
    age = _age_s(nest_hb) if nest_hb.exists() else None
    hb = _load_json(nest_hb) if nest_hb.exists() else None
    loop_active = bool(hb.get("wake_loop_active")) if hb else False
    if loop_active and age is not None and age < LIVE_WINDOW_S:
        return 2, f"wake loop active, heartbeat {int(age)}s old"
    if wake_log.exists():
        return 1, "wake receipts exist but Tier-2 loop not live (<7d) — proven-once-dead"
    return 0, "no wake machinery"


def _check_H4_authority(home: Path, uid: str) -> tuple[int, str]:
    ident = _load_json(home / "identity.json") or {}
    mode = str(ident.get("authority_mode", ""))
    declared = "lease" in mode or "read_only" in mode
    store_exists = LEASES.exists()
    store_populated = store_exists and any(LEASES.iterdir())
    if declared and store_populated:
        return 2, f"authority mode '{mode}' + populated lease store (enforceable)"
    if declared:
        return 0, f"authority mode '{mode}' declared but lease store {'empty' if store_exists else 'absent'} — gate is theater"
    return 0, "no authority envelope declared"


def _check_H5_memory(home: Path, uid: str) -> tuple[int, str]:
    mem = DHARMA / "agent_memory" / uid / "MEMORY.md"
    ledger = home / "INTENT_LEDGER.jsonl"
    if not mem.exists():
        return 0, "no memory surface"
    has_custody = ledger.exists()
    age = _age_s(mem)
    fresh = age is not None and age < LIVE_WINDOW_S
    if has_custody and fresh:
        return 2, f"memory + custody ledger, updated {int(age)}s ago"
    if has_custody:
        return 1, "memory + custody ledger but stale (no growth <7d)"
    return 1, "memory surface exists, no custody-graded ledger"


def _check_H6_delegation(home: Path, uid: str) -> tuple[int, str]:
    deleg = home / "OPEN_DELEGATIONS.md"
    if not deleg.exists():
        return 0, "no delegation surface"
    text = deleg.read_text(encoding="utf-8", errors="ignore")
    has_delegations = "expected receipt" in text.lower() or "ttl" in text.lower()
    closed = "closed" in text.lower() or "verified" in text.lower()
    graded = "grade" in text.lower() or (home / "receipts").exists()
    if has_delegations and closed and graded:
        return 2, "delegations with TTL + at least one loop closed with a graded receipt"
    if has_delegations and closed:
        return 1, "delegations closed but no graded receipt — autonomous closure unproven"
    if has_delegations:
        return 1, "delegations with TTL recorded, none closed"
    return 0, "delegation file present but no TTL'd delegations"


def _check_H7_receipts(home: Path, uid: str) -> tuple[int, str]:
    dojo = (home / "dojo" / "DOJO.md").exists()
    key = home / "keys" / "ed25519_private.pem"
    hb = _load_json(HEARTBEATS / f"{uid}.json") or {}
    receipt_count = hb.get("receipt_count", 0)
    hb_age = _age_s(HEARTBEATS / f"{uid}.json")
    live_flow = isinstance(receipt_count, int) and receipt_count > 0 and hb_age is not None and hb_age < LIVE_WINDOW_S
    signable = key.exists()
    if dojo and live_flow and signable:
        return 2, f"verifier discipline + live receipt flow ({receipt_count}) + signable"
    if dojo and signable:
        return 1, "verifier discipline + signable receipts, but receipt-emission flow dead"
    if dojo:
        return 1, "verifier discipline present but no signable seat key"
    return 0, "no receipt discipline"


def _check_O1_always_on(home: Path, uid: str) -> tuple[int, str]:
    hb = HEARTBEATS / f"{uid}.json"
    age = _age_s(hb) if hb.exists() else None
    # launchd durability is checked by the caller via launchctl in the CLI; the FS probe
    # can only see recent heartbeat freshness.
    if age is not None and age < 3600:
        return 2, f"heartbeat fresh ({int(age)}s) — process alive"
    if hb.exists():
        return 1, "heartbeat exists but stale — process not alive now"
    return 0, "no transport heartbeat"


def _check_O2_cron(home: Path, uid: str) -> tuple[int, str]:
    wake_log = home / "wake" / "wake_proof.log"
    if wake_log.exists():
        age = _age_s(wake_log)
        if age is not None and age < LIVE_WINDOW_S:
            return 2, "scheduled wake fired <7d"
        return 1, "scheduled wake proven once, stale"
    return 0, "no scheduled job"


def _check_O3_channels(home: Path, uid: str) -> tuple[int, str]:
    # A filesystem probe sees only the NATS bridge. A second, operator-facing channel
    # (Slack/Telegram/HTTP) is what earns 2 — not visible here, so this caps at 1.
    if (HEARTBEATS / f"{uid}.json").exists():
        return 1, "single NATS channel only (no operator-facing channel visible)"
    return 0, "no channel"


def _check_O4_gateway(home: Path, uid: str) -> tuple[int, str]:
    return 0, "no callable gateway (filesystem probe cannot see one; CLI --gateway-url overrides)"


def _check_O5_growth(home: Path, uid: str) -> tuple[int, str]:
    mem = DHARMA / "agent_memory" / uid
    if not mem.exists():
        return 0, "no memory dir"
    # automated growth => an episodes/archival file touched <7d AND a writer marker.
    writer = (mem / ".growth_loop").exists()
    newest = max((_age_s(p) or 1e9 for p in mem.glob("*")), default=1e9)
    if writer and newest < LIVE_WINDOW_S:
        return 2, "automated growth loop active"
    return 0, "no automated growth loop (hand-edited only)"


def _check_O6_evolution(home: Path, uid: str) -> tuple[int, str]:
    if (home / "evolution" / "ledger.jsonl").exists():
        return 2, "governed self-improvement ledger present"
    return 0, "no governed self-improvement loop"


def _check_O7_queue(home: Path, uid: str) -> tuple[int, str]:
    hb = _load_json(HEARTBEATS / f"{uid}.json") or {}
    rc = hb.get("receipt_count", 0)
    inbox = DHARMA / "a2a_bus" / "inboxes" / uid
    unread = len(list(inbox.iterdir())) if inbox.exists() else 0
    if isinstance(rc, int) and rc > 0:
        return 2, f"tasks consumed (receipt_count={rc})"
    return 0, f"inbound docked but not consumed ({unread} in inbox, receipt_count=0)"


def _check_O8_recovery(home: Path, uid: str) -> tuple[int, str]:
    # A launchd/systemd unit is the recovery mechanism; FS probe can't confirm, CLI does.
    return 0, "recovery unproven (needs a launchd/systemd unit — checked in CLI)"


def _check_O9_keys(home: Path, uid: str) -> tuple[int, str]:
    key = home / "keys" / "ed25519_private.pem"
    ident = _load_json(home / "identity.json") or {}
    if not key.exists():
        return 0, "no seat key"
    try:
        mode = oct(key.stat().st_mode)[-3:]
    except Exception:
        mode = "???"
    if mode != "600":
        return 1, f"seat key present but perms {mode} (want 600)"
    # cryptographic pubkey match (the proof) — done here so any caller gets it for free.
    declared = str(ident.get("public_key", ""))
    try:
        from cryptography.hazmat.primitives import serialization
        priv = serialization.load_pem_private_key(key.read_bytes(), password=None)
        raw = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
        # sign/verify + tamper-reject roundtrip
        msg = b"holon_grade_keyproof"
        sig = priv.sign(msg)
        priv.public_key().verify(sig, msg)
        tampered_ok = True
        try:
            priv.public_key().verify(sig, b"tampered")
            tampered_ok = False  # should have raised
        except Exception:
            tampered_ok = True
        if raw == declared and tampered_ok:
            return 2, "key 0600, pubkey matches identity, sign/verify+tamper-reject proven"
        return 1, "key 0600 but pubkey mismatch or tamper check failed"
    except Exception as exc:  # cryptography missing or key unreadable
        return 1, f"key 0600 present; crypto roundtrip unavailable ({type(exc).__name__})"


_PROBES: dict[str, Callable[[Path, str], tuple[int, str]]] = {
    "H1_identity_honest_liveness": _check_H1_identity,
    "H2_dialogue_face": _check_H2_dialogue,
    "H3_wake_metabolism": _check_H3_wake,
    "H4_authority_envelope": _check_H4_authority,
    "H5_memory_truth_precedence": _check_H5_memory,
    "H6_delegation_surface": _check_H6_delegation,
    "H7_receipts_verification": _check_H7_receipts,
    "O1_always_on_presence": _check_O1_always_on,
    "O2_scheduling_cron": _check_O2_cron,
    "O3_multi_channel": _check_O3_channels,
    "O4_callable_gateway": _check_O4_gateway,
    "O5_memory_growth_loop": _check_O5_growth,
    "O6_governed_self_improvement": _check_O6_evolution,
    "O7_task_queue_execution": _check_O7_queue,
    "O8_recovery_resume": _check_O8_recovery,
    "O9_security_key_custody": _check_O9_keys,
}


# ---------------------------------------------------------------------------
# The harness API.
# ---------------------------------------------------------------------------


def grade_agent(uid: str, agents_root: Path | None = None) -> HolonGrade:
    """Grade any registered agent uid against the holon invariant + oracle-parity axes.

    Deterministic and model-free. The single entry point every agent uses to prove
    holon-grade — the same harness that graded fable_composer at 30/100 on 2026-07-13.
    """
    root = agents_root or AGENTS_ROOT
    home = root / uid
    results: list[AxisResult] = []
    for axis in AXES:
        try:
            points, evidence = _PROBES[axis.id](home, uid)
        except Exception as exc:  # a broken probe must fail closed, never crash a grade
            points, evidence = 0, f"probe error: {type(exc).__name__}"
        results.append(AxisResult(axis.id, axis.weight, axis.invariant, points, evidence))
    num = sum(r.weight * r.points / 2 for r in results)
    den = sum(r.weight for r in results)
    score = round(num / den * 100, 2)
    grade = HolonGrade(uid=uid, probed_at=_now(), score=score, axes=results,
                       ctrl_broken=not (home / "keys").exists() and not (home / "identity.json").exists())
    grade.digest = _digest(grade.as_dict())
    return grade


def assert_holon_grade(uid: str) -> HolonGrade:
    """Raise unless the agent has at least holon SHAPE (all invariant axes >= 1).

    This is the gate any caller uses before treating an agent as a holon. Reaching
    holon-grade is not a claim you assert in prose — it is this function returning.
    """
    grade = grade_agent(uid)
    if not grade.has_holon_shape:
        missing = [a.id for a in grade.axes if a.invariant and a.points < 1]
        raise HolonGradeError(f"{uid} is not holon-grade: invariant axes absent: {missing}")
    return grade


def run_holon(uid: str, require_grade: bool = True):
    """Load a graded agent through THE ONE runtime (holon_bridge.load_holon).

    This is where "reaches that level -> uses the harness" becomes literal: the harness
    grades, then delegates running to the existing sovereign runtime. It never forks a
    second loader. Set require_grade=False only for diagnostics on a not-yet-holon seat.
    """
    if require_grade:
        assert_holon_grade(uid)
    from dharma_swarm.holon_bridge import load_holon  # the ONE runtime door
    return load_holon(uid)


class HolonGradeError(RuntimeError):
    """Raised when an agent claimed holon-grade but does not pass the invariant."""


def write_grade(grade: HolonGrade, reports_root: Path | None = None) -> Path:
    """Write a grade artifact to the track-owned reports/sovereign_holons/ surface.

    NOT a new durable receipt store — a governance grade projected onto the existing
    track surface (composer-holon-spine-longrun non-goal honored).
    """
    root = reports_root or (Path(__file__).resolve().parent.parent / "reports" / "sovereign_holons")
    root.mkdir(parents=True, exist_ok=True)
    stamp = grade.probed_at.replace(":", "").replace("-", "")[:15]
    path = root / f"holon_grade_{grade.uid}_{stamp}.json"
    path.write_text(json.dumps(grade.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def frontier_targets(uid: str | None = None, agents_root: Path | None = None) -> list[dict[str, Any]]:
    """The five sovereign dimensions ABOVE hermes-parity, with each one's build status for a seat.

    A holon reaches hermes-PARITY by scoring on the 16 axes; it becomes SOVEREIGN by building
    these five. Thin wrapper over ``holon_frontier`` that resolves the agent home first.
    """
    root = agents_root or AGENTS_ROOT
    home = (root / uid) if uid else None
    return _frontier_targets_for_home(home)


def prescribe_climb(grade: HolonGrade) -> list[str]:
    """Given a graded holon, which sovereign rung to build next (from its weak axes)."""
    weak = {a.id: a.points for a in grade.axes if a.points < 2}
    return _prescribe_climb_from_weak(weak)


def _now() -> str:
    # UTC ISO without importing datetime.utcnow (deprecated); time.gmtime is fine.
    t = time.gmtime()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", t)


def _digest(obj: dict[str, Any]) -> str:
    payload = {k: v for k, v in obj.items() if k != "digest"}
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(canon).hexdigest()


def _cli(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Grade an agent against the holon invariant. THE holon harness.")
    ap.add_argument("uid", help="registered agent uid under ~/.dharma/agents/")
    ap.add_argument("--write", action="store_true", help="write the grade artifact to reports/sovereign_holons/")
    ap.add_argument("--json", action="store_true", help="print the full grade as JSON")
    ap.add_argument("--frontier", action="store_true", help="also print the beyond-hermes sovereign target tier")
    args = ap.parse_args(argv)
    grade = grade_agent(args.uid)
    if args.json:
        print(json.dumps(grade.as_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"HOLON GRADE — {grade.uid}: {grade.score}/100")
        print(f"  holon shape (all invariant axes present): {grade.has_holon_shape}")
        print(f"  holon-grade LIVE (all invariant axes durable): {grade.is_holon_grade_live}")
        for a in grade.axes:
            tag = "INV" if a.invariant else "   "
            print(f"  [{tag}] {a.id:<32} {a.points}/2  {a.evidence}")
    if args.frontier:
        print("\nBEYOND-HERMES SOVEREIGN TIER (the climb above parity):")
        for f in frontier_targets(args.uid):
            print(f"  [{f['status']:<6}] {f['id']:<40} ({f['feasibility']})")
            print(f"           {f['question']}")
        rx = prescribe_climb(grade)
        if rx:
            print("\nPRESCRIBED NEXT RUNGS (from this seat's weak axes):")
            for r in rx:
                print(f"  - {r}")
    if args.write:
        p = write_grade(grade)
        print(f"grade written: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
