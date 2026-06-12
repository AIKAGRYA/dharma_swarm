import React from "react";
import {Box, Text} from "ink";
import {THEME} from "../theme";

type Props = {
  activeTitle: string;
  activeCount?: number;
  compact?: boolean;
};

// FACE-2 command post (F-165 de-border + F-164 status single-source): the
// header is ONE unbordered row carrying identity + place only. Status tokens
// (offline/live/ready/route/model/mode) live exclusively in the bottom
// status row — the header never repeats them.
export function ShellHeader({activeTitle, activeCount, compact = false}: Props): React.ReactElement {
  const clippedTitle = activeTitle.length > (compact ? 12 : 24) ? `${activeTitle.slice(0, compact ? 11 : 23)}…` : activeTitle;
  return (
    <Box paddingX={1}>
      <Text wrap="truncate-end">
        <Text color={THEME.wave} bold>
          ◆ DHARMA
        </Text>
        {compact ? null : <Text color={THEME.stone}> COMMAND POST</Text>}
        <Text color={THEME.ink}>{"  ·  "}</Text>
        <Text color={THEME.foam} bold>
          {clippedTitle}
        </Text>
        {!compact && typeof activeCount === "number" ? (
          <>
            <Text color={THEME.ink}>{"  ·  "}</Text>
            <Text color={THEME.stone}>panes </Text>
            <Text color={THEME.foam}>{activeCount}</Text>
          </>
        ) : null}
        <Text color={THEME.ink}>{"  ·  "}</Text>
        <Text color={THEME.stone}>F2 zen · ^K panes</Text>
      </Text>
    </Box>
  );
}
