"""Command-line tools for the Darshan Publication VentureCell."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from dharma_swarm.venture_cell.darshan.bundle import (
    create_bundle,
    refresh_manifest,
    validate_bundle,
)
from dharma_swarm.venture_cell.darshan.operator_log import append_operator_observation
from dharma_swarm.venture_cell.darshan.polsia_log import append_observation
from dharma_swarm.venture_cell.darshan.schema import (
    ExternalOperatorObservation,
    PolsiaObservation,
)
from dharma_swarm.venture_cell.darshan.substrate import materialize_bundle


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m dharma_swarm.venture_cell.darshan.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    build = sub.add_parser("build-bundle", help="create a Darshan artifact bundle")
    build.add_argument("--title", required=True)
    build.add_argument("--slug", default="")
    build.add_argument("--date", dest="bundle_date", default="")
    build.add_argument("--root", default="")
    build.add_argument("--overwrite", action="store_true")

    validate = sub.add_parser("validate-bundle", help="validate a Darshan artifact bundle")
    validate.add_argument("path")

    refresh = sub.add_parser("refresh-manifest", help="refresh bundle content hashes")
    refresh.add_argument("path")

    log = sub.add_parser("log-polsia", help="append a Polsia observation")
    log.add_argument("--track", required=True, choices=["collaborator", "observatory"])
    log.add_argument("--prompt-given", required=True)
    log.add_argument("--expected-output", default="")
    log.add_argument("--action", action="append", default=[])
    log.add_argument("--role", action="append", default=[])
    log.add_argument("--latency-minutes", type=float, default=0.0)
    log.add_argument("--output", action="append", default=[])
    log.add_argument("--quality-score", type=float, default=0.0)
    log.add_argument("--human-intervention-required", action="store_true")
    log.add_argument("--missing-receipt", action="append", default=[])
    log.add_argument("--reusable-operator-pattern", default="")
    log.add_argument("--followup-task", default="")
    log.add_argument("--log-path", default="")

    operator_log = sub.add_parser(
        "log-operator",
        help="append a Cofounder/Polsia/external-operator observation",
    )
    operator_log.add_argument(
        "--operator",
        required=True,
        choices=["cofounder", "polsia", "company_co", "openclaw", "custom"],
    )
    operator_log.add_argument(
        "--track",
        required=True,
        choices=["collaborator", "observatory", "benchmark"],
    )
    operator_log.add_argument("--venture-cell", default="DARSHAN")
    operator_log.add_argument("--surface", default="")
    operator_log.add_argument("--session-phase", default="")
    operator_log.add_argument("--prompt-given", required=True)
    operator_log.add_argument("--expected-output", default="")
    operator_log.add_argument("--response-summary", default="")
    operator_log.add_argument("--action", action="append", default=[])
    operator_log.add_argument("--role", action="append", default=[])
    operator_log.add_argument("--artifact", action="append", default=[])
    operator_log.add_argument("--screenshot-ref", action="append", default=[])
    operator_log.add_argument("--capability", action="append", default=[])
    operator_log.add_argument("--limitation", action="append", default=[])
    operator_log.add_argument("--allowed-scope", action="append", default=[])
    operator_log.add_argument("--forbidden-scope", action="append", default=[])
    operator_log.add_argument("--quality-score", type=float, default=0.0)
    operator_log.add_argument("--autonomy-risk-score", type=float, default=0.0)
    operator_log.add_argument("--human-intervention-required", action="store_true")
    operator_log.add_argument("--missing-receipt", action="append", default=[])
    operator_log.add_argument("--reusable-operator-pattern", default="")
    operator_log.add_argument("--design-implication", default="")
    operator_log.add_argument("--followup-task", default="")
    operator_log.add_argument("--log-path", default="")

    handoff = sub.add_parser("emit-handoff", help="print the Polsia handoff path")
    handoff.add_argument("bundle_path")

    materialize = sub.add_parser(
        "materialize-bundle",
        help="stage Chetana, ontology, task, and decision outputs for a bundle",
    )
    materialize.add_argument("bundle_path")
    materialize.add_argument("--ontology-path", default="")
    materialize.add_argument("--task-db-path", default="")
    materialize.add_argument("--decision-log-path", default="")

    args = parser.parse_args(argv)
    if args.cmd == "build-bundle":
        return _cmd_build(args)
    if args.cmd == "validate-bundle":
        return _cmd_validate(args)
    if args.cmd == "refresh-manifest":
        return _cmd_refresh(args)
    if args.cmd == "log-polsia":
        return _cmd_log_polsia(args)
    if args.cmd == "log-operator":
        return _cmd_log_operator(args)
    if args.cmd == "emit-handoff":
        return _cmd_emit_handoff(args)
    if args.cmd == "materialize-bundle":
        return _cmd_materialize(args)
    return 2


def _cmd_build(args: argparse.Namespace) -> int:
    bundle_day = date.fromisoformat(args.bundle_date) if args.bundle_date else None
    path = create_bundle(
        title=args.title,
        slug=args.slug or None,
        root=Path(args.root).expanduser() if args.root else None,
        bundle_date=bundle_day,
        overwrite=args.overwrite,
    )
    print(path)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    result = validate_bundle(Path(args.path))
    if result.valid:
        print(f"valid: {result.bundle_path}")
        for warning in result.warnings:
            print(f"warning: {warning}")
        return 0
    print(f"invalid: {result.bundle_path}", file=sys.stderr)
    for error in result.errors:
        print(f"error: {error}", file=sys.stderr)
    return 2


def _cmd_refresh(args: argparse.Namespace) -> int:
    try:
        manifest = refresh_manifest(Path(args.path))
    except Exception as exc:
        print(f"refresh failed: {exc}", file=sys.stderr)
        return 2
    print(manifest.bundle_path)
    return 0


def _cmd_log_polsia(args: argparse.Namespace) -> int:
    try:
        observation = PolsiaObservation(
            track=args.track,
            prompt_given=args.prompt_given,
            expected_output=args.expected_output,
            polsia_actions_observed=args.action or [],
            agents_or_roles_visible=args.role or [],
            latency_minutes=args.latency_minutes,
            output_paths_or_links=args.output or [],
            quality_score=args.quality_score,
            human_intervention_required=args.human_intervention_required,
            missing_receipts=args.missing_receipt or [],
            reusable_operator_pattern=args.reusable_operator_pattern,
            dharma_swarm_followup_task=args.followup_task,
        )
    except ValidationError as exc:
        print(f"invalid Polsia observation: {exc}", file=sys.stderr)
        return 2
    path = append_observation(
        observation,
        path=Path(args.log_path).expanduser() if args.log_path else None,
    )
    print(path)
    return 0


def _cmd_log_operator(args: argparse.Namespace) -> int:
    try:
        observation = ExternalOperatorObservation(
            operator=args.operator,
            track=args.track,
            venture_cell=args.venture_cell,
            surface=args.surface,
            session_phase=args.session_phase,
            prompt_given=args.prompt_given,
            expected_output=args.expected_output,
            operator_response_summary=args.response_summary,
            actions_observed=args.action or [],
            agents_or_roles_visible=args.role or [],
            artifacts_or_urls=args.artifact or [],
            screenshot_refs=args.screenshot_ref or [],
            capabilities_observed=args.capability or [],
            limitations_observed=args.limitation or [],
            allowed_scope_boundary=args.allowed_scope or [],
            forbidden_scope_boundary=args.forbidden_scope or [],
            quality_score=args.quality_score,
            autonomy_risk_score=args.autonomy_risk_score,
            human_intervention_required=args.human_intervention_required,
            missing_receipts=args.missing_receipt or [],
            reusable_operator_pattern=args.reusable_operator_pattern,
            dharma_swarm_design_implication=args.design_implication,
            followup_task=args.followup_task,
        )
    except ValidationError as exc:
        print(f"invalid external operator observation: {exc}", file=sys.stderr)
        return 2
    path = append_operator_observation(
        observation,
        path=Path(args.log_path).expanduser() if args.log_path else None,
    )
    print(path)
    return 0


def _cmd_emit_handoff(args: argparse.Namespace) -> int:
    bundle_path = Path(args.bundle_path).expanduser().resolve()
    result = validate_bundle(bundle_path)
    if not result.valid:
        for error in result.errors:
            print(f"error: {error}", file=sys.stderr)
        return 2
    path = bundle_path / "polsia_handoff.json"
    print(path)
    return 0


def _cmd_materialize(args: argparse.Namespace) -> int:
    try:
        result = materialize_bundle(
            Path(args.bundle_path),
            ontology_path=Path(args.ontology_path).expanduser() if args.ontology_path else None,
            task_db_path=Path(args.task_db_path).expanduser() if args.task_db_path else None,
            decision_log_path=Path(args.decision_log_path).expanduser()
            if args.decision_log_path
            else None,
        )
    except Exception as exc:
        print(f"materialize failed: {exc}", file=sys.stderr)
        return 2
    for key, value in result.to_dict().items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
