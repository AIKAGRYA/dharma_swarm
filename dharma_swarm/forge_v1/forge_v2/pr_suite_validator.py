"""FAIL_TO_PASS validator for harvested post-cutoff PR-suite candidates."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from . import pr_suite_execution as execution
from .fresh_task_oracle import read_manifest
from .pr_suite_execution import CommandExecutor, ExecutionProfile
from .signals import canonical_sha256
from .pr_suite_validator_runtime import (
    BASE_OUTCOME_FAILED,
    BASE_OUTCOME_INCONCLUSIVE_NO_RUN,
    BASE_OUTCOME_INCONCLUSIVE_TIMEOUT,
    DEFAULT_RECEIPT_ROOT,
    DEFAULT_TEST_COMMAND_TEMPLATE,
    SCHEMA_VERSION,
    CommandResult as _CommandResult,
    _checkout_ref,
    _clone_repo,
    _materialize_fixed_test,
    _repo_url_for_row,
    _resolve_base_and_fixed,
    _run,
    _write_json,
    candidate_targets,
    classify_base_outcome,
    now_stamp,
    write_jsonl,
)

CommandResult = _CommandResult

def validate_candidate(
    row: dict[str, Any],
    *,
    work_root: Path,
    receipt_root: Path,
    test_command_template: str = DEFAULT_TEST_COMMAND_TEMPLATE,
    python: str = sys.executable,
    timeout_seconds: int = 120,
    local_repo_root: Path | None = None,
    keep_workdir: bool = False,
    use_merge_parent_base: bool = True,
    setup_command_template: str = "",
    setup_timeout_seconds: int | None = None,
    execution_profile: ExecutionProfile | Path | str | None = None,
    receipt_signing_key: Ed25519PrivateKey | None = None,
    receipt_signer_key_id: str | None = None,
) -> dict[str, Any]:
    """Validate one harvested PR-suite row and write a receipt."""

    raw = dict(row)
    task_hint = str(raw.get("task_id") or raw.get("instance_id") or raw.get("pr_number") or "candidate")
    row_sha = canonical_sha256(raw)
    run_id = f"pr_suite_ftp_{now_stamp()}_{time.time_ns()}_{row_sha[:12]}"
    row_work_root = work_root.expanduser() / run_id
    checkout = row_work_root / "repo"
    receipt_path = receipt_root.expanduser() / f"{run_id}.json"

    commands: list[dict[str, Any]] = []
    target_results: list[dict[str, Any]] = []
    blockers: list[str] = []
    validated_targets: list[str] = []
    resolved_refs: dict[str, str] = {}
    status = "fail_to_pass_validation_failed"
    repo_url = ""
    started_at = now_stamp()
    executor: CommandExecutor | None = None
    signer: Ed25519PrivateKey | None = None
    signer_key_id = ""

    try:
        signer, signer_key_id = execution.resolve_validator_signer(
            receipt_signing_key,
            receipt_signer_key_id,
        )
        targets = candidate_targets(raw)
        if not targets:
            blockers.append("missing_candidate_test_targets")
            raise ValueError("candidate row has no validator_targets/test_targets/test_files")
        for target in targets:
            execution.validated_target_path(target, checkout)

        repo_url = _repo_url_for_row(raw, local_repo_root=local_repo_root)
        source_roots = [Path(repo_url)] if Path(repo_url).expanduser().exists() else []
        executor = execution.build_executor(
            profile=execution_profile,
            workspace_root=row_work_root,
            source_roots=source_roots,
            total_timeout_seconds=timeout_seconds,
        )
        execution.require_command_contract(
            executor.profile,
            test_command_template=test_command_template,
            setup_command_template=setup_command_template,
            python=python,
        )
        clone_result = _clone_repo(
            repo_url,
            checkout,
            timeout_seconds=timeout_seconds,
            executor=executor,
        )
        commands.append({"phase": "clone", **clone_result.to_receipt()})
        if not clone_result.passed:
            blockers.append("clone_failed")
            raise RuntimeError("git clone failed")

        _, _, resolved_refs = _resolve_base_and_fixed(
            checkout,
            raw,
            use_merge_parent_base=use_merge_parent_base,
            timeout_seconds=timeout_seconds,
            executor=executor,
        )

        for target in targets:
            setup_argv = executor.setup_argv(cwd=checkout)
            effective_setup_timeout = (
                int(setup_timeout_seconds) if setup_timeout_seconds is not None else max(timeout_seconds, 600)
            )
            base_checkout_commands = _checkout_ref(
                checkout,
                resolved_refs["base_sha"],
                timeout_seconds=timeout_seconds,
                executor=executor,
            )
            commands.extend({"phase": "checkout_base", **result.to_receipt()} for result in base_checkout_commands)
            if not all(result.passed for result in base_checkout_commands):
                blockers.append("base_checkout_failed")
                break
            materialize_result = _materialize_fixed_test(
                checkout,
                fixed_ref=resolved_refs["fixed_sha"],
                target=target,
                timeout_seconds=timeout_seconds,
                executor=executor,
            )
            commands.append({"phase": "materialize_fixed_test_on_base", "target": target, **materialize_result.to_receipt()})
            if not materialize_result.passed:
                blockers.append("fixed_test_materialization_failed")
                break
            if setup_argv is not None:
                base_setup = _run(
                    setup_argv,
                    cwd=checkout,
                    timeout_seconds=effective_setup_timeout,
                    executor=executor,
                )
                commands.append({"phase": "setup_base", "target": target, **base_setup.to_receipt()})
                if not base_setup.passed:
                    blocker = f"base_setup_failed:{target}"
                    if blocker not in blockers:
                        blockers.append(blocker)
                    break
            base_command = executor.test_argv(cwd=checkout, targets=[target])
            base_result = _run(
                base_command,
                cwd=checkout,
                timeout_seconds=timeout_seconds,
                executor=executor,
            )
            commands.append({"phase": "test_base", "target": target, **base_result.to_receipt()})

            fixed_checkout_commands = _checkout_ref(
                checkout,
                resolved_refs["fixed_sha"],
                timeout_seconds=timeout_seconds,
                executor=executor,
            )
            commands.extend({"phase": "checkout_fixed", **result.to_receipt()} for result in fixed_checkout_commands)
            if not all(result.passed for result in fixed_checkout_commands):
                blockers.append("fixed_checkout_failed")
                break
            if setup_argv is not None:
                fixed_setup = _run(
                    setup_argv,
                    cwd=checkout,
                    timeout_seconds=effective_setup_timeout,
                    executor=executor,
                )
                commands.append({"phase": "setup_fixed", "target": target, **fixed_setup.to_receipt()})
                if not fixed_setup.passed:
                    blocker = f"fixed_setup_failed:{target}"
                    if blocker not in blockers:
                        blockers.append(blocker)
                    break
            fixed_command = executor.test_argv(cwd=checkout, targets=[target])
            fixed_result = _run(
                fixed_command,
                cwd=checkout,
                timeout_seconds=timeout_seconds,
                executor=executor,
            )
            commands.append({"phase": "test_fixed", "target": target, **fixed_result.to_receipt()})

            base_outcome = classify_base_outcome(base_result)
            base_failed = base_outcome == BASE_OUTCOME_FAILED
            target_state = {
                "target": target,
                "base_returncode": base_result.returncode,
                "fixed_returncode": fixed_result.returncode,
                "base_outcome": base_outcome,
                "base_failed": base_failed,
                "fixed_passed": fixed_result.passed,
                "validated_fail_to_pass": base_failed and fixed_result.passed,
            }
            target_results.append(target_state)
            if target_state["validated_fail_to_pass"]:
                validated_targets.append(target)
            elif base_outcome in {
                BASE_OUTCOME_INCONCLUSIVE_TIMEOUT,
                BASE_OUTCOME_INCONCLUSIVE_NO_RUN,
            }:
                # The base test never actually ran to a real verdict; surface it
                # explicitly so a non-run is never silently read as a regression.
                blocker = f"base_test_inconclusive:{target}:{base_outcome}"
                if blocker not in blockers:
                    blockers.append(blocker)

        if validated_targets:
            status = "fail_to_pass_validated"
        elif "base_checkout_failed" not in blockers and "fixed_checkout_failed" not in blockers:
            blockers.append("no_targets_failed_on_base_and_passed_on_fixed")
    except Exception as exc:  # noqa: BLE001 - receipt-first validator; failures become evidence.
        if isinstance(exc, execution.IsolationUnavailable):
            blockers.append("isolation_unavailable")
        elif isinstance(exc, execution.ProfileTampered):
            blockers.append("execution_profile_tampered")
        elif isinstance(exc, execution.UnsafeTargetPath):
            blockers.append("unsafe_test_target")
        if not blockers:
            blockers.append(f"{type(exc).__name__}: {exc}")

    source_binding = {
        "source_row_sha256": row_sha,
        "task_hint": task_hint,
        "repo": raw.get("repo") or raw.get("repository") or "",
        "repository_locators": {
            key: raw.get(key)
            for key in ("repo_path", "clone_url", "repo_url", "local_repo")
            if raw.get(key) is not None
        },
        "pr_number": raw.get("pr_number"),
        "candidate_targets": candidate_targets(raw),
        "resolved_refs": resolved_refs,
    }
    receipt = {
        "schema": SCHEMA_VERSION,
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": now_stamp(),
        "status": status,
        "task_hint": task_hint,
        "row_sha256": row_sha,
        "source_binding": source_binding,
        "repo": raw.get("repo") or raw.get("repository") or "",
        "repo_url": execution.redact_secret_text(repo_url),
        "checkout_path": str(checkout) if keep_workdir else "",
        "kept_workdir": keep_workdir,
        "candidate_targets": candidate_targets(raw),
        "validated_fail_to_pass": validated_targets,
        "target_results": target_results,
        "resolved_refs": resolved_refs,
        "caller_claimed_contamination_state": raw.get("contamination_state"),
        "contamination_state_trusted": False,
        "test_command_template": test_command_template,
        "setup_command_template": str(setup_command_template or ""),
        "execution_profile": executor.profile.to_mapping() if executor is not None else {},
        "execution_profile_sha256": executor.profile.sha256 if executor is not None else "",
        "commands": commands,
        "blockers": blockers,
    }
    if signer is not None:
        receipt = execution.sign_validator_receipt(
            receipt,
            signing_key=signer,
            key_id=signer_key_id,
            nonce=run_id,
        )
    else:
        if "validator_receipt_auth_unavailable" not in receipt["blockers"]:
            receipt["blockers"].append("validator_receipt_auth_unavailable")
        receipt["status"] = "fail_to_pass_validation_failed"
        status = receipt["status"]
        validated_targets = []
        receipt["validated_fail_to_pass"] = []
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    _write_json(receipt_path, receipt)

    output_row = dict(raw)
    output_row["validation_schema"] = SCHEMA_VERSION
    output_row["validation_state"] = status
    output_row["requires_fail_to_pass_validation"] = status != "fail_to_pass_validated"
    output_row["fail_to_pass"] = list(validated_targets)
    output_row["validation_receipt"] = str(receipt_path)
    output_row["validation_receipt_sha256"] = receipt["receipt_sha256"]
    output_row["validation_source_row_sha256"] = row_sha
    output_row["validation_task_hint"] = task_hint
    output_row["validation_execution_profile_sha256"] = (
        executor.profile.sha256 if executor is not None else ""
    )
    output_row["validated_base_sha"] = resolved_refs.get("base_sha", "")
    output_row["validated_fixed_sha"] = resolved_refs.get("fixed_sha", "")
    output_row["validator_blockers"] = list(blockers)

    if not keep_workdir:
        shutil.rmtree(row_work_root, ignore_errors=True)

    return {
        "schema": SCHEMA_VERSION,
        "status": status,
        "row_sha256": row_sha,
        "task_hint": task_hint,
        "validated": bool(validated_targets),
        "validated_targets": validated_targets,
        "blockers": blockers,
        "receipt": str(receipt_path),
        "receipt_sha256": receipt["receipt_sha256"],
        "row": output_row,
    }


def validate_rows(
    rows: Iterable[dict[str, Any]],
    *,
    work_root: Path,
    receipt_root: Path,
    test_command_template: str = DEFAULT_TEST_COMMAND_TEMPLATE,
    python: str = sys.executable,
    timeout_seconds: int = 120,
    local_repo_root: Path | None = None,
    keep_workdir: bool = False,
    include_failed: bool = False,
    use_merge_parent_base: bool = True,
    setup_command_template: str = "",
    setup_timeout_seconds: int | None = None,
    execution_profile: ExecutionProfile | Path | str | None = None,
    receipt_signing_key: Ed25519PrivateKey | None = None,
    receipt_signer_key_id: str | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    output_rows: list[dict[str, Any]] = []
    for row in rows:
        result = validate_candidate(
            dict(row),
            work_root=work_root,
            receipt_root=receipt_root,
            test_command_template=test_command_template,
            python=python,
            timeout_seconds=timeout_seconds,
            local_repo_root=local_repo_root,
            keep_workdir=keep_workdir,
            use_merge_parent_base=use_merge_parent_base,
            setup_command_template=setup_command_template,
            setup_timeout_seconds=setup_timeout_seconds,
            execution_profile=execution_profile,
            receipt_signing_key=receipt_signing_key,
            receipt_signer_key_id=receipt_signer_key_id,
        )
        results.append({key: value for key, value in result.items() if key != "row"})
        if result["validated"] or include_failed:
            output_rows.append(dict(result["row"]))
    return {
        "schema": SCHEMA_VERSION,
        "input_count": len(results),
        "validated_count": sum(1 for result in results if result["validated"]),
        "failed_count": sum(1 for result in results if not result["validated"]),
        "output_count": len(output_rows),
        "output_rows": output_rows,
        "results": results,
        "receipt_root": str(receipt_root),
        "work_root": str(work_root),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate PR-suite candidates into explicit FAIL_TO_PASS rows")
    parser.add_argument("--manifest", required=True, help="Input JSON/JSONL candidate manifest from pr_suite_harvester")
    parser.add_argument("--out", required=True, help="Output JSONL manifest for fresh_task_oracle")
    parser.add_argument("--receipt-root", default=str(DEFAULT_RECEIPT_ROOT))
    parser.add_argument("--work-root", default="", help="Isolated checkout root; default uses a temporary directory")
    parser.add_argument("--local-repo-root", default="", help="Optional local mirror root used before GitHub clone URLs")
    parser.add_argument("--test-command-template", default=DEFAULT_TEST_COMMAND_TEMPLATE)
    parser.add_argument(
        "--setup-command-template",
        default="",
        help=(
            "Optional environment provisioning command rendered per checkout before "
            "the base and fixed test runs, e.g. '{python} -m pip install -e .'. "
            "Empty (default) preserves the historical bare-clone behaviour."
        ),
    )
    parser.add_argument(
        "--setup-timeout-seconds",
        type=int,
        default=0,
        help="Timeout for the setup command; 0 uses max(timeout_seconds, 600).",
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--execution-profile",
        default="",
        help="Digest-bound Docker/Podman execution profile; required for execution.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--keep-workdir", action="store_true")
    parser.add_argument("--include-failed", action="store_true", help="Also write failed validation rows to --out")
    parser.add_argument("--no-merge-parent-base", action="store_true", help="Use row base_sha instead of merge_commit_sha^1")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = read_manifest(Path(args.manifest).expanduser())
    receipt_root = Path(args.receipt_root).expanduser()
    local_repo_root = Path(args.local_repo_root).expanduser() if args.local_repo_root else None
    setup_timeout = args.setup_timeout_seconds or None
    profile = args.execution_profile or None

    if args.work_root or args.keep_workdir:
        work_root = Path(args.work_root).expanduser() if args.work_root else receipt_root / "workdirs"
        work_root.mkdir(parents=True, exist_ok=True)
        summary = validate_rows(
            rows,
            work_root=work_root,
            receipt_root=receipt_root,
            test_command_template=args.test_command_template,
            python=args.python,
            timeout_seconds=args.timeout_seconds,
            local_repo_root=local_repo_root,
            keep_workdir=args.keep_workdir,
            include_failed=args.include_failed,
            use_merge_parent_base=not args.no_merge_parent_base,
            setup_command_template=args.setup_command_template,
            setup_timeout_seconds=setup_timeout,
            execution_profile=profile,
        )
    else:
        with tempfile.TemporaryDirectory(prefix="forge-pr-suite-validator-") as temp:
            summary = validate_rows(
                rows,
                work_root=Path(temp),
                receipt_root=receipt_root,
                test_command_template=args.test_command_template,
                python=args.python,
                timeout_seconds=args.timeout_seconds,
                local_repo_root=local_repo_root,
                keep_workdir=args.keep_workdir,
                include_failed=args.include_failed,
                use_merge_parent_base=not args.no_merge_parent_base,
                setup_command_template=args.setup_command_template,
                setup_timeout_seconds=setup_timeout,
                execution_profile=profile,
            )

    write_jsonl(Path(args.out).expanduser(), list(summary["output_rows"]))
    printable = {key: value for key, value in summary.items() if key != "output_rows"}
    printable["out"] = args.out
    if args.json:
        print(json.dumps(printable, indent=2, sort_keys=True, default=str))
    else:
        print(
            "FORGE_PR_SUITE_FAIL_TO_PASS_VALIDATED "
            f"validated={summary['validated_count']} failed={summary['failed_count']} out={args.out}"
        )
    return 0 if summary["validated_count"] > 0 or not rows else 1


__all__ = [
    "DEFAULT_TEST_COMMAND_TEMPLATE",
    "SCHEMA_VERSION",
    "candidate_targets",
    "validate_candidate",
    "validate_rows",
    "write_jsonl",
]


if __name__ == "__main__":
    raise SystemExit(main())
