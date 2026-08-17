"""Argument orchestration for the session-status CLI.

Orchestration only: parse flags, drive collection (``evidence``), policy
(``readiness``), persistence (``receipt``), and rendering (``render``).
No admission rule lives here.

Writer doctrine: ``WRITER_SCHEMA_DEFAULT`` is the sole source-controlled
schema choice. An ambient ``DHARMA_ONBOARD_WRITER`` that differs from it is
denied and typed. The v2 condition object is always assembled and is what
``--json`` emits, whatever compatible schema is written to disk.

Cache doctrine: the stable core is reused only on a full
input-manifest key match with validated stable digest and unchanged
repository head/identity, and never from a v1/corrupt prior; hard and live
checks always rerun. Every miss carries a typed reason.

Exit doctrine: the process always returns the receipt's true typed exit code.
``--strict`` remains an accepted compatibility no-op for older callers.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from . import (
    evidence,
    killswitch_status,
    nats_status,
    readiness,
    render,
    repository_identity,
)
from .models import ConfigError, RECEIPT_SCHEMA_V1, RECEIPT_SCHEMA_V2
from .receipt import (
    build_input_manifest,
    cache_key,
    compute_delta,
    compute_stable_digest,
    load_receipt,
    receipt_transaction,
    section_fingerprints,
    write_receipt,
)

# Flipped to "v2" under the merged operator D3 record (PR #941). This
# constant is the sole writer seam — ambient overrides that
# differ from it are denied and typed (O3R-B2).
WRITER_SCHEMA_DEFAULT = "v2"

_MANIFEST_CATEGORIES: dict[str, list[str]] = {
    "entry_implementation": [
        "Makefile",
        "scripts/governance/agent_onboard.py",
        "dharma_swarm/operator_core/onboarding/cli.py",
        "dharma_swarm/operator_core/onboarding/evidence.py",
        "dharma_swarm/operator_core/onboarding/killswitch_status.py",
        "dharma_swarm/operator_core/onboarding/nats_status.py",
        "dharma_swarm/operator_core/onboarding/readiness.py",
        "dharma_swarm/operator_core/onboarding/repository_identity.py",
        "dharma_swarm/operator_core/onboarding/receipt.py",
        "dharma_swarm/operator_core/onboarding/render.py",
        "dharma_swarm/operator_core/onboarding/broken_register.py",
        "dharma_swarm/memory_kernel/write_receipts.py",
    ],
    "instruction_custody": [
        "CLAUDE.md",
        "docs/governance/ANTI_SLOP_RULES.md",
        "docs/governance/BUILD_SESSION_ENTRYPOINT.md",
        "docs/governance/CANONICAL_DOC_STACK.md",
        "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md",
        "docs/governance/REPOSITORY_IDENTITY.json",
    ],
    "intent_surface_breakage": [
        "docs/governance/ACTIVE_TRACK.yaml",
        "ACTIVE_SURFACE_MANIFEST.yaml",
        "docs/state/BROKEN_REGISTER.md",
        # Static orientation surfaces: their existence feeds stable_core, so
        # their appearance/disappearance must invalidate cache reuse.
        "foundations/THE_ORGANISM.md",
        "docs/vision_maps/NORTH_STAR.md",
        "docs/MEGAFILE_INDEX.md",
        "INTERFACE_MISMATCH_MAP.md",
    ],
    "dependency_contract": [
        "pyproject.toml",
        "uv.lock",
    ],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="onboard", description=__doc__, add_help=True,
    )
    parser.add_argument("--json", action="store_true", help="deterministic machine output")
    parser.add_argument("--deep", action="store_true", help="detailed view, same verdict")
    parser.add_argument("--net", action="store_true", help="opt-in non-admission PR context")
    parser.add_argument("--no-net", action="store_true", help="no-op alias; default is network-off")
    parser.add_argument("--require-live", action="store_true", help="required host gaps exit 4")
    parser.add_argument("--fast", action="store_true", help="deprecated alias of the compact default")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="deprecated compatibility no-op; truthful exits are always enabled",
    )
    return parser


def _collect_conditions(
    live_state: Mapping[str, Any],
    toolchain: Mapping[str, str],
    orientation: Mapping[str, Any],
    *,
    net: bool,
    probe_errors: Mapping[str, str] | None = None,
    repository_observation: (
        repository_identity.RepositoryIdentityObservation | None
    ) = None,
) -> list[readiness.Condition]:
    conditions: list[readiness.Condition] = []
    if repository_observation is not None:
        status = repository_observation.status
        if status is repository_identity.RepositoryIdentityStatus.CANONICAL:
            conditions.append(readiness.Condition(
                id="repository_identity",
                state="pass",
                condition_class="config",
                reason=repository_observation.reason,
            ))
        elif status is repository_identity.RepositoryIdentityStatus.LEGACY_COMPATIBLE:
            conditions.append(readiness.Condition(
                id="repository_identity",
                state="warn",
                condition_class="config",
                mandatory=False,
                reason=repository_observation.reason,
            ))
        elif status is repository_identity.RepositoryIdentityStatus.STERILE:
            conditions.append(readiness.Condition(
                id="repository_identity",
                state="skipped",
                condition_class="info",
                mandatory=False,
                reason=repository_observation.reason,
            ))
        else:
            conditions.append(readiness.Condition(
                id="repository_identity",
                state="fail",
                condition_class="config",
                reason=repository_observation.reason,
            ))
    errors = {str(k): str(v) for k, v in dict(probe_errors or {}).items() if v}
    status_error = errors.get("status", "")
    if status_error:
        # O3R-B1: an unobservable working tree is typed, never a false clean.
        for condition_id in ("repo_clean", "repo_unconflicted"):
            conditions.append(readiness.Condition(
                id=condition_id,
                state="not_observed",
                condition_class="blocking",
                reason="git status probe failed; state not observed",
            ))
    else:
        conditions.append(readiness.Condition(
            id="repo_clean",
            state="pass" if not live_state.get("dirty") else "fail",
            condition_class="blocking",
            reason="" if not live_state.get("dirty") else "working tree is dirty",
        ))
        conditions.append(readiness.Condition(
            id="repo_unconflicted",
            state="pass" if not live_state.get("conflicted") else "fail",
            condition_class="blocking",
            reason="" if not live_state.get("conflicted") else "merge conflicts present",
        ))
    # Cleanliness/conflict observation is session-critical.  Base distance is
    # only context: detached CI checkouts and local clones legitimately lack
    # ``origin/main``, so an unavailable ahead/behind comparison must stay
    # visible without turning a clean, observed worktree into CONFIG_ERROR.
    config_errors = {
        name: message
        for name, message in errors.items()
        if name != "ahead_behind"
    }
    if config_errors:
        conditions.append(readiness.Condition(
            id="git_state_observed",
            state="fail",
            condition_class="config",
            reason="; ".join(
                f"{name}: {message}"
                for name, message in sorted(config_errors.items())
            )[:200],
        ))
    if "ahead_behind" in errors:
        conditions.append(readiness.Condition(
            id="git_base_distance_observed",
            state="warn",
            condition_class="info",
            mandatory=False,
            reason=(
                "ahead/behind unavailable; worktree status remains observed: "
                f"{errors['ahead_behind']}"
            )[:200],
        ))
    for tool in ("git", "make"):
        present = bool(toolchain.get(tool))
        conditions.append(readiness.Condition(
            id=f"toolchain_{tool}",
            state="pass" if present else "fail",
            condition_class="toolchain",
            reason="" if present else f"{tool} is not on PATH",
        ))
    # Generated portfolio evidence is a deep diagnostic, never a session gate.
    # It is intentionally absent from a sterile clone and remains available in
    # ``live_delta.projection_freshness`` for ``--deep`` without making every
    # clean checkout BLOCKED by construction.
    register = orientation.get("broken_register", {})
    parse_ok = isinstance(register, Mapping) and "error" not in register
    conditions.append(readiness.Condition(
        id="broken_register_parses",
        state="pass" if parse_ok else "fail",
        condition_class="blocking",
        reason="" if parse_ok else str(register.get("error", "parser failed")),
    ))
    if net:
        conditions.append(readiness.Condition(
            id="net_context",
            state="skipped",
            condition_class="info",
            mandatory=False,
            reason="network PR context is outside session-status scope",
        ))
    return conditions


def _evaluate_reuse(
    previous: Mapping[str, Any] | None,
    *,
    prior_corrupt: bool,
    key: str,
    fresh_core: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    """Return ``(reused stable core | None, typed cache-miss reasons)``.

    A hit requires ALL of: an intact v2 prior, a full input-manifest key
    match, a validated stable digest, unchanged repository head and identity,
    and a valid prior core. Anything else is a typed miss; corrupt or poisoned
    priors can never seed it.
    """
    reasons: list[str] = []
    if prior_corrupt:
        reasons.append("prior_corrupt")
        return None, reasons
    if previous is None:
        reasons.append("no_prior_receipt")
        return None, reasons
    if previous.get("schema") != RECEIPT_SCHEMA_V2:
        reasons.append("prior_not_v2")
        return None, reasons
    if reasons:
        return None, reasons
    prior_cache = previous.get("cache")
    if not isinstance(prior_cache, Mapping) or prior_cache.get("key") != key:
        return None, ["manifest_changed"]
    prior_core = previous.get("stable_core")
    if not isinstance(prior_core, dict) or previous.get(
        "stable_digest"
    ) != compute_stable_digest(prior_core):
        return None, ["stable_digest_mismatch"]
    fresh_repo = fresh_core.get("repository", {})
    prior_repo = prior_core.get("repository", {})
    if prior_repo.get("head") != fresh_repo.get("head"):
        return None, ["head_changed"]
    if prior_repo.get("identity") != fresh_repo.get("identity"):
        return None, ["identity_changed"]
    return prior_core, []


def _legacy_v1_payload(now: str, stable_core: Mapping[str, Any]) -> dict[str, Any]:
    """A minimal VALID v1 receipt (loader-validated types; legacy display only)."""
    repository = stable_core.get("repository", {})
    return {
        "schema": RECEIPT_SCHEMA_V1,
        "observed_at": now,
        "authority": "projection_only",
        "repo": dict(repository),
        "work_lanes": {},
        "portfolio": dict(stable_core.get("portfolio", {})),
        "next_items": [],
        "swarm_bulletins": [],
        "broken_register": dict(
            stable_core.get("orientation", {}).get("broken_register", {})
        ),
        "open_prs": [],
        "runtime_truth_packets": [],
    }


def assemble_and_run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args, unknown = parser.parse_known_args(argv)
    conditions: list[readiness.Condition] = []
    if unknown:
        conditions.append(readiness.Condition(
            id="usage_error", state="fail", condition_class="usage",
            reason=f"unknown argument(s): {' '.join(sorted(unknown))}",
        ))
    if args.fast:
        print("note: --fast is deprecated; it maps to the compact default", file=sys.stderr)

    repo_root = evidence.REPO_ROOT
    now = _utc_now()
    repository_observation = repository_identity.observe_repository_identity(
        repo_root, now=now,
    )
    stable_core = evidence.collect_stable_core(repository_observation)
    live_state, probe_errors = evidence.observe_repo_live_state()
    toolchain = evidence.toolchain_versions()
    freshness = evidence.projection_freshness()
    nats_projection = nats_status.collect_nats_substrate_status()
    killswitch_projection = killswitch_status.collect_killswitch_status()
    conditions.extend(_collect_conditions(
        live_state, toolchain, stable_core.get("orientation", {}),
        net=bool(args.net), probe_errors=probe_errors,
        repository_observation=repository_observation,
    ))

    manifest = build_input_manifest(repo_root, _MANIFEST_CATEGORIES)
    key = cache_key(manifest, environment_class=f"py{sys.version_info.major}.{sys.version_info.minor}")

    # An explicitly unsafe receipt path is a configuration error.  Failure to
    # write the default external cache remains visible but cannot make a
    # read-only checkout unusable as a status command.
    previous: dict[str, Any] | None = None
    prior_corrupt = False
    cache_hit = False
    miss_reasons: list[str] = ["no_prior_receipt"]
    persistence_condition: readiness.Condition
    # Sole-writer doctrine (O3R-B2): the on-disk schema comes only from the
    # source-controlled default; a differing ambient override is denied and
    # typed instead of honored.
    writer_schema = WRITER_SCHEMA_DEFAULT
    ambient_writer = os.environ.get("DHARMA_ONBOARD_WRITER")
    if ambient_writer is not None and ambient_writer != WRITER_SCHEMA_DEFAULT:
        conditions.append(readiness.Condition(
            id="writer_override_denied",
            state="fail",
            condition_class="config",
            reason=(
                f"ambient DHARMA_ONBOARD_WRITER={ambient_writer!r} is denied; "
                f"the writer flips only through the source-controlled default "
                f"and stays {WRITER_SCHEMA_DEFAULT!r}"
            ),
        ))
    try:
        # Cache concurrency invariant: the prior read, reuse decision, and
        # the replace must share one lock span, or a concurrent run's replace
        # makes this run's decision stale (PR #942 review finding).
        with receipt_transaction(repo_root) as target:
            if target.exists():
                try:
                    previous = load_receipt(target).payload
                except Exception:
                    prior_corrupt = True
                    conditions.append(readiness.Condition(
                        id="prior_receipt_corrupt", state="fail",
                        condition_class="blocking",
                        reason="existing receipt failed validation; not trusted, not replaced silently",
                    ))
            reused_core, miss_reasons = _evaluate_reuse(
                previous, prior_corrupt=prior_corrupt, key=key,
                fresh_core=stable_core,
            )
            cache_hit = reused_core is not None
            if cache_hit:
                stable_core = reused_core
            if writer_schema == "v2":
                draft = _assemble_v2(
                    now, stable_core, live_state, conditions, manifest, key,
                    freshness, previous, toolchain=toolchain,
                    nats_projection=nats_projection,
                    killswitch_projection=killswitch_projection,
                    require_live=bool(args.require_live),
                    cache_hit=cache_hit, miss_reasons=miss_reasons,
                )
                write_receipt(draft, repo_root=repo_root, presumed_locked=True)
            else:
                write_receipt(
                    _legacy_v1_payload(now, stable_core),
                    repo_root=repo_root, presumed_locked=True,
                )
        persistence_condition = readiness.Condition(
            id="receipt_persisted", state="pass", condition_class="info",
        )
    except ConfigError as exc:
        persistence_condition = readiness.Condition(
            id="receipt_path_invalid", state="fail", condition_class="config",
            reason=str(exc)[:200],
        )
    except OSError as exc:
        persistence_condition = readiness.Condition(
            id="receipt_write_failed", state="warn", condition_class="info",
            mandatory=False,
            reason=(
                "optional cache/diagnostic receipt was not written: "
                f"{type(exc).__name__}: {exc}"
            )[:200],
        )
    conditions.append(persistence_condition)

    receipt_object = _assemble_v2(
        now, stable_core, live_state, conditions, manifest, key,
        freshness, previous, toolchain=toolchain,
        nats_projection=nats_projection,
        killswitch_projection=killswitch_projection,
        require_live=bool(args.require_live),
        cache_hit=cache_hit, miss_reasons=miss_reasons,
    )

    if args.json:
        sys.stdout.write(render.render_json(receipt_object))
    elif args.deep:
        sys.stdout.write(render.render_deep(receipt_object))
    else:
        sys.stdout.write(render.render_compact(receipt_object))

    return int(receipt_object["exit_code"])


def _assemble_v2(
    now: str,
    stable_core: Mapping[str, Any],
    live_state: Mapping[str, Any],
    conditions: Sequence[readiness.Condition],
    manifest: Mapping[str, Any],
    key: str,
    freshness: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
    *,
    toolchain: Mapping[str, str],
    nats_projection: Mapping[str, Any],
    killswitch_projection: Mapping[str, Any],
    require_live: bool,
    cache_hit: bool = False,
    miss_reasons: Sequence[str] | None = None,
) -> dict[str, Any]:
    outcome = readiness.evaluate(conditions, require_live=require_live)
    condition_rows = [c.as_dict() for c in outcome.conditions]
    core = dict(stable_core)
    return {
        "schema": RECEIPT_SCHEMA_V2,
        "authority": "projection_only",
        "observed_at": now,
        "primary_verdict": outcome.verdict,
        "exit_code": outcome.exit_code,
        "stable_core": core,
        "live_delta": {
            "repo_state": dict(live_state),
            "conditions": condition_rows,
            "host_gaps": list(outcome.host_gaps),
            "toolchain": dict(toolchain),
            "projection_freshness": dict(freshness),
        },
        "cache": {
            "key": key,
            "hit": cache_hit,
            "miss_reasons": list(miss_reasons or []),
            "input_manifest": dict(manifest),
            "section_fingerprints": section_fingerprints(manifest),
        },
        "delta": compute_delta(previous, core, condition_rows),
        "legacy_v1": _legacy_v1_payload(now, core),
        "extensions": {
            "nats_substrate": dict(nats_projection),
            "loop_killswitch": dict(killswitch_projection),
        },
        "stable_digest": compute_stable_digest(core),
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return assemble_and_run(argv)
    except ConfigError as exc:
        print(f"CONFIG_ERROR: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "WRITER_SCHEMA_DEFAULT",
    "assemble_and_run",
    "build_parser",
    "main",
]
