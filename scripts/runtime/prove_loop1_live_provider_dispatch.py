#!/usr/bin/env python3
"""Prove Loop 1 with one bounded live provider dispatch through the spine."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.api_keys import bootstrap_runtime_env  # noqa: E402
from dharma_swarm.models import (  # noqa: E402
    AgentConfig,
    AgentRole,
    LLMRequest,
    ProviderType,
    Task,
    TaskDispatch,
    TopologyType,
)
from dharma_swarm.orchestrator import Orchestrator  # noqa: E402
from dharma_swarm.runtime_provider import (  # noqa: E402
    create_runtime_provider,
    resolve_runtime_provider_config,
)
from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB  # noqa: E402


DEFAULT_PROVIDER = ProviderType.NVIDIA_NIM
DEFAULT_MODEL = "meta/llama-3.3-70b-instruct"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _same_path(left: Path, right: Path) -> bool:
    return left.expanduser().resolve() == right.expanduser().resolve()


def _provider_type(value: str) -> ProviderType:
    try:
        return ProviderType(value)
    except ValueError as exc:
        choices = ", ".join(provider.value for provider in ProviderType)
        raise argparse.ArgumentTypeError(
            f"unsupported provider {value!r}; choices: {choices}"
        ) from exc


def _insert_delegation_run(
    db_path: Path,
    *,
    run_id: str,
    task_id: str,
    agent_id: str,
    trace_id: str,
    started_at: str,
) -> None:
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            INSERT INTO delegation_runs
                (run_id, session_id, task_id, assigned_to, status, started_at,
                 trace_id, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                f"sess_{run_id}",
                task_id,
                agent_id,
                "running",
                started_at,
                trace_id,
                json.dumps({"source": "prove_loop1_live_provider_dispatch"}),
            ),
        )


def _mark_delegation_run_completed(db_path: Path, *, run_id: str, status: str) -> None:
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            UPDATE delegation_runs
            SET status = ?, completed_at = ?
            WHERE run_id = ?
            """,
            (status, _utc_now().isoformat(), run_id),
        )


class _RuntimeLifecycleStub:
    def __init__(self, db_path: Path) -> None:
        self._store = SimpleNamespace(db_path=db_path)

    def _runtime_state_store(self) -> SimpleNamespace:
        return self._store


class _LiveProviderRunner:
    def __init__(self, *, provider_type: ProviderType, model: str, provider: object) -> None:
        self._config = AgentConfig(
            name="loop1-live-provider-proof",
            role=AgentRole.TESTER,
            provider=provider_type,
            model=model,
        )
        self._provider = provider
        self.actual_served_provider = ""
        self.actual_served_model = ""
        self.provider_model_truth_source = ""
        self.provider_execution: bool | str = ""
        self.provider_model_applicability = ""
        self.served_provider = ""
        self.served_model = ""
        self.provider_served = ""
        self.model_served = ""

    async def run_task(self, task: Task) -> str:
        request = LLMRequest(
            model=self._config.model,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Reply with exactly this token and nothing else: LOOP1_OK"
                    ),
                }
            ],
            max_tokens=32,
            temperature=0,
        )
        response = await self._provider.complete(request)
        provider = str(
            response.provider
            or getattr(self._provider, "runtime_provider_type", "")
            or self._config.provider.value
        ).strip()
        model = str(response.model or self._config.model).strip()
        if provider and model:
            self.actual_served_provider = provider
            self.actual_served_model = model
            self.provider_model_truth_source = "runtime_provider.actual_served"
            self.provider_execution = True
            self.provider_model_applicability = "actual_served"
            self.served_provider = provider
            self.served_model = model
            self.provider_served = provider
            self.model_served = model
        return response.content


async def run_live_dispatch(
    *,
    db_path: Path,
    provider_type: ProviderType,
    model: str,
    timeout_seconds: float,
) -> dict[str, object]:
    bootstrap_runtime_env()
    cfg = resolve_runtime_provider_config(
        provider_type,
        model=model,
        timeout_seconds=int(timeout_seconds),
        working_dir=str(REPO_ROOT),
    )
    if not cfg.available:
        raise RuntimeError(f"provider {provider_type.value} is not available")
    provider = create_runtime_provider(cfg)
    resolved_model = str(cfg.default_model or model)
    stamp = _utc_now().strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid4().hex[:8]
    run_id = f"loop1_live_provider_dispatch_{stamp}_{suffix}"
    task_id = f"task_{run_id}"
    trace_id = f"trace_{run_id}"
    agent_id = "loop1-live-provider-proof"
    started_at = _utc_now().isoformat()
    _insert_delegation_run(
        db_path,
        run_id=run_id,
        task_id=task_id,
        agent_id=agent_id,
        trace_id=trace_id,
        started_at=started_at,
    )
    runner = _LiveProviderRunner(
        provider_type=cfg.provider,
        model=resolved_model,
        provider=provider,
    )
    task = Task(
        id=task_id,
        title="Loop 1 live provider proof",
        description="Bounded provider dispatch through Orchestrator._run_task_via_spine.",
        metadata={"run_id": run_id, "trace_id": trace_id},
    )
    td = TaskDispatch(
        task_id=task_id,
        agent_id=agent_id,
        topology=TopologyType.PIPELINE,
        timeout_seconds=timeout_seconds,
        metadata={
            "execution_identity": {
                "trace_id": trace_id,
                "session_id": f"sess_{run_id}",
                "run_id": run_id,
            }
        },
    )
    owner = SimpleNamespace(_runtime_lifecycle=_RuntimeLifecycleStub(db_path))
    try:
        content = await Orchestrator._run_task_via_spine(
            owner,
            runner,
            task,
            td,
            timeout_seconds,
        )
    except Exception:
        _mark_delegation_run_completed(db_path, run_id=run_id, status="failed")
        raise
    _mark_delegation_run_completed(db_path, run_id=run_id, status="completed")
    receipt = owner._last_evidence_receipt
    return {
        "run_id": run_id,
        "task_id": task_id,
        "trace_id": trace_id,
        "db_path": str(db_path),
        "provider": receipt.provider,
        "model": receipt.model,
        "provider_model_truth_source": receipt.attributes.get(
            "provider_model_truth_source", ""
        ),
        "receipt_id": str(receipt.receipt_id),
        "status": receipt.status,
        "content_preview": str(content or "")[:80],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path(DEFAULT_RUNTIME_DB))
    parser.add_argument("--provider", type=_provider_type, default=DEFAULT_PROVIDER)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument(
        "--allow-live",
        action="store_true",
        help="required when writing the canonical runtime.db",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    db_path = args.db.expanduser()
    if _same_path(db_path, Path(DEFAULT_RUNTIME_DB)) and not args.allow_live:
        print(
            "refusing to write live runtime.db without --allow-live; "
            "pass --db for a temp DB or add --allow-live",
            file=sys.stderr,
        )
        return 2
    result = asyncio.run(
        run_live_dispatch(
            db_path=db_path,
            provider_type=args.provider,
            model=args.model,
            timeout_seconds=args.timeout_seconds,
        )
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("LOOP1 LIVE PROVIDER DISPATCH PROOF")
        print(f"DB:          {result['db_path']}")
        print(f"Run ID:      {result['run_id']}")
        print(f"Task ID:     {result['task_id']}")
        print(f"Receipt ID:  {result['receipt_id']}")
        print(f"Status:      {result['status']}")
        print(f"Provider:    {result['provider']}")
        print(f"Model:       {result['model']}")
        print(f"Truth source:{result['provider_model_truth_source']}")
        print(f"Preview:     {result['content_preview']}")
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
