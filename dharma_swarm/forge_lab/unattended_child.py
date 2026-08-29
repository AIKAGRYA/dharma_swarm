"""Isolated child seams and scratch-custody helpers for unattended RSI."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.source_guard import require_execution_source
from dharma_swarm.forge_lab.state_io import content_digest, write_json_exclusive
from dharma_swarm.forge_lab.unattended_receipts import UnattendedError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _run_git(argv: list[str], *, cwd: Path | None = None, timeout: int = 300) -> None:
    result = subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
        env={
            "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin",
            "HOME": os.environ.get("HOME", "/nonexistent"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
        },
    )
    if result.returncode != 0:
        raise UnattendedError("SCRATCH_GIT_FAILED", result.stderr.strip()[:500])


def clone_scratch(
    *,
    source_repo: Path,
    experiment_id: str,
    archive_path: Path,
    category: str,
) -> Path:
    """Clone exact release bytes without writing the immutable source Git dir."""

    from dharma_swarm.evolution_safety import EVOLUTION_MARKER, is_scratch_worktree

    scratch_root = Path(os.environ["DHARMA_EVOLUTION_WORKTREE_ROOT"]).resolve()
    repo = (scratch_root / experiment_id / "repo").resolve()
    if scratch_root not in repo.parents or repo.exists():
        raise UnattendedError("SCRATCH_PATH_UNSAFE", str(repo))
    commit = str(require_execution_source(source_repo)["commit"])
    repo.parent.mkdir(parents=True, exist_ok=False)
    try:
        _run_git(["git", "clone", "--no-hardlinks", "--no-checkout", "--quiet", str(source_repo), str(repo)])
        _run_git(["git", "checkout", "--detach", "--quiet", commit], cwd=repo)
    except Exception:
        if scratch_root in repo.parent.parents:
            shutil.rmtree(repo.parent)
        raise
    marker = {
        "experiment_id": experiment_id,
        "git_base_sha": commit,
        "created_at": _now(),
        "archive_path": str(archive_path),
        "category": category,
        "standalone_clone": True,
    }
    marker_path = repo / EVOLUTION_MARKER
    write_json_exclusive(marker_path, marker)
    ok, _payload, reason = is_scratch_worktree(repo)
    if not ok:
        raise UnattendedError("SCRATCH_MARKER_REFUSED", str(reason))
    return repo


def remove_clone_scratch(*, source_repo: Path, repo: Path, experiment_id: str) -> None:
    del source_repo, experiment_id
    from dharma_swarm.evolution_safety import EVOLUTION_MARKER, is_scratch_worktree

    scratch_root = Path(os.environ["DHARMA_EVOLUTION_WORKTREE_ROOT"]).resolve()
    resolved = repo.resolve()
    ok, _payload, _reason = is_scratch_worktree(resolved)
    if scratch_root not in resolved.parents or not ok or not (resolved / EVOLUTION_MARKER).is_file():
        raise UnattendedError("SCRATCH_REMOVE_REFUSED", str(resolved))
    shutil.rmtree(resolved.parent)


def bounded_child_seams(spec: dict[str, Any], counter: Any):
    """Build seams with exactly one explicit provider dispatch per logical slot."""

    from dharma_swarm.api_keys import bootstrap_runtime_env
    from dharma_swarm.forge_lab import grade_explore
    from dharma_swarm.forge_lab.experiment import Seams
    from dharma_swarm.forge_lab.unattended_explore import (
        PER_CALL_TOKENS,
    )
    from dharma_swarm.forge_lab.taskpack import FORBIDDEN_GOLD_FIELDS, load_taskpack
    from dharma_swarm.forge_v1.forge_v2.taskbed_ledger import allocate_task_ids, task_for_id
    from dharma_swarm.forge_lab.provider_selftest import (
        _probe_model_identity,
        _resolve_selftest_slot,
        _safe_usage,
        _complete_exactly_one_transport,
        _wire_model_for_provider,
    )
    from dharma_swarm.forge_v1.canonical import (
        KIMI_TEMP1,
        _provider_for_slot,
        apply_edit_blocks,
        build_repair_prompt,
        compute_unified_diff,
        parse_edit_blocks,
        parse_full_files,
    )
    from dharma_swarm.models import LLMRequest

    bootstrap_runtime_env()
    base = grade_explore.production_seams()
    original_grade = base.grade_task

    routes = spec["routes"]

    def exact_route(model_id: str) -> tuple[dict[str, Any], Any]:
        route = next(
            (item for item in routes if str(item.get("model_id")) == str(model_id)),
            None,
        )
        if route is None:
            raise UnattendedError("PROVIDER_ROUTE_NOT_ADMITTED", str(model_id))
        slot = _resolve_selftest_slot(str(route.get("route_id") or model_id))
        if slot is None:
            raise UnattendedError("PROVIDER_ROUTE_NOT_EXACT", str(model_id))
        provider_name = str(getattr(slot.provider, "value", slot.provider))
        if provider_name != str(route.get("provider")):
            raise UnattendedError("PROVIDER_ROUTE_NOT_EXACT", str(model_id))
        if _wire_model_for_provider(provider_name, str(slot.model_id)) != str(model_id):
            raise UnattendedError("PROVIDER_ROUTE_NOT_EXACT", str(model_id))
        return route, slot

    def bounded_completion(
        *, label: str, model_id: str, prompt: str, max_tokens: int, timeout_s: int
    ) -> tuple[str, int]:
        counter.consume(label)
        route, slot = exact_route(model_id)
        try:
            provider, wire = _provider_for_slot(slot, timeout_s=timeout_s)
        except Exception:
            counter.record_unverifiable("route_configuration_failed")
            raise
        requested_wire_model = _wire_model_for_provider(str(route["provider"]), str(wire))
        request = LLMRequest(
            model=wire,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=1.0 if model_id in KIMI_TEMP1 else 0.2,
        )
        try:
            response = asyncio.run(
                _complete_exactly_one_transport(
                    provider,
                    request,
                    provider_name=str(route["provider"]),
                    timeout_s=timeout_s,
                    before_dispatch=lambda: counter.transport_attempt(
                        label,
                        provider=str(route["provider"]),
                        model_id=requested_wire_model,
                        pricing=dict(route["pricing"]),
                    ),
                )
            )
        except Exception:
            counter.record_unverifiable("provider_call_failed")
            raise
        usage = _safe_usage(response)
        served_model = str(getattr(response, "model", "") or "")
        requested_identity = _probe_model_identity(requested_wire_model)
        served_identity = _probe_model_identity(served_model)
        if not served_model or requested_identity != served_identity:
            counter.record_unverifiable("served_model_identity_mismatch")
            raise UnattendedError(
                "PROVIDER_IDENTITY_MISMATCH",
                f"requested={requested_identity} served={served_identity or 'missing'}",
            )
        counter.record_response(
            served_model=served_model,
            input_tokens=usage.get("input_tokens", -1),
            output_tokens=usage.get("output_tokens", -1),
            total_tokens=usage.get("total_tokens", -1),
        )
        if not counter.telemetry_valid:
            raise UnattendedError("PROVIDER_USAGE_UNVERIFIABLE", model_id)
        return str(getattr(response, "content", "") or ""), int(usage["total_tokens"])

    def propose_once(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if not args:
            raise UnattendedError("PROVIDER_ROUTE_NOT_ADMITTED", "missing slot")
        slot, inst, ctx = args[:3]
        kwargs["continue_rounds"] = 0
        max_tokens = int(kwargs.get("max_tokens") or 0)
        timeout_s = int(kwargs.get("timeout_s") or 0)
        prompt = build_repair_prompt(inst, ctx)
        extra = str(kwargs.get("extra_instruction") or "")
        if extra:
            prompt = extra + "\n\n" + prompt
        text, tokens = bounded_completion(
            label="candidate_generation",
            model_id=str(slot.model_id),
            prompt=prompt,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )
        edits = parse_edit_blocks(text)
        new_files, error = (
            apply_edit_blocks(ctx, edits) if edits else (parse_full_files(text), None)
        )
        patch = "" if error or (not edits and not new_files) else compute_unified_diff(ctx, new_files)
        return {
            "model": str(slot.model_id),
            "provider": str(getattr(slot.provider, "value", slot.provider)),
            "tokens": tokens,
            "patch": patch,
            "error": error or (None if patch else "no applicable candidate edit"),
            "seconds": 0.0,
            "raw_len": len(text),
        }

    def forbidden_arm(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise UnattendedError("UNBOUNDED_ARM_REFUSED", "unattended lane admits freeform_single only")

    def private_official_grade(
        candidate_task: dict[str, Any], patch: str, *, timeout: int
    ) -> Any:
        """Load sealed harness fields only after candidate generation finishes."""

        from dharma_swarm.forge_lab.taskpack import (
            _image_key,
            _load_official_instances,
            official_source_row_digest,
        )

        task_id = str(candidate_task.get("instance_id") or "")
        try:
            official_rows = _load_official_instances([task_id])
            official = official_rows[0]
        except Exception as exc:
            raise UnattendedError("OFFICIAL_GRADER_TASK_UNAVAILABLE", task_id) from exc
        bindings = {
            "instance_id": task_id,
            "repo": str(candidate_task.get("repo") or ""),
            "base_commit": str(candidate_task.get("base_commit") or ""),
            "image_key": str(candidate_task.get("image_key") or ""),
        }
        observed = {
            "instance_id": str(official.get("instance_id") or ""),
            "repo": str(official.get("repo") or ""),
            "base_commit": str(official.get("base_commit") or ""),
            "image_key": _image_key(official),
        }
        if bindings != observed:
            raise UnattendedError("OFFICIAL_GRADER_TASK_IDENTITY_MISMATCH", task_id)
        if official_source_row_digest(official) != candidate_task.get(
            "official_source_row_digest"
        ):
            raise UnattendedError("OFFICIAL_GRADER_SOURCE_REVISION_MISMATCH", task_id)
        grader_task = {
            **official,
            "official_eligible": True,
            "image_key": bindings["image_key"],
            "local_image_id": candidate_task["local_image_id"],
            "local_image_repo_digests": candidate_task["local_image_repo_digests"],
            "taskpack_digest": candidate_task["taskpack_digest"],
        }
        return original_grade(grader_task, patch, timeout=timeout)

    grade = replace(
        base,
        propose_slot=propose_once,
        self_moa_arm=forbidden_arm,
        verify_chain_arm=forbidden_arm,
        mixed_moa_arm=forbidden_arm,
        grade_task=private_official_grade,
    )
    taskbed_db = Path(spec["state_root"]) / ".dharma" / "forge_v1" / "taskbed.db"

    def state_anchored_allocate(**kwargs: Any) -> dict[str, Any]:
        if kwargs.pop("count", None) != 1:
            raise UnattendedError("TASK_SHAPE", "unattended allocation requires one task")
        return allocate_task_ids(task_ids=[spec["task_id"]], db_path=taskbed_db, **kwargs)

    def state_anchored_pull(task_id: str) -> tuple[dict[str, Any], dict[str, str]]:
        """Return only the sealed candidate view; never reload gold-derived context."""

        if task_id != spec["task_id"]:
            raise UnattendedError("TASK_ID_MISMATCH", task_id)
        try:
            stored = task_for_id(task_id, db_path=taskbed_db)
        except Exception as exc:
            raise UnattendedError("TASKBED_TASK_UNAVAILABLE", task_id) from exc
        task = stored.get("task")
        provenance = stored.get("provenance")
        if not isinstance(task, dict) or not isinstance(provenance, dict):
            raise UnattendedError("TASKBED_TASK_MALFORMED", task_id)
        unsigned = {
            key: value
            for key, value in task.items()
            if key not in {"task_digest", "provenance", "sealed_provenance"}
        }
        manifest_shaped = {
            key: value
            for key, value in task.items()
            if key not in {"provenance", "sealed_provenance"}
        }
        try:
            manifest = load_taskpack(str(provenance["manifest_path"]))
        except Exception as exc:
            raise UnattendedError("TASKPACK_BINDING_INVALID", task_id) from exc
        manifest_task = next(
            (
                row
                for row in manifest["content"]["tasks"]
                if row.get("instance_id") == task_id
            ),
            None,
        )
        valid = bool(
            stored.get("source") == "official_swebench_verified_taskpack"
            and stored.get("taskbed") == "official_swebench_verified_shadow"
            and int(stored.get("active") or 0) == 1
            and task.get("official_eligible") is True
            and task.get("candidate_network_disabled") is True
            and not FORBIDDEN_GOLD_FIELDS.intersection(task)
            and task.get("task_digest") == content_digest(unsigned)
            and task.get("provenance") == provenance
            and task.get("sealed_provenance") == provenance
            and provenance.get("task_digest") == task.get("task_digest")
            and provenance.get("taskpack_digest") == manifest.get("taskpack_digest")
            and manifest_task == manifest_shaped
        )
        if not valid:
            raise UnattendedError("TASKPACK_BINDING_INVALID", task_id)
        candidate_task = dict(manifest_shaped)
        candidate_task["taskpack_digest"] = provenance["taskpack_digest"]
        # An empty context is intentional: deriving target files from the gold
        # patch discloses evaluator information. The candidate receives only
        # the public issue statement and sealed repository/base/image identity.
        return candidate_task, {}

    def bounded_mutation(prompt: str) -> tuple[str, int]:
        text, tokens = bounded_completion(
            label="mutation",
            model_id=str(routes[1]["model_id"]),
            prompt=prompt,
            max_tokens=2_048,
            timeout_s=240,
        )
        child = {
            "arm_kind": "freeform_single",
            "generator_model": routes[0]["model_id"],
            "verifier_model": routes[1]["model_id"],
            "per_call_tokens": PER_CALL_TOKENS,
            "window_chars": 24_000,
            "extra_instruction": str(text or "")[:4_000],
            "notes": "bounded_unattended_mutation_projection",
        }
        return json.dumps(child, sort_keys=True), int(tokens)

    return Seams(
        grade=grade,
        pull_task_context=state_anchored_pull,
        allocate_explore=state_anchored_allocate,
        mutate_complete=bounded_mutation,
        make_worktree=clone_scratch,
        remove_worktree=remove_clone_scratch,
    )


__all__ = ["bounded_child_seams", "clone_scratch", "remove_clone_scratch"]
