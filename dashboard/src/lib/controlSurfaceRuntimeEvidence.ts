import type {
  ControlSurfaceEvidenceItem,
  ControlSurfaceRow,
} from "./types";

export type RuntimeEvidenceTone = "ok" | "warn" | "error" | "muted";

export interface RuntimeEvidenceDigest {
  label: string;
  detail: string;
  tone: RuntimeEvidenceTone;
}

const TONE_RANK: Record<RuntimeEvidenceTone, number> = {
  muted: 0,
  ok: 1,
  warn: 2,
  error: 3,
};

interface RatioField {
  current: number;
  total: number;
}

function raiseTone(
  current: RuntimeEvidenceTone,
  next: RuntimeEvidenceTone,
): RuntimeEvidenceTone {
  return TONE_RANK[next] > TONE_RANK[current] ? next : current;
}

function stateField(source: string): string {
  const match = source.match(/\bstate=([^;]+)/);
  return match?.[1] ?? "";
}

function ratioField(source: string, field: string): RatioField | null {
  const match = source.match(new RegExp(`\\b${field}=(\\d+)\\/(\\d+)`));
  if (!match) {
    return null;
  }
  return {
    current: Number.parseInt(match[1] ?? "0", 10),
    total: Number.parseInt(match[2] ?? "0", 10),
  };
}

function ratioIsCompleteAndNonEmpty(ratio: RatioField | null): boolean {
  return ratio !== null && ratio.total > 0 && ratio.current === ratio.total;
}

function boolField(source: string, field: string): boolean | null {
  const match = source.match(new RegExp(`\\b${field}=(true|false)`));
  if (!match) {
    return null;
  }
  return match[1] === "true";
}

function addLabel(labels: string[], label: string): void {
  if (label && !labels.includes(label)) {
    labels.push(label);
  }
}

function findEvidence(
  row: ControlSurfaceRow,
  predicate: (item: ControlSurfaceEvidenceItem) => boolean,
): ControlSurfaceEvidenceItem | undefined {
  return row.evidence.find(predicate);
}

function isRuntimeProofGap(gap: string): boolean {
  if (
    gap.startsWith("live_ops_status:") ||
    gap === "live_ops_not_live" ||
    gap === "human_authority_required" ||
    gap === "vps_candidate" ||
    gap === "heavy_local_load"
  ) {
    return false;
  }
  return gap.length > 0;
}

function proofGapLabel(gap: string): string {
  return gap.replaceAll("_", " ");
}

function proofGapAlreadyRepresented(gap: string, labels: string[]): boolean {
  if (gap.includes("source_stale") && labels.includes("source stale")) {
    return true;
  }
  if (
    gap.includes("runtime_receipts") &&
    labels.some((label) => label.startsWith("receipt head "))
  ) {
    return true;
  }
  if (
    gap.includes("provider_model") &&
    labels.some((label) => label.startsWith("provider/model "))
  ) {
    return true;
  }
  if (gap.includes("dispatch_runtime") && labels.includes("dispatch unproven")) {
    return true;
  }
  if (
    gap.includes("control_surface_rows") &&
    labels.some((label) => label.startsWith("rows "))
  ) {
    return true;
  }
  if (
    gap.includes("nats_hot_contact") &&
    labels.some((label) => label.startsWith("hot contact "))
  ) {
    return true;
  }
  if (
    gap.includes("a2a_inbox_bridge") &&
    labels.some(
      (label) =>
        label.startsWith("bridge ") ||
        label.startsWith("heartbeat ") ||
        label.startsWith("consumer "),
    )
  ) {
    return true;
  }
  if (
    gap.includes("ds_goal_cli") &&
    labels.some(
      (label) =>
        label.startsWith("ds-goal target ") ||
        label.startsWith("receipt hardening ") ||
        label.startsWith("preflight "),
    )
  ) {
    return true;
  }
  return false;
}

