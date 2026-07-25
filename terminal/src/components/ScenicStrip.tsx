import React from "react";
import {Box, Text} from "ink";

import {SCENIC_VARIANTS, SCENIC_WIDTHS} from "./scenicArt";
import {THEME} from "../theme";

// Hokusai's Great Wave (the real woodblock print, public domain), rendered as
// half-block truecolor cells: every terminal cell is U+2580 with foreground =
// top pixel and background = bottom pixel. One universally-covered glyph; the
// color does all the painting. This replaces the hand-typed glyph mosaic that
// shattered into confetti on fonts missing block-eighths/quadrants/U+224B
// (design truth finding 19). Regenerate via scripts/scenic_generate.py.

const HALF = "▀";

function truecolorCapable(): boolean {
  const colorterm = (process.env.COLORTERM ?? "").toLowerCase();
  return colorterm.includes("truecolor") || colorterm.includes("24bit");
}

export function ScenicStrip(): React.ReactElement {
  if (process.env.NODE_ENV === "test" || !process.stdout.isTTY) {
    return <Box />;
  }
  const columns = process.stdout.columns ?? 80;
  if (!truecolorCapable()) {
    // F-176 graceful degrade: a single quiet wave rule, never broken confetti.
    return (
      <Box marginTop={1} paddingX={1}>
        <Text color={THEME.wave} dimColor>
          {"~".repeat(Math.max(Math.min(columns - 4, 60), 8))}
        </Text>
      </Box>
    );
  }
  const width = SCENIC_WIDTHS.find((candidate) => candidate <= columns - 2) ?? null;
  if (width === null) {
    return <Box />;
  }
  const rows = SCENIC_VARIANTS[String(width)] ?? [];
  return (
    <Box flexDirection="column" marginTop={1} paddingX={1}>
      {rows.map((row, rowIndex) => (
        <Text key={`scenic-${rowIndex}`}>
          {row.map((segment, segmentIndex) => (
            <Text
              key={`scenic-${rowIndex}-${segmentIndex}`}
              color={segment.fg}
              backgroundColor={segment.bg}
            >
              {HALF.repeat(segment.n)}
            </Text>
          ))}
        </Text>
      ))}
    </Box>
  );
}
