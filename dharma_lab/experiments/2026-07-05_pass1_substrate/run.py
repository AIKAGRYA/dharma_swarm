"""Run the Pass 1 substrate experiment scaffold."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from dharma_lab.inference.router import route_question

EXPERIMENT_DIR = Path(__file__).resolve().parent
QUESTION_PATH = EXPERIMENT_DIR / "question.md"

PLANNED_ROUTES = {
    "claude_opus": {
        "provider": "anthropic",
        "model": "claude-opus-4-8",
        "live_capable": True,
    },
    "gpt5": {
        "provider": "openai",
        "model": "gpt-5.5",
        "live_capable": False,
    },
    "gemini_3_pro": {
        "provider": "google_ai",
        "model": "gemini-3.1-pro-preview",
        "live_capable": False,
    },
    "monlam_tibetan": {
        "provider": "hf_reference",
        "model": "MonlamAI/tibetan_RoBERTa_S_e6",
        "live_capable": False,
    },
}


async def run_experiment(
    *,
    repo_root: Path,
    dry_run: bool,
    route: str | None,
    output_dir: Path = EXPERIMENT_DIR,
) -> list[dict[str, object]]:
    question = QUESTION_PATH.read_text(encoding="utf-8")
    selected = [route] if route else list(PLANNED_ROUTES)
    responses_dir = output_dir / "responses"
    receipts_dir = output_dir / "receipts"
    responses_dir.mkdir(exist_ok=True)
    receipts_dir.mkdir(exist_ok=True)

    records: list[dict[str, object]] = []
    for route_name in selected:
        config = PLANNED_ROUTES[route_name]
        route_dry_run = dry_run or not bool(config["live_capable"])
        record = await route_question(
            repo_root=repo_root,
            question=question,
            modality_target="Attested_by",
            provider_name=str(config["provider"]),
            model=str(config["model"]),
            dry_run=route_dry_run,
        )
        payload = asdict(record)
        payload["route"] = route_name
        payload["dry_run"] = route_dry_run
        payload["receipt_path"] = record.receipt_path.relative_to(repo_root).as_posix()
        response_path = responses_dir / f"{route_name}.json"
        response_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        copied_receipt = receipts_dir / record.receipt_path.name
        shutil.copy2(record.receipt_path, copied_receipt)
        payload["experiment_receipt_path"] = _display_path(copied_receipt, repo_root)
        records.append(payload)
    return records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Dharma Lab Pass 1 substrate experiment.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root.")
    parser.add_argument("--dry-run", action="store_true", help="Skip all live model calls.")
    parser.add_argument("--route", choices=sorted(PLANNED_ROUTES), help="Run one route instead of every planned route.")
    parser.add_argument("--output-dir", type=Path, default=EXPERIMENT_DIR, help="Directory for response and receipt copies.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records = asyncio.run(
        run_experiment(
            repo_root=args.repo_root.resolve(),
            dry_run=args.dry_run,
            route=args.route,
            output_dir=args.output_dir.resolve(),
        )
    )
    print(json.dumps(records, indent=2, sort_keys=True))
    return 0


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
