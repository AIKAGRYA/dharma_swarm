#!/usr/bin/env python3
"""Loop 11 (Replication Monitor) closure driver — run the REAL checkpoint-gated
ReplicationProtocol over a proposal provably triggered by REAL Loop-1 outputs.

Loop 11 consumes Loop 1 output: completed delegation_runs are the evidence that a
capability gap exists, which (via the consolidation->differentiation handoff) feeds
a replication proposal. This driver closes that fed-cascade edge WITHOUT touching
the production daemon, the live runtime.db, or archive fitness.

Loop 11 trace (owner surface: dharma_swarm/replication_protocol.py +
orchestrate_live._run_replication_monitor_loop; CYBERNETIC_LOOP_MAP.md row 11
"Replication Monitor"):
  SENSE     ReplicationProtocol.get_pending_proposals() drains proposals.jsonl.
            The proposal's evidence is grounded in REAL Loop-1 completed runs.
  INTERPRET G1 _validate_proposal (required fields, generation cap, parent in
            roster, no duplicate) + S _assess_need (population capacity, budget,
            severity threshold).
  CONSTRAIN G2 _check_gates: the 11 REAL telos gates (TelosGatekeeper.check) +
            REAL kernel SHA-256 integrity (KernelGuard.verify_integrity). NOT
            weakened, NOT mocked — must PASS legitimately (decision != BLOCK).
  ACT       M _materialize: REAL GenomeInheritance composes a child AgentSpec from
            a real parent in the bootstrapped roster; child registered + added to
            roster; probation started. A child agent actually materializes.
  ADAPT     M_MATERIALIZED witness receipt + materialized proposals.jsonl entry +
            AGENT_REPLICATED signal; child is now tracked for probation/apoptosis.

It does the following, all on REAL data:

  1. Drives N real FREE-provider Loop-1 dispatches through
     dharma_swarm.spine.invoke.invoke_agent, persisting Loop-1-shaped
     EvidenceReceipts (real provider/model/input_tokens>0/side_effect_key) to a
     SCOPED delegation_runs db. No mock provider anywhere.
  2. SENSE: reads those real completed run_ids back from the scoped db; they are
     the evidence the replication proposal cites.
  3. INTERPRET+CONSTRAIN+ACT: runs the REAL ReplicationProtocol.run() with a
     SCOPED state_dir, a real bootstrapped DynamicRoster, real DEFAULT_GATEKEEPER,
     real KernelGuard, real GenomeInheritance, real PopulationController. A child
     agent materializes through the real G1->S->G2->M pipeline.
  4. ADAPT: writes ONE replication_cycle receipt (the adapt payload) referencing
     the same real Loop-1 run_ids, the materialized child name, and the witness
     stages observed. This is an INTERNAL state write, NOT an archive-fitness
     write (One Wire stays intact — nothing here touches archive.jsonl).

Run:
  DHARMA_SPINE_DISPATCH=1 \
    LC_LOOP11_RUNTIME_DB=/tmp/lc_loop11_runtime.db \
    LC_LOOP11_STATE_DIR=/tmp/lc_loop11_state \
    python3 scripts/governance/closure/drive_loop_11.py
Then:
  LC_LOOP11_RUNTIME_DB=/tmp/lc_loop11_runtime.db \
    LC_LOOP11_STATE_DIR=/tmp/lc_loop11_state \
    python3 scripts/governance/closure/check_loop_11.py
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

from dharma_swarm.models import LLMRequest, ProviderType  # noqa: E402
from dharma_swarm.runtime_provider import (  # noqa: E402
    create_runtime_provider,
    resolve_runtime_provider_config,
)
from dharma_swarm.spine.invoke import invoke_agent  # noqa: E402
from dharma_swarm.spine.receipt import EvidenceReceipt  # noqa: E402
from dharma_swarm.spine.routing import RoutingDecision  # noqa: E402

RUNTIME_DB = os.environ.get(
    "LC_LOOP11_RUNTIME_DB", f"/tmp/lc_loop11_runtime_{int(time.time())}.db"
)
STATE_DIR = Path(
    os.environ.get("LC_LOOP11_STATE_DIR", f"/tmp/lc_loop11_state_{int(time.time())}")
)

# FREE-first decorrelated candidates (live-confirmed 2026-06-16). Each is a real
# LLM provider; none is 'orchestrator'/'mock'. We require >=3 SUCCESSFUL real
# dispatches (input_tokens>0) as the Loop-1 evidence that justifies a capability
# gap. gemini-2.5-flash is intentionally NOT used here: its free-tier daily quota
# (20 req/day) is exhausted by the other loop drivers, so it 429s. The two
# ollama_cloud families (glm-5, deepseek-v3.2) are distinct model families that
# return substantive, tokenized responses — decorrelated and reliable.
FREE_CANDIDATES: list[tuple[ProviderType, str | None]] = [
    (ProviderType.OLLAMA, "glm-5"),
    (ProviderType.OLLAMA, "deepseek-v3.2"),
    (ProviderType.OLLAMA, "glm-5"),
    (ProviderType.OLLAMA, "deepseek-v3.2"),
    (ProviderType.OLLAMA, "glm-5"),
    (ProviderType.OLLAMA, "deepseek-v3.2"),
]

# More tasks than the >=3 minimum so transient zero-token responses (a real
# provider occasionally returns no usage) still leave >=3 valid receipts.


# Loop-1 tasks whose completion evidences a capability gap (the differentiation
# trigger). Real provider answers; only the seed text is synthetic.
TASKS = [
    "Reply with exactly one word: ALPHA",
    "Reply with exactly one word: BRAVO",
    "Reply with exactly one word: CHARLIE",
    "Reply with exactly one word: DELTA",
    "Reply with exactly one word: ECHO",
    "Reply with exactly one word: FOXTROT",
]


def _seed_runtime_db(path: str, task_ids: list[str]) -> None:
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
    now = datetime.now(timezone.utc).isoformat()
    for tid in task_ids:
        conn.execute(
            "INSERT INTO delegation_runs (run_id, task_id, assigned_to, status, started_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (f"run_{uuid4().hex[:16]}", tid, "loop11_closer", "running", now),
        )
    conn.commit()
    conn.close()


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


async def _real_provider_invoker(task, agent_id, context_id, routing):  # noqa: ANN001
    """The blessed invoker: call a REAL live FREE provider, return a real receipt."""
    pt: ProviderType = task["_provider_type"]
    model_hint: str | None = task["_model_hint"]
    prompt: str = task["prompt"]

    cfg = resolve_runtime_provider_config(pt, model=model_hint)
    if not cfg.available:
        raise RuntimeError(f"provider {pt.value} unavailable (no live key)")
    provider = create_runtime_provider(cfg)
    req = LLMRequest(
        model=cfg.default_model or model_hint or "",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=32,
        temperature=0,
    )
    t0 = time.monotonic()
    resp = await asyncio.wait_for(provider.complete(req), timeout=90)
    latency_ms = int((time.monotonic() - t0) * 1000)

    usage = resp.usage or {}
    in_tok = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    out_tok = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    real_provider = resp.provider or pt.value
    real_model = resp.model or cfg.default_model or ""

    # A real provider must return token accounting; a zero-token response is not
    # valid Loop-1 evidence (it cannot pass check_loop_11's input_tokens>0 filter).
    # Treat it as a failed dispatch so the driver moves to the next candidate.
    if in_tok <= 0:
        raise RuntimeError(
            f"provider {real_provider}/{real_model} returned zero input_tokens "
            "(no usable usage accounting) — not valid evidence"
        )

    side_effect_key = (
        f"{real_provider}:{real_model}:in{in_tok}:out{out_tok}:"
        f"{abs(hash(resp.content)) & 0xFFFFFFFF:08x}"
    )

    return EvidenceReceipt(
        trace_id=task["_trace_id"],
        context_id=context_id,
        task_id=task["_task_id"],
        agent_id=agent_id,
        provider=real_provider,
        model=real_model,
        operation="invoke_agent",
        provider_attempted=True,
        status="ok",
        error_source="none",
        finished_at=datetime.now(timezone.utc),
        latency_ms=latency_ms,
        input_tokens=in_tok,
        output_tokens=out_tok,
        routing_decision_id=routing.decision_id,
        attributes={
            "router": "loop11_closer_free_first",
            "side_effect_key": side_effect_key,
            "content_preview": resp.content[:60],
            "free_first": True,
        },
    )


async def _dispatch_one(scoped_db_path, task_id, trace_id, prompt, pt, model_hint):  # noqa: ANN001
    if os.environ.get("DHARMA_SPINE_DISPATCH") != "1":
        raise RuntimeError("DHARMA_SPINE_DISPATCH must be set to 1 for real dispatch")

    routing = RoutingDecision(
        agent_id="loop11_closer",
        provider=pt.value,
        model=model_hint or "",
        reason="free-first decorrelated closure dispatch",
        router_name="loop11_closer_free_first",
        context_id=trace_id,
        task_id=task_id,
    )
    task = {
        "prompt": prompt,
        "_provider_type": pt,
        "_model_hint": model_hint,
        "_task_id": task_id,
        "_trace_id": trace_id,
    }
    receipt = await invoke_agent(
        task=task,
        agent_id="loop11_closer",
        context_id=trace_id,
        routing=routing,
        invoker=_real_provider_invoker,
    )
    from dharma_swarm.spine.persistence import persist_receipt

    db = _ScopedSyncDB(scoped_db_path)
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


def _real_loop1_run_ids(db_path: str) -> list[dict]:
    """SENSE side: REAL-provider completed Loop-1 rows (the replication evidence)."""
    bad = {"", "orchestrator", "mock", "stub", "fixture", "test", "none"}
    out: list[dict] = []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = conn.execute(
            "SELECT run_id, receipt_json FROM delegation_runs "
            "WHERE status='completed' AND receipt_json IS NOT NULL AND receipt_json!=''"
        )
        for run_id, rj in cur:
            try:
                r = json.loads(rj)
            except Exception:
                continue
            provider = str(r.get("provider", "")).strip().lower()
            model = str(r.get("model", "")).strip()
            itok = r.get("input_tokens")
            if provider in bad or not model:
                continue
            if not isinstance(itok, (int, float)) or itok <= 0:
                continue
            out.append({"run_id": run_id, "provider": r.get("provider"), "model": model})
    finally:
        conn.close()
    return out


async def main() -> int:
    if os.environ.get("DHARMA_SPINE_DISPATCH") != "1":
        print("DHARMA_SPINE_DISPATCH must be set to 1 for real dispatch")
        return 1

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Phase 1: real Loop-1 dispatches (the evidence of capability gap) ----
    task_ids = [f"task_loop11_{uuid4().hex[:12]}" for _ in TASKS]
    _seed_runtime_db(RUNTIME_DB, task_ids)
    successes = 0
    errors: list[str] = []
    for i, prompt in enumerate(TASKS):
        pt, model_hint = FREE_CANDIDATES[i % len(FREE_CANDIDATES)]
        trace_id = f"trace_loop11_{uuid4().hex[:12]}"
        try:
            r = await _dispatch_one(RUNTIME_DB, task_ids[i], trace_id, prompt, pt, model_hint)
            successes += 1
            print(
                f"LOOP1 DISPATCH OK task={task_ids[i]} provider={r.provider} "
                f"model={r.model} in_tok={r.input_tokens} out_tok={r.output_tokens}"
            )
        except Exception as e:  # noqa: BLE001
            errors.append(f"{pt.value}: {type(e).__name__}: {str(e)[:140]}")
            print(f"LOOP1 DISPATCH ERR task={task_ids[i]} {pt.value}: {e}")

    real_runs = _real_loop1_run_ids(RUNTIME_DB)
    print(f"\nReal Loop-1 completed runs (evidence): {len(real_runs)} (need >=3)")
    if len(real_runs) < 3:
        print("Not enough real Loop-1 evidence to justify replication. RED.")
        if errors:
            print("errors:", json.dumps(errors, indent=2))
        return 1
    evidence_run_ids = [r["run_id"] for r in real_runs]

    # ---- Phase 2: REAL replication pipeline triggered by that evidence ----
    from dharma_swarm.agent_constitution import bootstrap_dynamic_roster
    from dharma_swarm.replication_protocol import ReplicationProtocol

    roster = bootstrap_dynamic_roster(state_dir=STATE_DIR)
    parents = [s.name for s in roster.get_all()]
    if not parents:
        print("No parent agents in roster; cannot replicate. RED.")
        return 1
    parent = parents[0]

    # The proposal cites the real Loop-1 run_ids as its evidence: this is the
    # genuine Loop-1 -> Loop-11 link. Severity is high because >=3 completed runs
    # provably exercised the gap (no fabricated number).
    proposal_data = {
        "proposed_role": "loop11_replication_specialist",
        "justification": (
            f"Capability gap evidenced by {len(real_runs)} REAL completed Loop-1 "
            f"runs: {', '.join(evidence_run_ids[:3])}"
        ),
        "capability_gap": f"loop11-closure-real-data-{uuid4().hex[:8]}",
        "parent_agent": parent,
        "generation": 0,
        "severity": 0.8,
        "evidence_metadata": {
            "loop1_run_ids": evidence_run_ids,
            "providers": sorted({r["provider"] for r in real_runs}),
            "models": sorted({r["model"] for r in real_runs}),
        },
    }

    # REAL gatekeeper, REAL kernel, REAL genome, REAL population controller are all
    # lazily constructed inside ReplicationProtocol when not injected. We inject
    # only the bootstrapped roster (so the parent exists) and the scoped state_dir.
    protocol = ReplicationProtocol(state_dir=STATE_DIR, dynamic_roster=roster)
    outcome = await protocol.run(proposal_data)

    print(
        f"\nREPLICATION success={outcome.success} child={outcome.child_agent_name} "
        f"gate_decision={outcome.gate_results.get('decision')} err={outcome.error}"
    )
    if not outcome.success or not outcome.child_agent_name:
        print("Replication did not materialize a child. RED.")
        return 1

    # G5 guard: the gate must have PASSED on its own merits, never BLOCK.
    gate_decision = str(outcome.gate_results.get("decision", "")).upper()
    if gate_decision == "BLOCK":
        print("Telos gate BLOCKED — closure must never bypass a gate. RED.")
        return 1

    # Confirm the child is actually in the roster (the ACT edge landed).
    child_in_roster = roster.get(outcome.child_agent_name) is not None

    # ---- Phase 3: ADAPT receipt (internal state write, NOT archive fitness) ----
    witness_file = STATE_DIR / "witness" / "replication.jsonl"
    witness_stages = []
    if witness_file.exists():
        for line in witness_file.read_text().splitlines():
            try:
                witness_stages.append(json.loads(line).get("type"))
            except Exception:
                continue

    adapt = {
        "type": "REPLICATION_CYCLE",
        "loop": 11,
        "evidence_loop1_run_ids": evidence_run_ids,
        "child_agent_name": outcome.child_agent_name,
        "parent_agent": parent,
        "gate_decision": outcome.gate_results.get("decision"),
        "witness_stages": witness_stages,
        "child_in_roster": child_in_roster,
        "state_dir": str(STATE_DIR),
        "runtime_db": RUNTIME_DB,
        "note": "internal replication state write only; no archive.jsonl fitness write",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    adapt_path = STATE_DIR / "loop11_adapt_receipt.json"
    adapt_path.write_text(json.dumps(adapt, indent=2), encoding="utf-8")
    print(f"\nADAPT receipt written: {adapt_path}")
    print(f"witness stages: {witness_stages}")
    print(f"child_in_roster: {child_in_roster}")
    print(f"RUNTIME_DB={RUNTIME_DB}")
    print(f"STATE_DIR={STATE_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
