import React from "react";
import {Box, Text} from "ink";

import {
  centeredSessionViewport,
  compactSessionId,
  compactSessionRoute,
  compactText,
  sessionContinuityLabel,
  sessionConversationLines,
  sessionStatusGlyph,
} from "../sessionRender.ts";
import type {SessionCatalogEntry, SessionContinuityState, SessionPaneState} from "../types";
import {THEME} from "../theme";

type Props = {
  title: string;
  sessionPane: SessionPaneState;
  sessionContinuity: SessionContinuityState;
};

function sessionEntries(sessionPane: SessionPaneState): SessionCatalogEntry[] {
  return sessionPane.catalog?.sessions ?? [];
}

function selectedSession(sessionPane: SessionPaneState): SessionCatalogEntry | undefined {
  const entries = sessionEntries(sessionPane);
  return entries.find((entry) => entry.session.session_id === sessionPane.selectedSessionId) ?? entries[0];
}

export function SessionsPane({title, sessionPane, sessionContinuity}: Props): React.ReactElement {
  const entries = sessionEntries(sessionPane);
  const selected = selectedSession(sessionPane);
  const detail = selected ? sessionPane.detailsBySessionId[selected.session.session_id] : undefined;
  const viewport = centeredSessionViewport(sessionPane.catalog, selected?.session.session_id);
  const conversation = sessionConversationLines(detail);
  const visibleRange = viewport.entries.length > 0
    ? `${viewport.startIndex + 1}-${viewport.endIndex}`
    : "0";
  const continuityLabel = sessionContinuityLabel(
    sessionContinuity.continuityMode,
    sessionContinuity.activeSessionId,
    selected?.session.session_id,
  );

  return (
    // FACE-2 de-border (F-165): ridge = the one focused-pane border; inner
    // columns separate by space, selection by glyph+color (never border).
    <Box flexGrow={1} borderStyle="round" borderColor={THEME.ridge} paddingX={1} flexDirection="column">
      <Text color={THEME.wave} bold>{title}</Text>
      <Text color={THEME.stone} wrap="truncate-end">
        {viewport.loadedCount} shown of {viewport.totalCount} | rows {visibleRange} | {continuityLabel} | j/k select | Enter detail | r resume | f fresh
      </Text>
      <Box marginTop={1}>
        <Box width="35%" flexDirection="column" paddingX={1}>
          <Text color={THEME.mist} bold>Catalog</Text>
          <Text color={THEME.stone} wrap="truncate-end">id · route · status</Text>
          {entries.length === 0 ? (
            <Text color={THEME.stone}>No sessions.</Text>
          ) : (
            viewport.entries.map((entry) => {
              const active = sessionPane.selectedSessionId === entry.session.session_id;
              return (
                <Text
                  key={entry.session.session_id}
                  color={active ? THEME.wave : THEME.foam}
                  bold={active}
                  backgroundColor={active ? THEME.harbor : undefined}
                  wrap="truncate-end"
                >
                    {active ? "◆ " : "• "}
                    {compactSessionId(entry.session.session_id, 9)} {compactSessionRoute(entry.session.provider_id, entry.session.model_id, 10)} {sessionStatusGlyph(entry.session.status)}
                </Text>
              );
            })
          )}
        </Box>
        <Box width="65%" marginLeft={1} flexDirection="column" paddingX={1}>
          <Text color={THEME.mist} bold>Drilldown</Text>
          <Text color={THEME.stone} wrap="truncate-end">identity, replay, and typed conversation</Text>
          {!selected ? (
            <Text color={THEME.stone}>No selected session.</Text>
          ) : (
            <>
              <Text color={THEME.foam} bold wrap="truncate-end">{selected.session.session_id}</Text>
              <Text color={THEME.stone} wrap="truncate-end">{selected.session.provider_id}:{selected.session.model_id} | {sessionStatusGlyph(selected.session.status)} {selected.session.status}</Text>
              <Text color={THEME.stone} wrap="truncate-end">branch {selected.session.branch_label ?? "none"} | replay {selected.replay_ok ? "ok" : selected.replay_issues.join(", ") || "issues"}</Text>
              <Text color={THEME.mist} bold>Summary</Text>
              <Text color={THEME.foam} wrap="truncate-end">{compactText(selected.session.summary ?? "none", 96)}</Text>
              {detail ? (
                <>
                  <Text color={THEME.mist} bold>Conversation</Text>
                  {conversation.length > 0 ? conversation.map((message, index) => (
                    <Text key={`${message.role}-${index}`} color={message.role === "you" ? THEME.wave : THEME.foam} wrap="truncate-end">
                      {message.role}: {compactText(message.content, 72)}
                    </Text>
                  )) : <Text color={THEME.stone}>No typed conversation events.</Text>}
                  <Text color={THEME.stone} wrap="truncate-end">
                    compact {detail.compaction_preview.event_count} events · {Math.round(detail.compaction_preview.compactable_ratio * 100)}%
                  </Text>
                </>
              ) : (
                <Text color={THEME.stone}>Detail pending.</Text>
              )}
            </>
          )}
        </Box>
      </Box>
    </Box>
  );
}
