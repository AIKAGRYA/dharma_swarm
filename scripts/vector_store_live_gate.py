#!/usr/bin/env python3
"""Live raw-vector gate for the compact memory retrieval lane."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.vector_store import VectorStore


DEFAULT_CASES: tuple[dict[str, Any], ...] = (
    {
        "name": "s_x_fixed_point",
        "query": "S(x) self sustaining fixed point",
        "expected": "s-x-equals-x",
    },
    {
        "name": "orchestrator",
        "query": "orchestrator async task routing engine",
        "expected": "concepts-orchestrator",
    },
    {
        "name": "lmstudio_mlx",
        "query": "LM Studio MLX local model inference",
        "expected": "lmstudio-mlx",
    },
    {
        "name": "jagat_kalyan",
        "query": "Jagat Kalyan universal welfare north star",
        "expected": "concepts-jagat-kalyan",
    },
    {
        "name": "gnani_purush",
        "query": "Gnani Purush realized teacher",
        "expected": "concepts-gnani-purush",
    },
    {
        "name": "bronze_supply_chain",
        "query": "bronze supply chain intake dedup MinHash LSH",
        "expected": "bronze-supply-chain-intake",
    },
    {
        "name": "apex_holon_vision",
        "query": "Apex Holon agent vision full system architecture",
        "expected": "42190",
    },
    {
        "name": "dharma_capital_holon",
        "query": "Dharma Capital Holon loop never closes tier changes",
        "expected": "42219",
    },
    {
        "name": "gaia_restoration",
        "query": "GAIA browser state restoration packet",
        "expected": "gaia",
    },
    {
        "name": "negative_canary",
        "query": "xyzzq impossible memory topic lunar cheese invoice",
        "expected": "",
        "expect_empty": True,
    },
)


@dataclass(frozen=True)
class VectorGateReceipt:
    state_dir: str
    db_path: str
    memory_embedder_path: str
    memory_corpus_len: int
    case_count: int
    passed_cases: int
    score: float
    passed: bool
    p95_latency_ms: float
    max_latency_ms: float
    cases: tuple[dict[str, Any], ...]

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", default=str(Path.home() / ".dharma"))
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-memory-corpus", type=int, default=500)
    parser.add_argument("--max-p95-ms", type=float, default=750.0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--receipt-path", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = run_gate(
        state_dir=Path(args.state_dir).expanduser(),
        top_k=max(1, args.top_k),
        min_memory_corpus=max(1, args.min_memory_corpus),
        max_p95_ms=max(1.0, args.max_p95_ms),
    )
    if args.receipt_path:
        path = Path(args.receipt_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt.to_json(), indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(receipt.to_json(), indent=2, sort_keys=True))
    else:
        print(render_receipt(receipt))
    return 0 if receipt.passed else 1


def run_gate(
    *,
    state_dir: Path,
    top_k: int = 3,
    min_memory_corpus: int = 500,
    max_p95_ms: float = 750.0,
    cases: tuple[dict[str, Any], ...] = DEFAULT_CASES,
) -> VectorGateReceipt:
    store = VectorStore(state_dir=state_dir, dim=128)
    memory_embedder_path = state_dir / "tfidf_embedder_memory_retrieval.pkl"
    memory_corpus_len = _memory_corpus_len(memory_embedder_path)
    case_receipts: list[dict[str, Any]] = []
    latencies: list[float] = []
    passed_cases = 0
    for case in cases:
        t0 = time.perf_counter()
        rows = store.search_vector(str(case["query"]), top_k=top_k)
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        latencies.append(latency_ms)
        top = rows[0] if rows else None
        haystack = ""
        if top is not None:
            haystack = f"{top.get('source', '')} {top.get('content', '')}".lower()
        expect_empty = bool(case.get("expect_empty"))
        expected = str(case.get("expected", "")).lower()
        passed = (not rows) if expect_empty else bool(top and expected in haystack)
        if passed:
            passed_cases += 1
        case_receipts.append(
            {
                "name": case["name"],
                "query": case["query"],
                "expected": case.get("expected", ""),
                "expect_empty": expect_empty,
                "passed": passed,
                "latency_ms": latency_ms,
                "result_count": len(rows),
                "top_id": top.get("id") if top else None,
                "top_layer": top.get("layer") if top else None,
                "top_source": top.get("source") if top else None,
                "top_distance": top.get("distance") if top else None,
                "top_preview": str(top.get("content", ""))[:180] if top else "",
            }
        )
    p95 = _p95(latencies)
    score = round(100.0 * passed_cases / max(1, len(cases)), 2)
    passed = (
        passed_cases == len(cases)
        and memory_corpus_len >= min_memory_corpus
        and p95 <= max_p95_ms
    )
    if not passed and memory_corpus_len < min_memory_corpus:
        score = min(score, 80.0)
    if not passed and p95 > max_p95_ms:
        score = min(score, 90.0)
    return VectorGateReceipt(
        state_dir=str(state_dir),
        db_path=str(state_dir / "vectors.db"),
        memory_embedder_path=str(memory_embedder_path),
        memory_corpus_len=memory_corpus_len,
        case_count=len(cases),
        passed_cases=passed_cases,
        score=score,
        passed=passed,
        p95_latency_ms=p95,
        max_latency_ms=round(max(latencies) if latencies else 0.0, 3),
        cases=tuple(case_receipts),
    )


def _memory_corpus_len(path: Path) -> int:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        return len(state.get("corpus", []))
    except Exception:
        return 0


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    if len(values) < 2:
        return round(values[0], 3)
    return round(statistics.quantiles(values, n=20, method="inclusive")[18], 3)


def render_receipt(receipt: VectorGateReceipt) -> str:
    status = "PASS" if receipt.passed else "FAIL"
    lines = [
        f"# VectorStore Live Gate: {status}",
        "",
        f"- Score: `{receipt.score}/100`",
        f"- Cases: `{receipt.passed_cases}/{receipt.case_count}`",
        f"- Memory corpus rows: `{receipt.memory_corpus_len}`",
        f"- p95 latency ms: `{receipt.p95_latency_ms}`",
        f"- Max latency ms: `{receipt.max_latency_ms}`",
    ]
    for case in receipt.cases:
        marker = "PASS" if case["passed"] else "FAIL"
        lines.append(
            f"- {marker} `{case['name']}` -> `{case['top_source']}` "
            f"({case['latency_ms']} ms)"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
