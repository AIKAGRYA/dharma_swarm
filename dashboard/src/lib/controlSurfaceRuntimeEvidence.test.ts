import assert from "node:assert/strict";
import test from "node:test";

import {
  buildRuntimeEvidenceDigest,
} from "./controlSurfaceRuntimeEvidence.ts";
import type { ControlSurfaceRow } from "./types.ts";

function makeRow(overrides: Partial<ControlSurfaceRow> = {}): ControlSurfaceRow {
  return {
    id: "live_ops.substrate.dharma_daemon",
    kind: "fleet",
    label: "Dharma daemon",
    authority_role: "observed_authority",
    declared_state: "live",
    desired_state: "live",
    observed_state: "live",
    coherence_state: "partial",
    priority: "p0",
    owner_module: "scripts/runtime/live_ops_census.py",
    truth_owner: "live_ops_census",
    evidence: [],
    evidence_labels: [],
    freshness: "2026-06-13T23:22:51Z",
    gap_codes: [],
    next_action: "",
    human_decision_required: false,
    source_refs: [],
    source_ref_labels: [],
    raw: {},
    ...overrides,
  };
}

test("runtime evidence digest surfaces stale daemon source and dirty receipt head", () => {
  const digest = buildRuntimeEvidenceDigest(
    makeRow({
      evidence: [
        {
          kind: "process",
          source:
            "process_source_state state=source_changed_after_process_start; starts=93875@2026-06-13T13:55:10Z; newest_source=2026-06-13T21:10:58Z; newer_files=dharma_swarm/orchestrator.py@2026-06-13T21:10:58Z",
          status: "degraded",
        },
        {
          kind: "db_probe",
          source:
            "runtime_receipt_active_head clean=false; fresh=false; age_hours=8.53; max_age_hours=6.0; total=7769; latest=2026-06-13T23:13:37.937601+00:00; windows=5m:56/56,15m:56/56,60m:224/224",
          status: "unproven",
        },
        {
          kind: "process",
          source:
            "daemon_dispatch launch=spine_enabled_launch_spec; running=not_inspected_no_secret_env_dump",
          status: "unproven",
        },
      ],
    }),
  );

  assert.equal(digest?.label, "source stale · receipt head dirty/stale · dispatch unproven");
  assert.equal(digest?.tone, "error");
  assert.match(digest?.detail ?? "", /newest_source=2026-06-13T21:10:58Z/);
  assert.match(digest?.detail ?? "", /fresh=false/);
  assert.match(digest?.detail ?? "", /windows=5m:56\/56/);
});

test("runtime evidence digest surfaces clean but stale receipt head", () => {
  const digest = buildRuntimeEvidenceDigest(
    makeRow({
      gap_codes: [
        "live_ops_status:live",
        "daemon_runtime_receipts_stale",
      ],
      evidence: [
        {
          kind: "db_probe",
          source:
            "runtime_receipt_active_head clean=true; fresh=false; age_hours=7.1; max_age_hours=6.0; total=42; latest=2026-06-13T23:13:37.937601+00:00; windows=5m:0/1,15m:0/2,60m:0/4",
          status: "unproven",
        },
      ],
    }),
  );

  assert.equal(digest?.label, "receipt head stale");
  assert.equal(digest?.tone, "warn");
  assert.match(digest?.detail ?? "", /age_hours=7.1/);
});

test("runtime evidence digest labels missing provider model coverage", () => {
  const digest = buildRuntimeEvidenceDigest(
    makeRow({
      gap_codes: [
        "live_ops_status:live",
        "daemon_runtime_receipts_active_head_dirty",
        "daemon_runtime_receipts_stale",
        "daemon_runtime_provider_model_unproven",
      ],
      evidence: [
        {
          kind: "db_probe",
          source:
            "runtime_receipt_active_head clean=false; fresh=false; age_hours=8.53; max_age_hours=6.0; total=7769; latest=2026-06-13T23:13:37.937601+00:00; windows=5m:56/56,15m:56/56,60m:224/224",
          status: "unproven",
        },
        {
          kind: "db_probe",
          source:
            "runtime_receipt_provider_model available=true; latest=0/250; provider=0/250; model=0/250; percent=0.0; major_total=3523",
          status: "unproven",
        },
        {
          kind: "process",
          source:
            "daemon_dispatch launch=spine_enabled_launch_spec; running=not_inspected_no_secret_env_dump",
          status: "unproven",
        },
      ],
    }),
  );

  assert.equal(
    digest?.label,
    "receipt head dirty/stale · provider/model missing · dispatch unproven",
  );
  assert.equal(digest?.tone, "error");
  assert.match(digest?.detail ?? "", /runtime_receipt_provider_model/);
});

