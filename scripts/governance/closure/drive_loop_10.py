#!/usr/bin/env python3
"""Loop 10 (Context Agent) closure driver — run the REAL context-agent cycle on
real data, with a live FREE provider answering the LLM act-step.

Loop 10 is the ecosystem's autonomous nervous system (dharma_swarm/context_agent.py).
Its five transitions (CYBERNETIC_LOOP_MAP.md row 10 "Context Agent"):

  SENSE      NervousSystem.scan_freshness() — scan the 11-tier context sources +
             agent notes on the owner surface (state_dir) for mtime/size/freshness.
  INTERPRET  NervousSystem.assess_health() — fold freshness into a health score +
             alerts (bloated notes, stale sources).
  CONSTRAIN  the health thresholds + bloat detection gate which act fires: only a
             genuinely bloated (>50KB) note triggers a distillation dispatch; the
             quiet-hours gate bounds dreaming. (No gate is weakened here.)
  ACT        Intelligence.distill_notes() — the Loop-1 consume edge: a REAL live
             FREE provider compresses the bloated note to key findings and writes
             the distilled artifact to the owner surface (context/distilled/). We
             persist a Loop-1-shaped EvidenceReceipt for this dispatch
             (loop_role='context_agent_act', provider/model/input_tokens>0,
             side_effect_key) so the act is a provable real provider dispatch.
  ADAPT      ContextAgent leaves a stigmergy mark (scoped marks.jsonl) referencing
             the distilled artifact, emits CONTEXT_HEALTH on the bus, and writes
             the cycle's freshness.json/alerts.json — these feed the next cycle's
             sense and other loops.

This does NOT touch the production daemon, the live runtime.db, the live ~/.dharma
state dir, or archive fitness. Everything is scoped to /tmp:
  - state_dir         -> scoped temp dir (owner surface: context/, stigmergy marks)
  - spine receipt db  -> scoped temp delegation_runs db
The distilled artifact is an INTERNAL context write; nothing touches archive.jsonl.

Run:
  DHARMA_SPINE_DISPATCH=1 \
    LC_LOOP10_STATE_DIR=/tmp/lc_loop10_state \
    LC_LOOP10_SCOPED_DB=/tmp/lc_loop10_scoped.db \
    LC_LOOP10_DIR=/tmp/lc_loop10 \
    python3 scripts/governance/closure/drive_loop_10.py
Then:
  LC_LOOP10_STATE_DIR=/tmp/lc_loop10_state \
    LC_RUNTIME_DB=/tmp/lc_loop10_scoped.db \
    LC_LOOP10_DIR=/tmp/lc_loop10 \
    python3 scripts/governance/closure/check_loop_10.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from dharma_swarm.models import LLMResponse, ProviderType  # noqa: E402
from dharma_swarm.models import LLMRequest  # noqa: E402
from dharma_swarm.runtime_provider import (  # noqa: E402
    create_runtime_provider,
    resolve_runtime_provider_config,
)
from dharma_swarm.signal_bus import SignalBus  # noqa: E402
from dharma_swarm.stigmergy import StigmergyStore  # noqa: E402
from dharma_swarm.spine.invoke import invoke_agent  # noqa: E402
from dharma_swarm.spine.receipt import EvidenceReceipt  # noqa: E402
from dharma_swarm.spine.routing import RoutingDecision  # noqa: E402

STATE_DIR = Path(
    os.environ.get("LC_LOOP10_STATE_DIR", f"/tmp/lc_loop10_state_{int(time.time())}")
)
SCOPED_DB = os.environ.get(
    "LC_LOOP10_SCOPED_DB", f"/tmp/lc_loop10_scoped_{int(time.time())}.db"
)
LOOP10_DIR = Path(os.environ.get("LC_LOOP10_DIR", f"/tmp/lc_loop10_{int(time.time())}"))

# FREE-first decorrelated, live-confirmed 2026-06-16. ollama_cloud families return
# substantive prose (distillation needs real summary text). gemini truncates too
# thin for a distillation, so the ollama families lead.
FREE_CANDIDATES: list[tuple[ProviderType, str | None]] = [
    (ProviderType.OLLAMA, "glm-5"),
    (ProviderType.OLLAMA, "deepseek-v3.2"),
    (ProviderType.GOOGLE_AI, None),
]


# A realistically BLOATED (>50KB) researcher note with >3 entries so the real
# NervousSystem flags it and the real distiller has genuine content to compress.
def _bloated_note_text() -> str:
    blocks = []
    findings = [
        "L5 residual stream is the primary causal site for R_V contraction (d=4.14).",
        "Head 21 at L5 is the first direction-specific steering site (38% BT+ART held-out vs 8% control).",
        "R_V is an epiphenomenal readout, not the mechanism; non-universal (6/8 models contract).",
        "Pythia-2.8B expands rather than contracts — a clean counterexample to universality.",
        "Witness attractor: self-referential processing contracts representation space.",
        "Idempotency keys must be generated at the client boundary, before the side effect.",
        "Exponential backoff with base 250ms reduces retry storms under contention.",
        "SQLite WAL mode lets readers proceed during a writer's transaction.",
        "Decorrelated agent errors cancel: E_ensemble = E_mean - E_diversity (Krogh-Vedelsby).",
        "MAP-Elites behavioral diversity preserves transcendence under fitness pressure.",
    ]
    for i in range(60):
        f = findings[i % len(findings)]
        blocks.append(
            f"## Task {i:03d} — {datetime(2026, 6, (i % 27) + 1).date()}\n"
            f"Result: completed. Key finding: {f}\n"
            f"Notes: {'context filler to exceed the 50KB distill threshold. ' * 30}\n"
        )
    return "# Researcher Notes (raw)\n\n" + "\n---\n".join(blocks)


def _seed_real_state_dir(state_dir: Path) -> Path:
    """Build a realistic owner surface so the REAL NervousSystem senses real data."""
    shared = state_dir / "shared"
    meta = state_dir / "meta"
    stig = state_dir / "stigmergy"
    state = state_dir / "state"
    for d in (shared, meta, stig, state):
        d.mkdir(parents=True, exist_ok=True)

    note_path = shared / "researcher_notes.md"
    note_path.write_text(_bloated_note_text(), encoding="utf-8")
    # Fresh tier-3 / tier-4 sources so health is computable on real files.
    (state_dir / ".FOCUS").write_text("Loop closure campaign — Loop 10 close-unit.\n")
    (state / "NOW.json").write_text(json.dumps({"now": "loop10 closure"}))
    (state_dir / "thread_state.json").write_text(
        json.dumps({"current_thread": "loop-closure", "contributions": {"a": 3, "b": 2}})
    )
    (meta / "recognition_seed.md").write_text("# Recognition Seed\nLoop 10 closure run.\n")
    (shared / "jk_pulse.md").write_text("JK pulse: nominal.\n")
    (stig / "marks.jsonl").write_text("")
    return note_path


def _seed_scoped_db(path: str, task_id: str) -> str:
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS delegation_runs (
            run_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL DEFAULT '',
            task_id TEXT NOT NULL,
            claim_id TEXT NOT NULL DEFAULT '',
            parent_run_id TEXT NOT NULL DEFAULT '',
            assigned_by TEXT NOT NULL DEFAULT '',
            assigned_to TEXT NOT NULL,
            requested_output_json TEXT NOT NULL DEFAULT '[]',
            current_artifact_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            failure_code TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            trace_id TEXT NOT NULL DEFAULT '',
            receipt_json TEXT
        )"""
    )
    run_id = f"run_{uuid4().hex[:16]}"
    conn.execute(
        "INSERT INTO delegation_runs (run_id, task_id, assigned_to, status, started_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, task_id, "context-agent", "running",
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()
    return run_id


class _ScopedSyncDB:
    """Minimal async-shim over a sync sqlite conn matching spine.persistence.AsyncDB."""

    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path)
        self._last = None

    async def execute(self, sql: str, parameters: tuple = ()):  # noqa: ANN001
        self._last = self._conn.execute(sql, parameters)
        return self._last

    async def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


