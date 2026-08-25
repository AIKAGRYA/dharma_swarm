#!/usr/bin/env python3
"""Fail-closed release envelope for the time-bounded SADHANA campaign.

This module deliberately admits an *unmerged deployment candidate*, never a
canonical release.  It validates exact Git, evidence, topology, timebox, and
filesystem claims before it can render or activate any host service.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import ctypes
import errno
import fcntl
import hashlib
import hmac
import http.client
import json
import os
import platform
import pwd
import re
import shlex
import shutil
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

SCHEMA_VERSION = "dharma.sadhana.deployment_candidate.v1"
MISSION_ID = "sadhana-10-20260823"
CAMPAIGN_START_UTC = "2026-08-22T17:15:12Z"
CAMPAIGN_STOP_UTC = "2026-09-01T17:15:12Z"
CANONICAL_ORIGIN = "https://github.com/AIKAGRYA/dharma_swarm.git"
ACCEPTED_BASE_SHA = "abc8bd35c34c729ed421f9615df504f5615868bd"
RELEASE_CLASS = "unmerged-deployment-candidate"
WRITER_NODE = "meghadharma-cloud"
STANDBY_NODE = "agni-openclaw"
API_LISTEN = "127.0.0.1:18420"
RESERVED_CONTROL_LISTEN = "127.0.0.1:18421"
CONTROL_REQUEST_PATH = "/v1/operator-control/requests"
CONTROL_REQUEST_URL = f"http://{RESERVED_CONTROL_LISTEN}{CONTROL_REQUEST_PATH}"
ACCOUNT_UI_CONFIRMATION_REQUEST_PATH = "/v1/account-ui-confirmations"
ACCOUNT_UI_CONFIRMATION_REQUEST_URL = (
    f"http://{RESERVED_CONTROL_LISTEN}{ACCOUNT_UI_CONFIRMATION_REQUEST_PATH}"
)
ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256 = (
    "60996ccfa8de0db715d26ecf062d13604e09ab019c51d9047cb250e39652dad1"
)
ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_CANONICAL = (
    "schema=dharma.sadhana.account_ui_confirmation_http_binding.v1;method=POST;"
    "browser_route=/dharma-internal/account-ui-confirmation;internal_url="
    "http://127.0.0.1:18421/v1/account-ui-confirmations;headers=authorization,"
    "content-type,origin,tailscale-user-login,x-sadhana-csrf,x-sadhana-release-sha;"
    "request_schema=dharma.sadhana.authenticated_account_ui_confirmation_request.v1;"
    "request_fields=campaign_id,client_request_id,coarse_pointer_reported,"
    "dashboard_rendered_reported,document_width_css_px_reported,expires_at,"
    "explicit_confirmation_gesture_reported,issued_at,schema_version,"
    "touch_capability_reported,trusted_browser_event_reported,"
    "viewport_width_css_px_reported,visual_viewport_width_css_px_reported;"
    "response_fields=account_authenticated,authority_applied,candidate_recorded,"
    "dispatch_authorized,human_identity_attested,physical_device_attested,replayed,"
    "status;http_202=CandidateRecorded<NoAuthority,NoDispatch>;"
    "candidate=fixed-path-o_excl;mac=derived-domain-separated-hmac-sha256"
)
if (
    hashlib.sha256(ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_CANONICAL.encode()).hexdigest()
    != ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256
):
    raise RuntimeError("account UI confirmation HTTP binding digest differs")
DASHBOARD_SOCKET_DIRECTORY = Path("/run/dharma-sadhana/dashboard")
DASHBOARD_SOCKET_PATH = DASHBOARD_SOCKET_DIRECTORY / "constellation.sock"
DASHBOARD_LISTEN = f"unix:{DASHBOARD_SOCKET_PATH}"
DASHBOARD_PROXY_URL = "http://127.0.0.1:18420"
TAILSCALE_EXPOSURE = "serve-private"
RELEASE_ROOT = "/opt/dharma-sadhana/releases"
STATE_ROOT = "/var/lib/dharma-sadhana/state"
WORKSPACE_ROOT = "/var/lib/dharma-sadhana/workspace"
API_STATE_ROOT = "/var/lib/dharma-sadhana/api-state"
SNAPSHOT_ROOT = "/var/lib/dharma-sadhana/snapshots"
SNAPSHOT_STAGING_ROOT = "/var/lib/dharma-sadhana/snapshot-staging"
SNAPSHOT_FINALIZING_ROOT = "/var/lib/dharma-sadhana/snapshot-finalizing"
SNAPSHOT_INCOMING_ROOT = "/var/lib/dharma-sadhana/snapshot-incoming"
SNAPSHOT_UPLOAD_ROOT = f"{SNAPSHOT_INCOMING_ROOT}/uploads"
SNAPSHOT_ACK_ROOT = f"{SNAPSHOT_INCOMING_ROOT}/acks"
SNAPSHOT_RECEIVER_CLAIM_ROOT = "/var/lib/dharma-sadhana/snapshot-receiver-claims"
SNAPSHOT_QUARANTINE_ROOT = "/var/lib/dharma-sadhana/snapshot-quarantine"
SNAPSHOT_RECEIPT_ROOT = "/var/lib/dharma-sadhana/snapshot-receipts"
SNAPSHOT_OUTBOX_ROOT = "/var/lib/dharma-sadhana/snapshot-outbox"
PROJECTION_SOURCE_ROOT = Path("/var/lib/dharma-sadhana/projection-source")
WRITER_PROJECTION_PATH = PROJECTION_SOURCE_ROOT / "mission-projection.json"
OBSERVER_PROJECTION_PATH = Path(API_STATE_ROOT) / "mission-projection.json"
SNAPSHOT_READINESS_SOURCE_PATH = (
    Path(SNAPSHOT_STAGING_ROOT) / "snapshot-readiness.v1.json"
)
OBSERVER_SNAPSHOT_READINESS_PATH = (
    Path(API_STATE_ROOT) / "snapshot-readiness.v1.json"
)
CONTROL_SCHEMA_VERSION = "dharma.sadhana.operator_control.v1"
CONTROL_SEMANTICS_SHA256 = (
    "69a0eb088277882e333ac41a6fb7014f6ed9d792e6d4a4b2b8510f20de15077c"
)
CONTROL_HTTP_BINDING_SHA256 = (
    "9e1aec44c75cf6b24341389b8227f57fe4d4cf48328992f2125bffca34fcf3eb"
)
CONTROL_AUTHORITY_BINDING_SHA256 = (
    "495f16964248948c68f97b5ec02b7e5d3e00e006979bf283ea783127e303d52d"
)
CONTROL_ROOT = Path("/run/dharma-sadhana/control")
CONTROL_NORMAL_INBOX = CONTROL_ROOT / "normal"
CONTROL_EMERGENCY_INBOX = CONTROL_ROOT / "emergency"
CONTROL_INFLIGHT_ROOT = CONTROL_ROOT / "inflight"
CONTROL_APPLIED_ROOT = CONTROL_ROOT / "applied"
CONTROL_REJECTED_ROOT = CONTROL_ROOT / "rejected"
CONTROL_ACTIVATION_ROOT = CONTROL_ROOT / "activation"
ACCOUNT_UI_CONFIRMATION_ROOT = CONTROL_ROOT / "account-ui-confirmation"
ACCOUNT_UI_CONFIRMATION_CANDIDATE = ACCOUNT_UI_CONFIRMATION_ROOT / "candidate.v2.json"
PREDISPATCH_ACCOUNT_UI_GATE_ROOT = CONTROL_ROOT / "account-ui-gate"
PREDISPATCH_ACCOUNT_UI_GATE = (
    PREDISPATCH_ACCOUNT_UI_GATE_ROOT / "predispatch-gate.v1.json"
)
PREDISPATCH_ACCOUNT_UI_GATE_SCHEMA_VERSION = (
    "dharma.sadhana.account_ui_predispatch_gate.v1"
)
ACCOUNT_UI_CONFIRMATION_CANDIDATE_SCHEMA_VERSION = (
    "dharma.sadhana.authenticated_account_ui_confirmation_candidate.v2"
)
ACCOUNT_UI_CONFIRMATION_SCHEMA_VERSION = (
    "dharma.sadhana.authenticated_account_ui_confirmation.v1"
)
ACCOUNT_UI_CONFIRMATION_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/"
    "authenticated-account-ui-confirmation.v1.json"
)
ACCOUNT_UI_CONFIRMATION_MAC_DOMAIN = (
    b"dharma.sadhana.authenticated_account_ui_confirmation_candidate.v2\x00"
)
ACCOUNT_UI_CONFIRMATION_KEY_DOMAIN = (
    b"dharma.sadhana.authenticated_account_ui_confirmation_key.v2\x00"
)
CAMPAIGN_ACTIVATION_PROOF = CONTROL_ACTIVATION_ROOT / "campaign-activation.v1.json"
CAMPAIGN_ACTIVATION_SCHEMA_VERSION = "dharma.sadhana.campaign_activation.v1"
EMERGENCY_QUARANTINE_ROOT = Path("/run/dharma-sadhana/emergency-quarantine")
EMERGENCY_INFLIGHT_ROOT = Path("/var/lib/dharma-sadhana/emergency-inflight")
EMERGENCY_APPLY_LOCK = Path("/var/lib/dharma-sadhana/emergency-apply.lock")
CONTROL_CREDENTIAL_SOURCE_ROOT = Path("/etc/dharma-sadhana/credentials")
CONTROL_BEARER_SOURCE = CONTROL_CREDENTIAL_SOURCE_ROOT / "operator_bearer"
CONTROL_HMAC_SOURCE = CONTROL_CREDENTIAL_SOURCE_ROOT / "control_hmac_key"
CONTROL_LOGIN_SOURCE = CONTROL_CREDENTIAL_SOURCE_ROOT / "tailscale_operator_login"
CONTROL_CREDENTIAL_DESTINATIONS = {
    "operator_bearer": CONTROL_BEARER_SOURCE,
    "control_hmac_key": CONTROL_HMAC_SOURCE,
    "tailscale_operator_login": CONTROL_LOGIN_SOURCE,
}
EMERGENCY_RECEIPT_ROOT = Path("/etc/dharma-sadhana/receipts/control/emergency")
EMERGENCY_STOP_MARKER = EMERGENCY_RECEIPT_ROOT / "emergency-stopped"
CONTROL_MAX_REQUEST_BYTES = 4096
CONTROL_CSRF_HEADER = "X-Sadhana-CSRF"
CONTROL_CSRF_VALUE = MISSION_ID
UV_VERSION = "0.11.2"
UV_WHEEL_FILE = "uv-0.11.2-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
UV_WHEEL_URL = (
    "https://files.pythonhosted.org/packages/9f/6e/"
    "f49ca8ad037919e5d44a2070af3d369792be3419c594cfb92f4404ab7832/" + UV_WHEEL_FILE
)
UV_WHEEL_SHA256 = "be4bb136bbc8840ede58663e8ba5a9bbf3b5376f7f933f915df28d4078bb9095"
UV_BINARY_MEMBER = "uv-0.11.2.data/scripts/uv"
UV_TOOLING_ROOT = Path("/opt/dharma-sadhana/tooling")
GIT_PATH = "/usr/bin/git"
GITLEAKS_PATH = "/opt/homebrew/bin/gitleaks"
GITLEAKS_VERSION = "8.30.1"
JOURNALCTL_PATH = "/usr/bin/journalctl"
NPM_PATH = "/usr/bin/npm"
PYTHON312_PATH = "/usr/bin/python3.12"
SYSTEMCTL_PATH = "/usr/bin/systemctl"
SYSTEMD_RUN_PATH = "/usr/bin/systemd-run"
SETPRIV_PATH = "/usr/bin/setpriv"
RSYNC_CLIENT_PATH = "/usr/bin/rsync"
SSH_KEYSCAN_PATH = "/usr/bin/ssh-keyscan"
SSH_PATH = "/usr/bin/ssh"
TAILSCALE_PATH = "/usr/bin/tailscale"
TAILSCALE_VERSION = "1.102.2"
TIMEDATECTL_PATH = "/usr/bin/timedatectl"
RUNTIME_ROOT = Path("/run/dharma-sadhana")
TAILSCALE_ROUTE = DASHBOARD_LISTEN
TAILSCALE_STATE_ROOT = RUNTIME_ROOT / "tailscale"
TAILSCALE_INTENT_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/tailscale-serve-intent.v1.json"
)
TAILSCALE_OWNERSHIP_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/tailscale-serve-owned.v3.json"
)
TAILSCALE_STOP_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/tailscale-serve-stopped.v1.json"
)
TAILSCALE_INTENT_SCHEMA_VERSION = "dharma.sadhana.tailscale_serve_intent.v1"
TAILSCALE_OWNERSHIP_SCHEMA_VERSION = "dharma.sadhana.tailscale_ownership.v3"
TAILSCALE_STOP_SCHEMA_VERSION = "dharma.sadhana.tailscale_serve_stop.v1"
TAILSCALE_EMPTY_CONFIG = {"version": "0.0.1"}
STANDBY_TAILSCALE_PORT = 2222
STANDBY_TAILSCALE_ROUTE = "tcp://localhost:22"
STANDBY_TAILSCALE_STATUS = {
    "TCP": {str(STANDBY_TAILSCALE_PORT): {"TCPForward": "localhost:22"}}
}
STANDBY_TAILSCALE_INTENT_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/"
    "standby-replication-serve-intent.v1.json"
)
STANDBY_TAILSCALE_OWNERSHIP_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/"
    "standby-replication-serve-owned.v1.json"
)
STANDBY_TAILSCALE_STOP_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/"
    "standby-replication-serve-stopped.v1.json"
)
STANDBY_TAILSCALE_INTENT_SCHEMA_VERSION = (
    "dharma.sadhana.standby_replication_serve_intent.v1"
)
STANDBY_TAILSCALE_OWNERSHIP_SCHEMA_VERSION = (
    "dharma.sadhana.standby_replication_serve_ownership.v1"
)
STANDBY_TAILSCALE_STOP_SCHEMA_VERSION = (
    "dharma.sadhana.standby_replication_serve_stop.v1"
)
STANDBY_REPLICATION_ROUTE_PROBE_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/"
    "standby-replication-route-probe.v1.json"
)
STANDBY_REPLICATION_ROUTE_PROBE_SCHEMA_VERSION = (
    "dharma.sadhana.standby_replication_route_probe.v1"
)
STANDBY_REPLICATION_ROUTE_PROBE_FRESHNESS_SECONDS = 600
STANDBY_REPLICATION_ROUTE_PROBE_MAX_SEQUENCE = 4096
STANDBY_REPLICATION_SSH_KEY = Path("/etc/dharma-sadhana/replication_ed25519")
STANDBY_REPLICATION_KNOWN_HOSTS = Path("/etc/dharma-sadhana/known_hosts")
STOP_ENFORCEMENT_RECEIPT = Path(STATE_ROOT) / "stop-enforcement-receipt.json"
PREACTIVATION_CLOCK_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/"
    "preactivation-clock-proof.v1.json"
)
HOST_SCAFFOLD_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/host-scaffold-admission.v1.json"
)
OBSERVER_HEALTH_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/observer-health-18420.v3.json"
)
OBSERVER_HEALTH_SCHEMA_VERSION = "dharma.sadhana.observer_health_acceptance.v3"
OBSERVER_HEALTH_ENDPOINT = "http://127.0.0.1:18420/api/health"
OBSERVER_HEALTH_SUCCESS_COUNT = 20
OBSERVER_HEALTH_MAX_GAP_SECONDS = 5
OBSERVER_UNIT = "dharma-sadhana-api.service"
OBSERVER_HEALTH_UNIT = "dharma-sadhana-observer-health.service"
SUPERVISOR_UNIT = "dharma-sadhana-supervisor.service"
DASHBOARD_UNIT = "dharma-sadhana-dashboard.service"
CONTROL_UNIT = "dharma-sadhana-control.service"
PREDISPATCH_TARGET = "dharma-sadhana.target"
DISPATCH_TARGET = "dharma-sadhana-dispatch.target"
DISPATCH_ENABLE_UNIT = "dharma-sadhana-dispatch-enable.service"
CAMPAIGN_STOP_TIMER = "dharma-sadhana-campaign-stop.timer"
EMERGENCY_RECOVERY_PATH = "dharma-sadhana-control-emergency-recovery.path"
PREDISPATCH_ACTIVATION_UNITS = (
    CAMPAIGN_STOP_TIMER,
    EMERGENCY_RECOVERY_PATH,
    PREDISPATCH_TARGET,
)
DASHBOARD_IDENTITY_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/dashboard-identity.v5.json"
)
DASHBOARD_IDENTITY_SCHEMA_VERSION = (
    "dharma.sadhana.dashboard_identity_acceptance.v5"
)
DASHBOARD_ROLLBACK_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/dashboard-rollback.v3.json"
)
DASHBOARD_ROLLBACK_SCHEMA_VERSION = "dharma.sadhana.dashboard_rollback_probe.v3"
OPERATOR_CREDENTIAL_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/operator-bearer-custody.v4.json"
)
OPERATOR_CREDENTIAL_SCHEMA_VERSION = (
    "dharma.sadhana.operator_bearer_custody_acceptance.v4"
)
ORACLE_SANDBOX_EVIDENCE_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/oracle/oracle-sandbox-evidence.v1.json"
)
SUPERVISOR_ACTIVATION_ENV = Path(
    "/etc/dharma-sadhana/receipts/preactivation/supervisor-activation.env"
)
SUPERVISOR_CREDENTIAL_ROOT = Path(
    "/run/credentials/dharma-sadhana-supervisor.service"
)
DISPATCH_ACTIVATION_CREDENTIAL = (
    SUPERVISOR_CREDENTIAL_ROOT / "dispatch_activation_receipt"
)
DASHBOARD_IDENTITY_CREDENTIAL = (
    SUPERVISOR_CREDENTIAL_ROOT / "dashboard_identity_receipt"
)
RUNTIME_BINDING_CREDENTIAL = (
    SUPERVISOR_CREDENTIAL_ROOT / "runtime_binding_activation"
)
OPERATOR_LOGIN_CREDENTIAL = (
    SUPERVISOR_CREDENTIAL_ROOT / "tailscale_operator_login"
)
CONTROL_HMAC_CREDENTIAL = SUPERVISOR_CREDENTIAL_ROOT / "control_hmac_key"
SUPERVISOR_RUNTIME_ENV = Path("/etc/dharma-sadhana/supervisor-runtime.env")
RUNTIME_STAGING_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/runtime-staging.v1.json"
)
RUNTIME_STAGING_SCHEMA_VERSION = "dharma.sadhana.runtime_staging_acceptance.v1"
PREDISPATCH_REFRESH_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/predispatch-refresh.v1.json"
)
PREDISPATCH_REFRESH_SCHEMA_VERSION = "dharma.sadhana.predispatch_refresh.v1"
PREDISPATCH_REFRESH_FRESHNESS_SECONDS = 120
PREDISPATCH_ACTIVATION_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/predispatch-activation.v1.json"
)
PREDISPATCH_ACTIVATION_INTENT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/"
    "predispatch-activation-intent.v1.json"
)
PREDISPATCH_ACTIVATION_SCHEMA_VERSION = (
    "dharma.sadhana.predispatch_activation.v1"
)
PREDISPATCH_ACTIVATION_INTENT_SCHEMA_VERSION = (
    "dharma.sadhana.predispatch_activation_intent.v1"
)
DISPATCH_ENABLE_MARKER = Path(
    "/etc/dharma-sadhana/receipts/preactivation/dispatch-enabled.v1.json"
)
DISPATCH_ENABLE_SCHEMA_VERSION = "dharma.sadhana.dispatch_enablement.v1"
ROLLBACK_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/rollback/rollback.v1.json"
)
ROLLBACK_SCHEMA_VERSION = "dharma.sadhana.release_rollback.v3"
STANDBY_TARGET = "dharma-sadhana-standby.target"
STANDBY_STOP_TIMER = "dharma-sadhana-standby-stop.timer"
STANDBY_REPLICATION_SERVE_UNIT = (
    "dharma-sadhana-standby-replication-serve.service"
)
STANDBY_ACTIVATION_RECEIPT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/standby-activation.v1.json"
)
STANDBY_ACTIVATION_INTENT = Path(
    "/etc/dharma-sadhana/receipts/preactivation/standby-activation-intent.v1.json"
)
STANDBY_ACTIVATION_SCHEMA_VERSION = "dharma.sadhana.standby_activation.v1"
STANDBY_ACTIVATION_INTENT_SCHEMA_VERSION = (
    "dharma.sadhana.standby_activation_intent.v1"
)
STANDBY_STOP_MARKER = Path(
    "/etc/dharma-sadhana/receipts/standby/deadline-stopped.v1.json"
)
STANDBY_STOP_SCHEMA_VERSION = "dharma.sadhana.standby_deadline_stop.v1"
TAILSCALE_DASHBOARD_CREDENTIAL = Path(
    "/run/credentials/dharma-sadhana-dashboard.service/operator_bearer"
)
TAILSCALE_CONTROL_CREDENTIAL = Path(
    "/run/credentials/dharma-sadhana-control.service/operator_bearer"
)
OBSERVER_UNIT_PATH = Path("/etc/systemd/system") / OBSERVER_UNIT
STANDBY_CAPACITY_RECEIPT_TARGET = Path(
    "/etc/dharma-sadhana/receipts/preactivation/standby-capacity.v2.json"
)
STANDBY_CAPACITY_SCHEMA_VERSION = "dharma.sadhana.standby_capacity_proof.v2"
STANDBY_CAPACITY_PROOF_FRESHNESS_SECONDS = 600
MAX_CONTROLLER_CLOCK_SKEW_SECONDS = 30
CLOCK_PROOF_FRESHNESS_SECONDS = 120
PREACTIVATION_CLOCK_SCHEMA_VERSION = (
    "dharma.sadhana.preactivation_clock_proof.v2"
)
USERADD_PATH = "/usr/sbin/useradd"
BUILD_ACCOUNT_NAME = "dharma-sadhana-build"
BUILD_ACCOUNT_HOME = "/var/lib/dharma-sadhana-build"
BUILD_ACCOUNT_SHELL = "/usr/sbin/nologin"
DASHBOARD_ACCOUNT_NAME = "dharma-sadhana-dashboard"
DASHBOARD_ACCOUNT_HOME = "/var/lib/dharma-sadhana-dashboard"
DASHBOARD_ACCOUNT_SHELL = "/usr/sbin/nologin"
OBSERVER_ACCOUNT_NAME = "dharma-sadhana-observer"
OBSERVER_ACCOUNT_HOME = "/var/lib/dharma-sadhana-observer"
OBSERVER_ACCOUNT_SHELL = "/usr/sbin/nologin"
ORACLE_ACCOUNT_NAME = "dharma-sadhana-oracle"
ORACLE_ACCOUNT_HOME = "/var/lib/dharma-sadhana-oracle"
ORACLE_ACCOUNT_SHELL = "/usr/sbin/nologin"
ORACLE_INPUT_ROOT = Path("/var/lib/dharma-sadhana/oracle-inputs")
ORACLE_CLAIM_ROOT = Path("/var/lib/dharma-sadhana/oracle-claims")
ORACLE_RUN_ROOT = Path("/var/lib/dharma-sadhana/oracle-runs")
ORACLE_QUARANTINE_ROOT = Path("/var/lib/dharma-sadhana/oracle-quarantine")
ORACLE_RECEIPT_ROOT = Path("/etc/dharma-sadhana/receipts/oracle")
BUILD_DRIVER_PREFIX = "sadhana-build-driver-"
RRSYNC_PATH = Path("/usr/bin/rrsync")
STANDBY_AUTHORIZED_KEY_INPUT = Path(
    "/etc/dharma-sadhana/replication_authorized_key.pub"
)
STANDBY_SSH_ROOT = Path("/var/lib/dharma-sadhana/.ssh")
SYSTEMD_TEMPLATE_ROOT = Path("deploy/sadhana/systemd")
SYSTEMD_OUTPUT_ROOT = Path("/etc/systemd/system")
WRITER_MARKER = Path("/etc/dharma-sadhana/writer-enabled")
RUNTIME_PREPARATION_UNIT = "dharma-sadhana-runtime-prepare.service"
CAMPAIGN_UNITS = (
    RUNTIME_PREPARATION_UNIT,
    "dharma-sadhana-dispatch.target",
    "dharma-sadhana-dispatch-enable.service",
    "dharma-sadhana-supervisor.service",
    "dharma-sadhana-api.service",
    "dharma-sadhana-observer-health.service",
    "dharma-sadhana-dashboard.service",
    "dharma-sadhana-projection-sync.service",
    "dharma-sadhana-projection-sync.timer",
    "dharma-sadhana-control-directories.service",
    "dharma-sadhana-control.service",
    "dharma-sadhana-control-emergency.path",
    "dharma-sadhana-control-emergency-recovery.path",
    "dharma-sadhana-control-emergency-recovery.service",
    "dharma-sadhana-control-emergency.service",
    "dharma-sadhana-oracle-directories.service",
    "dharma-sadhana-oracle-sandbox-probe.service",
    "dharma-sadhana-oracle-sandbox.service",
    "dharma-sadhana-oracle-sandbox.path",
    "dharma-sadhana-oracle-sandbox.timer",
    "dharma-sadhana-private-serve.service",
    "dharma-sadhana-campaign-stop.service",
    "dharma-sadhana-campaign-stop.timer",
    "dharma-sadhana-snapshot.service",
    "dharma-sadhana-snapshot.timer",
    "dharma-sadhana-snapshot-finalize.path",
    "dharma-sadhana-snapshot-retry.timer",
    "dharma-sadhana-snapshot-finalize.service",
    "dharma-sadhana.target",
)
STANDBY_UNITS = (
    "dharma-sadhana-standby.target",
    STANDBY_REPLICATION_SERVE_UNIT,
    "dharma-sadhana-standby-stop.service",
    "dharma-sadhana-standby-stop.timer",
    "dharma-sadhana-standby-snapshot-receiver.path",
    "dharma-sadhana-standby-snapshot-receiver.timer",
    "dharma-sadhana-standby-snapshot-receiver.service",
)
CAMPAIGN_PARTOF_UNITS = (
    "dharma-sadhana-dispatch.target",
    "dharma-sadhana-dispatch-enable.service",
    "dharma-sadhana-supervisor.service",
    "dharma-sadhana-api.service",
    "dharma-sadhana-observer-health.service",
    "dharma-sadhana-dashboard.service",
    "dharma-sadhana-projection-sync.service",
    "dharma-sadhana-projection-sync.timer",
    "dharma-sadhana-control-directories.service",
    "dharma-sadhana-oracle-directories.service",
    "dharma-sadhana-oracle-sandbox-probe.service",
    "dharma-sadhana-oracle-sandbox.service",
    "dharma-sadhana-oracle-sandbox.path",
    "dharma-sadhana-oracle-sandbox.timer",
    "dharma-sadhana-private-serve.service",
    "dharma-sadhana-snapshot.service",
    "dharma-sadhana-snapshot.timer",
    "dharma-sadhana-snapshot-finalize.path",
    "dharma-sadhana-snapshot-retry.timer",
    "dharma-sadhana-snapshot-finalize.service",
    "dharma-sadhana-control.service",
    "dharma-sadhana-control-emergency.path",
)
ENV_FILES = (
    "/etc/dharma-sadhana/supervisor.env",
    "/etc/dharma-sadhana/api.env",
    "/etc/dharma-sadhana/dashboard.env",
    "/etc/dharma-sadhana/control.env",
    "/etc/dharma-sadhana/replication.env",
    "/etc/dharma-sadhana/verifier.env",
)
VERIFIER_ENV_PATH = Path(ENV_FILES[-1])
INPUT_SET_SCHEMA_VERSION = "dharma.sadhana.immutable_input_set.v1"
INPUT_SET_TARGET_ROOT = Path("/etc/dharma-sadhana/inputs")
INPUT_SET_MANIFEST_TARGET = Path("/etc/dharma-sadhana/input-set.manifest.json")
INPUT_SET_RECEIPT_TARGET = Path("/etc/dharma-sadhana/input-set.receipt.json")
INPUT_SET_MANIFEST_FILE = "input-set.manifest.json"
INPUT_SET_ARCHIVE_FILE = "dharma-sadhana-input-set.zip"
TRACKED_SOURCE_SCHEMA_VERSION = "dharma.sadhana.tracked_source_manifest.v1"
TRACKED_SOURCE_MANIFEST_FILE = "tracked-source.manifest.json"
TRACKED_SOURCE_BUILD_OUTPUT_ROOTS = (
    ".venv",
    "dashboard/.next",
    "dashboard/node_modules",
)
RUNTIME_INPUT_RELATIVE_ROOT = "runtime/sadhana-10-20260823"
RUNTIME_INPUT_ROOT = INPUT_SET_TARGET_ROOT / RUNTIME_INPUT_RELATIVE_ROOT
RELEASE_RECEIPT_ROOT = Path("/etc/dharma-sadhana/receipts/releases")
STAGED_RELEASE_ADMISSION_FILE = "staged-release-admission.v1.json"
STAGED_RELEASE_BUILD_RECEIPT_FILE = "isolated-build.v1.json"
STAGED_RELEASE_TRACKED_LEDGER_FILE = "tracked-source.manifest.json"
STAGED_RELEASE_ADMISSION_SCHEMA_VERSION = (
    "dharma.sadhana.staged_release_admission.v1"
)
PREPARED_RELEASE_ADMISSION_PROJECTION = (
    Path(STATE_ROOT) / "release-admission" / STAGED_RELEASE_ADMISSION_FILE
)
PREPARED_RUNTIME_MANIFEST_ROOT = Path(STATE_ROOT) / "prepared-runtime-manifests"
RUNTIME_PREPARATION_ENV_FILE = "runtime-prep.env"
RUNTIME_PREPARATION_INPUT_PATHS = {
    "contracts": "contracts/goal-contracts.v1.json",
    "roster": "contracts/agent-roster.v1.json",
    "observed_source": (
        "runtime/sadhana-10-20260823/observed-inputs.source.json"
    ),
    "evaluator": "runtime/sadhana-10-20260823/held-out/g10-evaluator.py",
    "policy": "runtime/sadhana-10-20260823/held-out/g10-policy.json",
    "operator_control_semantics": "contracts/operator-control-semantics.v1.json",
    "operator_control_authority_binding": (
        "contracts/operator-control-authority-binding.v1.json"
    ),
    "deployment_authority_topology": (
        "contracts/deployment-authority-topology.v1.json"
    ),
    "deployment_authority_credential_clarification": (
        "contracts/deployment-authority-topology-credential-clarification.v4.json"
    ),
}
RUNTIME_PREPARATION_RECEIPT = (
    Path(STATE_ROOT) / "receipts/sadhana-runtime-preparation.v1.json"
)
RUNTIME_PREPARATION_SCHEMA_VERSION = "dharma.sadhana.runtime_preparation.v1"
RUNTIME_BINDING_RECEIPT_TARGET = Path(
    "/etc/dharma-sadhana/receipts/runtime/sadhana-10-20260823/"
    "runtime-binding-activation.v2.json"
)
RUNTIME_BINDING_SCHEMA_VERSION = "dharma.sadhana.runtime_binding_activation.v2"
AUTHORITY_MANIFEST_SCHEMA_VERSION = (
    "dharma.sadhana.campaign_authority_manifest.v4"
)
RUNTIME_INPUT_SCHEMAS: dict[str, str | None] = {
    "observed-inputs.json": "dharma.sadhana.observed_input_manifest.v1",
    "held-out-oracle.json": "dharma.sadhana.held_out_oracle_manifest.v1",
    "authority-manifest.json": AUTHORITY_MANIFEST_SCHEMA_VERSION,
}
DEPLOYMENT_KNOWN_HOSTS_FILE = "deployment-known-hosts"
DEPLOYMENT_KNOWN_HOSTS_SHA256 = (
    "26abf6943e7965d3139cd1e635fc9b50b10cd6b5b649d7e09d0ca764e513803d"
)
OBJECTIVE_INPUT_PATH = "contracts/SADHANA_10_GOAL_PROMPT_2026-08-23.md"
OBJECTIVE_SHA256 = "1d4d2ad5f8a744212cb65ba46bdb4993eafc152c6837e3cf73cb7d080c370f2b"
REQUIRED_INPUT_TARGETS = frozenset(
    {
        OBJECTIVE_INPUT_PATH,
        "approvals/day-01-publication-request.v1.json",
        "audits/day-01-program-stewardship.v1.json",
        "audits/day-01-telos-audit.v1.json",
        "audits/g10-effect-ledger-through-20260823T001249Z.v1.json",
        "bootstrap/bootstrap-truth.v1.json",
        "bootstrap/provider-inventory.v1.json",
        "contracts/agent-roster.v1.json",
        "contracts/capability-warrants.v1.json",
        "contracts/deployment-authority-topology.v1.json",
        "contracts/deployment-authority-topology-port-supersession.v2.json",
        "contracts/deployment-authority-topology-unix-supersession.v3.json",
        "contracts/deployment-authority-topology-credential-clarification.v4.json",
        "contracts/goal-contracts.v1.json",
        "contracts/operator-control-semantics.v1.json",
        "contracts/operator-control-http-binding.v1.json",
        "contracts/operator-control-authority-binding.v1.json",
        "contracts/telos-constitution.v1.json",
        "incidents/tplus6-accepted-model-task-miss-20260823T002234Z.v1.json",
        "receipts/bootstrap-seal.v1.json",
        "receipts/controller-host-preflight-20260823T0032Z.v1.json",
        "receipts/controller-clock-preflight-20260823T004235Z.v1.json",
        "receipts/darshan-divergence-20260822T234025Z.v1.json",
        "receipts/day-01-stewardship-seal.v1.json",
        "receipts/dashboard-unix-identity-supersession-20260823T020248Z.v1.json",
        "receipts/hermes-triad-orientation-20260822T230555Z.v1.json",
        "receipts/hermes-ingress-audit-20260823T002018Z.v2.json",
        "receipts/g10-oracle-precommit-20260823T002500Z.v2.json",
        "receipts/g10-contract-binding-20260823T001029Z.v1.json",
        "receipts/g10-effect-audit-20260823T001249Z.v1.json",
        "receipts/launch-readiness-20260822T231335Z.v1.json",
        "receipts/launch-readiness-20260822T235432Z.v2.json",
        "receipts/model-council-plan.v1.json",
        "receipts/mobile-tailnet-identity-preflight-20260823T0047Z.v1.json",
        "receipts/operator-control-authority-binding-20260823T0108Z.v1.json",
        "receipts/operator-bearer-custody-clarification-20260823T021313Z.v1.json",
        "receipts/a2a-v1-lifecycle-conformance-20260823T0035Z.v1.json",
        "receipts/pr-graph-orientation-20260822T234417Z.v1.json",
        "receipts/provider-matrix-interpretation.v1.json",
        "receipts/provider-matrix/ollama-seven-family-canary-20260822T2116Z.json",
        "receipts/provider-matrix/provider_matrix_f9a5cae8a691.json",
        "receipts/tailnet-census-20260822T233654Z.v1.json",
        "reports/day-01-field-report-draft.md",
        "runtime/sadhana-10-20260823/observed-inputs.source.json",
        "runtime/sadhana-10-20260823/held-out/g10-evaluator.py",
        "runtime/sadhana-10-20260823/held-out/g10-policy.json",
    }
)
REQUIRED_INPUT_SHA256 = {
    OBJECTIVE_INPUT_PATH: OBJECTIVE_SHA256,
    "receipts/darshan-divergence-20260822T234025Z.v1.json": (
        "f7d907052b08a7538dd05bc9eefcc7a373081ae137f91aa5c01b2e117f2d919c"
    ),
    "receipts/pr-graph-orientation-20260822T234417Z.v1.json": (
        "6a7e8e06124899bc116d69c34feb4c04e2b38a76f0996ae956b130b2bd3b1e4d"
    ),
    "receipts/tailnet-census-20260822T233654Z.v1.json": (
        "aeaddbaced8fa01c8574c859d0db4bac92cbf6c7b2a6823538bd30043cd5a910"
    ),
    "reports/day-01-field-report-draft.md": (
        "a21fd71b8a8d526185926d955a4cb887c9e2d565d2f9f68c077d38fd948074b7"
    ),
    "receipts/g10-contract-binding-20260823T001029Z.v1.json": (
        "2a543b07c44a1ab8d41ebd3ce824c113cb23e61fd07a4643eadf434b32677e1e"
    ),
    "receipts/g10-oracle-precommit-20260823T002500Z.v2.json": (
        "b6f9eb802527c97a40d205a103a1713ae304d6837a0bd6bcf45218b54a18e320"
    ),
    "audits/g10-effect-ledger-through-20260823T001249Z.v1.json": (
        "243661f57fe308862a7d6b1e9c9dacd5a6a70100abc114cea66a964ce9d451dc"
    ),
    "receipts/g10-effect-audit-20260823T001249Z.v1.json": (
        "d9b0794bc06a4ab6ed4c5b0fbf08dfc066ba6db997ee29918e6cf11e3cb4abb8"
    ),
    "receipts/hermes-ingress-audit-20260823T002018Z.v2.json": (
        "c42efc2adb865562687a419091cd9c5e0eebc97ddf4aac36accca8112348a420"
    ),
    "receipts/launch-readiness-20260822T235432Z.v2.json": (
        "4f507083aa41525f846ac3fd2ba5e91d2c9f8b667475b12657d0e41496442f4d"
    ),
    "incidents/tplus6-accepted-model-task-miss-20260823T002234Z.v1.json": (
        "ecaa8ef3dc25f1c3a7f46dab7fc255be2a4fd4c802efe5d5d0e6cc54e6b0c0ee"
    ),
    "contracts/deployment-authority-topology-port-supersession.v2.json": (
        "102fa8a05583ba63df1546af76953458fada61bb7de066b689dc4d9f888fd6a7"
    ),
    "contracts/deployment-authority-topology-unix-supersession.v3.json": (
        "c97eea10b62803b88f42f6f20eea9560c1600757a9e18216fcd643b2e550dbf6"
    ),
    "contracts/deployment-authority-topology-credential-clarification.v4.json": (
        "b78c581fd1d1768af2bda12eaae2723864cf1de1a53b8802e4d8d08eff784f9a"
    ),
    "receipts/dashboard-unix-identity-supersession-20260823T020248Z.v1.json": (
        "d5570da52bb6adb5868fbed1bc98a0145f3291d05f099b208d9cbb2e32693d1d"
    ),
    "receipts/operator-bearer-custody-clarification-20260823T021313Z.v1.json": (
        "52688ce51c856c6dc966d3f58971f8e686890b91eb80833687ae66a9754d976b"
    ),
    "contracts/operator-control-semantics.v1.json": (
        "69a0eb088277882e333ac41a6fb7014f6ed9d792e6d4a4b2b8510f20de15077c"
    ),
    "contracts/operator-control-http-binding.v1.json": CONTROL_HTTP_BINDING_SHA256,
    "contracts/operator-control-authority-binding.v1.json": (
        CONTROL_AUTHORITY_BINDING_SHA256
    ),
    "receipts/controller-host-preflight-20260823T0032Z.v1.json": (
        "5e2192a523ad6635e5929a38edad591b9e34fe9a56489f49a31fede22e226531"
    ),
    "receipts/controller-clock-preflight-20260823T004235Z.v1.json": (
        "364c5f67fca8357947c25f351a3d8ee90faac76f828b8d917efdf00a1cb357b8"
    ),
    "receipts/a2a-v1-lifecycle-conformance-20260823T0035Z.v1.json": (
        "3a4e214614dc94522119ffc6cd87e031e0884b5438a1c01ffdf0ac5e8656dce0"
    ),
    "receipts/mobile-tailnet-identity-preflight-20260823T0047Z.v1.json": (
        "aa1124aaade427eff5e3e28f9afe08a3425820e3e1f5d01cbdcd0aea34f82664"
    ),
    "receipts/operator-control-authority-binding-20260823T0108Z.v1.json": (
        "0fa5cb66b923e553bf1853134f0d6485db63d86992bbc6323444c0505e0a2bc4"
    ),
    "runtime/sadhana-10-20260823/held-out/g10-evaluator.py": (
        "1cfec1beb9a1d51dbdb31d1b01c7ca9f912664ec729ea55502c7c7ebedf75a18"
    ),
    "runtime/sadhana-10-20260823/held-out/g10-policy.json": (
        "7e368aaabb57424e35b95b87f91b1dd7639a64a1bdf71bb5f4fae83f13890841"
    ),
    "runtime/sadhana-10-20260823/observed-inputs.source.json": (
        "d32cc4733918503494e5e5b479cce52cfbfdf5ceaa3b77a4d9463dc1e0194904"
    ),
}
REVOKED_INPUT_SHA256 = {
    "runtime/sadhana-10-20260823/observed-inputs.source.json": frozenset(
        {
            # Revoked before deployment: disclosed held-out oracle digests in G10.
            "4c60ba84b7e36db12b373bbcefd6b6f34cce8e616b845f24a9e932136057cda1"
        }
    )
}
REQUIRED_INPUT_CONSUMERS = {
    target: "immutable_evidence" for target in REQUIRED_INPUT_TARGETS
}
REQUIRED_INPUT_CONSUMERS.update(
    {
        "contracts/agent-roster.v1.json": "roster_loader",
        "contracts/goal-contracts.v1.json": "bootstrap_goal_loader",
        "runtime/sadhana-10-20260823/observed-inputs.source.json": (
            "observed_input_loader"
        ),
        "runtime/sadhana-10-20260823/held-out/g10-evaluator.py": "oracle_loader",
        "runtime/sadhana-10-20260823/held-out/g10-policy.json": "oracle_loader",
    }
)
INPUT_SOURCE_OVERRIDES = {
    "runtime/sadhana-10-20260823/observed-inputs.source.json": (
        "observed-inputs.source.json"
    ),
    "runtime/sadhana-10-20260823/held-out/g10-evaluator.py": (
        "held-out/g10-evaluator.py"
    ),
    "runtime/sadhana-10-20260823/held-out/g10-policy.json": (
        "held-out/g10-policy.json"
    ),
}
_SHA_RE = re.compile(r"[0-9a-f]{64}")
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_PACKET_PATH_RE = re.compile(
    r"reports/agentops/work_packets/[A-Za-z0-9][A-Za-z0-9._-]{1,199}\.json"
)
_BASENAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")
_STABLE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@-]{0,199}")
_ENV_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")
_ED25519_COMMENT_RE = re.compile(r"[A-Za-z0-9_.@-]{1,128}")
_MAX_JSON_BYTES = 4 * 1024 * 1024
_MAX_STANDBY_CAPACITY_PROOF_BYTES = 1024 * 1024
_STANDBY_CAPACITY_LEDGER_ENTRY_BYTES = 213
_STANDBY_CAPACITY_FIXED_ENVELOPE_ALLOWANCE_BYTES = 6_976
_MAX_ARTIFACT_BYTES = 4 * 1024 * 1024 * 1024
_MAX_UV_WHEEL_BYTES = 64 * 1024 * 1024
_MAX_UV_BINARY_BYTES = 64 * 1024 * 1024
_MAX_TAILSCALE_CONFIG_BYTES = 256 * 1024
_MAX_TAILSCALE_VERSION_BYTES = 4096
_MAX_INPUT_FILE_BYTES = 32 * 1024 * 1024
_MAX_INPUT_SET_BYTES = 256 * 1024 * 1024
_MAX_TRACKED_SOURCE_MANIFEST_BYTES = 4 * 1024 * 1024
_MAX_TRACKED_SOURCE_ENTRIES = 100_000
_MAX_TRACKED_SOURCE_BYTES = 16 * 1024 * 1024 * 1024
_INPUT_MANIFEST_FIELDS = {
    "schema_version",
    "mission_id",
    "objective_sha256",
    "target_root",
    "entries",
    "input_set_digest",
}
_TRACKED_SOURCE_MANIFEST_FIELDS = {
    "schema_version",
    "release_sha",
    "canonical_origin",
    "git_object_format",
    "entries",
    "tracked_entry_count",
    "tracked_bytes",
    "build_output_roots",
    "manifest_digest",
}
_TRACKED_SOURCE_ENTRY_FIELDS = {
    "path",
    "kind",
    "git_mode",
    "git_object_id",
    "size_bytes",
    "sha256",
}
_RUNTIME_BINDING_FIELDS = {
    "schema_version",
    "campaign_id",
    "mission_id",
    "release_sha",
    "created_at",
    "service_uid",
    "service_gid",
    "release_admission_receipt_digest",
    "release_input_set_digest",
    "preparation_receipt_digest",
    "preparation_input_digest",
    "config_digest",
    "supervisor_runtime_env_sha256",
    "task_set_digest",
    "manifest_set_digest",
    "session_generation",
    "session_status",
    "prepared_proof_type",
    "prepared_effect",
    "root_verification_type",
    "files",
    "receipt_digest",
}
_RUNTIME_BINDING_FILE_FIELDS = {
    "absolute_path",
    "prepared_source_path",
    "schema_version",
    "manifest_digest",
    "prepared_file_sha256",
    "file_sha256",
    "size_bytes",
    "uid",
    "mode",
}
_STAGED_RELEASE_ADMISSION_FIELDS = {
    "schema_version",
    "release_sha",
    "release_root",
    "tracked_source_manifest_digest",
    "tracked_source_manifest_sha256",
    "tracked_entry_count",
    "tracked_bytes",
    "isolated_build_receipt_sha256",
    "release_input_set_digest",
    "git_metadata_present",
    "frozen_tree",
    "candidate_code_executed_as_root",
    "receipt_digest",
}
_RUNTIME_PREPARATION_ENV_FIELDS = {
    "SADHANA_PREP_RELEASE_ROOT",
    "SADHANA_PREP_RELEASE_SHA",
    "SADHANA_PREP_RELEASE_INPUT_SET_DIGEST",
    "SADHANA_PREP_RELEASE_ADMISSION_RECEIPT",
    "SADHANA_PREP_CONTRACTS",
    "SADHANA_PREP_OBSERVED_SOURCE",
    "SADHANA_PREP_ROSTER",
    "SADHANA_PREP_ROSTER_SHA256",
    "SADHANA_PREP_OBJECTIVE_SHA256",
    "SADHANA_PREP_STATE_DIR",
    "SADHANA_PREP_PROJECTION_PATH",
    "SADHANA_PREP_MANIFEST_STAGING_ROOT",
    "SADHANA_PREP_OPERATOR_ID",
    "SADHANA_PREP_MAX_DISPATCH_PER_CYCLE",
    "SADHANA_PREP_CYCLE_INTERVAL_SECONDS",
    "SADHANA_PREP_FRESHNESS_SECONDS",
    "SADHANA_PREP_VERIFIER_SEAT",
    "SADHANA_PREP_EVALUATOR_PATH",
    "SADHANA_PREP_EVALUATOR_SHA256",
    "SADHANA_PREP_POLICY_PATH",
    "SADHANA_PREP_POLICY_SHA256",
    "SADHANA_PREP_OPERATOR_CONTROL_SEMANTICS_SHA256",
    "SADHANA_PREP_OPERATOR_CONTROL_AUTHORITY_BINDING_SHA256",
    "SADHANA_PREP_DEPLOYMENT_AUTHORITY_TOPOLOGY_SHA256",
    "SADHANA_PREP_DEPLOYMENT_AUTHORITY_CREDENTIAL_CLARIFICATION_SHA256",
}
_STATIC_SUPERVISOR_ENV_FIELDS = {
    "SADHANA_WRITER_LOCK_PATH",
    "SADHANA_PROJECTION_PATH",
    "SADHANA_OPERATOR_ID",
    "SADHANA_MAX_DISPATCH_PER_CYCLE",
    "SADHANA_CYCLE_INTERVAL_SECONDS",
    "SADHANA_FRESHNESS_SECONDS",
    "SADHANA_LEASE_ROOT",
    "SADHANA_AGENT_ROSTER_PATH",
    "SADHANA_AGENT_ROSTER_SHA256",
    "SADHANA_OBJECTIVE_SHA256",
}
_ISOLATED_BUILD_RECEIPT_FIELDS = {
    "schema_version",
    "release_sha",
    "build_uid",
    "build_gid",
    "no_new_privileges",
    "solo_cgroup_process",
    "build_process_dumpable",
    "runtime_max_seconds",
    "tasks_max",
    "memory_max_bytes",
    "commands",
    "manifest_sha256",
    "build_driver_sha256",
    "candidate_code_executed_as_root",
    "post_exit_build_uid_process_count",
}
_OBSERVER_HEALTH_RECEIPT_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "service_unit_digest",
    "endpoint",
    "probe_started_at",
    "probe_finished_at",
    "consecutive_successes",
    "response_sha256_sequence",
    "listener_process_identity",
    "dispatch_enabled_during_probe",
    "observer_identity_separated",
    "projection_source_separated",
    "canonical_paths_inaccessible",
    "health_is_work_evidence",
    "verdict",
    "receipt_digest",
}
_OBSERVER_LISTENER_FIELDS = {
    "unit",
    "main_pid",
    "proc_start_ticks",
    "cmdline_sha256",
    "socket_inode",
    "uid",
    "gid",
    "forbidden_path_count",
    "canonical_path_visible",
    "release_sha",
}
_DASHBOARD_IDENTITY_RECEIPT_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "dashboard_unit_digest",
    "tailscale_version",
    "serve_status_before_sha256",
    "serve_status_after_sha256",
    "serve_upstream",
    "socket_stat",
    "dashboard_process_identity",
    "negative_access_matrix",
    "tcp_listener_inventory",
    "funnel_absence",
    "operator_login_sha256",
    "authenticated_account_ui_confirmation",
    "rollback_probe",
    "verdict",
    "receipt_digest",
}
_ACCOUNT_UI_CONFIRMATION_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "client_request_id_sha256",
    "source_candidate_sha256",
    "viewport_width_css_px_reported",
    "document_width_css_px_reported",
    "visual_viewport_width_css_px_reported",
    "coarse_pointer_reported",
    "touch_capability_reported",
    "trusted_browser_event_reported",
    "explicit_confirmation_gesture_reported",
    "dashboard_rendered_reported",
    "private_tailnet_https",
    "identity_header_injected",
    "operator_account_allowlist_match",
    "operator_login_sha256",
    "normal_control_request_sent",
    "external_message_sent",
    "physical_device_attested",
    "human_identity_attested",
    "predispatch_gate_receipt_digest",
    "normal_and_emergency_inbox_ledger_sha256_before",
    "normal_and_emergency_inbox_ledger_sha256_after",
    "normal_and_emergency_inboxes_unchanged",
    "observed_at",
    "receipt_digest",
}
_ACCOUNT_UI_CONFIRMATION_CANDIDATE_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "client_request_id",
    "issued_at",
    "expires_at",
    "viewport_width_css_px_reported",
    "document_width_css_px_reported",
    "visual_viewport_width_css_px_reported",
    "coarse_pointer_reported",
    "touch_capability_reported",
    "trusted_browser_event_reported",
    "explicit_confirmation_gesture_reported",
    "dashboard_rendered_reported",
    "origin",
    "operator_login_sha256",
    "private_tailnet_https",
    "identity_header_injected",
    "operator_account_allowlist_match",
    "normal_control_request_sent",
    "external_message_sent",
    "physical_device_attested",
    "human_identity_attested",
    "predispatch_gate_receipt_digest",
    "normal_inbox_empty_ledger_sha256",
    "emergency_inbox_empty_ledger_sha256",
    "control_inboxes_empty_at_last_prepublication_scan",
    "observed_at",
    "hmac_sha256",
}
_PREDISPATCH_ACCOUNT_UI_GATE_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "activated_at",
    "predispatch_activation_receipt_digest",
    "dispatch_marker_absent",
    "dispatch_target_inactive",
    "supervisor_main_pid",
    "provider_dispatch",
    "receipt_digest",
}
_DISPATCH_ACTIVATION_SOURCE_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "dispatch_enable_receipt_digest",
    "dashboard_identity_receipt_digest",
    "account_ui_confirmation_receipt_digest",
    "runtime_binding_receipt_digest",
    "config_digest",
    "session_id",
    "campaign_generation",
    "transition_sequence",
    "prior_control_state",
    "next_control_state",
    "operator_login_sha256",
    "effect",
}
_OPERATOR_CREDENTIAL_RECEIPT_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "dashboard_unit_digest",
    "control_unit_digest",
    "source_file_custody",
    "dashboard_credential_custody",
    "control_credential_custody",
    "credential_copies_equal",
    "negative_reader_matrix",
    "secret_sink_scan",
    "verdict",
    "receipt_digest",
}
_POSITIVE_BEARER_PROBE_FIELDS = {
    "probe_kind",
    "authenticated_unsupported_response_observed",
    "connected_dashboard_peer_identity_proven",
    "normal_and_emergency_inboxes_unchanged",
    "request_accepted",
    "decision_or_effect_state_proven",
}
_RUNTIME_STAGING_RECEIPT_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "dispatch_process_count",
    "env_file_names",
    "scoped_runtime_files_verified",
    "runtime_binding_receipt_digest",
    "control_credentials_present",
    "verifier_secret_present",
    "verdict",
    "receipt_digest",
}
_PREDISPATCH_REFRESH_RECEIPT_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "hostname",
    "refreshed_at",
    "valid_until",
    "staged_release_admission_receipt_digest",
    "runtime_binding_receipt_digest",
    "preparation_receipt_digest",
    "projection_contract_digest",
    "config_digest",
    "projection_path",
    "observer_projection_path",
    "observer_projection_sha256",
    "global_dispatch_rows_empty",
    "provider_dispatch",
    "preparation_unit_static",
    "supervisor_main_pid",
    "receipt_digest",
}
_DISPATCH_ENABLE_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "enabled_at",
    "predispatch_target_active",
    "supervisor_main_pid_before_enable",
    "observer_health_receipt_digest",
    "dashboard_identity_receipt_digest",
    "operator_credential_receipt_digest",
    "runtime_staging_receipt_digest",
    "runtime_binding_receipt_digest",
    "predispatch_refresh_receipt_digest",
    "standby_capacity_receipt_digest",
    "preactivation_clock_proof_receipt_digest",
    "oracle_sandbox_evidence_digest",
    "standby_replication_route_probe_receipt_digest",
    "supervisor_activation_env_sha256",
    "dispatch_authorized",
    "effect_executed",
    "receipt_digest",
}
_PREDISPATCH_ACTIVATION_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "activated_at",
    "activation_intent_receipt_digest",
    "staged_release_admission_receipt_digest",
    "preactivation_clock_proof_receipt_digest",
    "runtime_binding_receipt_digest",
    "runtime_staging_receipt_digest",
    "tailscale_intent_receipt_digest",
    "tailscale_ownership_receipt_digest",
    "writer_marker_present",
    "campaign_stop_timer_active",
    "campaign_stop_timer_enabled",
    "emergency_recovery_path_active",
    "emergency_recovery_path_enabled",
    "predispatch_target_active",
    "predispatch_target_enabled",
    "dispatch_marker_absent",
    "dispatch_target_inactive",
    "supervisor_main_pid",
    "proof_type",
    "effect",
    "provider_dispatch",
    "receipt_digest",
}
_PREDISPATCH_ACTIVATION_INTENT_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "created_at",
    "preactivation_clock_proof_receipt_digest",
    "writer_marker_absent_before",
    "campaign_stop_timer_inactive_before",
    "campaign_stop_timer_disabled_before",
    "emergency_recovery_path_inactive_before",
    "emergency_recovery_path_disabled_before",
    "predispatch_target_inactive_before",
    "predispatch_target_disabled_before",
    "dispatch_marker_absent_before",
    "dispatch_target_inactive_before",
    "supervisor_main_pid_before",
    "effect_intent",
    "provider_dispatch",
    "receipt_digest",
}
_ROLLBACK_RECEIPT_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "rolled_back_at",
    "dispatch_target_static_and_inactive",
    "predispatch_target_disabled",
    "partof_units_inactive",
    "campaign_listeners_absent",
    "owned_serve_removed",
    "writer_marker_removed",
    "release_tree_retained",
    "snapshots_retained",
    "authority_transferred",
    "receipt_digest",
}
_PREACTIVATION_CLOCK_PROOF_FIELDS = {
    "schema_version",
    "mission_id",
    "release_sha",
    "staged_release_admission_receipt_digest",
    "role",
    "hostname",
    "controller_utc",
    "host_utc",
    "skew_seconds",
    "max_skew_seconds",
    "ntp_synchronized",
    "strict_host_key_channel",
    "ssh_connection_observed",
    "known_hosts_sha256",
    "campaign_stop_utc",
    "timer_unit",
    "timer_on_calendar",
    "timer_accuracy_seconds",
    "timer_persistent",
    "release_timer_sha256",
    "installed_timer_match",
    "valid_until",
    "receipt_digest",
}
_STANDBY_ACTIVATION_INTENT_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "created_at",
    "staged_release_admission_receipt_digest",
    "preactivation_clock_proof_receipt_digest",
    "writer_marker_absent_before",
    "campaign_units_mask_requested",
    "standby_target_inactive_before",
    "standby_target_disabled_before",
    "standby_stop_timer_inactive_before",
    "standby_stop_timer_disabled_before",
    "standby_replication_serve_inactive_before",
    "standby_replication_route_absent_before",
    "effect_intent",
    "writer_authority_transferred",
    "receipt_digest",
}
_STANDBY_ACTIVATION_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "activated_at",
    "activation_intent_receipt_digest",
    "staged_release_admission_receipt_digest",
    "preactivation_clock_proof_receipt_digest",
    "campaign_units_masked_and_inactive",
    "standby_stop_timer_active",
    "standby_stop_timer_enabled",
    "standby_target_active",
    "standby_target_enabled",
    "standby_replication_serve_active",
    "standby_replication_serve_owned",
    "standby_replication_serve_ownership_receipt_digest",
    "standby_replication_route_end_to_end_verified",
    "writer_marker_absent",
    "writer_authority_transferred",
    "effect",
    "receipt_digest",
}
_STANDBY_STOP_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "stopped_at",
    "standby_target_disabled",
    "receiver_path_inactive",
    "receiver_timer_inactive",
    "receiver_service_inactive",
    "replication_serve_unit_inactive",
    "replication_serve_stop_receipt_digest",
    "replication_route_absent",
    "writer_authority_transferred",
    "receipt_digest",
}
_STANDBY_TAILSCALE_INTENT_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "route",
    "tailnet_port",
    "local_endpoint",
    "tailscale_version",
    "serve_status_before_sha256",
    "named_config_before_sha256",
    "end_to_end_route_verified",
    "effect_intent",
    "receipt_digest",
}
_STANDBY_TAILSCALE_OWNERSHIP_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "route",
    "tailnet_port",
    "local_endpoint",
    "tailscale_version",
    "intent_receipt_digest",
    "serve_status_before_sha256",
    "config_sha256",
    "config",
    "end_to_end_route_verified",
    "effect",
    "receipt_digest",
}
_STANDBY_TAILSCALE_STOP_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "tailnet_port",
    "ownership_receipt_digest",
    "prestate_sha256",
    "poststate_sha256",
    "named_config_sha256",
    "owned_handler_removed",
    "effect",
    "receipt_digest",
}
_STANDBY_REPLICATION_ROUTE_PROBE_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "observed_at",
    "valid_until",
    "destination",
    "tailnet_port",
    "known_hosts_sha256",
    "bracketed_host_key_sha256",
    "ssh_transport_policy_sha256",
    "standby_serve_ownership_receipt_digest",
    "probe_sequence",
    "previous_receipt_digest",
    "keyscan_host_pin_exact",
    "dry_run_rsync_succeeded",
    "arbitrary_command_rejected",
    "interactive_shell_rejected",
    "out_of_root_rsync_rejected",
    "remote_state_mutation_performed",
    "route_verified",
    "verdict",
    "receipt_digest",
}
_DASHBOARD_PROCESS_FIELDS = {
    "unit",
    "main_pid",
    "uid",
    "gid",
    "cmdline_sha256",
    "socket_path",
    "socket_dev",
    "socket_ino",
    "listener_inode",
    "tcp_listener_count",
    "release_sha",
}
_STANDBY_CAPACITY_FIELDS = {
    "schema_version",
    "campaign_id",
    "release_sha",
    "hostname",
    "role",
    "observed_at",
    "valid_until",
    "strict_host_key_channel",
    "deployment_known_hosts_sha256",
    "snapshot_root",
    "snapshot_root_uid",
    "snapshot_root_gid",
    "snapshot_root_mode",
    "source_sizes_bytes",
    "source_bytes",
    "existing_snapshot_entries",
    "snapshot_ledger",
    "zero_existing_snapshot_directories",
    "maximum_campaign_snapshot_count",
    "snapshot_interval_seconds",
    "metadata_allowance_bytes",
    "estimate_headroom_numerator",
    "estimate_headroom_denominator",
    "estimated_bytes_per_snapshot",
    "free_bytes",
    "minimum_free_reserve_bytes",
    "required_free_bytes_for_remaining_series",
    "silent_deletion_allowed",
    "standby_capacity_proven",
    "verdict",
    "receipt_digest",
}
_STANDBY_SOURCE_SIZE_FIELDS = {"runtime_db", "tasks_db", "projection"}
_STANDBY_SNAPSHOT_LEDGER_FIELDS = {"snapshot_id", "snapshot_digest", "tree_digest"}
_CAMPAIGN_ACTIVATION_PROOF_FIELDS = {
    "schema_version",
    "mission_id",
    "release_sha",
    "config_digest",
    "campaign_generation",
    "transition_sequence",
    "control_state",
    "action",
    "dispatch_enable_receipt_digest",
    "account_ui_confirmation_receipt_digest",
    "operator_login_sha256",
    "authority_receipt_ref",
    "authority_receipt_sha256",
    "activated_at",
    "external_effect_performed",
    "receipt_digest",
}
_EMERGENCY_RECEIPT_FIELDS = {
    "schema_version",
    "campaign_id",
    "control_semantics_sha256",
    "control_http_binding_sha256",
    "control_authority_binding_sha256",
    "request_id",
    "idempotency_key",
    "action",
    "operator_login_matched",
    "envelope_sha256",
    "status",
    "error_code",
    "target_stop_requested_at",
    "target_inactive_observed_at",
    "target_inactive",
    "partof_units_inactive",
    "campaign_listeners_absent",
    "durable_stop_marker_persisted",
    "authority_applied",
    "effect_observed",
    "receipt_digest",
}
_EMERGENCY_REJECTION_FIELDS = {
    "schema_version",
    "campaign_id",
    "control_semantics_sha256",
    "control_http_binding_sha256",
    "control_authority_binding_sha256",
    "candidate_name_sha256",
    "candidate_identity_digest",
    "status",
    "error_code",
    "quarantine_entry",
    "quarantined",
    "target_stop_requested",
    "authority_applied",
    "effect_observed",
    "rejected_at",
    "receipt_digest",
}
_EMERGENCY_CLAIM_FIELDS = {
    "schema_version",
    "campaign_id",
    "control_semantics_sha256",
    "control_http_binding_sha256",
    "control_authority_binding_sha256",
    "original_filename",
    "candidate_identity",
    "envelope_sha256",
    "request_id",
    "idempotency_key",
    "action",
    "claimed_at",
    "claim_digest",
}
_EMERGENCY_CANDIDATE_IDENTITY_FIELDS = {
    "dev",
    "ino",
    "mode",
    "uid",
    "gid",
    "nlink",
    "size",
    "mtime_ns",
}
_EMERGENCY_STOP_MARKER_FIELDS = {
    "schema_version",
    "campaign_id",
    "control_semantics_sha256",
    "control_http_binding_sha256",
    "control_authority_binding_sha256",
    "envelope_sha256",
    "request_id",
    "idempotency_key",
    "stop_request_claimed_at",
    "receipt_digest",
}
_INPUT_ENTRY_FIELDS = {
    "source_relative_path",
    "target_relative_path",
    "sha256",
    "bytes",
    "custody",
    "consumer",
}
_INPUT_CONSUMERS = {
    "authority_loader",
    "bootstrap_goal_loader",
    "immutable_evidence",
    "observed_input_loader",
    "oracle_loader",
    "roster_loader",
}
_INPUT_LOADER_CONSUMERS = _INPUT_CONSUMERS - {"immutable_evidence"}
_INPUT_CUSTODY = {"root_immutable", "service_hash_pinned"}
_CLOCK_GUARDED_UNITS = {
    "dharma-sadhana-dispatch-enable.service",
    "dharma-sadhana-api.service",
    "dharma-sadhana-observer-health.service",
    "dharma-sadhana-control-directories.service",
    "dharma-sadhana-control.service",
    "dharma-sadhana-dashboard.service",
    "dharma-sadhana-private-serve.service",
    "dharma-sadhana-projection-sync.service",
    "dharma-sadhana-snapshot.service",
    "dharma-sadhana-snapshot-finalize.service",
    "dharma-sadhana-supervisor.service",
    "dharma-sadhana-oracle-directories.service",
    "dharma-sadhana-oracle-sandbox-probe.service",
    "dharma-sadhana-oracle-sandbox.service",
}
_TARGET_CESSATION_UNITS = _CLOCK_GUARDED_UNITS | {
    "dharma-sadhana-control-emergency.path",
    "dharma-sadhana-oracle-sandbox.path",
    "dharma-sadhana-oracle-sandbox.timer",
    "dharma-sadhana-snapshot.timer",
    "dharma-sadhana-snapshot-finalize.path",
    "dharma-sadhana-snapshot-retry.timer",
    "dharma-sadhana-projection-sync.timer",
}
_ROLLBACK_QUIET_UNITS = _TARGET_CESSATION_UNITS | {
    RUNTIME_PREPARATION_UNIT,
    "dharma-sadhana-campaign-stop.service",
    "dharma-sadhana-control-emergency.service",
    "dharma-sadhana-control-emergency-recovery.service",
}
_SAFE_SUBPROCESS_ENV = {
    "GIT_ATTR_NOSYSTEM": "1",
    "GIT_CONFIG_COUNT": "3",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_KEY_0": "core.fsmonitor",
    "GIT_CONFIG_KEY_1": "core.hooksPath",
    "GIT_CONFIG_KEY_2": "diff.external",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_VALUE_0": "false",
    "GIT_CONFIG_VALUE_1": "/dev/null",
    "GIT_CONFIG_VALUE_2": "",
    "GIT_NO_REPLACE_OBJECTS": "1",
    "GIT_OPTIONAL_LOCKS": "0",
    "HOME": "/nonexistent",
    "LANG": "C",
    "LC_ALL": "C",
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
}

_MANIFEST_FIELDS = {
    "schema_version",
    "mission_id",
    "campaign_start_utc",
    "campaign_stop_utc",
    "cash_budget_usd",
    "release_class",
    "canonical_or_merged",
    "release_sha",
    "canonical_origin",
    "accepted_base_sha",
    "integration_base_sha",
    "bundle_file",
    "bundle_sha256",
    "work_packet_path",
    "work_packet_sha256",
    "work_packet_digest",
    "closeout_receipt_file",
    "closeout_receipt_sha256",
    "writer_node",
    "standby_node",
    "api_listen",
    "dashboard_listen",
    "tailscale_exposure",
    "automatic_failover",
    "standby_writer_enabled",
    "python_version",
    "venv_copies",
    "release_root",
    "state_root",
    "workspace_root",
    "api_state_root",
    "snapshot_root",
    "env_files",
    "uv_version",
    "uv_wheel_file",
    "uv_wheel_sha256",
    "input_set_manifest_file",
    "input_set_manifest_sha256",
    "input_set_archive_file",
    "input_set_archive_sha256",
    "input_set_digest",
    "deployment_known_hosts_file",
    "deployment_known_hosts_sha256",
    "tracked_source_manifest_file",
    "tracked_source_manifest_sha256",
    "tracked_source_digest",
    "tracked_source_entry_count",
    "manifest_digest",
}


class ReleaseContractError(RuntimeError):
    """The candidate envelope or host state does not satisfy the contract."""


class InvalidEmergencyCandidate(ReleaseContractError):
    """One untrusted emergency inbox entry failed shared admission."""


class EmergencyMarkerPersistenceError(ReleaseContractError):
    """The post-cessation emergency marker could not be durably published."""


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _canonical_bytes(payload: Mapping[str, Any], *, omit_digest: bool = False) -> bytes:
    canonical = dict(payload)
    if omit_digest:
        canonical.pop("manifest_digest", None)
    try:
        encoded = json.dumps(
            canonical,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ReleaseContractError("manifest is not canonical JSON") from exc
    return encoded.encode("ascii")


def manifest_digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(payload, omit_digest=True)).hexdigest()


def _input_set_digest(payload: Mapping[str, Any]) -> str:
    canonical = dict(payload)
    canonical.pop("input_set_digest", None)
    return hashlib.sha256(_canonical_bytes(canonical)).hexdigest()


def _input_relative_path(
    value: Any,
    field: str,
    *,
    minimum_parts: int = 2,
) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ReleaseContractError(f"{field} must be a canonical relative path")
    candidate = PurePosixPath(value)
    if (
        candidate.is_absolute()
        or str(candidate) != value
        or any(part in {"", ".", ".."} for part in candidate.parts)
        or len(candidate.parts) < minimum_parts
        or len(value) > 512
        or any(
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._@+-]{0,199}", part)
            for part in candidate.parts
        )
    ):
        raise ReleaseContractError(f"{field} must be a canonical relative path")
    return value


def validate_input_set_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a closed, hash-pinned set of non-secret campaign inputs."""
    if set(payload) != _INPUT_MANIFEST_FIELDS:
        raise ReleaseContractError("input-set manifest fields differ")
    if (
        payload.get("schema_version") != INPUT_SET_SCHEMA_VERSION
        or payload.get("mission_id") != MISSION_ID
        or payload.get("objective_sha256") != OBJECTIVE_SHA256
        or payload.get("target_root") != str(INPUT_SET_TARGET_ROOT)
    ):
        raise ReleaseContractError("input-set manifest exact bindings differ")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ReleaseContractError("input-set entries must be a nonempty list")
    normalized: list[dict[str, Any]] = []
    source_paths: set[str] = set()
    target_paths: set[str] = set()
    total_bytes = 0
    for raw in entries:
        if not isinstance(raw, dict) or set(raw) != _INPUT_ENTRY_FIELDS:
            raise ReleaseContractError("input-set entry fields differ")
        source = _input_relative_path(
            raw.get("source_relative_path"),
            "source_relative_path",
            minimum_parts=1,
        )
        target = _input_relative_path(
            raw.get("target_relative_path"), "target_relative_path"
        )
        if source in source_paths or target in target_paths:
            raise ReleaseContractError("input-set paths must be unique")
        source_paths.add(source)
        target_paths.add(target)
        digest = _require_hash(raw.get("sha256"), "input entry sha256")
        size = raw.get("bytes")
        if (
            isinstance(size, bool)
            or not isinstance(size, int)
            or not 0 < size <= _MAX_INPUT_FILE_BYTES
        ):
            raise ReleaseContractError("input entry byte count is outside its bound")
        total_bytes += size
        custody = raw.get("custody")
        consumer = raw.get("consumer")
        if custody not in _INPUT_CUSTODY or consumer not in _INPUT_CONSUMERS:
            raise ReleaseContractError("input entry custody or consumer is unknown")
        expected_custody = (
            "service_hash_pinned"
            if consumer in _INPUT_LOADER_CONSUMERS
            else "root_immutable"
        )
        if custody != expected_custody:
            raise ReleaseContractError(
                "input entry custody does not match its declared consumer"
            )
        normalized.append(
            {
                "source_relative_path": source,
                "target_relative_path": target,
                "sha256": digest,
                "bytes": size,
                "custody": custody,
                "consumer": consumer,
            }
        )
    if total_bytes > _MAX_INPUT_SET_BYTES:
        raise ReleaseContractError("input set exceeds its aggregate byte bound")
    if target_paths != set(REQUIRED_INPUT_TARGETS):
        raise ReleaseContractError("input-set target set differs from the campaign set")
    consumers = {
        entry["target_relative_path"]: entry["consumer"] for entry in normalized
    }
    if consumers != REQUIRED_INPUT_CONSUMERS:
        raise ReleaseContractError("input-set target consumers differ")
    pinned = {entry["target_relative_path"]: entry["sha256"] for entry in normalized}
    if any(
        pinned.get(path) in revoked for path, revoked in REVOKED_INPUT_SHA256.items()
    ):
        raise ReleaseContractError("input set contains a revoked campaign input")
    if any(
        pinned.get(path) != digest for path, digest in REQUIRED_INPUT_SHA256.items()
    ):
        raise ReleaseContractError("input set differs from a pinned campaign input")
    if normalized != sorted(
        normalized, key=lambda entry: entry["target_relative_path"]
    ):
        raise ReleaseContractError("input-set entries must use canonical target order")
    digest = _require_hash(payload.get("input_set_digest"), "input_set_digest")
    if digest != _input_set_digest(payload):
        raise ReleaseContractError("input-set manifest self-digest mismatch")
    return dict(payload)


def _reject_input_secret_markers(raw: bytes) -> None:
    lowered = raw.lower()
    forbidden = (
        b"ollama_api_key=",
        b"openai_api_key=",
        b"anthropic_api_key=",
        b"-----begin open" + b"ssh private key-----",
        b"-----begin " + b"private key-----",
        b"authorization: bearer ",
    )
    if any(marker in lowered for marker in forbidden):
        raise ReleaseContractError("input set contains forbidden secret material")


def _read_input_source(
    path: Path, *, expected_bytes: int, expected_uid: int | None = None
) -> bytes:
    _require_secure_parent_chain(path)
    try:
        identity = path.lstat()
    except OSError as exc:
        raise ReleaseContractError(
            f"input-set source is unavailable: {path.name}"
        ) from exc
    admitted_uid = os.geteuid() if expected_uid is None else expected_uid
    if (
        not stat.S_ISREG(identity.st_mode)
        or path.is_symlink()
        or identity.st_uid != admitted_uid
        or identity.st_nlink != 1
        or stat.S_IMODE(identity.st_mode) & 0o022
        or identity.st_size != expected_bytes
    ):
        raise ReleaseContractError(f"input-set source lacks exact custody: {path.name}")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ReleaseContractError("platform lacks no-follow input admission")
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino, opened.st_size) != (
            identity.st_dev,
            identity.st_ino,
            identity.st_size,
        ):
            raise ReleaseContractError("input-set source changed during open")
        raw = b""
        while len(raw) <= expected_bytes:
            chunk = os.read(descriptor, min(65_536, expected_bytes + 1 - len(raw)))
            if not chunk:
                break
            raw += chunk
    finally:
        os.close(descriptor)
    if len(raw) != expected_bytes:
        raise ReleaseContractError("input-set source length differs")
    _reject_input_secret_markers(raw)
    return raw


def _read_deployment_known_hosts(path: Path) -> bytes:
    """Admit an already-authorized public host-key file without creating trust."""
    source = path.expanduser()
    if not source.is_absolute():
        raise ReleaseContractError("deployment known_hosts path must be absolute")
    try:
        identity = source.lstat()
    except OSError as exc:
        raise ReleaseContractError("deployment known_hosts is unavailable") from exc
    if not 0 < identity.st_size <= 1024 * 1024:
        raise ReleaseContractError("deployment known_hosts size is invalid")
    raw = _read_input_source(source, expected_bytes=identity.st_size)
    if b"\x00" in raw or b"\r" in raw or not raw.endswith(b"\n"):
        raise ReleaseContractError("deployment known_hosts bytes are not canonical")
    lines = [line for line in raw.splitlines() if line and not line.startswith(b"#")]
    if not lines or any(len(line.split()) < 3 for line in lines):
        raise ReleaseContractError(
            "deployment known_hosts has no pinned host-key entry"
        )
    return raw


def validate_input_set_sources(
    payload: Mapping[str, Any], source_root: Path
) -> dict[str, bytes]:
    manifest = validate_input_set_manifest(payload)
    source_root = source_root.expanduser()
    if not source_root.is_absolute() or source_root.is_symlink():
        raise ReleaseContractError(
            "input-set source root must be an absolute directory"
        )
    _require_secure_parent_chain(source_root / ".custody-check")
    root_identity = source_root.lstat()
    if (
        not stat.S_ISDIR(root_identity.st_mode)
        or root_identity.st_uid != os.geteuid()
        or stat.S_IMODE(root_identity.st_mode) & 0o022
    ):
        raise ReleaseContractError("input-set source root lacks exact custody")
    admitted: dict[str, bytes] = {}
    for entry in manifest["entries"]:
        source = source_root.joinpath(
            *PurePosixPath(entry["source_relative_path"]).parts
        )
        raw = _read_input_source(source, expected_bytes=entry["bytes"])
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ReleaseContractError("input-set source hash differs")
        admitted[entry["target_relative_path"]] = raw
    return admitted


def render_static_input_set_manifest(source_root: Path) -> dict[str, Any]:
    """Render the closed pre-bootstrap input manifest from canonical source bytes."""
    root = source_root.expanduser()
    if not root.is_absolute() or root.is_symlink():
        raise ReleaseContractError(
            "input-set source root must be an absolute directory"
        )
    _require_secure_parent_chain(root / ".custody-check")
    identity = root.lstat()
    if (
        not stat.S_ISDIR(identity.st_mode)
        or identity.st_uid != os.geteuid()
        or stat.S_IMODE(identity.st_mode) & 0o022
    ):
        raise ReleaseContractError("input-set source root lacks exact custody")
    entries: list[dict[str, Any]] = []
    for target in sorted(REQUIRED_INPUT_TARGETS):
        source = INPUT_SOURCE_OVERRIDES.get(target, target)
        source_path = root.joinpath(*PurePosixPath(source).parts)
        try:
            source_identity = source_path.lstat()
        except OSError as exc:
            raise ReleaseContractError(
                f"canonical input source is unavailable: {Path(source).name}"
            ) from exc
        raw = _read_input_source(
            source_path,
            expected_bytes=source_identity.st_size,
        )
        consumer = REQUIRED_INPUT_CONSUMERS[target]
        entries.append(
            {
                "source_relative_path": source,
                "target_relative_path": target,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "custody": (
                    "service_hash_pinned"
                    if consumer in _INPUT_LOADER_CONSUMERS
                    else "root_immutable"
                ),
                "consumer": consumer,
            }
        )
    payload: dict[str, Any] = {
        "schema_version": INPUT_SET_SCHEMA_VERSION,
        "mission_id": MISSION_ID,
        "objective_sha256": OBJECTIVE_SHA256,
        "target_root": str(INPUT_SET_TARGET_ROOT),
        "entries": entries,
        "input_set_digest": "1" * 64,
    }
    payload["input_set_digest"] = _input_set_digest(payload)
    return validate_input_set_manifest(payload)


def write_static_input_set_manifest(*, source_root: Path, destination: Path) -> Path:
    target = destination.expanduser()
    if not target.is_absolute() or target.name != INPUT_SET_MANIFEST_FILE:
        raise ReleaseContractError(
            "input-set manifest target must be its exact basename"
        )
    if target.exists() or target.is_symlink():
        raise ReleaseContractError("input-set manifest target already exists")
    _require_secure_parent_chain(target)
    payload = render_static_input_set_manifest(source_root)
    _atomic_private_bytes(
        target,
        _canonical_bytes(payload) + b"\n",
        uid=os.geteuid(),
        gid=os.getegid(),
    )
    return target


def build_input_set_archive(
    payload: Mapping[str, Any],
    *,
    source_root: Path,
    destination: Path,
) -> Path:
    """Build a deterministic regular-file-only ZIP after validating every source."""
    admitted = validate_input_set_sources(payload, source_root)
    if not destination.is_absolute() or destination.name != INPUT_SET_ARCHIVE_FILE:
        raise ReleaseContractError("input-set archive destination differs")
    _require_secure_parent_chain(destination)
    if destination.exists() or destination.is_symlink():
        raise ReleaseContractError("input-set archive destination already exists")
    try:
        with zipfile.ZipFile(
            destination,
            mode="x",
            compression=zipfile.ZIP_STORED,
            allowZip64=False,
        ) as archive:
            for target in sorted(admitted):
                info = zipfile.ZipInfo(target, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = (stat.S_IFREG | 0o600) << 16
                archive.writestr(info, admitted[target])
        os.chmod(destination, 0o600)
        descriptor = os.open(
            destination,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        validate_input_set_archive(payload, destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def scan_static_input_set(
    payload: Mapping[str, Any],
    *,
    source_root: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    gitleaks_path: Path = Path(GITLEAKS_PATH),
    scratch_root: Path = Path("/private/tmp"),
) -> dict[str, Any]:
    """Require a redacted zero-finding scan over only admitted ZIP members."""
    manifest = validate_input_set_manifest(payload)
    execute = runner or _run
    _require_secure_parent_chain(scratch_root / ".custody-check")
    try:
        scratch_identity = scratch_root.lstat()
    except OSError as exc:
        raise ReleaseContractError(
            "static-input scan scratch root is unavailable"
        ) from exc
    if not stat.S_ISDIR(scratch_identity.st_mode) or scratch_root.is_symlink():
        raise ReleaseContractError("static-input scan scratch root is invalid")
    version = execute(
        (str(gitleaks_path), "version"),
        cwd=scratch_root,
        check=False,
    )
    if version.returncode != 0 or version.stdout.strip() != GITLEAKS_VERSION:
        raise ReleaseContractError("gitleaks version differs from the seal gate")
    scan_root = Path(tempfile.mkdtemp(prefix="sadhana-static-scan-", dir=scratch_root))
    os.chmod(scan_root, 0o700)
    try:
        archive = scan_root / INPUT_SET_ARCHIVE_FILE
        build_input_set_archive(
            manifest,
            source_root=source_root,
            destination=archive,
        )
        admitted = validate_input_set_archive(manifest, archive)
        members = scan_root / "members"
        members.mkdir(mode=0o700)
        for relative, raw in admitted.items():
            target = members.joinpath(*PurePosixPath(relative).parts)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(target.parent, 0o700)
            descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                _write_all(descriptor, raw)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        report = scan_root / "gitleaks-report.json"
        scan_env = dict(_SAFE_SUBPROCESS_ENV)
        scan_env["HOME"] = str(scan_root)
        result = execute(
            (
                str(gitleaks_path),
                "dir",
                "--redact",
                "--no-banner",
                "--report-format",
                "json",
                "--report-path",
                str(report),
                str(members),
            ),
            cwd=scan_root,
            check=False,
            env=scan_env,
        )
        try:
            report_identity = report.lstat()
        except OSError as exc:
            raise ReleaseContractError(
                "gitleaks did not create its redacted report"
            ) from exc
        if (
            not stat.S_ISREG(report_identity.st_mode)
            or report.is_symlink()
            or report_identity.st_uid != os.geteuid()
            or report_identity.st_nlink != 1
            or report_identity.st_size > _MAX_JSON_BYTES
            or stat.S_IMODE(report_identity.st_mode) & 0o022
        ):
            raise ReleaseContractError("gitleaks report lacks exact custody")
        try:
            findings = json.loads(report.read_bytes())
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ReleaseContractError("gitleaks report is invalid") from exc
        if result.returncode != 0 or findings != []:
            raise ReleaseContractError("static input set has redacted secret findings")
        return {
            "schema_version": "dharma.sadhana.static_input_secret_scan.v1",
            "tool": "gitleaks",
            "tool_version": GITLEAKS_VERSION,
            "redacted": True,
            "scope": "validated_static_input_zip_members_only",
            "entry_count": len(manifest["entries"]),
            "input_set_digest": manifest["input_set_digest"],
            "finding_count": 0,
        }
    finally:
        shutil.rmtree(scan_root)


def validate_input_set_archive(
    payload: Mapping[str, Any], archive_path: Path
) -> dict[str, bytes]:
    """Read a closed ZIP and return bytes only after the full set validates."""
    manifest = validate_input_set_manifest(payload)
    if archive_path.name != INPUT_SET_ARCHIVE_FILE:
        raise ReleaseContractError("input-set archive basename differs")
    try:
        identity = archive_path.lstat()
    except OSError as exc:
        raise ReleaseContractError("input-set archive is unavailable") from exc
    if (
        not stat.S_ISREG(identity.st_mode)
        or archive_path.is_symlink()
        or identity.st_uid != os.geteuid()
        or identity.st_nlink != 1
        or stat.S_IMODE(identity.st_mode) & 0o022
        or not 0 < identity.st_size <= _MAX_INPUT_SET_BYTES
    ):
        raise ReleaseContractError("input-set archive lacks bounded custody")
    expected = {entry["target_relative_path"]: entry for entry in manifest["entries"]}
    admitted: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)) or set(names) != set(expected):
                raise ReleaseContractError("input-set archive member set differs")
            for info in infos:
                entry = expected[info.filename]
                if (
                    info.is_dir()
                    or info.flag_bits & 0x1
                    or info.compress_type != zipfile.ZIP_STORED
                    or info.file_size != entry["bytes"]
                    or info.compress_size != entry["bytes"]
                    or info.file_size > _MAX_INPUT_FILE_BYTES
                ):
                    raise ReleaseContractError("input-set archive member is not exact")
                unix_mode = info.external_attr >> 16
                if (
                    info.create_system != 3
                    or not stat.S_ISREG(unix_mode)
                    or stat.S_IMODE(unix_mode) != 0o600
                ):
                    raise ReleaseContractError(
                        "input-set archive member custody differs"
                    )
                raw = archive.read(info)
                _reject_input_secret_markers(raw)
                if (
                    len(raw) != entry["bytes"]
                    or hashlib.sha256(raw).hexdigest() != entry["sha256"]
                ):
                    raise ReleaseContractError("input-set archive member hash differs")
                admitted[info.filename] = raw
    except (OSError, zipfile.BadZipFile) as exc:
        raise ReleaseContractError("input-set archive is not a valid ZIP") from exc
    if sum(len(raw) for raw in admitted.values()) > _MAX_INPUT_SET_BYTES:
        raise ReleaseContractError("input-set archive exceeds aggregate bound")
    return admitted


def _atomic_private_bytes(
    path: Path,
    raw: bytes,
    *,
    uid: int,
    gid: int,
    replace_existing: bool = False,
    checkpoint: Callable[[str], None] | None = None,
) -> None:
    _require_secure_parent_chain(path)
    if path.exists() or path.is_symlink():
        identity = path.lstat()
        if (
            not replace_existing
            or not stat.S_ISREG(identity.st_mode)
            or path.is_symlink()
            or identity.st_uid != uid
            or identity.st_gid != gid
            or stat.S_IMODE(identity.st_mode) != 0o600
            or identity.st_nlink != 1
            ):
            raise ReleaseContractError(f"private target already exists: {path.name}")

    # Linux production uses an unnamed inode. A crash before link publishes no
    # directory entry; a crash after link leaves the final path with nlink=1.
    # This avoids both the stale-dotfile and two-hardlink replay wedges of a
    # named-temp + link publication.
    if not replace_existing and sys.platform.startswith("linux"):
        anonymous_flag = getattr(os, "O_TMPFILE", 0)
        if not anonymous_flag:
            raise ReleaseContractError("platform lacks anonymous private publication")
        directory_descriptor = os.open(
            path.parent,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
        )
        descriptor = -1
        try:
            try:
                descriptor = os.open(
                    path.parent,
                    os.O_WRONLY | anonymous_flag | getattr(os, "O_CLOEXEC", 0),
                    0o600,
                )
            except OSError as exc:
                raise ReleaseContractError(
                    "filesystem lacks anonymous private publication"
                ) from exc
            os.fchmod(descriptor, 0o600)
            os.fchown(descriptor, uid, gid)
            _write_all(descriptor, raw)
            os.fsync(descriptor)
            identity = os.fstat(descriptor)
            if (
                not stat.S_ISREG(identity.st_mode)
                or identity.st_uid != uid
                or identity.st_gid != gid
                or stat.S_IMODE(identity.st_mode) != 0o600
                or identity.st_nlink != 0
            ):
                raise ReleaseContractError(
                    "anonymous private target lacks exact custody"
                )
            if checkpoint is not None:
                checkpoint("private_bytes_pre_publish")
            libc = ctypes.CDLL(None, use_errno=True)
            linkat = libc.linkat
            linkat.argtypes = (
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
            )
            linkat.restype = ctypes.c_int
            source = os.fsencode(f"/proc/self/fd/{descriptor}")
            result = linkat(
                getattr(os, "AT_FDCWD", -100),
                source,
                directory_descriptor,
                os.fsencode(path.name),
                0x400,  # AT_SYMLINK_FOLLOW
            )
            if result != 0:
                error_number = ctypes.get_errno()
                if error_number == errno.EEXIST:
                    raise ReleaseContractError(
                        f"private target already exists: {path.name}"
                    )
                raise OSError(error_number, os.strerror(error_number), str(path))
            if checkpoint is not None:
                checkpoint("private_bytes_post_publish")
            os.fsync(directory_descriptor)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            os.close(directory_descriptor)
        return

    descriptor, temporary_raw = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_raw)
    try:
        os.fchmod(descriptor, 0o600)
        os.fchown(descriptor, uid, gid)
        _write_all(descriptor, raw)
        os.fsync(descriptor)
        identity = os.fstat(descriptor)
        if (
            not stat.S_ISREG(identity.st_mode)
            or identity.st_uid != uid
            or identity.st_gid != gid
            or stat.S_IMODE(identity.st_mode) != 0o600
            or identity.st_nlink != 1
        ):
            raise ReleaseContractError("private temporary target lacks exact custody")
        os.close(descriptor)
        descriptor = -1
        if checkpoint is not None:
            checkpoint("private_bytes_pre_publish")
        if replace_existing:
            os.replace(temporary, path)
        else:
            source_descriptor = os.open(
                path.parent,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            )
            try:
                _rename_noreplace_at(
                    source_descriptor,
                    temporary.name,
                    source_descriptor,
                    path.name,
                )
            finally:
                os.close(source_descriptor)
        if checkpoint is not None:
            checkpoint("private_bytes_post_publish")
        directory_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def _canonical_self_digest(payload: Mapping[str, Any], field: str) -> str:
    canonical = dict(payload)
    canonical.pop(field, None)
    return "sha256:" + hashlib.sha256(_canonical_bytes(canonical)).hexdigest()


def _canonical_newline_self_digest(payload: Mapping[str, Any], field: str) -> str:
    """Digest the canonical newline-terminated projection used by preparation."""
    canonical = dict(payload)
    canonical.pop(field, None)
    return "sha256:" + hashlib.sha256(_canonical_bytes(canonical) + b"\n").hexdigest()


def _read_exact_custodied_bytes(
    path: Path,
    *,
    expected_uid: int,
    expected_gid: int,
    expected_mode: int = 0o600,
    maximum_bytes: int = _MAX_JSON_BYTES,
) -> tuple[bytes, os.stat_result]:
    """Stable-read one private file whose parent may be root or service owned."""
    if not path.is_absolute() or not 0 < maximum_bytes <= _MAX_ARTIFACT_BYTES:
        raise ReleaseContractError("custodied file path or size bound differs")
    current = Path(path.anchor)
    allowed_uids = {0, expected_uid}
    for part in path.parts[1:-1]:
        current /= part
        try:
            parent = current.lstat()
        except OSError as exc:
            raise ReleaseContractError("custodied file parent is unavailable") from exc
        mode = stat.S_IMODE(parent.st_mode)
        sticky_root = bool(parent.st_uid == 0 and parent.st_mode & stat.S_ISVTX)
        # An ancestor's inherited group metadata is not an integrity authority
        # when that group cannot write.  This keeps owner-controlled paths
        # portable across macOS private-tmp and jailed fixture roots.  The
        # write-bit check still denies replacement by any untrusted group or
        # world principal, while the leaf must have the exact expected uid/gid,
        # expected mode, and single-link stable identity below.
        if (
            not stat.S_ISDIR(parent.st_mode)
            or current.is_symlink()
            or parent.st_uid not in allowed_uids
            or (mode & 0o022 and not sticky_root)
        ):
            raise ReleaseContractError(
                f"custodied file parent lacks private custody: {current.name}"
            )
    try:
        identity = path.lstat()
    except OSError as exc:
        raise ReleaseContractError(
            f"custodied file is unavailable: {path.name}"
        ) from exc
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ReleaseContractError("platform lacks no-follow custody admission")
    if (
        path.is_symlink()
        or not stat.S_ISREG(identity.st_mode)
        or identity.st_uid != expected_uid
        or identity.st_gid != expected_gid
        or stat.S_IMODE(identity.st_mode) != expected_mode
        or identity.st_nlink != 1
        or not 0 < identity.st_size <= maximum_bytes
    ):
        raise ReleaseContractError(f"custodied file scope differs: {path.name}")
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        before = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            identity.st_dev,
            identity.st_ino,
            identity.st_size,
            identity.st_mtime_ns,
        ):
            raise ReleaseContractError("custodied file changed during open")
        raw = b""
        while len(raw) <= maximum_bytes:
            chunk = os.read(
                descriptor,
                min(65_536, maximum_bytes + 1 - len(raw)),
            )
            if not chunk:
                break
            raw += chunk
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        len(raw) != identity.st_size
        or len(raw) > maximum_bytes
        or (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        != (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        )
    ):
        raise ReleaseContractError("custodied file changed during read")
    return raw, identity


def _read_exact_custodied_json(
    path: Path,
    *,
    expected_uid: int,
    expected_gid: int,
    expected_mode: int = 0o600,
    maximum_bytes: int = _MAX_JSON_BYTES,
) -> tuple[dict[str, Any], bytes, os.stat_result]:
    raw, identity = _read_exact_custodied_bytes(
        path,
        expected_uid=expected_uid,
        expected_gid=expected_gid,
        expected_mode=expected_mode,
        maximum_bytes=maximum_bytes,
    )
    try:
        payload = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseContractError(f"custodied JSON is invalid: {path.name}") from exc
    if not isinstance(payload, dict) or raw != _canonical_bytes(payload) + b"\n":
        raise ReleaseContractError(f"custodied JSON is noncanonical: {path.name}")
    return payload, raw, identity


def _publish_or_replay_exact_bytes(
    path: Path,
    raw: bytes,
    *,
    expected_uid: int,
    expected_gid: int,
    maximum_bytes: int = _MAX_JSON_BYTES,
) -> None:
    if path.exists() or path.is_symlink():
        prior, _identity = _read_exact_custodied_bytes(
            path,
            expected_uid=expected_uid,
            expected_gid=expected_gid,
            maximum_bytes=maximum_bytes,
        )
        if prior != raw:
            raise ReleaseContractError(f"immutable projection conflicts: {path.name}")
        return
    _atomic_private_bytes(path, raw, uid=expected_uid, gid=expected_gid)


def _publish_or_replay_private_receipt(
    path: Path,
    payload: Mapping[str, Any],
    *,
    expected_uid: int,
    expected_gid: int,
) -> dict[str, Any]:
    """Publish one immutable canonical receipt or accept an exact-byte replay."""
    schema = payload.get("schema_version")
    if not isinstance(schema, str) or not schema:
        raise ReleaseContractError("immutable receipt schema differs")
    raw = _canonical_bytes(payload) + b"\n"
    if path.exists() or path.is_symlink():
        prior, prior_raw, _identity = _read_exact_canonical_json(
            path,
            expected_uid=expected_uid,
            expected_gid=expected_gid,
            expected_schema=schema,
            digest_field="receipt_digest",
        )
        if prior_raw != raw:
            raise ReleaseContractError(
                f"immutable receipt conflicts: {path.name}"
            )
        return prior
    _require_secure_parent_chain(path)
    _atomic_private_bytes(
        path,
        raw,
        uid=expected_uid,
        gid=expected_gid,
    )
    return dict(payload)


def _read_exact_canonical_json(
    path: Path,
    *,
    expected_uid: int,
    expected_gid: int,
    expected_schema: str,
    digest_field: str,
    maximum_bytes: int = _MAX_JSON_BYTES,
) -> tuple[dict[str, Any], bytes, os.stat_result]:
    """Read one immutable canonical JSON object with stable inode metadata."""
    if not 0 < maximum_bytes <= _MAX_JSON_BYTES:
        raise ReleaseContractError("runtime binding artifact size bound differs")
    _require_secure_parent_chain(path)
    try:
        identity = path.lstat()
    except OSError as exc:
        raise ReleaseContractError(
            f"runtime binding artifact is unavailable: {path.name}"
        ) from exc
    if (
        not stat.S_ISREG(identity.st_mode)
        or path.is_symlink()
        or identity.st_uid != expected_uid
        or identity.st_gid != expected_gid
        or stat.S_IMODE(identity.st_mode) != 0o600
        or identity.st_nlink != 1
        or not 0 < identity.st_size <= maximum_bytes
    ):
        raise ReleaseContractError(
            f"runtime binding artifact lacks exact custody: {path.name}"
        )
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ReleaseContractError("platform lacks no-follow runtime admission")
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        before = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            identity.st_dev,
            identity.st_ino,
            identity.st_size,
            identity.st_mtime_ns,
        ):
            raise ReleaseContractError("runtime binding artifact changed during open")
        raw = b""
        while len(raw) <= maximum_bytes:
            chunk = os.read(descriptor, min(65_536, maximum_bytes + 1 - len(raw)))
            if not chunk:
                break
            raw += chunk
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if len(raw) > maximum_bytes or len(raw) != identity.st_size:
        raise ReleaseContractError("runtime binding artifact size changed during read")
    if (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) != (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ):
        raise ReleaseContractError("runtime binding artifact changed during read")
    try:
        payload = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseContractError(
            f"runtime binding artifact is invalid JSON: {path.name}"
        ) from exc
    if not isinstance(payload, dict):
        raise ReleaseContractError("runtime binding artifact root must be an object")
    if payload.get("schema_version") != expected_schema:
        raise ReleaseContractError("runtime binding artifact schema differs")
    digest = payload.get(digest_field)
    if (
        not isinstance(digest, str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
        or digest != _canonical_self_digest(payload, digest_field)
    ):
        raise ReleaseContractError("runtime binding artifact self-digest differs")
    if raw != _canonical_bytes(payload) + b"\n":
        raise ReleaseContractError("runtime binding artifact bytes are noncanonical")
    return payload, raw, identity


def _supervisor_runtime_environment_bytes(config: Mapping[str, Any]) -> bytes:
    canary_task_id = config.get("canary_task_id")
    held_out_digest = config.get("held_out_oracle_digest")
    if (
        not isinstance(canary_task_id, str)
        or not _STABLE_ID_RE.fullmatch(canary_task_id)
        or not isinstance(held_out_digest, str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", held_out_digest)
    ):
        raise ReleaseContractError("prepared supervisor runtime config differs")
    return (
        f"SADHANA_CANARY_TASK_ID={canary_task_id}\n"
        f"SADHANA_HELD_OUT_ORACLE_DIGEST={held_out_digest}\n"
    ).encode("ascii")


def _publish_supervisor_runtime_environment(
    config: Mapping[str, Any],
    *,
    destination: Path = SUPERVISOR_RUNTIME_ENV,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> bytes:
    raw = _supervisor_runtime_environment_bytes(config)
    _publish_or_replay_exact_bytes(
        destination,
        raw,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        maximum_bytes=4096,
    )
    return raw


def _validate_prepared_runtime_semantics(
    preparation: Mapping[str, Any],
    prepared: Mapping[str, tuple[Mapping[str, Any], bytes]],
    *,
    contracts_raw: bytes,
) -> None:
    """Domain-validate and cross-bind all service-prepared runtime manifests."""
    try:
        from dharma_swarm.mission_control_binding_manifest import (
            load_campaign_authority_manifest,
        )
        from dharma_swarm.mission_control_bootstrap import (
            CANARY_GOAL_ID,
            GoalContractError,
            load_goal_contract,
        )
        from dharma_swarm.mission_control_contract import MissionControlError
        from dharma_swarm.mission_control_held_out_oracle import (
            G10_GOAL_ID,
            load_held_out_oracle_manifest,
        )
        from dharma_swarm.mission_control_observed_input import (
            load_observed_input_manifest,
        )
        from dharma_swarm.mission_control_oracle_custody import HeldOutOracleError

        validation_scratch = Path(
            "/private/tmp" if sys.platform == "darwin" else "/tmp"
        )
        validation_root = Path(
            tempfile.mkdtemp(
                prefix="sadhana-root-manifest-validation-",
                dir=validation_scratch,
            )
        )
        os.chmod(validation_root, 0o700)
        try:
            contract_path = validation_root / "goal-contracts.v1.json"
            _atomic_private_bytes(
                contract_path,
                contracts_raw,
                uid=os.geteuid(),
                gid=os.getegid(),
            )
            validation_paths: dict[str, Path] = {}
            for name, (_payload, raw) in prepared.items():
                path = validation_root / name
                _atomic_private_bytes(
                    path,
                    raw,
                    uid=os.geteuid(),
                    gid=os.getegid(),
                )
                validation_paths[name] = path
            portfolio = load_goal_contract(contract_path)
            observed = load_observed_input_manifest(
                validation_paths["observed-inputs.json"]
            )
            held = load_held_out_oracle_manifest(
                validation_paths["held-out-oracle.json"]
            )
            authority = load_campaign_authority_manifest(
                validation_paths["authority-manifest.json"]
            )
        finally:
            shutil.rmtree(validation_root)
    except (
        GoalContractError,
        HeldOutOracleError,
        MissionControlError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        raise ReleaseContractError(
            "prepared runtime manifest semantics are invalid"
        ) from exc

    input_set = preparation.get("input_set")
    tasks = preparation.get("tasks")
    config = preparation.get("config")
    if not all(isinstance(value, dict) for value in (input_set, tasks, config)):
        raise ReleaseContractError("prepared runtime semantic indices are malformed")
    assert isinstance(input_set, dict)
    assert isinstance(tasks, dict)
    assert isinstance(config, dict)
    pins = input_set.get("manifest_pins")
    observed_goals = observed.get("goals")
    authority_goals = {goal.goal_id: goal for goal in authority.goals}
    goal_contracts = portfolio.by_id
    if (
        not isinstance(pins, dict)
        or not isinstance(observed_goals, dict)
        or portfolio.campaign_id != MISSION_ID
        or input_set.get("goal_contract_digest") != portfolio.digest
        or observed.get("campaign_id") != MISSION_ID
        or observed.get("mission_id") != MISSION_ID
        or observed.get("portfolio_contract_sha256") != portfolio.digest
        or set(tasks) != set(goal_contracts)
        or set(observed_goals) != set(tasks)
        or set(authority_goals) != set(tasks)
        or config.get("canary_task_id") != tasks.get(CANARY_GOAL_ID)
        or config.get("held_out_oracle_digest") != held.manifest_digest
        or held.campaign_id != MISSION_ID
        or held.mission_id != MISSION_ID
        or held.goal_id != G10_GOAL_ID
        or held.task_id != tasks.get(G10_GOAL_ID)
        or authority.campaign_id != MISSION_ID
        or authority.mission_id != MISSION_ID
        or authority.goal_contract_sha256 != portfolio.digest
        or authority.agent_roster_sha256 != input_set.get("roster_sha256")
        or authority.campaign_end_text != portfolio.campaign_deadline
        or authority.observed_input_manifest_digest
        != observed.get("manifest_digest")
        or authority.held_out_oracle_manifest_digest != held.manifest_digest
        or str(held.evaluator_path) != pins.get("evaluator_path")
        or held.evaluator_sha256 != pins.get("evaluator_sha256")
        or str(held.policy_path) != pins.get("policy_path")
        or held.policy_sha256 != pins.get("policy_sha256")
        or authority.operator_control_semantics_sha256
        != pins.get("operator_control_semantics_sha256")
        or authority.operator_control_authority_binding_sha256
        != pins.get("operator_control_authority_binding_sha256")
        or authority.deployment_authority_topology_sha256
        != pins.get("deployment_authority_topology_sha256")
        or authority.deployment_authority_credential_clarification_sha256
        != pins.get("deployment_authority_credential_clarification_sha256")
    ):
        raise ReleaseContractError("prepared runtime semantic lineage differs")
    for goal_id, task_id in tasks.items():
        observed_goal = observed_goals.get(goal_id)
        authority_goal = authority_goals.get(goal_id)
        contract = goal_contracts.get(goal_id)
        if (
            not isinstance(observed_goal, dict)
            or authority_goal is None
            or contract is None
            or observed_goal.get("task_id") != task_id
            or authority_goal.task_id != task_id
            or observed_goal.get("goal_contract_sha256")
            != contract.content_digest
            or authority_goal.goal_contract_sha256 != contract.content_digest
            or authority_goal.task_creation_hash
            != observed_goal.get("task_creation_hash")
            or authority_goal.observed_input_ref.receipt_id
            != observed_goal.get("receipt_id")
            or authority_goal.observed_input_ref.artifact_id
            != observed_goal.get("artifact_id")
            or authority_goal.observed_input_ref.content_sha256
            != observed_goal.get("content_sha256")
        ):
            raise ReleaseContractError("prepared runtime goal lineage differs")
    g10_observed = observed_goals[G10_GOAL_ID]
    if held.task_creation_hash != g10_observed.get("task_creation_hash"):
        raise ReleaseContractError("prepared held-out task lineage differs")


def _validate_root_preparation(
    *,
    release_sha: str,
    account: pwd.struct_passwd,
    preparation_receipt_path: Path,
    prepared_root: Path,
    release_receipt_root: Path,
    release_admission_projection: Path,
    supervisor_env_path: Path,
    expected_root_uid: int,
    expected_root_gid: int,
) -> tuple[dict[str, Any], dict[str, tuple[dict[str, Any], bytes]]]:
    preparation, _raw, _identity = _read_exact_custodied_json(
        preparation_receipt_path,
        expected_uid=account.pw_uid,
        expected_gid=account.pw_gid,
    )
    try:
        from scripts.runtime.sadhana_prepare_runtime import (
            PREPARED_PROOF_TYPE,
            validate_preparation_receipt,
        )

        validate_preparation_receipt(
            preparation,
            expected_release_sha=release_sha,
        )
    except (ImportError, RuntimeError, TypeError, ValueError) as exc:
        raise ReleaseContractError("runtime preparation receipt is invalid") from exc
    proof = preparation.get("proof")
    parameters = proof.get("parameters") if isinstance(proof, dict) else None
    manifests = preparation.get("manifests")
    input_set = preparation.get("input_set")
    config = preparation.get("config")
    if not all(
        isinstance(item, dict)
        for item in (proof, parameters, manifests, input_set, config)
    ):
        raise ReleaseContractError("runtime preparation projection is malformed")
    assert isinstance(parameters, dict)
    assert isinstance(manifests, dict)
    assert isinstance(input_set, dict)
    assert isinstance(config, dict)
    release_input_set_digest = parameters.get("release_input_set_digest")
    if not isinstance(release_input_set_digest, str):
        raise ReleaseContractError("prepared release input-set binding is absent")
    admission = verify_staged_release_admission(
        release_sha=release_sha,
        release_path=Path(RELEASE_ROOT) / release_sha,
        expected_release_input_set_digest=release_input_set_digest,
        account=account,
        receipt_root=release_receipt_root,
        projection_path=release_admission_projection,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if (
        input_set.get("release_admission_receipt_digest")
        != admission["receipt_digest"]
        or proof.get("type") != PREPARED_PROOF_TYPE
        or proof.get("effect") != "NoEffect"
        or parameters.get("campaign_id") != MISSION_ID
        or parameters.get("session_status") != "paused"
    ):
        raise ReleaseContractError("prepared release authority indices differ")

    installed_input_manifest = validate_input_set_manifest(
        _secure_json(INPUT_SET_MANIFEST_TARGET, require_private=True)
    )
    expected_preparation_env = _runtime_preparation_environment_bindings(
        installed_input_manifest,
        admission=admission,
        release_sha=release_sha,
        release_path=Path(RELEASE_ROOT) / release_sha,
        account=account,
        supervisor_env_path=supervisor_env_path,
    )
    preparation_env_path = _runtime_preparation_env_path(
        release_sha,
        receipt_root=release_receipt_root,
    )
    preparation_env_raw, _preparation_env_identity = _read_exact_custodied_bytes(
        preparation_env_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        maximum_bytes=64 * 1024,
    )
    if preparation_env_raw != _runtime_preparation_environment_bytes(
        expected_preparation_env
    ):
        raise ReleaseContractError("runtime preparation environment differs")
    installed_entries = {
        entry["target_relative_path"]: entry
        for entry in installed_input_manifest["entries"]
    }
    contracts_entry = installed_entries[
        RUNTIME_PREPARATION_INPUT_PATHS["contracts"]
    ]
    contracts_service_owned = (
        contracts_entry.get("custody") == "service_hash_pinned"
    )
    contracts_raw, _contracts_identity = _read_exact_custodied_bytes(
        Path(expected_preparation_env["SADHANA_PREP_CONTRACTS"]),
        expected_uid=(account.pw_uid if contracts_service_owned else expected_root_uid),
        expected_gid=(account.pw_gid if contracts_service_owned else expected_root_gid),
        maximum_bytes=contracts_entry["bytes"],
    )
    if (
        len(contracts_raw) != contracts_entry["bytes"]
        or hashlib.sha256(contracts_raw).hexdigest()
        != contracts_entry["sha256"]
    ):
        raise ReleaseContractError("sealed goal contract bytes differ")
    expected_pins = {
        "evaluator_path": expected_preparation_env[
            "SADHANA_PREP_EVALUATOR_PATH"
        ],
        "evaluator_sha256": expected_preparation_env[
            "SADHANA_PREP_EVALUATOR_SHA256"
        ],
        "policy_path": expected_preparation_env["SADHANA_PREP_POLICY_PATH"],
        "policy_sha256": expected_preparation_env[
            "SADHANA_PREP_POLICY_SHA256"
        ],
        "operator_control_semantics_sha256": expected_preparation_env[
            "SADHANA_PREP_OPERATOR_CONTROL_SEMANTICS_SHA256"
        ],
        "operator_control_authority_binding_sha256": expected_preparation_env[
            "SADHANA_PREP_OPERATOR_CONTROL_AUTHORITY_BINDING_SHA256"
        ],
        "deployment_authority_topology_sha256": expected_preparation_env[
            "SADHANA_PREP_DEPLOYMENT_AUTHORITY_TOPOLOGY_SHA256"
        ],
        "deployment_authority_credential_clarification_sha256": (
            expected_preparation_env[
                "SADHANA_PREP_DEPLOYMENT_AUTHORITY_CREDENTIAL_CLARIFICATION_SHA256"
            ]
        ),
    }
    if (
        input_set.get("roster_sha256")
        != expected_preparation_env["SADHANA_PREP_ROSTER_SHA256"]
        or input_set.get("objective_sha256")
        != expected_preparation_env["SADHANA_PREP_OBJECTIVE_SHA256"]
        or input_set.get("verifier_seat")
        != expected_preparation_env["SADHANA_PREP_VERIFIER_SEAT"]
        or input_set.get("observed_source_sha256")
        != "sha256:"
        + installed_entries[
            RUNTIME_PREPARATION_INPUT_PATHS["observed_source"]
        ]["sha256"]
        or input_set.get("manifest_pins") != expected_pins
    ):
        raise ReleaseContractError("prepared sealed input projection differs")

    supervisor = _private_env_bindings(supervisor_env_path)
    expected_supervisor = {
        "SADHANA_OPERATOR_ID": config.get("operator_id"),
        "SADHANA_MAX_DISPATCH_PER_CYCLE": config.get("max_dispatch_per_cycle"),
        "SADHANA_CYCLE_INTERVAL_SECONDS": config.get("cycle_interval_seconds"),
        "SADHANA_FRESHNESS_SECONDS": config.get("freshness_seconds"),
    }
    if {
        "SADHANA_CANARY_TASK_ID",
        "SADHANA_HELD_OUT_ORACLE_DIGEST",
    } & set(supervisor):
        raise ReleaseContractError("static supervisor config claims runtime outputs")
    for key, expected in expected_supervisor.items():
        actual = supervisor.get(key)
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            try:
                equal = float(actual or "nan") == float(expected)
            except ValueError:
                equal = False
        else:
            equal = actual == expected
        if not equal:
            raise ReleaseContractError(
                f"supervisor config projection differs at {key}"
            )
    if config.get("mission_id") != MISSION_ID:
        raise ReleaseContractError("supervisor mission projection differs")
    expected_supervisor_inputs = {
        "SADHANA_AGENT_ROSTER_PATH": expected_preparation_env[
            "SADHANA_PREP_ROSTER"
        ],
        "SADHANA_AGENT_ROSTER_SHA256": expected_preparation_env[
            "SADHANA_PREP_ROSTER_SHA256"
        ],
        "SADHANA_OBJECTIVE_SHA256": expected_preparation_env[
            "SADHANA_PREP_OBJECTIVE_SHA256"
        ],
    }
    if any(
        supervisor.get(key) != expected
        for key, expected in expected_supervisor_inputs.items()
    ):
        raise ReleaseContractError("supervisor sealed input projection differs")

    file_hashes = manifests.get("files")
    if not isinstance(file_hashes, dict) or set(file_hashes) != set(
        RUNTIME_INPUT_SCHEMAS
    ):
        raise ReleaseContractError("prepared runtime manifest file set differs")
    prepared: dict[str, tuple[dict[str, Any], bytes]] = {}
    for name, schema in sorted(RUNTIME_INPUT_SCHEMAS.items()):
        if not isinstance(schema, str):
            raise ReleaseContractError("runtime binding schema is unavailable")
        path = prepared_root / name
        payload, raw, _file_identity = _read_exact_custodied_json(
            path,
            expected_uid=account.pw_uid,
            expected_gid=account.pw_gid,
        )
        expected_hash = file_hashes.get(name)
        if (
            payload.get("schema_version") != schema
            or payload.get("manifest_digest")
            != _canonical_self_digest(payload, "manifest_digest")
            or not isinstance(expected_hash, str)
            or expected_hash != hashlib.sha256(raw).hexdigest()
        ):
            raise ReleaseContractError("prepared runtime manifest binding differs")
        prepared[name] = (payload, raw)
    semantic_digests = {
        "observed-inputs.json": "observed_input_manifest_digest",
        "held-out-oracle.json": "held_out_oracle_manifest_digest",
        "authority-manifest.json": "authority_manifest_digest",
    }
    for name, field in semantic_digests.items():
        if prepared[name][0]["manifest_digest"] != manifests.get(field):
            raise ReleaseContractError("prepared semantic manifest digest differs")
    _validate_prepared_runtime_semantics(
        preparation,
        prepared,
        contracts_raw=contracts_raw,
    )
    return preparation, prepared


def publish_runtime_binding_activation(
    *,
    role: str,
    release_sha: str,
    account: pwd.struct_passwd | None = None,
    preparation_receipt_path: Path = RUNTIME_PREPARATION_RECEIPT,
    prepared_root: Path = PREPARED_RUNTIME_MANIFEST_ROOT,
    release_receipt_root: Path = RELEASE_RECEIPT_ROOT,
    release_admission_projection: Path = PREPARED_RELEASE_ADMISSION_PROJECTION,
    supervisor_env_path: Path = Path(ENV_FILES[0]),
    supervisor_runtime_env_path: Path = SUPERVISOR_RUNTIME_ENV,
    receipt_path: Path = RUNTIME_BINDING_RECEIPT_TARGET,
    runtime_root: Path = RUNTIME_INPUT_ROOT,
    now: datetime | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Promote Prepared<...>:NoEffect by exact copy, publishing authority last."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("runtime binding publication requires root")
    _require_host_role(role, observed_node=observed_node)
    if role != "writer" or not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("runtime binding publication identity differs")
    service = account or _require_static_service_identity()
    if service.pw_name != "dharma-sadhana" or min(service.pw_uid, service.pw_gid) <= 0:
        raise ReleaseContractError("runtime binding service identity differs")
    if receipt_path.exists() or receipt_path.is_symlink():
        return verify_runtime_binding_activation(
            receipt_path=receipt_path,
            runtime_root=runtime_root,
            account=service,
            preparation_receipt_path=preparation_receipt_path,
            prepared_root=prepared_root,
            release_receipt_root=release_receipt_root,
            release_admission_projection=release_admission_projection,
            supervisor_env_path=supervisor_env_path,
            supervisor_runtime_env_path=supervisor_runtime_env_path,
            expected_release_sha=release_sha,
            now=now,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
    preparation, prepared = _validate_root_preparation(
        release_sha=release_sha,
        account=service,
        preparation_receipt_path=preparation_receipt_path,
        prepared_root=prepared_root,
        release_receipt_root=release_receipt_root,
        release_admission_projection=release_admission_projection,
        supervisor_env_path=supervisor_env_path,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    proof = preparation["proof"]
    parameters = proof["parameters"]
    input_set = preparation["input_set"]
    supervisor_runtime_env_raw = _publish_supervisor_runtime_environment(
        preparation["config"],
        destination=supervisor_runtime_env_path,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    files: dict[str, dict[str, Any]] = {}
    for name, schema in sorted(RUNTIME_INPUT_SCHEMAS.items()):
        assert isinstance(schema, str)
        source_payload, source_raw = prepared[name]
        destination = runtime_root / name
        _publish_or_replay_exact_bytes(
            destination,
            source_raw,
            expected_uid=service.pw_uid,
            expected_gid=service.pw_gid,
        )
        installed, installed_raw, installed_identity = _read_exact_canonical_json(
            destination,
            expected_uid=service.pw_uid,
            expected_gid=service.pw_gid,
            expected_schema=schema,
            digest_field="manifest_digest",
        )
        if installed_raw != source_raw or installed != source_payload:
            raise ReleaseContractError("published runtime manifest bytes differ")
        files[name] = {
            "absolute_path": str(destination),
            "prepared_source_path": str(prepared_root / name),
            "schema_version": schema,
            "manifest_digest": installed["manifest_digest"],
            "prepared_file_sha256": hashlib.sha256(source_raw).hexdigest(),
            "file_sha256": hashlib.sha256(installed_raw).hexdigest(),
            "size_bytes": len(installed_raw),
            "uid": service.pw_uid,
            "mode": "0600",
        }
        if installed_identity.st_gid != service.pw_gid:
            raise ReleaseContractError("published runtime manifest group differs")
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ReleaseContractError("runtime binding publication clock must be aware")
    observed = observed.astimezone(timezone.utc).replace(microsecond=0)
    created_at = observed.isoformat().replace("+00:00", "Z")
    if receipt_path.exists() or receipt_path.is_symlink():
        prior, _prior_raw, _prior_identity = _read_exact_canonical_json(
            receipt_path,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
            expected_schema=RUNTIME_BINDING_SCHEMA_VERSION,
            digest_field="receipt_digest",
        )
        created_at = prior.get("created_at")
    payload: dict[str, Any] = {
        "schema_version": RUNTIME_BINDING_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "mission_id": MISSION_ID,
        "release_sha": release_sha,
        "created_at": created_at,
        "service_uid": service.pw_uid,
        "service_gid": service.pw_gid,
        "release_admission_receipt_digest": input_set[
            "release_admission_receipt_digest"
        ],
        "release_input_set_digest": parameters["release_input_set_digest"],
        "preparation_receipt_digest": preparation["receipt_digest"],
        "preparation_input_digest": parameters["preparation_input_digest"],
        "config_digest": parameters["config_digest"],
        "supervisor_runtime_env_sha256": hashlib.sha256(
            supervisor_runtime_env_raw
        ).hexdigest(),
        "task_set_digest": parameters["task_set_digest"],
        "manifest_set_digest": parameters["manifest_set_digest"],
        "session_generation": parameters["session_generation"],
        "session_status": parameters["session_status"],
        "prepared_proof_type": proof["type"],
        "prepared_effect": proof["effect"],
        "root_verification_type": (
            "RootVerified<Prepared<Mission,Release,InputSet,Config,TaskSet,"
            "ProjectionContract>>"
        ),
        "files": files,
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    if set(payload) != _RUNTIME_BINDING_FIELDS:
        raise ReleaseContractError("runtime binding receipt fields differ")
    _publish_or_replay_private_receipt(
        receipt_path,
        payload,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )
    return verify_runtime_binding_activation(
        receipt_path=receipt_path,
        runtime_root=runtime_root,
        account=service,
        preparation_receipt_path=preparation_receipt_path,
        prepared_root=prepared_root,
        release_receipt_root=release_receipt_root,
        release_admission_projection=release_admission_projection,
        supervisor_env_path=supervisor_env_path,
        supervisor_runtime_env_path=supervisor_runtime_env_path,
        expected_release_sha=release_sha,
        now=observed,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )


def verify_runtime_binding_activation(
    *,
    receipt_path: Path = RUNTIME_BINDING_RECEIPT_TARGET,
    runtime_root: Path = RUNTIME_INPUT_ROOT,
    account: pwd.struct_passwd,
    preparation_receipt_path: Path = RUNTIME_PREPARATION_RECEIPT,
    prepared_root: Path = PREPARED_RUNTIME_MANIFEST_ROOT,
    release_receipt_root: Path = RELEASE_RECEIPT_ROOT,
    release_admission_projection: Path = PREPARED_RELEASE_ADMISSION_PROJECTION,
    supervisor_env_path: Path = Path(ENV_FILES[0]),
    supervisor_runtime_env_path: Path = SUPERVISOR_RUNTIME_ENV,
    expected_release_sha: str | None = None,
    now: datetime | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Reprove the root-published v2 activation and every prepared index."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("runtime binding verification requires root")
    if account.pw_name != "dharma-sadhana" or min(account.pw_uid, account.pw_gid) <= 0:
        raise ReleaseContractError("runtime binding service identity differs")
    receipt, _receipt_raw, _receipt_identity = _read_exact_canonical_json(
        receipt_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=RUNTIME_BINDING_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    if set(receipt) != _RUNTIME_BINDING_FIELDS:
        raise ReleaseContractError("runtime binding receipt fields differ")
    release_sha = receipt.get("release_sha")
    if not isinstance(release_sha, str) or not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("runtime binding release differs")
    if expected_release_sha is not None and release_sha != expected_release_sha:
        raise ReleaseContractError("runtime binding release differs")
    preparation, prepared = _validate_root_preparation(
        release_sha=release_sha,
        account=account,
        preparation_receipt_path=preparation_receipt_path,
        prepared_root=prepared_root,
        release_receipt_root=release_receipt_root,
        release_admission_projection=release_admission_projection,
        supervisor_env_path=supervisor_env_path,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    proof = preparation["proof"]
    parameters = proof["parameters"]
    input_set = preparation["input_set"]
    supervisor_runtime_env_raw, _supervisor_runtime_env_identity = (
        _read_exact_custodied_bytes(
            supervisor_runtime_env_path,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
            maximum_bytes=4096,
        )
    )
    expected_supervisor_runtime_env = _supervisor_runtime_environment_bytes(
        preparation["config"]
    )
    if supervisor_runtime_env_raw != expected_supervisor_runtime_env:
        raise ReleaseContractError("supervisor runtime environment differs")
    expected_indices = {
        "campaign_id": MISSION_ID,
        "mission_id": MISSION_ID,
        "release_sha": release_sha,
        "service_uid": account.pw_uid,
        "service_gid": account.pw_gid,
        "release_admission_receipt_digest": input_set[
            "release_admission_receipt_digest"
        ],
        "release_input_set_digest": parameters["release_input_set_digest"],
        "preparation_receipt_digest": preparation["receipt_digest"],
        "preparation_input_digest": parameters["preparation_input_digest"],
        "config_digest": parameters["config_digest"],
        "supervisor_runtime_env_sha256": hashlib.sha256(
            supervisor_runtime_env_raw
        ).hexdigest(),
        "task_set_digest": parameters["task_set_digest"],
        "manifest_set_digest": parameters["manifest_set_digest"],
        "session_generation": parameters["session_generation"],
        "session_status": "paused",
        "prepared_proof_type": proof["type"],
        "prepared_effect": "NoEffect",
        "root_verification_type": (
            "RootVerified<Prepared<Mission,Release,InputSet,Config,TaskSet,"
            "ProjectionContract>>"
        ),
    }
    if any(receipt.get(key) != value for key, value in expected_indices.items()):
        raise ReleaseContractError("runtime binding authority indices differ")
    created_at = _parse_utc(receipt.get("created_at"), "runtime binding created_at")
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ReleaseContractError("runtime binding clock must be timezone-aware")
    observed = observed.astimezone(timezone.utc)
    if (
        created_at < _parse_utc(CAMPAIGN_START_UTC, "campaign_start_utc")
        or created_at > observed + timedelta(seconds=15)
        or observed >= _parse_utc(CAMPAIGN_STOP_UTC, "campaign_stop_utc")
    ):
        raise ReleaseContractError("runtime binding activation time differs")
    files = receipt.get("files")
    if not isinstance(files, dict) or set(files) != set(RUNTIME_INPUT_SCHEMAS):
        raise ReleaseContractError("runtime binding receipt file set differs")
    validated_files: dict[str, dict[str, Any]] = {}
    for name, schema in sorted(RUNTIME_INPUT_SCHEMAS.items()):
        assert isinstance(schema, str)
        entry = files.get(name)
        if not isinstance(entry, dict) or set(entry) != _RUNTIME_BINDING_FILE_FIELDS:
            raise ReleaseContractError("runtime binding file fields differ")
        path = runtime_root / name
        payload, raw, identity = _read_exact_canonical_json(
            path,
            expected_uid=account.pw_uid,
            expected_gid=account.pw_gid,
            expected_schema=schema,
            digest_field="manifest_digest",
        )
        source_payload, source_raw = prepared[name]
        expected_entry = {
            "absolute_path": str(path),
            "prepared_source_path": str(prepared_root / name),
            "schema_version": schema,
            "manifest_digest": payload["manifest_digest"],
            "prepared_file_sha256": hashlib.sha256(source_raw).hexdigest(),
            "file_sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
            "uid": account.pw_uid,
            "mode": "0600",
        }
        if (
            entry != expected_entry
            or identity.st_gid != account.pw_gid
            or raw != source_raw
            or payload != source_payload
        ):
            raise ReleaseContractError("runtime binding file receipt differs")
        validated_files[name] = expected_entry
    return {**receipt, "files": validated_files}


def _verify_installed_input_set(
    payload: Mapping[str, Any],
    *,
    account: pwd.struct_passwd,
    target_root: Path = INPUT_SET_TARGET_ROOT,
    root_uid: int = 0,
    root_gid: int = 0,
    runtime_binding_receipt: Path | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    manifest = validate_input_set_manifest(payload)
    if target_root != INPUT_SET_TARGET_ROOT or target_root.is_symlink():
        raise ReleaseContractError("installed input-set root differs")
    expected = {entry["target_relative_path"]: entry for entry in manifest["entries"]}
    admitted_dynamic: set[str] = set()
    if runtime_binding_receipt is not None:
        verify_runtime_binding_activation(
            receipt_path=runtime_binding_receipt,
            runtime_root=target_root / RUNTIME_INPUT_RELATIVE_ROOT,
            account=account,
            now=now,
            expected_root_uid=root_uid,
            expected_root_gid=root_gid,
        )
        admitted_dynamic = {
            f"{RUNTIME_INPUT_RELATIVE_ROOT}/{name}" for name in RUNTIME_INPUT_SCHEMAS
        }
    observed_files: set[str] = set()
    observed_entries: list[dict[str, Any]] = []
    root_identity = target_root.lstat()
    if (
        not stat.S_ISDIR(root_identity.st_mode)
        or root_identity.st_uid != root_uid
        or root_identity.st_gid != account.pw_gid
        or stat.S_IMODE(root_identity.st_mode) != 0o750
    ):
        raise ReleaseContractError("installed input-set root lacks exact custody")
    for directory, names, files in os.walk(target_root, followlinks=False):
        directory_path = Path(directory)
        directory_identity = directory_path.lstat()
        if (
            directory_path.is_symlink()
            or not stat.S_ISDIR(directory_identity.st_mode)
            or directory_identity.st_uid != root_uid
            or directory_identity.st_gid != account.pw_gid
            or stat.S_IMODE(directory_identity.st_mode) != 0o750
        ):
            raise ReleaseContractError("installed input-set directory custody differs")
        for name in names:
            child = directory_path / name
            if child.is_symlink() or not stat.S_ISDIR(child.lstat().st_mode):
                raise ReleaseContractError("installed input-set contains a link")
        for name in files:
            candidate = directory_path / name
            relative = candidate.relative_to(target_root).as_posix()
            observed_files.add(relative)
            entry = expected.get(relative)
            if entry is None:
                if relative in admitted_dynamic:
                    continue
                raise ReleaseContractError("installed input set contains an extra file")
            identity = candidate.lstat()
            expected_uid = (
                account.pw_uid
                if entry["custody"] == "service_hash_pinned"
                else root_uid
            )
            expected_gid = (
                account.pw_gid
                if entry["custody"] == "service_hash_pinned"
                else root_gid
            )
            if (
                not stat.S_ISREG(identity.st_mode)
                or candidate.is_symlink()
                or identity.st_uid != expected_uid
                or identity.st_gid != expected_gid
                or stat.S_IMODE(identity.st_mode) != 0o600
                or identity.st_nlink != 1
                or identity.st_size != entry["bytes"]
            ):
                raise ReleaseContractError("installed input-set file custody differs")
            raw = _read_input_source(
                candidate,
                expected_bytes=entry["bytes"],
                expected_uid=expected_uid,
            )
            if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                raise ReleaseContractError("installed input-set file hash differs")
            observed_entries.append(
                {
                    **entry,
                    "installed_uid": expected_uid,
                    "installed_gid": expected_gid,
                    "installed_mode": "0600",
                }
            )
    if observed_files != set(expected) | admitted_dynamic:
        raise ReleaseContractError("installed input-set file set differs")
    return sorted(observed_entries, key=lambda entry: entry["target_relative_path"])


def _input_set_receipt_payload(
    payload: Mapping[str, Any],
    *,
    manifest_sha256: str,
    archive_sha256: str,
    installed_entries: Sequence[Mapping[str, Any]],
    installed_at: datetime,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema_version": "dharma.sadhana.immutable_input_set_receipt.v1",
        "mission_id": MISSION_ID,
        "input_set_digest": payload["input_set_digest"],
        "manifest_sha256": manifest_sha256,
        "archive_sha256": archive_sha256,
        "target_root": str(INPUT_SET_TARGET_ROOT),
        "installed_at": installed_at.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "verifier_secret_included": False,
        "runtime_database_is_canonical": True,
        "entries": [dict(entry) for entry in installed_entries],
        "receipt_digest": "1" * 64,
    }
    receipt["receipt_digest"] = hashlib.sha256(
        _canonical_bytes(
            {key: value for key, value in receipt.items() if key != "receipt_digest"}
        )
    ).hexdigest()
    return receipt


def install_input_set(
    *,
    manifest_path: Path,
    archive_path: Path,
    account: pwd.struct_passwd,
    observed_node: str | None = None,
    now: datetime | None = None,
    target_root: Path = INPUT_SET_TARGET_ROOT,
    installed_manifest: Path = INPUT_SET_MANIFEST_TARGET,
    installed_receipt: Path = INPUT_SET_RECEIPT_TARGET,
    runtime_binding_receipt: Path = RUNTIME_BINDING_RECEIPT_TARGET,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Install a validated immutable input set without creating another state store."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("input-set installation requires root")
    _require_host_role("writer", observed_node=observed_node)
    if (
        account.pw_name != "dharma-sadhana"
        or account.pw_uid == 0
        or account.pw_gid == 0
    ):
        raise ReleaseContractError("input-set service identity differs")
    if (
        target_root != INPUT_SET_TARGET_ROOT
        or installed_manifest != INPUT_SET_MANIFEST_TARGET
        or installed_receipt != INPUT_SET_RECEIPT_TARGET
    ):
        raise ReleaseContractError("input-set installation targets differ")
    manifest_payload = validate_input_set_manifest(
        _secure_json(manifest_path, require_private=True)
    )
    manifest_identity = manifest_path.lstat()
    manifest_bytes = _read_input_source(
        manifest_path, expected_bytes=manifest_identity.st_size
    )
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    admitted = validate_input_set_archive(manifest_payload, archive_path)
    archive_sha256 = sha256_file(archive_path, max_bytes=_MAX_INPUT_SET_BYTES)
    parent = target_root.parent
    parent_identity = parent.lstat()
    if (
        not stat.S_ISDIR(parent_identity.st_mode)
        or parent.is_symlink()
        or parent_identity.st_uid != expected_root_uid
        or parent_identity.st_gid != account.pw_gid
        or stat.S_IMODE(parent_identity.st_mode) != 0o750
    ):
        raise ReleaseContractError("input-set parent lacks exact service-group custody")

    target_exists = target_root.exists() or target_root.is_symlink()
    manifest_exists = installed_manifest.exists() or installed_manifest.is_symlink()
    receipt_exists = installed_receipt.exists() or installed_receipt.is_symlink()
    binding_exists = (
        runtime_binding_receipt.exists() or runtime_binding_receipt.is_symlink()
    )
    if target_exists:
        installed_entries = _verify_installed_input_set(
            manifest_payload,
            account=account,
            target_root=target_root,
            root_uid=expected_root_uid,
            root_gid=expected_root_gid,
            runtime_binding_receipt=(
                runtime_binding_receipt if binding_exists else None
            ),
            now=now,
        )
        if manifest_exists:
            existing_manifest = _read_input_source(
                installed_manifest,
                expected_bytes=installed_manifest.lstat().st_size,
            )
            if existing_manifest != manifest_bytes:
                raise ReleaseContractError("installed input-set manifest bytes differ")
        if receipt_exists:
            existing_receipt = _secure_json(installed_receipt, require_private=True)
            if (
                existing_receipt.get("input_set_digest")
                != manifest_payload["input_set_digest"]
                or existing_receipt.get("manifest_sha256") != manifest_sha256
                or existing_receipt.get("archive_sha256") != archive_sha256
                or existing_receipt.get("entries") != installed_entries
                or existing_receipt.get("verifier_secret_included") is not False
                or existing_receipt.get("runtime_database_is_canonical") is not True
            ):
                raise ReleaseContractError("installed input-set receipt differs")
            receipt_without_digest = {
                key: value
                for key, value in existing_receipt.items()
                if key != "receipt_digest"
            }
            if (
                existing_receipt.get("receipt_digest")
                != hashlib.sha256(_canonical_bytes(receipt_without_digest)).hexdigest()
            ):
                raise ReleaseContractError("installed input-set receipt digest differs")
            if not manifest_exists:
                _atomic_private_bytes(
                    installed_manifest,
                    manifest_bytes,
                    uid=expected_root_uid,
                    gid=expected_root_gid,
                )
            return existing_receipt
    elif manifest_exists or receipt_exists:
        raise ReleaseContractError("input-set control files exist without their set")
    else:
        staging = Path(tempfile.mkdtemp(prefix=".inputs-staging-", dir=parent))
        try:
            for entry in manifest_payload["entries"]:
                target = staging.joinpath(
                    *PurePosixPath(entry["target_relative_path"]).parts
                )
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
                descriptor = os.open(
                    target,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                )
                try:
                    expected_uid = (
                        account.pw_uid
                        if entry["custody"] == "service_hash_pinned"
                        else expected_root_uid
                    )
                    expected_gid = (
                        account.pw_gid
                        if entry["custody"] == "service_hash_pinned"
                        else expected_root_gid
                    )
                    os.fchown(descriptor, expected_uid, expected_gid)
                    os.fchmod(descriptor, 0o600)
                    _write_all(descriptor, admitted[entry["target_relative_path"]])
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            for directory, names, _files in os.walk(staging, topdown=False):
                for name in names:
                    child = Path(directory) / name
                    os.chown(child, expected_root_uid, account.pw_gid)
                    os.chmod(child, 0o750)
            os.chown(staging, expected_root_uid, account.pw_gid)
            os.chmod(staging, 0o750)
            os.replace(staging, target_root)
            directory_descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        installed_entries = _verify_installed_input_set(
            manifest_payload,
            account=account,
            target_root=target_root,
            root_uid=expected_root_uid,
            root_gid=expected_root_gid,
        )

    if not manifest_exists:
        _atomic_private_bytes(
            installed_manifest,
            manifest_bytes,
            uid=expected_root_uid,
            gid=expected_root_gid,
        )
    receipt = _input_set_receipt_payload(
        manifest_payload,
        manifest_sha256=manifest_sha256,
        archive_sha256=archive_sha256,
        installed_entries=installed_entries,
        installed_at=now or datetime.now(timezone.utc),
    )
    if not receipt_exists:
        _atomic_private_bytes(
            installed_receipt,
            _canonical_bytes(receipt) + b"\n",
            uid=expected_root_uid,
            gid=expected_root_gid,
        )
    return receipt


def _parse_utc(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReleaseContractError(f"{field} must be canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ReleaseContractError(f"{field} is invalid") from exc
    if parsed.tzinfo != timezone.utc or parsed.microsecond:
        raise ReleaseContractError(f"{field} must have whole UTC seconds")
    return parsed


def _sample_utc(
    *,
    now: datetime | None,
    clock: Callable[[], datetime] | None,
    label: str,
) -> datetime:
    """Sample one authority-bound whole-second UTC time from an injectable clock."""
    observed = now if clock is None and now is not None else (
        clock() if clock is not None else datetime.now(timezone.utc)
    )
    if not isinstance(observed, datetime) or observed.tzinfo is None:
        raise ReleaseContractError(f"{label} clock must be timezone-aware")
    return observed.astimezone(timezone.utc).replace(microsecond=0)


def guard_campaign_clock(
    *,
    role: str,
    now: datetime | None = None,
    observed_node: str | None = None,
) -> None:
    _require_host_role(role, observed_node=observed_node)
    if role == "writer" and (ROLLBACK_RECEIPT.exists() or ROLLBACK_RECEIPT.is_symlink()):
        raise ReleaseContractError("campaign release has an immutable rollback receipt")
    if role == "standby" and (
        STANDBY_STOP_MARKER.exists() or STANDBY_STOP_MARKER.is_symlink()
    ):
        raise ReleaseContractError("standby receiver has reached its immutable deadline")
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ReleaseContractError("campaign clock must be timezone-aware")
    observed = observed.astimezone(timezone.utc).replace(microsecond=0)
    start = _parse_utc(CAMPAIGN_START_UTC, "campaign_start_utc")
    stop = _parse_utc(CAMPAIGN_STOP_UTC, "campaign_stop_utc")
    if observed < start or observed >= stop:
        raise ReleaseContractError("campaign process is outside the exact timebox")


def guard_runtime_binding(
    *,
    role: str,
    receipt_path: Path = RUNTIME_BINDING_RECEIPT_TARGET,
    now: datetime | None = None,
    observed_node: str | None = None,
) -> dict[str, Any]:
    """Root ExecCondition for the exact post-bootstrap authority transaction."""
    if os.geteuid() != 0:
        raise ReleaseContractError("runtime binding gate requires root")
    if role != "writer":
        raise ReleaseContractError("runtime binding exists only on the writer")
    guard_campaign_clock(role=role, now=now, observed_node=observed_node)
    account = _require_static_service_identity()
    return verify_runtime_binding_activation(
        receipt_path=receipt_path,
        account=account,
        now=now,
    )


def guard_campaign_stop(
    *,
    role: str,
    now: datetime | None = None,
    observed_node: str | None = None,
) -> datetime:
    """Admit stop enforcement only at or after the exact UTC deadline."""
    _require_host_role(role, observed_node=observed_node)
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ReleaseContractError("campaign stop clock must be timezone-aware")
    observed = observed.astimezone(timezone.utc)
    stop = _parse_utc(CAMPAIGN_STOP_UTC, "campaign_stop_utc")
    if observed < stop:
        raise ReleaseContractError("campaign stop cannot run before the exact deadline")
    return observed


def _require_hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise ReleaseContractError(f"{field} must be lowercase sha256")
    if value == "0" * 64:
        raise ReleaseContractError(f"{field} cannot be a placeholder")
    return value


def validate_manifest(
    payload: Mapping[str, Any],
    *,
    now: datetime | None = None,
    for_activation: bool = False,
) -> dict[str, Any]:
    """Validate the exact deployment-candidate type without coercion."""
    if set(payload) != _MANIFEST_FIELDS:
        missing = sorted(_MANIFEST_FIELDS - set(payload))
        extra = sorted(set(payload) - _MANIFEST_FIELDS)
        raise ReleaseContractError(
            f"manifest fields differ: missing={missing} extra={extra}"
        )
    exact = {
        "schema_version": SCHEMA_VERSION,
        "mission_id": MISSION_ID,
        "campaign_start_utc": CAMPAIGN_START_UTC,
        "campaign_stop_utc": CAMPAIGN_STOP_UTC,
        "cash_budget_usd": 0,
        "release_class": RELEASE_CLASS,
        "canonical_or_merged": False,
        "canonical_origin": CANONICAL_ORIGIN,
        "accepted_base_sha": ACCEPTED_BASE_SHA,
        "writer_node": WRITER_NODE,
        "standby_node": STANDBY_NODE,
        "api_listen": API_LISTEN,
        "dashboard_listen": DASHBOARD_LISTEN,
        "tailscale_exposure": TAILSCALE_EXPOSURE,
        "automatic_failover": False,
        "standby_writer_enabled": False,
        "python_version": "3.12",
        "venv_copies": True,
        "release_root": RELEASE_ROOT,
        "state_root": STATE_ROOT,
        "workspace_root": WORKSPACE_ROOT,
        "api_state_root": API_STATE_ROOT,
        "snapshot_root": SNAPSHOT_ROOT,
        "env_files": list(ENV_FILES),
        "uv_version": UV_VERSION,
        "uv_wheel_file": UV_WHEEL_FILE,
        "uv_wheel_sha256": UV_WHEEL_SHA256,
        "input_set_manifest_file": INPUT_SET_MANIFEST_FILE,
        "input_set_archive_file": INPUT_SET_ARCHIVE_FILE,
        "deployment_known_hosts_file": DEPLOYMENT_KNOWN_HOSTS_FILE,
        "deployment_known_hosts_sha256": DEPLOYMENT_KNOWN_HOSTS_SHA256,
        "tracked_source_manifest_file": TRACKED_SOURCE_MANIFEST_FILE,
    }
    mismatches = {
        key: {"expected": value, "actual": payload.get(key)}
        for key, value in exact.items()
        if payload.get(key) != value
    }
    if mismatches:
        raise ReleaseContractError(f"manifest exact bindings differ: {mismatches}")
    if isinstance(payload["cash_budget_usd"], bool) or not isinstance(
        payload["cash_budget_usd"], int
    ):
        raise ReleaseContractError("cash_budget_usd must be the integer zero")
    for field in (
        "canonical_or_merged",
        "automatic_failover",
        "standby_writer_enabled",
        "venv_copies",
    ):
        if not isinstance(payload[field], bool):
            raise ReleaseContractError(f"{field} must be boolean")
    if not isinstance(payload["env_files"], list) or not all(
        isinstance(value, str) for value in payload["env_files"]
    ):
        raise ReleaseContractError("env_files must be an exact string list")
    release_sha = payload["release_sha"]
    if not isinstance(release_sha, str) or not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("release_sha must be an exact commit")
    integration_base_sha = payload["integration_base_sha"]
    if not isinstance(integration_base_sha, str) or not _COMMIT_RE.fullmatch(
        integration_base_sha
    ):
        raise ReleaseContractError("integration_base_sha must be an exact commit")
    if integration_base_sha == release_sha:
        raise ReleaseContractError(
            "release_sha must be a child of integration_base_sha"
        )
    for field in (
        "bundle_sha256",
        "work_packet_sha256",
        "work_packet_digest",
        "closeout_receipt_sha256",
        "uv_wheel_sha256",
        "input_set_manifest_sha256",
        "input_set_archive_sha256",
        "input_set_digest",
        "deployment_known_hosts_sha256",
        "tracked_source_manifest_sha256",
        "tracked_source_digest",
        "manifest_digest",
    ):
        _require_hash(payload[field], field)
    for field in (
        "bundle_file",
        "closeout_receipt_file",
        "input_set_manifest_file",
        "input_set_archive_file",
        "deployment_known_hosts_file",
        "tracked_source_manifest_file",
    ):
        value = payload[field]
        if not isinstance(value, str) or not _BASENAME_RE.fullmatch(value):
            raise ReleaseContractError(f"{field} must be a basename")
    work_packet_path = payload["work_packet_path"]
    if not isinstance(work_packet_path, str) or not _PACKET_PATH_RE.fullmatch(
        work_packet_path
    ):
        raise ReleaseContractError(
            "work_packet_path must be a canonical tracked packet"
        )
    tracked_source_entry_count = payload["tracked_source_entry_count"]
    if (
        isinstance(tracked_source_entry_count, bool)
        or not isinstance(tracked_source_entry_count, int)
        or not 0 < tracked_source_entry_count <= _MAX_TRACKED_SOURCE_ENTRIES
    ):
        raise ReleaseContractError("tracked_source_entry_count is invalid")
    if manifest_digest(payload) != payload["manifest_digest"]:
        raise ReleaseContractError("manifest self-digest mismatch")
    start = _parse_utc(payload["campaign_start_utc"], "campaign_start_utc")
    stop = _parse_utc(payload["campaign_stop_utc"], "campaign_stop_utc")
    if stop <= start:
        raise ReleaseContractError("campaign stop must follow start")
    if for_activation:
        observed = now or datetime.now(timezone.utc)
        if observed.tzinfo is None:
            raise ReleaseContractError("activation clock must be timezone-aware")
        observed = observed.astimezone(timezone.utc)
        if observed < start:
            raise ReleaseContractError(
                "campaign cannot activate before its exact start"
            )
        if observed >= stop:
            raise ReleaseContractError(
                "campaign cannot activate at or after its exact stop"
            )
    return dict(payload)


def _require_secure_parent_chain(path: Path) -> None:
    if not path.is_absolute():
        raise ReleaseContractError("security-bound artifact path must be absolute")
    current = Path(path.anchor)
    for part in path.parts[1:-1]:
        current /= part
        try:
            identity = current.lstat()
        except OSError as exc:
            raise ReleaseContractError("artifact parent chain is unavailable") from exc
        mode = stat.S_IMODE(identity.st_mode)
        sticky_root = bool(identity.st_uid == 0 and identity.st_mode & stat.S_ISVTX)
        if (
            not stat.S_ISDIR(identity.st_mode)
            or current.is_symlink()
            or identity.st_uid not in {0, os.geteuid()}
            or (mode & 0o022 and not sticky_root)
        ):
            raise ReleaseContractError(
                f"artifact parent lacks secure custody: {current.name}"
            )


def _secure_json(path: Path, *, require_private: bool) -> dict[str, Any]:
    path = path.expanduser()
    _require_secure_parent_chain(path)
    try:
        identity = path.lstat()
    except OSError as exc:
        raise ReleaseContractError(f"cannot stat JSON artifact: {path.name}") from exc
    mode = stat.S_IMODE(identity.st_mode)
    if (
        not stat.S_ISREG(identity.st_mode)
        or path.is_symlink()
        or identity.st_uid != os.geteuid()
        or identity.st_nlink != 1
        or not 0 < identity.st_size <= _MAX_JSON_BYTES
        or (require_private and mode != 0o600)
        or (not require_private and mode & 0o022)
    ):
        raise ReleaseContractError(f"JSON artifact lacks required custody: {path.name}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    if not getattr(os, "O_NOFOLLOW", 0):
        raise ReleaseContractError("platform lacks no-follow file admission")
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (identity.st_dev, identity.st_ino):
            raise ReleaseContractError("JSON artifact changed during open")
        raw = b""
        while len(raw) <= _MAX_JSON_BYTES:
            chunk = os.read(descriptor, min(65_536, _MAX_JSON_BYTES + 1 - len(raw)))
            if not chunk:
                break
            raw += chunk
        if len(raw) > _MAX_JSON_BYTES:
            raise ReleaseContractError("JSON artifact exceeds size bound")
    finally:
        os.close(descriptor)
    try:
        decoded = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseContractError(f"invalid JSON artifact: {path.name}") from exc
    if not isinstance(decoded, dict):
        raise ReleaseContractError("JSON artifact root must be an object")
    return decoded


def load_manifest(
    path: Path | str,
    *,
    now: datetime | None = None,
    for_activation: bool = False,
) -> dict[str, Any]:
    return validate_manifest(
        _secure_json(Path(path), require_private=True),
        now=now,
        for_activation=for_activation,
    )


def sha256_file(path: Path, *, max_bytes: int = _MAX_ARTIFACT_BYTES) -> str:
    path = path.expanduser()
    _require_secure_parent_chain(path)
    try:
        identity = path.lstat()
    except OSError as exc:
        raise ReleaseContractError(f"cannot stat artifact: {path.name}") from exc
    if (
        not stat.S_ISREG(identity.st_mode)
        or path.is_symlink()
        or identity.st_nlink != 1
        or not 0 < identity.st_size <= max_bytes
        or stat.S_IMODE(identity.st_mode) & 0o022
    ):
        raise ReleaseContractError(
            f"artifact lacks bounded regular custody: {path.name}"
        )
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (identity.st_dev, identity.st_ino):
            raise ReleaseContractError("artifact changed during open")
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def _write_all(descriptor: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise ReleaseContractError("artifact write made no progress")
        remaining = remaining[written:]


def _download_pinned_uv_wheel(destination: Path) -> None:
    """Fetch the sole admitted Linux wheel into a new private file."""
    if destination.exists() or destination.is_symlink():
        raise ReleaseContractError("pinned uv wheel destination already exists")
    request = urllib.request.Request(
        UV_WHEEL_URL,
        headers={"Accept-Encoding": "identity", "User-Agent": "dharma-sadhana/1"},
    )
    created = False
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        digest = hashlib.sha256()
        observed = 0
        try:
            try:
                with urllib.request.urlopen(  # noqa: S310
                    request, timeout=30
                ) as response:
                    if response.geturl() != UV_WHEEL_URL:
                        raise ReleaseContractError("pinned uv wheel URL redirected")
                    content_length = response.headers.get("Content-Length")
                    if (
                        content_length is not None
                        and int(content_length) > _MAX_UV_WHEEL_BYTES
                    ):
                        raise ReleaseContractError("pinned uv wheel exceeds size bound")
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        observed += len(chunk)
                        if observed > _MAX_UV_WHEEL_BYTES:
                            raise ReleaseContractError(
                                "pinned uv wheel exceeds size bound"
                            )
                        digest.update(chunk)
                        _write_all(descriptor, chunk)
            except (OSError, ValueError, urllib.error.URLError) as exc:
                raise ReleaseContractError("pinned uv wheel download failed") from exc
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if observed == 0 or digest.hexdigest() != UV_WHEEL_SHA256:
            raise ReleaseContractError("pinned uv wheel digest differs")
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise


def _materialize_uv_wheel(destination: Path, source: Path | None) -> None:
    if source is None:
        _download_pinned_uv_wheel(destination)
        return
    if sha256_file(source, max_bytes=_MAX_UV_WHEEL_BYTES) != UV_WHEEL_SHA256:
        raise ReleaseContractError("supplied uv wheel digest differs")
    if destination.exists() or destination.is_symlink():
        raise ReleaseContractError("pinned uv wheel destination already exists")
    source_identity = source.lstat()
    source_descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    created = False
    try:
        opened_source = os.fstat(source_descriptor)
        if (opened_source.st_dev, opened_source.st_ino) != (
            source_identity.st_dev,
            source_identity.st_ino,
        ):
            raise ReleaseContractError("supplied uv wheel changed during open")
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        try:
            while True:
                chunk = os.read(source_descriptor, 1024 * 1024)
                if not chunk:
                    break
                _write_all(descriptor, chunk)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise
    finally:
        os.close(source_descriptor)
    if sha256_file(destination, max_bytes=_MAX_UV_WHEEL_BYTES) != UV_WHEEL_SHA256:
        destination.unlink(missing_ok=True)
        raise ReleaseContractError("copied uv wheel digest differs")


def _validate_pinned_uv_tree(
    root: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    execution_uid: int | None,
    execution_gid: int | None,
    execute_version: bool,
    allow_legacy_private_modes: bool = False,
) -> Path:
    marker = root / "INSTALL.json"
    bin_root = root / "bin"
    binary = root / "bin" / "uv"
    try:
        root_identity = root.lstat()
        bin_identity = bin_root.lstat()
        marker_identity = marker.lstat()
        binary_identity = binary.lstat()
        root_entries = {entry.name for entry in root.iterdir()}
        bin_entries = {entry.name for entry in bin_root.iterdir()}
    except OSError as exc:
        raise ReleaseContractError("pinned uv tree is unavailable") from exc
    directory_modes = {0o755}
    executable_modes = {0o755}
    marker_modes = {0o644}
    if allow_legacy_private_modes:
        directory_modes.add(0o700)
        executable_modes.add(0o700)
        marker_modes.add(0o600)
    if (
        root.is_symlink()
        or not stat.S_ISDIR(root_identity.st_mode)
        or bin_root.is_symlink()
        or not stat.S_ISDIR(bin_identity.st_mode)
        or marker.is_symlink()
        or not stat.S_ISREG(marker_identity.st_mode)
        or marker_identity.st_nlink != 1
        or binary.is_symlink()
        or not stat.S_ISREG(binary_identity.st_mode)
        or binary_identity.st_nlink != 1
        or root_entries != {"INSTALL.json", "bin"}
        or bin_entries != {"uv"}
    ):
        raise ReleaseContractError("pinned uv root is not a regular directory")
    expected_uid = os.geteuid()
    expected_gid = os.getegid()
    custody = (
        (root_identity, directory_modes),
        (bin_identity, directory_modes),
        (marker_identity, marker_modes),
        (binary_identity, executable_modes),
    )
    if any(
        identity.st_uid != expected_uid
        or identity.st_gid != expected_gid
        or stat.S_IMODE(identity.st_mode) not in allowed_modes
        for identity, allowed_modes in custody
    ):
        raise ReleaseContractError("pinned uv tree lacks exact custody")
    expected_marker = {
        "schema_version": "dharma.sadhana.pinned_uv.v1",
        "uv_version": UV_VERSION,
        "wheel_file": UV_WHEEL_FILE,
        "wheel_sha256": UV_WHEEL_SHA256,
    }
    try:
        marker_payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseContractError("pinned uv install marker is invalid") from exc
    if marker_payload != expected_marker:
        raise ReleaseContractError("pinned uv install marker differs")
    if not execute_version:
        return binary
    if (
        execution_uid is None
        or execution_gid is None
        or execution_uid <= 0
        or execution_gid <= 0
    ):
        raise ReleaseContractError("pinned uv execution lacks a non-root identity")
    result = runner(
        (str(binary), "--version"),
        cwd=root,
        check=False,
        run_uid=execution_uid,
        run_gid=execution_gid,
        no_new_privileges=True,
    )
    words = result.stdout.strip().split()
    if result.returncode != 0 or words[:2] != ["uv", UV_VERSION]:
        raise ReleaseContractError("pinned uv executable version differs")
    return binary


def _normalize_pinned_uv_tree_modes(root: Path) -> None:
    """Converge only the admitted legacy-private uv tree to executable custody."""
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ReleaseContractError("platform lacks no-follow pinned uv custody")
    targets = (
        (root / "INSTALL.json", 0o644, {0o600, 0o644}, False),
        (root / "bin" / "uv", 0o755, {0o700, 0o755}, False),
        (root / "bin", 0o755, {0o700, 0o755}, True),
        (root, 0o755, {0o700, 0o755}, True),
    )
    for path, final_mode, admitted_modes, is_directory in targets:
        before = path.lstat()
        flags = os.O_RDONLY | nofollow
        if is_directory:
            flags |= os.O_DIRECTORY
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            expected_type = stat.S_ISDIR if is_directory else stat.S_ISREG
            if (
                path.is_symlink()
                or not expected_type(opened.st_mode)
                or (opened.st_dev, opened.st_ino)
                != (before.st_dev, before.st_ino)
                or opened.st_uid != os.geteuid()
                or opened.st_gid != os.getegid()
                or stat.S_IMODE(opened.st_mode) not in admitted_modes
                or (not is_directory and opened.st_nlink != 1)
            ):
                raise ReleaseContractError("pinned uv mode transition lacks custody")
            os.fchmod(descriptor, final_mode)
            os.fsync(descriptor)
            normalized = os.fstat(descriptor)
            if (
                (normalized.st_dev, normalized.st_ino)
                != (opened.st_dev, opened.st_ino)
                or normalized.st_uid != opened.st_uid
                or normalized.st_gid != opened.st_gid
                or stat.S_IMODE(normalized.st_mode) != final_mode
                or (not is_directory and normalized.st_nlink != 1)
            ):
                raise ReleaseContractError("pinned uv mode transition was not retained")
        finally:
            os.close(descriptor)


def provision_pinned_uv(
    wheel_path: Path,
    *,
    tooling_root: Path = UV_TOOLING_ROOT,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    execution_uid: int | None = None,
    execution_gid: int | None = None,
    execute_version: bool = False,
    system_name: str | None = None,
    machine: str | None = None,
) -> Path:
    """Install the hash-pinned x86_64 uv artifact without pip or PATH trust."""
    execute = runner or _run
    observed_system = system_name or platform.system()
    observed_machine = (machine or platform.machine()).lower()
    if observed_system != "Linux" or observed_machine not in {"x86_64", "amd64"}:
        raise ReleaseContractError("pinned uv artifact requires Linux x86_64")
    if sha256_file(wheel_path, max_bytes=_MAX_UV_WHEEL_BYTES) != UV_WHEEL_SHA256:
        raise ReleaseContractError("pinned uv wheel digest differs")
    tooling_root.mkdir(parents=True, exist_ok=True)
    if tooling_root.is_symlink():
        raise ReleaseContractError("pinned uv tooling root cannot be a symlink")
    os.chown(tooling_root, os.geteuid(), os.getegid())
    os.chmod(tooling_root, 0o755)
    target = tooling_root / f"uv-{UV_VERSION}"
    if target.exists() or target.is_symlink():
        _validate_pinned_uv_tree(
            target,
            runner=execute,
            execution_uid=None,
            execution_gid=None,
            execute_version=False,
            allow_legacy_private_modes=True,
        )
        _normalize_pinned_uv_tree_modes(target)
        return _validate_pinned_uv_tree(
            target,
            runner=execute,
            execution_uid=execution_uid,
            execution_gid=execution_gid,
            execute_version=execute_version,
        )
    staging = Path(tempfile.mkdtemp(prefix=".uv-staging-", dir=tooling_root))
    try:
        os.chmod(staging, 0o700)
        try:
            with zipfile.ZipFile(wheel_path) as archive:
                try:
                    member = archive.getinfo(UV_BINARY_MEMBER)
                except KeyError as exc:
                    raise ReleaseContractError(
                        "pinned uv wheel lacks its executable"
                    ) from exc
                if not 0 < member.file_size <= _MAX_UV_BINARY_BYTES:
                    raise ReleaseContractError(
                        "pinned uv executable exceeds size bound"
                    )
                with archive.open(member) as source:
                    binary_bytes = source.read(_MAX_UV_BINARY_BYTES + 1)
                if len(binary_bytes) != member.file_size:
                    raise ReleaseContractError("pinned uv executable length differs")
        except zipfile.BadZipFile as exc:
            raise ReleaseContractError("pinned uv wheel is not a ZIP archive") from exc
        if binary_bytes[:4] != b"\x7fELF" or binary_bytes[18:20] != b">\x00":
            raise ReleaseContractError("pinned uv executable is not x86_64 ELF")
        bin_root = staging / "bin"
        bin_root.mkdir(mode=0o755)
        os.chmod(bin_root, 0o700)
        binary = bin_root / "uv"
        descriptor = os.open(binary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o755)
        with os.fdopen(descriptor, "wb") as executable:
            executable.write(binary_bytes)
            executable.flush()
            os.fchmod(executable.fileno(), 0o700)
            os.fsync(executable.fileno())
        marker_payload = {
            "schema_version": "dharma.sadhana.pinned_uv.v1",
            "uv_version": UV_VERSION,
            "wheel_file": UV_WHEEL_FILE,
            "wheel_sha256": UV_WHEEL_SHA256,
        }
        marker = staging / "INSTALL.json"
        marker.write_bytes(_canonical_bytes(marker_payload) + b"\n")
        os.chmod(marker, 0o600)
        _validate_pinned_uv_tree(
            staging,
            runner=execute,
            execution_uid=None,
            execution_gid=None,
            execute_version=False,
            allow_legacy_private_modes=True,
        )
        _normalize_pinned_uv_tree_modes(staging)
        _validate_pinned_uv_tree(
            staging,
            runner=execute,
            execution_uid=None,
            execution_gid=None,
            execute_version=False,
        )
        if target.exists() or target.is_symlink():
            raise ReleaseContractError("pinned uv target appeared during installation")
        os.replace(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return _validate_pinned_uv_tree(
        target,
        runner=execute,
        execution_uid=execution_uid,
        execution_gid=execution_gid,
        execute_version=execute_version,
    )


def _run(
    argv: Sequence[str],
    *,
    cwd: Path,
    check: bool = True,
    env: Mapping[str, str] | None = None,
    run_uid: int | None = None,
    run_gid: int | None = None,
    no_new_privileges: bool = False,
) -> subprocess.CompletedProcess[str]:
    if not argv:
        raise ReleaseContractError("external command cannot be empty")
    if (run_uid is None) != (run_gid is None):
        raise ReleaseContractError("subprocess identity is only partially bound")
    demote: Callable[[], None] | None = None
    if run_uid is not None and run_gid is not None:
        if run_uid <= 0 or run_gid <= 0:
            raise ReleaseContractError("unprivileged subprocess identity differs")
        if os.geteuid() not in {0, run_uid}:
            raise ReleaseContractError("cannot enter the admitted subprocess identity")

        def demote() -> None:
            if no_new_privileges:
                libc = ctypes.CDLL(None, use_errno=True)
                prctl = getattr(libc, "prctl", None)
                if prctl is None or prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
                    error_number = ctypes.get_errno()
                    raise OSError(
                        error_number,
                        os.strerror(error_number),
                        "PR_SET_NO_NEW_PRIVS",
                    )
            if os.geteuid() == 0:
                os.setgroups([])
                os.setgid(run_gid)
                os.setuid(run_uid)
            if os.geteuid() != run_uid or os.getegid() != run_gid:
                raise OSError(errno.EPERM, "subprocess identity transition failed")
            os.umask(0o077)

    try:
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            env=dict(env) if env is not None else dict(_SAFE_SUBPROCESS_ENV),
            preexec_fn=demote,
        )
    except OSError as exc:
        raise ReleaseContractError(
            f"required executable is unavailable: {Path(argv[0]).name}"
        ) from exc
    if check and completed.returncode != 0:
        raise ReleaseContractError(
            f"command {Path(argv[0]).name} failed with exit {completed.returncode}"
        )
    return completed


def _git(repo: Path, *args: str, check: bool = True) -> str:
    if os.geteuid() == 0:
        raise ReleaseContractError("Git execution as root is forbidden")
    return _run((GIT_PATH, *args), cwd=repo, check=check).stdout.strip()


def _tracked_source_path(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise ReleaseContractError("tracked source path is invalid")
    try:
        value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ReleaseContractError("tracked source path must be ASCII") from exc
    pure = PurePosixPath(value)
    if (
        str(pure) != value
        or pure.is_absolute()
        or any(part in {"", ".", ".."} for part in pure.parts)
        or pure.parts[0] == ".git"
        or "\\" in value
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise ReleaseContractError("tracked source path is not canonical")
    for output_root in TRACKED_SOURCE_BUILD_OUTPUT_ROOTS:
        if value == output_root or value.startswith(f"{output_root}/"):
            raise ReleaseContractError(
                "tracked source overlaps a dependency/build output root"
            )
    return value


def validate_tracked_source_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the controller-authored commit-object byte ledger."""
    if set(payload) != _TRACKED_SOURCE_MANIFEST_FIELDS:
        raise ReleaseContractError("tracked source manifest fields differ")
    entries = payload.get("entries")
    if (
        payload.get("schema_version") != TRACKED_SOURCE_SCHEMA_VERSION
        or not _COMMIT_RE.fullmatch(str(payload.get("release_sha", "")))
        or payload.get("canonical_origin") != CANONICAL_ORIGIN
        or payload.get("git_object_format") != "sha1"
        or payload.get("build_output_roots")
        != list(TRACKED_SOURCE_BUILD_OUTPUT_ROOTS)
        or not isinstance(entries, list)
        or not 0 < len(entries) <= _MAX_TRACKED_SOURCE_ENTRIES
        or payload.get("tracked_entry_count") != len(entries)
    ):
        raise ReleaseContractError("tracked source manifest binding differs")
    admitted_entries: list[dict[str, Any]] = []
    prior_path = ""
    tracked_bytes = 0
    for raw_entry in entries:
        if not isinstance(raw_entry, dict) or set(raw_entry) != _TRACKED_SOURCE_ENTRY_FIELDS:
            raise ReleaseContractError("tracked source entry fields differ")
        path = _tracked_source_path(raw_entry.get("path"))
        if path <= prior_path:
            raise ReleaseContractError("tracked source entries are not uniquely sorted")
        prior_path = path
        kind = raw_entry.get("kind")
        git_mode = raw_entry.get("git_mode")
        if (kind, git_mode) not in {
            ("regular", "100644"),
            ("regular", "100755"),
            ("symlink", "120000"),
        }:
            raise ReleaseContractError("tracked source kind or Git mode differs")
        object_id = raw_entry.get("git_object_id")
        if not isinstance(object_id, str) or not _COMMIT_RE.fullmatch(object_id):
            raise ReleaseContractError("tracked source Git object ID differs")
        size_bytes = raw_entry.get("size_bytes")
        if (
            isinstance(size_bytes, bool)
            or not isinstance(size_bytes, int)
            or size_bytes < 0
            or size_bytes > _MAX_TRACKED_SOURCE_BYTES
        ):
            raise ReleaseContractError("tracked source entry size differs")
        _require_hash(raw_entry.get("sha256"), "tracked source entry sha256")
        tracked_bytes += size_bytes
        if tracked_bytes > _MAX_TRACKED_SOURCE_BYTES:
            raise ReleaseContractError("tracked source byte total exceeds bound")
        admitted_entries.append(dict(raw_entry))
    if payload.get("tracked_bytes") != tracked_bytes:
        raise ReleaseContractError("tracked source byte total differs")
    digest = payload.get("manifest_digest")
    _require_hash(digest, "tracked source manifest_digest")
    if manifest_digest(payload) != digest:
        raise ReleaseContractError("tracked source manifest self-digest differs")
    admitted = dict(payload)
    admitted["entries"] = admitted_entries
    return admitted


def _hash_git_blobs(
    repo: Path, object_ids: Sequence[str]
) -> dict[str, tuple[int, str]]:
    """Batch-hash exact objects without a worktree, filter, index, or root Git."""
    if os.geteuid() == 0:
        raise ReleaseContractError("Git object hashing as root is forbidden")
    if not object_ids or any(not _COMMIT_RE.fullmatch(value) for value in object_ids):
        raise ReleaseContractError("Git blob object ID differs")
    try:
        process = subprocess.Popen(
            (GIT_PATH, "cat-file", "--batch"),
            cwd=repo,
            env=dict(_SAFE_SUBPROCESS_ENV),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise ReleaseContractError("Git blob reader is unavailable") from exc
    if process.stdin is None or process.stdout is None or process.stderr is None:
        process.kill()
        process.wait()
        raise ReleaseContractError("Git blob reader pipes are unavailable")
    results: dict[str, tuple[int, str]] = {}
    try:
        for object_id in dict.fromkeys(object_ids):
            process.stdin.write(object_id.encode("ascii") + b"\n")
            process.stdin.flush()
            header = process.stdout.readline(256)
            try:
                header_id, object_kind, raw_size = header.rstrip(b"\n").split(b" ")
                size = int(raw_size)
            except (ValueError, OverflowError) as exc:
                raise ReleaseContractError("Git batch object header differs") from exc
            if (
                header_id.decode("ascii", "strict") != object_id
                or object_kind != b"blob"
                or size < 0
                or size > _MAX_TRACKED_SOURCE_BYTES
            ):
                raise ReleaseContractError("Git batch blob binding differs")
            digest = hashlib.sha256()
            remaining = size
            while remaining:
                chunk = process.stdout.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ReleaseContractError("Git batch blob ended early")
                digest.update(chunk)
                remaining -= len(chunk)
            if process.stdout.read(1) != b"\n":
                raise ReleaseContractError("Git batch blob framing differs")
            results[object_id] = (size, digest.hexdigest())
        process.stdin.close()
    except BaseException:
        process.kill()
        process.wait()
        raise
    stderr = process.stderr.read(65_537)
    returncode = process.wait()
    if returncode != 0 or stderr:
        raise ReleaseContractError("Git blob object could not be read exactly")
    return results


def render_tracked_source_manifest(
    repo_root: Path,
    release_sha: str,
) -> dict[str, Any]:
    """Render a trusted ledger directly from the exact commit tree objects."""
    if os.geteuid() == 0:
        raise ReleaseContractError("tracked source rendering cannot run as root")
    if not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("tracked source release SHA differs")
    repo = repo_root.resolve(strict=True)
    if _git(repo, "rev-parse", "--show-object-format") != "sha1":
        raise ReleaseContractError("canonical release must use sha1 Git objects")
    raw_tree = _run(
        (GIT_PATH, "ls-tree", "-rz", "--full-tree", release_sha),
        cwd=repo,
    ).stdout
    records = raw_tree.split("\0")
    if not records or records[-1] != "":
        raise ReleaseContractError("Git tree record framing differs")
    tree_entries: list[tuple[str, str, str]] = []
    for record in records[:-1]:
        try:
            metadata, raw_path = record.split("\t", 1)
            git_mode, object_kind, object_id = metadata.split(" ")
        except ValueError as exc:
            raise ReleaseContractError("Git tree record shape differs") from exc
        path = _tracked_source_path(raw_path)
        if object_kind != "blob" or git_mode not in {"100644", "100755", "120000"}:
            raise ReleaseContractError("Git tree contains an unsupported entry")
        tree_entries.append((path, git_mode, object_id))
    blob_hashes = _hash_git_blobs(repo, [entry[2] for entry in tree_entries])
    entries: list[dict[str, Any]] = []
    tracked_bytes = 0
    for path, git_mode, object_id in tree_entries:
        size_bytes, sha256 = blob_hashes[object_id]
        tracked_bytes += size_bytes
        if tracked_bytes > _MAX_TRACKED_SOURCE_BYTES:
            raise ReleaseContractError("tracked source byte total exceeds bound")
        entries.append(
            {
                "path": path,
                "kind": "symlink" if git_mode == "120000" else "regular",
                "git_mode": git_mode,
                "git_object_id": object_id,
                "size_bytes": size_bytes,
                "sha256": sha256,
            }
        )
    entries.sort(key=lambda entry: entry["path"])
    payload: dict[str, Any] = {
        "schema_version": TRACKED_SOURCE_SCHEMA_VERSION,
        "release_sha": release_sha,
        "canonical_origin": CANONICAL_ORIGIN,
        "git_object_format": "sha1",
        "entries": entries,
        "tracked_entry_count": len(entries),
        "tracked_bytes": tracked_bytes,
        "build_output_roots": list(TRACKED_SOURCE_BUILD_OUTPUT_ROOTS),
        "manifest_digest": "1" * 64,
    }
    payload["manifest_digest"] = manifest_digest(payload)
    encoded = _canonical_bytes(payload) + b"\n"
    if len(encoded) > _MAX_TRACKED_SOURCE_MANIFEST_BYTES:
        raise ReleaseContractError("tracked source manifest exceeds size bound")
    return validate_tracked_source_manifest(payload)


def verify_tracked_source_tree(
    repo_root: Path,
    payload: Mapping[str, Any],
    *,
    expected_uid: int = 0,
    expected_gid: int = 0,
    frozen: bool = True,
    require_build_outputs: bool = True,
    ignore_git_metadata: bool = False,
) -> dict[str, int | str]:
    """Rehash a closed candidate tree without consulting candidate Git metadata."""
    manifest = validate_tracked_source_manifest(payload)
    root = repo_root.resolve(strict=True)
    root_identity = root.lstat()
    expected_directory_mode = 0o555 if frozen else None
    if (
        repo_root.is_symlink()
        or not stat.S_ISDIR(root_identity.st_mode)
        or root_identity.st_uid != expected_uid
        or root_identity.st_gid != expected_gid
        or (
            expected_directory_mode is not None
            and stat.S_IMODE(root_identity.st_mode) != expected_directory_mode
        )
        or (
            expected_directory_mode is None
            and stat.S_IMODE(root_identity.st_mode) & 0o022
        )
    ):
        raise ReleaseContractError("tracked source root custody differs")
    expected_entries = {entry["path"]: entry for entry in manifest["entries"]}
    expected_directories: set[str] = set()
    for relative in (*expected_entries, *TRACKED_SOURCE_BUILD_OUTPUT_ROOTS):
        parts = PurePosixPath(relative).parts[:-1]
        for index in range(1, len(parts) + 1):
            expected_directories.add("/".join(parts[:index]))
    expected_outputs = set(TRACKED_SOURCE_BUILD_OUTPUT_ROOTS)
    seen_entries: set[str] = set()
    seen_outputs: set[str] = set()
    directory_flags = (
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )

    def require_directory(identity: os.stat_result, label: str) -> None:
        mode = stat.S_IMODE(identity.st_mode)
        if (
            not stat.S_ISDIR(identity.st_mode)
            or identity.st_uid != expected_uid
            or identity.st_gid != expected_gid
            or (frozen and mode != 0o555)
            or (not frozen and mode & 0o022)
        ):
            raise ReleaseContractError(f"tracked source directory custody differs: {label}")

    def walk(descriptor: int, prefix: str) -> None:
        before = os.fstat(descriptor)
        for name in sorted(os.listdir(descriptor), key=os.fsencode):
            relative = f"{prefix}/{name}" if prefix else name
            identity = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if relative == ".git" and ignore_git_metadata:
                require_directory(identity, relative)
                continue
            if relative in expected_outputs:
                require_directory(identity, relative)
                seen_outputs.add(relative)
                continue
            if stat.S_ISDIR(identity.st_mode):
                if relative not in expected_directories:
                    raise ReleaseContractError(
                        f"candidate contains an untracked directory: {relative}"
                    )
                child = os.open(name, directory_flags, dir_fd=descriptor)
                try:
                    opened = os.fstat(child)
                    if (opened.st_dev, opened.st_ino) != (
                        identity.st_dev,
                        identity.st_ino,
                    ):
                        raise ReleaseContractError(
                            "tracked source directory changed during open"
                        )
                    require_directory(opened, relative)
                    walk(child, relative)
                finally:
                    os.close(child)
                continue
            expected = expected_entries.get(relative)
            if expected is None:
                raise ReleaseContractError(
                    f"candidate contains an untracked source entry: {relative}"
                )
            if identity.st_uid != expected_uid or identity.st_gid != expected_gid:
                raise ReleaseContractError("tracked source entry custody differs")
            if expected["kind"] == "regular":
                expected_mode = (
                    0o555
                    if frozen and expected["git_mode"] == "100755"
                    else 0o444
                    if frozen
                    else 0o755
                    if expected["git_mode"] == "100755"
                    else 0o644
                )
                if (
                    not stat.S_ISREG(identity.st_mode)
                    or identity.st_nlink != 1
                    or stat.S_IMODE(identity.st_mode) != expected_mode
                    or identity.st_size != expected["size_bytes"]
                ):
                    raise ReleaseContractError("tracked source regular file differs")
                opened_file = os.open(
                    name,
                    os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=descriptor,
                )
                try:
                    opened = os.fstat(opened_file)
                    if (
                        opened.st_dev,
                        opened.st_ino,
                        opened.st_size,
                        opened.st_mtime_ns,
                    ) != (
                        identity.st_dev,
                        identity.st_ino,
                        identity.st_size,
                        identity.st_mtime_ns,
                    ):
                        raise ReleaseContractError(
                            "tracked source file changed during open"
                        )
                    digest = hashlib.sha256()
                    while True:
                        chunk = os.read(opened_file, 1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                    after = os.fstat(opened_file)
                    if (
                        after.st_dev,
                        after.st_ino,
                        after.st_size,
                        after.st_mtime_ns,
                    ) != (
                        opened.st_dev,
                        opened.st_ino,
                        opened.st_size,
                        opened.st_mtime_ns,
                    ):
                        raise ReleaseContractError(
                            "tracked source file changed while hashing"
                        )
                finally:
                    os.close(opened_file)
                if digest.hexdigest() != expected["sha256"]:
                    raise ReleaseContractError("tracked source file hash differs")
            else:
                if not stat.S_ISLNK(identity.st_mode) or identity.st_nlink != 1:
                    raise ReleaseContractError("tracked source symlink type differs")
                target = os.fsencode(os.readlink(name, dir_fd=descriptor))
                if (
                    len(target) != expected["size_bytes"]
                    or hashlib.sha256(target).hexdigest() != expected["sha256"]
                ):
                    raise ReleaseContractError("tracked source symlink bytes differ")
                try:
                    (root / relative).resolve(strict=True).relative_to(root)
                except (OSError, ValueError) as exc:
                    raise ReleaseContractError(
                        "tracked source symlink escapes or is broken"
                    ) from exc
            seen_entries.add(relative)
        after = os.fstat(descriptor)
        if (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ) != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns):
            raise ReleaseContractError("tracked source directory changed while hashing")

    root_descriptor = os.open(root, directory_flags)
    try:
        walk(root_descriptor, "")
    finally:
        os.close(root_descriptor)
    if seen_entries != set(expected_entries):
        raise ReleaseContractError("candidate tracked source set is incomplete")
    if require_build_outputs and seen_outputs != expected_outputs:
        raise ReleaseContractError("candidate dependency/build output roots are incomplete")
    return {
        "tracked_source_digest": manifest["manifest_digest"],
        "tracked_entry_count": len(seen_entries),
        "tracked_bytes": manifest["tracked_bytes"],
    }


def verify_checkout(repo_root: Path, manifest: Mapping[str, Any]) -> None:
    """Prove exact candidate source without asserting merge/canonical status."""
    if os.geteuid() == 0:
        raise ReleaseContractError("candidate Git verification cannot run as root")
    repo = repo_root.resolve(strict=True)
    if _git(repo, "rev-parse", "HEAD") != manifest["release_sha"]:
        raise ReleaseContractError("checkout HEAD differs from release_sha")
    if _git(repo, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ReleaseContractError("candidate checkout is not clean")
    if _git(repo, "remote", "get-url", "origin") != CANONICAL_ORIGIN:
        raise ReleaseContractError("origin is not the canonical AIKAGRYA repository")
    if _git(repo, "cat-file", "-t", manifest["release_sha"]) != "commit":
        raise ReleaseContractError("release_sha is not a commit")
    parents = _git(
        repo,
        "rev-list",
        "--parents",
        "-n",
        "1",
        manifest["release_sha"],
    ).split()
    if parents != [manifest["release_sha"], manifest["integration_base_sha"]]:
        raise ReleaseContractError(
            "release_sha must have integration_base_sha as its sole parent"
        )
    ancestry = _run(
        (
            GIT_PATH,
            "merge-base",
            "--is-ancestor",
            ACCEPTED_BASE_SHA,
            manifest["release_sha"],
        ),
        cwd=repo,
        check=False,
    )
    if ancestry.returncode != 0:
        raise ReleaseContractError("accepted base is not an ancestor of release_sha")
    packet_path = repo / manifest["work_packet_path"]
    if (
        sha256_file(packet_path, max_bytes=_MAX_JSON_BYTES)
        != manifest["work_packet_sha256"]
    ):
        raise ReleaseContractError("tracked work-packet bytes differ")
    packet = _secure_json(packet_path, require_private=False)
    entry = packet.get("session_entry")
    if (
        not isinstance(entry, dict)
        or entry.get("packet_digest") != manifest["work_packet_digest"]
    ):
        raise ReleaseContractError("tracked work-packet digest differs")


def verify_tracked_checkout(repo_root: Path, release_sha: str) -> None:
    """Re-check tracked bytes after dependency installation and dashboard build."""
    if not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("tracked checkout release SHA is invalid")
    repo = repo_root.resolve(strict=True)
    if _git(repo, "rev-parse", "HEAD") != release_sha:
        raise ReleaseContractError("built checkout HEAD differs from release_sha")
    status = _git(
        repo,
        "status",
        "--porcelain=v1",
        "--untracked-files=no",
        "--ignore-submodules=none",
    )
    if status:
        raise ReleaseContractError("build changed exact tracked source bytes")


def verify_dashboard_build(dashboard_root: Path) -> None:
    """Require Next's baked rewrites to target only the collision-free API."""
    routes = _secure_json(
        dashboard_root / ".next" / "routes-manifest.json",
        require_private=False,
    )
    rewrites = routes.get("rewrites")
    if not isinstance(rewrites, dict) or set(rewrites) != {
        "beforeFiles",
        "afterFiles",
        "fallback",
    }:
        raise ReleaseContractError("Next rewrite manifest has an unknown shape")
    if rewrites["beforeFiles"] != [] or rewrites["fallback"] != []:
        raise ReleaseContractError("Next build contains an unadmitted rewrite scope")
    after = rewrites["afterFiles"]
    if not isinstance(after, list):
        raise ReleaseContractError("Next afterFiles rewrites are invalid")
    projected: list[tuple[Any, Any]] = []
    for rule in after:
        if not isinstance(rule, dict):
            raise ReleaseContractError("Next rewrite rule is invalid")
        projected.append((rule.get("source"), rule.get("destination")))
    expected = [
        ("/api/:path*", f"{DASHBOARD_PROXY_URL}/api/:path*"),
        ("/ws/:path*", f"{DASHBOARD_PROXY_URL}/ws/:path*"),
    ]
    if projected != expected:
        raise ReleaseContractError("Next build rewrites differ from loopback 18420")


def _require_host_role(role: str, *, observed_node: str | None = None) -> str:
    if role not in {"writer", "standby"}:
        raise ReleaseContractError("role must be writer or standby")
    expected = WRITER_NODE if role == "writer" else STANDBY_NODE
    raw = observed_node if observed_node is not None else socket.gethostname()
    observed = str(raw).strip().split(".", 1)[0].lower()
    if observed != expected:
        raise ReleaseContractError("local host identity does not match requested role")
    return observed


def _require_loopback_ports_free(
    *,
    socket_factory: Callable[..., socket.socket] = socket.socket,
) -> None:
    """Preflight admitted IPv4 listeners, including the reserved control slot."""
    for port in (18420, 18421):
        probe = socket_factory(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise ReleaseContractError(
                f"campaign loopback port {port} is already occupied"
            ) from exc
        finally:
            probe.close()


def verify_envelope(
    manifest: Mapping[str, Any],
    *,
    repo_root: Path | None,
    bundle_path: Path,
    receipt_path: Path,
    uv_wheel_path: Path,
    input_set_manifest_path: Path | None,
    input_set_archive_path: Path | None,
    deployment_known_hosts_path: Path,
    tracked_source_manifest_path: Path,
    expected_role: str,
    now: datetime | None = None,
    observed_node: str | None = None,
) -> None:
    validate_manifest(manifest, now=now, for_activation=True)
    if expected_role not in {"writer", "standby"}:
        raise ReleaseContractError("role must be writer or standby")
    expected_node = WRITER_NODE if expected_role == "writer" else STANDBY_NODE
    if manifest[f"{expected_role}_node"] != expected_node:
        raise ReleaseContractError("role-to-node binding differs")
    _require_host_role(expected_role, observed_node=observed_node)
    if bundle_path.name != manifest["bundle_file"]:
        raise ReleaseContractError("bundle basename differs")
    if receipt_path.name != manifest["closeout_receipt_file"]:
        raise ReleaseContractError("receipt basename differs")
    if uv_wheel_path.name != manifest["uv_wheel_file"]:
        raise ReleaseContractError("uv wheel basename differs")
    if (
        tracked_source_manifest_path.name
        != manifest["tracked_source_manifest_file"]
        or sha256_file(
            tracked_source_manifest_path,
            max_bytes=_MAX_TRACKED_SOURCE_MANIFEST_BYTES,
        )
        != manifest["tracked_source_manifest_sha256"]
    ):
        raise ReleaseContractError("tracked source manifest artifact differs")
    tracked_source = validate_tracked_source_manifest(
        _secure_json(tracked_source_manifest_path, require_private=True)
    )
    if (
        tracked_source["release_sha"] != manifest["release_sha"]
        or tracked_source["manifest_digest"] != manifest["tracked_source_digest"]
        or tracked_source["tracked_entry_count"]
        != manifest["tracked_source_entry_count"]
    ):
        raise ReleaseContractError("tracked source release binding differs")
    if (
        deployment_known_hosts_path.name != manifest["deployment_known_hosts_file"]
        or hashlib.sha256(
            _read_deployment_known_hosts(deployment_known_hosts_path)
        ).hexdigest()
        != manifest["deployment_known_hosts_sha256"]
    ):
        raise ReleaseContractError("deployment known_hosts differs")
    if expected_role == "writer" and (
        input_set_manifest_path is None or input_set_archive_path is None
    ):
        raise ReleaseContractError(
            "writer verification requires the immutable input set"
        )
    if (input_set_manifest_path is None) != (input_set_archive_path is None):
        raise ReleaseContractError("input-set verification artifacts are partial")
    if sha256_file(bundle_path) != manifest["bundle_sha256"]:
        raise ReleaseContractError("bundle hash differs")
    if (
        sha256_file(receipt_path, max_bytes=_MAX_JSON_BYTES)
        != manifest["closeout_receipt_sha256"]
    ):
        raise ReleaseContractError("closeout receipt hash differs")
    if (
        sha256_file(uv_wheel_path, max_bytes=_MAX_UV_WHEEL_BYTES)
        != manifest["uv_wheel_sha256"]
    ):
        raise ReleaseContractError("uv wheel hash differs")
    if input_set_manifest_path is not None and input_set_archive_path is not None:
        if (
            input_set_manifest_path.name != manifest["input_set_manifest_file"]
            or input_set_archive_path.name != manifest["input_set_archive_file"]
            or sha256_file(input_set_manifest_path, max_bytes=_MAX_JSON_BYTES)
            != manifest["input_set_manifest_sha256"]
            or sha256_file(input_set_archive_path, max_bytes=_MAX_INPUT_SET_BYTES)
            != manifest["input_set_archive_sha256"]
        ):
            raise ReleaseContractError("input-set release artifacts differ")
        input_payload = validate_input_set_manifest(
            _secure_json(input_set_manifest_path, require_private=True)
        )
        if input_payload["input_set_digest"] != manifest["input_set_digest"]:
            raise ReleaseContractError("input-set digest differs from release manifest")
        validate_input_set_archive(input_payload, input_set_archive_path)
    receipt = _secure_json(receipt_path, require_private=False)
    if receipt.get("status") != "passed" or receipt.get("phase") != "closeout":
        raise ReleaseContractError("closeout receipt is not a passed closeout")
    if receipt.get("packet_digest") != manifest["work_packet_digest"]:
        raise ReleaseContractError("closeout receipt is not bound to the work packet")
    if receipt.get("packet_bytes_sha256") != manifest["work_packet_sha256"]:
        raise ReleaseContractError("closeout receipt is not bound to packet bytes")
    if receipt.get("target_head") != manifest["release_sha"]:
        raise ReleaseContractError("closeout receipt is not bound to release_sha")
    if repo_root is not None:
        verify_checkout(repo_root, manifest)
    verify_bundle_checkout(
        bundle_path,
        manifest,
        tracked_source_manifest=tracked_source,
    )


def verify_bundle_checkout(
    bundle_path: Path,
    manifest: Mapping[str, Any],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    tracked_source_manifest: Mapping[str, Any] | None = None,
) -> None:
    """Materialize a disposable checkout to prove the transferred bundle."""
    if os.geteuid() == 0:
        raise ReleaseContractError("bundle Git verification cannot run as root")
    with tempfile.TemporaryDirectory(prefix="sadhana-bundle-verify-") as raw_root:
        root = Path(raw_root)
        checkout = root / "repo"
        runner(
            (GIT_PATH, "clone", "--no-checkout", str(bundle_path), str(checkout)),
            cwd=root,
        )
        runner(
            (GIT_PATH, "checkout", "--detach", manifest["release_sha"]),
            cwd=checkout,
        )
        runner(
            (GIT_PATH, "remote", "set-url", "origin", CANONICAL_ORIGIN),
            cwd=checkout,
        )
        verify_checkout(checkout, manifest)
        if tracked_source_manifest is not None:
            checkout_identity = checkout.lstat()
            verify_tracked_source_tree(
                checkout,
                tracked_source_manifest,
                expected_uid=os.geteuid(),
                expected_gid=checkout_identity.st_gid,
                frozen=False,
                require_build_outputs=False,
                ignore_git_metadata=True,
            )


def verify_venv(
    venv_root: Path,
    *,
    expected_uid: int | None = None,
    execution_uid: int | None = None,
    execution_gid: int | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    execute_version: bool = True,
) -> None:
    """Require copied Python 3.12 and reject every link escaping the venv."""
    if venv_root.is_symlink():
        raise ReleaseContractError("venv root cannot be a symlink")
    root = venv_root.resolve(strict=True)
    root_identity = root.lstat()
    admitted_uid = os.geteuid() if expected_uid is None else expected_uid
    if (
        root_identity.st_uid != admitted_uid
        or stat.S_IMODE(root_identity.st_mode) & 0o022
    ):
        raise ReleaseContractError("venv root lacks owner-only write custody")
    python = root / "bin" / "python"
    if python.is_symlink() or not python.is_file() or python.lstat().st_nlink != 1:
        raise ReleaseContractError("venv Python must be a copied regular file")
    for directory, names, files in os.walk(root, followlinks=False):
        for name in (*names, *files):
            candidate = Path(directory) / name
            identity = candidate.lstat()
            if identity.st_uid != admitted_uid:
                raise ReleaseContractError("venv tree lacks owner-only write custody")
            if stat.S_ISLNK(identity.st_mode):
                try:
                    resolved = candidate.resolve(strict=True)
                    resolved.relative_to(root)
                except (OSError, ValueError) as exc:
                    raise ReleaseContractError(
                        f"venv link escapes or is broken: {candidate.relative_to(root)}"
                    ) from exc
                continue
            if stat.S_IMODE(identity.st_mode) & 0o022:
                raise ReleaseContractError("venv tree lacks owner-only write custody")
    if not execute_version:
        return
    if (
        execution_uid is None
        or execution_gid is None
        or execution_uid <= 0
        or execution_gid <= 0
    ):
        raise ReleaseContractError("venv execution lacks a non-root identity")
    version = runner(
        (str(python), "--version"),
        cwd=root,
        run_uid=execution_uid,
        run_gid=execution_gid,
        no_new_privileges=True,
    ).stdout.strip()
    if not version.startswith("Python 3.12."):
        raise ReleaseContractError("venv must use Python 3.12")


def _run_build_command(
    runner: Callable[..., subprocess.CompletedProcess[str]],
    argv: Sequence[str],
    *,
    cwd: Path,
    account: pwd.struct_passwd,
    env: Mapping[str, str],
) -> subprocess.CompletedProcess[str]:
    if account.pw_uid <= 0 or account.pw_gid <= 0:
        raise ReleaseContractError("build command cannot run as root")
    return runner(
        argv,
        cwd=cwd,
        env=env,
        run_uid=account.pw_uid,
        run_gid=account.pw_gid,
        no_new_privileges=True,
    )


def _freeze_release_tree(
    root: Path,
    *,
    build_uid: int,
    build_gid: int,
    build_processes_proven_absent: bool,
) -> None:
    """Freeze a quiescent build via a root top-directory and dirfd barrier."""
    if not build_processes_proven_absent:
        raise ReleaseContractError("build process cessation is unproven")
    identity = root.lstat()
    if (
        root.is_symlink()
        or not stat.S_ISDIR(identity.st_mode)
        or identity.st_uid != build_uid
        or identity.st_gid != build_gid
    ):
        raise ReleaseContractError("unprivileged release tree custody differs")
    resolved_root = root.resolve(strict=True)
    # Read-only preflight happens before the first privileged metadata mutation.
    # It rejects every way a build-owned inode could reach outside the staging
    # tree when root later changes ownership.
    for directory, names, files in os.walk(root, followlinks=False):
        for name in (*names, *files):
            path = Path(directory) / name
            item = path.lstat()
            if item.st_uid != build_uid or item.st_gid != build_gid:
                raise ReleaseContractError("build output escaped its build identity")
            if stat.S_ISLNK(item.st_mode):
                try:
                    path.resolve(strict=True).relative_to(resolved_root)
                except (OSError, ValueError) as exc:
                    raise ReleaseContractError(
                        "release tree contains an escaping or broken symlink"
                    ) from exc
            elif stat.S_ISREG(item.st_mode):
                if item.st_nlink != 1:
                    raise ReleaseContractError(
                        "release tree contains a hardlinked file"
                    )
            elif not stat.S_ISDIR(item.st_mode):
                raise ReleaseContractError("release tree contains a special file")

    directory_flags = (
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    root_descriptor = os.open(root, directory_flags)
    try:
        opened_root = os.fstat(root_descriptor)
        if (
            (opened_root.st_dev, opened_root.st_ino)
            != (identity.st_dev, identity.st_ino)
            or opened_root.st_uid != build_uid
            or opened_root.st_gid != build_gid
        ):
            raise ReleaseContractError("release root changed before freeze barrier")
        # Once the top directory is root:root0700, the retired build uid cannot
        # use even a pre-opened dirfd to mutate its namespace.
        os.fchown(root_descriptor, 0, 0)
        os.fchmod(root_descriptor, 0o700)

        def freeze_directory(descriptor: int) -> None:
            for name in sorted(os.listdir(descriptor), key=os.fsencode):
                admitted = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                if stat.S_ISDIR(admitted.st_mode):
                    child = os.open(name, directory_flags, dir_fd=descriptor)
                    try:
                        opened = os.fstat(child)
                        if (
                            (opened.st_dev, opened.st_ino)
                            != (admitted.st_dev, admitted.st_ino)
                            or opened.st_uid != build_uid
                            or opened.st_gid != build_gid
                        ):
                            raise ReleaseContractError(
                                "release directory changed during freeze"
                            )
                        freeze_directory(child)
                        os.fchown(child, 0, 0)
                        os.fchmod(child, 0o555)
                        os.fsync(child)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(admitted.st_mode):
                    if admitted.st_nlink != 1:
                        raise ReleaseContractError(
                            "release file link count changed during freeze"
                        )
                    file_descriptor = os.open(
                        name,
                        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                        dir_fd=descriptor,
                    )
                    try:
                        opened = os.fstat(file_descriptor)
                        if (
                            (opened.st_dev, opened.st_ino)
                            != (admitted.st_dev, admitted.st_ino)
                            or opened.st_uid != build_uid
                            or opened.st_gid != build_gid
                            or opened.st_nlink != 1
                        ):
                            raise ReleaseContractError(
                                "release file changed during freeze"
                            )
                        os.fchown(file_descriptor, 0, 0)
                        executable = bool(stat.S_IMODE(opened.st_mode) & 0o111)
                        os.fchmod(file_descriptor, 0o555 if executable else 0o444)
                        # Persist the final root/read-only inode metadata before
                        # the containing frozen tree is promoted.
                        os.fsync(file_descriptor)
                    finally:
                        os.close(file_descriptor)
                elif stat.S_ISLNK(admitted.st_mode):
                    os.chown(
                        name,
                        0,
                        0,
                        dir_fd=descriptor,
                        follow_symlinks=False,
                    )
                else:
                    raise ReleaseContractError("release tree changed during freeze")
            os.fsync(descriptor)

        freeze_directory(root_descriptor)
        os.fchmod(root_descriptor, 0o555)
        os.fsync(root_descriptor)
    finally:
        os.close(root_descriptor)


def _unit_templates(repo_root: Path) -> list[Path]:
    root = repo_root / SYSTEMD_TEMPLATE_ROOT
    templates = sorted(path for path in root.iterdir() if path.is_file())
    if not templates:
        raise ReleaseContractError("systemd template set is empty")
    return templates


def _unit_section_assignments(text: str, section: str) -> list[str]:
    """Return every effective assignment line from all copies of one section."""

    wanted = f"[{section}]"
    active_section: str | None = None
    assignments: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            active_section = line
        elif (
            active_section == wanted
            and line
            and not line.startswith(("#", ";"))
        ):
            assignments.append(line)
    return assignments


def validate_unit_text(name: str, text: str, *, rendered: bool) -> None:
    lowered = text.lower()
    canonical_name = name.removesuffix(".in")
    if "0.0.0.0" in text or "[::]" in text or "tailscale funnel" in lowered:
        raise ReleaseContractError(f"unit {name} permits public exposure")
    if re.search(r"(?<![0-9])3000(?![0-9])", text):
        raise ReleaseContractError(f"unit {name} retains the forbidden TCP dashboard")
    if name == "dharma-sadhana-private-serve.service":
        release_binding = r"(?:@RELEASE_SHA@|[0-9a-f]{40})"
        required = re.search(
            r"sadhana_release\.py tailscale-start --role writer --release-sha "
            + release_binding,
            text,
        )
        stop = re.search(
            r"sadhana_release\.py tailscale-stop --role writer --release-sha "
            + release_binding,
            text,
        )
        if (
            required is None
            or stop is None
            or "ReadWritePaths=/etc/dharma-sadhana/receipts/preactivation"
            not in text
            or "ReadWritePaths=/run/dharma-sadhana/tailscale" in text
        ):
            raise ReleaseContractError(
                "private Serve unit lacks the owned-config start/stop contract"
            )
    if canonical_name == STANDBY_REPLICATION_SERVE_UNIT:
        release_binding = r"(?:@RELEASE_SHA@|[0-9a-f]{40})"
        start = re.search(
            r"sadhana_release\.py standby-tailscale-start --role standby "
            r"--release-sha " + release_binding,
            text,
        )
        stop = re.search(
            r"sadhana_release\.py standby-tailscale-stop --role standby "
            r"--release-sha " + release_binding,
            text,
        )
        required_transport_fragments = (
            "Requires=tailscaled.service",
            "After=network-online.target tailscaled.service",
            "Before=dharma-sadhana-standby-snapshot-receiver.path "
            "dharma-sadhana-standby-snapshot-receiver.timer",
            "PartOf=dharma-sadhana-standby.target",
            "WantedBy=dharma-sadhana-standby.target",
            "RequiredBy=dharma-sadhana-standby.target",
            "RemainAfterExit=yes",
            "PrivateNetwork=true",
            "RestrictAddressFamilies=AF_UNIX",
            "ReadWritePaths=/etc/dharma-sadhana/receipts/preactivation",
        )
        if (
            start is None
            or stop is None
            or any(fragment not in text for fragment in required_transport_fragments)
            or "tailscale serve reset" in lowered
        ):
            raise ReleaseContractError(
                "standby replication Serve unit lifecycle differs"
            )
    if name == "dharma-sadhana-api.service.in":
        required_observer_fragments = (
            "User=dharma-sadhana-observer",
            "Group=dharma-sadhana-observer",
            "Wants=dharma-sadhana-projection-sync.timer",
            "ReadOnlyPaths=/opt/dharma-sadhana/releases/",
            "/var/lib/dharma-sadhana/api-state",
            "InaccessiblePaths=/etc/dharma-sadhana ",
            "/var/lib/dharma-sadhana/state",
            "/var/lib/dharma-sadhana/snapshots",
            "/var/lib/dharma-sadhana/projection-source",
            "/run/dharma-sadhana/control",
            "--no-proxy-headers",
        )
        if (
            any(fragment not in text for fragment in required_observer_fragments)
            or "Requires=dharma-sadhana-projection-sync.service "
            "dharma-sadhana-control-directories.service "
            "dharma-sadhana-oracle-directories.service" not in text.splitlines()
            or "After=dharma-sadhana-projection-sync.service "
            "dharma-sadhana-control-directories.service "
            "dharma-sadhana-oracle-directories.service" not in text.splitlines()
            or "ReadWritePaths=" in text
            or "User=dharma-sadhana\n" in text
        ):
            raise ReleaseContractError("API observer isolation differs")
    if canonical_name == OBSERVER_HEALTH_UNIT:
        required_health_barrier = (
            "Requires=dharma-sadhana-api.service",
            "After=dharma-sadhana-api.service",
            "Before=dharma-sadhana-dispatch-enable.service "
            "dharma-sadhana-supervisor.service",
            "PartOf=dharma-sadhana.target",
            "User=root",
            "sadhana_release.py probe-observer-health --role writer --release-sha ",
            "RemainAfterExit=yes",
            "ReadWritePaths=/etc/dharma-sadhana/receipts/preactivation",
            "InaccessiblePaths=/etc/dharma-sadhana/credentials ",
            "/var/lib/dharma-sadhana/state",
            "IPAddressDeny=any",
            "IPAddressAllow=localhost",
            "NoNewPrivileges=true",
            "ProtectSystem=strict",
            "SystemCallFilter=~ptrace process_vm_readv process_vm_writev",
            "RuntimeMaxSec=60s",
            "TasksMax=32",
            "MemoryMax=256M",
        )
        if (
            any(fragment not in text for fragment in required_health_barrier)
            or "EnvironmentFile=" in text
            or "LoadCredential=" in text
            or "PrivateNetwork=true" in text
        ):
            raise ReleaseContractError("observer health dispatch barrier differs")
    if canonical_name == "dharma-sadhana-runtime-prepare.service":
        preparation_write_paths = [
            line for line in text.splitlines() if line.startswith("ReadWritePaths=")
        ]
        required_preparation_fragments = (
            "Before=dharma-sadhana.target dharma-sadhana-dispatch.target",
            "ConditionPathExists=!/etc/dharma-sadhana/receipts/preactivation/"
            "dispatch-enabled.v1.json",
            "ConditionPathExists=/var/lib/dharma-sadhana/state/release-admission/"
            "staged-release-admission.v1.json",
            "EnvironmentFile=/etc/dharma-sadhana/receipts/releases/",
            "/runtime-prep.env",
            "User=dharma-sadhana",
            "Group=dharma-sadhana",
            "sadhana_prepare_runtime.py --release-root "
            "${SADHANA_PREP_RELEASE_ROOT}",
            "--release-admission-receipt "
            "${SADHANA_PREP_RELEASE_ADMISSION_RECEIPT}",
            "--manifest-staging-root ${SADHANA_PREP_MANIFEST_STAGING_ROOT}",
            "--projection-path ${SADHANA_PREP_PROJECTION_PATH}",
            "--operator-id ${SADHANA_PREP_OPERATOR_ID}",
            "--max-dispatch-per-cycle "
            "${SADHANA_PREP_MAX_DISPATCH_PER_CYCLE}",
            "--cycle-interval-seconds "
            "${SADHANA_PREP_CYCLE_INTERVAL_SECONDS}",
            "--freshness-seconds ${SADHANA_PREP_FRESHNESS_SECONDS}",
            "--verifier-seat ${SADHANA_PREP_VERIFIER_SEAT}",
            "--deployment-authority-credential-clarification-sha256 "
            "${SADHANA_PREP_DEPLOYMENT_AUTHORITY_CREDENTIAL_CLARIFICATION_SHA256}",
            "RemainAfterExit=yes",
            "PrivateNetwork=true",
            "ReadOnlyPaths=/opt/dharma-sadhana/releases/",
            "/var/lib/dharma-sadhana/state/release-admission",
            "ReadWritePaths=/var/lib/dharma-sadhana/state "
            "/var/lib/dharma-sadhana/projection-source",
            "InaccessiblePaths=-/etc/dharma-sadhana/credentials "
            "-/etc/dharma-sadhana/verifier.env -/run/credentials "
            "-/run/dharma-sadhana/control -/run/dharma-sadhana/oracle",
            "RestrictAddressFamilies=AF_UNIX",
            "IPAddressDeny=any",
            "NoNewPrivileges=true",
            "CapabilityBoundingSet=\n",
        )
        if (
            any(fragment not in text for fragment in required_preparation_fragments)
            or preparation_write_paths
            != [
                "ReadWritePaths=/var/lib/dharma-sadhana/state "
                "/var/lib/dharma-sadhana/projection-source"
            ]
            or "ConditionPathExists=!/etc/dharma-sadhana/receipts/runtime/"
            "sadhana-10-20260823/runtime-binding-activation.v2.json" in text
            or "ConditionPathExists=!/etc/dharma-sadhana/writer-enabled" in text
            or text.count("EnvironmentFile=") != 1
            or "EnvironmentFile=/etc/dharma-sadhana/supervisor.env" in text
            or "WantedBy=" in text
            or "[Install]" in text
            or "PartOf=" in text
            or "LoadCredential=" in text
            or re.search(r"(?:HMAC|API_KEY|BEARER|provider)", text, re.IGNORECASE)
            is not None
        ):
            raise ReleaseContractError("runtime preparation unit authority differs")
    if canonical_name == "dharma-sadhana-supervisor.service" and "--fast-boot" in text:
        raise ReleaseContractError(
            "supervisor fast boot would discard hash-pinned observed context"
        )
    if (
        canonical_name == "dharma-sadhana-supervisor.service"
        and "guard-standby-capacity" in text
    ):
        raise ReleaseContractError(
            "supervisor restart rechecks expiring standby capacity"
        )
    if canonical_name == "dharma-sadhana-supervisor.service":
        supervisor_lines = text.splitlines()
        supervisor_activation_environment = (
            "EnvironmentFile=/etc/dharma-sadhana/receipts/preactivation/"
            "supervisor-activation.env"
        )
        supervisor_write_paths = [
            line for line in supervisor_lines if line.startswith("ReadWritePaths=")
        ]
        supervisor_environment_files = [
            line for line in supervisor_lines if line.startswith("EnvironmentFile=")
        ]
        supervisor_environments = [
            line for line in supervisor_lines if line.startswith("Environment=")
        ]
        supervisor_credentials = [
            line for line in supervisor_lines if line.startswith("LoadCredential=")
        ]
        requires_line = next(
            (line for line in supervisor_lines if line.startswith("Requires=")), ""
        )
        after_line = next(
            (line for line in supervisor_lines if line.startswith("After=")), ""
        )
        required_oracle_membrane = (
            "Requires=dharma-sadhana-control.service "
            "dharma-sadhana-oracle-sandbox-probe.service",
            "/var/lib/dharma-sadhana/oracle-inputs",
            "/run/dharma-sadhana/oracle/requests",
            "/run/dharma-sadhana/oracle/terminals",
            "InaccessiblePaths=/etc/dharma-sadhana/inputs/runtime/"
            "sadhana-10-20260823/held-out/g10-evaluator.py ",
            "/etc/dharma-sadhana/inputs/runtime/sadhana-10-20260823/"
            "held-out/g10-policy.json",
            "Requires=dharma-sadhana-control.service "
            "dharma-sadhana-oracle-sandbox-probe.service "
            "dharma-sadhana-observer-health.service",
            "After=network-online.target dharma-sadhana-control.service "
            "dharma-sadhana-oracle-sandbox-probe.service "
            "dharma-sadhana-observer-health.service",
            "EnvironmentFile=/etc/dharma-sadhana/supervisor-runtime.env",
            "EnvironmentFile=/etc/dharma-sadhana/receipts/preactivation/"
            "supervisor-activation.env",
            "Environment=DHARMA_READ_ONLY_BOOT=1",
            "LoadCredential=control_hmac_key:/etc/dharma-sadhana/credentials/"
            "control_hmac_key",
            "LoadCredential=dispatch_activation_receipt:/etc/dharma-sadhana/"
            "receipts/preactivation/dispatch-enabled.v1.json",
            "LoadCredential=dashboard_identity_receipt:/etc/dharma-sadhana/"
            "receipts/preactivation/dashboard-identity.v5.json",
            "LoadCredential=tailscale_operator_login:/etc/dharma-sadhana/"
            "credentials/tailscale_operator_login",
            "LoadCredential=observer_health_receipt:/etc/dharma-sadhana/receipts/"
            "preactivation/observer-health-18420.v3.json",
            "LoadCredential=runtime_binding_activation:/etc/dharma-sadhana/"
            "receipts/runtime/sadhana-10-20260823/"
            "runtime-binding-activation.v2.json",
            "--authority-manifest /etc/dharma-sadhana/inputs/runtime/"
            "sadhana-10-20260823/authority-manifest.json",
            "--observed-input-manifest /etc/dharma-sadhana/inputs/runtime/"
            "sadhana-10-20260823/observed-inputs.json",
            "--held-out-oracle-manifest /etc/dharma-sadhana/inputs/runtime/"
            "sadhana-10-20260823/held-out-oracle.json",
            "--held-out-oracle-digest ${SADHANA_HELD_OUT_ORACLE_DIGEST}",
            "--observer-health-receipt %d/observer_health_receipt",
            "--observer-health-receipt-sha256 "
            "${SADHANA_OBSERVER_HEALTH_RECEIPT_SHA256}",
            "--oracle-sandbox-evidence-sha256 "
            "${SADHANA_ORACLE_SANDBOX_EVIDENCE_SHA256}",
            "mission_control_campaign.py run --state-dir /var/lib/dharma-sadhana ",
            "--release-sha ",
            "--dispatch-activation-receipt %d/dispatch_activation_receipt",
            "--dashboard-identity-receipt %d/dashboard_identity_receipt",
            "--runtime-binding-receipt %d/runtime_binding_activation",
            "--operator-login-file %d/tailscale_operator_login",
            "--control-hmac-key-file %d/control_hmac_key",
            "--activation-evidence-path /run/dharma-sadhana/control/activation/"
            "campaign-activation.v1.json",
        )
        if any(fragment not in text for fragment in required_oracle_membrane):
            raise ReleaseContractError("supervisor oracle membrane differs")
        if (
            DISPATCH_ENABLE_UNIT not in requires_line.split("=", 1)[-1].split()
            or DISPATCH_ENABLE_UNIT not in after_line.split("=", 1)[-1].split()
            or "ConditionPathExists=/etc/dharma-sadhana/receipts/preactivation/"
            "dispatch-enabled.v1.json" not in text
            or "WantedBy=dharma-sadhana-dispatch.target" not in text
            or "--operator-control-hmac-credential" in text
            or "--operator-control-hmac-sha256" in text
            or re.search(r"^Environment=.*(?:HMAC|control_hmac_key)", text, re.MULTILINE)
            is not None
            or text.count("--authority-manifest ") != 1
            or text.count("--observed-input-manifest ") != 1
            or text.count("--held-out-oracle-manifest ") != 1
            or text.count("--release-sha ") != 1
            or re.search(
                r"--release-sha (?:@RELEASE_SHA@|[0-9a-f]{40})(?: |$)",
                text,
            )
            is None
            or "sadhana_release.py activate-campaign-session " in text
            or supervisor_lines.count("Environment=DHARMA_READ_ONLY_BOOT=1") != 1
            or any(
                line.startswith("Environment=DHARMA_READ_ONLY_BOOT=")
                and line != "Environment=DHARMA_READ_ONLY_BOOT=1"
                for line in supervisor_lines
            )
            or supervisor_lines.count(supervisor_activation_environment) != 1
            or "EnvironmentFile=/etc/dharma-sadhana/supervisor-activation.env"
            in supervisor_lines
            or supervisor_environment_files
            != [
                "EnvironmentFile=/etc/dharma-sadhana/supervisor.env",
                "EnvironmentFile=/etc/dharma-sadhana/supervisor-runtime.env",
                "EnvironmentFile=/etc/dharma-sadhana/receipts/preactivation/"
                "supervisor-activation.env",
                "EnvironmentFile=/etc/dharma-sadhana/verifier.env",
            ]
            or supervisor_environments
            != [
                "Environment=SADHANA_CONTROL_SEMANTICS_SHA256="
                + CONTROL_SEMANTICS_SHA256,
                "Environment=SADHANA_CONTROL_HTTP_BINDING_SHA256="
                + CONTROL_HTTP_BINDING_SHA256,
                "Environment=SADHANA_CONTROL_AUTHORITY_BINDING_SHA256="
                + CONTROL_AUTHORITY_BINDING_SHA256,
                "Environment=DHARMA_READ_ONLY_BOOT=1",
            ]
            or supervisor_credentials
            != [
                "LoadCredential=control_hmac_key:/etc/dharma-sadhana/credentials/"
                "control_hmac_key",
                "LoadCredential=dispatch_activation_receipt:/etc/dharma-sadhana/"
                "receipts/preactivation/dispatch-enabled.v1.json",
                "LoadCredential=dashboard_identity_receipt:/etc/dharma-sadhana/"
                "receipts/preactivation/dashboard-identity.v5.json",
                "LoadCredential=tailscale_operator_login:/etc/dharma-sadhana/"
                "credentials/tailscale_operator_login",
                "LoadCredential=observer_health_receipt:/etc/dharma-sadhana/receipts/"
                "preactivation/observer-health-18420.v3.json",
                "LoadCredential=runtime_binding_activation:/etc/dharma-sadhana/"
                "receipts/runtime/sadhana-10-20260823/"
                "runtime-binding-activation.v2.json",
            ]
            or any(
                line.startswith(
                    (
                        "PassEnvironment=",
                        "UnsetEnvironment=",
                        "SetCredential=",
                        "SetCredentialEncrypted=",
                        "LoadCredentialEncrypted=",
                        "ImportCredential=",
                    )
                )
                for line in supervisor_lines
            )
            or supervisor_write_paths
            != [
                "ReadWritePaths=/var/lib/dharma-sadhana/state "
                "/var/lib/dharma-sadhana/workspace "
                "/var/lib/dharma-sadhana/leases "
                "/var/lib/dharma-sadhana/projection-source "
                "/var/lib/dharma-sadhana/oracle-inputs "
                "/run/dharma-sadhana/oracle/requests "
                "/run/dharma-sadhana/control/normal "
                "/run/dharma-sadhana/control/inflight "
                "/run/dharma-sadhana/control/applied "
                "/run/dharma-sadhana/control/rejected "
                "/run/dharma-sadhana/control/activation"
            ]
        ):
            raise ReleaseContractError("supervisor dispatch authority differs")
    if canonical_name == PREDISPATCH_TARGET:
        if (
            SUPERVISOR_UNIT in text
            or DISPATCH_ENABLE_UNIT in text
            or "dharma-sadhana-api.service" not in text
            or "dharma-sadhana-control.service" not in text
            or "dharma-sadhana-dashboard.service" not in text
            or "dharma-sadhana-private-serve.service" not in text
            or OBSERVER_HEALTH_UNIT not in text
        ):
            raise ReleaseContractError("predispatch target can start dispatch")
    if canonical_name == DISPATCH_ENABLE_UNIT:
        dispatch_write_paths = [
            line for line in text.splitlines() if line.startswith("ReadWritePaths=")
        ]
        required_dispatch_gate = (
            "Requires=dharma-sadhana.target ",
            "After=dharma-sadhana.target ",
            "Before=dharma-sadhana-supervisor.service",
            "sadhana_release.py enable-dispatch --role writer --release-sha ",
            "/var/lib/dharma-sadhana/api-state "
            "/var/lib/dharma-sadhana/state "
            "/var/lib/dharma-sadhana/projection-source",
            "ReadWritePaths=/etc/dharma-sadhana/receipts/preactivation",
            "/run/credentials/dharma-sadhana-dashboard.service/operator_bearer",
            "/run/credentials/dharma-sadhana-control.service/operator_bearer",
            "/run/dharma-sadhana/control/normal",
            "/run/dharma-sadhana/control/emergency",
            "InaccessiblePaths=/etc/dharma-sadhana/credentials/control_hmac_key ",
            "/run/credentials/dharma-sadhana-control.service/control_hmac_key",
            "/run/credentials/dharma-sadhana-control.service/"
            "tailscale_operator_login",
            "/run/dharma-sadhana/control/inflight",
            "/run/dharma-sadhana/control/applied",
            "/run/dharma-sadhana/control/rejected",
            "CapabilityBoundingSet=CAP_SYS_PTRACE",
            "NoNewPrivileges=true",
            "ProtectSystem=strict",
        )
        if (
            any(fragment not in text for fragment in required_dispatch_gate)
            or dispatch_write_paths
            != ["ReadWritePaths=/etc/dharma-sadhana/receipts/preactivation"]
            or "ReadWritePaths=/run/dharma-sadhana/control" in text
            or "/var/lib/dharma-sadhana/state " in next(
                (
                    line
                    for line in text.splitlines()
                    if line.startswith("InaccessiblePaths=")
                ),
                "",
            )
            or "/etc/dharma-sadhana/api.env " in next(
                (
                    line
                    for line in text.splitlines()
                    if line.startswith("InaccessiblePaths=")
                ),
                "",
            )
            or "LoadCredential=" in text
            or "CAP_DAC_READ_SEARCH" in text
            or "CAP_DAC_OVERRIDE" in text
        ):
            raise ReleaseContractError("dispatch enable unit binding differs")
    if canonical_name == "dharma-sadhana-control-directories.service":
        control_directory_write_paths = [
            line for line in text.splitlines() if line.startswith("ReadWritePaths=")
        ]
        if (
            control_directory_write_paths
            != [
                "ReadWritePaths=/run/dharma-sadhana "
                "/var/lib/dharma-sadhana/emergency-inflight "
                "/var/lib/dharma-sadhana/emergency-apply.lock"
            ]
            or text.count("RuntimeDirectory=dharma-sadhana") != 1
            or text.count("RuntimeDirectoryMode=0711") != 1
            or text.count("RuntimeDirectoryPreserve=yes") != 1
            or text.count(
                "CapabilityBoundingSet=CAP_CHOWN CAP_DAC_OVERRIDE CAP_FOWNER"
            )
            != 1
        ):
            raise ReleaseContractError("control directory write namespace differs")
    if canonical_name == DISPATCH_TARGET and (
        "Requires=dharma-sadhana.target " not in text
        or DISPATCH_ENABLE_UNIT not in text
        or SUPERVISOR_UNIT not in text
        or "WantedBy=" in text
    ):
        raise ReleaseContractError("dispatch target is not explicit-only")
    emergency_marker_condition = (
        "ConditionPathExists=!/etc/dharma-sadhana/receipts/control/emergency/"
        "emergency-stopped"
    )
    if (
        canonical_name
        in _CLOCK_GUARDED_UNITS
        | {
            "dharma-sadhana-control-emergency.path",
            "dharma-sadhana-snapshot.timer",
            "dharma-sadhana.target",
        }
        and emergency_marker_condition not in text
    ):
        raise ReleaseContractError(
            f"unit {name} lacks the durable emergency-stop condition"
        )
    claim_condition = (
        "ConditionDirectoryNotEmpty=!/var/lib/dharma-sadhana/emergency-inflight"
    )
    if (
        canonical_name in _TARGET_CESSATION_UNITS | {"dharma-sadhana.target"}
        and claim_condition not in text
    ):
        raise ReleaseContractError(
            f"unit {name} can restart while an emergency claim is unfinished"
        )
    if (
        canonical_name in _CLOCK_GUARDED_UNITS
        and "sadhana_release.py guard-start --role writer" not in text
    ):
        raise ReleaseContractError(f"unit {name} lacks the exact timebox guard")
    if (
        canonical_name in _TARGET_CESSATION_UNITS
        and "PartOf=dharma-sadhana.target" not in text
    ):
        raise ReleaseContractError(
            f"unit {name} is not stopped with the campaign target"
        )
    if name in {
        "dharma-sadhana-campaign-stop.timer",
        "dharma-sadhana-standby-stop.timer",
    } and (
        "OnCalendar=2026-09-01 17:15:12 UTC" not in text
        or "AccuracySec=1s" not in text
        or "Persistent=true" not in text
    ):
        raise ReleaseContractError("campaign stop timer differs from exact end")
    if canonical_name == STANDBY_TARGET:
        required_standby_target = (
            "ConditionPathExists=!/etc/dharma-sadhana/receipts/standby/"
            "deadline-stopped.v1.json",
            "Requires=dharma-sadhana-standby-replication-serve.service "
            "dharma-sadhana-standby-snapshot-receiver.path "
            "dharma-sadhana-standby-snapshot-receiver.timer",
            "After=network-online.target tailscaled.service "
            "dharma-sadhana-standby-replication-serve.service",
            "WantedBy=multi-user.target",
        )
        if any(fragment not in text for fragment in required_standby_target):
            raise ReleaseContractError("standby target deadline binding differs")
    if canonical_name in {
        "dharma-sadhana-standby-snapshot-receiver.path",
        "dharma-sadhana-standby-snapshot-receiver.timer",
        "dharma-sadhana-standby-snapshot-receiver.service",
    }:
        if (
            "PartOf=dharma-sadhana-standby.target" not in text
            or "ConditionPathExists=!/etc/dharma-sadhana/receipts/standby/"
            "deadline-stopped.v1.json" not in text
            or "WantedBy=dharma-sadhana-standby.target" not in text
        ):
            raise ReleaseContractError("standby receiver lifecycle differs")
    if canonical_name == "dharma-sadhana-standby-stop.service":
        disable = (
            "ExecStart=+/usr/bin/systemctl disable --now "
            "dharma-sadhana-standby.target"
        )
        receipt = "sadhana_release.py persist-standby-stop --role standby"
        if (
            "sadhana_release.py guard-stop --role standby" not in text
            or disable not in text
            or receipt not in text
            or text.index(disable) > text.index(receipt)
            or "PartOf=dharma-sadhana-standby.target" in text
            or "ConditionPathExists=" in text
        ):
            raise ReleaseContractError("standby stop service is not independent")
    if canonical_name == "dharma-sadhana-standby-stop.timer" and (
        "PartOf=dharma-sadhana-standby.target" in text
        or "WantedBy=multi-user.target" not in text
    ):
        raise ReleaseContractError("standby stop timer cannot stop with its target")
    if canonical_name == "dharma-sadhana-campaign-stop.service":
        target_stop = "ExecStart=+/usr/bin/systemctl stop dharma-sadhana.target"
        marker = "sadhana_release.py persist-stop --role writer"
        stop_write_paths = [
            line for line in text.splitlines() if line.startswith("ReadWritePaths=")
        ]
        if (
            "sadhana_release.py guard-stop --role writer" not in text
            or target_stop not in text
            or marker not in text
            or text.index(target_stop) > text.index(marker)
            or "PartOf=dharma-sadhana.target" in text
            or "ConditionPathExists=" in text
            or stop_write_paths
            != [
                "ReadWritePaths=/var/lib/dharma-sadhana/state "
                "/var/lib/dharma-sadhana/workspace "
                "/var/lib/dharma-sadhana/projection-source"
            ]
        ):
            raise ReleaseContractError(
                "campaign stop service lacks independent cessation"
            )
    if canonical_name == "dharma-sadhana-campaign-stop.timer" and (
        "PartOf=dharma-sadhana.target" in text
    ):
        raise ReleaseContractError("campaign stop timer cannot stop with its target")
    if canonical_name == "dharma-sadhana-control-emergency.service":
        required_fragments = (
            "After=dharma-sadhana-control-directories.service",
            "LoadCredential=control_hmac_key:",
            "LoadCredential=tailscale_operator_login:",
            "sadhana_release.py apply-emergency-control --role writer",
            "/run/dharma-sadhana/emergency-quarantine",
            "/var/lib/dharma-sadhana/emergency-inflight",
            "/var/lib/dharma-sadhana/emergency-apply.lock",
            "/etc/dharma-sadhana/receipts/control/emergency",
        )
        if (
            any(fragment not in text for fragment in required_fragments)
            or "Requires=dharma-sadhana-control-directories.service" in text
            or "PartOf=dharma-sadhana.target" in text
        ):
            raise ReleaseContractError(
                "emergency service is not independent of target-owned units"
            )
    if canonical_name == "dharma-sadhana-control-emergency-recovery.service":
        required_fragments = (
            "LoadCredential=control_hmac_key:",
            "LoadCredential=tailscale_operator_login:",
            "sadhana_release.py resume-emergency-control --role writer",
            "/var/lib/dharma-sadhana/emergency-inflight",
            "/var/lib/dharma-sadhana/emergency-apply.lock",
            "/etc/dharma-sadhana/receipts/control/emergency",
        )
        if (
            any(fragment not in text for fragment in required_fragments)
            or "PartOf=dharma-sadhana.target" in text
            or "Requires=dharma-sadhana-control-directories.service" in text
            or "ConditionPathExists=!" in text
        ):
            raise ReleaseContractError(
                "emergency recovery service is not reboot-independent"
            )
    if canonical_name == "dharma-sadhana-control-emergency-recovery.path" and (
        "DirectoryNotEmpty=/var/lib/dharma-sadhana/emergency-inflight" not in text
        or "Unit=dharma-sadhana-control-emergency-recovery.service" not in text
        or "WantedBy=multi-user.target" not in text
        or "PartOf=dharma-sadhana.target" in text
        or "ConditionPathExists=!" in text
    ):
        raise ReleaseContractError("emergency recovery path is not reboot-independent")
    if canonical_name == "dharma-sadhana-control.service":
        control_lines = text.splitlines()
        control_service_assignments = _unit_section_assignments(text, "Service")
        control_environments = [
            line for line in control_lines if line.startswith("Environment=")
        ]
        control_environment_files = [
            line for line in control_lines if line.startswith("EnvironmentFile=")
        ]
        control_credentials = [
            line for line in control_lines if line.startswith("LoadCredential=")
        ]
        release_environments = [
            line
            for line in control_lines
            if line.startswith("Environment=SADHANA_RELEASE_SHA=")
        ]
        account_binding_environment = (
            "Environment=SADHANA_ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256="
            f"{ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256}"
        )
        account_endpoint_environment = (
            "Environment=SADHANA_ACCOUNT_UI_CONFIRMATION_ENDPOINT="
            f"{ACCOUNT_UI_CONFIRMATION_REQUEST_PATH}"
        )
        control_release_value = (
            release_environments[0].removeprefix(
                "Environment=SADHANA_RELEASE_SHA="
            )
            if len(release_environments) == 1
            else "<invalid-release-sha>"
        )
        expected_control_environments = [
            "Environment=SADHANA_CONTROL_TAILSCALE_LOGIN_FILE="
            "%d/tailscale_operator_login",
            "Environment=SADHANA_CONTROL_NORMAL_INBOX="
            "/run/dharma-sadhana/control/normal",
            "Environment=SADHANA_CONTROL_EMERGENCY_INBOX="
            "/run/dharma-sadhana/control/emergency",
            f"Environment=SADHANA_CONTROL_SEMANTICS_SHA256={CONTROL_SEMANTICS_SHA256}",
            f"Environment=SADHANA_CONTROL_HTTP_BINDING_SHA256={CONTROL_HTTP_BINDING_SHA256}",
            "Environment=SADHANA_CONTROL_AUTHORITY_BINDING_SHA256="
            f"{CONTROL_AUTHORITY_BINDING_SHA256}",
            account_binding_environment,
            account_endpoint_environment,
            f"Environment=SADHANA_RELEASE_SHA={control_release_value}",
        ]
        expected_control_service_assignments = [
            "Type=simple",
            "User=dharma-sadhana-control",
            "Group=dharma-sadhana-control",
            "EnvironmentFile=/etc/dharma-sadhana/control.env",
            "LoadCredential=operator_bearer:/etc/dharma-sadhana/credentials/"
            "operator_bearer",
            "LoadCredential=control_hmac_key:/etc/dharma-sadhana/credentials/"
            "control_hmac_key",
            "LoadCredential=tailscale_operator_login:/etc/dharma-sadhana/"
            "credentials/tailscale_operator_login",
            *expected_control_environments,
            f"WorkingDirectory=/opt/dharma-sadhana/releases/{control_release_value}",
            "ExecStartPre=/opt/dharma-sadhana/releases/"
            f"{control_release_value}/.venv/bin/python "
            f"/opt/dharma-sadhana/releases/{control_release_value}/scripts/runtime/"
            "sadhana_release.py guard-start --role writer",
            "ExecStart=/opt/dharma-sadhana/releases/"
            f"{control_release_value}/.venv/bin/python -m "
            "scripts.runtime.sadhana_control_api",
            "Restart=on-failure",
            "RestartSec=3s",
            "NoNewPrivileges=true",
            "CapabilityBoundingSet=",
            "KeyringMode=private",
            "LockPersonality=true",
            "PrivateDevices=true",
            "PrivateIPC=true",
            "PrivateTmp=true",
            "ProtectClock=true",
            "ProtectControlGroups=true",
            "ProtectHome=true",
            "ProtectHostname=true",
            "ProtectKernelLogs=true",
            "ProtectKernelModules=true",
            "ProtectKernelTunables=true",
            "ProtectProc=invisible",
            "ProtectSystem=strict",
            "ProcSubset=pid",
            "RemoveIPC=true",
            "ReadOnlyPaths=/opt/dharma-sadhana/releases/"
            f"{control_release_value} /etc/dharma-sadhana",
            "ReadWritePaths=/run/dharma-sadhana/control/normal "
            "/run/dharma-sadhana/control/emergency "
            "/run/dharma-sadhana/control/account-ui-confirmation",
            "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6",
            "RestrictNamespaces=true",
            "RestrictRealtime=true",
            "RestrictSUIDSGID=true",
            "SystemCallArchitectures=native",
            "IPAddressDeny=any",
            "IPAddressAllow=localhost",
            "UMask=0077",
        ]
        required_fragments = (
            "User=dharma-sadhana-control",
            "LoadCredential=operator_bearer:",
            "LoadCredential=control_hmac_key:",
            "LoadCredential=tailscale_operator_login:",
            "python -m scripts.runtime.sadhana_control_api",
            f"SADHANA_CONTROL_SEMANTICS_SHA256={CONTROL_SEMANTICS_SHA256}",
            f"SADHANA_CONTROL_HTTP_BINDING_SHA256={CONTROL_HTTP_BINDING_SHA256}",
            "SADHANA_CONTROL_AUTHORITY_BINDING_SHA256="
            f"{CONTROL_AUTHORITY_BINDING_SHA256}",
        )
        expected_write_paths = (
            "ReadWritePaths=/run/dharma-sadhana/control/normal "
            "/run/dharma-sadhana/control/emergency "
            "/run/dharma-sadhana/control/account-ui-confirmation"
        )
        if (
            any(fragment not in text for fragment in required_fragments)
            or control_environments != expected_control_environments
            or control_service_assignments
            != expected_control_service_assignments
            or control_lines.count(expected_write_paths) != 1
            or [
                line
                for line in control_lines
                if line.startswith("ReadWritePaths=")
            ]
            != [expected_write_paths]
            or [
                line
                for line in control_lines
                if line.startswith(
                    "Environment=SADHANA_ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256="
                )
            ]
            != [account_binding_environment]
            or [
                line
                for line in control_lines
                if line.startswith(
                    "Environment=SADHANA_ACCOUNT_UI_CONFIRMATION_ENDPOINT="
                )
            ]
            != [account_endpoint_environment]
            or control_environment_files
            != ["EnvironmentFile=/etc/dharma-sadhana/control.env"]
            or control_credentials
            != [
                "LoadCredential=operator_bearer:/etc/dharma-sadhana/credentials/"
                "operator_bearer",
                "LoadCredential=control_hmac_key:/etc/dharma-sadhana/credentials/"
                "control_hmac_key",
                "LoadCredential=tailscale_operator_login:/etc/dharma-sadhana/"
                "credentials/tailscale_operator_login",
            ]
            or any(
                line.startswith(
                    (
                        "LoadCredentialEncrypted=",
                        "SetCredential=",
                        "SetCredentialEncrypted=",
                        "ImportCredential=",
                        "PassEnvironment=",
                    )
                )
                for line in control_lines
            )
            or (
                not rendered
                and release_environments
                != ["Environment=SADHANA_RELEASE_SHA=@RELEASE_SHA@"]
            )
            or (
                rendered
                and (
                    len(release_environments) != 1
                    or re.fullmatch(
                        r"Environment=SADHANA_RELEASE_SHA=[0-9a-f]{40}",
                        release_environments[0],
                    )
                    is None
                )
            )
        ):
            raise ReleaseContractError("control API unit binding differs")
    if canonical_name == "dharma-sadhana-oracle-directories.service":
        oracle_write_paths = [
            line for line in text.splitlines() if line.startswith("ReadWritePaths=")
        ]
        exact_oracle_write_paths = (
            "ReadWritePaths=/run/dharma-sadhana "
            "/var/lib/dharma-sadhana/oracle-inputs "
            "/var/lib/dharma-sadhana/oracle-claims "
            "/var/lib/dharma-sadhana/oracle-runs "
            "/var/lib/dharma-sadhana/oracle-quarantine "
            "/etc/dharma-sadhana/receipts/oracle"
        )
        required_fragments = (
            "User=root",
            "sadhana_oracle_sandbox.py prepare",
            "Requires=dharma-sadhana-control-directories.service",
            "After=dharma-sadhana-control-directories.service",
            "Before=dharma-sadhana-oracle-sandbox-probe.service ",
            "dharma-sadhana-oracle-sandbox.service",
        )
        if (
            any(fragment not in text for fragment in required_fragments)
            or oracle_write_paths != [exact_oracle_write_paths]
        ):
            raise ReleaseContractError("oracle directory unit binding differs")
    if canonical_name == "dharma-sadhana-oracle-sandbox-probe.service":
        required_fragments = (
            "sadhana_oracle_sandbox.py probe --release-sha ",
            "Before=dharma-sadhana-supervisor.service ",
            "PrivateNetwork=true",
            "ProtectSystem=strict",
            "NoNewPrivileges=true",
            "CapabilityBoundingSet=\n",
            "InaccessiblePaths=/var/lib/dharma-sadhana/state ",
            "/etc/dharma-sadhana/credentials",
            "ReadWritePaths=/var/lib/dharma-sadhana/oracle-runs ",
            "/etc/dharma-sadhana/receipts/oracle",
            "TemporaryFileSystem=/tmp:ro /var/tmp:ro /dev/shm:ro",
            "RestrictAddressFamilies=AF_UNIX",
            "SystemCallFilter=~ptrace process_vm_readv process_vm_writev",
            " socket socketpair connect bind listen accept accept4 ",
        )
        if any(fragment not in text for fragment in required_fragments):
            raise ReleaseContractError("oracle sandbox probe binding differs")
    if canonical_name == "dharma-sadhana-oracle-sandbox.service":
        required_fragments = (
            "sadhana_oracle_sandbox.py reconcile --release-sha ",
            "Requires=dharma-sadhana-oracle-directories.service "
            "dharma-sadhana-oracle-sandbox-probe.service",
            "PrivateNetwork=true",
            "ProtectSystem=strict",
            "NoNewPrivileges=true",
            "CapabilityBoundingSet=CAP_CHOWN CAP_DAC_OVERRIDE CAP_FOWNER "
            "CAP_SETGID CAP_SETUID",
            "InaccessiblePaths=/var/lib/dharma-sadhana/state ",
            "/run/dharma-sadhana/control",
            "/etc/dharma-sadhana/credentials",
            "/etc/dharma-sadhana/verifier.env",
            "ReadOnlyPaths=/opt/dharma-sadhana/releases/",
            "/etc/dharma-sadhana/inputs/runtime/sadhana-10-20260823",
            "/run/dharma-sadhana/oracle/requests",
            "/var/lib/dharma-sadhana/oracle-inputs",
            "ReadWritePaths=/run/dharma-sadhana/oracle/terminals ",
            "/var/lib/dharma-sadhana/oracle-claims",
            "/var/lib/dharma-sadhana/oracle-runs",
            "/etc/dharma-sadhana/receipts/oracle",
            "TemporaryFileSystem=/tmp:ro /var/tmp:ro /dev/shm:ro",
            "RestrictAddressFamilies=AF_UNIX",
            "SystemCallFilter=~ptrace process_vm_readv process_vm_writev",
            " socket socketpair connect bind listen accept accept4 ",
            "TasksMax=32",
            "MemoryMax=768M",
            "RuntimeMaxSec=90s",
        )
        if any(fragment not in text for fragment in required_fragments):
            raise ReleaseContractError("oracle sandbox worker binding differs")
        if "EnvironmentFile=" in text or "LoadCredential=" in text:
            raise ReleaseContractError("oracle sandbox worker inherits a secret source")
    if canonical_name == "dharma-sadhana-oracle-sandbox.path" and (
        "PathChanged=/run/dharma-sadhana/oracle/requests" not in text
        or "Unit=dharma-sadhana-oracle-sandbox.service" not in text
        or "DirectoryNotEmpty=/run/dharma-sadhana/oracle/requests" in text
    ):
        raise ReleaseContractError("oracle sandbox path wakeup differs")
    if canonical_name == "dharma-sadhana-oracle-sandbox.timer" and (
        "OnUnitInactiveSec=15s" not in text
        or "Unit=dharma-sadhana-oracle-sandbox.service" not in text
        or "PartOf=dharma-sadhana.target" not in text
    ):
        raise ReleaseContractError("oracle sandbox retry timer differs")
    if canonical_name == "dharma-sadhana-projection-sync.service":
        required_fragments = (
            "User=root",
            "sadhana_release.py sync-observer-projection --role writer",
            "ReadOnlyPaths=/opt/dharma-sadhana/releases/",
            "/var/lib/dharma-sadhana/projection-source",
            "/var/lib/dharma-sadhana/snapshot-staging",
            "ReadWritePaths=/var/lib/dharma-sadhana/api-state",
            "CapabilityBoundingSet=CAP_CHOWN CAP_DAC_OVERRIDE CAP_FOWNER",
        )
        if any(fragment not in text for fragment in required_fragments):
            raise ReleaseContractError("observer projection sync binding differs")
    if canonical_name == "dharma-sadhana-dashboard.service":
        dashboard_lines = text.splitlines()
        dashboard_service_assignments = _unit_section_assignments(text, "Service")
        dashboard_environments = [
            line for line in dashboard_lines if line.startswith("Environment=")
        ]
        dashboard_environment_files = [
            line for line in dashboard_lines if line.startswith("EnvironmentFile=")
        ]
        dashboard_credentials = [
            line for line in dashboard_lines if line.startswith("LoadCredential=")
        ]
        dashboard_release_environments = [
            line
            for line in dashboard_lines
            if line.startswith("Environment=SADHANA_RELEASE_SHA=")
        ]
        dashboard_write_paths = [
            line for line in dashboard_lines if line.startswith("ReadWritePaths=")
        ]
        dashboard_release_value = (
            dashboard_release_environments[0].removeprefix(
                "Environment=SADHANA_RELEASE_SHA="
            )
            if len(dashboard_release_environments) == 1
            else "<invalid-release-sha>"
        )
        expected_dashboard_environments = [
            "Environment=SADHANA_CONTROL_BEARER_FILE=%d/operator_bearer",
            f"Environment=SADHANA_CONTROL_INTERNAL_URL={CONTROL_REQUEST_URL}",
            "Environment=SADHANA_ACCOUNT_UI_CONFIRMATION_INTERNAL_URL="
            f"{ACCOUNT_UI_CONFIRMATION_REQUEST_URL}",
            f"Environment=SADHANA_RELEASE_SHA={dashboard_release_value}",
            "Environment=SADHANA_ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256="
            f"{ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256}",
            f"Environment=SADHANA_CONTROL_HTTP_BINDING_SHA256={CONTROL_HTTP_BINDING_SHA256}",
            "Environment=SADHANA_DASHBOARD_SOCKET="
            "/run/dharma-sadhana/dashboard/constellation.sock",
        ]
        expected_dashboard_service_assignments = [
            "Type=simple",
            "User=dharma-sadhana-dashboard",
            "Group=dharma-sadhana-dashboard",
            "RuntimeDirectory=dharma-sadhana/dashboard",
            "RuntimeDirectoryMode=0700",
            "RuntimeDirectoryPreserve=yes",
            "EnvironmentFile=/etc/dharma-sadhana/dashboard.env",
            "LoadCredential=operator_bearer:/etc/dharma-sadhana/credentials/"
            "operator_bearer",
            *expected_dashboard_environments,
            "UnsetEnvironment=NEXT_PUBLIC_API_URL",
            f"WorkingDirectory=/opt/dharma-sadhana/releases/{dashboard_release_value}/dashboard",
            "ExecStartPre=/opt/dharma-sadhana/releases/"
            f"{dashboard_release_value}/.venv/bin/python "
            f"/opt/dharma-sadhana/releases/{dashboard_release_value}/scripts/runtime/"
            "sadhana_release.py guard-start --role writer",
            "ExecStartPre=+/opt/dharma-sadhana/releases/"
            f"{dashboard_release_value}/.venv/bin/python "
            f"/opt/dharma-sadhana/releases/{dashboard_release_value}/scripts/runtime/"
            "sadhana_release.py prepare-dashboard-runtime --role writer",
            "ExecStart=/usr/bin/node /opt/dharma-sadhana/releases/"
            f"{dashboard_release_value}/deploy/sadhana/sadhana-dashboard-server.mjs",
            "Restart=on-failure",
            "RestartSec=3s",
            "NoNewPrivileges=true",
            "CapabilityBoundingSet=",
            "KeyringMode=private",
            "LockPersonality=true",
            "PrivateDevices=true",
            "PrivateIPC=true",
            "PrivateTmp=true",
            "ProtectHome=true",
            "ProtectClock=true",
            "ProtectControlGroups=true",
            "ProtectHostname=true",
            "ProtectKernelLogs=true",
            "ProtectKernelModules=true",
            "ProtectKernelTunables=true",
            "ProtectProc=invisible",
            "ProtectSystem=strict",
            "ProcSubset=pid",
            "RemoveIPC=true",
            "ReadOnlyPaths=/opt/dharma-sadhana/releases/"
            f"{dashboard_release_value} /etc/dharma-sadhana",
            "ReadWritePaths=/run/dharma-sadhana/dashboard",
            "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6",
            "RestrictNamespaces=true",
            "RestrictRealtime=true",
            "RestrictSUIDSGID=true",
            "SystemCallArchitectures=native",
            "IPAddressDeny=any",
            "IPAddressAllow=localhost",
            "UMask=0077",
        ]
        if (
            "User=dharma-sadhana-dashboard" not in text
            or "Group=dharma-sadhana-dashboard" not in text
            or "LoadCredential=operator_bearer:" not in text
            or "SADHANA_CONTROL_BEARER_FILE=%d/operator_bearer" not in text
            or dashboard_environments != expected_dashboard_environments
            or dashboard_service_assignments
            != expected_dashboard_service_assignments
            or dashboard_environment_files
            != ["EnvironmentFile=/etc/dharma-sadhana/dashboard.env"]
            or dashboard_credentials
            != [
                "LoadCredential=operator_bearer:/etc/dharma-sadhana/credentials/"
                "operator_bearer"
            ]
            or any(
                line.startswith(
                    (
                        "LoadCredentialEncrypted=",
                        "SetCredential=",
                        "SetCredentialEncrypted=",
                        "ImportCredential=",
                        "PassEnvironment=",
                    )
                )
                for line in dashboard_lines
            )
            or f"Environment=SADHANA_CONTROL_INTERNAL_URL={CONTROL_REQUEST_URL}"
            not in text.splitlines()
            or [
                line
                for line in dashboard_lines
                if line.startswith(
                    "Environment=SADHANA_ACCOUNT_UI_CONFIRMATION_INTERNAL_URL="
                )
            ]
            != [
                "Environment=SADHANA_ACCOUNT_UI_CONFIRMATION_INTERNAL_URL="
                f"{ACCOUNT_UI_CONFIRMATION_REQUEST_URL}"
            ]
            or [
                line
                for line in dashboard_lines
                if line.startswith(
                    "Environment=SADHANA_ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256="
                )
            ]
            != [
                "Environment=SADHANA_ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256="
                f"{ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256}"
            ]
            or (
                not rendered
                and dashboard_release_environments
                != ["Environment=SADHANA_RELEASE_SHA=@RELEASE_SHA@"]
            )
            or (
                rendered
                and (
                    len(dashboard_release_environments) != 1
                    or re.fullmatch(
                        r"Environment=SADHANA_RELEASE_SHA=[0-9a-f]{40}",
                        dashboard_release_environments[0],
                    )
                    is None
                )
            )
            or "SADHANA_DASHBOARD_SOCKET=/run/dharma-sadhana/dashboard/constellation.sock"
            not in text
            or "sadhana_release.py prepare-dashboard-runtime --role writer" not in text
            or "deploy/sadhana/sadhana-dashboard-server.mjs" not in text
            or text.count("RuntimeDirectory=dharma-sadhana/dashboard") != 1
            or text.count("RuntimeDirectoryMode=0700") != 1
            or text.count("RuntimeDirectoryPreserve=yes") != 1
            or dashboard_write_paths
            != ["ReadWritePaths=/run/dharma-sadhana/dashboard"]
            or "ReadWritePaths=-/run/dharma-sadhana/dashboard" in text
            or re.search(r"^Environment=NEXT_PUBLIC_", text, flags=re.MULTILINE)
            or "UnsetEnvironment=NEXT_PUBLIC_API_URL" not in text
            or "SupplementaryGroups=" in text
            or "next start" in text
        ):
            raise ReleaseContractError("dashboard control bridge binding differs")
    if canonical_name == "dharma-sadhana-snapshot.service":
        required_fragments = (
            "User=dharma-sadhana",
            "sadhana_snapshot.py stage --mission-id sadhana-10-20260823",
            "--staging-root /var/lib/dharma-sadhana/snapshot-staging",
            "ReadOnlyPaths=/opt/dharma-sadhana/releases/",
            "/var/lib/dharma-sadhana/snapshots",
            "ReadWritePaths=/var/lib/dharma-sadhana/snapshot-staging",
            "RestrictAddressFamilies=AF_UNIX",
            "IPAddressDeny=any",
        )
        if (
            any(fragment not in text for fragment in required_fragments)
            or "SADHANA_REPLICATION_SSH_KEY" in text
            or "snapshot-incoming" in text
        ):
            raise ReleaseContractError("snapshot staging unit authority differs")
    if canonical_name == "dharma-sadhana-snapshot-finalize.service":
        required_fragments = (
            "User=root",
            "sadhana_snapshot.py finalize-local",
            "--standby dharma-sadhana@100.79.111.89 --standby-port 2222",
            "--standby-root /var/lib/dharma-sadhana/snapshot-incoming/uploads",
            "ReadWritePaths=/var/lib/dharma-sadhana/snapshot-staging ",
            "/var/lib/dharma-sadhana/snapshot-finalizing",
            "/var/lib/dharma-sadhana/snapshot-quarantine",
            "/var/lib/dharma-sadhana/snapshot-receipts",
            "/var/lib/dharma-sadhana/snapshot-outbox",
            "IPAddressAllow=100.79.111.89/32",
            "CapabilityBoundingSet=CAP_CHOWN CAP_DAC_OVERRIDE CAP_FOWNER",
        )
        if any(fragment not in text for fragment in required_fragments):
            raise ReleaseContractError("snapshot root finalizer binding differs")
    if canonical_name == "dharma-sadhana-snapshot-finalize.path" and (
        "PathExistsGlob=/var/lib/dharma-sadhana/snapshot-staging/"
        "????????T??????Z-????????????" not in text
        or "Unit=dharma-sadhana-snapshot-finalize.service" not in text
        or "DirectoryNotEmpty=/var/lib/dharma-sadhana/snapshot-staging" in text
    ):
        raise ReleaseContractError("snapshot finalizer path binding differs")
    if canonical_name == "dharma-sadhana-snapshot-retry.timer" and (
        "Unit=dharma-sadhana-snapshot-finalize.service" not in text
        or "OnUnitInactiveSec=60s" not in text
        or "PartOf=dharma-sadhana.target" not in text
    ):
        raise ReleaseContractError("snapshot outbox retry timer binding differs")
    if canonical_name == "dharma-sadhana-standby-snapshot-receiver.service":
        required_fragments = (
            "User=root",
            "sadhana_release.py guard-start --role standby",
            "sadhana_snapshot.py finalize-standby",
            "PrivateNetwork=true",
            "ReadWritePaths=/var/lib/dharma-sadhana/snapshot-incoming/uploads ",
            "/var/lib/dharma-sadhana/snapshot-incoming/acks",
            "/var/lib/dharma-sadhana/snapshot-receiver-claims",
            "/var/lib/dharma-sadhana/snapshot-quarantine",
            "/var/lib/dharma-sadhana/snapshot-receipts",
            "CapabilityBoundingSet=CAP_CHOWN CAP_DAC_OVERRIDE CAP_FOWNER",
        )
        if any(fragment not in text for fragment in required_fragments):
            raise ReleaseContractError("standby snapshot receiver binding differs")
    if canonical_name == "dharma-sadhana-standby-snapshot-receiver.path" and (
        "PathExistsGlob=/var/lib/dharma-sadhana/snapshot-incoming/"
        "uploads/????????T??????Z-????????????.upload-*/.ready.json" not in text
        or "Unit=dharma-sadhana-standby-snapshot-receiver.service" not in text
        or "WantedBy=dharma-sadhana-standby.target" not in text
        or "DirectoryNotEmpty=/var/lib/dharma-sadhana/snapshot-incoming" in text
    ):
        raise ReleaseContractError("standby snapshot receiver path binding differs")
    if canonical_name == "dharma-sadhana-standby-snapshot-receiver.timer" and (
        "Unit=dharma-sadhana-standby-snapshot-receiver.service" not in text
        or "OnUnitInactiveSec=60s" not in text
        or "WantedBy=dharma-sadhana-standby.target" not in text
    ):
        raise ReleaseContractError("standby snapshot retry timer binding differs")
    if canonical_name == "dharma-sadhana-standby.target" and (
        "ConditionPathExists=!/etc/dharma-sadhana/receipts/standby/"
        "deadline-stopped.v1.json" not in text
        or "dharma-sadhana-standby-snapshot-receiver.path" not in text
        or "dharma-sadhana-standby-snapshot-receiver.timer" not in text
        or STANDBY_REPLICATION_SERVE_UNIT not in text
    ):
        raise ReleaseContractError("standby target deadline binding differs")
    if canonical_name == "dharma-sadhana-standby-stop.service":
        target_stop = (
            "ExecStart=+/usr/bin/systemctl disable --now "
            "dharma-sadhana-standby.target"
        )
        receipt = "sadhana_release.py persist-standby-stop --role standby"
        if (
            "sadhana_release.py guard-stop --role standby" not in text
            or target_stop not in text
            or receipt not in text
            or text.index(target_stop) > text.index(receipt)
            or "PartOf=dharma-sadhana-standby.target" in text
        ):
            raise ReleaseContractError("standby deadline stop binding differs")
    if name.endswith(".service.in") and "@RELEASE_SHA@" not in text and not rendered:
        raise ReleaseContractError(
            f"service template lacks exact release token: {name}"
        )
    if rendered and "@RELEASE_SHA@" in text:
        raise ReleaseContractError(f"rendered unit retains release token: {name}")


def render_units(repo_root: Path, release_sha: str, output_root: Path) -> list[Path]:
    if not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("unit release SHA is invalid")
    output_root.mkdir(parents=True, exist_ok=True)
    rendered_paths: list[Path] = []
    for source in _unit_templates(repo_root):
        text = source.read_text(encoding="utf-8")
        validate_unit_text(source.name, text, rendered=False)
        rendered = text.replace("@RELEASE_SHA@", release_sha)
        destination_name = source.name.removesuffix(".in")
        validate_unit_text(destination_name, rendered, rendered=True)
        destination = output_root / destination_name
        destination.write_text(rendered, encoding="utf-8")
        os.chmod(destination, 0o644)
        rendered_paths.append(destination)
    return rendered_paths


_LIVE_WRITER_SERVICE_UNITS = (CONTROL_UNIT, DASHBOARD_UNIT)
_LIVE_WRITER_UNIT_PROPERTY_NAMES = (
    "FragmentPath",
    "DropInPaths",
    "User",
    "Group",
    "NoNewPrivileges",
    "CapabilityBoundingSet",
    "ProtectSystem",
    "ReadWritePaths",
    "Environment",
    "EnvironmentFiles",
    "NeedDaemonReload",
)
_LIVE_WRITER_EXEC_PROPERTY_NAMES = ("ExecStartEx", "ExecStartPreEx")
_SYSTEMD_EXEC_RECORD_RE = re.compile(
    r"\{\s*path=(?P<path>[^ ;{}]+)\s*;\s*"
    r"argv\[\]=(?P<argv>.*?)\s*;\s*"
    r"flags=(?P<flags>[^ ;}]*)\s*;"
)


def _stable_root_unit_bytes(
    path: Path,
    *,
    expected_uid: int,
    expected_gid: int,
    expected_mode: int,
) -> tuple[bytes, tuple[int, ...]]:
    """Read one root-custodied unit without following or racing its inode."""

    if not path.is_absolute() or expected_mode not in {0o444, 0o644}:
        raise ReleaseContractError("live systemd unit custody binding differs")
    current = Path(path.anchor)
    for part in path.parts[1:-1]:
        current /= part
        try:
            parent = current.lstat()
        except OSError as exc:
            raise ReleaseContractError(
                "live systemd unit parent is unavailable"
            ) from exc
        parent_mode = stat.S_IMODE(parent.st_mode)
        sticky_root = bool(parent.st_uid == 0 and parent.st_mode & stat.S_ISVTX)
        if (
            not stat.S_ISDIR(parent.st_mode)
            or current.is_symlink()
            or parent.st_uid not in {0, expected_uid}
            or (parent_mode & 0o022 and not sticky_root)
        ):
            raise ReleaseContractError("live systemd unit parent custody differs")
    try:
        admitted = path.lstat()
    except OSError as exc:
        raise ReleaseContractError("live systemd unit is unavailable") from exc
    if (
        path.is_symlink()
        or not stat.S_ISREG(admitted.st_mode)
        or admitted.st_uid != expected_uid
        or admitted.st_gid != expected_gid
        or stat.S_IMODE(admitted.st_mode) != expected_mode
        or admitted.st_nlink != 1
        or not 0 < admitted.st_size <= 256 * 1024
    ):
        raise ReleaseContractError("live systemd unit custody differs")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ReleaseContractError("platform lacks no-follow unit admission")
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        opened = os.fstat(descriptor)
        raw = b""
        while len(raw) <= 256 * 1024:
            chunk = os.read(descriptor, min(65_536, 256 * 1024 + 1 - len(raw)))
            if not chunk:
                break
            raw += chunk
        stable = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    final = path.lstat()

    def identity(value: os.stat_result) -> tuple[int, ...]:
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_uid,
            value.st_gid,
            value.st_nlink,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    admitted_identity = identity(admitted)
    if (
        len(raw) != admitted.st_size
        or len(raw) > 256 * 1024
        or admitted_identity != identity(opened)
        or admitted_identity != identity(stable)
        or admitted_identity != identity(final)
    ):
        raise ReleaseContractError("live systemd unit changed during admission")
    return raw, admitted_identity


def _single_unit_assignment(assignments: Sequence[str], key: str) -> str:
    prefix = f"{key}="
    values = [line.removeprefix(prefix) for line in assignments if line.startswith(prefix)]
    if len(values) != 1:
        raise ReleaseContractError("live systemd unit assignment set differs")
    return values[0]


def _expected_exec_property(
    assignments: Sequence[str],
    key: str,
) -> tuple[tuple[str, str, str], ...]:
    prefix = f"{key}="
    commands = [line.removeprefix(prefix) for line in assignments if line.startswith(prefix)]
    expected: list[tuple[str, str, str]] = []
    for source in commands:
        flags = ""
        while source and source[0] in "-+!:@":
            flags += source[0]
            source = source[1:]
        try:
            argv = shlex.split(source, posix=True)
        except ValueError as exc:
            raise ReleaseContractError("live systemd exec binding differs") from exc
        if not argv or " ".join(argv) != source:
            raise ReleaseContractError("live systemd exec binding differs")
        effective_flags: list[str] = []
        for flag in flags:
            if flag == "-":
                effective_flags.append("ignore-failure")
            elif flag == "+":
                effective_flags.append("privileged")
            else:
                raise ReleaseContractError("live systemd exec prefix differs")
        expected.append((argv[0], source, ",".join(effective_flags)))
    if not expected:
        raise ReleaseContractError("live systemd exec binding is absent")
    return tuple(expected)


def _parse_live_exec_property(value: str) -> tuple[tuple[str, str, str], ...]:
    matches = tuple(
        (
            match.group("path"),
            match.group("argv"),
            match.group("flags"),
        )
        for match in _SYSTEMD_EXEC_RECORD_RE.finditer(value)
    )
    if (
        not matches
        or len(matches) != value.count("argv[]=")
        or len(matches) != value.count("{")
        or len(matches) != value.count("}")
    ):
        raise ReleaseContractError("live systemd exec property differs")
    return matches


def _expected_live_unit_properties(
    *,
    unit: str,
    assignments: Sequence[str],
    fragment_path: Path,
) -> dict[str, str]:
    environment_file = _single_unit_assignment(assignments, "EnvironmentFile")
    if environment_file.startswith("-"):
        environment_file = environment_file[1:]
        ignore_errors = "yes"
    else:
        ignore_errors = "no"
    no_new_privileges = _single_unit_assignment(
        assignments, "NoNewPrivileges"
    )
    if no_new_privileges not in {"true", "false"}:
        raise ReleaseContractError("live systemd no-new-privileges binding differs")
    if unit not in _LIVE_WRITER_SERVICE_UNITS:
        raise ReleaseContractError("live systemd unit name differs")
    environments = [
        line.removeprefix("Environment=")
        for line in assignments
        if line.startswith("Environment=")
    ]
    if not environments or any(
        "%" in value.replace("%d", "") for value in environments
    ):
        raise ReleaseContractError("live systemd environment binding differs")
    credential_directory = f"/run/credentials/{unit}"
    effective_environment = " ".join(
        value.replace("%d", credential_directory) for value in environments
    )
    return {
        "FragmentPath": str(fragment_path),
        "DropInPaths": "",
        "User": _single_unit_assignment(assignments, "User"),
        "Group": _single_unit_assignment(assignments, "Group"),
        "NoNewPrivileges": "yes" if no_new_privileges == "true" else "no",
        "CapabilityBoundingSet": _single_unit_assignment(
            assignments, "CapabilityBoundingSet"
        ).lower(),
        "ProtectSystem": _single_unit_assignment(assignments, "ProtectSystem"),
        "ReadWritePaths": _single_unit_assignment(
            assignments, "ReadWritePaths"
        ),
        "Environment": effective_environment,
        "EnvironmentFiles": (
            f"{environment_file} (ignore_errors={ignore_errors})"
        ),
        "NeedDaemonReload": "no",
    }


def _read_systemd_unit_properties(
    unit: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> dict[str, str]:
    result = runner(
        (
            SYSTEMCTL_PATH,
            "show",
            *(f"--property={name}" for name in _LIVE_WRITER_UNIT_PROPERTY_NAMES),
            unit,
        ),
        cwd=Path("/"),
        check=False,
    )
    if (
        result.returncode != 0
        or result.stderr
        or len(result.stdout) > 256 * 1024
        or "\x00" in result.stdout
        or "\r" in result.stdout
    ):
        raise ReleaseContractError("live systemd unit properties are unavailable")
    properties: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition("=")
        if not separator or key in properties:
            raise ReleaseContractError("live systemd unit property set differs")
        properties[key] = value
    if set(properties) != set(_LIVE_WRITER_UNIT_PROPERTY_NAMES):
        raise ReleaseContractError("live systemd unit property set differs")
    return properties


def _read_systemd_exec_property(
    unit: str,
    property_name: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> tuple[tuple[str, str, str], ...]:
    if property_name not in _LIVE_WRITER_EXEC_PROPERTY_NAMES:
        raise ReleaseContractError("live systemd exec property name differs")
    result = runner(
        (
            SYSTEMCTL_PATH,
            "show",
            f"--property={property_name}",
            "--value",
            unit,
        ),
        cwd=Path("/"),
        check=False,
    )
    if (
        result.returncode != 0
        or result.stderr
        or len(result.stdout) > 256 * 1024
        or "\x00" in result.stdout
        or "\r" in result.stdout
    ):
        raise ReleaseContractError("live systemd exec property is unavailable")
    records = [line for line in result.stdout.splitlines() if line]
    if not records:
        raise ReleaseContractError("live systemd exec property is absent")
    return _parse_live_exec_property(" ; ".join(records))


def _check_loaded_writer_service_units(
    *,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    unit_root: Path = SYSTEMD_OUTPUT_ROOT,
    release_root: Path = Path(RELEASE_ROOT),
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> None:
    """Compare loaded writer services with immutable, drop-in-free fragments."""

    if not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("live systemd release binding differs")
    for unit in _LIVE_WRITER_SERVICE_UNITS:
        template_path = (
            release_root / release_sha / SYSTEMD_TEMPLATE_ROOT / f"{unit}.in"
        )
        template_raw, _template_identity = _stable_root_unit_bytes(
            template_path,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
            expected_mode=0o444,
        )
        try:
            template_text = template_raw.decode("utf-8")
        except UnicodeError as exc:
            raise ReleaseContractError("immutable systemd template is not UTF-8") from exc
        validate_unit_text(f"{unit}.in", template_text, rendered=False)
        rendered_text = template_text.replace("@RELEASE_SHA@", release_sha)
        validate_unit_text(unit, rendered_text, rendered=True)
        expected_raw = rendered_text.encode("utf-8")
        fragment_path = unit_root / unit
        installed_raw, installed_identity = _stable_root_unit_bytes(
            fragment_path,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
            expected_mode=0o644,
        )
        if installed_raw != expected_raw:
            raise ReleaseContractError("installed systemd fragment differs")
        assignments = _unit_section_assignments(rendered_text, "Service")
        expected_properties = _expected_live_unit_properties(
            unit=unit,
            assignments=assignments,
            fragment_path=fragment_path,
        )
        properties = _read_systemd_unit_properties(unit, runner=runner)
        actual_exec_start = _read_systemd_exec_property(
            unit,
            "ExecStartEx",
            runner=runner,
        )
        actual_exec_start_pre = _read_systemd_exec_property(
            unit,
            "ExecStartPreEx",
            runner=runner,
        )
        if (
            properties != expected_properties
            or actual_exec_start
            != _expected_exec_property(assignments, "ExecStart")
            or actual_exec_start_pre
            != _expected_exec_property(assignments, "ExecStartPre")
        ):
            raise ReleaseContractError("effective systemd unit binding differs")
        confirmed_raw, confirmed_identity = _stable_root_unit_bytes(
            fragment_path,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
            expected_mode=0o644,
        )
        if confirmed_raw != installed_raw or confirmed_identity != installed_identity:
            raise ReleaseContractError("installed systemd fragment changed during gate")


def _require_live_writer_service_units(
    *,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    unit_root: Path = SYSTEMD_OUTPUT_ROOT,
    release_root: Path = Path(RELEASE_ROOT),
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
    reload_manager: bool = True,
) -> None:
    """Reject stale loaded state, root-reload, then recheck exact live units."""

    check_kwargs = {
        "release_sha": release_sha,
        "runner": runner,
        "unit_root": unit_root,
        "release_root": release_root,
        "expected_root_uid": expected_root_uid,
        "expected_root_gid": expected_root_gid,
    }
    _check_loaded_writer_service_units(**check_kwargs)
    if not reload_manager:
        return
    reloaded = runner(
        (SYSTEMCTL_PATH, "daemon-reload"),
        cwd=Path("/"),
        check=False,
    )
    if reloaded.returncode != 0 or reloaded.stdout or reloaded.stderr:
        raise ReleaseContractError("live systemd manager reload failed")
    _check_loaded_writer_service_units(**check_kwargs)


def _current_frozen_release_sha() -> str:
    script_path = Path(__file__).resolve(strict=True)
    release_path = script_path.parents[2]
    if (
        release_path.parent != Path(RELEASE_ROOT)
        or not _COMMIT_RE.fullmatch(release_path.name)
    ):
        raise ReleaseContractError("start guard is outside an immutable release")
    return release_path.name


def _validate_exact_stop_timer_bytes(raw: bytes, *, role: str) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise ReleaseContractError("release stop timer is not UTF-8") from exc
    if role == "writer":
        timer_unit = CAMPAIGN_STOP_TIMER
        service_unit = "dharma-sadhana-campaign-stop.service"
        wanted_by = "timers.target"
    elif role == "standby":
        timer_unit = STANDBY_STOP_TIMER
        service_unit = "dharma-sadhana-standby-stop.service"
        wanted_by = "multi-user.target"
    else:
        raise ReleaseContractError("release stop timer role differs")
    validate_unit_text(
        timer_unit,
        text,
        rendered=True,
    )
    required = {
        "OnCalendar=2026-09-01 17:15:12 UTC": 1,
        "AccuracySec=1s": 1,
        "Persistent=true": 1,
        f"Unit={service_unit}": 1,
        f"WantedBy={wanted_by}": 1,
    }
    lines = [line.strip() for line in text.splitlines()]
    if any(lines.count(line) != count for line, count in required.items()):
        raise ReleaseContractError("release stop timer has ambiguous bindings")
    return hashlib.sha256(raw).hexdigest()


def _preactivation_timer_paths(
    *,
    role: str,
    release_sha: str,
) -> tuple[Path, Path, str]:
    if not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("clock proof release SHA is invalid")
    if role == "writer":
        timer_unit = CAMPAIGN_STOP_TIMER
    elif role == "standby":
        timer_unit = STANDBY_STOP_TIMER
    else:
        raise ReleaseContractError("clock proof timer role differs")
    return (
        Path(RELEASE_ROOT)
        / release_sha
        / SYSTEMD_TEMPLATE_ROOT
        / timer_unit,
        SYSTEMD_OUTPUT_ROOT / timer_unit,
        timer_unit,
    )


def record_preactivation_clock_proof(
    *,
    role: str,
    release_sha: str,
    controller_utc: str,
    known_hosts_sha256: str,
    strict_host_key_channel: bool,
    staged_release_admission_receipt_digest: str,
    release_timer_path: Path,
    installed_timer_path: Path,
    receipt_path: Path = PREACTIVATION_CLOCK_RECEIPT,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    now: datetime | None = None,
    observed_node: str | None = None,
    ssh_connection_observed: bool | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Record fresh NTP/skew/timer proof obtained through strict SSH custody."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("clock proof requires root")
    node = _require_host_role(role, observed_node=observed_node)
    if not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("clock proof release SHA is invalid")
    expected_release_timer, expected_installed_timer, timer_unit = (
        _preactivation_timer_paths(role=role, release_sha=release_sha)
    )
    if (
        release_timer_path != expected_release_timer
        or installed_timer_path != expected_installed_timer
    ):
        raise ReleaseContractError("clock proof timer paths differ")
    _require_hash(known_hosts_sha256, "known_hosts_sha256")
    if known_hosts_sha256 != DEPLOYMENT_KNOWN_HOSTS_SHA256:
        raise ReleaseContractError("clock proof known-hosts binding differs")
    if not isinstance(staged_release_admission_receipt_digest, str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", staged_release_admission_receipt_digest
    ):
        raise ReleaseContractError("clock proof staged-admission digest differs")
    connection_observed = (
        bool(os.environ.get("SSH_CONNECTION"))
        if ssh_connection_observed is None
        else ssh_connection_observed
    )
    if not strict_host_key_channel or not connection_observed:
        raise ReleaseContractError("clock proof lacks its strict SSH channel")
    controller = _parse_utc(controller_utc, "controller_utc")
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ReleaseContractError("clock proof host time must be timezone-aware")
    observed = observed.astimezone(timezone.utc).replace(microsecond=0)
    guard_campaign_clock(role=role, now=observed, observed_node=node)
    skew = abs((observed - controller).total_seconds())
    if skew > MAX_CONTROLLER_CLOCK_SKEW_SECONDS:
        raise ReleaseContractError("host clock exceeds controller skew bound")
    ntp = runner(
        (
            TIMEDATECTL_PATH,
            "show",
            "--property=NTPSynchronized",
            "--value",
        ),
        cwd=Path("/"),
        check=False,
    )
    if ntp.returncode != 0 or ntp.stdout.strip() != "yes":
        raise ReleaseContractError("host clock is not NTP-synchronized")
    release_timer_identity = release_timer_path.lstat()
    release_timer_raw = _read_input_source(
        release_timer_path,
        expected_bytes=release_timer_identity.st_size,
        expected_uid=expected_root_uid,
    )
    timer_sha256 = _validate_exact_stop_timer_bytes(release_timer_raw, role=role)
    installed_identity = installed_timer_path.lstat()
    installed_raw = _read_input_source(
        installed_timer_path,
        expected_bytes=installed_identity.st_size,
        expected_uid=expected_root_uid,
    )
    _validate_exact_stop_timer_bytes(installed_raw, role=role)
    if installed_raw != release_timer_raw:
        raise ReleaseContractError("installed stop timer differs from release bytes")
    installed_timer_match = True
    expires = observed + timedelta(seconds=CLOCK_PROOF_FRESHNESS_SECONDS)
    receipt: dict[str, Any] = {
        "schema_version": PREACTIVATION_CLOCK_SCHEMA_VERSION,
        "mission_id": MISSION_ID,
        "release_sha": release_sha,
        "staged_release_admission_receipt_digest": (
            staged_release_admission_receipt_digest
        ),
        "role": role,
        "hostname": node,
        "controller_utc": controller.isoformat().replace("+00:00", "Z"),
        "host_utc": observed.isoformat().replace("+00:00", "Z"),
        "skew_seconds": skew,
        "max_skew_seconds": MAX_CONTROLLER_CLOCK_SKEW_SECONDS,
        "ntp_synchronized": True,
        "strict_host_key_channel": True,
        "ssh_connection_observed": True,
        "known_hosts_sha256": known_hosts_sha256,
        "campaign_stop_utc": CAMPAIGN_STOP_UTC,
        "timer_unit": timer_unit,
        "timer_on_calendar": "2026-09-01 17:15:12 UTC",
        "timer_accuracy_seconds": 1,
        "timer_persistent": True,
        "release_timer_sha256": timer_sha256,
        "installed_timer_match": installed_timer_match,
        "valid_until": expires.isoformat().replace("+00:00", "Z"),
        "receipt_digest": "",
    }
    receipt["receipt_digest"] = _canonical_self_digest(receipt, "receipt_digest")
    if set(receipt) != _PREACTIVATION_CLOCK_PROOF_FIELDS:
        raise ReleaseContractError("clock-proof receipt fields differ")
    if receipt_path != PREACTIVATION_CLOCK_RECEIPT:
        raise ReleaseContractError("clock-proof receipt target differs")
    _require_secure_parent_chain(receipt_path)
    _atomic_private_bytes(
        receipt_path,
        _canonical_bytes(receipt) + b"\n",
        uid=expected_root_uid,
        gid=expected_root_gid,
        replace_existing=True,
    )
    return receipt


def validate_preactivation_clock_proof(
    *,
    release_sha: str,
    role: str,
    known_hosts_sha256: str,
    staged_release_admission_receipt_digest: str,
    receipt_path: Path = PREACTIVATION_CLOCK_RECEIPT,
    now: datetime | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    if not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("clock-proof release SHA is invalid")
    _require_hash(known_hosts_sha256, "known_hosts_sha256")
    if known_hosts_sha256 != DEPLOYMENT_KNOWN_HOSTS_SHA256:
        raise ReleaseContractError("clock-proof known-hosts binding differs")
    if not isinstance(staged_release_admission_receipt_digest, str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", staged_release_admission_receipt_digest
    ):
        raise ReleaseContractError("clock-proof staged-admission digest differs")
    if receipt_path != PREACTIVATION_CLOCK_RECEIPT:
        raise ReleaseContractError("clock-proof receipt target differs")
    receipt, _raw, _identity = _read_exact_custodied_json(
        receipt_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )
    if set(receipt) != _PREACTIVATION_CLOCK_PROOF_FIELDS or receipt.get(
        "receipt_digest"
    ) != _canonical_self_digest(receipt, "receipt_digest"):
        raise ReleaseContractError("clock-proof receipt digest differs")
    node = _require_host_role(role, observed_node=observed_node)
    release_timer_path, installed_timer_path, timer_unit = (
        _preactivation_timer_paths(role=role, release_sha=release_sha)
    )
    exact = {
        "schema_version": PREACTIVATION_CLOCK_SCHEMA_VERSION,
        "mission_id": MISSION_ID,
        "release_sha": release_sha,
        "staged_release_admission_receipt_digest": (
            staged_release_admission_receipt_digest
        ),
        "role": role,
        "hostname": node,
        "max_skew_seconds": MAX_CONTROLLER_CLOCK_SKEW_SECONDS,
        "ntp_synchronized": True,
        "strict_host_key_channel": True,
        "ssh_connection_observed": True,
        "known_hosts_sha256": known_hosts_sha256,
        "campaign_stop_utc": CAMPAIGN_STOP_UTC,
        "timer_unit": timer_unit,
        "timer_on_calendar": "2026-09-01 17:15:12 UTC",
        "timer_accuracy_seconds": 1,
        "timer_persistent": True,
        "installed_timer_match": True,
    }
    if any(receipt.get(key) != value for key, value in exact.items()):
        raise ReleaseContractError("clock-proof exact bindings differ")
    release_timer_identity = release_timer_path.lstat()
    release_timer_raw = _read_input_source(
        release_timer_path,
        expected_bytes=release_timer_identity.st_size,
        expected_uid=expected_root_uid,
    )
    installed_timer_identity = installed_timer_path.lstat()
    installed_timer_raw = _read_input_source(
        installed_timer_path,
        expected_bytes=installed_timer_identity.st_size,
        expected_uid=expected_root_uid,
    )
    current_timer_sha256 = _validate_exact_stop_timer_bytes(
        release_timer_raw,
        role=role,
    )
    _validate_exact_stop_timer_bytes(installed_timer_raw, role=role)
    if (
        installed_timer_raw != release_timer_raw
        or receipt.get("release_timer_sha256") != current_timer_sha256
    ):
        raise ReleaseContractError("clock-proof stop timer drifted")
    skew = receipt.get("skew_seconds")
    controller_utc = _parse_utc(
        str(receipt.get("controller_utc", "")), "controller_utc"
    )
    host_utc = _parse_utc(str(receipt.get("host_utc", "")), "host_utc")
    expected_skew = abs((host_utc - controller_utc).total_seconds())
    if (
        isinstance(skew, bool)
        or not isinstance(skew, (int, float))
        or not 0 <= skew <= MAX_CONTROLLER_CLOCK_SKEW_SECONDS
        or skew != expected_skew
        or not isinstance(receipt.get("release_timer_sha256"), str)
        or not _SHA_RE.fullmatch(receipt["release_timer_sha256"])
    ):
        raise ReleaseContractError("clock-proof skew differs")
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ReleaseContractError("clock-proof validation time must be aware")
    valid_until = _parse_utc(receipt.get("valid_until", ""), "valid_until")
    observed = observed.astimezone(timezone.utc)
    if (
        valid_until != host_utc + timedelta(seconds=CLOCK_PROOF_FRESHNESS_SECONDS)
        or observed < host_utc
        or observed > valid_until
    ):
        raise ReleaseContractError("clock proof is not fresh")
    return receipt


def _systemd_main_pid(
    unit: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> int:
    result = runner(
        (SYSTEMCTL_PATH, "show", "--property=MainPID", "--value", unit),
        cwd=Path("/"),
        check=False,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or not value.isascii() or not value.isdigit():
        raise ReleaseContractError("cannot establish the systemd main process identity")
    return int(value)


def _observer_listener_identity(
    *,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    account = _require_observer_identity()
    pid = _systemd_main_pid(OBSERVER_UNIT, runner=runner)
    if pid <= 0:
        raise ReleaseContractError(
            "immutable observer has no live systemd main process"
        )
    process_root = proc_root / str(pid)
    try:
        cmdline = (process_root / "cmdline").read_bytes()
        status_raw = (process_root / "status").read_text(encoding="ascii")
        stat_raw = (process_root / "stat").read_text(encoding="utf-8")
        tcp_raw = (process_root / "net/tcp").read_text(encoding="ascii")
        fd_entries = tuple((process_root / "fd").iterdir())
        process_filesystem = (process_root / "root").stat()
    except OSError as exc:
        raise ReleaseContractError(
            "cannot inspect the immutable observer process"
        ) from exc
    expected_argv = (
        f"{RELEASE_ROOT}/{release_sha}/.venv/bin/python",
        "-m",
        "uvicorn",
        "scripts.runtime.sadhana_immutable_api:app",
        "--host",
        "127.0.0.1",
        "--port",
        "18420",
        "--workers",
        "1",
        "--no-access-log",
        "--no-proxy-headers",
    )
    if cmdline != b"\0".join(value.encode("utf-8") for value in expected_argv) + b"\0":
        raise ReleaseContractError("immutable observer process arguments differ")
    status: dict[str, str] = {}
    for line in status_raw.splitlines():
        key, separator, value = line.partition(":")
        if separator and key in {"Uid", "Gid", "Groups", "NoNewPrivs"}:
            if key in status:
                raise ReleaseContractError("immutable observer identity is ambiguous")
            status[key] = value.strip()
    expected_uid = str(account.pw_uid)
    expected_gid = str(account.pw_gid)
    if (
        not stat.S_ISDIR(process_filesystem.st_mode)
        or status.get("Uid", "").split() != [expected_uid] * 4
        or status.get("Gid", "").split() != [expected_gid] * 4
        or status.get("Groups", "").split() != [expected_gid]
        or status.get("NoNewPrivs") != "1"
    ):
        raise ReleaseContractError("immutable observer process identity differs")
    forbidden_paths = (
        "/etc/dharma-sadhana",
        "/var/lib/dharma-sadhana/state",
        "/var/lib/dharma-sadhana/workspace",
        "/var/lib/dharma-sadhana/leases",
        "/var/lib/dharma-sadhana/snapshots",
        "/var/lib/dharma-sadhana/projection-source",
        "/var/lib/dharma-sadhana/emergency-inflight",
        "/run/dharma-sadhana/control",
        "/run/dharma-sadhana/emergency-quarantine",
    )
    for forbidden in forbidden_paths:
        candidate = process_root / "root" / forbidden.removeprefix("/")
        try:
            identity = candidate.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ReleaseContractError(
                "cannot prove immutable observer mount isolation"
            ) from exc
        if stat.S_IMODE(identity.st_mode) != 0:
            raise ReleaseContractError(
                "canonical path remains visible to immutable observer"
            )
    try:
        suffix = stat_raw.rsplit(") ", maxsplit=1)[1].split()
        start_ticks = int(suffix[19])
    except (IndexError, ValueError) as exc:
        raise ReleaseContractError("immutable observer process stat differs") from exc
    socket_inodes: set[int] = set()
    for entry in fd_entries:
        try:
            target = os.readlink(entry)
        except OSError:
            continue
        match = re.fullmatch(r"socket:\[([0-9]+)\]", target)
        if match:
            socket_inodes.add(int(match.group(1)))
    listener_inodes: set[int] = set()
    for line in tcp_raw.splitlines()[1:]:
        fields = line.split()
        if (
            len(fields) >= 10
            and fields[1] == "0100007F:47F4"
            and fields[3] == "0A"
            and fields[9].isdigit()
        ):
            listener_inodes.add(int(fields[9]))
    owned = socket_inodes & listener_inodes
    if len(owned) != 1:
        raise ReleaseContractError("immutable observer listener ownership differs")
    return {
        "unit": OBSERVER_UNIT,
        "main_pid": pid,
        "proc_start_ticks": start_ticks,
        "cmdline_sha256": hashlib.sha256(cmdline).hexdigest(),
        "socket_inode": next(iter(owned)),
        "uid": account.pw_uid,
        "gid": account.pw_gid,
        "forbidden_path_count": len(forbidden_paths),
        "canonical_path_visible": False,
        "release_sha": release_sha,
    }


def _control_listener_identity(
    *,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    """Bind the loopback control listener to its exact systemd main process."""
    if not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("control release SHA differs")
    try:
        account = pwd.getpwnam("dharma-sadhana-control")
    except KeyError as exc:
        raise ReleaseContractError("control service identity is unavailable") from exc
    if account.pw_uid == 0 or account.pw_gid == 0:
        raise ReleaseContractError("control service identity differs")
    unit = "dharma-sadhana-control.service"
    pid = _systemd_main_pid(unit, runner=runner)
    if pid <= 0:
        raise ReleaseContractError("control service has no live systemd main process")
    process_root = proc_root / str(pid)
    try:
        cmdline = (process_root / "cmdline").read_bytes()
        status_raw = (process_root / "status").read_text(encoding="ascii")
        stat_raw = (process_root / "stat").read_text(encoding="utf-8")
        tcp_raw = (process_root / "net/tcp").read_text(encoding="ascii")
        tcp6_raw = (process_root / "net/tcp6").read_text(encoding="ascii")
        fd_entries = tuple((process_root / "fd").iterdir())
    except OSError as exc:
        raise ReleaseContractError("cannot inspect the control process") from exc
    expected_argv = (
        f"{RELEASE_ROOT}/{release_sha}/.venv/bin/python",
        "-m",
        "scripts.runtime.sadhana_control_api",
    )
    if cmdline != b"\0".join(value.encode("utf-8") for value in expected_argv) + b"\0":
        raise ReleaseContractError("control process arguments differ")
    status: dict[str, str] = {}
    for line in status_raw.splitlines():
        key, separator, value = line.partition(":")
        if separator and key in {"Uid", "Gid", "Groups", "NoNewPrivs"}:
            if key in status:
                raise ReleaseContractError("control process status is ambiguous")
            status[key] = value.strip()
    expected_uid = str(account.pw_uid)
    expected_gid = str(account.pw_gid)
    if (
        status.get("Uid", "").split() != [expected_uid] * 4
        or status.get("Gid", "").split() != [expected_gid] * 4
        or status.get("Groups", "").split() != [expected_gid]
        or status.get("NoNewPrivs") != "1"
    ):
        raise ReleaseContractError("control process identity differs")
    try:
        suffix = stat_raw.rsplit(") ", maxsplit=1)[1].split()
        start_ticks = int(suffix[19])
    except (IndexError, ValueError) as exc:
        raise ReleaseContractError("control process stat differs") from exc
    socket_inodes: set[int] = set()
    for entry in fd_entries:
        try:
            target = os.readlink(entry)
        except OSError:
            continue
        match = re.fullmatch(r"socket:\[([0-9]+)\]", target)
        if match:
            socket_inodes.add(int(match.group(1)))
    loopback_listener_inodes: set[int] = set()
    unexpected_listener_inodes: set[int] = set()
    for family, raw in (("tcp", tcp_raw), ("tcp6", tcp6_raw)):
        for line in raw.splitlines()[1:]:
            fields = line.split()
            if len(fields) < 10 or fields[3] != "0A" or not fields[9].isdigit():
                continue
            inode = int(fields[9])
            if fields[1] == "0100007F:47F5" and family == "tcp":
                loopback_listener_inodes.add(inode)
            if inode in socket_inodes and fields[1] != "0100007F:47F5":
                unexpected_listener_inodes.add(inode)
    owned = socket_inodes & loopback_listener_inodes
    if (
        len(loopback_listener_inodes) != 1
        or len(owned) != 1
        or unexpected_listener_inodes
    ):
        raise ReleaseContractError("control loopback listener ownership differs")
    return {
        "unit": unit,
        "main_pid": pid,
        "proc_start_ticks": start_ticks,
        "cmdline_sha256": hashlib.sha256(cmdline).hexdigest(),
        "socket_inode": next(iter(owned)),
        "listen_address": "127.0.0.1:18421",
        "uid": account.pw_uid,
        "gid": account.pw_gid,
        "no_new_privileges": True,
        "release_sha": release_sha,
    }


def _dashboard_listener_identity(
    *,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    proc_root: Path = Path("/proc"),
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Prove the admitted dashboard owns one UDS listener and no TCP listener."""
    if not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("dashboard release SHA differs")
    account = _require_dashboard_identity()
    pid = _systemd_main_pid(DASHBOARD_UNIT, runner=runner)
    if pid <= 0:
        raise ReleaseContractError("dashboard has no live systemd main process")
    process_root = proc_root / str(pid)
    try:
        cmdline = (process_root / "cmdline").read_bytes()
        status_raw = (process_root / "status").read_text(encoding="ascii")
        tcp_raw = (process_root / "net/tcp").read_text(encoding="ascii")
        tcp6_raw = (process_root / "net/tcp6").read_text(encoding="ascii")
        unix_raw = (process_root / "net/unix").read_text(encoding="utf-8")
        fd_entries = tuple((process_root / "fd").iterdir())
        outer = RUNTIME_ROOT.lstat()
        directory = DASHBOARD_SOCKET_DIRECTORY.lstat()
        socket_identity = DASHBOARD_SOCKET_PATH.lstat()
    except OSError as exc:
        raise ReleaseContractError("cannot inspect dashboard ingress") from exc
    expected_argv = (
        "/usr/bin/node",
        f"{RELEASE_ROOT}/{release_sha}/deploy/sadhana/sadhana-dashboard-server.mjs",
    )
    if cmdline != b"\0".join(value.encode("utf-8") for value in expected_argv) + b"\0":
        raise ReleaseContractError("dashboard process arguments differ")
    status: dict[str, str] = {}
    for line in status_raw.splitlines():
        key, separator, value = line.partition(":")
        if separator and key in {"Uid", "Gid", "Groups", "NoNewPrivs"}:
            if key in status:
                raise ReleaseContractError("dashboard process status is ambiguous")
            status[key] = value.strip()
    expected_uid = str(account.pw_uid)
    expected_gid = str(account.pw_gid)
    if (
        status.get("Uid", "").split() != [expected_uid] * 4
        or status.get("Gid", "").split() != [expected_gid] * 4
        or status.get("Groups", "").split() != [expected_gid]
        or status.get("NoNewPrivs") != "1"
    ):
        raise ReleaseContractError("dashboard process identity differs")
    if (
        not stat.S_ISDIR(outer.st_mode)
        or RUNTIME_ROOT.is_symlink()
        or outer.st_uid != expected_root_uid
        or outer.st_gid != expected_root_gid
        or stat.S_IMODE(outer.st_mode) != 0o711
        or not stat.S_ISDIR(directory.st_mode)
        or DASHBOARD_SOCKET_DIRECTORY.is_symlink()
        or directory.st_uid != account.pw_uid
        or directory.st_gid != account.pw_gid
        or stat.S_IMODE(directory.st_mode) != 0o700
        or not stat.S_ISSOCK(socket_identity.st_mode)
        or DASHBOARD_SOCKET_PATH.is_symlink()
        or socket_identity.st_uid != account.pw_uid
        or socket_identity.st_gid != account.pw_gid
        or stat.S_IMODE(socket_identity.st_mode) != 0o600
        or socket_identity.st_nlink != 1
    ):
        raise ReleaseContractError("dashboard Unix socket custody differs")
    socket_inodes: set[int] = set()
    for entry in fd_entries:
        try:
            target = os.readlink(entry)
        except OSError:
            continue
        match = re.fullmatch(r"socket:\[([0-9]+)\]", target)
        if match:
            socket_inodes.add(int(match.group(1)))
    for raw in (tcp_raw, tcp6_raw):
        for line in raw.splitlines()[1:]:
            fields = line.split()
            if (
                len(fields) >= 10
                and fields[3] == "0A"
                and fields[9].isdigit()
                and int(fields[9]) in socket_inodes
            ):
                raise ReleaseContractError("dashboard owns an unadmitted TCP listener")
    admitted_unix: set[int] = set()
    for line in unix_raw.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 8 or fields[-1] != str(DASHBOARD_SOCKET_PATH):
            continue
        if fields[6].isdigit() and int(fields[6]) in socket_inodes:
            admitted_unix.add(int(fields[6]))
    if len(admitted_unix) != 1:
        raise ReleaseContractError("dashboard Unix listener ownership differs")
    return {
        "unit": DASHBOARD_UNIT,
        "main_pid": pid,
        "uid": account.pw_uid,
        "gid": account.pw_gid,
        "cmdline_sha256": hashlib.sha256(cmdline).hexdigest(),
        "socket_path": str(DASHBOARD_SOCKET_PATH),
        "socket_dev": socket_identity.st_dev,
        "socket_ino": socket_identity.st_ino,
        "listener_inode": next(iter(admitted_unix)),
        "tcp_listener_count": 0,
        "release_sha": release_sha,
    }


def _wait_for_dashboard_ingress(
    *,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    proc_root: Path = Path("/proc"),
    attempts: int = 100,
    delay_seconds: float = 0.1,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    if not 1 <= attempts <= 100 or not 0 <= delay_seconds <= 0.25:
        raise ReleaseContractError("dashboard readiness retry policy differs")
    last_error: ReleaseContractError | None = None
    for attempt in range(attempts):
        try:
            return _dashboard_listener_identity(
                release_sha=release_sha,
                runner=runner,
                proc_root=proc_root,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
        except ReleaseContractError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(delay_seconds)
    raise ReleaseContractError(
        "dashboard Unix ingress did not become ready"
    ) from last_error


def _fetch_observer_health(endpoint: str) -> bytes:
    request = urllib.request.Request(
        endpoint,
        method="GET",
        headers={"Accept": "application/json"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=2) as response:
            if response.status != 200:
                raise ReleaseContractError("immutable observer health status differs")
            raw = response.read(4097)
    except (OSError, urllib.error.URLError) as exc:
        raise ReleaseContractError("immutable observer health probe failed") from exc
    if not raw or len(raw) > 4096:
        raise ReleaseContractError("immutable observer health response size differs")
    return raw


def probe_observer_health(
    *,
    role: str,
    release_sha: str,
    receipt_path: Path = OBSERVER_HEALTH_RECEIPT,
    unit_path: Path = OBSERVER_UNIT_PATH,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    fetcher: Callable[[str], bytes] = _fetch_observer_health,
    proc_root: Path = Path("/proc"),
    now: Callable[[], datetime] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Prove twenty exact observer responses before any dispatcher MainPID exists."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("observer health acceptance requires root")
    _require_host_role(role, observed_node=observed_node)
    if role != "writer" or not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("observer health release binding differs")
    if receipt_path != OBSERVER_HEALTH_RECEIPT or unit_path != OBSERVER_UNIT_PATH:
        raise ReleaseContractError("observer health artifact paths differ")
    guard_campaign_clock(role=role, observed_node=observed_node)
    if _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0:
        raise ReleaseContractError("dispatch process exists before health acceptance")
    unit_digest = sha256_file(unit_path, max_bytes=256 * 1024)
    unit_text = unit_path.read_text(encoding="utf-8")
    if (
        f"/opt/dharma-sadhana/releases/{release_sha}/" not in unit_text
        or "--host 127.0.0.1 --port ${SADHANA_API_PORT}" not in unit_text
        or "EnvironmentFile=/etc/dharma-sadhana/api.env" not in unit_text
    ):
        raise ReleaseContractError("immutable observer installed unit differs")
    listener = _observer_listener_identity(
        release_sha=release_sha,
        runner=runner,
        proc_root=proc_root,
    )
    clock = now or (lambda: datetime.now(timezone.utc))
    started = clock()
    if started.tzinfo is None:
        raise ReleaseContractError("observer health clock must be timezone-aware")
    response_hashes: list[str] = []
    previous_tick: float | None = None
    required = {
        "status": "ok",
        "mode": "immutable_observer",
        "runtime_projection_mode": "unavailable",
        "proves_executor_liveness": False,
        "write_routes": 0,
    }
    for _index in range(OBSERVER_HEALTH_SUCCESS_COUNT):
        tick = monotonic()
        if (
            previous_tick is not None
            and tick - previous_tick > OBSERVER_HEALTH_MAX_GAP_SECONDS
        ):
            raise ReleaseContractError("immutable observer health probe gap exceeded")
        previous_tick = tick
        raw = fetcher(OBSERVER_HEALTH_ENDPOINT)
        try:
            payload = json.loads(raw, object_pairs_hook=_strict_object)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ReleaseContractError(
                "immutable observer health JSON differs"
            ) from exc
        if not isinstance(payload, dict) or any(
            payload.get(key) != value for key, value in required.items()
        ):
            raise ReleaseContractError("immutable observer health response differs")
        response_hashes.append(hashlib.sha256(raw).hexdigest())
    finished = clock()
    if finished.tzinfo is None:
        raise ReleaseContractError("observer health clock must be timezone-aware")
    if _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0:
        raise ReleaseContractError("dispatch process appeared during health acceptance")
    if listener != _observer_listener_identity(
        release_sha=release_sha,
        runner=runner,
        proc_root=proc_root,
    ):
        raise ReleaseContractError(
            "immutable observer changed during health acceptance"
        )
    receipt: dict[str, Any] = {
        "schema_version": OBSERVER_HEALTH_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "service_unit_digest": unit_digest,
        "endpoint": OBSERVER_HEALTH_ENDPOINT,
        "probe_started_at": started.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "probe_finished_at": finished.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "consecutive_successes": OBSERVER_HEALTH_SUCCESS_COUNT,
        "response_sha256_sequence": response_hashes,
        "listener_process_identity": listener,
        "dispatch_enabled_during_probe": False,
        "observer_identity_separated": True,
        "projection_source_separated": True,
        "canonical_paths_inaccessible": True,
        "health_is_work_evidence": False,
        "verdict": "PASS",
        "receipt_digest": "",
    }
    receipt["receipt_digest"] = _canonical_self_digest(receipt, "receipt_digest")
    if set(receipt) != _OBSERVER_HEALTH_RECEIPT_FIELDS:
        raise ReleaseContractError("observer health receipt fields differ")
    _require_secure_parent_chain(receipt_path)
    _atomic_private_bytes(
        receipt_path,
        _canonical_bytes(receipt) + b"\n",
        uid=expected_root_uid,
        gid=expected_root_gid,
        replace_existing=True,
    )
    return receipt


def validate_observer_health_receipt(
    *,
    release_sha: str,
    receipt_path: Path = OBSERVER_HEALTH_RECEIPT,
    unit_path: Path = OBSERVER_UNIT_PATH,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    proc_root: Path = Path("/proc"),
    now: datetime | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Revalidate the immutable 20-probe barrier immediately before enablement."""
    if not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("observer health release binding differs")
    payload, _raw, _identity = _read_exact_canonical_json(
        receipt_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=OBSERVER_HEALTH_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    if (
        set(payload) != _OBSERVER_HEALTH_RECEIPT_FIELDS
        or payload.get("campaign_id") != MISSION_ID
        or payload.get("release_sha") != release_sha
        or payload.get("service_unit_digest")
        != sha256_file(unit_path, max_bytes=256 * 1024)
        or payload.get("endpoint") != OBSERVER_HEALTH_ENDPOINT
        or payload.get("consecutive_successes") != OBSERVER_HEALTH_SUCCESS_COUNT
        or payload.get("dispatch_enabled_during_probe") is not False
        or payload.get("observer_identity_separated") is not True
        or payload.get("projection_source_separated") is not True
        or payload.get("canonical_paths_inaccessible") is not True
        or payload.get("health_is_work_evidence") is not False
        or payload.get("verdict") != "PASS"
    ):
        raise ReleaseContractError("observer health receipt binding differs")
    hashes = payload.get("response_sha256_sequence")
    if (
        not isinstance(hashes, list)
        or len(hashes) != OBSERVER_HEALTH_SUCCESS_COUNT
        or any(not isinstance(item, str) or not _SHA_RE.fullmatch(item) for item in hashes)
    ):
        raise ReleaseContractError("observer health response ledger differs")
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ReleaseContractError("observer health validation clock must be aware")
    finished = _parse_utc(str(payload.get("probe_finished_at", "")), "probe_finished_at")
    started = _parse_utc(str(payload.get("probe_started_at", "")), "probe_started_at")
    observed = observed.astimezone(timezone.utc)
    if finished < started or observed < finished or observed - finished > timedelta(minutes=10):
        raise ReleaseContractError("observer health receipt is not fresh")
    if _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0:
        raise ReleaseContractError("dispatch process exists before enablement")
    if payload.get("listener_process_identity") != _observer_listener_identity(
        release_sha=release_sha,
        runner=runner,
        proc_root=proc_root,
    ):
        raise ReleaseContractError("observer health listener changed before enablement")
    return payload


def _receipt_file_custody(path: Path, *, expected_uid: int, expected_gid: int) -> dict[str, Any]:
    identity = path.lstat()
    if (
        path.is_symlink()
        or not stat.S_ISREG(identity.st_mode)
        or identity.st_uid != expected_uid
        or identity.st_gid != expected_gid
        or stat.S_IMODE(identity.st_mode) != 0o600
        or identity.st_nlink != 1
        or not 0 < identity.st_size <= 64 * 1024
    ):
        raise ReleaseContractError("credential receipt custody differs")
    return {
        "uid": identity.st_uid,
        "gid": identity.st_gid,
        "mode": "0600",
        "nlink": identity.st_nlink,
        "regular": True,
    }


def _account_ui_field_types_exact(
    payload: Mapping[str, Any],
    *,
    additional_boolean_fields: tuple[str, ...] = (),
) -> bool:
    width_fields = (
        "viewport_width_css_px_reported",
        "document_width_css_px_reported",
        "visual_viewport_width_css_px_reported",
    )
    boolean_fields = (
        "coarse_pointer_reported",
        "touch_capability_reported",
        "trusted_browser_event_reported",
        "explicit_confirmation_gesture_reported",
        "dashboard_rendered_reported",
        "private_tailnet_https",
        "identity_header_injected",
        "operator_account_allowlist_match",
        "normal_control_request_sent",
        "external_message_sent",
        "physical_device_attested",
        "human_identity_attested",
        *additional_boolean_fields,
    )
    return all(type(payload.get(field)) is int for field in width_fields) and all(
        type(payload.get(field)) is bool for field in boolean_fields
    )


def _validate_account_ui_confirmation_payload(
    payload: Mapping[str, Any],
    *,
    release_sha: str,
    now: datetime,
    operator_login_sha256: str,
) -> dict[str, Any]:
    exact = {
        "schema_version": ACCOUNT_UI_CONFIRMATION_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "viewport_width_css_px_reported": 390,
        "document_width_css_px_reported": 390,
        "visual_viewport_width_css_px_reported": 390,
        "coarse_pointer_reported": True,
        "touch_capability_reported": True,
        "trusted_browser_event_reported": True,
        "explicit_confirmation_gesture_reported": True,
        "dashboard_rendered_reported": True,
        "private_tailnet_https": True,
        "identity_header_injected": True,
        "operator_account_allowlist_match": True,
        "operator_login_sha256": operator_login_sha256,
        "normal_control_request_sent": False,
        "external_message_sent": False,
        "physical_device_attested": False,
        "human_identity_attested": False,
        "normal_and_emergency_inboxes_unchanged": True,
    }
    if (
        set(payload) != _ACCOUNT_UI_CONFIRMATION_FIELDS
        or any(payload.get(key) != value for key, value in exact.items())
        or not _account_ui_field_types_exact(
            payload,
            additional_boolean_fields=(
                "normal_and_emergency_inboxes_unchanged",
            ),
        )
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(payload.get("client_request_id_sha256", ""))
        )
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(payload.get("source_candidate_sha256", ""))
        )
        or not re.fullmatch(
            r"sha256:[0-9a-f]{64}",
            str(payload.get("predispatch_gate_receipt_digest", "")),
        )
        or not re.fullmatch(
            r"sha256:[0-9a-f]{64}",
            str(
                payload.get(
                    "normal_and_emergency_inbox_ledger_sha256_before", ""
                )
            ),
        )
        or payload.get("normal_and_emergency_inbox_ledger_sha256_before")
        != payload.get("normal_and_emergency_inbox_ledger_sha256_after")
        or payload.get("normal_and_emergency_inbox_ledger_sha256_before")
        != _empty_account_ui_inbox_ledger_sha256()
        or payload.get("receipt_digest")
        != _canonical_self_digest(payload, "receipt_digest")
    ):
        raise ReleaseContractError("account UI confirmation binding differs")
    observed_at = _parse_utc(str(payload.get("observed_at", "")), "observed_at")
    if now < observed_at or now - observed_at > timedelta(minutes=10):
        raise ReleaseContractError("account UI confirmation is not fresh")
    return dict(payload)


def _read_account_ui_confirmation(
    path: Path,
    *,
    release_sha: str,
    now: datetime,
    expected_root_uid: int,
    expected_root_gid: int,
    operator_login_sha256: str,
) -> dict[str, Any]:
    if path != ACCOUNT_UI_CONFIRMATION_RECEIPT:
        raise ReleaseContractError("account UI confirmation path differs")
    payload, _raw, _identity = _read_exact_canonical_json(
        path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=ACCOUNT_UI_CONFIRMATION_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    return _validate_account_ui_confirmation_payload(
        payload,
        release_sha=release_sha,
        now=now,
        operator_login_sha256=operator_login_sha256,
    )


def _account_ui_candidate_mac(payload: Mapping[str, Any], secret: bytes) -> str:
    unsigned = dict(payload)
    unsigned.pop("hmac_sha256", None)
    derived_key = hmac.new(
        secret,
        ACCOUNT_UI_CONFIRMATION_KEY_DOMAIN,
        hashlib.sha256,
    ).digest()
    return "hmac-sha256:" + hmac.new(
        derived_key,
        ACCOUNT_UI_CONFIRMATION_MAC_DOMAIN + _canonical_bytes(unsigned),
        hashlib.sha256,
    ).hexdigest()


def _empty_account_ui_inbox_ledger_sha256() -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes({"rows": []})).hexdigest()


def _read_account_ui_candidate(
    *,
    control_uid: int,
    control_gid: int,
    frozen: bool,
    expected_root_uid: int,
    expected_root_gid: int,
) -> tuple[dict[str, Any], bytes, os.stat_result, os.stat_result]:
    """Stable-read only the fixed one-shot candidate through its exact parent."""
    path = ACCOUNT_UI_CONFIRMATION_CANDIDATE
    directory = ACCOUNT_UI_CONFIRMATION_ROOT
    if path.parent != directory or path.name != "candidate.v2.json":
        raise ReleaseContractError("account UI candidate path differs")
    expected_directory = (
        (expected_root_uid, expected_root_gid, 0o700)
        if frozen
        else (expected_root_uid, control_gid, 0o770)
    )
    expected_file = (
        (expected_root_uid, expected_root_gid, 0o400)
        if frozen
        else (control_uid, control_gid, 0o600)
    )
    try:
        directory_identity = directory.lstat()
    except OSError as exc:
        raise ReleaseContractError("account UI candidate directory unavailable") from exc
    if (
        directory.is_symlink()
        or not stat.S_ISDIR(directory_identity.st_mode)
        or (
            directory_identity.st_uid,
            directory_identity.st_gid,
            stat.S_IMODE(directory_identity.st_mode),
        )
        != expected_directory
    ):
        raise ReleaseContractError("account UI candidate directory custody differs")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ReleaseContractError("platform lacks account UI no-follow admission")
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | nofollow)
    try:
        opened_directory = os.fstat(directory_fd)
        if (
            opened_directory.st_dev != directory_identity.st_dev
            or opened_directory.st_ino != directory_identity.st_ino
        ):
            raise ReleaseContractError("account UI candidate directory changed")
        try:
            identity = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
            descriptor = os.open(path.name, os.O_RDONLY | nofollow, dir_fd=directory_fd)
        except OSError as exc:
            raise ReleaseContractError("account UI candidate unavailable") from exc
        try:
            before = os.fstat(descriptor)
            if (
                not stat.S_ISREG(identity.st_mode)
                or (
                    identity.st_uid,
                    identity.st_gid,
                    stat.S_IMODE(identity.st_mode),
                )
                != expected_file
                or identity.st_nlink != 1
                or not 0 < identity.st_size <= 64 * 1024
                or (
                    before.st_dev,
                    before.st_ino,
                    before.st_uid,
                    before.st_gid,
                    before.st_mode,
                    before.st_nlink,
                    before.st_size,
                    before.st_mtime_ns,
                    before.st_ctime_ns,
                )
                != (
                    identity.st_dev,
                    identity.st_ino,
                    identity.st_uid,
                    identity.st_gid,
                    identity.st_mode,
                    identity.st_nlink,
                    identity.st_size,
                    identity.st_mtime_ns,
                    identity.st_ctime_ns,
                )
            ):
                raise ReleaseContractError("account UI candidate custody differs")
            raw = os.read(descriptor, 64 * 1024 + 1)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        directory_after = os.fstat(directory_fd)
    finally:
        os.close(directory_fd)
    if (
        len(raw) != identity.st_size
        or (
            after.st_dev,
            after.st_ino,
            after.st_uid,
            after.st_gid,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        != (
            before.st_dev,
            before.st_ino,
            before.st_uid,
            before.st_gid,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        or (
            directory_after.st_dev,
            directory_after.st_ino,
            directory_after.st_uid,
            directory_after.st_gid,
            directory_after.st_mode,
            directory_after.st_mtime_ns,
            directory_after.st_ctime_ns,
        )
        != (
            opened_directory.st_dev,
            opened_directory.st_ino,
            opened_directory.st_uid,
            opened_directory.st_gid,
            opened_directory.st_mode,
            opened_directory.st_mtime_ns,
            opened_directory.st_ctime_ns,
        )
    ):
        raise ReleaseContractError("account UI candidate changed during read")
    try:
        payload = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseContractError("account UI candidate JSON is invalid") from exc
    if not isinstance(payload, dict) or raw != _canonical_bytes(payload) + b"\n":
        raise ReleaseContractError("account UI candidate JSON is noncanonical")
    return payload, raw, identity, directory_identity


def _load_predispatch_account_ui_gate(
    *,
    release_sha: str,
    control_gid: int,
    expected_root_uid: int,
    expected_root_gid: int,
) -> dict[str, Any]:
    payload, _raw, _identity = _read_exact_custodied_json(
        PREDISPATCH_ACCOUNT_UI_GATE,
        expected_uid=expected_root_uid,
        expected_gid=control_gid,
        expected_mode=0o640,
    )
    if (
        set(payload) != _PREDISPATCH_ACCOUNT_UI_GATE_FIELDS
        or payload.get("schema_version")
        != PREDISPATCH_ACCOUNT_UI_GATE_SCHEMA_VERSION
        or payload.get("campaign_id") != MISSION_ID
        or payload.get("release_sha") != release_sha
        or payload.get("dispatch_marker_absent") is not True
        or payload.get("dispatch_target_inactive") is not True
        or payload.get("supervisor_main_pid") != 0
        or payload.get("provider_dispatch") != "NoProviderDispatch"
        or payload.get("receipt_digest")
        != _canonical_self_digest(payload, "receipt_digest")
    ):
        raise ReleaseContractError("account UI predispatch gate differs")
    activation, _raw, _identity = _read_exact_canonical_json(
        PREDISPATCH_ACTIVATION_RECEIPT,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=PREDISPATCH_ACTIVATION_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    if (
        set(activation) != _PREDISPATCH_ACTIVATION_FIELDS
        or activation.get("campaign_id") != MISSION_ID
        or activation.get("release_sha") != release_sha
        or activation.get("provider_dispatch") != "NoProviderDispatch"
        or activation.get("dispatch_marker_absent") is not True
        or activation.get("dispatch_target_inactive") is not True
        or activation.get("supervisor_main_pid") != 0
        or payload.get("predispatch_activation_receipt_digest")
        != activation.get("receipt_digest")
    ):
        raise ReleaseContractError("account UI gate activation binding differs")
    return payload


def _require_account_ui_predispatch_fences(
    *,
    role: str,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    observed_node: str | None,
    expected_root_uid: int,
    expected_root_gid: int,
) -> None:
    guard_campaign_clock(role=role, observed_node=observed_node)
    if (
        role != "writer"
        or not _COMMIT_RE.fullmatch(release_sha)
        or DISPATCH_ENABLE_MARKER.exists()
        or DISPATCH_ENABLE_MARKER.is_symlink()
        or ROLLBACK_RECEIPT.exists()
        or ROLLBACK_RECEIPT.is_symlink()
        or EMERGENCY_STOP_MARKER.exists()
        or EMERGENCY_STOP_MARKER.is_symlink()
        or CAMPAIGN_ACTIVATION_PROOF.exists()
        or CAMPAIGN_ACTIVATION_PROOF.is_symlink()
        or not _unit_inactive(DISPATCH_TARGET, runner=runner)
        or _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0
    ):
        raise ReleaseContractError("account UI confirmation is not predispatch")
    _predispatch_live_state(
        runner=runner,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )


def _freeze_account_ui_candidate(
    *,
    control_uid: int,
    control_gid: int,
    expected_root_uid: int,
    expected_root_gid: int,
) -> None:
    payload, raw, identity, directory_identity = _read_account_ui_candidate(
        control_uid=control_uid,
        control_gid=control_gid,
        frozen=False,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    del payload
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_fd = os.open(
        ACCOUNT_UI_CONFIRMATION_ROOT,
        os.O_RDONLY | os.O_DIRECTORY | nofollow,
    )
    try:
        opened_directory = os.fstat(directory_fd)
        if (opened_directory.st_dev, opened_directory.st_ino) != (
            directory_identity.st_dev,
            directory_identity.st_ino,
        ):
            raise ReleaseContractError("account UI candidate directory changed")
        descriptor = os.open(
            ACCOUNT_UI_CONFIRMATION_CANDIDATE.name,
            os.O_RDONLY | nofollow,
            dir_fd=directory_fd,
        )
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (identity.st_dev, identity.st_ino):
                raise ReleaseContractError("account UI candidate changed before freeze")
            # Seal traversal/unlink authority first. Any later failure leaves a
            # root-only parent that runtime preparation must refuse to reopen.
            os.fchown(directory_fd, expected_root_uid, expected_root_gid)
            os.fchmod(directory_fd, 0o700)
            os.fsync(directory_fd)
            os.fchown(descriptor, expected_root_uid, expected_root_gid)
            os.fchmod(descriptor, 0o400)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        os.close(directory_fd)
    _payload, frozen_raw, _identity, _directory = _read_account_ui_candidate(
        control_uid=control_uid,
        control_gid=control_gid,
        frozen=True,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if not hmac.compare_digest(raw, frozen_raw):
        raise ReleaseContractError("account UI candidate changed during freeze")


def consume_account_ui_confirmation(
    *,
    role: str,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    now: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
    before_publish: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Promote only the fixed authenticated-account UI candidate; no booleans/paths."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("account UI confirmation import requires root")
    _require_host_role(role, observed_node=observed_node)
    observed = _sample_utc(now=now, clock=clock, label="account UI confirmation")
    operator_login_raw = _read_control_credential(
        CONTROL_LOGIN_SOURCE,
        expected_root_uid=expected_root_uid,
        minimum_bytes=1,
        maximum_bytes=254,
    )
    operator_login_sha256 = hashlib.sha256(operator_login_raw).hexdigest()
    if ACCOUNT_UI_CONFIRMATION_RECEIPT.exists() or ACCOUNT_UI_CONFIRMATION_RECEIPT.is_symlink():
        _require_account_ui_predispatch_fences(
            role=role,
            release_sha=release_sha,
            runner=runner,
            observed_node=observed_node,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        return _read_account_ui_confirmation(
            ACCOUNT_UI_CONFIRMATION_RECEIPT,
            release_sha=release_sha,
            now=observed,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
            operator_login_sha256=operator_login_sha256,
        )
    _require_account_ui_predispatch_fences(
        role=role,
        release_sha=release_sha,
        runner=runner,
        observed_node=observed_node,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    try:
        control = pwd.getpwnam("dharma-sadhana-control")
    except KeyError as exc:
        raise ReleaseContractError("control service identity is absent") from exc
    gate = _load_predispatch_account_ui_gate(
        release_sha=release_sha,
        control_gid=control.pw_gid,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    inbox_ledger_before = _control_inbox_ledger(
        expected_root_uid=expected_root_uid,
        expected_control_gid=control.pw_gid,
    )
    if inbox_ledger_before:
        raise ReleaseContractError("account UI confirmation found a control request")
    candidate, candidate_raw, _identity, _directory = _read_account_ui_candidate(
        control_uid=control.pw_uid,
        control_gid=control.pw_gid,
        frozen=False,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    hmac_secret = _read_control_credential(
        CONTROL_HMAC_SOURCE,
        expected_root_uid=expected_root_uid,
        textual=False,
    )
    expected = {
        "schema_version": ACCOUNT_UI_CONFIRMATION_CANDIDATE_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "origin": _control_expected_origin(),
        "operator_login_sha256": operator_login_sha256,
        "viewport_width_css_px_reported": 390,
        "document_width_css_px_reported": 390,
        "visual_viewport_width_css_px_reported": 390,
        "coarse_pointer_reported": True,
        "touch_capability_reported": True,
        "trusted_browser_event_reported": True,
        "explicit_confirmation_gesture_reported": True,
        "dashboard_rendered_reported": True,
        "private_tailnet_https": True,
        "identity_header_injected": True,
        "operator_account_allowlist_match": True,
        "normal_control_request_sent": False,
        "external_message_sent": False,
        "physical_device_attested": False,
        "human_identity_attested": False,
        "predispatch_gate_receipt_digest": gate["receipt_digest"],
        "control_inboxes_empty_at_last_prepublication_scan": True,
    }
    issued = _parse_utc(str(candidate.get("issued_at", "")), "issued_at")
    expires = _parse_utc(str(candidate.get("expires_at", "")), "expires_at")
    candidate_observed = _parse_utc(
        str(candidate.get("observed_at", "")), "observed_at"
    )
    request_id = candidate.get("client_request_id")
    if (
        set(candidate) != _ACCOUNT_UI_CONFIRMATION_CANDIDATE_FIELDS
        or any(candidate.get(key) != value for key, value in expected.items())
        or not _account_ui_field_types_exact(
            candidate,
            additional_boolean_fields=(
                "control_inboxes_empty_at_last_prepublication_scan",
            ),
        )
        or not isinstance(request_id, str)
        or re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            request_id,
        )
        is None
        or expires - issued != timedelta(seconds=90)
        or issued > candidate_observed + timedelta(seconds=15)
        or candidate_observed < issued - timedelta(seconds=60)
        or observed < candidate_observed
        or observed >= expires
        or observed - candidate_observed > timedelta(seconds=90)
        or candidate.get("hmac_sha256")
        != _account_ui_candidate_mac(candidate, hmac_secret)
        or any(
            re.fullmatch(
                r"sha256:[0-9a-f]{64}",
                str(candidate.get(field, "")),
            )
            is None
            for field in (
                "normal_inbox_empty_ledger_sha256",
                "emergency_inbox_empty_ledger_sha256",
            )
        )
        or candidate.get("normal_inbox_empty_ledger_sha256")
        != _empty_account_ui_inbox_ledger_sha256()
        or candidate.get("emergency_inbox_empty_ledger_sha256")
        != _empty_account_ui_inbox_ledger_sha256()
    ):
        raise ReleaseContractError("account UI candidate binding differs")
    if before_publish is not None:
        before_publish()
    observed = _sample_utc(now=now, clock=clock, label="account UI publication")
    _require_account_ui_predispatch_fences(
        role=role,
        release_sha=release_sha,
        runner=runner,
        observed_node=observed_node,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    refreshed_gate = _load_predispatch_account_ui_gate(
        release_sha=release_sha,
        control_gid=control.pw_gid,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if refreshed_gate["receipt_digest"] != gate["receipt_digest"]:
        raise ReleaseContractError("account UI predispatch gate changed")
    if observed >= expires or observed - candidate_observed > timedelta(seconds=90):
        raise ReleaseContractError("account UI candidate expired before publication")
    _freeze_account_ui_candidate(
        control_uid=control.pw_uid,
        control_gid=control.pw_gid,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    observed = _sample_utc(
        now=now,
        clock=clock,
        label="account UI post-freeze publication",
    )
    _require_account_ui_predispatch_fences(
        role=role,
        release_sha=release_sha,
        runner=runner,
        observed_node=observed_node,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    final_gate = _load_predispatch_account_ui_gate(
        release_sha=release_sha,
        control_gid=control.pw_gid,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if final_gate["receipt_digest"] != gate["receipt_digest"]:
        raise ReleaseContractError("account UI gate changed after candidate freeze")
    if observed >= expires or observed - candidate_observed > timedelta(seconds=90):
        raise ReleaseContractError("account UI candidate expired after freeze")
    inbox_ledger_after = _control_inbox_ledger(
        expected_root_uid=expected_root_uid,
        expected_control_gid=control.pw_gid,
    )
    if inbox_ledger_after != inbox_ledger_before or inbox_ledger_after:
        raise ReleaseContractError("control inbox changed during account UI import")
    inbox_ledger_digest = "sha256:" + hashlib.sha256(
        _canonical_bytes({"rows": inbox_ledger_before})
    ).hexdigest()
    payload: dict[str, Any] = {
        "schema_version": ACCOUNT_UI_CONFIRMATION_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "client_request_id_sha256": hashlib.sha256(request_id.encode("ascii")).hexdigest(),
        "source_candidate_sha256": hashlib.sha256(candidate_raw).hexdigest(),
        "viewport_width_css_px_reported": 390,
        "document_width_css_px_reported": 390,
        "visual_viewport_width_css_px_reported": 390,
        "coarse_pointer_reported": True,
        "touch_capability_reported": True,
        "trusted_browser_event_reported": True,
        "explicit_confirmation_gesture_reported": True,
        "dashboard_rendered_reported": True,
        "private_tailnet_https": True,
        "identity_header_injected": True,
        "operator_account_allowlist_match": True,
        "operator_login_sha256": operator_login_sha256,
        "normal_control_request_sent": False,
        "external_message_sent": False,
        "physical_device_attested": False,
        "human_identity_attested": False,
        "predispatch_gate_receipt_digest": gate["receipt_digest"],
        "normal_and_emergency_inbox_ledger_sha256_before": inbox_ledger_digest,
        "normal_and_emergency_inbox_ledger_sha256_after": inbox_ledger_digest,
        "normal_and_emergency_inboxes_unchanged": True,
        "observed_at": candidate["observed_at"],
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    if set(payload) != _ACCOUNT_UI_CONFIRMATION_FIELDS:
        raise ReleaseContractError("account UI confirmation fields differ")
    return _publish_or_replay_private_receipt(
        ACCOUNT_UI_CONFIRMATION_RECEIPT,
        payload,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )


def _default_principal_access_probe(
    label: str,
    *,
    uid: int,
    gid: int,
    target: Path,
    release_sha: str,
    kind: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> bool:
    if uid <= 0 or gid <= 0 or kind not in {"file", "unix"} or not label:
        raise ReleaseContractError("negative access probe identity differs")
    helper = (
        Path(RELEASE_ROOT)
        / release_sha
        / ".venv/bin/python"
    )
    script = Path(RELEASE_ROOT) / release_sha / "scripts/runtime/sadhana_release.py"
    result = runner(
        (
            SETPRIV_PATH,
            "--reuid",
            str(uid),
            "--regid",
            str(gid),
            "--clear-groups",
            "--no-new-privs",
            str(helper),
            str(script),
            "probe-denied-access",
            "--kind",
            kind,
            "--path",
            str(target),
        ),
        cwd=Path("/"),
        check=False,
    )
    if result.stdout or result.stderr:
        raise ReleaseContractError("negative access probe emitted output")
    return result.returncode == 0


def probe_denied_access(*, kind: str, path: Path) -> None:
    """Exit cleanly only when an unprivileged helper cannot reach the target."""
    if kind == "file":
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except PermissionError:
            return
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EPERM}:
                return
            raise ReleaseContractError("credential denial probe failed") from exc
        else:
            os.close(descriptor)
            raise ReleaseContractError("forbidden principal read a credential")
    if kind != "unix" or path != DASHBOARD_SOCKET_PATH:
        raise ReleaseContractError("negative access probe target differs")
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        probe.settimeout(1.0)
        probe.connect(str(path))
    except PermissionError:
        return
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EPERM}:
            return
        raise ReleaseContractError("dashboard denial probe failed") from exc
    finally:
        probe.close()
    raise ReleaseContractError("forbidden principal reached dashboard ingress")


def perform_dashboard_rollback_probe(
    *,
    role: str,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    receipt_path: Path = DASHBOARD_ROLLBACK_RECEIPT,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Exercise only the owned dashboard/Serve rollback while dispatch is absent."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("dashboard rollback probe requires root")
    _require_host_role(role, observed_node=observed_node)
    if role != "writer" or not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("dashboard rollback binding differs")
    if _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0:
        raise ReleaseContractError("dashboard rollback cannot run after dispatch")
    before = _validate_owned_tailscale_config(_read_tailscale_status(runner=runner))
    ownership = _load_tailscale_ownership_receipt(
        TAILSCALE_OWNERSHIP_RECEIPT,
        release_sha=release_sha,
    )
    if ownership["config_sha256"] != _tailscale_config_digest(before):
        raise ReleaseContractError("dashboard rollback ownership differs")
    for unit in ("dharma-sadhana-private-serve.service", DASHBOARD_UNIT):
        result = runner((SYSTEMCTL_PATH, "stop", unit), cwd=Path("/"), check=False)
        if result.returncode != 0:
            raise ReleaseContractError("dashboard rollback stop failed")
    if _dashboard_socket_is_live(DASHBOARD_SOCKET_PATH):
        raise ReleaseContractError("dashboard socket remained reachable after rollback")
    _require_empty_tailscale_serve(runner=runner)
    for unit in (DASHBOARD_UNIT, "dharma-sadhana-private-serve.service"):
        result = runner((SYSTEMCTL_PATH, "start", unit), cwd=Path("/"), check=False)
        if result.returncode != 0:
            raise ReleaseContractError("dashboard rollback restart failed")
    _wait_for_dashboard_ingress(release_sha=release_sha, runner=runner)
    after = _validate_owned_tailscale_config(_read_tailscale_status(runner=runner))
    if _canonical_bytes(after) != _canonical_bytes(before):
        raise ReleaseContractError("dashboard route changed across rollback")
    payload: dict[str, Any] = {
        "schema_version": DASHBOARD_ROLLBACK_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "owned_route_removed": True,
        "socket_unreachable_while_stopped": True,
        "foreign_route_changed": False,
        "dashboard_restarted": True,
        "owned_route_restored": True,
        "supervisor_main_pid": 0,
        "verdict": "PASS",
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    return _publish_or_replay_private_receipt(
        receipt_path,
        payload,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )


def _listener_count(port: int, *, proc_net_root: Path = Path("/proc/net")) -> int:
    if not 1 <= port <= 65535:
        raise ReleaseContractError("listener inventory port differs")
    count = 0
    for name in ("tcp", "tcp6"):
        try:
            raw = (proc_net_root / name).read_text(encoding="ascii")
        except OSError as exc:
            raise ReleaseContractError("cannot inspect listener inventory") from exc
        for line in raw.splitlines()[1:]:
            fields = line.split()
            if len(fields) < 4 or fields[3] != "0A":
                continue
            try:
                observed = int(fields[1].rsplit(":", maxsplit=1)[1], 16)
            except (IndexError, ValueError) as exc:
                raise ReleaseContractError("listener inventory differs") from exc
            count += int(observed == port)
    return count


def record_dashboard_identity_acceptance(
    *,
    role: str,
    release_sha: str,
    receipt_path: Path = DASHBOARD_IDENTITY_RECEIPT,
    rollback_receipt_path: Path = DASHBOARD_ROLLBACK_RECEIPT,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    proc_root: Path = Path("/proc"),
    proc_net_root: Path = Path("/proc/net"),
    now: datetime | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
    access_probe: Callable[..., bool] = _default_principal_access_probe,
) -> dict[str, Any]:
    """Seal v5 UDS identity plus bounded authenticated-account UI evidence."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("dashboard identity acceptance requires root")
    _require_host_role(role, observed_node=observed_node)
    if role != "writer" or not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("dashboard identity release binding differs")
    guard_campaign_clock(role=role, observed_node=observed_node)
    if _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0:
        raise ReleaseContractError("dashboard identity proof cannot run after dispatch")
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ReleaseContractError("dashboard identity clock must be aware")
    observed = observed.astimezone(timezone.utc)
    dashboard_unit = SYSTEMD_OUTPUT_ROOT / DASHBOARD_UNIT
    dashboard_unit_digest = sha256_file(dashboard_unit, max_bytes=256 * 1024)
    identity = _dashboard_listener_identity(
        release_sha=release_sha,
        runner=runner,
        proc_root=proc_root,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if set(identity) != _DASHBOARD_PROCESS_FIELDS:
        raise ReleaseContractError("dashboard process receipt fields differ")
    _require_tailscale_version(runner=runner)
    status = _validate_owned_tailscale_config(_read_tailscale_status(runner=runner))
    ownership = _load_tailscale_ownership_receipt(
        TAILSCALE_OWNERSHIP_RECEIPT,
        release_sha=release_sha,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if ownership["config_sha256"] != _tailscale_config_digest(status):
        raise ReleaseContractError("dashboard Serve ownership differs")
    rollback, _rollback_raw, _rollback_identity = _read_exact_canonical_json(
        rollback_receipt_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=DASHBOARD_ROLLBACK_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    if (
        rollback.get("campaign_id") != MISSION_ID
        or rollback.get("release_sha") != release_sha
        or rollback.get("verdict") != "PASS"
        or rollback.get("supervisor_main_pid") != 0
    ):
        raise ReleaseContractError("dashboard rollback receipt binding differs")
    operator_login_raw = _read_control_credential(
        CONTROL_LOGIN_SOURCE,
        expected_root_uid=expected_root_uid,
        minimum_bytes=1,
        maximum_bytes=254,
    )
    operator_login_sha256 = hashlib.sha256(operator_login_raw).hexdigest()
    account_confirmation = _read_account_ui_confirmation(
        ACCOUNT_UI_CONFIRMATION_RECEIPT,
        release_sha=release_sha,
        now=observed,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
        operator_login_sha256=operator_login_sha256,
    )
    service = _require_static_service_identity()
    principals: dict[str, pwd.struct_passwd] = {}
    for label, name in (
        ("supervisor", service.pw_name),
        ("observer", OBSERVER_ACCOUNT_NAME),
        ("control", "dharma-sadhana-control"),
        ("build", BUILD_ACCOUNT_NAME),
        ("oracle", ORACLE_ACCOUNT_NAME),
        ("unrelated", "nobody"),
    ):
        try:
            principals[label] = pwd.getpwnam(name)
        except KeyError as exc:
            raise ReleaseContractError("dashboard negative identity is absent") from exc
    negative: dict[str, bool] = {}
    for label, account in principals.items():
        negative[label] = access_probe(
            label,
            uid=account.pw_uid,
            gid=account.pw_gid,
            target=DASHBOARD_SOCKET_PATH,
            release_sha=release_sha,
            kind="unix",
            runner=runner,
        )
    if set(negative) != set(principals) or not all(negative.values()):
        raise ReleaseContractError("dashboard negative access matrix differs")
    port_3000 = _listener_count(3000, proc_net_root=proc_net_root)
    if port_3000 != 0 or identity["tcp_listener_count"] != 0:
        raise ReleaseContractError("dashboard TCP bypass exists")
    payload: dict[str, Any] = {
        "schema_version": DASHBOARD_IDENTITY_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "dashboard_unit_digest": dashboard_unit_digest,
        "tailscale_version": TAILSCALE_VERSION,
        "serve_status_before_sha256": ownership["serve_status_before_sha256"],
        "serve_status_after_sha256": _tailscale_config_digest(status),
        "serve_upstream": TAILSCALE_ROUTE,
        "socket_stat": {
            "path": identity["socket_path"],
            "uid": identity["uid"],
            "gid": identity["gid"],
            "mode": "0600",
            "dev": identity["socket_dev"],
            "ino": identity["socket_ino"],
        },
        "dashboard_process_identity": identity,
        "negative_access_matrix": negative,
        "tcp_listener_inventory": {
            "dashboard_process": identity["tcp_listener_count"],
            "host_port_3000": port_3000,
        },
        "funnel_absence": True,
        "operator_login_sha256": operator_login_sha256,
        "authenticated_account_ui_confirmation": account_confirmation,
        "rollback_probe": rollback,
        "verdict": "PASS",
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    if set(payload) != _DASHBOARD_IDENTITY_RECEIPT_FIELDS:
        raise ReleaseContractError("dashboard identity receipt fields differ")
    return _publish_or_replay_private_receipt(
        receipt_path,
        payload,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )


def _credential_copy_bytes(
    path: Path,
    *,
    expected_root_uid: int,
    expected_root_gid: int,
) -> tuple[bytes, dict[str, Any]]:
    identity = path.lstat()
    if (
        path.is_symlink()
        or not stat.S_ISREG(identity.st_mode)
        or identity.st_uid != expected_root_uid
        or identity.st_gid != expected_root_gid
        or stat.S_IMODE(identity.st_mode) != 0o400
        or identity.st_nlink != 1
        or not 32 <= identity.st_size <= 512
    ):
        raise ReleaseContractError("systemd credential copy custody differs")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(descriptor)
        raw = os.read(descriptor, 513)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        len(raw) != identity.st_size
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or any(byte < 0x21 or byte > 0x7E for byte in raw)
    ):
        raise ReleaseContractError("systemd credential copy changed during read")
    return raw, {
        "uid": identity.st_uid,
        "gid": identity.st_gid,
        "mode": "0400",
        "nlink": identity.st_nlink,
        "regular": True,
    }


def _read_supervisor_credential_bytes(
    path: Path,
    *,
    credential_root: Path,
    expected_name: str,
    expected_uid: int,
    expected_gid: int,
    minimum_bytes: int = 1,
    maximum_bytes: int = _MAX_JSON_BYTES,
) -> bytes:
    """Stable-read one exact systemd credential as the supervisor user."""
    if (
        not path.is_absolute()
        or not credential_root.is_absolute()
        or path != credential_root / expected_name
        or not 0 < minimum_bytes <= maximum_bytes <= _MAX_ARTIFACT_BYTES
    ):
        raise ReleaseContractError("supervisor credential path differs")
    _require_secure_parent_chain(path)
    try:
        root_identity = credential_root.lstat()
        identity = path.lstat()
    except OSError as exc:
        raise ReleaseContractError("supervisor credential is unavailable") from exc
    if (
        credential_root.is_symlink()
        or not stat.S_ISDIR(root_identity.st_mode)
        or root_identity.st_uid not in {0, expected_uid}
        or stat.S_IMODE(root_identity.st_mode) not in {0o500, 0o700}
        or path.is_symlink()
        or not stat.S_ISREG(identity.st_mode)
        or identity.st_uid not in {0, expected_uid}
        or identity.st_gid not in {0, expected_gid}
        or stat.S_IMODE(identity.st_mode) not in {0o400, 0o600}
        or identity.st_nlink != 1
        or not minimum_bytes <= identity.st_size <= maximum_bytes
    ):
        raise ReleaseContractError("supervisor credential custody differs")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ReleaseContractError("platform lacks no-follow credential admission")
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        before = os.fstat(descriptor)
        raw = b""
        while len(raw) <= maximum_bytes:
            chunk = os.read(
                descriptor,
                min(65_536, maximum_bytes + 1 - len(raw)),
            )
            if not chunk:
                break
            raw += chunk
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    stable = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    if (
        stable
        != (
            identity.st_dev,
            identity.st_ino,
            identity.st_size,
            identity.st_mtime_ns,
        )
        or stable
        != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        or len(raw) != identity.st_size
        or not minimum_bytes <= len(raw) <= maximum_bytes
    ):
        raise ReleaseContractError("supervisor credential changed during read")
    return raw


def _read_supervisor_json_credential(
    path: Path,
    *,
    credential_root: Path,
    expected_name: str,
    expected_uid: int,
    expected_gid: int,
    expected_schema: str,
) -> dict[str, Any]:
    raw = _read_supervisor_credential_bytes(
        path,
        credential_root=credential_root,
        expected_name=expected_name,
        expected_uid=expected_uid,
        expected_gid=expected_gid,
    )
    try:
        payload = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseContractError("supervisor JSON credential is invalid") from exc
    if (
        not isinstance(payload, dict)
        or raw != _canonical_bytes(payload) + b"\n"
        or payload.get("schema_version") != expected_schema
        or payload.get("receipt_digest")
        != _canonical_self_digest(payload, "receipt_digest")
    ):
        raise ReleaseContractError("supervisor JSON credential differs")
    return payload


def _operator_bearer_triplet(
    *,
    source_path: Path,
    dashboard_copy: Path,
    control_copy: Path,
    expected_root_uid: int,
    expected_root_gid: int,
) -> dict[str, Any]:
    """Read one stable source/copy set and prove both equal without short circuit."""
    source = _read_control_credential(
        source_path,
        expected_root_uid=expected_root_uid,
        minimum_bytes=32,
        maximum_bytes=512,
    )
    dashboard_raw, dashboard_custody = _credential_copy_bytes(
        dashboard_copy,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    control_raw, control_custody = _credential_copy_bytes(
        control_copy,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    dashboard_equal = hmac.compare_digest(source, dashboard_raw)
    control_equal = hmac.compare_digest(source, control_raw)
    if not (dashboard_equal & control_equal):
        raise ReleaseContractError("operator bearer credential copies differ")
    return {
        "source": source,
        "dashboard": dashboard_raw,
        "control": control_raw,
        "source_custody": _receipt_file_custody(
            source_path,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
        ),
        "dashboard_custody": dashboard_custody,
        "control_custody": control_custody,
    }


def _control_credential_source_inventory(
    root: Path,
    *,
    expected_root_uid: int,
    expected_root_gid: int,
    hmac_masked: bool,
) -> tuple[str, ...]:
    """Admit exact names plus either source or systemd-masked HMAC custody."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    if not getattr(os, "O_DIRECTORY", 0) or not getattr(os, "O_NOFOLLOW", 0):
        raise ReleaseContractError("platform lacks no-follow credential inventory")
    descriptor = os.open(root, flags)
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(before.st_mode)
            or before.st_uid != expected_root_uid
            or before.st_gid != expected_root_gid
            or stat.S_IMODE(before.st_mode) != 0o700
        ):
            raise ReleaseContractError("control credential root custody differs")
        names = tuple(sorted(os.listdir(descriptor), key=os.fsencode))
        if names != tuple(sorted(CONTROL_CREDENTIAL_DESTINATIONS)):
            raise ReleaseContractError("control credential root inventory differs")
        limits = {
            "operator_bearer": (32, 512),
            "control_hmac_key": (32, 4096),
            "tailscale_operator_login": (1, 254),
        }
        for name in names:
            identity = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if name == "control_hmac_key" and hmac_masked:
                if (
                    not stat.S_ISREG(identity.st_mode)
                    or identity.st_uid != expected_root_uid
                    or identity.st_gid != expected_root_gid
                    or stat.S_IMODE(identity.st_mode) != 0
                    or identity.st_nlink != 1
                    or identity.st_size != 0
                ):
                    raise ReleaseContractError(
                        "control HMAC source is not masked in this namespace"
                    )
                try:
                    masked_descriptor = os.open(
                        name,
                        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                        dir_fd=descriptor,
                    )
                except OSError as exc:
                    if exc.errno not in {errno.EACCES, errno.EPERM}:
                        raise ReleaseContractError(
                            "control HMAC mask open denial differs"
                        ) from exc
                else:
                    os.close(masked_descriptor)
                    raise ReleaseContractError("control HMAC mask is readable")
                continue
            minimum, maximum = limits[name]
            if (
                not stat.S_ISREG(identity.st_mode)
                or identity.st_uid != expected_root_uid
                or identity.st_gid != expected_root_gid
                or stat.S_IMODE(identity.st_mode) != 0o600
                or identity.st_nlink != 1
                or not minimum <= identity.st_size <= maximum
            ):
                raise ReleaseContractError("control credential inventory custody differs")
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_mtime_ns,
        ):
            raise ReleaseContractError("control credential inventory changed during read")
    finally:
        os.close(descriptor)
    return names


def _stable_operator_bearer_probe(
    *,
    release_sha: str,
    source_path: Path,
    dashboard_copy: Path,
    control_copy: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    proc_root: Path,
    expected_root_uid: int,
    expected_root_gid: int,
    positive_read_probe: Callable[..., dict[str, Any]],
    hmac_masked: bool = False,
) -> dict[str, Any]:
    """Prove credential bytes and the intended control listener stayed stable."""
    if source_path.name != "operator_bearer":
        raise ReleaseContractError("operator bearer source path differs")
    inventory_before = _control_credential_source_inventory(
        source_path.parent,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
        hmac_masked=hmac_masked,
    )
    before = _operator_bearer_triplet(
        source_path=source_path,
        dashboard_copy=dashboard_copy,
        control_copy=control_copy,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    control_before = _control_listener_identity(
        release_sha=release_sha,
        runner=runner,
        proc_root=proc_root,
    )
    dashboard_before = _dashboard_listener_identity(
        release_sha=release_sha,
        runner=runner,
        proc_root=proc_root,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    positive = _validate_positive_bearer_probe(
        positive_read_probe(
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
            expected_dashboard_pid=dashboard_before["main_pid"],
            expected_dashboard_uid=dashboard_before["uid"],
            expected_dashboard_gid=dashboard_before["gid"],
        )
    )
    after = _operator_bearer_triplet(
        source_path=source_path,
        dashboard_copy=dashboard_copy,
        control_copy=control_copy,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    control_after = _control_listener_identity(
        release_sha=release_sha,
        runner=runner,
        proc_root=proc_root,
    )
    dashboard_after = _dashboard_listener_identity(
        release_sha=release_sha,
        runner=runner,
        proc_root=proc_root,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    inventory_after = _control_credential_source_inventory(
        source_path.parent,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
        hmac_masked=hmac_masked,
    )
    stable_bytes = (
        hmac.compare_digest(before["source"], after["source"])
        & hmac.compare_digest(before["dashboard"], after["dashboard"])
        & hmac.compare_digest(before["control"], after["control"])
    )
    if (
        not stable_bytes
        or before["source_custody"] != after["source_custody"]
        or before["dashboard_custody"] != after["dashboard_custody"]
        or before["control_custody"] != after["control_custody"]
        or control_before != control_after
        or dashboard_before != dashboard_after
        or inventory_before != inventory_after
    ):
        raise ReleaseContractError("operator bearer readers changed during proof")
    dashboard_custody = dict(after["dashboard_custody"])
    dashboard_custody.update(
        {
            "service_main_pid": dashboard_after["main_pid"],
            "listener_process_identity": dashboard_after,
            "positive_read_proven": True,
            "positive_read_probe": positive["probe_kind"],
            "connected_peer_identity_proven": positive[
                "connected_dashboard_peer_identity_proven"
            ],
            "probe_request_accepted": positive["request_accepted"],
            "probe_inbox_inventory_unchanged": positive[
                "normal_and_emergency_inboxes_unchanged"
            ],
            "decision_or_effect_state_proven": False,
        }
    )
    control_custody = dict(after["control_custody"])
    control_custody.update(
        {
            "service_main_pid": control_after["main_pid"],
            "listener_process_identity": control_after,
            "positive_read_proven": True,
            "positive_read_probe": positive["probe_kind"],
            "probe_request_accepted": positive["request_accepted"],
            "probe_inbox_inventory_unchanged": positive[
                "normal_and_emergency_inboxes_unchanged"
            ],
            "decision_or_effect_state_proven": False,
        }
    )
    return {
        "source_bytes": after["source"],
        "source_file_custody": {
            **after["source_custody"],
            "source_root_exact_three_entries": True,
        },
        "hmac_source_masked_in_dispatch_namespace": hmac_masked,
        "dashboard_credential_custody": dashboard_custody,
        "control_credential_custody": control_custody,
        "positive": positive,
    }


def _control_expected_origin() -> str:
    dashboard = _private_env_bindings(Path(ENV_FILES[2]))
    control = _private_env_bindings(Path(ENV_FILES[3]))
    if set(control) != {"SADHANA_CONTROL_EXPECTED_ORIGIN"}:
        raise ReleaseContractError("control Origin binding differs during read probe")
    origin = control["SADHANA_CONTROL_EXPECTED_ORIGIN"]
    if dashboard.get("SADHANA_CONTROL_EXPECTED_ORIGIN") != origin:
        raise ReleaseContractError("dashboard and control Origin bindings differ")
    parsed = urllib.parse.urlsplit(origin)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.geturl() != origin
        or any(character in origin for character in "\r\n")
    ):
        raise ReleaseContractError("control Origin is not one exact HTTPS origin")
    return origin


def _control_inbox_ledger(
    *,
    expected_root_uid: int,
    expected_control_gid: int,
) -> tuple[tuple[str, tuple[int, ...]], ...]:
    """Inventory names and inodes only; never read signed request bytes."""
    rows: list[tuple[str, tuple[int, ...]]] = []
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    if not getattr(os, "O_DIRECTORY", 0) or not getattr(os, "O_NOFOLLOW", 0):
        raise ReleaseContractError("platform lacks no-follow inbox inventory")
    for root in (CONTROL_NORMAL_INBOX, CONTROL_EMERGENCY_INBOX):
        descriptor = os.open(root, flags)
        try:
            before = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(before.st_mode)
                or before.st_uid != expected_root_uid
                or before.st_gid != expected_control_gid
                or stat.S_IMODE(before.st_mode) != 0o770
            ):
                raise ReleaseContractError("control inbox custody differs")
            for name in sorted(os.listdir(descriptor), key=os.fsencode):
                if not name or "/" in name or "\x00" in name:
                    raise ReleaseContractError("control inbox entry name differs")
                identity = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                rows.append(
                    (
                        f"{root.name}/{name}",
                        (
                            identity.st_dev,
                            identity.st_ino,
                            identity.st_mode,
                            identity.st_uid,
                            identity.st_gid,
                            identity.st_nlink,
                            identity.st_size,
                            identity.st_mtime_ns,
                        ),
                    )
                )
            after = os.fstat(descriptor)
            if (
                before.st_dev,
                before.st_ino,
                before.st_mtime_ns,
            ) != (
                after.st_dev,
                after.st_ino,
                after.st_mtime_ns,
            ):
                raise ReleaseContractError("control inbox changed during inventory")
        finally:
            os.close(descriptor)
    return tuple(rows)


def _request_positive_bearer_read_probe(
    *,
    socket_path: Path,
    origin: str,
    operator_login: str,
    expected_dashboard_pid: int,
    expected_dashboard_uid: int,
    expected_dashboard_gid: int,
    peer_identity_reader: Callable[[socket.socket], tuple[int, int, int]] | None = None,
) -> dict[str, Any]:
    """Exercise the authenticated unsupported-action path without a write."""
    if (
        socket_path != DASHBOARD_SOCKET_PATH
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9@._+:-]{0,253}", operator_login)
        or any(character in origin for character in "\r\n")
    ):
        raise ReleaseContractError("positive bearer probe binding differs")
    body = b'{"action":"approve"}'
    request = (
        "POST /dharma-internal/operator-control HTTP/1.1\r\n"
        "Host: sadhana.internal\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Origin: {origin}\r\n"
        f"Tailscale-User-Login: {operator_login}\r\n"
        f"{CONTROL_CSRF_HEADER}: {CONTROL_CSRF_VALUE}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii") + body
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        connection.settimeout(10.0)
        connection.connect(str(socket_path))
        reader = peer_identity_reader or _linux_connected_unix_peer_identity
        peer_pid, peer_uid, peer_gid = reader(connection)
        if (
            peer_pid != expected_dashboard_pid
            or peer_uid != expected_dashboard_uid
            or peer_gid != expected_dashboard_gid
        ):
            raise ReleaseContractError("connected dashboard peer identity differs")
        connection.sendall(request)
        response = http.client.HTTPResponse(connection, method="POST")
        response.begin()
        raw = response.read(CONTROL_MAX_REQUEST_BYTES + 1)
        status_code = response.status
        content_type = response.headers.get("Content-Type", "")
    except (OSError, http.client.HTTPException) as exc:
        raise ReleaseContractError("positive bearer read probe failed") from exc
    finally:
        connection.close()
    if (
        status_code != 501
        or len(raw) > CONTROL_MAX_REQUEST_BYTES
        or content_type.split(";", 1)[0].strip().lower() != "application/json"
    ):
        raise ReleaseContractError("positive bearer read response differs")
    try:
        payload = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseContractError("positive bearer read response is invalid") from exc
    expected = {
        "status": "unsupported_action",
        "error_code": "proposal_effect_warrant_contract_unavailable",
        "request_accepted": False,
        "decision_applied": False,
        "effect_executed": False,
    }
    if payload != expected:
        raise ReleaseContractError("positive bearer read response claim differs")
    return expected


def _linux_connected_unix_peer_identity(
    connection: socket.socket,
) -> tuple[int, int, int]:
    """Return Linux credentials for the exact connected AF_UNIX peer."""
    option = getattr(socket, "SO_PEERCRED", None)
    if not sys.platform.startswith("linux") or option is None:
        raise ReleaseContractError("Linux SO_PEERCRED is unavailable")
    try:
        raw = connection.getsockopt(
            socket.SOL_SOCKET,
            option,
            struct.calcsize("3i"),
        )
        peer_pid, peer_uid, peer_gid = struct.unpack("3i", raw)
    except (OSError, struct.error) as exc:
        raise ReleaseContractError("cannot read connected dashboard peer") from exc
    if peer_pid <= 0 or peer_uid < 0 or peer_gid < 0:
        raise ReleaseContractError("connected dashboard peer credentials differ")
    return peer_pid, peer_uid, peer_gid


def _default_positive_bearer_read_probe(
    *,
    expected_root_uid: int,
    expected_root_gid: int,
    expected_dashboard_pid: int,
    expected_dashboard_uid: int,
    expected_dashboard_gid: int,
) -> dict[str, Any]:
    """Prove both intended bearer readers via one bounded no-effect request."""
    if os.geteuid() != expected_root_uid or os.getegid() != expected_root_gid:
        raise ReleaseContractError("positive bearer probe requires root custody")
    try:
        control = pwd.getpwnam("dharma-sadhana-control")
    except KeyError as exc:
        raise ReleaseContractError("control service identity is unavailable") from exc
    if control.pw_uid == 0 or control.pw_gid == 0:
        raise ReleaseContractError("control service identity differs")
    login_raw = _read_control_credential(
        CONTROL_LOGIN_SOURCE,
        expected_root_uid=expected_root_uid,
        minimum_bytes=1,
        maximum_bytes=254,
    )
    try:
        login = login_raw.decode("ascii")
    except UnicodeError as exc:
        raise ReleaseContractError("operator login credential is not ASCII") from exc
    before = _control_inbox_ledger(
        expected_root_uid=expected_root_uid,
        expected_control_gid=control.pw_gid,
    )
    response = _request_positive_bearer_read_probe(
        socket_path=DASHBOARD_SOCKET_PATH,
        origin=_control_expected_origin(),
        operator_login=login,
        expected_dashboard_pid=expected_dashboard_pid,
        expected_dashboard_uid=expected_dashboard_uid,
        expected_dashboard_gid=expected_dashboard_gid,
    )
    after = _control_inbox_ledger(
        expected_root_uid=expected_root_uid,
        expected_control_gid=control.pw_gid,
    )
    if before != after:
        raise ReleaseContractError("positive bearer probe changed a control inbox")
    return {
        "probe_kind": "unsupported_action_501_no_inbox_write",
        "authenticated_unsupported_response_observed": True,
        "connected_dashboard_peer_identity_proven": True,
        "normal_and_emergency_inboxes_unchanged": True,
        "request_accepted": response["request_accepted"],
        "decision_or_effect_state_proven": False,
    }


def _validate_positive_bearer_probe(payload: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "probe_kind": "unsupported_action_501_no_inbox_write",
        "authenticated_unsupported_response_observed": True,
        "connected_dashboard_peer_identity_proven": True,
        "normal_and_emergency_inboxes_unchanged": True,
        "request_accepted": False,
        "decision_or_effect_state_proven": False,
    }
    if set(payload) != _POSITIVE_BEARER_PROBE_FIELDS or dict(payload) != expected:
        raise ReleaseContractError("positive bearer reader proof differs")
    return dict(payload)


def _default_secret_sink_scan(
    secret: bytes,
    *,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    proc_root: Path = Path("/proc"),
) -> dict[str, bool]:
    if not secret:
        raise ReleaseContractError("secret sink scan lacks admitted bytes")
    process_clean = True
    for unit in (DASHBOARD_UNIT, "dharma-sadhana-control.service", SUPERVISOR_UNIT, OBSERVER_UNIT):
        pid = _systemd_main_pid(unit, runner=runner)
        if pid <= 0:
            continue
        for name in ("cmdline", "environ"):
            try:
                raw = (proc_root / str(pid) / name).read_bytes()
            except OSError as exc:
                raise ReleaseContractError("secret sink process scan failed") from exc
            process_clean = process_clean and secret not in raw
    unit_clean = True
    for unit in (DASHBOARD_UNIT, "dharma-sadhana-control.service", SUPERVISOR_UNIT, OBSERVER_UNIT):
        unit_clean = unit_clean and secret not in (SYSTEMD_OUTPUT_ROOT / unit).read_bytes()
    journal = runner(
        (
            JOURNALCTL_PATH,
            "--no-pager",
            "--output=cat",
            "-u",
            DASHBOARD_UNIT,
            "-u",
            "dharma-sadhana-control.service",
        ),
        cwd=Path("/"),
        check=False,
    )
    if journal.returncode != 0:
        raise ReleaseContractError("secret sink journal scan failed")
    journal_clean = secret not in journal.stdout.encode("utf-8", errors="surrogateescape")
    source_clean = True
    for candidate in (
        Path(RELEASE_ROOT) / release_sha / "deploy/sadhana/sadhana-dashboard-server.mjs",
        Path(RELEASE_ROOT) / release_sha / "scripts/runtime/sadhana_release.py",
    ):
        source_clean = source_clean and secret not in candidate.read_bytes()
    result = {
        "process_environment_and_argv": process_clean,
        "unit_files": unit_clean,
        "service_journal": journal_clean,
        "release_source": source_clean,
        "browser_public_environment_forbidden": True,
        "receipt_secret_fields_forbidden": True,
    }
    if not all(result.values()):
        raise ReleaseContractError("operator bearer appeared in a forbidden sink")
    return result


def record_operator_credential_acceptance(
    *,
    role: str,
    release_sha: str,
    receipt_path: Path = OPERATOR_CREDENTIAL_RECEIPT,
    source_path: Path = CONTROL_BEARER_SOURCE,
    dashboard_copy: Path = TAILSCALE_DASHBOARD_CREDENTIAL,
    control_copy: Path = TAILSCALE_CONTROL_CREDENTIAL,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    proc_root: Path = Path("/proc"),
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
    access_probe: Callable[..., bool] = _default_principal_access_probe,
    sink_scan: Callable[..., dict[str, bool]] = _default_secret_sink_scan,
    positive_read_probe: Callable[..., dict[str, Any]] = (
        _default_positive_bearer_read_probe
    ),
) -> dict[str, Any]:
    """Prove the v4 two-reader bearer boundary without emitting secret material."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("operator credential acceptance requires root")
    _require_host_role(role, observed_node=observed_node)
    if role != "writer" or not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("operator credential release binding differs")
    if _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0:
        raise ReleaseContractError("credential proof cannot run after dispatch")
    live = _stable_operator_bearer_probe(
        release_sha=release_sha,
        source_path=source_path,
        dashboard_copy=dashboard_copy,
        control_copy=control_copy,
        runner=runner,
        proc_root=proc_root,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
        positive_read_probe=positive_read_probe,
        hmac_masked=False,
    )
    dashboard_custody = live["dashboard_credential_custody"]
    control_custody = live["control_credential_custody"]
    service = _require_static_service_identity()
    identities: dict[str, pwd.struct_passwd] = {}
    for label, name in (
        ("dashboard", DASHBOARD_ACCOUNT_NAME),
        ("control", "dharma-sadhana-control"),
        ("supervisor", service.pw_name),
        ("observer", OBSERVER_ACCOUNT_NAME),
        ("build", BUILD_ACCOUNT_NAME),
        ("oracle", ORACLE_ACCOUNT_NAME),
        ("unrelated", "nobody"),
    ):
        try:
            identities[label] = pwd.getpwnam(name)
        except KeyError as exc:
            raise ReleaseContractError("credential negative identity is absent") from exc
    negative_specs = {
        "dashboard_to_control_copy": (identities["dashboard"], control_copy),
        "control_to_dashboard_copy": (identities["control"], dashboard_copy),
        "supervisor_to_dashboard_copy": (identities["supervisor"], dashboard_copy),
        "supervisor_to_control_copy": (identities["supervisor"], control_copy),
        "observer_to_dashboard_copy": (identities["observer"], dashboard_copy),
        "build_to_dashboard_copy": (identities["build"], dashboard_copy),
        "oracle_to_dashboard_copy": (identities["oracle"], dashboard_copy),
        "unrelated_to_dashboard_copy": (identities["unrelated"], dashboard_copy),
        "supervisor_to_source": (identities["supervisor"], source_path),
        "dashboard_to_source": (identities["dashboard"], source_path),
        "control_to_source": (identities["control"], source_path),
    }
    negative: dict[str, bool] = {}
    for label, (account, target) in negative_specs.items():
        negative[label] = access_probe(
            label,
            uid=account.pw_uid,
            gid=account.pw_gid,
            target=target,
            release_sha=release_sha,
            kind="file",
            runner=runner,
        )
    if not all(negative.values()):
        raise ReleaseContractError("operator bearer negative reader matrix differs")
    sinks = sink_scan(
        live["source_bytes"],
        release_sha=release_sha,
        runner=runner,
        proc_root=proc_root,
    )
    if not sinks or not all(value is True for value in sinks.values()):
        raise ReleaseContractError("operator bearer secret sink scan differs")
    dashboard_unit = SYSTEMD_OUTPUT_ROOT / DASHBOARD_UNIT
    control_unit = SYSTEMD_OUTPUT_ROOT / "dharma-sadhana-control.service"
    payload: dict[str, Any] = {
        "schema_version": OPERATOR_CREDENTIAL_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "dashboard_unit_digest": sha256_file(dashboard_unit, max_bytes=256 * 1024),
        "control_unit_digest": sha256_file(control_unit, max_bytes=256 * 1024),
        "source_file_custody": live["source_file_custody"],
        "dashboard_credential_custody": dashboard_custody,
        "control_credential_custody": control_custody,
        "credential_copies_equal": True,
        "negative_reader_matrix": negative,
        "secret_sink_scan": sinks,
        "verdict": "PASS",
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    if set(payload) != _OPERATOR_CREDENTIAL_RECEIPT_FIELDS:
        raise ReleaseContractError("operator credential receipt fields differ")
    return _publish_or_replay_private_receipt(
        receipt_path,
        payload,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )


def _validate_preactivation_acceptance(
    path: Path,
    *,
    schema: str,
    fields: set[str],
    release_sha: str,
    expected_root_uid: int,
    expected_root_gid: int,
) -> dict[str, Any]:
    payload, _raw, _identity = _read_exact_canonical_json(
        path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=schema,
        digest_field="receipt_digest",
    )
    if (
        set(payload) != fields
        or payload.get("campaign_id") != MISSION_ID
        or payload.get("release_sha") != release_sha
        or payload.get("verdict") != "PASS"
    ):
        raise ReleaseContractError("preactivation acceptance receipt differs")
    return payload


def _revalidate_live_tailscale_binding(
    dashboard: Mapping[str, Any],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> dict[str, Any]:
    release_sha = dashboard.get("release_sha")
    if not isinstance(release_sha, str) or not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("dashboard release binding differs")
    live_state = _revalidate_owned_tailscale_release(
        release_sha=release_sha,
        runner=runner,
    )
    ownership = live_state["ownership"]
    live_digest = live_state["config_sha256"]
    if (
        dashboard.get("tailscale_version") != TAILSCALE_VERSION
        or dashboard.get("serve_status_before_sha256")
        != ownership["serve_status_before_sha256"]
        or dashboard.get("serve_status_after_sha256") != live_digest
        or dashboard.get("serve_upstream") != TAILSCALE_ROUTE
        or dashboard.get("funnel_absence") is not True
    ):
        raise ReleaseContractError("live private Serve binding changed before dispatch")
    return {
        "config_sha256": live_digest,
        "serve_status_before_sha256": ownership["serve_status_before_sha256"],
        "funnel_absent": True,
    }


def _revalidate_owned_tailscale_release(
    *,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    receipt_path: Path | None = None,
    intent_path: Path | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Reprove the durable intent/finalization pair against live Serve state."""
    if not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("Tailscale live release binding differs")
    receipt_path = receipt_path or TAILSCALE_OWNERSHIP_RECEIPT
    intent_path = intent_path or TAILSCALE_INTENT_RECEIPT
    _require_tailscale_version(runner=runner)
    if _read_tailscale_config(runner=runner) != TAILSCALE_EMPTY_CONFIG:
        raise ReleaseContractError("named Tailscale service appeared before dispatch")
    live = _validate_owned_tailscale_config(_read_tailscale_status(runner=runner))
    ownership = _load_tailscale_ownership_receipt(
        receipt_path,
        release_sha=release_sha,
        intent_path=intent_path,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    live_digest = _tailscale_config_digest(live)
    if (
        _canonical_bytes(live) != _canonical_bytes(ownership["config"])
        or live_digest != ownership["config_sha256"]
    ):
        raise ReleaseContractError("live private Serve differs from durable ownership")
    return {
        "ownership": ownership,
        "config_sha256": live_digest,
        "funnel_absent": True,
    }


def _revalidate_live_operator_credentials(
    credentials: Mapping[str, Any],
    *,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    proc_root: Path,
    expected_root_uid: int,
    expected_root_gid: int,
    positive_read_probe: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    live = _stable_operator_bearer_probe(
        release_sha=release_sha,
        source_path=CONTROL_BEARER_SOURCE,
        dashboard_copy=TAILSCALE_DASHBOARD_CREDENTIAL,
        control_copy=TAILSCALE_CONTROL_CREDENTIAL,
        runner=runner,
        proc_root=proc_root,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
        positive_read_probe=positive_read_probe,
        hmac_masked=True,
    )
    dashboard_custody = live["dashboard_credential_custody"]
    control_custody = live["control_credential_custody"]
    if (
        credentials.get("credential_copies_equal") is not True
        or live.get("hmac_source_masked_in_dispatch_namespace") is not True
        or not all(credentials.get("negative_reader_matrix", {}).values())
        or not all(credentials.get("secret_sink_scan", {}).values())
        or credentials.get("source_file_custody") != live["source_file_custody"]
        or credentials.get("dashboard_credential_custody") != dashboard_custody
        or credentials.get("control_credential_custody") != control_custody
        or credentials.get("dashboard_unit_digest")
        != sha256_file(SYSTEMD_OUTPUT_ROOT / DASHBOARD_UNIT, max_bytes=256 * 1024)
        or credentials.get("control_unit_digest")
        != sha256_file(
            SYSTEMD_OUTPUT_ROOT / "dharma-sadhana-control.service",
            max_bytes=256 * 1024,
        )
    ):
        raise ReleaseContractError("live operator credential acceptance changed")
    return {
        "dashboard_service_main_pid": dashboard_custody["service_main_pid"],
        "control_service_main_pid": control_custody["service_main_pid"],
        "control_listener_process_identity": control_custody[
            "listener_process_identity"
        ],
        "credential_copies_equal": True,
        "positive_read_proven": True,
        "request_accepted": False,
        "normal_and_emergency_inboxes_unchanged": True,
        "decision_or_effect_state_proven": False,
    }


def _revalidate_live_predispatch(
    *,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    proc_root: Path,
    now: datetime,
    expected_root_uid: int,
    expected_root_gid: int,
    positive_read_probe: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    """One authority-free live gate used identically for create and replay."""
    if not _unit_active(PREDISPATCH_TARGET, runner=runner):
        raise ReleaseContractError("predispatch target is not independently active")
    if _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0:
        raise ReleaseContractError("supervisor exists before dispatch enablement")
    health = validate_observer_health_receipt(
        release_sha=release_sha,
        runner=runner,
        proc_root=proc_root,
        now=now,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    dashboard = _validate_preactivation_acceptance(
        DASHBOARD_IDENTITY_RECEIPT,
        schema=DASHBOARD_IDENTITY_SCHEMA_VERSION,
        fields=_DASHBOARD_IDENTITY_RECEIPT_FIELDS,
        release_sha=release_sha,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if (
        dashboard.get("dashboard_unit_digest")
        != sha256_file(SYSTEMD_OUTPUT_ROOT / DASHBOARD_UNIT, max_bytes=256 * 1024)
        or dashboard.get("dashboard_process_identity")
        != _dashboard_listener_identity(
            release_sha=release_sha,
            runner=runner,
            proc_root=proc_root,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
    ):
        raise ReleaseContractError("dashboard identity changed before dispatch")
    tailscale = _revalidate_live_tailscale_binding(dashboard, runner=runner)
    credentials = _validate_preactivation_acceptance(
        OPERATOR_CREDENTIAL_RECEIPT,
        schema=OPERATOR_CREDENTIAL_SCHEMA_VERSION,
        fields=_OPERATOR_CREDENTIAL_RECEIPT_FIELDS,
        release_sha=release_sha,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    live_credentials = _revalidate_live_operator_credentials(
        credentials,
        release_sha=release_sha,
        runner=runner,
        proc_root=proc_root,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
        positive_read_probe=positive_read_probe,
    )
    staging = _validate_preactivation_acceptance(
        RUNTIME_STAGING_RECEIPT,
        schema=RUNTIME_STAGING_SCHEMA_VERSION,
        fields=_RUNTIME_STAGING_RECEIPT_FIELDS,
        release_sha=release_sha,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    account = _require_static_service_identity()
    binding = verify_runtime_binding_activation(account=account, now=now)
    if staging.get("runtime_binding_receipt_digest") != binding["receipt_digest"]:
        raise ReleaseContractError("runtime staging binding changed before dispatch")
    _require_live_writer_service_units(
        release_sha=release_sha,
        runner=runner,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    return {
        "health": health,
        "dashboard": dashboard,
        "tailscale": tailscale,
        "credentials": credentials,
        "live_credentials": live_credentials,
        "staging": staging,
        "binding": binding,
    }


def _remove_exact_writer_marker(
    *,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> None:
    if not _validate_existing_writer_marker(
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    ):
        return
    descriptor = os.open(
        WRITER_MARKER,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        opened = os.fstat(descriptor)
        current = WRITER_MARKER.lstat()
        if (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
        ) != (
            current.st_dev,
            current.st_ino,
            current.st_size,
            current.st_mtime_ns,
        ):
            raise ReleaseContractError("writer marker changed during removal")
    finally:
        os.close(descriptor)
    WRITER_MARKER.unlink()
    parent = os.open(WRITER_MARKER.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def _predispatch_live_state(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    unit_states = {
        unit: _activation_unit_state(unit, runner=runner)
        for unit in PREDISPATCH_ACTIVATION_UNITS
    }
    state = {
        "writer_marker_present": _validate_existing_writer_marker(
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        ),
        "campaign_stop_timer_active": unit_states[CAMPAIGN_STOP_TIMER]["active"],
        "campaign_stop_timer_enabled": unit_states[CAMPAIGN_STOP_TIMER]["enabled"],
        "emergency_recovery_path_active": unit_states[EMERGENCY_RECOVERY_PATH][
            "active"
        ],
        "emergency_recovery_path_enabled": unit_states[EMERGENCY_RECOVERY_PATH][
            "enabled"
        ],
        "predispatch_target_active": unit_states[PREDISPATCH_TARGET]["active"],
        "predispatch_target_enabled": unit_states[PREDISPATCH_TARGET]["enabled"],
        "dispatch_marker_absent": not (
            DISPATCH_ENABLE_MARKER.exists() or DISPATCH_ENABLE_MARKER.is_symlink()
        ),
        "dispatch_target_inactive": _unit_inactive(DISPATCH_TARGET, runner=runner),
        "supervisor_main_pid": _systemd_main_pid(SUPERVISOR_UNIT, runner=runner),
    }
    if state != {
        "writer_marker_present": True,
        "campaign_stop_timer_active": True,
        "campaign_stop_timer_enabled": True,
        "emergency_recovery_path_active": True,
        "emergency_recovery_path_enabled": True,
        "predispatch_target_active": True,
        "predispatch_target_enabled": True,
        "dispatch_marker_absent": True,
        "dispatch_target_inactive": True,
        "supervisor_main_pid": 0,
    }:
        raise ReleaseContractError("predispatch live state is not authority-quiet")
    return state


def _activation_unit_state(
    unit: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> dict[str, bool]:
    active = _unit_active(unit, runner=runner)
    inactive = _unit_inactive(unit, runner=runner)
    enabled = _unit_enabled(unit, runner=runner)
    disabled = _unit_disabled(unit, runner=runner)
    if active == inactive or enabled == disabled:
        raise ReleaseContractError(f"activation unit state is indeterminate: {unit}")
    return {
        "active": active,
        "inactive": inactive,
        "enabled": enabled,
        "disabled": disabled,
    }


def _predispatch_activation_intent(
    *,
    release_sha: str,
    preactivation_clock_proof_receipt_digest: str,
    path: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    observed: datetime,
    expected_root_uid: int,
    expected_root_gid: int,
) -> tuple[dict[str, Any], bool]:
    """Persist exact clean preconditions before the first infrastructure effect."""
    if path.exists() or path.is_symlink():
        prior, _raw, _identity = _read_exact_canonical_json(
            path,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
            expected_schema=PREDISPATCH_ACTIVATION_INTENT_SCHEMA_VERSION,
            digest_field="receipt_digest",
        )
        if (
            set(prior) != _PREDISPATCH_ACTIVATION_INTENT_FIELDS
            or prior.get("campaign_id") != MISSION_ID
            or prior.get("release_sha") != release_sha
            or prior.get("preactivation_clock_proof_receipt_digest")
            != preactivation_clock_proof_receipt_digest
            or prior.get("writer_marker_absent_before") is not True
            or prior.get("campaign_stop_timer_inactive_before") is not True
            or prior.get("campaign_stop_timer_disabled_before") is not True
            or prior.get("emergency_recovery_path_inactive_before") is not True
            or prior.get("emergency_recovery_path_disabled_before") is not True
            or prior.get("predispatch_target_inactive_before") is not True
            or prior.get("predispatch_target_disabled_before") is not True
            or prior.get("dispatch_marker_absent_before") is not True
            or prior.get("dispatch_target_inactive_before") is not True
            or prior.get("supervisor_main_pid_before") != 0
            or prior.get("effect_intent") != "InfrastructureEffect"
            or prior.get("provider_dispatch") != "NoProviderDispatch"
        ):
            raise ReleaseContractError("predispatch activation intent differs")
        return prior, False

    if WRITER_MARKER.exists() or WRITER_MARKER.is_symlink():
        raise ReleaseContractError("fresh predispatch activation found a writer marker")
    unit_states = {
        unit: _activation_unit_state(unit, runner=runner)
        for unit in PREDISPATCH_ACTIVATION_UNITS
    }
    if any(
        not state["inactive"] or not state["disabled"]
        for state in unit_states.values()
    ):
        raise ReleaseContractError(
            "fresh predispatch activation found an active or enabled unit"
        )
    dispatch_marker_absent = not (
        DISPATCH_ENABLE_MARKER.exists() or DISPATCH_ENABLE_MARKER.is_symlink()
    )
    dispatch_target_inactive = _unit_inactive(DISPATCH_TARGET, runner=runner)
    supervisor_main_pid = _systemd_main_pid(SUPERVISOR_UNIT, runner=runner)
    if (
        not dispatch_marker_absent
        or not dispatch_target_inactive
        or supervisor_main_pid != 0
    ):
        raise ReleaseContractError("fresh predispatch authority is not quiet")
    payload: dict[str, Any] = {
        "schema_version": PREDISPATCH_ACTIVATION_INTENT_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "created_at": observed.isoformat().replace("+00:00", "Z"),
        "preactivation_clock_proof_receipt_digest": (
            preactivation_clock_proof_receipt_digest
        ),
        "writer_marker_absent_before": True,
        "campaign_stop_timer_inactive_before": True,
        "campaign_stop_timer_disabled_before": True,
        "emergency_recovery_path_inactive_before": True,
        "emergency_recovery_path_disabled_before": True,
        "predispatch_target_inactive_before": True,
        "predispatch_target_disabled_before": True,
        "dispatch_marker_absent_before": True,
        "dispatch_target_inactive_before": True,
        "supervisor_main_pid_before": 0,
        "effect_intent": "InfrastructureEffect",
        "provider_dispatch": "NoProviderDispatch",
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    if set(payload) != _PREDISPATCH_ACTIVATION_INTENT_FIELDS:
        raise ReleaseContractError("predispatch activation intent fields differ")
    return (
        _publish_or_replay_private_receipt(
            path,
            payload,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
        ),
        True,
    )


def _verify_activation_staged_release(
    *,
    role: str,
    release_sha: str,
    expected_root_uid: int,
    expected_root_gid: int,
) -> tuple[dict[str, Any], pwd.struct_passwd]:
    """Return the exact staged admission only after revalidating its frozen tree."""
    account = _require_static_service_identity()
    _release_receipt_dir, _ledger, _build, admission_path = (
        _staged_release_receipt_paths(release_sha)
    )
    admission, _admission_raw, _admission_identity = _read_exact_custodied_json(
        admission_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )
    release_input_set_digest = admission.get("release_input_set_digest")
    if not isinstance(release_input_set_digest, str):
        raise ReleaseContractError("staged release input-set digest is absent")
    admitted = verify_staged_release_admission(
        release_sha=release_sha,
        release_path=Path(RELEASE_ROOT) / release_sha,
        expected_release_input_set_digest=release_input_set_digest,
        account=account,
        require_projection=role == "writer",
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if admission != admitted:
        raise ReleaseContractError("staged release admission changed during validation")
    digest = admission.get("receipt_digest")
    if not isinstance(digest, str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", digest
    ):
        raise ReleaseContractError("staged release admission receipt digest differs")
    return admission, account


def _prepared_projection_refresh_indices(
    preparation: Mapping[str, Any],
) -> dict[str, str]:
    """Extract the exact stable no-provider projection contract from preparation."""
    proof = preparation.get("proof")
    parameters = proof.get("parameters") if isinstance(proof, Mapping) else None
    projection = preparation.get("projection")
    global_rows = preparation.get("global_dispatch_rows")
    empty_rows = {"task_claim_ids": [], "delegation_run_ids": []}
    expected_projection_fields = {
        "schema_version",
        "path",
        "projection_schema_version",
        "mission_id",
        "session_id",
        "config_digest",
        "generation",
        "minimum_cycle_sequence",
        "campaign_status",
        "supervisor_state",
        "writer_lock_held",
        "proves_process_liveness",
        "provider_dispatch",
    }
    if (
        not isinstance(parameters, Mapping)
        or not isinstance(projection, Mapping)
        or set(projection) != expected_projection_fields
        or projection.get("schema_version")
        != "dharma.sadhana.prepared_projection_contract.v1"
        or projection.get("path") != str(WRITER_PROJECTION_PATH)
        or projection.get("projection_schema_version")
        != "dharma.mission_control.read_model.v1"
        or projection.get("mission_id") != MISSION_ID
        or projection.get("session_id") != f"mission_campaign:{MISSION_ID}"
        or projection.get("generation") != 1
        or projection.get("minimum_cycle_sequence") != 1
        or projection.get("campaign_status") != "paused"
        or projection.get("supervisor_state") != "not_running"
        or projection.get("writer_lock_held") is not False
        or projection.get("proves_process_liveness") is not False
        or projection.get("provider_dispatch") != "NoProviderDispatch"
        or global_rows != {"before": empty_rows, "after": empty_rows}
    ):
        raise ReleaseContractError("prepared projection refresh contract differs")
    projection_contract_digest = parameters.get("projection_contract_digest")
    config_digest = parameters.get("config_digest")
    preparation_receipt_digest = preparation.get("receipt_digest")
    expected_projection_digest = "sha256:" + hashlib.sha256(
        _canonical_bytes(projection) + b"\n"
    ).hexdigest()
    if (
        projection_contract_digest != expected_projection_digest
        or projection.get("config_digest") != config_digest
        or not isinstance(config_digest, str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", config_digest)
        or not isinstance(preparation_receipt_digest, str)
        or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", preparation_receipt_digest
        )
    ):
        raise ReleaseContractError("prepared projection refresh digest differs")
    return {
        "preparation_receipt_digest": preparation_receipt_digest,
        "projection_contract_digest": projection_contract_digest,
        "config_digest": config_digest,
    }


def _validate_refreshed_projection_bytes(expected_sha256: str) -> None:
    """Require the writer and observer copies to remain the exact refreshed bytes."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ReleaseContractError("predispatch projection digest differs")
    service = _require_static_service_identity()
    observer = _require_observer_identity()
    source = _read_scoped_runtime_source(
        WRITER_PROJECTION_PATH,
        parent_uid=service.pw_uid,
        parent_gid=service.pw_gid,
        file_uid=service.pw_uid,
        file_gid=service.pw_gid,
        maximum_bytes=32 * 1024 * 1024,
    )
    projected, _identity = _read_exact_custodied_bytes(
        OBSERVER_PROJECTION_PATH,
        expected_uid=observer.pw_uid,
        expected_gid=observer.pw_gid,
        maximum_bytes=32 * 1024 * 1024,
    )
    if (
        source != projected
        or hashlib.sha256(source).hexdigest() != expected_sha256
    ):
        raise ReleaseContractError("predispatch projection copies differ")


def refresh_predispatch(
    *,
    role: str,
    release_sha: str,
    receipt_path: Path = PREDISPATCH_REFRESH_RECEIPT,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    now: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
    projection_syncer: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Refresh paused no-provider preparation and observer bytes before dispatch."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("predispatch refresh requires root")
    hostname = _require_host_role(role, observed_node=observed_node)
    if (
        role != "writer"
        or not _COMMIT_RE.fullmatch(release_sha)
        or receipt_path != PREDISPATCH_REFRESH_RECEIPT
    ):
        raise ReleaseContractError("predispatch refresh binding differs")
    observed = _sample_utc(
        now=now,
        clock=clock,
        label="predispatch refresh",
    )
    guard_campaign_clock(role=role, now=observed, observed_node=hostname)
    if (
        ROLLBACK_RECEIPT.exists()
        or ROLLBACK_RECEIPT.is_symlink()
        or DISPATCH_ENABLE_MARKER.exists()
        or DISPATCH_ENABLE_MARKER.is_symlink()
    ):
        raise ReleaseContractError("predispatch refresh found terminal authority")
    _validate_existing_writer_marker(
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if (
        not _unit_inactive(DISPATCH_TARGET, runner=runner)
        or _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0
    ):
        raise ReleaseContractError("predispatch refresh found dispatch activity")
    admission, account = _verify_activation_staged_release(
        role=role,
        release_sha=release_sha,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    binding = verify_runtime_binding_activation(
        account=account,
        expected_release_sha=release_sha,
        now=observed,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if not _unit_static(RUNTIME_PREPARATION_UNIT, runner=runner):
        raise ReleaseContractError("runtime preparation unit is enableable")
    restarted = runner(
        (SYSTEMCTL_PATH, "restart", RUNTIME_PREPARATION_UNIT),
        cwd=Path("/"),
        check=False,
    )
    if restarted.returncode != 0 or restarted.stdout or restarted.stderr:
        raise ReleaseContractError("predispatch runtime refresh failed")
    if (
        not _unit_active(RUNTIME_PREPARATION_UNIT, runner=runner)
        or not _unit_static(RUNTIME_PREPARATION_UNIT, runner=runner)
        or _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0
    ):
        raise ReleaseContractError("predispatch runtime refresh did not remain safe")
    preparation, _prepared = _validate_root_preparation(
        release_sha=release_sha,
        account=account,
        preparation_receipt_path=RUNTIME_PREPARATION_RECEIPT,
        prepared_root=PREPARED_RUNTIME_MANIFEST_ROOT,
        release_receipt_root=RELEASE_RECEIPT_ROOT,
        release_admission_projection=PREPARED_RELEASE_ADMISSION_PROJECTION,
        supervisor_env_path=Path(ENV_FILES[0]),
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    indices = _prepared_projection_refresh_indices(preparation)
    if (
        binding.get("preparation_receipt_digest")
        != indices["preparation_receipt_digest"]
        or binding.get("config_digest") != indices["config_digest"]
    ):
        raise ReleaseContractError("predispatch refresh runtime binding differs")
    syncer = projection_syncer or sync_observer_projection
    synchronized = syncer(
        role=role,
        now=observed,
        observed_node=hostname,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    projection_sha256 = synchronized.get("projection_sha256")
    if (
        synchronized.get("status") != "observer_projection_synced"
        or not isinstance(projection_sha256, str)
    ):
        raise ReleaseContractError("predispatch observer projection sync differs")
    _validate_refreshed_projection_bytes(projection_sha256)
    observed = _sample_utc(
        now=now,
        clock=clock,
        label="predispatch refresh completion",
    )
    guard_campaign_clock(role=role, now=observed, observed_node=hostname)
    if (
        ROLLBACK_RECEIPT.exists()
        or ROLLBACK_RECEIPT.is_symlink()
        or DISPATCH_ENABLE_MARKER.exists()
        or DISPATCH_ENABLE_MARKER.is_symlink()
        or _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0
    ):
        raise ReleaseContractError(
            "predispatch refresh authority changed before publication"
        )
    binding = verify_runtime_binding_activation(
        account=account,
        expected_release_sha=release_sha,
        now=observed,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if (
        binding.get("preparation_receipt_digest")
        != indices["preparation_receipt_digest"]
        or binding.get("config_digest") != indices["config_digest"]
    ):
        raise ReleaseContractError("predispatch refresh completion binding differs")
    _validate_refreshed_projection_bytes(projection_sha256)
    valid_until = min(
        observed + timedelta(seconds=PREDISPATCH_REFRESH_FRESHNESS_SECONDS),
        _parse_utc(CAMPAIGN_STOP_UTC, "campaign_stop_utc"),
    )
    payload: dict[str, Any] = {
        "schema_version": PREDISPATCH_REFRESH_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "hostname": hostname,
        "refreshed_at": observed.isoformat().replace("+00:00", "Z"),
        "valid_until": valid_until.isoformat().replace("+00:00", "Z"),
        "staged_release_admission_receipt_digest": admission["receipt_digest"],
        "runtime_binding_receipt_digest": binding["receipt_digest"],
        **indices,
        "projection_path": str(WRITER_PROJECTION_PATH),
        "observer_projection_path": str(OBSERVER_PROJECTION_PATH),
        "observer_projection_sha256": projection_sha256,
        "global_dispatch_rows_empty": True,
        "provider_dispatch": "NoProviderDispatch",
        "preparation_unit_static": True,
        "supervisor_main_pid": 0,
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    if set(payload) != _PREDISPATCH_REFRESH_RECEIPT_FIELDS:
        raise ReleaseContractError("predispatch refresh receipt fields differ")
    _atomic_private_bytes(
        receipt_path,
        _canonical_bytes(payload) + b"\n",
        uid=expected_root_uid,
        gid=expected_root_gid,
        replace_existing=receipt_path.exists() or receipt_path.is_symlink(),
    )
    admitted, _raw, _identity = _read_exact_canonical_json(
        receipt_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=PREDISPATCH_REFRESH_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    if admitted != payload:
        raise ReleaseContractError("predispatch refresh receipt changed on publish")
    return admitted


def validate_predispatch_refresh_receipt(
    *,
    role: str,
    release_sha: str,
    receipt_path: Path = PREDISPATCH_REFRESH_RECEIPT,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    now: datetime | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
    require_preparation_active: bool = True,
) -> dict[str, Any]:
    """Admit only the current short-lived refresh and its exact copied bytes."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("predispatch refresh validation requires root")
    hostname = _require_host_role(role, observed_node=observed_node)
    if (
        role != "writer"
        or not _COMMIT_RE.fullmatch(release_sha)
        or receipt_path != PREDISPATCH_REFRESH_RECEIPT
    ):
        raise ReleaseContractError("predispatch refresh validation binding differs")
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ReleaseContractError("predispatch refresh validation clock must be aware")
    observed = observed.astimezone(timezone.utc).replace(microsecond=0)
    guard_campaign_clock(role=role, now=observed, observed_node=hostname)
    if require_preparation_active and (
        DISPATCH_ENABLE_MARKER.exists() or DISPATCH_ENABLE_MARKER.is_symlink()
    ):
        raise ReleaseContractError("predispatch refresh was already consumed")
    receipt, _raw, _identity = _read_exact_canonical_json(
        receipt_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=PREDISPATCH_REFRESH_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    refreshed_at = _parse_utc(str(receipt.get("refreshed_at")), "refreshed_at")
    valid_until = _parse_utc(str(receipt.get("valid_until")), "valid_until")
    expected_valid_until = min(
        refreshed_at + timedelta(seconds=PREDISPATCH_REFRESH_FRESHNESS_SECONDS),
        _parse_utc(CAMPAIGN_STOP_UTC, "campaign_stop_utc"),
    )
    if (
        set(receipt) != _PREDISPATCH_REFRESH_RECEIPT_FIELDS
        or receipt.get("campaign_id") != MISSION_ID
        or receipt.get("release_sha") != release_sha
        or receipt.get("hostname") != hostname
        or valid_until != expected_valid_until
        or refreshed_at
        > observed + timedelta(seconds=MAX_CONTROLLER_CLOCK_SKEW_SECONDS)
        or observed >= valid_until
        or receipt.get("projection_path") != str(WRITER_PROJECTION_PATH)
        or receipt.get("observer_projection_path")
        != str(OBSERVER_PROJECTION_PATH)
        or receipt.get("global_dispatch_rows_empty") is not True
        or receipt.get("provider_dispatch") != "NoProviderDispatch"
        or receipt.get("preparation_unit_static") is not True
        or receipt.get("supervisor_main_pid") != 0
    ):
        raise ReleaseContractError("predispatch refresh receipt differs")
    admission, account = _verify_activation_staged_release(
        role=role,
        release_sha=release_sha,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    binding = verify_runtime_binding_activation(
        account=account,
        expected_release_sha=release_sha,
        now=observed,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    preparation, _preparation_raw, _preparation_identity = (
        _read_exact_custodied_json(
            RUNTIME_PREPARATION_RECEIPT,
            expected_uid=account.pw_uid,
            expected_gid=account.pw_gid,
        )
    )
    indices = _prepared_projection_refresh_indices(preparation)
    if (
        receipt.get("staged_release_admission_receipt_digest")
        != admission["receipt_digest"]
        or receipt.get("runtime_binding_receipt_digest")
        != binding["receipt_digest"]
        or any(receipt.get(key) != value for key, value in indices.items())
        or _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0
        or not _unit_static(RUNTIME_PREPARATION_UNIT, runner=runner)
        or (
            require_preparation_active
            and not _unit_active(RUNTIME_PREPARATION_UNIT, runner=runner)
        )
    ):
        raise ReleaseContractError("predispatch refresh live binding differs")
    projection_sha256 = receipt.get("observer_projection_sha256")
    if not isinstance(projection_sha256, str):
        raise ReleaseContractError("predispatch projection digest differs")
    _validate_refreshed_projection_bytes(projection_sha256)
    return receipt


def _predispatch_compensation_is_quiet(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> bool:
    return (
        all(
            _unit_inactive(unit, runner=runner)
            and _unit_disabled(unit, runner=runner)
            for unit in PREDISPATCH_ACTIVATION_UNITS
        )
        and _unit_inactive(DISPATCH_TARGET, runner=runner)
        and _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) == 0
        and not (WRITER_MARKER.exists() or WRITER_MARKER.is_symlink())
    )


def _publish_predispatch_account_ui_gate(
    activation: Mapping[str, Any],
    *,
    release_sha: str,
    expected_root_uid: int,
) -> dict[str, Any]:
    """Project only the narrow root authority bytes readable by control."""
    try:
        control = pwd.getpwnam("dharma-sadhana-control")
    except KeyError as exc:
        raise ReleaseContractError("control service identity is absent") from exc
    _ensure_host_directory(
        PREDISPATCH_ACCOUNT_UI_GATE_ROOT,
        uid=expected_root_uid,
        gid=control.pw_gid,
        mode=0o750,
    )
    payload: dict[str, Any] = {
        "schema_version": PREDISPATCH_ACCOUNT_UI_GATE_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "activated_at": activation["activated_at"],
        "predispatch_activation_receipt_digest": activation["receipt_digest"],
        "dispatch_marker_absent": True,
        "dispatch_target_inactive": True,
        "supervisor_main_pid": 0,
        "provider_dispatch": "NoProviderDispatch",
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    if set(payload) != _PREDISPATCH_ACCOUNT_UI_GATE_FIELDS:
        raise ReleaseContractError("account UI predispatch gate fields differ")
    raw = _canonical_bytes(payload) + b"\n"
    if PREDISPATCH_ACCOUNT_UI_GATE.exists() or PREDISPATCH_ACCOUNT_UI_GATE.is_symlink():
        prior, prior_raw, _identity = _read_exact_custodied_json(
            PREDISPATCH_ACCOUNT_UI_GATE,
            expected_uid=expected_root_uid,
            expected_gid=control.pw_gid,
            expected_mode=0o640,
        )
        if prior_raw != raw or prior != payload:
            raise ReleaseContractError("account UI predispatch gate conflicts")
        return prior
    _atomic_private_bytes(
        PREDISPATCH_ACCOUNT_UI_GATE,
        raw,
        uid=expected_root_uid,
        gid=control.pw_gid,
    )
    os.chmod(PREDISPATCH_ACCOUNT_UI_GATE, 0o640, follow_symlinks=False)
    admitted, admitted_raw, _identity = _read_exact_custodied_json(
        PREDISPATCH_ACCOUNT_UI_GATE,
        expected_uid=expected_root_uid,
        expected_gid=control.pw_gid,
        expected_mode=0o640,
    )
    if admitted_raw != raw or admitted != payload:
        raise ReleaseContractError("account UI predispatch gate changed on publish")
    return admitted


def _compensate_failed_predispatch_replay(
    *,
    release_sha: str,
    intent_path: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    expected_root_uid: int,
    expected_root_gid: int,
) -> None:
    """Return an interrupted predispatch transaction to its exact quiet state."""
    intent, _raw, _identity = _read_exact_canonical_json(
        intent_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=PREDISPATCH_ACTIVATION_INTENT_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    if (
        set(intent) != _PREDISPATCH_ACTIVATION_INTENT_FIELDS
        or intent.get("campaign_id") != MISSION_ID
        or intent.get("release_sha") != release_sha
        or intent.get("effect_intent") != "InfrastructureEffect"
        or intent.get("provider_dispatch") != "NoProviderDispatch"
    ):
        raise ReleaseContractError(
            "predispatch crash intent cannot authorize compensation"
        )
    compensation_failed = False
    for unit in reversed(PREDISPATCH_ACTIVATION_UNITS):
        stopped = runner(
            (SYSTEMCTL_PATH, "disable", "--now", unit),
            cwd=Path("/"),
            check=False,
        )
        compensation_failed = compensation_failed or stopped.returncode != 0
    if WRITER_MARKER.exists() or WRITER_MARKER.is_symlink():
        try:
            _remove_exact_writer_marker(
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
        except ReleaseContractError:
            compensation_failed = True
    if compensation_failed or not _predispatch_compensation_is_quiet(
        runner=runner
    ):
        raise ReleaseContractError("predispatch crash compensation failed")


def _replay_completed_predispatch_activation(
    *,
    role: str,
    release_sha: str,
    receipt_path: Path,
    intent_path: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    observed_node: str | None,
    expected_root_uid: int,
    expected_root_gid: int,
) -> dict[str, Any]:
    """Validate a completed live activation without rerunning pre-effect gates."""
    prior, _prior_raw, _prior_identity = _read_exact_canonical_json(
        receipt_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=PREDISPATCH_ACTIVATION_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    admission, account = _verify_activation_staged_release(
        role=role,
        release_sha=release_sha,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    clock_proof = validate_preactivation_clock_proof(
        release_sha=release_sha,
        role=role,
        known_hosts_sha256=DEPLOYMENT_KNOWN_HOSTS_SHA256,
        staged_release_admission_receipt_digest=admission["receipt_digest"],
        now=_parse_utc(str(prior.get("activated_at")), "activated_at"),
        observed_node=observed_node,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    binding = verify_runtime_binding_activation(
        account=account,
        expected_release_sha=release_sha,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    staging = _validate_preactivation_acceptance(
        RUNTIME_STAGING_RECEIPT,
        schema=RUNTIME_STAGING_SCHEMA_VERSION,
        fields=_RUNTIME_STAGING_RECEIPT_FIELDS,
        release_sha=release_sha,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if staging.get("runtime_binding_receipt_digest") != binding["receipt_digest"]:
        raise ReleaseContractError("runtime staging binding changed before replay")
    activation_intent, intent_created = _predispatch_activation_intent(
        release_sha=release_sha,
        preactivation_clock_proof_receipt_digest=clock_proof["receipt_digest"],
        path=intent_path,
        runner=runner,
        observed=_parse_utc(str(prior.get("activated_at")), "activated_at"),
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if intent_created:
        raise ReleaseContractError("completed predispatch activation intent is absent")
    live = _predispatch_live_state(
        runner=runner,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    intent = _load_tailscale_intent_receipt(
        TAILSCALE_INTENT_RECEIPT,
        release_sha=release_sha,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    tailscale = _revalidate_owned_tailscale_release(
        release_sha=release_sha,
        runner=runner,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    ownership = tailscale["ownership"]
    expected = {
        "activation_intent_receipt_digest": activation_intent["receipt_digest"],
        "staged_release_admission_receipt_digest": admission["receipt_digest"],
        "preactivation_clock_proof_receipt_digest": clock_proof["receipt_digest"],
        "runtime_binding_receipt_digest": binding["receipt_digest"],
        "runtime_staging_receipt_digest": staging["receipt_digest"],
        "tailscale_intent_receipt_digest": intent["receipt_digest"],
        "tailscale_ownership_receipt_digest": ownership["receipt_digest"],
        **live,
    }
    if (
        set(prior) != _PREDISPATCH_ACTIVATION_FIELDS
        or prior.get("campaign_id") != MISSION_ID
        or prior.get("release_sha") != release_sha
        or prior.get("proof_type")
        != "PredispatchAuthority<Mission,Release,InputSet,Config,TaskSet>"
        or prior.get("effect") != "InfrastructureEffect"
        or prior.get("provider_dispatch") != "NoProviderDispatch"
        or any(prior.get(key) != value for key, value in expected.items())
    ):
        raise ReleaseContractError("predispatch activation replay differs")
    _require_live_writer_service_units(
        release_sha=release_sha,
        runner=runner,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    return prior


def activate_predispatch(
    *,
    role: str,
    release_sha: str,
    receipt_path: Path = PREDISPATCH_ACTIVATION_RECEIPT,
    intent_path: Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    now: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Promote preparation into infrastructure-only predispatch authority."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("predispatch activation requires root")
    _require_host_role(role, observed_node=observed_node)
    intent_path = intent_path or PREDISPATCH_ACTIVATION_INTENT
    if (
        role != "writer"
        or not _COMMIT_RE.fullmatch(release_sha)
        or receipt_path != PREDISPATCH_ACTIVATION_RECEIPT
        or intent_path != PREDISPATCH_ACTIVATION_INTENT
    ):
        raise ReleaseContractError("predispatch activation binding differs")
    replay = receipt_path.exists() or receipt_path.is_symlink()
    crash_intent = not replay and (intent_path.exists() or intent_path.is_symlink())
    observed = _sample_utc(
        now=now,
        clock=clock,
        label="predispatch activation",
    )
    guard_campaign_clock(role=role, now=observed, observed_node=observed_node)
    if replay:
        if ROLLBACK_RECEIPT.exists() or ROLLBACK_RECEIPT.is_symlink():
            raise ReleaseContractError("rolled-back release cannot reactivate")
        if DISPATCH_ENABLE_MARKER.exists() or DISPATCH_ENABLE_MARKER.is_symlink():
            raise ReleaseContractError("predispatch activation cannot replace dispatch")
        if _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0:
            raise ReleaseContractError("supervisor exists during predispatch replay")
        admitted = _replay_completed_predispatch_activation(
            role=role,
            release_sha=release_sha,
            receipt_path=receipt_path,
            intent_path=intent_path,
            runner=runner,
            observed_node=observed_node,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        _publish_predispatch_account_ui_gate(
            admitted,
            release_sha=release_sha,
            expected_root_uid=expected_root_uid,
        )
        return admitted
    try:
        if ROLLBACK_RECEIPT.exists() or ROLLBACK_RECEIPT.is_symlink():
            raise ReleaseContractError("rolled-back release cannot reactivate")
        if DISPATCH_ENABLE_MARKER.exists() or DISPATCH_ENABLE_MARKER.is_symlink():
            raise ReleaseContractError(
                "predispatch activation cannot replace dispatch"
            )
        if _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0:
            raise ReleaseContractError(
                "supervisor exists before predispatch activation"
            )
        admission, account = _verify_activation_staged_release(
            role=role,
            release_sha=release_sha,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        clock_proof = validate_preactivation_clock_proof(
            release_sha=release_sha,
            role=role,
            known_hosts_sha256=DEPLOYMENT_KNOWN_HOSTS_SHA256,
            staged_release_admission_receipt_digest=admission["receipt_digest"],
            now=observed,
            observed_node=observed_node,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        binding = publish_runtime_binding_activation(
            role=role,
            release_sha=release_sha,
            account=account,
            now=observed,
            observed_node=observed_node,
        )
        staging = finalize_disabled_runtime_staging(
            role=role,
            release_sha=release_sha,
            runner=runner,
            now=observed,
            observed_node=observed_node,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        refresh_predispatch(
            role=role,
            release_sha=release_sha,
            runner=runner,
            now=observed,
            clock=clock,
            observed_node=observed_node,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        _require_loopback_ports_free()
        observed = _sample_utc(
            now=now,
            clock=clock,
            label="predispatch activation completion",
        )
        guard_campaign_clock(role=role, now=observed, observed_node=observed_node)
        clock_proof = validate_preactivation_clock_proof(
            release_sha=release_sha,
            role=role,
            known_hosts_sha256=DEPLOYMENT_KNOWN_HOSTS_SHA256,
            staged_release_admission_receipt_digest=admission["receipt_digest"],
            now=observed,
            observed_node=observed_node,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        if (
            ROLLBACK_RECEIPT.exists()
            or ROLLBACK_RECEIPT.is_symlink()
            or DISPATCH_ENABLE_MARKER.exists()
            or DISPATCH_ENABLE_MARKER.is_symlink()
            or _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0
        ):
            raise ReleaseContractError(
                "predispatch activation authority changed before intent"
            )
        activation_intent, intent_created = _predispatch_activation_intent(
            release_sha=release_sha,
            preactivation_clock_proof_receipt_digest=clock_proof["receipt_digest"],
            path=intent_path,
            runner=runner,
            observed=observed,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
    except Exception:
        if crash_intent:
            _compensate_failed_predispatch_replay(
                release_sha=release_sha,
                intent_path=intent_path,
                runner=runner,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
        raise
    marker_owned = False
    touched_units: set[str] = set()
    prior_owned_units: set[str] = set()
    for unit in PREDISPATCH_ACTIVATION_UNITS:
        state = _activation_unit_state(unit, runner=runner)
        clean = state["inactive"] and state["disabled"]
        resumable = state["enabled"] and (state["active"] or state["inactive"])
        if not clean and not resumable:
            raise ReleaseContractError(
                f"predispatch activation unit drifted before replay: {unit}"
            )
        if resumable:
            prior_owned_units.add(unit)
    if intent_created and prior_owned_units:
        raise ReleaseContractError("fresh predispatch activation unit state raced")
    try:
        marker_present = _validate_existing_writer_marker(
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        if marker_present:
            if intent_created:
                raise ReleaseContractError(
                    "fresh predispatch activation marker state raced"
                )
            marker_owned = True
        else:
            _atomic_private_bytes(
                WRITER_MARKER,
                b"writer\n",
                uid=expected_root_uid,
                gid=expected_root_gid,
            )
            marker_owned = True
        _require_live_writer_service_units(
            release_sha=release_sha,
            runner=runner,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        for unit in PREDISPATCH_ACTIVATION_UNITS:
            state = _activation_unit_state(unit, runner=runner)
            if state["active"] and state["enabled"]:
                continue
            if not state["inactive"] or not (
                state["disabled"] or state["enabled"]
            ):
                raise ReleaseContractError(
                    f"predispatch activation unit cannot resume: {unit}"
                )
            touched_units.add(unit)
            started = runner(
                (SYSTEMCTL_PATH, "enable", "--now", unit),
                cwd=Path("/"),
                check=False,
            )
            if started.returncode != 0:
                raise ReleaseContractError(
                    f"predispatch lifecycle unit activation failed: {unit}"
                )
        _require_live_writer_service_units(
            release_sha=release_sha,
            runner=runner,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        live = _predispatch_live_state(
            runner=runner,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        intent = _load_tailscale_intent_receipt(
            TAILSCALE_INTENT_RECEIPT,
            release_sha=release_sha,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        tailscale = _revalidate_owned_tailscale_release(
            release_sha=release_sha,
            runner=runner,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        ownership = tailscale["ownership"]
        payload: dict[str, Any] = {
            "schema_version": PREDISPATCH_ACTIVATION_SCHEMA_VERSION,
            "campaign_id": MISSION_ID,
            "release_sha": release_sha,
            "activated_at": observed.isoformat().replace("+00:00", "Z"),
            "activation_intent_receipt_digest": activation_intent[
                "receipt_digest"
            ],
            "staged_release_admission_receipt_digest": admission[
                "receipt_digest"
            ],
            "preactivation_clock_proof_receipt_digest": clock_proof[
                "receipt_digest"
            ],
            "runtime_binding_receipt_digest": binding["receipt_digest"],
            "runtime_staging_receipt_digest": staging["receipt_digest"],
            "tailscale_intent_receipt_digest": intent["receipt_digest"],
            "tailscale_ownership_receipt_digest": ownership["receipt_digest"],
            **live,
            "proof_type": (
                "PredispatchAuthority<Mission,Release,InputSet,Config,TaskSet>"
            ),
            "effect": "InfrastructureEffect",
            "provider_dispatch": "NoProviderDispatch",
            "receipt_digest": "",
        }
        payload["receipt_digest"] = _canonical_self_digest(
            payload,
            "receipt_digest",
        )
        if set(payload) != _PREDISPATCH_ACTIVATION_FIELDS:
            raise ReleaseContractError("predispatch activation receipt fields differ")
        admitted = _publish_or_replay_private_receipt(
            receipt_path,
            payload,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
        )
        _publish_predispatch_account_ui_gate(
            admitted,
            release_sha=release_sha,
            expected_root_uid=expected_root_uid,
        )
        return admitted
    except Exception as exc:
        compensation_failed = False
        owned_units = prior_owned_units | touched_units
        for unit in reversed(PREDISPATCH_ACTIVATION_UNITS):
            if unit not in owned_units:
                continue
            stopped = runner(
                (SYSTEMCTL_PATH, "disable", "--now", unit),
                cwd=Path("/"),
                check=False,
            )
            compensation_failed = compensation_failed or stopped.returncode != 0
        if marker_owned:
            try:
                _remove_exact_writer_marker(
                    expected_root_uid=expected_root_uid,
                    expected_root_gid=expected_root_gid,
                )
            except ReleaseContractError:
                compensation_failed = True
        compensation_failed = compensation_failed or not (
            _predispatch_compensation_is_quiet(runner=runner)
        )
        if compensation_failed:
            raise ReleaseContractError(
                "predispatch activation compensation failed"
            ) from exc
        raise


def _load_oracle_sandbox_evidence(release_sha: str) -> tuple[dict[str, Any], bytes]:
    raw, _identity = _read_exact_custodied_bytes(
        ORACLE_SANDBOX_EVIDENCE_RECEIPT,
        expected_uid=0,
        expected_gid=0,
    )
    try:
        from scripts.runtime import sadhana_oracle_sandbox

        worker_digest = sha256_file(
            Path(sadhana_oracle_sandbox.WORKER_UNIT_PATH),
            max_bytes=256 * 1024,
        )
        payload = sadhana_oracle_sandbox._decode_evidence(  # noqa: SLF001
            raw,
            release_sha=release_sha,
            worker_unit_sha256=worker_digest,
        )
    except (ImportError, RuntimeError, TypeError, ValueError) as exc:
        raise ReleaseContractError("oracle sandbox evidence is invalid") from exc
    return payload, raw


def _publish_supervisor_activation_env(
    *,
    observer_health_raw: bytes,
    oracle_evidence: Mapping[str, Any],
    destination: Path = SUPERVISOR_ACTIVATION_ENV,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> bytes:
    oracle_digest = oracle_evidence.get("receipt_digest")
    if not isinstance(oracle_digest, str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", oracle_digest
    ):
        raise ReleaseContractError("oracle sandbox evidence digest differs")
    raw = (
        "SADHANA_OBSERVER_HEALTH_RECEIPT_SHA256="
        f"{hashlib.sha256(observer_health_raw).hexdigest()}\n"
        f"SADHANA_ORACLE_SANDBOX_EVIDENCE_SHA256={oracle_digest}\n"
    ).encode("ascii")
    _publish_or_replay_exact_bytes(
        destination,
        raw,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        maximum_bytes=4096,
    )
    return raw


def _load_predispatch_activation_for_dispatch(
    *,
    release_sha: str,
    expected_root_uid: int,
    expected_root_gid: int,
) -> dict[str, Any]:
    activation, _raw, _identity = _read_exact_canonical_json(
        PREDISPATCH_ACTIVATION_RECEIPT,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=PREDISPATCH_ACTIVATION_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    staged_digest = activation.get("staged_release_admission_receipt_digest")
    if (
        set(activation) != _PREDISPATCH_ACTIVATION_FIELDS
        or activation.get("campaign_id") != MISSION_ID
        or activation.get("release_sha") != release_sha
        or not isinstance(staged_digest, str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", staged_digest)
        or activation.get("writer_marker_present") is not True
        or activation.get("predispatch_target_active") is not True
        or activation.get("dispatch_target_inactive") is not True
        or activation.get("provider_dispatch") != "NoProviderDispatch"
    ):
        raise ReleaseContractError("predispatch activation receipt differs")
    return activation


def _fence_runtime_preparation(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """Stop the refreshable no-effect writer before dispatch authority exists."""
    if _unit_active(RUNTIME_PREPARATION_UNIT, runner=runner):
        stopped = runner(
            (SYSTEMCTL_PATH, "stop", RUNTIME_PREPARATION_UNIT),
            cwd=Path("/"),
            check=False,
        )
        if stopped.returncode != 0 or stopped.stdout or stopped.stderr:
            raise ReleaseContractError("runtime preparation fence failed")
    if (
        not _unit_inactive(RUNTIME_PREPARATION_UNIT, runner=runner)
        or not _unit_static(RUNTIME_PREPARATION_UNIT, runner=runner)
        or _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0
    ):
        raise ReleaseContractError("runtime preparation fence is not quiet")


def enable_dispatch(
    *,
    role: str,
    release_sha: str,
    marker_path: Path = DISPATCH_ENABLE_MARKER,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    proc_root: Path = Path("/proc"),
    now: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
    positive_read_probe: Callable[..., dict[str, Any]] = (
        _default_positive_bearer_read_probe
    ),
) -> dict[str, Any]:
    """Create dispatch authority only after a separately started observer phase."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("dispatch enablement requires root")
    _require_host_role(role, observed_node=observed_node)
    if role != "writer" or not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("dispatch enablement release binding differs")
    if marker_path != DISPATCH_ENABLE_MARKER:
        raise ReleaseContractError("dispatch authority marker path differs")
    observed = _sample_utc(
        now=now,
        clock=clock,
        label="dispatch enablement",
    )
    guard_campaign_clock(role=role, now=observed, observed_node=observed_node)
    marker_replay = marker_path.exists() or marker_path.is_symlink()
    activation = _load_predispatch_activation_for_dispatch(
        release_sha=release_sha,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    clock_proof = validate_preactivation_clock_proof(
        release_sha=release_sha,
        role=role,
        known_hosts_sha256=DEPLOYMENT_KNOWN_HOSTS_SHA256,
        staged_release_admission_receipt_digest=activation[
            "staged_release_admission_receipt_digest"
        ],
        now=observed,
        observed_node=observed_node,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    refresh = validate_predispatch_refresh_receipt(
        role=role,
        release_sha=release_sha,
        runner=runner,
        now=observed,
        observed_node=observed_node,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
        require_preparation_active=not marker_replay,
    )
    capacity = guard_standby_capacity(
        role=role,
        release_sha=release_sha,
        projection_path=WRITER_PROJECTION_PATH,
        now=observed,
        observed_node=observed_node,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if marker_replay:
        if (
            not _unit_inactive(RUNTIME_PREPARATION_UNIT, runner=runner)
            or not _unit_static(RUNTIME_PREPARATION_UNIT, runner=runner)
        ):
            raise ReleaseContractError("runtime preparation replay fence differs")
    else:
        _fence_runtime_preparation(runner=runner)
    live = _revalidate_live_predispatch(
        release_sha=release_sha,
        runner=runner,
        proc_root=proc_root,
        now=observed,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
        positive_read_probe=positive_read_probe,
    )
    health = live["health"]
    dashboard = live["dashboard"]
    credentials = live["credentials"]
    staging = live["staging"]
    binding = live["binding"]
    standby_route_probe = _load_standby_replication_route_probe(
        release_sha=release_sha,
        now=observed,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    _observer_payload, observer_raw, _observer_identity = (
        _read_exact_custodied_json(
            OBSERVER_HEALTH_RECEIPT,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
        )
    )
    oracle_evidence, _oracle_raw = _load_oracle_sandbox_evidence(release_sha)
    activation_env = _publish_supervisor_activation_env(
        observer_health_raw=observer_raw,
        oracle_evidence=oracle_evidence,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    observed = _sample_utc(
        now=now,
        clock=clock,
        label="dispatch enablement publication",
    )
    guard_campaign_clock(role=role, now=observed, observed_node=observed_node)
    clock_proof = validate_preactivation_clock_proof(
        release_sha=release_sha,
        role=role,
        known_hosts_sha256=DEPLOYMENT_KNOWN_HOSTS_SHA256,
        staged_release_admission_receipt_digest=activation[
            "staged_release_admission_receipt_digest"
        ],
        now=observed,
        observed_node=observed_node,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    refresh = validate_predispatch_refresh_receipt(
        role=role,
        release_sha=release_sha,
        runner=runner,
        now=observed,
        observed_node=observed_node,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
        require_preparation_active=False,
    )
    capacity = guard_standby_capacity(
        role=role,
        release_sha=release_sha,
        projection_path=WRITER_PROJECTION_PATH,
        now=observed,
        observed_node=observed_node,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    account_confirmation = dashboard.get("authenticated_account_ui_confirmation")
    if not isinstance(account_confirmation, Mapping):
        raise ReleaseContractError("dispatch account UI confirmation differs")
    _validate_account_ui_confirmation_payload(
        account_confirmation,
        release_sha=release_sha,
        now=observed,
        operator_login_sha256=str(dashboard.get("operator_login_sha256", "")),
    )
    _require_live_writer_service_units(
        release_sha=release_sha,
        runner=runner,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if marker_path.exists() or marker_path.is_symlink():
        prior, _raw, _identity = _read_exact_canonical_json(
            marker_path,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
            expected_schema=DISPATCH_ENABLE_SCHEMA_VERSION,
            digest_field="receipt_digest",
        )
        if (
            set(prior) != _DISPATCH_ENABLE_FIELDS
            or prior.get("campaign_id") != MISSION_ID
            or prior.get("release_sha") != release_sha
            or prior.get("predispatch_target_active") is not True
            or prior.get("supervisor_main_pid_before_enable") != 0
            or prior.get("observer_health_receipt_digest")
            != health["receipt_digest"]
            or prior.get("dashboard_identity_receipt_digest")
            != dashboard["receipt_digest"]
            or prior.get("operator_credential_receipt_digest")
            != credentials["receipt_digest"]
            or prior.get("runtime_staging_receipt_digest")
            != staging["receipt_digest"]
            or prior.get("runtime_binding_receipt_digest")
            != binding["receipt_digest"]
            or prior.get("predispatch_refresh_receipt_digest")
            != refresh["receipt_digest"]
            or prior.get("standby_capacity_receipt_digest")
            != capacity["receipt_digest"]
            or prior.get("preactivation_clock_proof_receipt_digest")
            != clock_proof["receipt_digest"]
            or prior.get("oracle_sandbox_evidence_digest")
            != oracle_evidence["receipt_digest"]
            or prior.get("standby_replication_route_probe_receipt_digest")
            != standby_route_probe["receipt_digest"]
            or prior.get("supervisor_activation_env_sha256")
            != hashlib.sha256(activation_env).hexdigest()
            or prior.get("dispatch_authorized") is not True
            or prior.get("effect_executed") is not False
        ):
            raise ReleaseContractError("dispatch authority marker differs")
        return prior
    payload: dict[str, Any] = {
        "schema_version": DISPATCH_ENABLE_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "enabled_at": observed.isoformat().replace("+00:00", "Z"),
        "predispatch_target_active": True,
        "supervisor_main_pid_before_enable": 0,
        "observer_health_receipt_digest": health["receipt_digest"],
        "dashboard_identity_receipt_digest": dashboard["receipt_digest"],
        "operator_credential_receipt_digest": credentials["receipt_digest"],
        "runtime_staging_receipt_digest": staging["receipt_digest"],
        "runtime_binding_receipt_digest": binding["receipt_digest"],
        "predispatch_refresh_receipt_digest": refresh["receipt_digest"],
        "standby_capacity_receipt_digest": capacity["receipt_digest"],
        "preactivation_clock_proof_receipt_digest": clock_proof[
            "receipt_digest"
        ],
        "oracle_sandbox_evidence_digest": oracle_evidence["receipt_digest"],
        "standby_replication_route_probe_receipt_digest": standby_route_probe[
            "receipt_digest"
        ],
        "supervisor_activation_env_sha256": hashlib.sha256(
            activation_env
        ).hexdigest(),
        "dispatch_authorized": True,
        "effect_executed": False,
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    if set(payload) != _DISPATCH_ENABLE_FIELDS:
        raise ReleaseContractError("dispatch authority marker fields differ")
    return _publish_or_replay_private_receipt(
        marker_path,
        payload,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )


def _dispatch_activation_source(
    *,
    marker: Mapping[str, Any],
    dashboard: Mapping[str, Any],
    binding: Mapping[str, Any],
    operator_login: str,
) -> dict[str, Any]:
    account_confirmation = dashboard.get("authenticated_account_ui_confirmation")
    if not isinstance(account_confirmation, Mapping):
        raise ReleaseContractError("dispatch activation account confirmation differs")
    source: dict[str, Any] = {
        "schema_version": "dharma.sadhana.dispatch_activation_resume_source.v1",
        "campaign_id": MISSION_ID,
        "release_sha": marker["release_sha"],
        "dispatch_enable_receipt_digest": marker["receipt_digest"],
        "dashboard_identity_receipt_digest": dashboard["receipt_digest"],
        "account_ui_confirmation_receipt_digest": account_confirmation[
            "receipt_digest"
        ],
        "runtime_binding_receipt_digest": binding["receipt_digest"],
        "config_digest": binding["config_digest"],
        "session_id": f"mission_campaign:{MISSION_ID}",
        "campaign_generation": 1,
        "transition_sequence": 2,
        "prior_control_state": "PAUSED",
        "next_control_state": "RUNNING",
        "operator_login_sha256": hashlib.sha256(
            operator_login.encode("ascii")
        ).hexdigest(),
        "effect": "NoEffect",
    }
    if set(source) != _DISPATCH_ACTIVATION_SOURCE_FIELDS:
        raise ReleaseContractError("dispatch activation source fields differ")
    return source


def _validate_dispatch_activation_credentials(
    *,
    release_sha: str,
    marker: Mapping[str, Any],
    dashboard: Mapping[str, Any],
    binding: Mapping[str, Any],
) -> None:
    account_confirmation = dashboard.get("authenticated_account_ui_confirmation")
    expected_confirmation = {
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "viewport_width_css_px_reported": 390,
        "document_width_css_px_reported": 390,
        "visual_viewport_width_css_px_reported": 390,
        "coarse_pointer_reported": True,
        "touch_capability_reported": True,
        "trusted_browser_event_reported": True,
        "explicit_confirmation_gesture_reported": True,
        "dashboard_rendered_reported": True,
        "private_tailnet_https": True,
        "identity_header_injected": True,
        "operator_account_allowlist_match": True,
        "normal_control_request_sent": False,
        "external_message_sent": False,
        "physical_device_attested": False,
        "human_identity_attested": False,
    }
    if (
        set(marker) != _DISPATCH_ENABLE_FIELDS
        or marker.get("campaign_id") != MISSION_ID
        or marker.get("release_sha") != release_sha
        or marker.get("dispatch_authorized") is not True
        or marker.get("effect_executed") is not False
        or set(dashboard) != _DASHBOARD_IDENTITY_RECEIPT_FIELDS
        or dashboard.get("campaign_id") != MISSION_ID
        or dashboard.get("release_sha") != release_sha
        or dashboard.get("verdict") != "PASS"
        or marker.get("dashboard_identity_receipt_digest")
        != dashboard.get("receipt_digest")
        or not isinstance(account_confirmation, Mapping)
        or dashboard.get("operator_login_sha256")
        != account_confirmation.get("operator_login_sha256")
        or set(account_confirmation) != _ACCOUNT_UI_CONFIRMATION_FIELDS
        or any(
            account_confirmation.get(key) != value
            for key, value in expected_confirmation.items()
        )
        or not _account_ui_field_types_exact(
            account_confirmation,
            additional_boolean_fields=(
                "normal_and_emergency_inboxes_unchanged",
            ),
        )
        or account_confirmation.get("receipt_digest")
        != _canonical_self_digest(account_confirmation, "receipt_digest")
        or set(binding) != _RUNTIME_BINDING_FIELDS
        or binding.get("schema_version") != RUNTIME_BINDING_SCHEMA_VERSION
        or binding.get("campaign_id") != MISSION_ID
        or binding.get("mission_id") != MISSION_ID
        or binding.get("release_sha") != release_sha
        or marker.get("runtime_binding_receipt_digest")
        != binding.get("receipt_digest")
        or binding.get("session_generation") != 1
        or binding.get("session_status") != "paused"
        or binding.get("prepared_proof_type")
        != "Prepared<Mission,Release,InputSet,Config,TaskSet,ProjectionContract>"
        or binding.get("prepared_effect") != "NoEffect"
        or binding.get("root_verification_type")
        != "RootVerified<Prepared<Mission,Release,InputSet,Config,TaskSet,"
        "ProjectionContract>>"
        or not isinstance(binding.get("config_digest"), str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", binding["config_digest"]) is None
    ):
        raise ReleaseContractError("dispatch activation credential binding differs")


async def _campaign_dispatch_rows(
    runtime: Any,
    *,
    session_id: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    claims = await runtime.list_task_claims(session_id=session_id, limit=10_000)
    runs = await runtime.list_delegation_runs(session_id=session_id, limit=10_000)
    return (
        tuple(sorted(claim.claim_id for claim in claims)),
        tuple(sorted(run.run_id for run in runs)),
    )


def _require_empty_activation_directory(
    path: Path,
    *,
    expected_uid: int,
    expected_gid: int,
    expected_mode: int,
    label: str,
) -> None:
    """Stable-read one exact inbox and require that it has no direct entries."""
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow or not path.is_absolute():
        raise ReleaseContractError(f"{label} path differs")
    try:
        identity = path.lstat()
    except OSError as exc:
        raise ReleaseContractError(f"{label} is unavailable") from exc
    if (
        path.is_symlink()
        or not stat.S_ISDIR(identity.st_mode)
        or identity.st_uid != expected_uid
        or identity.st_gid != expected_gid
        or stat.S_IMODE(identity.st_mode) != expected_mode
    ):
        raise ReleaseContractError(f"{label} custody differs")
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | nofollow)
    try:
        before = os.fstat(descriptor)
        names = tuple(sorted(os.listdir(descriptor)))
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        names
        or (
            before.st_dev,
            before.st_ino,
            before.st_uid,
            before.st_gid,
            before.st_mode,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        != (
            after.st_dev,
            after.st_ino,
            after.st_uid,
            after.st_gid,
            after.st_mode,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
    ):
        raise ReleaseContractError(f"{label} is not stably empty")


def _read_campaign_activation_proof(
    path: Path,
    *,
    service_uid: int,
    control_gid: int,
) -> tuple[dict[str, Any], bytes]:
    """Stable-read the group-readable, service-owned boot-epoch proof."""
    parent = path.parent.lstat()
    identity = path.lstat()
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if (
        not nofollow
        or path.parent.is_symlink()
        or not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid != service_uid
        or parent.st_gid != control_gid
        or stat.S_IMODE(parent.st_mode) != 0o750
        or path.is_symlink()
        or not stat.S_ISREG(identity.st_mode)
        or identity.st_uid != service_uid
        or identity.st_gid != control_gid
        or stat.S_IMODE(identity.st_mode) != 0o640
        or identity.st_nlink != 1
        or not 0 < identity.st_size <= _MAX_JSON_BYTES
    ):
        raise ReleaseContractError("campaign activation proof custody differs")
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        before = os.fstat(descriptor)
        raw = os.read(descriptor, _MAX_JSON_BYTES + 1)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        len(raw) != identity.st_size
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    ):
        raise ReleaseContractError("campaign activation proof changed during read")
    try:
        payload = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseContractError("campaign activation proof JSON differs") from exc
    if (
        not isinstance(payload, dict)
        or raw != _canonical_bytes(payload) + b"\n"
        or set(payload) != _CAMPAIGN_ACTIVATION_PROOF_FIELDS
        or payload.get("schema_version") != CAMPAIGN_ACTIVATION_SCHEMA_VERSION
        or payload.get("receipt_digest")
        != _canonical_self_digest(payload, "receipt_digest")
    ):
        raise ReleaseContractError("campaign activation proof bytes differ")
    return payload, raw


def _publish_campaign_activation_proof(
    path: Path,
    payload: Mapping[str, Any],
    *,
    service_uid: int,
    control_gid: int,
) -> dict[str, Any]:
    raw = _canonical_bytes(payload) + b"\n"
    if path.exists() or path.is_symlink():
        prior, prior_raw = _read_campaign_activation_proof(
            path,
            service_uid=service_uid,
            control_gid=control_gid,
        )
        if prior_raw != raw:
            raise ReleaseContractError("campaign activation proof conflicts")
        return prior
    parent = path.parent.lstat()
    if (
        path.parent.is_symlink()
        or not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid != service_uid
        or parent.st_gid != control_gid
        or stat.S_IMODE(parent.st_mode) != 0o750
    ):
        raise ReleaseContractError("campaign activation proof parent differs")
    descriptor, temporary_raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_raw)
    try:
        os.fchmod(descriptor, 0o640)
        os.fchown(descriptor, service_uid, control_gid)
        _write_all(descriptor, raw)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        parent_descriptor = os.open(
            path.parent,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            _rename_noreplace_at(
                parent_descriptor,
                temporary.name,
                parent_descriptor,
                path.name,
            )
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
    admitted, _raw = _read_campaign_activation_proof(
        path,
        service_uid=service_uid,
        control_gid=control_gid,
    )
    if admitted != payload:
        raise ReleaseContractError("campaign activation proof changed on publish")
    return admitted


async def activate_campaign_session(
    *,
    role: str,
    release_sha: str,
    dispatch_receipt_path: Path = DISPATCH_ACTIVATION_CREDENTIAL,
    dashboard_receipt_path: Path = DASHBOARD_IDENTITY_CREDENTIAL,
    runtime_binding_path: Path = RUNTIME_BINDING_CREDENTIAL,
    operator_login_path: Path = OPERATOR_LOGIN_CREDENTIAL,
    control_hmac_path: Path = CONTROL_HMAC_CREDENTIAL,
    credential_root: Path = SUPERVISOR_CREDENTIAL_ROOT,
    state_root: Path = Path(STATE_ROOT),
    control_gate_path: Path = Path(f"{STATE_ROOT}/writer.lock.control"),
    activation_evidence_path: Path = CAMPAIGN_ACTIVATION_PROOF,
    runtime_store: Any | None = None,
    now: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Apply or replay the unique typed seq2 resume after dispatch authority."""
    service = _require_static_service_identity()
    try:
        control = pwd.getpwnam("dharma-sadhana-control")
    except KeyError as exc:
        raise ReleaseContractError("control service identity is absent") from exc
    if os.geteuid() != service.pw_uid or os.getegid() != service.pw_gid:
        raise ReleaseContractError(
            "campaign activation must run as the static service identity"
        )
    _require_host_role(role, observed_node=observed_node)
    if role != "writer" or _COMMIT_RE.fullmatch(release_sha) is None:
        raise ReleaseContractError("campaign activation release binding differs")
    if (
        control.pw_uid == 0
        or control.pw_gid == 0
        or activation_evidence_path != CAMPAIGN_ACTIVATION_PROOF
    ):
        raise ReleaseContractError("campaign activation evidence topology differs")
    initial_observed = _sample_utc(
        now=now,
        clock=clock,
        label="campaign activation admission",
    )
    guard_campaign_clock(
        role=role,
        now=initial_observed,
        observed_node=observed_node,
    )

    marker = _read_supervisor_json_credential(
        dispatch_receipt_path,
        credential_root=credential_root,
        expected_name="dispatch_activation_receipt",
        expected_uid=service.pw_uid,
        expected_gid=service.pw_gid,
        expected_schema=DISPATCH_ENABLE_SCHEMA_VERSION,
    )
    dashboard = _read_supervisor_json_credential(
        dashboard_receipt_path,
        credential_root=credential_root,
        expected_name="dashboard_identity_receipt",
        expected_uid=service.pw_uid,
        expected_gid=service.pw_gid,
        expected_schema=DASHBOARD_IDENTITY_SCHEMA_VERSION,
    )
    binding = _read_supervisor_json_credential(
        runtime_binding_path,
        credential_root=credential_root,
        expected_name="runtime_binding_activation",
        expected_uid=service.pw_uid,
        expected_gid=service.pw_gid,
        expected_schema=RUNTIME_BINDING_SCHEMA_VERSION,
    )
    _validate_dispatch_activation_credentials(
        release_sha=release_sha,
        marker=marker,
        dashboard=dashboard,
        binding=binding,
    )
    login_raw = _read_supervisor_credential_bytes(
        operator_login_path,
        credential_root=credential_root,
        expected_name="tailscale_operator_login",
        expected_uid=service.pw_uid,
        expected_gid=service.pw_gid,
        minimum_bytes=1,
        maximum_bytes=254,
    )
    control_hmac_key = _read_supervisor_credential_bytes(
        control_hmac_path,
        credential_root=credential_root,
        expected_name="control_hmac_key",
        expected_uid=service.pw_uid,
        expected_gid=service.pw_gid,
        minimum_bytes=32,
        maximum_bytes=4096,
    )
    control_gate: Any | None = None
    if (
        hashlib.sha256(login_raw).hexdigest()
        != dashboard.get("operator_login_sha256")
    ):
        raise ReleaseContractError("campaign activation operator principal differs")
    try:
        operator_login = login_raw.decode("ascii")
        from dharma_swarm.mission_control_operator_control import (  # noqa: PLC0415
            ControlAction,
            OperatorControlEnvelope,
            OperatorControlRequest,
            validate_operator_login,
        )

        if validate_operator_login(operator_login) != operator_login:
            raise ReleaseContractError("campaign activation operator login differs")
    except (UnicodeError, ValueError) as exc:
        raise ReleaseContractError("campaign activation operator login differs") from exc

    source = _dispatch_activation_source(
        marker=marker,
        dashboard=dashboard,
        binding=binding,
        operator_login=operator_login,
    )
    source_claim_digest = "sha256:" + hashlib.sha256(
        _canonical_bytes(source)
    ).hexdigest()
    token = source_claim_digest.removeprefix("sha256:")[:24]
    request_id = f"sadhana-dispatch-resume-{token}"
    idempotency_key = f"sadhana-dispatch-resume-v1-{token}"
    reason = f"Resume exact dispatch activation source {source_claim_digest}."
    marker_enabled_at = _parse_utc(
        str(marker.get("enabled_at")),
        "dispatch enabled_at",
    )
    session_id = f"mission_campaign:{MISSION_ID}"
    database = state_root / "state/runtime.db"
    try:
        from dharma_swarm.mission_control_operator_authority import (  # noqa: PLC0415
            CampaignOperatorAuthority,
        )
        from dharma_swarm.mission_control_operator_state import (  # noqa: PLC0415
            OPERATOR_CONTROL_RECEIPT_TYPE,
            runtime_receipt_content_digest,
            validate_operator_control_state,
        )
        from dharma_swarm.mission_control_contract import stable_id  # noqa: PLC0415
        from dharma_swarm.mission_control_service import (  # noqa: PLC0415
            CampaignControlGate,
        )
        from dharma_swarm.runtime_state import RuntimeStateStore  # noqa: PLC0415

        resolved_state_root = state_root.resolve(strict=False)
        resolved_control_gate = control_gate_path.resolve(strict=False)
        if (
            not control_gate_path.is_absolute()
            or not resolved_control_gate.is_relative_to(resolved_state_root)
            or not control_gate_path.name.endswith(".control")
        ):
            raise ReleaseContractError("campaign activation control gate differs")
        _require_secure_parent_chain(control_gate_path)
        if control_gate_path.exists() or control_gate_path.is_symlink():
            gate_identity = control_gate_path.lstat()
            if (
                control_gate_path.is_symlink()
                or not stat.S_ISREG(gate_identity.st_mode)
                or gate_identity.st_uid != service.pw_uid
                or gate_identity.st_gid != service.pw_gid
                or stat.S_IMODE(gate_identity.st_mode) != 0o600
                or gate_identity.st_nlink != 1
            ):
                raise ReleaseContractError("campaign activation control gate custody differs")
        control_gate = CampaignControlGate(control_gate_path)
        await control_gate.__aenter__()
        observed = _sample_utc(
            now=now,
            clock=clock,
            label="campaign activation",
        )
        guard_campaign_clock(role=role, now=observed, observed_node=observed_node)
        runtime = runtime_store or RuntimeStateStore(
            database,
            include_memory_plane=False,
        )
        if Path(runtime.db_path).resolve(strict=False) != database.resolve(strict=False):
            raise ReleaseContractError("campaign activation runtime path differs")
        expected_receipt_id = stable_id(
            "mission_campaign_operator_control",
            MISSION_ID,
            idempotency_key,
        )
        existing_receipt = await runtime.get_runtime_receipt(expected_receipt_id)
        if existing_receipt is None:
            if not marker_enabled_at <= observed < marker_enabled_at + timedelta(
                seconds=120
            ):
                raise ReleaseContractError(
                    "fresh campaign activation dispatch marker is not timely"
                )
            issued_at = observed.replace(microsecond=0)
            request_mapping = {
                "action": ControlAction.RESUME.value,
                "request_id": request_id,
                "idempotency_key": idempotency_key,
                "issued_at": issued_at.isoformat().replace("+00:00", "Z"),
                "expires_at": (issued_at + timedelta(seconds=120))
                .isoformat()
                .replace("+00:00", "Z"),
                "reason": reason,
            }
            signing_time = observed
        else:
            existing_payload = existing_receipt.payload
            request_mapping = {
                "action": existing_payload.get("action"),
                "request_id": existing_payload.get("request_id"),
                "idempotency_key": existing_payload.get("idempotency_key"),
                "issued_at": existing_payload.get("issued_at"),
                "expires_at": existing_payload.get("expires_at"),
                "reason": existing_payload.get("reason"),
            }
            signing_time = _parse_utc(
                str(existing_payload.get("issued_at")),
                "campaign activation issued_at",
            )
        request = OperatorControlRequest.from_mapping(request_mapping)
        envelope = OperatorControlEnvelope.sign(
            request,
            operator_login=operator_login,
            secret=control_hmac_key,
            now=signing_time,
        )
        source_digest = envelope.envelope_sha256
        before = await runtime.get_session(session_id)
        if before is None:
            raise ReleaseContractError("prepared campaign session is absent")
        before_state = validate_operator_control_state(
            before.metadata.get("operator_control_state"),
            expected_generation=1,
        )
        common_session_valid = (
            before.metadata.get("mission_id") == MISSION_ID
            and before.metadata.get("config_digest") == binding["config_digest"]
            and before.metadata.get("generation") == 1
            and before.metadata.get("stop_requested") is False
        )
        fresh_pause = (
            before.status == "paused"
            and before_state.get("control_state") == "PAUSED"
            and before_state.get("campaign_generation") == 1
            and before_state.get("transition_sequence") == 1
            and before_state.get("request_id")
            == "sadhana-runtime-preparation-pause"
            and before_state.get("idempotency_key")
            == "sadhana-runtime-preparation-pause-v1"
            and before_state.get("action") == "pause"
            and before_state.get("effect_state") == "unobserved"
        )
        exact_replay = (
            before.status == "active"
            and before_state.get("control_state") == "RUNNING"
            and before_state.get("campaign_generation") == 1
            and before_state.get("transition_sequence") == 2
            and before_state.get("request_id") == request_id
            and before_state.get("idempotency_key") == idempotency_key
            and before_state.get("action") == "resume"
            and before_state.get("source_envelope_sha256") == source_digest
            and before_state.get("effect_state") == "unobserved"
        )
        if not common_session_valid or not (fresh_pause or exact_replay):
            raise ReleaseContractError("campaign activation prior state differs")
        if exact_replay and existing_receipt is None:
            raise ReleaseContractError("campaign activation receipt is absent")
        dispatch_rows_before = await _campaign_dispatch_rows(
            runtime,
            session_id=session_id,
        )
        if fresh_pause and dispatch_rows_before != ((), ()):
            raise ReleaseContractError("campaign activation found dispatch rows")
        if fresh_pause:
            if EMERGENCY_STOP_MARKER.exists() or EMERGENCY_STOP_MARKER.is_symlink():
                raise ReleaseContractError("campaign activation found emergency stop")
            for directory, uid, gid, mode, label in (
                (
                    CONTROL_NORMAL_INBOX,
                    expected_root_uid,
                    control.pw_gid,
                    0o770,
                    "campaign activation normal inbox",
                ),
                (
                    CONTROL_INFLIGHT_ROOT,
                    service.pw_uid,
                    service.pw_gid,
                    0o700,
                    "campaign activation normal inflight",
                ),
                (
                    CONTROL_EMERGENCY_INBOX,
                    expected_root_uid,
                    control.pw_gid,
                    0o770,
                    "campaign activation emergency inbox",
                ),
                (
                    EMERGENCY_INFLIGHT_ROOT,
                    expected_root_uid,
                    expected_root_gid,
                    0o700,
                    "campaign activation emergency inflight",
                ),
            ):
                _require_empty_activation_directory(
                    directory,
                    expected_uid=uid,
                    expected_gid=gid,
                    expected_mode=mode,
                    label=label,
                )

        apply_observed = _sample_utc(
            now=now,
            clock=clock,
            label="campaign activation application",
        )
        guard_campaign_clock(
            role=role,
            now=apply_observed,
            observed_node=observed_node,
        )
        if fresh_pause:
            if not marker_enabled_at <= apply_observed < (
                marker_enabled_at + timedelta(seconds=120)
            ):
                raise ReleaseContractError(
                    "fresh campaign activation dispatch marker is not timely"
                )
            account_confirmation = dashboard.get(
                "authenticated_account_ui_confirmation"
            )
            if not isinstance(account_confirmation, Mapping):
                raise ReleaseContractError(
                    "campaign activation account confirmation differs"
                )
            _validate_account_ui_confirmation_payload(
                account_confirmation,
                release_sha=release_sha,
                now=apply_observed,
                operator_login_sha256=hashlib.sha256(login_raw).hexdigest(),
            )
        application = await CampaignOperatorAuthority(
            runtime,
            mission_id=MISSION_ID,
            session_id=session_id,
            config_digest=binding["config_digest"],
            now=lambda: apply_observed,
        ).apply(request, operator_login, source_digest)
        if application.status != "applied":
            raise ReleaseContractError("campaign activation was not applied")
        receipt_id = application.authority_receipt_ref.removeprefix(
            "runtime-receipt:"
        )
        receipt = await runtime.get_runtime_receipt(receipt_id)
        if receipt is None:
            raise ReleaseContractError("campaign activation receipt is absent")
        payload = receipt.payload
        expected_payload = {
            "mission_id": MISSION_ID,
            "config_digest": binding["config_digest"],
            "campaign_generation": 1,
            "transition_sequence": 2,
            "request_id": request_id,
            "idempotency_key": idempotency_key,
            "action": "resume",
            "issued_at": request.issued_at,
            "expires_at": request.expires_at,
            "reason": reason,
            "operator_login": operator_login,
            "source_envelope_sha256": source_digest,
            "prior_control_state": "PAUSED",
            "next_control_state": "RUNNING",
            "application_status": "applied",
            "rejection_reason": "",
            "preserves_queued_work": True,
            "external_effect_performed": False,
        }
        if (
            receipt.receipt_type != OPERATOR_CONTROL_RECEIPT_TYPE
            or receipt.receipt_id != expected_receipt_id
            or receipt.status != "applied"
            or receipt.correlation_id != session_id
            or receipt.agent_id != "mission-control-supervisor"
            or receipt.idempotency_key != idempotency_key
            or receipt.side_effect_key
            != f"mission_campaign_operator_control:{idempotency_key}"
            or any(payload.get(key) != value for key, value in expected_payload.items())
            or application.request_id != request_id
            or application.idempotency_key != idempotency_key
            or application.envelope_sha256 != source_digest
            or application.authority_receipt_ref
            != f"runtime-receipt:{expected_receipt_id}"
            or application.authority_receipt_sha256
            != runtime_receipt_content_digest(receipt)
        ):
            raise ReleaseContractError("campaign activation receipt differs")
        after = await runtime.get_session(session_id)
        if after is None:
            raise ReleaseContractError("activated campaign session is absent")
        after_state = validate_operator_control_state(
            after.metadata.get("operator_control_state"),
            expected_generation=1,
        )
        if (
            after.status != "active"
            or after.metadata.get("mission_id") != MISSION_ID
            or after.metadata.get("config_digest") != binding["config_digest"]
            or after.metadata.get("generation") != 1
            or after.metadata.get("stop_requested") is not False
            or after_state.get("control_state") != "RUNNING"
            or after_state.get("transition_sequence") != 2
            or after_state.get("request_id") != request_id
            or after_state.get("idempotency_key") != idempotency_key
            or after_state.get("action") != "resume"
            or after_state.get("source_envelope_sha256") != source_digest
            or after_state.get("authority_receipt_ref")
            != application.authority_receipt_ref
            or after_state.get("authority_receipt_sha256")
            != application.authority_receipt_sha256
            or after_state.get("effect_state") != "unobserved"
            or await _campaign_dispatch_rows(runtime, session_id=session_id)
            != dispatch_rows_before
        ):
            raise ReleaseContractError("campaign activation postcondition differs")
        activated_at = request.issued_at
        _parse_utc(str(activated_at), "campaign activation activated_at")
        evidence: dict[str, Any] = {
            "schema_version": CAMPAIGN_ACTIVATION_SCHEMA_VERSION,
            "mission_id": MISSION_ID,
            "release_sha": release_sha,
            "config_digest": binding["config_digest"],
            "campaign_generation": 1,
            "transition_sequence": 2,
            "control_state": "RUNNING",
            "action": "resume",
            "dispatch_enable_receipt_digest": marker["receipt_digest"],
            "account_ui_confirmation_receipt_digest": source[
                "account_ui_confirmation_receipt_digest"
            ],
            "operator_login_sha256": source["operator_login_sha256"],
            "authority_receipt_ref": application.authority_receipt_ref,
            "authority_receipt_sha256": application.authority_receipt_sha256,
            "activated_at": activated_at,
            "external_effect_performed": False,
            "receipt_digest": "",
        }
        evidence["receipt_digest"] = _canonical_self_digest(
            evidence,
            "receipt_digest",
        )
        if (
            set(evidence) != _CAMPAIGN_ACTIVATION_PROOF_FIELDS
            or re.fullmatch(r"sha256:[0-9a-f]{64}", evidence["receipt_digest"])
            is None
        ):
            raise ReleaseContractError("campaign activation evidence differs")
        evidence = _publish_campaign_activation_proof(
            activation_evidence_path,
            evidence,
            service_uid=service.pw_uid,
            control_gid=control.pw_gid,
        )
    except ReleaseContractError:
        raise
    except (RuntimeError, TypeError, ValueError) as exc:
        raise ReleaseContractError("campaign activation transition failed") from exc
    finally:
        if control_gate is not None:
            await control_gate.__aexit__(None, None, None)
    return {
        "status": "campaign_session_activated",
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "session_id": session_id,
        "campaign_generation": 1,
        "transition_sequence": 2,
        "prior_control_state": "PAUSED",
        "next_control_state": "RUNNING",
        "dispatch_enable_receipt_digest": marker["receipt_digest"],
        "account_ui_confirmation_receipt_digest": source[
            "account_ui_confirmation_receipt_digest"
        ],
        "authority_receipt_ref": application.authority_receipt_ref,
        "authority_receipt_sha256": application.authority_receipt_sha256,
        "activation_evidence_path": str(activation_evidence_path),
        "activation_evidence_receipt_digest": evidence["receipt_digest"],
        "external_effect_performed": False,
    }


def _validate_standby_capacity_payload(
    payload: Mapping[str, Any],
    *,
    release_sha: str,
    now: datetime,
) -> dict[str, Any]:
    from scripts.runtime import sadhana_snapshot

    provisioned_bytes = (
        _STANDBY_CAPACITY_FIXED_ENVELOPE_ALLOWANCE_BYTES
        + _STANDBY_CAPACITY_LEDGER_ENTRY_BYTES
        * sadhana_snapshot.MAX_CAMPAIGN_SNAPSHOTS
    )
    if (
        provisioned_bytes != 620_416
        or provisioned_bytes > _MAX_STANDBY_CAPACITY_PROOF_BYTES
    ):
        raise ReleaseContractError("standby capacity proof size bound invariant differs")
    if set(payload) != _STANDBY_CAPACITY_FIELDS:
        raise ReleaseContractError("standby capacity proof fields differ")
    existing_snapshot_entries = payload.get("existing_snapshot_entries")
    zero_existing_snapshot_directories = payload.get(
        "zero_existing_snapshot_directories"
    )
    if (
        payload.get("schema_version") != STANDBY_CAPACITY_SCHEMA_VERSION
        or payload.get("campaign_id") != MISSION_ID
        or payload.get("release_sha") != release_sha
        or payload.get("hostname") != STANDBY_NODE
        or payload.get("role") != "fenced_standby"
        or payload.get("strict_host_key_channel") is not True
        or payload.get("deployment_known_hosts_sha256") != DEPLOYMENT_KNOWN_HOSTS_SHA256
        or payload.get("snapshot_root") != SNAPSHOT_ROOT
        or payload.get("snapshot_root_mode") != "0700"
        or isinstance(existing_snapshot_entries, bool)
        or not isinstance(existing_snapshot_entries, int)
        or not 0 <= existing_snapshot_entries < sadhana_snapshot.MAX_CAMPAIGN_SNAPSHOTS
        or not isinstance(zero_existing_snapshot_directories, bool)
        or zero_existing_snapshot_directories
        is not (existing_snapshot_entries == 0)
        or payload.get("silent_deletion_allowed") is not False
        or payload.get("standby_capacity_proven") is not True
        or payload.get("verdict") != "PASS"
    ):
        raise ReleaseContractError("standby capacity proof bindings differ")
    snapshot_ledger = payload.get("snapshot_ledger")
    if (
        not isinstance(snapshot_ledger, list)
        or len(snapshot_ledger) != existing_snapshot_entries
    ):
        raise ReleaseContractError("standby snapshot ledger length differs")
    ledger_ids: list[str] = []
    for entry in snapshot_ledger:
        if (
            not isinstance(entry, dict)
            or set(entry) != _STANDBY_SNAPSHOT_LEDGER_FIELDS
            or not isinstance(entry.get("snapshot_id"), str)
            or sadhana_snapshot._SNAPSHOT_DIR_RE.fullmatch(entry["snapshot_id"])
            is None
            or not isinstance(entry.get("snapshot_digest"), str)
            or re.fullmatch(r"[0-9a-f]{64}", entry["snapshot_digest"]) is None
            or not isinstance(entry.get("tree_digest"), str)
            or re.fullmatch(r"[0-9a-f]{64}", entry["tree_digest"]) is None
        ):
            raise ReleaseContractError("standby snapshot ledger entry differs")
        ledger_ids.append(entry["snapshot_id"])
    if ledger_ids != sorted(ledger_ids) or len(set(ledger_ids)) != len(ledger_ids):
        raise ReleaseContractError("standby snapshot ledger order differs")
    for field in ("snapshot_root_uid", "snapshot_root_gid"):
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ReleaseContractError("standby capacity custody identity differs")
    source_sizes = payload.get("source_sizes_bytes")
    if (
        not isinstance(source_sizes, dict)
        or set(source_sizes) != _STANDBY_SOURCE_SIZE_FIELDS
    ):
        raise ReleaseContractError("standby capacity source size fields differ")
    if any(
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 < value <= _MAX_ARTIFACT_BYTES
        for value in source_sizes.values()
    ):
        raise ReleaseContractError("standby capacity source size differs")
    source_bytes = sum(source_sizes.values())
    free_bytes = payload.get("free_bytes")
    if (
        payload.get("source_bytes") != source_bytes
        or isinstance(free_bytes, bool)
        or not isinstance(free_bytes, int)
        or free_bytes < 0
    ):
        raise ReleaseContractError("standby capacity byte totals differ")
    capacity = sadhana_snapshot.snapshot_capacity_formula(
        source_bytes=source_bytes,
        existing_snapshot_count=existing_snapshot_entries,
        free_bytes=free_bytes,
    )
    if (
        payload.get("maximum_campaign_snapshot_count")
        != sadhana_snapshot.MAX_CAMPAIGN_SNAPSHOTS
        or payload.get("snapshot_interval_seconds")
        != sadhana_snapshot.SNAPSHOT_INTERVAL_SECONDS
        or payload.get("metadata_allowance_bytes")
        != sadhana_snapshot.SNAPSHOT_METADATA_ALLOWANCE_BYTES
        or payload.get("estimate_headroom_numerator")
        != sadhana_snapshot.SNAPSHOT_ESTIMATE_HEADROOM_NUMERATOR
        or payload.get("estimate_headroom_denominator")
        != sadhana_snapshot.SNAPSHOT_ESTIMATE_HEADROOM_DENOMINATOR
        or payload.get("estimated_bytes_per_snapshot")
        != capacity["estimated_bytes_per_snapshot"]
        or payload.get("minimum_free_reserve_bytes")
        != sadhana_snapshot.MIN_FREE_RESERVE_BYTES
        or payload.get("required_free_bytes_for_remaining_series")
        != capacity["required_free_bytes_for_remaining_series"]
        or capacity["status"] != "ready"
    ):
        raise ReleaseContractError("standby capacity formula differs")
    observed = _parse_utc(str(payload.get("observed_at")), "observed_at")
    valid_until = _parse_utc(str(payload.get("valid_until")), "valid_until")
    expected_valid_until = min(
        observed + timedelta(seconds=STANDBY_CAPACITY_PROOF_FRESHNESS_SECONDS),
        _parse_utc(CAMPAIGN_STOP_UTC, "campaign_stop_utc"),
    )
    admitted_now = now.astimezone(timezone.utc)
    if (
        valid_until != expected_valid_until
        or observed
        > admitted_now + timedelta(seconds=MAX_CONTROLLER_CLOCK_SKEW_SECONDS)
        or admitted_now >= valid_until
    ):
        raise ReleaseContractError("standby capacity proof is stale or future-dated")
    if payload.get("receipt_digest") != _canonical_self_digest(
        payload, "receipt_digest"
    ):
        raise ReleaseContractError("standby capacity proof digest differs")
    if len(_canonical_bytes(payload)) + 1 > _MAX_STANDBY_CAPACITY_PROOF_BYTES:
        raise ReleaseContractError("standby capacity proof exceeds its size bound")
    return dict(payload)


def _validate_existing_standby_snapshot_series(
    snapshot_root: Path,
    *,
    release_sha: str,
    expected_root_uid: int,
    expected_root_gid: int,
    snapshot_validator: Callable[..., Any] | None = None,
    frozen_validator: Callable[..., Any] | None = None,
) -> list[dict[str, str]]:
    """Validate every direct child as one frozen, restorable campaign snapshot."""
    from scripts.runtime import sadhana_snapshot

    validator = snapshot_validator or sadhana_snapshot._validate_restorable_snapshot
    custody_validator = frozen_validator or sadhana_snapshot._assert_frozen_snapshot
    before = snapshot_root.lstat()
    entries = sorted(snapshot_root.iterdir(), key=lambda item: item.name)
    ledger: list[dict[str, str]] = []
    try:
        for child in entries:
            identity = child.lstat()
            if (
                child.is_symlink()
                or not stat.S_ISDIR(identity.st_mode)
                or sadhana_snapshot._SNAPSHOT_DIR_RE.fullmatch(child.name) is None
            ):
                raise ReleaseContractError(
                    "standby snapshot root contains a foreign entry"
                )
            manifest, tree_digest = validator(
                child,
                expected_snapshot_id=child.name,
                expected_root_uid=expected_root_uid,
                expected_release_sha=release_sha,
            )
            custody_validator(
                child,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
            snapshot_digest = manifest.get("snapshot_digest")
            if (
                not isinstance(snapshot_digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", snapshot_digest) is None
                or not isinstance(tree_digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", tree_digest) is None
            ):
                raise ReleaseContractError(
                    "standby existing snapshot digest differs"
                )
            ledger.append(
                {
                    "snapshot_id": child.name,
                    "snapshot_digest": snapshot_digest,
                    "tree_digest": tree_digest,
                }
            )
    except sadhana_snapshot.SnapshotError as exc:
        raise ReleaseContractError(
            "standby existing snapshot series is invalid"
        ) from exc
    after = snapshot_root.lstat()
    if (
        snapshot_root.is_symlink()
        or (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns)
        != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns)
        or len(entries) >= sadhana_snapshot.MAX_CAMPAIGN_SNAPSHOTS
    ):
        raise ReleaseContractError("standby snapshot series changed during proof")
    return ledger


def emit_standby_capacity_proof(
    *,
    release_sha: str,
    runtime_db_bytes: int,
    tasks_db_bytes: int,
    projection_bytes: int,
    snapshot_root: Path = Path(SNAPSHOT_ROOT),
    known_hosts_sha256: str = DEPLOYMENT_KNOWN_HOSTS_SHA256,
    strict_host_key_channel: bool,
    ssh_connection_observed: bool | None = None,
    statvfs: Callable[[Path], os.statvfs_result] = os.statvfs,
    now: datetime | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
    snapshot_validator: Callable[..., Any] | None = None,
    frozen_validator: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Emit a read-only, short-lived AGNI capacity proof for controller custody."""
    from scripts.runtime import sadhana_snapshot

    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("standby capacity proof requires root")
    hostname = _require_host_role("standby", observed_node=observed_node)
    if not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("standby capacity release SHA differs")
    if known_hosts_sha256 != DEPLOYMENT_KNOWN_HOSTS_SHA256:
        raise ReleaseContractError("standby capacity known-hosts binding differs")
    connection_observed = (
        bool(os.environ.get("SSH_CONNECTION"))
        if ssh_connection_observed is None
        else ssh_connection_observed
    )
    if not strict_host_key_channel or not connection_observed:
        raise ReleaseContractError("standby capacity proof lacks strict SSH custody")
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ReleaseContractError("standby capacity clock must be aware")
    observed = observed.astimezone(timezone.utc).replace(microsecond=0)
    guard_campaign_clock(role="standby", now=observed, observed_node=hostname)
    if snapshot_root != Path(SNAPSHOT_ROOT):
        raise ReleaseContractError("standby capacity snapshot root differs")
    root_identity = snapshot_root.lstat()
    admitted_owners = {(expected_root_uid, expected_root_gid)}
    try:
        service = pwd.getpwnam("dharma-sadhana")
    except KeyError:
        service = None
    if service is not None and service.pw_uid != 0 and service.pw_gid != 0:
        admitted_owners.add((service.pw_uid, service.pw_gid))
    if (
        snapshot_root.is_symlink()
        or not stat.S_ISDIR(root_identity.st_mode)
        or (root_identity.st_uid, root_identity.st_gid) not in admitted_owners
        or stat.S_IMODE(root_identity.st_mode) != 0o700
    ):
        raise ReleaseContractError("standby snapshot root custody differs")
    snapshot_ledger = _validate_existing_standby_snapshot_series(
        snapshot_root,
        release_sha=release_sha,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
        snapshot_validator=snapshot_validator,
        frozen_validator=frozen_validator,
    )
    existing_snapshot_count = len(snapshot_ledger)
    source_sizes = {
        "runtime_db": runtime_db_bytes,
        "tasks_db": tasks_db_bytes,
        "projection": projection_bytes,
    }
    if any(
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 < value <= _MAX_ARTIFACT_BYTES
        for value in source_sizes.values()
    ):
        raise ReleaseContractError("standby capacity source size differs")
    source_bytes = sum(source_sizes.values())
    filesystem = statvfs(snapshot_root)
    free_bytes = filesystem.f_bavail * filesystem.f_frsize
    capacity = sadhana_snapshot.snapshot_capacity_formula(
        source_bytes=source_bytes,
        existing_snapshot_count=existing_snapshot_count,
        free_bytes=free_bytes,
    )
    if capacity["status"] != "ready":
        raise ReleaseContractError("standby capacity is insufficient")
    valid_until = min(
        observed + timedelta(seconds=STANDBY_CAPACITY_PROOF_FRESHNESS_SECONDS),
        _parse_utc(CAMPAIGN_STOP_UTC, "campaign_stop_utc"),
    )
    payload: dict[str, Any] = {
        "schema_version": STANDBY_CAPACITY_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "hostname": hostname,
        "role": "fenced_standby",
        "observed_at": observed.isoformat().replace("+00:00", "Z"),
        "valid_until": valid_until.isoformat().replace("+00:00", "Z"),
        "strict_host_key_channel": True,
        "deployment_known_hosts_sha256": known_hosts_sha256,
        "snapshot_root": str(snapshot_root),
        "snapshot_root_uid": root_identity.st_uid,
        "snapshot_root_gid": root_identity.st_gid,
        "snapshot_root_mode": "0700",
        "source_sizes_bytes": source_sizes,
        "source_bytes": source_bytes,
        "existing_snapshot_entries": existing_snapshot_count,
        "snapshot_ledger": snapshot_ledger,
        "zero_existing_snapshot_directories": existing_snapshot_count == 0,
        "maximum_campaign_snapshot_count": sadhana_snapshot.MAX_CAMPAIGN_SNAPSHOTS,
        "snapshot_interval_seconds": sadhana_snapshot.SNAPSHOT_INTERVAL_SECONDS,
        "metadata_allowance_bytes": sadhana_snapshot.SNAPSHOT_METADATA_ALLOWANCE_BYTES,
        "estimate_headroom_numerator": (
            sadhana_snapshot.SNAPSHOT_ESTIMATE_HEADROOM_NUMERATOR
        ),
        "estimate_headroom_denominator": (
            sadhana_snapshot.SNAPSHOT_ESTIMATE_HEADROOM_DENOMINATOR
        ),
        "estimated_bytes_per_snapshot": capacity["estimated_bytes_per_snapshot"],
        "free_bytes": free_bytes,
        "minimum_free_reserve_bytes": sadhana_snapshot.MIN_FREE_RESERVE_BYTES,
        "required_free_bytes_for_remaining_series": capacity[
            "required_free_bytes_for_remaining_series"
        ],
        "silent_deletion_allowed": False,
        "standby_capacity_proven": True,
        "verdict": "PASS",
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    return _validate_standby_capacity_payload(
        payload,
        release_sha=release_sha,
        now=observed,
    )


def install_standby_capacity_proof_from_stdin(
    raw: bytes,
    *,
    release_sha: str,
    destination: Path = STANDBY_CAPACITY_RECEIPT_TARGET,
    now: datetime | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> Path:
    """Install the controller-captured AGNI proof without weakening its bytes."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("standby capacity installation requires root")
    _require_host_role("writer", observed_node=observed_node)
    if destination != STANDBY_CAPACITY_RECEIPT_TARGET:
        raise ReleaseContractError("standby capacity receipt destination differs")
    if (
        not 0 < len(raw) <= _MAX_STANDBY_CAPACITY_PROOF_BYTES
        or not raw.endswith(b"\n")
    ):
        raise ReleaseContractError("standby capacity receipt framing differs")
    try:
        payload = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ReleaseContractError("standby capacity receipt JSON differs") from exc
    if not isinstance(payload, dict) or raw != _canonical_bytes(payload) + b"\n":
        raise ReleaseContractError("standby capacity receipt bytes are not canonical")
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ReleaseContractError("standby capacity installation clock must be aware")
    admitted = _validate_standby_capacity_payload(
        payload,
        release_sha=release_sha,
        now=observed,
    )
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _ensure_host_directory(
        destination.parent,
        uid=expected_root_uid,
        gid=expected_root_gid,
        mode=0o700,
    )
    if destination.exists() or destination.is_symlink():
        prior, prior_raw, _identity = _read_exact_canonical_json(
            destination,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
            expected_schema=STANDBY_CAPACITY_SCHEMA_VERSION,
            digest_field="receipt_digest",
            maximum_bytes=_MAX_STANDBY_CAPACITY_PROOF_BYTES,
        )
        if prior_raw == raw:
            return destination
        prior_observed = _parse_utc(str(prior.get("observed_at")), "observed_at")
        next_observed = _parse_utc(str(admitted.get("observed_at")), "observed_at")
        prior_ledger = prior.get("snapshot_ledger")
        next_ledger = admitted.get("snapshot_ledger")
        if (
            prior.get("release_sha") != release_sha
            or next_observed <= prior_observed
            or not isinstance(prior_ledger, list)
            or not isinstance(next_ledger, list)
            or len(next_ledger) < len(prior_ledger)
            or next_ledger[: len(prior_ledger)] != prior_ledger
        ):
            raise ReleaseContractError("standby capacity replacement is not newer")
    _atomic_private_bytes(
        destination,
        raw,
        uid=expected_root_uid,
        gid=expected_root_gid,
        replace_existing=True,
    )
    return destination


def _stable_service_regular_size(
    path: Path,
    *,
    service_uid: int,
    maximum_bytes: int = _MAX_ARTIFACT_BYTES,
) -> int:
    if not path.is_absolute():
        raise ReleaseContractError("capacity source path must be absolute")
    current = Path(path.anchor)
    for part in path.parts[1:-1]:
        current /= part
        identity = current.lstat()
        mode = stat.S_IMODE(identity.st_mode)
        sticky_root = bool(identity.st_uid == 0 and identity.st_mode & stat.S_ISVTX)
        if (
            current.is_symlink()
            or not stat.S_ISDIR(identity.st_mode)
            or identity.st_uid not in {0, service_uid}
            or (mode & 0o022 and not sticky_root)
        ):
            raise ReleaseContractError("capacity source parent custody differs")
    identity = path.lstat()
    if (
        path.is_symlink()
        or not stat.S_ISREG(identity.st_mode)
        or identity.st_uid != service_uid
        or stat.S_IMODE(identity.st_mode) & 0o077
        or identity.st_nlink != 1
        or not 0 < identity.st_size <= maximum_bytes
    ):
        raise ReleaseContractError("capacity source file custody differs")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ReleaseContractError("platform lacks no-follow capacity admission")
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        opened = os.fstat(descriptor)
        stable = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    admitted_identity = (
        identity.st_dev,
        identity.st_ino,
        identity.st_size,
        identity.st_mtime_ns,
    )
    if admitted_identity != (
        opened.st_dev,
        opened.st_ino,
        opened.st_size,
        opened.st_mtime_ns,
    ) or admitted_identity != (
        stable.st_dev,
        stable.st_ino,
        stable.st_size,
        stable.st_mtime_ns,
    ):
        raise ReleaseContractError("capacity source file changed during admission")
    return identity.st_size


def guard_standby_capacity(
    *,
    role: str,
    release_sha: str,
    projection_path: Path,
    receipt_path: Path = STANDBY_CAPACITY_RECEIPT_TARGET,
    now: datetime | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
    api_env_path: Path = Path("/etc/dharma-sadhana/api.env"),
    projection_validator: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Bind a fresh AGNI proof to the still-disabled writer source bytes."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("standby capacity guard requires root")
    _require_host_role(role, observed_node=observed_node)
    if role != "writer" or receipt_path != STANDBY_CAPACITY_RECEIPT_TARGET:
        raise ReleaseContractError("standby capacity guard topology differs")
    if (
        projection_path != WRITER_PROJECTION_PATH
        or projection_path.parent != PROJECTION_SOURCE_ROOT
    ):
        raise ReleaseContractError("capacity projection path differs")
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ReleaseContractError("standby capacity guard clock must be aware")
    guard_campaign_clock(role=role, now=observed, observed_node=observed_node)
    payload, _raw, _identity = _read_exact_canonical_json(
        receipt_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=STANDBY_CAPACITY_SCHEMA_VERSION,
        digest_field="receipt_digest",
        maximum_bytes=_MAX_STANDBY_CAPACITY_PROOF_BYTES,
    )
    admitted = _validate_standby_capacity_payload(
        payload,
        release_sha=release_sha,
        now=observed,
    )
    service = _require_static_service_identity()
    state_root = Path(STATE_ROOT)
    projection_raw = _read_scoped_runtime_source(
        projection_path,
        parent_uid=service.pw_uid,
        parent_gid=service.pw_gid,
        file_uid=service.pw_uid,
        file_gid=service.pw_gid,
        maximum_bytes=32 * 1024 * 1024,
    )
    api = _private_env_bindings(api_env_path)
    required_api = {
        "DHARMA_MISSION_SNAPSHOT_CONFIG_DIGEST",
        "DHARMA_MISSION_SNAPSHOT_MAX_AGE_SECONDS",
        "DHARMA_MISSION_SNAPSHOT_MIN_GENERATION",
    }
    if not required_api <= set(api):
        raise ReleaseContractError("api.env lacks projection validation bindings")
    validator = projection_validator
    if validator is None:
        try:
            from api.mission_snapshot_validation import validate_campaign_projection
        except ImportError as exc:
            raise ReleaseContractError("projection validator is unavailable") from exc
        validator = validate_campaign_projection
    try:
        validator(
            projection_raw,
            mission_id=MISSION_ID,
            config_digest=api["DHARMA_MISSION_SNAPSHOT_CONFIG_DIGEST"],
            minimum_generation=int(api["DHARMA_MISSION_SNAPSHOT_MIN_GENERATION"]),
            max_age_seconds=float(
                api["DHARMA_MISSION_SNAPSHOT_MAX_AGE_SECONDS"]
            ),
            now=observed,
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        raise ReleaseContractError("capacity projection validation failed") from exc
    local_sizes = {
        "runtime_db": _stable_service_regular_size(
            state_root / "state/runtime.db",
            service_uid=service.pw_uid,
        ),
        "tasks_db": _stable_service_regular_size(
            state_root / "db/tasks.db",
            service_uid=service.pw_uid,
        ),
        "projection": len(projection_raw),
    }
    if local_sizes != admitted["source_sizes_bytes"]:
        raise ReleaseContractError("standby capacity proof source bytes drifted")
    return admitted


def _read_control_credential(
    path: Path,
    *,
    expected_root_uid: int,
    minimum_bytes: int = 32,
    maximum_bytes: int = 4096,
    textual: bool = True,
) -> bytes:
    _require_secure_parent_chain(path)
    try:
        identity = path.lstat()
    except OSError as exc:
        raise ReleaseContractError(
            "operator control credential is unavailable"
        ) from exc
    if (
        not stat.S_ISREG(identity.st_mode)
        or path.is_symlink()
        or identity.st_uid != expected_root_uid
        or stat.S_IMODE(identity.st_mode) & 0o077
        or identity.st_nlink != 1
        or not minimum_bytes <= identity.st_size <= maximum_bytes
    ):
        raise ReleaseContractError("operator control credential custody differs")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ReleaseContractError("platform lacks no-follow credential admission")
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        before = os.fstat(descriptor)
        raw = os.read(descriptor, maximum_bytes + 1)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or len(raw) != identity.st_size
        or len(raw) > maximum_bytes
        or b"\r" in raw
        or b"\n" in raw
        or (textual and any(byte < 0x21 or byte > 0x7E for byte in raw))
    ):
        raise ReleaseContractError("operator control credential bytes differ")
    if len(raw) < minimum_bytes or len(raw) > maximum_bytes:
        raise ReleaseContractError("operator control credential length differs")
    return raw


def _candidate_identity(identity: os.stat_result) -> dict[str, int]:
    return {
        "dev": identity.st_dev,
        "ino": identity.st_ino,
        "mode": identity.st_mode,
        "uid": identity.st_uid,
        "gid": identity.st_gid,
        "nlink": identity.st_nlink,
        "size": identity.st_size,
        "mtime_ns": identity.st_mtime_ns,
    }


def _read_emergency_envelope(
    path: Path,
    *,
    control_uid: int,
    control_gid: int,
    hmac_key: bytes,
    operator_login: bytes,
    now: datetime,
    admitted_filename: str | None = None,
) -> tuple[Any, str, dict[str, int]]:
    request_filename = admitted_filename or path.name
    if not re.fullmatch(r"[0-9a-f]{64}\.control\.json", request_filename):
        raise InvalidEmergencyCandidate("emergency request filename differs")
    try:
        identity = path.lstat()
    except OSError as exc:
        raise InvalidEmergencyCandidate("emergency request is unavailable") from exc
    if (
        not stat.S_ISREG(identity.st_mode)
        or path.is_symlink()
        or identity.st_uid != control_uid
        or identity.st_gid != control_gid
        or stat.S_IMODE(identity.st_mode) != 0o640
        or identity.st_nlink != 1
        or not 0 < identity.st_size <= CONTROL_MAX_REQUEST_BYTES
    ):
        raise InvalidEmergencyCandidate("emergency request custody differs")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ReleaseContractError("platform lacks no-follow emergency admission")
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        before = os.fstat(descriptor)
        raw = os.read(descriptor, CONTROL_MAX_REQUEST_BYTES + 1)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        len(raw) != identity.st_size
        or len(raw) > CONTROL_MAX_REQUEST_BYTES
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    ):
        raise InvalidEmergencyCandidate("emergency request changed during read")
    try:
        admitted_login = operator_login.decode("ascii")
    except UnicodeError as exc:
        raise ReleaseContractError("operator login credential is not ASCII") from exc
    try:
        from dharma_swarm.mission_control_operator_control import (
            ControlAction,
            OperatorControlError,
            control_filename,
            decode_and_verify_envelope,
        )
    except ImportError as exc:
        raise ReleaseContractError("shared emergency decoder is unavailable") from exc
    try:
        envelope = decode_and_verify_envelope(
            raw,
            secret=hmac_key,
            now=now,
            expected_actions=frozenset({ControlAction.EMERGENCY_STOP}),
        )
    except OperatorControlError as exc:
        raise InvalidEmergencyCandidate(
            "shared emergency envelope admission failed"
        ) from exc
    except (TypeError, ValueError) as exc:
        raise ReleaseContractError(
            "shared emergency decoder configuration failed"
        ) from exc
    if envelope.operator_login != admitted_login:
        raise InvalidEmergencyCandidate("emergency operator login differs")
    try:
        admitted_filename = control_filename(envelope.request.idempotency_key)
    except OperatorControlError as exc:
        raise InvalidEmergencyCandidate(
            "emergency idempotency filename differs"
        ) from exc
    if request_filename != admitted_filename:
        raise InvalidEmergencyCandidate("emergency idempotency filename differs")
    digest = envelope.envelope_sha256
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ReleaseContractError("emergency envelope digest differs")
    return envelope, digest, _candidate_identity(identity)


def _unit_inactive(
    unit: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> bool:
    result = runner(
        (
            SYSTEMCTL_PATH,
            "show",
            "--property=LoadState",
            "--property=ActiveState",
            "--property=MainPID",
            unit,
        ),
        cwd=Path("/"),
        check=False,
    )
    properties: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition("=")
        if not separator or key in properties:
            return False
        properties[key] = value
    return (
        result.returncode == 0
        and properties
        == {
            "LoadState": "loaded",
            "ActiveState": properties.get("ActiveState", ""),
            "MainPID": "0",
        }
        and properties["ActiveState"] in {"inactive", "failed"}
    )


def _unit_active(
    unit: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> bool:
    result = runner(
        (
            SYSTEMCTL_PATH,
            "show",
            "--property=LoadState",
            "--property=ActiveState",
            unit,
        ),
        cwd=Path("/"),
        check=False,
    )
    properties: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition("=")
        if not separator or key in properties:
            return False
        properties[key] = value
    return result.returncode == 0 and properties == {
        "LoadState": "loaded",
        "ActiveState": "active",
    }


def _unit_enabled(
    unit: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> bool:
    result = runner(
        (SYSTEMCTL_PATH, "is-enabled", unit),
        cwd=Path("/"),
        check=False,
    )
    return (
        result.returncode == 0
        and result.stdout == "enabled\n"
        and not result.stderr
    )


def _unit_disabled(
    unit: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> bool:
    result = runner(
        (SYSTEMCTL_PATH, "is-enabled", unit),
        cwd=Path("/"),
        check=False,
    )
    return (
        result.returncode != 0
        and result.stdout == "disabled\n"
        and not result.stderr
    )


def _unit_static(
    unit: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> bool:
    """Require a unit with no enablement surface, not merely disabled state."""
    result = runner(
        (SYSTEMCTL_PATH, "is-enabled", unit),
        cwd=Path("/"),
        check=False,
    )
    return (
        result.returncode == 0
        and result.stdout == "static\n"
        and not result.stderr
    )


def _unit_masked(
    unit: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> bool:
    result = runner(
        (SYSTEMCTL_PATH, "is-enabled", unit),
        cwd=Path("/"),
        check=False,
    )
    return (
        result.returncode != 0
        and result.stdout == "masked\n"
        and not result.stderr
    )


def _campaign_listeners_absent(proc_net_root: Path = Path("/proc/net")) -> bool:
    admitted_ports = {18420, 18421}
    for name in ("tcp", "tcp6"):
        try:
            raw = (proc_net_root / name).read_text(encoding="ascii")
        except OSError as exc:
            raise ReleaseContractError("cannot inspect campaign listeners") from exc
        for line in raw.splitlines()[1:]:
            fields = line.split()
            if len(fields) < 4 or fields[3] != "0A":
                continue
            try:
                port = int(fields[1].rsplit(":", maxsplit=1)[1], 16)
            except (IndexError, ValueError) as exc:
                raise ReleaseContractError("campaign listener table differs") from exc
            if port in admitted_ports:
                return False
    return True


def _emergency_receipt_path(input_path: Path) -> Path:
    digest = input_path.name.removesuffix(".control.json")
    if not _SHA_RE.fullmatch(digest):
        raise ReleaseContractError("emergency receipt identity differs")
    return EMERGENCY_RECEIPT_ROOT / f"{digest}.terminal.json"


def _write_emergency_terminal(
    path: Path,
    payload: Mapping[str, Any],
    *,
    expected_root_uid: int,
    expected_root_gid: int,
) -> None:
    if set(payload) != _EMERGENCY_RECEIPT_FIELDS:
        raise ReleaseContractError("emergency terminal fields differ")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    parent = path.parent.lstat()
    if (
        path.parent.is_symlink()
        or not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid != expected_root_uid
        or parent.st_gid != expected_root_gid
        or stat.S_IMODE(parent.st_mode) != 0o700
    ):
        raise ReleaseContractError("emergency receipt root custody differs")
    _atomic_private_bytes(
        path,
        _canonical_bytes(payload) + b"\n",
        uid=expected_root_uid,
        gid=expected_root_gid,
    )


def _move_emergency_candidate_into_claim(
    *,
    original_filename: str,
    expected_identity: Mapping[str, int],
    reservation: Path,
) -> Path:
    if set(expected_identity) != _EMERGENCY_CANDIDATE_IDENTITY_FIELDS:
        raise ReleaseContractError("emergency claim identity fields differ")
    directory_flags = (
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    source_descriptor = os.open(CONTROL_EMERGENCY_INBOX, directory_flags)
    reservation_descriptor = os.open(reservation, directory_flags)
    try:
        try:
            os.stat("entry", dir_fd=reservation_descriptor, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ReleaseContractError("emergency claim entry already exists")
        current = os.stat(
            original_filename,
            dir_fd=source_descriptor,
            follow_symlinks=False,
        )
        if _candidate_identity(current) != dict(expected_identity):
            raise ReleaseContractError("emergency candidate was substituted")
        _rename_noreplace_at(
            source_descriptor,
            original_filename,
            reservation_descriptor,
            "entry",
        )
        admitted = os.stat(
            "entry",
            dir_fd=reservation_descriptor,
            follow_symlinks=False,
        )
        if _candidate_identity(admitted) != dict(expected_identity):
            raise ReleaseContractError("emergency claimed inode differs")
        os.fsync(reservation_descriptor)
        os.fsync(source_descriptor)
    finally:
        os.close(reservation_descriptor)
        os.close(source_descriptor)
    return reservation / "entry"


def _rename_noreplace_at(
    source_directory_fd: int,
    source_name: str,
    destination_directory_fd: int,
    destination_name: str,
) -> None:
    """Atomically move one directory entry without replacing a destination.

    Linux deployment uses renameat2(RENAME_NOREPLACE).  Darwin's equivalent is
    used only by the local clean-room tests.  Absence of either primitive is a
    hard failure; a precheck followed by os.rename is not an admissible fallback.
    """
    libc = ctypes.CDLL(None, use_errno=True)
    source_raw = os.fsencode(source_name)
    destination_raw = os.fsencode(destination_name)
    if hasattr(libc, "renameat2"):
        rename = libc.renameat2
        rename.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        rename.restype = ctypes.c_int
        result = rename(
            source_directory_fd,
            source_raw,
            destination_directory_fd,
            destination_raw,
            1,  # RENAME_NOREPLACE
        )
    elif hasattr(libc, "renameatx_np"):
        rename = libc.renameatx_np
        rename.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        rename.restype = ctypes.c_int
        result = rename(
            source_directory_fd,
            source_raw,
            destination_directory_fd,
            destination_raw,
            0x00000004,  # Darwin RENAME_EXCL
        )
    else:
        raise ReleaseContractError("platform lacks atomic no-replace rename")
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise ReleaseContractError("atomic no-replace destination already exists")
    raise OSError(
        error_number,
        os.strerror(error_number),
        f"{source_name} -> {destination_name}",
    )


def _claim_emergency_candidate(
    candidate: Path,
    *,
    envelope: Any,
    envelope_sha256: str,
    candidate_identity: Mapping[str, int],
    claimed_at: datetime,
    expected_root_uid: int,
    expected_root_gid: int,
) -> Path:
    if candidate.parent != CONTROL_EMERGENCY_INBOX:
        raise ReleaseContractError("emergency claim source differs")
    request = envelope.request
    action = getattr(request.action, "value", request.action)
    if action != "emergency_stop":
        raise InvalidEmergencyCandidate("emergency claim action differs")
    reservation_digest = hashlib.sha256(
        candidate.name.encode("utf-8", errors="surrogateescape")
    ).hexdigest()
    reservation = EMERGENCY_INFLIGHT_ROOT / f"{reservation_digest}.claim"
    if reservation.exists() or reservation.is_symlink():
        raise ReleaseContractError("emergency claim reservation already exists")
    os.mkdir(reservation, 0o700)
    os.chown(reservation, expected_root_uid, expected_root_gid)
    os.chmod(reservation, 0o700)
    claim: dict[str, Any] = {
        "schema_version": "dharma.sadhana.emergency_control_claim.v1",
        "campaign_id": MISSION_ID,
        "control_semantics_sha256": CONTROL_SEMANTICS_SHA256,
        "control_http_binding_sha256": CONTROL_HTTP_BINDING_SHA256,
        "control_authority_binding_sha256": CONTROL_AUTHORITY_BINDING_SHA256,
        "original_filename": candidate.name,
        "candidate_identity": dict(candidate_identity),
        "envelope_sha256": envelope_sha256,
        "request_id": request.request_id,
        "idempotency_key": request.idempotency_key,
        "action": action,
        "claimed_at": claimed_at.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "claim_digest": "",
    }
    if (
        set(claim) != _EMERGENCY_CLAIM_FIELDS
        or set(claim["candidate_identity"]) != _EMERGENCY_CANDIDATE_IDENTITY_FIELDS
    ):
        raise ReleaseContractError("emergency claim fields differ")
    claim["claim_digest"] = _canonical_self_digest(claim, "claim_digest")
    try:
        _atomic_private_bytes(
            reservation / "claim.json",
            _canonical_bytes(claim) + b"\n",
            uid=expected_root_uid,
            gid=expected_root_gid,
        )
        claimed = _move_emergency_candidate_into_claim(
            original_filename=candidate.name,
            expected_identity=candidate_identity,
            reservation=reservation,
        )
        directory_descriptor = os.open(
            EMERGENCY_INFLIGHT_ROOT,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        return claimed
    except BaseException:
        # Keep a populated claim reservation for deterministic crash recovery.
        # Only an empty reservation created before claim.json can be removed.
        if not any(reservation.iterdir()):
            reservation.rmdir()
        raise


def _read_emergency_claim(
    reservation: Path,
    *,
    control_uid: int,
    control_gid: int,
    hmac_key: bytes,
    operator_login: bytes,
    now: datetime,
    expected_root_uid: int,
    expected_root_gid: int,
) -> tuple[Any, str, dict[str, Any], Path]:
    if reservation.parent != EMERGENCY_INFLIGHT_ROOT or not re.fullmatch(
        r"[0-9a-f]{64}\.claim", reservation.name
    ):
        raise ReleaseContractError("emergency claim reservation name differs")
    identity = reservation.lstat()
    if (
        reservation.is_symlink()
        or not stat.S_ISDIR(identity.st_mode)
        or identity.st_uid != expected_root_uid
        or identity.st_gid != expected_root_gid
        or stat.S_IMODE(identity.st_mode) != 0o700
    ):
        raise ReleaseContractError("emergency claim reservation custody differs")
    claim, _raw, _claim_identity = _read_exact_canonical_json(
        reservation / "claim.json",
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema="dharma.sadhana.emergency_control_claim.v1",
        digest_field="claim_digest",
    )
    candidate_identity = claim.get("candidate_identity")
    original_filename = claim.get("original_filename")
    if (
        set(claim) != _EMERGENCY_CLAIM_FIELDS
        or not isinstance(candidate_identity, dict)
        or set(candidate_identity) != _EMERGENCY_CANDIDATE_IDENTITY_FIELDS
        or not isinstance(original_filename, str)
        or hashlib.sha256(
            original_filename.encode("utf-8", errors="surrogateescape")
        ).hexdigest()
        != reservation.name.removesuffix(".claim")
        or claim.get("campaign_id") != MISSION_ID
        or claim.get("control_semantics_sha256") != CONTROL_SEMANTICS_SHA256
        or claim.get("control_http_binding_sha256") != CONTROL_HTTP_BINDING_SHA256
        or claim.get("control_authority_binding_sha256")
        != CONTROL_AUTHORITY_BINDING_SHA256
        or claim.get("action") != "emergency_stop"
    ):
        raise ReleaseContractError("emergency claim bindings differ")
    entry = reservation / "entry"
    if not entry.exists() and not entry.is_symlink():
        _move_emergency_candidate_into_claim(
            original_filename=original_filename,
            expected_identity=candidate_identity,
            reservation=reservation,
        )
    if set(path.name for path in reservation.iterdir()) != {"claim.json", "entry"}:
        raise ReleaseContractError("emergency claim contains unexpected entries")
    claimed_at = _parse_utc(str(claim.get("claimed_at")), "claimed_at")
    if claimed_at > now.astimezone(timezone.utc) + timedelta(
        seconds=MAX_CONTROLLER_CLOCK_SKEW_SECONDS
    ):
        raise ReleaseContractError("emergency claim is future-dated")
    envelope, envelope_sha256, observed_identity = _read_emergency_envelope(
        entry,
        control_uid=control_uid,
        control_gid=control_gid,
        hmac_key=hmac_key,
        operator_login=operator_login,
        now=claimed_at,
        admitted_filename=original_filename,
    )
    request = envelope.request
    action = getattr(request.action, "value", request.action)
    if (
        observed_identity != candidate_identity
        or envelope_sha256 != claim.get("envelope_sha256")
        or request.request_id != claim.get("request_id")
        or request.idempotency_key != claim.get("idempotency_key")
        or action != claim.get("action")
    ):
        raise ReleaseContractError("emergency claimed envelope differs")
    return envelope, envelope_sha256, claim, entry


def _persist_emergency_stop_marker(
    *,
    claim: Mapping[str, Any],
    expected_root_uid: int,
    expected_root_gid: int,
) -> dict[str, Any]:
    marker: dict[str, Any] = {
        "schema_version": "dharma.sadhana.emergency_stop_marker.v1",
        "campaign_id": MISSION_ID,
        "control_semantics_sha256": CONTROL_SEMANTICS_SHA256,
        "control_http_binding_sha256": CONTROL_HTTP_BINDING_SHA256,
        "control_authority_binding_sha256": CONTROL_AUTHORITY_BINDING_SHA256,
        "envelope_sha256": claim["envelope_sha256"],
        "request_id": claim["request_id"],
        "idempotency_key": claim["idempotency_key"],
        "stop_request_claimed_at": claim["claimed_at"],
        "receipt_digest": "",
    }
    if set(marker) != _EMERGENCY_STOP_MARKER_FIELDS:
        raise ReleaseContractError("emergency stop marker fields differ")
    marker["receipt_digest"] = _canonical_self_digest(marker, "receipt_digest")
    raw = _canonical_bytes(marker) + b"\n"
    try:
        if EMERGENCY_STOP_MARKER.exists() or EMERGENCY_STOP_MARKER.is_symlink():
            prior, prior_raw, _identity = _read_exact_canonical_json(
                EMERGENCY_STOP_MARKER,
                expected_uid=expected_root_uid,
                expected_gid=expected_root_gid,
                expected_schema="dharma.sadhana.emergency_stop_marker.v1",
                digest_field="receipt_digest",
            )
            if set(prior) != _EMERGENCY_STOP_MARKER_FIELDS or prior_raw != raw:
                raise ReleaseContractError("immutable emergency stop marker conflicts")
            return prior
        _atomic_private_bytes(
            EMERGENCY_STOP_MARKER,
            raw,
            uid=expected_root_uid,
            gid=expected_root_gid,
        )
    except (OSError, ReleaseContractError) as exc:
        raise EmergencyMarkerPersistenceError(
            "post-cessation emergency stop marker was not persisted"
        ) from exc
    return marker


def _require_emergency_stop_marker_binding(
    *,
    claim: Mapping[str, Any],
    expected_root_uid: int,
    expected_root_gid: int,
) -> dict[str, Any]:
    marker, _raw, _identity = _read_exact_canonical_json(
        EMERGENCY_STOP_MARKER,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema="dharma.sadhana.emergency_stop_marker.v1",
        digest_field="receipt_digest",
    )
    if (
        set(marker) != _EMERGENCY_STOP_MARKER_FIELDS
        or marker.get("campaign_id") != MISSION_ID
        or marker.get("control_semantics_sha256") != CONTROL_SEMANTICS_SHA256
        or marker.get("control_http_binding_sha256") != CONTROL_HTTP_BINDING_SHA256
        or marker.get("control_authority_binding_sha256")
        != CONTROL_AUTHORITY_BINDING_SHA256
        or marker.get("envelope_sha256") != claim.get("envelope_sha256")
        or marker.get("request_id") != claim.get("request_id")
        or marker.get("idempotency_key") != claim.get("idempotency_key")
    ):
        raise ReleaseContractError("emergency stop marker binding differs")
    return marker


def _remove_emergency_claim(reservation: Path) -> None:
    if reservation.parent != EMERGENCY_INFLIGHT_ROOT:
        raise ReleaseContractError("emergency claim cleanup root differs")
    directory_flags = (
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    parent_descriptor = os.open(EMERGENCY_INFLIGHT_ROOT, directory_flags)
    reservation_descriptor = os.open(reservation, directory_flags)
    try:
        if set(path.name for path in reservation.iterdir()) != {"claim.json", "entry"}:
            raise ReleaseContractError("emergency claim cleanup entries differ")
        os.unlink("entry", dir_fd=reservation_descriptor)
        os.unlink("claim.json", dir_fd=reservation_descriptor)
        os.fsync(reservation_descriptor)
        os.rmdir(reservation.name, dir_fd=parent_descriptor)
        os.fsync(parent_descriptor)
    finally:
        os.close(reservation_descriptor)
        os.close(parent_descriptor)


def _acquire_emergency_apply_lock(
    *,
    expected_root_uid: int,
    expected_root_gid: int,
) -> int:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ReleaseContractError("platform lacks no-follow emergency lock")
    descriptor = os.open(
        EMERGENCY_APPLY_LOCK,
        os.O_RDWR | os.O_CREAT | nofollow,
        0o600,
    )
    try:
        os.fchmod(descriptor, 0o600)
        os.fchown(descriptor, expected_root_uid, expected_root_gid)
        identity = os.fstat(descriptor)
        if (
            not stat.S_ISREG(identity.st_mode)
            or identity.st_uid != expected_root_uid
            or identity.st_gid != expected_root_gid
            or stat.S_IMODE(identity.st_mode) != 0o600
            or identity.st_nlink != 1
        ):
            raise ReleaseContractError("emergency apply lock custody differs")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ReleaseContractError(
                "another emergency applier holds the root lock"
            ) from exc
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _quarantine_invalid_emergency(
    candidate: Path,
    *,
    observed_at: datetime,
    expected_root_uid: int,
    expected_root_gid: int,
) -> dict[str, Any]:
    """Atomically remove one poison entry from the live inbox, then receipt it."""
    if candidate.parent != CONTROL_EMERGENCY_INBOX:
        raise ReleaseContractError("emergency rejection source differs")
    for root in (EMERGENCY_QUARANTINE_ROOT, EMERGENCY_RECEIPT_ROOT):
        root_identity = root.lstat()
        if (
            root.is_symlink()
            or not stat.S_ISDIR(root_identity.st_mode)
            or root_identity.st_uid != expected_root_uid
            or root_identity.st_gid != expected_root_gid
            or stat.S_IMODE(root_identity.st_mode) != 0o700
        ):
            raise ReleaseContractError("emergency rejection root custody differs")
    directory_flags = (
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    source_descriptor = os.open(CONTROL_EMERGENCY_INBOX, directory_flags)
    quarantine_descriptor = os.open(EMERGENCY_QUARANTINE_ROOT, directory_flags)
    reservation_descriptor = -1
    reservation_name = ""
    moved = False
    try:
        identity = os.stat(
            candidate.name,
            dir_fd=source_descriptor,
            follow_symlinks=False,
        )
        name_bytes = candidate.name.encode("utf-8", errors="surrogateescape")
        identity_payload = {
            "name_sha256": hashlib.sha256(name_bytes).hexdigest(),
            "dev": identity.st_dev,
            "ino": identity.st_ino,
            "mode": identity.st_mode,
            "uid": identity.st_uid,
            "gid": identity.st_gid,
            "nlink": identity.st_nlink,
            "size": identity.st_size,
            "mtime_ns": identity.st_mtime_ns,
        }
        identity_digest = hashlib.sha256(_canonical_bytes(identity_payload)).hexdigest()
        reservation_name = f"{identity_digest}.invalid-entry"
        receipt_path = EMERGENCY_RECEIPT_ROOT / f"{identity_digest}.rejected.json"
        if receipt_path.exists() or receipt_path.is_symlink():
            raise ReleaseContractError("emergency rejection receipt already exists")
        os.mkdir(
            reservation_name,
            0o700,
            dir_fd=quarantine_descriptor,
        )
        reservation_descriptor = os.open(
            reservation_name,
            directory_flags,
            dir_fd=quarantine_descriptor,
        )
        reservation_identity = os.fstat(reservation_descriptor)
        if (
            reservation_identity.st_uid != expected_root_uid
            or reservation_identity.st_gid != expected_root_gid
            or stat.S_IMODE(reservation_identity.st_mode) != 0o700
        ):
            raise ReleaseContractError("emergency quarantine reservation differs")
        current = os.stat(
            candidate.name,
            dir_fd=source_descriptor,
            follow_symlinks=False,
        )
        identity_tuple = (
            identity.st_dev,
            identity.st_ino,
            identity.st_mode,
            identity.st_uid,
            identity.st_gid,
            identity.st_nlink,
            identity.st_size,
            identity.st_mtime_ns,
        )
        current_tuple = (
            current.st_dev,
            current.st_ino,
            current.st_mode,
            current.st_uid,
            current.st_gid,
            current.st_nlink,
            current.st_size,
            current.st_mtime_ns,
        )
        if current_tuple != identity_tuple:
            raise ReleaseContractError("emergency rejection source was substituted")
        _rename_noreplace_at(
            source_descriptor,
            candidate.name,
            reservation_descriptor,
            "entry",
        )
        moved = True
        quarantined = os.stat(
            "entry",
            dir_fd=reservation_descriptor,
            follow_symlinks=False,
        )
        quarantined_tuple = (
            quarantined.st_dev,
            quarantined.st_ino,
            quarantined.st_mode,
            quarantined.st_uid,
            quarantined.st_gid,
            quarantined.st_nlink,
            quarantined.st_size,
            quarantined.st_mtime_ns,
        )
        if quarantined_tuple != identity_tuple:
            raise ReleaseContractError("emergency quarantine identity differs")
        os.fsync(reservation_descriptor)
        os.fsync(source_descriptor)
        os.fsync(quarantine_descriptor)
    except BaseException:
        if reservation_name and not moved:
            try:
                if reservation_descriptor >= 0:
                    os.close(reservation_descriptor)
                    reservation_descriptor = -1
                os.rmdir(reservation_name, dir_fd=quarantine_descriptor)
            except OSError:
                pass
        raise
    finally:
        if reservation_descriptor >= 0:
            os.close(reservation_descriptor)
        os.close(quarantine_descriptor)
        os.close(source_descriptor)
    quarantine_name = f"{reservation_name}/entry"
    receipt: dict[str, Any] = {
        "schema_version": "dharma.sadhana.emergency_control_rejection.v1",
        "campaign_id": MISSION_ID,
        "control_semantics_sha256": CONTROL_SEMANTICS_SHA256,
        "control_http_binding_sha256": CONTROL_HTTP_BINDING_SHA256,
        "control_authority_binding_sha256": CONTROL_AUTHORITY_BINDING_SHA256,
        "candidate_name_sha256": identity_payload["name_sha256"],
        "candidate_identity_digest": identity_digest,
        "status": "rejected",
        "error_code": "invalid_emergency_control_envelope",
        "quarantine_entry": quarantine_name,
        "quarantined": True,
        "target_stop_requested": False,
        "authority_applied": False,
        "effect_observed": False,
        "rejected_at": observed_at.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "receipt_digest": "",
    }
    if set(receipt) != _EMERGENCY_REJECTION_FIELDS:
        raise ReleaseContractError("emergency rejection fields differ")
    receipt["receipt_digest"] = _canonical_self_digest(receipt, "receipt_digest")
    _atomic_private_bytes(
        receipt_path,
        _canonical_bytes(receipt) + b"\n",
        uid=expected_root_uid,
        gid=expected_root_gid,
    )
    return receipt


def _stop_campaign_and_prove_cessation(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    proc_net_root: Path,
    clock: Callable[[], datetime],
) -> tuple[datetime, datetime]:
    stopped_at = clock()
    if stopped_at.tzinfo is None:
        raise ReleaseContractError("emergency stop clock must be aware")
    stopped = runner(
        (SYSTEMCTL_PATH, "stop", "dharma-sadhana.target"),
        cwd=Path("/"),
        check=False,
    )
    if stopped.returncode != 0:
        raise ReleaseContractError("emergency target stop failed")
    inactive_at = clock()
    if inactive_at.tzinfo is None:
        raise ReleaseContractError("emergency postcondition clock must be aware")
    target_inactive = _unit_inactive("dharma-sadhana.target", runner=runner)
    partof_inactive = all(
        _unit_inactive(unit, runner=runner) for unit in CAMPAIGN_PARTOF_UNITS
    )
    listeners_absent = _campaign_listeners_absent(proc_net_root)
    if not target_inactive or not partof_inactive or not listeners_absent:
        raise ReleaseContractError("emergency stop postcondition differs")
    return stopped_at, inactive_at


def _apply_emergency_claim(
    reservation: Path,
    *,
    control_uid: int,
    control_gid: int,
    hmac_key: bytes,
    operator_login: bytes,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    proc_net_root: Path,
    clock: Callable[[], datetime],
    expected_root_uid: int,
    expected_root_gid: int,
) -> dict[str, Any]:
    observed = clock()
    if observed.tzinfo is None:
        raise ReleaseContractError("emergency control clock must be aware")
    envelope, envelope_sha256, claim, _entry = _read_emergency_claim(
        reservation,
        control_uid=control_uid,
        control_gid=control_gid,
        hmac_key=hmac_key,
        operator_login=operator_login,
        now=observed,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    request = envelope.request
    receipt_path = _emergency_receipt_path(Path(claim["original_filename"]))
    if receipt_path.exists() or receipt_path.is_symlink():
        prior, _raw, _identity = _read_exact_canonical_json(
            receipt_path,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
            expected_schema="dharma.sadhana.emergency_control_terminal.v1",
            digest_field="receipt_digest",
        )
        marker_persisted = prior.get("durable_stop_marker_persisted")
        expected_error = (
            "" if marker_persisted is True else "durable_stop_marker_not_persisted"
        )
        if (
            set(prior) != _EMERGENCY_RECEIPT_FIELDS
            or prior.get("envelope_sha256") != envelope_sha256
            or prior.get("request_id") != request.request_id
            or prior.get("idempotency_key") != request.idempotency_key
            or prior.get("status") != "applied"
            or (marker_persisted is not True and marker_persisted is not False)
            or prior.get("error_code") != expected_error
            or prior.get("authority_applied") is not True
            or prior.get("effect_observed") is not True
        ):
            raise ReleaseContractError("emergency terminal replay conflicts")
        if marker_persisted is True:
            _require_emergency_stop_marker_binding(
                claim=claim,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
        else:
            # The terminal already proves the original stop. Reassert cessation
            # before repairing the best-effort restart barrier after a crash or
            # transient filesystem failure. The immutable terminal remains
            # honest: it is never rewritten from false to true.
            _stop_campaign_and_prove_cessation(
                runner=runner,
                proc_net_root=proc_net_root,
                clock=clock,
            )
            try:
                _persist_emergency_stop_marker(
                    claim=claim,
                    expected_root_uid=expected_root_uid,
                    expected_root_gid=expected_root_gid,
                )
            except EmergencyMarkerPersistenceError:
                return prior
        _remove_emergency_claim(reservation)
        return prior
    stopped_at, inactive_at = _stop_campaign_and_prove_cessation(
        runner=runner,
        proc_net_root=proc_net_root,
        clock=clock,
    )
    marker_persisted = True
    try:
        # The semantics contract requires cessation first. This immutable
        # marker is a postcondition/restart barrier, never a prerequisite that
        # can delay or reverse the stop effect.
        _persist_emergency_stop_marker(
            claim=claim,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
    except EmergencyMarkerPersistenceError:
        marker_persisted = False
    terminal: dict[str, Any] = {
        "schema_version": "dharma.sadhana.emergency_control_terminal.v1",
        "campaign_id": MISSION_ID,
        "control_semantics_sha256": CONTROL_SEMANTICS_SHA256,
        "control_http_binding_sha256": CONTROL_HTTP_BINDING_SHA256,
        "control_authority_binding_sha256": CONTROL_AUTHORITY_BINDING_SHA256,
        "request_id": request.request_id,
        "idempotency_key": request.idempotency_key,
        "action": "emergency_stop",
        "operator_login_matched": True,
        "envelope_sha256": envelope_sha256,
        "status": "applied",
        "error_code": (
            "" if marker_persisted else "durable_stop_marker_not_persisted"
        ),
        "target_stop_requested_at": stopped_at.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "target_inactive_observed_at": inactive_at.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "target_inactive": True,
        "partof_units_inactive": True,
        "campaign_listeners_absent": True,
        "durable_stop_marker_persisted": marker_persisted,
        "authority_applied": True,
        "effect_observed": True,
        "receipt_digest": "",
    }
    terminal["receipt_digest"] = _canonical_self_digest(terminal, "receipt_digest")
    _write_emergency_terminal(
        receipt_path,
        terminal,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if marker_persisted:
        _remove_emergency_claim(reservation)
    return terminal


def apply_emergency_controls(
    *,
    role: str,
    hmac_key_file: Path,
    operator_login_file: Path,
    inbox: Path = CONTROL_EMERGENCY_INBOX,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    proc_net_root: Path = Path("/proc/net"),
    now: Callable[[], datetime] | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> list[dict[str, Any]]:
    """Claim one valid request, prove cessation, then best-effort mark it."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("emergency control application requires root")
    _require_host_role(role, observed_node=observed_node)
    if role != "writer" or inbox != CONTROL_EMERGENCY_INBOX:
        raise ReleaseContractError("emergency control topology differs")
    try:
        control = pwd.getpwnam("dharma-sadhana-control")
    except KeyError as exc:
        raise ReleaseContractError("control service identity is unavailable") from exc
    if control.pw_uid == 0 or control.pw_gid == 0:
        raise ReleaseContractError("control service identity differs")
    _require_secure_parent_chain(inbox.parent / ".custody-check")
    inbox_identity = inbox.lstat()
    if (
        inbox.is_symlink()
        or not stat.S_ISDIR(inbox_identity.st_mode)
        or inbox_identity.st_uid != expected_root_uid
        or inbox_identity.st_gid != control.pw_gid
        or stat.S_IMODE(inbox_identity.st_mode) != 0o770
    ):
        raise ReleaseContractError("emergency inbox custody differs")
    for root in (
        EMERGENCY_INFLIGHT_ROOT,
        EMERGENCY_QUARANTINE_ROOT,
        EMERGENCY_RECEIPT_ROOT,
    ):
        try:
            identity = root.lstat()
        except OSError as exc:
            raise ReleaseContractError("emergency root custody is unavailable") from exc
        if (
            root.is_symlink()
            or not stat.S_ISDIR(identity.st_mode)
            or identity.st_uid != expected_root_uid
            or identity.st_gid != expected_root_gid
            or stat.S_IMODE(identity.st_mode) != 0o700
        ):
            raise ReleaseContractError("emergency root custody differs")
    hmac_key = _read_control_credential(
        hmac_key_file,
        expected_root_uid=expected_root_uid,
        textual=False,
    )
    operator_login = _read_control_credential(
        operator_login_file,
        expected_root_uid=expected_root_uid,
        minimum_bytes=1,
        maximum_bytes=254,
    )
    clock = now or (lambda: datetime.now(timezone.utc))
    results: list[dict[str, Any]] = []
    quarantine_failed = False
    lock_descriptor = _acquire_emergency_apply_lock(
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    try:
        # A crash may leave a root-only reservation after the inbox pathname
        # has disappeared.  Resume it before admitting any newer request.
        reservations = sorted(
            EMERGENCY_INFLIGHT_ROOT.iterdir(),
            key=lambda path: os.fsencode(path.name),
        )
        for reservation in reservations:
            terminal = _apply_emergency_claim(
                reservation,
                control_uid=control.pw_uid,
                control_gid=control.pw_gid,
                hmac_key=hmac_key,
                operator_login=operator_login,
                runner=runner,
                proc_net_root=proc_net_root,
                clock=clock,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
            results.append(terminal)
            return results

        candidates = sorted(inbox.iterdir(), key=lambda path: os.fsencode(path.name))
        for candidate in candidates:
            observed = clock()
            if observed.tzinfo is None:
                raise ReleaseContractError("emergency control clock must be aware")
            try:
                envelope, envelope_sha256, candidate_identity = (
                    _read_emergency_envelope(
                        candidate,
                        control_uid=control.pw_uid,
                        control_gid=control.pw_gid,
                        hmac_key=hmac_key,
                        operator_login=operator_login,
                        now=observed,
                    )
                )
            except InvalidEmergencyCandidate:
                try:
                    _quarantine_invalid_emergency(
                        candidate,
                        observed_at=observed,
                        expected_root_uid=expected_root_uid,
                        expected_root_gid=expected_root_gid,
                    )
                except (OSError, ReleaseContractError):
                    # A poison receipt failure is visible but cannot starve a
                    # later valid stop in the same bounded scan.
                    quarantine_failed = True
                continue
            _claim_emergency_candidate(
                candidate,
                envelope=envelope,
                envelope_sha256=envelope_sha256,
                candidate_identity=candidate_identity,
                claimed_at=observed,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
            reservation_name = hashlib.sha256(
                candidate.name.encode("utf-8", errors="surrogateescape")
            ).hexdigest()
            terminal = _apply_emergency_claim(
                EMERGENCY_INFLIGHT_ROOT / f"{reservation_name}.claim",
                control_uid=control.pw_uid,
                control_gid=control.pw_gid,
                hmac_key=hmac_key,
                operator_login=operator_login,
                runner=runner,
                proc_net_root=proc_net_root,
                clock=clock,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
            results.append(terminal)
            return results
        if quarantine_failed:
            raise ReleaseContractError("emergency poison quarantine failed")
        return results
    finally:
        fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
        os.close(lock_descriptor)


def resume_emergency_controls(
    *,
    role: str,
    hmac_key_file: Path,
    operator_login_file: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    proc_net_root: Path = Path("/proc/net"),
    now: Callable[[], datetime] | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> list[dict[str, Any]]:
    """Resume one persistent root claim without depending on volatile inboxes."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("emergency recovery requires root")
    _require_host_role(role, observed_node=observed_node)
    if role != "writer":
        raise ReleaseContractError("emergency recovery topology differs")
    try:
        control = pwd.getpwnam("dharma-sadhana-control")
    except KeyError as exc:
        raise ReleaseContractError("control service identity is unavailable") from exc
    if control.pw_uid == 0 or control.pw_gid == 0:
        raise ReleaseContractError("control service identity differs")
    for root in (EMERGENCY_INFLIGHT_ROOT, EMERGENCY_RECEIPT_ROOT):
        identity = root.lstat()
        if (
            root.is_symlink()
            or not stat.S_ISDIR(identity.st_mode)
            or identity.st_uid != expected_root_uid
            or identity.st_gid != expected_root_gid
            or stat.S_IMODE(identity.st_mode) != 0o700
        ):
            raise ReleaseContractError("emergency recovery root custody differs")
    hmac_key = _read_control_credential(
        hmac_key_file,
        expected_root_uid=expected_root_uid,
        textual=False,
    )
    operator_login = _read_control_credential(
        operator_login_file,
        expected_root_uid=expected_root_uid,
        minimum_bytes=1,
        maximum_bytes=254,
    )
    clock = now or (lambda: datetime.now(timezone.utc))
    lock_descriptor = _acquire_emergency_apply_lock(
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    try:
        reservations = sorted(
            EMERGENCY_INFLIGHT_ROOT.iterdir(),
            key=lambda path: os.fsencode(path.name),
        )
        if not reservations:
            return []
        if len(reservations) != 1:
            raise ReleaseContractError("emergency recovery claim count differs")
        return [
            _apply_emergency_claim(
                reservations[0],
                control_uid=control.pw_uid,
                control_gid=control.pw_gid,
                hmac_key=hmac_key,
                operator_login=operator_login,
                runner=runner,
                proc_net_root=proc_net_root,
                clock=clock,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
        ]
    finally:
        fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
        os.close(lock_descriptor)


def _standby_activation_intent(
    *,
    release_sha: str,
    staged_release_admission_receipt_digest: str,
    preactivation_clock_proof_receipt_digest: str,
    path: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    observed: datetime,
    expected_root_uid: int,
    expected_root_gid: int,
) -> tuple[dict[str, Any], bool]:
    expected = {
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "staged_release_admission_receipt_digest": (
            staged_release_admission_receipt_digest
        ),
        "preactivation_clock_proof_receipt_digest": (
            preactivation_clock_proof_receipt_digest
        ),
        "writer_marker_absent_before": True,
        "campaign_units_mask_requested": True,
        "standby_target_inactive_before": True,
        "standby_target_disabled_before": True,
        "standby_stop_timer_inactive_before": True,
        "standby_stop_timer_disabled_before": True,
        "standby_replication_serve_inactive_before": True,
        "standby_replication_route_absent_before": True,
        "effect_intent": "InfrastructureEffect",
        "writer_authority_transferred": False,
    }
    if path.exists() or path.is_symlink():
        prior, _raw, _identity = _read_exact_canonical_json(
            path,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
            expected_schema=STANDBY_ACTIVATION_INTENT_SCHEMA_VERSION,
            digest_field="receipt_digest",
        )
        if set(prior) != _STANDBY_ACTIVATION_INTENT_FIELDS or any(
            prior.get(key) != value for key, value in expected.items()
        ):
            raise ReleaseContractError("standby activation intent differs")
        return prior, False
    if WRITER_MARKER.exists() or WRITER_MARKER.is_symlink():
        raise ReleaseContractError("standby activation found a writer marker")
    if not (
        _unit_inactive(STANDBY_TARGET, runner=runner)
        and _unit_disabled(STANDBY_TARGET, runner=runner)
        and _unit_inactive(STANDBY_STOP_TIMER, runner=runner)
        and _unit_disabled(STANDBY_STOP_TIMER, runner=runner)
        and _unit_inactive(STANDBY_REPLICATION_SERVE_UNIT, runner=runner)
    ):
        raise ReleaseContractError("fresh standby activation is not disabled")
    _require_standby_tailscale_route_absent(runner=runner)
    payload: dict[str, Any] = {
        "schema_version": STANDBY_ACTIVATION_INTENT_SCHEMA_VERSION,
        **expected,
        "created_at": observed.isoformat().replace("+00:00", "Z"),
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    if set(payload) != _STANDBY_ACTIVATION_INTENT_FIELDS:
        raise ReleaseContractError("standby activation intent fields differ")
    return (
        _publish_or_replay_private_receipt(
            path,
            payload,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
        ),
        True,
    )


def _standby_activation_live_state(
    *,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    expected_root_uid: int,
    expected_root_gid: int,
) -> dict[str, Any]:
    ownership = _load_standby_tailscale_ownership_receipt(
        STANDBY_TAILSCALE_OWNERSHIP_RECEIPT,
        release_sha=release_sha,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if _read_tailscale_config(runner=runner) != TAILSCALE_EMPTY_CONFIG:
        raise ReleaseContractError("standby activation named Serve config differs")
    status = _validate_standby_tailscale_status(
        _read_tailscale_status(runner=runner)
    )
    if (
        _canonical_bytes(status) != _canonical_bytes(ownership["config"])
        or _tailscale_config_digest(status) != ownership["config_sha256"]
    ):
        raise ReleaseContractError("standby activation Serve ownership differs")
    live = {
        "campaign_units_masked_and_inactive": all(
            _unit_inactive(unit, runner=runner) and _unit_masked(unit, runner=runner)
            for unit in CAMPAIGN_UNITS
        ),
        "standby_stop_timer_active": _unit_active(
            STANDBY_STOP_TIMER, runner=runner
        ),
        "standby_stop_timer_enabled": _unit_enabled(
            STANDBY_STOP_TIMER, runner=runner
        ),
        "standby_target_active": _unit_active(STANDBY_TARGET, runner=runner),
        "standby_target_enabled": _unit_enabled(STANDBY_TARGET, runner=runner),
        "standby_replication_serve_active": _unit_active(
            STANDBY_REPLICATION_SERVE_UNIT, runner=runner
        ),
        "standby_replication_serve_owned": True,
        "standby_replication_serve_ownership_receipt_digest": ownership[
            "receipt_digest"
        ],
        "standby_replication_route_end_to_end_verified": False,
        "writer_marker_absent": not (
            WRITER_MARKER.exists() or WRITER_MARKER.is_symlink()
        ),
    }
    if (
        not all(
            live[field]
            for field in (
                "campaign_units_masked_and_inactive",
                "standby_stop_timer_active",
                "standby_stop_timer_enabled",
                "standby_target_active",
                "standby_target_enabled",
                "standby_replication_serve_active",
                "standby_replication_serve_owned",
                "writer_marker_absent",
            )
        )
        or live["standby_replication_route_end_to_end_verified"] is not False
    ):
        raise ReleaseContractError("standby activation live fence differs")
    return live


def _standby_compensation_is_quiet(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> bool:
    return (
        _unit_inactive(STANDBY_TARGET, runner=runner)
        and _unit_disabled(STANDBY_TARGET, runner=runner)
        and _unit_inactive(STANDBY_STOP_TIMER, runner=runner)
        and _unit_disabled(STANDBY_STOP_TIMER, runner=runner)
        and _unit_inactive(STANDBY_REPLICATION_SERVE_UNIT, runner=runner)
        and all(
            _unit_inactive(unit, runner=runner)
            and _unit_masked(unit, runner=runner)
            for unit in CAMPAIGN_UNITS
        )
        and not (WRITER_MARKER.exists() or WRITER_MARKER.is_symlink())
    )


def _compensate_failed_standby_replay(
    *,
    release_sha: str,
    intent_path: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    expected_root_uid: int,
    expected_root_gid: int,
    observed_node: str | None,
) -> None:
    """Keep an interrupted standby activation fenced and authority-quiet."""
    intent, _raw, _identity = _read_exact_canonical_json(
        intent_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=STANDBY_ACTIVATION_INTENT_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    if (
        set(intent) != _STANDBY_ACTIVATION_INTENT_FIELDS
        or intent.get("campaign_id") != MISSION_ID
        or intent.get("release_sha") != release_sha
        or intent.get("effect_intent") != "InfrastructureEffect"
        or intent.get("writer_authority_transferred") is not False
    ):
        raise ReleaseContractError("standby crash intent cannot authorize compensation")
    compensation_failed = False
    for command in (
        (SYSTEMCTL_PATH, "disable", "--now", STANDBY_TARGET),
        (SYSTEMCTL_PATH, "disable", "--now", STANDBY_STOP_TIMER),
        (SYSTEMCTL_PATH, "mask", "--now", *CAMPAIGN_UNITS),
    ):
        result = runner(command, cwd=Path("/"), check=False)
        compensation_failed = compensation_failed or result.returncode != 0
    try:
        _stop_standby_serve_for_compensation(
            release_sha=release_sha,
            runner=runner,
            observed_node=observed_node,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
    except ReleaseContractError:
        compensation_failed = True
    if compensation_failed or not _standby_compensation_is_quiet(runner=runner):
        raise ReleaseContractError("standby crash compensation failed")


def activate_standby(
    *,
    role: str,
    release_sha: str,
    receipt_path: Path = STANDBY_ACTIVATION_RECEIPT,
    intent_path: Path = STANDBY_ACTIVATION_INTENT,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    now: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Fence writer units and activate only the receipted append-only standby."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("standby activation requires root")
    _require_host_role(role, observed_node=observed_node)
    if (
        role != "standby"
        or not _COMMIT_RE.fullmatch(release_sha)
        or receipt_path != STANDBY_ACTIVATION_RECEIPT
        or intent_path != STANDBY_ACTIVATION_INTENT
    ):
        raise ReleaseContractError("standby activation binding differs")
    replay = receipt_path.exists() or receipt_path.is_symlink()
    crash_intent = not replay and (intent_path.exists() or intent_path.is_symlink())
    try:
        observed = _sample_utc(
            now=now,
            clock=clock,
            label="standby activation",
        )
        guard_campaign_clock(role=role, now=observed, observed_node=observed_node)
        if WRITER_MARKER.exists() or WRITER_MARKER.is_symlink():
            raise ReleaseContractError("standby activation found writer authority")
        admission, account = _verify_activation_staged_release(
            role=role,
            release_sha=release_sha,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        clock_proof = validate_preactivation_clock_proof(
            release_sha=release_sha,
            role=role,
            known_hosts_sha256=DEPLOYMENT_KNOWN_HOSTS_SHA256,
            staged_release_admission_receipt_digest=admission["receipt_digest"],
            now=observed,
            observed_node=observed_node,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        _validate_installed_standby_replication_route(
            account=account,
            expected_root_uid=expected_root_uid,
        )
        intent, _intent_created = _standby_activation_intent(
            release_sha=release_sha,
            staged_release_admission_receipt_digest=admission["receipt_digest"],
            preactivation_clock_proof_receipt_digest=clock_proof["receipt_digest"],
            path=intent_path,
            runner=runner,
            observed=observed,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        observed = _sample_utc(
            now=now,
            clock=clock,
            label="standby activation completion",
        )
        guard_campaign_clock(role=role, now=observed, observed_node=observed_node)
        clock_proof = validate_preactivation_clock_proof(
            release_sha=release_sha,
            role=role,
            known_hosts_sha256=DEPLOYMENT_KNOWN_HOSTS_SHA256,
            staged_release_admission_receipt_digest=admission["receipt_digest"],
            now=observed,
            observed_node=observed_node,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        if WRITER_MARKER.exists() or WRITER_MARKER.is_symlink():
            raise ReleaseContractError(
                "standby activation found writer authority before effect"
            )
    except Exception:
        if crash_intent:
            _compensate_failed_standby_replay(
                release_sha=release_sha,
                intent_path=intent_path,
                runner=runner,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
                observed_node=observed_node,
            )
        raise
    expected = {
        "activation_intent_receipt_digest": intent["receipt_digest"],
        "staged_release_admission_receipt_digest": admission["receipt_digest"],
        "preactivation_clock_proof_receipt_digest": clock_proof["receipt_digest"],
        "writer_authority_transferred": False,
        "effect": "InfrastructureEffect",
    }
    if receipt_path.exists() or receipt_path.is_symlink():
        prior, _raw, _identity = _read_exact_canonical_json(
            receipt_path,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
            expected_schema=STANDBY_ACTIVATION_SCHEMA_VERSION,
            digest_field="receipt_digest",
        )
        live = _standby_activation_live_state(
            release_sha=release_sha,
            runner=runner,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        if (
            set(prior) != _STANDBY_ACTIVATION_FIELDS
            or prior.get("campaign_id") != MISSION_ID
            or prior.get("release_sha") != release_sha
            or any(prior.get(key) != value for key, value in expected.items())
            or any(prior.get(key) != value for key, value in live.items())
        ):
            raise ReleaseContractError("standby activation receipt differs")
        return prior
    try:
        reloaded = runner(
            (SYSTEMCTL_PATH, "daemon-reload"), cwd=Path("/"), check=False
        )
        if reloaded.returncode != 0:
            raise ReleaseContractError("standby systemd daemon reload failed")
        masked = runner(
            (SYSTEMCTL_PATH, "mask", "--now", *CAMPAIGN_UNITS),
            cwd=Path("/"),
            check=False,
        )
        if masked.returncode != 0:
            raise ReleaseContractError("standby writer-unit fence failed")
        started = runner(
            (
                SYSTEMCTL_PATH,
                "enable",
                "--now",
                STANDBY_STOP_TIMER,
                STANDBY_TARGET,
            ),
            cwd=Path("/"),
            check=False,
        )
        if started.returncode != 0:
            raise ReleaseContractError("standby receiver activation failed")
        live = _standby_activation_live_state(
            release_sha=release_sha,
            runner=runner,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        payload: dict[str, Any] = {
            "schema_version": STANDBY_ACTIVATION_SCHEMA_VERSION,
            "campaign_id": MISSION_ID,
            "release_sha": release_sha,
            "activated_at": observed.isoformat().replace("+00:00", "Z"),
            **expected,
            **live,
            "receipt_digest": "",
        }
        payload["receipt_digest"] = _canonical_self_digest(
            payload, "receipt_digest"
        )
        if set(payload) != _STANDBY_ACTIVATION_FIELDS:
            raise ReleaseContractError("standby activation receipt fields differ")
        return _publish_or_replay_private_receipt(
            receipt_path,
            payload,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
        )
    except Exception as exc:
        compensation_failed = False
        for command in (
            (SYSTEMCTL_PATH, "disable", "--now", STANDBY_TARGET),
            (SYSTEMCTL_PATH, "disable", "--now", STANDBY_STOP_TIMER),
            (SYSTEMCTL_PATH, "mask", "--now", *CAMPAIGN_UNITS),
        ):
            result = runner(command, cwd=Path("/"), check=False)
            compensation_failed = compensation_failed or result.returncode != 0
        try:
            _stop_standby_serve_for_compensation(
                release_sha=release_sha,
                runner=runner,
                observed_node=observed_node,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
        except ReleaseContractError:
            compensation_failed = True
        compensation_failed = compensation_failed or not (
            _standby_compensation_is_quiet(runner=runner)
        )
        if compensation_failed:
            raise ReleaseContractError("standby activation compensation failed") from exc
        raise


def activation_commands(role: str) -> tuple[tuple[str, ...], ...]:
    """Prevent bypassing either receipted activation transaction."""
    if role == "writer":
        raise ReleaseContractError("writer activation requires activate-predispatch")
    if role == "standby":
        raise ReleaseContractError("standby activation requires activate-standby")
    raise ReleaseContractError("role must be writer or standby")


def _read_tailscale_config(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> dict[str, Any]:
    """Read the declarative named-Services scope without emitting its bytes."""
    result = runner(
        (TAILSCALE_PATH, "serve", "get-config", "--all"),
        cwd=Path("/"),
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseContractError("cannot read the node-scoped Tailscale Serve config")
    try:
        raw = result.stdout.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ReleaseContractError("Tailscale Serve config is not UTF-8") from exc
    if not 0 < len(raw) <= _MAX_TAILSCALE_CONFIG_BYTES:
        raise ReleaseContractError("Tailscale Serve config exceeds its size bound")
    try:
        config = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseContractError("Tailscale Serve config is not valid JSON") from exc
    if not isinstance(config, dict):
        raise ReleaseContractError("Tailscale Serve config root must be an object")
    return config


def _require_tailscale_version(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """Fail closed when the probed Serve CLI semantics may have changed."""
    result = runner(
        (TAILSCALE_PATH, "version"),
        cwd=Path("/"),
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseContractError("cannot identify the Tailscale runtime version")
    try:
        raw = result.stdout.encode("ascii", errors="strict")
    except UnicodeError as exc:
        raise ReleaseContractError("Tailscale runtime version is not ASCII") from exc
    if (
        not 0 < len(raw) <= _MAX_TAILSCALE_VERSION_BYTES
        or b"\x00" in raw
        or raw.splitlines()[:1] != [TAILSCALE_VERSION.encode("ascii")]
    ):
        raise ReleaseContractError("Tailscale runtime version differs from the probe")


def _read_tailscale_status(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> dict[str, Any]:
    """Read the raw node-level TCP/Web Serve config used by background Serve."""
    result = runner(
        (TAILSCALE_PATH, "serve", "status", "--json"),
        cwd=Path("/"),
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseContractError("cannot read the raw Tailscale Serve status")
    try:
        raw = result.stdout.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ReleaseContractError("Tailscale Serve status is not UTF-8") from exc
    if not 0 < len(raw) <= _MAX_TAILSCALE_CONFIG_BYTES:
        raise ReleaseContractError("Tailscale Serve status exceeds its size bound")
    try:
        status = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseContractError("Tailscale Serve status is not valid JSON") from exc
    if not isinstance(status, dict):
        raise ReleaseContractError("Tailscale Serve status root must be an object")
    return status


def _require_empty_tailscale_serve(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> dict[str, Any]:
    # get-config --all covers named Services, while status --json carries the
    # node-scoped TCP/Web route. Both scopes must be empty before node reset can
    # ever be owned safely.
    _require_tailscale_version(runner=runner)
    config = _read_tailscale_config(runner=runner)
    status = _read_tailscale_status(runner=runner)
    if config != TAILSCALE_EMPTY_CONFIG or status != {}:
        raise ReleaseContractError(
            "Tailscale Serve already has configuration; preserving it requires review"
        )
    return status


def _validate_owned_tailscale_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Admit only the single private HTTPS proxy installed by this campaign."""
    if set(config) != {"TCP", "Web"}:
        raise ReleaseContractError("Tailscale Serve config is not campaign-exclusive")
    if config.get("TCP") != {"443": {"HTTPS": True}}:
        raise ReleaseContractError(
            "Tailscale Serve transport differs from private HTTPS"
        )
    web = config.get("Web")
    if not isinstance(web, dict) or len(web) != 1:
        raise ReleaseContractError("Tailscale Serve web scope is not exclusive")
    host_port, web_config = next(iter(web.items()))
    if (
        not isinstance(host_port, str)
        or not host_port.startswith(f"{WRITER_NODE}.")
        or not host_port.endswith(".ts.net:443")
        or host_port != host_port.lower()
        or any(character.isspace() for character in host_port)
        or web_config != {"Handlers": {"/": {"Proxy": TAILSCALE_ROUTE}}}
    ):
        raise ReleaseContractError(
            "Tailscale Serve route differs from the pinned proxy"
        )
    # Funnel is represented by top-level AllowFunnel. Requiring the exact key set
    # above makes public ingress and every unrelated node handler uninhabitable.
    return dict(config)


def _tailscale_config_digest(config: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(config)).hexdigest()


def _write_tailscale_ownership_receipt(
    path: Path,
    config: Mapping[str, Any],
    *,
    release_sha: str,
    intent: Mapping[str, Any],
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    admitted = _validate_owned_tailscale_config(config)
    payload: dict[str, Any] = {
        "schema_version": TAILSCALE_OWNERSHIP_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "route": TAILSCALE_ROUTE,
        "tailscale_version": TAILSCALE_VERSION,
        "intent_receipt_digest": intent["receipt_digest"],
        "serve_status_before_sha256": intent["serve_status_before_sha256"],
        "config_sha256": _tailscale_config_digest(admitted),
        "config": admitted,
        "effect": "InfrastructureEffect",
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    return _publish_or_replay_private_receipt(
        path,
        payload,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )


def _load_tailscale_intent_receipt(
    path: Path,
    *,
    release_sha: str,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    receipt, _raw, _identity = _read_exact_canonical_json(
        path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=TAILSCALE_INTENT_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    if (
        set(receipt)
        != {
            "schema_version",
            "campaign_id",
            "release_sha",
            "route",
            "tailscale_version",
            "serve_status_before_sha256",
            "named_config_before_sha256",
            "effect_intent",
            "receipt_digest",
        }
        or receipt.get("campaign_id") != MISSION_ID
        or receipt.get("release_sha") != release_sha
        or receipt.get("route") != TAILSCALE_ROUTE
        or receipt.get("tailscale_version") != TAILSCALE_VERSION
        or receipt.get("serve_status_before_sha256")
        != _tailscale_config_digest({})
        or receipt.get("named_config_before_sha256")
        != _tailscale_config_digest(TAILSCALE_EMPTY_CONFIG)
        or receipt.get("effect_intent") != "InfrastructureEffect"
    ):
        raise ReleaseContractError("Tailscale intent receipt binding differs")
    return receipt


def _load_tailscale_ownership_receipt(
    path: Path,
    *,
    release_sha: str,
    intent_path: Path | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    intent_path = intent_path or TAILSCALE_INTENT_RECEIPT
    receipt, _raw, _identity = _read_exact_canonical_json(
        path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=TAILSCALE_OWNERSHIP_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    expected_fields = {
        "schema_version",
        "campaign_id",
        "release_sha",
        "route",
        "tailscale_version",
        "intent_receipt_digest",
        "serve_status_before_sha256",
        "config_sha256",
        "config",
        "effect",
        "receipt_digest",
    }
    config = receipt.get("config")
    if (
        set(receipt) != expected_fields
        or receipt.get("schema_version") != TAILSCALE_OWNERSHIP_SCHEMA_VERSION
        or receipt.get("campaign_id") != MISSION_ID
        or receipt.get("release_sha") != release_sha
        or receipt.get("route") != TAILSCALE_ROUTE
        or receipt.get("tailscale_version") != TAILSCALE_VERSION
        or receipt.get("serve_status_before_sha256")
        != _tailscale_config_digest({})
        or receipt.get("effect") != "InfrastructureEffect"
        or not isinstance(config, dict)
    ):
        raise ReleaseContractError("Tailscale ownership receipt binding differs")
    intent = _load_tailscale_intent_receipt(
        intent_path,
        release_sha=release_sha,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if receipt.get("intent_receipt_digest") != intent["receipt_digest"]:
        raise ReleaseContractError("Tailscale ownership intent differs")
    admitted = _validate_owned_tailscale_config(config)
    if receipt.get("config_sha256") != _tailscale_config_digest(admitted):
        raise ReleaseContractError("Tailscale ownership receipt digest differs")
    return receipt


def _load_tailscale_stop_receipt(
    path: Path,
    *,
    release_sha: str,
    ownership: Mapping[str, Any],
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    receipt, _raw, _identity = _read_exact_canonical_json(
        path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=TAILSCALE_STOP_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    expected = {
        "schema_version": TAILSCALE_STOP_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "ownership_receipt_digest": ownership.get("receipt_digest"),
        "empty_status_sha256": _tailscale_config_digest({}),
        "empty_named_config_sha256": _tailscale_config_digest(
            TAILSCALE_EMPTY_CONFIG
        ),
        "effect": "InfrastructureEffect",
    }
    if set(receipt) != {*expected, "receipt_digest"} or any(
        receipt.get(key) != value for key, value in expected.items()
    ):
        raise ReleaseContractError("Tailscale stop receipt binding differs")
    return receipt


def tailscale_start(
    *,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    receipt_path: Path = TAILSCALE_OWNERSHIP_RECEIPT,
    intent_path: Path = TAILSCALE_INTENT_RECEIPT,
    stop_receipt_path: Path = TAILSCALE_STOP_RECEIPT,
    now: datetime | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> str:
    """Intent-first private Serve mutation with crash-finalizable ownership."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("Tailscale start requires root")
    guard_campaign_clock(role="writer", now=now, observed_node=observed_node)
    _wait_for_dashboard_ingress(release_sha=release_sha, runner=runner)
    _require_tailscale_version(runner=runner)
    if _read_tailscale_config(runner=runner) != TAILSCALE_EMPTY_CONFIG:
        raise ReleaseContractError("named Tailscale service appeared before Serve")
    before_status = _read_tailscale_status(runner=runner)
    if intent_path.exists() or intent_path.is_symlink():
        intent = _load_tailscale_intent_receipt(
            intent_path,
            release_sha=release_sha,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
    else:
        if before_status != {}:
            raise ReleaseContractError(
                "Tailscale Serve already has configuration before durable intent"
            )
        intent_payload: dict[str, Any] = {
            "schema_version": TAILSCALE_INTENT_SCHEMA_VERSION,
            "campaign_id": MISSION_ID,
            "release_sha": release_sha,
            "route": TAILSCALE_ROUTE,
            "tailscale_version": TAILSCALE_VERSION,
            "serve_status_before_sha256": _tailscale_config_digest(before_status),
            "named_config_before_sha256": _tailscale_config_digest(
                TAILSCALE_EMPTY_CONFIG
            ),
            "effect_intent": "InfrastructureEffect",
            "receipt_digest": "",
        }
        intent_payload["receipt_digest"] = _canonical_self_digest(
            intent_payload,
            "receipt_digest",
        )
        intent = _publish_or_replay_private_receipt(
            intent_path,
            intent_payload,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
        )
    if receipt_path.exists() or receipt_path.is_symlink():
        ownership = _load_tailscale_ownership_receipt(
            receipt_path,
            release_sha=release_sha,
            intent_path=intent_path,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        if before_status == {}:
            _load_tailscale_stop_receipt(
                stop_receipt_path,
                release_sha=release_sha,
                ownership=ownership,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
            result = runner(
                (TAILSCALE_PATH, "serve", "--bg", "--https=443", TAILSCALE_ROUTE),
                cwd=Path("/"),
                check=False,
            )
            if result.returncode != 0:
                raise ReleaseContractError(
                    "private Tailscale Serve route could not restart"
                )
            before_status = _read_tailscale_status(runner=runner)
        live = _validate_owned_tailscale_config(before_status)
        if _canonical_bytes(live) != _canonical_bytes(ownership["config"]):
            raise ReleaseContractError("live private Serve differs on replay")
        return ownership["config_sha256"]
    if before_status == {}:
        result = runner(
            (TAILSCALE_PATH, "serve", "--bg", "--https=443", TAILSCALE_ROUTE),
            cwd=Path("/"),
            check=False,
        )
        if result.returncode != 0:
            raise ReleaseContractError("private Tailscale Serve route could not start")
        before_status = _read_tailscale_status(runner=runner)
    config = _validate_owned_tailscale_config(before_status)
    ownership = _write_tailscale_ownership_receipt(
        receipt_path,
        config,
        release_sha=release_sha,
        intent=intent,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    return ownership["config_sha256"]


def tailscale_stop(
    *,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    receipt_path: Path = TAILSCALE_OWNERSHIP_RECEIPT,
    intent_path: Path = TAILSCALE_INTENT_RECEIPT,
    stop_receipt_path: Path = TAILSCALE_STOP_RECEIPT,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> None:
    """Reset only exact owned bytes; replay proves the durable empty poststate."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("Tailscale stop requires root")
    _require_host_role("writer", observed_node=observed_node)
    if not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("Tailscale stop release binding differs")
    _require_tailscale_version(runner=runner)
    receipt = _load_tailscale_ownership_receipt(
        receipt_path,
        release_sha=release_sha,
        intent_path=intent_path,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if _read_tailscale_config(runner=runner) != TAILSCALE_EMPTY_CONFIG:
        raise ReleaseContractError(
            "named Tailscale Services appeared; preserving them instead of resetting"
        )
    live_status = _read_tailscale_status(runner=runner)
    if live_status != {}:
        live = _validate_owned_tailscale_config(live_status)
        if (
            _canonical_bytes(live) != _canonical_bytes(receipt["config"])
            or _tailscale_config_digest(live) != receipt["config_sha256"]
        ):
            raise ReleaseContractError(
                "Tailscale Serve config drifted; preserving it instead of resetting"
            )
        result = runner(
            (TAILSCALE_PATH, "serve", "reset"),
            cwd=Path("/"),
            check=False,
        )
        if result.returncode != 0:
            raise ReleaseContractError("owned Tailscale Serve config could not reset")
    _require_empty_tailscale_serve(runner=runner)
    stop_payload: dict[str, Any] = {
        "schema_version": TAILSCALE_STOP_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "ownership_receipt_digest": receipt["receipt_digest"],
        "empty_status_sha256": _tailscale_config_digest({}),
        "empty_named_config_sha256": _tailscale_config_digest(
            TAILSCALE_EMPTY_CONFIG
        ),
        "effect": "InfrastructureEffect",
        "receipt_digest": "",
    }
    stop_payload["receipt_digest"] = _canonical_self_digest(
        stop_payload,
        "receipt_digest",
    )
    _publish_or_replay_private_receipt(
        stop_receipt_path,
        stop_payload,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )


def _validate_standby_tailscale_status(
    status: Mapping[str, Any],
) -> dict[str, Any]:
    """Admit only tailnet TCP 2222 forwarding to the local OpenSSH listener."""
    if dict(status) != STANDBY_TAILSCALE_STATUS:
        raise ReleaseContractError(
            "standby Tailscale Serve status differs from the owned TCP bridge"
        )
    return dict(status)


def _load_standby_tailscale_intent_receipt(
    path: Path,
    *,
    release_sha: str,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    receipt, _raw, _identity = _read_exact_canonical_json(
        path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=STANDBY_TAILSCALE_INTENT_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    expected = {
        "schema_version": STANDBY_TAILSCALE_INTENT_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "route": STANDBY_TAILSCALE_ROUTE,
        "tailnet_port": STANDBY_TAILSCALE_PORT,
        "local_endpoint": "localhost:22",
        "tailscale_version": TAILSCALE_VERSION,
        "serve_status_before_sha256": _tailscale_config_digest({}),
        "named_config_before_sha256": _tailscale_config_digest(
            TAILSCALE_EMPTY_CONFIG
        ),
        "end_to_end_route_verified": False,
        "effect_intent": "InfrastructureEffect",
    }
    if set(receipt) != _STANDBY_TAILSCALE_INTENT_FIELDS or any(
        receipt.get(key) != value for key, value in expected.items()
    ):
        raise ReleaseContractError("standby Serve intent receipt binding differs")
    return receipt


def _write_standby_tailscale_ownership_receipt(
    path: Path,
    status: Mapping[str, Any],
    *,
    release_sha: str,
    intent: Mapping[str, Any],
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    admitted = _validate_standby_tailscale_status(status)
    payload: dict[str, Any] = {
        "schema_version": STANDBY_TAILSCALE_OWNERSHIP_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "route": STANDBY_TAILSCALE_ROUTE,
        "tailnet_port": STANDBY_TAILSCALE_PORT,
        "local_endpoint": "localhost:22",
        "tailscale_version": TAILSCALE_VERSION,
        "intent_receipt_digest": intent["receipt_digest"],
        "serve_status_before_sha256": intent["serve_status_before_sha256"],
        "config_sha256": _tailscale_config_digest(admitted),
        "config": admitted,
        "end_to_end_route_verified": False,
        "effect": "InfrastructureEffect",
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    if set(payload) != _STANDBY_TAILSCALE_OWNERSHIP_FIELDS:
        raise ReleaseContractError("standby Serve ownership fields differ")
    return _publish_or_replay_private_receipt(
        path,
        payload,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )


def _load_standby_tailscale_ownership_receipt(
    path: Path,
    *,
    release_sha: str,
    intent_path: Path = STANDBY_TAILSCALE_INTENT_RECEIPT,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    receipt, _raw, _identity = _read_exact_canonical_json(
        path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=STANDBY_TAILSCALE_OWNERSHIP_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    if (
        set(receipt) != _STANDBY_TAILSCALE_OWNERSHIP_FIELDS
        or receipt.get("campaign_id") != MISSION_ID
        or receipt.get("release_sha") != release_sha
        or receipt.get("route") != STANDBY_TAILSCALE_ROUTE
        or receipt.get("tailnet_port") != STANDBY_TAILSCALE_PORT
        or receipt.get("local_endpoint") != "localhost:22"
        or receipt.get("tailscale_version") != TAILSCALE_VERSION
        or receipt.get("serve_status_before_sha256")
        != _tailscale_config_digest({})
        or receipt.get("end_to_end_route_verified") is not False
        or receipt.get("effect") != "InfrastructureEffect"
        or not isinstance(receipt.get("config"), dict)
    ):
        raise ReleaseContractError("standby Serve ownership receipt binding differs")
    intent = _load_standby_tailscale_intent_receipt(
        intent_path,
        release_sha=release_sha,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    admitted = _validate_standby_tailscale_status(receipt["config"])
    if (
        receipt.get("intent_receipt_digest") != intent["receipt_digest"]
        or receipt.get("config_sha256") != _tailscale_config_digest(admitted)
    ):
        raise ReleaseContractError("standby Serve ownership digest differs")
    return receipt


def _load_standby_tailscale_stop_receipt(
    path: Path,
    *,
    release_sha: str,
    ownership: Mapping[str, Any],
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    receipt, _raw, _identity = _read_exact_canonical_json(
        path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=STANDBY_TAILSCALE_STOP_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    expected = {
        "schema_version": STANDBY_TAILSCALE_STOP_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "tailnet_port": STANDBY_TAILSCALE_PORT,
        "ownership_receipt_digest": ownership.get("receipt_digest"),
        "prestate_sha256": ownership.get("config_sha256"),
        "poststate_sha256": _tailscale_config_digest({}),
        "named_config_sha256": _tailscale_config_digest(TAILSCALE_EMPTY_CONFIG),
        "owned_handler_removed": True,
        "effect": "InfrastructureEffect",
    }
    if set(receipt) != _STANDBY_TAILSCALE_STOP_FIELDS or any(
        receipt.get(key) != value for key, value in expected.items()
    ):
        raise ReleaseContractError("standby Serve stop receipt binding differs")
    return receipt


def _require_standby_tailscale_route_absent(
    *, runner: Callable[..., subprocess.CompletedProcess[str]]
) -> None:
    _require_tailscale_version(runner=runner)
    if _read_tailscale_config(runner=runner) != TAILSCALE_EMPTY_CONFIG:
        raise ReleaseContractError(
            "named Tailscale Services appeared; preserving them unchanged"
        )
    if _read_tailscale_status(runner=runner) != {}:
        raise ReleaseContractError("standby replication Serve route is not absent")


def standby_tailscale_start(
    *,
    role: str,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    receipt_path: Path = STANDBY_TAILSCALE_OWNERSHIP_RECEIPT,
    intent_path: Path = STANDBY_TAILSCALE_INTENT_RECEIPT,
    stop_receipt_path: Path = STANDBY_TAILSCALE_STOP_RECEIPT,
    now: datetime | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Own only AGNI's private 2222-to-localhost:22 Serve handler."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("standby Serve start requires root")
    _require_host_role(role, observed_node=observed_node)
    if role != "standby" or not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("standby Serve start binding differs")
    guard_campaign_clock(role=role, now=now, observed_node=observed_node)
    _require_tailscale_version(runner=runner)
    if _read_tailscale_config(runner=runner) != TAILSCALE_EMPTY_CONFIG:
        raise ReleaseContractError(
            "named Tailscale Services appeared before standby Serve"
        )
    status = _read_tailscale_status(runner=runner)
    if intent_path.exists() or intent_path.is_symlink():
        intent = _load_standby_tailscale_intent_receipt(
            intent_path,
            release_sha=release_sha,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
    else:
        if status != {}:
            raise ReleaseContractError(
                "standby Tailscale Serve was not empty before durable intent"
            )
        intent_payload: dict[str, Any] = {
            "schema_version": STANDBY_TAILSCALE_INTENT_SCHEMA_VERSION,
            "campaign_id": MISSION_ID,
            "release_sha": release_sha,
            "route": STANDBY_TAILSCALE_ROUTE,
            "tailnet_port": STANDBY_TAILSCALE_PORT,
            "local_endpoint": "localhost:22",
            "tailscale_version": TAILSCALE_VERSION,
            "serve_status_before_sha256": _tailscale_config_digest({}),
            "named_config_before_sha256": _tailscale_config_digest(
                TAILSCALE_EMPTY_CONFIG
            ),
            "end_to_end_route_verified": False,
            "effect_intent": "InfrastructureEffect",
            "receipt_digest": "",
        }
        intent_payload["receipt_digest"] = _canonical_self_digest(
            intent_payload, "receipt_digest"
        )
        intent = _publish_or_replay_private_receipt(
            intent_path,
            intent_payload,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
        )
    if receipt_path.exists() or receipt_path.is_symlink():
        ownership = _load_standby_tailscale_ownership_receipt(
            receipt_path,
            release_sha=release_sha,
            intent_path=intent_path,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        if status == {}:
            _load_standby_tailscale_stop_receipt(
                stop_receipt_path,
                release_sha=release_sha,
                ownership=ownership,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
            started = runner(
                (
                    TAILSCALE_PATH,
                    "serve",
                    "--bg",
                    f"--tcp={STANDBY_TAILSCALE_PORT}",
                    STANDBY_TAILSCALE_ROUTE,
                ),
                cwd=Path("/"),
                check=False,
            )
            if started.returncode != 0:
                raise ReleaseContractError("standby Serve route could not restart")
            status = _read_tailscale_status(runner=runner)
        admitted = _validate_standby_tailscale_status(status)
        if (
            _canonical_bytes(admitted) != _canonical_bytes(ownership["config"])
            or _tailscale_config_digest(admitted) != ownership["config_sha256"]
        ):
            raise ReleaseContractError("live standby Serve differs on replay")
        return ownership
    if status == {}:
        started = runner(
            (
                TAILSCALE_PATH,
                "serve",
                "--bg",
                f"--tcp={STANDBY_TAILSCALE_PORT}",
                STANDBY_TAILSCALE_ROUTE,
            ),
            cwd=Path("/"),
            check=False,
        )
        if started.returncode != 0:
            raise ReleaseContractError("standby Serve route could not start")
        status = _read_tailscale_status(runner=runner)
    return _write_standby_tailscale_ownership_receipt(
        receipt_path,
        status,
        release_sha=release_sha,
        intent=intent,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )


def standby_tailscale_stop(
    *,
    role: str,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    receipt_path: Path = STANDBY_TAILSCALE_OWNERSHIP_RECEIPT,
    intent_path: Path = STANDBY_TAILSCALE_INTENT_RECEIPT,
    stop_receipt_path: Path = STANDBY_TAILSCALE_STOP_RECEIPT,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Remove only the unchanged owned 2222 handler; never reset node Serve."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("standby Serve stop requires root")
    _require_host_role(role, observed_node=observed_node)
    if role != "standby" or not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("standby Serve stop binding differs")
    _require_tailscale_version(runner=runner)
    ownership = _load_standby_tailscale_ownership_receipt(
        receipt_path,
        release_sha=release_sha,
        intent_path=intent_path,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    if _read_tailscale_config(runner=runner) != TAILSCALE_EMPTY_CONFIG:
        raise ReleaseContractError(
            "named Tailscale Services appeared; preserving them unchanged"
        )
    prestate = _read_tailscale_status(runner=runner)
    if prestate != {}:
        admitted = _validate_standby_tailscale_status(prestate)
        if (
            _canonical_bytes(admitted) != _canonical_bytes(ownership["config"])
            or _tailscale_config_digest(admitted) != ownership["config_sha256"]
        ):
            raise ReleaseContractError(
                "standby Serve drifted; preserving it instead of removing a handler"
            )
        stopped = runner(
            (
                TAILSCALE_PATH,
                "serve",
                f"--tcp={STANDBY_TAILSCALE_PORT}",
                "off",
            ),
            cwd=Path("/"),
            check=False,
        )
        if stopped.returncode != 0:
            raise ReleaseContractError("owned standby Serve handler could not stop")
    elif not (stop_receipt_path.exists() or stop_receipt_path.is_symlink()):
        raise ReleaseContractError(
            "standby Serve disappeared without an owned stop receipt"
        )
    if _read_tailscale_config(runner=runner) != TAILSCALE_EMPTY_CONFIG:
        raise ReleaseContractError("named Tailscale config changed during stop")
    poststate = _read_tailscale_status(runner=runner)
    if poststate != {}:
        raise ReleaseContractError(
            "standby Serve poststate is not prestate minus the owned handler"
        )
    payload: dict[str, Any] = {
        "schema_version": STANDBY_TAILSCALE_STOP_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "tailnet_port": STANDBY_TAILSCALE_PORT,
        "ownership_receipt_digest": ownership["receipt_digest"],
        "prestate_sha256": ownership["config_sha256"],
        "poststate_sha256": _tailscale_config_digest(poststate),
        "named_config_sha256": _tailscale_config_digest(TAILSCALE_EMPTY_CONFIG),
        "owned_handler_removed": True,
        "effect": "InfrastructureEffect",
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    if set(payload) != _STANDBY_TAILSCALE_STOP_FIELDS:
        raise ReleaseContractError("standby Serve stop fields differ")
    _publish_or_replay_private_receipt(
        stop_receipt_path,
        payload,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )
    return _load_standby_tailscale_stop_receipt(
        stop_receipt_path,
        release_sha=release_sha,
        ownership=ownership,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )


def _stop_standby_serve_for_compensation(
    *,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    observed_node: str | None,
    expected_root_uid: int,
    expected_root_gid: int,
) -> None:
    """Finish intent-bound ownership if needed, then remove only that handler."""
    _require_tailscale_version(runner=runner)
    if _read_tailscale_config(runner=runner) != TAILSCALE_EMPTY_CONFIG:
        raise ReleaseContractError(
            "standby compensation found named Tailscale Services"
        )
    status = _read_tailscale_status(runner=runner)
    ownership_exists = (
        STANDBY_TAILSCALE_OWNERSHIP_RECEIPT.exists()
        or STANDBY_TAILSCALE_OWNERSHIP_RECEIPT.is_symlink()
    )
    if not ownership_exists:
        if status == {}:
            return
        admitted = _validate_standby_tailscale_status(status)
        intent = _load_standby_tailscale_intent_receipt(
            STANDBY_TAILSCALE_INTENT_RECEIPT,
            release_sha=release_sha,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        _write_standby_tailscale_ownership_receipt(
            STANDBY_TAILSCALE_OWNERSHIP_RECEIPT,
            admitted,
            release_sha=release_sha,
            intent=intent,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
    standby_tailscale_stop(
        role="standby",
        release_sha=release_sha,
        runner=runner,
        observed_node=observed_node,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )


def _read_route_probe_input(
    path: Path,
    *,
    maximum_bytes: int,
    expected_root_uid: int,
) -> bytes:
    """Stable-read one root-owned 0600/0640 replication input without follows."""
    _require_secure_parent_chain(path)
    try:
        identity = path.lstat()
    except OSError as exc:
        raise ReleaseContractError(
            f"replication probe input is unavailable: {path.name}"
        ) from exc
    if (
        path.is_symlink()
        or not stat.S_ISREG(identity.st_mode)
        or identity.st_uid != expected_root_uid
        or stat.S_IMODE(identity.st_mode) not in {0o600, 0o640}
        or identity.st_nlink != 1
        or not 0 < identity.st_size <= maximum_bytes
    ):
        raise ReleaseContractError(
            f"replication probe input lacks root custody: {path.name}"
        )
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ReleaseContractError("platform lacks no-follow route probe admission")
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        opened = os.fstat(descriptor)
        raw = os.read(descriptor, maximum_bytes + 1)
        stable = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    admitted = (identity.st_dev, identity.st_ino, identity.st_size, identity.st_mtime_ns)
    if (
        admitted
        != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
        or admitted
        != (stable.st_dev, stable.st_ino, stable.st_size, stable.st_mtime_ns)
        or len(raw) != identity.st_size
    ):
        raise ReleaseContractError(f"replication probe input changed: {path.name}")
    return raw


def _load_standby_replication_route_probe(
    *,
    release_sha: str,
    now: datetime,
    path: Path = STANDBY_REPLICATION_ROUTE_PROBE_RECEIPT,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
    require_fresh: bool = True,
) -> dict[str, Any]:
    from scripts.runtime import sadhana_snapshot

    receipt, _raw, _identity = _read_exact_canonical_json(
        path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        expected_schema=STANDBY_REPLICATION_ROUTE_PROBE_SCHEMA_VERSION,
        digest_field="receipt_digest",
    )
    sequence = receipt.get("probe_sequence")
    previous_digest = receipt.get("previous_receipt_digest")
    if (
        set(receipt) != _STANDBY_REPLICATION_ROUTE_PROBE_FIELDS
        or receipt.get("campaign_id") != MISSION_ID
        or receipt.get("release_sha") != release_sha
        or receipt.get("destination") != sadhana_snapshot.STANDBY_DESTINATION
        or receipt.get("tailnet_port") != STANDBY_TAILSCALE_PORT
        or receipt.get("known_hosts_sha256") != DEPLOYMENT_KNOWN_HOSTS_SHA256
        or receipt.get("ssh_transport_policy_sha256")
        != sadhana_snapshot.standby_ssh_policy_digest()
        or not isinstance(receipt.get("bracketed_host_key_sha256"), str)
        or not _SHA_RE.fullmatch(receipt["bracketed_host_key_sha256"])
        or not isinstance(
            receipt.get("standby_serve_ownership_receipt_digest"), str
        )
        or re.fullmatch(
            r"sha256:[0-9a-f]{64}",
            receipt["standby_serve_ownership_receipt_digest"],
        )
        is None
        or isinstance(sequence, bool)
        or not isinstance(sequence, int)
        or not 1 <= sequence <= STANDBY_REPLICATION_ROUTE_PROBE_MAX_SEQUENCE
        or (
            sequence == 1
            and previous_digest is not None
        )
        or (
            sequence > 1
            and (
                not isinstance(previous_digest, str)
                or re.fullmatch(r"sha256:[0-9a-f]{64}", previous_digest) is None
            )
        )
        or any(
            receipt.get(field) is not True
            for field in (
                "keyscan_host_pin_exact",
                "dry_run_rsync_succeeded",
                "arbitrary_command_rejected",
                "interactive_shell_rejected",
                "out_of_root_rsync_rejected",
                "route_verified",
            )
        )
        or receipt.get("remote_state_mutation_performed") is not False
        or receipt.get("verdict") != "PASS"
    ):
        raise ReleaseContractError("standby replication route probe binding differs")
    observed_at = _parse_utc(receipt.get("observed_at", ""), "observed_at")
    valid_until = _parse_utc(receipt.get("valid_until", ""), "valid_until")
    now = now.astimezone(timezone.utc)
    if (
        valid_until
        != observed_at
        + timedelta(seconds=STANDBY_REPLICATION_ROUTE_PROBE_FRESHNESS_SECONDS)
        or now < observed_at
        or (require_fresh and now > valid_until)
    ):
        raise ReleaseContractError("standby replication route probe is not fresh")
    return receipt


def probe_standby_replication_route(
    *,
    role: str,
    release_sha: str,
    standby_serve_ownership_receipt_digest: str,
    ssh_key: Path = STANDBY_REPLICATION_SSH_KEY,
    known_hosts: Path = STANDBY_REPLICATION_KNOWN_HOSTS,
    receipt_path: Path = STANDBY_REPLICATION_ROUTE_PROBE_RECEIPT,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    now: datetime | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Exercise the exact forced-key :2222 route without publishing bytes."""
    from scripts.runtime import sadhana_snapshot

    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("standby replication route probe requires root")
    _require_host_role(role, observed_node=observed_node)
    if (
        role != "writer"
        or not _COMMIT_RE.fullmatch(release_sha)
        or ssh_key != STANDBY_REPLICATION_SSH_KEY
        or known_hosts != STANDBY_REPLICATION_KNOWN_HOSTS
        or receipt_path != STANDBY_REPLICATION_ROUTE_PROBE_RECEIPT
        or re.fullmatch(
            r"sha256:[0-9a-f]{64}", standby_serve_ownership_receipt_digest
        )
        is None
    ):
        raise ReleaseContractError("standby replication route probe binding differs")
    guard_campaign_clock(role=role, now=now, observed_node=observed_node)
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ReleaseContractError("standby replication route probe clock is naive")
    observed = observed.astimezone(timezone.utc).replace(microsecond=0)
    prior: dict[str, Any] | None = None
    if receipt_path.exists() or receipt_path.is_symlink():
        prior = _load_standby_replication_route_probe(
            release_sha=release_sha,
            now=observed,
            path=receipt_path,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
            require_fresh=False,
        )
        if (
            prior["standby_serve_ownership_receipt_digest"]
            != standby_serve_ownership_receipt_digest
        ):
            raise ReleaseContractError("standby route probe ownership differs")
        prior_valid_until = _parse_utc(prior["valid_until"], "valid_until")
        if observed <= prior_valid_until:
            return prior
        if DISPATCH_ENABLE_MARKER.exists() or DISPATCH_ENABLE_MARKER.is_symlink():
            raise ReleaseContractError(
                "standby route probe cannot renew after dispatch authority"
            )
        if prior["probe_sequence"] >= STANDBY_REPLICATION_ROUTE_PROBE_MAX_SEQUENCE:
            raise ReleaseContractError("standby route probe renewal limit reached")
    elif DISPATCH_ENABLE_MARKER.exists() or DISPATCH_ENABLE_MARKER.is_symlink():
        raise ReleaseContractError(
            "standby route probe cannot publish after dispatch authority"
        )
    _read_route_probe_input(
        ssh_key,
        maximum_bytes=64 * 1024,
        expected_root_uid=expected_root_uid,
    )
    known_hosts_raw = _read_route_probe_input(
        known_hosts,
        maximum_bytes=1024 * 1024,
        expected_root_uid=expected_root_uid,
    )
    if hashlib.sha256(known_hosts_raw).hexdigest() != DEPLOYMENT_KNOWN_HOSTS_SHA256:
        raise ReleaseContractError("replication probe known_hosts differs")
    bracketed_lines = [
        line + b"\n"
        for line in known_hosts_raw.splitlines()
        if line.startswith(b"[100.79.111.89]:2222 ")
    ]
    if len(bracketed_lines) != 1:
        raise ReleaseContractError("bracketed AGNI :2222 host pin differs")
    bracketed_host_key = bracketed_lines[0]
    safe_env = {
        "HOME": "/nonexistent",
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
    }
    keyscan = runner(
        (
            SSH_KEYSCAN_PATH,
            "-T",
            "5",
            "-p",
            str(STANDBY_TAILSCALE_PORT),
            "-t",
            "ed25519",
            "100.79.111.89",
        ),
        cwd=Path("/"),
        check=False,
        env=safe_env,
    )
    if keyscan.returncode != 0 or keyscan.stdout.encode("ascii") != bracketed_host_key:
        raise ReleaseContractError("live AGNI :2222 host key differs from its pin")
    transport = sadhana_snapshot.standby_ssh_transport(
        ssh_key=ssh_key,
        known_hosts=known_hosts,
        standby_port=STANDBY_TAILSCALE_PORT,
    )
    ssh_argv = tuple(transport.split())
    destination = sadhana_snapshot.STANDBY_DESTINATION
    with tempfile.TemporaryDirectory(prefix="sadhana-route-probe-") as raw_root:
        source = Path(raw_root)
        positive = runner(
            (
                RSYNC_CLIENT_PATH,
                "--archive",
                "--dry-run",
                "--no-owner",
                "--no-group",
                "--ignore-existing",
                "--delay-updates",
                "-e",
                transport,
                f"{source}/",
                f"{destination}:uploads/.transport-probe/",
            ),
            cwd=Path("/"),
            check=False,
            env=safe_env,
        )
        arbitrary = runner(
            (*ssh_argv, destination, "/usr/bin/true"),
            cwd=Path("/"),
            check=False,
            env=safe_env,
        )
        shell = runner(
            (*ssh_argv, destination),
            cwd=Path("/"),
            check=False,
            env=safe_env,
        )
        traversal = runner(
            (*ssh_argv, destination, "rsync --server . ../escape"),
            cwd=Path("/"),
            check=False,
            env=safe_env,
        )
    if positive.returncode != 0:
        raise ReleaseContractError("standby dry-run rsync probe failed")
    expected_policy_rejections = (
        (
            arbitrary,
            "/usr/bin/rrsync error: SSH_ORIGINAL_COMMAND does not run rsync\n",
        ),
        (shell, "/usr/bin/rrsync error: Not invoked via sshd\n"),
        (
            traversal,
            "/usr/bin/rrsync error: do not use .. in arg "
            "(anchor the path at the root of your restricted dir)\n",
        ),
    )
    if any(
        result.returncode != 1 or result.stderr != expected_stderr
        for result, expected_stderr in expected_policy_rejections
    ):
        raise ReleaseContractError(
            "standby forced-key policy rejection proof differs"
        )
    payload: dict[str, Any] = {
        "schema_version": STANDBY_REPLICATION_ROUTE_PROBE_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "observed_at": observed.isoformat().replace("+00:00", "Z"),
        "valid_until": (
            observed
            + timedelta(seconds=STANDBY_REPLICATION_ROUTE_PROBE_FRESHNESS_SECONDS)
        )
        .isoformat()
        .replace("+00:00", "Z"),
        "destination": destination,
        "tailnet_port": STANDBY_TAILSCALE_PORT,
        "known_hosts_sha256": DEPLOYMENT_KNOWN_HOSTS_SHA256,
        "bracketed_host_key_sha256": hashlib.sha256(
            bracketed_host_key
        ).hexdigest(),
        "ssh_transport_policy_sha256": (
            sadhana_snapshot.standby_ssh_policy_digest()
        ),
        "standby_serve_ownership_receipt_digest": (
            standby_serve_ownership_receipt_digest
        ),
        "probe_sequence": 1 if prior is None else prior["probe_sequence"] + 1,
        "previous_receipt_digest": (
            None if prior is None else prior["receipt_digest"]
        ),
        "keyscan_host_pin_exact": True,
        "dry_run_rsync_succeeded": True,
        "arbitrary_command_rejected": True,
        "interactive_shell_rejected": True,
        "out_of_root_rsync_rejected": True,
        "remote_state_mutation_performed": False,
        "route_verified": True,
        "verdict": "PASS",
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    if set(payload) != _STANDBY_REPLICATION_ROUTE_PROBE_FIELDS:
        raise ReleaseContractError("standby route probe fields differ")
    if prior is None:
        if DISPATCH_ENABLE_MARKER.exists() or DISPATCH_ENABLE_MARKER.is_symlink():
            raise ReleaseContractError(
                "standby route probe cannot publish after dispatch authority"
            )
        return _publish_or_replay_private_receipt(
            receipt_path,
            payload,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
        )
    current = _load_standby_replication_route_probe(
        release_sha=release_sha,
        now=observed,
        path=receipt_path,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
        require_fresh=False,
    )
    if current["receipt_digest"] != prior["receipt_digest"]:
        raise ReleaseContractError("standby route probe changed during renewal")
    if _parse_utc(payload["observed_at"], "observed_at") <= _parse_utc(
        prior["observed_at"], "observed_at"
    ):
        raise ReleaseContractError("standby route probe renewal is not newer")
    if DISPATCH_ENABLE_MARKER.exists() or DISPATCH_ENABLE_MARKER.is_symlink():
        raise ReleaseContractError(
            "standby route probe cannot renew after dispatch authority"
        )
    _atomic_private_bytes(
        receipt_path,
        _canonical_bytes(payload) + b"\n",
        uid=expected_root_uid,
        gid=expected_root_gid,
        replace_existing=True,
    )
    return _load_standby_replication_route_probe(
        release_sha=release_sha,
        now=observed,
        path=receipt_path,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )


def _revalidate_release_rollback_quiet(
    *,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    proc_net_root: Path,
) -> dict[str, bool]:
    """Revalidate every live no-authority postcondition, including on replay."""
    dispatch_target_static_and_inactive = _unit_inactive(
        DISPATCH_TARGET,
        runner=runner,
    ) and _unit_static(DISPATCH_TARGET, runner=runner)
    predispatch_target_disabled = _unit_inactive(
        PREDISPATCH_TARGET,
        runner=runner,
    ) and _unit_disabled(PREDISPATCH_TARGET, runner=runner)
    lifecycle_units_quiet = all(
        _unit_inactive(unit, runner=runner)
        and _unit_disabled(unit, runner=runner)
        for unit in (CAMPAIGN_STOP_TIMER, EMERGENCY_RECOVERY_PATH)
    )
    partof_units_inactive = all(
        _unit_inactive(unit, runner=runner) for unit in _ROLLBACK_QUIET_UNITS
    ) and lifecycle_units_quiet
    campaign_listeners_absent = _campaign_listeners_absent(proc_net_root)
    _require_empty_tailscale_serve(runner=runner)
    writer_marker_removed = not (
        WRITER_MARKER.exists() or WRITER_MARKER.is_symlink()
    )
    release_path = Path(RELEASE_ROOT) / release_sha
    release_tree_retained = (
        release_path.is_dir()
        and not release_path.is_symlink()
        and not (release_path / ".git").exists()
    )
    snapshot_path = Path(SNAPSHOT_ROOT)
    snapshots_retained = snapshot_path.is_dir() and not snapshot_path.is_symlink()
    live = {
        "dispatch_target_static_and_inactive": (
            dispatch_target_static_and_inactive
        ),
        "predispatch_target_disabled": predispatch_target_disabled,
        "partof_units_inactive": partof_units_inactive,
        "campaign_listeners_absent": campaign_listeners_absent,
        "writer_marker_removed": writer_marker_removed,
        "release_tree_retained": release_tree_retained,
        "snapshots_retained": snapshots_retained,
    }
    if not all(live.values()):
        raise ReleaseContractError("release rollback live quiet state differs")
    return live


def execute_release_rollback(
    *,
    role: str,
    release_sha: str,
    receipt_path: Path = ROLLBACK_RECEIPT,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    proc_net_root: Path = Path("/proc/net"),
    now: datetime | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Stop and disable only the exact release, preserving all forensic bytes."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("release rollback requires root")
    _require_host_role(role, observed_node=observed_node)
    if role != "writer" or not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("release rollback binding differs")
    if receipt_path != ROLLBACK_RECEIPT:
        raise ReleaseContractError("release rollback receipt path differs")
    if receipt_path.exists() or receipt_path.is_symlink():
        prior, _raw, _identity = _read_exact_canonical_json(
            receipt_path,
            expected_uid=expected_root_uid,
            expected_gid=expected_root_gid,
            expected_schema=ROLLBACK_SCHEMA_VERSION,
            digest_field="receipt_digest",
        )
        ownership_exists = (
            TAILSCALE_OWNERSHIP_RECEIPT.exists()
            or TAILSCALE_OWNERSHIP_RECEIPT.is_symlink()
        )
        if ownership_exists:
            tailscale_stop(
                release_sha=release_sha,
                runner=runner,
                observed_node=observed_node,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
        live = _revalidate_release_rollback_quiet(
            release_sha=release_sha,
            runner=runner,
            proc_net_root=proc_net_root,
        )
        if (
            set(prior) != _ROLLBACK_RECEIPT_FIELDS
            or prior.get("campaign_id") != MISSION_ID
            or prior.get("release_sha") != release_sha
            or prior.get("authority_transferred") is not False
            or prior.get("owned_serve_removed") is not ownership_exists
            or any(prior.get(key) is not value for key, value in live.items())
        ):
            raise ReleaseContractError("release rollback receipt differs")
        return prior
    dispatch_stop = runner(
        (SYSTEMCTL_PATH, "stop", DISPATCH_TARGET),
        cwd=Path("/"),
        check=False,
    )
    if dispatch_stop.returncode != 0:
        raise ReleaseContractError("release rollback dispatch target stop failed")
    for unit in (
        PREDISPATCH_TARGET,
        EMERGENCY_RECOVERY_PATH,
        CAMPAIGN_STOP_TIMER,
    ):
        result = runner(
            (SYSTEMCTL_PATH, "disable", "--now", unit),
            cwd=Path("/"),
            check=False,
        )
        if result.returncode != 0:
            raise ReleaseContractError("release rollback target disable failed")
    preparation_stop = runner(
        (SYSTEMCTL_PATH, "stop", RUNTIME_PREPARATION_UNIT),
        cwd=Path("/"),
        check=False,
    )
    if preparation_stop.returncode != 0:
        raise ReleaseContractError("release rollback preparation stop failed")
    owned_serve_removed = (
        TAILSCALE_OWNERSHIP_RECEIPT.exists()
        or TAILSCALE_OWNERSHIP_RECEIPT.is_symlink()
    )
    if owned_serve_removed:
        tailscale_stop(
            release_sha=release_sha,
            runner=runner,
            observed_node=observed_node,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
    else:
        _require_empty_tailscale_serve(runner=runner)
    if WRITER_MARKER.exists() or WRITER_MARKER.is_symlink():
        _remove_exact_writer_marker(
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
    live = _revalidate_release_rollback_quiet(
        release_sha=release_sha,
        runner=runner,
        proc_net_root=proc_net_root,
    )
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ReleaseContractError("release rollback clock must be aware")
    payload: dict[str, Any] = {
        "schema_version": ROLLBACK_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "rolled_back_at": observed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "dispatch_target_static_and_inactive": live[
            "dispatch_target_static_and_inactive"
        ],
        "predispatch_target_disabled": live["predispatch_target_disabled"],
        "partof_units_inactive": live["partof_units_inactive"],
        "campaign_listeners_absent": live["campaign_listeners_absent"],
        "owned_serve_removed": owned_serve_removed,
        "writer_marker_removed": live["writer_marker_removed"],
        "release_tree_retained": live["release_tree_retained"],
        "snapshots_retained": live["snapshots_retained"],
        "authority_transferred": False,
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    if set(payload) != _ROLLBACK_RECEIPT_FIELDS:
        raise ReleaseContractError("release rollback receipt fields differ")
    return _publish_or_replay_private_receipt(
        receipt_path,
        payload,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )


def persist_standby_deadline_stop(
    *,
    role: str,
    release_sha: str,
    receipt_path: Path = STANDBY_STOP_MARKER,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    now: datetime | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Receipt the disabled AGNI receiver so reboot stays quiet after deadline."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("standby deadline receipt requires root")
    observed = guard_campaign_stop(role=role, now=now, observed_node=observed_node)
    if role != "standby" or not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("standby deadline binding differs")
    inactive = {
        "receiver_path_inactive": _unit_inactive(
            "dharma-sadhana-standby-snapshot-receiver.path", runner=runner
        ),
        "receiver_timer_inactive": _unit_inactive(
            "dharma-sadhana-standby-snapshot-receiver.timer", runner=runner
        ),
        "receiver_service_inactive": _unit_inactive(
            "dharma-sadhana-standby-snapshot-receiver.service", runner=runner
        ),
        "replication_serve_unit_inactive": _unit_inactive(
            STANDBY_REPLICATION_SERVE_UNIT, runner=runner
        ),
    }
    if not all(inactive.values()) or _unit_active(STANDBY_TARGET, runner=runner):
        raise ReleaseContractError("standby receiver did not become quiet")
    stop_receipt = standby_tailscale_stop(
        role=role,
        release_sha=release_sha,
        runner=runner,
        observed_node=observed_node,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    _require_standby_tailscale_route_absent(runner=runner)
    payload: dict[str, Any] = {
        "schema_version": STANDBY_STOP_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "stopped_at": observed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "standby_target_disabled": True,
        **inactive,
        "replication_serve_stop_receipt_digest": stop_receipt["receipt_digest"],
        "replication_route_absent": True,
        "writer_authority_transferred": False,
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    if set(payload) != _STANDBY_STOP_FIELDS:
        raise ReleaseContractError("standby deadline receipt fields differ")
    return _publish_or_replay_private_receipt(
        receipt_path,
        payload,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )


def persist_campaign_stop(
    *,
    writer_lock_path: Path,
    projection_path: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    receipt_path: Path = STOP_ENFORCEMENT_RECEIPT,
    release_root: Path | None = None,
    now: datetime | None = None,
    observed_node: str | None = None,
) -> dict[str, Any]:
    """Persist the stop marker after cessation and receipt success or failure."""
    observed = guard_campaign_stop(
        role="writer",
        now=now,
        observed_node=observed_node,
    )
    state_root = Path(STATE_ROOT)
    _require_env_path_within(
        {"writer_lock_path": str(writer_lock_path)},
        "writer_lock_path",
        state_root,
        "stop",
    )
    if (
        projection_path != WRITER_PROJECTION_PATH
        or projection_path.parent != PROJECTION_SOURCE_ROOT
    ):
        raise ReleaseContractError("stop projection path differs")
    service = _require_static_service_identity()
    _read_scoped_runtime_source(
        projection_path,
        parent_uid=service.pw_uid,
        parent_gid=service.pw_gid,
        file_uid=service.pw_uid,
        file_gid=service.pw_gid,
        maximum_bytes=32 * 1024 * 1024,
    )
    if receipt_path != state_root / "stop-enforcement-receipt.json":
        raise ReleaseContractError(
            "stop receipt path differs from the exact state root"
        )
    persistence_exit_code = -1
    try:
        root = (release_root or Path(__file__).resolve().parents[2]).resolve(
            strict=True
        )
        python = root / ".venv" / "bin" / "python"
        campaign = root / "scripts" / "runtime" / "mission_control_campaign.py"
        for executable in (python, campaign):
            if executable.is_symlink() or not executable.is_file():
                raise ReleaseContractError("stop persistence executable is unavailable")
        result = runner(
            (
                str(python),
                str(campaign),
                "stop",
                "--state-dir",
                str(state_root),
                "--mission-id",
                MISSION_ID,
                "--lock-path",
                str(writer_lock_path),
                "--projection-path",
                str(projection_path),
            ),
            cwd=Path(WORKSPACE_ROOT),
            check=False,
        )
        persistence_exit_code = result.returncode
    except (OSError, ReleaseContractError):
        # Cessation already completed in the preceding systemd ExecStart.  The
        # private receipt records the failed persistence attempt without ever
        # serializing an exception (which may carry provider or child details).
        persistence_exit_code = -1
    payload: dict[str, Any] = {
        "schema_version": "dharma.sadhana.stop_enforcement.v1",
        "mission_id": MISSION_ID,
        "campaign_stop_utc": CAMPAIGN_STOP_UTC,
        "observed_at": observed.isoformat().replace("+00:00", "Z"),
        "target_stop_completed": True,
        "durable_marker_persisted": persistence_exit_code == 0,
        "persistence_exit_code": persistence_exit_code,
        "command_output_recorded": False,
    }
    _require_secure_parent_chain(receipt_path)
    if receipt_path.exists() or receipt_path.is_symlink():
        raise ReleaseContractError("stop enforcement receipt already exists")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    if not getattr(os, "O_NOFOLLOW", 0):
        raise ReleaseContractError("platform lacks no-follow stop receipt creation")
    descriptor = os.open(receipt_path, flags, 0o600)
    try:
        _write_all(descriptor, _canonical_bytes(payload) + b"\n")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return payload


def _ensure_host_directory(path: Path, *, uid: int, gid: int, mode: int) -> None:
    """Create one campaign-owned directory without following an existing link."""
    if not path.is_absolute():
        raise ReleaseContractError("host directory must be absolute")
    parent = path.parent.lstat()
    if (
        not stat.S_ISDIR(parent.st_mode)
        or path.parent.is_symlink()
        or parent.st_uid != 0
        or stat.S_IMODE(parent.st_mode) & 0o022
    ):
        raise ReleaseContractError(
            f"host directory parent lacks root custody: {path.parent.name}"
        )
    try:
        identity = path.lstat()
    except FileNotFoundError:
        os.mkdir(path, mode)
        identity = path.lstat()
    if not stat.S_ISDIR(identity.st_mode) or path.is_symlink():
        raise ReleaseContractError(
            f"host directory is not a real directory: {path.name}"
        )
    os.chown(path, uid, gid)
    os.chmod(path, mode)
    final = path.lstat()
    if (
        final.st_uid != uid
        or final.st_gid != gid
        or stat.S_IMODE(final.st_mode) != mode
    ):
        raise ReleaseContractError(f"host directory custody differs: {path.name}")


def _ensure_exact_host_directory(
    path: Path,
    *,
    parent_uid: int,
    parent_gid: int,
    parent_mode: int,
    uid: int,
    gid: int,
    mode: int,
) -> None:
    """Create a leaf once, or admit an existing exact leaf without repairing it."""
    if (
        not path.is_absolute()
        or path.name in {"", ".", ".."}
        or ".." in path.parts
    ):
        raise ReleaseContractError("exact host directory path differs")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    if not nofollow or not directory:
        raise ReleaseContractError(
            "platform lacks no-follow exact host directory admission"
        )
    _require_secure_parent_chain(path)
    parent_descriptor: int | None = None
    descriptor: int | None = None
    created_identity: os.stat_result | None = None
    created = False
    try:
        parent_descriptor = os.open(
            path.parent,
            os.O_RDONLY | nofollow | directory,
        )
        parent = os.fstat(parent_descriptor)
        if (
            not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != parent_uid
            or parent.st_gid != parent_gid
            or stat.S_IMODE(parent.st_mode) != parent_mode
        ):
            raise ReleaseContractError(
                f"exact host directory parent custody differs: {path.parent.name}"
            )
        try:
            os.mkdir(path.name, 0o700, dir_fd=parent_descriptor)
            created = True
            created_identity = os.stat(
                path.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileExistsError:
            pass
        descriptor = os.open(
            path.name,
            os.O_RDONLY | nofollow | directory,
            dir_fd=parent_descriptor,
        )
        opened = os.fstat(descriptor)
        observed = os.stat(
            path.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISDIR(opened.st_mode)
            or (opened.st_dev, opened.st_ino) != (observed.st_dev, observed.st_ino)
        ):
            raise ReleaseContractError(
                f"exact host directory identity differs: {path.name}"
            )
        if created:
            os.fchown(descriptor, uid, gid)
            os.fchmod(descriptor, mode)
            os.fsync(descriptor)
            os.fsync(parent_descriptor)
        final = os.fstat(descriptor)
        observed = os.stat(
            path.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISDIR(final.st_mode)
            or (final.st_dev, final.st_ino) != (observed.st_dev, observed.st_ino)
            or final.st_uid != uid
            or final.st_gid != gid
            or stat.S_IMODE(final.st_mode) != mode
        ):
            raise ReleaseContractError(
                f"exact host directory custody differs: {path.name}"
            )
    except Exception as exc:
        if created and parent_descriptor is not None:
            try:
                current = os.stat(
                    path.name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
                identity_matches = created_identity is None or (
                    current.st_dev,
                    current.st_ino,
                ) == (created_identity.st_dev, created_identity.st_ino)
                descriptor_matches = descriptor is None
                if descriptor is not None:
                    opened = os.fstat(descriptor)
                    descriptor_matches = (opened.st_dev, opened.st_ino) == (
                        current.st_dev,
                        current.st_ino,
                    )
                if (
                    stat.S_ISDIR(current.st_mode)
                    and identity_matches
                    and descriptor_matches
                ):
                    # The exact parent is root-custodied.  rmdir supplies the
                    # final nonempty/replacement refusal even if the initial
                    # post-mkdir stat or open failed.
                    os.rmdir(path.name, dir_fd=parent_descriptor)
                    os.fsync(parent_descriptor)
            except OSError:
                pass
        if isinstance(exc, ReleaseContractError):
            raise
        raise ReleaseContractError(
            f"exact host directory unavailable: {path.name}"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent_descriptor is not None:
            os.close(parent_descriptor)


def _require_existing_root_directory(path: Path) -> None:
    try:
        identity = path.lstat()
    except OSError as exc:
        raise ReleaseContractError(
            f"required host directory is unavailable: {path.name}"
        ) from exc
    if (
        not stat.S_ISDIR(identity.st_mode)
        or path.is_symlink()
        or identity.st_uid != 0
        or stat.S_IMODE(identity.st_mode) & 0o022
    ):
        raise ReleaseContractError(
            f"required host directory lacks root custody: {path.name}"
        )


def _admit_preexisting_host_scaffolding(
    *,
    role: str,
    account: pwd.struct_passwd,
    observed_node: str,
    now: datetime | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Receipt the exact empty VPS scaffolding before its custody transition."""
    application_root = Path(RELEASE_ROOT).parent
    data_root = Path(STATE_ROOT).parent
    expected_prestate = {
        str(application_root): (
            expected_root_uid,
            expected_root_gid,
            0o700,
            ("releases",),
        ),
        str(application_root / "releases"): (
            expected_root_uid,
            expected_root_gid,
            0o700,
            (),
        ),
        str(data_root): (
            expected_root_uid,
            expected_root_gid,
            0o700,
            ("leases", "snapshots", "state", "workspace"),
        ),
        str(data_root / "leases"): (
            expected_root_uid,
            expected_root_gid,
            0o700,
            (),
        ),
        str(data_root / "snapshots"): (
            expected_root_uid,
            expected_root_gid,
            0o700,
            (),
        ),
        str(data_root / "state"): (
            expected_root_uid,
            expected_root_gid,
            0o700,
            (),
        ),
        str(data_root / "workspace"): (
            expected_root_uid,
            expected_root_gid,
            0o700,
            (),
        ),
    }
    expected_poststate = {
        str(application_root): (expected_root_uid, expected_root_gid, 0o755),
        str(application_root / "releases"): (
            expected_root_uid,
            expected_root_gid,
            0o755,
        ),
        str(data_root): (expected_root_uid, expected_root_gid, 0o755),
        str(data_root / "leases"): (account.pw_uid, account.pw_gid, 0o700),
        str(data_root / "snapshots"): (
            (
                expected_root_uid,
                account.pw_gid,
                0o750,
            )
            if role == "writer"
            else (expected_root_uid, expected_root_gid, 0o700)
        ),
        str(data_root / "state"): (account.pw_uid, account.pw_gid, 0o700),
        str(data_root / "workspace"): (account.pw_uid, account.pw_gid, 0o700),
    }
    expected_prestate_receipt = {
        raw_path: {
            "uid": uid,
            "gid": gid,
            "mode": f"{mode:04o}",
            "children": list(children),
        }
        for raw_path, (uid, gid, mode, children) in expected_prestate.items()
    }
    expected_poststate_receipt = {
        raw_path: {"uid": uid, "gid": gid, "mode": f"{mode:04o}"}
        for raw_path, (uid, gid, mode) in expected_poststate.items()
    }
    if HOST_SCAFFOLD_RECEIPT.exists() or HOST_SCAFFOLD_RECEIPT.is_symlink():
        receipt = _secure_json(HOST_SCAFFOLD_RECEIPT, require_private=True)
        unsigned = {
            key: value for key, value in receipt.items() if key != "receipt_digest"
        }
        if (
            receipt.get("receipt_digest")
            != hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()
            or receipt.get("schema_version")
            != "dharma.sadhana.host_scaffold_admission.v1"
            or receipt.get("mission_id") != MISSION_ID
            or receipt.get("role") != role
            or receipt.get("hostname") != observed_node
            or receipt.get("preexisting_empty_scaffolding") is not True
            or receipt.get("data_deleted") is not False
            or receipt.get("release_sha_preexisted") is not False
            or receipt.get("prestate") != expected_prestate_receipt
            or receipt.get("poststate") != expected_poststate_receipt
        ):
            raise ReleaseContractError("host scaffolding receipt differs")
        for raw_path, (uid, gid, mode) in expected_poststate.items():
            path = Path(raw_path)
            identity = path.lstat()
            if (
                path.is_symlink()
                or not stat.S_ISDIR(identity.st_mode)
                or identity.st_uid != uid
                or identity.st_gid != gid
                or stat.S_IMODE(identity.st_mode) != mode
            ):
                raise ReleaseContractError("receipted host scaffolding custody differs")
        return receipt

    observed_paths: dict[str, dict[str, Any]] = {}
    for raw_path, (uid, gid, mode, children) in expected_prestate.items():
        path = Path(raw_path)
        try:
            identity = path.lstat()
        except OSError as exc:
            raise ReleaseContractError(
                "expected pre-existing empty host scaffolding is unavailable"
            ) from exc
        if (
            path.is_symlink()
            or not stat.S_ISDIR(identity.st_mode)
            or identity.st_uid != uid
            or identity.st_gid != gid
            or stat.S_IMODE(identity.st_mode) != mode
            or tuple(sorted(child.name for child in path.iterdir())) != children
        ):
            raise ReleaseContractError("pre-existing host scaffolding differs")
        observed_paths[raw_path] = {
            "uid": uid,
            "gid": gid,
            "mode": f"{mode:04o}",
            "children": list(children),
        }
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ReleaseContractError("host scaffolding receipt clock must be aware")
    receipt: dict[str, Any] = {
        "schema_version": "dharma.sadhana.host_scaffold_admission.v1",
        "mission_id": MISSION_ID,
        "role": role,
        "hostname": observed_node,
        "observed_at": observed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "preexisting_empty_scaffolding": True,
        "prestate": observed_paths,
        "poststate": {
            path: {"uid": uid, "gid": gid, "mode": f"{mode:04o}"}
            for path, (uid, gid, mode) in expected_poststate.items()
        },
        "release_sha_preexisted": False,
        "data_deleted": False,
        "receipt_digest": "",
    }
    receipt["receipt_digest"] = hashlib.sha256(
        _canonical_bytes(
            {key: value for key, value in receipt.items() if key != "receipt_digest"}
        )
    ).hexdigest()
    transitioned: list[str] = []
    try:
        for raw_path, (uid, gid, mode) in expected_poststate.items():
            path = Path(raw_path)
            os.chown(path, uid, gid)
            os.chmod(path, mode)
            transitioned.append(raw_path)
        etc_root = WRITER_MARKER.parent
        _ensure_host_directory(
            etc_root,
            uid=expected_root_uid,
            gid=account.pw_gid,
            mode=0o750,
        )
        receipt_parent = HOST_SCAFFOLD_RECEIPT.parent
        receipt_parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _ensure_host_directory(
            receipt_parent,
            uid=expected_root_uid,
            gid=expected_root_gid,
            mode=0o700,
        )
        _atomic_private_bytes(
            HOST_SCAFFOLD_RECEIPT,
            _canonical_bytes(receipt) + b"\n",
            uid=expected_root_uid,
            gid=expected_root_gid,
        )
    except Exception:
        if not HOST_SCAFFOLD_RECEIPT.exists() and not HOST_SCAFFOLD_RECEIPT.is_symlink():
            for raw_path in reversed(transitioned):
                uid, gid, mode, _children = expected_prestate[raw_path]
                path = Path(raw_path)
                os.chown(path, uid, gid)
                os.chmod(path, mode)
        raise
    return receipt


def _prepare_service_identity_and_paths(
    *,
    role: str,
    observed_node: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> pwd.struct_passwd:
    try:
        account = pwd.getpwnam("dharma-sadhana")
    except KeyError:
        runner(
            (
                USERADD_PATH,
                "--system",
                "--user-group",
                "--home-dir",
                "/var/lib/dharma-sadhana",
                "--shell",
                "/bin/sh",
                "dharma-sadhana",
            ),
            cwd=Path("/"),
        )
        account = pwd.getpwnam("dharma-sadhana")
    if (
        account.pw_name != "dharma-sadhana"
        or account.pw_uid == 0
        or account.pw_gid == 0
        or account.pw_dir != "/var/lib/dharma-sadhana"
        or account.pw_shell != "/bin/sh"
    ):
        raise ReleaseContractError("service identity differs from the static account")
    _admit_preexisting_host_scaffolding(
        role=role,
        account=account,
        observed_node=observed_node,
    )
    for path in (
        Path("/opt/dharma-sadhana"),
        Path(RELEASE_ROOT),
        UV_TOOLING_ROOT,
    ):
        _ensure_host_directory(path, uid=0, gid=0, mode=0o755)
    _ensure_host_directory(
        WRITER_MARKER.parent,
        uid=0,
        gid=account.pw_gid,
        mode=0o750,
    )
    for receipt_parent in (
        ROLLBACK_RECEIPT.parent,
        STANDBY_STOP_MARKER.parent,
        RELEASE_RECEIPT_ROOT,
        RUNTIME_BINDING_RECEIPT_TARGET.parent,
    ):
        receipt_parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _ensure_host_directory(receipt_parent, uid=0, gid=0, mode=0o700)
    state_parent = Path("/var/lib/dharma-sadhana")
    _ensure_host_directory(state_parent, uid=0, gid=0, mode=0o755)
    writable_roots = (
        Path(WORKSPACE_ROOT),
        Path(STATE_ROOT),
        PROJECTION_SOURCE_ROOT,
        Path("/var/lib/dharma-sadhana/leases"),
    )
    for path in writable_roots:
        _ensure_host_directory(
            path,
            uid=account.pw_uid,
            gid=account.pw_gid,
            mode=0o700,
        )
    snapshot_mode = 0o750 if role == "writer" else 0o700
    snapshot_gid = account.pw_gid if role == "writer" else 0
    _ensure_host_directory(
        Path(SNAPSHOT_ROOT), uid=0, gid=snapshot_gid, mode=snapshot_mode
    )
    if role == "writer":
        _ensure_host_directory(
            Path(SNAPSHOT_STAGING_ROOT),
            uid=account.pw_uid,
            gid=account.pw_gid,
            mode=0o700,
        )
    else:
        _ensure_host_directory(
            Path(SNAPSHOT_INCOMING_ROOT),
            uid=0,
            gid=account.pw_gid,
            mode=0o750,
        )
        _ensure_host_directory(
            Path(SNAPSHOT_UPLOAD_ROOT),
            uid=account.pw_uid,
            gid=account.pw_gid,
            mode=0o700,
        )
        _ensure_host_directory(
            Path(SNAPSHOT_ACK_ROOT),
            uid=0,
            gid=account.pw_gid,
            mode=0o750,
        )
    for root_owned in (
        Path(SNAPSHOT_FINALIZING_ROOT),
        Path(SNAPSHOT_RECEIVER_CLAIM_ROOT),
        Path(SNAPSHOT_QUARANTINE_ROOT),
        Path(SNAPSHOT_RECEIPT_ROOT),
        Path(SNAPSHOT_OUTBOX_ROOT),
    ):
        _ensure_host_directory(root_owned, uid=0, gid=0, mode=0o700)
    _ensure_host_directory(
        EMERGENCY_INFLIGHT_ROOT,
        uid=0,
        gid=0,
        mode=0o700,
    )
    _ensure_emergency_apply_lock()
    return account


def _ensure_emergency_apply_lock(
    *,
    path: Path | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> None:
    """Precreate the exact empty lock before its systemd parent becomes read-only."""
    target = EMERGENCY_APPLY_LOCK if path is None else path
    if target != EMERGENCY_APPLY_LOCK:
        raise ReleaseContractError("emergency apply lock path differs")
    path = target
    if path.exists() or path.is_symlink():
        identity = path.lstat()
        if (
            path.is_symlink()
            or not stat.S_ISREG(identity.st_mode)
            or identity.st_uid != expected_root_uid
            or identity.st_gid != expected_root_gid
            or stat.S_IMODE(identity.st_mode) != 0o600
            or identity.st_nlink != 1
            or identity.st_size != 0
        ):
            raise ReleaseContractError("emergency apply lock custody differs")
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        if not nofollow:
            raise ReleaseContractError("platform lacks no-follow emergency lock admission")
        descriptor = os.open(path, os.O_RDONLY | nofollow)
        try:
            opened = os.fstat(descriptor)
            if (
                opened.st_dev,
                opened.st_ino,
                opened.st_size,
                opened.st_mtime_ns,
            ) != (
                identity.st_dev,
                identity.st_ino,
                identity.st_size,
                identity.st_mtime_ns,
            ) or os.read(descriptor, 1):
                raise ReleaseContractError("emergency apply lock changed during read")
        finally:
            os.close(descriptor)
        return
    _atomic_private_bytes(
        path,
        b"",
        uid=expected_root_uid,
        gid=expected_root_gid,
    )


def _prepare_control_identity_and_paths(
    *,
    service_account: pwd.struct_passwd,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> pwd.struct_passwd:
    try:
        control = pwd.getpwnam("dharma-sadhana-control")
    except KeyError:
        runner(
            (
                USERADD_PATH,
                "--system",
                "--user-group",
                "--home-dir",
                "/var/lib/dharma-sadhana-control",
                "--shell",
                "/bin/sh",
                "dharma-sadhana-control",
            ),
            cwd=Path("/"),
        )
        control = pwd.getpwnam("dharma-sadhana-control")
    if (
        control.pw_name != "dharma-sadhana-control"
        or control.pw_uid == 0
        or control.pw_gid == 0
        or control.pw_dir != "/var/lib/dharma-sadhana-control"
        or control.pw_shell != "/bin/sh"
        or control.pw_uid == service_account.pw_uid
        or control.pw_gid == service_account.pw_gid
    ):
        raise ReleaseContractError("control service identity differs")
    for path in (
        CONTROL_CREDENTIAL_SOURCE_ROOT,
        EMERGENCY_RECEIPT_ROOT,
        OBSERVER_HEALTH_RECEIPT.parent,
    ):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        _ensure_host_directory(path, uid=0, gid=0, mode=0o700)
    return control


def _prepare_observer_identity(
    *,
    service_account: pwd.struct_passwd,
    control_account: pwd.struct_passwd,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> pwd.struct_passwd:
    """Create the non-login identity that can read only disposable projections."""
    try:
        account = pwd.getpwnam(OBSERVER_ACCOUNT_NAME)
    except KeyError:
        runner(
            (
                USERADD_PATH,
                "--system",
                "--user-group",
                "--no-create-home",
                "--home-dir",
                OBSERVER_ACCOUNT_HOME,
                "--shell",
                OBSERVER_ACCOUNT_SHELL,
                OBSERVER_ACCOUNT_NAME,
            ),
            cwd=Path("/"),
        )
        account = pwd.getpwnam(OBSERVER_ACCOUNT_NAME)
    if (
        account.pw_name != OBSERVER_ACCOUNT_NAME
        or account.pw_uid in {0, service_account.pw_uid, control_account.pw_uid}
        or account.pw_gid in {0, service_account.pw_gid, control_account.pw_gid}
        or account.pw_dir != OBSERVER_ACCOUNT_HOME
        or account.pw_shell != OBSERVER_ACCOUNT_SHELL
    ):
        raise ReleaseContractError("observer service identity differs")
    _ensure_host_directory(
        Path(API_STATE_ROOT),
        uid=0,
        gid=account.pw_gid,
        mode=0o750,
    )
    return account


def _require_observer_identity() -> pwd.struct_passwd:
    try:
        account = pwd.getpwnam(OBSERVER_ACCOUNT_NAME)
        service = _require_static_service_identity()
        control = pwd.getpwnam("dharma-sadhana-control")
    except KeyError as exc:
        raise ReleaseContractError(
            "observer service identity is absent; run prepare-host first"
        ) from exc
    if (
        account.pw_name != OBSERVER_ACCOUNT_NAME
        or account.pw_uid in {0, service.pw_uid, control.pw_uid}
        or account.pw_gid in {0, service.pw_gid, control.pw_gid}
        or account.pw_dir != OBSERVER_ACCOUNT_HOME
        or account.pw_shell != OBSERVER_ACCOUNT_SHELL
    ):
        raise ReleaseContractError("observer service identity differs")
    return account


def _prepare_dashboard_identity(
    *,
    service_account: pwd.struct_passwd,
    control_account: pwd.struct_passwd,
    observer_account: pwd.struct_passwd,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> pwd.struct_passwd:
    """Create the dashboard-only identity that owns the private Unix socket."""
    try:
        account = pwd.getpwnam(DASHBOARD_ACCOUNT_NAME)
    except KeyError:
        runner(
            (
                USERADD_PATH,
                "--system",
                "--user-group",
                "--no-create-home",
                "--home-dir",
                DASHBOARD_ACCOUNT_HOME,
                "--shell",
                DASHBOARD_ACCOUNT_SHELL,
                DASHBOARD_ACCOUNT_NAME,
            ),
            cwd=Path("/"),
        )
        account = pwd.getpwnam(DASHBOARD_ACCOUNT_NAME)
    if (
        account.pw_name != DASHBOARD_ACCOUNT_NAME
        or account.pw_uid
        in {
            0,
            service_account.pw_uid,
            control_account.pw_uid,
            observer_account.pw_uid,
        }
        or account.pw_gid
        in {
            0,
            service_account.pw_gid,
            control_account.pw_gid,
            observer_account.pw_gid,
        }
        or account.pw_dir != DASHBOARD_ACCOUNT_HOME
        or account.pw_shell != DASHBOARD_ACCOUNT_SHELL
    ):
        raise ReleaseContractError("dashboard service identity differs")
    return account


def _prepare_oracle_identity(
    *,
    service_account: pwd.struct_passwd,
    control_account: pwd.struct_passwd,
    observer_account: pwd.struct_passwd,
    dashboard_account: pwd.struct_passwd,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> pwd.struct_passwd:
    """Create the evaluator-only identity used after root copies admitted bytes."""
    try:
        account = pwd.getpwnam(ORACLE_ACCOUNT_NAME)
    except KeyError:
        runner(
            (
                USERADD_PATH,
                "--system",
                "--user-group",
                "--no-create-home",
                "--home-dir",
                ORACLE_ACCOUNT_HOME,
                "--shell",
                ORACLE_ACCOUNT_SHELL,
                ORACLE_ACCOUNT_NAME,
            ),
            cwd=Path("/"),
        )
        account = pwd.getpwnam(ORACLE_ACCOUNT_NAME)
    other_uids = {
        0,
        service_account.pw_uid,
        control_account.pw_uid,
        observer_account.pw_uid,
        dashboard_account.pw_uid,
    }
    other_gids = {
        0,
        service_account.pw_gid,
        control_account.pw_gid,
        observer_account.pw_gid,
        dashboard_account.pw_gid,
    }
    if (
        account.pw_name != ORACLE_ACCOUNT_NAME
        or account.pw_uid in other_uids
        or account.pw_gid in other_gids
        or account.pw_dir != ORACLE_ACCOUNT_HOME
        or account.pw_shell != ORACLE_ACCOUNT_SHELL
    ):
        raise ReleaseContractError("oracle evaluator identity differs")
    return account


def _prepare_oracle_custody_roots(
    *,
    service_account: pwd.struct_passwd,
    oracle_account: pwd.struct_passwd,
    root_uid: int = 0,
    root_gid: int = 0,
) -> None:
    """Precreate persistent roots before systemd admits them into a namespace."""
    persistent_parent = ORACLE_INPUT_ROOT.parent
    if any(
        path.parent != persistent_parent
        for path in (ORACLE_CLAIM_ROOT, ORACLE_RUN_ROOT, ORACLE_QUARANTINE_ROOT)
    ):
        raise ReleaseContractError("oracle persistent root topology differs")
    roots = (
        (
            ORACLE_INPUT_ROOT,
            persistent_parent,
            0o755,
            service_account.pw_uid,
            service_account.pw_gid,
            0o700,
        ),
        (
            ORACLE_CLAIM_ROOT,
            persistent_parent,
            0o755,
            root_uid,
            root_gid,
            0o700,
        ),
        (
            ORACLE_RUN_ROOT,
            persistent_parent,
            0o755,
            root_uid,
            oracle_account.pw_gid,
            0o710,
        ),
        (
            ORACLE_QUARANTINE_ROOT,
            persistent_parent,
            0o755,
            root_uid,
            root_gid,
            0o700,
        ),
        (
            ORACLE_RECEIPT_ROOT,
            ORACLE_RECEIPT_ROOT.parent,
            0o700,
            root_uid,
            root_gid,
            0o700,
        ),
    )
    for path, parent, parent_mode, uid, gid, mode in roots:
        if path.parent != parent:
            raise ReleaseContractError("oracle persistent root topology differs")
        _ensure_exact_host_directory(
            path,
            parent_uid=root_uid,
            parent_gid=root_gid,
            parent_mode=parent_mode,
            uid=uid,
            gid=gid,
            mode=mode,
        )


def _require_dashboard_identity() -> pwd.struct_passwd:
    try:
        account = pwd.getpwnam(DASHBOARD_ACCOUNT_NAME)
        service = _require_static_service_identity()
        control = pwd.getpwnam("dharma-sadhana-control")
        observer = pwd.getpwnam(OBSERVER_ACCOUNT_NAME)
    except KeyError as exc:
        raise ReleaseContractError(
            "dashboard service identity is absent; run prepare-host first"
        ) from exc
    if (
        account.pw_name != DASHBOARD_ACCOUNT_NAME
        or account.pw_uid in {0, service.pw_uid, control.pw_uid, observer.pw_uid}
        or account.pw_gid in {0, service.pw_gid, control.pw_gid, observer.pw_gid}
        or account.pw_dir != DASHBOARD_ACCOUNT_HOME
        or account.pw_shell != DASHBOARD_ACCOUNT_SHELL
    ):
        raise ReleaseContractError("dashboard service identity differs")
    return account


def _prepare_build_identity(
    *,
    service_account: pwd.struct_passwd,
    control_account: pwd.struct_passwd | None,
    dashboard_account: pwd.struct_passwd | None,
    observer_account: pwd.struct_passwd | None,
    oracle_account: pwd.struct_passwd | None,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> pwd.struct_passwd:
    try:
        account = pwd.getpwnam(BUILD_ACCOUNT_NAME)
    except KeyError:
        runner(
            (
                USERADD_PATH,
                "--system",
                "--user-group",
                "--no-create-home",
                "--home-dir",
                BUILD_ACCOUNT_HOME,
                "--shell",
                BUILD_ACCOUNT_SHELL,
                BUILD_ACCOUNT_NAME,
            ),
            cwd=Path("/"),
        )
        account = pwd.getpwnam(BUILD_ACCOUNT_NAME)
    forbidden_uids = {0, service_account.pw_uid}
    forbidden_gids = {0, service_account.pw_gid}
    if control_account is not None:
        forbidden_uids.add(control_account.pw_uid)
        forbidden_gids.add(control_account.pw_gid)
    if dashboard_account is not None:
        forbidden_uids.add(dashboard_account.pw_uid)
        forbidden_gids.add(dashboard_account.pw_gid)
    if observer_account is not None:
        forbidden_uids.add(observer_account.pw_uid)
        forbidden_gids.add(observer_account.pw_gid)
    if oracle_account is not None:
        forbidden_uids.add(oracle_account.pw_uid)
        forbidden_gids.add(oracle_account.pw_gid)
    if (
        account.pw_name != BUILD_ACCOUNT_NAME
        or account.pw_uid in forbidden_uids
        or account.pw_gid in forbidden_gids
        or account.pw_dir != BUILD_ACCOUNT_HOME
        or account.pw_shell != BUILD_ACCOUNT_SHELL
    ):
        raise ReleaseContractError("isolated build identity differs")
    return account


def prepare_control_runtime(
    *,
    role: str,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
) -> None:
    """Create the volatile inbox topology with asymmetric writer custody."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("control runtime preparation requires root")
    _require_host_role(role, observed_node=observed_node)
    if role != "writer":
        raise ReleaseContractError("control runtime exists only on the writer")
    service = _require_static_service_identity()
    try:
        control = pwd.getpwnam("dharma-sadhana-control")
    except KeyError as exc:
        raise ReleaseContractError("control service identity is absent") from exc
    if control.pw_uid == 0 or control.pw_gid == 0:
        raise ReleaseContractError("control service identity differs")
    try:
        confirmation_root_identity = ACCOUNT_UI_CONFIRMATION_ROOT.lstat()
    except FileNotFoundError:
        confirmation_root_identity = None
    if confirmation_root_identity is not None:
        active_directory_custody = (expected_root_uid, control.pw_gid, 0o770)
        observed_directory_custody = (
            confirmation_root_identity.st_uid,
            confirmation_root_identity.st_gid,
            stat.S_IMODE(confirmation_root_identity.st_mode),
        )
        if (
            ACCOUNT_UI_CONFIRMATION_ROOT.is_symlink()
            or not stat.S_ISDIR(confirmation_root_identity.st_mode)
            or observed_directory_custody != active_directory_custody
        ):
            # Includes fully sealed and every partial freeze state. Never
            # chown/chmod an irreversible one-shot directory back to control.
            raise ReleaseContractError(
                "sealed account UI candidate custody cannot be reopened"
            )
        names = set(os.listdir(ACCOUNT_UI_CONFIRMATION_ROOT))
        if names not in (set(), {ACCOUNT_UI_CONFIRMATION_CANDIDATE.name}):
            raise ReleaseContractError(
                "partial account UI candidate publication cannot be reopened"
            )
        if names:
            candidate_identity = ACCOUNT_UI_CONFIRMATION_CANDIDATE.lstat()
            if (
                ACCOUNT_UI_CONFIRMATION_CANDIDATE.is_symlink()
                or not stat.S_ISREG(candidate_identity.st_mode)
                or (
                    candidate_identity.st_uid,
                    candidate_identity.st_gid,
                    stat.S_IMODE(candidate_identity.st_mode),
                    candidate_identity.st_nlink,
                )
                != (control.pw_uid, control.pw_gid, 0o600, 1)
            ):
                raise ReleaseContractError(
                    "partial account UI candidate custody cannot be reopened"
                )
    roots = (
        (RUNTIME_ROOT, 0, 0, 0o711),
        (TAILSCALE_STATE_ROOT, 0, 0, 0o700),
        (CONTROL_ROOT, 0, control.pw_gid, 0o750),
        (CONTROL_NORMAL_INBOX, 0, control.pw_gid, 0o770),
        (CONTROL_EMERGENCY_INBOX, 0, control.pw_gid, 0o770),
        (ACCOUNT_UI_CONFIRMATION_ROOT, 0, control.pw_gid, 0o770),
        (PREDISPATCH_ACCOUNT_UI_GATE_ROOT, 0, control.pw_gid, 0o750),
        (EMERGENCY_QUARANTINE_ROOT, 0, 0, 0o700),
        (EMERGENCY_INFLIGHT_ROOT, 0, 0, 0o700),
        (CONTROL_INFLIGHT_ROOT, service.pw_uid, service.pw_gid, 0o700),
        (CONTROL_APPLIED_ROOT, service.pw_uid, service.pw_gid, 0o700),
        (CONTROL_REJECTED_ROOT, service.pw_uid, service.pw_gid, 0o700),
        (CONTROL_ACTIVATION_ROOT, service.pw_uid, control.pw_gid, 0o750),
    )
    for path, uid, gid, mode in roots:
        _ensure_host_directory(path, uid=uid, gid=gid, mode=mode)
    _ensure_emergency_apply_lock(
        expected_root_uid=expected_root_uid,
        expected_root_gid=0,
    )


def _dashboard_socket_is_live(path: Path) -> bool:
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        probe.settimeout(0.25)
        probe.connect(str(path))
        return True
    except FileNotFoundError:
        return False
    except ConnectionRefusedError:
        return False
    except OSError as exc:
        if exc.errno in {errno.ENOENT, errno.ECONNREFUSED}:
            return False
        raise ReleaseContractError(
            "cannot establish dashboard socket liveness"
        ) from exc
    finally:
        probe.close()


def _remove_stale_dashboard_socket(
    *,
    account: pwd.struct_passwd,
) -> None:
    """Remove only a stable, dead socket after proving its UID has no process."""
    if _uid_process_ids(account.pw_uid):
        raise ReleaseContractError(
            "dashboard identity still has a process before socket preparation"
        )
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    if not getattr(os, "O_NOFOLLOW", 0):
        raise ReleaseContractError("platform lacks no-follow dashboard custody")
    descriptor = os.open(DASHBOARD_SOCKET_DIRECTORY, directory_flags)
    try:
        try:
            before = os.stat(
                DASHBOARD_SOCKET_PATH.name,
                dir_fd=descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return
        if (
            not stat.S_ISSOCK(before.st_mode)
            or before.st_uid != account.pw_uid
            or before.st_gid != account.pw_gid
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
        ):
            raise ReleaseContractError("existing dashboard socket custody differs")
        if _dashboard_socket_is_live(DASHBOARD_SOCKET_PATH):
            raise ReleaseContractError("dashboard socket is already live")
        after = os.stat(
            DASHBOARD_SOCKET_PATH.name,
            dir_fd=descriptor,
            follow_symlinks=False,
        )
        identity = (before.st_dev, before.st_ino, before.st_mode, before.st_nlink)
        if identity != (after.st_dev, after.st_ino, after.st_mode, after.st_nlink):
            raise ReleaseContractError("dashboard socket changed during admission")
        os.unlink(DASHBOARD_SOCKET_PATH.name, dir_fd=descriptor)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def prepare_dashboard_runtime(
    *,
    role: str,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
) -> None:
    """Prepare the exclusive dashboard Unix-socket directory without TCP fallback."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("dashboard runtime preparation requires root")
    _require_host_role(role, observed_node=observed_node)
    if role != "writer":
        raise ReleaseContractError("dashboard runtime exists only on the writer")
    account = _require_dashboard_identity()
    _ensure_host_directory(RUNTIME_ROOT, uid=0, gid=0, mode=0o711)
    _ensure_host_directory(
        DASHBOARD_SOCKET_DIRECTORY,
        uid=account.pw_uid,
        gid=account.pw_gid,
        mode=0o700,
    )
    _remove_stale_dashboard_socket(account=account)


def _read_scoped_runtime_source(
    path: Path,
    *,
    parent_uid: int,
    parent_gid: int,
    file_uid: int,
    file_gid: int,
    maximum_bytes: int,
) -> bytes:
    """Stable dirfd read from one exact private service-owned source root."""
    if not path.is_absolute() or not 0 < maximum_bytes <= 32 * 1024 * 1024:
        raise ReleaseContractError("projection source contract differs")
    parent = path.parent
    parent_identity = parent.lstat()
    if (
        parent.is_symlink()
        or not stat.S_ISDIR(parent_identity.st_mode)
        or parent_identity.st_uid != parent_uid
        or parent_identity.st_gid != parent_gid
        or stat.S_IMODE(parent_identity.st_mode) != 0o700
    ):
        raise ReleaseContractError("projection source directory custody differs")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    if not getattr(os, "O_NOFOLLOW", 0):
        raise ReleaseContractError("platform lacks no-follow projection admission")
    parent_descriptor = os.open(parent, directory_flags)
    descriptor = -1
    try:
        entry = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
        if (
            not stat.S_ISREG(entry.st_mode)
            or entry.st_uid != file_uid
            or entry.st_gid != file_gid
            or stat.S_IMODE(entry.st_mode) != 0o600
            or entry.st_nlink != 1
            or not 0 < entry.st_size <= maximum_bytes
        ):
            raise ReleaseContractError("projection source file custody differs")
        descriptor = os.open(path.name, file_flags, dir_fd=parent_descriptor)
        before = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (entry.st_dev, entry.st_ino):
            raise ReleaseContractError("projection source changed during open")
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
        if (
            len(raw) > maximum_bytes
            or len(raw) != after.st_size
            or (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
            )
            != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
            )
        ):
            raise ReleaseContractError("projection source changed during read")
        return raw
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_descriptor)


def _validate_snapshot_readiness_bytes(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseContractError("snapshot readiness projection is invalid") from exc
    if not isinstance(payload, dict) or raw != _canonical_bytes(payload) + b"\n":
        raise ReleaseContractError("snapshot readiness projection is not canonical")
    digest = payload.get("receipt_digest")
    unsigned = dict(payload)
    unsigned.pop("receipt_digest", None)
    if (
        payload.get("schema_version")
        != "dharma.sadhana.snapshot_capacity_readiness.v1"
        or payload.get("mission_id") != MISSION_ID
        or not isinstance(digest, str)
        or digest != hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()
        or payload.get("status") not in {"ready", "snapshot_blocked"}
        or payload.get("standby_capacity_proven") is not False
    ):
        raise ReleaseContractError("snapshot readiness projection binding differs")
    return payload


def _remove_disposable_observer_file(
    path: Path,
    *,
    observer: pwd.struct_passwd,
) -> None:
    if not path.exists() and not path.is_symlink():
        return
    identity = path.lstat()
    if (
        path.is_symlink()
        or not stat.S_ISREG(identity.st_mode)
        or identity.st_uid != observer.pw_uid
        or identity.st_gid != observer.pw_gid
        or stat.S_IMODE(identity.st_mode) != 0o600
        or identity.st_nlink != 1
    ):
        raise ReleaseContractError("observer disposable file custody differs")
    path.unlink()
    directory_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


def sync_observer_projection(
    *,
    role: str,
    projection_source: Path = WRITER_PROJECTION_PATH,
    projection_destination: Path = OBSERVER_PROJECTION_PATH,
    readiness_source: Path = SNAPSHOT_READINESS_SOURCE_PATH,
    readiness_destination: Path = OBSERVER_SNAPSHOT_READINESS_PATH,
    api_env_path: Path = Path("/etc/dharma-sadhana/api.env"),
    now: datetime | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
    projection_validator: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Root-project writer-owned derived bytes into the observer-only read model."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("observer projection sync requires root")
    _require_host_role(role, observed_node=observed_node)
    if role != "writer":
        raise ReleaseContractError("observer projection exists only on the writer")
    if (
        projection_source != WRITER_PROJECTION_PATH
        or projection_destination != OBSERVER_PROJECTION_PATH
        or readiness_source != SNAPSHOT_READINESS_SOURCE_PATH
        or readiness_destination != OBSERVER_SNAPSHOT_READINESS_PATH
    ):
        raise ReleaseContractError("observer projection paths differ")
    guard_campaign_clock(role=role, now=now, observed_node=observed_node)
    service = _require_static_service_identity()
    observer = _require_observer_identity()
    destination_root = Path(API_STATE_ROOT).lstat()
    if (
        Path(API_STATE_ROOT).is_symlink()
        or not stat.S_ISDIR(destination_root.st_mode)
        or destination_root.st_uid != expected_root_uid
        or destination_root.st_gid != observer.pw_gid
        or stat.S_IMODE(destination_root.st_mode) != 0o750
    ):
        raise ReleaseContractError("observer projection root custody differs")
    raw = _read_scoped_runtime_source(
        projection_source,
        parent_uid=service.pw_uid,
        parent_gid=service.pw_gid,
        file_uid=service.pw_uid,
        file_gid=service.pw_gid,
        maximum_bytes=32 * 1024 * 1024,
    )
    api = _private_env_bindings(api_env_path)
    required_api = {
        "DHARMA_MISSION_SNAPSHOT_CONFIG_DIGEST",
        "DHARMA_MISSION_SNAPSHOT_MAX_AGE_SECONDS",
        "DHARMA_MISSION_SNAPSHOT_MIN_GENERATION",
    }
    if not required_api <= set(api):
        raise ReleaseContractError("api.env lacks projection validation bindings")
    validator = projection_validator
    if validator is None:
        try:
            from api.mission_snapshot_validation import validate_campaign_projection
        except ImportError as exc:
            raise ReleaseContractError(
                "projection validator is unavailable"
            ) from exc
        validator = validate_campaign_projection
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ReleaseContractError("projection sync clock must be timezone-aware")
    try:
        minimum_generation = int(api["DHARMA_MISSION_SNAPSHOT_MIN_GENERATION"])
        maximum_age = float(api["DHARMA_MISSION_SNAPSHOT_MAX_AGE_SECONDS"])
        validator(
            raw,
            mission_id=MISSION_ID,
            config_digest=api["DHARMA_MISSION_SNAPSHOT_CONFIG_DIGEST"],
            minimum_generation=minimum_generation,
            max_age_seconds=maximum_age,
            now=observed,
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        raise ReleaseContractError("writer projection validation failed") from exc
    _atomic_private_bytes(
        projection_destination,
        raw,
        uid=observer.pw_uid,
        gid=observer.pw_gid,
        replace_existing=projection_destination.exists(),
    )
    readiness_copied = False
    if readiness_source.exists() and not readiness_source.is_symlink():
        readiness_raw = _read_scoped_runtime_source(
            readiness_source,
            parent_uid=service.pw_uid,
            parent_gid=service.pw_gid,
            file_uid=service.pw_uid,
            file_gid=service.pw_gid,
            maximum_bytes=64 * 1024,
        )
        _validate_snapshot_readiness_bytes(readiness_raw)
        _atomic_private_bytes(
            readiness_destination,
            readiness_raw,
            uid=observer.pw_uid,
            gid=observer.pw_gid,
            replace_existing=readiness_destination.exists(),
        )
        readiness_copied = True
    else:
        _remove_disposable_observer_file(
            readiness_destination,
            observer=observer,
        )
    return {
        "status": "observer_projection_synced",
        "projection_sha256": hashlib.sha256(raw).hexdigest(),
        "readiness_copied": readiness_copied,
        "canonical_state_visible_to_observer": False,
    }


def _require_static_service_identity() -> pwd.struct_passwd:
    try:
        account = pwd.getpwnam("dharma-sadhana")
    except KeyError as exc:
        raise ReleaseContractError(
            "static service identity is absent; run prepare-host first"
        ) from exc
    if (
        account.pw_name != "dharma-sadhana"
        or account.pw_uid == 0
        or account.pw_gid == 0
        or account.pw_dir != "/var/lib/dharma-sadhana"
        or account.pw_shell != "/bin/sh"
    ):
        raise ReleaseContractError("service identity differs from the static account")
    return account


def _require_build_identity(
    *,
    service_account: pwd.struct_passwd,
) -> pwd.struct_passwd:
    try:
        account = pwd.getpwnam(BUILD_ACCOUNT_NAME)
    except KeyError as exc:
        raise ReleaseContractError(
            "isolated build identity is absent; run prepare-host first"
        ) from exc
    forbidden_uids = {0, service_account.pw_uid}
    forbidden_gids = {0, service_account.pw_gid}
    for name in (
        "dharma-sadhana-control",
        OBSERVER_ACCOUNT_NAME,
        DASHBOARD_ACCOUNT_NAME,
        ORACLE_ACCOUNT_NAME,
    ):
        try:
            other = pwd.getpwnam(name)
        except KeyError:
            continue
        forbidden_uids.add(other.pw_uid)
        forbidden_gids.add(other.pw_gid)
    if (
        account.pw_name != BUILD_ACCOUNT_NAME
        or account.pw_uid in forbidden_uids
        or account.pw_gid in forbidden_gids
        or account.pw_dir != BUILD_ACCOUNT_HOME
        or account.pw_shell != BUILD_ACCOUNT_SHELL
    ):
        raise ReleaseContractError("isolated build identity differs")
    return account


def prepare_host(
    role: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    observed_node: str | None = None,
) -> pwd.struct_passwd:
    """Create only the static account and roots needed to admit external inputs."""
    if os.geteuid() != 0:
        raise ReleaseContractError("host preparation requires root")
    _require_host_role(role, observed_node=observed_node)
    marker_exists = _validate_existing_writer_marker()
    if role == "standby" and marker_exists:
        raise ReleaseContractError("standby host already carries writer marker")
    account = _prepare_service_identity_and_paths(
        role=role,
        observed_node=_require_host_role(role, observed_node=observed_node),
        runner=runner,
    )
    if role == "writer":
        control = _prepare_control_identity_and_paths(
            service_account=account,
            runner=runner,
        )
        observer = _prepare_observer_identity(
            service_account=account,
            control_account=control,
            runner=runner,
        )
        dashboard = _prepare_dashboard_identity(
            service_account=account,
            control_account=control,
            observer_account=observer,
            runner=runner,
        )
        oracle = _prepare_oracle_identity(
            service_account=account,
            control_account=control,
            observer_account=observer,
            dashboard_account=dashboard,
            runner=runner,
        )
        _prepare_oracle_custody_roots(
            service_account=account,
            oracle_account=oracle,
        )
    else:
        control = None
        dashboard = None
        observer = None
        oracle = None
    _prepare_build_identity(
        service_account=account,
        control_account=control,
        dashboard_account=dashboard,
        observer_account=observer,
        oracle_account=oracle,
        runner=runner,
    )
    return account


def _private_env_bindings(
    path: Path,
    *,
    exact_single_key: str | None = None,
) -> dict[str, str]:
    """Read a root-custodied env file without ever returning it to a logger."""
    _require_secure_parent_chain(path)
    try:
        identity = path.lstat()
    except OSError as exc:
        raise ReleaseContractError(
            f"scoped env file is unavailable: {path.name}"
        ) from exc
    if (
        not stat.S_ISREG(identity.st_mode)
        or path.is_symlink()
        or identity.st_uid != os.geteuid()
        or stat.S_IMODE(identity.st_mode) != 0o600
        or identity.st_nlink != 1
        or not 0 < identity.st_size <= 64 * 1024
    ):
        raise ReleaseContractError(
            f"scoped env file lacks root/0600 custody: {path.name}"
        )
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    if not getattr(os, "O_NOFOLLOW", 0):
        raise ReleaseContractError("platform lacks no-follow env-file admission")
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (identity.st_dev, identity.st_ino):
            raise ReleaseContractError("scoped env file changed during open")
        raw = os.read(descriptor, 64 * 1024 + 1)
    finally:
        os.close(descriptor)
    if len(raw) > 64 * 1024 or b"\x00" in raw:
        raise ReleaseContractError(f"scoped env file is invalid: {path.name}")
    if exact_single_key is not None:
        prefix = exact_single_key.encode("ascii") + b"="
        if (
            not raw.startswith(prefix)
            or not raw.endswith(b"\n")
            or raw.count(b"\n") != 1
            or b"\r" in raw
            or not raw[len(prefix) : -1]
            or raw[len(prefix) : -1].strip() != raw[len(prefix) : -1]
        ):
            raise ReleaseContractError(
                f"{path.name} must contain exactly one nonempty {exact_single_key} assignment"
            )
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise ReleaseContractError(
            f"scoped env file is not UTF-8: {path.name}"
        ) from exc
    bindings: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ReleaseContractError(
                f"malformed env binding in {path.name} at line {line_number}"
            )
        key, value = line.split("=", 1)
        if not _ENV_KEY_RE.fullmatch(key) or key in bindings:
            raise ReleaseContractError(
                f"invalid or duplicate env key in {path.name} at line {line_number}"
            )
        bindings[key] = value
    return bindings


def _require_env_value(
    bindings: Mapping[str, str], key: str, expected: str, file_name: str
) -> None:
    if bindings.get(key) != expected:
        raise ReleaseContractError(
            f"{file_name} does not bind required key {key} to its admitted value"
        )


def _require_bounded_env_integer(
    bindings: Mapping[str, str],
    key: str,
    minimum: int,
    maximum: int,
    file_name: str,
) -> int:
    raw = bindings.get(key, "")
    if not raw.isascii() or not raw.isdecimal():
        raise ReleaseContractError(f"{file_name} key {key} must be a decimal integer")
    value = int(raw)
    if str(value) != raw or not minimum <= value <= maximum:
        raise ReleaseContractError(
            f"{file_name} key {key} is outside its admitted bound"
        )
    return value


def _require_env_path_within(
    bindings: Mapping[str, str], key: str, root: Path, file_name: str
) -> None:
    value = bindings.get(key, "")
    candidate = Path(value)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ReleaseContractError(
            f"{file_name} key {key} must remain beneath its admitted root"
        ) from exc
    if not candidate.is_absolute() or ".." in candidate.parts or candidate == root:
        raise ReleaseContractError(
            f"{file_name} key {key} is not an admitted absolute child path"
        )


def _ensure_private_env_files(
    env_files: Sequence[str] = ENV_FILES,
) -> dict[str, dict[str, str]]:
    if len(env_files) != 6:
        raise ReleaseContractError("scoped env-file set must contain six files")
    parsed: dict[str, dict[str, str]] = {}
    for raw in env_files:
        path = Path(raw)
        parsed[path.name] = _private_env_bindings(path)

    supervisor = parsed[Path(env_files[0]).name]
    api = parsed[Path(env_files[1]).name]
    dashboard = parsed[Path(env_files[2]).name]
    control = parsed[Path(env_files[3]).name]
    replication = parsed[Path(env_files[4]).name]
    verifier_path = Path(env_files[5])
    verifier = _private_env_bindings(
        verifier_path,
        exact_single_key="OLLAMA_API_KEY",
    )
    parsed[verifier_path.name] = verifier
    _require_env_value(api, "SADHANA_API_PORT", "18420", "api.env")
    _require_env_value(api, "DHARMA_STATE_DIR", API_STATE_ROOT, "api.env")
    _require_env_value(
        api,
        "DHARMA_MISSION_SNAPSHOT_MISSION_ID",
        MISSION_ID,
        "api.env",
    )
    for key in (
        "DHARMA_MISSION_SNAPSHOT_PATH",
        "DHARMA_MISSION_SNAPSHOT_CONFIG_DIGEST",
        "DHARMA_MISSION_SNAPSHOT_MIN_GENERATION",
        "DHARMA_MISSION_SNAPSHOT_MAX_AGE_SECONDS",
    ):
        if not api.get(key):
            raise ReleaseContractError(f"api.env lacks required key {key}")
    _require_env_value(
        dashboard,
        "DHARMA_API_PROXY_URL",
        DASHBOARD_PROXY_URL,
        "dashboard.env",
    )
    _require_env_value(
        dashboard,
        "DHARMA_API_INTERNAL_URL",
        DASHBOARD_PROXY_URL,
        "dashboard.env",
    )
    if any(key.startswith("NEXT_PUBLIC_") for key in dashboard):
        raise ReleaseContractError("dashboard.env cannot expose a NEXT_PUBLIC binding")
    sensitive_dashboard_keys = {
        key
        for key in dashboard
        if any(
            fragment in key.upper()
            for fragment in (
                "BEARER",
                "HMAC",
                "LOGIN",
                "PASSWORD",
                "SECRET",
                "TOKEN",
            )
        )
    }
    if sensitive_dashboard_keys:
        raise ReleaseContractError(
            "dashboard.env cannot carry operator-control credentials"
        )
    if set(control) != {"SADHANA_CONTROL_EXPECTED_ORIGIN"}:
        raise ReleaseContractError(
            "control.env must contain only SADHANA_CONTROL_EXPECTED_ORIGIN"
        )
    expected_origin = urllib.parse.urlsplit(control["SADHANA_CONTROL_EXPECTED_ORIGIN"])
    if (
        expected_origin.scheme != "https"
        or not expected_origin.hostname
        or expected_origin.username is not None
        or expected_origin.password is not None
        or expected_origin.port is not None
        or expected_origin.path
        or expected_origin.query
        or expected_origin.fragment
        or expected_origin.geturl() != control["SADHANA_CONTROL_EXPECTED_ORIGIN"]
    ):
        raise ReleaseContractError(
            "control.env expected Origin must be one exact HTTPS origin"
        )
    _require_env_value(
        dashboard,
        "SADHANA_CONTROL_EXPECTED_ORIGIN",
        control["SADHANA_CONTROL_EXPECTED_ORIGIN"],
        "dashboard.env",
    )
    supervisor_fields = {
        "SADHANA_WRITER_LOCK_PATH",
        "SADHANA_PROJECTION_PATH",
        "SADHANA_OPERATOR_ID",
        "SADHANA_MAX_DISPATCH_PER_CYCLE",
        "SADHANA_CYCLE_INTERVAL_SECONDS",
        "SADHANA_FRESHNESS_SECONDS",
        "SADHANA_LEASE_ROOT",
        "SADHANA_AGENT_ROSTER_PATH",
        "SADHANA_AGENT_ROSTER_SHA256",
        "SADHANA_OBJECTIVE_SHA256",
    }
    if {
        "SADHANA_CANARY_TASK_ID",
        "SADHANA_HELD_OUT_ORACLE_DIGEST",
    } & set(supervisor):
        raise ReleaseContractError(
            "supervisor.env cannot claim post-preparation runtime outputs"
        )
    if set(supervisor) != supervisor_fields:
        raise ReleaseContractError("supervisor.env fields differ")
    for key in supervisor_fields:
        if not supervisor.get(key):
            raise ReleaseContractError(f"supervisor.env lacks required key {key}")
    for key in ("SADHANA_OPERATOR_ID",):
        if not _STABLE_ID_RE.fullmatch(supervisor[key]):
            raise ReleaseContractError(f"supervisor.env key {key} is not a stable ID")
    _require_bounded_env_integer(
        supervisor,
        "SADHANA_MAX_DISPATCH_PER_CYCLE",
        1,
        64,
        "supervisor.env",
    )
    cycle_interval = _require_bounded_env_integer(
        supervisor,
        "SADHANA_CYCLE_INTERVAL_SECONDS",
        1,
        3600,
        "supervisor.env",
    )
    freshness = _require_bounded_env_integer(
        supervisor,
        "SADHANA_FRESHNESS_SECONDS",
        1,
        86_400,
        "supervisor.env",
    )
    if cycle_interval > freshness:
        raise ReleaseContractError(
            "supervisor cycle cannot exceed its evidence freshness window"
        )
    _require_bounded_env_integer(
        api,
        "DHARMA_MISSION_SNAPSHOT_MIN_GENERATION",
        1,
        2**63 - 1,
        "api.env",
    )
    _require_bounded_env_integer(
        api,
        "DHARMA_MISSION_SNAPSHOT_MAX_AGE_SECONDS",
        1,
        3600,
        "api.env",
    )
    if api["DHARMA_MISSION_SNAPSHOT_PATH"] != str(OBSERVER_PROJECTION_PATH):
        raise ReleaseContractError(
            "API projection path differs from its disposable observer copy"
        )
    _require_env_path_within(
        supervisor,
        "SADHANA_WRITER_LOCK_PATH",
        Path(STATE_ROOT),
        "supervisor.env",
    )
    _require_env_path_within(
        supervisor,
        "SADHANA_PROJECTION_PATH",
        PROJECTION_SOURCE_ROOT,
        "supervisor.env",
    )
    _require_env_value(
        supervisor,
        "SADHANA_PROJECTION_PATH",
        str(WRITER_PROJECTION_PATH),
        "supervisor.env",
    )
    _require_env_path_within(
        supervisor,
        "SADHANA_AGENT_ROSTER_PATH",
        Path("/etc/dharma-sadhana"),
        "supervisor.env",
    )
    for key in (
        "SADHANA_AGENT_ROSTER_SHA256",
        "SADHANA_OBJECTIVE_SHA256",
    ):
        _require_hash(supervisor[key], key)
    if not re.fullmatch(
        r"sha256:[0-9a-f]{64}",
        api["DHARMA_MISSION_SNAPSHOT_CONFIG_DIGEST"],
    ):
        raise ReleaseContractError(
            "DHARMA_MISSION_SNAPSHOT_CONFIG_DIGEST must be a canonical digest"
        )
    _require_env_value(
        supervisor,
        "SADHANA_LEASE_ROOT",
        "/var/lib/dharma-sadhana/leases",
        "supervisor.env",
    )
    _require_env_value(
        replication,
        "SADHANA_REPLICATION_SSH_KEY",
        "/etc/dharma-sadhana/replication_ed25519",
        "replication.env",
    )
    if set(verifier) != {"OLLAMA_API_KEY"} or not verifier["OLLAMA_API_KEY"].strip():
        raise ReleaseContractError(
            "verifier.env must contain only a nonempty OLLAMA_API_KEY"
        )
    return parsed


def install_verifier_env_from_stdin(
    raw: bytes,
    *,
    destination: Path = VERIFIER_ENV_PATH,
    observed_node: str | None = None,
    expected_uid: int = 0,
    expected_gid: int = 0,
) -> Path:
    """Atomically install the sole verifier secret received over SSH stdin."""
    _require_host_role("writer", observed_node=observed_node)
    if os.geteuid() != expected_uid:
        raise ReleaseContractError("verifier secret installation requires root")
    if destination != VERIFIER_ENV_PATH or not destination.is_absolute():
        raise ReleaseContractError("verifier secret destination differs")
    prefix = b"OLLAMA_API_KEY="
    if (
        not raw.startswith(prefix)
        or not raw.endswith(b"\n")
        or raw.count(b"\n") != 1
        or b"\x00" in raw
        or b"\r" in raw
        or not raw[len(prefix) : -1]
        or raw[len(prefix) : -1].strip() != raw[len(prefix) : -1]
        or len(raw) > 64 * 1024
    ):
        raise ReleaseContractError(
            "verifier secret input must be one nonempty OLLAMA_API_KEY assignment"
        )
    _require_secure_parent_chain(destination)
    parent = destination.parent
    parent_identity = parent.lstat()
    if (
        not stat.S_ISDIR(parent_identity.st_mode)
        or parent.is_symlink()
        or parent_identity.st_uid != expected_uid
        or stat.S_IMODE(parent_identity.st_mode) & 0o022
    ):
        raise ReleaseContractError("verifier secret directory lacks root custody")
    if destination.exists() or destination.is_symlink():
        identity = destination.lstat()
        if (
            not stat.S_ISREG(identity.st_mode)
            or destination.is_symlink()
            or identity.st_uid != expected_uid
            or identity.st_gid != expected_gid
            or stat.S_IMODE(identity.st_mode) != 0o600
            or identity.st_nlink != 1
        ):
            raise ReleaseContractError("existing verifier env lacks exact custody")
    descriptor, temporary_raw = tempfile.mkstemp(
        prefix=".verifier.env.",
        dir=parent,
    )
    temporary = Path(temporary_raw)
    try:
        os.fchmod(descriptor, 0o600)
        os.fchown(descriptor, expected_uid, expected_gid)
        _write_all(descriptor, raw)
        os.fsync(descriptor)
        identity = os.fstat(descriptor)
        if (
            not stat.S_ISREG(identity.st_mode)
            or identity.st_uid != expected_uid
            or identity.st_gid != expected_gid
            or stat.S_IMODE(identity.st_mode) != 0o600
            or identity.st_nlink != 1
        ):
            raise ReleaseContractError("temporary verifier env lacks exact custody")
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, destination)
        directory_descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
    admitted = _private_env_bindings(
        destination,
        exact_single_key="OLLAMA_API_KEY",
    )
    if set(admitted) != {"OLLAMA_API_KEY"} or not admitted["OLLAMA_API_KEY"]:
        raise ReleaseContractError("installed verifier env is not admitted")
    return destination


def install_control_credential_from_stdin(
    raw: bytes,
    *,
    credential: str,
    observed_node: str | None = None,
    expected_uid: int = 0,
    expected_gid: int = 0,
) -> Path:
    """Install one named control credential without argv, logs, or replacement."""
    _require_host_role("writer", observed_node=observed_node)
    if os.geteuid() != expected_uid:
        raise ReleaseContractError("control credential installation requires root")
    destination = CONTROL_CREDENTIAL_DESTINATIONS.get(credential)
    if destination is None:
        raise ReleaseContractError("control credential name differs")
    if b"\r" in raw or b"\n" in raw:
        raise ReleaseContractError("control credential stdin framing differs")
    value = raw
    if credential == "tailscale_operator_login":
        try:
            from dharma_swarm.mission_control_operator_control import (
                ControlSchemaError,
                validate_operator_login,
            )
        except ImportError as exc:
            raise ReleaseContractError(
                "shared operator login validator is unavailable"
            ) from exc
        try:
            login_text = value.decode("ascii")
            admitted_login = validate_operator_login(login_text)
        except (UnicodeError, ControlSchemaError) as exc:
            raise ReleaseContractError(
                "operator login credential bytes differ"
            ) from exc
        if admitted_login != login_text:
            raise ReleaseContractError("shared operator login validator changed bytes")
        minimum_bytes = 1
        maximum_bytes = 254
    else:
        maximum_bytes = 512 if credential == "operator_bearer" else 4096
        if not 32 <= len(value) <= maximum_bytes or (
            credential == "operator_bearer"
            and any(byte < 0x21 or byte > 0x7E for byte in value)
        ):
            raise ReleaseContractError("control secret credential bytes differ")
        minimum_bytes = 32
    parent = destination.parent
    _require_secure_parent_chain(destination)
    parent_identity = parent.lstat()
    if (
        parent.is_symlink()
        or not stat.S_ISDIR(parent_identity.st_mode)
        or parent_identity.st_uid != expected_uid
        or parent_identity.st_gid != expected_gid
        or stat.S_IMODE(parent_identity.st_mode) != 0o700
    ):
        raise ReleaseContractError("control credential root custody differs")
    if destination.exists() or destination.is_symlink():
        existing = _read_control_credential(
            destination,
            expected_root_uid=expected_uid,
            minimum_bytes=minimum_bytes,
            maximum_bytes=maximum_bytes,
            textual=credential != "control_hmac_key",
        )
        if not hmac.compare_digest(existing, value):
            raise ReleaseContractError("existing control credential conflicts")
        return destination
    _atomic_private_bytes(
        destination,
        value,
        uid=expected_uid,
        gid=expected_gid,
    )
    installed = _read_control_credential(
        destination,
        expected_root_uid=expected_uid,
        minimum_bytes=minimum_bytes,
        maximum_bytes=maximum_bytes,
        textual=credential != "control_hmac_key",
    )
    if not hmac.compare_digest(installed, value):
        raise ReleaseContractError("installed control credential differs")
    return destination


def _scope_runtime_file(
    path: Path,
    *,
    uid: int,
    gid: int,
    mode: int = 0o640,
    max_bytes: int = 1024 * 1024,
) -> None:
    _validate_runtime_file_scope(
        path,
        uid=uid,
        gid=gid,
        mode=mode,
        max_bytes=max_bytes,
    )
    before = path.lstat()
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ReleaseContractError("platform lacks no-follow runtime custody")
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        opened = os.fstat(descriptor)
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_uid,
            before.st_gid,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
        )
        opened_identity = (
            opened.st_dev,
            opened.st_ino,
            opened.st_mode,
            opened.st_uid,
            opened.st_gid,
            opened.st_nlink,
            opened.st_size,
            opened.st_mtime_ns,
        )
        if before_identity != opened_identity:
            raise ReleaseContractError(
                f"scoped runtime file changed before custody: {path.name}"
            )
        os.fchown(descriptor, uid, gid)
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
        narrowed = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    final = path.lstat()
    if (
        path.is_symlink()
        or not stat.S_ISREG(final.st_mode)
        or final.st_dev != narrowed.st_dev
        or final.st_ino != narrowed.st_ino
        or final.st_uid != uid
        or final.st_gid != gid
        or stat.S_IMODE(final.st_mode) != mode
        or final.st_nlink != 1
    ):
        raise ReleaseContractError(
            f"scoped runtime file custody could not be narrowed: {path.name}"
        )


def _validate_runtime_file_scope(
    path: Path,
    *,
    uid: int,
    gid: int,
    mode: int = 0o640,
    max_bytes: int = 1024 * 1024,
) -> None:
    _require_secure_parent_chain(path)
    try:
        identity = path.lstat()
    except OSError as exc:
        raise ReleaseContractError(
            f"scoped runtime file is unavailable: {path.name}"
        ) from exc
    observed_mode = stat.S_IMODE(identity.st_mode)
    root_input = identity.st_uid == 0 and observed_mode == 0o600
    already_scoped = (
        identity.st_uid == uid and identity.st_gid == gid and observed_mode == mode
    )
    if (
        not stat.S_ISREG(identity.st_mode)
        or path.is_symlink()
        or not (root_input or already_scoped)
        or identity.st_nlink != 1
        or not 0 < identity.st_size <= max_bytes
    ):
        raise ReleaseContractError(
            f"scoped runtime file lacks admitted custody: {path.name}"
        )


def _ensure_scoped_runtime_files(
    parsed_env: Mapping[str, Mapping[str, str]],
    *,
    account: pwd.struct_passwd,
) -> None:
    supervisor = parsed_env["supervisor.env"]
    replication = parsed_env["replication.env"]
    roster = Path(supervisor["SADHANA_AGENT_ROSTER_PATH"])
    key = Path(replication["SADHANA_REPLICATION_SSH_KEY"])
    known_hosts = Path("/etc/dharma-sadhana/known_hosts")
    roster_sha256 = supervisor["SADHANA_AGENT_ROSTER_SHA256"]
    # Validate root-custodied source bytes before changing ownership.  The
    # same-euid loader then requires service-owned 0600; its pinned hash means
    # later service mutation can create only detectable self-DoS, not authority.
    if sha256_file(roster, max_bytes=1024 * 1024) != roster_sha256:
        raise ReleaseContractError("agent roster bytes differ from supervisor binding")
    # Admit the complete set before the first chown/chmod. A missing or
    # mismatched SSH input must not leave only the roster custody transitioned.
    _validate_runtime_file_scope(
        roster,
        uid=account.pw_uid,
        gid=account.pw_gid,
        mode=0o600,
    )
    for path in (key, known_hosts):
        _validate_runtime_file_scope(path, uid=0, gid=account.pw_gid)
    if (
        sha256_file(known_hosts, max_bytes=1024 * 1024)
        != DEPLOYMENT_KNOWN_HOSTS_SHA256
    ):
        raise ReleaseContractError("runtime known_hosts differs from pinned deployment")
    _scope_runtime_file(
        roster,
        uid=account.pw_uid,
        gid=account.pw_gid,
        mode=0o600,
    )
    for path in (key, known_hosts):
        _scope_runtime_file(path, uid=0, gid=account.pw_gid)
    if sha256_file(roster, max_bytes=1024 * 1024) != roster_sha256:
        raise ReleaseContractError("agent roster bytes differ from supervisor binding")
    if (
        sha256_file(known_hosts, max_bytes=1024 * 1024)
        != DEPLOYMENT_KNOWN_HOSTS_SHA256
    ):
        raise ReleaseContractError("runtime known_hosts changed during custody transition")


def finalize_disabled_runtime_staging(
    *,
    role: str,
    release_sha: str,
    receipt_path: Path = RUNTIME_STAGING_RECEIPT,
    env_files: Sequence[str] = ENV_FILES,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    now: datetime | None = None,
    observed_node: str | None = None,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Validate and narrow runtime custody while every dispatcher is disabled."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("runtime staging finalization requires root")
    _require_host_role(role, observed_node=observed_node)
    if role != "writer" or not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("runtime staging release binding differs")
    guard_campaign_clock(role=role, now=now, observed_node=observed_node)
    if _systemd_main_pid(SUPERVISOR_UNIT, runner=runner) != 0:
        raise ReleaseContractError("runtime staging requires disabled dispatch")
    if DISPATCH_ENABLE_MARKER.exists() or DISPATCH_ENABLE_MARKER.is_symlink():
        raise ReleaseContractError("runtime staging cannot replace dispatch authority")
    account = _require_static_service_identity()
    # This is the only activation-path caller of both custody gates. The first
    # validates all six environment files; the second pre-admits its complete
    # file set before the first ownership transition.
    parsed = _ensure_private_env_files(env_files)
    binding = verify_runtime_binding_activation(account=account, now=now)
    credentials = (
        _read_control_credential(
            CONTROL_BEARER_SOURCE,
            expected_root_uid=expected_root_uid,
            minimum_bytes=32,
            maximum_bytes=512,
        ),
        _read_control_credential(
            CONTROL_HMAC_SOURCE,
            expected_root_uid=expected_root_uid,
            minimum_bytes=32,
            maximum_bytes=4096,
            textual=False,
        ),
        _read_control_credential(
            CONTROL_LOGIN_SOURCE,
            expected_root_uid=expected_root_uid,
            minimum_bytes=1,
            maximum_bytes=254,
        ),
    )
    if any(not item for item in credentials):
        raise ReleaseContractError("runtime staging credential set differs")
    _ensure_scoped_runtime_files(parsed, account=account)
    # Re-read every environment after custody transition. Secret values remain
    # in memory only and never enter this receipt.
    _ensure_private_env_files(env_files)
    payload: dict[str, Any] = {
        "schema_version": RUNTIME_STAGING_SCHEMA_VERSION,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "dispatch_process_count": 0,
        "env_file_names": [Path(path).name for path in env_files],
        "scoped_runtime_files_verified": True,
        "runtime_binding_receipt_digest": binding["receipt_digest"],
        "control_credentials_present": True,
        "verifier_secret_present": True,
        "verdict": "PASS",
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_self_digest(payload, "receipt_digest")
    if set(payload) != _RUNTIME_STAGING_RECEIPT_FIELDS:
        raise ReleaseContractError("runtime staging receipt fields differ")
    return _publish_or_replay_private_receipt(
        receipt_path,
        payload,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )


def _read_standby_public_key(*, expected_root_uid: int = 0) -> str:
    path = STANDBY_AUTHORIZED_KEY_INPUT
    _require_secure_parent_chain(path)
    try:
        identity = path.lstat()
    except OSError as exc:
        raise ReleaseContractError(
            "standby replication public key is unavailable"
        ) from exc
    if (
        not stat.S_ISREG(identity.st_mode)
        or path.is_symlink()
        or identity.st_uid != expected_root_uid
        or stat.S_IMODE(identity.st_mode) != 0o600
        or identity.st_nlink != 1
        or not 0 < identity.st_size <= 4096
    ):
        raise ReleaseContractError("standby replication public key lacks custody")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ReleaseContractError("platform lacks no-follow standby key admission")
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (identity.st_dev, identity.st_ino):
            raise ReleaseContractError("standby replication public key changed")
        raw = os.read(descriptor, 4097)
    finally:
        os.close(descriptor)
    try:
        line = raw.decode("ascii").rstrip("\n")
    except UnicodeError as exc:
        raise ReleaseContractError(
            "standby replication public key is not ASCII"
        ) from exc
    if raw != (line + "\n").encode("ascii"):
        raise ReleaseContractError(
            "standby replication public key is not exact ed25519"
        )
    return _validate_ed25519_public_key(line)


def _validate_ed25519_public_key(public_key: str) -> str:
    parts = public_key.split(" ", 2)
    if (
        len(parts) not in {2, 3}
        or parts[0] != "ssh-ed25519"
        or (len(parts) == 3 and not _ED25519_COMMENT_RE.fullmatch(parts[2]))
    ):
        raise ReleaseContractError(
            "standby replication public key is not exact ed25519"
        )
    try:
        decoded = base64.b64decode(parts[1], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ReleaseContractError(
            "standby replication public key is not exact ed25519"
        ) from exc
    algorithm = b"ssh-ed25519"
    expected_prefix = len(algorithm).to_bytes(4, "big") + algorithm
    if (
        not decoded.startswith(expected_prefix)
        or decoded[len(expected_prefix) : len(expected_prefix) + 4]
        != (32).to_bytes(4, "big")
        or len(decoded) != len(expected_prefix) + 4 + 32
    ):
        raise ReleaseContractError(
            "standby replication public key is not exact ed25519"
        )
    return public_key


def _restricted_authorized_key_bytes(public_key: str) -> bytes:
    public_key = _validate_ed25519_public_key(public_key)
    return (
        'restrict,command="/usr/bin/python3.12 /usr/bin/rrsync -wo -no-del '
        '/var/lib/dharma-sadhana/snapshot-incoming" ' + public_key + "\n"
    ).encode("ascii")


def _validate_restricted_standby_key_destination(
    public_key: str,
    *,
    role: str,
    account: pwd.struct_passwd,
    expected_root_uid: int = 0,
    require_installed: bool = False,
) -> bytes:
    """Pre-admit the exact forced route and any already-installed destination."""
    if role != "standby":
        raise ReleaseContractError("forced replication route exists only on standby")
    if (
        account.pw_name != "dharma-sadhana"
        or account.pw_uid == 0
        or account.pw_gid == 0
        or account.pw_dir != "/var/lib/dharma-sadhana"
        or account.pw_shell != "/bin/sh"
    ):
        raise ReleaseContractError("standby replication identity differs")
    forced = _restricted_authorized_key_bytes(public_key)
    for executable in (Path(PYTHON312_PATH), RRSYNC_PATH):
        try:
            identity = executable.lstat()
        except OSError as exc:
            raise ReleaseContractError(
                f"forced replication tool is unavailable: {executable.name}"
            ) from exc
        if (
            not stat.S_ISREG(identity.st_mode)
            or executable.is_symlink()
            or identity.st_uid != expected_root_uid
            or not identity.st_mode & stat.S_IXUSR
            or stat.S_IMODE(identity.st_mode) & 0o022
        ):
            raise ReleaseContractError(
                f"forced replication tool lacks root custody: {executable.name}"
            )
    if STANDBY_SSH_ROOT.exists() or STANDBY_SSH_ROOT.is_symlink():
        root_identity = STANDBY_SSH_ROOT.lstat()
        if (
            STANDBY_SSH_ROOT.is_symlink()
            or not stat.S_ISDIR(root_identity.st_mode)
            or root_identity.st_uid != account.pw_uid
            or root_identity.st_gid != account.pw_gid
            or stat.S_IMODE(root_identity.st_mode) != 0o700
        ):
            raise ReleaseContractError("standby SSH root custody differs")
    elif require_installed:
        raise ReleaseContractError("standby forced replication route is absent")
    authorized_keys = STANDBY_SSH_ROOT / "authorized_keys"
    if authorized_keys.exists() or authorized_keys.is_symlink():
        identity = authorized_keys.lstat()
        if (
            authorized_keys.is_symlink()
            or not stat.S_ISREG(identity.st_mode)
            or identity.st_uid != account.pw_uid
            or identity.st_gid != account.pw_gid
            or stat.S_IMODE(identity.st_mode) != 0o600
            or identity.st_nlink != 1
            or identity.st_size != len(forced)
        ):
            raise ReleaseContractError(
                "standby authorized_keys differs from forced route"
            )
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        if not nofollow:
            raise ReleaseContractError(
                "platform lacks no-follow standby route admission"
            )
        descriptor = os.open(authorized_keys, os.O_RDONLY | nofollow)
        try:
            opened = os.fstat(descriptor)
            raw = os.read(descriptor, len(forced) + 1)
            stable = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        admitted_identity = (
            identity.st_dev,
            identity.st_ino,
            identity.st_size,
            identity.st_mtime_ns,
        )
        if (
            admitted_identity
            != (
                opened.st_dev,
                opened.st_ino,
                opened.st_size,
                opened.st_mtime_ns,
            )
            or admitted_identity
            != (
                stable.st_dev,
                stable.st_ino,
                stable.st_size,
                stable.st_mtime_ns,
            )
            or raw != forced
        ):
            raise ReleaseContractError(
                "standby authorized_keys differs from forced route"
            )
    elif require_installed:
        raise ReleaseContractError("standby forced replication route is absent")
    return forced


def _validate_installed_standby_replication_route(
    *,
    account: pwd.struct_passwd,
    expected_root_uid: int = 0,
) -> None:
    public_key = _read_standby_public_key(expected_root_uid=expected_root_uid)
    _validate_restricted_standby_key_destination(
        public_key,
        role="standby",
        account=account,
        expected_root_uid=expected_root_uid,
        require_installed=True,
    )


def _install_restricted_standby_key(
    public_key: str,
    *,
    role: str,
    account: pwd.struct_passwd,
    expected_root_uid: int = 0,
    checkpoint: Callable[[str], None] | None = None,
) -> None:
    """Atomically install the standby-only forced SSH route, with crash rollback."""
    forced = _validate_restricted_standby_key_destination(
        public_key,
        role=role,
        account=account,
        expected_root_uid=expected_root_uid,
    )
    ssh_root_preexisted = STANDBY_SSH_ROOT.exists() or STANDBY_SSH_ROOT.is_symlink()
    authorized_keys = STANDBY_SSH_ROOT / "authorized_keys"
    if authorized_keys.exists() or authorized_keys.is_symlink():
        return
    published = False

    def publication_checkpoint(phase: str) -> None:
        nonlocal published
        if phase == "private_bytes_post_publish":
            published = True
        if checkpoint is not None:
            checkpoint(phase)

    try:
        _ensure_host_directory(
            STANDBY_SSH_ROOT,
            uid=account.pw_uid,
            gid=account.pw_gid,
            mode=0o700,
        )
        _atomic_private_bytes(
            authorized_keys,
            forced,
            uid=account.pw_uid,
            gid=account.pw_gid,
            checkpoint=publication_checkpoint,
        )
        _validate_restricted_standby_key_destination(
            public_key,
            role=role,
            account=account,
            expected_root_uid=expected_root_uid,
        )
    except Exception:
        try:
            if published:
                _validate_restricted_standby_key_destination(
                    public_key,
                    role=role,
                    account=account,
                    expected_root_uid=expected_root_uid,
                )
                authorized_keys.unlink()
            if not ssh_root_preexisted and STANDBY_SSH_ROOT.exists():
                STANDBY_SSH_ROOT.rmdir()
        except (OSError, ReleaseContractError) as rollback_exc:
            raise ReleaseContractError(
                "standby authorized_keys transaction rollback failed"
            ) from rollback_exc
        raise


def _validate_existing_writer_marker(
    *,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> bool:
    if WRITER_MARKER.is_symlink():
        raise ReleaseContractError("writer marker cannot be a symlink")
    if not WRITER_MARKER.exists():
        return False
    marker = WRITER_MARKER.lstat()
    if (
        not stat.S_ISREG(marker.st_mode)
        or marker.st_uid != expected_root_uid
        or marker.st_gid != expected_root_gid
        or stat.S_IMODE(marker.st_mode) != 0o600
        or marker.st_nlink != 1
        or WRITER_MARKER.read_bytes() != b"writer\n"
    ):
        raise ReleaseContractError("existing writer marker lacks exact custody")
    return True


def _uid_process_ids(uid: int, *, proc_root: Path = Path("/proc")) -> tuple[int, ...]:
    if uid <= 0:
        raise ReleaseContractError("process audit uid differs")
    observed: list[int] = []
    try:
        candidates = tuple(proc_root.iterdir())
    except OSError as exc:
        raise ReleaseContractError("cannot enumerate build-identity processes") from exc
    for candidate in candidates:
        if not candidate.name.isdecimal():
            continue
        try:
            raw = (candidate / "status").read_text(encoding="ascii")
        except (OSError, UnicodeError):
            continue
        match = re.search(r"^Uid:\s+([0-9]+)(?:\s+[0-9]+){3}$", raw, re.MULTILINE)
        if match and int(match.group(1)) == uid:
            observed.append(int(candidate.name))
    return tuple(sorted(observed))


def _require_solo_hardened_build_process(
    *,
    proc_root: Path = Path("/proc"),
    cgroup_root: Path = Path("/sys/fs/cgroup"),
) -> None:
    try:
        status = (proc_root / "self/status").read_text(encoding="ascii")
        cgroup = (proc_root / "self/cgroup").read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        raise ReleaseContractError(
            "build sandbox process evidence is unavailable"
        ) from exc
    if not re.search(r"^NoNewPrivs:\s+1$", status, re.MULTILINE):
        raise ReleaseContractError("build sandbox lacks no-new-privileges")
    unified = [line[3:] for line in cgroup.splitlines() if line.startswith("0::/")]
    if len(unified) != 1 or "dharma-sadhana-build-" not in unified[0]:
        raise ReleaseContractError("build process is outside its transient cgroup")
    process_file = cgroup_root / unified[0].lstrip("/") / "cgroup.procs"
    try:
        pids = {
            int(line)
            for line in process_file.read_text(encoding="ascii").splitlines()
            if line
        }
    except (OSError, UnicodeError, ValueError) as exc:
        raise ReleaseContractError("build cgroup process proof is unavailable") from exc
    if pids != {os.getpid()}:
        raise ReleaseContractError("build cgroup contains a lingering process")


def _make_build_process_undumpable() -> None:
    """Prevent same-UID lifecycle children from ptracing the trusted driver."""
    if platform.system() != "Linux":
        raise ReleaseContractError("build ptrace barrier requires Linux")
    libc = ctypes.CDLL(None, use_errno=True)
    prctl = getattr(libc, "prctl", None)
    # PR_SET_DUMPABLE=4, PR_GET_DUMPABLE=3.
    if prctl is None or prctl(4, 0, 0, 0, 0) != 0 or prctl(3, 0, 0, 0, 0) != 0:
        error_number = ctypes.get_errno()
        raise ReleaseContractError(
            f"build process dumpability could not be disabled: errno={error_number}"
        )


def execute_isolated_build_plan(
    *,
    staging: Path,
    bundle: Path,
    manifest_path: Path,
    uv_binary: Path,
    release_sha: str,
    expected_uid: int,
    expected_gid: int,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
) -> dict[str, Any]:
    """Run the complete dependency/build lifecycle inside one transient cgroup."""
    if (
        expected_uid <= 0
        or expected_gid <= 0
        or os.geteuid() != expected_uid
        or os.getegid() != expected_gid
    ):
        raise ReleaseContractError("isolated build plan identity differs")
    if not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("isolated build release SHA differs")
    staging = staging.resolve(strict=True)
    if (
        bundle != staging / "candidate.bundle"
        or manifest_path != staging / "release-manifest.json"
        or uv_binary
        != Path(f"/opt/dharma-sadhana/tooling/uv-{UV_VERSION}/bin/uv")
    ):
        raise ReleaseContractError("isolated build input paths differ")
    staging_identity = staging.lstat()
    bundle_identity = bundle.lstat()
    manifest_identity = manifest_path.lstat()
    if (
        staging.is_symlink()
        or not stat.S_ISDIR(staging_identity.st_mode)
        or staging_identity.st_uid != expected_uid
        or staging_identity.st_gid != expected_gid
        or stat.S_IMODE(staging_identity.st_mode) != 0o700
        or bundle.is_symlink()
        or not stat.S_ISREG(bundle_identity.st_mode)
        or bundle_identity.st_uid != expected_uid
        or bundle_identity.st_gid != expected_gid
        or stat.S_IMODE(bundle_identity.st_mode) != 0o400
        or bundle_identity.st_nlink != 1
        or manifest_path.is_symlink()
        or not stat.S_ISREG(manifest_identity.st_mode)
        or manifest_identity.st_uid != expected_uid
        or manifest_identity.st_gid != expected_gid
        or stat.S_IMODE(manifest_identity.st_mode) != 0o400
        or manifest_identity.st_nlink != 1
    ):
        raise ReleaseContractError("isolated build staging custody differs")
    manifest_payload, _manifest_raw, _manifest_identity = (
        _read_exact_custodied_json(
            manifest_path,
            expected_uid=expected_uid,
            expected_gid=expected_gid,
            expected_mode=0o400,
            maximum_bytes=_MAX_JSON_BYTES,
        )
    )
    manifest = validate_manifest(manifest_payload, for_activation=True)
    if manifest["release_sha"] != release_sha:
        raise ReleaseContractError("isolated build manifest release differs")
    _make_build_process_undumpable()
    build_home = staging / "build-home"
    uv_cache = staging / "uv-cache"
    npm_cache = staging / "npm-cache"
    for private_root in (build_home, uv_cache, npm_cache):
        identity = private_root.lstat()
        if (
            private_root.is_symlink()
            or not stat.S_ISDIR(identity.st_mode)
            or identity.st_uid != expected_uid
            or identity.st_gid != expected_gid
            or stat.S_IMODE(identity.st_mode) != 0o700
            or any(private_root.iterdir())
        ):
            raise ReleaseContractError("isolated build cache custody differs")
    build_env = dict(_SAFE_SUBPROCESS_ENV)
    build_env.update(
        {
            "HOME": str(build_home),
            "UV_CACHE_DIR": str(uv_cache),
            "UV_LINK_MODE": "copy",
            "UV_NO_PROGRESS": "1",
            "npm_config_cache": str(npm_cache),
            "npm_config_update_notifier": "false",
            "npm_config_audit": "false",
            "DHARMA_API_PROXY_URL": DASHBOARD_PROXY_URL,
            "DHARMA_API_INTERNAL_URL": DASHBOARD_PROXY_URL,
        }
    )
    commands: list[str] = []

    def execute(
        label: str,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str] = build_env,
    ) -> subprocess.CompletedProcess[str]:
        result = runner(argv, cwd=cwd, env=env)
        commands.append(label)
        return result

    version = execute("uv-version", (str(uv_binary), "--version"), cwd=staging)
    if version.stdout.strip().split()[:2] != ["uv", UV_VERSION]:
        raise ReleaseContractError("pinned uv executable version differs")
    repo = staging / "repo"
    execute(
        "git-clone",
        (GIT_PATH, "clone", "--no-checkout", str(bundle), str(repo)),
        cwd=staging,
    )
    execute(
        "git-checkout",
        (GIT_PATH, "checkout", "--detach", release_sha),
        cwd=repo,
    )
    execute(
        "git-origin",
        (GIT_PATH, "remote", "set-url", "origin", CANONICAL_ORIGIN),
        cwd=repo,
    )
    execute(
        "uv-venv",
        (
            str(uv_binary),
            "venv",
            "--python",
            PYTHON312_PATH,
            "--copies",
            ".venv",
        ),
        cwd=repo,
    )
    sync_env = dict(build_env)
    sync_env["VIRTUAL_ENV"] = str(repo / ".venv")
    execute(
        "uv-sync",
        (str(uv_binary), "sync", "--active", "--frozen", "--no-dev"),
        cwd=repo,
        env=sync_env,
    )
    execute(
        "npm-ci",
        (NPM_PATH, "ci", "--legacy-peer-deps", "--no-audit", "--no-fund"),
        cwd=repo / "dashboard",
    )
    execute(
        "next-build",
        (NPM_PATH, "run", "build"),
        cwd=repo / "dashboard",
    )
    python_version = execute(
        "venv-python-version",
        (str(repo / ".venv/bin/python"), "--version"),
        cwd=repo,
    )
    if not python_version.stdout.strip().startswith("Python 3.12."):
        raise ReleaseContractError("venv must use Python 3.12")
    # All untrusted lifecycle children must be gone before trusted Python reads
    # any candidate output or removes candidate-controlled Git metadata.
    _require_solo_hardened_build_process()
    verify_dashboard_build(repo / "dashboard")
    verify_venv(repo / ".venv", expected_uid=expected_uid, execute_version=False)
    tracked_driver = repo / "scripts/runtime/sadhana_release.py"
    if sha256_file(tracked_driver, max_bytes=_MAX_JSON_BYTES) != sha256_file(
        Path(__file__), max_bytes=_MAX_JSON_BYTES
    ):
        raise ReleaseContractError("isolated build driver differs from tracked bytes")
    verify_checkout(repo, manifest)
    commands.append("git-verify-checkout")
    verify_tracked_checkout(repo, release_sha)
    commands.append("git-verify-tracked")
    _require_solo_hardened_build_process()
    git_metadata = repo / ".git"
    git_identity = git_metadata.lstat()
    if (
        git_metadata.is_symlink()
        or not stat.S_ISDIR(git_identity.st_mode)
        or git_identity.st_uid != expected_uid
        or git_identity.st_gid != expected_gid
    ):
        raise ReleaseContractError("candidate Git metadata custody differs")
    shutil.rmtree(git_metadata)
    commands.append("git-metadata-removed")
    expected_commands = [
        "uv-version",
        "git-clone",
        "git-checkout",
        "git-origin",
        "uv-venv",
        "uv-sync",
        "npm-ci",
        "next-build",
        "venv-python-version",
        "git-verify-checkout",
        "git-verify-tracked",
        "git-metadata-removed",
    ]
    if commands != expected_commands:
        raise ReleaseContractError("isolated build command ledger differs")
    return {
        "schema_version": "dharma.sadhana.isolated_build.v1",
        "release_sha": release_sha,
        "build_uid": expected_uid,
        "build_gid": expected_gid,
        "no_new_privileges": True,
        "solo_cgroup_process": True,
        "build_process_dumpable": False,
        "runtime_max_seconds": 1800,
        "tasks_max": 256,
        "memory_max_bytes": 4_294_967_296,
        "commands": commands,
        "manifest_sha256": sha256_file(manifest_path, max_bytes=_MAX_JSON_BYTES),
        "build_driver_sha256": sha256_file(Path(__file__), max_bytes=_MAX_JSON_BYTES),
        "candidate_code_executed_as_root": False,
    }


def _install_exact_build_driver(
    *,
    release_sha: str,
    source: Path | None = None,
) -> Path:
    """Install the already-authorized deploy executable without invoking Git.

    The caller is already executing this module with root authority.  Reusing
    those exact bytes avoids asking root Git to parse bundle- or candidate-owned
    metadata.  The isolated build later proves that these bytes equal the
    tracked driver at ``release_sha`` before its receipt can pass.
    """
    destination = UV_TOOLING_ROOT / f"{BUILD_DRIVER_PREFIX}{release_sha}.py"
    admitted_source = (source or Path(__file__)).resolve(strict=True)
    source_identity = admitted_source.lstat()
    if (
        admitted_source.is_symlink()
        or not stat.S_ISREG(source_identity.st_mode)
        or source_identity.st_nlink != 1
        or not 0 < source_identity.st_size <= _MAX_JSON_BYTES
    ):
        raise ReleaseContractError("authorized build driver source custody differs")
    descriptor = os.open(admitted_source, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(descriptor)
        if (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
        ) != (
            source_identity.st_dev,
            source_identity.st_ino,
            source_identity.st_size,
            source_identity.st_mtime_ns,
        ):
            raise ReleaseContractError("authorized build driver source changed")
        raw = os.read(descriptor, _MAX_JSON_BYTES + 1)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) != (
        opened.st_dev,
        opened.st_ino,
        opened.st_size,
        opened.st_mtime_ns,
    ):
        raise ReleaseContractError("authorized build driver source changed")
    if (
        not raw.startswith(b"#!/usr/bin/env python3\n")
        or len(raw) != source_identity.st_size
    ):
        raise ReleaseContractError("exact build driver bytes differ")
    if destination.exists() or destination.is_symlink():
        identity = destination.lstat()
        if (
            destination.is_symlink()
            or not stat.S_ISREG(identity.st_mode)
            or identity.st_uid != 0
            or identity.st_gid != 0
            or stat.S_IMODE(identity.st_mode) != 0o555
            or identity.st_nlink != 1
            or destination.read_bytes() != raw
        ):
            raise ReleaseContractError("existing exact build driver conflicts")
        return destination
    _atomic_private_bytes(destination, raw, uid=0, gid=0)
    os.chmod(destination, 0o555)
    return destination


def _invoke_isolated_build_plan(
    *,
    staging: Path,
    build_account: pwd.struct_passwd,
    uv_binary: Path,
    build_driver: Path,
    manifest_path: Path,
    expected_manifest_sha256: str,
    release_sha: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise ReleaseContractError("isolated build invocation requires root")
    if _uid_process_ids(build_account.pw_uid):
        raise ReleaseContractError("build identity already has a live process")
    admitted_manifest_sha256 = _require_hash(
        expected_manifest_sha256,
        "expected_manifest_sha256",
    )
    systemd_run = Path(SYSTEMD_RUN_PATH)
    identity = systemd_run.lstat()
    if (
        systemd_run.is_symlink()
        or not stat.S_ISREG(identity.st_mode)
        or identity.st_uid != 0
        or not identity.st_mode & stat.S_IXUSR
        or stat.S_IMODE(identity.st_mode) & 0o022
    ):
        raise ReleaseContractError("systemd-run lacks root executable custody")
    unit = f"dharma-sadhana-build-{release_sha}.service"
    expected_driver = UV_TOOLING_ROOT / f"{BUILD_DRIVER_PREFIX}{release_sha}.py"
    if build_driver != expected_driver:
        raise ReleaseContractError("isolated build driver path differs")
    driver_identity = build_driver.lstat()
    if (
        build_driver.is_symlink()
        or not stat.S_ISREG(driver_identity.st_mode)
        or driver_identity.st_uid != 0
        or driver_identity.st_gid != 0
        or stat.S_IMODE(driver_identity.st_mode) != 0o555
        or driver_identity.st_nlink != 1
    ):
        raise ReleaseContractError("isolated build driver custody differs")
    command = (
        SYSTEMD_RUN_PATH,
        "--quiet",
        "--wait",
        "--collect",
        "--pipe",
        "--service-type=exec",
        f"--unit={unit}",
        f"--uid={build_account.pw_uid}",
        f"--gid={build_account.pw_gid}",
        f"--working-directory={staging}",
        "--property=NoNewPrivileges=yes",
        "--property=CapabilityBoundingSet=",
        "--property=AmbientCapabilities=",
        "--property=KillMode=control-group",
        "--property=RuntimeMaxSec=1800",
        "--property=TasksMax=256",
        "--property=MemoryMax=4294967296",
        "--property=PrivateDevices=yes",
        "--property=PrivateTmp=yes",
        "--property=ProtectHome=yes",
        "--property=ProtectSystem=strict",
        "--property=RestrictNamespaces=yes",
        "--property=RestrictRealtime=yes",
        "--property=RestrictSUIDSGID=yes",
        "--property=SystemCallArchitectures=native",
        "--property=SystemCallFilter=~ptrace process_vm_readv process_vm_writev",
        "--property=UMask=0077",
        f"--property=ReadWritePaths={staging}",
        "--",
        PYTHON312_PATH,
        str(build_driver),
        "build-candidate",
        "--staging",
        str(staging),
        "--bundle",
        str(staging / "candidate.bundle"),
        "--manifest",
        str(manifest_path),
        "--uv-binary",
        str(uv_binary),
        "--release-sha",
        release_sha,
        "--expected-uid",
        str(build_account.pw_uid),
        "--expected-gid",
        str(build_account.pw_gid),
    )
    try:
        completed = runner(command, cwd=Path("/"), check=False)
    finally:
        remaining = _uid_process_ids(build_account.pw_uid)
    if remaining:
        raise ReleaseContractError("isolated build left a live build-uid process")
    if completed.returncode != 0:
        raise ReleaseContractError("isolated build transient service failed")
    try:
        receipt = json.loads(completed.stdout)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseContractError("isolated build receipt is invalid") from exc
    expected_fields = {
        "schema_version",
        "release_sha",
        "build_uid",
        "build_gid",
        "no_new_privileges",
        "solo_cgroup_process",
        "build_process_dumpable",
        "runtime_max_seconds",
        "tasks_max",
        "memory_max_bytes",
        "commands",
        "manifest_sha256",
        "build_driver_sha256",
        "candidate_code_executed_as_root",
    }
    if (
        not isinstance(receipt, dict)
        or set(receipt) != expected_fields
        or receipt.get("schema_version") != "dharma.sadhana.isolated_build.v1"
        or receipt.get("release_sha") != release_sha
        or receipt.get("build_uid") != build_account.pw_uid
        or receipt.get("build_gid") != build_account.pw_gid
        or receipt.get("no_new_privileges") is not True
        or receipt.get("solo_cgroup_process") is not True
        or receipt.get("build_process_dumpable") is not False
        or receipt.get("runtime_max_seconds") != 1800
        or receipt.get("tasks_max") != 256
        or receipt.get("memory_max_bytes") != 4_294_967_296
        or receipt.get("manifest_sha256")
        != admitted_manifest_sha256
        or receipt.get("build_driver_sha256")
        != sha256_file(build_driver, max_bytes=_MAX_JSON_BYTES)
        or receipt.get("candidate_code_executed_as_root") is not False
        or receipt.get("commands")
        != [
            "uv-version",
            "git-clone",
            "git-checkout",
            "git-origin",
            "uv-venv",
            "uv-sync",
            "npm-ci",
            "next-build",
            "venv-python-version",
            "git-verify-checkout",
            "git-verify-tracked",
            "git-metadata-removed",
        ]
    ):
        raise ReleaseContractError("isolated build receipt binding differs")
    receipt["post_exit_build_uid_process_count"] = 0
    return receipt


def _retake_build_staging_custody(
    staging: Path,
    *,
    build_uid: int,
    build_gid: int,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> None:
    """Retire build-parent authority only after a fresh zero-process proof."""
    if os.geteuid() != expected_root_uid:
        raise ReleaseContractError("build staging custody barrier requires root")
    if _uid_process_ids(build_uid):
        raise ReleaseContractError(
            "build staging custody cannot be retaken while a build process remains"
        )
    identity = staging.lstat()
    descriptor = os.open(
        staging,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        opened = os.fstat(descriptor)
        if (
            staging.is_symlink()
            or (opened.st_dev, opened.st_ino) != (identity.st_dev, identity.st_ino)
            or opened.st_uid != build_uid
            or opened.st_gid != build_gid
            or stat.S_IMODE(opened.st_mode) != 0o700
        ):
            raise ReleaseContractError("build staging custody changed at barrier")
        os.fchown(descriptor, expected_root_uid, expected_root_gid)
        os.fchmod(descriptor, 0o700)
        os.fsync(descriptor)
        retained = os.fstat(descriptor)
        if (
            (retained.st_dev, retained.st_ino) != (opened.st_dev, opened.st_ino)
            or retained.st_uid != expected_root_uid
            or retained.st_gid != expected_root_gid
            or stat.S_IMODE(retained.st_mode) != 0o700
        ):
            raise ReleaseContractError("build staging root custody was not retained")
    finally:
        os.close(descriptor)


def _cleanup_build_staging(
    staging: Path,
    *,
    build_uid: int,
    build_gid: int,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> None:
    """Remove staging only after root custody and build-process absence."""
    if not staging.exists() and not staging.is_symlink():
        return
    identity = staging.lstat()
    if staging.is_symlink() or not stat.S_ISDIR(identity.st_mode):
        raise ReleaseContractError("failed build staging is not a directory")
    if identity.st_uid == build_uid:
        _retake_build_staging_custody(
            staging,
            build_uid=build_uid,
            build_gid=build_gid,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
    elif (
        identity.st_uid != expected_root_uid
        or identity.st_gid != expected_root_gid
        or stat.S_IMODE(identity.st_mode) != 0o700
    ):
        raise ReleaseContractError("failed build staging lacks root custody")
    if _uid_process_ids(build_uid):
        raise ReleaseContractError(
            "failed build staging retained while a build process remains"
        )
    shutil.rmtree(staging)


def _admit_build_manifest_after_custody_barrier(
    manifest_path: Path,
    *,
    expected_raw: bytes,
    expected_sha256: str,
    build_uid: int,
    build_gid: int,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> None:
    """Root-read the exact build manifest only after retaking its parent."""
    expected_sha256 = _require_hash(expected_sha256, "expected_manifest_sha256")
    if (
        not 0 < len(expected_raw) <= _MAX_JSON_BYTES
        or hashlib.sha256(expected_raw).hexdigest() != expected_sha256
    ):
        raise ReleaseContractError("root-admitted build manifest binding differs")
    staging = manifest_path.parent
    identity = staging.lstat()
    if (
        staging.is_symlink()
        or not stat.S_ISDIR(identity.st_mode)
        or identity.st_uid != expected_root_uid
        or identity.st_gid != expected_root_gid
        or stat.S_IMODE(identity.st_mode) != 0o700
    ):
        raise ReleaseContractError("build staging root custody barrier differs")
    admitted_raw, _manifest_identity = _read_exact_custodied_bytes(
        manifest_path,
        expected_uid=build_uid,
        expected_gid=build_gid,
        expected_mode=0o400,
        maximum_bytes=_MAX_JSON_BYTES,
    )
    if (
        admitted_raw != expected_raw
        or hashlib.sha256(admitted_raw).hexdigest() != expected_sha256
    ):
        raise ReleaseContractError("build manifest differs after root custody barrier")


def _staged_release_receipt_paths(
    release_sha: str,
    *,
    receipt_root: Path = RELEASE_RECEIPT_ROOT,
) -> tuple[Path, Path, Path, Path]:
    if not _COMMIT_RE.fullmatch(release_sha) or not receipt_root.is_absolute():
        raise ReleaseContractError("staged release receipt binding differs")
    release_receipt_root = receipt_root / release_sha
    return (
        release_receipt_root,
        release_receipt_root / STAGED_RELEASE_TRACKED_LEDGER_FILE,
        release_receipt_root / STAGED_RELEASE_BUILD_RECEIPT_FILE,
        release_receipt_root / STAGED_RELEASE_ADMISSION_FILE,
    )


def _runtime_preparation_env_path(
    release_sha: str,
    *,
    receipt_root: Path = RELEASE_RECEIPT_ROOT,
) -> Path:
    if not _COMMIT_RE.fullmatch(release_sha) or not receipt_root.is_absolute():
        raise ReleaseContractError("runtime preparation environment binding differs")
    return receipt_root / release_sha / RUNTIME_PREPARATION_ENV_FILE


def _runtime_preparation_supervisor_config(
    supervisor_env_path: Path = Path(ENV_FILES[0]),
) -> dict[str, str]:
    """Project only validated nonsecret prep config from the closed env file."""
    supervisor = _private_env_bindings(supervisor_env_path)
    if set(supervisor) != _STATIC_SUPERVISOR_ENV_FIELDS:
        raise ReleaseContractError("supervisor.env fields differ")
    if not _STABLE_ID_RE.fullmatch(supervisor.get("SADHANA_OPERATOR_ID", "")):
        raise ReleaseContractError("supervisor.env operator is not a stable ID")
    maximum = _require_bounded_env_integer(
        supervisor,
        "SADHANA_MAX_DISPATCH_PER_CYCLE",
        1,
        64,
        "supervisor.env",
    )
    cycle = _require_bounded_env_integer(
        supervisor,
        "SADHANA_CYCLE_INTERVAL_SECONDS",
        1,
        3600,
        "supervisor.env",
    )
    freshness = _require_bounded_env_integer(
        supervisor,
        "SADHANA_FRESHNESS_SECONDS",
        1,
        86_400,
        "supervisor.env",
    )
    if cycle > freshness:
        raise ReleaseContractError(
            "supervisor cycle cannot exceed its evidence freshness window"
        )
    return {
        "SADHANA_PREP_OPERATOR_ID": supervisor["SADHANA_OPERATOR_ID"],
        "SADHANA_PREP_MAX_DISPATCH_PER_CYCLE": str(maximum),
        "SADHANA_PREP_CYCLE_INTERVAL_SECONDS": str(cycle),
        "SADHANA_PREP_FRESHNESS_SECONDS": str(freshness),
    }


def _runtime_preparation_environment_bindings(
    manifest: Mapping[str, Any],
    *,
    admission: Mapping[str, Any],
    release_sha: str,
    release_path: Path,
    account: pwd.struct_passwd,
    input_root: Path = INPUT_SET_TARGET_ROOT,
    admission_projection: Path = PREPARED_RELEASE_ADMISSION_PROJECTION,
    state_dir: Path = Path(STATE_ROOT),
    prepared_root: Path = PREPARED_RUNTIME_MANIFEST_ROOT,
    supervisor_env_path: Path = Path(ENV_FILES[0]),
) -> dict[str, str]:
    """Derive the nonsecret prep CLI projection from one sealed input set."""
    payload = validate_input_set_manifest(manifest)
    resolved_release_path = release_path.resolve(strict=True)
    if (
        not release_path.is_absolute()
        or release_path != resolved_release_path
        or input_root != INPUT_SET_TARGET_ROOT
        or admission_projection != PREPARED_RELEASE_ADMISSION_PROJECTION
        or state_dir != Path(STATE_ROOT)
        or prepared_root != PREPARED_RUNTIME_MANIFEST_ROOT
        or account.pw_name != "dharma-sadhana"
        or min(account.pw_uid, account.pw_gid) <= 0
        or admission.get("release_sha") != release_sha
        or admission.get("release_root") != str(resolved_release_path)
        or admission.get("release_input_set_digest")
        != payload["input_set_digest"]
    ):
        raise ReleaseContractError("runtime preparation release indices differ")
    entries = {
        entry["target_relative_path"]: entry for entry in payload["entries"]
    }
    required_targets = set(RUNTIME_PREPARATION_INPUT_PATHS.values()) | {
        OBJECTIVE_INPUT_PATH
    }
    if not required_targets <= set(entries):
        raise ReleaseContractError("runtime preparation input set is incomplete")

    roster_relative = RUNTIME_PREPARATION_INPUT_PATHS["roster"]
    roster_entry = entries[roster_relative]
    roster_path = input_root.joinpath(*PurePosixPath(roster_relative).parts)
    roster_raw, _roster_identity = _read_exact_custodied_bytes(
        roster_path,
        expected_uid=account.pw_uid,
        expected_gid=account.pw_gid,
        maximum_bytes=roster_entry["bytes"],
    )
    if (
        len(roster_raw) != roster_entry["bytes"]
        or hashlib.sha256(roster_raw).hexdigest() != roster_entry["sha256"]
    ):
        raise ReleaseContractError("runtime preparation roster bytes differ")
    try:
        roster = json.loads(roster_raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseContractError("runtime preparation roster is invalid") from exc
    agents = roster.get("agents") if isinstance(roster, dict) else None
    verifier = [
        agent
        for agent in agents or []
        if isinstance(agent, dict)
        and agent.get("role") == "validator"
        and agent.get("provider") == "ollama"
    ]
    if (
        not isinstance(roster, dict)
        or roster.get("schema") != "dharma.sadhana.agent_roster.v1"
        or roster.get("campaign_id") != MISSION_ID
        or roster.get("objective_sha256") != payload["objective_sha256"]
        or not isinstance(agents, list)
        or len(verifier) != 1
        or not isinstance(verifier[0].get("name"), str)
        or not _STABLE_ID_RE.fullmatch(verifier[0]["name"])
    ):
        raise ReleaseContractError("runtime preparation verifier seat is not exact")

    def installed_path(label: str) -> str:
        relative = RUNTIME_PREPARATION_INPUT_PATHS[label]
        return str(input_root.joinpath(*PurePosixPath(relative).parts))

    def prefixed_hash(label: str) -> str:
        return "sha256:" + entries[RUNTIME_PREPARATION_INPUT_PATHS[label]][
            "sha256"
        ]

    bindings = {
        "SADHANA_PREP_RELEASE_ROOT": str(resolved_release_path),
        "SADHANA_PREP_RELEASE_SHA": release_sha,
        "SADHANA_PREP_RELEASE_INPUT_SET_DIGEST": payload["input_set_digest"],
        "SADHANA_PREP_RELEASE_ADMISSION_RECEIPT": str(admission_projection),
        "SADHANA_PREP_CONTRACTS": installed_path("contracts"),
        "SADHANA_PREP_OBSERVED_SOURCE": installed_path("observed_source"),
        "SADHANA_PREP_ROSTER": str(roster_path),
        "SADHANA_PREP_ROSTER_SHA256": roster_entry["sha256"],
        "SADHANA_PREP_OBJECTIVE_SHA256": entries[OBJECTIVE_INPUT_PATH]["sha256"],
        "SADHANA_PREP_STATE_DIR": str(state_dir),
        "SADHANA_PREP_PROJECTION_PATH": str(WRITER_PROJECTION_PATH),
        "SADHANA_PREP_MANIFEST_STAGING_ROOT": str(prepared_root),
        **_runtime_preparation_supervisor_config(supervisor_env_path),
        "SADHANA_PREP_VERIFIER_SEAT": verifier[0]["name"],
        "SADHANA_PREP_EVALUATOR_PATH": installed_path("evaluator"),
        "SADHANA_PREP_EVALUATOR_SHA256": prefixed_hash("evaluator"),
        "SADHANA_PREP_POLICY_PATH": installed_path("policy"),
        "SADHANA_PREP_POLICY_SHA256": prefixed_hash("policy"),
        "SADHANA_PREP_OPERATOR_CONTROL_SEMANTICS_SHA256": prefixed_hash(
            "operator_control_semantics"
        ),
        "SADHANA_PREP_OPERATOR_CONTROL_AUTHORITY_BINDING_SHA256": prefixed_hash(
            "operator_control_authority_binding"
        ),
        "SADHANA_PREP_DEPLOYMENT_AUTHORITY_TOPOLOGY_SHA256": prefixed_hash(
            "deployment_authority_topology"
        ),
        "SADHANA_PREP_DEPLOYMENT_AUTHORITY_CREDENTIAL_CLARIFICATION_SHA256": (
            prefixed_hash("deployment_authority_credential_clarification")
        ),
    }
    if set(bindings) != _RUNTIME_PREPARATION_ENV_FIELDS or any(
        not isinstance(value, str)
        or not re.fullmatch(r"[A-Za-z0-9_./:@+-]{1,4096}", value)
        for value in bindings.values()
    ):
        raise ReleaseContractError("runtime preparation environment is unsafe")
    return bindings


def _runtime_preparation_environment_bytes(bindings: Mapping[str, str]) -> bytes:
    if set(bindings) != _RUNTIME_PREPARATION_ENV_FIELDS:
        raise ReleaseContractError("runtime preparation environment fields differ")
    return "".join(
        f"{key}={bindings[key]}\n" for key in sorted(bindings)
    ).encode("ascii")


def _publish_runtime_preparation_environment(
    manifest: Mapping[str, Any],
    *,
    admission: Mapping[str, Any],
    release_sha: str,
    release_path: Path,
    account: pwd.struct_passwd,
    receipt_root: Path = RELEASE_RECEIPT_ROOT,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> Path:
    bindings = _runtime_preparation_environment_bindings(
        manifest,
        admission=admission,
        release_sha=release_sha,
        release_path=release_path,
        account=account,
    )
    destination = _runtime_preparation_env_path(
        release_sha,
        receipt_root=receipt_root,
    )
    _publish_or_replay_exact_bytes(
        destination,
        _runtime_preparation_environment_bytes(bindings),
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        maximum_bytes=64 * 1024,
    )
    return destination


def _ensure_private_directory(
    path: Path,
    *,
    uid: int,
    gid: int,
) -> None:
    if not path.is_absolute():
        raise ReleaseContractError("private directory path must be absolute")
    parent = path.parent.lstat()
    if (
        path.parent.is_symlink()
        or not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid not in {0, uid}
        or stat.S_IMODE(parent.st_mode) & 0o022
    ):
        raise ReleaseContractError("private directory parent custody differs")
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    identity = path.lstat()
    if path.is_symlink() or not stat.S_ISDIR(identity.st_mode):
        raise ReleaseContractError("private directory is not a real directory")
    os.chown(path, uid, gid)
    os.chmod(path, 0o700)
    identity = path.lstat()
    if (
        identity.st_uid != uid
        or identity.st_gid != gid
        or stat.S_IMODE(identity.st_mode) != 0o700
    ):
        raise ReleaseContractError("private directory custody differs")


def _validate_isolated_build_receipt(
    payload: Mapping[str, Any],
    *,
    release_sha: str,
) -> dict[str, Any]:
    if (
        set(payload) != _ISOLATED_BUILD_RECEIPT_FIELDS
        or payload.get("schema_version") != "dharma.sadhana.isolated_build.v1"
        or payload.get("release_sha") != release_sha
        or type(payload.get("build_uid")) is not int
        or type(payload.get("build_gid")) is not int
        or payload.get("build_uid", 0) <= 0
        or payload.get("build_gid", 0) <= 0
        or payload.get("no_new_privileges") is not True
        or payload.get("solo_cgroup_process") is not True
        or payload.get("build_process_dumpable") is not False
        or payload.get("runtime_max_seconds") != 1800
        or payload.get("tasks_max") != 256
        or payload.get("memory_max_bytes") != 4_294_967_296
        or payload.get("candidate_code_executed_as_root") is not False
        or payload.get("post_exit_build_uid_process_count") != 0
        or payload.get("commands")
        != [
            "uv-version",
            "git-clone",
            "git-checkout",
            "git-origin",
            "uv-venv",
            "uv-sync",
            "npm-ci",
            "next-build",
            "venv-python-version",
            "git-verify-checkout",
            "git-verify-tracked",
            "git-metadata-removed",
        ]
    ):
        raise ReleaseContractError("durable isolated build receipt differs")
    for field in ("manifest_sha256", "build_driver_sha256"):
        _require_hash(payload.get(field), field)
    return dict(payload)


def _verify_frozen_release_tree(
    root: Path,
    *,
    expected_uid: int,
    expected_gid: int,
) -> None:
    if root.is_symlink() or not root.is_dir() or (root / ".git").exists():
        raise ReleaseContractError("staged release is not a frozen gitless tree")
    for directory, names, files in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        identity = directory_path.lstat()
        if (
            directory_path.is_symlink()
            or not stat.S_ISDIR(identity.st_mode)
            or identity.st_uid != expected_uid
            or identity.st_gid != expected_gid
            or stat.S_IMODE(identity.st_mode) != 0o555
        ):
            raise ReleaseContractError("staged release directory custody differs")
        for name in names + files:
            candidate = directory_path / name
            item = candidate.lstat()
            if stat.S_ISLNK(item.st_mode):
                if item.st_uid != expected_uid or item.st_gid != expected_gid:
                    raise ReleaseContractError("staged release link custody differs")
                continue
            if stat.S_ISDIR(item.st_mode):
                continue
            if (
                not stat.S_ISREG(item.st_mode)
                or item.st_uid != expected_uid
                or item.st_gid != expected_gid
                or item.st_nlink != 1
                or stat.S_IMODE(item.st_mode) not in {0o444, 0o555}
            ):
                raise ReleaseContractError("staged release file custody differs")


def _staged_release_admission_payload(
    *,
    release_sha: str,
    release_path: Path,
    tracked_source: Mapping[str, Any],
    tracked_source_raw: bytes,
    build_receipt_raw: bytes,
    release_input_set_digest: str,
) -> dict[str, Any]:
    _require_hash(release_input_set_digest, "release_input_set_digest")
    payload: dict[str, Any] = {
        "schema_version": STAGED_RELEASE_ADMISSION_SCHEMA_VERSION,
        "release_sha": release_sha,
        "release_root": str(release_path.resolve(strict=True)),
        "tracked_source_manifest_digest": tracked_source["manifest_digest"],
        "tracked_source_manifest_sha256": hashlib.sha256(
            tracked_source_raw
        ).hexdigest(),
        "tracked_entry_count": tracked_source["tracked_entry_count"],
        "tracked_bytes": tracked_source["tracked_bytes"],
        "isolated_build_receipt_sha256": hashlib.sha256(
            build_receipt_raw
        ).hexdigest(),
        "release_input_set_digest": release_input_set_digest,
        "git_metadata_present": False,
        "frozen_tree": True,
        "candidate_code_executed_as_root": False,
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _canonical_newline_self_digest(
        payload,
        "receipt_digest",
    )
    if set(payload) != _STAGED_RELEASE_ADMISSION_FIELDS:
        raise ReleaseContractError("staged release admission fields differ")
    return payload


def _project_staged_release_admission(
    raw: bytes,
    *,
    account: pwd.struct_passwd,
    projection_path: Path = PREPARED_RELEASE_ADMISSION_PROJECTION,
) -> None:
    _ensure_private_directory(
        projection_path.parent,
        uid=account.pw_uid,
        gid=account.pw_gid,
    )
    _publish_or_replay_exact_bytes(
        projection_path,
        raw,
        expected_uid=account.pw_uid,
        expected_gid=account.pw_gid,
    )


def _persist_staged_release_evidence(
    *,
    release_sha: str,
    tracked_source: Mapping[str, Any],
    build_receipt: Mapping[str, Any],
    receipt_root: Path,
    expected_root_uid: int,
    expected_root_gid: int,
) -> tuple[dict[str, Any], bytes, dict[str, Any], bytes]:
    tracked = validate_tracked_source_manifest(tracked_source)
    build = _validate_isolated_build_receipt(build_receipt, release_sha=release_sha)
    release_receipt_root, ledger_path, build_path, _admission_path = (
        _staged_release_receipt_paths(release_sha, receipt_root=receipt_root)
    )
    _ensure_private_directory(
        receipt_root,
        uid=expected_root_uid,
        gid=expected_root_gid,
    )
    _ensure_private_directory(
        release_receipt_root,
        uid=expected_root_uid,
        gid=expected_root_gid,
    )
    tracked_raw = _canonical_bytes(tracked) + b"\n"
    build_raw = _canonical_bytes(build) + b"\n"
    _publish_or_replay_exact_bytes(
        ledger_path,
        tracked_raw,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )
    _publish_or_replay_exact_bytes(
        build_path,
        build_raw,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )
    return tracked, tracked_raw, build, build_raw


def publish_staged_release_admission(
    *,
    release_sha: str,
    release_path: Path,
    tracked_source: Mapping[str, Any],
    build_receipt: Mapping[str, Any],
    release_input_set_digest: str,
    account: pwd.struct_passwd,
    receipt_root: Path = RELEASE_RECEIPT_ROOT,
    projection_path: Path = PREPARED_RELEASE_ADMISSION_PROJECTION,
    project_for_preparation: bool = True,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Persist Git-independent build evidence, then publish admission last."""
    tracked, tracked_raw, _build, build_raw = _persist_staged_release_evidence(
        release_sha=release_sha,
        tracked_source=tracked_source,
        build_receipt=build_receipt,
        receipt_root=receipt_root,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    _release_receipt_root, _ledger_path, _build_path, admission_path = (
        _staged_release_receipt_paths(release_sha, receipt_root=receipt_root)
    )
    _verify_frozen_release_tree(
        release_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )
    verify_tracked_source_tree(
        release_path,
        tracked,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )
    payload = _staged_release_admission_payload(
        release_sha=release_sha,
        release_path=release_path,
        tracked_source=tracked,
        tracked_source_raw=tracked_raw,
        build_receipt_raw=build_raw,
        release_input_set_digest=release_input_set_digest,
    )
    admitted = _publish_or_replay_private_receipt(
        admission_path,
        payload,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )
    admission_raw = _canonical_bytes(admitted) + b"\n"
    if project_for_preparation:
        _project_staged_release_admission(
            admission_raw,
            account=account,
            projection_path=projection_path,
        )
    return admitted


def verify_staged_release_admission(
    *,
    release_sha: str,
    release_path: Path,
    expected_release_input_set_digest: str,
    account: pwd.struct_passwd,
    receipt_root: Path = RELEASE_RECEIPT_ROOT,
    projection_path: Path = PREPARED_RELEASE_ADMISSION_PROJECTION,
    require_projection: bool = True,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> dict[str, Any]:
    """Reprove a staged release without Git, bundle parsing, or code execution."""
    release_receipt_root, ledger_path, build_path, admission_path = (
        _staged_release_receipt_paths(release_sha, receipt_root=receipt_root)
    )
    del release_receipt_root
    admission, admission_raw, _identity = _read_exact_custodied_json(
        admission_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )
    if (
        set(admission) != _STAGED_RELEASE_ADMISSION_FIELDS
        or admission.get("schema_version")
        != STAGED_RELEASE_ADMISSION_SCHEMA_VERSION
        or admission.get("release_sha") != release_sha
        or admission.get("release_root") != str(release_path.resolve(strict=True))
        or admission.get("release_input_set_digest")
        != expected_release_input_set_digest
        or admission.get("git_metadata_present") is not False
        or admission.get("frozen_tree") is not True
        or admission.get("candidate_code_executed_as_root") is not False
        or admission.get("receipt_digest")
        != _canonical_newline_self_digest(admission, "receipt_digest")
    ):
        raise ReleaseContractError("staged release admission binding differs")
    ledger, ledger_raw, _ledger_identity = _read_exact_custodied_json(
        ledger_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )
    tracked = validate_tracked_source_manifest(ledger)
    build, build_raw, _build_identity = _read_exact_custodied_json(
        build_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )
    _validate_isolated_build_receipt(build, release_sha=release_sha)
    if (
        admission.get("tracked_source_manifest_digest")
        != tracked["manifest_digest"]
        or admission.get("tracked_source_manifest_sha256")
        != hashlib.sha256(ledger_raw).hexdigest()
        or admission.get("tracked_entry_count") != tracked["tracked_entry_count"]
        or admission.get("tracked_bytes") != tracked["tracked_bytes"]
        or admission.get("isolated_build_receipt_sha256")
        != hashlib.sha256(build_raw).hexdigest()
    ):
        raise ReleaseContractError("staged release evidence ledger differs")
    _verify_frozen_release_tree(
        release_path,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )
    verify_tracked_source_tree(
        release_path,
        tracked,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
    )
    if require_projection:
        projection_raw, _projection_identity = _read_exact_custodied_bytes(
            projection_path,
            expected_uid=account.pw_uid,
            expected_gid=account.pw_gid,
        )
        if projection_raw != admission_raw:
            raise ReleaseContractError("service release admission projection differs")
    return admission


def _install_rendered_release_units(
    *,
    target: Path,
    release_sha: str,
    role: str,
    unit_root: Path,
) -> None:
    rendered_root = Path(tempfile.mkdtemp(prefix="sadhana-units-"))
    try:
        rendered = render_units(target, release_sha, rendered_root)
        admitted_units = set(CAMPAIGN_UNITS if role == "writer" else STANDBY_UNITS)
        for source in rendered:
            if source.name not in admitted_units:
                continue
            destination = unit_root / source.name
            temporary = unit_root / f".{source.name}.new"
            shutil.copyfile(source, temporary)
            os.chmod(temporary, 0o644)
            os.replace(temporary, destination)
    finally:
        shutil.rmtree(rendered_root)


def _start_runtime_preparation_unit(
    *,
    release_sha: str,
    account: pwd.struct_passwd,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """Run and root-verify the never-enabled NoEffect preparation oneshot."""
    if not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("runtime preparation release SHA differs")
    if (
        RUNTIME_BINDING_RECEIPT_TARGET.exists()
        or RUNTIME_BINDING_RECEIPT_TARGET.is_symlink()
    ):
        verify_runtime_binding_activation(
            account=account,
            expected_release_sha=release_sha,
        )
        return
    if (
        WRITER_MARKER.exists()
        or WRITER_MARKER.is_symlink()
        or DISPATCH_ENABLE_MARKER.exists()
        or DISPATCH_ENABLE_MARKER.is_symlink()
    ):
        raise ReleaseContractError("runtime preparation found preexisting authority")
    reloaded = runner(
        (SYSTEMCTL_PATH, "daemon-reload"),
        cwd=Path("/"),
        check=False,
    )
    if reloaded.returncode != 0 or reloaded.stdout or reloaded.stderr:
        raise ReleaseContractError("runtime preparation systemd reload failed")
    if not _unit_static(RUNTIME_PREPARATION_UNIT, runner=runner):
        raise ReleaseContractError("runtime preparation unit is enableable")
    started = runner(
        (SYSTEMCTL_PATH, "start", RUNTIME_PREPARATION_UNIT),
        cwd=Path("/"),
        check=False,
    )
    if started.returncode != 0 or started.stdout or started.stderr:
        raise ReleaseContractError("runtime preparation unit failed")
    if (
        not _unit_active(RUNTIME_PREPARATION_UNIT, runner=runner)
        or not _unit_static(RUNTIME_PREPARATION_UNIT, runner=runner)
    ):
        raise ReleaseContractError("runtime preparation unit did not remain successful")
    _validate_root_preparation(
        release_sha=release_sha,
        account=account,
        preparation_receipt_path=RUNTIME_PREPARATION_RECEIPT,
        prepared_root=PREPARED_RUNTIME_MANIFEST_ROOT,
        release_receipt_root=RELEASE_RECEIPT_ROOT,
        release_admission_projection=PREPARED_RELEASE_ADMISSION_PROJECTION,
        supervisor_env_path=Path(ENV_FILES[0]),
        expected_root_uid=0,
        expected_root_gid=0,
    )


def _finalize_staged_candidate_host(
    *,
    target: Path,
    release_sha: str,
    role: str,
    unit_root: Path,
    account: pwd.struct_passwd,
    standby_public_key: str | None,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """Install inert host surfaces, then atomically close the role-specific edge."""
    if role == "standby":
        if standby_public_key is None:
            raise ReleaseContractError("standby replication route was not pre-admitted")
    elif role == "writer":
        if standby_public_key is not None:
            raise ReleaseContractError("writer cannot receive a standby replication route")
    else:
        raise ReleaseContractError("role must be writer or standby")
    _install_rendered_release_units(
        target=target,
        release_sha=release_sha,
        role=role,
        unit_root=unit_root,
    )
    if role == "standby":
        _install_restricted_standby_key(
            standby_public_key,
            role=role,
            account=account,
        )
    else:
        _start_runtime_preparation_unit(
            release_sha=release_sha,
            account=account,
            runner=runner,
        )


def stage_candidate(
    manifest: Mapping[str, Any],
    *,
    bundle_path: Path,
    receipt_path: Path,
    uv_wheel_path: Path,
    input_set_manifest_path: Path | None,
    input_set_archive_path: Path | None,
    tracked_source_manifest_path: Path,
    role: str,
    release_root: Path = Path(RELEASE_ROOT),
    unit_root: Path = SYSTEMD_OUTPUT_ROOT,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    observed_node: str | None = None,
) -> Path:
    """Stage a new immutable exact-SHA release; never replace an existing one."""
    if os.geteuid() != 0:
        raise ReleaseContractError("candidate staging requires root")
    validate_manifest(manifest, for_activation=True)
    if role not in {"writer", "standby"}:
        raise ReleaseContractError("role must be writer or standby")
    _require_host_role(role, observed_node=observed_node)
    if release_root != Path(RELEASE_ROOT) or unit_root != SYSTEMD_OUTPUT_ROOT:
        raise ReleaseContractError("candidate host roots must remain exact")
    if (
        bundle_path.name != manifest["bundle_file"]
        or sha256_file(bundle_path) != manifest["bundle_sha256"]
    ):
        raise ReleaseContractError("candidate bundle differs from manifest")
    if (
        receipt_path.name != manifest["closeout_receipt_file"]
        or sha256_file(receipt_path, max_bytes=_MAX_JSON_BYTES)
        != manifest["closeout_receipt_sha256"]
    ):
        raise ReleaseContractError("candidate closeout receipt differs from manifest")
    if (
        uv_wheel_path.name != manifest["uv_wheel_file"]
        or sha256_file(uv_wheel_path, max_bytes=_MAX_UV_WHEEL_BYTES)
        != manifest["uv_wheel_sha256"]
    ):
        raise ReleaseContractError("candidate uv wheel differs from manifest")
    if (
        tracked_source_manifest_path.name
        != manifest["tracked_source_manifest_file"]
        or sha256_file(
            tracked_source_manifest_path,
            max_bytes=_MAX_TRACKED_SOURCE_MANIFEST_BYTES,
        )
        != manifest["tracked_source_manifest_sha256"]
    ):
        raise ReleaseContractError("candidate tracked source manifest differs")
    tracked_source = validate_tracked_source_manifest(
        _secure_json(tracked_source_manifest_path, require_private=True)
    )
    if (
        tracked_source["release_sha"] != manifest["release_sha"]
        or tracked_source["manifest_digest"] != manifest["tracked_source_digest"]
        or tracked_source["tracked_entry_count"]
        != manifest["tracked_source_entry_count"]
    ):
        raise ReleaseContractError("candidate tracked source binding differs")
    if role == "writer" and (
        input_set_manifest_path is None or input_set_archive_path is None
    ):
        raise ReleaseContractError("writer staging requires the immutable input set")
    if (input_set_manifest_path is None) != (input_set_archive_path is None):
        raise ReleaseContractError("candidate input-set artifacts are partial")
    if role == "standby" and input_set_manifest_path is not None:
        raise ReleaseContractError("standby cannot receive Mac-private campaign inputs")
    input_payload: dict[str, Any] | None = None
    if input_set_manifest_path is not None and input_set_archive_path is not None:
        if (
            input_set_manifest_path.name != manifest["input_set_manifest_file"]
            or input_set_archive_path.name != manifest["input_set_archive_file"]
            or sha256_file(input_set_manifest_path, max_bytes=_MAX_JSON_BYTES)
            != manifest["input_set_manifest_sha256"]
            or sha256_file(input_set_archive_path, max_bytes=_MAX_INPUT_SET_BYTES)
            != manifest["input_set_archive_sha256"]
        ):
            raise ReleaseContractError("candidate input-set release artifacts differ")
        input_payload = validate_input_set_manifest(
            _secure_json(input_set_manifest_path, require_private=True)
        )
        if input_payload["input_set_digest"] != manifest["input_set_digest"]:
            raise ReleaseContractError(
                "candidate input-set digest differs from release manifest"
            )
        # Close and rehash every member before any host mutation.  Installation
        # repeats this check immediately before custody changes.
        validate_input_set_archive(input_payload, input_set_archive_path)
    receipt = _secure_json(receipt_path, require_private=False)
    if (
        receipt.get("status") != "passed"
        or receipt.get("phase") != "closeout"
        or receipt.get("packet_digest") != manifest["work_packet_digest"]
        or receipt.get("packet_bytes_sha256") != manifest["work_packet_sha256"]
        or receipt.get("target_head") != manifest["release_sha"]
    ):
        raise ReleaseContractError("candidate closeout receipt is not bound and passed")
    account = _require_static_service_identity()
    build_account = _require_build_identity(service_account=account)
    marker_exists = _validate_existing_writer_marker()
    if role == "writer" and marker_exists:
        raise ReleaseContractError(
            "writer activation marker already exists before governed binding"
        )
    if role == "standby" and marker_exists:
        raise ReleaseContractError("standby host already carries writer marker")
    _require_existing_root_directory(unit_root)
    standby_public_key: str | None = None
    if role == "standby":
        # Admit the complete root-custodied key and destination/tool contract
        # before the first deployment mutation. Publication occurs only after
        # the inert release and units have staged successfully.
        standby_public_key = _read_standby_public_key()
        _validate_restricted_standby_key_destination(
            standby_public_key,
            role=role,
            account=account,
        )
        conflicting = [
            str(unit_root / name)
            for name in CAMPAIGN_UNITS
            if (unit_root / name).exists() and not (unit_root / name).is_symlink()
        ]
        if conflicting:
            raise ReleaseContractError(
                f"standby has unfenced regular campaign units: {conflicting}"
            )
    target = release_root / manifest["release_sha"]
    if input_payload is not None:
        if input_set_manifest_path is None or input_set_archive_path is None:
            raise ReleaseContractError(
                "writer input-set paths were lost after admission"
            )
        install_input_set(
            manifest_path=input_set_manifest_path,
            archive_path=input_set_archive_path,
            account=account,
            observed_node=observed_node,
        )
    if target.is_symlink():
        raise ReleaseContractError("exact release target is a symlink")
    if target.exists():
        _release_receipt_root, ledger_path, build_path, _admission_path = (
            _staged_release_receipt_paths(manifest["release_sha"])
        )
        durable_tracked, _ledger_raw, _ledger_identity = (
            _read_exact_custodied_json(
                ledger_path,
                expected_uid=0,
                expected_gid=0,
            )
        )
        durable_build, _build_raw, _build_identity = _read_exact_custodied_json(
            build_path,
            expected_uid=0,
            expected_gid=0,
        )
        if durable_tracked != tracked_source:
            raise ReleaseContractError("durable tracked-source ledger conflicts")
        admission = publish_staged_release_admission(
            release_sha=manifest["release_sha"],
            release_path=target,
            tracked_source=durable_tracked,
            build_receipt=durable_build,
            release_input_set_digest=manifest["input_set_digest"],
            account=account,
            project_for_preparation=role == "writer",
        )
        if role == "writer":
            if input_payload is None:
                raise ReleaseContractError("writer preparation input set is absent")
            _publish_runtime_preparation_environment(
                input_payload,
                admission=admission,
                release_sha=manifest["release_sha"],
                release_path=target,
                account=account,
            )
        verify_staged_release_admission(
            release_sha=manifest["release_sha"],
            release_path=target,
            expected_release_input_set_digest=manifest["input_set_digest"],
            account=account,
            require_projection=role == "writer",
        )
        _finalize_staged_candidate_host(
            target=target,
            release_sha=manifest["release_sha"],
            role=role,
            unit_root=unit_root,
            account=account,
            standby_public_key=standby_public_key,
            runner=runner,
        )
        return target
    uv_binary = provision_pinned_uv(
        uv_wheel_path,
        runner=runner,
        execution_uid=build_account.pw_uid,
        execution_gid=build_account.pw_gid,
        execute_version=True,
    )
    build_driver = _install_exact_build_driver(
        release_sha=manifest["release_sha"],
    )
    build_manifest_raw = _canonical_bytes(dict(manifest)) + b"\n"
    expected_manifest_sha256 = hashlib.sha256(build_manifest_raw).hexdigest()
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=release_root))
    try:
        build_home = staging / "build-home"
        uv_cache = staging / "uv-cache"
        npm_cache = staging / "npm-cache"
        for private_root in (build_home, uv_cache, npm_cache):
            private_root.mkdir(mode=0o700)
            os.chown(private_root, build_account.pw_uid, build_account.pw_gid)
            os.chmod(private_root, 0o700)
        build_bundle = staging / "candidate.bundle"
        shutil.copyfile(bundle_path, build_bundle)
        os.chown(build_bundle, build_account.pw_uid, build_account.pw_gid)
        os.chmod(build_bundle, 0o400)
        build_manifest = staging / "release-manifest.json"
        _atomic_private_bytes(
            build_manifest,
            build_manifest_raw,
            uid=build_account.pw_uid,
            gid=build_account.pw_gid,
        )
        os.chmod(build_manifest, 0o400)
        # Root creates and binds every exact input under a root-custodied parent.
        # Parent-directory authority transfers only after the final write; from
        # here until the post-process fchown barrier, root must not path-read a
        # candidate-controlled leaf.
        os.chown(staging, build_account.pw_uid, build_account.pw_gid)
        os.chmod(staging, 0o700)
        build_receipt = _invoke_isolated_build_plan(
            staging=staging,
            build_account=build_account,
            uv_binary=uv_binary,
            build_driver=build_driver,
            manifest_path=build_manifest,
            expected_manifest_sha256=expected_manifest_sha256,
            release_sha=manifest["release_sha"],
            runner=runner,
        )
        # Retire the build identity's parent-directory authority before root
        # reads, freezes, or promotes any candidate pathname.
        _retake_build_staging_custody(
            staging,
            build_uid=build_account.pw_uid,
            build_gid=build_account.pw_gid,
        )
        _admit_build_manifest_after_custody_barrier(
            build_manifest,
            expected_raw=build_manifest_raw,
            expected_sha256=expected_manifest_sha256,
            build_uid=build_account.pw_uid,
            build_gid=build_account.pw_gid,
        )
        repo = staging / "repo"
        _freeze_release_tree(
            repo,
            build_uid=build_account.pw_uid,
            build_gid=build_account.pw_gid,
            build_processes_proven_absent=True,
        )
        verify_tracked_source_tree(repo, tracked_source)
        verify_dashboard_build(repo / "dashboard")
        verify_venv(
            repo / ".venv",
            expected_uid=0,
            execute_version=False,
        )
        _persist_staged_release_evidence(
            release_sha=manifest["release_sha"],
            tracked_source=tracked_source,
            build_receipt=build_receipt,
            receipt_root=RELEASE_RECEIPT_ROOT,
            expected_root_uid=0,
            expected_root_gid=0,
        )
        source_identity = repo.lstat()
        staging_descriptor = os.open(
            staging,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
        )
        release_descriptor = os.open(
            release_root,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            _rename_noreplace_at(
                staging_descriptor,
                repo.name,
                release_descriptor,
                target.name,
            )
            promoted = os.stat(
                target.name,
                dir_fd=release_descriptor,
                follow_symlinks=False,
            )
            if (promoted.st_dev, promoted.st_ino) != (
                source_identity.st_dev,
                source_identity.st_ino,
            ):
                raise ReleaseContractError("promoted release inode differs")
            os.fsync(release_descriptor)
            os.fsync(staging_descriptor)
        finally:
            os.close(release_descriptor)
            os.close(staging_descriptor)
    finally:
        _cleanup_build_staging(
            staging,
            build_uid=build_account.pw_uid,
            build_gid=build_account.pw_gid,
        )
    admission = publish_staged_release_admission(
        release_sha=manifest["release_sha"],
        release_path=target,
        tracked_source=tracked_source,
        build_receipt=build_receipt,
        release_input_set_digest=manifest["input_set_digest"],
        account=account,
        project_for_preparation=role == "writer",
    )
    if role == "writer":
        if input_payload is None:
            raise ReleaseContractError("writer preparation input set is absent")
        _publish_runtime_preparation_environment(
            input_payload,
            admission=admission,
            release_sha=manifest["release_sha"],
            release_path=target,
            account=account,
        )
    verify_staged_release_admission(
        release_sha=manifest["release_sha"],
        release_path=target,
        expected_release_input_set_digest=manifest["input_set_digest"],
        account=account,
        require_projection=role == "writer",
    )
    _finalize_staged_candidate_host(
        target=target,
        release_sha=manifest["release_sha"],
        role=role,
        unit_root=unit_root,
        account=account,
        standby_public_key=standby_public_key,
        runner=runner,
    )
    return target


def _manifest_payload(
    *,
    release_sha: str,
    integration_base_sha: str,
    bundle_file: str,
    bundle_sha256: str,
    work_packet_path: str,
    work_packet_sha256: str,
    work_packet_digest: str,
    receipt_file: str,
    receipt_sha256: str,
    input_set_manifest_sha256: str,
    input_set_archive_sha256: str,
    input_set_digest: str,
    deployment_known_hosts_sha256: str,
    tracked_source_manifest_sha256: str,
    tracked_source_digest: str,
    tracked_source_entry_count: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "mission_id": MISSION_ID,
        "campaign_start_utc": CAMPAIGN_START_UTC,
        "campaign_stop_utc": CAMPAIGN_STOP_UTC,
        "cash_budget_usd": 0,
        "release_class": RELEASE_CLASS,
        "canonical_or_merged": False,
        "release_sha": release_sha,
        "canonical_origin": CANONICAL_ORIGIN,
        "accepted_base_sha": ACCEPTED_BASE_SHA,
        "integration_base_sha": integration_base_sha,
        "bundle_file": bundle_file,
        "bundle_sha256": bundle_sha256,
        "work_packet_path": work_packet_path,
        "work_packet_sha256": work_packet_sha256,
        "work_packet_digest": work_packet_digest,
        "closeout_receipt_file": receipt_file,
        "closeout_receipt_sha256": receipt_sha256,
        "writer_node": WRITER_NODE,
        "standby_node": STANDBY_NODE,
        "api_listen": API_LISTEN,
        "dashboard_listen": DASHBOARD_LISTEN,
        "tailscale_exposure": TAILSCALE_EXPOSURE,
        "automatic_failover": False,
        "standby_writer_enabled": False,
        "python_version": "3.12",
        "venv_copies": True,
        "release_root": RELEASE_ROOT,
        "state_root": STATE_ROOT,
        "workspace_root": WORKSPACE_ROOT,
        "api_state_root": API_STATE_ROOT,
        "snapshot_root": SNAPSHOT_ROOT,
        "env_files": list(ENV_FILES),
        "uv_version": UV_VERSION,
        "uv_wheel_file": UV_WHEEL_FILE,
        "uv_wheel_sha256": UV_WHEEL_SHA256,
        "input_set_manifest_file": INPUT_SET_MANIFEST_FILE,
        "input_set_manifest_sha256": input_set_manifest_sha256,
        "input_set_archive_file": INPUT_SET_ARCHIVE_FILE,
        "input_set_archive_sha256": input_set_archive_sha256,
        "input_set_digest": input_set_digest,
        "deployment_known_hosts_file": DEPLOYMENT_KNOWN_HOSTS_FILE,
        "deployment_known_hosts_sha256": deployment_known_hosts_sha256,
        "tracked_source_manifest_file": TRACKED_SOURCE_MANIFEST_FILE,
        "tracked_source_manifest_sha256": tracked_source_manifest_sha256,
        "tracked_source_digest": tracked_source_digest,
        "tracked_source_entry_count": tracked_source_entry_count,
        "manifest_digest": "1" * 64,
    }
    payload["manifest_digest"] = manifest_digest(payload)
    return validate_manifest(payload)


def seal_envelope(
    *,
    repo_root: Path,
    integration_base_sha: str,
    work_packet_path: str,
    closeout_receipt: Path,
    input_set_manifest: Path,
    input_set_source_root: Path,
    deployment_known_hosts: Path,
    output_root: Path,
    uv_wheel_source: Path | None = None,
) -> tuple[Path, Path, Path, Path, Path, Path, Path, Path]:
    """Create a full Git bundle and exact external evidence envelope."""
    repo = repo_root.resolve(strict=True)
    release_sha = _git(repo, "rev-parse", "HEAD")
    if not _COMMIT_RE.fullmatch(release_sha):
        raise ReleaseContractError("repository HEAD is not an exact commit")
    if not _COMMIT_RE.fullmatch(integration_base_sha):
        raise ReleaseContractError("integration base is not an exact commit")
    if _git(repo, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ReleaseContractError("release checkout must be clean before sealing")
    if _git(repo, "remote", "get-url", "origin") != CANONICAL_ORIGIN:
        raise ReleaseContractError("release checkout origin is not canonical")
    parents = _git(repo, "rev-list", "--parents", "-n", "1", release_sha).split()
    if parents != [release_sha, integration_base_sha]:
        raise ReleaseContractError(
            "release must be one commit whose sole parent is integration base"
        )
    ancestry = _run(
        (GIT_PATH, "merge-base", "--is-ancestor", ACCEPTED_BASE_SHA, release_sha),
        cwd=repo,
        check=False,
    )
    if ancestry.returncode:
        raise ReleaseContractError("release checkout lacks accepted base ancestry")
    if not _PACKET_PATH_RE.fullmatch(work_packet_path):
        raise ReleaseContractError("work packet path is not a tracked canonical path")
    packet_path = repo / work_packet_path
    packet = _secure_json(packet_path, require_private=False)
    entry = packet.get("session_entry")
    if not isinstance(entry, dict):
        raise ReleaseContractError("work packet has no Session Entry")
    packet_digest = _require_hash(entry.get("packet_digest"), "work_packet_digest")
    receipt_source = closeout_receipt.expanduser()
    if not receipt_source.is_absolute():
        raise ReleaseContractError("closeout receipt path must be absolute")
    receipt = _secure_json(receipt_source, require_private=False)
    if (
        receipt.get("status") != "passed"
        or receipt.get("phase") != "closeout"
        or receipt.get("packet_digest") != packet_digest
        or receipt.get("packet_bytes_sha256")
        != sha256_file(packet_path, max_bytes=_MAX_JSON_BYTES)
        or receipt.get("target_head") != release_sha
    ):
        raise ReleaseContractError("closeout receipt does not accept the work packet")
    input_manifest_source = input_set_manifest.expanduser()
    if not input_manifest_source.is_absolute():
        raise ReleaseContractError("input-set manifest path must be absolute")
    input_payload = validate_input_set_manifest(
        _secure_json(input_manifest_source, require_private=True)
    )
    # Validate the full source set before creating any release-envelope bytes.
    validate_input_set_sources(input_payload, input_set_source_root)
    scan_static_input_set(input_payload, source_root=input_set_source_root)
    deployment_known_hosts_bytes = _read_deployment_known_hosts(deployment_known_hosts)
    if (
        hashlib.sha256(deployment_known_hosts_bytes).hexdigest()
        != DEPLOYMENT_KNOWN_HOSTS_SHA256
    ):
        raise ReleaseContractError("deployment known_hosts differs from accepted bytes")
    tracked_source_payload = render_tracked_source_manifest(repo, release_sha)
    if not output_root.is_absolute():
        raise ReleaseContractError("release envelope output must be absolute")
    if output_root.is_symlink():
        raise ReleaseContractError("release envelope output cannot be a symlink")
    output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    _require_secure_parent_chain(output_root / ".custody-check")
    output_identity = output_root.lstat()
    if (
        not stat.S_ISDIR(output_identity.st_mode)
        or output_identity.st_uid != os.geteuid()
        or stat.S_IMODE(output_identity.st_mode) != 0o700
    ):
        raise ReleaseContractError("release envelope output lacks private custody")
    bundle = output_root / f"dharma-sadhana-{release_sha}.bundle"
    receipt_copy = output_root / "agentops-closeout-receipt.json"
    manifest_path = output_root / "release-manifest.json"
    uv_wheel = output_root / UV_WHEEL_FILE
    input_manifest_copy = output_root / INPUT_SET_MANIFEST_FILE
    input_archive = output_root / INPUT_SET_ARCHIVE_FILE
    deployment_known_hosts_copy = output_root / DEPLOYMENT_KNOWN_HOSTS_FILE
    tracked_source_manifest_copy = output_root / TRACKED_SOURCE_MANIFEST_FILE
    if any(
        path.exists() or path.is_symlink()
        for path in (
            bundle,
            receipt_copy,
            manifest_path,
            uv_wheel,
            input_manifest_copy,
            input_archive,
            deployment_known_hosts_copy,
            tracked_source_manifest_copy,
        )
    ):
        raise ReleaseContractError("release envelope output already exists")
    input_manifest_identity = input_manifest_source.lstat()
    input_manifest_bytes = _read_input_source(
        input_manifest_source,
        expected_bytes=input_manifest_identity.st_size,
    )
    _atomic_private_bytes(
        input_manifest_copy,
        input_manifest_bytes,
        uid=os.geteuid(),
        gid=os.getegid(),
    )
    build_input_set_archive(
        input_payload,
        source_root=input_set_source_root,
        destination=input_archive,
    )
    _atomic_private_bytes(
        deployment_known_hosts_copy,
        deployment_known_hosts_bytes,
        uid=os.geteuid(),
        gid=os.getegid(),
    )
    _atomic_private_bytes(
        tracked_source_manifest_copy,
        _canonical_bytes(tracked_source_payload) + b"\n",
        uid=os.geteuid(),
        gid=os.getegid(),
    )
    _materialize_uv_wheel(uv_wheel, uv_wheel_source)
    _run((GIT_PATH, "bundle", "create", str(bundle), "HEAD"), cwd=repo)
    os.chmod(bundle, 0o600)
    if _git(repo, "rev-parse", "HEAD") != release_sha or _git(
        repo, "status", "--porcelain=v1", "--untracked-files=all"
    ):
        raise ReleaseContractError("release checkout changed while bundling")
    verified_bundle = _run((GIT_PATH, "bundle", "verify", str(bundle)), cwd=repo)
    if release_sha not in (verified_bundle.stdout + verified_bundle.stderr):
        raise ReleaseContractError("bundle does not advertise the exact release SHA")
    source_identity = receipt_source.lstat()
    source_descriptor = os.open(receipt_source, os.O_RDONLY | os.O_NOFOLLOW)
    destination_descriptor = os.open(
        receipt_copy, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
    )
    try:
        opened_source = os.fstat(source_descriptor)
        if (opened_source.st_dev, opened_source.st_ino) != (
            source_identity.st_dev,
            source_identity.st_ino,
        ):
            raise ReleaseContractError("closeout receipt changed during copy")
        while True:
            chunk = os.read(source_descriptor, 65_536)
            if not chunk:
                break
            _write_all(destination_descriptor, chunk)
        os.fsync(destination_descriptor)
    finally:
        os.close(source_descriptor)
        os.close(destination_descriptor)
    os.chmod(receipt_copy, 0o600)
    copied_receipt = _secure_json(receipt_copy, require_private=True)
    if copied_receipt != receipt:
        raise ReleaseContractError("copied closeout receipt content differs")
    payload = _manifest_payload(
        release_sha=release_sha,
        integration_base_sha=integration_base_sha,
        bundle_file=bundle.name,
        bundle_sha256=sha256_file(bundle),
        work_packet_path=work_packet_path,
        work_packet_sha256=sha256_file(packet_path, max_bytes=_MAX_JSON_BYTES),
        work_packet_digest=packet_digest,
        receipt_file=receipt_copy.name,
        receipt_sha256=sha256_file(receipt_copy, max_bytes=_MAX_JSON_BYTES),
        input_set_manifest_sha256=sha256_file(
            input_manifest_copy,
            max_bytes=_MAX_JSON_BYTES,
        ),
        input_set_archive_sha256=sha256_file(
            input_archive,
            max_bytes=_MAX_INPUT_SET_BYTES,
        ),
        input_set_digest=input_payload["input_set_digest"],
        deployment_known_hosts_sha256=hashlib.sha256(
            deployment_known_hosts_bytes
        ).hexdigest(),
        tracked_source_manifest_sha256=sha256_file(
            tracked_source_manifest_copy,
            max_bytes=_MAX_TRACKED_SOURCE_MANIFEST_BYTES,
        ),
        tracked_source_digest=tracked_source_payload["manifest_digest"],
        tracked_source_entry_count=tracked_source_payload["tracked_entry_count"],
    )
    descriptor = os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        _write_all(descriptor, _canonical_bytes(payload) + b"\n")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return (
        manifest_path,
        bundle,
        receipt_copy,
        uv_wheel,
        input_manifest_copy,
        input_archive,
        deployment_known_hosts_copy,
        tracked_source_manifest_copy,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify", help="verify an exact release envelope")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument(
        "--repo",
        type=Path,
        help="optional clean source checkout for an additional local-source equality gate",
    )
    verify.add_argument("--bundle", type=Path, required=True)
    verify.add_argument("--receipt", type=Path, required=True)
    verify.add_argument("--uv-wheel", type=Path, required=True)
    verify.add_argument("--input-set-manifest", type=Path)
    verify.add_argument("--input-set-archive", type=Path)
    verify.add_argument("--deployment-known-hosts", type=Path, required=True)
    verify.add_argument("--tracked-source-manifest", type=Path, required=True)
    verify.add_argument("--role", choices=("writer", "standby"), required=True)
    render = commands.add_parser("render-units", help="render exact-SHA systemd units")
    render.add_argument("--repo", type=Path, required=True)
    render.add_argument("--release-sha", required=True)
    render.add_argument("--output", type=Path, required=True)
    input_manifest_parser = commands.add_parser(
        "render-static-input-manifest",
        help="render the closed pre-bootstrap campaign input manifest",
    )
    input_manifest_parser.add_argument("--source-root", type=Path, required=True)
    input_manifest_parser.add_argument("--output", type=Path, required=True)
    input_scan_parser = commands.add_parser(
        "scan-static-inputs",
        help="run pinned redacted gitleaks over only the closed static input set",
    )
    input_scan_parser.add_argument("--source-root", type=Path, required=True)
    seal = commands.add_parser("seal", help="create bundle plus evidence manifest")
    seal.add_argument("--repo", type=Path, required=True)
    seal.add_argument("--integration-base-sha", required=True)
    seal.add_argument("--work-packet", required=True)
    seal.add_argument("--closeout-receipt", type=Path, required=True)
    seal.add_argument("--input-set-manifest", type=Path, required=True)
    seal.add_argument("--input-set-source-root", type=Path, required=True)
    seal.add_argument("--deployment-known-hosts", type=Path, required=True)
    seal.add_argument("--output", type=Path, required=True)
    seal.add_argument("--uv-wheel-source", type=Path)
    deploy = commands.add_parser(
        "deploy", help="stage an immutable host role without activation"
    )
    deploy.add_argument("--manifest", type=Path, required=True)
    deploy.add_argument("--bundle", type=Path, required=True)
    deploy.add_argument("--receipt", type=Path, required=True)
    deploy.add_argument("--uv-wheel", type=Path, required=True)
    deploy.add_argument("--input-set-manifest", type=Path)
    deploy.add_argument("--input-set-archive", type=Path)
    deploy.add_argument("--tracked-source-manifest", type=Path, required=True)
    deploy.add_argument("--role", choices=("writer", "standby"), required=True)
    build_candidate = commands.add_parser(
        "build-candidate",
        help=argparse.SUPPRESS,
    )
    build_candidate.add_argument("--staging", type=Path, required=True)
    build_candidate.add_argument("--bundle", type=Path, required=True)
    build_candidate.add_argument("--manifest", type=Path, required=True)
    build_candidate.add_argument("--uv-binary", type=Path, required=True)
    build_candidate.add_argument("--release-sha", required=True)
    build_candidate.add_argument("--expected-uid", type=int, required=True)
    build_candidate.add_argument("--expected-gid", type=int, required=True)
    guard = commands.add_parser(
        "guard-start", help="reject process start outside the exact campaign timebox"
    )
    guard.add_argument("--role", choices=("writer", "standby"), required=True)
    binding_guard = commands.add_parser(
        "guard-runtime-binding",
        help="root-verify the exact three-manifest activation transaction",
    )
    binding_guard.add_argument("--role", choices=("writer",), required=True)
    publish_binding = commands.add_parser(
        "publish-runtime-binding",
        help="root-promote the exact no-effect preparation into runtime custody",
    )
    publish_binding.add_argument("--role", choices=("writer",), required=True)
    publish_binding.add_argument("--release-sha", required=True)
    activate_predispatch_parser = commands.add_parser(
        "activate-predispatch",
        help="start infrastructure-only services without provider dispatch",
    )
    activate_predispatch_parser.add_argument(
        "--role", choices=("writer",), required=True
    )
    activate_predispatch_parser.add_argument("--release-sha", required=True)
    refresh_predispatch_parser = commands.add_parser(
        "refresh-predispatch",
        help="refresh the paused no-provider projection before governed dispatch",
    )
    refresh_predispatch_parser.add_argument(
        "--role", choices=("writer",), required=True
    )
    refresh_predispatch_parser.add_argument("--release-sha", required=True)
    activate_standby_parser = commands.add_parser(
        "activate-standby",
        help="fence writer units and start the receipted append-only standby",
    )
    activate_standby_parser.add_argument(
        "--role", choices=("standby",), required=True
    )
    activate_standby_parser.add_argument("--release-sha", required=True)
    health_probe = commands.add_parser(
        "probe-observer-health",
        help="record twenty exact 18420 observer responses before dispatch",
    )
    health_probe.add_argument("--role", choices=("writer",), required=True)
    health_probe.add_argument("--release-sha", required=True)
    runtime_staging = commands.add_parser(
        "finalize-runtime-staging",
        help="validate all disabled runtime inputs and narrow their custody",
    )
    runtime_staging.add_argument("--role", choices=("writer",), required=True)
    runtime_staging.add_argument("--release-sha", required=True)
    dashboard_rollback = commands.add_parser(
        "probe-dashboard-rollback",
        help="exercise the owned dashboard and private-Serve rollback before dispatch",
    )
    dashboard_rollback.add_argument("--role", choices=("writer",), required=True)
    dashboard_rollback.add_argument("--release-sha", required=True)
    account_ui_confirmation = commands.add_parser(
        "record-account-ui-confirmation",
        help="consume only the fixed one-shot authenticated-account UI candidate",
    )
    account_ui_confirmation.add_argument(
        "--role", choices=("writer",), required=True
    )
    account_ui_confirmation.add_argument("--release-sha", required=True)
    dashboard_identity = commands.add_parser(
        "record-dashboard-identity",
        help="bind UDS isolation to the fixed authenticated-account UI receipt",
    )
    dashboard_identity.add_argument("--role", choices=("writer",), required=True)
    dashboard_identity.add_argument("--release-sha", required=True)
    credential_acceptance = commands.add_parser(
        "record-operator-credential",
        help="prove isolated equal bearer copies without exposing secret bytes",
    )
    credential_acceptance.add_argument("--role", choices=("writer",), required=True)
    credential_acceptance.add_argument("--release-sha", required=True)
    dispatch_enable = commands.add_parser(
        "enable-dispatch",
        help="create dispatch authority after every predispatch receipt passes",
    )
    dispatch_enable.add_argument("--role", choices=("writer",), required=True)
    dispatch_enable.add_argument("--release-sha", required=True)
    campaign_activation = commands.add_parser(
        "activate-campaign-session",
        help="apply or replay the typed seq2 resume after dispatch authority",
    )
    campaign_activation.add_argument(
        "--role", choices=("writer",), required=True
    )
    campaign_activation.add_argument("--release-sha", required=True)
    campaign_activation.add_argument(
        "--dispatch-activation-receipt", type=Path, required=True
    )
    campaign_activation.add_argument(
        "--dashboard-identity-receipt", type=Path, required=True
    )
    campaign_activation.add_argument(
        "--runtime-binding-receipt", type=Path, required=True
    )
    campaign_activation.add_argument(
        "--operator-login-file", type=Path, required=True
    )
    campaign_activation.add_argument(
        "--control-hmac-key-file", type=Path, required=True
    )
    campaign_activation.add_argument("--control-gate-path", type=Path, required=True)
    access_probe = commands.add_parser("probe-denied-access", help=argparse.SUPPRESS)
    access_probe.add_argument("--kind", choices=("file", "unix"), required=True)
    access_probe.add_argument("--path", type=Path, required=True)
    standby_capacity = commands.add_parser(
        "emit-standby-capacity-proof",
        help="read-only AGNI proof for the complete immutable snapshot series",
    )
    standby_capacity.add_argument("--role", choices=("standby",), required=True)
    standby_capacity.add_argument("--release-sha", required=True)
    standby_capacity.add_argument("--runtime-db-bytes", type=int, required=True)
    standby_capacity.add_argument("--tasks-db-bytes", type=int, required=True)
    standby_capacity.add_argument("--projection-bytes", type=int, required=True)
    standby_capacity.add_argument("--deployment-known-hosts-sha256", required=True)
    standby_capacity.add_argument(
        "--strict-host-key-channel", action="store_true", required=True
    )
    install_standby_capacity = commands.add_parser(
        "install-standby-capacity-proof",
        help="install the controller-captured canonical AGNI capacity proof",
    )
    install_standby_capacity.add_argument("--role", choices=("writer",), required=True)
    install_standby_capacity.add_argument("--release-sha", required=True)
    guard_standby_capacity_parser = commands.add_parser(
        "guard-standby-capacity",
        help="bind fresh AGNI capacity to exact disabled writer source sizes",
    )
    guard_standby_capacity_parser.add_argument(
        "--role", choices=("writer",), required=True
    )
    guard_standby_capacity_parser.add_argument("--release-sha", required=True)
    guard_standby_capacity_parser.add_argument(
        "--projection-path", type=Path, required=True
    )
    emergency_control = commands.add_parser(
        "apply-emergency-control",
        help="root-validate emergency inbox, stop target, then receipt",
    )
    emergency_control.add_argument("--role", choices=("writer",), required=True)
    emergency_control.add_argument("--hmac-key-file", type=Path, required=True)
    emergency_control.add_argument("--operator-login-file", type=Path, required=True)
    emergency_recovery = commands.add_parser(
        "resume-emergency-control",
        help="resume a persistent root emergency claim after failure",
    )
    emergency_recovery.add_argument("--role", choices=("writer",), required=True)
    emergency_recovery.add_argument("--hmac-key-file", type=Path, required=True)
    emergency_recovery.add_argument("--operator-login-file", type=Path, required=True)
    stop_guard = commands.add_parser(
        "guard-stop", help="admit stop enforcement only at or after the deadline"
    )
    stop_guard.add_argument("--role", choices=("writer", "standby"), required=True)
    persist_stop = commands.add_parser(
        "persist-stop", help="best-effort persist and receipt the post-cessation stop"
    )
    persist_stop.add_argument("--role", choices=("writer",), required=True)
    persist_stop.add_argument("--writer-lock-path", type=Path, required=True)
    persist_stop.add_argument("--projection-path", type=Path, required=True)
    standby_stop = commands.add_parser(
        "persist-standby-stop",
        help="receipt the disabled standby receiver at the exact deadline",
    )
    standby_stop.add_argument("--role", choices=("standby",), required=True)
    standby_stop.add_argument("--release-sha", required=True)
    rollback = commands.add_parser(
        "rollback",
        help="stop and disable only the exact release while retaining evidence",
    )
    rollback.add_argument("--role", choices=("writer",), required=True)
    rollback.add_argument("--release-sha", required=True)
    install_verifier = commands.add_parser(
        "install-verifier-env",
        help="atomically install the exact verifier assignment received on stdin",
    )
    install_verifier.add_argument("--role", choices=("writer",), required=True)
    install_control_credential = commands.add_parser(
        "install-control-credential",
        help="atomically install one named control credential received on stdin",
    )
    install_control_credential.add_argument(
        "--role", choices=("writer",), required=True
    )
    install_control_credential.add_argument(
        "--credential",
        choices=tuple(CONTROL_CREDENTIAL_DESTINATIONS),
        required=True,
    )
    prepare_host_parser = commands.add_parser(
        "prepare-host",
        help="create only the static service identity and campaign roots",
    )
    prepare_host_parser.add_argument(
        "--role", choices=("writer", "standby"), required=True
    )
    prepare_control_parser = commands.add_parser(
        "prepare-control-runtime",
        help="create the volatile asymmetric operator-control inbox roots",
    )
    prepare_control_parser.add_argument("--role", choices=("writer",), required=True)
    prepare_dashboard_parser = commands.add_parser(
        "prepare-dashboard-runtime",
        help="prepare the exclusive dashboard Unix-socket directory",
    )
    prepare_dashboard_parser.add_argument("--role", choices=("writer",), required=True)
    sync_observer_parser = commands.add_parser(
        "sync-observer-projection",
        help="copy validated derived bytes into the isolated observer root",
    )
    sync_observer_parser.add_argument("--role", choices=("writer",), required=True)
    clock_proof_parser = commands.add_parser(
        "clock-proof",
        help="record fresh NTP, skew, strict-SSH, and exact-stop proof",
    )
    clock_proof_parser.add_argument(
        "--role", choices=("writer", "standby"), required=True
    )
    clock_proof_parser.add_argument("--release-sha", required=True)
    clock_proof_parser.add_argument("--controller-utc", required=True)
    clock_proof_parser.add_argument("--known-hosts-sha256", required=True)
    clock_proof_parser.add_argument(
        "--strict-host-key-channel", action="store_true", required=True
    )
    tailscale_start_parser = commands.add_parser(
        "tailscale-start", help="install and receipt the campaign-owned private route"
    )
    tailscale_start_parser.add_argument("--role", choices=("writer",), required=True)
    tailscale_start_parser.add_argument("--release-sha", required=True)
    tailscale_stop_parser = commands.add_parser(
        "tailscale-stop", help="reset only an unchanged campaign-owned private route"
    )
    tailscale_stop_parser.add_argument("--role", choices=("writer",), required=True)
    tailscale_stop_parser.add_argument("--release-sha", required=True)
    standby_tailscale_start_parser = commands.add_parser(
        "standby-tailscale-start",
        help="install and receipt only the private AGNI TCP 2222 bridge",
    )
    standby_tailscale_start_parser.add_argument(
        "--role", choices=("standby",), required=True
    )
    standby_tailscale_start_parser.add_argument("--release-sha", required=True)
    standby_tailscale_stop_parser = commands.add_parser(
        "standby-tailscale-stop",
        help="remove only the unchanged campaign-owned AGNI TCP 2222 handler",
    )
    standby_tailscale_stop_parser.add_argument(
        "--role", choices=("standby",), required=True
    )
    standby_tailscale_stop_parser.add_argument("--release-sha", required=True)
    route_probe_parser = commands.add_parser(
        "probe-standby-replication-route",
        help="prove the bracketed, forced-key AGNI :2222 route before dispatch",
    )
    route_probe_parser.add_argument("--role", choices=("writer",), required=True)
    route_probe_parser.add_argument("--release-sha", required=True)
    route_probe_parser.add_argument(
        "--standby-serve-ownership-receipt-digest", required=True
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "probe-denied-access":
        probe_denied_access(kind=args.kind, path=args.path)
        return 0
    if args.command == "build-candidate":
        receipt = execute_isolated_build_plan(
            staging=args.staging,
            bundle=args.bundle,
            manifest_path=args.manifest,
            uv_binary=args.uv_binary,
            release_sha=args.release_sha,
            expected_uid=args.expected_uid,
            expected_gid=args.expected_gid,
        )
        print(json.dumps(receipt, separators=(",", ":"), sort_keys=True))
        return 0
    if args.command == "seal":
        paths = seal_envelope(
            repo_root=args.repo,
            integration_base_sha=args.integration_base_sha,
            work_packet_path=args.work_packet,
            closeout_receipt=args.closeout_receipt,
            input_set_manifest=args.input_set_manifest,
            input_set_source_root=args.input_set_source_root,
            deployment_known_hosts=args.deployment_known_hosts,
            output_root=args.output,
            uv_wheel_source=args.uv_wheel_source,
        )
        print(
            json.dumps(
                {
                    "manifest": str(paths[0]),
                    "bundle": str(paths[1]),
                    "receipt": str(paths[2]),
                    "uv_wheel": str(paths[3]),
                    "input_set_manifest": str(paths[4]),
                    "input_set_archive": str(paths[5]),
                    "deployment_known_hosts": str(paths[6]),
                    "tracked_source_manifest": str(paths[7]),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "render-units":
        rendered = render_units(args.repo, args.release_sha, args.output)
        print(
            json.dumps({"rendered": [str(path) for path in rendered]}, sort_keys=True)
        )
        return 0
    if args.command == "render-static-input-manifest":
        path = write_static_input_set_manifest(
            source_root=args.source_root,
            destination=args.output,
        )
        payload = validate_input_set_manifest(_secure_json(path, require_private=True))
        print(
            json.dumps(
                {
                    "status": "static_input_manifest_rendered",
                    "path": str(path),
                    "input_set_digest": payload["input_set_digest"],
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "scan-static-inputs":
        payload = render_static_input_set_manifest(args.source_root)
        receipt = scan_static_input_set(payload, source_root=args.source_root)
        print(json.dumps(receipt, sort_keys=True))
        return 0
    if args.command == "guard-start":
        guard_campaign_clock(role=args.role)
        if args.role == "writer":
            _require_live_writer_service_units(
                release_sha=_current_frozen_release_sha(),
                runner=_run,
                reload_manager=False,
            )
        print(
            json.dumps({"status": "within_timebox", "role": args.role}, sort_keys=True)
        )
        return 0
    if args.command == "guard-runtime-binding":
        receipt = guard_runtime_binding(role=args.role)
        print(
            json.dumps(
                {
                    "status": "runtime_binding_verified",
                    "receipt_digest": receipt["receipt_digest"],
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "publish-runtime-binding":
        receipt = publish_runtime_binding_activation(
            role=args.role,
            release_sha=args.release_sha,
        )
        print(
            json.dumps(
                {
                    "status": "runtime_binding_published",
                    "receipt_digest": receipt["receipt_digest"],
                    "effect": "NoEffect",
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "activate-predispatch":
        receipt = activate_predispatch(
            role=args.role,
            release_sha=args.release_sha,
        )
        print(
            json.dumps(
                {
                    "status": "predispatch_activated",
                    "receipt_digest": receipt["receipt_digest"],
                    "effect": receipt["effect"],
                    "provider_dispatch": receipt["provider_dispatch"],
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "refresh-predispatch":
        receipt = refresh_predispatch(
            role=args.role,
            release_sha=args.release_sha,
        )
        print(
            json.dumps(
                {
                    "status": "predispatch_refreshed",
                    "receipt_digest": receipt["receipt_digest"],
                    "valid_until": receipt["valid_until"],
                    "provider_dispatch": receipt["provider_dispatch"],
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "activate-standby":
        receipt = activate_standby(
            role=args.role,
            release_sha=args.release_sha,
        )
        print(
            json.dumps(
                {
                    "status": "standby_activated",
                    "receipt_digest": receipt["receipt_digest"],
                    "effect": receipt["effect"],
                    "writer_authority_transferred": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "probe-observer-health":
        receipt = probe_observer_health(
            role=args.role,
            release_sha=args.release_sha,
        )
        print(
            json.dumps(
                {
                    "status": "observer_health_accepted",
                    "receipt_digest": receipt["receipt_digest"],
                    "consecutive_successes": receipt["consecutive_successes"],
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "finalize-runtime-staging":
        receipt = finalize_disabled_runtime_staging(
            role=args.role,
            release_sha=args.release_sha,
        )
        print(
            json.dumps(
                {
                    "status": "runtime_staging_accepted",
                    "receipt_digest": receipt["receipt_digest"],
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "probe-dashboard-rollback":
        receipt = perform_dashboard_rollback_probe(
            role=args.role,
            release_sha=args.release_sha,
        )
        print(
            json.dumps(
                {
                    "status": "dashboard_rollback_accepted",
                    "receipt_digest": receipt["receipt_digest"],
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "record-account-ui-confirmation":
        consume_account_ui_confirmation(
            role=args.role,
            release_sha=args.release_sha,
        )
        print(
            json.dumps(
                {
                    "status": "account_ui_confirmation_recorded",
                    "physical_device_attested": False,
                    "human_identity_attested": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "record-dashboard-identity":
        receipt = record_dashboard_identity_acceptance(
            role=args.role,
            release_sha=args.release_sha,
        )
        print(
            json.dumps(
                {
                    "status": "dashboard_identity_accepted",
                    "receipt_digest": receipt["receipt_digest"],
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "record-operator-credential":
        receipt = record_operator_credential_acceptance(
            role=args.role,
            release_sha=args.release_sha,
        )
        print(
            json.dumps(
                {
                    "status": "operator_credential_accepted",
                    "receipt_digest": receipt["receipt_digest"],
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "enable-dispatch":
        receipt = enable_dispatch(role=args.role, release_sha=args.release_sha)
        print(
            json.dumps(
                {
                    "status": "dispatch_authorized",
                    "receipt_digest": receipt["receipt_digest"],
                    "effect_executed": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "activate-campaign-session":
        receipt = asyncio.run(
            activate_campaign_session(
                role=args.role,
                release_sha=args.release_sha,
                dispatch_receipt_path=args.dispatch_activation_receipt,
                dashboard_receipt_path=args.dashboard_identity_receipt,
                runtime_binding_path=args.runtime_binding_receipt,
                operator_login_path=args.operator_login_file,
                control_hmac_path=args.control_hmac_key_file,
                control_gate_path=args.control_gate_path,
            )
        )
        print(json.dumps(receipt, sort_keys=True))
        return 0
    if args.command == "emit-standby-capacity-proof":
        proof = emit_standby_capacity_proof(
            release_sha=args.release_sha,
            runtime_db_bytes=args.runtime_db_bytes,
            tasks_db_bytes=args.tasks_db_bytes,
            projection_bytes=args.projection_bytes,
            known_hosts_sha256=args.deployment_known_hosts_sha256,
            strict_host_key_channel=args.strict_host_key_channel,
        )
        print(json.dumps(proof, separators=(",", ":"), sort_keys=True))
        return 0
    if args.command == "install-standby-capacity-proof":
        installed = install_standby_capacity_proof_from_stdin(
            sys.stdin.buffer.read(_MAX_STANDBY_CAPACITY_PROOF_BYTES + 1),
            release_sha=args.release_sha,
        )
        print(
            json.dumps(
                {"status": "standby_capacity_proof_installed", "path": str(installed)},
                sort_keys=True,
            )
        )
        return 0
    if args.command == "guard-standby-capacity":
        proof = guard_standby_capacity(
            role=args.role,
            release_sha=args.release_sha,
            projection_path=args.projection_path,
        )
        print(
            json.dumps(
                {
                    "status": "standby_capacity_verified",
                    "receipt_digest": proof["receipt_digest"],
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "apply-emergency-control":
        receipts = apply_emergency_controls(
            role=args.role,
            hmac_key_file=args.hmac_key_file,
            operator_login_file=args.operator_login_file,
        )
        print(
            json.dumps(
                {
                    "status": "emergency_inbox_processed",
                    "terminal_receipt_count": len(receipts),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "resume-emergency-control":
        receipts = resume_emergency_controls(
            role=args.role,
            hmac_key_file=args.hmac_key_file,
            operator_login_file=args.operator_login_file,
        )
        print(
            json.dumps(
                {
                    "status": "emergency_claims_resumed",
                    "terminal_receipt_count": len(receipts),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "tailscale-start":
        digest = tailscale_start(release_sha=args.release_sha)
        print(
            json.dumps(
                {"status": "private_serve_owned", "config_sha256": digest},
                sort_keys=True,
            )
        )
        return 0
    if args.command == "guard-stop":
        observed = guard_campaign_stop(role=args.role)
        print(
            json.dumps(
                {
                    "status": "deadline_reached",
                    "role": args.role,
                    "observed_at": observed.isoformat().replace("+00:00", "Z"),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "persist-stop":
        payload = persist_campaign_stop(
            writer_lock_path=args.writer_lock_path,
            projection_path=args.projection_path,
        )
        print(
            json.dumps(
                {
                    "status": "stop_receipted",
                    "durable_marker_persisted": payload["durable_marker_persisted"],
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "persist-standby-stop":
        payload = persist_standby_deadline_stop(
            role=args.role,
            release_sha=args.release_sha,
        )
        print(
            json.dumps(
                {
                    "status": "standby_receiver_deadline_stopped",
                    "receipt_digest": payload["receipt_digest"],
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "rollback":
        payload = execute_release_rollback(
            role=args.role,
            release_sha=args.release_sha,
        )
        print(
            json.dumps(
                {
                    "status": "release_rolled_back",
                    "receipt_digest": payload["receipt_digest"],
                    "authority_transferred": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "install-verifier-env":
        installed = install_verifier_env_from_stdin(
            sys.stdin.buffer.read(64 * 1024 + 1),
        )
        print(
            json.dumps(
                {"status": "verifier_env_installed", "path": str(installed)},
                sort_keys=True,
            )
        )
        return 0
    if args.command == "install-control-credential":
        installed = install_control_credential_from_stdin(
            sys.stdin.buffer.read(4098),
            credential=args.credential,
        )
        print(
            json.dumps(
                {
                    "status": "control_credential_installed",
                    "credential": args.credential,
                    "path": str(installed),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "prepare-host":
        account = prepare_host(args.role)
        print(
            json.dumps(
                {
                    "status": "host_roots_prepared",
                    "role": args.role,
                    "service_account": account.pw_name,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "prepare-control-runtime":
        prepare_control_runtime(role=args.role)
        print(json.dumps({"status": "control_runtime_prepared"}, sort_keys=True))
        return 0
    if args.command == "prepare-dashboard-runtime":
        prepare_dashboard_runtime(role=args.role)
        print(json.dumps({"status": "dashboard_runtime_prepared"}, sort_keys=True))
        return 0
    if args.command == "sync-observer-projection":
        payload = sync_observer_projection(role=args.role)
        print(json.dumps(payload, sort_keys=True))
        return 0
    if args.command == "clock-proof":
        timer_name = (
            CAMPAIGN_STOP_TIMER if args.role == "writer" else STANDBY_STOP_TIMER
        )
        release_timer = (
            Path(RELEASE_ROOT)
            / args.release_sha
            / SYSTEMD_TEMPLATE_ROOT
            / timer_name
        )
        installed_timer = SYSTEMD_OUTPUT_ROOT / timer_name
        admission, _account = _verify_activation_staged_release(
            role=args.role,
            release_sha=args.release_sha,
            expected_root_uid=0,
            expected_root_gid=0,
        )
        proof = record_preactivation_clock_proof(
            role=args.role,
            release_sha=args.release_sha,
            controller_utc=args.controller_utc,
            known_hosts_sha256=args.known_hosts_sha256,
            strict_host_key_channel=args.strict_host_key_channel,
            staged_release_admission_receipt_digest=admission["receipt_digest"],
            release_timer_path=release_timer,
            installed_timer_path=installed_timer,
        )
        print(
            json.dumps(
                {
                    "status": "clock_proof_recorded",
                    "role": args.role,
                    "hostname": proof["hostname"],
                    "ntp_synchronized": True,
                    "skew_seconds": proof["skew_seconds"],
                    "valid_until": proof["valid_until"],
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "tailscale-stop":
        tailscale_stop(release_sha=args.release_sha)
        print(json.dumps({"status": "private_serve_reset"}, sort_keys=True))
        return 0
    if args.command == "standby-tailscale-start":
        receipt = standby_tailscale_start(
            role=args.role,
            release_sha=args.release_sha,
        )
        print(
            json.dumps(
                {
                    "status": "standby_replication_serve_owned",
                    "receipt_digest": receipt["receipt_digest"],
                    "end_to_end_route_verified": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "standby-tailscale-stop":
        receipt = standby_tailscale_stop(
            role=args.role,
            release_sha=args.release_sha,
        )
        print(
            json.dumps(
                {
                    "status": "standby_replication_serve_stopped",
                    "receipt_digest": receipt["receipt_digest"],
                    "owned_handler_removed": True,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "probe-standby-replication-route":
        receipt = probe_standby_replication_route(
            role=args.role,
            release_sha=args.release_sha,
            standby_serve_ownership_receipt_digest=(
                args.standby_serve_ownership_receipt_digest
            ),
        )
        print(
            json.dumps(
                {
                    "status": "standby_replication_route_verified",
                    "receipt_digest": receipt["receipt_digest"],
                    "valid_until": receipt["valid_until"],
                },
                sort_keys=True,
            )
        )
        return 0
    manifest = load_manifest(args.manifest, for_activation=True)
    if args.command == "verify":
        verify_envelope(
            manifest,
            repo_root=args.repo,
            bundle_path=args.bundle,
            receipt_path=args.receipt,
            uv_wheel_path=args.uv_wheel,
            input_set_manifest_path=args.input_set_manifest,
            input_set_archive_path=args.input_set_archive,
            deployment_known_hosts_path=args.deployment_known_hosts,
            tracked_source_manifest_path=args.tracked_source_manifest,
            expected_role=args.role,
        )
        print(
            json.dumps(
                {
                    "status": "verified",
                    "release_sha": manifest["release_sha"],
                    "role": args.role,
                },
                sort_keys=True,
            )
        )
        return 0
    target = stage_candidate(
        manifest,
        bundle_path=args.bundle,
        receipt_path=args.receipt,
        uv_wheel_path=args.uv_wheel,
        input_set_manifest_path=args.input_set_manifest,
        input_set_archive_path=args.input_set_archive,
        tracked_source_manifest_path=args.tracked_source_manifest,
        role=args.role,
    )
    print(
        json.dumps(
            {"status": "staged", "path": str(target), "role": args.role}, sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseContractError as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, sort_keys=True))
        raise SystemExit(2) from exc
