#!/usr/bin/env python3
"""Spec §4 warrant parser, validator, and enforcer.

A warrant is the YAML scope contract that bounds every loop run. It declares:
``id``, ``issued_by``, ``authority_level`` (low|medium|high), ``trigger``,
``scope`` (base_ref, head_ref, councils[], prompt_ids[]), ``write_set[]``,
``budget`` (max_tokens, max_wall_clock_min, max_fixes_per_run), ``merge_policy``
(always ``propose_only``), and ``expires_at`` (ISO-8601).

The loop refuses to act outside the warrant. The warrant is re-validated on
every stage entry (a warrant expiring mid-run is refused at the next stage).

Usage:
    python3 scripts/governance/loop/warrant.py validate <path>
    python3 scripts/governance/loop/warrant.py stage-entry <path>
    python3 scripts/governance/loop/warrant.py assert-write-set <path> <file>
    python3 scripts/governance/loop/warrant.py check-budget <path> [--used-fixes N] [--used-tokens N] [--used-wall-clock-min N]

Exit codes:
    0   warrant is valid / the asserted constraint holds
    2   warrant is invalid / expired / refused / a constraint is violated
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

REQUIRED_FIELDS = (
    "id",
    "issued_by",
    "authority_level",
    "trigger",
    "scope",
    "write_set",
    "budget",
    "merge_policy",
    "expires_at",
)

AUTHORITY_LEVELS = ("low", "medium", "high")

REQUIRED_SCOPE_KEYS = ("base_ref", "head_ref", "councils", "prompt_ids")
REQUIRED_BUDGET_KEYS = ("max_tokens", "max_wall_clock_min", "max_fixes_per_run")


class WarrantError(Exception):
    """Base class for all warrant failures."""


class WarrantValidationError(WarrantError):
    """The warrant YAML is structurally invalid (missing field, bad enum, bad policy)."""


class WarrantExpiredError(WarrantError):
    """The warrant has passed its expires_at."""


class WriteSetViolationError(WarrantError):
    """A file outside the warrant's write_set was touched."""


@dataclass
class BudgetResult:
    """Outcome of a runtime budget check."""

    exceeded: bool
    reason: str = ""
    deferred: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"exceeded": self.exceeded, "reason": self.reason, "deferred": self.deferred}