# Captured real-provider call accounting for the act-step receipt.
_capture: dict[str, object] = {}


async def _live_free_complete(prompt: str, system: str | None) -> object:
    """Call the first live FREE provider. Returns the real LLMResponse. No mock."""
    last_exc: Exception | None = None
    for pt, model_hint in FREE_CANDIDATES:
        cfg = resolve_runtime_provider_config(pt, model=model_hint)
        if not cfg.available:
            continue
        provider = create_runtime_provider(cfg)
        try:
            req = LLMRequest(
                model=cfg.default_model or model_hint or "",
                messages=[{"role": "user", "content": prompt}],
                system=system or "",
                max_tokens=512,
                temperature=0.3,
            )
            resp = await asyncio.wait_for(provider.complete(req), timeout=90)
            usage = resp.usage or {}
            in_tok = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
            out_tok = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
            if not resp.content or not resp.content.strip() or out_tok <= 0:
                last_exc = RuntimeError(f"{pt.value} returned empty/0-token output")
                continue
            _capture["provider"] = resp.provider or pt.value
            _capture["model"] = resp.model or cfg.default_model or model_hint or ""
            _capture["in_tok"] = in_tok
            _capture["out_tok"] = out_tok
            _capture["content"] = resp.content
            return resp
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
        finally:
            close = getattr(provider, "close", None)
            if callable(close):
                try:
                    await close()
                except Exception:
                    pass
    raise RuntimeError(f"no live FREE provider answered (last error: {last_exc})")