export function buildRuntimeEvidenceDigest(
  row: ControlSurfaceRow,
): RuntimeEvidenceDigest | null {
  if (!row.id.startsWith("live_ops.") && row.kind !== "fleet") {
    return null;
  }

  const labels: string[] = [];
  const details: string[] = [];
  let tone: RuntimeEvidenceTone = "muted";

  const processSource = findEvidence(row, (item) =>
    item.source.startsWith("process_source_state "),
  );
  if (processSource) {
    details.push(processSource.source);
    switch (stateField(processSource.source)) {
      case "process_started_after_sources":
        addLabel(labels, "source fresh");
        tone = raiseTone(tone, "ok");
        break;
      case "source_changed_after_process_start":
        addLabel(labels, "source stale");
        tone = raiseTone(tone, "warn");
        break;
      case "no_process":
        addLabel(labels, "no process");
        tone = raiseTone(tone, "error");
        break;
      case "process_start_probe_failed":
        addLabel(labels, "source probe failed");
        tone = raiseTone(tone, "warn");
        break;
      case "process_start_uninspected":
        addLabel(labels, "source uninspected");
        tone = raiseTone(tone, "warn");
        break;
      default:
        addLabel(labels, "source unproven");
        tone = raiseTone(tone, "warn");
        break;
    }
  }

  const receiptHead = findEvidence(row, (item) =>
    item.source.startsWith("runtime_receipt_active_head "),
  );
  if (receiptHead) {
    details.push(receiptHead.source);
    const clean = boolField(receiptHead.source, "clean");
    const fresh = boolField(receiptHead.source, "fresh");
    if (clean === false && fresh === false) {
      addLabel(labels, "receipt head dirty/stale");
      tone = raiseTone(tone, "error");
    } else if (clean === false) {
      addLabel(labels, "receipt head dirty");
      tone = raiseTone(tone, "error");
    } else if (fresh === false) {
      addLabel(labels, "receipt head stale");
      tone = raiseTone(tone, "warn");
    } else if (clean === true) {
      addLabel(labels, "receipt head clean");
      tone = raiseTone(tone, "ok");
    } else {
      addLabel(labels, "receipt head unknown");
      tone = raiseTone(tone, "warn");
    }
  }

  const providerModelCoverage = findEvidence(row, (item) =>
    item.source.startsWith("runtime_receipt_provider_model "),
  );
  if (providerModelCoverage) {
    details.push(providerModelCoverage.source);
    const accounted = ratioField(providerModelCoverage.source, "accounted");
    const accountedComplete = ratioIsCompleteAndNonEmpty(accounted);
    const hasAccountedRows = accounted !== null && accounted.current > 0;
    if (
      accountedComplete ||
      (
        providerModelCoverage.status === "present" &&
        providerModelCoverage.source.includes("no_provider_execution")
      )
    ) {
      addLabel(labels, "provider/model accounted");
      tone = raiseTone(tone, "ok");
    } else if (providerModelCoverage.status === "present") {
      addLabel(labels, "provider/model proven");
      tone = raiseTone(tone, "ok");
    } else if (
      providerModelCoverage.source.includes("latest=0/") &&
      !hasAccountedRows
    ) {
      addLabel(labels, "provider/model missing");
      tone = raiseTone(tone, "warn");
    } else {
      addLabel(labels, "provider/model partial");
      tone = raiseTone(tone, "warn");
    }
  }

  const daemonDispatch = findEvidence(row, (item) =>
    item.source.startsWith("daemon_dispatch "),
  );
  if (daemonDispatch) {
    details.push(daemonDispatch.source);
    if (daemonDispatch.status === "present") {
      addLabel(labels, "dispatch proven");
      tone = raiseTone(tone, "ok");
    } else {
      addLabel(labels, "dispatch unproven");
      tone = raiseTone(tone, "warn");
    }
  }

  const dashboardRows = findEvidence(row, (item) =>
    item.source.startsWith("dashboard_control_surface_rows="),
  );
  if (dashboardRows) {
    details.push(dashboardRows.source);
    const state = dashboardRows.source.split("=", 2)[1] || "unknown";
    if (row.gap_codes.includes("dashboard_control_surface_rows_slow")) {
      addLabel(labels, "rows slow");
      tone = raiseTone(tone, "warn");
    } else if (state === "ok") {
      addLabel(labels, "rows ok");
      tone = raiseTone(tone, "ok");
    } else if (state === "not_checked") {
      addLabel(labels, "rows not checked");
    } else {
      addLabel(labels, `rows ${state}`);
      tone = raiseTone(tone, "warn");
    }
  }

  const natsAckTier = findEvidence(row, (item) =>
    item.source.startsWith("nats_ack_tier_state "),
  );
  if (natsAckTier) {
    details.push(natsAckTier.source);
    if (natsAckTier.source.includes("ready=true")) {
      addLabel(labels, "hot contact ready");
      tone = raiseTone(tone, "ok");
    } else if (row.gap_codes.includes("nats_hot_contact_ack_stale")) {
      addLabel(labels, "hot contact stale");
      tone = raiseTone(tone, "warn");
    } else {
      addLabel(labels, "hot contact unproven");
      tone = raiseTone(tone, "warn");
    }
  }

  const a2aBridgeState = findEvidence(row, (item) =>
    item.source.startsWith("a2a_bridge_state "),
  );
  if (a2aBridgeState) {
    details.push(a2aBridgeState.source);
    const processLive = boolField(a2aBridgeState.source, "process_live");
    const tmuxLive = boolField(a2aBridgeState.source, "tmux_live");
    const heartbeat =
      a2aBridgeState.source.match(/\bheartbeat=([^;]+)/)?.[1] ?? "";
    const consumer =
      a2aBridgeState.source.match(/\bconsumer=([^;]+)/)?.[1] ?? "";
    const domainReceipt =
      a2aBridgeState.source.match(/\bdomain_receipt=([^;]+)/)?.[1] ?? "";
    const semanticReply = boolField(a2aBridgeState.source, "semantic_reply");
    const completed = boolField(a2aBridgeState.source, "completed");
    if (processLive === true || tmuxLive === true) {
      addLabel(labels, "bridge live");
      tone = raiseTone(tone, "ok");
    } else {
      addLabel(labels, "bridge stopped");
      tone = raiseTone(tone, "warn");
    }
    if (heartbeat === "fresh") {
      addLabel(labels, "heartbeat fresh");
      tone = raiseTone(tone, "ok");
    } else if (heartbeat === "stale") {
      addLabel(labels, "heartbeat stale");
      tone = raiseTone(tone, "warn");
    } else if (heartbeat === "missing") {
      addLabel(labels, "heartbeat missing");
      tone = raiseTone(tone, "warn");
    }
    if (completed === true) {
      addLabel(labels, "A2A completed");
      tone = raiseTone(tone, "ok");
    } else if (domainReceipt === "domain_receipted" && semanticReply === true) {
      addLabel(labels, "semantic reply present");
      tone = raiseTone(tone, "ok");
    } else if (domainReceipt === "domain_receipted") {
      addLabel(labels, "domain receipt only");
      tone = raiseTone(tone, "warn");
    } else if (
      domainReceipt === "missing" ||
      domainReceipt === "not_domain_receipted"
    ) {
      addLabel(labels, "domain reply missing");
      tone = raiseTone(tone, "warn");
    } else if (semanticReply === false) {
      addLabel(labels, "semantic reply missing");
      tone = raiseTone(tone, "warn");
    }
    if (labels.length < 3 && consumer === "consumer_inspectable") {
      addLabel(labels, "consumer inspectable");
    } else if (labels.length < 3 && consumer) {
      addLabel(labels, "consumer unproven");
      tone = raiseTone(tone, "warn");
    }
  }

  const dsGoalCliState = findEvidence(row, (item) =>
    item.source.startsWith("ds_goal_cli_state "),
  );
  if (dsGoalCliState) {
    details.push(dsGoalCliState.source);
    const matchesCurrent = boolField(dsGoalCliState.source, "matches_current");
    const approvalRequired = boolField(
      dsGoalCliState.source,
      "operator_approval_required",
    );
    const hardening =
      dsGoalCliState.source.match(/\bhardening=([^;]+)/)?.[1] ?? "";
    const preflight =
      dsGoalCliState.source.match(/\bpreflight=([^;]+)/)?.[1] ?? "";
    if (matchesCurrent === true) {
      addLabel(labels, "ds-goal target current");
      tone = raiseTone(tone, "ok");
    } else if (matchesCurrent === false) {
      addLabel(labels, "ds-goal target mismatch");
      tone = raiseTone(tone, "error");
    } else {
      addLabel(labels, "ds-goal target unproven");
      tone = raiseTone(tone, "warn");
    }
    if (hardening === "sync_receipt_side_effect_keys_hardened") {
      addLabel(labels, "receipt hardening present");
      tone = raiseTone(tone, "ok");
    } else if (hardening === "sync_receipt_side_effect_keys_missing") {
      addLabel(labels, "receipt hardening missing");
      tone = raiseTone(tone, "error");
    } else if (hardening) {
      addLabel(labels, "receipt hardening unproven");
      tone = raiseTone(tone, "warn");
    }
    if (preflight.startsWith("pass")) {
      addLabel(labels, "preflight pinned");
      tone = raiseTone(tone, "ok");
    } else if (preflight.startsWith("blocked")) {
      addLabel(labels, "preflight blocked");
      tone = raiseTone(tone, "error");
    } else if (approvalRequired === true) {
      addLabel(labels, "approval required");
      tone = raiseTone(tone, "warn");
    }
  }

  if (labels.length < 3) {
    const proofGaps = row.gap_codes.filter(
      (gap) => isRuntimeProofGap(gap) && !proofGapAlreadyRepresented(gap, labels),
    );
    for (const gap of proofGaps.slice(0, 3 - labels.length)) {
      addLabel(labels, proofGapLabel(gap));
      tone = raiseTone(tone, "warn");
    }
  }

  if (labels.length === 0) {
    return null;
  }

  return {
    label: labels.slice(0, 3).join(" · "),
    detail: details.length > 0 ? details.join(" | ") : row.gap_codes.join(", "),
    tone,
  };
}
