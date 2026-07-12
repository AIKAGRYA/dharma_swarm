"""Argument orchestration for the one-door onboarding CLI.

Orchestration only: parse flags, drive collection (``evidence``), policy
(``readiness``), persistence (``receipt``), and rendering (``render``).
No admission rule lives here.

Writer doctrine (spec §3.3): the on-disk receipt stays **v1** until the D3
fleet-reader inventory is recorded; ``WRITER_SCHEMA_DEFAULT`` is the one flag
that flips after D3.  The v2 condition object is always assembled and is what
``--json`` emits, whatever the on-disk schema (spec §2.2).

Exit doctrine (spec §WP-O3 / O3-B11): before WP-O5, strict verdict exits are
reachable only through ``--strict`` / ``DHARMA_ONBOARD_STRICT=1``.  The legacy
default keeps exit 0 for everything except usage errors, but the receipt and
JSON always carry the true verdict and true exit code.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import evidence, readiness, render
from .models import ConfigError, RECEIPT_SCHEMA_V1, RECEIPT_SCHEMA_V2
from .receipt import (
    build_input_manifest,
    cache_key,
    compute_delta,
    compute_stable_digest,
    load_receipt,
    receipt_path,
    section_fingerprints,
    write_receipt,
)

# Flipped to "v2" only after the operator records D3 (spec §3.3 step 4).
WRITER_SCHEMA_DEFAULT = "v1"

_MANIFEST_CATEGORIES: dict[str, list[str]] = {
    "entry_implementation": [
        "Makefile",
        "scripts/governance/agent_onboard.py",
        "dharma_swarm/operator_core/onboarding/cli.py",
        "dharma_swarm/operator_core/onboarding/evidence.py",
        "dharma_swarm/operator_core/onboarding/readiness.py",
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
    ],
    "intent_surface_breakage": [
        "docs/governance/ACTIVE_TRACK.yaml",
        "ACTIVE_SURFACE_MANIFEST.yaml",
        "docs/state/BROKEN_REGISTER.md",
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
    parser.add_argument("--packet", help="Session Entry Packet path to validate and bind")
    parser.add_argument("--fast", action="store_true", help="deprecated alias of the compact default")
    parser.add_argument("--strict", action="store_true", help="strict verdict exits (pre-WP-O5 opt-in)")
    return parser


def _load_packet(path_text: str) -> tuple[dict[str, Any], list[readiness.Condition]]:
    """Validate and bind the Session Entry Packet; never a preflight substitute."""
    from .contract import packet_digest, parse_work_packet

    conditions: list[readiness.Condition] = []
    try:
        payload = json.loads(Path(path_text).read_text(encoding="utf-8"))
        packet = parse_work_packet(payload)
        digest = packet_digest(payload)
    except (OSError, ValueError) as exc:
        conditions.append(readiness.Condition(
            id="packet_invalid", state="fail", condition_class="config",
            reason=f"{type(exc).__name__}: {exc}"[:200],
        ))
        return {}, conditions
    conditions.append(readiness.Condition(
        id="packet_bound", state="pass", condition_class="info",
        reason=f"packet {packet.id}",
    ))
    entry = packet.session_entry
    return {
        "id": packet.id,
        "digest": digest,
        "track": entry.active_track if entry else "",
        "owner": entry.owner if entry else "",
        "allowed_files": list(packet.allowed_files),
        "forbidden_files": list(packet.forbidden_files),
    }, conditions


def _collect_conditions(
    live_state: Mapping[str, Any],
    toolchain: Mapping[str, str],
    freshness: Mapping[str, Any],
    orientation: Mapping[str, Any],
    *,
    net: bool,
) -> list[readiness.Condition]:
    conditions: list[readiness.Condition] = []
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
    for tool in ("git", "make"):
        present = bool(toolchain.get(tool))
        conditions.append(readiness.Condition(
            id=f"toolchain_{tool}",
            state="pass" if present else "fail",
            condition_class="toolchain",
            reason="" if present else f"{tool} is not on PATH",
        ))
    for rel, row in freshness.items():
        if not isinstance(row, Mapping):
            continue
        if not row.get("present"):
            state, reason = "fail", "generated projection missing; run its owner command"
        elif row.get("stale"):
            state, reason = "fail", "generated projection older than its TTL; run its owner command"
        else:
            state, reason = "pass", ""
        conditions.append(readiness.Condition(
            id="active_track_projection_fresh",
            state=state, condition_class="blocking", reason=reason,
        ))
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
            reason="non-admission PR context deferred to a later WP-O3 slice",
        ))
    return conditions


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
    strict = bool(args.strict or os.environ.get("DHARMA_ONBOARD_STRICT") == "1")

    packet_block: dict[str, Any] = {}
    if args.packet:
        packet_block, packet_conditions = _load_packet(args.packet)
        conditions.extend(packet_conditions)

    stable_core = evidence.collect_stable_core(packet=packet_block or None)
    live_state = evidence.repo_live_state()
    toolchain = evidence.toolchain_versions()
    freshness = evidence.projection_freshness()
    conditions.extend(_collect_conditions(
        live_state, toolchain, freshness, stable_core.get("orientation", {}),
        net=bool(args.net),
    ))

    manifest = build_input_manifest(repo_root, _MANIFEST_CATEGORIES)
    key = cache_key(manifest, environment_class=f"py{sys.version_info.major}.{sys.version_info.minor}")

    # Receipt persistence is an admission requirement, evaluated before policy.
    now = _utc_now()
    previous: dict[str, Any] | None = None
    persistence_condition: readiness.Condition
    writer_schema = os.environ.get("DHARMA_ONBOARD_WRITER", WRITER_SCHEMA_DEFAULT)
    try:
        target = receipt_path(repo_root)
        if target.exists():
            try:
                previous = load_receipt(target).payload
            except Exception:
                conditions.append(readiness.Condition(
                    id="prior_receipt_corrupt", state="fail",
                    condition_class="blocking",
                    reason="existing receipt failed validation; not trusted, not replaced silently",
                ))
        if writer_schema == "v2":
            draft = _assemble_v2(
                now, stable_core, live_state, conditions, manifest, key,
                freshness, previous, toolchain=toolchain,
                require_live=bool(args.require_live),
            )
            write_receipt(draft, repo_root=repo_root)
        else:
            write_receipt(_legacy_v1_payload(now, stable_core), repo_root=repo_root)
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
            id="receipt_write_failed", state="fail", condition_class="blocking",
            reason=f"{type(exc).__name__}: {exc}"[:200],
        )
    conditions.append(persistence_condition)

    receipt_object = _assemble_v2(
        now, stable_core, live_state, conditions, manifest, key,
        freshness, previous, toolchain=toolchain,
        require_live=bool(args.require_live),
    )

    if args.json:
        sys.stdout.write(render.render_json(receipt_object))
    elif args.deep:
        sys.stdout.write(render.render_deep(receipt_object))
    else:
        sys.stdout.write(render.render_compact(receipt_object))

    true_exit = int(receipt_object["exit_code"])
    if strict:
        return true_exit
    # Legacy pre-WP-O5 contract: only usage errors escape exit 0.  The verdict
    # and true exit stay visible in the receipt and every rendered view.
    return true_exit if true_exit == 2 else 0


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
    require_live: bool,
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
            # Groundwork only: manifest/key/fingerprints are real, but no
            # static-section reuse happens until the §3.2 adversarial matrix
            # is fully in place.  hit stays honestly false.
            "hit": False,
            "miss_reasons": ["section_reuse_not_yet_enabled"],
            "input_manifest": dict(manifest),
            "section_fingerprints": section_fingerprints(manifest),
        },
        "delta": compute_delta(previous, core, condition_rows),
        "legacy_v1": _legacy_v1_payload(now, core),
        "extensions": {},
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
