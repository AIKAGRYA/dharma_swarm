import React from "react";
import {Box, Text} from "ink";

import type {SessionCatalogEntry, SessionPaneState} from "../types";
import {THEME} from "../theme";

type Props = {
  title: string;
  sessionPane: SessionPaneState;
};

function sessionEntries(sessionPane: SessionPaneState): SessionCatalogEntry[] {
  return sessionPane.catalog?.sessions ?? [];
}

function selectedSession(sessionPane: SessionPaneState): SessionCatalogEntry | undefined {
  const entries = sessionEntries(sessionPane);
  return entries.find((entry) => entry.session.session_id === sessionPane.selectedSessionId) ?? entries[0];
}

export function SessionsPane({title, sessionPane}: Props): React.ReactElement {
  const entries = sessionEntries(sessionPane);
  const selected = selectedSession(sessionPane);
  const detail = selected ? sessionPane.detailsBySessionId[selected.session.session_id] : undefined;

  return (
    // FACE-2 de-border (F-165): ridge = the one focused-pane border; inner
    // columns separate by space, selection by glyph+color (never border).
    <Box flexGrow={1} borderStyle="round" borderColor={THEME.ridge} paddingX={1} flexDirection="column">
      <Text color={THEME.wave} bold>{title}</Text>
      <Text color={THEME.stone}>{entries.length} sessions | j/k select | enter refresh detail</Text>
      <Box marginTop={1}>
        <Box width="35%" flexDirection="column" paddingX={1}>
          <Text color={THEME.mist} bold>Catalog</Text>
          <Text color={THEME.stone}>recent sessions and replay health</Text>
          {entries.length === 0 ? (
            <Text color={THEME.stone}>No sessions.</Text>
          ) : (
            entries.slice(0, 12).map((entry) => {
              const active = sessionPane.selectedSessionId === entry.session.session_id;
              return (
                <Box key={entry.session.session_id} flexDirection="column" marginTop={1}>
                  <Text color={active ? THEME.wave : THEME.foam} bold={active} backgroundColor={active ? THEME.harbor : undefined}>
                    {active ? "◆ " : "• "}
                    {entry.session.session_id}
                  </Text>
                  <Text color={active ? THEME.foam : THEME.stone}>
                    {"  "}{entry.session.provider_id}:{entry.session.model_id} | {entry.session.status}
                  </Text>
                </Box>
              );
            })
          )}
        </Box>
        <Box width="65%" marginLeft={1} flexDirection="column" paddingX={1}>
          <Text color={THEME.mist} bold>Drilldown</Text>
          <Text color={THEME.stone}>identity, replay, compaction, and recent events</Text>
          {!selected ? (
            <Text color={THEME.stone}>No selected session.</Text>
          ) : (
            <>
              <Text color={THEME.foam} bold>{selected.session.session_id}</Text>
              <Text color={THEME.stone}>{selected.session.provider_id}:{selected.session.model_id} | {selected.session.status}</Text>
              <Text color={THEME.stone}>branch {selected.session.branch_label ?? "none"} | replay {selected.replay_ok ? "ok" : selected.replay_issues.join(", ") || "issues"}</Text>
              <Text color={THEME.mist} bold>Summary</Text>
              <Text color={THEME.foam}>{selected.session.summary ?? "none"}</Text>
              {detail ? (
                <>
                  <Text color={THEME.mist} bold>Compaction</Text>
                  <Text color={THEME.foam}>{detail.compaction_preview.event_count} events | {Math.round(detail.compaction_preview.compactable_ratio * 100)}%</Text>
                  <Text color={THEME.mist} bold>Recent events</Text>
                  {detail.recent_events.slice(0, 6).map((event) => (
                    <Text key={event.event_id} color={THEME.stone}>
                      • {event.event_type} | {event.created_at}
                    </Text>
                  ))}
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