test("runtime evidence digest labels complete provider model accounting", () => {
  const digest = buildRuntimeEvidenceDigest(
    makeRow({
      evidence: [
        {
          kind: "db_probe",
          source:
            "runtime_receipt_provider_model available=true; latest=0/2; proof=2/2; accounted=2/2; provider=0/2; model=0/2; percent=0.0; proof_percent=100.0; accounted_percent=100.0; terminal=0/2; terminal_proof=2/2; terminal_accounted=2/2; classes=no_provider_execution=2",
          status: "present",
        },
      ],
    }),
  );

  assert.equal(digest?.label, "provider/model accounted");
  assert.equal(digest?.tone, "ok");
});

test("runtime evidence digest does not treat empty accounting as proof", () => {
  const digest = buildRuntimeEvidenceDigest(
    makeRow({
      evidence: [
        {
          kind: "db_probe",
          source:
            "runtime_receipt_provider_model available=true; latest=0/0; proof=0/0; accounted=0/0; provider=0/0; model=0/0; percent=unknown; proof_percent=unknown; accounted_percent=unknown; terminal=0/0; terminal_accounted=0/0; classes=no_provider_execution=0",
          status: "unproven",
        },
      ],
    }),
  );

  assert.equal(digest?.label, "provider/model missing");
  assert.equal(digest?.tone, "warn");
});

test("runtime evidence digest keeps partial accounting as partial", () => {
  const digest = buildRuntimeEvidenceDigest(
    makeRow({
      evidence: [
        {
          kind: "db_probe",
          source:
            "runtime_receipt_provider_model available=true; latest=0/2; proof=1/2; accounted=1/2; provider=0/2; model=0/2; percent=0.0; proof_percent=50.0; accounted_percent=50.0; terminal=0/2; terminal_accounted=1/2; classes=missing=1|no_provider_execution=1",
          status: "unproven",
        },
      ],
    }),
  );

  assert.equal(digest?.label, "provider/model partial");
  assert.equal(digest?.tone, "warn");
});

test("runtime evidence digest surfaces stale dashboard source and rows timeout", () => {
  const digest = buildRuntimeEvidenceDigest(
    makeRow({
      id: "live_ops.dashboard.local",
      label: "Dashboard API and web",
      evidence: [
        {
          kind: "process",
          source:
            "process_source_state state=source_changed_after_process_start; starts=70585@2026-06-13T16:58:24Z; newest_source=2026-06-13T23:21:56Z; newer_files=dharma_swarm/operator_core/control_surface_live_ops.py@2026-06-13T23:21:56Z",
          status: "degraded",
        },
        {
          kind: "process",
          source: "dashboard_control_surface_rows=timeout",
          status: "unproven",
        },
      ],
    }),
  );

  assert.equal(digest?.label, "source stale · rows timeout");
  assert.equal(digest?.tone, "warn");
  assert.match(digest?.detail ?? "", /control_surface_live_ops.py/);
});

test("runtime evidence digest prefers slow rows proof gap over ok rows response", () => {
  const digest = buildRuntimeEvidenceDigest(
    makeRow({
      id: "live_ops.dashboard.local",
      label: "Dashboard API and web",
      gap_codes: [
        "live_ops_status:live",
        "dashboard_control_surface_rows_slow",
        "dashboard_control_surface_source_stale",
      ],
      evidence: [
        {
          kind: "process",
          source:
            "process_source_state state=source_changed_after_process_start; starts=70585@2026-06-13T16:58:24Z; newest_source=2026-06-13T23:34:00Z; newer_files=dashboard/src/lib/controlSurfaceRuntimeEvidence.ts@2026-06-13T23:34:00Z",
          status: "degraded",
        },
        {
          kind: "process",
          source: "dashboard_control_surface_rows=ok",
          status: "present",
        },
      ],
    }),
  );

  assert.equal(digest?.label, "source stale · rows slow");
  assert.equal(digest?.tone, "warn");
});

test("runtime evidence digest treats dashboard self-probe skip as muted", () => {
  const digest = buildRuntimeEvidenceDigest(
    makeRow({
      id: "live_ops.dashboard.local",
      label: "Dashboard API and web",
      gap_codes: [
        "live_ops_status:live",
      ],
      evidence: [
        {
          kind: "process",
          source: "dashboard_control_surface_rows=not_checked",
          status: "skipped",
        },
      ],
    }),
  );

  assert.equal(digest?.label, "rows not checked");
  assert.equal(digest?.tone, "muted");
});

test("runtime evidence digest surfaces generic census proof gaps", () => {
  const digest = buildRuntimeEvidenceDigest(
    makeRow({
      id: "live_ops.transport.a2a_bridge",
      label: "A2A inbox delivery bridge",
      observed_state: "stopped",
      coherence_state: "drifted",
      gap_codes: [
        "live_ops_status:stopped",
        "a2a_inbox_bridge_stopped",
        "live_ops_not_live",
      ],
      evidence: [
        {
          kind: "process",
          source: "proof_gap=a2a_inbox_bridge_stopped",
          status: "unproven",
        },
      ],
    }),
  );

  assert.equal(digest?.label, "a2a inbox bridge stopped");
  assert.equal(digest?.tone, "warn");
  assert.match(digest?.detail ?? "", /a2a_inbox_bridge_stopped/);
});