def _parse_expires_at(raw: str) -> datetime:
    """Parse an ISO-8601 timestamp (tolerant of a trailing 'Z')."""
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise WarrantValidationError(f"expires_at is not a valid ISO-8601 timestamp: {raw!r} ({exc})") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class Warrant:
    """A parsed, structurally-validated warrant."""

    id: str
    issued_by: str
    authority_level: str
    trigger: str
    scope: dict
    write_set: list[str]
    budget: dict
    merge_policy: str
    expires_at: datetime
    raw: dict = field(default_factory=dict)

    # --- construction ---

    @classmethod
    def from_dict(cls, data: dict) -> "Warrant":
        """Structurally validate a warrant dict and build a Warrant.

        Raises WarrantValidationError on any structural problem (missing
        required field, invalid authority_level enum, non-propose_only
        merge_policy, malformed scope/budget, bad expires_at).
        """
        if not isinstance(data, dict):
            raise WarrantValidationError(f"warrant must be a mapping, got {type(data).__name__}")

        for field_name in REQUIRED_FIELDS:
            if field_name not in data:
                raise WarrantValidationError(f"missing required field: {field_name}")

        authority_level = data["authority_level"]
        if authority_level not in AUTHORITY_LEVELS:
            raise WarrantValidationError(
                f"authority_level must be one of {AUTHORITY_LEVELS}, got {authority_level!r}"
            )

        merge_policy = data["merge_policy"]
        if merge_policy != "propose_only":
            raise WarrantValidationError(
                f"merge_policy must be 'propose_only', got {merge_policy!r}"
            )

        scope = data["scope"]
        if not isinstance(scope, dict):
            raise WarrantValidationError(f"scope must be a mapping, got {type(scope).__name__}")
        for key in REQUIRED_SCOPE_KEYS:
            if key not in scope:
                raise WarrantValidationError(f"missing required scope field: scope.{key}")
        if not isinstance(scope["councils"], list):
            raise WarrantValidationError("scope.councils must be a list")
        if not isinstance(scope["prompt_ids"], list):
            raise WarrantValidationError("scope.prompt_ids must be a list")

        write_set = data["write_set"]
        if not isinstance(write_set, list):
            raise WarrantValidationError(f"write_set must be a list, got {type(write_set).__name__}")

        budget = data["budget"]
        if not isinstance(budget, dict):
            raise WarrantValidationError(f"budget must be a mapping, got {type(budget).__name__}")
        for key in REQUIRED_BUDGET_KEYS:
            if key not in budget:
                raise WarrantValidationError(f"missing required budget field: budget.{key}")

        expires_at = _parse_expires_at(str(data["expires_at"]))

        return cls(
            id=str(data["id"]),
            issued_by=str(data["issued_by"]),
            authority_level=authority_level,
            trigger=str(data["trigger"]),
            scope=scope,
            write_set=[str(p) for p in write_set],
            budget=budget,
            merge_policy=merge_policy,
            expires_at=expires_at,
            raw=data,
        )

    @classmethod
    def from_yaml(cls, path: Path) -> "Warrant":
        """Load and structurally validate a warrant YAML file."""
        if not path.exists():
            raise WarrantValidationError(f"warrant file not found: {path}")
        try:
            with path.open() as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise WarrantValidationError(f"warrant YAML is unparseable: {exc}") from exc
        if data is None:
            raise WarrantValidationError("warrant file is empty")
        return cls.from_dict(data)

    @classmethod
    def load_and_check(cls, path: Path) -> "Warrant":
        """Load, structurally validate, and check expiry.

        This is the stage-entry re-validation: every stage calls this on entry
        so a warrant expiring mid-run is refused at the next stage.
        """
        warrant = cls.from_yaml(path)
        if warrant.is_expired():
            raise WarrantExpiredError(
                f"warrant {warrant.id!r} expired at {warrant.expires_at.isoformat()}"
            )
        return warrant

    # --- enforcement ---

    def is_expired(self, now: datetime | None = None) -> bool:
        """True if the warrant's expires_at is in the past."""
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current >= self.expires_at

    def assert_write_set(self, path: str) -> None:
        """Raise WriteSetViolationError if ``path`` is not in the write_set.

        A file the Implementer touches must be in the write_set; a violation is
        a hard abort (the caller maps this to exit 2).
        """
        if path in self.write_set:
            return
        raise WriteSetViolationError(
            f"write-set violation: {path!r} is not in warrant {self.id!r} write_set"
        )

    def check_budget(
        self,
        used_fixes: int = 0,
        used_tokens: int = 0,
        used_wall_clock_min: int | float = 0,
    ) -> BudgetResult:
        """Check runtime usage against the warrant budget.

        Returns a BudgetResult. If any limit is exceeded, ``exceeded`` is True
        and ``reason`` names the breached limit. Excess IMPLEMENT findings are
        deferred (the caller is responsible for routing them to DEFER).
        """
        max_fixes = self.budget["max_fixes_per_run"]
        max_tokens = self.budget["max_tokens"]
        max_wall = self.budget["max_wall_clock_min"]

        if used_fixes > max_fixes:
            return BudgetResult(
                exceeded=True,
                reason=f"budget.max_fixes_per_run exceeded: used {used_fixes} > limit {max_fixes}",
                deferred=[f"fix #{i}" for i in range(max_fixes, used_fixes)],
            )
        if used_tokens > max_tokens:
            return BudgetResult(
                exceeded=True,
                reason=f"budget.max_tokens exceeded: used {used_tokens} > limit {max_tokens}",
            )
        if used_wall_clock_min > max_wall:
            return BudgetResult(
                exceeded=True,
                reason=f"budget.max_wall_clock_min exceeded: used {used_wall_clock_min} > limit {max_wall}",
            )
        return BudgetResult(exceeded=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _emit_error(message: str) -> int:
    sys.stderr.write(message + "\n")
    return 2


def _cmd_validate(path: Path) -> int:
    try:
        warrant = Warrant.from_yaml(path)
    except WarrantValidationError as exc:
        return _emit_error(f"warrant validation failed: {exc}")
    if warrant.is_expired():
        return _emit_error(
            f"warrant {warrant.id!r} expired at {warrant.expires_at.isoformat()} — refused"
        )
    sys.stdout.write(f"warrant {warrant.id!r} valid (authority={warrant.authority_level})\n")
    return 0


def _cmd_stage_entry(path: Path) -> int:
    try:
        warrant = Warrant.load_and_check(path)
    except WarrantValidationError as exc:
        return _emit_error(f"warrant validation failed: {exc}")
    except WarrantExpiredError as exc:
        return _emit_error(f"warrant expired — stage entry refused: {exc}")
    sys.stdout.write(f"stage entry ok: warrant {warrant.id!r} valid and not expired\n")
    return 0


def _cmd_assert_write_set(path: Path, file: str) -> int:
    try:
        warrant = Warrant.from_yaml(path)
    except WarrantValidationError as exc:
        return _emit_error(f"warrant validation failed: {exc}")
    try:
        warrant.assert_write_set(file)
    except WriteSetViolationError as exc:
        return _emit_error(str(exc))
    sys.stdout.write(f"ok: {file!r} is within warrant {warrant.id!r} write_set\n")
    return 0


def _cmd_check_budget(
    path: Path,
    used_fixes: int,
    used_tokens: int,
    used_wall_clock_min: float,
) -> int:
    try:
        warrant = Warrant.from_yaml(path)
    except WarrantValidationError as exc:
        return _emit_error(f"warrant validation failed: {exc}")
    result = warrant.check_budget(
        used_fixes=used_fixes,
        used_tokens=used_tokens,
        used_wall_clock_min=used_wall_clock_min,
    )
    if result.exceeded:
        msg = f"budget exceeded — run aborted: {result.reason}"
        if result.deferred:
            msg += f"; deferred: {result.deferred}"
        return _emit_error(msg)
    sys.stdout.write(f"budget ok: warrant {warrant.id!r} within limits\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Parse, validate, and enforce a spec §4 warrant YAML.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="structurally validate a warrant and check expiry")
    p_validate.add_argument("path", help="path to the warrant YAML file")

    p_stage = sub.add_parser("stage-entry", help="re-validate the warrant on stage entry (load_and_check)")
    p_stage.add_argument("path", help="path to the warrant YAML file")

    p_writeset = sub.add_parser("assert-write-set", help="assert a file is within the warrant write_set")
    p_writeset.add_argument("path", help="path to the warrant YAML file")
    p_writeset.add_argument("file", help="the file path to check against write_set")

    p_budget = sub.add_parser("check-budget", help="check runtime usage against the warrant budget")
    p_budget.add_argument("path", help="path to the warrant YAML file")
    p_budget.add_argument("--used-fixes", type=int, default=0)
    p_budget.add_argument("--used-tokens", type=int, default=0)
    p_budget.add_argument("--used-wall-clock-min", type=float, default=0.0)

    args = parser.parse_args(argv)

    if args.command == "validate":
        return _cmd_validate(Path(args.path))
    if args.command == "stage-entry":
        return _cmd_stage_entry(Path(args.path))
    if args.command == "assert-write-set":
        return _cmd_assert_write_set(Path(args.path), args.file)
    if args.command == "check-budget":
        return _cmd_check_budget(
            Path(args.path),
            used_fixes=args.used_fixes,
            used_tokens=args.used_tokens,
            used_wall_clock_min=args.used_wall_clock_min,
        )
    return 2


if __name__ == "__main__":
    sys.exit(main())
