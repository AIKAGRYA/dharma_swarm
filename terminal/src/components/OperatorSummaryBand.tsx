import React from "react";
import {Box, Text} from "ink";
import {THEME} from "../theme";

type SummaryItem = {
  label: string;
  value: string;
  tone?: "live" | "warn" | "critical" | "neutral";
};

type Props = {
  items: SummaryItem[];
  compact?: boolean;
};

function compactSummaryItems(items: SummaryItem[]): SummaryItem[] {
  const lookup = Object.fromEntries(items.map((item) => [item.label, item]));
  return [lookup.loop, lookup.verify, lookup.runtime ?? lookup.sessions, lookup.approvals].filter(Boolean) as SummaryItem[];
}

// Calm-density law: empty values (unknown/idle/none/0/clear) read as quiet
// stone, never bold foam — bold is earned by data, not by furniture.
function isEmptyValue(value: string): boolean {
  return /^(unknown|idle|none|clear|0|-|–)$/.test(value.trim());
}

function valueColor(item: SummaryItem): string {
  if (isEmptyValue(item.value)) {
    return THEME.stone;
  }
  switch (item.tone) {
    case "live":
      return THEME.moss;
    case "warn":
      return THEME.persimmon;
    case "critical":
      return THEME.vermilion;
    default:
      return THEME.foam;
  }
}

// FACE-2 command post (F-165 de-border): the operator summary is an
// unbordered ONE-row data strip at every width — labels in stone, values in
// foam/status tones. Borders are not separators; space is.
export function OperatorSummaryBand({items, compact = false}: Props): React.ReactElement {
  const shown = compact ? compactSummaryItems(items) : items;
  return (
    <Box paddingX={1} height={1} overflow="hidden">
      <Text wrap="truncate-end">
        {shown.map((item, index) => (
          <React.Fragment key={`${item.label}-${index}`}>
            {index > 0 ? <Text color={THEME.ink}>{"   "}</Text> : null}
            <Text color={THEME.stone}>{item.label}</Text>
            <Text color={THEME.stone}> </Text>
            <Text color={valueColor(item)} bold={!isEmptyValue(item.value) && (item.tone === "warn" || item.tone === "critical")}>
              {item.value}
            </Text>
          </React.Fragment>
        ))}
      </Text>
    </Box>
  );
}
