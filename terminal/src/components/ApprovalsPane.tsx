import React from "react";
import {Box, Text} from "ink";

import {ownerProjectionModality} from "../nihonga/projectionModality.ts";
import type {ApprovalQueueEntry, ApprovalQueueState, BridgeStatus} from "../types";
import {THEME} from "../theme";

type Props = {
  title: string;
  approvalPane: ApprovalQueueState;
  authorityObserved: boolean;
  bridgeStatus: BridgeStatus;
  compact?: boolean;
};

function approvalEntries(approvalPane: ApprovalQueueState): ApprovalQueueEntry[] {
  return approvalPane.order
    .map((actionId) => approvalPane.entriesByActionId[actionId])
    .filter((entry): entry is ApprovalQueueEntry => Boolean(entry));
}

function selectedApprovalEntry(approvalPane: ApprovalQueueState): ApprovalQueueEntry | undefined {
  const entries = approvalEntries(approvalPane);
  const pending = entries.filter((entry) => entry.pending);
  return approvalPane.selectedActionId ? approvalPane.entriesByActionId[approvalPane.selectedActionId] : pending[0] ?? entries[0];
}

export function ApprovalsPane({title, approvalPane, authorityObserved, bridgeStatus, compact = false}: Props): React.ReactElement {
  const entries = approvalEntries(approvalPane);
  const pending = entries.filter((entry) => entry.pending);
  const selected = selectedApprovalEntry(approvalPane);
  const retained = entries.length > 0 || approvalPane.historyBacked;
  const modality = ownerProjectionModality({
    bridgeStatus,
    authorityObserved,
    hasRetainedProjection: retained,
  });
  const modalityLabel = modality === "observed"
    ? `◉ OBSERVED · owner history · pending ${pending.length} · tracked ${entries.length}`
    : modality === "stale"
      ? `~ STALE · ${entries.length} retained rows · resolution held`
      : "?[?] UNKNOWN · permission owner projection absent";

  return (
    <Box flexGrow={1} borderStyle="round" borderColor={THEME.ridge} paddingX={1} flexDirection="column">
      <Text color={THEME.wave} bold>{title}</Text>
      <Text color={THEME.stone}>
        {modalityLabel}
      </Text>
      {compact && modality !== "observed" ? <Text color={THEME.persimmon}>▣ HELD · fresh owner history required</Text> : null}
      <Box marginTop={1} flexDirection={compact ? "column" : "row"}>
        <Box width={compact ? undefined : "35%"} flexDirection="column" paddingX={1}>
          <Text color={THEME.mist} bold>Queue</Text>
          <Text color={THEME.stone}>pending-first operator decisions</Text>
          {entries.length === 0 ? (
            <Text color={THEME.stone}>
              {modality === "observed" ? "No approvals in the observed projection." : "No current permission projection."}
            </Text>
          ) : (
            entries.slice(0, 12).map((entry) => {
              const active = approvalPane.selectedActionId === entry.decision.action_id;
              const tone = active ? THEME.wave : entry.pending ? THEME.parchment : THEME.stone;
              return (
                <Box key={entry.decision.action_id} flexDirection="column" marginTop={1}>
                  <Text color={tone} bold={active} backgroundColor={active ? THEME.harbor : undefined}>
                    {active ? "◆ " : "• "}
                    {entry.decision.tool_name} | {entry.status}
                  </Text>
                  <Text color={active ? THEME.foam : THEME.stone}>
                    {"  "}{entry.decision.risk} | {entry.decision.action_id}
                  </Text>
                </Box>
              );
            })
          )}
        </Box>
        <Box
          width={compact ? undefined : "65%"}
          marginLeft={compact ? 0 : 1}
          marginTop={compact ? 1 : 0}
          flexDirection="column"
          paddingX={1}
        >
          <Text color={THEME.mist} bold>Selected</Text>
          <Text color={THEME.stone}>decision, resolution, and runtime trace</Text>
          {!selected ? (
            <Text color={THEME.stone}>No selected approval.</Text>
          ) : (
            <>
              <Text color={THEME.foam} bold>{selected.decision.tool_name}</Text>
              <Text color={THEME.stone}>status {selected.status} | risk {selected.decision.risk}</Text>
              <Text color={THEME.stone}>session {String(selected.decision.metadata.session_id ?? "none")} | provider {String(selected.decision.metadata.provider_id ?? "unknown")}</Text>
              <Text color={THEME.stone}>action {selected.decision.action_id} | tool call {String(selected.decision.metadata.tool_call_id ?? "none")}</Text>
              <Text color={THEME.mist} bold>Rationale</Text>
              <Text color={THEME.foam}>{selected.decision.rationale}</Text>
              {selected.resolution ? (
                <>
                  <Text color={THEME.mist} bold>Resolution</Text>
                  <Text color={THEME.foam}>{selected.resolution.resolution} | {selected.resolution.enforcement_state}</Text>
                </>
              ) : null}
              {selected.outcome ? (
                <>
                  <Text color={THEME.mist} bold>Runtime outcome</Text>
                  <Text color={THEME.foam}>{selected.outcome.outcome} | {selected.outcome.source}</Text>
                </>
              ) : null}
            </>
          )}
        </Box>
      </Box>
    </Box>
  );
}
