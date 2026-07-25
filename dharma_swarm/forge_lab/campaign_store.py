"""Durable, fenced SQLite authority store for governed Forge campaigns."""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping

from .campaign_contract import (
    CampaignContractError,
    content_digest,
    validate_manifest,
)
from .campaign_store_schema import (
    LEASE_MODES as _MODES,
    SCHEMA_SQL,
    STATES as _STATES,
    StoreError,
    action_receipt as _action_receipt,
    action_replay as _replay,
    append_event as _event,
    assert_executor_enabled as _executor_enabled,
    assert_fence as _fence,
    assert_holder as _holder,
    assert_powered as _powered,
    campaign_row as _campaign,
    format_time as _format,
    identifier as _identifier,
    json_object as _object,
    parse_time as _time,
    project_campaign as _project,
    require_transition,
    save_action as _save_action,
    text as _text,
)

STORE_SCHEMA = "forge_lab.campaign_store.v1"


class CampaignStore:
    """SQLite WAL store below an explicit canonical/test state root."""

    def __init__(
        self,
        root: Path | str,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.state_root = Path(root)
        if not self.state_root.is_absolute():
            raise StoreError("STATE_ROOT_NOT_ABSOLUTE", "state root must be absolute")
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.root = self.state_root / ".dharma" / "forge_lab" / "campaigns"
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "control.sqlite3"
        self._initialize()

    def create_campaign(
        self, manifest: Mapping[str, Any], *, request_id: str, actor: str
    ) -> dict[str, Any]:
        request_id, actor = _identifier(request_id), _identifier(actor)
        try:
            item = validate_manifest(manifest)
        except CampaignContractError as exc:
            raise StoreError(exc.code, str(exc)) from exc
        campaign, md = item["campaign_name"], item["manifest_digest"]
        claim = content_digest({"action": "create", "actor": actor, "manifest": md})
        with self._write() as db:
            replay = _replay(db, campaign, request_id, claim)
            if replay:
                return replay
            old = db.execute(
                "SELECT manifest_digest FROM campaigns WHERE campaign_id=?", (campaign,)
            ).fetchone()
            if old:
                code = "CAMPAIGN_ALREADY_EXISTS"
                if old["manifest_digest"] != md:
                    code = "CAMPAIGN_MANIFEST_CONFLICT"
                raise StoreError(code, f"campaign {campaign} is already reserved")
            observed = self._observed()
            now, limits = _format(observed), item["limits"]
            db.execute(
                """INSERT INTO campaigns(
                campaign_id,manifest_digest,manifest_json,state,created_at,updated_at,
                attempt_budget,token_limit,usd_limit,request_limit,deadline)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (campaign, md, _text(item), "CREATED", now, now,
                 item["stages"]["primary"]["primary_attempts"],
                 limits["total_tokens"], limits["total_usd_micros"],
                 limits["total_requests"], limits["deadline_utc"]),
            )
            db.execute(
                """INSERT INTO executor_fuses(
                campaign_id,state,reason,updated_at) VALUES(?,?,?,?)""",
                (
                    campaign,
                    "closed",
                    "GOVERNED_EXECUTOR_NOT_IMPLEMENTED",
                    now,
                ),
            )
            event = _event(
                db, campaign, "campaign.created", request_id, actor, None, "CREATED",
                None, {"manifest_digest": md}, recorded_at=now,
            )
            receipt = _action_receipt(
                campaign,
                request_id,
                "create",
                actor,
                md,
                None,
                "CREATED",
                event,
                recorded_at=now,
            )
            _save_action(db, campaign, request_id, claim, receipt)
            return receipt

    def get_campaign(self, campaign_id: str) -> dict[str, Any]:
        with self._read() as db:
            return _project(_campaign(db, _identifier(campaign_id)))

    def list_campaigns(self, state: str | None = None) -> list[dict[str, Any]]:
        if state is not None and state not in _STATES:
            raise StoreError("INVALID_STATE", f"unknown campaign state {state!r}")
        sql, args = "SELECT * FROM campaigns", ()
        if state:
            sql, args = f"{sql} WHERE state=?", (state,)
        with self._read() as db:
            return [_project(row) for row in db.execute(
                f"{sql} ORDER BY created_at,campaign_id", args
            ).fetchall()]

    def events(self, campaign_id: str, after: int = 0) -> list[dict[str, Any]]:
        campaign = _identifier(campaign_id)
        if not isinstance(after, int) or after < 0:
            raise StoreError("INVALID_EVENT_SEQUENCE", "after must be nonnegative")
        with self._read() as db:
            _campaign(db, campaign)
            rows = db.execute(
                """SELECT event_json FROM events WHERE campaign_id=?
                AND sequence>? ORDER BY sequence""", (campaign, after)
            ).fetchall()
            return [_object(row["event_json"]) for row in rows]

    def active_leases(self) -> list[dict[str, Any]]:
        """Return unexpired authoritative leases for deployment guards."""
        observed = _format(self._observed())
        with self._read() as db:
            rows = db.execute(
                """SELECT campaign_id,manifest_digest,active_fence,lease_holder,
                lease_mode,lease_expires FROM campaigns
                WHERE active_fence IS NOT NULL AND lease_expires>? ORDER BY campaign_id""",
                (observed,),
            ).fetchall()
            return [dict(row) for row in rows]

    def has_active_lease(self) -> bool:
        return bool(self.active_leases())

    def apply_action(
        self, campaign_id: str, *, request_id: str, action: str, actor: str,
        target_state: str | None = None, fencing_token: int | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        campaign, request_id = _identifier(campaign_id), _identifier(request_id)
        action, actor = _identifier(action), _identifier(actor)
        if target_state is not None and target_state not in _STATES:
            raise StoreError("INVALID_STATE", f"unknown state {target_state!r}")
        body = {"action": action, "actor": actor, "target_state": target_state,
                "fencing_token": fencing_token, "payload": dict(payload or {})}
        claim = content_digest(body)
        with self._write() as db:
            replay = _replay(db, campaign, request_id, claim)
            if replay:
                return replay
            row = _campaign(db, campaign)
            observed = self._observed()
            now = _format(observed)
            _fence(row, fencing_token, required=True, observed=observed)
            _holder(row, actor)
            old, new = row["state"], target_state or row["state"]
            if target_state is not None:
                require_transition(old, new)
            if row["lease_mode"] == "terminal_only" and new in {
                "PREFLIGHTING", "READY", "RUNNING", "RECOVERING"
            }:
                raise StoreError("AUTHORITY_MODE_VIOLATION", "terminal lease cannot reopen work")
            if row["lease_mode"] == "recovery_only" and new in {
                "PREFLIGHTING", "READY", "RUNNING"
            }:
                raise StoreError(
                    "AUTHORITY_MODE_VIOLATION",
                    "recovery reconciliation must promote authority before reopening",
                )
            if new in {"READY", "RUNNING"}:
                _executor_enabled(db, campaign)
                _powered(db, row, observed)
            next_mode = "terminal_only" if new == "DRAINING" else row["lease_mode"]
            db.execute(
                """UPDATE campaigns SET state=?,lease_mode=?,updated_at=?
                WHERE campaign_id=?""",
                (new, next_mode, now, campaign),
            )
            event = _event(
                db, campaign, f"operator.{action}", request_id, actor, old, new,
                fencing_token, body["payload"], recorded_at=now,
            )
            receipt = _action_receipt(
                campaign, request_id, action, actor, row["manifest_digest"],
                fencing_token, new, event, previous_state=old, payload=body["payload"],
                recorded_at=now,
            )
            _save_action(db, campaign, request_id, claim, receipt)
            return receipt
    def acquire_lease(
        self, campaign_id: str, *, request_id: str, holder: str,
        mode: str = "active", ttl_seconds: int = 90,
    ) -> dict[str, Any]:
        campaign, request_id = _identifier(campaign_id), _identifier(request_id)
        holder = _identifier(holder)
        if mode not in _MODES:
            raise StoreError("INVALID_LEASE_MODE", f"unknown lease mode {mode!r}")
        if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or ttl_seconds < 3:
            raise StoreError("INVALID_LEASE_TTL", "lease TTL must be at least 3 seconds")
        observed = self._observed()
        body = {"holder": holder, "mode": mode, "ttl_seconds": ttl_seconds}
        claim = content_digest(body)
        with self._write() as db:
            replay = _replay(db, campaign, request_id, claim)
            if replay:
                return replay
            row = _campaign(db, campaign)
            expiry = _time(row["lease_expires"]) if row["lease_expires"] else None
            if row["state"] in {"COMPLETED", "FAILED"}:
                raise StoreError("CAMPAIGN_TERMINAL", "terminal campaign cannot acquire a lease")
            if row["active_fence"] is not None and expiry and observed < expiry:
                raise StoreError("LEASE_HELD", "an unexpired manager lease exists")
            token, acquired = row["fence_counter"] + 1, _format(observed)
            expires = _format(observed + timedelta(seconds=ttl_seconds))
            db.execute(
                """INSERT INTO leases VALUES(?,?,?,?,?,?,?)""",
                (campaign, token, row["manifest_digest"], holder, mode, acquired, expires),
            )
            db.execute(
                """UPDATE campaigns SET fence_counter=?,active_fence=?,lease_holder=?,
                lease_mode=?,lease_expires=?,updated_at=? WHERE campaign_id=?""",
                (token, token, holder, mode, expires, acquired, campaign),
            )
            event = _event(
                db, campaign, "lease.acquired", request_id, holder, row["state"],
                row["state"], token, body | {"expires_at": expires},
                recorded_at=acquired,
            )
            receipt = {
                "schema": "forge_lab.fenced_lease.v1", "campaign": campaign,
                "manifest_digest": row["manifest_digest"], "request_id": request_id,
                "holder": holder, "mode": mode, "fencing_token": token,
                "ttl_seconds": ttl_seconds, "acquired_at": acquired,
                "expires_at": expires, "event_sequence": event["sequence"],
            }
            receipt["digest"] = content_digest(receipt)
            _save_action(db, campaign, request_id, claim, receipt)
            return receipt
    def release_lease(
        self, campaign_id: str, *, request_id: str, holder: str,
        fencing_token: int,
    ) -> dict[str, Any]:
        """Conditionally release only the caller's current fenced lease."""
        campaign, request_id, holder = (
            _identifier(campaign_id), _identifier(request_id), _identifier(holder)
        )
        body = {"action": "release_lease", "holder": holder,
                "fencing_token": fencing_token}
        claim = content_digest(body)
        with self._write() as db:
            replay = _replay(db, campaign, request_id, claim)
            if replay:
                return replay
            row = _campaign(db, campaign)
            observed = self._observed()
            now = _format(observed)
            _fence(row, fencing_token, required=True, observed=observed)
            if row["lease_holder"] != holder:
                raise StoreError("LEASE_HOLDER_MISMATCH", "lease holder differs")
            event = _event(
                db, campaign, "lease.released", request_id, holder, row["state"],
                row["state"], fencing_token, {"holder": holder}, recorded_at=now,
            )
            receipt = _action_receipt(
                campaign, request_id, "release_lease", holder,
                row["manifest_digest"], fencing_token, row["state"], event,
                recorded_at=now,
            )
            db.execute(
                """UPDATE campaigns SET active_fence=NULL,lease_holder=NULL,
                lease_mode=NULL,lease_expires=NULL,updated_at=? WHERE campaign_id=?
                AND active_fence=? AND lease_holder=?""",
                (now, campaign, fencing_token, holder),
            )
            if db.execute("SELECT changes() n").fetchone()["n"] != 1:
                raise StoreError("STALE_FENCING_TOKEN", "lease changed during release")
            _save_action(db, campaign, request_id, claim, receipt)
            return receipt
    def checkpoint(
        self, campaign_id: str, *, checkpoint_id: str, actor: str,
        fencing_token: int, payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        campaign, checkpoint_id, actor = (
            _identifier(campaign_id),
            _identifier(checkpoint_id),
            _identifier(actor),
        )
        pd = content_digest(payload)
        with self._write() as db:
            row = _campaign(db, campaign)
            observed = self._observed()
            now = _format(observed)
            _fence(row, fencing_token, required=True, observed=observed)
            _holder(row, actor)
            old = db.execute(
                """SELECT payload_digest,receipt_json FROM checkpoints
                WHERE campaign_id=? AND checkpoint_id=?""", (campaign, checkpoint_id)
            ).fetchone()
            if old:
                if old["payload_digest"] != pd:
                    raise StoreError("IDEMPOTENCY_CONFLICT", "checkpoint ID reused")
                return _object(old["receipt_json"])
            event = _event(
                db, campaign, "checkpoint.committed", checkpoint_id,
                actor, row["state"], row["state"], fencing_token,
                {"payload_digest": pd}, recorded_at=now,
            )
            receipt = {
                "schema": "forge_lab.checkpoint.v1", "campaign": campaign,
                "manifest_digest": row["manifest_digest"], "checkpoint_id": checkpoint_id,
                "payload": dict(payload), "payload_digest": pd,
                "fencing_token": fencing_token, "event_sequence": event["sequence"],
                "recorded_at": now,
            }
            receipt["digest"] = content_digest(receipt)
            db.execute(
                "INSERT INTO checkpoints VALUES(?,?,?,?,?,?)",
                (campaign, checkpoint_id, pd, _text(receipt),
                 fencing_token, event["sequence"]),
            )
            return receipt
    def authorize_campaign(
        self, campaign_id: str, *, request_id: str, actor: str,
        envelope: Mapping[str, Any] | str | None,
        trusted_public_keys: Mapping[str, str | bytes] | Iterable[str | bytes],
        expected_host: str, fencing_token: int,
    ) -> dict[str, Any]:
        """Bind one verified manifest-specific operator spend envelope."""
        from .campaign_authority import authorize_campaign

        return authorize_campaign(
            self,
            _identifier(campaign_id),
            request_id=_identifier(request_id),
            actor=_identifier(actor),
            envelope=envelope,
            trusted_public_keys=trusted_public_keys,
            expected_host=expected_host,
            fencing_token=fencing_token,
        )
    def reserve_request(
        self, campaign_id: str, *, request_id: str, stage: str,
        token_ceiling: int, usd_micros_ceiling: int, fencing_token: int,
    ) -> dict[str, Any]:
        from .campaign_usage import reserve_request

        return reserve_request(
            self, campaign_id, request_id=request_id, stage=stage,
            token_ceiling=token_ceiling, usd_micros_ceiling=usd_micros_ceiling,
            fencing_token=fencing_token,
        )

    def settle_request(
        self, campaign_id: str, *, request_id: str, status: str,
        actual_tokens: int, actual_usd_micros: int, fencing_token: int,
    ) -> dict[str, Any]:
        from .campaign_usage import settle_request

        return settle_request(
            self, campaign_id, request_id=request_id, status=status,
            actual_tokens=actual_tokens, actual_usd_micros=actual_usd_micros,
            fencing_token=fencing_token,
        )
    def terminal_attempt(
        self, campaign_id: str, *, attempt_id: str, status: str,
        parent_digest: str, mutation_result: Mapping[str, Any],
        evaluation_digest: str, accounting: Mapping[str, Any],
        terminal_receipt: Mapping[str, Any], fencing_token: int,
    ) -> dict[str, Any]:
        from .campaign_attempts import terminal_attempt

        return terminal_attempt(
            self,
            _identifier(campaign_id),
            attempt_id=_identifier(attempt_id),
            status=status,
            parent_digest=parent_digest,
            mutation_result=mutation_result,
            evaluation_digest=evaluation_digest,
            accounting=accounting,
            terminal_receipt=terminal_receipt,
            fencing_token=fencing_token,
        )

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(SCHEMA_SQL)
            db.execute(
                """INSERT INTO executor_fuses(campaign_id,state,reason,updated_at)
                SELECT campaign_id,'closed','GOVERNED_EXECUTOR_NOT_IMPLEMENTED',?
                FROM campaigns
                WHERE campaign_id NOT IN (SELECT campaign_id FROM executor_fuses)""",
                (_format(self._observed()),),
            )

    def _observed(self) -> datetime:
        observed = self._clock()
        if not isinstance(observed, datetime):
            raise StoreError(
                "INVALID_TRUSTED_CLOCK",
                "trusted clock must return a timezone-aware datetime",
            )
        return _time(observed)

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        db = self._connect()
        try:
            yield db
        finally:
            db.close()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        for pragma in ("journal_mode=WAL", "synchronous=FULL", "foreign_keys=ON",
                       "busy_timeout=10000"):
            db.execute(f"PRAGMA {pragma}")
        return db
