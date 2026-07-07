#!/usr/bin/env python3
"""inward_ascent_baseline.py — re-runnable 10x baseline scoreboard.

Fact-owner: docs/plans/INWARD_ASCENT_PHASE0_DOSSIER_2026-07-07.md §(c). This
script owns NO fact. It projects each ratchet surface the operator named
(ingest volume/quality, ontology coverage, memory hit-rate, gate catch-rate,
routing regret vs history, self-model accuracy, forecast Brier) plus the
git-history gym substrate onto evidence that already exists on THIS host, and
emits an honest, digest-stamped, re-runnable receipt so that "10x" is a
number rather than a feeling.

Doctrine (same as trust_gate_status.py / agent_onboard.py):
  Read models project truth from owners; they do not become authority.
  A surface that cannot be measured on this host scores measured=False with
  the gap named — an unmeasured surface is UNKNOWN, never silently green.

Outputs:
  - human table to stdout
  - reports/governance/inward_ascent/baseline_receipt.json  (digest-stamped)

The digest excludes only volatile fields (generated_at, digest, host). Re-run
on the same host state reproduces the same digest, which is what makes the
"10x" claim a replayable measurement rather than a screenshot.

Exit code: always 0. This is a scoreboard, not a CI gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sqlite3
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RECEIPT_DIR = REPO_ROOT / "reports/governance/inward_ascent"
RECEIPT_PATH = RECEIPT_DIR / "baseline_receipt.json"
SCHEMA = "dharma_swarm.inward_ascent_baseline.v1"

# Fields excluded from the cross-run REPLAY identity (content_digest): they are
# volatile (time/host) or are themselves digests. The top-level `digest` is a
# separate, checker-compatible tamper seal that DOES cover these (it mirrors
# scripts/governance/check_track_status.py::_recompute_digest, so a
# receipt_valid criterion with expect_digest passes).
_VOLATILE_KEYS = ("generated_at", "host", "digest", "content_digest")

# lower_is_better surfaces ratchet DOWN toward baseline/10; the rest ratchet UP.
LOWER_IS_BETTER = {"routing_regret", "forecast_brier"}


@dataclass
class Surface:
    """One ratchet surface measured (or honestly not) on this host."""

    id: str
    label: str
    value: float | int | None
    unit: str
    measured: bool
    owner: str
    note: str = ""
    detail: dict[str, object] = field(default_factory=dict)

    def ten_x_target(self) -> float | None:
        if not self.measured or self.value is None:
            return None
        v = float(self.value)
        if self.id in LOWER_IS_BETTER:
            return round(v / 10.0, 6)
        # A zero baseline has no multiplicative 10x; the target is "light it".
        return round(v * 10.0, 6) if v > 0 else 0.0


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def stable_digest(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _state_dir() -> Path:
    # State-dir ownership stays with daemon_config (canonical owner); this
    # read-only projection never derives its own ~/.dharma path.
    from dharma_swarm.daemon_config import dharma_state_dir

    return dharma_state_dir()


# --------------------------------------------------------------------------
# Surface probes. Each returns a Surface; none raises.
# --------------------------------------------------------------------------
def probe_ingest_volume(state: Path) -> Surface:
    """Count Bronze raw receipts already landed (afferent supply-chain)."""
    receipt_dir = state / "meta" / "intelligence_supply_chain" / "bronze" / "raw_receipts"
    n = len(list(receipt_dir.glob("*.json"))) if receipt_dir.is_dir() else 0
    return Surface(
        id="ingest_volume",
        label="Bronze raw receipts landed",
        value=n,
        unit="receipts",
        measured=True,
        owner=str(receipt_dir.relative_to(state.parent)) if state in receipt_dir.parents else str(receipt_dir),
        note="live-capable: HN Algolia fetch verified this host; 0 = organs dark, not broken",
    )


def probe_ingest_quality(state: Path) -> Surface:
    """Fraction of landed receipts that reached required corroboration k."""
    receipt_dir = state / "meta" / "intelligence_supply_chain" / "bronze" / "raw_receipts"
    if not receipt_dir.is_dir():
        return Surface(
            id="ingest_quality", label="Corroborated ingest fraction", value=None,
            unit="fraction", measured=False, owner=str(receipt_dir),
            note="no bronze receipts on this host — cannot measure corroboration yet",
        )
    total = 0
    corroborated = 0
    for p in receipt_dir.glob("*.json"):
        try:
            row = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        total += 1
        corr = row.get("corroboration", {}) if isinstance(row, dict) else {}
        req = corr.get("required_k", 2)
        obs = corr.get("observed_k", 0)
        if isinstance(req, int) and isinstance(obs, int) and obs >= req:
            corroborated += 1
    if total == 0:
        return Surface(
            id="ingest_quality", label="Corroborated ingest fraction", value=None,
            unit="fraction", measured=False, owner=str(receipt_dir),
            note="0 receipts — corroboration undefined",
        )
    return Surface(
        id="ingest_quality", label="Corroborated ingest fraction",
        value=round(corroborated / total, 4), unit="fraction", measured=True,
        owner=str(receipt_dir), detail={"total": total, "corroborated": corroborated},
    )


def probe_ontology_coverage(state: Path) -> Surface:
    """Entity count in the ontology store (Palantir-style semantic layer)."""
    db = state / "ontology.db"
    if not db.is_file():
        return Surface(
            id="ontology_coverage", label="Ontology entities", value=None,
            unit="entities", measured=False, owner=str(db),
            note="ontology.db ABSENT on this host (BR-007) — coverage UNKNOWN, "
                 "measurable only on the daemon host that owns the store",
        )
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            target = next((t for t in ("entities", "nodes", "ontology_entities") if t in tables), None)
            n = conn.execute(f"SELECT COUNT(*) FROM {target}").fetchone()[0] if target else 0
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return Surface(
            id="ontology_coverage", label="Ontology entities", value=None,
            unit="entities", measured=False, owner=str(db),
            note=f"ontology.db unreadable: {exc}",
        )
    return Surface(
        id="ontology_coverage", label="Ontology entities", value=n,
        unit="entities", measured=True, owner=str(db),
    )


def probe_routing_regret(state: Path) -> Surface:
    """Off-policy routing regret needs the real delegation_runs history."""
    db = state / "state" / "runtime.db"
    if not db.is_file():
        return Surface(
            id="routing_regret", label="Routing regret vs history", value=None,
            unit="regret", measured=False, owner=str(db),
            note="runtime.db ABSENT on this host (BR-007) — the ~2k historical "
                 "delegation_runs live only on the daemon host; regret UNKNOWN here",
        )
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            rows = conn.execute("SELECT COUNT(*) FROM delegation_runs").fetchone()[0] if "delegation_runs" in tables else 0
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return Surface(
            id="routing_regret", label="Routing regret vs history", value=None,
            unit="regret", measured=False, owner=str(db),
            note=f"runtime.db unreadable: {exc}",
        )
    # Regret itself requires the replay evaluator (Phase 1 build). Baseline here
    # reports only that the substrate exists; regret stays UNMEASURED until the
    # evaluator lands.
    return Surface(
        id="routing_regret", label="Routing regret vs history", value=None,
        unit="regret", measured=False, owner=str(db),
        note=f"delegation_runs rows={rows} present but replay evaluator not built "
             "(Phase 1) — regret UNMEASURED", detail={"delegation_runs": rows},
    )


def probe_forecast_brier(state: Path) -> Surface:
    """Forecast calibration over resolved predictions (ginko_brier owner)."""
    try:
        from dharma_swarm.ginko_brier import compute_brier_score
    except Exception as exc:  # noqa: BLE001 - heavy optional import.
        return Surface(
            id="forecast_brier", label="Forecast Brier score", value=None,
            unit="brier", measured=False, owner="dharma_swarm/ginko_brier.py",
            note=f"ginko_brier import failed: {type(exc).__name__}",
        )
    try:
        score = compute_brier_score()
    except Exception as exc:  # noqa: BLE001
        return Surface(
            id="forecast_brier", label="Forecast Brier score", value=None,
            unit="brier", measured=False, owner="dharma_swarm/ginko_brier.py",
            note=f"compute_brier_score raised {type(exc).__name__}",
        )
    if score is None:
        return Surface(
            id="forecast_brier", label="Forecast Brier score", value=None,
            unit="brier", measured=False, owner="dharma_swarm/ginko_brier.py",
            note="no RESOLVED predictions on this host — Brier undefined; the "
                 "forecasting gym exists to create resolvable predictions",
        )
    return Surface(
        id="forecast_brier", label="Forecast Brier score", value=round(score, 4),
        unit="brier", measured=True, owner="dharma_swarm/ginko_brier.py",
    )


def probe_gate_inventory() -> Surface:
    """Gate catch-rate needs a held-out attack corpus (Phase 1). Baseline =
    inert-gate inventory so the red-team gym has a starting number."""
    try:
        from dharma_swarm import telos_gates
    except Exception as exc:  # noqa: BLE001
        return Surface(
            id="gate_catch_rate", label="Gate catch-rate (held-out attacks)",
            value=None, unit="fraction", measured=False,
            owner="dharma_swarm/telos_gates.py",
            note=f"telos_gates import failed: {type(exc).__name__}",
        )
    src = Path(telos_gates.__file__).read_text(encoding="utf-8")
    inert = src.count("always passes") + src.count("always-pass")
    return Surface(
        id="gate_catch_rate", label="Gate catch-rate (held-out attacks)",
        value=None, unit="fraction", measured=False,
        owner="dharma_swarm/telos_gates.py",
        note="no held-out attack corpus yet — catch-rate UNMEASURED; the "
             "gate red-team gym calibrates inert gates (e.g. BHED_GNAN)",
        detail={"inert_gate_markers": inert},
    )


def probe_memory_hit_rate(state: Path) -> Surface:
    """Memory-kernel first-token hit-rate needs a retrieval-QA harness (Phase 1)."""
    kernel_db = next((state.glob("**/memory*.db")), None)
    return Surface(
        id="memory_hit_rate", label="Memory-kernel hit-rate", value=None,
        unit="fraction", measured=False,
        owner="dharma_swarm/memory_kernel/",
        note="no retrieval-QA harness yet — hit-rate UNMEASURED; the retrieval/"
             "memory gym creates verifiable QA over ingested corpora"
             + (f"; kernel store found at {kernel_db}" if kernel_db else "; no kernel store on this host"),
    )


def probe_self_model_accuracy() -> Surface:
    """Predict-which-tests-a-diff-breaks accuracy needs the self-model gym harness."""
    return Surface(
        id="self_model_accuracy", label="Self-model test-break accuracy",
        value=None, unit="fraction", measured=False,
        owner="(self-model gym — Phase 1)",
        note="no self-model harness yet — UNMEASURED; the self-model gym scores "
             "predictions of which tests a diff breaks by running them",
    )


def _git_count(args: list[str]) -> int | None:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), *args],
            text=True, stderr=subprocess.DEVNULL, timeout=60)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    return len([ln for ln in out.splitlines() if ln.strip()])


def _git_head_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.DEVNULL, timeout=30).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None


def probe_git_history_gym(pin_sha: str | None = None) -> Surface:
    """Real substrate for the git-history repo gym: this repo's own past.

    The substrate is a FROZEN snapshot: counts are taken at a pinned commit
    sha (recorded in the receipt), so committing the receipt itself never
    shifts the measurement and ``--check`` replays against the same snapshot.
    """
    shallow = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--is-shallow-repository"],
        capture_output=True, text=True, timeout=30).stdout.strip()
    snapshot_sha = pin_sha or _git_head_sha()
    log_ref = [snapshot_sha] if snapshot_sha else []
    commits = _git_count(["log", "--oneline", *log_ref]) if snapshot_sha else None
    merges = _git_count(["log", "--oneline", "--merges", *log_ref]) if snapshot_sha else None
    return Surface(
        id="git_history_gym", label="git-history gym substrate (commits/merges)",
        value=commits, unit="commits", measured=commits is not None,
        owner=f"git log {snapshot_sha or '(unresolved HEAD)'} (frozen snapshot)",
        note=f"non-shallow={shallow == 'false'}; landed merges = real solved tasks",
        detail={"commits": commits, "merges": merges, "shallow": shallow,
                "snapshot_sha": snapshot_sha},
    )


def collect(state: Path, git_pin_sha: str | None = None) -> list[Surface]:
    return [
        probe_ingest_volume(state),
        probe_ingest_quality(state),
        probe_ontology_coverage(state),
        probe_memory_hit_rate(state),
        probe_gate_inventory(),
        probe_routing_regret(state),
        probe_self_model_accuracy(),
        probe_forecast_brier(state),
        probe_git_history_gym(git_pin_sha),
    ]


def build_receipt(surfaces: list[Surface], state: Path) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": SCHEMA,
        "doctrine": "read model projects truth from owners; unmeasured = UNKNOWN, never green",
        "state_dir": str(state),
        "surfaces": [
            {
                **{k: v for k, v in asdict(s).items() if k != "detail" or s.detail},
                "ten_x_target": s.ten_x_target(),
                "ratchet_direction": "down" if s.id in LOWER_IS_BETTER else "up",
            }
            for s in surfaces
        ],
        "summary": {
            "surfaces_total": len(surfaces),
            "surfaces_measured": sum(1 for s in surfaces if s.measured),
            "surfaces_unknown": sum(1 for s in surfaces if not s.measured),
        },
    }
    # content_digest = cross-run replay identity (excludes volatile fields).
    body["content_digest"] = stable_digest(
        {k: v for k, v in body.items() if k not in _VOLATILE_KEYS})
    body["generated_at"] = _utc_now()
    body["host"] = socket.gethostname()
    # digest = checker-compatible tamper seal over EVERYTHING except `digest`.
    body["digest"] = stable_digest({k: v for k, v in body.items() if k != "digest"})
    return body


def _committed_git_pin(committed: dict[str, object]) -> str | None:
    """Pull the frozen git snapshot sha out of a committed receipt."""
    surfaces = committed.get("surfaces")
    if not isinstance(surfaces, list):
        return None
    for s in surfaces:
        if isinstance(s, dict) and s.get("id") == "git_history_gym":
            detail = s.get("detail")
            if isinstance(detail, dict):
                sha = detail.get("snapshot_sha")
                return str(sha) if sha else None
    return None


def _print_table(receipt: dict[str, object]) -> None:
    print("=" * 78)
    print("INWARD ASCENT — 10x BASELINE SCOREBOARD (owner: dossier §(c))")
    print("=" * 78)
    surfaces = receipt["surfaces"]
    assert isinstance(surfaces, list)
    for s in surfaces:
        assert isinstance(s, dict)
        val = s["value"]
        shown = "UNKNOWN" if not s["measured"] else f"{val} {s['unit']}"
        tgt = s["ten_x_target"]
        arrow = "↓" if s["ratchet_direction"] == "down" else "↑"
        tgt_str = "" if tgt is None else f"  10x{arrow}-> {tgt}"
        print(f"  [{'measured' if s['measured'] else ' UNKNOWN'}] {s['id']:<22} {shown}{tgt_str}")
        if s.get("note"):
            print(f"      · {s['note']}")
    summ = receipt["summary"]
    assert isinstance(summ, dict)
    print("-" * 78)
    print(f"  measured={summ['surfaces_measured']}  unknown={summ['surfaces_unknown']}  "
          f"total={summ['surfaces_total']}")
    print(f"  content_digest={receipt['content_digest']}")
    print(f"  digest(seal)={receipt['digest']}")
    print("=" * 78)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit receipt JSON to stdout")
    parser.add_argument("--no-write", action="store_true", help="do not write the receipt file")
    parser.add_argument(
        "--check", action="store_true",
        help="re-measure and fail (exit 3) if the committed receipt digest does not replay")
    args = parser.parse_args(argv)

    state = _state_dir()

    if args.check:
        if not RECEIPT_PATH.is_file():
            print(f"--check: no committed receipt at {RECEIPT_PATH}")
            return 3
        committed = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        pin_sha = _committed_git_pin(committed)
        surfaces = collect(state, git_pin_sha=pin_sha)
        receipt = build_receipt(surfaces, state)
        stored_seal = str(committed.get("digest", ""))
        reseal = stable_digest({k: v for k, v in committed.items() if k != "digest"})
        if stored_seal != reseal:
            print(f"--check: TAMPER — stored digest {stored_seal[:16]} != reseal {reseal[:16]}")
            return 3
        stored_content = str(committed.get("content_digest", ""))
        recomputed = str(receipt["content_digest"])
        if stored_content != recomputed:
            print(f"--check: CONTENT MISMATCH stored={stored_content[:16]} recomputed={recomputed[:16]}")
            print("  (host state changed since commit — expected off the daemon host)")
            return 3
        print(f"--check: seal intact and content replays ({stored_content[:16]}…)")
        return 0

    surfaces = collect(state)
    receipt = build_receipt(surfaces, state)

    if not args.no_write:
        RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
        RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        _print_table(receipt)
        if not args.no_write:
            print(f"  receipt -> {RECEIPT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