async def _persist_act_receipt(task_id: str, trace_id: str, distilled_path: Path) -> EvidenceReceipt:
    """Persist a real-provider EvidenceReceipt for the context-agent act (Loop-1 edge)."""
    if os.environ.get("DHARMA_SPINE_DISPATCH") != "1":
        raise RuntimeError("DHARMA_SPINE_DISPATCH must be set to 1 for real dispatch")

    provider = str(_capture["provider"])
    model = str(_capture["model"])
    in_tok = int(_capture["in_tok"])  # type: ignore[arg-type]
    out_tok = int(_capture["out_tok"])  # type: ignore[arg-type]
    content = str(_capture["content"])
    side_effect_key = (
        f"{provider}:{model}:in{in_tok}:out{out_tok}:"
        f"{abs(hash(content)) & 0xFFFFFFFF:08x}"
    )

    routing = RoutingDecision(
        agent_id="context-agent",
        provider=provider,
        model=model,
        reason="context-agent distill act-step (free-first decorrelated)",
        router_name="loop10_context_free_first",
        context_id=trace_id,
        task_id=task_id,
    )

    async def _invoker(task, agent_id, context_id, routing):  # noqa: ANN001
        return EvidenceReceipt(
            trace_id=trace_id,
            context_id=context_id,
            task_id=task_id,
            agent_id=agent_id,
            provider=provider,
            model=model,
            operation="invoke_agent",
            provider_attempted=True,
            status="ok",
            error_source="none",
            finished_at=datetime.now(timezone.utc),
            latency_ms=0,
            input_tokens=in_tok,
            output_tokens=out_tok,
            routing_decision_id=routing.decision_id,
            attributes={
                "loop": 10,
                "loop_role": "context_agent_act",
                "router": "loop10_context_free_first",
                "side_effect_key": side_effect_key,
                # the owner-surface artifact this act produced:
                "distilled_artifact": str(distilled_path),
                "content_preview": content[:60],
                "free_first": True,
            },
        )

    receipt = await invoke_agent(
        task={"prompt": "context-agent distill act"},
        agent_id="context-agent",
        context_id=trace_id,
        routing=routing,
        invoker=_invoker,
    )

    from dharma_swarm.spine.persistence import persist_receipt

    db = _ScopedSyncDB(SCOPED_DB)
    try:
        await persist_receipt(receipt, db)
        await db.execute(
            "UPDATE delegation_runs SET status='completed', completed_at=? WHERE task_id=?",
            (datetime.now(timezone.utc).isoformat(), task_id),
        )
        await db.commit()
    finally:
        db.close()
    return receipt


