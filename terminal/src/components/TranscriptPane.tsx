import React from "react";
import {Box, Text} from "ink";

import type {TranscriptLine} from "../types";
import {formatTranscriptLine} from "../transcriptFormatting";
import {THEME} from "../theme";

type Props = {
  title: string;
  lines: TranscriptLine[];
  scrollOffset?: number;
  windowSize?: number;
  subtitle?: string;
  emptyState?: string;
  accentColor?: string;
  // F-111 zen: no border, no title block — the conversation IS the screen.
  frameless?: boolean;
  // Claude-Code baseline: bottom-anchor the body so the newest line hugs the
  // composer (only meaningful when the frameless box grows, i.e. the zen face).
  bottomAnchor?: boolean;
};

function visibleWindow<T>(items: T[], scrollOffset: number, windowSize: number): T[] {
  const total = items.length;
  const end = Math.max(total - scrollOffset, 0);
  const start = Math.max(end - windowSize, 0);
  return items.slice(start, end);
}

export function TranscriptPane({
  title,
  lines,
  scrollOffset = 0,
  windowSize = 24,
  subtitle,
  emptyState = "No content yet.",
  accentColor = THEME.ink,
  frameless = false,
  bottomAnchor = false,
}: Props): React.ReactElement {
  const visible = visibleWindow(lines, scrollOffset, windowSize);
  const body =
    visible.length === 0 ? (
      <Text color={THEME.stone}>{emptyState}</Text>
    ) : (
      visible.map((line) => {
        const formatted = formatTranscriptLine(line);
        return (
          <Box key={line.id} flexShrink={0}>
            <Text color={formatted.color} bold={formatted.bold}>
              {formatted.prefix ? (
                <Text color={formatted.prefix.color} bold={formatted.prefix.bold} dimColor={formatted.prefix.dimColor}>
                  {formatted.prefix.text}
                </Text>
              ) : null}
              {formatted.segments.map((segment, index) => (
                <Text key={`${line.id}-${index}`} color={segment.color} bold={segment.bold} dimColor={segment.dimColor}>
                  {segment.text}
                </Text>
              ))}
            </Text>
          </Box>
        );
      })
    );
  if (frameless) {
    return (
      <Box
        flexGrow={1}
        flexDirection="column"
        justifyContent={bottomAnchor ? "flex-end" : "flex-start"}
        paddingX={1}
      >
        {body}
      </Box>
    );
  }
  return (
    <Box flexGrow={1} flexDirection="column" borderStyle="round" borderColor={THEME.ridge} paddingX={1}>
      <Text color={accentColor} bold>{title}</Text>
      {subtitle ? <Text color={THEME.stone}>{subtitle}</Text> : <Text color={THEME.stone}> </Text>}
      {subtitle ? <Text color={THEME.stone}> </Text> : null}
      {body}
    </Box>
  );
}