test("runtime evidence digest surfaces A2A bridge heartbeat and consumer state", () => {
  const digest = buildRuntimeEvidenceDigest(
    makeRow({
      id: "live_ops.transport.a2a_bridge",
      label: "A2A inbox delivery bridge",
      observed_state: "stopped",
      coherence_state: "drifted",
      gap_codes: [
        "live_ops_status:stopped",
        "a2a_inbox_bridge_stopped",
        "a2a_inbox_bridge_heartbeat_stale",
        "live_ops_not_live",
      ],
      evidence: [
        {
          kind: "process",
          source:
            "a2a_bridge_state process_live=false; tmux_live=false; heartbeat=stale; heartbeat_age_hours=66.06; consumer=consumer_inspectable; pending=0; ack_pending=0; sent=send_receipt_found; handler_ack=handler_acked; domain_receipt=missing; semantic_reply=false; peer_model_processed=false; completed=false",
          status: "degraded",
        },
      ],
    }),
  );

  assert.equal(
    digest?.label,
    "bridge stopped · heartbeat stale · domain reply missing",
  );
  assert.equal(digest?.tone, "warn");
  assert.match(digest?.detail ?? "", /handler_ack=handler_acked/);
  assert.match(digest?.detail ?? "", /semantic_reply=false/);
});

test("runtime evidence digest surfaces ds-goal wrapper target and preflight state", () => {
  const digest = buildRuntimeEvidenceDigest(
    makeRow({
      id: "live_ops.cli.ds_goal",
      label: "ds-goal runtime CLI",
      observed_state: "live",
      coherence_state: "partial",
      gap_codes: [
        "live_ops_status:live",
        "ds_goal_cli_target_repo_mismatch",
        "ds_goal_cli_target_lacks_sync_side_effect_hardening",
      ],
      evidence: [
        {
          kind: "process",
          source:
            "ds_goal_cli_state target_repo=/Users/dhyana/dharma_swarm_main; current_repo=/Users/dhyana/dharma_swarm; matches_current=false; default_target=/Users/dhyana/dharma_swarm_main; hardening=sync_receipt_side_effect_keys_missing; preflight=blocked_unpinned_default_target; operator_approval_required=true; safe_pin=DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm /Users/dhyana/.dharma/bin/ds-goal",
          status: "degraded",
        },
      ],
    }),
  );

  assert.equal(
    digest?.label,
    "ds-goal target mismatch · receipt hardening missing · preflight blocked",
  );
  assert.equal(digest?.tone, "error");
  assert.match(digest?.detail ?? "", /safe_pin=DHARMA_SWARM_REPO=/);
});

test("runtime evidence digest ignores metadata-only live ops gaps", () => {
  assert.equal(
    buildRuntimeEvidenceDigest(
      makeRow({
        id: "live_ops.revenue.cashclaw_gate",
        label: "Revenue / CashClaw gate",
        observed_state: "blocked",
        coherence_state: "drifted",
        gap_codes: [
          "live_ops_status:blocked",
          "live_ops_not_live",
          "human_authority_required",
        ],
      }),
    ),
    null,
  );
});

test("runtime evidence digest surfaces stale NATS hot-contact proof", () => {
  const digest = buildRuntimeEvidenceDigest(
    makeRow({
      id: "live_ops.evidence.nats_receipts",
      label: "NATS receipts and logs",
      gap_codes: [
        "live_ops_status:live",
        "nats_hot_contact_ack_stale",
      ],
      evidence: [
        {
          kind: "go_receipt",
          source:
            "nats_ack_tier_state live_probe=DELIVERED_TO_CONSUMER; live_verified=true; live_age_hours=0.01; hot_contact=HANDLER_ACKED; hot_age_hours=210.5; hot_max_age_hours=24.0; ready=false",
          status: "degraded",
        },
      ],
    }),
  );

  assert.equal(digest?.label, "hot contact stale");
  assert.equal(digest?.tone, "warn");
  assert.match(digest?.detail ?? "", /hot_contact=HANDLER_ACKED/);
});

test("runtime evidence digest ignores non-runtime rows", () => {
  assert.equal(
    buildRuntimeEvidenceDigest(
      makeRow({
        id: "module.runtime_state",
        kind: "module",
        evidence: [
          {
            kind: "file",
            source: "dharma_swarm/runtime_state.py",
            status: "present",
          },
        ],
      }),
    ),
    null,
  );
});