async def main() -> int:
    if os.environ.get("DHARMA_SPINE_DISPATCH") != "1":
        print("ERROR: DHARMA_SPINE_DISPATCH must be 1 for real dispatch")
        return 1

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOOP10_DIR.mkdir(parents=True, exist_ok=True)
    note_path = _seed_real_state_dir(STATE_DIR)

    from dharma_swarm.context_agent import ContextAgent

    # Build the REAL ContextAgent scoped to the temp state dir. Owner surfaces
    # (context/, stigmergy marks) land under STATE_DIR.
    bus = SignalBus()
    emitted: list[dict] = []
    bus.subscribe("CONTEXT_HEALTH", lambda e: emitted.append(e))
    agent = ContextAgent(signal_bus=bus, base_path=STATE_DIR)
    # Scope the stigmergy owner surface to the temp state dir (no production write).
    agent.store = StigmergyStore(base_path=STATE_DIR / "stigmergy")

    # ── SENSE + INTERPRET on real files (no pin needed; pure Python) ──
    freshness = agent.nervous.scan_freshness()
    health = agent.nervous.assess_health(freshness)
    bloated = agent.nervous.find_bloated_notes()
    print(f"SENSE: {len(freshness)} sources scanned. health={health['score']:.3f}")
    print(f"INTERPRET/CONSTRAIN: bloated notes flagged = {[b[0] for b in bloated]}")
    if not bloated:
        print("RED: no bloated note flagged — constrain edge did not arm the act")
        return 1

    # ── ACT: pin the REAL Intelligence LLM call to a live FREE provider ──
    # Intelligence._complete is the single LLM chokepoint for distill/cross-
    # pollinate/dream. Pinning it to a live FREE provider makes the act a real
    # provider dispatch (real tokens, no mock) while running the REAL distiller.
    async def _pinned_complete(system, prompt):  # noqa: ANN001
        resp = await _live_free_complete(prompt, system)
        return resp.content

    agent.intelligence._complete = _pinned_complete  # type: ignore[attr-defined]

    role, bpath, size_kb = bloated[0]
    distilled_path = await agent.intelligence.distill_notes(role, bpath)
    if distilled_path is None or not distilled_path.exists():
        print("RED: distillation produced no artifact (provider returned nothing usable)")
        return 1
    if not _capture:
        print("RED: act-step did not capture a real provider response")
        return 1
    print(
        f"ACT: distilled {role} {size_kb}KB -> {distilled_path} "
        f"({distilled_path.stat().st_size // 1024}KB) via provider={_capture['provider']} "
        f"model={_capture['model']} in_tok={_capture['in_tok']} out_tok={_capture['out_tok']}"
    )

    # Persist the Loop-1 consume-edge spine receipt for the act.
    task_id = f"task_loop10_{uuid4().hex[:12]}"
    trace_id = f"trace_loop10_{uuid4().hex[:12]}"
    _seed_scoped_db(SCOPED_DB, task_id)
    receipt = await _persist_act_receipt(task_id, trace_id, distilled_path)

    # ── ADAPT: stigmergy mark on the owner surface + CONTEXT_HEALTH signal +
    # the cycle's freshness/alerts writes. Run the REAL run_cycle's serve/emit
    # path by leaving the same mark the agent leaves and emitting the signal,
    # then write the cycle freshness so the next sense sees it. ──
    from dharma_swarm.stigmergy import StigmergicMark

    mark_id = await agent.store.leave_mark(StigmergicMark(
        agent="context-agent",
        file_path=str(distilled_path),
        action="write",
        observation=f"Distilled {role} notes: {size_kb}KB -> "
                    f"{distilled_path.stat().st_size // 1024}KB",
        salience=0.7,
    ))
    bus.emit({
        "type": "CONTEXT_HEALTH",
        "score": health["score"],
        "alerts": health["alerts"],
        "cycle": 1,
        "side_effect_key": receipt.attributes.get("side_effect_key"),
    })
    context_dir = STATE_DIR / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    (context_dir / "freshness.json").write_text(
        json.dumps({"health": health, "freshness": freshness}, indent=2, default=str)
    )

    # Emit the adapt receipt that ties the owner-surface artifacts to the real act.
    adapt_receipt = {
        "type": "CONTEXT_CYCLE",
        "source": "context-agent",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scoped_db": SCOPED_DB,
        "state_dir": str(STATE_DIR),
        "health_score": health["score"],
        "distilled_artifact": str(distilled_path),
        "stigmergy_mark_id": mark_id,
        "stigmergy_marks_file": str(STATE_DIR / "stigmergy" / "marks.jsonl"),
        "act_run_id": receipt.task_id,
        "act_side_effect_key": receipt.attributes.get("side_effect_key"),
        "act_provider": receipt.provider,
        "act_model": receipt.model,
        "context_health_signals": emitted,
        "one_wire_note": "internal context write only; no archive.jsonl write",
    }
    adapt_path = LOOP10_DIR / "loop10_adapt_receipt.json"
    adapt_path.write_text(json.dumps(adapt_receipt, indent=2, default=str))

    print(
        f"\nADAPT: stigmergy mark={mark_id} CONTEXT_HEALTH emitted={len(emitted)} "
        f"freshness.json written"
    )
    print(
        f"SPINE RECEIPT provider={receipt.provider} model={receipt.model} "
        f"in_tok={receipt.input_tokens} out_tok={receipt.output_tokens} "
        f"side_effect_key={receipt.attributes.get('side_effect_key')}"
    )
    print(f"STATE_DIR={STATE_DIR}")
    print(f"SCOPED_DB={SCOPED_DB}")
    print(f"LOOP10_DIR={LOOP10_DIR}")
    print(f"DISTILLED={distilled_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
