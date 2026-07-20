import React from "react";
import {Box, Text} from "ink";
import {THEME} from "../theme";
import type {TranscriptLine} from "../types";
import {TranscriptPane} from "./TranscriptPane";

type Props = {
  lines: TranscriptLine[];
  narration: readonly string[];
  routeLabel: string;
  activeTitle: string;
  windowSize: number;
  width: number;
};

// The Navigator copilot rail: a persistent chat tether docked in the cockpit
// pane row. The operator keeps talking to the agent here (one shared composer
// at the root) while the Helm's panes stay visible beside it. The head band is
// the live "where am I / what did the agent just do" receipt; the body mirrors
// the chat transcript so the conversation is never out of sight.
export function NavigatorRail({lines, narration, routeLabel, activeTitle, windowSize, width}: Props): React.ReactElement {
  const recent = narration.slice(-2);
  return (
    <Box flexDirection="column" overflow="hidden" paddingX={1}>
      <Text color={THEME.wave} bold wrap="truncate-end">
        ◆ Navigator <Text color={THEME.stone}>· {routeLabel}</Text>
      </Text>
      {recent.length === 0 ? (
        <Text color={THEME.stone} wrap="truncate-end">▸ watching: {activeTitle}</Text>
      ) : (
        recent.map((line, index) => (
          <Text key={index} color={THEME.stone} wrap="truncate-end">▸ {line}</Text>
        ))
      )}
      <Text color={THEME.ink}>{"─".repeat(Math.max(0, width - 2))}</Text>
      <TranscriptPane
        frameless
        bottomAnchor
        title="Chat"
        lines={lines}
        windowSize={windowSize}
        emptyState="Talk to me here — I steer the Helm."
      />
    </Box>
  );
}
